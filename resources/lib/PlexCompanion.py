# -*- coding: utf-8 -*-
from logging import getLogger
from threading import Thread
from Queue import Queue, Empty
from socket import SHUT_RDWR
from urllib import urlencode

from xbmc import sleep, executebuiltin

from utils import settings, thread_methods
from plexbmchelper import listener, plexgdm, subscribers, httppersist
from PlexFunctions import ParseContainerKey, GetPlexMetadata
from PlexAPI import API
from playlist_func import get_pms_playqueue, get_plextype_from_xml
import player
import variables as v
import state

###############################################################################

log = getLogger("PLEX."+__name__)

###############################################################################


@thread_methods(add_suspends=['PMS_STATUS'])
class PlexCompanion(Thread):
    """
    """
    def __init__(self, callback=None):
        log.info("----===## Starting PlexCompanion ##===----")
        if callback is not None:
            self.mgr = callback
        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm()
        self.client.clientDetails()
        log.debug("Registration string is:\n%s"
                  % self.client.getClientDetails())
        # kodi player instance
        self.player = player.PKC_Player()

        Thread.__init__(self)

    def _getStartItem(self, string):
        """
        Grabs the Plex id from e.g. '/library/metadata/12987'

        and returns the tuple (typus, id) where typus is either 'queueId' or
        'plexId' and id is the corresponding id as a string
        """
        typus = 'plexId'
        if string.startswith('/library/metadata'):
            try:
                string = string.split('/')[3]
            except IndexError:
                string = ''
        else:
            log.error('Unknown string! %s' % string)
        return typus, string

    def processTasks(self, task):
        """
        Processes tasks picked up e.g. by Companion listener, e.g.
        {'action': 'playlist',
         'data': {'address': 'xyz.plex.direct',
                  'commandID': '7',
                  'containerKey': '/playQueues/6669?own=1&repeat=0&window=200',
                  'key': '/library/metadata/220493',
                  'machineIdentifier': 'xyz',
                  'offset': '0',
                  'port': '32400',
                  'protocol': 'https',
                  'token': 'transient-cd2527d1-0484-48e0-a5f7-f5caa7d591bd',
                  'type': 'video'}}
        """
        log.debug('Processing: %s' % task)
        data = task['data']

        # Get the token of the user flinging media (might be different one)
        token = data.get('token')
        if task['action'] == 'alexa':
            # e.g. Alexa
            xml = GetPlexMetadata(data['key'])
            try:
                xml[0].attrib
            except (AttributeError, IndexError, TypeError):
                log.error('Could not download Plex metadata')
                return
            api = API(xml[0])
            if api.getType() == v.PLEX_TYPE_ALBUM:
                log.debug('Plex music album detected')
                queue = self.mgr.playqueue.init_playqueue_from_plex_children(
                    api.getRatingKey())
                queue.plex_transient_token = token
            else:
                state.PLEX_TRANSIENT_TOKEN = token
                params = {
                    'mode': 'plex_node',
                    'key': '{server}%s' % data.get('key'),
                    'view_offset': data.get('offset'),
                    'play_directly': 'true',
                    'node': 'false'
                }
                executebuiltin('RunPlugin(plugin://%s?%s)'
                               % (v.ADDON_ID, urlencode(params)))

        elif (task['action'] == 'playlist' and
                data.get('address') == 'node.plexapp.com'):
            # E.g. watch later initiated by Companion
            state.PLEX_TRANSIENT_TOKEN = token
            params = {
                'mode': 'plex_node',
                'key': '{server}%s' % data.get('key'),
                'view_offset': data.get('offset'),
                'play_directly': 'true'
            }
            executebuiltin('RunPlugin(plugin://%s?%s)'
                           % (v.ADDON_ID, urlencode(params)))

        elif task['action'] == 'playlist':
            # Get the playqueue ID
            try:
                typus, ID, query = ParseContainerKey(data['containerKey'])
            except Exception as e:
                log.error('Exception while processing: %s' % e)
                import traceback
                log.error("Traceback:\n%s" % traceback.format_exc())
                return
            try:
                playqueue = self.mgr.playqueue.get_playqueue_from_type(
                    v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[data['type']])
            except KeyError:
                # E.g. Plex web does not supply the media type
                # Still need to figure out the type (video vs. music vs. pix)
                xml = GetPlexMetadata(data['key'])
                try:
                    xml[0].attrib
                except (AttributeError, IndexError, TypeError):
                    log.error('Could not download Plex metadata')
                    return
                api = API(xml[0])
                playqueue = self.mgr.playqueue.get_playqueue_from_type(
                    v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[api.getType()])
            self.mgr.playqueue.update_playqueue_from_PMS(
                playqueue,
                ID,
                repeat=query.get('repeat'),
                offset=data.get('offset'))
            playqueue.plex_transient_token = token

        elif task['action'] == 'refreshPlayQueue':
            # example data: {'playQueueID': '8475', 'commandID': '11'}
            xml = get_pms_playqueue(data['playQueueID'])
            if xml is None:
                return
            if len(xml) == 0:
                log.debug('Empty playqueue received - clearing playqueue')
                plex_type = get_plextype_from_xml(xml)
                if plex_type is None:
                    return
                playqueue = self.mgr.playqueue.get_playqueue_from_type(
                    v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[plex_type])
                playqueue.clear()
                return
            playqueue = self.mgr.playqueue.get_playqueue_from_type(
                v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[xml[0].attrib['type']])
            self.mgr.playqueue.update_playqueue_from_PMS(
                playqueue,
                data['playQueueID'])

    def run(self):
        # Ensure that sockets will be closed no matter what
        try:
            self.__run()
        finally:
            try:
                self.httpd.socket.shutdown(SHUT_RDWR)
            except AttributeError:
                pass
            finally:
                try:
                    self.httpd.socket.close()
                except AttributeError:
                    pass
        log.info("----===## Plex Companion stopped ##===----")

    def __run(self):
        self.httpd = False
        httpd = self.httpd
        # Cache for quicker while loops
        client = self.client
        thread_stopped = self.thread_stopped
        thread_suspended = self.thread_suspended

        # Start up instances
        requestMgr = httppersist.RequestMgr()
        subscriptionManager = subscribers.SubscriptionManager(
            requestMgr, self.player, self.mgr)

        queue = Queue(maxsize=100)
        self.queue = queue

        if settings('plexCompanion') == 'true':
            # Start up httpd
            start_count = 0
            while True:
                try:
                    httpd = listener.ThreadedHTTPServer(
                        client,
                        subscriptionManager,
                        queue,
                        ('', v.COMPANION_PORT),
                        listener.MyHandler)
                    httpd.timeout = 0.95
                    break
                except:
                    log.error("Unable to start PlexCompanion. Traceback:")
                    import traceback
                    log.error(traceback.print_exc())

                sleep(3000)

                if start_count == 3:
                    log.error("Error: Unable to start web helper.")
                    httpd = False
                    break

                start_count += 1
        else:
            log.info('User deactivated Plex Companion')

        client.start_all()

        message_count = 0
        if httpd:
            t = Thread(target=httpd.handle_request)

        while not thread_stopped():
            # If we are not authorized, sleep
            # Otherwise, we trigger a download which leads to a
            # re-authorizations
            while thread_suspended():
                if thread_stopped():
                    break
                sleep(1000)
            try:
                message_count += 1
                if httpd:
                    if not t.isAlive():
                        # Use threads cause the method will stall
                        t = Thread(target=httpd.handle_request)
                        t.start()

                    if message_count == 3000:
                        message_count = 0
                        if client.check_client_registration():
                            log.debug("Client is still registered")
                        else:
                            log.debug("Client is no longer registered. "
                                      "Plex Companion still running on port %s"
                                      % v.COMPANION_PORT)
                            client.register_as_client()
                # Get and set servers
                if message_count % 30 == 0:
                    subscriptionManager.serverlist = client.getServerList()
                    subscriptionManager.notify()
                    if not httpd:
                        message_count = 0
            except:
                log.warn("Error in loop, continuing anyway. Traceback:")
                import traceback
                log.warn(traceback.format_exc())
            # See if there's anything we need to process
            try:
                task = queue.get(block=False)
            except Empty:
                pass
            else:
                # Got instructions, process them
                self.processTasks(task)
                queue.task_done()
                # Don't sleep
                continue
            sleep(50)

        client.stop_all()

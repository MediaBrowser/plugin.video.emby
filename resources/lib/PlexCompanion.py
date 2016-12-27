# -*- coding: utf-8 -*-
import logging
from threading import Thread
import Queue
from socket import SHUT_RDWR

from xbmc import sleep

from utils import settings, ThreadMethodsAdditionalSuspend, ThreadMethods
from plexbmchelper import listener, plexgdm, subscribers, functions, \
    httppersist, plexsettings
from PlexFunctions import ParseContainerKey, GetPlayQueue, \
    ConvertPlexToKodiTime
import player

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


@ThreadMethodsAdditionalSuspend('plex_serverStatus')
@ThreadMethods
class PlexCompanion(Thread):
    """
    """
    def __init__(self, callback=None):
        log.info("----===## Starting PlexCompanion ##===----")
        if callback is not None:
            self.mgr = callback
        self.playqueue = self.mgr.playqueue
        self.settings = plexsettings.getSettings()
        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm()
        self.client.clientDetails(self.settings)
        log.debug("Registration string is: %s "
                  % self.client.getClientDetails())
        # kodi player instance
        self.player = player.Player()

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
        Processes tasks picked up e.g. by Companion listener

        task = {
            'action':       'playlist'
            'data':         as received from Plex companion
        }
        """
        log.debug('Processing: %s' % task)
        data = task['data']

        if task['action'] == 'playlist':
            # Get the playqueue ID
            try:
                _, ID, query = ParseContainerKey(data['containerKey'])
            except Exception as e:
                log.error('Exception while processing: %s' % e)
                import traceback
                log.error("Traceback:\n%s" % traceback.format_exc())
                return
            self.mgr.playqueue.update_playqueue_with_companion(data)

            self.playqueue = self.mgr.playqueue.get_playqueue_from_plextype(
                data.get('type'))
            if queueId != self.playqueue.ID:
                log.info('New playlist received, updating!')
                xml = GetPlayQueue(queueId)
                if xml in (None, 401):
                    log.error('Could not download Plex playlist.')
                    return
                # Clear existing playlist on the Kodi side
                self.playqueue.clear()
                # Set new values
                self.playqueue.QueueId(queueId)
                self.playqueue.PlayQueueVersion(int(
                    xml.attrib.get('playQueueVersion')))
                self.playqueue.Guid(xml.attrib.get('guid'))
                items = []
                for item in xml:
                    items.append({
                        'playQueueItemID': item.get('playQueueItemID'),
                        'plexId': item.get('ratingKey'),
                        'kodiId': None})
                self.playqueue.playAll(
                    items,
                    startitem=self._getStartItem(data.get('key', '')),
                    offset=ConvertPlexToKodiTime(data.get('offset', 0)))
                log.info('Initiated playlist no %s with version %s'
                         % (self.playqueue.QueueId(),
                            self.playqueue.PlayQueueVersion()))
            else:
                log.error('This has never happened before!')

    def run(self):
        httpd = False
        # Cache for quicker while loops
        client = self.client
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended

        # Start up instances
        requestMgr = httppersist.RequestMgr()
        jsonClass = functions.jsonClass(requestMgr, self.settings)
        subscriptionManager = subscribers.SubscriptionManager(
            jsonClass, requestMgr, self.player, self.playqueue)

        queue = Queue.Queue(maxsize=100)

        if settings('plexCompanion') == 'true':
            # Start up httpd
            start_count = 0
            while True:
                try:
                    httpd = listener.ThreadedHTTPServer(
                        client,
                        subscriptionManager,
                        jsonClass,
                        self.settings,
                        queue,
                        ('', self.settings['myport']),
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

        while not threadStopped():
            # If we are not authorized, sleep
            # Otherwise, we trigger a download which leads to a
            # re-authorizations
            while threadSuspended():
                if threadStopped():
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
                            log.info("Client is no longer registered. "
                                     "Plex Companion still running on port %s"
                                     % self.settings['myport'])
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
            except Queue.Empty:
                pass
            else:
                # Got instructions, process them
                self.processTasks(task)
                queue.task_done()
                # Don't sleep
                continue
            sleep(20)

        client.stop_all()
        if httpd:
            try:
                httpd.socket.shutdown(SHUT_RDWR)
            except:
                pass
            finally:
                httpd.socket.close()
        log.info("----===## Plex Companion stopped ##===----")

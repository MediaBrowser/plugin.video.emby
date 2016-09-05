# -*- coding: utf-8 -*-
import threading
import traceback
import socket
import Queue

import xbmc

import utils
from plexbmchelper import listener, plexgdm, subscribers, functions, \
    httppersist, settings
from PlexFunctions import ParseContainerKey, GetPlayQueue, \
    ConvertPlexToKodiTime
import playlist
import player


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('plex_serverStatus')
@utils.ThreadMethods
class PlexCompanion(threading.Thread):
    """
    Initialize with a Queue for callbacks
    """
    def __init__(self):
        self.logMsg("----===## Starting PlexCompanion ##===----", 1)
        self.settings = settings.getSettings()

        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm()
        self.client.clientDetails(self.settings)
        self.logMsg("Registration string is: %s "
                    % self.client.getClientDetails(), 2)

        # Initialize playlist/queue stuff
        self.playlist = playlist.Playlist('video')

        # kodi player instance
        self.player = player.Player()

        threading.Thread.__init__(self)

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
            self.logMsg('Unknown string! %s' % string, -1)
        return typus, string

    def processTasks(self, task):
        """
        Processes tasks picked up e.g. by Companion listener

        task = {
            'action':       'playlist'
            'data':         as received from Plex companion
        }
        """
        self.logMsg('Processing: %s' % task, 2)
        data = task['data']

        if task['action'] == 'playlist':
            try:
                _, queueId, query = ParseContainerKey(data['containerKey'])
            except Exception as e:
                self.logMsg('Exception while processing: %s' % e, -1)
                import traceback
                self.logMsg("Traceback:\n%s" % traceback.format_exc(), -1)
                return
            if self.playlist is not None:
                if self.playlist.Typus() != data.get('type'):
                    self.logMsg('Switching to Kodi playlist of type %s'
                                % data.get('type'), 1)
                    self.playlist = None
            if self.playlist is None:
                if data.get('type') == 'music':
                    self.playlist = playlist.Playlist('music')
                elif data.get('type') == 'video':
                    self.playlist = playlist.Playlist('video')
                else:
                    self.playlist = playlist.Playlist()
            if self.playlist is None:
                self.logMsg('Could not initialize playlist', -1)
                return
            if queueId != self.playlist.QueueId():
                self.logMsg('New playlist received, updating!', 1)
                xml = GetPlayQueue(queueId)
                if xml in (None, 401):
                    self.logMsg('Could not download Plex playlist.', -1)
                    return
                # Clear existing playlist on the Kodi side
                self.playlist.clear()
                # Set new values
                self.playlist.QueueId(queueId)
                self.playlist.PlayQueueVersion(int(
                    xml.attrib.get('playQueueVersion')))
                self.playlist.Guid(xml.attrib.get('guid'))
                items = []
                for item in xml:
                    items.append({
                        'playQueueItemID': item.get('playQueueItemID'),
                        'plexId': item.get('ratingKey'),
                        'kodiId': None})
                self.playlist.playAll(
                    items,
                    startitem=self._getStartItem(data.get('key', '')),
                    offset=ConvertPlexToKodiTime(data.get('offset', 0)))
                self.logMsg('Initiated playlist no %s with version %s'
                            % (self.playlist.QueueId(),
                               self.playlist.PlayQueueVersion()))
            else:
                self.logMsg('This has never happened before!', -1)

    def run(self):
        httpd = False
        # Cache for quicker while loops
        log = self.logMsg
        client = self.client
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended

        # Start up instances
        requestMgr = httppersist.RequestMgr()
        jsonClass = functions.jsonClass(requestMgr, self.settings)
        subscriptionManager = subscribers.SubscriptionManager(
            jsonClass, requestMgr, self.player, self.playlist)

        queue = Queue.Queue(maxsize=100)

        if utils.settings('plexCompanion') == 'true':
            self.logMsg('User activated Plex Companion', 0)
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
                    log("Unable to start PlexCompanion. Traceback:", -1)
                    log(traceback.print_exc(), -1)

                xbmc.sleep(3000)

                if start_count == 3:
                    log("Error: Unable to start web helper.", -1)
                    httpd = False
                    break

                start_count += 1
        else:
            self.logMsg('User deactivated Plex Companion', 0)

        client.start_all()

        message_count = 0
        if httpd:
            t = threading.Thread(target=httpd.handle_request)

        while not threadStopped():
            # If we are not authorized, sleep
            # Otherwise, we trigger a download which leads to a
            # re-authorizations
            while threadSuspended():
                if threadStopped():
                    break
                xbmc.sleep(1000)
            try:
                message_count += 1
                if httpd:
                    if not t.isAlive():
                        # Use threads cause the method will stall
                        t = threading.Thread(target=httpd.handle_request)
                        t.start()

                    if message_count == 3000:
                        message_count = 0
                        if client.check_client_registration():
                            log("Client is still registered", 1)
                        else:
                            log("Client is no longer registered", 1)
                            log("Plex Companion still running on port %s"
                                % self.settings['myport'], 1)

                # Get and set servers
                if message_count % 30 == 0:
                    subscriptionManager.serverlist = client.getServerList()
                    subscriptionManager.notify()
                    if not httpd:
                        message_count = 0
            except:
                log("Error in loop, continuing anyway. Traceback:", 1)
                log(traceback.format_exc(), 1)
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
            xbmc.sleep(20)

        client.stop_all()
        if httpd:
            try:
                httpd.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            finally:
                httpd.socket.close()
        log("----===## Plex Companion stopped ##===----", 0)

# -*- coding: utf-8 -*-

###############################################################################

import os
import sys
from datetime import datetime
import Queue

import xbmc
import xbmcaddon
import xbmcgui

###############################################################################

_addon = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
try:
    addon_path = _addon.getAddonInfo('path').decode('utf-8')
except TypeError:
    addon_path = _addon.getAddonInfo('path').decode()
try:
    base_resource = xbmc.translatePath(os.path.join(
        addon_path,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    base_resource = xbmc.translatePath(os.path.join(
        addon_path,
        'resources',
        'lib')).decode()

sys.path.append(base_resource)

###############################################################################

import utils
import userclient
import clientinfo
import initialsetup
import kodimonitor
import librarysync
import player
import videonodes
import websocket_client as wsc
import downloadutils
import playlist

import PlexAPI
import PlexCompanion
import PlexFunctions as PF

###############################################################################


@utils.logging
class Service():

    welcome_msg = True
    server_online = True
    warn_auth = True

    userclient_running = False
    websocket_running = False
    library_running = False
    kodimonitor_running = False
    plexCompanion_running = False

    def __init__(self):

        log = self.logMsg
        window = utils.window

        self.clientInfo = clientinfo.ClientInfo()
        logLevel = self.getLogLevel()
        self.monitor = xbmc.Monitor()

        window('plex_logLevel', value=str(logLevel))
        window('plex_kodiProfile', value=xbmc.translatePath("special://profile"))
        window('plex_pluginpath', value=utils.settings('useDirectPaths'))

        # Initial logging
        log("======== START %s ========" % self.addonName, 0)
        log("Platform: %s" % (self.clientInfo.getPlatform()), 0)
        log("KODI Version: %s" % xbmc.getInfoLabel('System.BuildVersion'), 0)
        log("%s Version: %s" % (self.addonName, self.clientInfo.getVersion()), 0)
        log("Using plugin paths: %s" % (utils.settings('useDirectPaths') != "true"), 0)
        log("Log Level: %s" % logLevel, 0)

        # Reset window props for profile switch
        properties = [

            "plex_online", "plex_serverStatus", "plex_onWake",
            "plex_dbCheck", "plex_kodiScan",
            "plex_shouldStop", "currUserId", "plex_dbScan",
            "plex_initialScan", "plex_customplaylist", "plex_playbackProps",
            "plex_runLibScan", "plex_username", "pms_token", "plex_token",
            "pms_server", "plex_machineIdentifier", "plex_servername",
            "plex_authenticated", "PlexUserImage", "useDirectPaths",
            "replaceSMB", "remapSMB", "remapSMBmovieOrg", "remapSMBtvOrg",
            "remapSMBmusicOrg", "remapSMBmovieNew", "remapSMBtvNew",
            "remapSMBmusicNew", "remapSMBphotoOrg", "remapSMBphotoNew",
            "suspend_LibraryThread", "plex_terminateNow",
            "kodiplextimeoffset", "countError", "countUnauthorized"
        ]
        for prop in properties:
            window(prop, clear=True)

        # Clear video nodes properties
        videonodes.VideoNodes().clearProperties()

        # Set the minimum database version
        window('plex_minDBVersion', value="1.1.5")

        # Initialize playlist/queue stuff
        self.queueId = None
        self.playlist = None

    def getLogLevel(self):
        try:
            logLevel = int(utils.settings('logLevel'))
        except ValueError:
            logLevel = 0
        return logLevel

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
                _, queueId, query = PF.ParseContainerKey(data['containerKey'])
            except Exception as e:
                self.logMsg('Exception while processing: %s' % e, -1)
                import traceback
                self.logMsg("Traceback:\n%s" % traceback.format_exc(), -1)
                return
            if self.playlist is not None:
                if self.playlist.typus != data.get('type'):
                    self.logMsg('Switching to Kodi playlist of type %s'
                                % data.get('type'), 1)
                    self.playlist = None
                    self.queueId = None
            if self.playlist is None:
                if data.get('type') == 'music':
                    self.playlist = playlist.Playlist('music')
                elif data.get('type') == 'video':
                    self.playlist = playlist.Playlist('video')
                else:
                    self.playlist = playlist.Playlist()
            if queueId != self.queueId:
                self.logMsg('New playlist received, updating!', 1)
                self.queueId = queueId
                xml = PF.GetPlayQueue(queueId)
                if xml in (None, 401):
                    self.logMsg('Could not download Plex playlist.', -1)
                    return
                # Clear existing playlist on the Kodi side
                self.playlist.clear()
                items = []
                for item in xml:
                    items.append({
                        'queueId': item.get('playQueueItemID'),
                        'plexId': item.get('ratingKey'),
                        'kodiId': None
                    })
                self.playlist.playAll(
                    items,
                    startitem=self._getStartItem(data.get('key', '')),
                    offset=PF.ConvertPlexToKodiTime(data.get('offset', 0)))
            else:
                self.logMsg('This has never happened before!', -1)

    def ServiceEntryPoint(self):

        log = self.logMsg
        window = utils.window
        lang = utils.language

        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        monitor = self.monitor
        kodiProfile = xbmc.translatePath("special://profile")

        # Server auto-detect
        initialsetup.InitialSetup().setup()

        # Queue for background sync
        queue = Queue.Queue(maxsize=200)
        # Queue for PlexCompanion listener
        companionQueue = Queue.Queue(maxsize=100)

        connectMsg = True if utils.settings('connectMsg') == 'true' else False

        # Initialize important threads
        user = userclient.UserClient()
        ws = wsc.WebSocket(queue)
        library = librarysync.LibrarySync(queue)
        kplayer = player.Player()
        xplayer = xbmc.Player()
        plx = PlexAPI.PlexAPI()

        # Sync and progress report
        lastProgressUpdate = datetime.today()

        counter = 0
        while not monitor.abortRequested():

            if window('plex_kodiProfile') != kodiProfile:
                # Profile change happened, terminate this thread and others
                log("Kodi profile was: %s and changed to: %s. Terminating old "
                    "PlexKodiConnect thread."
                    % (kodiProfile, utils.window('plex_kodiProfile')), 1)
                
                break
            
            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server

            if window('plex_online') == "true":
                # Plex server is online
                # Verify if user is set and has access to the server
                if (user.currUser is not None) and user.HasAccess:
                    # If an item is playing
                    if xplayer.isPlaying():
                        try:
                            # Update and report progress
                            playtime = xplayer.getTime()
                            totalTime = xplayer.getTotalTime()
                            currentFile = kplayer.currentFile

                            # Update positionticks
                            if kplayer.played_info.get(currentFile) is not None:
                                kplayer.played_info[currentFile]['currentPosition'] = playtime
                            
                            td = datetime.today() - lastProgressUpdate
                            secDiff = td.seconds
                            
                            # Report progress to Plex server
                            if (secDiff > 3):
                                kplayer.reportPlayback()
                                lastProgressUpdate = datetime.today()
                            
                            elif window('plex_command') == "true":
                                # Received a remote control command that
                                # requires updating immediately
                                window('plex_command', clear=True)
                                kplayer.reportPlayback()
                                lastProgressUpdate = datetime.today()
                        except Exception as e:
                            log("Exception in Playback Monitor Service: %s" % e, 1)
                            pass
                    try:
                        task = companionQueue.get(block=False)
                    except Queue.Empty:
                        pass
                    else:
                        # Got instructions from Plex Companions, process them
                        self.processTasks(task)
                        companionQueue.task_done()
                    if not self.kodimonitor_running:
                        # Start up events
                        self.warn_auth = True
                        if connectMsg and self.welcome_msg:
                            # Reset authentication warnings
                            self.welcome_msg = False
                            xbmcgui.Dialog().notification(
                                heading=self.addonName,
                                message="%s %s" % (lang(33000), user.currUser),
                                icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                                time=2000,
                                sound=False)
                        # Start monitoring kodi events
                        self.kodimonitor_running = True
                        kodimonitor.KodiMonitor()

                        # Start the Websocket Client
                        if not self.websocket_running:
                            self.websocket_running = True
                            ws.start()
                        # Start the syncing thread
                        if not self.library_running:
                            self.library_running = True
                            library.start()
                        # Start the Plex Companion thread
                        if not self.plexCompanion_running:
                            self.plexCompanion_running = True
                            plexCompanion = PlexCompanion.PlexCompanion(
                                companionQueue)
                            plexCompanion.start()
                else:
                    if (user.currUser is None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future warning
                        self.warn_auth = False
                        log("Not authenticated yet.", 1)

                    # User access is restricted.
                    # Keep verifying until access is granted
                    # unless server goes offline or Kodi is shut down.
                    while user.HasAccess == False:
                        # Verify access with an API call
                        user.hasAccess()

                        if window('plex_online') != "true":
                            # Server went offline
                            break

                        if monitor.waitForAbort(5):
                            # Abort was requested while waiting. We should exit
                            break
                        xbmc.sleep(50)
            else:
                # Wait until Plex server is online
                # or Kodi is shut down.
                while not monitor.abortRequested():
                    server = user.getServer()
                    if server is False:
                        # No server info set in add-on settings
                        pass
                    elif plx.CheckConnection(server, verifySSL=True) is False:
                        # Server is offline or cannot be reached
                        # Alert the user and suppress future warning
                        if self.server_online:
                            log("Server is offline.", -1)
                            window('plex_online', value="false")
                            # Suspend threads
                            window('suspend_LibraryThread', value='true')
                            xbmcgui.Dialog().notification(
                                heading=lang(33001),
                                message="%s %s"
                                        % (self.addonName, lang(33002)),
                                icon="special://home/addons/plugin.video."
                                     "plexkodiconnect/icon.png",
                                sound=False)
                        self.server_online = False
                        counter += 1
                        # Periodically check if the IP changed, e.g. per minute
                        if counter > 30:
                            counter = 0
                            setup = initialsetup.InitialSetup()
                            tmp = setup.PickPMS()
                            if tmp is not None:
                                setup.WritePMStoSettings(tmp)
                    else:
                        # Server is online
                        counter = 0
                        if not self.server_online:
                            # Server was offline when Kodi started.
                            # Wait for server to be fully established.
                            if monitor.waitForAbort(5):
                                # Abort was requested while waiting.
                                break
                            # Alert the user that server is online.
                            xbmcgui.Dialog().notification(
                                heading=self.addonName,
                                message=lang(33003),
                                icon="special://home/addons/plugin.video."
                                     "plexkodiconnect/icon.png",
                                time=5000,
                                sound=False)
                        self.server_online = True
                        log("Server %s is online and ready." % server, 1)
                        window('plex_online', value="true")
                        if window('plex_authenticated') == 'true':
                            # Server got offline when we were authenticated.
                            # Hence resume threads
                            window('suspend_LibraryThread', clear=True)

                        # Start the userclient thread
                        if not self.userclient_running:
                            self.userclient_running = True
                            user.start()

                        break

                    if monitor.waitForAbort(2):
                        # Abort was requested while waiting.
                        break

            if monitor.waitForAbort(0.05):
                # Abort was requested while waiting. We should exit
                break

        # Terminating PlexKodiConnect

        # Tell all threads to terminate (e.g. several lib sync threads)
        utils.window('plex_terminateNow', value='true')

        try:
            plexCompanion.stopThread()
        except:
            xbmc.log('plexCompanion already shut down')

        try:
            library.stopThread()
        except:
            xbmc.log('Library sync already shut down')

        try:
            ws.stopThread()
        except:
            xbmc.log('Websocket client already shut down')

        try:
            user.stopThread()
        except:
            xbmc.log('User client already shut down')

        try:
            downloadutils.DownloadUtils().stopSession()
        except:
            pass

        log("======== STOP %s ========" % self.addonName, 0)

# Delay option
delay = int(utils.settings('startupDelay'))

xbmc.log("Delaying Plex startup by: %s sec..." % delay)
if delay and xbmc.Monitor().waitForAbort(delay):
    # Start the service
    xbmc.log("Abort requested while waiting. PKC not started.")
else:
    Service().ServiceEntryPoint()

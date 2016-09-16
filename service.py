# -*- coding: utf-8 -*-

###############################################################################

import logging
import os
import sys
import Queue

import xbmc
import xbmcaddon
import xbmcgui

###############################################################################

_addon = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
try:
    _addon_path = _addon.getAddonInfo('path').decode('utf-8')
except TypeError:
    _addon_path = _addon.getAddonInfo('path').decode()
try:
    _base_resource = xbmc.translatePath(os.path.join(
        _addon_path,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    _base_resource = xbmc.translatePath(os.path.join(
        _addon_path,
        'resources',
        'lib')).decode()
sys.path.append(_base_resource)

###############################################################################

from utils import settings, window, language as lang
import userclient
import clientinfo
import initialsetup
import kodimonitor
import librarysync
import videonodes
import websocket_client as wsc
import downloadutils

import PlexAPI
import PlexCompanion

###############################################################################

import loghandler

loghandler.config()
log = logging.getLogger("PLEX.default")
addonName = 'PlexKodiConnect'

###############################################################################


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

        self.clientInfo = clientinfo.ClientInfo()
        logLevel = self.getLogLevel()
        self.monitor = xbmc.Monitor()

        window('plex_logLevel', value=str(logLevel))
        window('plex_kodiProfile',
               value=xbmc.translatePath("special://profile"))

        # Initial logging
        log.warn("======== START %s ========" % addonName)
        log.warn("Platform: %s" % (self.clientInfo.getPlatform()))
        log.warn("KODI Version: %s" % xbmc.getInfoLabel('System.BuildVersion'))
        log.warn("%s Version: %s" % (addonName, self.clientInfo.getVersion()))
        log.warn("Using plugin paths: %s"
                 % (settings('useDirectPaths') != "true"))
        log.warn("Log Level: %s" % logLevel)

        # Reset window props for profile switch
        properties = [

            "plex_online", "plex_serverStatus", "plex_onWake",
            "plex_dbCheck", "plex_kodiScan",
            "plex_shouldStop", "currUserId", "plex_dbScan",
            "plex_initialScan", "plex_customplaylist", "plex_playbackProps",
            "plex_runLibScan", "plex_username", "pms_token", "plex_token",
            "pms_server", "plex_machineIdentifier", "plex_servername",
            "plex_authenticated", "PlexUserImage", "useDirectPaths",
            "suspend_LibraryThread", "plex_terminateNow",
            "kodiplextimeoffset", "countError", "countUnauthorized"
        ]
        for prop in properties:
            window(prop, clear=True)

        # Clear video nodes properties
        videonodes.VideoNodes().clearProperties()

        # Set the minimum database version
        window('plex_minDBVersion', value="1.1.5")

    def getLogLevel(self):
        try:
            logLevel = int(settings('logLevel'))
        except ValueError:
            logLevel = 0
        return logLevel

    def ServiceEntryPoint(self):
        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        monitor = self.monitor
        kodiProfile = xbmc.translatePath("special://profile")

        # Server auto-detect
        initialsetup.InitialSetup().setup()

        # Queue for background sync
        queue = Queue.Queue(maxsize=200)

        connectMsg = True if settings('connectMsg') == 'true' else False

        # Initialize important threads
        user = userclient.UserClient()
        ws = wsc.WebSocket(queue)
        library = librarysync.LibrarySync(queue)
        plx = PlexAPI.PlexAPI()

        counter = 0
        while not monitor.abortRequested():

            if window('plex_kodiProfile') != kodiProfile:
                # Profile change happened, terminate this thread and others
                log.warn("Kodi profile was: %s and changed to: %s. "
                         "Terminating old PlexKodiConnect thread."
                         % (kodiProfile, window('plex_kodiProfile')))
                break

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server

            if window('plex_online') == "true":
                # Plex server is online
                # Verify if user is set and has access to the server
                if (user.currUser is not None) and user.HasAccess:
                    if not self.kodimonitor_running:
                        # Start up events
                        self.warn_auth = True
                        if connectMsg and self.welcome_msg:
                            # Reset authentication warnings
                            self.welcome_msg = False
                            xbmcgui.Dialog().notification(
                                heading=addonName,
                                message="%s %s" % (lang(33000), user.currUser),
                                icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                                time=2000,
                                sound=False)
                        # Start monitoring kodi events
                        self.kodimonitor_running = kodimonitor.KodiMonitor()

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
                            plexCompanion = PlexCompanion.PlexCompanion()
                            plexCompanion.start()
                else:
                    if (user.currUser is None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future warning
                        self.warn_auth = False
                        log.warn("Not authenticated yet.")

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
                            log.error("Server is offline.")
                            window('plex_online', value="false")
                            # Suspend threads
                            window('suspend_LibraryThread', value='true')
                            xbmcgui.Dialog().notification(
                                heading=lang(33001),
                                message="%s %s"
                                        % (addonName, lang(33002)),
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
                                heading=addonName,
                                message=lang(33003),
                                icon="special://home/addons/plugin.video."
                                     "plexkodiconnect/icon.png",
                                time=5000,
                                sound=False)
                        self.server_online = True
                        log.warn("Server %s is online and ready." % server)
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
        window('plex_terminateNow', value='true')

        try:
            plexCompanion.stopThread()
        except:
            log.warn('plexCompanion already shut down')

        try:
            library.stopThread()
        except:
            log.warn('Library sync already shut down')

        try:
            ws.stopThread()
        except:
            log.warn('Websocket client already shut down')

        try:
            user.stopThread()
        except:
            log.warn('User client already shut down')

        try:
            downloadutils.DownloadUtils().stopSession()
        except:
            pass

        log.warn("======== STOP %s ========" % addonName)

# Delay option
delay = int(settings('startupDelay'))

log.warn("Delaying Plex startup by: %s sec..." % delay)
if delay and xbmc.Monitor().waitForAbort(delay):
    # Start the service
    log.warn("Abort requested while waiting. PKC not started.")
else:
    Service().ServiceEntryPoint()

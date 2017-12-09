# -*- coding: utf-8 -*-
###############################################################################
from logging import getLogger
from os import path as os_path
from sys import path as sys_path, argv

from xbmc import translatePath, Monitor
from xbmcaddon import Addon

###############################################################################

_addon = Addon(id='plugin.video.plexkodiconnect')
try:
    _addon_path = _addon.getAddonInfo('path').decode('utf-8')
except TypeError:
    _addon_path = _addon.getAddonInfo('path').decode()
try:
    _base_resource = translatePath(os_path.join(
        _addon_path,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    _base_resource = translatePath(os_path.join(
        _addon_path,
        'resources',
        'lib')).decode()
sys_path.append(_base_resource)

###############################################################################

from utils import settings, window, language as lang, dialog, tryDecode
from userclient import UserClient
import initialsetup
from kodimonitor import KodiMonitor
from librarysync import LibrarySync
import videonodes
from websocket_client import PMS_Websocket, Alexa_Websocket
import downloadutils
from playqueue import Playqueue

import PlexAPI
from PlexCompanion import PlexCompanion
from command_pipeline import Monitor_Window
from playback_starter import Playback_Starter
from artwork import Image_Cache_Thread
from json_rpc import get_setting, set_setting
import variables as v
import state

###############################################################################
import loghandler

loghandler.config()
log = getLogger("PLEX.service")
###############################################################################

def set_webserver():
    """
    Set the Kodi webserver details - used to set the texture cache
    """
    if get_setting('services.webserver') in (None, False):
        # Enable the webserver, it is disabled
        set_setting('services.webserver', True)
        # Set standard port and username
        set_setting('services.webserverport', 8080)
        set_setting('services.webserverusername', 'kodi')
    # Webserver already enabled
    state.WEBSERVER_PORT = get_setting('services.webserverport')
    state.WEBSERVER_USERNAME = get_setting('services.webserverusername')
    state.WEBSERVER_PASSWORD = get_setting('services.webserverpassword')


class Service():

    server_online = True
    warn_auth = True

    user = None
    ws = None
    library = None
    plexCompanion = None
    playqueue = None

    user_running = False
    ws_running = False
    alexa_running = False
    library_running = False
    plexCompanion_running = False
    playqueue_running = False
    kodimonitor_running = False
    playback_starter_running = False
    image_cache_thread_running = False

    def __init__(self):
        set_webserver()
        self.monitor = Monitor()

        window('plex_kodiProfile',
               value=tryDecode(translatePath("special://profile")))
        window('fetch_pms_item_number',
               value=settings('fetch_pms_item_number'))

        # Initial logging
        log.info("======== START %s ========" % v.ADDON_NAME)
        log.info("Platform: %s" % v.PLATFORM)
        log.info("KODI Version: %s" % v.KODILONGVERSION)
        log.info("%s Version: %s" % (v.ADDON_NAME, v.ADDON_VERSION))
        log.info("Using plugin paths: %s"
                 % (settings('useDirectPaths') != "true"))
        log.info("Number of sync threads: %s"
                 % settings('syncThreadNumber'))
        log.info("Full sys.argv received: %s" % argv)

        # Reset window props for profile switch
        properties = [
            "plex_online", "plex_serverStatus", "plex_onWake",
            "plex_kodiScan",
            "plex_shouldStop", "plex_dbScan",
            "plex_initialScan", "plex_customplayqueue", "plex_playbackProps",
            "pms_token", "plex_token",
            "pms_server", "plex_machineIdentifier", "plex_servername",
            "plex_authenticated", "PlexUserImage", "useDirectPaths",
            "countError", "countUnauthorized",
            "plex_restricteduser", "plex_allows_mediaDeletion",
            "plex_command", "plex_result", "plex_force_transcode_pix"
        ]
        for prop in properties:
            window(prop, clear=True)

        # Clear video nodes properties
        videonodes.VideoNodes().clearProperties()

        # Set the minimum database version
        window('plex_minDBVersion', value="1.5.10")

    def __stop_PKC(self):
        """
        Kodi's abortRequested is really unreliable :-(
        """
        return self.monitor.abortRequested() or state.STOP_PKC

    def ServiceEntryPoint(self):
        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        __stop_PKC = self.__stop_PKC
        monitor = self.monitor
        kodiProfile = v.KODI_PROFILE

        # Detect playback start early on
        self.command_pipeline = Monitor_Window(self)
        self.command_pipeline.start()

        # Server auto-detect
        initialsetup.InitialSetup().setup()

        # Initialize important threads, handing over self for callback purposes
        self.user = UserClient(self)
        self.ws = PMS_Websocket(self)
        self.alexa = Alexa_Websocket(self)
        self.library = LibrarySync(self)
        self.plexCompanion = PlexCompanion(self)
        self.playqueue = Playqueue(self)
        self.playback_starter = Playback_Starter(self)
        if settings('enableTextureCache') == "true":
            self.image_cache_thread = Image_Cache_Thread()

        plx = PlexAPI.PlexAPI()

        welcome_msg = True
        counter = 0
        while not __stop_PKC():

            if window('plex_kodiProfile') != kodiProfile:
                # Profile change happened, terminate this thread and others
                log.info("Kodi profile was: %s and changed to: %s. "
                         "Terminating old PlexKodiConnect thread."
                         % (kodiProfile,
                            window('plex_kodiProfile')))
                break

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server

            if window('plex_online') == "true":
                # Plex server is online
                # Verify if user is set and has access to the server
                if (self.user.currUser is not None) and self.user.HasAccess:
                    if not self.kodimonitor_running:
                        # Start up events
                        self.warn_auth = True
                        if welcome_msg is True:
                            # Reset authentication warnings
                            welcome_msg = False
                            dialog('notification',
                                   lang(29999),
                                   "%s %s" % (lang(33000),
                                              self.user.currUser),
                                   icon='{plex}',
                                   time=2000,
                                   sound=False)
                        # Start monitoring kodi events
                        self.kodimonitor_running = KodiMonitor(self)
                        # Start playqueue client
                        if not self.playqueue_running:
                            self.playqueue_running = True
                            self.playqueue.start()
                        # Start the Websocket Client
                        if not self.ws_running:
                            self.ws_running = True
                            self.ws.start()
                        # Start the Alexa thread
                        if (not self.alexa_running and
                                settings('enable_alexa') == 'true'):
                            self.alexa_running = True
                            self.alexa.start()
                        # Start the syncing thread
                        if not self.library_running:
                            self.library_running = True
                            self.library.start()
                        # Start the Plex Companion thread
                        if not self.plexCompanion_running:
                            self.plexCompanion_running = True
                            self.plexCompanion.start()
                        if not self.playback_starter_running:
                            self.playback_starter_running = True
                            self.playback_starter.start()
                        if (not self.image_cache_thread_running and
                                settings('enableTextureCache') == "true"):
                            self.image_cache_thread_running = True
                            self.image_cache_thread.start()
                else:
                    if (self.user.currUser is None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future
                        # warning
                        self.warn_auth = False
                        log.warn("Not authenticated yet.")

                    # User access is restricted.
                    # Keep verifying until access is granted
                    # unless server goes offline or Kodi is shut down.
                    while self.user.HasAccess is False:
                        # Verify access with an API call
                        self.user.hasAccess()

                        if window('plex_online') != "true":
                            # Server went offline
                            break

                        if monitor.waitForAbort(3):
                            # Abort was requested while waiting. We should exit
                            break
            else:
                # Wait until Plex server is online
                # or Kodi is shut down.
                while not self.__stop_PKC():
                    server = self.user.getServer()
                    if server is False:
                        # No server info set in add-on settings
                        pass
                    elif plx.CheckConnection(server, verifySSL=True) is False:
                        # Server is offline or cannot be reached
                        # Alert the user and suppress future warning
                        if self.server_online:
                            self.server_online = False
                            window('plex_online', value="false")
                            # Suspend threads
                            state.SUSPEND_LIBRARY_THREAD = True
                            log.error("Plex Media Server went offline")
                            if settings('show_pms_offline') == 'true':
                                dialog('notification',
                                       lang(33001),
                                       "%s %s" % (lang(29999), lang(33002)),
                                       icon='{plex}',
                                       sound=False)
                        counter += 1
                        # Periodically check if the IP changed, e.g. per minute
                        if counter > 20:
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
                            self.server_online = True
                            # Alert the user that server is online.
                            if (welcome_msg is False and
                                    settings('show_pms_offline') == 'true'):
                                dialog('notification',
                                       lang(29999),
                                       lang(33003),
                                       icon='{plex}',
                                       time=5000,
                                       sound=False)
                        log.info("Server %s is online and ready." % server)
                        window('plex_online', value="true")
                        if state.AUTHENTICATED:
                            # Server got offline when we were authenticated.
                            # Hence resume threads
                            state.SUSPEND_LIBRARY_THREAD = False

                        # Start the userclient thread
                        if not self.user_running:
                            self.user_running = True
                            self.user.start()

                        break

                    if monitor.waitForAbort(3):
                        # Abort was requested while waiting.
                        break

            if monitor.waitForAbort(0.05):
                # Abort was requested while waiting. We should exit
                break
        # Terminating PlexKodiConnect

        # Tell all threads to terminate (e.g. several lib sync threads)
        state.STOP_PKC = True
        try:
            downloadutils.DownloadUtils().stopSession()
        except:
            pass
        window('plex_service_started', clear=True)
        log.info("======== STOP %s ========" % v.ADDON_NAME)


# Safety net - Kody starts PKC twice upon first installation!
if window('plex_service_started') == 'true':
    exit = True
else:
    window('plex_service_started', value='true')
    exit = False

# Delay option
delay = int(settings('startupDelay'))

log.info("Delaying Plex startup by: %s sec..." % delay)
if exit:
    log.error('PKC service.py already started - exiting this instance')
elif delay and Monitor().waitForAbort(delay):
    # Start the service
    log.info("Abort requested while waiting. PKC not started.")
else:
    Service().ServiceEntryPoint()

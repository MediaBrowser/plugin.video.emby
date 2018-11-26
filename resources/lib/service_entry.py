#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import logging
import sys
import xbmc
import xbmcgui

from . import utils, clientinfo, timing
from . import initialsetup, artwork
from . import kodimonitor
from . import sync
from . import websocket_client
from . import plex_companion
from . import plex_functions as PF, playqueue as PQ
from . import playback_starter
from . import playqueue
from . import variables as v
from . import app
from . import loghandler
from . import backgroundthread
from .windows import userselect

###############################################################################
loghandler.config()
LOG = logging.getLogger("PLEX.service")
###############################################################################

WINDOW_PROPERTIES = (
    "plex_dbScan", "pms_token", "plex_token", "pms_server",
    "plex_authenticated", "plex_restricteduser", "plex_allows_mediaDeletion",
    "plex_command", "plex_result")

# "Start from beginning", "Play from beginning"
STRINGS = (utils.try_encode(utils.lang(12021)),
           utils.try_encode(utils.lang(12023)))


class Service():
    ws = None
    sync = None
    plexcompanion = None

    def __init__(self):
        # Initial logging
        LOG.info("======== START %s ========", v.ADDON_NAME)
        LOG.info("Platform: %s", v.PLATFORM)
        LOG.info("KODI Version: %s", v.KODILONGVERSION)
        LOG.info("%s Version: %s", v.ADDON_NAME, v.ADDON_VERSION)
        LOG.info("PKC Direct Paths: %s",
                 utils.settings('useDirectPaths') == '1')
        LOG.info("Number of sync threads: %s",
                 utils.settings('syncThreadNumber'))
        LOG.info('Playlist m3u encoding: %s', v.M3U_ENCODING)
        LOG.info("Full sys.argv received: %s", sys.argv)
        LOG.info('Sync playlists: %s', utils.settings('enablePlaylistSync'))
        LOG.info('Synching only specific Kodi playlists: %s',
                 utils.settings('syncSpecificKodiPlaylists') == 'true')
        LOG.info('Kodi playlist prefix: %s',
                 utils.settings('syncSpecificKodiPlaylistsPrefix'))
        LOG.info('Synching only specific Plex playlists: %s',
                 utils.settings('syncSpecificPlexPlaylistsPrefix') == 'true')
        LOG.info('Play playlist prefix: %s',
                 utils.settings('syncSpecificPlexPlaylistsPrefix'))
        LOG.info('XML decoding being used: %s', utils.ETREE)
        LOG.info("Db version: %s", utils.settings('dbCreatedWithVersion'))

        # Reset window props
        for prop in WINDOW_PROPERTIES:
            utils.window(prop, clear=True)

        # To detect Kodi profile switches
        utils.window('plex_kodiProfile',
                     value=utils.try_decode(xbmc.translatePath("special://profile")))

        # Load/Reset PKC entirely - important for user/Kodi profile switch
        # Clear video nodes properties
        from .library_sync import videonodes
        videonodes.VideoNodes().clearProperties()
        clientinfo.getDeviceId()
        # Init time-offset between Kodi and Plex
        timing.KODI_PLEX_TIME_OFFSET = float(utils.settings('kodiplextimeoffset') or 0.0)

        self.startup_completed = False
        self.server_has_been_online = True
        self.welcome_msg = True
        self.connection_check_counter = 0
        # Flags for other threads
        self.connection_check_running = False
        self.auth_running = False

    def on_connection_check(self, result):
        """
        Call this method after PF.check_connection()
        """
        try:
            if result is False:
                # Server is offline or cannot be reached
                # Alert the user and suppress future warning
                if app.CONN.online:
                    # PMS was online before
                    app.CONN.online = False
                    app.APP.suspend_threads = True
                    LOG.warn("Plex Media Server went offline")
                    if utils.settings('show_pms_offline') == 'true':
                        utils.dialog('notification',
                                     utils.lang(33001),
                                     "%s %s" % (utils.lang(29999),
                                                utils.lang(33002)),
                                     icon='{plex}',
                                     sound=False)
                self.connection_check_counter += 1
                # Periodically check if the IP changed every 15 seconds
                if self.connection_check_counter > 150:
                    self.connection_check_counter = 0
                    server = self.setup.pick_pms()
                    if server:
                        self.setup.write_pms_to_settings(server)
                        app.CONN.load()
            else:
                # Server is online
                self.connection_check_counter = 0
                if not app.CONN.online:
                    # Server was offline before
                    if (self.welcome_msg is False and
                            utils.settings('show_pms_offline') == 'true'):
                        # Alert the user that server is online
                        utils.dialog('notification',
                                     utils.lang(29999),
                                     utils.lang(33003),
                                     icon='{plex}',
                                     time=5000,
                                     sound=False)
                LOG.info("Server is online and ready")
                if app.ACCOUNT.authenticated:
                    # Server got offline when we were authenticated.
                    # Hence resume threads
                    app.APP.suspend_threads = False
                app.CONN.online = True
        finally:
            self.connection_check_running = False

    def log_out(self):
        """
        Ensures that lib sync threads are suspended; signs out user
        """
        LOG.info('Log-out requested')
        app.APP.suspend_threads = True
        i = 0
        while app.SYNC.db_scan:
            i += 1
            app.APP.monitor.waitForAbort(0.05)
            if i > 100:
                LOG.error('Could not stop library sync, aborting log-out')
                # Failed to reset PMS and plex.tv connects. Try to restart Kodi
                utils.messageDialog(utils.lang(29999), utils.lang(39208))
                # Resuming threads, just in case
                app.APP.suspend_threads = False
                return False
        LOG.info('Successfully stopped library sync')
        app.ACCOUNT.log_out()
        LOG.info('User has been logged out')
        return True

    def choose_pms_server(self, manual=False):
        LOG.info("Choosing PMS server requested, starting")
        if manual:
            if not self.setup.enter_new_pms_address():
                return False
        else:
            server = self.setup.pick_pms(showDialog=True)
            if server is None:
                LOG.info('We did not connect to a new PMS, aborting')
                return False
            LOG.info("User chose server %s", server['name'])
            if server['baseURL'] == app.CONN.server:
                LOG.info('User chose old PMS to connect to')
                return False
            self.setup.write_pms_to_settings(server)
        if not self.log_out():
            return False
        # Wipe Kodi and Plex database as well as playlists and video nodes
        utils.wipe_database()
        app.CONN.load()
        app.ACCOUNT.set_unauthenticated()
        self.server_has_been_online = False
        self.welcome_msg = False
        LOG.info("Choosing new PMS complete")
        return True

    def switch_plex_user(self):
        if not self.log_out():
            return False
        # First remove playlists of old user
        utils.delete_playlists()
        # Remove video nodes
        utils.delete_nodes()
        app.ACCOUNT.set_unauthenticated()
        # Force full sync after login
        app.SYNC.run_lib_scan = 'full'
        return True

    def toggle_plex_tv(self):
        if app.ACCOUNT.plex_token:
            LOG.info('Resetting plex.tv credentials in settings')
            self.log_out()
            app.ACCOUNT.clear()
        else:
            LOG.info('Login to plex.tv')
            if self.setup.plex_tv_sign_in():
                self.setup.write_credentials_to_settings()
                app.ACCOUNT.load()

    def authenticate(self):
        """
        Authenticate the current user or prompt to log-in

        Returns True if successful, False if not. 'aborted' if user chose to
        abort
        """
        if self._do_auth():
            if self.welcome_msg is True:
                # Reset authentication warnings
                self.welcome_msg = False
                utils.dialog('notification',
                             utils.lang(29999),
                             "%s %s" % (utils.lang(33000),
                                        app.ACCOUNT.plex_username),
                             icon='{plex}',
                             time=2000,
                             sound=False)
            app.APP.suspend_threads = False
        self.auth_running = False

    def enter_new_pms_address(self):
        if self.setup.enter_new_pms_address():
            app.CONN.load()
            app.ACCOUNT.set_unauthenticated()
            self.server_has_been_online = False
            self.welcome_msg = False

    def _do_auth(self):
        LOG.info('Authenticating user')
        if app.ACCOUNT.plex_username and not app.ACCOUNT.force_login:            # Found a user in the settings, try to authenticate
            LOG.info('Trying to authenticate with old settings')
            res = PF.check_connection(app.CONN.server,
                                      token=app.ACCOUNT.pms_token,
                                      verifySSL=app.CONN.verify_ssl_cert)
            if res is False:
                LOG.error('Something went wrong while checking connection')
                return False
            elif res == 401:
                LOG.error('User %s no longer has access - signing user out',
                          app.ACCOUNT.plex_username)
                self.log_out()
                return False
            elif res >= 400:
                LOG.error('Answer from PMS is not as expected')
                return False
            LOG.info('Successfully authenticated using old settings')
            app.ACCOUNT.set_authenticated()
            return True

        while True:
            # Could not use settings - try to get Plex user list from plex.tv
            if app.ACCOUNT.plex_token:
                LOG.info("Trying to connect to plex.tv to get a user list")
                user, _ = userselect.start()
                if not user:
                    LOG.info('No user received')
                    app.APP.suspend = True
                    return False
                username = user.title
                user_id = user.id
                token = user.authToken
            else:
                LOG.info("Trying to authenticate without a token")
                username = ''
                user_id = ''
                token = ''
            res = PF.check_connection(app.CONN.server,
                                      token=token,
                                      verifySSL=app.CONN.verify_ssl_cert)
            if res is False:
                LOG.error('Something went wrong while checking connection')
                return False
            elif res == 401:
                if app.ACCOUNT.plex_token:
                    LOG.error('User %s does not have access to PMS %s on %s',
                              username, app.CONN.server_name, app.CONN.server)
                    # "User is unauthorized for server {0}"
                    utils.messageDialog(utils.lang(29999),
                                        utils.lang(33010).format(app.CONN.server_name))
                    self.log_out()
                    return False
                else:
                    # "Failed to authenticate. Did you login to plex.tv?"
                    utils.messageDialog(utils.lang(29999), utils.lang(39023))
                    if self.setup.plex_tv_sign_in():
                        self.setup.write_credentials_to_settings()
                        app.ACCOUNT.load()
                        continue
                    else:
                        app.APP.suspend = True
                        return False
            elif res >= 400:
                LOG.error('Answer from PMS is not as expected')
                return False
            LOG.info('Successfully authenticated')
            # Got new values that need to be saved
            utils.settings('username', value=username)
            utils.settings('userid', value=user_id)
            utils.settings('accessToken', value=token)
            app.ACCOUNT.load()
            app.ACCOUNT.set_authenticated()
            return True

    def ServiceEntryPoint(self):
        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        # Some plumbing
        app.init()
        app.APP.monitor = kodimonitor.KodiMonitor()
        app.APP.player = xbmc.Player()
        artwork.IMAGE_CACHING_SUSPENDS = [
            app.APP.suspend_threads,
            app.SYNC.stop_sync,
            app.SYNC.db_scan
        ]
        if not utils.settings('imageSyncDuringPlayback') == 'true':
            artwork.IMAGE_CACHING_SUSPENDS.append(app.SYNC.suspend_sync)
        # Initialize the PKC playqueues
        PQ.init_playqueues()

        # Server auto-detect
        self.setup = initialsetup.InitialSetup()
        self.setup.setup()

        # Initialize important threads
        self.ws = websocket_client.PMS_Websocket()
        self.alexa = websocket_client.Alexa_Websocket()
        self.sync = sync.Sync()
        self.plexcompanion = plex_companion.PlexCompanion()
        self.playback_starter = playback_starter.PlaybackStarter()
        self.playqueue = playqueue.PlayqueueMonitor()

        # Main PKC program loop
        while not xbmc.abortRequested:
            # Check for Kodi profile change
            if utils.window('plex_kodiProfile') != v.KODI_PROFILE:
                # Profile change happened, terminate this thread and others
                LOG.info("Kodi profile was: %s and changed to: %s. "
                         "Terminating old PlexKodiConnect thread.",
                         v.KODI_PROFILE, utils.window('plex_kodiProfile'))
                break

            # Check for PKC commands from other Python instances
            plex_command = utils.window('plex_command')
            if plex_command:
                # Commands/user interaction received from other PKC Python
                # instances (default.py and context.py instead of service.py)
                utils.window('plex_command', clear=True)
                if plex_command.startswith('PLAY-'):
                    # Add-on path playback!
                    app.APP.command_pipeline_queue.put(
                        plex_command.replace('PLAY-', ''))
                elif plex_command.startswith('NAVIGATE-'):
                    app.APP.command_pipeline_queue.put(
                        plex_command.replace('NAVIGATE-', ''))
                elif plex_command.startswith('CONTEXT_menu?'):
                    app.APP.command_pipeline_queue.put(
                        'dummy?mode=context_menu&%s'
                        % plex_command.replace('CONTEXT_menu?', ''))
                elif plex_command == 'choose_pms_server':
                    task = backgroundthread.FunctionAsTask(
                        self.choose_pms_server, None)
                    backgroundthread.BGThreader.addTasksToFront([task])
                elif plex_command == 'switch_plex_user':
                    task = backgroundthread.FunctionAsTask(
                        self.switch_plex_user, None)
                    backgroundthread.BGThreader.addTasksToFront([task])
                elif plex_command == 'enter_new_pms_address':
                    task = backgroundthread.FunctionAsTask(
                        self.enter_new_pms_address, None)
                    backgroundthread.BGThreader.addTasksToFront([task])
                elif plex_command == 'toggle_plex_tv_sign_in':
                    task = backgroundthread.FunctionAsTask(
                        self.toggle_plex_tv, None)
                    backgroundthread.BGThreader.addTasksToFront([task])
                elif plex_command == 'repair-scan':
                    app.SYNC.run_lib_scan = 'repair'
                elif plex_command == 'full-scan':
                    app.SYNC.run_lib_scan = 'full'
                elif plex_command == 'fanart-scan':
                    app.SYNC.run_lib_scan = 'fanart'
                elif plex_command == 'textures-scan':
                    app.SYNC.run_lib_scan = 'textures'
                elif plex_command == 'RESET-PKC':
                    utils.reset()
                continue

            if app.APP.suspend:
                app.APP.monitor.waitForAbort(0.1)
                continue

            # Detect the resume dialog for widgets. Could also be used to detect
            # external players (see Emby implementation)
            if xbmc.getCondVisibility('Window.IsVisible(DialogContextMenu.xml)'):
                if xbmc.getInfoLabel('Control.GetLabel(1002)') in STRINGS:
                    # Remember that the item IS indeed resumable
                    control = int(xbmcgui.Window(10106).getFocusId())
                    app.PLAYSTATE.resume_playback = True if control == 1001 else False
                else:
                    # Different context menu is displayed
                    app.PLAYSTATE.resume_playback = False

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server
            if not app.CONN.online:
                # Not online
                server = app.CONN.server
                if not server:
                    # No server info set in add-on settings
                    pass
                elif not self.connection_check_running:
                    self.connection_check_running = True
                    task = backgroundthread.FunctionAsTask(
                        PF.check_connection,
                        self.on_connection_check,
                        server,
                        verifySSL=True)
                    backgroundthread.BGThreader.addTasksToFront([task])
                    continue
            elif not app.ACCOUNT.authenticated:
                # Plex server is online, but we're not yet authenticated
                if not self.auth_running:
                    self.auth_running = True
                    task = backgroundthread.FunctionAsTask(
                        self.authenticate, None)
                    backgroundthread.BGThreader.addTasksToFront([task])
                    continue
            elif not self.startup_completed:
                self.startup_completed = True
                self.ws.start()
                self.sync.start()
                self.plexcompanion.start()
                self.playback_starter.start()
                self.playqueue.start()
                if utils.settings('enable_alexa') == 'true':
                    self.alexa.start()

            app.APP.monitor.waitForAbort(0.1)

        # EXITING PKC
        # Tell all threads to terminate (e.g. several lib sync threads)
        app.APP.stop_pkc = True
        utils.window('plex_service_started', clear=True)
        LOG.info("======== STOP %s ========", v.ADDON_NAME)


def start():
    # Safety net - Kody starts PKC twice upon first installation!
    if utils.window('plex_service_started') == 'true':
        EXIT = True
    else:
        utils.window('plex_service_started', value='true')
        EXIT = False

    # Delay option
    DELAY = int(utils.settings('startupDelay'))

    LOG.info("Delaying Plex startup by: %s sec...", DELAY)
    if EXIT:
        LOG.error('PKC service.py already started - exiting this instance')
    elif DELAY and xbmc.Monitor().waitForAbort(DELAY):
        # Start the service
        LOG.info("Abort requested while waiting. PKC not started.")
    else:
        Service().ServiceEntryPoint()

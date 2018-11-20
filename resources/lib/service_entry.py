#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import logging
import sys
import xbmc

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
from .windows import userselect

###############################################################################
loghandler.config()
LOG = logging.getLogger("PLEX.service")
###############################################################################

WINDOW_PROPERTIES = (
    "plex_online", "plex_command_processed", "plex_shouldStop", "plex_dbScan",
    "plex_customplayqueue", "plex_playbackProps",
    "pms_token", "plex_token", "pms_server", "plex_machineIdentifier",
    "plex_servername", "plex_authenticated", "PlexUserImage", "useDirectPaths",
    "countError", "countUnauthorized", "plex_restricteduser",
    "plex_allows_mediaDeletion", "plex_command", "plex_result",
    "plex_force_transcode_pix"
)


class Service():
    ws = None
    sync = None
    plexcompanion = None

    ws_running = False
    alexa_running = False
    sync_running = False
    plexcompanion_running = False
    kodimonitor_running = False
    playback_starter_running = False

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
        timing.KODI_PLEX_TIME_OFFSET = float(utils.settings('kodiplextimeoffset')) or 0.0

    def isCanceled(self):
        return xbmc.abortRequested or app.APP.stop_pkc

    def log_out(self):
        """
        Ensures that lib sync threads are suspended; signs out user
        """
        LOG.info('Log-out requested')
        app.SYNC.suspend_library_thread = True
        i = 0
        while app.SYNC.db_scan:
            i += 1
            app.APP.monitor.waitForAbort(0.05)
            if i > 100:
                LOG.error('Could not stop library sync, aborting log-out')
                # Failed to reset PMS and plex.tv connects. Try to restart Kodi
                utils.messageDialog(utils.lang(29999), utils.lang(39208))
                # Resuming threads, just in case
                app.SYNC.suspend_library_thread = False
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
        LOG.info("Choosing new PMS complete")
        return True

    def switch_plex_user(self):
        if not self.log_out():
            return False
        # First remove playlists of old user
        utils.delete_playlists()
        # Remove video nodes
        utils.delete_nodes()
        return True

    def toggle_plex_tv(self):
        if utils.settings('plexToken'):
            LOG.info('Reseting plex.tv credentials in settings')
            app.ACCOUNT.clear()
            return True
        else:
            LOG.info('Login to plex.tv')
            return self.setup.plex_tv_sign_in()

    def authenticate(self):
        """
        Authenticate the current user or prompt to log-in

        Returns True if successful, False if not. 'aborted' if user chose to
        abort
        """
        LOG.info('Authenticating user')
        if app.ACCOUNT.plex_username and not app.ACCOUNT.force_login:
            # Found a user in the settings, try to authenticate
            LOG.info('Trying to authenticate with old settings')
            res = PF.check_connection(app.CONN.server,
                                      token=app.ACCOUNT.pms_token,
                                      verifySSL=app.CONN.verify_ssl_cert)
            if res is False:
                LOG.error('Something went wrong while checking connection')
                return False
            elif res == 401:
                LOG.error('User token no longer valid. Sign user out')
                app.ACCOUNT.clear()
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
                    app.CONN.pms_status = 'Stop'
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
                    LOG.error('Token no longer valid')
                    # "Your Plex token is no longer valid. Logging-out of plex.tv"
                    utils.messageDialog(utils.lang(29999), utils.lang(33010))
                    app.ACCOUNT.clear()
                    return False
                else:
                    # "Failed to authenticate. Did you login to plex.tv?"
                    utils.messageDialog(utils.lang(29999), utils.lang(39023))
                    if self.setup.plex_tv_sign_in():
                        self.setup.write_credentials_to_settings()
                        app.ACCOUNT.load()
                        continue
                    else:
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
        app.init()
        # Some plumbing
        app.APP.monitor = kodimonitor.KodiMonitor()
        artwork.IMAGE_CACHING_SUSPENDS = [
            app.SYNC.suspend_library_thread,
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
        self.specialmonitor = kodimonitor.SpecialMonitor()
        self.playback_starter = playback_starter.PlaybackStarter()
        self.playqueue = playqueue.PlayqueueMonitor()

        server_online = True
        welcome_msg = True
        counter = 0
        while not self.isCanceled():

            if utils.window('plex_kodiProfile') != v.KODI_PROFILE:
                # Profile change happened, terminate this thread and others
                LOG.info("Kodi profile was: %s and changed to: %s. "
                         "Terminating old PlexKodiConnect thread.",
                         v.KODI_PROFILE, utils.window('plex_kodiProfile'))
                break

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
                    if self.choose_pms_server():
                        utils.window('plex_online', clear=True)
                        app.ACCOUNT.set_unauthenticated()
                        server_online = False
                        welcome_msg = False
                elif plex_command == 'switch_plex_user':
                    if self.switch_plex_user():
                        app.ACCOUNT.set_unauthenticated()
                elif plex_command == 'enter_new_pms_address':
                    if self.setup.enter_new_pms_address():
                        if self.log_out():
                            utils.window('plex_online', clear=True)
                            app.ACCOUNT.set_unauthenticated()
                            server_online = False
                            welcome_msg = False
                elif plex_command == 'toggle_plex_tv_sign_in':
                    if self.toggle_plex_tv():
                        app.ACCOUNT.set_unauthenticated()
                elif plex_command == 'repair-scan':
                    app.SYNC.run_lib_scan = 'repair'
                elif plex_command == 'full-scan':
                    app.SYNC.run_lib_scan = 'full'
                elif plex_command == 'fanart-scan':
                    app.SYNC.run_lib_scan = 'fanart'
                elif plex_command == 'textures-scan':
                    app.SYNC.run_lib_scan = 'textures'
                continue

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server
            if utils.window('plex_online') == "true":
                # Plex server is online
                if app.CONN.pms_status == 'Stop':
                    app.APP.monitor.waitForAbort(0.05)
                    continue
                elif app.CONN.pms_status == '401':
                    # Unauthorized access, revoke token
                    LOG.info('401 received - revoking token')
                    app.ACCOUNT.clear()
                    app.CONN.pms_status = 'Auth'
                    utils.window('plex_serverStatus', value='Auth')
                    continue
                if not app.ACCOUNT.authenticated:
                    LOG.info('Not yet authenticated')
                    # Do authentication
                    if not self.authenticate():
                        continue
                    # Start up events
                    if welcome_msg is True:
                        # Reset authentication warnings
                        welcome_msg = False
                        utils.dialog('notification',
                                     utils.lang(29999),
                                     "%s %s" % (utils.lang(33000),
                                                app.ACCOUNT.plex_username),
                                     icon='{plex}',
                                     time=2000,
                                     sound=False)
                    # Start monitoring kodi events
                    if not self.kodimonitor_running:
                        self.kodimonitor_running = True
                        self.specialmonitor.start()
                    # Start the Websocket Client
                    if not self.ws_running:
                        self.ws_running = True
                        self.ws.start()
                    # Start the Alexa thread
                    if (not self.alexa_running and
                            utils.settings('enable_alexa') == 'true'):
                        self.alexa_running = True
                        self.alexa.start()
                    # Start the syncing thread
                    if not self.sync_running:
                        self.sync_running = True
                        self.sync.start()
                    # Start the Plex Companion thread
                    if not self.plexcompanion_running:
                        self.plexcompanion_running = True
                        self.plexcompanion.start()
                    if not self.playback_starter_running:
                        self.playback_starter_running = True
                        self.playback_starter.start()
                        self.playqueue.start()
            else:
                # Wait until Plex server is online
                # or Kodi is shut down.
                server = app.CONN.server
                if not server:
                    # No server info set in add-on settings
                    pass
                elif PF.check_connection(server, verifySSL=True) is False:
                    # Server is offline or cannot be reached
                    # Alert the user and suppress future warning
                    if server_online:
                        server_online = False
                        utils.window('plex_online', value="false")
                        # Suspend threads
                        app.SYNC.suspend_library_thread = True
                        LOG.warn("Plex Media Server went offline")
                        if utils.settings('show_pms_offline') == 'true':
                            utils.dialog('notification',
                                         utils.lang(33001),
                                         "%s %s" % (utils.lang(29999),
                                                    utils.lang(33002)),
                                         icon='{plex}',
                                         sound=False)
                    counter += 1
                    # Periodically check if the IP changed, e.g. per minute
                    if counter > 20:
                        counter = 0
                        setup = initialsetup.InitialSetup()
                        tmp = setup.pick_pms()
                        if tmp:
                            setup.write_pms_to_settings(tmp)
                            app.CONN.load()
                else:
                    # Server is online
                    counter = 0
                    if not server_online:
                        # Server was offline when Kodi started.
                        server_online = True
                        # Alert the user that server is online.
                        if (welcome_msg is False and
                                utils.settings('show_pms_offline') == 'true'):
                            utils.dialog('notification',
                                         utils.lang(29999),
                                         utils.lang(33003),
                                         icon='{plex}',
                                         time=5000,
                                         sound=False)
                    LOG.info("Server %s is online and ready.", server)
                    utils.window('plex_online', value="true")
                    if app.ACCOUNT.authenticated:
                        # Server got offline when we were authenticated.
                        # Hence resume threads
                        app.SYNC.suspend_library_thread = False

            if app.APP.monitor.waitForAbort(0.05):
                # Abort was requested while waiting. We should exit
                break
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

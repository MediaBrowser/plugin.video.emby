#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmc

from .downloadutils import DownloadUtils as DU
from . import library_sync, timing
from . import backgroundthread, utils, artwork, variables as v, app
from . import kodi_db

LOG = getLogger('PLEX.sync')


def set_library_scan_toggle(boolean=True):
    """
    Make sure to hit this function before starting large scans
    """
    if not boolean:
        # Deactivate
        app.SYNC.db_scan = False
        utils.window('plex_dbScan', clear=True)
    else:
        app.SYNC.db_scan = True
        utils.window('plex_dbScan', value="true")


class Sync(backgroundthread.KillableThread):
    """
    The one and only library sync thread. Spawn only 1!
    """
    def __init__(self):
        self.sync_successful = False
        self.last_full_sync = 0
        self.fanart = None
        # Show sync dialog even if user deactivated?
        self.force_dialog = False
        self.image_cache_thread = None
        # Lock used to wait on a full sync, e.g. on initial sync
        # self.lock = backgroundthread.threading.Lock()
        super(Sync, self).__init__()

    def isSuspended(self):
        return self._suspended or app.APP.suspend_threads

    def show_kodi_note(self, message, icon="plex", force=False):
        """
        Shows a Kodi popup, if user selected to do so. Pass message in unicode
        or string

        icon:   "plex": shows Plex icon
                "error": shows Kodi error icon
        """
        if app.APP.player.isPlaying():
            LOG.info('Playing media - not showing note: %s', message)
            return
        if not force and app.SYNC.sync_dialog is not True and self.force_dialog is not True:
            return
        if icon == "plex":
            utils.dialog('notification',
                         heading='{plex}',
                         message=message,
                         icon='{plex}',
                         sound=False)
        elif icon == "error":
            utils.dialog('notification',
                         heading='{plex}',
                         message=message,
                         icon='{error}')

    def triage_lib_scans(self):
        """
        Decides what to do if app.SYNC.run_lib_scan has been set. E.g. manually
        triggered full or repair syncs
        """
        if app.SYNC.run_lib_scan in ("full", "repair"):
            set_library_scan_toggle()
            LOG.info('Full library scan requested, starting')
            self.start_library_sync(show_dialog=True,
                                    repair=app.SYNC.run_lib_scan == 'repair',
                                    block=True)
            if not self.sync_successful and not self.isSuspended() and not self.isCanceled():
                # ERROR in library sync
                self.show_kodi_note(utils.lang(39410), icon='error')
        elif app.SYNC.run_lib_scan == 'fanart':
            # Only look for missing fanart (No) or refresh all fanart (Yes)
            from .windows import optionsdialog
            refresh = optionsdialog.show(utils.lang(29999),
                                         utils.lang(39223),
                                         utils.lang(39224),  # refresh all
                                         utils.lang(39225)) == 0
            if not self.start_fanart_download(refresh=refresh):
                # Fanart download already running
                utils.dialog('notification',
                             heading='{plex}',
                             message=utils.lang(30015),
                             icon='{plex}',
                             sound=False)
        elif app.SYNC.run_lib_scan == 'textures':
            LOG.info("Caching of images requested")
            if not utils.yesno_dialog("Image Texture Cache", utils.lang(39250)):
                return
            # ask to reset all existing or not
            if utils.yesno_dialog('Image Texture Cache', utils.lang(39251)):
                kodi_db.reset_cached_images()
            self.start_image_cache_thread()

    def on_library_scan_finished(self, successful):
        """
        Hit this after the full sync has finished
        """
        self.sync_successful = successful
        self.last_full_sync = timing.unix_timestamp()
        set_library_scan_toggle(boolean=False)
        if not successful:
            LOG.error('Could not finish scheduled full sync')
            self.force_dialog = True
            self.show_kodi_note(utils.lang(39410), icon='error')
            self.force_dialog = False
        # try:
        #     self.lock.release()
        # except backgroundthread.threading.ThreadError:
        #     pass

    def start_library_sync(self, show_dialog=None, repair=False, block=False):
        set_library_scan_toggle(boolean=True)
        show_dialog = show_dialog if show_dialog is not None else app.SYNC.sync_dialog
        library_sync.start(show_dialog, repair, self.on_library_scan_finished)
        # if block:
        # self.lock.acquire()
        # Will block until scan is finished
        # self.lock.acquire()
        # self.lock.release()

    def start_fanart_download(self, refresh):
        if not utils.settings('FanartTV') == 'true':
            LOG.info('Additional fanart download is deactivated')
            return False
        if not app.SYNC.artwork:
            LOG.info('Not synching Plex PMS artwork, not getting artwork')
            return False
        elif self.fanart is None or not self.fanart.is_alive():
            LOG.info('Start downloading additional fanart with refresh %s',
                     refresh)
            self.fanart = library_sync.FanartThread(self.on_fanart_download_finished, refresh)
            self.fanart.start()
            return True
        else:
            LOG.info('Still downloading fanart')
            return False

    def on_fanart_download_finished(self, successful):
        # FanartTV lookup completed
        if successful:
            # Toggled to "Yes"
            utils.settings('plex_status_fanarttv_lookup', value=utils.lang(107))

    def start_image_cache_thread(self):
        if not utils.settings('enableTextureCache') == "true":
            LOG.info('Image caching has been deactivated')
            return
        if not app.SYNC.artwork:
            LOG.info('Not synching Plex artwork - not caching')
            return
        if self.image_cache_thread and self.image_cache_thread.is_alive():
            self.image_cache_thread.cancel()
            self.image_cache_thread.join()
        self.image_cache_thread = artwork.ImageCachingThread()
        self.image_cache_thread.start()

    def run(self):
        try:
            self._run_internal()
        except:
            app.SYNC.db_scan = False
            utils.window('plex_dbScan', clear=True)
            utils.ERROR(txt='sync.py crashed', notify=True)
            raise

    def _run_internal(self):
        LOG.info("---===### Starting Sync Thread ###===---")
        install_sync_done = utils.settings('SyncInstallRunDone') == 'true'
        playlist_monitor = None
        initial_sync_done = False
        last_websocket_processing = 0
        last_time_sync = 0
        one_day_in_seconds = 60 * 60 * 24
        # Link to Websocket queue
        queue = app.APP.websocket_queue

        # Check whether we need to reset the Kodi DB
        if install_sync_done:
            current_version = utils.settings('dbCreatedWithVersion')
            if not utils.compare_version(current_version,
                                         v.MIN_DB_VERSION):
                LOG.warn("Db version out of date: %s minimum version "
                         "required: %s", current_version, v.MIN_DB_VERSION)
                # DB out of date. Proceed to recreate?
                if not utils.yesno_dialog(utils.lang(29999),
                                          utils.lang(39401)):
                    LOG.warn("Db version out of date! USER IGNORED!")
                    # PKC may not work correctly until reset
                    utils.messageDialog(utils.lang(29999),
                                        '%s%s' % (utils.lang(29999),
                                                  utils.lang(39402)))
                else:
                    utils.reset(ask_user=False)
                return

        utils.init_dbs()

        while not self.isCanceled():
            # In the event the server goes offline
            while self.isSuspended():
                if self.isCanceled():
                    # Abort was requested while waiting. We should exit
                    LOG.info("###===--- Sync Thread Stopped ---===###")
                    return
                app.APP.monitor.waitForAbort(1)

            if not install_sync_done:
                # Very FIRST sync ever upon installation or reset of Kodi DB
                set_library_scan_toggle()
                self.force_dialog = True
                # Initialize time offset Kodi - PMS
                library_sync.sync_pms_time()
                last_time_sync = timing.unix_timestamp()
                LOG.info('Initial start-up full sync starting')
                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                # This call will block until scan is completed
                self.start_library_sync(show_dialog=True, block=True)
                if self.sync_successful:
                    LOG.info('Initial start-up full sync successful')
                    utils.settings('SyncInstallRunDone', value='true')
                    install_sync_done = True
                    initial_sync_done = True
                    utils.settings('dbCreatedWithVersion', v.ADDON_VERSION)
                    if library_sync.PLAYLIST_SYNC_ENABLED:
                        from . import playlists
                        playlist_monitor = playlists.kodi_playlist_monitor()
                    self.start_fanart_download(refresh=False)
                    self.start_image_cache_thread()
                else:
                    LOG.error('Initial start-up full sync unsuccessful')
                    app.APP.monitor.waitForAbort(1)
                self.force_dialog = False
                xbmc.executebuiltin('InhibitIdleShutdown(false)')

            elif not initial_sync_done:
                # First sync upon PKC restart. Skipped if very first sync upon
                # PKC installation has been completed
                LOG.info('Doing initial sync on Kodi startup')
                self.start_library_sync(block=True)
                if self.sync_successful:
                    initial_sync_done = True
                    LOG.info('Done initial sync on Kodi startup')
                    if library_sync.PLAYLIST_SYNC_ENABLED:
                        from . import playlists
                        playlist_monitor = playlists.kodi_playlist_monitor()
                    self.start_fanart_download(refresh=False)
                    self.start_image_cache_thread()
                else:
                    LOG.info('Startup sync has not yet been successful')
                    app.APP.monitor.waitForAbort(1)

            # Currently no db scan, so we could start a new scan
            elif app.SYNC.db_scan is False:
                # Full scan was requested from somewhere else
                if app.SYNC.run_lib_scan is not None:
                    # Force-show dialogs since they are user-initiated
                    self.force_dialog = True
                    self.triage_lib_scans()
                    self.force_dialog = False
                    # Reset the flag
                    app.SYNC.run_lib_scan = None
                    continue

                # Standard syncs - don't force-show dialogs
                now = timing.unix_timestamp()
                if (now - self.last_full_sync > app.SYNC.full_sync_intervall and
                        not app.SYNC.suspend_sync):
                    LOG.info('Doing scheduled full library scan')
                    self.start_library_sync()
                elif now - last_time_sync > one_day_in_seconds:
                    LOG.info('Starting daily time sync')
                    library_sync.sync_pms_time()
                    last_time_sync = now
                elif not app.SYNC.background_sync_disabled:
                    # Check back whether we should process something Only do
                    # this once a while (otherwise, potentially many screen
                    # refreshes lead to flickering)
                    if (library_sync.WEBSOCKET_MESSAGES and
                            now - last_websocket_processing > 5):
                        last_websocket_processing = now
                        library_sync.process_websocket_messages()
                    # See if there is a PMS message we need to handle
                    try:
                        message = queue.get(block=False)
                    except backgroundthread.Queue.Empty:
                        pass
                    # Got a message from PMS; process it
                    else:
                        library_sync.store_websocket_message(message)
                        queue.task_done()
                        # Sleep just a bit
                        app.APP.monitor.waitForAbort(0.01)
                        continue
            app.APP.monitor.waitForAbort(0.1)
        # Shut down playlist monitoring
        if playlist_monitor:
            playlist_monitor.stop()
        # doUtils could still have a session open due to interrupted sync
        try:
            DU().stopSession()
        except AttributeError:
            pass
        LOG.info("###===--- Sync Thread Stopped ---===###")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from random import shuffle
import Queue
import xbmc

from . import library_sync

from .plex_api import API
from .downloadutils import DownloadUtils as DU
from . import backgroundthread, utils, path_ops
from . import itemtypes, plex_db, kodidb_functions as kodidb
from . import artwork, plex_functions as PF
from . import variables as v, state

LOG = getLogger('PLEX.sync')


def set_library_scan_toggle(boolean=True):
    """
    Make sure to hit this function before starting large scans
    """
    if not boolean:
        # Deactivate
        state.DB_SCAN = False
        utils.window('plex_dbScan', clear=True)
    else:
        state.DB_SCAN = True
        utils.window('plex_dbScan', value="true")


class Sync(backgroundthread.KillableThread):
    """
    The one and only library sync thread. Spawn only 1!
    """
    def __init__(self):
        self.items_to_process = []
        self.session_keys = {}
        self.sync_successful = False
        self.last_full_sync = 0
        if utils.settings('FanartTV') == 'true':
            self.fanartqueue = Queue.Queue()
            self.fanartthread = library_sync.fanart.ThreadedProcessFanart(self.fanartqueue)
        else:
            self.fanartqueue = None
            self.fanartthread = None
        # How long should we wait at least to process new/changed PMS items?
        # Show sync dialog even if user deactivated?
        self.force_dialog = False
        # Need to be set accordingly later
        self.update_kodi_video_library = False
        self.update_kodi_music_library = False
        # Lock used to wait on a full sync, e.g. on initial sync
        self.lock = backgroundthread.threading.Lock()
        super(Sync, self).__init__()

    def isCanceled(self):
        return xbmc.abortRequested or state.STOP_PKC

    def isSuspended(self):
        return state.SUSPEND_LIBRARY_THREAD or state.STOP_SYNC

    def suspend_item_sync(self):
        """
        Returns True if we should not sync new items or artwork to Kodi or even
        abort a sync currently running.

        Returns False otherwise.
        """
        if self.isSuspended() or self.isCanceled():
            return True
        elif state.SUSPEND_SYNC:
            return True
        return False

    def show_kodi_note(self, message, icon="plex"):
        """
        Shows a Kodi popup, if user selected to do so. Pass message in unicode
        or string

        icon:   "plex": shows Plex icon
                "error": shows Kodi error icon
        """
        if state.SYNC_DIALOG is not True and self.force_dialog is not True:
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

    def process_message(self, message):
        """
        processes json.loads() messages from websocket. Triage what we need to
        do with "process_" methods
        """
        if message['type'] == 'playing':
            self.process_playing(message['PlaySessionStateNotification'])
        elif message['type'] == 'timeline':
            self.process_timeline(message['TimelineEntry'])
        elif message['type'] == 'activity':
            self.process_activity(message['ActivityNotification'])

    def multi_delete(self, liste, delete_list):
        """
        Deletes the list items of liste at the positions in delete_list
        (which can be in any arbitrary order)
        """
        indexes = sorted(delete_list, reverse=True)
        for index in indexes:
            del liste[index]
        return liste

    def process_items(self):
        """
        Periodically called to process new/updated PMS items

        PMS needs a while to download info from internet AFTER it
        showed up under 'timeline' websocket messages

        data['type']:
            1:      movie
            2:      tv show??
            3:      season??
            4:      episode
            8:      artist (band)
            9:      album
            10:     track (song)
            12:     trailer, extras?

        data['state']:
            0: 'created',
            2: 'matching',
            3: 'downloading',
            4: 'loading',
            5: 'finished',
            6: 'analyzing',
            9: 'deleted'
        """
        now = utils.unix_timestamp()
        delete_list = []
        for i, item in enumerate(self.items_to_process):
            if self.isCanceled() or self.suspended():
                # Chances are that Kodi gets shut down
                break
            if item['state'] == 9:
                successful = self.process_deleteditems(item)
            elif now - item['timestamp'] < state.BACKGROUNDSYNC_SAFTYMARGIN:
                # We haven't waited long enough for the PMS to finish
                # processing the item. Do it later (excepting deletions)
                continue
            else:
                successful = self.process_newitems(item)
                if successful and utils.settings('FanartTV') == 'true':
                    if item['type'] in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW):
                        self.fanartqueue.put({
                            'plex_id': item['ratingKey'],
                            'plex_type': item['type'],
                            'refresh': False
                        })
            if successful is True:
                delete_list.append(i)
            else:
                # Safety net if we can't process an item
                item['attempt'] += 1
                if item['attempt'] > 3:
                    LOG.error('Repeatedly could not process item %s, abort',
                              item)
                    delete_list.append(i)

        # Get rid of the items we just processed
        if delete_list:
            self.items_to_process = self.multi_delete(self.items_to_process,
                                                      delete_list)
        # Let Kodi know of the change
        if self.update_kodi_video_library or self.update_kodi_music_library:
            library_sync.update_library(video=self.update_kodi_video_library,
                                        music=self.update_kodi_music_library)
            self.update_kodi_video_library = False
            self.update_kodi_music_library = False

    def process_newitems(self, item):
        xml = PF.GetPlexMetadata(item['ratingKey'])
        try:
            mediatype = xml[0].attrib['type']
        except (IndexError, KeyError, TypeError):
            LOG.error('Could not download metadata for %s', item['ratingKey'])
            return False
        LOG.debug("Processing new/updated PMS item: %s", item['ratingKey'])
        viewtag = xml.attrib.get('librarySectionTitle')
        viewid = xml.attrib.get('librarySectionID')
        if mediatype == v.PLEX_TYPE_MOVIE:
            self.update_kodi_video_library = True
            with itemtypes.Movies() as movie:
                movie.add_update(xml[0],
                                 viewtag=viewtag,
                                 viewid=viewid)
        elif mediatype == v.PLEX_TYPE_EPISODE:
            self.update_kodi_video_library = True
            with itemtypes.TVShows() as show:
                show.add_updateEpisode(xml[0],
                                       viewtag=viewtag,
                                       viewid=viewid)
        elif mediatype == v.PLEX_TYPE_SONG:
            self.update_kodi_music_library = True
            with itemtypes.Music() as music_db:
                music_db.add_updateSong(xml[0], viewtag=viewtag, viewid=viewid)
        return True

    def process_deleteditems(self, item):
        if item['type'] == v.PLEX_TYPE_MOVIE:
            LOG.debug("Removing movie %s", item['ratingKey'])
            self.update_kodi_video_library = True
            with itemtypes.Movies() as movie:
                movie.remove(item['ratingKey'])
        elif item['type'] in (v.PLEX_TYPE_SHOW,
                              v.PLEX_TYPE_SEASON,
                              v.PLEX_TYPE_EPISODE):
            LOG.debug("Removing episode/season/show with plex id %s",
                      item['ratingKey'])
            self.update_kodi_video_library = True
            with itemtypes.TVShows() as show:
                show.remove(item['ratingKey'])
        elif item['type'] in (v.PLEX_TYPE_ARTIST,
                              v.PLEX_TYPE_ALBUM,
                              v.PLEX_TYPE_SONG):
            LOG.debug("Removing song/album/artist %s", item['ratingKey'])
            self.update_kodi_music_library = True
            with itemtypes.Music() as music_db:
                music_db.remove(item['ratingKey'])
        return True

    def process_timeline(self, data):
        """
        PMS is messing with the library items, e.g. new or changed. Put in our
        "processing queue" for later
        """
        for item in data:
            if 'tv.plex' in item.get('identifier', ''):
                # Ommit Plex DVR messages - the Plex IDs are not corresponding
                # (DVR ratingKeys are not unique and might correspond to a
                # movie or episode)
                continue
            typus = v.PLEX_TYPE_FROM_WEBSOCKET[int(item['type'])]
            if typus == v.PLEX_TYPE_CLIP:
                # No need to process extras or trailers
                continue
            status = int(item['state'])
            if typus == 'playlist':
                if not library_sync.PLAYLIST_SYNC_ENABLED:
                    continue
                playlists.websocket(plex_id=unicode(item['itemID']),
                                    status=status)
            elif status == 9:
                # Immediately and always process deletions (as the PMS will
                # send additional message with other codes)
                self.items_to_process.append({
                    'state': status,
                    'type': typus,
                    'ratingKey': str(item['itemID']),
                    'timestamp': utils.unix_timestamp(),
                    'attempt': 0
                })
            elif typus in (v.PLEX_TYPE_MOVIE,
                           v.PLEX_TYPE_EPISODE,
                           v.PLEX_TYPE_SONG) and status == 5:
                plex_id = str(item['itemID'])
                # Have we already added this element for processing?
                for existing_item in self.items_to_process:
                    if existing_item['ratingKey'] == plex_id:
                        break
                else:
                    # Haven't added this element to the queue yet
                    self.items_to_process.append({
                        'state': status,
                        'type': typus,
                        'ratingKey': plex_id,
                        'timestamp': utils.unix_timestamp(),
                        'attempt': 0
                    })

    def process_activity(self, data):
        """
        PMS is re-scanning an item, e.g. after having changed a movie poster.
        WATCH OUT for this if it's triggered by our PKC library scan!
        """
        for item in data:
            if item['event'] != 'ended':
                # Scan still going on, so skip for now
                continue
            elif item['Activity'].get('Context') is None:
                # Not related to any Plex element, but entire library
                continue
            elif item['Activity']['type'] != 'library.refresh.items':
                # Not the type of message relevant for us
                continue
            plex_id = PF.GetPlexKeyNumber(item['Activity']['Context']['key'])[1]
            if plex_id == '':
                # Likely a Plex id like /library/metadata/3/children
                continue
            # We're only looking at existing elements - have we synced yet?
            with plexdb.Get_Plex_DB() as plex_db:
                kodi_info = plex_db.getItem_byId(plex_id)
            if kodi_info is None:
                LOG.debug('Plex id %s not synced yet - skipping', plex_id)
                continue
            # Have we already added this element?
            for existing_item in self.items_to_process:
                if existing_item['ratingKey'] == plex_id:
                    break
            else:
                # Haven't added this element to the queue yet
                self.items_to_process.append({
                    'state': None,  # Don't need a state here
                    'type': kodi_info[5],
                    'ratingKey': plex_id,
                    'timestamp': utils.unix_timestamp(),
                    'attempt': 0
                })

    def process_playing(self, data):
        """
        Someone (not necessarily the user signed in) is playing something some-
        where
        """
        for item in data:
            status = item['state']
            if status == 'buffering' or status == 'stopped':
                # Drop buffering and stop messages immediately - no value
                continue
            plex_id = item['ratingKey']
            skip = False
            for pid in (0, 1, 2):
                if plex_id == state.PLAYER_STATES[pid]['plex_id']:
                    # Kodi is playing this item - no need to set the playstate
                    skip = True
            if skip:
                continue
            session_key = item['sessionKey']
            # Do we already have a sessionKey stored?
            if session_key not in self.session_keys:
                with plexdb.Get_Plex_DB() as plex_db:
                    kodi_info = plex_db.getItem_byId(plex_id)
                if kodi_info is None:
                    # Item not (yet) in Kodi library
                    continue
                if utils.settings('plex_serverowned') == 'false':
                    # Not our PMS, we are not authorized to get the sessions
                    # On the bright side, it must be us playing :-)
                    self.session_keys[session_key] = {}
                else:
                    # PMS is ours - get all current sessions
                    self.session_keys.update(PF.GetPMSStatus(state.PLEX_TOKEN))
                    LOG.debug('Updated current sessions. They are: %s',
                              self.session_keys)
                    if session_key not in self.session_keys:
                        LOG.info('Session key %s still unknown! Skip '
                                 'playstate update', session_key)
                        continue
                # Attach Kodi info to the session
                self.session_keys[session_key]['kodi_id'] = kodi_info[0]
                self.session_keys[session_key]['file_id'] = kodi_info[1]
                self.session_keys[session_key]['kodi_type'] = kodi_info[4]
            session = self.session_keys[session_key]
            if utils.settings('plex_serverowned') != 'false':
                # Identify the user - same one as signed on with PKC? Skip
                # update if neither session's username nor userid match
                # (Owner sometime's returns id '1', not always)
                if not state.PLEX_TOKEN and session['userId'] == '1':
                    # PKC not signed in to plex.tv. Plus owner of PMS is
                    # playing (the '1').
                    # Hence must be us (since several users require plex.tv
                    # token for PKC)
                    pass
                elif not (session['userId'] == state.PLEX_USER_ID or
                          session['username'] == state.PLEX_USERNAME):
                    LOG.debug('Our username %s, userid %s did not match '
                              'the session username %s with userid %s',
                              state.PLEX_USERNAME,
                              state.PLEX_USER_ID,
                              session['username'],
                              session['userId'])
                    continue
            # Get an up-to-date XML from the PMS because PMS will NOT directly
            # tell us: duration of item viewCount
            if session.get('duration') is None:
                xml = PF.GetPlexMetadata(plex_id)
                if xml in (None, 401):
                    LOG.error('Could not get up-to-date xml for item %s',
                              plex_id)
                    continue
                api = API(xml[0])
                userdata = api.userdata()
                session['duration'] = userdata['Runtime']
                session['viewCount'] = userdata['PlayCount']
            # Sometimes, Plex tells us resume points in milliseconds and
            # not in seconds - thank you very much!
            if item['viewOffset'] > session['duration']:
                resume = item['viewOffset'] / 1000
            else:
                resume = item['viewOffset']
            if resume < v.IGNORE_SECONDS_AT_START:
                continue
            try:
                completed = float(resume) / float(session['duration'])
            except (ZeroDivisionError, TypeError):
                LOG.error('Could not mark playstate for %s and session %s',
                          data, session)
                continue
            if completed >= v.MARK_PLAYED_AT:
                # Only mark completely watched ONCE
                if session.get('marked_played') is None:
                    session['marked_played'] = True
                    mark_played = True
                else:
                    # Don't mark it as completely watched again
                    continue
            else:
                mark_played = False
            LOG.debug('Update playstate for user %s with id %s for plex id %s',
                      state.PLEX_USERNAME, state.PLEX_USER_ID, plex_id)
            item_fkt = getattr(itemtypes,
                               v.ITEMTYPE_FROM_KODITYPE[session['kodi_type']])
            with item_fkt() as fkt:
                plex_type = v.PLEX_TYPE_FROM_KODI_TYPE[session['kodi_type']]
                fkt.updatePlaystate(mark_played,
                                    session['viewCount'],
                                    resume,
                                    session['duration'],
                                    session['file_id'],
                                    utils.unix_date_to_kodi(
                                        utils.unix_timestamp()),
                                    plex_type)

    def sync_fanart(self, missing_only=True, refresh=False):
        """
        Throw items to the fanart queue in order to download missing (or all)
        additional fanart.

        missing_only=True    False will start look-up for EVERY item
        refresh=False        True will force refresh all external fanart
        """
        if utils.settings('FanartTV') == 'false':
            return
        with plexdb.Get_Plex_DB() as plex_db:
            if missing_only:
                with plexdb.Get_Plex_DB() as plex_db:
                    items = plex_db.get_missing_fanart()
                LOG.info('Trying to get %s additional fanart', len(items))
            else:
                items = []
                for plex_type in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW):
                    items.extend(plex_db.itemsByType(plex_type))
                LOG.info('Trying to get ALL additional fanart for %s items',
                         len(items))
        if not items:
            return
        # Shuffle the list to not always start out identically
        shuffle(items)
        # Checking FanartTV for %s items
        self.fanartqueue.put(artwork.ArtworkSyncMessage(
            utils.lang(30018) % len(items)))
        for item in items:
            self.fanartqueue.put({
                'plex_id': item['plex_id'],
                'plex_type': item['plex_type'],
                'refresh': refresh
            })
        # FanartTV lookup completed
        self.fanartqueue.put(artwork.ArtworkSyncMessage(utils.lang(30019)))

    def triage_lib_scans(self):
        """
        Decides what to do if state.RUN_LIB_SCAN has been set. E.g. manually
        triggered full or repair syncs
        """
        if state.RUN_LIB_SCAN in ("full", "repair"):
            set_library_scan_toggle()
            LOG.info('Full library scan requested, starting')
            self.start_library_sync(show_dialog=True,
                                    repair=state.RUN_LIB_SCAN == 'repair',
                                    block=True)
            if self.sync_successful:
                # Full library sync finished
                self.show_kodi_note(utils.lang(39407))
            elif not self.suspend_item_sync():
                self.force_dialog = True
                # ERROR in library sync
                self.show_kodi_note(utils.lang(39410), icon='error')
                self.force_dialog = False
        elif state.RUN_LIB_SCAN == 'fanart':
            # Only look for missing fanart (No)
            # or refresh all fanart (Yes)
            from .windows import optionsdialog
            refresh = optionsdialog.show(utils.lang(29999),
                                         utils.lang(39223),
                                         utils.lang(39224),  # refresh all
                                         utils.lang(39225)) == 0
            self.sync_fanart(missing_only=not refresh, refresh=refresh)
        elif state.RUN_LIB_SCAN == 'textures':
            artwork.Artwork().fullTextureCacheSync()
        else:
            raise NotImplementedError('Library scan not defined: %s'
                                      % state.RUN_LIB_SCAN)

    def onLibrary_scan_finished(self, successful):
        """
        Hit this after the full sync has finished
        """
        self.sync_successful = successful
        self.last_full_sync = utils.unix_timestamp()
        set_library_scan_toggle(boolean=False)
        try:
            self.lock.release()
        except backgroundthread.threading.ThreadError:
            pass

    def start_library_sync(self, show_dialog=None, repair=False, block=False):
        show_dialog = show_dialog if show_dialog is not None else state.SYNC_DIALOG
        if block:
            self.lock.acquire()
            library_sync.start(show_dialog, repair, self.onLibrary_scan_finished)
            # Will block until scan is finished
            self.lock.acquire()
            self.lock.release()
        else:
            library_sync.start(show_dialog, repair, self.onLibrary_scan_finished)

    def run(self):
        try:
            self._run_internal()
        except:
            state.DB_SCAN = False
            utils.window('plex_dbScan', clear=True)
            utils.ERROR(txt='Sync.py crashed', notify=True)
            raise

    def _run_internal(self):
        LOG.info("---===### Starting Sync ###===---")
        install_sync_done = utils.settings('SyncInstallRunDone') == 'true'

        playlist_monitor = None
        initial_sync_done = False
        kodi_db_version_checked = False
        last_processing = 0
        last_time_sync = 0
        one_day_in_seconds = 60 * 60 * 24
        # Link to Websocket queue
        queue = state.WEBSOCKET_QUEUE

        if (not path_ops.exists(v.DB_VIDEO_PATH) or
                not path_ops.exists(v.DB_TEXTURE_PATH) or
                (state.ENABLE_MUSIC and not path_ops.exists(v.DB_MUSIC_PATH))):
            # Database does not exists
            LOG.error('The current Kodi version is incompatible')
            LOG.error('Current Kodi version: %s', utils.try_decode(
                xbmc.getInfoLabel('System.BuildVersion')))
            # "Current Kodi version is unsupported, cancel lib sync"
            utils.messageDialog(utils.lang(29999), utils.lang(39403))
            return

        # Do some initializing
        # Ensure that Plex DB is set-up
        plex_db.initialize()
        # Hack to speed up look-ups for actors (giant table!)
        utils.create_actor_db_index()
        # Run start up sync
        LOG.info("Db version: %s", utils.settings('dbCreatedWithVersion'))
        LOG.info('Refreshing video nodes and playlists now')
        with kodidb.GetKodiDB('video') as kodi_db:
            # Setup the paths for addon-paths (even when using direct paths)
            kodi_db.setup_path_table()

        while not self.isCanceled():
            # In the event the server goes offline
            while self.isSuspended():
                if self.isCanceled():
                    # Abort was requested while waiting. We should exit
                    LOG.info("###===--- Sync Stopped ---===###")
                    return
                xbmc.sleep(1000)

            if not install_sync_done:
                # Very FIRST sync ever upon installation or reset of Kodi DB
                set_library_scan_toggle()
                # Initialize time offset Kodi - PMS
                library_sync.sync_pms_time()
                last_time_sync = utils.unix_timestamp()
                LOG.info('Initial start-up full sync starting')
                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                # This call will block until scan is completed
                self.start_library_sync(show_dialog=True, block=True)
                if self.sync_successful:
                    LOG.info('Initial start-up full sync successful')
                    utils.settings('SyncInstallRunDone', value='true')
                    install_sync_done = True
                    utils.settings('dbCreatedWithVersion', v.ADDON_VERSION)
                    self.force_dialog = False
                    kodi_db_version_checked = True
                    if library_sync.PLAYLIST_SYNC_ENABLED:
                        from . import playlists
                        playlist_monitor = playlists.kodi_playlist_monitor()
                    self.sync_fanart()
                    self.fanartthread.start()
                else:
                    LOG.error('Initial start-up full sync unsuccessful')
                xbmc.executebuiltin('InhibitIdleShutdown(false)')

            elif not kodi_db_version_checked:
                # Install sync was already done, don't force-show dialogs
                self.force_dialog = False
                # Verify the validity of the database
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
                    break
                kodi_db_version_checked = True

            elif not initial_sync_done:
                # First sync upon PKC restart. Skipped if very first sync upon
                # PKC installation has been completed
                set_library_scan_toggle()
                LOG.info('Doing initial sync on Kodi startup')
                if state.SUSPEND_SYNC:
                    LOG.warning('Forcing startup sync even if Kodi is playing')
                    state.SUSPEND_SYNC = False
                self.start_library_sync(block=True)
                if self.sync_successful:
                    initial_sync_done = True
                    LOG.info('Done initial sync on Kodi startup')
                    if library_sync.PLAYLIST_SYNC_ENABLED:
                        from . import playlists
                        playlist_monitor = playlists.kodi_playlist_monitor()
                    artwork.Artwork().cache_major_artwork()
                    self.sync_fanart()
                    self.fanartthread.start()
                else:
                    LOG.info('Startup sync has not yet been successful')

            # Currently no db scan, so we could start a new scan
            elif state.DB_SCAN is False:
                # Full scan was requested from somewhere else, e.g. userclient
                if state.RUN_LIB_SCAN is not None:
                    # Force-show dialogs since they are user-initiated
                    self.force_dialog = True
                    self.triage_lib_scans()
                    self.force_dialog = False
                    # Reset the flag
                    state.RUN_LIB_SCAN = None
                    continue

                # Standard syncs - don't force-show dialogs
                now = utils.unix_timestamp()
                self.force_dialog = False
                if (now - self.last_full_sync > state.FULL_SYNC_INTERVALL):
                    LOG.info('Doing scheduled full library scan')
                    set_library_scan_toggle()
                    success = self.maintain_views()
                    if success:
                        success = library_sync.start()
                    if not success and not self.suspend_item_sync():
                        LOG.error('Could not finish scheduled full sync')
                        self.force_dialog = True
                        self.show_kodi_note(utils.lang(39410),
                                            icon='error')
                        self.force_dialog = False
                    elif success:
                        self.last_full_sync = now
                        # Full library sync finished successfully
                        self.show_kodi_note(utils.lang(39407))
                    else:
                        LOG.info('Full sync interrupted')
                elif now - last_time_sync > one_day_in_seconds:
                    LOG.info('Starting daily time sync')
                    library_sync.sync_pms_time()
                    last_time_sync = now
                elif not state.BACKGROUND_SYNC_DISABLED:
                    # Check back whether we should process something
                    # Only do this once every while (otherwise, potentially
                    # many screen refreshes lead to flickering)
                    if now - last_processing > 5:
                        last_processing = now
                        self.process_items()
                    # See if there is a PMS message we need to handle
                    try:
                        message = queue.get(block=False)
                    except backgroundthread.Queue.Empty:
                        pass
                    # Got a message from PMS; process it
                    else:
                        self.process_message(message)
                        queue.task_done()
                        # Sleep just a bit
                        xbmc.sleep(10)
                        continue
            xbmc.sleep(100)
        # Shut down playlist monitoring
        if playlist_monitor:
            playlist_monitor.stop()
        # doUtils could still have a session open due to interrupted sync
        try:
            DU().stopSession()
        except AttributeError:
            pass
        LOG.info("###===--- Sync Stopped ---===###")

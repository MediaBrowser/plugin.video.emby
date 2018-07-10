# -*- coding: utf-8 -*-
from logging import getLogger
import Queue
import xbmc

from .watchdog import events
from .watchdog.observers import Observer
from .watchdog.utils.bricks import OrderedSetQueue
from . import playlist_func as PL
from .plex_api import API
from . import kodidb_functions as kodidb
from . import plexdb_functions as plexdb
from . import utils
from . import path_ops
from . import variables as v
from . import state

###############################################################################

LOG = getLogger('PLEX.playlists')

# Safety margin for playlist filesystem operations
FILESYSTEM_TIMEOUT = 1
# These filesystem events are considered similar
SIMILAR_EVENTS = (events.EVENT_TYPE_CREATED, events.EVENT_TYPE_MODIFIED)

# Which playlist formates are supported by PKC?
SUPPORTED_FILETYPES = (
    'm3u',
    # 'm3u8'
    # 'pls',
    # 'cue',
)


def create_plex_playlist(playlist):
    """
    Adds the playlist [Playlist_Object] to the PMS. If playlist.id is
    not None the existing Plex playlist will be overwritten; otherwise a new
    playlist will be generated and stored accordingly in the playlist object.
    Will also add (or modify an existing) Plex playlist table entry.
    Make sure that playlist.kodi_hash is set!
    Returns None or raises PL.PlaylistError
    """
    LOG.debug('Creating Plex playlist from Kodi file: %s', playlist)
    plex_ids = _playlist_file_to_plex_ids(playlist)
    if not plex_ids:
        LOG.info('No Plex ids found for playlist %s', playlist)
        raise PL.PlaylistError
    for pos, plex_id in enumerate(plex_ids):
        try:
            if pos == 0 or not playlist.id:
                PL.init_plex_playlist(playlist, plex_id)
            else:
                PL.add_item_to_plex_playlist(playlist, plex_id=plex_id)
        except PL.PlaylistError:
            continue
    update_plex_table(playlist)
    LOG.debug('Done creating Plex playlist %s', playlist)


def delete_plex_playlist(playlist):
    """
    Removes the playlist [Playlist_Object] from the PMS. Will also delete the
    entry in the Plex playlist table.
    Returns None or raises PL.PlaylistError
    """
    LOG.debug('Deleting playlist from PMS: %s', playlist)
    PL.delete_playlist_from_pms(playlist)
    update_plex_table(playlist, delete=True)


def create_kodi_playlist(plex_id):
    """
    Creates a new Kodi playlist file. Will also add (or modify an existing)
    Plex playlist table entry.
    Assumes that the Plex playlist is indeed new. A NEW Kodi playlist will be
    created in any case (not replaced). Thus make sure that the "same" playlist
    is deleted from both disk and the Plex database.
    Returns the playlist or raises PL.PlaylistError
    """
    xml_metadata = PL.get_pms_playlist_metadata(plex_id)
    if xml_metadata is None:
        LOG.error('Could not get Plex playlist metadata %s', plex_id)
        raise PL.PlaylistError('Could not get Plex playlist %s' % plex_id)
    api = API(xml_metadata[0])
    playlist = PL.Playlist_Object()
    playlist.id = api.plex_id()
    playlist.type = v.KODI_PLAYLIST_TYPE_FROM_PLEX[api.playlist_type()]
    playlist.plex_name = api.title()
    playlist.plex_updatedat = api.updated_at()
    LOG.debug('Creating new Kodi playlist from Plex playlist: %s', playlist)
    # Derive filename close to Plex playlist name
    name = utils.valid_filename(playlist.plex_name)
    path = path_ops.path.join(v.PLAYLIST_PATH, playlist.type, '%s.m3u' % name)
    while path_ops.exists(path) or playlist_object_from_db(path=path):
        # In case the Plex playlist names are not unique
        occurance = utils.REGEX_FILE_NUMBERING.search(path)
        if not occurance:
            path = path_ops.path.join(v.PLAYLIST_PATH,
                                      playlist.type,
                                      '%s_01.m3u' % name[:min(len(name), 248)])
        else:
            occurance = int(occurance.group(1)) + 1
            path = path_ops.path.join(v.PLAYLIST_PATH,
                                      playlist.type,
                                      '%s_%02d.m3u' % (name[:min(len(name),
                                                                 248)],
                                                       occurance))
    LOG.debug('Kodi playlist path: %s', path)
    playlist.kodi_path = path
    xml_playlist = PL.get_PMS_playlist(playlist, playlist_id=plex_id)
    if xml_playlist is None:
        LOG.error('Could not get Plex playlist %s', plex_id)
        raise PL.PlaylistError('Could not get Plex playlist %s' % plex_id)
    _write_playlist_to_file(playlist, xml_playlist)
    playlist.kodi_hash = utils.generate_file_md5(path)
    update_plex_table(playlist)
    LOG.debug('Created Kodi playlist based on Plex playlist: %s', playlist)


def delete_kodi_playlist(playlist):
    """
    Removes the corresponding Kodi file for playlist [Playlist_Object] from
    disk. Be sure that playlist.kodi_path is set. Will also delete the entry in
    the Plex playlist table.
    Returns None or raises PL.PlaylistError
    """
    if path_ops.exists(playlist.kodi_path):
        try:
            path_ops.remove(playlist.kodi_path)
        except (OSError, IOError) as err:
            LOG.error('Could not delete Kodi playlist file %s. Error:\n%s: %s',
                      playlist, err.errno, err.strerror)
            raise PL.PlaylistError('Could not delete %s' % playlist.kodi_path)
    update_plex_table(playlist, delete=True)


def update_plex_table(playlist, delete=False):
    """
    Assumes that all sync operations are over. Takes playlist [Playlist_Object]
    and creates/updates the corresponding Plex playlists table entry

    Pass delete=True to delete the playlist entry
    """
    with plexdb.Get_Plex_DB() as plex_db:
        if delete:
            plex_db.delete_playlist_entry(playlist)
        else:
            plex_db.insert_playlist_entry(playlist)


def _playlist_file_to_plex_ids(playlist):
    """
    Takes the playlist file located at path [unicode] and parses it.
    Returns a list of plex_ids (str) or raises PL.PlaylistError if a single
    item cannot be parsed from Kodi to Plex.
    """
    if playlist.kodi_extension == 'm3u':
        plex_ids = m3u_to_plex_ids(playlist)
    else:
        LOG.error('Unsupported playlist extension: %s',
                  playlist.kodi_extension)
        raise PL.PlaylistError
    return plex_ids


def _m3u_iterator(text):
    """
    Yields e.g. plugin://plugin.video.plexkodiconnect.movies/?plex_id=xxx
    """
    lines = iter(text.split('\n'))
    for line in lines:
        if line.startswith('#EXTINF:'):
            yield next(lines).strip()


def m3u_to_plex_ids(playlist):
    """
    Adapter to process *.m3u playlist files. Encoding is not uniform!
    """
    plex_ids = list()
    with open(path_ops.encode_path(playlist.kodi_path), 'rb') as f:
        text = f.read()
    try:
        text = text.decode(v.M3U_ENCODING)
    except UnicodeDecodeError:
        LOG.warning('Fallback to ISO-8859-1 decoding for %s', playlist)
        text = text.decode('ISO-8859-1')
    for entry in _m3u_iterator(text):
        plex_id = utils.REGEX_PLEX_ID.search(entry)
        if plex_id:
            plex_id = plex_id.group(1)
            plex_ids.append(plex_id)
        else:
            # Add-on paths not working, try direct
            kodi_id, kodi_type = kodidb.kodiid_from_filename(
                entry, db_type=playlist.type)
            if not kodi_id:
                continue
            with plexdb.Get_Plex_DB() as plex_db:
                plex_id = plex_db.getItem_byKodiId(kodi_id, kodi_type)
            if plex_id:
                plex_ids.append(plex_id[0])
    return plex_ids


def _write_playlist_to_file(playlist, xml):
    """
    Feed with playlist [Playlist_Object]. Will write the playlist to a m3u file
    Returns None or raises PL.PlaylistError
    """
    text = '#EXTCPlayListM3U::M3U\n'
    for element in xml:
        api = API(element)
        append_season_episode = False
        if api.plex_type() == v.PLEX_TYPE_EPISODE:
            _, show, season_id, episode_id = api.episode_data()
            try:
                season_id = int(season_id)
                episode_id = int(episode_id)
            except ValueError:
                pass
            else:
                append_season_episode = True
            if append_season_episode:
                text += ('#EXTINF:%s,%s S%.2dE%.2d - %s\n%s\n'
                         % (api.runtime(), show, season_id, episode_id,
                            api.title(), api.path()))
            else:
                # Only append the TV show name
                text += ('#EXTINF:%s,%s - %s\n%s\n'
                         % (api.runtime(), show, api.title(), api.path()))
        else:
            text += ('#EXTINF:%s,%s\n%s\n'
                     % (api.runtime(), api.title(), api.path()))
    text += '\n'
    text = text.encode(v.M3U_ENCODING, 'strict')
    try:
        with open(path_ops.encode_path(playlist.kodi_path), 'wb') as f:
            f.write(text)
    except EnvironmentError as err:
        LOG.error('Could not write Kodi playlist file: %s', playlist)
        LOG.error('Error message %s: %s', err.errno, err.strerror)
        raise PL.PlaylistError('Cannot write Kodi playlist to path for %s'
                               % playlist)


def plex_id_from_playlist_path(path):
    """
    Given the Kodi playlist path [unicode], this will return the Plex id [str]
    or None
    """
    with plexdb.Get_Plex_DB() as plex_db:
        plex_id = plex_db.plex_id_from_playlist_path(path)
    if not plex_id:
        LOG.error('Could not find existing entry for playlist path %s', path)
    return plex_id


def playlist_object_from_db(path=None, kodi_hash=None, plex_id=None):
    """
    Returns the playlist as a Playlist_Object for either the plex_id, path or
    kodi_hash. kodi_hash will be more reliable as it includes path and file
    content.
    """
    playlist = PL.Playlist_Object()
    with plexdb.Get_Plex_DB() as plex_db:
        playlist = plex_db.retrieve_playlist(playlist,
                                             plex_id,
                                             path, kodi_hash)
    return playlist


def process_websocket(plex_id, status):
    """
    Hit by librarysync to process websocket messages concerning playlists
    """
    create = False
    with state.LOCK_PLAYLISTS:
        playlist = playlist_object_from_db(plex_id=plex_id)
        if playlist and status == 9:
            # Won't be able to download metadata of the deleted playlist
            if sync_plex_playlist(playlist=playlist):
                LOG.debug('Plex deletion of playlist detected: %s', playlist)
                try:
                    delete_kodi_playlist(playlist)
                except PL.PlaylistError:
                    pass
            return
        xml = PL.get_pms_playlist_metadata(plex_id)
        if xml is None:
            LOG.debug('Could not download playlist %s, probably deleted',
                      plex_id)
            return
        if not sync_plex_playlist(xml=xml[0]):
            return
        api = API(xml[0])
        try:
            if playlist:
                if api.updated_at() == playlist.plex_updatedat:
                    LOG.debug('Playlist with id %s already synced: %s',
                              plex_id, playlist)
                else:
                    LOG.debug('Change of Plex playlist detected: %s',
                              playlist)
                    delete_kodi_playlist(playlist)
                    create = True
            elif not playlist and not status == 9:
                LOG.debug('Creation of new Plex playlist detected: %s',
                          plex_id)
                create = True
            # To the actual work
            if create:
                create_kodi_playlist(plex_id)
        except PL.PlaylistError:
            pass


def full_sync():
    """
    Full sync of playlists between Kodi and Plex. Returns True is successful,
    False otherwise
    """
    if not state.SYNC_PLAYLISTS:
        LOG.debug('Not syncing playlists')
        return True
    LOG.info('Starting playlist full sync')
    with state.LOCK_PLAYLISTS:
        return _full_sync()


def _full_sync():
    """
    Need to lock because we're messing with playlists
    """
    # Get all Plex playlists
    xml = PL.get_all_playlists()
    if xml is None:
        return False
    # For each playlist, check Plex database to see whether we already synced
    # before. If yes, make sure that hashes are identical. If not, sync it.
    with plexdb.Get_Plex_DB() as plex_db:
        old_plex_ids = plex_db.plex_ids_all_playlists()
    for xml_playlist in xml:
        api = API(xml_playlist)
        try:
            old_plex_ids.remove(api.plex_id())
        except ValueError:
            pass
        if not sync_plex_playlist(xml=xml_playlist):
            continue
        playlist = playlist_object_from_db(plex_id=api.plex_id())
        try:
            if not playlist:
                LOG.debug('New Plex playlist %s discovered: %s',
                          api.plex_id(), api.title())
                create_kodi_playlist(api.plex_id())
            elif playlist.plex_updatedat != api.updated_at():
                LOG.debug('Detected changed Plex playlist %s: %s',
                          api.plex_id(), api.title())
                delete_kodi_playlist(playlist)
                create_kodi_playlist(api.plex_id())
        except PL.PlaylistError:
            LOG.info('Skipping playlist %s: %s', api.plex_id(), api.title())
    # Get rid of old Plex playlists that were deleted on the Plex side
    for plex_id in old_plex_ids:
        playlist = playlist_object_from_db(plex_id=plex_id)
        if playlist:
            LOG.debug('Removing outdated Plex playlist %s from %s',
                      playlist.plex_name, playlist.kodi_path)
            try:
                delete_kodi_playlist(playlist)
            except PL.PlaylistError:
                LOG.debug('Skipping deletion of playlist %s: %s',
                          api.plex_id(), api.title())
    # Look at all supported Kodi playlists. Check whether they are in the DB.
    with plexdb.Get_Plex_DB() as plex_db:
        old_kodi_paths = plex_db.all_kodi_playlist_paths()
    for root, _, files in path_ops.walk(v.PLAYLIST_PATH):
        for f in files:
            path = path_ops.path.join(root, f)
            try:
                old_kodi_paths.remove(path)
            except ValueError:
                pass
            if not sync_kodi_playlist(path):
                continue
            kodi_hash = utils.generate_file_md5(path)
            playlist = playlist_object_from_db(path=path)
            if playlist and playlist.kodi_hash == kodi_hash:
                continue
            try:
                if not playlist:
                    LOG.debug('New Kodi playlist detected: %s', path)
                    playlist = PL.Playlist_Object()
                    playlist.kodi_path = path
                    playlist.kodi_hash = kodi_hash
                    create_plex_playlist(playlist)
                else:
                    LOG.debug('Changed Kodi playlist detected: %s', playlist)
                    delete_plex_playlist(playlist)
                    playlist.kodi_hash = kodi_hash
                    create_plex_playlist(playlist)
            except PL.PlaylistError:
                LOG.info('Skipping Kodi playlist %s', path)
    for kodi_path in old_kodi_paths:
        playlist = playlist_object_from_db(kodi_path=kodi_path)
        try:
            delete_plex_playlist(playlist)
        except PL.PlaylistError:
            LOG.debug('Skipping deletion of playlist %s: %s',
                      playlist.plex_id, playlist.plex_name)
    LOG.info('Playlist full sync done')
    return True


def sync_kodi_playlist(path):
    """
    Returns True if we should sync this Kodi playlist with path [unicode] to
    Plex based on the playlist file name and the user settings, False otherwise
    """
    if path.startswith(v.PLAYLIST_PATH_MIXED):
        return False
    try:
        extension = path.rsplit('.', 1)[1].lower()
    except IndexError:
        return False
    if extension not in SUPPORTED_FILETYPES:
        return False
    if not state.SYNC_SPECIFIC_KODI_PLAYLISTS:
        return True
    playlist = PL.Playlist_Object()
    playlist.kodi_path = path
    prefix = utils.settings('syncSpecificKodiPlaylistsPrefix').lower()
    if playlist.kodi_filename.lower().startswith(prefix):
        return True
    LOG.debug('User chose to not sync Kodi playlist %s', path)
    return False


def sync_plex_playlist(plex_id=None, xml=None, playlist=None):
    """
    Returns True if we should sync this specific Plex playlist due to the
    user settings (including a disabled music library), False if not.

    Pass in either the plex_id or an xml (where API(xml) will be used)
    """
    if not state.SYNC_SPECIFIC_PLEX_PLAYLISTS:
        return True
    if playlist:
        # Mainly once we DELETED a Plex playlist that we're NOT supposed
        # to sync
        name = playlist.plex_name
        typus = playlist.type
    else:
        if xml is None:
            xml = PL.get_pms_playlist_metadata(plex_id)
            if xml is None:
                LOG.info('Could not get Plex metadata for playlist %s',
                         plex_id)
                return False
            api = API(xml[0])
        else:
            api = API(xml)
        name = api.title()
        typus = api.playlist_type()
    if (not state.ENABLE_MUSIC and typus == v.PLEX_PLAYLIST_TYPE_AUDIO):
        LOG.debug('Not synching Plex audio playlist')
        return False
    prefix = utils.settings('syncSpecificPlexPlaylistsPrefix').lower()
    if name and name.lower().startswith(prefix):
        return True
    LOG.debug('User chose to not sync Plex playlist')
    return False


class PlaylistEventhandler(events.FileSystemEventHandler):
    """
    PKC eventhandler to monitor Kodi playlists safed to disk
    """
    def dispatch(self, event):
        """
        Dispatches events to the appropriate methods.

        :param event:
            The event object representing the file system event.
        :type event:
            :class:`FileSystemEvent`
        """
        if not state.SYNC_PLAYLISTS:
            # Sync is deactivated
            return
        path = event.dest_path if event.event_type == events.EVENT_TYPE_MOVED \
            else event.src_path
        if not sync_kodi_playlist(path):
            return
        _method_map = {
            events.EVENT_TYPE_MODIFIED: self.on_modified,
            events.EVENT_TYPE_MOVED: self.on_moved,
            events.EVENT_TYPE_CREATED: self.on_created,
            events.EVENT_TYPE_DELETED: self.on_deleted,
        }
        with state.LOCK_PLAYLISTS:
            _method_map[event.event_type](event)

    def on_created(self, event):
        LOG.debug('on_created: %s', event.src_path)
        old_playlist = playlist_object_from_db(path=event.src_path)
        kodi_hash = utils.generate_file_md5(event.src_path)
        if old_playlist and old_playlist.kodi_hash == kodi_hash:
            LOG.debug('Playlist already in DB - skipping')
            return
        elif old_playlist:
            LOG.debug('Playlist already in DB but it has been changed')
            self.on_modified(event)
            return
        playlist = PL.Playlist_Object()
        playlist.kodi_path = event.src_path
        playlist.kodi_hash = kodi_hash
        try:
            create_plex_playlist(playlist)
        except PL.PlaylistError:
            pass

    def on_modified(self, event):
        LOG.debug('on_modified: %s', event.src_path)
        old_playlist = playlist_object_from_db(path=event.src_path)
        kodi_hash = utils.generate_file_md5(event.src_path)
        if old_playlist and old_playlist.kodi_hash == kodi_hash:
            LOG.debug('Nothing modified, playlist already in DB - skipping')
            return
        new_playlist = PL.Playlist_Object()
        if old_playlist:
            # Retain the name! Might've come from Plex
            # (rename should fire on_moved)
            new_playlist.plex_name = old_playlist.plex_name
            delete_plex_playlist(old_playlist)
        new_playlist.kodi_path = event.src_path
        new_playlist.kodi_hash = kodi_hash
        try:
            create_plex_playlist(new_playlist)
        except PL.PlaylistError:
            pass

    def on_moved(self, event):
        LOG.debug('on_moved: %s to %s', event.src_path, event.dest_path)
        kodi_hash = utils.generate_file_md5(event.dest_path)
        # First check whether we don't already have destination playlist in
        # our DB. Just in case....
        old_playlist = playlist_object_from_db(path=event.dest_path)
        if old_playlist:
            LOG.warning('Found target playlist already in our DB!')
            new_event = events.FileModifiedEvent(event.dest_path)
            self.on_modified(new_event)
            return
        # All good
        old_playlist = playlist_object_from_db(path=event.src_path)
        if not old_playlist:
            LOG.debug('Did not have source path in the DB %s', event.src_path)
        else:
            delete_plex_playlist(old_playlist)
        new_playlist = PL.Playlist_Object()
        new_playlist.kodi_path = event.dest_path
        new_playlist.kodi_hash = kodi_hash
        try:
            create_plex_playlist(new_playlist)
        except PL.PlaylistError:
            pass

    def on_deleted(self, event):
        LOG.debug('on_deleted: %s', event.src_path)
        playlist = playlist_object_from_db(path=event.src_path)
        if not playlist:
            LOG.info('Playlist not found in DB for path %s', event.src_path)
        else:
            delete_plex_playlist(playlist)


class PlaylistQueue(OrderedSetQueue):
    """
    OrderedSetQueue that drops all directory events immediately
    """
    def _put(self, item):
        if item[0].is_directory:
            self.unfinished_tasks -= 1
        else:
            # Can't use super as OrderedSetQueue is old style class
            OrderedSetQueue._put(self, item)


class PlaylistObserver(Observer):
    """
    PKC implementation, overriding the dispatcher. PKC will wait for the
    duration timeout (in seconds) AFTER receiving a filesystem event. A new 
    ("non-similar") event will reset the timer.
    Creating and modifying will be regarded as equal.
    """
    def __init__(self, *args, **kwargs):
        super(PlaylistObserver, self).__init__(*args, **kwargs)
        # Drop the same events that get into the queue even if there are other
        # events in between these similar events. Ignore directory events
        # completely
        self._event_queue = PlaylistQueue()

    @staticmethod
    def _pkc_similar_events(event1, event2):
        if event1 == event2:
            return True
        elif (event1.src_path == event2.src_path and
              event1.event_type in SIMILAR_EVENTS and
              event2.event_type in SIMILAR_EVENTS):
            # Set created and modified events to equal
            return True
        return False

    def _dispatch_iterator(self, event_queue, timeout):
        """
        This iterator will block for timeout (seconds) until an event is
        received or raise Queue.Empty.
        """
        event, watch = event_queue.get(block=True, timeout=timeout)
        event_queue.task_done()
        start = utils.unix_timestamp()
        while utils.unix_timestamp() - start < timeout:
            if state.STOP_PKC:
                raise Queue.Empty
            try:
                new_event, new_watch = event_queue.get(block=False)
            except Queue.Empty:
                xbmc.sleep(200)
            else:
                event_queue.task_done()
                start = utils.unix_timestamp()
                if self._pkc_similar_events(new_event, event):
                    continue
                else:
                    yield event, watch
                    event, watch = new_event, new_watch
        yield event, watch

    def dispatch_events(self, event_queue, timeout):
        for event, watch in self._dispatch_iterator(event_queue, timeout):
            # This is copy-paste of original code
            with self._lock:
                # To allow unschedule/stop and safe removal of event handlers
                # within event handlers itself, check if the handler is still
                # registered after every dispatch.
                for handler in list(self._handlers.get(watch, [])):
                    if handler in self._handlers.get(watch, []):
                        handler.dispatch(event)


def kodi_playlist_monitor():
    """
    Monitors the Kodi playlist folder special://profile/playlist for the user.
    Will thus catch all changes on the Kodi side of things.

    Returns an watchdog Observer instance. Be sure to use
    observer.stop() (and maybe observer.join()) to shut down properly
    """
    event_handler = PlaylistEventhandler()
    observer = PlaylistObserver(timeout=FILESYSTEM_TIMEOUT)
    observer.schedule(event_handler, v.PLAYLIST_PATH, recursive=True)
    observer.start()
    return observer

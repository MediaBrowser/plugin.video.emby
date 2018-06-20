# -*- coding: utf-8 -*-
from logging import getLogger
import os
import sys
from threading import Lock

from xbmcvfs import exists

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import playlist_func as PL
from PlexAPI import API
import kodidb_functions as kodidb
import plexdb_functions as plexdb
import utils
import variables as v
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

# Necessary to temporarily hold back librarysync/websocket listener when doing
# a full sync
LOCK = Lock()
LOCKER = utils.LockFunction(LOCK)

# Which playlist formates are supported by PKC?
SUPPORTED_FILETYPES = (
    'm3u',
    # 'm3u8'
    # 'pls',
    # 'cue',
)

# Watchdog copy-paste
EVENT_TYPE_MOVED = 'moved'
EVENT_TYPE_DELETED = 'deleted'
EVENT_TYPE_CREATED = 'created'
EVENT_TYPE_MODIFIED = 'modified'

# m3u files do not have encoding specified
if v.PLATFORM == 'Windows':
    ENCODING = 'mbcs'
else:
    ENCODING = sys.getdefaultencoding()


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


def create_kodi_playlist(plex_id=None, updated_at=None):
    """
    Creates a new Kodi playlist file. Will also add (or modify an existing) Plex
    playlist table entry.
    Assumes that the Plex playlist is indeed new. A NEW Kodi playlist will be
    created in any case (not replaced). Thus make sure that the "same" playlist
    is deleted from both disk and the Plex database.
    Returns the playlist or raises PL.PlaylistError
    """
    xml = PL.get_PMS_playlist(PL.Playlist_Object(), playlist_id=plex_id)
    if xml is None:
        LOG.error('Could not get Plex playlist %s', plex_id)
        raise PL.PlaylistError('Could not get Plex playlist %s' % plex_id)
    api = API(xml)
    playlist = PL.Playlist_Object()
    playlist.id = api.plex_id()
    playlist.type = v.KODI_PLAYLIST_TYPE_FROM_PLEX[api.playlist_type()]
    if not state.ENABLE_MUSIC and playlist.type == v.KODI_PLAYLIST_TYPE_AUDIO:
        return
    playlist.plex_name = api.title()
    playlist.plex_updatedat = updated_at
    LOG.debug('Creating new Kodi playlist from Plex playlist: %s', playlist)
    name = utils.valid_filename(playlist.plex_name)
    path = os.path.join(v.PLAYLIST_PATH, playlist.type, '%s.m3u' % name)
    while exists(path) or playlist_object_from_db(path=path):
        # In case the Plex playlist names are not unique
        occurance = utils.REGEX_FILE_NUMBERING.search(path)
        if not occurance:
            path = os.path.join(v.PLAYLIST_PATH,
                                playlist.type,
                                '%s_01.m3u' % name[:min(len(name), 248)])
        else:
            occurance = int(occurance.group(1)) + 1
            path = os.path.join(v.PLAYLIST_PATH,
                                playlist.type,
                                '%s_%02d.m3u' % (name[:min(len(name), 248)],
                                                 occurance))
    LOG.debug('Kodi playlist path: %s', path)
    playlist.kodi_path = path
    # Derive filename close to Plex playlist name
    _write_playlist_to_file(playlist, xml)
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
    try:
        os.remove(playlist.kodi_path)
    except (OSError, IOError) as err:
        LOG.error('Could not delete Kodi playlist file %s. Error:\n %s: %s',
                  playlist, err.errno, err.strerror)
        raise PL.PlaylistError('Could not delete %s' % playlist.kodi_path)
    else:
        update_plex_table(playlist, delete=True)


def update_plex_table(playlist, delete=False):
    """
    Assumes that all sync operations are over. Takes playlist [Playlist_Object]
    and creates/updates the corresponding Plex playlists table entry

    Pass delete=True to delete the playlist entry
    """
    if delete:
        with plexdb.Get_Plex_DB() as plex_db:
            plex_db.delete_playlist_entry(playlist)
        return
    with plexdb.Get_Plex_DB() as plex_db:
        plex_db.insert_playlist_entry(playlist)


def _playlist_file_to_plex_ids(playlist):
    """
    Takes the playlist file located at path [unicode] and parses it.
    Returns a list of plex_ids (str) or raises PL.PlaylistError if a single
    item cannot be parsed from Kodi to Plex.
    """
    if playlist.kodi_extension == 'm3u':
        plex_ids = m3u_to_plex_ids(playlist)
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
    with open(playlist.kodi_path, 'rb') as f:
        text = f.read()
    try:
        text = text.decode(ENCODING)
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
    text = u'#EXTCPlayListM3U::M3U\n'
    for element in xml:
        api = API(element)
        text += (u'#EXTINF:%s,%s\n%s\n'
                 % (api.runtime(), api.title(), api.path()))
    text += '\n'
    text = text.encode(ENCODING, 'ignore')
    try:
        with open(playlist.kodi_path, 'wb') as f:
            f.write(text)
    except (OSError, IOError) as err:
        LOG.error('Could not write Kodi playlist file: %s', playlist)
        LOG.error('Error message %s: %s', err.errno, err.strerror)
        raise PL.PlaylistError('Cannot write Kodi playlist to path for %s'
                               % playlist)


def change_plex_playlist_name(playlist, new_name):
    """
    TODO - Renames the existing playlist with new_name [unicode]
    """
    pass


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
        playlist = plex_db.retrieve_playlist(playlist, plex_id, path, kodi_hash)
    return playlist


def _kodi_playlist_identical(xml_element):
    """
    Feed with one playlist xml element from the PMS. Will return True if PKC
    already synced this playlist, False if not or if the Play playlist has
    changed in the meantime
    """
    pass


@LOCKER.lockthis
def process_websocket(plex_id, updated_at, state):
    """
    Hit by librarysync to process websocket messages concerning playlists
    """
    create = False
    playlist = playlist_object_from_db(plex_id=plex_id)
    try:
        if playlist and state == 9:
            LOG.debug('Plex deletion of playlist detected: %s', playlist)
            delete_kodi_playlist(playlist)
        elif playlist and playlist.plex_updatedat == updated_at:
            LOG.debug('Playlist with id %s already synced: %s',
                      plex_id, playlist)
        elif playlist:
            LOG.debug('Change of Plex playlist detected: %s', playlist)
            delete_kodi_playlist(playlist)
            create = True
        elif not playlist and not state == 9:
            LOG.debug('Creation of new Plex playlist detected: %s', plex_id)
            create = True
        # To the actual work
        if create:
            create_kodi_playlist(plex_id=plex_id, updated_at=updated_at)
    except PL.PlaylistError:
        pass


@LOCKER.lockthis
def full_sync():
    """
    Full sync of playlists between Kodi and Plex. Returns True is successful,
    False otherwise
    """
    LOG.info('Starting playlist full sync')
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
        if (not state.ENABLE_MUSIC and
                api.playlist_type() == v.PLEX_TYPE_AUDIO_PLAYLIST):
            continue
        playlist = playlist_object_from_db(plex_id=api.plex_id())
        try:
            if not playlist:
                LOG.debug('New Plex playlist %s discovered: %s',
                          api.plex_id(), api.title())
                create_kodi_playlist(api.plex_id(), api.updated_at())
                continue
            elif playlist.plex_updatedat != api.updated_at():
                LOG.debug('Detected changed Plex playlist %s: %s',
                          api.plex_id(), api.title())
                if exists(playlist.kodi_path):
                    delete_kodi_playlist(playlist)
                else:
                    update_plex_table(playlist, delete=True)
                create_kodi_playlist(api.plex_id(), api.updated_at())
        except PL.PlaylistError:
            LOG.info('Skipping playlist %s: %s', api.plex_id(), api.title())
        try:
            old_plex_ids.remove(api.plex_id())
        except ValueError:
            pass
    # Get rid of old Plex playlists that were deleted on the Plex side
    for plex_id in old_plex_ids:
        playlist = playlist_object_from_db(plex_id=plex_id)
        if playlist:
            LOG.debug('Removing outdated Plex playlist %s from %s',
                      playlist.plex_name, playlist.kodi_path)
            try:
                delete_kodi_playlist(playlist)
            except PL.PlaylistError:
                pass
    # Look at all supported Kodi playlists. Check whether they are in the DB.
    with plexdb.Get_Plex_DB() as plex_db:
        old_kodi_hashes = plex_db.kodi_hashes_all_playlists()
    master_paths = [v.PLAYLIST_PATH_VIDEO]
    if state.ENABLE_MUSIC:
        master_paths.append(v.PLAYLIST_PATH_MUSIC)
    for master_path in master_paths:
        for root, _, files in os.walk(master_path):
            for file in files:
                try:
                    extension = file.rsplit('.', 1)[1]
                except IndexError:
                    continue
                if extension not in SUPPORTED_FILETYPES:
                    continue
                path = os.path.join(root, file)
                kodi_hash = utils.generate_file_md5(path)
                playlist = playlist_object_from_db(kodi_hash=kodi_hash)
                playlist_2 = playlist_object_from_db(path=path)
                if playlist:
                    # Nothing changed at all - neither path nor content
                    old_kodi_hashes.remove(kodi_hash)
                    continue
                try:
                    playlist = PL.Playlist_Object()
                    playlist.kodi_path = path
                    playlist.kodi_hash = kodi_hash
                    if playlist_2:
                        LOG.debug('Changed Kodi playlist %s detected: %s',
                                  playlist_2.plex_name, path)
                        playlist.id = playlist_2.id
                        playlist.plex_name = playlist_2.plex_name
                        delete_plex_playlist(playlist_2)
                        create_plex_playlist(playlist)
                    else:
                        LOG.debug('New Kodi playlist detected: %s', path)
                        # Make sure that we delete any playlist with other hash
                        create_plex_playlist(playlist)
                except PL.PlaylistError:
                    LOG.info('Skipping Kodi playlist %s', path)
    for kodi_hash in old_kodi_hashes:
        playlist = playlist_object_from_db(kodi_hash=kodi_hash)
        if playlist:
            try:
                delete_plex_playlist(playlist)
            except PL.PlaylistError:
                pass
    LOG.info('Playlist full sync done')
    return True


class PlaylistEventhandler(FileSystemEventHandler):
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
        if event.is_directory:
            # todo: take care of folder renames
            return
        try:
            _, extension = event.src_path.rsplit('.', 1)
        except ValueError:
            return
        if extension.lower() not in SUPPORTED_FILETYPES:
            return
        if event.src_path.startswith(v.PLAYLIST_PATH_MIXED):
            return
        if (not state.ENABLE_MUSIC and
                event.src_path.startswith(v.PLAYLIST_PATH_MUSIC)):
            return
        _method_map = {
            EVENT_TYPE_MODIFIED: self.on_modified,
            EVENT_TYPE_MOVED: self.on_moved,
            EVENT_TYPE_CREATED: self.on_created,
            EVENT_TYPE_DELETED: self.on_deleted,
        }
        event_type = event.event_type
        with LOCK:
            _method_map[event_type](event)

    def on_created(self, event):
        LOG.debug('on_created: %s', event.src_path)
        old_playlist = playlist_object_from_db(path=event.src_path)
        if old_playlist:
            LOG.debug('Playlist already in DB - skipping')
            return
        playlist = PL.Playlist_Object()
        playlist.kodi_path = event.src_path
        playlist.kodi_hash = utils.generate_file_md5(event.src_path)
        try:
            create_plex_playlist(playlist)
        except PL.PlaylistError:
            pass

    def on_deleted(self, event):
        LOG.debug('on_deleted: %s', event.src_path)
        playlist = playlist_object_from_db(path=event.src_path)
        if not playlist:
            LOG.error('Playlist not found in DB for path %s', event.src_path)
        else:
            delete_plex_playlist(playlist)

    def on_modified(self, event):
        LOG.debug('on_modified: %s', event.src_path)
        old_playlist = playlist_object_from_db(path=event.src_path)
        new_playlist = PL.Playlist_Object()
        if old_playlist:
            # Retain the name! Might've vom from Plex
            new_playlist.plex_name = old_playlist.plex_name
        new_playlist.kodi_path = event.src_path
        new_playlist.kodi_hash = utils.generate_file_md5(event.src_path)
        try:
            if not old_playlist:
                LOG.debug('Old playlist not found, creating a new one')
                try:
                    create_plex_playlist(new_playlist)
                except PL.PlaylistError:
                    pass
            elif old_playlist.kodi_hash == new_playlist.kodi_hash:
                LOG.debug('Old and new playlist are identical - nothing to do')
            else:
                delete_plex_playlist(old_playlist)
                create_plex_playlist(new_playlist)
        except PL.PlaylistError:
            pass

    def on_moved(self, event):
        LOG.debug('on_moved: %s to %s', event.src_path, event.dest_path)
        old_playlist = playlist_object_from_db(path=event.src_path)
        if not old_playlist:
            LOG.error('Did not have source path in the DB', event.src_path)
        else:
            delete_plex_playlist(old_playlist)
        new_playlist = PL.Playlist_Object()
        new_playlist.kodi_path = event.dest_path
        new_playlist.kodi_hash = utils.generate_file_md5(event.dest_path)
        try:
            create_plex_playlist(new_playlist)
        except PL.PlaylistError:
            pass


def kodi_playlist_monitor():
    """
    Monitors the Kodi playlist folder special://profile/playlist for the user.
    Will thus catch all changes on the Kodi side of things.

    Returns an watchdog Observer instance. Be sure to use
    observer.stop() (and maybe observer.join()) to shut down properly
    """
    event_handler = PlaylistEventhandler()
    observer = Observer()
    observer.schedule(event_handler, v.PLAYLIST_PATH, recursive=True)
    observer.start()
    return observer

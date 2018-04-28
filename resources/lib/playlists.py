# -*- coding: utf-8 -*-
from logging import getLogger
import os
import sys
import re

import watchdog
import playlist_func as PL
from PlexAPI import API
import kodidb_functions as kodidb
import plexdb_functions as plexdb
import utils
import variables as v

###############################################################################

LOG = getLogger("PLEX." + __name__)

# Our PKC playlists. Keys: ID [int] of plex DB table playlists. Values:
# playlist_func.Playlist_Object()
PLAYLISTS = {}

# Which playlist formates are supported by PKC?
SUPPORTED_FILETYPES = (
    'm3u',
    'm3u8'
    # 'pls',
    # 'cue',
)

DEFAULT_ENCODING = sys.getdefaultencoding()

REGEX_PLEX_ID = re.compile(r'''plex_id=(\d+)''')


def create_plex_playlist(playlist):
    """
    Adds the playlist [Playlist_Object] to the PMS. If playlist.plex_id is
    not None the existing Plex playlist will be overwritten; otherwise a new
    playlist will be generated and stored accordingly in the playlist object.

    Will also add (or modify an existing) Plex playlist table entry.

    Returns None or raises PL.PlaylistError
    """
    LOG.info('Creating Plex playlist from Kodi file: %s', playlist.kodi_path)
    plex_ids = _playlist_file_to_plex_ids(playlist)
    for pos, plex_id in enumerate(plex_ids):
        if pos == 0:
            PL.init_Plex_playlist(playlist, plex_id=plex_id)
        else:
            PL.add_item_to_PMS_playlist(playlist, pos, plex_id=plex_id)
    update_plex_table(playlist, update_kodi_hash=True)
    LOG.info('Done creating Plex %s playlist %s',
             playlist.type, playlist.plex_name)


def delete_plex_playlist(playlist):
    """
    Removes the playlist [Playlist_Object] from the PMS. Will also delete the
    entry in the Plex playlist table.
    Returns None or raises PL.PlaylistError
    """
    LOG.info('Deleting playlist %s from the PMS', playlist.plex_name)
    try:
        PL.delete_playlist_from_pms(playlist)
    except PL.PlaylistError as err:
        LOG.error('Could not delete Plex playlist: %s', err.strerror)
    else:
        update_plex_table(playlist, delete=True)


def create_kodi_playlist(plex_id):
    """
    Creates a new Kodi playlist file. Will also add (or modify an existing) Plex
    playlist table entry.
    Assumes that the Plex playlist is indeed new. A NEW Kodi playlist will be
    created in any case (not replaced)
    Returns the playlist or raises PL.PlaylistError
    """
    LOG.info('Creating new Kodi playlist from Plex playlist %s', plex_id)
    playlist = PL.Playlist_Object()
    playlist.id = plex_id
    xml = PL.get_PMS_playlist(playlist)
    if not xml:
        LOG.error('Could not create Kodi playlist for %s', plex_id)
        return
    PL.get_playlist_details_from_xml(playlist, xml)
    if xml.get('playlistType') == 'audio':
        playlist.type = 'music'
    elif xml.get('playlistType') == 'video':
        playlist.type = 'video'
    else:
        raise RuntimeError('Plex playlist type unknown: %s'
                           % xml.get('playlistType'))
    playlist.plex_name = xml.get('title')
    name = utils.slugify(playlist.plex_name)
    playlist.kodi_path = os.join(v.PLAYLIST_PATH,
                                 playlist.type,
                                 '%s.m3u8' % name)
    # Derive filename close to Plex playlist name
    _write_playlist_to_file(playlist, xml)
    update_plex_table(playlist, update_kodi_hash=True)
    LOG.info('Created Kodi playlist %s based on Plex playlist %s',
             playlist.kodi_filename, playlist.plex_name)


def delete_kodi_playlist(playlist):
    """
    Removes the corresponding Kodi file for playlist [Playlist_Object] from
    disk. Be sure that playlist.kodi_path is set. Will also delete the entry in
    the Plex playlist table.
    Returns None or raises PL.PlaylistError
    """
    try:
        os.remove(playlist.kodi_path)
    except OSError as err:
        LOG.error('Could not delete Kodi playlist file %s. Error:\n %s: %s',
                  playlist.kodi_path, err.errno, err.strerror)
    else:
        update_plex_table(playlist, delete=True)


def update_plex_table(playlist, delete=False, new_path=None,
                      update_kodi_hash=False):
    """
    Assumes that all sync operations are over. Takes playlist [Playlist_Object]
    and creates/updates the corresponding Plex playlists table entry

    Pass delete=True to delete the playlist entry
    """
    if delete:
        with plexdb.Get_Plex_DB() as plex_db:
            plex_db.delete_playlist_entry(playlist)
        return
    if update_kodi_hash:
        playlist.kodi_hash = utils.generate_file_md5(playlist.kodi_path)
    with plexdb.Get_Plex_DB() as plex_db:
        plex_db.insert_playlist_entry(playlist)


def _playlist_file_to_plex_ids(playlist):
    """
    Takes the playlist file located at path [unicode] and parses it.
    Returns a list of plex_ids (str) or raises PL.PlaylistError if a single
    item cannot be parsed from Kodi to Plex.
    """
    if playlist.kodi_extension in ('m3u', 'm3u8'):
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
    Adapter to process *.m3u playlist files. Encoding is not uniform except for
    m3u8 files!
    """
    plex_ids = set()
    with open(playlist.kodi_path, 'rb') as f:
        text = f.read()
    if playlist.kodi_extension == 'm3u8':
        encoding = 'utf-8'
    elif v.PLATFORM == 'Windows':
        encoding = 'mbcs'
    else:
        encoding = DEFAULT_ENCODING
    try:
        text = text.decode(encoding)
    except UnicodeDecodeError:
        LOG.warning('Fallback to ISO-8859-1 decoding for %s',
                    playlist.kodi_path)
        text = text.decode('ISO-8859-1')
    for entry in _m3u_iterator(text):
        plex_id = REGEX_PLEX_ID.search(entry)
        if plex_id:
            plex_id = plex_id.group(1)
            plex_ids.append(plex_id)
        else:
            # Add-on paths not working, try direct
            kodi_id, kodi_type = kodidb.kodiid_from_filename(
                playlist.kodi_path, db_type=playlist.type)
            if not kodi_id:
                continue
            with plexdb.Get_Plex_DB() as plex_db:
                plex_id = plex_db.getItem_byKodiId(kodi_id, kodi_type)
            if plex_id:
                plex_ids.append(plex_id)
    return plex_ids


def _write_playlist_to_file(playlist, xml):
    """
    Feed with playlist [Playlist_Object]. Will write the playlist to a m3u8 file
    Returns None or raises PL.PlaylistError
    """
    text = u'#EXTCPlayListM3U::M3U\n'
    for element in xml:
        api = API(element)
        text += (u'#EXTINF:%s,%s\n%s\n'
                 % (api.runtime(), api.title(), api.path()))
    text += '\n'
    text = text.encode('utf-8')
    with open(playlist.kodi_path, 'wb') as f:
        f.write(text)


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


def playlist_object_from_db(path=None):
    """
    Returns the playlist as a Playlist_Object for path [unicode] from the Plex
    playlists table or None if not found.
    """
    playlist = PL.Playlist_Object()
    return playlist


def full_sync():
    """
    Full sync of playlists between Kodi and Plex. Returns True is successful,
    False otherwise
    """
    xml = PL.get_all_playlists()
    if not xml:
        return False
    for entry in xml:


class PlaylistEventhandler(watchdog.events.FileSystemEventHandler):
    """
    PKC eventhandler to monitor Kodi playlists safed to disk
    """
    @staticmethod
    def _event_relevant(event):
        """
        Returns True if the event is relevant for PKC, False otherwise (e.g.
        when a smart playlist *.xsp is considered)
        """
        LOG.debug('event.is_directory: %s, event.src_path: %s',
                  event.is_directory, event.src_path)
        if event.is_directory:
            # todo: take care of folder renames
            return False
        try:
            _, extension = event.src_path.rsplit('.', 1)
        except ValueError:
            return False
        if extension.lower() not in SUPPORTED_FILETYPES:
            return False
        if event.src_path.startswith(v.PLAYLIST_PATH_MIXED):
            return False
        return True

    def on_created(self, event):
        if not self._event_relevant(event):
            return
        LOG.debug('on_created: %s', event.src_path)
        playlist = PL.Playlist_Object()
        playlist.kodi_path = event.src_path
        create_plex_playlist(playlist)

    def on_deleted(self, event):
        if not self._event_relevant(event):
            return
        LOG.debug('on_deleted: %s', event.src_path)
        playlist = PL.Playlist_Object()
        playlist.kodi_path = event.src_path
        delete_plex_playlist(playlist)

    def on_modified(self, event):
        if not self._event_relevant(event):
            return
        LOG.debug('on_modified: %s', event.src_path)
        playlist = PL.Playlist_Object()
        playlist.kodi_path = event.src_path
        delete_plex_playlist(playlist)
        create_plex_playlist(playlist)

    def on_moved(self, event):
        if not self._event_relevant(event):
            return
        LOG.debug('on_moved: %s to %s', event.src_path, event.dest_path)
        playlist = PL.Playlist_Object()
        playlist.id = plex_id_from_playlist_path(event.src_path)
        if not playlist.id:
            return
        playlist.kodi_path = event.dest_path
        change_plex_playlist_name(playlist, playlist.kodi_filename)
        update_plex_table(playlist)


def kodi_playlist_monitor():
    """
    Monitors the Kodi playlist folder special://profile/playlist for the user.
    Will thus catch all changes on the Kodi side of things.

    Returns an watchdog Observer instance. Be sure to use
    observer.stop() (and maybe observer.join()) to shut down properly
    """
    event_handler = PlaylistEventhandler()
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, v.PLAYLIST_PATH, recursive=True)
    observer.start()
    return observer

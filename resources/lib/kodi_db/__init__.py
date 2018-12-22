#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .video import KodiVideoDB
from .music import KodiMusicDB
from .texture import KodiTextureDB

from .. import path_ops, utils, timing, variables as v

LOG = getLogger('PLEX.kodi_db')


def kodiid_from_filename(path, kodi_type=None, db_type=None):
    """
    Returns kodi_id if we have an item in the Kodi video or audio database with
    said path. Feed with either koditype, e.v. 'movie', 'song' or the DB
    you want to poll ('video' or 'music')
    Returns None, <kodi_type> if not possible
    """
    kodi_id = None
    path = utils.try_decode(path)
    try:
        filename = path.rsplit('/', 1)[1]
        path = path.rsplit('/', 1)[0] + '/'
    except IndexError:
        filename = path.rsplit('\\', 1)[1]
        path = path.rsplit('\\', 1)[0] + '\\'
    if kodi_type == v.KODI_TYPE_SONG or db_type == 'music':
        with KodiMusicDB() as kodidb:
            try:
                kodi_id = kodidb.song_id_from_filename(filename, path)
            except TypeError:
                LOG.debug('No Kodi audio db element found for path %s', path)
            else:
                kodi_type = v.KODI_TYPE_SONG
    else:
        with KodiVideoDB() as kodidb:
            try:
                kodi_id, kodi_type = kodidb.video_id_from_filename(filename,
                                                                   path)
            except TypeError:
                LOG.debug('No kodi video db element found for path %s file %s',
                          path, filename)
    return kodi_id, kodi_type


def setup_kodi_default_entries():
    """
    Makes sure that we retain the Kodi standard databases. E.g. that there
    is a dummy artist with ID 1
    """
    if utils.settings('enableMusic') == 'true':
        with KodiMusicDB() as kodidb:
            kodidb.cursor.execute('''
                INSERT OR REPLACE INTO artist(
                    idArtist,
                    strArtist,
                    strMusicBrainzArtistID)
                VALUES (?, ?, ?)
            ''', (1, '[Missing Tag]', 'Artist Tag Missing'))
            kodidb.cursor.execute('''
                INSERT OR REPLACE INTO role(
                    idRole,
                    strRole)
                VALUES (?, ?)
            ''', (1, 'Artist'))
            if v.KODIVERSION >= 18:
                kodidb.cursor.execute('DELETE FROM versiontagscan')
                kodidb.cursor.execute('''
                    INSERT INTO versiontagscan(
                        idVersion,
                        iNeedsScan,
                        lastscanned)
                    VALUES (?, ?, ?)
                ''', (v.DB_MUSIC_VERSION[v.KODIVERSION],
                      0,
                      timing.kodi_now()))


def reset_cached_images():
    LOG.info('Resetting cached artwork')
    # Remove all existing textures first
    path = path_ops.translate_path('special://thumbnails/')
    if path_ops.exists(path):
        path_ops.rmtree(path, ignore_errors=True)
        paths = ('', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                 'a', 'b', 'c', 'd', 'e', 'f',
                 'Video', 'plex')
        for path in paths:
            new_path = path_ops.translate_path('special://thumbnails/%s' % path)
            try:
                path_ops.makedirs(path_ops.encode_path(new_path))
            except OSError:
                pass
    with KodiTextureDB() as kodidb:
        for row in kodidb.cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type=?',
                                         ('table', )):
            if row[0] != 'version':
                kodidb.cursor.execute("DELETE FROM %s" % row[0])


def wipe_dbs(music=True):
    """
    Completely resets the Kodi databases 'video', 'texture' and 'music' (if
    music sync is enabled)

    DO NOT use context menu as we need to connect without WAL mode - if Kodi
    is still accessing the DB
    """
    from sqlite3 import connect
    LOG.warn('Wiping Kodi databases!')
    kinds = [v.DB_VIDEO_PATH, v.DB_TEXTURE_PATH]
    if music:
        kinds.append(v.DB_MUSIC_PATH)
    for path in kinds:
        conn = connect(path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = cursor.fetchall()
        tables = [i[0] for i in tables]
        if 'version' in tables:
            tables.remove('version')
        if 'versiontagscan' in tables:
            tables.remove('versiontagscan')
        for table in tables:
            cursor.execute('DELETE FROM %s' % table)
        conn.commit()
        conn.close()
    setup_kodi_default_entries()
    # Delete SQLITE wal files
    import xbmc
    # Make sure Kodi knows we wiped the databases
    xbmc.executebuiltin('UpdateLibrary(video)')
    if utils.settings('enableMusic') == 'true':
        xbmc.executebuiltin('UpdateLibrary(music)')


KODIDB_FROM_PLEXTYPE = {
    v.PLEX_TYPE_MOVIE: KodiVideoDB,
    v.PLEX_TYPE_SHOW: KodiVideoDB,
    v.PLEX_TYPE_SEASON: KodiVideoDB,
    v.PLEX_TYPE_EPISODE: KodiVideoDB,
    v.PLEX_TYPE_ARTIST: KodiMusicDB,
    v.PLEX_TYPE_ALBUM: KodiMusicDB,
    v.PLEX_TYPE_SONG: KodiMusicDB
}

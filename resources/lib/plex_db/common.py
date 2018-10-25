#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from .. import utils, variables as v

SUPPORTED_KODI_TYPES = (
    v.KODI_TYPE_MOVIE,
    v.KODI_TYPE_SHOW,
    v.KODI_TYPE_SEASON,
    v.KODI_TYPE_EPISODE,
    v.KODI_TYPE_ARTIST,
    v.KODI_TYPE_ALBUM,
    v.KODI_TYPE_SONG)


class PlexDBBase(object):
    """
    Plex database methods used for all types of items
    """
    def __init__(self, cursor=None):
        # Allows us to use this class with a cursor instead of context mgr
        self.cursor = cursor

    def __enter__(self):
        self.plexconn = utils.kodi_sql('plex')
        self.cursor = self.plexconn.cursor()
        return self

    def __exit__(self, e_typ, e_val, trcbak):
        self.plexconn.commit()
        self.plexconn.close()

    def is_recorded(self, plex_id, plex_type):
        """
        FAST method to check whether a plex_id has already been recorded
        """
        query = 'SELECT plex_id FROM %s WHERE plex_id = ?' % plex_type
        self.cursor.execute(query, (plex_id, ))
        return self.cursor.fetchone() is not None

    def item_by_id(self, plex_id, plex_type=None):
        """
        Returns the item for plex_id or None.
        Supply with the correct plex_type to speed up lookup
        """
        answ = None
        if plex_type == v.PLEX_TYPE_MOVIE:
            entry = self.movie(plex_id)
            if entry:
                answ = self.entry_to_movie(entry)
        elif plex_type == v.PLEX_TYPE_EPISODE:
            entry = self.episode(plex_id)
            if entry:
                answ = self.entry_to_episode(entry)
        elif plex_type == v.PLEX_TYPE_SHOW:
            entry = self.show(plex_id)
            if entry:
                answ = self.entry_to_show(entry)
        elif plex_type == v.PLEX_TYPE_SEASON:
            entry = self.season(plex_id)
            if entry:
                answ = self.entry_to_season(entry)
        else:
            # SLOW - lookup plex_id in all our tables
            for kind in (v.PLEX_TYPE_MOVIE,
                         v.PLEX_TYPE_SHOW,
                         v.PLEX_TYPE_EPISODE,
                         v.PLEX_TYPE_SEASON):
                method = getattr(self, kind)
                entry = method(plex_id)
                if entry:
                    method = getattr(self, 'entry_to_%s' % kind)
                    answ = method(entry)
                    break
        return answ

    def item_by_kodi_id(self, kodi_id, kodi_type):
        """
        """
        if kodi_type not in SUPPORTED_KODI_TYPES:
            return
        query = ('SELECT * from %s WHERE kodi_id = ? LIMIT 1'
                 % v.PLEX_TYPE_FROM_KODI_TYPE[kodi_type])
        self.cursor.execute(query, (kodi_id, ))
        method = getattr(self, 'entry_to_%s' % v.PLEX_TYPE_FROM_KODI_TYPE[kodi_type])
        return method(self.cursor.fetchone())

    def plex_id_by_last_sync(self, plex_type, last_sync):
        """
        Returns an iterator for all items where the last_sync is NOT identical
        """
        query = 'SELECT plex_id FROM %s WHERE last_sync <> ?' % plex_type
        self.cursor.execute(query, (last_sync, ))
        return (x[0] for x in self.cursor)

    def update_last_sync(self, plex_type, plex_id, last_sync):
        """
        Sets a new timestamp for plex_id
        """
        query = 'UPDATE %s SET last_sync = ? WHERE plex_id = ?' % plex_type
        self.cursor.execute(query, (last_sync, plex_id))

    def remove(self, plex_id, plex_type):
        """
        Removes the item from our Plex db
        """
        query = 'DELETE FROM ? WHERE plex_id = ?' % plex_type
        self.cursor.execute(query, (plex_id, ))

    def fanart(self, plex_type):
        """
        Returns an iterator for plex_type for all plex_id, where fanart_synced
        has not yet been set to 1
        """
        query = 'SELECT plex_id from %s WHERE fanart_synced = 0' % plex_type
        self.cursor.execute(query)
        return (x[0] for x in self.cursor)

    def set_fanart_synced(self, plex_id, plex_type):
        """
        Toggles fanart_synced to 1 for plex_id
        """
        query = 'UPDATE %s SET fanart_synced = 1 WHERE plex_id = ?' % plex_type
        self.cursor.execute(query, (plex_id, ))


def initialize():
        """
        Run once upon PKC startup to verify that plex db exists.
        """
        with PlexDBBase() as plexdb:
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS version(
                    idVersion TEXT)
            ''')
            plexdb.cursor.execute('''
                INSERT OR REPLACE INTO version(idVersion)
                VALUES (?)
            ''', (v.ADDON_VERSION, ))
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sections(
                    section_id INTEGER PRIMARY KEY,
                    section_name TEXT,
                    plex_type TEXT,
                    kodi_tagid INTEGER,
                    sync_to_kodi INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS movie(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS show(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS season(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS episode(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,
                    grandparent_id INTEGER,
                    season_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS artist(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS album(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS track(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,
                    grandparent_id INTEGER,
                    album_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    kodi_pathid INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists(
                    plex_id INTEGER PRIMARY KEY,
                    plex_name TEXT,
                    plex_updatedat INTEGER,
                    kodi_path TEXT,
                    kodi_type TEXT,
                    kodi_hash TEXT)
            ''')


def wipe():
    """
    Completely resets the Plex database
    """
    query = "SELECT name FROM sqlite_master WHERE type = 'table'"
    with PlexDBBase() as plexdb:
        plexdb.cursor.execute(query)
        tables = plexdb.cursor.fetchall()
        tables = [i[0] for i in tables]
        for table in tables:
            delete_query = 'DROP table IF EXISTS %s' % table
            plexdb.cursor.execute(delete_query)

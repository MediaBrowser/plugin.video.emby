#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from . import utils


class PlexDBBase(object):
    """
    Methods used for all types of items
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

    def section_ids(self):
        """
        Returns an iterator for section Plex ids for all sections
        """
        self.cursor.execute('SELECT section_id FROM sections')
        return (x[0] for x in self.cursor)

    def section_infos(self):
        """
        Returns an iterator for dicts for all Plex libraries:
        {
            'section_id'
            'section_name'
            'plex_type'
            'kodi_tagid'
            'sync_to_kodi'
        }
        """
        self.cursor.execute('SELECT * FROM sections')
        return ({'section_id': x[0],
                 'section_name': x[1],
                 'plex_type': x[2],
                 'kodi_tagid': x[3],
                 'sync_to_kodi': x[4]} for x in self.cursor)

    def section(self, section_id):
        """
        For section_id, returns the tuple (or None)
            section_id INTEGER PRIMARY KEY,
            section_name TEXT,
            plex_type TEXT,
            kodi_tagid INTEGER,
            sync_to_kodi INTEGER
        """
        self.cursor.execute('SELECT * FROM sections WHERE section_id = ? LIMIT 1',
                            (section_id, ))
        return self.cursor.fetchone()

    def section_id_by_name(self, section_name):
        """
        Returns the section_id for section_name (or None)
        """
        self.cursor.execute('SELECT section_id FROM sections WHERE section_name = ? LIMIT 1,'
                            (section_name, ))
        try:
            return self.cursor.fetchone()[0]
        except TypeError:
            pass

    def add_section(self, section_id, section_name, plex_type, kodi_tagid,
                    sync_to_kodi=True):
        """
        Appends a Plex section to the Plex sections table
        sync=False: Plex library won't be synced to Kodi
        """
        query = '''
            INSERT OR REPLACE INTO sections(
                section_id, section_name, plex_type, kodi_tagid, sync_to_kodi)
            VALUES (?, ?, ?, ?, ?)
            '''
        self.cursor.execute(query,
                            (section_id,
                             section_name,
                             plex_type,
                             kodi_tagid,
                             sync_to_kodi))

    def remove_section(self, section_id):
        """
        Removes the Plex db entry for the section with section_id
        """
        self.cursor.execute('DELETE FROM sections WHERE section_id = ?',
                            (section_id, ))

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


def initialize():
        """
        Run once during startup to verify that plex db exists.
        """
        with PlexDBBase() as plex_db:
            # Create the tables for the plex database
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sections(
                    section_id INTEGER PRIMARY KEY,
                    section_name TEXT,
                    plex_type TEXT,
                    kodi_tagid INTEGER,
                    sync_to_kodi INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS movie(
                    plex_id INTEGER PRIMARY KEY ASC,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS show(
                    plex_id INTEGER PRIMARY KEY ASC,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS season(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,  # plex_id of the parent show
                    parent_id INTEGER,  # kodi_id of the parent show
                    kodi_id INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS episode(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,  # plex_id of the parent show
                    grandparent_id INTEGER,  # kodi_id of the parent show
                    season_id INTEGER,  # plex_id of the parent season
                    parent_id INTEGER,  # kodi_id of the parent season
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS artist(
                    plex_id INTEGER PRIMARY KEY ASC,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS album(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,  # plex_id of the parent artist
                    parent_id INTEGER,  # kodi_id of the parent artist
                    kodi_id INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS track(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,  # plex_id of the parent artist
                    grandparent_id INTEGER,  # kodi_id of the parent artist
                    album_id INTEGER,  # plex_id of the parent album
                    parent_id INTEGER,  # kodi_id of the parent album
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plex_db.cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists(
                    plex_id INTEGER PRIMARY KEY ASC,
                    plex_name TEXT,
                    plex_updatedat INTEGER,
                    kodi_path TEXT,
                    kodi_type TEXT,
                    kodi_hash TEXT)
            ''')
        # Create an index for actors to speed up sync
        utils.create_actor_db_index()


def wipe():
    """
    Completely resets the Plex database
    """
    query = "SELECT name FROM sqlite_master WHERE type = 'table'"
    with PlexDBBase() as plex_db:
        plex_db.cursor.execute(query)
        tables = plex_db.cursor.fetchall()
        tables = [i[0] for i in tables]
        for table in tables:
            delete_query = 'DELETE FROM %s' % table
            plex_db.cursor.execute(delete_query)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from . import common
from .. import variables as v

###############################################################################


class PlexDB(common.PlexDB):
    def add_reference(self, plex_type=None, plex_id=None, checksum=None,
                      section_id=None, show_id=None, grandparent_id=None,
                      season_id=None, parent_id=None, kodi_id=None,
                      kodi_fileid=None, kodi_pathid=None, last_sync=None):
        """
        Appends or replaces an entry into the plex table
        """
        if plex_type == v.PLEX_TYPE_EPISODE:
            query = '''
                INSERT OR REPLACE INTO episode(
                    plex_id, checksum, section_id, show_id, grandparent_id,
                    season_id, parent_id, kodi_id, kodi_fileid, kodi_pathid,
                    fanart_synced, last_sync)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            self.plexcursor.execute(
                query,
                (plex_id, checksum, section_id, show_id, grandparent_id,
                 season_id, parent_id, kodi_id, kodi_fileid, kodi_pathid,
                 0, last_sync))
        elif plex_type == v.PLEX_TYPE_SEASON:
            query = '''
                INSERT OR REPLACE INTO season(
                    plex_id, checksum, section_id, show_id, parent_id,
                    kodi_id, fanart_synced, last_sync)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            self.plexcursor.execute(
                query,
                (plex_id, checksum, section_id, show_id, parent_id,
                 kodi_id, 0, last_sync))
        elif plex_type == v.PLEX_TYPE_SHOW:
            query = '''
                INSERT OR REPLACE INTO show(
                    plex_id, checksum, section_id, kodi_id, kodi_pathid,
                    fanart_synced, last_sync)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            self.plexcursor.execute(
                query,
                (plex_id, checksum, section_id, kodi_id, kodi_pathid, 0,
                 last_sync))

    def show(self, plex_id):
        """
        Returns the show info as a tuple for the TV show with plex_id:
            plex_id INTEGER PRIMARY KEY ASC,
            checksum INTEGER UNIQUE,
            section_id INTEGER,
            kodi_id INTEGER,
            kodi_pathid INTEGER,
            fanart_synced INTEGER,
            last_sync INTEGER
        """
        self.cursor.execute('SELECT * FROM show WHERE plex_id = ?',
                            (plex_id, ))
        return self.cursor.fetchone()

    def season(self, plex_id):
        """
        Returns the show info as a tuple for the TV show with plex_id:
            plex_id INTEGER PRIMARY KEY,
            checksum INTEGER UNIQUE,
            section_id INTEGER,
            show_id INTEGER,  # plex_id of the parent show
            parent_id INTEGER,  # kodi_id of the parent show
            kodi_id INTEGER,
            fanart_synced INTEGER,
            last_sync INTEGER
        """
        self.cursor.execute('SELECT * FROM season WHERE plex_id = ?',
                            (plex_id, ))
        return self.cursor.fetchone()

    def episode(self, plex_id):
        """
        Returns the show info as a tuple for the TV show with plex_id:
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
            last_sync INTEGER
        """
        self.cursor.execute('SELECT * FROM episode WHERE plex_id = ?',
                            (plex_id, ))
        return self.cursor.fetchone()

    def plex_id_by_last_sync(self, plex_type, last_sync):
        """
        Returns an iterator for all items where the last_sync is NOT identical
        """
        self.cursor.execute('SELECT plex_id FROM ? WHERE last_sync <> ?',
                            (plex_type, last_sync, ))
        return (x[0] for x in self.cursor)

    def shows_plex_id_section_id(self):
        """
        Iterator for tuples (plex_id, section_id) of all our TV shows
        """
        self.cursor.execute('SELECT plex_id, section_id FROM show')
        return self.cursor

    def update_last_sync(self, plex_type, plex_id, last_sync):
        """
        Sets a new timestamp for plex_id
        """

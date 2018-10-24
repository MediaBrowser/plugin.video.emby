#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals


class TVShows(object):
    def add_show(self, plex_id=None, checksum=None, section_id=None,
                 kodi_id=None, kodi_pathid=None, last_sync=None):
        """
        Appends or replaces tv show entry into the plex table
        """
        query = '''
            INSERT OR REPLACE INTO show(
                plex_id
                checksum
                section_id
                kodi_id
                kodi_pathid
                fanart_synced
                last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        self.plexcursor.execute(
            query,
            (plex_id, checksum, section_id, kodi_id, kodi_pathid, 0,
             last_sync))

    def add_season(self, plex_id=None, checksum=None, section_id=None,
                   show_id=None, parent_id=None, kodi_id=None, last_sync=None):
        """
        Appends or replaces an entry into the plex table
        """
        query = '''
            INSERT OR REPLACE INTO season(
                plex_id
                checksum
                section_id
                show_id
                parent_id
                kodi_id
                fanart_synced
                last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        self.plexcursor.execute(
            query,
            (plex_id, checksum, section_id, show_id, parent_id,
             kodi_id, 0, last_sync))

    def add_episode(self, plex_id=None, checksum=None, section_id=None,
                    show_id=None, grandparent_id=None, season_id=None,
                    parent_id=None, kodi_id=None, kodi_fileid=None,
                    kodi_pathid=None, last_sync=None):
        """
        Appends or replaces an entry into the plex table
        """
        query = '''
            INSERT OR REPLACE INTO episode(
                plex_id
                checksum
                section_id
                show_id
                grandparent_id
                season_id
                parent_id
                kodi_id
                kodi_fileid
                kodi_pathid
                fanart_synced
                last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        self.plexcursor.execute(
            query,
            (plex_id, checksum, section_id, show_id, grandparent_id,
             season_id, parent_id, kodi_id, kodi_fileid, kodi_pathid,
             0, last_sync))

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
        self.cursor.execute('SELECT * FROM show WHERE plex_id = ? LIMIT 1',
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
        self.cursor.execute('SELECT * FROM season WHERE plex_id = ? LIMIT 1',
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
        self.cursor.execute('SELECT * FROM episode WHERE plex_id = ? LIMIT 1',
                            (plex_id, ))
        return self.cursor.fetchone()

    def season_has_episodes(self, plex_id):
        """
        Returns True if there are episodes left for the season with plex_id
        """
        self.cursor.execute('SELECT plex_id FROM episode WHERE season_id = ? LIMIT 1',
                            (plex_id, ))
        return self.cursor.fetchone() is not None

    def show_has_seasons(self, plex_id):
        """
        Returns True if there are seasons left for the show with plex_id
        """
        self.cursor.execute('SELECT plex_id FROM season WHERE show_id = ? LIMIT 1',
                            (plex_id, ))
        return self.cursor.fetchone() is not None

    def show_has_episodes(self, plex_id):
        """
        Returns True if there are episodes left for the show with plex_id
        """
        self.cursor.execute('SELECT plex_id FROM episode WHERE show_id = ? LIMIT 1',
                            (plex_id, ))
        return self.cursor.fetchone() is not None

    def episode_by_season(self, plex_id):
        """
        Returns an iterator for all episodes that have a parent season_id with
        a value of plex_id
        """
        self.cursor.execute('SELECT * FROM episode WHERE season_id = ?',
                            (plex_id, ))
        return (self.entry_to_episode(x) for x in self.cursor)

    def episode_by_show(self, plex_id):
        """
        Returns an iterator for all episodes that have a grandparent show_id
        with a value of plex_id
        """
        self.cursor.execute('SELECT * FROM episode WHERE show_id = ?',
                            (plex_id, ))
        return (self.entry_to_episode(x) for x in self.cursor)

    def season_by_show(self, plex_id):
        """
        Returns an iterator for all seasons that have a parent show_id
        with a value of plex_id
        """
        self.cursor.execute('SELECT * FROM season WHERE show_id = ?',
                            (plex_id, ))
        return (self.entry_to_season(x) for x in self.cursor)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals


class Movies(object):
    def add_movie(self, plex_id=None, checksum=None, section_id=None,
                  kodi_id=None, kodi_fileid=None, kodi_pathid=None,
                  last_sync=None):
        """
        Appends or replaces an entry into the plex table for movies
        """
        query = '''
            INSERT OR REPLACE INTO movie(
                plex_id,
                checksum,
                section_id,
                kodi_id,
                kodi_fileid,
                kodi_pathid,
                fanart_synced,
                last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
        self.plexcursor.execute(
            query,
            (plex_id,
             checksum,
             section_id,
             kodi_id,
             kodi_fileid,
             kodi_pathid,
             0,
             last_sync))

    def movie(self, plex_id):
        """
        Returns the show info as a tuple for the TV show with plex_id:
            plex_id INTEGER PRIMARY KEY ASC,
            checksum INTEGER UNIQUE,
            section_id INTEGER,
            kodi_id INTEGER,
            kodi_fileid INTEGER,
            kodi_pathid INTEGER,
            fanart_synced INTEGER,
            last_sync INTEGER
        """
        self.cursor.execute('SELECT * FROM movie WHERE plex_id = ?',
                            (plex_id, ))
        return self.cursor.fetchone()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals


class PlexDB(object):
    """
    Methods used for all types of items
    """
    def __init__(self, cursor):
        self.cursor = cursor

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

    def section_by_id(self, section_id):
        """
        For section_id, returns tuple (or None)
            (section_id,
             section_name,
             plex_type,
             kodi_tagid,
             sync_to_kodi)
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
            INSERT INTO sections(
                section_id, section_name, plex_type, kodi_tagid, sync_to_kodi)
            VALUES (?, ?, ?, ?, ?)
            '''
        self.cursor.execute(query,
                            (section_id,
                             section_name,
                             plex_type,
                             kodi_tagid,
                             sync_to_kodi))

    def update_section(self, section_name, kodi_tagid, section_id):
        """
        Updates the section_id with section_name and kodi_tagid
        """
        query = '''
            UPDATE sections
            SET section_name = ?, kodi_tagid = ?
            WHERE section_id = ?
        '''
        self.cursor.execute(query, (section_name, kodi_tagid, section_id))

    def remove_section(self, section_id):
        """
        Removes the Plex db entry for the section with section_id
        """
        self.cursor.execute('DELETE FROM sections WHERE section_id = ?',
                            (section_id, ))

    def item_by_id(self, plex_id):
        """
        For plex_id, returns the tuple
          (kodi_id, kodi_fileid, kodi_pathid, parent_id, kodi_type, plex_type)

        None if not found
        """
        query = '''
            SELECT kodi_id, kodi_fileid, kodi_pathid, parent_id, kodi_type,
                   plex_type
            FROM plex WHERE plex_id = ?
            LIMIT 1
        '''
        self.cursor.execute(query, (plex_id,))
        return self.cursor.fetchone()

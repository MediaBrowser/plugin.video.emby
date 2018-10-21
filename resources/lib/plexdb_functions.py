#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from . import utils
from . import variables as v

###############################################################################


class Get_Plex_DB():
    """
    Usage: with Get_Plex_DB() as plex_db:
               plex_db.do_something()

    On exiting "with" (no matter what), commits get automatically committed
    and the db gets closed
    """
    def __enter__(self):
        self.plexconn = utils.kodi_sql('plex')
        return Plex_DB_Functions(self.plexconn.cursor())

    def __exit__(self, type, value, traceback):
        self.plexconn.commit()
        self.plexconn.close()


class Plex_DB_Functions():

    def __init__(self, plexcursor):
        self.plexcursor = plexcursor

    def sections(self):
        """
        Returns a list of section Plex ids for all sections
        """
        self.plexcursor.execute('SELECT section_id FROM sections')
        return [x[0] for x in self.plexcursor]

    def list_section_info(self):
        """
        Returns a list of dicts for all Plex libraries:
        {
            'section_id'
            'section_name'
            'plex_type'
            'kodi_tagid'
            'sync_to_kodi'
        }
        """
        self.plexcursor.execute('SELECT * FROM sections')
        return [{'section_id': x[0],
                 'section_name': x[1],
                 'plex_type': x[2],
                 'kodi_tagid': x[3],
                 'sync_to_kodi': x[4]} for x in self.plexcursor]

    def section_by_id(self, section_id):
        """
        Returns tuple (section_id, section_name, plex_type, kodi_tagid,
        sync_to_kodi) for section_id
        """
        self.plexcursor.execute('SELECT * FROM sections WHERE section_id = ? LIMIT 1',
                                (section_id, ))
        return self.plexcursor.fetchone()

    def section_id_by_name(self, section_name):
        """
        Returns the section_id for section_name (or None)
        """
        query = '''
            SELECT section_id FROM sections
            WHERE section_name = ?
            LIMIT 1
        '''
        self.plexcursor.execute(query, (section_name,))
        try:
            section = self.plexcursor.fetchone()[0]
        except TypeError:
            section = None
        return section

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
        self.plexcursor.execute(query,
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
        self.plexcursor.execute(query, (section_name, kodi_tagid, section_id))

    def remove_section(self, section_id):
        self.plexcursor.execute('DELETE FROM sections WHERE section_id = ?',
                                (section_id, ))

    def plexid_by_section(self, section_id):
        """
        Returns an iterator for the plex_id for section_id
        """
        self.plexcursor.execute('SELECT plex_id FROM plex WHERE section_id = ?',
                                (section_id, ))
        return (x[0] for x in self.plexcursor)

    def getItem_byId(self, plex_id):
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
        self.plexcursor.execute(query, (plex_id,))
        return self.plexcursor.fetchone()

    def getItem_byWildId(self, plex_id):
        """
        Returns a list of tuples (kodi_id, kodi_type) for plex_id (% appended)
        """
        query = '''
            SELECT kodi_id, kodi_type
            FROM plex
            WHERE plex_id LIKE ?
        '''
        self.plexcursor.execute(query, (plex_id + "%",))
        return self.plexcursor.fetchall()

    def kodi_id_by_section(self, section_id):
        """
        Returns an iterator! Returns kodi_id for section_id
        """
        self.plexcursor.execute('SELECT kodi_id FROM plex WHERE section_id = ?',
                                (section_id, ))
        return self.plexcursor

    def getItem_byKodiId(self, kodi_id, kodi_type):
        """
        Returns the tuple (plex_id, parent_id, plex_type) for kodi_id and
        kodi_type
        """
        query = '''
            SELECT plex_id, parent_id, plex_type
            FROM plex
            WHERE kodi_id = ? AND kodi_type = ?
            LIMIT 1
        '''
        self.plexcursor.execute(query, (kodi_id, kodi_type,))
        return self.plexcursor.fetchone()

    def getItem_byParentId(self, parent_id, kodi_type):
        """
        Returns a list of tuples (plex_id, kodi_id, kodi_fileid) for parent_id,
        kodi_type
        """
        query = '''
            SELECT plex_id, kodi_id, kodi_fileid
            FROM plex
            WHERE parent_id = ? AND kodi_type = ?
        '''
        self.plexcursor.execute(query, (parent_id, kodi_type,))
        return self.plexcursor.fetchall()

    def getItemId_byParentId(self, parent_id, kodi_type):
        """
        Returns the tuple (plex_id, kodi_id) for parent_id, kodi_type
        """
        query = '''
            SELECT plex_id, kodi_id
            FROM plex
            WHERE parent_id = ?
            AND kodi_type = ?
        '''
        self.plexcursor.execute(query, (parent_id, kodi_type,))
        return self.plexcursor.fetchall()

    def check_plexid(self, plex_id):
        """
        FAST method to check whether plex_id has already been safed in db.
        Returns None if not yet in plex DB
        """
        self.plexcursor.execute('SELECT plex_id FROM plex WHERE plex_id = ? LIMIT 1',
                                (plex_id, ))
        return self.plexcursor.fetchone()

    def check_checksum(self, checksum):
        """
        FAST method to check whether checksum has already been safed in db.
        Returns None if not yet in plex DB
        """
        self.plexcursor.execute('SELECT checksum FROM plex WHERE checksum = ? LIMIT 1',
                                (checksum, ))
        return self.plexcursor.fetchone()

    def update_last_sync(self, plex_id, last_sync):
        """
        Fast method that updates Plex table with last_sync (an int) for plex_id
        """
        self.plexcursor.execute('UPDATE plex SET last_sync = ? WHERE plex_id = ?',
                                (last_sync, plex_id, ))

    def checksum(self, plex_type):
        """
        Returns a list of tuples (plex_id, checksum) for plex_type
        """
        query = '''
            SELECT plex_id, checksum
            FROM plex
            WHERE plex_type = ?
        '''
        self.plexcursor.execute(query, (plex_type,))
        return self.plexcursor.fetchall()

    def addReference(self, plex_id, plex_type, kodi_id, kodi_type,
                     kodi_fileid=None, kodi_pathid=None, parent_id=None,
                     checksum=None, section_id=None, last_sync=None):
        """
        Appends or replaces an entry into the plex table
        """
        query = '''
            INSERT OR REPLACE INTO plex(
                plex_id, kodi_id, kodi_fileid, kodi_pathid, plex_type,
                kodi_type, parent_id, checksum, section_id, fanart_synced,
                last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        self.plexcursor.execute(query, (plex_id, kodi_id, kodi_fileid,
                                        kodi_pathid, plex_type, kodi_type,
                                        parent_id, checksum, section_id, 0,
                                        last_sync))

    def updateReference(self, plex_id, checksum):
        """
        Updates checksum for plex_id
        """
        query = "UPDATE plex SET checksum = ? WHERE plex_id = ?"
        self.plexcursor.execute(query, (checksum, plex_id))

    def updateParentId(self, plexid, parent_kodiid):
        """
        Updates parent_id for plex_id
        """
        query = "UPDATE plex SET parent_id = ? WHERE plex_id = ?"
        self.plexcursor.execute(query, (parent_kodiid, plexid))

    def removeItems_byParentId(self, parent_id, kodi_type):
        """
        Removes all entries with parent_id and kodi_type
        """
        query = '''
            DELETE FROM plex
            WHERE parent_id = ?
            AND kodi_type = ?
        '''
        self.plexcursor.execute(query, (parent_id, kodi_type,))

    def removeItem_byKodiId(self, kodi_id, kodi_type):
        """
        Removes the one entry with kodi_id and kodi_type
        """
        query = '''
            DELETE FROM plex
            WHERE kodi_id = ?
            AND kodi_type = ?
        '''
        self.plexcursor.execute(query, (kodi_id, kodi_type,))

    def removeItem(self, plex_id):
        """
        Removes the one entry with plex_id
        """
        self.plexcursor.execute('DELETE FROM plex WHERE plex_id = ?',
                                (plex_id,))

    def itemsByType(self, plex_type):
        """
        Returns a list of dicts for plex_type:
        {
            'plex_id': plex_id
            'kodiId': kodi_id
            'kodi_type': kodi_type
            'plex_type': plex_type
        }
        """
        query = '''
            SELECT plex_id, kodi_id, kodi_type
            FROM plex
            WHERE plex_type = ?
        '''
        self.plexcursor.execute(query, (plex_type, ))
        result = []
        for row in self.plexcursor.fetchall():
            result.append({
                'plex_id': row[0],
                'kodiId': row[1],
                'kodi_type': row[2],
                'plex_type': plex_type
            })
        return result

    def set_fanart_synched(self, plex_id):
        """
        Sets the fanart_synced flag to 1 for plex_id
        """
        query = 'UPDATE plex SET fanart_synced = 1 WHERE plex_id = ?'
        self.plexcursor.execute(query, (plex_id,))

    def get_missing_fanart(self):
        """
        Returns a list of {'plex_id': x, 'plex_type': y} where fanart_synced
        flag is set to 0

        This only for plex_type is either movie or TV show
        """
        query = '''
            SELECT plex_id, plex_type FROM plex
            WHERE fanart_synced = ?
            AND (plex_type = ? OR plex_type = ?)
        '''
        self.plexcursor.execute(query,
                                (0, v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW))
        rows = self.plexcursor.fetchall()
        result = []
        for row in rows:
            result.append({'plex_id': row[0],
                           'plex_type': row[1]})
        return result

    def plex_id_from_playlist_path(self, path):
        """
        Given the Kodi playlist path [unicode], this will return the Plex id
        [str] or None
        """
        query = 'SELECT plex_id FROM playlists WHERE kodi_path = ? LIMIT 1'
        self.plexcursor.execute(query, (path, ))
        try:
            plex_id = self.plexcursor.fetchone()[0]
        except TypeError:
            plex_id = None
        return plex_id

    def plex_ids_all_playlists(self):
        """
        Returns a list of all Plex ids of playlists.
        """
        answ = []
        self.plexcursor.execute('SELECT plex_id FROM playlists')
        for entry in self.plexcursor.fetchall():
            answ.append(entry[0])
        return answ

    def all_kodi_playlist_paths(self):
        """
        Returns a list of all Kodi playlist paths.
        """
        answ = []
        self.plexcursor.execute('SELECT kodi_path FROM playlists')
        for entry in self.plexcursor.fetchall():
            answ.append(entry[0])
        return answ

    def retrieve_playlist(self, playlist, plex_id=None, path=None,
                          kodi_hash=None):
        """
        Returns a complete Playlist (empty one passed in via playlist)
        for the entry with plex_id OR kodi_hash OR kodi_path.
        Returns None if not found
        """
        query = '''
            SELECT plex_id, plex_name, plex_updatedat, kodi_path, kodi_type,
                   kodi_hash
            FROM playlists
            WHERE %s = ?
            LIMIT 1
        '''
        if plex_id:
            query = query % 'plex_id'
            var = plex_id
        elif kodi_hash:
            query = query % 'kodi_hash'
            var = kodi_hash
        else:
            query = query % 'kodi_path'
            var = path
        self.plexcursor.execute(query, (var, ))
        answ = self.plexcursor.fetchone()
        if not answ:
            return
        playlist.plex_id = answ[0]
        playlist.plex_name = answ[1]
        playlist.plex_updatedat = answ[2]
        playlist.kodi_path = answ[3]
        playlist.kodi_type = answ[4]
        playlist.kodi_hash = answ[5]
        return playlist

    def insert_playlist_entry(self, playlist):
        """
        Inserts or modifies an existing entry in the Plex playlists table.
        """
        query = '''
            INSERT OR REPLACE INTO playlists(
                plex_id, plex_name, plex_updatedat, kodi_path, kodi_type,
                kodi_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            '''
        self.plexcursor.execute(query,
                                (playlist.plex_id, playlist.plex_name,
                                 playlist.plex_updatedat, playlist.kodi_path,
                                 playlist.kodi_type, playlist.kodi_hash))

    def delete_playlist_entry(self, playlist):
        """
        Removes the entry for playlist [Playqueue_Object] from the Plex
        playlists table.
        Be sure to either set playlist.id or playlist.kodi_path
        """
        if playlist.plex_id:
            query = 'DELETE FROM playlists WHERE plex_id = ?'
            var = playlist.plex_id
        elif playlist.kodi_path:
            query = 'DELETE FROM playlists WHERE kodi_path = ?'
            var = playlist.kodi_path
        else:
            raise RuntimeError('Cannot delete playlist: %s' % playlist)
        self.plexcursor.execute(query, (var, ))


def wipe_dbs():
    """
    Completely resets the Plex database
    """
    query = "SELECT name FROM sqlite_master WHERE type = 'table'"
    with Get_Plex_DB() as plex_db:
        plex_db.plexcursor.execute(query)
        tables = plex_db.plexcursor.fetchall()
        tables = [i[0] for i in tables]
        for table in tables:
            delete_query = 'DELETE FROM %s' % table
            plex_db.plexcursor.execute(delete_query)

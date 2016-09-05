# -*- coding: utf-8 -*-

###############################################################################

from utils import logging, kodiSQL

###############################################################################


class GetEmbyDB():
    """
    Usage: with GetEmbyDB() as emby_db:
               do stuff with emby_db

    On exiting "with" (no matter what), commits get automatically committed
    and the db gets closed
    """
    def __enter__(self):
        self.embyconn = kodiSQL('emby')
        self.emby_db = Embydb_Functions(self.embyconn.cursor())
        return self.emby_db

    def __exit__(self, type, value, traceback):
        self.embyconn.commit()
        self.embyconn.close()


@logging
class Embydb_Functions():

    def __init__(self, embycursor):

        self.embycursor = embycursor

    def getViews(self):

        views = []

        query = ' '.join((

            "SELECT view_id",
            "FROM view"
        ))
        self.embycursor.execute(query)
        rows = self.embycursor.fetchall()
        for row in rows:
            views.append(row[0])
        return views

    def getAllViewInfo(self):

        embycursor = self.embycursor
        views = []

        query = ' '.join((

            "SELECT view_id, view_name, media_type",
            "FROM view"
        ))
        embycursor.execute(query)
        rows = embycursor.fetchall()
        for row in rows:
            views.append({'id': row[0],
                          'name': row[1],
                          'itemtype': row[2]})
        return views

    def getView_byId(self, viewid):


        query = ' '.join((

            "SELECT view_name, media_type, kodi_tagid",
            "FROM view",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (viewid,))
        view = self.embycursor.fetchone()
        
        return view

    def getView_byType(self, mediatype):

        views = []

        query = ' '.join((

            "SELECT view_id, view_name, media_type",
            "FROM view",
            "WHERE media_type = ?"
        ))
        self.embycursor.execute(query, (mediatype,))
        rows = self.embycursor.fetchall()
        for row in rows:
            views.append({

                'id': row[0],
                'name': row[1],
                'itemtype': row[2]
            })

        return views

    def getView_byName(self, tagname):

        query = ' '.join((

            "SELECT view_id",
            "FROM view",
            "WHERE view_name = ?"
        ))
        self.embycursor.execute(query, (tagname,))
        try:
            view = self.embycursor.fetchone()[0]
        
        except TypeError:
            view = None

        return view

    def addView(self, plexid, name, mediatype, tagid):

        query = (
            '''
            INSERT INTO view(
                view_id, view_name, media_type, kodi_tagid)

            VALUES (?, ?, ?, ?)
            '''
        )
        self.embycursor.execute(query, (plexid, name, mediatype, tagid))

    def updateView(self, name, tagid, mediafolderid):

        query = ' '.join((

            "UPDATE view",
            "SET view_name = ?, kodi_tagid = ?",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (name, tagid, mediafolderid))

    def removeView(self, viewid):

        query = ' '.join((

            "DELETE FROM view",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (viewid,))

    def getItem_byFileId(self, fileId, kodiType):
        """
        Returns the Plex itemId by using the Kodi fileId. VIDEO ONLY

        kodiType: 'movie', 'episode', ...
        """
        query = ' '.join((
            "SELECT emby_id",
            "FROM emby",
            "WHERE kodi_fileid = ? AND media_type = ?"
        ))
        try:
            self.embycursor.execute(query, (fileId, kodiType))
            item = self.embycursor.fetchone()[0]
            return item
        except:
            return None

    def getMusicItem_byFileId(self, fileId, kodiType):
        """
        Returns the Plex itemId by using the Kodi fileId. MUSIC ONLY

        kodiType: 'song'
        """
        query = ' '.join((
            "SELECT emby_id",
            "FROM emby",
            "WHERE kodi_id = ? AND media_type = ?"
        ))
        try:
            self.embycursor.execute(query, (fileId, kodiType))
            item = self.embycursor.fetchone()[0]
            return item
        except:
            return None

    def getItem_byId(self, plexid):

        query = ' '.join((

            "SELECT kodi_id, kodi_fileid, kodi_pathid, parent_id, media_type, emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        try:
            self.embycursor.execute(query, (plexid,))
            item = self.embycursor.fetchone()
            return item
        except: return None

    def getItem_byWildId(self, plexid):

        query = ' '.join((

            "SELECT kodi_id, media_type",
            "FROM emby",
            "WHERE emby_id LIKE ?"
        ))
        self.embycursor.execute(query, (plexid+"%",))
        return self.embycursor.fetchall()

    def getItem_byView(self, mediafolderid):

        query = ' '.join((

            "SELECT kodi_id",
            "FROM emby",
            "WHERE media_folder = ?"
        ))
        self.embycursor.execute(query, (mediafolderid,))
        return self.embycursor.fetchall()

    def getPlexId(self, kodiid, mediatype):
        """
        Returns the Plex ID usind the Kodiid. Result:
            (Plex Id, Parent's Plex Id)
        """
        query = ' '.join((
            "SELECT emby_id, parent_id",
            "FROM emby",
            "WHERE kodi_id = ? AND media_type = ?"
        ))
        try:
            self.embycursor.execute(query, (kodiid, mediatype))
            item = self.embycursor.fetchone()
            return item
        except:
            return None

    def getItem_byKodiId(self, kodiid, mediatype):

        query = ' '.join((

            "SELECT emby_id, parent_id",
            "FROM emby",
            "WHERE kodi_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (kodiid, mediatype,))
        return self.embycursor.fetchone()

    def getItem_byParentId(self, parentid, mediatype):

        query = ' '.join((

            "SELECT emby_id, kodi_id, kodi_fileid",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parentid, mediatype,))
        return self.embycursor.fetchall()

    def getItemId_byParentId(self, parentid, mediatype):

        query = ' '.join((

            "SELECT emby_id, kodi_id",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parentid, mediatype,))
        return self.embycursor.fetchall()

    def getChecksum(self, mediatype):

        query = ' '.join((

            "SELECT emby_id, checksum",
            "FROM emby",
            "WHERE emby_type = ?"
        ))
        self.embycursor.execute(query, (mediatype,))
        return self.embycursor.fetchall()

    def getMediaType_byId(self, plexid):

        query = ' '.join((

            "SELECT emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        self.embycursor.execute(query, (plexid,))
        try:
            itemtype = self.embycursor.fetchone()[0]
        
        except TypeError:
            itemtype = None

        return itemtype

    def sortby_mediaType(self, itemids, unsorted=True):

        sorted_items = {}
        
        for itemid in itemids:
            mediatype = self.getMediaType_byId(itemid)
            if mediatype:
                sorted_items.setdefault(mediatype, []).append(itemid)
            elif unsorted:
                sorted_items.setdefault('Unsorted', []).append(itemid)

        return sorted_items

    def addReference(self, plexid, kodiid, embytype, mediatype, fileid=None, pathid=None,
                        parentid=None, checksum=None, mediafolderid=None):
        query = (
            '''
            INSERT OR REPLACE INTO emby(
                emby_id, kodi_id, kodi_fileid, kodi_pathid, emby_type, media_type, parent_id,
                checksum, media_folder)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.embycursor.execute(query, (plexid, kodiid, fileid, pathid, embytype, mediatype,
            parentid, checksum, mediafolderid))

    def updateReference(self, plexid, checksum):

        query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
        self.embycursor.execute(query, (checksum, plexid))

    def updateParentId(self, plexid, parent_kodiid):
        
        query = "UPDATE emby SET parent_id = ? WHERE emby_id = ?"
        self.embycursor.execute(query, (parent_kodiid, plexid))

    def removeItems_byParentId(self, parent_kodiid, mediatype):

        query = ' '.join((

            "DELETE FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parent_kodiid, mediatype,))

    def removeItem_byKodiId(self, kodiid, mediatype):

        query = ' '.join((

            "DELETE FROM emby",
            "WHERE kodi_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (kodiid, mediatype,))

    def removeItem(self, plexid):

        query = "DELETE FROM emby WHERE emby_id = ?"
        self.embycursor.execute(query, (plexid,))

    def removeWildItem(self, plexid):

        query = "DELETE FROM emby WHERE emby_id LIKE ?"
        self.embycursor.execute(query, (plexid+"%",))
        
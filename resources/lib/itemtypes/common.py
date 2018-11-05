#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from ntpath import dirname

from ..plex_api import API
from ..plex_db import PlexDB
from .. import kodidb_functions as kodidb
from .. import artwork, utils

LOG = getLogger('PLEX.itemtypes.common')

# Note: always use same order of URL arguments, NOT urlencode:
#   plex_id=<plex_id>&plex_type=<plex_type>&mode=play


def process_path(playurl):
    """
    Do NOT use os.path since we have paths that might not apply to the current
    OS!
    """
    if '\\' in playurl:
        # Local path
        path = '%s\\' % playurl
        toplevelpath = '%s\\' % dirname(dirname(path))
    else:
        # Network path
        path = '%s/' % playurl
        toplevelpath = '%s/' % dirname(dirname(path))
    return path, toplevelpath


class ItemBase(object):
    """
    Items to be called with "with Items() as xxx:" to ensure that __enter__
    method is called (opens db connections)

    Input:
        kodiType:       optional argument; e.g. 'video' or 'music'
    """
    def __init__(self, last_sync, plexdb=None, kodi_db=None):
        self.last_sync = last_sync
        self.plexconn = None
        self.plexcursor = plexdb.cursor if plexdb else None
        self.kodiconn = None
        self.kodicursor = kodi_db.cursor if kodi_db else None
        self.plexdb = plexdb
        self.kodi_db = kodi_db

    def __enter__(self):
        """
        Open DB connections and cursors
        """
        self.plexconn = utils.kodi_sql('plex')
        self.plexcursor = self.plexconn.cursor()
        self.kodiconn = utils.kodi_sql('video')
        self.kodicursor = self.kodiconn.cursor()
        self.plexdb = PlexDB(self.plexcursor)
        self.kodi_db = kodidb.KodiDBMethods(self.kodicursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Make sure DB changes are committed and connection to DB is closed.
        """
        self.plexconn.commit()
        self.kodiconn.commit()
        self.plexconn.close()
        self.kodiconn.close()
        return self

    def set_fanart(self, artworks, kodi_id, kodi_type):
        """
        Writes artworks [dict containing only set artworks] to the Kodi art DB
        """
        artwork.modify_artwork(artworks,
                               kodi_id,
                               kodi_type,
                               self.kodicursor)

    def update_userdata(self, xml_element, plex_type):
        """
        Updates the Kodi watched state of the item from PMS. Also retrieves
        Plex resume points for movies in progress.
        """
        api = API(xml_element)
        # Get key and db entry on the Kodi db side
        db_item = self.plexdb.item_by_id(api.plex_id(), plex_type)
        if not db_item:
            LOG.error('Item not yet synced: %s', xml_element.attrib)
            return
        # Grab the user's viewcount, resume points etc. from PMS' answer
        userdata = api.userdata()
        # Write to Kodi DB
        self.kodi_db.set_resume(db_item['kodi_fileid'],
                                userdata['Resume'],
                                userdata['Runtime'],
                                userdata['PlayCount'],
                                userdata['LastPlayedDate'],
                                plex_type)
        self.kodi_db.update_userrating(db_item['kodi_id'],
                                       db_item['kodi_type'],
                                       userdata['UserRating'])

    def update_playstate(self, mark_played, view_count, resume, duration,
                         kodi_fileid, lastViewedAt, plex_type):
        """
        Use with websockets, not xml
        """
        # If the playback was stopped, check whether we need to increment the
        # playcount. PMS won't tell us the playcount via websockets
        if mark_played:
            LOG.info('Marking item as completely watched in Kodi')
            try:
                view_count += 1
            except TypeError:
                view_count = 1
            resume = 0
        # Do the actual update
        self.kodi_db.set_resume(kodi_fileid,
                                resume,
                                duration,
                                view_count,
                                utils.unix_date_to_kodi(lastViewedAt),
                                plex_type)

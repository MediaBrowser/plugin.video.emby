#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from ntpath import dirname

from ..plex_db import PlexDB, PLEXDB_LOCK
from ..kodi_db import KodiVideoDB, KODIDB_LOCK
from .. import utils, timing

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
    def __init__(self, last_sync, plexdb=None, kodidb=None, lock=True):
        self.last_sync = last_sync
        self.lock = lock
        self.plexconn = None
        self.plexcursor = plexdb.cursor if plexdb else None
        self.kodiconn = None
        self.kodicursor = kodidb.cursor if kodidb else None
        self.artconn = kodidb.artconn if kodidb else None
        self.artcursor = kodidb.artcursor if kodidb else None
        self.plexdb = plexdb
        self.kodidb = kodidb

    def __enter__(self):
        """
        Open DB connections and cursors
        """
        if self.lock:
            PLEXDB_LOCK.acquire()
            KODIDB_LOCK.acquire()
        self.plexconn = utils.kodi_sql('plex')
        self.plexcursor = self.plexconn.cursor()
        self.kodiconn = utils.kodi_sql('video')
        self.kodicursor = self.kodiconn.cursor()
        self.artconn = utils.kodi_sql('texture')
        self.artcursor = self.artconn.cursor()
        self.plexdb = PlexDB(cursor=self.plexcursor)
        self.kodidb = KodiVideoDB(texture_db=True,
                                  cursor=self.kodicursor,
                                  artcursor=self.artcursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Make sure DB changes are committed and connection to DB is closed.
        """
        try:
            if exc_type:
                # re-raise any exception
                return False
            self.plexconn.commit()
            self.artconn.commit()
            self.kodiconn.commit()
            return self
        finally:
            self.plexconn.close()
            self.kodiconn.close()
            self.artconn.close()
            if self.lock:
                PLEXDB_LOCK.release()
                KODIDB_LOCK.release()

    def commit(self):
        self.plexconn.commit()
        self.plexconn.execute('BEGIN')
        self.artconn.commit()
        self.artconn.execute('BEGIN')
        self.kodiconn.commit()
        self.kodiconn.execute('BEGIN')

    def set_fanart(self, artworks, kodi_id, kodi_type):
        """
        Writes artworks [dict containing only set artworks] to the Kodi art DB
        """
        self.kodidb.modify_artwork(artworks,
                                   kodi_id,
                                   kodi_type)

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
        self.kodidb.set_resume(kodi_fileid,
                               resume,
                               duration,
                               view_count,
                               timing.plex_date_to_kodi(lastViewedAt),
                               plex_type)

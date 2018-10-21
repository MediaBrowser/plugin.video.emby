#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from .common import PlexDBBase
from .tvshows import 
from .. import utils, variables as v


class PlexDB(object):
    """
    Usage: with PlexDB() as plex_db:
               plex_db.do_something()

    On exiting "with" (no matter what), commits get automatically committed
    and the db gets closed
    """
    def __init__(self, kind=None):
        pass

    def __enter__(self):
        self.plexconn = utils.kodi_sql('plex')
        if kind is None:
            func = PlexDBBase
        return func(self.plexconn.cursor())

    def __exit__(self, type, value, traceback):
        self.plexconn.commit()
        self.plexconn.close()


def wipe_dbs():
    """
    Completely resets the Plex database
    """
    query = "SELECT name FROM sqlite_master WHERE type = 'table'"
    with PlexDB() as plex_db:
        plex_db.plexcursor.execute(query)
        tables = plex_db.plexcursor.fetchall()
        tables = [i[0] for i in tables]
        for table in tables:
            delete_query = 'DELETE FROM %s' % table
            plex_db.plexcursor.execute(delete_query)

# -*- coding: utf-8 -*-
import sqlite3
import helper.loghandler
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

LOG = helper.loghandler.LOG('EMBY.database.db_open.io')


class io:
    def __init__(self, DatabaseFiles, DBID, commit_close):
        self.DatabaseFiles = DatabaseFiles
        self.DBID = DBID
        self.commit_close = commit_close
        self.conn = None
        self.cursor = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.DatabaseFiles[self.DBID], timeout=999999, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")  # to avoid writing conflict with kodi
        self.cursor = self.conn.cursor()
        LOG.debug("--->[ database: %s ] %s" % (self.DBID, id(self.conn)))

        if self.DBID == 'video':
            return video_db.VideoDatabase(self.cursor)

        if self.DBID == 'music':
            return music_db.MusicDatabase(self.cursor)

        if self.DBID == 'texture':
            return common_db.CommonDatabase(self.cursor)

        return emby_db.EmbyDatabase(self.cursor)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.commit_close:
            changes = self.conn.total_changes
            LOG.info("[%s] %s rows updated." % (self.DBID, changes))

            if changes:
                self.conn.commit()

        LOG.debug("---<[ database: %s ] %s" % (self.DBID, id(self.conn)))
        self.cursor.close()
        self.conn.close()

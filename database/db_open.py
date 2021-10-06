# -*- coding: utf-8 -*-
import sqlite3
import threading
import helper.loghandler
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

DBIOLock = threading.Lock()
DBConnections = {}
DBConnectionsOpenCounters = {}
LOG = helper.loghandler.LOG('EMBY.database.db_open')


def DBOpen(DatabaseFiles, DBID):
    with DBIOLock:
        global DBConnections
        global DBConnectionsOpenCounters

        if DBID not in DBConnectionsOpenCounters:
            DBConnections[DBID] = sqlite3.connect(DatabaseFiles[DBID], timeout=999999, check_same_thread=False)
            DBConnections[DBID].execute("PRAGMA journal_mode=WAL")
            DBConnectionsOpenCounters[DBID] = 1
        else:
            DBConnectionsOpenCounters[DBID] += 1

        LOG.info("--->[ database: %s/%s ]" % (DBID, DBConnectionsOpenCounters[DBID]))

        if DBID == 'video':
            return video_db.VideoDatabase(DBConnections[DBID].cursor())

        if DBID == 'music':
            return music_db.MusicDatabase(DBConnections[DBID].cursor())

        if DBID == 'texture':
            return common_db.CommonDatabase(DBConnections[DBID].cursor())

        return emby_db.EmbyDatabase(DBConnections[DBID].cursor())

def DBClose(DBID, commit_close):
    with DBIOLock:
        global DBConnections
        global DBConnectionsOpenCounters

        if commit_close:
            changes = DBConnections[DBID].total_changes
            LOG.info("[%s] %s rows updated." % (DBID, changes))

            if changes:
                DBConnections[DBID].commit()

        DBConnectionsOpenCounters[DBID] += -1
        LOG.info("---<[ database: %s/%s ]" % (DBID, DBConnectionsOpenCounters[DBID]))

        if DBConnectionsOpenCounters[DBID] == 0:
            DBConnections[DBID].cursor().close()
            DBConnections[DBID].close()
            del DBConnections[DBID]
            del DBConnectionsOpenCounters[DBID]

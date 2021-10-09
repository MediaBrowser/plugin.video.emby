# -*- coding: utf-8 -*-
import sqlite3
import threading
import helper.loghandler
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

DBIOLock = {}
DBConnections = {}
LOG = helper.loghandler.LOG('EMBY.database.db_open')


def DBOpen(DatabaseFiles, DBID):
    global DBIOLock

    if DBID not in DBIOLock:
        DBIOLock[DBID] = threading.Lock()

    with DBIOLock[DBID]:
        global DBConnections

        if DBID not in DBConnections:
            DBConnections[DBID] = sqlite3.connect(DatabaseFiles[DBID], timeout=999999, check_same_thread=False)
            DBConnections[DBID].execute("PRAGMA journal_mode=WAL")
            DBConnections["%s_count" % DBID] = 1
        else:
            DBConnections["%s_count" % DBID] += 1

        LOG.debug("--->[ database: %s/%s ]" % (DBID, DBConnections["%s_count" % DBID]))

        if DBID == 'video':
            return video_db.VideoDatabase(DBConnections[DBID].cursor())

        if DBID == 'music':
            return music_db.MusicDatabase(DBConnections[DBID].cursor())

        if DBID == 'texture':
            return common_db.CommonDatabase(DBConnections[DBID].cursor())

        return emby_db.EmbyDatabase(DBConnections[DBID].cursor())

def DBClose(DBID, commit_close):
    with DBIOLock[DBID]:
        global DBConnections

        if commit_close:
            changes = DBConnections[DBID].total_changes
            LOG.info("[%s] %s rows updated." % (DBID, changes))

            if changes:
                DBConnections[DBID].commit()

        DBConnections["%s_count" % DBID] += -1
        LOG.debug("---<[ database: %s/%s ]" % (DBID, DBConnections["%s_count" % DBID]))

        if DBConnections["%s_count" % DBID] == 0:
            DBConnections[DBID].cursor().close()
            DBConnections[DBID].close()
            del DBConnections[DBID]

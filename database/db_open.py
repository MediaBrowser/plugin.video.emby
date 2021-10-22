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
    if DBID not in globals()["DBIOLock"]:
        globals()["DBIOLock"][DBID] = threading.Lock()

    with globals()["DBIOLock"][DBID]:
        if DBID not in globals()["DBConnections"]:
            globals()["DBConnections"][DBID] = sqlite3.connect(DatabaseFiles[DBID], timeout=999999, check_same_thread=False)
            globals()["DBConnections"][DBID].execute("PRAGMA journal_mode=WAL")
            globals()["DBConnections"]["%s_count" % DBID] = 1
        else:
            globals()["DBConnections"]["%s_count" % DBID] += 1

        LOG.debug("--->[ database: %s/%s ]" % (DBID, globals()["DBConnections"]["%s_count" % DBID]))

        if DBID == 'video':
            return video_db.VideoDatabase(globals()["DBConnections"][DBID].cursor())

        if DBID == 'music':
            return music_db.MusicDatabase(globals()["DBConnections"][DBID].cursor())

        if DBID == 'texture':
            return common_db.CommonDatabase(globals()["DBConnections"][DBID].cursor())

        return emby_db.EmbyDatabase(globals()["DBConnections"][DBID].cursor())

def DBClose(DBID, commit_close):
    with globals()["DBIOLock"][DBID]:
        if commit_close:
            changes = globals()["DBConnections"][DBID].total_changes
            LOG.info("[%s] %s rows updated." % (DBID, changes))

            if changes:
                globals()["DBConnections"][DBID].commit()

        globals()["DBConnections"]["%s_count" % DBID] += -1
        LOG.debug("---<[ database: %s/%s ]" % (DBID, globals()["DBConnections"]["%s_count" % DBID]))

        if globals()["DBConnections"]["%s_count" % DBID] == 0:
            globals()["DBConnections"][DBID].cursor().close()
            globals()["DBConnections"][DBID].close()
            del globals()["DBConnections"][DBID]

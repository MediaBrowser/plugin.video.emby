# -*- coding: utf-8 -*-
import sqlite3
import xbmc
from helper import loghandler
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

DBIOLock = {}
DBConnections = {}
LOG = loghandler.LOG('EMBY.database.db_open')


def DBOpen(DatabaseFiles, DBID):
    if DBID in globals()["DBIOLock"]:
        while globals()["DBIOLock"][DBID]:
            xbmc.sleep(500)

    globals()["DBIOLock"][DBID] = True

    if DBID not in globals()["DBConnections"]:  # create curser
        globals()["DBConnections"][DBID] = sqlite3.connect(DatabaseFiles[DBID], timeout=999999, check_same_thread=False)
        globals()["DBConnections"][DBID].execute("PRAGMA journal_mode=WAL")
        globals()["DBConnections"]["%s_count" % DBID] = 1
    else:  # re-use curser
        globals()["DBConnections"]["%s_count" % DBID] += 1

    LOG.debug("--->[ database: %s/%s ]" % (DBID, globals()["DBConnections"]["%s_count" % DBID]))
    globals()["DBIOLock"][DBID] = False

    if DBID == 'video':
        return video_db.VideoDatabase(globals()["DBConnections"][DBID].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(globals()["DBConnections"][DBID].cursor())

    if DBID == 'texture':
        return common_db.CommonDatabase(globals()["DBConnections"][DBID].cursor())

    return emby_db.EmbyDatabase(globals()["DBConnections"][DBID].cursor())

def DBClose(DBID, commit_close):
    if DBID in globals()["DBIOLock"]:
        while globals()["DBIOLock"][DBID]:
            xbmc.sleep(500)

    globals()["DBIOLock"][DBID] = True

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

    globals()["DBIOLock"][DBID] = False

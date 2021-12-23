# -*- coding: utf-8 -*-
import sqlite3
import xbmc
from helper import loghandler
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

DBConnections = {}  # content: list [dbconn, opencounter, commitdelta, locked]
LOG = loghandler.LOG('EMBY.database.dbio')


def DBOpen(DatabaseFiles, DBID):
    if DBID in globals()["DBConnections"]:
        while globals()["DBConnections"][DBID][3]:  #Wait for db unlock
            xbmc.sleep(500)

    if DBID not in globals()["DBConnections"]:  # create curser
        globals()["DBConnections"][DBID] = [sqlite3.connect(DatabaseFiles[DBID], timeout=999999, check_same_thread=False), 1, 0, False]
        globals()["DBConnections"][DBID][0].execute("PRAGMA journal_mode=WAL")
    else:  # re-use curser
        globals()["DBConnections"][DBID][1] += 1

    LOG.debug("--->[ database: %s/%s ]" % (DBID, globals()["DBConnections"][DBID][1]))

    if DBID == 'video':
        return video_db.VideoDatabase(globals()["DBConnections"][DBID][0].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(globals()["DBConnections"][DBID][0].cursor())

    if DBID == 'texture':
        return common_db.CommonDatabase(globals()["DBConnections"][DBID][0].cursor())

    return emby_db.EmbyDatabase(globals()["DBConnections"][DBID][0].cursor())

def DBClose(DBID, commit_close):
    while globals()["DBConnections"][DBID][3]:
        xbmc.sleep(500)

    globals()["DBConnections"][DBID][3] = True

    if commit_close:
        changes = globals()["DBConnections"][DBID][0].total_changes
        LOG.info("--->[%s] %s rows updated on db close" % (DBID, changes))

        if changes:
            globals()["DBConnections"][DBID][0].commit()

        LOG.info("---<[%s] %s rows updated on db close" % (DBID, changes))

    globals()["DBConnections"][DBID][1] += -1
    LOG.debug("---<[ database: %s/%s ]" % (DBID, globals()["DBConnections"][DBID][1]))

    if globals()["DBConnections"][DBID][1] == 0:  # last db access closed -> close db
        globals()["DBConnections"][DBID][0].cursor().close()
        globals()["DBConnections"][DBID][0].close()
        del globals()["DBConnections"][DBID]
    else:
        globals()["DBConnections"][DBID][3] = False

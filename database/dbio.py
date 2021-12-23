# -*- coding: utf-8 -*-
import sqlite3
import threading
import xbmc
from helper import loghandler
from helper import utils
from . import emby_db
from . import video_db
from . import music_db
from . import common_db

DBConnections = {}  # content: list [dbconn, dbopencounter, locked]
LOG = loghandler.LOG('EMBY.database.dbio')


def DBOpen(DBID):
    DBIDThreadID = "%s%s" % (DBID, threading.current_thread().ident)

    if DBIDThreadID in globals()["DBConnections"]:
        while globals()["DBConnections"][DBIDThreadID][2]:  #Wait for db unlock
            xbmc.sleep(500)

    if DBIDThreadID not in globals()["DBConnections"]:  # create curser
        globals()["DBConnections"][DBIDThreadID] = [None, 1, 0, True]
        globals()["DBConnections"][DBIDThreadID][0] = sqlite3.connect(utils.DatabaseFiles[DBID], timeout=999999)
        globals()["DBConnections"][DBIDThreadID][0].execute("PRAGMA journal_mode=WAL")
        globals()["DBConnections"][DBIDThreadID][2] = False
    else:  # re-use curser
        globals()["DBConnections"][DBIDThreadID][1] += 1

    LOG.debug("--->[ database: %s/%s ]" % (DBIDThreadID, globals()["DBConnections"][DBIDThreadID][1]))

    if DBID == 'video':
        return video_db.VideoDatabase(globals()["DBConnections"][DBIDThreadID][0].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(globals()["DBConnections"][DBIDThreadID][0].cursor())

    if DBID == 'texture':
        return common_db.CommonDatabase(globals()["DBConnections"][DBIDThreadID][0].cursor())

    return emby_db.EmbyDatabase(globals()["DBConnections"][DBIDThreadID][0].cursor())

def DBClose(DBID, commit_close):
    DBIDThreadID = "%s%s" % (DBID, threading.current_thread().ident)

    while globals()["DBConnections"][DBIDThreadID][2]:
        xbmc.sleep(500)

    globals()["DBConnections"][DBIDThreadID][2] = True

    if commit_close:
        changes = globals()["DBConnections"][DBIDThreadID][0].total_changes
        LOG.info("--->[%s] %s rows updated on db close" % (DBIDThreadID, changes))

        if changes:
            globals()["DBConnections"][DBIDThreadID][0].commit()

        LOG.info("---<[%s] %s rows updated on db close" % (DBIDThreadID, changes))

    globals()["DBConnections"][DBIDThreadID][1] += -1
    LOG.debug("---<[ database: %s/%s ]" % (DBIDThreadID, globals()["DBConnections"][DBIDThreadID][1]))

    if globals()["DBConnections"][DBIDThreadID][1] == 0:  # last db access closed -> close db
        globals()["DBConnections"][DBIDThreadID][0].cursor().close()
        globals()["DBConnections"][DBIDThreadID][0].close()
        del globals()["DBConnections"][DBIDThreadID]
    else:
        globals()["DBConnections"][DBIDThreadID][2] = False

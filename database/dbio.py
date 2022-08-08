import sqlite3
from _thread import get_ident

from helper import utils, loghandler
from . import emby_db, video_db, music_db, texture_db

DBConnectionsRW = {}
DBConnectionsRO = {}
LOG = loghandler.LOG('EMBY.database.dbio')


def DBVacuum():
    for DBID, DBFile in list(utils.DatabaseFiles.items()):
        if 'version' in DBID:
            continue

        LOG.info("---> DBVacuum: %s" % DBID)

        if DBID in DBConnectionsRW:
            while DBConnectionsRW[DBID][1]:  #Wait for db unlock
                LOG.info("DBOpenRW: Waiting Vacuum %s" % DBID)
                utils.sleep(1)
        else:
            globals()["DBConnectionsRW"][DBID] = [None, False]

        globals()["DBConnectionsRW"][DBID][1] = True
        globals()["DBConnectionsRW"][DBID][0] = sqlite3.connect(DBFile, timeout=999999)

        if DBID == "music":
            DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
            curser = DBConnectionsRW[DBID][0].cursor()
            curser.execute("DELETE FROM removed_link")
            curser.close()
            DBConnectionsRW[DBID][0].commit()
            DBConnectionsRW[DBID][0].close()
            globals()["DBConnectionsRW"][DBID][0] = sqlite3.connect(DBFile, timeout=999999)

        DBConnectionsRW[DBID][0].execute("VACUUM")
        DBConnectionsRW[DBID][0].cursor().close()
        DBConnectionsRW[DBID][0].close()
        globals()["DBConnectionsRW"][DBID][1] = False
        LOG.info("---< DBVacuum: %s" % DBID)

def DBOpenRO(DBID, TaskId):
    DBIDThreadID = "%s%s%s" % (DBID, TaskId, get_ident())

    try:
        globals()["DBConnectionsRO"][DBIDThreadID] = sqlite3.connect("file:%s?immutable=1&mode=ro" % utils.DatabaseFiles[DBID].decode('utf-8'), uri=True, timeout=999999) #, check_same_thread=False
    except Exception as Error:
        LOG.error("Database IO: %s / %s" % (utils.DatabaseFiles[DBID], Error))
        return None

    DBConnectionsRO[DBIDThreadID].execute("PRAGMA journal_mode=WAL")
    LOG.info("---> DBOpenRO: %s" % DBIDThreadID)

    if DBID == 'video':
        return video_db.VideoDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    if DBID == 'texture':
        return texture_db.TextureDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    return emby_db.EmbyDatabase(DBConnectionsRO[DBIDThreadID].cursor())

def DBCloseRO(DBID, TaskId):
    DBIDThreadID = "%s%s%s" % (DBID, TaskId, get_ident())
    DBConnectionsRO[DBIDThreadID].cursor().close()
    DBConnectionsRO[DBIDThreadID].close()
    LOG.info("---< DBCloseRO: %s" % DBIDThreadID)

def DBOpenRW(DBID, TaskId):
    if DBID == "folder":
        return None

    if DBID in DBConnectionsRW:
        while DBConnectionsRW[DBID][1]:  #Wait for db unlock
            LOG.info("DBOpenRW: Waiting %s / %s" % (DBID, TaskId))
            utils.sleep(1)
    else:
        globals()["DBConnectionsRW"][DBID] = [None, False]

    globals()["DBConnectionsRW"][DBID][1] = True
    globals()["DBConnectionsRW"][DBID][0] = sqlite3.connect(utils.DatabaseFiles[DBID].decode('utf-8'), timeout=999999)
    DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
    LOG.info("---> DBOpenRW: %s/%s" % (DBID, TaskId))

    if DBID == 'video':
        return video_db.VideoDatabase(DBConnectionsRW[DBID][0].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(DBConnectionsRW[DBID][0].cursor())

    if DBID == 'texture':
        return texture_db.TextureDatabase(DBConnectionsRW[DBID][0].cursor())

    return emby_db.EmbyDatabase(DBConnectionsRW[DBID][0].cursor())

def DBCloseRW(DBID, TaskId):
    if DBID == "folder":
        return

    changes = DBConnectionsRW[DBID][0].total_changes

    if changes:
        DBConnectionsRW[DBID][0].commit()

    DBConnectionsRW[DBID][0].cursor().close()
    DBConnectionsRW[DBID][0].close()
    globals()["DBConnectionsRW"][DBID][1] = False
    LOG.info("---< DBCloseRW: %s / %s / %s rows updated on db close" % (DBID, changes, TaskId))

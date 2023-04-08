import sqlite3
from _thread import get_ident
import xbmc
from helper import utils
from . import emby_db, video_db, music_db, texture_db

DBConnectionsRW = {}
DBConnectionsRO = {}


def DBVacuum():
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    utils.progress_open(utils.Translate(33436))
    TotalItems = len(utils.DatabaseFiles) / 100
    Index = 1

    for DBID, DBFile in list(utils.DatabaseFiles.items()):
        utils.progress_update(int(Index / TotalItems), utils.Translate(33436), str(DBID))

        if 'version' in DBID:
            continue

        xbmc.log(f"EMBY.database.dbio: ---> DBVacuum: {DBID}", 1) # LOGINFO

        if DBID in DBConnectionsRW:
            while DBConnectionsRW[DBID][1]:  #Wait for db unlock
                xbmc.log(f"EMBY.database.dbio: DBOpenRW: Waiting Vacuum {DBID}", 1) # LOGINFO
                utils.sleep(1)
        else:
            globals()["DBConnectionsRW"][DBID] = [None, False]

        globals()["DBConnectionsRW"][DBID] = [sqlite3.connect(DBFile, timeout=999999), True]

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
        xbmc.log(f"EMBY.database.dbio: ---< DBVacuum: {DBID}", 1) # LOGINFO
        Index += 1

    utils.progress_close()

def DBOpenRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{get_ident()}"

    try:
        globals()["DBConnectionsRO"][DBIDThreadID] = sqlite3.connect(f"file:{utils.DatabaseFiles[DBID].decode('utf-8')}?immutable=1&mode=ro", uri=True, timeout=999999) #, check_same_thread=False
    except Exception as Error:
        xbmc.log(f"EMBY.database.dbio: Database IO: {DBID} / {TaskId} / {Error}", 3) # LOGERROR
        return None

    DBConnectionsRO[DBIDThreadID].execute("PRAGMA journal_mode=WAL")
    xbmc.log(f"EMBY.database.dbio: ---> DBOpenRO: {DBIDThreadID}", 1) # LOGINFO

    if DBID == 'video':
        return video_db.VideoDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    if DBID == 'music':
        return music_db.MusicDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    if DBID == 'texture':
        return texture_db.TextureDatabase(DBConnectionsRO[DBIDThreadID].cursor())

    return emby_db.EmbyDatabase(DBConnectionsRO[DBIDThreadID].cursor())

def DBCloseRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{get_ident()}"

    if DBIDThreadID in DBConnectionsRO:
        DBConnectionsRO[DBIDThreadID].cursor().close()
        DBConnectionsRO[DBIDThreadID].close()
        xbmc.log(f"EMBY.database.dbio: ---< DBCloseRO: {DBIDThreadID}", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.database.dbio: DBIDThreadID not found {DBIDThreadID}", 3) # LOGERROR

def DBOpenRW(DBID, TaskId):
    if DBID == "folder":
        return None

    if DBID in DBConnectionsRW:
        while DBConnectionsRW[DBID][1]:  #Wait for db unlock
            xbmc.log(f"EMBY.database.dbio: DBOpenRW: Waiting {DBID} / {TaskId}", 1) # LOGINFO
            utils.sleep(1)
    else:
        globals()["DBConnectionsRW"][DBID] = [None, False]

    globals()["DBConnectionsRW"][DBID] = [sqlite3.connect(utils.DatabaseFiles[DBID].decode('utf-8'), timeout=999999), True]
    DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
    xbmc.log(f"EMBY.database.dbio: ---> DBOpenRW: {DBID}/{TaskId}", 1) # LOGINFO

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
    xbmc.log(f"EMBY.database.dbio: ---< DBCloseRW: {DBID} / {changes} / {TaskId} rows updated on db close", 1) # LOGINFO

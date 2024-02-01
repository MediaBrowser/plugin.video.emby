import sqlite3
from _thread import get_ident
import xbmc
import xbmcgui
from helper import utils
from . import emby_db, video_db, music_db, texture_db, common_db

DBConnectionsRW = {}
DBConnectionsRO = {}

def DBVacuum():
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    ProgressBar = xbmcgui.DialogProgressBG()
    ProgressBar.create(utils.Translate(33199), utils.Translate(33436))
    TotalItems = len(utils.DatabaseFiles) / 100
    Index = 1

    for DBID, DBFile in list(utils.DatabaseFiles.items()):
        ProgressBar.update(int(Index / TotalItems), utils.Translate(33436), str(DBID))

        if 'version' in DBID:
            continue

        xbmc.log(f"EMBY.database.dbio: ---> DBVacuum: {DBID}", 0) # LOGDEBUG

        if DBID in DBConnectionsRW:
            while DBConnectionsRW[DBID][2]:  #Wait for db unlock
                xbmc.log(f"EMBY.database.dbio: DBOpenRW: Waiting Vacuum {DBID}", 1) # LOGINFO
                utils.sleep(1)

        globals()["DBConnectionsRW"][DBID] = [None, None, True]
        globals()["DBConnectionsRW"][DBID][0] = sqlite3.connect(DBFile, timeout=999999)
        globals()["DBConnectionsRW"][DBID][1] = DBConnectionsRW[DBID][0].cursor()

        if DBID == "music":
            DBConnectionsRW[DBID][1].execute("DELETE FROM removed_link")
            DBConnectionsRW[DBID][1].close()
            DBConnectionsRW[DBID][0].commit()

        DBConnectionsRW[DBID][0].execute("VACUUM")
        DBConnectionsRW[DBID][0].close()
        globals()["DBConnectionsRW"][DBID][2] = False
        xbmc.log(f"EMBY.database.dbio: ---< DBVacuum: {DBID}", 0) # LOGDEBUG
        Index += 1

    ProgressBar.close()
    del ProgressBar

def DBOpenRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{get_ident()}"
    xbmc.log(f"EMBY.database.dbio: ---> DBRO: {DBIDThreadID}", 0) # LOGDEBUG
    globals()["DBConnectionsRO"][DBIDThreadID] = [sqlite3.connect(f"file:{utils.DatabaseFiles[DBID].decode('utf-8')}?mode=ro", uri=True, timeout=999999, check_same_thread=False), None]
    DBConnectionsRO[DBIDThreadID][0].execute("PRAGMA journal_mode=WAL")
    DBConnectionsRO[DBIDThreadID][0].execute("PRAGMA secure_delete=false")
    DBConnectionsRO[DBIDThreadID][0].execute("PRAGMA synchronous=normal")
    DBConnectionsRO[DBIDThreadID][0].execute("PRAGMA temp_store=memory")
    DBConnectionsRO[DBIDThreadID][1] = DBConnectionsRO[DBIDThreadID][0].cursor()

    if DBID == 'video':
        return video_db.VideoDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID == 'music':
        return music_db.MusicDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID == 'texture':
        return texture_db.TextureDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID in ('epg', 'tv'):
        return common_db.CommonDatabase(DBConnectionsRO[DBIDThreadID][1])

    return emby_db.EmbyDatabase(DBConnectionsRO[DBIDThreadID][1])

def DBCloseRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{get_ident()}"

    if DBIDThreadID in DBConnectionsRO:
        DBConnectionsRO[DBIDThreadID][1].close()
        DBConnectionsRO[DBIDThreadID][0].close()
        globals()["DBConnectionsRO"][DBIDThreadID] = [None, None]
        xbmc.log(f"EMBY.database.dbio: ---< DBRO: {DBIDThreadID}", 0) # LOGDEBUG
    else:
        xbmc.log(f"EMBY.database.dbio: DBIDThreadID not found {DBIDThreadID}", 3) # LOGERROR

def DBOpenRW(Databases, TaskId, SQLs):
    DBIDs = Databases.split(",")

    for DBID in DBIDs:
        if DBID == "none":
            continue

        if DBID in DBConnectionsRW:
            while DBConnectionsRW[DBID][2]:  #Wait for db unlock
                xbmc.log(f"EMBY.database.dbio: DBOpenRW: Waiting {DBID} / {TaskId}", 1) # LOGINFO
                utils.sleep(1)

        xbmc.log(f"EMBY.database.dbio: ---> DBRW: {DBID}/{TaskId}", 0) # LOGDEBUG
        globals()["DBConnectionsRW"][DBID] = [None, None, True]
        globals()["DBConnectionsRW"][DBID][0] = sqlite3.connect(utils.DatabaseFiles[DBID].decode('utf-8'), timeout=999999)
        globals()["DBConnectionsRW"][DBID][1] = DBConnectionsRW[DBID][0].cursor()
        DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
        DBConnectionsRW[DBID][0].execute("PRAGMA secure_delete=false")
        DBConnectionsRW[DBID][0].execute("PRAGMA synchronous=normal")
        DBConnectionsRW[DBID][0].execute("PRAGMA temp_store=memory")
        DBConnectionsRW[DBID][0].execute("pragma mmap_size=1073741824")

        if DBID == 'video':
            SQLs[DBID] = video_db.VideoDatabase(DBConnectionsRW[DBID][1])
        elif DBID == 'music':
            SQLs[DBID] = music_db.MusicDatabase(DBConnectionsRW[DBID][1])
        elif DBID == 'texture':
            SQLs[DBID] = texture_db.TextureDatabase(DBConnectionsRW[DBID][1])
        elif DBID == 'epg':
            SQLs[DBID] = common_db.CommonDatabase(DBConnectionsRW[DBID][1])
        elif DBID == 'tv':
            SQLs[DBID] = common_db.CommonDatabase(DBConnectionsRW[DBID][1])
        else:
            SQLs["emby"] = emby_db.EmbyDatabase(DBConnectionsRW[DBID][1])

    return SQLs

def DBCloseRW(Databases, TaskId, SQLs):
    DBIDs = Databases.split(",")

    for DBID in DBIDs:
        if DBID == "none":
            continue

        DBConnectionsRW[DBID][1].close() # curser close
        changes = DBConnectionsRW[DBID][0].total_changes

        if changes:
            DBConnectionsRW[DBID][0].commit()

        DBConnectionsRW[DBID][0].close() # db close
        globals()["DBConnectionsRW"][DBID] = [None, None, False]

        if DBID in ('video', 'music', 'texture', 'epg', 'tv'):
            SQLs[DBID] = None
        else:
            SQLs["emby"] = None

        xbmc.log(f"EMBY.database.dbio: ---< DBRW: {DBID} / {changes} / {TaskId} rows updated on db close", 0) # LOGDEBUG

    return SQLs

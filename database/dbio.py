import sqlite3
import threading
import xbmcvfs
import xbmc
from helper import utils
from . import emby_db, video_db, music_db, texture_db, addon_db, common_db

DBConnectionsRW = {}
DBConnectionsRO = {}

def DBVacuum():
    utils.close_dialog(10146) # addoninformation
    utils.create_ProgressBar("DBVacuum", utils.Translate(33199), utils.Translate(33436))
    TotalItems = len(utils.DatabaseFiles) / 100
    Index = 1

    for DBID, DBFile in list(utils.DatabaseFiles.items()):
        utils.update_ProgressBar("DBVacuum", Index / TotalItems, utils.Translate(33436), str(DBID))

        if 'version' in DBID:
            continue

        if not xbmcvfs.exists(DBFile):
            continue

        if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---> DBVacuum: {DBID}", 1) # LOGDEBUG

        if DBID not in DBConnectionsRW:
            DBConnectionsRW[DBID] = [None, None, threading.Condition(threading.Lock()), False]

        if utils.DebugLog: xbmc.log("EMBY.database.dbio (DEBUG): CONDITION: --->[ DBConnectionsRW ]", 1) # LOGDEBUG

        with utils.SafeLock(DBConnectionsRW[DBID][2]):
            while DBConnectionsRW[DBID][3]:
                DBConnectionsRW[DBID][2].wait(timeout=0.1)
                xbmc.sleep(1)

            if utils.DebugLog: xbmc.log("EMBY.database.dbio (DEBUG): CONDITION: ---<[ DBConnectionsRW ]", 1) # LOGDEBUG
            DBConnectionsRW[DBID][3] = True

            while True:
                try:
                    DBConnectionsRW[DBID][0] = sqlite3.connect(DBFile, timeout=0.1)
                    break
                except:
                    xbmc.sleep(100)

            DBConnectionsRW[DBID][1] = DBConnectionsRW[DBID][0].cursor()

            if DBID == "music":
                DBConnectionsRW[DBID][1].execute("DELETE FROM removed_link")
                DBConnectionsRW[DBID][0].commit()
                DBConnectionsRW[DBID][1].close()
                DBConnectionsRW[DBID][1] = None

            try:
                DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=OFF")
            except:
                xbmc.log(f"EMBY.database.dbio: Journalmode cannot be changed to OFF ---> DBVacuum: {DBID}", 1) # LOGINFO

            DBConnectionsRW[DBID][0].execute("PRAGMA page_size=65536")
            DBConnectionsRW[DBID][0].execute("VACUUM")

            try:
                DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
            except:
                xbmc.log(f"EMBY.database.dbio: Journalmode cannot be changed to WAL ---> DBVacuum: {DBID}", 1) # LOGINFO

            DBConnectionsRW[DBID][0].execute("ANALYZE")
            DBConnectionsRW[DBID][0].close()
            DBConnectionsRW[DBID][0] = None
            DBConnectionsRW[DBID][3] = False
            DBConnectionsRW[DBID][2].notify_all()
            if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---< DBVacuum: {DBID}", 1) # LOGDEBUG
            Index += 1

    utils.close_ProgressBar("DBVacuum")

def DBOpenRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{threading.get_ident()}"
    if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---> DBRO: {DBIDThreadID}", 1) # LOGDEBUG
    DBConnectionsRO[DBIDThreadID] = [sqlite3.connect(f"file:{utils.DatabaseFiles[DBID]}?mode=ro", uri=True, timeout=999999, check_same_thread=False), None]
    DBConnectionsRO[DBIDThreadID][1] = DBConnectionsRO[DBIDThreadID][0].cursor()
    DBConnectionsRO[DBIDThreadID][0].execute("PRAGMA temp_store=MEMORY")

    if DBID == 'video':
        return video_db.VideoDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID == 'music':
        return music_db.MusicDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID == 'texture':
        return texture_db.TextureDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID == 'addon':
        return addon_db.AddonDatabase(DBConnectionsRO[DBIDThreadID][1])

    if DBID in ('epg', 'tv'):
        return common_db.CommonDatabase(DBConnectionsRO[DBIDThreadID][1])

    return emby_db.EmbyDatabase(DBConnectionsRO[DBIDThreadID][1])

def DBCloseRO(DBID, TaskId):
    DBIDThreadID = f"{DBID}{TaskId}{threading.get_ident()}"

    if DBIDThreadID in DBConnectionsRO:
        DBConnectionsRO[DBIDThreadID][1].close()
        DBConnectionsRO[DBIDThreadID][0].close()
        DBConnectionsRO[DBIDThreadID] = [None, None]
        if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---< DBRO: {DBIDThreadID}", 1) # LOGDEBUG
    else:
        xbmc.log(f"EMBY.database.dbio: DBIDThreadID not found {DBIDThreadID}", 3) # LOGERROR

def DBOpenRW(Databases, TaskId, SQLs):
    DBIDs = Databases.split(",")

    for DBID in DBIDs:
        if DBID in utils.DatabaseFiles:
            if DBID not in DBConnectionsRW:
                DBConnectionsRW[DBID] = [None, None, threading.Condition(threading.Lock()), False]

            if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---> DBRW: {DBID}/{TaskId}", 1) # LOGDEBUG
            if utils.DebugLog: xbmc.log("EMBY.database.dbio (DEBUG): CONDITION: --->[ DBConnectionsRW ]", 1) # LOGDEBUG

            with utils.SafeLock(DBConnectionsRW[DBID][2]):
                while DBConnectionsRW[DBID][3]:
                    DBConnectionsRW[DBID][2].wait(timeout=0.1)
                    xbmc.sleep(1)

                if utils.DebugLog: xbmc.log("EMBY.database.dbio (DEBUG): CONDITION: ---<[ DBConnectionsRW ]", 1) # LOGDEBUG
                DBConnectionsRW[DBID][3] = True

                while True:
                    try:
                        DBConnectionsRW[DBID][0] = sqlite3.connect(utils.DatabaseFiles[DBID], timeout=0.1, check_same_thread=False)
                        DBConnectionsRW[DBID][1] = DBConnectionsRW[DBID][0].cursor()
                        DBConnectionsRW[DBID][0].execute("PRAGMA temp_store=MEMORY")
                        DBConnectionsRW[DBID][0].execute("PRAGMA journal_mode=WAL")
                        DBConnectionsRW[DBID][0].execute("PRAGMA synchronous=NORMAL")
                        DBConnectionsRW[DBID][0].execute("PRAGMA secure_delete=OFF")
                        DBConnectionsRW[DBID][1].execute("BEGIN IMMEDIATE TRANSACTION")
                        break
                    except:
                        if DBConnectionsRW[DBID][0]:
                            DBConnectionsRW[DBID][0].close()
                            DBConnectionsRW[DBID][0] = None
                            DBConnectionsRW[DBID][1] = None

                        xbmc.sleep(100)

                if DBID == 'video':
                    SQLs[DBID] = video_db.VideoDatabase(DBConnectionsRW[DBID][1])
                elif DBID == 'music':
                    SQLs[DBID] = music_db.MusicDatabase(DBConnectionsRW[DBID][1])
                elif DBID == 'texture':
                    SQLs[DBID] = texture_db.TextureDatabase(DBConnectionsRW[DBID][1])
                elif DBID == 'addon':
                    SQLs[DBID] = addon_db.AddonDatabase(DBConnectionsRW[DBID][1])
                elif DBID in ('tv', 'epg'):
                    SQLs[DBID] = common_db.CommonDatabase(DBConnectionsRW[DBID][1])
                else:
                    SQLs["emby"] = emby_db.EmbyDatabase(DBConnectionsRW[DBID][1])

def DBCloseRW(Databases, TaskId, SQLs):
    DBIDs = Databases.split(",")

    for DBID in DBIDs:
        if DBID in DBConnectionsRW:
            with utils.SafeLock(DBConnectionsRW[DBID][2]):
                DBConnectionsRW[DBID][0].commit()
                DBConnectionsRW[DBID][1].close() # curser close
                DBConnectionsRW[DBID][0].close() # db close

                if DBID in ('video', 'music', 'texture', 'epg', 'tv', 'addon'):
                    SQLs[DBID] = None
                else:
                    SQLs["emby"] = None

                DBConnectionsRW[DBID][0] = None
                DBConnectionsRW[DBID][1] = None
                DBConnectionsRW[DBID][3] = False
                DBConnectionsRW[DBID][2].notify_all()

            if utils.DebugLog: xbmc.log(f"EMBY.database.dbio (DEBUG): ---< DBRW: {DBID} / {TaskId} rows updated on db close", 1) # LOGDEBUG

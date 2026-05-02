import threading
import json
import unicodedata
import xbmc
from core import movies, videos, musicvideo, folder, boxsets, genre, musicgenre, musicartist, musicalbum, audio, tag, person, studio, playlist, series, season, episode, trailer, photoalbum, photo, common
from helper import utils, cache
from hooks import favorites
from . import dbio

LockPause = threading.Lock()
LockPauseBusy = threading.Lock()
LockLowPriorityWorkers = threading.Lock()
LockLibraryOps = threading.Lock()


class Library:
    def __init__(self, EmbyServer):
        xbmc.log(f"EMBY.database.library: -->[ Emby server {EmbyServer.ServerData['ServerId']}: library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.LibrarySynced = []
        self.LibrarySyncedKodiDBs = {}
        self.LibrarySyncedNames = {}
        self.LibrarySyncedContent = {}
        self.SettingsLoaded = False
        self.LockKodiStartSync = threading.Lock()
        self.LockDBRWOpen = threading.Lock()
        self.DatabaseInitCondition = threading.Condition(threading.Lock())
        self.SettingsLoadedCondition = threading.Condition(threading.Lock())
        self.ServerStartingId = f"{self.EmbyServer.ServerData['ServerId']}_server_starting"
        self.ServerBusyId = f"{self.EmbyServer.ServerData['ServerId']}_server_busy"
        self.ServerDatabaseInitId = f"{self.EmbyServer.ServerData['ServerId']}_database_init"
        self.ServerReconnectingId = f"{self.EmbyServer.ServerData['ServerId']}_server_reconnecting"
        self.ServerStartSyncId = f"{self.EmbyServer.ServerData['ServerId']}_server_startscync"
        self.RemoveId = f"{self.EmbyServer.ServerData['ServerId']}_remove"
        self.LibraryRemoveId = f"{self.EmbyServer.ServerData['ServerId']}_library_remove"
        self.LibraryAddId = f"{self.EmbyServer.ServerData['ServerId']}_library_add"
        self.UserDataId = f"{self.EmbyServer.ServerData['ServerId']}_userdata"
        self.UpdateId = f"{self.EmbyServer.ServerData['ServerId']}_update"
        self.UpdateParentsId = f"{self.EmbyServer.ServerData['ServerId']}_update_parents"
        self.LibraryRemoveCleanId = f"{self.EmbyServer.ServerData['ServerId']}_library_remove_clean"
        self.KodiStartSyncId = f"{self.EmbyServer.ServerData['ServerId']}_kodi_start_sync"
        self.MusicVideoLinks = f"{self.EmbyServer.ServerData['ServerId']}_musicvideo_links"
        self.SelectLibrariesId = f"{self.EmbyServer.ServerData['ServerId']}_select_libraries"
        self.JobBusy = False

    # Wait for database init
    def wait_DatabaseInit(self, WorkerId):
        if utils.DebugLog:
            xbmc.log(f"EMBY.database.library (DEBUG) -->[ WorkerId {WorkerId}: wait for database init ]", 1) # LOGINFO
            xbmc.log("EMBY.database.library (DEBUG): CONDITION: --->[ DatabaseInitCondition ]", 1) # LOGDEBUG

        with utils.SafeLock(self.DatabaseInitCondition):
            while utils.SyncPause.get(self.ServerDatabaseInitId, True):
                self.DatabaseInitCondition.wait(timeout=0.1)

                if utils.SystemShutdown:
                    if utils.DebugLog:
                        xbmc.log(f"EMBY.database.library (DEBUG): --<[ WorkerId {WorkerId}: wait for database init ]", 1) # LOGINFO
                        xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ DatabaseInitCondition ]", 1) # LOGDEBUG

                    return False

        if utils.DebugLog:
            xbmc.log(f"EMBY.database.library (DEBUG): --<[ WorkerId {WorkerId}: wait for database init ]", 1) # LOGINFO
            xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ DatabaseInitCondition ]", 1) # LOGDEBUG

        return True

    def open_Worker(self, WorkerId):
        if utils.DebugLog:
            xbmc.log(f"EMBY.database.library (DEBUG): -->[ WorkerId {WorkerId}: Worker_is_paused ]", 1) # LOGINFO
            xbmc.log("EMBY.database.library (DEBUG): CONDITION: --->[ SyncPauseCondition ]", 1) # LOGDEBUG

        WriteLog = True

        with utils.SafeLock(utils.SyncPauseCondition):
            while self.Worker_is_paused(WorkerId):
                utils.SyncPauseCondition.wait(timeout=0.1)

                if utils.SystemShutdown:
                    if utils.DebugLog:
                        xbmc.log(f"EMBY.database.library (DEBUG): --<[ WorkerId {WorkerId}: Worker_is_paused ]", 1) # LOGINFO
                        xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ SyncPauseCondition ]", 1) # LOGDEBUG

                    return False

                if WriteLog:
                    xbmc.log(f"EMBY.database.library: [ WorkerId {WorkerId}: Worker_is_paused ]", 1) # LOGINFO
                    WriteLog = False

        if utils.DebugLog:
            xbmc.log(f"EMBY.database.library (DEBUG): --<[ WorkerId {WorkerId}: Worker_is_paused ]", 1) # LOGINFO
            xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ SyncPauseCondition ]", 1) # LOGDEBUG

        return True

    def close_Worker(self, WorkerId, RefreshVideo, RefreshAudio, SQLs):
        self.close_EmbyDBRW(WorkerId, SQLs)
        common.CachedItemsMissing = {}
        common.CachedArtworkDownload = ()
        utils.close_ProgressBar(WorkerId)

        if RefreshVideo:
            utils.refresh_widgets(True)

        if RefreshAudio:
            utils.refresh_widgets(False)

    def open_EmbyDBRW(self, WorkerId, Priority):
        # if worker in progress, interrupt workers database ops (worker has lower priority) compared to all other Emby database (rw) ops
        if Priority and LockLowPriorityWorkers.locked() and self.LockDBRWOpen.locked():
            utils.update_SyncPause('priority', True)

        while not self.LockDBRWOpen.acquire(timeout=0.1):
            pass

        SQLs = {}
        dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], WorkerId, SQLs)
        return SQLs

    def close_EmbyDBRW(self, WorkerId, SQLs):
        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerId, SQLs)

        if self.LockDBRWOpen.locked():
            self.LockDBRWOpen.release()

        utils.update_SyncPause('priority', False)

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        SQLs = self.open_EmbyDBRW("set_syncdate", True)
        SQLs["emby"].update_LastIncrementalSync(TimestampUTC)
        SQLs["emby"].update_LastIncrementalSyncStart(TimestampUTC)
        self.close_EmbyDBRW("set_syncdate", SQLs)
        utils.set_syncdate(TimestampUTC)

    def load_LibrarySynced(self, SQLs):
        self.LibrarySynced = SQLs["emby"].get_LibrarySynced()
        LibrarySyncedMirrows = SQLs["emby"].get_LibrarySyncedMirrow()
        self.LibrarySyncedKodiDBs = {}
        self.LibrarySyncedNames = {}
        self.LibrarySyncedContent = {}

        for LibrarySyncedMirrowId, LibrarySyncedMirrowName, LibrarySyncedMirrowEmbyType, LibrarySyncedMirrowKodiDBs in LibrarySyncedMirrows:
            self.LibrarySyncedKodiDBs[f"{LibrarySyncedMirrowId}{LibrarySyncedMirrowEmbyType}"] = LibrarySyncedMirrowKodiDBs
            self.LibrarySyncedNames[LibrarySyncedMirrowId] = LibrarySyncedMirrowName

            if LibrarySyncedMirrowId in self.LibrarySyncedContent:
                self.LibrarySyncedContent[LibrarySyncedMirrowId] += (LibrarySyncedMirrowEmbyType,)
            else:
                self.LibrarySyncedContent[LibrarySyncedMirrowId] = (LibrarySyncedMirrowEmbyType,)

    def load_settings(self):
        xbmc.log(f"EMBY.database.library: --->[ Emby server {self.EmbyServer.ServerData['ServerId']}: load settings ]", 1) # LOGINFO
        self.ServerStartingId = f"{self.EmbyServer.ServerData['ServerId']}_server_starting"
        self.ServerBusyId = f"{self.EmbyServer.ServerData['ServerId']}_server_busy"
        self.ServerDatabaseInitId = f"{self.EmbyServer.ServerData['ServerId']}_database_init"
        self.ServerReconnectingId = f"{self.EmbyServer.ServerData['ServerId']}_server_reconnecting"
        self.ServerStartSyncId = f"{self.EmbyServer.ServerData['ServerId']}_server_startscync"
        self.RemoveId = f"{self.EmbyServer.ServerData['ServerId']}_remove"
        self.LibraryRemoveId = f"{self.EmbyServer.ServerData['ServerId']}_library_remove"
        self.LibraryAddId = f"{self.EmbyServer.ServerData['ServerId']}_library_add"
        self.UserDataId = f"{self.EmbyServer.ServerData['ServerId']}_userdata"
        self.UpdateId = f"{self.EmbyServer.ServerData['ServerId']}_update"
        self.UpdateParentsId = f"{self.EmbyServer.ServerData['ServerId']}_update_parents"
        self.LibraryRemoveCleanId = f"{self.EmbyServer.ServerData['ServerId']}_library_remove_clean"
        self.KodiStartSyncId = f"{self.EmbyServer.ServerData['ServerId']}_kodi_start_sync"
        self.MusicVideoLinks = f"{self.EmbyServer.ServerData['ServerId']}_musicvideo_links"
        self.SelectLibrariesId = f"{self.EmbyServer.ServerData['ServerId']}_select_libraries"
        utils.update_SyncPause(self.ServerDatabaseInitId, True)

        # Load essential data and prefetching Media tags
        SQLs = self.open_EmbyDBRW("load_settings", True)

        if SQLs["emby"].init_EmbyDB():
            self.load_LibrarySynced(SQLs)
        else:
            utils.set_settings('MinimumSetup', "INVALID DATABASE")
            self.close_EmbyDBRW("load_settings", SQLs)
            utils.restart_kodi()
            xbmc.log(f"EMBY.database.library: load settings: database corrupt: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: load settings ]", 3) # LOGERROR
            return

        self.close_EmbyDBRW("load_settings", SQLs)

        # Init database
        dbio.DBOpenRW("video", "load_settings", SQLs)
        SQLs["video"].add_Index()
        SQLs["video"].get_add_path(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/", None, None)
        dbio.DBCloseRW("video", "load_settings", SQLs)
        dbio.DBOpenRW("music", "load_settings", SQLs)
        SQLs["music"].add_Index()
        SQLs["music"].disable_rescan(utils.currenttime_kodi_format())
        dbio.DBCloseRW("music", "load_settings", SQLs)
        dbio.DBOpenRW("texture", "load_settings", SQLs)
        SQLs["texture"].add_Index()
        dbio.DBCloseRW("texture", "load_settings", SQLs)
        dbio.DBOpenRW("epg", "load_settings", SQLs)
        SQLs["epg"].analyze()
        dbio.DBCloseRW("epg", "load_settings", SQLs)
        dbio.DBOpenRW("tv", "load_settings", SQLs)
        SQLs["tv"].analyze()
        dbio.DBCloseRW("tv", "load_settings", SQLs)
        utils.update_SyncPause(self.ServerDatabaseInitId, False)
        self.SettingsLoaded = True

        with utils.SafeLock(self.DatabaseInitCondition):
            self.DatabaseInitCondition.notify_all()

        with utils.SafeLock(self.SettingsLoadedCondition):
            self.SettingsLoadedCondition.notify_all()

        with utils.SafeLock(utils.EmbyServerOnlineCondition):
            utils.EmbyServerOnlineCondition.notify_all()

        xbmc.log(f"EMBY.database.library: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: load settings ]", 1) # LOGINFO

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: --->[ {self.KodiStartSyncId} ]", 1) # LOGDEBUG

        with utils.SafeLock(self.LockKodiStartSync):
            if not utils.startsyncenabled or utils.SystemShutdown:
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] IncrementalSync disabled", 1) # LOGDEBUG
                return

            # Verify time sync
            _, UnixTime = utils.currenttime_kodi_format_and_unixtime()

            if UnixTime < 946684800: # 01-01-2000
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33751), icon=utils.icon, time=60000, sound=True)
                return

            NewSyncData = utils.currenttime()
            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): CONDITION: --->[ {self.KodiStartSyncId} ] SettingsLoadedCondition", 1) # LOGDEBUG

            with utils.SafeLock(self.SettingsLoadedCondition):
                while not self.SettingsLoaded:
                    self.SettingsLoadedCondition.wait(timeout=0.1)

                    if utils.SystemShutdown:
                        if utils.DebugLog:
                            xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 1", 1) # LOGDEBUG
                            xbmc.log(f"EMBY.database.library (DEBUG): CONDITION: ---<[ {self.KodiStartSyncId} ] SettingsLoadedCondition", 1) # LOGDEBUG

                        return

            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): CONDITION: ---<[ {self.KodiStartSyncId} ] SettingsLoadedCondition", 1) # LOGDEBUG

            if Firstrun:
                self.select_libraries("AddLibrarySelection")

            # Upsync downloaded content progress
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.KodiStartSyncId)
            DownlodedItems = embydb.get_DownloadItem()
            LastSyncTime = embydb.get_LastIncrementalSync()
            LastSyncTimeStart = embydb.get_LastIncrementalSyncStart()

            if not LastSyncTimeStart:
                LastSyncTimeStart = LastSyncTime

            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.KodiStartSyncId)
            videodb = dbio.DBOpenRO("video", self.KodiStartSyncId)

            for DownlodedItem in DownlodedItems:
                utils.ItemSkipUpdate.append(str(DownlodedItem[0]))
                Found, timeInSeconds, playCount, lastPlayed = videodb.get_Progress(DownlodedItem[2])

                if Found:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): Upsync offline content {DownlodedItem}", 1) # LOGDEBUG
                    self.EmbyServer.API.set_progress_upsync(DownlodedItem[0], int(timeInSeconds * 10000000), playCount, utils.convert_to_gmt(lastPlayed))  # Id, PlaybackPositionTicks, PlayCount, LastPlayedDate

            dbio.DBCloseRO("video", self.KodiStartSyncId)
            UpdateData = [[], []]

            if utils.SystemShutdown:
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 2", 1) # LOGDEBUG
                return

            # Retrieve changes
            if LastSyncTimeStart:
                utils.SyncPause[self.ServerStartSyncId] = True
                xbmc.log(f"EMBY.database.library: [ {self.KodiStartSyncId} ] last synced: {LastSyncTime} / {LastSyncTimeStart}", 1) # LOGINFO
                utils.create_ProgressBar(self.KodiStartSyncId, utils.Translate(33199), utils.Translate(33445))
                xbmc.log(f"EMBY.database.library: -->[ {self.KodiStartSyncId} ] Kodi companion", 1) # LOGINFO
                result = self.EmbyServer.API.get_sync_queue(LastSyncTimeStart)  # Kodi companion

                if 'ItemsRemoved' in result:
                    if result['ItemsRemoved']:
                        self.removed(result['ItemsRemoved'], False, False)
                elif utils.verifyKodiCompanion:
                    utils.Dialog.ok(utils.addon_name, utils.Translate(33716))

                xbmc.log(f"EMBY.database.library: --<[ {self.KodiStartSyncId} ] Kodi companion ]", 1) # LOGINFO
                ProgressBarTotal = len(self.LibrarySynced) / 100
                ProgressBarIndex = 0

                for LibrarySyncedId, LibrarySyncedName, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                    if utils.SystemShutdown:
                        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 3", 1) # LOGDEBUG
                        utils.close_ProgressBar(self.KodiStartSyncId)
                        utils.SyncPause[self.ServerStartSyncId] = False
                        return

                    xbmc.log(f"EMBY.database.library: [ {self.KodiStartSyncId} ] {LibrarySyncedName} / {LibrarySyncedEmbyType}", 1) # LOGINFO
                    LibraryName = ""
                    ProgressBarIndex += 1

                    if LibrarySyncedId in self.EmbyServer.Views.ViewItems:
                        LibraryName = self.EmbyServer.Views.ViewItems[LibrarySyncedId][0]

                        if utils.SystemShutdown:
                            utils.close_ProgressBar(self.KodiStartSyncId)
                            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 4", 1) # LOGDEBUG
                            utils.SyncPause[self.ServerStartSyncId] = False
                            return

                        utils.update_ProgressBar(self.KodiStartSyncId, ProgressBarIndex / ProgressBarTotal, utils.Translate(33199), f"{LibraryName} / {LibrarySyncedEmbyType}")

                    if not LibraryName and LibrarySyncedEmbyType != "Person":
                        xbmc.log(f"EMBY.database.library: [ {self.KodiStartSyncId} ] remove library {LibrarySyncedId}", 1) # LOGINFO
                        continue

                    ItemIndex = 0
                    UpdateDataTemp = 10000 * [()] # pre allocate memory
                    UpdateUserDataTemp = 10000 * [()] # pre allocate memory

                    if LibrarySyncedEmbyType == "Folder":
                        Params = {'MinDateLastSaved': LastSyncTime}
                    elif LibrarySyncedEmbyType in ("Person", "BoxSet"): # No realtime sync supported by Emby server (at least not for people artwork and boxsets)
                        Params = {'MinDateLastSavedForUser': LastSyncTimeStart, "Fields": "UserDataLastPlayedDate"}
                    else:
                        Params = {'MinDateLastSavedForUser': LastSyncTime, "Fields": "UserDataLastPlayedDate"}

                    for Item in self.EmbyServer.API.get_Items(LibrarySyncedId, (LibrarySyncedEmbyType,), True, Params, "", None, True):
                        if utils.SystemShutdown:
                            utils.close_ProgressBar(self.KodiStartSyncId)
                            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 5", 1) # LOGDEBUG
                            utils.SyncPause[self.ServerStartSyncId] = False
                            return

                        if ItemIndex >= 10000:
                            UpdateData[0] += UpdateDataTemp
                            UpdateData[1] += UpdateUserDataTemp
                            UpdateDataTemp = 10000 * [()] # pre allocate memory
                            UpdateUserDataTemp = 10000 * [()] # pre allocate memory
                            ItemIndex = 0

                        self.set_recording_type(Item)
                        UpdateDataTemp[ItemIndex] = (Item['Id'], Item['Type'], LibrarySyncedId)

                        if Item['Type'] != "Folder": # Folder has no userdata
                            UpdateUserDataTemp[ItemIndex] = (Item['Id'], Item['Type'], Item['UserData'].get("PlaybackPositionTicks", None), Item['UserData'].get("PlayCount", None), Item['UserData'].get("IsFavorite", None), Item['UserData'].get("Played", None), Item['UserData'].get("LastPlayedDate", None), Item['UserData'].get("PlayedPercentage", None), Item['UserData'].get("UnplayedItemCount", None))

                        ItemIndex += 1

                    UpdateData[0] += UpdateDataTemp
                    UpdateData[1] += UpdateUserDataTemp

                utils.close_ProgressBar(self.KodiStartSyncId)

                if utils.SystemShutdown:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ] shutdown 6", 1) # LOGDEBUG
                    utils.SyncPause[self.ServerStartSyncId] = False
                    return

            # Run jobs
            # Items updates
            if UpdateData[0]:
                UpdateData[0] = list(dict.fromkeys(UpdateData[0])) # filter doubles

                if () in UpdateData[0]:  # Remove empty
                    UpdateData[0].remove(())

                if UpdateData[0]:
                    self.updated(UpdateData[0], False, False)

            # Userdata updated
            if UpdateData[1]:
                UpdateData[1] = list(dict.fromkeys(UpdateData[1])) # filter doubles

                if () in UpdateData[1]:  # Remove empty
                    UpdateData[1].remove(())

                if UpdateData[1]:
                    self.userdata(UpdateData[1], False, False)

            utils.SyncPause[self.ServerStartSyncId] = False
            self.RunJobs(False, True)

        self.set_syncdate(NewSyncData)
        self.SyncLiveTVEPG()
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): THREAD: ---<[ {self.KodiStartSyncId} ]", 1) # LOGDEBUG

    # Userdata change is an high priority task
    def worker_userdata(self, IncrementalSync):
        UpdateUserDataCached = ()

        if not self.wait_DatabaseInit(self.UserDataId):
            return

        SQLs = {"emby": dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.UserDataId)}
        UserDataItems = SQLs["emby"].get_Userdata()
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.UserDataId} ] queue size: {len(UserDataItems)}", 1) # LOGDEBUG

        if not UserDataItems:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.UserDataId)
            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UserDataId} ] worker userdata empty", 1) # LOGDEBUG
            return

        utils.create_ProgressBar(self.UserDataId, utils.Translate(33199), utils.Translate(33178))
        RecordsPercent = len(UserDataItems) / 100
        UpdateItems, Others = self.ItemsSort(self.worker_userdata_generator, SQLs, UserDataItems, False, RecordsPercent)

        if not SQLs['emby']:
            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UserDataId} ] ItemsSort", 1) # LOGDEBUG
            return

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.UserDataId)
        SQLs = self.open_EmbyDBRW(self.UserDataId, True)
        RefreshAudio = False
        RefreshVideo = False
        RefreshWidgets = False

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            if content_available(CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                dbio.DBOpenRW(KodiDBs, self.UserDataId, SQLs)

                for Items in CategoryItems:
                    if not Items:
                        continue

                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                    ClassObject = None
                    ReleaseCounter = 0

                    for index, Item in enumerate(Items, 1):
                        ReleaseCounter += 1

                        if ReleaseCounter % 50 == 0:
                            xbmc.sleep(0) # release GIL

                        Item = json.loads(Item)

                        if not ClassObject:
                            ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                        SQLs["emby"].delete_Userdata(Item["Id"])
                        Continue, Update = self.update_UserData(index / RecordsPercent, index, Item, SQLs, KodiDBs, IncrementalSync, ClassObject, True, self.UserDataId, True)
                        UpdateUserDataCached += ((str(Item['Id']), Item.get('PlaybackPositionTicks', 0), Item.get('LastPlayedDate', ""), common.set_PlayCount(Item), False),)

                        if Update:
                            RefreshWidgets = True

                        if not Continue:
                            del ClassObject
                            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UserDataId} ] worker userdata interrupt", 1) # LOGDEBUG
                            return

                    del ClassObject

                dbio.DBCloseRW(KodiDBs, self.UserDataId, SQLs)

        for Other in Others: # Unsynced content
            Other = json.loads(Other)

            if not SQLs["emby"].exist_UpdateItem(Other['Id']): # Do not remove items which are flagged for update
                SQLs["emby"].delete_Userdata(Other['Id'])
                UpdateUserDataCached += ((str(Other['Id']), Other.get('PlaybackPositionTicks', 0), Other.get('LastPlayedDate', ""), common.set_PlayCount(Other), False),)

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
        cache.update_querycache_userdata(UpdateUserDataCached)
        del UpdateUserDataCached

        if Others:
            self.close_Worker(self.UserDataId, True, True, SQLs)
        else:
            if RefreshWidgets:
                self.close_Worker(self.UserDataId, RefreshVideo, RefreshAudio, SQLs)
            else:
                self.close_Worker(self.UserDataId, False, False, SQLs)

        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UserDataId} ] worker userdata completed", 1) # LOGDEBUG

    def worker_userdata_generator(self, SQLs, UserDataItems, RecordsPercent):
        for index, UserDataItem in enumerate(UserDataItems, 1): # UserDataItem = EmbyId, EmbyType, EmbyPlaybackPositionTicks, EmbyPlayCount, EmbyIsFavorite, EmbyPlayed, EmbyLastPlayedDate
            utils.update_ProgressBar(self.UserDataId, index / RecordsPercent, utils.Translate(33178), str(UserDataItem[0]))
            MetaData = SQLs["emby"].get_UserData_MetaData(UserDataItem[0], UserDataItem[1])
            MetaData.update({"Id": UserDataItem[0], 'PlaybackPositionTicks': UserDataItem[2], 'PlayCount': UserDataItem[3], 'IsFavorite': UserDataItem[4], 'LastPlayedDate': UserDataItem[6], 'Played': UserDataItem[5], 'PlayedPercentage': UserDataItem[7], 'UnplayedItemCount': UserDataItem[8]})

            if MetaData['KodiItemId']:
                yield True, MetaData
            else: # skip if item is not synced
                yield False, MetaData
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): Emby server {self.EmbyServer.ServerData['ServerId']}: Skip not synced item: {UserDataItem[0]}", 1) # LOGDEBUG

    def worker_update(self, IncrementalSync):
        MusicVideoLinks = False

        while True: # While running update additional updates migth be addded
            with utils.SafeLock(LockLowPriorityWorkers):
                if not self.wait_DatabaseInit(self.UpdateId):
                    return False

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.UpdateId)
                UpdateItems, UpdateItemsCount, KodiDBMappingUpdate = embydb.get_UpdateItem()
                RemoveItems = embydb.empty_RemoveItem()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.UpdateId)
                del embydb

            # Re-run if removed items are added while waiting for updates
            if RemoveItems:
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): [ {self.UpdateId} ] Worker update, removed items found, trigger removal", 1) # LOGDEBUG
                self.worker_remove(IncrementalSync)

            # Process updates
            with utils.SafeLock(LockLowPriorityWorkers):
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.UpdateId} ] queue size: {UpdateItemsCount}", 1) # LOGDEBUG

                if not UpdateItemsCount: # Job done
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UpdateId} ] worker update empty", 1) # LOGDEBUG

                    if utils.LinkMusicVideos and MusicVideoLinks:
                        self.refresh_musicvideolinks()

                    return True

                if not self.open_Worker(self.UpdateId):
                    return False

                utils.create_ProgressBar(self.UpdateId, utils.Translate(33199), utils.Translate(33178))
                RecordsPercent = UpdateItemsCount / 100
                index = 0
                UpdateItems, Others = self.ItemsSort(self.worker_update_generator, {}, UpdateItems, False, RecordsPercent)
                RefreshAudio = False
                RefreshVideo = False
                SQLs = self.open_EmbyDBRW(self.UpdateId, False)

                for KodiDBs, CategoryItems in list(UpdateItems.items()):
                    Continue = True

                    if content_available(CategoryItems):
                        dbio.DBOpenRW(KodiDBs, self.UpdateId, SQLs)

                        for Items in CategoryItems:
                            if not Items:
                                continue

                            RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                            ClassObject = None
                            ReleaseCounter = 0

                            for Item in Items:
                                ReleaseCounter += 1

                                if ReleaseCounter % 50 == 0:
                                    xbmc.sleep(0) # release GIL

                                Item = json.loads(Item)

                                if not MusicVideoLinks and Item['Type'] in ("Audio", "MusicVideo") and Item.get('ExtraType', "") != "ThemeSong":
                                    MusicVideoLinks = True

                                if not ClassObject:
                                    ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                                if 'EmbyParentId' in Item:
                                    SQLs["emby"].delete_UpdateItem_Parent(Item['EmbyParentId'], Item['EmbyParentType'], Item['LibraryId'], Item['KodiParentId'])
                                else:
                                    SQLs["emby"].delete_UpdateItem(Item['Id'])

                                index += 1

                                if Item['Id'] in KodiDBMappingUpdate:
                                    ClassObject.KodiDBMapping = KodiDBMappingUpdate[Item['Id']]

                                if not self.update_Item(index / RecordsPercent, index, Item, SQLs, KodiDBs, IncrementalSync, ClassObject, self.UpdateId):
#                                    self.EmbyServer.API.update_Progress(self.UpdateId, -1)
                                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.UpdateId} ] worker update interrupt", 1) # LOGDEBUG
                                    del ClassObject
                                    return False

                            del ClassObject

                        dbio.DBCloseRW(KodiDBs, self.UpdateId, SQLs)

                    if not Continue:
                        break

#                self.EmbyServer.API.update_Progress(self.UpdateId, -1)

                for Other in Others:
                    Other = json.loads(Other)

                    if 'EmbyParentId' in Other:
                        SQLs["emby"].delete_UpdateItem_Parent(Other['EmbyParentId'], Other['EmbyParentType'], Other['LibraryId'], Other['KodiParentId'])
                    else:
                        SQLs["emby"].delete_UpdateItem(Other['Id'])

                SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
                cache.reset_querycache()

                if Others:
                    self.close_Worker(self.UpdateId, True, True, SQLs)
                else:
                    self.close_Worker(self.UpdateId, RefreshVideo, RefreshAudio, SQLs)

    def worker_update_generator(self, SQLs, UpdateItems, RecordsPercent):
        Counter = 0

        for LibraryId, UpdateItemsArray in list(UpdateItems.items()):
            for ContentType, UpdateItemsData in list(UpdateItemsArray.items()):
                if not UpdateItemsData:
                    continue

                if LibraryId in self.EmbyServer.Views.ViewItems:
                    LibraryName = self.EmbyServer.Views.ViewItems[LibraryId][0]
                else:
                    LibraryName = LibraryId

                utils.update_ProgressBar(self.UpdateId, Counter / RecordsPercent, utils.Translate(33734), f"{LibraryName} / {ContentType}")

                # Update Items is subcontent of a ParentItem
                if isinstance(UpdateItemsData[0], dict):
                    UpdateItemsDataTemp = UpdateItemsData.copy()
                    utils.create_ProgressBar(self.UpdateParentsId, utils.Translate(33199), utils.Translate(33178))
                    RecordsPercentParents = len(UpdateItemsData) / 100

                    for ParentCounter, ParentItem in enumerate(UpdateItemsData): # {'EmbyParentId': 76037, 'EmbyParentType': 'Movie'}
                        if ContentType == "Trailer":
                            for TrailerLocal in self.EmbyServer.API.get_local_trailers(ParentItem['EmbyParentId']):
                                TrailerLocal.update({'EmbyParentType': ParentItem['EmbyParentType'], 'LibraryId': LibraryId, 'EmbyParentId': ParentItem['EmbyParentId'], 'KodiParentId': ParentItem['KodiParentId']})
                                if ParentItem in UpdateItemsDataTemp:
                                    UpdateItemsDataTemp.remove(ParentItem)

                                yield True, TrailerLocal
                        elif ContentType == "Special": # Specials
                            for Special in self.EmbyServer.API.get_specialfeatures(ParentItem['EmbyParentId']):
                                Special.update({'EmbyParentType': ParentItem['EmbyParentType'], 'LibraryId': LibraryId, 'EmbyParentId': ParentItem['EmbyParentId'], 'KodiParentId': ParentItem['KodiParentId']})
                                if ParentItem in UpdateItemsDataTemp:
                                    UpdateItemsDataTemp.remove(ParentItem)

                                yield True, Special
                        elif ContentType == "Theme": # ThemeSong
                            Themes = self.EmbyServer.API.get_themes(ParentItem['EmbyParentId'])

                            if 'ThemeSongsResult' in Themes:
                                for ThemeSong in Themes['ThemeSongsResult']['Items']:
                                    ThemeSong.update({'EmbyParentType': ParentItem['EmbyParentType'], 'LibraryId': LibraryId, 'EmbyParentId': ParentItem['EmbyParentId'], 'KodiParentId': ParentItem['KodiParentId']})

                                    if ParentItem in UpdateItemsDataTemp:
                                        UpdateItemsDataTemp.remove(ParentItem)

                                    yield True, ThemeSong

                            if 'ThemeVideosResult' in Themes:
                                for ThemeVideo in Themes['ThemeVideosResult']['Items']:
                                    ThemeVideo.update({'EmbyParentType': ParentItem['EmbyParentType'], 'LibraryId': LibraryId, 'EmbyParentId': ParentItem['EmbyParentId'], 'KodiParentId': ParentItem['KodiParentId']})

                                    if ParentItem in UpdateItemsDataTemp:
                                        UpdateItemsDataTemp.remove(ParentItem)

                                    yield True, ThemeVideo

                        utils.update_ProgressBar(self.UpdateParentsId, ParentCounter / RecordsPercentParents, utils.Translate(33734), f"{LibraryName} / {ContentType}")

                    utils.close_ProgressBar(self.UpdateParentsId)

                    for UpdateItemDataTemp in UpdateItemsDataTemp:
                        UpdateItemDataTemp['LibraryId'] = LibraryId
                        yield False, UpdateItemDataTemp
                else: # Get Items by Ids
                    if ContentType == "unknown":
                        ContentType = ["Person", "Studio", "Genre", "Tag", "Trailer", "BoxSet", "Movie", "Video", "Series", "Season", "Episode", "MusicArtist", "MusicGenre", "MusicVideo", "MusicAlbum", "Audio", "Playlist", "Folder", "PhotoAlbum", "Photo"]
                    else:
                        ContentType = [ContentType]

                    UpdateItemsDataTemp = UpdateItemsData.copy()

                    for Item in self.EmbyServer.API.get_Items_Ids(UpdateItemsData, ContentType, False, False, "", LibraryId, {}, {"Object": self.pause_workers, "Params": ("Startsync_http", SQLs, None)}, False):
                        Counter += 1

                        if Item['Id'] in UpdateItemsData:
                            UpdateItemsData.remove(Item['Id'])

                        yield True, Item

                    # Remove not detected Items
                    for UpdateItemsIdTemp in UpdateItemsDataTemp:
                        if UpdateItemsIdTemp in UpdateItemsData:
                            UpdateItemsData.remove(UpdateItemsIdTemp)
                            yield False, {'Id': UpdateItemsIdTemp}

    def worker_remove(self, IncrementalSync):
        with utils.SafeLock(LockLowPriorityWorkers):
            if not self.wait_DatabaseInit(self.RemoveId):
                return False

            while True: # Removed items can add additional subitems to be removed
                EmbyDB = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.RemoveId)
                RemoveItems = EmbyDB.get_RemoveItem()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.RemoveId)
                del EmbyDB
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.RemoveId} ] queue size: {len(RemoveItems)}", 1) # LOGDEBUG

                if not RemoveItems:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.RemoveId} ] worker remove empty", 1) # LOGDEBUG
                    return True

                if not self.open_Worker(self.RemoveId):
                    return False

                RefreshAudio = False
                RefreshVideo = False
                utils.create_ProgressBar(self.RemoveId, utils.Translate(33199), utils.Translate(33261))
                RecordsPercent = len(RemoveItems) / 100
                SQLs = self.open_EmbyDBRW(self.RemoveId, False)
                UpdateItems, Others = self.ItemsSort(self.worker_remove_generator, SQLs, RemoveItems, True, RecordsPercent)

                if not SQLs['emby']:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.RemoveId} ] ItemsSort", 1) # LOGDEBUG
                    return False

                for KodiDBs, CategoryItems in list(UpdateItems.items()):
                    if content_available(CategoryItems):
                        dbio.DBOpenRW(KodiDBs, self.RemoveId, SQLs)

                        for Items in CategoryItems:
                            if not Items:
                                continue

                            RecordsPercent = len(Items) / 100
                            RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                            ClassObject = None
                            ReleaseCounter = 0

                            for index, Item in enumerate(Items, 1):
                                ReleaseCounter += 1

                                if ReleaseCounter % 50 == 0:
                                    xbmc.sleep(0) # release GIL

                                Item = json.loads(Item)

                                if not ClassObject:
                                    ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                                SQLs["emby"].delete_RemoveItem(Item['Id'])

                                if not self.remove_Item(index / RecordsPercent, index, Item, SQLs, KodiDBs, IncrementalSync, ClassObject):
                                    del ClassObject
                                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.RemoveId} ] worker remove interrupt", 1) # LOGDEBUG
                                    return False

                            del ClassObject

                        dbio.DBCloseRW(KodiDBs, self.RemoveId, SQLs)

                for Other in Others:
                    Other = json.loads(Other)
                    SQLs["emby"].delete_RemoveItem(Other['Id'])

                SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
                cache.reset_querycache()

                if Others:
                    utils.refresh_DynamicNode()
                    self.close_Worker(self.RemoveId, True, True, SQLs)
                else:
                    self.close_Worker(self.RemoveId, RefreshVideo, RefreshAudio, SQLs)

                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.RemoveId} ] worker remove completed", 1) # LOGDEBUG

    def worker_remove_generator(self, SQLs, RemoveItems, RecordsPercent):
        for index, RemoveItem in enumerate(RemoveItems, 1):
            if not self.pause_workers(self.RemoveId, SQLs, None):
                break

            utils.update_ProgressBar(self.RemoveId, index / RecordsPercent, utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = SQLs["emby"].get_remove_generator_items(RemoveItem[0], RemoveItem[1])

            for FoundRemoveItem in FoundRemoveItems:
                if RemoveItem[1]:
                    FoundRemoveItem['LibraryId'] = str(RemoveItem[1])
                else:
                    FoundRemoveItem['LibraryId'] = ""

                yield True, FoundRemoveItem

            if not FoundRemoveItems:
                yield False, {'Id': RemoveItem[0]}

    def worker_library_remove(self):
        with utils.SafeLock(LockLibraryOps):
            with utils.SafeLock(LockLowPriorityWorkers):
                if not self.wait_DatabaseInit(self.LibraryRemoveId):
                    return False

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.LibraryRemoveId)
                RemovedLibraries = embydb.get_LibraryRemove()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.LibraryRemoveId)
                del embydb
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.LibraryRemoveId} ] queue size: {len(RemovedLibraries)}", 1) # LOGDEBUG

                if not RemovedLibraries:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryRemoveId} ] worker library empty", 1) # LOGDEBUG
                    return True

                if not self.open_Worker(self.LibraryRemoveId):
                    return False

                utils.create_ProgressBar(self.LibraryRemoveId, utils.Translate(33199), utils.Translate(33184))
                RemovedLibrariesPercent = len(RemovedLibraries) / 100
                SQLs = self.open_EmbyDBRW(self.LibraryRemoveId, False)

                for RemovedLibraryIndex, RemovedLibrary in enumerate(RemovedLibraries):
                    SQLs["emby"].remove_LibraryRemove(RemovedLibrary[0])
                    utils.update_ProgressBar(self.LibraryRemoveId, RemovedLibraryIndex / RemovedLibrariesPercent, utils.Translate(33184), RemovedLibrary[1])
                    SQLs["emby"].add_remove_library_items(RemovedLibrary[0])
                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed library: {RemovedLibrary[0]} ]", 1) # LOGINFO
                    dbio.DBOpenRW("video", self.LibraryRemoveId, SQLs)
                    SQLs["video"].delete_path(f"{utils.AddonModePath}tvshows/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}movies/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}musicvideos/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    dbio.DBCloseRW("video", self.LibraryRemoveId, SQLs)
                    dbio.DBOpenRW("music", self.LibraryRemoveId, SQLs)
                    SQLs["music"].delete_path(f"{utils.AddonModePath}audio/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    dbio.DBCloseRW("music", self.LibraryRemoveId, SQLs)
                    self.EmbyServer.Views.delete_playlist_by_id(RemovedLibrary[0])
                    self.EmbyServer.Views.delete_node_by_id(RemovedLibrary[0])
                    utils.notify_event("library_remove", {"EmbyId": RemovedLibrary[0]}, True)

                self.load_LibrarySynced(SQLs)
                self.close_Worker(self.LibraryRemoveId, True, True, SQLs)

        if RemovedLibraries:
            if self.worker_remove(False):
                SQLs = self.open_EmbyDBRW(self.LibraryRemoveCleanId, True)

                for RemovedLibrary in RemovedLibraries:
                    SQLs["emby"].remove_LibrarySyncedMirrow(RemovedLibrary[0])

                self.load_LibrarySynced(SQLs)
                self.close_EmbyDBRW(self.LibraryRemoveCleanId, SQLs)
                self.worker_library_add()

            self.EmbyServer.Views.update_nodes()
            cache.reset_querycache()

        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryRemoveId} ] worker library completed", 1) # LOGDEBUG
        return True

    def worker_library_add(self):
        with utils.SafeLock(LockLibraryOps):
            with utils.SafeLock(LockLowPriorityWorkers):
                if not self.wait_DatabaseInit(self.LibraryAddId):
                    return

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.LibraryAddId)
                AddedLibraries = embydb.get_LibraryAdd()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.LibraryAddId)
                del embydb

                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.LibraryAddId} ] queue size: {len(AddedLibraries)}", 1) # LOGDEBUG

                if not AddedLibraries:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryAddId} ] worker library empty", 1) # LOGDEBUG
                    return

                if not self.open_Worker(self.LibraryAddId):
                    return

                utils.create_ProgressBar(self.LibraryAddId, utils.Translate(33199), utils.Translate(33238))
                GenreUpdate = False
                StudioUpdate = False
                TagUpdate = False
                MusicGenreUpdate = False
                PersonUpdate = False
                MusicArtistUpdate = False
                MusicVideoLinks = False
                newContent = utils.newContent
                utils.newContent = False  # Disable new content notification on init sync
                SQLs = self.open_EmbyDBRW(self.LibraryAddId, False)
                SQLs["emby"].delete_Index()

                # remove index (for faster inserts)
                dbio.DBOpenRW('video', self.LibraryAddId, SQLs)
                SQLs["video"].delete_Index()
                dbio.DBCloseRW('video', self.LibraryAddId, SQLs)
                dbio.DBOpenRW('music', self.LibraryAddId, SQLs)
                SQLs["music"].delete_Index()
                dbio.DBCloseRW('music', self.LibraryAddId, SQLs)
                dbio.DBOpenRW('texture', self.LibraryAddId, SQLs)
                SQLs["texture"].delete_Index()
                dbio.DBCloseRW('texture', self.LibraryAddId, SQLs)

                # Add libraries
                AddedLibrariesPercent = len(AddedLibraries) / 100

                for AddedLibraryIndex, AddedLibrary in enumerate(AddedLibraries): # AddedLibrary -> LibraryId, LibraryName, EmbyType, KodiDB, KodiDBs
                    AddedLibraryProgress = int(AddedLibraryIndex / AddedLibrariesPercent)

                    if AddedLibrary[2] == "MusicGenre":
                        MusicGenreUpdate = True
                    elif AddedLibrary[2] == "Genre":
                        GenreUpdate = True
                    elif AddedLibrary[2] == "Studio":
                        StudioUpdate = True
                    elif AddedLibrary[2] == "Tag":
                        TagUpdate = True
                    elif AddedLibrary[2] == "MusicArtist":
                        MusicArtistUpdate = True
                    elif AddedLibrary[2] == "Person":
                        PersonUpdate = True
                    elif AddedLibrary[2] in ("Audio", "MusicVideo"):
                        MusicVideoLinks = True

                    utils.update_ProgressBar(self.LibraryAddId, AddedLibraryProgress, utils.Translate(33238), AddedLibrary[1])
                    SQLs["emby"].add_LibrarySyncedMirrow(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    self.load_LibrarySynced(SQLs)
                    dbio.DBOpenRW(AddedLibrary[3], self.LibraryAddId, SQLs)
                    self.EmbyServer.API.update_Progress(self.LibraryAddId, 0)

                    if AddedLibrary[2] in ("Movie", "Video", "MusicVideo", "Series") and "video" in SQLs and SQLs["video"]:
                        TagObject = tag.Tag(self.EmbyServer, SQLs)
                        TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}00{AddedLibrary[0]}", "Name": AddedLibrary[1], "Memo": "library"}, False) # add library name as tag

                        if AddedLibrary[2] in ("Movie", "Video"):
                            TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}01{AddedLibrary[0]}", "Name": "Movies (Favorites)", "Memo": "favorite"}, False) # add library favorits as tag
                        elif AddedLibrary[2] == "MusicVideo":
                            TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}02{AddedLibrary[0]}", "Name": "Musicvideos (Favorites)", "Memo": "favorite"}, False) # add library favorits as tag
                        elif AddedLibrary[2] == "Series":
                            TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}03{AddedLibrary[0]}", "Name": "TVShows (Favorites)", "Memo": "favorite"}, False) # add library favorits as tag

                        del TagObject

                    # Add Item
                    ClassObject = self.load_libraryObject(AddedLibrary[2], SQLs)

                    for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(AddedLibrary[0], (AddedLibrary[2],), False, {}, self.LibraryAddId, {"Object": self.pause_workers, "Params": (self.LibraryAddId, SQLs, ClassObject)}, True), 1):
                        # Add Content
                        Item["LibraryId"] = AddedLibrary[0]
                        self.EmbyServer.API.update_Progress(self.LibraryAddId, ItemIndex)

                        if not self.update_Item(AddedLibraryProgress, ItemIndex, Item, SQLs, AddedLibrary[3], False, ClassObject, self.LibraryAddId):
                            del ClassObject
                            self.EmbyServer.API.update_Progress(self.LibraryAddId, -1)
                            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryAddId} ] paused", 1) # LOGDEBUG
                            return

                        # Add UserData
                        UpdateKodiFavorites = AddedLibrary[2] not in ("MusicGenre", "Genre", "Studio", "Tag", "MusicArtist", "Person") # skip favorite updates, they must be refreshed last
                        Continue, _ = self.update_UserData(AddedLibraryProgress, ItemIndex, Item, SQLs, AddedLibrary[3], False, ClassObject, UpdateKodiFavorites, self.LibraryAddId, False)

                        if not Continue:
                            del ClassObject
                            self.EmbyServer.API.update_Progress(self.LibraryAddId, -1)
                            utils.close_ProgressBar(self.LibraryAddId)
                            if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryAddId} ] paused 2", 1) # LOGDEBUG
                            return

                    del ClassObject

                    if not SQLs["emby"]:
                        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryAddId} ] closed database", 1) # LOGDEBUG-> db can be closed via http busyfunction
                        return

                    SQLs["emby"].add_LibrarySynced(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    SQLs["emby"].remove_LibraryAdd(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    self.load_LibrarySynced(SQLs)
                    dbio.DBCloseRW(AddedLibrary[3], self.LibraryAddId, SQLs)
                    utils.notify_event("library_add", {"EmbyId": AddedLibrary[0]}, True)

                # add index
                dbio.DBOpenRW('video', self.LibraryAddId, SQLs)
                SQLs["video"].add_Index()
                dbio.DBCloseRW('video', self.LibraryAddId, SQLs)
                dbio.DBOpenRW('music', self.LibraryAddId, SQLs)
                SQLs["music"].add_Index()
                dbio.DBCloseRW('music', self.LibraryAddId, SQLs)
                dbio.DBOpenRW("texture", self.LibraryAddId, SQLs)
                SQLs["texture"].add_Index()
                dbio.DBCloseRW("texture", self.LibraryAddId, SQLs)
                SQLs["emby"].add_Index()
                self.close_Worker(self.LibraryAddId, True, True, SQLs)

                # Update musicvideo links
                if utils.LinkMusicVideos and MusicVideoLinks:
                    self.refresh_musicvideolinks()

                # Update favorites for subitems
                if GenreUpdate:
                    favorites.update_Genre(self.EmbyServer)

                if StudioUpdate:
                    favorites.update_Studio(self.EmbyServer)

                if TagUpdate:
                    favorites.update_Tag(self.EmbyServer)

                if MusicGenreUpdate:
                    favorites.update_MusicGenre(self.EmbyServer)

                if PersonUpdate:
                    favorites.update_Person(self.EmbyServer)

                if MusicArtistUpdate:
                    favorites.update_MusicArtist(self.EmbyServer)

                # refresh
                utils.newContent = newContent
                self.EmbyServer.Views.update_nodes()
                cache.reset_querycache()
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.LibraryAddId} ] worker library completed", 1) # LOGDEBUG
        #        utils.sleep(2) # give Kodi time to catch up (otherwise could cause crashes)
        #        xbmc.executebuiltin('ReloadSkin()') # Skin reload broken in Kodi 21

        self.RunJobs(False, False)

    # Process item operations
    def update_Item(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, IncrementalSync, ClassObject, WorkerId):
        self.set_recording_type(Item)

        with utils.SafeLock(LockPause):
            Ret = ClassObject.change(Item, IncrementalSync)

        if "Name" in Item:
            ProgressMsg = Item.get('Name', "unknown")
        elif "Path" in Item:
            ProgressMsg = Item['Path']
        else:
            ProgressMsg = "unknown"

        utils.update_ProgressBar(WorkerId, ProgressValue, f"{Item['Type']}: {ItemIndex}", ProgressMsg)

        if Ret and utils.newContent:
            utils.Dialog.notification(heading=f"{utils.Translate(33049)} {Item['Type']}", message=Item.get('Name', "unknown"), icon=utils.icon, time=utils.newContentTime, sound=False)

        if not self.pause_workers(WorkerId, SQLs, ClassObject):
            return False

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, WorkerId, SQLs)
            self.close_Worker(WorkerId, False, False, SQLs)
            if utils.DebugLog: xbmc.log(f"EMBY.database.library: [ {WorkerId} ] shutdown 2", 1) # LOGINFO
            return False

        del Item
        return True

    def update_UserData(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, IncrementalSync, ClassObject, UpdateFavorite, WorkerId, UpdateProgress):
        if UpdateProgress:
            utils.update_ProgressBar(WorkerId, ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))

        Update = ClassObject.userdata(Item, IncrementalSync, UpdateFavorite)

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, WorkerId, SQLs)
            self.close_Worker(WorkerId, False, False, SQLs)
            xbmc.log(f"EMBY.database.library: [ {WorkerId} ] shutdown 2", 1) # LOGINFO
            return False, False

        del Item
        return True, Update

    def remove_Item(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, IncrementalSync, ClassObject):
        utils.update_ProgressBar(self.RemoveId, ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))

        with utils.SafeLock(LockPause):
            ClassObject.remove(Item, IncrementalSync)

        if not self.pause_workers(self.RemoveId, SQLs, ClassObject):
            return False

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, self.RemoveId, SQLs)
            self.close_Worker(self.RemoveId, False, False, SQLs)
            xbmc.log(f"EMBY.database.library: [ {self.RemoveId} ] shutdown 2", 1) # LOGINFO
            return False

        del Item
        return True

    def pause_workers(self, WorkerId, SQLs, ClassObject):
        with utils.SafeLock(LockPauseBusy):
            # Check if Kodi db or emby is about to open -> close db, wait, reopen db
            if self.Worker_is_paused(WorkerId):
                Databases = set()

                for SQLKey, SQLDatabase in list(SQLs.items()):
                    if SQLDatabase:
                        if SQLKey == "emby":
                            Databases.add(self.EmbyServer.ServerData['ServerId'])
                        else:
                            Databases.add(SQLKey)

                Databases = ",".join(Databases)
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {WorkerId} ] {utils.SyncPause}", 1) # LOGDEBUG

                while not LockPause.acquire(timeout=0.1):
                    pass

                if Databases:
                    dbio.DBCloseRW(Databases, WorkerId, SQLs)

                    if self.LockDBRWOpen.locked():
                        self.LockDBRWOpen.release()

                # Wait on progress updates
                if utils.DebugLog: xbmc.log("EMBY.database.library (DEBUG): CONDITION: --->[ SyncPauseCondition ]", 1) # LOGDEBUG

                with utils.SafeLock(utils.SyncPauseCondition):
                    while self.Worker_is_paused(WorkerId):
                        utils.SyncPauseCondition.wait(timeout=0.1)

                        if utils.SystemShutdown:
                            utils.close_ProgressBar(WorkerId)

                            if utils.DebugLog:
                                xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ SyncPauseCondition ]", 1) # LOGDEBUG
                                xbmc.log(f"EMBY.database.library (DEBUG): --<[ {WorkerId} ] {utils.SyncPause}", 1) # LOGDEBUG

                            LockPause.release()
                            return False

                if utils.DebugLog:
                    xbmc.log("EMBY.database.library (DEBUG): CONDITION: ---<[ SyncPauseCondition ]", 1) # LOGDEBUG
                    xbmc.log(f"EMBY.database.library (DEBUG): --<[ {WorkerId} ] {utils.SyncPause}", 1) # LOGDEBUG

                if Databases:
                    while not self.LockDBRWOpen.acquire(timeout=0.1):
                        pass

                    dbio.DBOpenRW(Databases, WorkerId, SQLs)

                # Update object due new database -> SQLs
                if ClassObject:
                    ClassObject.update_SQLs(SQLs)

                LockPause.release()

        return True

    def load_libraryObject(self, MediaType, SQLs):
        if MediaType == "Movie":
            return movies.Movies(self.EmbyServer, SQLs)

        if MediaType == "Video":
            return videos.Videos(self.EmbyServer, SQLs)

        if MediaType == "MusicVideo":
            return musicvideo.MusicVideo(self.EmbyServer, SQLs)

        if MediaType == "MusicAlbum":
            return musicalbum.MusicAlbum(self.EmbyServer, SQLs)

        if MediaType == 'Audio':
            return audio.Audio(self.EmbyServer, SQLs)

        if MediaType == "Episode":
            return episode.Episode(self.EmbyServer, SQLs)

        if MediaType == "Season":
            return season.Season(self.EmbyServer, SQLs)

        if MediaType == "Folder":
            return folder.Folder(self.EmbyServer, SQLs)

        if MediaType == "BoxSet":
            return boxsets.BoxSets(self.EmbyServer, SQLs)

        if MediaType == "Genre":
            return genre.Genre(self.EmbyServer, SQLs)

        if MediaType == "Series":
            return series.Series(self.EmbyServer, SQLs)

        if MediaType == "MusicGenre":
            return musicgenre.MusicGenre(self.EmbyServer, SQLs)

        if MediaType == "MusicArtist":
            return musicartist.MusicArtist(self.EmbyServer, SQLs)

        if MediaType == "Tag":
            return tag.Tag(self.EmbyServer, SQLs)

        if MediaType == "Person":
            return person.Person(self.EmbyServer, SQLs)

        if MediaType == "Studio":
            return studio.Studio(self.EmbyServer, SQLs)

        if MediaType == "Playlist":
            return playlist.Playlist(self.EmbyServer, SQLs)

        if MediaType == "Trailer":
            return trailer.Trailer(self.EmbyServer, SQLs)

        if MediaType == "PhotoAlbum":
            return photoalbum.PhotoAlbum(self.EmbyServer, SQLs)

        if MediaType == "Photo":
            return photo.Photo(self.EmbyServer, SQLs)

        return None

    def RunJobs(self, IncrementalSync, DropJobs):
        if utils.SystemShutdown:
            return

        if self.JobBusy:
            return

        if DropJobs:
            self.JobBusy = True

        if utils.DebugLog: xbmc.log("EMBY.database.library (DEBUG): --->[ run jobs ]", 1) # LOGDEBUG
        self.worker_userdata(IncrementalSync) # Priority

        if not utils.SyncPause.get(self.ServerBusyId, False):
            if self.worker_remove(IncrementalSync):
                if self.worker_update(IncrementalSync):
                    if self.worker_library_remove():
                        self.worker_library_add()
        else:
            xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: RunJobs limited due to server busy", 1) # LOGINFO

            if self.worker_library_remove():
                self.worker_library_add()

        self.worker_userdata(IncrementalSync) # Check again after updates
        self.JobBusy = False
        if utils.DebugLog: xbmc.log("EMBY.database.library (DEBUG): ---<[ run jobs ]", 1) # LOGDEBUG

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):
        LibrariesSelected = ()
        LibrariesSelectedIds = ()
        cache.reset_querycache()
        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], self.SelectLibrariesId)

        if mode in ('RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            PendingSyncRemoved = embydb.get_LibraryRemove_EmbyLibraryIds()

            for LibrarySyncedId, LibrarySyncedName, _, _ in self.LibrarySynced:
                if LibrarySyncedName != "shared" and LibrarySyncedId not in PendingSyncRemoved:
                    if LibrarySyncedId not in LibrariesSelectedIds:
                        LibrariesSelectedIds += (LibrarySyncedId,)
                        LibrariesSelected += ({'Id': LibrarySyncedId, 'Name': LibrarySyncedName},)
        else: # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()
            PendingSyncAdded = embydb.get_LibraryAdd_EmbyLibraryIds()

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ("movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos", "playlists", "trailers") and AvailableLibId not in self.LibrarySyncedNames and AvailableLibId not in PendingSyncAdded:
                    LibrariesSelected += ({'Id': AvailableLibId, 'Name': AvailableLib[0]},)

        SelectionMenu = [x['Name'] for x in LibrariesSelected]
        SelectionMenu.insert(0, utils.Translate(33121))

        if mode == 'RepairLibrarySelection':
            Text = utils.Translate(33432)
        elif mode == 'RemoveLibrarySelection':
            Text = utils.Translate(33434)
        elif mode == 'UpdateLibrarySelection':
            Text = utils.Translate(33433)
        elif mode == 'AddLibrarySelection':
            Text = utils.Translate(33120)
        else:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.SelectLibrariesId)
            return

        Selections = utils.Dialog.multiselect(Text, SelectionMenu)

        if not Selections:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.SelectLibrariesId)
            return

        # "All" selected
        if 0 in Selections:
            Selections = list(range(1, len(LibrariesSelected) + 1))

        utils.close_dialog(10146) # addoninformation
        LibraryIdsRemove = ()
        LibraryRemoveItems = ()
        LibraryIdsAdd = ()

        if mode in ('AddLibrarySelection', 'UpdateLibrarySelection'):
            for x in Selections:
                LibraryIdsAdd += (LibrariesSelected[x - 1]['Id'],)
        elif mode == 'RepairLibrarySelection':
            for x in Selections:
                LibraryRemoveItems += (LibrariesSelected[x - 1],)
                LibraryIdsRemove += (LibrariesSelected[x - 1]['Id'],)
                LibraryIdsAdd += (LibrariesSelected[x - 1]['Id'],)
        elif mode == 'RemoveLibrarySelection':
            for x in Selections:
                LibraryRemoveItems += (LibrariesSelected[x - 1],)
                LibraryIdsRemove += (LibrariesSelected[x - 1]['Id'],)

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], self.SelectLibrariesId)
        SQLs = self.open_EmbyDBRW(self.SelectLibrariesId, True)

        if LibraryRemoveItems:
            # detect shared content type
            removeGlobalVideoContent = True

            for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                if LibrarySyncedId not in LibraryIdsRemove + ('999999999', '999999998') and LibrarySyncedEmbyType in ('Movie', 'Series', 'Video', 'MusicVideo'):
                    removeGlobalVideoContent = False
                    break

            if removeGlobalVideoContent:
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: remove library: 999999999 / Person ]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced("999999999")
                SQLs["emby"].add_LibraryRemove("999999999", "Person")
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: remove library: 999999998 / Video ]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced("999999998")
                SQLs["emby"].add_LibraryRemove("999999998", "Video")

            # Remove libraries
            for LibraryIdRemove in LibraryRemoveItems:
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: remove library: {LibraryIdRemove['Id']} / {LibraryIdRemove['Name']}]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced(LibraryIdRemove["Id"])
                SQLs["emby"].add_LibraryRemove(LibraryIdRemove["Id"], LibraryIdRemove["Name"])

            self.load_LibrarySynced(SQLs)

        if LibraryIdsAdd:
            # detect shared content type
            syncGlobalVideoContent = False

            for LibraryIdAdd in LibraryIdsAdd:
                if LibraryIdAdd in self.EmbyServer.Views.ViewItems:
                    ViewData = self.EmbyServer.Views.ViewItems[LibraryIdAdd]

                    if ViewData[1] in ('movies', 'tvshows', 'mixed', 'musicvideos', 'trailers'):
                        syncGlobalVideoContent = True
                        break

            for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                if (LibrarySyncedId == "999999999" and LibrarySyncedEmbyType == "Person") or (LibrarySyncedId == "999999998" and LibrarySyncedEmbyType == "Video"):
                    syncGlobalVideoContent = False

            if syncGlobalVideoContent:
                SQLs["emby"].add_LibraryAdd("999999999", "shared", "Person", "video") # Person can only be queried globally by Emby server
                SQLs["emby"].add_LibraryAdd("999999998", "shared", "Video", "none") # Video's with no ParentId are Trailes in TrailerFolder and can only be queried globally by Emby server
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library: 999999999 / Person ]", 1) # LOGINFO
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library: 999999998 / Video ]", 1) # LOGINFO

            # Add libraries
            for LibraryId in LibraryIdsAdd:
                if LibraryId in self.EmbyServer.Views.ViewItems:
                    ViewData = self.EmbyServer.Views.ViewItems[LibraryId]
                    library_type = ViewData[1]
                    library_name = ViewData[0]

                    # content specific libraries
                    if library_type == 'mixed':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "video,music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "video,music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Movie", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Series", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Season", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Episode", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicVideo", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicAlbum", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Audio", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type == 'movies':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Movie", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type == 'musicvideos':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicVideo", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type == 'homevideos':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "PhotoAlbum", "none")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Photo", "none")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type == 'tvshows':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Series", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Season", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Episode", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type in ('music', 'audiobooks', 'podcasts'):
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicAlbum", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Audio", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")
                    elif library_type == 'playlists':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "video,music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "video,music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicAlbum", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Series", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Season", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicAlbum", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Playlist", "video,music")
                    elif library_type == 'trailers':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Trailer", "none")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")

                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library: {LibraryId} ]", 1) # LOGINFO
                else:
                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library not found: {LibraryId} ]", 1) # LOGINFO

            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())

        self.close_EmbyDBRW(self.SelectLibrariesId, SQLs)

        if LibraryIdsRemove:
            utils.start_thread(self.worker_library_remove, ())

        if LibraryIdsAdd and not LibraryIdsRemove:
            utils.start_thread(self.worker_library_add, ())

    def refresh_boxsets(self):  # threaded by caller
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_boxsets ]", 1) # LOGDEBUG
        utils.close_dialog(10146) # addoninformation
        SQLs = self.open_EmbyDBRW("refresh_boxsets", False)
        dbio.DBOpenRW("video", "refresh_boxsets", SQLs)

        for LibrarySyncedLibraryId, LibrarySyncedLibraryName, LibrarySyncedEmbyType, _ in self.LibrarySynced:
            if LibrarySyncedEmbyType == "BoxSet":
                items = SQLs["emby"].get_boxsets()

                for item in items:
                    SQLs["emby"].add_RemoveItem(item[0], LibrarySyncedLibraryId)

                KodiTagIds = SQLs["emby"].get_item_by_memo("collection")
                SQLs["emby"].remove_item_by_memo("collection")

                for KodiTagId in KodiTagIds:
                    SQLs["video"].delete_tag_by_Id(KodiTagId)

                SQLs["emby"].add_LibraryAdd(LibrarySyncedLibraryId, LibrarySyncedLibraryName, "BoxSet", "video")

        dbio.DBCloseRW("video", "refresh_boxsets", SQLs)
        self.close_EmbyDBRW("refresh_boxsets", SQLs)
        self.worker_remove(False)
        self.worker_library_add()
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_boxsets ]", 1) # LOGDEBUG

    def SyncLiveTV(self):
        if not utils.check_iptvsimple():
            return

        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: iptv simple config change ]", 1) # LOGINFO
        SQLs = {}
        dbio.DBOpenRW("epg", "livetvsync", SQLs)
        SQLs["epg"].delete_tables("EPG")
        dbio.DBCloseRW("epg", "livetvsync", SQLs)
        dbio.DBOpenRW("tv", "livetvsync", SQLs)
        SQLs["tv"].delete_tables("TV")
        dbio.DBCloseRW("tv", "livetvsync", SQLs)
        PlaylistFile = f"{utils.FolderEmbyTemp}{self.EmbyServer.ServerData['ServerId']}-livetv.m3u"
        ChannelsUnsorted = []
        ChannelsSortedbyChannelNumber = {}
        Channels = self.EmbyServer.API.get_channels()

        if not utils.LiveTVEnabled:
            utils.delFile(PlaylistFile)
            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: iptv simple disabled ]", 1) # LOGINFO
            return

        # Sort Channels by ChannelNumber
        for Channel in Channels:
            ChannelNumber = str(Channel.get("ChannelNumber", 0))

            if ChannelNumber.isdigit():
                ChannelNumber = int(ChannelNumber)
            else:
                ChannelNumber = 0

            if ChannelNumber:
                while ChannelNumber in ChannelsSortedbyChannelNumber:
                    ChannelNumber += 1

                ChannelsSortedbyChannelNumber[ChannelNumber] = Channel
            else:
                ChannelsUnsorted.append(Channel)

        ChannelsSorted = list(dict(sorted(ChannelsSortedbyChannelNumber.items())).values())
        ChannelsSortedbyId = {}

        # Sort Channels by ChannelId
        for Channel in ChannelsUnsorted:
            ChannelsSortedbyId[int(Channel["Id"])] = Channel

        ChannelsSorted += list(dict(sorted(ChannelsSortedbyId.items())).values())

        # Build M3U
        PlaylistM3U = "#EXTM3U\n"
        ReleaseCounter = 0

        for ChannelSorted in ChannelsSorted:
            ReleaseCounter += 1

            if ReleaseCounter % 50 == 0:
                xbmc.sleep(0) # release GIL

            if ChannelSorted['TagItems']:
                Tag = ChannelSorted['TagItems'][0]['Name']
            else:
                Tag = "--NO INFO--"

            tvglogo = ""
            tvgchno = ""
            ChannelNumber = ChannelSorted.get("ChannelNumber", "")

            if ChannelSorted['ImageTags']:
                if 'Primary' in ChannelSorted['ImageTags']:
                    IconFile = utils.download_Icon(ChannelSorted['Id'], "", self.EmbyServer.ServerData['ServerId'], "", True)
                    tvglogo = f" tvg-logo=\"{IconFile}\""

            if ChannelNumber:
                tvgchno = f" tvg-chno=\"{ChannelNumber}\""

            if ChannelSorted['Name'].lower().find("radio") != -1 or ChannelSorted['MediaType'] != "Video":
                PlaylistM3U += f'#EXTINF:-1 tvg-id="{ChannelSorted["Id"]}" tvg-name="{ChannelSorted["Name"]}"{tvglogo}{tvgchno} radio="true" group-title="{Tag}",{ChannelSorted["Name"]}\n'
            else:
                PlaylistM3U += f'#EXTINF:-1 tvg-id="{ChannelSorted["Id"]}" tvg-name="{ChannelSorted["Name"]}"{tvglogo}{tvgchno} group-title="{Tag}",{ChannelSorted["Name"]}\n'

            common.set_streams(ChannelSorted)
            common.set_chapters(ChannelSorted, self.EmbyServer.ServerData['ServerId'])
            common.set_path_filename(ChannelSorted, self.EmbyServer.ServerData['ServerId'], None, True)
            PlaylistM3U += f"{ChannelSorted['KodiFullPath']}\n"

        utils.writeFile(PlaylistFile, PlaylistM3U)
        self.SyncLiveTVEPG(False)

        if not utils.LiveTVEnabled:
            return

        SimpleIptvSettings = utils.readFileString("special://home/addons/plugin.service.emby-next-gen/resources/iptvsimple.xml")
        SimpleIptvSettings = SimpleIptvSettings.replace("SERVERID", self.EmbyServer.ServerData['ServerId'])
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
        utils.writeFile(f"special://profile/addon_data/pvr.iptvsimple/instance-settings-{str(int(self.EmbyServer.ServerData['ServerId'], 16))[:4]}.xml", SimpleIptvSettings.encode("utf-8"))
        utils.sleep(3)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')
        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: iptv simple config change ]", 1) # LOGINFO

    def SyncLiveTVEPG(self, ChannelSync=True):
        if not utils.LiveTVEnabled:
            return

        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: load EPG ]", 1) # LOGINFO
        epg = '<?xml version="1.0" encoding="utf-8" ?><tv>'
        ReleaseCounter = 0

        for item in self.EmbyServer.API.get_channelprogram():
            ReleaseCounter += 1

            if ReleaseCounter % 50 == 0:
                xbmc.sleep(0) # release GIL

            temp = item['StartDate'].split("T")
            timestampStart = temp[0].replace("-", "")
            temp2 = temp[1].split(".")
            timestampStart += temp2[0].replace(":", "")[:6]
            temp2 = temp2[1].split("+")

            if len(temp2) > 1:
                timestampStart += f"+{temp2[1].replace(':', '')}"

            temp = item['EndDate'].split("T")
            timestampEnd = temp[0].replace("-", "")
            temp2 = temp[1].split(".")
            timestampEnd += temp2[0].replace(":", "")[:6]
            temp2 = temp2[1].split("+")

            if len(temp2) > 1:
                timestampEnd += f"+{temp2[1].replace(':', '')}"

            epg += f'<channel id="{item["ChannelId"]}"><display-name lang="en">{item["ChannelId"]}</display-name></channel><programme start="{timestampStart}" stop="{timestampEnd}" channel="{item["ChannelId"]}"><title lang="en">{item["Name"]}</title>'

            if 'Overview' in item:
                item["Overview"] = item["Overview"].replace("<", "(").replace(">", ")")
                epg += f'<desc lang="en">{item["Overview"]}</desc>'

            epg += f'<icon src="{self.EmbyServer.ServerData["ServerId"]}Z{item["Id"]}"/></programme>' # rape icon -> assign serverId and programId

        epg += '</tv>'
        EPGFile = f"{utils.FolderEmbyTemp}{self.EmbyServer.ServerData['ServerId']}-livetvepg.xml"
        utils.delFile(EPGFile)
        utils.writeFile(EPGFile, epg)

        if utils.LiveTVEnabled and utils.SyncLiveTvOnEvents and ChannelSync:
            self.SyncLiveTV()

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: load EPG ]", 1) # LOGINFO

    # Add item_id to userdata queue
    def userdata(self, Items, IncrementalSync, ProcessUpdates=True):  # threaded by caller -> websocket via monitor
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: userdata ]", 1) # LOGDEBUG

        if Items:
            SQLs = self.open_EmbyDBRW("userdata", True)
            SQLs["emby"].add_Userdatas(Items)
            self.close_EmbyDBRW("userdata", SQLs)

            if ProcessUpdates:
                self.worker_userdata(IncrementalSync)

        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: userdata ]", 1) # LOGDEBUG

    # Add item_id to updated queue
    def updated(self, Items, IncrementalSync, ProcessUpdates=True):  # threaded by caller
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: updated ]", 1) # LOGDEBUG

        if Items:
            SQLs = self.open_EmbyDBRW("updated", True)
            SQLs["emby"].add_UpdateItems(Items)
            self.close_EmbyDBRW("updated", SQLs)

            if ProcessUpdates:
                if not utils.SyncPause.get(self.ServerBusyId, False):
                    self.worker_update(IncrementalSync)
                else:
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: updated trigger skipped due to server busy", 1) # LOGINFO

        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: updated ]", 1) # LOGDEBUG

    # Add item_id to removed queue
    def removed(self, Ids, IncrementalSync, ProcessUpdates=True):  # threaded by caller
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed ]", 1) # LOGDEBUG

        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)
            SQLs["emby"].add_RemoveItems_EmbyId(Ids)
            self.close_EmbyDBRW("removed", SQLs)

            if ProcessUpdates:
                if not utils.SyncPause.get(self.ServerBusyId, False):
                    self.worker_remove(IncrementalSync)
                else:
                    xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: removed trigger skipped due to server busy", 1) # LOGINFO

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed ]", 1) # LOGDEBUG

    # Add item_id to removed queue
    def removed_deduplicate(self, Ids):  # threaded by caller
        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)
            SQLs["emby"].add_RemoveItems_EmbyLibraryId_EmbyId(Ids)
            self.close_EmbyDBRW("removed", SQLs)
            self.worker_remove(True)

    def Worker_is_paused(self, WorkerId):
        for Key, Busy in list(utils.SyncPause.items()):
            if Busy:
                if WorkerId.endswith("remove") and Key == self.ServerBusyId: # Continue removes, even emby server is busy
                    continue

                if Key.endswith("server_busy") and Key != self.ServerBusyId:
                    continue

                if Key.endswith("database_init") and Key != self.ServerDatabaseInitId:
                    continue

                if Key.endswith("server_reconnecting") and Key != self.ServerReconnectingId:
                    continue



                if Key.endswith("server_startscync") and Key != self.ServerStartSyncId:
                    continue

                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): Emby server Worker_is_paused: {WorkerId} / {utils.SyncPause}", 1) # LOGINFO
                return True

        return False

    def refresh_musicvideolinks(self):
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): -->[ {self.MusicVideoLinks} ] refresh", 1) # LOGDEBUG
        utils.close_dialog(10146) # addoninformation

        utils.create_ProgressBar(self.MusicVideoLinks, utils.Translate(33749), utils.Translate(33363))
        videodb = dbio.DBOpenRO("video", self.MusicVideoLinks)
        MusicVideoDatas = videodb.get_musicvideos_KodiId_MusicBrainzId_Artist_Title()
        dbio.DBCloseRO("video", self.MusicVideoLinks)
        TotalItems = len(MusicVideoDatas)
        SQLs = {}
        dbio.DBOpenRW("music", self.MusicVideoLinks, SQLs)
        SQLs["music"].del_song_musicvideo()

        # Bulk Update in Chunks
        if MusicVideoDatas:
            for i in range(0, TotalItems, 1000):
                xbmc.sleep(0) # release GIL

                if utils.SystemShutdown:
                    break

                chunk = MusicVideoDatas[i : i + 1000]
                SQLs["music"].update_song_musicvideo(chunk)
                utils.update_ProgressBar(self.MusicVideoLinks, (i + len(chunk)) / TotalItems * 100, utils.Translate(33363), f"{chunk[-1][3]} - {chunk[-1][2]}")

        dbio.DBCloseRW("music", self.MusicVideoLinks, SQLs)
        utils.close_ProgressBar(self.MusicVideoLinks)
        if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): --<[ {self.MusicVideoLinks} ] refresh", 1) # LOGDEBUG

    def ItemsSort(self, GeneratorFunction, SQLs, Items, Reverse, RecordsPercent):
        SortItems = {'Movie': set(), 'Video': set(), 'BoxSet': set(), 'MusicVideo': set(), 'Series': set(), 'Episode': set(), 'MusicAlbum': set(), 'MusicArtist': set(), 'AlbumArtist': set(), 'Season': set(), 'Folder': set(), 'Audio': set(), 'Genre': set(), 'MusicGenre': set(), 'Tag': set(), 'Person': set(), 'Studio': set(), 'Playlist': set(), 'Trailer': set(), 'PhotoAlbum': set(), 'Photo': set()}
        Others = set()
        ReleaseCounter = 0

        for Valid, Item in GeneratorFunction(SQLs, Items, RecordsPercent):
            ReleaseCounter += 1

            if ReleaseCounter % 100 == 0:
                xbmc.sleep(0) # release GIL

            if not Item:
                continue

            if Valid:
                self.set_recording_type(Item)

                if Item['Type'] in SortItems:
                    SortItems[Item['Type']].add(json.dumps(Item)) # Dict is not hashable (not possible adding "dict" to "set") -> convert to json string necessary
                else: # e.g. PlaceHolder
                    if utils.DebugLog: xbmc.log(f"EMBY.database.library(DEBUG): Emby server {self.EmbyServer.ServerData['ServerId']}: Unsupported item type {Item['Type']}", 1) # LOGDEBUG
                    Others.add(json.dumps(Item))
            else:
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): Emby server {self.EmbyServer.ServerData['ServerId']}: Unknown {Item} / {GeneratorFunction}", 1) # LOGDEBUG
                Others.add(json.dumps(Item))
                continue

        if Reverse: # on remove, reverse sort order
            return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['BoxSet'], SortItems['Trailer'], SortItems['Video'], SortItems['Movie'], SortItems['Episode'], SortItems['Season'], SortItems['Series']], "music,video": [SortItems['MusicGenre'], SortItems['Audio'], SortItems['MusicVideo'], SortItems['MusicAlbum'], SortItems['MusicArtist'], SortItems['Playlist']], "none": [SortItems['Photo'], SortItems['PhotoAlbum'], SortItems['Folder']]}, Others

        return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['Series'], SortItems['Season'], SortItems['Trailer'], SortItems['Episode'], SortItems['Movie'], SortItems['Video'], SortItems['BoxSet']], "music,video": [SortItems['MusicGenre'], SortItems['MusicArtist'], SortItems['MusicAlbum'], SortItems['MusicVideo'], SortItems['Audio'], SortItems['Playlist']], "none": [SortItems['Folder'], SortItems['PhotoAlbum'], SortItems['Photo']]}, Others

    def set_recording_type(self, Item):
        if 'Type' in Item:
            if Item['Type'] == "Recording":
                if utils.DebugLog: xbmc.log(f"EMBY.database.library (DEBUG): Emby server {self.EmbyServer.ServerData['ServerId']}: Recording detected", 1) # LOGDEBUG

                if Item.get('IsSeries', False):
                    Item['Type'] = 'Episode'
                else:
                    Item['Type'] = 'Movie'

def content_available(CategoryItems):
    for CategoryItem in CategoryItems:
        if CategoryItem:
            return True

    return False

def StringToDict(Data):
    Data = Data.replace("'", '"')
    Data = Data.replace("False", "false")
    Data = Data.replace("True", "true")
    return json.loads(Data)

# For theme media, do not modify unless modified in TV Tunes.
# Remove dots from the last character as windows can not have directories with dots at the end
def normalize_string(text):
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.strip()
    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', text)
    return text

def get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio):
    if Items:
        if KodiDBs.find("music") != -1:
            RefreshAudio = True

        if KodiDBs.find("video") != -1:
            RefreshVideo = True

    return RefreshVideo, RefreshAudio

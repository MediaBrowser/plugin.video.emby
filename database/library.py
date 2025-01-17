from _thread import allocate_lock
import json
import unicodedata
import xbmc
import xbmcaddon
import xbmcgui
from core import movies, videos, musicvideo, folder, boxsets, genre, musicgenre, musicartist, musicalbum, audio, tag, person, studio, playlist, series, season, episode, common
from helper import utils
from hooks import favorites
from . import dbio

LockPause = allocate_lock()
LockPauseBusy = allocate_lock()
LockLowPriorityWorkers = allocate_lock()
LockLibraryOps = allocate_lock()


class Library:
    def __init__(self, EmbyServer):
        xbmc.log("EMBY.database.library: -->[ library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.LibrarySynced = []
        self.LibrarySyncedKodiDBs = {}
        self.LibrarySyncedNames = {}
        self.LastSyncTime = ""
        self.ContentObject = None
        self.SettingsLoaded = False
        self.LockKodiStartSync = allocate_lock()
        self.LockDBRWOpen = allocate_lock()

    # Wait for database init
    def wait_DatabaseInit(self, WorkerName):
        if utils.SyncPause.get(f"database_init_{self.EmbyServer.ServerData['ServerId']}", True):
            xbmc.log("EMBY.database.library: -->[ open_Worker delay: Wait for database init ]", 1) # LOGINFO

            while utils.SyncPause.get(f"database_init_{self.EmbyServer.ServerData['ServerId']}", True):
                xbmc.log(f"EMBY.database.library: [ worker {WorkerName} wait for database init ]", 1) # LOGINFO

                if utils.sleep(1):
                    xbmc.log("EMBY.database.library: --<[ open_Worker delay: Wait for database init (shutdown) ]", 1) # LOGINFO
                    return False

            xbmc.log("EMBY.database.library: --<[ open_Worker delay: Wait for database init ]", 1) # LOGINFO

        return True

    def open_Worker(self, WorkerName):
        if Worker_is_paused(WorkerName):
            xbmc.log("EMBY.database.library: -->[ open_Worker delay: Worker_is_paused ]", 1) # LOGINFO

            while Worker_is_paused(WorkerName):
                if utils.sleep(1):
                    xbmc.log("EMBY.database.library: --<[ open_Worker delay: Worker_is_paused (shutdown) ]", 1) # LOGINFO
                    return False

            xbmc.log("EMBY.database.library: --<[ open_Worker delay: Worker_is_paused ]", 1) # LOGINFO

        if utils.SystemShutdown:
            return False

        return True

    def close_Worker(self, WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs):
        self.close_EmbyDBRW(WorkerName, SQLs)

        if RefreshVideo:
            utils.refresh_widgets(True)

        if RefreshAudio:
            utils.refresh_widgets(False)

        ProgressBar.close()
        del ProgressBar

    def open_EmbyDBRW(self, WorkerName, Priority):
        # if worker in progress, interrupt workers database ops (worker has lower priority) compared to all other Emby database (rw) ops
        if Priority and LockLowPriorityWorkers.locked() and self.LockDBRWOpen.locked():
            utils.SyncPause['priority'] = True

        self.LockDBRWOpen.acquire() # Wait for close
        SQLs = {}
        dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], WorkerName, SQLs)
        return SQLs

    def close_EmbyDBRW(self, WorkerName, SQLs):
        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName, SQLs)
        utils.SyncPause['priority'] = False

        if self.LockDBRWOpen.locked():
            self.LockDBRWOpen.release()
    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        SQLs = self.open_EmbyDBRW("set_syncdate", True)
        SQLs["emby"].update_LastIncrementalSync(TimestampUTC)
        self.close_EmbyDBRW("set_syncdate", SQLs)
        self.LastSyncTime = TimestampUTC
        utils.set_syncdate(self.LastSyncTime)

    def load_LibrarySynced(self, SQLs):
        self.LibrarySynced = SQLs["emby"].get_LibrarySynced()
        LibrarySyncedMirrows = SQLs["emby"].get_LibrarySyncedMirrow()
        self.LibrarySyncedKodiDBs = {}
        self.LibrarySyncedNames = {}

        for LibrarySyncedMirrowId, LibrarySyncedMirrowName, LibrarySyncedMirrowEmbyType, LibrarySyncedMirrowKodiDBs in LibrarySyncedMirrows:
            self.LibrarySyncedKodiDBs[f"{LibrarySyncedMirrowId}{LibrarySyncedMirrowEmbyType}"] = LibrarySyncedMirrowKodiDBs
            self.LibrarySyncedNames[LibrarySyncedMirrowId] = LibrarySyncedMirrowName

    def load_settings(self):
        xbmc.log(f"EMBY.database.library: {self.EmbyServer.ServerData['ServerId']} --->[ load settings ]", 1) # LOGINFO
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = True

        # Load essential data and prefetching Media tags
        SQLs = self.open_EmbyDBRW("load_settings", True)

        if SQLs["emby"].init_EmbyDB():
            self.load_LibrarySynced(SQLs)
        else:
            utils.set_settings('MinimumSetup', "INVALID DATABASE")
            self.close_EmbyDBRW("load_settings", SQLs)
            utils.restart_kodi()
            xbmc.log(f"EMBY.database.library: load settings: database corrupt: {self.EmbyServer.ServerData['ServerId']}  ---<[ load settings ]", 3) # LOGERROR
            return

        self.LastSyncTime = SQLs["emby"].get_LastIncrementalSync()
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
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = False
        self.SettingsLoaded = True
        xbmc.log(f"EMBY.database.library: {self.EmbyServer.ServerData['ServerId']} ---<[ load settings ]", 1) # LOGINFO

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        xbmc.log("EMBY.database.library: THREAD: --->[ retrieve changes ]", 0) # LOGDEBUG

        with self.LockKodiStartSync:
            if not utils.startsyncenabled:
                xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] IncrementalSync disabled", 0) # LOGDEBUG

            NewSyncData = utils.currenttime()
            UpdateSyncData = False

            while not self.SettingsLoaded:
                if utils.sleep(1):
                    xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 1", 0) # LOGDEBUG
                    return

            if Firstrun:
                self.select_libraries("AddLibrarySelection")

            # Upsync downloaded content progress
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "KodiIncrementalSync")
            DownlodedItems = embydb.get_DownloadItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "KodiIncrementalSync")
            videodb = dbio.DBOpenRO("video", "KodiIncrementalSync")

            for DownlodedItem in DownlodedItems:
                utils.ItemSkipUpdate.append(str(DownlodedItem[0]))
                Found, timeInSeconds, playCount, lastPlayed, = videodb.get_Progress(DownlodedItem[2])

                if Found:
                    self.EmbyServer.API.set_progress_upsync(DownlodedItem[0], int(timeInSeconds * 10000000), playCount, utils.convert_to_gmt(lastPlayed))  # Id, PlaybackPositionTicks, PlayCount, LastPlayedDate

            dbio.DBCloseRO("video", "KodiIncrementalSync")
            self.RunJobs(False)
            UpdateData = []

            if utils.SystemShutdown:
                xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 2", 0) # LOGDEBUG
                return

            # Retrieve changes
            if self.LastSyncTime:
                xbmc.log(f"EMBY.database.library: Retrieve changes, last synced: {self.LastSyncTime}", 1) # LOGINFO
                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33445))
                xbmc.log("EMBY.database.library: -->[ Kodi companion ]", 1) # LOGINFO
                result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

                if 'ItemsRemoved' in result:
                    if result['ItemsRemoved']:
                        UpdateSyncData = True
                        self.removed(result['ItemsRemoved'], True)
                else:
                    utils.Dialog.ok(utils.addon_name, utils.Translate(33716))

                xbmc.log("EMBY.database.library: --<[ Kodi companion ]", 1) # LOGINFO
                ProgressBarTotal = len(self.LibrarySynced) / 100
                ProgressBarIndex = 0

                for LibrarySyncedId, LibrarySyncedName, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                    if utils.SystemShutdown:
                        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 3", 0) # LOGDEBUG
                        ProgressBar.close()
                        del ProgressBar
                        return

                    xbmc.log(f"EMBY.database.library: [ retrieve changes ] {LibrarySyncedName} / {LibrarySyncedEmbyType}", 1) # LOGINFO
                    LibraryName = ""
                    ProgressBarIndex += 1

                    if LibrarySyncedId in self.EmbyServer.Views.ViewItems:
                        LibraryName = self.EmbyServer.Views.ViewItems[LibrarySyncedId][0]
                        ProgressBar.update(int(ProgressBarIndex / ProgressBarTotal), utils.Translate(33445), LibraryName)

                    if not LibraryName and LibrarySyncedName != "shared":
                        xbmc.log(f"EMBY.database.library: [ KodiIncrementalSync remove library {LibrarySyncedId} ]", 1) # LOGINFO
                        continue

                    ItemIndex = 0
                    UpdateDataTemp = 10000 * [()] # pre allocate memory

                    if LibrarySyncedEmbyType == "Folder":
                        Param = 'MinDateLastSaved'
                    else:
                        Param = 'MinDateLastSavedForUser'

                    for Item in self.EmbyServer.API.get_Items(LibrarySyncedId, [LibrarySyncedEmbyType], True, True, {Param: self.LastSyncTime}, "", True, None):
                        if utils.SystemShutdown:
                            ProgressBar.close()
                            del ProgressBar
                            xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 4", 0) # LOGDEBUG
                            return

                        if ItemIndex >= 10000:
                            UpdateData += UpdateDataTemp
                            UpdateDataTemp = 10000 * [()] # pre allocate memory
                            ItemIndex = 0

                        set_recording_type(Item)
                        UpdateDataTemp[ItemIndex] = (Item['Id'], Item['Type'], LibrarySyncedId)
                        ItemIndex += 1

                    UpdateData += UpdateDataTemp

                ProgressBar.close()
                del ProgressBar

                if utils.SystemShutdown:
                    xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 5", 0) # LOGDEBUG
                    return

            # Run jobs
            if UpdateData:
                UpdateData = list(dict.fromkeys(UpdateData)) # filter doubles

                if () in UpdateData:  # Remove empty
                    UpdateData.remove(())

                if UpdateData:
                    UpdateSyncData = True
                    self.updated(UpdateData, True)

        # Update sync update timestamp
        if UpdateSyncData:
            xbmc.log("EMBY.database.library: Start sync, updates found", 1) # LOGINFO
            self.set_syncdate(NewSyncData)
        else:
            xbmc.log("EMBY.database.library: Start sync, widget refresh", xbmc.LOGINFO) # reload artwork/images
            utils.refresh_widgets(True)
            utils.refresh_widgets(False)

        utils.set_syncdate(self.LastSyncTime)
        self.SyncLiveTVEPG()
        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ]", 0) # LOGDEBUG

    # Userdata change is an high priority task
    def worker_userdata(self):
        WorkerName = "worker_userdata"

        if not self.wait_DatabaseInit(WorkerName):
            return

        SQLs = {"emby": dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)}
        UserDataItems = SQLs["emby"].get_Userdata()
        xbmc.log(f"EMBY.database.library: -->[ worker userdata started ] queue size: {len(UserDataItems)}", 0) # LOGDEBUG

        if not UserDataItems:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log("EMBY.database.library: --<[ worker userdata empty ]", 0) # LOGDEBUG
            return

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
        RecordsPercent = len(UserDataItems) / 100
        UpdateItems, Others = ItemsSort(self.worker_userdata_generator, SQLs, UserDataItems, False, RecordsPercent, ProgressBar)

        if not SQLs['emby']:
            xbmc.log("EMBY.database.library: --<[ worker userdata interrupt ] (ItemsSort)", 0) # LOGDEBUG
            return

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        SQLs = self.open_EmbyDBRW(WorkerName, True)
        RefreshAudio = False
        RefreshVideo = False
        RefreshWidgets = False

        for Other in Others:
            SQLs["emby"].delete_Userdata(json.loads(Other))

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            if content_available(CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                for Items in CategoryItems:
                    self.ContentObject = None
                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                    for index, Item in enumerate(Items, 1):
                        Item = json.loads(Item)
                        SQLs["emby"].delete_Userdata(Item["UpdateItem"])
                        Continue, Update = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar, True)

                        if Update:
                            RefreshWidgets = True

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker userdata interrupt ]", 0) # LOGDEBUG
                            return

                dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())

        if RefreshWidgets:
            self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)
        else:
            self.close_Worker(WorkerName, False, False, ProgressBar, SQLs)

        xbmc.log("EMBY.database.library: --<[ worker userdata completed ]", 0) # LOGDEBUG

    def worker_userdata_generator(self, SQLs, UserDataItems, RecordsPercent, ProgressBar):
        RefreshDynamicNodes = False

        for index, UserDataItem in enumerate(UserDataItems, 1):
            UserDataItem = StringToDict(UserDataItem[0])
            ProgressBar.update(int(index / RecordsPercent), utils.Translate(33178), str(UserDataItem['ItemId']))
            KodiItemId, KodiFileId, EmbyType, KodiParentId = SQLs["emby"].get_kodiid_kodifileid_embytype_kodiparentid_by_id(UserDataItem['ItemId'])

            if KodiItemId:
                if "LastPlayedDate" in UserDataItem:
                    LastPlayedDate = UserDataItem['LastPlayedDate']
                    PlayCount = UserDataItem['PlayCount']
                else:
                    LastPlayedDate = None
                    PlayCount = None

                yield True, {"Id": UserDataItem['ItemId'], "KodiItemId": KodiItemId, "KodiParentId": KodiParentId, "KodiFileId": KodiFileId, "Type": EmbyType, 'PlaybackPositionTicks': UserDataItem['PlaybackPositionTicks'], 'PlayCount': PlayCount, 'IsFavorite': UserDataItem['IsFavorite'], 'LastPlayedDate': LastPlayedDate, 'Played': UserDataItem['Played'], "PlayedPercentage": UserDataItem.get('PlayedPercentage', 0), "UpdateItem": str(UserDataItem)}
            else: # skip if item is not synced
                RefreshDynamicNodes = True
                yield False, str(UserDataItem)
                xbmc.log(f"EMBY.database.library: Skip not synced item: {UserDataItem}", 0) # LOGDEBUG

        if RefreshDynamicNodes:
            refresh_dynamic_nodes()

    def worker_update(self, IncrementalSync):
        with LockLowPriorityWorkers:
            WorkerName = "worker_update"

            if not self.wait_DatabaseInit(WorkerName):
                return False

            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            UpdateItems, UpdateItemsCount = embydb.get_UpdateItem()
            RemoveItems = embydb.get_RemoveItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            del embydb

        # Re-run if removed items are added while waiting for updates
        if RemoveItems:
            xbmc.log("EMBY.database.library: Worker update, removed items found, trigger removal", 0) # LOGDEBUG
            self.worker_remove(IncrementalSync)

        # Process updates
        with LockLowPriorityWorkers:
            xbmc.log(f"EMBY.database.library: -->[ worker update started ] queue size: {UpdateItemsCount}", 0) # LOGDEBUG

            if not UpdateItemsCount:
                xbmc.log("EMBY.database.library: --<[ worker update empty ]", 0) # LOGDEBUG
                return True

            if not self.open_Worker(WorkerName):
                return False

            ProgressBar = xbmcgui.DialogProgressBG()
            ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
            RecordsPercent = UpdateItemsCount / 100
            index = 0
            UpdateItems, Others = ItemsSort(self.worker_update_generator, {}, UpdateItems, False, RecordsPercent, ProgressBar)
            RefreshAudio = False
            RefreshVideo = False
            SQLs = self.open_EmbyDBRW(WorkerName, False)

            for Other in Others:
                SQLs["emby"].delete_UpdateItem(json.loads(Other)['Id'])

            for KodiDBs, CategoryItems in list(UpdateItems.items()):
                Continue = True

                if content_available(CategoryItems):
                    dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                    for Items in CategoryItems:
                        self.ContentObject = None
                        Item = ""
                        RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                        for Item in Items:
                            Item = json.loads(Item)
                            SQLs["emby"].delete_UpdateItem(Item['Id'])
                            Continue, _ = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar, IncrementalSync)
                            index += 1

                            if not Continue:
                                self.EmbyServer.API.ProcessProgress[WorkerName] = -1
                                xbmc.log("EMBY.database.library: --<[ worker update interrupt ]", 0) # LOGDEBUG
                                return False

                    dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

                if not Continue:
                    break

            self.EmbyServer.API.ProcessProgress[WorkerName] = -1
            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
            self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)
            xbmc.log("EMBY.database.library: --<[ worker update completed ]", 0) # LOGDEBUG

        return True

    def worker_update_generator(self, SQLs, UpdateItems, _RecordsPercent, ProgressBar):
        RefreshDynamicNodes = False

        for LibraryId, UpdateItemsArray in list(UpdateItems.items()):
            for ContentType, UpdateItemsIds in list(UpdateItemsArray.items()):
                if not UpdateItemsIds:
                    continue

                if ContentType == "unknown":
                    ContentType = ["Folder", "Episode", "Movie", "Trailer", "MusicVideo", "BoxSet", "MusicAlbum", "MusicArtist", "Season", "Series", "Audio", "Video", "Genre", "MusicGenre", "Tag", "Person", "Studio", "Playlist"]
                else:
                    ContentType = [ContentType]

                UpdateItemsIdsTemp = UpdateItemsIds.copy()
                self.EmbyServer.API.ProcessProgress["worker_update"] = 0

                for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items_Ids(UpdateItemsIds, ContentType, False, False, "worker_update", LibraryId, {}, {"Object": self.pause_workers, "Params": ("Startsync_http", SQLs, ProgressBar, None)}), 1):
                    self.EmbyServer.API.ProcessProgress["worker_update"] = ItemIndex

                    if Item['Id'] in UpdateItemsIds:
                        UpdateItemsIds.remove(Item['Id'])

                    yield True, Item

                # Remove not detected Items
                for UpdateItemsIdTemp in UpdateItemsIdsTemp:
                    if UpdateItemsIdTemp in UpdateItemsIds:
                        UpdateItemsIds.remove(UpdateItemsIdTemp)
                        RefreshDynamicNodes = True
                        yield False, {'Id': UpdateItemsIdTemp}

        if RefreshDynamicNodes:
            refresh_dynamic_nodes()

    def worker_remove(self, IncrementalSync):
        with LockLowPriorityWorkers:
            WorkerName = "worker_remove"

            if not self.wait_DatabaseInit(WorkerName):
                return False

            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            RemoveItems = embydb.get_RemoveItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            del embydb

            xbmc.log(f"EMBY.database.library: -->[ worker remove started ] queue size: {len(RemoveItems)}", 0) # LOGDEBUG

            if not RemoveItems:
                xbmc.log("EMBY.database.library: --<[ worker remove empty ]", 0) # LOGDEBUG
                return True

            if not self.open_Worker(WorkerName):
                return False

            RefreshAudio = False
            RefreshVideo = False
            ProgressBar = xbmcgui.DialogProgressBG()
            ProgressBar.create(utils.Translate(33199), utils.Translate(33261))
            RecordsPercent = len(RemoveItems) / 100
            SQLs = self.open_EmbyDBRW(WorkerName, False)
            UpdateItems, Others = ItemsSort(self.worker_remove_generator, SQLs, RemoveItems, True, RecordsPercent, ProgressBar)

            if not SQLs['emby']:
                xbmc.log("EMBY.database.library: --<[ worker remove interrupt ] (ItemsSort)", 0) # LOGDEBUG
                return False

            for KodiDBs, CategoryItems in list(UpdateItems.items()):
                if content_available(CategoryItems):
                    dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                    for Items in CategoryItems:
                        self.ContentObject = None
                        RecordsPercent = len(Items) / 100
                        RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                        for index, Item in enumerate(Items, 1):
                            Item = json.loads(Item)
                            SQLs["emby"].delete_RemoveItem(Item['Id'])
                            Continue, _ = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar, IncrementalSync)

                            if not Continue:
                                xbmc.log("EMBY.database.library: --<[ worker remove interrupt ]", 0) # LOGDEBUG
                                return False

                    dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

            for Other in Others:
                SQLs["emby"].delete_RemoveItem(json.loads(Other)['Id'])

            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
            self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)
            xbmc.log("EMBY.database.library: --<[ worker remove completed ]", 0) # LOGDEBUG

        return True

    def worker_remove_generator(self, SQLs, RemoveItems, RecordsPercent, ProgressBar):
        RefreshDynamicNodes = False

        for index, RemoveItem in enumerate(RemoveItems, 1):
            if not self.pause_workers("worker_remove_generator", SQLs, ProgressBar, None):
                break

            ProgressBar.update(int(index / RecordsPercent), utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = SQLs["emby"].get_remove_generator_items(RemoveItem[0], RemoveItem[1])
            SQLs["emby"].delete_RemoveItem(RemoveItem[0])

            for EmbyId, KodiItemId, KodiFileId, EmbyType, EmbyPresentationKey, KodiParentId, KodiPathId, isSpecial in FoundRemoveItems:
                yield True, {'Id': EmbyId, 'Type': EmbyType, 'LibraryId': RemoveItem[1], 'KodiItemId': KodiItemId, 'KodiFileId': KodiFileId, "PresentationUniqueKey": EmbyPresentationKey, "KodiParentId": KodiParentId, "KodiPathId": KodiPathId, "isSpecial": isSpecial}

            if not FoundRemoveItems:
                RefreshDynamicNodes = True

        if RefreshDynamicNodes:
            refresh_dynamic_nodes()

    def worker_library_remove(self):
        with LockLibraryOps:
            with LockLowPriorityWorkers:
                WorkerName = "worker_library_remove"

                if not self.wait_DatabaseInit(WorkerName):
                    return False

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                RemovedLibraries = embydb.get_LibraryRemove()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                del embydb
                xbmc.log(f"EMBY.database.library: -->[ worker library started ] queue size: {len(RemovedLibraries)}", 0) # LOGDEBUG

                if not RemovedLibraries:
                    xbmc.log("EMBY.database.library: --<[ worker library empty ]", 0) # LOGDEBUG
                    return True

                if not self.open_Worker(WorkerName):
                    return False

                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33184))
                RemovedLibrariesPercent = len(RemovedLibraries) / 100
                SQLs = self.open_EmbyDBRW(WorkerName, False)

                for RemovedLibraryIndex, RemovedLibrary in enumerate(RemovedLibraries):
                    SQLs["emby"].remove_LibraryRemove(RemovedLibrary[0])
                    ProgressBar.update(int(RemovedLibraryIndex / RemovedLibrariesPercent), f"{utils.Translate(33184)}", RemovedLibrary[1])
                    SQLs["emby"].add_remove_library_items(RemovedLibrary[0])
                    xbmc.log(f"EMBY.database.library: ---[ removed library: {RemovedLibrary[0]} ]", 1) # LOGINFO
                    dbio.DBOpenRW("video", WorkerName, SQLs)
                    SQLs["video"].delete_tag(RemovedLibrary[1])
                    SQLs["video"].delete_path(f"{utils.AddonModePath}tvshows/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}movies/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}musicvideos/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    dbio.DBCloseRW("video", WorkerName, SQLs)
                    dbio.DBOpenRW("music", WorkerName, SQLs)
                    SQLs["music"].delete_path(f"{utils.AddonModePath}audio/{self.EmbyServer.ServerData['ServerId']}/{RemovedLibrary[0]}/")
                    dbio.DBCloseRW("music", WorkerName, SQLs)
                    self.EmbyServer.Views.delete_playlist_by_id(RemovedLibrary[0])
                    self.EmbyServer.Views.delete_node_by_id(RemovedLibrary[0])
                    utils.notify_event("library_remove", {"EmbyId": f"{RemovedLibrary[0]}"}, True)

                self.load_LibrarySynced(SQLs)
                self.close_Worker(WorkerName, True, True, ProgressBar, SQLs)

        if RemovedLibraries:
            if self.worker_remove(False):
                SQLs = self.open_EmbyDBRW(f"{WorkerName}_clean", True)

                for RemovedLibrary in RemovedLibraries:
                    SQLs["emby"].remove_LibrarySyncedMirrow(RemovedLibrary[0])

                self.load_LibrarySynced(SQLs)
                self.close_EmbyDBRW(f"{WorkerName}_clean", SQLs)
                self.worker_library_add()

            self.EmbyServer.Views.update_nodes()
            utils.reset_querycache(None)

        xbmc.log("EMBY.database.library: --<[ worker library completed ]", 0) # LOGDEBUG
        return True

    def worker_library_add(self):
        with LockLibraryOps:
            with LockLowPriorityWorkers:
                WorkerName = "worker_library_add"

                if not self.wait_DatabaseInit(WorkerName):
                    return

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                AddedLibraries = embydb.get_LibraryAdd()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                del embydb
                xbmc.log(f"EMBY.database.library: -->[ worker library started ] queue size: {len(AddedLibraries)}", 0) # LOGDEBUG

                if not AddedLibraries:
                    xbmc.log("EMBY.database.library: --<[ worker library empty ]", 0) # LOGDEBUG
                    return

                if not self.open_Worker(WorkerName):
                    return

                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33238))
                GenreUpdate = False
                StudioUpdate = False
                TagUpdate = False
                MusicGenreUpdate = False
                PersonUpdate = False
                MusicArtistUpdate = False
                newContent = utils.newContent
                utils.newContent = False  # Disable new content notification on init sync
                SQLs = self.open_EmbyDBRW(WorkerName, False)
                SQLs["emby"].delete_Index()
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

                    ProgressBar.update(AddedLibraryProgress, f"{utils.Translate(33238)}", AddedLibrary[1])
                    SQLs["emby"].add_LibrarySyncedMirrow(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    self.load_LibrarySynced(SQLs)
                    dbio.DBOpenRW(AddedLibrary[3], WorkerName, SQLs)
                    VideoDB = AddedLibrary[3].find("video") != -1
                    MusicDB = AddedLibrary[3].find("music") != -1

                    if VideoDB:
                        SQLs["video"].delete_Index()

                    if MusicDB:
                        SQLs["music"].delete_Index()

                    self.ContentObject = None
                    self.EmbyServer.API.ProcessProgress[WorkerName] = 0

                    # Add Kodi tag for each library
                    if AddedLibrary[3] == "video" and AddedLibrary[0] != "999999999":
                        TagObject = tag.Tag(self.EmbyServer, SQLs)
                        TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"999999993{AddedLibrary[0]}", "Name": AddedLibrary[1], "Memo": "library"}, False)
                        del TagObject

                    # Sync Content
                    for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(AddedLibrary[0], [AddedLibrary[2]], False, True, {}, WorkerName, True, {"Object": self.pause_workers, "Params": (WorkerName, SQLs, ProgressBar, None)}), 1):
                        Item["LibraryId"] = AddedLibrary[0]
                        self.EmbyServer.API.ProcessProgress[WorkerName] = ItemIndex
                        Continue, _ = self.ItemOps(AddedLibraryProgress, ItemIndex, Item, SQLs, WorkerName, AddedLibrary[3], ProgressBar, False)

                        if not Continue:
                            self.EmbyServer.API.ProcessProgress[WorkerName] = -1
                            xbmc.log("EMBY.database.library: --<[ worker library interrupt ] (paused)", 0) # LOGDEBUG
                            return

                    if not SQLs["emby"]:
                        xbmc.log("EMBY.database.library: --<[ worker library interrupt ] (closed database)", 0) # LOGDEBUG-> db can be closed via http busyfunction
                        return

                    SQLs["emby"].add_LibrarySynced(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    SQLs["emby"].remove_LibraryAdd(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    self.load_LibrarySynced(SQLs)

                    if VideoDB:
                        SQLs["video"].add_Index()

                    if MusicDB:
                        SQLs["music"].add_Index()

                    dbio.DBCloseRW(AddedLibrary[3], WorkerName, SQLs)
                    utils.notify_event("library_add", {"EmbyId": f"{AddedLibrary[0]}"}, True)

                SQLs["emby"].add_Index()
                utils.newContent = newContent
                self.close_Worker(WorkerName, True, True, ProgressBar, SQLs)

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

                self.EmbyServer.Views.update_nodes()
                utils.reset_querycache(None)
                xbmc.log("EMBY.database.library: --<[ worker library completed ]", 0) # LOGDEBUG
        #        utils.sleep(2) # give Kodi time to catch up (otherwise could cause crashes)
        #        xbmc.executebuiltin('ReloadSkin()') # Skin reload broken in Kodi 21

    def ItemOps(self, ProgressValue, ItemIndex, Item, SQLs, WorkerName, KodiDBs, ProgressBar, IncrementalSync):
        set_recording_type(Item)
        Update = False

        if not self.ContentObject:
            self.load_libraryObject(Item['Type'], SQLs)

        if WorkerName in ("worker_library_add", "worker_update"):
            with LockPause:
                Ret = self.ContentObject.change(Item, IncrementalSync)

            if "Name" in Item:
                ProgressMsg = Item.get('Name', "unknown")
            elif "Path" in Item:
                ProgressMsg = Item['Path']
            else:
                ProgressMsg = "unknown"

            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", ProgressMsg)

            if Ret and utils.newContent:
                utils.Dialog.notification(heading=f"{utils.Translate(33049)} {Item['Type']}", message=Item.get('Name', "unknown"), icon=utils.icon, time=utils.newContentTime, sound=False)

            if not self.pause_workers(WorkerName, SQLs, ProgressBar, Item['Type']):
                return False, False
        elif WorkerName == "worker_remove":
            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))

            with LockPause:
                self.ContentObject.remove(Item, IncrementalSync)

            if not self.pause_workers(WorkerName, SQLs, ProgressBar, Item['Type']):
                return False, False
        elif WorkerName == "worker_userdata": # change userdata is a priority task, do not pause it
            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))
            Update = self.ContentObject.userdata(Item)

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)
            self.close_Worker(WorkerName, False, False, ProgressBar, SQLs)
            xbmc.log("EMBY.database.library: [ worker exit (shutdown 2) ]", 1) # LOGINFO
            return False, False

        del Item
        return True, Update

    def pause_workers(self, WorkerName, SQLs, ProgressBar, ItemType):
        with LockPauseBusy:
            # Check if Kodi db or emby is about to open -> close db, wait, reopen db
            if Worker_is_paused(WorkerName):
                Databases = set()

                for SQLKey, SQLDatabase in list(SQLs.items()):
                    if SQLDatabase:
                        if SQLKey == "emby":
                            Databases.add(self.EmbyServer.ServerData['ServerId'])
                        else:
                            Databases.add(SQLKey)

                Databases = ",".join(Databases)
                xbmc.log(f"EMBY.database.library: -->[ worker delay {WorkerName} ] {utils.SyncPause}", 0) # LOGDEBUG
                LockPause.acquire()

                if Databases:
                    dbio.DBCloseRW(Databases, WorkerName, SQLs)

                    if self.LockDBRWOpen.locked():
                        self.LockDBRWOpen.release()

                # Wait on progress updates
                while Worker_is_paused(WorkerName):
                    if utils.sleep(1):
                        ProgressBar.close()
                        del ProgressBar
                        xbmc.log(f"EMBY.database.library: -->[ worker delay {WorkerName} ] shutdown", 0) # LOGDEBUG
                        LockPause.release()
                        return False

                xbmc.log(f"EMBY.database.library: --<[ worker delay {WorkerName} ] {utils.SyncPause}", 0) # LOGDEBUG

                if Databases:
                    if not self.LockDBRWOpen.locked():
                        self.LockDBRWOpen.acquire()

                    dbio.DBOpenRW(Databases, WorkerName, SQLs)

                # Reload content object due to changed database -> SQLs
                self.load_libraryObject(ItemType, SQLs)
                LockPause.release()

        return True

    def load_libraryObject(self, MediaType, SQLs):
        if MediaType == "Movie":
            self.ContentObject = movies.Movies(self.EmbyServer, SQLs)
        elif MediaType == "Video":
            self.ContentObject = videos.Videos(self.EmbyServer, SQLs)
        elif MediaType == "MusicVideo":
            self.ContentObject = musicvideo.MusicVideo(self.EmbyServer, SQLs)
        elif MediaType == "MusicAlbum":
            self.ContentObject = musicalbum.MusicAlbum(self.EmbyServer, SQLs)
        elif MediaType == 'Audio':
            self.ContentObject = audio.Audio(self.EmbyServer, SQLs)
        elif MediaType == "Episode":
            self.ContentObject = episode.Episode(self.EmbyServer, SQLs)
        elif MediaType == "Season":
            self.ContentObject = season.Season(self.EmbyServer, SQLs)
        elif MediaType == "Folder":
            self.ContentObject = folder.Folder(self.EmbyServer, SQLs)
        elif MediaType == "BoxSet":
            self.ContentObject = boxsets.BoxSets(self.EmbyServer, SQLs)
        elif MediaType == "Genre":
            self.ContentObject = genre.Genre(self.EmbyServer, SQLs)
        elif MediaType == "Series":
            self.ContentObject = series.Series(self.EmbyServer, SQLs)
        elif MediaType == "MusicGenre":
            self.ContentObject = musicgenre.MusicGenre(self.EmbyServer, SQLs)
        elif MediaType == "MusicArtist":
            self.ContentObject = musicartist.MusicArtist(self.EmbyServer, SQLs)
        elif MediaType == "Tag":
            self.ContentObject = tag.Tag(self.EmbyServer, SQLs)
        elif MediaType == "Person":
            self.ContentObject = person.Person(self.EmbyServer, SQLs)
        elif MediaType == "Studio":
            self.ContentObject = studio.Studio(self.EmbyServer, SQLs)
        elif MediaType == "Playlist":
            self.ContentObject = playlist.Playlist(self.EmbyServer, SQLs)

    # Run workers in specific order
    def RunJobs(self, IncrementalSync):
        self.worker_userdata()

        if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
            if self.worker_remove(IncrementalSync):
                if self.worker_update(IncrementalSync):
                    if self.worker_library_remove():
                        self.worker_library_add()
        else:
            xbmc.log("EMBY.database.library: RunJobs limited due to server busy", 1) # LOGINFO

            if self.worker_library_remove():
                self.worker_library_add()

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):
        LibrariesSelected = ()
        LibrariesSelectedIds = ()
        utils.reset_querycache(None)
        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")

        if mode in ('RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            PendingSyncRemoved = embydb.get_LibraryRemove_EmbyLibraryIds()

            for LibrarySyncedId, LibrarySyncedName, _, _ in self.LibrarySynced:
                if LibrarySyncedName != "shared" and LibrarySyncedId not in PendingSyncRemoved:
                    if LibrarySyncedId not in LibrariesSelectedIds:
                        LibrariesSelectedIds += (LibrarySyncedId,)
                        LibrariesSelected += ({'Id': LibrarySyncedId, 'Name': LibrarySyncedName},)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()
            PendingSyncAdded = embydb.get_LibraryAdd_EmbyLibraryIds()

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ("movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos", "playlists") and AvailableLibId not in self.LibrarySyncedNames and AvailableLibId not in PendingSyncAdded:
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
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")
            return

        Selections = utils.Dialog.multiselect(Text, SelectionMenu)

        if not Selections:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")
            return

        # "All" selected
        if 0 in Selections:
            Selections = list(range(1, len(LibrariesSelected) + 1))

        xbmc.executebuiltin('Dialog.Close(addoninformation)')
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

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")
        SQLs = self.open_EmbyDBRW("select_libraries", True)

        if LibraryRemoveItems:
            # detect shared content type
            removeGlobalVideoContent = True

            for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                if LibrarySyncedId not in LibraryIdsRemove and LibrarySyncedEmbyType in ('Movie', 'Series', 'Video', 'MusicVideo'):
                    removeGlobalVideoContent = False
                    break

            if removeGlobalVideoContent:
                xbmc.log("EMBY.database.library: ---[ remove library: 999999999 / Person ]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced("999999999")
                SQLs["emby"].add_LibraryRemove("999999999", "Person")

            # Remove libraries
            for LibraryIdRemove in LibraryRemoveItems:
                xbmc.log(f"EMBY.database.library: ---[ remove library: {LibraryIdRemove['Id']} / {LibraryIdRemove['Name']}]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced(LibraryIdRemove["Id"])
                SQLs["emby"].add_LibraryRemove(LibraryIdRemove["Id"], LibraryIdRemove["Name"])

            self.load_LibrarySynced(SQLs)

        if LibraryIdsAdd:
            # detect shared content type
            syncGlobalVideoContent = False

            for LibraryIdAdd in LibraryIdsAdd:
                if LibraryIdAdd in self.EmbyServer.Views.ViewItems:
                    ViewData = self.EmbyServer.Views.ViewItems[LibraryIdAdd]

                    if ViewData[1] in ('movies', 'tvshows', 'mixed', 'musicvideos'):
                        syncGlobalVideoContent = True
                        break

            for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                if LibrarySyncedId == "999999999" and LibrarySyncedEmbyType == "Person":
                    syncGlobalVideoContent = False

            if syncGlobalVideoContent:
                SQLs["emby"].add_LibraryAdd("999999999", "shared", "Person", "video") # Person can only be queried globally by Emby server
                xbmc.log("EMBY.database.library: ---[ added library: 999999999 ]", 1) # LOGINFO
                syncGlobalVideoContent = False

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
                    elif library_type == 'movies':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Movie", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                    elif library_type == 'musicvideos':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicVideo", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                    elif library_type == 'homevideos':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Playlist", "none")
                    elif library_type == 'tvshows':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Series", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Season", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Episode", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "BoxSet", "video")
                    elif library_type in ('music', 'audiobooks', 'podcasts'):
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicGenre", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicArtist", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "MusicAlbum", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Audio", "music")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Playlist", "none")
                    elif library_type == 'playlists':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Playlist", "none")

                    if library_type != 'playlists':
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Folder", "none")

                    xbmc.log(f"EMBY.database.library: ---[ added library: {LibraryId} ]", 1) # LOGINFO
                else:
                    xbmc.log(f"EMBY.database.library: ---[ added library not found: {LibraryId} ]", 1) # LOGINFO

            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())

        self.close_EmbyDBRW("select_libraries", SQLs)

        if LibraryIdsRemove:
            utils.start_thread(self.worker_library_remove, ())

        if LibraryIdsAdd and not LibraryIdsRemove:
            utils.start_thread(self.worker_library_add, ())

    def refresh_boxsets(self):  # threaded by caller
        SQLs = self.open_EmbyDBRW("refresh_boxsets", False)
        dbio.DBOpenRW("video", "refresh_boxsets", SQLs)
        xbmc.executebuiltin('Dialog.Close(addoninformation)')

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

    def SyncThemes(self):
        if not utils.check_tvtunes:
            return

        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        LibraryThemeIds = set()
        DownloadThemes = False
        Path = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-themes")
        utils.mkDir(Path)
        Path = utils.PathAddTrailing(f"{Path}{self.EmbyServer.ServerData['ServerId']}")
        utils.mkDir(Path)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"service.tvtunes","enabled":true}}')
        tvtunes = xbmcaddon.Addon(id="service.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', Path)
        xbmc.log("EMBY.database.library: TV Tunes custom path is enabled and set", 1) # LOGINFO

        if not utils.useDirectPaths:
            DownloadThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33641))

        UseAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33481))
        UseVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33482))
        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33451))

        for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
            if LibrarySyncedEmbyType in ('Movie', 'Series'):
                LibraryThemeIds.add(LibrarySyncedId)

        items = {}

        for LibraryThemeId in LibraryThemeIds:
            if UseVideoThemes:
                for item in self.EmbyServer.API.get_Items(LibraryThemeId, ["Movie", "Series"], True, True, {'HasThemeVideo': "True"}, "", False, None):
                    items[item['Id']] = normalize_string(item['Name'])

            if UseAudioThemes:
                for item in self.EmbyServer.API.get_Items(LibraryThemeId, ["Movie", "Series"], True, True, {'HasThemeSong': "True"}, "", False, None):
                    items[item['Id']] = normalize_string(item['Name'])

        Index = 1
        TotalItems = len(items) / 100

        for ItemId, Name in list(items.items()):
            ProgressBar.update(int(Index / TotalItems), utils.Translate(33451), Name)
            NfoPath = utils.PathAddTrailing(f"{Path}{Name}")
            NfoPath = utils.translatePath(NfoPath).decode('utf-8')
            utils.mkDir(NfoPath)
            NfoFile = f"{NfoPath}tvtunes.nfo"
            ThemeItems = []

            if UseAudioThemes and not UseVideoThemes:
                Theme = self.EmbyServer.API.get_themes(ItemId, True, False)

                if 'ThemeSongsResult' in Theme:
                    ThemeItems += Theme['ThemeSongsResult']['Items']
            elif UseVideoThemes and not UseAudioThemes:
                Theme = self.EmbyServer.API.get_themes(ItemId, False, True)

                if 'ThemeVideosResult' in Theme:
                    ThemeItems += Theme['ThemeVideosResult']['Items']
            elif UseVideoThemes and UseAudioThemes:
                Theme = self.EmbyServer.API.get_themes(ItemId, True, True)

                if 'ThemeSongsResult' in Theme:
                    ThemeItems += Theme['ThemeSongsResult']['Items']

                if 'ThemeVideosResult' in Theme:
                    ThemeItems += Theme['ThemeVideosResult']['Items']

            if utils.SystemShutdown:
                ProgressBar.close()
                del ProgressBar
                return

            # add content sorted by audio -> video
            if ThemeItems:
                XMLData = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<tvtunes>\n'

                for ThemeItem in ThemeItems:
                    if 'Path' not in ThemeItem or 'Size' not in ThemeItem or not ThemeItem['Size']:
                        xbmc.log(f"EMBY.database.library: Theme: No Path or Size {ThemeItem}", 0) # LOGDEBUG
                        xbmc.log(f"EMBY.database.library: Theme: No Path or Size: {ThemeItem['Id']}", 3) # LOGERROR
                        continue

                    if DownloadThemes:
                        ThemeItem['KodiFullPath'] = f"{NfoPath}{ThemeItem['Id']}-{ThemeItem['MediaSources'][0]['Id']}"

                        if not utils.checkFileExists(ThemeItem['KodiFullPath']):
                            utils.EmbyServer.API.download_file(ThemeItem['Id'], "", NfoPath, ThemeItem['KodiFullPath'], ThemeItem['Size'], Name, "", "", "", "")
                    else:
                        common.set_streams(ThemeItem)
                        common.set_chapters(ThemeItem, self.EmbyServer.ServerData['ServerId'])
                        common.set_path_filename(ThemeItem, self.EmbyServer.ServerData['ServerId'], None, True)

                    XMLData += f"    <file>{utils.encode_XML(ThemeItem['KodiFullPath'])}</file>\n".encode("utf-8")

                XMLData += b'</tvtunes>'
                utils.delFile(NfoFile)
                utils.writeFileBinary(NfoFile, XMLData)

            Index += 1

        ProgressBar.close()
        del ProgressBar
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=utils.displayMessage, sound=False)

    def SyncLiveTV(self):
        if not utils.check_iptvsimple():
            return

        xbmc.log("EMBY.database.library: -->[ iptv simple config change ]", 1) # LOGINFO
        SQLs = {}
        dbio.DBOpenRW("epg", "livetvsync", SQLs)
        SQLs["epg"].delete_tables("EPG")
        dbio.DBCloseRW("epg", "livetvsync", SQLs)
        dbio.DBOpenRW("tv", "livetvsync", SQLs)
        SQLs["tv"].delete_tables("TV")
        dbio.DBCloseRW("tv", "livetvsync", SQLs)
        PlaylistFile = f"{utils.FolderEmbyTemp}{self.EmbyServer.ServerData['ServerId']}-livetv.m3u"
        utils.delFile(PlaylistFile)
        PlaylistM3U = "#EXTM3U\n"
        ChannelsUnsorted = []
        ChannelsSortedbyChannelNumber = {}
        Channels = self.EmbyServer.API.get_channels()

        if not utils.LiveTVEnabled:
            xbmc.log("EMBY.database.library: --<[ iptv simple disabled ]", 1) # LOGINFO
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
        for ChannelSorted in ChannelsSorted:
            ChannelSorted['MediaSources'] = self.EmbyServer.API.get_PlaybackInfo(ChannelSorted['Id'])

            if ChannelSorted['TagItems']:
                Tag = ChannelSorted['TagItems'][0]['Name']
            else:
                Tag = "--NO INFO--"

            tvglogo = ""
            tvgchno = ""
            ChannelNumber = ChannelSorted.get("ChannelNumber", "")

            if ChannelSorted['ImageTags']:
                if 'Primary' in ChannelSorted['ImageTags']:
                    tvglogo = f" tvg-logo=\"http://127.0.0.1:57342/picture/{self.EmbyServer.ServerData['ServerId']}/p-{ChannelSorted['Id']}-0-p-{ChannelSorted['ImageTags']['Primary']}\""

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

        utils.writeFileString(PlaylistFile, PlaylistM3U)
        self.SyncLiveTVEPG(False)

        if not utils.LiveTVEnabled:
            return

        SimpleIptvSettings = utils.readFileString("special://home/addons/plugin.service.emby-next-gen/resources/iptvsimple.xml")
        SimpleIptvSettings = SimpleIptvSettings.replace("SERVERID", self.EmbyServer.ServerData['ServerId'])
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
        utils.writeFileBinary(f"special://profile/addon_data/pvr.iptvsimple/instance-settings-{str(int(self.EmbyServer.ServerData['ServerId'], 16))[:4]}.xml", SimpleIptvSettings.encode("utf-8"))
        utils.sleep(3)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')
        xbmc.log("EMBY.database.library: --<[ iptv simple config change ]", 1) # LOGINFO

    def SyncLiveTVEPG(self, ChannelSync=True):
        if not utils.LiveTVEnabled:
            return

        xbmc.log("EMBY.database.library: -->[ load EPG ]", 1) # LOGINFO
        epg = '<?xml version="1.0" encoding="utf-8" ?><tv>'

        for item in self.EmbyServer.API.get_channelprogram():
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
        utils.writeFileString(EPGFile, epg)

        if utils.LiveTVEnabled and utils.SyncLiveTvOnEvents and ChannelSync:
            self.SyncLiveTV()

        xbmc.log("EMBY.database.library: --<[ load EPG ]", 1) # LOGINFO

    # Add item_id to userdata queue
    def userdata(self, ItemIds):  # threaded by caller -> websocket via monitor
        xbmc.log("EMBY.database.library: -->[ userdata ]", 0) # LOGDEBUG

        if ItemIds:
            SQLs = self.open_EmbyDBRW("userdata", True)

            for ItemId in ItemIds:
                SQLs["emby"].add_Userdata(str(ItemId))

            self.close_EmbyDBRW("userdata", SQLs)
            self.worker_userdata()

        xbmc.log("EMBY.database.library: --<[ userdata ]", 0) # LOGDEBUG

    # Add item_id to updated queue
    def updated(self, Items, IncrementalSync):  # threaded by caller
        xbmc.log("EMBY.database.library: -->[ updated ]", 0) # LOGDEBUG

        if Items:
            SQLs = self.open_EmbyDBRW("updated", True)

            for Item in Items:
                SQLs["emby"].add_UpdateItem(Item[0], Item[1], Item[2])

            self.close_EmbyDBRW("updated", SQLs)

            if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
                self.worker_update(IncrementalSync)
            else:
                xbmc.log("EMBY.database.library: updated trigger skipped due to server busy", 1) # LOGINFO

        xbmc.log("EMBY.database.library: --<[ updated ]", 0) # LOGDEBUG

    # Add item_id to removed queue
    def removed(self, Ids, IncrementalSync):  # threaded by caller
        xbmc.log("EMBY.database.library: -->[ removed ]", 0) # LOGDEBUG

        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)

            for Id in Ids:
                SQLs["emby"].add_RemoveItem(Id, None)

            self.close_EmbyDBRW("removed", SQLs)

            if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
                self.worker_remove(IncrementalSync)
            else:
                xbmc.log("EMBY.database.library: removed trigger skipped due to server busy", 1) # LOGINFO

        xbmc.log("EMBY.database.library: --<[ removed ]", 0) # LOGDEBUG

    # Add item_id to removed queue
    def removed_deduplicate(self, Ids):  # threaded by caller
        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)

            for Id in Ids:
                SQLs["emby"].add_RemoveItem(Id[1], Id[0])

            self.close_EmbyDBRW("removed", SQLs)
            self.worker_remove(True)

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

def Worker_is_paused(WorkerName):
    for Key, Busy in list(utils.SyncPause.items()):
        if Busy:
            if WorkerName == "worker_remove" and Key.startswith("server_busy_"): # Continue on progress updates, even emby server is busy
                continue

            xbmc.log(f"EMBY.database.library: Worker_is_paused: {WorkerName} / {utils.SyncPause}", 1) # LOGINFO
            return True

    return False

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

def ItemsSort(GeneratorFunction, SQLs, Items, Reverse, RecordsPercent, ProgressBar):
    SortItems = {'Movie': set(), 'Video': set(), 'BoxSet': set(), 'MusicVideo': set(), 'Series': set(), 'Episode': set(), 'MusicAlbum': set(), 'MusicArtist': set(), 'AlbumArtist': set(), 'Season': set(), 'Folder': set(), 'Audio': set(), 'Genre': set(), 'MusicGenre': set(), 'Tag': set(), 'Person': set(), 'Studio': set(), 'Playlist': set()}
    Others = set()

    for Valid, Item in GeneratorFunction(SQLs, Items, RecordsPercent, ProgressBar):
        if not Item:
            continue

        set_recording_type(Item)

        if Valid and Item['Type'] in SortItems:
            SortItems[Item['Type']].add(json.dumps(Item)) # Dict is not hashable (not possible adding "dict" to "set") -> convert to json string necessary
        else:
            Others.add(json.dumps(Item))
            xbmc.log(f"EMBY.database.library: Unknown {Item}", 1) # LOGINFO
            continue

    if Reverse:
        return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['BoxSet'], SortItems['Video'], SortItems['Movie'], SortItems['Episode'], SortItems['Season'], SortItems['Series']], "music,video": [SortItems['MusicGenre'], SortItems['Audio'], SortItems['MusicVideo'], SortItems['MusicAlbum'], SortItems['MusicArtist']], "none": [SortItems['Folder'], SortItems['Playlist']]}, Others

    return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['Series'], SortItems['Season'], SortItems['Episode'], SortItems['Movie'], SortItems['Video'], SortItems['BoxSet']], "music,video": [SortItems['MusicGenre'], SortItems['MusicArtist'], SortItems['MusicAlbum'], SortItems['MusicVideo'], SortItems['Audio']], "none": [SortItems['Folder'], SortItems['Playlist']]}, Others

def set_recording_type(Item):
    if 'Type' in Item:
        if Item['Type'] == "Recording":
            xbmc.log("EMBY.database.library: Recording detected", 0) # LOGDEBUG

            if Item.get('IsSeries', False):
                Item['Type'] = 'Episode'
            else:
                Item['Type'] = 'Movie'

def refresh_dynamic_nodes():
    utils.reset_querycache(None)
    MenuPath = xbmc.getInfoLabel('Container.FolderPath')

    if MenuPath.startswith("plugin://plugin.service.emby-next-gen/") and "mode=browse" in MenuPath.lower():
        xbmc.log("Emby.hooks.websocket: [ UserDataChanged refresh dynamic nodes ]", 1) # LOGINFO
        xbmc.executebuiltin('Container.Refresh')
    else:
        utils.refresh_widgets(True)
        utils.refresh_widgets(False)

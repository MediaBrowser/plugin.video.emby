from _thread import allocate_lock
import os
import json
from urllib.parse import quote
import unicodedata
import xbmcvfs
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
        xbmc.log(f"EMBY.database.library: -->[ Emby server {EmbyServer.ServerData['ServerId']}: library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.LibrarySynced = []
        self.LibrarySyncedKodiDBs = {}
        self.LibrarySyncedNames = {}
        self.LibrarySyncedContent = {}
        self.LastSyncTime = ""
        self.SettingsLoaded = False
        self.LockKodiStartSync = allocate_lock()
        self.LockDBRWOpen = allocate_lock()

    # Wait for database init
    def wait_DatabaseInit(self, WorkerName):
        if utils.SyncPause.get(f"database_init_{self.EmbyServer.ServerData['ServerId']}", True):
            xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Wait for database init ]", 1) # LOGINFO

            while utils.SyncPause.get(f"database_init_{self.EmbyServer.ServerData['ServerId']}", True):
                xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: worker {WorkerName} wait for database init ]", 1) # LOGINFO

                if utils.sleep(1):
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Wait for database init (shutdown) ]", 1) # LOGINFO
                    return False

            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Wait for database init ]", 1) # LOGINFO

        return True

    def open_Worker(self, WorkerName):
        utils.get_scans()

        if self.Worker_is_paused(WorkerName):
            xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Worker_is_paused ]", 1) # LOGINFO

            while self.Worker_is_paused(WorkerName):
                if utils.sleep(1):
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Worker_is_paused (shutdown) ]", 1) # LOGINFO
                    return False

            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: open_Worker delay: Worker_is_paused ]", 1) # LOGINFO

        if utils.SystemShutdown:
            return False

        return True

    def close_Worker(self, WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs):
        self.close_EmbyDBRW(WorkerName, SQLs)
        common.CachedItemsMissing = {}
        common.CachedArtworkDownload = ()

        if RefreshVideo:
            utils.refresh_widgets(True)

        if RefreshAudio:
            utils.refresh_widgets(False)

        if ProgressBar:
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
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = True

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
        dbio.DBOpenRW("epg", "load_settings", SQLs)
        SQLs["epg"].analyze()
        dbio.DBCloseRW("epg", "load_settings", SQLs)
        dbio.DBOpenRW("tv", "load_settings", SQLs)
        SQLs["tv"].analyze()
        dbio.DBCloseRW("tv", "load_settings", SQLs)
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = False
        self.SettingsLoaded = True
        xbmc.log(f"EMBY.database.library: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: load settings ]", 1) # LOGINFO

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        xbmc.log(f"EMBY.database.library: THREAD: --->[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ]", 0) # LOGDEBUG

        with self.LockKodiStartSync:
            if not utils.startsyncenabled:
                xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] IncrementalSync disabled", 0) # LOGDEBUG
                return

            # Verify time sync
            _, UnixTime = utils.currenttime_kodi_format_and_unixtime()

            if UnixTime < 946684800: # 01-01-2000
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33751), icon=utils.icon, time=60000, sound=True)
                return

            NewSyncData = utils.currenttime()

            while not self.SettingsLoaded:
                if utils.sleep(1):
                    xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] shutdown 1", 0) # LOGDEBUG
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
            UpdateData = [[], []]

            if utils.SystemShutdown:
                xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] shutdown 2", 0) # LOGDEBUG
                return

            # Retrieve changes
            if self.LastSyncTime:
                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Retrieve changes, last synced: {self.LastSyncTime}", 1) # LOGINFO
                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33445))
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: Kodi companion ]", 1) # LOGINFO
                result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

                if 'ItemsRemoved' in result:
                    if result['ItemsRemoved']:
                        self.removed(result['ItemsRemoved'], True, False)
                else:
                    utils.Dialog.ok(utils.addon_name, utils.Translate(33716))

                xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: Kodi companion ]", 1) # LOGINFO
                ProgressBarTotal = len(self.LibrarySynced) / 100
                ProgressBarIndex = 0

                for LibrarySyncedId, LibrarySyncedName, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                    if utils.SystemShutdown:
                        xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] shutdown 3", 0) # LOGDEBUG
                        ProgressBar.close()
                        del ProgressBar
                        return

                    xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] {LibrarySyncedName} / {LibrarySyncedEmbyType}", 1) # LOGINFO
                    LibraryName = ""
                    ProgressBarIndex += 1

                    if LibrarySyncedId in self.EmbyServer.Views.ViewItems:
                        LibraryName = self.EmbyServer.Views.ViewItems[LibrarySyncedId][0]
                        ProgressBar.update(int(ProgressBarIndex / ProgressBarTotal), utils.Translate(33445), f"{LibraryName} / {LibrarySyncedEmbyType}")

                    if not LibraryName and LibrarySyncedEmbyType != "Person":
                        xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: KodiIncrementalSync remove library {LibrarySyncedId} ]", 1) # LOGINFO
                        continue

                    ItemIndex = 0
                    UpdateDataTemp = 10000 * [()] # pre allocate memory
                    UpdateUserDataTemp = 10000 * [()] # pre allocate memory

                    if LibrarySyncedEmbyType == "Folder":
                        Params = {'MinDateLastSaved': self.LastSyncTime}
                    else:
                        Params = {'MinDateLastSavedForUser': self.LastSyncTime, "Fields": "UserDataLastPlayedDate"}

                    for Item in self.EmbyServer.API.get_Items(LibrarySyncedId, (LibrarySyncedEmbyType,), True, Params, "", None, True, True):
                        if utils.SystemShutdown:
                            ProgressBar.close()
                            del ProgressBar
                            xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] shutdown 4", 0) # LOGDEBUG
                            return

                        if ItemIndex >= 10000:
                            UpdateData[0] += UpdateDataTemp
                            UpdateData[1] += UpdateUserDataTemp
                            UpdateDataTemp = 10000 * [()] # pre allocate memory
                            UpdateUserDataTemp = 10000 * [()] # pre allocate memory
                            ItemIndex = 0

                        self.set_recording_type(Item)
                        UpdateDataTemp[ItemIndex] = (Item['Id'], Item['Type'], LibrarySyncedId)
                        UpdateUserDataTemp[ItemIndex] = (Item['Id'], Item['Type'], Item['UserData'].get("PlaybackPositionTicks", None), Item['UserData'].get("PlayCount", None), Item['UserData'].get("IsFavorite", None), Item['UserData'].get("Played", None), Item['UserData'].get("LastPlayedDate", None), Item['UserData'].get("PlayedPercentage", None), Item['UserData'].get("UnplayedItemCount", None))
                        ItemIndex += 1

                    UpdateData[0] += UpdateDataTemp
                    UpdateData[1] += UpdateUserDataTemp

                ProgressBar.close()
                del ProgressBar

                if utils.SystemShutdown:
                    xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ] shutdown 5", 0) # LOGDEBUG
                    return

            # Run jobs
            # Items updates
            if UpdateData[0]:
                UpdateData[0] = list(dict.fromkeys(UpdateData[0])) # filter doubles

                if () in UpdateData[0]:  # Remove empty
                    UpdateData[0].remove(())

                if UpdateData[0]:
                    self.updated(UpdateData[0], True, False)

            # Userdata updated
            if UpdateData[1]:
                UpdateData[1] = list(dict.fromkeys(UpdateData[1])) # filter doubles

                if () in UpdateData[1]:  # Remove empty
                    UpdateData[1].remove(())

                if UpdateData[1]:
                    self.userdata(UpdateData[1], True, False)

            self.RunJobs(True)

        self.set_syncdate(NewSyncData)
        self.SyncLiveTVEPG()
        xbmc.log(f"EMBY.database.library: THREAD: ---<[ Emby server {self.EmbyServer.ServerData['ServerId']}: retrieve changes ]", 0) # LOGDEBUG

    # Userdata change is an high priority task
    def worker_userdata(self, IncrementalSync):
        WorkerName = "worker_userdata"
        UpdateUserDataCached = ()

        if not self.wait_DatabaseInit(WorkerName):
            return

        SQLs = {"emby": dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)}
        UserDataItems = SQLs["emby"].get_Userdata()
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker userdata started ] queue size: {len(UserDataItems)}", 0) # LOGDEBUG

        if not UserDataItems:
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker userdata empty ]", 0) # LOGDEBUG
            return

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
        RecordsPercent = len(UserDataItems) / 100
        UpdateItems, Others = self.ItemsSort(self.worker_userdata_generator, SQLs, UserDataItems, False, RecordsPercent, ProgressBar)

        if not SQLs['emby']:
            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker userdata interrupt ] (ItemsSort)", 0) # LOGDEBUG
            return

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        SQLs = self.open_EmbyDBRW(WorkerName, True)
        RefreshAudio = False
        RefreshVideo = False
        RefreshWidgets = False

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            if content_available(CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                for Items in CategoryItems:
                    if not Items:
                        continue

                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                    ClassObject = None

                    for index, Item in enumerate(Items, 1):
                        Item = json.loads(Item)

                        if not ClassObject:
                            ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                        SQLs["emby"].delete_Userdata(Item["Id"])
                        Continue, Update = self.update_UserData(int(index / RecordsPercent), index, Item, SQLs, KodiDBs, ProgressBar, IncrementalSync, ClassObject, True)
                        UpdateUserDataCached += ((str(Item['Id']), Item.get('PlaybackPositionTicks', 0), Item.get('LastPlayedDate', ""), common.set_PlayCount(Item), False),)

                        if Update:
                            RefreshWidgets = True

                        if not Continue:
                            del ClassObject
                            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker userdata interrupt ]", 0) # LOGDEBUG
                            return

                    del ClassObject

                dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

        for Other in Others: # Unsynced content
            Other = json.loads(Other)
            SQLs["emby"].delete_Userdata(Other['Id'])
            UpdateUserDataCached += ((str(Other['Id']), Other.get('PlaybackPositionTicks', 0), Other.get('LastPlayedDate', ""), common.set_PlayCount(Other), False),)

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
        utils.update_querycache_userdata(UpdateUserDataCached)
        del UpdateUserDataCached

        if Others:
            self.close_Worker(WorkerName, True, True, ProgressBar, SQLs)
        else:
            if RefreshWidgets:
                self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)
            else:
                self.close_Worker(WorkerName, False, False, ProgressBar, SQLs)

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker userdata completed ]", 0) # LOGDEBUG

    def worker_userdata_generator(self, SQLs, UserDataItems, RecordsPercent, ProgressBar):
        for index, UserDataItem in enumerate(UserDataItems, 1): # UserDataItem = EmbyId, EmbyType, EmbyPlaybackPositionTicks, EmbyPlayCount, EmbyIsFavorite, EmbyPlayed, EmbyLastPlayedDate
            ProgressBar.update(int(index / RecordsPercent), utils.Translate(33178), str(UserDataItem[0]))
            MetaData = SQLs["emby"].get_UserData_MetaData(UserDataItem[0], UserDataItem[1])
            MetaData.update({"Id": UserDataItem[0], 'PlaybackPositionTicks': UserDataItem[2], 'PlayCount': UserDataItem[3], 'IsFavorite': UserDataItem[4], 'LastPlayedDate': UserDataItem[6], 'Played': UserDataItem[5], 'PlayedPercentage': UserDataItem[7], 'UnplayedItemCount': UserDataItem[8]})

            if MetaData['KodiItemId']:
                yield True, MetaData
            else: # skip if item is not synced
                yield False, MetaData
                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Skip not synced item: {UserDataItem[0]}", 0) # LOGDEBUG

    def worker_update(self, IncrementalSync):
        MusicVideoLinks = False
        WorkerName = "worker_update"

        while True: # While running update additional updates migth be addded
            with LockLowPriorityWorkers:
                if not self.wait_DatabaseInit(WorkerName):
                    return False

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                UpdateItems, UpdateItemsCount, KodiDBMapping = embydb.get_UpdateItem()
                RemoveItems = embydb.empty_RemoveItem()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                del embydb

            # Re-run if removed items are added while waiting for updates
            if RemoveItems:
                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Worker update, removed items found, trigger removal", 0) # LOGDEBUG
                self.worker_remove(IncrementalSync)

            # Process updates
            with LockLowPriorityWorkers:
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker update started ] queue size: {UpdateItemsCount}", 0) # LOGDEBUG

                if not UpdateItemsCount: # Job done
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker update empty ]", 0) # LOGDEBUG

                    if utils.LinkMusicVideos and MusicVideoLinks:
                        self.refresh_musicvideolinks()

                    return True

                if not self.open_Worker(WorkerName):
                    return False

                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
                RecordsPercent = UpdateItemsCount / 100
                index = 0
                UpdateItems, Others = self.ItemsSort(self.worker_update_generator, {}, UpdateItems, False, RecordsPercent, ProgressBar)
                RefreshAudio = False
                RefreshVideo = False
                SQLs = self.open_EmbyDBRW(WorkerName, False)

                for KodiDBs, CategoryItems in list(UpdateItems.items()):
                    Continue = True

                    if content_available(CategoryItems):
                        dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                        for Items in CategoryItems:
                            if not Items:
                                continue

                            RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                            ClassObject = None

                            for Item in Items:
                                Item = json.loads(Item)

                                if not MusicVideoLinks and Item['Type'] in ("Audio", "MusicVideo"):
                                    MusicVideoLinks = True

                                if not ClassObject:
                                    ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                                SQLs["emby"].delete_UpdateItem(Item['Id'])
                                index += 1

                                if Item['Id'] in KodiDBMapping:
                                    ClassObject.KodiDBMapping = KodiDBMapping[Item['Id']]

                                if not self.update_Item(int(index / RecordsPercent), index, Item, SQLs, KodiDBs, ProgressBar, True, ClassObject):
                                    self.EmbyServer.API.ProcessProgress[WorkerName] = -1
                                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker update interrupt ]", 0) # LOGDEBUG
                                    del ClassObject
                                    return False

                            del ClassObject

                        dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

                    if not Continue:
                        break

                self.EmbyServer.API.ProcessProgress[WorkerName] = -1

                for Other in Others:
                    Other = json.loads(Other)
                    SQLs["emby"].delete_UpdateItem(Other['Id'])

                SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
                utils.reset_querycache()

                if Others:
                    self.close_Worker(WorkerName, True, True, ProgressBar, SQLs)
                else:
                    self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)

    def worker_update_generator(self, SQLs, UpdateItems, RecordsPercent, ProgressBar):
        Counter = 0

        for LibraryId, UpdateItemsArray in list(UpdateItems.items()):
            for ContentType, UpdateItemsIds in list(UpdateItemsArray.items()):
                if not UpdateItemsIds:
                    continue

                ContentTypeLabel = ContentType

                if ContentType == "unknown":
                    ContentType = ["Person", "Studio", "Genre", "Tag", "Trailer", "BoxSet", "Movie", "Video", "Series", "Season", "Episode", "MusicArtist", "MusicGenre", "MusicVideo", "MusicAlbum", "Audio", "Playlist", "Folder"]
                else:
                    ContentType = [ContentType]

                UpdateItemsIdsTemp = UpdateItemsIds.copy()

                if LibraryId in self.EmbyServer.Views.ViewItems:
                    LibraryName = self.EmbyServer.Views.ViewItems[LibraryId][0]
                else:
                    LibraryName = LibraryId

                ProgressBar.update(int(Counter / RecordsPercent), utils.Translate(33734), f"{LibraryName} / {ContentTypeLabel}")

                for Item in self.EmbyServer.API.get_Items_Ids(UpdateItemsIds, ContentType, False, False, "worker_update", LibraryId, {}, {"Object": self.pause_workers, "Params": ("Startsync_http", SQLs, "", None)}, False, True, True):
                    Counter += 1

                    if Item['Id'] in UpdateItemsIds:
                        UpdateItemsIds.remove(Item['Id'])

                    yield True, Item

                # Remove not detected Items
                for UpdateItemsIdTemp in UpdateItemsIdsTemp:
                    if UpdateItemsIdTemp in UpdateItemsIds:
                        UpdateItemsIds.remove(UpdateItemsIdTemp)
                        yield False, {'Id': UpdateItemsIdTemp}

    def worker_remove(self, IncrementalSync):
        with LockLowPriorityWorkers:
            WorkerName = "worker_remove"

            if not self.wait_DatabaseInit(WorkerName):
                return False

            while True: # Removed items can add additional subitems to be removed
                EmbyDB = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                RemoveItems = EmbyDB.get_RemoveItem()
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                del EmbyDB
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker remove started ] queue size: {len(RemoveItems)}", 0) # LOGDEBUG

                if not RemoveItems:
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker remove empty ]", 0) # LOGDEBUG
                    return True

                if not self.open_Worker(WorkerName):
                    return False

                RefreshAudio = False
                RefreshVideo = False
                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33261))
                RecordsPercent = len(RemoveItems) / 100
                SQLs = self.open_EmbyDBRW(WorkerName, False)
                UpdateItems, Others = self.ItemsSort(self.worker_remove_generator, SQLs, RemoveItems, True, RecordsPercent, ProgressBar)

                if not SQLs['emby']:
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker remove interrupt ] (ItemsSort)", 0) # LOGDEBUG
                    return False

                for KodiDBs, CategoryItems in list(UpdateItems.items()):
                    if content_available(CategoryItems):
                        dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                        for Items in CategoryItems:
                            if not Items:
                                continue

                            RecordsPercent = len(Items) / 100
                            RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)
                            ClassObject = None

                            for index, Item in enumerate(Items, 1):
                                Item = json.loads(Item)

                                if not ClassObject:
                                    ClassObject = self.load_libraryObject(Item['Type'], SQLs)

                                SQLs["emby"].delete_RemoveItem(Item['Id'])

                                if not self.remove_Item(int(index / RecordsPercent), index, Item, SQLs, KodiDBs, ProgressBar, IncrementalSync, ClassObject):
                                    del ClassObject
                                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker remove interrupt ]", 0) # LOGDEBUG
                                    return False

                            del ClassObject

                        dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

                for Other in Others:
                    Other = json.loads(Other)
                    SQLs["emby"].delete_RemoveItem(Other['Id'])

                SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
                utils.reset_querycache()

                if Others:
                    utils.refresh_DynamicNode()
                    self.close_Worker(WorkerName, True, True, ProgressBar, SQLs)
                else:
                    self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar, SQLs)

                xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker remove completed ]", 0) # LOGDEBUG

        return True

    def worker_remove_generator(self, SQLs, RemoveItems, RecordsPercent, ProgressBar):
        for index, RemoveItem in enumerate(RemoveItems, 1):
            if not self.pause_workers("worker_remove_generator", SQLs, ProgressBar, None):
                break

            ProgressBar.update(int(index / RecordsPercent), utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = SQLs["emby"].get_remove_generator_items(RemoveItem[0], RemoveItem[1])

            for FoundRemoveItem in FoundRemoveItems:
                FoundRemoveItem['LibraryId'] = str(RemoveItem[1])
                yield True, FoundRemoveItem

            if not FoundRemoveItems:
                yield False, {'Id': RemoveItem[0]}

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
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library started ] queue size: {len(RemovedLibraries)}", 0) # LOGDEBUG

                if not RemovedLibraries:
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library empty ]", 0) # LOGDEBUG
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
                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed library: {RemovedLibrary[0]} ]", 1) # LOGINFO
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
                    utils.notify_event("library_remove", {"EmbyId": RemovedLibrary[0]}, True)

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
            utils.reset_querycache()

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library completed ]", 0) # LOGDEBUG
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
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library started ] queue size: {len(AddedLibraries)}", 0) # LOGDEBUG

                if not AddedLibraries:
                    xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library empty ]", 0) # LOGDEBUG
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
                MusicVideoLinks = False
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
                    elif AddedLibrary[2] in ("Audio", "MusicVideo"):
                        MusicVideoLinks = True

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

                    self.EmbyServer.API.ProcessProgress[WorkerName] = 0

                    # Add Kodi tag for each library
                    if AddedLibrary[3] == "video" and AddedLibrary[0] != "999999999":
                        TagObject = tag.Tag(self.EmbyServer, SQLs)
                        TagObject.change({"LibraryId": AddedLibrary[0], "Type": "Tag", "Id": f"999999993{AddedLibrary[0]}", "Name": AddedLibrary[1], "Memo": "library"}, False)
                        del TagObject

                    # Add Item
                    ClassObject = self.load_libraryObject(AddedLibrary[2], SQLs)

                    for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(AddedLibrary[0], (AddedLibrary[2],), False, {}, WorkerName, {"Object": self.pause_workers, "Params": (WorkerName, SQLs, ProgressBar, ClassObject)}, True, True), 1):
                        # Add Content
                        Item["LibraryId"] = AddedLibrary[0]
                        self.EmbyServer.API.ProcessProgress[WorkerName] = ItemIndex

                        if not self.update_Item(AddedLibraryProgress, ItemIndex, Item, SQLs, AddedLibrary[3], ProgressBar, False, ClassObject):
                            del ClassObject
                            self.EmbyServer.API.ProcessProgress[WorkerName] = -1
                            xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library interrupt ] (paused)", 0) # LOGDEBUG
                            return

                        # Add UserData
                        UpdateKodiFavorites = AddedLibrary[2] not in ("MusicGenre", "Genre", "Studio", "Tag", "MusicArtist", "Person") # skip favorite updates, they must be refreshed last
                        Continue, _ = self.update_UserData(AddedLibraryProgress, ItemIndex, Item, SQLs, AddedLibrary[3], None, False, ClassObject, UpdateKodiFavorites)

                        if not Continue:
                            del ClassObject
                            self.EmbyServer.API.ProcessProgress[WorkerName] = -1
                            ProgressBar.close()
                            del ProgressBar
                            xbmc.log("EMBY.database.library: --<[ worker library interrupt ] (paused)", 0) # LOGDEBUG
                            return

                    del ClassObject

                    if not SQLs["emby"]:
                        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library interrupt ] (closed database)", 0) # LOGDEBUG-> db can be closed via http busyfunction
                        return

                    SQLs["emby"].add_LibrarySynced(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    SQLs["emby"].remove_LibraryAdd(AddedLibrary[0], AddedLibrary[1], AddedLibrary[2], AddedLibrary[3])
                    self.load_LibrarySynced(SQLs)

                    if VideoDB:
                        SQLs["video"].add_Index()

                    if MusicDB:
                        SQLs["music"].add_Index()

                    dbio.DBCloseRW(AddedLibrary[3], WorkerName, SQLs)
                    utils.notify_event("library_add", {"EmbyId": AddedLibrary[0]}, True)

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

                if utils.LinkMusicVideos and MusicVideoLinks:
                    self.refresh_musicvideolinks()

                self.EmbyServer.Views.update_nodes()
                utils.reset_querycache()
                xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker library completed ]", 0) # LOGDEBUG
        #        utils.sleep(2) # give Kodi time to catch up (otherwise could cause crashes)
        #        xbmc.executebuiltin('ReloadSkin()') # Skin reload broken in Kodi 21

        self.RunJobs(False)

    # Process item operations
    def update_Item(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, ProgressBar, IncrementalSync, ClassObject):
        self.set_recording_type(Item)

        with LockPause:
            Ret = ClassObject.change(Item, IncrementalSync)

        if "Name" in Item:
            ProgressMsg = Item.get('Name', "unknown")
        elif "Path" in Item:
            ProgressMsg = Item['Path']
        else:
            ProgressMsg = "unknown"

        ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", ProgressMsg)

        if Ret and utils.newContent:
            utils.Dialog.notification(heading=f"{utils.Translate(33049)} {Item['Type']}", message=Item.get('Name', "unknown"), icon=utils.icon, time=utils.newContentTime, sound=False)

        if not self.pause_workers("update_Item", SQLs, ProgressBar, ClassObject):
            return False

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, "update_item", SQLs)
            self.close_Worker("update_item", False, False, ProgressBar, SQLs)
            xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: worker exit (shutdown 2) ]", 1) # LOGINFO
            return False

        del Item
        return True

    def update_UserData(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, ProgressBar, IncrementalSync, ClassObject, UpdateFavorite):
        if ProgressBar:
            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))

        Update = ClassObject.userdata(Item, IncrementalSync, UpdateFavorite)

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, "update_UserData", SQLs)
            self.close_Worker("update_UserData", False, False, ProgressBar, SQLs)
            xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: worker exit (shutdown 2) ]", 1) # LOGINFO
            return False, False

        del Item
        return True, Update

    def remove_Item(self, ProgressValue, ItemIndex, Item, SQLs, KodiDBs, ProgressBar, IncrementalSync, ClassObject):
        ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))

        with LockPause:
            ClassObject.remove(Item, IncrementalSync)

        if not self.pause_workers("remove_Item", SQLs, ProgressBar, ClassObject):
            return False

        if utils.SystemShutdown:
            dbio.DBCloseRW(KodiDBs, "remove_Item", SQLs)
            self.close_Worker("remove_Item", False, False, ProgressBar, SQLs)
            xbmc.log(f"EMBY.database.library: [ Emby server {self.EmbyServer.ServerData['ServerId']}: worker exit (shutdown 2) ]", 1) # LOGINFO
            return False

        del Item
        return True

    def pause_workers(self, WorkerName, SQLs, ProgressBar, ClassObject):
        with LockPauseBusy:
            # Check if Kodi db or emby is about to open -> close db, wait, reopen db
            if self.Worker_is_paused(WorkerName):
                Databases = set()

                for SQLKey, SQLDatabase in list(SQLs.items()):
                    if SQLDatabase:
                        if SQLKey == "emby":
                            Databases.add(self.EmbyServer.ServerData['ServerId'])
                        else:
                            Databases.add(SQLKey)

                Databases = ",".join(Databases)
                xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker delay {WorkerName} ] {utils.SyncPause}", 0) # LOGDEBUG
                LockPause.acquire()

                if Databases:
                    dbio.DBCloseRW(Databases, WorkerName, SQLs)

                    if self.LockDBRWOpen.locked():
                        self.LockDBRWOpen.release()

                # Wait on progress updates
                while self.Worker_is_paused(WorkerName):
                    if utils.sleep(1):
                        if ProgressBar:
                            ProgressBar.close()
                            del ProgressBar

                        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker delay {WorkerName} ] shutdown", 0) # LOGDEBUG
                        LockPause.release()
                        return False

                xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: worker delay {WorkerName} ] {utils.SyncPause}", 0) # LOGDEBUG

                if Databases:
                    if not self.LockDBRWOpen.locked():
                        self.LockDBRWOpen.acquire()

                    dbio.DBOpenRW(Databases, WorkerName, SQLs)

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

        return None

    # Run workers in specific order
    def RunJobs(self, IncrementalSync):
        if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
            if self.worker_remove(IncrementalSync):
                if self.worker_update(IncrementalSync):
                    if self.worker_library_remove():
                        self.worker_library_add()
        else:
            xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: RunJobs limited due to server busy", 1) # LOGINFO

            if self.worker_library_remove():
                self.worker_library_add()

        self.worker_userdata(IncrementalSync)

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):
        LibrariesSelected = ()
        LibrariesSelectedIds = ()
        utils.reset_querycache()
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
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: remove library: 999999999 / Person ]", 1) # LOGINFO
                SQLs["emby"].remove_LibrarySynced("999999999")
                SQLs["emby"].add_LibraryRemove("999999999", "Person")

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

                    if ViewData[1] in ('movies', 'tvshows', 'mixed', 'musicvideos'):
                        syncGlobalVideoContent = True
                        break

            for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
                if LibrarySyncedId == "999999999" and LibrarySyncedEmbyType == "Person":
                    syncGlobalVideoContent = False

            if syncGlobalVideoContent:
                SQLs["emby"].add_LibraryAdd("999999999", "shared", "Person", "video") # Person can only be queried globally by Emby server
                xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library: 999999999 ]", 1) # LOGINFO

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
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
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
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Genre", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Tag", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Studio", "video")
                        SQLs["emby"].add_LibraryAdd(LibraryId, library_name, "Video", "video")
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

                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library: {LibraryId} ]", 1) # LOGINFO
                else:
                    xbmc.log(f"EMBY.database.library: ---[ Emby server {self.EmbyServer.ServerData['ServerId']}: added library not found: {LibraryId} ]", 1) # LOGINFO

            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())

        self.close_EmbyDBRW("select_libraries", SQLs)

        if LibraryIdsRemove:
            utils.start_thread(self.worker_library_remove, ())

        if LibraryIdsAdd and not LibraryIdsRemove:
            utils.start_thread(self.worker_library_add, ())

    def refresh_boxsets(self):  # threaded by caller
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_boxsets ]", 0) # LOGDEBUG
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
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
        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_boxsets ]", 0) # LOGDEBUG

    def SyncThemes(self):
        if not utils.check_tvtunes:
            return

        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        LibraryThemeIds = set()
        DownloadAudioThemes = False
        DownloadVideoThemes = False
        Path = os.path.join(utils.DownloadPath, "EMBY-themes", "")
        utils.mkDir(Path)
        Path = os.path.join(Path, self.EmbyServer.ServerData['ServerId'], "")
        utils.mkDir(Path)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"service.tvtunes","enabled":true}}')
        tvtunes = xbmcaddon.Addon(id="service.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', Path)
        xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: TV Tunes custom path is enabled and set", 1) # LOGINFO
        UseAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33762), defaultbutton=11) # defaultbutton=11 = yes

        if UseAudioThemes and not utils.useDirectPaths:
            DownloadAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33758), yeslabel=utils.Translate(33760), nolabel=utils.Translate(33761), defaultbutton=11) # defaultbutton=11 = yes

        UseVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33763), defaultbutton=10) # defaultbutton=10 = no

        if UseVideoThemes and not utils.useDirectPaths:
            DownloadVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33759), yeslabel=utils.Translate(33760), nolabel=utils.Translate(33761), defaultbutton=10) # defaultbutton=10 = no

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33451))

        for LibrarySyncedId, _, LibrarySyncedEmbyType, _ in self.LibrarySynced:
            if LibrarySyncedEmbyType in ('Movie', 'Series'):
                LibraryThemeIds.add(LibrarySyncedId)

        items = {}

        for LibraryThemeId in LibraryThemeIds:
            if UseVideoThemes:
                for item in self.EmbyServer.API.get_Items(LibraryThemeId, ("Movie", "Series"), True, {'HasThemeVideo': "True"}, "", None, True, False):
                    items[item['Id']] = normalize_string(item['Name'])

            if UseAudioThemes:
                for item in self.EmbyServer.API.get_Items(LibraryThemeId, ("Movie", "Series"), True, {'HasThemeSong': "True"}, "", None, True, False):
                    items[item['Id']] = normalize_string(item['Name'])

        Index = 1
        TotalItems = len(items) / 100

        for ItemId, Name in list(items.items()):
            ProgressBar.update(int(Index / TotalItems), utils.Translate(33451), Name)
            NfoPath = os.path.join(Path, Name, "")
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
                        xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Theme: No Path or Size {ThemeItem}", 0) # LOGDEBUG
                        xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Theme: No Path or Size: {ThemeItem['Id']}", 3) # LOGERROR
                        continue

                    isAudio = ThemeItem.get('Type', 'unknown') == 'Audio'
                    isVideo = ThemeItem.get('Type', 'unknown') == 'Video'

                    if isAudio:
                        Filename = f"emby-themes-audio-{self.EmbyServer.ServerData['ServerId']}-{ThemeItem['Id']}-{quote(Name).replace('-', '<_>')}-theme.{ThemeItem.get('Container', 'unknown')}"
                    else:
                        Filename = f"emby-themes-video-{self.EmbyServer.ServerData['ServerId']}-{ThemeItem['Id']}-{quote(Name).replace('-', '<_>')}-theme.{ThemeItem.get('Container', 'unknown')}"

                    MetaDataFile = f"{NfoPath}/metadata-{ThemeItem['Id']}.json"
                    utils.delFile(MetaDataFile)
                    utils.writeFile(MetaDataFile, json.dumps(ThemeItem))

                    if (isAudio and DownloadAudioThemes) or (isVideo and DownloadVideoThemes):
                        if utils.useDirectPaths:
                            ThemeItemPath = ThemeItem['KodiFullPath']
                        else:
                            ThemeItemPath = xbmcvfs.translatePath(f"{NfoPath}{Filename}")

                        if not xbmcvfs.exists(ThemeItemPath):
                            self.EmbyServer.API.download_file(ThemeItem['Id'], "", NfoPath, ThemeItemPath, ThemeItem['Size'], Name, "", "", "", "")
                    else:
                        common.set_streams(ThemeItem)
                        common.set_chapters(ThemeItem, self.EmbyServer.ServerData['ServerId'])
                        common.set_path_filename(ThemeItem, self.EmbyServer.ServerData['ServerId'], None, True)

                        if utils.useDirectPaths:
                            ThemeItemPath = ThemeItem['KodiFullPath']
                        else:
                            ThemeItemPath = f"{ThemeItem['KodiPath']}{Filename}"

                    XMLData += f"    <file>{utils.encode_XML(ThemeItemPath)}</file>\n".encode("utf-8")

                XMLData += b'</tvtunes>'
                utils.delFile(NfoFile)
                utils.writeFile(NfoFile, XMLData)

            Index += 1

        ProgressBar.close()
        del ProgressBar
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=utils.displayMessage, sound=False)

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

        for ChannelSorted in ChannelsSorted:
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
        utils.writeFile(EPGFile, epg)

        if utils.LiveTVEnabled and utils.SyncLiveTvOnEvents and ChannelSync:
            self.SyncLiveTV()

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: load EPG ]", 1) # LOGINFO

    # Add item_id to userdata queue
    def userdata(self, Items, IncrementalSync, ProcessUpdates=True):  # threaded by caller -> websocket via monitor
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: userdata ]", 0) # LOGDEBUG

        if Items:
            SQLs = self.open_EmbyDBRW("userdata", True)

            for Item in Items:
                SQLs["emby"].add_Userdata(Item[0], Item[1], Item[2], Item[3], Item[4], Item[5], Item[6], Item[7], Item[8])

            self.close_EmbyDBRW("userdata", SQLs)

            if ProcessUpdates:
                self.worker_userdata(IncrementalSync)

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: userdata ]", 0) # LOGDEBUG

    # Add item_id to updated queue
    def updated(self, Items, IncrementalSync, ProcessUpdates=True):  # threaded by caller
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: updated ]", 0) # LOGDEBUG

        if Items:
            SQLs = self.open_EmbyDBRW("updated", True)

            for Item in Items:
                SQLs["emby"].add_UpdateItem(Item[0], Item[1], Item[2])

            self.close_EmbyDBRW("updated", SQLs)

            if ProcessUpdates:
                if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
                    self.worker_update(IncrementalSync)
                else:
                    xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: updated trigger skipped due to server busy", 1) # LOGINFO

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: updated ]", 0) # LOGDEBUG

    # Add item_id to removed queue
    def removed(self, Ids, IncrementalSync, ProcessUpdates=True):  # threaded by caller
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed ]", 0) # LOGDEBUG

        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)

            for Id in Ids:
                SQLs["emby"].add_RemoveItem(Id, "")

            self.close_EmbyDBRW("removed", SQLs)

            if ProcessUpdates:
                if not utils.SyncPause.get(f"server_busy_{self.EmbyServer.ServerData['ServerId']}", False):
                    self.worker_remove(IncrementalSync)
                else:
                    xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: removed trigger skipped due to server busy", 1) # LOGINFO

        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: removed ]", 0) # LOGDEBUG

    # Add item_id to removed queue
    def removed_deduplicate(self, Ids):  # threaded by caller
        if Ids:
            SQLs = self.open_EmbyDBRW("removed", True)

            for Id in Ids:
                SQLs["emby"].add_RemoveItem(Id[1], Id[0])

            self.close_EmbyDBRW("removed", SQLs)
            self.worker_remove(True)

    def Worker_is_paused(self, WorkerName):
        for Key, Busy in list(utils.SyncPause.items()):
            if Busy:
                if WorkerName in ("worker_remove", "worker_library_remove") and Key.startswith("server_busy_"): # Continue removes, even emby server is busy
                    continue

                # Doublecheck scan is in progress, sometimes Kodi simply does not fire callbacks
                if Key == "kodi_rw":
                    IsScanningVideo, IsScanningMusic = utils.get_scans()

                    if not IsScanningVideo and not IsScanningMusic:
                        xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Worker_is_paused overwrite Kodi scans: {WorkerName} / {utils.SyncPause}", 1) # LOGINFO
                        continue
                elif Key.startswith("server_starting") and not Key.endswith(self.EmbyServer.ServerData['ServerId']):
                    continue
                elif Key.startswith("server_busy") and not Key.endswith(self.EmbyServer.ServerData['ServerId']):
                    continue
                elif Key.startswith("database_init") and not Key.endswith(self.EmbyServer.ServerData['ServerId']):
                    continue
                elif Key.startswith("server_reconnecting") and not Key.endswith(self.EmbyServer.ServerData['ServerId']):
                    continue

                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Worker_is_paused: {WorkerName} / {utils.SyncPause}", 1) # LOGINFO
                return True

        return False

    def refresh_musicvideolinks(self):
        xbmc.log(f"EMBY.database.library: -->[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_musicvideolinks ]", 0) # LOGDEBUG
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33749), utils.Translate(33363))
        videodb = dbio.DBOpenRO("video", "MusicvideoLinks")
        MusicVideoDatas = videodb.get_musicvideos_KodiId_MusicBrainzId_Artist_Title()
        dbio.DBCloseRO("video", "MusicvideoLinks")
        TotalItems = len(MusicVideoDatas) / 100
        SQLs = {}
        dbio.DBOpenRW("music", "MusicvideoLinks", SQLs)

        # Clear old links
        SQLs["music"].del_song_musicvideo()

        # Add new musicvideo links
        for Index, MusicVideoData in enumerate(MusicVideoDatas, 1): # MusicBrainzId, Path, Title, Artist
            if utils.SystemShutdown:
                break

            SQLs["music"].update_song_musicvideo(MusicVideoData[0], MusicVideoData[1], MusicVideoData[2], MusicVideoData[3])
            ProgressBar.update(int(Index / TotalItems), utils.Translate(33363), f"{MusicVideoData[3]} - {MusicVideoData[2]}")

        dbio.DBCloseRW("music", "MusicvideoLinks", SQLs)
        ProgressBar.close()
        del ProgressBar
        xbmc.log(f"EMBY.database.library: --<[ Emby server {self.EmbyServer.ServerData['ServerId']}: refresh_musicvideolinks ]", 0) # LOGDEBUG

    def ItemsSort(self, GeneratorFunction, SQLs, Items, Reverse, RecordsPercent, ProgressBar):
        SortItems = {'Movie': set(), 'Video': set(), 'BoxSet': set(), 'MusicVideo': set(), 'Series': set(), 'Episode': set(), 'MusicAlbum': set(), 'MusicArtist': set(), 'AlbumArtist': set(), 'Season': set(), 'Folder': set(), 'Audio': set(), 'Genre': set(), 'MusicGenre': set(), 'Tag': set(), 'Person': set(), 'Studio': set(), 'Playlist': set()}
        Others = set()

        for Valid, Item in GeneratorFunction(SQLs, Items, RecordsPercent, ProgressBar):
            if not Item:
                continue

            if Valid:
                self.set_recording_type(Item)

                if Item['Type'] in SortItems:
                    SortItems[Item['Type']].add(json.dumps(Item)) # Dict is not hashable (not possible adding "dict" to "set") -> convert to json string necessary
                else: # e.g. PlaceHolder
                    xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Unsupported item type {Item['Type']}", 1) # LOGINFO
                    Others.add(json.dumps(Item))
            else:
                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Unknown {Item}", 1) # LOGINFO
                Others.add(json.dumps(Item))
                continue

        if Reverse: # on remove, reverse sort order
            return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['BoxSet'], SortItems['Video'], SortItems['Movie'], SortItems['Episode'], SortItems['Season'], SortItems['Series']], "music,video": [SortItems['MusicGenre'], SortItems['Audio'], SortItems['MusicVideo'], SortItems['MusicAlbum'], SortItems['MusicArtist'], SortItems['Playlist']], "none": [SortItems['Folder']]}, Others

        return {"video": [SortItems['Person'], SortItems['Studio'], SortItems['Genre'], SortItems['Tag'], SortItems['Series'], SortItems['Season'], SortItems['Episode'], SortItems['Movie'], SortItems['Video'], SortItems['BoxSet']], "music,video": [SortItems['MusicGenre'], SortItems['MusicArtist'], SortItems['MusicAlbum'], SortItems['MusicVideo'], SortItems['Audio'], SortItems['Playlist']], "none": [SortItems['Folder']]}, Others

    def set_recording_type(self, Item):
        if 'Type' in Item:
            if Item['Type'] == "Recording":
                xbmc.log(f"EMBY.database.library: Emby server {self.EmbyServer.ServerData['ServerId']}: Recording detected", 0) # LOGDEBUG

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

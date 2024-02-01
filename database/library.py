import json
import unicodedata
import xbmc
import xbmcaddon
import xbmcgui
from core import movies, videos, musicvideo, folder, boxsets, genre, musicgenre, musicartist, musicalbum, audio, tag, person, studio, playlist, series, season, episode, common
from helper import utils, pluginmenu
from . import dbio

WorkerInProgress = False


class Library:
    def __init__(self, EmbyServer):
        xbmc.log("EMBY.database.library: -->[ library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.Whitelist = [] # LibraryId, LibraryName, MediaType
        self.WhitelistUnique = {} # LibraryId, LibraryName
        self.LastSyncTime = ""
        self.ContentObject = None
        self.EmbyDBOpen = False
        self.SettingsLoaded = False
        self.KodiStartSyncRunning = False

    def open_Worker(self, WorkerName):
        if WorkerName != "worker_userdata":
            while utils.SyncPause.get(f"database_init_{self.EmbyServer.ServerData['ServerId']}", False):
                xbmc.log(f"EMBY.database.library: [ worker {WorkerName} wait for database init ]", 1) # LOGINFO

                if utils.sleep(1):
                    return False

        if utils.SystemShutdown:
            return False

        if Worker_is_paused(WorkerName):
            xbmc.log(f"EMBY.database.library: [ worker {WorkerName} sync paused ]", 1) # LOGINFO
            return False

        if WorkerInProgress:
            xbmc.log(f"EMBY.database.library: [ worker {WorkerName} in progress ]", 1) # LOGINFO
            return False

        globals()["WorkerInProgress"] = True
        return True

    def close_Worker(self, WorkerName, RefreshVideo, RefreshAudio, ProgressBar):
        self.close_EmbyDBRW(WorkerName)
        utils.SyncPause['kodi_rw'] = False

        if RefreshVideo:
            utils.refresh_widgets(True)

        if RefreshAudio:
            utils.refresh_widgets(False)

        ProgressBar.close()
        del ProgressBar
        globals()["WorkerInProgress"] = False

    def open_EmbyDBRW(self, WorkerName):
        # if worker in progress, interrupt workers database ops (worker has lower priority) compared to all other Emby database (rw) ops
        if self.EmbyDBOpen:
            if WorkerInProgress:
                utils.SyncPause['priority'] = True

        # wait for DB close
        while self.EmbyDBOpen:
            xbmc.log(f"EMBY.database.library: open_EmbyDBRW waiting: {WorkerName}", 1) # LOGINFO
            utils.sleep(1)

        self.EmbyDBOpen = True
        return dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], WorkerName, {})

    def close_EmbyDBRW(self, WorkerName):
        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName, {})
        self.EmbyDBOpen = False
        utils.SyncPause['priority'] = False

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        SQLs = self.open_EmbyDBRW("set_syncdate")
        SQLs["emby"].update_LastIncrementalSync(TimestampUTC)
        self.close_EmbyDBRW("set_syncdate")
        self.LastSyncTime = TimestampUTC
        utils.set_syncdate(self.LastSyncTime)

    def load_WhiteList(self, SQLs):
        self.WhitelistUnique = {}
        self.Whitelist = SQLs["emby"].get_Whitelist()

        for LibraryIdWhitelist, LibraryNameWhitelist, _, KodiDBWhitelist, _ in self.Whitelist:
            if LibraryIdWhitelist not in self.WhitelistUnique:
                self.WhitelistUnique[LibraryIdWhitelist] = [LibraryNameWhitelist, KodiDBWhitelist]

    def load_settings(self):
        xbmc.log(f"EMBY.database.library: {self.EmbyServer.ServerData['ServerId']} --->[ load settings ]", 1) # LOGINFO
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = True

        # Load essential data and prefetching Media tags
        SQLs = self.open_EmbyDBRW("load_settings")

        if SQLs["emby"].init_EmbyDB():
            self.load_WhiteList(SQLs)
        else:
            utils.set_settings('MinimumSetup', "INVALID DATABASE")
            self.close_EmbyDBRW("load_settings")
            utils.restart_kodi()
            xbmc.log(f"EMBY.database.library: load settings: database corrupt: {self.EmbyServer.ServerData['ServerId']}  ---<[ load settings ]", 3) # LOGERROR
            return

        self.LastSyncTime = SQLs["emby"].get_LastIncrementalSync()
        self.close_EmbyDBRW("load_settings")

        # Init database
        SQLs = dbio.DBOpenRW("video", "load_settings", {})
        SQLs["video"].add_Index()
        SQLs["video"].get_add_path(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/", None, None)
        dbio.DBCloseRW("video", "load_settings", {})
        SQLs = dbio.DBOpenRW("music", "load_settings", {})
        SQLs["music"].add_Index()
        SQLs["music"].disable_rescan(utils.currenttime_kodi_format())
        dbio.DBCloseRW("music", "load_settings", {})
        SQLs = dbio.DBOpenRW("texture", "load_settings", {})
        SQLs["texture"].add_Index()
        dbio.DBCloseRW("texture", "load_settings", {})
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = False
        self.SettingsLoaded = True
        xbmc.log(f"EMBY.database.library: {self.EmbyServer.ServerData['ServerId']} ---<[ load settings ]", 1) # LOGINFO

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        xbmc.log("EMBY.database.library: THREAD: --->[ retrieve changes ]", 0) # LOGDEBUG
        self.KodiStartSyncRunning = True
        NewSyncData = utils.currenttime()
        UpdateSyncData = False

        while not self.SettingsLoaded:
            if utils.sleep(1):
                self.KodiStartSyncRunning = False
                xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 1", 0) # LOGDEBUG
                return

        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        # Upsync downloaded content progress
        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "KodiStartSync")
        DownlodedItems = embydb.get_DownloadItem()
        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "KodiStartSync")
        videodb = dbio.DBOpenRO("video", "KodiStartSync")

        for DownlodedItem in DownlodedItems:
            utils.ItemSkipUpdate += [int(DownlodedItem[0])]
            Found, timeInSeconds, playCount, lastPlayed, = videodb.get_Progress(DownlodedItem[2])

            if Found:
                self.EmbyServer.API.set_progress_upsync(DownlodedItem[0], int(timeInSeconds * 10000000), playCount, utils.convert_to_gmt(lastPlayed))  # Id, PlaybackPositionTicks, PlayCount, LastPlayedDate

        dbio.DBCloseRO("video", "KodiStartSync")
        self.RunJobs()
        UpdateData = []

        if self.LastSyncTime:
            xbmc.log(f"EMBY.database.library: Retrieve changes, last synced: {self.LastSyncTime}", 1) # LOGINFO
            ProgressBar = xbmcgui.DialogProgressBG()
            ProgressBar.create(utils.Translate(33199), utils.Translate(33445))
            xbmc.log("EMBY.database.library: -->[ Kodi companion ]", 1) # LOGINFO
            result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

            if 'ItemsRemoved' in result and result['ItemsRemoved']:
                UpdateSyncData = True
                self.removed(result['ItemsRemoved'])

            xbmc.log("EMBY.database.library: --<[ Kodi companion ]", 1) # LOGINFO
            ProgressBarTotal = len(self.Whitelist) / 100
            ProgressBarIndex = 0

            for LibraryIdWhitelist, LibraryNameWhitelist, EmbyTypeWhitelist, _, _ in self.Whitelist:
                xbmc.log(f"EMBY.database.library: [ retrieve changes ] {LibraryNameWhitelist}", 1) # LOGINFO
                LibraryName = ""
                ProgressBarIndex += 1

                if LibraryIdWhitelist in self.EmbyServer.Views.ViewItems:
                    LibraryName = self.EmbyServer.Views.ViewItems[LibraryIdWhitelist][0]
                    ProgressBar.update(int(ProgressBarIndex / ProgressBarTotal), utils.Translate(33445), LibraryName)

                if not LibraryName and LibraryNameWhitelist != "shared":
                    xbmc.log(f"EMBY.database.library: [ KodiStartSync remove library {LibraryIdWhitelist} ]", 1) # LOGINFO
                    continue

                ItemIndex = 0
                UpdateDataTemp = 10000 * [()] # pre allocate memory

                for Item in self.EmbyServer.API.get_Items(LibraryIdWhitelist, [EmbyTypeWhitelist], True, True, {'MinDateLastSavedForUser': self.LastSyncTime}):
                    if utils.SystemShutdown:
                        ProgressBar.close()
                        del ProgressBar
                        self.KodiStartSyncRunning = False
                        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 2", 0) # LOGDEBUG
                        return

                    if ItemIndex >= 10000:
                        UpdateData += UpdateDataTemp
                        UpdateDataTemp = 10000 * [()] # pre allocate memory
                        ItemIndex = 0

                    UpdateDataTemp[ItemIndex] = (Item['Id'], Item['Type'], LibraryIdWhitelist)
                    ItemIndex += 1

                UpdateData += UpdateDataTemp

            ProgressBar.close()
            del ProgressBar

        # Run jobs
        if UpdateData:
            UpdateData = list(dict.fromkeys(UpdateData)) # filter doubles

            if () in UpdateData:  # Remove empty
                UpdateData.remove(())

            if UpdateData:
                UpdateSyncData = True
                self.updated(UpdateData)

        # Update sync update timestamp
        if UpdateSyncData:
            xbmc.log("EMBY.database.library: Start sync, updates found", 1) # LOGINFO
            self.set_syncdate(NewSyncData)
        else:
            xbmc.log("EMBY.database.library: Start sync, widget refresh", xbmc.LOGINFO) # reload artwork/images
            utils.refresh_widgets(True)
            utils.refresh_widgets(False)

        self.SyncLiveTVEPG()
        self.KodiStartSyncRunning = False
        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ]", 0) # LOGDEBUG

    def worker_userdata(self):
        WorkerName = "worker_userdata"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            SQLs = {"emby": dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)}
            UserDataItems = SQLs["emby"].get_Userdata()
            xbmc.log(f"EMBY.database.library: -->[ worker userdata started ] queue size: {len(UserDataItems)}", 1) # LOGINFO

            if not UserDataItems:
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                globals()["WorkerInProgress"] = False
                return ContinueJobs
        else:
            return False

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
        RecordsPercent = len(UserDataItems) / 100
        UpdateItems, Others = ItemsSort(self.worker_userdata_generator, SQLs, UserDataItems, False, RecordsPercent, ProgressBar)
        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        SQLs = self.open_EmbyDBRW(WorkerName)
        RefreshAudio = False
        RefreshVideo = False

        for Other in Others:
            SQLs["emby"].delete_Userdata(json.loads(Other))

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            if content_available(CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                SQLs = dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                for Items in CategoryItems:
                    self.ContentObject = None
                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                    for index, Item in enumerate(Items, 1):
                        Item = json.loads(Item)
                        SQLs["emby"].delete_Userdata(Item["UpdateItem"])
                        Continue, SQLs = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar)

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker userdata interrupt ]", 1) # LOGINFO
                            return False

                SQLs = dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar)
        xbmc.log("EMBY.database.library: --<[ worker userdata completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_userdata_generator(self, SQLs, UserDataItems, RecordsPercent, ProgressBar):
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
                yield False, str(UserDataItem)
                xbmc.log(f"EMBY.database.library: Skip not synced item: {UserDataItem}", 1) # LOGINFO

    def worker_update(self):
        WorkerName = "worker_update"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            UpdateItems, UpdateItemsCount = embydb.get_UpdateItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log(f"EMBY.database.library: -->[ worker update started ] queue size: {UpdateItemsCount}", 1) # LOGINFO

            if not UpdateItemsCount:
                globals()["WorkerInProgress"] = False
                return ContinueJobs
        else:
            return False

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33178))
        RecordsPercent = UpdateItemsCount / 100
        index = 0
        embydb = None
        UpdateItems, Others = ItemsSort(self.worker_update_generator, embydb, UpdateItems, False, RecordsPercent, ProgressBar)
        RefreshAudio = False
        RefreshVideo = False
        SQLs = self.open_EmbyDBRW(WorkerName)

        for Other in Others:
            SQLs["emby"].delete_UpdateItem(json.loads(Other)['Id'])

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            Continue = True

            if content_available(CategoryItems):
                SQLs = dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                for Items in CategoryItems:
                    self.ContentObject = None
                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                    for Item in Items:
                        Item = json.loads(Item)
                        SQLs["emby"].delete_UpdateItem(Item['Id'])
                        Continue, SQLs = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar)
                        index += 1

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker update interrupt ]", 1) # LOGINFO
                            return False

                SQLs = dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

            if not Continue:
                break

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar)
        xbmc.log("EMBY.database.library: --<[ worker update completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_update_generator(self, _SQLs, UpdateItems, _RecordsPercent, _):
        for LibraryId, UpdateItemsArray in list(UpdateItems.items()):

            for ContentType, UpdateItemsIds in list(UpdateItemsArray.items()):
                if ContentType == "unknown":
                    ContentType = ["Folder", "Episode", "Movie", "Trailer", "MusicVideo", "BoxSet", "MusicAlbum", "MusicArtist", "Season", "Series", "Audio", "Video", "Genre", "MusicGenre", "Tag", "Person", "Studio"]
                else:
                    ContentType = [ContentType]

                UpdateItemsIdsTemp = UpdateItemsIds.copy()
                self.EmbyServer.API.ProcessProgress["worker_update"] = 0

                for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items_Ids(UpdateItemsIds, ContentType, False, False, "worker_update", LibraryId), 1):
                    self.EmbyServer.API.ProcessProgress["worker_update"] = ItemIndex

                    if Item['Id'] in UpdateItemsIds:
                        UpdateItemsIds.remove(Item['Id'])

                    yield True, Item

                # Remove not detected Items
                for UpdateItemsIdTemp in UpdateItemsIdsTemp:
                    if UpdateItemsIdTemp in UpdateItemsIds:
                        UpdateItemsIds.remove(UpdateItemsIdTemp)
                        yield False, {'Id': UpdateItemsIdTemp}

    def worker_remove(self):
        WorkerName = "worker_remove"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            RemoveItems = embydb.get_RemoveItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log(f"EMBY.database.library: -->[ worker remove started ] queue size: {len(RemoveItems)}", 1) # LOGINFO

            if not RemoveItems:
                globals()["WorkerInProgress"] = False
                return ContinueJobs
        else:
            return False

        RefreshAudio = False
        RefreshVideo = False
        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33261))
        RecordsPercent = len(RemoveItems) / 100
        SQLs = self.open_EmbyDBRW(WorkerName)
        UpdateItems, Others = ItemsSort(self.worker_remove_generator, SQLs, RemoveItems, True, RecordsPercent, ProgressBar)

        for KodiDBs, CategoryItems in list(UpdateItems.items()):
            if content_available(CategoryItems):
                SQLs = dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)

                for Items in CategoryItems:
                    self.ContentObject = None
                    RecordsPercent = len(Items) / 100
                    RefreshVideo, RefreshAudio = get_content_database(KodiDBs, Items, RefreshVideo, RefreshAudio)

                    for index, Item in enumerate(Items, 1):
                        Item = json.loads(Item)
                        SQLs["emby"].delete_RemoveItem(Item['Id'])
                        Continue, SQLs = self.ItemOps(int(index / RecordsPercent), index, Item, SQLs, WorkerName, KodiDBs, ProgressBar)

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker remove interrupt ]", 1) # LOGINFO
                            return False

                SQLs = dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)

        for Other in Others:
            Other = json.loads(Other)

            if Other["Type"] == "library":
                OtherId = str(Other["Id"])

                if OtherId in self.WhitelistUnique:
                    LibraryName, _ = self.WhitelistUnique[OtherId]
                    SQLs = dbio.DBOpenRW("video", WorkerName, SQLs)
                    SQLs["video"].delete_tag(LibraryName)
                    SQLs["video"].delete_path(f"{utils.AddonModePath}tvshows/{self.EmbyServer.ServerData['ServerId']}/{OtherId}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}movies/{self.EmbyServer.ServerData['ServerId']}/{OtherId}/")
                    SQLs["video"].delete_path(f"{utils.AddonModePath}musicvideos/{self.EmbyServer.ServerData['ServerId']}/{OtherId}/")
                    SQLs = dbio.DBCloseRW("video", WorkerName, SQLs)
                    SQLs = dbio.DBOpenRW("music", WorkerName, SQLs)
                    SQLs["music"].delete_path(f"{utils.AddonModePath}audio/{self.EmbyServer.ServerData['ServerId']}/{OtherId}/")
                    SQLs = dbio.DBCloseRW("music", WorkerName, SQLs)
                    SQLs["emby"].remove_Whitelist(OtherId)
                    self.load_WhiteList(SQLs)
                    self.EmbyServer.Views.delete_playlist_by_id(OtherId)
                    self.EmbyServer.Views.delete_node_by_id(OtherId)
                    xbmc.log(f"EMBY.database.library: removed library: {Other['Id']}", 1) # LOGINFO
                    self.EmbyServer.Views.update_nodes()

                SQLs["emby"].delete_RemoveItem("library")

        SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName, RefreshVideo, RefreshAudio, ProgressBar)
        xbmc.log("EMBY.database.library: --<[ worker remove completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_remove_generator(self, SQLs, RemoveItems, RecordsPercent, ProgressBar):
        for index, RemoveItem in enumerate(RemoveItems, 1):
            if RemoveItem[0] == "library":
                yield False, {'Id': RemoveItem[1], 'Type': "library"}
                continue

            ProgressBar.update(int(index / RecordsPercent), utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = SQLs["emby"].get_remove_generator_items(RemoveItem[0], RemoveItem[1])
            SQLs["emby"].delete_RemoveItem(RemoveItem[0])

            for EmbyId, KodiItemId, KodiFileId, EmbyType, EmbyPresentationKey in FoundRemoveItems:
                yield True, {'Id': EmbyId, 'Type': EmbyType, 'LibraryId': RemoveItem[1], 'KodiItemId': KodiItemId, 'KodiFileId': KodiFileId, "PresentationUniqueKey": EmbyPresentationKey}

    def worker_library(self):
        WorkerName = "worker_library"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            SyncItems = embydb.get_PendingSync()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log(f"EMBY.database.library: -->[ worker library started ] queue size: {len(SyncItems)}", 1) # LOGINFO

            if not SyncItems:
                globals()["WorkerInProgress"] = False
                xbmc.log("EMBY.database.library: --<[ worker library empty ]", 1) # LOGINFO
                return
        else:
            return

        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33238))
        newContent = utils.newContent
        utils.newContent = False  # Disable new content notification on init sync
        SQLs = self.open_EmbyDBRW(WorkerName)
        SQLs["emby"].delete_Index()
        SyncItemPercent = len(SyncItems) / 100

        for SyncItemIndex, SyncItem in enumerate(SyncItems):
            LibraryId = SyncItem[0]
            LibraryName = SyncItem[1]
            EmbyType = SyncItem[2]
            KodiDB = SyncItem[3]
            KodiDBs = SyncItem[4]
            SyncItemProgress = int(SyncItemIndex / SyncItemPercent)
            ProgressBar.update(SyncItemProgress, f"{utils.Translate(33238)}", SyncItem[1])
            SQLs["emby"].add_Whitelist(LibraryId, LibraryName, EmbyType, KodiDB, KodiDBs)
            self.load_WhiteList(SQLs)
            SQLs = dbio.DBOpenRW(KodiDBs, WorkerName, SQLs)
            self.ContentObject = None
            self.EmbyServer.API.ProcessProgress["worker_library"] = 0

            # Add Kodi tag for each library
            if SyncItem[3] == "video" and LibraryId != "999999999":
                TagObject = tag.Tag(self.EmbyServer, SQLs)
                TagObject.change({"LibraryId": LibraryId, "Type": "Tag", "Id": f"999999993{LibraryId}", "Name": LibraryName, "Memo": "library"})
                del TagObject

            # Sync Content
            for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(LibraryId, [EmbyType], False, True, {}, "worker_library"), 1):
                Item["LibraryId"] = LibraryId
                Continue, SQLs = self.ItemOps(SyncItemProgress, ItemIndex, Item, SQLs, WorkerName, KodiDBs, ProgressBar)
                self.EmbyServer.API.ProcessProgress["worker_library"] = ItemIndex

                if not Continue:
                    self.EmbyServer.API.ProcessProgress["worker_library"] = -1
                    xbmc.log("EMBY.database.library: --<[ worker library interrupt ]", 1) # LOGINFO
                    return

            SQLs = dbio.DBCloseRW(KodiDBs, WorkerName, SQLs)
            SQLs["emby"].remove_PendingSync(LibraryId, LibraryName, EmbyType, KodiDB)

        SQLs["emby"].add_Index()
        utils.newContent = newContent
        self.EmbyServer.Views.update_nodes()
        pluginmenu.reset_querycache(None)
        self.close_Worker(WorkerName, True, True, ProgressBar)
#        utils.sleep(2) # give Kodi time to catch up (otherwise could cause crashes)
#        xbmc.executebuiltin('ReloadSkin()')



        xbmc.log("EMBY.database.library: --<[ worker library completed ]", 1) # LOGINFO
        self.RunJobs()

    def ItemOps(self, ProgressValue, ItemIndex, Item, SQLs, WorkerName, KodiDBs, ProgressBar):
        if not self.ContentObject:
            self.load_libraryObject(Item['Type'], SQLs)

        if WorkerName in ("worker_library", "worker_update"):
            Ret = self.ContentObject.change(Item)

            if "Name" in Item:
                ProgressMsg = Item.get('Name', "unknown")
            elif "Path" in Item:
                ProgressMsg = Item['Path']
            else:
                ProgressMsg = "unknown"

            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", ProgressMsg)

            if Ret and utils.newContent:
                MsgTime = int(utils.newContentTime) * 1000
                utils.Dialog.notification(heading=f"{utils.Translate(33049)} {Item['Type']}", message=Item.get('Name', "unknown"), icon=utils.icon, time=MsgTime, sound=False)

        elif WorkerName == "worker_remove":
            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))
            self.ContentObject.remove(Item)
        elif WorkerName == "worker_userdata":
            ProgressBar.update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))
            self.ContentObject.userdata(Item)

        # Check if Kodi db or emby is about to open -> close db, wait, reopen db
        if Worker_is_paused(WorkerName):
            xbmc.log(f"EMBY.database.library: -->[ worker delay {utils.SyncPause}]", 1) # LOGINFO
            dbio.DBCloseRW(f"{self.EmbyServer.ServerData['ServerId']},{KodiDBs}", WorkerName, {})
            self.EmbyDBOpen = False

            while Worker_is_paused(WorkerName):
                if utils.sleep(1):
                    ProgressBar.close()
                    del ProgressBar
                    xbmc.log("EMBY.database.library: [ worker exit (shutdown) ]", 1) # LOGINFO
                    return False, {}

            self.EmbyDBOpen = True
            xbmc.log(f"EMBY.database.library: --<[ worker delay {utils.SyncPause}]", 1) # LOGINFO
            SQLs = dbio.DBOpenRW(f"{self.EmbyServer.ServerData['ServerId']},{KodiDBs}", WorkerName, {})
            self.load_libraryObject(Item['Type'], SQLs)

        if utils.SystemShutdown:
            dbio.DBCloseRW(f"{self.EmbyServer.ServerData['ServerId']},{KodiDBs}", WorkerName, {})
            self.EmbyDBOpen = False
            xbmc.log("EMBY.database.library: [ worker exit ]", 1) # LOGINFO
            return False, {}

        return True, SQLs

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
    def RunJobs(self):
        if self.worker_remove():
            if self.worker_update():
                if self.worker_userdata():
                    self.worker_library()

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):  # threaded by caller
        LibrariesSelected = ()
        pluginmenu.reset_querycache(None)

        if mode in ('RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            for WhitelistLibraryId, WhitelistLibraryData in list(self.WhitelistUnique.items()):

                if WhitelistLibraryData[0] != "shared":
                    LibrariesSelected += ({'Id': WhitelistLibraryId, 'Name': WhitelistLibraryData[0]},)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()

            for WhitelistLibraryId in self.WhitelistUnique:
                if WhitelistLibraryId in AvailableLibs:
                    del AvailableLibs[WhitelistLibraryId]

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ("movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos", "playlists"):
                    LibrariesSelected += ({'Id': AvailableLibId, 'Name': AvailableLib[0]},)

        choices = [x['Name'] for x in LibrariesSelected]
        choices.insert(0, utils.Translate(33121))

        if mode == 'RepairLibrarySelection':
            Text = utils.Translate(33432)
        elif mode == 'RemoveLibrarySelection':
            Text = utils.Translate(33434)
        elif mode == 'UpdateLibrarySelection':
            Text = utils.Translate(33433)
        elif mode == 'AddLibrarySelection':
            Text = utils.Translate(33120)
        else:
            return

        selection = utils.Dialog.multiselect(Text, choices)

        if not selection:
            return

        # "All" selected
        if 0 in selection:
            selection = list(range(1, len(LibrariesSelected) + 1))

        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        LibraryIdsRemove = ()
        LibraryIdsAdd = ()

        if mode in ('AddLibrarySelection', 'UpdateLibrarySelection'):
            for x in selection:
                LibraryIdsAdd += (LibrariesSelected[x - 1]['Id'],)
        elif mode == 'RepairLibrarySelection':
            for x in selection:
                LibraryIdsRemove += (LibrariesSelected[x - 1]['Id'],)
                LibraryIdsAdd += (LibrariesSelected[x - 1]['Id'],)
        elif mode == 'RemoveLibrarySelection':
            for x in selection:
                LibraryIdsRemove += (LibrariesSelected[x - 1]['Id'],)

        if LibraryIdsRemove or LibraryIdsAdd:
            GenreUpdate = False
            StudioUpdate = False
            TagUpdate = False
            MusicGenreUpdate = False
            PersonUpdate = False
            SQLs = self.open_EmbyDBRW("select_libraries")

            if LibraryIdsRemove:
                # detect shared content type
                removeGlobalVideoContent = True

                for LibraryIdWhitelist, _, LibraryEmbyType, _, _ in self.Whitelist:
                    if LibraryEmbyType in ('Movie', 'Series', 'Season', 'Episode', 'Playlist') and LibraryIdWhitelist not in LibraryIdsRemove:
                        removeGlobalVideoContent = False

                # Remove libraries
                RecordsPercent = len(LibraryIdsRemove) / 100
                ProgressBar = xbmcgui.DialogProgressBG()
                ProgressBar.create(utils.Translate(33199), utils.Translate(33184))

                for Index, LibraryId in enumerate(LibraryIdsRemove):
                    ProgressBar.update(int(Index / RecordsPercent), utils.Translate(33184), str(LibraryId))
                    SQLs["emby"].remove_library_items(LibraryId)
                    SQLs["emby"].add_RemoveItem("library", LibraryId)
                    xbmc.log(f"EMBY.database.library: ---[ removed library: {LibraryId} ]", 1) # LOGINFO

                # global libraries must be removed last
                if removeGlobalVideoContent:
                    SQLs["emby"].remove_library_items_person()
                    SQLs["emby"].add_RemoveItem("library", "999999999")
                    xbmc.log("EMBY.database.library: ---[ removed library: 999999999 ]", 1) # LOGINFO

                ProgressBar.close()
                del ProgressBar

            if LibraryIdsAdd:
                # detect shared content type
                syncGlobalVideoContent = False

                for LibraryId in LibraryIdsAdd:
                    if LibraryId in self.EmbyServer.Views.ViewItems:
                        ViewData = self.EmbyServer.Views.ViewItems[LibraryId]

                        if ViewData[1] in ('movies', 'tvshows', 'mixed'):
                            syncGlobalVideoContent = True
                            break

                for LibraryIdWhitelist, _, EmbyTypeWhitelist, _, _ in self.Whitelist:
                    if LibraryIdWhitelist == "999999999" and EmbyTypeWhitelist == "Person":
                        syncGlobalVideoContent = False

                # Sync libraries
                for LibraryId in LibraryIdsAdd:
                    if LibraryId in self.EmbyServer.Views.ViewItems:
                        ViewData = self.EmbyServer.Views.ViewItems[LibraryId]
                        library_type = ViewData[1]
                        library_name = ViewData[0]

                        # global libraries must be scyned first
                        if syncGlobalVideoContent:
                            SQLs["emby"].add_PendingSync("999999999", "shared", "Person", "video", "video") # Person can only be queried globally by Emby server
                            syncGlobalVideoContent = False
                            PersonUpdate = True

                        # content specific libraries
                        if library_type == 'mixed':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicGenre", "video,music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicArtist", "video,music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Genre", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Tag", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Movie", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Video", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Series", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Season", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Episode", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicVideo", "video", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicAlbum", "music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Audio", "music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "BoxSet", "video", "video")
                            GenreUpdate = True
                            StudioUpdate = True
                            TagUpdate = True
                            MusicGenreUpdate = True
                        elif library_type == 'movies':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Genre", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Tag", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Video", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Movie", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "BoxSet", "video", "video")
                            GenreUpdate = True
                            StudioUpdate = True
                            TagUpdate = True
                        elif library_type == 'musicvideos':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicGenre", "video", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicArtist", "video", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Tag", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicVideo", "video", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "BoxSet", "video", "video")
                            StudioUpdate = True
                            TagUpdate = True
                            MusicGenreUpdate = True
                        elif library_type == 'homevideos':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Genre", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Tag", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Video", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "BoxSet", "video", "video")
                            GenreUpdate = True
                            StudioUpdate = True
                            TagUpdate = True
                        elif library_type == 'tvshows':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Tag", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Genre", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Series", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Season", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Episode", "video", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "BoxSet", "video", "video")
                            GenreUpdate = True
                            StudioUpdate = True
                        elif library_type in ('music', 'audiobooks', 'podcasts'):
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicGenre", "music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Studio", "music", "video")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicArtist", "music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "MusicAlbum", "music", "video,music")
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Audio", "music", "video,music")
                            StudioUpdate = True
                            MusicGenreUpdate = True
                        elif library_type == 'playlists':
                            SQLs["emby"].add_PendingSync(LibraryId, library_name, "Playlist", "none", "none")

                        SQLs["emby"].add_PendingSync(LibraryId, library_name, "Folder", "none", "none")
                        xbmc.log(f"EMBY.database.library: ---[ added library: {LibraryId} ]", 1) # LOGINFO
                    else:
                        xbmc.log(f"EMBY.database.library: ---[ added library not found: {LibraryId} ]", 1) # LOGINFO

            SQLs["emby"].update_LastIncrementalSync(utils.currenttime())
            self.close_EmbyDBRW("select_libraries")

            if LibraryIdsRemove or LibraryIdsAdd:
                self.RunJobs()

            # Update Favorites
            if GenreUpdate or StudioUpdate or TagUpdate or MusicGenreUpdate or PersonUpdate:
                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")

                if GenreUpdate:
                    GenresInfo = embydb.get_FavoriteInfos("Genre")

                if StudioUpdate:
                    StudiosInfo = embydb.get_FavoriteInfos("Studio")

                if TagUpdate:
                    TagsInfo = embydb.get_FavoriteInfos("Tag")

                if MusicGenreUpdate:
                    MusicGenresInfo = embydb.get_FavoriteInfos("MusicGenre")

                if PersonUpdate:
                    PersonsInfo = embydb.get_FavoriteInfos("Person")

                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "select_libraries")
                SQLs = {}

                if GenreUpdate or StudioUpdate or TagUpdate:
                    SQLs["video"] = dbio.DBOpenRO("video", "select_libraries")

                    if GenreUpdate:
                        ProgressBar = xbmcgui.DialogProgressBG()
                        ProgressBar.create(utils.Translate(33199), "Update genre favorites")
                        GenreObject = genre.Genre(self.EmbyServer, SQLs)
                        RecordsPercent = len(GenresInfo) / 100

                        for Index, GenreInfo in enumerate(GenresInfo):
                            if GenreInfo[0]:
                                GenreObject.set_favorite(GenreInfo[0], GenreInfo[1], GenreInfo[2])

                            ProgressBar.update(int(Index / RecordsPercent), "Update genre favorites", str(GenreInfo[1]))

                        del GenreObject
                        ProgressBar.close()
                        del ProgressBar

                    if StudioUpdate:
                        ProgressBar = xbmcgui.DialogProgressBG()
                        ProgressBar.create(utils.Translate(33199), "Update studio favorites")
                        StudioObject = studio.Studio(self.EmbyServer, SQLs)
                        RecordsPercent = len(StudiosInfo) / 100

                        for Index, StudioInfo in enumerate(StudiosInfo):
                            if StudioInfo[0]:
                                StudioObject.set_favorite(StudioInfo[0], StudioInfo[1], StudioInfo[2])

                            ProgressBar.update(int(Index / RecordsPercent), "Update studio favorites", str(StudioInfo[1]))

                        del StudioObject
                        ProgressBar.close()
                        del ProgressBar

                    if TagUpdate:
                        ProgressBar = xbmcgui.DialogProgressBG()
                        ProgressBar.create(utils.Translate(33199), "Update tag favorites")
                        TagObject = tag.Tag(self.EmbyServer, SQLs)
                        RecordsPercent = len(TagsInfo) / 100

                        for Index, TagInfo in enumerate(TagsInfo):
                            if TagInfo[0]:
                                TagObject.set_favorite(TagInfo[0], TagInfo[1], TagInfo[2])

                            ProgressBar.update(int(Index / RecordsPercent), "Update tag favorites", str(TagInfo[1]))

                        del TagObject
                        ProgressBar.close()
                        del ProgressBar

                if MusicGenreUpdate:
                    SQLs["music"] = dbio.DBOpenRO("music", "select_libraries")
                    ProgressBar = xbmcgui.DialogProgressBG()
                    ProgressBar.create(utils.Translate(33199), "Update musicgenre favorites")
                    MusicGenreObject = musicgenre.MusicGenre(self.EmbyServer, SQLs)
                    RecordsPercent = len(MusicGenresInfo) / 100

                    for Index, MusicGenreInfo in enumerate(MusicGenresInfo):
                        if MusicGenreInfo[0]:
                            KodiIds = MusicGenreInfo[1].split(";")

                            if KodiIds[0]:
                                MusicGenreObject.set_favorite(MusicGenreInfo[0], "video", KodiIds[0], MusicGenreInfo[2])

                            if KodiIds[1]:
                                MusicGenreObject.set_favorite(MusicGenreInfo[0], "music", KodiIds[1], MusicGenreInfo[2])

                        ProgressBar.update(int(Index / RecordsPercent), "Update musicgenre favorites", str(MusicGenreInfo[1]))

                    del MusicGenreObject
                    ProgressBar.close()
                    del ProgressBar

                if PersonUpdate:
                    SQLs["video"] = dbio.DBOpenRO("video", "select_libraries")
                    ProgressBar = xbmcgui.DialogProgressBG()
                    ProgressBar.create(utils.Translate(33199), "Update person favorites")
                    PersonObject = person.Person(self.EmbyServer, SQLs)
                    RecordsPercent = len(PersonsInfo) / 100

                    for Index, PersonInfo in enumerate(PersonsInfo):
                        if PersonInfo[0]:
                            PersonObject.set_favorite(PersonInfo[1], PersonInfo[0])

                        ProgressBar.update(int(Index / RecordsPercent), "Update person favorites", str(PersonInfo[1]))

                    del PersonObject
                    ProgressBar.close()
                    del ProgressBar

                for SQL in SQLs:
                    dbio.DBCloseRO(SQL, "select_libraries")

    def refresh_boxsets(self):  # threaded by caller
        SQLs = self.open_EmbyDBRW("refresh_boxsets")
        SQLs = dbio.DBOpenRW("video", "refresh_boxsets", SQLs)
        xbmc.executebuiltin('Dialog.Close(addoninformation)')

        for WhitelistLibraryId, WhitelistLibraryName, WhitelistEmbyType, _, _ in self.Whitelist:
            if WhitelistEmbyType == "BoxSet":
                items = SQLs["emby"].get_boxsets()

                for item in items:
                    SQLs["emby"].add_RemoveItem(item[0], WhitelistLibraryId)

                KodiTagIds = SQLs["emby"].get_item_by_memo("collection")

                for KodiTagId in KodiTagIds:
                    SQLs["video"].delete_tag_by_Id(KodiTagId)

                SQLs["emby"].add_PendingSync(WhitelistLibraryId, WhitelistLibraryName, "BoxSet", "video", "video")

        dbio.DBCloseRW("video", "refresh_boxsets", {})
        self.close_EmbyDBRW("refresh_boxsets")
        self.worker_remove()
        self.worker_library()

    def SyncThemes(self):
        views = []
        DownloadThemes = False
        TvTunesAddon = utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"service.tvtunes", "properties": ["enabled"]}}', True)
        Path = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-themes")
        utils.mkDir(Path)
        Path = utils.PathAddTrailing(f"{Path}{self.EmbyServer.ServerData['ServerId']}")
        utils.mkDir(Path)

        if TvTunesAddon and TvTunesAddon['result']['addon']['enabled']:
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', Path)
            xbmc.log("EMBY.database.library: TV Tunes custom path is enabled and set", 1) # LOGINFO
        else:
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33152))
            return

        if not utils.useDirectPaths:
            DownloadThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Download themes (YES) or link themes (NO)?")

        UseAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Audio")
        UseVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Video")
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), utils.Translate(33451))

        for LibraryID, LibraryInfo in list(self.EmbyServer.Views.ViewItems.items()):
            if LibraryInfo[1] in ('movies', 'tvshows', 'mixed'):
                views.append(LibraryID)

        items = {}

        for ViewId in views:
            if UseVideoThemes:
                for item in self.EmbyServer.API.get_Items(ViewId, ["Movie", "Series"], True, True, {'HasThemeVideo': "True"}):
                    query = normalize_string(item['Name'])
                    items[item['Id']] = query

            if UseAudioThemes:
                for item in self.EmbyServer.API.get_Items(ViewId, ["Movie", "Series"], True, True, {'HasThemeSong': "True"}):
                    query = normalize_string(item['Name'])
                    items[item['Id']] = query

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

                    FilePath, _ = common.get_path_type_from_item(self.EmbyServer.ServerData['ServerId'], ThemeItem, True)

                    if DownloadThemes:
                        FilePath = FilePath.replace(f"http://127.0.0.1:57342/dynamic/{self.EmbyServer.ServerData['ServerId']}/", NfoPath)
                        FilePath = FilePath.replace(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/", NfoPath)
                        utils.translatePath(FilePath).decode('utf-8')

                        if not utils.checkFileExists(FilePath):
                            self.EmbyServer.API.download_file({"Id": ThemeItem['Id'], "FileSize": ThemeItem['Size'], "Name": Name, "FilePath": FilePath, "Path": NfoPath})

                    XMLData += f"    <file>{utils.encode_XML(FilePath)}</file>\n".encode("utf-8")

                XMLData += b'</tvtunes>'
                utils.delFile(NfoFile)
                utils.writeFileBinary(NfoFile, XMLData)

            Index += 1

        ProgressBar.close()
        del ProgressBar
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=5000, sound=False)

    def SyncLiveTV(self):
        iptvsimpleData = utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"pvr.iptvsimple", "properties": ["version"]}}', True)

        if not iptvsimpleData:
            xbmc.log("EMBY.database.library: iptv simple not found", 2) # LOGWARNING
            return

        xbmc.log("EMBY.database.library: -->[ iptv simple config change ]", 1) # LOGINFO
        SQLs = dbio.DBOpenRW("epg", "livetvsync", {})
        SQLs["epg"].delete_tables("EPG")
        dbio.DBCloseRW("epg", "livetvsync", {})
        SQLs = dbio.DBOpenRW("tv", "livetvsync", {})
        SQLs["tv"].delete_tables("TV")
        dbio.DBCloseRW("tv", "livetvsync", {})
        PlaylistFile = f"{utils.FolderEmbyTemp}{self.EmbyServer.ServerData['ServerId']}-livetv.m3u"
        utils.delFile(PlaylistFile)
        PlaylistM3U = "#EXTM3U\n"
        ChannelsUnsorted = []
        ChannelsSortedbyChannelNumber = {}
        Channels = self.EmbyServer.API.get_channels()

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

            PlaylistM3U += f"http://127.0.0.1:57342/dynamic/{self.EmbyServer.ServerData['ServerId']}/t-{ChannelSorted['Id']}-livetv\n"

        utils.writeFileString(PlaylistFile, PlaylistM3U)
        self.SyncLiveTVEPG(False)
        SimpleIptvSettings = utils.readFileString("special://home/addons/plugin.video.emby-next-gen/resources/iptvsimple.xml")
        SimpleIptvSettings = SimpleIptvSettings.replace("SERVERID", self.EmbyServer.ServerData['ServerId'])
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
        utils.writeFileBinary(f"special://profile/addon_data/pvr.iptvsimple/instance-settings-{str(int(self.EmbyServer.ServerData['ServerId'], 16))[:4]}.xml", SimpleIptvSettings.encode("utf-8"))
        utils.sleep(3)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')
        xbmc.log("EMBY.database.library: --<[ iptv simple config change ]", 1) # LOGINFO

    def SyncLiveTVEPG(self, ChannelSync=True):
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

        if utils.SyncLiveTvOnEvents and ChannelSync:
            self.SyncLiveTV()

        xbmc.log("EMBY.database.library: --<[ load EPG ]", 1) # LOGINFO

    # Add item_id to userdata queue
    def userdata(self, ItemIds):  # threaded by caller -> websocket via monitor
        if ItemIds:
            SQLs = self.open_EmbyDBRW("userdata")

            for ItemId in ItemIds:
                SQLs["emby"].add_Userdata(str(ItemId))

            self.close_EmbyDBRW("userdata")
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Items):  # threaded by caller
        if Items:
            SQLs = self.open_EmbyDBRW("updated")

            for Item in Items:
                SQLs["emby"].add_UpdateItem(Item[0], Item[1], Item[2])

            self.close_EmbyDBRW("updated")
            self.worker_update()

    # Add item_id to removed queue
    def removed(self, Ids):  # threaded by caller
        if Ids:
            SQLs = self.open_EmbyDBRW("removed")

            for Id in Ids:
                SQLs["emby"].add_RemoveItem(Id, None)

            self.close_EmbyDBRW("removed")
            self.worker_remove()

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
            if WorkerName == "worker_userdata" and Key.startswith("server_busy_"): # Continue on progress updates, even emby server is busy
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

        if Valid and Item['Type'] in SortItems:
            if Item['Type'] == "Recording":
                if 'MediaType' in Item:
                    if Item['IsSeries']:
                        Item['Type'] = 'Episode'
                    else:
                        Item['Type'] = 'Movie'

            SortItems[Item['Type']].add(json.dumps(Item)) # Dict is not hashable (not possible adding "dict" to "set") -> convert to json string necessary
        else:
            Others.add(json.dumps(Item))
            xbmc.log(f"EMBY.database.library: Unknown {Item}", 1) # LOGINFO
            continue

    if Reverse:
        return {"video": [SortItems['Video'], SortItems['Movie'], SortItems['Episode'], SortItems['Season'], SortItems['Series'], SortItems['Studio'], SortItems['Person'], SortItems['Tag'], SortItems['Genre'], SortItems['BoxSet']], "music,video": [SortItems['Audio'], SortItems['MusicVideo'], SortItems['MusicAlbum'], SortItems['MusicArtist'], SortItems['MusicGenre']], "none": [SortItems['Playlist'], SortItems['Folder']]}, Others

    return {"music,video": [SortItems['MusicArtist'], SortItems['MusicAlbum'], SortItems['MusicGenre'], SortItems['MusicVideo'], SortItems['Audio']], "video": [SortItems['Genre'], SortItems['Tag'], SortItems['Person'], SortItems['Studio'], SortItems['Series'], SortItems['Season'], SortItems['Episode'], SortItems['Movie'], SortItems['Video'], SortItems['BoxSet']], "none": [SortItems['Folder'], SortItems['Playlist']]}, Others

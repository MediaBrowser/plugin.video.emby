import json
import unicodedata
import xbmc
import xbmcaddon
from core import movies, musicvideos, tvshows, music, folder, common
from helper import utils, pluginmenu
from . import dbio

WorkerInProgress = False


class Library:
    def __init__(self, EmbyServer):
        xbmc.log("EMBY.database.library: -->[ library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.Whitelist = [] # LibraryId, LibraryName, MediaType
        self.WhitelistUnique = [] # LibraryId, LibraryName
        self.LastSyncTime = ""
        self.ContentObject = None
        self.EmbyDBOpen = False
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

    def close_Worker(self, WorkerName):
        self.close_EmbyDBRW(WorkerName)
        utils.SyncPause['kodi_rw'] = False
        utils.refresh_widgets()
        utils.progress_close()
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
        return dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], WorkerName)

    def close_EmbyDBRW(self, WorkerName):
        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName)
        self.EmbyDBOpen = False
        utils.SyncPause['priority'] = False

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        embydb = self.open_EmbyDBRW("set_syncdate")
        embydb.update_LastIncrementalSync(TimestampUTC)
        self.close_EmbyDBRW("set_syncdate")
        self.LastSyncTime = TimestampUTC
        LastSyncTimeLocalTime = utils.convert_to_local(self.LastSyncTime)
        utils.set_syncdate(LastSyncTimeLocalTime)

    def load_WhiteList(self, embydb):
        self.WhitelistUnique = []
        self.Whitelist = embydb.get_Whitelist()

        for LibraryIdWhitelist, LibraryNameWhitelist, _ in self.Whitelist:
            if (LibraryIdWhitelist, LibraryNameWhitelist) not in self.WhitelistUnique:
                self.WhitelistUnique.append((LibraryIdWhitelist, LibraryNameWhitelist))

    def load_settings(self):
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = True

        # Load essential data and prefetching Media tags
        embydb = self.open_EmbyDBRW("load_settings")

        if embydb.init_EmbyDB():
            self.load_WhiteList(embydb)
        else:
            self.close_EmbyDBRW("load_settings")
            xbmc.log("EMBY.database.library: load_settings, database corrupt", 1) # LOGINFO
            return

        self.LastSyncTime = embydb.get_LastIncrementalSync()
        self.close_EmbyDBRW("load_settings")

        # Init database
        videodb = dbio.DBOpenRW("video", "load_settings")
        videodb.init_favorite_tags()
        videodb.add_Index()
        videodb.get_add_path(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/", None, None)

        for ViewItem in list(self.EmbyServer.Views.ViewItems.values()):
            common.MediaTags[ViewItem[0]] = videodb.get_tag(ViewItem[0])

        dbio.DBCloseRW("video", "load_settings")
        musicdb = dbio.DBOpenRW("music", "load_settings")
        musicdb.add_Index()
        musicdb.disable_rescan(utils.currenttime_kodi_format())
        dbio.DBCloseRW("music", "load_settings")
        texturedb = dbio.DBOpenRW("texture", "load_settings")
        texturedb.add_Index()
        dbio.DBCloseRW("texture", "load_settings")
        utils.SyncPause[f"database_init_{self.EmbyServer.ServerData['ServerId']}"] = False

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        xbmc.log("EMBY.database.library: THREAD: --->[ retrieve changes ]", 1) # LOGINFO
        self.KodiStartSyncRunning = True
        NewSyncData = utils.currenttime()
        UpdateSyncData = False

        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        self.RunJobs()
        UpdateData = []

        if self.LastSyncTime:
            xbmc.log(f"EMBY.database.library: Retrieve changes, last synced: {self.LastSyncTime}", 1) # LOGINFO
            utils.progress_open(utils.Translate(33445))
            xbmc.log("EMBY.database.library: -->[ Kodi companion ]", 1) # LOGINFO
            result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

            if 'ItemsRemoved' in result:
                UpdateSyncData = True
                self.removed(result['ItemsRemoved'])

            xbmc.log("EMBY.database.library: --<[ Kodi companion ]", 1) # LOGINFO
            ProgressBarTotal = len(self.Whitelist) / 100
            ProgressBarIndex = 0

            for Whitelist in self.Whitelist:
                xbmc.log(f"EMBY.database.library: [ retrieve changes ] {Whitelist[0]} / {Whitelist[1]}", 1) # LOGINFO
                LibraryName = ""
                ProgressBarIndex += 1

                if Whitelist[0] in self.EmbyServer.Views.ViewItems:
                    LibraryName = self.EmbyServer.Views.ViewItems[Whitelist[0]][0]
                    utils.progress_update(int(ProgressBarIndex / ProgressBarTotal), utils.Translate(33445), LibraryName)

                if not LibraryName:
                    xbmc.log(f"EMBY.database.library: [ KodiStartSync remove library {Whitelist[0]} ]", 1) # LOGINFO
                    continue

                ItemIndex = 0
                UpdateDataTemp = 10000 * [()] # pre allocate memory

                for Item in self.EmbyServer.API.get_Items(Whitelist[0], [Whitelist[2]], True, True, {'MinDateLastSavedForUser': self.LastSyncTime}):
                    if utils.SystemShutdown:
                        utils.progress_close()
                        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 3", 1) # LOGINFO
                        self.KodiStartSyncRunning = False
                        return

                    if ItemIndex >= 10000:
                        UpdateData += UpdateDataTemp
                        UpdateDataTemp = 10000 * [()] # pre allocate memory
                        ItemIndex = 0

                    UpdateDataTemp[ItemIndex] = (Item['Id'], Item['Type'])
                    ItemIndex += 1

                UpdateData += UpdateDataTemp

            utils.progress_close()

        # Run jobs
        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ]", 1) # LOGINFO

        if UpdateData:
            UpdateData = list(dict.fromkeys(UpdateData)) # filter doubles

            if () in UpdateData:  # Remove empty
                UpdateData.remove(())

            UpdateSyncData = True
            self.updated(UpdateData)

        # Update sync update timestamp
        if UpdateSyncData:
            xbmc.log("EMBY.database.library: Start sync, updates found", 1) # LOGINFO
            pluginmenu.reset_querycache()
            self.set_syncdate(NewSyncData)

        self.SyncLiveTVEPG()
        self.KodiStartSyncRunning = False

    def worker_userdata(self):
        WorkerName = "worker_userdata"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            UserDataItems = embydb.get_Userdata()
            xbmc.log(f"EMBY.database.library: -->[ worker userdata started ] queue size: {len(UserDataItems)}", 1) # LOGINFO

            if not UserDataItems:
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
                globals()["WorkerInProgress"] = False
                return ContinueJobs
        else:
            return False

        utils.progress_open(utils.Translate(33178))
        Items = []
        ItemsNotSynced = []

        for UserDataItem in UserDataItems:
            UserDataItem = StringToDict(UserDataItem[0])
            e_item = embydb.get_item_by_id(UserDataItem['ItemId'])

            if e_item:
                if "LastPlayedDate" in UserDataItem:
                    LastPlayedDate = UserDataItem['LastPlayedDate']
                    PlayCount = UserDataItem['PlayCount']
                else:
                    LastPlayedDate = None
                    PlayCount = None

                Items.append({"Id": UserDataItem['ItemId'], "KodiItemId": e_item[0], "KodiFileId": e_item[1], "KodiType": e_item[4], "Type": e_item[5], 'PlaybackPositionTicks': UserDataItem['PlaybackPositionTicks'], 'PlayCount': PlayCount, 'IsFavorite': UserDataItem['IsFavorite'], 'LastPlayedDate': LastPlayedDate, 'Played': UserDataItem['Played'], "PlayedPercentage": UserDataItem.get('PlayedPercentage', 0), "UpdateItem": str(UserDataItem)})
            else: # skip if item is not synced
                ItemsNotSynced.append(str(UserDataItem))
                xbmc.log(f"EMBY.database.library: Skip not synced item: {UserDataItem}", 1) # LOGINFO

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        UpdateItems = ItemsSort(Items, False)
        embydb = self.open_EmbyDBRW(WorkerName)

        for ItemNotSynced in ItemsNotSynced:
            embydb.delete_Userdata(ItemNotSynced)

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if content_available(ContentType, CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                kodidb = dbio.DBOpenRW(ContentType, WorkerName)

                for Items in CategoryItems:
                    self.ContentObject = None

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_Userdata(Item["UpdateItem"])
                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), index, Item, embydb, kodidb, ContentType, WorkerName)

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker userdata interrupt ]", 1) # LOGINFO
                            return False

                dbio.DBCloseRW(ContentType, WorkerName)

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName)
        xbmc.log("EMBY.database.library: --<[ worker userdata completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

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

        utils.progress_open(utils.Translate(33178))
        RecordsPercent = UpdateItemsCount / 100
        index = 0
        embydb = None

        for ContentType, UpdateItemsIds in list(UpdateItems.items()):
            if ContentType == "unknown":
                ContentType = ["Folder", "Episode", "Movie", "Trailer", "MusicVideo", "BoxSet", "MusicAlbum", "MusicArtist", "Season", "Series", "Audio", "Video"]
            else:
                ContentType = [ContentType]

            UpdateItemsIdsTemp = UpdateItemsIds.copy()
            Items = 100 * [None] # pre allocate memory
            ItemArrayIndex = 0
            self.EmbyServer.API.ProcessProgress["worker_update"] = 0

            for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items_Ids(UpdateItemsIds, ContentType, False, False, True, "worker_update"), 1):
                if ItemArrayIndex >= 100:
                    self.EmbyServer.API.ProcessProgress["worker_update"] = ItemIndex
                    Continue, index, embydb = self.worker_update_items(embydb, Items, UpdateItemsIds, RecordsPercent, WorkerName, index)

                    if not Continue:
                        self.EmbyServer.API.ProcessProgress["worker_update"] = -1
                        return False

                    Items = 100 * [None] # pre allocate memory
                    ItemArrayIndex = 0

                Items[ItemArrayIndex] = Item
                ItemArrayIndex += 1

            Continue, index, embydb = self.worker_update_items(embydb, Items, UpdateItemsIds, RecordsPercent, WorkerName, index)

            if not Continue:
                return False

            # Remove not detected Items
            for UpdateItemsIdTemp in UpdateItemsIdsTemp:
                if UpdateItemsIdTemp in UpdateItemsIds:
                    UpdateItemsIds.remove(UpdateItemsIdTemp)
                    embydb.delete_UpdateItem(UpdateItemsIdTemp)

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName)
        xbmc.log("EMBY.database.library: --<[ worker update completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_update_items(self, embydb, Items, UpdateItemsIds, RecordsPercent, WorkerName, index):
        SortedItems = ItemsSort(Items, False)

        if not embydb:
            embydb = self.open_EmbyDBRW(WorkerName)

        for ContentType, CategoryItems in list(SortedItems.items()):
            if content_available(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, WorkerName)

                for ProcessItems in CategoryItems:
                    self.ContentObject = None

                    for Item in ProcessItems:
                        embydb.delete_UpdateItem(Item['Id'])

                        if Item['Id'] in UpdateItemsIds:
                            UpdateItemsIds.remove(Item['Id'])

                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), index, Item, embydb, kodidb, ContentType, WorkerName)
                        index += 1

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker update interrupt ]", 1) # LOGINFO
                            return False, index, embydb

                dbio.DBCloseRW(ContentType, WorkerName)

        return True, index, embydb

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

        utils.progress_open(utils.Translate(33261))
        RecordsPercent = len(RemoveItems) / 100
        AllRemoveItems = []
        embydb = self.open_EmbyDBRW(WorkerName)

        for index, RemoveItem in enumerate(RemoveItems, 1):
            utils.progress_update(int(index / RecordsPercent), utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = embydb.get_media_by_id(RemoveItem[0])

            if FoundRemoveItems:
                if FoundRemoveItems[0][2] == "Folder":
                    xbmc.log(f"EMBY.database.library: Detect media by folder id {RemoveItem[0]} / {FoundRemoveItems[0][11]}", 1) # LOGINFO
                    FoundRemoveItems = embydb.get_media_by_folder(FoundRemoveItems[0][11])

            if not FoundRemoveItems:
                xbmc.log(f"EMBY.database.library: Detect media by parent id {RemoveItem[0]}", 1) # LOGINFO
                FoundRemoveItems = embydb.get_media_by_parent_id(RemoveItem[0])

            if FoundRemoveItems:
                TempRemoveItems = []

                for FoundRemoveItem in FoundRemoveItems:
                    LibraryIds = FoundRemoveItem[1].split(";")
                    KodiItemIds = FoundRemoveItem[4]

                    if KodiItemIds:
                        KodiItemIds = str(KodiItemIds).split(";")
                    else:
                        KodiItemIds = len(LibraryIds) * [None]

                    KodiFileIds = FoundRemoveItem[5]

                    if KodiFileIds:
                        KodiFileIds = str(KodiFileIds).split(";")
                    else:
                        KodiFileIds = len(LibraryIds) * [None]

                    KodiParentIds = FoundRemoveItem[7]

                    if KodiParentIds:
                        KodiParentIds = str(KodiParentIds).split(";")
                    else:
                        KodiParentIds = len(LibraryIds) * [None]

                    for ItemIndex, LibraryId in enumerate(LibraryIds):
                        if LibraryId in self.EmbyServer.Views.ViewItems:
                            LibrayName = self.EmbyServer.Views.ViewItems[LibraryId][0]
                        else:
                            LibrayName = "unknown library"

                        if not RemoveItem[1] or LibraryId == RemoveItem[1]:
                            TempRemoveItems.append({'Id': FoundRemoveItem[0], 'Type': FoundRemoveItem[2], 'Library': {"Id": LibraryId, "Name": LibrayName}, 'DeleteByLibraryId': RemoveItem[1], 'KodiItemId': KodiItemIds[ItemIndex], 'KodiFileId': KodiFileIds[ItemIndex], 'KodiParentId': KodiParentIds[ItemIndex], 'PresentationUniqueKey': FoundRemoveItem[9]})
                        else:
                            embydb.delete_RemoveItem_EmbyId(RemoveItem[0])
                            xbmc.log(f"EMBY.database.library: Worker remove, item not valid {RemoveItem}", 3) # LOGERROR

                AllRemoveItems += TempRemoveItems
            else:
                embydb.delete_RemoveItem_EmbyId(RemoveItem[0])
                xbmc.log(f"EMBY.database.library: Worker remove, item not found in local database {RemoveItem[0]}", 1) # LOGINFO
                continue

        UpdateItems = ItemsSort(AllRemoveItems, True)

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if content_available(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, WorkerName)

                for Items in CategoryItems:
                    self.ContentObject = None
                    RecordsPercent = len(Items) / 100

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_RemoveItem(Item['Id'], Item['Library']["Id"])
                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), index, Item, embydb, kodidb, ContentType, WorkerName)

                        if not Continue:
                            xbmc.log("EMBY.database.library: --<[ worker remove interrupt ]", 1) # LOGINFO
                            return False

                dbio.DBCloseRW(ContentType, WorkerName)

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName)
        xbmc.log("EMBY.database.library: --<[ worker remove completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_library(self):
        WorkerName = "worker_library"
        self.open_Worker(WorkerName)
        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        SyncItems = embydb.get_PendingSync()
        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
        xbmc.log(f"EMBY.database.library: -->[ worker library started ] queue size: {len(SyncItems)}", 1) # LOGINFO

        if not SyncItems:
            globals()["WorkerInProgress"] = False
            xbmc.log("EMBY.database.library: --<[ worker library empty ]", 1) # LOGINFO
            return

        utils.progress_open(f"{utils.Translate(33238)}")
        newContent = utils.newContent
        utils.newContent = False  # Disable new content notification on init sync
        embydb = self.open_EmbyDBRW(WorkerName)
        SyncItemPercent = len(SyncItems) / 100

        for SyncItemIndex, SyncItem in enumerate(SyncItems):
            SyncItemProgress = int(SyncItemIndex / SyncItemPercent)
            utils.progress_update(SyncItemProgress, f"{utils.Translate(33238)}", SyncItem[1])
            embydb.add_Whitelist(SyncItem[0], SyncItem[1], SyncItem[2])
            self.load_WhiteList(embydb)
            kodidb = dbio.DBOpenRW(SyncItem[3], WorkerName)

            if SyncItem[3] == "video":
                common.MediaTags[SyncItem[1]] = kodidb.get_add_tag(SyncItem[1])

            self.ContentObject = None
            self.EmbyServer.API.ProcessProgress["worker_library"] = 0

            # Sync Content
            for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(SyncItem[0], [SyncItem[2]], False, True, {}, "worker_library"), 1):
                Item["Library"] = {"Id": SyncItem[0], "Name": SyncItem[1]}
                Continue, embydb, kodidb = self.ItemOps(SyncItemProgress, ItemIndex, Item, embydb, kodidb, SyncItem[3], WorkerName)
                self.EmbyServer.API.ProcessProgress["worker_library"] = ItemIndex

                if not Continue:
                    self.EmbyServer.API.ProcessProgress["worker_library"] = -1
                    xbmc.log("EMBY.database.library: --<[ worker library interrupt ]", 1) # LOGINFO
                    return

            dbio.DBCloseRW(SyncItem[3], WorkerName)
            embydb.remove_PendingSync(SyncItem[0], SyncItem[1], SyncItem[2], SyncItem[3])

        utils.newContent = newContent
        self.EmbyServer.Views.update_nodes()
        pluginmenu.reset_querycache()
        self.close_Worker(WorkerName)
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.log("EMBY.database.library: --<[ worker library completed ]", 1) # LOGINFO
        self.RunJobs()

    def ItemOps(self, ProgressValue, ItemIndex, Item, embydb, kodidb, ContentCategory, WorkerName):
        Ret = False

        if not self.ContentObject:
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        if WorkerName in ("worker_library", "worker_update"):
            if Item['Type'] == "Audio":
                Ret = self.ContentObject.song(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] == "MusicAlbum":
                Ret = self.ContentObject.album(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] in ("MusicArtist", "AlbumArtist"):
                Ret = self.ContentObject.artist(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] in ("Movie", "Video"):
                Ret = self.ContentObject.movie(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] == "BoxSet":
                Ret = self.ContentObject.boxset(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] == "MusicVideo":
                Ret = self.ContentObject.musicvideo(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] == "Episode":
                Ret = self.ContentObject.episode(Item)
                ProgressMsg = f"{Item.get('SeriesName', 'Unknown Seriesname')} / {Item.get('SeasonName', 'Unknown Seasonname')} / {Item.get('Name', 'unknown')}"
            elif Item['Type'] == "Season":
                Ret = self.ContentObject.season(Item)
                ProgressMsg = f"{Item['SeriesName']} / {Item.get('Name', 'unknown')}"
            elif Item['Type'] == "Series":
                Ret = self.ContentObject.tvshow(Item)
                ProgressMsg = Item.get('Name', "unknown")
            elif Item['Type'] == "Folder":
                self.ContentObject.folder(Item)

                if "Path" in Item:
                    ProgressMsg = Item['Path']
                elif "Name" in Item:
                    ProgressMsg = Item.get('Name', "unknown")
                else:
                    ProgressMsg = "unknown"
            else:
                ProgressMsg = "unknown"

            utils.progress_update(ProgressValue, f"{Item['Type']}: {ItemIndex}", ProgressMsg)

            if Ret and utils.newContent:
                if ContentCategory == "music":
                    MsgTime = int(utils.newmusictime) * 1000
                else:
                    MsgTime = int(utils.newvideotime) * 1000

                utils.Dialog.notification(heading=f"{utils.Translate(33049)} {Item['Type']}", message=Item.get('Name', "unknown"), icon=utils.icon, time=MsgTime, sound=False)
        elif WorkerName == "worker_remove":
            utils.progress_update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))
            self.ContentObject.remove(Item)
        elif WorkerName == "worker_userdata":
            utils.progress_update(ProgressValue, f"{Item['Type']}: {ItemIndex}", str(Item['Id']))
            self.ContentObject.userdata(Item)

        # Check if Kodi db or emby is about to open -> close db, wait, reopen db
        if Worker_is_paused(WorkerName):
            xbmc.log(f"EMBY.database.library: -->[ worker delay {utils.SyncPause}]", 1) # LOGINFO
            dbio.DBCloseRW(ContentCategory, WorkerName)
            dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName)
            self.EmbyDBOpen = False

            while Worker_is_paused(WorkerName):
                if utils.sleep(1):
                    utils.progress_close()
                    xbmc.log("EMBY.database.library: [ worker exit (shutdown) ]", 1) # LOGINFO
                    return False, None, None

            self.EmbyDBOpen = True
            xbmc.log(f"EMBY.database.library: --<[ worker delay {utils.SyncPause}]", 1) # LOGINFO
            embydb = dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], WorkerName)
            kodidb = dbio.DBOpenRW(ContentCategory, WorkerName)
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        Continue = True

        if utils.SystemShutdown:
            dbio.DBCloseRW(ContentCategory, WorkerName)
            dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName)
            self.EmbyDBOpen = False
            xbmc.log("EMBY.database.library: [ worker exit ]", 1) # LOGINFO
            Continue = False

        return Continue, embydb, kodidb

    def load_libraryObject(self, MediaType, embydb, kodidb):
        if MediaType in ("Movie", "BoxSet", "Video", "SpecialFeature"):
            self.ContentObject = movies.Movies(self.EmbyServer, embydb, kodidb)
        elif MediaType == "MusicVideo":
            self.ContentObject = musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb)
        elif MediaType in ('Audio', "MusicArtist", "MusicAlbum", "AlbumArtist"):
            self.ContentObject = music.Music(self.EmbyServer, embydb, kodidb)
        elif MediaType in ("Episode", "Season", 'Series'):
            self.ContentObject = tvshows.TVShows(self.EmbyServer, embydb, kodidb)
        elif MediaType == "Folder":
            self.ContentObject = folder.Folder(self.EmbyServer, embydb)

    # Run workers in specific order
    def RunJobs(self):
        if self.worker_remove():
            if self.worker_update():
                if self.worker_userdata():
                    self.worker_library()

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):  # threaded by caller
        libraries = ()
        pluginmenu.reset_querycache()

        if mode in ('RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            for LibraryId, LibraryName in self.WhitelistUnique:
                AddData = {'Id': LibraryId, 'Name': LibraryName}

                if AddData not in libraries:
                    libraries += (AddData,)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()

            for LibraryId, _ in self.WhitelistUnique:
                if LibraryId in AvailableLibs:
                    del AvailableLibs[LibraryId]

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ["movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos"]:
                    libraries += ({'Id': AvailableLibId, 'Name': AvailableLib[0]},)

        choices = [x['Name'] for x in libraries]
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
            selection = list(range(1, len(libraries) + 1))

        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        remove_librarys = ()
        add_librarys = ()

        if mode in ('AddLibrarySelection', 'UpdateLibrarySelection'):
            for x in selection:
                add_librarys += (libraries[x - 1]['Id'],)
        elif mode == 'RepairLibrarySelection':
            for x in selection:
                remove_librarys += (libraries[x - 1]['Id'],)
                add_librarys += (libraries[x - 1]['Id'],)
        elif mode == 'RemoveLibrarySelection':
            for x in selection:
                remove_librarys += (libraries[x - 1]['Id'],)

        if remove_librarys or add_librarys:
            embydb = self.open_EmbyDBRW("select_libraries")
            videodb = dbio.DBOpenRW("video", "select_libraries")
            musicdb = dbio.DBOpenRW("music", "select_libraries")

            if remove_librarys:
                for LibraryId in remove_librarys:
                    if LibraryId in self.EmbyServer.Views.ViewItems:
                        ViewData = self.EmbyServer.Views.ViewItems[LibraryId]
                        videodb.delete_tag(ViewData[0])

                    items = embydb.get_item_by_emby_folder_wild(LibraryId)

                    for item in items:
                        embydb.add_RemoveItem(item[0], LibraryId)

                    embydb.remove_Whitelist(LibraryId)
                    self.load_WhiteList(embydb)
                    self.EmbyServer.Views.delete_playlist_by_id(LibraryId)
                    self.EmbyServer.Views.delete_node_by_id(LibraryId)
                    xbmc.log(f"EMBY.database.library: ---[ removed library: {LibraryId} ]", 1) # LOGINFO
                    self.EmbyServer.Views.update_nodes()

            if add_librarys:
                for LibraryId in add_librarys:
                    if LibraryId in self.EmbyServer.Views.ViewItems:
                        ViewData = self.EmbyServer.Views.ViewItems[LibraryId]
                        library_type = ViewData[1]
                        library_name = ViewData[0]

                        if library_type == 'mixed':
                            embydb.add_PendingSync(LibraryId, library_name, "Movie", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "BoxSet", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Video", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Series", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Season", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Episode", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "Audio", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "MusicVideo", "video")
                        elif library_type == 'movies':
                            embydb.add_PendingSync(LibraryId, library_name, "Movie", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "BoxSet", "video")
                        elif library_type == 'musicvideos':
                            embydb.add_PendingSync(LibraryId, library_name, "MusicVideo", "video")
                        elif library_type == 'homevideos':
                            embydb.add_PendingSync(LibraryId, library_name, "Video", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "BoxSet", "video")
                        elif library_type == 'tvshows':
                            embydb.add_PendingSync(LibraryId, library_name, "Series", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Season", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "Episode", "video")
                        elif library_type == 'podcasts':
                            embydb.add_PendingSync(LibraryId, library_name, "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "Audio", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "Video", "video")
                            musicdb.add_role()
                        elif library_type in ('music', 'audiobooks'):
                            embydb.add_PendingSync(LibraryId, library_name, "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, "Audio", "music")
                            musicdb.add_role()

                        embydb.add_PendingSync(LibraryId, library_name, "Folder", "folder")
                        xbmc.log(f"EMBY.database.library: ---[ added library: {LibraryId} ]", 1) # LOGINFO
                    else:
                        xbmc.log(f"EMBY.database.library: ---[ added library not found: {LibraryId} ]", 1) # LOGINFO

            self.close_EmbyDBRW("select_libraries")
            dbio.DBCloseRW("video", "select_libraries")
            dbio.DBCloseRW("music", "select_libraries")

            if remove_librarys or add_librarys:
                self.RunJobs()

    def refresh_boxsets(self):  # threaded by caller
        embydb = self.open_EmbyDBRW("refresh_boxsets")
        xbmc.executebuiltin('Dialog.Close(addoninformation)')

        for WhitelistLibraryId, WhitelistLibraryName, WhitelistLibraryType in self.Whitelist:
            if WhitelistLibraryType == "BoxSet":
                items = embydb.get_item_by_emby_folder_wild_and_EmbyType(WhitelistLibraryId, "BoxSet")

                for item in items:
                    embydb.add_RemoveItem(item[0], WhitelistLibraryId)

                embydb.add_PendingSync(WhitelistLibraryId, WhitelistLibraryName, "BoxSet", "video")

        self.close_EmbyDBRW("refresh_boxsets")
        self.worker_remove()
        self.worker_library()

    def SyncThemes(self):
        views = []
        DownloadThemes = False
        tvtunesData = utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"service.tvtunes", "properties": ["enabled"]}}', True)

        if tvtunesData and tvtunesData['result']['addon']['enabled']:
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', utils.FolderAddonUserdataLibrary)
            xbmc.log("EMBY.helper.pluginmenu: TV Tunes custom path is enabled and set", 1) # LOGINFO
        else:
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33152))
            return

        if not utils.useDirectPaths:
            DownloadThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Download themes (YES) or link themes (NO)?")

        UseAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Audio")
        UseVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message="Video")
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        utils.progress_open(utils.Translate(33451))

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

        for ItemId, name in list(items.items()):
            utils.progress_update(int(Index / TotalItems), utils.Translate(33451), name)
            nfo_path = f"{utils.FolderAddonUserdataLibrary}{name}/"
            nfo_file = f"{nfo_path}tvtunes.nfo"
            paths = []
            themes = []

            if UseAudioThemes and not UseVideoThemes:
                ThemeItems = self.EmbyServer.API.get_themes(ItemId, True, False)

                if 'ThemeSongsResult' in ThemeItems:
                    themes += ThemeItems['ThemeSongsResult']['Items']
            elif UseVideoThemes and not UseAudioThemes:
                ThemeItems = self.EmbyServer.API.get_themes(ItemId, False, True)

                if 'ThemeVideosResult' in ThemeItems:
                    themes += ThemeItems['ThemeVideosResult']['Items']
            elif UseVideoThemes and UseAudioThemes:
                ThemeItems = self.EmbyServer.API.get_themes(ItemId, True, True)

                if 'ThemeSongsResult' in ThemeItems:
                    themes += ThemeItems['ThemeSongsResult']['Items']

                if 'ThemeVideosResult' in ThemeItems:
                    themes += ThemeItems['ThemeVideosResult']['Items']

            if DownloadThemes and utils.getFreeSpace(utils.FolderAddonUserdataLibrary) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=5000, sound=True)
                xbmc.log("EMBY.helper.pluginmenu: Themes download: running out of space", 2) # LOGWARNING
                break

            if utils.SystemShutdown:
                utils.progress_close()
                return

            # add content sorted by audio -> video
            for theme in themes:
                if not 'Path' in theme:
                    xbmc.log(f"EMBY.helper.pluginmenu: Theme not including Path: {theme}", 0) # LOGDEBUG
                    xbmc.log(f"EMBY.helper.pluginmenu: Theme not including Path: {theme['Id']}", 3) # LOGERROR
                    continue

                Filename = utils.PathToFilenameReplaceSpecialCharecters(theme['Path'])

                if theme['Type'] == 'Audio':
                    if DownloadThemes:
                        ThemeFile = f"{nfo_path}{Filename}"
                        paths.append(ThemeFile)

                        if not utils.checkFileExists(ThemeFile):
                            BinaryData = self.EmbyServer.API.get_Item_Binary(theme['Id'])

                            if BinaryData:
                                utils.mkDir(nfo_path)
                                utils.writeFileBinary(ThemeFile, BinaryData)
                            else:
                                xbmc.log(f"EMBY.helper.pluginmenu: Themes: Download failed {theme['Path']}", 2) # LOGWARNING
                                paths.remove(ThemeFile)
                                continue
                    else: # remote links
                        if utils.useDirectPaths:
                            paths.append(theme['Path'])
                        else:
                            paths.append(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/A-{theme['Id']}--{Filename}")
                else:
                    if DownloadThemes:
                        ThemeFile = f"{nfo_path}{Filename}"
                        paths.append(ThemeFile)

                        if not utils.checkFileExists(ThemeFile):
                            BinaryData = self.EmbyServer.API.get_Item_Binary(theme['Id'])

                            if BinaryData:
                                utils.mkDir(nfo_path)
                                utils.writeFileBinary(ThemeFile, BinaryData)
                            else:
                                xbmc.log(f"EMBY.helper.pluginmenu: Themes: Download failed {theme['Path']}", 2) # LOGWARNING
                                paths.remove(ThemeFile)
                                continue
                    else: # remote links
                        if utils.useDirectPaths:
                            paths.append(theme['Path'])
                        else:
                            paths.append(f"{utils.AddonModePath}dynamic/{self.EmbyServer.ServerData['ServerId']}/V-{theme['Id']}--{Filename}")

            Index += 1

            if paths:
                utils.mkDir(nfo_path)
                Data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<tvtunes>\n'

                for path in paths:
                    Data += f"    <file>{path}</file>\n".encode("utf-8")

                Data += b'</tvtunes>'
                utils.delFile(nfo_file)
                utils.writeFileBinary(nfo_file, Data)

        utils.progress_close()
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=5000, sound=False)

    def SyncLiveTV(self):
        iptvsimpleData = utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"pvr.iptvsimple", "properties": ["version"]}}', True)

        if iptvsimpleData:
            iptvsimpleVersion = iptvsimpleData['result']['addon']['version']
            xbmc.log(f"EMBY.database.library: iptv simple version: {iptvsimpleVersion}", 1) # LOGINFO
        else:
            xbmc.log("EMBY.database.library: iptv simple not found", 2) # LOGWARNING
            return

        epgdb = dbio.DBOpenRW("epg", "livetvsync")
        epgdb.delete_tables("EPG")
        dbio.DBCloseRW("epg", "livetvsync")
        tvdb = dbio.DBOpenRW("tv", "livetvsync")
        tvdb.delete_tables("TV")
        dbio.DBCloseRW("tv", "livetvsync")
        PlaylistFile = f"{utils.FolderEmbyTemp}{self.EmbyServer.ServerData['ServerId']}-livetv.m3u"
        utils.delFile(PlaylistFile)
        playlist = "#EXTM3U\n"
        ChannelsUnsorted = []
        ChannelsSortedbyChannelNumber = {}
        Channels = self.EmbyServer.API.get_channels()

        # Sort Channels by ChannelNumber
        for Channel in Channels:
            ChannelNumber = str(Channel.get("ChannelNumber", 0))

            if ChannelNumber.isnumeric():
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
                Tag = "--No Info--"

            tvglogo = ""
            tvgchno = ""
            ChannelNumber = ChannelSorted.get("ChannelNumber", "")

            if ChannelSorted['ImageTags']:
                if 'Primary' in ChannelSorted['ImageTags']:
                    tvglogo = f" tvg-logo=\"http://127.0.0.1:57342/picture/{self.EmbyServer.ServerData['ServerId']}/p-{ChannelSorted['Id']}-0-p-{ChannelSorted['ImageTags']['Primary']}\""

            if ChannelNumber:
                tvgchno = f" tvg-chno=\"{ChannelNumber}\""

            if ChannelSorted['Name'].lower().find("radio") != -1 or ChannelSorted['MediaType'] != "Video":
                playlist += f'#EXTINF:-1 tvg-id="{ChannelSorted["Id"]}" tvg-name="{ChannelSorted["Name"]}"{tvglogo}{tvgchno} radio="true" group-title="{Tag}",{ChannelSorted["Name"]}\n'
            else:
                playlist += f'#EXTINF:-1 tvg-id="{ChannelSorted["Id"]}" tvg-name="{ChannelSorted["Name"]}"{tvglogo}{tvgchno} group-title="{Tag}",{ChannelSorted["Name"]}\n'

            playlist += f"http://127.0.0.1:57342/dynamic/{self.EmbyServer.ServerData['ServerId']}/t-{ChannelSorted['Id']}-livetv\n"

        utils.writeFileString(PlaylistFile, playlist)
        EPGFile = self.SyncLiveTVEPG()
        xbmc.log("EMBY.database.library: -->[ iptv simple config change ]", 1) # LOGINFO

        if int(iptvsimpleVersion[:1]) > 1:
            utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')
            ConfigChanged = False
            iptvsimpleConfigFile = f"special://profile/addon_data/pvr.iptvsimple/instance-settings-{str(int(self.EmbyServer.ServerData['ServerId'], 16))[:4]}.xml"
            RebuildConfig = False

            if utils.checkFileExists(iptvsimpleConfigFile):
                iptvsimpleConfig = utils.readFileString(iptvsimpleConfigFile)

                if iptvsimpleConfig.find('<setting id="epgPath"') == -1:
                    RebuildConfig = True
            else: # use iptvsimple config(xml) template
                RebuildConfig = True

            if RebuildConfig:
                iptvsimpleConfig = '<settings version="2">\n    <setting id="kodi_addon_instance_name"></setting>\n    <setting id="m3uPathType" default="true"></setting>\n    <setting id="m3uPath"></setting>\n    <setting id="epgPathType" default="true"></setting>\n    <setting id="epgPath"></setting>\n    <setting id="m3uRefreshMode">2</setting>\n    <setting id="m3uRefreshHour">12</setting>\n</settings>'

            PosStart = iptvsimpleConfig.find('<setting id="kodi_addon_instance_name">')

            if PosStart != -1:
                PosEnd = iptvsimpleConfig.find('</setting>', PosStart)
                CurrentValue = iptvsimpleConfig[PosStart:PosEnd + 10]
                NewValue = f'<setting id="kodi_addon_instance_name">{self.EmbyServer.ServerData["ServerName"]}</setting>'

                if CurrentValue != NewValue:
                    iptvsimpleConfig = iptvsimpleConfig.replace(CurrentValue, NewValue)
                    ConfigChanged = True

            PosStart = iptvsimpleConfig.find('<setting id="m3uPathType"')

            if PosStart != -1:
                PosEnd = iptvsimpleConfig.find('</setting>', PosStart)
                CurrentValue = iptvsimpleConfig[PosStart:PosEnd + 10]
                NewValue = '<setting id="m3uPathType" default="true">0</setting>'

                if CurrentValue != NewValue:
                    iptvsimpleConfig = iptvsimpleConfig.replace(CurrentValue, NewValue)
                    ConfigChanged = True

            PosStart = iptvsimpleConfig.find('<setting id="m3uPath"')

            if PosStart != -1:
                PosEnd = iptvsimpleConfig.find('</setting>', PosStart)
                CurrentValue = iptvsimpleConfig[PosStart:PosEnd + 10]
                NewValue = f'<setting id="m3uPath">{PlaylistFile}</setting>'

                if CurrentValue != NewValue:
                    iptvsimpleConfig = iptvsimpleConfig.replace(CurrentValue, NewValue)
                    ConfigChanged = True

            PosStart = iptvsimpleConfig.find('<setting id="epgPathType"')

            if PosStart != -1:
                PosEnd = iptvsimpleConfig.find('</setting>', PosStart)
                CurrentValue = iptvsimpleConfig[PosStart:PosEnd + 10]
                NewValue = '<setting id="epgPathType" default="true">0</setting>'

                if CurrentValue != NewValue:
                    iptvsimpleConfig = iptvsimpleConfig.replace(CurrentValue, NewValue)
                    ConfigChanged = True

            PosStart = iptvsimpleConfig.find('<setting id="epgPath"')

            if PosStart != -1:
                PosEnd = iptvsimpleConfig.find('</setting>', PosStart)
                CurrentValue = iptvsimpleConfig[PosStart:PosEnd + 10]
                NewValue = f'<setting id="epgPath">{EPGFile}</setting>'

                if CurrentValue != NewValue:
                    iptvsimpleConfig = iptvsimpleConfig.replace(CurrentValue, NewValue)
                    ConfigChanged = True

            if ConfigChanged:
                xbmc.log("EMBY.database.library: Modify iptv simple configuration", 1) # LOGINFO
                utils.writeFileString(iptvsimpleConfigFile, iptvsimpleConfig)
        else:
            utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')
            utils.sleep(3)
            iptvsimple = xbmcaddon.Addon(id="pvr.iptvsimple")
            iptvsimple.setSetting('m3uPathType', "0") # refresh -> the parameter (settings) modification triggers a refresh

            if iptvsimple.getSetting('m3uPath') != PlaylistFile:
                iptvsimple.setSetting('m3uPath', PlaylistFile)

            if iptvsimple.getSetting('epgPathType') != "0":
                iptvsimple.setSetting('epgPathType', "0")

            if iptvsimple.getSetting('epgPath') != EPGFile:
                iptvsimple.setSetting('epgPath', EPGFile)

            utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":false}}')

        utils.sleep(3)
        utils.SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"pvr.iptvsimple","enabled":true}}')
        xbmc.log("EMBY.database.library: --<[ iptv simple config change ]", 1) # LOGINFO

    def SyncLiveTVEPG(self):
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
        xbmc.log("EMBY.database.library: --<[ load EPG ]", 1) # LOGINFO
        return EPGFile

    # Add item_id to userdata queue
    def userdata(self, ItemIds):  # threaded by caller -> websocket via monitor
        if ItemIds:
            embydb = self.open_EmbyDBRW("userdata")

            for ItemId in ItemIds:
                embydb.add_Userdata(str(ItemId))

            self.close_EmbyDBRW("userdata")
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Items):  # threaded by caller
        if Items:
            embydb = self.open_EmbyDBRW("updated")

            for Item in Items:
                embydb.add_UpdateItem(Item[0], Item[1])

            self.close_EmbyDBRW("updated")
            self.worker_update()

    # Add item_id to removed queue
    def removed(self, Ids):  # threaded by caller
        if Ids:
            embydb = self.open_EmbyDBRW("removed")

            for Id in Ids:
                embydb.add_RemoveItem(Id, None)

            self.close_EmbyDBRW("removed")
            self.worker_remove()

def ItemsSort(Items, Reverse):
    # preallocate memory
    ItemsArray = len(Items) * [{}]
    ItemsAudio = ItemsArray.copy()
    ItemsAudioCounter = 0
    ItemsMovie = ItemsArray.copy()
    ItemsMovieCounter = 0
    ItemsBoxSet = ItemsArray.copy()
    ItemsBoxSetCounter = 0
    ItemsMusicVideo = ItemsArray.copy()
    ItemsMusicVideoCounter = 0
    ItemsSeries = ItemsArray.copy()
    ItemsSeriesCounter = 0
    ItemsEpisode = ItemsArray.copy()
    ItemsEpisodeCounter = 0
    ItemsMusicAlbum = ItemsArray.copy()
    ItemsMusicAlbumCounter = 0
    ItemsMusicArtist = ItemsArray.copy()
    ItemsMusicArtistCounter = 0
    ItemsAlbumArtist = ItemsArray.copy()
    ItemsAlbumArtistCounter = 0
    ItemsSeason = ItemsArray.copy()
    ItemsSeasonCounter = 0
    ItemsFolder = ItemsArray.copy()
    ItemsFolderCounter = 0
    del ItemsArray

    for Item in Items:
        if not Item:
            continue

        if Item['Type'] == "Recording":
            if 'MediaType' in Item:
                if Item['IsSeries']:
                    Item['Type'] = 'Episode'
                else:
                    Item['Type'] = 'Movie'

        if Item['Type'] in ('Movie', 'Video', 'SpecialFeature'):
            ItemsMovie[ItemsMovieCounter] = Item
            ItemsMovieCounter += 1
        elif Item['Type'] == 'BoxSet':
            ItemsBoxSet[ItemsBoxSetCounter] = Item
            ItemsBoxSetCounter += 1
        elif Item['Type'] == 'MusicVideo':
            ItemsMusicVideo[ItemsMusicVideoCounter] = Item
            ItemsMusicVideoCounter += 1
        elif Item['Type'] == 'Series':
            ItemsSeries[ItemsSeriesCounter] = Item
            ItemsSeriesCounter += 1
        elif Item['Type'] == 'Episode':
            ItemsEpisode[ItemsEpisodeCounter] = Item
            ItemsEpisodeCounter += 1
        elif Item['Type'] == 'MusicAlbum':
            ItemsMusicAlbum[ItemsMusicAlbumCounter] = Item
            ItemsMusicAlbumCounter += 1
        elif Item['Type'] == 'MusicArtist':
            ItemsMusicArtist[ItemsMusicArtistCounter] = Item
            ItemsMusicArtistCounter += 1
        elif Item['Type'] == 'Audio':
            ItemsAudio[ItemsAudioCounter] = Item
            ItemsAudioCounter += 1
        elif Item['Type'] == 'AlbumArtist':
            ItemsAlbumArtist[ItemsAlbumArtistCounter] = Item
            ItemsAlbumArtistCounter += 1
        elif Item['Type'] == 'Season':
            ItemsSeason[ItemsSeasonCounter] = Item
            ItemsSeasonCounter += 1
        elif Item['Type'] == 'Folder':
            ItemsFolder[ItemsFolderCounter] = Item
            ItemsFolderCounter += 1
        else:
            xbmc.log(f"EMBY.database.library: Type unknown: {Item['Type']} {Item['Id']}", 1) # LOGINFO
            continue

    # remove empty data
    ItemsAudio = ItemsAudio[:ItemsAudioCounter]
    ItemsMusicAlbum = ItemsMusicAlbum[:ItemsMusicAlbumCounter]
    ItemsAlbumArtist = ItemsAlbumArtist[:ItemsAlbumArtistCounter]
    ItemsMusicArtist = ItemsMusicArtist[:ItemsMusicArtistCounter]
    ItemsMusicVideo = ItemsMusicVideo[:ItemsMusicVideoCounter]
    ItemsEpisode = ItemsEpisode[:ItemsEpisodeCounter]
    ItemsSeason = ItemsSeason[:ItemsSeasonCounter]
    ItemsSeries = ItemsSeries[:ItemsSeriesCounter]
    ItemsBoxSet = ItemsBoxSet[:ItemsBoxSetCounter]
    ItemsMovie = ItemsMovie[:ItemsMovieCounter]
    ItemsFolder = ItemsFolder[:ItemsFolderCounter]

    if Reverse:
        return {"music": [ItemsAudio + ItemsMusicAlbum + ItemsAlbumArtist + ItemsMusicArtist], "video": [ItemsMusicVideo, ItemsEpisode + ItemsSeason + ItemsSeries, ItemsBoxSet + ItemsMovie], "folder": [ItemsFolder]}

    return {"music": [ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio], "video": [ItemsMusicVideo, ItemsSeries + ItemsSeason + ItemsEpisode, ItemsMovie + ItemsBoxSet], "folder": [ItemsFolder]}

def content_available(ContentType, CategoryItems):
    if ContentType == "video" and (CategoryItems[0] or CategoryItems[1] or CategoryItems[2]):
        return True

    if CategoryItems[0]:
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

import json
import xbmc
from core import movies, musicvideos, tvshows, music, folder, common
from helper import utils, pluginmenu
from . import dbio

WorkerInProgress = False


class Library:
    def __init__(self, EmbyServer):
        xbmc.log("EMBY.database.library: -->[ library ]", 1) # LOGINFO
        self.EmbyServer = EmbyServer
        self.WhitelistArray = []
        self.Whitelist = {}
        self.LastSyncTime = ""
        self.ContentObject = None
        self.EmbyDBOpen = False
        self.DatabaseInit = False
        self.KodiStartSyncRunning = False

    def open_Worker(self, WorkerName):
        if utils.SystemShutdown:
            return False

        if Worker_is_paused():
            xbmc.log(f"EMBY.database.library: [ worker {WorkerName} sync paused ]", 1) # LOGINFO
            return False

        if WorkerInProgress:
            xbmc.log(f"EMBY.database.library: [ worker {WorkerName} in progress ]", 1) # LOGINFO
            return False

        globals()["WorkerInProgress"] = True

        while not self.DatabaseInit:
            xbmc.log(f"EMBY.database.library: [ worker {WorkerName} wait for database init ]", 1) # LOGINFO

            if utils.sleep(1):
                return False

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

    def load_settings(self):
        # Load essential data and prefetching Media tags
        embydb = self.open_EmbyDBRW("load_settings")

        if embydb.init_EmbyDB():
            self.Whitelist, self.WhitelistArray = embydb.get_Whitelist()
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
        self.DatabaseInit = True

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        xbmc.log("EMBY.database.library: THREAD: --->[ retrieve changes ]", 1) # LOGINFO
        self.KodiStartSyncRunning = True

        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        self.RunJobs()
        UpdateData = []

        if self.LastSyncTime:
            xbmc.log(f"EMBY.database.library: Retrieve changes, last synced: {self.LastSyncTime}", 1) # LOGINFO
            utils.progress_open(utils.Translate(33445))

            for plugin in self.EmbyServer.API.get_plugins():
                if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                    xbmc.log("EMBY.database.library: -->[ Kodi companion ]", 1) # LOGINFO
                    result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

                    if 'ItemsRemoved' in result:
                        self.removed(result['ItemsRemoved'])

                    xbmc.log("EMBY.database.library: --<[ Kodi companion ]", 1) # LOGINFO
                    break

            ProgressBarTotal = len(self.WhitelistArray) / 100
            ProgressBarIndex = 0

            for Whitelist in self.WhitelistArray:
                xbmc.log(f"EMBY.database.library: [ retrieve changes ] {Whitelist[0]} / {Whitelist[1]}", 1) # LOGINFO
                LibraryName = ""
                ProgressBarIndex += 1

                if Whitelist[0] in self.EmbyServer.Views.ViewItems:
                    LibraryName = self.EmbyServer.Views.ViewItems[Whitelist[0]][0]
                    utils.progress_update(int(ProgressBarIndex / ProgressBarTotal), utils.Translate(33445), LibraryName)

                if not LibraryName:
                    xbmc.log(f"EMBY.database.library: [ KodiStartSync remove library {Whitelist[0]} ]", 1) # LOGINFO
                    continue

                if Whitelist[1] == "musicvideos":
                    Content = "MusicVideo,Folder"
                elif Whitelist[1] == "movies":
                    Content = "Movie,Folder"
                elif Whitelist[1] == "homevideos":
                    Content = "Video,Folder"
                elif Whitelist[1] == "tvshows":
                    Content = "Series,Season,Episode,Folder"
                elif Whitelist[1] in ("music", "audiobooks"):
                    Content = "MusicArtist,MusicAlbum,Audio,Folder"
                elif Whitelist[1] == "podcasts":
                    Content = "MusicArtist,MusicAlbum,Audio,Folder"
                else:
                    xbmc.log(f"EMBY.database.library: Skip library type startup sync: {Whitelist[1]}", 1) # LOGINFO
                    continue

                ItemIndex = 0
                UpdateDataTemp = 10000 * [None] # pre allocate memory

                for Item in self.EmbyServer.API.get_Items(Whitelist[0], Content.split(','), True, True, {'MinDateLastSavedForUser': self.LastSyncTime}):
                    if utils.SystemShutdown:
                        utils.progress_close()
                        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ] shutdown 3", 1) # LOGINFO
                        self.KodiStartSyncRunning = False
                        return

                    if ItemIndex >= 10000:
                        UpdateData += UpdateDataTemp
                        UpdateDataTemp = 10000 * [None] # pre allocate memory
                        ItemIndex = 0

                    UpdateDataTemp[ItemIndex] = Item['Id']
                    ItemIndex += 1

                UpdateData += UpdateDataTemp

            utils.progress_close()

        # Update sync update timestamp
        self.set_syncdate(utils.currenttime())

        # iptvsimple update
        if utils.synclivetv:
            utils.SyncLiveTV(False)

        # Run jobs
        xbmc.log("EMBY.database.library: THREAD: ---<[ retrieve changes ]", 1) # LOGINFO
        pluginmenu.reset_querycache()

        if UpdateData:
            UpdateData = list(dict.fromkeys(UpdateData)) # filter doubles

            if None in UpdateData:
                UpdateData.remove(None)

            self.updated(UpdateData)

        self.KodiStartSyncRunning = False

    def worker_userdata(self):
        WorkerName = "worker_userdata"
        ContinueJobs = self.open_Worker(WorkerName)

        if ContinueJobs:
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            UserDataItems = embydb.get_Userdata()
            xbmc.log(f"EMBY.database.library: -->[ worker_userdata started ] queue size: {len(UserDataItems)}", 1) # LOGINFO

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
            UpdateItems = embydb.get_UpdateItem()
            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], WorkerName)
            xbmc.log(f"EMBY.database.library: -->[ worker_update started ] queue size: {len(UpdateItems)}", 1) # LOGINFO

            if not UpdateItems:
                globals()["WorkerInProgress"] = False
                return ContinueJobs
        else:
            return False

        utils.progress_open(utils.Translate(33178))
        RecordsPercent = len(UpdateItems) / 100
        index = 0
        embydb = None
        TempLibraryInfos = []

        if UpdateItems:
            TempLibraryInfos = UpdateItems
            Items = 10000 * [None] # pre allocate memory
            ItemArrayIndex = 0
            self.EmbyServer.API.ProcessProgress["worker_update"] = 0

            for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items_Ids(UpdateItems, ["Everything"], False, False, "worker_update"), 1):
                if ItemArrayIndex >= 10000:
                    self.EmbyServer.API.ProcessProgress["worker_update"] = ItemIndex
                    Continue, index, embydb = self.worker_update_items(embydb, Items, UpdateItems, RecordsPercent, WorkerName, index)

                    if not Continue:
                        self.EmbyServer.API.ProcessProgress["worker_update"] = -1
                        return False

                    Items = 10000 * [None] # pre allocate memory
                    ItemArrayIndex = 0

                Items[ItemArrayIndex] = Item
                ItemArrayIndex += 1

            Continue, index, embydb = self.worker_update_items(embydb, Items, UpdateItems, RecordsPercent, WorkerName, index)

            if not Continue:
                return False

        # Remove not detected Items
        for TempLibraryInfo in TempLibraryInfos:
            if TempLibraryInfo in UpdateItems:
                UpdateItems.remove(TempLibraryInfo)
                embydb.delete_UpdateItem(TempLibraryInfo)

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker(WorkerName)
        xbmc.log("EMBY.database.library: --<[ worker update completed ]", 1) # LOGINFO
        self.RunJobs()
        return True

    def worker_update_items(self, embydb, Items, UpdateItems, RecordsPercent, WorkerName, index):
        Items = list([item for item in Items if item is not None])

        if None in Items:
            Items.remove(None)

        SortedItems = ItemsSort(Items, False)

        if not embydb:
            embydb = self.open_EmbyDBRW(WorkerName)

        for ContentType, CategoryItems in list(SortedItems.items()):
            if content_available(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, WorkerName)

                for ProcessItems in CategoryItems:
                    self.ContentObject = None

                    for Item in ProcessItems:
                        Item['Library'] = {}   #LibraryInfos[Item['Id']]
                        embydb.delete_UpdateItem(Item['Id'])
                        UpdateItems.remove(Item['Id'])
                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), index, Item, embydb, kodidb, ContentType, WorkerName)
                        index += 1

                        if not Continue:
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
            xbmc.log(f"EMBY.database.library: -->[ worker_remove started ] queue size: {len(RemoveItems)}", 1) # LOGINFO

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
        xbmc.log(f"EMBY.database.library: -->[ worker_library started ] queue size: {len(SyncItems)}", 1) # LOGINFO

        if not SyncItems:
            globals()["WorkerInProgress"] = False
            return

        utils.progress_open(f"{utils.Translate(33238)}")
        newContent = utils.newContent
        utils.newContent = False  # Disable new content notification on init sync
        embydb = self.open_EmbyDBRW(WorkerName)
        SyncItemPercent = len(SyncItems) / 100

        for SyncItemIndex, SyncItem in enumerate(SyncItems):
            SyncItemProgress = int(SyncItemIndex / SyncItemPercent)
            utils.progress_update(SyncItemProgress, f"{utils.Translate(33238)}", SyncItem[1])
            embydb.add_Whitelist(SyncItem[0], SyncItem[2], SyncItem[1])
            self.Whitelist[SyncItem[0]] = (SyncItem[2], SyncItem[1])
            kodidb = dbio.DBOpenRW(SyncItem[4], WorkerName)

            if SyncItem[4] == "video":
                common.MediaTags[SyncItem[1]] = kodidb.get_add_tag(SyncItem[1])

            self.ContentObject = None
            self.EmbyServer.API.ProcessProgress["worker_library"] = 0

            # Sync Content
            for ItemIndex, Item in enumerate(self.EmbyServer.API.get_Items(SyncItem[0], [SyncItem[3]], False, True, {}, "worker_library"), 1):
                Item["Library"] = {"Id": SyncItem[0], "Name": SyncItem[1]}
                Continue, embydb, kodidb = self.ItemOps(SyncItemProgress, ItemIndex, Item, embydb, kodidb, SyncItem[4], WorkerName)
                self.EmbyServer.API.ProcessProgress["worker_library"] = ItemIndex

                if not Continue:
                    self.EmbyServer.API.ProcessProgress["worker_library"] = -1
                    return

            dbio.DBCloseRW(SyncItem[4], WorkerName)
            embydb.remove_PendingSync(SyncItem[0], SyncItem[1], SyncItem[2], SyncItem[3], SyncItem[4])

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
        if Worker_is_paused():
            xbmc.log(f"EMBY.database.library: -->[ worker delay {utils.SyncPause}]", 1) # LOGINFO
            dbio.DBCloseRW(ContentCategory, WorkerName)
            dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], WorkerName)
            self.EmbyDBOpen = False

            while Worker_is_paused():
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
            for LibraryId, Value in list(self.Whitelist.items()):
                AddData = {'Id': LibraryId, 'Name': Value[1]}

                if AddData not in libraries:
                    libraries += (AddData,)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()

            for LibraryId in self.Whitelist:
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
                    del self.Whitelist[LibraryId]
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
                            embydb.add_PendingSync(LibraryId, library_name, "movies", "Movie", "video")
                            embydb.add_PendingSync(LibraryId, library_name, "movies", "BoxSet", "video")
                            embydb.add_PendingSync(LibraryId, library_name, 'homevideos', "Video", "video")
                            embydb.add_PendingSync(LibraryId, library_name, 'tvshows', "Series", "video")
                            embydb.add_PendingSync(LibraryId, library_name, 'tvshows', "Season", "video")
                            embydb.add_PendingSync(LibraryId, library_name, 'tvshows', "Episode", "video")
                            embydb.add_PendingSync(LibraryId, library_name, 'music', "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, 'music', "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, 'music', "Audio", "music")
                            embydb.add_PendingSync(LibraryId, library_name, 'musicvideos', "MusicVideo", "video")
                        elif library_type == 'movies':
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Movie", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "BoxSet", "video")
                        elif library_type == 'musicvideos':
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "MusicVideo", "video")
                        elif library_type == 'homevideos':
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Video", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "BoxSet", "video")
                        elif library_type == 'tvshows':
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Series", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Season", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Episode", "video")
                        elif library_type in ('music', 'audiobooks', 'podcasts'):
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Audio", "music")
                            musicdb.add_role()

                        embydb.add_PendingSync(LibraryId, library_name, library_type, "Folder", "folder")
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

        for EmbyLibraryId, Value in list(self.Whitelist.items()):
            if Value[0] == "movies":
                items = embydb.get_item_by_emby_folder_wild_and_EmbyType(EmbyLibraryId, "BoxSet")

                for item in items:
                    embydb.add_RemoveItem(item[0], EmbyLibraryId)

                embydb.add_PendingSync(EmbyLibraryId, Value[1], Value[0], "BoxSet", "video")

        self.close_EmbyDBRW("refresh_boxsets")
        self.worker_remove()
        self.worker_library()

    # Add item_id to userdata queue
    def userdata(self, ItemIds):  # threaded by caller -> websocket via monitor
        if ItemIds:
            embydb = self.open_EmbyDBRW("userdata")

            for ItemId in ItemIds:
                embydb.add_Userdata(str(ItemId))

            self.close_EmbyDBRW("userdata")
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, ItemIds):  # threaded by caller
        if ItemIds:
            embydb = self.open_EmbyDBRW("updated")

            for ItemId in ItemIds:
                embydb.add_UpdateItem(ItemId)

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
    ItemsAudio = len(Items) * [None]
    ItemsAudioCounter = 0
    ItemsMovie = len(Items) * [None]
    ItemsMovieCounter = 0
    ItemsBoxSet = len(Items) * [None]
    ItemsBoxSetCounter = 0
    ItemsMusicVideo = len(Items) * [None]
    ItemsMusicVideoCounter = 0
    ItemsSeries = len(Items) * [None]
    ItemsSeriesCounter = 0
    ItemsEpisode = len(Items) * [None]
    ItemsEpisodeCounter = 0
    ItemsMusicAlbum = len(Items) * [None]
    ItemsMusicAlbumCounter = 0
    ItemsMusicArtist = len(Items) * [None]
    ItemsMusicArtistCounter = 0
    ItemsAlbumArtist = len(Items) * [None]
    ItemsAlbumArtistCounter = 0
    ItemsSeason = len(Items) * [None]
    ItemsSeasonCounter = 0
    ItemsFolder = len(Items) * [None]
    ItemsFolderCounter = 0

    for Item in Items:
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

def Worker_is_paused():
    for Busy in list(utils.SyncPause.values()):
        if Busy:
            xbmc.log(f"EMBY.database.library: Worker_is_paused: {utils.SyncPause}", 1) # LOGINFO
            return True

    return False

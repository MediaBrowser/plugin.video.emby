import json
import xbmc
from core import movies, musicvideos, tvshows, music, folder, common
from helper import utils, loghandler, pluginmenu
from . import dbio

WorkerInProgress = False
LOG = loghandler.LOG('EMBY.database.library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("-->[ library ]")
        self.EmbyServer = EmbyServer
        self.WhitelistArray = []
        self.Whitelist = {}
        self.LastSyncTime = ""
        self.ContentObject = None
        self.EmbyDBOpen = False

    def open_Worker(self, Worker):
        if Worker_is_paused():
            LOG.info("[ worker %s sync paused ]" % Worker)
            return False, []

        if WorkerInProgress:
            LOG.info("[ worker %s in progress ]" % Worker)
            return False, []

        globals()["WorkerInProgress"] = True
        Items = []
        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], Worker)

        if not embydb:
            globals()["WorkerInProgress"] = False
            LOG.info("[ worker %s exit ] database io error")
            return False, []

        if Worker == "userdata":
            Items = embydb.get_Userdata()
        elif Worker == "update":
            Items = embydb.get_UpdateItem()
        elif Worker == "remove":
            Items = embydb.get_RemoveItem()
        elif Worker == "library":
            Items = embydb.get_PendingSync()

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], Worker)

        if not Items:
            globals()["WorkerInProgress"] = False
            LOG.info("[ worker %s exit ] queue size: 0" % Worker)
            return True, []

        LOG.info("-->[ worker %s started ] queue size: %d" % (Worker, len(Items)))
        return True, Items

    def close_Worker(self, TaskId, MusicSynced, VideoSynced):
        self.close_EmbyDBRW(TaskId)
        utils.SyncPause['kodi_rw'] = False

        if VideoSynced and MusicSynced and not utils.useDirectPaths:
            utils.ScanStaggered = True

        if VideoSynced:
            LOG.info("close_Worker: VideoLibrary.Scan initiated. Staggerd: %s" % utils.ScanStaggered)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","params":{"showdialogs":false,"directory":""},"id":1}')

        if MusicSynced and not utils.useDirectPaths and not utils.ScanStaggered:
            LOG.info("close_Worker: AudioLibrary.Scan initiated")
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":""},"id":1}')

        utils.progress_close()
        globals()["WorkerInProgress"] = False

    def open_EmbyDBRW(self, TaskId):
        # if worker in progress, interrupt workers database ops (worker has lower priority) compared to all other Emby database (rw) ops
        if self.EmbyDBOpen:
            if WorkerInProgress:
                utils.SyncPause['priority'] = True

        # wait for DB close
        while self.EmbyDBOpen:
            LOG.info("open_EmbyDBRW waiting: %s" % TaskId)
            utils.sleep(1)

        self.EmbyDBOpen = True
        return dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], TaskId)

    def close_EmbyDBRW(self, TaskId):
        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], TaskId)
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
            return

        videodb = dbio.DBOpenRW("video", "load_settings")

        for ViewItem in list(self.EmbyServer.Views.ViewItems.values()):
            common.MediaTags[ViewItem[0]] = videodb.get_tag(ViewItem[0])

        videodb.init_favorite_tags()
        videodb.add_Index()
        dbio.DBCloseRW("video", "load_settings")
        musicdb = dbio.DBOpenRW("music", "load_settings")
        musicdb.add_Index()
        musicdb.disable_rescan(utils.currenttime_kodi_format())
        dbio.DBCloseRW("music", "load_settings")
        texturedb = dbio.DBOpenRW("texture", "load_settings")
        texturedb.add_Index()
        dbio.DBCloseRW("texture", "load_settings")
        self.LastSyncTime = embydb.get_LastIncrementalSync()
        self.close_EmbyDBRW("load_settings")

    def KodiStartSync(self, Firstrun):  # Threaded by caller -> emby.py
        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        if utils.sleep(5):
            return

        self.RunJobs()
        UpdateData = []

        if self.LastSyncTime:
            LOG.info("-->[ retrieve changes ] %s" % self.LastSyncTime)
            utils.progress_open("Startup sync")

            for plugin in self.EmbyServer.API.get_plugins():
                if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                    LOG.info("-->[ Kodi companion ]")
                    result = self.EmbyServer.API.get_sync_queue(self.LastSyncTime)  # Kodi companion

                    if 'ItemsRemoved' in result:
                        self.removed(result['ItemsRemoved'])

                    LOG.info("--<[ Kodi companion ]")
                    break

            ProgressBarTotal = len(self.WhitelistArray) / 50
            ProgressBarIndex = 0

            for UserSync in (False, True):
                if UserSync:
                    extra = {'MinDateLastSavedForUser': self.LastSyncTime}
                else:
                    extra = {'MinDateLastSaved': self.LastSyncTime}

                for Whitelist in self.WhitelistArray:
                    LOG.info("[ retrieve changes ] %s / %s / %s" % (Whitelist[0], Whitelist[1], UserSync))
                    LibraryName = ""
                    ProgressBarIndex += 1

                    if UserSync:
                        ProgressBarLabel = "Startup sync / userdata"
                    else:
                        ProgressBarLabel = "Startup sync / content"

                    if Whitelist[0] in self.EmbyServer.Views.ViewItems:
                        LibraryName = self.EmbyServer.Views.ViewItems[Whitelist[0]][0]
                        utils.progress_update(int(ProgressBarIndex / ProgressBarTotal), ProgressBarLabel, LibraryName)

                    if not LibraryName:
                        LOG.info("[ KodiStartSync remove library %s ]" % Whitelist[0])
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
                        LOG.info("Skip library type startup sync: %s" % Whitelist[1])
                        continue

                    if utils.SystemShutdown:
                        utils.progress_close()
                        return

                    TotalRecords = self.EmbyServer.API.get_TotalRecordsRegular(Whitelist[0], Content, extra)

                    if TotalRecords:
                        UpdateDataTemp = TotalRecords * [None] # preallocate memory

                        for Index, Item in enumerate(self.EmbyServer.API.get_Items(Whitelist[0], Content.split(','), True, True, extra)):
                            if utils.SystemShutdown:
                                utils.progress_close()
                                return

                            if Index >= TotalRecords: # Emby server updates were in progress. New items were added after TotalRecords was calculated
                                UpdateDataTemp.append(Item['Id'])
                            else:
                                UpdateDataTemp[Index] = Item['Id']

                        UpdateData += UpdateDataTemp

        # Update sync update timestamp
        self.set_syncdate(utils.currenttime())

        # Run jobs
        UpdateData = list(dict.fromkeys(UpdateData)) # filter doubles
        LOG.info("--<[ retrieve changes ]")
        pluginmenu.reset_episodes_cache()
        utils.progress_close()
        self.updated(UpdateData)

    def worker_userdata(self):
        ContinueJobs, UserDataItems = self.open_Worker("userdata")

        if not UserDataItems:
            return ContinueJobs

        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "userdata")
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
                LOG.info("Skip not synced item: %s " % UserDataItem)

        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "userdata")
        UpdateItems = ItemsSort(Items, False)
        embydb = self.open_EmbyDBRW("userdata")
        MusicSynced = False
        VideoSynced = False

        for ItemNotSynced in ItemsNotSynced:
            embydb.delete_Userdata(ItemNotSynced)

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if content_available(ContentType, CategoryItems):
                RecordsPercent = len(CategoryItems) / 100
                kodidb = dbio.DBOpenRW(ContentType, "worker_userdata")

                for Items in CategoryItems:
                    self.ContentObject = None

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_Userdata(Item["UpdateItem"])
                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), Item, embydb, kodidb, ContentType, "userdata")

                        if not Continue:
                            return False

                dbio.DBCloseRW(ContentType, "worker_userdata")

                if ContentType == "music":
                    MusicSynced = True
                else:
                    VideoSynced = True

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker("worker_userdata", MusicSynced, VideoSynced)
        LOG.info("--<[ worker userdata completed ]")
        self.RunJobs()
        return True

    def worker_update(self):
        ContinueJobs, UpdateItems = self.open_Worker("update")

        if not UpdateItems:
            return ContinueJobs

        utils.progress_open(utils.Translate(33178))
        RecordsPercent = len(UpdateItems) / 100
        index = 0
        embydb = self.open_EmbyDBRW("worker_update")
        MusicSynced = False
        VideoSynced = False

        while UpdateItems:
            TempLibraryInfos = UpdateItems[:100]  # Chunks of 100
            Items = self.EmbyServer.API.get_Item(",".join(TempLibraryInfos), ["Everything"], False, False, False)
            SortedItems = ItemsSort(Items, False)

            for ContentType, CategoryItems in list(SortedItems.items()):
                if content_available(ContentType, CategoryItems):
                    kodidb = dbio.DBOpenRW(ContentType, "worker_update")

                    for Items in CategoryItems:
                        self.ContentObject = None

                        for Item in Items:
                            Item['Library'] = {}   #LibraryInfos[Item['Id']]
                            embydb.delete_UpdateItem(Item['Id'])
                            UpdateItems.remove(Item['Id'])
                            Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), Item, embydb, kodidb, ContentType, "add/update")
                            index += 1

                            if not Continue:
                                return False

                    dbio.DBCloseRW(ContentType, "worker_update")

                    if ContentType == "music":
                        MusicSynced = True
                    else:
                        VideoSynced = True

            # Remove not detected Items
            for TempLibraryInfo in TempLibraryInfos:
                if TempLibraryInfo in UpdateItems:
                    UpdateItems.remove(TempLibraryInfo)
                    embydb.delete_UpdateItem(TempLibraryInfo)

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker("worker_update", MusicSynced, VideoSynced)
        LOG.info("--<[ worker update completed ]")
        self.RunJobs()
        return True

    def worker_remove(self):
        ContinueJobs, RemoveItems = self.open_Worker("remove")

        if not RemoveItems:
            return ContinueJobs

        utils.progress_open(utils.Translate(33261))
        RecordsPercent = len(RemoveItems) / 100
        AllRemoveItems = []
        embydb = self.open_EmbyDBRW("remove")

        for index, RemoveItem in enumerate(RemoveItems, 1):
            utils.progress_update(int(index / RecordsPercent), utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = embydb.get_media_by_id(RemoveItem[0])

            if FoundRemoveItems:
                if FoundRemoveItems[0][2] == "Folder":
                    LOG.info("Detect media by folder id %s / % s" % (RemoveItem[0], FoundRemoveItems[0][11]))
                    FoundRemoveItems = embydb.get_media_by_folder(FoundRemoveItems[0][11])

            if not FoundRemoveItems:
                LOG.info("Detect media by parent id %s" % RemoveItem[0])
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
                            LOG.error("worker remove, item not valid %s" % str(RemoveItem))

                AllRemoveItems += TempRemoveItems
                del TempRemoveItems[:] # relese memory
            else:
                embydb.delete_RemoveItem_EmbyId(RemoveItem[0])
                LOG.info("worker remove, item not found in local database %s" % RemoveItem[0])
                continue

        UpdateItems = ItemsSort(AllRemoveItems, True)
        del AllRemoveItems[:] # relese memory
        MusicSynced = False
        VideoSynced = False

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if content_available(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, "worker_remove")

                for Items in CategoryItems:
                    self.ContentObject = None
                    RecordsPercent = len(Items) / 100

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_RemoveItem(Item['Id'], Item['Library']["Id"])
                        Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), Item, embydb, kodidb, ContentType, "remove")

                        if not Continue:
                            return False

                dbio.DBCloseRW(ContentType, "worker_remove")

                if ContentType == "music":
                    MusicSynced = True
                else:
                    VideoSynced = True

        embydb.update_LastIncrementalSync(utils.currenttime())
        self.close_Worker("worker_remove", MusicSynced, VideoSynced)
        LOG.info("--<[ worker remove completed ]")
        self.RunJobs()
        return True

    def worker_library(self):
        _, SyncItems = self.open_Worker("library")

        if not SyncItems:
            return

        MusicSynced = False
        VideoSynced = False
        utils.progress_open("%s %s" % (utils.Translate(33021), utils.Translate(33238)))
        newContent = utils.newContent
        utils.newContent = False  # Disable new content notification on init sync
        embydb = self.open_EmbyDBRW("library")

        for SyncItem in SyncItems:
            embydb.add_Whitelist(SyncItem[0], SyncItem[2], SyncItem[1])
            self.Whitelist[SyncItem[0]] = (SyncItem[2], SyncItem[1])
            kodidb = dbio.DBOpenRW(SyncItem[4], "worker_library")

            if SyncItem[4] == "video":
                common.MediaTags[SyncItem[1]] = kodidb.get_add_tag(SyncItem[1])

            self.ContentObject = None
            RecordsPercent = self.EmbyServer.API.get_TotalRecordsRegular(SyncItem[0], SyncItem[3]) / 100

            # Sync Content
            for index, Item in enumerate(self.EmbyServer.API.get_Items(SyncItem[0], [SyncItem[3]], False, True, {}), 1):
                Item["Library"] = {"Id": SyncItem[0], "Name": SyncItem[1]}
                Continue, embydb, kodidb = self.ItemOps(int(index / RecordsPercent), Item, embydb, kodidb, SyncItem[4], "add/update")

                if not Continue:
                    return

            if SyncItem[4] == "music":
                MusicSynced = True
            else:
                VideoSynced = True

            dbio.DBCloseRW(SyncItem[4], "worker_library")
            embydb.remove_PendingSync(SyncItem[0], SyncItem[1], SyncItem[2], SyncItem[3], SyncItem[4])

        utils.newContent = newContent
        self.EmbyServer.Views.update_nodes()
        pluginmenu.reset_episodes_cache()
        self.close_Worker("worker_library", MusicSynced, VideoSynced)
        xbmc.sleep(1000) # give Kodi time for keep up
        xbmc.executebuiltin('ReloadSkin()')
        LOG.info("Reload skin by worker library")
        LOG.info("--<[ worker library completed ]")

        if not utils.sleep(1):  # give Kodi time to catch up
            self.RunJobs()

    def ItemOps(self, ProgressValue, Item, embydb, kodidb, ContentCategory, Task):
        Ret = False

        if not self.ContentObject:
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        if Task == "add/update":
            if Item['Type'] == "Audio":
                Ret = self.ContentObject.song(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] == "MusicAlbum":
                Ret = self.ContentObject.album(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] in ("MusicArtist", "AlbumArtist"):
                Ret = self.ContentObject.artist(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] in ("Movie", "Video"):
                Ret = self.ContentObject.movie(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] == "BoxSet":
                Ret = self.ContentObject.boxset(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] == "MusicVideo":
                Ret = self.ContentObject.musicvideo(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] == "Episode":
                Ret = self.ContentObject.episode(Item)
                ProgressMsg = "%s / %s / %s" % (Item.get('SeriesName', 'Unknown Seriesname'), Item.get('SeasonName', 'Unknown Seasonname'), Item['Name'])
            elif Item['Type'] == "Season":
                Ret = self.ContentObject.season(Item)
                ProgressMsg = "%s / %s" % (Item['SeriesName'], Item['Name'])
            elif Item['Type'] == "Series":
                Ret = self.ContentObject.tvshow(Item)
                ProgressMsg = Item['Name']
            elif Item['Type'] == "Folder":
                self.ContentObject.folder(Item)

                if "Path" in Item:
                    ProgressMsg = Item['Path']
                elif "Name" in Item:
                    ProgressMsg = Item['Name']
                else:
                    ProgressMsg = "unknown"
            else:
                ProgressMsg = "unknown"

            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], ProgressMsg)

            if Ret and utils.newContent:
                if ContentCategory == "music":
                    MsgTime = int(utils.newmusictime) * 1000
                else:
                    MsgTime = int(utils.newvideotime) * 1000

                utils.Dialog.notification(heading="%s %s" % (utils.Translate(33049), Item['Type']), message=Item['Name'], icon=utils.icon, time=MsgTime, sound=False)
        elif Task == "remove":
            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], str(Item['Id']))
            self.ContentObject.remove(Item)
        elif Task == "userdata":
            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], str(Item['Id']))
            self.ContentObject.userdata(Item)

        # Check if Kodi db or emby is about to open -> close db, wait, reopen db
        if Worker_is_paused():
            LOG.info("-->[ worker delay %s]" % str(utils.SyncPause))
            dbio.DBCloseRW(ContentCategory, "ItemOps")
            dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], "ItemOps")
            self.EmbyDBOpen = False

            while Worker_is_paused():
                if utils.sleep(1):
                    utils.progress_close()
                    LOG.info("[ worker exit (shutdown) ]")
                    return False, None, None

            self.EmbyDBOpen = True
            LOG.info("--<[ worker delay %s]" % str(utils.SyncPause))
            embydb = dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], "ItemOps")
            kodidb = dbio.DBOpenRW(ContentCategory, "ItemOps")
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        Continue = True

        if utils.SystemShutdown:
            dbio.DBCloseRW(ContentCategory, "ItemOps")
            self.close_Worker("ItemOps", False, False)
            LOG.info("[ worker exit ]")
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
        pluginmenu.QueryCache = {}

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
                    LOG.info("---[ removed library: %s ]" % LibraryId)
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

                        LOG.info("---[ added library: %s ]" % LibraryId)
                    else:
                        LOG.info("---[ added library not found: %s ]" % LibraryId)

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
            LOG.info("Type unknown: %s %s" % (Item['Type'], Item['Id']))
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
            LOG.info("Worker_is_paused: %s" % str(utils.SyncPause))
            return True

    return False

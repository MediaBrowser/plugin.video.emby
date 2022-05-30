import json
import xbmc
from core import movies, musicvideos, tvshows, music, common
from helper import utils, loghandler, pluginmenu
from . import dbio

WorkerInProgress = False
LOG = loghandler.LOG('EMBY.database.library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("--->[ library ]")
        self.EmbyServer = EmbyServer
        self.WhitelistArray = []
        self.Whitelist = {}
        self.LastStartSync = ""
        self.LastRealtimeSync = ""
        self.ContentObject = None
        self.EmbyDBOpen = False

    def open_Worker(self, Worker):
        if utils.sync_is_paused():
            LOG.info("[ worker %s sync paused ]" % Worker)
            return False, []

        if WorkerInProgress:
            LOG.info("[ worker %s in progress ]" % Worker)
            return False, []

        globals()["WorkerInProgress"] = True
        Items = []
        embydb = dbio.DBOpenRO(self.EmbyServer.server_id, Worker)

        if Worker == "userdata":
            Items = embydb.get_Userdata()
        elif Worker == "update":
            Items = embydb.get_UpdateItem()
        elif Worker == "remove":
            Items = embydb.get_RemoveItem()
        elif Worker == "library":
            Items = embydb.get_PendingSync()

        dbio.DBCloseRO(self.EmbyServer.server_id, Worker)

        if not Items:
            globals()["WorkerInProgress"] = False
            LOG.info("[ worker %s exit ] queue size: 0" % Worker)
            return True, []

        LOG.info("-->[ worker %s started ] queue size: %d" % (Worker, len(Items)))
        return True, Items

    def close_Worker(self, TaskId):
        utils.progress_close()
        self.close_EmbyDBRW(TaskId)
        globals()["WorkerInProgress"] = False

    def open_EmbyDBRW(self, TaskId):
        # pause if worker (lower priority) is in progress
        if self.EmbyDBOpen:
            if WorkerInProgress:
                utils.DBBusy = True

        # wait for DB close
        while self.EmbyDBOpen:
            LOG.info("open_EmbyDBRW waiting: %s" % TaskId)
            utils.waitForAbort(1)

        self.EmbyDBOpen = True
        return dbio.DBOpenRW(self.EmbyServer.server_id, TaskId)

    def close_EmbyDBRW(self, TaskId):
        dbio.DBCloseRW(self.EmbyServer.server_id, TaskId)
        self.EmbyDBOpen = False
        utils.DBBusy = False

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        embydb = self.open_EmbyDBRW("set_syncdate")
        embydb.update_LastIncrementalSync(TimestampUTC, "realtime")
        embydb.update_LastIncrementalSync(TimestampUTC, "start")
        self.LastRealtimeSync = TimestampUTC
        self.LastStartSync = TimestampUTC
        LastRealtimeSyncLocalTime = utils.convert_to_local(self.LastRealtimeSync)
        utils.set_syncdate(LastRealtimeSyncLocalTime)
        self.close_EmbyDBRW("set_syncdate")

    def load_settings(self):
        # Load essential data and prefetching Media tags
        embydb = self.open_EmbyDBRW("load_settings")
        embydb.init_EmbyDB()
        self.Whitelist, self.WhitelistArray = embydb.get_Whitelist()
        kodidb = dbio.DBOpenRO("video", "load_settings")

        for ViewItem in list(self.EmbyServer.Views.ViewItems.values()):
            common.MediaTags[ViewItem[0]] = kodidb.get_tag(ViewItem[0])

        dbio.DBCloseRO("video", "load_settings")
        videodb = dbio.DBOpenRW("video", "setup")
        videodb.init_favorite_tags()
        dbio.DBCloseRW("video", "setup")
        kodidb = dbio.DBOpenRW("music", "load_settings")
        kodidb.disable_rescan(utils.currenttime_kodi_format())
        dbio.DBCloseRW("music", "load_settings")
        self.LastRealtimeSync = embydb.get_LastIncrementalSync("realtime")
        self.LastStartSync = embydb.get_LastIncrementalSync("start")
        self.close_EmbyDBRW("load_settings")

    def InitSync(self, Firstrun):  # Threaded by caller -> emby.py
        while not utils.StartupComplete:
            if utils.waitForAbort(5):
                return

        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        if utils.SystemShutdown:
            return

        self.RunJobs()
        UpdateData = []

        if self.LastRealtimeSync:
            LOG.info("-->[ retrieve changes ] %s / %s" % (self.LastRealtimeSync, self.LastStartSync))

            for plugin in self.EmbyServer.API.get_plugins():
                if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                    LOG.info("-->[ Kodi companion ]")
                    result = self.EmbyServer.API.get_sync_queue(self.LastRealtimeSync)  # Kodi companion

                    if 'ItemsRemoved' in result:
                        self.removed(result['ItemsRemoved'])

                    LOG.info("--<[ Kodi companion ]")
                    break

            for UserSync in (False, True):
                if UserSync:
                    extra = {'MinDateLastSavedForUser': self.LastRealtimeSync}
                else:
                    extra = {'MinDateLastSaved': self.LastRealtimeSync}

                Content = ""

                for Whitelist in self.WhitelistArray:
                    LOG.info("[ retrieve changes ] %s / %s / %s" % (Whitelist[0], Whitelist[1], UserSync))

                    if Whitelist[0] not in self.EmbyServer.Views.ViewItems:
                        LOG.info("[ InitSync remove library %s ]" % Whitelist[0])
                        continue

                    if Whitelist[1] == "musicvideos":
                        Content = "MusicVideo"
                    elif Whitelist[1] == "movies":
                        Content = "Movie,BoxSet"
                    elif Whitelist[1] == "homevideos":
                        Content = "Video"
                    elif Whitelist[1] == "tvshows":
                        Content = "Series,Season,Episode"
                    elif Whitelist[1] in ("music", "audiobooks"):
                        Content = "MusicArtist,MusicAlbum,Audio"
                    elif Whitelist[1] == "podcasts":
                        Content = "MusicArtist,MusicAlbum,Audio"

                    if utils.SystemShutdown:
                        return

                    TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(Whitelist[0], Content, extra))

                    if TotalRecords:
                        UpdateDataTemp = TotalRecords * [(None, None, None, None)] # preallocate memory

                        for Index, Item in enumerate(self.EmbyServer.API.get_Items(Whitelist[0], Content.split(','), True, True, extra, False, False)):
                            UpdateDataTemp[Index] = (Item['Id'], Whitelist[0], Whitelist[2], Item['Type'])

                        UpdateData += UpdateDataTemp

        # Update sync update timestamp
        self.set_syncdate(utils.currenttime())

        # Run jobs
        UpdateData = list(dict.fromkeys(UpdateData)) # filter doplicates
        LOG.info("--<[ retrieve changes ]")
        pluginmenu.reset_episodes_cache()
        self.updated(UpdateData)

    # Get items from emby and place them in the appropriate queues
    # No progress bar needed, it's all internal and damn fast
    def worker_userdata(self):
        ContinueJobs, UserDataItems = self.open_Worker("userdata")

        if not UserDataItems:
            return ContinueJobs

        embydb = dbio.DBOpenRO(self.EmbyServer.server_id, "userdata")
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

        dbio.DBCloseRO(self.EmbyServer.server_id, "userdata")
        UpdateItems = ItemsSort(Items, False)
        embydb = self.open_EmbyDBRW("userdata")

        for ItemNotSynced in ItemsNotSynced:
            embydb.delete_Userdata(ItemNotSynced)

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if refresh_check(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, "worker_userdata")
                TotalRecords = len(CategoryItems)

                for Items in CategoryItems:
                    self.ContentObject = None

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_Userdata(Item["UpdateItem"])
                        Continue, embydb, kodidb = self.ItemOps(index, TotalRecords, Item, embydb, kodidb, ContentType, "userdata")

                        if not Continue:
                            return False

                close_KodiDatabase(ContentType, "userdata")

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_Worker("worker_userdata")
        LOG.info("--<[ worker userdata completed ]")
        self.RunJobs()
        return True

    def worker_update(self):
        ContinueJobs, UpdateItems = self.open_Worker("update")

        if not UpdateItems:
            return ContinueJobs

        utils.progress_open(utils.Translate(33178))
        LibraryInfos = {}

        for UpdateItem in UpdateItems:
            Id = UpdateItem[0]

            if UpdateItem[1]:  # Fastsync update
                LibraryInfos[str(Id)] = {"Id": UpdateItem[1], "Name": UpdateItem[2]}
            else:  # Realtime update
                LibraryInfos[str(Id)] = {}

        TotalRecords = len(LibraryInfos)
        index = 0
        embydb = self.open_EmbyDBRW("worker_update")

        while LibraryInfos:
            TempLibraryInfos = list(LibraryInfos.keys())[:100]  # Chunks of 100
            Items = self.EmbyServer.API.get_Item(",".join(TempLibraryInfos), ["Everything"], False, False, False)
            UpdateItems = ItemsSort(Items, False)

            for ContentType, CategoryItems in list(UpdateItems.items()):
                if refresh_check(ContentType, CategoryItems):
                    kodidb = dbio.DBOpenRW(ContentType, "worker_update")

                    for Items in CategoryItems:
                        self.ContentObject = None

                        for Item in Items:
                            Item['Library'] = LibraryInfos[Item['Id']]
                            embydb.delete_UpdateItem(Item['Id'])
                            del LibraryInfos[Item['Id']]
                            Continue, embydb, kodidb = self.ItemOps(index, TotalRecords, Item, embydb, kodidb, ContentType, "add/update")
                            index += 1

                            if not Continue:
                                return False

                    close_KodiDatabase(ContentType, "worker_update")

            # Remove not detected Items
            for TempLibraryInfo in TempLibraryInfos:
                if TempLibraryInfo in LibraryInfos:
                    del LibraryInfos[TempLibraryInfo]
                    embydb.delete_UpdateItem(TempLibraryInfo)

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_Worker("worker_update")
        LOG.info("--<[ worker update completed ]")
        self.RunJobs()
        return True

    def worker_remove(self):
        ContinueJobs, RemoveItems = self.open_Worker("remove")

        if not RemoveItems:
            return ContinueJobs

        utils.progress_open(utils.Translate(33261))
        TotalRecords = len(RemoveItems)
        AllRemoveItems = []
        embydb = self.open_EmbyDBRW("remove")

        for index, RemoveItem in enumerate(RemoveItems, 1):
            ProgressValue = int(float(index) / float(TotalRecords) * 100)
            utils.progress_update(ProgressValue, utils.Translate(33261), str(RemoveItem[0]))
            FoundRemoveItems = embydb.get_media_by_id(RemoveItem[0])

            if not FoundRemoveItems:
                LOG.info("Detect media by parent id %s" % RemoveItem[0])
                FoundRemoveItems = embydb.get_media_by_parent_id(RemoveItem[0])

            if FoundRemoveItems:
                TempRemoveItems = []

                for FoundRemoveItem in FoundRemoveItems:
                    LibraryIds = FoundRemoveItem[1].split(";")

                    if len(LibraryIds) > 1: # music content
                        TempRemoveItems.append({'Id': FoundRemoveItem[0], 'Type': FoundRemoveItem[2], 'Library': {'Multi': FoundRemoveItem[1]}, 'DeleteByLibraryId': RemoveItem[1], 'KodiItemId': FoundRemoveItem[4], 'KodiFileId': FoundRemoveItem[5], 'KodiParentId': FoundRemoveItem[7], 'PresentationUniqueKey': FoundRemoveItem[9]})
                    else:
                        TempRemoveItems.append({'Id': FoundRemoveItem[0], 'Type': FoundRemoveItem[2], 'Library': {"Id": FoundRemoveItem[1], "Name": self.EmbyServer.Views.ViewItems[FoundRemoveItem[1]][0]}, 'DeleteByLibraryId': RemoveItem[1], 'KodiItemId': FoundRemoveItem[4], 'KodiFileId': FoundRemoveItem[5], 'KodiParentId': FoundRemoveItem[7], 'PresentationUniqueKey': FoundRemoveItem[9]})

                AllRemoveItems += TempRemoveItems
                del TempRemoveItems[:] # relese memory
            else:
                embydb.delete_RemoveItem(RemoveItem[0])
                LOG.info("worker remove, item not found in local database %s" % RemoveItem[0])
                continue

        UpdateItems = ItemsSort(AllRemoveItems, True)
        del AllRemoveItems[:] # relese memory

        for ContentType, CategoryItems in list(UpdateItems.items()):
            if refresh_check(ContentType, CategoryItems):
                kodidb = dbio.DBOpenRW(ContentType, "worker_remove")

                for Items in CategoryItems:
                    self.ContentObject = None
                    TotalRecords = len(Items)

                    for index, Item in enumerate(Items, 1):
                        embydb.delete_RemoveItem(Item['Id'])
                        Continue, embydb, kodidb = self.ItemOps(index, TotalRecords, Item, embydb, kodidb, ContentType, "remove")

                        if not Continue:
                            return False

                if ContentType == "music":
                    kodidb.clean_music()

                close_KodiDatabase(ContentType, "remove")

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_Worker("worker_remove")
        LOG.info("--<[ worker remove completed ]")
        self.RunJobs()
        return True

    def worker_library(self):
        _, SyncItems = self.open_Worker("library")

        if not SyncItems:
            return

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
            TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(SyncItem[0], SyncItem[3]))

            for index, Item in enumerate(self.EmbyServer.API.get_Items(SyncItem[0], [SyncItem[3]], False, True, {}, False, False), 1):
                Item["Library"] = {"Id": SyncItem[0], "Name": SyncItem[1]}
                Continue, embydb, kodidb = self.ItemOps(index, TotalRecords, Item, embydb, kodidb, SyncItem[4], "add/update")

                if not Continue:
                    utils.newContent = newContent
                    return

            dbio.DBCommitRW(self.EmbyServer.server_id)
            close_KodiDatabase(SyncItem[4], "library")
            embydb.remove_PendingSync(SyncItem[0], SyncItem[1], SyncItem[2], SyncItem[3], SyncItem[4])

        utils.newContent = newContent
        self.EmbyServer.Views.update_nodes()
        pluginmenu.reset_episodes_cache()
        self.close_Worker("worker_library")
        LOG.info("--<[ worker library completed ]")
        xbmc.executebuiltin('ReloadSkin()')
        utils.waitForAbort(1)  # give Kodi time to catch up
        self.RunJobs()

    def ItemOps(self, index, TotalRecords, Item, embydb, kodidb, ContentCategory, Task):
        Ret = False

        if not self.ContentObject:
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        ProgressValue = int(float(index) / float(TotalRecords) * 100)

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
            else:
                ProgressMsg = "unkown"

            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], ProgressMsg)

            if Ret and utils.newContent:
                if ContentCategory == "music":
                    MsgTime = int(utils.newmusictime) * 1000
                else:
                    MsgTime = int(utils.newvideotime) * 1000

                utils.dialog("notification", heading="%s %s" % (utils.Translate(33049), Item['Type']), message=Item['Name'], icon=utils.icon, time=MsgTime, sound=False)
        elif Task == "remove":
            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], str(Item['Id']))
            self.ContentObject.remove(Item)
        elif Task == "userdata":
            utils.progress_update(ProgressValue, "Emby: %s" % Item['Type'], str(Item['Id']))
            self.ContentObject.userdata(Item)

        # Check if Kodi db or emby is about to open -> close db, wait, reopen db
        if utils.DBBusy or utils.sync_is_paused():
            LOG.info("-->[ worker delay %s/%s]" % (utils.DBBusy, str(utils.SyncPause)))
            dbio.DBCloseRW(ContentCategory, "ItemOps")
            dbio.DBCloseRW(self.EmbyServer.server_id, "ItemOps")
            self.EmbyDBOpen = False

            while utils.DBBusy or utils.sync_is_paused():
                utils.waitForAbort(1)

            self.EmbyDBOpen = True
            LOG.info("--<[ worker delay %s/%s]" % (utils.DBBusy, str(utils.SyncPause)))
            embydb = dbio.DBOpenRW(self.EmbyServer.server_id, "ItemOps")
            kodidb = dbio.DBOpenRW(ContentCategory, "ItemOps")
            self.load_libraryObject(Item['Type'], embydb, kodidb)

        Continue = True

        if utils.SystemShutdown:
            dbio.DBCloseRW(ContentCategory, "ItemOps")
            self.close_Worker("ItemOps")
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

        if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
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
        selection = utils.dialog("multi", utils.Translate(33120), choices)

        if not selection:
            return

        # "All" selected
        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
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
                    ViewData = self.EmbyServer.Views.ViewItems[LibraryId]
                    videodb.delete_tag(ViewData[0])
                    items = embydb.get_item_by_emby_folder_wild(LibraryId)

                    for item in items:
                        embydb.add_RemoveItem(item[0], ";".join(remove_librarys))

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
                        elif library_type == 'tvshows':
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Series", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Season", "video")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Episode", "video")
                        elif library_type in ('music', 'audiobooks', 'podcasts'):
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "MusicArtist", "music")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "MusicAlbum", "music")
                            embydb.add_PendingSync(LibraryId, library_name, library_type, "Audio", "music")
                            musicdb.add_role()

                        LOG.info("---[ added library: %s ]" % LibraryId)
                    else:
                        LOG.info("---[ added library not found: %s ]" % LibraryId)

            self.close_EmbyDBRW("select_libraries")
            dbio.DBCloseRW("video", "select_libraries")
            dbio.DBCloseRW("music", "select_libraries")

            if remove_librarys:
                self.worker_remove()

            if add_librarys:
                self.worker_library()

    def refresh_boxsets(self):  # threaded by caller
        embydb = self.open_EmbyDBRW("refresh_boxsets")
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')

        for EmbyLibraryId, Value in list(self.Whitelist.items()):
            if Value[0] == "movies":
                embydb.add_PendingSync(EmbyLibraryId, Value[1], Value[0], "BoxSet", "video")

        self.close_EmbyDBRW("refresh_boxsets")
        self.worker_library()

    # Add item_id to userdata queue
    def userdata(self, Data):  # threaded by caller -> websocket via monitor
        if Data:
            embydb = self.open_EmbyDBRW("userdata")

            for item in Data:
                embydb.add_Userdata(str(item))

            self.close_EmbyDBRW("userdata")
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Data):  # threaded by caller
        if Data:
            embydb = self.open_EmbyDBRW("updated")

            for item in Data:
                if item[0] and item[0].isnumeric():
                    embydb.add_UpdateItem(item[0], item[1], item[2], item[3])
                else:
                    LOG.info("Skip invalid update item: %s" % item[0])

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

    if Reverse:
        return {"music": [ItemsAudio + ItemsMusicAlbum + ItemsAlbumArtist + ItemsMusicArtist], "video": [ItemsMusicVideo, ItemsEpisode + ItemsSeason + ItemsSeries, ItemsBoxSet + ItemsMovie]}

    return {"music": [ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio], "video": [ItemsMusicVideo, ItemsSeries + ItemsSeason + ItemsEpisode, ItemsMovie + ItemsBoxSet]}


def refresh_check(ContentType, CategoryItems):
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

def close_KodiDatabase(ContentType, WorkerId):
    dbio.DBCloseRW(ContentType, WorkerId)

#    if ContentType == "video":
#        xbmc.executebuiltin('UpdateLibrary(video)')
#    elif ContentType == "music" and not utils.useDirectPaths:
#        xbmc.executebuiltin('UpdateLibrary(music)')

    if ContentType == "video":
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","params":{"showdialogs":false,"directory":""},"id":1}')
    elif ContentType == "music" and not utils.useDirectPaths:
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":""},"id":1}')

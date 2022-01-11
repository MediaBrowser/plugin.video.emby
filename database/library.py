# -*- coding: utf-8 -*-
import json
import xbmc
import xbmcgui
from core import movies
from core import musicvideos
from core import tvshows
from core import music
from helper import loghandler
from helper import utils
from . import dbio

XbmcMonitor = xbmc.Monitor()
MediaEmbyMappedSubContent = {"movies": "Movie", "boxsets": "BoxSet", "musicvideos": "MusicVideo", "tvshows": "Series", "music": "Music", "homevideos": "Video", "audiobooks": "Audio"}
LOG = loghandler.LOG('EMBY.database.library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("--->[ library ]")
        self.EmbyServer = EmbyServer
        self.Whitelist = {}
        self.LastStartSync = ""
        self.LastRealtimeSync = ""
        self.EmbyDBWritePriority = False
        self.ContentObject = None

    def wait_EmbyDBWritePriority(self, TaskId):
        if self.EmbyDBWritePriority:
            LOG.info("-->[ %s: Wait for priority workers finished ]" % TaskId)

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            LOG.info("--<[ %s: Wait for priority workers finished ]" % TaskId)

    def open_EmbyDBWorker(self, Worker):
        if utils.SyncPause:
            LOG.info("[ worker %s sync paused ]" % Worker)
            return None, False, None, None

        if utils.WorkerInProgress:
            LOG.info("[ worker %s in progress ]" % Worker)
            return None, False, None, None

        self.wait_EmbyDBWritePriority("Worker")

        # verify again in case multithread has started simultan while waiting for EmbyDBWritePriority
        if utils.SyncPause:
            LOG.info("[ worker %s sync paused ]" % Worker)
            return None, False, None, None

        if utils.WorkerInProgress:
            LOG.info("[ worker %s in progress ]" % Worker)
            return None, False, None, None

        utils.WorkerInProgress = True
        embydb = dbio.DBOpen(self.EmbyServer.server_id)

        if Worker == "userdata":
            Items = embydb.get_Userdata()
        elif Worker == "update":
            Items = embydb.get_UpdateItem()
        elif Worker == "remove":
            Items = embydb.get_RemoveItem()
        elif Worker == "library":
            Items = embydb.get_PendingSync()

        if not Items:
            self.close_EmbyDBWorker(False, None, "[ worker %s exit ] queue size: 0" % Worker)
            return None, True, None, None

        LOG.info("-->[ worker %s started ] queue size: %d" % (Worker, len(Items)))
        return embydb, True, xbmcgui.DialogProgressBG(), Items

    def close_EmbyDBWorker(self, Commit, progress_updates, LogInfo):
        if progress_updates:
            progress_updates.close()

        dbio.DBClose(self.EmbyServer.server_id, Commit)
        utils.WorkerInProgress = False
        LOG.info(LogInfo)

    def open_EmbyDBPriority(self):
        self.wait_EmbyDBWritePriority("Priority")
        self.EmbyDBWritePriority = True

        if utils.WorkerInProgress:
            LOG.info("-->[ Wait for workers paused ]")

            while not utils.WorkerPaused and utils.WorkerInProgress:
                xbmc.sleep(500)

            LOG.info("--<[ Wait for workers paused ]")

        return dbio.DBOpen(self.EmbyServer.server_id)

    def close_EmbyDBPriority(self):
        dbio.DBClose(self.EmbyServer.server_id, True)
        self.EmbyDBWritePriority = False

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        embydb = self.open_EmbyDBPriority()
        embydb.update_LastIncrementalSync(TimestampUTC, "realtime")
        embydb.update_LastIncrementalSync(TimestampUTC, "start")
        self.LastRealtimeSync = TimestampUTC
        self.LastStartSync = TimestampUTC
        LastRealtimeSyncLocalTime = utils.convert_to_local(self.LastRealtimeSync)
        utils.set_syncdate(LastRealtimeSyncLocalTime)
        self.close_EmbyDBPriority()

    def load_settings(self):
        # Load previous sync information
        embydb = self.open_EmbyDBPriority()
        embydb.init_EmbyDB()
        self.Whitelist = embydb.get_Whitelist()
        self.LastRealtimeSync = embydb.get_LastIncrementalSync("realtime")
        self.LastStartSync = embydb.get_LastIncrementalSync("start")
        self.close_EmbyDBPriority()

    def InitSync(self, Firstrun):  # Threaded by caller -> emby.py
        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        self.RunJobs()

        if utils.SystemShutdown:
            return

        KodiCompanion = False
        RemovedItems = []
        UpdateData = []

        for plugin in self.EmbyServer.API.get_plugins():
            if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                KodiCompanion = True
                break

        LOG.info("[ Kodi companion: %s ]" % KodiCompanion)

        if self.LastRealtimeSync:
            Items = {}
            LOG.info("-->[ retrieve changes ] %s / %s" % (self.LastRealtimeSync, self.LastStartSync))

            for UserSync in (False, True):
                for LibraryId, Value in list(self.Whitelist.items()):
                    LOG.info("[ retrieve changes ] %s / %s / %s" % (LibraryId, Value[0], UserSync))

                    if LibraryId not in self.EmbyServer.Views.ViewItems:
                        LOG.info("[ InitSync remove library %s ]" % LibraryId)
                        continue

                    if Value[0] == "musicvideos":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicVideo", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "movies":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Movie,BoxSet", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "homevideos":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Video", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "tvshows":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Series,Season,Episode", self.LastRealtimeSync, UserSync)
                    elif Value[0] in ("music", "audiobooks"):
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "podcasts":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastStartSync, UserSync)

                    if 'Items' in Items:
                        ItemCounter = 0
                        ItemTemp = len(Items['Items']) * [(None, None, None, None)]  # allocate memory for array (much faster than append each item)

                        for item in Items['Items']:
                            ItemData = (item['Id'], LibraryId, Value[1], item['Type'])

                            if ItemData not in UpdateData:
                                ItemTemp[ItemCounter] = ItemData
                                ItemCounter += 1

                        UpdateData += ItemTemp

            UpdateData = list(_f for _f in UpdateData if _f)

            if KodiCompanion:
                result = self.EmbyServer.API.get_sync_queue(self.LastRealtimeSync, None)  # Kodi companion

                if 'ItemsRemoved' in result:
                    RemovedItems = result['ItemsRemoved']

        # Update sync update timestamp
        self.set_syncdate(utils.currenttime())

        # Run jobs
        self.removed(RemovedItems)
        self.updated(UpdateData)
        LOG.info("--<[ retrieve changes ]")

    # Get items from emby and place them in the appropriate queues
    # No progress bar needed, it's all internal an damn fast
    def worker_userdata(self):
        embydb, ReturnValue, progress_updates, UserDataItems = self.open_EmbyDBWorker("userdata")

        if not embydb:
            return ReturnValue

        progress_updates.create("Emby", utils.Translate(33178))
        isMusic = False
        isVideo = False
        MusicItems = []
        VideoItems = []
        index = 0

        # Group items
        for UserDataItem in UserDataItems:
            UserDataItem = StringToDict(UserDataItem[0])
            e_item = embydb.get_item_by_id(UserDataItem['ItemId'])

            if not e_item: #not synced item
                LOG.info("worker userdata, item not found in local database %s" % UserDataItem['ItemId'])
                embydb.delete_Userdata(str(UserDataItem))
                continue

            if e_item[5] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                MusicItems.append((UserDataItem, e_item, e_item[5]))
            elif e_item[5] == "SpecialFeature":
                LOG.info("worker userdata, skip special feature %s" % UserDataItem['ItemId'])
                embydb.delete_Userdata(str(UserDataItem))
                continue
            else:
                VideoItems.append((UserDataItem, e_item, e_item[5]))

        if MusicItems:
            kodidb = dbio.DBOpen("music")
            isMusic = True
            self.ContentObject = None
            TotalRecords = len(MusicItems)

            for MusicItem in MusicItems:
                index += 1
                embydb.delete_Userdata(str(MusicItem[0]))
                Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, MusicItem[1], MusicItem[0], embydb, kodidb, MusicItem[2], "music", "userdata")

                if not Continue:
                    return False

            dbio.DBClose("music", True)

        if VideoItems:
            kodidb = dbio.DBOpen("video")
            isVideo = True
            self.ContentObject = None
            TotalRecords = len(VideoItems)

            for VideoItem in VideoItems:
                index += 1
                embydb.delete_Userdata(str(VideoItem[0]))
                Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, VideoItem[1], VideoItem[0], embydb, kodidb, VideoItem[2], "video", "userdata")

                if not Continue:
                    return False

            dbio.DBClose("video", True)

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_EmbyDBWorker(True, progress_updates, "--<[ worker userdata completed ]")

        if isMusic and not utils.useDirectPaths:
            wait_LibraryRefresh("music", "userdata")

        if isVideo:
            wait_LibraryRefresh("video", "userdata")

        self.RunJobs()
        return True

    def worker_update(self):
        embydb, ReturnValue, progress_updates, UpdateItems = self.open_EmbyDBWorker("update")

        if not embydb:
            return ReturnValue

        progress_updates.create("Emby", utils.Translate(33178))
        TotalRecords = len(UpdateItems)
        QueryUpdateItems = {}
        isMusic = False
        isVideo = False
        index = 0

        for UpdateItem in UpdateItems:
            Id = UpdateItem[0]

            if UpdateItem[1]:  # Fastsync update
                QueryUpdateItems[str(Id)] = {"Id": UpdateItem[1], "Name": UpdateItem[2]}
            else:  # Realtime update
                QueryUpdateItems[str(Id)] = None

        # Load data from Emby server and cache them to minimize Kodi db open time
        while QueryUpdateItems:
            TempQueryUpdateItems = list(QueryUpdateItems.keys())[:int(utils.limitIndex)]
            Items = self.EmbyServer.API.get_item_library(",".join(TempQueryUpdateItems))

            if 'Items' in Items:
                Items = Items['Items']
                ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason = ItemsSort(Items, QueryUpdateItems)
                ItemsTVShows = ItemsSeries + ItemsSeason + ItemsEpisode
                ItemsMovies = ItemsMovie + ItemsBoxSet
                ItemsAudio = ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio

                if ItemsTVShows or ItemsMovies or ItemsMusicVideo:
                    kodidb = dbio.DBOpen("video")

                    for Items in (ItemsTVShows, ItemsMovies, ItemsMusicVideo):
                        self.ContentObject = None

                        for Item, LibraryData, ContentType in Items:
                            index += 1
                            embydb.delete_UpdateItem(Item['Id'])
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, ContentType, "video", "add/update")

                            if not Continue:
                                return False

                            del QueryUpdateItems[Item['Id']]

                    dbio.DBClose("video", True)
                    isVideo = True

                if ItemsAudio:
                    kodidb = dbio.DBOpen("music")
                    self.ContentObject = None

                    for Item, LibraryData, ContentType in ItemsAudio:
                        index += 1
                        embydb.delete_UpdateItem(Item['Id'])
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, ContentType, "music", "add/update")

                        if not Continue:
                            return False

                        del QueryUpdateItems[Item['Id']]

                    kodidb.clean_music()
                    dbio.DBClose("music", True)
                    isMusic = True

            for QueryUpdateItemId in TempQueryUpdateItems:
                if QueryUpdateItemId in QueryUpdateItems:
                    del QueryUpdateItems[QueryUpdateItemId]
                    index += 1
                    embydb.delete_UpdateItem(QueryUpdateItemId)

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_EmbyDBWorker(True, progress_updates, "--<[ worker update completed ]")

        if isMusic and not utils.useDirectPaths:
            wait_LibraryRefresh("music", "update")

        if isVideo:
            wait_LibraryRefresh("video", "update")

        self.RunJobs()
        return True

    def worker_remove(self):
        embydb, ReturnValue, progress_updates, RemoveItems = self.open_EmbyDBWorker("remove")

        if not embydb:
            return ReturnValue

        progress_updates.create("Emby", utils.Translate(33261))
        TotalRecords = len(RemoveItems)
        isMusic = False
        isVideo = False

        #Sort Items
        AllRemoveItems = []
        QueryUpdateItems = {}
        index = 0

        for RemoveItem in RemoveItems:
            Id = RemoveItem[0]
            LibraryId = RemoveItem[2]
            index += 1
            ProgressValue = int(float(index) / float(TotalRecords) * 100)
            progress_updates.update(ProgressValue, heading=utils.Translate(33261), message=str(Id))
            FoundRemoveItems = embydb.get_media_by_id(Id)

            if not FoundRemoveItems:
                LOG.info("Detect media by folder id %s" % Id)
                FoundRemoveItems = embydb.get_media_by_parent_id(Id)
                embydb.delete_RemoveItem(Id)

            if FoundRemoveItems:
                for FoundRemoveItem in FoundRemoveItems:
                    QueryUpdateItems[FoundRemoveItem[0]] = {"Id": FoundRemoveItem[4], "ForceRemoval": bool(LibraryId)}
                    AllRemoveItems.append({'Id': FoundRemoveItem[0], 'Type': FoundRemoveItem[1], 'IsSeries': 'unknown'})
            else:
                LOG.info("worker remove, item not found in local database %s" % Id)
                continue

        ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason = ItemsSort(AllRemoveItems, QueryUpdateItems)
        index = 0
        ItemsTVShows = ItemsSeries + ItemsSeason + ItemsEpisode
        ItemsMovies = ItemsMovie + ItemsBoxSet
        ItemsAudio = ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio

        if ItemsTVShows or ItemsMovies or ItemsMusicVideo:
            kodidb = dbio.DBOpen("video")

            for Items in (ItemsTVShows, ItemsMovies, ItemsMusicVideo):
                self.ContentObject = None

                for Item, _, ContentType in Items:
                    index += 1
                    embydb.delete_RemoveItem(Item['Id'])
                    Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item['Id'], QueryUpdateItems[Item['Id']]["ForceRemoval"], embydb, kodidb, ContentType, "video", "remove")

                    if not Continue:
                        return False

                    del QueryUpdateItems[Item['Id']]

            dbio.DBClose("video", True)
            isVideo = True

        if ItemsAudio:
            kodidb = dbio.DBOpen("music")
            self.ContentObject = None

            for Item, _, ContentType in ItemsAudio:
                index += 1
                LibraryIds = QueryUpdateItems[Item['Id']]["Id"].split(";")

                for LibraryId in LibraryIds:
                    Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item['Id'], LibraryId, embydb, kodidb, ContentType, "music", "remove")
                    embydb.delete_RemoveItem(Item['Id'])

                    if not Continue:
                        return False

                del QueryUpdateItems[Item['Id']]

            kodidb.clean_music()
            dbio.DBClose("music", True)
            isMusic = True

        # remove not found items
        for QueryUpdateItem in QueryUpdateItems:
            embydb.delete_RemoveItem(QueryUpdateItem)

        embydb.update_LastIncrementalSync(utils.currenttime(), "realtime")
        self.close_EmbyDBWorker(True, progress_updates, "--<[ worker remove completed ]")

        if isMusic and not utils.useDirectPaths:
            wait_LibraryRefresh("music", "remove")

        if isVideo:
            wait_LibraryRefresh("video", "remove")

        self.RunJobs()
        return True

    def worker_library(self):
        embydb, _, progress_updates, SyncItems = self.open_EmbyDBWorker("library")

        if not embydb:
            return

        progress_updates.create("Emby", "%s %s" % (utils.Translate(33021), utils.Translate(33238)))

        for SyncItem in SyncItems:
            if utils.SyncPause:
                self.close_EmbyDBWorker(True, progress_updates, "[ worker library paused ]")
                return

            isMusic = False
            isVideo = False
            library_id = SyncItem[0]
            library_type = SyncItem[1]
            library_name = SyncItem[2]
            LibraryData = {"Id": library_id, "Name": library_name}
            embydb.add_Whitelist(library_id, library_type, library_name)
            self.Whitelist[library_id] = (library_type, library_name)

            if SyncItem[3]:
                RestorePoint = StringToDict(SyncItem[3])
            else:
                RestorePoint = {}

            if library_type in ('movies', 'musicvideos', 'boxsets', 'homevideos'):
                isVideo = True
                SubContent = MediaEmbyMappedSubContent[library_type]
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, SubContent))
                index = int(RestorePoint.get('StartIndex', 0))
                kodidb = dbio.DBOpen("video")
                self.ContentObject = None

                for items in self.EmbyServer.API.get_itemsSync(library_id, SubContent, False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for Item in items['Items']:
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, MediaEmbyMappedSubContent[library_type], "video", "add/update")

                        if not Continue:
                            return

                dbio.DBClose("video", True)
            elif library_type == 'tvshows':  # stacked sync: tv-shows -> season/episode
                isVideo = True
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "Series"))
                index = int(RestorePoint.get('StartIndex', 0))
                kodidb = dbio.DBOpen("video")
                self.ContentObject = None

                for items in self.EmbyServer.API.get_itemsSync(library_id, 'Series', False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for tvshow in items['Items']:
                        Seasons = []
                        Episodes = []
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, tvshow, LibraryData, embydb, kodidb, "Series", "video", "add/update")

                        if not Continue:
                            return

                        for itemsContent in self.EmbyServer.API.get_itemsSync(tvshow['Id'], "Season,Episode", False, {}):
                            # Sort
                            for item in itemsContent['Items']:
                                if item["Type"] == "Season":
                                    Seasons.append(item)
                                else:
                                    Episodes.append(item)

                        for Season in Seasons:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Season, LibraryData, embydb, kodidb, "Season", "video", "add/update")

                            if not Continue:
                                return

                        for Episode in Episodes:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Episode, LibraryData, embydb, kodidb, "Episode", "video", "add/update")

                            if not Continue:
                                return

                dbio.DBClose("video", True)
            elif library_type == 'music':  #  Sync only if artist is valid - staggered sync (performance)
                isMusic = True
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "MusicArtist"))
                kodidb = dbio.DBOpen("music")
                self.ContentObject = None
                index = int(RestorePoint.get('StartIndex', 0))

                for items in self.EmbyServer.API.get_artists(library_id, False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for artist in items['Items']:
                        Albums = []
                        Audios = []
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, artist, LibraryData, embydb, kodidb, "MusicArtist", "music", "add/update")

                        if not Continue:
                            return

                        for itemsContent in self.EmbyServer.API.get_itemsSyncMusic(library_id, "MusicAlbum,Audio", {"ArtistIds": artist['Id']}):
                            # Sort
                            for item in itemsContent['Items']:
                                if item["Type"] == "MusicAlbum":
                                    Albums.append(item)
                                else:
                                    Audios.append(item)

                        for album in Albums:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, album, LibraryData, embydb, kodidb, "MusicAlbum", "music", "add/update")

                            if not Continue:
                                return

                        for song in Audios:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, song, LibraryData, embydb, kodidb, "Audio", "music", "add/update")

                            if not Continue:
                                return

                dbio.DBClose("music", True)
            elif library_type in ('audiobooks', 'podcasts'):  # Sync even if artist is empty
                isMusic = True
                kodidb = dbio.DBOpen("music")
                self.ContentObject = None
                MusicTypes = ("MusicArtist", "MusicAlbum", "Audio")

                for MusicType in MusicTypes:
                    TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, MusicTypes))
                    index = 0

                    for items in self.EmbyServer.API.get_itemsSyncMusic(library_id, MusicType, {}):
                        for Item in items['Items']:
                            index += 1
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, MusicType, "music", "add/update")

                            if not Continue:
                                return

                dbio.DBClose("music", True)

            embydb.remove_PendingSync(library_id, library_type, library_name)

            if isMusic and not utils.useDirectPaths:
                wait_LibraryRefresh("music", "library")

            if isVideo:
                wait_LibraryRefresh("video", "library")

        self.EmbyServer.Views.update_nodes()
        self.close_EmbyDBWorker(True, progress_updates, "--<[ worker library completed ]")
        LOG.info("[ reload skin ]")
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.sleep(1000)  # give Kodi time to catch up
        self.RunJobs()
        return

    def ItemOps(self, progress_updates, index, TotalRecords, Item, Parameter, embydb, kodidb, ContentType, ContentCategory, Task):
        Ret = False

        if not self.ContentObject:
            self.load_libraryObject(ContentType, embydb, kodidb)

        ProgressValue = int(float(index) / float(TotalRecords) * 100)

        if Task == "add/update":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=Item['Name'])

            if ContentType == "Audio":
                Ret = self.ContentObject.song(Item, Parameter)
            elif ContentType == "MusicAlbum":
                Ret = self.ContentObject.album(Item, Parameter)
            elif ContentType in ("MusicArtist", "AlbumArtist"):
                Ret = self.ContentObject.artist(Item, Parameter)
            elif ContentType in ("Movie", "Video"):
                Ret = self.ContentObject.movie(Item, Parameter)
            elif ContentType == "BoxSet":
                Ret = self.ContentObject.boxset(Item, Parameter)
            elif ContentType == "MusicVideo":
                Ret = self.ContentObject.musicvideo(Item, Parameter)
            elif ContentType == "Episode":
                Ret = self.ContentObject.episode(Item, Parameter)
            elif ContentType == "Season":
                Ret = self.ContentObject.season(Item, Parameter)
            elif ContentType == "Series":
                Ret = self.ContentObject.tvshow(Item, Parameter)

            if Ret and utils.newContent:
                if ContentCategory == "music":
                    MsgTime = int(utils.newmusictime) * 1000
                else:
                    MsgTime = int(utils.newvideotime) * 1000

                utils.dialog("notification", heading="%s %s" % (utils.Translate(33049), ContentType), message=Item['Name'], icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=MsgTime, sound=False)
        elif Task == "remove":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=str(Item))
            self.ContentObject.remove(Item, Parameter)
        elif Task == "userdata":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=str(Parameter['ItemId']))
            self.ContentObject.userdata(Item, Parameter)

        # Check priority tasks
        if self.EmbyDBWritePriority:
            dbio.DBClose(self.EmbyServer.server_id, True)
            utils.WorkerPaused = True
            LOG.info("-->[ Priority Emby DB I/O in progress ]")

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            utils.WorkerPaused = False
            LOG.info("--<[ Priority Emby DB I/O in progress ]")
            embydb = dbio.DBOpen(self.EmbyServer.server_id)
            self.load_libraryObject(ContentType, embydb, kodidb)

        # Check if Kodi db is open -> close db, wait, reopen db
        if utils.KodiDBLock[ContentCategory]:
            LOG.info("-->[ worker delay due to kodi %s db io ]" % ContentCategory)
            dbio.DBClose(ContentCategory, True)

            while utils.KodiDBLock[ContentCategory]:
                xbmc.sleep(500)

            LOG.info("--<[ worker delay due to kodi %s db io ]" % ContentCategory)
            kodidb = dbio.DBOpen(ContentCategory)
            self.load_libraryObject(ContentType, embydb, kodidb)

        # Check sync pause
        Continue = True

        if utils.SyncPause:
            dbio.DBClose(ContentCategory, True)
            self.close_EmbyDBWorker(True, progress_updates, "[ worker paused ]")
            Continue = False

        return Continue, embydb, kodidb

    def load_libraryObject(self, ContentType, embydb, kodidb):
        if ContentType in ("Movie", "BoxSet", "Video"):
            self.ContentObject = movies.Movies(self.EmbyServer, embydb, kodidb)
        elif ContentType == "MusicVideo":
            self.ContentObject = musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb)
        elif ContentType in ('Audio', "MusicArtist", "MusicAlbum", "AlbumArtist"):
            self.ContentObject = music.Music(self.EmbyServer, embydb, kodidb)
        elif ContentType in ("Episode", "Season", 'Series'):
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
        libraries = []

        if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            for LibraryId, Value in list(self.Whitelist.items()):
                AddData = {'Id': LibraryId, 'Name': Value[1]}

                if AddData not in libraries:
                    libraries.append(AddData)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()

            for LibraryId in self.Whitelist:
                if LibraryId in AvailableLibs:
                    del AvailableLibs[LibraryId]

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ["movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos"]:
                    libraries.append({'Id': AvailableLibId, 'Name': AvailableLib[0]})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, utils.Translate(33121))
        selection = utils.dialog("multi", utils.Translate(33120), choices)

        if selection is None:
            return

        # "All" selected
        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
        remove_librarys = []
        add_librarys = []

        if mode in ('AddLibrarySelection', 'UpdateLibrarySelection'):
            for x in selection:
                add_librarys.append(libraries[x - 1]['Id'])
        elif mode == 'RepairLibrarySelection':
            for x in selection:
                remove_librarys.append(libraries[x - 1]['Id'])
                add_librarys.append(libraries[x - 1]['Id'])
        elif mode == 'RemoveLibrarySelection':
            for x in selection:
                remove_librarys.append(libraries[x - 1]['Id'])

        if remove_librarys or add_librarys:
            embydb = self.open_EmbyDBPriority()

            if remove_librarys:
                for LibraryId in remove_librarys:
                    items = embydb.get_item_by_emby_folder_wild(LibraryId)

                    for item in items:
                        embydb.add_RemoveItem(item[0], item[1], LibraryId)

                    embydb.remove_Whitelist_wild(LibraryId)
                    del self.Whitelist[LibraryId]
                    self.EmbyServer.Views.delete_playlist_by_id(LibraryId)
                    self.EmbyServer.Views.delete_node_by_id(LibraryId)
                    LOG.info("---[ removed library: %s ]" % LibraryId)
                    self.EmbyServer.Views.update_nodes()

            if add_librarys:
                for library_id in add_librarys:
                    if library_id in self.EmbyServer.Views.ViewItems:
                        ViewData = self.EmbyServer.Views.ViewItems[library_id]
                        library_type = ViewData[1]
                        library_name = ViewData[0]

                        if library_type == 'mixed':
                            embydb.add_PendingSync(library_id, "movies", library_name, None)
                            embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                            embydb.add_PendingSync(library_id, "tvshows", library_name, None)
                            embydb.add_PendingSync(library_id, "music", library_name, None)
                        elif library_type == 'movies':
                            embydb.add_PendingSync(library_id, "movies", library_name, None)
                            embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                        else:
                            embydb.add_PendingSync(library_id, library_type, library_name, None)

                        LOG.info("---[ added library: %s ]" % library_id)
                    else:
                        LOG.info("---[ added library not found: %s ]" % library_id)

            self.close_EmbyDBPriority()

            if remove_librarys:
                self.worker_remove()

            if add_librarys:
                self.worker_library()

    def refresh_boxsets(self):  # threaded by caller
        embydb = self.open_EmbyDBPriority()
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')

        for LibraryId, Value in list(self.Whitelist.items()):
            if Value[0] == "movies":
                embydb.add_PendingSync(LibraryId, "boxsets", Value[1], None)

        self.close_EmbyDBPriority()
        self.worker_library()

    # Add item_id to userdata queue
    def userdata(self, Data):  # threaded by caller -> websocket via monitor
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                embydb.add_Userdata(str(item))

            self.close_EmbyDBPriority()
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Data):  # threaded by caller
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    LibraryId = item[1]
                    LibraryName = item[2]
                    LibraryType = item[3]
                else:  # update via Websocket
                    item = str(item)

                    if not utils.Python3:
                        item = unicode(item, 'utf-8')

                    if item.isnumeric():
                        EmbyId = item
                        LibraryId = None
                        LibraryName = None
                        LibraryType = None
                    else:
                        LOG.info("Skip invalid update item: %s" % item)
                        continue

                embydb.add_UpdateItem(EmbyId, LibraryId, LibraryName, LibraryType)

            self.close_EmbyDBPriority()
            self.worker_update()

    # Add item_id to removed queue
    def removed(self, Data):  # threaded by caller
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    EmbyType = item[1]
                    LibraryId = item[2]
                else:  # update via Websocket
                    item = str(item)

                    if not utils.Python3:
                        item = unicode(item, 'utf-8')

                    if item.isnumeric():
                        EmbyId = item
                        EmbyType = None
                        LibraryId = None
                    else:
                        LOG.info("Skip invalid remove item: %s" % item)
                        continue

                embydb.add_RemoveItem(EmbyId, EmbyType, LibraryId)

            self.close_EmbyDBPriority()
            self.worker_remove()

def ItemsSort(Items, LibraryData):
    ItemsAudio = []
    ItemsMovie = []
    ItemsBoxSet = []
    ItemsMusicVideo = []
    ItemsSeries = []
    ItemsEpisode = []
    ItemsMusicAlbum = []
    ItemsMusicArtist = []
    ItemsAlbumArtist = []
    ItemsSeason = []

    for Item in Items:
        ItemType = 'Unknown'

        if 'Type' in Item:
            ItemType = Item['Type']

            if ItemType == "Recording":
                if 'MediaType' in Item:
                    if Item['IsSeries']:
                        ItemType = 'Episode'
                    else:
                        ItemType = 'Movie'

        if ItemType in ('Movie', 'Video'):
            ItemsMovie.append((Item, LibraryData[Item["Id"]], 'Movie'))
        elif ItemType == 'BoxSet':
            ItemsBoxSet.append((Item, LibraryData[Item["Id"]], 'BoxSet'))
        elif ItemType == 'MusicVideo':
            ItemsMusicVideo.append((Item, LibraryData[Item["Id"]], 'MusicVideo'))
        elif ItemType == 'Series':
            ItemsSeries.append((Item, LibraryData[Item["Id"]], 'Series'))
        elif ItemType == 'Episode':
            ItemsEpisode.append((Item, LibraryData[Item["Id"]], 'Episode'))
        elif ItemType == 'MusicAlbum':
            ItemsMusicAlbum.append((Item, LibraryData[Item["Id"]], 'MusicAlbum'))
        elif ItemType == 'MusicArtist':
            ItemsMusicArtist.append((Item, LibraryData[Item["Id"]], 'MusicArtist'))
        elif ItemType == 'Audio':
            ItemsAudio.append((Item, LibraryData[Item["Id"]], 'Audio'))
        elif ItemType == 'AlbumArtist':
            ItemsAlbumArtist.append((Item, LibraryData[Item["Id"]], 'AlbumArtist'))
        elif ItemType == 'Season':
            ItemsSeason.append((Item, LibraryData[Item["Id"]], 'Season'))
        else:
            LOG.info("ItemType unknown: %s" % ItemType)
            continue

    return ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason

def StringToDict(Data):
    Data = Data.replace("'", '"')
    Data = Data.replace("False", "false")
    Data = Data.replace("True", "true")
    Data = Data.replace('u"', '"')  # Python 2.X workaround
    Data = Data.replace('L, "', ', "')  # Python 2.X workaround
    Data = Data.replace('l, "', ', "')  # Python 2.X workaround
    return json.loads(Data)

def wait_LibraryRefresh(LibraryId, WorkerId):
    LOG.info("-->[ library refresh %s / worker %s ]" % (LibraryId, WorkerId))
    utils.KodiDBLock[LibraryId] = True
    xbmc.executebuiltin('UpdateLibrary(%s)' % LibraryId)

    while utils.KodiDBLock[LibraryId]:
        xbmc.sleep(250)

    LOG.info("--<[ library refresh %s / worker %s ]" % (LibraryId, WorkerId))

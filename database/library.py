# -*- coding: utf-8 -*-
import json
import xbmc
import xbmcgui
import core.movies
import core.musicvideos
import core.tvshows
import core.music
import helper.loghandler
import helper.utils as Utils
from . import db_open

MediaEmbyMappedSubContent = {"movies": "Movie", "boxsets": "BoxSet", "musicvideos": "MusicVideo", "tvshows": "Series", "music": "Music", "homevideos": "Video"}
LOG = helper.loghandler.LOG('EMBY.database.library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("--->[ library ]")
        self.EmbyServer = EmbyServer
        self.Whitelist = []
        self.LastStartSync = ""
        self.LastRealtimeSync = ""
        self.EmbyDBWritePriority = False
        self.WorkerPaused = False
        self.WorkerInProgressLocal = False

    def set_WorkerInProgress(self, Value):
        Utils.WorkerInProgress = Value
        self.WorkerInProgressLocal = Value

    def set_EmbyDBWritePriority(self):
        if self.EmbyDBWritePriority:
            LOG.info("-->[ Wait for priority workers finished ]")

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            LOG.info("--<[ Wait for priority workers finished ]")

        self.EmbyDBWritePriority = True

        if self.WorkerInProgressLocal:
            LOG.info("-->[ Wait for workers paused ]")

            while not self.WorkerPaused:
                xbmc.sleep(500)

            LOG.info("--<[ Wait for workers paused ]")

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        self.set_EmbyDBWritePriority()
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        embydb.update_LastIncrementalSync(TimestampUTC, "realtime")
        embydb.update_LastIncrementalSync(TimestampUTC, "start")
        db_open.DBClose(self.EmbyServer.server_id, True)
        self.LastRealtimeSync = TimestampUTC
        self.LastStartSync = TimestampUTC
        LastRealtimeSyncLocalTime = Utils.convert_to_local(self.LastRealtimeSync)
        Utils.set_syncdate(LastRealtimeSyncLocalTime)
        self.EmbyDBWritePriority = False

    def load_settings(self):
        # Load previous sync information
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        embydb.init_EmbyDB()
        self.Whitelist = embydb.get_Whitelist()
        self.LastRealtimeSync = embydb.get_LastIncrementalSync("realtime")
        self.LastStartSync = embydb.get_LastIncrementalSync("start")
        db_open.DBClose(self.EmbyServer.server_id, True)

    def InitSync(self, Firstrun):  # Threaded by caller -> emby.py
        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        self.RunJobs()
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

            for LibraryId, library_type, library_name in self.Whitelist:
                if LibraryId not in self.EmbyServer.Views.ViewItems:
                    LOG.info("[ fast_sync remove library %s ]" % LibraryId)
                    continue

                if library_type == "musicvideos":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicVideo", self.LastRealtimeSync, False)
                elif library_type == "movies":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Movie", self.LastRealtimeSync, False)
                elif library_type == "homevideos":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Video", self.LastRealtimeSync, False)
                elif library_type == "boxsets":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "BoxSet", self.LastStartSync, False)
                elif library_type == "tvshows":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Series,Season,Episode", self.LastRealtimeSync, False)
                elif library_type in ("music", "audiobooks"):
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastRealtimeSync, False)
                elif library_type == "podcasts":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastStartSync, False)

                if 'Items' in Items:
                    ItemCounter = 0
                    ItemTemp = len(Items['Items']) * [(None, None, None, None)]  # allocate memory for array (much faster than append each item)

                    for item in Items['Items']:
                        ItemData = (item['Id'], LibraryId, library_name, item['Type'])

                        if ItemData not in UpdateData:
                            ItemTemp[ItemCounter] = ItemData
                            ItemCounter += 1

                    UpdateData += ItemTemp

            for LibraryId, library_type, library_name in self.Whitelist:
                if LibraryId not in self.EmbyServer.Views.ViewItems:
                    LOG.info("[ fast_sync remove library %s ]" % LibraryId)
                    continue

                if library_type == "musicvideos":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicVideo", self.LastRealtimeSync, True)
                elif library_type == "movies":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Movie", self.LastRealtimeSync, True)
                elif library_type == "homevideos":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Video", self.LastRealtimeSync, True)
                elif library_type == "boxsets":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "BoxSet", self.LastStartSync, True)
                elif library_type == "tvshows":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Series,Season,Episode", self.LastRealtimeSync, True)
                elif library_type in ("music", "audiobooks"):
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastRealtimeSync, True)
                elif library_type == "podcasts":
                    Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastStartSync, True)

                if 'Items' in Items:
                    ItemCounter = 0
                    ItemTemp = len(Items['Items']) * [(None, None, None, None)]  # allocate memory for array (much faster than append each item)

                    for item in Items['Items']:
                        ItemData = (item['Id'], LibraryId, library_name, item['Type'])

                        if ItemData not in UpdateData:
                            ItemTemp[ItemCounter] = ItemData
                            ItemCounter += 1

                    UpdateData += ItemTemp

            UpdateData = list(filter(None, UpdateData))

            if KodiCompanion:
                result = self.EmbyServer.API.get_sync_queue(self.LastRealtimeSync, None)  # Kodi companion

                if 'ItemsRemoved' in result:
                    RemovedItems = result['ItemsRemoved']

        # Update sync update timestamp
        self.set_syncdate(Utils.currenttime())

        # Run jobs
        self.removed(RemovedItems)
        self.updated(UpdateData)
        LOG.info("--<[ retrieve changes ]")

    # Get items from emby and place them in the appropriate queues
    # No progress bar needed, it's all internal an damn fast
    def worker_userdata(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker userdata in progress ]")
            return False

        LOG.info("[ worker userdata started ]")
        isMusic = False
        isVideo = False
        self.set_WorkerInProgress(True)
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        UserDataItems = embydb.get_Userdata()

        if not UserDataItems:
            LOG.info("[ worker userdata queue size ] 0")
            db_open.DBClose(self.EmbyServer.server_id, True)
            self.set_WorkerInProgress(False)
            return True

        ItemCounter = len(UserDataItems)
        LOG.info("[ worker userdata queue size ] %s" % ItemCounter)
        MusicItems = []
        VideoItems = []

        # Group items
        for UserDataItem in UserDataItems:
            UserDataItem = StringToDict(UserDataItem[0])
            Continue, embydb, _, _ = self.CheckSyncContinue("userdata", None, "", embydb, None)

            if not Continue:
                return False

            e_item = embydb.get_item_by_id(UserDataItem['ItemId'])

            if not e_item: #not synced item
                LOG.info("worker userdata, item not found in local database %s" % UserDataItem['ItemId'])
                embydb.delete_Userdata(str(UserDataItem))
                continue

            if e_item[5] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                MusicItems.append((UserDataItem, e_item))
            else:
                VideoItems.append((UserDataItem, e_item))

        if MusicItems:
            musicdb = db_open.DBOpen(Utils.DatabaseFiles, "music")
            isMusic = True

            for MusicItem in MusicItems:
                core.music.Music(self.EmbyServer, embydb, musicdb).userdata(MusicItem[1], MusicItem[0])
                embydb.delete_Userdata(str(MusicItem[0]))

            db_open.DBClose("music", True)

        if VideoItems:
            videodb = db_open.DBOpen(Utils.DatabaseFiles, "video")
            isVideo = True

            for VideoItem in VideoItems:
                if VideoItem[1][5] in ('Movie', 'BoxSet'):
                    core.movies.Movies(self.EmbyServer, embydb, videodb).userdata(VideoItem[1], VideoItem[0])
                elif VideoItem[1][5] == 'MusicVideo':
                    core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb).userdata(VideoItem[1], VideoItem[0])
                elif VideoItem[1][5] in ('TVShow', 'Series', 'Season', 'Episode'):
                    core.tvshows.TVShows(self.EmbyServer, embydb, videodb).userdata(VideoItem[1], VideoItem[0])

                embydb.delete_Userdata(str(VideoItem[0]))

            db_open.DBClose("video", True)

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")
        db_open.DBClose(self.EmbyServer.server_id, True)

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        LOG.info("--<[ worker userdata completed ]")
        self.set_WorkerInProgress(False)
        self.RunJobs()
        return True

    def worker_update(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker update in progress ]")
            return False

        LOG.info("-->[ worker update started ]")
        isMusic = False
        isVideo = False
        self.set_WorkerInProgress(True)
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        Counter = 0
        UpdateItems = embydb.get_UpdateItem()

        if not UpdateItems:
            LOG.info("[ worker update queue size ] 0")
            db_open.DBClose(self.EmbyServer.server_id, True)
            self.set_WorkerInProgress(False)
            return True

        ItemCounter = len(UpdateItems)
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", Utils.Translate(33178))
        ItemIds = []
        ItemLibraryData = []
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
        LOG.info("[ worker update queue size ] %s" % ItemCounter)

        for UpdateItem in UpdateItems:
            Continue, embydb, _, _ = self.CheckSyncContinue("update", progress_updates, "", embydb, None)

            if not Continue:
                return False

            Id = UpdateItem[0]

            if UpdateItem[1]:  # Fastsync update
                ItemLibraryData.append({"Id": UpdateItem[1], "Name": UpdateItem[2]})
            else:  # Realtime update
                ItemLibraryData.append(None)

            ItemIds.append(str(Id))

        # Load data from Emby server and cache them to minimize Kodi db open time
        if ItemIds:
            Items = self.EmbyServer.API.get_item_library(",".join(ItemIds))

            if 'Items' in Items:
                for index, Item in enumerate(Items['Items']):
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
                        ItemsMovie.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'BoxSet':
                        ItemsBoxSet.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'MusicVideo':
                        ItemsMusicVideo.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'Series':
                        ItemsSeries.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'Episode':
                        ItemsEpisode.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'MusicAlbum':
                        ItemsMusicAlbum.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'MusicArtist':
                        ItemsMusicArtist.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'Audio':
                        ItemsAudio.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'AlbumArtist':
                        ItemsAlbumArtist.append((Item, ItemLibraryData[index]))
                    elif ItemType == 'Season':
                        ItemsSeason.append((Item, ItemLibraryData[index]))
                    else:
                        ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                        progress_updates.update(ProgressValue, message="%s: media not found %s" % (Utils.Translate(33178), ItemType))
                        LOG.error("Media Type not found: %s/%s" % (ItemType, Item['Id']))
                        LOG.debug("Media Type not found: %s" % Item)
                        ItemIds.remove(Item['Id'])
                        embydb.delete_UpdateItem(Item['Id'])
                        Counter += 1
                        continue

        if ItemsMovie or ItemsBoxSet or ItemsMusicVideo or ItemsSeries or ItemsSeason or ItemsEpisode:
            videodb = db_open.DBOpen(Utils.DatabaseFiles, "video")
            ContentObj = core.movies.Movies(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsMovie:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Movie')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.movies.Movies(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsBoxSet:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'BoxSet')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.movies.Movies(self.EmbyServer, embydb, videodb)

            ContentObj = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsMusicVideo:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicVideo')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb)

            ContentObj = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsSeries:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Series')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsSeason:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Season')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

            for Item, LibraryData in ItemsEpisode:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Episode')
                ItemIds.remove(Item['Id'])
                Continue, embydb, videodb, Reload = self.CheckSyncContinue("update", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

            db_open.DBClose("video", True)
            isVideo = True

        if ItemsMusicArtist or ItemsAlbumArtist or ItemsMusicAlbum or ItemsAudio:
            musicdb = db_open.DBOpen(Utils.DatabaseFiles, "music")
            ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            for Item, LibraryData in ItemsMusicArtist:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicArtist')
                ItemIds.remove(Item['Id'])
                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("update", progress_updates, "music", embydb, musicdb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            for Item, LibraryData in ItemsAlbumArtist:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'AlbumArtist')
                ItemIds.remove(Item['Id'])
                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("update", progress_updates, "music", embydb, musicdb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            for Item, LibraryData in ItemsMusicAlbum:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicAlbum')
                ItemIds.remove(Item['Id'])
                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("update", progress_updates, "music", embydb, musicdb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            for Item, LibraryData in ItemsAudio:
                Counter += 1
                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Audio')
                ItemIds.remove(Item['Id'])
                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("update", progress_updates, "music", embydb, musicdb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            musicdb.clean_music()
            db_open.DBClose("music", True)
            isMusic = True

        for ItemID in ItemIds:
            embydb.delete_UpdateItem(ItemID)

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")
        db_open.DBClose(self.EmbyServer.server_id, True)
        progress_updates.close()

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        LOG.info("--<[ worker update completed ]")
        self.set_WorkerInProgress(False)
        self.RunJobs()
        return True

    def worker_remove(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker remove in progress ]")
            return False

        LOG.info("-->[ worker remove started ]")
        isMusic = False
        isVideo = False
        self.set_WorkerInProgress(True)
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        RemoveItems = embydb.get_RemoveItem()

        if not RemoveItems:
            LOG.info("[ worker remove queue size ] 0")
            db_open.DBClose(self.EmbyServer.server_id, True)
            self.set_WorkerInProgress(False)
            return True

        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", Utils.Translate(33178))

        #Sort Items
        RemoveItemsAudio = []
        RemoveItemsVideo = []

        for RemoveItem in RemoveItems:
            Id = RemoveItem[0]
            LibraryType = RemoveItem[1]
            LibraryId = RemoveItem[2]

            if not LibraryType:
                LibraryType = embydb.get_media_by_id(Id)
                ForceRemoval = False  # msg from Emby server
            else:
                ForceRemoval = True  # Library removed (manually)

            if LibraryType:
                if LibraryType in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    RemoveItemsAudio.append([Id, LibraryType, LibraryId, ForceRemoval])
                else:
                    RemoveItemsVideo.append([Id, LibraryType, LibraryId, ForceRemoval])
            else:
                # Folder removal (realtime msg from Emby server)
                RemoveFolderItems = embydb.get_media_by_parent_id(Id)

                for RemoveFolderItem in RemoveFolderItems:
                    if RemoveFolderItem[1] in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                        RemoveItemsAudio.append([RemoveFolderItem[0], RemoveFolderItem[1], LibraryId, False])
                    else:
                        RemoveItemsVideo.append([RemoveFolderItem[0], RemoveFolderItem[1], LibraryId, False])

                LOG.info("Delete media by folder id %s" % Id)
                embydb.delete_RemoveItem(Id)

        ItemCounter = len(RemoveItemsAudio) + len(RemoveItemsVideo)
        Counter = 0
        LOG.info("[ worker remove queue size ] %s" % ItemCounter)

        if RemoveItemsVideo:
            videodb = db_open.DBOpen(Utils.DatabaseFiles, "video")

            for RemoveItemVideo in RemoveItemsVideo:
                Counter += 1
                Continue, embydb, videodb, _ = self.CheckSyncContinue("remove", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                Value = int((float(Counter) / float(ItemCounter)) * 100)
                progress_updates.update(Value, message="%s (remove): %s" % (Utils.Translate(33178), RemoveItemVideo[0]))
                embydb.delete_RemoveItem(RemoveItemVideo[0])

                if RemoveItemVideo[1] in ('Movie', 'BoxSet', 'SpecialFeature'):
                    core.movies.Movies(self.EmbyServer, embydb, videodb).remove(RemoveItemVideo[0], RemoveItemVideo[3])
                elif RemoveItemVideo[1] == 'MusicVideo':
                    core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb).remove(RemoveItemVideo[0], RemoveItemVideo[3])
                elif RemoveItemVideo[1] in ('TVShow', 'Series', 'Season', 'Episode'):
                    core.tvshows.TVShows(self.EmbyServer, embydb, videodb).remove(RemoveItemVideo[0], RemoveItemVideo[3])

            db_open.DBClose("video", True)
            isVideo = True

        if RemoveItemsAudio:
            musicdb = db_open.DBOpen(Utils.DatabaseFiles, "music")
            ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

            for RemoveItemAudio in RemoveItemsAudio:
                Counter += 1
                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("remove", progress_updates, "music", embydb, musicdb)

                if not Continue:
                    return False

                if Reload:
                    ContentObj = core.music.Music(self.EmbyServer, embydb, musicdb)

                Value = int((float(Counter) / float(ItemCounter)) * 100)
                progress_updates.update(Value, message="%s (remove): %s" % (Utils.Translate(33178), RemoveItemAudio[0]))
                embydb.delete_RemoveItem(RemoveItemAudio[0])
                ContentObj.remove(RemoveItemAudio[0], RemoveItemAudio[2])
                musicdb.clean_music()

            db_open.DBClose("music", True)
            isMusic = True

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")
        db_open.DBClose(self.EmbyServer.server_id, True)
        progress_updates.close()

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        LOG.info("--<[ worker remove completed ]")
        self.set_WorkerInProgress(False)
        self.RunJobs()
        return True

    def worker_library(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker library in progress ]")
            return False

        LOG.info("-->[ worker library started ]")
        self.set_WorkerInProgress(True)
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
        isMusic = False
        isVideo = False
        SyncItems = embydb.get_PendingSync()

        if not SyncItems:
            LOG.info("[ worker library queue size ] 0")
            db_open.DBClose(self.EmbyServer.server_id, True)
            self.set_WorkerInProgress(False)
            return True

        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", "%s %s" % (Utils.Translate(33021), Utils.Translate(33238)))
        ItemCounter = len(SyncItems)
        LOG.info("[ worker library queue size ] %s" % ItemCounter)

        for SyncItem in SyncItems:
            library_id = SyncItem[0]
            library_type = SyncItem[1]
            library_name = SyncItem[2]
            LibraryData = {"Id": library_id, "Name": library_name}
            self.Whitelist = embydb.add_Whitelist(library_id, library_type, library_name)

            if SyncItem[3]:
                RestorePoint = StringToDict(SyncItem[3])
            else:
                RestorePoint = {}

            if library_type not in ('music', 'audiobooks', 'podcasts', 'tvshows'):
                isVideo = True
                SubContent = MediaEmbyMappedSubContent[library_type]
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, SubContent))
                videodb = db_open.DBOpen(Utils.DatabaseFiles, "video")
                Continue, embydb, videodb, _ = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                if not Continue:
                    return False

                if library_type in ("movies", "homevideos"):
                    DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).movie
                elif library_type == "boxsets":
                    DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).boxset
                elif library_type == "musicvideos":
                    DBObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb).musicvideo
                else:
                    LOG.error("Invalid DBObject %s" % library_type)
                    continue

                for items in self.EmbyServer.API.get_itemsSync(library_id, SubContent, False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                    start_index = RestorePoint['StartIndex']

                    for index, Item in enumerate(items['Items']):
                        ProgressValue = int((float(start_index + index) / TotalRecords) * 100)
                        progress_updates.update(ProgressValue, heading="Emby: %s" % library_name, message=Item['Name'])
                        DBObject(Item, LibraryData)
                        Continue, embydb, videodb, Reload = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                        if not Continue:
                            return False

                        if Reload:
                            if library_type in ("movies", "homevideos"):
                                DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).movie
                            elif library_type == "boxsets":
                                DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).boxset
                            elif library_type == "musicvideos":
                                DBObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb).musicvideo
                            else:
                                LOG.error("Invalid DBObject %s" % library_type)
                                continue

                db_open.DBClose("video", True)
            elif library_type == 'tvshows':  # stacked sync: tv-shows -> season/episode
                isVideo = True
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "Series"))
                videodb = db_open.DBOpen(Utils.DatabaseFiles, "video")
                DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                for items in self.EmbyServer.API.get_itemsSync(library_id, 'Series', False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                    start_index = RestorePoint['StartIndex']

                    for index, tvshow in enumerate(items['Items']):
                        percent = int((float(start_index + index) / TotalRecords) * 100)
                        progress_updates.update(percent, heading="Emby: %s" % library_name, message="TVShow: %s" % tvshow['Name'])
                        Seasons = []
                        Episodes = []
                        Continue, embydb, videodb, Reload = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                        if not Continue:
                            return False

                        if Reload:
                            DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                        for itemsContent in self.EmbyServer.API.get_itemsSync(tvshow['Id'], "Season,Episode", False, {}):
                            # Sort
                            for item in itemsContent['Items']:
                                if item["Type"] == "Season":
                                    Seasons.append(item)
                                else:
                                    Episodes.append(item)

                            Continue, embydb, videodb, Reload = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                            if not Continue:
                                return False

                            if Reload:
                                DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                        for Season in Seasons:
                            progress_updates.update(percent, heading="Emby: %s" % library_name, message="Season: %s / TVShow: %s" % (Season['Name'], tvshow['Name']))
                            DBObject.season(Season, LibraryData)
                            Continue, embydb, videodb, Reload = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                            if not Continue:
                                return False

                            if Reload:
                                DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                        for Episode in Episodes:
                            progress_updates.update(percent, heading="Emby: %s" % library_name, message="Episode: %s / TVShow: %s" % (Episode['Name'], tvshow['Name']))
                            DBObject.episode(Episode, LibraryData)
                            Continue, embydb, videodb, Reload = self.CheckSyncContinue("library", progress_updates, "video", embydb, videodb)

                            if not Continue:
                                return False

                            if Reload:
                                DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                db_open.DBClose("video", True)
            else:  #  Sync only if artist is valid (performance)
                isMusic = True
                musicdb = db_open.DBOpen(Utils.DatabaseFiles, "music")
                DBObject = core.music.Music(self.EmbyServer, embydb, musicdb)

                if library_type == 'music':
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsArtists(library_id)

                    for items in self.EmbyServer.API.get_artists(library_id, False, RestorePoint):
                        RestorePoint = items['RestorePoint']['params']
                        embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                        start_index = RestorePoint['StartIndex']

                        for index, artist in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords) * 100)
                            progress_updates.update(percent, heading="Emby: %s" % library_name, message=artist['Name'])
                            DBObject.artist(artist, LibraryData)
                            Albums = []
                            Audios = []

                            for itemsContent in self.EmbyServer.API.get_itemsSyncMusic(library_id, "MusicAlbum,Audio", {"ArtistIds": artist['Id']}):
                                # Sort
                                for item in itemsContent['Items']:
                                    if item["Type"] == "MusicAlbum":
                                        Albums.append(item)
                                    else:
                                        Audios.append(item)

                            for album in Albums:
                                DBObject.album(album, LibraryData)

                            for song in Audios:
                                DBObject.song(song, LibraryData)

                            Continue, embydb, musicdb, Reload = self.CheckSyncContinue("library", progress_updates, "music", embydb, musicdb)

                            if not Continue:
                                return False

                            if Reload:
                                DBObject = core.music.Music(self.EmbyServer, embydb, musicdb)
                else:  # Sync even if artist is empty
                    SyncArtists = False

                    if not RestorePoint:
                        SyncArtists = True
                    else:
                        if RestorePoint['IncludeItemTypes'] == "MusicArtist":
                            SyncArtists = True

                    if SyncArtists:
                        TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "MusicArtist"))

                        for items in self.EmbyServer.API.get_itemsSyncMusic(library_id, "MusicArtist", RestorePoint):
                            RestorePoint = items['RestorePoint']['params']
                            embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                            start_index = RestorePoint['StartIndex']

                            for index, Item in enumerate(items['Items']):
                                ProgressValue = int((float(start_index + index) / TotalRecords) * 100)
                                progress_updates.update(ProgressValue, heading="Emby: %s Artist" % library_name, message=Item['Name'])
                                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("library", progress_updates, "music", embydb, musicdb)

                                if not Continue:
                                    return False

                                if Reload:
                                    DBObject = core.music.Music(self.EmbyServer, embydb, musicdb)

                                DBObject.artist(Item, LibraryData)

                        RestorePoint = {}

                    SyncAlbum = False

                    if not RestorePoint:
                        SyncAlbum = True
                    else:
                        if RestorePoint['IncludeItemTypes'] == "MusicAlbum":
                            SyncAlbum = True

                    if SyncAlbum:
                        TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "MusicAlbum"))

                        for items in self.EmbyServer.API.get_itemsSyncMusic(library_id, "MusicAlbum", RestorePoint):
                            RestorePoint = items['RestorePoint']['params']
                            embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                            start_index = RestorePoint['StartIndex']

                            for index, Item in enumerate(items['Items']):
                                ProgressValue = int((float(start_index + index) / TotalRecords) * 100)
                                progress_updates.update(ProgressValue, heading="Emby: %s Album" % library_name, message=Item['Name'])
                                DBObject.album(Item, LibraryData)
                                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("library", progress_updates, "music", embydb, musicdb)

                                if not Continue:
                                    return False

                                if Reload:
                                    DBObject = core.music.Music(self.EmbyServer, embydb, musicdb)

                        RestorePoint = {}

                    SyncAudio = False

                    if not RestorePoint:
                        SyncAudio = True
                    else:
                        if RestorePoint['IncludeItemTypes'] == "Audio":
                            SyncAudio = True

                    if SyncAudio:
                        TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "Audio"))

                        for items in self.EmbyServer.API.get_itemsSyncMusic(library_id, "Audio", RestorePoint):
                            RestorePoint = items['RestorePoint']['params']
                            embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                            start_index = RestorePoint['StartIndex']

                            for index, Item in enumerate(items['Items']):
                                ProgressValue = int((float(start_index + index) / TotalRecords) * 100)
                                progress_updates.update(ProgressValue, heading="Emby: %s Audio" % library_name, message=Item['Name'])
                                DBObject.song(Item, LibraryData)
                                Continue, embydb, musicdb, Reload = self.CheckSyncContinue("library", progress_updates, "music", embydb, musicdb)

                                if not Continue:
                                    return False

                                if Reload:
                                    DBObject = core.music.Music(self.EmbyServer, embydb, musicdb)

                db_open.DBClose("music", True)

            embydb.remove_PendingSync(library_id, library_type, library_name)

            if isMusic and not Utils.useDirectPaths:
                xbmc.executebuiltin('UpdateLibrary(music)')

            if isVideo:
                xbmc.executebuiltin('UpdateLibrary(video)')

        db_open.DBClose(self.EmbyServer.server_id, True)
        progress_updates.close()
        self.EmbyServer.Views.update_nodes()
        xbmc.sleep(1000)  # give Kodi time for updates
        LOG.info("[ reload skin ]")
        xbmc.executebuiltin('ReloadSkin()')
        LOG.info("--<[ worker library completed ]")
        self.set_WorkerInProgress(False)
        self.RunJobs()
        return True

    # Run workers in specific order
    def RunJobs(self):
        if self.worker_remove():
            if self.worker_update():
                if self.worker_userdata():
                    self.worker_library()

    def CheckSyncContinue(self, Id, progress_updates, kodidbType, embydb, kodidb):
        Reload = False

        # Check priority tasks
        if self.EmbyDBWritePriority:
            db_open.DBClose(self.EmbyServer.server_id, True)
            self.WorkerPaused = True
            LOG.info("-->[ Priority Emby DB I/O in progress ]")

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            self.WorkerPaused = False
            LOG.info("--<[ Priority Emby DB I/O in progress ]")
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
            Reload = True

        # Check if Kodi db is open -> close db, wait, reopen db
        if kodidbType == "music":
            if Utils.KodiDBLockMusic:
                LOG.info("[ worker %s delay due to kodi music db io ]" % Id)
                db_open.DBClose(kodidbType, True)

                while Utils.KodiDBLockMusic:
                    xbmc.sleep(500)

                kodidb = db_open.DBOpen(Utils.DatabaseFiles, kodidbType)
                Reload = True
        elif kodidbType == "video":
            if Utils.KodiDBLockVideo:
                db_open.DBClose(kodidbType, True)
                LOG.info("[ worker %s delay due to kodi video db io ]" % Id)

                while Utils.KodiDBLockVideo:
                    xbmc.sleep(500)

                kodidb = db_open.DBOpen(Utils.DatabaseFiles, kodidbType)
                Reload = True

        # Check sync pause
        if Utils.SyncPause:
            LOG.info("[ worker %s paused ]" % Id)

            if progress_updates:
                progress_updates.close()

            if kodidbType:
                db_open.DBClose(kodidbType, True)

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.set_WorkerInProgress(False)
            return False, embydb, kodidb, Reload

        return True, embydb, kodidb, Reload

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):  # threaded by caller
        libraries = []

        if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            for LibraryId, _, LibraryName in self.Whitelist:
                AddData = {'Id': LibraryId, 'Name': LibraryName}

                if AddData not in libraries:
                    libraries.append(AddData)
        else:  # AddLibrarySelection
            available = self.EmbyServer.Views.ViewItems

            for LibraryId, _, _ in self.Whitelist:
                # boxsets and movies have same ID
                if LibraryId in available:
                    del available[LibraryId]

            for LibraryId in available:
                if self.EmbyServer.Views.ViewItems[LibraryId][1] in ["movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos"]:
                    libraries.append({'Id': LibraryId, 'Name': self.EmbyServer.Views.ViewItems[LibraryId][0]})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, Utils.Translate(33121))
        selection = Utils.dialog("multi", Utils.Translate(33120), choices)

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

        if remove_librarys:
            self.remove_library(remove_librarys)

        if add_librarys:
            self.add_library(add_librarys)

    def refresh_boxsets(self):  # threaded by caller
        self.set_EmbyDBWritePriority()
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
        embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

        for library_id, library_type, library_name in self.Whitelist:
            if library_type == "boxsets":
                self.Whitelist = embydb.remove_Whitelist(library_id, library_type, library_name)
                embydb.add_PendingSync(library_id, "boxsets", library_name, None)

        db_open.DBClose(self.EmbyServer.server_id, True)
        self.EmbyDBWritePriority = False
        self.worker_library()

    def add_library(self, library_ids):  # threaded by caller
        if library_ids:
            self.set_EmbyDBWritePriority()
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

            for library_id in library_ids:
                ViewData = self.EmbyServer.Views.ViewItems[library_id]
                library_type = ViewData[1]
                library_name = ViewData[0]

                if library_type == 'mixed':
                    embydb.add_PendingSync(library_id, "movies", library_name, None)
                    embydb.add_PendingSync(library_id, "tvshows", library_name, None)
                    embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                    embydb.add_PendingSync(library_id, "music", library_name, None)
                elif library_type == 'movies':
                    embydb.add_PendingSync(library_id, "movies", library_name, None)
                    embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                else:
                    embydb.add_PendingSync(library_id, library_type, library_name, None)

                LOG.info("---[ added library: %s ]" % library_id)

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.EmbyDBWritePriority = False
            self.worker_library()

    # Remove library by their id from the Kodi database
    def remove_library(self, library_ids):  # threaded by caller
        if library_ids:
            self.set_EmbyDBWritePriority()
            RemoveItems = []
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

            for library_id in library_ids:
                items = embydb.get_item_by_emby_folder_wild(library_id)

                for item in items:
                    RemoveItems.append(item + (library_id,))

                for Whitelist_library_id, Whitelist_library_type, Whitelist_library_name in self.Whitelist:
                    if Whitelist_library_id == library_id:
                        self.Whitelist = embydb.remove_Whitelist(Whitelist_library_id, Whitelist_library_type, Whitelist_library_name)

                self.EmbyServer.Views.delete_playlist_by_id(library_id)
                self.EmbyServer.Views.delete_node_by_id(library_id)
                LOG.info("---[ removed library: %s ]" % library_id)

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.EmbyDBWritePriority = False
            self.EmbyServer.Views.update_nodes()
            self.removed(RemoveItems)

    # Add item_id to userdata queue
    def userdata(self, Data):  # threaded by caller -> websocket via monitor
        if Data:
            self.set_EmbyDBWritePriority()
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

            for item in Data:
                embydb.add_Userdata(str(item))

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.EmbyDBWritePriority = False
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Data):  # threaded by caller
        if Data:
            self.set_EmbyDBWritePriority()
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    LibraryId = item[1]
                    LibraryName = item[2]
                    LibraryType = item[3]
                else:  # update via Websocket
                    item = str(item)

                    if not Utils.Python3:
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

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.EmbyDBWritePriority = False
            self.worker_update()

    # Add item_id to removed queue
    def removed(self, Data):  # threaded by caller
        if Data:
            self.set_EmbyDBWritePriority()
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    EmbyType = item[1]
                    LibraryId = item[2]
                else:  # update via Websocket
                    item = str(item)

                    if not Utils.Python3:
                        item = unicode(item, 'utf-8')

                    if item.isnumeric():
                        EmbyId = item
                        EmbyType = None
                        LibraryId = None
                    else:
                        LOG.info("Skip invalid remove item: %s" % item)
                        continue

                embydb.add_RemoveItem(EmbyId, EmbyType, LibraryId)

            db_open.DBClose(self.EmbyServer.server_id, True)
            self.EmbyDBWritePriority = False
            self.worker_remove()

def worker_update_process_item(Item, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, LibraryType):
    Ret = False
    progress_updates.update(ProgressValue, message="%s: %s" % (Utils.Translate(33178), Item['Name']))

    if LibraryType == 'Movie':
        Ret = ContentObj.movie(Item, LibraryData)
    elif LibraryType == 'BoxSet':
        Ret = ContentObj.boxset(Item, LibraryData)
    elif LibraryType == 'MusicVideo':
        Ret = ContentObj.musicvideo(Item, LibraryData)
    elif LibraryType == 'Series':
        Ret = ContentObj.tvshow(Item, LibraryData)
    elif LibraryType == 'Episode':
        Ret = ContentObj.episode(Item, LibraryData)
    elif LibraryType == 'MusicAlbum':
        Ret = ContentObj.album(Item, LibraryData)
    elif LibraryType == 'MusicArtist':
        Ret = ContentObj.artist(Item, LibraryData)
    elif LibraryType == 'Audio':
        Ret = ContentObj.song(Item, LibraryData)
    elif LibraryType == 'AlbumArtist':
        Ret = ContentObj.artist(Item, LibraryData)
    elif LibraryType == 'Season':
        Ret = ContentObj.season(Item, LibraryData)

    embydb.delete_UpdateItem(Item['Id'])

    if Ret and Utils.newContent:
        Utils.dialog("notification", heading="%s %s" % (Utils.Translate(33049), LibraryType), message=Item['Name'], icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=int(Utils.newvideotime) * 1000, sound=False)

def StringToDict(Data):
    Data = Data.replace("'", '"')
    Data = Data.replace("False", "false")
    Data = Data.replace("True", "true")
    Data = Data.replace('u"', '"')  # Python 2.X workaround
    Data = Data.replace('L, "', ', "')  # Python 2.X workaround
    Data = Data.replace('l, "', ', "')  # Python 2.X workaround
    return json.loads(Data)

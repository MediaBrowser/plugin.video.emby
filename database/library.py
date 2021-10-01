# -*- coding: utf-8 -*-
import threading
import xbmc
import xbmcgui
import core.movies
import core.musicvideos
import core.tvshows
import core.music
import helper.loghandler
import helper.utils as Utils
from . import db_open

LockQueue = threading.Lock()
DBLock = threading.Lock()
MediaEmbyMappedSubContent = {"movies": "Movie", "boxsets": "BoxSet", "musicvideos": "MusicVideo", "tvshows": "Series", "music": "Music", "homevideos": "Video"}
LOG = helper.loghandler.LOG('EMBY.library.Library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("--->[ library ]")
        self.EmbyServer = EmbyServer
        self.worker_running = {"userdata": False, "update": False, "remove": False, "library": False, "boxset": False}
        self.Whitelist = []
        self.LastRealtimeSync = None
        self.LastStartSync = None

        # Load previous sync information and update timestamp
        with DBLock:
            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                self.Whitelist = embydb.get_Whitelist()
                self.LastRealtimeSync = embydb.get_update_LastIncrementalSync(Utils.currenttime(), "realtime")
                self.LastStartSync = embydb.get_update_LastIncrementalSync(Utils.currenttime(), "start")

        threading.Thread(target=self.Start).start()

    def Start(self):
        enable_fast_sync = False

        for plugin in self.EmbyServer.API.get_plugins():
            if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                enable_fast_sync = True
                break

        if self.LastRealtimeSync:
            self.fast_sync(enable_fast_sync)
            LOG.info("--<[ retrieve changes ]")

        threading.Thread(target=self.RunJobs).start()

    # Get items from emby and place them in the appropriate queues
    # No progress bar needed, it's all internal an damn fast
    def worker_userdata(self):
        if self.worker_running["userdata"]:
            LOG.info("[ worker userdata in progress ]")
            return False

        if Utils.SyncPause:
            return False

        LOG.info("[ worker userdata started ]")

        with DBLock:
            if Utils.SyncPause:
                return False

            Music = False
            Video = False

            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                while True:
                    UserDataItems = embydb.get_Userdata()

                    if not UserDataItems:
                        if self.worker_running["userdata"]:
                            break

                        LOG.info("[ worker userdata queue size ] 0")
                        return True

                    self.worker_running["userdata"] = True
                    ItemCounter = len(UserDataItems)
                    LOG.info("[ worker userdata queue size ] %s" % ItemCounter)

                    for UserDataItem in UserDataItems:
                        UserDataItem = Utils.StringToDict(UserDataItem[0])

                        if self.CheckPause("userdata", None):
                            return False

                        embydb.delete_Userdata(str(UserDataItem))
                        e_item = embydb.get_item_by_id(UserDataItem['ItemId'])

                        if not e_item: #not synced item
                            LOG.info("worker userdata, item not found in local database %s" % UserDataItem['ItemId'])
                            continue

                        if e_item[5] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                            DBType = "music"
                        else:
                            DBType = "video"

                        with db_open.io(Utils.DatabaseFiles, DBType, True) as kodidb:
                            if e_item[5] in ('Movie', 'BoxSet'):
                                core.movies.Movies(self.EmbyServer, embydb, kodidb).userdata(e_item, UserDataItem)
                                Video = True
                            elif e_item[5] == 'MusicVideo':
                                core.musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb).userdata(e_item, UserDataItem)
                                Video = True
                            elif e_item[5] in ('TVShow', 'Series', 'Season', 'Episode'):
                                core.tvshows.TVShows(self.EmbyServer, embydb, kodidb).userdata(e_item, UserDataItem)
                                Video = True
                            elif e_item[5] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                                core.music.Music(self.EmbyServer, embydb, kodidb).userdata(e_item, UserDataItem)
                                Music = True

                embydb.get_update_LastIncrementalSync(Utils.currenttime(), "realtime")

            if Music:
                xbmc.executebuiltin('UpdateLibrary(music)')

            if Video:
                xbmc.executebuiltin('UpdateLibrary(video)')

            LOG.info("--<[ worker userdata completed ]")
            self.worker_running["userdata"] = False
            return True

    def worker_update_process_item(self, Id, IsVideo, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, LibraryType):
        Item = None
        Ret = False

        if IsVideo:
            Items = self.EmbyServer.API.get_item_library_video(Id)
        else:
            Items = self.EmbyServer.API.get_item_library_music(Id)

        if 'Items' in Items:
            Item = Items['Items']

            if Item:
                Item = Item[0]

        if not Item:
            embydb.delete_UpdateItem(Id)
            LOG.info("Could not find item %s in the emby database." % Id)
            return

        progress_updates.update(ProgressValue, message="%s: %s" % (Utils.Translate(33178), Item['Name']))
        embydb.delete_UpdateItem(Id)

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

        if Ret and Utils.newContent:
            Utils.dialog("notification", heading="%s %s" % (Utils.Translate(33049), LibraryType), message=Item['Name'], icon="{emby}", time=int(Utils.newvideotime) * 1000, sound=False)

    def worker_update(self):
        if self.worker_running["update"]:
            LOG.info("[ worker update in progress ]")
            return False

        if Utils.SyncPause:
            return False

        LOG.info("-->[ worker update started ]")

        with DBLock:
            if Utils.SyncPause:
                return False

            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                while True:
                    UpdateItems = embydb.get_UpdateItem()

                    if not UpdateItems:
                        LOG.info("[ worker update queue size ] 0")

                        if self.worker_running["update"]:
                            break

                        return True

                    if not self.worker_running["update"]:
                        progress_updates = xbmcgui.DialogProgressBG()
                        progress_updates.create("Emby", Utils.Translate(33178))
                        self.worker_running["update"] = True

                    ItemCounter = len(UpdateItems)
                    Counter = 0
                    ProgressValue = 0
                    LOG.info("[ worker update queue size ] %s" % ItemCounter)
                    ItemsMovie = []
                    ItemsBoxSet = []
                    ItemsMusicVideo = []
                    ItemsSeries = []
                    ItemsEpisode = []
                    ItemsMusicAlbum = []
                    ItemsAudio = []
                    ItemsMusicArtist = []
                    ItemsAlbumArtist = []
                    ItemsSeason = []

                    for UpdateItem in UpdateItems:
                        if self.CheckPause("update", progress_updates):
                            return False

                        Id = UpdateItem[0]

                        if UpdateItem[1]:  # Fastsync update
                            LibraryData = {"Id": UpdateItem[1], "Name": UpdateItem[2]}
                            LibraryType = UpdateItem[3]
                        else:  # Realtime update
                            LibraryData = None
                            LibraryType = None

                        Item = None

                        if not LibraryType:  # Realtime update
                            Items = self.EmbyServer.API.get_item_library_type(Id)  # Query minimum Info to check type

                            if 'Items' in Items:
                                Item = Items['Items']

                                if Item:
                                    Item = Item[0]

                            if not Item:
                                progress_updates.update(ProgressValue, message="%s: item not found %s in emby database" % (Utils.Translate(33178), LibraryType))
                                embydb.delete_UpdateItem(Id)
                                LOG.info("Could not find item %s in the emby database." % Id)
                                ItemCounter -= 1
                                continue

                            if self.CheckPause("update", progress_updates):
                                return False

                            LibraryType = Item['Type']

                        if LibraryType not in ('Movie', 'BoxSet', 'MusicVideo', 'Series', 'Episode', 'MusicAlbum', 'Audio', 'MusicArtist', 'AlbumArtist', 'Season', 'Video', 'Recording'):
                            progress_updates.update(ProgressValue, message="%s: media not found %s" % (Utils.Translate(33178), LibraryType))
                            LOG.error("Media Type not found: %s/%s" % (LibraryType, Id))
                            LOG.debug("Media Type not found: %s" % Item)
                            embydb.delete_UpdateItem(Id)
                            ItemCounter -= 1
                            continue

                        if LibraryType == 'Recording':
                            if Item['IsSeries']:
                                LibraryType = 'Episode'
                            else:
                                LibraryType = 'Movie'

                        if LibraryType in ('Movie', 'Video'):
                            ItemsMovie.append((Id, LibraryData))
                        elif LibraryType == 'BoxSet':
                            ItemsBoxSet.append((Id, LibraryData))
                        elif LibraryType == 'MusicVideo':
                            ItemsMusicVideo.append((Id, LibraryData))
                        elif LibraryType == 'Series':
                            ItemsSeries.append((Id, LibraryData))
                        elif LibraryType == 'Episode':
                            ItemsEpisode.append((Id, LibraryData))
                        elif LibraryType == 'MusicAlbum':
                            ItemsMusicAlbum.append((Id, LibraryData))
                        elif LibraryType == 'MusicArtist':
                            ItemsMusicArtist.append((Id, LibraryData))
                        elif LibraryType == 'Audio':
                            ItemsAudio.append((Id, LibraryData))
                        elif LibraryType == 'AlbumArtist':
                            ItemsAlbumArtist.append((Id, LibraryData))
                        elif LibraryType == 'Season':
                            ItemsSeason.append((Id, LibraryData))

                        Counter += 1
                        ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                        progress_updates.update(ProgressValue, message="%s: prepare sync items" % Utils.Translate(33178))

                    Counter = 0

                    if ItemsMovie or ItemsBoxSet or ItemsMusicVideo or ItemsSeries or ItemsSeason or ItemsEpisode:
                        with db_open.io(Utils.DatabaseFiles, "video", True) as kodidb:
                            ContentObj = core.movies.Movies(self.EmbyServer, embydb, kodidb)
                            Update = False

                            for Id, LibraryData in ItemsMovie:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Movie')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsBoxSet:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'BoxSet')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            ContentObj = core.musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb)

                            for Id, LibraryData in ItemsMusicVideo:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicVideo')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            ContentObj = core.tvshows.TVShows(self.EmbyServer, embydb, kodidb)

                            for Id, LibraryData in ItemsSeries:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Series')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsSeason:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Season')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsEpisode:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, True, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Episode')

                                if self.CheckPause("update", progress_updates):
                                    return False

                        if Update:
                            xbmc.executebuiltin('UpdateLibrary(video)')

                    if ItemsMusicArtist or ItemsAlbumArtist or ItemsMusicAlbum or ItemsAudio:
                        with db_open.io(Utils.DatabaseFiles, "music", True) as kodidb:
                            ContentObj = core.music.Music(self.EmbyServer, embydb, kodidb)
                            Update = False

                            for Id, LibraryData in ItemsMusicArtist:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, False, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicArtist')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsAlbumArtist:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, False, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'AlbumArtist')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsMusicAlbum:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, False, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'MusicAlbum')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            for Id, LibraryData in ItemsAudio:
                                Update = True
                                Counter += 1
                                ProgressValue = int((float(Counter) / float(ItemCounter)) * 100)
                                self.worker_update_process_item(Id, False, embydb, ContentObj, LibraryData, progress_updates, ProgressValue, 'Audio')

                                if self.CheckPause("update", progress_updates):
                                    return False

                            if Update:
                                kodidb.clean_music()

                        if Update:
                            xbmc.executebuiltin('UpdateLibrary(music)')

                embydb.get_update_LastIncrementalSync(Utils.currenttime(), "realtime")

            progress_updates.close()
            LOG.info("--<[ worker update completed ]")
            self.worker_running["update"] = False
            return True

    def worker_remove(self):
        if self.worker_running["remove"]:
            LOG.info("[ worker remove in progress ]")
            return False

        if Utils.SyncPause:
            return False

        LOG.info("[ worker remove started ]")

        with DBLock:
            if Utils.SyncPause:
                return False

            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                while True:
                    RemoveItems = embydb.get_RemoveItem()

                    if not RemoveItems:
                        if self.worker_running["remove"]:
                            break

                        LOG.info("[ worker remove queue size ] 0")
                        return True

                    if not self.worker_running["remove"]:
                        progress_updates = xbmcgui.DialogProgressBG()
                        progress_updates.create("Emby", Utils.Translate(33178))
                        self.worker_running["remove"] = True

                    #Sort Items
                    RemoveItemsAudio = []
                    RemoveItemsVideo = []

                    for RemoveItem in RemoveItems:
                        Id = RemoveItem[0]
                        LibraryType = RemoveItem[1]
                        LibraryId = RemoveItem[2]

                        if not LibraryType:
                            LibraryType = embydb.get_media_by_id(Id)

                        if LibraryType:
                            if LibraryType in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                                RemoveItemsAudio.append([Id, LibraryType, LibraryId])
                            else:
                                RemoveItemsVideo.append([Id, LibraryType, LibraryId])
                        else:
                            LOG.info("Could not find media %s in the emby database." % Id)
                            embydb.delete_RemoveItem(Id)

                    ItemCounter = len(RemoveItemsAudio) + len(RemoveItemsVideo)
                    Counter = 0
                    LOG.info("[ worker remove queue size ] %s" % ItemCounter)

                    if RemoveItemsVideo:
                        with db_open.io(Utils.DatabaseFiles, "video", True) as kodidb:
                            for RemoveItemVideo in RemoveItemsVideo:
                                Counter += 1

                                if self.CheckPause("remove", progress_updates):
                                    return False

                                Value = int((float(Counter) / float(ItemCounter)) * 100)
                                progress_updates.update(Value, message="%s: %s" % (Utils.Translate(33178), "Remove"))
                                embydb.delete_RemoveItem(RemoveItemVideo[0])

                                if RemoveItemVideo[1] in ('Movie', 'BoxSet', 'SpecialFeature'):
                                    core.movies.Movies(self.EmbyServer, embydb, kodidb).remove(RemoveItemVideo[0])
                                elif RemoveItemVideo[1] == 'MusicVideo':
                                    core.musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb).remove(RemoveItemVideo[0])
                                elif RemoveItemVideo[1] in ('TVShow', 'Series', 'Season', 'Episode'):
                                    core.tvshows.TVShows(self.EmbyServer, embydb, kodidb).remove(RemoveItemVideo[0])

                        xbmc.executebuiltin('UpdateLibrary(video)')

                    if RemoveItemsAudio:
                        with db_open.io(Utils.DatabaseFiles, "music", True) as kodidb:
                            for RemoveItemAudio in RemoveItemsAudio:
                                Counter += 1

                                if self.CheckPause("remove", progress_updates):
                                    return False

                                Value = int((float(Counter) / float(ItemCounter)) * 100)
                                progress_updates.update(Value, message="%s: %s" % (Utils.Translate(33178), "Remove"))
                                embydb.delete_RemoveItem(RemoveItemAudio[0])
                                core.music.Music(self.EmbyServer, embydb, kodidb).remove(RemoveItemAudio[0], RemoveItemAudio[2])
                                kodidb.clean_music()

                        xbmc.executebuiltin('UpdateLibrary(music)')

                embydb.get_update_LastIncrementalSync(Utils.currenttime(), "realtime")

            progress_updates.close()
            LOG.info("--<[ worker remove completed ]")
            self.worker_running["remove"] = False
            return True

    def worker_library(self):
        if self.worker_running["library"]:
            LOG.info("[ worker library in progress ]")
            return False

        if Utils.SyncPause:
            return False

        LOG.info("[ worker library started ]")

        with DBLock:
            if Utils.SyncPause:
                return False

            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                while True:
                    SyncItems = embydb.get_PendingSync()

                    if not SyncItems:
                        if self.worker_running["library"]:
                            break

                        LOG.info("[ worker library queue size ] 0")
                        return True

                    if not self.worker_running["library"]:
                        progress_updates = xbmcgui.DialogProgressBG()
                        progress_updates.create("Emby", "%s %s" % (Utils.Translate('gathering'), "Add library"))
                        self.worker_running["library"] = True

                    ItemCounter = len(SyncItems)
                    LOG.info("[ worker library queue size ] %s" % ItemCounter)

                    for SyncItem in SyncItems:
                        library_id = SyncItem[0]
                        library_type = SyncItem[1]
                        library_name = SyncItem[2]
                        LibraryData = {"Id": library_id, "Name": library_name}
                        self.Whitelist = embydb.add_Whitelist(library_id, library_type, library_name)

                        if SyncItem[3]:
                            RestorePoint = Utils.StringToDict(SyncItem[3])
                        else:
                            RestorePoint = {}

                        if library_type not in ('music', 'audiobooks', 'podcasts', 'tvshows'):
                            SubContent = MediaEmbyMappedSubContent[library_type]
                            TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, SubContent))

                            with db_open.io(Utils.DatabaseFiles, 'video', True) as videodb:
                                if library_type in ("movies", "homevideos"):
                                    DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).movie
                                elif library_type == "boxsets":
                                    DBObject = core.movies.Movies(self.EmbyServer, embydb, videodb).boxset
                                elif library_type == "musicvideos":
                                    DBObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb).musicvideo

                                if self.CheckPause("library", progress_updates):
                                    return False

                                for items in self.EmbyServer.API.get_itemsSync(library_id, SubContent, False, RestorePoint):
                                    RestorePoint = items['RestorePoint']['params']
                                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                                    start_index = RestorePoint['StartIndex']

                                    for index, Item in enumerate(items['Items']):
                                        ProgressValue = int((float(start_index + index) / TotalRecords) * 100)
                                        progress_updates.update(ProgressValue, heading="Emby: %s" % library_name, message=Item['Name'])
                                        DBObject(Item, LibraryData)

                                        if self.CheckPause("library", progress_updates):
                                            return False

                            xbmc.executebuiltin('UpdateLibrary(video)')
                        elif library_type == 'tvshows': #stacked sync: tv-shows -> season/episode
                            TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "Series"))

                            with db_open.io(Utils.DatabaseFiles, 'video', True) as videodb:
                                DBObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb)

                                for items in self.EmbyServer.API.get_itemsSync(library_id, 'Series', False, RestorePoint):
                                    RestorePoint = items['RestorePoint']['params']
                                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))
                                    start_index = RestorePoint['StartIndex']

                                    for index, tvshow in enumerate(items['Items']):
                                        percent = int((float(start_index + index) / TotalRecords) * 100)
                                        progress_updates.update(percent, heading="Emby: %s" % library_name, message="TVShow: %s" % tvshow['Name'])
                                        DBObject.tvshow(tvshow, LibraryData)
                                        Seasons = []
                                        Episodes = []

                                        if self.CheckPause("library", progress_updates):
                                            return False

                                        for itemsContent in self.EmbyServer.API.get_itemsSync(tvshow['Id'], "Season,Episode", False, {}):
                                            # Sort
                                            for item in itemsContent['Items']:
                                                if item["Type"] == "Season":
                                                    Seasons.append(item)
                                                else:
                                                    Episodes.append(item)

                                            if self.CheckPause("library", progress_updates):
                                                return False

                                        for Season in Seasons:
                                            progress_updates.update(percent, heading="Emby: %s" % library_name, message="Season: %s / TVShow: %s" % (Season['Name'], tvshow['Name']))
                                            DBObject.season(Season, LibraryData)

                                            if self.CheckPause("library", progress_updates):
                                                return False

                                        for Episode in Episodes:
                                            progress_updates.update(percent, heading="Emby: %s" % library_name, message="Episode: %s / TVShow: %s" % (Episode['Name'], tvshow['Name']))
                                            DBObject.episode(Episode, LibraryData)

                                            if self.CheckPause("library", progress_updates):
                                                return False

                            xbmc.executebuiltin('UpdateLibrary(video)')
                        else:  #  Sync only if artist is valid (performance)
                            with db_open.io(Utils.DatabaseFiles, 'music', True) as musicdb:
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

                                            if self.CheckPause("library", progress_updates):
                                                return False
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
                                                DBObject.artist(Item, LibraryData)

                                                if self.CheckPause("library", progress_updates):
                                                    return False

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

                                                if self.CheckPause("library", progress_updates):
                                                    return False

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

                                                if self.CheckPause("library", progress_updates):
                                                    return False

                            xbmc.executebuiltin('UpdateLibrary(music)')

                        embydb.remove_PendingSync(library_id, library_type, library_name)

            progress_updates.close()
            self.EmbyServer.Views.update_nodes(True)
            xbmc.sleep(1000)  # give Kodi time for updates
            LOG.info("[ reload skin ]")
            xbmc.executebuiltin('ReloadSkin()')
            LOG.info("--<[ worker library completed ]")
            self.worker_running["library"] = False
            return True

    def RunJobs(self):
        if self.worker_remove():
            if self.worker_update():
                if self.worker_userdata():
                    self.worker_library()

    def CheckPause(self, Id, progress_updates):
        if Utils.SyncPause:
            LOG.info("[ worker %s paused ]" % Id)
            self.worker_running[Id] = False

            if progress_updates:
                progress_updates.close()

            return True

        return False

    def fast_sync(self, plugin):
        UpdateData = []
        result = {}
        LOG.info("-->[ retrieve changes ] %s / %s" % (self.LastRealtimeSync, self.LastStartSync))

        for LibraryId, library_type, library_name in self.Whitelist:
            if LibraryId not in self.EmbyServer.Views.ViewItems:
                LOG.info("[ fast_sync remove library %s ]" % LibraryId)
                continue

            if library_type == "musicvideos":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "MusicVideo", False, {'MinDateLastSaved': self.LastRealtimeSync})
            elif library_type == "movies":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Movie", False, {'MinDateLastSaved': self.LastRealtimeSync})
            elif library_type == "homevideos":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Video", False, {'MinDateLastSaved': self.LastRealtimeSync})
            elif library_type == "boxsets":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "BoxSet", False, {'MinDateLastSaved': self.LastStartSync})
            elif library_type == "tvshows":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Series,Season,Episode", False, {'MinDateLastSaved': self.LastRealtimeSync})
            elif library_type in ("music", "audiobooks"):
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "MusicArtist,MusicAlbum,Audio", False, {'MinDateLastSaved': self.LastRealtimeSync})
            elif library_type == "podcasts":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "MusicArtist,MusicAlbum,Audio", False, {'MinDateLastSaved': self.LastStartSync})

            for data in result:
                for item in data['Items']:
                    UpdateData.append((item['Id'], LibraryId, library_name, item['Type']))

            result = {}

            if library_type == "musicvideos":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "MusicVideo", False, {'MinDateLastSavedForUser': self.LastRealtimeSync})
            elif library_type == "tvshows":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Episode", False, {'MinDateLastSavedForUser': self.LastRealtimeSync})
            elif library_type == "movies":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Movie", False, {'MinDateLastSavedForUser': self.LastRealtimeSync})
            elif library_type == "homevideos":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Video", False, {'MinDateLastSavedForUser': self.LastRealtimeSync})
            elif library_type == "boxsets":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "BoxSet", False, {'MinDateLastSavedForUser': self.LastStartSync})
            elif library_type in ("music", "audiobooks"):
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Audio", False, {'MinDateLastSavedForUser': self.LastRealtimeSync})
            elif library_type == "podcasts":
                result = self.EmbyServer.API.get_itemsSync(LibraryId, "Audio", False, {'MinDateLastSavedForUser': self.LastStartSync})

            for data in result:
                for item in data['Items']:
                    UpdateData.append((item['Id'], LibraryId, library_name, item['Type']))

        self.updated(UpdateData)

        if plugin:
            result = self.EmbyServer.API.get_sync_queue(self.LastRealtimeSync, None)  # Kodi companion plugin
            self.removed(result['ItemsRemoved'])

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

    def refresh_boxsets(self):
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
        SyncPauseState = Utils.SyncPause
        Utils.SyncPause = True

        with DBLock:
            with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                for library_id, library_type, library_name in self.Whitelist:
                    if library_type == "boxsets":
                        self.Whitelist = embydb.remove_Whitelist(library_id, library_type, library_name)
                        embydb.add_PendingSync(library_id, "boxsets", library_name, None)

        Utils.SyncPause = SyncPauseState
        threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()

    def add_library(self, library_ids):
        if library_ids:
            SyncPauseState = Utils.SyncPause
            Utils.SyncPause = True

            with DBLock:
                with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
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

            Utils.SyncPause = SyncPauseState
            threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()

    # Remove library by their id from the Kodi database
    def remove_library(self, library_ids):
        if library_ids:
            SyncPauseState = Utils.SyncPause
            Utils.SyncPause = True
            RemoveItems = []

            with DBLock:
                with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
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

            Utils.SyncPause = SyncPauseState
            self.removed(RemoveItems)

    # Add item_id to userdata queue
    def userdata(self, Data):
        if Data:
            with LockQueue:
                SyncPauseState = Utils.SyncPause
                Utils.SyncPause = True

                with DBLock:
                    with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                        for item in Data:
                            embydb.add_Userdata(str(item))

                Utils.SyncPause = SyncPauseState
                threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()

    # Add item_id to updated queue
    def updated(self, Data):
        if Data:
            with LockQueue:
                SyncPauseState = Utils.SyncPause
                Utils.SyncPause = True

                with DBLock:
                    with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                        for item in Data:
                            if isinstance(item, tuple):
                                EmbyId = item[0]
                                LibraryId = item[1]
                                LibraryName = item[2]
                                LibraryType = item[3]
                            else:  # update via Websocket
                                if item.isnumeric():
                                    EmbyId = item
                                    LibraryId = None
                                    LibraryName = None
                                    LibraryType = None
                                else:
                                    LOG.info("Skip invalid update item: %s" % item)
                                    continue

                            embydb.add_UpdateItem(EmbyId, LibraryId, LibraryName, LibraryType)

                Utils.SyncPause = SyncPauseState
                threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()

    # Add item_id to removed queue
    def removed(self, Data):
        if Data:
            with LockQueue:
                SyncPauseState = Utils.SyncPause
                Utils.SyncPause = True

                with DBLock:
                    with db_open.io(Utils.DatabaseFiles, self.EmbyServer.server_id, True) as embydb:
                        for item in Data:
                            if isinstance(item, tuple):
                                EmbyId = item[0]
                                EmbyType = item[1]
                                LibraryId = item[2]
                            else:  # update via Websocket
                                if item.isnumeric():
                                    EmbyId = item
                                    EmbyType = None
                                    LibraryId = None
                                else:
                                    LOG.info("Skip invalid remove item: %s" % item)
                                    continue

                            embydb.add_RemoveItem(EmbyId, EmbyType, LibraryId)

                Utils.SyncPause = SyncPauseState
                threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()

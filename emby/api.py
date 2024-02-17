from _thread import start_new_thread
import json
import xbmc
from helper import utils, queue
from database import dbio
from . import listitem

EmbyFields = {
    "musicartist": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicalbum": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "Studios", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "audio": ("Genres", "SortName", "ProductionYear", "DateCreated", "MediaStreams", "ProviderIds", "Overview", "Path", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "movie": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "trailer": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags"),
    "boxset": ("Overview", "SortName", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "series": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProviderIds", "ParentId", "Status", "PresentationUniqueKey", "OriginalTitle", "Tags", "LocalTrailerCount", "RemoteTrailers", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "season": ("PresentationUniqueKey", "SortName", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "episode": ("SpecialEpisodeNumbers", "Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicvideo": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "video": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photo": ("Path", "SortName", "ProductionYear", "ParentId", "PremiereDate", "Width", "Height", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photoalbum": ("Path", "SortName", "Taglines", "DateCreated", "ShortOverview", "ProductionLocations", "Tags", "ParentId", "OriginalTitle", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "tvchannel": ("Genres", "SortName", "Taglines", "DateCreated", "Overview", "MediaSources", "Tags", "MediaStreams", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "folder": ("Path",),
    "playlist": ("SortName", "Overview", "Path"),
    "genre": (),
    "musicgenre": (),
    "person": (),
    "tag": (),
    "channel": (),
    "collectionfolder": (),
    "studio": (),
    "all": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate")
}


class API:
    def __init__(self, EmbyServer):
        self.DynamicListsRemoveFields = ()
        self.EmbyServer = EmbyServer
        self.update_settings()
        self.ProcessProgress = {}

    def update_settings(self):
        self.DynamicListsRemoveFields = ()

        if not utils.getDateCreated:
            self.DynamicListsRemoveFields += ("DateCreated",)

        if not utils.getGenres:
            self.DynamicListsRemoveFields += ("Genres",)

        if not utils.getStudios:
            self.DynamicListsRemoveFields += ("Studios",)

        if not utils.getTaglines:
            self.DynamicListsRemoveFields += ("Taglines",)

        if not utils.getOverview:
            self.DynamicListsRemoveFields += ("Overview",)

        if not utils.getProductionLocations:
            self.DynamicListsRemoveFields += ("ProductionLocations",)

        if not utils.getCast:
            self.DynamicListsRemoveFields += ("People",)

    def open_livestream(self, Id):
        PlaybackInfoData = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], "IsPlayback": "true", "AutoOpenLiveStream": "true"}, 'type': "POST", 'handler': f"Items/{Id}/PlaybackInfo"}, True, False)

        if 'MediaSources' in PlaybackInfoData and PlaybackInfoData['MediaSources']:
            MediaSourceId = PlaybackInfoData['MediaSources'][0]['Id']
            LiveStreamId = PlaybackInfoData['MediaSources'][0].get('LiveStreamId', None)
            Container = PlaybackInfoData['MediaSources'][0].get('Container', "")
        else:
            MediaSourceId = None
            LiveStreamId = None
            Container = None

        return MediaSourceId, LiveStreamId, PlaybackInfoData['PlaySessionId'], Container

    def get_Items_dynamic(self, ParentId, MediaTypes, Recursive, Extra, Resume, LibraryId):
        CustomLimit = False

        if Resume:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Resume"
        else:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items"

        ItemsFullQuery = 10000 * [()] # pre allocate memory
        ItemIndex = 0

        for MediaType in MediaTypes:
            Limit = get_Limit(MediaType)
            Params = {'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit}

            if ParentId:
                Params['ParentId'] = ParentId

            if MediaType != "All":
                Params['IncludeItemTypes'] = MediaType

            if Extra:
                CustomLimit = bool("Limit" in Extra)
                Params.update(Extra)

            embydb = None
            videodb = None
            musicdb = None

            for BasicItem in self.get_Items_Custom(Request, Params, CustomLimit):
                KodiItem = ({}, "")
                KodiDB = ""

                # Try to find content by internal database first, before query Emby server
                if BasicItem['Type'] not in ("Movie", "Video", "Series", "Season", "Episode", "MusicVideo", "MusicArtist", "MusicAlbum", "Audio"):
                    if ItemIndex % 10000 == 0: # modulo 10000
                        ItemsFullQuery += 10000 * [()] # pre allocate memory

                    ItemsFullQuery[ItemIndex] = (BasicItem['Type'], BasicItem['Id'], BasicItem)
                    ItemIndex += 1
                    continue

                if not embydb:
                    embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "get_Items_dynamic")
                    videodb = dbio.DBOpenRO("video", "get_Items_dynamic")
                    musicdb = dbio.DBOpenRO("music", "get_Items_dynamic")

                if BasicItem['Type'] in ("MusicArtist", "MusicAlbum", "Audio") and LibraryId != "0":
                    KodiId, KodiDB = embydb.get_KodiId_by_EmbyId_and_LibraryId(BasicItem['Id'], BasicItem['Type'], LibraryId, self.EmbyServer)
                else:
                    KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(BasicItem['Id'], BasicItem['Type'])

                if KodiId:
                    if BasicItem['Type'] in ("Movie", "Video"):
                        KodiItem = (videodb.get_movie_metadata_for_listitem(KodiId, None), BasicItem['Type'])
                    elif BasicItem['Type'] == "Series":
                        KodiItem = (videodb.get_tvshows_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Season":
                        KodiItem = (videodb.get_season_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Episode":
                        KodiItem = (videodb.get_episode_metadata_for_listitem(KodiId, None), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicVideo":
                        KodiItem = (videodb.get_musicvideos_metadata_for_listitem(KodiId, None), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicArtist":
                        if KodiDB == "music":
                            KodiItem = (musicdb.get_artist_metadata_for_listitem(KodiId), BasicItem['Type'])
                        else:
                            KodiItem = (videodb.get_actor_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicAlbum":
                        KodiItem = (musicdb.get_album_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Audio":
                        KodiItem = (musicdb.get_song_metadata_for_listitem(KodiId), BasicItem['Type'])
                else:
                    if ItemIndex % 10000 == 0: # modulo 10000
                        ItemsFullQuery += 10000 * [()] # pre allocate memory

                    ItemsFullQuery[ItemIndex] = (BasicItem['Type'], BasicItem['Id'], BasicItem)
                    ItemIndex += 1

                if KodiItem[0]:
                    isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem[0])

                    if 'pathandfilename' in KodiItem[0]:
                        yield {"ListItem": ListItem, "Path": KodiItem[0]['pathandfilename'], "isFolder": isFolder, "Type": KodiItem[1]}
                    else:
                        yield {"ListItem": ListItem, "Path": KodiItem[0]['path'], "isFolder": isFolder, "Type": KodiItem[1]}

            if embydb:
                dbio.DBCloseRO("video", "get_Items_dynamic")
                dbio.DBCloseRO("music", "get_Items_dynamic")
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "get_Items_dynamic")

        SortItems = {'Movie': (), 'Video': (), 'BoxSet': (), 'MusicVideo': (), 'Series': (), 'Episode': (), 'MusicAlbum': (), 'MusicArtist': (), 'AlbumArtist': (), 'Season': (), 'Folder': (), 'Audio': (), 'Genre': (), 'MusicGenre': (), 'Tag': (), 'Person': (), 'Studio': (), 'Playlist': (), 'Photo': (), 'PhotoAlbum': (), 'Trailer': (), 'Channel': (), 'CollectionFolder': ()}

        for ItemFullQuery in ItemsFullQuery:
            if not ItemFullQuery:
                continue

            SortItems[ItemFullQuery[0]] += ((ItemFullQuery[1], ItemFullQuery[2]),)

        for Type, ItemData in list(SortItems.items()):
            if ItemData:
                if EmbyFields[Type.lower()]:
                    yield from self.get_Items_Ids(list(dict(ItemData).keys()), [Type], True, False, False, "")
                else:
                    for Item in ItemData:
                        yield Item[1]

    def get_Items_Ids(self, Ids, MediaTypes, Dynamic, Basic, ProcessProgressId, LibraryId):
        ItemsQueue = queue.Queue()
        Fields = []

        if not Basic:
            for MediaType in MediaTypes:
                Fields += EmbyFields[MediaType.lower()]

            #Dynamic list query, remove fields to improve performance
            if Dynamic:
                if "Series" in MediaTypes or "Season" in MediaTypes:
                    Fields += ("RecursiveItemCount", "ChildCount")

                for DynamicListsRemoveField in self.DynamicListsRemoveFields:
                    if DynamicListsRemoveField in Fields:
                        Fields.remove(DynamicListsRemoveField)

            Fields = ",".join(list(dict.fromkeys(Fields))) # remove duplicates and join into string
        else:
            Fields = None

        if len(MediaTypes) == 1:
            Params = {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'IncludeItemTypes': MediaTypes[0]}
        else:
            Params = {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}

        start_new_thread(self.async_get_Items_Ids, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, Params, Ids, Dynamic, ProcessProgressId, LibraryId))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                return

            yield from Items
            del Items

    def async_get_Items_Ids(self, Request, ItemsQueue, Params, Ids, Dynamic, ProcessProgressId, LibraryId):
        xbmc.log("EMBY.emby.api: THREAD: --->[ load Item by Ids ]", 0) # LOGDEBUG
        Index = 0
        IncomingData = ()

        while Ids:
            MaxURILenght = 1500 # Uri lenght limitation
            IdsIndex = 100

            while len(",".join(Ids[:IdsIndex])) < MaxURILenght and IdsIndex < len(Ids):
                IdsIndex += 5

            Params['Ids'] = ",".join(Ids[:IdsIndex])  # Chunks of 100+X -> due to URI lenght limitation, more than 100+X Ids not possible to request (HTTP error 414)
            Ids = Ids[IdsIndex:]

            if not Dynamic and LibraryId and LibraryId != "unknown": # Kodi start updates
                Found = False

                if Params['IncludeItemTypes'] in ("BoxSet", "MusicArtist", "MusicAlbum", "Genre", "MusicGenre", "Tag", "Person"): # workaround for Emby 4.X version
                    Params.update({'Recursive': False})
                elif Params['IncludeItemTypes'] == "Playlist": # workaround for Emby 4.7.X version
                    Params.update({'Recursive': True})
                else:
                    Params.update({'Recursive': True, 'ParentId': LibraryId})

                IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)

                if 'Items' in IncomingData:
                    for Item in IncomingData['Items']:
                        Found = True
                        Item['LibraryId'] = LibraryId
                        ItemsQueue.put(Item)
                        Index += 1

                if not Found or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Item by Ids ] no items found or shutdown (regular query)", 0) # LOGDEBUG
                    return
            elif not Dynamic: # realtime updates via websocket
                for WhitelistLibraryId in self.EmbyServer.library.WhitelistUnique:
                    BoxSetParentIds = ()
                    Params.update({'Recursive': True, 'ParentId': WhitelistLibraryId})
                    IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)

                    if 'Items' in IncomingData:
                        for Item in IncomingData['Items']:
                            if 'ParentId' in Item:
                                BoxSetParentIds += (Item['ParentId'],)

                            Item['LibraryId'] = WhitelistLibraryId
                            ItemsQueue.put(Item)
                            Index += 1

                        if len(IncomingData['Items']) == len(Params['Ids'].split(",")): # All data received, no need to check additional libraries
                            break

                    if BoxSetParentIds:
                        BoxsetDoublesCheck = ()

                        for BoxSetParentId in BoxSetParentIds:
                            ParamsBoxSet = {'ParentId': BoxSetParentId, 'Fields': EmbyFields['boxset'], 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'IncludeItemTypes': "BoxSet", 'Recursive': True}
                            IncomingData = self.EmbyServer.http.request({'params': ParamsBoxSet, 'type': "GET", 'handler': Request}, False, False)

                            if 'Items' in IncomingData:
                                for Item in IncomingData['Items']:
                                    if Item['Type'] == "BoxSet":
                                        Item['LibraryId'] = WhitelistLibraryId

                                        if Item not in BoxsetDoublesCheck:
                                            BoxsetDoublesCheck += (Item,)
                                            ItemsQueue.put(Item)

                        del BoxsetDoublesCheck

                    del BoxSetParentIds

                    if utils.SystemShutdown:
                        ItemsQueue.put("QUIT")
                        del IncomingData  # release memory
                        xbmc.log("EMBY.emby.api: THREAD: ---<[ load Item by Ids ] shutdown (websocket query)", 0) # LOGDEBUG
                        return
            else: # dynamic node query
                IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)

                if utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Item by Ids ] shutdown (dynamic)", 0) # LOGDEBUG
                    return

                if 'Items' in IncomingData and IncomingData['Items']:
                    ItemsQueue.put(IncomingData['Items'])
                    Index += len(IncomingData['Items'])

            if not self.async_throttle_queries(Index, 10000, ProcessProgressId):
                ItemsQueue.put("QUIT")

        del IncomingData  # release memory
        ItemsQueue.put("QUIT")
        xbmc.log("EMBY.emby.api: THREAD: ---<[ load Item by Ids ]", 0) # LOGDEBUG

    def async_throttle_queries(self, Index, Limit, ProcessProgressId):
        # Throttle queries -> give Kodi time to catch up
        if ProcessProgressId and ProcessProgressId in self.ProcessProgress:
            ProcessLimit = Index - 2 * Limit

            while ProcessLimit > self.ProcessProgress[ProcessProgressId]:
                if utils.sleep(2) or self.ProcessProgress[ProcessProgressId] == -1: # Cancel
                    return False

                xbmc.log(f"EMBY.emby.api: Throttle queries {ProcessLimit} / {ProcessProgressId} / {self.ProcessProgress[ProcessProgressId]}", 1) # LOGINFO

        return True

    def get_Items_Custom(self, Request, Params, CustomLimit):
        ItemsQueue = queue.Queue()
        start_new_thread(self.async_get_Items, (Request, ItemsQueue, CustomLimit, Params))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                return

            yield from Items
            del Items

    def get_Items(self, ParentId, MediaTypes, Basic, Recursive, Extra, ProcessProgressId=""):
        CustomLimit = False
        ItemsQueue = queue.Queue()

        for MediaType in MediaTypes:
            Limit = get_Limit(MediaType)
            Fields = self.get_Fields(MediaType, Basic, False)
            Params = {'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit, 'Fields': Fields}

            if MediaType != "All":
                Params['IncludeItemTypes'] = MediaType

            if str(ParentId) != "999999999" and MediaType != "Playlist": # global libraries or playlist (workaround Emby 4.7.X version)
                Params['ParentId'] = ParentId

            if Extra:
                CustomLimit = bool("Limit" in Extra)
                Params.update(Extra)

            start_new_thread(self.async_get_Items, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, CustomLimit, Params, ProcessProgressId))

            while True:
                Items = ItemsQueue.getall()

                if utils.SystemShutdown:
                    return

                if Items[-1] == "QUIT":
                    yield from Items[:-1]
                    break

                yield from Items
                del Items  # release memory

    def get_channelprogram(self):
        Limit = get_Limit("livetv")
        Params = {'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': "Overview", 'EnableTotalRecordCount': False, 'Limit': Limit}
        ItemsQueue = queue.Queue()
        start_new_thread(self.async_get_Items, ("LiveTv/Programs", ItemsQueue, False, Params))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                del Items
                return

            yield from Items
            del Items

    def get_recommendations(self, ParentId):
        Fields = self.get_Fields("movie", False, True)
        Params = {'ParentId': ParentId, 'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': Fields, 'EnableTotalRecordCount': False, 'Recursive': True}
        IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': "Movies/Recommendations"}, False, False)
        Items = []

        for Data in IncomingData:
            if 'Items' in Data:
                Items += Data['Items']

        return Items

    def async_get_Items(self, Request, ItemsQueue, CustomLimit, Params, ProcessProgressId=""):
        xbmc.log("EMBY.emby.api: THREAD: --->[ load Items ]", 0) # LOGDEBUG
        Index = 0
        ItemCounter = 0
        Limit = Params['Limit']

        while True:
            Params['StartIndex'] = Index
            IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)
            DirectItems = Request.lower().find("latest") != -1

            if DirectItems:
                if not IncomingData or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (latest / no items found or shutdown)", 0) # LOGDEBUG
                    return

                ItemsQueue.put(IncomingData)
                ItemCounter += len(IncomingData)
            else:
                if 'Items' not in IncomingData or not IncomingData['Items'] or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (no items found or shutdown)", 0) # LOGDEBUG
                    return

                ItemsQueue.put(IncomingData['Items'])
                ItemCounter += len(IncomingData['Items'])

            del IncomingData  # release memory

            if CustomLimit:
                ItemsQueue.put("QUIT")
                xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (limit reached)", 0) # LOGDEBUG
                return

            if not self.async_throttle_queries(Index, Limit, ProcessProgressId):
                ItemsQueue.put("QUIT")

            Index += Limit

        xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ]", 0) # LOGDEBUG

    def get_Item(self, Ids, MediaTypes, Dynamic, Basic, Specials=False):
        for MediaType in MediaTypes:
            Fields = self.get_Fields(MediaType, Basic, Dynamic)

            if Specials: # Bugfix workaround
                Data = self.EmbyServer.http.request({'params': {'Ids': Ids, 'Fields': Fields, 'IncludeItemTypes': 'Workaround', 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)
            else:
                Data = self.EmbyServer.http.request({'params': {'Ids': Ids, 'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

            if 'Items' in Data:
                if Data['Items']:
                    return Data['Items'][0]

        return {}

    def get_TotalRecords(self, parent_id, item_type, Extra):
        Params = {'ParentId': parent_id, 'IncludeItemTypes': item_type, 'EnableTotalRecordCount': True, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': True, 'Limit': 1}

        if Extra:
            Params.update(Extra)

        Data = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if 'TotalRecordCount' in Data:
            return int(Data['TotalRecordCount'])

        return 0

    def get_timer(self, ProgramId):
        Data = self.EmbyServer.http.request({'params': {'programId': ProgramId}, 'type': "GET", 'handler': "LiveTv/Timers"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def set_timer(self, ProgramId):
        return self.EmbyServer.http.request({'data': json.dumps({'programId': ProgramId}), 'type': "POST", 'handler': "LiveTv/Timers"}, False, False)

    def delete_timer(self, TimerId):
        return self.EmbyServer.http.request({'type': "POST", 'handler': f"LiveTv/Timers/{TimerId}/Delete"}, False, False)

    def get_users(self, disabled, hidden):
        return self.EmbyServer.http.request({'params': {'IsDisabled': disabled, 'IsHidden': hidden}, 'type': "GET", 'handler': "Users"}, False, False)

    def get_public_users(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "Users/Public"}, False, False)

    def get_user(self, user_id):
        if not user_id:
            return self.EmbyServer.http.request({'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}"}, False, False)

        return self.EmbyServer.http.request({'type': "GET", 'handler': f"Users/{user_id}"}, False, False)

    def get_libraries(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "Library/VirtualFolders/Query"}, False, False)

    def get_views(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Views"}, False, False)

    def download_file(self, Download):
        self.EmbyServer.http.request({'type': "GET", 'handler': f"Items/{Download['Id']}/Download"}, False, True, False, False, False, Download)

    def get_Image_Binary(self, Id, ImageType, ImageIndex, ImageTag, UserImage=False):
        Params = {"EnableImageEnhancers": utils.enableCoverArt}

        if utils.compressArt:
            Params["Quality"] = utils.compressArtLevel

        if utils.ArtworkLimitations:
            Width = 100
            Height = 100

            if ImageType == "Primary":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationPrimary) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationPrimary) / 100
            elif ImageType == "Art":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationArt) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationArt) / 100
            elif ImageType == "Banner":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationBanner) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationBanner) / 100
            elif ImageType == "Disc":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationDisc) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationDisc) / 100
            elif ImageType == "Logo":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationLogo) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationLogo) / 100
            elif ImageType == "Thumb":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationThumb) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationThumb) / 100
            elif ImageType == "Backdrop":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationBackdrop) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationBackdrop) / 100
            elif ImageType == "Chapter":
                Width = utils.ScreenResolution[0] * int(utils.ArtworkLimitationChapter) / 100
                Height = utils.ScreenResolution[1] * int(utils.ArtworkLimitationChapter) / 100

            Params["MaxWidth"] = int(Width)
            Params["MaxHeight"] = int(Height)

        if UserImage:
            Params["Format"] = "original"
            BinaryData, Headers = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Users/{Id}/Images/{ImageType}"}, False, True, True)
        else:
            if ImageTag:
                Params["tag"] = ImageTag

            BinaryData, Headers = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Items/{Id}/Images/{ImageType}/{ImageIndex}"}, False, True, True)

        if 'Content-Type' in Headers:
            ContentType = Headers['Content-Type']

            if ContentType == "image/jpeg":
                FileExtension = "jpg"
            elif ContentType == "image/png":
                FileExtension = "png"
            elif ContentType == "image/gif":
                FileExtension = "gif"
            elif ContentType == "image/webp":
                FileExtension = "webp"
            elif ContentType == "image/apng":
                FileExtension = "apng"
            elif ContentType == "image/avif":
                FileExtension = "avif"
            elif ContentType == "image/svg+xml":
                FileExtension = "svg"
            else:
                FileExtension = "ukn"
        else:
            FileExtension = "ukn"
            ContentType = "ukn"

        return BinaryData, ContentType, FileExtension

    def get_device(self):
        return self.EmbyServer.http.request({'params': {'DeviceId': self.EmbyServer.ServerData['DeviceId']}, 'type': "GET", 'handler': "Sessions"}, False, False)

    def get_active_sessions(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "Sessions"}, False, False)

    def send_text_msg(self, SessionId, Header, Text, Priority=False, LastWill=False):
        self.EmbyServer.http.request({'data': json.dumps({'Header': f"{Header}", 'Text': f"{Text}"}), 'type': "POST", 'handler': f"Sessions/{SessionId}/Message"}, Priority, False, True, LastWill, Priority)

    def send_play(self, SessionId, ItemId, PlayCommand, StartPositionTicks, Priority=False):
        self.EmbyServer.http.request({'data': json.dumps({'ItemIds': f"{ItemId}", 'StartPositionTicks': f"{StartPositionTicks}", 'PlayCommand': f"{PlayCommand}"}), 'type': "POST", 'handler': f"Sessions/{SessionId}/Playing"}, Priority, False, True, False, Priority)

    def send_pause(self, SessionId, Priority=False):
        self.EmbyServer.http.request({'type': "POST", 'handler': f"Sessions/{SessionId}/Playing/Pause"}, Priority, False, True, False, Priority)

    def send_unpause(self, SessionId, Priority=False):
        self.EmbyServer.http.request({'type': "POST", 'handler': f"Sessions/{SessionId}/Playing/Unpause"}, Priority, False, True, False, Priority)

    def send_seek(self, SessionId, Position, Priority=False):
        self.EmbyServer.http.request({'data': json.dumps({'SeekPositionTicks': Position}), 'type': "POST", 'handler': f"Sessions/{SessionId}/Playing/Seek"}, Priority, False, True, False, Priority)

    def send_stop(self, SessionId, Priority=False):
        self.EmbyServer.http.request({'type': "POST", 'handler': f"Sessions/{SessionId}/Playing/Stop"}, Priority, False, True, False, Priority)

    def ping(self):
        self.EmbyServer.http.request({'type': "POST", 'handler': "System/Ping"}, False, False)

    def get_channels(self):
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'EnableImages': True, 'EnableUserData': True, 'Fields': EmbyFields['tvchannel']}, 'type': "GET", 'handler': "LiveTv/Channels"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_specialfeatures(self, Id):
        return self.EmbyServer.http.request({'params': {'Fields': "Path,MediaSources,PresentationUniqueKey", 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/SpecialFeatures"}, False, False)

    def get_intros(self, Id):
        Fields = EmbyFields["trailer"]
        return self.EmbyServer.http.request({'params': {'Fields': Fields, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/Intros"}, False, False)

    def get_additional_parts(self, Id):
        return self.EmbyServer.http.request({'params': {'Fields': "Path,MediaSources"}, 'type': "GET", 'handler': f"Videos/{Id}/AdditionalParts"}, False, False)

    def get_local_trailers(self, Id):
        Fields = EmbyFields["trailer"]
        return self.EmbyServer.http.request({'params': {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/LocalTrailers"}, False, False)

    def get_themes(self, Id, Songs, Videos):
        return self.EmbyServer.http.request({'params': {'Fields': "Path,MediaSources", 'UserId': self.EmbyServer.ServerData['UserId'], 'InheritFromParent': True, 'EnableThemeSongs': Songs, 'EnableThemeVideos': Videos, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Items/{Id}/ThemeMedia"}, False, False)

    def get_sync_queue(self, date):
        return self.EmbyServer.http.request({'params': {'LastUpdateDT': date}, 'type': "GET", 'handler': f"Emby.Kodi.SyncQueue/{self.EmbyServer.ServerData['UserId']}/GetItems"}, False, False)

    def get_system_info(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "System/Configuration"}, False, False)

    def set_progress(self, Id, Progress, PlayCount):
        Params = {"PlaybackPositionTicks": Progress}

        if PlayCount and PlayCount != -1:
            Params.update({"PlayCount": PlayCount, "Played": bool(PlayCount)})

        self.EmbyServer.http.request({'data': json.dumps(Params), 'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/UserData"}, False, False)

    def set_progress_upsync(self, Id, PlaybackPositionTicks, PlayCount, LastPlayedDate):
        Params = {"PlaybackPositionTicks": PlaybackPositionTicks, "LastPlayedDate": LastPlayedDate}

        if PlayCount and PlayCount != -1:
            Params.update({"PlayCount": PlayCount, "Played": bool(PlayCount)})

        self.EmbyServer.http.request({'data': json.dumps(Params), 'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/UserData"}, False, False)

    def set_played(self, Id, PlayCount):
        if PlayCount:
            self.EmbyServer.http.request({'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{Id}"}, False, False)
        else:
            self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{Id}"}, False, False)

    def refresh_item(self, Id):
        self.EmbyServer.http.request({'data': json.dumps({'Recursive': True, 'ImageRefreshMode': "FullRefresh", 'MetadataRefreshMode': "FullRefresh", 'ReplaceAllImages': False, 'ReplaceAllMetadata': True}), 'type': "POST", 'handler': f"Items/{Id}/Refresh"}, False, False)

    def favorite(self, Id, Add):
        if Add:
            self.EmbyServer.http.request({'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{Id}"}, False, False)
        else:
            self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{Id}"}, False, False)

    def post_capabilities(self, params):
        self.EmbyServer.http.request({'data': json.dumps(params), 'type': "POST", 'handler': "Sessions/Capabilities/Full"}, False, False)

    def session_add_user(self, session_id, user_id, option):
        if option:
            self.EmbyServer.http.request({'type': "POST", 'handler': f"Sessions/{session_id}/Users/{user_id}"}, False, False)
        else:
            self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Sessions/{session_id}/Users/{user_id}"}, False, False)

    def session_playing(self, params):
        self.EmbyServer.http.request({'data': json.dumps(params), 'type': "POST", 'handler': "Sessions/Playing"}, False, False)

    def session_progress(self, params):
        self.EmbyServer.http.request({'data': json.dumps(params), 'type': "POST", 'handler': "Sessions/Playing/Progress"}, False, False)

    def session_stop(self, params):
        self.EmbyServer.http.request({'data': json.dumps(params), 'type': "POST", 'handler': "Sessions/Playing/Stopped"}, False, False)

    def session_logout(self):
        self.EmbyServer.http.request({'type': "POST", 'handler': "Sessions/Logout"}, False, False)

    def delete_item(self, Id):
        self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Items/{Id}"}, False, False)

    def get_stream_statuscode(self, Id, MediasourceID):
        return self.EmbyServer.http.request({'params': {'static': True, 'MediaSourceId': MediasourceID, 'DeviceId': self.EmbyServer.ServerData['DeviceId']}, 'type': "HEAD", 'handler': f"videos/{Id}/stream"}, False, False)

    def get_Subtitle_Binary(self, Id, MediasourceID, SubtitleId, SubtitleFormat):
        return self.EmbyServer.http.request({'type': "GET", 'handler': f"/videos/{Id}/{MediasourceID}/Subtitles/{SubtitleId}/stream.{SubtitleFormat}"}, False, True, False)

    def get_Fields(self, MediaType, Basic, Dynamic):
        if not Basic:
            Fields = EmbyFields[MediaType.lower()]

            #Dynamic list query, remove fields to improve performance
            if Dynamic:
                if MediaType in ("Series", "Season"):
                    Fields += ("RecursiveItemCount", "ChildCount")

                for DynamicListsRemoveField in self.DynamicListsRemoveFields:
                    if DynamicListsRemoveField in Fields:
                        Fields.remove(DynamicListsRemoveField)

            Fields = ",".join(list(dict.fromkeys(Fields))) # remove duplicates and join into string
        else:
            Fields = None

        return Fields

    def get_upcoming(self, ParentId):
        Fields = EmbyFields["episode"]
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': Fields, 'EnableImages': True, 'EnableUserData': True}, 'type': "GET", 'handler': "Shows/Upcoming"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_NextUp(self, ParentId):
        Fields = EmbyFields["episode"]
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': Fields, 'EnableImages': True, 'EnableUserData': True, 'LegacyNextUp': True}, 'type': "GET", 'handler': "Shows/NextUp"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

def get_Limit(MediaType):
    Type = MediaType.lower()

    if Type == "musicartist":
        return utils.MusicartistPaging

    if Type == "musicalbum":
        return utils.MusicalbumPaging

    if Type == "audio":
        return utils.AudioPaging

    if Type == "movie":
        return utils.MoviePaging

    if Type == "boxset":
        return utils.BoxsetPaging

    if Type == "series":
        return utils.SeriesPaging

    if Type == "season":
        return utils.SeasonPaging

    if Type == "episode":
        return utils.EpisodePaging

    if Type == "musicvideo":
        return utils.MusicvideoPaging

    if Type == "video":
        return utils.VideoPaging

    if Type == "photo":
        return utils.PhotoPaging

    if Type == "photoalbum":
        return utils.PhotoalbumPaging

    if Type == "playlist":
        return utils.PlaylistPaging

    if Type == "channels":
        return utils.ChannelsPaging

    if Type == "folder":
        return utils.FolderPaging

    if Type == "livetv":
        return utils.LiveTVPaging

    if Type == "trailer":
        return utils.TrailerPaging

    if Type == "musicgenre":
        return utils.MusicgenrePaging

    if Type == "person":
        return utils.PersonPaging

    if Type == "tag":
        return utils.TagPaging

    if Type == "studio":
        return utils.StudioPaging

    if Type == "genre":
        return utils.GenrePaging

    if Type == "all":
        return utils.AllPaging

    xbmc.log(f"EMBY.emby.api: Invalid content: {MediaType}", 3) # LOGERROR
    return 5000

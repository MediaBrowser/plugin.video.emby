import xbmc
from helper import utils, queue
from database import dbio
from . import listitem

EmbyFields = {
    "musicartist": ["Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "musicalbum": ["Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "Studios", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "audio": ["Genres", "SortName", "ProductionYear", "DateCreated", "MediaStreams", "ProviderIds", "Overview", "Path", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "movie": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "trailer": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags"],
    "boxset": ["Overview", "SortName", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "series": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProviderIds", "ParentId", "Status", "PresentationUniqueKey", "OriginalTitle", "Tags", "LocalTrailerCount", "RemoteTrailers", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "season": ["PresentationUniqueKey", "SortName", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "episode": ["SpecialEpisodeNumbers", "ParentId", "Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "musicvideo": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "video": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "photo": ["Path", "SortName", "ProductionYear", "ParentId", "PremiereDate", "Width", "Height", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "photoalbum": ["Path", "SortName", "Taglines", "DateCreated", "ShortOverview", "ProductionLocations", "Tags", "ParentId", "OriginalTitle", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "tvchannel": ["Genres", "SortName", "Taglines", "DateCreated", "Overview", "MediaSources", "Tags", "MediaStreams", "UserDataPlayCount", "UserDataLastPlayedDate"],
    "folder": ["Path",],
    "playlist": ["SortName", "Overview", "Path"],
    "genre": [],
    "musicgenre": [],
    "person": [],
    "tag": [],
    "channel": [],
    "collectionfolder": [],
    "studio": [],
    "all": ["Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"]
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
        _, _, Payload = self.EmbyServer.http.request("POST", f"Items/{Id}/PlaybackInfo", {'UserId': self.EmbyServer.ServerData['UserId'], "IsPlayback": "true", "AutoOpenLiveStream": "true"}, {}, False, "", False)

        if 'MediaSources' in Payload and Payload['MediaSources']:
            MediaSourceId = Payload['MediaSources'][0]['Id']
            LiveStreamId = Payload['MediaSources'][0].get('LiveStreamId', None)
            Container = Payload['MediaSources'][0].get('Container', "")
            PlaySessionId = Payload['PlaySessionId']
        else:
            MediaSourceId = None
            LiveStreamId = None
            Container = None
            PlaySessionId = None

        return MediaSourceId, LiveStreamId, PlaySessionId, Container

    def get_Items_dynamic(self, ParentId, MediaTypes, Recursive, Extra, Resume, LibraryId):
        CustomLimit = False

        if Resume:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Resume"
        else:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items" # Userdata must be always queried, otherwise ParentId parameter is not respected by Emby server

        ItemsQueue = queue.Queue()
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
            utils.start_thread(self.async_get_Items, (Request, ItemsQueue, Params, "", CustomLimit, None))

            while True:
                BasicItem = ItemsQueue.get()

                if BasicItem == "QUIT":
                    break

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

        SortItems = {'Movie': (), 'BoxSet': (), 'MusicVideo': (), 'Series': (), 'Season': (), 'Episode': (), 'Folder': (), 'MusicArtist': (), 'AlbumArtist': (), 'MusicAlbum': (), 'Audio': (), 'Genre': (), 'MusicGenre': (), 'Tag': (), 'Person': (), 'Studio': (), 'Playlist': (), 'Photo': (), 'PhotoAlbum': (), 'Video': (), 'Trailer': (), 'Channel': (), 'CollectionFolder': ()}

        for ItemFullQuery in ItemsFullQuery:
            if not ItemFullQuery:
                continue

            SortItems[ItemFullQuery[0]] += ((ItemFullQuery[1], ItemFullQuery[2]),)

        # request extended item data
        for Type, ItemData in list(SortItems.items()):
            if ItemData:
                Fields = EmbyFields[Type.lower()]

                if Fields and Fields != ("Path",):
                    yield from self.get_Items_Ids(list(dict(ItemData).keys()), [Type], True, False, False, "", Extra)
                else:  # no extended information required
                    for Item in ItemData:
                        yield Item[1]

    def get_Items_Ids(self, Ids, MediaTypes, Dynamic, Basic, ProcessProgressId, LibraryId, Extra, BusyFunction=None):
        ItemsQueue = queue.Queue()

        for MediaType in MediaTypes:
            utils.start_thread(self.async_get_Items_Ids, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, Ids, Dynamic, Basic, ProcessProgressId, LibraryId, MediaType, Extra, BusyFunction))

            while True:
                Items = ItemsQueue.getall()

                if utils.SystemShutdown:
                    return

                if not Items:
                    break

                if Items[-1] == "QUIT":
                    yield from Items[:-1]
                    del Items
                    break

                yield from Items
                del Items

    def async_get_Items_Ids(self, Request, ItemsQueue, Ids, Dynamic, Basic, ProcessProgressId, LibraryId, MediaType, Extra, BusyFunction=None):
        xbmc.log("EMBY.emby.api: THREAD: --->[ load Item by Ids ]", 0) # LOGDEBUG
        CounterFound = 0
        CounterQuery = 0
        Payload = ()
        IdsTotal = len(Ids)
        Params = {'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'IncludeItemTypes': MediaType, 'Recursive': False}
        SubContent = bool(MediaType in ("BoxSet", "MusicArtist", "MusicAlbum", "Genre", "MusicGenre", "Tag", "Person", "Studio", "Playlist"))

        if not Basic:
            Fields = EmbyFields[MediaType.lower()]

            #Dynamic list query, remove fields to improve performance
            if Dynamic:
                if MediaType in ("Series", "Season"):
                    Fields += ["RecursiveItemCount", "ChildCount"]

                for DynamicListsRemoveField in self.DynamicListsRemoveFields:
                    if DynamicListsRemoveField in Fields:
                        Fields.remove(DynamicListsRemoveField)

            Params['Fields'] = ",".join(list(dict.fromkeys(Fields))) # remove duplicates and join into string

        if Extra:
            Params.update(Extra)

        if 'SortBy' not in Params:
            Params['SortBy'] = "None"

        while Ids:
            # Uri length limitation
            IdsIndex = 100

            while len(",".join(Ids[:IdsIndex])) < utils.MaxURILength and IdsIndex < len(Ids):
                IdsIndex += 5

            QueryIds = Ids[:IdsIndex]
            CounterQuery += len(QueryIds)
            Params['Ids'] = ",".join(QueryIds)  # Chunks of 100 + IdsIndex -> due to URI length limitation, more than X Ids not possible to request (HTTP error 414)
            Ids = Ids[IdsIndex:]

            # Query content
            if not Dynamic:
                if LibraryId and LibraryId.lower() != "unknown": # Kodi start updates
                    _, _, Payload = self.EmbyServer.http.request("GET", Request, Params, {}, False, "", False, BusyFunction)

                    if 'Items' in Payload:
                        for Item in Payload['Items']:
                            Item['LibraryId'] = LibraryId
                            ItemsQueue.put(Item)
                            CounterFound += 1
                else: # realtime updates via websocket
                    if SubContent: # Subcontent doesn not respect ParentId queries
                        embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "Realtimesync_Subcontent")
                        LibrarySyncedIds = embydb.get_LibraryIds_by_EmbyIds(QueryIds)
                        dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "Realtimesync_Subcontent")
                        _, _, Payload = self.EmbyServer.http.request("GET", Request, Params, {}, False, "", False, BusyFunction)

                        if 'Items' in Payload:
                            for Item in Payload['Items']: # Check if content is an synced content update
                                if Item['Id'] in LibrarySyncedIds:
                                    for LibrarySyncedId in LibrarySyncedIds[Item['Id']]:
                                        Item['LibraryId'] = LibrarySyncedId[0]
                                        ItemsQueue.put(Item)
                                        CounterFound += 1
                    else:
                        for LibrarySyncedId in self.EmbyServer.library.LibrarySyncedNames:
                            CounterFoundSubItems = 0
                            Params.update({'Recursive': True, 'ParentId': LibrarySyncedId}) # Recursive = True must be set, when query by ParentId
                            _, _, Payload = self.EmbyServer.http.request("GET", Request, Params, {}, False, "", False, BusyFunction)

                            if 'Items' in Payload:
                                CounterFoundSubItems += len(Payload['Items'])

                                for Item in Payload['Items']:
                                    Item['LibraryId'] = LibrarySyncedId
                                    ItemsQueue.put(Item)
                                    CounterFound += 1

                            if CounterFoundSubItems == len(QueryIds) or utils.SystemShutdown: # All data received, no need to check additional libraries
                                break
            else: # dynamic node query
                _, _, Payload = self.EmbyServer.http.request("GET", Request, Params, {}, False, "", False)

                if 'Items' in Payload and Payload['Items']:
                    # Restore item order as requsted -> Emby sorts by ascending Ids
                    ItemsSorted = len(Payload['Items']) * [()] # pre allocate memory

                    for Item in Payload['Items']:
                        ItemsSorted[QueryIds.index(Item['Id'])] = Item

                    # Add items into queue
                    ItemsQueue.put(ItemsSorted)
                    del ItemsSorted
                    CounterFound += len(Payload['Items'])

            del Payload  # release memory

            if IdsTotal == CounterQuery or utils.SystemShutdown or not self.async_throttle_queries(CounterFound, ProcessProgressId): # all requested items received
                break

        ItemsQueue.put("QUIT")
        xbmc.log("EMBY.emby.api: THREAD: ---<[ load Item by Ids ]", 0) # LOGDEBUG

    def async_throttle_queries(self, Index, ProcessProgressId):
        # Throttle queries -> give Kodi time to catch up
        if ProcessProgressId and ProcessProgressId in self.ProcessProgress:
            while Index > self.ProcessProgress[ProcessProgressId]:
                xbmc.log(f"EMBY.emby.api: Throttle queries {Index} / {ProcessProgressId} / {self.ProcessProgress[ProcessProgressId]}", 1) # LOGINFO

                if utils.sleep(2) or self.ProcessProgress[ProcessProgressId] == -1: # Cancel
                    return False

        return True

    def get_Items(self, ParentId, MediaTypes, Basic, Recursive, Extra, ProcessProgressId, UserData, BusyFunction):
        CustomLimit = False
        ItemsQueue = queue.Queue()

        for MediaType in MediaTypes:
            Limit = get_Limit(MediaType)
            Fields = self.get_Fields(MediaType, Basic, False)

            if Fields:
                Params = {'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit, 'Fields': Fields}
            else:
                Params = {'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit}

            if MediaType != "All":
                Params['IncludeItemTypes'] = MediaType

            if str(ParentId) != "999999999":
                Params['ParentId'] = ParentId

            if Extra:
                CustomLimit = bool("Limit" in Extra)
                Params.update(Extra)

            if 'SortBy' not in Params:
                Params['SortBy'] = "None"

            if UserData and MediaType != "Folder":
                utils.start_thread(self.async_get_Items, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, Params, ProcessProgressId, CustomLimit, BusyFunction))
            else:
                utils.start_thread(self.async_get_Items, ("Items", ItemsQueue, Params, ProcessProgressId, CustomLimit, BusyFunction))

            while True:
                Items = ItemsQueue.getall()

                if utils.SystemShutdown:
                    return

                if not Items:
                    break

                if Items[-1] == "QUIT":
                    yield from Items[:-1]
                    del Items  # release memory
                    break

                yield from Items
                del Items  # release memory

    def get_channelprogram(self):
        Limit = get_Limit("livetv")
        Params = {'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': "Overview", 'EnableTotalRecordCount': False, 'Limit': Limit}
        ItemsQueue = queue.Queue()
        utils.start_thread(self.async_get_Items, ("LiveTv/Programs", ItemsQueue, Params, "", False, None))

        while True:
            Items = ItemsQueue.getall()

            if utils.SystemShutdown or not Items:
                return

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                del Items
                return

            yield from Items
            del Items

    def get_recommendations(self, ParentId):
        Fields = self.get_Fields("movie", False, True)
        Params = {'ParentId': ParentId, 'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': Fields, 'EnableTotalRecordCount': False, 'Recursive': True}
        _, _, Payload = self.EmbyServer.http.request("GET", "Movies/Recommendations", Params, {}, False, "", False)

        Items = []

        for Data in Payload:
            if 'Items' in Data:
                Items += Data['Items']

        return Items

    def async_get_Items(self, Request, ItemsQueue, Params, ProcessProgressId, CustomLimit, BusyFunction=None):
        xbmc.log("EMBY.emby.api: THREAD: --->[ load Items ]", 0) # LOGDEBUG
        Index = 0
        ItemCounter = 0
        Limit = Params['Limit']

        while True:
            Params['StartIndex'] = Index
            _, _, Payload = self.EmbyServer.http.request("GET", Request, Params, {}, False, "", False, BusyFunction)
            DirectItems = Request.lower().find("latest") != -1

            if DirectItems:
                if utils.SystemShutdown or not Payload:
                    ItemsQueue.put("QUIT")
                    del Payload  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (latest / no items found or shutdown)", 0) # LOGDEBUG
                    return

                ItemsQueue.put(Payload)
                ReceivedItems = len(Payload)
                ItemCounter += ReceivedItems
            else:
                if utils.SystemShutdown or 'Items' not in Payload or not Payload['Items']:
                    ItemsQueue.put("QUIT")
                    del Payload  # release memory
                    xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (no items found or shutdown)", 0) # LOGDEBUG
                    return

                ItemsQueue.put(Payload['Items'])
                ReceivedItems = len(Payload['Items'])
                ItemCounter += ReceivedItems

            del Payload  # release memory

            if ReceivedItems < Limit:
                ItemsQueue.put("QUIT")
                xbmc.log(f"EMBY.emby.api: THREAD: ---<[ load Items ] Limit: {Limit} / ReceivedItems: {ReceivedItems}", 0) # LOGDEBUG
                return

            if CustomLimit:
                ItemsQueue.put("QUIT")
                xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (limit reached)", 0) # LOGDEBUG
                return

            if not self.async_throttle_queries(Index, ProcessProgressId):
                ItemsQueue.put("QUIT")
                xbmc.log("EMBY.emby.api: THREAD: ---<[ load Items ] (throttle)", 0) # LOGDEBUG
                return

            Index += Limit

    def get_Item(self, Ids, MediaTypes, Dynamic, Basic, Specials=False):
        for MediaType in MediaTypes:
            Fields = self.get_Fields(MediaType, Basic, Dynamic)

            if Specials: # Bugfix workaround
                _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items", {'Ids': Ids, 'Fields': Fields, 'IncludeItemTypes': 'Workaround', 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'SortBy': "None"}, {}, False, "", False)
            else:
                _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items", {'Ids': Ids, 'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'SortBy': "None"}, {}, False, "", False)

            if 'Items' in Payload:
                if Payload['Items']:
                    return Payload['Items'][0]

        return {}

    def get_TotalRecords(self, parent_id, item_type, Extra):
        Params = {'ParentId': parent_id, 'IncludeItemTypes': item_type, 'EnableTotalRecordCount': True, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': True, 'Limit': 1}

        if Extra:
            Params.update(Extra)

        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items", Params, {}, False, "", False)

        if 'TotalRecordCount' in Payload:
            return int(Payload['TotalRecordCount'])

        return 0

    def get_timer(self, ProgramId):
        _, _, Payload = self.EmbyServer.http.request("GET", "LiveTv/Timers", {'programId': ProgramId}, {}, False, "", False)

        if 'Items' in Payload:
            return Payload['Items']

        return []

    def set_timer(self, ProgramId):
        _, _, Payload = self.EmbyServer.http.request("POST", "LiveTv/Timers", {'programId': ProgramId}, {}, False, "", False)
        return Payload

    def delete_timer(self, TimerId):
        _, _, Payload = self.EmbyServer.http.request("POST", f"LiveTv/Timers/{TimerId}/Delete", {}, {}, False, "", False)
        return Payload

    def get_users(self, disabled, hidden):
        _, _, Payload = self.EmbyServer.http.request("GET", "Users", {'IsDisabled': disabled, 'IsHidden': hidden}, {}, False, "", False)
        return Payload

    def get_public_users(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "Users/Public", {}, {}, False, "", False)
        return Payload

    def get_user(self, user_id):
        if not user_id:
            _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}", {}, {}, False, "", False)
            return Payload

        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{user_id}", {}, {}, False, "", False)
        return Payload

    def get_libraries(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "Library/VirtualFolders/Query", {}, {}, False, "", False)
        return Payload

    def get_views(self):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Views", {}, {}, False, "", False)
        return Payload

    def download_file(self, EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId):
        self.EmbyServer.http.Queues["DOWNLOAD"].put(((EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId),))

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
            _, Header, Payload = self.EmbyServer.http.request("GET", f"Users/{Id}/Images/{ImageType}", Params, {}, True, "", True)
        else:
            if ImageTag:
                Params["tag"] = ImageTag

            _, Header, Payload = self.EmbyServer.http.request("GET", f"Items/{Id}/Images/{ImageType}/{ImageIndex}", Params, {}, True, "", True)

        if 'Content-Type' in Header:
            ContentType = Header['content-type']

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
            ContentType = "image/unknown"

        return Payload, ContentType, FileExtension

    def get_device(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "Sessions", {'DeviceId': self.EmbyServer.ServerData['DeviceId']}, {}, False, "", False)
        return Payload

    def get_active_sessions(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "Sessions", {}, {}, False, "", False)
        return Payload

    def send_text_msg(self, SessionId, Header, Text, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Message", {'Header': f"{Header}", 'Text': f"{Text}"}, Priority),))

    def send_play(self, SessionId, ItemId, PlayCommand, StartPositionTicks, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Playing", {'ItemIds': f"{ItemId}", 'StartPositionTicks': f"{StartPositionTicks}", 'PlayCommand': f"{PlayCommand}"}, Priority),))

    def send_pause(self, SessionId, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Playing/Pause", {}, Priority),))

    def send_unpause(self, SessionId, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Playing/Unpause", {}, Priority),))

    def send_seek(self, SessionId, Position, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Playing/Seek", {'SeekPositionTicks': Position}, Priority),))

    def send_stop(self, SessionId, Priority=False):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{SessionId}/Playing/Stop", {}, Priority),))

    def get_channels(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "LiveTv/Channels", {'UserId': self.EmbyServer.ServerData['UserId'], 'EnableImages': True, 'EnableUserData': True, 'Fields': ",".join(EmbyFields['tvchannel'])}, {}, False, "", False)

        if 'Items' in Payload:
            return Payload['Items']

        return []

    def get_PlaybackInfo(self, Id):
        _, _, Payload = self.EmbyServer.http.request("POST", f"Items/{Id}/PlaybackInfo", {'UserId': self.EmbyServer.ServerData['UserId']}, {}, False, "", False)

        if 'MediaSources' in Payload and Payload['MediaSources']:
            return Payload['MediaSources']

        return []

    def get_specialfeatures(self, Id):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/SpecialFeatures", {'Fields': "Path,MediaSources,PresentationUniqueKey,ParentId,DateCreated,UserDataPlayCount", 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, {}, False, "", False)
        return Payload

    def get_intros(self, Id):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/Intros", {'Fields': ",".join(EmbyFields["trailer"]), 'EnableTotalRecordCount': False, "EnableUserData": False}, {}, False, "", False)
        return Payload

    def get_additional_parts(self, Id):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Videos/{Id}/AdditionalParts", {'Fields': "Path,MediaSources"}, {}, False, "", False)
        return Payload

    def get_local_trailers(self, Id):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/LocalTrailers", {'Fields': ",".join(EmbyFields["trailer"]), 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", "EnableUserData": False}, {}, False, "", False)
        return Payload

    def get_themes(self, Id, Songs, Videos):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Items/{Id}/ThemeMedia", {'Fields': "Path,MediaSources", 'UserId': self.EmbyServer.ServerData['UserId'], 'InheritFromParent': True, 'EnableThemeSongs': Songs, 'EnableThemeVideos': Videos, 'EnableTotalRecordCount': False}, {}, False, "", False)
        return Payload

    def get_sync_queue(self, date):
        _, _, Payload = self.EmbyServer.http.request("GET", f"Emby.Kodi.SyncQueue/{self.EmbyServer.ServerData['UserId']}/GetItems", {'LastUpdateDT': date}, {}, False, "", False)
        return Payload

    def get_system_info(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "System/Configuration", {}, {}, False, "", False)
        return Payload

    def set_progress(self, Id, Progress, PlayCount):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/UserData", {"PlaybackPositionTicks": Progress, "PlayCount": PlayCount, "Played": bool(PlayCount)}, False),))

    def set_progress_upsync(self, Id, PlaybackPositionTicks, PlayCount, LastPlayedDate):
        Params = {"PlaybackPositionTicks": PlaybackPositionTicks, "LastPlayedDate": LastPlayedDate}

        if PlayCount and PlayCount != -1:
            Params.update({"PlayCount": PlayCount, "Played": bool(PlayCount)})

        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{Id}/UserData", Params, False),))

    def set_played(self, Id, PlayCount):
        if PlayCount:
            self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{Id}", {}, False),))
        else:
            self.EmbyServer.http.Queues["ASYNC"].put((("DELETE", f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{Id}", {}, False),))

    def refresh_item(self, Id):
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Items/{Id}/Refresh", {'Recursive': True, 'ImageRefreshMode': "FullRefresh", 'MetadataRefreshMode': "FullRefresh", 'ReplaceAllImages': False, 'ReplaceAllMetadata': True}, False),))

    def favorite(self, Id, Add):
        if Add:
            self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{Id}", {}, False),))
        else:
            self.EmbyServer.http.Queues["ASYNC"].put((("DELETE", f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{Id}", {}, False),))

    def post_capabilities(self):
        self.EmbyServer.http.request("POST", "Sessions/Capabilities/Full", {'Id': self.EmbyServer.EmbySession[0]['Id'], 'SupportsRemoteControl': True, 'PlayableMediaTypes': ["Audio", "Video", "Photo"], 'SupportsMediaControl': True, 'SupportsSync': True, 'SupportedCommands': ["MoveUp", "MoveDown", "MoveLeft", "MoveRight", "Select", "Back", "ToggleContextMenu", "ToggleFullscreen", "ToggleOsdMenu", "GoHome", "PageUp", "NextLetter", "GoToSearch", "GoToSettings", "PageDown", "PreviousLetter", "TakeScreenshot", "VolumeUp", "VolumeDown", "ToggleMute", "SendString", "DisplayMessage", "SetAudioStreamIndex", "SetSubtitleStreamIndex", "SetRepeatMode", "SetShuffle", "PlaybackRate", "Mute", "Unmute", "SetVolume", "MovePlaylistItem", "RemoveFromPlaylist", "SetCurrentPlaylistItem", "ToggleStats", "PlayTrailers", "Pause", "Unpause", "Play", "Playstate", "PlayNext", "PlayMediaSource", "ChannelDown", "ChannelUp", "DisplayContent"], 'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"}, {}, False, "", False)

    def session_add_user(self, session_id, user_id, option):
        if option:
            self.EmbyServer.http.Queues["ASYNC"].put((("POST", f"Sessions/{session_id}/Users/{user_id}", {}, False),))
        else:
            self.EmbyServer.http.Queues["ASYNC"].put((("DELETE", f"Sessions/{session_id}/Users/{user_id}", {}, False),))

    def session_playing(self, EmbySessionInfo, PlaylistKodi, PlaylistEmby):
        EmbySessionInfoLocal, PlaylistEmby = update_sessioninfo(EmbySessionInfo, "", PlaylistKodi, PlaylistEmby)
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", "Sessions/Playing", EmbySessionInfoLocal, False),))
        return PlaylistEmby

    def session_progress(self, EmbySessionInfo, EventName, PlaylistKodi, PlaylistEmby):
        EmbySessionInfoLocal, PlaylistEmby = update_sessioninfo(EmbySessionInfo, EventName, PlaylistKodi, PlaylistEmby)
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", "Sessions/Playing/Progress", EmbySessionInfoLocal, False),))
        return PlaylistEmby

    def session_stop(self, EmbySessionInfo, PlaylistKodi, PlaylistEmby):
        EmbySessionInfoLocal, PlaylistEmby = update_sessioninfo(EmbySessionInfo, "", PlaylistKodi, PlaylistEmby)
        self.EmbyServer.http.Queues["ASYNC"].put((("POST", "Sessions/Playing/Stopped", EmbySessionInfoLocal, False),))
        return PlaylistEmby

    def session_logout(self):
        self.EmbyServer.http.request("POST", "Sessions/Logout", {}, {}, False, "", False)

    def delete_item(self, Id):
        self.EmbyServer.http.Queues["ASYNC"].put((("DELETE", f"Items/{Id}", {}, False),))

    def get_publicinfo(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "system/info/public", {}, {}, False, "", False)
        return Payload

    def get_exchange(self):
        _, _, Payload = self.EmbyServer.http.request("GET", "Connect/Exchange", {'ConnectUserId': self.EmbyServer.ServerData['EmbyConnectUserId']}, {'X-Emby-Token': self.EmbyServer.ServerData['EmbyConnectExchangeToken']}, {}, False, "", False)
        return Payload

    def get_authbyname(self, Username, Password):
        _, _, Payload = self.EmbyServer.http.request("POST", "Users/AuthenticateByName", {'username': Username, 'pw': Password or ""}, {}, False, "", False)
        return Payload

    def get_stream_statuscode(self, Id, MediaSourceId):
        StatusCode, _, _ = self.EmbyServer.http.request("HEAD", f"videos/{Id}/stream", {'static': True, 'MediaSourceId': MediaSourceId, 'DeviceId': self.EmbyServer.ServerData['DeviceId']}, {}, False, "", False)
        return StatusCode

    def get_Subtitle_Binary(self, Id, MediaSourceId, SubtitleIndex, SubtitleFormat):
        _, _, Payload = self.EmbyServer.http.request("GET", f"videos/{Id}/{MediaSourceId}/Subtitles/{SubtitleIndex}/stream.{SubtitleFormat}", {}, {}, True, "", True)
        return Payload

    def get_embyconnect_authenticate(self, Username, Password):
        _, _, Payload = self.EmbyServer.http.request("POST", "service/user/authenticate", {'nameOrEmail': Username, 'rawpw': Password}, {'X-Application': f"{utils.addon_name}/{utils.addon_version}"}, False, "https://connect.emby.media:443", True)
        return Payload

    def get_embyconnect_servers(self):
        _, _, Payload = self.EmbyServer.http.request("GET", f"service/servers?userId={self.EmbyServer.ServerData['EmbyConnectUserId']}", {}, {'X-Connect-UserToken': self.EmbyServer.ServerData['EmbyConnectAccessToken'], 'X-Application': f"{utils.addon_name}/{utils.addon_version}"}, False, "https://connect.emby.media:443", True)
        return Payload

    def get_Fields(self, MediaType, Basic, Dynamic):
        if not Basic:
            Fields = EmbyFields[MediaType.lower()]

            #Dynamic list query, remove fields to improve performance
            if Dynamic:
                if MediaType in ("Series", "Season"):
                    Fields += ["RecursiveItemCount", "ChildCount"]

                for DynamicListsRemoveField in self.DynamicListsRemoveFields:
                    if DynamicListsRemoveField in Fields:
                        Fields.remove(DynamicListsRemoveField)

            Fields = ",".join(list(dict.fromkeys(Fields))) # remove duplicates and join into string
        else:
            Fields = None

        return Fields

    def get_upcoming(self, ParentId):
        _, _, Payload = self.EmbyServer.http.request("GET", "Shows/Upcoming", {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': ",".join(EmbyFields["episode"]), 'EnableImages': True, 'EnableUserData': True}, {}, False, "", False)

        if 'Items' in Payload:
            return Payload['Items']

        return []

    def get_NextUp(self, ParentId):
        _, _, Payload = self.EmbyServer.http.request("GET", "Shows/NextUp", {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': ",".join(EmbyFields["episode"]), 'EnableImages': True, 'EnableUserData': True, 'LegacyNextUp': True}, {}, False, "", False)

        if 'Items' in Payload:
            return Payload['Items']

        return []

def get_Limit(MediaType):
    if not MediaType:
        xbmc.log(f"EMBY.emby.api: Invalid content 1: {MediaType}", 3) # LOGERROR
        return 5000

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

    xbmc.log(f"EMBY.emby.api: Invalid content 2: {MediaType}", 3) # LOGERROR
    return 5000

def update_sessioninfo(EmbySessionInfo, EventName, PlaylistKodi, PlaylistEmby):
    # Build PlayingQueue
    PlaylistKodiLen = len(PlaylistKodi)
    PlaylistEmbyLen = len(PlaylistEmby)

    if EventName and PlaylistKodiLen > PlaylistEmbyLen:
        EventName = "PlaylistItemAdd"

    if PlaylistKodiLen != PlaylistEmbyLen:
        PlaylistEmby = PlaylistKodiLen * [{}] # allocate memory
        Complete = True

        for ServerId in utils.EmbyServers:
            embydb = dbio.DBOpenRO(ServerId, "Playlist_Add")

            for PlaylistIndex, PlaylistKodiItem in enumerate(PlaylistKodi):
                if PlaylistKodiItem["KodiId"] > 1000000000: # Update dynamic item
                    EmbyId = PlaylistKodiItem["KodiId"] - 1000000000
                else:
                    EmbyId = embydb.get_EmbyId_by_KodiId_KodiType(PlaylistKodiItem["KodiId"], PlaylistKodiItem["KodiType"])

                if not EmbyId:
                    Complete = False
                    EmbyId = -1

                PlaylistEmby[PlaylistIndex] = {"Id": int(EmbyId), "PlaylistItemId": str(PlaylistIndex)}

            dbio.DBCloseRO(ServerId, "Playlist_Add")

            if Complete:
                break

    # Update info
    EmbySessionInfoLocal = EmbySessionInfo.copy()
    EmbySessionInfoLocal.update({"PlaylistLength": PlaylistEmbyLen, "NowPlayingQueue": PlaylistEmby})

    if EventName:
        EmbySessionInfoLocal["EventName"] = EventName

    if 'MediaSourceId' in EmbySessionInfoLocal and not EmbySessionInfoLocal['MediaSourceId']:
        del EmbySessionInfoLocal['MediaSourceId']

    if 'PlaylistPosition' in EmbySessionInfoLocal and EmbySessionInfoLocal['PlaylistPosition'] == -1:
        del EmbySessionInfoLocal['PlaylistPosition']

    return EmbySessionInfoLocal, PlaylistEmby

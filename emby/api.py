from _thread import start_new_thread
import json
import xbmc
from helper import utils, queue
from database import dbio
from . import listitem

EmbyPagingFactors = {"musicartist": 100, "musicalbum": 100, "audio": 200, "movie": 50, "boxset": 50, "series": 50, "season": 50, "episode": 50, "musicvideo": 50, "video": 50, "photo": 50, "photoalbum": 50, "playlist": 50, "channels": 50, "folder": 100, "livetv": 10000, "trailer": 200}
EmbyFields = {
    "musicartist": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicalbum": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "Studios", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "audio": ("Genres", "SortName", "ProductionYear", "DateCreated", "MediaStreams", "ProviderIds", "Overview", "Path", "ParentId", "PresentationUniqueKey", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "movie": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "trailer": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags"),
    "boxset": ("Overview", "PresentationUniqueKey", "SortName", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "series": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProviderIds", "ParentId", "Status", "PresentationUniqueKey", "OriginalTitle", "Tags", "LocalTrailerCount", "RemoteTrailers", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "season": ("PresentationUniqueKey", "SortName", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "episode": ("SpecialEpisodeNumbers", "Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicvideo": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "video": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photo": ("Path", "SortName", "ProductionYear", "ParentId", "PremiereDate", "Width", "Height", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photoalbum": ("Path", "SortName", "Taglines", "DateCreated", "ShortOverview", "ProductionLocations", "Tags", "ParentId", "OriginalTitle", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "tvchannel": ("Genres", "SortName", "Taglines", "DateCreated", "Overview", "MediaSources", "Tags", "MediaStreams", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "folder": ("Path", ),
    "playlist": ("SortName", "Overview", "Path"),
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

    def open_livestream(self, EmbyID, PlaySessionId):
        for HTTPQueryDoubleFilter in list(utils.HTTPQueryDoublesFilter.values()):
            if self.EmbyServer.ServerData['ServerId'] == HTTPQueryDoubleFilter['ServerId'] and HTTPQueryDoubleFilter['LiveStreamId']:
                self.close_livestream(HTTPQueryDoubleFilter['LiveStreamId'])
                break

        PlaybackInfoData = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], "IsPlayback": "true", "AutoOpenLiveStream": "true", "PlaySessionId": PlaySessionId}, 'type': "POST", 'handler': f"Items/{EmbyID}/PlaybackInfo"}, True, False)
        xbmc.log(f"EMBY.emby.api: Open LiveStreamId {PlaybackInfoData['MediaSources'][0]['LiveStreamId']}", 1) # LOGINFO
        return PlaybackInfoData['MediaSources'][0]['Id'], PlaybackInfoData['MediaSources'][0]['LiveStreamId'], PlaybackInfoData['MediaSources'][0].get('Container', "")

    def close_livestream(self, LiveStreamId):
        xbmc.log(f"EMBY.emby.api: Close LiveStreamId {LiveStreamId}", 1) # LOGINFO
        self.EmbyServer.http.request({'data': json.dumps({'LiveStreamId': LiveStreamId}), 'type': "POST", 'handler': "LiveStreams/Close"}, False, False)

    def get_Items_dynamic(self, ParentId, MediaTypes, Basic, Recursive, Extra, Resume, Latest=False, SkipLocalDB=False, UseAncestors=False):
        CustomLimit = False

        if Resume:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Resume"
        elif Latest:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Latest"
        else:
            Request = f"Users/{self.EmbyServer.ServerData['UserId']}/Items"

        for MediaType in MediaTypes:
            Limit = get_Limit(MediaType)
            Params = {'ParentId': ParentId, 'IncludeItemTypes': MediaType, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit}

            if Extra:
                Params.update(Extra)

                if "Limit" in Extra:
                    Limit = Extra["Limit"]
                    CustomLimit = True

            ItemsFullQuery = 10000 * [None] # pre allocate memory
            embydb = None
            videodb = None
            musicdb = None

            for ItemIndex, BasicItem in enumerate(self.get_Items_Custom(Request, Params, Limit, not Recursive or CustomLimit)):
                KodiItem = ({}, "")

                if SkipLocalDB or BasicItem['Type'] in ("Photo", "PhotoAlbum", "BoxSet"):
                    if ItemIndex % 10000 == 0: # modulo 10000
                        ItemsFullQuery += 10000 * [None] # pre allocate memory

                    ItemsFullQuery[ItemIndex] = BasicItem['Id']
                    continue

                if not embydb:
                    embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "get_Items_dynamic")
                    videodb = dbio.DBOpenRO("video", "get_Items_dynamic")
                    musicdb = dbio.DBOpenRO("music", "get_Items_dynamic")

                KodiId, _ = embydb.get_KodiId_KodiType_by_EmbyId_EmbyLibraryId(BasicItem['Id'], ParentId) # Requested video is synced to KodiDB.zz

                if not KodiId and UseAncestors and BasicItem['Type'] in ("Movie", "Series", "Season", "Episode", "MusicVideo", "MusicArtist", "MusicAlbum", "Audio"):
                    Ancestors = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId']}, 'type': "GET", 'handler': f"Items/{BasicItem['Id']}/Ancestors"}, False, False)

                    for Ancestor in Ancestors:
                        KodiId, _ = embydb.get_KodiId_KodiType_by_EmbyId_EmbyLibraryId(BasicItem['Id'], Ancestor['Id']) # Requested video is synced to KodiDB.zz

                        if KodiId:
                            break

                if KodiId:
                    if BasicItem['Type'] in ("Movie", "Video"):
                        KodiItem = (videodb.get_movie_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Series":
                        KodiItem = (videodb.get_tvshows_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Season":
                        KodiItem = (videodb.get_season_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Episode":
                        KodiItem = (videodb.get_episode_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "BoxSet":
                        KodiItem = (videodb.get_boxset_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicVideo":
                        KodiItem = (videodb.get_musicvideos_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicArtist":
                        KodiItem = (musicdb.get_artist_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "MusicAlbum":
                        KodiItem = (musicdb.get_album_metadata_for_listitem(KodiId), BasicItem['Type'])
                    elif BasicItem['Type'] == "Audio":
                        KodiItem = (musicdb.get_song_metadata_for_listitem(KodiId), BasicItem['Type'])
                else:
                    if ItemIndex % 10000 == 0: # modulo 10000
                        ItemsFullQuery += 10000 * [None] # pre allocate memory

                    ItemsFullQuery[ItemIndex] = BasicItem['Id']

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

            ItemsFullQuery = list(dict.fromkeys(ItemsFullQuery)) # filter doubles

            if None in ItemsFullQuery:
                ItemsFullQuery.remove(None)

            if ItemsFullQuery:
                yield from self.get_Items_Ids(ItemsFullQuery, [MediaType], True, Basic, False, "")

    def get_Items_Ids(self, Ids, MediaTypes, Dynamic, Basic, BySyncedLibrarys, ProcessProgressId):
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
            MediaType = MediaTypes[0]
        else:
            MediaType = None

        start_new_thread(self.async_get_Items_Ids, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'IncludeItemTypes': MediaType}, Ids, BySyncedLibrarys, ProcessProgressId))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                return

            yield from Items

    def async_get_Items_Ids(self, Request, ItemsQueue, Params, Ids, BySyncedLibrarys, ProcessProgressId):
        Index = 0

        while Ids:
            MaxURILenght = 1500 # Uri lenght limitation
            IdsIndex = 100

            while len(",".join(Ids[:IdsIndex])) < MaxURILenght and IdsIndex < len(Ids):
                IdsIndex += 5

            Params['Ids'] = ",".join(Ids[:IdsIndex])  # Chunks of 100+X -> due to URI lenght limitation, more than 100+X Ids not possible to request (HTTP error 414)
            Ids = Ids[IdsIndex:]

            if BySyncedLibrarys:
                Found = False

                for WhitelistLibraryId, WhitelistLibraryName in self.EmbyServer.library.WhitelistUnique:
                    Params.update({'Recursive': True, 'ParentId': WhitelistLibraryId})
                    IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)

                    if 'Items' in IncomingData:
                        for Item in IncomingData['Items']:
                            Found = True
                            Item['Library'] = {'Id': WhitelistLibraryId, 'Name': WhitelistLibraryName}
                            ItemsQueue.put(Item)
                            Index += 1

                if not Found or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    return
            else:
                IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)

                if 'Items' not in IncomingData or not IncomingData['Items'] or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    del IncomingData  # release memory
                    return

                ItemsQueue.put(IncomingData['Items'])
                Index += len(IncomingData['Items'])

            del IncomingData  # release memory

            if not self.async_throttle_queries(Index, 10000, ProcessProgressId):
                ItemsQueue.put("QUIT")

        ItemsQueue.put("QUIT")

    def async_throttle_queries(self, Index, Limit, ProcessProgressId):
        # Throttle queries -> give Kodi time to catch up
        if ProcessProgressId and ProcessProgressId in self.ProcessProgress:
            ProcessLimit = Index - 2 * Limit

            while ProcessLimit > self.ProcessProgress[ProcessProgressId]:
                if utils.sleep(2) or self.ProcessProgress[ProcessProgressId] == -1: # Cancel
                    return False

                xbmc.log(f"EMBY.emby.api: Throttle queries {ProcessLimit} / {ProcessProgressId} / {self.ProcessProgress[ProcessProgressId]}", 1) # LOGINFO

        return True

    def get_Items_Custom(self, Request, Params, Limit, CustomLimit):
        ItemsQueue = queue.Queue()
        start_new_thread(self.async_get_Items, (Request, ItemsQueue, CustomLimit, Params, Limit))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                return

            yield from Items

    def get_Items(self, ParentId, MediaTypes, Basic, Recursive, Extra, ProcessProgressId=""):
        CustomLimit = False
        ItemsQueue = queue.Queue()

        for MediaType in MediaTypes:
            Limit = get_Limit(MediaType)
            Fields = self.get_Fields(MediaType, Basic, False)
            Params = {'ParentId': ParentId, 'IncludeItemTypes': MediaType, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit, 'Fields': Fields}

            if Extra:
                Params.update(Extra)

                if "Limit" in Extra:
                    Limit = Extra["Limit"]
                    CustomLimit = True

            start_new_thread(self.async_get_Items, (f"Users/{self.EmbyServer.ServerData['UserId']}/Items", ItemsQueue, not Recursive or CustomLimit, Params, Limit, ProcessProgressId))

            while True:
                Items = ItemsQueue.getall()

                if utils.SystemShutdown:
                    return

                if Items[-1] == "QUIT":
                    yield from Items[:-1]
                    return

                yield from Items

    def get_channelprogram(self):
        Limit = get_Limit("livetv")
        Params = {'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': "Overview", 'EnableTotalRecordCount': False, 'Limit': Limit}
        ItemsQueue = queue.Queue()
        start_new_thread(self.async_get_Items, ("LiveTv/Programs", ItemsQueue, False, Params, Limit))

        while True:
            Items = ItemsQueue.getall()

            if Items[-1] == "QUIT":
                yield from Items[:-1]
                return

            yield from Items

    def get_recommendations(self, ParentId):
        Fields = self.get_Fields("movie", False, True)
        Params = {'ParentId': ParentId, 'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': Fields, 'EnableTotalRecordCount': False, 'Recursive': True}
        IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': "Movies/Recommendations"}, False, False)
        Items = []

        for Data in IncomingData:
            if 'Items' in Data:
                Items += Data['Items']

        return Items

    def async_get_Items(self, Request, ItemsQueue, CustomLimit, Params, Limit, ProcessProgressId=""):
        Index = 0
        ItemCounter = 0

        while True:
            Params['StartIndex'] = Index
            IncomingData = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': Request}, False, False)
            DirectItems = Request.lower().find("latest") != -1

            if DirectItems:
                if not IncomingData or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    return

                ItemsQueue.put(IncomingData)
                ItemCounter += len(IncomingData)
            else:
                if 'Items' not in IncomingData or not IncomingData['Items'] or utils.SystemShutdown:
                    ItemsQueue.put("QUIT")
                    return

                ItemsQueue.put(IncomingData['Items'])
                ItemCounter += len(IncomingData['Items'])

            del IncomingData  # release memory

            if CustomLimit: # Emby server bug workaround
                ItemsQueue.put("QUIT")
                return

            if not self.async_throttle_queries(Index, Limit, ProcessProgressId):
                ItemsQueue.put("QUIT")

            Index += Limit

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
        Params = {'ParentId': parent_id, 'IncludeItemTypes': item_type, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': True, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': True, 'Limit': 1}

        if Extra:
            Params.update(Extra)

        Data = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if 'TotalRecordCount' in Data:
            return int(Data['TotalRecordCount'])

        return 0

    def browse_MusicByArtistId(self, Artist_id, Parent_id, MediaTypes, Dynamic):
        Items = []

        for MediaType in MediaTypes:
            Fields = self.get_Fields(MediaType, False, Dynamic)
            Data = self.EmbyServer.http.request({'params': {'ParentId': Parent_id, 'ArtistIds': Artist_id, 'IncludeItemTypes': MediaType, 'Recursive': True, 'Fields': Fields, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

            if 'Items' in Data:
                Items += Data['Items']

        return Items

    def get_timer(self, ProgramId):
        Data = self.EmbyServer.http.request({'params': {'programId': ProgramId}, 'type': "GET", 'handler': "LiveTv/Timers"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def set_timer(self, ProgramId):
        return self.EmbyServer.http.request({'data': json.dumps({'programId': ProgramId}), 'type': "POST", 'handler': "LiveTv/Timers"}, False, False)

    def delete_timer(self, TimerId):
        return self.EmbyServer.http.request({'type': "POST", 'handler': f"LiveTv/Timers/{TimerId}/Delete"}, False, False)

    def get_genres(self, ParentId, MediaTypes):
        Items = []

        for MediaType in MediaTypes:
            Fields = self.get_Fields(MediaType, False, False)
            Data = self.EmbyServer.http.request({'params': {'ParentId': ParentId, 'IncludeItemTypes': MediaType, 'Recursive': True, 'Fields': Fields}, 'type': "GET", 'handler': "Genres"}, False, False)

            if 'Items' in Data:
                Items += Data['Items']

        return Items

    def get_tags(self, ParentId, MediaTypes):
        Items = []

        for MediaType in MediaTypes:
            Fields = self.get_Fields(MediaType, False, False)
            Data = self.EmbyServer.http.request({'params': {'ParentId': ParentId, 'IncludeItemTypes': MediaType, 'Recursive': True, 'Fields': Fields}, 'type': "GET", 'handler': "Tags"}, False, False)

            if 'Items' in Data:
                Items += Data['Items']

        return Items

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

    def get_Item_Binary(self, Id):
        Data = self.EmbyServer.http.request({'type': "GET", 'handler': f"Items/{Id}/Download"}, False, True)
        return Data

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
        return self.EmbyServer.http.request({'params': {'DeviceId': utils.device_id}, 'type': "GET", 'handler': "Sessions"}, False, False)

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

    def get_channels(self):
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'EnableImages': True, 'EnableUserData': True, 'Fields': EmbyFields['tvchannel']}, 'type': "GET", 'handler': "LiveTv/Channels"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_specialfeatures(self, item_id):
        return self.EmbyServer.http.request({'params': {'Fields': "Path,MediaSources,PresentationUniqueKey", 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/SpecialFeatures"}, False, False)

    def get_intros(self, item_id):
        return self.EmbyServer.http.request({'params': {'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/Intros"}, False, False)

    def get_additional_parts(self, item_id):
        return self.EmbyServer.http.request({'params': {'Fields': "Path,MediaSources"}, 'type': "GET", 'handler': f"Videos/{item_id}/AdditionalParts"}, False, False)

    def get_local_trailers(self, item_id):
        Fields = EmbyFields["trailer"]
        return self.EmbyServer.http.request({'params': {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/LocalTrailers"}, False, False)

    def get_themes(self, item_id, Songs, Videos):
        return self.EmbyServer.http.request({'params': {'Fields': "Path", 'UserId': self.EmbyServer.ServerData['UserId'], 'InheritFromParent': True, 'EnableThemeSongs': Songs, 'EnableThemeVideos': Videos, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Items/{item_id}/ThemeMedia"}, False, False)

    def get_sync_queue(self, date):
        return self.EmbyServer.http.request({'params': {'LastUpdateDT': date}, 'type': "GET", 'handler': f"Emby.Kodi.SyncQueue/{self.EmbyServer.ServerData['UserId']}/GetItems"}, False, False)

    def get_system_info(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "System/Configuration"}, False, False)

    def set_progress(self, item_id, Progress, PlayCount):
        Params = {"PlaybackPositionTicks": Progress}

        if PlayCount != -1:
            Params.update({"PlayCount": PlayCount, "Played": bool(PlayCount)})

        self.EmbyServer.http.request({'data': json.dumps(Params), 'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/UserData"}, False, False)

    def set_played(self, item_id, PlayCount):
        if PlayCount:
            self.EmbyServer.http.request({'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{item_id}"}, False, False)
        else:
            self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/PlayedItems/{item_id}"}, False, False)

    def refresh_item(self, item_id):
        self.EmbyServer.http.request({'data': json.dumps({'Recursive': True, 'ImageRefreshMode': "FullRefresh", 'MetadataRefreshMode': "FullRefresh", 'ReplaceAllImages': False, 'ReplaceAllMetadata': True}), 'type': "POST", 'handler': f"Items/{item_id}/Refresh"}, False, False)

    def favorite(self, item_id, Add):
        if Add:
            self.EmbyServer.http.request({'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{item_id}"}, False, False)
        else:
            self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/FavoriteItems/{item_id}"}, False, False)

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

    def delete_item(self, item_id):
        self.EmbyServer.http.request({'type': "DELETE", 'handler': f"Items/{item_id}"}, False, False)

    def get_stream_statuscode(self, EmbyID, MediasourceID, PlaySessionId):
        return self.EmbyServer.http.request({'params': {'static': True, 'MediaSourceId': MediasourceID, 'PlaySessionId': PlaySessionId, 'DeviceId': utils.device_id}, 'type': "HEAD", 'handler': f"videos/{EmbyID}/stream"}, False, False)

    def get_Subtitle_Binary(self, EmbyID, MediasourceID, SubtitleId, SubtitleFormat):
        return self.EmbyServer.http.request({'type': "GET", 'handler': f"/videos/{EmbyID}/{MediasourceID}/Subtitles/{SubtitleId}/stream.{SubtitleFormat}"}, False, True, False)

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

def get_Limit(MediaTypes):
    Factor = EmbyPagingFactors[MediaTypes.lower()]
    return int(utils.limitIndex) * Factor

from _thread import start_new_thread
import queue
import json
from helper import utils
from database import dbio
from . import listitem

EmbyPagingFactors = {"musicartist": 100, "musicalbum": 100, "audio": 200, "movie": 50, "boxset": 50, "series": 50, "season": 50, "episode": 50, "musicvideo": 50, "video": 50, "everything": 50, "photo": 50, "photoalbum": 50, "playlist": 50, "channels": 50, "folder": 1000, "livetv": 100}
EmbyFields = {
    "musicartist": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicalbum": ("Genres", "SortName", "ProductionYear", "DateCreated", "ProviderIds", "Overview", "Path", "PresentationUniqueKey", "Studios", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "audio": ("Genres", "SortName", "ProductionYear", "DateCreated", "MediaStreams", "ProviderIds", "Overview", "Path", "ParentId", "PresentationUniqueKey", "PremiereDate", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "movie": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "trailer": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags"),
    "boxset": ("Overview", "PresentationUniqueKey", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "series": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProviderIds", "ParentId", "Status", "PresentationUniqueKey", "OriginalTitle", "Tags", "LocalTrailerCount", "RemoteTrailers", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "season": ("PresentationUniqueKey", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "episode": ("SpecialEpisodeNumbers", "Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "musicvideo": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "Tags", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "Chapters", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "video": ("Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "ProviderIds", "ParentId", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "Chapters", "Tags", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "everything": ("SpecialEpisodeNumbers", "Path", "Genres", "SortName", "Studios", "Writer", "Taglines", "LocalTrailerCount", "Video3DFormat", "OfficialRating", "PremiereDate", "ProductionYear", "DateCreated", "People", "Overview", "CommunityRating", "CriticRating", "ShortOverview", "ProductionLocations", "Tags", "ProviderIds", "ParentId", "RemoteTrailers", "MediaSources", "PresentationUniqueKey", "OriginalTitle", "AlternateMediaSources", "PartCount", "SpecialFeatureCount", "Chapters", "MediaStreams", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photo": ("Path", "SortName", "ProductionYear", "ParentId", "PremiereDate", "Width", "Height", "Tags", "DateCreated", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "photoalbum": ("Path", "SortName", "Taglines", "DateCreated", "ShortOverview", "ProductionLocations", "Tags", "ParentId", "OriginalTitle", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "tvchannel": ("Genres", "SortName", "Taglines", "DateCreated", "Overview", "MediaSources", "Tags", "MediaStreams", "UserDataPlayCount", "UserDataLastPlayedDate"),
    "folder": ("Path", )
}
LiveStreamEmbyID = 0

class API:
    def __init__(self, EmbyServer):
        self.DynamicListsRemoveFields = ()
        self.EmbyServer = EmbyServer
        self.update_settings()

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
        if EmbyID == LiveStreamEmbyID: # skip identical queries
            return "", "", ""

        globals()["LiveStreamEmbyID"] = EmbyID
        PlaybackInfoData = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId']}, 'type': "POST", 'handler': f"Items/{EmbyID}/PlaybackInfo"}, True, False)
        OpenToken = PlaybackInfoData['MediaSources'][0]['OpenToken']
        MediasourceID = PlaybackInfoData['MediaSources'][0]['Id']
        OpenData = self.EmbyServer.http.request({'data': json.dumps({'UserId': self.EmbyServer.ServerData['UserId'], 'playsessionid': PlaySessionId, 'itemid': EmbyID, 'AutoOpenLiveStream': 'true', 'OpenToken': OpenToken}), 'type': "POST", 'handler': "LiveStreams/Open"}, True, False)

        if not OpenData:
            return "FAIL", "", ""

        return MediasourceID, OpenData['MediaSource']['LiveStreamId'], OpenData['MediaSource']['Container']

    def close_livestream(self, LiveStreamId):
        globals()["LiveStreamEmbyID"] = 0
        self.EmbyServer.http.request({'data': json.dumps({'LiveStreamId': LiveStreamId}), 'type': "POST", 'handler': "LiveStreams/Close"}, False, False)

    def get_Items_dynamic(self, parent_id, MediaTypes, Basic, Recursive, Extra, Resume, Latest=False, SkipLocalDB=False, UseAncestors=False):
        SingleRun = False
        Limit = get_Limit(MediaTypes)
        IncludeItemTypes, _ = self.get_MediaData(MediaTypes, Basic, True)
        params = {'ParentId': parent_id, 'IncludeItemTypes': IncludeItemTypes, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit}

        if Extra:
            params.update(Extra)

            if "Limit" in Extra:
                Limit = Extra["Limit"]
                SingleRun = True

        index = 0

        if Resume:
            url = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Resume"
        elif Latest:
            url = f"Users/{self.EmbyServer.ServerData['UserId']}/Items/Latest"
        else:
            url = f"Users/{self.EmbyServer.ServerData['UserId']}/Items"

        while True:
            params['StartIndex'] = index
            IncomingData = self.EmbyServer.http.request({'params': params, 'type': "GET", 'handler': url}, False, False)

            if Latest:
                if not IncomingData:
                    break

                IncomingData = {'Items': IncomingData}
            else:
                if 'Items' not in IncomingData:
                    break

                if not IncomingData['Items']:
                    break

            ItemsReturn = []
            ItemsFullQuery = ()

            if SkipLocalDB:
                for Item in IncomingData['Items']:
                    ItemsFullQuery += (Item['Id'],)
            else:
                KodiItems = ()
                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "get_Items_dynamic")
                videodb = dbio.DBOpenRO("video", "get_Items_dynamic")
                musicdb = dbio.DBOpenRO("music", "get_Items_dynamic")

                for Item in IncomingData['Items']:
                    if Item['Type'] in ("Photo", "PhotoAlbum", "BoxSet"):
                        ItemsFullQuery += (Item['Id'],)
                        continue

                    KodiId, _ = embydb.get_KodiId_KodiType_by_EmbyId_EmbyLibraryId(Item['Id'], parent_id) # Requested video is synced to KodiDB.zz

                    if not KodiId and UseAncestors and Item['Type'] in ("Movie", "Series", "Season", "Episode", "MusicVideo", "MusicArtist", "MusicAlbum", "Audio"):
                        Ancestors = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId']}, 'type': "GET", 'handler': f"Items/{Item['Id']}/Ancestors"}, False, False)

                        for Ancestor in Ancestors:
                            KodiId, _ = embydb.get_KodiId_KodiType_by_EmbyId_EmbyLibraryId(Item['Id'], Ancestor['Id']) # Requested video is synced to KodiDB.zz

                            if KodiId:
                                break

                    if KodiId:
                        if Item['Type'] == "Movie":
                            KodiItems += ((videodb.get_movie_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "Series":
                            KodiItems += ((videodb.get_tvshows_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "Season":
                            KodiItems += ((videodb.get_season_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "Episode":
                            KodiItems += ((videodb.get_episode_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "BoxSet":
                            KodiItems += ((videodb.get_boxset_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "MusicVideo":
                            KodiItems += ((videodb.get_musicvideos_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "MusicArtist":
                            KodiItems += ((musicdb.get_artist_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "MusicAlbum":
                            KodiItems += ((musicdb.get_album_metadata_for_listitem(KodiId), Item['Type']),)
                        elif Item['Type'] == "Audio":
                            KodiItems += ((musicdb.get_song_metadata_for_listitem(KodiId), Item['Type']),)
                    else:
                        ItemsFullQuery += (Item['Id'],)

                for KodiItem in KodiItems:
                    if KodiItem[0]:
                        isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem[0])

                        if 'pathandfilename' in KodiItem[0]:
                            ItemsReturn.append({"ListItem": ListItem, "Path": KodiItem[0]['pathandfilename'], "isFolder": isFolder, "Type": KodiItem[1]})
                        else:
                            ItemsReturn.append({"ListItem": ListItem, "Path": KodiItem[0]['path'], "isFolder": isFolder, "Type": KodiItem[1]})

                IncomingData['Items'].clear()  # free memory
                dbio.DBCloseRO("video", "get_Items_dynamic")
                dbio.DBCloseRO("music", "get_Items_dynamic")
                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "get_Items_dynamic")

            # Load All Data
            while ItemsFullQuery:
                TempItemsFullQuery = ItemsFullQuery[:100]  # Chunks of 100
                ItemsFullQuery = ItemsFullQuery[100:]
                ItemsFull = self.get_Item(",".join(TempItemsFullQuery), ["Everything"], True, Basic, False)
                ItemsReturn += ItemsFull

            for ItemReturn in ItemsReturn:
                yield ItemReturn

            if not Recursive or SingleRun: # Emby server bug workaround
                break

            index += Limit

    def get_Items(self, parent_id, MediaTypes, Basic, Recursive, Extra):
        SingleRun = False
        Limit = get_Limit(MediaTypes)
        IncludeItemTypes, Fields = self.get_MediaData(MediaTypes, Basic, False)
        params = {'ParentId': parent_id, 'IncludeItemTypes': IncludeItemTypes, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': Recursive, 'Limit': Limit, 'Fields': Fields}

        if Extra:
            params.update(Extra)

            if "Limit" in Extra:
                Limit = Extra["Limit"]
                SingleRun = True

        ItemsQueue = queue.Queue()
        start_new_thread(self.async_get_Items, (ItemsQueue, not Recursive or SingleRun, params, Limit))

        while True:
            Item = ItemsQueue.get()

            if Item == "QUIT":
                return

            yield Item

    def async_get_Items(self, ItemsQueue, SingleLoop, params, Limit):
        index = 0

        while True:
            params['StartIndex'] = index
            IncomingData = self.EmbyServer.http.request({'params': params, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

            if 'Items' not in IncomingData:
                ItemsQueue.put("QUIT")
                return

            if not IncomingData['Items']:
                ItemsQueue.put("QUIT")
                return

            for Item in IncomingData['Items']:
                ItemsQueue.put(Item)

            IncomingData['Items'].clear()  # free memory

            if SingleLoop: # Emby server bug workaround
                ItemsQueue.put("QUIT")
                return

            index += Limit

    def get_TotalRecords(self, parent_id, item_type, Extra):
        params = {'ParentId': parent_id, 'IncludeItemTypes': item_type, 'CollapseBoxSetItems': False, 'EnableTotalRecordCount': True, 'LocationTypes': "FileSystem,Remote,Offline", 'Recursive': True, 'Limit': 1}

        if Extra:
            params.update(Extra)

        Data = self.EmbyServer.http.request({'params': params, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if 'TotalRecordCount' in Data:
            return int(Data['TotalRecordCount'])

        return 0

    def browse_MusicByArtistId(self, Artist_id, Parent_id, MediaTypes, Dynamic):
        IncludeItemTypes, Fields = self.get_MediaData(MediaTypes, False, Dynamic)
        Data = self.EmbyServer.http.request({'params': {'ParentId': Parent_id, 'ArtistIds': Artist_id, 'IncludeItemTypes': IncludeItemTypes, 'Recursive': True, 'Fields': Fields, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

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
        IncludeItemTypes, Fields = self.get_MediaData(MediaTypes, False, False)
        Data = self.EmbyServer.http.request({'params': {'ParentId': ParentId, 'IncludeItemTypes': IncludeItemTypes, 'Recursive': True, 'Fields': Fields}, 'type': "GET", 'handler': "Genres"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_tags(self, ParentId, MediaTypes):
        IncludeItemTypes, Fields = self.get_MediaData(MediaTypes, False, False)
        Data = self.EmbyServer.http.request({'params': {'ParentId': ParentId, 'IncludeItemTypes': IncludeItemTypes, 'Recursive': True, 'Fields': Fields}, 'type': "GET", 'handler': "Tags"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

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

    def get_Item_Basic(self, Id, ParentId, Type):
        Data = self.EmbyServer.http.request({'params': {'ParentId': ParentId, 'Ids': Id, 'Recursive': True, 'IncludeItemTypes': Type, 'Limit': 1, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_Item_Binary(self, Id):
        Data = self.EmbyServer.http.request({'type': "GET", 'handler': f"Items/{Id}/Download"}, False, True)
        return Data

    def get_Image_Binary(self, Id, ImageType, ImageIndex, ImageTag, UserImage=False):
        Params = {}

        if utils.enableCoverArt:
            Params["EnableImageEnhancers"]: True
        else:
            Params["EnableImageEnhancers"]: False

        if utils.compressArt:
            Params["Quality"]: 70


        if UserImage:
            BinaryData, Headers = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Users/{Id}/Images/{ImageType}?Format=original"}, False, True, True)
        else:
            BinaryData, Headers = self.EmbyServer.http.request({'params': Params, 'type': "GET", 'handler': f"Items/{Id}/Images/{ImageType}/{ImageIndex}?{ImageTag}"}, False, True, True)

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

    def get_Item(self, Ids, MediaTypes, Dynamic, Basic, SingleItemQuery=True, Specials=False):
        _, Fields = self.get_MediaData(MediaTypes, Basic, Dynamic)

        if Specials: # Bugfix workaround
            Data = self.EmbyServer.http.request({'params': {'Ids': Ids, 'Fields': Fields, 'IncludeItemTypes': 'Workaround', 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)
        else:
            Data = self.EmbyServer.http.request({'params': {'Ids': Ids, 'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items"}, False, False)

        if SingleItemQuery:
            if 'Items' in Data:
                if Data['Items']:
                    return Data['Items'][0]

            return {}

        if 'Items' in Data:
            return Data['Items']

        return []

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

    def ping(self):
        self.EmbyServer.http.request({'type': "POST", 'handler': "System/Ping"}, False, False)

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

    def get_channelprogram(self):
        Limit = get_Limit(("LiveTV",))
        index = 0

        while True:
            IncomingData = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'Fields': "Overview", 'Limit': Limit, 'StartIndex': index}, 'type': "GET", 'handler': "LiveTv/Programs"}, False, False)

            if 'Items' not in IncomingData:
                break

            if not IncomingData['Items']:
                break

            for Item in IncomingData['Items']:
                yield Item

            IncomingData['Items'].clear()  # free memory
            index += Limit

    def get_specialfeatures(self, item_id, MediaTypes):
        _, Fields = self.get_MediaData(MediaTypes, False, False)
        return self.EmbyServer.http.request({'params': {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/SpecialFeatures"}, False, False)

    def get_intros(self, item_id):
        return self.EmbyServer.http.request({'params': {'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/Intros"}, False, False)

    def get_additional_parts(self, item_id, MediaTypes):
        _, Fields = self.get_MediaData(MediaTypes, False, False)
        return self.EmbyServer.http.request({'params': {'Fields': Fields}, 'type': "GET", 'handler': f"Videos/{item_id}/AdditionalParts"}, False, False)

    def get_local_trailers(self, item_id):
        _, Fields = self.get_MediaData(["trailer"], False, False)
        return self.EmbyServer.http.request({'params': {'Fields': Fields, 'EnableTotalRecordCount': False, 'LocationTypes': "FileSystem,Remote,Offline"}, 'type': "GET", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/LocalTrailers"}, False, False)

    def get_themes(self, item_id, Songs, Videos):
        return self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'InheritFromParent': True, 'EnableThemeSongs': Songs, 'EnableThemeVideos': Videos, 'EnableTotalRecordCount': False}, 'type': "GET", 'handler': f"Items/{item_id}/ThemeMedia"}, False, False)

    def get_plugins(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "Plugins"}, False, False)

    def get_sync_queue(self, date):
        return self.EmbyServer.http.request({'params': {'LastUpdateDT': date}, 'type': "GET", 'handler': f"Emby.Kodi.SyncQueue/{self.EmbyServer.ServerData['UserId']}/GetItems"}, False, False)

    def get_system_info(self):
        return self.EmbyServer.http.request({'type': "GET", 'handler': "System/Configuration"}, False, False)

    def set_progress(self, item_id, Progress, PlayCount):
        params = {"PlaybackPositionTicks": Progress}

        if PlayCount != -1:
            params["PlayCount"] = PlayCount
            params["Played"] = bool(PlayCount)

        self.EmbyServer.http.request({'data': json.dumps(params), 'type': "POST", 'handler': f"Users/{self.EmbyServer.ServerData['UserId']}/Items/{item_id}/UserData"}, False, False)

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

    def get_MediaData(self, MediaTypes, Basic, Dynamic):
        IncludeItemTypes = ",".join(MediaTypes)
        Fields = []

        if not Basic:
            if MediaTypes[0].lower() == "everything":
                IncludeItemTypes = None

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

        return IncludeItemTypes, Fields

    def get_upcoming(self, ParentId, MediaTypes):
        _, Fields = self.get_MediaData(MediaTypes, False, False)
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': Fields, 'EnableImages': True, 'EnableUserData': True}, 'type': "GET", 'handler': "Shows/Upcoming"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

    def get_NextUp(self, ParentId, MediaTypes):
        _, Fields = self.get_MediaData(MediaTypes, False, False)
        Data = self.EmbyServer.http.request({'params': {'UserId': self.EmbyServer.ServerData['UserId'], 'ParentId': ParentId, 'Fields': Fields, 'EnableImages': True, 'EnableUserData': True, 'LegacyNextUp': True}, 'type': "GET", 'handler': "Shows/NextUp"}, False, False)

        if 'Items' in Data:
            return Data['Items']

        return []

def get_Limit(MediaTypes):
    Factor = 1000000

    for MediaType in MediaTypes:
        MediaTypeLower = MediaType.lower()

        if EmbyPagingFactors[MediaTypeLower] < Factor:
            Factor = EmbyPagingFactors[MediaTypeLower]

    return int(utils.limitIndex) * Factor

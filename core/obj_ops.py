# -*- coding: utf-8 -*-
import json

class Objects():
    def __init__(self):
        self.mapped_item = {}
        self.objects = {
            "MovieProviderName": "imdb",
            "Movie": {
                "Id": "Id",
                "Title": "Name",
                "SortTitle": "SortName",
                "Path": "Path",
                "Genres": "Genres",
                "UniqueId": "ProviderIds/Imdb",
                "UniqueIds": "ProviderIds",
                "Rating": "CommunityRating",
                "Year": "ProductionYear",
                "Votes": "VoteCount",
                "Plot": "Overview",
                "ShortPlot": "ShortOverview",
                "People": "People",
                "Writers": "People:?Type=Writer$Name",
                "Directors": "People:?Type=Director$Name",
                "Cast": "People:?Type=Actor$Name",
                "Tagline": "Taglines/0",
                "Mpaa": "OfficialRating",
                "Country": "ProductionLocations/0",
                "Countries": "ProductionLocations",
                "Studios": "Studios:?$Name",
                "Studio": "Studios/0/Name",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "LocalTrailer": "LocalTrailerCount",
                "Trailer": "RemoteTrailers/0/Url",
                "DateAdded": "DateCreated",
                "Premiered": "PremiereDate",
                "Played": "UserData/Played",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "Favorite": "UserData/IsFavorite",
                "Resume": "UserData/PlaybackPositionTicks",
                "Tags": "Tags",
                "TagItems": "TagItems:?$Name",
                "Subtitles": "MediaSources/0/MediaStreams:?Type=Subtitle$Language",
                "Audio": "MediaSources/0/MediaStreams:?Type=Audio",
                "Video": "MediaSources/0/MediaStreams:?Type=Video",
                "Container": "MediaSources/0/Container",
                "EmbyParentId": "ParentId",
                "CriticRating": "CriticRating",
                "PresentationKey": "PresentationUniqueKey",
                "OriginalTitle": "OriginalTitle"
            },
            "MovieUserData": {
                "Id": "Id",
                "Title": "Name",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Resume": "UserData/PlaybackPositionTicks",
                "Favorite": "UserData/IsFavorite",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "Played": "UserData/Played",
                "PresentationKey": "PresentationUniqueKey"
            },
            "Boxset": {
                "Id": "Id",
                "Title": "Name",
                "Overview": "Overview",
                "PresentationKey": "PresentationUniqueKey",
                "Etag": "Etag"
            },
            "SeriesProviderName": "tvdb",
            "Series": {
                "Id": "Id",
                "Title": "Name",
                "SortTitle": "SortName",
                "People": "People",
                "Path": "Path",
                "Genres": "Genres",
                "Plot": "Overview",
                "Rating": "CommunityRating",
                "Year": "ProductionYear",
                "Votes": "VoteCount",
                "Premiere": "PremiereDate",
                "UniqueId": "ProviderIds/Tvdb",
                "UniqueIds": "ProviderIds",
                "Mpaa": "OfficialRating",
                "Studios": "Studios:?$Name",
                "Tags": "Tags",
                "TagItems": "TagItems:?$Name",
                "Favorite": "UserData/IsFavorite",
                "RecursiveCount": "RecursiveItemCount",
                "EmbyParentId": "ParentId",
                "Status": "Status",
                "PresentationKey": "PresentationUniqueKey",
                "OriginalTitle": "OriginalTitle"
            },
            "Season": {
                "Id": "Id",
                "Index": "IndexNumber",
                "SeriesId": "SeriesId",
                "Location": "LocationType",
                "Title": "Name",
                "EmbyParentId": "ParentId",
                "PresentationKey": "PresentationUniqueKey"
            },
            "EpisodeProviderName": "tvdb",
            "Episode": {
                "Id": "Id",
                "Title": "Name",
                "Path": "Path",
                "Plot": "Overview",
                "People": "People",
                "Rating": "CommunityRating",
                "Writers": "People:?Type=Writer$Name",
                "Directors": "People:?Type=Director$Name",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Premiere": "PremiereDate",
                "Votes": "VoteCount",
                "UniqueId": "ProviderIds/Tvdb",
                "UniqueIds": "ProviderIds",
                "SeriesId": "SeriesId",
                "Season": "ParentIndexNumber",
                "Index": "IndexNumber",
                "AbsoluteNumber": "AbsoluteEpisodeNumber",
                "AirsAfterSeason": "AirsAfterSeasonNumber",
                "AirsBeforeSeason": "AirsBeforeSeasonNumber,SortParentIndexNumber",
                "AirsBeforeEpisode": "AirsBeforeEpisodeNumber,SortIndexNumber",
                "Played": "UserData/Played",
                "PlayCount": "UserData/PlayCount",
                "DateAdded": "DateCreated",
                "DatePlayed": "UserData/LastPlayedDate",
                "Resume": "UserData/PlaybackPositionTicks",
                "Subtitles": "MediaSources/0/MediaStreams:?Type=Subtitle$Language",
                "Audio": "MediaSources/0/MediaStreams:?Type=Audio",
                "Video": "MediaSources/0/MediaStreams:?Type=Video",
                "Container": "MediaSources/0/Container",
                "Location": "LocationType",
                "EmbyParentId": "SeriesId,ParentId",
                "PresentationKey": "PresentationUniqueKey",
                "OriginalTitle": "OriginalTitle"
            },
            "EpisodeUserData": {
                "Id": "Id",
                "Title": "Name",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Resume": "UserData/PlaybackPositionTicks",
                "Favorite": "UserData/IsFavorite",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "DateAdded": "DateCreated",
                "Played": "UserData/Played",
                "PresentationKey": "PresentationUniqueKey"
            },
            "MusicVideo": {
                "Id": "Id",
                "Title": "Name",
                "Path": "Path",
                "DateAdded": "DateCreated",
                "DatePlayed": "UserData/LastPlayedDate",
                "PlayCount": "UserData/PlayCount",
                "Resume": "UserData/PlaybackPositionTicks",
                "SortTitle": "SortName",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Plot": "Overview",
                "Year": "ProductionYear",
                "Premiere": "PremiereDate",
                "Genres": "Genres",
                "Studios": "Studios?$Name",
                "Artists": "ArtistItems:?$Name",
                "ArtistItems": "ArtistItems",
                "Album": "Album",
                "Index": "Track",
                "People": "People",
                "Subtitles": "MediaSources/0/MediaStreams:?Type=Subtitle$Language",
                "Audio": "MediaSources/0/MediaStreams:?Type=Audio",
                "Video": "MediaSources/0/MediaStreams:?Type=Video",
                "Container": "MediaSources/0/Container",
                "Tags": "Tags",
                "TagItems": "TagItems:?$Name",
                "Played": "UserData/Played",
                "Favorite": "UserData/IsFavorite",
                "Directors": "People:?Type=Director$Name",
                "EmbyParentId": "ParentId",
                "PresentationKey": "PresentationUniqueKey"
            },
            "MusicVideoUserData": {
                "Id": "Id",
                "Title": "Name",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Resume": "UserData/PlaybackPositionTicks",
                "Favorite": "UserData/IsFavorite",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "Played": "UserData/Played",
                "PresentationKey": "PresentationUniqueKey"
            },
            "Artist": {
                "Id": "Id",
                "Name": "Name",
                "UniqueId": "ProviderIds/MusicBrainzArtist",
                "Genres": "Genres",
                "Bio": "Overview",
                "EmbyParentId": "ParentId",
                "DateAdded": "DateCreated",
                "SortName": "SortName",
                "PresentationKey": "PresentationUniqueKey"
            },
            "Album": {
                "Id": "Id",
                "Title": "Name",
                "UniqueId": "ProviderIds/MusicBrainzAlbum",
                "Year": "ProductionYear",
                "Genres": "Genres",
                "Bio": "Overview",
                "AlbumArtists": "AlbumArtists",
                "Artists": "AlbumArtists:?$Name",
                "ArtistItems": "ArtistItems",
                "EmbyParentId": "ParentId",
                "DateAdded": "DateCreated",
                "PresentationKey": "PresentationUniqueKey"
            },
            "Song": {
                "Id": "Id",
                "Title": "Name",
                "Path": "Path",
                "DateAdded": "DateCreated",
                "Played": "UserData/Played",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "UniqueId": "ProviderIds/MusicBrainzTrackId",
                "Genres": "Genres",
                "Artists": "ArtistItems:?$Name",
                "Index": "IndexNumber",
                "Disc": "ParentIndexNumber",
                "Year": "ProductionYear",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Comment": "Overview",
                "ArtistItems": "ArtistItems",
                "AlbumArtists": "AlbumArtists",
                "Album": "Album",
                "SongAlbumId": "AlbumId",
                "Container": "MediaSources/0/Container",
                "EmbyParentId": "ParentId",
                "PresentationKey": "PresentationUniqueKey"
            },
            "SongUserData": {
                "Id": "Id",
                "Title": "Name",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "DateAdded": "DateCreated",
                "Played": "UserData/Played",
                "PresentationKey": "PresentationUniqueKey"
            },
            "Artwork": {
                "Id": "Id",
                "Tags": "ImageTags",
                "BackdropTags": "BackdropImageTags"
            },
            "ArtworkParent": {
                "Id": "Id",
                "Tags": "ImageTags",
                "BackdropTags": "BackdropImageTags",
                "ParentBackdropId": "ParentBackdropItemId",
                "ParentBackdropTags": "ParentBackdropImageTags",
                "ParentLogoId": "ParentLogoItemId",
                "ParentLogoTag": "ParentLogoImageTag",
                "ParentArtId": "ParentArtItemId",
                "ParentArtTag": "ParentArtImageTag",
                "ParentThumbId": "ParentThumbItemId",
                "ParentThumbTag": "ParentThumbTag",
                "SeriesTag": "SeriesPrimaryImageTag",
                "SeriesId": "SeriesId"
            },
            "ArtworkMusic": {
                "Id": "Id",
                "Tags": "ImageTags",
                "BackdropTags": "BackdropImageTags",
                "ParentBackdropId": "ParentBackdropItemId",
                "ParentBackdropTags": "ParentBackdropImageTags",
                "ParentLogoId": "ParentLogoItemId",
                "ParentLogoTag": "ParentLogoImageTag",
                "ParentArtId": "ParentArtItemId",
                "ParentArtTag": "ParentArtImageTag",
                "ParentThumbId": "ParentThumbItemId",
                "ParentThumbTag": "ParentThumbTag",
                "AlbumId": "AlbumId",
                "AlbumTag": "AlbumPrimaryImageTag"
            },
            "BrowseVideo": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "Plot": "Overview",
                "Year": "ProductionYear",
                "Writers": "People:?Type=Writer$Name",
                "Directors": "People:?Type=Director$Name",
                "Cast": "People:?Type=Actor$Name",
                "Mpaa": "OfficialRating",
                "Genres": "Genres",
                "Studios": "Studios:?$Name,SeriesStudio",
                "Premiere": "PremiereDate,DateCreated",
                "Rating": "CommunityRating",
                "Votes": "VoteCount",
                "Season": "ParentIndexNumber",
                "Index": "IndexNumber,AbsoluteEpisodeNumber",
                "SeriesName": "SeriesName",
                "Countries": "ProductionLocations",
                "Played": "UserData/Played",
                "People": "People",
                "ShortPlot": "ShortOverview",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Tagline": "Taglines/0",
                "UniqueId": "ProviderIds/Imdb",
                "DatePlayed": "UserData/LastPlayedDate",
                "Artists": "ArtistItems:?$Name",
                "Album": "Album",
                "Path": "Path",
                "LocalTrailer": "LocalTrailerCount",
                "Trailer": "RemoteTrailers/0/Url",
                "DateAdded": "DateCreated",
                "SortTitle": "SortName",
                "PlayCount": "UserData/PlayCount",
                "Resume": "UserData/PlaybackPositionTicks",
                "Subtitles": "MediaStreams:?Type=Subtitle$Language",
                "Audio": "MediaStreams:?Type=Audio",
                "Video": "MediaStreams:?Type=Video",
                "Container": "Container",
                "Unwatched": "UserData/UnplayedItemCount",
                "ChildCount": "ChildCount",
                "RecursiveCount": "RecursiveItemCount",
                "MediaType": "MediaType",
                "CriticRating": "CriticRating",
                "Status": "Status",
                "OriginalTitle": "OriginalTitle"
            },
            "BrowseAudio": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "Index": "IndexNumber",
                "Disc": "ParentIndexNumber",
                "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
                "Year": "ProductionYear",
                "Genre": "Genres/0",
                "Album": "Album",
                "Artists": "ArtistItems/0/Name",
                "Rating": "CommunityRating",
                "PlayCount": "UserData/PlayCount",
                "DatePlayed": "UserData/LastPlayedDate",
                "UniqueId": "ProviderIds/MusicBrainzTrackId,ProviderIds/MusicBrainzAlbum,ProviderIds/MusicBrainzArtist",
                "Comment": "Overview",
                "DateAdded": "DateCreated",
                "Played": "UserData/Played"
            },
            "BrowsePhoto": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "Width": "Width",
                "Height": "Height",
                "Size": "Size",
                "Overview": "Overview",
                "CameraMake": "CameraMake",
                "CameraModel": "CameraModel",
                "ExposureTime": "ExposureTime",
                "FocalLength": "FocalLength",
                "DateAdded": "DateCreated"
            },
            "BrowseFolder": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "Overview": "Overview"
            },
            "BrowseGenre": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "Tags": "ImageTags",
                "BackdropTags": "BackdropImageTags"
            },
            "BrowseChannel": {
                "Id": "Id",
                "Title": "Name",
                "Type": "Type",
                "ProgramName": "CurrentProgram/Name",
                "Played": "CurrentProgram/UserData/Played",
                "PlayCount": "CurrentProgram/UserData/PlayCount",
                "Runtime": "CurrentProgram/RunTimeTicks",
                "MediaType": "MediaType"
            },
            "MediaSources": {
                "emby_id": "emby_id",
                "MediaIndex": "MediaIndex",
                "Protocol": "Protocol",
                "Id": "Id",
                "Path": "Path",
                "Type": "Type",
                "Container": "Container",
                "Size": "Size",
                "Name": "Name",
                "IsRemote": "IsRemote",
                "RunTimeTicks": "RunTimeTicks",
                "SupportsTranscoding": "SupportsTranscoding",
                "SupportsDirectStream": "SupportsDirectStream",
                "SupportsDirectPlay": "SupportsDirectPlay",
                "IsInfiniteStream": "IsInfiniteStream",
                "RequiresOpening": "RequiresOpening",
                "RequiresClosing": "RequiresClosing",
                "RequiresLooping": "RequiresLooping",
                "SupportsProbing": "SupportsProbing",
                "Formats": "Formats",
                "Bitrate": "Bitrate",
                "RequiredHttpHeaders": "RequiredHttpHeaders",
                "ReadAtNativeFramerate": "ReadAtNativeFramerate",
                "DefaultAudioStreamIndex": "DefaultAudioStreamIndex"
            },
            "AudioStreams": {
                "emby_id": "emby_id",
                "MediaIndex": "MediaIndex",
                "AudioIndex": "AudioIndex",
                "StreamIndex": "StreamIndex",
                "Codec": "Codec",
                "Language": "Language",
                "TimeBase": "TimeBase",
                "CodecTimeBase": "CodecTimeBase",
                "DisplayTitle": "DisplayTitle",
                "DisplayLanguage": "DisplayLanguage",
                "IsInterlaced": "IsInterlaced",
                "ChannelLayout": "ChannelLayout",
                "BitRate": "BitRate",
                "Channels": "Channels",
                "SampleRate": "SampleRate",
                "IsDefault": "IsDefault",
                "IsForced": "IsForced",
                "Profile": "Profile",
                "Type": "Type",
                "IsExternal": "IsExternal",
                "IsTextSubtitleStream": "IsTextSubtitleStream",
                "SupportsExternalStream": "SupportsExternalStream",
                "Protocol": "Protocol"
            },
            "VideoStreams": {
                "emby_id": "emby_id",
                "MediaIndex": "MediaIndex",
                "VideoIndex": "VideoIndex",
                "StreamIndex": "StreamIndex",
                "Codec": "Codec",
                "TimeBase": "TimeBase",
                "CodecTimeBase": "CodecTimeBase",
                "VideoRange": "VideoRange",
                "DisplayTitle": "DisplayTitle",
                "IsInterlaced": "IsInterlaced",
                "BitRate": "BitRate",
                "BitDepth": "BitDepth",
                "RefFrames": "RefFrames",
                "IsDefault": "IsDefault",
                "IsForced": "IsForced",
                "Height": "Height",
                "Width": "Width",
                "AverageFrameRate": "AverageFrameRate",
                "RealFrameRate": "RealFrameRate",
                "Profile": "Profile",
                "Type": "Type",
                "AspectRatio": "AspectRatio",
                "IsExternal": "IsExternal",
                "IsTextSubtitleStream": "IsTextSubtitleStream",
                "SupportsExternalStream": "SupportsExternalStream",
                "Protocol": "Protocol",
                "PixelFormat": "PixelFormat",
                "Level": "Level",
                "IsAnamorphic": "IsAnamorphic"
            },
            "Subtitles": {
                "emby_id": "emby_id",
                "MediaIndex": "MediaIndex",
                "SubtitleIndex": "SubtitleIndex",
                "StreamIndex": "StreamIndex",
                "IsForced": "IsForced",
                "IsInterlaced": "IsInterlaced",
                "DisplayTitle": "DisplayTitle",
                "SupportsExternalStream": "SupportsExternalStream",
                "Language": "Language",
                "DisplayLanguage": "DisplayLanguage",
                "Codec": "Codec",
                "CodecTimeBase": "CodecTimeBase",
                "Protocol": "Protocol",
                "Type": "Type",
                "Path": "Path",
                "TimeBase": "TimeBase",
                "IsTextSubtitleStream": "IsTextSubtitleStream",
                "IsDefault": "IsDefault",
                "IsExternal": "IsExternal"
            }
        }

    def MapMissingData(self, item, mapping_name):
        mapping = self.objects[mapping_name]

        for key, _ in list(mapping.items()):
            if not key in item:
                item[key] = None

        return item

    def map(self, item, mapping_name):
        ''' Syntax to traverse the item dictionary.
            This of the query almost as a url.

            Item is the Emby item json object structure

            ",": each element will be used as a fallback until a value is found.
            "?": split filters and key name from the query part, i.e. MediaSources/0?$Name
            "$": lead the key name with $. Only one key value can be requested per element.
            ":": indicates it's a list of elements [], i.e. MediaSources/0/MediaStreams:?$Name
                 MediaStreams is a list.
            "/": indicates where to go directly
        '''
        self.mapped_item = {}
        mapping = self.objects[mapping_name]

        for key, value in list(mapping.items()):
            self.mapped_item[key] = None
            params = value.split(',')

            for param in params:
                obj = item
                obj_param = param
                obj_key = ""
                obj_filters = {}

                if '?' in obj_param:

                    if '$' in obj_param:
                        obj_param, obj_key = obj_param.rsplit('$', 1)

                    obj_param, filters = obj_param.rsplit('?', 1)

                    if filters:
                        for filterData in filters.split('&'):
                            filter_key, filter_value = filterData.split('=')
                            obj_filters[filter_key] = filter_value

                if ':' in obj_param:
                    result = []

                    for d in self.recursiveloop(obj, obj_param):

                        if obj_filters and self.filters(d, obj_filters):
                            result.append(d)
                        elif not obj_filters:
                            result.append(d)

                    obj = result
                    obj_filters = {}
                elif '/' in obj_param:
                    obj = self.recursive(obj, obj_param)
                elif obj is item and obj is not None:
                    obj = item.get(obj_param)

                if obj_filters and obj:
                    if not self.filters(obj, obj_filters):
                        obj = None

                if obj is None and len(params) != params.index(param):
                    continue

                if obj_key:
                    obj = [d[obj_key] for d in obj if d.get(obj_key)] if isinstance(obj, list) else obj.get(obj_key)

                self.mapped_item[key] = obj
                break

        if not mapping_name.startswith('Browse') and not mapping_name.startswith('Artwork') and not mapping_name.startswith('MediaSources') and not mapping_name.startswith('AudioStreams') and not mapping_name.startswith('VideoStreams'):
            self.mapped_item['ProviderName'] = self.objects.get('%sProviderName' % mapping_name)
            self.mapped_item['Checksum'] = json.dumps(item['UserData'])
            self.mapped_item.setdefault('PresentationKey', None)

        return self.mapped_item

    def recursiveloop(self, obj, keys):
        first, rest = keys.split(':', 1)
        obj = self.recursive(obj, first)

        if obj:
            if rest:
                for item in obj:
                    self.recursiveloop(item, rest)
            else:
                for item in obj:
                    yield item

    def recursive(self, obj, keys):
        for string in keys.split('/'):
            if not obj:
                return None

            obj = obj[int(string)] if string.isdigit() else obj.get(string)

        return obj

    def filters(self, obj, filters):
        result = False

        for key, value in iter(list(filters.items())):
            inverse = False

            if value.startswith('!'):
                inverse = True
                value = value.split('!', 1)[1]
            elif value.lower() == "null":
                value = None

            result = obj.get(key) != value if inverse else obj.get(key) == value

        return result

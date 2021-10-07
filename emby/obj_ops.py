# -*- coding: utf-8 -*-
objects = {
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
        "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
        "LocalTrailer": "LocalTrailerCount",
        "Trailer": "RemoteTrailers/0/Url",
        "DateAdded": "DateCreated",
        "Premiere": "PremiereDate",
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
    "Boxset": {
        "Id": "Id",
        "Title": "Name",
        "Overview": "Overview",
        "PresentationKey": "PresentationUniqueKey",
        "Etag": "Etag",
        "Favorite": "UserData/IsFavorite"
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
        "PresentationKey": "PresentationUniqueKey",
        "Favorite": "UserData/IsFavorite"
    },
    "EpisodeProviderName": "tvdb",
    "Episode": {
        "Id": "Id",
        "Title": "Name",
        "SeasonName": "SeasonName",
        "SeriesName": "SeriesName",
        "Path": "Path",
        "Plot": "Overview",
        "People": "People",
        "Rating": "CommunityRating",
        "Writers": "People:?Type=Writer$Name",
        "Directors": "People:?Type=Director$Name",
        "Runtime": "RunTimeTicks,CumulativeRunTimeTicks",
        "Premiere": "PremiereDate",
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
        "OriginalTitle": "OriginalTitle",
        "Favorite": "UserData/IsFavorite"
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
        "MediaSourcesName": "MediaSources/0/Name",
        "Tags": "Tags",
        "TagItems": "TagItems:?$Name",
        "Played": "UserData/Played",
        "Favorite": "UserData/IsFavorite",
        "Directors": "People:?Type=Director$Name",
        "EmbyParentId": "ParentId",
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
        "PresentationKey": "PresentationUniqueKey",
        "Favorite": "UserData/IsFavorite"
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
        "PresentationKey": "PresentationUniqueKey",
        "Favorite": "UserData/IsFavorite"
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
        "PresentationKey": "PresentationUniqueKey",
        "Favorite": "UserData/IsFavorite"
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
        "AlbumTag": "AlbumPrimaryImageTag",
        "AlbumId": "AlbumId"
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
    }
}

def mapitem(item, mapping_name):
    """ Syntax to traverse the item dictionary.
        This of the query almost as a url.

        Item is the Emby item json object structure

        ",": each element will be used as a fallback until a value is found.
        "?": split filters and key name from the query part, i.e. MediaSources/0?$Name
        "$": lead the key name with $. Only one key value can be requested per element.
        ":": indicates it's a list of elements [], i.e. MediaSources/0/MediaStreams:?$Name
             MediaStreams is a list.
        "/": indicates where to go directly
    """
    mapped_item = {}
    mapping = objects[mapping_name]

    for key, value in list(mapping.items()):
        mapped_item[key] = None
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

                for d in recursiveloop(obj, obj_param):

                    if obj_filters and filtersops(d, obj_filters):
                        result.append(d)
                    elif not obj_filters:
                        result.append(d)

                obj = result
                obj_filters = {}
            elif '/' in obj_param:
                obj = recursive(obj, obj_param)
            elif obj is item and obj is not None:
                obj = item.get(obj_param)

            if obj_filters and obj:
                if not filtersops(obj, obj_filters):
                    obj = None

            if obj is None and len(params) != params.index(param):
                continue

            if obj_key:
                if isinstance(obj, list):
                    obj = [d[obj_key] for d in obj if d.get(obj_key)]
                else:
                    obj = obj.get(obj_key)

            mapped_item[key] = obj
            break

    if not mapping_name.startswith('Browse') and not mapping_name.startswith('Artwork') and not mapping_name.startswith('MediaSources') and not mapping_name.startswith('AudioStreams') and not mapping_name.startswith('VideoStreams'):
        mapped_item['ProviderName'] = objects.get('%sProviderName' % mapping_name)
        mapped_item.setdefault('PresentationKey', None)

    return mapped_item

def recursiveloop(obj, keys):
    first, rest = keys.split(':', 1)
    obj = recursive(obj, first)

    if obj:
        if rest:
            for item in obj:
                recursiveloop(item, rest)
        else:
            for item in obj:
                yield item

def recursive(obj, keys):
    for string in keys.split('/'):
        if not obj:
            return None

        obj = obj[int(string)] if string.isdigit() else obj.get(string)

    return obj

def filtersops(obj, filterdata):
    result = False

    for key, value in iter(list(filterdata.items())):
        inverse = False

        if value.startswith('!'):
            inverse = True
            value = value.split('!', 1)[1]
        elif value.lower() == "null":
            value = None

        result = obj.get(key) != value if inverse else obj.get(key) == value

    return result

import xbmc
import xbmcgui
from helper import utils
from core import common

def get_shortdate(EmbyDate):
    try:
        DateTime = EmbyDate.split(" ")
        DateTemp = DateTime[0].split("-")
        return f"{DateTemp[2]}-{DateTemp[1]}-{DateTemp[0]}"
    except Exception as Error:
        xbmc.log(f"EMBY.emby.listitem: No valid date: {EmbyDate} / {Error}", 0) # LOGDEBUG
        return ""

def set_ListItem_from_Kodi_database(KodiItem, Path=None):
    if Path:
        ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=Path)
    else:
        if 'pathandfilename' in KodiItem:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=KodiItem['pathandfilename'])
        elif 'path' in KodiItem:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=KodiItem['path'])
        else:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True)

    ListItem.setContentLookup(False)

    if KodiItem['mediatype'] in ("episode", "movie", "musicvideo", "tvshow", "season", "set"):
        if KodiItem.get('ProductionLocation'):
            KodiItem['ProductionLocations'] = KodiItem['ProductionLocation'].split("/")

        if KodiItem.get('StudioName'):
            KodiItem['StudioNames'] = KodiItem['StudioName'].split("/")

        if KodiItem.get('Writer'):
            KodiItem['Writers'] = KodiItem['Writer'].split("/")

        if KodiItem.get('Director'):
            KodiItem['Directors'] = KodiItem['Director'].split("/")

        InfoTags = ListItem.getVideoInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']))
        set_DateAdded(KodiItem, InfoTags)
        set_setRating(KodiItem, InfoTags)
        set_UserRating(KodiItem, InfoTags)
        set_TagLine(KodiItem, InfoTags)
        set_PlotOutline(KodiItem, InfoTags)
        set_Countries(KodiItem, InfoTags)
        set_Mpaa(KodiItem, InfoTags)
        set_OriginalTitle(KodiItem, InfoTags)
        set_Plot(KodiItem, InfoTags)
        set_SortTitle(KodiItem, InfoTags)
        set_Studios(KodiItem, InfoTags)
        set_Writers(KodiItem, InfoTags)
        set_Directors(KodiItem, InfoTags)
        set_SortSeason(KodiItem, InfoTags)
        set_Season(KodiItem, InfoTags)
        set_Episode(KodiItem, InfoTags)
        set_SortEpisode(KodiItem, InfoTags)
        set_TvShowTitle(KodiItem, InfoTags)
        set_IMDBNumber(KodiItem, InfoTags)
        set_Premiered(KodiItem, InfoTags)
        set_ResumePoint(KodiItem, InfoTags)
        set_Album(KodiItem, InfoTags)
        set_TvShowStatus(KodiItem, InfoTags)

        if KodiItem.get('trailer'):
            InfoTags.setTrailer(KodiItem['trailer'])

#        if KodiItem.get('path'):
#            InfoTags.setPath(KodiItem['path'])

#        if KodiItem.get('pathandfilename'):
#            InfoTags.setFilenameAndPath(KodiItem['pathandfilename'])

        if KodiItem.get('track'):
            InfoTags.setTrackNumber(int(KodiItem['track']))

        if KodiItem.get('firstaired'):
            InfoTags.setFirstAired(KodiItem['firstaired'])

        if KodiItem.get('people'):
            People = ()

            for Person in KodiItem['people']:
                People += (xbmc.Actor(*Person),)

            InfoTags.setCast(People)
    elif KodiItem['mediatype'] in ("song", "artist", "album"):
        InfoTags = ListItem.getMusicInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']), KodiItem['mediatype'])

        if KodiItem.get('artist'):
            InfoTags.setArtist(KodiItem['artist'])

        if KodiItem.get('albumartists'):
            InfoTags.setAlbumArtist(KodiItem['albumartists'])

        if KodiItem.get('comment'):
            InfoTags.setComment(KodiItem['comment'])

        if KodiItem.get('disc'):
            InfoTags.setDisc(KodiItem['disc'])

        if KodiItem.get('track'):
            InfoTags.setTrack(KodiItem['track'])

        set_Album(KodiItem, InfoTags)

        if KodiItem.get('releasedate'):
            InfoTags.setReleaseDate(KodiItem['releasedate'])

        if KodiItem.get('musicbrainzartistid'):
            InfoTags.setMusicBrainzArtistID(KodiItem['musicbrainzartistid'].split("/"))

        if KodiItem.get('musicbrainzalbumid'):
            InfoTags.setMusicBrainzAlbumID(KodiItem['musicbrainzalbumid'])

        if KodiItem.get('musicbrainztrackid'):
            InfoTags.setMusicBrainzTrackID(KodiItem['musicbrainztrackid'])

#        set_MusicBrainzAlbumArtistID(item, InfoTags)

    # Common infotags
    InfoTags.setMediaType(KodiItem['mediatype'])
    InfoTags.setTitle(KodiItem['title'])

    if KodiItem.get('duration'):
        InfoTags.setDuration(int(float(KodiItem['duration'])))

    if KodiItem['artwork']:
        ListItem.setArt(KodiItem['artwork'])

    if KodiItem.get('genre'):
        InfoTags.setGenres(KodiItem['genre'].split("/"))

    if KodiItem.get('playCount'):
        InfoTags.setPlaycount(KodiItem['playCount'])

    if KodiItem.get('lastplayed'):
        InfoTags.setLastPlayed(KodiItem['lastplayed'])

    if KodiItem.get('year'):
        InfoTags.setYear(int(KodiItem['year']))

    ListItem.setProperties(KodiItem['properties'])
    IsFolder = bool(KodiItem['properties']['IsFolder'] == "true")
    return IsFolder, ListItem

def set_ListItem(item, ServerId, Path=None, KodiId=None):
    if Path:
        listitem = xbmcgui.ListItem(label=item['Name'], offscreen=True, path=Path)
    else:
        listitem = xbmcgui.ListItem(label=item['Name'], offscreen=True)

    listitem.setContentLookup(False)
    Properties = {}
    InfoTags = None
    HasStreams = False
    IsVideo = False

    if item['Type'] == 'Folder' or item.get('NodesMenu', False):
        common.set_KodiArtwork(item, ServerId, True)
        common.set_overview(item)
        Properties = {'IsFolder': 'true', 'IsPlayable': 'false'}
    elif item['Type'] == "TvChannel":
        common.load_tvchannel(item, ServerId)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("video")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        InfoTags.setPlot(item['CurrentProgram']['Overview'])
        set_DateAdded(item, InfoTags)
        set_Countries(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_Genres(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_ResumePoint(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        Properties = {'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] in ("Movie", "Trailer"):
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("movie")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        set_ResumePoint(item, InfoTags)

        if item['Type'] == "Movie":
            common.set_trailer(item, utils.EmbyServers[ServerId])
            InfoTags.setTrailer(item['Trailer'])

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "movie"}
    elif item['Type'] == "Series":
        item['SeriesName'] = item['Name']
        common.set_RunTimeTicks(item)
        common.set_trailer(item, utils.EmbyServers[ServerId])
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("tvshow")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        InfoTags.setTrailer(item['Trailer'])
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_TvShowStatus(item, InfoTags)
        set_TvShowTitle(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'TotalEpisodes': item.get('RecursiveItemCount', 0), 'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']), 'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'], 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Season":
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("season")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        InfoTags.setSeason(item.get('IndexNumber', 0))
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'NumEpisodes': item.get('RecursiveItemCount', 0), 'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']), 'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'], 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Episode":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("episode")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_SortSeason(item, InfoTags)
        set_Season(item, InfoTags)
        set_Episode(item, InfoTags)
        set_SortEpisode(item, InfoTags)
        set_TvShowTitle(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        set_ResumePoint(item, InfoTags)
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "episode"}

        # Virtual content e.g. Upcoming
        if 'Id' not in item:
            Properties['IsPlayable'] = 'false'
            item['NoLink'] = True
        else:
            Properties['embyid'] = str(item['Id'])
    elif item['Type'] == "MusicVideo":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_MusicVideoTracks(item)
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("musicvideo")

        if item['IndexNumber']:
            InfoTags.setTrackNumber(int(item['IndexNumber']))

        InfoTags.setTitle(item['Name'])
        set_Album(item, InfoTags)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        set_ResumePoint(item, InfoTags)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "musicvideo"}
    elif item['Type'] == "Video":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("video")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        set_ResumePoint(item, InfoTags)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "movie"}
    elif item['Type'] == "MusicArtist":
        item['KodiLastScraped'] = utils.currenttime_kodi_format()
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("artist")
        InfoTags.setTitle(item['Name'])
        InfoTags.setArtist(item['Name'])
        set_Genres(item, InfoTags)
        InfoTags.setDbId(1000000000 + int(item['Id']), "artist")
        set_MusicBrainzArtistID(item, InfoTags)
        set_Comment(item, InfoTags)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "MusicAlbum":
        common.set_common(item, ServerId, True)
        common.set_KodiArtwork(item, ServerId, True)
        item['KodiLastScraped'] = utils.currenttime_kodi_format()
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("album")
        InfoTags.setTitle(item['Name'])
        InfoTags.setAlbum(item['Name'])
        set_Album(item, InfoTags)
        set_AlbumArtist(item, InfoTags)
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Genres(item, InfoTags)
        InfoTags.setDbId(1000000000 + int(item['Id']), "album")
        set_MusicBrainzAlbumID(item, InfoTags)
        set_MusicBrainzAlbumArtistID(item, InfoTags)
        set_Comment(item, InfoTags)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Audio":
        common.set_common(item, ServerId, True)
        common.set_KodiArtwork(item, ServerId, True)
        item['IndexNumber'] = item.get('IndexNumber', None)
        common.set_playstate(item)
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setArtist(" / ".join(item['Artists']))
        set_Album(item, InfoTags)
        set_AlbumArtist(item, InfoTags)
        InfoTags.setMediaType("song")
        InfoTags.setTitle(item['Name'])
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        InfoTags.setDbId(1000000000 + int(item['Id']), "song")
        set_MusicBrainzArtistID(item, InfoTags)
        set_MusicBrainzAlbumID(item, InfoTags)
        set_MusicBrainzAlbumArtistID(item, InfoTags)
        set_MusicBrainzTrackID(item, InfoTags)
        set_Comment(item, InfoTags)
        set_Disc(item, InfoTags)
        set_Track(item, InfoTags)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true',  "KodiType": "song"}
    elif item['Type'] == "BoxSet":
        common.set_RunTimeTicks(item)
        common.set_common(item, ServerId, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("set")
        InfoTags.setTitle(item['Name'])
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_setRating(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Playcount(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)

        if KodiId:
            InfoTags.setDbId(int(KodiId))
        elif 'Id' in item:
            InfoTags.setDbId(1000000000 + int(item['Id']))

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == 'Playlist':
        InfoTags = listitem.getVideoInfoTag()
        InfoTags.setTitle(item['Name'])
        common.set_KodiArtwork(item, ServerId, True)
        common.set_overview(item)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'false'}
    elif item['Type'] == "Photo":
        common.set_KodiArtwork(item, ServerId, True)
        item['Width'] = int(item.get('Width', 0))
        item['Height'] = int(item.get('Height', 0))
        common.set_Dates(item)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['KodiPremiereDate']))

        if item['Height'] > 0:
            PictureInfoTags.setResolution(int(item['Width']), int(item['Height']))

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "PhotoAlbum":
        common.set_KodiArtwork(item, ServerId, True)
        common.set_Dates(item)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['KodiPremiereDate']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    else: # Letter, Tag, Genre, MusicGenre,  etc
        InfoTags = listitem.getVideoInfoTag()
        InfoTags.setTitle(item['Name'])
        common.set_KodiArtwork(item, ServerId, True)

    if HasStreams:
        if 'Streams' in item and item['Streams']:
            for Stream in item['Streams'][0]['Video']:
                set_ListItem_StreamInfo('video', InfoTags, item['KodiRunTimeTicks'], Stream)

            for Stream in item['Streams'][0]['Audio']:
                set_ListItem_StreamInfo('audio', InfoTags, 0, Stream)

            for Stream in item['Streams'][0]['Subtitle']:
                set_ListItem_StreamInfo('subtitle', InfoTags, 0, Stream)

    cast = ()

    if IsVideo and 'ArtistItems' in item and item['ArtistItems']:
        cast = ()

        for person in item['ArtistItems']:
            cast += ((xbmc.Actor(person['Name'], "Artist", len(cast) + 1, person['imageurl'])),)

    if IsVideo and 'People' in item and item['People']:
        cast = ()

        for person in item['People']:
            if person['Type'] in ("Actor", 'Director', 'GuestStar'):
                if str(person['imageurl']).startswith("http"):
                    ImageUrl = person['imageurl']
                else:
                    ImageUrl = ""

                cast += ((xbmc.Actor(person['Name'], person.get('Role', "Unknown"), len(cast) + 1, ImageUrl)),)

    if cast:
        InfoTags.setCast(cast)

    if item['KodiArtwork']:
        ArtworkData = {}

        for KodiArtworkId, ArtworkValue in list(item['KodiArtwork'].items()):
            if KodiArtworkId == 'fanart':
                for KodiArtworkIdFanart, ArtworkValueFanart in list(ArtworkValue.items()):
                    ArtworkData[KodiArtworkIdFanart] = ArtworkValueFanart
            else:
                ArtworkData[KodiArtworkId] = ArtworkValue

        listitem.setArt(ArtworkData)

    if Properties:
        listitem.setProperties(Properties)

    return listitem

def set_TvShowStatus(Item, InfoTags):
    if 'Status' in Item and Item['Status']:
        InfoTags.setTvShowStatus(Item['Status'])

def set_UserRating(Item, InfoTags):
    if 'CriticRating' in Item and Item['CriticRating']:
        InfoTags.setUserRating(Item['CriticRating'])

def set_setRating(Item, InfoTags):
    if 'CommunityRating' in Item and Item['CommunityRating']:
        InfoTags.setRating(Item['CommunityRating'])

def set_PlotOutline(Item, InfoTags):
    if 'ShortOverview' in Item and Item['ShortOverview']:
        InfoTags.setPlotOutline(Item['ShortOverview'])

def set_OriginalTitle(Item, InfoTags):
    if 'OriginalTitle' in Item and Item['OriginalTitle']:
        InfoTags.setOriginalTitle(Item['OriginalTitle'])

def set_SortSeason(Item, InfoTags):
    if 'SortParentIndexNumber' in Item and Item['SortParentIndexNumber']:
        InfoTags.setSortSeason(int(Item['SortParentIndexNumber']))

def set_Season(Item, InfoTags):
    if 'ParentIndexNumber' in Item and Item['ParentIndexNumber']:
        InfoTags.setSeason(int(Item['ParentIndexNumber']))

def set_Episode(Item, InfoTags):
    if 'IndexNumber' in Item and Item['IndexNumber']:
        InfoTags.setEpisode(int(Item['IndexNumber']))

def set_SortEpisode(Item, InfoTags):
    if 'SortIndexNumber' in Item and Item['SortIndexNumber']:
        InfoTags.setSortEpisode(int(Item['SortIndexNumber']))

def set_Genres(Item, InfoTags):
    if 'GenreNames' in Item and Item['GenreNames']:
        InfoTags.setGenres(Item['GenreNames'])

def set_Disc(Item, InfoTags):
    if 'ParentIndexNumber' in Item and Item['ParentIndexNumber']:
        InfoTags.setDisc(Item['ParentIndexNumber'])

def set_Year(Item, InfoTags):
    if 'KodiProductionYear' in Item and Item['KodiProductionYear']:
        InfoTags.setYear(int(Item['KodiProductionYear']))

def set_MusicBrainzArtistID(Item, InfoTags):
    if Item['ProviderIds']['MusicBrainzArtist']:
        InfoTags.setMusicBrainzArtistID(tuple(Item['ProviderIds']['MusicBrainzArtist']))

def set_MusicBrainzTrackID(Item, InfoTags):
    if Item['ProviderIds']['MusicBrainzTrack']:
        InfoTags.setMusicBrainzTrackID(Item['ProviderIds']['MusicBrainzTrack'])

def set_MusicBrainzAlbumID(Item, InfoTags):
    if Item['ProviderIds']['MusicBrainzAlbum']:
        InfoTags.setMusicBrainzAlbumID(Item['ProviderIds']['MusicBrainzAlbum'])

def set_MusicBrainzAlbumArtistID(Item, InfoTags):
    if Item['ProviderIds']['MusicBrainzAlbumArtist']:
        InfoTags.setMusicBrainzAlbumArtistID(tuple(Item['ProviderIds']['MusicBrainzAlbumArtist']))

def set_Countries(Item, InfoTags):
    if 'ProductionLocations' in Item and Item['ProductionLocations']:
        InfoTags.setCountries(Item['ProductionLocations'])

def set_Plot(Item, InfoTags):
    if 'Overview' in Item and Item['Overview']:
        InfoTags.setPlot(Item['Overview'])

def set_TagLine(Item, InfoTags):
    if 'Tagline' in Item and Item['Tagline']:
        InfoTags.setTagLine(Item['Tagline'])

def set_Studios(Item, InfoTags):
    if 'StudioNames' in Item and Item['StudioNames']:
        InfoTags.setStudios(Item['StudioNames'])

def set_Premiered(Item, InfoTags):
    if 'KodiPremiereDate' in Item and Item['KodiPremiereDate']:
        InfoTags.setPremiered(Item['KodiPremiereDate'])

def set_DateAdded(Item, InfoTags):
    if 'KodiDateCreated' in Item and Item['KodiDateCreated']:
        InfoTags.setDateAdded(Item['KodiDateCreated'])

def set_AlbumArtist(Item, InfoTags):
    if 'AlbumArtist' in Item and Item['AlbumArtist']:
        InfoTags.setAlbumArtist(Item['AlbumArtist'])

def set_Track(Item, InfoTags):
    if 'IndexNumber' in Item and Item['IndexNumber']:
        InfoTags.setTrack(Item['IndexNumber'])

def set_Album(Item, InfoTags):
    if 'Album' in Item and Item['Album']:
        InfoTags.setAlbum(Item['Album'])

def set_SortTitle(Item, InfoTags):
    if 'SortName' in Item and Item['SortName']:
        InfoTags.setSortTitle(Item['SortName'])

def set_Comment(Item, InfoTags):
    if 'Overview' in Item and Item['Overview']:
        InfoTags.setComment(Item['Overview'])

def set_Duration(Item, InfoTags):
    if 'KodiRunTimeTicks' in Item and Item['KodiRunTimeTicks']:
        InfoTags.setDuration(int(float(Item['KodiRunTimeTicks'])))

def set_Playcount(Item, InfoTags):
    if 'UserData' in Item and Item['UserData']['PlayCount']:
        InfoTags.setPlaycount(int(Item['UserData']['PlayCount']))

def set_LastPlayed(Item, InfoTags):
    if Item['KodiLastPlayedDate']:
        InfoTags.setLastPlayed(Item['KodiLastPlayedDate'])

def set_IMDBNumber(Item, InfoTags):
    if 'Unique' in Item and Item['Unique']:
        InfoTags.setIMDBNumber(Item['Unique'])

def set_Mpaa(Item, InfoTags):
    if 'OfficialRating' in Item and Item['OfficialRating']:
        InfoTags.setMpaa(Item['OfficialRating'])

def set_TvShowTitle(Item, InfoTags):
    if 'SeriesName' in Item and Item['SeriesName']:
        InfoTags.setTvShowTitle(Item['SeriesName'])

def set_ResumePoint(Item, InfoTags):
    if 'KodiRunTimeTicks' in Item and Item['KodiRunTimeTicks'] and Item['KodiPlaybackPositionTicks']:
        InfoTags.setResumePoint(int(float(Item['KodiPlaybackPositionTicks'])), int(float(Item['KodiRunTimeTicks'])))

def set_Artists(Item, InfoTags):
    if 'Artists' in Item and Item['Artists']:
        InfoTags.setArtists(Item['Artists'])

def set_Writers(Item, InfoTags):
    if 'Writers' in Item and Item['Writers']:
        InfoTags.setWriters(Item['Writers'])

def set_Directors(Item, InfoTags):
    if 'Directors' in Item and Item['Directors']:
        InfoTags.setDirectors(Item['Directors'])

def set_ListItem_StreamInfo(Content, InfoTags, Duration, StreamInfo):
    if Content == "video":
        if StreamInfo['width'] and StreamInfo['height']:
            if StreamInfo['language']:
                Language = StreamInfo['language']
            else:
                Language = ""

            if StreamInfo['codec']:
                Codec = StreamInfo['codec']
            else:
                Codec = ""

            if Duration:
                Duration = int(Duration)
            else:
                Duration = 0

            InfoTags.addVideoStream(xbmc.VideoStreamDetail(int(StreamInfo['width']), int(StreamInfo['height']), float(StreamInfo['aspect']), Duration, Codec, "", Language))
    elif Content == "audio":
        if StreamInfo['channels'] and StreamInfo['codec']:
            InfoTags.addAudioStream(xbmc.AudioStreamDetail(StreamInfo['channels'], StreamInfo['codec'], ""))
    elif Content == "subtitle":
        if StreamInfo['language']:
            InfoTags.addSubtitleStream(xbmc.SubtitleStreamDetail(StreamInfo['language']))

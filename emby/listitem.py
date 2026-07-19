import xbmc
import xbmcgui
from helper import utils
from core import common

def get_shortdate(EmbyDate):
    if not EmbyDate:
        return ""

    try:
        DateTime = EmbyDate.split(" ")
        DateTemp = DateTime[0].split("-")
        return f"{DateTemp[2]}-{DateTemp[1]}-{DateTemp[0]}"
    except Exception as Error:
        if utils.DebugLog: xbmc.log(f"EMBY.emby.listitem (DEBUG): No valid date: {EmbyDate} / {Error}", 1) # LOGDEBUG
        return ""

def set_ListItem_from_Kodi_database(KodiItem, Path=None, ContentLookup=True):
    if Path:
        ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=Path)
        MimeType = get_MimeType(Path)
    else:
        if 'pathandfilename' in KodiItem:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=KodiItem['pathandfilename'])
            MimeType = get_MimeType(KodiItem['pathandfilename'])
        elif 'path' in KodiItem:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True, path=KodiItem['path'])
            MimeType = get_MimeType(KodiItem['path'])
        else:
            ListItem = xbmcgui.ListItem(label=KodiItem['title'], offscreen=True)
            MimeType = ""

    if MimeType:
        ListItem.setMimeType(MimeType)
        KodiItem['properties'].update({'mimetype': MimeType})

        if not ContentLookup: # disable mime requests, as they stall webservice: hls mimetype must be set in webservice.py -> sendHeadVideoHLS -> Don't use it, it breaks transocding, for direct Embyserver re uests or not transcoding, it's save to use it
            ListItem.setContentLookup(False)

    if KodiItem['mediatype'] in ("episode", "movie", "musicvideo", "tvshow", "season", "set", "actor", "video"):
        if KodiItem.get('ProductionLocation'):
            KodiItem['ProductionLocations'] = KodiItem['ProductionLocation'].split("/")

        if KodiItem.get('StudioName'):
            KodiItem['StudioNames'] = KodiItem['StudioName'].split("/")

        if KodiItem.get('Writer'):
            KodiItem['Writers'] = KodiItem['Writer'].split("/")

        if KodiItem.get('Director'):
            KodiItem['Directors'] = KodiItem['Director'].split("/")

        InfoTags = ListItem.getVideoInfoTag()

        if 'dbid' in KodiItem:
            InfoTags.setDbId(int(KodiItem['dbid']))

        set_DateAdded(KodiItem, InfoTags)
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
        set_Season(KodiItem, InfoTags, 'ParentIndexNumber')
        set_Episode(KodiItem, InfoTags)
        set_SortEpisode(KodiItem, InfoTags)
        set_TvShowTitle(KodiItem, InfoTags)
        set_IMDBNumber(KodiItem, InfoTags)
        set_Premiered(KodiItem, InfoTags)
        set_ResumePoint(KodiItem, InfoTags)
        set_Album(KodiItem, InfoTags)
        set_TvShowStatus(KodiItem, InfoTags)
        set_Artists(KodiItem, InfoTags)
        set_Trailer(KodiItem, InfoTags)
        set_RatingVideo(KodiItem, InfoTags)

        if KodiItem.get('path'):
            InfoTags.setPath(KodiItem['path'])

        if KodiItem.get('pathandfilename'):
            InfoTags.setFilenameAndPath(KodiItem['pathandfilename'])

        if KodiItem.get('track'):
            InfoTags.setTrackNumber(int(KodiItem['track']))

        if KodiItem.get('firstaired'):
            InfoTags.setFirstAired(KodiItem['firstaired'])

        if KodiItem.get('People'):
            People = ()

            for Person in KodiItem['People']:
                People += (xbmc.Actor(*Person),)

            InfoTags.setCast(People)

        if KodiItem.get('playcount'):
            InfoTags.setPlaycount(KodiItem['playcount'])
    elif KodiItem['mediatype'] in ("song", "artist", "album"):
        InfoTags = ListItem.getMusicInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']), KodiItem['mediatype'])
        set_RatingMusic(KodiItem, InfoTags)

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

        if KodiItem.get('playcount'):
            InfoTags.setPlayCount(KodiItem['playcount'])

        if KodiItem.get('path'):
            InfoTags.setURL(KodiItem['path'])

        if KodiItem.get('pathandfilename'):
            InfoTags.setURL(KodiItem['pathandfilename'])

#        set_MusicBrainzAlbumArtistID(item, InfoTags)

    # Common infotags
    if InfoTags:
        InfoTags.setTitle(KodiItem['title'])
        InfoTags.setMediaType(KodiItem['mediatype'])

        if KodiItem.get('duration'):
            InfoTags.setDuration(int(float(KodiItem['duration'])))

        if KodiItem['artwork']:
            ListItem.setArt(KodiItem['artwork'])

        if KodiItem.get('genre'):
            InfoTags.setGenres(KodiItem['genre'].split("/"))

        if KodiItem.get('lastplayed'):
            InfoTags.setLastPlayed(KodiItem['lastplayed'])

        if KodiItem.get('year'):
            InfoTags.setYear(int(KodiItem['year']))

    ListItem.setProperties(KodiItem['properties'])
    IsFolder = bool(KodiItem['properties']['IsFolder'] == "true")
    return IsFolder, ListItem

def set_ListItem(item, ServerId, Path=None, ContentLookup=True, ContentSupported=""):
    if 'Name' in item:
        Name = item['Name']
    elif 'SeriesName' in item: # {'ServerId': '2a38697ffc1b428b943aa1b6014e2263', 'PremiereDate': '2024-10-23T22:00:00.0000000Z', 'ProductionYear': 2024, 'IndexNumber': 2, 'ParentIndexNumber': 5, 'ProviderIds': {}, 'Type': 'Episode', 'SeriesName': 'Star Trek: Lower Decks', 'SeriesId': '58574', 'SeriesPrimaryImageTag': 'fb201a2139810a15d125dfea5e981f36', 'ParentThumbItemId': '58574', 'ParentThumbImageTag': '01e69ca501869a469606bc82bd94d300', 'LocationType': 'Virtual'}
        Name = item['SeriesName']
    else:
        Name = "Unknown"

    if Path:
        listitem = xbmcgui.ListItem(label=Name, offscreen=True, path=Path)
    else:
        listitem = xbmcgui.ListItem(label=Name, offscreen=True)

    MimeType = get_MimeType(item.get('Path', ""))

    if MimeType:
        listitem.setMimeType(MimeType)
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item.get('Id', "")), 'mimetype': MimeType}

        if not ContentLookup: # disable mime requests, as they stall webservice: hls mimetype must be set in webservice.py -> sendHeadVideoHLS -> Don't use it, it breaks transocding, for direct Embyserver re uests or not transcoding, it's save to use it
            listitem.setContentLookup(False)
    else:
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item.get('Id', ""))}

    InfoTags = None
    IsVideo = False

    if item['Type'] == 'Folder' or item.get('NodesMenu', False):
        common.set_KodiArtwork(item, ServerId, True)
        common.set_overview(item)
        common.set_path_filename(item, ServerId, None, True)
        Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == "TvChannel":
        common.load_tvchannel(item, ServerId)
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("video")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        InfoTags.setPlot(item['CurrentProgram']['Overview'])
        set_DateAdded(item, InfoTags)
        set_Countries(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_Genres(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_ResumePoint(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_Path(item, InfoTags)
        set_FilenameAndPath(item, InfoTags)
        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true'})
    elif item['Type'] in ("Movie", "Trailer"):
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("movie")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
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
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_ResumePoint(item, InfoTags)
        set_Path(item, InfoTags)
        set_FilenameAndPath(item, InfoTags)

#        if item['Type'] == "Movie" and utils.getLocalTrailers:
#            common.set_trailer(item, utils.EmbyServers[ServerId])
#            set_Trailer(item, InfoTags)

        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "movie"})
    elif item['Type'] == "Series":
        item['SeriesName'] = Name
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("tvshow")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_TvShowStatus(item, InfoTags)
        set_TvShowTitle(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_Path(item, InfoTags)

#        if utils.getLocalTrailers:
#            common.set_trailer(item, utils.EmbyServers[ServerId])
#            set_Trailer(item, InfoTags)

        if utils.getTotalEpisodes:
            TotalEpisodes = get_TotalEpisodesSeries(item['Id'], ServerId) # load total episodes: "RecursiveItemCount" doesn't match UnplayedItemCount when specials available

            if 'KodiPlayCount' in item and item['KodiPlayCount']:
                inprogressepisodes = 0
            else:
                inprogressepisodes = TotalEpisodes - int(item['UserData']['UnplayedItemCount'])

            Properties.update({'TotalEpisodes': TotalEpisodes, 'InProgressEpisodes': inprogressepisodes, 'IsFolder': 'true', 'IsPlayable': 'false', 'WatchedEpisodes': TotalEpisodes - int(item['UserData']['UnplayedItemCount'])})
        else:
            Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == "Season":
        common.set_playstate(item)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("season")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_Season(item, InfoTags, 'IndexNumber')
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_Path(item, InfoTags)
        isSpecial = "IndexNumber" in item and not item["IndexNumber"]

        if utils.getTotalEpisodes:
            TotalEpisodes = get_TotalEpisodesSeason(item['Id'], ServerId, isSpecial) # load total episodes: "RecursiveItemCount" doesn't match UnplayedItemCount when specials available

            if 'KodiPlayCount' in item and item['KodiPlayCount']:
                inprogressepisodes = 0
            else:
                inprogressepisodes = TotalEpisodes - int(item['UserData']['UnplayedItemCount'])

            Properties.update({'TotalEpisodes': TotalEpisodes, 'InProgressEpisodes': inprogressepisodes, 'IsFolder': 'true', 'IsPlayable': 'false', 'WatchedEpisodes': TotalEpisodes - int(item['UserData']['UnplayedItemCount'])})
        else:
            Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == "Episode":
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("episode")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Mpaa(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_SortSeason(item, InfoTags)
        set_Season(item, InfoTags, 'ParentIndexNumber')
        set_Episode(item, InfoTags)
        set_SortEpisode(item, InfoTags)
        set_TvShowTitle(item, InfoTags)
        set_IMDBNumber(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_ResumePoint(item, InfoTags)
        set_Path(item, InfoTags)
        set_FilenameAndPath(item, InfoTags)
        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "episode"})

        # Virtual content e.g. Upcoming
        if 'Id' not in item:
            Properties['IsPlayable'] = 'false'
            item['NoLink'] = True
    elif item['Type'] == "MusicVideo":
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        common.set_common(item, ServerId, True, False)
        common.set_MusicVideoTracks(item)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("musicvideo")

        if item['IndexNumber']:
            InfoTags.setTrackNumber(int(item['IndexNumber']))

        InfoTags.setTitle(Name)
        set_Album(item, InfoTags)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_ResumePoint(item, InfoTags)
        set_Path(item, InfoTags)
        set_FilenameAndPath(item, InfoTags)
        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "musicvideo"})
    elif item['Type'] == "Video":
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("video")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_ResumePoint(item, InfoTags)
        set_Path(item, InfoTags)
        set_FilenameAndPath(item, InfoTags)
        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true', "KodiType": "movie"})
    elif item['Type'] == "MusicArtist":
        item['KodiLastScraped'] = utils.currenttime_kodi_format()
        common.set_common(item, ServerId, True, False)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("artist")
        InfoTags.setTitle(Name)
        InfoTags.setArtist(Name)
        set_Genres(item, InfoTags)
        set_EmbyIdAsKodiIdAudio(item, InfoTags, ServerId, "artist")
        set_MusicBrainzArtistID(item, InfoTags)
        set_Comment(item, InfoTags)
        Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == "MusicAlbum":
        common.set_RunTimeTicks(item)
        common.set_common(item, ServerId, True, False)
        item['KodiLastScraped'] = utils.currenttime_kodi_format()
        common.set_RunTimeTicks(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("album")
        InfoTags.setTitle(Name)
        InfoTags.setAlbum(Name)
        set_Album(item, InfoTags)
        set_AlbumArtist(item, InfoTags)
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_Genres(item, InfoTags)
        set_EmbyIdAsKodiIdAudio(item, InfoTags, ServerId, "album")
        set_MusicBrainzAlbumID(item, InfoTags)
        set_MusicBrainzAlbumArtistID(item, InfoTags)
        set_Comment(item, InfoTags)
        Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == "Audio":
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        item['IndexNumber'] = item.get('IndexNumber', None)
        common.set_RunTimeTicks(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setArtist(" / ".join(item['Artists']))
        set_Album(item, InfoTags)
        set_AlbumArtist(item, InfoTags)
        set_RatingMusic(item, InfoTags)
        InfoTags.setMediaType("song")
        InfoTags.setTitle(Name)
        set_Year(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountAudio(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_EmbyIdAsKodiIdAudio(item, InfoTags, ServerId, "song")
        set_MusicBrainzArtistID(item, InfoTags)
        set_MusicBrainzAlbumID(item, InfoTags)
        set_MusicBrainzAlbumArtistID(item, InfoTags)
        set_MusicBrainzTrackID(item, InfoTags)
        set_Comment(item, InfoTags)
        set_Disc(item, InfoTags)
        set_Track(item, InfoTags)

        if Path:
            InfoTags.setURL(Path)
        elif 'KodiFullPath' in item and item['KodiFullPath']:
            InfoTags.setURL(item['KodiFullPath'])

        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true',  "KodiType": "song"})
    elif item['Type'] == "BoxSet":
        common.set_RunTimeTicks(item)
        common.set_playstate(item)
        common.set_common(item, ServerId, True, False)
        common.set_path_filename(item, ServerId, None, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("set")
        InfoTags.setTitle(Name)
        set_SortTitle(item, InfoTags)
        set_OriginalTitle(item, InfoTags)
        set_Plot(item, InfoTags)
        set_PlotOutline(item, InfoTags)
        set_DateAdded(item, InfoTags)
        set_Year(item, InfoTags)
        set_RatingVideo(item, InfoTags)
        set_Duration(item, InfoTags)
        set_PlaycountVideo(item, InfoTags)
        set_LastPlayed(item, InfoTags)
        set_Genres(item, InfoTags)
        set_Countries(item, InfoTags)
        set_TagLine(item, InfoTags)
        set_Studios(item, InfoTags)
        set_Writers(item, InfoTags)
        set_Directors(item, InfoTags)
        set_UserRating(item, InfoTags)
        set_Premiered(item, InfoTags)
        set_EmbyIdAsKodiIdVideo(item, InfoTags, ServerId)
        set_Path(item, InfoTags)
        Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    elif item['Type'] == 'Playlist':
        common.set_path_filename(item, ServerId, None, True)

        if ContentSupported == "audio":
            InfoTags = listitem.getMusicInfoTag()
            Properties.update({'IsFolder': 'true', 'IsPlayable': 'true'})
        else:
            InfoTags = listitem.getVideoInfoTag()
            set_Path(item, InfoTags)
            Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})

        InfoTags.setTitle(Name)
        common.set_KodiArtwork(item, ServerId, True)
        common.set_overview(item)
    elif item['Type'] == "Photo":
        common.set_KodiArtwork(item, ServerId, True)
        item['Width'] = int(item.get('Width', 0))
        item['Height'] = int(item.get('Height', 0))
        common.set_Dates(item)
        common.set_path_filename(item, ServerId, None, True)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['KodiPremiereDate']))

        if item['Height'] > 0:
            PictureInfoTags.setResolution(int(item['Width']), int(item['Height']))

        Properties.update({'IsFolder': 'false', 'IsPlayable': 'true'})
    elif item['Type'] == "PhotoAlbum":
        common.set_KodiArtwork(item, ServerId, True)
        common.set_Dates(item)
        common.set_path_filename(item, ServerId, None, True)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['KodiPremiereDate']))
        Properties.update({'IsFolder': 'true', 'IsPlayable': 'false'})
    else: # Letter, Tag, Genre, MusicGenre,  etc
        InfoTags = listitem.getVideoInfoTag()
        InfoTags.setTitle(Name)
        common.set_KodiArtwork(item, ServerId, True)
        common.set_path_filename(item, ServerId, None, True)

    if 'MediaSources' in item:
        common.set_streams(item)
        common.set_chapters(item, ServerId)
        Properties['mediasourcescount'] = len(item['MediaSources'])

        for Index, MediaSource in enumerate(item['MediaSources']):
            Properties.update({f"embyintrostartposticks{Index}": MediaSource['IntroStartPositionTicks'], f"embyintroendpositionticks{Index}": MediaSource['IntroEndPositionTicks'], f"embycreditspositionticks{Index}": MediaSource['CreditsPositionTicks'], f"embymediacourcename{Index}": MediaSource['Name'], f"embymediacourcesize{Index}": MediaSource['Size'], f"embymediacourcepath{Index}": MediaSource['Path'], f"embymediacourceid{Index}": MediaSource['Id']})

        if IsVideo and item['MediaSources'][0] and 'KodiStreams' in item['MediaSources'][0] and item['MediaSources'][0]['KodiStreams']:
            for Stream in item['MediaSources'][0]['KodiStreams']['Video']:
                set_ListItem_StreamInfo('video', InfoTags, item['KodiRunTimeTicks'], Stream)

            for Stream in item['MediaSources'][0]['KodiStreams']['Audio']:
                set_ListItem_StreamInfo('audio', InfoTags, 0, Stream)

            for Stream in item['MediaSources'][0]['KodiStreams']['Subtitle']:
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
                if ArtworkValue:
                    ArtworkData[KodiArtworkId] = ArtworkValue

        listitem.setArt(ArtworkData)

    listitem.setProperties(Properties)
    return listitem

def set_TvShowStatus(Item, InfoTags):
    if 'Status' in Item and Item['Status']:
        InfoTags.setTvShowStatus(Item['Status'])

def set_UserRating(Item, InfoTags):
    if 'CriticRating' in Item and Item['CriticRating']:
        InfoTags.setUserRating(Item['CriticRating'])


def set_RatingVideo(Item, InfoTags):
    if 'Ratings' not in Item:
        Item['Ratings'] = ()

        if 'CommunityRating' in Item and Item['CommunityRating']:
            if utils.imdbrating:
                Item['Ratings'] += (("imdb", float(Item['CommunityRating']), 0),)
                Item['RatingType'] = "imdb"
            else:
                Item['Ratings'] += (("default", float(Item['CommunityRating']), 0),)
                Item['RatingType'] = "default"

        if 'KodiCriticRating' in Item and Item['KodiCriticRating']:
            Item['Ratings'] += (("tomatometerallcritics", float(Item['KodiCriticRating']), 0),)

            if 'RatingType' not in Item or not Item['RatingType']:
                Item['RatingType'] = "tomatometerallcritics"

    RatingData = {}

    for Rating in Item['Ratings']:
        if Rating[2]:
            RatingData[Rating[0]] = (float(Rating[1]), int(Rating[2]))
        else:
            RatingData[Rating[0]] = (float(Rating[1]), 0)

    if RatingData:
        InfoTags.setRatings(RatingData, Item['RatingType'])

def set_Path(Item, InfoTags):
    if 'KodiPath' in Item and Item['KodiPath']:
        InfoTags.setPath(Item['KodiPath'])

def set_FilenameAndPath(Item, InfoTags):
    if 'KodiFullPath' in Item and Item['KodiFullPath']:
        InfoTags.setFilenameAndPath(Item['KodiFullPath'])

def set_RatingMusic(Item, InfoTags):
    if 'CommunityRating' in Item and Item['CommunityRating']:
        InfoTags.setRating(float(Item['CommunityRating']))

def set_PlotOutline(Item, InfoTags):
    if 'ShortOverview' in Item and Item['ShortOverview']:
        InfoTags.setPlotOutline(Item['ShortOverview'])

def set_OriginalTitle(Item, InfoTags):
    if 'OriginalTitle' in Item and Item['OriginalTitle']:
        InfoTags.setOriginalTitle(Item['OriginalTitle'])

def set_SortSeason(Item, InfoTags):
    if 'SortParentIndexNumber' in Item and Item['SortParentIndexNumber']:
        InfoTags.setSortSeason(int(Item['SortParentIndexNumber']))

def set_Season(Item, InfoTags, IndexNumber):
    if IndexNumber in Item and Item[IndexNumber]:
        InfoTags.setSeason(int(Item[IndexNumber]))

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

def set_PlaycountAudio(Item, InfoTags):
    if 'KodiPlayCount' in Item and Item['KodiPlayCount']:
        InfoTags.setPlayCount(Item['KodiPlayCount'])

def set_PlaycountVideo(Item, InfoTags):
    if 'KodiPlayCount' in Item and Item['KodiPlayCount']:
        InfoTags.setPlaycount(Item['KodiPlayCount'])

def set_LastPlayed(Item, InfoTags):
    if Item['KodiLastPlayedDate']:
        InfoTags.setLastPlayed(Item['KodiLastPlayedDate'])

def set_IMDBNumber(Item, InfoTags):
    if 'UniqueIdType' in Item and Item['UniqueIdType'] and Item['UniqueIdType'].lower() == "imdb":
        InfoTags.setIMDBNumber(Item['UniqueIdValue'])

def set_Mpaa(Item, InfoTags):
    if 'MPAA' in Item and Item['MPAA']:
        InfoTags.setMpaa(Item['MPAA'])

def set_TvShowTitle(Item, InfoTags):
    if 'SeriesName' in Item and Item['SeriesName']:
        InfoTags.setTvShowTitle(Item['SeriesName'])

def set_ResumePoint(Item, InfoTags):
    if 'KodiPlaybackPositionTicks' in Item and Item['KodiPlaybackPositionTicks']:
        if 'KodiRunTimeTicks' in Item and Item['KodiRunTimeTicks']:
            InfoTags.setResumePoint(float(Item['KodiPlaybackPositionTicks']), int(float(Item['KodiRunTimeTicks'])))
        else:
            InfoTags.setResumePoint(float(Item['KodiPlaybackPositionTicks']))

def set_Artists(Item, InfoTags):
    if 'Artists' in Item and Item['Artists']:
        InfoTags.setArtists(Item['Artists'])

def set_Writers(Item, InfoTags):
    if 'Writers' in Item and Item['Writers']:
        InfoTags.setWriters(Item['Writers'])

def set_Directors(Item, InfoTags):
    if 'Directors' in Item and Item['Directors']:
        InfoTags.setDirectors(Item['Directors'])

def set_Trailer(Item, InfoTags):
    if 'Trailer' in Item and Item['Trailer']:
        InfoTags.setTrailer(Item['Trailer'])

def set_EmbyIdAsKodiIdVideo(Item, InfoTags, ServerId): # Fake Id is necessary, otherwise Kodi does not report notifications via monitor.py
    if 'Id' in Item and Item['Id']:
        Item['KodiId'] = utils.set_EmbyId_ServerId_by_Fake_KodiId(Item['Id'], ServerId)
        InfoTags.setDbId(Item['KodiId']) # Maximum value is 2147483648

def set_EmbyIdAsKodiIdAudio(Item, InfoTags, ServerId, KodiType): # Fake Id is necessary, otherwise Kodi does not report notifications via monitor.py
    if 'Id' in Item and Item['Id']:
        Item['KodiId'] = utils.set_EmbyId_ServerId_by_Fake_KodiId(Item['Id'], ServerId)
        InfoTags.setDbId(Item['KodiId'], KodiType) # Maximum value is 2147483648

def set_ListItem_StreamInfo(Content, InfoTags, Duration, StreamInfo):
    if Content == "video":
        if StreamInfo['width'] and StreamInfo['height'] and StreamInfo['aspect']:
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

def get_TotalEpisodesSeason(ParentId, ServerId, isSpecial):
    EpisodeInfo = set()
    Uid = 10000

    if isSpecial:
        Params = (ParentId, ("Episode",), True, {}, None, False, False)
    else:
        Params = (ParentId, ("Episode",), True, {"IsSpecialSeason": False}, None, False, False)

    for Item in utils.EmbyServers[ServerId].API.get_Items(*Params):
        Uid += 1
        Temp = (Item.get("IndexNumber", Uid), Item.get("ParentIndexNumber", Uid))

        if Temp not in EpisodeInfo: # Filter multiversions
            EpisodeInfo.add(Temp)

    TotalEpisodes = len(EpisodeInfo)
    del EpisodeInfo
    return TotalEpisodes

def get_TotalEpisodesSeries(ParentId, ServerId):
    EpisodeInfo = set()
    Uid = 10000

    for Item in utils.EmbyServers[ServerId].API.get_Items(ParentId, ("Episode",), True, {"IsSpecialSeason": False, "fields": "SpecialEpisodeNumbers"}, None, False, False):
        if ("ParentIndexNumber" in Item and not Item["ParentIndexNumber"]) and not ("SortIndexNumber" in Item and Item["SortIndexNumber"]) and not ("SortParentIndexNumber" in Item and Item["SortParentIndexNumber"]): # Filter inserted specials
            continue

        Uid += 1
        Temp = (Item.get("IndexNumber", Uid), Item.get("ParentIndexNumber", Uid))

        if Temp not in EpisodeInfo: # Filter multiversions
            EpisodeInfo.add(Temp)

    TotalEpisodes = len(EpisodeInfo)
    del EpisodeInfo
    return TotalEpisodes

def get_MimeType(Path):
    if not Path:
        return ""

    p = Path.lower().replace("|redirect-limit=1000&failonerror=false", "").replace("|seekable=0&failonerror=false&verifypeer=false", "")

    if p.endswith(".mp4") or p.endswith(".m4v"):
        return "video/mp4"

    if p.endswith(".mkv"):
        return "video/x-matroska"

    if p.endswith(".avi"):
        return "video/x-msvideo"

    if p.endswith(".ts") or p.endswith(".m2ts") or p.endswith(".mts"):
        return "video/mp2t"

    if p.endswith(".mpg") or p.endswith(".mpeg") or p.endswith(".mpe"):
        return "video/mpeg"

    if p.endswith(".webm"):
        return "video/webm"

    if p.endswith(".mov"):
        return "video/quicktime"

    if p.endswith(".wmv"):
        return "video/x-ms-wmv"

    if p.endswith(".ogv"):
        return "video/ogg"

    if p.endswith(".3gp"):
        return "video/3gpp"

    if p.endswith(".flv"):
        return "video/x-flv"

    if p.endswith(".mxf"):
        return "application/mxf"

    if p.endswith(".vob"):
        return "video/dvd"

    if p.endswith(".asf"):
        return "video/x-ms-asf"

    if p.endswith(".strm"):
        return "text/plain"

    if p.endswith(".m3u") or p.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"

    if p.endswith(".pls"):
        return "audio/x-scpls"

    if p.endswith(".jpg") or p.endswith(".jpeg") or p.endswith(".jpe") or p.endswith(".jfif"):
        return "image/jpeg"

    if p.endswith(".png"):
        return "image/png"

    if p.endswith(".gif"):
        return "image/gif"

    if p.endswith(".webp"):
        return "image/webp"

    if p.endswith(".avif"):
        return "image/avif"

    if p.endswith(".heic") or p.endswith(".heif"):
        return "image/heic"

    if p.endswith(".apng"):
        return "image/apng"

    if p.endswith(".svg") or p.endswith(".svgz"):
        return "image/svg+xml"

    if p.endswith(".ico"):
        return "image/vnd.microsoft.icon"

    if p.endswith(".bmp"):
        return "image/bmp"

    if p.endswith(".tiff") or p.endswith(".tif"):
        return "image/tiff"

    if p.endswith(".psd"):
        return "image/vnd.adobe.photoshop"

    if p.endswith(".ai") or p.endswith(".eps"):
        return "application/postscript"

    if p.endswith(".dng"):
        return "image/x-adobe-dng"

    if p.endswith(".cr2") or p.endswith(".cr3") or p.endswith(".crw"):
        return "image/x-canon-raw"

    if p.endswith(".nef") or p.endswith(".nrw"):
        return "image/x-nikon-nef"

    if p.endswith(".arw") or p.endswith(".srf") or p.endswith(".sr2"):
        return "image/x-sony-arw"

    if p.endswith(".orf"):
        return "image/x-olympus-orf"

    if p.endswith(".raf"):
        return "image/x-fuji-raf"

    if p.endswith(".rw2"):
        return "image/x-panasonic-raw"

    if p.endswith(".raw"):
        return "image/x-dcraw"

    if p.endswith(".jpx") or p.endswith(".jp2"):
        return "image/jp2"

    if p.endswith(".tga"):
        return "image/x-tga"

    if p.endswith(".pcx"):
        return "image/x-pcx"

    if p.endswith(".mp3"):
        return "audio/mpeg"

    if p.endswith(".flac"):
        return "audio/flac"

    if p.endswith(".m4a") or p.endswith(".m4b"):
        return "audio/mp4"

    if p.endswith(".wav"):
        return "audio/wav"

    if p.endswith(".aac"):
        return "audio/aac"

    if p.endswith(".ogg") or p.endswith(".oga"):
        return "audio/ogg"

    if p.endswith(".opus"):
        return "audio/opus"

    if p.endswith(".wma"):
        return "audio/x-ms-wma"

    if p.endswith(".aiff") or p.endswith(".aif") or p.endswith(".aifc"):
        return "audio/x-aiff"

    if p.endswith(".ac3"):
        return "audio/ac3"

    if p.endswith(".dts"):
        return "audio/vnd.dts"

    if p.endswith(".amr"):
        return "audio/amr"

    if p.endswith(".mp2"):
        return "audio/mpeg"

    if p.endswith(".dsf"):
        return "audio/x-dsf"

    if p.endswith(".dff"):
        return "audio/x-dff"

    if p.endswith(".ape"):
        return "audio/x-ape"

    if p.endswith(".wv"):
        return "audio/x-wavpack"

    if p.endswith(".tta"):
        return "audio/x-tta"

    if p.endswith(".mpc"):
        return "audio/x-musepack"

    if p.endswith(".shn"):
        return "audio/x-shn"

    if p.endswith(".mka"):
        return "audio/x-matroska"

    if p.endswith(".mid") or p.endswith(".midi"):
        return "audio/midi"

    if p.endswith(".mod"):
        return "audio/x-mod"

    if p.endswith(".it"):
        return "audio/x-it"

    if p.endswith(".s3m"):
        return "audio/x-s3m"

    if p.endswith(".xm"):
        return "audio/x-xm"

    return ""

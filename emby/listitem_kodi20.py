import xbmc
import xbmcgui
from helper import utils
from core import common

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

    if KodiItem['mediatype'] in ("episode", "movie", "musicvideo", "tvshow", "season", "set"):
        InfoTags = ListItem.getVideoInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']))

        if bool(KodiItem.get('dateadded')):
            InfoTags.setDateAdded(KodiItem['dateadded'])

        if bool(KodiItem.get('rating')):
            InfoTags.setRating(float(KodiItem['rating']))

        if bool(KodiItem.get('userrating')):
            InfoTags.setUserRating(int(KodiItem['userrating']))

        if bool(KodiItem.get('tagline')):
            InfoTags.setTagLine(KodiItem['tagline'])

        if bool(KodiItem.get('plotoutline')):
            InfoTags.setPlotOutline(KodiItem['plotoutline'])

        if bool(KodiItem.get('country')):
            InfoTags.setCountries(KodiItem['country'].split("/"))

        if bool(KodiItem.get('mpaa')):
            InfoTags.setMpaa(KodiItem['mpaa'])

        if bool(KodiItem.get('originaltitle')):
            InfoTags.setOriginalTitle(KodiItem['originaltitle'])

        if bool(KodiItem.get('plot')):
            InfoTags.setPlot(KodiItem['plot'])

        if bool(KodiItem.get('sorttitle')):
            InfoTags.setSortTitle(KodiItem['sorttitle'])

        if bool(KodiItem.get('studio')):
            InfoTags.setStudios(KodiItem['studio'].split("/"))

        if bool(KodiItem.get('writer')):
            InfoTags.setWriters(KodiItem['writer'].split("/"))

        if bool(KodiItem.get('director')):
            InfoTags.setDirectors(KodiItem['director'].split("/"))

        if bool(KodiItem.get('sortseason')):
            InfoTags.setSortSeason(int(KodiItem['sortseason']))

        if bool(KodiItem.get('season')):
            InfoTags.setSeason(int(KodiItem['season']))

        if bool(KodiItem.get('episode')):
            InfoTags.setEpisode(int(KodiItem['episode']))

        if bool(KodiItem.get('sortepisode')):
            InfoTags.setSortEpisode(int(KodiItem['sortepisode']))

        if bool(KodiItem.get('tvshowtitle')):
            InfoTags.setTvShowTitle(KodiItem['tvshowtitle'])

        if bool(KodiItem.get('imdbnumber')):
            InfoTags.setIMDBNumber(KodiItem['imdbnumber'])

        if bool(KodiItem.get('premiered')):
            InfoTags.setPremiered(KodiItem['premiered'])

        if bool(KodiItem.get('resumepoint')):
            InfoTags.setResumePoint(KodiItem['resumepoint'], KodiItem['totaltime'])

        if bool(KodiItem.get('trailer')):
            InfoTags.setTrailer(KodiItem['trailer'])

        if bool(KodiItem.get('path')):
            InfoTags.setPath(KodiItem['path'])

        if bool(KodiItem.get('pathandfilename')):
            InfoTags.setFilenameAndPath(KodiItem['pathandfilename'])

        if bool(KodiItem.get('track')):
            InfoTags.setTrackNumber(int(KodiItem['track']))

        if bool(KodiItem.get('album')):
            InfoTags.setAlbum(KodiItem['album'])

        if bool(KodiItem.get('artist')):
            InfoTags.setArtists(KodiItem['artist'])

        if bool(KodiItem.get('tvshowstatus')):
            InfoTags.setTvShowStatus(KodiItem['tvshowstatus'])

        if bool(KodiItem.get('firstaired')):
            InfoTags.setFirstAired(KodiItem['firstaired'])

        if bool(KodiItem.get('people')):
            People = ()

            for Person in KodiItem['people']:
                People += (xbmc.Actor(*Person),)

            InfoTags.setCast(People)
    elif KodiItem['mediatype'] in ("song", "artist", "album"):
        InfoTags = ListItem.getMusicInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']), KodiItem['mediatype'])

        if bool(KodiItem.get('artist')):
            InfoTags.setArtist(KodiItem['artist'])

        if bool(KodiItem.get('albumartists')):
            InfoTags.setAlbumArtist(KodiItem['albumartists'])

        if bool(KodiItem.get('comment')):
            InfoTags.setComment(KodiItem['comment'])

        if bool(KodiItem.get('disc')):
            InfoTags.setDisc(KodiItem['disc'])

        if bool(KodiItem.get('track')):
            InfoTags.setTrack(KodiItem['track'])

        if bool(KodiItem.get('album')):
            InfoTags.setAlbum(KodiItem['album'])

        if bool(KodiItem.get('releasedate')):
            InfoTags.setReleaseDate(KodiItem['releasedate'])

        if bool(KodiItem.get('musicbrainzartistid')):
            InfoTags.setMusicBrainzArtistID(KodiItem['musicbrainzartistid'].split("/"))

        if bool(KodiItem.get('musicbrainzalbumid')):
            InfoTags.setMusicBrainzAlbumID(KodiItem['musicbrainzalbumid'])

        if bool(KodiItem.get('musicbrainztrackid')):
            InfoTags.setMusicBrainzTrackID(KodiItem['musicbrainztrackid'])

#        InfoTags.setMusicBrainzAlbumArtistID(item['ProviderIds']['MusicBrainzAlbumArtist'])

    # Common infotags
    InfoTags.setMediaType(KodiItem['mediatype'])
    InfoTags.setTitle(KodiItem['title'])

    if bool(KodiItem.get('duration')):
        InfoTags.setDuration(int(KodiItem['duration']))

    if KodiItem['artwork']:
        ListItem.setArt(KodiItem['artwork'])

    if bool(KodiItem.get('genre')):
        InfoTags.setGenres(KodiItem['genre'].split("/"))

    if bool(KodiItem.get('playCount')):
        InfoTags.setPlaycount(KodiItem['playCount'])

    if bool(KodiItem.get('lastplayed')):
        InfoTags.setLastPlayed(KodiItem['lastplayed'])

    if bool(KodiItem.get('year')):
        InfoTags.setYear(KodiItem['year'])

    ListItem.setProperties(KodiItem['properties'])
    ListItem.setContentLookup(False)
    IsFolder = bool(KodiItem['properties']['IsFolder'] == "true")
    return IsFolder, ListItem

def set_ListItem(item, ServerId, Path, get_shortdate):
    if Path:
        listitem = xbmcgui.ListItem(label=item['Name'], offscreen=True, path=Path)
    else:
        listitem = xbmcgui.ListItem(label=item['Name'], offscreen=True)

    Properties = {}
    InfoTags = None
    HasStreams = False
    IsVideo = False

    if 'Library' not in item:
        item['Library'] = {'Id': 0}

    item['LibraryIds'] = [item['Library']['Id']]

    if item['Type'] == 'Folder' or item.get('NodesMenu', False):
        InfoTags = listitem.getVideoInfoTag()
        InfoTags.setTitle(item['Name'])
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
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setPlot(item['CurrentProgram']['Overview'])
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setDuration(int(item['CurrentProgram']['RunTimeTicks']))
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['CurrentProgram']['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setIMDBNumber(item.get('Unique', ""))
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setDbId(1000000000 + int(item['Id']))
        InfoTags.setResumePoint(int(item['CurrentProgram']['UserData']['PlaybackPositionTicks']))
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] in ("Movie", "Trailer"):
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("movie")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setMpaa(item['OfficialRating'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setIMDBNumber(item.get('Unique', ""))
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        InfoTags.setResumePoint(int(item['UserData']['PlaybackPositionTicks']), int(item['RunTimeTicks']))

        if item['Type'] == "Movie":
            common.set_trailer(item, utils.EmbyServers[ServerId])
            InfoTags.setTrailer(item['Trailer'])

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "Series":
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        common.set_trailer(item, utils.EmbyServers[ServerId])
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("tvshow")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setMpaa(item['OfficialRating'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTrailer(item['Trailer'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setTvShowStatus(item.get('status', ""))
        InfoTags.setTvShowTitle(item['Name'])
        InfoTags.setIMDBNumber(item.get('Unique', ""))
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'TotalEpisodes': item.get('RecursiveItemCount', 0), 'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']), 'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'], 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Season":
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("season")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setMpaa(item['OfficialRating'])
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setSeason(item.get('IndexNumber', 0))
        InfoTags.setIMDBNumber(item.get('Unique', ""))
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'NumEpisodes': item.get('RecursiveItemCount', 0), 'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']), 'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'], 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Episode":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("episode")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setMpaa(item['OfficialRating'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setSortSeason(item.get('SortParentIndexNumber', 0))
        InfoTags.setSeason(item.get('ParentIndexNumber', 0))
        InfoTags.setEpisode(item.get('IndexNumber', 0))
        InfoTags.setSortEpisode(item.get('SortIndexNumber', 0))
        InfoTags.setTvShowTitle(item.get('SeriesName', ""))
        InfoTags.setIMDBNumber(item.get('Unique', ""))
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        InfoTags.setResumePoint(int(item['UserData']['PlaybackPositionTicks']), int(item['RunTimeTicks']))
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true'}

        # Upcoming
        if item['MediaSources'][0]['Type'] == "Placeholder":
            Properties['IsPlayable'] = 'false'
            item['NoLink'] = True
        else:
            Properties['embyid'] = str(item['Id'])
    elif item['Type'] == "MusicVideo":
        for artist in item['ArtistItems']:
            artist['Type'] = "Artist"

        item['People'] = item.get('People', [])
        item['People'] = item['People'] + item['ArtistItems']
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_overview(item)
        common.set_MusicVideoTracks(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("musicvideo")
        InfoTags.setTrackNumber(item['IndexNumber'])

        if 'Artists' in item and item['Artists']:
            InfoTags.setArtists(item['Artists'])

        if 'Album' in item and item['Album']:
            InfoTags.setAlbum(item['Album'])

        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        InfoTags.setResumePoint(int(item['UserData']['PlaybackPositionTicks']), int(item['RunTimeTicks']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "Video":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_overview(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        HasStreams = True
        InfoTags.setMediaType("video")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setDbId(1000000000 + int(item['Id']))
        InfoTags.setResumePoint(int(item['UserData']['PlaybackPositionTicks']), int(item['RunTimeTicks']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "MusicArtist":
        common.set_KodiArtwork(item, ServerId, True)
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['Genres'] = item.get('Genres', [])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzArtist'] = tuple(item['ProviderIds'].get('MusicBrainzArtist', ()))
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("artist")
        InfoTags.setTitle(item['Name'])
        InfoTags.setArtist(item['Name'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlayCount(int(item['UserData']['PlayCount']))
        InfoTags.setGenres(item['Genres'])
        InfoTags.setDbId(1000000000 + int(item['Id']), "artist")
        InfoTags.setMusicBrainzArtistID(item['ProviderIds']['MusicBrainzArtist'])
        InfoTags.setComment(item['Overview'])
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "MusicAlbum":
        common.set_KodiArtwork(item, ServerId, True)
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['Genres'] = item.get('Genres', [])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', "")
        item['ProviderIds']['MusicBrainzAlbumArtist'] = tuple(item['ProviderIds'].get('MusicBrainzAlbumArtist', ()))
        item['ProductionYear'] = item.get('ProductionYear', 0)
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("album")
        InfoTags.setTitle(item['Name'])
        InfoTags.setAlbum(item['Name'])

        if 'AlbumArtist' in item and item['AlbumArtist']:
            InfoTags.setAlbumArtist(item['AlbumArtist'])

        InfoTags.setArtist(" / ".join(item['Artists']))
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlayCount(int(item['UserData']['PlayCount']))
        InfoTags.setGenres(item['Genres'])
        InfoTags.setDbId(1000000000 + int(item['Id']), "album")
        InfoTags.setMusicBrainzAlbumID(item['ProviderIds']['MusicBrainzAlbum'])
        InfoTags.setMusicBrainzAlbumArtistID(item['ProviderIds']['MusicBrainzAlbumArtist'])
        InfoTags.setComment(item['Overview'])
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    elif item['Type'] == "Audio":
        common.set_KodiArtwork(item, ServerId, True)
        item['ProductionYear'] = item.get('ProductionYear', 0)
        item['Genres'] = item.get('Genres', [])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzTrack'] = item['ProviderIds'].get('MusicBrainzTrack', "")
        item['ProviderIds']['MusicBrainzArtist'] = tuple(item['ProviderIds'].get('MusicBrainzArtist', ()))
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', "")
        item['ProviderIds']['MusicBrainzAlbumArtist'] = tuple(item['ProviderIds'].get('MusicBrainzAlbumArtist', ()))
        item['IndexNumber'] = item.get('IndexNumber', None)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 1)
        item['UserData']['LastPlayedDate'] = item['UserData'].get('LastPlayedDate', None)
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setArtist(" / ".join(item['Artists']))

        if 'Album' in item and item['Album']:
            InfoTags.setAlbum(item['Album'])

        if 'AlbumArtist' in item and item['AlbumArtist']:
            InfoTags.setAlbumArtist(item['AlbumArtist'])

        InfoTags.setMediaType("song")
        InfoTags.setTitle(item['Name'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlayCount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setDbId(1000000000 + int(item['Id']), "song")
        InfoTags.setMusicBrainzArtistID(item['ProviderIds']['MusicBrainzArtist'])
        InfoTags.setMusicBrainzAlbumID(item['ProviderIds']['MusicBrainzAlbum'])
        InfoTags.setMusicBrainzAlbumArtistID(item['ProviderIds']['MusicBrainzAlbumArtist'])
        InfoTags.setMusicBrainzTrackID(item['ProviderIds']['MusicBrainzTrack'])
        InfoTags.setComment(item['Overview'])
        InfoTags.setDisc(item['ParentIndexNumber'])

        if item['IndexNumber']:
            InfoTags.setTrack(item['IndexNumber'])

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "BoxSet":
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        common.set_videocommon(item, ServerId, 0, True)
        InfoTags = listitem.getVideoInfoTag()
        IsVideo = True
        InfoTags.setMediaType("set")
        InfoTags.setTitle(item['Name'])
        InfoTags.setSortTitle(item['SortName'])
        InfoTags.setOriginalTitle(item.get('OriginalTitle', ""))
        InfoTags.setPlot(item['Overview'])
        InfoTags.setPlotOutline(item.get('ShortOverview', ""))
        InfoTags.setDateAdded(item['DateCreated'])
        InfoTags.setYear(item['ProductionYear'])
        InfoTags.setRating(item.get('CommunityRating', 0))
        InfoTags.setDuration(int(item['RunTimeTicks']))
        InfoTags.setPlaycount(int(item['UserData']['PlayCount']))
        InfoTags.setLastPlayed(item['UserData']['LastPlayedDate'])
        InfoTags.setGenres(item['Genres'])
        InfoTags.setCountries(item['ProductionLocations'])
        InfoTags.setTagLine(item['Taglines'][0])
        InfoTags.setStudios(item['Studios'])
        InfoTags.setWriters(item['Writers'])
        InfoTags.setDirectors(item['Directors'])
        InfoTags.setUserRating(item.get('CriticRating', 0))
        InfoTags.setPremiered(item['PremiereDate'])
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
        common.set_PremiereDate(item)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['PremiereDate']))

        if item['Height'] > 0:
            PictureInfoTags.setResolution(int(item['Width']), int(item['Height']))

        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'false', 'IsPlayable': 'true'}
    elif item['Type'] == "PhotoAlbum":
        common.set_KodiArtwork(item, ServerId, True)
        common.set_PremiereDate(item)
        PictureInfoTags = listitem.getPictureInfoTag()
        PictureInfoTags.setDateTimeTaken(get_shortdate(item['PremiereDate']))
        Properties = {'embyserverid': str(ServerId), 'embyid': str(item['Id']), 'IsFolder': 'true', 'IsPlayable': 'true'}
    else: # Letter etc
        InfoTags = listitem.getVideoInfoTag()
        InfoTags.setTitle(item['Name'])
        common.set_KodiArtwork(item, ServerId, True)

    if HasStreams:
        if 'Streams' in item:
            for track in item['Streams'][0]['Video']:
                set_ListItem_StreamInfo('video', InfoTags, {'duration': item['RunTimeTicks'], 'aspect': track['aspect'], 'codec': track['codec'], 'width': track['width'], 'height': track['height']})

            for track in item['Streams'][0]['Audio']:
                set_ListItem_StreamInfo('audio', InfoTags, {'codec': track['codec'], 'channels': track['channels']})

            for track in item['Streams'][0]['Subtitle']:
                set_ListItem_StreamInfo('subtitle', InfoTags, {'language': track['language']})

    if IsVideo and 'People' in item and item['People']:
        cast = ()

        for person in item['People']:
            if person['Type'] in ("Actor", "Artist", 'Director', 'GuestStar'):
                if str(person['imageurl']).startswith("http"):
                    ImageUrl = person['imageurl']
                else:
                    ImageUrl = ""

                cast += ((xbmc.Actor(person['Name'], person.get('Role', "Unknown"), len(cast) + 1, ImageUrl)),)

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

    listitem.setContentLookup(False)
    return listitem

def set_ListItem_StreamInfo(Content, InfoTags, StreamInfo):
    if Content == "video":
        InfoTags.addVideoStream(xbmc.VideoStreamDetail(int(StreamInfo['width']), int(StreamInfo['height']), float(StreamInfo.get('aspect', 0.0)), int(StreamInfo['duration']), StreamInfo.get('codec', ""), "", ""))
    elif Content == "audio":
        InfoTags.addAudioStream(xbmc.AudioStreamDetail(StreamInfo.get('channels', 0), StreamInfo.get('codec', ""), ""))
    elif Content == "subtitle":
        InfoTags.addSubtitleStream(xbmc.SubtitleStreamDetail(StreamInfo['language']))

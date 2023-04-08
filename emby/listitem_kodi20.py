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

        if 'dateadded' in KodiItem:
            InfoTags.setDateAdded(KodiItem['dateadded'])

        if 'rating' in KodiItem and KodiItem['rating']:
            InfoTags.setRating(float(KodiItem['rating']))

        if 'userrating' in KodiItem and KodiItem['userrating']:
            InfoTags.setUserRating(int(KodiItem['userrating']))

        if 'tagline' in KodiItem:
            InfoTags.setTagLine(KodiItem['tagline'])

        if 'plotoutline' in KodiItem:
            InfoTags.setPlotOutline(KodiItem['plotoutline'])

        if 'country' in KodiItem and KodiItem['country']:
            InfoTags.setCountries(KodiItem['country'].split("/"))

        if 'mpaa' in KodiItem:
            InfoTags.setMpaa(KodiItem['mpaa'])

        if 'originaltitle' in KodiItem:
            InfoTags.setOriginalTitle(KodiItem['originaltitle'])

        if 'plot' in KodiItem:
            InfoTags.setPlot(KodiItem['plot'])

        if 'sorttitle' in KodiItem:
            InfoTags.setSortTitle(KodiItem['sorttitle'])

        if 'studio' in KodiItem and KodiItem['studio']:
            InfoTags.setStudios(KodiItem['studio'].split("/"))

        if 'writer' in KodiItem and KodiItem['writer']:
            InfoTags.setWriters(KodiItem['writer'].split("/"))

        if 'director' in KodiItem and KodiItem['director']:
            InfoTags.setDirectors(KodiItem['director'].split("/"))

        if 'sortseason' in KodiItem and KodiItem['sortseason']:
            InfoTags.setSortSeason(int(KodiItem['sortseason']))

        if 'season' in KodiItem and KodiItem['season']:
            InfoTags.setSeason(int(KodiItem['season']))

        if 'episode' in KodiItem:
            InfoTags.setEpisode(int(KodiItem['episode']))

        if 'sortepisode' in KodiItem and KodiItem['sortepisode']:
            InfoTags.setSortEpisode(int(KodiItem['sortepisode']))

        if 'tvshowtitle' in KodiItem:
            InfoTags.setTvShowTitle(KodiItem['tvshowtitle'])

        if 'imdbnumber' in KodiItem:
            InfoTags.setIMDBNumber(KodiItem['imdbnumber'])

        if 'premiered' in KodiItem:
            InfoTags.setPremiered(KodiItem['premiered'])

        if 'resumepoint' in KodiItem and KodiItem['resumepoint']:
            InfoTags.setResumePoint(KodiItem['resumepoint'], KodiItem['totaltime'])

        if 'trailer' in KodiItem and KodiItem['trailer']:
            InfoTags.setTrailer(KodiItem['trailer'])

        if 'path' in KodiItem:
            InfoTags.setPath(KodiItem['path'])

        if 'pathandfilename' in KodiItem:
            InfoTags.setFilenameAndPath(KodiItem['pathandfilename'])

        if 'track' in KodiItem and KodiItem['track']:
            InfoTags.setTrackNumber(int(KodiItem['track']))

        if 'album' in KodiItem:
            InfoTags.setAlbum(KodiItem['album'])

        if 'artist' in KodiItem:
            InfoTags.setArtists(KodiItem['artist'])

        if 'tvshowstatus' in KodiItem:
            InfoTags.setTvShowStatus(KodiItem['tvshowstatus'])

        if 'firstaired' in KodiItem:
            InfoTags.setFirstAired(KodiItem['firstaired'])

        if 'people' in KodiItem:
            People = ()

            for Person in KodiItem['people']:
                People += (xbmc.Actor(*Person),)

            InfoTags.setCast(People)
    elif KodiItem['mediatype'] in ("song", "artist", "album"):
        InfoTags = ListItem.getMusicInfoTag()
        InfoTags.setDbId(int(KodiItem['dbid']), KodiItem['mediatype'])

        if 'artist' in KodiItem:
            InfoTags.setArtist(KodiItem['artist'])

        if 'comment' in KodiItem:
            InfoTags.setComment(KodiItem['comment'])

        if 'disc' in KodiItem:
            InfoTags.setDisc(KodiItem['disc'])

        if 'track' in KodiItem:
            InfoTags.setTrack(KodiItem['track'])

        if 'musicbrainzartistid' in KodiItem and KodiItem['musicbrainzartistid']:
            InfoTags.setMusicBrainzArtistID(KodiItem['musicbrainzartistid'].split("/"))

        if 'musicbrainzalbumid' in KodiItem:
            InfoTags.setMusicBrainzAlbumID(KodiItem['musicbrainzalbumid'])

        if 'musicbrainztrackid' in KodiItem:
            InfoTags.setMusicBrainzTrackID(KodiItem['musicbrainztrackid'])

#        InfoTags.setMusicBrainzAlbumArtistID(item['ProviderIds']['MusicBrainzAlbumArtist'])

    # Common infotags
    InfoTags.setMediaType(KodiItem['mediatype'])
    InfoTags.setTitle(KodiItem['title'])

    if 'duration' in KodiItem and KodiItem['duration']:
        InfoTags.setDuration(int(KodiItem['duration']))

    if KodiItem['artwork']:
        ListItem.setArt(KodiItem['artwork'])

    if 'genre' in KodiItem and KodiItem['genre']:
        InfoTags.setGenres(KodiItem['genre'].split("/"))

    if 'playCount' in KodiItem and KodiItem['playCount']:
        InfoTags.setPlaycount(KodiItem['playCount'])

    if 'lastplayed' in KodiItem:
        InfoTags.setLastPlayed(KodiItem['lastplayed'])

    if 'year' in KodiItem:
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
#        InfoTags.setArtists()
#        InfoTags.setAlbum()
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
        item['ProductionYear'] = item.get('ProductionYear')
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        InfoTags = listitem.getMusicInfoTag()
        InfoTags.setMediaType("album")
        InfoTags.setTitle(item['Name'])
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
        item['AlbumId'] = item.get('AlbumId', None)
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

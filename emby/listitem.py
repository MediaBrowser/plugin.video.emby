import xbmcgui
from helper import utils, loghandler
from core import common
LOG = loghandler.LOG('EMBY.emby.listitem')


def set_ListItem(item, server_id):
    listitem = xbmcgui.ListItem(label=item['Name'], offscreen=True)
    Properties = {}
    common.set_KodiArtwork(item, server_id)
    item['LibraryIds'] = [item['Library']['Id']]

    if item['Type'] == 'Folder' or item.get('NodesMenu', False):
        common.set_overview(item)
        metadata = {
            'title': item['Name'],
            'plot': item['Overview']
        }
        Properties = {
            'IsFolder': 'true',
            'IsPlayable': 'false'
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "TvChannel":
        item['CurrentProgram'] = item.get('CurrentProgram', {})
        item['CurrentProgram']['UserData'] = item['CurrentProgram'].get('UserData', {})

        if 'Name' in item['CurrentProgram']:
            item['Name'] = "%s / %s" % (item['Name'], item['CurrentProgram']['Name'])

        if 'RunTimeTicks' in item['CurrentProgram']:
            item['CurrentProgram']['RunTimeTicks'] = round(float((item['CurrentProgram']['RunTimeTicks']) / 10000000.0), 6)
        else:
            item['CurrentProgram']['RunTimeTicks'] = 0

        if 'PlaybackPositionTicks' in item['CurrentProgram']['UserData']:
            item['CurrentProgram']['UserData']['PlaybackPositionTicks'] = round(float((item['CurrentProgram']['UserData']['PlaybackPositionTicks']) / 10000000.0), 6)
        else:
            item['CurrentProgram']['UserData']['PlaybackPositionTicks'] = 0

        item['CurrentProgram']['Genres'] = item['CurrentProgram'].get('Genres', [])
        item['CurrentProgram']['Genres'] = item['CurrentProgram'].get('Genres', [])
        item['CurrentProgram']['UserData']['PlayCount'] = item['CurrentProgram']['UserData'].get('PlayCount', 0)
        item['CurrentProgram']['UserData']['LastPlayedDate'] = item['CurrentProgram']['UserData'].get('LastPlayedDate', "")

        common.get_streams(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'sorttitle': item['SortName'],
            'country': item['ProductionLocations'],
            'genre': item['CurrentProgram']['Genres'],
            'playcount': item['CurrentProgram']['UserData']['PlayCount'],
            'overlay': 5 if item['CurrentProgram']['UserData']['PlayCount'] else 4,
            'plot': item['CurrentProgram']['Overview'],
            'tagline': item['Taglines'][0],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['CurrentProgram']['UserData']['LastPlayedDate'],
            'duration': item['CurrentProgram']['RunTimeTicks'],
            'userrating': item.get('CriticRating', None),
            'mediatype': "video"
        }
        Properties = {
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['CurrentProgram']['RunTimeTicks']),
            'ResumeTime': item['CurrentProgram']['UserData']['PlaybackPositionTicks']
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] in ("Movie", "Trailer"):
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'sorttitle': item['SortName'],
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'mpaa': item['OfficialRating'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'duration': item['RunTimeTicks'],
            'imdbnumber': item.get('Unique', None),
            'userrating': item.get('CriticRating', None),
            'mediatype': "movie"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks']),
            'ResumeTime': item['UserData']['PlaybackPositionTicks']
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "Series":
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'tvshowtitle': item['Name'],
            'status': item.get('status', None),
            'sorttitle': item['SortName'],
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'mpaa': item['OfficialRating'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'imdbnumber': item.get('Unique', None),
            'userrating': item.get('CriticRating', None),
            'mediatype': "tvshow"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'TotalEpisodes': item.get('RecursiveItemCount', 0),
            'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']),
            'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'],
            'IsFolder': 'true',
            'IsPlayable': 'true'
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "Season":
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'season': item.get('IndexNumber', 0),
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'mpaa': item['OfficialRating'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'imdbnumber': item.get('Unique', None),
            'userrating': item.get('CriticRating', None),
            'mediatype': "season"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'NumEpisodes': item.get('RecursiveItemCount', 0),
            'WatchedEpisodes': int(item.get('RecursiveItemCount', 0)) - int(item['UserData']['UnplayedItemCount']),
            'UnWatchedEpisodes': item['UserData']['UnplayedItemCount'],
            'IsFolder': 'true',
            'IsPlayable': 'true'
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "Episode":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_mpaa(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'tvshowtitle': item['SeriesName'],
            'season': item.get('ParentIndexNumber', 0),
            'episode': item.get('IndexNumber', 0),
            'sortepisode': item.get('SortIndexNumber', None),
            'sortseason': item.get('SortParentIndexNumber', None),
            'sorttitle': item['SortName'],
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'mpaa': item['OfficialRating'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'duration': item['RunTimeTicks'],
            'imdbnumber': item.get('Unique', None),
            'userrating': item.get('CriticRating', None),
            'mediatype': "episode"
        }
        Properties = {
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks']),
            'ResumeTime': item['UserData']['PlaybackPositionTicks']
        }

        # Upcoming
        if item['MediaSources'][0]['Type'] == "Placeholder":
            metadata['date'] = get_shortdate(item['PremiereDate'])
            Properties['IsPlayable'] = 'false'
            item['NoLink'] = True
        else:
            Properties['embyid'] = str(item['Id'])

        listitem.setInfo('video', metadata)
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
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'sorttitle': item['SortName'],
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'duration': item['RunTimeTicks'],
            'userrating': item.get('CriticRating', None),
            'mediatype': "musicvideo"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks']),
            'ResumeTime': item['UserData']['PlaybackPositionTicks']
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "Video":
        common.SwopMediaSources(item)  # 3D
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'sorttitle': item['SortName'],
            'originaltitle': item.get('OriginalTitle', None),
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'duration': item['RunTimeTicks'],
            'mediatype': "video"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks']),
            'ResumeTime': item['UserData']['PlaybackPositionTicks']
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "MusicArtist":
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['Genres'] = item.get('Genres', [])
        item['Genre'] = " / ".join(item['Genres'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzArtist'] = item['ProviderIds'].get('MusicBrainzArtist', None)
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        metadata = {
            'title': item['Name'],
            'duration': str(item['RunTimeTicks']),
            'genre': item['Genre'],
            'artist': item['Name'],
            'musicbrainzartistid': item['ProviderIds']['MusicBrainzArtist'],
            'comment': item['Overview'],
            'playcount': item['UserData']['PlayCount'],
            'mediatype': "artist"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'true',
            'IsPlayable': 'false'
        }
        listitem.setInfo('music', metadata)
    elif item['Type'] == "MusicAlbum":
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['Genres'] = item.get('Genres', [])
        item['Genre'] = " / ".join(item['Genres'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', None)
        item['ProviderIds']['MusicBrainzAlbumArtist'] = item['ProviderIds'].get('MusicBrainzAlbumArtist', None)
        item['ProductionYear'] = item.get('ProductionYear')
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        metadata = {
            'title': item['Name'],
            'duration': str(item['RunTimeTicks']),
            'genre': item['Genre'],
            'artist': [item['Name']],
            'year': item['ProductionYear'],
            'musicbrainzalbumartistid': item['ProviderIds']['MusicBrainzAlbumArtist'],
            'musicbrainzalbumid': item['ProviderIds']['MusicBrainzAlbum'],
            'comment': item['Overview'],
            'playcount': item['UserData']['PlayCount'],
            'mediatype': "album"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'true',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks'])
        }
        listitem.setInfo('music', metadata)
    elif item['Type'] == "Audio":
        item['AlbumId'] = item.get('AlbumId', None)
        item['ProductionYear'] = item.get('ProductionYear', None)
        item['Genres'] = item.get('Genres', [])
        item['Genre'] = " / ".join(item['Genres'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzTrack'] = item['ProviderIds'].get('MusicBrainzTrack', None)
        item['ProviderIds']['MusicBrainzArtist'] = item['ProviderIds'].get('MusicBrainzArtist', None)
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', None)
        item['ProviderIds']['MusicBrainzAlbumArtist'] = item['ProviderIds'].get('MusicBrainzAlbumArtist', None)
        item['IndexNumber'] = item.get('IndexNumber', None)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 1)
        item['UserData']['LastPlayedDate'] = item['UserData'].get('LastPlayedDate', None)
        common.set_overview(item)
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        metadata = {
            'title': item['Name'],
            'sorttitle': item['SortName'],
            'tracknumber': item['IndexNumber'],
            'discnumber': item['ParentIndexNumber'],
            'playcount': item['UserData']['PlayCount'],
            'comment': item['Overview'],
            'duration': item['RunTimeTicks'],
            'musicbrainzartistid': item['ProviderIds']['MusicBrainzArtist'],
            'musicbrainzalbumartistid': item['ProviderIds']['MusicBrainzAlbumArtist'],
            'musicbrainzalbumid': item['ProviderIds']['MusicBrainzAlbum'],
            'musicbrainztrackid': item['ProviderIds']['MusicBrainzTrack'],
            'year': item['ProductionYear'],
            'mediatype': "song"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'false',
            'IsPlayable': 'true',
            'TotalTime': str(item['RunTimeTicks']),
            'ResumeTime': item['UserData']['PlaybackPositionTicks']
        }
        listitem.setInfo('music', metadata)
    elif item['Type'] == "BoxSet":
        common.set_RunTimeTicks(item)
        common.set_overview(item)
        common.set_videocommon(item, server_id, 0)
        metadata = {
            'title': item['Name'],
            'sorttitle': item.get('SortName', None),
            'originaltitle': item.get('OriginalTitle', None),
            'country': item['ProductionLocations'],
            'genre': item['Genres'],
            'year': item['ProductionYear'],
            'rating': item.get('CommunityRating', None),
            'playcount': item['UserData']['PlayCount'],
            'overlay': 5 if item['UserData']['PlayCount'] else 4,
            'director': item['Directors'],
            'plot': item['Overview'],
            'plotoutline': item.get('ShortOverview', ""),
            'studio': item['Studios'],
            'tagline': item['Taglines'][0],
            'writer': item['Writers'],
            'premiered': item['PremiereDate'],
            'date': get_shortdate(item['DateCreated']),
            'lastplayed': item['UserData']['LastPlayedDate'],
            'duration': item['RunTimeTicks'],
            'userrating': item.get('CriticRating', None),
            'mediatype': "set"
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'true',
            'IsPlayable': 'true'
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == 'Playlist':
        common.set_overview(item)
        metadata = {
            'title': item['Name'],
            'plot': item['Overview']
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'true',
            'IsPlayable': 'false'
        }
        listitem.setInfo('video', metadata)
    elif item['Type'] == "Photo":
        item['Width'] = str(item.get('Width', 0))
        item['Height'] = str(item.get('Height', 0))
        common.set_PremiereDate(item)
        metadata = {
            'title': item['Name'],
            'picturepath': item['KodiArtwork']['poster'],
            'exif:width': item['Width'],
            'exif:height': item['Height'],
            'date': get_shortdate(item['PremiereDate']),
            'count': item['UserData']['PlayCount'],
            'resolution': "%s, %s" % (item['Width'], item['Height'])
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'false',
            'IsPlayable': 'true'
        }
        listitem.setInfo('pictures', metadata)
    elif item['Type'] == "PhotoAlbum":
        common.set_PremiereDate(item)
        metadata = {
            'title': item['Name'],
            'picturepath': item['KodiArtwork']['poster'],
            'date': get_shortdate(item['PremiereDate']),
            'count': item['UserData']['PlayCount']
        }
        Properties = {
            'embyserverid': str(server_id),
            'embyid': str(item['Id']),
            'IsFolder': 'true',
            'IsPlayable': 'true'
        }
        listitem.setInfo('pictures', metadata)

    if 'Streams' in item:
        for track in item['Streams'][0]['Video']:
            listitem.addStreamInfo('video', {'duration': item['RunTimeTicks'], 'aspect': track['aspect'], 'codec': track['codec'], 'width': track['width'], 'height': track['height']})

        for track in item['Streams'][0]['Audio']:
            listitem.addStreamInfo('audio', {'codec': track['codec'], 'channels': track['channels']})

        for track in item['Streams'][0]['SubtitleLanguage']:
            listitem.addStreamInfo('subtitle', {'language': track})

    if Properties:
        listitem.setProperties(Properties)

    if item['KodiArtwork']:
        ArtworkData = {}

        for KodiArtworkId, ArtworkValue in list(item['KodiArtwork'].items()):
            if KodiArtworkId == 'fanart':
                for KodiArtworkIdFanart, ArtworkValueFanart in list(ArtworkValue.items()):
                    ArtworkData[KodiArtworkIdFanart] = ArtworkValueFanart
            else:
                ArtworkData[KodiArtworkId] = ArtworkValue

        listitem.setArt(ArtworkData)

    if 'People' in item:
        if item['People']:
            listitem.setCast(get_actors(item['People']))

    listitem.setContentLookup(False)
    return listitem

def get_shortdate(EmbyDate):
    try:
        DateTime = EmbyDate.split(" ")
        DateTemp = DateTime[0].split("-")
        return "%s-%s-%s" % (DateTemp[2], DateTemp[1], DateTemp[0])
    except:
        LOG.debug("No valid date: %s" % EmbyDate)
        return ""

def get_actors(People):
    cast = []

    for person in People:
        if person['Type'] in ("Actor", "Artist", 'Director', 'GuestStar'):
            cast.append({'name': person['Name'], 'role': person.get('Role', "Unknown"), 'order': len(cast) + 1, 'thumbnail': person['imageurl']})

    return cast

# -*- coding: utf-8 -*-
import xbmcgui
import core.common as Common
from . import obj_ops as Objects

art = {'clearart': "Art", 'clearlogo': "Logo", 'discart': "Disc", 'fanart_image': "Backdrop", 'landscape': "Thumb", 'thumb': "Primary", 'fanart': "Backdrop", 'banner': "Banner"}


def set_ListItem(item, server_id):
    listitem = xbmcgui.ListItem()
    Properties = {}

    if item['Type'] == 'Genre':
        obj = Objects.mapitem(item, 'BrowseGenre')
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, server_id)
        Properties['IsFolder'] = 'true'
        Properties['IsPlayable'] = 'false'
    elif item['Type'] in ("Movie", "MusicVideo", 'Episode', 'Season', 'Series', 'Video', 'BoxSet', 'AudioBook', 'Folder', 'Trailer', 'Studio', 'Person', 'Program', 'CollectionFolder', 'UserView', "Channel"):
        obj = Objects.mapitem(item, 'BrowseVideo')
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'ArtworkParent'), True, server_id)
        obj['Genres'] = " / ".join(obj['Genres'] or [])
        obj['Studios'] = " / ".join(obj['Studios'] or [])
        obj['Mpaa'] = Common.get_mpaa(obj['Mpaa'], item)
        obj['People'] = obj['People'] or []
        obj['Countries'] = " / ".join(obj['Countries'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Plot'] = Common.get_overview(obj['Plot'], item)
        obj['ShortPlot'] = Common.get_overview(obj['ShortPlot'], item)
        obj['Rating'] = obj['Rating'] or 0
        obj['DateAdded'], obj['FileDate'] = Common.get_DateAdded(obj['DateAdded'])
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['Resume'] = Common.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6
        obj['Video'] = Common.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = Common.audio_streams(obj['Audio'] or [])
        obj['Streams'] = Common.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['ChildCount'] = obj['ChildCount'] or 0
        obj['RecursiveCount'] = obj['RecursiveCount'] or 0
        obj['Unwatched'] = obj['Unwatched'] or 0

        if 'Primary' not in obj['Artwork']:
            obj['Artwork']['Primary'] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        if obj['Premiere']:
            obj['Premiere'] = obj['Premiere'].split('T')[0]

        if obj['DatePlayed']:
            obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

        if obj['Status'] != 'Ended':
            obj['Status'] = None

        Folder = False
        Properties['totaltime'] = str(obj['Runtime'])
        metadata = {
            'title': obj['Title'],
            'originaltitle': obj['OriginalTitle'],
            'sorttitle': obj['SortTitle'],
            'country': obj['Countries'],
            'genre': obj['Genres'],
            'year': obj['Year'],
            'rating': obj['Rating'],
            'playcount': obj['PlayCount'],
            'overlay': obj['Overlay'],
            'director': obj['Directors'],
            'mpaa': obj['Mpaa'],
            'plot': obj['Plot'],
            'plotoutline': obj['ShortPlot'],
            'studio': obj['Studios'],
            'tagline': obj['Tagline'],
            'writer': obj['Writers'],
            'premiered': obj['Premiere'],
            'date': obj['Premiere'] or obj['FileDate'],
            'lastplayed': obj['DatePlayed'],
            'duration': obj['Runtime'],
            'aired': obj['Year']
        }

        if obj['DateAdded']:
            metadata['dateadded'] = obj['DateAdded']

        if item['Type'] == 'Movie':
            metadata['imdbnumber'] = obj['UniqueId']
            metadata['userrating'] = obj['CriticRating']
            metadata['mediatype'] = "movie"
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'MusicVideo':
            metadata['mediatype'] = "musicvideo"
            metadata['album'] = obj['Album']
            metadata['artist'] = obj['Artists'] or []
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'Episode':
            metadata['mediatype'] = "episode"
            metadata['tvshowtitle'] = obj['SeriesName']
            metadata['season'] = obj['Season'] or 0
            metadata['sortseason'] = obj['Season'] or 0
            metadata['episode'] = obj['Index'] or 0
            metadata['sortepisode'] = obj['Index'] or 0
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
            art['tvshow.poster'] = "Series.Primary"
            art['tvshow.clearart'] = "Art"
            art['tvshow.clearlogo'] = "Logo"
        elif item['Type'] == 'Season':
            metadata['mediatype'] = "season"
            metadata['tvshowtitle'] = obj['SeriesName']
            metadata['season'] = obj['Index'] or 0
            metadata['sortseason'] = obj['Index'] or 0
            Properties['NumEpisodes'] = str(obj['RecursiveCount'])
            Properties['WatchedEpisodes'] = str(obj['RecursiveCount'] - obj['Unwatched'])
            Properties['UnWatchedEpisodes'] = str(obj['Unwatched'])
            Properties['IsFolder'] = 'true'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'Series':
            metadata['mediatype'] = "tvshow"
            metadata['tvshowtitle'] = obj['Title']
            metadata['status'] = obj['Status']
            Properties['TotalSeasons'] = str(obj['ChildCount'])
            Properties['TotalEpisodes'] = str(obj['RecursiveCount'])
            Properties['WatchedEpisodes'] = str(obj['RecursiveCount'] - obj['Unwatched'])
            Properties['UnWatchedEpisodes'] = str(obj['Unwatched'])
            Properties['IsFolder'] = 'true'
            Properties['IsPlayable'] = 'true'
            Folder = True
            art['poster'] = "Primary"
        elif item['Type'] == 'Video':
            metadata['mediatype'] = "video"
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'Boxset':
            metadata['mediatype'] = "set"
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'Trailer':
            metadata['mediatype'] = "video"
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'
            art['poster'] = "Primary"
        elif item['Type'] == 'Folder':
            Properties['IsFolder'] = 'true'
            Properties['IsPlayable'] = 'true'
            Folder = True
            art['poster'] = "Primary"

        if not Folder:
            Properties['resumetime'] = obj['Resume']

            for track in obj['Streams']['video']:
                listitem.addStreamInfo('video', {
                    'duration': obj['Runtime'],
                    'aspect': track['aspect'],
                    'codec': track['codec'],
                    'width': track['width'],
                    'height': track['height']
                })

            for track in obj['Streams']['audio']:
                listitem.addStreamInfo('audio', {'codec': track['codec'], 'channels': track['channels']})

            for track in obj['Streams']['subtitle']:
                listitem.addStreamInfo('subtitle', {'language': track})

        listitem.setInfo('video', metadata)
    elif item['Type'] in ("Music", "Audio", "MusicAlbum", "MusicArtist", "Artist", "MusicGenre"):
        obj = Objects.mapitem(item, 'BrowseAudio')
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'ArtworkMusic'), True, server_id)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Rating'] = obj['Rating'] or 0
        obj['DateAdded'], obj['FileDate'] = Common.get_DateAdded(obj['DateAdded'])
        metadata = {
            'title': obj['Title'],
            'genre': obj['Genre'],
            'year': obj['Year'],
            'album': obj['Album'],
            'artist': obj['Artists'],
            'rating': obj['Rating'],
            'comment': obj['Comment']
        }

        if obj['FileDate']:
            metadata['date'] = obj['DateAdded']

        if item['Type'] == 'Music':
            metadata['mediatype'] = "music"
        elif item['Type'] == 'Audio':
            metadata['mediatype'] = "song"
            metadata['tracknumber'] = obj['Index']
            metadata['discnumber'] = obj['Disc']
            metadata['duration'] = obj['Runtime']
            metadata['playcount'] = obj['PlayCount']
            metadata['lastplayed'] = obj['DatePlayed']
            metadata['musicbrainztrackid'] = obj['UniqueId']
            Properties['IsPlayable'] = 'true'
            Properties['IsFolder'] = 'false'
        elif item['Type'] == 'MusicAlbum':
            metadata['mediatype'] = "album"
            metadata['musicbrainzalbumid'] = obj['UniqueId']
            Properties['IsFolder'] = 'true'
        elif item['Type'] in ("MusicArtist", "Artist"):
            metadata['mediatype'] = "artist"
            metadata['musicbrainzartistid'] = obj['UniqueId']
            Properties['IsFolder'] = 'true'

        listitem.setInfo('music', metadata)
    elif item['Type'] in ("Photo", "PhotoAlbum"):
        obj = Objects.mapitem(item, 'BrowsePhoto')
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, server_id)
        obj['Overview'] = Common.get_overview(obj['Overview'], item)
        obj['DateAdded'], obj['FileDate'] = Common.get_DateAdded(obj['DateAdded'])
        metadata = {
            'title': obj['Title'],
            'picturepath': obj['Artwork']['Primary'],
            'exif:width': str(obj.get('Width', 0)),
            'exif:height': str(obj.get('Height', 0)),
            'size': obj['Size'],
            'exif:cameramake': obj['CameraMake'],
            'exif:cameramodel': obj['CameraModel'],
            'exif:exposuretime': str(obj['ExposureTime']),
            'exif:focallength': str(obj['FocalLength'])
        }

        if obj['FileDate']:
            metadata['date'] = obj['DateAdded']

        if item['Type'] == 'Photo':
            Properties['IsFolder'] = 'false'
        else:
            Properties['IsFolder'] = 'true'

        Properties['plot'] = obj['Overview']
        Properties['IsPlayable'] = 'false'
        listitem.setInfo('pictures', metadata)
    elif item['Type'] == 'Playlist':
        obj = Objects.mapitem(item, 'BrowseFolder')
        metadata = {'title': obj['Title']}
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, server_id)
        Properties['IsFolder'] = 'true'
        Properties['IsPlayable'] = 'false'
        listitem.setInfo('video', metadata)
    elif item['Type'] == 'TvChannel':
        obj = Objects.mapitem(item, 'BrowseChannel')
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, server_id)
        obj['Title'] = "%s - %s" % (obj['Title'], obj['ProgramName'])
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6

        if 'Primary' not in obj['Artwork']:
            obj['Artwork']['Primary'] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        if 'Thumb' not in obj['Artwork']:
            obj['Artwork']['Thumb'] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        if 'Backdrop' not in obj:
            obj['Artwork']['Backdrop'] = ["special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg"]
        else:

            if 'Thumb' not in obj['Backdrop']:
                obj['Artwork']['Backdrop'] = ["special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg"]

        metadata = {'title': obj['Title'], 'originaltitle': obj['Title'], 'playcount': obj['PlayCount'], 'overlay': obj['Overlay']}
        Properties['totaltime'] = str(obj['Runtime'])
        Properties['IsFolder'] = 'false'
        Properties['IsPlayable'] = 'true'
        listitem.setInfo('video', metadata)
    else:
        return listitem

    if Properties:
        listitem.setProperties(Properties)

    if obj['Artwork']:
        ArtworkData = {}

        for kodi, emby in list(art.items()):
            if emby == 'Backdrop':
                ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
            else:
                if emby in obj['Artwork']:
                    ArtworkData[kodi] = obj['Artwork'][emby]

        listitem.setArt(ArtworkData)

    listitem.setLabel(obj['Title'])
    listitem.setContentLookup(False)

    if 'People' in obj:
        if obj['People']:
            listitem.setCast(Common.get_actors(obj['People'], server_id))

    return listitem

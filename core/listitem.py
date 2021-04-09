# -*- coding: utf-8 -*-
import xbmcgui

import helper.api
import helper.loghandler
from . import obj_ops

class ListItem():
    def __init__(self, ssl, Utils):
        self.objects = obj_ops.Objects(Utils)
        self.API = helper.api.API(Utils, ssl)

    def set(self, item, listitem, db_id, seektime):
        listitem = listitem or xbmcgui.ListItem()
        Properties = {}
        ArtworkData = {}

        if item['Type'] in ("Movie", "MusicVideo", 'Episode', 'Season', 'Series', 'Video', 'BoxSet', 'AudioBook', 'Folder', 'Trailer'):
            obj = self.objects.map(item, 'BrowseVideo')
            obj['Artwork'] = self.API.get_all_artwork(self.objects.map(item, 'ArtworkParent'), True)
            obj['Genres'] = " / ".join(obj['Genres'] or [])
            obj['Studios'] = [self.API.validate_studio(studio) for studio in (obj['Studios'] or [])]
            obj['Studios'] = " / ".join(obj['Studios'])
            obj['Mpaa'] = self.API.get_mpaa(obj['Mpaa'], item)
            obj['People'] = obj['People'] or []
            obj['Countries'] = " / ".join(obj['Countries'] or [])
            obj['Directors'] = " / ".join(obj['Directors'] or [])
            obj['Writers'] = " / ".join(obj['Writers'] or [])
            obj['Plot'] = self.API.get_overview(obj['Plot'], item)
            obj['ShortPlot'] = self.API.get_overview(obj['ShortPlot'], item)
            obj['DateAdded'] = obj['DateAdded'].split('.')[0].replace('T', " ")
            obj['Rating'] = obj['Rating'] or 0
            obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['DateAdded'].split('T')[0].split('-')))
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['Resume'] = self.API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
            obj['PlayCount'] = self.API.get_playcount(obj['Played'], obj['PlayCount']) or 0
            obj['Overlay'] = 7 if obj['Played'] else 6
            obj['Video'] = self.API.video_streams(obj['Video'] or [], obj['Container'], item)
            obj['Audio'] = self.API.audio_streams(obj['Audio'] or [])
            obj['Streams'] = self.API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
            obj['ChildCount'] = obj['ChildCount'] or 0
            obj['RecursiveCount'] = obj['RecursiveCount'] or 0
            obj['Unwatched'] = obj['Unwatched'] or 0
            obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or []
            obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or ""
            obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

            if obj['Premiere']:
                obj['Premiere'] = obj['Premiere'].split('T')[0]

            if obj['DatePlayed']:
                obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

            if obj['Status'] != 'Ended':
                obj['Status'] = None

            Folder = False
            Properties['totaltime'] = str(obj['Runtime'])
            art = {
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
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
                'votes': obj['Votes'],
                'dateadded': obj['DateAdded'],
                'date': obj['Premiere'] or obj['FileDate'],
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime'],
                'aired': obj['Year']
            }

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
                art['poster'] = "Series.Primary"
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

            if db_id:
                metadata['dbid'] = db_id

            if not Folder:
                if obj['Resume'] and obj['Runtime'] and seektime != False:
                    Properties['resumetime'] = str(obj['Resume'])
                    Properties['StartPercent'] = str(((obj['Resume'] / obj['Runtime']) * 100))
                else:
                    Properties['resumetime'] = '0'
                    Properties['StartPercent'] = '0'

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

            for kodi, emby in list(art.items()):
                if emby == 'Backdrop':
                    ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
                else:
                    ArtworkData[kodi] = obj['Artwork'].get(emby, " ")

            listitem.setInfo('video', metadata)
        elif item['Type'] in ("Music", "Audio", "MusicAlbum", "MusicArtist", "Artist"):
            obj = self.objects.map(item, 'BrowseAudio')
            obj['Artwork'] = self.API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['PlayCount'] = self.API.get_playcount(obj['Played'], obj['PlayCount']) or 0
            obj['Rating'] = obj['Rating'] or 0
            obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['DateAdded'].split('T')[0].split('-')))
            art = {
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
            metadata = {
                'title': obj['Title'],
                'genre': obj['Genre'],
                'year': obj['Year'],
                'album': obj['Album'],
                'artist': obj['Artists'],
                'rating': obj['Rating'],
                'comment': obj['Comment'],
                'date': obj['FileDate'],
            }

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
            elif item['Type'] in ("MusicArtist", "Artist"):
                metadata['mediatype'] = "artist"
                metadata['musicbrainzartistid'] = obj['UniqueId']

            for kodi, emby in list(art.items()):
                if emby == 'Backdrop':
                    ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
                else:
                    ArtworkData[kodi] = obj['Artwork'].get(emby, " ")

            listitem.setInfo('music', metadata)
        elif item['Type'] in ("Photo", "PhotoAlbum"):
            obj = self.objects.map(item, 'BrowsePhoto')
            obj['Artwork'] = self.API.get_all_artwork(self.objects.map(item, 'Artwork'), False)
            obj['Overview'] = self.API.get_overview(obj['Overview'], item)
            obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['DateAdded'].split('T')[0].split('-')))
            art = {
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
            metadata = {
                'title': obj['Title'],
                'picturepath': obj['Artwork']['Primary'],
                'date': obj['FileDate'],
                'exif:width': str(obj.get('Width', 0)),
                'exif:height': str(obj.get('Height', 0)),
                'size': obj['Size'],
                'exif:cameramake': obj['CameraMake'],
                'exif:cameramodel': obj['CameraModel'],
                'exif:exposuretime': str(obj['ExposureTime']),
                'exif:focallength': str(obj['FocalLength'])
            }

            if item['Type'] == 'Photo':
                Properties['IsFolder'] = 'false'
            else:
                Properties['IsFolder'] = 'true'

            Properties['path'] = obj['Artwork']['Primary']
            Properties['plot'] = obj['Overview']
            Properties['IsPlayable'] = 'false'

            for kodi, emby in list(art.items()):
                if emby == 'Backdrop':
                    ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
                else:
                    ArtworkData[kodi] = obj['Artwork'].get(emby, " ")

            listitem.setInfo('pictures', metadata)
        elif item['Type'] == 'Playlist':
            obj = self.objects.map(item, 'BrowseFolder')
            obj['Artwork'] = self.API.get_all_artwork(self.objects.map(item, 'Artwork'), False)
            Properties['path'] = obj['Artwork']['Primary']
            Properties['IsFolder'] = 'true'
            Properties['IsPlayable'] = 'false'
            art = {
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }

            for kodi, emby in list(art.items()):
                if emby == 'Backdrop':
                    ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
                else:
                    ArtworkData[kodi] = obj['Artwork'].get(emby, " ")
        elif item['Type'] == 'TvChannel':
            obj = self.objects.map(item, 'BrowseChannel')
            obj['Artwork'] = self.API.get_all_artwork(self.objects.map(item, 'Artwork'), False)
            obj['Title'] = "%s - %s" % (obj['Title'], obj['ProgramName'])
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['PlayCount'] = self.API.get_playcount(obj['Played'], obj['PlayCount']) or 0
            obj['Overlay'] = 7 if obj['Played'] else 6
            obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"
            obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"
            obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or ["special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg"]
            metadata = {
                'title': obj['Title'],
                'originaltitle': obj['Title'],
                'playcount': obj['PlayCount'],
                'overlay': obj['Overlay']
            }
            art = {
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
            Properties['totaltime'] = str(obj['Runtime'])
            Properties['IsFolder'] = 'false'
            Properties['IsPlayable'] = 'true'

            for kodi, emby in list(art.items()):
                if emby == 'Backdrop':
                    ArtworkData[kodi] = obj['Artwork'][emby][0] if obj['Artwork'][emby] else ""
                else:
                    ArtworkData[kodi] = obj['Artwork'].get(emby, " ")

            listitem.setInfo('video', metadata)

        if Properties:
            listitem.setProperties(Properties)

        listitem.setArt(ArtworkData)
        listitem.setLabel(obj['Title'])
        listitem.setContentLookup(False)
        return listitem

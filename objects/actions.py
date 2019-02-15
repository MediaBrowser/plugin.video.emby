# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading
import sys
from datetime import timedelta

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

import database
from downloader import TheVoid
from obj import Objects
from helper import _, playutils, api, window, settings, dialog, JSONRPC
from dialogs import resume
from emby import Emby
from utils import get_play_action

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Actions(object):

    def __init__(self, server_id=None, server=None, *args, **kwargs):

        self.server_id = server_id or None
        self.server = server or TheVoid('GetServerAddress', {'ServerId': self.server_id}).get()
        self.stack = []

    def get_playlist(self, item, *args, **kwargs):

        if item['Type'] == 'Audio':
            return xbmc.PlayList(xbmc.PLAYLIST_MUSIC)

        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)


    def detect_playlist(self, item, *args, **kwargs):

        ''' Sometimes it's required to clear the playlist to get everything working together.
            Otherwise "Play from here" and cinema mode is going to break.
        '''
        playlist_items = self.get_playlist(item).size()

        ''' Do not clear playlist for audio items at all
        '''
        if item['Type'] == 'Audio':
            return False

        ''' Clear the playlist if the user starts a new playback from the GUI and there is still
            an existing one set.
        '''
        if xbmc.getCondVisibility('Player.HasMedia + !Window.IsVisible(fullscreenvideo)') and int(playlist_items) > 0:
            # ANGEL --SUALFRED: CHANGED
            return False

        ''' Clear the pseudo-playlist that has been created by the library windows for a single
            video item. This is required to get the cinema mode working.
        '''
        if not int(playlist_items) > 1:
            return True

        return False

    def playlist_position(self, item, *args, **kwargs):

        kodi_playlist = self.get_playlist(item)
        return kodi_playlist.getposition()

    def play(self, item, db_id=None, transcode=False, playlist=False, *args, **kwargs):

        window('emby.context.widget', clear=True)
        clear_playlist = self.detect_playlist(item)

        if clear_playlist:
            self.get_playlist(item).clear()

        play_action = get_play_action()
        listitem = xbmcgui.ListItem()
        LOG.info("[ play/%s ] %s", item['Id'], item['Name'])

        transcode = transcode or settings('playFromTranscode.bool')
        kodi_playlist = self.get_playlist(item)
        play = playutils.PlayUtils(item, transcode, self.server_id, self.server)
        source = play.select_source(play.get_sources())
        play.set_external_subs(source, listitem)

        self.set_playlist(item, listitem, db_id, transcode)
        index = max(kodi_playlist.getposition(), 0) + 1 # Can return -1

        self.stack[0][1].setPath(self.stack[0][0])

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, self.stack[0][1])

        if clear_playlist:
            xbmc.Player().play(kodi_playlist, startpos=index, windowed=False)
        else:
            self.stack.pop(0)

        for stack in self.stack:
            kodi_playlist.add(url=stack[0], listitem=stack[1], index=index)
            index += 1

        self.verify_playlist()

    @classmethod
    def verify_playlist(cls):
        LOG.info(JSONRPC('Playlist.GetItems').execute({'playlistid': 1}))

    @classmethod
    def add_to_playlist(cls, db_id=None, media_type=None, url=None, *args, **kwargs):

        params = {
            'playlistid': 1
        }
        params['item'] = {'%sid' % media_type: int(db_id)} if db_id is not None else {'file': url}
        LOG.info(JSONRPC('Playlist.Add').execute(params))

    @classmethod
    def insert_to_playlist(cls, position, db_id=None, media_type=None, url=None, *args, **kwargs):

        params = {
            'playlistid': 1,
            'position': position
        }
        params['item'] = {'%sid' % media_type: int(db_id)} if db_id is not None else {'file': url}
        LOG.info(JSONRPC('Playlist.Insert').execute(params))

    def set_playlist(self, item, listitem, db_id=None, transcode=False, *args, **kwargs):

        ''' Verify seektime, set intros, set main item and set additional parts.
            Detect the seektime for video type content.
            Verify the default video action set in Kodi for accurate resume behavior.
        '''
        seektime = window('emby.resume.bool')
        window('emby.resume', clear=True)

        if item['MediaType'] in ('Video', 'Audio'):
            resume = item['UserData'].get('PlaybackPositionTicks')

            if resume:
                """
                if get_play_action() == "Resume":
                    seektime = True

                if transcode and not seektime and not window('emby.context.widget.bool'):
                    choice = self.resume_dialog(api.API(item, self.server).adjust_resume((resume or 0) / 10000000.0))

                    if choice is None:
                        raise Exception("User backed out of resume dialog.")

                    seektime = False if not choice else True
                """
                choice = self.resume_dialog(api.API(item, self.server).adjust_resume((resume or 0) / 10000000.0), item)

                if choice is None:
                    raise Exception("User backed out of resume dialog.")

                seektime = False if not choice else True

        playlist_pos = self.playlist_position(item)
        if settings('enableCinema.bool') and not seektime and not int(playlist_pos) > 0:
            self._set_intros(item)

        self.set_listitem(item, listitem, db_id, seektime)
        playutils.set_properties(item, item['PlaybackInfo']['Method'], self.server_id)
        self.stack.append([item['PlaybackInfo']['Path'], listitem, item['Id'], db_id])

        if item.get('PartCount'):
            self._set_additional_parts(item['Id'])

    def _set_intros(self, item, *args, **kwargs):

        ''' if we have any play them when the movie/show is not being resumed.
        '''
        intros = TheVoid('GetIntros', {'ServerId': self.server_id, 'Id': item['Id']}).get()

        if intros['Items']:
            enabled = True

            if settings('askCinema') == "true":

                resp = dialog("yesno", heading="{emby}", line1=_(33016))
                if not resp:

                    enabled = False
                    LOG.info("Skip trailers.")

            if enabled:
                for intro in intros['Items']:

                    listitem = xbmcgui.ListItem()
                    LOG.info("[ intro/%s ] %s", intro['Id'], intro['Name'])

                    play = playutils.PlayUtils(intro, False, self.server_id, self.server)
                    source = play.select_source(play.get_sources())
                    self.set_listitem(intro, listitem, intro=True)
                    listitem.setPath(intro['PlaybackInfo']['Path'])
                    playutils.set_properties(intro, intro['PlaybackInfo']['Method'], self.server_id)

                    self.stack.append([intro['PlaybackInfo']['Path'], listitem, intro['Id'], None])

                window('emby.skip.%s' % intro['Id'], value="true")

    def _set_additional_parts(self, item_id, *args, **kwargs):

        ''' Create listitems and add them to the stack of playlist.
        '''
        parts = TheVoid('GetAdditionalParts', {'ServerId': self.server_id, 'Id': item_id}).get()

        for part in parts['Items']:

            listitem = xbmcgui.ListItem()
            LOG.info("[ part/%s ] %s", part['Id'], part['Name'])

            play = playutils.PlayUtils(part, False, self.server_id, self.server)
            source = play.select_source(play.get_sources())
            play.set_external_subs(source, listitem)
            self.set_listitem(part, listitem)
            listitem.setPath(part['PlaybackInfo']['Path'])
            playutils.set_properties(part, part['PlaybackInfo']['Method'], self.server_id)

            self.stack.append([part['PlaybackInfo']['Path'], listitem, part['Id'], None])

    def play_playlist(self, items, clear=True, seektime=None, audio=None, subtitle=None, *args, **kwargs):

        ''' Play a list of items. Creates a new playlist. Add additional items as plugin listing.
        '''
        item = items['Items'][0]
        playlist = self.get_playlist(item)
        player = xbmc.Player()

        #xbmc.executebuiltin("Playlist.Clear") # Clear playlist to remove the previous item from playlist position no.2

        if clear:
            if player.isPlaying():
                player.stop()

            xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
            index = 0
        else:
            index = max(playlist.getposition(), 0) + 1 # Can return -1

        listitem = xbmcgui.ListItem()
        LOG.info("[ playlist/%s ] %s", item['Id'], item['Name'])

        play = playutils.PlayUtils(item, False, self.server_id, self.server)
        source = play.select_source(play.get_sources())
        play.set_external_subs(source, listitem)

        item['PlaybackInfo']['AudioStreamIndex'] = audio or item['PlaybackInfo']['AudioStreamIndex']
        item['PlaybackInfo']['SubtitleStreamIndex'] = subtitle or item['PlaybackInfo'].get('SubtitleStreamIndex')

        self.set_listitem(item, listitem, None, True if seektime else False)
        listitem.setPath(item['PlaybackInfo']['Path'])
        playutils.set_properties(item, item['PlaybackInfo']['Method'], self.server_id)

        playlist.add(item['PlaybackInfo']['Path'], listitem, index)
        index += 1

        if clear:
            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
            player.play(playlist)

        for item in items['Items'][1:]:
            listitem = xbmcgui.ListItem()
            LOG.info("[ playlist/%s ] %s", item['Id'], item['Name'])

            self.set_listitem(item, listitem, None, False)
            path = "plugin://plugin.video.emby/?mode=play&id=%s&playlist=true" % item['Id']
            listitem.setPath(path)

            playlist.add(path, listitem, index)
            index += 1

    def set_listitem(self, item, listitem, db_id=None, seektime=None, intro=False, *args, **kwargs):

        objects = Objects()
        API = api.API(item, self.server)

        if item['Type'] in ('MusicArtist', 'MusicAlbum', 'Audio'):

            obj = objects.map(item, 'BrowseAudio')
            obj['DbId'] = db_id
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'ArtworkMusic'), True)
            self.listitem_music(obj, listitem, item)

        elif item['Type'] in ('Photo', 'PhotoAlbum'):

            obj = objects.map(item, 'BrowsePhoto')
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'Artwork'))
            self.listitem_photo(obj, listitem, item)

        elif item['Type'] in ('Playlist'):

            obj = objects.map(item, 'BrowseFolder')
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'Artwork'))
            self.listitem_folder(obj, listitem, item)

        elif item['Type'] in ('TvChannel'):

            obj = objects.map(item, 'BrowseChannel')
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'Artwork'))
            self.listitem_channel(obj, listitem, item)

        else:
            obj = objects.map(item, 'BrowseVideo')
            obj['DbId'] = db_id
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'ArtworkParent'), True)

            self.listitem_video(obj, listitem, item, seektime, intro)

            if 'PlaybackInfo' in item:

                if seektime:
                    item['PlaybackInfo']['CurrentPosition'] = obj['Resume']

                if 'SubtitleUrl' in item['PlaybackInfo']:

                    #LOG.info("[ subtitles ] %s", item['PlaybackInfo']['SubtitleUrl'])
                    listitem.setSubtitles([item['PlaybackInfo']['SubtitleUrl']])

                if item['Type'] == 'Episode':

                    item['PlaybackInfo']['CurrentEpisode'] = objects.map(item, "UpNext")
                    item['PlaybackInfo']['CurrentEpisode']['art'] = {
                        'tvshow.poster': obj['Artwork'].get('Series.Primary'),
                        'thumb': obj['Artwork'].get('Primary'),
                        'tvshow.fanart': None
                    }
                    if obj['Artwork']['Backdrop']:
                        item['PlaybackInfo']['CurrentEpisode']['art']['tvshow.fanart'] = obj['Artwork']['Backdrop'][0]

        listitem.setContentLookup(False)

    def listitem_video(self, obj, listitem, item, seektime=None, intro=False, *args, **kwargs):

        ''' Set listitem for video content. That also include streams.
        '''
        API = api.API(item, self.server)
        is_video = obj['MediaType'] in ('Video', 'Audio') # audiobook

        obj['Genres'] = " / ".join(obj['Genres'] or [])
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Studios'] = " / ".join(obj['Studios'])
        obj['Mpaa'] = API.get_mpaa(obj['Mpaa'])
        obj['People'] = obj['People'] or []
        obj['Countries'] = " / ".join(obj['Countries'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['ShortPlot'] = API.get_overview(obj['ShortPlot'])
        obj['DateAdded'] = obj['DateAdded'].split('.')[0].replace('T', " ")
        obj['Rating'] = obj['Rating'] or 0
        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['DateAdded'].split('T')[0].split('-')))
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['ChildCount'] = obj['ChildCount'] or 0
        obj['RecursiveCount'] = obj['RecursiveCount'] or 0
        obj['Unwatched'] = obj['Unwatched'] or 0
        obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or []
        obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or ""

        if not intro and not obj['Type'] == 'Trailer':
            obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/icon.png"
        else:
            obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or obj['Artwork']['Thumb'] or (obj['Artwork']['Backdrop'][0] if len(obj['Artwork']['Backdrop']) else "special://home/addons/plugin.video.emby/fanart.jpg")
            obj['Artwork']['Primary'] += "&KodiTrailer=true" if obj['Type'] == 'Trailer' else "&KodiCinemaMode=true"
            obj['Artwork']['Backdrop'] = [obj['Artwork']['Primary']]

        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if intro or obj['Type'] == 'Trailer':
            listitem.setArt({'poster': ""}) # Clear the poster value for intros / trailers to prevent issues in skins

        listitem.setIconImage('DefaultVideo.png')
        listitem.setThumbnailImage(obj['Artwork']['Primary'])

        if obj['Premiere']:
            obj['Premiere'] = obj['Premiere'].split('T')[0]

        if obj['DatePlayed']:
            obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

        metadata = {
            'title': obj['Title'],
            'originaltitle': obj['Title'],
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
            'aired': obj['Year'],
            'date': obj['FileDate'],
            'dbid': obj['DbId']
        }
        listitem.setCast(API.get_actors())

        if obj['Premiere']:
            metadata['date'] = obj['Premiere']

        if obj['Type'] == 'Episode':
            metadata.update({
                'mediatype': "episode",
                'tvshowtitle': obj['SeriesName'],
                'season': obj['Season'] or 0,
                'sortseason': obj['Season'] or 0,
                'episode': obj['Index'] or 0,
                'sortepisode': obj['Index'] or 0,
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime'],
                'aired': obj['Premiere'],
            })

        elif obj['Type'] == 'Season':
            metadata.update({
                'mediatype': "season",
                'tvshowtitle': obj['SeriesName'],
                'season': obj['Index'] or 0,
                'sortseason': obj['Index'] or 0
            })
            listitem.setProperty('NumEpisodes', str(obj['RecursiveCount']))
            listitem.setProperty('WatchedEpisodes', str(obj['RecursiveCount'] - obj['Unwatched']))
            listitem.setProperty('UnWatchedEpisodes', str(obj['Unwatched']))
            listitem.setProperty('IsFolder', 'true')

        elif obj['Type'] == 'Series':

            if obj['Status'] != 'Ended':
                obj['Status'] = None

            metadata.update({
                'mediatype': "tvshow",
                'tvshowtitle': obj['Title'],
                'status': obj['Status']
            })
            listitem.setProperty('TotalSeasons', str(obj['ChildCount']))
            listitem.setProperty('TotalEpisodes', str(obj['RecursiveCount']))
            listitem.setProperty('WatchedEpisodes', str(obj['RecursiveCount'] - obj['Unwatched']))
            listitem.setProperty('UnWatchedEpisodes', str(obj['Unwatched']))
            listitem.setProperty('IsFolder', 'true')

        elif obj['Type'] == 'Movie':
            metadata.update({
                'mediatype': "movie",
                'imdbnumber': obj['UniqueId'],
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime'],
                'userrating': obj['CriticRating']
            })

        elif obj['Type'] == 'MusicVideo':
            metadata.update({
                'mediatype': "musicvideo",
                'album': obj['Album'],
                'artist': obj['Artists'] or [],
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime']
            })

        elif obj['Type'] == 'BoxSet':
            metadata['mediatype'] = "set"
            listitem.setProperty('IsFolder', 'true')
        else:
            metadata.update({
                'mediatype': "video",
                'lastplayed': obj['DatePlayed'],
                'year': obj['Year'],
                'duration': obj['Runtime']
            })

        if is_video:

            listitem.setProperty('totaltime', str(obj['Runtime']))
            listitem.setProperty('IsPlayable', 'true')
            listitem.setProperty('IsFolder', 'false')

            if obj['Resume'] and seektime != False:

                listitem.setProperty('resumetime', str(obj['Resume']))
                listitem.setProperty('StartPercent', str(((obj['Resume']/obj['Runtime']) * 100)))
            else:
                ''' StartPercent to trick Kodi Leia into seeking to the beginning for library content.
                    If value set to 0, it seems to ignore and resume anyway. StartOffset is broken.
                '''
                listitem.setProperty('resumetime', '0')
                listitem.setProperty('StartPercent', '0')

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

        listitem.setLabel(obj['Title'])
        listitem.setInfo('video', metadata)
        listitem.setContentLookup(False)

    def listitem_channel(self, obj, listitem, item, *args, **kwargs):

        ''' Set listitem for channel content.
        '''
        API = api.API(item, self.server)

        obj['Title'] = "%s - %s" % (obj['Title'], obj['ProgramName'])
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6
        obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/icon.png"
        obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or "special://home/addons/plugin.video.emby/fanart.jpg"
        obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or ["special://home/addons/plugin.video.emby/fanart.jpg"]


        metadata = {
            'title': obj['Title'],
            'originaltitle': obj['Title'],
            'playcount': obj['PlayCount'],
            'overlay': obj['Overlay']
        }
        listitem.setIconImage(obj['Artwork']['Thumb'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])
        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if obj['Artwork']['Primary']:
            listitem.setThumbnailImage(obj['Artwork']['Primary'])

        if not obj['Artwork']['Backdrop']:
            listitem.setArt({'fanart': obj['Artwork']['Primary']})

        listitem.setProperty('totaltime', str(obj['Runtime']))
        listitem.setProperty('IsPlayable', 'true')
        listitem.setProperty('IsFolder', 'false')

        listitem.setLabel(obj['Title'])
        listitem.setInfo('video', metadata)
        listitem.setContentLookup(False)

    def listitem_music(self, obj, listitem, item, *args, **kwargs):
        API = api.API(item, self.server)

        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Rating'] = obj['Rating'] or 0

        if obj['FileDate'] or obj['DatePlayed']:
            obj['DatePlayed'] = (obj['DatePlayed'] or obj['FileDate']).split('.')[0].replace('T', " ")

        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['FileDate'].split('T')[0].split('-')))

        metadata = {
            'title': obj['Title'],
            'genre': obj['Genre'],
            'year': obj['Year'],
            'album': obj['Album'],
            'artist': obj['Artists'],
            'rating': obj['Rating'],
            'comment': obj['Comment'],
            'date': obj['FileDate']
        }
        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if obj['Type'] == 'Audio':
            metadata.update({
                'mediatype': "song",
                'tracknumber': obj['Index'],
                'discnumber': obj['Disc'],
                'duration': obj['Runtime'],
                'playcount': obj['PlayCount'],
                'lastplayed': obj['DatePlayed'],
                'musicbrainztrackid': obj['UniqueId']
            })
            listitem.setProperty('IsPlayable', 'true')
            listitem.setProperty('IsFolder', 'false')

        elif obj['Type'] == 'Album':
            metadata.update({
                'mediatype': "album",
                'musicbrainzalbumid': obj['UniqueId']
            })

        elif obj['Type'] in ('Artist', 'MusicArtist'):
            metadata.update({
                'mediatype': "artist",
                'musicbrainzartistid': obj['UniqueId']
            })
        else:
            metadata['mediatype'] = "music"

        listitem.setLabel(obj['Title'])
        listitem.setInfo('music', metadata)
        listitem.setContentLookup(False)

    def listitem_photo(self, obj, listitem, item, *args, **kwargs):
        API = api.API(item, self.server)

        obj['Overview'] = API.get_overview(obj['Overview'])
        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['FileDate'].split('T')[0].split('-')))

        metadata = {
            'title': obj['Title']
        }
        listitem.setProperty('path', obj['Artwork']['Primary'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])

        if obj['Type'] == 'Photo':
            metadata.update({
                'picturepath': obj['Artwork']['Primary'],
                'date': obj['FileDate'],
                'exif:width': str(obj.get('Width', 0)),
                'exif:height': str(obj.get('Height', 0)),
                'size': obj['Size'],
                'exif:cameramake': obj['CameraMake'],
                'exif:cameramodel': obj['CameraModel'],
                'exif:exposuretime': str(obj['ExposureTime']),
                'exif:focallength': str(obj['FocalLength'])
            })
            listitem.setProperty('plot', obj['Overview'])
            listitem.setProperty('IsFolder', 'false')
            listitem.setIconImage('DefaultPicture.png')
        else:
            listitem.setProperty('IsFolder', 'true')
            listitem.setIconImage('DefaultFolder.png')

        listitem.setProperty('IsPlayable', 'false')
        listitem.setLabel(obj['Title'])
        listitem.setInfo('pictures', metadata)
        listitem.setContentLookup(False)

    def listitem_folder(self, obj, listitem, item, *args, **kwargs):
        API = api.API(item, self.server)

        obj['Overview'] = API.get_overview(obj['Overview'])

        metadata = {
            'title': obj['Title']
        }
        listitem.setProperty('path', obj['Artwork']['Primary'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])
        listitem.setProperty('IsFolder', 'true')
        listitem.setIconImage('DefaultFolder.png')

        listitem.setProperty('IsPlayable', 'false')
        listitem.setLabel(obj['Title'])
        listitem.setContentLookup(False)

    def set_artwork(self, artwork, listitem, media, *args, **kwargs):

        if media == 'Episode':

            art = {
                'poster': "Series.Primary",
                'tvshow.poster': "Series.Primary",
                'clearart': "Art",
                'tvshow.clearart': "Art",
                'clearlogo': "Logo",
                'tvshow.clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'tvshow.landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
        elif media in ('Artist', 'Audio', 'MusicAlbum'):

            art = {
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart': "Backdrop",
                'fanart_image': "Backdrop", # in case
                'thumb': "Primary"
            }
        else:
            art = {
                'poster': "Primary",
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }

        for k_art, e_art in art.items():

            if e_art == "Backdrop":
                self._set_art(listitem, k_art, artwork[e_art][0] if artwork[e_art] else " ")
            else:
                self._set_art(listitem, k_art, artwork.get(e_art, " "))

    def _set_art(self, listitem, art, path, *args, **kwargs):
        LOG.debug(" [ art/%s ] %s", art, path)

        if art in ('fanart_image', 'small_poster', 'tiny_poster',
                   'medium_landscape', 'medium_poster', 'small_fanartimage',
                   'medium_fanartimage', 'fanart_noindicators', 'discart',
                   'tvshow.poster'):

            listitem.setProperty(art, path)
        else:
            listitem.setArt({art: path})

    def resume_dialog(self, seektime, item, *args, **kwargs):

        ''' Skip resume of queued playlist items and start them from the beginning
        '''
        playlist_pos = self.playlist_position(item)
        if int(playlist_pos) > 0:
            LOG.info("[ playlist/position %s ] skip resume dialog" % playlist_pos)
            return False

        ''' Base resume dialog based on Kodi settings.
        '''
        LOG.info("Resume dialog called.")
        XML_PATH = (xbmcaddon.Addon('plugin.video.emby').getAddonInfo('path'), "default", "1080i")

        dialog = resume.ResumeDialog("script-emby-resume.xml", *XML_PATH)
        dialog.set_resume_point("Resume from %s" % str(timedelta(seconds=seektime)).split(".")[0])
        dialog.doModal()

        if dialog.is_selected():
            if not dialog.get_selected(): # Start from beginning selected.
                return False
        else: # User backed out
            LOG.info("User exited without a selection.")
            return

        return True


class PlaylistWorker(threading.Thread):

    def __init__(self, server_id, items, *args, **kwargs):

        self.server_id = server_id
        self.items = items
        self.args = args
        self.kwargs = kwargs
        threading.Thread.__init__(self)

    def run(self):
        Actions(self.server_id).play_playlist(self.items, *self.args, **self.kwargs)


def on_update(data, server, *args, **kwargs):

    ''' Only for manually marking as watched/unwatched
    '''
    reset_resume = False

    try:
        kodi_id = data['item']['id']
        media = data['item']['type']
        playcount = int(data.get('playcount', 0))
        LOG.info(" [ update/%s ] kodi_id: %s media: %s", playcount, kodi_id, media)
    except (KeyError, TypeError):

        if 'id' in data and 'type' in data and window('emby.context.resetresume.bool'):

            window('emby.context.resetresume', clear=True)
            kodi_id = data['id']
            media = data['type']
            playcount = 0
            reset_resume = True
            LOG.info("reset position detected [ %s/%s ]", kodi_id, media)
        else:
            LOG.debug("Invalid playstate update")

            return

    item = database.get_item(kodi_id, media)

    if item:

        if reset_resume:
            checksum = item[4]
            server['api'].item_played(item[0], False)

            if checksum:
                checksum = json.loads(checksum)
                if checksum['Played']:
                    server['api'].item_played(item[0], True)
        else:
            if not window('emby.skip.%s.bool' % item[0]):
                server['api'].item_played(item[0], playcount)

            window('emby.skip.%s' % item[0], clear=True)

def on_play(data, server, *args, **kwargs):

    ''' Setup progress for emby playback.
    '''
    player = xbmc.Player()

    try:
        kodi_id = None

        if player.isPlayingVideo():

            ''' Seems to misbehave when playback is not terminated prior to playing new content.
                The kodi id remains that of the previous title. Maybe onPlay happens before
                this information is updated. Added a failsafe further below.
            '''
            item = player.getVideoInfoTag()
            kodi_id = item.getDbId()
            media = item.getMediaType()

        if kodi_id is None or int(kodi_id) == -1 or 'item' in data and 'id' in data['item'] and data['item']['id'] != kodi_id:

            item = data['item']
            kodi_id = item['id']
            media = item['type']

        LOG.info(" [ play ] kodi_id: %s media: %s", kodi_id, media)

    except (KeyError, TypeError):
        LOG.debug("Invalid playstate update")

        return

    if settings('useDirectPaths') == '1' or media == 'song':
        item = database.get_item(kodi_id, media)

        if item:

            try:
                file = player.getPlayingFile()
            except Exception as error:
                LOG.error(error)

                return

            item = server['api'].get_item(item[0])
            item['PlaybackInfo'] = {'Path': file}
            playutils.set_properties(item, 'DirectStream' if settings('useDirectPaths') == '0' else 'DirectPlay')

def special_listener():

    ''' Corner cases that needs to be listened to.
        This is run in a loop within monitor.py
    '''
    player = xbmc.Player()
    isPlaying = player.isPlaying()

    if not isPlaying and xbmc.getCondVisibility('Window.IsVisible(DialogContextMenu.xml)'):
        control = int(xbmcgui.Window(10106).getFocusId())

        if xbmc.getInfoLabel('Control.GetLabel(1002)') == xbmc.getLocalizedString(12021):
            if control == 1002: # Start from beginning

                LOG.info("Resume dialog: Start from beginning selected.")
                window('emby.resume.bool', False)
                window('emby.context.widget.bool', True)
            elif control == 1001:

                LOG.info("Resume dialog: Resume selected.")
                window('emby.resume.bool', True)
                window('emby.context.widget.bool', True)
            elif control == 1005:

                LOG.info("Reset resume point selected.")
                window('emby.context.resetresume.bool', True)
            else:
                window('emby.resume', clear=True)
                window('emby.context.resetresume', clear=True)
                window('emby.context.widget', clear=True)
        else: # Item without a resume point
            if control == 1001:

                LOG.info("Play dialog selected.")
                window('emby.context.widget.bool', True)
            else:
                window('emby.context.widget', clear=True)

    elif isPlaying and not window('emby.external_check'):

        window('emby.external.bool', player.isExternalPlayer())
        window('emby.external_check.bool', True)

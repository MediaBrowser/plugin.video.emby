# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os

import xbmc
import xbmcgui
import xbmcvfs

from objects.obj import Objects
from helper import _, api, window, kodi_version, settings, dialog, event, silent_catch, JSONRPC
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Player(xbmc.Player):

    played = {}
    up_next = False

    def __init__(self, monitor=None):

        self.monitor = monitor
        xbmc.Player.__init__(self)

    @silent_catch()
    def get_playing_file(self):
        return self.getPlayingFile()

    @silent_catch()
    def get_file_info(self, file):
        return self.played[file]

    def is_playing_file(self, file):
        return file in self.played

    def is_current_file(self, file):
        return file == self.get_playing_file()

    def get_current_file(self, count=0):

        ''' Each count is approx 1s.
        '''
        try:
            return self.getPlayingFile()
        except Exception:

            while count > 0:
                try:
                    return self.getPlayingFile()
                except Exception:
                    count -= 1

                if self.monitor.waitForAbort(1):
                    return
            else:
                raise Exception("FileNotFound")

    def onAVStarted(self):
        LOG.info("[ onAVStarted ]")

    def onPlayBackStarted(self):

        ''' We may need to wait for info to be set in kodi monitor.
            Accounts for scenario where Kodi starts playback and exits immediately.
            First, ensure previous playback terminated correctly in Emby.
        '''
        LOG.info("[ onPlayBackStarted ]")
        self.up_next = False

        try:
            current_file = self.get_current_file(5)
        except Exception as error:
            LOG.error(error)

            return

        self.stop_playback()
        items = window('emby.play.json')
        item = None
        count = 0

        while not items:

            if self.monitor.waitForAbort(2):
                return

            items = window('emby.play.json')
            count += 1

            if count == 20:
                LOG.info("<[ emby.play empty ]")

                return

            if window('emby.play.reset.bool'):
                LOG.info("<[ reset play setup ]")

                return

        for item in items:
            if item['Path'] == current_file.decode('utf-8'):
                items.pop(items.index(item))

                break
        else:
            item = items.pop(0)

        window('emby.play.json', items)

        self.set_item(current_file, item)
        data = {
            'QueueableMediaTypes': "Video,Audio",
            'CanSeek': True,
            'ItemId': item['Id'],
            'MediaSourceId': item['MediaSourceId'],
            'PlayMethod': item['PlayMethod'],
            'VolumeLevel': item['Volume'],
            'PositionTicks': int(item['CurrentPosition'] * 10000000),
            'IsPaused': item['Paused'],
            'IsMuted': item['Muted'],
            'PlaySessionId': item['PlaySessionId'],
            'AudioStreamIndex': item['AudioStreamIndex'],
            'SubtitleStreamIndex': item['SubtitleStreamIndex']
        }
        item['Server']['api'].session_playing(data)
        window('emby.skip.%s.bool' % item['Id'], True)

        if self.monitor.waitForAbort(2):
            return

        if item['PlayOption'] == 'Addon' and kodi_version() < 18:
            self.set_audio_subs(item['AudioStreamIndex'], item['SubtitleStreamIndex'])

        item['Track'] = True

    def set_item(self, file, item):

        ''' Set playback information.
        '''
        try:
            item['Runtime'] = int(item['Runtime'])
        except (TypeError, ValueError):
            try:
                item['Runtime'] = int(self.getTotalTime())
                LOG.info("Runtime is missing, Kodi runtime: %s" % item['Runtime'])
            except Exception:
                item['Runtime'] = 0
                LOG.info("Runtime is missing, Using Zero")

        try:
            seektime = self.getTime()
        except Exception: # at this point we should be playing and if not then bail out
            return

        result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')

        item.update({
            'File': file,
            'CurrentPosition': item.get('CurrentPosition') or int(seektime),
            'Muted': muted,
            'Volume': volume,
            'Server': Emby(item['ServerId']).get_client(),
            'Paused': False,
            'Track': False
        })

        self.played[file] = item
        LOG.info("-->[ play/%s ] %s", item['Id'], item)

    def set_audio_subs(self, audio=None, subtitle=None):

        ''' Only for after playback started
        '''
        LOG.info("Setting audio: %s subs: %s", audio, subtitle)
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            item = self.get_file_info(current_file)
            mapping = item['SubsMapping']

            if audio and len(self.getAvailableAudioStreams()) > 1:
                self.setAudioStream(audio - 1)

            if subtitle == -1 or subtitle is None:
                self.showSubtitles(False)

                return

            tracks = len(self.getAvailableAudioStreams())

            if mapping:
                for index in mapping:

                    if mapping[index] == subtitle:
                        self.setSubtitleStream(int(index))

                        break
                else:
                    self.setSubtitleStream(len(mapping) + subtitle - tracks - 1)
            else:
                self.setSubtitleStream(subtitle - tracks - 1)

    def detect_audio_subs(self, item):

        params = {
            'playerid': self.monitor.playlistid,
            'properties': ["currentsubtitle","currentaudiostream","subtitleenabled"]
        }
        result = JSONRPC('Player.GetProperties').execute(params)
        result = result.get('result')

        try: # Audio tracks
            audio = result['currentaudiostream']['index']
        except (KeyError, TypeError):
            audio = 0
        
        try: # Subtitles tracks
            subs = result['currentsubtitle']['index']
        except (KeyError, TypeError):
            subs = 0

        try: # If subtitles are enabled
            subs_enabled = result['subtitleenabled']
        except (KeyError, TypeError):
            subs_enabled = False

        item['AudioStreamIndex'] = audio + 1

        if not subs_enabled or not len(self.getAvailableSubtitleStreams()):
            item['SubtitleStreamIndex'] = -1

            return

        mapping = item['SubsMapping']
        tracks = len(self.getAvailableAudioStreams())

        if mapping:
            if str(subs) in mapping:
                item['SubtitleStreamIndex'] = mapping[str(subs)]
            else:
                item['SubtitleStreamIndex'] = subs - len(mapping) + tracks + 1
        else:
            item['SubtitleStreamIndex'] = subs + tracks + 1

    def next_up(self):

        item = self.get_file_info(self.get_playing_file())
        objects = Objects()

        if item['Type'] != 'Episode' or not item.get('CurrentEpisode'):
            return

        next_items = item['Server']['api'].get_adjacent_episodes(item['CurrentEpisode']['tvshowid'], item['Id'])

        for index, next_item in enumerate(next_items['Items']):
            if next_item['Id'] == item['Id']:

                try:
                    next_item = next_items['Items'][index + 1]
                except IndexError:
                    LOG.warn("No next up episode.")

                    return

                break

        API = api.API(next_item, item['Server']['auth/server-address'])
        data = objects.map(next_item, "UpNext")
        artwork = API.get_all_artwork(objects.map(next_item, 'ArtworkParent'), True)
        data['art'] = {
            'tvshow.poster': artwork.get('Series.Primary'),
            'tvshow.fanart': None,
            'thumb': artwork.get('Primary')
        }
        if artwork['Backdrop']:
            data['art']['tvshow.fanart'] = artwork['Backdrop'][0]

        next_info = {
            'play_info': {'ItemIds': [data['episodeid']], 'ServerId': item['ServerId'], 'PlayCommand': 'PlayNow'},
            'current_episode': item['CurrentEpisode'],
            'next_episode': data
        }

        LOG.info("--[ next up ] %s", next_info)
        event("upnext_data", next_info, hexlify=True)

    def onPlayBackPaused(self):
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            self.get_file_info(current_file)['Paused'] = True
            self.report_playback()
            LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            self.get_file_info(current_file)['Paused'] = False
            self.report_playback()
            LOG.debug("--<[ paused ]")

    def onPlayBackSeek(self, time, seekOffset):

        ''' Does not seem to work in Leia??
        '''
        if self.is_playing_file(self.get_playing_file()):

            self.report_playback()
            LOG.info("--[ seek ]")

    def report_playback(self, report=True):

        ''' Report playback progress to emby server.
            Check if the user seek or any other basic changes happened.
        '''
        current_file = self.get_playing_file()

        if not self.is_playing_file(current_file):
            return

        item = self.get_file_info(current_file)
        orig_item = dict(item)

        if window('emby.external.bool'):
            return

        if not item['Track']:
            return

        result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        item['Volume'] = result.get('volume')
        item['Muted'] = result.get('muted')
        self.detect_audio_subs(item)

        if (not report and orig_item['AudioStreamIndex'] != item['AudioStreamIndex'] or
            orig_item['SubtitleStreamIndex'] != item['SubtitleStreamIndex'] or
            orig_item['Muted'] != item['Muted']) or orig_item['Volume'] != item['Volume']:

            report = True

        if not report:

            previous = item['CurrentPosition']
            item['CurrentPosition'] = int(self.getTime())

            if int(item['CurrentPosition']) == 1:
                return

            try:
                played = float(item['CurrentPosition'] * 10000000) / int(item['Runtime']) * 100
            except ZeroDivisionError: # Runtime is 0.
                played = 0

            if not self.up_next and played > 2.0:

                self.up_next = True
                self.next_up()

            if (item['CurrentPosition'] - previous) < 30:
                return
        else:
            current_time = int(self.getTime())

            if not current_time:
                count = 2

                while count:
                    file = self.get_playing_file()

                    if file != current_file:
                        LOG.info("<[ new play ]")

                        return

                    count -= 1

                    if self.monitor.waitForAbort(1):
                        return

            item['CurrentPosition'] = current_time

        data = {
            'QueueableMediaTypes': "Video,Audio",
            'CanSeek': True,
            'ItemId': item['Id'],
            'MediaSourceId': item['MediaSourceId'],
            'PlayMethod': item['PlayMethod'],
            'VolumeLevel': item['Volume'],
            'PositionTicks': int(item['CurrentPosition'] * 10000000),
            'IsPaused': item['Paused'],
            'IsMuted': item['Muted'],
            'PlaySessionId': item['PlaySessionId'],
            'AudioStreamIndex': item['AudioStreamIndex'],
            'SubtitleStreamIndex': item['SubtitleStreamIndex']
        }
        item['Server']['api'].session_progress(data)

    def onPlayBackStopped(self):

        ''' Will be called when user stops playing a file.
        '''
        self.stop_playback()
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):

        ''' Will be called when kodi stops playing a file.
        '''
        self.stop_playback()
        LOG.info("--<<[ playback ]")

    def stop_playback(self):

        ''' Stop all playback. Check for external player for positionticks.
        '''
        if not self.played:
            return

        LOG.info("[ played info ] %s", self.played)

        for file in dict(self.played):

            try:
                item = self.get_file_info(file)

                if not item['Track']:
                    LOG.info("[ skip stop ] %s", file)

                    continue

                self.played.pop(file, None)
                window('emby.skip.%s.bool' % item['Id'], True)

                if window('emby.external.bool'):
                    window('emby.external', clear=True)

                    if int(item['CurrentPosition']) == 1:
                        item['CurrentPosition'] = int(item['Runtime'])

                data = {
                    'ItemId': item['Id'],
                    'MediaSourceId': item['MediaSourceId'],
                    'PositionTicks': int(item['CurrentPosition'] * 10000000),
                    'PlaySessionId': item['PlaySessionId']
                }
                item['Server']['api'].session_stop(data)

                if item.get('LiveStreamId'):

                    LOG.info("<[ livestream/%s ]", item['LiveStreamId'])
                    item['Server']['api'].close_live_stream(item['LiveStreamId'])

                elif item['PlayMethod'] == 'Transcode':

                    LOG.info("<[ transcode/%s ]", item['Id'])
                    item['Server']['api'].close_transcode(item['DeviceId'])


                path = xbmc.translatePath("special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

                if xbmcvfs.exists(path):
                    dirs, files = xbmcvfs.listdir(path)

                    for file in files:
                        xbmcvfs.delete(os.path.join(path, file.decode('utf-8')))

                result = item['Server']['api'].get_item(item['Id']) or {}

                if 'UserData' in result and result['UserData']['Played']:
                    delete = False

                    if result['Type'] == 'Episode' and settings('deleteTV.bool'):
                        delete = True
                    elif result['Type'] == 'Movie' and settings('deleteMovies.bool'):
                        delete = True

                    if not settings('offerDelete.bool'):
                        delete = False

                    if delete:
                        LOG.info("Offer delete option")

                        if dialog("yesno", heading=_(30091), line1=_(33015), autoclose=120000):
                            item['Server']['api'].delete_item(item['Id'])

            except Exception as error:
                LOG.error(error)

            window('emby.external_check', clear=True)

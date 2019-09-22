# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os

import xbmc
import xbmcgui
import xbmcvfs

from helper import _, api, window, kodi_version, settings, dialog, event, silent_catch, JSONRPC
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Player(xbmc.Player):

    ''' Basic Player class to track progress of Emby content.
        Inherit from within Player class in objects/player.py.
    '''
    played = {}
    up_next = False

    def __init__(self, monitor=None):

        self.monitor = monitor
        xbmc.Player.__init__(self, monitor)

    @silent_catch()
    def get_file_info(self, file):
        return self.played[file]

    def is_playing_file(self, file):
        return file in self.played

    def is_current_file(self, file):
        return file == self.get_playing_file()

    @silent_catch()
    def get_playing_file(self):

        ''' Safe to replace in child class.
        '''
        return self.getPlayingFile()

    def get_available_audio_streams(self):

        ''' Safe to replace in child class.
        '''
        return self.getAvailableAudioStreams()

    def get_current_streams(self):

        ''' Safe to replace in child class.
            Return audio stream, subtitle stream, subtitle bool.
        '''
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

        return audio, subs, subs_enabled

    def get_volume(self):

        ''' Safe to replace in child class.
            Return volume and mute.
        '''
        result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')

        return volume, muted

    def get_time(self):

        ''' Safe to replace in child class.
        '''
        return int(self.getTime())

    def get_total_time(self):

        ''' Safe to replace in child class.
        '''
        return int(self.getTotalTime())

    def set_audio_stream(self, index):

        ''' Safe to replace in child class.
        '''
        self.setAudioStream(int(index))

    def set_subtitle_stream(self, index):

        ''' Safe to replace in child class.
        '''
        self.setSubtitleStream(int(index))

    def set_subtitle(self, enable):

        ''' Safe to replace in child class.
        '''
        self.showSubtitles(enable)

    def set_audio_subs(self, audio=None, subtitle=None):

        ''' Safe to replace in child class.
            Only for after playback started.
        '''
        LOG.info("Setting audio: %s subs: %s", audio, subtitle)
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            item = self.get_file_info(current_file)
            mapping = item['SubsMapping']

            if audio and len(self.get_available_audio_streams()) > 1:
                self.set_audio_stream(audio - 1)

            if subtitle is None or subtitle == -1:
                self.set_subtitle(False)

                return

            tracks = len(self.get_available_audio_streams())

            if mapping:
                for index in mapping:

                    if mapping[index] == subtitle:
                        self.set_subtitle_stream(int(index))

                        break
                else:
                    self.set_subtitle_stream(len(mapping) + subtitle - tracks - 1)
            else:
                self.set_subtitle_stream(subtitle - tracks - 1)

    def onAVStarted(self):

        LOG.info("[ onAVStarted ]")
        self.up_next = False
        current_file = self.get_playing_file()
        item = self.set_item(current_file)

        if not item:
            return

        window('emby.skip.%s.bool' % item['Id'], True)

    def onPlayBackStarted(self):

        LOG.info("[ onPlayBackStarted ]")
        self.stop_playback()

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

    def onPlayBackStopped(self):

        ''' Safe to replace in child class.
            Will be called when user stops playing a file.
        '''
        window('emby.play.reset.bool', True)
        window('emby.sync.pause.bool', True)
        self.stop_playback()
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):

        ''' Safe to replace in child class.
            Will be called when kodi stops playing a file.
        '''
        window('emby.play.reset.bool', True)
        window('emby.sync.pause.bool', True)
        self.stop_playback()
        LOG.info("--<<[ playback ]")

    def _get_items(self):

        ''' Property setup in playutils.py
            Simple list of dicts filled ordered by play request.
        '''
        items = window('emby.play.json')
        count = 0

        while not items:

            if self.monitor.waitForAbort(2):
                raise Exception('InternalStop')

            items = window('emby.play.json')
            count += 1

            if count == 5:
                LOG.info("<[ emby.play empty ]")

                raise Exception('TimedOut')

            if window('emby.play.reset.bool'):

                window('emby.play.reset', clear=True)
                LOG.info("<[ reset play setup ]")

                raise Exception('InternalStop')

        return items

    def _set_items(self, items):
        window('emby.play.json', items)

    def set_item(self, file, track=True):

        ''' Call when playback start to setup play entry in player tracker.
        '''
        if not file:
            LOG.warn("Filename is invalid")

            return

        try:
            items = self._get_items()
        except Exception as error:
            if file in self.played:

                LOG.warn("[ reusing played item ]")
                item = self.played[file]
            else:
                LOG.error(error)

                return
        else:
            item = None

            for item in items:
                if item['Path'] == file.decode('utf-8'):
                    items.pop(items.index(item))

                    break
            else:
                item = items.pop(0)

            self._set_items(items)

        try:
            item['Runtime'] = int(item['Runtime'])
        except (TypeError, ValueError):
            try:
                item['Runtime'] = self.get_total_time()
                LOG.info("Runtime is missing, Kodi runtime: %s" % item['Runtime'])
            except Exception:

                item['Runtime'] = 0
                LOG.info("Runtime is missing, Using Zero")

        try:
            seektime = self.get_time()
        except Exception: # at this point we should be playing and if not then bail out
            return

        volume, muted = self.get_volume()
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

        if track:
            item['Track'] = True

        if self.monitor.waitForAbort(2):
            return

        return item

    def detect_audio_subs(self, item):

        audio, subs, subs_enabled = self.get_current_streams()

        item['AudioStreamIndex'] = audio + 1

        if not subs_enabled or not len(self.get_available_audio_streams()):
            item['SubtitleStreamIndex'] = -1

            return

        mapping = item['SubsMapping']
        tracks = len(self.get_available_audio_streams())

        if mapping:
            if str(subs) in mapping:
                item['SubtitleStreamIndex'] = mapping[str(subs)]
            else:
                item['SubtitleStreamIndex'] = subs - len(mapping) + tracks + 1
        else:
            item['SubtitleStreamIndex'] = subs + tracks + 1

    def get_next_up(self, item):

        if item['Type'] != 'Episode' or not item.get('CurrentEpisode'):
            return

        next_items = item['Server']['api'].get_adjacent_episodes(item['CurrentEpisode']['tvshowid'], item['Id'])

        for index, next_item in enumerate(next_items['Items']):
            if next_item['Id'] == item['Id']:

                try:
                    return next_items['Items'][index + 1]
                except IndexError:
                    raise Exception("MissingNextEpisode")

                break

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

        item['Volume'], item['Muted'] = self.get_volume()
        self.detect_audio_subs(item)

        if (not report and orig_item['AudioStreamIndex'] != item['AudioStreamIndex'] or
            orig_item['SubtitleStreamIndex'] != item['SubtitleStreamIndex'] or
            orig_item['Muted'] != item['Muted']) or orig_item['Volume'] != item['Volume']:

            report = True

        if not report:

            previous = item['CurrentPosition']
            item['CurrentPosition'] = self.get_time()

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
            current_time = self.get_time()

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
            'SubtitleStreamIndex': item['SubtitleStreamIndex'],
            'RunTimeTicks': int(item['Runtime'] * 10000000)
        }
        item['Server']['api'].session_progress(data)

    def onPlayBackError(self):

        LOG.warn("Playback error occured")
        self.stop_playback()

        try:
            items = self._get_items()
        except Exception as error:
            LOG.error(error)

            return

        item = items.pop(0)
        self._set_items(items)

        item['Server'] = Emby(item['ServerId']).get_client()

        if item.get('LiveStreamId'):

            LOG.info("<[ livestream/%s ]", item['LiveStreamId'])
            item['Server']['api'].close_live_stream(item['LiveStreamId'])

        elif item['PlayMethod'] == 'Transcode':

            LOG.info("<[ transcode/%s ]", item['Id'])
            item['Server']['api'].close_transcode(item['DeviceId'])

    def stop_playback(self):

        ''' Stop all playback. Check for external player for positionticks.
        '''
        LOG.debug("[ played info ] %s", self.played)

        for file in self.played:

            try:
                item = self.get_file_info(file)

                if not item['Track']:
                    LOG.info("[ skip stop ] %s", file)

                    continue

                LOG.info("[ played info ] %s", item)
                item['Track'] = False
                self.played[file] = item
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
                            event("LibraryChanged", {'ItemsRemoved': [item['Id']], 'ItemsVerify': [item['Id']], 'ItemsUpdated': [], 'ItemsAdded': []})

            except Exception as error:
                LOG.error(error)

        window('emby.play.reset', clear=True)
        window('emby.external_check', clear=True)
        window('emby.sync.pause', clear=True)

# -*- coding: utf-8 -*-

#################################################################################################

import binascii
import json
import logging
import Queue
import threading
import sys

import xbmc
import xbmcgui

import connect
import database
import downloader
import objects
from client import get_device_id
from helper import _, settings, window, dialog, event, playutils, api, JSONRPC
from emby import Emby
from webservice import WebService

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Monitor(xbmc.Monitor):

    servers = []
    sleep = False
    playlistid = None

    def __init__(self):

        self.device_id = get_device_id()
        self.player = objects.player.Player(monitor=self)
        self.listener = Listener(monitor=self)
        self.listener.start()

        self.workers_threads = []
        self.queue = Queue.Queue()

        xbmc.Monitor.__init__(self)

    def _get_server(self, method, data):

        ''' Retrieve the Emby server.
        '''
        try:
            if not data.get('ServerId'):
                raise Exception("ServerId undefined.")

            if method != 'LoadServer' and data['ServerId'] not in self.servers:

                try:
                    connect.Connect().register(data['ServerId'])
                    self.server_instance(data['ServerId'])
                except Exception as error:

                    LOG.error(error)
                    dialog("ok", heading="{emby}", line1=_(33142))

                    return

            server = Emby(data['ServerId']).get_client()
        except Exception:
            server = Emby().get_client()

        return server

    def add_worker(self):
        
        ''' Use threads to avoid blocking the onNotification function.
        '''
        if len(self.workers_threads) < 3:

            new_thread = MonitorWorker(self)
            new_thread.start()
            self.workers_threads.append(new_thread)

    def onScanStarted(self, library):

        ''' Safe to replace in child class.
        '''
        LOG.info("-->[ kodi scan/%s ]", library)

    def onScanFinished(self, library):

        ''' Safe to replace in child class.
        '''
        LOG.info("--<[ kodi scan/%s ]", library)

    def get_plugin_video_emby_method(self):
        return ('GetItem', 'ReportProgressRequested', 'LoadServer', 'RandomItems', 'Recommended',
                'GetServerAddress', 'GetPlaybackInfo', 'Browse', 'GetImages', 'GetToken',
                'PlayPlaylist', 'Play', 'GetIntros', 'GetAdditionalParts', 'RefreshItem', 'Genres',
                'FavoriteItem', 'DeleteItem', 'AddUser', 'GetSession', 'GetUsers', 'GetThemes',
                'GetTheme', 'Playstate', 'GeneralCommand', 'GetTranscodeOptions', 'RecentlyAdded',
                'BrowseSeason', 'LiveTV', 'GetLiveStream')

    def get_xbmc_method(self):

        ''' Safe to replace in child class.
        '''
        return ('Player.OnPlay', 'Playlist.OnAdd', 'VideoLibrary.OnUpdate', 'Player.OnAVChange', 'Playlist.OnClear')

    def onNotification(self, sender, method, data):

        ''' Safe to replace in child class.
        '''
        if sender.lower() not in ('plugin.video.emby', 'xbmc', 'upnextprovider.signal'):
            return

        if sender == 'plugin.video.emby':
            method = method.split('.')[1]

            if method not in self.get_plugin_video_emby_method():
                return

            data = json.loads(data)[0]

        elif sender.startswith('upnextprovider'):
            method = method.split('.')[1]

            if method not in ('plugin.video.emby_play_action'):
                return

            method = "Play"
            data = json.loads(data)
            data = json.loads(binascii.unhexlify(data[0])) if data else data
        else:
            if method not in self._get_xbmc_method():

                LOG.info("[ %s/%s ]", sender, method)
                LOG.debug(data)

                return

            data = json.loads(data)

        return self.on_notification(sender, method, data)

    def on_notification(self, sender, method, data):

        LOG.debug("[ %s: %s ] %s", sender, method, json.dumps(data))
        data['MonitorMethod'] = method

        if self.sleep:
            LOG.info("System.OnSleep detected, ignore monitor request.")

            return

        server = self._get_server(method, data)
        self.queue.put((getattr(self, method.replace('.', '_')), server, data,))
        self.add_worker()

    def void_responder(self, data, result):

        window('emby_%s.json' % data['VoidName'], result)
        LOG.debug("--->[ nostromo/emby_%s.json ] sent", data['VoidName'])

    def server_instance(self, server_id=None):

        server = Emby(server_id)
        self.post_capabilities(server)

        if server_id is not None:
            self.servers.append(server_id)
        elif settings('addUsers'):

            users = settings('addUsers').split(',')
            hidden = None if settings('addUsersHidden.bool') else False
            all_users = server['api'].get_users(hidden=hidden)

            for additional in users:
                for user in all_users:

                    if user['Id'] == additional:
                        server['api'].session_add_user(server['config/app.session'], user['Id'])

            self.additional_users(server)

        event('ServerOnline', {'ServerId': server_id})

    def post_capabilities(self, server):
        LOG.info("--[ post capabilities/%s ]", server['auth/server-id'])

        server['api'].post_capabilities({
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png",
        })

        session = server['api'].get_device(self.device_id)
        server['config']['app.session'] = session[0]['Id']

    def additional_users(self, server):

        ''' Setup additional users images.
        '''
        for i in range(10):
            window('EmbyAdditionalUserImage.%s' % i, clear=True)

        try:
            session = server['api'].get_device(self.device_id)
        except Exception as error:
            LOG.error(error)

            return

        for index, user in enumerate(session[0]['AdditionalUsers']):

            info = server['api'].get_user(user['UserId'])
            image = api.API(info, server['config/auth.server']).get_user_artwork(user['UserId'])
            window('EmbyAdditionalUserImage.%s' % index, image)
            window('EmbyAdditionalUserPosition.%s' % user['UserId'], str(index))

    def GetItem(self, server, data, *args, **kwargs):

        item = server['api'].get_item(data['Id'])
        self.void_responder(data, item)

    def GetAdditionalParts(self, server, data, *args, **kwargs):

        item = server['api'].get_additional_parts(data['Id'])
        self.void_responder(data, item)

    def GetIntros(self, server, data, *args, **kwargs):

        item = server['api'].get_intros(data['Id'])
        self.void_responder(data, item)

    def GetImages(self, server, data, *args, **kwargs):

        item = server['api'].get_images(data['Id'])
        self.void_responder(data, item)

    def GetServerAddress(self, server, data, *args, **kwargs):

        server_address = server['auth/server-address']
        self.void_responder(data, server_address)

    def GetPlaybackInfo(self, server, data, *args, **kwargs):
        
        sources = server['api'].get_play_info(data['Id'], data['Profile'])
        self.void_responder(data, sources)

    def GetLiveStream(self, server, data, *args, **kwargs):

        sources = server['api'].get_live_stream(data['Id'], data['PlaySessionId'], data['Token'], data['Profile'])
        self.void_responder(data, sources)

    def GetToken(self, server, data, *args, **kwargs):

        token = server['auth/token']
        self.void_responder(data, token)

    def GetSession(self, server, data, *args, **kwargs):

        session = server['api'].get_device(self.device_id)
        self.void_responder(data, session)

    def GetUsers(self, server, data, *args, **kwargs):

        users = server['api'].get_users(data.get('IsDisabled', False), data.get('IsHidden'))
        self.void_responder(data, users)

    def GetTranscodeOptions(self, server, data, *args, **kwargs):

        result = server['api'].get_transcode_settings()
        self.void_responder(data, result)

    def GetThemes(self, server, data, *args, **kwargs):

        if data['Type'] == 'Video':
            theme = server['api'].get_items_theme_video(data['Id'])
        else:
            theme = server['api'].get_items_theme_song(data['Id'])

        self.void_responder(data, theme)

    def GetTheme(self, server, data, *args, **kwargs):

        theme = server['api'].get_themes(data['Id'])
        self.void_responder(data, theme)

    def Browse(self, server, data, *args, **kwargs):

        result = downloader.get_filtered_section(data.get('Id'), data.get('Media'), data.get('Limit'),
                                                 data.get('Recursive'), data.get('Sort'), data.get('SortOrder'),
                                                 data.get('Filters'), data.get('Params'), data.get('ServerId'))
        self.void_responder(data, result)

    def BrowseSeason(self, server, data, *args, **kwargs):

        result = server['api'].get_seasons(data['Id'])
        self.void_responder(data, result)

    def LiveTV(self, server, data, *args, **kwargs):

        result = server['api'].get_channels()
        self.void_responder(data, result)

    def RecentlyAdded(self, server, data, *args, **kwargs):

        result = server['api'].get_recently_added(data.get('Media'), data.get('Id'), data.get('Limit'))
        self.void_responder(data, result)

    def Genres(self, server, data, *args, **kwargs):

        result = server['api'].get_genres(data.get('Id'))
        self.void_responder(data, result)

    def Recommended(self, server, data, *args, **kwargs):

        result = server['api'].get_recommendation(data.get('Id'), data.get('Limit'))
        self.void_responder(data, result)

    def RefreshItem(self, server, data, *args, **kwargs):
        server['api'].refresh_item(data['Id'])

    def FavoriteItem(self, server, data, *args, **kwargs):
        server['api'].favorite(data['Id'], data['Favorite'])

    def DeleteItem(self, server, data, *args, **kwargs):
        server['api'].delete_item(data['Id'])        

    def PlayPlaylist(self, server, data, *args, **kwargs):
        server['api'].post_session(server['config/app.session'], "Playing", {
            'PlayCommand': "PlayNow",
            'ItemIds': data['Id'],
            'StartPositionTicks': 0
        })

    def Playstate(self, server, data, *args, **kwargs):

        ''' Emby playstate updates.
        '''
        command = data['Command']
        actions = {
            'Stop': self.player.stop,
            'Unpause': self.player.pause,
            'Pause': self.player.pause,
            'PlayPause': self.player.pause,
            'NextTrack': self.player.playnext,
            'PreviousTrack': self.player.playprevious
        }
        if command == 'Seek':

            if self.player.isPlaying():

                seektime = data['SeekPositionTicks'] / 10000000.0
                self.player.seekTime(seektime)
                LOG.info("[ seek/%s ]", seektime)

        elif command in actions:

            actions[command]()
            LOG.info("[ command/%s ]", command)

    def GeneralCommand(self, server, data, *args, **kwargs):

        ''' General commands from Emby to control the Kodi interface.
        '''
        command = data['Name']
        args = data['Arguments']

        if command in ('Mute', 'Unmute', 'SetVolume',
                       'SetSubtitleStreamIndex', 'SetAudioStreamIndex', 'SetRepeatMode'):

            if command == 'Mute':
                xbmc.executebuiltin('Mute')
            elif command == 'Unmute':
                xbmc.executebuiltin('Mute')
            elif command == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % args['Volume'])
            elif command == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % args['RepeatMode'])
            elif command == 'SetAudioStreamIndex':
                self.player.set_audio_subs(args['Index'])
            elif command == 'SetSubtitleStreamIndex':
                self.player.set_audio_subs(None, args['Index'])

            self.player.report_playback()

        elif command == 'DisplayMessage':
            dialog("notification", heading=args['Header'], message=args['Text'],
                   icon="{emby}", time=int(settings('displayMessage'))*1000)

        elif command == 'SendString':
            JSONRPC('Input.SendText').execute({'text': args['String'], 'done': False})

        elif command == 'GoHome':
            JSONRPC('GUI.ActivateWindow').execute({'window': "home"})

        elif command == 'Guide':
            JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})

        elif command in ('MoveUp', 'MoveDown', 'MoveRight', 'MoveLeft'):
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }
            JSONRPC(actions[command]).execute()

        else:
            builtin = {
                'ToggleFullscreen': 'Action(FullScreen)',
                'ToggleOsdMenu': 'Action(OSD)',
                'ToggleContextMenu': 'Action(ContextMenu)',
                'Select': 'Action(Select)',
                'Back': 'Action(back)',
                'PageUp': 'Action(PageUp)',
                'NextLetter': 'Action(NextLetter)',
                'GoToSearch': 'VideoLibrary.Search',
                'GoToSettings': 'ActivateWindow(Settings)',
                'PageDown': 'Action(PageDown)',
                'PreviousLetter': 'Action(PrevLetter)',
                'TakeScreenshot': 'TakeScreenshot',
                'ToggleMute': 'Mute',
                'VolumeUp': 'Action(VolumeUp)',
                'VolumeDown': 'Action(VolumeDown)',
            }
            if command in builtin:
                xbmc.executebuiltin(builtin[command])

    def LoadServer(self, server, data, *args, **kwargs):
        self.server_instance(data['ServerId'])

    def AddUser(self, server, data, *args, **kwargs):

        server['api'].session_add_user(server['config/app.session'], data['Id'], data['Add'])
        self.additional_users(server)

    def Player_OnAVChange(self, *args, **kwargs):

        ''' Safe to replace in child class.
        '''
        self.ReportProgressRequested(*args, **kwargs)

    def ReportProgressRequested(self, server, data, *args, **kwargs):

        ''' Safe to replace in child class.
        '''
        self.player.report_playback(data.get('Report', True))

    def Player_OnPlay(self, server, data, *args, **kwargs):
        
        ''' Safe to replace in child class.
            Setup progress for emby playback.
        '''
        try:
            kodi_id = None

            if self.player.isPlayingVideo():

                ''' Seems to misbehave when playback is not terminated prior to playing new content.
                    The kodi id remains that of the previous title. Maybe onPlay happens before
                    this information is updated. Added a failsafe further below.
                '''
                item = self.player.getVideoInfoTag()
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

    def Playlist_OnClear(self, server, data, *args, **kwargs):

        ''' Safe to replace in child class.
        '''
        pass

    def VideoLibrary_OnUpdate(self, server, data, *args, **kwargs):

        ''' Safe to replace in child class.
            Only for manually marking as watched/unwatched
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

    def Playlist_OnAdd(self, server, data, *args, **kwargs):

        ''' Detect widget playback. Widget for some reason, use audio playlists.
        '''
        if data['position'] == 0:

            if self.playlistid == data['playlistid'] and data['item']['type'] != 'unknown':

                LOG.info("[ reset autoplay ]")
                window('emby.autoplay', clear=True)

            if data['playlistid'] == 0:
                window('emby.playlist.audio.bool', True)
            else:
                window('emby.playlist.audio', clear=True)

            self.playlistid = data['playlistid']

        LOG.info(data)
        if window('emby.playlist.start') and data['position'] == int(window('emby.playlist.start')) + 1:

            LOG.info("--[ playlist ready ]")
            window('emby.playlist.ready.bool', True)
            window('emby.playlist.start', clear=True)


class MonitorWorker(threading.Thread):

    def __init__(self, monitor):

        ''' Thread the monitor so that we can do whatever we need without blocking onNotification.
        '''
        self.monitor = monitor
        self.queue = monitor.queue
        threading.Thread.__init__(self)

    def run(self):

        while True:

            try:
                func, server, data = self.queue.get(timeout=1)
            except Queue.Empty:
                self.monitor.workers_threads.remove(self)

                break

            try:
                LOG.info("-->[ q:monitor/%s ]", data['MonitorMethod'])
                func(server, data)
            except Exception as error:
                LOG.exception(error)

            self.queue.task_done()

            if window('emby_should_stop.bool'):
                break


class Listener(threading.Thread):

    stop_thread = False

    def __init__(self, monitor):

        self.monitor = monitor
        threading.Thread.__init__(self)

    def run(self):

        ''' Detect the resume dialog for widgets.
            Detect external players.
        '''
        LOG.warn("--->[ listener ]")

        while not self.stop_thread:
            objects.listener()

            if self.monitor.waitForAbort(0.5):
                break

        LOG.warn("---<[ listener ]")

    def stop(self):
        self.stop_thread = True

# -*- coding: utf-8 -*-
import json
import logging
import threading
import uuid

try: #python 2
    import imp
except: #python 3
    import importlib as imp

import xbmc
import xbmcgui
import helper.api
import helper.utils
import helper.translate
import database.database
import database.library
import emby.main
import emby.connect
import emby.views
import hooks.webservice
import core.listitem
from . import player

try:
    import queue as Queue
except ImportError:
    import Queue

class Monitor(xbmc.Monitor):
    def __init__(self):
        self.LOG = logging.getLogger("EMBY.hooks.monitor.Monitor")
        self.sleep = False
        self.library = None
        self.servers = []
        self.Utils = helper.utils.Utils()
        self.device_id = self.Utils.get_device_id()
        self.ServerIP = None
        self.ServerToken = None
        self.Server = None
        self.DeviceID = None
        self.connect = emby.connect.Connect(self.Utils)
        self.auth_check = True
        self.warn = False
        self.ProgressThread = None
        self.WebServiceThread = None
        self.log_level = self.Utils.settings('logLevel') or "1"
        self.WebserviceOnPlayThread = None
        self.WebserviceEventOut = Queue.Queue()
        self.WebserviceEventIn = Queue.Queue()
        self.player = player.PlayerEvents(monitor=self)
        self.server = []
        self.Service = None
        self.ItemSkipUpdate = []
        self.ItemSkipUpdateAfterStop = []
        self.ItemSkipUpdateReset = False
        self.PlaySessionIdLast = ""
        self.PlaySessionId = ""
        self.MediasourceID = ""
        self.Trailer = False
        self.PlayerReloadIndex = "-1"
        self.PlayerLastItem = ""
        self.PlayerLastItemID = "-1"

        self.PlayWebsocketPreviousCommand = "" #Propably an issue from Emby Server -> Same command send twice
        xbmc.Monitor.__init__(self)

    def Monitor_waitForAbort(self, Data):
        self.waitForAbort(Data)

    def LibraryStop(self):
        if self.library is not None:
            self.library.stop_client()
            self.library = None

    def Register(self):
        self.connect.register()

    def LibraryLoad(self):
        if self.library is None:
            self.library = database.library.Library(self.Utils)

    #Retrieve the Emby server.
    def _get_server(self, method, data):
        try:
            if not data.get('ServerId'):
                raise Exception("ServerId undefined.")

            if method != 'LoadServer' and data['ServerId'] not in self.servers:
                try:
                    self.connect.register(data['ServerId'])
                    self.server_instance(data['ServerId'])
                except Exception as error:
                    self.LOG.error(error)
                    self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33142))
                    return

            server = emby.main.Emby(data['ServerId']).get_client()
        except Exception:
            server = emby.main.Emby().get_client()

        return server

    def onScanStarted(self, library):
        self.LOG.info("-->[ kodi scan/%s ]", library)

    def onScanFinished(self, library):
        self.LOG.info("--<[ kodi scan/%s ]", library)

    def onSettingsChanged(self):
        new_thread = MonitorWorker(self, None, "settingschanged", None, None, self.device_id)
        new_thread.start()

    def onNotification(self, sender, method, data):
        if sender.lower() not in ('plugin.video.emby-next-gen', 'xbmc', 'upnextprovider.signal'):
            return

        if self.sleep:
            self.LOG.info("System.OnSleep detected, ignore monitor request.")
            return

        server = self._get_server(method, data)
        new_thread = MonitorWorker(self, sender, method, data, server)
        new_thread.start()

    def server_instance(self, server_id=None):
        server = emby.main.Emby(server_id).get_client()
        self.post_capabilities(server)

        if server_id is not None:
            self.servers.append(server_id)
        elif self.Utils.settings('addUsers'):
            users = self.Utils.settings('addUsers').split(',')
            hidden = None if self.Utils.settings('addUsersHidden.bool') else False
            all_users = server['api'].get_users(hidden=hidden)

            for additional in users:
                for user in all_users:
                    if user['Id'] == additional:
                        server['api'].session_add_user(server['config/app.session'], user['Id'])

            self.additional_users(server)

        self.Utils.event('ServerOnline', {'ServerId': server_id})

    def post_capabilities(self, server):
        self.LOG.info("--[ post capabilities/%s ]", server['auth/server-id'])
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
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"
        })

        session = server['api'].get_device(self.device_id)
        server['config']['app.session'] = session[0]['Id']

    def additional_users(self, server):
        for i in range(10):
            self.Utils.window('EmbyAdditionalUserImage.%s' % i, clear=True)

        try:
            session = server['api'].get_device(self.device_id)
        except Exception as error:
            self.LOG.error(error)
            return

        for index, user in enumerate(session[0]['AdditionalUsers']):
            info = server['api'].get_user(user['UserId'])
            image = helper.api.API(info, self.Utils, server['config/auth.server']).get_user_artwork(user['UserId'])
            self.Utils.window('EmbyAdditionalUserImage.%s' % index, image)
            self.Utils.window('EmbyAdditionalUserPosition.%s' % user['UserId'], str(index))

    #Emby playstate updates.
    def Playstate(self, server, data):
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
                self.LOG.info("[ seek/%s ]", seektime)
        elif command in actions:
            actions[command]()
            self.LOG.info("[ command/%s ]", command)

    #General commands from Emby to control the Kodi interface.
    def GeneralCommand(self, server, data):
        command = data['Name']
        args = data['Arguments']

        if command in ('Mute', 'Unmute', 'SetVolume', 'SetSubtitleStreamIndex', 'SetAudioStreamIndex', 'SetRepeatMode'):
            if command == 'Mute':
                xbmc.executebuiltin('Mute')
            elif command == 'Unmute':
                xbmc.executebuiltin('Mute')
            elif command == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % args['Volume'])
            elif command == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % args['RepeatMode'])
#            elif command == 'SetAudioStreamIndex':
#                self.player.set_audio_subs(args['Index'])
#            elif command == 'SetSubtitleStreamIndex':
#                self.player.set_audio_subs(None, args['Index'])

            self.player.report_playback()
        elif command == 'DisplayMessage':
            self.Utils.dialog("notification", heading=args['Header'], message=args['Text'], icon="{emby}", time=int(self.Utils.settings('displayMessage')) * 1000)
        elif command == 'SendString':
            helper.utils.JSONRPC('Input.SendText').execute({'text': args['String'], 'done': False})
        elif command == 'GoHome':
            helper.utils.JSONRPC('GUI.ActivateWindow').execute({'window': "home"})
        elif command == 'Guide':
            helper.utils.JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})
        elif command in ('MoveUp', 'MoveDown', 'MoveRight', 'MoveLeft'):
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }

            helper.utils.JSONRPC(actions[command]).execute()
        else:
            builtin = {
                'ToggleFullscreen': 'Action(FullScreen)',
                'ToggleOsdMen': 'Action(OSD)',
                'ToggleContextMen': 'Action(ContextMenu)',
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
                'VolumeDown': 'Action(VolumeDown)'
            }

            if command in builtin:
                xbmc.executebuiltin(builtin[command])

    def LoadServer(self, server, data):
        self.server_instance(data['ServerId'])

        if not data['ServerId']:
            self.Utils.window('emby.server.state.json', server.get_state())
        else:
            self.Utils.window('emby.server.%s.state.json' % data['ServerId'], server.get_state())
            current = self.Utils.window('emby.server.states.json') or []
            current.append(data['ServerId'])
            self.Utils.window('emby.server.states.json', current)

    def StopServer(self, server, data):
        if not data['ServerId']:
            self.Utils.window('emby.server.state', clear=True)
        else:
            self.Utils.window('emby.server.%s.state' % data['ServerId'], clear=True)
            current = self.Utils.window('emby.server.states.json')
            current.pop(current.index(data['ServerId']))
            self.Utils.window('emby.server.states.json', current)

    def Player_OnAVChange(self, *args, **kwargs):
        self.ReportProgressRequested(*args, **kwargs)

    def ReportProgressRequested(self, server, data):
        if not self.Trailer:
            self.player.report_playback()

    def Player_OnStop(self, server, data):
        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        server['api'].close_transcode(self.device_id)
        self.Utils.window('emby.sync.pause.bool', clear=True)

    def Player_OnPlay(self, server, data):
        self.Utils.window('emby.sync.pause.bool', True)
        current_file = self.player.get_playing_file()

        if not "id" in data['item']:
            if 'title' in data['item']:
                DynamicItemId = self.Utils.window('emby_DynamicItem_' + current_file)

                if not DynamicItemId:
                    return
            else:
                return

        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        if not self.Trailer:
            CurrentItem = None

            if current_file:
                if not "id" in data['item']:
                    CurrentItem = dict([
                        ('Type', data['item']['type']),
                        ('Id', DynamicItemId),
                        ('Path', current_file),
                        ('MediaSourceId', self.MediasourceID),
                        ('ServerId', None),
                        ('Server', server),
                        ('Paused', False),
                        ('PlaySessionId', self.PlaySessionId),
                        ('RunTime', -1),
                        ('CurrentPosition', -1),
                        ('DeviceId', self.Utils.window('emby_deviceId'))
                    ])
                else:
                    kodi_id = data['item']['id']
                    media_type = data['item']['type']
                    item = database.database.get_item(kodi_id, media_type)

                    if item:
                        CurrentItem = dict([
                            ('Type', media_type),
                            ('Id', item[0]),
                            ('Path', current_file),
                            ('MediaSourceId', self.MediasourceID),
                            ('ServerId', None),
                            ('Server', server),
                            ('Paused', False),
                            ('PlaySessionId', self.PlaySessionId),
                            ('RunTime', -1),
                            ('CurrentPosition', -1),
                            ('DeviceId', self.Utils.window('emby_deviceId'))
                        ])

                if CurrentItem: #else native Kodi
                    #native mode
                    if not "127.0.0.1" in current_file:
                        CurrentItem['PlaySessionId'] = str(uuid.uuid4()).replace("-", "")
                    else:
                        if self.PlaySessionIdLast == CurrentItem['PlaySessionId']:
                            for i in range(60):
                                xbmc.sleep(500)

                                if self.PlaySessionIdLast != self.PlaySessionId:
                                    break

                            CurrentItem['PlaySessionId'] = self.PlaySessionId
                            CurrentItem['MediaSourceId'] = self.MediasourceID

                    self.PlaySessionIdLast = CurrentItem['PlaySessionId']
                    self.player.set_item(CurrentItem)

                    if not self.ProgressThread:
                        self.ProgressThread = player.ProgressUpdates(self.player)
                        self.ProgressThread.start()

    def AddPlaylistItem(self, Position, EmbyID, server, Offset=0):
        Data = database.database.get_kodiID(str(EmbyID))

        if Data: #Requested video is synced to KodiDB. No additional info required
            if Data[0][1] == "audio":
                playlistID = 0
                playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            else:
                playlistID = 1
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            Pos = self.GetPlaylistPos(Position, playlist, Offset)
            helper.utils.JSONRPC('Playlist.Insert').execute({'playlistid': playlistID, 'position': Pos, 'item': {'%sid' % Data[0][1]: int(Data[0][0])}})
        else:
            listitems = core.listitem.ListItem(server['auth/server-address'], self.Utils)
            item = server['api'].get_item(EmbyID)
            li = xbmcgui.ListItem()
            li = listitems.set(item, li, None, False, None)
            path = ""

            if item['Type'] == "MusicVideo":
                Type = "musicvideo"
            elif item['Type'] == "Movie":
                Type = "movie"
            elif item['Type'] == "Episode":
                Type = "tvshow"
            elif item['Type'] == "Audio":
                Type = "audio"
            elif item['Type'] == "Video":
                Type = "video"
            elif item['Type'] == "Trailer":
                Type = "trailer"
            elif item['Type'] == "TvChannel":
                Type = "tvchannel"
                path = "http://127.0.0.1:57578/livetv/%s-stream.ts" % item['Id']
            else:
                return

            if not path:
                if 'MediaSources' in item:
                    FilenameURL = self.Utils.PathToFilenameReplaceSpecialCharecters(item['Path'])

                    if len(item['MediaSources'][0]['MediaStreams']) >= 1:
                        path = "http://127.0.0.1:57578/%s/%s-%s-%s-stream-%s" % (Type, item['Id'], item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], FilenameURL)
                    else:
                        path = "http://127.0.0.1:57578/%s/%s-%s-stream-%s" % (Type, item['Id'], item['MediaSources'][0]['Id'], FilenameURL)

            li.setProperty('path', path)

            if Type == "audio":
                playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            else:
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            Pos = self.GetPlaylistPos(Position, playlist, Offset)
            self.Utils.window('emby_DynamicItem_' + path, item['Id'])
            playlist.add(path, li, index=Pos)

        return playlist

    def GetPlaylistPos(self, Position, playlist, Offset):
        if Position == "current":
            Pos = playlist.getposition()

            if Pos == -1:
                Pos = 0

            Pos = Pos + Offset
        elif Position == "previous":
            Pos = playlist.getposition()

            if Pos == -1:
                Pos = 0
        elif Position == "last":
            Pos = playlist.size()
        else:
            Pos = Position

        return Pos

    #Websocket command from Emby server
    def Play(self, server, data):
        if self.PlayWebsocketPreviousCommand == data:
            return

        self.PlayWebsocketPreviousCommand = data
        FirstItem = True
        Offset = 0

        for ID in data['ItemIds']:
            Offset += 1

            if data["PlayCommand"] == "PlayNow":
                playlist = self.AddPlaylistItem("current", ID, server, Offset)
            elif data["PlayCommand"] == "PlayNext":
                playlist = self.AddPlaylistItem("current", ID, server, Offset)

            elif data["PlayCommand"] == "PlayLast":
                playlist = self.AddPlaylistItem("last", ID, server)

            #Play Item
            if data["PlayCommand"] == "PlayNow":
                if "StartIndex" in data:
                    if Offset == int(data["StartIndex"] + 1):
                        if FirstItem:
                            Pos = playlist.getposition()

                            if Pos == -1:
                                Pos = 0

                            xbmc.Player().play(item=playlist, startpos=Pos + Offset)

                            if "StartPositionTicks" in data:
                                xbmc.Player().seekTime(int(data["StartPositionTicks"]) / 100000)

                            Offset = 0
                            FirstItem = False
                else:
                    if FirstItem:
                        Pos = playlist.getposition()

                        if Pos == -1:
                            Pos = 0

                        xbmc.Player().play(item=playlist, startpos=Pos + Offset)

                        if "StartPositionTicks" in data:
                            xbmc.Player().seekTime(int(data["StartPositionTicks"]) / 100000)

                        Offset = 0
                        FirstItem = False

    def Playlist_OnClear(self, server, data):
        self.player.played = {}

    def ServerConnect(self, server, data):
        self.connect.register(data['Id'])
        xbmc.executebuiltin("Container.Refresh")

    def EmbyConnect(self, server, data):
        self.connect.setup_login_connect()

    def RemoveServer(self, server, data):
        self.connect.remove_server(data['Id'])
        xbmc.executebuiltin("Container.Refresh")

    def UserDataChanged(self, server, data):
        if not self.library and data.get('ServerId') or not self.library.started:
            return

        if data.get('UserId') != emby.main.Emby()['auth/user-id']:
            return

        self.LOG.info("[ UserDataChanged ] %s", data)
        UpdateData = []

        for ItemData in data['UserDataList']:
            if not ItemData['ItemId'] in self.ItemSkipUpdate: #Check EmbyID
                item = database.database.get_Presentationkey(ItemData['ItemId'])

                if item:
                    PresentationKey = item.split("-")

                    if not PresentationKey[0] in self.ItemSkipUpdate: #Check PresentationKey
                        UpdateData.append(ItemData)
                    else:
                        self.LOG.info("[ skip update/%s ]", ItemData['ItemId'])
                else:
                    UpdateData.append(ItemData)
            else:
                self.LOG.info("[ skip update/%s ]", ItemData['ItemId'])

        if UpdateData:
            self.library.userdata(UpdateData)

        if self.ItemSkipUpdateReset:
            self.ItemSkipUpdateReset = False
            self.ItemSkipUpdate = []
            self.LOG.info("[ skip reset ]")

    def LibraryChanged(self, server, data):
        if data.get('ServerId') or not self.library.started:
            return

        self.LOG.info("[ LibraryChanged ] %s", data)
        self.library.updated(data['ItemsUpdated'] + data['ItemsAdded'])
        self.library.removed(data['ItemsRemoved'])
        self.library.delay_verify(data.get('ItemsVerify', []))

    def WebSocketRestarting(self, server, data):
        if self.library:
            try:
                self.library.get_fast_sync()
            except Exception as error:
                self.LOG.error(error)

    def SyncLibrarySelection(self, server, data):
        self.library.select_libraries("SyncLibrarySelection")

    def RepairLibrarySelection(self, server, data):
        self.library.select_libraries("RepairLibrarySelection")

    def AddLibrarySelection(self, server, data):
        self.library.select_libraries("AddLibrarySelection")

    def RemoveLibrarySelection(self, server, data):
        self.library.select_libraries("RemoveLibrarySelection")

    def ServerUnreachable(self, server, data):
        if self.warn or data.get('ServerId'):
            self.warn = data.get('ServerId') is not None
            self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33146) if data.get('ServerId') is None else helper.translate._(33149), icon=xbmcgui.NOTIFICATION_ERROR)

        if data.get('ServerId') is None:
            self.Service.Server(20)

    def ServerShuttingDown(self, server, data):
        if self.warn or data.get('ServerId'):
            self.warn = data.get('ServerId') is not None
            self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33146) if data.get('ServerId') is None else helper.translate._(33149), icon=xbmcgui.NOTIFICATION_ERROR)

        if data.get('ServerId') is None:
            self.Service.Server(20)

    def ServiceHandle(self, Handle):
        self.Service = Handle

    def UserConfigurationUpdated(self, server, data):
        if data.get('ServerId') is None:
            emby.views.Views(self.Utils).get_views()

    def UserPolicyUpdated(self, server, data):
        if data.get('ServerId') is None:
            emby.views.Views(self.Utils).get_views()

    def SyncLibrary(self, server, data):
        if not data.get('Id'):
            return

        self.library.add_library(data['Id'], data.get('Update', False))

    def RepairLibrary(self, server, data):
        if not data.get('Id'):
            return

        libraries = data['Id'].split(',')

        for lib in libraries:
            self.library.remove_library(lib)

        self.library.add_library(data['Id'])

    def RemoveLibrary(self, server, data):
        libraries = data['Id'].split(',')

        for lib in libraries:
            self.library.remove_library(lib)

    def GUI_OnScreensaverDeactivated(self, server, data):
        self.LOG.info("--<[ screensaver ]")
        xbmc.sleep(5000)

        if self.library is not None:
            self.library.get_fast_sync()

    def PatchMusic(self, server, data):
        self.library.patch_music(data.get('Notification', True))

    def Unauthorized(self, server, data):
        self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33147) if data['ServerId'] is None else helper.translate._(33148), icon=xbmcgui.NOTIFICATION_ERROR)

        if data.get('ServerId') is None and self.auth_check:
            self.auth_check = False
            self.Service.Server(120)

    def System_OnQuit(self, server, data):
        self.Server = None
        server['api'].close_transcode(self.device_id)
        self.Utils.window('emby_should_stop.bool', True)
        self.Service.running = False

    def Other_ServerRestarting(self, server, data):
        self.Server = None

        if data.get('ServerId'):
            return

        if self.Utils.settings('restartMsg.bool'):
            self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33006), icon="{emby}")

        self.Service.Server(20)

    def WebserviceUpdateInfo(self, server):
        if self.ServerIP:
            try:
                if server: #Restart Webservice
                    self.Server = server

                    if self.WebserviceOnPlayThread:
                        self.WebserviceOnPlayThread.Stop()
                        self.WebserviceOnPlayThread.join()
                        self.WebserviceOnPlayThread = None

                    self.WebserviceOnPlayThread = player.WebserviceOnPlay(self, server)
                    self.WebserviceOnPlayThread.start()

                    if self.WebServiceThread:
                        self.WebServiceThread.stop()
                        self.WebServiceThread.join()
                        self.WebServiceThread = None

                    self.WebServiceThread = hooks.webservice.WebService(self.WebserviceEventOut, self.WebserviceEventIn, self.ServerIP, self.ServerToken)
                    self.WebServiceThread.start()
            except:
                self.LOG.info("[ WebserviceUpdateInfo -> No Connection ]")
        else:
            self.LOG.info("[ WebserviceUpdateInfo -> No Info ]")

    def QuitThreads(self):
        if self.WebserviceOnPlayThread:
            self.WebserviceOnPlayThread.Stop()
            self.WebserviceOnPlayThread.join()
            self.WebserviceOnPlayThread = None

        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread.join()
            self.ProgressThread = None

        if self.WebServiceThread:
            self.WebServiceThread.stop()
            self.WebServiceThread.join()
            self.WebServiceThread = None

    def AddServer(self, server, data):
        self.connect.setup_manual_server()
        xbmc.executebuiltin("Container.Refresh")

    def UpdateServer(self, server, data):
        self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33151))
        self.connect.setup_manual_server()

    def SetServerSSL(self, server, data):
        self.connect.set_ssl(data['Id'])

    def settingschanged(self, server, data):
        imp.reload(helper.utils)
        self.Utils = helper.utils.Utils()

        if self.Utils.window('emby_should_stop.bool'):
            return

        self.DeviceID = self.Utils.get_device_id()
        self.WebserviceUpdateInfo(self.Server)

    def Application_OnVolumeChanged(self, server, data):
        self.player.SETVolume(data['volume'], data['muted'])

    def System_OnWake(self, server=None, data=None):
        if not self.sleep:
            self.LOG.warning("System.OnSleep was never called, skip System.OnWake")
            return

        xbmc.sleep(5000)
        self.LOG.info("--<[ sleep ]")
        self.Utils.window('emby_sleep.bool', False)
        self.sleep = False
        self.Utils.window('emby_should_stop', clear=True)
        self.Service.Server()

    def System_OnSleep(self, server, data):
        self.LOG.info("-->[ sleep ]")
        self.Utils.window('emby_sleep.bool', True)
        self.Utils.window('emby_should_stop.bool', True)
        self.Service.Server(close=True)
        emby.main.Emby().close_all()
        self.server = []
        self.sleep = True

    def ServerOnline(self, server, data):
        self.LOG.info("[ Server Online ]")

        if data.get('ServerId') is None:
            self.Utils.window('emby_online.bool', True)
            self.ServerIP = server['auth/server-address']
            self.ServerToken = server['auth/token']
            self.DeviceID = self.Utils.get_device_id()
            self.WebserviceUpdateInfo(server)

            if self.Utils.window('emby_reloadskin.bool'):
                xbmc.executebuiltin('ReloadSkin()')

            xbmc.sleep(1000) #Give Kodi a second for skin reload
            self.auth_check = True
            self.warn = True

            if self.Utils.settings('connectMsg.bool'):
                users = emby.main.Emby()['api'].get_device(self.Utils.window('emby_deviceId'))[0]['AdditionalUsers']
                users = [user['UserName'] for user in users]
                users.insert(0, self.Utils.settings('username'))
                self.Utils.dialog("notification", heading="{emby}", message="%s %s" % (helper.translate._(33000), ", ".join(users)), icon="{emby}", time=1500, sound=False)

    def AddSkipItem(self, ID):
        self.ItemSkipUpdate.append(ID)
        self.ItemSkipUpdateAfterStop.append(ID)

    def SetSkipItemAfterStop(self):
        self.ItemSkipUpdate = self.ItemSkipUpdateAfterStop
        self.ItemSkipUpdateReset = True

    #Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self, server, data):
        if 'item' in data:
            if 'playcount' in data:
                kodi_id = data['item']['id']
                media = data['item']['type']
                item = database.database.get_item_complete(kodi_id, media)

                if item:
                    if media in ("tvshow"): #Search for all items in TVShow and update them
                        PresentationKey = item[10].split("-")
                        items = database.database.get_ItemsByPresentationkey(PresentationKey[0])

                        for item2 in items:
                            self.ItemSkipUpdate.append(item2[0])
                            server['api'].item_played(item2[0], bool(data['playcount']))

                        return

                    self.ItemSkipUpdate.append(item[0])
                    server['api'].item_played(item[0], bool(data['playcount']))

            self.ItemSkipUpdateReset = True

#Thread the monitor so that we can do whatever we need without blocking onNotification.
class MonitorWorker(threading.Thread):
    def __init__(self, monitor=None, sender=None, method=None, data=None, server=None, device_id=None):
        self.sender = sender
        self.method = method
        self.data = data
        self.server = server
        self.monitor = monitor
        self.device_id = device_id
        self.Utils = helper.utils.Utils()
        self.LOG = logging.getLogger("EMBY.hooks.monitor.MonitorWorker")
        threading.Thread.__init__(self)

    def run(self):
        if self.method in ('System.OnWake', 'System.OnSleep', 'Unauthorized', 'System.OnQuit', 'Other.ServerRestarting', 'settingschanged'):
            self.data = {}
        elif self.sender == 'plugin.video.emby-next-gen':
            self.method = self.method.split('.')[1]

            if self.method not in ('ReportProgressRequested', 'LoadServer', 'Play', 'Playstate', 'GeneralCommand', 'StopServer', 'RegisterServer', 'ServerOnline', 'ServerConnect', 'EmbyConnect', 'AddServer', 'RemoveServer', 'UpdateServer', 'SetServerSSL', 'UserDataChanged', 'LibraryChanged', 'WebSocketRestarting', 'SyncLibrarySelection', 'RepairLibrarySelection', 'AddLibrarySelection', 'RemoveLibrarySelection', 'SyncLibrary', 'RepairLibrary', 'RemoveLibrary', 'GUI.OnScreensaverDeactivated', 'PatchMusic', 'UserConfigurationUpdated', 'UserPolicyUpdated', 'ServerUnreachable', 'ServerShuttingDown'):
                return

            self.data = json.loads(self.data)[0]
        elif self.sender.startswith('upnextprovider'):
            self.method = self.method.split('.')[1]

            if self.method != 'plugin.video.emby-next-gen_play_action':
                return

            self.method = "Play"
            self.data = json.loads(self.data)
        else:
            if self.method not in ('Player.OnPlay', 'Player.OnStop', 'VideoLibrary.OnUpdate', 'Player.OnAVChange', 'Playlist.OnClear', 'Application.OnVolumeChanged'):
                return

            self.data = json.loads(self.data)

        self.data['MonitorMethod'] = self.method
        func = getattr(self.monitor, self.method.replace('.', '_'))
        func(self.server, self.data)

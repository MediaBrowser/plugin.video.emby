# -*- coding: utf-8 -*-
import json
import threading
import os

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

import helper.loghandler
import helper.xmls
import database.database
import database.library
import emby.connect
import hooks.webservice
import core.listitem
import core.artwork
from . import player

try:
    import queue as Queue
except ImportError:
    import Queue

class Monitor(xbmc.Monitor):
    def __init__(self, Service):
        self.LOG = helper.loghandler.LOG('EMBY.hooks.monitor.Monitor')
        self.sleep = False
        self.EmbyServer = {}
        self.library = {}
        self.ServerIP = None
        self.ServerToken = None
        self.Server = None
        self.WebServiceThread = None
        self.WebserviceOnPlayThread = None
        self.WebserviceEventOut = Queue.Queue()
        self.WebserviceEventIn = Queue.Queue()
        self.Service = Service
        self.player = player.PlayerEvents()
        self.PlayWebsocketPreviousCommand = "" #Propably an issue from Emby Server -> Same command send twice
        self.Xmls = helper.xmls.Xmls(self.Service.Utils)
        self.connect = emby.connect.Connect(self.Service.Utils) #multipe servers here!!!!!!!!!!!!!!!!!!!!!!!!!!!

    def EmbyServer_ReconnectAll(self):
        for server_id in self.EmbyServer:
            self.Service.ServerReconnect(server_id, False)

    def EmbyServer_DisconnectAll(self):
        for server_id in self.EmbyServer:
            self.EmbyServer[server_id].stop()
            self.StopServer({'ServerId': server_id})
            self.Service.Utils.window('emby.server.%s.online.bool' % server_id, False)

    def EmbyServer_Connect(self):
        server_id, EmbyServer = self.connect.register({})

        if server_id == 'cancel':
            return False

        if not server_id:
#            self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33146))
            self.LOG.error("EmbyServer Connect error")
            return False
        else:
            self.EmbyServer[server_id] = EmbyServer
            self.EmbyServer[server_id].start()
            self.ServerOnline({'ServerId': server_id})
            return server_id

    #Add theme media locally, via strm. This is only for tv tunes.
    #If another script is used, adjust this code
    def SyncThemes(self, data):
        library = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/library")

        if not xbmcvfs.exists(library + '/'):
            xbmcvfs.mkdir(library)

        if xbmc.getCondVisibility('System.HasAddon(script.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="script.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', library)
            self.LOG.info("TV Tunes custom path is enabled and set.")
        elif xbmc.getCondVisibility('System.HasAddon(service.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', library)
            self.LOG.info("TV Tunes custom path is enabled and set.")
        else:
            self.Service.Utils.dialog("ok", heading="{emby}", line1=self.Service.Utils.Translate(33152))
            return

        with database.database.Database(self.Service.Utils, 'emby', False) as embydb:
            all_views = database.emby_db.EmbyDatabase(embydb.cursor).get_views()
            views = [x[0] for x in all_views if x[2] in ('movies', 'tvshows', 'mixed')]

        items = {}

        for view in views:
            for result in self.EmbyServer[data['ServerId']].API.get_itemsSync(view, None, False, {'HasThemeVideo': True}):
                for item in result['Items']:
                    folder = self.Service.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

            for result in self.EmbyServer[data['ServerId']].API.get_itemsSync(view, None, False, {'HasThemeSong': True}):
                for item in result['Items']:
                    folder = self.Service.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

        for item in items:
            nfo_path = os.path.join(library, items[item])
            nfo_file = os.path.join(nfo_path, "tvtunes.nfo")

            if not xbmcvfs.exists(nfo_path):
                xbmcvfs.mkdir(nfo_path)

            themes = self.EmbyServer[data['ServerId']].API.get_themes(item)
            paths = []

            for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
                if self.Service.Utils.direct_path:
                    paths.append(theme['MediaSources'][0]['Path'])
                else:
                    paths.append(self.Service.Utils.direct_url(theme))

            self.Xmls.tvtunes_nfo(nfo_file, paths)

        self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33153), icon="{emby}", time=1000, sound=False)

    def DatabaseReset(self):
        database.database.reset(self.Service.Utils, False)

    def TextureCache(self):
        core.artwork.Artwork(None, self.Service.Utils).cache_textures()

    def LibraryStopAll(self):
        for server_id in self.library:
            self.library[server_id].stop_thread = True

        self.library = {}

    def LibraryStop(self, server_id):
        if server_id in self.library:
            self.library[server_id].stop_thread = True
            del self.library[server_id]

    def LibraryLoad(self, server_id):
        if not server_id in self.library:
            self.ServerOnline({'ServerId': server_id})
            self.library[server_id] = database.library.Library(self.player, self.EmbyServer[server_id])

    def onScanStarted(self, library):
        self.LOG.info("-->[ kodi scan/%s ]" % library)

    def onScanFinished(self, library):
        self.LOG.info("--<[ kodi scan/%s ]" % library)

    def onSettingsChanged(self):
        new_thread = MonitorWorker(self, None, "settingschanged", None)
        new_thread.start()

    def onNotification(self, sender, method, data):
        if sender.lower() not in ('plugin.video.emby-next-gen', 'plugin.video.emby', 'xbmc', 'upnextprovider.signal'):
            return

        if self.sleep:
            self.LOG.info("System.OnSleep detected, ignore monitor request.")
            return

        new_thread = MonitorWorker(self, sender, method, data)
        new_thread.start()

    #Emby playstate updates.
    def Playstate(self, data):
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
                self.LOG.info("[ seek/%s ]" % seektime)
        elif command in actions:
            actions[command]()
            self.LOG.info("[ command/%s ]" % command)

    #General commands from Emby to control the Kodi interface.
    def GeneralCommand(self, data):
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
            self.Service.Utils.dialog("notification", heading=args['Header'], message=args['Text'], icon="{emby}", time=int(self.Service.Utils.settings('displayMessage')) * 1000)
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

            helper.utils.JSONRPC(actions[command]).execute(False)
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

    def StopServer(self, data):
        self.Service.Utils.window('emby.server.%s.state' % data['ServerId'], clear=True)

    def Player_OnAVChange(self, *args, **kwargs):
        self.ReportProgressRequested(*args, **kwargs)

    def ReportProgressRequested(self, data):
        if not self.player.Trailer:
            self.player.report_playback()

    def Player_OnStop(self, data):
        for server_id in self.EmbyServer: ######################## WORKAROUND!!!!!!!!!!!
            break

        self.player.OnStop(self.EmbyServer[server_id])

    def Player_OnPlay(self, data):
        for server_id in self.EmbyServer: ######################## WORKAROUND!!!!!!!!!!!
            break

        self.player.OnPlay(data, self.EmbyServer[server_id])






    def AddPlaylistItem(self, Position, EmbyID, server_id, Offset):
        Data = database.database.get_kodiID(self.Service.Utils, str(EmbyID))

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
            listitems = core.listitem.ListItem(self.EmbyServer[server_id].Data['auth.ssl'], self.Service.Utils)
            item = self.EmbyServer[server_id].API.get_item(EmbyID)
            li = xbmcgui.ListItem()
            li = listitems.set(item, li, None, None)
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
                    FilenameURL = self.Service.Utils.PathToFilenameReplaceSpecialCharecters(item['Path'])

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
            self.Service.Utils.window('emby.DynamicItem_' + self.Service.Utils.ReplaceSpecialCharecters(li.getLabel()), item['Id'])
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
    def Play(self, data):
        if self.PlayWebsocketPreviousCommand == data:
            return

        self.PlayWebsocketPreviousCommand = data
        FirstItem = True
        Offset = 0

        for ID in data['ItemIds']:
            Offset += 1

            if data["PlayCommand"] == "PlayNow":
                playlist = self.AddPlaylistItem("current", ID, data['ServerId'], Offset)
            elif data["PlayCommand"] == "PlayNext":
                playlist = self.AddPlaylistItem("current", ID, data['ServerId'], Offset)

            elif data["PlayCommand"] == "PlayLast":
                playlist = self.AddPlaylistItem("last", ID, data['ServerId'], 0)

            #Play Item
            if data["PlayCommand"] == "PlayNow":
                if "StartIndex" in data:
                    if Offset == int(data["StartIndex"] + 1):
                        if FirstItem:
                            Pos = playlist.getposition()

                            if Pos == -1:
                                Pos = 0

                            self.player.play(item=playlist, startpos=Pos + Offset)

                            if "StartPositionTicks" in data:
                                self.player.seekTime(int(data["StartPositionTicks"]) / 100000)

                            Offset = 0
                            FirstItem = False
                else:
                    if FirstItem:
                        Pos = playlist.getposition()

                        if Pos == -1:
                            Pos = 0

                        self.player.play(item=playlist, startpos=Pos + Offset)

                        if "StartPositionTicks" in data:
                            self.player.seekTime(int(data["StartPositionTicks"]) / 100000)

                        Offset = 0
                        FirstItem = False

    def Playlist_OnClear(self, data):
        self.player.played = {}

    def ServerConnect(self, data):
        self.EmbyServer_Connect()
        xbmc.executebuiltin("Container.Refresh")

    def RemoveServer(self, data):
        self.EmbyServer[data['ServerId']].close()
        self.connect.remove_server(data['ServerId'])
        xbmc.executebuiltin("Container.Refresh")

    def UserDataChanged(self, data):
        if data.get('UserId') != self.EmbyServer[data['ServerId']].auth.get_server_info()['UserId']:
            return

        self.LOG.info("[ UserDataChanged ] %s" % data)
        UpdateData = []

        for ItemData in data['UserDataList']:
            if not ItemData['ItemId'] in self.player.ItemSkipUpdate: #Check EmbyID
                item = database.database.get_Presentationkey(self.Service.Utils, ItemData['ItemId'])

                if item:
                    PresentationKey = item.split("-")

                    if not PresentationKey[0] in self.player.ItemSkipUpdate: #Check PresentationKey
                        UpdateData.append(ItemData)
                    else:
                        self.LOG.info("[ skip update/%s ]" % ItemData['ItemId'])
                else:
                    UpdateData.append(ItemData)
            else:
                self.LOG.info("[ skip update/%s ]" % ItemData['ItemId'])

        if UpdateData:
            self.library[data['ServerId']].userdata(UpdateData)

        if self.player.ItemSkipUpdateReset:
            self.player.ItemSkipUpdateReset = False
            self.player.ItemSkipUpdate = []
            self.LOG.info("[ skip reset ]")

    def LibraryChanged(self, data):
        self.LOG.info("[ LibraryChanged ] %s" % data)
        self.library[data['ServerId']].updated(data['ItemsUpdated'] + data['ItemsAdded'])
        self.library[data['ServerId']].removed(data['ItemsRemoved'])
        self.library[data['ServerId']].delay_verify(data.get('ItemsVerify', []))

    def WebSocketRestarting(self, data):
        self.library[data['ServerId']].get_fast_sync()

    def SyncLibrarySelection(self, data):
        self.library[data['ServerId']].select_libraries("SyncLibrarySelection")

    def RepairLibrarySelection(self, data):
        self.library[data['ServerId']].select_libraries("RepairLibrarySelection")

    def AddLibrarySelection(self, data):
        self.library[data['ServerId']].select_libraries("AddLibrarySelection")

    def RemoveLibrarySelection(self, data):
        self.library[data['ServerId']].select_libraries("RemoveLibrarySelection")

    def ServerUnreachable(self, data):
        if self.Service.ServerReconnectingInProgress(data['ServerId']):
            return

        self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33146))
        self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId'], False)
        self.Service.ServerReconnect(data['ServerId'])

    def RefreshItem(self, data):
        self.EmbyServer[data['ServerId']].API.refresh_item(data['Id'])

    def AddFavItem(self, data):
        self.EmbyServer[data['ServerId']].API.favorite(data['Id'], True)

    def RemoveFavItem(self, data):
        self.EmbyServer[data['ServerId']].API.favorite(data['Id'], False)

    def ServerShuttingDown(self, data):
        if self.Service.ServerReconnectingInProgress(data['ServerId']):
            return

        self.Service.Utils.dialog("notification", heading="{emby}", message="Enable server shutdown")
        self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId'], False)
        self.Service.ServerReconnect(data['ServerId'])

    def UserConfigurationUpdated(self, data):
        self.Service.Views.get_views()

    def UserPolicyUpdated(self, data):
        self.Service.Views.get_views()

    def SyncLibrary(self, data):
        self.library[data['ServerId']].add_library(data['Id'], data['Update'])

    def RepairLibrary(self, data):
        libraries = data['Id'].split(',')

        for lib in libraries:
            self.library[data['ServerId']].remove_library(lib)

        self.library[data['ServerId']].add_library(data['Id'], False)

    def RemoveLibrary(self, data):
        libraries = data['Id'].split(',')

        for lib in libraries:
            self.library[data['ServerId']].remove_library(lib)

    def GUI_OnScreensaverDeactivated(self, data):
        self.LOG.info("--<[ screensaver ]")
        xbmc.sleep(5000)

        if data['ServerId'] in self.library:
            self.library[data['ServerId']].get_fast_sync()

    def PatchMusic(self, data):
        self.library[data['ServerId']].patch_music(data.get('Notification', True))

    def Unauthorized(self, data):
        self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId'], False)
        self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33147))

    def System_OnQuit(self):
        self.Server = None

        for server_id in self.EmbyServer:
            if self.player.Transcoding:
                self.EmbyServer[server_id].API.close_transcode()

        self.Service.ShouldStop = True

    def ServerRestarting(self, data):
        self.Server = None

        if self.Service.ServerReconnectingInProgress(data['ServerId']):
            return

        if self.Service.Utils.settings('restartMsg.bool'):
            self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33006), icon="{emby}")

        self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId'], False)
        self.Service.ServerReconnect(data['ServerId'])

    def WebserviceUpdateInfo(self, server):
        if self.ServerIP:
            if server: #Restart Webservice
                self.Server = server

                if self.WebserviceOnPlayThread:
                    self.WebserviceOnPlayThread.Stop()
                    self.WebserviceOnPlayThread = None

                self.WebserviceOnPlayThread = player.WebserviceOnPlay(self.player, server, self.WebserviceEventIn, self.WebserviceEventOut)
                self.WebserviceOnPlayThread.start()

                if self.WebServiceThread:
                    self.WebServiceThread.stop()
                    self.WebServiceThread.join()
                    self.WebServiceThread = None

                self.WebServiceThread = hooks.webservice.WebService(self.WebserviceEventOut, self.WebserviceEventIn, self.ServerIP, self.ServerToken)
                self.WebServiceThread.start()
        else:
            self.LOG.info("[ WebserviceUpdateInfo -> No Info ]")

    def QuitThreads(self):
        if self.WebserviceOnPlayThread:
            self.WebserviceOnPlayThread.Stop()
            self.WebserviceOnPlayThread = None

        if self.player.ProgressThread:
            self.player.ProgressThread.Stop()
            self.player.ProgressThread = None

        if self.WebServiceThread:
            self.WebServiceThread.stop()
            self.WebServiceThread = None

    def AddServer(self, data):
#        self.connect.setup_manual_server()
#        xbmc.executebuiltin("Container.Refresh")
        self.EmbyServer_Connect()

    def SetServerSSL(self, data):
        self.connect.set_ssl(data['ServerId'])

    def settingschanged(self):
        if self.Service.ShouldStop or self.sleep:
            return

        self.Service.Utils.InitSettings()

    def Application_OnVolumeChanged(self, data):
        self.player.SETVolume(data['volume'], data['muted'])

    def System_OnWake(self):
        if not self.sleep:
            self.LOG.warning("System.OnSleep was never called, skip System.OnWake")
            return

        self.LOG.info("--<[ sleep ]")
        self.sleep = False
        self.EmbyServer_ReconnectAll()
        self.player.SyncPause = False

    def System_OnSleep(self):
        self.LOG.info("-->[ sleep ]")
        self.player.SyncPause = True
        self.QuitThreads()
        self.EmbyServer_DisconnectAll()
        self.LibraryStopAll()
        self.sleep = True

    def ServerOnline(self, data):
        self.LOG.info("[ Server Online ]")

        if self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId']):
            return

        self.Service.Utils.window('emby.server.%s.online.bool' % data['ServerId'], True)
        self.ServerIP = self.EmbyServer[data['ServerId']].auth.get_serveraddress()
        self.ServerToken = self.EmbyServer[data['ServerId']].Data['auth.token']
        self.WebserviceUpdateInfo(self.EmbyServer[data['ServerId']])

        if self.Service.ReloadSkin:
            xbmc.executebuiltin('ReloadSkin()')
            self.Service.ReloadSkin = False

        if self.Service.Utils.settings('connectMsg.bool'):
            users = self.EmbyServer[data['ServerId']].API.get_device()[0]   # ['AdditionalUsers']
            users = users['UserName']
#            users = [user['UserName'] for user in users['AdditionalUsers']]
#            users.insert(0, self.Service.Utils.settings('username'))
#            self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33000), ", ".join(users)), icon="{emby}", time=1500, sound=False)
            self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33000), self.Service.Utils.StringMod(users)), icon="{emby}", time=1500, sound=False)

    #Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self, data):
        for server_id in self.EmbyServer: ######################## WORKAROUND!!!!!!!!!!!  ADD Serverid info in emby.db and query from there
            break

        if 'item' in data:
            if 'playcount' in data:
                kodi_id = data['item']['id']
                media = data['item']['type']
                item = database.database.get_item_complete(self.Service.Utils, kodi_id, media) #read here serverid

                if item:
                    if media == "tvshow": #Search for all items in TVShow and update them
                        PresentationKey = item[10].split("-")
                        items = database.database.get_ItemsByPresentationkey(self.Service.Utils, PresentationKey[0])

                        for item2 in items:
                            self.player.ItemSkipUpdate.append(item2[0])
                            self.EmbyServer[server_id].API.item_played(item2[0], bool(data['playcount']))

                        return

                    self.player.ItemSkipUpdate.append(item[0])
                    self.EmbyServer[server_id].API.item_played(item[0], bool(data['playcount']))

            self.player.ItemSkipUpdateReset = True

#Thread the monitor so that we can do whatever we need without blocking onNotification.
class MonitorWorker(threading.Thread):
    def __init__(self, monitor, sender, method, data):
        self.sender = sender
        self.method = method
        self.data = data
        self.monitor = monitor
        threading.Thread.__init__(self)

    def run(self):
        if self.method == 'System.OnWake':
            self.monitor.System_OnWake()
            return

        if self.method == 'System.OnSleep':
            self.monitor.System_OnSleep()
            return

        if self.method == 'System.OnQuit':
            self.monitor.System_OnQuit()
            return

        if self.method == 'settingschanged':
            self.monitor.settingschanged()
            return

        if self.method == 'Other.DatabaseReset':
            self.monitor.DatabaseReset()
            return

        if self.method == 'Other.TextureCache':
            self.monitor.TextureCache()
            return

        if self.sender == 'plugin.video.emby-next-gen':
            self.method = self.method.split('.')[1]

            if self.method not in ('ReportProgressRequested', 'Play', 'Playstate', 'GeneralCommand', 'StopServer', 'RegisterServer', 'ServerOnline', 'ServerConnect', 'AddServer', 'RemoveServer', 'SetServerSSL', 'UserDataChanged', 'LibraryChanged', 'WebSocketRestarting', 'SyncLibrarySelection', 'RepairLibrarySelection', 'AddLibrarySelection', 'RemoveLibrarySelection', 'SyncLibrary', 'RepairLibrary', 'RemoveLibrary', 'GUI.OnScreensaverDeactivated', 'PatchMusic', 'UserConfigurationUpdated', 'UserPolicyUpdated', 'ServerUnreachable', 'ServerShuttingDown', 'RefreshItem', 'AddFavItem', 'RemoveFavItem', 'ServerRestarting', 'Unauthorized', 'SyncThemes'):
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
        func(self.data)

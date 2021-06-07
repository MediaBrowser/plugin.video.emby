# -*- coding: utf-8 -*-
import json
import threading
import os

import xbmc
import xbmcvfs
import xbmcaddon

import helper.loghandler
import helper.xmls
import helper.jsonrpc
import helper.context
import helper.pluginmenu
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
        self.ItemSkipUpdateReset = False
        self.EmbyServers = {}
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
        self.Context = helper.context.Context(self.Service.Utils, self.EmbyServers, self.library)
        self.Menu = helper.pluginmenu.Menu(self.Service.Utils, self.EmbyServers, self.player)
        self.Xmls = helper.xmls.Xmls(self.Service.Utils)
        self.connect = emby.connect.Connect(self.Service.Utils) #multipe servers here!!!!!!!!!!!!!!!!!!!!!!!!!!!

    def EmbyServer_ReconnectAll(self):
        for server_id in self.EmbyServers:
            self.Service.ServerReconnect(server_id, False)

    def EmbyServer_DisconnectAll(self):
        for server_id in self.EmbyServers:
            self.EmbyServers[server_id].stop()
            self.EmbyServers[server_id].Online = False
            self.StopServer({'ServerId': server_id})

    def EmbyServer_Connect(self):
        server_id, EmbyServer = self.connect.register({})

        if server_id == 'cancel':
            return False

        if not server_id:
            self.LOG.error("EmbyServer Connect error")
            return False

        self.EmbyServers[server_id] = EmbyServer
        self.EmbyServers[server_id].start()
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
            for result in self.EmbyServers[data['ServerId']].API.get_itemsSync(view, None, False, {'HasThemeVideo': True}):
                for item in result['Items']:
                    folder = self.Service.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

            for result in self.EmbyServers[data['ServerId']].API.get_itemsSync(view, None, False, {'HasThemeSong': True}):
                for item in result['Items']:
                    folder = self.Service.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

        for item in items:
            nfo_path = os.path.join(library, items[item])
            nfo_file = os.path.join(nfo_path, "tvtunes.nfo")

            if not xbmcvfs.exists(nfo_path):
                xbmcvfs.mkdir(nfo_path)

            themes = self.EmbyServers[data['ServerId']].API.get_themes(item)
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
            self.library[server_id] = database.library.Library(self.player, self.EmbyServers[server_id])

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
            self.Service.Utils.dialog("notification", heading=args['Header'], message=args['Text'], icon="{emby}", time=int(self.Service.Utils.Settings.displayMessage) * 1000)
        elif command == 'SendString':
            helper.jsonrpc.JSONRPC('Input.SendText').execute({'text': args['String'], 'done': False})
        elif command == 'GoHome':
            helper.jsonrpc.JSONRPC('GUI.ActivateWindow').execute({'window': "home"})
        elif command == 'Guide':
            helper.jsonrpc.JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})
        elif command in ('MoveUp', 'MoveDown', 'MoveRight', 'MoveLeft'):
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }
            helper.jsonrpc.JSONRPC(actions[command]).execute(False)
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
        self.EmbyServers[data['ServerId']].Online = False

    def Player_OnAVChange(self, *args, **kwargs):
        self.ReportProgressRequested(*args, **kwargs)

    def ReportProgressRequested(self, data):
        if not self.player.Trailer:
            self.player.report_playback()

    def Player_OnStop(self, data):
        for server_id in self.EmbyServers: ######################## WORKAROUND!!!!!!!!!!!
            break

        self.player.OnStop(self.EmbyServers[server_id])

    def Player_OnPlay(self, data):
        for server_id in self.EmbyServers: ######################## WORKAROUND!!!!!!!!!!!
            break

        self.player.OnPlay(data, self.EmbyServers[server_id], self.library[server_id])

    def AddPlaylistItem(self, Position, EmbyID, server_id, Offset):
        Data = database.database.get_kodiID(self.Service.Utils, str(EmbyID))

        if Data: #Requested video is synced to KodiDB. No additional info required
            if Data[0][1] in ("song", "album", "artist"):
                playlistID = 0
                playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            else:
                playlistID = 1
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            Pos = self.GetPlaylistPos(Position, playlist, Offset)

            helper.jsonrpc.JSONRPC('Playlist.Insert').execute({'playlistid': playlistID, 'position': Pos, 'item': {'%sid' % Data[0][1]: int(Data[0][0])}})
        else:
            listitems = core.listitem.ListItem(self.Service.Utils)
            item = self.EmbyServers[server_id].API.get_item(EmbyID)
            li = listitems.set(item)
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
            self.player.DynamicItem[self.Service.Utils.ReplaceSpecialCharecters(li.getLabel())] = item['Id']
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
        self.EmbyServers[data['ServerId']].close()
        self.connect.remove_server(data['ServerId'])
        xbmc.executebuiltin("Container.Refresh")

    def UserDataChanged(self, data):
        if data.get('UserId') != self.EmbyServers[data['ServerId']].auth.get_server_info()['UserId']:
            return

        self.LOG.info("[ UserDataChanged ] %s" % data)

        if not self.player.SyncPause and not self.ItemSkipUpdateReset:
            self.player.ItemSkipUpdate = []
            self.LOG.info("[ reset skip after playback ]")

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

        if self.ItemSkipUpdateReset:
            self.player.ItemSkipUpdate = []
            self.LOG.info("[ reset skip after video library update ]")

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
        self.EmbyServers[data['ServerId']].Online = False
        self.Service.ServerReconnect(data['ServerId'])

    def ServerShuttingDown(self, data):
        if self.Service.ServerReconnectingInProgress(data['ServerId']):
            return

        self.Service.Utils.dialog("notification", heading="{emby}", message="Enable server shutdown")
        self.EmbyServers[data['ServerId']].Online = False
        self.Service.ServerReconnect(data['ServerId'])

    def UserConfigurationUpdated(self, data):
        self.Service.Views.get_views()

    def UserPolicyUpdated(self, data):
        self.Service.Views.get_views()

    def GUI_OnScreensaverDeactivated(self, data):
        self.LOG.info("--<[ screensaver ]")
        xbmc.sleep(5000)

        if data['ServerId'] in self.library:
            self.library[data['ServerId']].get_fast_sync()

    def PatchMusic(self, data):
        self.library[data['ServerId']].patch_music(data.get('Notification', True))

    def Unauthorized(self, data):
        self.EmbyServers[data['ServerId']].Online = False
        self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33147))

    def System_OnQuit(self):
        self.Server = None

        for server_id in self.EmbyServers:
            if self.player.Transcoding:
                self.EmbyServers[server_id].API.close_transcode()

        self.Service.ShouldStop = True

    def ServerRestarting(self, data):
        self.Server = None

        if self.Service.ServerReconnectingInProgress(data['ServerId']):
            return

        if self.Service.Utils.Settings.restartMsg:
            self.Service.Utils.dialog("notification", heading="{emby}", message=self.Service.Utils.Translate(33006), icon="{emby}")

        self.EmbyServers[data['ServerId']].Online = False
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

                self.WebServiceThread = hooks.webservice.WebService(self.WebserviceEventOut, self.WebserviceEventIn, self.ServerIP, self.ServerToken, self.Service.Utils.Settings.enableCoverArt, self.Service.Utils.Settings.compressArt)
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

        self.Service.Utils.Settings.InitSettings()

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

        if self.EmbyServers[data['ServerId']].Online:
            return

        self.EmbyServers[data['ServerId']].Online = True
        self.ServerIP = self.EmbyServers[data['ServerId']].auth.get_serveraddress()
        self.ServerToken = self.EmbyServers[data['ServerId']].Data['auth.token']
        self.WebserviceUpdateInfo(self.EmbyServers[data['ServerId']])

        if self.Service.Utils.Settings.ReloadSkin:
            xbmc.executebuiltin('ReloadSkin()')
            self.Service.Utils.Settings.set_settings_bool('ReloadSkin', False)

        if self.Service.Utils.Settings.connectMsg:
            users = self.EmbyServers[data['ServerId']].API.get_device()[0]   # ['AdditionalUsers']
            users = users['UserName']
#            users = [user['UserName'] for user in users['AdditionalUsers']]
#            users.insert(0, self.Service.Utils.Settings.username)
#            self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33000), ", ".join(users)), icon="{emby}", time=1500, sound=False)
            self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33000), self.Service.Utils.StringMod(users)), icon="{emby}", time=1500, sound=False)

    #Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self, data):
        for server_id in self.EmbyServers: ######################## WORKAROUND!!!!!!!!!!!  ADD Serverid info in emby.db and query from there
            break

        self.LOG.info("[ VideoLibraryUpdate ] %s" % data)

        if 'item' in data:
            if 'playcount' in data:
                kodi_id = data['item']['id']
                media = data['item']['type']
                item = database.database.get_item_complete(self.Service.Utils, kodi_id, media) #read here serverid

                if item:
                    if not item[0] in self.player.ItemSkipUpdate: #Check EmbyID
                        if media in ("season", "tvshow"):
                            return

                        self.ItemSkipUpdateReset = True
                        self.player.ItemSkipUpdate.append(item[0])
                        self.EmbyServers[server_id].API.item_played(item[0], bool(data['playcount']))

    #Emby backup
    def Backup(self, data):
        if not self.Service.Utils.Settings.backupPath:
            self.Service.Utils.dialog("notification", heading="{emby}", icon="{emby}", message="No backup path set", sound=False)
            return

        path = self.Service.Utils.Settings.backupPath
        folder_name = "Kodi%s.%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2], xbmc.getInfoLabel('System.Date(dd-mm-yy)'))
        folder_name = self.Service.Utils.dialog("input", heading=self.Service.Utils.Translate(33089), defaultt=folder_name)

        if not folder_name:
            return

        backup = os.path.join(path, folder_name)

        if xbmcvfs.exists(backup + '/'):
            if not self.Service.Utils.dialog("yesno", heading="{emby}", line1=self.Service.Utils.Translate(33090)):
                return backup()

            self.Service.Utils.delete_folder(backup)

        addon_data = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen")
        destination_data = os.path.join(backup, "addon_data", "plugin.video.emby-next-gen")
        destination_databases = os.path.join(backup, "Database")

        if not xbmcvfs.mkdirs(path) or not xbmcvfs.mkdirs(destination_databases):
            self.LOG.info("Unable to create all directories")
            self.Service.Utils.dialog("notification", heading="{emby}", icon="{emby}", message=self.Service.Utils.Translate(33165), sound=False)
            return

        self.Service.Utils.copytree(addon_data, destination_data)
        db = self.Service.Utils.translatePath("special://database/")
        _, files = xbmcvfs.listdir(db)

        for Temp in files:
            if 'MyVideos' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s" % Temp)
            elif 'emby' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s" % Temp)
            elif 'MyMusic' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s" % Temp)

        self.LOG.info("backup completed")
        self.Service.Utils.dialog("ok", heading="{emby}", line1="%s %s" % (self.Service.Utils.Translate(33091), backup))

    #Add or remove users from the default server session
    #permanent=True from the add-on settings
    def AddUser(self, data):
        server_id = data['ServerId']
        permanent = True
        session = self.EmbyServers[server_id].API.get_device()
        hidden = None if self.Service.Utils.Settings.addUsersHidden else False
        users = self.EmbyServers[server_id].API.get_users(False, hidden)

        if not users:
            return

        for user in users:
            if user['Id'] == session[0]['UserId']:
                users.remove(user)
                break

        while True:
            session = self.EmbyServers[server_id].API.get_device()
            current = session[0]['AdditionalUsers']

            if permanent:
                perm_users = self.Service.Utils.Settings.Users.split(',') if self.Service.Utils.Settings.Users else []
                current = []

                for user in users:
                    for perm_user in perm_users:

                        if user['Id'] == perm_user:
                            current.append({'UserName': user['Name'], 'UserId': user['Id']})

            result = self.Service.Utils.dialog("select", self.Service.Utils.Translate(33061), [self.Service.Utils.Translate(33062), self.Service.Utils.Translate(33063)] if current else [self.Service.Utils.Translate(33062)])

            if result < 0:
                break

            if not result: # Add user
                eligible = [x for x in users if x['Id'] not in [current_user['UserId'] for current_user in current]]
                resp = self.Service.Utils.dialog("select", self.Service.Utils.Translate(33064), [x['Name'] for x in eligible])

                if resp < 0:
                    break

                user = eligible[resp]

                if permanent:
                    perm_users.append(user['Id'])
                    self.Service.Utils.Settings.set_settings('Users', ','.join(perm_users))

                self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33067), user['Name']), icon="{emby}", time=1000, sound=False)
            else: # Remove user
                resp = self.Service.Utils.dialog("select", self.Service.Utils.Translate(33064), [x['UserName'] for x in current])

                if resp < 0:
                    break

                user = current[resp]

                if permanent:
                    perm_users.remove(user['UserId'])
                    self.Service.Utils.Settings.set_settings('Users', ','.join(perm_users))

                self.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.Service.Utils.Translate(33066), user['UserName']), icon="{emby}", time=1000, sound=False)

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

        if self.method == 'Other.DeleteItem':
            self.monitor.Context.delete_item(True)
            return

        if self.method == 'Other.browse':
            self.data = json.loads(self.data)[0]
            self.monitor.Service.Utils.set_queryIO('emby_event_ack_%s' % self.data['QueryId'])
            self.monitor.Menu.browse(self.data['Handle'], self.data['type'], self.data['id'], self.data['folder'], self.data['name'], self.data['extra'], self.data['ServerId'])
            self.monitor.Service.Utils.set_queryIO('emby_event_%s' % self.data['QueryId'])
            return

        if self.method == 'Other.manage_libraries':
            self.data = json.loads(self.data)[0]
            self.monitor.Service.Utils.set_queryIO('emby_event_ack_%s' % self.data['QueryId'])
            self.monitor.Menu.manage_libraries(self.data['Handle'], self.data['ServerId'])
            self.monitor.Service.Utils.set_queryIO('emby_event_%s' % self.data['QueryId'])
            return

        if self.method == 'Other.nextepisodes':
            self.data = json.loads(self.data)[0]
            self.monitor.Service.Utils.set_queryIO('emby_event_ack_%s' % self.data['QueryId'])
            self.monitor.Menu.get_next_episodes(self.data['Handle'], self.data['libraryname'])
            self.monitor.Service.Utils.set_queryIO('emby_event_%s' % self.data['QueryId'])
            return

        if self.method == 'Other.listing':
            self.data = json.loads(self.data)[0]
            self.monitor.Service.Utils.set_queryIO('emby_event_ack_%s' % self.data['QueryId'])
            self.monitor.Menu.listing(self.data['Handle'])
            self.monitor.Service.Utils.set_queryIO('emby_event_%s' % self.data['QueryId'])
            return

        if self.method == 'Other.restartservice':
            self.monitor.Service.Utils.Settings.emby_restart = True
            return

        if self.method == 'Other.reset_device_id':
            self.monitor.Service.Utils.reset_device_id()
            return

        if self.method == 'Other.context':
            self.monitor.Context.select_menu()
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

            if self.method not in ('ReportProgressRequested', 'Play', 'Playstate', 'GeneralCommand', 'StopServer', 'RegisterServer', 'ServerOnline', 'ServerConnect', 'AddUser', 'AddServer', 'RemoveServer', 'SetServerSSL', 'UserDataChanged', 'LibraryChanged', 'WebSocketRestarting', 'SyncLibrarySelection', 'RepairLibrarySelection', 'AddLibrarySelection', 'RemoveLibrarySelection', 'GUI.OnScreensaverDeactivated', 'PatchMusic', 'UserConfigurationUpdated', 'UserPolicyUpdated', 'ServerUnreachable', 'ServerShuttingDown', 'ServerRestarting', 'Unauthorized', 'SyncThemes', 'Backup'):
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

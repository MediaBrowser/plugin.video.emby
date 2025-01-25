import json
import xbmc
import xbmcgui
from helper import utils, playerops, queue
from database import dbio

class WebSocket:
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.ConnectionInProgress = False
        self.Tasks = {}
        self.EmbyServerSyncCheckRunning = False
        self.RefreshProgressRunning = False
        self.RefreshProgressInit = False
        self.EPGRefresh = False
        self.Running = False
        self.ProgressBar = {}
        self.MessageQueue = queue.Queue()
        xbmc.log("EMBY.hooks.websocket: WSClient initializing...", 0) # LOGDEBUG

    def Message(self):  # threaded
        xbmc.log("EMBY.hooks.websocket: THREAD: --->[ message ]", 0) # LOGDEBUG
        self.Running = True

        while True:
            IncomingData = self.MessageQueue.get()

            if IncomingData == "QUIT":
                xbmc.log("EMBY.hooks.websocket: Queue closed", 1) # LOGINFO
                break

            try:
                xbmc.log(f"EMBY.hooks.websocket: Incoming data: {IncomingData}", 0) # LOGDEBUG
                IncomingData = json.loads(IncomingData)
            except Exception as Error: # connection interrupted and data corrupted
                xbmc.log(f"EMBY.hooks.websocket: Incoming data: {IncomingData} / {Error}", 3) # LOGERROR
                continue

            if IncomingData['MessageType'] == 'GeneralCommand':
                if 'Text' in IncomingData['Data']['Arguments']:
                    Text = IncomingData['Data']['Arguments']['Text']
                else:
                    Text = ""

                if IncomingData['Data']['Name'] == 'DisplayMessage':
                    if IncomingData['Data']['Arguments']['Header'] == "remotecommand":
                        xbmc.log(f"EMBY.hooks.websocket: Incoming remote command: {Text}", 1) # LOGINFO
                        Command = Text.split("|")
                        Event = Command[0].lower()

                        if Event == "clients":
                            playerops.update_Remoteclients(self.EmbyServer.ServerData['ServerId'], Command)
                        elif Event == "connect":
                            utils.start_thread(self.confirm_remote, (Command[1], Command[2]))
                        elif Event == "support":
                            playerops.add_RemoteClientExtendedSupport(self.EmbyServer.ServerData['ServerId'], Command[1])
                        elif Event == "ack":
                            playerops.add_RemoteClientExtendedSupportAck(self.EmbyServer.ServerData['ServerId'], Command[1], Command[2], Command[3])
                        elif Event == "playsingle":
                            playerops.PlayEmby([Command[1]], "PlaySingle", 0, Command[2], self.EmbyServer, Command[3])
                        elif Event == "playinit":
                            playerops.PlayEmby([Command[1]], "PlayInit", 0, Command[2], self.EmbyServer, Command[3])
                        elif Event == "pause":
                            playerops.Pause(True, Command[1], Command[2])
                        elif Event == "seek":
                            playerops.Seek(Command[1], True, Command[2])

                        continue
                    utils.Dialog.notification(heading=IncomingData['Data']['Arguments']['Header'], message=Text, icon=utils.icon, time=utils.displayMessage)
                elif IncomingData['Data']['Name'] == 'SetCurrentPlaylistItem':
                    playerops.PlayPlaylistItem(playerops.PlayerId, IncomingData['Data']['Arguments']['PlaylistItemId'])
                elif IncomingData['Data']['Name'] == 'RemoveFromPlaylist':
                    PlaylistItemIds = IncomingData['Data']['Arguments']['PlaylistItemIds'].split(",")

                    for PlaylistItemId in PlaylistItemIds:
                        playerops.RemovePlaylistItem(playerops.PlayerId, PlaylistItemId)
                elif IncomingData['Data']['Name'] in ('Mute', 'Unmute'):
                    xbmc.executebuiltin('Mute')
                elif IncomingData['Data']['Name'] == 'SetVolume':
                    xbmc.executebuiltin(f"SetVolume({IncomingData['Data']['Arguments']['Volume']}[,showvolumebar])")
                elif IncomingData['Data']['Name'] == 'SetRepeatMode':
                    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Player.SetRepeat", "params": {{"playerid": {playerops.PlayerId}, "repeat": "{IncomingData["Data"]["Arguments"]["RepeatMode"].lower().replace("repeat", "")}"}}}}', True)
                elif IncomingData['Data']['Name'] == 'SetShuffle':
                    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Player.SetShuffle", "params": {{"playerid": {playerops.PlayerId}, "shuffle": {IncomingData["Data"]["Arguments"]["Shuffle"].lower()}}}}}', True)
                elif IncomingData['Data']['Name'] == 'SetAudioStreamIndex':
                    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Player.SetAudioStream", "params": {{"playerid": {playerops.PlayerId}, "stream": {int(IncomingData["Data"]["Arguments"]["Index"]) - 1}}}}}', True)
                elif IncomingData['Data']['Name'] == 'GoHome':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "home"}}')
                elif IncomingData['Data']['Name'] == 'Guide':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "tvguide"}}')
                elif IncomingData['Data']['Name'] == 'MoveUp':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Up"}')
                elif IncomingData['Data']['Name'] == 'MoveDown':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Down"}')
                elif IncomingData['Data']['Name'] == 'MoveRight':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Right"}')
                elif IncomingData['Data']['Name'] == 'MoveLeft':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Left"}')
                elif IncomingData['Data']['Name'] == 'ToggleFullscreen':
                    xbmc.executebuiltin('Action(FullScreen)')
                elif IncomingData['Data']['Name'] == 'ToggleOsdMenu':
                    xbmc.executebuiltin('Action(OSD)')
                elif IncomingData['Data']['Name'] == 'ToggleContextMenu':
                    xbmc.executebuiltin('Action(ContextMenu)')
                elif IncomingData['Data']['Name'] == 'Select':
                    xbmc.executebuiltin('Action(Select)')
                elif IncomingData['Data']['Name'] == 'Back':
                    xbmc.executebuiltin('Action(back)')
                elif IncomingData['Data']['Name'] == 'NextLetter':
                    xbmc.executebuiltin('Action(NextLetter)')
                elif IncomingData['Data']['Name'] == 'PreviousLetter':
                    xbmc.executebuiltin('Action(PrevLetter)')
                elif IncomingData['Data']['Name'] == 'GoToSearch':
                    xbmc.executebuiltin('VideoLibrary.Search')
                elif IncomingData['Data']['Name'] == 'GoToSettings':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "settings"}}')
                elif IncomingData['Data']['Name'] == 'PageUp':
                    xbmc.executebuiltin('Action(PageUp)')
                elif IncomingData['Data']['Name'] == 'PageDown':
                    xbmc.executebuiltin('Action(PageDown)')
                elif IncomingData['Data']['Name'] == 'TakeScreenshot':
                    xbmc.executebuiltin('TakeScreenshot')
                elif IncomingData['Data']['Name'] == 'ToggleMute':
                    xbmc.executebuiltin('Mute')
                elif IncomingData['Data']['Name'] == 'VolumeUp':
                    xbmc.executebuiltin('Action(VolumeUp)')
                elif IncomingData['Data']['Name'] == 'VolumeDown':
                    xbmc.executebuiltin('Action(VolumeDown)')
            elif IncomingData['MessageType'] == 'ScheduledTasksInfo':
                for Task in IncomingData['Data']:
                    xbmc.log(f"EMBY.hooks.websocket: Task update: {Task['Name']} / {Task['State']}", 0) # LOGDEBUG
                    Key = Task.get("Key", "")

                    if not Task['Name'].lower().startswith("scan") and Key != "RefreshGuide":
                        continue

                    if Task["State"] == "Running":
                        if Key == "RefreshGuide":
                            self.EPGRefresh = True

                        if Task["Name"] not in self.Tasks:
                            self.Tasks[Task["Name"]] = True

                            if utils.busyMsg:
                                ProgressBarCreate = xbmcgui.DialogProgressBG()
                                ProgressBarCreate.create(utils.Translate(33199), utils.Translate(33411))
                                self.ProgressBar[Task['Name']] = ProgressBarCreate

                            if not self.EmbyServerSyncCheckRunning:
                                self.EmbyServerSyncCheckRunning = True
                                utils.start_thread(self.EmbyServerSyncCheck, ())

                        if utils.busyMsg and Task['Name'] in self.ProgressBar and self.ProgressBar[Task['Name']]:
                            if 'CurrentProgressPercentage' in Task:
                                Progress = int(float(Task['CurrentProgressPercentage']))
                            else:
                                Progress = 0

                            self.ProgressBar[Task['Name']].update(Progress, utils.Translate(33199), f"{utils.Translate(33411)}: {Task['Name']}")
                    else:
                        if Task["Name"] in self.Tasks:
                            if self.Tasks[Task["Name"]]: # ProgressBar close can take a while, therefore check if close is in progress
                                self.Tasks[Task["Name"]] = False

                                if Task['Name'] in self.ProgressBar:
                                    self.ProgressBar[Task['Name']].close()
                                    del self.ProgressBar[Task['Name']]

            elif IncomingData['MessageType'] == 'RefreshProgress':
                self.RefreshProgressRunning = True

                if not self.RefreshProgressInit:
                    self.RefreshProgressInit = True

                    if utils.busyMsg:
                        self.ProgressBar["RefreshProgress"] = [None, "Init"]
                        self.ProgressBar["RefreshProgress"][0] = xbmcgui.DialogProgressBG()
                        self.ProgressBar["RefreshProgress"][0].create(utils.Translate(33199), utils.Translate(33411))
                        self.ProgressBar["RefreshProgress"][1] = "Loaded"

                    if not self.EmbyServerSyncCheckRunning:
                        self.EmbyServerSyncCheckRunning = True
                        utils.start_thread(self.EmbyServerSyncCheck, ())

                if utils.busyMsg and "RefreshProgress" in self.ProgressBar and self.ProgressBar["RefreshProgress"][1] == "Loaded":
                    self.ProgressBar["RefreshProgress"][0].update(int(float(IncomingData['Data']['Progress'])), utils.Translate(33199), utils.Translate(33414))
            elif IncomingData['MessageType'] == 'UserDataChanged':
                xbmc.log(f"EMBY.hooks.websocket: [ UserDataChanged ] {IncomingData['Data']['UserDataList']}", 1) # LOGINFO
                UpdateData = ()
                RemoveSkippedItems = ()

                if IncomingData['Data']['UserId'] != self.EmbyServer.ServerData['UserId']:
                    xbmc.log(f"EMBY.hooks.websocket: UserDataChanged skip by wrong UserId: {IncomingData['Data']['UserId']}", 0) # LOGDEBUG
                    continue

                if utils.RemoteMode:
                    xbmc.log("EMBY.hooks.websocket: UserDataChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")
                ItemSkipUpdateUniqueIds = set()
                ItemSkipUpdateEmbyPresentationKeys = ()
                ItemSkipUpdateAlbumIds = ()
                ItemSkipUpdateAlbumSongIds = ()

                # Create unique array
                for ItemSkipId in utils.ItemSkipUpdate:
                    if not ItemSkipId.startswith("KODI"):
                        ItemSkipUpdateUniqueIds.add(ItemSkipId)

                for ItemSkipUpdateUniqueId in ItemSkipUpdateUniqueIds:
                    Data = embydb.get_embypresentationkey_by_id_embytype(ItemSkipUpdateUniqueId, ("Episode",)).split("_")[0]

                    if Data:
                        ItemSkipUpdateEmbyPresentationKeys += (Data,)
                    else:
                        AlbumId = embydb.get_albumid_by_id(ItemSkipUpdateUniqueId)

                        if AlbumId:
                            ItemSkipUpdateAlbumIds += (AlbumId,)
                            ItemSkipUpdateAlbumSongIds += embydb.get_id_by_albumid(AlbumId)

                for ItemData in IncomingData['Data']['UserDataList']:
                    if ItemData['ItemId'] not in utils.ItemSkipUpdate:  # Filter skipped items
                        if ItemData['ItemId'] in ItemSkipUpdateAlbumIds:
                            xbmc.log(f"EMBY.hooks.websocket: UserDataChanged skip by ItemSkipUpdate ancestors (AlbumId) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        elif ItemData['ItemId'] in ItemSkipUpdateAlbumSongIds:
                            xbmc.log(f"EMBY.hooks.websocket: UserDataChanged skip by ItemSkipUpdate ancestors (AlbumSongId) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        else:
                            EpisodeEmbyPresentationKey = embydb.get_embypresentationkey_by_id_embytype(ItemData['ItemId'], ("Season", "Series")).split("_")[0]

                            if EpisodeEmbyPresentationKey in ItemSkipUpdateEmbyPresentationKeys:
                                xbmc.log(f"EMBY.hooks.websocket: UserDataChanged skip by ItemSkipUpdate ancestors (PresentationKey) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                            else:
                                UpdateData += (ItemData,)
                    else:
                        xbmc.log(f"EMBY.hooks.websocket: UserDataChanged skip by ItemSkipUpdate / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        RemoveSkippedItems += (ItemData['ItemId'],)

                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")

                for RemoveSkippedItem in RemoveSkippedItems:
                    utils.ItemSkipUpdate.remove(RemoveSkippedItem)

                if UpdateData:
                    utils.start_thread(self.EmbyServer.library.userdata, (UpdateData,))
            elif IncomingData['MessageType'] == 'LibraryChanged':
                xbmc.log(f"EMBY.hooks.websocket: [ LibraryChanged ] {IncomingData['Data']}", 1) # LOGINFO

                if utils.RemoteMode:
                    xbmc.log("EMBY.hooks.websocket: LibraryChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                ItemsUpdated = IncomingData['Data']['ItemsUpdated'] + IncomingData['Data']['ItemsAdded']
                UpdateItemIds = len(ItemsUpdated) * [None] # preallocate memory

                for Index, ItemId in enumerate(ItemsUpdated):
                    UpdateItemIds[Index] = (ItemId, "unknown", "unknown")

                UpdateItemIds = list(dict.fromkeys(UpdateItemIds)) # filter duplicates
                utils.start_thread(self.LibraryChanged, (UpdateItemIds, IncomingData['Data']['ItemsRemoved']))
            elif IncomingData['MessageType'] == 'ServerRestarting':
                xbmc.log("EMBY.hooks.websocket: [ ServerRestarting ]", 1) # LOGINFO
                self.close_EmbyServerBusy()

                if utils.restartMsg:
                    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33006), icon=utils.icon, time=utils.newContentTime)

                self.EmbyServer.ServerReconnect(False)
            elif IncomingData['MessageType'] == 'ServerShuttingDown':
                xbmc.log("EMBY.hooks.websocket: [ ServerShuttingDown ]", 1) # LOGINFO
                self.close_EmbyServerBusy()
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33236), time=utils.newContentTime)
                self.EmbyServer.ServerReconnect(False)
            elif IncomingData['MessageType'] == 'RestartRequired':
                xbmc.log("EMBY.hooks.websocket: [ RestartRequired ]", 1) # LOGINFO
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33237), time=utils.newContentTime)
            elif IncomingData['MessageType'] == 'Play':
                playerops.PlayEmby(IncomingData['Data']['ItemIds'], IncomingData['Data']['PlayCommand'], int(IncomingData['Data'].get('StartIndex', 0)), int(IncomingData['Data'].get('StartPositionTicks', -1)), self.EmbyServer, 0)
            elif IncomingData['MessageType'] == 'Playstate':
                if playerops.PlayerId != -1:
                    if IncomingData['Data']['Command'] == 'Seek':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, False)
                    elif IncomingData['Data']['Command'] == 'SeekRelative':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, True)
                    elif IncomingData['Data']['Command'] == "Stop":
                        playerops.Stop(True)
                    elif IncomingData['Data']['Command'] == "Unpause":
                        playerops.Unpause(True)
                    elif IncomingData['Data']['Command'] == "Pause":
                        playerops.Pause(True, 0, 0)
                    elif IncomingData['Data']['Command'] == "PlayPause": # Toggle pause
                        playerops.PauseToggle(True)
                    elif IncomingData['Data']['Command'] == "NextTrack":
                        playerops.Next()
                    elif IncomingData['Data']['Command'] == "PreviousTrack":
                        playerops.Previous()

                xbmc.log(f"EMBY.hooks.websocket: command: {IncomingData['Data']['Command']} / PlayedId: {playerops.PlayerId}", 1) # LOGINFO

        self.Running = False
        xbmc.log("EMBY.hooks.websocket: THREAD: ---<[ message ]", 0) # LOGDEBUG

    def EmbyServerSyncCheck(self):
        xbmc.log("EMBY.hooks.websocket: THREAD: --->[ Emby server is busy, sync in progress ]", 1) # LOGINFO
        utils.SyncPause[f"server_busy_{self.EmbyServer.ServerData['ServerId']}"] = True
        Compare = [False] * len(self.Tasks)

        while self.Running and (self.RefreshProgressRunning or Compare != list(self.Tasks.values())):
            self.RefreshProgressRunning = False

            if utils.sleep(5): # every 5 seconds a "RefreshProgress" is expected. If not, sync was canceled
                break

            Compare = [False] * len(self.Tasks)

        self.close_EmbyServerBusy()

        if self.Running:
            utils.start_thread(self.EmbyServer.library.RunJobs, (True,))

            if self.EPGRefresh:
                self.EmbyServer.library.SyncLiveTVEPG()
                self.EPGRefresh = False

        xbmc.log("EMBY.hooks.websocket: THREAD: ---<[ Emby server is busy, sync in progress ]", 1) # LOGINFO

    def close_EmbyServerBusy(self):
        if utils.busyMsg:
            if "RefreshProgress" in self.ProgressBar:
                while self.ProgressBar["RefreshProgress"][1] == "Init":
                    utils.sleep(1)

                self.ProgressBar["RefreshProgress"][0].close()
                del self.ProgressBar["RefreshProgress"]

            for TaskId, TaskActive in list(self.Tasks.items()):
                if TaskActive:
                    self.ProgressBar[TaskId].close()

        self.Tasks = {}
        self.RefreshProgressRunning = False
        self.RefreshProgressInit = False
        self.EmbyServerSyncCheckRunning = False
        utils.SyncPause[f"server_busy_{self.EmbyServer.ServerData['ServerId']}"] = False

    def confirm_remote(self, SessionId, Timeout): # threaded
        xbmc.log("EMBY.hooks.websocket: THREAD: --->[ Remote confirm ]", 0) # LOGDEBUG
        self.EmbyServer.API.send_text_msg(SessionId, "remotecommand", f"support|{self.EmbyServer.EmbySession[0]['Id']}", True)

        if utils.remotecontrol_auto_ack:
            Ack = True
        else:
            Ack = utils.Dialog.yesno(heading=utils.addon_name, message="Accept remote connection", autoclose=int(Timeout) * 1000)

        if Ack: # send confirm msg
            self.EmbyServer.API.send_text_msg(SessionId, "remotecommand", f"ack|{self.EmbyServer.EmbySession[0]['Id']}|{self.EmbyServer.EmbySession[0]['DeviceName']}|{self.EmbyServer.EmbySession[0]['UserName']}", True)

        xbmc.log("EMBY.hooks.websocket: THREAD: ---<[ Remote confirm ]", 0) # LOGDEBUG

    def LibraryChanged(self, UpdateItemIds, ItemsRemoved):
        self.EmbyServer.library.removed(ItemsRemoved, True)
        self.EmbyServer.library.updated(UpdateItemIds, True)

        if self.EmbyServerSyncCheckRunning:
            xbmc.log("EMBY.hooks.websocket: Emby server sync in progress, delay updates", 1) # LOGINFO
        else:
            self.EmbyServer.library.RunJobs(True)

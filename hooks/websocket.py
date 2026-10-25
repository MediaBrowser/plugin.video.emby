import threading
import json
import xbmc
from helper import utils, playerops, queue, player, cache
from database import dbio

class WebSocket:
    def __init__(self, ServerData, ThreadsRunningCondition, EmbySession, API, Library, WebsocketRunning, WebsocketMessageQueue):
        self.ServerData = ServerData
        self.EmbySession = EmbySession
        self.API = API
        self.library = Library
        self.WebsocketRunning = WebsocketRunning
        self.WebsocketMessageQueue = WebsocketMessageQueue
        self.ConnectionInProgress = False
        self.Tasks = {}
        self.RefreshProgressRunning = False
        self.RefreshProgressInit = False
        self.EPGRefresh = False
        self.LibraryChangedQueue = queue.Queue()
        self.ProgressCondition = threading.Condition(threading.Lock())
        self.ThreadsRunningCondition = ThreadsRunningCondition
        self.EmbyServerSyncCheckIdleEvent = threading.Event()
        self.RefreshProgressId = f"{self.ServerData['ServerId']}_refresh_progress"
        self.RefreshTaskId = f"{self.ServerData['ServerId']}_task"
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): Emby server {self.ServerData['ServerId']}: WSClient initializing...", 1) # LOGDEBUG

    def Message(self):  # threaded
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: --->[ Emby server {self.ServerData['ServerId']}: message ]", 1) # LOGDEBUG
        self.RefreshProgressId = f"{self.ServerData['ServerId']}_refresh_progress"
        self.RefreshTaskId = f"{self.ServerData['ServerId']}_task"
        self.WebsocketRunning[0] = True
        utils.start_thread(self.EmbyServerSyncCheck, ())
        utils.start_thread(self.LibraryChanged, ())

        with utils.SafeLock(self.ThreadsRunningCondition):
            self.ThreadsRunningCondition.notify_all()

        with utils.SafeLock(self.ProgressCondition):
            self.ProgressCondition.notify_all()

        while True:
            IncomingData = self.WebsocketMessageQueue.get()

            if IncomingData == "QUIT":
                self.LibraryChangedQueue.put("QUIT")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: ---<[ Emby server {self.ServerData['ServerId']}: message ]", 1) # LOGDEBUG
                break

            try:
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): Emby server {self.ServerData['ServerId']}: Incoming data: {IncomingData}", 1) # LOGDEBUG
                IncomingData = json.loads(IncomingData)
            except Exception as Error: # connection interrupted and data corrupted
                xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: Incoming data: {IncomingData} / {Error}", 3) # LOGERROR
                continue

            if IncomingData['MessageType'] == 'GeneralCommand':
                if 'Text' in IncomingData['Data']['Arguments']:
                    Text = IncomingData['Data']['Arguments']['Text']
                else:
                    Text = ""

                if IncomingData['Data']['Name'] == 'DisplayMessage':
                    if IncomingData['Data']['Arguments']['Header'] == "remotecommand":
                        xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: Incoming remote command: {Text}", 1) # LOGINFO
                        Command = Text.split("|")
                        Event = Command[0].lower()

                        if Event == "clients":
                            playerops.update_Remoteclients(self.ServerData['ServerId'], Command)
                        elif Event == "connect":
                            self.confirm_remote(Command[1], Command[2])
                        elif Event == "support":
                            playerops.add_RemoteClientExtendedSupport(self.ServerData['ServerId'], Command[1])
                        elif Event == "ack":
                            playerops.add_RemoteClientExtendedSupportAck(self.ServerData['ServerId'], Command[1], Command[2], Command[3])
                        elif Event == "playsingle":
                            playerops.PlayEmby(True, [Command[1]], "PlaySingle", 0, Command[2], self.ServerData, self.API, Command[3])
                        elif Event == "playplaylist":
                            playerops.PlayEmby(True, Command[1].split(","), "PlayPlaylist", int(Command[4]), int(Command[2]), self.ServerData, self.API, Command[3])
                        elif Event == "playinit":
                            playerops.PlayEmby(True, [Command[1]], "PlayInit", 0, Command[2], self.ServerData, self.API, Command[3])
                        elif Event == "pause":
                            playerops.Pause(True, Command[1], Command[2], True)
                        elif Event == "seek":
                            playerops.Seek(Command[1], True, Command[2])

                        continue
                    utils.Dialog.notification(heading=IncomingData['Data']['Arguments']['Header'], message=Text, icon=utils.icon, time=utils.displayMessage)
                elif IncomingData['Data']['Name'] == 'SetCurrentPlaylistItem':
                    playerops.PlayPlaylistItem(playerops.PlayerId, IncomingData['Data']['Arguments']['PlaylistItemId'])
                elif IncomingData['Data']['Name'] == 'RemoveFromPlaylist':
                    PlaylistItemIds = IncomingData['Data']['Arguments']['PlaylistItemIds'].split(",")

                    for PlaylistItemId in PlaylistItemIds:
                        playerops.RemovePlaylistItem(playerops.PlayerId, int(PlaylistItemId))
                elif IncomingData['Data']['Name'] in ('Mute', 'Unmute'):
                    xbmc.executebuiltin('Mute')
                elif IncomingData['Data']['Name'] == 'SetVolume':
                    xbmc.executebuiltin(f"SetVolume({IncomingData['Data']['Arguments']['Volume']},showvolumebar)")
                elif IncomingData['Data']['Name'] == 'SetRepeatMode':
                    RepeatModeEmby = IncomingData["Data"]["Arguments"]["RepeatMode"].lower()

                    if RepeatModeEmby == "repeatall":
                        RepeatMode = "RepeatAll"
                    elif RepeatModeEmby == "repeatone":
                        RepeatMode = "RepeatOne"
                    elif RepeatModeEmby == "repeatnone":
                        RepeatMode = "RepeatOff"
                    else:
                        continue

                    xbmc.executebuiltin(f"PlayerControl({RepeatMode})")
                elif IncomingData['Data']['Name'] == 'SetShuffle':
                    Shuffle = IncomingData["Data"]["Arguments"]["Shuffle"].lower()
                    ShuffleCommand = {"true": "RandomOn", "false": "RandomOff"}.get(Shuffle)

                    if ShuffleCommand:
                        xbmc.executebuiltin(f"PlayerControl({ShuffleCommand})")
                elif IncomingData['Data']['Name'] == 'SetPlaybackRate':
                    PlaybackRate = IncomingData["Data"]["Arguments"]["PlaybackRate"]
                    playerops.SetSpeed(float(PlaybackRate))
                elif IncomingData['Data']['Name'] == 'SetAudioStreamIndex':
                    StreamIndexEmby = str(IncomingData["Data"]["Arguments"]["Index"])

                    if StreamIndexEmby in player.PlayingItem["IndexMappingAudioEmby"]:
                        utils.SendJson("Player.SetAudioStream", f'{{"playerid": {playerops.PlayerId}, "stream": {player.PlayingItem["IndexMappingAudioEmby"][StreamIndexEmby]}}}', True)
                elif IncomingData['Data']['Name'] == 'SetSubtitleStreamIndex':
                    StreamIndexEmby = str(IncomingData["Data"]["Arguments"]["Index"])

                    if StreamIndexEmby in player.PlayingItem["IndexMappingSubtitleEmby"]:
                        utils.SendJson("Player.SetSubtitle", f'{{"playerid": {playerops.PlayerId}, "subtitle": {player.PlayingItem["IndexMappingSubtitleEmby"][StreamIndexEmby]}}}', True)
                elif IncomingData['Data']['Name'] == 'GoHome':
                    utils.ActivateWindow("home", "")
                elif IncomingData['Data']['Name'] == 'Guide':
                    utils.ActivateWindow("tvguide", "")
                elif IncomingData['Data']['Name'] == 'MoveUp':
                    xbmc.executebuiltin("Action(Up)")
                elif IncomingData['Data']['Name'] == 'MoveDown':
                    xbmc.executebuiltin("Action(Down)")
                elif IncomingData['Data']['Name'] == 'MoveRight':
                    xbmc.executebuiltin("Action(Right)")
                elif IncomingData['Data']['Name'] == 'MoveLeft':
                    xbmc.executebuiltin("Action(Left)")
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
                    utils.ActivateWindow("settings", "")
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
                    if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): Emby server {self.ServerData['ServerId']}: Task update: {Task['Name']} / {Task['State']}", 1) # LOGDEBUG
                    KeyId = Task.get("Key", "")
                    Key = KeyId.lower()
                    OtherTask = True

                    if Key.startswith("refreshlibrary"):
                        if not utils.PauseRefreshLibrary:
                            continue

                        OtherTask = False
                    elif Key.startswith("refreshchapterimages"):
                        if not utils.PauseRefreshChapterImages:
                            continue

                        OtherTask = False
                    elif Key.startswith("vacuumdatabase") :
                        if not utils.PauseVacuumDatabase:
                            continue

                        OtherTask = False
                    elif Key.startswith("localthemevideosuploadtask"):
                        if not utils.PauseLocalThemeVideosUploadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("localthemesongsuploadtask"):
                        if not utils.PauseLocalThemeSongsUploadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("chapterapiupdateintrodb"):
                        if not utils.PauseChapterApiUpdateIntroDB:
                            continue

                        OtherTask = False
                    elif Key.startswith("tvmazeupdatetask"):
                        if not utils.PauseTvMazeUpdateTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("serversync"):
                        if not utils.PauseServerSync:
                            continue

                        OtherTask = False
                    elif Key.startswith("scaninternalmetadatafoldertask"):
                        if not utils.PauseScanInternalMetadataFolderTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("refreshinternetchannels"):
                        if not utils.PauseRefreshInternetChannels:
                            continue

                        OtherTask = False
                    elif Key.startswith("downloadsubtitles"):
                        if not utils.PauseDownloadSubtitles:
                            continue

                        OtherTask = False
                    elif Key.startswith("localytrailersdownloadtask"):
                        if not utils.PauseLocalYTrailersDownloadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("tvlocalthemesongdownloadtask"):
                        if not utils.PauseTVLocalThemeSongDownloadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("localthemevideosdownloadtask"):
                        if not utils.PauseLocalThemeVideosDownloadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("localthemesongsdownloadtask"):
                        if not utils.PauseLocalThemeSongsDownloadTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("markers"):
                        if not utils.PauseMarkers:
                            continue

                        OtherTask = False
                    elif Key.startswith("syncprepare"):
                        if not utils.PauseSyncPrepare:
                            continue

                        OtherTask = False
                    elif Key.startswith("embscriptxschedtask"):
                        if not utils.PauseEmbScriptxSchedTask:
                            continue

                        OtherTask = False
                    elif Key.startswith("refreshguide"):
                        if not utils.PauseRefreshGuide:
                            continue

                        OtherTask = False

                    if OtherTask and Key and not utils.PauseOther:
                        continue

                    if Task["State"] == "Running":
                        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): Emby server task running: {Task['Name']} / {KeyId} ]", 1) # LOGDEBUG

                        if Key == "refreshguide":
                            self.EPGRefresh = True

                        if Task["Name"] not in self.Tasks:
                            self.Tasks[Task["Name"]] = True

                            with utils.SafeLock(self.ProgressCondition):
                                self.ProgressCondition.notify_all()

                            if utils.busyMsg:
                                utils.create_ProgressBar(f"{self.RefreshTaskId}_{Task['Name']}", utils.Translate(33199), utils.Translate(33411))

                            self.EmbyServerSyncCheckIdleEvent.set()

                        if utils.busyMsg:
                            if 'CurrentProgressPercentage' in Task:
                                Progress = float(Task['CurrentProgressPercentage'])
                            else:
                                Progress = 0

                            utils.update_ProgressBar(f"{self.RefreshTaskId}_{Task['Name']}", Progress, utils.Translate(33199), f"{utils.Translate(33411)}: {Task['Name']}")
                    else:
                        if Task["Name"] in self.Tasks:
                            if self.Tasks[Task["Name"]]:
                                self.Tasks[Task["Name"]] = False

                                with utils.SafeLock(self.ProgressCondition):
                                    self.ProgressCondition.notify_all()

                                utils.close_ProgressBar(f"{self.RefreshTaskId}_{Task['Name']}")
            elif IncomingData['MessageType'] == 'RefreshProgress':
                if not utils.PauseRefreshProgress:
                    continue

                self.RefreshProgressRunning = True

                with utils.SafeLock(self.ProgressCondition):
                    self.ProgressCondition.notify_all()

                if not self.RefreshProgressInit:
                    self.RefreshProgressInit = True

                    if utils.busyMsg:
                        utils.create_ProgressBar(self.RefreshProgressId, utils.Translate(33199), utils.Translate(33411))

                    self.EmbyServerSyncCheckIdleEvent.set()

                if utils.busyMsg:
                    utils.update_ProgressBar(self.RefreshProgressId, float(IncomingData['Data']['Progress']), utils.Translate(33199), utils.Translate(33414))
            elif IncomingData['MessageType'] == 'UserDataChanged':
                xbmc.log(f"EMBY.hooks.websocket: [ Emby server {self.ServerData['ServerId']}: UserDataChanged ] {IncomingData['Data']['UserDataList']}", 1) # LOGINFO
                UpdateData = ()
                RemoveSkippedItems = ()

                if IncomingData['Data']['UserId'] != self.ServerData['UserId']:
                    if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): Emby server {self.ServerData['ServerId']}: UserDataChanged skip by wrong UserId: {IncomingData['Data']['UserId']}", 1) # LOGDEBUG
                    continue

                ItemsUserData = IncomingData['Data']['UserDataList']

                # Update cache
                for ItemData in ItemsUserData:
                    cache.update_userdata_Emby(ItemData.get("ItemId", None), self.ServerData['ServerId'], ItemData.get("PlaybackPositionTicks", None), ItemData.get("PlayCount", None), ItemData.get("IsFavorite", None), ItemData.get("Played", None), ItemData.get("LastPlayedDate", None), ItemData.get("PlayedPercentage", None)) # {'PlayedPercentage': 53.10315618015892, 'PlaybackPositionTicks': 13966544280, 'PlayCount': 2, 'IsFavorite': False, 'LastPlayedDate': '2026-09-28T18:47:57.0000000Z', 'Played': False, 'ItemId': '7956217'}

                if utils.RemoteMode:
                    xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: UserDataChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                embydb = dbio.DBOpenRO(self.ServerData['ServerId'], "UserDataChanged")
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

                for ItemData in ItemsUserData:
                    if ItemData['ItemId'] not in utils.ItemSkipUpdate:  # Filter skipped items
                        if ItemData['ItemId'] in ItemSkipUpdateAlbumIds:
                            xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: UserDataChanged skip by ItemSkipUpdate ancestors (AlbumId) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        elif ItemData['ItemId'] in ItemSkipUpdateAlbumSongIds:
                            xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: UserDataChanged skip by ItemSkipUpdate ancestors (AlbumSongId) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        else:
                            EpisodeEmbyPresentationKey = embydb.get_embypresentationkey_by_id_embytype(ItemData['ItemId'], ("Season", "Series")).split("_")[0]

                            if EpisodeEmbyPresentationKey in ItemSkipUpdateEmbyPresentationKeys:
                                xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: UserDataChanged skip by ItemSkipUpdate ancestors (PresentationKey) / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                            else:
#{'PlayedPercentage': 76.7570087715811, 'PlaybackPositionTicks': 10618910000, 'PlayCount': 1, 'IsFavorite': False, 'LastPlayedDate': '2025-05-01T14:17:15.0000000Z', 'Played': False, 'ItemId': '6534037'}, {'UnplayedItemCount': 62, 'PlaybackPositionTicks': 0, 'PlayCount': 0, 'IsFavorite': False, 'Played': False, 'ItemId': '5034684'}
                                UpdateData += ((ItemData['ItemId'], None, ItemData.get("PlaybackPositionTicks", None), ItemData.get("PlayCount", None), ItemData.get("IsFavorite", None), ItemData.get("Played", None), ItemData.get("LastPlayedDate", None), ItemData.get("PlayedPercentage", None), ItemData.get("UnplayedItemCount", None)),)
                    else:
                        xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: UserDataChanged skip by ItemSkipUpdate / Id: {ItemData['ItemId']} / ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
                        RemoveSkippedItems += (ItemData['ItemId'],)

                dbio.DBCloseRO(self.ServerData['ServerId'], "UserDataChanged")

                for RemoveSkippedItem in RemoveSkippedItems:
                    utils.ItemSkipUpdate.remove(RemoveSkippedItem)

                if UpdateData:
                    self.LibraryChangedQueue.put((("userdata", UpdateData),))
            elif IncomingData['MessageType'] == 'LibraryChanged':
                xbmc.log(f"EMBY.hooks.websocket: [ Emby server {self.ServerData['ServerId']}: LibraryChanged ] {IncomingData['Data']}", 1) # LOGINFO
                ItemsUpdated = IncomingData['Data']['ItemsUpdated'] + IncomingData['Data']['ItemsAdded']
                ItemsRemoved = IncomingData['Data']['ItemsRemoved']

                # Reset cache
                for ItemId in ItemsRemoved:
                    cache.remove(ItemId, self.ServerData['ServerId'])

                for ItemId in ItemsUpdated:
                    cache.remove(ItemId, self.ServerData['ServerId'])

                if utils.RemoteMode:
                    xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: LibraryChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                UpdateItemIds = len(ItemsUpdated) * [None] # preallocate memory

                for Index, ItemId in enumerate(ItemsUpdated):
                    UpdateItemIds[Index] = (ItemId, "unknown", "unknown")

                UpdateItemIds = list(dict.fromkeys(UpdateItemIds)) # filter duplicates

                if ItemsRemoved:
                    self.LibraryChangedQueue.put((("remove", IncomingData['Data']['ItemsRemoved']),))

                if UpdateItemIds:
                    self.LibraryChangedQueue.put((("update", UpdateItemIds),))
            elif IncomingData['MessageType'] == 'ServerRestarting':
                xbmc.log(f"EMBY.hooks.websocket: [ Emby server {self.ServerData['ServerId']}: ServerRestarting ]", 1) # LOGINFO
                self.close_EmbyServerBusy()

                if utils.restartMsg:
                    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33006), icon=utils.icon, time=utils.newContentTime)

                if self.ServerData['ServerId'] in utils.EmbyServers:
                    utils.EmbyServers[self.ServerData['ServerId']].ServerReconnect(False)
            elif IncomingData['MessageType'] == 'ServerShuttingDown':
                xbmc.log(f"EMBY.hooks.websocket: [ Emby server {self.ServerData['ServerId']}: ServerShuttingDown ]", 1) # LOGINFO
                self.close_EmbyServerBusy()
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33236), time=utils.newContentTime)

                if self.ServerData['ServerId'] in utils.EmbyServers:
                    utils.EmbyServers[self.ServerData['ServerId']].ServerReconnect(False)
            elif IncomingData['MessageType'] == 'RestartRequired':
                xbmc.log(f"EMBY.hooks.websocket: [ Emby server {self.ServerData['ServerId']}: RestartRequired ]", 1) # LOGINFO
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33237), time=utils.newContentTime)
            elif IncomingData['MessageType'] == 'Play':
                playerops.PlayEmby(True, IncomingData['Data']['ItemIds'], IncomingData['Data']['PlayCommand'], int(IncomingData['Data'].get('StartIndex', 0)), int(IncomingData['Data'].get('StartPositionTicks', -1)), self.ServerData, self.API, 0)
            elif IncomingData['MessageType'] == 'Playstate':
                if playerops.PlayerId != -1:
                    if IncomingData['Data']['Command'] == 'Seek':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, False)
                    elif IncomingData['Data']['Command'] == 'SeekRelative':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, True)
                    elif IncomingData['Data']['Command'] == "Stop":
                        playerops.Stop(True, False)
                    elif IncomingData['Data']['Command'] == "Unpause":
                        playerops.Unpause(True)
                    elif IncomingData['Data']['Command'] == "Pause":
                        playerops.Pause(True, 0, 0, True)
                    elif IncomingData['Data']['Command'] == "PlayPause": # Toggle pause
                        playerops.PauseToggle(True)
                    elif IncomingData['Data']['Command'] == "NextTrack":
                        playerops.Next()
                    elif IncomingData['Data']['Command'] == "PreviousTrack":
                        playerops.Previous()

                xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: Command: {IncomingData['Data']['Command']} / PlayedId: {playerops.PlayerId}", 1) # LOGINFO

        self.WebsocketRunning[0] = False

        with utils.SafeLock(self.ThreadsRunningCondition):
            self.ThreadsRunningCondition.notify_all()

        with utils.SafeLock(self.ProgressCondition):
            self.ProgressCondition.notify_all()

        self.EmbyServerSyncCheckIdleEvent.set()
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: ---<[ Emby server {self.ServerData['ServerId']}: message ]", 1) # LOGDEBUG

    def EmbyServerSyncCheck(self):
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: --->[ Emby server {self.ServerData['ServerId']}: EmbyServerSyncCheck ]", 1) # LOGINFO

        while True:
            while True:
                if self.EmbyServerSyncCheckIdleEvent.wait(timeout=0.1) or not self.WebsocketRunning[0] or utils.SystemShutdown:
                    break

            utils.update_SyncPause(self.library.ServerBusyId, True)
            if utils.DebugLog: xbmc.log("EMBY.hooks.websocket (DEBUG): CONDITION: --->[ ProgressCondition ]", 1)

            with utils.SafeLock(self.ProgressCondition):
                Compare = [False] * len(self.Tasks)

                while self.WebsocketRunning[0] and not utils.SystemShutdown and (self.RefreshProgressRunning or Compare != list(self.Tasks.values())):
                    self.RefreshProgressRunning = False
                    Wait = 40

                    while Wait > 0:
                        if self.ProgressCondition.wait(timeout=0.1) or utils.SystemShutdown:
                            break

                        Wait -= 1

                    Compare = list(self.Tasks.values())

            if utils.DebugLog: xbmc.log("EMBY.hooks.websocket (DEBUG): CONDITION: ---<[ ProgressCondition ]", 1)
            self.close_EmbyServerBusy()

            if self.WebsocketRunning[0] and not utils.SystemShutdown:
                utils.unset_SyncLock()

                if self.EPGRefresh:
                    self.library.SyncLiveTVEPG()
                    self.EPGRefresh = False

            if not self.WebsocketRunning[0] or utils.SystemShutdown:
                xbmc.log(f"EMBY.hooks.websocket: THREAD: ---<[ Emby server {self.ServerData['ServerId']}: EmbyServerSyncCheck ]", 1) # LOGINFO
                return

    def close_EmbyServerBusy(self):
        if utils.busyMsg:
            utils.close_ProgressBar(self.RefreshProgressId)

            for TaskName, TaskActive in list(self.Tasks.items()):
                if TaskActive:
                    utils.close_ProgressBar(f"{self.RefreshTaskId}_{TaskName}")

        self.Tasks = {}
        self.RefreshProgressInit = False
        self.EmbyServerSyncCheckIdleEvent.clear()

        with utils.SafeLock(self.ProgressCondition):
            self.ProgressCondition.notify_all()

        utils.update_SyncPause(self.library.ServerBusyId, False)

    def confirm_remote(self, SessionId, Timeout): # threaded
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: --->[ Emby server {self.ServerData['ServerId']}: Remote confirm ]", 1) # LOGDEBUG
        self.API.send_text_msg(SessionId, "remotecommand", f"support|{self.EmbySession[0]['Id']}", True)

        if utils.remotecontrol_auto_ack:
            Ack = True
        else:
            Ack = utils.Dialog.yesno(heading=utils.addon_name, message="Accept remote connection", autoclose=int(Timeout) * 1000, defaultbutton=11)

        if Ack: # send confirm msg
            playerops.Stop(False, True)
            self.API.send_text_msg(SessionId, "remotecommand", f"ack|{self.EmbySession[0]['Id']}|{self.EmbySession[0]['DeviceName']}|{self.EmbySession[0]['UserName']}", True)

        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: ---<[ Emby server {self.ServerData['ServerId']}: Remote confirm ]", 1) # LOGDEBUG

    def LibraryChanged(self):
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: --->[ Emby server {self.ServerData['ServerId']}: LibraryChangedQueue ]", 1) # LOGDEBUG

        while True:
            IncomingData = self.LibraryChangedQueue.get()

            if IncomingData == "QUIT":
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.websocket (DEBUG): THREAD: ---<[ Emby server {self.ServerData['ServerId']}: LibraryChangedQueue ]", 1) # LOGDEBUG
                break

            Unlock = False

            if IncomingData[0] == "remove":
                self.library.removed(IncomingData[1], True, False)
                Unlock = True
            elif IncomingData[0] == "update":
                self.library.updated(IncomingData[1], True, False)
                Unlock = True
            elif IncomingData[0] == "userdata":
                self.library.userdata(IncomingData[1], True, True)

            if Unlock:
                if self.EmbyServerSyncCheckIdleEvent.is_set():
                    xbmc.log(f"EMBY.hooks.websocket: Emby server {self.ServerData['ServerId']}: Sync in progress, delay updates", 1) # LOGINFO
                else:
                    utils.unset_SyncLock()

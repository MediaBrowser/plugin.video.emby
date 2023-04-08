from _thread import start_new_thread
import queue
import uuid
from urllib.parse import unquote_plus
import json
import xbmc
from database import dbio
from emby import listitem
from helper import utils, pluginmenu, playerops
from dialogs import skipintrocredits

PlaylistRemoveItem = -1
result = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}').get('result', {})
Volume = result.get('volume', 0)
Muted = result.get('muted', False)
NowPlayingQueue = [[], [], []]
PlaylistKodiItems = [[], [], []]
PlaySessionId = str(uuid.uuid4()).replace("-", "")
EmbyPlayerSessionOpen = False
PlayingItem = {}
QueuedPlayingItem = {}
EmbyServerPlayback = None
MultiselectionDone = False
TrailerPath = ""
playlistIndex = -1
SkipItem = False
KodiMediaType = ""
LibraryId = ""
PlayBackEnded = True
PlaybackStarted = False
IntroStartPositionTicks = 0
IntroEndPositionTicks = 0
CreditsPositionTicks = 0
LiveStreamId = None
SkipIntroJumpDone = False
SkipCreditsJumpDone = False
SkipAVChange = False
TasksRunning = []
PlayerEvents = queue.Queue()
SkipIntroDialog = skipintrocredits.SkipIntro("SkipIntroDialog.xml", *utils.CustomDialogParameters)
SkipIntroDialogEmbuary = skipintrocredits.SkipIntro("SkipIntroDialogEmbuary.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("SkipCreditsDialog.xml", *utils.CustomDialogParameters)

# Player events (queued by monitor notifications)
def PlayerCommands():
    while True:
        Commands = PlayerEvents.get()
        xbmc.log(f"EMBY.hooks.player: playercommand received: {Commands}", 1) # LOGINFO

        if Commands[0] == "QUIT":
            return

        if Commands[0] == "seek":
            xbmc.log("EMBY.hooks.player: [ onSeek ]", 1) # LOGINFO
            playerops.AVChange = False
            playerops.RemoteCommand(EmbyServerPlayback.ServerData['ServerId'], EmbyServerPlayback.EmbySession[0]['Id'], "seek")
        elif Commands[0] == "avchange":
            xbmc.log("EMBY.hooks.player: [ onAVChange ]", 1) # LOGINFO

            if EmbyServerPlayback and "ItemId" in PlayingItem and PlaybackStarted:
                globals()["PlayingItem"]['PositionTicks'] = playerops.PlayBackPosition()

            playerops.AVChange = True

            if SkipAVChange:
                xbmc.log("EMBY.hooks.player: skip onAVChange: SkipAVChange", 1) # LOGINFO
                globals()["SkipAVChange"] = False
                continue

            if EmbyServerPlayback and "ItemId" in PlayingItem:
                if PlaylistRemoveItem != -1 or SkipItem:
                    xbmc.log("EMBY.hooks.player: skip onAVChange", 0) # LOGDEBUG
                    continue

                if PlaybackStarted:
                    EmbyServerPlayback.API.session_progress(PlayingItem)
        elif Commands[0] == "avstart":
            xbmc.log("EMBY.hooks.player: --> [ onAVStarted ]", 1) # LOGINFO
            globals()["PlaybackStarted"] = True
            close_SkipIntroDialog()
            close_SkipCreditsDialog()
            EventData = json.loads(Commands[1])
            globals().update({"SkipIntroJumpDone": False, "SkipCreditsJumpDone": False})

            if not utils.syncduringplayback:
                utils.SyncPause['playing'] = True

            # Trailer from webserverice (addon mode)
            if SkipItem:
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] SkipItem", 1) # LOGINFO
                continue

            # 3D, ISO etc. content from webserverice (addon mode)
            if PlaylistRemoveItem != -1:
                playerops.RemovePlaylistItem(1, PlaylistRemoveItem)
                globals()["PlaylistRemoveItem"] = -1

            # Native mode multiselection
            if MultiselectionDone:
                globals()["MultiselectionDone"] = False
                xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] focus videoplayer", 1) # LOGINFO
                continue

            globals().update({"MediaType": "", "LibraryId": ""})
            EmbyId = None
            playerops.PlayerId = EventData['player']['playerid']
            FullPath = playerops.GetFilenameandpath()

            if not 'id' in EventData['item']:
                # Update player info for dynamic content (played via widget)
                for CacheList in list(pluginmenu.QueryCache.values()):
                    for ListItemCache in CacheList[1]:
                        if ListItemCache[0] == FullPath:
                            xbmc.log("EMBY.hooks.player: Update player info", 1) # LOGINFO
                            utils.XbmcPlayer.updateInfoTag(ListItemCache[1])
                            break

                pluginmenu.reset_querycache() # Clear Cache
            else:
                KodiId = EventData['item']['id']

            globals().update({"KodiMediaType": EventData['item']['type'], "LibraryId": ""})

            # Extract LibraryId from Path
            if FullPath and FullPath.startswith("http://127.0.0.1:57342"):
                Temp = FullPath.split("/")

                if len(Temp) > 5:
                    globals()["LibraryId"] = Temp[4]

            # extract path for bluray or iso (native mode)
            if utils.useDirectPaths and not FullPath:
                PlayingFile = utils.XbmcPlayer.getPlayingFile()

                if PlayingFile.startswith("bluray://"):
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = PlayingFile.replace("bluray://", "")
                    PlayingFile = PlayingFile.replace("udf://", "")
                    PlayingFile = PlayingFile[:PlayingFile.find("//")]

                    for server_id, EmbyServer in list(utils.EmbyServers.items()):
                        globals()["EmbyServerPlayback"] = EmbyServer
                        embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                        EmbyId = embydb.get_mediasource_EmbyID_by_path(PlayingFile)

                        if EmbyId:
                            FullPath = PlayingFile

                        dbio.DBCloseRO(server_id, "onAVStarted")

            # native mode
            if FullPath and not FullPath.startswith("http") and not FullPath.startswith("/emby_addon_mode/"):
                MediasourceID = ""

                for server_id, EmbyServer in list(utils.EmbyServers.items()):
                    globals()["EmbyServerPlayback"] = EmbyServer
                    embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                    item = embydb.get_item_by_KodiId_KodiType(KodiId, KodiMediaType)

                    if not item:
                        dbio.DBCloseRO(server_id, "onAVStarted")
                        xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no itme", 1) # LOGINFO
                        continue

                    EmbyId = item[0][0]

                    # Cinnemamode
                    if ((utils.enableCinemaMovies and item[0][3] == "movie") or (utils.enableCinemaEpisodes and item[0][3] == "episode")) and not playerops.RemoteMode:
                        if TrailerPath != "START_MAIN_CONTENT":
                            if TrailerPath != utils.XbmcPlayer.getPlayingFile():  # If not currently playing a trailer, initiate new trailers
                                playerops.Pause()
                                EmbyServerPlayback.http.Intros = []
                                PlayTrailer = True

                                if utils.askCinema:
                                    PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

                                if PlayTrailer:
                                    EmbyServerPlayback.http.load_Trailers(EmbyId)

                                if EmbyServerPlayback.http.Intros:
                                    globals().update({"playlistIndex": playerops.GetPlayerPosition(1), "SkipAVChange": True})
                                    play_Trailer()
                                    dbio.DBCloseRO(server_id, "onAVStarted")
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] native cinnemamode", 1) # LOGINFO
                                    continue

                                globals()["TrailerPath"] = ""
                                playerops.Unpause()
                        else:
                            globals()["TrailerPath"] = ""

                    # Multiversion
                    MediaSources = embydb.get_mediasource(EmbyId)
                    dbio.DBCloseRO(server_id, "onAVStarted")

                    if MediaSources and not playerops.RemoteMode: # video
                        MediasourceID = MediaSources[0][2]

                        if len(MediaSources) > 1:
                            playerops.Pause()
                            Selection = []

                            for MediaSource in MediaSources:
                                Selection.append(f"{MediaSource[4]} - {utils.SizeToText(float(MediaSource[5]))} - {MediaSource[3]}")

                            MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

                            if MediaIndex == -1:
                                Cancel()
                                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] cancel", 1) # LOGINFO
                                continue

                            if MediaIndex == 0:
                                playerops.Unpause()
                            else:
                                globals()["MultiselectionDone"] = True
                                Path = MediaSources[MediaIndex][3]

                                if Path.startswith('\\\\'):
                                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                                ListItem = load_KodiItem("onAVStarted", KodiId, KodiMediaType, Path)

                                if not ListItem:
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no listitem", 1) # LOGINFO
                                    continue

                                globals()["playlistIndex"] = playerops.GetPlayerPosition(1)
                                utils.Playlists[1].add(Path, ListItem, playlistIndex + 1)
                                MediasourceID = MediaSources[MediaIndex][2]
                                playerops.Next()
                                playerops.RemovePlaylistItem(1, playlistIndex)

                            break
                    else:
                        MediasourceID = ""

                if EmbyId:
                    queuePlayingItem(EmbyId, MediasourceID, item[0][12], item[0][13], item[0][14])

            globals().update({"PlayBackEnded": False, "PlayingItem": QueuedPlayingItem, "QueuedPlayingItem": {}})

            if EmbyServerPlayback and 'ItemId' in PlayingItem:
                if playerops.PlayerId == 1:
                    xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer

                if not playerops.RemoteMode:
                    playerops.ItemSkipUpdate += [PlayingItem['ItemId'], PlayingItem['ItemId'], PlayingItem['ItemId']] # triple add -> for Emby (2 times incoming msg) and once for Kodi database incoming msg

                xbmc.log(f"EMBY.hooks.player: PlayingItem: {PlayingItem}", 1) # LOGINFO
                PlaylistPosition = playerops.GetPlayerPosition(playerops.PlayerId)
                globals()["PlayingItem"].update({'RunTimeTicks': playerops.PlayBackDuration(), 'PositionTicks': playerops.PlayBackPosition(), "NowPlayingQueue": NowPlayingQueue[playerops.PlayerId], "PlaylistLength": len(NowPlayingQueue[playerops.PlayerId]), "PlaylistIndex": PlaylistPosition})

                if EmbyPlayerSessionOpen:
                    EmbyServerPlayback.API.session_progress(PlayingItem)
                else:
                    xbmc.log("EMBY.hooks.player: Emby playsession open", 1) # LOGINFO
                    EmbyServerPlayback.API.session_playing(PlayingItem)
                    globals()['EmbyPlayerSessionOpen'] = True

                xbmc.log(f"EMBY.hooks.player: ItemSkipUpdate: {playerops.ItemSkipUpdate}", 0) # LOGDEBUG
                playerops.AVStarted = True

                if "PositionTracker" not in TasksRunning:
                    start_new_thread(PositionTracker, ())

            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ]", 1) # LOGINFO
        elif Commands[0] == "playlistupdate":
            if not EmbyServerPlayback or 'ItemId' not in PlayingItem or playerops.PlayerId == -1:
                continue

            PlaylistPosition = playerops.GetPlayerPosition(playerops.PlayerId)
            globals()["PlayingItem"].update({"NowPlayingQueue": NowPlayingQueue[playerops.PlayerId], "PlaylistLength": len(NowPlayingQueue[playerops.PlayerId]), "PlaylistIndex": PlaylistPosition})
            EmbyServerPlayback.API.session_progress(PlayingItem)
        elif Commands[0] == "play":
            globals()["PlaybackStarted"] = False

            if not PlayBackEnded:
                xbmc.log("EMBY.hooks.player: [ Playback not stopped ]", 1) # LOGINFO
                stop_playback(True, False)

            xbmc.log("EMBY.hooks.player: [ onPlayBackStarted ]", 1) # LOGINFO

            if not utils.syncduringplayback:
                utils.SyncPause['playing'] = True
        elif Commands[0] == "pause":
            xbmc.log("EMBY.hooks.player: [ onPlayBackPaused ]", 1) # LOGINFO
            playerops.PlayerPause = True

            if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
                playerops.RemoteCommandActive[0] -= 1
                continue

            PositionTicks = playerops.PlayBackPosition()
            globals()["PlayingItem"].update({'PositionTicks': PositionTicks, 'IsPaused': True})
            playerops.RemoteCommand(EmbyServerPlayback.ServerData['ServerId'], EmbyServerPlayback.EmbySession[0]['Id'], "pause")
            EmbyServerPlayback.API.session_progress(PlayingItem)
            xbmc.log("EMBY.hooks.player: -->[ paused ]", 0) # LOGDEBUG
        elif Commands[0] == "resume":
            xbmc.log("EMBY.hooks.player: [ onPlayBackResumed ]", 1) # LOGINFO
            playerops.PlayerPause = False

            if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
                playerops.RemoteCommandActive[1] -= 1
                continue

            playerops.RemoteCommand(EmbyServerPlayback.ServerData['ServerId'], EmbyServerPlayback.EmbySession[0]['Id'], "unpause")
            globals()["PlayingItem"]['IsPaused'] = False
            EmbyServerPlayback.API.session_progress(PlayingItem)
            xbmc.log("EMBY.hooks.player: --<[ paused ]", 0) # LOGDEBUG
        elif Commands[0] == "stop":
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onPlayBackStopped ] {EventData}", 1) # LOGINFO
            utils.SyncPause['playing'] = False
            playerops.AVStarted = False
            playerops.EmbyIdPlaying = 0
            playerops.PlayerPause = False
            playerops.PlayerId = -1

            if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
                continue

            playerops.RemoteCommand(EmbyServerPlayback.ServerData['ServerId'], EmbyServerPlayback.EmbySession[0]['Id'], "stop")

            if EmbyPlayerSessionOpen:
                globals()['EmbyPlayerSessionOpen'] = False
                xbmc.log("EMBY.hooks.player: Emby playsession closed", 1) # LOGINFO
                EmbyServerPlayback.API.session_stop(PlayingItem)
                globals()['PlaySessionId'] = str(uuid.uuid4()).replace("-", "")

            if EventData['end']:
                stop_playback(True, False)
            else:
                stop_playback(True, True)

            xbmc.log("EMBY.hooks.player: --<[ playback ]", 1) # LOGINFO
        elif Commands[0] == "volume":
            EventData = json.loads(Commands[1])
            globals().update({"Muted": EventData["muted"], "Volume": EventData["volume"]})

            if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
                continue

            globals()["PlayingItem"].update({'VolumeLevel': Volume, 'IsMuted': Muted})
            EmbyServerPlayback.API.session_progress(PlayingItem)

def stop_playback(delete, Stopped):
    xbmc.log(f"EMBY.hooks.player: [ played info ] {PlayingItem} / {KodiMediaType}", 1) # LOGINFO
    PlayingItemLocal = PlayingItem.copy()
    globals()["PlaybackStarted"] = False

    if MultiselectionDone or not EmbyServerPlayback:
        return

    globals().update({"PlayBackEnded": True, "PlayingItem": {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}})

    # remove cached query for next up node
    if KodiMediaType == "episode" and LibraryId in EmbyServerPlayback.Views.ViewItems:
        CacheId = f"next_episodes_{EmbyServerPlayback.Views.ViewItems[LibraryId][0]}"
        xbmc.log(f"EMBY.hooks.player: [ played info cache Id ] {CacheId}", 1) # LOGINFO

        if CacheId in pluginmenu.QueryCache:
            xbmc.log("EMBY.hooks.player: [ played info clear cache ]", 1) # LOGINFO
            pluginmenu.QueryCache[CacheId][0] = False

    close_SkipIntroDialog()
    close_SkipCreditsDialog()

    # Trailer is playing, skip
    if SkipItem:
        return

    # Trailers for native content
    if not Stopped:
        # Play init item after native content trailer playback
        if TrailerPath and not EmbyServerPlayback.http.Intros:
            globals()["TrailerPath"] = "START_MAIN_CONTENT"
            EmbyServerPlayback.http.Intros = []
            playerops.PlayPlaylistItem(1, playlistIndex)
            return

        # play trailers for native content
        if EmbyServerPlayback.http.Intros:
            play_Trailer()
            return

    EmbyServerPlayback.http.Intros = []
    globals().update({"TrailerPath": "", "SkipAVChange": False})

    if 'ItemId' not in PlayingItemLocal:
        return

    # Set watched status
    Runtime = int(PlayingItemLocal['RunTimeTicks'])
    PlayPosition = int(PlayingItemLocal['PositionTicks'])

    if LiveStreamId:
        EmbyServerPlayback.API.close_livestream(LiveStreamId)

    if delete:
        if utils.offerDelete:
            if Runtime > 10:
                if PlayPosition > Runtime * 0.90:  # 90% Progress
                    DeleteMsg = False

                    if KodiMediaType == 'episode' and utils.deleteTV:
                        DeleteMsg = True
                    elif KodiMediaType == 'movie' and utils.deleteMovies:
                        DeleteMsg = True

                    if DeleteMsg:
                        xbmc.log("EMBY.hooks.player: Offer delete option", 1) # LOGINFO

                        if utils.Dialog.yesno(heading=utils.Translate(30091), message=utils.Translate(33015), autoclose=int(utils.autoclose) * 1000):
                            EmbyServerPlayback.API.delete_item(PlayingItemLocal['ItemId'])
                            EmbyServerPlayback.library.removed((PlayingItemLocal['ItemId'],))

    thread_sync_workers()

def play_Trailer(): # for native content
    Path = EmbyServerPlayback.http.Intros[0]['Path']
    li = listitem.set_ListItem(EmbyServerPlayback.http.Intros[0], EmbyServerPlayback.ServerData['ServerId'])
    del EmbyServerPlayback.http.Intros[0]

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    globals()["TrailerPath"] = Path
    li.setPath(Path)
    utils.XbmcPlayer.play(Path, li)

def PositionTracker():
    TasksRunning.append("PositionTracker")
    LoopCounter = 1
    xbmc.log("EMBY.hooks.player: THREAD: --->[ position tracker ]", 1) # LOGINFO

    while EmbyServerPlayback and "ItemId" in PlayingItem and not utils.SystemShutdown:
        if not utils.sleep(1):
            if PlayBackEnded:
                break

            Position = int(playerops.PlayBackPosition())

            if Position == -1:
                break

            xbmc.log(f"EMBY.hooks.player: PositionTracker: Position: {Position} / IntroStartPositionTicks: {IntroStartPositionTicks} / IntroEndPositionTicks: {IntroEndPositionTicks} / CreditsPositionTicks: {CreditsPositionTicks}", 0) # LOGDEBUG

            if utils.enableSkipIntro:
                if IntroEndPositionTicks and IntroStartPositionTicks < Position < IntroEndPositionTicks:
                    if not SkipIntroJumpDone:
                        globals()["SkipIntroJumpDone"] = True

                        if utils.askSkipIntro:
                            if utils.skipintroembuarydesign:
                                SkipIntroDialogEmbuary.show()
                            else:
                                SkipIntroDialog.show()
                        else:
                            jump_Intro()
                            LoopCounter = 0
                            continue
                else:
                    close_SkipIntroDialog()

            if utils.enableSkipCredits:
                if CreditsPositionTicks and Position > CreditsPositionTicks:
                    if not SkipCreditsJumpDone:
                        globals()["SkipCreditsJumpDone"] = True

                        if utils.askSkipCredits:
                            SkipCreditsDialog.show()
                        else:
                            jump_Credits()
                            LoopCounter = 0
                            continue
                else:
                    close_SkipCreditsDialog()

            if LoopCounter % 10 == 0: # modulo 10
                globals()["PlayingItem"]['PositionTicks'] = Position
                xbmc.log(f"EMBY.hooks.player: PositionTracker: Report progress {PlayingItem['PositionTicks']}", 0) # LOGDEBUG
                EmbyServerPlayback.API.session_progress(PlayingItem)
                LoopCounter = 0

            LoopCounter += 1

    TasksRunning.remove("PositionTracker")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ position tracker ]", 1) # LOGINFO

def jump_Intro():
    xbmc.log(f"EMBY.hooks.player: Skip intro jump {IntroEndPositionTicks}", 1) # LOGINFO
    playerops.Seek(IntroEndPositionTicks)
    globals()["PlayingItem"]['PositionTicks'] = IntroEndPositionTicks
    globals()["SkipIntroJumpDone"] = True
    EmbyServerPlayback.API.session_progress(PlayingItem)

def jump_Credits():
    xbmc.log(f"EMBY.hooks.player: Skip credits jump {CreditsPositionTicks}", 1) # LOGINFO
    playerops.Seek(CreditsPositionTicks)
    globals()["PlayingItem"]['PositionTicks'] = CreditsPositionTicks
    globals()["SkipCreditsJumpDone"] = True

def close_SkipIntroDialog():
    if utils.skipintroembuarydesign:
        if SkipIntroDialogEmbuary.dialog_open:
            SkipIntroDialogEmbuary.close()
    else:
        if SkipIntroDialog.dialog_open:
            SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

def queuePlayingItem(EmbyID, MediasourceID, IntroStartPosTicks, IntroEndPosTicks, CreditsPosTicks, LiveStreamID=None):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
    xbmc.log("EMBY.hooks.player: [ Queue playing item ]", 1) # LOGINFO
    globals()["LiveStreamId"] = LiveStreamID

    if not utils.syncduringplayback:
        utils.SyncPause['playing'] = True

    if IntroStartPosTicks:
        globals()["IntroStartPositionTicks"] = IntroStartPosTicks * 10000000
    else:
        globals()["IntroStartPositionTicks"] = 0

    if IntroEndPosTicks:
        globals()["IntroEndPositionTicks"] = IntroEndPosTicks * 10000000
    else:
        globals()["IntroEndPositionTicks"] = 0

    if CreditsPosTicks:
        globals()["CreditsPositionTicks"] = CreditsPosTicks * 10000000
    else:
        globals()["CreditsPositionTicks"] = 0

    globals()["QueuedPlayingItem"] = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(EmbyID), 'MediaSourceId': MediasourceID, 'PlaySessionId': PlaySessionId, 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}
    playerops.AVStarted = False
    playerops.EmbyIdPlaying = int(EmbyID)
    playerops.RemoteCommand(EmbyServerPlayback.ServerData['ServerId'], EmbyServerPlayback.EmbySession[0]['Id'], "play", EmbyID)

# Build NowPlayingQueue
def build_NowPlayingQueue():
    for PlaylistIndex in range(2):
        globals()['NowPlayingQueue'][PlaylistIndex] = []

        for Index, ItemId in enumerate(PlaylistKodiItems[PlaylistIndex]):
            globals()['NowPlayingQueue'][PlaylistIndex].append({"Id": int(ItemId), "PlaylistItemId": str(Index)})

def Cancel():
    playerops.Stop()
    utils.SyncPause['playing'] = False
    thread_sync_workers()

def load_KodiItem(TaskId, KodiItemId, Type, Path):
    videodb = dbio.DBOpenRO("video", TaskId)

    if Type == "movie":
        KodiItem = videodb.get_movie_metadata_for_listitem(KodiItemId, Path)
    elif Type == "episode":
        KodiItem = videodb.get_episode_metadata_for_listitem(KodiItemId, Path)
    elif Type == "musicvideo":
        KodiItem = videodb.get_musicvideos_metadata_for_listitem(KodiItemId, Path)
    else:
        KodiItem = {}

    dbio.DBCloseRO("video", TaskId)

    if KodiItem:
        return listitem.set_ListItem_from_Kodi_database(KodiItem, Path)[1]

    return None

def replace_playlist_listitem(ListItem, QueryData, Path):
    globals()["PlaylistRemoveItem"] = playerops.GetPlayerPosition(1) # old listitem will be removed after play next
    utils.Playlists[1].add(Path, ListItem, PlaylistRemoveItem + 1)
    queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])

# Sync jobs
def thread_sync_workers():
    if "sync_workers" not in TasksRunning and not playerops.RemoteMode:  # skip sync on remote client mode
        start_new_thread(sync_workers, ())

def sync_workers():
    TasksRunning.append("sync_workers")

    if not utils.sleep(2):
        for _, EmbyServer in list(utils.EmbyServers.items()):
            EmbyServer.library.RunJobs()

    TasksRunning.remove("sync_workers")

SkipIntroDialog.set_JumpFunction(jump_Intro)
SkipIntroDialogEmbuary.set_JumpFunction(jump_Intro)
SkipCreditsDialog.set_JumpFunction(jump_Credits)
start_new_thread(PlayerCommands, ())

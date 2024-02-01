from _thread import start_new_thread
import uuid
from urllib.parse import unquote_plus
import json
import xbmc
import xbmcgui
from database import dbio
from emby import listitem
from helper import utils, pluginmenu, playerops, queue
from dialogs import skipintrocredits


TrailerStatus = "READY"
PlaylistRemoveItem = -1
result = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}').get('result', {})
Volume = result.get('volume', 0)
Muted = result.get('muted', False)
NowPlayingQueue = [[], [], []]
PlaylistKodiItems = [[], [], []]
PlayingItem = [{}, None, None, None, None] # EmbySessionData (QueuedPlayingItem), IntroStartPositionTicks, IntroEndPositionTicks, CreditsPositionTicks, EmbyServer
QueuedPlayingItem = []
MultiselectionDone = False
playlistIndex = -1
KodiMediaType = ""
PlayBackEnded = True
SkipIntroJumpDone = False
SkipCreditsJumpDone = False
TasksRunning = []
PlayerEvents = queue.Queue()
SkipIntroDialog = skipintrocredits.SkipIntro("SkipIntroDialog.xml", *utils.CustomDialogParameters)
SkipIntroDialogEmbuary = skipintrocredits.SkipIntro("SkipIntroDialogEmbuary.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("SkipCreditsDialog.xml", *utils.CustomDialogParameters)

# Player events (queued by monitor notifications)
def PlayerCommands():
    xbmc.log("EMBY.hooks.player: THREAD: --->[ player commands ]", 0) # LOGDEBUG

    while True:
        Commands = PlayerEvents.get()
        xbmc.log(f"EMBY.hooks.player: playercommand received: {Commands}", 1) # LOGINFO

        if Commands == "QUIT":
            xbmc.log("EMBY.hooks.player: THREAD: ---<[ player commands ] quit", 0) # LOGDEBUG
            return

        if Commands[0] == "seek":
            xbmc.log("EMBY.hooks.player: [ onSeek ]", 1) # LOGINFO

            if not PlayingItem[0] or 'RunTimeTicks' not in PlayingItem[0]:
                continue

            EventData = json.loads(Commands[1])

            if EventData['player']['playerid'] != -1:
                playerops.PlayerId = EventData['player']['playerid']

            if 'player' in EventData and 'time' in EventData['player']:
                PositionTicks = (EventData['player']['time']['hours'] * 3600000 + EventData['player']['time']['minutes'] * 60000 + EventData['player']['time']['seconds'] * 1000 + EventData['player']['time']['milliseconds']) * 10000

                if int(PlayingItem[0]['RunTimeTicks']) < PositionTicks:
                    PlayingItem[0]['PositionTicks'] = PlayingItem[0]['RunTimeTicks']
                else:
                    PlayingItem[0]['PositionTicks'] = PositionTicks

            playerops.AVChange = False

            if PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "seek")
        elif Commands[0] == "avchange":
            xbmc.log("EMBY.hooks.player: [ onAVChange ]", 1) # LOGINFO

            if PlayingItem[0]:
                globals()["PlayingItem"][0]['PositionTicks'] = playerops.PlayBackPosition()

            playerops.AVChange = True
        elif Commands[0] == "avstart":
            xbmc.log("EMBY.hooks.player: --> [ onAVStarted ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])

            if EventData['player']['playerid'] != -1:
                playerops.PlayerId = EventData['player']['playerid']

            FullPath = playerops.GetFilenameandpath()

            if not FullPath:
                xbmc.log("EMBY.helper.player: XbmcPlayer no FullPath", 3) # LOGERROR
                continue

            PlaylistPosition, PositionTicks, RunTimeTicks = playerops.GetPlayerInfo(playerops.PlayerId) # Load player info as fast as possible
            close_SkipIntroDialog()
            close_SkipCreditsDialog()

            globals().update({"SkipIntroJumpDone": False, "SkipCreditsJumpDone": False})

            if not utils.syncduringplayback:
                utils.SyncPause['playing'] = True

            # 3D, ISO etc. content from webserverice (addon mode)
            if PlaylistRemoveItem != -1:
                playerops.RemovePlaylistItem(1, PlaylistRemoveItem)
                globals()["PlaylistRemoveItem"] = -1

            # Native mode multiselection
            if MultiselectionDone:
                globals()["MultiselectionDone"] = False

                if xbmcgui.getCurrentWindowId() != 12005:
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "fullscreenvideo"}}')  # focus videoplayer

                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] focus videoplayer", 1) # LOGINFO
                continue

            globals()["MediaType"] = ""
            EmbyId = None
            KodiId = None
            KodiType = None

            if playerops.PlayerId == -1: # workaround for Kodi bug after wake from sleep
                playerops.PlayerId = 1

            # Unsynced content: Update player info for dynamic/downloaded content (played via widget or themes or themes downloaded)
            if not 'id' in EventData['item']:
                isDynamic = FullPath.startswith("http://127.0.0.1:57342/dynamic/")
                isDynamicPathSubstitution = FullPath.startswith("/emby_addon_mode/dynamic/")
                isTheme = bool(FullPath.find("/EMBY-themes/") != -1)

                if isDynamic or isDynamicPathSubstitution or isTheme:
                    Separator = utils.get_Path_Seperator(FullPath)
                    Pos = FullPath.rfind(Separator)
                    Filename = FullPath[Pos + 1:]
                    Path = FullPath[:Pos]
                    SubIds = Filename.split("-")

                    if len(SubIds) > 1:
                        SubIds2 = Path.split(Separator)

                        if isDynamic:
                            ServerId = SubIds2[4]
                        elif isDynamicPathSubstitution:
                            ServerId = SubIds2[3]
                        elif isTheme:
                            ServerId = SubIds2[-2]

                        EmbyId = SubIds[1]
                        CachedItemFound = False

                        # Try to load from cache
                        for CachedItems in list(pluginmenu.QueryCache.values()):
                            if CachedItemFound:
                                break

                            for CachedContentItems in list(CachedItems.values()):
                                if CachedItemFound:
                                    break

                                for CachedItem in CachedContentItems[1]:
                                    if CachedItem[0] == FullPath:
                                        xbmc.log("EMBY.hooks.player: Update player info", 1) # LOGINFO

                                        if utils.XbmcPlayer.isPlaying():
                                            utils.XbmcPlayer.updateInfoTag(CachedItem[1])
                                        else:
                                            xbmc.log("EMBY.helper.player: XbmcPlayer not playing 1", 3) # LOGERROR
                                            continue

                                        KodiType = CachedItem[1].getProperty("KodiType")
                                        IntroStartPosTicks = 0
                                        IntroEndPosTicks = 0
                                        CachedItemFound = True
                                        break

                        # Load listitem for uncached content: e.g. for themes
                        if not CachedItemFound:
                            if SubIds[0] in ("A", "a"):
                                Item = utils.EmbyServers[ServerId].API.get_Item(EmbyId, ("Audio",), True, False, False)
                                ListItem = listitem.set_ListItem(Item, ServerId, FullPath)

                                if "Audio" not in pluginmenu.QueryCache:
                                    pluginmenu.QueryCache["Audio"] = {}

                                pluginmenu.QueryCache["Audio"]["Theme"] = [True, ((FullPath, ListItem, False), )]
                            else:
                                Item = utils.EmbyServers[ServerId].API.get_Item(EmbyId, ("Video",), True, False, False)
                                ListItem = listitem.set_ListItem(Item, ServerId, FullPath)

                                if "Video" not in pluginmenu.QueryCache:
                                    pluginmenu.QueryCache["Video"] = {}

                                pluginmenu.QueryCache["Video"]["Theme"] = [True, ((FullPath, ListItem, False), )]

                        if isTheme:
                            globals()["QueuedPlayingItem"] = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(EmbyId), 'MediaSourceId': None, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}, None, None, None, utils.EmbyServers[ServerId]]

                        if utils.XbmcPlayer.isPlaying():
                            utils.XbmcPlayer.updateInfoTag(ListItem)
                        else:
                            xbmc.log("EMBY.helper.player: XbmcPlayer not playing 2", 3) # LOGERROR
                            continue
            else:
                KodiId = EventData['item']['id']
                KodiType = EventData['item']['type']

            globals()["KodiMediaType"] = KodiType

            if KodiType and KodiType in utils.KodiTypeMapping:
                pluginmenu.reset_querycache(utils.KodiTypeMapping[KodiType])

            # native content
            if FullPath.startswith("bluray://"):
                FullPath = unquote_plus(FullPath)
                FullPath = unquote_plus(FullPath)
                FullPath = FullPath.replace("bluray://", "")
                FullPath = FullPath.replace("udf://", "")
                FullPath = FullPath[:FullPath.find("//")]

                for server_id, EmbyServer in list(utils.EmbyServers.items()):
                    embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                    EmbyId = embydb.get_mediasource_EmbyID_by_path(FullPath)
                    dbio.DBCloseRO(server_id, "onAVStarted")

            if not FullPath.startswith("http") and not FullPath.startswith("/emby_addon_mode/") and FullPath.find("/EMBY-themes/") == -1:
                MediasourceID = ""

                if not KodiId:
                    xbmc.log("EMBY.hooks.player: Kodi Id not found", 1) # LOGINFO
                    continue

                for server_id, EmbyServer in list(utils.EmbyServers.items()):
                    embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                    EmbyId, EmbyType, IntroStartPosTicks, IntroEndPosTicks = embydb.get_EmbyId_EmbyType_IntroStartPosTicks_IntroEndPosTicks_by_KodiId_KodiType(KodiId, KodiType)

                    if not EmbyId:
                        dbio.DBCloseRO(server_id, "onAVStarted")
                        xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no item", 1) # LOGINFO
                        continue

                    # Cinnemamode
                    if ((utils.enableCinemaMovies and EmbyType == "Movie") or (utils.enableCinemaEpisodes and EmbyType == "Episode")) and not playerops.RemoteMode:
                        if TrailerStatus == "READY":
                            playerops.Pause()
                            EmbyServer.http.Intros = []
                            PlayTrailer = True

                            if utils.askCinema:
                                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

                            if PlayTrailer:
                                EmbyServer.http.load_Trailers(EmbyId)

                            if EmbyServer.http.Intros:
                                globals()["playlistIndex"] = PlaylistPosition
                                play_Trailer(EmbyServer)
                                dbio.DBCloseRO(server_id, "onAVStarted")
                                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] native cinnemamode", 1) # LOGINFO
                                break

                            playerops.Unpause()
                        elif TrailerStatus == "CONTENT":
                            globals()["TrailerStatus"] = "READY"

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

                                globals()["playlistIndex"] = PlaylistPosition
                                utils.Playlists[1].add(Path, ListItem, playlistIndex + 1)
                                MediasourceID = MediaSources[MediaIndex][2]
                                playerops.Next()
                                playerops.RemovePlaylistItem(1, playlistIndex)

                            break
                    else:
                        MediasourceID = ""

                if EmbyServer.http.Intros:
                    continue

                if EmbyId:
                    globals()["QueuedPlayingItem"] = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(EmbyId), 'MediaSourceId': MediasourceID, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}, IntroStartPosTicks, IntroEndPosTicks, None, EmbyServer]

            # Load playback data
            load_queuePlayingItem()
            globals().update({"PlayBackEnded": False, "PlayingItem": QueuedPlayingItem, "QueuedPlayingItem": []})

            if PlayingItem[0]:
                if playerops.PlayerId == 1 and xbmcgui.getCurrentWindowId() != 12005:
                    xbmc.log("EMBY.hooks.player: Focus fullscreenvideo", 0) # DEBUGINFO
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "fullscreenvideo"}}')  # focus videoplayer

                if not playerops.RemoteMode:
                    utils.ItemSkipUpdate += [f"KODI{PlayingItem[0]['ItemId']}", PlayingItem[0]['ItemId']] # triple add -> for Emby (2 times incoming msg -> userdata changed) and once for Kodi database incoming msg -> VideoLibrary_OnUpdate; "KODI" prefix makes sure, VideoLibrary_OnUpdate is skipped even if more userdata requests from Emby server were received

                xbmc.log(f"EMBY.hooks.player: PlayingItem: {PlayingItem}", 1) # LOGINFO
                globals()["PlayingItem"][0].update({'RunTimeTicks': RunTimeTicks, 'PositionTicks': PositionTicks, "NowPlayingQueue": NowPlayingQueue[playerops.PlayerId], "PlaylistLength": len(NowPlayingQueue[playerops.PlayerId]), "PlaylistIndex": PlaylistPosition})
                PlayingItem[4].API.session_playing(PlayingItem[0])
                xbmc.log(f"EMBY.hooks.player: ItemSkipUpdate: {utils.ItemSkipUpdate}", 0) # LOGDEBUG
                playerops.AVStarted = True

                if "PositionTracker" not in TasksRunning:
                    start_new_thread(PositionTracker, ())

            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ]", 1) # LOGINFO
        elif Commands == "playlistupdate":
            if not PlayingItem[0] or playerops.PlayerId == -1:
                continue

            PlaylistPosition = playerops.GetPlayerPosition(playerops.PlayerId)
            globals()["PlayingItem"][0].update({"NowPlayingQueue": NowPlayingQueue[playerops.PlayerId], "PlaylistLength": len(NowPlayingQueue[playerops.PlayerId]), "PlaylistIndex": PlaylistPosition})
            PlayingItem[4].API.session_progress(PlayingItem[0])
        elif Commands[0] == "play":
            EventData = json.loads(Commands[1])

            if EventData['player']['playerid'] != -1:
                playerops.PlayerId = EventData['player']['playerid']

            if not utils.syncduringplayback or playerops.WatchTogether:
                utils.SyncPause['playing'] = True

            if not PlayBackEnded:
                xbmc.log("EMBY.hooks.player: [ Playback was not stopped ]", 1) # LOGINFO
                stop_playback(True, False)
        elif Commands == "pause":
            xbmc.log("EMBY.hooks.player: [ onPlayBackPaused ]", 1) # LOGINFO
            playerops.PlayerPause = True

            if not PlayingItem[0]:
                playerops.RemoteCommandActive[0] -= 1
                continue

            PositionTicks = playerops.PlayBackPosition()

            if PositionTicks == -1:
                continue

            globals()["PlayingItem"][0].update({'PositionTicks': PositionTicks, 'IsPaused': True})

            if PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "pause")

            PlayingItem[4].API.session_progress(PlayingItem[0])
            xbmc.log("EMBY.hooks.player: -->[ paused ]", 0) # LOGDEBUG
        elif Commands == "resume":
            xbmc.log("EMBY.hooks.player: [ onPlayBackResumed ]", 1) # LOGINFO
            playerops.PlayerPause = False

            if not PlayingItem[0]:
                playerops.RemoteCommandActive[1] -= 1
                continue

            if PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "unpause")

            globals()["PlayingItem"][0]['IsPaused'] = False
            PlayingItem[4].API.session_progress(PlayingItem[0])
            xbmc.log("EMBY.hooks.player: --<[ paused ]", 0) # LOGDEBUG
        elif Commands[0] == "stop":
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onPlayBackStopped ] {EventData}", 1) # LOGINFO
            utils.SyncPause['playing'] = False
            playerops.AVStarted = False
            playerops.EmbyIdPlaying = 0
            playerops.PlayerPause = False

            if 'item' in EventData and "type" in EventData['item'] and EventData['item']['type'] in utils.KodiTypeMapping:
                pluginmenu.reset_querycache(utils.KodiTypeMapping[EventData['item']['type']])

            if not PlayingItem[0]:
                continue

            if PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "stop")

            if EventData['end'] == "sleep":
                stop_playback(False, True)
            elif EventData['end']:
                stop_playback(True, False)
            else:
                stop_playback(True, True)

            xbmc.log("EMBY.hooks.player: --<[ playback ]", 1) # LOGINFO
        elif Commands[0] == "volume":
            EventData = json.loads(Commands[1])
            globals().update({"Muted": EventData["muted"], "Volume": EventData["volume"]})

            if not PlayingItem[0]:
                continue

            globals()["PlayingItem"][0].update({'VolumeLevel': Volume, 'IsMuted': Muted})
            PlayingItem[4].API.session_progress(PlayingItem[0])

    xbmc.log("EMBY.hooks.player: THREAD: ---<[ player commands ]", 0) # LOGDEBUG

def stop_playback(delete, Stopped):
    xbmc.log(f"EMBY.hooks.player: [ played info ] {PlayingItem} / {KodiMediaType}", 0) # LOGDEBUG
    PlayingItemLocal = PlayingItem.copy()

    if MultiselectionDone:
        xbmc.log("EMBY.hooks.player: stop_playback MultiselectionDone", 0) # LOGDEBUG
        return

    if not PlayingItemLocal[4]:
        xbmc.log("EMBY.hooks.player: stop_playback no PlayingItemLocal", 2) # LOGWARNING
        return

    PlayingItemLocal[4].API.session_stop(PlayingItemLocal[0])
    globals().update({"PlayBackEnded": True, "PlayingItem": [{}, None, None, None, None]})
    close_SkipIntroDialog()
    close_SkipCreditsDialog()

    if not Stopped and TrailerStatus == "PLAYING":
        if not PlayingItemLocal[4].http.Intros:
            PlayingItemLocal[4].http.Intros = []
            globals()["TrailerStatus"] = "CONTENT"
            playerops.PlayPlaylistItem(1, playlistIndex)
            return

        # play trailers for native content
        if PlayingItemLocal[4].http.Intros:
            play_Trailer(PlayingItemLocal[4])
            return

    globals()["TrailerStatus"] = "READY"
    PlayingItemLocal[4].http.Intros = []

    if not PlayingItem[0]:
        return

    utils.HTTPQueryDoublesFilter.pop(str(PlayingItemLocal[0]['ItemId']), None) # delete dict key if exists

    # Set watched status
    Runtime = int(PlayingItemLocal[0]['RunTimeTicks'])
    PlayPosition = int(PlayingItemLocal[0]['PositionTicks'])

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
                            PlayingItemLocal[4].API.delete_item(PlayingItemLocal[0]['ItemId'])
                            PlayingItemLocal[4].library.removed((PlayingItemLocal[0]['ItemId'],))

    thread_sync_workers()

def play_Trailer(EmbyServer): # for native content
    MediasourceID = EmbyServer.http.Intros[0]['MediaSources'][0]['Id']
    globals()["QueuedPlayingItem"] = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(EmbyServer.http.Intros[0]['Id']), 'MediaSourceId': MediasourceID, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}, None, None, None, EmbyServer]
    Path = EmbyServer.http.Intros[0]['Path']
    li = listitem.set_ListItem(EmbyServer.http.Intros[0], EmbyServer.ServerData['ServerId'])
    del EmbyServer.http.Intros[0]
    globals()["TrailerStatus"] = "PLAYING"
    li.setPath(Path)
    utils.XbmcPlayer.play(Path, li)

def PositionTracker():
    TasksRunning.append("PositionTracker")
    LoopCounter = 1
    xbmc.log("EMBY.hooks.player: THREAD: --->[ position tracker ]", 0) # LOGDEBUG

    while PlayingItem[0] and not utils.SystemShutdown:
        if not utils.sleep(1):
            if PlayBackEnded:
                break

            Position = int(playerops.PlayBackPosition())

            if Position == -1:
                break

            xbmc.log(f"EMBY.hooks.player: PositionTracker: Position: {Position} / IntroStartPositionTicks: {PlayingItem[1]} / IntroEndPositionTicks: {PlayingItem[2]} / CreditsPositionTicks: {PlayingItem[3]}", 0) # LOGDEBUG

            if utils.enableSkipIntro:
                if PlayingItem[1] and PlayingItem[1] < Position < PlayingItem[2]:
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
                if PlayingItem[3] and Position > PlayingItem[3]:
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
                globals()["PlayingItem"][0]['PositionTicks'] = Position
                xbmc.log(f"EMBY.hooks.player: PositionTracker: Report progress {PlayingItem[0]['PositionTicks']}", 0) # LOGDEBUG
                PlayingItem[4].API.session_progress(PlayingItem[0])
                LoopCounter = 0

            LoopCounter += 1

    TasksRunning.remove("PositionTracker")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ position tracker ]", 0) # LOGDEBUG

def jump_Intro():
    xbmc.log(f"EMBY.hooks.player: Skip intro jump {PlayingItem[2]}", 1) # LOGINFO
    playerops.Seek(PlayingItem[2])
    globals()["PlayingItem"][0]['PositionTicks'] = PlayingItem[2]
    globals()["SkipIntroJumpDone"] = True
    PlayingItem[4].API.session_progress(PlayingItem[0])

def jump_Credits():
    xbmc.log(f"EMBY.hooks.player: Skip credits jump {PlayingItem[3]}", 1) # LOGINFO
    playerops.Seek(PlayingItem[3])
    globals()["PlayingItem"][0]['PositionTicks'] = PlayingItem[3]
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

def load_queuePlayingItem():
    xbmc.log("EMBY.hooks.player: [ Queue playing item ]", 1) # LOGINFO

    if not playerops.RemoteMode:
        utils.ItemSkipUpdate += [int(QueuedPlayingItem[0]['ItemId'])] # triple add -> for Emby (2 times incoming msg -> userdata changed) and once for Kodi database incoming msg -> VideoLibrary_OnUpdate; "KODI" prefix makes sure, VideoLibrary_OnUpdate is skipped even if more userdata requests from Emby server were received

    if QueuedPlayingItem[1]:
        globals()["QueuedPlayingItem"][1] = QueuedPlayingItem[1] * 10000000
    else:
        globals()["QueuedPlayingItem"][1] = 0

    if QueuedPlayingItem[2]:
        globals()["QueuedPlayingItem"][2] = QueuedPlayingItem[2] * 10000000
    else:
        globals()["QueuedPlayingItem"][2] = 0

    if QueuedPlayingItem[3]:
        globals()["QueuedPlayingItem"][3] = QueuedPlayingItem[3] * 10000000
    else:
        globals()["QueuedPlayingItem"][3] = 0

    playerops.AVStarted = False
    playerops.EmbyIdPlaying = int(QueuedPlayingItem[0]['ItemId'])

    if QueuedPlayingItem[4].EmbySession:
        playerops.RemoteCommand(QueuedPlayingItem[4].ServerData['ServerId'], QueuedPlayingItem[4].EmbySession[0]['Id'], "play", QueuedPlayingItem[0]['ItemId'])

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
    globals()["QueuedPlayingItem"] = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(QueryData['EmbyID']), 'MediaSourceId': QueryData['MediasourceID'], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'], None]
    load_queuePlayingItem()

# Sync jobs
def thread_sync_workers():
    if "sync_workers" not in TasksRunning and not playerops.RemoteMode:  # skip sync on remote client mode
        start_new_thread(sync_workers, ())

def sync_workers():
    xbmc.log("EMBY.hooks.player: THREAD: --->[ sync worker ]", 0) # LOGDEBUG
    TasksRunning.append("sync_workers")

    if not utils.sleep(2):
        for _, EmbyServer in list(utils.EmbyServers.items()):
            EmbyServer.library.RunJobs()

    TasksRunning.remove("sync_workers")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ sync worker ]", 0) # LOGDEBUG

SkipIntroDialog.set_JumpFunction(jump_Intro)
SkipIntroDialogEmbuary.set_JumpFunction(jump_Intro)
SkipCreditsDialog.set_JumpFunction(jump_Credits)
start_new_thread(PlayerCommands, ())

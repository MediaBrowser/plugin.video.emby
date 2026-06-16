import threading
import random
import uuid
from urllib.parse import unquote_plus
import json
import xbmc
from database import dbio
from emby import listitem
from helper import utils, playerops, queue, cache
from dialogs import skipintrocredits
TrackerPaused = False
VideoPlayback = "READY"
VideoPlaybackOld = "READY"
PlaylistRemoveItem = -1
Volume = 100
Muted = False
CloseDialog = False
PlayItem = (0, "")
PlayerVolume = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}', False).get('result', {})

if PlayerVolume:
    Volume = PlayerVolume.get('volume', 100)
    Muted = PlayerVolume.get('muted', False)

RepeatMode = ['RepeatNone', 'RepeatNone', 'RepeatNone']
Shuffled = [False, False, False]
PlaybackRate = [1.0, 1.0, 1.0]
PlaylistKodi = [[], [], []]
PlaylistEmby = [[], [], []]
PlayingItem = [{}, 0, 0, 0, None, 0, "", ""] # EmbySessionData (QueuedPlayingItem), IntroStartPositionTicks, IntroEndPositionTicks, CreditsPositionTicks, EmbyServer, PlayerId, KodiMediaType, Filename
PlayingItemInit = [{}, 0, 0, 0, None, 0, "", ""]
QueuedPlayingItem = []
MultiselectionDone = False
PlaylistIndexContent = -2
EmbyPlaying = False
SkipIntroJumpDone = False
SkipCreditsJumpDone = False
PlayerBusyDelay = 5
Trailers = []
ItemKodiSkipUpdate = []
PlayerEventsQueue = queue.Queue()
ItemsUpdateQueue = queue.Queue()
SkipIntroDialog = skipintrocredits.SkipIntro("script-emby-skipintrodialog.xml", *utils.CustomDialogParameters)
SkipIntroDialogEmbuary = skipintrocredits.SkipIntro("script-emby-skipintrodialogembuary.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("script-emby-skipcreditsdialog.xml", *utils.CustomDialogParameters)
ForceStopKodiId = 0
ForceStopCondition = threading.Condition(threading.Lock())
ProgressBarEnable = -1

# Player events (queued by monitor notifications)
def PlayerCommands():
    if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): THREAD: --->[ player commands ]", 1) # LOGDEBUG
    global PlayerBusyDelay
    global TrackerPaused
    global SkipIntroJumpDone
    global SkipCreditsJumpDone
    global PlaylistRemoveItem
    global MultiselectionDone
    global QueuedPlayingItem
    global PlayingItemInit
    global Trailers
    global PlaylistIndexContent
    global VideoPlayback
    global EmbyPlaying
    global PlayingItem
    global CloseDialog
    global VideoPlaybackOld
    global PlayItem
    global ForceStopKodiId
    global Muted
    global Volume
    global ProgressBarEnable

    while True:
        Commands = PlayerEventsQueue.get()
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): playercommand received: {Commands}", 1) # LOGDEBUG

        if Commands == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): THREAD: ---<[ player commands ] quit", 1) # LOGDEBUG
            return

        PlayerBusyDelay = 5

        if Commands[0] == "seek": # {'item': {'id': 33874, 'type': 'episode'}, 'player': {'playerid': 1, 'seekoffset': {'hours': 0, 'milliseconds': 177, 'minutes': 41, 'seconds': 56}, 'speed': 1, 'time': {'hours': 0, 'milliseconds': 550, 'minutes': 47, 'seconds': 3}}}
            # Seekposition might not be exact. Don't use it as critical data e.g. do not use for remote playback seek, but good enough for the progress updates
            xbmc.log("EMBY.hooks.player: [ onSeek ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onSeek ] {EventData}", 1) # LOGDEBUG
            set_PlayerId(EventData)

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "seek")
                continue

            if 'player' in EventData and 'time' in EventData['player']:
                PlayingItem[0]['PositionTicks'] = (EventData['player']['time']['hours'] * 3600000 + EventData['player']['time']['minutes'] * 60000 + EventData['player']['time']['seconds'] * 1000 + EventData['player']['time']['milliseconds']) * 10000
                TrackerPaused = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])

            playerops.AVChange = False

            with utils.SafeLock(playerops.AVChangeCondition):
                playerops.AVChangeCondition.notify_all()

            if PlayingItem[4] and PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "seek")
        elif Commands[0] == "avchange": # {"item":{"id":12115,"type":"episode"},"player":{"playerid":1,"speed":1}}
            xbmc.log("EMBY.hooks.player: [ onAVChange ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onAVChange ] {EventData}", 1) # LOGDEBUG

            if "item" in EventData:
                if 'id' in EventData['item']:
                    if ForceStopKodiId == EventData["item"]["id"]:
                        if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): [ avchange/forced stop ]", 1) # LOGDEBUG
                        playerops.Stop(False)
                        continue

            set_PlayerId(EventData)
            playerops.AVChange = True

            with utils.SafeLock(playerops.AVChangeCondition):
                playerops.AVChangeCondition.notify_all()
        elif Commands[0] == "avstart": # ('avstart', '{"item":{"id":33874,"type":"episode"},"player":{"playerid":1,"speed":1}}')
            xbmc.log("EMBY.hooks.player: --> [ onAVStarted ]", 1) # LOGINFO
            playerops.AVStart = True
            EventData = json.loads(Commands[1])
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onAVStarted ] {EventData}", 1) # LOGDEBUG
            KodiId = 0
            KodiType = 0

            # Dummy (blankwav) played
            if "item" in EventData:
                if 'id' in EventData['item']:
                    KodiId = EventData['item']['id']
                    KodiType = EventData['item']['type']

                    if ForceStopKodiId == EventData["item"]["id"]:
                        if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): [ avstart/forced stop ]", 1) # LOGDEBUG
                        playerops.Stop(False, True)
                        continue

            set_PlayerId(EventData)
            FullPath = ""

            if KodiType != "channel":
                FullPath = playerops.GetPlayerFilepath()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): FullPath: {FullPath}", 1) # LOGDEBUG

                if not FullPath:
                    xbmc.log("EMBY.helper.player: No FullPath", 3) # LOGERROR
                    continue

            PlaylistPosition = playerops.GetPlaylistPosition(playerops.PlayerId)
            close_SkipIntroDialog()
            close_SkipCreditsDialog()
            SkipIntroJumpDone = False
            SkipCreditsJumpDone = False

            # 3D, ISO etc. content from webserverice (addon mode)
            if PlaylistRemoveItem != -1:
                playerops.RemovePlaylistItem(1, PlaylistRemoveItem)
                PlaylistRemoveItem = -1

            # multiselection done
            if MultiselectionDone:
                MultiselectionDone = False
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ]", 1) # LOGINFO
                continue

            EmbyId = None
            ServerId = None

            # Dynamic content
            if not KodiId:
                if not load_from_cache(FullPath, PlaylistPosition, ""): # Load QueuedPlayingItem, continue for multiversion
                    continue
            else:
                EmbyId, ServerId = utils.get_EmbyId_ServerId_by_Fake_KodiId(KodiId)

                if EmbyId and not load_from_cache(FullPath, PlaylistPosition, KodiType): # Load QueuedPlayingItem, continue for multiversion
                    continue

            if PlayingItem[0] and 'ItemId' in PlayingItem[0]:
                cache.update_querycache_userdata(((str(PlayingItem[0]['ItemId']), PlayingItem[0]['PositionTicks'], utils.currenttime(), -1, False),))

            # native (bluray) content, get actual path
            if FullPath.startswith("bluray://") and not EmbyId:
                FullPath = unquote_plus(FullPath)
                FullPath = unquote_plus(FullPath)
                FullPath = FullPath.replace("bluray://", "")
                FullPath = FullPath.replace("udf://", "")
                FullPath = FullPath[:FullPath.find("//")]

                for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                    embydb = dbio.DBOpenRO(ServerId, "onAVStarted")
                    EmbyId = embydb.get_mediasource_EmbyID_by_path_like(FullPath)
                    dbio.DBCloseRO(ServerId, "onAVStarted")

                    if EmbyId:
                        break

            # native content
            if not QueuedPlayingItem and not FullPath.startswith("dav://127.0.0.1:57342") and not FullPath.startswith("http://127.0.0.1:57342") and not FullPath.startswith("/emby_addon_mode/"):
                EmbyType = ""

                # load native mode played content from database
                for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                    embydb = dbio.DBOpenRO(ServerId, "onAVStarted")

                    if EmbyId: # could be a youtube video played via plugin://plugin.video.youtube/ -> FullPath http://192.168.0.50:50152/youtube/manifest/dash?file=W_cxASk1YMs.mpd
                        EmbyType = ""
                        IntroStartPosTicks = 0
                        IntroEndPosTicks = 0
                        CreditsStartPosTicks = 0
                    else:
                        EmbyId, EmbyType, IntroStartPosTicks, IntroEndPosTicks, CreditsStartPosTicks = embydb.get_nativemode_data(KodiId, KodiType)

                        if not EmbyId:
                            dbio.DBCloseRO(ServerId, "onAVStarted")
                            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no item", 1) # LOGINFO
                            continue

                    QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': embydb.get_mediasourceid_by_path(FullPath), 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStartPosTicks, IntroEndPosTicks, CreditsStartPosTicks, EmbyServer, playerops.PlayerId, KodiType, FullPath]

                    break

                # Select options for native played content
                if QueuedPlayingItem:
                    # Cinnemamode
                    if ((utils.enableCinemaMovies and EmbyType == "Movie") or (utils.enableCinemaEpisodes and EmbyType == "Episode")) and not utils.RemoteMode:
                        if VideoPlayback == "READY":
                            playerops.Pause()
                            Trailers = []
                            PlayTrailer = True

                            if utils.askCinema:
                                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

                            if PlayTrailer:
                                if load_Trailer(QueuedPlayingItem[4].ServerData['ServerId']):
                                    PlaylistIndexContent = PlaylistPosition
                                    playerops.Stop(False, True)
                                    play_Trailer(QueuedPlayingItem[4])
                                    dbio.DBCloseRO(ServerId, "onAVStarted")
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] native cinnemamode", 1) # LOGINFO
                                    init_EmbyPlayback()
                                    continue

                            playerops.Unpause()
                        elif VideoPlayback == "CONTENT":
                            VideoPlayback = "READY"

                    # Multiversion selection
                    MediaSources = embydb.get_mediasource(EmbyId)
                    VideoStreams = embydb.get_videostreams(EmbyId)
                    dbio.DBCloseRO(ServerId, "onAVStarted")

                    if len(MediaSources) > 1 and not utils.RemoteMode and not utils.SelectDefaultVideoversion:
                        if KodiType == "movie":
                            QueuedPlayingItem[7] = "" # disable delete after watched option for multicontent
                        else:
                            playerops.Pause()

                            # Autoselect mediasource by highest resolution
                            if utils.AutoSelectHighestResolution:
                                HighestResolution = 0
                                MediaIndex = 0

                                for MediaSourceIndex, MediaSource in enumerate(MediaSources):
                                    VideoStreamsWidth = int(VideoStreams[0][4]) # Resolution Width

                                    if HighestResolution < VideoStreamsWidth:
                                        HighestResolution = VideoStreamsWidth
                                        MediaIndex = MediaSourceIndex
                            else: # Manual select mediasource
                                Selection = []

                                for MediaSource in MediaSources:
                                    Selection.append(f"{MediaSource[3]} - {utils.SizeToText(float(MediaSource[4]))} - {MediaSource[2]}")

                                MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

                                if MediaIndex == -1:
                                    Cancel()
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] cancel", 1) # LOGINFO
                                    continue

                            if MediaIndex == 0: # Multiversion not changes
                                playerops.Unpause()
                            else: # Reload new multiversion
                                MultiselectionDone = True
                                Path = MediaSources[MediaIndex][2]

                                if Path.startswith('\\\\'):
                                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                                ListItem = load_KodiItem("onAVStarted", KodiId, KodiType, Path)

                                if not ListItem:
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no listitem", 1) # LOGINFO
                                    continue

                                PlaylistIndexContent = PlaylistPosition
                                utils.Playlists[1].add(Path, ListItem, PlaylistIndexContent + 1)
                                QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSources[MediaIndex][1], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, MediaSources[MediaIndex][5], MediaSources[MediaIndex][6], MediaSources[MediaIndex][7], QueuedPlayingItem[4], playerops.PlayerId, KodiType, ""]
                                playerops.Next()
                                playerops.RemovePlaylistItem(1, PlaylistIndexContent)

                    if Trailers:
                        continue

            if not QueuedPlayingItem:
                xbmc.log("EMBY.hooks.player: Playing unknown content 2", 1) # LOGINFO
                continue

            # Load playback data
            load_queuePlayingItem()
            EmbyPlaying = True
            PlayingItem = QueuedPlayingItem.copy()
            QueuedPlayingItem = []
            init_EmbyPlayback()

            if VideoPlayback == "CONTENT":
                VideoPlayback = "READY"

            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ]", 1) # LOGINFO
        elif Commands[0] == "play": # {"item":{"id":216,"type":"episode"},"player":{"playerid":1,"speed":1}}, '{"item":{"id":1100045814,"type":"song"},"player":{"playerid":-1,"speed":1}
            xbmc.log("EMBY.hooks.player: [ onPlay ]", 1) # LOGINFO
            PlayingItemInit = QueuedPlayingItem.copy()
            playerops.Stopped = False

            with utils.SafeLock(playerops.StoppedCondition):
                playerops.StoppedCondition.notify_all()

            if utils.PauseSyncDuringPlayback:
                utils.update_SyncPause('playing', True)
                utils.set_SyncLock()

            utils.closeall_ProgressBar()
            ProgressBarEnable = -1
            EventData = json.loads(Commands[1])
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onPlay ] {EventData}", 1) # LOGDEBUG

            if "item" in EventData:
                if 'id' in EventData['item']:
                    ItemKodiSkipUpdate.append([EventData['item']['id'], EventData['item']['type']])
                    PlayItem = (EventData['item']['id'], EventData['item']['type'])
                else:
                    PlayItem = (999999999, "unknown")
                    xbmc.log(f"EMBY.hooks.player: play no Id found: {EventData}", 2) # LOGWARNING

            set_PlayerId(EventData)

            if CloseDialog:
                utils.close_busyDialog(True)
                CloseDialog = False

            VideoPlaybackOld = VideoPlayback

            if EmbyPlaying:
                xbmc.log("EMBY.hooks.player: [ Playback was not stopped ]", 1) # LOGINFO
                stop_playback(True, False)
        elif Commands[0] == "playerid": # {"player":{"playerid":1,}}  # This is a custom command, not by Kodi events (youtube)
            xbmc.log("EMBY.hooks.player: [ onPlayerId ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onPlayerId ] {EventData}", 1) # LOGDEBUG
            set_PlayerId(EventData)
        elif Commands[0] == "pause": # {"item":{"id":22352,"type":"episode"},"player":{"playerid":1,"speed":0}}
            xbmc.log("EMBY.hooks.player: [ onPlayBackPaused ]", 1) # LOGINFO
            playerops.PlayerPause = True

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "pause")
                continue

            PositionTicks = playerops.PlayBackPosition()

            if PositionTicks:
                PlayingItem[0].update({'PositionTicks': PositionTicks, 'IsPaused': True})
            else:
                PlayingItem[0]['IsPaused'] = True

            if PlayingItem[4]:
                if PlayingItem[4].EmbySession:
                    playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "pause")

                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "Pause", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])

            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): -->[ paused ]", 1) # LOGDEBUG
        elif Commands[0] == "resume": # {"item":{"id":22352,"type":"episode"},"player":{"playerid":1,"speed":1}}
            xbmc.log("EMBY.hooks.player: [ onPlayBackResumed ]", 1) # LOGINFO
            playerops.PlayerPause = False

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "unpause")
                continue

            if PlayingItem[4]:
                if PlayingItem[4] and PlayingItem[4].EmbySession:
                    playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "unpause")

                PlayingItem[0]['IsPaused'] = False
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "Unpause", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
                TrackerPaused = True

            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): --<[ paused ]", 1) # LOGDEBUG
        elif Commands[0] == "stop": # {'end': True, 'item': {'id': 33874, 'type': 'episode'}}; '{"end":false,"item":{"id":107446349,"type":"song"}}'
            xbmc.log("EMBY.hooks.player: [ onPlayBackStopped ]", 1) # LOGINFO
            PlayItem = (0, "")
            EventData = json.loads(Commands[1])
            KodiId = 0
            KodiTypeId = 0
            utils.update_SyncPause('playing', False)
            utils.unset_SyncLock()
            ProgressBarEnable = 5

            if "item" in EventData: # remove from skipped items list
                if 'id' in EventData['item']:
                    KodiId = EventData["item"]["id"]
                    KodiTypeId = EventData["item"]["type"]

            if KodiId:
                if not EventData['end']: # remove from skipped items list
                    ItemsUpdateQueue.put(f'{{"DELETE": [{KodiId}, "{KodiTypeId}"]}}')  # Do not delete the item diectly from utils.ItemKodiSkipUpdate, to keep the events in order

                # Dummy (blankwav) played
                if ForceStopKodiId == EventData["item"]["id"]:
                    ForceStopKodiId = 0

                    with utils.SafeLock(ForceStopCondition):
                        ForceStopCondition.notify_all()

                    if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): [ forced stop ]", 1) # LOGDEBUG
                    continue

            if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ onPlayBackStopped ] {EventData}", 1) # LOGDEBUG
            playerops.AVStarted = False
            playerops.AVStart = False
            playerops.EmbyIdPlaying = 0
            playerops.PlayerPause = False

            with utils.SafeLock(playerops.AVStartedCondition):
                playerops.AVStartedCondition.notify_all()

            if not PlayingItem[0]: # Playback never triggered avstart
                if len(PlayingItemInit) >= 1 and PlayingItemInit[0]: # Play was triggered, but avstart never did. This can happen on invalid (livetv) streams.
                    if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): [ cancel session by PlayingItemInit ]", 1) # LOGDEBUG
                    PlayingItemInitLocal = PlayingItemInit.copy()
                    PlayingItemInit = [{}, 0, 0, 0, None, 0, "", ""]
                    PlayingItemInitLocal[4].API.session_stop(PlayingItemInitLocal[0], PlaylistKodi[PlayingItemInitLocal[5]], PlaylistEmby[PlayingItemInitLocal[5]])

                playerops.RemoteCommand(None, None, "stop")

                with utils.SafeLock(ForceStopCondition):
                    ForceStopCondition.notify_all()

                continue

            if PlayingItem[4] and PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "stop")

            VideoPlaybackOld = VideoPlayback

            if EventData['end'] == "quit":
                stop_playback(False, False)
            elif EventData['end']: # finished play and play next playlist item: {"end":true,"item":{"id":215,"type":"episode"}}
                stop_playback(True, True)
            else: # stopped in playlist: '{"end":false,"item":{"id":215,"type":"episode"}}'; play next item but playlist is at the end: '{"end":false,"item":{"type":"unknown"}}, -> playback failed
                stop_playback(True, False)

            with utils.SafeLock(ForceStopCondition):
                ForceStopCondition.notify_all()

            playerops.Stopped = True

            with utils.SafeLock(playerops.StoppedCondition):
                playerops.StoppedCondition.notify_all()

            xbmc.log("EMBY.hooks.player: --<[ playback ]", 1) # LOGINFO
        elif Commands[0] == "volume":
            EventData = json.loads(Commands[1])
            Muted = EventData["muted"]
            Volume = EventData["volume"]

            if not PlayingItem[0]:
                continue

            PlayingItem[0].update({'VolumeLevel': Volume, 'IsMuted': Muted})

            if PlayingItem[4]:
                TrackerPaused = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "VolumeChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "propertychanged":
            EventData = json.loads(Commands[1])

            if "repeat" in EventData['property']:
                Repeat = parse_repeat(EventData['property']['repeat'])
                PlayerId = EventData['player']['playerid']
                RepeatMode[PlayerId] = Repeat

                if PlayerId == playerops.PlayerId:
                    PlayingItem[0].update({'RepeatMode': RepeatMode[playerops.PlayerId]})

                    if PlayingItem[4]:
                        TrackerPaused = True
                        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "RepeatModeChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
            elif "shuffled" in EventData['property']:
                Shuffle = EventData['property']['shuffled']
                PlayerId = EventData['player']['playerid']
                Shuffled[PlayerId] = Shuffle

                if PlayerId == playerops.PlayerId:
                    PlayingItem[0].update({'Shuffle': Shuffled[playerops.PlayerId]})

                    if PlayingItem[4]:
                        TrackerPaused = True
                        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "ShuffleChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "speedchanged": # {"item":{"id":215,"type":"episode"},"player":{"playerid":1,"speed":2}}
            EventData = json.loads(Commands[1])
            Speed = EventData['player']['speed']
            PlayerId = EventData['player']['playerid']
            PlaybackRate[PlayerId] = float(Speed)

            if PlayerId == playerops.PlayerId:
                PlayingItem[0].update({'PlaybackRate': PlaybackRate[playerops.PlayerId]})

                if PlayingItem[4]:
                    TrackerPaused = True
                    PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaybackRateChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "clear": # '{"playlistid":1}'
            EventData = json.loads(Commands[1])
            PlaylistKodi[EventData['playlistid']] = []

            if PlayingItem[4]:
                TrackerPaused = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaylistItemRemove", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "remove": # '{"playlistid":1,"position":0}'
            EventData = json.loads(Commands[1])
            del PlaylistKodi[EventData['playlistid']][EventData['position']]

            if PlayingItem[4]:
                TrackerPaused = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaylistItemRemove", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "add": # unsyncd video = '{"item":{"id":1000018721,"type":"episode"},"playlistid":1,"position":0}'; synced video = '{"item":{"id":4268,"type":"episode"},"playlistid":1,"position":2}'; unsynced music = {"item":{"id":1000073262,"type":"song"},"playlistid":0,"position":0}; unsynced music external played e.g. via favorites'{"item":{"album":"Bella stella","artist":["Highland"],"title":"Bella stella","track":1,"type":"song"},"playlistid":0,"position":0}'; synced music = '{"item":{"id":233155,"type":"song"},"playlistid":0,"position":0}')
            EventData = json.loads(Commands[1])

            if 'id' in EventData['item']:
                PlaylistKodi[EventData['playlistid']].insert(EventData['position'], {"KodiId": EventData['item']['id'], "KodiType": EventData['item']['type']})

    if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): THREAD: ---<[ player commands ]", 1) # LOGDEBUG

def set_PlayerId(EventData):
    LocalPlayerId = -1

    if 'player' in EventData and 'playerid' in EventData['player']:
        LocalPlayerId = EventData['player']['playerid']

    if LocalPlayerId == -1 and 'item' in EventData and 'type' in EventData['item']:
        if EventData['item']['type'] == "song":
            LocalPlayerId = 0
        elif EventData['item']['type'] in ("episode", "video", "movie", "musicvideo"):
            LocalPlayerId = 1

    if LocalPlayerId != -1:
        playerops.PlayerId = LocalPlayerId

def parse_repeat(Data):
    if Data == "all":
        return "RepeatAll"

    if Data == "one":
        return "RepeatOne"

    return "RepeatNone"

def stop_playback(delete, PlaybackEnded):
    global TrackerPaused
    global VideoPlayback
    global Trailers
    global EmbyPlaying
    global PlayingItem

    if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): [ played info ] {PlayingItem}", 1) # LOGDEBUG
    PlayingItemLocal = PlayingItem.copy()
    TrackerPaused = False
    PlaybackRate[playerops.PlayerId] = 1.0

    if MultiselectionDone:
        if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): stop_playback MultiselectionDone", 1) # LOGDEBUG
        return

    if not PlayingItemLocal[4]:
        xbmc.log("EMBY.hooks.player: stop_playback no PlayingItemLocal", 2) # LOGWARNING
        return

    EmbyPlaying = False
    PlayingItem = [{}, 0, 0, 0, None, 0, "", ""]

    if PlaybackEnded and PlayingItemLocal[0]['RunTimeTicks']:
        PlayingItemLocal[0]['PositionTicks'] = PlayingItemLocal[0]['RunTimeTicks']

    cache.update_querycache_userdata(((str(PlayingItemLocal[0]['ItemId']), PlayingItemLocal[0]['PositionTicks'], utils.currenttime(), -1, PlaybackEnded),))

    if not utils.RemoteMode:
        utils.ItemSkipUpdate.append(str(PlayingItemLocal[0]['ItemId'])) # Skip Emby progress updates as Kodi keeps track

    PlaylistEmby[PlayingItemLocal[5]] = PlayingItemLocal[4].API.session_stop(PlayingItemLocal[0], PlaylistKodi[PlayingItemLocal[5]], PlaylistEmby[PlayingItemLocal[5]])
    close_SkipIntroDialog()
    close_SkipCreditsDialog()

    if PlaybackEnded and VideoPlaybackOld in ("TRAILER", "READY") and VideoPlayback == "TRAILER":
        if not Trailers: # Play initial item
            VideoPlayback = "CONTENT"
            playerops.PlayPlaylistItem(1, PlaylistIndexContent)
            return

        # play trailers
        play_Trailer(PlayingItemLocal[4])
        return

    if VideoPlayback != "TRAILERLOADING":
        VideoPlayback = "READY"
        Trailers = []

    if not PlayingItemLocal[0]:
        return

    # Set watched status
    RunTimeTicks = int(PlayingItemLocal[0]['RunTimeTicks'])
    PositionTicks = int(PlayingItemLocal[0]['PositionTicks'])

    if delete and PlayingItemLocal[7]:
        if utils.offerDelete:
            if RunTimeTicks > 10:
                if PositionTicks > RunTimeTicks * 0.90:  # 90% Progress
                    DeleteMsg = False

                    if PlayingItemLocal[6] == 'episode' and utils.deleteTV:
                        DeleteMsg = True
                    elif PlayingItemLocal[6] == 'movie' and utils.deleteMovies:
                        DeleteMsg = True

                    if DeleteMsg:
                        xbmc.log("EMBY.hooks.player: Offer delete option", 1) # LOGINFO

                        if utils.Dialog.yesno(heading=utils.Translate(33015), message=PlayingItemLocal[7], autoclose=int(utils.autoclose) * 1000):
                            PlayingItemLocal[4].API.delete_item(PlayingItemLocal[0]['ItemId'])
                            PlayingItemLocal[4].library.removed((PlayingItemLocal[0]['ItemId'],), True)

def load_Trailer(ServerId):
    global VideoPlayback
    global Trailers
    VideoPlayback = "TRAILERLOADING"
    FoundTrailers = []
    EmbyDB = dbio.DBOpenRO(ServerId, "LoadTrailer")

    if utils.trailer_local:
        FoundTrailers += EmbyDB.get_Trailers_local_random(utils.trailer_playback)

    if utils.trailer_local_folder:
        FoundTrailers += EmbyDB.get_Trailers_folder_random(utils.trailer_playback)

    if ServerId in utils.trailer_remote_options:
        if utils.trailer_remote_options[ServerId]["LocalMovie"]:
            FoundTrailers += EmbyDB.get_Trailers_remote_movie_random(utils.trailer_playback)

        if utils.trailer_remote_options[ServerId]["Option1"]["Enabled"]:
            FoundTrailers += EmbyDB.get_Trailers_remote_option_random(utils.trailer_remote_options[ServerId]["Option1"]["Id"], utils.trailer_playback)

        if utils.trailer_remote_options[ServerId]["Option2"]["Enabled"]:
            FoundTrailers += EmbyDB.get_Trailers_remote_option_random(utils.trailer_remote_options[ServerId]["Option2"]["Id"], utils.trailer_playback)

    dbio.DBCloseRO(ServerId, "LoadTrailer")

    if FoundTrailers:
        random.shuffle(FoundTrailers)
        FoundTrailers = FoundTrailers[:utils.trailer_playback]

        Trailers = len(FoundTrailers) * [{}] # pre allocate memory

        for Index, FoundTrailer in enumerate(FoundTrailers):
            Trailer = json.loads(FoundTrailer[0])
            Trailers[Index] = Trailer

        return True

    VideoPlayback = VideoPlaybackOld
    return False

def play_Trailer(EmbyServer):
    global QueuedPlayingItem
    global VideoPlayback
    MediaSourceId = None

    if 'MediaSources' in Trailers[0] and Trailers[0]['MediaSources']:
        MediaSourceId = Trailers[0]['MediaSources'][0]['Id']

    PlaySessionId = str(uuid.uuid4()).replace("-", "")
    QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(Trailers[0]['Id']), 'MediaSourceId': MediaSourceId, 'PlaySessionId': PlaySessionId, 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, None, None, None, EmbyServer, playerops.PlayerId, "", ""]
    PathLower = Trailers[0]['Path'].lower()

    if (PathLower.startswith("http://") or PathLower.startswith("https://")) and PathLower.find("youtube") != -1 and PathLower.find("plugin.video.youtube") == -1:
        Path = f"plugin://plugin.video.youtube/play/?video_id={Trailers[0]['Path'].rsplit('=', 1)[1]}"
    else:
        Container = Trailers[0].get('Container', 'ukn')

        if MediaSourceId:
            Path = f"{EmbyServer.ServerData['ServerUrl']}/emby/videos/{Trailers[0]['Id']}/stream.{Container}?static=true&MediaSourceId={MediaSourceId}&PlaySessionId={PlaySessionId}&DeviceId={EmbyServer.ServerData['DeviceId']}&api_key={EmbyServer.ServerData['AccessToken']}&stream.{Container}"
        else:
            Path = f"{EmbyServer.ServerData['ServerUrl']}/emby/videos/{Trailers[0]['Id']}/stream.{Container}?static=true&PlaySessionId={PlaySessionId}&DeviceId={EmbyServer.ServerData['DeviceId']}&api_key={EmbyServer.ServerData['AccessToken']}&stream.{Container}"

    # Play trailer
    ListItem = listitem.set_ListItem(Trailers[0], EmbyServer.ServerData['ServerId'], "", False)
    del Trailers[0]
    VideoPlayback = "TRAILER"
    ListItem.setPath(Path)
    playerops.Play(False, Path, ListItem, False, False)

def PositionTracker():
    global PlayerBusyDelay
    global SkipIntroJumpDone
    global SkipCreditsJumpDone
    global TrackerPaused
    global ProgressBarEnable
    LoopCounter = 1
    if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): THREAD: --->[ position tracker ]", 1) # LOGDEBUG
    PlayerBusy = False

    while True:
        # Enable progress bars 5 seconds after playback stop
        if ProgressBarEnable == 0:
            if utils.DebugLog: xbmc.log("EMBY.hooks.player [ position tracker ] eneable progress bars", 1) # LOGDEBUG
            utils.openall_ProgressBar()
            ProgressBarEnable = -1
        elif ProgressBarEnable > 0:
            ProgressBarEnable -= 1

        # Disable sync 2 seconds before stop and for 5 seconds after start
        if PlayerBusyDelay:
            PlayerBusyDelay -= 1

            if not PlayerBusy:
                if utils.PauseSyncDuringPlaybackStateChange:
                    utils.update_SyncPause('playerbusy', True)

                PlayerBusy = True
        elif PlayerBusy:
            utils.update_SyncPause('playerbusy', False)
            PlayerBusy = False

        if utils.sleep(1):
            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): THREAD: ---<[ position tracker ]", 1) # LOGDEBUG
            PlayerBusy = False
            return

        if not EmbyPlaying or not PlayingItem[0] or not PlayItem[0]:
            LoopCounter = 1
            continue

        PositionTicks = playerops.PlayBackPosition()
        RunTimeTicks = PlayingItem[0].get('RunTimeTicks', 0)

        if not RunTimeTicks:
            RunTimeTicks = playerops.PlayBackDuration()
            PlayingItem[0]['RunTimeTicks'] = RunTimeTicks

        if PositionTicks:
            PlayingItem[0]['PositionTicks'] = PositionTicks

        if RunTimeTicks and (PositionTicks + 20000000) > RunTimeTicks: # 2 seconds before playback ends pause updates
            PlayerBusyDelay = 5

        if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): PositionTracker: PositionTicks: {PositionTicks} / IntroStartPositionTicks: {PlayingItem[1]} / IntroEndPositionTicks: {PlayingItem[2]} / CreditsPositionTicks: {PlayingItem[3]} / SkipIntroJumpDone: {SkipIntroJumpDone}", 1) # LOGDEBUG

        if utils.enableSkipIntro:
            if PlayingItem[1] < PositionTicks < PlayingItem[2]:
                if not SkipIntroJumpDone:
                    SkipIntroJumpDone = True

                    if utils.askSkipIntro:
                        if utils.skipintroembuarydesign:
                            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): --->[ SkipIntroDialogEmbuary ]", 1) # LOGDEBUG
                            SkipIntroDialogEmbuary.show()
                        else:
                            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): --->[ SkipIntroDialog ]", 1) # LOGDEBUG
                            SkipIntroDialog.show()
                    else:
                        jump_Intro()
                        LoopCounter = 0
                        continue
            else:
                close_SkipIntroDialog()

        if utils.enableSkipCredits:
            if PlayingItem[3] and PositionTicks > PlayingItem[3]:
                if not SkipCreditsJumpDone:
                    SkipCreditsJumpDone = True

                    if utils.askSkipCredits:
                        SkipCreditsDialog.show()
                    else:
                        jump_Credits()
                        LoopCounter = 0
                        continue
            else:
                close_SkipCreditsDialog()

        if LoopCounter % 50 == 0 and PlayingItem[4]: # modulo 50
            if not TrackerPaused:
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): PositionTracker: Report progress {PlayingItem[0]['PositionTicks']}", 1) # LOGDEBUG
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
            else:
                TrackerPaused = False

            LoopCounter = 0

        LoopCounter += 1

def jump_Intro():
    global SkipIntroJumpDone
    global TrackerPaused
    xbmc.log(f"EMBY.hooks.player: Skip intro jump {PlayingItem[2]}", 1) # LOGINFO

    if PlayingItem[4]:
        playerops.Seek(PlayingItem[2])
        PlayingItem[0]['PositionTicks'] = PlayingItem[2]
        SkipIntroJumpDone = True
        TrackerPaused = True
        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
    else:
        xbmc.log(f"EMBY.hooks.player: Skip intro jump error: {PlayingItem}", 3) # LOGERROR

def jump_Credits():
    global SkipCreditsJumpDone

    if PlayingItem[0].get('RunTimeTicks', 0):
        xbmc.log(f"EMBY.hooks.player: Skip credits jump {PlayingItem[0]['RunTimeTicks']}", 1) # LOGINFO
        playerops.Seek(PlayingItem[0]['RunTimeTicks'])
        PlayingItem[0]['PositionTicks'] = PlayingItem[0]['RunTimeTicks']
        SkipCreditsJumpDone = True
    else:
        xbmc.log("EMBY.hooks.player: Skip credits, invalid RunTimeTicks", 1) # LOGINFO

def close_SkipIntroDialog():
    if utils.skipintroembuarydesign:
        if SkipIntroDialogEmbuary.dialog_open:
            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): ---<[ SkipIntroDialogEmbuary ]", 1) # LOGDEBUG
            SkipIntroDialogEmbuary.close()
    else:
        if SkipIntroDialog.dialog_open:
            if utils.DebugLog: xbmc.log("EMBY.hooks.player (DEBUG): ---<[ SkipIntroDialog ]", 1) # LOGDEBUG
            SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

def load_queuePlayingItem():
    global PlayerBusyDelay
    if utils.DebugLog: xbmc.log("EMBY.hooks.player: [ Queue playing item ]", 1) # LOGINFO
    PlayerBusyDelay = 5

    if QueuedPlayingItem[1]:
        QueuedPlayingItem[1] = QueuedPlayingItem[1] * 10000000
    else:
        QueuedPlayingItem[1] = 0

    if QueuedPlayingItem[2]:
        QueuedPlayingItem[2] = QueuedPlayingItem[2] * 10000000
    else:
        QueuedPlayingItem[2] = 0

    if QueuedPlayingItem[3]:
        QueuedPlayingItem[3] = QueuedPlayingItem[3] * 10000000
    else:
        QueuedPlayingItem[3] = 0

    playerops.AVStarted = False
    playerops.EmbyIdPlaying = int(QueuedPlayingItem[0]['ItemId'])

    with utils.SafeLock(playerops.AVStartedCondition):
        playerops.AVStartedCondition.notify_all()

    if QueuedPlayingItem[4] and QueuedPlayingItem[4].EmbySession:
        playerops.RemoteCommand(QueuedPlayingItem[4].ServerData['ServerId'], QueuedPlayingItem[4].EmbySession[0]['Id'], "play", QueuedPlayingItem[0]['ItemId'])

def Cancel():
    playerops.Stop()
    utils.update_SyncPause('playing', False)
    utils.unset_SyncLock()

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

def replace_playlist_listitem(ListItem, Path):
    global PlaylistRemoveItem
    PlaylistRemoveItem = playerops.GetPlaylistPosition(1) # old listitem will be removed after play next
    utils.Playlists[1].add(Path, ListItem, PlaylistRemoveItem + 1)
    load_queuePlayingItem()

def load_from_cache(FullPath, PlaylistPosition, KodiType):
    global MultiselectionDone
    global PlaylistIndexContent
    global QueuedPlayingItem

    with utils.SafeLock(cache.CacheLock):
        CachedListitem = cache.PathItemIndex.get(FullPath)

    if CachedListitem:
        xbmc.log("EMBY.hooks.player: Update player info", 1)

        if not playerops.UpdateInfoTag(CachedListitem):
            xbmc.log("EMBY.helper.player: Player not playing 1", 3)
            return False

        KodiType = CachedListitem.getProperty("KodiType")
        ServerId = CachedListitem.getProperty("embyserverid")
        EmbyId = CachedListitem.getProperty("embyid")
        MediaSourcesCount = int(CachedListitem.getProperty("mediasourcescount"))
        MediaSourceIds = []
        MediaSourceSize = []
        MediaSourceName = []
        MediaSourcePath = []
        IntroStart = []
        IntroEnd = []
        CreditsStart = []

        for i in range(MediaSourcesCount):
            MediaSourceIds.append(CachedListitem.getProperty(f"embymediacourceid{i}"))
            MediaSourceSize.append(int(CachedListitem.getProperty(f"embymediacourcesize{i}")))
            MediaSourceName.append(CachedListitem.getProperty(f"embymediacourcename{i}"))
            MediaSourcePath.append(CachedListitem.getProperty(f"embymediacourcepath{i}"))
            IntroStart.append(int(CachedListitem.getProperty(f"embyintrostartposticks{i}")))
            IntroEnd.append(int(CachedListitem.getProperty(f"embyintroendpositionticks{i}")))
            CreditsStart.append(int(CachedListitem.getProperty(f"embycreditspositionticks{i}")))

        if MediaSourcesCount > 1 and not utils.RemoteMode:
            playerops.Pause()
            Selection = []

            for i in range(MediaSourcesCount):
                Selection.append(f"{MediaSourceName[i]} - {utils.SizeToText(float(MediaSourceSize[i]))} - {MediaSourcePath[i]}")

            MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

            if MediaIndex == -1:
                Cancel()
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] cancel", 1)
                return False

            if MediaIndex == 0:
                playerops.Unpause()
            else:
                MultiselectionDone = True
                Path = MediaSourcePath[MediaIndex]

                if Path.startswith('\\\\'):
                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                CachedListitem.setPath(Path)
                PlaylistIndexContent = PlaylistPosition
                utils.Playlists[1].add(Path, CachedListitem, PlaylistIndexContent + 1)
                QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSourceIds[MediaIndex], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStart[MediaIndex], IntroEnd[MediaIndex], CreditsStart[MediaIndex], utils.EmbyServers[ServerId], playerops.PlayerId, KodiType, FullPath]
                playerops.Next()
                playerops.RemovePlaylistItem(1, PlaylistIndexContent)

            return False

        QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSourceIds[0], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStart[0], IntroEnd[0], CreditsStart[0], utils.EmbyServers[ServerId], playerops.PlayerId, KodiType, FullPath]

    return True

def init_EmbyPlayback():
    if PlayingItem[0]:
        RunTimeTicks = playerops.PlayBackDuration()
        PositionTicks = playerops.PlayBackPosition()
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): PlayingItem: {PlayingItem}", 1) # LOGDEBUG
        PlayingItem[0].update({'RunTimeTicks': RunTimeTicks, 'PositionTicks': PositionTicks})

        if PlayingItem[4]:
            if not utils.RemoteMode:
                utils.ItemSkipUpdate.append(str(PlayingItem[0]['ItemId'])) # Skip Emby progress updates as Kodi keeps track

            PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_playing(PlayingItem[0], PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        else:
            xbmc.log(f"EMBY.hooks.player: avstart error: {PlayingItem}", 3) # LOGERROR

        if utils.DebugLog: xbmc.log(f"EMBY.hooks.player (DEBUG): ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGDEBUG
        playerops.AVStarted = True

        with utils.SafeLock(playerops.AVStartedCondition):
            playerops.AVStartedCondition.notify_all()

Ret = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties", "params": {"playerid": 0, "properties": ["repeat", "shuffled"]}}', False).get('result', {})
RepeatMode[0] = parse_repeat(Ret.get("repeat", "off"))
Shuffled[0] = Ret.get("shuffled", False)
Ret = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties", "params": {"playerid": 1, "properties": ["repeat", "shuffled"]}}', False).get('result', {})
RepeatMode[1] = parse_repeat(Ret.get("repeat", "off"))
Shuffled[1] = Ret.get("shuffled", False)
Ret = utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties", "params": {"playerid": 2, "properties": ["repeat", "shuffled"]}}', False).get('result', {})
RepeatMode[2] = parse_repeat(Ret.get("repeat", "off"))
Shuffled[2] = Ret.get("shuffled", False)
SkipIntroDialog.set_JumpFunction(jump_Intro)
SkipIntroDialogEmbuary.set_JumpFunction(jump_Intro)
SkipCreditsDialog.set_JumpFunction(jump_Credits)
utils.start_thread(PlayerCommands, ())
utils.start_thread(PositionTracker, ())

import uuid
import os
from urllib.parse import unquote_plus, unquote
import json
import xbmc
from database import dbio
from emby import listitem
from helper import utils, playerops, queue
from dialogs import skipintrocredits

XbmcPlayer = xbmc.Player()  # Init Player
TrackerPaused = False
SkipItem = ()
TrailerStatus = "READY"
PlaylistRemoveItem = -1
Volume = 100
Muted = False
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
QueuedPlayingItem = []
MultiselectionDone = False
playlistIndex = -1
EmbyPlaying = False
PlaybackEndedForced = False
SkipIntroJumpDone = False
SkipCreditsJumpDone = False
TasksRunning = []
PlayerBusyDelay = 5
PlayerEventsQueue = queue.Queue()
SkipIntroDialog = skipintrocredits.SkipIntro("script-emby-skipintrodialog.xml", *utils.CustomDialogParameters)
SkipIntroDialogEmbuary = skipintrocredits.SkipIntro("script-emby-skipintrodialogembuary.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("script-emby-skipcreditsdialog.xml", *utils.CustomDialogParameters)

# Player events (queued by monitor notifications)
def PlayerCommands():
    xbmc.log("EMBY.hooks.player: THREAD: --->[ player commands ]", 0) # LOGDEBUG

    while True:
        Commands = PlayerEventsQueue.get()
        xbmc.log(f"EMBY.hooks.player: playercommand received: {Commands}", 0) # LOGDEBUG

        if Commands == "QUIT":
            xbmc.log("EMBY.hooks.player: THREAD: ---<[ player commands ] quit", 0) # LOGDEBUG
            return

        PlayerBusy()

        if Commands[0] == "seek": # {'item': {'id': 33874, 'type': 'episode'}, 'player': {'playerid': 1, 'seekoffset': {'hours': 0, 'milliseconds': 177, 'minutes': 41, 'seconds': 56}, 'speed': 1, 'time': {'hours': 0, 'milliseconds': 550, 'minutes': 47, 'seconds': 3}}}
            # Seekposition might not be exact. Don't use it as critical data e.g. do not use for remote playback seek, but good enough for the progress updates
            xbmc.log("EMBY.hooks.player: [ onSeek ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onSeek ] {EventData}", 0) # LOGDEBUG
            set_PlayerId(EventData)

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "seek")
                continue

            if 'player' in EventData and 'time' in EventData['player']:
                PlayingItem[0]['PositionTicks'] = (EventData['player']['time']['hours'] * 3600000 + EventData['player']['time']['minutes'] * 60000 + EventData['player']['time']['seconds'] * 1000 + EventData['player']['time']['milliseconds']) * 10000

                # Workaround for Kodi bug seekposition higher than runtime
                if 'RunTimeTicks' in PlayingItem[0] and int(PlayingItem[0]['RunTimeTicks']) < PlayingItem[0]['PositionTicks']:
                    PlayingItem[0]['PositionTicks'] = PlayingItem[0]['RunTimeTicks']
                    PlaylistPosition = playerops.GetPlayerPosition(playerops.PlayerId)
                    globals()['PlaybackEndedForced'] = True
                    playerops.Stop(False, playerops.PlayerId)
                    PlaylistSize = playerops.GetPlaylistSize(playerops.PlayerId)
                    PlaylistPosition += 1

                    if TrailerStatus != "PLAYING" and PlaylistPosition < PlaylistSize:
                        playerops.PlayPlaylistItem(playerops.PlayerId, PlaylistPosition)

                        if playerops.PlayerId == 1:
                            utils.ActivateWindow("fullscreenvideo", "", False)

                    continue

                globals()["TrackerPaused"] = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])

            playerops.AVChange = False

            if PlayingItem[4] and PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "seek")
        elif Commands[0] == "avchange": # {"item":{"id":12115,"type":"episode"},"player":{"playerid":1,"speed":1}}
            xbmc.log("EMBY.hooks.player: [ onAVChange ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onAVChange ] {EventData}", 0) # LOGDEBUG
            set_PlayerId(EventData)
            playerops.AVChange = True
        elif Commands[0] == "avstart": # ('avstart', '{"item":{"id":33874,"type":"episode"},"player":{"playerid":1,"speed":1}}')
            xbmc.log("EMBY.hooks.player: --> [ onAVStarted ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onAVStarted ] {EventData}", 0) # LOGDEBUG
            set_PlayerId(EventData)
            FullPath = ""

            try:
                FullPath = XbmcPlayer.getPlayingFile()
            except Exception as Error:
                xbmc.log(f"EMBY.helper.player: getPlayingFile issue {Error}", 3) # LOGERROR

            xbmc.log(f"EMBY.hooks.player: FullPath: {FullPath}", 0) # LOGDEBUG

            if not FullPath:
                xbmc.log("EMBY.helper.player: XbmcPlayer no FullPath", 3) # LOGERROR
                continue

            PlaylistPosition, PositionTicks, RunTimeTicks = playerops.GetPlayerInfo(playerops.PlayerId) # Load player info as fast as possible
            close_SkipIntroDialog()
            close_SkipCreditsDialog()

            globals().update({"SkipIntroJumpDone": False, "SkipCreditsJumpDone": False})

            if not utils.PauseSyncDuringPlayback:
                utils.SyncPause['playing'] = True

            # 3D, ISO etc. content from webserverice (addon mode)
            if PlaylistRemoveItem != -1:
                playerops.RemovePlaylistItem(1, PlaylistRemoveItem)
                globals()["PlaylistRemoveItem"] = -1

            # multiselection done
            if MultiselectionDone:
                globals()["MultiselectionDone"] = False
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] focus videoplayer", 1) # LOGINFO
                continue

            EmbyId = None
            KodiId = None
            ServerId = None
            KodiType = ""

            # Dynamic content
            if 'id' not in EventData['item']:
                if FullPath.find("/emby-themes-") != -1: # Themes
                    PathSplit = os.path.split(FullPath)
                    ThemeMetaData = PathSplit[1].split("-")
                    EmbyId = ThemeMetaData[4]
                    ServerId = ThemeMetaData[3]
                    ThemeItem = utils.readFileString(os.path.join(utils.DownloadPath, "EMBY-themes", ThemeMetaData[3], f"{unquote(ThemeMetaData[5]).replace('<_>', '-')}", f"metadata-{EmbyId}.json"))

                    if ThemeItem:
                        ThemeItem = json.loads(ThemeItem)
                        ListItem = listitem.set_ListItem(ThemeItem, ThemeMetaData[3], FullPath)

                        if XbmcPlayer.isPlaying():
                            XbmcPlayer.updateInfoTag(ListItem)
                        else:
                            xbmc.log("EMBY.helper.player: XbmcPlayer not playing 2", 3) # LOGERROR
                            continue

                        globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(EmbyId), 'MediaSourceId': None, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'IsMuted': Muted, 'RepeatMode': RepeatMode[playerops.PlayerId]}, None, None, None, utils.EmbyServers[ServerId], playerops.PlayerId, "", ""]
                else: # dynamic node items
                    if not load_unsynced_content(FullPath, PlaylistPosition, ""):
                        continue
            else:
                KodiId = EventData['item']['id']
                KodiType = EventData['item']['type']
                EmbyId, ServerId = utils.get_EmbyId_ServerId_by_Fake_KodiId(KodiId)

                if EmbyId:
                    KodiId = None

                    if not load_unsynced_content(FullPath, PlaylistPosition, KodiType):
                        continue

            if PlayingItem[0]:
                utils.update_querycache_userdata(((str(PlayingItem[0]['ItemId']), PlayingItem[0]['PositionTicks'], utils.currenttime(), -1, False),))

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
            if not QueuedPlayingItem and not FullPath.startswith("dav://127.0.0.1:57342") and not FullPath.startswith("http://127.0.0.1:57342") and not FullPath.startswith("/emby_addon_mode/") and FullPath.find("/EMBY-themes/") == -1:
                EmbyType = ""

                # load native mode played content from database
                if not QueuedPlayingItem:
                    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                        embydb = dbio.DBOpenRO(ServerId, "onAVStarted")
                        EmbyId, EmbyType, IntroStartPosTicks, IntroEndPosTicks, CreditsStartPosTicks = embydb.get_nativemode_data(KodiId, KodiType)

                        if not EmbyId:
                            dbio.DBCloseRO(ServerId, "onAVStarted")
                            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no item", 1) # LOGINFO
                            continue

                        globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediasourceId': embydb.get_mediasourceid_by_path(FullPath), 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStartPosTicks, IntroEndPosTicks, CreditsStartPosTicks, EmbyServer, playerops.PlayerId, KodiType, FullPath]
                        break

                # Select options for native played content
                if QueuedPlayingItem:
                    # Cinnemamode
                    if ((utils.enableCinemaMovies and EmbyType == "Movie") or (utils.enableCinemaEpisodes and EmbyType == "Episode")) and not utils.RemoteMode:
                        if TrailerStatus == "READY":
                            playerops.Pause()
                            globals()["QueuedPlayingItem"][4].http.Intros = []
                            PlayTrailer = True

                            if utils.askCinema:
                                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

                            if PlayTrailer:
                                globals()["QueuedPlayingItem"][4].http.load_Trailers(EmbyId)

                            if QueuedPlayingItem[4].http.Intros:
                                globals()["playlistIndex"] = PlaylistPosition
                                play_Trailer(QueuedPlayingItem[4])
                                dbio.DBCloseRO(ServerId, "onAVStarted")
                                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] native cinnemamode", 1) # LOGINFO
                                init_EmbyPlayback(KodiType, RunTimeTicks, PositionTicks, PlaylistPosition)
                                continue

                            playerops.Unpause()
                        elif TrailerStatus == "CONTENT":
                            globals()["TrailerStatus"] = "READY"

                    # Multiversion selection
                    MediaSources = embydb.get_mediasource(EmbyId)
                    VideoStreams = embydb.get_videostreams(EmbyId)
                    dbio.DBCloseRO(ServerId, "onAVStarted")

                    if len(MediaSources) > 1 and not utils.RemoteMode and not utils.SelectDefaultVideoversion:
                        if KodiType == "movie":
                            globals()["QueuedPlayingItem"][7] = "" # disable delete after watched option for multicontent
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
                                globals()["MultiselectionDone"] = True
                                Path = MediaSources[MediaIndex][2]

                                if Path.startswith('\\\\'):
                                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                                ListItem = load_KodiItem("onAVStarted", KodiId, KodiType, Path)

                                if not ListItem:
                                    xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] no listitem", 1) # LOGINFO
                                    continue

                                globals()["playlistIndex"] = PlaylistPosition
                                utils.Playlists[1].add(Path, ListItem, playlistIndex + 1)
                                globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSources[MediaIndex][1], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, MediaSources[MediaIndex][5], MediaSources[MediaIndex][6], MediaSources[MediaIndex][7], QueuedPlayingItem[4], playerops.PlayerId, KodiType, ""]
                                playerops.Next()
                                playerops.RemovePlaylistItem(1, playlistIndex)

                    if QueuedPlayingItem[4].http.Intros:
                        continue

            if not QueuedPlayingItem:
                xbmc.log("EMBY.hooks.player: Playing unknown content 2", 1) # LOGINFO
                continue

            # Load playback data
            load_queuePlayingItem()
            globals().update({"EmbyPlaying": True, "PlayingItem": QueuedPlayingItem, "QueuedPlayingItem": []})
            init_EmbyPlayback(KodiType, RunTimeTicks, PositionTicks, PlaylistPosition)
            xbmc.log("EMBY.hooks.player: --< [ onAVStarted ]", 1) # LOGINFO
        elif Commands[0] == "play": # {"item":{"id":216,"type":"episode"},"player":{"playerid":1,"speed":1}}
            xbmc.log("EMBY.hooks.player: [ onPlay ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onPlay ] {EventData}", 0) # LOGDEBUG
            set_PlayerId(EventData)

            if not utils.PauseSyncDuringPlayback or playerops.WatchTogether:
                utils.SyncPause['playing'] = True

            if EmbyPlaying:
                xbmc.log("EMBY.hooks.player: [ Playback was not stopped ]", 1) # LOGINFO
                stop_playback(True, False)
        elif Commands[0] == "pause":
            xbmc.log("EMBY.hooks.player: [ onPlayBackPaused ]", 1) # LOGINFO
            playerops.PlayerPause = True

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "pause")
                continue

            PositionTicks = playerops.PlayBackPosition()

            if PositionTicks == -1:
                playerops.RemoteCommand(None, None, "pause")
                continue

            globals()["PlayingItem"][0].update({'PositionTicks': PositionTicks, 'IsPaused': True})

            if PlayingItem[4]:
                if PlayingItem[4].EmbySession:
                    playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "pause")

                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "Pause", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])

            xbmc.log("EMBY.hooks.player: -->[ paused ]", 0) # LOGDEBUG
        elif Commands[0] == "resume":
            xbmc.log("EMBY.hooks.player: [ onPlayBackResumed ]", 1) # LOGINFO
            playerops.PlayerPause = False

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "unpause")
                continue

            if PlayingItem[4]:
                if PlayingItem[4] and PlayingItem[4].EmbySession:
                    playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "unpause")

                globals()["PlayingItem"][0]['IsPaused'] = False
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "Unpause", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
                globals()["TrackerPaused"] = True

            xbmc.log("EMBY.hooks.player: --<[ paused ]", 0) # LOGDEBUG
        elif Commands[0] == "stop": # {'end': True, 'item': {'id': 33874, 'type': 'episode'}}
            xbmc.log("EMBY.hooks.player: [ onPlayBackStopped ]", 1) # LOGINFO
            EventData = json.loads(Commands[1])
            xbmc.log(f"EMBY.hooks.player: [ onPlayBackStopped ] {EventData}", 0) # LOGDEBUG
            utils.SyncPause['playing'] = False
            playerops.AVStarted = False
            playerops.EmbyIdPlaying = 0
            playerops.PlayerPause = False

            if not PlayingItem[0]:
                playerops.RemoteCommand(None, None, "stop")
                continue

            if PlayingItem[4] and PlayingItem[4].EmbySession:
                playerops.RemoteCommand(PlayingItem[4].ServerData['ServerId'], PlayingItem[4].EmbySession[0]['Id'], "stop")

            if EventData['end'] == "quit":
                stop_playback(False, False)
            elif EventData['end'] or PlaybackEndedForced: # finished play and play next playlist item: {"end":true,"item":{"id":215,"type":"episode"}}
                globals()['PlaybackEndedForced'] = False
                stop_playback(True, True)
            else: # stopped in playlist: '{"end":false,"item":{"id":215,"type":"episode"}}'; play next item but playlist is at the end: '{"end":false,"item":{"type":"unknown"}}
                stop_playback(True, False)

            xbmc.log("EMBY.hooks.player: --<[ playback ]", 1) # LOGINFO
        elif Commands[0] == "volume":
            EventData = json.loads(Commands[1])
            globals().update({"Muted": EventData["muted"], "Volume": EventData["volume"]})

            if not PlayingItem[0]:
                continue

            globals()["PlayingItem"][0].update({'VolumeLevel': Volume, 'IsMuted': Muted})

            if PlayingItem[4]:
                globals()["TrackerPaused"] = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "VolumeChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "propertychanged":
            EventData = json.loads(Commands[1])

            if "repeat" in EventData['property']:
                Repeat = parse_repeat(EventData['property']['repeat'])
                PlayerId = EventData['player']['playerid']
                globals()['RepeatMode'][PlayerId] = Repeat

                if PlayerId == playerops.PlayerId:
                    globals()["PlayingItem"][0].update({'RepeatMode': RepeatMode[playerops.PlayerId]})

                    if PlayingItem[4]:
                        globals()["TrackerPaused"] = True
                        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "RepeatModeChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
            elif "shuffled" in EventData['property']:
                Shuffle = EventData['property']['shuffled']
                PlayerId = EventData['player']['playerid']
                globals()['Shuffled'][PlayerId] = Shuffle

                if PlayerId == playerops.PlayerId:
                    globals()["PlayingItem"][0].update({'Shuffle': Shuffled[playerops.PlayerId]})

                    if PlayingItem[4]:
                        globals()["TrackerPaused"] = True
                        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "ShuffleChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "speedchanged": # {"item":{"id":215,"type":"episode"},"player":{"playerid":1,"speed":2}}
            EventData = json.loads(Commands[1])
            Speed = EventData['player']['speed']
            PlayerId = EventData['player']['playerid']
            globals()['PlaybackRate'][PlayerId] = float(Speed)

            if PlayerId == playerops.PlayerId:
                globals()["PlayingItem"][0].update({'PlaybackRate': PlaybackRate[playerops.PlayerId]})

                if PlayingItem[4]:
                    globals()["TrackerPaused"] = True
                    PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaybackRateChange", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "clear": # '{"playlistid":1}'
            EventData = json.loads(Commands[1])
            globals()['PlaylistKodi'][EventData['playlistid']] = []

            if PlayingItem[4]:
                globals()["TrackerPaused"] = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaylistItemRemove", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "remove": # '{"playlistid":1,"position":0}'
            EventData = json.loads(Commands[1])
            del globals()['PlaylistKodi'][EventData['playlistid']][EventData['position']]

            if PlayingItem[4]:
                globals()["TrackerPaused"] = True
                PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "PlaylistItemRemove", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        elif Commands[0] == "add": # unsyncd video = '{"item":{"id":1000018721,"type":"episode"},"playlistid":1,"position":0}'; synced video = '{"item":{"id":4268,"type":"episode"},"playlistid":1,"position":2}'; unsynced music = {"item":{"id":1000073262,"type":"song"},"playlistid":0,"position":0}; unsynced music external played e.g. via favorites'{"item":{"album":"Bella stella","artist":["Highland"],"title":"Bella stella","track":1,"type":"song"},"playlistid":0,"position":0}'; synced music = '{"item":{"id":233155,"type":"song"},"playlistid":0,"position":0}')
            EventData = json.loads(Commands[1])

            if 'id' in EventData['item']:
                PlaylistKodi[EventData['playlistid']].insert(EventData['position'], {"KodiId": EventData['item']['id'], "KodiType": EventData['item']['type']})

    xbmc.log("EMBY.hooks.player: THREAD: ---<[ player commands ]", 0) # LOGDEBUG

def set_PlayerId(EventData):
    if 'player' in EventData and 'playerid' in EventData['player'] and EventData['player']['playerid'] != -1:
        playerops.PlayerId = EventData['player']['playerid']

def parse_repeat(Data):
    if Data == "all":
        return "RepeatAll"

    if Data == "one":
        return "RepeatOne"

    return "RepeatNone"

def stop_playback(delete, PlaybackEnded):
    xbmc.log(f"EMBY.hooks.player: [ played info ] {PlayingItem}", 0) # LOGDEBUG
    PlayingItemLocal = PlayingItem.copy()
    globals()["TrackerPaused"] = False
    PlaybackRate[playerops.PlayerId] = 1.0

    if MultiselectionDone:
        xbmc.log("EMBY.hooks.player: stop_playback MultiselectionDone", 0) # LOGDEBUG
        return

    if not PlayingItemLocal[4]:
        xbmc.log("EMBY.hooks.player: stop_playback no PlayingItemLocal", 2) # LOGWARNING
        return

    globals().update({"EmbyPlaying": False, "PlayingItem": [{}, 0, 0, 0, None, 0, "", ""]})

    if PlaybackEnded and PlayingItemLocal[0]['RunTimeTicks']:
        PlayingItemLocal[0]['PositionTicks'] = PlayingItemLocal[0]['RunTimeTicks']

    utils.update_querycache_userdata(((str(PlayingItemLocal[0]['ItemId']), PlayingItemLocal[0]['PositionTicks'], utils.currenttime(), -1, PlaybackEnded),))
    PlaylistEmby[PlayingItem[5]] = PlayingItemLocal[4].API.session_stop(PlayingItemLocal[0], PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
    close_SkipIntroDialog()
    close_SkipCreditsDialog()

    if PlaybackEnded and TrailerStatus == "PLAYING":
        if not PlayingItemLocal[4].http.Intros:
            PlayingItemLocal[4].http.Intros = []
            globals()["TrailerStatus"] = "CONTENT"
            globals()['SkipItem'] = ()
            playerops.PlayPlaylistItem(1, playlistIndex)
            return

        # play trailers for native content
        if PlayingItemLocal[4].http.Intros:
            play_Trailer(PlayingItemLocal[4])
            return

    globals()["TrailerStatus"] = "READY"
    PlayingItemLocal[4].http.Intros = []
    globals()['SkipItem'] = ()

    if not PlayingItemLocal[0]:
        return

    utils.HTTPResponseCaches.pop(str(PlayingItemLocal[0]['ItemId']), None) # delete dict key if exists

    # Set watched status
    Runtime = int(PlayingItemLocal[0]['RunTimeTicks'])
    PlayPosition = int(PlayingItemLocal[0]['PositionTicks'])

    if delete and PlayingItemLocal[7]:
        if utils.offerDelete:
            if Runtime > 10:
                if PlayPosition > Runtime * 0.90:  # 90% Progress
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

    thread_sync_workers()

def play_Trailer(EmbyServer):
    MediasourceID = EmbyServer.http.Intros[0]['MediaSources'][0]['Id']
    globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(EmbyServer.http.Intros[0]['Id']), 'MediaSourceId': MediasourceID, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, None, None, None, EmbyServer, playerops.PlayerId, "", ""]
    Path = EmbyServer.http.Intros[0]['KodiFullPath']
    li = listitem.set_ListItem(EmbyServer.http.Intros[0], EmbyServer.ServerData['ServerId'])
    del EmbyServer.http.Intros[0]
    globals()["TrailerStatus"] = "PLAYING"
    li.setPath(Path)
    XbmcPlayer.play(Path, li)

def PositionTracker():
    TasksRunning.append("PositionTracker")
    LoopCounter = 1
    xbmc.log("EMBY.hooks.player: THREAD: --->[ position tracker ]", 0) # LOGDEBUG

    while PlayingItem[0] and not utils.SystemShutdown:
        if not utils.sleep(1):
            if not EmbyPlaying or not PlayingItem[0]:
                break

            Position = int(playerops.PlayBackPosition())

            if Position == 0:
                continue

            if Position == -1:
                break

            Runtime = int(PlayingItem[0].get('RunTimeTicks', 0))

            if Runtime and (Position + 20000000) > Runtime: # 2 seconds before playback ends pause updates
                PlayerBusy()

            xbmc.log(f"EMBY.hooks.player: PositionTracker: Position: {Position} / IntroStartPositionTicks: {PlayingItem[1]} / IntroEndPositionTicks: {PlayingItem[2]} / CreditsPositionTicks: {PlayingItem[3]} / SkipIntroJumpDone: {SkipIntroJumpDone}", 0) # LOGDEBUG

            if utils.enableSkipIntro:
                if PlayingItem[1] < Position < PlayingItem[2]:
                    if not SkipIntroJumpDone:
                        globals()["SkipIntroJumpDone"] = True

                        if utils.askSkipIntro:
                            if utils.skipintroembuarydesign:
                                xbmc.log("EMBY.hooks.player: --->[ SkipIntroDialogEmbuary ]", 0) # LOGDEBUG
                                SkipIntroDialogEmbuary.show()
                            else:
                                xbmc.log("EMBY.hooks.player: --->[ SkipIntroDialog ]", 0) # LOGDEBUG
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

            if LoopCounter % 50 == 0 and PlayingItem[4]: # modulo 10
                if not TrackerPaused:
                    globals()["PlayingItem"][0]['PositionTicks'] = Position
                    xbmc.log(f"EMBY.hooks.player: PositionTracker: Report progress {PlayingItem[0]['PositionTicks']}", 0) # LOGDEBUG
                    PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
                else:
                    globals()["TrackerPaused"] = False

                LoopCounter = 0

            LoopCounter += 1

    TasksRunning.remove("PositionTracker")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ position tracker ]", 0) # LOGDEBUG

def jump_Intro():
    xbmc.log(f"EMBY.hooks.player: Skip intro jump {PlayingItem[2]}", 1) # LOGINFO

    if PlayingItem[4]:
        playerops.Seek(PlayingItem[2])
        globals()["PlayingItem"][0]['PositionTicks'] = PlayingItem[2]
        globals()["SkipIntroJumpDone"] = True
        globals()["TrackerPaused"] = True
        PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_progress(PlayingItem[0], "TimeUpdate", PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
    else:
        xbmc.log(f"EMBY.hooks.player: Skip intro jump error: {PlayingItem}", 3) # LOGERROR

def jump_Credits():
    if PlayingItem[0].get('RunTimeTicks', 0):
        xbmc.log(f"EMBY.hooks.player: Skip credits jump {PlayingItem[0]['RunTimeTicks']}", 1) # LOGINFO
        playerops.Seek(PlayingItem[0]['RunTimeTicks'])
        globals()["PlayingItem"][0]['PositionTicks'] = PlayingItem[0]['RunTimeTicks']
        globals()["SkipCreditsJumpDone"] = True
    else:
        xbmc.log("EMBY.hooks.player: Skip credits, invalid RunTimeTicks", 1) # LOGINFO

def close_SkipIntroDialog():
    if utils.skipintroembuarydesign:
        if SkipIntroDialogEmbuary.dialog_open:
            xbmc.log("EMBY.hooks.player: ---<[ SkipIntroDialogEmbuary ]", 0) # LOGDEBUG
            SkipIntroDialogEmbuary.close()
    else:
        if SkipIntroDialog.dialog_open:
            xbmc.log("EMBY.hooks.player: ---<[ SkipIntroDialog ]", 0) # LOGDEBUG
            SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

def load_queuePlayingItem():
    xbmc.log("EMBY.hooks.player: [ Queue playing item ]", 1) # LOGINFO
    PlayerBusy()

    if not utils.RemoteMode:
        utils.ItemSkipUpdate.append(str(QueuedPlayingItem[0]['ItemId'])) # triple add -> for Emby (2 times incoming msg -> userdata changed) and once for Kodi database incoming msg -> VideoLibrary_OnUpdate; "KODI" prefix makes sure, VideoLibrary_OnUpdate is skipped even if more userdata requests from Emby server were received

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

    if QueuedPlayingItem[4] and QueuedPlayingItem[4].EmbySession:
        playerops.RemoteCommand(QueuedPlayingItem[4].ServerData['ServerId'], QueuedPlayingItem[4].EmbySession[0]['Id'], "play", QueuedPlayingItem[0]['ItemId'])

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

def replace_playlist_listitem(ListItem, Path):
    globals()["PlaylistRemoveItem"] = playerops.GetPlayerPosition(1) # old listitem will be removed after play next
    utils.Playlists[1].add(Path, ListItem, PlaylistRemoveItem + 1)
    load_queuePlayingItem()

# Sync jobs
def thread_sync_workers():
    if "sync_workers" not in TasksRunning and not utils.RemoteMode:  # skip sync on remote client mode
        utils.start_thread(sync_workers, ())

def sync_workers():
    xbmc.log("EMBY.hooks.player: THREAD: --->[ sync worker ]", 0) # LOGDEBUG
    TasksRunning.append("sync_workers")

    if not utils.sleep(2):
        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.library.RunJobs(True)

    TasksRunning.remove("sync_workers")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ sync worker ]", 0) # LOGDEBUG

# Interrupt syncs while player is busy -> 5 seconds delay
def PlayerBusy():
    globals()["PlayerBusyDelay"] = 5

    if "PlayerBusy" not in TasksRunning:
        TasksRunning.append("PlayerBusy")
        utils.start_thread(PlayerBusyThread, ())

def PlayerBusyThread():
    xbmc.log("EMBY.hooks.player: THREAD: --->[ PlayerBusyThread ]", 0) # LOGDEBUG
    utils.SyncPause['playerbusy'] = True
    utils.PlayerBusy.acquire()

    while PlayerBusyDelay >= 0:
        utils.sleep(1)
        globals()["PlayerBusyDelay"] -= 1

    utils.SyncPause['playerbusy'] = False
    utils.release_lock(utils.PlayerBusy)
    TasksRunning.remove("PlayerBusy")
    xbmc.log("EMBY.hooks.player: THREAD: ---<[ PlayerBusyThread ]", 0) # LOGDEBUG

def load_unsynced_content(FullPath, PlaylistPosition, KodiType):
    IntroStartPosTicks = []
    IntroEndPosTicks = []
    CreditsStartPosTicks = []
    MediaSourceIds = []
    MediaSourceSize = []
    MediaSourceName = []
    MediaSourcePath = []
    MediaSourcesCount = 0
    EmbyId = ""
    MediaSourceIndex = 0
    ServerId = ""

    # Try to load item from cache
    CachedItemFound = False
    CachedItem = []

    for CachedItems in list(utils.QueryCache.values()):
        if CachedItemFound:
            break

        for CachedContentItems in list(CachedItems.values()):
            if CachedItemFound:
                break

            for CachedItem in CachedContentItems[1]:
                if CachedItem[0] == FullPath:
                    xbmc.log("EMBY.hooks.player: Update player info", 1) # LOGINFO

                    if XbmcPlayer.isPlaying():
                        XbmcPlayer.updateInfoTag(CachedItem[1])

                        if QueuedPlayingItem: # Dynamic widget -> item played via addon mode or multicontent native content item
                            CachedItemFound = True
                            break
                    else:
                        xbmc.log("EMBY.helper.player: XbmcPlayer not playing 1", 3) # LOGERROR
                        continue

                    KodiType = CachedItem[1].getProperty("KodiType")
                    ServerId = CachedItem[1].getProperty("embyserverid")
                    EmbyId = CachedItem[1].getProperty("embyid")
                    MediaSourcesCount = int(CachedItem[1].getProperty("mediasourcescount"))

                    for MediaSourceIndex in range(MediaSourcesCount):
                        IntroStartPosTicks.append(int(CachedItem[1].getProperty(f"embyintrostartposticks{MediaSourceIndex}")))
                        IntroEndPosTicks.append(int(CachedItem[1].getProperty(f"embyintroendpositionticks{MediaSourceIndex}")))
                        CreditsStartPosTicks.append(int(CachedItem[1].getProperty(f"embycreditspositionticks{MediaSourceIndex}")))
                        MediaSourceIds.append(CachedItem[1].getProperty(f"embymediacourceid{MediaSourceIndex}"))
                        MediaSourceSize.append(int(CachedItem[1].getProperty(f"embymediacourcesize{MediaSourceIndex}")))
                        MediaSourceName.append(CachedItem[1].getProperty(f"embymediacourcename{MediaSourceIndex}"))
                        MediaSourcePath.append(CachedItem[1].getProperty(f"embymediacourcepath{MediaSourceIndex}"))

                    CachedItemFound = True
                    break

    # Dynamic widget item played via native mode
    if CachedItemFound and not QueuedPlayingItem:
        if MediaSourcesCount > 1 and not utils.RemoteMode:
            playerops.Pause()
            Selection = []

            for MediaSourceIndex in range(MediaSourcesCount):
                Selection.append(f"{MediaSourceName[MediaSourceIndex]} - {utils.SizeToText(float(MediaSourceSize[MediaSourceIndex]))} - {MediaSourcePath[MediaSourceIndex]}")

            MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

            if MediaIndex == -1:
                Cancel()
                xbmc.log("EMBY.hooks.player: --< [ onAVStarted ] cancel", 1) # LOGINFO
                return False

            if MediaIndex == 0:
                playerops.Unpause()
            else:
                globals()["MultiselectionDone"] = True
                Path = MediaSourcePath[MediaIndex]

                if Path.startswith('\\\\'):
                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                ListItem = CachedItem[1]
                ListItem.setPath(Path)
                globals()["playlistIndex"] = PlaylistPosition
                utils.Playlists[1].add(Path, ListItem, playlistIndex + 1)
                globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSourceIds[MediaIndex], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStartPosTicks[MediaSourceIndex], IntroEndPosTicks[MediaSourceIndex], CreditsStartPosTicks[MediaSourceIndex], utils.EmbyServers[ServerId], playerops.PlayerId, KodiType, FullPath]
                playerops.Next()
                playerops.RemovePlaylistItem(1, playlistIndex)
                return False
        else:
            globals()["QueuedPlayingItem"] = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': not bool(KodiType == "channel"), 'IsPaused': False, 'ItemId': EmbyId, 'MediaSourceId': MediaSourceIds[0], 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'PlaybackRate': PlaybackRate[playerops.PlayerId], 'Shuffle': Shuffled[playerops.PlayerId], 'RepeatMode': RepeatMode[playerops.PlayerId], 'IsMuted': Muted}, IntroStartPosTicks[0], IntroEndPosTicks[0], CreditsStartPosTicks[0], utils.EmbyServers[ServerId], playerops.PlayerId, KodiType, FullPath]

    return True

def init_EmbyPlayback(KodiType, RunTimeTicks, PositionTicks, PlaylistPosition):
    if PlayingItem[0]:
        if not utils.RemoteMode:
            if KodiType == "song":
                utils.ItemSkipUpdate += [str(PlayingItem[0]['ItemId'])] # double add -> for Emby (2 times incoming msg -> userdata changed)
            else:
                utils.ItemSkipUpdate += [f"KODI{PlayingItem[0]['ItemId']}", str(PlayingItem[0]['ItemId'])] # triple add -> for Emby (2 times incoming msg -> userdata changed) and once for Kodi database incoming msg -> VideoLibrary_OnUpdate; "KODI" prefix makes sure, VideoLibrary_OnUpdate is skipped even if more userdata requests from Emby server were received

        xbmc.log(f"EMBY.hooks.player: PlayingItem: {PlayingItem}", 0) # LOGDEBUG
        globals()["PlayingItem"][0].update({'RunTimeTicks': RunTimeTicks, 'PositionTicks': PositionTicks, "PlaylistIndex": PlaylistPosition})

        if PlayingItem[4]:
            PlaylistEmby[PlayingItem[5]] = PlayingItem[4].API.session_playing(PlayingItem[0], PlaylistKodi[PlayingItem[5]], PlaylistEmby[PlayingItem[5]])
        else:
            xbmc.log(f"EMBY.hooks.player: avstart error: {PlayingItem}", 3) # LOGERROR

        xbmc.log(f"EMBY.hooks.player: ItemSkipUpdate: {utils.ItemSkipUpdate}", 0) # LOGDEBUG
        playerops.AVStarted = True

        if "PositionTracker" not in TasksRunning:
            utils.start_thread(PositionTracker, ())

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

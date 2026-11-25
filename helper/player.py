import threading
import random
import uuid
from urllib.parse import unquote_plus
import json
import xbmc
from database import dbio
from emby import listitem, metadata
from core import common
from dialogs import skipintrocredits
from . import utils, playerops, queue, cache, copy
TrackerPaused = False
VideoPlayback = "READY"
VideoPlaybackOld = "READY"
PlaylistRemoveItem = -1
Volume = 100
Muted = False
CloseDialog = False
PlayItem = (0, "")
PlayerVolume = utils.SendJson("Application.GetProperties", '{"properties": ["volume", "muted"]}', False).get('result', {})

if PlayerVolume:
    Volume = PlayerVolume.get('volume', 100)
    Muted = PlayerVolume.get('muted', False)

PlaylistKodi = [[], [], []]
PlaylistEmby = [[], [], []]
PlayingItem = {"EmbySessionData": {}, "IntroStartPositionTicks": 0, "IntroEndPositionTicks": 0, "CreditsPositionTicks": 0, "EmbyServer": None, "KodiType": "", "Filename": "", "IndexMappingVideoEmby": {}, "IndexMappingVideoKodi": {}, "IndexMappingAudioEmby": {}, "IndexMappingAudioKodi": {}, "IndexMappingSubtitleEmby": {}, "IndexMappingSubtitleKodi": {}, "SubtitleEnabled": False, "SubtitleIndexKodi": 0}
PlayingItemInit = {"EmbySessionData": {}, "IntroStartPositionTicks": 0, "IntroEndPositionTicks": 0, "CreditsPositionTicks": 0, "EmbyServer": None, "KodiType": "", "Filename": "", "IndexMappingVideoEmby": {}, "IndexMappingVideoKodi": {}, "IndexMappingAudioEmby": {}, "IndexMappingAudioKodi": {}, "IndexMappingSubtitleEmby": {}, "IndexMappingSubtitleKodi": {}, "SubtitleEnabled": False, "SubtitleIndexKodi": 0}
QueuedPlayingItem = {}
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
DeleteContentQueue = queue.Queue()
SkipIntroDialog = skipintrocredits.SkipIntro("script-emby-skipintrodialog.xml", *utils.CustomDialogParameters)
SkipIntroDialogEmbuary = skipintrocredits.SkipIntro("script-emby-skipintrodialogembuary.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("script-emby-skipcreditsdialog.xml", *utils.CustomDialogParameters)
ForceStopKodiId = 0
ForceStopCondition = threading.Condition(threading.Lock())
ProgressBarEnable = -1
PicturePlaybackInit = False
PlayerLock = threading.Lock()
Theme = {"PlayerId": -1, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": "", "Runtime": 0}

# Player events (queued by monitor notifications)
def PlayerCommands():
    if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: --->[ player commands ]", 1) # LOGDEBUG
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
    global PicturePlaybackInit

    while True:
        Commands = PlayerEventsQueue.get()

        with utils.SafeLock(PlayerLock):
            if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): playercommand received: {Commands}", 1) # LOGDEBUG

            if Commands == "QUIT":
                if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: ---<[ player commands ] quit", 1) # LOGDEBUG
                return

            PlayerBusyDelay = 5

            if Commands[0] == "seek": # {'item': {'id': 33874, 'type': 'episode'}, 'player': {'playerid': 1, 'seekoffset': {'hours': 0, 'milliseconds': 177, 'minutes': 41, 'seconds': 56}, 'speed': 1, 'time': {'hours': 0, 'milliseconds': 550, 'minutes': 47, 'seconds': 3}}}
                # Seekposition might not be exact. Don't use it as critical data e.g. do not use for remote playback seek, but good enough for the progress updates
                xbmc.log("EMBY.helper.player: [ onSeek ]", 1) # LOGINFO
                EventData = json.loads(Commands[1])
                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onSeek ] {EventData}", 1) # LOGDEBUG
                set_PlayerId(EventData)

                if not PlayingItem["EmbySessionData"]:
                    playerops.RemoteCommand(None, None, "seek")
                    continue

                if 'player' in EventData and 'time' in EventData['player']:
                    PlayingItem["EmbySessionData"]['PositionTicks'] = (EventData['player']['time']['hours'] * 3600000 + EventData['player']['time']['minutes'] * 60000 + EventData['player']['time']['seconds'] * 1000 + EventData['player']['time']['milliseconds']) * 10000
                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "TimeUpdate", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])

                playerops.AVChange = False

                with utils.SafeLock(playerops.AVChangeCondition):
                    playerops.AVChangeCondition.notify_all()

                if PlayingItem["EmbyServer"] and PlayingItem["EmbyServer"].EmbySession:
                    playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "seek")
            elif Commands[0] == "avchange": # {"item":{"id":12115,"type":"episode"},"player":{"playerid":1,"speed":1}}
                xbmc.log("EMBY.helper.player: [ onAVChange ]", 1) # LOGINFO
                EventData = json.loads(Commands[1])
                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onAVChange ] {EventData}", 1) # LOGDEBUG

                if "item" in EventData:
                    if 'id' in EventData['item']:
                        if ForceStopKodiId == EventData["item"]["id"]:
                            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): [ avchange/forced stop ]", 1) # LOGDEBUG
                            playerops.Stop(False)
                            continue

                set_PlayerId(EventData)

                # Update playback rate
                Speed = float(playerops.GetTempo())

                if Speed != playerops.PlaybackRate[playerops.PlayerId]:
                    playerops.PlaybackRate[playerops.PlayerId] = float(Speed)
                    PlayingItem["EmbySessionData"].update({'PlaybackRate': playerops.PlaybackRate[playerops.PlayerId]})

                    if PlayingItem["EmbyServer"]:
                        TrackerPaused = True
                        PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "PlaybackRateChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])

                playerops.AVChange = True

                with utils.SafeLock(playerops.AVChangeCondition):
                    playerops.AVChangeCondition.notify_all()
            elif Commands[0] == "avstart": # ('avstart', '{"item":{"id":33874,"type":"episode"},"player":{"playerid":1,"speed":1}}')
                xbmc.log("EMBY.helper.player: --> [ onAVStarted ]", 1) # LOGINFO
                playerops.AVStart = True
                EventData = json.loads(Commands[1])
                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onAVStarted ] {EventData}", 1) # LOGDEBUG
                KodiId = 0
                KodiType = ""

                # Dummy (blankwav) played
                if "item" in EventData:
                    if 'id' in EventData['item']:
                        KodiId = EventData['item']['id']
                        KodiType = EventData['item']['type']

                        if ForceStopKodiId == EventData["item"]["id"]:
                            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): [ avstart/forced stop ]", 1) # LOGDEBUG
                            playerops.Stop(False, True)
                            continue

                set_PlayerId(EventData)
                FullPath = ""

                if KodiType != "channel":
                    FullPath = playerops.GetPlayerFilepath()
                    if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): FullPath: {FullPath}", 1) # LOGDEBUG

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
                    xbmc.log("EMBY.helper.player: --< [ onAVStarted ] multisiection done", 1) # LOGINFO
                    continue

                EmbyId = 0
                EmbyId, isAddonContent, isDynamic, EmbyType, MediaSources, CachedItem = find_EmbyContent(FullPath, KodiId, KodiType)

                if PlayingItem["EmbySessionData"] and 'ItemId' in PlayingItem["EmbySessionData"]:
                    cache.update_userdata_Kodi(str(PlayingItem["EmbySessionData"]['ItemId']), PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbySessionData"]['PositionTicks'] / 10000000.0, utils.currenttime(), None, PlayingItem["EmbySessionData"]['RunTimeTicks'] / 10000000.0, None)

                # native content
                if not isAddonContent:
                    # Cinnemamode
                    if not Trailers:
                        if ((utils.enableCinemaMovies and EmbyType == "Movie") or (utils.enableCinemaEpisodes and EmbyType == "Episode")) and not utils.RemoteMode:
                            if VideoPlayback == "READY":
                                playerops.Pause()
                                Trailers = []
                                PlayTrailer = True

                                if utils.askCinema:
                                    PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

                                if PlayTrailer:
                                    if load_Trailer(QueuedPlayingItem["EmbyServer"].ServerData['ServerId']):
                                        PlaylistIndexContent = PlaylistPosition
                                        playerops.Stop(False, True)
                                        play_Trailer(QueuedPlayingItem["EmbyServer"])
                                        xbmc.log("EMBY.helper.player: --< [ onAVStarted ] native cinnemamode", 1) # LOGINFO
                                        init_EmbyPlayback()
                                        continue

                                playerops.Unpause()
                            elif VideoPlayback == "CONTENT":
                                VideoPlayback = "READY"

                        # Multiversion selection
                        if len(MediaSources) > 1 and not utils.RemoteMode:
                            if KodiType == "movie":
                                QueuedPlayingItem["Filename"] = "" # disable delete after watched option for multicontent

                            if isDynamic or KodiType != "movie":
                                playerops.Pause()

                                # Autoselect mediasource by highest resolution
                                if utils.AutoSelectHighestResolution:
                                    HighestResolution = 0
                                    MediaIndex = 0

                                    for MediaSourceIndex, MediaSourceData in enumerate(MediaSources):
                                        for Stream in MediaSourceData['MediaStreams']:
                                            if Stream["Type"] == "Video":
                                                VideoStreamsWidth = int(Stream.get('Width', 0) or 0) # Resolution Width

                                                if HighestResolution < VideoStreamsWidth:
                                                    HighestResolution = VideoStreamsWidth
                                                    MediaIndex = MediaSourceIndex
                                else: # Manual select mediasource
                                    Selection = []
                                    MediasourcesSelection = []

                                    for MediaSourceData in MediaSources:
                                        Selection.append(f"{MediaSourceData['Name']} - {utils.SizeToText(float(MediaSourceData['Size']))} - {MediaSourceData['Path']}")
                                        MediasourcesSelection.append(MediaSourceData)

                                    MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

                                    if MediaIndex == -1:
                                        Cancel()
                                        xbmc.log("EMBY.helper.player: --< [ onAVStarted ] cancel", 1) # LOGINFO
                                        continue

                                if MediaIndex == 0: # Multiversion not changes
                                    playerops.Unpause()
                                else: # Reload new multiversion
                                    MultiselectionDone = True
                                    Path = MediaSources[MediaIndex]['Path']
                                    ListItem = load_KodiItem("onAVStarted", KodiId, KodiType, CachedItem, MediaIndex)

                                    if not ListItem:
                                        xbmc.log("EMBY.helper.player: --< [ onAVStarted ] no listitem", 1) # LOGINFO
                                        continue

                                    # Insert Multicontent version into playlist as next item, play next and remove it afterwards
                                    PlaylistIndexContent = PlaylistPosition
                                    playerops.XbmcPlaylists[1].add(Path, ListItem, PlaylistIndexContent + 1)
                                    MediasourcesSelected = MediaSources[MediaIndex]
                                    QueuedPlayingItem = {
                                        "EmbySessionData": {
                                            "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                                            "CanSeek": not bool(KodiType == "channel"),
                                            "IsPaused": False,
                                            "ItemId": EmbyId,
                                            "MediaSourceId": MediasourcesSelected["Id"],
                                            "PlaySessionId": str(uuid.uuid4()).replace("-", ""),
                                            "PositionTicks": 0,
                                            "RunTimeTicks": 0,
                                            "VolumeLevel": Volume,
                                            "PlaybackRate": playerops.PlaybackRate[playerops.PlayerId],
                                            "Shuffle": playerops.Shuffled[playerops.PlayerId],
                                            "RepeatMode": playerops.RepeatMode[playerops.PlayerId],
                                            "IsMuted": Muted
                                        },
                                        "IntroStartPositionTicks": MediasourcesSelected["IntroStartPositionTicks"],
                                        "IntroEndPositionTicks": MediasourcesSelected["IntroEndPositionTicks"],
                                        "CreditsPositionTicks": MediasourcesSelected["CreditsPositionTicks"],
                                        "EmbyServer": QueuedPlayingItem["EmbyServer"],
                                        "KodiType": KodiType,
                                        "Filename": "",
                                        "IndexMappingVideoEmby": {},
                                        "IndexMappingVideoKodi": {},
                                        "IndexMappingAudioEmby": {},
                                        "IndexMappingAudioKodi": {},
                                        "IndexMappingSubtitleEmby": {},
                                        "IndexMappingSubtitleKodi": {},
                                        "SubtitleEnabled": False,
                                        "SubtitleIndexKodi": 0
                                    }
                                    playerops.Next()
                                    playerops.RemovePlaylistItem(1, PlaylistIndexContent)

                if not QueuedPlayingItem:
                    xbmc.log("EMBY.helper.player: Playing unknown content 2", 1) # LOGINFO
                    continue

                # Update Stream info
                if playerops.PlayerId == 0:
                    QueuedPlayingItem["EmbySessionData"]['AudioStreamIndex'] = 1
                else:
                    AudioIndexKodi, QueuedPlayingItem["SubtitleIndexKodi"], QueuedPlayingItem["SubtitleEnabled"], QueuedPlayingItem["IndexMappingSubtitleEmby"], QueuedPlayingItem["IndexMappingSubtitleKodi"] = playerops.GetStreamInfo(QueuedPlayingItem["IndexMappingSubtitleEmby"], QueuedPlayingItem["IndexMappingSubtitleKodi"])

                    if AudioIndexKodi in QueuedPlayingItem["IndexMappingAudioKodi"]:
                        QueuedPlayingItem["EmbySessionData"].update({'AudioStreamIndex': QueuedPlayingItem["IndexMappingAudioKodi"][AudioIndexKodi]})

                    if QueuedPlayingItem["SubtitleIndexKodi"] in QueuedPlayingItem["IndexMappingSubtitleKodi"] and QueuedPlayingItem["SubtitleEnabled"]:
                        QueuedPlayingItem["EmbySessionData"].update({'SubtitleStreamIndex': QueuedPlayingItem["IndexMappingSubtitleKodi"][QueuedPlayingItem["SubtitleIndexKodi"]]})

                # Load playback data
                load_queuePlayingItem()
                EmbyPlaying = True
                PlayingItem = copy.Object(QueuedPlayingItem)
                QueuedPlayingItem.clear()

                # Init Playback
                init_EmbyPlayback()

                if VideoPlayback == "CONTENT":
                    VideoPlayback = "READY"

                xbmc.log("EMBY.helper.player: --< [ onAVStarted ]", 1) # LOGINFO
            elif Commands[0] == "play": # {"item":{"id":216,"type":"episode"},"player":{"playerid":1,"speed":1}}, '{"item":{"id":1100045814,"type":"song"},"player":{"playerid":-1,"speed":1}
                xbmc.log("EMBY.helper.player: [ onPlay ]", 1) # LOGINFO
                PlayingItemInit = copy.Object(QueuedPlayingItem)
                playerops.Stopped = False

                with utils.SafeLock(playerops.StoppedCondition):
                    playerops.StoppedCondition.notify_all()

                if utils.PauseSyncDuringPlayback:
                    utils.update_SyncPause('playing', True)
                    utils.set_SyncLock()

                EventData = json.loads(Commands[1])
                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onPlay ] {EventData}", 1) # LOGDEBUG

                utils.closeall_ProgressBar()
                ProgressBarEnable = -1
                set_PlayerId(EventData)

                if CloseDialog:
                    utils.close_busyDialog(True)
                    CloseDialog = False

                VideoPlaybackOld = VideoPlayback

                if EmbyPlaying:
                    xbmc.log("EMBY.helper.player: [ Playback was never stopped ]", 1) # LOGINFO
                    stop_playback(True, False)

                if "item" in EventData:
                    if 'id' in EventData['item']:
                        ItemKodiSkipUpdate.append([EventData['item']['id'], EventData['item']['type']])
                        PlayItem = (EventData['item']['id'], EventData['item']['type'])
                    else:
                        PlayItem = (999999999, "unknown")

                # Reset virtual theme if it's the same content as playback starts
                if VideoPlayback == "THEME" and PlayItem[0] == Theme["KodiId"] and PlayItem[1] == Theme["KodiType"]:
                    VideoPlayback = "READY"

                # Check if picture
                if PlayItem == (999999999, "unknown"): # {"item":{"file":"image://emby@dav%3A%2F%2F127.0.0.1%3A57342%2Fpicture%2F2a38697ffc1b428b943aa1b6014e2263%2Fp-8356665-0-p-a7abae265b4d5b73693b144e3d429081_639224251790000000%7Credirect-limit%3D1000%26failonerror%3Dfalse/20260815_141257.jpg","type":"picture"},"player":{"playerid":2,"speed":1}}
                    if "file" in EventData['item'] and EventData['item']['file'].startswith("image://emby@dav%3A%2F%2F127.0.0.1%3A57342"):
                        xbmc.executebuiltin('PlayerControl(Stop, 0)') # Music can play in background on pictureplay, but Emby does not (fully) support multi content playback on a single session even PlaybacksessionId is unique. WebUI cannot show multiple NowplayingQueues.
                        PlayItem = (999999999, "picture")
                        URL = utils.image_url_decode(EventData['item']['file'], False)
                        URL = URL.replace("dav://127.0.0.1:57342", "")
                        MetaData = metadata.load_MetaData(URL, True, False)
                        PlayingItem = {
                            "EmbySessionData": {
                                "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                                "CanSeek": False,
                                "IsPaused": False,
                                "ItemId": MetaData["EmbyId"],
                                "PlaySessionId": str(uuid.uuid4()).replace("-", ""),
                                "PositionTicks": 0,
                                "RunTimeTicks": 0,
                                "VolumeLevel": Volume,
                                "PlaybackRate": 1,
                                "Shuffle": False,
                                "RepeatMode": False,
                                "IsMuted": Muted
                            },
                            "IntroStartPositionTicks": 0,
                            "IntroEndPositionTicks": 0,
                            "CreditsPositionTicks": 0,
                            "EmbyServer": utils.EmbyServers[MetaData["ServerId"]],
                            "KodiType": "picture",
                            "Filename": "",
                            "IndexMappingVideoEmby": {},
                            "IndexMappingVideoKodi": {},
                            "IndexMappingAudioEmby": {},
                            "IndexMappingAudioKodi": {},
                            "IndexMappingSubtitleEmby": {},
                            "IndexMappingSubtitleKodi": {},
                            "SubtitleEnabled": False,
                            "SubtitleIndexKodi": 0
                        }

                        if not utils.RemoteMode:
                            utils.ItemSkipUpdate.append(str(PlayingItem["EmbySessionData"]['ItemId'])) # Skip Emby progress updates as Kodi keeps track

                        PlaylistPositionOld = playerops.PlaylistsPosition[2]
                        playerops.GetPlaylistPosition(2)
                        PlaylistEmby[2] = PlayingItem["EmbyServer"].API.session_playing(PlayingItem["EmbySessionData"], PlaylistKodi[2], PlaylistEmby[2], playerops.PlaylistsPosition[2])
                        EmbyPlaying = True
                        playerops.AVStarted = True
                        playerops.EmbyIdPlaying = int(MetaData["EmbyId"])

                        with utils.SafeLock(playerops.AVStartedCondition):
                            playerops.AVStartedCondition.notify_all()

                        if not PicturePlaybackInit:
                            PicturePlaybackInit = True
                            EmbyIds = []

                            for Playlist in PlaylistEmby[2]:
                                EmbyIds.append(str(Playlist['Id']))

                            EmbyIdsString = ','.join(EmbyIds)

                            if not PlayingItem["EmbyServer"].EmbySession:
                                xbmc.log("EMBY.helper.player: No Emby session for picture playback", 2) # LOGWARNING
                                continue

                            playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "play", EmbyIdsString, playerops.PlaylistsPosition[2])

                            if EventData['player']['speed'] == 0:
                                PlayerEventsQueue.put((("pause",),))

                            continue

                        if EventData['player']['speed'] != 0:
                            if playerops.PlayerPause or playerops.RemoteCommandActiveGet(1) > 0:
                                PlayerEventsQueue.put((("resume",),))
                                continue

                        if PlayingItem["EmbyServer"] and PlayingItem["EmbyServer"].EmbySession:
                            if PlaylistPositionOld < playerops.PlaylistsPosition[2]:
                                playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "nexttrack")
                            elif PlaylistPositionOld > playerops.PlaylistsPosition[2]:
                                playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "previoustrack")
                    else:
                        xbmc.log(f"EMBY.helper.player: play no Id found: {EventData}", 2) # LOGWARNING
            elif Commands[0] == "playerid": # {"player":{"playerid":1,}}  # This is a custom command, not by Kodi events (youtube)
                xbmc.log("EMBY.helper.player: [ onPlayerId ]", 1) # LOGINFO
                EventData = json.loads(Commands[1])
                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onPlayerId ] {EventData}", 1) # LOGDEBUG
                set_PlayerId(EventData)
            elif Commands[0] == "pause": # {"item":{"id":22352,"type":"episode"},"player":{"playerid":1,"speed":0}}
                xbmc.log("EMBY.helper.player: [ onPlayBackPaused ]", 1) # LOGINFO
                playerops.PlayerPause = True

                if not PlayingItem["EmbySessionData"]:
                    playerops.RemoteCommand(None, None, "pause")
                    continue

                if playerops.PlayerId != 2: # Music, Video
                    PositionTicks = playerops.PlayBackPosition()

                    if PositionTicks:
                        PlayingItem["EmbySessionData"].update({'PositionTicks': PositionTicks, 'IsPaused': True})
                    else:
                        PlayingItem["EmbySessionData"]['IsPaused'] = True
                else: # Picture
                    PlayingItem["EmbySessionData"]['IsPaused'] = True

                if PlayingItem["EmbyServer"]:
                    if PlayingItem["EmbyServer"].EmbySession:
                        playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "pause")

                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "Pause", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])

                if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): -->[ paused ]", 1) # LOGDEBUG
            elif Commands[0] == "resume": # {"item":{"id":22352,"type":"episode"},"player":{"playerid":1,"speed":1}}
                xbmc.log("EMBY.helper.player: [ onPlayBackResumed ]", 1) # LOGINFO
                playerops.PlayerPause = False

                if not PlayingItem["EmbySessionData"]:
                    playerops.RemoteCommand(None, None, "unpause")
                    continue

                if PlayingItem["EmbyServer"]:
                    if PlayingItem["EmbyServer"] and PlayingItem["EmbyServer"].EmbySession:
                        playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "unpause")

                    PlayingItem["EmbySessionData"]['IsPaused'] = False
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "Unpause", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                    TrackerPaused = True

                if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): --<[ paused ]", 1) # LOGDEBUG
            elif Commands[0] == "stop": # {'end': True, 'item': {'id': 33874, 'type': 'episode'}}; '{"end":false,"item":{"id":107446349,"type":"song"}}'
                xbmc.log("EMBY.helper.player: [ onPlayBackStopped ]", 1) # LOGINFO
                EventData = json.loads(Commands[1])
                KodiId = 0
                KodiTypeId = 0
                utils.update_SyncPause('playing', False)
                utils.unset_SyncLock()
                ProgressBarEnable = 5
                Failed = EventData.get("fail", False)
                ResetPlayItem = False

                if "item" in EventData: # remove from skipped items list
                    if 'id' in EventData['item']:
                        KodiId = EventData["item"]["id"]
                        KodiTypeId = EventData["item"]["type"]

                        if (KodiId, KodiTypeId) == PlayItem:
                            ResetPlayItem = True

                if PlayItem[1] =='unknown':
                    ResetPlayItem = True

                if KodiId:
                    if not EventData['end']: # remove from skipped items list
                        ItemsUpdateQueue.put(f'{{"DELETE": [{KodiId}, "{KodiTypeId}"]}}')  # Do not delete the item diectly from utils.ItemKodiSkipUpdate, to keep the events in order

                    # Dummy (blankwav) played
                    if ForceStopKodiId == EventData["item"]["id"]:
                        ForceStopKodiId = 0
                        playerops.Stopped = True

                        if ResetPlayItem:
                            PlayItem = (0, "")

                        with utils.SafeLock(ForceStopCondition):
                            ForceStopCondition.notify_all()

                        if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): [ forced stop ]", 1) # LOGDEBUG
                        continue

                if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ onPlayBackStopped ] {EventData}", 1) # LOGDEBUG
                playerops.AVStarted = False
                playerops.AVStart = False
                PicturePlaybackInit = False

                if PlayItem[1] != "picture":
                    playerops.EmbyIdPlaying = 0

                playerops.PlayerPause = False

                with utils.SafeLock(playerops.AVStartedCondition):
                    playerops.AVStartedCondition.notify_all()

                if Failed and VideoPlayback == "TRAILER" and QueuedPlayingItem:
                    PlayingItem = copy.Object(QueuedPlayingItem)

                if not PlayingItem["EmbySessionData"]: # Playback never triggered avstart
                    if PlayingItemInit and PlayingItemInit["EmbySessionData"]: # Play was triggered, but avstart never did. This can happen on invalid (livetv) streams.
                        if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): [ cancel session by PlayingItemInit ]", 1) # LOGDEBUG
                        PlayingItemInitLocal = copy.Object(PlayingItemInit)
                        PlayingItemInit = {"EmbySessionData": {}, "IntroStartPositionTicks": 0, "IntroEndPositionTicks": 0, "CreditsPositionTicks": 0, "EmbyServer": None, "KodiType": "", "Filename": "", "IndexMappingVideoEmby": {}, "IndexMappingVideoKodi": {}, "IndexMappingAudioEmby": {}, "IndexMappingAudioKodi": {}, "IndexMappingSubtitleEmby": {}, "IndexMappingSubtitleKodi": {}, "SubtitleEnabled": False, "SubtitleIndexKodi": 0}
                        PlayingItemInitLocal["EmbyServer"].API.session_stop(PlayingItemInitLocal["EmbySessionData"])

                    playerops.RemoteCommand(None, None, "stop")
                    playerops.Stopped = True

                    if ResetPlayItem:
                        PlayItem = (0, "")

                    with utils.SafeLock(ForceStopCondition):
                        ForceStopCondition.notify_all()

                    continue

                if PlayingItem["EmbyServer"] and PlayingItem["EmbyServer"].EmbySession:
                    playerops.RemoteCommand(PlayingItem["EmbyServer"].ServerData['ServerId'], PlayingItem["EmbyServer"].EmbySession[0]['Id'], "stop")

                VideoPlaybackOld = VideoPlayback

                if EventData['end'] == "quit":
                    stop_playback(False, False)
                elif EventData['end']: # finished play and play next playlist item: {"end":true,"item":{"id":215,"type":"episode"}}
                    stop_playback(True, True)
                else: # stopped in playlist: '{"end":false,"item":{"id":215,"type":"episode"}}'; play next item but playlist is at the end: '{"end":false,"item":{"type":"unknown"}}, -> playback failed
                    stop_playback(True, False)

                if ResetPlayItem:
                    PlayItem = (0, "")

                with utils.SafeLock(ForceStopCondition):
                    ForceStopCondition.notify_all()

                playerops.Stopped = True

                with utils.SafeLock(playerops.StoppedCondition):
                    playerops.StoppedCondition.notify_all()

                xbmc.log("EMBY.helper.player: --<[ playback ]", 1) # LOGINFO
            elif Commands[0] == "volume":
                EventData = json.loads(Commands[1])
                Muted = EventData["muted"]
                Volume = EventData["volume"]

                if not PlayingItem["EmbySessionData"]:
                    continue

                PlayingItem["EmbySessionData"].update({'VolumeLevel': Volume, 'IsMuted': Muted})

                if PlayingItem["EmbyServer"]:
                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "VolumeChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
            elif Commands[0] == "propertychanged":
                # {"player":{"playerid":1},"property":{"currentsubtitle":{"codec":"","index":9,"isdefault":false,"isforced":false,"isimpaired":false,"language":"de","name":"2 (External)"}}}
                # {"player":{"playerid":1},"property":{"currentsubtitle":{"codec":"SubRip","index":6,"isdefault":false,"isforced":false,"isimpaired":false,"language":"ja","name":""}}}
                # {"player":{"playerid":1},"property":{"subtitleenabled":false}}
                # {"player":{"playerid":1},"property":{"subtitleenabled":true}}
                # {"player":{"playerid":1},"property":{"currentaudiostream":{"bitrate":0,"channels":1,"codec":"AAC-LC 1.0","index":1,"isdefault":false,"isimpaired":false,"isoriginal":false,"language":"en","name":"Commentary"}}}
                # {"player":{"playerid":1},"property":{"currentaudiostream":{"bitrate":0,"channels":2,"codec":"AAC-LC 2.0","index":0,"isdefault":true,"isimpaired":false,"isoriginal":false,"language":"","name":""}}}
                # {'player': {'playerid': -1}, 'property': {'currentsubtitle': {'codec': '', 'index': 10, 'isdefault': False, 'isforced': False, 'isimpaired': False, 'language': 'de', 'name': '3 (External)'}}}

                if not PlayingItem["EmbySessionData"]:
                    continue

                EventData = json.loads(Commands[1])

                if "currentaudiostream" in EventData['property'] and "index" in EventData['property']["currentaudiostream"] and EventData['property']["currentaudiostream"]["index"] in PlayingItem["IndexMappingAudioKodi"]:
                    PlayingItem["EmbySessionData"].update({'AudioStreamIndex': PlayingItem["IndexMappingAudioKodi"][EventData['property']["currentaudiostream"]["index"]]})
                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "AudioTrackChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                elif "currentsubtitle" in EventData['property'] and "index" in EventData['property']["currentsubtitle"]:
                    PlayingItem["SubtitleIndexKodi"] = EventData['property']["currentsubtitle"]["index"]

                    if PlayingItem["SubtitleEnabled"] and PlayingItem["SubtitleIndexKodi"] in PlayingItem["IndexMappingSubtitleKodi"]:
                        PlayingItem["EmbySessionData"].update({'SubtitleStreamIndex': PlayingItem["IndexMappingSubtitleKodi"][PlayingItem["SubtitleIndexKodi"]]})
                        TrackerPaused = True
                        PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "SubtitleTrackChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                elif "subtitleenabled" in EventData['property']:
                    PlayingItem["SubtitleEnabled"] = EventData['property']["subtitleenabled"]

                    if not PlayingItem["SubtitleEnabled"]:
                        PlayingItem["EmbySessionData"].update({'SubtitleStreamIndex': -1})
                    elif PlayingItem["SubtitleIndexKodi"] in PlayingItem["IndexMappingSubtitleKodi"]:
                        PlayingItem["EmbySessionData"].update({'SubtitleStreamIndex': PlayingItem["IndexMappingSubtitleKodi"][PlayingItem["SubtitleIndexKodi"]]})

                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "SubtitleTrackChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                elif "repeat" in EventData['property']:
                    Repeat = parse_repeat(EventData['property']['repeat'])
                    playerops.RepeatMode[playerops.PlayerId] = Repeat
                    PlayingItem["EmbySessionData"].update({'RepeatMode': playerops.RepeatMode[playerops.PlayerId]})
                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "RepeatModeChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                elif "shuffled" in EventData['property']:
                    Shuffle = EventData['property']['shuffled']
                    playerops.Shuffled[playerops.PlayerId] = Shuffle
                    PlayingItem["EmbySessionData"].update({'Shuffle': playerops.Shuffled[playerops.PlayerId]})
                    TrackerPaused = True
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "ShuffleChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
            elif Commands[0] == "speedchanged": # {"item":{"id":215,"type":"episode"},"player":{"playerid":1,"speed":2}}
                if not PlayingItem["EmbySessionData"]:
                    continue

                EventData = json.loads(Commands[1])
                playerops.PlaybackRate[playerops.PlayerId] = float(playerops.GetTempo()) # Get real speed. Kodi has two speed params. tempo and speed. Tempo is (with audio, range 0.8 to 1.5). Speed is fast forward and accepts integers.
                PlayingItem["EmbySessionData"].update({'PlaybackRate': playerops.PlaybackRate[playerops.PlayerId]})
                TrackerPaused = True
                PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "PlaybackRateChange", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
            elif Commands[0] == "clear": # '{"playlistid":1}'
                EventData = json.loads(Commands[1])
                playerops.PlaylistsPosition[EventData['playlistid']] = -1
                PlaylistKodi[EventData['playlistid']] = []

                if not PlayingItem["EmbySessionData"]:
                    continue

                TrackerPaused = True
                PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "PlaylistItemRemove", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
            elif Commands[0] == "remove": # '{"playlistid":1,"position":0}'


                EventData = json.loads(Commands[1])
                PlaylistId = EventData['playlistid']
                Position = EventData['position']

                if playerops.PlaylistsPosition[PlaylistId] >= Position:
                    playerops.PlaylistsPosition[PlaylistId] -= 1

                if Position < len(PlaylistKodi[PlaylistId]):
                    del PlaylistKodi[PlaylistId][Position]

                if not PlayingItem["EmbySessionData"]:
                    continue

                TrackerPaused = True
                PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "PlaylistItemRemove", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
            elif Commands[0] == "add": # unsyncd video = '{"item":{"id":1000018721,"type":"episode"},"playlistid":1,"position":0}'; synced video = '{"item":{"id":4268,"type":"episode"},"playlistid":1,"position":2}'; unsynced music = {"item":{"id":1000073262,"type":"song"},"playlistid":0,"position":0}; unsynced music external played e.g. via favorites'{"item":{"album":"Bella stella","artist":["Highland"],"title":"Bella stella","track":1,"type":"song"},"playlistid":0,"position":0}'; synced music = '{"item":{"id":233155,"type":"song"},"playlistid":0,"position":0}')
                EventData = json.loads(Commands[1])

                if playerops.PlaylistsPosition[EventData['playlistid']] >= EventData['position']:
                    playerops.PlaylistsPosition[EventData['playlistid']] += 1

                if 'id' in EventData['item']:
                    PlaylistKodi[EventData['playlistid']].insert(EventData['position'], {"KodiId": EventData['item']['id'], "KodiType": EventData['item']['type']})
                elif 'file' in EventData['item'] and (EventData['item']['file'].startswith("image://emby@dav%3A%2F%2F127.0.0.1%3A57342") or EventData['item']['file'].startswith("image://epg@dav%3A%2F%2F127.0.0.1%3A57342")):
                    PlaylistKodi[EventData['playlistid']].insert(EventData['position'], {"KodiFile": EventData['item']['file']})

    if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: ---<[ player commands ]", 1) # LOGDEBUG

def set_PlayerId(EventData):
    LocalPlayerId = -1

    if 'player' in EventData and 'playerid' in EventData['player']: # This can return -1 when no playlist is available. e.g. pleaylist clear during playback
        LocalPlayerId = EventData['player']['playerid']

    if LocalPlayerId == -1 and 'item' in EventData and 'type' in EventData['item']:
        if EventData['item']['type'] == "song":
            LocalPlayerId = 0
        elif EventData['item']['type'] in ("episode", "video", "movie", "musicvideo", "channel"):
            LocalPlayerId = 1
        elif EventData['item']['type'] == "picture":
            LocalPlayerId = 2

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

    if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): [ played info ] {PlayingItem}", 1) # LOGDEBUG
    PlayingItemLocal = copy.Object(PlayingItem)
    TrackerPaused = False
    playerops.PlaybackRate[playerops.PlayerId] = 1.0

    if MultiselectionDone:
        if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): stop_playback MultiselectionDone", 1) # LOGDEBUG
        return

    if not PlayingItemLocal["EmbyServer"]:
        xbmc.log("EMBY.helper.player: stop_playback no PlayingItemLocal", 2) # LOGWARNING
        return

    EmbyPlaying = False
    PlayingItem = {"EmbySessionData": {}, "IntroStartPositionTicks": 0, "IntroEndPositionTicks": 0, "CreditsPositionTicks": 0, "EmbyServer": None, "KodiType": "", "Filename": "", "IndexMappingVideoEmby": {}, "IndexMappingVideoKodi": {}, "IndexMappingAudioEmby": {}, "IndexMappingAudioKodi": {}, "IndexMappingSubtitleEmby": {}, "IndexMappingSubtitleKodi": {}, "SubtitleEnabled": False, "SubtitleIndexKodi": 0}

    if PlaybackEnded and PlayingItemLocal["EmbySessionData"]['RunTimeTicks']:
        PlayingItemLocal["EmbySessionData"]['PositionTicks'] = PlayingItemLocal["EmbySessionData"]['RunTimeTicks']

    if PlaybackEnded:
        KodiPositionSeconds = 0.0
    else:
        KodiPositionSeconds = PlayingItemLocal["EmbySessionData"]['PositionTicks'] / 10000000.0

    cache.update_userdata_Kodi(str(PlayingItemLocal["EmbySessionData"]['ItemId']), PlayingItemLocal["EmbyServer"].ServerData['ServerId'], KodiPositionSeconds, utils.currenttime(), PlaybackEnded, PlayingItemLocal["EmbySessionData"]['RunTimeTicks'] / 10000000.0, None)

    if not utils.RemoteMode:
        utils.ItemSkipUpdate.append(str(PlayingItemLocal["EmbySessionData"]['ItemId'])) # Skip Emby progress updates as Kodi keeps track

    PlayingItemLocal["EmbyServer"].API.session_stop(PlayingItemLocal["EmbySessionData"])
    close_SkipIntroDialog()
    close_SkipCreditsDialog()

    if PlaybackEnded and VideoPlaybackOld in ("TRAILER", "READY") and VideoPlayback == "TRAILER":
        if not Trailers: # Play initial item
            VideoPlayback = "CONTENT"
            playerops.PlayPlaylistItem(1, PlaylistIndexContent)
            return

        # play trailers
        play_Trailer(PlayingItemLocal["EmbyServer"])
        return

    if VideoPlayback != "TRAILERLOADING":
        VideoPlayback = "READY"
        Trailers = []

    if not PlayingItemLocal["EmbySessionData"]:
        return

    # Set watched status
    if delete and PlayingItemLocal["Filename"]:
        if utils.offerDelete:
            DeleteContentQueue.put(PlayingItemLocal)

def DeleteContent():
    if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: --->[ DeleteContent ]", 1) # LOGDEBUG

    while True:
        DeleteItem = DeleteContentQueue.get()

        if DeleteItem == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: ---<[ DeleteContent ] quit", 1) # LOGDEBUG
            return

        RunTimeTicks = int(DeleteItem["EmbySessionData"]['RunTimeTicks'])
        PositionTicks = int(DeleteItem["EmbySessionData"]['PositionTicks'])

        if RunTimeTicks > 10:
            if PositionTicks > RunTimeTicks * 0.90:  # 90% Progress
                DeleteMsg = False

                if DeleteItem["KodiType"] == 'episode' and utils.deleteTV:
                    DeleteMsg = True
                elif DeleteItem["KodiType"] == 'movie' and utils.deleteMovies:
                    DeleteMsg = True

                if DeleteMsg:
                    xbmc.log("EMBY.helper.player: Offer delete option", 1) # LOGINFO

                    if utils.Dialog.yesno(heading=utils.Translate(33015), message=DeleteItem["Filename"], autoclose=int(utils.autoclose) * 1000):
                        DeleteItem["EmbyServer"].API.delete_item(DeleteItem["EmbySessionData"]['ItemId'])
                        DeleteItem["EmbyServer"].library.removed((DeleteItem["EmbySessionData"]['ItemId'],), True)

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
    PathLower = Trailers[0]['Path'].lower()

    if (PathLower.startswith("http://") or PathLower.startswith("https://")) and PathLower.find("youtube") != -1 and (PathLower.find("plugin.video.youtube") == -1 or PathLower.find("youtu.be") != -1):
        Path = utils.get_youtube_path(Trailers[0]['Path'])
    else:
        Container = Trailers[0].get('Container', 'ukn')

        if MediaSourceId:
            Path = f"{EmbyServer.ServerData['ServerUrl']}/emby/videos/{Trailers[0]['Id']}/stream.{Container}?static=true&MediaSourceId={MediaSourceId}&PlaySessionId={PlaySessionId}&DeviceId={EmbyServer.ServerData['DeviceId']}&api_key={EmbyServer.ServerData['AccessToken']}&stream.{Container}"
        else:
            Path = f"{EmbyServer.ServerData['ServerUrl']}/emby/videos/{Trailers[0]['Id']}/stream.{Container}?static=true&PlaySessionId={PlaySessionId}&DeviceId={EmbyServer.ServerData['DeviceId']}&api_key={EmbyServer.ServerData['AccessToken']}&stream.{Container}"

    # Play trailer
    listitem.set_ListItem(Trailers[0], EmbyServer.ServerData['ServerId'])
    ListItem = Trailers[0]['ListItem']
    VideoPlayback = "TRAILER"
    ListItem.setPath(Path)
    QueuedPlayingItem = {
        "EmbySessionData": {
            "QueueableMediaTypes": ["Audio", "Video", "Photo"],
            "CanSeek": True,
            "IsPaused": False,
            "ItemId": int(Trailers[0]["Id"]),
            "MediaSourceId": MediaSourceId,
            "PlaySessionId": PlaySessionId,
            "PositionTicks": 0,
            "RunTimeTicks": 0,
            "VolumeLevel": Volume,
            "PlaybackRate": playerops.PlaybackRate[playerops.PlayerId],
            "Shuffle": playerops.Shuffled[playerops.PlayerId],
            "RepeatMode": playerops.RepeatMode[playerops.PlayerId],
            "IsMuted": Muted
        },
        "IntroStartPositionTicks": 0,
        "IntroEndPositionTicks": 0,
        "CreditsPositionTicks": 0,
        "EmbyServer": EmbyServer,
        "KodiType": "video",
        "Filename": Path,
        "IndexMappingVideoEmby": {},
        "IndexMappingVideoKodi": {},
        "IndexMappingAudioEmby": {},
        "IndexMappingAudioKodi": {},
        "IndexMappingSubtitleEmby": {},
        "IndexMappingSubtitleKodi": {},
        "SubtitleEnabled": False,
        "SubtitleIndexKodi": 0
    }
    del Trailers[0]
    playerops.Play(False, Path, ListItem, False, False)

def PositionTracker():
    global PlayerBusyDelay
    global SkipIntroJumpDone
    global SkipCreditsJumpDone
    global TrackerPaused
    global ProgressBarEnable
    global PicturePlaybackInit
    LoopCounter = 1
    if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: --->[ position tracker ]", 1) # LOGDEBUG
    PlayerBusy = False

    while True:
        # Enable progress bars 5 seconds after playback stop
        if ProgressBarEnable == 0:
            if utils.DebugLog: xbmc.log("EMBY.helper.player [ position tracker ] eneable progress bars", 1) # LOGDEBUG
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
            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): THREAD: ---<[ position tracker ]", 1) # LOGDEBUG
            PlayerBusy = False
            return

        with utils.SafeLock(PlayerLock):
            if not EmbyPlaying or not PlayingItem["EmbySessionData"] or not PlayItem[0]:
                LoopCounter = 1
                continue

            if PlayingItem["KodiType"] == "picture": # Picture player
                if not xbmc.getCondVisibility("Window.IsActive(12007)"): # 12007 -> slideshow
                    if PicturePlaybackInit:
                        PicturePlaybackInit = False
                        PlayerEventsQueue.put((("stop", '{"end":true, "fail":false}'),))

                    continue
            else:
                PositionTicks = playerops.PlayBackPosition()
                RunTimeTicks = PlayingItem["EmbySessionData"].get('RunTimeTicks', 0)

                if not RunTimeTicks:
                    RunTimeTicks = playerops.PlayBackDuration()
                    PlayingItem["EmbySessionData"]['RunTimeTicks'] = RunTimeTicks

                if PositionTicks:
                    PlayingItem["EmbySessionData"]['PositionTicks'] = PositionTicks

                if RunTimeTicks and (PositionTicks + 20000000) > RunTimeTicks: # 2 seconds before playback ends pause updates
                    PlayerBusyDelay = 5

                if utils.DebugLog: xbmc.log(f'EMBY.helper.player (DEBUG): PositionTracker: PositionTicks: {PositionTicks} / IntroStartPositionTicks: {PlayingItem["IntroStartPositionTicks"]} / IntroEndPositionTicks: {PlayingItem["IntroEndPositionTicks"]} / CreditsPositionTicks: {PlayingItem["CreditsPositionTicks"]} / SkipIntroJumpDone: {SkipIntroJumpDone}', 1) # LOGDEBUG

                if VideoPlayback not in ("THEME", "THEMEINIT"):
                    if utils.enableSkipIntro:
                        if PlayingItem["IntroStartPositionTicks"] < PositionTicks < PlayingItem["IntroEndPositionTicks"]:
                            if not SkipIntroJumpDone:
                                SkipIntroJumpDone = True

                                if utils.askSkipIntro:
                                    if utils.skipintroembuarydesign:
                                        if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): --->[ SkipIntroDialogEmbuary ]", 1) # LOGDEBUG
                                        SkipIntroDialogEmbuary.show()
                                    else:
                                        if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): --->[ SkipIntroDialog ]", 1) # LOGDEBUG
                                        SkipIntroDialog.show()
                                else:
                                    jump_Intro()
                                    LoopCounter = 0
                                    continue
                        else:
                            close_SkipIntroDialog()

                    if utils.enableSkipCredits:
                        if PlayingItem["CreditsPositionTicks"] and PositionTicks > PlayingItem["CreditsPositionTicks"]:
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
            if LoopCounter % 20 == 0 and PlayingItem["EmbyServer"]: # modulo 50
                if not TrackerPaused:
                    if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): PositionTracker: Report progress {PlayingItem['EmbySessionData']['PositionTicks']}", 1) # LOGDEBUG
                    PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "TimeUpdate", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
                else:
                    TrackerPaused = False

                LoopCounter = 0

            LoopCounter += 1

def jump_Intro():
    global SkipIntroJumpDone
    global TrackerPaused
    xbmc.log(f"EMBY.helper.player: Skip intro jump {PlayingItem['IntroEndPositionTicks']}", 1) # LOGINFO

    if PlayingItem["EmbyServer"]:
        playerops.Seek(PlayingItem["IntroEndPositionTicks"])
        PlayingItem["EmbySessionData"]['PositionTicks'] = PlayingItem["IntroEndPositionTicks"]
        SkipIntroJumpDone = True
        TrackerPaused = True
        PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_progress(PlayingItem["EmbySessionData"], "TimeUpdate", PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
    else:
        xbmc.log(f"EMBY.helper.player: Skip intro jump error: {PlayingItem}", 3) # LOGERROR

def jump_Credits():
    global SkipCreditsJumpDone

    if PlayingItem["EmbySessionData"].get('RunTimeTicks', 0):
        xbmc.log(f"EMBY.helper.player: Skip credits jump {PlayingItem['EmbySessionData']['RunTimeTicks']}", 1) # LOGINFO
        playerops.Seek(PlayingItem["EmbySessionData"]['RunTimeTicks'])
        PlayingItem["EmbySessionData"]['PositionTicks'] = PlayingItem["EmbySessionData"]['RunTimeTicks']
        SkipCreditsJumpDone = True
    else:
        xbmc.log("EMBY.helper.player: Skip credits, invalid RunTimeTicks", 1) # LOGINFO

def close_SkipIntroDialog():
    if utils.skipintroembuarydesign:
        if SkipIntroDialogEmbuary.dialog_open:
            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): ---<[ SkipIntroDialogEmbuary ]", 1) # LOGDEBUG
            SkipIntroDialogEmbuary.close()
    else:
        if SkipIntroDialog.dialog_open:
            if utils.DebugLog: xbmc.log("EMBY.helper.player (DEBUG): ---<[ SkipIntroDialog ]", 1) # LOGDEBUG
            SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

def load_queuePlayingItem():
    global PlayerBusyDelay
    if utils.DebugLog: xbmc.log("EMBY.helper.player: [ Queue playing item ]", 1) # LOGINFO
    PlayerBusyDelay = 5

    if not QueuedPlayingItem.get("Loaded", False):
        if QueuedPlayingItem["IntroStartPositionTicks"]:
            QueuedPlayingItem["IntroStartPositionTicks"] = QueuedPlayingItem["IntroStartPositionTicks"] * 10000000
        else:
            QueuedPlayingItem["IntroStartPositionTicks"] = 0

        if QueuedPlayingItem["IntroEndPositionTicks"]:
            QueuedPlayingItem["IntroEndPositionTicks"] = QueuedPlayingItem["IntroEndPositionTicks"] * 10000000
        else:
            QueuedPlayingItem["IntroEndPositionTicks"] = 0

        if QueuedPlayingItem["CreditsPositionTicks"]:
            QueuedPlayingItem["CreditsPositionTicks"] = QueuedPlayingItem["CreditsPositionTicks"] * 10000000
        else:
            QueuedPlayingItem["CreditsPositionTicks"] = 0

        playerops.AVStarted = False
        playerops.EmbyIdPlaying = int(QueuedPlayingItem["EmbySessionData"]['ItemId'])

        with utils.SafeLock(playerops.AVStartedCondition):
            playerops.AVStartedCondition.notify_all()

        if QueuedPlayingItem["EmbyServer"] and QueuedPlayingItem["EmbyServer"].EmbySession:
            playerops.RemoteCommand(QueuedPlayingItem["EmbyServer"].ServerData['ServerId'], QueuedPlayingItem["EmbyServer"].EmbySession[0]['Id'], "play", QueuedPlayingItem["EmbySessionData"]['ItemId'])

        QueuedPlayingItem["Loaded"] = True

def Cancel():
    playerops.Stop()
    utils.update_SyncPause('playing', False)
    utils.unset_SyncLock()

def load_KodiItem(TaskId, KodiItemId, Type, CachedItem, MediaSourceIndex):
    if CachedItem:
        common.set_path_filename(CachedItem, CachedItem['ServerId'], CachedItem['MediaSources'][MediaSourceIndex], True)
        return CachedItem['ListItem']

    videodb = dbio.DBOpenRO("video", TaskId)

    if Type == "movie":
        KodiItem = videodb.get_movie_metadata_for_listitem(KodiItemId, "")
    elif Type == "episode":
        KodiItem = videodb.get_episode_metadata_for_listitem(KodiItemId, "")
    elif Type == "musicvideo":
        KodiItem = videodb.get_musicvideos_metadata_for_listitem(KodiItemId, "")
    else:
        KodiItem = {}

    dbio.DBCloseRO("video", TaskId)

    if KodiItem:
        listitem.set_ListItem_from_Kodi_database(KodiItem, "")
        return KodiItem['ListItem']

    return None

def replace_playlist_listitem(ListItem, Path):
    global PlaylistRemoveItem
    PlaylistRemoveItem = playerops.GetPlaylistPosition(1) # old listitem will be removed after play next
    playerops.XbmcPlaylists[1].add(Path, ListItem, PlaylistRemoveItem + 1)
    load_queuePlayingItem()

def find_EmbyContent(FullPath, KodiId, KodiType):
    global QueuedPlayingItem
    EmbyId = 0
    ServerId = ""
    KodiItem = {}
    isDynamic = False
    MediaSources = []
    CachedItem = None

    if KodiId:
        EmbyId, ServerId = utils.get_EmbyId_ServerId_by_Fake_KodiId(KodiId) # Get Emby data injected by dynamic content

        if EmbyId:
            isDynamic = True

    # Get actual url
    FullPathMod = FullPath

    if FullPath.startswith("bluray://"):
        FullPathMod = unquote_plus(FullPathMod) # double unquote
        FullPathMod = unquote_plus(FullPathMod) # double unquote
        FullPathMod = FullPathMod.replace("bluray://", "")
        FullPathMod = FullPathMod.replace("udf://", "")
        FullPathMod = FullPathMod[:FullPathMod.find("//")]

    # Get cached item
    if EmbyId:
        CachedItem = cache.get_ItemByEmbyId(EmbyId, ServerId)

    if not CachedItem:
        CachedItem = cache.get_ItemByPath(FullPathMod)

    isAddonContent = FullPathMod.startswith("dav://127.0.0.1:57342") or FullPathMod.startswith("http://127.0.0.1:57342") or FullPathMod.startswith("/emby_addon_mode/")

    # happens for m3u playlists and other special content. Kodi does not recognize it's own content even it's in Kodi's database. Check if KodiId is available from addon's database
    # Player's ListItem must be updated
    if not CachedItem and not KodiId:
        # Addon mode
        if isAddonContent: # e.g. playlists played
            # QueuedPlayingItem is fully loaded at this point by webservice.py
            if not QueuedPlayingItem: # Playback was stopped, before
                return 0, isAddonContent, isDynamic, "", [], {}

            EmbyId = QueuedPlayingItem["EmbySessionData"]['ItemId']
            KodiType = QueuedPlayingItem["KodiType"]
            EmbyType = utils.KodiTypeMapping[KodiType]
        else:
            # Native mode
            # QueuedPlayingItem is not set at this point, needs to be updated
            # No data available, try to load via path from synced content database
            ServerId = ""

            for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                embydb = dbio.DBOpenRO(ServerId, "onAVStarted")
                EmbyId = embydb.get_mediasource_EmbyID_by_path(FullPathMod)

                if EmbyId:
                    KodiIdByMetadata, EmbyType, MediaSources = embydb.get_metadata_by_EmbyId_EmbyType(EmbyId, "")
                    dbio.DBCloseRO(ServerId, "onAVStarted")

                    if not EmbyType or ServerId not in utils.EmbyServers:
                        return 0, isAddonContent, isDynamic, "", [], {}

                    KodiType = utils.EmbyTypeMapping[EmbyType]
                    QueuedPlayingItem = {
                        "EmbySessionData": {
                            "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                            "CanSeek": not bool(KodiType == "channel"),
                            "IsPaused": False,
                            "ItemId": EmbyId,
                            "MediaSourceId": MediaSources[0]["Id"],
                            "PlaySessionId": str(uuid.uuid4()).replace("-", ""),
                            "PositionTicks": 0,
                            "RunTimeTicks": 0,
                            "VolumeLevel": Volume,
                            "PlaybackRate": playerops.PlaybackRate[playerops.PlayerId],
                            "Shuffle": playerops.Shuffled[playerops.PlayerId],
                            "RepeatMode": playerops.RepeatMode[playerops.PlayerId],
                            "IsMuted": Muted
                        },
                        "IntroStartPositionTicks": MediaSources[0].get("IntroStartPositionTicks", 0),
                        "IntroEndPositionTicks": MediaSources[0].get("IntroEndPositionTicks", 0),
                        "CreditsPositionTicks": MediaSources[0].get("CreditsPositionTicks", 0),
                        "EmbyServer": utils.EmbyServers[ServerId],
                        "KodiType": KodiType,
                        "Filename": FullPath,
                        "IndexMappingVideoEmby": MediaSources[0]['IndexMappingVideoEmby'],
                        "IndexMappingVideoKodi": MediaSources[0]['IndexMappingVideoKodi'],
                        "IndexMappingAudioEmby": MediaSources[0]['IndexMappingAudioEmby'],
                        "IndexMappingAudioKodi": MediaSources[0]['IndexMappingAudioKodi'],
                        "IndexMappingSubtitleEmby": MediaSources[0]['IndexMappingSubtitleEmby'],
                        "IndexMappingSubtitleKodi": MediaSources[0]['IndexMappingSubtitleKodi'],
                        "SubtitleEnabled": False,
                        "SubtitleIndexKodi": 0
                    }
                    break

                dbio.DBCloseRO(ServerId, "onAVStarted")
            else: # not found
                return 0, isAddonContent, isDynamic, "", [], {}

            if KodiType == 'episode':
                videodb = dbio.DBOpenRO("video", "find_EmbyContent")
                KodiItem = videodb.get_episode_metadata_for_listitem(KodiIdByMetadata, FullPathMod)
                dbio.DBCloseRO("video", "find_EmbyContent")
                listitem.set_ListItem_from_Kodi_database(KodiItem, FullPath)
            elif KodiType == 'musicvideo':
                videodb = dbio.DBOpenRO("video", "find_EmbyContent")
                KodiItem = videodb.get_musicvideos_metadata_for_listitem(KodiIdByMetadata, FullPathMod)
                dbio.DBCloseRO("video", "find_EmbyContent")
                listitem.set_ListItem_from_Kodi_database(KodiItem, FullPath)
            elif KodiType == 'movie':
                videodb = dbio.DBOpenRO("video", "find_EmbyContent")
                KodiItem = videodb.get_movie_metadata_for_listitem(KodiIdByMetadata, FullPathMod)
                dbio.DBCloseRO("video", "find_EmbyContent")
                listitem.set_ListItem_from_Kodi_database(KodiItem, FullPath)
            elif KodiType == 'song':
                musicdb = dbio.DBOpenRO("music", "find_EmbyContent")
                KodiItem = musicdb.get_song_metadata_for_listitem(KodiIdByMetadata)
                dbio.DBCloseRO("music", "find_EmbyContent")
                listitem.set_ListItem_from_Kodi_database(KodiItem, FullPath)

            xbmc.log("EMBY.helper.player: Update player info for special content", 1)

            if 'ListItem' in KodiItem and not playerops.UpdateInfoTag(KodiItem['ListItem']):
                xbmc.log("EMBY.helper.player: UpdateInfoTag failed 1", 3)
                return 0, isAddonContent, isDynamic, "", [], {}

            return EmbyId, isAddonContent, isDynamic, EmbyType, MediaSources, {}

    # found cached item (dynamic content)
    if CachedItem and "ServerId" in CachedItem and "Type" in CachedItem and CachedItem["ServerId"] in utils.EmbyServers:
        xbmc.log("EMBY.helper.player: Update player info by cached listitem", 1)

        if FullPathMod.startswith("dav://127.0.0.1:57342") or FullPathMod.startswith("http://127.0.0.1:57342") or FullPathMod.startswith("/emby_addon_mode/"): # e.g. playlists played
            EmbyType = CachedItem["Type"]
        else: # Load native played content from cache
            KodiType = utils.EmbyTypeMapping[CachedItem["Type"]]
            EmbyType = CachedItem["Type"]
            MediaSources = CachedItem['MediaSources']
            IndexMappingVideoEmby = {}
            IndexMappingVideoKodi = {}
            IndexMappingAudioEmby = {}
            IndexMappingAudioKodi = {}
            IndexMappingSubtitleEmby = {}
            IndexMappingSubtitleKodi = {}

            for MediaSourceData in MediaSources:
                for IndexKodi, VideoStream in enumerate(MediaSourceData['KodiStreams']['Video']):
                    IndexMappingVideoEmby[str(VideoStream["Index"])] = IndexKodi
                    IndexMappingVideoKodi[IndexKodi] = str(VideoStream["Index"])

                for IndexKodi, AudioStream in enumerate(MediaSourceData['KodiStreams']['Audio']):
                    IndexMappingAudioEmby[str(AudioStream["Index"])] = IndexKodi
                    IndexMappingAudioKodi[IndexKodi] = str(AudioStream["Index"])

                for IndexKodi, SubtitleStream in enumerate(MediaSourceData['KodiStreams']['Subtitle']):
                    IndexMappingSubtitleEmby[str(SubtitleStream["Index"])] = IndexKodi
                    IndexMappingSubtitleKodi[IndexKodi] = str(SubtitleStream["Index"])

            QueuedPlayingItem = {
                "EmbySessionData": {
                    "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                    "CanSeek": not bool(KodiType == "channel"),
                    "IsPaused": False,
                    "ItemId": CachedItem['Id'],
                    "MediaSourceId": CachedItem['MediaSources'][0]["Id"],
                    "PlaySessionId": str(uuid.uuid4()).replace("-", ""),
                    "PositionTicks": 0,
                    "RunTimeTicks": 0,
                    "VolumeLevel": Volume,
                    "PlaybackRate": playerops.PlaybackRate[playerops.PlayerId],
                    "Shuffle": playerops.Shuffled[playerops.PlayerId],
                    "RepeatMode": playerops.RepeatMode[playerops.PlayerId],
                    "IsMuted": Muted
                },
                "IntroStartPositionTicks": CachedItem['MediaSources'][0].get("IntroStartPositionTicks", 0),
                "IntroEndPositionTicks": CachedItem['MediaSources'][0].get("IntroEndPositionTicks", 0),
                "CreditsPositionTicks": CachedItem['MediaSources'][0].get("CreditsPositionTicks", 0),
                "EmbyServer": utils.EmbyServers[CachedItem["ServerId"]],
                "KodiType": KodiType,
                "Filename": FullPath,
                "IndexMappingVideoEmby": IndexMappingVideoEmby,
                "IndexMappingVideoKodi": IndexMappingVideoKodi,
                "IndexMappingAudioEmby": IndexMappingAudioEmby,
                "IndexMappingAudioKodi": IndexMappingAudioKodi,
                "IndexMappingSubtitleEmby": IndexMappingSubtitleEmby,
                "IndexMappingSubtitleKodi": IndexMappingSubtitleKodi,
                "SubtitleEnabled": False,
                "SubtitleIndexKodi": 0
            }

        return CachedItem['Id'], isAddonContent, isDynamic, EmbyType, MediaSources, CachedItem

    # Native content not cached but has a KodiId
    # QueuedPlayingItem is not set at this point, needs to be updated
    if not isAddonContent and KodiId and not EmbyId:
        # KodiId available but no EmbyId. This is synced content played from Kodi's database. Try to load via KodiId from addon's database
        for ServerId, EmbyServer in list(utils.EmbyServers.items()):
            embydb = dbio.DBOpenRO(ServerId, "onAVStarted")
            EmbyId, EmbyType, IntroStartPosTicks, IntroEndPosTicks, CreditsStartPosTicks = embydb.get_nativemode_data_by_KodiId_KodiType(KodiId, KodiType)

            if not EmbyId:
                dbio.DBCloseRO(ServerId, "onAVStarted")
                xbmc.log("EMBY.helper.player: --< [ onAVStarted ] no item", 1) # LOGINFO
                continue

            MediaSourceId = embydb.get_mediasourceid_by_path(FullPath)
            _, EmbyType, MediaSources = embydb.get_metadata_by_EmbyId_EmbyType(EmbyId, EmbyType)
            dbio.DBCloseRO(ServerId, "onAVStarted")

            if not EmbyType or ServerId not in utils.EmbyServers:
                return 0, isAddonContent, isDynamic, "", [], {}

            KodiType = utils.EmbyTypeMapping[EmbyType]
            QueuedPlayingItem = {
                "EmbySessionData": {
                    "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                    "CanSeek": not bool(KodiType == "channel"),
                    "IsPaused": False,
                    "ItemId": EmbyId,
                    "MediaSourceId": MediaSourceId,
                    "PlaySessionId": str(uuid.uuid4()).replace("-", ""),
                    "PositionTicks": 0,
                    "RunTimeTicks": 0,
                    "VolumeLevel": Volume,
                    "PlaybackRate": playerops.PlaybackRate[playerops.PlayerId],
                    "Shuffle": playerops.Shuffled[playerops.PlayerId],
                    "RepeatMode": playerops.RepeatMode[playerops.PlayerId],
                    "IsMuted": Muted
                },
                "IntroStartPositionTicks": IntroStartPosTicks,
                "IntroEndPositionTicks": IntroEndPosTicks,
                "CreditsPositionTicks": CreditsStartPosTicks,
                "EmbyServer": EmbyServer,
                "KodiType": KodiType,
                "Filename": FullPath,
                "IndexMappingVideoEmby": MediaSources[0]['IndexMappingVideoEmby'],
                "IndexMappingVideoKodi": MediaSources[0]['IndexMappingVideoKodi'],
                "IndexMappingAudioEmby": MediaSources[0]['IndexMappingAudioEmby'],
                "IndexMappingAudioKodi": MediaSources[0]['IndexMappingAudioKodi'],
                "IndexMappingSubtitleEmby": MediaSources[0]['IndexMappingSubtitleEmby'],
                "IndexMappingSubtitleKodi": MediaSources[0]['IndexMappingSubtitleKodi'],
                "SubtitleEnabled": False,
                "SubtitleIndexKodi": 0
            }
            return EmbyId, isAddonContent, isDynamic, EmbyType, MediaSources, {}

        return 0, isAddonContent, isDynamic, "", [], {}

    return 0, isAddonContent, isDynamic, "", [], {}

def init_EmbyPlayback():
    if PlayingItem["EmbySessionData"]:
        RunTimeTicks = playerops.PlayBackDuration()
        PositionTicks = playerops.PlayBackPosition()
        if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): PlayingItem: {PlayingItem}", 1) # LOGDEBUG
        PlayingItem["EmbySessionData"].update({'RunTimeTicks': RunTimeTicks, 'PositionTicks': PositionTicks})

        if PlayingItem["EmbyServer"]:
            if not utils.RemoteMode:
                utils.ItemSkipUpdate.append(str(PlayingItem["EmbySessionData"]['ItemId'])) # Skip Emby progress updates as Kodi keeps track

            playerops.GetPlaylistPosition(playerops.PlayerId)
            PlaylistEmby[playerops.PlayerId] = PlayingItem["EmbyServer"].API.session_playing(PlayingItem["EmbySessionData"], PlaylistKodi[playerops.PlayerId], PlaylistEmby[playerops.PlayerId], playerops.PlaylistsPosition[playerops.PlayerId])
        else:
            xbmc.log(f"EMBY.helper.player: avstart error: {PlayingItem}", 3) # LOGERROR

        if utils.DebugLog: xbmc.log(f"EMBY.helper.player (DEBUG): ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGDEBUG
        playerops.AVStarted = True

        with utils.SafeLock(playerops.AVStartedCondition):
            playerops.AVStartedCondition.notify_all()

Ret = utils.SendJson("Player.GetProperties", '{"playerid": 0, "properties": ["repeat", "shuffled"]}', False).get('result', {})
playerops.RepeatMode[0] = parse_repeat(Ret.get("repeat", "off"))
playerops.Shuffled[0] = Ret.get("shuffled", False)
Ret = utils.SendJson("Player.GetProperties", '{"playerid": 1, "properties": ["repeat", "shuffled"]}', False).get('result', {})
playerops.RepeatMode[1] = parse_repeat(Ret.get("repeat", "off"))
playerops.Shuffled[1] = Ret.get("shuffled", False)
Ret = utils.SendJson("Player.GetProperties", '{"playerid": 2, "properties": ["repeat", "shuffled"]}', False).get('result', {})
playerops.RepeatMode[2] = parse_repeat(Ret.get("repeat", "off"))
playerops.Shuffled[2] = Ret.get("shuffled", False)
SkipIntroDialog.set_JumpFunction(jump_Intro)
SkipIntroDialogEmbuary.set_JumpFunction(jump_Intro)
SkipCreditsDialog.set_JumpFunction(jump_Credits)
utils.start_thread(PlayerCommands, ())
utils.start_thread(PositionTracker, ())
utils.start_thread(DeleteContent, ())

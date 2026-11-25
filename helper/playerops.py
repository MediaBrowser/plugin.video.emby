import threading
import xbmc
import xbmcvfs
import xbmcgui
from helper import utils, queue, cache
from database import dbio
from emby import listitem

PlayerId = -1
PlayerPause = False
RemoteClientData = {} # {"ServerId": {"SessionIds": [], "Usernames": {SessionId: UserName, ...}, "Devicenames": {SessionId: DeviceName, ...}, "ExtendedSupport": [], "ExtendedSupportAck": []}
RemoteCommandQueue = {}
RemoteControl = False
RemotePlaybackInit = False
EmbyIdPlaying = 0
WatchTogether = False
AVStarted = False
AVStart = False
AVChange = False
Stopped = True
AVStartedCondition = threading.Condition(threading.Lock())
AVChangeCondition = threading.Condition(threading.Lock())
StoppedCondition = threading.Condition(threading.Lock())
RemoteCommandActive = [0, 0, 0, 0, 0, 0, 0] # prevent loops when client has control [Pause, Unpause, Seek, Stop, Play, NextTrack, PreviousTrack]
XbmcPlayer = xbmc.Player() # Init Player
XbmcPlaylists = [xbmc.PlayList(0), xbmc.PlayList(1)] # Init Playlists
PlaylistsPosition = [-1, -1, -1]
PlaybackRate = [1.0, 1.0, 1.0]
RepeatMode = ['RepeatNone', 'RepeatNone', 'RepeatNone']
Shuffled = [False, False, False]
PauseLock = threading.Lock()
RemoteCommandActiveLock = threading.Lock()

def RemoteCommandActiveAdd(CommandId):
    with utils.SafeLock(RemoteCommandActiveLock):
        RemoteCommandActive[CommandId] += 1

def RemoteCommandActiveRelease(CommandId):
    with utils.SafeLock(RemoteCommandActiveLock):
        if RemoteCommandActive[CommandId] > 0:
            RemoteCommandActive[CommandId] -= 1

def RemoteCommandActiveConsume(CommandId):
    with utils.SafeLock(RemoteCommandActiveLock):
        if RemoteCommandActive[CommandId] > 0:
            RemoteCommandActive[CommandId] -= 1
            return False

        return True

def RemoteCommandActiveGet(CommandId):
    with utils.SafeLock(RemoteCommandActiveLock):
        return RemoteCommandActive[CommandId]

def RemoteCommandActiveReset():
    global RemoteCommandActive

    with utils.SafeLock(RemoteCommandActiveLock):
        RemoteCommandActive = [0, 0, 0, 0, 0, 0, 0]

def reload_PlaylistHandles(PlaylistId):
    XbmcPlaylists[PlaylistId] = xbmc.PlayList(PlaylistId)

def enable_remotemode(ServerId):
    global RemoteControl
    RemoteControl = True
    utils.RemoteMode = True
    send_RemoteClients(ServerId, [], True)

def GetTempo():
    if PlayerId != -1:
        Tempo = xbmc.getInfoLabel('Player.PlaySpeed')

        if Tempo:
            try:
                Tempo = float(Tempo)
            except:
                return 0

            if Tempo == 0.76:
                Tempo = 0.75

            return Tempo

    return 0

def SetSpeed(Speed):
    if PlayerId != -1: # Tempo accepct only ranges between 0.75 to 1.55
        if Speed < 0.75: # Not possible by Kodi
            return

        if Speed > 1.54:
            if Speed < 1.5:
                Speed = 1
            else:
                Speed = 2

            utils.SendJson("Player.SetSpeed", f'{{"playerid": {PlayerId}, "speed": {int(Speed)}}}', True) # fast forward
        else: # Try set Tempo
            Result = utils.SendJson("Settings.GetSettingValue", '{"setting": "videoplayer.usedisplayasclock"}', True)

            if Result:
                Result = Result.get("result", {})
                UseDisplayAsClock = Result.get("value", False)
            else:
                UseDisplayAsClock = False

            if not UseDisplayAsClock: # Tempo not supported when UseDisplayAsClock is disabled
                if Speed < 1.5:
                    Speed = 1
                else:
                    Speed = 2

                utils.SendJson("Player.SetSpeed", f'{{"playerid": {PlayerId}, "speed": {int(Speed)}}}', True) # fast forward
            else:
                if Speed == 0.75:
                    Speed = 0.76

                utils.SendJson("Player.SetSpeed", f'{{"playerid": {PlayerId}, "speed": 1}}', True) # fast forward
                utils.SendJson("Player.SetTempo", f'{{"playerid": {PlayerId}, "tempo": {float(Speed)}}}', True) # playback speed

def GetStreamInfo(IndexMappingSubtitleEmby, IndexMappingSubtitleKodi):
    if PlayerId != -1:
        Result = utils.SendJson("Player.GetProperties", f'{{"playerid": {PlayerId}, "properties": ["currentaudiostream", "subtitleenabled", "currentsubtitle", "subtitles"]}}', True)

        if Result:
            Result = Result.get("result", {})
        else:
            return -1, -1, False, {}, {}

        KodiSubtitles = Result.get("subtitles", [])

        # Sort: External subtitles always last
        if KodiSubtitles and len(IndexMappingSubtitleEmby) == len(KodiSubtitles):
            KodiSubtitlesIndexExternal = []
            KodiSubtitlesIndexInternal = []
            KodiSubtitlesIndex = []
            IndexMappingSubtitleEmbyKeyByIndex = []
            Valid = True

            for KodiSubtitle in KodiSubtitles:
                Name = KodiSubtitle.get("name", "")

                if 'index' not in KodiSubtitle:
                    Valid = False
                    break

                if "(External)" in Name:
                    KodiSubtitlesIndexExternal.append(KodiSubtitle['index'])
                else:
                    KodiSubtitlesIndexInternal.append(KodiSubtitle['index'])

            if Valid:
                KodiSubtitlesIndex = KodiSubtitlesIndexInternal + KodiSubtitlesIndexExternal

                for Key in IndexMappingSubtitleEmby:
                    IndexMappingSubtitleEmbyKeyByIndex.append(Key)

                for Index, KodiSubtitlsIndex in enumerate(KodiSubtitlesIndex):
                    Key = IndexMappingSubtitleEmbyKeyByIndex[Index]
                    IndexMappingSubtitleEmby[Key] = KodiSubtitlsIndex
                    IndexMappingSubtitleKodi[KodiSubtitlsIndex] = Key

        KodiSubtitleIndex = Result.get("currentsubtitle", -1)

        if KodiSubtitleIndex:
            if KodiSubtitleIndex != -1:
                KodiSubtitleIndex = KodiSubtitleIndex.get("index", -1)
        else:
            KodiSubtitleIndex = -1

        KodiAudioIndex = Result.get("currentaudiostream", -1)

        if KodiAudioIndex:
            if KodiAudioIndex != -1:
                KodiAudioIndex = KodiAudioIndex.get("index", -1)
        else:
            KodiAudioIndex = -1

        return KodiAudioIndex, KodiSubtitleIndex, Result.get("subtitleenabled", False), IndexMappingSubtitleEmby, IndexMappingSubtitleKodi

    return -1, -1, False, {}, {}

def InsertPlaylist(PlaylistId, Position, KodiType, KodiId):
    if PlaylistId != -1:
        utils.SendJson("Playlist.Insert", f'{{"playlistid": {PlaylistId}, "position": {Position}, "item": {{"{KodiType}id": {KodiId}}}}}', False)
        xbmc.log("EMBY.helper.playerops: [ InsertPlaylist ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: InsertPlaylist failed: PlaylistId={PlaylistId}", 3) # LOGERROR

def GetPlaylistItems(PlaylistId):
    if PlaylistId != -1:
        Result = utils.SendJson("Playlist.GetItems", f'{{"properties": ["file"], "playlistid": {PlaylistId}}}', True)

        if Result:
            Result = Result.get("result", {})

            if Result:
                return Result.get("items", [])

        xbmc.log(f"EMBY.helper.playerops: GetPlaylistItems failed: Result={Result}", 3) # LOGERROR
    else:
        xbmc.log(f"EMBY.helper.playerops: GetPlaylistItems failed: PlaylistId={PlaylistId}", 3) # LOGERROR

    return []

def GetPlaylistPosition(PlaylistId):
    if -1 < PlaylistId < 2:
        try:
            PlaylistsPosition[PlaylistId] = XbmcPlaylists[PlaylistId].getposition()
            if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): [ GetPlaylistPosition ] {PlaylistsPosition[PlaylistId]}", 1) # LOGINFO
            return PlaylistsPosition[PlaylistId]
        except:
            try:
                reload_PlaylistHandles(PlaylistId)
                PlaylistsPosition[PlaylistId] = XbmcPlaylists[PlaylistId].getposition()
                xbmc.log(f"EMBY.helper.playerops: [ GetPlaylistPosition ] reloaded, {PlaylistsPosition[PlaylistId]}", 1) # LOGINFO
                return PlaylistsPosition[PlaylistId]
            except:
                xbmc.log("EMBY.helper.playerops: [ GetPlaylistPosition ] failed", 3) # LOGERROR
                PlaylistsPosition[PlaylistId] = -1
                return -1
    elif PlaylistId == 2:
        Ret = utils.SendJson("Player.GetProperties", '{"playerid":2,"properties":["position", "playlistid"]}', False)
        PlaylistsPosition[PlaylistId] = int(Ret.get("result", {}).get("position", -1))
        return PlaylistsPosition[PlaylistId]

    return -1

def GetPlaylistSize(PlaylistId):
    if PlaylistId != -1:
        try:
            Size = XbmcPlaylists[PlaylistId].size()
            xbmc.log(f"EMBY.helper.playerops: [ GetPlaylistSize ] {Size}", 1) # LOGINFO
            return Size
        except:
            try:
                reload_PlaylistHandles(PlaylistId)
                Size = XbmcPlaylists[PlaylistId].size()
                xbmc.log(f"EMBY.helper.playerops: [ GetPlaylistSize ] reloaded, {Size}", 1) # LOGINFO
                return Size
            except:
                xbmc.log("EMBY.helper.playerops: [ GetPlaylistSize ] failed", 3) # LOGERROR
                return 0

    return 0

def PlayPlaylistItem(PlaylistId, Index):
    global PlayerId

    if PlaylistId != -1:
        utils.SendJson("Player.Open", f'{{"item":{{"playlistid":{PlaylistId},"position":{Index}}} ,"options": {{"resume": false}}}}', True)
        PlayerId = PlaylistId
    else:
        xbmc.log(f"EMBY.helper.playerops: PlayPlaylistItem failed: PlaylistId={PlaylistId}", 3) # LOGERROR

def GetPlayerFilepath():
    if XbmcPlayer.isPlaying():
        try:
            Filepath = XbmcPlayer.getPlayingFile()
            xbmc.log(f"EMBY.helper.playerops: [ GetPlayerFilepath ] {Filepath}", 1) # LOGINFO
            return Filepath
        except:
            pass

    xbmc.log("EMBY.helper.playerops: GetPlayerFilepath: No active player", 1) # LOGINFO
    return ""

def AddSubtitle(Path):
    SubtitleIndexAdded = -1
    Path = xbmcvfs.translatePath(Path)

    if not wait_AVStarted():
        return -1

    Ret = utils.SendJson("Player.GetProperties", '{"playerid":1,"properties":["subtitles"]}', False)
    SubtitleCount = len(Ret.get("result", {}).get("subtitles", []))
    utils.SendJson("Player.AddSubtitle", f'{{"playerid":1, "subtitle":"{Path}"}}', False)
    xbmc.log(f"EMBY.helper.playerops: [ AddSubtitle ] {Path}", 1) # LOGINFO

    # Wait for subtitle added
    for _ in range(50):
        Ret = utils.SendJson("Player.GetProperties", '{"playerid":1,"properties":["subtitles"]}', False)
        Subtitles = Ret.get("result", {}).get("subtitles", [])

        if len(Subtitles) > SubtitleCount:
            SubtitleIndexAdded = Subtitles[-1]["index"]
            break

        utils.sleep(0.1)

    return SubtitleIndexAdded

def SelectSubtitle(Index):
    if XbmcPlayer.isPlaying():
        try:
            XbmcPlayer.setSubtitleStream(Index)
            xbmc.log(f"EMBY.helper.playerops: [ SelectSubtitle ] {Index}", 1) # LOGINFO
        except:
            xbmc.log(f"EMBY.helper.playerops: [ SelectSubtitle ] failed {Index}", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: [ SelectSubtitle ] failed, not playing {Index}", 1) # LOGINFO

def EnableSubtitle(Enable):
    if XbmcPlayer.isPlaying():
        try:
            XbmcPlayer.showSubtitles(Enable)
            xbmc.log(f"EMBY.helper.playerops: [ EnableSubtitle ] {Enable}", 1) # LOGINFO
        except:
            xbmc.log(f"EMBY.helper.playerops: [ EnableSubtitle ] failed {Enable}", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: [ EnableSubtitle ] failed, not playing {Enable}", 1) # LOGINFO

def RemovePlaylistItem(PlaylistId, Index):
    if PlaylistId != -1:
        utils.SendJson("Playlist.Remove", f'{{"playlistid":{PlaylistId}, "position":{Index}}}', False)
        xbmc.log(f"EMBY.helper.playerops: [ RemovePlaylistItem ] PlaylistId={PlaylistId} Index: {Index}", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: RemovePlaylistItem failed: PlaylistId={PlaylistId}", 3) # LOGERROR

def Next():
    global PlayerPause
    global AVStarted

    if PlayerId == 2:
        RemoteCommandActiveAdd(5)
        xbmc.executebuiltin("Action(right)")
        xbmc.log("EMBY.helper.playerops: [ Next ], Picture", 1) # LOGINFO
    else:
        if XbmcPlayer.isPlaying():
            RemoteCommandActiveAdd(5)

            try:
                xbmc.executebuiltin("PlayerControl(Next)")
                xbmc.log("EMBY.helper.playerops: [ Next ]", 1)
                PlayerPause = False
                AVStarted = False
                return
            except:
                RemoteCommandActiveRelease(5)
                xbmc.log(f"EMBY.helper.playerops: Next failed: PlayerId={PlayerId}", 3) # LOGERROR
        else:
            xbmc.log(f"EMBY.helper.playerops: Next failed, not playing: PlayerId={PlayerId}", 3) # LOGERROR

def Previous():
    global PlayerPause
    global AVStarted

    if PlayerId == 2:
        RemoteCommandActiveAdd(6)
        xbmc.executebuiltin("Action(left)")
        xbmc.log("EMBY.helper.playerops: [ Previous ], Picture", 1) # LOGINFO
    else:
        if XbmcPlayer.isPlaying():
            RemoteCommandActiveAdd(6)

            try:
                xbmc.executebuiltin("PlayerControl(Previous)")
                xbmc.log("EMBY.helper.playerops: [ Previous ]", 1) # LOGINFO
                PlayerPause = False
                AVStarted = False
                return
            except:
                RemoteCommandActiveRelease(6)
                xbmc.log("EMBY.helper.playerops: Previous failed", 3) # LOGERROR
        else:
            xbmc.log("EMBY.helper.playerops: Previous failed, not playing", 3) # LOGERROR

def Stop(isRemote=False, Wait=False):
    global PlayerPause
    global AVStarted
    AVStarted = False
    PlayerPause = False

    if PlayerId == 2:
        PlayerPause = False

        if isRemote:
            RemoteCommandActiveAdd(3)

        xbmc.executebuiltin("Action(Stop)")
        xbmc.log("EMBY.helper.playerops: [ Stop ], Picture", 1) # LOGINFO
    else:
        if XbmcPlayer.isPlaying():
            if isRemote:
                RemoteCommandActiveAdd(3)

            PlayerPause = False
            xbmc.executebuiltin(f'PlayerControl(Stop, {PlayerId})')

            if Wait:
                while XbmcPlayer.isPlaying():
                    if utils.sleep(0.1):
                        break

            xbmc.log("EMBY.helper.playerops: [ Stop ]", 1) # LOGINFO
        else:
            xbmc.log("EMBY.helper.playerops: Stop: No active player", 1) # LOGINFO

def Play(isRemote, Path, ListItem, Windowed, WaitForPlayback):
    global PlayerPause
    global AVStarted
    AVStarted = False
    PlayerPause = False

    if isRemote:
        RemoteCommandActiveAdd(4)

    xbmc.log("EMBY.helper.playerops: [ Play ]", 1) # LOGINFO
    XbmcPlayer.play(Path, listitem=ListItem, windowed=Windowed)

    if WaitForPlayback:
        Timeout = 0

        # Wait for playback
        while not XbmcPlayer.isPlaying():
            utils.close_busyDialog(True)
            Timeout += 1

            if utils.sleep(0.1):
                if isRemote:
                    RemoteCommandActiveRelease(4)

                xbmc.log("EMBY.helper.playerops: [ Play ] shutdown", 3) # LOGERROR
                return False

            if Timeout > 100: # 10 seconds timeout
                if isRemote:
                    RemoteCommandActiveRelease(4)

                xbmc.log("EMBY.helper.playerops: [ Play ] timeout play", 3) # LOGERROR
                return False

        # Wait for full player init
        if not wait_AVStarted(True):
            if isRemote:
                RemoteCommandActiveRelease(4)

            xbmc.log("EMBY.helper.playerops: [ Play ] timeout avstart", 3) # LOGERROR
            return False

    return True

def UpdateInfoTag(ListItem):
    if XbmcPlayer.isPlaying():
        try:
            XbmcPlayer.updateInfoTag(ListItem)
            return True
        except:
            pass

    return False

def PauseToggle(isRemote=False):
    if PlayerPause:
        Unpause(isRemote)
    else:
        Pause(isRemote)

    xbmc.log("EMBY.helper.playerops: [ PauseToggle ]", 1) # LOGINFO

def Pause(isRemote=False, PositionTicks=0, TimeStamp=0, WaitForPlayback=False):
    global PlayerPause

    with utils.SafeLock(PauseLock):
        if not PlayerPause:
            if PlayerId == 2:
                if WaitForPlayback:
                    if not wait_AVStarted(False):
                        xbmc.log("EMBY.helper.playerops: Pause (forced) failed, player not playing", 3) # LOGERROR
                        return

                if isRemote:
                    RemoteCommandActiveAdd(0)

                xbmc.executebuiltin("Action(Pause)")
                PlayerPause = True
                xbmc.log("EMBY.helper.playerops: [ Pause ], Picture", 1) # LOGINFO
            else:
                if WaitForPlayback:
                    if not wait_AVStarted(False):
                        xbmc.log("EMBY.helper.playerops: Pause (forced) failed, player not playing", 3) # LOGERROR
                        return

                if XbmcPlayer.isPlaying():
                    if isRemote:
                        RemoteCommandActiveAdd(0)

                    xbmc.executebuiltin('PlayerControl(Play)')
                    PlayerPause = True
                    xbmc.log("EMBY.helper.playerops: [ Pause ]", 1) # LOGINFO

                    if TimeStamp:
                        Seek(PositionTicks, isRemote, TimeStamp)
                else:
                    xbmc.log("EMBY.helper.playerops: Pause failed, player not playing", 3) # LOGERROR
        else:
            xbmc.log(f"EMBY.helper.playerops: Pause failed: PlayerId={PlayerId} / PlayerPause={PlayerPause}", 3) # LOGERROR

def Unpause(isRemote=False):
    global PlayerPause

    with utils.SafeLock(PauseLock):
        if PlayerPause:
            if PlayerId == 2:
                if isRemote:
                    RemoteCommandActiveAdd(1)

                xbmc.executebuiltin("Action(Pause)")
                PlayerPause = False
                xbmc.log("EMBY.helper.playerops: [ Unpause ], Picture", 1) # LOGINFO
            else:
                if XbmcPlayer.isPlaying():
                    if isRemote:
                        RemoteCommandActiveAdd(1)

                    xbmc.executebuiltin('PlayerControl(Play)')
                    xbmc.log("EMBY.helper.playerops: [ Unpause ]", 1) # LOGINFO
                else:
                    xbmc.log("EMBY.helper.playerops: Unpause failed, player not playing", 3) # LOGERROR

                PlayerPause = False
        else:
            xbmc.log(f"EMBY.helper.playerops: Unpause failed: PlayerId={PlayerId} / PlayerPause={PlayerPause}", 3) # LOGERROR

def TicksToTimestamp(Ticks, TimeStamp):
    Ticks = float(Ticks)

    if TimeStamp:
        DeltaTime = (utils.get_unixtime_emby_format() - float(TimeStamp))
        xbmc.log(f"EMBY.helper.playerops: DeltaTime: {DeltaTime}ms", 1) # LOGINFO
        Ticks += DeltaTime

    return int((Ticks / 36000000000) % 24), int((Ticks / 600000000) % 60), int((Ticks / 10000000) % 60), int((Ticks / 10000) % 1000), round(Ticks)  # Hours / Minutes / Seconds / Milliseconds / Ticks

def Seek(SeekPositionTicksQuery, isRemote=False, TimeStamp=0, Relative=False):
    if PlayerId != -1:
        if not wait_AVStarted():
            xbmc.log(f"EMBY.helper.playerops: Seek: avstart not set: seek={SeekPositionTicksQuery}", 3)
            return

        if XbmcPlayer.isPlaying():
            WarningLogSend = False
            TargetTicks = float(SeekPositionTicksQuery)
            RemoteCounterAdded = False

            if TimeStamp:
                DeltaTicks = utils.get_unixtime_emby_format() - float(TimeStamp)
                xbmc.log(f"EMBY.helper.playerops: DeltaTime: {DeltaTicks}ms", 1)
                TargetTicks += DeltaTicks

            for _ in range(5):
                CurrentPositionTicks = PlayBackPosition()

                if CurrentPositionTicks == 0:
                    if RemoteCounterAdded:
                        RemoteCommandActiveRelease(2)

                    return

                if Relative:
                    FinalTicks = CurrentPositionTicks + TargetTicks
                else:
                    FinalTicks = TargetTicks

                Drift = (FinalTicks - CurrentPositionTicks) / 10000.0

                if -utils.remotecontrol_drift < Drift < utils.remotecontrol_drift:
                    xbmc.log(f"EMBY.helper.playerops: [ seek, allowed drift / Drift={Drift}]", 1)

                    if RemoteCounterAdded:
                        RemoteCommandActiveRelease(2)

                    return

                if isRemote and not RemoteCounterAdded:
                    RemoteCommandActiveAdd(2)
                    RemoteCounterAdded = True

                try:
                    XbmcPlayer.seekTime(FinalTicks / 10000000.0)
                    xbmc.log(f"EMBY.helper.playerops: Seek / FinalTicks: {int(FinalTicks)} / TimeStamp: {TimeStamp} / Drift: {Drift}", 1)
                    return

                except:
                    if not WarningLogSend:
                        xbmc.log("EMBY.helper.playerops: Seek failed, retrying...", 2)
                        WarningLogSend = True

                xbmc.sleep(100)

            if RemoteCounterAdded:
                RemoteCommandActiveRelease(2)

            xbmc.log(f"EMBY.helper.playerops: Seek not set: seek={TargetTicks}", 3)
    else:
        xbmc.log(f"EMBY.helper.playerops: Seek failed: PlayerId={PlayerId}", 3)

# wait for prezise progress information
def PlayBackPositionExact():
    PlaybackPositionCompare = 0
    PlaybackPosition = 0

    if XbmcPlayer.isPlaying():
        for _ in range(10): # timeout 2 seconds
            PlaybackPosition = PlayBackPosition()

            if PlayerPause:
                if PlaybackPositionCompare == PlaybackPosition:
                    return PlaybackPosition
            else:
                Delta = PlaybackPosition - PlaybackPositionCompare

                if PlaybackPosition and -7000000 < Delta < 7000000: # Allow 500ms delta
                    if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): Exact playback position found", 1) # LOGDEBUG
                    return PlaybackPosition

            if utils.sleep(0.2):
                return 0

            PlaybackPositionCompare = PlaybackPosition

        xbmc.log("EMBY.helper.playerops: Unable to detect exact playback position", 2) # LOGWARNING
        return PlaybackPosition

    return 0

def PlayBackPosition():
    if XbmcPlayer.isPlaying():
        try:
            return max(int(XbmcPlayer.getTime() * 10000000), 0)
        except:
            xbmc.log("EMBY.helper.playerops: PlayBackPosition failed, player", 2) # LOGWARNING
            return 0

    if utils.DebugLog: xbmc.log("EMBY.helper.playerops: PlayBackPosition failed, player not playing", 2) # LOGWARNING
    return 0

def PlayBackDuration():
    if XbmcPlayer.isPlaying():
        try:
            return max(int(XbmcPlayer.getTotalTime() * 10000000), 0)
        except:
            xbmc.log("EMBY.helper.playerops: PlayBackDuration failed, player", 2) # LOGWARNING
            return 0

    xbmc.log("EMBY.helper.playerops: PlayBackDuration failed, player not playing", 2) # LOGWARNING
    return 0

def PlayEmby(isRemote, ItemIds, PlayCommand, StartIndex, StartPositionTicks, ServerData, API, TimeStamp):
    global WatchTogether
    global RemotePlaybackInit
    global RemoteControl
    global EmbyIdPlaying
    global PlayerId
    global AVStarted
    global PlayerPause

    if not ItemIds:
        xbmc.log("EMBY.helper.playerops: PlayEmby, no ItemIds received", 2) # LOGWARNING
        return

    WatchTogether = False
    RemotePlaybackInit = True
    RemoteControl = utils.remotecontrol_client_control
    utils.RemoteMode = False
    StartIndex = max(StartIndex, 0)
    hasVideo = False
    hasAudio = False
    hasPicture = False

    # Check if content is synced and load item data
    embydb = dbio.DBOpenRO(ServerData['ServerId'], "AddPlaylistItem")
    LoadFromServer = False
    PlaylistItems = len(ItemIds) * [None] # pre allocate memory

    for Index, EmbyID in enumerate(ItemIds):
        KodiId, KodiType = embydb.get_KodiId_by_EmbyId(EmbyID)

        if KodiId: # synced content
            if KodiType == "song": # pictures are not synced to kodi, cannot be local
                hasAudio = True
            else:
                hasVideo = True

            PlaylistItems[Index] = [EmbyID, utils.KodiTypeMapping[KodiType], KodiType, KodiId, None, None, None]
        else: # not synced content
            PlaylistItems[Index] = [EmbyID, None, None, None, None, None, None]
            LoadFromServer = True

    dbio.DBCloseRO(ServerData['ServerId'], "AddPlaylistItem")

    # Load Additional data from server check content
    if LoadFromServer:
        Items = len(ItemIds) * [None] # pre allocate memory
        ItemIdsString = [str(ItemId) for ItemId in ItemIds] # Convert Emby Id (integer) to string values

        for Index, Item in enumerate(API.get_Items_Ids(ItemIdsString, ["All"], True, False, "", "", {}, None, False)): # Use "All" to disable sorting by API
            if not Item: # skip empty or synced content item
                continue

            if Item["Type"] == "Audio":
                hasAudio = True
            elif Item["Type"] == "Photo":
                hasPicture = True
            else:
                hasVideo = True

            Items[Index] = Item

    # Select player
    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): PlayEmby: hasAudio: {hasAudio} / hasPicture: {hasPicture} / hasVideo: {hasVideo}", 1) # LOGDEBUG
    EmbyIdPlaying = int(PlaylistItems[StartIndex][0])

    if hasPicture:
        PlayerIdPlaylistId = 2
        PlayerId = 2
        KodiPlaylistIndexStartitem = 0
        xbmc.executebuiltin('Action(Stop)') # Stop everything including slideshow
        utils.SendJson("Playlist.Clear", '{"playlistid": 2}', False)
        PlaylistsPosition[2] = -1
    elif hasVideo:
        PlayerIdPlaylistId = 1
        PlayerId = 1
    else:
        PlayerIdPlaylistId = 0
        PlayerId = 0

    # Load StartIndex item
    if not PlaylistItems[StartIndex][1]: # Load data for unsynced content or picture playlist
        PlaylistItems[StartIndex] = load_Remoteitems(Items[StartIndex], PlaylistItems[StartIndex], ServerData['ServerId'])

    # Prepare music/video playlist for StartIndex item and start playback
    if PlayerIdPlaylistId != 2: # Audio or video
        if PlayCommand in ("PlayNow", "PlayNext"):
            KodiPlaylistIndexStartitem = GetPlaylistPosition(PlayerIdPlaylistId) + 1
        elif PlayCommand == "PlayInit":
            utils.RemoteMode = True
            WatchTogether = True
            KodiPlaylistIndexStartitem = GetPlaylistSize(PlayerIdPlaylistId)
        elif PlayCommand == "PlaySingle":
            utils.RemoteMode = True
            KodiPlaylistIndexStartitem = GetPlaylistSize(PlayerIdPlaylistId)
        elif PlayCommand == "PlayLast":
            utils.RemoteMode = True
            KodiPlaylistIndexStartitem = GetPlaylistSize(PlayerIdPlaylistId)
        else:
            RemotePlaybackInit = False
            return

        if PlaylistItems[StartIndex][2]: # synced item (KodiType available)
            InsertPlaylist(PlayerIdPlaylistId, KodiPlaylistIndexStartitem, PlaylistItems[StartIndex][2], PlaylistItems[StartIndex][3])
        else:
            XbmcPlaylists[PlayerIdPlaylistId].add(PlaylistItems[StartIndex][5], PlaylistItems[StartIndex][4], index=KodiPlaylistIndexStartitem) # Path, ListItem, Index

        if PlayCommand in ("PlayLast", "PlayNext"):
            RemotePlaybackInit = False
            return

        RemotePlaybackInit = False

        # Start playback
        if isRemote:
            RemoteCommandActiveAdd(4)

        AVStarted = False
        PlayerPause = False

        with utils.SafeLock(AVStartedCondition):
            AVStartedCondition.notify_all()

        StartPositionTicks = int(StartPositionTicks)

        if PlaylistItems[StartIndex][2]: # KodiType
            if PlayCommand == "PlayInit":
                utils.SendJson("Player.Open", f'{{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": false}}}}', False)
            else:
                if StartPositionTicks != -1:
                    Hours, Minutes, Seconds, Milliseconds, _ = TicksToTimestamp(StartPositionTicks, TimeStamp)
                    utils.SendJson("Player.Open", f'{{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": {{"hours": {Hours}, "minutes": {Minutes}, "seconds": {Seconds}, "milliseconds": {Milliseconds}}}}}}}', False)
                else:
                    utils.SendJson("Player.Open", f'{{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": true}}}}', False)
        else:
            PlayPlaylistItem(PlayerIdPlaylistId, KodiPlaylistIndexStartitem)

            if PlayCommand != "PlayInit":
                if StartPositionTicks != -1:
                    Seek(StartPositionTicks, True, TimeStamp) # Resumeposition not respected by Kodi if "Player.Open" adresses a playlist/playlist position. Use seek as workaround
                else:
                    Seek(PlaylistItems[StartIndex][6], True, TimeStamp) # Resumeposition not respected by Kodi if "Player.Open" adresses a playlist/playlist position. Use seek as workaround

        if PlayCommand == "PlayInit":
            Pause(False, 0, 0, True)

        WindowId = xbmcgui.getCurrentWindowId()

        if PlayerIdPlaylistId == 0 and WindowId != 12006:
            utils.ActivateWindow("visualisation", "", False, 0)
        elif PlayerIdPlaylistId == 1 and WindowId != 12005:
            utils.ActivateWindow("fullscreenvideo", "", False, 0)

    # Load Additional data from server
    if LoadFromServer:
        for Index, Item in enumerate(Items):
            if not Item:
                continue

            InsertPosition = KodiPlaylistIndexStartitem + Index

            if PlayerIdPlaylistId != 2:
                if Index == StartIndex:
                    continue

                PlaylistItems[Index] = load_Remoteitems(Item, PlaylistItems[Index], ServerData['ServerId'])

                if PlaylistItems[Index][2]: # synced item
                    InsertPlaylist(PlayerIdPlaylistId, InsertPosition, PlaylistItems[Index][2], PlaylistItems[Index][3])
                else:
                    XbmcPlaylists[PlayerIdPlaylistId].add(PlaylistItems[Index][5], PlaylistItems[Index][4], index=InsertPosition) # Path, ListItem, Index
            else:
                PlaylistItems[Index] = load_Remoteitems(Item, PlaylistItems[Index], ServerData['ServerId'])
                utils.SendJson("Playlist.Add", f'{{"playlistid":2,"item":{{"file":"{PlaylistItems[Index][5]}"}}}}', False)

        del Items

    if PlayerIdPlaylistId == 2: # picture
        RemotePlaybackInit = False

        if isRemote:
            RemoteCommandActiveAdd(4)

        utils.SendJson("Player.Open", f'{{"item": {{"playlistid": 2, "position": {StartIndex}}}}}', False)

def load_Remoteitems(Item, PlaylistItem, ServerId):
    listitem.set_ListItem(Item, ServerId)

    if PlaylistItem[1]: # Kodi content
        PlaylistItem[4] = Item['ListItem']
        PlaylistItem[5] = Item['KodiFullPath']
    else:
        if "UserData" in Item and "PlaybackPositionTicks" in Item["UserData"] and Item["UserData"]["PlaybackPositionTicks"]:
            PlaylistItem = [Item['Id'], Item['Type'], None, None, Item['ListItem'], Item['KodiFullPath'], Item["UserData"]["PlaybackPositionTicks"]]
        else:
            PlaylistItem = [Item['Id'], Item['Type'], None, None, Item['ListItem'], Item['KodiFullPath'], 0]

        cache.add_Item(Item, ServerId)

    return PlaylistItem

def add_RemoteClient(ServerId, SessionId, DeviceName, UserName):
    if SessionId not in RemoteClientData[ServerId]["SessionIds"]:
        RemoteClientData[ServerId]["SessionIds"].append(SessionId)
        RemoteClientData[ServerId]["Usernames"][SessionId] = UserName
        RemoteClientData[ServerId]["Devicenames"][SessionId] = DeviceName

        if utils.EmbyServers[ServerId].EmbySession[0]['Id'] != SessionId:
            RemoteCommandQueue[SessionId] = queue.Queue()
            utils.start_thread(thread_RemoteCommands, (ServerId, SessionId, RemoteCommandQueue[SessionId]))

def add_RemoteClientExtendedSupport(ServerId, SessionId):
    if SessionId not in RemoteClientData[ServerId]["ExtendedSupport"]:
        RemoteClientData[ServerId]["ExtendedSupport"].append(SessionId)

def add_RemoteClientExtendedSupportAck(ServerId, SessionId, DeviceName, UserName):
    if SessionId not in RemoteClientData[ServerId]["ExtendedSupportAck"]:
        add_RemoteClient(ServerId, SessionId, DeviceName, UserName)
        RemoteClientData[ServerId]["ExtendedSupportAck"].append(SessionId)
        send_RemoteClients(ServerId, RemoteClientData[ServerId]["ExtendedSupportAck"], False)

def init_RemoteClient(ServerId):
    if ServerId in utils.EmbyServers and utils.EmbyServers[ServerId].EmbySession:
        RemoteClientData[ServerId] = {"SessionIds": [utils.EmbyServers[ServerId].EmbySession[0]['Id']], "Usernames": {utils.EmbyServers[ServerId].EmbySession[0]['Id']: utils.EmbyServers[ServerId].EmbySession[0]['UserName']}, "Devicenames": {utils.EmbyServers[ServerId].EmbySession[0]['Id']: utils.EmbyServers[ServerId].EmbySession[0]['DeviceName']}, "ExtendedSupport": [utils.EmbyServers[ServerId].EmbySession[0]['Id']], "ExtendedSupportAck": [utils.EmbyServers[ServerId].EmbySession[0]['Id']]}

def delete_RemoteClient(ServerId, SessionIds, Priority):
    if ServerId not in RemoteClientData:
        xbmc.log(f"EMBY.helper.playerops: ServerId {ServerId} not found in RemoteClientData", 2) # LOGWARNING
        return

    ClientExtendedSupportAck = RemoteClientData[ServerId]["ExtendedSupportAck"].copy()
    SelfRemove = False

    for SessionId in SessionIds:
        if SessionId in RemoteClientData[ServerId]["ExtendedSupport"]:
            RemoteClientData[ServerId]["ExtendedSupport"].remove(SessionId)

        if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
            RemoteClientData[ServerId]["ExtendedSupportAck"].remove(SessionId)

        if SessionId in RemoteClientData[ServerId]["SessionIds"]:
            RemoteClientData[ServerId]["SessionIds"].remove(SessionId)
        else:
            xbmc.log(f"EMBY.helper.playerops: SessionId {SessionId} not found in RemoteClientData", 2) # LOGWARNING
            continue

        del RemoteClientData[ServerId]["Usernames"][SessionId]
        del RemoteClientData[ServerId]["Devicenames"][SessionId]

        if SessionId in RemoteCommandQueue:
            RemoteCommandQueue[SessionId].put("QUIT")

        if SessionId == utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            SelfRemove = True

    send_RemoteClients(ServerId, ClientExtendedSupportAck, Priority)

    # Remove self
    if SelfRemove:
        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): Self removed from remote clients ]", 1) # LOGDEBUG
        disable_RemoteClients(ServerId, False)

    # Disable remote mode when self device is the only one left
    if len(RemoteClientData[ServerId]["SessionIds"]) == 1 and RemoteClientData[ServerId]["SessionIds"][0] == utils.EmbyServers[ServerId].EmbySession[0]['Id']:
        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): Reset remote clients due to no more participants ]", 1) # LOGDEBUG
        disable_RemoteClients(ServerId)

def update_Remoteclients(ServerId, Data):
    global RemoteControl
    ServerSessionId = utils.EmbyServers[ServerId].EmbySession[0]['Id']
    SessionIds = Data[1].split(";")
    ExtendedSupport = Data[2].split(";")
    ExtendedSupportAck = Data[3].split(";")
    Usernames = Data[4].split(";")
    Devicenames = Data[5].split(";")

    # Stop old threads
    for RemoteQueue in list(RemoteCommandQueue.values()):
        RemoteQueue.put(("QUIT",))

    # Stop new threads
    for SessionId in SessionIds:
        if SessionId == ServerSessionId:
            continue

        RemoteCommandQueue[SessionId] = queue.Queue()
        utils.start_thread(thread_RemoteCommands, (ServerId, SessionId, RemoteCommandQueue[SessionId]))

    if ServerSessionId not in SessionIds:
        xbmc.log("EMBY.helper.playerops: delete remote clients", 1) # LOGINFO
        disable_RemoteClients(ServerId, False)
    else:
        RemoteClientData[ServerId] = {"SessionIds": SessionIds, "ExtendedSupport": ExtendedSupport, "ExtendedSupportAck": ExtendedSupportAck, "Usernames": {}, "Devicenames": {}}

        for Index, SessionId in enumerate(SessionIds):
            RemoteClientData[ServerId]["Usernames"][SessionId] = Usernames[Index]
            RemoteClientData[ServerId]["Devicenames"][SessionId] = Devicenames[Index]

        # Disable remote mode when self device is the only one left
        if len(RemoteClientData[ServerId]["SessionIds"]) == 1 and RemoteClientData[ServerId]["SessionIds"][0] == ServerSessionId:
            disable_RemoteClients(ServerId)
        else:
            xbmc.executebuiltin('SetProperty(EmbyRemoteclient,True,10000)')

            if utils.remotecontrol_sync_clients:
                RemoteControl = True

            utils.RemoteMode = True

def disable_RemoteClients(ServerId, ResetRemoteClients=True):
    global RemoteControl
    global WatchTogether
    xbmc.executebuiltin('SetProperty(EmbyRemoteclient,False,10000)')

    if utils.RemoteMode:
        if ResetRemoteClients:
            for SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                if SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
                    utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", "clients|||||", True)

        init_RemoteClient(ServerId)
        RemoteControl = False
        WatchTogether = False
        RemoteCommandActiveReset()
        utils.RemoteMode = False

        if not utils.EmbyServers[ServerId].library.LockKodiStartSync.locked():
            utils.start_thread(utils.EmbyServers[ServerId].library.KodiStartSync, (False,))

def send_RemoteClients(ServerId, SendSessionIds, Priority):
    if not utils.remotecontrol_sync_clients:
        return

    if not SendSessionIds:
        SendSessionIds = RemoteClientData[ServerId]["ExtendedSupportAck"]

    ClientSessionIds = ';'.join(RemoteClientData[ServerId]['SessionIds'])
    ClientExtendedSupport = ';'.join(RemoteClientData[ServerId]['ExtendedSupport'])
    ClientExtendedSupportAck = ';'.join(RemoteClientData[ServerId]['ExtendedSupportAck'])
    ClientUsernames = []
    ClientDevicenames = []

    for SessionId in RemoteClientData[ServerId]["SessionIds"]:
        ClientUsernames.append(RemoteClientData[ServerId]["Usernames"][SessionId])
        ClientDevicenames.append(RemoteClientData[ServerId]["Devicenames"][SessionId])

    ClientUsernames = ';'.join(ClientUsernames)
    ClientDevicenames = ';'.join(ClientDevicenames)
    Data = f"clients|{ClientSessionIds}|{ClientExtendedSupport}|{ClientExtendedSupportAck}|{ClientUsernames}|{ClientDevicenames}"

    for SessionId in SendSessionIds:
        if SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", Data, Priority)

# Remote control clients
def RemoteCommand(ServerId, selfSessionId, Command, EmbyId=-1, PlaylistPosition=-1):
    global WatchTogether
    global RemoteControl

    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): --> [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGDEBUG

    if Command == "stop":
        if WatchTogether:
            if ServerId:
                delete_RemoteClient(ServerId, [utils.EmbyServers[ServerId].EmbySession[0]['Id']], True)

            WatchTogether = False
            RemoteControl = False
            utils.RemoteMode = False

        if RemoteCommandActiveConsume(3) and not WatchTogether and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "stop")
    elif Command == "pause":
        if RemoteCommandActiveConsume(0) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "pause")
    elif Command == "unpause":
        if RemoteCommandActiveConsume(1) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "unpause")
    elif Command == "seek":
        if RemoteCommandActiveConsume(2) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "seek")
    elif Command == "play":
        if RemoteCommandActiveConsume(4) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, (("play", EmbyId, PlaylistPosition),))
    elif Command == "nexttrack":
        if RemoteCommandActiveConsume(5) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "nexttrack")
    elif Command == "previoustrack":
        if RemoteCommandActiveConsume(6) and ServerId:
            queue_RemoteCommand(ServerId, selfSessionId, "previoustrack")

    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): --< [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGDEBUG

def RemoteClientResync(ServerId, SessionId, LocalEmbyIdPlaying):
    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): THREAD: --->[ Remote client resync: {SessionId} ]", 1) # LOGDEBUG

    if utils.sleep(utils.remotecontrol_resync_time):
        if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): THREAD: ---<[ Remote client resync: {SessionId} ] shutdown", 1) # LOGDEBUG
        return

    if EmbyIdPlaying == LocalEmbyIdPlaying:
        xbmc.log(f"EMBY.helper.playerops: resync started {SessionId}", 1) # LOGINFO
        PositionTicks = PlayBackPosition()
        utils.EmbyServers[ServerId].API.send_seek(SessionId, PositionTicks, True)
    else:
        xbmc.log(f"EMBY.helper.playerops: resync skipped {SessionId}", 2) # LOGWARNING

    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): THREAD: ---<[ Remote client resync: {SessionId} ]", 1) # LOGDEBUG

def queue_RemoteCommand(ServerId, selfSessionId, Command):
    if ServerId in RemoteClientData:
        for SessionId in RemoteClientData[ServerId]["SessionIds"].copy():
            if SessionId != selfSessionId:
                RemoteQueue = RemoteCommandQueue.get(SessionId)

                if RemoteQueue:
                    RemoteQueue.put(Command)

def thread_RemoteCommands(ServerId, SessionId, RemoteQueue):
    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): THREAD: --->[ Remote command queue: {SessionId} ]", 1) # LOGDEBUG
    API = utils.EmbyServers[ServerId].API

    while True:
        Command = RemoteQueue.get()
        xbmc.log(f"EMBY.helper.playerops: Remote command: {Command} {SessionId}", 1) # LOGINFO

        if Command == "QUIT":
            xbmc.log(f"EMBY.helper.playerops: Remote command queue closed {SessionId}", 1) # LOGINFO
            break

        if not RemoteControl:
            xbmc.log(f"EMBY.helper.playerops: Remote command skip by disabled remote control: {Command} {SessionId}", 1) # LOGINFO
            continue

        if RemotePlaybackInit:
            xbmc.log(f"EMBY.helper.playerops: Remote command skip by playback init: {Command} {SessionId}", 1) # LOGINFO
            continue

        if Command == "stop":
            if not utils.SystemShutdown:
                API.send_stop(SessionId, True)
                xbmc.log(f"EMBY.helper.playerops: remotecommand send: stop {SessionId}", 1) # LOGINFO
        elif Command == "pause":
            PositionTicks = PlayBackPosition()
            Timestamp = utils.get_unixtime_emby_format()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                API.send_text_msg(SessionId, "remotecommand", f"pause|{PositionTicks}|{Timestamp}", True)
            else:
                API.send_pause(SessionId, True)
                RemoteQueue.put("seek")

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: pause {SessionId}", 1) # LOGINFO
        elif Command == "unpause":
            API.send_unpause(SessionId, True)
            xbmc.log(f"EMBY.helper.playerops: remotecommand send: unpause {SessionId}", 1) # LOGINFO
        elif Command == "seek":
            if not wait_AVChanged():
                xbmc.log(f"EMBY.helper.playerops: Seek: AVchange not set {SessionId}", 3) # LOGERROR
                continue

            TimeStamp = utils.get_unixtime_emby_format()
            PositionTicks = PlayBackPositionExact()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                API.send_text_msg(SessionId, "remotecommand", f"seek|{PositionTicks}|{TimeStamp}", True)
            else:
                API.send_seek(SessionId, PositionTicks, True)

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: seek {SessionId} {PositionTicks} {TimeStamp}", 1) # LOGINFO
        elif Command[0] == "play":
            if not wait_AVStarted():
                xbmc.log(f"EMBY.helper.playerops: Play: AVstart not set {SessionId}", 3) # LOGERROR
                continue

            TimeStamp = utils.get_unixtime_emby_format()
            PositionTicks = PlayBackPositionExact()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                if str(Command[1]).find(",") == -1:
                    API.send_text_msg(SessionId, "remotecommand", f"playsingle|{Command[1]}|{PositionTicks}|{TimeStamp}", True)
                else:
                    API.send_text_msg(SessionId, "remotecommand", f"playplaylist|{Command[1]}|{PositionTicks}|{TimeStamp}|{Command[2]}", True) # ItemIds, Position, Timestamp, Playlistposition
            else:
                API.send_play(SessionId, Command[1], "PlayNow", PositionTicks, True)

                if utils.remotecontrol_resync_clients:
                    utils.start_thread(RemoteClientResync, (ServerId, SessionId, EmbyIdPlaying))

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: play {SessionId} {Command[1]} {PositionTicks} {TimeStamp}", 1) # LOGINFO
        elif Command == "nexttrack":
            API.send_nexttrack(SessionId, True)
        elif Command == "previoustrack":
            API.send_previoustrack(SessionId, True)

    if utils.DebugLog: xbmc.log(f"EMBY.helper.playerops (DEBUG): THREAD: ---<[ Remote command queue: {SessionId} ]", 1) # LOGDEBUG

def get_EmbyTicks(KodiTimeStamp): # Position(ticks) in Emby format 1 tick = 10000ms
    return max(KodiTimeStamp['hours'] * 36000000000 + KodiTimeStamp['minutes'] * 600000000 + KodiTimeStamp['seconds'] * 10000000 + KodiTimeStamp['milliseconds'] * 10000, 0)

def wait_AVStarted(BusyDialogClose=False):
    Timeout = 100 # 10 seconds

    with utils.SafeLock(AVStartedCondition):
        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: --->[ AVStartedCondition ]", 1) # LOGDEBUG

        while not AVStarted:
            if Timeout <= 0:
                if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ AVStartedCondition ] timeout", 1) # LOGDEBUG
                xbmc.log("EMBY.helper.playerops: AVstart timeout", 3)
                return False

            if BusyDialogClose:
                utils.close_busyDialog(True)

            if AVStartedCondition.wait(timeout=0.1):
                pass

            Timeout -= 1

        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ AVStartedCondition ]", 1) # LOGDEBUG
        return True

def wait_AVChanged():
    Timeout = 100 # 10 seconds

    with utils.SafeLock(AVChangeCondition):
        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: --->[ AVChangeCondition ]", 1) # LOGDEBUG

        while not AVChange:
            if Timeout <= 0:
                if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ AVChangeCondition ] timeout", 1) # LOGDEBUG
                xbmc.log("EMBY.helper.playerops: AVchange timeout", 3)
                return False

            if AVChangeCondition.wait(timeout=0.1):
                pass

            Timeout -= 1

        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ AVChangeCondition ]", 1) # LOGDEBUG
        return True

def wait_Stopped():
    Timeout = 100 # 10 seconds

    with utils.SafeLock(StoppedCondition):
        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: --->[ StoppedCondition ]", 1) # LOGDEBUG

        while not Stopped:
            if Timeout <= 0:
                if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ StoppedCondition ] timeout", 1) # LOGDEBUG
                xbmc.log("EMBY.helper.playerops: Stopped timeout", 3)
                return False

            if StoppedCondition.wait(timeout=0.1):
                pass

            Timeout -= 1

        if utils.DebugLog: xbmc.log("EMBY.helper.playerops (DEBUG): CONDITION: ---<[ StoppedCondition ]", 1) # LOGDEBUG
        return True

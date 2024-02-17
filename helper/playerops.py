from _thread import start_new_thread
import xbmc
import xbmcgui
from helper import utils, queue
from database import dbio
from emby import listitem
from core import common

Pictures = []
PlayerId = -1
PlayerPause = False
RemoteClientData = {} # {"ServerId": {"SessionIds": [], "Usernames": {SessionId: UserName, ...}, "Devicenames": {SessionId: DeviceName, ...}, "ExtendedSupport": [], "ExtendedSupportAck": []}
RemoteCommandQueue = {}
RemoteControl = False
RemotePlaybackInit = False
EmbyIdPlaying = 0
RemoteMode = False
WatchTogether = False
AVStarted = False
AVChange = False
RemoteCommandActive = [0, 0, 0, 0, 0] # prevent loops when client has control [Pause, Unpause, Seek, Stop, Play]

def enable_remotemode(ServerId):
    globals()["RemoteControl"] = True
    globals()["RemoteMode"] = True
    send_RemoteClients(ServerId, [], True, False)

def ClearPlaylist(PlaylistId):
    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Playlist.Clear", "params": {{"playlistid": {PlaylistId}}}}}')
    xbmc.log("EMBY.helper.playerops: [ ClearPlaylist ]", 1) # LOGINFO

def InsertPlaylist(PlaylistId, Position, KodiType, KodiId):
    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Playlist.Insert", "params": {{"playlistid": {PlaylistId}, "position": {Position}, "item": {{"{KodiType}id": {KodiId}}}}}}}')
    xbmc.log("EMBY.helper.playerops: [ InsertPlaylist ]", 1) # LOGINFO

def GetPlayerInfo(PlayerIdLocal):
    Result = utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.GetProperties", "params":{{"playerid":{PlayerIdLocal},"properties": ["position", "time", "totaltime"]}}, "id": 1}}', True).get("result", {})

    if Result:
        xbmc.log("EMBY.helper.playerops: [ GetPlayerPosition ]", 1) # LOGINFO
        TimeStamp = Result.get("totaltime", {})
        Duration = 0

        if TimeStamp:
            Duration = (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000
            Duration = max(Duration, 0)

        TimeStamp = Result.get("time", {})
        PositionTicks = 0

        if TimeStamp:
            PositionTicks = (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000
            PositionTicks = max(PositionTicks, 0)

        return Result.get("position", -1), PositionTicks, Duration

    xbmc.log(f"EMBY.helper.playerops: GetPlayerInfo failed: Result={Result}", 3) # LOGERROR
    return -1, 0, 0

def GetPlayerPosition(PlayerIdLocal):
    Result = utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.GetProperties", "params":{{"playerid":{PlayerIdLocal},"properties": ["position"]}}, "id": 1}}', True)

    if Result:
        Result = Result.get("result", {})
        xbmc.log("EMBY.helper.playerops: [ GetPlayerPosition ]", 1) # LOGINFO
        return Result.get("position", -1)

    xbmc.log(f"EMBY.helper.playerops: GetPlayerPosition failed: Result={Result}", 3) # LOGERROR
    return -1

def GetPlaylistSize(PlaylistId):
    Result = utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Playlist.GetProperties", "params":{{"playlistid":{PlaylistId},"properties": ["size"]}}, "id": 1}}').get("result", {})

    if Result:
        xbmc.log("EMBY.helper.playerops: [ GetPlaylistSize ]", 1) # LOGINFO
        return Result.get("size", 0)

    xbmc.log(f"EMBY.helper.playerops: GetPlaylistSize failed: Result={Result}", 3) # LOGERROR
    return 0

def PlayPlaylistItem(PlaylistId, Index):
    utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.Open","params":{{"item":{{"playlistid":{PlaylistId},"position":{Index}}} ,"options": {{"resume": true}}   }},"id":1}}')
    globals()['PlayerId'] = PlaylistId

def AddSubtitle(Path):
    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.AddSubtitle", "params":{{"playerid": 1, "subtitle":"{Path}"}}, "id": 1}}')

def SetSubtitle(Enable):
    if Enable:
        utils.SendJson('{"jsonrpc":"2.0", "method":"Player.SetSubtitle", "params":{"playerid":1, "subtitle":"on"}, "id": 1}')
    else:
        utils.SendJson('{"jsonrpc":"2.0", "method":"Player.SetSubtitle", "params":{"playerid":1, "subtitle":"off"}, "id": 1}')

    xbmc.log(f"EMBY.helper.playerops: [ SetSubtitle ] {Enable}", 1) # LOGINFO

def RemovePlaylistItem(PlaylistId, Index):
    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{{"playlistid":{PlaylistId}, "position":{Index}}}}}')

def Next():
    if PlayerId != -1:
        utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.GoTo","params":{{"playerid":{PlayerId},"to":"next"}},"id":1}}')
        xbmc.log("EMBY.helper.playerops: [ Next ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: Next failed: PlayerId={PlayerId}", 3) # LOGERROR

    globals()['PlayerPause'] = False

def Previous():
    if PlayerId != -1:
        utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.GoTo","params":{{"playerid":{PlayerId},"to":"previous"}},"id":1}}')
        xbmc.log("EMBY.helper.playerops: [ Previous ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: Previous failed: PlayerId={PlayerId}", 3) # LOGERROR

    globals()['PlayerPause'] = False

def Stop(isRemote=False):
    if PlayerId != -1:
        if isRemote:
            globals()['RemoteCommandActive'][3] += 1

        utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.Stop","params":{{"playerid":{PlayerId}}},"id":1}}')
        xbmc.log("EMBY.helper.playerops: [ Stop ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: Stop failed: PlayerId={PlayerId}", 3) # LOGERROR

    globals()['PlayerPause'] = False

def PauseToggle(isRemote=False):
    if PlayerPause:
        Unpause(isRemote)
    else:
        Pause(isRemote)

    xbmc.log("EMBY.helper.playerops: [ PauseToggle ]", 1) # LOGINFO

def Pause(isRemote=False, PositionTicks=0, TimeStamp=0):
    if PlayerId != -1 and not PlayerPause:
        if isRemote:
            globals()['RemoteCommandActive'][0] += 1

        utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.PlayPause","params":{{"playerid":{PlayerId}}},"id":1}}')
        globals()['PlayerPause'] = True
        xbmc.log("EMBY.helper.playerops: [ Pause ]", 1) # LOGINFO

        if TimeStamp:
            Seek(PositionTicks, isRemote, TimeStamp)
    else:
        xbmc.log(f"EMBY.helper.playerops: Pause failed: PlayerId={PlayerId} / PlayerPause={PlayerPause}", 3) # LOGERROR

def Unpause(isRemote=False):
    if PlayerId != -1 and PlayerPause:
        if isRemote:
            globals()['RemoteCommandActive'][1] += 1

        utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.PlayPause","params":{{"playerid":{PlayerId}}},"id":1}}')
        globals()['PlayerPause'] = False
        xbmc.log("EMBY.helper.playerops: [ Unpause ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: Unpause failed: PlayerId={PlayerId} / PlayerPause={PlayerPause}", 3) # LOGERROR

def TicksToTimestamp(Ticks, TimeStamp):
    DeltaTime = 0
    Ticks = float(Ticks)

    if TimeStamp:
        DeltaTime = float(utils.unixtimeInMicroseconds() - float(TimeStamp)) * 10000000
        Ticks += DeltaTime

    TicksMilliseconds = int(Ticks / 10000)
    xbmc.log(f"EMBY.helper.playerops: Seek DeltaTime: {DeltaTime}", 1) # LOGINFO
    return int((TicksMilliseconds / 3600000) % 24), int((TicksMilliseconds / 60000) % 60), int((TicksMilliseconds / 1000) % 60), int(TicksMilliseconds % 1000), Ticks  # Hours / Minutes / Seconds / Milliseconds / Ticks

def Seek(SeekPositionTicksQuery, isRemote=False, TimeStamp=0, Relative=False):
    if PlayerId != -1:
        if not wait_AVStarted():
            xbmc.log(f"EMBY.helper.playerops: Seek: avstart not set: seek={SeekPositionTicksQuery}", 3) # LOGERROR
            return

        WarningLogSend = False
        SeekPositionTicks = SeekPositionTicksQuery

        for _ in range(5): # try 5 times
            CurrentPositionTicks = PlayBackPosition()

            if CurrentPositionTicks == -1:
                return

            if Relative:
                SeekPositionTicks = CurrentPositionTicks + SeekPositionTicksQuery

            Hours, Minutes, Seconds, Milliseconds, Ticks = TicksToTimestamp(SeekPositionTicks, TimeStamp)
            Drift = (Ticks - CurrentPositionTicks) / 10000 # in milliseconds

            if -utils.remotecontrol_drift < Drift < utils.remotecontrol_drift:
                xbmc.log(f"EMBY.helper.playerops: [ seek, allowed drift / Drift={Drift}]", 1) # LOGINFO
                return

            if isRemote:
                globals()['RemoteCommandActive'][2] += 1

            Result = utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.Seek","params":{{"playerid":{PlayerId},"value":{{"time":{{"hours":{Hours},"minutes":{Minutes},"seconds":{Seconds},"milliseconds": {Milliseconds}}}}}}},"id":1}}', True)

            if Result:
                xbmc.log(f"EMBY.helper.playerops: Seek / SeekPositionTicks: {Ticks} / TimeStamp :{TimeStamp} / Drift: {Drift}", 1) # LOGINFO
                return

            if not WarningLogSend:
                WarningLogSend = True
                xbmc.log("EMBY.helper.playerops: Seek not send, delay", 2) # LOGWARNING

            if utils.sleep(0.1):
                return

        xbmc.log(f"EMBY.helper.playerops: Seek not set: seek={SeekPositionTicks}", 3) # LOGERROR
    else:
        xbmc.log(f"EMBY.helper.playerops: Seek failed: PlayerId={PlayerId}", 3) # LOGERROR

# wait for prezise progress information
def PlayBackPositionExact():
    PlaybackPositionCompare = 0
    PlaybackPosition = 0

    for _ in range(10): # timeout 2 seconds
        PlaybackPosition = PlayBackPosition()

        if PlaybackPosition == -1:
            return 0

        if PlayerPause:
            if PlaybackPositionCompare == PlaybackPosition:
                return PlaybackPosition
        else:
            if PlaybackPosition - 7000000 < PlaybackPositionCompare and PlaybackPosition != PlaybackPositionCompare: # Allow 500ms delta
                xbmc.log("EMBY.helper.playerops: Exact playback position found", 2) # LOGWARNING
                return PlaybackPosition

        if utils.sleep(0.2):
            return 0

        PlaybackPositionCompare = PlaybackPosition

    xbmc.log("EMBY.helper.playerops: Unable to detect exact playback position", 2) # LOGWARNING
    return PlaybackPosition

def PlayBackPosition():
    Result = None

    if PlayerId != -1:
        Result = utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.GetProperties","params":{{"playerid":{PlayerId},"properties": ["time"]}},"id":1}}').get("result", {})

        if Result:
            TimeStamp = Result.get("time", {})

            if TimeStamp:
                PositionTicks = (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000
                return max(PositionTicks, 0)

        xbmc.log(f"EMBY.helper.playerops: PlayBackPosition failed: Result={Result}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.helper.playerops: PlayBackPosition failed: PlayerId={PlayerId}", 2) # LOGWARNING

    return -1

def PlayBackDuration():
    if PlayerId != -1:
        Result = utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.GetProperties","params":{{"playerid":{PlayerId},"properties": ["totaltime"]}},"id":1}}').get("result", {})

        if Result:
            TimeStamp = Result.get("totaltime", {})

            if TimeStamp:
                Duration = (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000
                return max(Duration, 0)

        xbmc.log(f"EMBY.helper.playerops: PlayBackDuration failed: Result={Result}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.helper.playerops: PlayBackDuration failed: PlayerId={PlayerId}", 2) # LOGWARNING

    return 0

def PlayEmby(ItemIds, PlayCommand, StartIndex, StartPositionTicks, EmbyServer, TimeStamp):
    if not ItemIds:
        xbmc.log("EMBY.helper.playerops: PlayEmby, no ItemIds received", 2) # LOGWARNING
        return

    if utils.remotecontrol_client_control:
        globals().update({"RemoteMode": False, "WatchTogether": False, "RemotePlaybackInit": True, "RemoteControl": True})
    else:
        globals().update({"RemoteMode": False, "WatchTogether": False, "RemotePlaybackInit": True, "RemoteControl": False})

    PlaylistItems = []
    DelayedQueryEmbyIds = ()
    StartIndex = max(StartIndex, 0)
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "AddPlaylistItem")

    for Index, EmbyID in enumerate(ItemIds):
        KodiId, KodiType = embydb.get_KodiId_by_EmbyId(EmbyID)

        if KodiId: # synced content
            PlaylistItems.append((EmbyID, None, KodiType, KodiId, None, None, None))
        else: # not synced content
            PlaylistItems.append((EmbyID, None, None, None, None, None, None))

            if Index != StartIndex:
                DelayedQueryEmbyIds += (str(EmbyID),)

    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "AddPlaylistItem")

    # Load not synced startitem
    if not PlaylistItems[StartIndex][2]: # dynamic item
        Item = EmbyServer.API.get_Item(ItemIds[StartIndex], ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video", "Photo"], True, False)

        if not Item:
            return

        ListItem = listitem.set_ListItem(Item, EmbyServer.ServerData['ServerId'])
        Path, ShortType = common.get_path_type_from_item(EmbyServer.ServerData['ServerId'], Item)

        if "UserData" in Item and "PlaybackPositionTicks" in Item["UserData"] and Item["UserData"]["PlaybackPositionTicks"]:
            PlaylistItems[StartIndex] = (Item['Id'], ShortType, None, None, ListItem, Path, Item["UserData"]["PlaybackPositionTicks"])
        else:
            PlaylistItems[StartIndex] = (Item['Id'], ShortType, None, None, ListItem, Path, 0)

    globals()["EmbyIdPlaying"] = int(PlaylistItems[StartIndex][0])

    if PlaylistItems[StartIndex][1] == "a" or PlaylistItems[StartIndex][2] == "song": # audio
        PlayerIdPlaylistId = 0
        globals()['PlayerId'] = 0
    elif PlaylistItems[StartIndex][1] == "p": # pictures
        PlayerIdPlaylistId = 2
    else: # video
        PlayerIdPlaylistId = 1
        globals()['PlayerId'] = 1

    if PlayCommand in ("PlayNow", "PlayNext"):
        KodiPlaylistIndexStartitem = GetPlayerPosition(PlayerIdPlaylistId) + 1
    elif PlayCommand == "PlayInit":
        globals()['RemoteMode'] = True
        globals()['WatchTogether'] = True
        Stop(True)
        KodiPlaylistIndexStartitem = GetPlaylistSize(PlayerIdPlaylistId)
    elif PlayCommand == "PlaySingle":
        globals()['RemoteMode'] = True
        KodiPlaylistIndexStartitem = GetPlaylistSize(PlayerIdPlaylistId)
    else:
        return

    if PlayerIdPlaylistId != 2: # Audio or video
        if PlaylistItems[StartIndex][2]: # synced item (KodiType available)
            InsertPlaylist(PlayerIdPlaylistId, KodiPlaylistIndexStartitem, PlaylistItems[StartIndex][2], PlaylistItems[StartIndex][3])
        else:
            utils.Playlists[PlayerIdPlaylistId].add(PlaylistItems[StartIndex][5], PlaylistItems[StartIndex][4], index=KodiPlaylistIndexStartitem) # Path, ListItem, Index
    else: # picture
        globals()["Pictures"].append((Path, ListItem))
        utils.SendJson(f'{{"jsonrpc":"2.0","id":1,"method":"Playlist.Add","params":{{"playlistid":2,"item":{{"file":"{Path}"}}}}}}')

    if PlayerIdPlaylistId == 2: # picture
        globals()["Pictures"][KodiPlaylistIndexStartitem][1].select(True)
        xbmc.executebuiltin('Action(Stop)')
        xbmc.executebuiltin('Action(Back)')
        ClearPlaylist(2)
    else:
        globals()['RemoteCommandActive'][4] += 1
        globals().update({"AVStarted": False, "PlayerPause": False})
        StartPositionTicks = int(StartPositionTicks)

        if PlaylistItems[StartIndex][2]: # KodiType
            if PlayCommand == "PlayInit":
                utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": false}}}}, "id": 1}}')
            else:
                if StartPositionTicks != -1:
                    Hours, Minutes, Seconds, Milliseconds, _ = TicksToTimestamp(StartPositionTicks, TimeStamp)
                    utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": {{"hours": {Hours}, "minutes": {Minutes}, "seconds": {Seconds}, "milliseconds": {Milliseconds}}}}}}}, "id": 1}}')
                else:
                    utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"{PlaylistItems[StartIndex][2]}id": {PlaylistItems[StartIndex][3]}}}, "options": {{"resume": true}}}}, "id": 1}}')
        else:
            utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"playlistid":{PlayerIdPlaylistId}, "position": {KodiPlaylistIndexStartitem}}}}}, "id": 1}}')

            if PlayCommand != "PlayInit":
                if StartPositionTicks != -1:
                    Seek(StartPositionTicks, True, TimeStamp) # Resumeposition not respected by Kodi if "Player.Open" adresses a playlist/playlist position. Use seek as workaround
                else:
                    Seek(PlaylistItems[StartIndex][6], True, TimeStamp) # Resumeposition not respected by Kodi if "Player.Open" adresses a playlist/playlist position. Use seek as workaround

        if PlayCommand == "PlayInit":
            Pause(True)

        WindowId = xbmcgui.getCurrentWindowId()

        if PlayerIdPlaylistId == 0 and WindowId != 12006:
            utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "visualisation"}}')
        elif PlayerIdPlaylistId == 1 and WindowId != 12005:
            utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "fullscreenvideo"}}')

    globals()['RemotePlaybackInit'] = False

    #load additional items after playback started
    if PlayCommand not in ("PlayInit", "PlaySingle"):
        if DelayedQueryEmbyIds:
            for Item in EmbyServer.API.get_Items_Ids(DelayedQueryEmbyIds, ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video", "Photo"], True, False, "", None):
                ListItem = listitem.set_ListItem(Item, EmbyServer.ServerData['ServerId'])
                Path, ShortType = common.get_path_type_from_item(EmbyServer.ServerData['ServerId'], Item)

                for Index, PlaylistItem in enumerate(PlaylistItems):
                    if str(Item['Id']) == str(PlaylistItem[0]):
                        if "UserData" in Item and "PlaybackPositionTicks" in Item["UserData"] and Item["UserData"]["PlaybackPositionTicks"]:
                            PlaylistItems[Index] = (Item['Id'], ShortType, None, None, ListItem, Path, Item["UserData"]["PlaybackPositionTicks"])
                        else:
                            PlaylistItems[Index] = (Item['Id'], ShortType, None, None, ListItem, Path, 0)

                        continue

        for Index, PlaylistItem in enumerate(PlaylistItems):
            if Index == StartIndex:
                continue

            InsertPosition = KodiPlaylistIndexStartitem + Index

            if PlayerIdPlaylistId != 2:
                if PlaylistItem[2]: # synced item
                    InsertPlaylist(PlayerIdPlaylistId, InsertPosition, PlaylistItem[2], PlaylistItem[3])
                else:
                    utils.Playlists[PlayerIdPlaylistId].add(PlaylistItem[5], PlaylistItem[4], index=InsertPosition) # Path, ListItem, Index
            else:
                Pictures.append((PlaylistItem[5], PlaylistItem[4]))

    if PlayerIdPlaylistId == 2: # picture
        utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "pictures", "parameters": ["plugin://plugin.video.emby-next-gen/?mode=remotepictures&position={KodiPlaylistIndexStartitem}", "return"]}}}}')

    for Index, Picture in enumerate(Pictures):
        if Index != 0:
            utils.SendJson(f'{{"jsonrpc":"2.0","id":1,"method":"Playlist.Add","params":{{"playlistid":2,"item":{{"file":"{Picture[0]}"}}}}}}')

def add_RemoteClient(ServerId, SessionId, DeviceName, UserName):
    if SessionId not in RemoteClientData[ServerId]["SessionIds"]:
        globals()['RemoteClientData'][ServerId]["SessionIds"].append(SessionId)
        globals()['RemoteClientData'][ServerId]["Usernames"][SessionId] = UserName
        globals()['RemoteClientData'][ServerId]["Devicenames"][SessionId] = DeviceName

        if utils.EmbyServers[ServerId].EmbySession[0]['Id'] != SessionId:
            globals()['RemoteCommandQueue'][SessionId] = queue.Queue()
            start_new_thread(thread_RemoteCommands, (ServerId, SessionId))

def add_RemoteClientExtendedSupport(ServerId, SessionId):
    if SessionId not in RemoteClientData[ServerId]["ExtendedSupport"]:
        globals()['RemoteClientData'][ServerId]["ExtendedSupport"].append(SessionId)

def add_RemoteClientExtendedSupportAck(ServerId, SessionId, DeviceName, UserName):
    if SessionId not in RemoteClientData[ServerId]["ExtendedSupportAck"]:
        add_RemoteClient(ServerId, SessionId, DeviceName, UserName)
        globals()['RemoteClientData'][ServerId]["ExtendedSupportAck"].append(SessionId)
        send_RemoteClients(ServerId, RemoteClientData[ServerId]["ExtendedSupportAck"], False, False)

def init_RemoteClient(ServerId):
    globals()['RemoteClientData'][ServerId] = {"SessionIds": [utils.EmbyServers[ServerId].EmbySession[0]['Id']], "Usernames": {utils.EmbyServers[ServerId].EmbySession[0]['Id']: utils.EmbyServers[ServerId].EmbySession[0]['UserName']}, "Devicenames": {utils.EmbyServers[ServerId].EmbySession[0]['Id']: utils.EmbyServers[ServerId].EmbySession[0]['DeviceName']}, "ExtendedSupport": [utils.EmbyServers[ServerId].EmbySession[0]['Id']], "ExtendedSupportAck": [utils.EmbyServers[ServerId].EmbySession[0]['Id']]}

def delete_RemoteClient(ServerId, SessionIds, Force=False, LastWill=False):
    if ServerId not in RemoteClientData:
        xbmc.log(f"EMBY.helper.playerops: ServerId {ServerId} not found in RemoteClientData", 2) # LOGWARNING
        return

    ClientExtendedSupportAck = RemoteClientData[ServerId]["ExtendedSupportAck"].copy()

    for SessionId in SessionIds:
        if SessionId in RemoteClientData[ServerId]["ExtendedSupport"]:
            globals()['RemoteClientData'][ServerId]["ExtendedSupport"].remove(SessionId)

        if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
            globals()['RemoteClientData'][ServerId]["ExtendedSupportAck"].remove(SessionId)

        globals()['RemoteClientData'][ServerId]["SessionIds"].remove(SessionId)
        del globals()['RemoteClientData'][ServerId]["Usernames"][SessionId]
        del globals()['RemoteClientData'][ServerId]["Devicenames"][SessionId]

        if SessionId in RemoteCommandQueue:
            globals()['RemoteCommandQueue'][SessionId].put("QUIT")

    send_RemoteClients(ServerId, ClientExtendedSupportAck, Force, LastWill)

    # Disable remote mode when self device is the only one left
    if len(RemoteClientData[ServerId]["SessionIds"]) == 1 and RemoteClientData[ServerId]["SessionIds"][0] == utils.EmbyServers[ServerId].EmbySession[0]['Id']:
        disable_RemoteClients(ServerId)

def update_Remoteclients(ServerId, Data):
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
        globals()['RemoteCommandQueue'][SessionId] = queue.Queue()
        start_new_thread(thread_RemoteCommands, (ServerId, SessionId))

    if ServerSessionId not in SessionIds:
        xbmc.log("EMBY.helper.playerops: delete remote clients", 1) # LOGINFO
        disable_RemoteClients(ServerId)
    else:
        globals()['RemoteClientData'][ServerId] = {"SessionIds": SessionIds, "ExtendedSupport": ExtendedSupport, "ExtendedSupportAck": ExtendedSupportAck, "Usernames": {}, "Devicenames": {}}

        for Index, SessionId in enumerate(SessionIds):
            globals()['RemoteClientData'][ServerId]["Usernames"][SessionId] = Usernames[Index]
            globals()['RemoteClientData'][ServerId]["Devicenames"][SessionId] = Devicenames[Index]

        # Disable remote mode when self device is the only one left
        if len(RemoteClientData[ServerId]["SessionIds"]) == 1 and RemoteClientData[ServerId]["SessionIds"][0] == ServerSessionId:
            disable_RemoteClients(ServerId)
        else:
            xbmcgui.Window(10000).setProperty('EmbyRemoteclient', 'True')

            if utils.remotecontrol_sync_clients:
                globals()["RemoteControl"] = True

            globals()["RemoteMode"] = True

def disable_RemoteClients(ServerId):
    xbmcgui.Window(10000).setProperty('EmbyRemoteclient', 'False')

    if RemoteMode:
        for SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
            if SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
                utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", "clients|||||", True, False)

        init_RemoteClient(ServerId)
        globals().update({"RemoteMode": False, "WatchTogether": False, "RemoteControl": False, "RemoteCommandActive": [0, 0, 0, 0, 0]})

        if not utils.EmbyServers[ServerId].library.KodiStartSyncRunning:
            start_new_thread(utils.EmbyServers[ServerId].library.KodiStartSync, (False,))

def send_RemoteClients(ServerId, SendSessionIds, Force, LastWill):
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
            utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", Data, Force, LastWill)

# Remote control clients
def RemoteCommand(ServerId, selfSessionId, Command, EmbyId=-1):
    xbmc.log(f"EMBY.helper.playerops: --> [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGINFO

    if Command == "stop":
        if RemoteCommandActive[3] > 0:
            RemoteCommandActive[3] -= 1

            if WatchTogether:
                disable_RemoteClients(ServerId)
                globals().update({'WatchTogether': False, 'RemoteMode': False, 'RemoteControl': False})
        else:
            globals()['RemoteCommandActive'][3] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "stop")
    elif Command == "pause":
        if RemoteCommandActive[0] > 0:
            RemoteCommandActive[0] -= 1
        else:
            globals()['RemoteCommandActive'][0] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "pause")
    elif Command == "unpause":
        if RemoteCommandActive[1] > 0:
            RemoteCommandActive[1] -= 1
        else:
            globals()['RemoteCommandActive'][1] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "unpause")
    elif Command == "seek":
        if RemoteCommandActive[2] > 0:
            RemoteCommandActive[2] -= 1
        else:
            globals()['RemoteCommandActive'][2] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "seek")
    elif Command == "play":
        if RemoteCommandActive[4] > 0:
            RemoteCommandActive[4] -= 1
        else:
            globals()['RemoteCommandActive'][4] = 0
            queue_RemoteCommand(ServerId, selfSessionId, (("play", EmbyId),))

    xbmc.log(f"EMBY.helper.playerops: --< [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGINFO

def RemoteClientResync(ServerId, SessionId, LocalEmbyIdPlaying):
    xbmc.log(f"EMBY.helper.playerops: THREAD: --->[ Remote client resync: {SessionId} ]", 0) # LOGDEBUG

    if utils.sleep(utils.remotecontrol_resync_time):
        xbmc.log(f"EMBY.helper.playerops: THREAD: ---<[ Remote client resync: {SessionId} ] shutdown", 0) # LOGDEBUG
        return

    if EmbyIdPlaying == LocalEmbyIdPlaying:
        xbmc.log(f"EMBY.helper.playerops: resync started {SessionId}", 1) # LOGINFO
        PositionTicks = PlayBackPosition()

        if PositionTicks != -1:
            utils.EmbyServers[ServerId].API.send_seek(SessionId, PositionTicks, True)
    else:
        xbmc.log(f"EMBY.helper.playerops: resync skipped {SessionId}", 2) # LOGWARNING

    xbmc.log(f"EMBY.helper.playerops: THREAD: ---<[ Remote client resync: {SessionId} ]", 0) # LOGDEBUG

def queue_RemoteCommand(ServerId, selfSessionId, Command):
    for SessionId in RemoteClientData[ServerId]["SessionIds"]:
        if SessionId != selfSessionId:
            globals()['RemoteCommandQueue'][SessionId].put(Command)

def thread_RemoteCommands(ServerId, SessionId):
    xbmc.log(f"EMBY.helper.playerops: THREAD: --->[ Remote command queue: {SessionId} ]", 0) # LOGDEBUG
    API = utils.EmbyServers[ServerId].API

    while True:
        Command = globals()['RemoteCommandQueue'][SessionId].get()
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

            if PositionTicks == -1:
                continue

            Timestamp = utils.unixtimeInMicroseconds()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                API.send_text_msg(SessionId, "remotecommand", f"pause|{PositionTicks}|{Timestamp}", True)
            else:
                API.send_pause(SessionId, True)
                globals()['RemoteCommandQueue'][SessionId].put("seek")

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: pause {SessionId}", 1) # LOGINFO
        elif Command == "unpause":
            API.send_unpause(SessionId, True)
            xbmc.log(f"EMBY.helper.playerops: remotecommand send: unpause {SessionId}", 1) # LOGINFO
        elif Command == "seek":
            if not wait_AVChanged():
                xbmc.log(f"EMBY.helper.playerops: Seek: AVchange not set {SessionId}", 3) # LOGERROR
                continue

            TimeStamp = utils.unixtimeInMicroseconds()
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

            TimeStamp = utils.unixtimeInMicroseconds()
            PositionTicks = PlayBackPositionExact()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                API.send_text_msg(SessionId, "remotecommand", f"playsingle|{Command[1]}|{PositionTicks}|{TimeStamp}", True)
            else:
                API.send_play(SessionId, Command[1], "PlayNow", PlayBackPositionExact(), True)

                if utils.remotecontrol_resync_clients:
                    start_new_thread(RemoteClientResync, (ServerId, SessionId, EmbyIdPlaying))

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: play {SessionId} {Command[1]} {PositionTicks} {TimeStamp}", 1) # LOGINFO

    xbmc.log(f"EMBY.helper.playerops: THREAD: ---<[ Remote command queue: {SessionId} ]", 0) # LOGDEBUG

def wait_AVStarted():
    for _ in range(200): # Wait for avstart, timeout 20 seconds
        if AVStarted:
            return True

        if utils.sleep(0.1):
            return False

    xbmc.log("EMBY.helper.playerops: AVstart not set", 3) # LOGERROR
    return False

def wait_AVChanged():
    for _ in range(200): # Wait for avstart, timeout 20 seconds
        if AVChange:
            return True

        if utils.sleep(0.1):
            return False

    xbmc.log("EMBY.helper.playerops: AVchange not set", 3) # LOGERROR
    return False

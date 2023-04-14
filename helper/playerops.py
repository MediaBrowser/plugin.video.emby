from _thread import start_new_thread
import queue
import xbmc
from helper import utils
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
ItemSkipUpdate = []
AVStarted = False
AVChange = False
RemoteCommandActive = [0, 0, 0, 0, 0] # prevent loops when client has control [Pause, Unpause, Seek, Stop, Play]
# https://github.com/xbmc/xbmc/blob/master/xbmc/interfaces/json-rpc/schema/methods.json

def ClearPlaylist(PlaylistId):
    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Playlist.Clear", "params": {{"playlistid": {PlaylistId}}}}}')
    xbmc.log("EMBY.helper.playerops: [ ClearPlaylist ]", 1) # LOGINFO

def InsertPlaylist(PlaylistId, Position, KodiType, KodiId):
    utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "Playlist.Insert", "params": {{"playlistid": {PlaylistId}, "position": {Position}, "item": {{"{KodiType}id": {KodiId}}}}}}}')
    xbmc.log("EMBY.helper.playerops: [ InsertPlaylist ]", 1) # LOGINFO

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
    utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.Open","params":{{"item":{{"playlistid":{PlaylistId},"position":{Index}}}}},"id":1}}')
    globals()['PlayerId'] = PlaylistId

def GetFilenameandpath():
    Result = None

    if PlayerId != -1:
        Result = utils.SendJson('{"jsonrpc": "2.0", "method": "xbmc.GetInfoLabels", "params":{"labels": ["player.Filenameandpath"]}, "id": 1}').get("result", {})

        if Result:
            xbmc.log("EMBY.helper.playerops: [ GetFilenameandpath ]", 1) # LOGINFO
            return Result.get("player.Filenameandpath", "")

    xbmc.log(f"EMBY.helper.playerops: GetFilenameandpath failed: PlayerId={PlayerId} / Result={Result}", 3) # LOGERROR
    return ""

def AddSubtitle(Path):
    if PlayerId != -1:
        utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.AddSubtitle", "params":{{"playerid":{PlayerId}, "subtitle":"{Path}"}}, "id": 1}}')
    else:
        xbmc.log(f"EMBY.helper.playerops: AddSubtitle failed: PlayerId={PlayerId}", 3) # LOGERROR

def SetSubtitle(Enable):
    if PlayerId != -1:
        if Enable:
            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.SetSubtitle", "params":{{"playerid":{PlayerId}, "subtitle":"on"}}, "id": 1}}')
        else:
            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.SetSubtitle", "params":{{"playerid":{PlayerId}, "subtitle":"off"}}, "id": 1}}')

        xbmc.log(f"EMBY.helper.playerops: [ SetSubtitle ] {Enable}", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: SetSubtitle failed: PlayerId={PlayerId}", 3) # LOGERROR

def SetRepeatOff():
    if PlayerId != -1:
        utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.SetRepeat", "params":{{"playerid":{PlayerId}, "repeat":"off"}}}}')
        xbmc.log("EMBY.helper.playerops: [ SetRepeatOff ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: SetRepeatOff failed: PlayerId={PlayerId}", 3) # LOGERROR

def SetRepeatOneTime():
    if PlayerId != -1:
        utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Player.SetRepeat", "params":{{"playerid":{PlayerId}, "repeat":"one"}}}}')
        xbmc.log("EMBY.helper.playerops: [ SetRepeatOneTime ]", 1) # LOGINFO
    else:
        xbmc.log(f"EMBY.helper.playerops: SetRepeatOneTime failed: PlayerId={PlayerId}", 3) # LOGERROR

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

def SeekPositionTicks_to_Jsonstring(SeekPositionTicks, TimeStamp):
    DeltaTime = 0
    SeekPositionTicks = float(SeekPositionTicks)

    if TimeStamp:
        DeltaTime = float(utils.unixtimeInMicroseconds() - float(TimeStamp)) * 10000000
        SeekPositionTicks += DeltaTime

    seektime = int(SeekPositionTicks / 10000)
    milliseconds = int(seektime % 1000)
    seconds = int((seektime / 1000) % 60)
    minutes = int((seektime / 60000) % 60)
    hours =  int((seektime / 3600000) % 24)
    return f'{{"jsonrpc":"2.0","method":"Player.Seek","params":{{"playerid":{PlayerId},"value":{{"time":{{"hours":{hours},"minutes":{minutes},"seconds":{seconds},"milliseconds": {milliseconds}}}}}}},"id":1}}', DeltaTime, SeekPositionTicks

def Seek(SeekPositionTicks, isRemote=False, TimeStamp=0):
    if PlayerId != -1:
        if not wait_AVStarted():
            xbmc.log(f"EMBY.helper.playerops: Seek: avstart not set: seek={SeekPositionTicks}", 3) # LOGERROR
            return

        WarningLogSend = False

        for _ in range(5): # try 5 times
            CurrentPositionTicks = PlayBackPosition()
            JsonString, DeltaTime, SeekPositionTicks = SeekPositionTicks_to_Jsonstring(SeekPositionTicks, TimeStamp)
            Drift = (SeekPositionTicks - CurrentPositionTicks) / 10000 # in milliseconds

            if -utils.remotecontrol_drift < Drift < utils.remotecontrol_drift:
                xbmc.log(f"EMBY.helper.playerops: [ seek, allowed drift / Drift={Drift}]", 1) # LOGINFO
                return

            if isRemote:
                globals()['RemoteCommandActive'][2] += 1

            Result = utils.SendJson(JsonString, True)

            if Result:
                xbmc.log(f"EMBY.helper.playerops: Seek / SeekPositionTicks: {SeekPositionTicks} / TimeStamp :{TimeStamp} / DeltaTime: {DeltaTime} / Drift: {Drift}", 1) # LOGINFO
                return

            globals()['RemoteCommandActive'][2] -= 1

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
            return -1

        if PlayerPause:
            if PlaybackPositionCompare == PlaybackPosition:
                return PlaybackPosition
        else:
            if PlaybackPosition - 7000000 < PlaybackPositionCompare and PlaybackPosition != PlaybackPositionCompare: # Allow 500ms delta
                xbmc.log("EMBY.helper.playerops: Exact playback position found", 2) # LOGWARNING
                return PlaybackPosition

        if utils.sleep(0.2):
            return -1

        PlaybackPositionCompare = PlaybackPosition

    xbmc.log("EMBY.helper.playerops: Unable to detect exact playback position", 2) # LOGWARNING
    return PlaybackPosition

def PlayBackPosition():
    Result = None

    if PlayerId != -1:
        for _ in range(5): # try 5 times
            Result = utils.SendJson(f'{{"jsonrpc":"2.0","method":"Player.GetProperties","params":{{"playerid":{PlayerId},"properties": ["time"]}},"id":1}}').get("result", {})

            if Result:
                TimeStamp = Result.get("time", {})

                if TimeStamp:
                    PositionTicks = (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000

                    if PositionTicks < 0:
                        xbmc.log(f"EMBY.helper.playerops: PlayBackPosition invalid timestamp: Result={Result}", 2) # LOGWARNING

                        if utils.sleep(0.1):
                            return -1

                        continue

                    return PositionTicks

                xbmc.log(f"EMBY.helper.playerops: PlayBackPosition invalid result: Result={Result}", 2) # LOGWARNING
            else:
                break

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
                return (TimeStamp['hours'] * 3600000 + TimeStamp['minutes'] * 60000 + TimeStamp['seconds'] * 1000 + TimeStamp['milliseconds']) * 10000

        xbmc.log(f"EMBY.helper.playerops: PlayBackDuration failed: Result={Result}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.helper.playerops: PlayBackDuration failed: PlayerId={PlayerId}", 2) # LOGWARNING

    return 0

def PlayEmby(ItemIds, PlayCommand, StartIndex, StartPositionTicks, EmbyServer, TimeStamp):
    if utils.remotecontrol_client_control:
        globals().update({"RemoteMode": False, "WatchTogether": False, "RemotePlaybackInit": True, "RemoteControl": True})
    else:
        globals().update({"RemoteMode": False, "WatchTogether": False, "RemotePlaybackInit": True, "RemoteControl": False})

    ItemsData = []
    path = ""
    li = None
    QueryEmbyIds = ()
    Reference = {}
    Counter = [0, 0, 0]
    StartIndex = max(StartIndex, 0)
    EmbyIdStart = str(ItemIds[StartIndex])
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "AddPlaylistItem")

    for Index, EmbyID in enumerate(ItemIds):
        KodiId, KodiType = embydb.get_KodiId_KodiType_by_EmbyId_EmbyLibraryId(EmbyID)
        EmbyIDStr = str(EmbyID)

        if KodiId: # synced content
            ItemsData.append((True, EmbyID, KodiType, KodiId))
        else: # not synced content
            ItemsData.append(())
            Reference[EmbyIDStr] = Index

            if Index != StartIndex:
                QueryEmbyIds += (EmbyIDStr,)

    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "AddPlaylistItem")

    if EmbyIdStart in Reference:
        Item = EmbyServer.API.get_Item(EmbyIdStart, ['Everything'], True, False)

        if not Item:
            return

        li = listitem.set_ListItem(Item, EmbyServer.ServerData['ServerId'])
        path, Type = common.get_path_type_from_item(EmbyServer.ServerData['ServerId'], Item)
        ItemsData[Reference[EmbyIdStart]] = (False, Item['Id'], Type, li, path)

    ItemData = ItemsData[StartIndex]
    globals()["EmbyIdPlaying"] = int(ItemData[1])

    if ItemData[2] in ("song", "a"):
        PlayerIdPlaylistId = 0
        globals()['PlayerId'] = 0
    elif ItemData[2] == "p":
        PlayerIdPlaylistId = 2
    else:
        PlayerIdPlaylistId = 1
        globals()['PlayerId'] = 1

    if PlayCommand in ("PlayNow", "PlayNext"):
        PlaylistPos = (GetPlayerPosition(0), GetPlayerPosition(1))
        Offset = (PlaylistPos[0] + 1, PlaylistPos[1] + 1, 0)
    elif PlayCommand == "PlayInit":
        globals()['RemoteMode'] = True
        globals()['WatchTogether'] = True
        Stop(True)
        PlaylistSize = (GetPlaylistSize(0), GetPlaylistSize(1))
        Offset = (PlaylistSize[0], PlaylistSize[1], 0)
    elif PlayCommand == "PlaySingle":
        globals()['RemoteMode'] = True
        PlaylistSize = (GetPlaylistSize(0), GetPlaylistSize(1))
        Offset = (PlaylistSize[0], PlaylistSize[1], 0)
    else:
        return

    KodiPlaylistIndexStartitem = Offset[PlayerIdPlaylistId] + Counter[PlayerIdPlaylistId]

    if PlayerIdPlaylistId != 2:
        if ItemData[0]: # synced item
            InsertPlaylist(PlayerIdPlaylistId, KodiPlaylistIndexStartitem, ItemData[2], ItemData[3])
        else:
            utils.Playlists[PlayerIdPlaylistId].add(ItemData[4], ItemData[3], index=KodiPlaylistIndexStartitem)
    else:
        globals()["Pictures"].append((path, li))

    if PlayerIdPlaylistId == 2: # picture
        globals()["Pictures"][KodiPlaylistIndexStartitem][1].select(True)
        xbmc.executebuiltin('Action(Stop)')
        xbmc.executebuiltin('Action(Back)')
        ClearPlaylist(2)
        xbmc.executebuiltin("ReplaceWindow(10002,'plugin://{utils.PluginId}/?mode=remotepictures&position={KodiPlaylistIndexStartitem}')")
    else:
        globals()['RemoteCommandActive'][4] += 1
        globals().update({"AVStarted": False, "PlayerPause": False})
        PlayPlaylistItem(PlayerIdPlaylistId, KodiPlaylistIndexStartitem)
        StartPositionTicks = int(StartPositionTicks)

        if StartPositionTicks > 0:
            Pause(True)
            Seek(StartPositionTicks, True, TimeStamp)

            if PlayCommand == "PlaySingle":
                if wait_AVStarted():
                    Unpause(True)
        else:
            if PlayCommand == "PlayInit":
                Pause(True)
                wait_AVStarted()

    globals()['RemotePlaybackInit'] = False

    #load additional items after playback started
    if PlayCommand not in ("PlayInit", "PlaySingle"):
        if QueryEmbyIds:
            for Item in EmbyServer.API.get_Items_Ids(QueryEmbyIds, ["Everything"], True, False):
                li = listitem.set_ListItem(Item, EmbyServer.ServerData['ServerId'])
                path, Type = common.get_path_type_from_item(EmbyServer.ServerData['ServerId'], Item)
                ItemsData[Reference[Item['Id']]] = (False, Item['Id'], Type, li, path)

        for Index, ItemData in enumerate(ItemsData):
            if Index == StartIndex:
                continue

            InsertPosition = KodiPlaylistIndexStartitem + Index

            if PlayerIdPlaylistId != 2:
                if ItemData[0]: # synced item
                    InsertPlaylist(PlayerIdPlaylistId, InsertPosition, ItemData[2], ItemData[3])
                else:
                    utils.Playlists[PlayerIdPlaylistId].add(ItemData[4], ItemData[3], index=InsertPosition)
            else:
                Pictures.append((path, li))

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

def add_RemoteClientSelf(ServerId, SessionId, DeviceName, UserName):
    if ServerId not in RemoteClientData:
        disable_RemoteClients(ServerId)
        globals()['RemoteClientData'][ServerId] = {"SessionIds": [SessionId], "Usernames": {SessionId: UserName}, "Devicenames": {SessionId: DeviceName}, "ExtendedSupport": [SessionId], "ExtendedSupportAck": [SessionId]}
    elif SessionId not in RemoteClientData[ServerId]["SessionIds"]:
        globals()['RemoteClientData'][ServerId]["SessionIds"].append(SessionId)
        globals()['RemoteClientData'][ServerId]["ExtendedSupport"].append(SessionId)
        globals()['RemoteClientData'][ServerId]["ExtendedSupportAck"].append(SessionId)
        globals()['RemoteClientData'][ServerId]["Usernames"][SessionId] = UserName
        globals()['RemoteClientData'][ServerId]["Devicenames"][SessionId] = DeviceName

    send_RemoteClients(ServerId, RemoteClientData[ServerId]["ExtendedSupportAck"], True, False)

def delete_RemoteClient(ServerId, SessionIds, Force=False, LastWill=False):
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
            globals()['RemoteCommandQueue'][SessionId].put(("QUIT",))

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
        globals()['RemoteClientData'][ServerId] = {"SessionIds": [ServerSessionId], "Usernames": {ServerSessionId: utils.EmbyServers[ServerId].EmbySession[0]['UserName']}, "Devicenames": {ServerSessionId: utils.EmbyServers[ServerId].EmbySession[0]['DeviceName']}, "ExtendedSupport": [utils.EmbyServers[ServerId].EmbySession[0]['Id']], "ExtendedSupportAck": [utils.EmbyServers[ServerId].EmbySession[0]['Id']]}
    else:
        globals()['RemoteClientData'][ServerId] = {"SessionIds": SessionIds, "ExtendedSupport": ExtendedSupport, "ExtendedSupportAck": ExtendedSupportAck, "Usernames": {}, "Devicenames": {}}

        for Index, SessionId in enumerate(SessionIds):
            globals()['RemoteClientData'][ServerId]["Usernames"][SessionId] = Usernames[Index]
            globals()['RemoteClientData'][ServerId]["Devicenames"][SessionId] = Devicenames[Index]

        # Disable remote mode when self device is the only one left
        if len(RemoteClientData[ServerId]["SessionIds"]) == 1 and RemoteClientData[ServerId]["SessionIds"][0] == ServerSessionId:
            disable_RemoteClients(ServerId)

def disable_RemoteClients(ServerId):
    if RemoteMode:
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

def unlink_RemoteClients(ServerId):
    xbmc.log("EMBY.helper.playerops: unlink remote clients", 1) # LOGINFO

    for SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
        if SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", "clients|||||", True, False)

# Remote control clients
def RemoteCommand(ServerId, selfSessionId, Command, EmbyId=-1):
    xbmc.log(f"EMBY.helper.playerops: --> [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGINFO

    if Command == "stop":
        if RemoteCommandActive[3] > 0:
            RemoteCommandActive[3] -= 1

            if WatchTogether:
                globals().update({'WatchTogether': False, 'RemoteMode': False, 'RemoteControl': False})
        else:
            globals()['RemoteCommandActive'][3] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "stop", -1)
    elif Command == "pause":
        if RemoteCommandActive[0] > 0:
            RemoteCommandActive[0] -= 1
        else:
            globals()['RemoteCommandActive'][0] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "pause", -1)
    elif Command == "unpause":
        if RemoteCommandActive[1] > 0:
            RemoteCommandActive[1] -= 1
        else:
            globals()['RemoteCommandActive'][1] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "unpause", -1)
    elif Command == "seek":
        if RemoteCommandActive[2] > 0:
            RemoteCommandActive[2] -= 1
        else:
            globals()['RemoteCommandActive'][2] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "seek", -1)
    elif Command == "play":
        if RemoteCommandActive[4] > 0:
            RemoteCommandActive[4] -= 1
        else:
            globals()['RemoteCommandActive'][4] = 0
            queue_RemoteCommand(ServerId, selfSessionId, "play", EmbyId)

    xbmc.log(f"EMBY.helper.playerops: --< [ remotecommand received: {Command} / {RemoteCommandActive} ]", 1) # LOGINFO

def RemoteClientResync(ServerId, SessionId, LocalEmbyIdPlaying):
    if utils.sleep(utils.remotecontrol_resync_time):
        return

    if EmbyIdPlaying == LocalEmbyIdPlaying:
        xbmc.log(f"EMBY.helper.playerops: resync started {SessionId}", 1) # LOGINFO
        PositionTicks = PlayBackPosition()

        if PositionTicks != -1:
            utils.EmbyServers[ServerId].API.send_seek(SessionId, PositionTicks, True)
    else:
        xbmc.log(f"EMBY.helper.playerops: resync skipped {SessionId}", 2) # LOGWARNING

def queue_RemoteCommand(ServerId, selfSessionId, Command, EmbyId):
    for SessionId in RemoteClientData[ServerId]["SessionIds"]:
        if SessionId != selfSessionId:
            globals()['RemoteCommandQueue'][SessionId].put((Command, EmbyId))

def thread_RemoteCommands(ServerId, SessionId):
    xbmc.log(f"EMBY.helper.playerops: Remote command queue opened {SessionId}", 1) # LOGINFO
    API = utils.EmbyServers[ServerId].API

    while True:
        Command = globals()['RemoteCommandQueue'][SessionId].get()
        xbmc.log(f"EMBY.helper.playerops: Remote command: {Command} {SessionId}", 1) # LOGINFO

        if Command[0] == "QUIT":
            xbmc.log(f"EMBY.helper.playerops: Remote command queue closed {SessionId}", 1) # LOGINFO
            break

        if not RemoteControl:
            xbmc.log(f"EMBY.helper.playerops: Remote command skip by disabled remote control: {Command} {SessionId}", 1) # LOGINFO
            continue

        if RemotePlaybackInit:
            xbmc.log(f"EMBY.helper.playerops: Remote command skip by playback init: {Command} {SessionId}", 1) # LOGINFO
            continue

        if Command[0] == "stop":
            if not utils.SystemShutdown:
                API.send_stop(SessionId, True)
                xbmc.log(f"EMBY.helper.playerops: remotecommand send: stop {SessionId}", 1) # LOGINFO
        elif Command[0] == "pause":
            PositionTicks = PlayBackPosition()
            Timestamp = utils.unixtimeInMicroseconds()

            if SessionId in RemoteClientData[ServerId]["ExtendedSupportAck"]:
                API.send_text_msg(SessionId, "remotecommand", f"pause|{PositionTicks}|{Timestamp}", True)
            else:
                API.send_pause(SessionId, True)
                globals()['RemoteCommandQueue'][SessionId].put(("seek",))

            xbmc.log(f"EMBY.helper.playerops: remotecommand send: pause {SessionId}", 1) # LOGINFO
        elif Command[0] == "unpause":
            API.send_unpause(SessionId, True)
            xbmc.log(f"EMBY.helper.playerops: remotecommand send: unpause {SessionId}", 1) # LOGINFO
        elif Command[0] == "seek":
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

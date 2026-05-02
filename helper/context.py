import os
import random
import xbmcvfs
import xbmc
import xbmcgui
from database import dbio
from emby import listitem, metadata
from core import common
from . import utils, playerops, artworkcache

xbmcgui.Window(10000).setProperty('EmbyRemoteclient', 'False')


def load_item(KodiId=None, KodiType=None):
    ServerId = xbmc.getInfoLabel('ListItem.Property(embyserverid)')
    ListItemEmbyId = xbmc.getInfoLabel('ListItem.Property(embyid)')

    if not KodiType:
        KodiType = xbmc.getInfoLabel('ListItem.DBTYPE')

    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): load_item ServerId: {ServerId}, KodiType: {KodiType}, ListItemEmbyId: {ListItemEmbyId}, ListItem.FolderPath: {xbmc.getInfoLabel('ListItem.FolderPath')}", 1) # LOGDEBUG

    if not ServerId:
        if not KodiId:
            KodiId = xbmc.getInfoLabel('ListItem.DBID')

        EmbyFavourite = None
        EmbyId = None

        for ServerId in utils.EmbyServers:
            embydb = dbio.DBOpenRO(ServerId, "contextmenu_item")
            EmbyId, EmbyFavourite = embydb.get_EmbyId_EmbyFavourite_by_KodiId_KodiType(KodiId, KodiType)
            dbio.DBCloseRO(ServerId, "contextmenu_item")

            if EmbyId:
                break

        return EmbyId, ServerId, EmbyFavourite, KodiType

    return ListItemEmbyId, ServerId, None, KodiType

def deletedownload():
    KodiTypeListItem = xbmc.getInfoLabel('ListItem.DBTYPE')
    KodiIdListItem = xbmc.getInfoLabel('ListItem.DBID')

    if KodiTypeListItem in ("season", "tvshow"):
        KodiType = "episode"
        videodb = dbio.DBOpenRO("video", f"deletedownload_get_{KodiTypeListItem}")
        DeleteItems = videodb.get_KodiId_FileName_by_SubcontentId(KodiIdListItem, KodiTypeListItem)
        dbio.DBCloseRO("video", f"deletedownload_get_{KodiTypeListItem}")
    else:
        KodiType = KodiTypeListItem
        DeleteItems = ((KodiIdListItem, xbmc.getInfoLabel('ListItem.FileName')),)

    ArtworksNoUrlParam = ()
    SQLs = {}
    dbio.DBOpenRW("video", "deletedownload_item_replace", SQLs)
    ServerIdOld = ""
    ServerId = ""

    for KodiIdListItem, KodiFileName in DeleteItems:
        EmbyId = ""

        if "emby" in SQLs and SQLs["emby"]:
            EmbyId, _ = SQLs["emby"].get_EmbyId_EmbyFavourite_by_KodiId_KodiType(KodiIdListItem, KodiType)

        if not EmbyId:
            EmbyId, ServerId, _, _ = load_item(KodiIdListItem, KodiType)

        if not EmbyId:
            continue

        if ServerIdOld != ServerId:
            if ServerIdOld:
                dbio.DBCloseRW(ServerIdOld, "deletedownload_item", SQLs)

            dbio.DBOpenRW(ServerId, "deletedownload_item", SQLs)
            ServerIdOld = ServerId

        KodiPathIdBeforeDownload, KodiFileId, KodiId = SQLs['emby'].get_DownloadItem_PathId_FileId(EmbyId)
        KodiFileId = str(KodiFileId)
        EmbyId = str(EmbyId)
        SQLs['emby'].delete_DownloadItem(EmbyId)
        SQLs['video'].update_Name(KodiId, KodiType, False)

        if KodiPathIdBeforeDownload:
            PathStream = SQLs['video'].get_Path(KodiPathIdBeforeDownload)
            SQLs['video'].replace_PathId(KodiFileId, KodiPathIdBeforeDownload)
            ArtworksNoUrlParam += SQLs['video'].download_Artwork(KodiId, KodiType, False)
            PathStreamFile = os.path.join(PathStream.replace("|redirect-limit=1000&failonerror=false", ""), f"{KodiFileName}|redirect-limit=1000&failonerror=false")
            SQLs['video'].replace_Path_ContentItem(KodiId, KodiType, PathStream, PathStreamFile)
            DownloadPath = xbmcvfs.translatePath(os.path.join(utils.DownloadPath, "EMBY-offline-content", KodiType, KodiFileId, ""))
            DownloadFile = os.path.join(DownloadPath, KodiFileName)
            utils.delFile(DownloadFile)
            utils.rmFolder(DownloadPath)

        if KodiType == "episode":
            ArtworksNoUrlParam += SQLs['video'].download_Subcontent(KodiId, False)

    if ServerId:
        dbio.DBCloseRW(ServerId, "deletedownload_item", SQLs)

    dbio.DBCloseRW("video", "deletedownload_item_replace", SQLs)
    ArtworksNoUrlParam = list(dict.fromkeys(ArtworksNoUrlParam)) # filter doubles
    artworkcache.CacheAllEntries(ArtworksNoUrlParam, "")
    utils.refresh_widgets(True)

def download():
    KodiTypeListItem = xbmc.getInfoLabel('ListItem.DBTYPE')
    KodiIdListItem = xbmc.getInfoLabel('ListItem.DBID')
    videodb = dbio.DBOpenRO("video", "download_item")

    if KodiTypeListItem in ("season", "tvshow"):
        KodiType = "episode"
        DownloadItems = videodb.get_Fileinfo_by_SubcontentId(KodiIdListItem, KodiTypeListItem)  # idEpisode, idParentPath, idPath, idFile, strFilename, c00 (Name), strPath, idShow
    else:
        KodiType = KodiTypeListItem
        DownloadItems = videodb.get_Fileinfo(KodiIdListItem, KodiType)

    dbio.DBCloseRO("video", "download_item")

    for KodiMediaId, KodiPathId, KodiFileId, KodiFilename, KodiMediaName in DownloadItems:
        EmbyId, ServerId, _, _ = load_item(KodiMediaId, KodiType)

        if not EmbyId:
            continue

        PathDownload = os.path.join(utils.DownloadPath, "EMBY-offline-content", "")
        embydb = dbio.DBOpenRO(ServerId, "download_item")
        FileSize = embydb.get_FileSize(EmbyId)
        dbio.DBCloseRO(ServerId, "download_item")

        if FileSize:
            utils.EmbyServers[ServerId].API.download_file(EmbyId, PathDownload, FileSize, KodiMediaName, KodiType, KodiPathId, KodiFileId, KodiMediaId, KodiFilename)

def gotoshow():
    KodiId = xbmc.getInfoLabel('ListItem.DBID')
    videodb = dbio.DBOpenRO("video", "gotoshow")
    KodiShowId = videodb.get_showid_by_episodeid(KodiId)
    dbio.DBCloseRO("video", "gotoshow")
    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): Gotoshow, ShowId = {KodiShowId}", 1) # LOGDEBUG

    if KodiShowId:
        utils.ActivateWindow("videos", f"videodb://tvshows/titles/{KodiShowId}")

def gotoseason():
    KodiId = xbmc.getInfoLabel('ListItem.DBID')
    KodiSeason = xbmc.getInfoLabel('ListItem.Season')
    videodb = dbio.DBOpenRO("video", "gotoshow")
    KodiShowId = videodb.get_showid_by_episodeid(KodiId)
    dbio.DBCloseRO("video", "gotoshow")
    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): Gotoseason, ShowId = {KodiShowId}, Season = {KodiSeason}", 1) # LOGDEBUG

    if KodiShowId:
        utils.ActivateWindow("videos", f"videodb://tvshows/titles/{KodiShowId}/{KodiSeason}")

def gotoalbum():
    KodiId = xbmc.getInfoLabel('ListItem.DBID')
    musicdb = dbio.DBOpenRO("music", "gotoalbum")
    KodiAlbumId = musicdb.get_albumid_by_songid(KodiId)
    dbio.DBCloseRO("music", "gotoalbum")
    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): gotoalbum, AlbumId = {KodiAlbumId}", 1) # LOGDEBUG

    if KodiAlbumId:
        utils.ActivateWindow("music", f"musicdb://albums/{KodiAlbumId}/")

def gotoartist():
    KodiId = xbmc.getInfoLabel('ListItem.DBID')
    musicdb = dbio.DBOpenRO("music", "gotoartist")
    KodiArtistId = musicdb.get_artistid_by_songid(KodiId)
    dbio.DBCloseRO("music", "gotoartist")
    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): gotoartist, ArtistId = {KodiArtistId}", 1) # LOGDEBUG

    if KodiArtistId:
        utils.ActivateWindow("music", f"musicdb://artists/{KodiArtistId}/")

def similar(EmbyType):
    EmbyId, ServerId, _, _ = load_item()

    if not EmbyId:
        return

    if EmbyType in ("Movie", "Video", "Series", "Season", "Episode", "MusicVideo"):
        utils.ActivateWindow("videos", f"plugin://plugin.service.emby-next-gen/?id={EmbyId}&mode=browse&query=similar&server={ServerId}&parentid=0&content=all&libraryid=0")
    elif EmbyType in ("MusicArtist", "MusicAlbum", "Audio"):
        utils.ActivateWindow("music", f"plugin://plugin.service.emby-next-gen/?id={EmbyId}&mode=browse&query=similar&server={ServerId}&parentid=0&content=all&libraryid=0")
    else:
        utils.ActivateWindow("pictures", f"plugin://plugin.service.emby-next-gen/?id={EmbyId}&mode=browse&query=similar&server={ServerId}&parentid=0&content=all&libraryid=0")

def multiversion():
    Path = xbmc.getInfoLabel('ListItem.Path')
    PathFiltered = Path.replace("dav://127.0.0.1:57342", "").replace("http://127.0.0.1:57342", "").replace("/emby_addon_mode", "")
    MetaData = metadata.load_MetaData(PathFiltered, False, False)
    Selection = []

    for MediaSource in MetaData['MediaSources']:
        Selection.append(f"{MediaSource[0]['Name']} - {utils.SizeToText(float(MediaSource[0]['Size']))} - {MediaSource[0]['Path']}")

    MetaData['SelectionIndexMediaSource'] = utils.Dialog.select(utils.Translate(33453), Selection)

    if MetaData['SelectionIndexMediaSource'] == -1: # Cancel
        return

    metadata.MediaSourceContextMenu = MetaData['SelectionIndexMediaSource']

    if not MetaData["isDynamic"]:
        utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"{MetaData["Type"]}id": {MetaData["KodiId"]}}}, "options": {{"resume": true}}}}, "id": 1}}')
    else:
        PathFile = f"{Path}{xbmc.getInfoLabel('ListItem.Filename')}"

        if MetaData["Type"] not in utils.KodiTypeMapping:
            return

        EmbyType = utils.KodiTypeMapping[MetaData["Type"]]
        Item = utils.EmbyServers[MetaData["ServerId"]].API.get_Item(MetaData["EmbyId"], (EmbyType,), True, False, False)

        if not Item:
            return

        ListItem = listitem.set_ListItem(Item, MetaData["ServerId"], PathFile)
        KodiPlaylistIndexStartitem = playerops.GetPlaylistSize(1)
        utils.Playlists[1].add(PathFile, ListItem, index=KodiPlaylistIndexStartitem) # Path, ListItem, Index
        utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"playlistid": 1, "position": {KodiPlaylistIndexStartitem}}}}}, "id": 1}}')

def specials():
    SpecialFeaturesSelections = []
    EmbyId, ServerId, _, _ = load_item()

    if not EmbyId:
        return

    # Load SpecialFeatures
    embydb = dbio.DBOpenRO(ServerId, "specials")
    SpecialFeaturesIds = embydb.get_special_features(EmbyId)

    for SpecialFeaturesId in SpecialFeaturesIds:
        SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])

        if SpecialFeaturesMediasources:
            SpecialFeaturesSelections.append((SpecialFeaturesMediasources[0][3], SpecialFeaturesId[0]))

    dbio.DBCloseRO(ServerId, "specials")
    MenuData = []
    SpecialFeaturesSelections.sort()

    for SpecialFeaturesSelection in SpecialFeaturesSelections:
        MenuData.append(SpecialFeaturesSelection[0])

    resp = utils.Dialog.select(utils.Translate(33231), MenuData)

    if resp < 0:
        return

    ItemId = SpecialFeaturesSelections[resp][1]
    SpecialFeatureItem = utils.EmbyServers[ServerId].API.get_Item(ItemId, ('All',), True, False, False) # Workaround: "Video" param not respected by Emby server's IncludeItemTypes (for specials)

    if SpecialFeatureItem:
        li = listitem.set_ListItem(SpecialFeatureItem, ServerId)
        common.set_path_filename(SpecialFeatureItem, ServerId, None, True)
        li.setProperty('path', SpecialFeatureItem['KodiFullPath'])
        Pos = playerops.GetPlaylistPosition(1) + 1
        utils.Playlists[1].add(SpecialFeatureItem['KodiFullPath'], li, index=Pos)
        playerops.PlayPlaylistItem(1, Pos)

def favorites():
    EmbyId, ServerId, EmbyFavourite, _ = load_item()

    if not EmbyId:
        return

    if EmbyFavourite:
        utils.EmbyServers[ServerId].API.favorite(EmbyId, False)
        utils.Dialog.notification(heading=utils.Translate(33558), message=utils.Translate(33066), icon=utils.icon, time=utils.displayMessage)
    else:
        utils.EmbyServers[ServerId].API.favorite(EmbyId, True)
        utils.Dialog.notification(heading=utils.Translate(33558), message=utils.Translate(33067), icon=utils.icon, time=utils.displayMessage)

def refreshitem():
    EmbyId, ServerId, _, KodiType = load_item()

    if not EmbyId:
        return

    utils.EmbyServers[ServerId].API.refresh_item(EmbyId)

    if KodiType in utils.KodiTypeMapping:
        utils.EmbyServers[ServerId].library.updated([(EmbyId, utils.KodiTypeMapping[KodiType], "unknown")], True)

def deleteitem():
    EmbyId, ServerId, _, KodiType = load_item()
    if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): Delete item, metadata: {ServerId}, KodiType: {KodiType}, EmbyId: {EmbyId}", 1) # LOGDEBUG

    if not EmbyId:
        return

    embydb = dbio.DBOpenRO(ServerId, "contextmenu_item")

    if KodiType == "season":
        Path, EmbyIds = embydb.get_EpisodePathsBySeason(EmbyId)
    elif KodiType == "tvshow":
        Path, EmbyIds = embydb.get_EpisodePathsBySeries(EmbyId)
    elif KodiType == "movie":
        Path, EmbyIds = embydb.get_SinglePath(EmbyId, "Movie")

        if not EmbyIds: # Emby homevideos are synced as "movie" content into Kodi
            Path, EmbyIds = embydb.get_SinglePath(EmbyId, "Video")
    elif KodiType in utils.KodiTypeMapping:
        Path, EmbyIds = embydb.get_SinglePath(EmbyId, utils.KodiTypeMapping[KodiType])
    else:
        Path = ""
        EmbyIds = ()

    EmbyIds += (EmbyId,)
    EmbyIds = set(EmbyIds) # deduplicate Items
    dbio.DBCloseRO(ServerId, "contextmenu_item")

    if not Path:
        Path = utils.Translate(33703)

    if utils.Dialog.yesno(heading=utils.Translate(33015), message=Path):
        for EmbyId in EmbyIds:
            if utils.DebugLog: xbmc.log(f"EMBY.helper.context (DEBUG): Delete item: EmbyId: {EmbyId}", 1) # LOGDEBUG
            utils.EmbyServers[ServerId].API.delete_item(EmbyId)
            utils.EmbyServers[ServerId].library.removed([EmbyId], True)

        xbmc.executebuiltin("Container.Refresh()")

def remoteplay():
    EmbyId, ServerId, _, _ = load_item()

    if not EmbyId:
        return

    KodiId = xbmc.getInfoLabel('ListItem.DBID')
    KodiType = xbmc.getInfoLabel('ListItem.DBTYPE')

    if not KodiId or not KodiType:
        return

    videodb = dbio.DBOpenRO("video", "remoteplay")
    Progress = videodb.get_Progress_by_KodiType_KodiId(KodiType, KodiId)
    dbio.DBCloseRO("video", "remoteplay")

    if Progress:
        PositionTicks = int(Progress * 10000000)
    else:
        PositionTicks = 0

    ActiveSessions = utils.EmbyServers[ServerId].API.get_active_sessions()
    SelectionLabels = []
    ClientData = []

    for ActiveSession in ActiveSessions:
        if ActiveSession['SupportsRemoteControl'] and ActiveSession['Id'] != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            UserName = ActiveSession.get('UserName', "unknown")
            SelectionLabels.append(f"{ActiveSession['DeviceName']}, {UserName}")
            ClientData.append(ActiveSession['Id'])

    Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

    if not Selections:
        return

    for Selection in Selections:
        utils.EmbyServers[ServerId].API.send_play(ClientData[Selection], EmbyId, "PlayNow", PositionTicks, False)

def watchtogether():
    EmbyId, ServerId, _, _ = load_item()

    if not EmbyId:
        return

    # Disable previous remote sessions
    playerops.disable_RemoteClients(ServerId)
    playerops.WatchTogether = False
    playerops.RemoteControl = False
    utils.RemoteMode = False
    playerops.Stop(False, True)

    # Enable new remote session
    if len(playerops.RemoteClientData[ServerId]["SessionIds"]) <= 1:
        add_remoteclients(ServerId)

        if len(playerops.RemoteClientData[ServerId]["SessionIds"]) <= 1:
            return

    playerops.WatchTogether = True
    playerops.enable_remotemode(ServerId)
    playerops.PlayEmby([EmbyId], "PlayInit", 0, 0, utils.EmbyServers[ServerId], 0)

    for SessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
        if SessionId in playerops.RemoteClientData[ServerId]["ExtendedSupportAck"] and SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", f"playinit|{EmbyId}|0|0", True)
        elif SessionId not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
            utils.EmbyServers[ServerId].API.send_play(SessionId, EmbyId, "PlayNow", 0, True)
            utils.EmbyServers[ServerId].API.send_pause(SessionId, True)

     # give time to prepare streams for all client devices
    ProgressBar = xbmcgui.DialogProgress()
    ProgressBar.create(utils.Translate(33493))
    ProgressBar.update(0, utils.Translate(33493))

    # Delay playback
    WaitFactor = int(int(utils.watchtogeter_start_delay) / 10)

    for Index in range(1, WaitFactor * 100):
        ProgressBar.update(int(Index / WaitFactor), utils.Translate(33493))

        if Index % 10 == 0: # modulo 20 -> every 2 seconds resend to unspported client the start
            for SessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
                if SessionId not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
                    utils.EmbyServers[ServerId].API.send_pause(SessionId, True)
                    utils.EmbyServers[ServerId].API.send_seek(SessionId, 0, True)

        if check_ProgressBar(ProgressBar):
            # cancel remote session
            playerops.disable_RemoteClients(ServerId)
            playerops.WatchTogether = False
            playerops.RemoteControl = False
            utils.RemoteMode = False
            return

    ProgressBar.close()
    playerops.Unpause(False)

def delete_remoteclients():
    _, ServerId, _, _ = load_item()

    if not ServerId:
        return

    SelectionLabels = []
    SessionIds = []

    for RemoteClientSessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
        SelectionLabels.append(f"{playerops.RemoteClientData[ServerId]['Devicenames'][RemoteClientSessionId]}, {playerops.RemoteClientData[ServerId]['Usernames'][RemoteClientSessionId]}")
        SessionIds.append(RemoteClientSessionId)

    Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

    if Selections:
        RemoveSessionIds = []

        for Selection in Selections:
            RemoveSessionIds.append(SessionIds[Selection])

        playerops.delete_RemoteClient(ServerId, RemoveSessionIds, False)

    xbmcgui.Window(10000).setProperty('EmbyRemoteclient', str(playerops.RemoteClientData[ServerId]["SessionIds"] != [utils.EmbyServers[ServerId].EmbySession[0]['Id']]))

def add_remoteclients(ServerId=None):
    if not ServerId:
        _, ServerId, _, _ = load_item()

        if not ServerId:
            return

    ActiveSessions = utils.EmbyServers[ServerId].API.get_active_sessions()
    SelectionLabels = []
    ClientData = []

    for ActiveSession in ActiveSessions:
        if ActiveSession['SupportsRemoteControl'] and ActiveSession['Id'] != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            if ActiveSession['Id'] not in playerops.RemoteClientData[ServerId]["SessionIds"]:
                UserName = ActiveSession.get('UserName', "unknown")
                SelectionLabels.append(f"{ActiveSession['DeviceName']}, {UserName}")
                ClientData.append((ActiveSession['Id'], ActiveSession['DeviceName'], UserName))

    Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

    if not Selections:
        return

    for Selection in Selections:
        utils.EmbyServers[ServerId].API.send_text_msg(ClientData[Selection][0], "remotecommand", f"connect|{utils.EmbyServers[ServerId].EmbySession[0]['Id']}|60", True)

    # wait for clients
    ProgressBar = xbmcgui.DialogProgress()
    ProgressBar.create(utils.Translate(33495))
    WaitFactor = 10 / utils.remotecontrol_wait_clients

    for Index in range(1, int(utils.remotecontrol_wait_clients) * 10):
        ProgressBar.update(int(Index * WaitFactor), utils.Translate(33492))

        if check_ProgressBar(ProgressBar):
            return

        if len(Selections) + 1 == len(playerops.RemoteClientData[ServerId]["SessionIds"]):
            break

    ProgressBar.close()

    # Force clients to participate
    for Selection in Selections:
        if ClientData[Selection][0] not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
            playerops.add_RemoteClient(ServerId, ClientData[Selection][0], ClientData[Selection][1], ClientData[Selection][2])

    playerops.enable_remotemode(ServerId)
    xbmcgui.Window(10000).setProperty('EmbyRemoteclient', str(playerops.RemoteClientData[ServerId]["SessionIds"] != [utils.EmbyServers[ServerId].EmbySession[0]['Id']]))

def check_ProgressBar(ProgressBar):
    if utils.sleep(0.1):
        ProgressBar.close()
        return True

    if ProgressBar.iscanceled():
        ProgressBar.close()
        return True

    return False

def Record():
    Temp = xbmc.getInfoLabel('ListItem.EPGEventIcon') # Icon path has Emby's EPG programId assinged (workaround)
    Temp = Temp[Temp.find("@") + 1:].replace("/","")
    Temp = Temp.split("Z")
    Timers = utils.EmbyServers[Temp[0]].API.get_timer(Temp[1])
    TimerId = 0

    if Timers:
        for Timer in Timers:
            if Timer['ProgramId'] == Temp[1]:
                TimerId = Timer['ProgramInfo']['TimerId']
                break

    if TimerId: # Delete recording
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33496)):
            utils.EmbyServers[Temp[0]].API.delete_timer(TimerId)
    else: # Add recoding
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33497)):
            utils.EmbyServers[Temp[0]].API.set_timer(Temp[1])

def playrandom():
    DBTYPE = xbmc.getInfoLabel("ListItem.DBTYPE")

    if DBTYPE == "season":
        TVShowDBID = xbmc.getInfoLabel("ListItem.TVShowDBID")
        DBID = xbmc.getInfoLabel('ListItem.DBID')
        videodb = dbio.DBOpenRO("video", "playrandomseason")
        Episodes = videodb.get_episodes_by_seasonId(TVShowDBID, DBID)
        dbio.DBCloseRO("video", "playrandomseason")

        if not Episodes:
            return

        Index = round(random.uniform(0, len(Episodes) - 1))
        DBTYPE = "episode"
        DBID = Episodes[Index][0]
    elif DBTYPE == "tvshow":
        DBID = xbmc.getInfoLabel('ListItem.DBID')
        videodb = dbio.DBOpenRO("video", "playrandomtvshow")
        Episodes = videodb.get_episodes_by_tvshowId(DBID)
        dbio.DBCloseRO("video", "playrandomtvshow")

        if not Episodes:
            return

        Index = round(random.uniform(0, len(Episodes) - 1))
        DBTYPE = "episode"
        DBID = Episodes[Index][0]
    else:
        NumAllItems = xbmc.getInfoLabel("Container.NumAllItems()")
        NumItems = xbmc.getInfoLabel("Container.NumItems()")

        if NumAllItems and NumItems:
            NumItems = int(NumItems)
            NumAllItems = int(NumAllItems)
            StartIndex = NumAllItems - NumItems
        else:
            return

        Index = round(random.uniform(StartIndex, NumItems))
        DBID = xbmc.getInfoLabel(f"Container.ListItemAbsolute({Index}).DBID")
        DBTYPE = xbmc.getInfoLabel(f"Container.ListItemAbsolute({Index}).DBTYPE")

    utils.SendJson(f'{{"jsonrpc": "2.0", "method": "Player.Open", "params": {{"item": {{"{DBTYPE}id": {DBID}}}, "options": {{"resume": false}}}}, "id": 1}}', True)

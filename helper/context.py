import xbmc
import xbmcgui
from database import dbio
from emby import listitem
from core import common
from . import utils, playerops, artworkcache

xbmcgui.Window(10000).setProperty('EmbyRemoteclient', 'False')


def load_item(KodiId=None, KodiType=None):
    ServerId = xbmc.getInfoLabel('ListItem.Property(embyserverid)')
    ListItemEmbyId = xbmc.getInfoLabel('ListItem.Property(embyid)')

    if not ServerId:
        if not KodiId:
            KodiId = xbmc.getInfoLabel('ListItem.DBID')

        if not KodiType:
            KodiType = xbmc.getInfoLabel('ListItem.DBTYPE')

        EmbyFavourite = None
        EmbyId = None

        for ServerId in utils.EmbyServers:
            embydb = dbio.DBOpenRO(ServerId, "contextmenu_item")
            EmbyId, EmbyFavourite = embydb.get_EmbyId_EmbyFavourite_by_KodiId_KodiType(KodiId, KodiType)
            dbio.DBCloseRO(ServerId, "contextmenu_item")

            if EmbyId:
                break

        return EmbyId, ServerId, EmbyFavourite

    return ListItemEmbyId, ServerId, None

def update_Artwork(KodiId, KodiType, SQLs, Add):
    Artworks = ()
    ArtworksData = SQLs['video'].get_artworks(KodiId, KodiType)

    for ArtworkData in ArtworksData:
        if ArtworkData[3] in ("poster", "thumb", "landscape"):
            UrlMod = ArtworkData[4].split("|")

            if Add:
                UrlMod = f"{UrlMod[0].replace('-download', '')}-download|redirect-limit=1000"
            else:
                UrlMod = ArtworkData[4].replace("-download", "")

            SQLs['video'].update_artwork(ArtworkData[0], UrlMod)
            Artworks += ((UrlMod,),)

    return Artworks

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
        DeleteItems = ((KodiIdListItem, xbmc.getInfoLabel('ListItem.FileName'), KodiType),)

    Artworks = ()
    SQLs = dbio.DBOpenRW("video", "deletedownload_item_replace", {})

    for DeleteItem in DeleteItems:
        EmbyId, ServerId, _ = load_item(DeleteItem[0], KodiType)

        if not EmbyId:
            continue

        SQLs = dbio.DBOpenRW(ServerId, "deletedownload_item", SQLs)
        KodiPathIdBeforeDownload, KodiFileId, KodiId = SQLs['emby'].get_DownloadItem_PathId_FileId(EmbyId)
        SQLs['emby'].delete_DownloadItem(EmbyId)
        SQLs['video'].update_Name(DeleteItem[0], DeleteItem[2], False)

        if KodiPathIdBeforeDownload:
            SQLs['video'].replace_PathId(KodiFileId, KodiPathIdBeforeDownload)
            Artworks += update_Artwork(DeleteItem[0], KodiType, SQLs, False)
            FilePath = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content")
            FilePath = utils.PathAddTrailing(f"{FilePath}{KodiType}")
            SQLs['video'].replace_Path_ContentItem(KodiId, KodiType, utils.AddonModePath, utils.translatePath(FilePath).decode('utf-8'))
            FilePath = f"{FilePath}{DeleteItem[1]}"
            utils.delFile(FilePath)

        SQLs = dbio.DBCloseRW(ServerId, "deletedownload_item", SQLs)

        if KodiType == "episode":
            Artworks += SQLs['video'].set_Subcontent_download_tags(KodiId, False)

    dbio.DBCloseRW("video", "deletedownload_item_replace", SQLs)
    Artworks = list(dict.fromkeys(Artworks)) # filter doubles
    artworkcache.CacheAllEntries(Artworks, None)
    utils.refresh_widgets(True)

def download():
    KodiTypeListItem = xbmc.getInfoLabel('ListItem.DBTYPE')
    KodiIdListItem = xbmc.getInfoLabel('ListItem.DBID')
    videodb = dbio.DBOpenRO("video", "download_item")

    if KodiTypeListItem in ("season", "tvshow"):
        KodiType = "episode"
        DownloadItems = videodb.get_Fileinfo_by_SubcontentId(KodiIdListItem, KodiTypeListItem)
    else:
        KodiType = KodiTypeListItem
        DownloadItems = videodb.get_Fileinfo(KodiIdListItem, KodiType)

    dbio.DBCloseRO("video", "download_item")

    for DownloadItem in DownloadItems: # KodiId, ParentPath, KodiPathIdBeforeDownload, KodiFileId, Filename, Name
        EmbyId, ServerId, _ = load_item(DownloadItem[0], KodiType)

        if not EmbyId:
            continue

        Path = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content")
        utils.mkDir(Path)
        Path = utils.PathAddTrailing(f"{Path}{KodiType}")
        utils.mkDir(Path)
        Path = utils.translatePath(Path).decode('utf-8')
        FilePath = f"{Path}{DownloadItem[4]}"
        embydb = dbio.DBOpenRO(ServerId, "download_item")
        FileSize = embydb.get_FileSize(EmbyId, 0)
        dbio.DBCloseRO(ServerId, "download_item")

        if FileSize:
            utils.EmbyServers[ServerId].API.download_file({"Id": EmbyId, "ParentPath": DownloadItem[1], "Path": Path, "FilePath": FilePath, "FileSize": FileSize, "Name": DownloadItem[5], "KodiType": KodiType, "KodiPathIdBeforeDownload": DownloadItem[2], "KodiFileId": DownloadItem[3], "KodiId": DownloadItem[0]})

def specials():
    SpecialFeaturesSelections = []
    EmbyId, ServerId, _ = load_item()

    if not EmbyId:
        return

    # Load SpecialFeatures
    embydb = dbio.DBOpenRO(ServerId, "specials")
    SpecialFeaturesIds = embydb.get_special_features(EmbyId)

    for SpecialFeaturesId in SpecialFeaturesIds:
        SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])

        if SpecialFeaturesMediasources:
            SpecialFeaturesSelections.append({"Name": SpecialFeaturesMediasources[0][4], "Id": SpecialFeaturesId[0]})

    dbio.DBCloseRO(ServerId, "specials")
    MenuData = []

    for SpecialFeaturesSelection in SpecialFeaturesSelections:
        MenuData.append(SpecialFeaturesSelection['Name'])

    resp = utils.Dialog.select(utils.Translate(33231), MenuData)

    if resp < 0:
        return

    ItemData = SpecialFeaturesSelections[resp]
    SpecialFeatureItem = utils.EmbyServers[ServerId].API.get_Item(ItemData['Id'], ['Movie'], True, False, True)

    if SpecialFeatureItem:
        li = listitem.set_ListItem(SpecialFeatureItem, ServerId)
        path, _ = common.get_path_type_from_item(ServerId, SpecialFeatureItem)
        li.setProperty('path', path)
        Pos = playerops.GetPlayerPosition(1) + 1
        utils.Playlists[1].add(path, li, index=Pos)
        playerops.PlayPlaylistItem(1, Pos)

def favorites():
    EmbyId, ServerId, EmbyFavourite = load_item()

    if not EmbyId:
        return

    if EmbyFavourite:
        utils.EmbyServers[ServerId].API.favorite(EmbyId, False)
        utils.Dialog.notification(heading="Emby favorites", message="Removed", icon=utils.icon, time=int(utils.displayMessage) * 1000)
    else:
        utils.EmbyServers[ServerId].API.favorite(EmbyId, True)
        utils.Dialog.notification(heading="Emby favorites", message="Added", icon=utils.icon, time=int(utils.displayMessage) * 1000)

def refreshitem():
    EmbyId, ServerId, _ = load_item()

    if not EmbyId:
        return

    utils.EmbyServers[ServerId].API.refresh_item(EmbyId)

def deleteitem():
    EmbyId, ServerId, _ = load_item()

    if not EmbyId:
        return

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33015)):
        utils.EmbyServers[ServerId].API.delete_item(EmbyId)
        utils.EmbyServers[ServerId].library.removed([EmbyId])
        xbmc.executebuiltin("Container.Refresh()")

def watchtogether():
    EmbyId, ServerId, _ = load_item()

    if not EmbyId:
        return

    playerops.disable_RemoteClients(ServerId)
    playerops.WatchTogether = False
    playerops.RemoteControl = False
    playerops.RemoteMode = False

    if len(playerops.RemoteClientData[ServerId]["SessionIds"]) <= 1:
        add_remoteclients(ServerId)

        if len(playerops.RemoteClientData[ServerId]["SessionIds"]) <= 1:
            return

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
            return

    ProgressBar.close()
    playerops.WatchTogether = True
    playerops.enable_remotemode(ServerId)
    playerops.Unpause()

def delete_remoteclients():
    _, ServerId, _ = load_item()

    if not ServerId:
        return

    SelectionLabels = []
    SessionIds = []

    for RemoteClientSessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
        if RemoteClientSessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            SelectionLabels.append(f"{playerops.RemoteClientData[ServerId]['Devicenames'][RemoteClientSessionId]}, {playerops.RemoteClientData[ServerId]['Usernames'][RemoteClientSessionId]}")
            SessionIds.append(RemoteClientSessionId)

    Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

    if Selections:
        RemoveSessionIds = []

        for Selection in Selections:
            RemoveSessionIds.append(SessionIds[Selection])

        playerops.delete_RemoteClient(ServerId, RemoveSessionIds)

    xbmcgui.Window(10000).setProperty('EmbyRemoteclient', str(playerops.RemoteClientData[ServerId]["SessionIds"] != [utils.EmbyServers[ServerId].EmbySession[0]['Id']]))

def add_remoteclients(ServerId=None):
    if not ServerId:
        _, ServerId, _ = load_item()

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

from urllib.parse import urlencode
import json
from _thread import start_new_thread
import xbmc
from helper import pluginmenu, utils, playerops, xmls, player
from database import dbio
from emby import emby
from . import webservice

PlaylistItemsAdd = ()
PlaylistItemAddThread = False
PlaylistItemsRemove = ()
PlaylistItemRemoveThread = False
QueueItemsStatusupdate = ()
QueryItemStatusThread = False
QueueItemsRemove = ()
QueryItemRemoveThread = False
SettingsChangedThread = False
KodiScanCount = 0
SleepMode = False


class monitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if method == "Playlist.OnAdd":
            globals()["PlaylistItemsAdd"] += (data,)

            if not PlaylistItemAddThread:
                globals()["PlaylistItemAddThread"] = True
                start_new_thread(Playlist_Add, ())
        elif method == "Playlist.OnRemove":
            globals()["PlaylistItemsRemove"] += (data,)

            if not PlaylistItemRemoveThread:
                globals()["PlaylistItemRemoveThread"] = True
                start_new_thread(Playlist_Remove, ())
        elif method == "Playlist.OnClear":
            player.NowPlayingQueue = [[], []]
            player.PlaylistKodiItems = [[], []]
        elif method == "Player.OnPlay":
            player.PlayerEvents.put(("play",))
        elif method == "Player.OnStop":
            player.PlayerEvents.put(("stop", data))
        elif method == 'Player.OnSeek':
            player.PlayerEvents.put(("seek", data))
        elif method == "Player.OnAVChange":
            player.PlayerEvents.put(("avchange",))
        elif method == "Player.OnAVStart":
            player.PlayerEvents.put(("avstart", data))
        elif method == "Player.OnPause":
            player.PlayerEvents.put(("pause",))
        elif method == "Player.OnResume":
            player.PlayerEvents.put(("resume",))
        elif method == 'Application.OnVolumeChanged':
            player.PlayerEvents.put(("volume", data))
        elif method in ('Other.managelibsselection', 'Other.settings', 'Other.backup', 'Other.restore', 'Other.reset_device_id', 'Other.factoryreset', 'Other.databasereset', 'Other.nodesreset', 'Other.texturecache', 'System.OnWake', 'System.OnSleep', 'System.OnQuit', 'Other.play', 'Other.skinreload', 'Other.databasevacuummanual', 'Other.manageserver'):
            start_new_thread(Notification, (method, data))
        elif method == 'VideoLibrary.OnUpdate' and not playerops.RemoteMode:  # Buffer updated items -> not overloading threads
            globals()["QueueItemsStatusupdate"] += (data,)

            if not QueryItemStatusThread:
                globals()["QueryItemStatusThread"] = True
                pluginmenu.reset_querycache() # Clear Cache
                start_new_thread(VideoLibrary_OnUpdate, ())
        elif method == 'VideoLibrary.OnRemove' and not playerops.RemoteMode:  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                globals()["QueueItemsRemove"] += (data,)

                if not QueryItemRemoveThread:
                    globals()["QueryItemRemoveThread"] = True
                    start_new_thread(VideoLibrary_OnRemove, ())

    def onScanStarted(self, library):
        if playerops.RemoteMode:
            xbmc.log(f"EMBY.hooks.monitor: kodi scan skipped due to remote mode / {library}", 1) # LOGINFO
            return

        utils.SyncPause['kodi_rw'] = True
        globals()["KodiScanCount"] += 1
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi scan / {library} / {utils.WidgetRefresh} ]", 1) # LOGINFO

    def onScanFinished(self, library):
        if playerops.RemoteMode:
            xbmc.log(f"EMBY.hooks.monitor: kodi scan skipped due to remote mode / {library} ", 1) # LOGINFO
            utils.SyncPause['kodi_rw'] = False
            globals()["KodiScanCount"] = 0
            return

        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi scan / {library} / {utils.WidgetRefresh} ]", 1) # LOGINFO
        globals()["KodiScanCount"] -= 1

        if KodiScanCount > 0: # use > 0 in case the start event was not detected
            return

        globals()["KodiScanCount"] = 0

        if utils.WidgetRefresh:
            if library == "video":
                xbmc.log(f"EMBY.hooks.monitor: [ kodi scan / {library} ] Trigger music scan", 1) # LOGINFO
                utils.SendJson('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":"widget_refresh_trigger"},"id":1}')
                return

            utils.WidgetRefresh = False

        utils.SyncPause['kodi_rw'] = False
        start_new_thread(syncEmby, ())

    def onCleanStarted(self, library):
        if playerops.RemoteMode:
            xbmc.log(f"EMBY.hooks.monitor: kodi scan skipped due to remote mode / {library} ", 1) # LOGINFO
            return

        utils.SyncPause['kodi_rw'] = True
        globals()["KodiScanCount"] += 1
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi clean / {library} ]", 1) # LOGINFO

    def onCleanFinished(self, library):
        if playerops.RemoteMode:
            xbmc.log(f"EMBY.hooks.monitor: kodi scan skipped due to remote mode / {library} ", 1) # LOGINFO
            return

        globals()["KodiScanCount"] -= 1

        if KodiScanCount > 0: # use > 0 in case the start event was not detected
            return

        globals()["KodiScanCount"] = 0
        utils.SyncPause['kodi_rw'] = False
        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi clean / {library} ]", 1) # LOGINFO

    def onSettingsChanged(self):
        # delay settings changed updated
        if not SettingsChangedThread:
            globals()["SettingsChangedThread"] = True
            start_new_thread(settingschanged, ())
        else:
            xbmc.log("EMBY.hooks.monitor: [ Reload settings skip ]", 1) # LOGINFO

def Notification(method, data):  # threaded by caller
    xbmc.log(f"EMBY.hooks.monitor: THREAD: --->[ notification ] {method}", 0) # LOGDEBUG

    if method == 'Other.managelibsselection':
        pluginmenu.select_managelibs()
    elif method == 'Other.settings':
        xbmc.executebuiltin(f'Addon.OpenSettings({utils.PluginId})')
    elif method == 'Other.backup':
        Backup()
    elif method == 'Other.restore':
        BackupRestore()
    elif method == 'Other.skinreload':
        pluginmenu.reset_querycache() # Clear Cache
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.log("EMBY.hooks.monitor: Reload skin by notification", 1) # LOGINFO
    elif method == 'Other.reset_device_id':
        pluginmenu.reset_device_id()
    elif method == 'Other.manageserver':
        pluginmenu.manage_servers(ServerConnect)
    elif method == 'Other.databasereset':
        pluginmenu.databasereset()
    elif method == 'Other.nodesreset':
        utils.nodesreset()
    elif method == 'Other.factoryreset':
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
            pluginmenu.factoryreset()
    elif method == 'Other.texturecache':
        if not utils.artworkcacheenable:
            utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
        else:
            pluginmenu.cache_textures()
    elif method == 'System.OnWake':
        System_OnWake()
    elif method == 'System.OnSleep':
        System_OnSleep()
    elif method == 'System.OnQuit':
        System_OnQuit()
    elif method == 'Other.play':
        data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
        playerops.PlayEmby((data[1],), "PlayNow", 0, -1, utils.EmbyServers[data[0]], 0)
    elif method == 'Other.databasevacuummanual':
        dbio.DBVacuum()

    xbmc.log(f"EMBY.hooks.monitor: THREAD: ---<[ notification ] {method}", 0) # LOGDEBUG

def System_OnWake():
    if not SleepMode:
        xbmc.log("EMBY.hooks.monitor: System.OnSleep was never called, skip System.OnWake", 2) # LOGWARNING
        return

    xbmc.log("EMBY.hooks.monitor: --<[ sleep ]", 1) # LOGINFO
    globals()["SleepMode"] = False
    EmbyServer_ReconnectAll()
    webservice.start()
    utils.SyncPause['kodi_sleep'] = False

def System_OnSleep():
    if SleepMode:
        xbmc.log("EMBY.hooks.monitor: System.OnSleep in progress, skip System.OnSleep", 2) # LOGWARNING
        return

    xbmc.log("EMBY.hooks.monitor: -->[ sleep ]", 1) # LOGINFO
    utils.SyncPause['kodi_sleep'] = True
    webservice.close()
    globals()["SleepMode"] = True

# Remove Items
def VideoLibrary_OnRemove(): # Cache queries to minimize database openings
    if utils.sleep(0.5):
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnRemove ]", 1) # LOGINFO
    RemoveItems = QueueItemsRemove
    globals().update({"QueueItemsRemove": (), "QueryItemRemoveThread": False})

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33264)):
        for server_id, EmbyServer in list(utils.EmbyServers.items()):
            embydb = dbio.DBOpenRO(server_id, "VideoLibrary_OnRemove")

            for RemoveItem in RemoveItems:
                data = json.loads(RemoveItem)

                if 'item' in data:
                    kodi_id = data['item']['id']
                    media = data['item']['type']
                else:
                    kodi_id = data['id']
                    media = data['type']

                if media in ("tvshow", "season"):
                    continue

                items = embydb.get_item_by_KodiId_KodiType(kodi_id, media)

                if not items:
                    continue

                for item in items:
                    EmbyServer.API.delete_item(item[0])

            dbio.DBCloseRO(server_id, "VideoLibrary_OnRemove")

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnRemove ]", 1) # LOGINFO

def Playlist_Add():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Playlist_Add ]", 1) # LOGINFO
    UpdateItems = PlaylistItemsAdd
    globals().update({"PlaylistItemsAdd": (), "PlaylistItemAddThread": False})
    UpdateItemsPlaylist = [(), (), ()]
    PlaylistItemsNew = [{}, {}, {}]

    for UpdateItem in UpdateItems:
        data = json.loads(UpdateItem)

        if 'item' not in data or 'id' not in data['item']:
            UpdateItemsPlaylist[data['playlistid']] += ((data['position'], 0, ""),)
            continue

        UpdateItemsPlaylist[data['playlistid']] += ((data['position'], data['item']['id'], data['item']['type']),)

    for ServerId in utils.EmbyServers:
        if len(PlaylistItemsNew[0]) == len(UpdateItemsPlaylist[0]) and len(PlaylistItemsNew[1]) == len(UpdateItemsPlaylist[1]): # All items already loaded, no need to check additional Emby servers
            break

        embydb = dbio.DBOpenRO(ServerId, "Playlist_Add")

        for PlaylistIndex in range(2):
            for UpdateItemPlaylist in UpdateItemsPlaylist[PlaylistIndex]:
                if UpdateItemPlaylist in PlaylistItemsNew[PlaylistIndex] and PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]]: # Already loaded by other Emby Server (MultiServer)
                    continue

                if not UpdateItemPlaylist[1]:
                    PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]] = 0 # No Emby server Item
                    continue

                if UpdateItemPlaylist[1] > 1000000000: # Update dynamic item
                    EmbyId = UpdateItemPlaylist[1] - 1000000000
                else:
                    Item = embydb.get_item_by_KodiId_KodiType(UpdateItemPlaylist[1], UpdateItemPlaylist[2])

                    if not Item:
                        PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]] = 0 # No Emby server Item
                        continue

                    EmbyId = Item[0][0]

                PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]] = EmbyId

        dbio.DBCloseRO(ServerId, "Playlist_Add")

    # Sort playlist
    for PlaylistIndex in range(2):
        for Position, EmbyId in list(PlaylistItemsNew[PlaylistIndex].items()):
            player.PlaylistKodiItems[PlaylistIndex].insert(Position, EmbyId)

    player.build_NowPlayingQueue()
    player.PlayerEvents.put(("playlistupdate",))
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Playlist_Add ]", 1) # LOGINFO

def Playlist_Remove():
    if utils.sleep(0.5): # Cache queries
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Playlist_Remove ]", 1) # LOGINFO
    UpdateItems = PlaylistItemsRemove
    globals().update({"PlaylistItemsRemove": (), "PlaylistItemRemoveThread": False})
    RemovedItemsPlaylist = [[], []]

    for UpdateItem in UpdateItems:
        data = json.loads(UpdateItem)
        RemovedItemsPlaylist[data['playlistid']].append(data['position'])

    for PlaylistIndex in range(2):
        for RemovedItemPlaylist in reversed(RemovedItemsPlaylist[PlaylistIndex]):
            del player.PlaylistKodiItems[PlaylistIndex][RemovedItemPlaylist]

    player.build_NowPlayingQueue()
    player.PlayerEvents.put(("playlistupdate",))
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Playlist_Remove ]", 1) # LOGINFO

# Mark as watched/unwatched updates
def VideoLibrary_OnUpdate():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnUpdate ]", 1) # LOGINFO
    UpdateItems = QueueItemsStatusupdate
    globals().update({"QueueItemsStatusupdate": (), "QueryItemStatusThread": False})
    ItemsSkipUpdateRemove = []
    items = ()

    for server_id, EmbyServer in list(utils.EmbyServers.items()):
        EmbyUpdateItems = {}
        embydb = None
        EmbyId = ""

        for UpdateItem in UpdateItems:
            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate process item: {UpdateItem}", 1) # LOGINFO
            data = json.loads(UpdateItem)

            # Update dynamic item
            EmbyId = ""
            media = ""

            if 'item' in data:
                ItemId = int(data['item']['id'])

                if ItemId > 1000000000:
                    EmbyId = ItemId - 1000000000
                    media = data['item']['type']
            else:
                ItemId = int(data['id'])

                if ItemId > 1000000000:
                    EmbyId = ItemId - 1000000000
                    media = data['type']

            if EmbyId:
                xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate dynamic item detected: {EmbyId}", 1) # LOGINFO
                items = ((EmbyId,),)

                if pluginmenu.DynamicNodeServerId != server_id:
                    continue

            # Update synced item
            if not EmbyId:
                if 'item' in data:
                    kodi_id = data['item']['id']
                    media = data['item']['type']
                else:
                    kodi_id = data['id']
                    media = data['type']

                if not embydb:
                    embydb = dbio.DBOpenRO(server_id, "VideoLibrary_OnUpdate")

                items = embydb.get_item_by_KodiId_KodiType(kodi_id, media)

            if not items:
                continue

            # detect multiversion EmbyId
            UpdateItemsFiltered = []

            for item in items:
                if f"KODI{item[0]}" in playerops.ItemSkipUpdate:
                    UpdateItemsFiltered.append(item)
                    break

            if not UpdateItemsFiltered:
                UpdateItemsFiltered = items

            for UpdateItemFiltered in UpdateItemsFiltered:
                if int(UpdateItemFiltered[0]) not in ItemsSkipUpdateRemove:
                    ItemsSkipUpdateRemove.append(int(UpdateItemFiltered[0]))

                if 'item' in data and 'playcount' in data:
                    if media in ("tvshow", "season"):
                        xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {media} / {UpdateItemFiltered[0]} ]", 1) # LOGINFO
                        continue

                    if f"KODI{UpdateItemFiltered[0]}" not in playerops.ItemSkipUpdate:  # Check EmbyID
                        xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate update playcount {UpdateItemFiltered[0]} ]", 1) # LOGINFO

                        if int(UpdateItemFiltered[0]) in EmbyUpdateItems:
                            EmbyUpdateItems[int(UpdateItemFiltered[0])]['PlayCount'] = data['playcount']
                            EmbyUpdateItems[int(UpdateItemFiltered[0])]['EmbyItem'] = UpdateItemFiltered
                        else:
                            EmbyUpdateItems[int(UpdateItemFiltered[0])] = {'PlayCount': data['playcount'], 'EmbyItem': UpdateItemFiltered}
                    else:
                        xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {UpdateItemFiltered[0]} ]", 1) # LOGINFO
                else:
                    if 'item' not in data:
                        if f"KODI{UpdateItemFiltered[0]}" not in playerops.ItemSkipUpdate and int(UpdateItemFiltered[0]):  # Check EmbyID
                            if not f"{{'item':{UpdateItem}}}" in UpdateItems:
                                xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate reset progress {UpdateItemFiltered[0]} ]", 1) # LOGINFO

                                if int(UpdateItemFiltered[0]) in EmbyUpdateItems:
                                    EmbyUpdateItems[int(UpdateItemFiltered[0])]['Progress'] = 0
                                    EmbyUpdateItems[int(UpdateItemFiltered[0])]['EmbyItem'] = UpdateItemFiltered
                                else:
                                    EmbyUpdateItems[int(UpdateItemFiltered[0])] = {'Progress': 0, 'EmbyItem': UpdateItemFiltered}
                            else:
                                xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (UpdateItems) {UpdateItemFiltered[0]}", 1) # LOGINFO
                        else:
                            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (ItemSkipUpdate) {UpdateItemFiltered[0]}", 1) # LOGINFO

        for EmbyItemId, EmbyUpdateItem in list(EmbyUpdateItems.items()):
            playerops.ItemSkipUpdate.append(f"KODI{EmbyItemId}")

            if 'Progress' in EmbyUpdateItem:
                if 'PlayCount' in EmbyUpdateItem:
                    EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], EmbyUpdateItem['PlayCount'])
                else:
                    if not EmbyId:
                        kodidb = dbio.DBOpenRO("video", "VideoLibrary_OnUpdate")
                        PlayCount = kodidb.get_playcount(EmbyUpdateItem['EmbyItem'][5])
                        dbio.DBCloseRO("video", "VideoLibrary_OnUpdate")
                    else:
                        PlayCount = -1

                    EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], PlayCount)
            else:
                EmbyServer.API.set_played(EmbyItemId, EmbyUpdateItem['PlayCount'])

        if embydb:
            dbio.DBCloseRO(server_id, "VideoLibrary_OnUpdate")

    for ItemSkipUpdateRemove in ItemsSkipUpdateRemove:
        ItemSkipUpdateRemoveCompare = f"KODI{ItemSkipUpdateRemove}"

        if ItemSkipUpdateRemoveCompare in playerops.ItemSkipUpdate:
            playerops.ItemSkipUpdate.remove(ItemSkipUpdateRemoveCompare)

    xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate ItemSkipUpdate: {playerops.ItemSkipUpdate}", 1) # LOGINFO
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnUpdate ]", 1) # LOGINFO

def BackupRestore():
    RestoreFolder = utils.Dialog.browseSingle(type=0, heading='Select Backup', shares='files', defaultt=utils.backupPath)
    MinVersionPath = f"{RestoreFolder}minimumversion.txt"

    if not utils.checkFileExists(MinVersionPath):
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33224), sound=False)
        return

    BackupVersion = utils.readFileString(MinVersionPath)

    if BackupVersion != utils.MinimumVersion:
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33225), sound=False)
        return

    _, files = utils.listDir(utils.FolderAddonUserdata)

    for Filename in files:
        utils.delFile(f"{utils.FolderAddonUserdata}{Filename}")

    # delete database
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby') or Filename.startswith('My'):
            utils.delFile(f"special://profile/Database/{Filename}")

    utils.delete_playlists()
    utils.delete_nodes()
    RestoreFolderAddonData = f"{RestoreFolder}/addon_data/{utils.PluginId}/"
    utils.copytree(RestoreFolderAddonData, utils.FolderAddonUserdata)
    RestoreFolderDatabase = f"{RestoreFolder}/Database/"
    utils.copytree(RestoreFolderDatabase, "special://profile/Database/")
    utils.restart_kodi()

# Emby backup
def Backup():
    if not utils.backupPath:
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33229), sound=False)
        return None

    path = utils.backupPath
    folder_name = f"Kodi{xbmc.getInfoLabel('System.BuildVersion')[:2]} - {xbmc.getInfoLabel('System.Date(yyyy-mm-dd)')}-{xbmc.getInfoLabel('System.Time(hh:mm:ss xx)')}"
    folder_name = utils.Dialog.input(heading=utils.Translate(33089), defaultt=folder_name)

    if not folder_name:
        return None

    backup = f"{path}{folder_name}/"

    if utils.checkFolderExists(backup):
        if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33090)):
            return Backup()

        utils.delFolder(backup)

    destination_data = f"{backup}addon_data/{utils.PluginId}/"
    destination_databases = f"{backup}Database/"
    utils.mkDir(backup)
    utils.mkDir(f"{backup}addon_data/")
    utils.mkDir(destination_data)
    utils.mkDir(destination_databases)
    utils.copytree(utils.FolderAddonUserdata, destination_data)
    _, files = utils.listDir("special://profile/Database/")

    for Temp in files:
        if 'MyVideos' in Temp or 'emby' in Temp or 'MyMusic' in Temp:
            utils.copyFile(f"special://profile/Database/{Temp}", f"{destination_databases}/{Temp}")
            xbmc.log(f"EMBY.hooks.monitor: Copied {Temp}", 1) # LOGINFO

    utils.writeFileString(f"{backup}minimumversion.txt", utils.MinimumVersion)
    xbmc.log("EMBY.hooks.monitor: backup completed", 1) # LOGINFO
    utils.Dialog.ok(heading=utils.addon_name, message=f"{utils.Translate(33091)} {backup}")
    return None

def ServerConnect(ServerSettings):
    EmbyServerObj = emby.EmbyServer(ServerSettings)
    EmbyServerObj.ServerInitConnection()

def EmbyServer_ReconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.ServerReconnect()

def EmbyServer_DisconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.stop()

def settingschanged():  # threaded by caller
    if utils.sleep(0.5):
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ reload settings ]", 1) # LOGINFO
    globals()["SettingsChangedThread"] = False
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    RestartKodi = False
    syncdatePrevious = utils.syncdate
    synctimePrevious = utils.synctime
    disablehttp2Previous = utils.disablehttp2
    xspplaylistsPreviousValue = utils.xspplaylists
    enableCoverArtPreviousValue = utils.enableCoverArt
    maxnodeitemsPreviousValue = utils.maxnodeitems
    AddonModePathPreviousValue = utils.AddonModePath
    websocketenabledPreviousValue = utils.websocketenabled
    utils.InitSettings()

    # Http2 mode changed, rebuild advanced settings -> restart Kodi
    if disablehttp2Previous != utils.disablehttp2:
        if xmls.advanced_settings():
            RestartKodi = True

    # path(substitution) changed, update database pathes
    if AddonModePathPreviousValue != utils.AddonModePath:
        videodb = dbio.DBOpenRW("video", "settingschanged")
        videodb.toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("video", "settingschanged")
        musicdb = dbio.DBOpenRW("music", "settingschanged")
        musicdb.toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("music", "settingschanged")
        utils.refresh_widgets()

    # Toggle coverart setting
    if enableCoverArtPreviousValue != utils.enableCoverArt:
        DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message="Changing artwork requires an artwork cache reset. Proceed?")

        if DelArtwork:
            RestartKodi = True
            pluginmenu.DeleteThumbnails()
        else:
            utils.set_settings_bool("enableCoverArt", enableCoverArtPreviousValue)


    # Toggle node items limit
    if maxnodeitemsPreviousValue != utils.maxnodeitems:
        utils.nodesreset()

    # Toggle websocket connection
    if websocketenabledPreviousValue != utils.websocketenabled:
        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.toggle_websocket(utils.websocketenabled)

    # Restart Kodi
    if RestartKodi:
        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        utils.restart_kodi()
        xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ reload settings ] restart", 1) # LOGINFO
        return

    # Manual adjusted sync time/date
    if syncdatePrevious != utils.syncdate or synctimePrevious != utils.synctime:
        xbmc.log("EMBY.hooks.monitor: [ Trigger KodiStartSync due to setting changed ]", 1) # LOGINFO
        SyncTimestamp = f"{utils.syncdate} {utils.synctime}:00"
        SyncTimestamp = utils.convert_to_gmt(SyncTimestamp)

        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.library.set_syncdate(SyncTimestamp)
            start_new_thread(EmbyServer.library.KodiStartSync, (False,))

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.API.update_settings()

    # Toggle xsp playlists
    if xspplaylistsPreviousValue != utils.xspplaylists:
        if utils.xspplaylists:
            for EmbyServer in list(utils.EmbyServers.values()):
                EmbyServer.Views.update_nodes()
        else:
            # delete playlists
            for playlistfolder in ['special://profile/playlists/video/', 'special://profile/playlists/music/']:
                if utils.checkFolderExists(playlistfolder):
                    _, files = utils.listDir(playlistfolder)

                    for Filename in files:
                        utils.delFile(f"{playlistfolder}{Filename}")

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ reload settings ]", 1) # LOGINFO

def System_OnQuit():
    xbmc.log("EMBY.hooks.monitor: System_OnQuit", 1) # LOGINFO
    utils.SystemShutdown = True
    utils.SyncPause = {}
    webservice.close()
    EmbyServer_DisconnectAll()

def ServersConnect():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ ServersConnect ]", 1) # LOGINFO

    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            utils.SyncPause = {}
            xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ] shutdown", 1) # LOGINFO
            return

    _, files = utils.listDir(utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in files:
        if Filename.startswith('server'):
            ServersSettings.append(f"{utils.FolderAddonUserdata}{Filename}")

    if not utils.WizardCompleted:  # First run
        utils.set_settings_bool('WizardCompleted', True)
        ServerConnect(None)
    else:
        for ServerSettings in ServersSettings:
            ServerConnect(ServerSettings)

    if utils.refreshskin:
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.log("EMBY.hooks.webservice: Reload skin on connection established", xbmc.LOGINFO)
    else:
        xbmc.log("EMBY.hooks.webservice: widget refresh: connection established", xbmc.LOGINFO) # reload artwork/images
        utils.refresh_widgets()

    utils.PluginStarted = True
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ]", 1) # LOGINFO

def syncEmby():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ syncEmby ]", 1) # LOGINFO

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.library.RunJobs()

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ syncEmby ]", 1) # LOGINFO

def setup():
    # Detect corupted setting file
    if not xmls.verify_settings_file():
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33427))
        utils.delFile(f"{utils.FolderAddonUserdata}settings.xml")

        if utils.sleep(5):
            return False

        return False

    # copy default nodes
    utils.mkDir("special://profile/library/video/")
    utils.mkDir("special://profile/library/music/")
    utils.copytree("special://xbmc/system/library/video/", "special://profile/library/video/")
    utils.copytree("special://xbmc/system/library/music/", "special://profile/library/music/")

    # add favorite emby nodes
    index = 0

    for FavNode in [{'Name': utils.Translate(30180), 'Tag': "Favorite movies", 'MediaType': "movies"}, {'Name': utils.Translate(30181), 'Tag': "Favorite tvshows", 'MediaType': "tvshows"}, {'Name': utils.Translate(30182), 'Tag': "Favorite episodes", 'MediaType': "episodes"}, {'Name': "Favorite musicvideos", 'Tag': "Favorite musicvideos", 'MediaType': "musicvideos"}]:
        index += 1
        filepath = f"special://profile/library/video/emby_{FavNode['Tag'].replace(' ', '_')}.xml"

        if not utils.checkFileExists(filepath):
            utils.mkDir("special://profile/library/video/")
            Data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'

            if FavNode['MediaType'] == 'episodes':
                Data += f'<node order="{index}" type="folder">\n'.encode("utf-8")
            else:
                Data += f'<node order="{index}" type="filter">\n'.encode("utf-8")

            Data += b'    <icon>DefaultFavourites.png</icon>\n'
            Data += f'    <label>EMBY: {FavNode["Name"]}</label>\n'.encode("utf-8")
            Data += f'    <content>{FavNode["MediaType"]}</content>\n'.encode("utf-8")

            if FavNode['MediaType'] == 'episodes':
                params = {'mode': "favepisodes"}
                Data += f'    <path>plugin://{utils.PluginId}/?{urlencode(params)}"</path>\n'.encode("utf-8")
            else:
                Data += b'    <match>all</match>\n'
                Data += b'    <rule field="tag" operator="is">\n'
                Data += f'        <value>{FavNode["Tag"]}</value>\n'.encode("utf-8")
                Data += b'    </rule>\n'

            Data += b'</node>'
            utils.writeFileBinary(filepath, Data)
        else:
            xbmc.log(f"EMBY.hooks.monitor: Favorite node exists, skip: {filepath}", 1) # LOGINFO

    # verify sources.xml
    xmls.sources()

    # verify advancedsettings.xml
    if xmls.advanced_settings():
        return False

    if utils.MinimumSetup == utils.MinimumVersion:
        return True

    xbmc.executebuiltin('ReplaceWindow(10000)', True)
    utils.refreshskin = False

    # Clean installation
    if not utils.MinimumSetup:
        value = utils.Dialog.yesno(heading=utils.Translate(30511), message=utils.Translate(33035), nolabel=utils.Translate(33036), yeslabel=utils.Translate(33037))

        if value:
            utils.set_settings_bool('useDirectPaths', True)
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33145))
        else:
            utils.set_settings_bool('useDirectPaths', False)

        xbmc.log(f"EMBY.hooks.monitor: Add-on playback: {utils.useDirectPaths == '0'}", 1) # LOGINFO
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return True

    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33222)): # final warning
        return "stop"

    utils.set_settings('MinimumSetup', utils.MinimumVersion)
    pluginmenu.factoryreset()
    return False

def StartUp():
    xbmc.log("EMBY.hooks.monitor: [ Start Emby-next-gen ]", 1) # LOGINFO
    webservice.init_additional_modules()
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        webservice.close()
        xbmc.log("EMBY.hooks.monitor: [ DB upgrade declined, Shutdown Emby-next-gen ]", 3) # LOGERROR
    elif not Ret:  # db reset required
        xbmc.log("EMBY.hooks.monitor: [ DB reset required, Kodi restart ]", 2) # LOGWARNING
        webservice.close()
        utils.restart_kodi()
    else:  # Regular start
        start_new_thread(ServersConnect, ())

        # Waiting/blocking function till Kodi stops
        xbmc.log("EMBY.hooks.monitor: Monitor listening", 1) # LOGINFO
        XbmcMonitor = monitor()  # Init Monitor
        XbmcMonitor.waitForAbort(0)

        # Shutdown
        player.stop_playback(False, False)

        for RemoteCommandQueue in list(playerops.RemoteCommandQueue.values()):
            RemoteCommandQueue.put(("QUIT",))

        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        xbmc.log("EMBY.hooks.monitor: [ Shutdown Emby-next-gen ]", 2) # LOGWARNING

    player.PlayerEvents.put(("QUIT",))
    utils.XbmcPlayer = None
    utils.SystemShutdown = True

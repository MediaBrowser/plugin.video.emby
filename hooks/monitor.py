import json
from _thread import start_new_thread
import xbmc
from helper import pluginmenu, utils, playerops, xmls, loghandler
from database import dbio
from emby import emby
from . import player, webservice

PatchFiles = {"script-emby-connect-login-manual.xml", "script-emby-connect-login.xml", "script-emby-connect-server.xml", "script-emby-connect-server-manual.xml", "script-emby-connect-users.xml"}
LOG = loghandler.LOG('EMBY.hooks.monitor')

class monitor(xbmc.Monitor):
    def __init__(self):
        webservice.start()
        self.QueueItemsStatusupdate = ()
        self.QueryItemStatusThread = False
        self.QueueItemsRemove = ()
        self.QueryItemRemoveThread = False
        self.KodiScanCount = 0
        self.sleep = False

    def onNotification(self, sender, method, data):
         # Skip unsupported notifications -> e.g. "Playlist.OnAdd" floats threading! -> Never let that happen
        if method == 'VideoLibrary.OnUpdate':  # Buffer updated items -> not overloading threads
            self.QueueItemsStatusupdate += (data,)

            if not self.QueryItemStatusThread:
                self.QueryItemStatusThread = True
                start_new_thread(self.VideoLibrary_OnUpdate, ())
        elif method == 'VideoLibrary.OnRemove':  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                self.QueueItemsRemove += (data,)

                if not self.QueryItemRemoveThread:
                    self.QueryItemRemoveThread = True
                    start_new_thread(self.VideoLibrary_OnRemove, ())
        elif method in ('Other.managelibsselection', 'Other.settings', 'Other.backup', 'Other.restore', 'Other.reset_device_id', 'Other.addserver', 'Other.adduserselection', 'Other.factoryreset', 'Other.databasereset', 'Other.nodesreset', 'Other.texturecache', 'System.OnWake', 'System.OnSleep', 'System.OnQuit', 'Application.OnVolumeChanged', 'Other.play', 'Other.skinreload', 'Other.databasevacuummanual'):
            start_new_thread(self.Notification, (method, data))

    def Notification(self, method, data):  # threaded by caller
        if method == 'Other.managelibsselection':
            pluginmenu.select_managelibs()
        elif method == 'Other.settings':
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
        elif method == 'Other.backup':
            Backup()
        elif method == 'Other.restore':
            BackupRestore()
        elif method == 'Other.skinreload':
            xbmc.executebuiltin('ReloadSkin()')
            LOG.info("Reload skin")
        elif method == 'Other.reset_device_id':
            pluginmenu.reset_device_id()
        elif method == 'Other.addserver':
            ServerConnect(None)
        elif method == 'Other.adduserselection':
            pluginmenu.select_adduser()
        elif method == 'Other.databasereset':
            pluginmenu.databasereset()
        elif method == 'Other.nodesreset':
            pluginmenu.nodesreset()
        elif method == 'Other.factoryreset':
            if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
                pluginmenu.factoryreset()
        elif method == 'Other.texturecache':
            if not utils.artworkcacheenable:
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
            else:
                pluginmenu.cache_textures()
        elif method == 'System.OnWake':
            self.System_OnWake()
        elif method == 'System.OnSleep':
            self.System_OnSleep()
        elif method == 'System.OnQuit':
            System_OnQuit()
        elif method == 'Application.OnVolumeChanged':
            player.Player.SETVolume(data)
        elif method == 'Other.play':
            data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
            playerops.Play((data[1],), "PlayNow", -1, -1, utils.EmbyServers[data[0]])
        elif method == 'Other.databasevacuummanual':
            dbio.DBVacuum()

    def onScanStarted(self, library):
        utils.SyncPause['kodi_rw'] = True
        self.KodiScanCount += 1
        LOG.info("-->[ kodi scan/%s ]" % library)

    def onScanFinished(self, library):
        LOG.info("--<[ kodi scan/%s ]" % library)
        self.KodiScanCount -= 1

        if self.KodiScanCount:
            return

        if utils.ScanStaggered:
            utils.ScanStaggered = False
            LOG.info("[ kodi scan/%s ] Trigger music scan" % library)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":""},"id":1}')
            return

        if utils.ScanReloadSkin:
            utils.ScanReloadSkin = False
            LOG.info("[ kodi scan/%s ] Reload skin" % library)
            xbmc.executebuiltin('ReloadSkin()')

        utils.SyncPause['kodi_rw'] = False

    def onCleanStarted(self, library):
        utils.SyncPause['kodi_rw'] = True
        self.KodiScanCount += 1
        LOG.info("-->[ kodi clean/%s ]" % library)

    def onCleanFinished(self, library):
        self.KodiScanCount -= 1

        if not self.KodiScanCount:
            utils.SyncPause['kodi_rw'] = False

        LOG.info("--<[ kodi clean/%s ]" % library)

    def onSettingsChanged(self):
        start_new_thread(settingschanged, ())

    def System_OnWake(self):
        if not self.sleep:
            LOG.warning("System.OnSleep was never called, skip System.OnWake")
            return

        LOG.info("--<[ sleep ]")
        self.sleep = False
        EmbyServer_ReconnectAll()
        webservice.start()
        utils.SyncPause['kodi_sleep'] = False

    def System_OnSleep(self):
        if self.sleep:
            LOG.warning("System.OnSleep in progress, skip System.OnSleep")
            return

        LOG.info("-->[ sleep ]")
        utils.SyncPause['kodi_sleep'] = True
        webservice.close()
        self.sleep = True

    # Remove Items
    def VideoLibrary_OnRemove(self):
        if utils.sleep(0.5):
            return

        RemoveItems = self.QueueItemsRemove
        self.QueueItemsRemove = ()
        self.QueryItemRemoveThread = False

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

    # Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self):
        if utils.sleep(0.5):
            return

        UpdateItems = self.QueueItemsStatusupdate
        self.QueueItemsStatusupdate = ()
        self.QueryItemStatusThread = False
        ItemsSkipUpdateRemove = []

        for server_id, EmbyServer in list(utils.EmbyServers.items()):
            EmbyUpdateItems = {}
            embydb = dbio.DBOpenRO(server_id, "VideoLibrary_OnUpdate")

            for UpdateItem in UpdateItems:
                data = json.loads(UpdateItem)

                if 'item' in data:
                    kodi_id = data['item']['id']
                    media = data['item']['type']
                else:
                    kodi_id = data['id']
                    media = data['type']

                items = embydb.get_item_by_KodiId_KodiType(kodi_id, media)

                if not items:
                    continue

                # detect multiversion EmbyId
                UpdateItemsFiltered = []

                for item in items:
                    if int(item[0]) in player.Player.ItemSkipUpdate:
                        UpdateItemsFiltered.append(item)
                        break

                if not UpdateItemsFiltered:
                    UpdateItemsFiltered = items

                for UpdateItemFiltered in UpdateItemsFiltered:
                    if int(UpdateItemFiltered[0]) not in ItemsSkipUpdateRemove:
                        ItemsSkipUpdateRemove.append(int(UpdateItemFiltered[0]))

                    if 'item' in data and 'playcount' in data:
                        if media in ("tvshow", "season"):
                            LOG.info("[ VideoLibrary_OnUpdate skip playcount %s/%s ]" % (media, UpdateItemFiltered[0]))
                            continue

                        if int(UpdateItemFiltered[0]) not in player.Player.ItemSkipUpdate:  # Check EmbyID
                            LOG.info("[ VideoLibrary_OnUpdate update playcount %s ]" % UpdateItemFiltered[0])

                            if int(UpdateItemFiltered[0]) in EmbyUpdateItems:
                                EmbyUpdateItems[int(UpdateItemFiltered[0])]['PlayCount'] = data['playcount']
                                EmbyUpdateItems[int(UpdateItemFiltered[0])]['EmbyItem'] = UpdateItemFiltered
                            else:
                                EmbyUpdateItems[int(UpdateItemFiltered[0])] = {'PlayCount': data['playcount'], 'EmbyItem': UpdateItemFiltered}
                        else:
                            LOG.info("[ VideoLibrary_OnUpdate skip playcount %s ]" % UpdateItemFiltered[0])
                    else:
                        if 'item' not in data:
                            if int(UpdateItemFiltered[0]) not in player.Player.ItemSkipUpdate:  # Check EmbyID
                                if not '{"item":%s}' % UpdateItem in UpdateItems:
                                    LOG.info("[ VideoLibrary_OnUpdate reset progress %s ]" % UpdateItemFiltered[0])

                                    if int(UpdateItemFiltered[0]) in EmbyUpdateItems:
                                        EmbyUpdateItems[int(UpdateItemFiltered[0])]['Progress'] = 0
                                        EmbyUpdateItems[int(UpdateItemFiltered[0])]['EmbyItem'] = UpdateItemFiltered
                                    else:
                                        EmbyUpdateItems[int(UpdateItemFiltered[0])] = {'Progress': 0, 'EmbyItem': UpdateItemFiltered}
                                else:
                                    LOG.info("VideoLibrary_OnUpdate skip reset progress (UpdateItems) %s" % UpdateItemFiltered[0])
                            else:
                                LOG.info("VideoLibrary_OnUpdate skip reset progress (ItemSkipUpdate) %s" % UpdateItemFiltered[0])

            for EmbyItemId, EmbyUpdateItem in list(EmbyUpdateItems.items()):
                player.Player.ItemSkipUpdate.append(int(EmbyItemId))

                if 'Progress' in EmbyUpdateItem:
                    if 'PlayCount' in EmbyUpdateItem:
                        EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], EmbyUpdateItem['PlayCount'])
                    else:
                        kodidb = dbio.DBOpenRO("video", "VideoLibrary_OnUpdate")
                        PlayCount = kodidb.get_playcount(EmbyUpdateItem['EmbyItem'][5]) # EmbyUpdateItem['EmbyItem'][5] = KodiFileId
                        dbio.DBCloseRO("video", "VideoLibrary_OnUpdate")
                        EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], PlayCount)
                else:
                    EmbyServer.API.set_played(EmbyItemId, EmbyUpdateItem['PlayCount'])

            dbio.DBCloseRO(server_id, "VideoLibrary_OnUpdate")

        for ItemSkipUpdateRemove in ItemsSkipUpdateRemove:
            if ItemSkipUpdateRemove in player.Player.ItemSkipUpdate:
                player.Player.ItemSkipUpdate.remove(ItemSkipUpdateRemove)

        LOG.info("VideoLibrary_OnUpdate ItemSkipUpdate: %s" % str(player.Player.ItemSkipUpdate))
        pluginmenu.reset_episodes_cache()

def BackupRestore():
    RestoreFolder = utils.Dialog.browseSingle(type=0, heading='Select Backup', shares='files', defaultt=utils.backupPath)
    MinVersionPath = "%s%s" % (RestoreFolder, 'minimumversion.txt')

    if not utils.checkFileExists(MinVersionPath):
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33224), sound=False)
        return

    BackupVersion = utils.readFileString(MinVersionPath)

    if BackupVersion != utils.MinimumVersion:
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33225), sound=False)
        return

    _, files = utils.listDir(utils.FolderAddonUserdata)

    for Filename in files:
        utils.delFile("%s%s" % (utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby') or Filename.startswith('My'):
            utils.delFile("special://profile/Database/%s" % Filename)

    utils.delete_playlists()
    utils.delete_nodes()
    RestoreFolderAddonData = "%s/addon_data/%s/" % (RestoreFolder, utils.PluginId)
    utils.copytree(RestoreFolderAddonData, utils.FolderAddonUserdata)
    RestoreFolderDatabase = "%s/Database/" % RestoreFolder
    utils.copytree(RestoreFolderDatabase, "special://profile/Database/")
    xbmc.executebuiltin('RestartApp')

# Emby backup
def Backup():
    if not utils.backupPath:
        utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33229), sound=False)
        return None

    path = utils.backupPath
    folder_name = "Kodi%s - %s-%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2], xbmc.getInfoLabel('System.Date(yyyy-mm-dd)'), xbmc.getInfoLabel('System.Time(hh:mm:ss xx)'))
    folder_name = utils.Dialog.input(heading=utils.Translate(33089), defaultt=folder_name)

    if not folder_name:
        return None

    backup = "%s%s/" % (path, folder_name)

    if utils.checkFolderExists(backup):
        if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33090)):
            return Backup()

        utils.delFolder(backup)

    destination_data = "%saddon_data/%s/" % (backup, utils.PluginId)
    destination_databases = "%sDatabase/" % backup
    utils.mkDir(backup)
    utils.mkDir("%saddon_data/" % backup)
    utils.mkDir(destination_data)
    utils.mkDir(destination_databases)
    utils.copytree(utils.FolderAddonUserdata, destination_data)
    _, files = utils.listDir("special://profile/Database/")

    for Temp in files:
        if 'MyVideos' in Temp:
            utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'emby' in Temp:
            utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'MyMusic' in Temp:
            utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)

    utils.writeFileString("%s%s" % (backup, 'minimumversion.txt'), utils.MinimumVersion)
    LOG.info("backup completed")
    utils.Dialog.ok(heading=utils.addon_name, message="%s %s" % (utils.Translate(33091), backup))
    return None


def EmbyServer_ReconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.ServerReconnect()

def EmbyServer_DisconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.stop()

# Update progress, skip for seasons and series. Just update episodes
def UserDataChanged(server_id, UserDataList, UserId):
    if UserId != utils.EmbyServers[server_id].user_id:
        return

    LOG.info("[ UserDataChanged ] %s" % UserDataList)
    UpdateData = []
    embydb = dbio.DBOpenRO(server_id, "UserDataChanged")

    for ItemData in UserDataList:
        ItemData['ItemId'] = int(ItemData['ItemId'])

        if ItemData['ItemId'] not in player.Player.ItemSkipUpdate:  # Check EmbyID
            e_item = embydb.get_item_by_id(ItemData['ItemId'])

            if e_item:
                if e_item[5] == "Season":
                    LOG.info("[ UserDataChanged skip %s/%s ]" % (e_item[5], ItemData['ItemId']))
                else:
                    UpdateData.append(ItemData)
            else:
                LOG.info("[ UserDataChanged item not found %s ]" % ItemData['ItemId'])
        else:
            LOG.info("UserDataChanged ItemSkipUpdate: %s" % str(player.Player.ItemSkipUpdate))
            LOG.info("[ UserDataChanged skip update/%s ]" % ItemData['ItemId'])
            player.Player.ItemSkipUpdate.remove(ItemData['ItemId'])
            LOG.info("UserDataChanged ItemSkipUpdate: %s" % str(player.Player.ItemSkipUpdate))

    dbio.DBCloseRO(server_id, "UserDataChanged")

    if UpdateData:
        utils.EmbyServers[server_id].library.userdata(UpdateData)

def ServerConnect(ServerSettings):
    EmbyServerObj = emby.EmbyServer(UserDataChanged, ServerSettings)
    server_id, EmbyServer = EmbyServerObj.register()

    if not server_id or server_id == 'cancel' or utils.SystemShutdown:
        LOG.error("EmbyServer Connect error")
        return False

    # disconnect previous Emby server instance on manual reconnect to the same Emby server
    if server_id in utils.EmbyServers:
        LOG.info("Close previous instance after reconnection to same Emby server")
        utils.EmbyServers[server_id].stop()

    utils.EmbyServers[server_id] = EmbyServer
    return True

def settingschanged():  # threaded by caller
    if utils.SkipUpdateSettings:
        utils.SkipUpdateSettings -= 1
        utils.SkipUpdateSettings = max(utils.SkipUpdateSettings, 0)

    if utils.SkipUpdateSettings:
        return

    LOG.info("[ Reload settings ]")
    RestartKodi = False
    syncdatePrevious = utils.syncdate
    synctimePrevious = utils.synctime
    disablehttp2Previous = utils.disablehttp2
    xspplaylistsPreviousValue = utils.xspplaylists
    syncruntimelimitsPreviousValue = utils.syncruntimelimits
    utils.InitSettings()

    # Http2 mode changed, rebuild advanced settings -> restart Kodi
    if disablehttp2Previous != utils.disablehttp2:
        if xmls.advanced_settings():
            RestartKodi = True

    # Toggle runtimelimits setting
    if syncruntimelimitsPreviousValue != utils.syncruntimelimits:
        if xmls.advanced_settings_runtimelimits(None):
            RestartKodi = True

    # Restart Kodi
    if RestartKodi:
        utils.SystemShutdown = True
        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()

        if utils.sleep(5):  # Give Kodi time to complete startup before reset
            return

        xbmc.executebuiltin('RestartApp')
        return

    # Manual adjusted sync time/date
    if syncdatePrevious != utils.syncdate or synctimePrevious != utils.synctime:
        LOG.info("[ Trigger KodiStartSync due to setting changed ]")
        SyncTimestamp = '%s %s:00' % (utils.syncdate, utils.synctime)
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
                        utils.delFile("%s%s" % (playlistfolder, Filename))

def System_OnQuit():
    LOG.warning("---<[ EXITING ]")
    utils.SystemShutdown = True
    utils.SyncPause = {}
    webservice.close()

    for EmbyServer in list(utils.EmbyServers.values()):
        if player.Transcoding:
            EmbyServer.API.close_transcode()

    EmbyServer_DisconnectAll()

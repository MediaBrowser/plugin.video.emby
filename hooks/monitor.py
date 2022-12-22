from urllib.parse import urlencode
import json
from _thread import start_new_thread
import xbmc
from helper import pluginmenu, utils, playerops, xmls, loghandler, player
from database import dbio
from emby import emby
from . import webservice

QueueItemsStatusupdate = ()
QueryItemStatusThread = False
QueueItemsRemove = ()
QueryItemRemoveThread = False
SettingsChangedThread = False
KodiScanCount = 0
SleepMode = False
LOG = loghandler.LOG('EMBY.hooks.monitor')


class monitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
         # Skip unsupported notifications -> e.g. "Playlist.OnAdd" floats threading! -> Never let that happen
        if method in ('Other.managelibsselection', 'Other.settings', 'Other.backup', 'Other.restore', 'Other.reset_device_id', 'Other.factoryreset', 'Other.databasereset', 'Other.nodesreset', 'Other.texturecache', 'System.OnWake', 'System.OnSleep', 'System.OnQuit', 'Application.OnVolumeChanged', 'Other.play', 'Other.skinreload', 'Other.databasevacuummanual', 'Other.manageserver', 'Player.OnPlay', 'Player.OnStop', 'Player.OnAVChange', 'Player.OnSeek', 'Player.OnAVStart', 'Player.OnPause', 'Player.OnResume'):
            start_new_thread(Notification, (method, data))
        elif method == 'VideoLibrary.OnUpdate':  # Buffer updated items -> not overloading threads
            globals()["QueueItemsStatusupdate"] += (data,)

            if not QueryItemStatusThread:
                globals()["QueryItemStatusThread"] = True
                pluginmenu.reset_querycache() # Clear Cache
                start_new_thread(VideoLibrary_OnUpdate, ())
        elif method == 'VideoLibrary.OnRemove':  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                globals()["QueueItemsRemove"] += (data,)

                if not QueryItemRemoveThread:
                    globals()["QueryItemRemoveThread"] = True
                    start_new_thread(VideoLibrary_OnRemove, ())

    def onScanStarted(self, library):
        utils.SyncPause['kodi_rw'] = True
        globals()["KodiScanCount"] += 1
        LOG.info("-->[ kodi scan/%s/%s ]" % (library, utils.WidgetRefresh))

    def onScanFinished(self, library):
        LOG.info("--<[ kodi scan/%s/%s ]" % (library, utils.WidgetRefresh))
        globals()["KodiScanCount"] -= 1

        if KodiScanCount > 0: # use > 0 in case the start event was not detected
            return

        globals()["KodiScanCount"] = 0

        if utils.WidgetRefresh:
            if library == "video":
                LOG.info("[ kodi scan/%s ] Trigger music scan" % library)
                xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":"widget_refresh_trigger"},"id":1}')
                return

            utils.WidgetRefresh = False
        else:
            start_new_thread(syncEmby, ())

        utils.SyncPause['kodi_rw'] = False

    def onCleanStarted(self, library):
        utils.SyncPause['kodi_rw'] = True
        globals()["KodiScanCount"] += 1
        LOG.info("-->[ kodi clean/%s ]" % library)

    def onCleanFinished(self, library):
        globals()["KodiScanCount"] -= 1

        if KodiScanCount > 0: # use > 0 in case the start event was not detected
            return

        globals()["KodiScanCount"] = 0
        utils.SyncPause['kodi_rw'] = False
        LOG.info("--<[ kodi clean/%s ]" % library)

    def onSettingsChanged(self):
        # delay settings changed updated
        if not SettingsChangedThread:
            globals()["SettingsChangedThread"] = True
            start_new_thread(settingschanged, ())
        else:
            LOG.info("[ Reload settings skip ]")

def Notification(method, data):  # threaded by caller
    LOG.debug("THREAD: --->[ notification ] %s" % method)

    if method == "Player.OnPlay":
        player.Play()
    elif method == "Player.OnStop":
        player.Stop(data)
    elif method == "Player.OnAVChange":
        player.AVChange()
    elif method == "Player.OnSeek":
        player.Seek(data)
    elif method == "Player.OnAVStart":
        player.AVStart(data)
    elif method == "Player.OnPause":
        player.Pause()
    elif method == "Player.OnResume":
        player.Resume()
    elif method == 'Other.managelibsselection':
        pluginmenu.select_managelibs()
    elif method == 'Other.settings':
        xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
    elif method == 'Other.backup':
        Backup()
    elif method == 'Other.restore':
        BackupRestore()
    elif method == 'Other.skinreload':
        pluginmenu.reset_querycache() # Clear Cache
        xbmc.executebuiltin('ReloadSkin()')
        LOG.info("Reload skin by notification")
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
    elif method == 'Application.OnVolumeChanged':
        player.SETVolume(data)
    elif method == 'Other.play':
        data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
        playerops.Play((data[1],), "PlayNow", -1, -1, utils.EmbyServers[data[0]])
    elif method == 'Other.databasevacuummanual':
        dbio.DBVacuum()

    LOG.debug("THREAD: ---<[ notification ] %s" % method)

def System_OnWake():
    if not SleepMode:
        LOG.warning("System.OnSleep was never called, skip System.OnWake")
        return

    LOG.info("--<[ sleep ]")
    globals()["SleepMode"] = False
    EmbyServer_ReconnectAll()
    webservice.start()
    utils.SyncPause['kodi_sleep'] = False

def System_OnSleep():
    if SleepMode:
        LOG.warning("System.OnSleep in progress, skip System.OnSleep")
        return

    LOG.info("-->[ sleep ]")
    utils.SyncPause['kodi_sleep'] = True
    webservice.close()
    globals()["SleepMode"] = True

# Remove Items
def VideoLibrary_OnRemove(): # Cache queries to minimize database openings
    if utils.sleep(0.5):
        return

    LOG.info("THREAD: --->[ VideoLibrary_OnRemove ]")
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

    LOG.info("THREAD: ---<[ VideoLibrary_OnRemove ]")

# Mark as watched/unwatched updates
def VideoLibrary_OnUpdate():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    LOG.info("THREAD: --->[ VideoLibrary_OnUpdate ]")
    UpdateItems = QueueItemsStatusupdate
    globals().update({"QueueItemsStatusupdate": (), "QueryItemStatusThread": False})
    ItemsSkipUpdateRemove = []
    items = ()

    for server_id, EmbyServer in list(utils.EmbyServers.items()):
        EmbyUpdateItems = {}
        embydb = None
        EmbyId = ""

        for UpdateItem in UpdateItems:
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
                LOG.info("VideoLibrary_OnUpdate dynamic item detected: %s" % EmbyId)
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
                if int(item[0]) in utils.ItemSkipUpdate:
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

                    if int(UpdateItemFiltered[0]) not in utils.ItemSkipUpdate:  # Check EmbyID
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
                        if int(UpdateItemFiltered[0]) not in utils.ItemSkipUpdate:  # Check EmbyID
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
            utils.ItemSkipUpdate.append(int(EmbyItemId))

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
        if ItemSkipUpdateRemove in utils.ItemSkipUpdate:
            utils.ItemSkipUpdate.remove(ItemSkipUpdateRemove)

    LOG.info("VideoLibrary_OnUpdate ItemSkipUpdate: %s" % str(utils.ItemSkipUpdate))
    LOG.info("THREAD: ---<[ VideoLibrary_OnUpdate ]")

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
    utils.restart_kodi()

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

def ServerConnect(ServerSettings):
    EmbyServerObj = emby.EmbyServer(ServerSettings)
    server_id, EmbyServer = EmbyServerObj.ServerInitConnection()

    if not server_id or server_id == 'cancel' or utils.SystemShutdown:
        LOG.error("EmbyServer Connect error")
        return

    # disconnect previous Emby server instance on manual reconnect to the same Emby server
    if server_id in utils.EmbyServers:
        LOG.info("Close previous instance after reconnection to same Emby server")
        utils.EmbyServers[server_id].stop()

    utils.EmbyServers[server_id] = EmbyServer

def EmbyServer_ReconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.ServerReconnect()

def EmbyServer_DisconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.stop()

def settingschanged():  # threaded by caller
    if utils.sleep(0.5):
        return

    LOG.info("THREAD: --->[ reload settings ]")
    globals()["SettingsChangedThread"] = False
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    RestartKodi = False
    syncdatePrevious = utils.syncdate
    synctimePrevious = utils.synctime
    disablehttp2Previous = utils.disablehttp2
    xspplaylistsPreviousValue = utils.xspplaylists
    enableCoverArtPreviousValue = utils.enableCoverArt
    maxnodeitemsPreviousValue = utils.maxnodeitems
    utils.InitSettings()

    # Http2 mode changed, rebuild advanced settings -> restart Kodi
    if disablehttp2Previous != utils.disablehttp2:
        if xmls.advanced_settings():
            RestartKodi = True

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

    # Restart Kodi
    if RestartKodi:
        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        utils.restart_kodi()
        LOG.info("THREAD: ---<[ reload settings ] restart")
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

    LOG.info("THREAD: ---<[ reload settings ]")

def System_OnQuit():
    LOG.info("System_OnQuit")
    utils.SystemShutdown = True
    utils.SyncPause = {}
    webservice.close()
    EmbyServer_DisconnectAll()

def ServersConnect():
    LOG.info("THREAD: --->[ ServersConnect ]")

    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            utils.SyncPause = {}
            LOG.info("THREAD: ---<[ ServersConnect ] shutdown")
            return

    _, files = utils.listDir(utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in files:
        if Filename.startswith('server'):
            ServersSettings.append("%s%s" % (utils.FolderAddonUserdata, Filename))

    if not utils.WizardCompleted:  # First run
        utils.set_settings_bool('WizardCompleted', True)
        ServerConnect(None)
    else:
        for ServerSettings in ServersSettings:
            ServerConnect(ServerSettings)

    if utils.refreshskin:
        xbmc.executebuiltin('ReloadSkin()')
        xbmc.log("EMBY.hooks.webservice: Reload Skin on connection established", xbmc.LOGINFO)
    else:
        xbmc.log("EMBY.hooks.webservice: Skin refresh: connection established", xbmc.LOGINFO)
        utils.refresh_widgets()

    utils.PluginStarted = True
    LOG.info("THREAD: ---<[ ServersConnect ]")

def syncEmby():
    LOG.info("THREAD: --->[ syncEmby ]")

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.library.RunJobs()

    LOG.info("THREAD: ---<[ syncEmby ]")

def setup():
    # Detect corupted setting file
    if not xmls.verify_settings_file():
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33427))
        utils.delFile("%ssettings.xml" % utils.FolderAddonUserdata)

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
        filepath = "special://profile/library/video/emby_%s.xml" % FavNode['Tag'].replace(" ", "_")

        if not utils.checkFileExists(filepath):
            utils.mkDir("special://profile/library/video/")
            Data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'

            if FavNode['MediaType'] == 'episodes':
                Data += ('<node order="%s" type="folder">\n' % index).encode("utf-8")
            else:
                Data += ('<node order="%s" type="filter">\n' % index).encode("utf-8")

            Data += b'    <icon>DefaultFavourites.png</icon>\n'
            Data += ('    <label>EMBY: %s</label>\n' % FavNode['Name']).encode("utf-8")
            Data += ('    <content>%s</content>\n' % FavNode['MediaType']).encode("utf-8")

            if FavNode['MediaType'] == 'episodes':
                params = {'mode': "favepisodes"}
                Data += ('    <path>plugin://%s/?%s"</path>\n' % (utils.PluginId, urlencode(params))).encode("utf-8")
            else:
                Data += b'    <match>all</match>\n'
                Data += b'    <rule field="tag" operator="is">\n'
                Data += ('        <value>%s</value>\n' % FavNode['Tag']).encode("utf-8")
                Data += b'    </rule>\n'

            Data += b'</node>'
            utils.writeFileBinary(filepath, Data)
        else:
            LOG.info("Favorite node exists, skip: %s" % filepath)

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

        LOG.info("Add-on playback: %s" % utils.useDirectPaths == "0")
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return True

    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33222)): # final warning
        return "stop"

    utils.set_settings('MinimumSetup', utils.MinimumVersion)
    pluginmenu.factoryreset()
    return False

def StartUp():
    LOG.info("[ Start Emby-next-gen ]")
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        webservice.close()
        LOG.error("[ DB upgrade declined, Shutdown Emby-next-gen ]")
    elif not Ret:  # db reset required
        LOG.warning("[ DB reset required, Kodi restart ]")
        webservice.close()
        utils.restart_kodi()
    else:  # Regular start
        start_new_thread(ServersConnect, ())

        # Waiting/blocking function till Kodi stops
        LOG.info("Monitor listening")
        XbmcMonitor = monitor()  # Init Monitor
        XbmcMonitor.waitForAbort(0)
        XbmcMonitor = None

        # Shutdown
        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        LOG.warning("[ Shutdown Emby-next-gen ]")

    utils.XbmcPlayer = None
    utils.SystemShutdown = True

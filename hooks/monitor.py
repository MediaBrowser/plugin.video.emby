import json
from _thread import allocate_lock
import xbmcvfs
import xbmc
from helper import pluginmenu, utils, playerops, xmls, player, queue, deduplicate, backup
from database import dbio
from emby import emby
from . import webservice, favorites

QueueItemsRemove = set()
QueueItemsStatusupdate = ()
FullShutdown = False
utils.FavoriteQueue = queue.Queue()
syncEmbyLock = allocate_lock()
VideoLibrary_OnUpdateLock = allocate_lock()
VideoLibrary_OnRemoveLock = allocate_lock()

class monitor(xbmc.Monitor):
    def onNotification(self, _sender, method, data):
        if method == "Player.OnPlay":
            player.PlayerEventsQueue.put((("play", data),))
        elif method == "Player.OnStop":
            player.PlayerEventsQueue.put((("stop", data),))
        elif method == 'Player.OnSeek':
            player.PlayerEventsQueue.put((("seek", data),))
        elif method == "Player.OnAVChange":
            player.PlayerEventsQueue.put((("avchange", data),))
        elif method == "Player.OnAVStart":
            player.PlayerEventsQueue.put((("avstart", data),))
        elif method == "Player.OnPause":
            player.PlayerEventsQueue.put((("pause",),))
        elif method == "Player.OnResume":
            player.PlayerEventsQueue.put((("resume",),))
        if method == "Player.OnPropertyChanged":
            player.PlayerEventsQueue.put((("propertychanged", data),))
        if method == "Player.OnSpeedChanged":
            player.PlayerEventsQueue.put((("speedchanged", data),))
        elif method == 'Application.OnVolumeChanged':
            player.PlayerEventsQueue.put((("volume", data),))
        elif method == "Playlist.OnAdd":
            player.PlayerEventsQueue.put((("add", data),))
        elif method == "Playlist.OnRemove":
            player.PlayerEventsQueue.put((("remove", data),))
        elif method == "Playlist.OnClear":
            player.PlayerEventsQueue.put((("clear", data),))
        elif method == 'System.OnWake':
            xbmc.log("EMBY.hooks.monitor: --<[ sleep ]", 1) # LOGINFO
            webservice.start()

            for EmbyServer in list(utils.EmbyServers.values()):
                EmbyServer.ServerReconnect(False)

            utils.SyncPause['kodi_sleep'] = False
        elif method == 'System.OnSleep':
            xbmc.log("EMBY.hooks.monitor: -->[ sleep ]", 1) # LOGINFO
            utils.SyncPause['kodi_sleep'] = True

            if player.EmbyPlaying and player.PlayingItem[4]:
                player.PlayerEventsQueue.put((("stop", '{"end":"quit"}'),))

                while not player.PlayerEventsQueue.isEmpty():
                    utils.sleep(0.5)

            EmbyServer_DisconnectAll()
        elif method == 'System.OnQuit':
            xbmc.log("EMBY.hooks.monitor: System_OnQuit", 1) # LOGINFO
            ShutDown()
        elif method == 'Other.managelibsselection':
            utils.start_thread(pluginmenu.select_managelibs, ())
        elif method == 'Other.deduplicate':
            utils.start_thread(deduplicate.deduplicate, ())
        elif method == 'Other.settings':
            utils.start_thread(opensettings, ())
        elif method == 'Other.backup':
            utils.start_thread(backup.Backup, ())
        elif method == 'Other.restore':
            utils.start_thread(backup.Restore, ())
        elif method == 'Other.backupdelete':
            utils.start_thread(backup.Delete, ())
        elif method == 'Other.skinreload':
            utils.start_thread(utils.reset_querycache, ()) # Clear Cache
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.log("EMBY.hooks.monitor: Reload skin by notification", 1) # LOGINFO
        elif method == 'Other.manageserver':
            utils.start_thread(pluginmenu.manage_servers, (ServerConnect,))
        elif method == 'Other.databasereset':
            utils.start_thread(pluginmenu.databasereset, (favorites, ))
        elif method == 'Other.nodesreset':
            utils.start_thread(utils.nodesreset, ())
        elif method == 'Other.databasevacuummanual':
            utils.start_thread(dbio.DBVacuum, ())
        elif method == 'Other.factoryreset':
            utils.start_thread(pluginmenu.factoryreset, (False, favorites))
        elif method == 'Other.downloadreset':
            utils.start_thread(pluginmenu.downloadreset, ("",))
        elif method == 'Other.texturecache':
            if not utils.artworkcacheenable:
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False, time=utils.displayMessage)
            else:
                utils.start_thread(pluginmenu.cache_textures, ())
        elif method == 'Other.texturecachecancel':
            utils.TextureCacheCancel = True
        elif method == 'VideoLibrary.OnUpdate' and not utils.RemoteMode:  # Buffer updated items -> not overloading threads
            globals()["QueueItemsStatusupdate"] += (data,)

            if not VideoLibrary_OnUpdateLock.locked():
                utils.start_thread(VideoLibrary_OnUpdate, ())
        elif method == 'VideoLibrary.OnRemove' and not utils.RemoteMode:  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                globals()["QueueItemsRemove"].add(data)

                if not VideoLibrary_OnRemoveLock.locked():
                    utils.start_thread(VideoLibrary_OnRemove, ())

    def onScanStarted(self, library):
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi scan / {library} ]", 1) # LOGINFO

        if not utils.RemoteMode:
            utils.SyncPause['kodi_rw'] = True

    def onScanFinished(self, library):
        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi scan / {library} ]", 1) # LOGINFO
        utils.WidgetRefresh[library] = False

        if not utils.WidgetRefresh['music'] and not utils.WidgetRefresh['video']:
            utils.SyncPause['kodi_rw'] = False

            if not utils.RemoteMode and not syncEmbyLock.locked():
                utils.start_thread(syncEmby, ())

    def onCleanStarted(self, library):
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi clean / {library} ]", 1) # LOGINFO

        if not utils.RemoteMode:
            utils.SyncPause['kodi_rw'] = True

    def onCleanFinished(self, library):
        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi clean / {library} ]", 1) # LOGINFO
        utils.WidgetRefresh[library] = False

        if not utils.WidgetRefresh['music'] and not utils.WidgetRefresh['video']:
            utils.SyncPause['kodi_rw'] = False

            if not utils.RemoteMode and not syncEmbyLock.locked():
                utils.start_thread(syncEmby, ())

    def onSettingsChanged(self):
        xbmc.log("EMBY.hooks.monitor: Seetings changed", 1) # LOGINFO
        utils.start_thread(settingschanged, ())

def opensettings():
    xbmc.executebuiltin('Dialog.Close(all,true)')
    xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')

def syncEmby():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ syncEmby ]", 0) # LOGDEBUG

    with syncEmbyLock:
        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.library.RunJobs(True)

        xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ syncEmby ]", 0) # LOGDEBUG

# Remove Items
def VideoLibrary_OnRemove(): # Cache queries to minimize database openings
    if utils.sleep(0.5):
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnRemove ]", 0) # LOGDEBUG

    with VideoLibrary_OnRemoveLock:
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33264)):
            for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                QueueItemsRemoveLocal = QueueItemsRemove.copy()
                embydb = dbio.DBOpenRO(ServerId, "VideoLibrary_OnRemove")

                for RemoveItem in QueueItemsRemoveLocal:
                    data = json.loads(RemoveItem)

                    if 'item' in data:
                        KodiId = data['item']['id']
                        KodiType = data['item']['type']
                    else:
                        KodiId = data['id']
                        KodiType = data['type']

                    if KodiType in ("tvshow", "season") or not KodiType or not KodiId:
                        continue

                    EmbyId = embydb.get_EmbyId_by_KodiId_KodiType(KodiId, KodiType)

                    if not EmbyId:
                        continue

                    EmbyServer.API.delete_item(EmbyId)
                    globals()['QueueItemsRemove'].remove(RemoveItem)

                dbio.DBCloseRO(ServerId, "VideoLibrary_OnRemove")

    globals()['QueueItemsRemove'] = set()
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnRemove ]", 0) # LOGDEBUG

# Mark as watched/unwatched updates
def VideoLibrary_OnUpdate():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnUpdate ]", 0) # LOGDEBUG

    with VideoLibrary_OnUpdateLock:
        ItemsSkipUpdateRemove = ()
        UpdateUserDataCached = ()
        EmbyUpdateItems = {}
        EmbyDBs = {}
        KodiDB = None

        while QueueItemsStatusupdate:
            UpdateItem = QueueItemsStatusupdate[0]
            globals()['QueueItemsStatusupdate'] = QueueItemsStatusupdate[1:]
            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate process item: {UpdateItem}", 1) # LOGINFO
            data = json.loads(UpdateItem)

            if 'item' in data:
                KodiItemId = int(data['item']['id'])
                KodiType = data['item']['type']
            else:
                KodiItemId = int(data['id'])
                KodiType = data['type']

            EmbyId, ServerId = utils.get_EmbyId_ServerId_by_Fake_KodiId(KodiItemId)

            if EmbyId:
                EmbyServer = utils.EmbyServers[ServerId]
                xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate dynamic item detected: {EmbyId}", 1) # LOGINFO
            else: # Update synced item
                for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                    if ServerId not in EmbyDBs:
                        EmbyDBs[ServerId] = dbio.DBOpenRO(ServerId, "VideoLibrary_OnUpdate")

                    EmbyId = EmbyDBs[ServerId].get_EmbyId_by_KodiId_KodiType(KodiItemId, KodiType)

                    if EmbyId:
                        break
                else: # EmbyId not found
                    continue

            if str(EmbyId) not in ItemsSkipUpdateRemove:
                ItemsSkipUpdateRemove += (str(EmbyId),)

            if 'item' in data and 'playcount' in data:
                if KodiType in ("tvshow", "season"):
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {KodiType} / {EmbyId} ]", 1) # LOGINFO
                    continue

                if f"KODI{EmbyId}" not in utils.ItemSkipUpdate:  # Check EmbyID
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate update playcount {EmbyId} ]", 1) # LOGINFO

                    if int(EmbyId) in EmbyUpdateItems:
                        EmbyUpdateItems[int(EmbyId)]['PlayCount'] = data['playcount']
                    else:
                        EmbyUpdateItems[int(EmbyId)] = {'PlayCount': data['playcount']}
                else:
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {EmbyId} ]", 1) # LOGINFO
            else:
                if 'item' not in data:
                    if f"KODI{EmbyId}" not in utils.ItemSkipUpdate and EmbyId:  # Check EmbyID
                        if f"{{'item':{UpdateItem}}}" not in QueueItemsStatusupdate:
                            xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate reset progress {EmbyId} ]", 1) # LOGINFO

                            if int(EmbyId) in EmbyUpdateItems:
                                EmbyUpdateItems[int(EmbyId)].update({'Progress': 0, 'KodiItemId': KodiItemId, 'KodiType': KodiType})
                            else:
                                EmbyUpdateItems[int(EmbyId)] = {'Progress': 0, 'KodiItemId': KodiItemId, 'KodiType': KodiType}
                        else:
                            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (UpdateItems) {EmbyId}", 1) # LOGINFO
                    else:
                        xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (ItemSkipUpdate) {EmbyId}", 1) # LOGINFO

            for EmbyItemId, EmbyUpdateItem in list(EmbyUpdateItems.items()):
                utils.ItemSkipUpdate.append(str(EmbyItemId))

                if 'Progress' in EmbyUpdateItem:
                    if 'PlayCount' in EmbyUpdateItem:
                        EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], EmbyUpdateItem['PlayCount'])
                        UpdateUserDataCached += ((str(EmbyItemId), 0, "", EmbyUpdateItem['PlayCount'], False),)
                    else:
                        if not KodiDB:
                            KodiDB = dbio.DBOpenRO("video", "VideoLibrary_OnUpdate")

                        PlayCount = KodiDB.get_playcount(EmbyUpdateItem['KodiItemId'], EmbyUpdateItem['KodiType'])
                        EmbyServer.API.set_progress(EmbyItemId, EmbyUpdateItem['Progress'], PlayCount)
                        UpdateUserDataCached += ((str(EmbyItemId), 0, "", PlayCount, False),)
                else:
                    EmbyServer.API.set_played(EmbyItemId, EmbyUpdateItem['PlayCount'])
                    UpdateUserDataCached += ((str(EmbyItemId), None, "", EmbyUpdateItem['PlayCount'], False),)

        if KodiDB:
            dbio.DBCloseRO("video", "VideoLibrary_OnUpdate")

        for EmbyDB in EmbyDBs:
            dbio.DBCloseRO(EmbyDB, "VideoLibrary_OnUpdate")

        for ItemSkipUpdateRemove in ItemsSkipUpdateRemove:
            ItemSkipUpdateRemoveCompare = f"KODI{ItemSkipUpdateRemove}"

            if ItemSkipUpdateRemoveCompare in utils.ItemSkipUpdate:
                utils.ItemSkipUpdate.remove(ItemSkipUpdateRemoveCompare)

        utils.update_querycache_userdata(UpdateUserDataCached)
        del UpdateUserDataCached
        xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
        xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnUpdate ]", 0) # LOGDEBUG

def ServerConnect(ServerSettings):
    emby.EmbyServer(ServerSettings).ServerInitConnection()

def EmbyServer_DisconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.stop()

def settingschanged():  # threaded by caller
    if utils.sleep(0.5):
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ reload settings ]", 0) # LOGDEBUG
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    RestartKodi = False
    syncdatePrevious = utils.syncdate
    synctimePrevious = utils.synctime
    enablehttp2Previous = utils.enablehttp2
    xspplaylistsPreviousValue = utils.xspplaylists
    enableCoverArtPreviousValue = utils.enableCoverArt
    maxnodeitemsPreviousValue = utils.maxnodeitems
    AddonModePathPreviousValue = utils.AddonModePath
    websocketenabledPreviousValue = utils.websocketenabled
    curltimeoutsPreviousValue = utils.curltimeouts
    curlBoxSetsToTagsPreviousValue = utils.BoxSetsToTags
    DownloadPathPreviousValue = utils.DownloadPath
    SyncFavoritesPreviousValue = utils.SyncFavorites
    utils.InitSettings()

    # Http2 mode or curltimeouts changed, rebuild advanced settings -> restart Kodi
    if enablehttp2Previous != utils.enablehttp2 or curltimeoutsPreviousValue != utils.curltimeouts:
        if xmls.advanced_settings():
            RestartKodi = True

    # path(substitution) changed, update database pathes
    if AddonModePathPreviousValue != utils.AddonModePath:
        SQLs = {}
        dbio.DBOpenRW("video", "settingschanged", SQLs)
        SQLs["video"].toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("video", "settingschanged", SQLs)
        dbio.DBOpenRW("music", "settingschanged", SQLs)
        SQLs["music"].toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("music", "settingschanged", SQLs)
        utils.refresh_widgets(True)
        utils.refresh_widgets(False)

    # Toggle coverart setting
    if enableCoverArtPreviousValue != utils.enableCoverArt:
        DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33644))

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

    # Toggle collection tags
    if curlBoxSetsToTagsPreviousValue != utils.BoxSetsToTags:
        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.Views.add_nodes({'ContentType': "rootvideo"}, False)
            EmbyServer.Views.add_nodes({'ContentType': "rootaudio"}, False)
            EmbyServer.library.refresh_boxsets()

    # Restart Kodi
    if RestartKodi:
        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        utils.restart_kodi()
        xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ reload settings ] restart", 0) # LOGDEBUG
        return

    # Manual adjusted sync time/date
    if syncdatePrevious != utils.syncdate or synctimePrevious != utils.synctime:
        xbmc.log("EMBY.hooks.monitor: [ Trigger KodiStartSync due to setting changed ]", 1) # LOGINFO
        SyncTimestamp = f"{utils.syncdate} {utils.synctime}:00"
        SyncTimestamp = utils.convert_to_gmt(SyncTimestamp)

        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.library.set_syncdate(SyncTimestamp)
            utils.start_thread(EmbyServer.library.KodiStartSync, (False,))

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.API.update_settings()

    # Toggle xsp playlists
    if xspplaylistsPreviousValue != utils.xspplaylists:
        if utils.xspplaylists:
            for EmbyServer in list(utils.EmbyServers.values()):
                EmbyServer.Views.update_nodes()
        else:
            # delete playlists
            for PlaylistFolder in ['special://profile/playlists/video/', 'special://profile/playlists/music/']:
                if xbmcvfs.exists(PlaylistFolder):
                    _, Filenames = xbmcvfs.listdir(PlaylistFolder)

                    for Filename in Filenames:
                        utils.delFile(f"{PlaylistFolder}{Filename}")

    # Change download path
    if DownloadPathPreviousValue != utils.DownloadPath:
        pluginmenu.downloadreset(DownloadPathPreviousValue)

    # Toggle Favorites
    if SyncFavoritesPreviousValue != utils.SyncFavorites:
        favorites.set_Favorites(utils.SyncFavorites)

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ reload settings ]", 0) # LOGDEBUG

def ServersConnect():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ ServersConnect ]", 0) # LOGDEBUG

    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            utils.SyncPause = {}
            xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ] shutdown", 0) # LOGDEBUG
            return

    _, Filenames = xbmcvfs.listdir(utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in Filenames:
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
        xbmc.log("EMBY.hooks.monitor: Reload skin on connection established", xbmc.LOGINFO)

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ]", 0) # LOGDEBUG

def setup():
    # copy default nodes
    utils.mkDir("special://profile/library/")
    utils.mkDir("special://profile/library/video/")
    utils.mkDir("special://profile/library/music/")
    utils.copytree("special://xbmc/system/library/video/", "special://profile/library/video/", (), True, False)
    utils.copytree("special://xbmc/system/library/music/", "special://profile/library/music/", (), True, False)

    # copy animated icons
    for PluginId in ("video", "image", "audio"):
        Destination = f"special://home/addons/plugin.{PluginId}.emby-next-gen/resources/icon-animated.gif"

        if not xbmcvfs.exists(Destination):
            utils.copyFile("special://home/addons/plugin.service.emby-next-gen/resources/icon-animated.gif", Destination)

    if utils.MinimumSetup == "OPENLIBRARY":
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return "OPENLIBRARY"

    if utils.MinimumSetup == utils.MinimumVersion:
        return True

    xbmc.executebuiltin('ReplaceWindow(10000)')
    utils.refreshskin = False

    # Clean installation
    if not utils.MinimumSetup:
        value = utils.Dialog.yesno(heading=utils.Translate(30511), message=utils.Translate(33035), nolabel=utils.Translate(33036), yeslabel=utils.Translate(33037))

        if value:
            utils.set_settings_bool('useDirectPaths', True)
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33145))
        else:
            utils.set_settings_bool('useDirectPaths', False)

        utils.update_mode_settings()
        xbmc.log(f"EMBY.hooks.monitor: Add-on playback: {utils.useDirectPaths == '0'}", 1) # LOGINFO
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        xmls.sources() # verify sources.xml

        if xmls.advanced_settings(): # verify advancedsettings.xml
            return False

        return True

    if utils.sleep(10): # Give Kodi time to load skin
        return "stop"

    TicksStart = utils.get_unixtime_emby_format()
    Ack = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33222), autoclose=60000, defaultbutton=11)
    TicksEnd = utils.get_unixtime_emby_format()

    if TicksEnd - TicksStart > 600000:
        Ack = True

    if not Ack: # final warning
        if backup.restore_Rollback():
            # Disable auto-updates
            SQLs = {}
            dbio.DBOpenRW("addon", "settingschanged", SQLs)
            SQLs["addon"].set_AutoUpdates("plugin.service.emby-next-gen", 1)
            dbio.DBCloseRW("addon", "settingschanged", SQLs)
            return False

        return "stop"

    pluginmenu.factoryreset(True, favorites)
    return False

def StartUp():
    xbmc.log("EMBY.hooks.monitor: [ Start Emby-next-gen ]", 1) # LOGINFO
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        webservice.close()
        xbmc.log("EMBY.hooks.monitor: [ DB upgrade declined, Shutdown Emby-next-gen ]", 3) # LOGERROR
    elif not Ret:  # db reset required
        xbmc.log("EMBY.hooks.monitor: [ DB reset required, Kodi restart ]", 2) # LOGWARNING
        webservice.close()
        utils.restart_kodi()
    else:  # Regular start
        xbmc.log("EMBY.hooks.monitor: Monitor listening", 1) # LOGINFO
        globals()['FullShutdown'] = True
        utils.XbmcMonitor = monitor()  # Init Monitor
        backup.create_Rollback()
        utils.start_thread(favorites.monitor_Favorites, ())
        utils.start_thread(favorites.emby_change_Favorite, ())

        if Ret == "OPENLIBRARY":
            ServersConnect()
            utils.ActivateWindow("home", "", True)

            for EmbyServer in list(utils.EmbyServers.values()):
                while not EmbyServer.Loaded:
                    if utils.sleep(1):
                        break
                else:
                    EmbyServer.library.select_libraries("AddLibrarySelection")
        else:
            utils.start_thread(ServersConnect, ())

        utils.XbmcMonitor.waitForAbort(0) # Waiting/blocking function till Kodi stops

    ShutDown()

def ShutDown():
    for EmbyServer in list(utils.EmbyServers.values()):
        while EmbyServer.http.RequestBusy['BUSY'].locked():
            utils.release_lock(EmbyServer.http.RequestBusy['BUSY'])
            xbmc.sleep(10)

    utils.release_lock(utils.PlayerBusy)

    if FullShutdown:
        # Shutdown
        globals()['FullShutdown'] = False
        utils.SystemShutdown = True
        utils.FavoriteQueue.put("QUIT")

        if player.EmbyPlaying and player.PlayingItem[4]:
            player.PlayerEventsQueue.put((("stop", '{"end":"quit"}'),))

            while not player.PlayerEventsQueue.isEmpty():
                xbmc.sleep(100)

        EmbyServer_DisconnectAll()

        for RemoteCommandQueue in list(playerops.RemoteCommandQueue.values()):
            RemoteCommandQueue.put("QUIT")

        webservice.close()
        xbmc.log("EMBY.hooks.monitor: [ Shutdown Emby-next-gen ]", 2) # LOGWARNING

    player.PlayerEventsQueue.put("QUIT")
    utils.SystemShutdown = True
    xbmc.log("EMBY.hooks.monitor: Exit Emby-next-gen", 1) # LOGINFO

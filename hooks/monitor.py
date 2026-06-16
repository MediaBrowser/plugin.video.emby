import json
import threading
import xbmcvfs
import xbmc
from helper import pluginmenu, utils, playerops, xmls, player, queue, deduplicate, backup, cache
from database import dbio
from emby import emby, httpcache
from . import webservice, favorites, themes

QueueItemsRemove = set()
FullShutdown = False
utils.FavoriteQueue = queue.Queue()
syncEmbyLock = threading.Lock()
VideoLibrary_OnRemoveLock = threading.Lock()
SettingsChangedEvent = threading.Event()
SystemEventsQueue = queue.Queue()
SystemScansQueue = queue.Queue()

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
        elif method == "Player.OnPropertyChanged":
            player.PlayerEventsQueue.put((("propertychanged", data),))
        elif method == "Player.OnSpeedChanged":
            player.PlayerEventsQueue.put((("speedchanged", data),))
        elif method == 'Application.OnVolumeChanged':
            player.PlayerEventsQueue.put((("volume", data),))
        elif method == "Playlist.OnAdd":
            player.PlayerEventsQueue.put((("add", data),))
        elif method == "Playlist.OnRemove":
            player.PlayerEventsQueue.put((("remove", data),))
        elif method == "Playlist.OnClear":
            player.PlayerEventsQueue.put((("clear", data),))
        elif method == "Other.playback_failed": # youtube plugin
            player.PlayerEventsQueue.put((("stop", '{"end":true}'),))
        elif method == "Other.playback_init": # youtube plugin
            player.PlayerEventsQueue.put((("playerid", '{"player":{"playerid":1}}'),))
        elif method == "Other.playback_started": # youtube plugin
            player.PlayerEventsQueue.put((("playerid", '{"player":{"playerid":1}}'),))
#        elif method == "Other.playback_stopped": # youtube plugin
#            pass
        else:
            SystemEventsQueue.put(((method, data),))

    def onScanStarted(self, library):
        SystemScansQueue.put((("scanstart", library),))

    def onScanFinished(self, library):
        SystemScansQueue.put((("scanstop", library),))

    def onCleanStarted(self, library):
        SystemScansQueue.put((("cleanstart", library),))

    def onCleanFinished(self, library):
        SystemScansQueue.put((("cleanfinsihed", library),))

    def onSettingsChanged(self):
        SystemEventsQueue.put((("settingschanged",),))

def SystemScans():
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ system scan ]", 1) # LOGDEBUG

    while True:
        SystemScan = SystemScansQueue.get()
        xbmc.log(f"EMBY.hooks.monitor: [ SystemScans: {SystemScan} ]", 1) # LOGINFO

        if SystemScan == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ system scan ] quit", 1) # LOGDEBUG
            return

        if SystemScan[0] in ('scanstart', 'cleanstart'):
            utils.update_SyncPause('kodi_rw', True)
            utils.set_SyncLock()
        elif SystemScan[0] in ('scanstop', 'cleanfinsihed'):
            utils.WidgetRefresh[SystemScan[1]] = False

            if not utils.WidgetRefresh['music'] and not utils.WidgetRefresh['video']:
                utils.update_SyncPause('kodi_rw', False)
                utils.unset_SyncLock()

def SystemEvents():
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ system event ]", 1) # LOGDEBUG

    while True:
        SystemEvent = SystemEventsQueue.get()
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.monitor (DEBUG): SystemEvents received: {SystemEvent}", 1) # LOGDEBUG

        if SystemEvent == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ system event ] quit", 1) # LOGDEBUG
            return

        if SystemEvent[0] == 'System.OnWake':
            xbmc.log("EMBY.hooks.monitor: -->[ wake ]", 1) # LOGINFO
            webservice.start()

            for EmbyServer in list(utils.EmbyServers.values()):
                EmbyServer.ServerReconnect(False)

            utils.update_SyncPause('kodi_sleep',  False)
            xbmc.log("EMBY.hooks.monitor: --<[ wake ]", 1) # LOGINFO
        elif SystemEvent[0] == 'System.OnSleep':
            xbmc.log("EMBY.hooks.monitor: -->[ sleep ]", 1) # LOGINFO
            utils.update_SyncPause('kodi_sleep', True)
            wait_PlayerEventsQueue()
            EmbyServer_DisconnectAll()
            xbmc.log("EMBY.hooks.monitor: --<[ sleep ]", 1) # LOGINFO
        elif SystemEvent[0] == 'System.OnQuit':
            xbmc.log("EMBY.hooks.monitor: System_OnQuit", 1) # LOGINFO
            ShutDown()
        elif SystemEvent[0] == 'Other.managelibsselection':
            utils.start_thread(pluginmenu.select_managelibs, ())
        elif SystemEvent[0] == 'Other.deduplicate':
            utils.start_thread(deduplicate.deduplicate, ())
        elif SystemEvent[0] == 'Other.settings':
            utils.start_thread(opensettings, ())
        elif SystemEvent[0] == 'Other.backup':
            utils.start_thread(backup.Backup, ())
        elif SystemEvent[0] == 'Other.restore':
            utils.start_thread(backup.Restore, ())
        elif SystemEvent[0] == 'Other.backupdelete':
            utils.start_thread(backup.Delete, ())
        elif SystemEvent[0] == 'Other.skinreload':
            utils.start_thread(cache.reset_querycache, ()) # Clear Cache
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.log("EMBY.hooks.monitor: Reload skin by notification", 1) # LOGINFO
        elif SystemEvent[0] == 'Other.manageserver':
            utils.start_thread(pluginmenu.manage_servers, (ServerConnect,))
        elif SystemEvent[0] == 'Other.databasereset':
            utils.start_thread(pluginmenu.databasereset, (favorites, ))
        elif SystemEvent[0] == 'Other.nodesreset':
            utils.start_thread(utils.nodesreset, ())
        elif SystemEvent[0] == 'Other.databasevacuummanual':
            utils.start_thread(dbio.DBVacuum, ())
        elif SystemEvent[0] == 'Other.factoryreset':
            utils.start_thread(pluginmenu.factoryreset, (False, favorites))
        elif SystemEvent[0] == 'Other.downloadreset':
            utils.start_thread(pluginmenu.downloadreset, ("",))
        elif SystemEvent[0] == 'Other.themedownload':
            utils.start_thread(themes.download, ())
        elif SystemEvent[0] == 'Other.remotetrailersselection':
            utils.start_thread(pluginmenu.remotetrailersselection, ())
        elif SystemEvent[0] == 'Other.texturecache':
            if not utils.artworkcacheenable:
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False, time=utils.displayMessage)
            else:
                utils.start_thread(pluginmenu.cache_textures, ())
        elif SystemEvent[0] == 'Other.texturecachecancel':
            utils.TextureCacheCancel = True
        elif SystemEvent[0] == 'VideoLibrary.OnUpdate' and not utils.RemoteMode:  # Buffer updated items -> not overloading threads
            player.ItemsUpdateQueue.put(SystemEvent[1])
        elif SystemEvent[0] == 'VideoLibrary.OnRemove' and not utils.RemoteMode:  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                QueueItemsRemove.add(SystemEvent[1])

                if not VideoLibrary_OnRemoveLock.locked():
                    utils.start_thread(VideoLibrary_OnRemove, ())
        elif SystemEvent[0] == 'settingschanged':
            xbmc.log("EMBY.hooks.monitor: Settings changed", 1) # LOGINFO
            SettingsChangedEvent.set()

def opensettings():
    utils.close_dialog("all")
    xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')

# Remove Items
def VideoLibrary_OnRemove(): # Cache queries to minimize database openings
    global QueueItemsRemove

    if utils.sleep(0.5):
        return

    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ VideoLibrary_OnRemove ]", 1) # LOGDEBUG

    with utils.SafeLock(VideoLibrary_OnRemoveLock):
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
                    QueueItemsRemove.remove(RemoveItem)

                dbio.DBCloseRO(ServerId, "VideoLibrary_OnRemove")

    QueueItemsRemove = set()
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ VideoLibrary_OnRemove ]", 1) # LOGDEBUG

def poll_Events(XbmcMonitor):
    IsScanningMusicOld = False
    IsScanningVideoOld = False

    while not XbmcMonitor.waitForAbort(0.5):
        # Get scan status
        IsScanningMusic = xbmc.getCondVisibility('Library.IsScanningMusic')
        IsScanningVideo = xbmc.getCondVisibility('Library.IsScanningVideo')

        if IsScanningMusic != IsScanningMusicOld:
            IsScanningMusicOld = IsScanningMusic
            if IsScanningMusic:
                XbmcMonitor.onScanStarted("music")
            else:
                XbmcMonitor.onScanFinished("music")

        if IsScanningVideo != IsScanningVideoOld:
            IsScanningVideoOld = IsScanningVideo

            if IsScanningVideo:
                XbmcMonitor.onScanStarted("video")
            else:
                XbmcMonitor.onScanFinished("video")

# Mark as watched/unwatched updates
def VideoLibrary_OnUpdate():
    # {"id":8418,"type":"episode"} and not played before, is reset progress
    # {"item":{"id":8418,"type":"episode"},"playcount":0} is mark as unwatched
    # {"item":{"id":8418,"type":"episode"},"playcount":1} is mark as watched
    # (video) playback stop send {"item":{"id":8418,"type":"episode"}}, skip it as Emby session progress keeps track
    # (video) playback end sends {"item":{"id":8418,"type":"episode"}} and {"item":{"id":8428,"type":"episode"},"playcount":1}, skip it as Emby session progress keeps track
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ VideoLibrary_OnUpdate ]", 1) # LOGDEBUG
    EmbyDBs = {}
    KodiDB = None

    while True:
        if player.ItemsUpdateQueue.isEmpty():
            if KodiDB:
                dbio.DBCloseRO("video", "VideoLibrary_OnUpdate")

            for EmbyDB in EmbyDBs:
                dbio.DBCloseRO(EmbyDB, "VideoLibrary_OnUpdate")

            EmbyDBs = {}
            KodiDB = None

        UpdateItem = player.ItemsUpdateQueue.get()

        if UpdateItem == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ VideoLibrary_OnUpdate ]", 1) # LOGDEBUG
            return

        EmbyUpdateItem = {}
        data = json.loads(UpdateItem)

        if "DELETE" in data and data["DELETE"] in player.ItemKodiSkipUpdate:
            player.ItemKodiSkipUpdate.remove(data["DELETE"])
            continue

        if 'item' in data:
            KodiItemId = int(data['item']['id'])
            KodiType = data['item']['type']
        elif 'id' in data:
            KodiItemId = int(data['id'])
            KodiType = data['type']
        else:
            continue

        if [KodiItemId, KodiType] in player.ItemKodiSkipUpdate:
            continue

        xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate process item: {UpdateItem}", 1) # LOGINFO
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

        if 'item' in data and 'playcount' in data:
            if KodiType in ("tvshow", "season"):
                xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {KodiType} / {EmbyId} ]", 1) # LOGINFO
                continue

            xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate update playcount {EmbyId} ]", 1) # LOGINFO
            EmbyUpdateItem = {'PlayCount': data['playcount']}
        else:
            if 'item' not in data: # {"id":8418,"type":"episode"}
                xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate reset progress {EmbyId} ]", 1) # LOGINFO
                EmbyUpdateItem = {'Progress': 0, 'KodiItemId': KodiItemId, 'KodiType': KodiType}

        if EmbyUpdateItem:
            utils.ItemSkipUpdate.append(str(EmbyId))

            if 'Progress' in EmbyUpdateItem:
                if 'PlayCount' in EmbyUpdateItem:
                    EmbyServer.API.set_progress(EmbyId, EmbyUpdateItem['Progress'], EmbyUpdateItem['PlayCount'])
                    UpdateUserDataCached = ((str(EmbyId), 0, "", EmbyUpdateItem['PlayCount'], False),)
                else:
                    if not KodiDB:
                        KodiDB = dbio.DBOpenRO("video", "VideoLibrary_OnUpdate")

                    PlayCount = KodiDB.get_playcount(EmbyUpdateItem['KodiItemId'], EmbyUpdateItem['KodiType'])
                    EmbyServer.API.set_progress(EmbyId, EmbyUpdateItem['Progress'], PlayCount)
                    UpdateUserDataCached = ((str(EmbyId), 0, "", PlayCount, False),)
            else:
                EmbyServer.API.set_played(EmbyId, EmbyUpdateItem['PlayCount'])
                UpdateUserDataCached = ((str(EmbyId), None, "", EmbyUpdateItem['PlayCount'], False),)

            cache.update_querycache_userdata(UpdateUserDataCached)
            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO

def ServerConnect(ServerSettings):
    emby.EmbyServer(ServerSettings).ServerInitConnection()

def EmbyServer_DisconnectAll():
    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.stop()

def settingschanged():
    while True:
        while True:
            if SettingsChangedEvent.wait(timeout=0.1):
                break

            if utils.SystemShutdown:
                if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ reload settings ]", 1) # LOGDEBUG
                return

        SettingsChangedEvent.clear()
        if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ reload settings ]", 1) # LOGDEBUG
        utils.close_dialog(10146) # addoninformation
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
            utils.clear_SyncPause()
            webservice.close()
            EmbyServer_DisconnectAll()
            utils.restart_kodi()
            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ reload settings ] restart", 1) # LOGDEBUG
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

def ServersConnect():
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: --->[ ServersConnect ]", 1) # LOGDEBUG

    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            utils.clear_SyncPause()
            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ ServersConnect ] shutdown", 1) # LOGDEBUG
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
        xbmc.log("EMBY.hooks.monitor: Reload skin on connection established", 1) # LOGINFO

    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): THREAD: ---<[ ServersConnect ]", 1) # LOGDEBUG

def get_digits(Text):
    Temp = ''.join(i for i in Text if i.isdigit())

    if Temp:
        return int(Temp)

    return 0

def setup():
    # Wait for homescreen (Kodi fully loaded)
    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): --->[ wait for homescreen ]", 1) # LOGDEBUG

    while not xbmc.getCondVisibility('Window.IsActive(10000)'):
        utils.sleep(1)

    if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): ---<[ wait for homescreen ]", 1) # LOGDEBUG

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

def wait_PlayerEventsQueue():
    if player.EmbyPlaying and player.PlayingItem[4]:
        player.PlayerEventsQueue.put((("stop", '{"end":"quit"}'),))
        if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): CONDITION: --->[ PlayerEventsQueue ]", 1) # LOGDEBUG

        with utils.SafeLock(player.PlayerEventsQueue.ThreadCondition):
            while player.PlayerEventsQueue.ItemsQueue:
                player.PlayerEventsQueue.ThreadCondition.wait(timeout=0.1)

        if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): CONDITION: ---<[ PlayerEventsQueue ]", 1) # LOGDEBUG

def StartUp():
    global FullShutdown
    xbmc.log("EMBY.hooks.monitor: [ Start Emby-next-gen ]", 1) # LOGINFO
    utils.start_thread(SystemEvents, ())
    utils.start_thread(SystemScans, ())
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        webservice.close()
        xbmc.log("EMBY.hooks.monitor: [ DB upgrade declined, Shutdown Emby-next-gen ]", 3) # LOGERROR
    elif not Ret:  # db reset required
        xbmc.log("EMBY.hooks.monitor: [ Modify settings, Kodi restart ]", 2) # LOGWARNING
        webservice.close()
        utils.restart_kodi()
    else:  # Regular start
        xbmc.log("EMBY.hooks.monitor: Monitor listening", 1) # LOGINFO
        FullShutdown = True
        backup.create_Rollback()
        utils.start_thread(utils.RunSyncJobsAsync, ())
        utils.start_thread(VideoLibrary_OnUpdate, ())
        utils.start_thread(themes.monitor_Themes, ())
        utils.start_thread(favorites.monitor_Favorites, ())
        utils.start_thread(favorites.emby_change_Favorite, ())
        utils.start_thread(httpcache.clear, ())
        utils.start_thread(settingschanged, ())
        XbmcMonitor = monitor()  # Init Monitor
        utils.start_thread(poll_Events, (XbmcMonitor,))

        if Ret == "OPENLIBRARY":
            ServersConnect()
            utils.ActivateWindow("home", "", True)

            for EmbyServer in list(utils.EmbyServers.values()):
                if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): CONDITION: --->[ EmbyServerOnlineCondition ]", 1)

                with utils.SafeLock(utils.EmbyServerOnlineCondition):
                    while not EmbyServer.Online:
                        Wait = 30

                        while Wait > 0:
                            if utils.EmbyServerOnlineCondition.wait(timeout=0.1):
                                break

                            Wait -= 1

                        if utils.SystemShutdown:
                            if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): CONDITION: ---<[ EmbyServerOnlineCondition ]", 1)
                            break
                    else:
                        EmbyServer.library.select_libraries("AddLibrarySelection")

                if utils.DebugLog: xbmc.log("EMBY.hooks.monitor (DEBUG): CONDITION: ---<[ EmbyServerOnlineCondition ]", 1)
        else:
            utils.start_thread(ServersConnect, ())

        utils.NextGenOnline.set()

        while not XbmcMonitor.waitForAbort(0.1):
            pass

    ShutDown()

def ShutDown():
    global FullShutdown

    if FullShutdown:
        # Shutdown
        FullShutdown = False
        utils.SystemShutdown = True
        utils.FavoriteQueue.put("QUIT")
        player.ItemsUpdateQueue.put("QUIT")
        wait_PlayerEventsQueue()
        EmbyServer_DisconnectAll()

        for RemoteCommandQueue in list(playerops.RemoteCommandQueue.values()):
            RemoteCommandQueue.put("QUIT")

        webservice.close()
        xbmc.log("EMBY.hooks.monitor: [ Shutdown Emby-next-gen ]", 2) # LOGWARNING

    with utils.SafeLock(utils.SettingsChangedCondition): # exit themes loop
        utils.SettingsChangedCondition.notify_all()

    player.PlayerEventsQueue.put("QUIT")
    utils.SystemShutdown = True
    utils.unset_SyncLock()
    utils.NextGenOnline.set()
    SettingsChangedEvent.set()
    SystemEventsQueue.put("QUIT")
    SystemScansQueue.put("QUIT")
    xbmc.log("EMBY.hooks.monitor: Exit Emby-next-gen", 1) # LOGINFO

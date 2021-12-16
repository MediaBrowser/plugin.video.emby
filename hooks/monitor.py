# -*- coding: utf-8 -*-
import json
import threading
import socket
import xml.etree.ElementTree
import requests
import xbmc
import xbmcgui
import xbmcplugin
import helper.loghandler
import helper.context
import helper.pluginmenu
import helper.utils as Utils
import helper.playerops as PlayerOps
import helper.xmls as xmls
import database.db_open
import emby.emby
from . import webservice
from . import player

if Utils.Python3:
    from urllib.parse import quote_plus
else:
    from urllib import quote_plus

LOG = helper.loghandler.LOG('EMBY.hooks.monitor')


class Monitor(xbmc.Monitor):
    def __init__(self):
        self.WebServiceThread = None
        self.sleep = False
        self.EmbyServers = {}
        self.player = player.PlayerEvents()
        self.player.StartUp(self.EmbyServers)
        self.WebserviceStart()
        self.Context = helper.context.Context(self.EmbyServers)
        self.Menu = helper.pluginmenu.Menu(self.EmbyServers, self.player)
        self.QueryDataThread = threading.Thread(target=self.QueryData)
        self.QueryDataThread.start()
        self.QueueItemsStatusupdate = ()
        self.QueryItemStatusThread = None

    def WebserviceStart(self):
        if self.WebServiceThread:
            self.WebServiceThread.close()
            self.WebServiceThread.join()
            self.WebServiceThread = None

        self.WebServiceThread = webservice.WebService(self.player)
        self.WebServiceThread.start()

    def shutdown(self):
        LOG.warning("---<[ EXITING ]")
        Utils.SyncPause = True
        Utils.SystemShutdown = True
        self.QuitThreads()
        self.EmbyServer_DisconnectAll()

    # List loading from events.py
    def QueryData(self):
        QuerySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        QuerySocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        QuerySocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        QuerySocket.settimeout(None)
        QuerySocket.bind(('127.0.0.1', 60001))
        QuerySocket.listen(50)

        while True:
            client, _ = QuerySocket.accept()
            Incomming = client.recv(1024).decode('utf-8')

            if Incomming == "QUIT":
                QuerySocket.close()
                return

            threading.Thread(target=self.QueryDataExcecute, args=(Incomming, client,)).start()

    def QueryDataExcecute(self, Incomming, client):  # threaded by caller
        Data = Incomming.split(";")

        if Data[0] == 'browse':
            self.Menu.browse(Data[7], Data[1], Data[2], Data[3], Data[4], Data[5], Data[6])
        elif Data[0] == 'nextepisodes':
            get_next_episodes(Data[3], Data[1])
        elif Data[0] == 'favepisodes':
            self.Menu.favepisodes(Data[3])
        elif Data[0] == 'listing':
            self.Menu.listing(Data[3])

        client.send(b"1")

    def onNotification(self, sender, method, data):
         # Skip unsupported notifications -> e.g. "Playlist.OnAdd" floats threading! -> Never let that happen
        if method == 'VideoLibrary.OnUpdate':  # Buffer updated items -> not overloading threads
            self.QueueItemsStatusupdate += (data,)

            if not self.QueryItemStatusThread:
                self.QueryItemStatusThread = threading.Thread(target=self.VideoLibrary_OnUpdate)
                self.QueryItemStatusThread.start()
        elif method in ('Other.managelibsselection', 'Other.delete', 'Other.settings', 'Other.backup', 'Other.restore', 'Other.reset_device_id', 'Other.addserver', 'Other.adduserselection', 'Other.databasereset', 'Other.texturecache', 'Other.context', 'System.OnWake', 'System.OnSleep', 'System.OnQuit', 'Application.OnVolumeChanged', 'Other.play'):
            threading.Thread(target=self.Notification, args=(method, data,)).start()

    def Notification(self, method, data):  # threaded by caller
        if method == 'Other.managelibsselection':
            self.Menu.select_managelibs()
        elif method == 'Other.delete':
            self.Context.delete_item(True)
        elif method == 'Other.settings':
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % Utils.PluginId)
        elif method == 'Other.backup':
            Backup()
        elif method == 'Other.restore':
            BackupRestore()
        elif method == 'Other.reset_device_id':
            reset_device_id()
        elif method == 'Other.addserver':
            self.ServerConnect(None)
        elif method == 'Other.adduserselection':
            self.Menu.select_adduser()
        elif method == 'Other.databasereset':
            databasereset(self.EmbyServers)
        elif method == 'Other.texturecache':
            if not Utils.artworkcacheenable:
                Utils.dialog("notification", heading=Utils.addon_name, icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", message=Utils.Translate(33226), sound=False)
            else:
                cache_textures()
        elif method == 'Other.context':
            self.Context.select_menu()
        elif method == 'System.OnWake':
            self.System_OnWake()
        elif method == 'System.OnSleep':
            self.System_OnSleep()
        elif method == 'System.OnQuit':
            self.System_OnQuit()
        elif method == 'Application.OnVolumeChanged':
            self.player.SETVolume(data)
        elif method == 'Other.play':
            data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
            PlayerOps.Play((data[1],), "PlayNow", -1, -1, self.EmbyServers[data[0]])

    def EmbyServer_ReconnectAll(self):
        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.ServerReconnect()

    def EmbyServer_DisconnectAll(self):
        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.stop()

    def onScanStarted(self, library):
        Utils.KodiDBLock[library] = True
        LOG.info("-->[ kodi scan/%s ]" % library)

    def onScanFinished(self, library):
        Utils.KodiDBLock[library] = False
        LOG.info("--<[ kodi scan/%s ]" % library)

    def ServerConnect(self, ServerSettings):
        EmbyServerObj = emby.emby.EmbyServer(self.UserDataChanged, ServerSettings)
        server_id, EmbyServer = EmbyServerObj.register()

        if not server_id or server_id == 'cancel' or Utils.SystemShutdown:
            LOG.error("EmbyServer Connect error")
            return

        self.EmbyServers[server_id] = EmbyServer

        if self.WebServiceThread:
            self.WebServiceThread.Update_EmbyServers(self.EmbyServers)

    # Update progress, skip for seasons and series. Just update episodes
    def UserDataChanged(self, server_id, UserDataList, UserId):
        if UserId != self.EmbyServers[server_id].user_id:
            return

        LOG.info("[ UserDataChanged ] %s" % UserDataList)
        UpdateData = []
        embydb = database.db_open.DBOpen(Utils.DatabaseFiles, server_id)

        for ItemData in UserDataList:
            if ItemData['ItemId'] not in self.player.ItemSkipUpdate:  # Check EmbyID
                e_item = embydb.get_item_by_id(ItemData['ItemId'])

                if e_item:
                    if e_item[5] in ("Season", "Series"):
                        LOG.info("[ UserDataChanged skip %s/%s ]" % (e_item[5], ItemData['ItemId']))
                    else:
                        UpdateData.append(ItemData)
                else:
                    LOG.info("[ UserDataChanged item not found %s ]" % ItemData['ItemId'])
            else:
                LOG.info("[ UserDataChanged skip update/%s ]" % ItemData['ItemId'])

                if 'ItemId' in self.player.PlayingItem:  # Skip removal for currently playing item
                    if self.player.PlayingItem['ItemId'] != str(ItemData['ItemId']):
                        self.player.ItemSkipUpdate.remove(str(ItemData['ItemId']))
                else:
                    self.player.ItemSkipUpdate.remove(str(ItemData['ItemId']))

        database.db_open.DBClose(server_id, False)

        if UpdateData:
            self.EmbyServers[server_id].library.userdata(UpdateData)

    def System_OnQuit(self):
        for EmbyServer in list(self.EmbyServers.values()):
            if self.player.Transcoding:
                EmbyServer.API.close_transcode()

        self.shutdown()

    def QuitThreads(self):
        if self.WebServiceThread:
            self.WebServiceThread.close()
            self.WebServiceThread.join()
            self.WebServiceThread = None

        if self.QueryDataThread:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                sock.connect(('127.0.0.1', 60001))
                sock.settimeout(1)
                request = "QUIT"
                sock.send(request.encode())
            except:
                pass

            self.QueryDataThread.join()
            self.QueryDataThread = None

    def onSettingsChanged(self):
        threading.Thread(target=self.settingschanged).start()

    def settingschanged(self):  # threaded by caller
        if Utils.SkipUpdateSettings:
            Utils.SkipUpdateSettings -= 1

            if Utils.SkipUpdateSettings < 0:
                Utils.SkipUpdateSettings = 0

        if Utils.SkipUpdateSettings:
            return

        LOG.info("[ Reload settings ]")
        syncdatePrevious = Utils.syncdate
        synctimePrevious = Utils.synctime
        xspplaylistsPreviousValue = Utils.xspplaylists
        compatibilitymodePreviousValue = Utils.compatibilitymode
        Utils.InitSettings()

        if syncdatePrevious != Utils.syncdate or synctimePrevious != Utils.synctime:
            LOG.info("[ Trigger initsync due to setting changed ]")
            SyncTimestamp = '%s %s:00' % (Utils.syncdate, Utils.synctime)
            SyncTimestamp = Utils.convert_to_gmt(SyncTimestamp)

            for EmbyServer in list(self.EmbyServers.values()):
                EmbyServer.library.set_syncdate(SyncTimestamp)
                threading.Thread(target=EmbyServer.library.InitSync, args=(False,)).start()  # start initial sync

        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.API.update_settings()

        # Toggle xsp playlists
        if xspplaylistsPreviousValue != Utils.xspplaylists:
            if Utils.xspplaylists:
                for EmbyServer in list(self.EmbyServers.values()):
                    EmbyServer.Views.update_nodes()
            else:
                # delete playlists
                for playlistfolder in ['special://profile/playlists/video/', 'special://profile/playlists/music/']:
                    if Utils.checkFolderExists(playlistfolder):
                        _, files = Utils.listDir(playlistfolder)

                        for Filename in files:
                            Utils.delFile("%s%s" % (playlistfolder, Filename))

        # Toggle compatibility mode
        if compatibilitymodePreviousValue != Utils.compatibilitymode:
            if Utils.compatibilitymode:
                PluginID = "plugin.video.emby"
                PluginIDPrevious = "plugin.video.emby-next-gen"
            else:
                PluginID = "plugin.video.emby-next-gen"
                PluginIDPrevious = "plugin.video.emby"

            PatchFiles = {"script-emby-connect-login-manual.xml", "script-emby-connect-login.xml", "script-emby-connect-server.xml", "script-emby-connect-server-manual.xml", "script-emby-connect-users.xml"}

            # update script files
            for PatchFile in PatchFiles:
                FileName = "special://home/addons/plugin.video.emby-next-gen/resources/skins/default/1080i/%s" % PatchFile
                xmlData = Utils.readFileString(FileName)
                xmlData = xml.etree.ElementTree.fromstring(xmlData)

                for elem in xmlData.iter():
                    if elem.tag == 'label':
                        if elem.text.find(PluginIDPrevious) != -1:
                            elem.text = elem.text.replace(PluginIDPrevious, PluginID)

                xmls.WriteXmlFile(FileName, xmlData)

            # update addon.xml id
            xmlData = Utils.readFileString("special://home/addons/plugin.video.emby-next-gen/addon.xml")
            xmlData = xml.etree.ElementTree.fromstring(xmlData)
            xmlData.attrib['id'] = PluginID
            xmls.WriteXmlFile("special://home/addons/plugin.video.emby-next-gen/addon.xml", xmlData)

            # rename settings folder
            Utils.delFolder("special://profile/addon_data/%s/" % PluginID)
            Utils.renameFolder("special://profile/addon_data/%s/" % PluginIDPrevious, "special://profile/addon_data/%s/" % PluginID)

            # Restart App
            xbmc.executebuiltin('RestartApp')

    def System_OnWake(self):
        if not self.sleep:
            LOG.warning("System.OnSleep was never called, skip System.OnWake")
            return

        LOG.info("--<[ sleep ]")
        self.sleep = False
        self.EmbyServer_ReconnectAll()
        self.QueryDataThread = threading.Thread(target=self.QueryData)
        self.QueryDataThread.start()
        self.WebserviceStart()
        self.WebServiceThread.Update_EmbyServers(self.EmbyServers)
        Utils.SyncPause = False

    def System_OnSleep(self):
        LOG.info("-->[ sleep ]")
        Utils.SyncPause = True
        self.QuitThreads()
        self.sleep = True

    # Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self):
        xbmc.sleep(1000)
        UpdateItems = self.QueueItemsStatusupdate     #.copy()
        self.QueueItemsStatusupdate = ()
        self.QueryItemStatusThread = None

        for UpdateItem in UpdateItems:
            data = json.loads(UpdateItem)
            item = None
            kodi_fileId = None
            server_id = None

            if 'item' in data:
                kodi_id = data['item']['id']
                media = data['item']['type']
            else:
                kodi_id = data['id']
                media = data['type']

            for server_id in self.EmbyServers:
                embydb = database.db_open.DBOpen(Utils.DatabaseFiles, server_id)
                item = embydb.get_full_item_by_kodi_id_complete(kodi_id, media)
                database.db_open.DBClose(server_id, False)

                if item:
                    kodi_fileId = item[5]
                    break

            if not item:
                return

            if 'item' in data and 'playcount' in data:
                if str(item[0]) not in self.player.ItemSkipUpdate:  # Check EmbyID
                    if media in ("tvshow", "season"):
                        LOG.info("[ VideoLibrary_OnUpdate skip playcount %s/%s ]" % (media, item[0]))
                    else:
                        if str(item[0]) not in self.player.ItemSkipUpdate:
                            self.player.ItemSkipUpdate.append(str(item[0]))

                        LOG.info("[ VideoLibrary_OnUpdate update playcount episode/%s ]" % item[0])
                        self.EmbyServers[server_id].API.item_played(item[0], bool(data['playcount']))
                else:
                    LOG.info("[ VideoLibrary_OnUpdate skip playcount episode/%s ]" % item[0])
            else:
                if str(item[0]) not in self.player.ItemSkipUpdate:
                    self.player.ItemSkipUpdate.append(str(item[0]))

                videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
                BookmarkItem = videodb.get_bookmark(kodi_fileId)
                FileItem = videodb.get_files(kodi_fileId)
                database.db_open.DBClose("video", False)

                if not BookmarkItem:
                    LOG.info("[ VideoLibrary_OnUpdate reset progress episode/%s ]" % item[0])
                    self.EmbyServers[server_id].API.set_progress(item[0], 0, FileItem[3], FileItem[4])

def BackupRestore():
    RestoreFolder = xbmcgui.Dialog().browseSingle(type=0, heading='Select Backup', shares='files', defaultt=Utils.backupPath)
    MinVersionPath = "%s%s" % (RestoreFolder, 'minimumversion.txt')

    if not Utils.checkFileExists(MinVersionPath):
        Utils.dialog("notification", heading=Utils.addon_name, icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", message=Utils.Translate(33224), sound=False)
        return

    BackupVersion = Utils.readFileString(MinVersionPath)

    if BackupVersion != Utils.MinimumVersion:
        Utils.dialog("notification", heading=Utils.addon_name, icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", message=Utils.Translate(33225), sound=False)
        return

    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    _, files = Utils.listDir(Utils.FolderAddonUserdata)

    for Filename in files:
        Utils.delFile("%s%s" % (Utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = Utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby') or Filename.startswith('My') or Filename.startswith('Textures'):
            Utils.delFile("special://profile/Database/%s" % Filename)

    Utils.delete_playlists()
    Utils.delete_nodes()
    RestoreFolderAddonData = "%s/addon_data/%s/" % (RestoreFolder, Utils.PluginId)
    Utils.copytree(RestoreFolderAddonData, Utils.FolderAddonUserdata)
    RestoreFolderDatabase = "%s/Database/" % RestoreFolder
    Utils.copytree(RestoreFolderDatabase, "special://profile/Database/")
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    xbmc.executebuiltin('RestartApp')

# This method will sync all Kodi artwork to textures13.db and cache them locally. This takes diskspace!
def cache_textures():
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    xbmc.executebuiltin('activatewindow(home)')
    LOG.info("<[ cache textures ]")
    EnableWebserver = False
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserver"}}'))
    webServerEnabled = (result['result']['value'] or False)

    if not webServerEnabled:
        if not Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33227)):
            return

        EnableWebserver = True

    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverpassword"}}'))

    if not result['result']['value']:  # set password, cause mandatory in Kodi 19
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "services.webserverpassword", "value": "kodi"}}')
        webServerPass = 'kodi'
        Utils.dialog("ok", heading=Utils.addon_name, line1=Utils.Translate(33228))
    else:
        webServerPass = str(result['result']['value'])

    if EnableWebserver:
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "services.webserver", "value": True}}')
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserver"}}'))
        webServerEnabled = (result['result']['value'] or False)

    if not webServerEnabled:  # check if webserver is now enabled
        Utils.dialog("ok", heading=Utils.addon_name, line1=Utils.Translate(33103))
        return

    Utils.set_settings_bool('artworkcacheenable', False)
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverport"}}'))
    webServerPort = str(result['result']['value'] or "")
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverusername"}}'))
    webServerUser = str(result['result']['value'] or "")
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverssl"}}'))
    webServerSSL = (result['result']['value'] or False)

    if webServerSSL:
        webServerUrl = "https://127.0.0.1:%s" % webServerPort
    else:
        webServerUrl = "http://127.0.0.1:%s" % webServerPort

    if Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33044)):
        LOG.info("[ delete all thumbnails ]")

        if Utils.checkFolderExists('special://thumbnails/'):
            dirs, _ = Utils.listDir('special://thumbnails/')

            for directory in dirs:
                _, files = Utils.listDir('special://thumbnails/%s' % directory)

                for Filename in files:
                    cached = 'special://thumbnails/%s%s' % (directory, Filename)
                    Utils.delFile(cached)
                    LOG.debug("DELETE cached %s" % cached)

        texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
        texturedb.delete_tables("Texture")
        database.db_open.DBClose("texture", True)

    # Select content to be cached
    choices = [Utils.Translate(33121), Utils.Translate(33257), Utils.Translate(33258)]
    selection = Utils.dialog("multi", Utils.Translate(33256), choices)
    CacheMusic = False
    CacheVideo = False
    selection = selection[0]

    if selection == 0:
        CacheMusic = True
        CacheVideo = True
    elif selection == 1:
        CacheVideo = True
    elif selection == 2:
        CacheMusic = True

    if CacheVideo:
        videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
        urls = videodb.common_db.get_urls()
        database.db_open.DBClose("video", False)
        CacheAllEntries(webServerUrl, urls, "video", webServerUser, webServerPass)

    if CacheMusic:
        musicdb = database.db_open.DBOpen(Utils.DatabaseFiles, "music")
        urls = musicdb.common_db.get_urls()
        database.db_open.DBClose("music", False)
        CacheAllEntries(webServerUrl, urls, "music", webServerUser, webServerPass)

    Utils.set_settings_bool('artworkcacheenable', True)

# Cache all entries
def CacheAllEntries(webServerUrl, urls, Label, webServerUser, webServerPass):
    progress_updates = xbmcgui.DialogProgressBG()
    progress_updates.create("Emby", Utils.Translate(33045))
    total = len(urls)

    with requests.Session() as session:
        for index, url in enumerate(urls):
            Value = int((float(float(index)) / float(total)) * 100)
            progress_updates.update(Value, message="%s: %s / %s" % (Utils.Translate(33045), Label, index))

            if Utils.SystemShutdown:
                break

            if url[0]:
                url = quote_plus(url[0])
                url = quote_plus(url)
                UrlSend = "%s/image/image://%s" % (webServerUrl, url)

                try:
                    session.head(UrlSend, auth=(webServerUser, webServerPass))
                except:
                    LOG.warning("Artwork caching interrupted. %s / %s" % (Label, UrlSend))
                    break

    progress_updates.close()

# Reset both the emby database and the kodi database.
def databasereset(EmbyServers):
    if not Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33074)):
        return

    LOG.warning("[ reset kodi ]")
    Utils.SyncPause = True
    DeleteTextureCache = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33086))
    DeleteSettings = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33087))
    xbmc.executebuiltin('Dialog.Close(addonsettings)')
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    xbmc.executebuiltin('activatewindow(home)')
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
    videodb.common_db.delete_tables("Video")
    database.db_open.DBClose("video", True)
    musicdb = database.db_open.DBOpen(Utils.DatabaseFiles, "music")
    musicdb.common_db.delete_tables("Music")
    database.db_open.DBClose("music", True)
    ServerIds = list(EmbyServers)

    for ServerId in ServerIds:
        DBPath = "special://profile/Database/emby_%s.db" % ServerId
        Utils.delFile(DBPath)

        if DeleteTextureCache:
            Utils.DeleteThumbnails()
            texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
            texturedb.delete_tables("Texture")
            database.db_open.DBClose("texture", True)

        if DeleteSettings:
            Utils.set_settings("MinimumSetup", "")
            SettingsPath = "%s%s" % (Utils.FolderAddonUserdata, "settings.xml")
            Utils.delFile(SettingsPath)
            ServerFile = "%s%s" % (Utils.FolderAddonUserdata, 'servers_%s.json' % ServerId)
            Utils.delFile(ServerFile)
            LOG.info("[ reset settings ]")

        SyncFile = "%s%s" % (Utils.FolderAddonUserdata, 'sync_%s.json' % ServerId)
        Utils.delFile(SyncFile)

    Utils.delete_playlists()
    Utils.delete_nodes()
    Utils.dialog("ok", heading=Utils.addon_name, line1=Utils.Translate(33088))
    xbmc.executebuiltin('RestartApp')

def get_next_episodes(Handle, libraryname):
    Handle = int(Handle)
    params = {
        'sort': {'order': 'descending', 'method': 'lastplayed'},
        'filter': {
            'and': [
                {'operator': 'true', 'field': 'inprogress', 'value': ''},
                {'operator': 'is', 'field': 'tag', 'value': '%s' % libraryname}
            ]},
        'properties': ['title', 'studio', 'mpaa', 'file', 'art']
    }

    result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': "2.0", 'id': 1, 'method': 'VideoLibrary.GetTVShows', 'params': params})))
    items = result['result']['tvshows']
    list_li = []

    for item in items:
        params = {
            'tvshowid': item['tvshowid'],
            'sort': {'method': "episode"},
            'filter': {
                'and': [
                    {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                    {'operator': "greaterthan", 'field': "season", 'value': "0"}]
            },
            'properties': [
                "title", "playcount", "season", "episode", "showtitle", "plot", "file", "rating", "resume", "streamdetails", "firstaired", "writer", "dateadded", "lastplayed", "originaltitle", "seasonid", "specialsortepisode", "specialsortseason", "userrating", "votes", "cast", "art", "uniqueid"
            ],
            'limits': {"end": 1}
        }
        result = json.loads(xbmc.executeJSONRPC(json.dumps({'jsonrpc': "2.0", 'id': 1, 'method': 'VideoLibrary.GetEpisodes', 'params': params})))
        episodes = result['result']['episodes']

        for episode in episodes:
            FilePath = episode["file"]
            li = Utils.CreateListitem("episode", episode)
            list_li.append((FilePath, li, False))

    xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle)

def reset_device_id():
    Utils.device_id = ""
    Utils.get_device_id(True)
    Utils.dialog("ok", heading=Utils.addon_name, line1=Utils.Translate(33033))
    xbmc.executebuiltin('RestartApp')

# Emby backup
def Backup():
    if not Utils.backupPath:
        Utils.dialog("notification", heading=Utils.addon_name, icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", message=Utils.Translate(33229), sound=False)
        return None

    path = Utils.backupPath
    folder_name = "Kodi%s - %s-%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2], xbmc.getInfoLabel('System.Date(yyyy-mm-dd)'), xbmc.getInfoLabel('System.Time(hh:mm:ss xx)'))
    folder_name = Utils.dialog("input", heading=Utils.Translate(33089), defaultt=folder_name)

    if not folder_name:
        return None

    backup = "%s%s/" % (path, folder_name)

    if Utils.checkFolderExists(backup):
        if not Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33090)):
            return Backup()

        Utils.delFolder(backup)

    destination_data = "%saddon_data/%s/" % (backup, Utils.PluginId)
    destination_databases = "%sDatabase/" % backup
    Utils.mkDir(backup)
    Utils.mkDir("%saddon_data/" % backup)
    Utils.mkDir(destination_data)
    Utils.mkDir(destination_databases)

#    if not xbmcvfs.mkdirs(path) or not xbmcvfs.mkdirs(destination_databases):
#        LOG.info("Unable to create all directories")
#        Utils.dialog("notification", heading=Utils.addon_name, icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", message=Utils.Translate(33165), sound=False)
#        return None

    Utils.copytree(Utils.FolderAddonUserdata, destination_data)
    _, files = Utils.listDir("special://profile/Database/")

    for Temp in files:
        if 'MyVideos' in Temp:
            Utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'emby' in Temp:
            Utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'MyMusic' in Temp:
            Utils.copyFile("special://profile/Database/%s" % Temp, "%s/%s" % (destination_databases, Temp))
            LOG.info("copied %s" % Temp)

    Utils.writeFileString("%s%s" % (backup, 'minimumversion.txt'), Utils.MinimumVersion)
    LOG.info("backup completed")
    Utils.dialog("ok", heading=Utils.addon_name, line1="%s %s" % (Utils.Translate(33091), backup))
    return None

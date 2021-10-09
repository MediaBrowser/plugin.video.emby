# -*- coding: utf-8 -*-
import json
import threading
import socket
import os
import xml.etree.ElementTree
import requests
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import helper.loghandler
import helper.jsonrpc
import helper.context
import helper.pluginmenu
import helper.utils as Utils
import helper.xmls as xmls
import database.db_open
import emby.emby
from . import webservice
from . import player

if Utils.Python3:
    from urllib.parse import quote_plus
else:
    from urllib import quote_plus

LOG = helper.loghandler.LOG('EMBY.hooks.monitor.Monitor')


class Monitor(xbmc.Monitor):
    def __init__(self, PluginCommands):
        self.WebServiceThread = None
        self.WebserviceStart()
        self.sleep = False
        self.EmbyServers = {}
        self.PluginCommands = PluginCommands
        self.player = player.PlayerEvents()
        self.player.StartUp(self.EmbyServers)  # python 2.X workaround
        self.Context = helper.context.Context(self.EmbyServers)
        self.Menu = helper.pluginmenu.Menu(self.EmbyServers, self.player)
        self.texturecache_running = False
        self.QueryDataThread = threading.Thread(target=self.QueryData)
        self.QueryDataThread.start()

    def RunLibraryJobs(self):  # Run queue jobs for multiserver
        ServerIds = list(self.EmbyServers.keys()) # prevents error -> dictionary changed size during iteration

        for ServerId in ServerIds:
            self.EmbyServers[ServerId].library.RunJobs()

    def WebserviceStart(self):
        if self.WebServiceThread:
            self.WebServiceThread.close()
            self.WebServiceThread.join()
            self.WebServiceThread = None

        self.WebServiceThread = webservice.WebService()
        self.WebServiceThread.start()

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

            Data = Incomming.split(";")

            if Data[0] == 'browse':
                self.Menu.browse(Data[7], Data[1], Data[2], Data[3], Data[4], Data[5], Data[6])
            elif Data[0] == 'nextepisodes':
                get_next_episodes(Data[3], Data[1])
            elif Data[0] == 'favepisodes':
                self.Menu.favepisodes(Data[3])
            elif Data[0] == 'managelibsselection':
                threading.Thread(target=self.Menu.select_managelibs).start()
            elif Data[0] == 'texturecache':
                threading.Thread(target=self.cache_textures).start()
            elif Data[0] == 'restartservice':
                self.PluginCommands.put("restart")
            elif Data[0] == 'databasereset':
                threading.Thread(target=self.databasereset).start()
            elif Data[0] == 'delete':
                threading.Thread(target=self.Context.delete_item, args=(True,)).start()
            elif Data[0] == 'settings':
                threading.Thread(target=xbmc.executebuiltin, args=('Addon.OpenSettings(%s)' % Utils.PluginId,)).start()
            elif Data[0] == 'listing':
                self.Menu.listing(Data[3])

            request = "DONE"
            client.send(request.encode())

    def onSettingsChanged(self):
        threading.Thread(target=self.settingschanged).start()

    def onNotification(self, sender, method, data):
        if self.sleep:
            LOG.info("System.OnSleep detected, ignore monitor request.")
            return

        if method == 'Other.managelibsselection':
            threading.Thread(target=self.Menu.select_managelibs).start()
        elif method == 'Other.backup':
            threading.Thread(target=self.Backup).start()
        elif method == 'Other.restore':
            threading.Thread(target=self.BackupRestore).start()
        elif method == 'Other.reset_device_id':
            threading.Thread(target=reset_device_id).start()
        elif method == 'Other.addserver':
            threading.Thread(target=self.ServerConnect, args=(None,)).start()
        elif method == 'Other.adduserselection':
            threading.Thread(target=self.Menu.select_adduser).start()
        elif method == 'Other.databasereset':
            threading.Thread(target=self.databasereset).start()
        elif method == 'Other.texturecache':
            xbmc.executebuiltin('Dialog.Close(addonsettings)')
            xbmc.executebuiltin('Dialog.Close(addoninformation)')
            xbmc.executebuiltin('activatewindow(home)')
            threading.Thread(target=self.cache_textures).start()
        elif method == 'Other.context':
            threading.Thread(target=self.Context.select_menu).start()
        elif method == 'Other.restartservice':
            self.PluginCommands.put("restart")
        elif method == 'System.OnWake':
            threading.Thread(target=self.System_OnWake).start()
        elif method == 'System.OnSleep':
            threading.Thread(target=self.System_OnSleep).start()
        elif method == 'System.OnQuit':
            threading.Thread(target=self.System_OnQuit).start()
        elif method == 'Application.OnVolumeChanged':
            threading.Thread(target=self.player.SETVolume, args=(data,)).start()
        elif method == 'VideoLibrary.OnUpdate':
            threading.Thread(target=self.VideoLibrary_OnUpdate, args=(data,)).start()

    def EmbyServer_ReconnectAll(self):
        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.ServerReconnect()

    def EmbyServer_DisconnectAll(self):
        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.stop()

    def onScanStarted(self, library):
        LOG.info("-->[ kodi scan/%s ]" % library)

        if library == "music":
            if not Utils.KodiDBLockMusic.locked():
                Utils.KodiDBLockMusic.acquire()
        else:
            if not Utils.KodiDBLockVideo.locked():
                Utils.KodiDBLockVideo.acquire()

    def onScanFinished(self, library):
        LOG.info("--<[ kodi scan/%s ]" % library)

        if library == "music":
            if Utils.KodiDBLockMusic.locked():
                Utils.KodiDBLockMusic.release()
        else:
            if Utils.KodiDBLockVideo.locked():
                Utils.KodiDBLockVideo.release()

    def ServerConnect(self, ServerSettings):
        EmbyServerObj = emby.emby.EmbyServer(self.UserDataChanged, ServerSettings, self.RunLibraryJobs)
        server_id, EmbyServer = EmbyServerObj.register()

        if not server_id or server_id == 'cancel' or xbmc.Monitor().waitForAbort(0.1):
            LOG.error("EmbyServer Connect error")
            return

        self.EmbyServers[server_id] = EmbyServer

        if self.WebServiceThread:
            self.WebServiceThread.Update_EmbyServers(self.EmbyServers, self.player)

            if not ServerSettings:  # First run
                threading.Thread(target=self.EmbyServers[server_id].library.select_libraries, args=("AddLibrarySelection",)).start()

        xbmc.executebuiltin('UpdateLibrary(video)')

        if not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

    def UserDataChanged(self, server_id, UserDataList, UserId):
        if UserId != self.EmbyServers[server_id].user_id:
            return

        LOG.info("[ UserDataChanged ] %s" % UserDataList)
        UpdateData = []

        for ItemData in UserDataList:
            if ItemData['ItemId'] not in self.player.ItemSkipUpdate:  # Check EmbyID
                UpdateData.append(ItemData)
            else:
                LOG.info("[ UserDataChanged skip update/%s ]" % ItemData['ItemId'])

                if 'ItemId' in self.player.PlayingItem:
                    if self.player.PlayingItem['ItemId'] != str(ItemData['ItemId']):
                        self.player.ItemSkipUpdate.remove(str(ItemData['ItemId']))
                else:
                    self.player.ItemSkipUpdate.remove(str(ItemData['ItemId']))

        if UpdateData:
            self.EmbyServers[server_id].library.userdata(UpdateData)

    def System_OnQuit(self):
        for EmbyServer in list(self.EmbyServers.values()):
            if self.player.Transcoding:
                EmbyServer.API.close_transcode()

        self.PluginCommands.put('stop')

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

    def settingschanged(self):
        if self.sleep or Utils.SkipUpdateSettings:
            Utils.SkipUpdateSettings -= 1

            if Utils.SkipUpdateSettings < 0:
                Utils.SkipUpdateSettings = 0

            return

        xspplaylistsPreviousValue = Utils.xspplaylists
        compatibilitymodePreviousValue = Utils.compatibilitymode
        Utils.InitSettings()

        for EmbyServer in list(self.EmbyServers.values()):
            EmbyServer.API.update_settings()

        # Toggle xsp playlists
        if xspplaylistsPreviousValue != Utils.xspplaylists:
            if Utils.xspplaylists:
                for EmbyServer in list(self.EmbyServers.values()):
                    EmbyServer.Views.update_nodes()
            else:
                # delete playlists
                for playlistfolder in [Utils.FolderPlaylistsVideo, Utils.FolderPlaylistsMusic]:
                    if xbmcvfs.exists(playlistfolder):
                        _, files = xbmcvfs.listdir(playlistfolder)

                        for Filename in files:
                            xbmcvfs.delete(os.path.join(playlistfolder, Filename))

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
                XMLFile = Utils.translatePath("special://home/addons/plugin.video.emby-next-gen/resources/skins/default/1080i/") + PatchFile
                xmlData = xml.etree.ElementTree.parse(XMLFile).getroot()

                for elem in xmlData.iter():
                    if elem.tag == 'label':
                        if elem.text.find(PluginIDPrevious) != -1:
                            elem.text = elem.text.replace(PluginIDPrevious, PluginID)

                xmls.WriteXmlFile(XMLFile, xmlData)

            # update addon.xml id
            xmlData = xml.etree.ElementTree.parse(Utils.FileAddonXML).getroot()
            xmlData.attrib['id'] = PluginID
            xmls.WriteXmlFile(Utils.FileAddonXML, xmlData)

            # rename settings folder
            SourceFolder = Utils.translatePath("special://profile/addon_data/%s/" % PluginIDPrevious)
            DestinationFolder = Utils.translatePath("special://profile/addon_data/%s/" % PluginID)

            if xbmcvfs.exists(DestinationFolder):
                folders, files = xbmcvfs.listdir(DestinationFolder)

                for Foldername in folders:
                    SearchSubFolder = os.path.join(DestinationFolder, Foldername)
                    _, subfolderfiles = xbmcvfs.listdir(SearchSubFolder)

                    for SubfolderFilename in subfolderfiles:
                        xbmcvfs.delete(os.path.join(SearchSubFolder, SubfolderFilename))

                    xbmcvfs.rmdir(SearchSubFolder, False)

                for filename in files:
                    xbmcvfs.delete(os.path.join(DestinationFolder, filename))

                xbmcvfs.rmdir(DestinationFolder, False)

            xbmcvfs.rename(SourceFolder, DestinationFolder)

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
        self.WebServiceThread.Update_EmbyServers(self.EmbyServers, self.player)
        Utils.SyncPause = False

    def System_OnSleep(self):
        LOG.info("-->[ sleep ]")
        Utils.SyncPause = True
        self.QuitThreads()
        self.sleep = True
        self.PluginCommands.put("sleep")

    # Mark as watched/unwatched updates
    def VideoLibrary_OnUpdate(self, data):
        data = json.loads(data)

        if 'item' in data and 'playcount' in data:
            kodi_id = data['item']['id']
            media = data['item']['type']

            for server_id in self.EmbyServers:
                embydb = database.db_open.DBOpen(Utils.DatabaseFiles, server_id)
                item = embydb.get_full_item_by_kodi_id_complete(kodi_id, media)
                database.db_open.DBClose(server_id, False)

                if item:
                    if str(item[0]) not in self.player.ItemSkipUpdate:  # Check EmbyID
                        if media in ("season", "tvshow"):
                            return

                        self.player.ItemSkipUpdate.append(str(item[0]))
                        LOG.info("[ VideoLibrary_OnUpdate update/%s ]" % item[0])
                        self.EmbyServers[server_id].API.item_played(item[0], bool(data['playcount']))
                    else:
                        LOG.info("[ VideoLibrary_OnUpdate skip update/%s ]" % item[0])

                    return

    def BackupRestore(self):
        RestoreFolder = xbmcgui.Dialog().browseSingle(type=0, heading='Select Backup', shares='files', defaultt=Utils.backupPath)
        MinVersionPath = os.path.join(RestoreFolder, 'minimumversion.txt')

        if not xbmcvfs.exists(MinVersionPath):
            Utils.dialog("notification", heading="{emby}", icon="{emby}", message="Invalid backup path", sound=False)
            return

        infile = xbmcvfs.File(MinVersionPath)
        BackupVersion = infile.read()
        infile.close()

        if BackupVersion != Utils.MinimumVersion:
            Utils.dialog("notification", heading="{emby}", icon="{emby}", message="Invalid backup", sound=False)
            return

        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        self.PluginCommands.put('stop')
        xbmc.sleep(5000)
        _, files = xbmcvfs.listdir(Utils.FolderAddonUserdata)

        for Filename in files:
            xbmcvfs.delete(os.path.join(Utils.FolderAddonUserdata, Filename))

        # delete database
        _, files = xbmcvfs.listdir(Utils.FolderDatabase)

        for Filename in files:
            if Filename.startswith('emby') or Filename.startswith('My') or Filename.startswith('Textures'):
                xbmcvfs.delete(os.path.join(Utils.FolderDatabase, Filename))

        Utils.delete_playlists()
        Utils.delete_nodes()
        RestoreFolderAddonData = os.path.join(RestoreFolder, "addon_data", Utils.PluginId)
        Utils.copytree(RestoreFolderAddonData, Utils.FolderAddonUserdata)
        RestoreFolderDatabase = os.path.join(RestoreFolder, "Database")
        Utils.copytree(RestoreFolderDatabase, Utils.FolderDatabase)
        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        xbmc.executebuiltin('RestartApp')

    # This method will sync all Kodi artwork to textures13.dband cache them locally. This takes diskspace!
    def cache_textures(self):
        LOG.info("<[ cache textures ]")

        if self.texturecache_running:
            Utils.dialog("notification", heading="{emby}", icon="{emby}", message="Artwork chache in progress", sound=False)
            return

        EnableWebserver = False
        get_setting = helper.jsonrpc.JSONRPC('Settings.GetSettingValue')
        result = helper.jsonrpc.JSONRPC('Settings.GetSettingValue').execute({'setting': "services.webserver"})
        webServerEnabled = (result['result']['value'] or False)

        if not webServerEnabled:
            if not Utils.dialog("yesno", heading="{emby}", line1="Webserver must be enabled for artwork cache. Enable now?"):
                return

            EnableWebserver = True

        result = get_setting.execute({'setting': "services.webserverpassword"})

        if not result['result']['value']:  # set password, cause mandatory in Kodi 19

            helper.jsonrpc.JSONRPC('Settings.SetSettingValue').execute({'setting': "services.webserverpassword", 'value': 'kodi'})
            webServerPass = 'kodi'
            Utils.dialog("ok", heading="{emby}", line1="No password found, set password to 'kodi'")
        else:
            webServerPass = str(result['result']['value'])

        if EnableWebserver:
            helper.jsonrpc.JSONRPC('Settings.SetSettingValue').execute({'setting': "services.webserver", 'value': True})
            result = helper.jsonrpc.JSONRPC('Settings.GetSettingValue').execute({'setting': "services.webserver"})
            webServerEnabled = (result['result']['value'] or False)

        if not webServerEnabled:  # check if webserver is now enabled
            Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33103))
            return

        result = get_setting.execute({'setting': "services.webserverport"})
        webServerPort = str(result['result']['value'] or "")
        result = get_setting.execute({'setting': "services.webserverusername"})
        webServerUser = str(result['result']['value'] or "")
        result = get_setting.execute({'setting': "services.webserverssl"})
        webServerSSL = (result['result']['value'] or False)

        if webServerSSL:
            webServerUrl = "https://127.0.0.1:%s" % webServerPort
        else:
            webServerUrl = "http://127.0.0.1:%s" % webServerPort

        if Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33044)):
            LOG.info("[ delete all thumbnails ]")

            if xbmcvfs.exists(Utils.FolderThumbnails):
                dirs, _ = xbmcvfs.listdir(Utils.FolderThumbnails)

                for directory in dirs:
                    _, files = xbmcvfs.listdir(os.path.join(Utils.FolderThumbnails, directory))

                    for Filename in files:
                        cached = os.path.join(Utils.FolderThumbnails, directory, Filename)
                        xbmcvfs.delete(cached)
                        LOG.debug("DELETE cached %s" % cached)

            texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
            texturedb.delete_tables("Texture")
            database.db_open.DBClose("texture", True)

        videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
        urls = videodb.common_db.get_urls()
        database.db_open.DBClose("video", False)
        threading.Thread(target=self.CacheAllEntries, args=(webServerUrl, urls, "video", webServerUser, webServerPass,)).start()
        musicdb = database.db_open.DBOpen(Utils.DatabaseFiles, "music")
        urls = musicdb.common_db.get_urls()
        database.db_open.DBClose("music", False)
        threading.Thread(target=self.CacheAllEntries, args=(webServerUrl, urls, "music", webServerUser, webServerPass,)).start()

    # Cache all entries
    def CacheAllEntries(self, webServerUrl, urls, Label, webServerUser, webServerPass):
        self.texturecache_running = True
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", Utils.Translate(33045))
        total = len(urls)

        with requests.Session() as session:
            for index, url in enumerate(urls):
                Value = int((float(float(index)) / float(total)) * 100)
                progress_updates.update(Value, message="%s: %s" % (Utils.Translate(33045), Label + ": " + str(index)))

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
        self.texturecache_running = False

    # Reset both the emby database and the kodi database.
    def databasereset(self):
        if not Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33074)):
            return

        LOG.warning("[ reset kodi ]")
        DeleteTextureCache = Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33086))
        DeleteSettings = Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33087))
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
        self.PluginCommands.put("stop")

        if xbmc.Monitor().waitForAbort(5):
            return

        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
        videodb.common_db.delete_tables("Video")
        database.db_open.DBClose("video", True)
        musicdb = database.db_open.DBOpen(Utils.DatabaseFiles, "music")
        musicdb.common_db.delete_tables("Music")
        database.db_open.DBClose("music", True)
        _, ServerIds, _ = self.Menu.get_EmbyServerList()

        for ServerId in ServerIds:
            DBPath = os.path.join(Utils.FolderDatabase, 'emby_%s.db' % ServerId)

            if xbmcvfs.exists(DBPath):
                xbmcvfs.delete(DBPath)

            if DeleteTextureCache:
                Utils.DeleteThumbnails()
                texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
                texturedb.delete_tables("Texture")
                database.db_open.DBClose("texture", True)

            if DeleteSettings:
                SettingsPath = os.path.join(Utils.FolderAddonUserdata, "settings.xml")

                if xbmcvfs.exists(SettingsPath):
                    xbmcvfs.delete(SettingsPath)

                ServerFile = os.path.join(Utils.FolderAddonUserdata, 'servers_%s.json' % ServerId)

                if xbmcvfs.exists(ServerFile):
                    xbmcvfs.delete(ServerFile)

                LOG.info("[ reset settings ]")

            SyncFile = os.path.join(Utils.FolderAddonUserdata, 'sync_%s.json' % ServerId)

            if xbmcvfs.exists(SyncFile):
                xbmcvfs.delete(SyncFile)

        Utils.delete_playlists()
        Utils.delete_nodes()
        Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33088))
        xbmc.executebuiltin('RestartApp')


def get_next_episodes(Handle, libraryname):
    Handle = int(Handle)
    result = helper.jsonrpc.JSONRPC('VideoLibrary.GetTVShows').execute({
        'sort': {'order': "descending", 'method': "lastplayed"},
        'filter': {
            'and': [
                {'operator': "true", 'field': "inprogress", 'value': ""},
                {'operator': "is", 'field': "tag", 'value': "%s" % libraryname}
            ]},
        'properties': ['title', 'studio', 'mpaa', 'file', 'art']
    })
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
        result = helper.jsonrpc.JSONRPC('VideoLibrary.GetEpisodes').execute(params)
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
    Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33033))
    xbmc.executebuiltin('RestartApp')

# Delete objects from kodi cache
def delete_folder(path):
    LOG.debug("--[ delete folder ]")
    delete_path = path is not None
    path = path or Utils.FolderEmbyTemp
    dirs, files = xbmcvfs.listdir(path)
    delete_recursive(path, dirs)

    for Filename in files:
        xbmcvfs.delete(os.path.join(path, Filename))

    if delete_path:
        xbmcvfs.delete(path)

    LOG.warning("DELETE %s" % path)

# Delete files and dirs recursively
def delete_recursive(path, dirs):
    for directory in dirs:
        dirs2, files = xbmcvfs.listdir(os.path.join(path, directory))

        for Filename in files:
            xbmcvfs.delete(os.path.join(path, directory, Filename))

        delete_recursive(os.path.join(path, directory), dirs2)
        xbmcvfs.rmdir(os.path.join(path, directory))

# Emby backup
def Backup():
    if not Utils.backupPath:
        Utils.dialog("notification", heading="{emby}", icon="{emby}", message="No backup path set", sound=False)
        return None

    path = Utils.backupPath
    folder_name = "Kodi%s - %s-%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2], xbmc.getInfoLabel('System.Date(yyyy-mm-dd)'), xbmc.getInfoLabel('System.Time(hh:mm:ss xx)'))
    folder_name = Utils.dialog("input", heading=Utils.Translate(33089), defaultt=folder_name)

    if not folder_name:
        return None

    backup = os.path.join(path, folder_name)

    if xbmcvfs.exists(backup + '/'):
        if not Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33090)):
            return Backup()

        delete_folder(backup)

    destination_data = os.path.join(backup, "addon_data", Utils.PluginId)
    destination_databases = os.path.join(backup, "Database")

    if not xbmcvfs.mkdirs(path) or not xbmcvfs.mkdirs(destination_databases):
        LOG.info("Unable to create all directories")
        Utils.dialog("notification", heading="{emby}", icon="{emby}", message=Utils.Translate(33165), sound=False)
        return None

    Utils.copytree(Utils.FolderAddonUserdata, destination_data)
    _, files = xbmcvfs.listdir(Utils.FolderDatabase)

    for Temp in files:
        if 'MyVideos' in Temp:
            xbmcvfs.copy(os.path.join(Utils.FolderDatabase, Temp), os.path.join(destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'emby' in Temp:
            xbmcvfs.copy(os.path.join(Utils.FolderDatabase, Temp), os.path.join(destination_databases, Temp))
            LOG.info("copied %s" % Temp)
        elif 'MyMusic' in Temp:
            xbmcvfs.copy(os.path.join(Utils.FolderDatabase, Temp), os.path.join(destination_databases, Temp))
            LOG.info("copied %s" % Temp)

    outfile = xbmcvfs.File(os.path.join(backup, 'minimumversion.txt'), "w")
    outfile.write(Utils.MinimumVersion)
    outfile.close()
    LOG.info("backup completed")
    Utils.dialog("ok", heading="{emby}", line1="%s %s" % (Utils.Translate(33091), backup))
    return None

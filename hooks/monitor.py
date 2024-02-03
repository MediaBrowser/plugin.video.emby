import json
from _thread import start_new_thread
import xbmc
import xbmcvfs
from helper import pluginmenu, utils, playerops, xmls, player, queue
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
FavoriteUpdatedByEmby = False
utils.FavoriteQueue = queue.Queue()
EventQueue = queue.Queue()

class monitor(xbmc.Monitor):
    def onNotification(self, sender, method, data):
        if method == "Player.OnPlay":
            player.PlayerEvents.put((("play", data),))
        elif method == "Player.OnStop":
            player.PlayerEvents.put((("stop", data),))
        elif method == 'Player.OnSeek':
            player.PlayerEvents.put((("seek", data),))
        elif method == "Player.OnAVChange":
            player.PlayerEvents.put((("avchange",),))
        elif method == "Player.OnAVStart":
            player.PlayerEvents.put((("avstart", data),))
        elif method == "Player.OnPause":
            player.PlayerEvents.put("pause")
        elif method == "Player.OnResume":
            player.PlayerEvents.put("resume")
        elif method == 'Application.OnVolumeChanged':
            player.PlayerEvents.put((("volume", data),))
        elif method == "Playlist.OnAdd":
            EventQueue.put((("playlistadd", data),))
        elif method == "Playlist.OnRemove":
            EventQueue.put((("playlistremove", data),))
        elif method == "Playlist.OnClear":
            EventQueue.put((("playlistclear",),))
        elif method == 'System.OnSleep':
            EventQueue.put((("sleep",),))
        elif method == 'System.OnWake':
            EventQueue.put((("wake",),))
        elif method == 'System.OnQuit':
            EventQueue.put((("quit",),))
        elif method == 'Other.managelibsselection':
            EventQueue.put((("managelibsselection",),))
        elif method == 'Other.settings':
            EventQueue.put((("opensettings",),))
        elif method == 'Other.backup':
            EventQueue.put((("backup",),))
        elif method == 'Other.restore':
            EventQueue.put((("restore",),))
        elif method == 'Other.skinreload':
            EventQueue.put((("skinreload",),))
        elif method == 'Other.manageserver':
            EventQueue.put((("manageserver",),))
        elif method == 'Other.databasereset':
            EventQueue.put((("databasereset",),))
        elif method == 'Other.nodesreset':
            EventQueue.put((("nodesreset",),))
        elif method == 'Other.databasevacuummanual':
            EventQueue.put((("databasevacuummanual",),))
        elif method == 'Other.factoryreset':
            EventQueue.put((("factoryreset",),))
        elif method == 'Other.downloadreset':
            EventQueue.put((("downloadreset",),))
        elif method == 'Other.texturecache':
            EventQueue.put((("texturecache",),))
        elif method == 'Other.play':
            EventQueue.put((("play", data),))
        elif method == 'VideoLibrary.OnUpdate' and not playerops.RemoteMode:  # Buffer updated items -> not overloading threads
            globals()["QueueItemsStatusupdate"] += (data,)

            if not QueryItemStatusThread:
                globals()["QueryItemStatusThread"] = True
                start_new_thread(VideoLibrary_OnUpdate, ())
        elif method == 'VideoLibrary.OnRemove' and not playerops.RemoteMode:  # Buffer updated items -> not overloading threads
            if utils.enableDeleteByKodiEvent:
                globals()["QueueItemsRemove"] += (data,)

                if not QueryItemRemoveThread:
                    globals()["QueryItemRemoveThread"] = True
                    start_new_thread(VideoLibrary_OnRemove, ())

    def onScanStarted(self, library):
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi scan / {library} ]", 1) # LOGINFO
        EventQueue.put((("scanstart", library),))

    def onScanFinished(self, library):
        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi scan / {library} ]", 1) # LOGINFO
        EventQueue.put((("scanstop", library),))

    def onCleanStarted(self, library):
        xbmc.log(f"EMBY.hooks.monitor: -->[ kodi clean / {library} ]", 1) # LOGINFO
        EventQueue.put((("cleanstart", library),))

    def onCleanFinished(self, library):
        xbmc.log(f"EMBY.hooks.monitor: --<[ kodi clean / {library} ]", 1) # LOGINFO
        EventQueue.put((("cleanstop", library),))

    def onSettingsChanged(self):
        xbmc.log("EMBY.hooks.monitor: Seetings changed", 1) # LOGINFO
        EventQueue.put((("settingschanged",),))

def monitor_EventQueue(): # Threaded / queued
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Kodi events ]", 0) # LOGDEBUG
    SleepMode = False

    while True:
        Events = EventQueue.getall()
        xbmc.log(f"EMBY.hooks.monitor: Event: {Events}", 0) # LOGDEBUG

        for Event in Events:
            if Event == "QUIT":
                xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Kodi events ]", 0) # LOGDEBUG
                return

            if Event[0] in ("scanstart", "cleanstart", "scanstop", "cleanstop") and playerops.RemoteMode:
                xbmc.log("EMBY.hooks.monitor: kodi scan skipped due to remote mode", 1) # LOGINFO
                continue

            if Event[0] in ("scanstart", "cleanstart"):
                utils.SyncPause['kodi_rw'] = True
            elif Event[0] in ("scanstop", "cleanstop"):
                if Event[0] == "scanstop" and utils.WidgetRefresh[Event[1]]:
                    utils.WidgetRefresh[Event[1]] = False

                if not utils.WidgetRefresh['music'] and not utils.WidgetRefresh['video']:
                    utils.SyncPause['kodi_rw'] = False
                    start_new_thread(syncEmby, ())
            elif Event[0] == "sleep":
                if SleepMode:
                    xbmc.log("EMBY.hooks.monitor: System.OnSleep in progress, skip System.OnSleep", 2) # LOGWARNING
                    continue

                SleepMode = True
                xbmc.log("EMBY.hooks.monitor: -->[ sleep ]", 1) # LOGINFO
                utils.SyncPause['kodi_sleep'] = True

                if not player.PlayBackEnded and player.PlayingItem[4]:
                    player.PlayerEvents.put((("stop", '{"end":"sleep"}'),))

                    while not player.PlayerEvents.isEmpty():
                        utils.sleep(0.5)

                EmbyServer_DisconnectAll()
            elif Event[0] == "wake":
                if not SleepMode:
                    xbmc.log("EMBY.hooks.monitor: System.OnSleep was never called, skip System.OnWake", 2) # LOGWARNING
                    continue

                xbmc.log("EMBY.hooks.monitor: --<[ sleep ]", 1) # LOGINFO
                SleepMode = False
                EmbyServer_ReconnectAll()
                utils.SyncPause['kodi_sleep'] = False
            elif Event[0] == "managelibsselection":
                start_new_thread(pluginmenu.select_managelibs, ())
            elif Event[0] == "opensettings":
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
            elif Event[0] == "backup":
                start_new_thread(Backup, ())
            elif Event[0] == "restore":
                start_new_thread(BackupRestore, ())
            elif Event[0] == "skinreload":
                start_new_thread(pluginmenu.reset_querycache, (None,)) # Clear Cache
                xbmc.executebuiltin('ReloadSkin()')
                xbmc.log("EMBY.hooks.monitor: Reload skin by notification", 1) # LOGINFO
            elif Event[0] == "manageserver":
                start_new_thread(pluginmenu.manage_servers, (ServerConnect,))
            elif Event[0] == "databasereset":
                start_new_thread(pluginmenu.databasereset, ())
            elif Event[0] == "nodesreset":
                start_new_thread(utils.nodesreset, ())
            elif Event[0] == "databasevacuummanual":
                start_new_thread(dbio.DBVacuum, ())
            elif Event[0] == "factoryreset":
                start_new_thread(pluginmenu.factoryreset, ())
            elif Event[0] == "downloadreset":
                start_new_thread(pluginmenu.downloadreset, ())
            elif Event[0] == "texturecache":
                if not utils.artworkcacheenable:
                    utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
                else:
                    start_new_thread(pluginmenu.cache_textures, ())
            elif Event[0] == "settingschanged":
                start_new_thread(settingschanged, ())
            elif Event[0] == "playlistclear":
                player.NowPlayingQueue = [[], []]
                player.PlaylistKodiItems = [[], []]
            elif Event[0] == "playlistremove":
                globals()["PlaylistItemsRemove"] += (Event[1],)

                if not PlaylistItemRemoveThread:
                    globals()["PlaylistItemRemoveThread"] = True
                    start_new_thread(Playlist_Remove, ())
            elif Event[0] == "playlistadd":
                globals()["PlaylistItemsAdd"] += (Event[1],)

                if not PlaylistItemAddThread:
                    globals()["PlaylistItemAddThread"] = True
                    start_new_thread(Playlist_Add, ())
            elif Event[0] == "quit":
                xbmc.log("EMBY.hooks.monitor: System_OnQuit", 1) # LOGINFO
                utils.SystemShutdown = True
                utils.SyncPause = {}
                webservice.close()
                EmbyServer_DisconnectAll()
                xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Kodi events ]", 0) # LOGDEBUG
                return

def syncEmby():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ syncEmby ]", 0) # LOGDEBUG

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.library.RunJobs()

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ syncEmby ]", 0) # LOGDEBUG

def get_Favorites():
    Result = utils.SendJson('{"jsonrpc":"2.0", "method":"Favourites.GetFavourites", "params":{"properties":["windowparameter", "path", "thumbnail", "window"]}, "id": 1}').get("result", {})

    if Result:
        Favorites = Result.get("favourites", [])

        if not Favorites: # Favorites can be "None"
            return []

        return Favorites

    return []

def monitor_KodiFavorites():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Kodi favorites ]", 0) # LOGDEBUG
    globals()['FavoriteUpdatedByEmby'] = False
    ItemsReadOutPrev = get_Favorites()
    FavoriteTimestamp = 0

    while True:
        if utils.sleep(0.5):
            xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Kodi favorites ]", 0) # LOGDEBUG
            return

        Stats = xbmcvfs.Stat(utils.KodiFavFile)
        TimestampReadOut = Stats.st_mtime()

        if FavoriteUpdatedByEmby:
            globals()['FavoriteUpdatedByEmby'] = False
            ItemsReadOutPrev = get_Favorites()
            continue

        if FavoriteTimestamp < TimestampReadOut:
            Trigger = bool(FavoriteTimestamp)
            FavoriteTimestamp = TimestampReadOut
            ItemsReadOut = get_Favorites()

            if Trigger:
                DeltaFavRemoved = []
                DeltaFavAdded = []

                for ItemReadOutPrev in ItemsReadOutPrev:
                    if ItemReadOutPrev not in ItemsReadOut:
                        DeltaFavRemoved.append(ItemReadOutPrev)

                for ItemReadOut in ItemsReadOut:
                    if ItemReadOut not in ItemsReadOutPrev:
                        DeltaFavAdded.append(ItemReadOut)

                # filter fav doubles
                ItemsReadOutPathes = []

                for ItemReadOut in ItemsReadOut:
                    if 'path' in ItemReadOut:
                        ItemsReadOutPathes.append(ItemReadOut['path'])
                    elif 'windowparameter' in ItemReadOut:
                        ItemsReadOutPathes.append(ItemReadOut['windowparameter'])
                    else:
                        ItemsReadOutPathes.append("")

                DoubleDetected = False

                for Index, ItemReadOut in enumerate(ItemsReadOut):
                    if 'path' in ItemReadOut:
                        CompareValue = ItemReadOut["path"]
                    elif 'windowparameter' in ItemReadOut:
                        CompareValue = ItemReadOut["windowparameter"]
                    else:
                        continue

                    if Index != len(ItemsReadOut):
                        if CompareValue in ItemsReadOutPathes[Index + 1:]:
                            globals()['FavoriteUpdatedByEmby'] = True

                            if 'path' in ItemReadOut:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemReadOut["type"]}", "title":"{ItemReadOut["title"]}", "thumbnail":"{ItemReadOut["thumbnail"]}", "path":"{ItemReadOut["path"]}"}}, "id": 1}}')
                            else:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemReadOut["type"]}", "title":"{ItemReadOut["title"]}", "thumbnail":"{ItemReadOut["thumbnail"]}", "windowparameter":"{ItemReadOut["windowparameter"]}", "window":"{ItemReadOut["window"]}"}}, "id": 1}}')

                            DoubleDetected = True
                            break

                if DoubleDetected:
                    ItemsReadOutPrev = get_Favorites()
                    continue

                xbmc.log("EMBY.hooks.monitor: Kodi favorites changed", 1) # LOGINFO
                ItemsReadOutStr = str(ItemsReadOut)

                for Item in DeltaFavRemoved:
                    Link = ""

                    if 'path' in Item:
                        Link = Item['path']
                        mod_MediaFav(Link, False)
                    elif 'windowparameter' in Item:
                        Link = Item['windowparameter']

                        if Link.startswith("videodb://movies/genres/") or Link.startswith("videodb://tvshows/genres/") or Link.startswith("videodb://musicvideos/genres/"):
                            Temp = Link.split("/")
                            ItemMod = Item.copy()
                            ItemMod.update({'windowparameter': f"videodb://movies/genres/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Movies)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://tvshows/genres/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (TVShows)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://musicvideos/genres/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Musicvideos)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/tags/") or Link.startswith("videodb://tvshows/tags/") or Link.startswith("videodb://musicvideos/tags/"):
                            Temp = Link.split("/")
                            ItemMod = Item.copy()
                            ItemMod.update({'windowparameter': f"videodb://movies/tags/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Movies)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://tvshows/tags/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (TVShows)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://musicvideos/tags/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Musicvideos)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/actors/") or Link.startswith("videodb://tvshows/actors/") or Link.startswith("videodb://musicvideos/actors/"):
                            Temp = Link.split("/")
                            ItemMod = Item.copy()
                            ItemMod.update({'windowparameter': f"videodb://movies/actors/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Movies)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://tvshows/actors/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (TVShows)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://musicvideos/actors/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Musicvideos)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/studios/") or Link.startswith("videodb://tvshows/studios/") or Link.startswith("videodb://musicvideos/studios/"):
                            Temp = Link.split("/")
                            ItemMod = Item.copy()
                            ItemMod.update({'windowparameter': f"videodb://movies/studios/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Movies)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://tvshows/studios/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (TVShows)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                            ItemMod.update({'windowparameter': f"videodb://musicvideos/studios/{Temp[4]}/", 'title': f"{ItemMod['title'][:ItemMod['title'].find(' (')]} (Musicvideos)"})

                            if ItemMod in ItemsReadOut:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{ItemMod["type"]}", "title":"{ItemMod["title"]}", "thumbnail":"{ItemMod["thumbnail"]}", "windowparameter":"{ItemMod["windowparameter"]}", "window":"{ItemMod["window"]}"}}, "id": 1}}')

                    if Link:
                        set_Favorite_Emby(Link, False)

                for Item in DeltaFavAdded:
                    if 'path' in Item:
                        Link = Item['path']
                        mod_MediaFav(Link, True)
                    elif 'windowparameter' in Item:
                        Link = Item['windowparameter']
                        NewLink = ""
                        Pos = Link.find("/?")

                        if Pos != -1:
                            globals()['FavoriteUpdatedByEmby'] = True
                            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                            NewLink = f"{Link[:Pos]}/"

                        if Link.startswith("videodb://inprogresstvshows/"):
                            if not NewLink:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                                NewLink = Link.replace("videodb://inprogresstvshows/", "videodb://tvshows/titles/")
                            else:
                                NewLink = NewLink.replace("videodb://inprogresstvshows/", "videodb://tvshows/titles/")

                        if Link.startswith("videodb://movies/genres/") or Link.startswith("videodb://tvshows/genres/") or Link.startswith("videodb://musicvideos/genres/"):
                            globals()['FavoriteUpdatedByEmby'] = True
                            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                            Temp = Link.split("/")
                            video_db = dbio.DBOpenRO("video", "Favorites_genres")
                            Itemname, hasMusicVideos, hasMovies, hasTVShows = video_db.get_Genre_Name(Temp[4])
                            dbio.DBCloseRO("video", "Favorites_genres")

                            if hasMovies:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Movies)", "windowparameter":"videodb://movies/genres/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasMusicVideos:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Musicvideos)", "windowparameter":"videodb://musicvideos/genres/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasTVShows:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (TVShows)", "windowparameter":"videodb://tvshows/genres/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/tags/") or Link.startswith("videodb://tvshows/tags/") or Link.startswith("videodb://musicvideos/tags/"):
                            globals()['FavoriteUpdatedByEmby'] = True
                            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                            Temp = Link.split("/")
                            video_db = dbio.DBOpenRO("video", "Favorites_tags")
                            Itemname, hasMusicVideos, hasMovies, hasTVShows = video_db.get_Tag_Name(Temp[4])
                            dbio.DBCloseRO("video", "Favorites_tags")

                            if hasMovies:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Movies)", "windowparameter":"videodb://movies/tags/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasMusicVideos:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Musicvideos)", "windowparameter":"videodb://musicvideos/tags/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasTVShows:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (TVShows)", "windowparameter":"videodb://tvshows/tags/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/actors/") or Link.startswith("videodb://tvshows/actors/") or Link.startswith("videodb://musicvideos/actors/"):
                            globals()['FavoriteUpdatedByEmby'] = True
                            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                            Temp = Link.split("/")
                            video_db = dbio.DBOpenRO("video", "Favorites_actors")
                            Itemname, ImageUrl, hasMusicVideos, hasMovies, hasTVShows = video_db.get_People(Temp[4])
                            dbio.DBCloseRO("video", "Favorites_actors")

                            if hasMovies:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Movies)", "thumbnail":"{ImageUrl}", "windowparameter":"videodb://movies/actors/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasMusicVideos:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Musicvideos)", "thumbnail":"{ImageUrl}", "windowparameter":"videodb://musicvideos/actors/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasTVShows:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (TVShows)", "thumbnail":"{ImageUrl}", "windowparameter":"videodb://tvshows/actors/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                        if Link.startswith("videodb://movies/studios/") or Link.startswith("videodb://tvshows/studios/") or Link.startswith("videodb://musicvideos/studios/"):
                            globals()['FavoriteUpdatedByEmby'] = True
                            utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{Item["windowparameter"]}", "window":"{Item["window"]}"}}, "id": 1}}')
                            Temp = Link.split("/")
                            video_db = dbio.DBOpenRO("video", "Favorites_studios")
                            Itemname, hasMusicVideos, hasMovies, hasTVShows = video_db.get_Studio_Name(Temp[4])
                            dbio.DBCloseRO("video", "Favorites_studios")

                            if hasMovies:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Movies)", "windowparameter":"videodb://movies/studios/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasMusicVideos:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (Musicvideos)", "windowparameter":"videodb://musicvideos/studios/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                            if hasTVShows:
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"window", "title":"{Itemname} (TVShows)", "windowparameter":"videodb://tvshows/studios/{Temp[4]}/", "window":"10025"}}, "id": 1}}')

                        if NewLink:
                            # Check for doubles
                            if f"'{NewLink}'" not in ItemsReadOutStr:
                                globals()['FavoriteUpdatedByEmby'] = True
                                utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Item["type"]}", "title":"{Item["title"]}", "thumbnail":"{Item["thumbnail"]}", "windowparameter":"{NewLink}", "window":"{Item["window"]}"}}, "id": 1}}')
                                set_Favorite_Emby(NewLink, True)
                        else:
                            set_Favorite_Emby(Link, True)

            ItemsReadOutPrev = get_Favorites()

def mod_MediaFav(Path, isFavorite):
    if Path.startswith("http://127.0.0.1:57342/") or Path.startswith("/emby_addon_mode/"):
        Path = Path.replace("http://127.0.0.1:57342/", "").replace("/emby_addon_mode/", "")
        ServerId = Path.split("/")[1]
        EmbyId = Path[Path.rfind("/"):].split("-")[1]
        utils.ItemSkipUpdate += [int(EmbyId)]
        xbmc.log(f"EMBY.hooks.monitor: ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGDEBUG
        utils.EmbyServers[ServerId].API.favorite(EmbyId, isFavorite)

def set_Favorite_Emby(Path, isFavorite):
    EmbyType = ""
    KodiId = -1
    SeasonNumber = -1

    if Path.startswith("videodb://tvshows/titles/"):
        Temp = Path.split("/")

        if Temp[5]:
            KodiId = Temp[4]
            SeasonNumber = Temp[5]
            EmbyType = "Season"
        else: # TVShow
            KodiId = Temp[4]
            EmbyType = "Series"
    elif Path.startswith("videodb://movies/sets/"):
        Temp = Path.split("/")
        KodiId = Temp[4]
        EmbyType = "BoxSet"
    elif Path.startswith("videodb://movies/genres/") or Path.startswith("videodb://tvshows/genres/") or Path.startswith("videodb://musicvideos/genres/"):
        Temp = Path.split("/")
        KodiId = Temp[4]
        EmbyType = "Genre"
    elif Path.startswith("videodb://movies/tags/") or Path.startswith("videodb://tvshows/tags/") or Path.startswith("videodb://musicvideos/tags/"):
        Temp = Path.split("/")
        KodiId = Temp[4]
        EmbyType = "Tag"
    elif Path.startswith("videodb://movies/actors/") or Path.startswith("videodb://tvshows/actors/") or Path.startswith("videodb://musicvideos/actors/"):
        Temp = Path.split("/")
        KodiId = Temp[4]
        EmbyType = "Person"
    elif Path.startswith("videodb://movies/studios/") or Path.startswith("videodb://tvshows/studios/") or Path.startswith("videodb://musicvideos/studios/"):
        Temp = Path.split("/")
        KodiId = Temp[4]
        EmbyType = "Studio"
    elif Path.startswith("special://profile/playlists/mixed/"):
        Temp = Path.split("/")
        KodiId = Temp[5][:-4]
        EmbyType = "Playlist"
    elif Path.startswith("musicdb://genres/"):
        Temp = Path.split("/")
        KodiId = Temp[3]
        EmbyType = "MusicGenre"

    if SeasonNumber != -1:
        videodb = dbio.DBOpenRO("video", "Favorites")
        KodiId = videodb.get_seasonid_by_showid_number(KodiId, SeasonNumber)
        dbio.DBCloseRO("video", "Favorites")

    if KodiId != -1:
        for ServerId, EmbyServer in list(utils.EmbyServers.items()):
            SQLs = dbio.DBOpenRW(ServerId, "Favorites", {})
            EmbyId = SQLs['emby'].get_item_by_KodiId_EmbyType(KodiId, EmbyType)
            SQLs["emby"].update_favourite(isFavorite, EmbyId, EmbyType)
            dbio.DBCloseRW(ServerId, "Favorites", {})

            if EmbyId:
                if str(EmbyId).startswith("999999993"): # fake collection tag
                    EmbyId = str(EmbyId).replace("999999993", "")

                utils.ItemSkipUpdate += [int(EmbyId)]
                xbmc.log(f"EMBY.hooks.monitor: ItemSkipUpdate favorite update: {utils.ItemSkipUpdate}", 0) # LOGDEBUG
                EmbyServer.API.favorite(EmbyId, isFavorite)
                break

def mod_Favorite(): # Threaded / queued
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Kodi favorites mods ]", 0) # LOGDEBUG

    while True:
        Favorites = utils.FavoriteQueue.getall()

        if Favorites == ("QUIT",):
            xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Kodi favorites mods ]", 0) # LOGDEBUG
            return

        if not utils.SyncFavorites:
            continue

        KodiFavsContent = get_Favorites()
        ItemsReadOutPathes = []

        for KodiFavContent in KodiFavsContent:
            if 'path' in KodiFavContent:
                ItemsReadOutPathes.append(KodiFavContent['path'])
            elif 'windowparameter' in KodiFavContent:
                ItemsReadOutPathes.append(KodiFavContent['windowparameter'])
            else:
                ItemsReadOutPathes.append("")

        for Favorite in Favorites:
            if Favorite[2] in ItemsReadOutPathes:
                Position = ItemsReadOutPathes.index(Favorite[2])
            else:
                Position = -1

            if Favorite[1] and Position == -1:
                globals()['FavoriteUpdatedByEmby'] = True
                Label = Favorite[3].replace('"', "'")
                xbmc.log(f"EMBY.helper.monitor: Add Kodi favorites {Label} / {Favorite[1]} / {Position}", 1) # LOGINFO

                if Favorite[4] == "window":
                    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Favorite[4]}", "title":"{Label}", "thumbnail":"{Favorite[0]}", "windowparameter":"{Favorite[2]}", "window":"{Favorite[5]}"}}, "id": 1}}')
                else:
                    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Favorite[4]}", "title":"{Label}", "thumbnail":"{Favorite[0]}", "path":"{Favorite[2]}"}}, "id": 1}}')
            if not Favorite[1] and Position != -1:
                globals()['FavoriteUpdatedByEmby'] = True
                xbmc.log(f"EMBY.helper.monitor: Remove Kodi favorites {Favorite[3]} / {Favorite[1]} / {Position}", 1) # LOGINFO

                if Favorite[4] == "window":
                    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{KodiFavsContent[Position]["type"]}", "title":"{KodiFavsContent[Position]["title"]}", "windowparameter":"{KodiFavsContent[Position]["windowparameter"]}", "window":"{KodiFavsContent[Position]["window"]}"}}, "id": 1}}')
                else:
                    utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{KodiFavsContent[Position]["type"]}", "title":"{KodiFavsContent[Position]["title"]}", "path":"{KodiFavsContent[Position]["path"]}"}}, "id": 1}}')

# Remove Items
def VideoLibrary_OnRemove(): # Cache queries to minimize database openings
    if utils.sleep(0.5):
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnRemove ]", 0) # LOGDEBUG
    RemoveItems = QueueItemsRemove
    globals().update({"QueueItemsRemove": (), "QueryItemRemoveThread": False})

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33264)):
        for ServerId, EmbyServer in list(utils.EmbyServers.items()):
            embydb = dbio.DBOpenRO(ServerId, "VideoLibrary_OnRemove")

            for RemoveItem in RemoveItems:
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

            dbio.DBCloseRO(ServerId, "VideoLibrary_OnRemove")

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnRemove ]", 0) # LOGDEBUG

def Playlist_Add():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Playlist_Add ]", 0) # LOGDEBUG
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
                    EmbyId = embydb.get_EmbyId_by_KodiId_KodiType(UpdateItemPlaylist[1], UpdateItemPlaylist[2])

                    if not EmbyId:
                        PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]] = 0 # No Emby server Item
                        continue

                PlaylistItemsNew[PlaylistIndex][UpdateItemPlaylist[0]] = EmbyId

        dbio.DBCloseRO(ServerId, "Playlist_Add")

    # Sort playlist
    for PlaylistIndex in range(2):
        for Position, EmbyId in list(PlaylistItemsNew[PlaylistIndex].items()):
            player.PlaylistKodiItems[PlaylistIndex].insert(Position, EmbyId)

    player.build_NowPlayingQueue()
    player.PlayerEvents.put("playlistupdate")
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Playlist_Add ]", 0) # LOGDEBUG

def Playlist_Remove():
    if utils.sleep(0.5): # Cache queries
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ Playlist_Remove ]", 0) # LOGDEBUG
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
    player.PlayerEvents.put("playlistupdate")
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ Playlist_Remove ]", 0) # LOGDEBUG

# Mark as watched/unwatched updates
def VideoLibrary_OnUpdate():
    if utils.sleep(0.5): # Cache queries to minimize database openings and redeuce threads
        return

    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ VideoLibrary_OnUpdate ]", 0) # LOGDEBUG
    UpdateItems = QueueItemsStatusupdate
    globals().update({"QueueItemsStatusupdate": (), "QueryItemStatusThread": False})
    ItemsSkipUpdateRemove = []

    for server_id, EmbyServer in list(utils.EmbyServers.items()):
        EmbyUpdateItems = {}
        embydb = None
        EmbyId = ""

        for UpdateItem in UpdateItems:
            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate process item: {UpdateItem}", 1) # LOGINFO
            data = json.loads(UpdateItem)

            # Update dynamic item
            EmbyId = ""
            KodiType = ""

            if 'item' in data:
                ItemId = int(data['item']['id'])

                if ItemId > 1000000000:
                    EmbyId = ItemId - 1000000000
                    KodiType = data['item']['type']
            else:
                ItemId = int(data['id'])

                if ItemId > 1000000000:
                    EmbyId = ItemId - 1000000000
                    KodiType = data['type']

            if EmbyId:
                xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate dynamic item detected: {EmbyId}", 1) # LOGINFO
            else: # Update synced item
                if 'item' in data:
                    kodi_id = data['item']['id']
                    KodiType = data['item']['type']
                else:
                    kodi_id = data['id']
                    KodiType = data['type']

                if not embydb:
                    embydb = dbio.DBOpenRO(server_id, "VideoLibrary_OnUpdate")

                EmbyId = embydb.get_EmbyId_by_KodiId_KodiType(kodi_id, KodiType)

            if not EmbyId:
                continue

            if int(EmbyId) not in ItemsSkipUpdateRemove:
                ItemsSkipUpdateRemove.append(int(EmbyId))

            if KodiType in utils.KodiTypeMapping:
                pluginmenu.reset_querycache(utils.KodiTypeMapping[KodiType])

            if 'item' in data and 'playcount' in data:
                if KodiType in ("tvshow", "season"):
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {KodiType} / {EmbyId} ]", 1) # LOGINFO
                    continue

                if f"KODI{EmbyId}" not in utils.ItemSkipUpdate:  # Check EmbyID
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate update playcount {EmbyId} ]", 1) # LOGINFO

                    if int(EmbyId) in EmbyUpdateItems:
                        EmbyUpdateItems[int(EmbyId)]['PlayCount'] = data['playcount']
                        EmbyUpdateItems[int(EmbyId)]['EmbyItem'] = EmbyId
                    else:
                        EmbyUpdateItems[int(EmbyId)] = {'PlayCount': data['playcount'], 'EmbyItem': EmbyId}
                else:
                    xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate skip playcount {EmbyId} ]", 1) # LOGINFO
            else:
                if 'item' not in data:
                    if f"KODI{EmbyId}" not in utils.ItemSkipUpdate and int(EmbyId):  # Check EmbyID
                        if not f"{{'item':{UpdateItem}}}" in UpdateItems:
                            xbmc.log(f"EMBY.hooks.monitor: [ VideoLibrary_OnUpdate reset progress {EmbyId} ]", 1) # LOGINFO

                            if int(EmbyId) in EmbyUpdateItems:
                                EmbyUpdateItems[int(EmbyId)]['Progress'] = 0
                                EmbyUpdateItems[int(EmbyId)]['EmbyItem'] = EmbyId
                            else:
                                EmbyUpdateItems[int(EmbyId)] = {'Progress': 0, 'EmbyItem': EmbyId}
                        else:
                            xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (UpdateItems) {EmbyId}", 1) # LOGINFO
                    else:
                        xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate skip reset progress (ItemSkipUpdate) {EmbyId}", 1) # LOGINFO

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
        ItemSkipUpdateRemoveCompare = f"KODI{ItemSkipUpdateRemove}"

        if ItemSkipUpdateRemoveCompare in utils.ItemSkipUpdate:
            utils.ItemSkipUpdate.remove(ItemSkipUpdateRemoveCompare)

    xbmc.log(f"EMBY.hooks.monitor: VideoLibrary_OnUpdate ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGINFO
    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ VideoLibrary_OnUpdate ]", 0) # LOGDEBUG

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
    RestoreFolderAddonData = f"{RestoreFolder}/addon_data/plugin.video.emby-next-gen/"
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
    folder_name = f"Kodi{xbmc.getInfoLabel('System.BuildVersion')[:2]} - {xbmc.getInfoLabel('System.Date(yyyy-mm-dd)')} {xbmc.getInfoLabel('System.Time(hh:mm:ss xx)').replace(':', '-')}"
    folder_name = utils.Dialog.input(heading=utils.Translate(33089), defaultt=folder_name)

    if not folder_name:
        return None

    backup = f"{path}{folder_name}/"

    if utils.checkFolderExists(backup):
        if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33090)):
            return Backup()

        utils.delFolder(backup)

    destination_data = f"{backup}addon_data/plugin.video.emby-next-gen/"
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
    utils.InitSettings()

    # Http2 mode or curltimeouts changed, rebuild advanced settings -> restart Kodi
    if enablehttp2Previous != utils.enablehttp2 or curltimeoutsPreviousValue != utils.curltimeouts:
        if xmls.advanced_settings():
            RestartKodi = True

    # path(substitution) changed, update database pathes
    if AddonModePathPreviousValue != utils.AddonModePath:
        SQLs = dbio.DBOpenRW("video", "settingschanged", {})
        SQLs["video"].toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("video", "settingschanged", {})
        SQLs = dbio.DBOpenRW("music", "settingschanged", {})
        SQLs["music"].toggle_path(AddonModePathPreviousValue, utils.AddonModePath)
        dbio.DBCloseRW("music", "settingschanged", {})
        utils.refresh_widgets(True)
        utils.refresh_widgets(False)

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

    # Toggle collection tags
    if curlBoxSetsToTagsPreviousValue != utils.BoxSetsToTags:
        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.Views.add_nodes_root(False)
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

    # Chnage download path
    if DownloadPathPreviousValue != utils.DownloadPath:
        pluginmenu.downloadreset(DownloadPathPreviousValue)

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ reload settings ]", 0) # LOGDEBUG

def ServersConnect():
    xbmc.log("EMBY.hooks.monitor: THREAD: --->[ ServersConnect ]", 0) # LOGDEBUG

    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            utils.SyncPause = {}
            xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ] shutdown", 0) # LOGDEBUG
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
        xbmc.log("EMBY.hooks.monitor: Reload skin on connection established", xbmc.LOGINFO)

    xbmc.log("EMBY.hooks.monitor: THREAD: ---<[ ServersConnect ]", 0) # LOGDEBUG

def setup():
    # copy default nodes
    utils.mkDir("special://profile/library/video/")
    utils.mkDir("special://profile/library/music/")
    utils.copytree("special://xbmc/system/library/video/", "special://profile/library/video/")
    utils.copytree("special://xbmc/system/library/music/", "special://profile/library/music/")

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

        utils.update_mode_settings()
        xbmc.log(f"EMBY.hooks.monitor: Add-on playback: {utils.useDirectPaths == '0'}", 1) # LOGINFO
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        xmls.sources() # verify sources.xml

        if xmls.advanced_settings(): # verify advancedsettings.xml
            return False

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
        start_new_thread(mod_Favorite, ())
        start_new_thread(monitor_EventQueue, ())
        start_new_thread(ServersConnect, ())

        # Waiting/blocking function till Kodi stops
        xbmc.log("EMBY.hooks.monitor: Monitor listening", 1) # LOGINFO
        XbmcMonitor = monitor()  # Init Monitor
        start_new_thread(monitor_KodiFavorites, ())
        XbmcMonitor.waitForAbort(0)

        # Shutdown
        utils.FavoriteQueue.put("QUIT")
        EventQueue.put("QUIT")

        if player.PlayingItem[4]:
            player.stop_playback(False, False)
            xbmc.sleep(2000)

        for RemoteCommandQueue in list(playerops.RemoteCommandQueue.values()):
            RemoteCommandQueue.put("QUIT")

        utils.SyncPause = {}
        webservice.close()
        EmbyServer_DisconnectAll()
        xbmc.log("EMBY.hooks.monitor: [ Shutdown Emby-next-gen ]", 2) # LOGWARNING

    player.PlayerEvents.put("QUIT")
    utils.XbmcPlayer = None
    utils.SystemShutdown = True

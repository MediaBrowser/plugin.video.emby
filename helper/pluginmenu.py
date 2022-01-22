# -*- coding: utf-8 -*-
import threading
import unicodedata
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from database import dbio
from emby import listitem
from . import xmls
from . import loghandler
from . import utils

if utils.Python3:
    from urllib.parse import urlencode
else:
    from urllib import urlencode

LOG = loghandler.LOG('EMBY.helper.pluginmenu')


class Menu:
    def __init__(self, EmbyServers, player):
        self.EmbyServers = EmbyServers
        self.player = player
        self.ListItemData = []
        self.PluginMenuActive = False

    # Add directory listitem. context should be a list of tuples [(label, action)*]
    def add_ListItem(self, label, path, folder, artwork, fanart):
        li = xbmcgui.ListItem(label, path=path)
        li.setArt({"thumb": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png", "fanart": fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png"})
        self.ListItemData.append((path, li, folder))

    # Build plugin menu
    def listing(self, Handle):
        self.ListItemData = []
        self.PluginMenuActive = True

        for server_id in self.EmbyServers:
            for Node in self.EmbyServers[server_id].Views.Nodes:
                label = utils.StringDecode(Node['title'])
                node = utils.StringDecode(Node['type'])
                LOG.debug("--[ listing/%s/%s ] %s" % (node, label, Node['path']))
                self.add_ListItem(label, Node['path'], True, Node['icon'], None)

        # Common Items
        Handle = int(Handle)
        self.add_ListItem(utils.Translate(30180), "library://video/emby_Favorite_movies.xml", True, None, None)
        self.add_ListItem(utils.Translate(30181), "library://video/emby_Favorite_tvshows.xml", True, None, None)
        self.add_ListItem(utils.Translate(30182), "plugin://%s/?mode=favepisodes" % utils.PluginId, True, None, None)

        if utils.menuOptions:
            self.add_ListItem(utils.Translate(33194), "plugin://%s/?mode=managelibsselection"  % utils.PluginId, False, None, None)
            self.add_ListItem(utils.Translate(33059), "plugin://%s/?mode=texturecache"  % utils.PluginId, False, None, None)
            self.add_ListItem(utils.Translate(5), "plugin://%s/?mode=settings"  % utils.PluginId, False, None, None)
            self.add_ListItem(utils.Translate(33058), "plugin://%s/?mode=databasereset"  % utils.PluginId, False, None, None)

        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'movies')
        xbmcplugin.endOfDirectory(Handle)

    def get_EmbyServerList(self):
        EmbyServersCounter = len(self.EmbyServers)
        ServerIds = list(self.EmbyServers)
        ServerItems = []

        for server_id in self.EmbyServers:
            ServerItems.append(self.EmbyServers[server_id].Name)

        return EmbyServersCounter, ServerIds, ServerItems

    def select_managelibs(self):  # threaded by monitor.py
        EmbyServersCounter, _, ServerItems = self.get_EmbyServerList()

        if EmbyServersCounter > 1:
            Selection = xbmcgui.Dialog().select(utils.Translate(33194), ServerItems)

            if Selection > -1:
                self.manage_libraries(Selection)
        else:
            if EmbyServersCounter > 0:
                self.manage_libraries(0)

    def manage_libraries(self, ServerSelection):  # threaded by caller
        MenuItems = [utils.Translate(33098), utils.Translate(33154), utils.Translate(33140), utils.Translate(33184), utils.Translate(33139), utils.Translate(33060), utils.Translate(33234)]
        Selection = xbmcgui.Dialog().select(utils.Translate(33194), MenuItems)
        ServerIds = list(self.EmbyServers)
        EmbyServerId = ServerIds[ServerSelection]

        if Selection == 0:
            self.EmbyServers[EmbyServerId].library.refresh_boxsets()
        elif Selection == 1:
            self.EmbyServers[EmbyServerId].library.select_libraries("AddLibrarySelection")
        elif Selection == 2:
            self.EmbyServers[EmbyServerId].library.select_libraries("RepairLibrarySelection")
        elif Selection == 3:
            self.EmbyServers[EmbyServerId].library.select_libraries("RemoveLibrarySelection")
        elif Selection == 4:
            self.EmbyServers[EmbyServerId].library.select_libraries("UpdateLibrarySelection")
        elif Selection == 5:
            self.SyncThemes(EmbyServerId)
        elif Selection == 6:
            self.SyncLiveTV(EmbyServerId)

    def select_adduser(self):
        EmbyServersCounter, ServerIds, ServerItems = self.get_EmbyServerList()

        if EmbyServersCounter > 1:
            Selection = xbmcgui.Dialog().select(utils.Translate(33054), ServerItems)

            if Selection > -1:
                AddUser(self.EmbyServers[ServerIds[Selection]])
        else:
            if EmbyServersCounter > 0:
                AddUser(self.EmbyServers[ServerIds[0]])

    def favepisodes(self, Handle):
        Handle = int(Handle)
        list_li = []
        episodes_kodiId = ()

        for server_id in self.EmbyServers:
            embydb = dbio.DBOpen(server_id)
            episodes_kodiId = embydb.get_episode_fav()
            dbio.DBClose(server_id, False)

        for episode_kodiId in episodes_kodiId:
            Details = utils.load_VideoitemFromKodiDB("episode", str(episode_kodiId[0]))
            FilePath = Details["file"]
            li = utils.CreateListitem("episode", Details)
            list_li.append((FilePath, li, False))

        xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'episodes')
        xbmcplugin.endOfDirectory(Handle)

    # Browse dynamically content
    def browse(self, Handle, media, view_id, folder, name, extra, server_id):
        if not server_id or server_id == 'None':
            return

        if not self.wait_online(server_id):
            return

        Handle = int(Handle)
        folder = folder.lower() if folder else None
        LOG.info("--[ v:%s/%s ] %s" % (view_id, media, folder))

        if folder is None:
            self.browse_subfolders(Handle, media, view_id, name, server_id)
            return

        if folder == 'letter':
            self.browse_letters(Handle, media, view_id, name, server_id)
            return

        # Mapping
        KodiMediaID = {'musicvideos': 'musicvideos', 'tvshows': 'tvshows', 'music': 'artists', 'movies': 'movies', 'livetv': 'videos', 'channels': 'songs', 'boxsets': 'movies', 'playlists': 'movies', 'Season': 'tvshows', 'Episode': 'episodes', 'MusicVideos': 'musicvideos', 'MusicAlbum': 'albums', 'Songs': 'songs', 'Folder': 'videos', 'PhotoAlbum': 'images', 'Photo': 'images', 'homevideos': 'images', 'mixed': 'mixed', 'Genre': 'videos', 'audiobooks': 'music', 'podcasts': 'music'}
        EmbyMediaID = {'musicvideos': 'MusicVideos', 'tvshows': "Series", 'music': 'MusicArtist', 'movies': 'Movie', 'livetv': 'LiveTv', 'channels': 'Songs', 'boxsets': 'BoxSet', 'playlists': 'Movie', 'Season': 'Season', 'Episode': 'Episode', 'MusicVideos': 'MusicVideos', 'MusicAlbum': 'MusicAlbum', 'Songs': 'Songs', 'Folder': 'Folder', 'PhotoAlbum': 'PhotoAlbum', 'Photo': 'Photo', 'homevideos': 'Video,PhotoAlbum,Photo', 'mixed': 'Movie,Series,Video', 'Genre': None, 'audiobooks': 'audiobooks', 'podcasts': 'channels'}
        KodiType = KodiMediaID[media]
        EmbyType = EmbyMediaID[media]

        if self.PluginMenuActive:
            ReloadWindowId = 0
            WindowId = xbmcgui.getCurrentWindowId()

            if KodiType == "images" and WindowId in (10025, 10502):  # check if video or music navigation window is open (MyVideoNav.xml MyMusicNav.xml) -> open MyPics.xml
                ReloadWindowId = 10002
            elif KodiType in ("albums", "artists", 'music', 'songs') and WindowId in (10025, 10002):
                ReloadWindowId = 10502
            elif WindowId in (10502, 10002) == 10002:
                ReloadWindowId = 10025

            if ReloadWindowId:
                threading.Thread(target=ChangeContentWindow, args=("plugin://plugin.video.emby-next-gen/?id=%s&mode=browse&type=%s&name=%s&folder=%s&server=%s" % (view_id, media, name, folder, server_id), ReloadWindowId)).start()
                return

        if view_id:
            xbmcplugin.setPluginCategory(Handle, name)

        if extra:
            if extra == "0-9":  # Special charecters
                extra = {'NameLessThan': "A"}
            else:  # alphabet
                extra = {'NameStartsWith': extra}

            ID = view_id
        else:
            ID = folder

        # General nodes
        if folder == 'recentlyadded':
            listing = self.EmbyServers[server_id].API.get_recently_added(None, view_id, 25)
        elif folder == 'genres':
            listing = self.EmbyServers[server_id].API.get_genres(view_id)
        elif folder == 'unwatched':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'filters': ['IsUnplayed']})
        elif folder == 'favorite':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'filters': ['IsFavorite']})
        elif folder == 'inprogress':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'filters': ['IsResumable']})
        elif folder == 'boxsets':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'media': "BoxSet"})
        elif folder == 'random':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'media': EmbyType, 'random': True, 'recursive': True, 'limit': 25})
        elif (folder or "").startswith('genres-'):
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'media': None, 'extra': {'GenreIds': folder.split('-')[1]}})
        elif folder == 'folder':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': view_id, 'recursive': False})

        # Root nodes
        elif media == 'audiobooks':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "MusicArtist", 'recursive': True})
        elif media == 'musicvideos':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "MusicArtist", 'recursive': True})
        elif media == 'tvshows':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Series", 'recursive': True})
        elif media == 'music':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "MusicArtist", 'recursive': True})
        elif media == 'movies':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Movie", 'recursive': True})
        elif media == 'livetv':
            listing = self.EmbyServers[server_id].API.get_channels()
        elif media == 'channels':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Folder", 'recursive': True})
        elif media == 'boxsets':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "BoxSet", 'recursive': True})
        elif media == 'playlists':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'recursive': False})
        elif media in ('homevideos', 'PhotoAlbum'):
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Video,Folder,PhotoAlbum,Photo", 'recursive': False})
        elif media == 'mixed':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Movie,Series,Video,MusicArtist", 'recursive': False})

        # Emby Server media ID nodes
        elif media == 'Season':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Season", 'recursive': True})
        elif media == 'Episode':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Episode", 'recursive': True})
        elif media == 'MusicVideos':
            listing = self.EmbyServers[server_id].API.browse_MusicByArtistId(folder, view_id, "MusicVideos", extra)
        elif media == 'MusicAlbum':
            listing = self.EmbyServers[server_id].API.browse_MusicByArtistId(folder, view_id, "MusicAlbum", extra)
        elif media == 'Songs':
            listing = self.EmbyServers[server_id].API.browse_MusicByArtistId(folder, view_id, "Audio", extra)
        elif media == 'Folder':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'recursive': False})
        elif media == 'Photo':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Photo", 'recursive': False})
        elif media == 'Movie':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Movie", 'recursive': True})
        else:
            listing = {}

        if listing:
            list_li = []
            listing = listing if isinstance(listing, list) else listing.get('Items', [])

            for item in listing:
                if utils.SystemShutdown:
                    return

                li = listitem.set_ListItem(item, server_id)

                if item.get('IsFolder') or item['Type'] in ('MusicArtist', 'MusicAlbum'):
                    params = {
                        'id': view_id,
                        'mode': "browse",
                        'type': get_Subfolder(item['Type'], KodiType),
                        'name': name,
                        'folder': item['Id'],
                        'server': server_id
                    }

                    path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
                    list_li.append((path, li, True))
                elif item['Type'] == 'Genre':
                    params = {
                        'id': view_id or item['Id'],
                        'mode': "browse",
                        'type': get_Subfolder(item['Type'], KodiType),
                        'folder': 'genres-%s' % item['Id'],
                        'name': name,
                        'server': server_id
                    }
                    path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
                    list_li.append((path, li, True))
                else:
                    path, _ = utils.get_path_type_from_item(server_id, item)

                    if not path:
                        return

                    list_li.append((path, li, False))

            xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))

        # Set Sorting
        if media in ('homevideos', 'Photo', 'PhotoAlbum'):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
        elif media == 'playlists' or folder == 'random':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        elif media == 'Episode':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_EPISODE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
        else:
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

        xbmcplugin.setContent(Handle, KodiType)
        xbmcplugin.endOfDirectory(Handle)

    # Display submenus for emby views
    def browse_subfolders(self, Handle, media, view_id, name, server_id):
        DYNNODES = {
            'tvshows': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('genres', utils.Translate(135), 'DefaultGenre.png'),
                ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'mixed': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('inprogress', utils.Translate(30171), 'DefaultInProgressShows.png'),
                ('inprogressepisodes', utils.Translate(30178), 'DefaultInProgressShows.png'),
                ('genres', utils.Translate(135), 'DefaultGenre.png'),
                ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'movies': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMovies.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
                ('inprogress', utils.Translate(30177), 'DefaultInProgressShows.png'),
                ('boxsets', utils.Translate(20434), 'DefaultSets.png'),
                ('favorite', utils.Translate(33168), 'DefaultFavourites.png'),
                ('genres', utils.Translate(135), 'DefaultGenre.png'),
                ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'boxsets': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultSets.png'),
                ('folder', 'Folder', 'DefaultFolder.png')
            ],
            'livetv': [
                ('all', None, 'DefaultMovies.png')
            ],
            'musicvideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
                ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
                ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png')
            ],
            'homevideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultAddonVideo.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(33167), '')
            ],
            'channels': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(33167), ''),
                ('inprogress', utils.Translate(33169), ''),
                ('favorite', utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'playlists': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultPlaylist.png'),
                ('folder', 'Folder', 'DefaultFolder.png')
            ],
            'books': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(33167), ''),
                ('inprogress', utils.Translate(33169), ''),
                ('favorite', utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'audiobooks': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(33167), ''),
                ('inprogress', utils.Translate(33169), ''),
                ('favorite', utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'podcasts': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('folder', 'Folder', 'DefaultFolder.png'),
                ('recentlyadded', utils.Translate(33167), ''),
                ('inprogress', utils.Translate(33169), ''),
                ('favorite', utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'music': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultAddonMusic.png'),
                ('folder', 'Folder', 'DefaultFolder.png')
            ]
        }
        self.ListItemData = []
        xbmcplugin.setPluginCategory(Handle, name)

        for node in DYNNODES[media]:
            params = {
                'id': view_id,
                'mode': "browse",
                'type': media,
                'folder': view_id if node[0] == 'all' else node[0],
                'name': name,
                'server': server_id
            }
            path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
            self.add_ListItem(node[1] or name, path, True, node[2], None)

        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.endOfDirectory(Handle)

    # Display letters as options
    def browse_letters(self, Handle, media, view_id, name, server_id):
        letters = ["0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
        self.ListItemData = []
        xbmcplugin.setPluginCategory(Handle, name)

        for node in letters:
            params = {
                'id': view_id,
                'mode': "browse",
                'type': media,
                'extra': node,
                'folder': view_id if node[0] == 'all' else node[0],
                'name': name,
                'server': server_id
            }
            path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
            self.add_ListItem(node, path, True, None, None)

        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.endOfDirectory(Handle)

    def wait_online(self, server_id):
        for _ in range(60):  # wait for ack (60 seconds timeout)
            if server_id in self.EmbyServers:
                if self.EmbyServers[server_id].Online:
                    return True

            if utils.SystemShutdown:
                return False

        return False

    # Add theme media locally, via strm. This is only for tv tunes.
    # If another script is used, adjust this code
    def SyncThemes(self, server_id):
        views = []

        if xbmc.getCondVisibility('System.HasAddon(script.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="script.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', utils.FolderAddonUserdataLibrary)
            LOG.info("TV Tunes custom path is enabled and set.")
        elif xbmc.getCondVisibility('System.HasAddon(service.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', utils.FolderAddonUserdataLibrary)
            LOG.info("TV Tunes custom path is enabled and set.")
        else:
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33152))
            return

        for LibraryID, LibraryInfo in list(self.EmbyServers[server_id].Views.ViewItems.items()):
            if LibraryInfo[1] in ('movies', 'tvshows', 'mixed'):
                views.append(LibraryID)

        items = {}

        for view in views:
            for result in self.EmbyServers[server_id].API.get_itemsSync(view, None, False, {'HasThemeVideo': True}):
                for item in result['Items']:
                    folder = normalize_string(item['Name'])
                    items[item['Id']] = folder

            for result in self.EmbyServers[server_id].API.get_itemsSync(view, None, False, {'HasThemeSong': True}):
                for item in result['Items']:
                    folder = normalize_string(item['Name'])
                    items[item['Id']] = folder

        for ItemId, name in list(items.items()):
            nfo_path = "%s%s/" % (utils.FolderAddonUserdataLibrary, name)
            nfo_file = "%s%s" % (nfo_path, "tvtunes.nfo")
            utils.mkDir(nfo_path)
            themes = self.EmbyServers[server_id].API.get_themes(ItemId)
            paths = []

            for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
                if utils.useDirectPaths:
                    paths.append(theme['MediaSources'][0]['Path'])
                else:
                    paths.append(direct_url(server_id, theme))

            xmls.tvtunes_nfo(nfo_file, paths)

        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33153), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=1000, sound=False)

    def SyncLiveTV(self, server_id):
        if xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)') and xbmc.getCondVisibility('System.AddonIsEnabled(pvr.iptvsimple)'):
            xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
            ChannelNames = {}

            # build m3u playlist
            channels = self.EmbyServers[server_id].API.get_channels()

            if channels:
                playlist = "#EXTM3U\n"

                for item in channels['Items']:
                    ChannelNames[item['Id']] = item['Name']

                    if item['TagItems']:
                        Tag = item['TagItems'][0]['Name']
                    else:
                        Tag = "--No Info--"

                    ImageUrl = ""

                    if item['ImageTags']:
                        if 'Primary' in item['ImageTags']:
                            ImageUrl = "http://127.0.0.1:57578/embyimage-%s-%s-0-Primary-%s" % (server_id, item['Id'], item['ImageTags']['Primary'])

                    StreamUrl = "http://127.0.0.1:57578/embylivetv-%s-%s-stream.ts" % (server_id, item['Id'])
                    playlist += '#KODIPROP:mimetype=video/mp2t\n'

                    if item['Name'].find("(radio)") != -1 or item['MediaType'] != "Video":
                        playlist += '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" radio="true" group-title="%s",%s\n' % (item['Id'], item['Name'], ImageUrl, Tag, item['Name'])
                    else:
                        playlist += '#EXTINF:-1 tvg-id="%s" tvg-name="%s" tvg-logo="%s" group-title="%s",%s\n' % (item['Id'], item['Name'], ImageUrl, Tag, item['Name'])

                    playlist += "%s\n" % StreamUrl

                PlaylistFile = "%s%s" % (utils.FolderEmbyTemp, 'livetv.m3u')
                utils.writeFileString(PlaylistFile, playlist)
                iptvsimple = xbmcaddon.Addon(id="pvr.iptvsimple")
                iptvsimple.setSetting('m3uPathType', "0")
                iptvsimple.setSetting('m3uPath', PlaylistFile)

                # build epg
                epgdata = self.EmbyServers[server_id].API.get_channelprogram()

                if epgdata:
                    EPGFile = "%s%s" % (utils.FolderEmbyTemp, 'livetv.epg')
                    epg = '<?xml version="1.0" encoding="utf-8" ?>\n'
                    epg += '<tv>\n'

                    for item in epgdata['Items']:
                        temp = item['StartDate'].split("T")
                        timestampStart = temp[0].replace("-", "")
                        temp2 = temp[1].split(".")
                        timestampStart += temp2[0].replace(":", "")[:6]
                        temp2 = temp2[1].split("+")
                        timestampStart += " +" + temp2[1].replace(":", "")
                        temp = item['EndDate'].split("T")
                        timestampEnd = temp[0].replace("-", "")
                        temp2 = temp[1].split(".")
                        timestampEnd += temp2[0].replace(":", "")[:6]
                        temp2 = temp2[1].split("+")
                        timestampEnd += " +" + temp2[1].replace(":", "")
                        epg += '  <channel id="%s">\n' % item['ChannelId']
                        epg += '  <display-name lang="en">%s</display-name>\n' % ChannelNames[item['ChannelId']]
                        epg += '  </channel>\n'
                        epg += '  <programme start="%s" stop="%s" channel="%s">\n' % (timestampStart, timestampEnd, item['ChannelId'])
                        epg += '    <title lang="en">%s</title>\n' % item['Name']

                        if 'Overview' in item:
                            epg += '    <desc lang="en">%s</desc>\n' % item['Overview']

                        epg += '  </programme>\n'
                    epg += '</tv>'

                    utils.writeFileString(EPGFile, epg)
                    iptvsimple.setSetting('epgPathType', "0")
                    iptvsimple.setSetting('epgPath', EPGFile)

            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33232))
        else:
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33233))

def direct_url(server_id, item):
    FilenameURL = utils.PathToFilenameReplaceSpecialCharecters(item['Path'])

    if item['Type'] == 'Audio':
        return "http://127.0.0.1:57578/embythemeaudio-%s-%s-%s-%s-%s" % (server_id, item['Id'], item['MediaSources'][0]['Id'], "audio", FilenameURL)

    return "http://127.0.0.1:57578/embythemevideo-%s-%s-%s-%s-%s" % (server_id, item['Id'], item['MediaSources'][0]['Id'], "video", FilenameURL)

# Add or remove users from the default server session
def AddUser(EmbyServer):
    session = EmbyServer.API.get_device()
    AllUsers = EmbyServer.API.get_users(False, utils.addUsersHidden)

    if not AllUsers:
        return

    AddUserChoices = []

    for AllUser in AllUsers:
        if AllUser['Id'] != session[0]['UserId']:
            UserExists = False

            for SessionAdditionalUser in session[0]['AdditionalUsers']:
                if SessionAdditionalUser['UserId'] == AllUser['Id']:
                    UserExists = True
                    break

            if not UserExists:
                AddUserChoices.append({'UserName': AllUser['Name'], 'UserId': AllUser['Id']})

    RemoveUserChoices = []

    for SessionAdditionalUser in session[0]['AdditionalUsers']:
        RemoveUserChoices.append({'UserName': SessionAdditionalUser['UserName'], 'UserId': SessionAdditionalUser['UserId']})

    result = utils.dialog("select", utils.Translate(33061), [utils.Translate(33062), utils.Translate(33063)] if RemoveUserChoices else [utils.Translate(33062)])

    if result < 0:
        return

    if not result:  # Add user
        AddNameArray = []

        for AddUserChoice in AddUserChoices:
            AddNameArray.append(AddUserChoice['UserName'])

        resp = utils.dialog("select", utils.Translate(33064), AddNameArray)

        if resp < 0:
            return

        UserData = AddUserChoices[resp]
        EmbyServer.add_AdditionalUser(UserData['UserId'])
        utils.dialog("notification", heading=utils.addon_name, message="%s %s" % (utils.Translate(33067), UserData['UserName']), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=1000, sound=False)
    else:  # Remove user
        RemoveNameArray = []

        for RemoveUserChoice in RemoveUserChoices:
            RemoveNameArray.append(RemoveUserChoice['UserName'])

        resp = utils.dialog("select", utils.Translate(33064), RemoveNameArray)

        if resp < 0:
            return

        UserData = RemoveUserChoices[resp]
        EmbyServer.remove_AdditionalUser(UserData['UserId'])
        utils.dialog("notification", heading=utils.addon_name, message="%s %s" % (utils.Translate(33066), UserData['UserName']), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=1000, sound=False)

# For theme media, do not modify unless modified in TV Tunes.
# Remove dots from the last character as windows can not have directories with dots at the end
def normalize_string(text):
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.strip()
    text = text.rstrip('.')

    if utils.Python3:
        text = unicodedata.normalize('NFKD', text)
    else:
        text = unicodedata.normalize('NFKD', text).encode('utf-8')

    return text

# Browsing (subfolder) mapping Table
def get_Subfolder(media, KodiType):
    if media == 'tvshows':
        return "Series"

    if media == 'Series':
        return "Season"

    if media == 'Season':
        return "Episode"

    if media == 'MusicArtist' and KodiType == "musicvideos":
        return "MusicVideos"

    if media == 'MusicArtist':
        return "MusicAlbum"

    if media == 'MusicAlbum':
        return "Songs"

    if media == 'Folder':
        return "Folder"

    if media == 'BoxSet':
        return "movies"

    if media == 'Playlist':
        return "playlists"

    if media == 'PhotoAlbum':
        return "PhotoAlbum"

    if media == 'movies':
        return "movies"

    if media == 'channels':
        return "channels"

    if media == 'homevideos':
        return "homevideos"

    if media == 'Genre':
        return "Genre"

    return ""

def ChangeContentWindow(Query, WindowId):  # threaded
    xbmc.sleep(100)

    while xbmc.getCondVisibility("System.HasActiveModalDialog"):  # check if modal dialogs are closed
        xbmc.sleep(50)

    xbmc.executebuiltin('ActivateWindow(%s,"%s",return)' % (WindowId, Query))

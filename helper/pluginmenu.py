# -*- coding: utf-8 -*-
try:
    from urllib import urlencode
except:
    from urllib.parse import urlencode

import xbmc
import xbmcgui
import xbmcplugin

import helper.loghandler
import core.listitem

class Menu():
    def __init__(self, Utils, EmbyServers, player):
        self.LOG = helper.loghandler.LOG('EMBY.helper.pluginmenu.Menu')
        self.Utils = Utils
        self.EmbyServers = EmbyServers
        self.player = player
        self.ListItemData = []

    #Add directory listitem. context should be a list of tuples [(label, action)*]
    def add_ListItem(self, label, path, folder, artwork, fanart):
        li = xbmcgui.ListItem(label, path=path)
        li.setArt({"thumb": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png", "fanart": fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png"})
        self.ListItemData.append((path, li, folder))

    #Display all emby nodes and dynamic entries when appropriate
    def listing(self, Handle):
        if not self.wait_online():
            return

        Handle = int(Handle)
        self.ListItemData = []

        for server_id in self.EmbyServers:
            for Node in self.EmbyServers[server_id].Nodes:
                label = self.Utils.StringDecode(Node['title'])
                node = self.Utils.StringDecode(Node['type'])
                self.LOG.debug("--[ listing/%s/%s ] %s" % (node, label, Node['path']))
                self.add_ListItem(label, Node['path'], True, Node['icon'], None)

            self.add_ListItem("%s (%s)" % (self.Utils.Translate(33194), self.EmbyServers[server_id].Data['auth.server-name']), "plugin://plugin.video.emby-next-gen/?mode=managelibs&server=%s" % server_id, True, None, None)
            self.add_ListItem("%s (%s)" % (self.Utils.Translate(33054), self.EmbyServers[server_id].Data['auth.server-name']), "plugin://plugin.video.emby-next-gen/?mode=adduser&server=%s" % server_id, False, None, None)

        self.add_ListItem(self.Utils.Translate('fav_movies'), "library://video/emby_Favoritemovies.xml", True, None, None)
        self.add_ListItem(self.Utils.Translate('fav_tvshows'), "library://video/emby_Favoritetvshows.xml", True, None, None)
        self.add_ListItem(self.Utils.Translate('fav_episodes'), "plugin://plugin.video.emby-next-gen/?mode=browse&type=Episode&folder=FavEpisodes", True, None, None)
        self.add_ListItem(self.Utils.Translate(33134), "plugin://plugin.video.emby-next-gen/?mode=addserver", False, None, None)
        self.add_ListItem(self.Utils.Translate(5), "plugin://plugin.video.emby-next-gen/?mode=settings", False, None, None)
        self.add_ListItem(self.Utils.Translate(33059), "plugin://plugin.video.emby-next-gen/?mode=texturecache", False, None, None)
        self.add_ListItem(self.Utils.Translate(33058), "plugin://plugin.video.emby-next-gen/?mode=reset", False, None, None)
        self.add_ListItem(self.Utils.Translate(33192), "plugin://plugin.video.emby-next-gen/?mode=restartservice", False, None, None)
        self.add_ListItem(self.Utils.Translate(33202), "plugin://plugin.video.emby-next-gen/?mode=patchmusic", False, None, None)
        self.add_ListItem(self.Utils.Translate(33092), "plugin://plugin.video.emby-next-gen/?mode=backup", False, None, None)
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    def manage_libraries(self, Handle, server_id):
        Handle = int(Handle)
        self.ListItemData = []
#        self.add_ListItem(self.Utils.Translate(33098), "plugin://plugin.video.emby-next-gen/?mode=refreshboxsets&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Utils.Translate(33154), "plugin://plugin.video.emby-next-gen/?mode=addlibs&server=%s" % server_id, False, None, None)
        self.add_ListItem(self.Utils.Translate(33139), "plugin://plugin.video.emby-next-gen/?mode=updatelibs&server=%s" % server_id, False, None, None)
        self.add_ListItem(self.Utils.Translate(33140), "plugin://plugin.video.emby-next-gen/?mode=repairlibs&server=%s" % server_id, False, None, None)
        self.add_ListItem(self.Utils.Translate(33184), "plugin://plugin.video.emby-next-gen/?mode=removelibs&server=%s" % server_id, False, None, None)
        self.add_ListItem(self.Utils.Translate(33060), "plugin://plugin.video.emby-next-gen/?mode=thememedia&server=%s" % server_id, False, None, None)
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    #Browse dynamically content
    def browse(self, Handle, media, view_id, folder, name, extra, server_id):
        if not self.wait_online():
            return

        server_id = self.verify_serverid(server_id)
        Handle = int(Handle)
        folder = folder.lower() if folder else None
        self.LOG.info("--[ v:%s/%s ] %s" % (view_id, media, folder))

        if folder is None:
            return self.browse_subfolders(Handle, media, view_id, name, server_id)

        if folder == 'letter':
            return self.browse_letters(Handle, media, view_id, name, server_id)

        #Mapping
        KodiMediaID = {'musicvideos': 'musicvideos', 'tvshows': 'tvshows', 'music': 'artists', 'movies': 'movies', 'livetv': 'videos', 'channels': 'songs', 'boxsets': 'movies', 'playlists': 'movies', 'Season': 'tvshows', 'Episode': 'episodes', 'MusicVideos': 'musicvideos', 'MusicAlbum': 'albums', 'Songs': 'songs', 'Folder': 'videos', 'PhotoAlbum': 'images', 'Photo': 'images', 'homevideos': 'images', 'mixed': 'mixed', 'Genre': 'videos'}
        EmbyMediaID = {'musicvideos': 'MusicVideos', 'tvshows': "Series", 'music': 'MusicArtist', 'movies': 'Movie', 'livetv': 'LiveTv', 'channels': 'Songs', 'boxsets': 'BoxSet', 'playlists': 'Movie', 'Season': 'Season', 'Episode': 'Episode', 'MusicVideos': 'MusicVideos', 'MusicAlbum': 'MusicAlbum', 'Songs': 'Songs', 'Folder': 'Folder', 'PhotoAlbum': 'PhotoAlbum', 'Photo': 'Photo', 'homevideos': 'Video,PhotoAlbum,Photo', 'mixed': 'Movie,Series,Video', 'Genre': None}
        KodiType = KodiMediaID[media]
        EmbyType = EmbyMediaID[media]

        if view_id:
            xbmcplugin.setPluginCategory(Handle, name)

        if extra:
            if extra == "0-9": #Special charecters
                extra = {'NameLessThan': "A"}
            else: #alphabet
                extra = {'NameStartsWith': extra}

            ID = view_id
        else:
            ID = folder

        #General nodes
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
        elif folder == 'favepisodes':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'limit': 25, 'media': EmbyType, 'filters': ['IsFavorite']})

        #Root nodes
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
        elif media == 'homevideos':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Video,Folder,PhotoAlbum,Photo", 'recursive': False})
        elif media == 'mixed':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Movie,Series,Video", 'recursive': False})

        #Emby Server media ID nodes
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
        elif media == 'PhotoAlbum':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "PhotoAlbum", 'recursive': False})
        elif media == 'Photo':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Photo", 'recursive': False})
        elif media == 'Movie':
            listing = self.EmbyServers[server_id].API.get_filtered_section({'ViewId': ID, 'extra': extra, 'media': "Movie", 'recursive': True})

        if listing:
            listitems = core.listitem.ListItem(self.Utils)
            list_li = []
            listing = listing if isinstance(listing, list) else listing.get('Items', [])

            for item in listing:
                if xbmc.Monitor().waitForAbort(0.0001):
                    return

                li = listitems.set(item)

                if item.get('IsFolder') or item['Type'] in ('MusicArtist', 'MusicAlbum'):
                    params = {
                        'id': view_id,
                        'mode': "browse",
                        'type': self.get_Subfolder(item['Type'], KodiType),
                        'name': name,
                        'folder': item['Id'],
                        'server': server_id
                    }

                    path = "plugin://plugin.video.emby-next-gen/?%s" % urlencode(params)
                    list_li.append((path, li, True))
                elif item['Type'] == 'Genre':
                    params = {
                        'id': view_id or item['Id'],
                        'mode': "browse",
                        'type': self.get_Subfolder(item['Type'], KodiType),
                        'folder': 'genres-%s' % item['Id'],
                        'name': name,
                        'server': server_id
                    }
                    path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
                    list_li.append((path, li, True))
                else:
                    if item['Type'] == 'Photo':
                        path = "http://127.0.0.1:57578/%s/Images/Primary" % item['Id']
                    elif item['Type'] == 'PhotoAlbum':
                        path = "plugin://plugin.video.emby-next-gen/?mode=photoviewer&id=%s" % item['Id']
                    else:
                        path = ""

                        if item['Type'] == "MusicVideo":
                            Type = "musicvideo"
                        elif item['Type'] == "Movie":
                            Type = "movie"
                        elif item['Type'] == "Episode":
                            Type = "tvshow"
                        elif item['Type'] == "Audio":
                            Type = "audio"
                        elif item['Type'] == "Video":
                            Type = "video"
                        elif item['Type'] == "Trailer":
                            Type = "trailer"
                        elif item['Type'] == "TvChannel":
                            Type = "tvchannel"
                            path = "http://127.0.0.1:57578/livetv/%s-stream.ts" % item['Id']
                        else:
                            return

                        if not path:
                            path = "http://127.0.0.1:57578/%s/%s-DYNAMIC-stream-%s" % (Type, item['Id'], self.Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))

                        self.player.DynamicItem[self.Utils.ReplaceSpecialCharecters(li.getLabel())] = item['Id']

                    list_li.append((path, li, False))

            xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))

        #Set Sorting
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
        else:
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

        xbmcplugin.setContent(Handle, KodiType)
        xbmcplugin.endOfDirectory(Handle)

    #Display submenus for emby views
    def browse_subfolders(self, Handle, media, view_id, name, server_id):
        DYNNODES = {
            'tvshows': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.Utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('genres', self.Utils.Translate(135), 'DefaultGenre.png'),
                ('random', self.Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'mixed': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.Utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('inprogress', self.Utils.Translate(30171), 'DefaultInProgressShows.png'),
                ('inprogressepisodes', self.Utils.Translate(30178), 'DefaultInProgressShows.png'),
                ('genres', self.Utils.Translate(135), 'DefaultGenre.png'),
                ('random', self.Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'movies': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMovies.png'),
                ('recentlyadded', self.Utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
                ('inprogress', self.Utils.Translate(30177), 'DefaultInProgressShows.png'),
                ('boxsets', self.Utils.Translate(20434), 'DefaultSets.png'),
                ('favorite', self.Utils.Translate(33168), 'DefaultFavourites.png'),
                ('genres', self.Utils.Translate(135), 'DefaultGenre.png'),
                ('random', self.Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'boxsets': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultSets.png')
            ],
            'livetv': [
                ('all', None, 'DefaultMovies.png')
            ],
            'musicvideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('recentlyadded', self.Utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
                ('inprogress', self.Utils.Translate(30257), 'DefaultInProgressShows.png'),
                ('Unwatched', self.Utils.Translate(30258), 'OverlayUnwatched.png')
            ],
            'homevideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultAddonVideo.png'),
                ('recentlyadded', self.Utils.Translate(33167), '')
            ],
            'channels': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.Utils.Translate(33167), ''),
                ('inprogress', self.Utils.Translate(33169), ''),
                ('favorite', self.Utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'playlists': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultPlaylist.png')
            ],
            'books': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('recentlyadded', self.Utils.Translate(33167), ''),
                ('inprogress', self.Utils.Translate(33169), ''),
                ('favorite', self.Utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'audiobooks': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('recentlyadded', self.Utils.Translate(33167), ''),
                ('inprogress', self.Utils.Translate(33169), ''),
                ('favorite', self.Utils.Translate(33168), 'DefaultFavourites.png')
            ],
            'music': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultAddonMusic.png')
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
            path = "plugin://plugin.video.emby-next-gen/?%s" % urlencode(params)
            self.add_ListItem(node[1] or name, path, True, node[2], None)

        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.endOfDirectory(Handle)

    #Display letters as options
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
            path = "plugin://plugin.video.emby-next-gen/?%s" % urlencode(params)
            self.add_ListItem(node, path, True, None, None)

        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.endOfDirectory(Handle)

    #Browsing (subfolder) mapping Table
    def get_Subfolder(self, media, KodiType):
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
            return "Photo"

        if media == 'movies':
            return "movies"

        if media == 'channels':
            return "channels2"

        if media == 'homevideos':
            return "homevideos"

        if media == 'Genre':
            return "Genre"

    def get_next_episodes(self, Handle, libraryname):
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
                li = self.Utils.CreateListitem("episode", episode)
                list_li.append((FilePath, li, False))

        xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'episodes')
        xbmcplugin.endOfDirectory(Handle)

    def wait_online(self):
        for _ in range(60): #wait for ack (60 seconds timeout)
            if self.EmbyServers:
                return True

            if xbmc.Monitor().waitForAbort(1):
                return False

        return False

    def verify_serverid(self, server_id):
        if not server_id or server_id == 'None':
            for server_id in self.EmbyServers: ######################## WORKAROUND!!!!!!!!!!!
                break

        return server_id

# -*- coding: utf-8 -*-
import json
import sys
import time

try:
    from urlparse import parse_qsl
    from urllib import urlencode
except:
    from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

import core.listitem
import helper.basics
import helper.loghandler

class Events():
    #Parse the parameters. Reroute to our service.py
    #where user is fully identified already
    def __init__(self, Parameter):
        self.ListItemData = []
        self.Basics = helper.basics.Basics()
        params = dict(parse_qsl(Parameter[2][1:]))
        Handle = int(Parameter[1])
        mode = params.get('mode')
        self.server_id = params.get('server')

        #Simple commands
        if mode == 'deviceid':
            self.Basics.event('reset_device_id', {})
            return

        if mode == 'reset':
            self.Basics.event('DatabaseReset', {})
            return

        if mode == 'login':
            self.Basics.event('ServerConnect', {'ServerId': None})
            return

        if mode == 'backup':
            self.Basics.event('Backup', {'ServerId': None})
            return

        if mode == 'restartservice':
            self.Basics.window('emby.restart.bool', True)
            return

        if mode == 'patchmusic':
            self.Basics.event('PatchMusic', {'Notification': True, 'ServerId': None})
            return

        if mode == 'settings':
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
            return

        if mode == 'texturecache':
            self.Basics.event('TextureCache', {})
            return

        if mode == 'delete':
            self.Basics.event('DeleteItem', {})
            return

        #Load Serverdata
        ServerOnline = False

        for _ in range(60):
            self.server_ids = self.Basics.window('emby.servers.json')

            if self.server_ids:
                ServerOnline = True
                break

            if xbmc.Monitor().waitForAbort(0.5):
                break

        if not ServerOnline:
            return

#        if not self.server_id:
        for server_id in self.server_ids:
            self.server_id = server_id
            break

        self.LOG = helper.loghandler.LOG('EMBY.Events')
        self.LOG.debug("path: %s params: %s" % (Parameter[2], json.dumps(params, indent=4)))

        #Events
#        if mode == 'refreshboxsets':
#            self.Basics.event('SyncLibrary', {'Id': "Boxsets: Refresh", 'Update': False, 'ServerId': self.server_id})
        if mode == 'nextepisodes':
            self.get_next_episodes(Handle, params.get('libraryname'))
        elif mode == 'photoviewer':
            xbmc.executebuiltin('ShowPicture(http://127.0.0.1:57578/%s/Images/Primary)' %  params['id'])
        elif mode == 'browse':
            self.browse(Handle, params.get('type'), params.get('id'), params.get('folder'), params.get('name'), params.get('extra'))
        elif mode == 'repairlibs':
            self.Basics.event('RepairLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'updatelibs':
            self.Basics.event('SyncLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'removelibs':
            self.Basics.event('RemoveLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'addlibs':
            self.Basics.event('AddLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'addserver':
            self.Basics.event('AddServer', {'ServerId': self.server_id})
        elif mode == 'removeserver':
            self.Basics.event('RemoveServer', {'ServerId': self.server_id})
        elif mode == 'adduser':
            self.Basics.event('AddUser', {'ServerId': self.server_id})
        elif mode == 'thememedia':
            self.Basics.event('SyncThemes', {'ServerId': self.server_id})
        elif mode == 'managelibs':
            self.manage_libraries(Handle)
        elif mode == 'setssl':
            self.Basics.event('SetServerSSL', {'ServerId': self.server_id})
        else:
            self.listing(Handle)

    #Display all emby nodes and dynamic entries when appropriate
    def listing(self, Handle):
        self.ListItemData = []

        for server_id in self.server_ids:
            total = int(self.Basics.window('emby.nodes.%s.total' % server_id) or 0)

            for i in range(total):
                NodeData = self.Basics.window("Emby.nodes.%s.%s.json" % (server_id, i))
                label = self.Basics.StringDecode(NodeData['title'])
                node = self.Basics.StringDecode(NodeData['type'])
                self.LOG.debug("--[ listing/%s/%s ] %s" % (node, label, NodeData['path']))
                self.add_ListItem(label, NodeData['path'], True, NodeData['icon'], None)

            self.add_ListItem("%s (%s)" % (self.Basics.Translate(33194), self.server_ids[self.server_id]), "plugin://plugin.video.emby-next-gen/?mode=managelibs", True, None, None)
            self.add_ListItem("%s (%s)" % (self.Basics.Translate(33054), self.server_ids[self.server_id]), "plugin://plugin.video.emby-next-gen/?mode=adduser&server=%s" % server_id, False, None, None)

        self.add_ListItem(self.Basics.Translate('fav_movies'), "library://video/emby_Favoritemovies.xml", True, None, None)
        self.add_ListItem(self.Basics.Translate('fav_tvshows'), "library://video/emby_Favoritetvshows.xml", True, None, None)
        self.add_ListItem(self.Basics.Translate('fav_episodes'), "plugin://plugin.video.emby-next-gen/?mode=browse&type=Episode&folder=FavEpisodes", True, None, None)
        self.add_ListItem(self.Basics.Translate(33134), "plugin://plugin.video.emby-next-gen/?mode=addserver", False, None, None)
        self.add_ListItem(self.Basics.Translate(5), "plugin://plugin.video.emby-next-gen/?mode=settings", False, None, None)
        self.add_ListItem(self.Basics.Translate(33059), "plugin://plugin.video.emby-next-gen/?mode=texturecache", False, None, None)
        self.add_ListItem(self.Basics.Translate(33058), "plugin://plugin.video.emby-next-gen/?mode=reset", False, None, None)
        self.add_ListItem(self.Basics.Translate(33192), "plugin://plugin.video.emby-next-gen/?mode=restartservice", False, None, None)
        self.add_ListItem(self.Basics.Translate(33202), "plugin://plugin.video.emby-next-gen/?mode=patchmusic", False, None, None)

        if self.Basics.settings('backupPath'):
            self.add_ListItem(self.Basics.Translate(33092), "plugin://plugin.video.emby-next-gen/?mode=backup", False, None, None)

        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    def manage_libraries(self, Handle):
        self.ListItemData = []
#        self.add_ListItem(self.Basics.Translate(33098), "plugin://plugin.video.emby-next-gen/?mode=refreshboxsets&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Basics.Translate(33154), "plugin://plugin.video.emby-next-gen/?mode=addlibs&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Basics.Translate(33139), "plugin://plugin.video.emby-next-gen/?mode=updatelibs&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Basics.Translate(33140), "plugin://plugin.video.emby-next-gen/?mode=repairlibs&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Basics.Translate(33184), "plugin://plugin.video.emby-next-gen/?mode=removelibs&server=%s" % self.server_id, False, None, None)
        self.add_ListItem(self.Basics.Translate(33060), "plugin://plugin.video.emby-next-gen/?mode=thememedia&server=%s" % self.server_id, False, None, None)
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    def EmbyQueryData(self, method, Data):
        QueryID = str(round(time.time() * 100000))
        Data['QueryId'] = QueryID
        Data['ServerId'] = self.server_id
        self.Basics.event(method, Data)

        #Wait for Data
        while True:
            data = self.Basics.window('emby.event.%s.json' % QueryID)

            if data:
                break

            if xbmc.Monitor().waitForAbort(0.1):
                self.Basics.window('emby.event.%s' % QueryID, clear=True)
                return None

        self.Basics.window('emby.event.%s' % QueryID, clear=True)

        if 'NoData' in data:
            return {}

        return data

    #Browse dynamically content
    def browse(self, Handle, media, view_id, folder, name, extra):
        folder = folder.lower() if folder else None
        self.LOG.info("--[ v:%s/%s ] %s" % (view_id, media, folder))

        if folder is None:
            return self.browse_subfolders(Handle, media, view_id, name)

        if folder == 'letter':
            return self.browse_letters(Handle, media, view_id, name)

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
            listing = self.EmbyQueryData('get_recently_added', {'ViewId': view_id, 'media': None})
        elif folder == 'genres':
            listing = self.EmbyQueryData('get_genres', {'ViewId': view_id})
        elif folder == 'unwatched':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'filters': ['IsUnplayed']})
        elif folder == 'favorite':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'filters': ['IsFavorite']})
        elif folder == 'inprogress':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'filters': ['IsResumable']})
        elif folder == 'boxsets':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'media': "BoxSet"})
        elif folder == 'random':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'media': EmbyType, 'sort': "Random", 'recursive': True, 'limit': 25})
        elif (folder or "").startswith('genres-'):
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': view_id, 'NoSort': False, 'media': None, 'extra': {'GenreIds': folder.split('-')[1]}})
        elif folder == 'favepisodes':
            listing = self.EmbyQueryData('get_filtered_section', {'limit': 25, 'NoSort': False, 'media': EmbyType, 'filters': ['IsFavorite']})

        #Root nodes
        elif media == 'musicvideos':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "MusicArtist", 'recursive': True})
        elif media == 'tvshows':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Series", 'recursive': True})
        elif media == 'music':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "MusicArtist", 'recursive': True})
        elif media == 'movies':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Movie", 'recursive': True})
        elif media == 'livetv':
            listing = self.EmbyQueryData('get_channels', {})
        elif media == 'channels':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Folder", 'recursive': True})
        elif media == 'boxsets':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "BoxSet", 'recursive': True})
        elif media == 'playlists':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': True, 'recursive': False})
        elif media == 'homevideos':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Video,PhotoAlbum,Photo", 'recursive': False})
        elif media == 'mixed':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Movie,Series,Video", 'recursive': False})

        #Emby Server media ID nodes
        elif media == 'Season':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Season", 'recursive': True})
        elif media == 'Episode':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Episode", 'recursive': True})
        elif media == 'MusicVideos':
            listing = self.EmbyQueryData('browse_MusicByArtistId', {'ViewId': folder, 'extra': extra, 'ArtistId': view_id, 'media': "MusicVideos"})
        elif media == 'MusicAlbum':
            listing = self.EmbyQueryData('browse_MusicByArtistId', {'ViewId': folder, 'extra': extra, 'ArtistId': view_id, 'media': "MusicAlbum"})
        elif media == 'Songs':
            listing = self.EmbyQueryData('browse_MusicByArtistId', {'ViewId': folder, 'extra': extra, 'ArtistId': view_id, 'media': "Audio"})
        elif media == 'Folder':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': True, 'recursive': False})
        elif media == 'PhotoAlbum':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': True, 'media': "PhotoAlbum", 'recursive': False})
        elif media == 'Photo':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': True, 'media': "Photo", 'recursive': False})
        elif media == 'Movie':
            listing = self.EmbyQueryData('get_filtered_section', {'ViewId': ID, 'extra': extra, 'NoSort': False, 'media': "Movie", 'recursive': True})

        if listing:
            listitems = core.listitem.ListItem(False, self.Basics)
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
                        'server': self.server_id
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
                        'server': self.server_id
                    }
                    path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
                    list_li.append((path, li, True))
                else:
                    if item['Type'] == 'Photo':
                        path = "plugin://plugin.video.emby-next-gen/?mode=photoviewer&id=%s" % item['Id']
#                        path = "http://127.0.0.1:57578/%s/Images/Primary" % item['Id']
                    elif item['Type'] not in ('PhotoAlbum', 'Photo'):
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
                            path = "http://127.0.0.1:57578/%s/%s-DYNAMIC-stream-%s" % (Type, item['Id'], self.Basics.PathToFilenameReplaceSpecialCharecters(item['Path']))

                        self.Basics.window('emby.DynamicItem_' + self.Basics.ReplaceSpecialCharecters(li.getLabel()), item['Id'])

                    list_li.append((path, li, False))

            xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))

        if KodiType == 'images':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

        if media == 'playlists':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

        xbmcplugin.setContent(Handle, KodiType)
        xbmcplugin.endOfDirectory(Handle)

    #Display submenus for emby views
    def browse_subfolders(self, Handle, media, view_id, name):
        DYNNODES = {
            'tvshows': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.Basics.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('genres', self.Basics.Translate(135), 'DefaultGenre.png'),
                ('random', self.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'mixed': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.Basics.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('inprogress', self.Basics.Translate(30171), 'DefaultInProgressShows.png'),
                ('inprogressepisodes', self.Basics.Translate(30178), 'DefaultInProgressShows.png'),
                ('genres', self.Basics.Translate(135), 'DefaultGenre.png'),
                ('random', self.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'movies': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMovies.png'),
                ('recentlyadded', self.Basics.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
                ('inprogress', self.Basics.Translate(30177), 'DefaultInProgressShows.png'),
                ('boxsets', self.Basics.Translate(20434), ''),
                ('favorite', self.Basics.Translate(33168), ''),
                ('genres', self.Basics.Translate(135), 'DefaultGenre.png'),
                ('random', self.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ],
            'boxsets': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMovies.png')
            ],
            'livetv': [
                ('all', None, 'DefaultMovies.png')
            ],
            'musicvideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('recentlyadded', self.Basics.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
                ('inprogress', self.Basics.Translate(30257), 'DefaultInProgressShows.png'),
                ('Unwatched', self.Basics.Translate(30258), 'OverlayUnwatched.png')
            ],
            'homevideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('recentlyadded', self.Basics.Translate(33167), '')
            ],
            'channels': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('recentlyadded', self.Basics.Translate(33167), ''),
                ('inprogress', self.Basics.Translate(33169), ''),
                ('favorite', self.Basics.Translate(33168), '')
            ],
            'playlists': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, '')
            ],
            'books': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('recentlyadded', self.Basics.Translate(33167), ''),
                ('inprogress', self.Basics.Translate(33169), ''),
                ('favorite', self.Basics.Translate(33168), '')
            ],
            'audiobooks': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, ''),
                ('recentlyadded', self.Basics.Translate(33167), ''),
                ('inprogress', self.Basics.Translate(33169), ''),
                ('favorite', self.Basics.Translate(33168), '')
            ],
            'music': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png')
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
                'server': self.server_id
            }
            path = "plugin://plugin.video.emby-next-gen/?%s" % urlencode(params)
            self.add_ListItem(node[1] or name, path, True, node[2], None)

        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.addDirectoryItems(Handle, self.ListItemData, len(self.ListItemData))
        xbmcplugin.endOfDirectory(Handle)

    #Add directory listitem. context should be a list of tuples [(label, action)*]
    def add_ListItem(self, label, path, folder, artwork, fanart):
        li = xbmcgui.ListItem(label, path=path)
        li.setArt({"thumb": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png", "fanart": fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png"})
        self.ListItemData.append((path, li, folder))

    #Display letters as options
    def browse_letters(self, Handle, media, view_id, name):
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
                'server': self.server_id
            }
            path = "plugin://plugin.video.emby-next-gen/?%s" % urlencode(params)
            self.add_ListItem(node, path, True, None, None)

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
        result = helper.basics.JSONRPC('VideoLibrary.GetTVShows').execute({
            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % libraryname}
                ]}
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
                    "title", "plot", "file", "art"
                ],
                'limits': {"end": 1}
            }

            result = helper.basics.JSONRPC('VideoLibrary.GetEpisodes').execute(params)
            episodes = result['result']['episodes']

            for episode in episodes:
                metadata = {
                    'mediatype': 'episode',
                    'Plot': episode['plot'],
                    'dbid': str(episode['episodeid'])
                }
                li = xbmcgui.ListItem(episode['title'])
                li.setProperty('IsPlayable', "true")
                li.setInfo("video", metadata)
                li.setArt(episode['art'])
                list_li.append((episode['file'], li))

        xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
        xbmcplugin.setContent(Handle, 'episodes')
        xbmcplugin.endOfDirectory(Handle)

if __name__ == "__main__":
    Events(sys.argv)

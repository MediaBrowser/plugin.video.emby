# -*- coding: utf-8 -*-
import json
import logging

try:
    from urlparse import parse_qsl
    from urllib import urlencode
except:
    from urllib.parse import parse_qsl, urlencode

import os
import sys
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon

import core.obj_ops
import core.listitem
import core.artwork
import emby.main
import emby.downloader
import database.database
import database.emby_db
import helper.translate
import helper.utils
import helper.api
import helper.loghandler
import helper.xmls
import context

class Events():
    #Parse the parameters. Reroute to our service.py
    #where user is fully identified already
    def __init__(self, Parameter):
        helper.loghandler.reset()
        helper.loghandler.config()
        #Emby.set_loghandler(helper.loghandler.LogHandler, logging.DEBUG)
        self.LOG = logging.getLogger("EMBY.entrypoint.evens.Events")
        self.Utils = helper.utils.Utils()
        self.xmls = helper.xmls.Xmls(self.Utils)
        self.CONTENT_TYPE = None
        self.EMBY = None
        self.LOG = logging.getLogger("EMBY.entrypoint.evens.Events")
        self.Downloader = emby.downloader.Downloader(self.Utils)
        self.DYNNODES = {
            'tvshows': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(30170)),
                ('recentepisodes', helper.translate._(30175)),
                ('InProgress', helper.translate._(30171)),
                ('inprogressepisodes', helper.translate._(30178)),
                ('nextepisodes', helper.translate._(30179)),
                ('Genres', helper.translate._(135)),
                ('Random', helper.translate._(30229)),
                ('recommended', helper.translate._(30230))
            ],
            'movies': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(30174)),
                ('InProgress', helper.translate._(30177)),
                ('Boxsets', helper.translate._(20434)),
                ('Favorite', helper.translate._(33168)),
                ('FirstLetter', helper.translate._(33171)),
                ('Genres', helper.translate._(135)),
                ('Random', helper.translate._(30229))
                #('Recommended', helper.translate._(30230))
            ],
            'musicvideos': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(30256)),
                ('InProgress', helper.translate._(30257)),
                ('Unwatched', helper.translate._(30258))
            ],
            'homevideos': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(33167)),
                ('InProgress', helper.translate._(33169)),
                ('Favorite', helper.translate._(33168))
            ],
            'books': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(33167)),
                ('InProgress', helper.translate._(33169)),
                ('Favorite', helper.translate._(33168))
            ],
            'audiobooks': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(33167)),
                ('InProgress', helper.translate._(33169)),
                ('Favorite', helper.translate._(33168))
            ],
            'music': [
                ('all', None),
                ('RecentlyAdded', helper.translate._(33167)),
                ('Favorite', helper.translate._(33168))
            ]
        }

        ServerOnline = False

        for i in range(60):
            if self.Utils.window('emby_online.bool'):
                ServerOnline = True
                break

            xbmc.sleep(500)

        if not ServerOnline:
            helper.loghandler.reset()
            return

        #Load server connection data
        emby.main.Emby().set_state(self.Utils.window('emby.server.state.json'))

        for server in self.Utils.window('emby.server.states.json') or []:
            emby.main.Emby(server).set_state(self.Utils.window('emby.server.%s.state.json' % server))

        try:
            params = dict(parse_qsl(Parameter[2][1:]))
        except:
            params = {}

        if 'content_type' in params:
            self.Utils.window('emby.plugin.content.type', params['content_type'])
            self.CONTENT_TYPE = params['content_type']
        else:
            self.CONTENT_TYPE = self.Utils.window('emby.plugin.content.type') or None

        Handle = int(Parameter[1])
        mode = params.get('mode')
        server = params.get('server')

        if server == 'None' or not server:
            server = None

        self.LOG.warning("path: %s params: %s", Parameter[2], json.dumps(params, indent=4))

#        if '/extrafanart' in Parameter[0]:
#            emby_path = path
#            emby_id = params.get('id')
#            self.get_fanart(Handle, emby_id, emby_path, server)
#        elif '/Extras' in Parameter[0] or '/VideoFiles' in Parameter[0]:
#            emby_path = path
#            emby_id = params.get('id')
#            self.get_video_extras(emby_id, emby_path, server)
        if mode == 'photoviewer':
            xbmc.executebuiltin('ShowPicture(%s/emby/Items/%s/Images/Primary)' % (emby.main.Emby(server)['auth/server-address'], params['id']))
        elif mode == 'deviceid':
            self.Utils.reset_device_id()
        elif mode == 'reset':
            database.database.reset()
        elif mode == 'delete':
            self.delete_item()
        elif mode == 'refreshboxsets':
            self.Utils.event('SyncLibrary', {'Id': "Boxsets:Refresh"})
        elif mode == 'nextepisodes':
            self.get_next_episodes(Handle, params['id'], params['limit'])
        elif mode == 'browse':
            self.browse(Handle, params.get('type'), params.get('id'), params.get('folder'), server)
        elif mode == 'synclib':
            self.Utils.event('SyncLibrary', {'Id': params.get('id')})
        elif mode == 'updatelib':
            self.Utils.event('SyncLibrary', {'Id': params.get('id'), 'Update': True})
        elif mode == 'repairlib':
            self.Utils.event('RepairLibrary', {'Id': params.get('id')})
        elif mode == 'removelib':
            self.Utils.event('RemoveLibrary', {'Id': params.get('id')})
        elif mode == 'repairlibs':
            self.Utils.event('RepairLibrarySelection')
        elif mode == 'updatelibs':
            self.Utils.event('SyncLibrarySelection')
        elif mode == 'removelibs':
            self.Utils.event('RemoveLibrarySelection')
        elif mode == 'addlibs':
            self.Utils.event('AddLibrarySelection')
        elif mode == 'connect':
            self.Utils.event('EmbyConnect')
        elif mode == 'addserver':
            self.Utils.event('AddServer')
        elif mode == 'login':
            self.Utils.event('ServerConnect', {'Id': server})
        elif mode == 'removeserver':
            self.Utils.event('RemoveServer', {'Id': server})
        elif mode == 'settings':
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
        elif mode == 'adduser':
            self.add_user(params.get('permanent') == 'true')
        elif mode == 'checkupdate':
            self.Utils.event('CheckUpdate')
        elif mode == 'resetupdate':
            self.Utils.event('ResetUpdate')
        elif mode == 'updateserver':
            self.Utils.event('UpdateServer')
        elif mode == 'thememedia':
            self.get_themes()
        elif mode == 'managelibs':
            self.manage_libraries(Handle)
        elif mode == 'texturecache':
            self.cache_artwork()
        elif mode == 'backup':
            self.backup()
        elif mode == 'restartservice':
            self.Utils.window('emby.restart.bool', True)
        elif mode == 'patchmusic':
            self.Utils.event('PatchMusic', {'Notification': True})
        elif mode == 'changelog':
            pass
            #self.changelog()
        elif mode == 'setssl':
            self.Utils.event('SetServerSSL', {'Id': server})
        else:
            self.listing(Handle)

        helper.loghandler.reset()

    def get_server(self, server=None):
        try:
            self.EMBY = emby.main.Emby(server).get_client()
        except KeyError: # Server never loaded.
            self.Utils.event('ServerConnect', {'Id': server})

            monitor = xbmc.Monitor()
            for i in range(300):
                if server is None and self.Utils.window('emby_online.bool'):
                    emby.main.Emby().set_state(self.Utils.window('emby.server.state.json'))
                    break

                if server is not None and server in self.Utils.window('emby.server.states.json') or []:
                    emby.main.Emby(server).set_state(self.Utils.window('emby.server.%s.state.json' % server))
                    break

                if monitor.waitForAbort(0.1):
                    raise Exception('ShutDownRequested')
            else:
                self.LOG.error("Server %s is not online", server)
                raise Exception('ServerOffline')

            self.EMBY = emby.main.Emby(server).get_client()

    #Display all emby nodes and dynamic entries when appropriate
    def listing(self, Handle):
        total = int(self.Utils.window('Emby.nodes.total') or 0)
        sync = database.database.get_sync()
        whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
        servers = database.database.get_credentials()['Servers'][1:]

        for i in range(total):
            window_prop = "Emby.nodes.%s" % i
            path = self.Utils.window('%s.index' % window_prop)

            if not path:
                path = self.Utils.window('%s.content' % window_prop) or self.Utils.window('%s.path' % window_prop)

            label = self.Utils.window('%s.title' % window_prop)
            node = self.Utils.window('%s.type' % window_prop)
            artwork = self.Utils.window('%s.artwork' % window_prop)
            view_id = self.Utils.window('%s.id' % window_prop)
            contextData = []

            if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed') and view_id not in whitelist:
                label = "%s %s" % (label, helper.translate._(33166))
                contextData.append((helper.translate._(33123), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=synclib&id=%s)" % view_id))

            if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music') and view_id in whitelist:
                contextData.append((helper.translate._(33136), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=updatelib&id=%s)" % view_id))
                contextData.append((helper.translate._(33132), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=repairlib&id=%s)" % view_id))
                contextData.append((helper.translate._(33133), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=removelib&id=%s)" % view_id))

            self.LOG.debug("--[ listing/%s/%s ] %s", node, label, path)

            if path:
                if xbmc.getCondVisibility('Window.IsActive(Pictures)') and node in ('photos', 'homevideos'):
                    self.directory(Handle, label, path, artwork=artwork)
                elif xbmc.getCondVisibility('Window.IsActive(Videos)') and node not in ('photos', 'music', 'audiobooks'):
                    self.directory(Handle, label, path, artwork=artwork, contextData=contextData)
                elif xbmc.getCondVisibility('Window.IsActive(Music)') and node in 'music':
                    self.directory(Handle, label, path, artwork=artwork, contextData=contextData)
                elif not xbmc.getCondVisibility('Window.IsActive(Videos) | Window.IsActive(Pictures) | Window.IsActive(Music)'):
                    self.directory(Handle, label, path, artwork=artwork)

        for server in servers:
            contextData = []

            if server.get('ManualAddress'):
                contextData.append((helper.translate._(30500), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=setssl&server=%s)" % server['Id']))
                contextData.append((helper.translate._(33141), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=removeserver&server=%s)" % server['Id']))

            if 'AccessToken' not in server:
                self.directory(Handle, "%s (%s)" % (server['Name'], helper.translate._(30539)), "plugin://plugin.video.emby-next-gen/?mode=login&server=%s" % server['Id'], False, contextData=contextData)
            else:
                self.directory(Handle, server['Name'], "plugin://plugin.video.emby-next-gen/?mode=browse&server=%s" % server['Id'], contextData=contextData)

        self.directory(Handle, helper.translate._(33194), "plugin://plugin.video.emby-next-gen/?mode=managelibs", True)
        self.directory(Handle, helper.translate._(33134), "plugin://plugin.video.emby-next-gen/?mode=addserver", False)
        self.directory(Handle, helper.translate._(33054), "plugin://plugin.video.emby-next-gen/?mode=adduser", False)
        self.directory(Handle, helper.translate._(5), "plugin://plugin.video.emby-next-gen/?mode=settings", False)
        self.directory(Handle, helper.translate._(33059), "plugin://plugin.video.emby-next-gen/?mode=texturecache", False)
        self.directory(Handle, helper.translate._(33058), "plugin://plugin.video.emby-next-gen/?mode=reset", False)
        self.directory(Handle, helper.translate._(33192), "plugin://plugin.video.emby-next-gen/?mode=restartservice", False)

        if self.Utils.settings('backupPath'):
            self.directory(Handle, helper.translate._(33092), "plugin://plugin.video.emby-next-gen/?mode=backup", False)

        self.directory(Handle, "Changelog", "plugin://plugin.video.emby-next-gen/?mode=changelog", False)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    #Add directory listitem. context should be a list of tuples [(label, action)*]
    def directory(self, Handle, label, path, folder=True, artwork=None, fanart=None, contextData=None):
        li = self.dir_listitem(label, path, artwork, fanart)

        if contextData:
            li.addContextMenuItems(contextData)

        xbmcplugin.addDirectoryItem(Handle, path, li, folder)
        return li

    def dir_listitem(self, label, path, artwork=None, fanart=None):
        li = xbmcgui.ListItem(label, path=path)
#        li.setThumbnailImage(artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png")
        li.setArt({"thumb": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png", "fanart": fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg"})
#        li.setArt({"landscape": artwork or fanart or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg"})
#        self.li.setArt({"thumb": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/icon.png", "icon" : 'DefaultFolder.png'     })
        return li

    def manage_libraries(self, Handle):
        self.directory(Handle, helper.translate._(33098), "plugin://plugin.video.emby-next-gen/?mode=refreshboxsets", False,)
        self.directory(Handle, helper.translate._(33154), "plugin://plugin.video.emby-next-gen/?mode=addlibs", False)
        self.directory(Handle, helper.translate._(33139), "plugin://plugin.video.emby-next-gen/?mode=updatelibs", False)
        self.directory(Handle, helper.translate._(33140), "plugin://plugin.video.emby-next-gen/?mode=repairlibs", False)
        self.directory(Handle, helper.translate._(33184), "plugin://plugin.video.emby-next-gen/?mode=removelibs", False)
        self.directory(Handle, helper.translate._(33060), "plugin://plugin.video.emby-next-gen/?mode=thememedia", False)
        self.directory(Handle, helper.translate._(33202), "plugin://plugin.video.emby-next-gen/?mode=patchmusic", False)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    def changelogTOBEDONE(self):
        return

    #Browse content dynamically
    def browse(self, Handle, media, view_id=None, folder=None, server_id=None):
        self.LOG.info("--[ v:%s/%s ] %s", view_id, media, folder)
        self.get_server(server_id)
        folder = folder.lower() if folder else None

        if folder is None and media in ('homevideos', 'movies', 'books', 'audiobooks'):
            return self.browse_subfolders(Handle, media, view_id, server_id)

        if folder and folder == 'firstletter':
            return self.browse_letters(Handle, media, view_id, server_id)

        if view_id:
            view = self.EMBY['api'].get_item(view_id)
            xbmcplugin.setPluginCategory(Handle, view['Name'])

        content_type = "files"

        if media in ('tvshows', 'seasons', 'episodes', 'movies', 'musicvideos', 'songs', 'albums'):
            content_type = media
        elif media in ('homevideos', 'photos'):
            content_type = "images"
        elif media in ('books', 'audiobooks'):
            content_type = "videos"
        elif media == 'music':
            content_type = "artists"
        if folder == 'recentlyadded':
            listing = self.EMBY['api'].get_recently_added(None, view_id, None)
        elif folder == 'genres':
            listing = self.EMBY['api'].get_genres(view_id)
        elif media == 'livetv':
            listing = self.EMBY['api'].get_channels()
        elif folder == 'unwatched':
            listing = self.Downloader.get_filtered_section(view_id, None, None, None, None, None, ['IsUnplayed'], None, server_id)
        elif folder == 'favorite':
            listing = self.Downloader.get_filtered_section(view_id, None, None, None, None, None, ['IsFavorite'], None, server_id)
        elif folder == 'inprogress':
            listing = self.Downloader.get_filtered_section(view_id, None, None, None, None, None, ['IsResumable'], None, server_id)
        elif folder == 'boxsets':
            listing = self.Downloader.get_filtered_section(view_id, self.get_media_type('boxsets'), None, True, None, None, None, None, server_id)
        elif folder == 'random':
            listing = self.Downloader.get_filtered_section(view_id, self.get_media_type(content_type), 25, True, "Random", None, None, None, server_id)
        elif (folder or "").startswith('firstletter-'):
            listing = self.Downloader.get_filtered_section(view_id, self.get_media_type(content_type), None, None, None, None, None, {'NameStartsWith': folder.split('-')[1]}, server_id)
        elif (folder or "").startswith('genres-'):
            listing = self.Downloader.get_filtered_section(view_id, self.get_media_type(content_type), None, None, None, None, None, {'GenreIds': folder.split('-')[1]}, server_id)
        elif folder == 'favepisodes':
            listing = self.Downloader.get_filtered_section(None, self.get_media_type(content_type), 25, None, None, None, ['IsFavorite'], None, server_id)
        elif media == 'homevideos':
            listing = self.Downloader.get_filtered_section(folder or view_id, self.get_media_type(content_type), None, False, None, None, None, None, server_id)
        elif media == 'movies':
            listing = self.Downloader.get_filtered_section(folder or view_id, self.get_media_type(content_type), None, True, None, None, None, None, server_id)
        elif media in ('boxset', 'library'):
            listing = self.Downloader.get_filtered_section(folder or view_id, None, None, True, None, None, None, None, server_id)
        elif media == 'episodes':
            listing = self.Downloader.get_filtered_section(folder or view_id, self.get_media_type(content_type), None, True, None, None, None, None, server_id)
        elif media == 'boxsets':
            listing = self.Downloader.get_filtered_section(folder or view_id, None, None, False, None, None, ['Boxsets'], None, server_id)
        elif media == 'tvshows':
            listing = self.Downloader.get_filtered_section(folder or view_id, self.get_media_type(content_type), None, True, None, None, None, None, server_id)
        elif media == 'seasons':
            listing = self.EMBY['api'].get_seasons(folder)
        elif media == 'playlists':
            listing = self.Downloader.get_filtered_section(folder or view_id, None, None, False, None, None, None, None, server_id, True)
        elif media != 'files':
            listing = self.Downloader.get_filtered_section(folder or view_id, self.get_media_type(content_type), None, False, None, None, None, None, server_id)
        else:
            listing = self.Downloader.get_filtered_section(folder or view_id, None, None, False, None, None, None, None, server_id)

        if listing:
            listitems = core.listitem.ListItem(self.EMBY['auth/server-address'], self.Utils)
            list_li = []
            listing = listing if isinstance(listing, list) else listing.get('Items', [])

            for item in listing:
                if self.Utils.window('emby_should_stop.bool'):
                    return

                li = xbmcgui.ListItem()
                li.setProperty('embyid', item['Id'])
                li.setProperty('embyserver', server_id)
                li = listitems.set(item, li, None, False, None)

                if item.get('IsFolder'):
                    params = {
                        'id': view_id or item['Id'],
                        'mode': "browse",
                        'type': self.get_folder_type(item, media) or media,
                        'folder': item['Id'],
                        'server': server_id
                    }

                    path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
                    contextData = []

                    if item['Type'] in ('Series', 'Season', 'Playlist'):
                        contextData.append(("Play", "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id)))

                    if item['UserData']['Played']:
                        contextData.append((helper.translate._(16104), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                    else:
                        contextData.append((helper.translate._(16103), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                    li.addContextMenuItems(contextData)
                    list_li.append((path, li, True))
                elif item['Type'] == 'Genre':
                    params = {
                        'id': view_id or item['Id'],
                        'mode': "browse",
                        'type': self.get_folder_type(item, media) or media,
                        'folder': 'genres-%s' % item['Id'],
                        'server': server_id
                    }

                    path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
                    list_li.append((path, li, True))
                else:
                    if item['Type'] == 'Photo':
                        path = "plugin://plugin.video.emby-next-gen/?mode=photoviewer&id=%s" % item['Id']
                        li.setProperty('path', path)
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
                            if 'MediaSources' in item:
                                FilenameURL = self.Utils.PathToFilenameReplaceSpecialCharecters(item['Path'])

                                if len(item['MediaSources'][0]['MediaStreams']) >= 1:
                                    path = "http://127.0.0.1:57578/%s/%s-%s-%s-stream-%s" % (Type, item['Id'], item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], FilenameURL)
                                else:
                                    path = "http://127.0.0.1:57578/%s/%s-%s-stream-%s" % (Type, item['Id'], item['MediaSources'][0]['Id'], FilenameURL)

                        self.Utils.window('emby_DynamicItem_' + path, item['Id'])

                        li.setProperty('path', path)
                        contextData = [(helper.translate._(13412), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id))]

                        if item['UserData']['Played']:
                            contextData.append((helper.translate._(16104), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                        else:
                            contextData.append((helper.translate._(16103), "RunPlugin(plugin://plugin.video.emby-next-gen/?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                        li.addContextMenuItems(contextData)

                    list_li.append((li.getProperty('path'), li, False))

            xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))

        if content_type == 'images':
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

        xbmcplugin.setContent(Handle, content_type)
        xbmcplugin.endOfDirectory(Handle)

    #Display submenus for emby views
    def browse_subfolders(self, Handle, media, view_id, server_id=None):
        self.get_server(server_id)
        view = self.EMBY['api'].get_item(view_id)
        xbmcplugin.setPluginCategory(Handle, view['Name'])

        for node in self.DYNNODES[media]:
            params = {
                'id': view_id,
                'mode': "browse",
                'type': media,
                'folder': view_id if node[0] == 'all' else node[0],
                'server': server_id
            }
            path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
            self.directory(Handle, node[1] or view['Name'], path)

        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    #Display letters as options
    def browse_letters(self, Handle, media, view_id, server_id=None):
        letters = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.get_server(server_id)
        view = self.EMBY['api'].get_item(view_id)
        xbmcplugin.setPluginCategory(Handle, view['Name'])

        for node in letters:
            params = {
                'id': view_id,
                'mode': "browse",
                'type': media,
                'folder': 'firstletter-%s' % node,
                'server': server_id
            }
            path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
            self.directory(Handle, node, path)

        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)

    def get_folder_type(self, item, content_type=None):
        media = item['Type']

        if media == 'Series':
            return "seasons"
        elif media == 'Season':
            return "episodes"
        elif media == 'BoxSet':
            return "boxset"
        elif media == 'MusicArtist':
            return "albums"
        elif media == 'MusicAlbum':
            return "songs"
        elif media == 'CollectionFolder':
            return item.get('CollectionType', 'library')
        elif media == 'Folder' and content_type == 'music':
            return "albums"
        else:
            return None

    def get_media_type(self, media):
        if media == 'movies':
            return "Movie,BoxSet"
        elif media == 'homevideos':
            return "Video,Folder,PhotoAlbum,Photo"
        elif media == 'episodes':
            return "Episode"
        elif media == 'boxsets':
            return "BoxSet"
        elif media == 'tvshows':
            return "Series"
        elif media == 'music':
            return "MusicArtist,MusicAlbum,Audio"
        else:
            return None

    #Get extra fanart for listitems. This is called by skinhelper.
    #Images are stored locally, due to the Kodi caching system
    def get_fanart(self, Handle, item_id, path, server_id=None):
        if not item_id and 'plugin.video.emby-next-gen' in path:
            item_id = path.split('/')[-2]

        if not item_id:
            return

        self.LOG.info("[ extra fanart ] %s", item_id)
        self.get_server(server_id)
        objects = core.obj_ops.Objects(self.Utils)
        list_li = []
        directory = self.Utils.translatePath("special://thumbnails/emby/%s/" % item_id)

        if not xbmcvfs.exists(directory):
            xbmcvfs.mkdirs(directory)
            item = self.EMBY['api'].get_item(item_id)
            obj = objects.map(item, 'Artwork')
            backdrops = helper.api.API(item, self.Utils, self.EMBY['auth/server-address']).get_all_artwork(obj)
            tags = obj['BackdropTags']

            for index, backdrop in enumerate(backdrops):
                tag = tags[index]
                fanart = os.path.join(directory, "fanart%s.jpg" % tag)
                li = xbmcgui.ListItem(tag, path=fanart)
                xbmcvfs.copy(backdrop, fanart)
                list_li.append((fanart, li, False))
        else:
            self.LOG.debug("cached backdrop found")
            dirs, files = xbmcvfs.listdir(directory)

            for filename in files:
                fanart = os.path.join(directory, filename)
                li = xbmcgui.ListItem(filename, path=fanart)
                list_li.append((fanart, li, False))

        xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
        xbmcplugin.endOfDirectory(Handle)

    #Returns the video files for the item as plugin listing, can be used
    #to browse actual files or video extras, etc
    def get_video_extras(self, item_id, path, server_id=None):
        if not item_id and 'plugin.video.emby-next-gen' in path:
            item_id = path.split('/')[-2]

        if not item_id:
            return

        self.get_server(server_id)

    #Only for synced content
    def get_next_episodes(self, Handle, item_id, limit):
        with database.database.Database('emby') as embydb:

            db = database.emby_db.EmbyDatabase(embydb.cursor)
            library = db.get_view_name(item_id)

            if not library:
                return

        result = helper.utils.JSONRPC('VideoLibrary.GetTVShows').execute({
            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % library}
                ]},
            'properties': ['title', 'studio', 'mpaa', 'file', 'art']
        })

        try:
            items = result['result']['tvshows']
        except (KeyError, TypeError):
            return

        list_li = []

        for item in items:
            if self.Utils.settings('ignoreSpecialsNextEpisodes.bool'):
                params = {
                    'tvshowid': item['tvshowid'],
                    'sort': {'method': "episode"},
                    'filter': {
                        'and': [
                            {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                            {'operator': "greaterthan", 'field': "season", 'value': "0"}]
                    },
                    'properties': [
                        "title", "playcount", "season", "episode", "showtitle",
                        "plot", "file", "rating", "resume", "tvshowid", "art",
                        "streamdetails", "firstaired", "runtime", "writer",
                        "dateadded", "lastplayed"
                    ],
                    'limits': {"end": 1}
                }
            else:
                params = {
                    'tvshowid': item['tvshowid'],
                    'sort': {'method': "episode"},
                    'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                    'properties': [
                        "title", "playcount", "season", "episode", "showtitle",
                        "plot", "file", "rating", "resume", "tvshowid", "art",
                        "streamdetails", "firstaired", "runtime", "writer",
                        "dateadded", "lastplayed"
                    ],
                    'limits': {"end": 1}
                }

            result = helper.utils.JSONRPC('VideoLibrary.GetEpisodes').execute(params)

            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                pass
            else:
                for episode in episodes:
                    li = self.create_listitem(episode)
                    list_li.append((episode['file'], li))

            if len(list_li) == limit:
                break

        xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
        xbmcplugin.setContent(Handle, 'episodes')
        xbmcplugin.endOfDirectory(Handle)

    #Listitem based on jsonrpc items
    def create_listitem(self, item):
        title = item['title']
        label2 = ""
        li = xbmcgui.ListItem(title)
        li.setProperty('IsPlayable', "true")

        metadata = {
            'Title': title,
            'duration': str(item['runtime']/60),
            'Plot': item['plot'],
            'Playcount': item['playcount']
        }

        if "showtitle" in item:
            metadata['TVshowTitle'] = item['showtitle']
            label2 = item['showtitle']

        if "episodeid" in item:
            # Listitem of episode
            metadata['mediatype'] = "episode"
            metadata['dbid'] = item['episodeid']

        if "episode" in item:
            episode = item['episode']
            metadata['Episode'] = episode

        if "season" in item:
            season = item['season']
            metadata['Season'] = season

        if season and episode:
            episodeno = "s%.2de%.2d" % (season, episode)
            li.setProperty('episodeno', episodeno)
            label2 = "%s - %s" % (label2, episodeno) if label2 else episodeno

        if "firstaired" in item:
            metadata['Premiered'] = item['firstaired']

        if "rating" in item:
            metadata['Rating'] = str(round(float(item['rating']), 1))

        if "director" in item:
            metadata['Director'] = " / ".join(item['director'])

        if "writer" in item:
            metadata['Writer'] = " / ".join(item['writer'])

        if "cast" in item:
            cast = []
            castandrole = []
            for person in item['cast']:
                name = person['name']
                cast.append(name)
                castandrole.append((name, person['role']))
            metadata['Cast'] = cast
            metadata['CastAndRole'] = castandrole

        li.setLabel2(label2)
        li.setInfo(type="Video", infoLabels=metadata)
        li.setProperty('resumetime', str(item['resume']['position']))
        li.setProperty('totaltime', str(item['resume']['total']))
        li.setArt(item['art'])
#        li.setArt({"thumb": item['art'].get('thumb',''), "icon" : 'DefaultFolder.png'     })
#        li.setThumbnailImage(item['art'].get('thumb',''))
#        self.li.setArt({"thumb": item['art'].get('thumb',''), "icon" : 'DefaultFolder.png'     })
#        li.setIconImage('DefaultTVShows.png')
        li.setProperty('dbid', str(item['episodeid']))
        li.setProperty('fanart_image', item['art'].get('tvshow.fanart', ''))

        for key, value in list(item['streamdetails'].items()):
            for stream in value:
                li.addStreamInfo(key, stream)

        return li

    #Add or remove users from the default server session
    #permanent=True from the add-on settings
    def add_user(self, permanent=False):
        if not self.Utils.window('emby_online.bool'):
            return

        self.get_server()
        session = self.EMBY['api'].get_device(self.EMBY['config/app.device_id'])
        hidden = None if self.Utils.settings('addUsersHidden.bool') else False
        users = self.EMBY['api'].get_users(False, hidden)

        for user in users:
            if user['Id'] == session[0]['UserId']:
                users.remove(user)
                break

        while True:
            session = self.EMBY['api'].get_device(self.EMBY['config/app.device_id'])
            additional = current = session[0]['AdditionalUsers']
            add_session = True

            if permanent:
                perm_users = self.Utils.settings('addUsers').split(',') if self.Utils.settings('addUsers') else []
                current = []

                for user in users:
                    for perm_user in perm_users:

                        if user['Id'] == perm_user:
                            current.append({'UserName': user['Name'], 'UserId': user['Id']})

            result = self.Utils.dialog("select", helper.translate._(33061), [helper.translate._(33062), helper.translate._(33063)] if current else [helper.translate._(33062)])

            if result < 0:
                break

            if not result: # Add user
                eligible = [x for x in users if x['Id'] not in [current_user['UserId'] for current_user in current]]
                resp = self.Utils.dialog("select", helper.translate._(33064), [x['Name'] for x in eligible])

                if resp < 0:
                    break

                user = eligible[resp]

                if permanent:
                    perm_users.append(user['Id'])
                    self.Utils.settings('addUsers', ','.join(perm_users))

                    if user['Id'] in [current_user['UserId'] for current_user in additional]:
                        add_session = False

                if add_session:
                    self.Utils.event('AddUser', {'Id': user['Id'], 'Add': True})

                self.Utils.dialog("notification", heading="{emby}", message="%s %s" % (helper.translate._(33067), user['Name']), icon="{emby}", time=1000, sound=False)
            else: # Remove user
                resp = self.Utils.dialog("select", helper.translate._(33064), [x['UserName'] for x in current])

                if resp < 0:
                    break

                user = current[resp]

                if permanent:
                    perm_users.remove(user['UserId'])
                    self.Utils.settings('addUsers', ','.join(perm_users))

                if add_session:
                    self.Utils.event('AddUser', {'Id': user['UserId'], 'Add': False})

                self.Utils.dialog("notification", heading="{emby}", message="%s %s" % (helper.translate._(33066), user['UserName']), icon="{emby}", time=1000, sound=False)

    #Add theme media locally, via strm. This is only for tv tunes.
    #If another script is used, adjust this code
    def get_themes(self):
        library = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/library")
        play = self.Utils.settings('useDirectPaths') == "1"

        if not xbmcvfs.exists(library + '/'):
            xbmcvfs.mkdir(library)

        if xbmc.getCondVisibility('System.HasAddon(script.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="script.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', library)
            self.LOG.info("TV Tunes custom path is enabled and set.")
        elif xbmc.getCondVisibility('System.HasAddon(service.tvtunes)'):
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', library)
            self.LOG.info("TV Tunes custom path is enabled and set.")
        else:
            self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33152))
            return

        with database.database.Database('emby') as embydb:
            all_views = database.emby_db.EmbyDatabase(embydb.cursor).get_views()
            views = [x[0] for x in all_views if x[2] in ('movies', 'tvshows', 'mixed')]

        self.get_server()
        items = {}

        for view in views:
            for result in self.Downloader.get_items(view, params={'HasThemeVideo': True}):
                for item in result['Items']:
                    folder = self.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

            for result in self.Downloader.get_items(view, params={'HasThemeSong': True}):
                for item in result['Items']:
                    folder = self.Utils.normalize_string(item['Name'])
                    items[item['Id']] = folder

        for item in items:
            nfo_path = os.path.join(library, items[item])
            nfo_file = os.path.join(nfo_path, "tvtunes.nfo")

            if not xbmcvfs.exists(nfo_path):
                xbmcvfs.mkdir(nfo_path)

            themes = self.EMBY['api'].get_themes(item)
            paths = []

            for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
                if play:
                    paths.append(theme['MediaSources'][0]['Path'])
                else:
                    paths.append(self.Utils.direct_url(theme))

            self.xmls.tvtunes_nfo(nfo_file, paths)

        self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33153), icon="{emby}", time=1000, sound=False)

    #Delete keymap action
    def delete_item(self):
        context.Context(delete=True)

    #Emby backup
    def backup(self):
        path = self.Utils.settings('backupPath')
        folder_name = "Kodi%s.%s" % (xbmc.getInfoLabel('System.BuildVersion')[:2], xbmc.getInfoLabel('System.Date(dd-mm-yy)'))
        folder_name = self.Utils.dialog("input", heading=helper.translate._(33089), default=folder_name)

        if not folder_name:
            return

        backup = os.path.join(path, folder_name)

        if xbmcvfs.exists(backup + '/'):
            if not self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33090)):
                return backup()

            self.Utils.delete_folder(backup)

        addon_data = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen")
        destination_data = os.path.join(backup, "addon_data", "plugin.video.emby-next-gen")
        destination_databases = os.path.join(backup, "Database")

        if not xbmcvfs.mkdirs(path) or not xbmcvfs.mkdirs(destination_databases):
            self.LOG.info("Unable to create all directories")
            self.Utils.dialog("notification", heading="{emby}", icon="{emby}", message=helper.translate._(33165), sound=False)
            return

        self.Utils.copytree(addon_data, destination_data)
        db = self.Utils.translatePath("special://database/")
        dirs, files = xbmcvfs.listdir(db)

        for Temp in files:
            if 'MyVideos' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s", Temp)
            elif 'emby' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s", Temp)
            elif 'MyMusic' in Temp:
                xbmcvfs.copy(os.path.join(db, Temp), os.path.join(destination_databases, Temp))
                self.LOG.info("copied %s", Temp)

        self.LOG.info("backup completed")
        self.Utils.dialog("ok", heading="{emby}", line1="%s %s" % (helper.translate._(33091), backup))

    def cache_artwork(self):
        core.artwork.Artwork(None, self.Utils).cache_textures()

if __name__ == "__main__":
    Events(sys.argv)

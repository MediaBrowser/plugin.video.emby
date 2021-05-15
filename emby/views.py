# -*- coding: utf-8 -*-
import os

try:
    from urllib import urlencode
except:
    from urllib.parse import urlencode

import xml.etree.ElementTree
import xbmcvfs
import xbmcgui
import database.database
import database.emby_db
import helper.api
import helper.loghandler

class Views():
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.limit = 25
        self.media_folders = None
        self.LOG = helper.loghandler.LOG('EMBY.emby.views.Views')
        self.APIHelper = helper.api.API(self.EmbyServer.Utils.Basics, self.EmbyServer.Data['auth.ssl'])
        self.LibraryIcons = {}
        self.NODES = {
            'tvshows': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultTVShows.png'),
                ('recentlyadded', self.EmbyServer.Utils.Basics.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
                ('recentlyaddedepisodes', self.EmbyServer.Utils.Basics.Translate(30175), 'DefaultRecentlyAddedEpisodes.png'),
                ('inprogress', self.EmbyServer.Utils.Basics.Translate(30171), 'DefaultInProgressShows.png'),
                ('inprogressepisodes', self.EmbyServer.Utils.Basics.Translate(30178), 'DefaultInProgressShows.png'),
                ('genres', "Genres", 'DefaultGenre.png'),
                ('random', self.EmbyServer.Utils.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
                ('recommended', self.EmbyServer.Utils.Basics.Translate(30230), 'DefaultFavourites.png'),
                ('years', self.EmbyServer.Utils.Basics.Translate(33218), 'DefaultYear.png'),
                ('actors', self.EmbyServer.Utils.Basics.Translate(33219), 'DefaultActor.png'),
                ('tags', self.EmbyServer.Utils.Basics.Translate(33220), 'DefaultTags.png'),
                ('unwatched', "Unwatched TV Shows", 'OverlayUnwatched.png'),
                ('unwatchedepisodes', "Unwatched Episodes", 'OverlayUnwatched.png'),
                ('studios', "Studios", 'DefaultStudios.png'),
                ('recentlyplayed', 'Recently played TV Show', 'DefaultMusicRecentlyPlayed.png'),
                ('recentlyplayedepisode', 'Recently played Episode', 'DefaultMusicRecentlyPlayed.png'),
                ('nextepisodes', self.EmbyServer.Utils.Basics.Translate(30179), 'DefaultInProgressShows.png')
            ],
            'movies': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMovies.png'),
                ('recentlyadded', self.EmbyServer.Utils.Basics.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
                ('inprogress', self.EmbyServer.Utils.Basics.Translate(30177), 'DefaultInProgressShows.png'),
                ('unwatched', self.EmbyServer.Utils.Basics.Translate(30189), 'OverlayUnwatched.png'),
                ('sets', "Sets", 'DefaultSets.png'),
                ('genres', "Genres", 'DefaultGenre.png'),
                ('random', self.EmbyServer.Utils.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
                ('recommended', self.EmbyServer.Utils.Basics.Translate(30230), 'DefaultFavourites.png'),
                ('years', self.EmbyServer.Utils.Basics.Translate(33218), 'DefaultYear.png'),
                ('actors', self.EmbyServer.Utils.Basics.Translate(33219), 'DefaultActor.png'),
                ('tags', self.EmbyServer.Utils.Basics.Translate(33220), 'DefaultTags.png'),
                ('studios', "Studios", 'DefaultStudios.png'),
                ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
                ('directors', 'Directors', 'DefaultDirector.png'),
                ('countries', 'Countries', 'DefaultCountry.png')
            ],
            'musicvideos': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('recentlyadded', self.EmbyServer.Utils.Basics.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
                ('years', self.EmbyServer.Utils.Basics.Translate(33218), 'DefaultMusicYears.png'),
                ('genres', "Genres", 'DefaultGenre.png'),
                ('inprogress', self.EmbyServer.Utils.Basics.Translate(30257), 'DefaultInProgressShows.png'),
                ('random', self.EmbyServer.Utils.Basics.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
                ('unwatched', self.EmbyServer.Utils.Basics.Translate(30258), 'OverlayUnwatched.png'),
                ('artists', "Artists", 'DefaultMusicArtists.png'),
                ('albums', "Albums", 'DefaultMusicAlbums.png'),
                ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png')
            ],
            'music': [
                ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
                ('all', None, 'DefaultMusicVideos.png'),
                ('years', self.EmbyServer.Utils.Basics.Translate(33218), 'DefaultMusicYears.png'),
                ('genres', "Genres", 'DefaultMusicGenres.png'),
                ('artists', "Artists", 'DefaultMusicArtists.png'),
                ('albums', "Albums", 'DefaultMusicAlbums.png'),
                ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
                ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
                ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
                ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
                ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
            ]
        }

    def IconDownload(self, URL, FileID):
        request = {'type': "GET", 'url': URL, 'params': {}}
        Filename = self.EmbyServer.Utils.Basics.PathToFilenameReplaceSpecialCharecters(FileID)# + ".jpg")
        FilePath = self.EmbyServer.Utils.Basics.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/temp/") + Filename

        if not xbmcvfs.exists(FilePath):
            return self.EmbyServer.Utils.download_file_from_Embyserver(request, Filename, self.EmbyServer)

        return FilePath

    def add_favorites(self, index, view):
        path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/video")
        filepath = os.path.join(path, "emby_%s.xml" % view['Tag'].replace(" ", ""))

        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
        except Exception:
            if view['Media'] == 'episodes':
                xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "folder"})
            else:
                xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "filter"})

            xml.etree.ElementTree.SubElement(xmlData, 'icon').text = self.EmbyServer.Utils.Basics.translatePath("special://home/addons/plugin.video.emby-next-gen/resources/DefaultFavourites.png")
            xml.etree.ElementTree.SubElement(xmlData, 'label')
            xml.etree.ElementTree.SubElement(xmlData, 'match')
            xml.etree.ElementTree.SubElement(xmlData, 'content')

        label = xmlData.find('label')
        label.text = view['Name']
        content = xmlData.find('content')
        content.text = view['Media']
        match = xmlData.find('match')
        match.text = "all"

        if view['Media'] != 'episodes':
            for rule in xmlData.findall('.//value'):
                if rule.text == view['Tag']:
                    break
            else:
                rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
                xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

            self.node_all(xmlData)
        else:
            params = {
                'mode': "browse",
                'type': "Episode",
                'folder': 'FavEpisodes'
            }
            path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
            self.node_favepisodes(xmlData, path)

        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    def update_nodes(self):
        index = 0

        #Favorites
        for single in [{'Name': self.EmbyServer.Utils.Basics.Translate('fav_movies'), 'Tag': "Favorite movies", 'Media': "movies"}, {'Name': self.EmbyServer.Utils.Basics.Translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'Media': "tvshows"}, {'Name': self.EmbyServer.Utils.Basics.Translate('fav_episodes'), 'Tag': "Favorite episodes", 'Media': "episodes"}]:
            self.add_favorites(index, single)
            index += 1

        #Specific nodes
        with database.database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)

            #update nodes and playlist
            for library in self.EmbyServer.Utils.SyncData['Whitelist']:
                library = library.replace('Mixed:', "")
                view = db.get_view(library)

                if view:
                    view = {'LibraryId': library, 'Name': view[1], 'Tag': view[1], 'Media': view[2], "Icon": self.LibraryIcons[library], 'NameClean': self.EmbyServer.Utils.Basics.StringDecode(view[1]).replace(" ", ""), 'MediaClean': view[2].replace(" ", "")}

                    if view['Media'] == 'music':
                        node_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/music")
                        playlist_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/playlists/music")
                    else:
                        node_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/video")
                        playlist_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/playlists/video")

                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):
                            view['Media'] = media
                            view['MediaClean'] = media.replace(" ", "")
                            self.add_playlist(playlist_path, view, True)
                            self.add_nodes(node_path, view)

                        index += 1 # Compensate for the duplicate.
                    else:
                        self.add_playlist(playlist_path, view, False)
                        self.add_nodes(node_path, view)

                    index += 1

        node_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/video")
        playlist_path = self.EmbyServer.Utils.Basics.translatePath("special://profile/playlists/video")
        self.window_nodes()

    def window_nodes(self):
        with database.database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
            libraries = database.emby_db.EmbyDatabase(embydb.cursor).get_views()

        index = 0

        for library in libraries:
            if library[0] in self.LibraryIcons:
                icon = self.LibraryIcons[library[0]]
            else:
                icon = None

            if not icon:
                if library[2] == 'tvshows':
                    icon = 'DefaultTVShows.png'
                elif library[2] == 'movies':
                    icon = 'DefaultMovies.png'
                elif library[2] == 'musicvideos':
                    icon = 'DefaultMusicVideos.png'
                elif library[2] == 'music':
                    icon = 'DefaultMusicVideos.png'
                else:
                    icon = self.EmbyServer.Utils.Basics.translatePath("special://home/addons/plugin.video.emby-next-gen/resources/icon.png")

            view = {'LibraryId': library[0], 'Name': library[1], 'Tag': library[1], 'Media': library[2], 'Icon': icon, 'NameClean': self.EmbyServer.Utils.Basics.StringDecode(library[1]).replace(" ", ""), 'MediaClean': library[2].replace(" ", "")}

            if library[0] in [x.replace('Mixed:', "") for x in self.EmbyServer.Utils.SyncData['Whitelist']]: # Synced libraries
                if view['Media'] in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):
                            temp_view = view
                            temp_view['Media'] = media
                            temp_view['MediaClean'] = media.replace(" ", "")
                            self.window_node(index, temp_view, False, True)
                            index += 1
                    else:
                        self.window_node(index, view, False, False)
                        index += 1
            else: #Dynamic entry
                self.window_node(index, view, True, False)
                index += 1

        self.EmbyServer.Utils.Basics.window('emby.nodes.%s.total' % self.EmbyServer.server_id, str(index))

    #Leads to another listing of nodes
    def window_node(self, index, view, dynamic, mixed):
        NodeData = {}

        if dynamic:
            params = {
                'mode': "browse",
                'type': view['Media'],
                'name': view['Name'].encode('utf-8')
            }

            if view.get('LibraryId'):
                params['id'] = view['LibraryId']

            path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))
            NodeData['title'] = "%s (%s)" % (view['Name'], self.EmbyServer.Data['auth.server-name'])
        else:
            if view['Media'] == 'music':
                path = "library://music/emby_%s_%s" % (view['MediaClean'], view['NameClean'])
            else:
                path = "library://video/emby_%s_%s" % (view['MediaClean'], view['NameClean'])

            if mixed:
                NodeData['title'] = "%s (%s)" % (view['Name'], view['Media'])
            else:
                NodeData['title'] = view['Name']

        NodeData['path'] = path
        NodeData['id'] = view['LibraryId']
        NodeData['type'] = view['Media']
        NodeData['icon'] = view['Icon']
        self.EmbyServer.Utils.Basics.window('Emby.nodes.%s.%s.json' % (self.EmbyServer.server_id, index), NodeData)

    def update_views(self):
        ViewsData = self.EmbyServer.API.get_views()['Items']
        Total = len(ViewsData)
        Counter = 1
        Progress = xbmcgui.DialogProgressBG()
        Progress.create(self.EmbyServer.Utils.Basics.Translate('addon_name'), "Update views")
        self.EmbyServer.Utils.SyncData['SortedViews'] = [x['Id'] for x in ViewsData]

        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            for library in ViewsData:
                Percent = int(Counter / Total * 100)
                Counter += 1
                Progress.update(Percent, message="Update views")

                if library['Type'] == 'Channel':
                    library['Media'] = "channels"
                else:
                    library['Media'] = library.get('CollectionType', "mixed")

                database.emby_db.EmbyDatabase(embydb.cursor).add_view(library['Id'], library['Name'], library['Media'])

                #Cache artwork
                icon = self.APIHelper.get_artwork(library['Id'], 'Primary', None, [('Index', 0)])
                iconpath = self.IconDownload(icon, "%s_%s" % (self.EmbyServer.Data['auth.server-name'], library['Id']))
                self.LibraryIcons[library['Id']] = iconpath

        Progress.close()

    def remove_library(self, view_id):
        self.delete_playlist_by_id(view_id)
        self.delete_node_by_id(view_id)
        whitelist = self.EmbyServer.Utils.SyncData['Whitelist']

        if view_id in whitelist:
            whitelist.remove(view_id)

        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData)
        self.update_nodes()

    #Create or update the xps file
    def add_playlist(self, path, view, mixed):
        filepath = os.path.join(path, "emby_%s.xsp" % (view['Name'].replace(" ", "_")))

        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
        except Exception:
            xmlData = xml.etree.ElementTree.Element('smartplaylist', {'type': view['Media']})
            xml.etree.ElementTree.SubElement(xmlData, 'name')
            xml.etree.ElementTree.SubElement(xmlData, 'match')

        name = xmlData.find('name')
        name.text = view['Name'] if not mixed else "%s (%s)" % (view['Name'], view['Media'])
        match = xmlData.find('match')
        match.text = "all"

        for rule in xmlData.findall('.//value'):
            if rule.text == view['Tag']:
                break
        else:
            rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    #Create or update the video node file
    def add_nodes(self, path, view):
        folder = os.path.join(path, "emby_%s_%s" % (view['MediaClean'], view['NameClean']))

        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdir(folder)

        #index.xml (root)
        filepath = os.path.join(folder, "index.xml")

        if not xbmcvfs.exists(filepath):
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0"})
            xml.etree.ElementTree.SubElement(xmlData, 'label').text = "EMBY: %s (%s)" % (view['Name'], view['Media'])

            if view['Icon']:
                Icon = view['Icon']
            else:
                if view['Media'] == 'tvshows':
                    Icon = 'DefaultTVShows.png'
                elif view['Media'] == 'movies':
                    Icon = 'DefaultMovies.png'
                elif view['Media'] == 'musicvideos':
                    Icon = 'DefaultMusicVideos.png'
                elif view['Media'] == 'music':
                    Icon = 'DefaultMusicVideos.png'
                else:
                    Icon = self.EmbyServer.Utils.Basics.translatePath("special://home/addons/plugin.video.emby-next-gen/resources/icon.png")

            xml.etree.ElementTree.SubElement(xmlData, 'icon').text = Icon
            self.EmbyServer.Utils.indent(xmlData, 0)
            self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

        #specific nodes
        for node in self.NODES[view['Media']]:
            if node[1]:
                xml_label = node[1] #Specific
            else:
                xml_label = view['Name'] #All

            if node[0] == "letter":
                self.node_letter(view, folder, node)
            else:
                filepath = os.path.join(folder, "%s.xml" % node[0])

                if not xbmcvfs.exists(filepath):
                    if node[0] == 'nextepisodes':
                        NodeType = 'folder'
                    else:
                        NodeType = 'filter'

                    xmlData = xml.etree.ElementTree.Element('node', {'order': str(self.NODES[view['Media']].index(node)), 'type': NodeType})
                    xml.etree.ElementTree.SubElement(xmlData, 'label').text = xml_label
                    xml.etree.ElementTree.SubElement(xmlData, 'match').text = "all"
                    xml.etree.ElementTree.SubElement(xmlData, 'content')
                    xml.etree.ElementTree.SubElement(xmlData, 'icon').text = node[2]
                    operator = "is"
                    field = "tag"
                    content = xmlData.find('content')

                    if view['Media'] == "music":
                        if node[0] in ("genres", "artists"):
                            content.text = "artists"
                            field = "disambiguation"

                        elif node[0] in ("years", "recentlyaddedalbums", "randomalbums", "albums"):
                            content.text = "albums"
                            field = "type"

                        elif node[0] in ("recentlyaddedsongs", "randomsongs", "all", "recentlyplayed"):
                            content.text = "songs"
                            operator = "contains"
                            field = "comment"
                    else:
                        if node[0] in ("recentlyaddedepisodes", "inprogressepisodes", "recentlyplayedepisode"):
                            content.text = "episodes"
                        else:
                            content.text = view['Media']

                    for rule in xmlData.findall('.//value'):
                        if rule.text == view['Tag']:
                            break
                    else:
                        rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': field, 'operator': operator})
                        xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

                    if node[0] == 'nextepisodes':
                        self.node_nextepisodes(xmlData, view['Name'])
                    else:
                        getattr(self, 'node_' + node[0])(xmlData) # get node function based on node type

                    self.EmbyServer.Utils.indent(xmlData, 0)
                    self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    def node_letter(self, View, folder, node):
        Index = 1
        FolderPath = os.path.join(folder, "letter/")

        if not xbmcvfs.exists(FolderPath):
            xbmcvfs.mkdir(FolderPath)

        #index.xml
        FileName = os.path.join(FolderPath, "index.xml")

        if not xbmcvfs.exists(FileName):
            xmlData = xml.etree.ElementTree.Element('node')
            xmlData.set('order', '0')
            xmlData.set('type', "folder")
            xml.etree.ElementTree.SubElement(xmlData, "label").text = node[1]
            xml.etree.ElementTree.SubElement(xmlData, 'icon').text = self.EmbyServer.Utils.Basics.translatePath(node[2])
            self.EmbyServer.Utils.indent(xmlData, 0)
            self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FileName)

        #0-9.xml
        FileName = os.path.join(FolderPath, "0-9.xml")

        if not xbmcvfs.exists(FileName):
            xmlData = xml.etree.ElementTree.Element('node')
            xmlData.set('order', str(Index))
            xmlData.set('type', "filter")
            xml.etree.ElementTree.SubElement(xmlData, "label").text = "0-9"
            xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

            if View['Media'] == "music":
                xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
            else:
                xml.etree.ElementTree.SubElement(xmlData, "content").text = View['Media']

            xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
            xmlRule.text = View['Tag']

            if View['Media'] == "music":
                xmlRule.set('field', "disambiguation")
            else:
                xmlRule.set('field', "tag")

            xmlRule.set('operator', "is")
            xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")

            if View['Media'] == "music":
                xmlRule.set('field', "artist")
            else:
                xmlRule.set('field', "sorttitle")

            xmlRule.set('operator', "startswith")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "0"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "1"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "2"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "3"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "4"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "5"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "6"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "7"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "8"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = "9"
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("&")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("Ä")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("Ö")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("Ü")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("!")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("(")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(")")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("@")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("#")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("$")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("^")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("*")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("-")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("=")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("+")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("{")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("}")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("[")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("]")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("?")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(":")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(";")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("'")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(",")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(".")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("<")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode(">")
            xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.Basics.StringDecode("~")
            xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
            self.EmbyServer.Utils.indent(xmlData, 0)
            self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FileName)

            #Alphabetically
            FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

            for FileName in FileNames:
                Index += 1
                FilePath = os.path.join(FolderPath, "%s.xml" % FileName)

                if not xbmcvfs.exists(FilePath):
                    xmlData = xml.etree.ElementTree.Element('node')
                    xmlData.set('order', str(Index))
                    xmlData.set('type', "filter")
                    xml.etree.ElementTree.SubElement(xmlData, "label").text = FileName
                    xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

                    if View['Media'] == "music":
                        xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
                    else:
                        xml.etree.ElementTree.SubElement(xmlData, "content").text = View['Media']

                    xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                    xmlRule.text = View['Tag']

                    if View['Media'] == "music":
                        xmlRule.set('field', "disambiguation")
                    else:
                        xmlRule.set('field', "tag")

                    xmlRule.set('operator', "is")
                    xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                    xmlRule.text = FileName

                    if View['Media'] == "music":
                        xmlRule.set('field', "artist")
                    else:
                        xmlRule.set('field', "sorttitle")

                    xmlRule.set('operator', "startswith")
                    xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
                    self.EmbyServer.Utils.indent(xmlData, 0)
                    self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FilePath)

    def delete_playlist(self, path):
        xbmcvfs.delete(path)
        self.LOG.info("DELETE playlist %s" % path)

    #Remove all emby playlists
    def delete_playlists(self):
        path = self.EmbyServer.Utils.Basics.translatePath("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)

        for filename in files:
            if filename.startswith('emby'):
                self.delete_playlist(os.path.join(path, filename))

    #Remove playlist based based on view_id
    def delete_playlist_by_id(self, view_id):
        path = self.EmbyServer.Utils.Basics.translatePath("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)

        for filename in files:
            if filename.startswith('emby') and filename.endswith('%s.xsp' % view_id):
                self.delete_playlist(os.path.join(path, filename))

    def delete_node(self, path):
        xbmcvfs.delete(path)
        self.LOG.info("DELETE node %s" % path)

    #Remove node and children files
    def delete_nodes(self):
        path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/video/")
        dirs, files = xbmcvfs.listdir(path)

        for filename in files:
            if filename.startswith('emby'):
                self.delete_node(os.path.join(path, filename))

        for directory in dirs:
            if directory.startswith('emby'):
                _, files = xbmcvfs.listdir(os.path.join(path, directory))

                for filename in files:
                    self.delete_node(os.path.join(path, directory, filename))

                xbmcvfs.rmdir(os.path.join(path, directory))

    def delete_node_by_id(self, view_id):
        path = self.EmbyServer.Utils.Basics.translatePath("special://profile/library/video/")
        dirs, files = xbmcvfs.listdir(path)

        for directory in dirs:
            if directory.startswith('emby') and directory.endswith(view_id):
                _, files = xbmcvfs.listdir(os.path.join(path, directory))

                for filename in files:
                    self.delete_node(os.path.join(path, directory, filename))

                xbmcvfs.rmdir(os.path.join(path, directory))

    #Nodes
    def node_all(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    def node_recentlyplayed(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "lastplayed":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    def node_directors(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "directors":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "directors"

        for rule in root.findall('.//group'):
            rule.text = "directors"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "directors"

    def node_countries(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "countries":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "countries"

        for rule in root.findall('.//group'):
            rule.text = "countries"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "countries"

    def node_nextepisodes(self, root, LibraryName):
        params = {
            'libraryname': LibraryName,
            'mode': "nextepisodes",
            'limit': 25
        }
        path = "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))

        for rule in root.findall('.//path'):
            rule.text = path
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'path').text = path

        for rule in root.findall('.//content'):
            rule.text = "episodes"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'content').text = "episodes"

    def node_years(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "title":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

        for rule in root.findall('.//group'):
            rule.text = "years"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "years"

    def node_actors(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "title":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

        for rule in root.findall('.//group'):
            rule.text = "actors"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "actors"

    def node_artists(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "artists":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "artists"

        for rule in root.findall('.//group'):
            rule.text = "artists"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "artists"

    def node_albums(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "albums":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "albums"

        for rule in root.findall('.//group'):
            rule.text = "albums"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "albums"

    def node_studios(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "title":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

        for rule in root.findall('.//group'):
            rule.text = "studios"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "studios"

    def node_tags(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "title":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

        for rule in root.findall('.//group'):
            rule.text = "tags"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "tags"

    def node_recentlyadded(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    def node_inprogress(self, root):
        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'inprogress':
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_genres(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//group'):
            rule.text = "genres"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "genres"

    def node_unwatched(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    def node_unwatchedepisodes(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

        content = root.find('content')
        content.text = "episodes"

    def node_sets(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//group'):
            rule.text = "sets"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'group').text = "sets"

    def node_random(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "random":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_recommended(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "rating":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "rating"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'rating':
                rule.find('value').text = "7"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "rating", 'operator': "greaterthan"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "7"

    def node_recentlyepisodes(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

        content = root.find('content')
        content.text = "episodes"

    def node_inprogressepisodes(self, root):
        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'inprogress':
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator':"true"})
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

        content = root.find('content')
        content.text = "episodes"

    def node_favepisodes(self, root, path):
        for rule in root.findall('.//path'):
            rule.text = path
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'path').text = path

        for rule in root.findall('.//content'):
            rule.text = "episodes"
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'content').text = "episodes"

    def node_randomalbums(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "random":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_randomsongs(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "random":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_recentlyaddedsongs(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_recentlyaddedalbums(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

    def node_recentlyaddedepisodes(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            xml.etree.ElementTree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    def node_recentlyplayedepisode(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "lastplayed":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

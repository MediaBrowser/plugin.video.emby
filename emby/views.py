# -*- coding: utf-8 -*-
import os
import shutil

try:
    from urllib import urlencode
except:
    from urllib.parse import urlencode

import xml.etree.ElementTree
import xbmcvfs
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
        self.APIHelper = helper.api.API(self.EmbyServer.Utils, self.EmbyServer.Data['auth.ssl'])
        self.NODES = {
            'tvshows': [
                ('alphabet', None),
                ('all', None),
                ('recent', self.EmbyServer.Utils.Translate(30170)),
                ('recentepisodes', self.EmbyServer.Utils.Translate(30175)),
                ('inprogress', self.EmbyServer.Utils.Translate(30171)),
                ('inprogressepisodes', self.EmbyServer.Utils.Translate(30178)),
                ('nextepisodes', self.EmbyServer.Utils.Translate(30179)),
                ('genres', 135),
                ('random', self.EmbyServer.Utils.Translate(30229)),
                ('recommended', self.EmbyServer.Utils.Translate(30230)),
                ('years', self.EmbyServer.Utils.Translate(33218)),
                ('actors', self.EmbyServer.Utils.Translate(33219)),
                ('tags', self.EmbyServer.Utils.Translate(33220)),
                ('unwatched', "Unwatched TV Shows"),
                ('unwatchedepisodes', "Unwatched Episodes"),
                ('studios', "Studios"),
                ('recentplayed', 'Recently played'),
                ('directors', 'Directors'),
                ('countries', 'Countries')
            ],
            'movies': [
                ('alphabet', None),
                ('all', None),
                ('recent', self.EmbyServer.Utils.Translate(30174)),
                ('inprogress', self.EmbyServer.Utils.Translate(30177)),
                ('unwatched', self.EmbyServer.Utils.Translate(30189)),
                ('sets', 20434),
                ('genres', 135),
                ('random', self.EmbyServer.Utils.Translate(30229)),
                ('recommended', self.EmbyServer.Utils.Translate(30230)),
                ('years', self.EmbyServer.Utils.Translate(33218)),
                ('actors', self.EmbyServer.Utils.Translate(33219)),
                ('tags', self.EmbyServer.Utils.Translate(33220)),
                ('studios', "Studios"),
                ('recentplayed', 'Recently played'),
                ('directors', 'Directors'),
                ('countries', 'Countries')
            ],
            'musicvideos': [
                ('alphabet', None),
                ('all', None),
                ('recent', self.EmbyServer.Utils.Translate(30256)),
                ('years', self.EmbyServer.Utils.Translate(33218)),
                ('genres', 135),
                ('inprogress', self.EmbyServer.Utils.Translate(30257)),
                ('random', self.EmbyServer.Utils.Translate(30229)),
                ('unwatched', self.EmbyServer.Utils.Translate(30258)),
                ('artists', "Artists"),
                ('albums', "Albums"),
                ('recentplayed', 'Recently played')
            ],
            'music': [
                ('alphabet', None),
                ('years', self.EmbyServer.Utils.Translate(33218)),
                ('genres', 135),
                ('artists', "Artists"),
                ('albums', "Albums"),
                ('recentaddedalbums', 'Recently added albums'),
                ('recentaddedsongs', 'Recently added songs'),
                ('randomalbums', 'Random albums'),
                ('randomsongs', 'Random songs')
            ]
        }

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

    def node_recentaddedsongs(self, root):
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

    def node_recentaddedalbums(self, root):
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

    #Make sure we have the kodi default folder in place
    def verify_kodi_defaults(self):
        node_path = self.EmbyServer.Utils.translatePath("special://profile/library/video")

        if not xbmcvfs.exists(node_path):
            try:
                shutil.copytree(src=self.EmbyServer.Utils.translatePath("special://xbmc/system/library/video"), dst=self.EmbyServer.Utils.translatePath("special://profile/library/video"))
            except Exception as error:
                xbmcvfs.mkdir(node_path)

        for index, node in enumerate(['movies', 'tvshows', 'musicvideos']):
            filename = os.path.join(node_path, node, "index.xml")

            if xbmcvfs.exists(filename):
                try:
                    xmlData = xml.etree.ElementTree.parse(filename).getroot()
                except Exception as error:
                    self.LOG.error(error)
                    continue

                xmlData.set('order', str(17 + index))
                self.EmbyServer.Utils.indent(xmlData, 0)
                self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filename)

        playlist_path = self.EmbyServer.Utils.translatePath("special://profile/playlists/video")

        if not xbmcvfs.exists(playlist_path):
            xbmcvfs.mkdirs(playlist_path)

    #Add entry to view table in emby database
    def add_library(self, view):
        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            database.emby_db.EmbyDatabase(embydb.cursor).add_view(view['Id'], view['Name'], view['Media'])

    #Remove entry from view table in emby database
    def remove_library(self, view_id):
        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            database.emby_db.EmbyDatabase(embydb.cursor).remove_view(view_id)

        self.delete_playlist_by_id(view_id)
        self.delete_node_by_id(view_id)

    def get_libraries(self):
        try:
            if not self.EmbyServer.logged_in:
                return False

            libraries = self.EmbyServer.API.get_media_folders()['Items']
            views = self.EmbyServer.API.get_views()['Items']
        except:
            return False

        libraries.extend([x for x in views if x['Id'] not in [y['Id'] for y in libraries]])
        return libraries

    #Get the media folders. Add or remove them. Do not proceed if issue getting libraries
    def get_views(self):
        libraries = self.get_libraries()

        if not libraries:
            self.LOG.error("Unable to retrieve libraries")
            return

        self.EmbyServer.Utils.SyncData['SortedViews'] = [x['Id'] for x in libraries]

        for library in libraries:
            if library['Type'] == 'Channel':
                library['Media'] = "channels"
            else:
                library['Media'] = library.get('OriginalCollectionType', library.get('CollectionType', "mixed"))

            self.add_library(library)

        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            views = database.emby_db.EmbyDatabase(embydb.cursor).get_views()
            sorted_views = self.EmbyServer.Utils.SyncData['SortedViews']
            whitelist = self.EmbyServer.Utils.SyncData['Whitelist']
            removed = []

            for view in views:
                if view[0] not in sorted_views:
                    removed.append(view[0])

        if removed:
            self.EmbyServer.Utils.event('RemoveLibrary', {'Id': ','.join(removed)})

            for library_id in removed:
                if library_id in sorted_views:
                    sorted_views.remove(library_id)

                if library_id in whitelist:
                    whitelist.remove(library_id)

        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData)

    #Set up playlists, video nodes, window prop
    def get_nodes(self):
        index = 0

        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)

            for library in self.EmbyServer.Utils.SyncData['Whitelist']:
                library = library.replace('Mixed:', "")
                view = db.get_view(library)

                if view:
                    view = {'Id': library, 'Name': view[0], 'Tag': view[0], 'Media': view[1]}

                    if view['Media'] == 'music':
                        node_path = self.EmbyServer.Utils.translatePath("special://profile/library/music")
                        playlist_path = self.EmbyServer.Utils.translatePath("special://profile/playlists/music")
                    else:
                        node_path = self.EmbyServer.Utils.translatePath("special://profile/library/video")
                        playlist_path = self.EmbyServer.Utils.translatePath("special://profile/playlists/video")

                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):
                            temp_view = dict(view)
                            temp_view['Media'] = media
                            self.add_playlist(playlist_path, temp_view, True)
                            self.add_nodes(node_path, temp_view, True)

                        index += 1 # Compensate for the duplicate.
                    else:
                        if view['Media'] != 'music':
                            self.add_playlist(playlist_path, view, False)

                        self.add_nodes(node_path, view, False)

                    index += 1

        node_path = self.EmbyServer.Utils.translatePath("special://profile/library/video")
        playlist_path = self.EmbyServer.Utils.translatePath("special://profile/playlists/video")

        for single in [{'Name': self.EmbyServer.Utils.Translate('fav_movies'), 'Tag': "Favorite movies", 'Media': "movies"}, {'Name': self.EmbyServer.Utils.Translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'Media': "tvshows"}, {'Name': self.EmbyServer.Utils.Translate('fav_episodes'), 'Tag': "Favorite episodes", 'Media': "episodes"}]:
            self.add_single_node(node_path, index, "favorites", single)
            index += 1

        self.window_nodes()

    #Create or update the xps file
    def add_playlist(self, path, view, mixed):
        filepath = os.path.join(path, "emby%s%s.xsp" % (view['Media'], view['Id']))

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
    def add_nodes(self, path, view, mixed):
        folder = os.path.join(path, "emby%s%s" % (view['Media'], view['Id']))

        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdir(folder)

        self.node_index(folder, view, mixed)

        if view['Media'] == 'tvshows':
            self.node_tvshow(folder, view)
        else:
            self.node(folder, view)

    def add_single_node(self, path, index, item_type, view):
        filepath = os.path.join(path, "emby_%s.xml" % view['Tag'].replace(" ", ""))

        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
        except Exception:
            xmlData = self.node_root('folder' if item_type == 'favorites' and view['Media'] == 'episodes' else 'filter', index)
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

        if item_type == 'favorites' and view['Media'] == 'episodes':
            path = self.window_browse(view, 'FavEpisodes')
            self.node_favepisodes(xmlData, path)
        else:
            self.node_all(xmlData)

        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    #Create the root element
    def node_root(self, root, index):
        if root == 'main':
            element = xml.etree.ElementTree.Element('node', {'order': str(index)})
        elif root == 'filter':
            element = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "filter"})
        else:
            element = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "folder"})

        xml.etree.ElementTree.SubElement(element, 'icon').text = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"
        return element

    def node_index(self, folder, view, mixed):
        filepath = os.path.join(folder, "index.xml")
        index = self.EmbyServer.Utils.SyncData['SortedViews'].index(view['Id'])

        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
            xmlData.set('order', str(index))
        except Exception:
            xmlData = self.node_root('main', index)
            xml.etree.ElementTree.SubElement(xmlData, 'label')

        label = xmlData.find('label')
        label.text = view['Name'] if not mixed else "%s (%s)" % (view['Name'], self.EmbyServer.Utils.Translate(view['Media']))
        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    def node(self, folder, view):
        for node in self.NODES[view['Media']]:
            xml_name = node[0]
            xml_label = node[1] or view['Name']

            if node[0] == "alphabet":
                FolderPath = os.path.join(folder, "alphabet/")

                if view['Media'] == "music":
                    self.node_alphabet(FolderPath, view, "artist", "artists")
                else:
                    self.node_alphabet(FolderPath, view, "title", False)
            else:
                filepath = os.path.join(folder, "%s.xml" % xml_name)
                self.add_node(self.NODES[view['Media']].index(node), filepath, view, xml_name, xml_label)

    def node_alphabet(self, FolderPath, View, SortObject, Content):
        if not xbmcvfs.exists(FolderPath):
            xbmcvfs.mkdir(FolderPath)

        FileName = os.path.join(FolderPath, "index.xml")

        if xbmcvfs.exists(FileName):
            self.delete_node(FileName)

        xmlData = xml.etree.ElementTree.Element('node')
        xmlData.set('order', '0')
        xmlData.set('type', "folder")
        xmlLabel = xml.etree.ElementTree.SubElement(xmlData, "label").text = "Alphabet"
        xmlIcon = xml.etree.ElementTree.SubElement(xmlData, 'icon').text = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"
        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FileName)
        Counter = 1
        FileName = os.path.join(FolderPath, "0-9.xml")

        if xbmcvfs.exists(FileName):
            self.delete_node(FileName)

        xmlData = xml.etree.ElementTree.Element('node')
        xmlData.set('order', str(Counter))
        xmlData.set('type', "filter")
        xml.etree.ElementTree.SubElement(xmlData, "label").text = "0-9"
        xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

        if Content:
            xml.etree.ElementTree.SubElement(xmlData, "content").text = Content
        else:
            xml.etree.ElementTree.SubElement(xmlData, "content").text = View['Media']

        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
        xmlRule.text = View['Tag']
        xmlRule.set('field', "tag")
        xmlRule.set('operator', "is")
        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")

        if Content:
            xmlRule.set('field', SortObject)
        else:
            xmlRule.set('field', "title")

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
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("&")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("Ä")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("Ö")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("Ü")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("!")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("(")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(")")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("@")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("#")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("$")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("^")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("*")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("-")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("=")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("+")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("{")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("}")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("[")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("]")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("?")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(":")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(";")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("'")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(",")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(".")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("<")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode(">")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = self.EmbyServer.Utils.StringDecode("~")
        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FileName)
        FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

        for FileID in FileNames:
            Counter += 1
            FileName = os.path.join(FolderPath, "%s.xml" % FileID)

            if xbmcvfs.exists(FileName):
                self.delete_node(FileName)

            xmlData = xml.etree.ElementTree.Element('node')
            xmlData.set('order', str(Counter))
            xmlData.set('type', "filter")
            xml.etree.ElementTree.SubElement(xmlData, "label").text = FileID
            xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

            if Content:
                xml.etree.ElementTree.SubElement(xmlData, "content").text = Content
            else:
                xml.etree.ElementTree.SubElement(xmlData, "content").text = View['Media']

            xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
            xmlRule.text = View['Tag']
            xmlRule.set('field', "tag")
            xmlRule.set('operator', "is")
            xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
            xmlRule.text = FileID
            xmlRule.set('field', SortObject)
            xmlRule.set('operator', "startswith")
            self.EmbyServer.Utils.indent(xmlData, 0)
            self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), FileName)

    def node_tvshow(self, folder, view):
        for node in self.NODES[view['Media']]:
            xml_name = node[0]
            xml_label = node[1] or view['Name']
            xml_index = self.NODES[view['Media']].index(node)
            filepath = os.path.join(folder, "%s.xml" % xml_name)

            if xml_name == 'nextepisodes':
                path = self.window_nextepisodes(view)
                self.add_dynamic_node(xml_index, filepath, xml_name, xml_label, path)
            else:
                if xml_name == "alphabet":
                    FolderPath = os.path.join(folder, "alphabet/")
                    self.node_alphabet(FolderPath, view, "title", False)
                else:
                    self.add_node(xml_index, filepath, view, xml_name, xml_label)

    def add_node(self, index, filepath, view, node, name):
        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
        except Exception:
            xmlData = self.node_root('filter', index)
            xml.etree.ElementTree.SubElement(xmlData, 'label')
            xml.etree.ElementTree.SubElement(xmlData, 'match')
            xml.etree.ElementTree.SubElement(xmlData, 'content')

        label = xmlData.find('label')
        label.text = str(name) if isinstance(name, int) else name
        content = xmlData.find('content')

        if view['Media'] == "music":
            if node in ("years", "genres"):
                content.text = "artists"
            elif node in ("recentaddedalbums", "randomalbums"):
                content.text = "albums"
            elif node in ("recentaddedsongs", "randomsongs"):
                content.text = "songs"
            else:
                content.text = node
        else:
            content.text = view['Media']

        match = xmlData.find('match')
        match.text = "all"

        for rule in xmlData.findall('.//value'):
            if rule.text == view['Tag']:
                break
        else:
            rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

        getattr(self, 'node_' + node)(xmlData) # get node function based on node type
        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    def add_dynamic_node(self, index, filepath, node, name, path):
        try:
            xmlData = xml.etree.ElementTree.parse(filepath).getroot()
        except Exception:
            xmlData = self.node_root('folder', index)
            xml.etree.ElementTree.SubElement(xmlData, 'label')
            xml.etree.ElementTree.SubElement(xmlData, 'content')

        label = xmlData.find('label')
        label.text = name
        getattr(self, 'node_' + node)(xmlData, path)
        self.EmbyServer.Utils.indent(xmlData, 0)
        self.EmbyServer.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), filepath)

    def node_all(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    def node_recentplayed(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "lastplayed":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    def node_directors(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "sorttitle"

    def node_countries(self, root):
        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "sorttitle"

    def node_nextepisodes(self, root, path):
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

    def node_recent(self, root):
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

    def node_recentepisodes(self, root):
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

    #Returns a list of sorted media folders based on the Emby views.
    #Insert them in SortedViews and remove Views that are not in media folders
    def order_media_folders(self, folders):
        if not folders:
            return folders

        sorted_views = list(self.EmbyServer.Utils.SyncData['SortedViews'])
        unordered = [x[0] for x in folders]
        grouped = [x for x in unordered if x not in sorted_views]

        for library in grouped:
            sorted_views.append(library)

        sorted_folders = [x for x in sorted_views if x in unordered]
        return [folders[unordered.index(x)] for x in sorted_folders]

    #Just read from the database and populate based on SortedViews
    #Setup the window properties that reflect the emby server views and more
    def window_nodes(self):
        self.window_clear('Emby.nodes')
        self.window_clear('Emby.wnodes')

        with database.database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            libraries = database.emby_db.EmbyDatabase(embydb.cursor).get_views()

        libraries = self.order_media_folders(libraries or [])
        index = 0
        windex = 0

        try:
            self.media_folders = self.get_libraries()
        except IndexError as error:
            self.LOG.warning(error)

        for library in (libraries or []):
            view = {'Id': library[0], 'Name': library[1], 'Tag': library[1], 'Media': library[2]}
            if library[0] in [x.replace('Mixed:', "") for x in self.EmbyServer.Utils.SyncData['Whitelist']]: # Synced libraries
                if view['Media'] in ('movies', 'tvshows', 'musicvideos', 'mixed'):
                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):
                            for node in self.NODES[media]:
                                temp_view = dict(view)
                                temp_view['Media'] = media
                                temp_view['CleanName'] = view['Name']
                                temp_view['Name'] = "%s (%s)" % (view['Name'], self.EmbyServer.Utils.Translate(media))
                                self.window_node(index, temp_view, *node)
                                self.window_wnode(windex, temp_view, *node)

                            # Add one to compensate for the duplicate.
                            index += 1
                            windex += 1
                    else:
                        for node in self.NODES[view['Media']]:
                            self.window_node(index, view, *node)

                            if view['Media'] in ('movies', 'tvshows'):
                                self.window_wnode(windex, view, *node)

                        if view['Media'] in ('movies', 'tvshows'):
                            windex += 1

                elif view['Media'] == 'music':
                    self.window_node(index, view, 'music', None)
            else: # Dynamic entry
                if view['Media'] in ('homevideos', 'books', 'playlists'):
                    self.window_wnode(windex, view, 'browse', None)
                    windex += 1

                self.window_node(index, view, 'browse', None)

            index += 1

        for single in [{'Name': self.EmbyServer.Utils.Translate('fav_movies'), 'Tag': "Favorite movies", 'Media': "movies"}, {'Name': self.EmbyServer.Utils.Translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'Media': "tvshows"}, {'Name': self.EmbyServer.Utils.Translate('fav_episodes'), 'Tag': "Favorite episodes", 'Media': "episodes"}]:
            self.window_single_node(index, "favorites", single)
            index += 1

        self.EmbyServer.Utils.window('emby.nodes.total', str(index))

    #Leads to another listing of nodes
    def window_node(self, index, view, node, node_label):
        if view['Media'] in ('homevideos', 'photos'):
            path = self.window_browse(view, None if node in ('all', 'browse') else node)
        elif node == 'nextepisodes':
            path = self.window_nextepisodes(view)
        elif node == 'music':
            path = self.window_music()
        elif node == 'browse':
            path = self.window_browse(view, None)
        else:
            path = self.window_path(view, node)

        if node == 'music':
            window_path = "ActivateWindow(Music,%s,return)" % path
        elif node in ('browse', 'homevideos', 'photos'):
            window_path = path
        else:
            window_path = "ActivateWindow(Videos,%s,return)" % path

        node_label = self.EmbyServer.Utils.Translate(node_label) if isinstance(node_label, int) else node_label
        node_label = node_label or view['Name']

        if node in ('all', 'music'):
            window_prop = "Emby.nodes.%s" % index
            self.EmbyServer.Utils.window('%s.index' % window_prop, path.replace('all.xml', "")) # dir
            self.EmbyServer.Utils.window('%s.title' % window_prop, view['Name'].encode('utf-8'))
            self.EmbyServer.Utils.window('%s.content' % window_prop, path)
        elif node == 'browse':
            window_prop = "Emby.nodes.%s" % index
            self.EmbyServer.Utils.window('%s.title' % window_prop, view['Name'].encode('utf-8'))
        else:
            window_prop = "Emby.nodes.%s.%s" % (index, node)
            self.EmbyServer.Utils.window('%s.title' % window_prop, node_label.encode('utf-8'))
            self.EmbyServer.Utils.window('%s.content' % window_prop, path)

        self.EmbyServer.Utils.window('%s.id' % window_prop, view['Id'])
        self.EmbyServer.Utils.window('%s.path' % window_prop, window_path)
        self.EmbyServer.Utils.window('%s.type' % window_prop, view['Media'])
        self.window_artwork(window_prop, view['Id'])

    #Single destination node
    def window_single_node(self, index, item_type, view):
        path = "library://video/emby_%s.xml" % view['Tag'].replace(" ", "")
        window_path = "ActivateWindow(Videos,%s,return)" % path
        window_prop = "Emby.nodes.%s" % index
        self.EmbyServer.Utils.window('%s.title' % window_prop, view['Name'])
        self.EmbyServer.Utils.window('%s.path' % window_prop, window_path)
        self.EmbyServer.Utils.window('%s.content' % window_prop, path)
        self.EmbyServer.Utils.window('%s.type' % window_prop, item_type)

    #Similar to window_node, but does not contain music, musicvideos.
    #Contains books, audiobooks
    def window_wnode(self, index, view, node, node_label):
        if view['Media'] in ('homevideos', 'photos', 'books', 'playlists'):
            path = self.window_browse(view, None if node in ('all', 'browse') else node)
        else:
            path = self.window_path(view, node)

        if node in ('browse', 'homevideos', 'photos', 'books', 'playlists'):
            window_path = path
        else:
            window_path = "ActivateWindow(Videos,%s,return)" % path

        node_label = self.EmbyServer.Utils.Translate(node_label) if isinstance(node_label, int) else node_label
        node_label = node_label or view['Name']
        clean_title = view.get('CleanName', node_label)

        if node == 'all':
            window_prop = "Emby.wnodes.%s" % index
            self.EmbyServer.Utils.window('%s.index' % window_prop, path.replace('all.xml', "")) # dir
            self.EmbyServer.Utils.window('%s.title' % window_prop, view['Name'].encode('utf-8'))
            self.EmbyServer.Utils.window('%s.cleantitle' % window_prop, clean_title.encode('utf-8'))
            self.EmbyServer.Utils.window('%s.content' % window_prop, path)
        elif node == 'browse':
            window_prop = "Emby.wnodes.%s" % index
            self.EmbyServer.Utils.window('%s.title' % window_prop, view['Name'].encode('utf-8'))
            self.EmbyServer.Utils.window('%s.cleantitle' % window_prop, clean_title.encode('utf-8'))
            self.EmbyServer.Utils.window('%s.content' % window_prop, path)
        else:
            window_prop = "Emby.wnodes.%s.%s" % (index, node)
            self.EmbyServer.Utils.window('%s.title' % window_prop, node_label.encode('utf-8'))
            self.EmbyServer.Utils.window('%s.cleantitle' % window_prop, clean_title.encode('utf-8'))
            self.EmbyServer.Utils.window('%s.content' % window_prop, path)

        self.EmbyServer.Utils.window('%s.id' % window_prop, view['Id'])
        self.EmbyServer.Utils.window('%s.path' % window_prop, window_path)
        self.EmbyServer.Utils.window('%s.type' % window_prop, view['Media'])
        self.window_artwork(window_prop, view['Id'])
        self.LOG.debug("--[ wnode/%s/%s ] %s" % (index, self.EmbyServer.Utils.window('%s.title' % window_prop), self.EmbyServer.Utils.window('%s.artwork' % window_prop)))

    def window_artwork(self, prop, view_id):
        if not self.EmbyServer.logged_in:
            self.EmbyServer.Utils.window('%s.artwork' % prop, clear=True)
        elif self.EmbyServer.logged_in and self.media_folders:
            for library in self.media_folders:
                if library['Id'] == view_id and 'Primary' in library.get('ImageTags', {}):
                    artwork = self.APIHelper.get_artwork(view_id, 'Primary', None, None)
                    self.EmbyServer.Utils.window('%s.artwork' % prop, artwork)
                    break
            else:
                self.EmbyServer.Utils.window('%s.artwork' % prop, clear=True)

    def window_path(self, view, node):
        return "library://video/emby%s%s/%s.xml" % (view['Media'], view['Id'], node)

    def window_music(self):
        return "library://music/"

    def window_nextepisodes(self, view):
        params = {
            'id': view['Id'],
            'mode': "nextepisodes",
            'limit': self.limit
        }
        return "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))

    def window_browse(self, view, node):
        params = {
            'mode': "browse",
            'type': view['Media']
        }

        if view.get('Id'):
            params['id'] = view['Id']

        if node:
            params['folder'] = node

        return "%s?%s" % ("plugin://plugin.video.emby-next-gen/", urlencode(params))

    #Clearing window prop setup for Views
    def window_clear(self, name):
        total = int(self.EmbyServer.Utils.window(name + '.total') or 0)
        props = [
            "index", "id", "path", "artwork", "title", "cleantitle", "content", "type"
            "inprogress.content", "inprogress.title",
            "inprogress.content", "inprogress.path",
            "nextepisodes.title", "nextepisodes.content",
            "nextepisodes.path", "unwatched.title",
            "unwatched.content", "unwatched.path",
            "recent.title", "recent.content", "recent.path",
            "recentepisodes.title", "recentepisodes.content",
            "recentepisodes.path", "inprogressepisodes.title",
            "inprogressepisodes.content", "inprogressepisodes.path"
        ]

        for i in range(total):
            for prop in props:
                self.EmbyServer.Utils.window(name + '.%s.%s' % (str(i), prop), clear=True)

        for prop in props:
            self.EmbyServer.Utils.window(name + '.%s' % prop, clear=True)

    def delete_playlist(self, path):
        xbmcvfs.delete(path)
        self.LOG.info("DELETE playlist %s" % path)

    #Remove all emby playlists
    def delete_playlists(self):
        path = self.EmbyServer.Utils.translatePath("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)

        for filename in files:
            if filename.startswith('emby'):
                self.delete_playlist(os.path.join(path, filename))

    #Remove playlist based based on view_id
    def delete_playlist_by_id(self, view_id):
        path = self.EmbyServer.Utils.translatePath("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)

        for filename in files:
            if filename.startswith('emby') and filename.endswith('%s.xsp' % view_id):
                self.delete_playlist(os.path.join(path, filename))

    def delete_node(self, path):
        xbmcvfs.delete(path)
        self.LOG.info("DELETE node %s" % path)

    #Remove node and children files
    def delete_nodes(self):
        path = self.EmbyServer.Utils.translatePath("special://profile/library/video/")
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

    #Remove node and children files based on view_id
    def delete_node_by_id(self, view_id):
        path = self.EmbyServer.Utils.translatePath("special://profile/library/video/")
        dirs, files = xbmcvfs.listdir(path)

        for directory in dirs:
            if directory.startswith('emby') and directory.endswith(view_id):
                _, files = xbmcvfs.listdir(os.path.join(path, directory))

                for filename in files:
                    self.delete_node(os.path.join(path, directory, filename))

                xbmcvfs.rmdir(os.path.join(path, directory))

# -*- coding: utf-8 -*-
import xml.etree.ElementTree
import xbmcgui
from helper import loghandler
from helper import utils
from helper import xmls

if utils.Python3:
    from urllib.parse import urlencode
else:
    from urllib import urlencode

limit = 25
SyncNodes = {
    'tvshows': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultTVShows.png'),
        ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
        ('recentlyaddedepisodes', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png'),
        ('inprogress', utils.Translate(30171), 'DefaultInProgressShows.png'),
        ('inprogressepisodes', utils.Translate(30178), 'DefaultInProgressShows.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('unwatched', "Unwatched TV Shows", 'OverlayUnwatched.png'),
        ('unwatchedepisodes', "Unwatched Episodes", 'OverlayUnwatched.png'),
        ('studios', "Studios", 'DefaultStudios.png'),
        ('recentlyplayed', 'Recently played TV Show', 'DefaultMusicRecentlyPlayed.png'),
        ('recentlyplayedepisode', 'Recently played Episode', 'DefaultMusicRecentlyPlayed.png'),
        ('nextepisodes', utils.Translate(30179), 'DefaultInProgressShows.png')
    ],
    'movies': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMovies.png'),
        ('recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
        ('inprogress', utils.Translate(30177), 'DefaultInProgressShows.png'),
        ('unwatched', utils.Translate(30189), 'OverlayUnwatched.png'),
        ('sets', "Sets", 'DefaultSets.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('studios', "Studios", 'DefaultStudios.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('directors', 'Directors', 'DefaultDirector.png'),
        ('countries', 'Countries', 'DefaultCountry.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'musicvideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'homevideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'music': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultMusicGenres.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
    ],
    'audiobooks': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultMusicGenres.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ],
    'podcasts': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
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
LOG = loghandler.LOG('EMBY.emby.views')


class Views:
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.ViewItems = {}
        self.ViewsData = {}
        self.Nodes = []

    def update_nodes(self):
        self.Nodes = []

        for library_id, Data in list(self.ViewItems.items()):
            # remove forbidden charecter for file/folder names
            CleanName = utils.StringDecode(Data[0]).replace(" ", "_")
            CleanName = CleanName.replace("/", "_")
            CleanName = CleanName.replace("\\", "_")
            CleanName = CleanName.replace("<", "_")
            CleanName = CleanName.replace(">", "_")
            CleanName = CleanName.replace(":", "_")
            CleanName = CleanName.replace('"', "_")
            CleanName = CleanName.replace("|", "_")
            CleanName = CleanName.replace("?", "_")
            CleanName = CleanName.replace("*", "_")
            view = {'LibraryId': library_id, 'Name': utils.StringDecode(Data[0]), 'Tag': utils.StringDecode(Data[0]), 'MediaType': Data[1], "Icon": Data[2], 'NameClean': CleanName}

            if library_id in list(self.EmbyServer.library.Whitelist.keys()):
                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    view['Tag'] = "-%s;" % view['Tag']

                if view['MediaType'] == 'mixed':
                    ViewName = view['Name']

                    for media in ('movies', 'tvshows', 'music'):
                        view['MediaType'] = media

                        if media == 'music':
                            view['Tag'] = "-%s;" % view['Tag']

                        node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                        view['Name'] = "%s / %s" % (ViewName, view['MediaType'])
                        add_playlist(playlist_path, view)
                        add_nodes(node_path, view)
                        self.window_nodes(view, False)
                elif view['MediaType'] == 'homevideos':
                    self.window_nodes(view, True)  # Add dynamic node supporting photos
                    view['MediaType'] = "movies"
                    node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                    add_playlist(playlist_path, view)
                    add_nodes(node_path, view)
                    self.window_nodes(view, False)
                else:
                    node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                    add_playlist(playlist_path, view)
                    add_nodes(node_path, view)
                    self.window_nodes(view, False)
            else:
                self.window_nodes(view, True)

    def window_nodes(self, view, Dynamic):
        if not view['Icon']:
            if view['MediaType'] == 'tvshows':
                view['Icon'] = 'DefaultTVShows.png'
            elif view['MediaType'] in ('movies', 'homevideos'):
                view['Icon'] = 'DefaultMovies.png'
            elif view['MediaType'] == 'musicvideos':
                view['Icon'] = 'DefaultMusicVideos.png'
            elif view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                view['Icon'] = 'DefaultMusicVideos.png'
            else:
                view['Icon'] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        self.window_node(view, Dynamic)

    # Points to another listing of nodes
    def window_node(self, view, dynamic):
        NodeData = {}

        if dynamic:
            params = {
                'mode': "browse",
                'type': view['MediaType'],
                'name': view['Name'].encode('utf-8'),
                'server': self.EmbyServer.server_id
            }

            if view.get('LibraryId'):
                params['id'] = view['LibraryId']

            path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
            NodeData['title'] = "%s (%s)" % (view['Name'], self.EmbyServer.Name)
        else:
            if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                path = "library://music/emby_%s_%s/" % (view['MediaType'], view['NameClean'])
            else:
                path = "library://video/emby_%s_%s/" % (view['MediaType'], view['NameClean'])

            NodeData['title'] = view['Name']

        NodeData['path'] = path
        NodeData['id'] = view['LibraryId']
        NodeData['type'] = view['MediaType']
        NodeData['icon'] = view['Icon']
        self.Nodes.append(NodeData)

    def update_views(self):
        Data = self.EmbyServer.API.get_views()

        if 'Items' in Data:
            self.ViewsData = Data['Items']
        else:
            return

        Total = len(self.ViewsData)
        Counter = 1
        Progress = xbmcgui.DialogProgressBG()
        Progress.create("Emby", "Update views")

        for library in self.ViewsData:
            Percent = int(float(Counter) / float(Total) * 100)
            Counter += 1
            Progress.update(Percent, message="Update views")

            if library['Type'] == 'Channel' and library['Name'].lower() == "podcasts":
                library['MediaType'] = "podcasts"
            elif library['Type'] == 'Channel' or library['Name'].lower() == "local trailers" or library['Name'].lower() == "trailers":
                library['MediaType'] = "channels"
            else:
                library['MediaType'] = library.get('CollectionType', "mixed")

            if "Primary" in library["ImageTags"]:
                # Cache artwork
                request = {'type': "GET", 'url': "%s/emby/Items/%s/Images/Primary" % (self.EmbyServer.server, library['Id']), 'params': {}}
                Filename = utils.PathToFilenameReplaceSpecialCharecters("%s_%s" % (self.EmbyServer.Name, library['Id']))
                iconpath = "%s%s" % (utils.FolderEmbyTemp, Filename)

                if not utils.checkFileExists(iconpath):
                    iconpath = utils.download_file_from_Embyserver(request, Filename, self.EmbyServer)
            else:
                iconpath = ""

            self.ViewItems[library['Id']] = [library['Name'], library['MediaType'], iconpath]

        Progress.close()

    # Remove playlist based based on LibraryId
    def delete_playlist_by_id(self, LibraryId):
        if LibraryId in self.ViewItems:
            if self.ViewItems[LibraryId][1] in ('music', 'audiobooks', 'podcasts'):
                path = 'special://profile/playlists/music/'
            else:
                path = 'special://profile/playlists/video/'

            PlaylistPath = '%semby_%s.xsp' % (path, self.ViewItems[LibraryId][0].replace(" ", "_"))
            utils.delFolder(PlaylistPath)
        else:
            LOG.info("Delete playlist: library not found: %s" % LibraryId)

    def delete_node_by_id(self, LibraryId):
        if LibraryId in self.ViewItems:
            mediatypes = []

            if self.ViewItems[LibraryId][1].find('Mixed:') != -1:
                mediatypes.append('movies')
                mediatypes.append('tvshows')
            else:
                mediatypes.append(self.ViewItems[LibraryId][1])

            for mediatype in mediatypes:
                if mediatype in ('music', 'audiobooks', 'podcasts'):
                    path = "special://profile/library/music/"
                else:
                    path = "special://profile/library/video/"

                NodePath = '%semby_%s_%s/' % (path, mediatype, self.ViewItems[LibraryId][0].replace(" ", "_"))
                utils.delFolder(NodePath)
        else:
            LOG.info("Delete node: library not found: %s" % LibraryId)

def get_node_playlist_path(MediaType):
    if MediaType in ('music', 'audiobooks', 'podcasts'):
        node_path = "special://profile/library/music/"
        playlist_path = 'special://profile/playlists/music/'
    else:
        node_path = "special://profile/library/video/"
        playlist_path = 'special://profile/playlists/video/'

    return node_path, playlist_path

# Create or update the xsp file
def add_playlist(path, view):
    if not utils.xspplaylists:
        return

    filepath = "%s%s" % (path, "emby_%s_%s.xsp" % (view['MediaType'], view['NameClean']))
    xmlData = utils.readFileString(filepath)

    if xmlData:
        xmlData = xml.etree.ElementTree.fromstring(xmlData)
    else:
        xmlData = xml.etree.ElementTree.Element('smartplaylist', {'type': view['MediaType']})
        xml.etree.ElementTree.SubElement(xmlData, 'name')
        xml.etree.ElementTree.SubElement(xmlData, 'match')

    name = xmlData.find('name')
    name.text = view['Name']
    match = xmlData.find('match')
    match.text = "all"

    for rule in xmlData.findall('.//value'):
        if rule.text == view['Tag']:
            break
    else:
        rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

    xmls.WriteXmlFile(filepath, xmlData)

# Create or update the video node file
def add_nodes(path, view):
    folder = "%semby_%s_%s/" % (path, view['MediaType'], view['NameClean'])
    utils.mkDir(folder)
    filepath = "%s%s" % (folder, "index.xml")

    if not utils.checkFileExists(filepath):
        if view['MediaType'] == 'movies':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(Movies)"})
        elif view['MediaType'] == 'tvshows':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(TVShows)"})
        elif view['MediaType'] == 'musicvideos':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(MusicVideos)"})
        else:
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(Music)"})

        xml.etree.ElementTree.SubElement(xmlData, 'label').text = "EMBY: %s (%s)" % (view['Name'], view['MediaType'])

        if view['Icon']:
            Icon = view['Icon']
        else:
            if view['MediaType'] == 'tvshows':
                Icon = 'DefaultTVShows.png'
            elif view['MediaType'] == 'movies':
                Icon = 'DefaultMovies.png'
            elif view['MediaType'] == 'musicvideos':
                Icon = 'DefaultMusicVideos.png'
            elif view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                Icon = 'DefaultMusicVideos.png'
            else:
                Icon = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = Icon
        xmls.WriteXmlFile(filepath, xmlData)

    # specific nodes
    for node in SyncNodes[view['MediaType']]:
        if node[1]:
            xml_label = node[1]  # Specific
        else:
            xml_label = view['Name']  # All

        if node[0] == "letter":
            node_letter(view, folder, node)
        else:
            filepath = "%s%s.xml" % (folder, node[0])

            if not utils.checkFileExists(filepath):
                if node[0] == 'nextepisodes':
                    NodeType = 'folder'
                else:
                    NodeType = 'filter'

                xmlData = xml.etree.ElementTree.Element('node', {'order': str(SyncNodes[view['MediaType']].index(node)), 'type': NodeType})
                xml.etree.ElementTree.SubElement(xmlData, 'label').text = xml_label
                xml.etree.ElementTree.SubElement(xmlData, 'match').text = "all"
                xml.etree.ElementTree.SubElement(xmlData, 'content')
                xml.etree.ElementTree.SubElement(xmlData, 'icon').text = node[2]
                operator = "is"
                field = "tag"
                content = xmlData.find('content')

                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    if node[0] in ("genres", "artists"):
                        content.text = "artists"
                        operator = "contains"
                        field = "disambiguation"

                    elif node[0] in ("years", "recentlyaddedalbums", "randomalbums", "albums"):
                        content.text = "albums"
                        operator = "contains"
                        field = "type"

                    elif node[0] in ("recentlyaddedsongs", "randomsongs", "all", "recentlyplayed"):
                        content.text = "songs"
                        operator = "contains"
                        field = "comment"
                else:
                    if node[0] in ("recentlyaddedepisodes", "inprogressepisodes", "recentlyplayedepisode"):
                        content.text = "episodes"
                    else:
                        content.text = view['MediaType']

                for rule in xmlData.findall('.//value'):
                    if rule.text == view['Tag']:
                        break
                else:
                    rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': field, 'operator': operator})
                    xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

                if node[0] == 'nextepisodes':
                    node_nextepisodes(xmlData, view['Name'])
                else:
                    globals()['node_' + node[0]](xmlData)  # get node function based on node type

                xmls.WriteXmlFile(filepath, xmlData)

# Nodes
def node_letter(View, folder, node):
    Index = 1
    FolderPath = "%sletter/" % folder
    utils.mkDir(FolderPath)

    # index.xml
    FileName = "%s%s" % (FolderPath, "index.xml")

    if not utils.checkFileExists(FileName):
        if View['MediaType'] == 'movies':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(Movies)"})
        elif View['MediaType'] == 'tvshows':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(TVShows)"})
        elif View['MediaType'] == 'musicvideos':
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(MusicVideos)"})
        else:
            xmlData = xml.etree.ElementTree.Element('node', {'order': "0", 'visible': "Library.HasContent(Music)"})

        xmlData.set('type', "folder")
        xml.etree.ElementTree.SubElement(xmlData, "label").text = node[1]
        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = utils.translatePath(node[2])
        xmls.WriteXmlFile(FileName, xmlData)

    # 0-9.xml
    FileName = "%s%s" % (FolderPath, "0-9.xml")

    if not utils.checkFileExists(FileName):
        xmlData = xml.etree.ElementTree.Element('node')
        xmlData.set('order', str(Index))
        xmlData.set('type', "filter")
        xml.etree.ElementTree.SubElement(xmlData, "label").text = "0-9"
        xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts', 'musicvideos'):
            xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
        else:
            xml.etree.ElementTree.SubElement(xmlData, "content").text = View['MediaType']

        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
        xmlRule.text = View['Tag']

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
            xmlRule.set('field', "disambiguation")
            xmlRule.set('operator', "contains")
        else:
            xmlRule.set('field', "tag")
            xmlRule.set('operator', "is")

        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts', 'musicvideos'):
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
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("&")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("Ä")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("Ö")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("Ü")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("!")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("(")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(")")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("@")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("#")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("$")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("^")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("*")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("-")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("=")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("+")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("{")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("}")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("[")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("]")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("?")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(":")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(";")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("'")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(",")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(".")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("<")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode(">")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = utils.StringDecode("~")
        xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
        xmls.WriteXmlFile(FileName, xmlData)

        # Alphabetically
        FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

        for FileName in FileNames:
            Index += 1
            FilePath = "%s%s" % (FolderPath, "%s.xml" % FileName)

            if not utils.checkFileExists(FilePath):
                xmlData = xml.etree.ElementTree.Element('node')
                xmlData.set('order', str(Index))
                xmlData.set('type', "filter")
                xml.etree.ElementTree.SubElement(xmlData, "label").text = FileName
                xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts', 'musicvideos'):
                    xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
                else:
                    xml.etree.ElementTree.SubElement(xmlData, "content").text = View['MediaType']

                xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                xmlRule.text = View['Tag']

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    xmlRule.set('field', "disambiguation")
                    xmlRule.set('operator', "contains")
                else:
                    xmlRule.set('field', "tag")
                    xmlRule.set('operator', "is")

                xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                xmlRule.text = FileName

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts', 'musicvideos'):
                    xmlRule.set('field', "artist")
                else:
                    xmlRule.set('field', "sorttitle")

                xmlRule.set('operator', "startswith")
                xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
                xmls.WriteXmlFile(FilePath, xmlData)

def node_all(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

def node_recentlyplayed(root):
    for rule in root.findall('.//order'):
        if rule.text == "lastplayed":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

def node_directors(root):
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

def node_countries(root):
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

def node_nextepisodes(root, LibraryName):
    path = "plugin://%s/?%s" % (utils.PluginId, urlencode({'libraryname': LibraryName, 'mode': "nextepisodes", 'limit': 25}))

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

def node_years(root):
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

def node_actors(root):
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

def node_artists(root):
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

def node_albums(root):
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

def node_studios(root):
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

def node_resolutionsd(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "lessthan"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_resolutionhd(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_resolution4k(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "greaterthan"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_tags(root):
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

def node_recentlyadded(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

def node_inprogress(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'inprogress':
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_genres(root):
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

def node_unwatched(root):
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

def node_unwatchedepisodes(root):
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

def node_sets(root):
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

def node_random(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recommended(root):
    for rule in root.findall('.//order'):
        if rule.text == "rating":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "rating"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

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

def node_recentlyepisodes(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    content = root.find('content')
    content.text = "episodes"

def node_inprogressepisodes(root):
    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'inprogress':
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    content = root.find('content')
    content.text = "episodes"

def node_randomalbums(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_randomsongs(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedsongs(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedalbums(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedepisodes(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

def node_recentlyplayedepisode(root):
    for rule in root.findall('.//order'):
        if rule.text == "lastplayed":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

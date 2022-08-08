import xml.etree.ElementTree
from urllib.parse import urlencode
from helper import utils, xmls, loghandler

SyncNodes = {
    'tvshows': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultTVShows.png'),
        ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
        ('recentlyaddedepisodes', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png'),
        ('inprogress', utils.Translate(30171), 'DefaultInProgressShows.png'),
        ('inprogressepisodes', utils.Translate(30178), 'DefaultInProgressShows.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('unwatched', utils.Translate(33345), 'OverlayUnwatched.png'),
        ('unwatchedepisodes', utils.Translate(33344), 'OverlayUnwatched.png'),
        ('studios', utils.Translate(33249), 'DefaultStudios.png'),
        ('recentlyplayed', utils.Translate(33347), 'DefaultMusicRecentlyPlayed.png'),
        ('recentlyplayedepisodes', utils.Translate(33351), 'DefaultMusicRecentlyPlayed.png'),
        ('nextepisodes', utils.Translate(30179), 'DefaultInProgressShows.png')
    ],
    'movies': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMovies.png'),
        ('recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
        ('inprogress', utils.Translate(30177), 'DefaultInProgressShows.png'),
        ('unwatched', utils.Translate(30189), 'OverlayUnwatched.png'),
        ('sets', utils.Translate(30185), 'DefaultSets.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('studios', utils.Translate(33249), 'DefaultStudios.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('directors', utils.Translate(33352), 'DefaultDirector.png'),
        ('countries', utils.Translate(33358), 'DefaultCountry.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'musicvideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'homevideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'music': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('composers', utils.Translate(33426), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', utils.Translate(33390), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', utils.Translate(33392), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
    ],
    'audiobooks': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', utils.Translate(33389), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', utils.Translate(33393), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ],
    'podcasts': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', utils.Translate(33395), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', utils.Translate(33394), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ]
}
LOG = loghandler.LOG('EMBY.emby.views')


class Views:
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.ViewItems = {}
        self.LibraryOptions = {}
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}

    def update_nodes(self):
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}

        for library_id, Data in list(self.ViewItems.items()):
            # remove forbidden charecter for file/folder names
            CleanName = Data[0].replace(" ", "_")
            CleanName = CleanName.replace("/", "_")
            CleanName = CleanName.replace("\\", "_")
            CleanName = CleanName.replace("<", "_")
            CleanName = CleanName.replace(">", "_")
            CleanName = CleanName.replace(":", "_")
            CleanName = CleanName.replace('"', "_")
            CleanName = CleanName.replace("|", "_")
            CleanName = CleanName.replace("?", "_")
            CleanName = CleanName.replace("*", "_")
            view = {'LibraryId': library_id, 'Name': Data[0], 'Tag': Data[0], 'MediaType': Data[1], "Icon": Data[2], 'FileName': CleanName}
            self.window_nodes(view, True)  # dynamic Nodes

            if library_id in list(self.EmbyServer.library.Whitelist.keys()):  # synced nodes
                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    view['Tag'] = "%s-%s" % (library_id, view['Tag'])

                if view['MediaType'] == 'mixed':
                    ViewName = view['Name']

                    for media in ('movies', 'tvshows', 'music'):
                        view['MediaType'] = media

                        if media == 'music':
                            view['Tag'] = "%s-%s" % (library_id, view['Tag'])

                        node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                        view['Name'] = "%s / %s" % (ViewName, view['MediaType'])
                        add_playlist(playlist_path, view)
                        add_nodes(node_path, view)
                        self.window_nodes(view, False)
                elif view['MediaType'] == 'homevideos':
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

    # Dynamic nodes
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

        NodeData = {}

        if Dynamic:
            params = {
                'mode': "browse",
                'id': view['LibraryId'],
                'arg': view['MediaType'],
                'server': self.EmbyServer.server_id,
                'query': "NodesMenu"
            }
            path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
        else:
            if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                path = "library://music/emby_%s_%s/" % (view['MediaType'], view['FileName'])
            else:
                path = "library://video/emby_%s_%s/" % (view['MediaType'], view['FileName'])

        NodeData['title'] = view['Name']
        NodeData['path'] = path
        NodeData['id'] = view['LibraryId']
        NodeData['type'] = view['MediaType']
        NodeData['icon'] = view['Icon']

        if Dynamic:
            self.Nodes['NodesDynamic'].append(NodeData)
        else:
            self.Nodes['NodesSynced'].append(NodeData)

    def update_views(self):
        if utils.syncruntimelimits:
            Data = self.EmbyServer.API.get_libraries()

            if 'Items' in Data:
                Libraries = Data['Items']
            else:
                return

            for library in Libraries:
                self.LibraryOptions[library['ItemId']] = library['LibraryOptions']

        Data = self.EmbyServer.API.get_views()

        if 'Items' in Data:
            Libraries = Data['Items']
        else:
            return

        for library in Libraries:
            if library['Type'] == 'Channel' and library['Name'].lower() == "podcasts":
                library['MediaType'] = "podcasts"
            elif library['Type'] == 'Channel':
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

    # Remove playlist based on LibraryId
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

    filepath = "%s%s" % (path, "emby_%s_%s.xsp" % (view['MediaType'], view['FileName']))
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
    folder = "%semby_%s_%s/" % (path, view['MediaType'], view['FileName'])
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
                xml.etree.ElementTree.SubElement(xmlData, 'icon').text = node[2]
                content = xml.etree.ElementTree.SubElement(xmlData, 'content')

                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    if node[0] in ("genres", "artists", "composers"):
                        content.text = "artists"
                        operator = "is"
                        field = "disambiguation"
                    elif node[0] in ("years", "recentlyaddedalbums", "randomalbums", "albums"):
                        content.text = "albums"
                        operator = "is"
                        field = "type"
                    else:
                        content.text = "songs"
                        operator = "endswith"
                        field = "comment"
                else:
                    if "episodes" in node[0]:
                        content.text = "episodes"
                    else:
                        content.text = view['MediaType']

                    field = "tag"
                    operator = "is"

                xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': field, 'operator': operator}).text = view['Tag']

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
        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = utils.translatePath(node[2]).decode('utf-8')
        xmls.WriteXmlFile(FileName, xmlData)

    # 0-9.xml
    FileName = "%s%s" % (FolderPath, "0-9.xml")

    if not utils.checkFileExists(FileName):
        xmlData, xmlRule = set_letter_common("0-9", Index, View)
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
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "&"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "Ä"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "Ö"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "Ü"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "!"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "("
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = ")"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "@"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "#"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "$"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "^"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "*"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "-"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "="
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "+"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "{"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "}"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "["
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "]"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "?"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = ":"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = ";"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "'"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = ","
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "."
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "<"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = ">"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "~"
        xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
        xmls.WriteXmlFile(FileName, xmlData)

        # Alphabetically
        FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

        for FileName in FileNames:
            Index += 1
            FilePath = "%s%s" % (FolderPath, "%s.xml" % FileName)

            if not utils.checkFileExists(FilePath):
                xmlData, xmlRule = set_letter_common(FileName, Index, View)
                xmlRule.text = FileName
                xmls.WriteXmlFile(FilePath, xmlData)

def set_letter_common(Label, Index, View):
    xmlData = xml.etree.ElementTree.Element('node')
    xmlData.set('order', str(Index))
    xmlData.set('type', "filter")
    xml.etree.ElementTree.SubElement(xmlData, "label").text = Label
    xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

    if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
        xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
    elif View['MediaType'] == 'musicvideos':
        xml.etree.ElementTree.SubElement(xmlData, "content").text = "musicvideos"
    else:
        xml.etree.ElementTree.SubElement(xmlData, "content").text = View['MediaType']

    xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"

    if View['MediaType'] == 'musicvideos':
        xml.etree.ElementTree.SubElement(xmlData, 'group', {}).text = "artists"

    xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
    xmlRule.text = View['Tag']

    if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
        xmlRule.set('field', "disambiguation")
        xmlRule.set('operator', "is")
    else:
        xmlRule.set('field', "tag")
        xmlRule.set('operator', "is")

    xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")

    if View['MediaType'] in ('music', 'audiobooks', 'podcasts', 'musicvideos'):
        xmlRule.set('field', "artist")
    else:
        xmlRule.set('field', "sorttitle")

    xmlRule.set('operator', "startswith")
    return xmlData, xmlRule

def node_all(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'ascending'}).text = "sorttitle"

def node_directors(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "directors"
    xml.etree.ElementTree.SubElement(root, 'group').text = "directors"

def node_countries(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "countries"
    xml.etree.ElementTree.SubElement(root, 'group').text = "countries"

def node_nextepisodes(root, LibraryName):
    xml.etree.ElementTree.SubElement(root, 'path').text = "plugin://%s/?%s" % (utils.PluginId, urlencode({'libraryname': LibraryName, 'mode': "nextepisodes"}))

def node_years(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "title"
    xml.etree.ElementTree.SubElement(root, 'group').text = "years"

def node_actors(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "title"
    xml.etree.ElementTree.SubElement(root, 'group').text = "actors"

def node_artists(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "artists"
    xml.etree.ElementTree.SubElement(root, 'group').text = "artists"

def node_composers(root):
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "role", 'operator': "is"}).text = "composer"
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "artists"
    xml.etree.ElementTree.SubElement(root, 'group').text = "artists"

def node_albums(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "albums"
    xml.etree.ElementTree.SubElement(root, 'group').text = "albums"

def node_studios(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "title"
    xml.etree.ElementTree.SubElement(root, 'group').text = "studios"

def node_resolutionsd(root):
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "lessthan"}).text = "1080"

def node_resolutionhd(root):
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "is"}).text = "1080"

def node_resolution4k(root):
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "greaterthan"}).text = "1080"

def node_tags(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "title"
    xml.etree.ElementTree.SubElement(root, 'group').text = "tags"

def node_recentlyadded(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "dateadded"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_genres(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'ascending'}).text = "sorttitle"
    xml.etree.ElementTree.SubElement(root, 'group').text = "genres"

def node_sets(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'ascending'}).text = "sorttitle"
    xml.etree.ElementTree.SubElement(root, 'group').text = "sets"

def node_random(root):
    xml.etree.ElementTree.SubElement(root, 'order').text = "random"
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recommended(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "rating"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "rating", 'operator': "greaterthan"}).text = "7"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_unwatched(root):
    xml.etree.ElementTree.SubElement(root, 'order').text = "random"
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_unwatchedepisodes(root):
    xml.etree.ElementTree.SubElement(root, 'order').text = "random"
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_inprogress(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "lastplayed"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_inprogressepisodes(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "lastplayed"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recentlyplayed(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "lastplayed"
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "greaterthan"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recentlyplayedepisodes(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "lastplayed"
    xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "greaterthan"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recentlyaddedepisodes(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "dateadded"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"}).text = "0"
    xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "false"})
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_randomalbums(root):
    xml.etree.ElementTree.SubElement(root, 'order').text = "random"
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_randomsongs(root):
    xml.etree.ElementTree.SubElement(root, 'order').text = "random"
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recentlyaddedsongs(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "dateadded"
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

def node_recentlyaddedalbums(root):
    xml.etree.ElementTree.SubElement(root, 'order', {'direction': 'descending'}).text = "dateadded"
    xml.etree.ElementTree.SubElement(root, 'limit').text = utils.maxnodeitems

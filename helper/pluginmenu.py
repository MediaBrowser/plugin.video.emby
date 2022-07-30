import struct
from urllib.parse import urlencode, unquote
import unicodedata
from _thread import start_new_thread
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from database import dbio
from emby import listitem
from core import common
from . import xmls, utils, loghandler, playerops

LOG = loghandler.LOG('EMBY.helper.pluginmenu')
QueryCache = {}
MappingStaggered = {"MusicArtist": "MusicAlbum", "MusicAlbum": "Audio", "Series": "Season", "Season": "Episode", "BoxSet": "Everything", "PhotoAlbum": "Photo", "Letter": "LetterSub", "Tags": "TagsSub", "Genre": "GenreSub"}
letters = ["0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
MappingContentKodi = {"Video": "videos", "Season": "tvshows", "Episode": "episodes", "Series": "tvshows", "Movie": "movies", "Photo": "images", "PhotoAlbum": "images", "MusicVideo": "musicvideos", "MusicArtist": "artists", "MusicAlbum": "albums", "Audio": "songs", "Everything": "", "TvChannel": "videos", "Folder": "videos"}
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
PluginMenuActive = False
DYNNODES = {
    'tvshows': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Series"),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode"),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series"),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode"),
        ('Favorite', utils.Translate(33346), 'DefaultFavourites.png', "Series"),
        ('Favorite', utils.Translate(30182), 'DefaultFavourites.png', "Episode"),
        ('Tags', utils.Translate(33353), 'DefaultTags.png', "Series"),
        ('Tags', utils.Translate(33354), 'DefaultTags.png', "Episode"),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Series"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet"),
        ('Upcoming', utils.Translate(33348), 'DefaultSets.png', "Episode"),
        ('NextUp', utils.Translate(30179), 'DefaultSets.png', "Episode"),
        ('Resume', utils.Translate(33355), 'DefaultInProgressShows.png', "Episode"),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Series"),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Episode")
    ],
    'mixed': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Everything"),
        ('Everything', utils.Translate(33336), 'DefaultTVShows.png', "Everything"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Everything"),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series"),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode"),
        ('Inprogress', utils.Translate(33337), 'DefaultInProgressShows.png', "Everything"),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Everything"),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Series"),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Episode")
    ],
    'movies': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Movie"),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "Movie"),
        ('BoxSet', utils.Translate(20434), 'DefaultSets.png', "BoxSet"),
        ('Tags', utils.Translate(33356), 'DefaultTags.png', "Movie"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Movie"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Movie"),
        ('Resume', utils.Translate(33357), 'DefaultInProgressShows.png', "Movie"),
        ('Random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Movie")
    ],
    'channels': [
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder")
    ],
    'boxsets': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "BoxSet"),
        ('BoxSet', utils.Translate(30185), 'DefaultMovies.png', "Everything")
    ],
    'livetv': [
        ('TvChannel', "LiveTV", 'DefaultMovies.png', None)
    ],
    'musicvideos': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicVideo"),
        ('MusicVideo', utils.Translate(33363), 'DefaultMusicVideos.png', "MusicVideo"),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicVideos.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "MusicVideo"),
        ('Tags', utils.Translate(33364), 'DefaultTags.png', "MusicVideo"),
        ('Random', utils.Translate(33365), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "MusicVideo"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "MusicVideo"),
        ('Resume', utils.Translate(33366), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "MusicVideo")
    ],
    'homevideos': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "PhotoAlbum"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Video', utils.Translate(33367), 'DefaultAddonVideo.png', "Video"),
        ('Photo', utils.Translate(33368), 'DefaultAddonVideo.png', "Photo"),
        ('PhotoAlbum', utils.Translate(33369), 'DefaultAddonVideo.png', "PhotoAlbum"),
        ('Tags', utils.Translate(33370), 'DefaultTags.png', "PhotoAlbum"),
        ('Tags', utils.Translate(33371), 'DefaultTags.png', "Photo"),
        ('Tags', utils.Translate(33372), 'DefaultTags.png', "Video"),
        ('Recentlyadded', utils.Translate(33373), 'DefaultRecentlyAddedMovies.png', "Photo"),
        ('Recentlyadded', utils.Translate(33374), 'DefaultRecentlyAddedMovies.png', "PhotoAlbum"),
        ('Recentlyadded', utils.Translate(33375), 'DefaultRecentlyAddedMovies.png', "Video")
    ],
    'playlists': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Everything"),
        ('Playlist', utils.Translate(33376), 'DefaultPlaylist.png', "Everything"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder")
    ],
    'audiobooks': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultAddonMusic.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Audio', utils.Translate(33377), 'DefaultFolder.png', "Audio"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio"),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio"),
        ('Random', utils.Translate(33378), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio")
    ],
    'podcasts': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultAddonMusic.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Audio', utils.Translate(33382), 'DefaultFolder.png', "Audio"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio"),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio"),
        ('Random', utils.Translate(33381), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio")
    ],
    'music': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultAddonMusic.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Random', utils.Translate(33380), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio"),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio")
    ]
}

# Build plugin menu
def listing(Handle):
    ListItemData = []
    Handle = int(Handle)

    for server_id, EmbyServer in list(utils.EmbyServers.items()):
        add_ListItem(ListItemData, "%s (%s)" % (utils.Translate(33386), EmbyServer.Name), "plugin://%s/?mode=browse&query=NodesSynced&server=%s" % (utils.PluginId, server_id), True, utils.icon, utils.Translate(33383))
        add_ListItem(ListItemData, "%s (%s)" % (utils.Translate(33387), EmbyServer.Name), "plugin://%s/?mode=browse&query=NodesDynamic&server=%s" % (utils.PluginId, server_id), True, utils.icon, utils.Translate(33384))

    # Common Items
    add_ListItem(ListItemData, utils.Translate(30180), "library://video/emby_Favorite_movies.xml", True, utils.icon, "")
    add_ListItem(ListItemData, utils.Translate(30181), "library://video/emby_Favorite_tvshows.xml", True, utils.icon, "")
    add_ListItem(ListItemData, utils.Translate(33385), "library://video/emby_Favorite_musicvideos.xml", True, utils.icon, "")
    add_ListItem(ListItemData, utils.Translate(30182), "plugin://%s/?mode=favepisodes" % utils.PluginId, True, utils.icon, "")

    if utils.menuOptions:
        add_ListItem(ListItemData, utils.Translate(33194), "plugin://%s/?mode=managelibsselection" % utils.PluginId, False, utils.icon, utils.Translate(33309))
        add_ListItem(ListItemData, utils.Translate(33059), "plugin://%s/?mode=texturecache" % utils.PluginId, False, utils.icon, utils.Translate(33310))
        add_ListItem(ListItemData, utils.Translate(5), "plugin://%s/?mode=settings" % utils.PluginId, False, utils.icon, utils.Translate(33398))
        add_ListItem(ListItemData, utils.Translate(33058), "plugin://%s/?mode=databasereset" % utils.PluginId, False, utils.icon, utils.Translate(33313))
        add_ListItem(ListItemData, utils.Translate(33340), "plugin://%s/?mode=factoryreset" % utils.PluginId, False, utils.icon, utils.Translate(33400))
        add_ListItem(ListItemData, utils.Translate(33341), "plugin://%s/?mode=nodesreset" % utils.PluginId, False, utils.icon, utils.Translate(33401))
        add_ListItem(ListItemData, utils.Translate(33409), "plugin://%s/?mode=skinreload" % utils.PluginId, False, utils.icon, "")

    xbmcplugin.addDirectoryItems(Handle, ListItemData, len(ListItemData))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'files')
    xbmcplugin.endOfDirectory(Handle)

# Browse dynamically content
def browse(Handle, Id, query, args, server_id):
    LOG.info("Pluginmenu query: %s/%s/%s" % (Id, query, args))
    Handle = int(Handle)

    if server_id not in utils.EmbyServers:
        LOG.error("Pluginmenu invalid server id: %s" % server_id)
        return

    if query in ('NodesDynamic', 'NodesSynced'):
        ListItemData = []

        for Node in utils.EmbyServers[server_id].Views.Nodes[query]:
            label = Node['title']
            node = Node['type']
            LOG.debug("--[ Nodes/%s/%s ] %s" % (node, label, Node['path']))
            add_ListItem(ListItemData, label, Node['path'], True, Node['icon'], "No helptext yet")

        globals()["PluginMenuActive"] = True
        xbmcplugin.addDirectoryItems(Handle, ListItemData, len(ListItemData))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle)
        return

    # Workaround for wrong window query
    if PluginMenuActive:
        ReloadWindowId = 0
        WindowId = xbmcgui.getCurrentWindowId()
        CheckQuery = "%s%s" % (args, query)

        # check if video or music navigation window is open (MyVideoNav.xml MyMusicNav.xml) -> open MyPics.xml etc
        if CheckQuery.find("Photo") > -1 and WindowId in (10025, 10502):
            ReloadWindowId = 10002
        elif (CheckQuery.find("MusicAlbum") > -1 or CheckQuery.find("MusicArtist") > -1  or CheckQuery.find("Audio") > -1) and WindowId in (10025, 10002):
            ReloadWindowId = 10502
        elif WindowId in (10502, 10002) == 10002:
            ReloadWindowId = 10025

        if ReloadWindowId:
            globals()["PluginMenuActive"] = False
            LOG.info("Change of (browse) node content. Reload window: %s/%s/%s" % (CheckQuery, WindowId, ReloadWindowId))
            start_new_thread(ChangeContentWindow, ("plugin://%s/?id=%s&mode=browse&query=%s&server=%s&arg=%s" % (utils.PluginId, Id, query, server_id, args), ReloadWindowId))
            return

    ItemsListing = []
    args = args.split("_")
    Content = ""
    Unsorted = False
    QueryArgs = ()

    if query == 'NodesMenu':
        node = []
        globals()["PluginMenuActive"] = True

        for node in DYNNODES[args[0]]:
            ItemsListing.append({'Id': Id, 'Type': node[0], 'Overview': "No helptext yet2DYNANODE", 'NodesMenu': True, 'IsFolder': True, 'Name': node[1], 'artwork': node[2], 'args': node[3]})

        Content = node[3]
    elif query == 'Letter':
        for node in letters:
            ItemsListing.append({'Id': Id, 'Type': "Letter", 'Overview': "No helptext yet2LETTERSUB", 'IsFolder': True, 'Name': node, 'artwork': "", 'args': "%s_%s" % (args[0], node)})

        Content = args[0]
    elif query == 'LetterSub':
        if args[1] == "0-9":
            QueryArgs = (Id, [args[0]], False, True, {'NameLessThan': "A"}, True, False)
        else:
            QueryArgs = (Id, [args[0]], False, True, {'NameStartsWith': args[1]}, True, False)

        Content = args[0]
    elif query == 'Genre':
        Items = utils.EmbyServers[server_id].API.get_genres(Id, [args[0]])

        for Item in Items:
            ItemsListing.append({'Id': Id, 'Type': "Genre", 'IsFolder': True, 'Name': Item['Name'], 'artwork': None, 'args': "%s_%s" % (args[0], Item['Id'])})

        Content = args[0]
    elif query == 'GenreSub':
        QueryArgs = (Id, [args[0]], False, True, {'GenreIds': args[1]}, True, False)
        Content = args[0]
    elif query == 'Tags':
        Items = utils.EmbyServers[server_id].API.get_tags(Id, [args[0]])

        for Item in Items:
            ItemsListing.append({'Id': Id, 'Type': "Tags", 'IsFolder': True, 'Name': Item['Name'], 'artwork': None, 'args': "%s_%s" % (args[0], Item['Id'])})

        Content = args[0]
    elif query == 'TagsSub':
        QueryArgs = (Id, [args[0]], False, True, {'TagIds': args[1]}, True, False)
        Content = args[0]
    elif query == 'Recentlyadded':
        CacheId = "Recentlyadded_%s_%s_%s" % (server_id, Id, args[0])

        if CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListing = QueryCache[CacheId]
        else:
            ItemsListing = utils.EmbyServers[server_id].API.get_recently_added(Id, [args[0]])
            globals()["QueryCache"][CacheId] = ItemsListing

        Content = args[0]
    elif query == 'Unwatched':
        QueryArgs = (Id, [args[0]], False, True, {'filters': 'IsUnplayed', 'SortBy': "Random"}, True, False)
        Content = args[0]
        Unsorted = True
    elif query == 'Favorite':
        QueryArgs = (Id, [args[0]], False, True, {'filters': 'IsFavorite'}, True, False)
        Content = args[0]
    elif query == 'Inprogress':
        QueryArgs = (Id, [args[0]], False, True, {'filters': 'IsResumable'}, True, False)
        Content = args[0]
    elif query == 'BoxSet':
        QueryArgs = (Id, [args[0]], False, True, {}, True, False)
        Content = "Everything"
    elif query == 'TvChannel':
        CacheId = "TvChannel_%s" % server_id

        if CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListing = QueryCache[CacheId]
        else:
            ItemsListing = utils.EmbyServers[server_id].API.get_channels()
            globals()["QueryCache"][CacheId] = ItemsListing

        Content = "TvChannel"
    elif query in ("Playlist", "Default"):
        QueryArgs = (Id, ["Everything"], False, True, {}, True, False)
        Content = "Video"
        Unsorted = True
    elif query == "Video":
        QueryArgs = (Id, ["Video"], False, True, {}, True, False)
        Content = "Video"
    elif query in ("Mixed", "Everything"):
        QueryArgs = (Id, ["Movie", "Series", "MusicVideo", "Video", "MusicArtist"], False, True, {}, True, False)
        Content = "Everything"
    elif query == 'Random':
        QueryArgs = (Id, [args[0]], False, True, {'Limit': utils.maxnodeitems, 'SortBy': "Random"}, True, False)
        Content = args[0]
        Unsorted = True
    elif query == 'Upcoming':
        CacheId = "Upcoming_%s" % "Upcoming"

        if CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListing = QueryCache[CacheId]
        else:
            ItemsListing = utils.EmbyServers[server_id].API.get_upcoming(Id, ["Episode"])
            globals()["QueryCache"][CacheId] = ItemsListing

        Content = "Episode"
    elif query == 'NextUp':
        CacheId = "NextUp_%s_%s" % (server_id, Id)

        if CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListing = QueryCache[CacheId]
        else:
            ItemsListing = utils.EmbyServers[server_id].API.get_NextUp(Id, ["Episode"])
            globals()["QueryCache"][CacheId] = ItemsListing

        Content = "Episode"
    elif query == 'Resume':
        QueryArgs = (Id, [args[0]], False, True, {}, True, True)
        Content = args[0]
    elif query == 'Season':
        QueryArgs = (Id, ["Season"], False, True, {}, True, False)
        Content = "Season"
    elif query == 'Episode':
        QueryArgs = (Id, ["Episode"], False, True, {}, True, False)
        Content = "Episode"
    elif query == 'Series':
        QueryArgs = (Id, ["Series"], False, True, {}, True, False)
        Content = "Series"
    elif query == 'Photo':
        QueryArgs = (Id, ["Photo"], False, True, {}, True, False)
        Content = "Photo"
    elif query == 'PhotoAlbum':
        QueryArgs = (Id, ["PhotoAlbum"], False, True, {}, True, False)
        Content = "PhotoAlbum"
    elif query == "Folder":
        QueryArgs = (Id, ["Everything"], False, False, {}, True, False)
        Content = "Everything"
    elif query == 'MusicVideo':
        QueryArgs = (Id, ["MusicVideo"], False, True, {}, True, False)
        Content = "MusicVideo"
    elif query == 'MusicArtist':
        QueryArgs = (Id, ["MusicArtist"], False, True, {}, True, False)
        Content = "MusicArtist"
    elif query == 'Movie':
        QueryArgs = (Id, ["Movie"], False, True, {}, True, False)
        Content = "Movie"
    elif query == 'Audio':
        QueryArgs = (Id, ["Audio"], False, True, {}, True, False)
        Content = "Audio"
    elif query == 'MusicAlbum':
        CacheId = "MusicAlbum_%s_%s_%s" % (server_id, Id, args[0])

        if CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListing = QueryCache[CacheId]
        else:
            ItemsListing = utils.EmbyServers[server_id].API.browse_MusicByArtistId(Id, args[0], ["MusicAlbum"], True)
            Content = "MusicAlbum"

            # Append audio with no album information
            AudioItems = utils.EmbyServers[server_id].API.browse_MusicByArtistId(Id, args[0], ["Audio", "MusicVideo"], True)

            for AudioItem in AudioItems:
                if not 'AlbumId' in AudioItem:
                    ItemsListing.append(AudioItem)

            globals()["QueryCache"][CacheId] = ItemsListing

    ItemsListings = []

    if QueryArgs:
        CacheId = str(QueryArgs)

        if not Unsorted and CacheId in QueryCache:
            LOG.info("Using QueryCache: %s" % CacheId)
            ItemsListings = QueryCache[CacheId]
        else:
            for Item in utils.EmbyServers[server_id].API.get_Items(*QueryArgs):
                if utils.SystemShutdown:
                    return

                load_ListItem(Id, Item, server_id, ItemsListings)

            if not Unsorted:
                globals()["QueryCache"][CacheId] = ItemsListings
    else:
        for Item in ItemsListing:
            if utils.SystemShutdown:
                return

            load_ListItem(Id, Item, server_id, ItemsListings)

    xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))

    # Set Sorting
    if Unsorted:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)

    if query in ('Photo', 'PhotoAlbum'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
    elif query == 'Episode':
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_EPISODE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    elif query == 'Upcoming':
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_EPISODE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    else:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    if Content:
        xbmcplugin.setContent(Handle, MappingContentKodi[Content])

    xbmcplugin.endOfDirectory(Handle)

def remotepictures(Handle, playposition):
    Handle = int(Handle)
    list_li = []

    for Pictures in playerops.Pictures:
        list_li.append((Pictures[0], Pictures[1], False))
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Playlist.Add","params":{"playlistid":2,"item":{"file":"%s"}}}' % Pictures[0])

    xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
    xbmcplugin.setContent(Handle, "images")
    xbmcplugin.endOfDirectory(Handle)

    if playposition != "-1":
        xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":1,"method":"Player.Open","params":{"item":{"playlistid":2,"position":%s}}}' % playposition)

def SyncThemes(server_id):
    views = []

    if xbmc.getCondVisibility('System.HasAddon(service.tvtunes)'):
        try:
            tvtunes = xbmcaddon.Addon(id="service.tvtunes")
            tvtunes.setSetting('custom_path_enable', "true")
            tvtunes.setSetting('custom_path', utils.FolderAddonUserdataLibrary)
            LOG.info("TV Tunes custom path is enabled and set.")
        except:
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33152))
            return
    else:
        utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33152))
        return

    for LibraryID, LibraryInfo in list(utils.EmbyServers[server_id].Views.ViewItems.items()):
        if LibraryInfo[1] in ('movies', 'tvshows', 'mixed'):
            views.append(LibraryID)

    items = {}

    for ViewId in views:
        for item in utils.EmbyServers[server_id].API.get_Items(ViewId, ['Everything'], True, True, {'HasThemeVideo': "True"}, True, False):
            query = normalize_string(item['Name'])
            items[item['Id']] = query

        for item in utils.EmbyServers[server_id].API.get_Items(ViewId, ['Everything'], True, True, {'HasThemeSong': "True"}, True, False):
            query = normalize_string(item['Name'])
            items[item['Id']] = query

    for ItemId, name in list(items.items()):
        nfo_path = "%s%s/" % (utils.FolderAddonUserdataLibrary, name)
        nfo_file = "%s%s" % (nfo_path, "tvtunes.nfo")
        utils.mkDir(nfo_path)
        themes = utils.EmbyServers[server_id].API.get_themes(ItemId)
        paths = []

        for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
            if utils.useDirectPaths:
                paths.append(theme['MediaSources'][0]['Path'])
            else:
                paths.append(direct_url(server_id, theme))

        xmls.tvtunes_nfo(nfo_file, paths)

    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=5000, sound=False)

def SyncLiveTV(server_id):
    if xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)') and xbmc.getCondVisibility('System.AddonIsEnabled(pvr.iptvsimple)'):
        ChannelNames = {}

        # build m3u playlist
        channels = utils.EmbyServers[server_id].API.get_channels()

        if channels:
            playlist = "#EXTM3U\n"

            for item in channels:
                ChannelNames[item['Id']] = item['Name']

                if item['TagItems']:
                    Tag = item['TagItems'][0]['Name']
                else:
                    Tag = "--No Info--"

                ImageUrl = ""

                if item['ImageTags']:
                    if 'Primary' in item['ImageTags']:
                        ImageUrl = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item['Id'], item['ImageTags']['Primary'])

                StreamUrl = "http://127.0.0.1:57342/t-%s-%s-stream.ts" % (server_id, item['Id'])
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
            epgdata = utils.EmbyServers[server_id].API.get_channelprogram()

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

                    if len(temp2) > 1:
                        timestampStart += " +" + temp2[1].replace(":", "")

                    temp = item['EndDate'].split("T")
                    timestampEnd = temp[0].replace("-", "")
                    temp2 = temp[1].split(".")
                    timestampEnd += temp2[0].replace(":", "")[:6]
                    temp2 = temp2[1].split("+")

                    if len(temp2) > 1:
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

        utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33232))
    else:
        utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33233))

def direct_url(server_id, item):
    Filename = utils.PathToFilenameReplaceSpecialCharecters(item['Path'])

    if item['Type'] == 'Audio':
        return "http://127.0.0.1:57342/A-%s-%s-%s-%s" % (server_id, item['Id'], item['MediaSources'][0]['Id'], Filename)

    return "http://127.0.0.1:57342/V-%s-%s-%s-%s" % (server_id, item['Id'], item['MediaSources'][0]['Id'], Filename)

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

    result = utils.Dialog.select(utils.Translate(33061), [utils.Translate(33062), utils.Translate(33063)] if RemoveUserChoices else [utils.Translate(33062)])

    if result < 0:
        return

    if not result:  # Add user
        AddNameArray = []

        for AddUserChoice in AddUserChoices:
            AddNameArray.append(AddUserChoice['UserName'])

        resp = utils.Dialog.select(utils.Translate(33064), AddNameArray)

        if resp < 0:
            return

        UserData = AddUserChoices[resp]
        EmbyServer.add_AdditionalUser(UserData['UserId'])
        utils.Dialog.notification(heading=utils.addon_name, message="%s %s" % (utils.Translate(33067), UserData['UserName']), icon=utils.icon, time=1000, sound=False)
    else:  # Remove user
        RemoveNameArray = []

        for RemoveUserChoice in RemoveUserChoices:
            RemoveNameArray.append(RemoveUserChoice['UserName'])

        resp = utils.Dialog.select(utils.Translate(33064), RemoveNameArray)

        if resp < 0:
            return

        UserData = RemoveUserChoices[resp]
        EmbyServer.remove_AdditionalUser(UserData['UserId'])
        utils.Dialog.notification(heading=utils.addon_name, message="%s %s" % (utils.Translate(33066), UserData['UserName']), icon=utils.icon, time=1000, sound=False)

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
    text = unicodedata.normalize('NFKD', text)
    return text

def ChangeContentWindow(Query, WindowId):  # threaded
    if not utils.sleep(1):
        while xbmc.getCondVisibility("System.HasActiveModalDialog"):  # check if modal dialogs are closed
            if utils.sleep(1):
                return

        xbmc.executebuiltin('ActivateWindow(%s,"%s",return)' % (WindowId, Query))

def load_ListItem(Id, Item, server_id, list_li):
    li = listitem.set_ListItem(Item, server_id)

    if not Item.get('NodesMenu', False):
        if Item['Type'] in MappingStaggered:
            Item['Type'] = MappingStaggered[Item['Type']]
            Item['IsFolder'] = True

    if Item.get('IsFolder', False):
        params = {'id': Item['Id'], 'mode': "browse", 'query': Item['Type'], 'server': server_id, 'arg': Item.get('args', Id)}
        path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))
        list_li.append((path, li, True))
    else:
        path, _ = utils.get_path_type_from_item(server_id, Item)
        list_li.append((path, li, False))

#Menu structure nodes
def add_ListItem(ListItemData, label, path, isFolder, artwork, HelpText):
    li = xbmcgui.ListItem(label, path=path, offscreen=True)
    li.setInfo('video', {'title': label, 'plotoutline': HelpText})
    li.setProperties({'IsFolder': 'true', 'IsPlayable': 'false'})
    li.setArt({"thumb": artwork, "fanart": "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png", "icon": artwork})
    ListItemData.append((path, li, isFolder))

def get_EmbyServerList():
    ServerIds = []
    ServerItems = []

    for server_id, EmbyServer in list(utils.EmbyServers.items()):
        ServerIds.append(server_id)
        ServerItems.append(EmbyServer.Name)

    return len(utils.EmbyServers), ServerIds, ServerItems

def select_managelibs():  # threaded by monitor.py
    EmbyServersCounter, _, ServerItems = get_EmbyServerList()

    if EmbyServersCounter > 1:
        Selection = utils.Dialog.select(utils.Translate(33064), ServerItems)

        if Selection > -1:
            manage_libraries(Selection)
    else:
        if EmbyServersCounter > 0:
            manage_libraries(0)

def manage_libraries(ServerSelection):  # threaded by caller
    MenuItems = [utils.Translate(33098), utils.Translate(33154), utils.Translate(33140), utils.Translate(33184), utils.Translate(33139), utils.Translate(33060), utils.Translate(33234)]
    Selection = utils.Dialog.select(utils.Translate(33194), MenuItems)
    ServerIds = list(utils.EmbyServers)
    EmbyServerId = ServerIds[ServerSelection]

    if Selection == 0:
        utils.EmbyServers[EmbyServerId].library.refresh_boxsets()
    elif Selection == 1:
        utils.EmbyServers[EmbyServerId].library.select_libraries("AddLibrarySelection")
    elif Selection == 2:
        utils.EmbyServers[EmbyServerId].library.select_libraries("RepairLibrarySelection")
    elif Selection == 3:
        utils.EmbyServers[EmbyServerId].library.select_libraries("RemoveLibrarySelection")
    elif Selection == 4:
        utils.EmbyServers[EmbyServerId].library.select_libraries("UpdateLibrarySelection")
    elif Selection == 5:
        SyncThemes(EmbyServerId)
    elif Selection == 6:
        SyncLiveTV(EmbyServerId)

def select_adduser():
    EmbyServersCounter, ServerIds, ServerItems = get_EmbyServerList()

    if EmbyServersCounter > 1:
        Selection = utils.Dialog.select(utils.Translate(33054), ServerItems)

        if Selection > -1:
            AddUser(utils.EmbyServers[ServerIds[Selection]])
    else:
        if EmbyServersCounter > 0:
            AddUser(utils.EmbyServers[ServerIds[0]])

def favepisodes(Handle):
    Handle = int(Handle)
    list_li = []
    episodes_kodiId = []

    for server_id in utils.EmbyServers:
        embydb = dbio.DBOpenRO(server_id, "favepisodes")
        episodes_kodiId += embydb.get_episode_fav()
        dbio.DBCloseRO(server_id, "favepisodes")

    for episode_kodiId in episodes_kodiId:
        Details = utils.load_VideoitemFromKodiDB("episode", str(episode_kodiId[0]))
        FilePath = Details["file"]
        li = utils.CreateListitem("episode", Details)
        list_li.append((FilePath, li, False))

    xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle)

# This method will sync all Kodi artwork to textures13.db and cache them locally. This takes diskspace!
def cache_textures():
    LOG.info("<[ cache textures ]")

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33044)):
        DeleteThumbnails()

    # Select content to be cached
    choices = [utils.Translate(33121), "Movies", "TVShows", "Season", "Episode", "Musicvideos", "Album", "Single", "Song", "Boxsets", "Actor", "Artist", "Writer", "Director", "Gueststar", "Producer", "Bookmarks", "Photoalbum", "Photos"]
    selection = utils.Dialog.multiselect(utils.Translate(33256), choices)

    if not selection:
        return

    utils.set_settings_bool('artworkcacheenable', False)
    Urls = []

    if 0 in selection or 17 in selection or 18 in selection:
        for server_id, EmbyServer in list(utils.EmbyServers.items()):
            if 0 in selection or 17 in selection: # PhotoAlbum
                TotalRecords = EmbyServer.API.get_TotalRecordsRegular(None, "PhotoAlbum", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["PhotoAlbum"], True, True, {}, False, False):
                    path, _ = utils.get_path_type_from_item(server_id, Item)
                    TempUrls[ItemCounter] = (path,)
                    ItemCounter += 1

                Urls += TempUrls

            if 0 in selection or 18 in selection: # Photo
                TotalRecords = EmbyServer.API.get_TotalRecordsRegular(None, "Photo", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["Photo"], True, True, {}, False, False):
                    path, _ = utils.get_path_type_from_item(server_id, Item)
                    TempUrls[ItemCounter] = (path,)
                    ItemCounter += 1

                Urls += TempUrls

            TempUrls = []

    if 0 in selection or 1 in selection or 2 in selection or 3 in selection or 4 in selection or 5 in selection or 9 in selection or 10 in selection or 12 in selection or 13 in selection or 14 in selection or 15 in selection or 16 in selection:
        videodb = dbio.DBOpenRO("video", "cache_textures")

        if 0 in selection:
            Urls += videodb.get_bookmark_urls_all()
            Urls += videodb.common.get_artwork_urls_all()
        else:
            if 1 in selection:
                Urls += videodb.common.get_artwork_urls("movie")

            if 2 in selection:
                Urls += videodb.common.get_artwork_urls("tvshow")

            if 3 in selection:
                Urls += videodb.common.get_artwork_urls("season")

            if 4 in selection:
                Urls += videodb.common.get_artwork_urls("episode")

            if 5 in selection:
                Urls += videodb.common.get_artwork_urls("musicvideo")

            if 9 in selection:
                Urls += videodb.common.get_artwork_urls("set")

            if 10 in selection:
                Urls += videodb.common.get_artwork_urls("actor")

            if 12 in selection:
                Urls += videodb.common.get_artwork_urls("writer")

            if 13 in selection:
                Urls += videodb.common.get_artwork_urls("director")

            if 14 in selection:
                Urls += videodb.common.get_artwork_urls("gueststar")

            if 15 in selection:
                Urls += videodb.common.get_artwork_urls("producer")

            if 16 in selection:
                Urls += videodb.get_bookmark_urls_all()

        dbio.DBCloseRO("video", "cache_textures")

    if 0 in selection or 6 in selection or 7 in selection or 8 in selection or 11 in selection:
        musicdb = dbio.DBOpenRO("music", "cache_textures")

        if 0 in selection:
            Urls += musicdb.common.get_artwork_urls_all()
        else:
            if 6 in selection:
                Urls += musicdb.common.get_artwork_urls("album")

            if 7 in selection:
                Urls += musicdb.common.get_artwork_urls("single")

            if 8 in selection:
                Urls += musicdb.common.get_artwork_urls("song")

            if 11 in selection:
                Urls += musicdb.common.get_artwork_urls("artist")

        dbio.DBCloseRO("music", "cache_textures")

    Urls = list(dict.fromkeys(Urls)) # remove duplicates
    CacheAllEntries(Urls)
    utils.set_settings_bool('artworkcacheenable', True)

def get_image_metadata(ImageBinaryData, Hash):
    height = 0
    width = 0
    imageformat = ""
    ImageBinaryDataSize = len(ImageBinaryData)

    if ImageBinaryDataSize < 10:
        LOG.warning("Artwork cache: invalid image size: %s / %s" % (Hash, ImageBinaryDataSize))
        return width, height, imageformat

    # JPG
    if ImageBinaryData[0] == 0xFF and ImageBinaryData[1] == 0xD8 and ImageBinaryData[2] == 0xFF:
        imageformat = "jpg"
        i = 4
        BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]

        while i < ImageBinaryDataSize:
            i += BlockLength

            if i >= ImageBinaryDataSize or ImageBinaryData[i] != 0xFF:
                LOG.warning("Artwork cache: invalid jpg: %s" % Hash)
                break

            if ImageBinaryData[i + 1] >> 4 == 12: # 0xCX
                height = ImageBinaryData[i + 5] * 256 + ImageBinaryData[i + 6]
                width = ImageBinaryData[i + 7] * 256 + ImageBinaryData[i + 8]
                break

            i += 2
            BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]
    elif ImageBinaryData[0] == 0x89 and ImageBinaryData[1] == 0x50 and ImageBinaryData[2] == 0x4E and ImageBinaryData[3] == 0x47: # PNG
        imageformat = "png"
        width, height = struct.unpack('>ii', ImageBinaryData[16:24])
    else: # Not supported format
        LOG.warning("Artwork cache: invalid image format: %s" % Hash)

    LOG.debug("Artwork cache image data: %s / %s / %s" % (width, height, Hash))
    return width, height, imageformat

# Cache all entries
def CacheAllEntries(urls):
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    utils.progress_open(utils.Translate(33045))
    total = len(urls)
    KodiTime, UnixTime = utils.currenttime_kodi_format_and_unixtime()
    ArtworkCacheItems = 1000 * [{}]
    ArtworkCacheIndex = 0

    for IndexUrl, url in enumerate(urls):
        if IndexUrl % 1000 == 0:
            add_textures(ArtworkCacheItems, KodiTime)
            ArtworkCacheItems = 1000 * [{}]
            ArtworkCacheIndex = 0

            if utils.getFreeSpace(utils.FolderUserdataThumbnails) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message="Artwork cacheing stopped: running out of space", icon=utils.icon, time=5000, sound=True)
                LOG.warning("Artwork cache: running out of space")
                break
        else:
            ArtworkCacheIndex += 1

        if not url[0]:
            continue

        Temp = url[0][url[0].rfind("/") + 1:]
        Data = Temp.split("-")
        ServerId = Data[1]
        EmbyID = Data[2]
        ImageIndex = Data[3]
        ImageType = EmbyArtworkIDs[Data[4]]

        # Calculate hash -> crc32mpeg2
        crc = 0xffffffff

        for val in url[0].encode("utf-8"):
            crc ^= val << 24

            for _ in range(8):
                crc = crc << 1 if (crc & 0x80000000) == 0 else (crc << 1) ^ 0x104c11db7

        Hash = hex(crc).replace("0x", "")

        if utils.SystemShutdown:
            utils.progress_close()
            return

        TempPath = "%s%s/%s" % (utils.FolderUserdataThumbnails, Hash[0], Hash)

        if not utils.checkFileExists("%s.jpg" % TempPath) and not utils.checkFileExists("%s.png" % TempPath):
            if len(Data) > 6 and ImageType == "Chapter":
                OverlayText = unquote("-".join(Data[6:]))
                ImageTag = Data[5]
                ImageBinary = utils.image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText)
            else:
                ImageBinary = utils.EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex)

            Width, Height, ImageFormat = get_image_metadata(ImageBinary, Hash)
            cachedUrl = "%s/%s.%s" % (Hash[0], Hash, ImageFormat)
            utils.mkDir("%s%s" % (utils.FolderUserdataThumbnails, Hash[0]))
            Path = "%s%s" % (utils.FolderUserdataThumbnails, cachedUrl)

            if Width == 0:
                LOG.warning("Artwork cache: image not detected: %s" % url[0])
            else:
                utils.writeFileBinary(Path, ImageBinary)
                Size = len(ImageBinary)
                ArtworkCacheItems[ArtworkCacheIndex] = {'Url': url[0], 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': "d%ss%s" % (UnixTime, Size), 'Path': Path, 'cachedUrl': cachedUrl}

        Value = int((IndexUrl + 1) / total * 100)
        utils.progress_update(Value, "Emby", "%s: %s / %s" % (utils.Translate(33045), EmbyID, IndexUrl))

    add_textures(ArtworkCacheItems, KodiTime)
    ArtworkCacheItems = []
    utils.progress_close()

def add_textures(ArtworkCacheItems, KodiTime):
    texturedb = dbio.DBOpenRW("texture", "artwork_cache")

    for ArtworkCacheItem in ArtworkCacheItems:
        if ArtworkCacheItem:
            texturedb.add_texture(ArtworkCacheItem["Url"], ArtworkCacheItem["cachedUrl"], ArtworkCacheItem["ImageHash"], "1", ArtworkCacheItem["Width"], ArtworkCacheItem["Height"], KodiTime, )

    dbio.DBCloseRW("texture", "artwork_cache")

def reset_episodes_cache():
    UpdateCache = QueryCache.copy()

    for CacheItem in QueryCache:
        if CacheItem.startswith("next_episodes"):
            del UpdateCache[CacheItem]

    globals()["QueryCache"] = UpdateCache

def get_next_episodes(Handle, libraryname):
    Handle = int(Handle)
    CacheId = "next_episodes_%s" % libraryname

    if CacheId in QueryCache:
        LOG.info("Using QueryCache: %s" % CacheId)
        list_li = QueryCache[CacheId]
    else:
        videodb = dbio.DBOpenRO("video", "get_next_episodes")
        NextEpisodeInfos = videodb.get_next_episodesIds(common.MediaTags[libraryname])
        dbio.DBCloseRO("video", "get_next_episodes")
        list_li = []

        for NextEpisodeInfo in NextEpisodeInfos:
            EpisodeId = NextEpisodeInfo.split(";")
            episode = utils.load_VideoitemFromKodiDB("episode", EpisodeId[1])
            FilePath = episode["file"]
            li = utils.CreateListitem("episode", episode)
            list_li.append((FilePath, li, False))

        globals()["QueryCache"][CacheId] = list_li

    xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle)

# Factory reset. wipes all db records etc.
def factoryreset():
    LOG.warning("[ factory reset ]")
    utils.SystemShutdown = True
    utils.SyncPause = {}
    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33223), icon=utils.icon, time=960000, sound=True)
    DeleteArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33086))
    xbmc.executebuiltin('Dialog.Close(addoninformation)')

    if utils.sleep(5):  # Give Kodi time to complete startup before reset
        return

    # delete settings
    utils.delFolder(utils.FolderAddonUserdata)

    # delete database
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            utils.delFile("special://profile/Database/%s" % Filename)

    videodb = dbio.DBOpenRW("video", "setup")
    videodb.common.delete_tables("Video")
    dbio.DBCloseRW("video", "setup")
    musicdb = dbio.DBOpenRW("music", "setup")
    musicdb.common.delete_tables("Music")
    dbio.DBCloseRW("music", "setup")

    if DeleteArtwork:
        DeleteThumbnails()

    utils.delete_playlists()
    utils.delete_nodes()
    LOG.info("[ complete reset ]")
    xbmc.executebuiltin('RestartApp')

def nodesreset():
    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33342)):
        return

    utils.delete_nodes()

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.Views.update_nodes()

    xbmc.executebuiltin('RestartApp')

# Reset both the emby database and the kodi database.
def databasereset():
    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
        return

    LOG.info("[ database reset ]")
    utils.SystemShutdown = True
    utils.SyncPause = {}
    DeleteTextureCache = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33086))
    DeleteSettings = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33087))
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    videodb = dbio.DBOpenRW("video", "databasereset")
    videodb.common.delete_tables("Video")
    dbio.DBCloseRW("video", "databasereset")
    musicdb = dbio.DBOpenRW("music", "databasereset")
    musicdb.common.delete_tables("Music")
    dbio.DBCloseRW("music", "databasereset")

    if DeleteTextureCache:
        DeleteThumbnails()

    if DeleteSettings:
        LOG.info("[ reset settings ]")
        utils.set_settings("MinimumSetup", "")
        utils.delFolder(utils.FolderAddonUserdata)
    else:
        _, files = utils.listDir(utils.FolderAddonUserdata)

        for Filename in files:
            if Filename.startswith('sync_'):
                utils.delFile("%s%s" % (utils.FolderAddonUserdata, Filename))

    # Delete Kodi's emby database(s)
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            utils.delFile("%s%s" % ("special://profile/Database/", Filename))

    utils.delete_playlists()
    utils.delete_nodes()
    utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33088))
    xbmc.executebuiltin('RestartApp')

def reset_device_id():
    utils.device_id = ""
    utils.get_device_id(True)
    utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33033))
    xbmc.executebuiltin('RestartApp')

def DeleteThumbnails():
    LOG.info("-->[ reset artwork ]")
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    Folders, _ = utils.listDir('special://thumbnails/')
    utils.progress_open(utils.Translate(33412))
    TotalFolders = len(Folders)

    for CounterFolder, Folder in enumerate(Folders, 1):
        _, Files = utils.listDir('special://thumbnails/%s' % Folder)
        TotalFiles = len(Files)

        for CounterFile, File in enumerate(Files, 1):
            utils.progress_update(int(CounterFile / TotalFiles * 100), utils.Translate(33199), "%s: %s%s" % (utils.Translate(33412), Folder, File))
            LOG.debug("DELETE thumbnail %s" % File)
            utils.delFile('special://thumbnails/%s%s' % (Folder, File))

        utils.progress_update(int(CounterFolder / TotalFolders * 100), utils.Translate(33199), "%s: %s" % (utils.Translate(33412), Folder))

    texturedb = dbio.DBOpenRW("texture", "cache_textures")
    texturedb.common.delete_tables("Texture")
    dbio.DBCloseRW("texture", "cache_textures")
    utils.progress_close()
    LOG.info("--<[ reset artwork ]")

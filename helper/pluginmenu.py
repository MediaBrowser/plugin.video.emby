from urllib.parse import quote_plus, urlencode
import json
import unicodedata
from _thread import start_new_thread
import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from database import dbio
from emby import listitem
from . import xmls, utils, loghandler, playerops

LOG = loghandler.LOG('EMBY.helper.pluginmenu')
XbmcPlayer = xbmc.Player()
QueryCache = {}
ArtworkCacheIndex = 0
ThreadCounter = 0
MappingStaggered = {"MusicArtist": "MusicAlbum", "MusicAlbum": "Audio", "Series": "Season", "Season": "Episode", "BoxSet": "Everything", "PhotoAlbum": "Photo", "Letter": "LetterSub", "Tags": "TagsSub", "Genre": "GenreSub"}
letters = ["0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
MappingContentKodi = {"Video": "videos", "Season": "tvshows", "Episode": "episodes", "Series": "tvshows", "Movie": "movies", "Photo": "images", "PhotoAlbum": "images", "MusicVideo": "musicvideos", "MusicArtist": "artists", "MusicAlbum": "albums", "Audio": "songs", "Everything": "", "TvChannel": "videos", "Folder": "videos"}
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
        add_ListItem(ListItemData, utils.Translate(33194), "plugin://%s/?mode=managelibsselection"  % utils.PluginId, False, utils.icon, utils.Translate(33309))
        add_ListItem(ListItemData, utils.Translate(33059), "plugin://%s/?mode=texturecache"  % utils.PluginId, False, utils.icon, utils.Translate(33310))
        add_ListItem(ListItemData, utils.Translate(5), "plugin://%s/?mode=settings"  % utils.PluginId, False, utils.icon, utils.Translate(33398))
        add_ListItem(ListItemData, utils.Translate(33058), "plugin://%s/?mode=databasereset"  % utils.PluginId, False, utils.icon, utils.Translate(33313))
        add_ListItem(ListItemData, utils.Translate(33340), "plugin://%s/?mode=factoryreset"  % utils.PluginId, False, utils.icon, utils.Translate(33400))
        add_ListItem(ListItemData, utils.Translate(33341), "plugin://%s/?mode=nodesreset"  % utils.PluginId, False, utils.icon, utils.Translate(33401))

    xbmcplugin.addDirectoryItems(Handle, ListItemData, len(ListItemData))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'files')
    xbmcplugin.endOfDirectory(Handle)

# Browse dynamically content
def browse(Handle, Id, query, args, server_id):
    LOG.info("Pluginmenu query: %s/%s/%s" % (Id, query, args))
    Handle = int(Handle)

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
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33152))
            return
    else:
        utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33152))
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

    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=5000, sound=False)

def SyncLiveTV(server_id):
    if xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)') and xbmc.getCondVisibility('System.AddonIsEnabled(pvr.iptvsimple)'):
        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
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

        xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
        utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33232))
    else:
        utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33233))

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
        utils.dialog("notification", heading=utils.addon_name, message="%s %s" % (utils.Translate(33067), UserData['UserName']), icon=utils.icon, time=1000, sound=False)
    else:  # Remove user
        RemoveNameArray = []

        for RemoveUserChoice in RemoveUserChoices:
            RemoveNameArray.append(RemoveUserChoice['UserName'])

        resp = utils.dialog("select", utils.Translate(33064), RemoveNameArray)

        if resp < 0:
            return

        UserData = RemoveUserChoices[resp]
        EmbyServer.remove_AdditionalUser(UserData['UserId'])
        utils.dialog("notification", heading=utils.addon_name, message="%s %s" % (utils.Translate(33066), UserData['UserName']), icon=utils.icon, time=1000, sound=False)

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
    utils.waitForAbort(1)

    while xbmc.getCondVisibility("System.HasActiveModalDialog"):  # check if modal dialogs are closed
        utils.waitForAbort(1)

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
        Selection = utils.dialog("select", utils.Translate(33064), ServerItems)

        if Selection > -1:
            manage_libraries(Selection)
    else:
        if EmbyServersCounter > 0:
            manage_libraries(0)

def manage_libraries(ServerSelection):  # threaded by caller
    MenuItems = [utils.Translate(33098), utils.Translate(33154), utils.Translate(33140), utils.Translate(33184), utils.Translate(33139), utils.Translate(33060), utils.Translate(33234)]
    Selection = utils.dialog("select", utils.Translate(33194), MenuItems)
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
        Selection = utils.dialog("select", utils.Translate(33054), ServerItems)

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
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    xbmc.executebuiltin('activatewindow(home)')
    LOG.info("<[ cache textures ]")
    EnableWebserver = False
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserver"}}'))
    webServerEnabled = (result['result']['value'] or False)

    if not webServerEnabled:
        if not utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33227)):
            return

        EnableWebserver = True

    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverpassword"}}'))

    if not result['result']['value']:  # set password, cause mandatory in Kodi 19
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "services.webserverpassword", "value": "kodi"}}')
        webServerPass = 'kodi'
        utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33228))
    else:
        webServerPass = str(result['result']['value'])

    if EnableWebserver:
        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.SetSettingValue", "params": {"setting": "services.webserver", "value": True}}')
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserver"}}'))
        webServerEnabled = (result['result']['value'] or False)

    if not webServerEnabled:  # check if webserver is now enabled
        utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33103))
        return

    utils.set_settings_bool('artworkcacheenable', False)
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverport"}}'))
    webServerPort = str(result['result']['value'] or "")
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverusername"}}'))
    webServerUser = str(result['result']['value'] or "")
    result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Settings.GetSettingValue", "params": {"setting": "services.webserverssl"}}'))
    webServerSSL = (result['result']['value'] or False)

    if webServerSSL:
        webServerUrl = "https://127.0.0.1:%s" % webServerPort
    else:
        webServerUrl = "http://127.0.0.1:%s" % webServerPort

    if utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33044)):
        LOG.info("[ delete all thumbnails ]")

        if utils.checkFolderExists('special://thumbnails/'):
            dirs, _ = utils.listDir('special://thumbnails/')

            for directory in dirs:
                _, files = utils.listDir('special://thumbnails/%s' % directory)

                for Filename in files:
                    cached = 'special://thumbnails/%s%s' % (directory, Filename)
                    utils.delFile(cached)
                    LOG.debug("DELETE cached %s" % cached)

        texturedb = dbio.DBOpenRW("texture", "cache_textures")
        texturedb.common.delete_tables("Texture")
        dbio.DBCloseRW("texture", "cache_textures")

    # Select content to be cached
    choices = [utils.Translate(33121), utils.Translate(33257), utils.Translate(33258)]
    selection = utils.dialog("multi", utils.Translate(33256), choices)
    CacheMusic = False
    CacheVideo = False
    selection = selection[0]

    if selection == 0:
        CacheMusic = True
        CacheVideo = True
    elif selection == 1:
        CacheVideo = True
    elif selection == 2:
        CacheMusic = True

    if CacheVideo:
        videodb = dbio.DBOpenRO("video", "cache_textures")
        urls = videodb.common.get_artwork_urls()
        dbio.DBCloseRO("video", "cache_textures")
        CacheAllEntries(webServerUrl, urls, "video", webServerUser, webServerPass)

    if CacheMusic:
        musicdb = dbio.DBOpenRO("music", "cache_textures")
        urls = musicdb.common.get_artwork_urls()
        dbio.DBCloseRO("music", "cache_textures")
        CacheAllEntries(webServerUrl, urls, "music", webServerUser, webServerPass)

    utils.set_settings_bool('artworkcacheenable', True)

# Cache all entries
def CacheAllEntries(webServerUrl, urls, Label, webServerUser, webServerPass):
    utils.progress_open(utils.Translate(33045))
    total = len(urls)
    globals()["ThreadCounter"] = 0

    with requests.Session() as session:
        session.verify = False

        for url in urls:
            start_new_thread(worker_CacheAllEntries, (session, url, total, Label, webServerUrl, webServerUser, webServerPass))
            globals()["ThreadCounter"] += 1

            while ThreadCounter >= utils.artworkcachethreads:
                if utils.SystemShutdown:
                    return

                utils.waitForAbort(1)

def worker_CacheAllEntries(session, url, total, Label, webServerUrl, webServerUser, webServerPass):
    globals()["ArtworkCacheIndex"] += 1
    CloseProgressBar = bool(ArtworkCacheIndex == total)
    Value = int((float(float(ArtworkCacheIndex)) / float(total)) * 100)
    utils.progress_update(Value, "Emby", "%s: %s / %s" % (utils.Translate(33045), Label, ArtworkCacheIndex))

    if utils.SystemShutdown:
        utils.progress_close()
        return

    if url[0]:
        url = quote_plus(url[0])
        url = quote_plus(url)
        UrlSend = "%s/image/image://%s" % (webServerUrl, url)
        session.head(UrlSend, auth=(webServerUser, webServerPass))

    if CloseProgressBar:
        utils.progress_close()

    globals()["ThreadCounter"] -= 1

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
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShows", "params": {"sort": {"order": "descending", "method": "lastplayed"}, "filter": {"and": [{"operator": "true", "field": "inprogress", "value": ""}, {"operator": "is", "field": "tag", "value": "%s"}]}, "properties": ["title", "studio", "mpaa", "file", "art"]}}' % libraryname))
        items = result['result']['tvshows']
        list_li = []

        for item in items:
            result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %s, "sort": {"method": "episode"}, "filter": {"and": [{"operator": "lessthan", "field": "playcount", "value": "1"}, {"operator": "greaterthan", "field": "season", "value": "0"}]}, "properties": ["title", "playcount", "season", "episode", "showtitle", "plot", "file", "rating", "resume", "streamdetails", "firstaired", "writer", "dateadded", "lastplayed", "originaltitle", "seasonid", "specialsortepisode", "specialsortseason", "userrating", "votes", "cast", "art", "uniqueid"], "limits": {"end": 1}}}' % item['tvshowid']))

            if 'result' in result:
                if 'episodes' in result['result']:
                    episodes = result['result']['episodes']

                    for episode in episodes:
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
    utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33223), icon=utils.icon, time=960000, sound=True)
    DeleteArtwork = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33086))
    xbmc.executebuiltin('Dialog.Close(addonsettings)')
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    xbmc.executebuiltin('activatewindow(home)')
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')

    if utils.waitForAbort(5):  # Give Kodi time to complete startup before reset
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
        utils.DeleteThumbnails()
        texturedb = dbio.DBOpenRW("texture", "setup")
        texturedb.common.delete_tables("Texture")
        dbio.DBCloseRW("texture", "setup")

    utils.delete_playlists()
    utils.delete_nodes()
    LOG.info("[ complete reset ]")
    xbmc.executebuiltin('RestartApp')

def nodesreset():
    if not utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33342)):
        return

    utils.delete_nodes()

    for EmbyServer in list(utils.EmbyServers.values()):
        EmbyServer.Views.update_nodes()

    xbmc.executebuiltin('RestartApp')

# Reset both the emby database and the kodi database.
def databasereset():
    if not utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33074)):
        return

    LOG.warning("[ database reset ]")
    utils.SystemShutdown = True
    utils.SyncPause = {}
    DeleteTextureCache = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33086))
    DeleteSettings = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33087))
    xbmc.executebuiltin('Dialog.Close(addonsettings)')
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    xbmc.executebuiltin('activatewindow(home)')
    xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
    xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
    videodb = dbio.DBOpenRW("video", "databasereset")
    videodb.common.delete_tables("Video")
    dbio.DBCloseRW("video", "databasereset")
    musicdb = dbio.DBOpenRW("music", "databasereset")
    musicdb.common.delete_tables("Music")
    dbio.DBCloseRW("music", "databasereset")

    if DeleteTextureCache:
        utils.DeleteThumbnails()
        texturedb = dbio.DBOpenRW("texture", "databasereset")
        texturedb.common.delete_tables("Texture")
        dbio.DBCloseRW("texture", "databasereset")

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
    utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33088))
    xbmc.executebuiltin('RestartApp')

def reset_device_id():
    utils.device_id = ""
    utils.get_device_id(True)
    utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33033))
    xbmc.executebuiltin('RestartApp')

import struct
from urllib.parse import urlencode, unquote
import xbmc
import xbmcgui
import xbmcplugin
from database import dbio
from emby import listitem
from core import common
from . import utils, playerops

DynamicNodeServerId = ""
QueryCache = {}
MappingStaggered = {"MusicArtist": "MusicAlbum", "MusicAlbum": "Audio", "Series": "Season", "Season": "Episode", "BoxSet": "MixedContent", "PhotoAlbum": "Photo", "Letter": "LetterSub", "Tags": "TagsSub", "Genre": "GenreSub"}
letters = ("0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")
MappingContentKodi = {"Video": "videos", "Season": "tvshows", "Episode": "episodes", "Series": "tvshows", "Movie": "movies", "Photo": "images", "PhotoAlbum": "images", "MusicVideo": "musicvideos", "MusicArtist": "artists", "MusicAlbum": "albums", "Audio": "songs", "TvChannel": "videos", "BoxSet": "movies"}
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
PluginMenuActive = False
DynamicNodes = {
    'tvshows': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Series"),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyaddedseries', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png', "Series"),
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
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MixedContent"),
        ('MixedContent', utils.Translate(33336), 'DefaultTVShows.png', "MixedContent"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "MixedContent"),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series"),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode"),
        ('Inprogress', utils.Translate(33337), 'DefaultInProgressShows.png', "MixedContent"),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "MixedContent"),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Series"),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Episode")
    ],
    'movies': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Movie"),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Unwatched', utils.Translate(30189), 'OverlayUnwatched.png', "Movie"),
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
        ('BoxSet', utils.Translate(30185), 'DefaultMovies.png', "BoxSet"),
        ('Favorite', "Favorite boxsets", 'DefaultFavourites.png', "BoxSet"),
    ],
    'livetv': [
        ('TvChannel', "LiveTV", 'DefaultMovies.png', None)
    ],
    'musicvideos': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicVideo"),
        ('MusicVideo', utils.Translate(33363), 'DefaultMusicVideos.png', "MusicVideo"),
        ('MusicVideoArtist', utils.Translate(33343), 'DefaultMusicVideos.png', "MusicVideoArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "MusicVideo"),
        ('Tags', utils.Translate(33364), 'DefaultTags.png', "MusicVideo"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet"),
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
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet"),
        ('Recentlyadded', utils.Translate(33373), 'DefaultRecentlyAddedMovies.png', "Photo"),
        ('Recentlyadded', utils.Translate(33375), 'DefaultRecentlyAddedMovies.png', "Video")
    ],
    'playlists': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Playlists"),
        ('Playlists', utils.Translate(33376), 'DefaultPlaylist.png', "Playlist")
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

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        add_ListItem(ListItemData, f"{utils.Translate(33386)} ({EmbyServer.ServerData['ServerName']})", f"plugin://{utils.PluginId}/?mode=browse&query=NodesSynced&server={ServerId}", True, utils.icon, utils.Translate(33383))
        add_ListItem(ListItemData, f"{utils.Translate(33387)} ({EmbyServer.ServerData['ServerName']})", f"plugin://{utils.PluginId}/?mode=browse&query=NodesDynamic&server={ServerId}", True, utils.icon, utils.Translate(33384))

    # Common Items
    if utils.menuOptions:
        add_ListItem(ListItemData, utils.Translate(33194), f"plugin://{utils.PluginId}/?mode=managelibsselection", False, utils.icon, utils.Translate(33309))
        add_ListItem(ListItemData, utils.Translate(33059), f"plugin://{utils.PluginId}/?mode=texturecache", False, utils.icon, utils.Translate(33310))
        add_ListItem(ListItemData, utils.Translate(5), f"plugin://{utils.PluginId}/?mode=settings", False, utils.icon, utils.Translate(33398))
        add_ListItem(ListItemData, utils.Translate(33058), f"plugin://{utils.PluginId}/?mode=databasereset", False, utils.icon, utils.Translate(33313))
        add_ListItem(ListItemData, utils.Translate(33340), f"plugin://{utils.PluginId}/?mode=factoryreset", False, utils.icon, utils.Translate(33400))
        add_ListItem(ListItemData, utils.Translate(33341), f"plugin://{utils.PluginId}/?mode=nodesreset", False, utils.icon, utils.Translate(33401))
        add_ListItem(ListItemData, utils.Translate(33409), f"plugin://{utils.PluginId}/?mode=skinreload", False, utils.icon, "")

    xbmcplugin.addDirectoryItems(Handle, ListItemData, len(ListItemData))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'files')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Browse dynamically content
def browse(Handle, Id, query, args, ServerId):
    xbmc.log(f"EMBY.helper.pluginmenu: Pluginmenu query: {Id} / {query} / {args}", 1) # LOGINFO
    Handle = int(Handle)

    if ServerId not in utils.EmbyServers:
        xbmc.log(f"EMBY.helper.pluginmenu: Pluginmenu invalid server id: {ServerId}", 3) # LOGERROR
        return

    if query in ('NodesDynamic', 'NodesSynced'):
        ListItemData = []

        for Node in utils.EmbyServers[ServerId].Views.Nodes[query]:
            label = Node['title']
            node = Node['type']
            xbmc.log(f"EMBY.helper.pluginmenu: --[ Nodes / {node} / {label} ] {Node['path']}", 0) # LOGDEBUG
            add_ListItem(ListItemData, label, Node['path'], True, Node['icon'], "")

        if query == 'NodesSynced':
            add_ListItem(ListItemData, utils.Translate(30180), "library://video/emby_Favorite_movies.xml", True, utils.icon, "")
            add_ListItem(ListItemData, utils.Translate(30181), "library://video/emby_Favorite_tvshows.xml", True, utils.icon, "")
            add_ListItem(ListItemData, utils.Translate(33385), "library://video/emby_Favorite_musicvideos.xml", True, utils.icon, "")
            add_ListItem(ListItemData, utils.Translate(30182), f"plugin://{utils.PluginId}/?mode=favepisodes", True, utils.icon, "")
        else:
            add_ListItem(ListItemData, "Favorites", f"plugin://{utils.PluginId}/?mode=browse&query=Favorite&server={ServerId}&arg=MixedContent", True, utils.icon, "")

        globals()["PluginMenuActive"] = True
        xbmcplugin.addDirectoryItems(Handle, ListItemData, len(ListItemData))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.setContent(Handle, 'files')
        xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)
        return

    # Workaround for wrong window query
    if PluginMenuActive:
        ReloadWindowId = ""
        WindowId = xbmcgui.getCurrentWindowId()
        CheckQuery = f"{args}{query}"

        # check if video or music navigation window is open (MyVideoNav.xml MyMusicNav.xml) -> open MyPics.xml etc 10502 = music, 10025 = videos, 10002 = pictures
        if CheckQuery.find("Photo") > -1 and WindowId in (10025, 10502):
            ReloadWindowId = "pictures"
        elif (CheckQuery.find("MusicAlbum") > -1 or CheckQuery.find("MusicArtist") > -1  or CheckQuery.find("Audio") > -1) and WindowId in (10025, 10002):
            ReloadWindowId = "music"
        elif WindowId in (10502, 10002) == 10002:
            ReloadWindowId = "videos"

        if ReloadWindowId:
            globals()["PluginMenuActive"] = False
            xbmc.log(f"EMBY.helper.pluginmenu: Change of (browse) node content. Reload window: {CheckQuery} / {WindowId} / {ReloadWindowId}", 1) # LOGINFO
            xbmcplugin.endOfDirectory(Handle, succeeded=False, cacheToDisc=False)
            utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "{ReloadWindowId}", "parameters": ["plugin://{utils.PluginId}/?id={Id}&mode=browse&query={query}&server={ServerId}&arg={args}", "return"]}}}}')
            return

    ItemsListings = []
    args = args.split("_")
    Content = ""
    Unsorted = False
    Cache = True
    QueryArgs = ()

    # Staggered: Map content types (customized queries -> not an Emby Type)
    if args[0] == "MixedContent":
        QueryContent = ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video"]
    elif args[0] == "Playlists":
        QueryContent = ["Playlist"]
    else:
        QueryContent = [args[0]]

    if query == 'NodesMenu':
        node = []
        globals()["PluginMenuActive"] = True

        for node in DynamicNodes[args[0]]:
            load_ListItem(Id, {'Id': Id, 'Type': node[0], 'Overview': utils.Translate(33387), 'NodesMenu': True, 'IsFolder': True, 'Name': node[1], 'artwork': node[2], 'args': node[3]}, ServerId, ItemsListings)

        Content = node[3]
    elif query == 'Letter':
        CacheId = f"Letter_{ServerId}_{Id}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for node in letters:
                load_ListItem(Id, {'Id': Id, 'Type': "Letter", 'Overview': utils.Translate(33387), 'IsFolder': True, 'Name': node, 'artwork': "", 'args': f"{args[0]}_{node}"}, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Content = args[0]
    elif query == 'LetterSub':
        if args[1] == "0-9":
            QueryArgs = (Id, QueryContent, False, True, {'NameLessThan': "A"}, False)
        else:
            QueryArgs = (Id, QueryContent, False, True, {'NameStartsWith': args[1]}, False)

        Content = args[0]
    elif query == 'Genre':
        CacheId = f"Genre_{ServerId}_{Id}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            Items = utils.EmbyServers[ServerId].API.get_genres(Id, args[0])

            for Item in Items:
                load_ListItem(Id, {'Id': Id, 'Type': "Genre", 'IsFolder': True, 'Name': Item['Name'], 'artwork': None, 'args': f"{args[0]}_{Item['Id']}"}, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Content = args[0]
    elif query == 'GenreSub':
        QueryArgs = (Id, QueryContent, False, True, {'GenreIds': args[1]}, False)
        Content = args[0]
    elif query == 'Tags':
        CacheId = f"Tags_{ServerId}_{Id}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            Items = utils.EmbyServers[ServerId].API.get_tags(Id, args[0])

            for Item in Items:
                load_ListItem(Id, {'Id': Id, 'Type': "Tags", 'IsFolder': True, 'Name': Item['Name'], 'artwork': None, 'args': f"{args[0]}_{Item['Id']}"}, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Content = args[0]
    elif query == 'TagsSub':
        QueryArgs = (Id, QueryContent, False, True, {'TagIds': args[1]}, False)
        Content = args[0]
    elif query == 'Recentlyadded':
        QueryArgs = (Id, QueryContent, False, True, {'Limit': utils.maxnodeitems, "GroupItems": "False"}, False, True)
        Content = args[0]
        Unsorted = True
    elif query == 'Recentlyaddedseries':
        QueryArgs = (Id, ["Episode"], False, True, {'Limit': utils.maxnodeitems}, False, True)
        Content = args[0]
        Unsorted = True
    elif query == 'Unwatched':
        QueryArgs = (Id, QueryContent, False, True, {'filters': 'IsUnplayed', 'SortBy': "Random", 'Limit': utils.maxnodeitems}, False)
        Content = args[0]
    elif query == 'Favorite':
        QueryArgs = (Id, QueryContent, False, True, {'filters': 'IsFavorite'}, False)
        Content = args[0]
    elif query == 'Inprogress':
        QueryArgs = (Id, QueryContent, False, True, {'filters': 'IsResumable'}, False)
        Content = args[0]
    elif query == 'BoxSet':
        QueryArgs = (Id, ['BoxSet'], False, True, {}, False, False, True)
        Content = "BoxSet"
    elif query == 'TvChannel':
        CacheId = f"TvChannel_{ServerId}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for Item in utils.EmbyServers[ServerId].API.get_channels():
                load_ListItem(Id, Item, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Content = "TvChannel"
    elif query == "Playlist":
        QueryArgs = (Id, ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video"], False, True, {}, False)
        Content = "Video"
        Unsorted = True
    elif query == "Playlists":
        QueryArgs = (Id, ["Playlist"], False, True, {}, False, False, False, True)
        Content = "Video"
    elif query == "Video":
        QueryArgs = (Id, ["Video"], False, True, {}, False)
        Content = "Video"
    elif query == "MixedContent":
        QueryArgs = (Id, ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video"], False, True, {}, False)
    elif query == 'Random':
        QueryArgs = (Id, QueryContent, False, True, {'Limit': utils.maxnodeitems, 'SortBy': "Random"}, False)
        Content = args[0]
        Unsorted = True
        Cache = False
    elif query == 'Upcoming':
        CacheId = "Upcoming_Upcoming"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for Item in utils.EmbyServers[ServerId].API.get_upcoming(Id):
                load_ListItem(Id, Item, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Content = "Episode"
    elif query == 'NextUp':
        CacheId = f"NextUp_{ServerId}_{Id}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for Item in utils.EmbyServers[ServerId].API.get_NextUp(Id):
                load_ListItem(Id, Item, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

        Unsorted = True
        Content = "Episode"
    elif query == 'Resume':
        QueryArgs = (Id, QueryContent, False, True, {}, True)
        Content = args[0]
    elif query == 'Season':
        QueryArgs = (Id, ["Season"], False, True, {}, False)
        Content = "Season"
    elif query == 'Episode':
        QueryArgs = (Id, ["Episode"], False, True, {}, False)
        Content = "Episode"
    elif query == 'Series':
        QueryArgs = (Id, ["Series"], False, True, {}, False)
        Content = "Series"
    elif query == 'Photo':
        QueryArgs = (Id, ["Photo"], False, True, {}, False)
        Content = "Photo"
    elif query == 'PhotoAlbum':
        QueryArgs = (Id, ["PhotoAlbum"], False, True, {}, False)
        Content = "PhotoAlbum"
    elif query == "Folder":
        QueryArgs = (Id, ["Folder", "Episode", "Movie", "MusicVideo", "BoxSet", "MusicAlbum", "MusicArtist", "Season", "Series", "Audio", "Video", "Trailer", "Photo", "PhotoAlbum"], False, False, {}, False, False, False, True)
    elif query == 'MusicVideo':
        QueryArgs = (Id, ["MusicVideo"], False, True, {}, False)
        Content = "MusicVideo"
    elif query == 'MusicArtist':
        QueryArgs = (Id, ["MusicArtist"], False, True, {}, False)
        Content = "MusicArtist"
    elif query == 'MusicVideoArtist':
        QueryArgs = (Id, ["MusicArtist"], False, True, {}, False, False, True)
        Content = "MusicArtist"
    elif query == 'Movie':
        QueryArgs = (Id, ["Movie"], False, True, {}, False)
        Content = "Movie"
    elif query == 'Audio':
        QueryArgs = (Id, ["Audio"], False, True, {}, False)
        Content = "Audio"
    elif query == 'MusicAlbum':
        CacheId = f"MusicAlbum_{ServerId}_{Id}_{args[0]}"

        if CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for Item in utils.EmbyServers[ServerId].API.browse_MusicByArtistId(Id, args[0], ["MusicAlbum"], True):
                load_ListItem(Id, Item, ServerId, ItemsListings)

            Content = "MusicAlbum"

            # Append audio with no album information
            for Item in utils.EmbyServers[ServerId].API.browse_MusicByArtistId(Id, args[0], ["Audio", "MusicVideo"], True):
                if not 'AlbumId' in Item:
                    load_ListItem(Id, Item, ServerId, ItemsListings)

            globals()["QueryCache"][CacheId] = [True, ItemsListings]

    if QueryArgs:
        CacheId = str(QueryArgs)

        if Cache and CacheId in QueryCache and QueryCache[CacheId][0]:
            xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
            ItemsListings = QueryCache[CacheId][1]
        else:
            for Item in utils.EmbyServers[ServerId].API.get_Items_dynamic(*QueryArgs):
                if utils.SystemShutdown:
                    return

                load_ListItem(Id, Item, ServerId, ItemsListings)

            if Cache:
                globals()["QueryCache"][CacheId] = [True, ItemsListings]

    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems", 1) # LOGINFO

    if not xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings)):
        xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems FAIL", 3) # LOGERROR
        xbmc.executebuiltin('ReloadSkin()')
        return

    # Set Sorting
    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addSortMethod", 1) # LOGINFO

    if Unsorted:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)

    if query in ('Genre', 'Tags', 'Letter', 'Folder', 'Playlist', 'Default', 'Favorite'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    elif query in ('Photo', 'PhotoAlbum') or args[0] == ('Photo', 'PhotoAlbum'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
    elif query in ('Audio', 'MusicVideo') or args[0] in ('Audio', 'MusicVideo'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    elif query == 'MusicAlbum' or args[0] == 'MusicAlbum':
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    elif query in ('MusicArtist', 'MusicVideoArtist') or args[0] in ('MusicArtist', 'MusicVideoArtist'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
    elif query in ('Movie', 'Video', 'Series') or args[0] in ('Movie', 'Video', 'Series'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    elif query == 'Season' or args[0] == 'Season':
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
    elif query in ('Episode', 'Upcoming', 'NextUp') or args[0] in ('Episode', 'Upcoming', 'NextUp'):
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_EPISODE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
    else:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)

    if Content and Content in MappingContentKodi:
        xbmcplugin.setContent(Handle, MappingContentKodi[Content])
    else:
        if ItemsListings and ItemsListings[0][3] in MappingContentKodi:
            xbmcplugin.setContent(Handle, MappingContentKodi[ItemsListings[0][3]])

    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: endOfDirectory", 1) # LOGINFO
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def remotepictures(Handle, playposition):
    Handle = int(Handle)
    list_li = []

    for Pictures in playerops.Pictures:
        list_li.append((Pictures[0], Pictures[1], False))

    xbmcplugin.addDirectoryItems(Handle, list_li, len(list_li))
    xbmcplugin.setContent(Handle, "images")
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

    if playposition != "-1":
        utils.SendJson(f'{{"jsonrpc":"2.0","id":1,"method":"Player.Open","params":{{"item":{{"playlistid":2,"position":{playposition}}}}}}}')

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

        resp = utils.Dialog.select(utils.Translate(33054), AddNameArray)

        if resp < 0:
            return

        UserData = AddUserChoices[resp]
        EmbyServer.add_AdditionalUser(UserData['UserId'], UserData['UserName'])
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33067)} {UserData['UserName']}", icon=utils.icon, time=1000, sound=False)
    else:  # Remove user
        RemoveNameArray = []

        for RemoveUserChoice in RemoveUserChoices:
            RemoveNameArray.append(RemoveUserChoice['UserName'])

        resp = utils.Dialog.select(utils.Translate(33064), RemoveNameArray)

        if resp < 0:
            return

        UserData = RemoveUserChoices[resp]
        EmbyServer.remove_AdditionalUser(UserData['UserId'])
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33066)} {UserData['UserName']}", icon=utils.icon, time=1000, sound=False)

def load_ListItem(Id, Item, ServerId, ItemsListings):
    # Item was fetched from internal database
    if "ListItem" in Item:
        ItemsListings.append((Item["Path"], Item["ListItem"], Item["isFolder"], Item["Type"]))
        return

    # Create Kodi listitem for dynamic loaded item
    li = listitem.set_ListItem(Item, ServerId)

    if not Item.get('NodesMenu', False):
        if Item['Type'] in MappingStaggered:
            Item['Type'] = MappingStaggered[Item['Type']]
            Item['IsFolder'] = True

    if Item.get('IsFolder', False):
        params = {'id': Item['Id'], 'mode': "browse", 'query': Item['Type'], 'server': ServerId, 'arg': Item.get('args', Id)}
        path = f"plugin://{utils.PluginId}/?{urlencode(params)}"
        ItemsListings.append((path, li, True, Item["Type"]))
    else:
        path, _ = common.get_path_type_from_item(ServerId, Item)
        ItemsListings.append((path, li, False, Item["Type"]))

        if Item['Type'] in ("Movie", "Episode", "MusicVideo", "Video", "Audio"):
            globals()["DynamicNodeServerId"] = ServerId

#Menu structure nodes
def add_ListItem(ListItemData, label, path, isFolder, artwork, HelpText):
    li = xbmcgui.ListItem(label, path=path, offscreen=True)

    if utils.KodiMajorVersion == "19":
        li.setInfo('video', {'title': label, 'plotoutline': HelpText})
    else:
        InfoTags = li.getVideoInfoTag()
        InfoTags.setPlotOutline(HelpText)
        InfoTags.setTitle(label)

    li.setProperties({'IsFolder': 'true', 'IsPlayable': 'false'})
    li.setArt({"thumb": artwork, "fanart": "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png", "icon": artwork})
    ListItemData.append((path, li, isFolder))

def get_EmbyServerList():
    ServerIds = []
    ServerItems = []

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        ServerIds.append(ServerId)
        ServerItems.append(EmbyServer.ServerData['ServerName'])

    return len(utils.EmbyServers), ServerIds, ServerItems

def select_managelibs():  # threaded by monitor.py
    EmbyServersCounter, _, ServerItems = get_EmbyServerList()

    if EmbyServersCounter > 1:
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            manage_libraries(Selection)
    else:
        if EmbyServersCounter > 0:
            manage_libraries(0)

def manage_servers(ServerConnect):  # threaded by caller
    MenuItems = ["Add Server", "Remove Server", "Add User"]
    Selection = utils.Dialog.select("Server ops", MenuItems) # Manage libraries

    if Selection == 0:
        ServerConnect(None)
    elif Selection == 1:
        _, ServerIds, ServerItems = get_EmbyServerList()
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33448)}: {utils.EmbyServers[ServerIds[Selection]].ServerData['ServerName']}", icon=utils.icon, time=1500, sound=False)
            utils.EmbyServers[ServerIds[Selection]].ServerDisconnect()
    elif Selection == 2:
        _, ServerIds, ServerItems = get_EmbyServerList()
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            AddUser(utils.EmbyServers[ServerIds[Selection]])

def manage_libraries(ServerSelection):  # threaded by caller
    MenuItems = [utils.Translate(33098), utils.Translate(33154), utils.Translate(33140), utils.Translate(33184), utils.Translate(33139), utils.Translate(33234), utils.Translate(33060)]
    Selection = utils.Dialog.select(utils.Translate(33194), MenuItems) # Manage libraries
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
        utils.EmbyServers[EmbyServerId].library.SyncLiveTV()
    elif Selection == 6:
        utils.EmbyServers[EmbyServerId].library.SyncThemes()

def favepisodes(Handle):
    Handle = int(Handle)
    CacheId = "favepisodes"

    if CacheId in QueryCache and QueryCache[CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache[CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        episodes_kodiId = []

        for ServerId in utils.EmbyServers:
            embydb = dbio.DBOpenRO(ServerId, "favepisodes")
            episodes_kodiId += embydb.get_episode_fav()
            dbio.DBCloseRO(ServerId, "favepisodes")

        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "favepisodes")

        for episode_kodiId in episodes_kodiId:
            KodiItems += (videodb.get_episode_metadata_for_listitem(episode_kodiId[0]),)

        dbio.DBCloseRO("video", "favepisodes")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)
                globals()["QueryCache"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# This method will sync all Kodi artwork to textures13.db and cache them locally. This takes diskspace!
def cache_textures():
    xbmc.log("EMBY.helper.pluginmenu: <[ cache textures ]", 1) # LOGINFO
    DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33044))

    # Select content to be cached
    choices = [utils.Translate(33121), "Movies", "TVShows", "Season", "Episode", "Musicvideos", "Album", "Single", "Song", "Boxsets", "Actor", "Artist", "Writer", "Director", "Gueststar", "Producer", "Bookmarks", "Photoalbum", "Photos"]
    selection = utils.Dialog.multiselect(utils.Translate(33256), choices)

    if not selection:
        return

    if DelArtwork:
        DeleteThumbnails()

    utils.progress_open(utils.Translate(33045))
    utils.set_settings_bool('artworkcacheenable', False)
    Urls = []

    if 0 in selection or 17 in selection or 18 in selection:
        for ServerId, EmbyServer in list(utils.EmbyServers.items()):
            if 0 in selection or 17 in selection: # PhotoAlbum
                TotalRecords = EmbyServer.API.get_TotalRecords(None, "PhotoAlbum", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["PhotoAlbum"], True, True, {}):
                    path, _ = common.get_path_type_from_item(ServerId, Item)
                    TempUrls[ItemCounter] = (path,)
                    ItemCounter += 1

                Urls += TempUrls

            if 0 in selection or 18 in selection: # Photo
                TotalRecords = EmbyServer.API.get_TotalRecords(None, "Photo", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["Photo"], True, True, {}):
                    path, _ = common.get_path_type_from_item(ServerId, Item)
                    TempUrls[ItemCounter] = (path,)
                    ItemCounter += 1

                Urls += TempUrls

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
    utils.progress_close()

def get_image_metadata(ImageBinaryData, Hash):
    height = 0
    width = 0
    imageformat = ""
    ImageBinaryDataSize = len(ImageBinaryData)

    if ImageBinaryDataSize < 10:
        xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid image size: {Hash} / {ImageBinaryDataSize}", 2) # LOGWARNING
        return width, height, imageformat

    # JPG
    if ImageBinaryData[0] == 0xFF and ImageBinaryData[1] == 0xD8 and ImageBinaryData[2] == 0xFF:
        imageformat = "jpg"
        i = 4
        BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]

        while i < ImageBinaryDataSize:
            i += BlockLength

            if i >= ImageBinaryDataSize or ImageBinaryData[i] != 0xFF:
                xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid jpg: {Hash}", 2) # LOGWARNING
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
        xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid image format: {Hash}", 2) # LOGWARNING

    xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache image data: {width} / {height} / {Hash}", 0) # LOGDEBUG
    return width, height, imageformat

# Cache all entries
def CacheAllEntries(urls):
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    total = len(urls)
    ArtworkCacheItems = 1000 * [{}]
    ArtworkCacheIndex = 0

    for IndexUrl, url in enumerate(urls):
        if IndexUrl % 1000 == 0:
            add_textures(ArtworkCacheItems)
            ArtworkCacheItems = 1000 * [{}]
            ArtworkCacheIndex = 0

            if utils.getFreeSpace(utils.FolderUserdataThumbnails) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=5000, sound=True)
                xbmc.log("EMBY.helper.pluginmenu: Artwork cache: running out of space", 2) # LOGWARNING
                break
        else:
            ArtworkCacheIndex += 1

        if not url[0]:
            continue

        Folder = url[0].split("/")
        Data = url[0][url[0].rfind("/") + 1:].split("-")

        if len(Data) < 4 or len(Folder) < 5:
            xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: Invalid item found {url}", 2) # LOGWARNING
            continue

        ServerId = Folder[4]
        EmbyID = Data[1]
        ImageIndex = Data[2]
        ImageTag = Data[4]

        if Data[3] not in EmbyArtworkIDs:
            xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: Invalid (EmbyArtworkIDs) item found {url}", 2) # LOGWARNING
            continue

        ImageType = EmbyArtworkIDs[Data[3]]

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

        TempPath = f"{utils.FolderUserdataThumbnails}{Hash[0]}/{Hash}"

        if not utils.checkFileExists(f"{TempPath}.jpg") and not utils.checkFileExists(f"{TempPath}.png"):
            if len(Data) > 5 and ImageType == "Chapter":
                OverlayText = unquote("-".join(Data[5:]))
                ImageBinary = utils.image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText)
            else:
                ImageBinary, _, _ = utils.EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag)

            Width, Height, ImageFormat = get_image_metadata(ImageBinary, Hash)
            cachedUrl = f"{Hash[0]}/{Hash}.{ImageFormat}"
            utils.mkDir(f"{utils.FolderUserdataThumbnails}{Hash[0]}")
            Path = f"{utils.FolderUserdataThumbnails}{cachedUrl}"

            if Width == 0:
                xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: image not detected: {url[0]}", 2) # LOGWARNING
            else:
                utils.writeFileBinary(Path, ImageBinary)
                Size = len(ImageBinary)
                ArtworkCacheItems[ArtworkCacheIndex] = {'Url': url[0], 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': f"d0s{Size}", 'Path': Path, 'cachedUrl': cachedUrl}

        Value = int((IndexUrl + 1) / total * 100)
        utils.progress_update(Value, "Emby", f"{utils.Translate(33045)}: {EmbyID} / {IndexUrl}")

    add_textures(ArtworkCacheItems)

def add_textures(ArtworkCacheItems):
    texturedb = dbio.DBOpenRW("texture", "artwork_cache")

    for ArtworkCacheItem in ArtworkCacheItems:
        if ArtworkCacheItem:
            texturedb.add_texture(ArtworkCacheItem["Url"], ArtworkCacheItem["cachedUrl"], ArtworkCacheItem["ImageHash"], "1", ArtworkCacheItem["Width"], ArtworkCacheItem["Height"], "")

    dbio.DBCloseRW("texture", "artwork_cache")

def reset_querycache():
    if not playerops.RemoteMode: # keep cache in remote client mode -> don't overload Emby server
        for CacheList in list(QueryCache.values()):
            CacheList[0] = False

def get_next_episodes(Handle, libraryname):
    Handle = int(Handle)
    CacheId = f"next_episodes_{libraryname}"

    if CacheId in QueryCache and QueryCache[CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache[CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()

        for ServerId in utils.EmbyServers:
            DelayQuery = 0

            while utils.SyncPause.get(f'database_init_{ServerId}', False):
                if utils.sleep(1) :
                    return

                if DelayQuery >= 10:
                    continue

        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_next_episodes")

        if libraryname in common.MediaTags:
            NextEpisodeInfos = videodb.get_next_episodesIds(common.MediaTags[libraryname])

            for NextEpisodeInfo in NextEpisodeInfos[:int(utils.maxnodeitems)]:
                EpisodeId = NextEpisodeInfo.split(";")
                KodiItems += (videodb.get_episode_metadata_for_listitem(EpisodeId[1]),)

        dbio.DBCloseRO("video", "get_next_episodes")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)
                globals()["QueryCache"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Factory reset. wipes all db records etc.
def factoryreset():
    xbmc.log("EMBY.helper.pluginmenu: [ factory reset ]", 2) # LOGWARNING
    utils.SyncPause = {}
    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33223), icon=utils.icon, time=960000, sound=True)
    xbmc.executebuiltin('Dialog.Close(addoninformation)')

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        EmbyServer.ServerDisconnect()
        EmbyServer.stop()
        del utils.EmbyServers[ServerId]

    utils.delFolder(utils.FolderAddonUserdata)
    utils.delete_playlists()
    utils.delete_nodes()

    # delete databases
    delete_database('emby')
    delete_database('MyMusic')
    delete_database('MyVideos')
    DeleteThumbnails()
    xbmc.log("EMBY.helper.pluginmenu: [ complete reset ]", 1) # LOGINFO
    utils.restart_kodi()

def delete_database(Database):
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith(Database):
            utils.delFile(f"special://profile/Database/{Filename}")

# Reset both the emby database and the kodi database.
def databasereset():
    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
        return

    xbmc.log("EMBY.helper.pluginmenu: [ database reset ]", 1) # LOGINFO
    utils.SyncPause = {}
    DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33086))
    DeleteSettings = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33087))
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    videodb = dbio.DBOpenRW("video", "databasereset")
    videodb.common.delete_tables("Video")
    dbio.DBCloseRW("video", "databasereset")
    musicdb = dbio.DBOpenRW("music", "databasereset")
    musicdb.common.delete_tables("Music")
    dbio.DBCloseRW("music", "databasereset")

    if DelArtwork:
        DeleteThumbnails()

    if DeleteSettings:
        xbmc.log("EMBY.helper.pluginmenu: [ reset settings ]", 1) # LOGINFO
        utils.set_settings("MinimumSetup", "")
        utils.delFolder(utils.FolderAddonUserdata)
    else:
        _, files = utils.listDir(utils.FolderAddonUserdata)

        for Filename in files:
            if Filename.startswith('sync_'):
                utils.delFile(f"{utils.FolderAddonUserdata}{Filename}")

    # Delete Kodi's emby database(s)
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            utils.delFile(f"special://profile/Database/{Filename}")

    utils.delete_playlists()
    utils.delete_nodes()
    utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33088))
    utils.restart_kodi()

def reset_device_id():
    utils.device_id = ""
    utils.get_device_id(True)
    utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33033))
    utils.restart_kodi()

def DeleteThumbnails():
    xbmc.log("EMBY.helper.pluginmenu: -->[ reset artwork ]", 1) # LOGINFO
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    utils.progress_open(utils.Translate(33412))
    Folders, _ = utils.listDir('special://thumbnails/')
    TotalFolders = len(Folders)

    for CounterFolder, Folder in enumerate(Folders, 1):
        utils.progress_update(int(CounterFolder / TotalFolders * 100), utils.Translate(33199), f"{utils.Translate(33412)}: {Folder}")
        _, Files = utils.listDir(f"special://thumbnails/{Folder}")
        TotalFiles = len(Files)

        for CounterFile, File in enumerate(Files, 1):
            utils.progress_update(int(CounterFile / TotalFiles * 100), utils.Translate(33199), f"{utils.Translate(33412)}: {Folder}{File}")
            xbmc.log(f"EMBY.helper.pluginmenu: DELETE thumbnail {File}", 0) # LOGDEBUG
            utils.delFile(f"special://thumbnails/{Folder}{File}")

    texturedb = dbio.DBOpenRW("texture", "cache_textures")
    texturedb.common.delete_tables("Texture")
    dbio.DBCloseRW("texture", "cache_textures")
    utils.progress_close()
    xbmc.log("EMBY.helper.pluginmenu: --<[ reset artwork ]", 1) # LOGINFO

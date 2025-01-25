from urllib.parse import urlencode
import xbmc
import xbmcgui
import xbmcplugin
from database import dbio
from emby import listitem
from core import common
from . import utils, playerops, xmls, artworkcache

SearchTerm = ""
MappingStaggered = {"Series": "Season", "Season": "Episode", "PhotoAlbum": "HomeVideos", "MusicAlbum": "Audio"} # additional stagged content parameter written in the code, based on conditions
letters = ("0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")
MappingContentKodi = {"movies": "movies", "Video": "videos", "Season": "tvshows", "Episode": "episodes", "Series": "tvshows", "Movie": "movies", "Photo": "images", "PhotoAlbum": "images", "MusicVideo": "musicvideos", "MusicArtist": "artists", "MusicAlbum": "albums", "Audio": "songs", "TvChannel": "videos", "musicvideos": "musicvideos", "VideoMusicArtist": "musicvideos", "tvshows": "tvshows", "Folder": "files", "All": "files", "homevideos": "files", "Playlist": "files", "Trailer": "videos", "Person": "videos", "videos": "videos", "music": "songs"}
Subcontent = {"tvshows": ("Series", "Season", "Episode", "Genre", "BoxSet"), "movies": ("Movie", "Genre", "BoxSet"), "music": ("MusicArtist", "MusicAlbum", "MusicGenre", "BoxSet", "Audio"), "musicvideos": ("MusicArtist", "MusicGenre", "BoxSet"), "homevideos": ("Photo", "PhotoAlbum", "Video"), "videos": ("Series", "Season", "Episode", "Genre", "BoxSet", "Movie", "Video", "Person"), "playablevideos": ("MusicVideo", "Episode", "Movie", "Video"), "PlaylistsAudio": ("Audio",), "PlaylistsVideo": ("MusicVideo", "Episode", "Movie", "Video"), "Playlists": ("Audio", "MusicVideo", "Episode", "Movie", "Video")}
IconMapping = {"MusicArtist": "DefaultMusicArtists.png", "MusicAlbum": "DefaultMusicAlbums.png", "Audio": "DefaultMusicSongs.png", "Movie": "DefaultMovies.png", "Trailer": "DefaultAddonVideo.png", "BoxSet": "DefaultSets.png", "Series": "DefaultTVShows.png", "Season": "DefaultTVShowTitle.png", "Episode": "DefaultAddonVideo.png", "MusicVideo": "DefaultMusicVideos.png", "Video": "DefaultAddonVideo.png", "Photo": "DefaultPicture.png.png", "PhotoAlbum": "DefaultAddonPicture.png", "TvChannel": "DefaultAddonPVRClient.png", "Folder": "DefaultFolder.png", "Playlist": "DefaultPlaylist.png", "Genre": "DefaultGenre.png", "MusicGenre": "DefaultMusicGenres.png", "Person": "DefaultActor.png", "Tag": "DefaultTags.png", "Channel": "DefaultFolder.png", "CollectionFolder": "DefaultFolder.png", "Studio": "DefaultStudios.png"}
LibraryMenu = {"LibraryAdd": utils.Translate(33154), "LibraryRemove": utils.Translate(33184), "LibraryUpdate": utils.Translate(33139), "LibraryRepair": utils.Translate(33140), "RefreshBoxsets": utils.Translate(33098), "ToggleLiveTv": "", "RefreshLiveTv": utils.Translate(33706), "ToggleThemes": "", "RefreshThemes": utils.Translate(33707)}

# Build plugin menu
def listing(Handle, ContentSupported):
    ItemsListings = ()
    Handle = int(Handle)

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        if ContentSupported != "image":
            ItemsListings = add_ListItem(ItemsListings, f"{utils.Translate(33386)} ({EmbyServer.ServerData['ServerName']})", f"plugin://plugin.service.emby-next-gen/?mode=browse&query=NodesSynced&server={ServerId}&contentsupported={ContentSupported}", "DefaultHardDisk.png", utils.Translate(33383))

        ItemsListings = add_ListItem(ItemsListings, f"{utils.Translate(33387)} ({EmbyServer.ServerData['ServerName']})", f"plugin://plugin.service.emby-next-gen/?mode=browse&query=NodesDynamic&server={ServerId}&contentsupported={ContentSupported}", "DefaultNetwork.png", utils.Translate(33384))

    # Common Items
    if utils.menuOptions:
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33194), "plugin://plugin.service.emby-next-gen/?mode=managelibsselection", "DefaultAddSource.png", utils.Translate(33309))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33059), "plugin://plugin.service.emby-next-gen/?mode=texturecache", "DefaultAddonImages.png", utils.Translate(33310))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(5), "plugin://plugin.service.emby-next-gen/?mode=settings", "DefaultAddon.png", utils.Translate(33398))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33058), "plugin://plugin.service.emby-next-gen/?mode=databasereset", "DefaultAddonsUpdates.png", utils.Translate(33313))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33340), "plugin://plugin.service.emby-next-gen/?mode=factoryreset", "DefaultAddonsUpdates.png", utils.Translate(33400))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33341), "plugin://plugin.service.emby-next-gen/?mode=nodesreset", "DefaultAddonsUpdates.png", utils.Translate(33401))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33409), "plugin://plugin.service.emby-next-gen/?mode=skinreload", "DefaultAddonSkin.png", "")

    xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Browse dynamically content
def browse(Handle, Id, query, ParentId, Content, ServerId, LibraryId, ContentSupported):
    Handle = int(Handle)
    WindowId = xbmcgui.getCurrentWindowId()
    xbmc.log(f"EMBY.helper.pluginmenu: Browse: Id: {Id} / Query: {query} / ParentId: {ParentId} / LibraryId: {LibraryId} / Content: {Content} / WindowId: {WindowId} / ServerId: {ServerId} / ContentSupported: {ContentSupported}", 1) # LOGINFO
    ItemsListings = ()
    xbmc.executebuiltin('Dialog.Close(busydialog,true)')

    # Limit number of nodes for widget queries
    if WindowId not in (10502, 10025, 10002, 10035): # 10035=skinsettings, 10502=music, 10002=pictures, 10025=videos
        Extras = {"Limit": utils.maxnodeitems}
        CacheId = f"{Id}{query}{ParentId}{ServerId}{LibraryId}{utils.maxnodeitems}"
    else:
        Extras = {}
        CacheId = f"{Id}{query}{ParentId}{ServerId}{LibraryId}"

    if ServerId not in utils.EmbyServers:
        xbmc.log(f"EMBY.helper.pluginmenu: Pluginmenu invalid server id: {ServerId}", 3) # LOGERROR
        return

    if Id == ParentId == LibraryId and Id != "0": # ID = 0 means e.g. "search"
        WindowIdCheck = False
    else:
        WindowIdCheck = True

    xbmc.log(f"EMBY.helper.pluginmenu: WindowIdCheck: {WindowIdCheck}", 0) # LOGDEBUG
    ContentQuery = Content

    # Load from cache
    if Content in utils.QueryCache and CacheId in utils.QueryCache[Content] and utils.QueryCache[Content][CacheId][0]:
        if WindowIdCheck and reload_Window(Content, ContentQuery, WindowId, Handle, utils.QueryCache[Content][CacheId][3], utils.QueryCache[Content][CacheId][4], utils.QueryCache[Content][CacheId][5], utils.QueryCache[Content][CacheId][6], utils.QueryCache[Content][CacheId][7]):
            return

        add_ViewItems(Handle, query, Content, utils.QueryCache[Content][CacheId][1], utils.QueryCache[Content][CacheId][2])
        return

    if query in ('NodesDynamic', 'NodesSynced'):
        for Node in utils.EmbyServers[ServerId].Views.Nodes[query]:
            if (ContentSupported == "audio" and Node['path'].startswith("library://music/")) or (ContentSupported == "video" and Node['path'].startswith("library://video/")):
                ItemsListings = add_ListItem(ItemsListings, Node['title'], Node['path'], Node['icon'], "")

        # Images (library://picture/ is not supported by Kodi)
        if query == 'NodesDynamic':
            for Node in utils.EmbyServers[ServerId].Views.Nodes[query]:
                if ContentSupported == "image" and not Node['path'].startswith("library://"):
                    ItemsListings = add_ListItem(ItemsListings, Node['title'], f"plugin://plugin.service.emby-next-gen/?id={Node['path']}&mode=browse&query=ImageDynamic&server={ServerId}&parentid={ParentId}&content={Content}&libraryid={LibraryId}", Node['icon'], "")

        xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)
        return

    Unsorted = False
    EmbyContentQuery = ()

    if query == 'ImageDynamic':
        for Node in utils.EmbyServers[ServerId].Views.PictureNodes[Id]:
            ItemsListings = add_ListItem(ItemsListings, Node[0], Node[2], Node[3], "")

        xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)
        return

    if query == 'Letter':
        if Content in ('VideoMusicArtist', 'MusicArtist'):
            LocalContent = 'MusicArtist'
            LocalParentId = ParentId
        elif Content == "PlaylistsVideo":
            LocalParentId = None
            LocalContent = "Playlist"
            Content = "playablevideos"
        elif Content == "PlaylistsAudio":
            LocalParentId = None
            LocalContent = "Playlist"
            Content = "Audio"
        else:
            LocalContent = Content
            LocalParentId = ParentId

        if Id == "0-9":
            Extras.update({'NameLessThan': "A", "SortBy": "SortName"})
            EmbyContentQuery = (LocalParentId, [LocalContent], True, Extras, False, LibraryId)
        else:
            Extras.update({'NameStartsWith': Id, "SortBy": "SortName"})
            EmbyContentQuery = (LocalParentId, [LocalContent], True, Extras, False, LibraryId)
    elif query == 'Recentlyadded':
        Extras.update({"SortBy": "DateCreated", "SortOrder": "Descending", "GroupItems": "False", "Limit": utils.maxnodeitems})
        EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
        Unsorted = True
    elif query == 'Unwatched':
        Extras.update({'filters': 'IsUnplayed', 'SortBy': "Random", "Limit": utils.maxnodeitems})
        EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
        Unsorted = True
    elif query == 'Favorite':
        if Content in Subcontent:
            Extras.update({'filters': 'IsFavorite', "GroupItemsIntoCollections": True, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, Subcontent[Content], True, Extras, False, LibraryId)
        else:
            Extras.update({'filters': 'IsFavorite', "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
    elif query == 'Inprogress':
        Extras.update({'filters': 'IsResumable', "SortBy": "DatePlayed"})
        EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
    elif query == 'Resume': # Continue Watching
        Extras.update({"SortBy": "DatePlayed"})
        EmbyContentQuery = (ParentId, [Content], True, Extras, True, LibraryId)
    elif query == 'Recommendations':
        Doubles = []

        for Item in utils.EmbyServers[ServerId].API.get_recommendations(ParentId):
            if Item['Name'] not in Doubles:
                Doubles.append(Item['Name'])
            else:
                continue

            ItemsListings = load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId)

        del Doubles
    elif query == 'BoxSet':
        ParentId = Id

        if LibraryId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (Id, ['BoxSet'], True, Extras, False, LibraryId)
        else:
            Extras.update({"GroupItemsIntoCollections": True, "SortBy": "SortName"})
            EmbyContentQuery = (Id, ["All"], True, Extras, False, LibraryId)
    elif query == 'TvChannel':
        for Item in utils.EmbyServers[ServerId].API.get_channels():
            ItemsListings = load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId)
    elif query == "Playlist":
        ParentId = Id
        Unsorted = True

        if Content in Subcontent:
            EmbyContentQuery = (ParentId, Subcontent[Content], True, Extras, False, LibraryId)
        else:
            EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
    elif query in ("Playlists", "PlaylistsAudio", "PlaylistsVideo"):
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (ParentId, ["Playlist"], True, Extras, False, LibraryId)
    elif query == "Video":
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (ParentId, ["Video"], True, Extras, False, LibraryId)
    elif query == "All":
        if Content in Subcontent:
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, Subcontent[Content], True, Extras, False, LibraryId)
        else:
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, [Content], True, Extras, False, LibraryId)
    elif query == 'Random':
        Extras.update({'SortBy': "Random", "Limit": utils.maxnodeitems})
        EmbyContentQuery = (Id, [Content], True, Extras, False, LibraryId)
        Unsorted = True
    elif query == 'Upcoming':
        for Item in utils.EmbyServers[ServerId].API.get_upcoming(ParentId):
            ItemsListings = load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId)

    elif query == 'NextUp':
        for Item in utils.EmbyServers[ServerId].API.get_NextUp(Id):
            ItemsListings = load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId)

        Unsorted = True
    elif query == 'Season':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Season"], True, Extras, False, LibraryId)
    elif query == 'Episode':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Episode"], True, Extras, False, LibraryId)
    elif query == 'Series':
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (ParentId, ["Series"], True, Extras, False, LibraryId)
    elif query == 'Photo':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Photo"], True, Extras, False, LibraryId)
    elif query == 'HomeVideos':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Photo", "PhotoAlbum", "Video", "Folder"], False, Extras, False, LibraryId)
    elif query == 'PhotoAlbum':
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (ParentId, ["PhotoAlbum"], True, Extras, False, LibraryId)
        Content = "Photo"
    elif query == "Folder":
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Folder", "Episode", "Movie", "MusicVideo", "BoxSet", "MusicAlbum", "MusicArtist", "Season", "Series", "Audio", "Video", "Trailer", "Photo", "PhotoAlbum"], False, Extras, False, LibraryId)
    elif query == 'MusicVideo':
        if ParentId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["MusicVideo"], True, Extras, False, LibraryId)
        else:
            Extras.update({'ArtistIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["MusicVideo"], True, Extras, False, LibraryId)
    elif query in ('VideoMusicArtist', 'MusicArtist'):
        EmbyContentQuery = (ParentId, ["MusicArtist"], True, {"SortBy": "SortName"}, False, LibraryId)
    elif query == 'MusicGenre':
        if ParentId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["MusicGenre"], True, Extras, False, LibraryId)
        else:
            if Content == "music":
                SubContentQuery = ("Audio",)
            else:
                SubContentQuery = (Content, )

            Extras.update({'GenreIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, SubContentQuery, True, Extras, False, LibraryId)
    elif query == 'Genre':
        if ParentId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["Genre"], True, Extras, False, LibraryId)
        else:
            if Content == "tvshows":
                SubContentQuery = ("Series",)
            elif Content == "movies":
                SubContentQuery = ("Movie",)
            elif Content == "musicvideos":
                SubContentQuery = ("MusicVideo",)
            elif Content == "homevideos":
                SubContentQuery = ("Video", "PhotoAlbum", "Photo")
            elif Content == "videos":
                SubContentQuery = ("Episode", "Movie", "Video")
            else:
                SubContentQuery = (Content, )

            Extras.update({'GenreIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, SubContentQuery, True, Extras, False, LibraryId)
    elif query == 'Person':
        if LibraryId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (None, ['Movie', "Series", "Episode"], True, Extras, False, LibraryId)
        else:
            Extras.update({'PersonIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (None, ['Movie', "Series", "Episode"], True, Extras, False, LibraryId)
    elif query == 'Tag':
        if LibraryId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["Tag"], True, Extras, False, LibraryId)
        else:
            Extras.update({'TagIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, Subcontent[Content], True, Extras, False, LibraryId)
    elif query == 'Movie':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Movie"], True, Extras, False, LibraryId)
    elif query == 'Audio':
        Extras.update({"SortBy": "SortName"})
        ParentId = Id
        EmbyContentQuery = (ParentId, ["Audio"], True, Extras, False, LibraryId)
    elif query == 'MusicAlbum':
        if LibraryId == Id: # initial query
            Extras.update({"SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["MusicAlbum"], True, Extras, False, LibraryId)
        else:
            Extras.update({'ArtistIds': Id, "SortBy": "SortName"})
            EmbyContentQuery = (ParentId, ["MusicAlbum"], True, Extras, False, LibraryId)
    elif query == 'Search':
        Extras.update({'SearchTerm': SearchTerm})
        EmbyContentQuery = (ParentId, ["Person", "Genre", "MusicGenre", "Movie", "Video", "Series", "Episode", "MusicVideo", "MusicArtist", "MusicAlbum", "Audio"], True, Extras, False, LibraryId)

    SortItems = {"MusicArtist": (), "MusicAlbum": (), "Audio": (), "Movie": (), "Trailer": (), "BoxSet": (), "Series": (), "Season": (), "Episode": (), "MusicVideo": (), "Video": (), "Photo": (), "PhotoAlbum": (), "TvChannel": (), "Folder": (), "Playlist": (), "Genre": (), "MusicGenre": (), "Person": (), "Tag": (), "Channel": (), "CollectionFolder": (), "Studio": ()}

    if EmbyContentQuery:
        Doublesfilter = set() # Emby server workaround bug -> IncludeItemTypes not respected by folders

        for Item in utils.EmbyServers[ServerId].API.get_Items_dynamic(*EmbyContentQuery):
            ItemId = Item.get("Id", "")

            if ItemId:
                if ItemId not in Doublesfilter:
                    Doublesfilter.add(ItemId)
                else:
                    continue

            if utils.SystemShutdown:
                return

            if Item['Type'] in SortItems:
                SortItems[Item['Type']] += (Item,)
            else:
                xbmc.log(f"EMBY.helper.pluginmenu: Invalid content: {Item['Type']}", 3) # LOGERROR

        TypeCounter = 0

        for SortItemContent, SortedItems in list(SortItems.items()):
            if SortedItems and SortItemContent not in ("Folder", "PhotoAlbum"):
                TypeCounter += 1

                if TypeCounter == 2: # multiple content types detected
                    break

        if TypeCounter == 2:
            for SortItemContent, SortedItems in list(SortItems.items()):
                if not SortedItems or SortItemContent in ("Folder", "PhotoAlbum"):
                    continue

                if SortItemContent not in utils.QueryCache:
                    utils.QueryCache[SortItemContent] = {}

                ItemsListingsCached = ()

                for SortedItem in SortedItems:
                    ItemsListingsCached = load_ListItem(ParentId, SortedItem, ServerId, ItemsListingsCached, Content, LibraryId)

                utils.QueryCache[SortItemContent][f"{Id}{SortItemContent}{ParentId}{ServerId}{LibraryId}"] = [True, ItemsListingsCached, Unsorted, Id, SortItemContent, ServerId, ParentId, LibraryId]
                ItemsListings = add_ListItem(ItemsListings, f"--{SortItemContent}--", f"plugin://plugin.service.emby-next-gen/?id={Id}&mode=browse&query={SortItemContent}&server={ServerId}&parentid={ParentId}&content={SortItemContent}&libraryid={LibraryId}", IconMapping[SortItemContent], SortItemContent)

            WindowIdCheck = False
        else: # unique content
            for SortItemContent, SortedItems in list(SortItems.items()):
                if SortedItems:
                    if SortItemContent in ("Folder", "PhotoAlbum"):
                        continue

                    if SortItemContent not in ("Genre", "MusicGenre", "Tag", "Playlist"): # Skip subqueries
                        Content = SortItemContent

                    for SortedItem in SortedItems:
                        ItemsListings = load_ListItem(ParentId, SortedItem, ServerId, ItemsListings, Content, LibraryId)

                    break

        # Always add not playable items
        for SubFolder in ("Folder", "PhotoAlbum"):
            for FolderItem in SortItems[SubFolder]:
                ItemsListings = load_ListItem(ParentId, FolderItem, ServerId, ItemsListings, Content, LibraryId)

    if ContentQuery not in utils.QueryCache:
        utils.QueryCache[ContentQuery] = {}

    utils.QueryCache[ContentQuery][CacheId] = [True, ItemsListings, Unsorted, Id, query, ServerId, ParentId, LibraryId]

    if WindowIdCheck and reload_Window(Content, ContentQuery, WindowId, Handle, Id, query, ServerId, ParentId, LibraryId):
        return

    add_ViewItems(Handle, query, Content, ItemsListings, Unsorted)

# Workaround for invalid window query
# check if video or music navigation window is open (MyVideoNav.xml MyMusicNav.xml) -> open MyPics.xml etc 10502 = music, 10025 = videos, 10002 = pictures
def reload_Window(Content, ContentQuery, WindowId, Handle, Id, query, ServerId, ParentId, LibraryId):
    if utils.SyncPause.get('kodi_rw', False): # skip if scan is in progress
        return False

    ReloadWindowId = ""

    if Content == "Photo" and WindowId in (10502, 10025):
    #if Content in ("Photo", "PhotoAlbum") and WindowId in (10502, 10025):
        ReloadWindowId = "pictures"
    elif Content in ("MusicAlbum", "MusicArtist", "Audio") and WindowId in (10002, 10025):
        ReloadWindowId = "music"
    elif Content in ("VideoMusicArtist", "Series", "Season", "Episode", "Movie", "Video", "MusicVideo") and WindowId in (10002, 10502):
        ReloadWindowId = "videos"

    if ReloadWindowId:
        xbmc.log(f"EMBY.helper.pluginmenu: Change of (browse) node content. Reload window: {Content} / {WindowId} / {ReloadWindowId}", 1) # LOGINFO
        xbmcplugin.endOfDirectory(Handle, succeeded=True, cacheToDisc=False)
        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        xbmc.executebuiltin('Action(back)')
        ControlListSize = 99999

        # Wait for "Back" Action processed
        for _ in range(20): # Timeout 2 seconds
            WindowIdCompare = xbmcgui.getCurrentWindowId()

            if WindowIdCompare != WindowId:
                break

            CurrentWindow = xbmcgui.Window(WindowIdCompare)
            ControlItemId = CurrentWindow.getFocusId()

            if ControlItemId == 0:
                break

            try:
                ControlItem = CurrentWindow.getControl(ControlItemId)
                ControlListSize = ControlItem.size()
            except Exception as Error:
                xbmc.log(f"EMBY.helper.pluginmenu: ControlItem invalid: {Error}", 3) # LOGERROR
                break

            if ControlListSize == 0:
                break

            xbmc.sleep(100)
        else:
            xbmc.log("EMBY.helper.pluginmenu: ReloadWindow timeout", 3) # LOGERROR

        xbmc.executebuiltin('Dialog.Close(busydialog,true)')
        utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "{ReloadWindowId}", "parameters": ["plugin://plugin.service.emby-next-gen/?id={Id}&mode=browse&query={query}&server={ServerId}&parentid={ParentId}&content={ContentQuery}&libraryid={LibraryId}", "return"]}}}}')
        return True

    return False

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
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33067)} {UserData['UserName']}", icon=utils.icon, time=utils.displayMessage, sound=False)
    else:  # Remove user
        RemoveNameArray = []

        for RemoveUserChoice in RemoveUserChoices:
            RemoveNameArray.append(RemoveUserChoice['UserName'])

        resp = utils.Dialog.select(utils.Translate(33064), RemoveNameArray)

        if resp < 0:
            return

        UserData = RemoveUserChoices[resp]
        EmbyServer.remove_AdditionalUser(UserData['UserId'])
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33066)} {UserData['UserName']}", icon=utils.icon, time=utils.displayMessage, sound=False)

def load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId):
    if "ListItem" in Item: # Item was fetched from internal database
        ItemsListings += ((Item["Path"], Item["ListItem"], Item["isFolder"]),)
    else: # Create Kodi listitem for dynamic loaded item
        ListItem = listitem.set_ListItem(Item, ServerId)

        if Item.get('IsFolder', False) or Item['Type'] in ("Tag", "Genre", "Person", "MusicGenre", "MusicArtist", "MusicAlbum", "Folder"):
            StaggeredQuery = Item['Type']

            if StaggeredQuery in MappingStaggered:
                StaggeredQuery = MappingStaggered[StaggeredQuery]
            elif StaggeredQuery == "MusicArtist" and LibraryId:
                if LibraryId == "0": # Search
                    StaggeredQuery = "Audio"
                else:
                    if utils.EmbyServers[ServerId].Views.ViewItems[LibraryId][1] in ('music', 'audiobooks', 'podcasts'):
                        StaggeredQuery = "MusicAlbum"
                    else:
                        StaggeredQuery = "MusicVideo"

            params = {'id': Item['Id'], 'mode': "browse", 'query': StaggeredQuery, 'server': ServerId, 'parentid': ParentId, 'content': Content, 'libraryid': LibraryId}
            ItemsListings += ((f"plugin://plugin.service.emby-next-gen/?{urlencode(params)}", ListItem, True),)
        else:
            common.set_path_filename(Item, ServerId, None, True)
            ItemsListings += ((Item['KodiFullPath'], ListItem, False),)

    return ItemsListings

#Menu structure nodes
def add_ListItem(ItemsListings, label, path, artwork, HelpText):
    ListItem = xbmcgui.ListItem(label, HelpText, path, True)
    ListItem.setContentLookup(False)
    ListItem.setProperties({'IsFolder': 'true', 'IsPlayable': 'false'})
    ListItem.setArt({"thumb": artwork, "fanart": "special://home/addons/plugin.service.emby-next-gen/resources/fanart.jpg", "landscape": artwork or "special://home/addons/plugin.service.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.service.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.service.emby-next-gen/resources/clearlogo.png", "icon": artwork})
    ItemsListings += ((path, ListItem, True),)
    return ItemsListings

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
    Selection = utils.Dialog.select(utils.Translate(33648), [utils.Translate(33134), utils.Translate(33141), utils.Translate(33062)]) # Manage libraries

    if Selection == 0:
        ServerConnect(None)
    elif Selection == 1:
        _, ServerIds, ServerItems = get_EmbyServerList()
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            utils.EmbyServers[ServerIds[Selection]].ServerData['ServerRemoved'] = True
            xbmc.executebuiltin('Dialog.Close(addoninformation)')
            utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33448)}: {utils.EmbyServers[ServerIds[Selection]].ServerData['ServerName']}", icon=utils.icon, time=utils.displayMessage, sound=False)
            SQLs = {}
            dbio.DBOpenRW(ServerIds[Selection], "remove_emby_server", SQLs)

            for LibrarySyncedId in utils.EmbyServers[ServerIds[Selection]].library.LibrarySyncedNames:
                SQLs["emby"].add_remove_library_items(LibrarySyncedId)
                SQLs["emby"].add_RemoveItem("library", LibrarySyncedId)

            SQLs["emby"].add_RemoveItem("library", "999999999")
            SQLs["emby"].add_remove_library_items_person()
            dbio.DBCloseRW(ServerIds[Selection], "remove_emby_server", SQLs)
            utils.SyncPause[f"database_init_{utils.EmbyServers[ServerIds[Selection]].ServerData['ServerId']}"] = False
            utils.EmbyServers[ServerIds[Selection]].library.RunJobs(False)

            for LibraryId in utils.EmbyServers[ServerIds[Selection]].Views.ViewItems:
                utils.EmbyServers[ServerIds[Selection]].Views.delete_node_by_id(LibraryId, True)

            utils.EmbyServers[ServerIds[Selection]].ServerDisconnect()
            del utils.EmbyServers[ServerIds[Selection]]
    elif Selection == 2:
        _, ServerIds, ServerItems = get_EmbyServerList()
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            AddUser(utils.EmbyServers[ServerIds[Selection]])

def manage_libraries(ServerSelection):  # threaded by caller
    ServerIds = list(utils.EmbyServers)
    EmbyServerId = ServerIds[ServerSelection]

    while True:
        SelectionMenu = ([], [])

        for Id, Text in list(LibraryMenu.items()):
            if Id == "ToggleLiveTv":
                if utils.LiveTVEnabled:
                    Text = utils.Translate(33708)
                else:
                    Text = utils.Translate(33709)
            elif Id == "ToggleThemes":
                if utils.ThemesEnabled:
                    Text = utils.Translate(33710)
                else:
                    Text = utils.Translate(33711)
            elif Id == "RefreshLiveTv":
                if not utils.LiveTVEnabled:
                    continue
            elif Id == "RefreshThemes":
                if not utils.ThemesEnabled:
                    continue

            SelectionMenu[0].append(Id)
            SelectionMenu[1].append(Text)

        Selection = utils.Dialog.select(utils.Translate(33194), SelectionMenu[1]) # Manage libraries

        if Selection == -1:
            return

        if SelectionMenu[0][Selection] == "LibraryAdd":
            utils.EmbyServers[EmbyServerId].library.select_libraries("AddLibrarySelection")
        elif SelectionMenu[0][Selection] == "LibraryRemove":
            utils.EmbyServers[EmbyServerId].library.select_libraries("RemoveLibrarySelection")
        elif SelectionMenu[0][Selection] == "LibraryUpdate":
            utils.EmbyServers[EmbyServerId].library.select_libraries("UpdateLibrarySelection")
        elif SelectionMenu[0][Selection] == "LibraryRepair":
            utils.EmbyServers[EmbyServerId].library.select_libraries("RepairLibrarySelection")
        elif SelectionMenu[0][Selection] == "RefreshBoxsets":
            utils.EmbyServers[EmbyServerId].library.refresh_boxsets()
        elif SelectionMenu[0][Selection] == "ToggleLiveTv":
            if not utils.check_iptvsimple():
                continue

            utils.set_settings_bool("LiveTVEnabled", not utils.LiveTVEnabled)

            if utils.LiveTVEnabled:
                utils.start_thread(utils.EmbyServers[EmbyServerId].library.SyncLiveTV, ())
            else:
                utils.delFile(f"{utils.FolderEmbyTemp}{EmbyServerId}-livetv.m3u")
                utils.delFile(f"{utils.FolderEmbyTemp}{EmbyServerId}-livetvepg.xml")
        elif SelectionMenu[0][Selection] == "ToggleThemes":
            if not utils.check_tvtunes():
                utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33152))
                continue

            utils.set_settings_bool("ThemesEnabled", not utils.ThemesEnabled)

            if utils.ThemesEnabled:
                utils.EmbyServers[EmbyServerId].library.SyncThemes()
            else:
                utils.delFolder(utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-themes"))
        elif SelectionMenu[0][Selection] == "RefreshLiveTv":
            utils.start_thread(utils.EmbyServers[EmbyServerId].library.SyncLiveTV, ())
        elif SelectionMenu[0][Selection] == "RefreshThemes":
            utils.EmbyServers[EmbyServerId].library.SyncThemes()

# Special favorite synced node
def favepisodes(Handle):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    Handle = int(Handle)
    CacheId = "favepisodes"

    if "Episode" not in utils.QueryCache:
        utils.QueryCache["Episode"] = {}

    if CacheId in utils.QueryCache["Episode"] and utils.QueryCache["Episode"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Episode"][CacheId][1]
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
            KodiItems += (videodb.get_episode_metadata_for_listitem(episode_kodiId[0], None),)

        dbio.DBCloseRO("video", "favepisodes")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)

        utils.QueryCache["Episode"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def favseasons(Handle):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    Handle = int(Handle)
    CacheId = "favseasons"

    if "Season" not in utils.QueryCache:
        utils.QueryCache["Season"] = {}

    if CacheId in utils.QueryCache["Season"] and utils.QueryCache["Season"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Season"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        seasons_kodiId = []

        for ServerId in utils.EmbyServers:
            embydb = dbio.DBOpenRO(ServerId, "favseasons")
            seasons_kodiId += embydb.get_season_fav()
            dbio.DBCloseRO(ServerId, "favseasons")

        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "favseasons")

        for season_kodiId in seasons_kodiId:
            KodiItems += (videodb.get_season_metadata_for_listitem(season_kodiId[0]),)

        dbio.DBCloseRO("video", "favseasons")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['path'], ListItem, isFolder),)

        utils.QueryCache["Season"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.setContent(Handle, 'tvshows')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Special collection synced node
def collections(Handle, KodiMediaType, LibraryTag):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "BoxSet" not in utils.QueryCache:
        utils.QueryCache["BoxSet"] = {}

    Handle = int(Handle)
    CacheId = f"collections_{LibraryTag}_{KodiMediaType}"

    if CacheId in utils.QueryCache["BoxSet"] and utils.QueryCache["BoxSet"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["BoxSet"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        videodb = dbio.DBOpenRO("video", "collections")
        CollectionTagIds, CollectionNames = videodb.get_collection_tags(LibraryTag, KodiMediaType)
        dbio.DBCloseRO("video", "collections")

        for Index, CollectionTagId in enumerate(CollectionTagIds):
            Name = CollectionNames[Index].replace(" (Collection)", "")
            ListItem = xbmcgui.ListItem(label=Name, offscreen=True, path=f"videodb://{KodiMediaType}s/tags/{CollectionTagId}/")
            InfoTags = ListItem.getVideoInfoTag()
            InfoTags.setTitle(Name)
            ListItem.setContentLookup(False)
            ListItems += ((f"videodb://{KodiMediaType}s/tags/{CollectionTagId}/", ListItem, True),)

        utils.QueryCache["BoxSet"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'set')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# This method will sync all Kodi artwork to textures13.db and cache them locally. This takes diskspace!
def cache_textures():
    xbmc.log("EMBY.helper.pluginmenu: <[ cache textures ]", 1) # LOGINFO
    DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33044))

    # Select content to be cached
    selection = utils.Dialog.multiselect(utils.Translate(33256), [utils.Translate(33121), utils.Translate(33632), utils.Translate(33633), utils.Translate(33634), utils.Translate(33489), utils.Translate(33363), utils.Translate(33362), utils.Translate(33638), utils.Translate(30185), utils.Translate(33639), utils.Translate(33343), utils.Translate(33640), utils.Translate(33369), utils.Translate(33368)])

    if not selection:
        return

    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    ProgressBar = xbmcgui.DialogProgressBG()
    ProgressBar.create(utils.Translate(33199), utils.Translate(33045))

    if DelArtwork:
        DeleteThumbnails()

    utils.set_settings_bool('artworkcacheenable', False)

    for Urls in cache_textures_generator(selection):
        Urls = list(dict.fromkeys(Urls)) # remove duplicates
        artworkcache.CacheAllEntries(Urls, ProgressBar)

    utils.set_settings_bool('artworkcacheenable', True)
    ProgressBar.close()
    del ProgressBar

def cache_textures_generator(selection):
    if 0 in selection or 12 in selection or 13 in selection:
        for ServerId, EmbyServer in list(utils.EmbyServers.items()):
            if 0 in selection or 12 in selection: # PhotoAlbum
                TotalRecords = EmbyServer.API.get_TotalRecords(None, "PhotoAlbum", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["PhotoAlbum"], True, True, {}, "", True, None):
                    common.set_path_filename(Item, ServerId, None, True)
                    TempUrls[ItemCounter] = (Item['KodiFullPath'],)
                    ItemCounter += 1

                yield TempUrls

            if 0 in selection or 13 in selection: # Photo
                TotalRecords = EmbyServer.API.get_TotalRecords(None, "Photo", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["Photo"], True, True, {}, "", True, None):
                    common.set_path_filename(Item, ServerId, None, True)
                    TempUrls[ItemCounter] = (Item['KodiFullPath'],)
                    ItemCounter += 1

                yield TempUrls

    if 0 in selection or 1 in selection or 2 in selection or 3 in selection or 4 in selection or 5 in selection or 8 in selection or 9 in selection or 11 in selection:
        videodb = dbio.DBOpenRO("video", "cache_textures")

        if 0 in selection:
            yield videodb.get_bookmark_urls_all()
            yield videodb.common_db.get_artwork_urls_all()
        else:
            if 1 in selection:
                yield videodb.common_db.get_artwork_urls("movie")

            if 2 in selection:
                yield videodb.common_db.get_artwork_urls("tvshow")

            if 3 in selection:
                yield videodb.common_db.get_artwork_urls("season")

            if 4 in selection:
                yield videodb.common_db.get_artwork_urls("episode")

            if 5 in selection:
                yield videodb.common_db.get_artwork_urls("musicvideo")

            if 8 in selection:
                yield videodb.common_db.get_artwork_urls("set")

            if 9 in selection:
                yield videodb.common_db.get_artwork_urls("actor")

            if 11 in selection:
                yield videodb.get_bookmark_urls_all()

        dbio.DBCloseRO("video", "cache_textures")

    if 0 in selection or 6 in selection or 7 in selection or 10 in selection:
        musicdb = dbio.DBOpenRO("music", "cache_textures")

        if 0 in selection:
            yield musicdb.common_db.get_artwork_urls_all()
        else:
            if 6 in selection:
                yield musicdb.common_db.get_artwork_urls("album")

            if 7 in selection:
                yield musicdb.common_db.get_artwork_urls("song")

            if 10 in selection:
                yield musicdb.common_db.get_artwork_urls("artist")

        dbio.DBCloseRO("music", "cache_textures")

def get_next_episodes(Handle, libraryname):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "Episode" not in utils.QueryCache:
        utils.QueryCache["Episode"] = {}

    Handle = int(Handle)
    CacheId = f"next_episodes_{libraryname}"

    if CacheId in utils.QueryCache["Episode"] and utils.QueryCache["Episode"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Episode"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_next_episodes")
        NextEpisodeInfos = videodb.get_next_episodesIds(libraryname)

        for NextEpisodeInfo in NextEpisodeInfos:
            EpisodeId = NextEpisodeInfo.split(";")
            KodiItems += (videodb.get_episode_metadata_for_listitem(EpisodeId[1], None),)

        dbio.DBCloseRO("video", "get_next_episodes")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)

        utils.QueryCache["Episode"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def get_next_episodes_played(Handle, libraryname):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "Episode" not in utils.QueryCache:
        utils.QueryCache["Episode"] = {}

    Handle = int(Handle)
    CacheId = f"next_episodes_played_{libraryname}"

    if CacheId in utils.QueryCache["Episode"] and utils.QueryCache["Episode"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Episode"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_next_episodes")
        NextEpisodeInfos = videodb.get_last_played_next_episodesIds(libraryname)

        for NextEpisodeInfo in NextEpisodeInfos:
            EpisodeId = NextEpisodeInfo.split(";")
            KodiItems += (videodb.get_episode_metadata_for_listitem(EpisodeId[1], None),)

        dbio.DBCloseRO("video", "get_next_episodes")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)

        utils.QueryCache["Episode"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def get_playlist(Handle, ServerId, MediaType, Id):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "Playlist" not in utils.QueryCache:
        utils.QueryCache["Playlist"] = {}

    Handle = int(Handle)
    CacheId = f"get_playlist_{ServerId}_{Id}_{MediaType}"

    if CacheId in utils.QueryCache["Playlist"] and utils.QueryCache["Playlist"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Playlist"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        embydb = dbio.DBOpenRO(ServerId, "playlist")

        if not Id:
            Playlists = embydb.get_Records_by_EmbyType("Playlist")

            for Playlist in Playlists:
                KodiPlaylistIds = Playlist[1].split(";")
                PlaylistName = ""
                Path = ""

                if MediaType == "audio":
                    if KodiPlaylistIds[1] and KodiPlaylistIds[1].endswith("_audio"):
                        Path = f'plugin://plugin.service.emby-next-gen/?mode=playlist&mediatype={MediaType}&server={ServerId}&id={KodiPlaylistIds[1]}'
                        PlaylistName = KodiPlaylistIds[1].replace("emby_", "").replace("_audio", "").replace("_", " ")
                else:
                    if KodiPlaylistIds[0] and KodiPlaylistIds[0].endswith("_video"):
                        Path = f'plugin://plugin.service.emby-next-gen/?mode=playlist&mediatype={MediaType}&server={ServerId}&id={KodiPlaylistIds[0]}'
                        PlaylistName = KodiPlaylistIds[0].replace("emby_", "").replace("_video", "").replace("_", " ")

                if not PlaylistName:
                    continue

                ListItems = add_ListItem(ListItems, PlaylistName, Path, Playlist[3], "")
        else:
            if MediaType == "audio":
                PlaylistData = utils.readFileString(f"{utils.PlaylistPathMusic}{Id}.m3u")
                musicdb = dbio.DBOpenRO("music", "playlist")
            else:
                PlaylistData = utils.readFileString(f"{utils.PlaylistPathVideo}{Id}.m3u")
                videodb = dbio.DBOpenRO("video", "playlist")

            # Get EmbyIds from m3u
            KodiItems = ()
            PlaylistRecords = PlaylistData.split("#EXTINF:")

            for PlaylistRecord in PlaylistRecords[1:]:
                if PlaylistRecord:
                    Data = PlaylistRecord.split("/")

                    if MediaType == "audio":
                        Data = Data[len(Data) - 1]
                        Data = Data.split("-")
                        EmbyId = Data[1]
                        KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "Audio")
                        KodiItems += (musicdb.get_song_metadata_for_listitem(KodiId),)
                    else:
                        if len(Data) < 8:
                            xbmc.log(f"EMBY.helper.pluginmenu: Playlist unknown content: {PlaylistRecord}", 2) # LOGWARN
                            continue

                        EmbyId = Data[7]
                        Data = Data[len(Data) - 2]
                        Data = Data.split("-")

                        if Data[0] == "M":
                            KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "MusicVideo")
                            KodiItems += (videodb.get_musicvideos_metadata_for_listitem(KodiId, ""),)
                        elif Data[0] == "m":
                            KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "Movie")
                            KodiItems += (videodb.get_movie_metadata_for_listitem(KodiId, ""),)
                        elif Data[0] == "e":
                            KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "Episode")
                            KodiItems += (videodb.get_episode_metadata_for_listitem(KodiId, ""),)
                        elif Data[0] == "v":
                            KodiId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "Video")
                            KodiItems += (videodb.get_movie_metadata_for_listitem(KodiId, ""),)

            if MediaType == "audio":
                dbio.DBCloseRO("music", "playlist")
            else:
                dbio.DBCloseRO("video", "playlist")

            for KodiItem in KodiItems:
                if KodiItem:
                    isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                    ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)

        dbio.DBCloseRO(ServerId, "playlist")
        utils.QueryCache["Playlist"][CacheId] = [True, ListItems]

    if ListItems:
        xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))

        if Id:
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        else:
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)

        if MediaType == "audio":
            xbmcplugin.setContent(Handle, 'songs')
        else:
            xbmcplugin.setContent(Handle, 'videos')

    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def get_inprogress_mixed(Handle):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "Episode_Movie_MusicVideo" not in utils.QueryCache:
        utils.QueryCache["Episode_Movie_MusicVideo"] = {}

    Handle = int(Handle)
    CacheId = "inprogress_mixed"

    if CacheId in utils.QueryCache["Episode_Movie_MusicVideo"] and utils.QueryCache["Episode_Movie_MusicVideo"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = utils.QueryCache["Episode_Movie_MusicVideo"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_inprogress_mixed")
        InProgressInfos = videodb.get_inprogress_mixedIds()

        for InProgressInfo in InProgressInfos:
            KodiItem = InProgressInfo.split(";")

            if len(KodiItem) == 3:
                if KodiItem[2] == "Movie":
                    KodiItems += (videodb.get_movie_metadata_for_listitem(KodiItem[1], None),)
                elif KodiItem[2] == "Episode":
                    KodiItems += (videodb.get_episode_metadata_for_listitem(KodiItem[1], None),)
                elif KodiItem[2] == "MusicVideo":
                    KodiItems += (videodb.get_musicvideos_metadata_for_listitem(KodiItem[1], None),)

        dbio.DBCloseRO("video", "get_inprogress_mixed")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)

        utils.QueryCache["Episode_Movie_MusicVideo"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'videos')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Delete all downloaded content
def downloadreset(Path=""):
    xbmc.log("EMBY.helper.pluginmenu: -->[ reset download ]", 1) # LOGINFO

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33573)):
        if Path:
            DownloadPath = Path
        else:
            DownloadPath = utils.DownloadPath

        utils.delFolder(utils.PathAddTrailing(f"{DownloadPath}EMBY-offline-content"))
        SQLs = {}
        dbio.DBOpenRW("video", "downloadreset", SQLs)
        Artworks = ()

        for ServerId in utils.EmbyServers:
            dbio.DBOpenRW(ServerId, "downloadreset", SQLs)

            for Item in SQLs['emby'].get_DownloadItem():
                SQLs['video'].replace_PathId(Item[2], Item[1])
                SQLs['emby'].delete_DownloadItem(Item[0])
                ArtworksData = SQLs['video'].get_artworks(Item[3], Item[4])

                for ArtworkData in ArtworksData:
                    if ArtworkData[3] in ("poster", "thumb", "landscape"):
                        UrlMod = ArtworkData[4].replace("-download", "")
                        SQLs['video'].update_artwork(ArtworkData[0], UrlMod)
                        Artworks += ((UrlMod,),)

            dbio.DBCloseRW(ServerId, "downloadreset", SQLs)

        dbio.DBCloseRW("video", "downloadreset", SQLs)
        artworkcache.CacheAllEntries(Artworks, None)
        utils.refresh_widgets(True)

    xbmc.log("EMBY.helper.pluginmenu: --<[ reset download ]", 1) # LOGINFO

# Factory reset. wipes all db records etc.
def factoryreset(KeepServerConfig, favoritesObj):
    xbmc.log("EMBY.helper.pluginmenu: [ factory reset ]", 2) # LOGWARNING

    if KeepServerConfig or utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
        utils.SyncPause = {}
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33223), icon=utils.icon, time=960000, sound=True)
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xmls.sources() # verify sources.xml
        xmls.advanced_settings() # verify advancedsettings.xml

        if not KeepServerConfig:
            for EmbyServer in list(utils.EmbyServers.values()):
                EmbyServer.ServerDisconnect()
                EmbyServer.stop()

            utils.delFolder(utils.FolderAddonUserdata, "")

        # remove nodes
        utils.delete_nodes()

        # remove playlists
        utils.delete_playlists()

        # remove favorites
        favoritesObj.set_Favorites(False)

        # delete downloaded content
        utils.delFolder(utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content"))
        utils.delFolder(utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-themes"))

        # Get EmbyServerIds based on config files
        EmbyServerIds = []
        _, files = utils.listDir(utils.FolderAddonUserdata)

        for Filename in files:
            if Filename.startswith('server'):
                EmbyServerIds.append(Filename.replace('servers_', "").replace('.json', ""))

        # delete databases
        delete_database('emby')
        SQLs = {}
        dbio.DBOpenRW("video", "factoryreset", SQLs)
        SQLs["video"].common_db.delete_tables("Video")
        dbio.DBCloseRW("video", "factoryreset", SQLs)
        dbio.DBOpenRW("music", "factoryreset", SQLs)
        SQLs["music"].common_db.delete_tables("Music")
        dbio.DBCloseRW("music", "factoryreset", SQLs)
        xbmc.log("EMBY.helper.pluginmenu: [ complete reset ]", 1) # LOGINFO

        # Re-Init emby databases
        for EmbyServerId in EmbyServerIds:
            utils.DatabaseFiles[EmbyServerId] = utils.translatePath(f"special://profile/Database/emby_{EmbyServerId}.db")
            SQLs = {}
            dbio.DBOpenRW(EmbyServerId, "factoryreset", SQLs)
            SQLs["emby"].init_EmbyDB()
            dbio.DBCloseRW(EmbyServerId, "factoryreset", SQLs)

        # Set configuration as last (Kodi timing issue)
        if KeepServerConfig:
            utils.set_settings('MinimumSetup', "OPENLIBRARY")

        utils.restart_kodi()

def delete_database(Database):
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith(Database):
            utils.delFile(f"special://profile/Database/{Filename}")

# Reset both the emby database and the kodi database.
def databasereset(favoritesObj):
    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
        return

    xbmc.log("EMBY.helper.pluginmenu: [ database reset ]", 1) # LOGINFO
    utils.SyncPause = {}
    DelArtwork = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33086))
    DeleteSettings = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33087))
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    favoritesObj.set_Favorites(False)
    SQLs = {}
    dbio.DBOpenRW("video", "databasereset", SQLs)
    SQLs["video"].common_db.delete_tables("Video")
    dbio.DBCloseRW("video", "databasereset", SQLs)
    dbio.DBOpenRW("music", "databasereset", SQLs)
    SQLs["music"].common_db.delete_tables("Music")
    dbio.DBCloseRW("music", "databasereset", SQLs)

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

    delete_database('emby')
    utils.delete_playlists()
    utils.delete_nodes()
    utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33088))
    utils.restart_kodi()

def DeleteThumbnails():
    xbmc.log("EMBY.helper.pluginmenu: -->[ reset artwork ]", 1) # LOGINFO
    xbmc.executebuiltin('Dialog.Close(addoninformation)')
    ProgressBar = xbmcgui.DialogProgressBG()
    ProgressBar.create(utils.Translate(33199), utils.Translate(33412))
    Folders, _ = utils.listDir('special://thumbnails/')
    TotalFolders = len(Folders)

    for CounterFolder, Folder in enumerate(Folders, 1):
        ProgressBar.update(int(CounterFolder / TotalFolders * 100), utils.Translate(33199), f"{utils.Translate(33412)}: {Folder}")
        _, Files = utils.listDir(f"special://thumbnails/{Folder}")
        TotalFiles = len(Files)

        for CounterFile, File in enumerate(Files, 1):
            ProgressBar.update(int(CounterFile / TotalFiles * 100), utils.Translate(33199), f"{utils.Translate(33412)}: {Folder}{File}")
            xbmc.log(f"EMBY.helper.pluginmenu: DELETE thumbnail {File}", 0) # LOGDEBUG
            utils.delFile(f"special://thumbnails/{Folder}{File}")

    SQLs = {}
    dbio.DBOpenRW("texture", "cache_textures", SQLs)
    SQLs["texture"].common_db.delete_tables("Texture")
    dbio.DBCloseRW("texture", "cache_textures", SQLs)
    ProgressBar.close()
    del ProgressBar
    xbmc.log("EMBY.helper.pluginmenu: --<[ reset artwork ]", 1) # LOGINFO

def add_ViewItems(Handle, QueryContent, Content, ItemsListings, Unsorted):
    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems", 0) # LOGDEBUG

    if not xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings)):
        xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems FAIL", 3) # LOGERROR
#        xbmc.executebuiltin('ReloadSkin()')
        return

    # Set Sorting
    xbmc.log(f"EMBY.helper.pluginmenu: Dynamic nodes: addSortMethod {QueryContent} / {Content}", 0) # LOGDEBUG
    ContentType = None

    if Unsorted:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)

    for ContentType in (QueryContent, Content):
        if ContentType in ('Folder', "TvChannel", "All", "homevideos"):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
            break

        if ContentType in ('Photo', 'PhotoAlbum'):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
            break

        if ContentType in ('Audio', 'MusicVideo', "musicvideos"):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            break

        if ContentType == 'MusicAlbum':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ALBUM_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            break

        if ContentType in ('MusicArtist', "VideoMusicArtist"):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_ARTIST_IGNORE_THE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            break

        if ContentType in ('Movie', 'Video', 'Series', "tvshows"):
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            break

        if ContentType == 'Season':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            break

        if ContentType == 'Episode':
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_EPISODE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_GENRE)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
            break
    else:
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_LABEL)
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)

    if ContentType and ContentType in MappingContentKodi:
        xbmcplugin.setContent(Handle, MappingContentKodi[ContentType])

    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: endOfDirectory", 0) # LOGDEBUG
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

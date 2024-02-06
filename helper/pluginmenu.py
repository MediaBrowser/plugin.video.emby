from urllib.parse import urlencode
import xbmc
import xbmcgui
import xbmcplugin
from database import dbio
from emby import listitem
from core import common
from . import utils, playerops, xmls, artworkcache

SearchTerm = ""
QueryCache = {}
MappingStaggered = {"Series": "Season", "Season": "Episode", "PhotoAlbum": "HomeVideos", "MusicAlbum": "Audio"} # additional stagged content parameter written in the code, based on conditions
letters = ("0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z")
MappingContentKodi = {"movies": "movies", "Video": "videos", "Season": "tvshows", "Episode": "episodes", "Series": "tvshows", "Movie": "movies", "Photo": "images", "PhotoAlbum": "images", "MusicVideo": "musicvideos", "MusicArtist": "artists", "MusicAlbum": "albums", "Audio": "songs", "TvChannel": "videos", "musicvideos": "musicvideos", "VideoMusicArtist": "musicvideos", "tvshows": "tvshows", "Folder": "files", "All": "files", "homevideos": "files", "Playlist": "files", "Trailer": "videos", "Person": "videos", "videos": "videos", "music": "songs"}
Subcontent = {"tvshows": ("Series", "Season", "Episode", "Genre", "BoxSet"), "movies": ("Movie", "Genre", "BoxSet"), "music": ("MusicArtist", "MusicAlbum", "MusicGenre", "BoxSet", "Audio"), "musicvideos": ("MusicArtist", "MusicGenre", "BoxSet"), "homevideos": ("Photo", "PhotoAlbum", "Video"), "videos": ("Series", "Season", "Episode", "Genre", "BoxSet", "Movie", "Video", "Person")}
IconMapping = {"MusicArtist": "DefaultMusicArtists.png", "MusicAlbum": "DefaultMusicAlbums.png", "Audio": "DefaultMusicSongs.png", "Movie": "DefaultMovies.png", "Trailer": "DefaultAddonVideo.png", "BoxSet": "DefaultSets.png", "Series": "DefaultTVShows.png", "Season": "DefaultTVShowTitle.png", "Episode": "DefaultAddonVideo.png", "MusicVideo": "DefaultMusicVideos.png", "Video": "DefaultAddonVideo.png", "Photo": "DefaultPicture.png.png", "PhotoAlbum": "DefaultAddonPicture.png", "TvChannel": "DefaultAddonPVRClient.png", "Folder": "DefaultFolder.png", "Playlist": "DefaultPlaylist.png", "Genre": "DefaultGenre.png", "MusicGenre": "DefaultMusicGenres.png", "Person": "DefaultActor.png", "Tag": "DefaultTags.png", "Channel": "DefaultFolder.png", "CollectionFolder": "DefaultFolder.png", "Studio": "DefaultStudios.png"}

# Build plugin menu
def listing(Handle):
    ItemsListings = ()
    Handle = int(Handle)

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        ItemsListings = add_ListItem(ItemsListings, f"{utils.Translate(33386)} ({EmbyServer.ServerData['ServerName']})", f"plugin://plugin.video.emby-next-gen/?mode=browse&query=NodesSynced&server={ServerId}", True, "DefaultHardDisk.png", utils.Translate(33383))
        ItemsListings = add_ListItem(ItemsListings, f"{utils.Translate(33387)} ({EmbyServer.ServerData['ServerName']})", f"plugin://plugin.video.emby-next-gen/?mode=browse&query=NodesDynamic&server={ServerId}", True, "DefaultNetwork.png", utils.Translate(33384))

    # Common Items
    if utils.menuOptions:
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33194), "plugin://plugin.video.emby-next-gen/?mode=managelibsselection", False, "DefaultAddSource.png", utils.Translate(33309))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33059), "plugin://plugin.video.emby-next-gen/?mode=texturecache", False, "DefaultAddonImages.png", utils.Translate(33310))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(5), "plugin://plugin.video.emby-next-gen/?mode=settings", False, "DefaultAddon.png", utils.Translate(33398))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33058), "plugin://plugin.video.emby-next-gen/?mode=databasereset", False, "DefaultAddonsUpdates.png", utils.Translate(33313))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33340), "plugin://plugin.video.emby-next-gen/?mode=factoryreset", False, "DefaultAddonsUpdates.png", utils.Translate(33400))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33341), "plugin://plugin.video.emby-next-gen/?mode=nodesreset", False, "DefaultAddonsUpdates.png", utils.Translate(33401))
        ItemsListings = add_ListItem(ItemsListings, utils.Translate(33409), "plugin://plugin.video.emby-next-gen/?mode=skinreload", False, "DefaultAddonSkin.png", "")

    xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Browse dynamically content
def browse(Handle, Id, query, ParentId, Content, ServerId, LibraryId):
    Handle = int(Handle)
    WindowId = xbmcgui.getCurrentWindowId()
    xbmc.log(f"EMBY.helper.pluginmenu: Browse: Id: {Id} / Query: {query} / ParentId: {ParentId} / LibraryId: {LibraryId} / Content: {Content} / WindowId: {WindowId} / ServerId: {ServerId}", 1) # LOGINFO
    ItemsListings = ()
#    xbmc.executebuiltin('Dialog.Close(busydialog,true)')

    # Limit number of nodes for widget queries
    if WindowId not in (10502, 10025, 10002):
        Extras = {"Limit": utils.maxnodeitems}
        CacheId = f"{Id}{query}{ParentId}{ServerId}{LibraryId}{utils.maxnodeitems}"
    else:
        Extras = {}
        CacheId = f"{Id}{query}{ParentId}{ServerId}{LibraryId}"

    if ServerId not in utils.EmbyServers:
        xbmc.log(f"EMBY.helper.pluginmenu: Pluginmenu invalid server id: {ServerId}", 3) # LOGERROR
        return

    ContentQuery = Content

    # Load from cache
    if Content in QueryCache and CacheId in QueryCache[Content] and QueryCache[Content][CacheId][0]:
        if reload_Window(Content, ContentQuery, WindowId, Handle, QueryCache[Content][CacheId][3], QueryCache[Content][CacheId][4], QueryCache[Content][CacheId][5], QueryCache[Content][CacheId][6], QueryCache[Content][CacheId][7]):
            return

        add_ViewItems(Handle, query, Content, QueryCache[Content][CacheId][1], QueryCache[Content][CacheId][2])
        return

    if query in ('NodesDynamic', 'NodesSynced'):
        for Node in utils.EmbyServers[ServerId].Views.Nodes[query]:
            ItemsListings = add_ListItem(ItemsListings, Node['title'], Node['path'], True, Node['icon'], "")

        xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings))
        xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)
        return

    Unsorted = False
    EmbyContentQuery = ()

    if query == 'Letter':
        if Content in ('VideoMusicArtist', 'MusicArtist'):
            LocalContent = 'MusicArtist'
            LocalParentId = ParentId
        elif Content == "Playlist":
            LocalParentId = None
            LocalContent = Content
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
        Unsorted = True
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
        for Item in utils.EmbyServers[ServerId].API.get_recommendations(ParentId):
            ItemsListings = load_ListItem(ParentId, Item, ServerId, ItemsListings, Content, LibraryId)
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
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (ParentId, ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video"], True, Extras, False, LibraryId)
        Unsorted = True
    elif query == "Playlists":
        Extras.update({"SortBy": "SortName"})
        EmbyContentQuery = (None, ["Playlist"], True, Extras, False, LibraryId)
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
        EmbyContentQuery = (ParentId, ["Photo", "PhotoAlbum", "Video"], False, Extras, False, LibraryId)
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
        for Item in utils.EmbyServers[ServerId].API.get_Items_dynamic(*EmbyContentQuery):
            if utils.SystemShutdown:
                return

            if Item['Type'] in SortItems:
                SortItems[Item['Type']] += (Item,)
            else:
                xbmc.log(f"EMBY.helper.pluginmenu: Invalid content: {Item['Type']}", 3) # LOGERROR

        TypeCounter = 0

        for SortItemContent, SortedItems in list(SortItems.items()):
            if SortedItems and SortItemContent != "Folder":
                TypeCounter += 1

                if TypeCounter == 2: # multiple content types detected
                    break

        if TypeCounter == 2:
            for SortItemContent, SortedItems in list(SortItems.items()):
                if not SortedItems:
                    continue

                if SortItemContent not in QueryCache:
                    globals()["QueryCache"][SortItemContent] = {}

                ItemsListingsCached = ()

                for SortedItem in SortedItems:
                    ItemsListingsCached = load_ListItem(ParentId, SortedItem, ServerId, ItemsListingsCached, Content, LibraryId)

                globals()["QueryCache"][SortItemContent][f"{Id}{SortItemContent}{ParentId}{ServerId}{LibraryId}"] = [True, ItemsListingsCached, Unsorted, Id, SortItemContent, ServerId, ParentId, LibraryId]
                ItemsListings = add_ListItem(ItemsListings, SortItemContent, f"plugin://plugin.video.emby-next-gen/?id={Id}&mode=browse&query={SortItemContent}&server={ServerId}&parentid={ParentId}&content={SortItemContent}&libraryid={LibraryId}", True, IconMapping[SortItemContent], SortItemContent)
        else: # unique content
            for SortItemContent, SortedItems in list(SortItems.items()):
                if SortedItems:
                    if SortItemContent not in ("Genre", "MusicGenre", "Tag"): # Skip subqueries
                        Content = SortItemContent

                    for SortedItem in SortedItems:
                        ItemsListings = load_ListItem(ParentId, SortedItem, ServerId, ItemsListings, Content, LibraryId)

                    break

    if ContentQuery not in QueryCache:
        globals()["QueryCache"][ContentQuery] = {}

    globals()["QueryCache"][ContentQuery][CacheId] = [True, ItemsListings, Unsorted, Id, query, ServerId, ParentId, LibraryId]

    if reload_Window(Content, ContentQuery, WindowId, Handle, Id, query, ServerId, ParentId, LibraryId):
        return

    add_ViewItems(Handle, query, Content, ItemsListings, Unsorted)

# Workaround for invalid window query
# check if video or music navigation window is open (MyVideoNav.xml MyMusicNav.xml) -> open MyPics.xml etc 10502 = music, 10025 = videos, 10002 = pictures
def reload_Window(Content, ContentQuery, WindowId, Handle, Id, query, ServerId, ParentId, LibraryId):
    if utils.SyncPause.get('kodi_rw', False): # skip if scan is in progress
        return False

    ReloadWindowId = ""

    if Content in ("Photo", "PhotoAlbum") and WindowId in (10502, 10025):
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
        utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "{ReloadWindowId}", "parameters": ["plugin://plugin.video.emby-next-gen/?id={Id}&mode=browse&query={query}&server={ServerId}&parentid={ParentId}&content={ContentQuery}&libraryid={LibraryId}", "return"]}}}}')
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
            ItemsListings += ((f"plugin://plugin.video.emby-next-gen/?{urlencode(params)}", ListItem, True),)
        else:
            path, _ = common.get_path_type_from_item(ServerId, Item)
            ItemsListings += ((path, ListItem, False),)

    return ItemsListings

#Menu structure nodes
def add_ListItem(ItemsListings, label, path, isFolder, artwork, HelpText):
    ListItem = xbmcgui.ListItem(label, HelpText, path, True)
    ListItem.setContentLookup(False)
    ListItem.setProperties({'IsFolder': 'true', 'IsPlayable': 'false'})
    ListItem.setArt({"thumb": artwork, "fanart": "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "landscape": artwork or "special://home/addons/plugin.video.emby-next-gen/resources/fanart.jpg", "banner": "special://home/addons/plugin.video.emby-next-gen/resources/banner.png", "clearlogo": "special://home/addons/plugin.video.emby-next-gen/resources/clearlogo.png", "icon": artwork})
    ItemsListings += ((path, ListItem, isFolder),)
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
    MenuItems = ["Add Server", "Remove Server", "Add User"]
    Selection = utils.Dialog.select("Server ops", MenuItems) # Manage libraries

    if Selection == 0:
        ServerConnect(None)
    elif Selection == 1:
        _, ServerIds, ServerItems = get_EmbyServerList()
        Selection = utils.Dialog.select(utils.Translate(33431), ServerItems)

        if Selection > -1:
            xbmc.executebuiltin('Dialog.Close(addoninformation)')
            utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33448)}: {utils.EmbyServers[ServerIds[Selection]].ServerData['ServerName']}", icon=utils.icon, time=1500, sound=False)
            SQLs = dbio.DBOpenRW(ServerIds[Selection], "remove_emby_server", {})

            for LibraryId in utils.EmbyServers[ServerIds[Selection]].library.WhitelistUnique:
                SQLs["emby"].remove_library_items(LibraryId)
                SQLs["emby"].add_RemoveItem("library", LibraryId)

            SQLs["emby"].add_RemoveItem("library", "999999999")
            SQLs["emby"].remove_library_items_person()
            dbio.DBCloseRW(ServerIds[Selection], "remove_emby_server", SQLs)
            utils.EmbyServers[ServerIds[Selection]].library.RunJobs()

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

# Special favorite synced node
def favepisodes(Handle):
    Handle = int(Handle)
    CacheId = "favepisodes"

    if "Episode" not in QueryCache:
        globals()["QueryCache"]["Episode"] = {}

    if CacheId in QueryCache["Episode"] and QueryCache["Episode"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["Episode"][CacheId][1]
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
                globals()["QueryCache"]["Episode"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def favseasons(Handle):
    Handle = int(Handle)
    CacheId = "favseasons"

    if "Season" not in QueryCache:
        globals()["QueryCache"]["Season"] = {}

    if CacheId in QueryCache["Season"] and QueryCache["Season"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["Season"][CacheId][1]
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
                globals()["QueryCache"]["Season"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_TITLE)
    xbmcplugin.setContent(Handle, 'tvshows')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

# Special collection synced node
def collections(Handle, KodiMediaType, LibraryTag):
    if "BoxSet" not in QueryCache:
        globals()["QueryCache"]["BoxSet"] = {}

    Handle = int(Handle)
    CacheId = f"collections_{LibraryTag}_{KodiMediaType}"

    if CacheId in QueryCache["BoxSet"] and QueryCache["BoxSet"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["BoxSet"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        videodb = dbio.DBOpenRO("video", "collections")
        CollectionTagIds, CollectionNames = videodb.get_collection_tags(LibraryTag, KodiMediaType)
        dbio.DBCloseRO("video", "collections")

        for Index, CollectionTagId in enumerate(CollectionTagIds):
            ListItem = xbmcgui.ListItem(label=CollectionNames[Index], offscreen=True, path=f"videodb://{KodiMediaType}s/tags/{CollectionTagId}/")
            ListItem.setContentLookup(False)
            ListItems += ((f"videodb://{KodiMediaType}s/tags/{CollectionTagId}/", ListItem, True),)

        globals()["QueryCache"]["BoxSet"][CacheId] = [True, ListItems]

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
    choices = [utils.Translate(33121), "Movies", "TVShows", "Season", "Episode", "Musicvideos", "Album", "Song", "Boxsets", "Actor", "Artist", "Bookmarks", "Photoalbum", "Photos"]
    selection = utils.Dialog.multiselect(utils.Translate(33256), choices)

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

                for Item in EmbyServer.API.get_Items(None, ["PhotoAlbum"], True, True, {}):
                    path, _ = common.get_path_type_from_item(ServerId, Item)
                    TempUrls[ItemCounter] = (path,)
                    ItemCounter += 1

                yield TempUrls

            if 0 in selection or 13 in selection: # Photo
                TotalRecords = EmbyServer.API.get_TotalRecords(None, "Photo", {})
                TempUrls = TotalRecords * [()]
                ItemCounter = 0

                for Item in EmbyServer.API.get_Items(None, ["Photo"], True, True, {}):
                    path, _ = common.get_path_type_from_item(ServerId, Item)
                    TempUrls[ItemCounter] = (path,)
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

def reset_querycache(Content):
    if not playerops.RemoteMode: # keep cache in remote client mode -> don't overload Emby server
        for CacheContent, CachedItems in list(QueryCache.items()):
            if CacheContent == Content or not Content or CacheContent == "All":
                xbmc.log(f"EMBY.helper.pluginmenu: Clear QueryCache: {CacheContent}", 1) # LOGINFO

                for CachedContentItems in list(CachedItems.values()):
                    if len(CachedContentItems) == 8 and CachedContentItems[7] != "0": # CachedItems[7] = LibraryId -> LibraryId = 0 means search content -> skip
                        CachedContentItems[0] = False

def get_next_episodes(Handle, libraryname):
    if "Episode" not in QueryCache:
        globals()["QueryCache"]["Episode"] = {}

    Handle = int(Handle)
    CacheId = f"next_episodes_{libraryname}"

    if CacheId in QueryCache["Episode"] and QueryCache["Episode"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["Episode"][CacheId][1]
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
                globals()["QueryCache"]["Episode"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'episodes')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def get_inprogress_mixed(Handle):
    if "All" not in QueryCache:
        globals()["QueryCache"]["All"] = {}

    Handle = int(Handle)
    CacheId = "inprogress_mixed"

    if CacheId in QueryCache["All"] and QueryCache["All"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["All"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_inprogress_mixed")
        InProgressInfos = videodb.get_inprogress_mixedIds(True)

        for InProgressInfo in InProgressInfos:
            KodiItem = InProgressInfo.split(";")

            if KodiItem[2] == "Movie":
                KodiItems += (videodb.get_movie_metadata_for_listitem(KodiItem[1], None),)
            elif KodiItem[2] == "Episode":
                KodiItems += (videodb.get_episode_metadata_for_listitem(KodiItem[1], None),)
            else:
                KodiItems += (videodb.get_musicvideos_metadata_for_listitem(KodiItem[1], None),)

        dbio.DBCloseRO("video", "get_inprogress_mixed")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)
                globals()["QueryCache"]["All"][CacheId] = [True, ListItems]

    xbmcplugin.addDirectoryItems(Handle, ListItems, len(ListItems))
    xbmcplugin.addSortMethod(Handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.setContent(Handle, 'videos')
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

def get_continue_watching(Handle):
    if "All" not in QueryCache:
        globals()["QueryCache"]["All"] = {}

    Handle = int(Handle)
    CacheId = "continue_watching"

    if CacheId in QueryCache["All"] and QueryCache["All"][CacheId][0]:
        xbmc.log(f"EMBY.helper.pluginmenu: Using QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = QueryCache["All"][CacheId][1]
    else:
        xbmc.log(f"EMBY.helper.pluginmenu: Rebuid QueryCache: {CacheId}", 1) # LOGINFO
        ListItems = ()
        KodiItems = ()
        videodb = dbio.DBOpenRO("video", "get_continue_watching")
        ContinueWatchingInfos = videodb.get_continue_watchingIds()

        for ContinueWatchingInfo in ContinueWatchingInfos:
            KodiItem = ContinueWatchingInfo.split(";")

            if len(KodiItem) == 3 and KodiItem[2] == "Movie":
                KodiItems += (videodb.get_movie_metadata_for_listitem(KodiItem[1], None),)
            else:
                KodiItems += (videodb.get_episode_metadata_for_listitem(KodiItem[1], None),)

        dbio.DBCloseRO("video", "get_continue_watching")

        for KodiItem in KodiItems:
            if KodiItem:
                isFolder, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem)
                ListItems += ((KodiItem['pathandfilename'], ListItem, isFolder),)
                globals()["QueryCache"]["All"][CacheId] = [True, ListItems]

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
        SQLs = dbio.DBOpenRW("video", "downloadreset", {})
        Artworks = ()

        for ServerId in utils.EmbyServers:
            SQLs = dbio.DBOpenRW(ServerId, "downloadreset", SQLs)

            for Item in SQLs['emby'].get_DownloadItem():
                SQLs['video'].replace_PathId(Item[2], Item[1])
                SQLs['emby'].delete_DownloadItem(Item[0])
                ArtworksData = SQLs['video'].get_artworks(Item[3], Item[4])

                for ArtworkData in ArtworksData:
                    if ArtworkData[3] in ("poster", "thumb", "landscape"):
                        UrlMod = ArtworkData[4].replace("-download", "")
                        SQLs['video'].update_artwork(ArtworkData[0], UrlMod)
                        Artworks += ((UrlMod,),)

            SQLs = dbio.DBCloseRW(ServerId, "downloadreset", SQLs)

        dbio.DBCloseRW("video", "downloadreset", {})
        artworkcache.CacheAllEntries(Artworks, None)
        utils.refresh_widgets(True)

    xbmc.log("EMBY.helper.pluginmenu: --<[ reset download ]", 1) # LOGINFO

# Factory reset. wipes all db records etc.
def factoryreset():
    xbmc.log("EMBY.helper.pluginmenu: [ factory reset ]", 2) # LOGWARNING

    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33074)):
        utils.SyncPause = {}
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33223), icon=utils.icon, time=960000, sound=True)
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xmls.sources() # verify sources.xml
        xmls.advanced_settings() # verify advancedsettings.xml

        for EmbyServer in list(utils.EmbyServers.values()):
            EmbyServer.ServerDisconnect()
            EmbyServer.stop()

        utils.delFolder(utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content"))
        utils.delFolder(utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-themes"))
        utils.delFolder(utils.FolderAddonUserdata)
        utils.delete_playlists()
        utils.delete_nodes()

        # delete databases
        delete_database('emby')
        SQLs = dbio.DBOpenRW("video", "databasereset", {})
        SQLs["video"].common_db.delete_tables("Video")
        dbio.DBCloseRW("video", "databasereset", {})
        SQLs = dbio.DBOpenRW("music", "databasereset", {})
        SQLs["music"].common_db.delete_tables("Music")
        dbio.DBCloseRW("music", "databasereset", {})
        DeleteThumbnails()
        Filepath = 'special://profile/favourites.xml'

        if utils.checkFileExists(Filepath):
            utils.delFile(Filepath)

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
    SQLs = dbio.DBOpenRW("video", "databasereset", {})
    SQLs["video"].common_db.delete_tables("Video")
    dbio.DBCloseRW("video", "databasereset", {})
    SQLs = dbio.DBOpenRW("music", "databasereset", {})
    SQLs["music"].common_db.delete_tables("Music")
    dbio.DBCloseRW("music", "databasereset", {})

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
    # remove favourites
    Filepath = 'special://profile/favourites.xml'

    if utils.checkFileExists(Filepath):
        utils.delFile(Filepath)

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

    SQLs = dbio.DBOpenRW("texture", "cache_textures", {})
    SQLs["texture"].common_db.delete_tables("Texture")
    dbio.DBCloseRW("texture", "cache_textures", {})
    ProgressBar.close()
    del ProgressBar
    xbmc.log("EMBY.helper.pluginmenu: --<[ reset artwork ]", 1) # LOGINFO

def add_ViewItems(Handle, QueryContent, Content, ItemsListings, Unsorted):
    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems", 1) # LOGINFO

    if not xbmcplugin.addDirectoryItems(Handle, ItemsListings, len(ItemsListings)):
        xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: addDirectoryItems FAIL", 3) # LOGERROR
        xbmc.executebuiltin('ReloadSkin()')
        return

    # Set Sorting
    xbmc.log(f"EMBY.helper.pluginmenu: Dynamic nodes: addSortMethod {QueryContent} / {Content}", 1) # LOGINFO

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

    if ContentType in MappingContentKodi:
        xbmcplugin.setContent(Handle, MappingContentKodi[ContentType])

    xbmc.log("EMBY.helper.pluginmenu: Dynamic nodes: endOfDirectory", 1) # LOGINFO
    xbmcplugin.endOfDirectory(Handle, cacheToDisc=False)

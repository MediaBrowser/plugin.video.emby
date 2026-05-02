import xbmc
from helper import utils
from . import common

class Genre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Genre"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.genre (DEBUG): Process item: {Item['Name']}", 1) # DEBUG
        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_genre(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_genre(Item['Id'], Item['KodiArtwork']['favourite'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.gerne: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.gerne (DEBUG): UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "genre"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_genre(Item['Name'])
            self.SQLs["emby"].add_reference_genre(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiArtwork']['favourite'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.gerne: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.gerne (DEBUG): ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "genre"}, IncrementalSync)

        common.download_SubnodeIcon(Item, self.EmbyServer.ServerData['ServerId']) # Download icon
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Delete = self.SQLs["emby"].remove_item(Item['Id'], "Genre", Item['LibraryId'])

        if Delete:
            if not common.verify_KodiIds(Item, IncrementalSync, False):
                return

            self.set_favorite(False, Item)
            GenreName = self.SQLs["video"].delete_genre_by_Id(Item['KodiItemId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.genre: DELETE {GenreName}: [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.genre (DEBUG): DELETE {GenreName}: [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

            self.EmbyServer.Views.remove_synced_subnode(Item['Id'], Item['LibraryId'], "Genre", GenreName) # Delete genre xml node
            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "genre"}, IncrementalSync)

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Genre")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "genre"}, True)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.genre: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.genre (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite']:
            Item['KodiArtwork']['favourite'] = self.SQLs["emby"].get_item_by_id(Item['Id'], "Genre")[3]

        Item['Name'], _, hasMovies, hasTVShows = self.SQLs["video"].get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(Item['KodiItemId'])

        if not Item['Name']:
            xbmc.log(f"EMBY.core.genre: set_favorite, item not found {Item['KodiItemId']}", 2) # LOGWARNING
            return

        if hasMovies or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://movies/genres/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasTVShows or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/genres/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

import xbmc
from helper import utils
from . import common

class Genre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Genre"):
            return False

        xbmc.log(f"EMBY.core.genre: Process item: {Item['Name']}", 0) # DEBUG
        isFavorite = common.set_Favorite(Item)
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_genre(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_genre(Item['Id'], isFavorite, ImageUrl, Item['LibraryId'])
            xbmc.log(f"EMBY.core.gerne: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "genre"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_genre(Item['Name'])
            self.SQLs["emby"].add_reference_genre(Item['Id'], Item['LibraryId'], Item['KodiItemId'], isFavorite, ImageUrl)
            xbmc.log(f"EMBY.core.gerne: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "genre"}, IncrementalSync)

        self.set_favorite(isFavorite, Item['KodiItemId'], ImageUrl, Item['Id'])
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        if self.SQLs["emby"].remove_item(Item['Id'], "Genre", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'], "", Item['Id'])
            self.SQLs["video"].delete_genre_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.genre: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "genre"}, IncrementalSync)

    def userdata(self, Item):
        ImageUrl = ""

        if Item['IsFavorite']:
            ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "Genre")[3]

        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], ImageUrl, Item['Id'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Genre")
        utils.reset_querycache("Genre")
        xbmc.log(f"EMBY.core.genre: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "genre"}, True)
        return False

    def set_favorite(self, isFavorite, KodiItemId, ImageUrl, EmbyItemId):
        Name, _, hasMovies, hasTVShows = self.SQLs["video"].get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(KodiItemId)

        if not Name:
            xbmc.log(f"EMBY.core.genre: set_favorite, item not found {KodiItemId}", 2) # LOGWARNING
            return

        if hasMovies or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Movies", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://movies/genres/{KodiItemId}/", Name, "window", 10025),))

        if hasTVShows or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "TV Shows", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://tvshows/genres/{KodiItemId}/", Name, "window", 10025),))

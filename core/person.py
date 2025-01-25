import xbmc
from helper import utils
from . import common

class Person:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        Item['LibraryId'] = "999999999"

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Person"):
            return False

        xbmc.log(f"EMBY.core.person: Process item: {Item['Name']}", 0) # DEBUG
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])
        isFavorite = common.set_Favorite(Item)
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

        if Item['KodiItemId']: # existing item
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "actor")
            self.SQLs["video"].update_person(Item['KodiItemId'], Item['Name'], ImageUrl)
            self.SQLs["emby"].update_favourite(isFavorite, Item['Id'], "Person")
            xbmc.log(f"EMBY.core.person: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "actor"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].add_person(Item['Name'], ImageUrl)
            self.SQLs["emby"].add_reference_metadata(Item['Id'], Item['LibraryId'], "Person", Item['KodiItemId'], isFavorite)
            xbmc.log(f"EMBY.core.person: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "actor"}, IncrementalSync)

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "actor")
        self.set_favorite(Item['KodiItemId'], isFavorite, Item['Id'])
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        if self.SQLs["emby"].remove_item(Item['Id'], "Person", Item['LibraryId']):
            self.set_favorite(Item['KodiItemId'], False, Item['Id'])
            self.SQLs["video"].delete_people_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.person: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "actor"}, IncrementalSync)

    def userdata(self, Item):
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Person")
        self.set_favorite(Item['KodiItemId'], Item['IsFavorite'], Item['Id'])
        utils.reset_querycache("Person")
        xbmc.log(f"EMBY.core.person: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "actor"}, True)
        return False

    def set_favorite(self, KodiItemId, isFavorite, EmbyItemId):
        Name, ImageUrl, hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_People(KodiItemId)

        if not Name:
            xbmc.log(f"EMBY.core.person: set_favorite, item not found {KodiItemId}", 2) # LOGWARNING
            return

        if hasMovies or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Movies", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://movies/actors/{KodiItemId}/", Name, "window", 10025),))

        if hasTVShows or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "TV Shows", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://tvshows/actors/{KodiItemId}/", Name, "window", 10025),))

        if hasMusicVideos or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Musicvideos", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://musicvideos/actors/{KodiItemId}/", Name, "window", 10025),))

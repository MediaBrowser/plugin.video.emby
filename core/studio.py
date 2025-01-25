import xbmc
from helper import utils
from . import common

class Studio:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Studio"):
            return False

        xbmc.log(f"EMBY.core.studio: Process item: {Item['Name']}", 0) # DEBUG
        isFavorite = common.set_Favorite(Item)
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_studio(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_studio(Item['Id'], isFavorite, ImageUrl, Item['LibraryId'])
            xbmc.log(f"EMBY.core.studio: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "studio"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_studio(Item['Name'])
            self.SQLs["emby"].add_reference_studio(Item['Id'], Item['LibraryId'], Item['KodiItemId'], isFavorite, ImageUrl)
            xbmc.log(f"EMBY.core.studio: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "studio"}, IncrementalSync)

        self.set_favorite(isFavorite, Item['KodiItemId'], ImageUrl, Item['Id'])
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        if self.SQLs["emby"].remove_item(Item['Id'], "Studio", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'], "", Item['Id'])
            self.SQLs["video"].delete_studio_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.studio: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "studio"}, IncrementalSync)

    def userdata(self, Item):
        ImageUrl = ""

        if Item['IsFavorite']:
            ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "Studio")[3]

        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], ImageUrl, Item['Id'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Studio")
        utils.reset_querycache("Studio")
        xbmc.log(f"EMBY.core.sudio: USERDATA studio [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "studio"}, True)
        return False

    def set_favorite(self, isFavorite, KodiItemId, ImageUrl, EmbyItemId):
        Name, hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_Studio_Name(KodiItemId)

        if not Name:
            xbmc.log(f"EMBY.core.sudio: set_favorite, item not found {KodiItemId}", 2) # LOGWARNING
            return

        if hasMovies or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Movies", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://movies/studios/{KodiItemId}/", Name, "window", 10025),))

        if hasTVShows or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "TV Shows", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://tvshows/studios/{KodiItemId}/", Name, "window", 10025),))

        if hasMusicVideos or not isFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Musicvideos", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://musicvideos/studios/{KodiItemId}/", Name, "window", 10025),))

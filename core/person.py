import xbmc
from helper import pluginmenu, utils
from . import common

class Person:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item):
        Item['LibraryId'] = "999999999"
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Person")
        xbmc.log(f"EMBY.core.person: Process item: {Item['Name']}", 0) # DEBUG
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])
        isFavorite = common.set_Favorite(Item)
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

        if Item['KodiItemId']: # existing item
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "actor")
            self.SQLs["video"].update_person(Item['KodiItemId'], Item['Name'], ImageUrl)
            self.SQLs["emby"].update_favourite(isFavorite, Item['Id'], "Person")
            xbmc.log(f"EMBY.core.person: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
        else:
            Item['KodiItemId'] = self.SQLs["video"].add_person(Item['Name'], ImageUrl)
            self.SQLs["emby"].add_reference_metadata(Item['Id'], Item['LibraryId'], "Person", Item['KodiItemId'], isFavorite)
            xbmc.log(f"EMBY.core.person: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "actor")
        self.set_favorite(Item['KodiItemId'], isFavorite)
        return not Item['UpdateItem']

    def remove(self, Item):
        if self.SQLs["emby"].remove_item(Item['Id'], "Person", Item['LibraryId']):
            self.set_favorite(Item['KodiItemId'], False)
            self.SQLs["video"].delete_people_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.person: DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Person")
        self.set_favorite(Item['KodiItemId'], Item['IsFavorite'])
        pluginmenu.reset_querycache("Person")
        xbmc.log(f"EMBY.core.person: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def set_favorite(self, KodiItemId, isFavorite):
        Name, ImageUrl, hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_People(KodiItemId)

        if hasMovies:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://movies/actors/{KodiItemId}/", f"{Name} (Movies)", "window", 10025),))

        if hasTVShows:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://tvshows/actors/{KodiItemId}/", f"{Name} (TVShows)", "window", 10025),))

        if hasMusicVideos:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://musicvideos/actors/{KodiItemId}/", f"{Name} (Musicvideos)", "window", 10025),))

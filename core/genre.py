import xbmc
from helper import pluginmenu, utils
from . import common

class Genre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item):
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Genre")
        xbmc.log(f"EMBY.core.genre: Process item: {Item['Name']}", 0) # DEBUG
        isFavorite = common.set_Favorite(Item)
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if int(Item['Id']) > 999999900: # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_genre(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_genre(Item['Id'], isFavorite, ImageUrl, Item['LibraryId'])
            xbmc.log(f"EMBY.core.gerne: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_genre(Item['Name'])
            self.SQLs["emby"].add_reference_genre(Item['Id'], Item['LibraryId'], Item['KodiItemId'], isFavorite, ImageUrl)
            xbmc.log(f"EMBY.core.gerne: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        self.set_favorite(isFavorite, Item['KodiItemId'], ImageUrl)
        return not Item['UpdateItem']

    def remove(self, Item):
        if self.SQLs["emby"].remove_item(Item['Id'], "Genre", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'], "")
            self.SQLs["video"].delete_genre_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.genre: DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        ImageUrl = ""

        if Item['IsFavorite']:
            ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "Genre")[3]

        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], ImageUrl)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Genre")
        pluginmenu.reset_querycache("Genre")
        xbmc.log(f"EMBY.core.genre: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def set_favorite(self, isFavorite, KodiItemId, ImageUrl):
        Name, hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_Genre_Name(KodiItemId)

        if hasMovies:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://movies/genres/{KodiItemId}/", f"{Name} (Movies)", "window", 10025),))

        if hasTVShows:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://tvshows/genres/{KodiItemId}/", f"{Name} (TVShows)", "window", 10025),))

        if hasMusicVideos:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://musicvideos/genres/{KodiItemId}/", f"{Name} (Musicvideos)", "window", 10025),))

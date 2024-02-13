import xbmc
from helper import pluginmenu, utils
from . import common

class Tag:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item):
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Tag")
        xbmc.log(f"EMBY.core.tag: Process item: {Item['Name']}", 0) # DEBUG
        isFavorite = common.set_Favorite(Item)
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if int(Item['Id']) > 999999900: # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_tag(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_tag(Item['Id'], isFavorite, Item.get('Memo', None), ImageUrl, Item['LibraryId'])
            xbmc.log(f"EMBY.core.tag: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_tag(Item['Name'])
            self.SQLs["emby"].add_reference_tag(Item['Id'], Item['LibraryId'], Item['KodiItemId'], isFavorite, Item.get('Memo', None), ImageUrl)
            xbmc.log(f"EMBY.core.tag: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        self.set_favorite(isFavorite, Item['KodiItemId'], ImageUrl)
        return not Item['UpdateItem']

    def remove(self, Item):
        if self.SQLs["emby"].remove_item(Item['Id'], "Tag", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'], "")
            self.SQLs["video"].delete_tag_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.tag: DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        ImageUrl = ""

        if Item['IsFavorite']:
            ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "Tag")[4]

        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], ImageUrl)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Tag")
        pluginmenu.reset_querycache("Tag")
        xbmc.log(f"EMBY.core.tag: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def set_favorite(self, isFavorite, KodiItemId, ImageUrl):
        Name, hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_Tag_Name(KodiItemId)

        if hasMovies or not isFavorite:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://movies/tags/{KodiItemId}/", f"{Name} (Movies)", "window", 10025),))

        if hasTVShows or not isFavorite:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://tvshows/tags/{KodiItemId}/", f"{Name} (TVShows)", "window", 10025),))

        if hasMusicVideos or not isFavorite:
            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://musicvideos/tags/{KodiItemId}/", f"{Name} (Musicvideos)", "window", 10025),))

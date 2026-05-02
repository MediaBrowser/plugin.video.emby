import xbmc
from helper import utils
from . import common

class Tag:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Tag"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.tag (DEBUG): Process item: {Item['Name']}", 1) # DEBUG
        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_tag(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_tag(Item['Id'], Item.get('Memo', None), Item['KodiArtwork']['favourite'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.tag: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.tag (DEBUG): UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "tag"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_tag(Item['Name'])
            self.SQLs["emby"].add_reference_tag(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item.get('Memo', None), Item['KodiArtwork']['favourite'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.tag: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.tag (DEBUG): ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "tag"}, IncrementalSync)

        common.download_SubnodeIcon(Item, self.EmbyServer.ServerData['ServerId']) # Download icon
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Delete = self.SQLs["emby"].remove_item(Item['Id'], "Tag", Item['LibraryId'])

        if Delete:
            if not common.verify_KodiIds(Item, IncrementalSync, False):
                return

            self.set_favorite(False, Item)
            TagName = self.SQLs["video"].delete_tag_by_Id(Item['KodiItemId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.tag: DELETE {TagName}: [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.tag (DEBUG): DELETE {TagName}: [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

            self.EmbyServer.Views.remove_synced_subnode(Item['Id'], Item['LibraryId'], "Tag", TagName) # Delete genre xml node
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "tag"}, IncrementalSync)

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Tag")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.tag: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.tag (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "tag"}, True)
        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite']:
            Item['KodiArtwork']['favourite'] = self.SQLs["emby"].get_item_by_id(Item['Id'], "Tag")[4]

        Item['Name'], hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_Tag_Name(Item['KodiItemId'])

        if not Item['Name']:
            xbmc.log(f"EMBY.core.tag: set_favorite, item not found {Item['KodiItemId']}", 2) # LOGWARNING
            return

        if hasMovies or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://movies/tags/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasTVShows or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/tags/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasMusicVideos or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://musicvideos/tags/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

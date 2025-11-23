import xbmc
from helper import utils
from . import common

class Studio:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Studio"):
            return False

        xbmc.log(f"EMBY.core.studio: Process item: {Item['Name']}", 0) # DEBUG
        common.set_Favorite(Item)
        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        if Item['KodiItemId']: # existing item
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["video"].update_studio(Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_studio(Item['Id'], Item['KodiArtwork']['favourite'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.studio: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "studio"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].get_add_studio(Item['Name'])
            self.SQLs["emby"].add_reference_studio(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiArtwork']['favourite'])
            xbmc.log(f"EMBY.core.studio: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "studio"}, IncrementalSync)

        common.download_SubnodeIcon(Item, self.EmbyServer.ServerData['ServerId']) # Download icon
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Delete, _ = self.SQLs["emby"].remove_item(Item['Id'], "Studio", Item['LibraryId'])

        if Delete:
            self.set_favorite(False, Item)
            StudioName = self.SQLs["video"].delete_studio_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.studio: DELETE {StudioName}: [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            self.EmbyServer.Views.remove_synced_subnode(Item['Id'], Item['LibraryId'], "Studio", StudioName) # Delete genre xml node
            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "studio"}, IncrementalSync)

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Studio")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "studio"}, True)
        xbmc.log(f"EMBY.core.studio: USERDATA [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite']:
            Item['KodiArtwork']['favourite'] = self.SQLs["emby"].get_item_by_id(Item['Id'], "Studio")[3]

        Item['Name'], hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_Studio_Name(Item['KodiItemId'])

        if not Item['Name']:
            xbmc.log(f"EMBY.core.studio: set_favorite, item not found {Item['KodiItemId']}", 2) # LOGWARNING
            return

        if hasMovies or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://movies/studios/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasTVShows or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/studios/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasMusicVideos or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://musicvideos/studios/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

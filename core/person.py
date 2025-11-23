import xbmc
from helper import utils
from . import common

class Person:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        Item['LibraryId'] = "999999999"

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Person"):
            return False

        xbmc.log(f"EMBY.core.person: Process item: {Item['Name']}", 0) # DEBUG
        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_Favorite(Item)
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

        if IncrementalSync and utils.ArtworkCacheIncremental:
            common.cache_artwork(Item['KodiArtwork'])

        if Item['KodiItemId']: # existing item
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "actor")
            self.SQLs["video"].update_person(Item['KodiItemId'], Item['Name'], Item['KodiArtwork']['favourite'])
            xbmc.log(f"EMBY.core.person: UPDATE [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "actor"}, IncrementalSync)
        else:
            Item['KodiItemId'] = self.SQLs["video"].add_person(Item['Name'], Item['KodiArtwork']['favourite'])
            self.SQLs["emby"].add_reference_metadata(Item['Id'], Item['LibraryId'], "Person", Item['KodiItemId'])
            xbmc.log(f"EMBY.core.person: ADD [{Item['KodiItemId']}] {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "actor"}, IncrementalSync)

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "actor")
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Delete, _ = self.SQLs["emby"].remove_item(Item['Id'], "Person", Item['LibraryId'])

        if Delete:
            self.set_favorite(False, Item)
            self.SQLs["video"].delete_people_by_Id(Item['KodiItemId'])
            xbmc.log(f"EMBY.core.person: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "actor"}, IncrementalSync)

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Person")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "actor"}, True)
        xbmc.log(f"EMBY.core.person: USERDATA [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)
        Item['Name'], Item['KodiArtwork']['favourite'], hasMusicVideos, hasMovies, hasTVShows = self.SQLs["video"].get_People(Item['KodiItemId'])

        if not Item['Name']:
            xbmc.log(f"EMBY.core.person: set_favorite, item not found {Item['KodiItemId']}", 2) # LOGWARNING
            return

        if hasMovies or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://movies/actors/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasTVShows or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/actors/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if hasMusicVideos or not IsFavorite:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://musicvideos/actors/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

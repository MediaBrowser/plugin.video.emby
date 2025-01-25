import xbmc
from helper import utils
from . import common, series


class Season:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.SeriesObject = series.Series(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if 'Name' not in Item:
            xbmc.log(f"EMBY.core.music: Name not found: {Item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.season: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Season"):
            return False

        IsFavorite = common.set_Favorite(Item)
        common.set_PresentationUniqueKey(Item)
        common.set_ItemsDependencies(Item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series", IncrementalSync)
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)
        Item['IndexNumber'] = Item.get('IndexNumber', 0)
        Item['SeriesName'] = Item.get('SeriesName', "")
        Item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeriesId'], "Series")

        if not Item['UpdateItem']:
            xbmc.log(f"EMBY.core.season: KodiSeasonId {Item['Id']} not found", 0) # LOGDEBUG
            StackedKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey("Season", Item['PresentationUniqueKey'])

            if StackedKodiId:
                Item['KodiItemId'] = StackedKodiId
                self.SQLs["emby"].add_reference_season(Item['Id'], Item['LibraryId'], Item['KodiItemId'], IsFavorite, Item['KodiParentId'], Item['PresentationUniqueKey'])
                xbmc.log(f"EMBY.core.season: ADD STACKED [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", int(IncrementalSync)) # LOG
                utils.FavoriteQueue.put(((Item['KodiArtwork']['favourite'], IsFavorite, f"videodb://tvshows/titles/{Item['KodiParentId']}/{Item['IndexNumber']}/", f"{Item['SeriesName']} - {Item['Name']}", "window", 10025),))
                return False

            Item['KodiItemId'] = self.SQLs["video"].create_entry_season()
        else:
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "season")

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "season")

        if Item['UpdateItem']:
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            self.SQLs["video"].update_season(Item['KodiParentId'], Item['IndexNumber'], Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_generic(IsFavorite, Item['Id'], "Season", Item['LibraryId'])
            xbmc.log(f"EMBY.core.season: UPDATE [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "season"}, IncrementalSync)
        else:
            self.SQLs["video"].add_season(Item['KodiItemId'], Item['KodiParentId'], Item['IndexNumber'], Item['Name'])
            self.SQLs["emby"].add_reference_season(Item['Id'], Item['LibraryId'], Item['KodiItemId'], IsFavorite, Item['KodiParentId'], Item['PresentationUniqueKey'])
            xbmc.log(f"EMBY.core.season: ADD [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "season"}, IncrementalSync)

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Season", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/titles/{Item['KodiParentId']}/{Item['IndexNumber']}/", f"{Item['SeriesName']} - {Item['Name']}", "window", 10025),))
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item):
        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], Item['KodiParentId'], Item['Id'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Season")
        utils.reset_querycache("Season")
        xbmc.log(f"EMBY.core.season: USERDATA {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "season"}, True)
        return False

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item, IncrementalSync):
        if self.SQLs["emby"].remove_item(Item['Id'], "Season", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'], Item['KodiParentId'], Item['Id'])
            SubcontentKodiIds = self.SQLs["video"].delete_season(Item['KodiItemId'])

            for KodiId, EmbyType in SubcontentKodiIds:
                self.SQLs["emby"].remove_item_by_KodiId(KodiId, EmbyType, Item['LibraryId'])
                utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiId}", "KodiType": "season"}, IncrementalSync)

            xbmc.log(f"EMBY.core.season: DELETE {Item['Id']}", int(IncrementalSync)) # LOG

    def set_favorite(self, IsFavorite, KodiItemId, KodiParentId, EmbyItemId):
        ImageUrl, Itemname, KodiSeasonNumber = self.SQLs["video"].get_FavoriteSubcontent(KodiItemId, "season")

        if Itemname:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Season", "TV Shows", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, f"videodb://tvshows/titles/{KodiParentId}/{KodiSeasonNumber}/", Itemname, "window", 10025),))

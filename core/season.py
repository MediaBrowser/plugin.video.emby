import xbmc
from helper import utils
from . import common, series


class Season:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.SeriesObject = series.Series(EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.SeriesObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if 'Name' not in Item:
            xbmc.log(f"EMBY.core.season: Name not found: {Item}", 3) # LOGERROR
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.season (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Season"):
            return False

        common.set_PresentationUniqueKey(Item)
        common.set_ItemsDependencies(Item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series", IncrementalSync, Item['LibraryId'])
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

        if IncrementalSync and utils.ArtworkCacheIncremental:
            common.cache_artwork(Item['KodiArtwork'])

        Item['IndexNumber'] = Item.get('IndexNumber', 0)
        Item['SeriesName'] = Item.get('SeriesName', "")
        Item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeriesId'], "Series")

        if not Item['UpdateItem']:
            if utils.DebugLog: xbmc.log(f"EMBY.core.season (DEBUG): KodiSeasonId {Item['Id']} not found", 1) # LOGDEBUG
            StackedKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey("Season", Item['PresentationUniqueKey'])

            if StackedKodiId:
                Item['KodiItemId'] = StackedKodiId
                self.SQLs["emby"].add_reference_season(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiParentId'], Item['PresentationUniqueKey'])

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.season: ADD STACKED [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.season (DEBUG): ADD STACKED [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGDEBUG

                return False

            Item['KodiItemId'] = self.SQLs["video"].create_entry_season()
        else:
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "season")

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "season")

        if Item['UpdateItem']:
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            self.SQLs["video"].update_season(Item['KodiParentId'], Item['IndexNumber'], Item['Name'], Item['KodiItemId'])
            self.SQLs["emby"].update_reference_generic(Item['Id'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.season: UPDATE [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.season (DEBUG): UPDATE [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "season"}, IncrementalSync)
        else:
            self.SQLs["video"].add_season(Item['KodiItemId'], Item['KodiParentId'], Item['IndexNumber'], Item['Name'])
            self.SQLs["emby"].add_reference_season(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiParentId'], Item['PresentationUniqueKey'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.season: ADD [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.season (DEBUG): ADD [{Item['KodiParentId']} / {Item['KodiItemId']}] {Item['Name'] or Item['IndexNumber']}: {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "season"}, IncrementalSync)

        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Season")

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.season: USERDATA {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.season (DEBUG): USERDATA {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "season"}, True)
        return False

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item, IncrementalSync):
        Delete = self.SQLs["emby"].remove_item(Item['Id'], "Season", Item['LibraryId'])

        if Delete:
            if not common.verify_KodiIds(Item, IncrementalSync, False):
                return

            self.set_favorite(False, Item)
            SubcontentKodiIds = self.SQLs["video"].delete_season(Item['KodiItemId'])

            for KodiId, EmbyType in SubcontentKodiIds:
                self.SQLs["emby"].remove_item_by_KodiId(KodiId, EmbyType, Item['LibraryId'])
                utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiId, "KodiType": "season"}, IncrementalSync)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.season: DELETE {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.season (DEBUG): DELETE {Item['Id']}", 1) # LOGDEBUG

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item or "IndexNumber" not in Item:
            Item['KodiArtwork']['favourite'], Item['Name'], Item['IndexNumber'] = self.SQLs["video"].get_FavoriteSubcontent(Item['KodiItemId'], "season")

        if Item['Name']:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Season", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/titles/{Item['KodiParentId']}/{Item['IndexNumber']}/", Item['Name'].replace('"', "'"), "window", 10025),))

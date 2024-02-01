import xbmc
from helper import pluginmenu, utils
from . import common, series


class Season:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.SeriesObject = series.Series(EmbyServer, self.SQLs)

    def change(self, item):
        if 'Name' not in item:
            xbmc.log(f"EMBY.core.music: Name not found: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.season: Process item: {item['Name']}", 0) # DEBUG
        common.load_ExistingItem(item, self.EmbyServer, self.SQLs["emby"], "Season")
        IsFavorite = common.set_Favorite(item)
        common.get_PresentationUniqueKey(item)
        common.set_ItemsDependencies(item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series")
        common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['SeriesName'] = item.get('SeriesName', "")
        item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(item['SeriesId'], "Series")

        if not item['UpdateItem']:
            xbmc.log(f"EMBY.core.season: KodiSeasonId {item['Id']} not found", 0) # LOGDEBUG
            StackedKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey("Season", item['PresentationUniqueKey'])

            if StackedKodiId:
                item['KodiItemId'] = StackedKodiId
                self.SQLs["emby"].add_reference_season(item['Id'], item['LibraryId'], item['KodiItemId'], IsFavorite, item['KodiParentId'], item['PresentationUniqueKey'])
                xbmc.log(f"EMBY.core.season: ADD STACKED [{item['KodiParentId']} / {item['KodiItemId']}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO
                utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], IsFavorite, f"videodb://tvshows/titles/{item['KodiParentId']}/{item['IndexNumber']}/", f"{item['SeriesName']} - {item['Name']}", "window", 10025),))
                return False

            item['KodiItemId'] = self.SQLs["video"].create_entry_season()
        else:
            self.SQLs["video"].common_db.delete_artwork(item['KodiItemId'], "season")

        self.SQLs["video"].common_db.add_artwork(item['KodiArtwork'], item['KodiItemId'], "season")

        if item['UpdateItem']:
            if int(item['Id']) > 999999900: # Skip injected items updates
                return False

            self.SQLs["video"].update_season(item['KodiParentId'], item['IndexNumber'], item['Name'], item['KodiItemId'])
            self.SQLs["emby"].update_reference_generic(IsFavorite, item['Id'], "Season", item['LibraryId'])
            xbmc.log(f"EMBY.core.season: UPDATE [{item['KodiParentId']} / {item['KodiItemId']}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO
        else:
            self.SQLs["video"].add_season(item['KodiItemId'], item['KodiParentId'], item['IndexNumber'], item['Name'])
            self.SQLs["emby"].add_reference_season(item['Id'], item['LibraryId'], item['KodiItemId'], IsFavorite, item['KodiParentId'], item['PresentationUniqueKey'])
            xbmc.log(f"EMBY.core.season: ADD [{item['KodiParentId']} / {item['KodiItemId']}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO

        utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], IsFavorite, f"videodb://tvshows/titles/{item['KodiParentId']}/{item['IndexNumber']}/", f"{item['SeriesName']} - {item['Name']}", "window", 10025),))
        return not item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item):
        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'], Item['KodiParentId'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Season")
        pluginmenu.reset_querycache("Season")
        xbmc.log(f"EMBY.core.season: USERDATA {Item['Id']}", 1) # LOGINFO

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if self.SQLs["emby"].remove_item(Item['Id'], "Season", Item['LibraryId']):
            SubcontentKodiIds = self.SQLs["video"].delete_season(Item['KodiItemId'])

            for KodiId, EmbyType in SubcontentKodiIds:
                self.SQLs["emby"].remove_item_by_KodiId(KodiId, EmbyType, Item['LibraryId'])

            xbmc.log(f"EMBY.core.season: DELETE {Item['Id']}", 1) # LOGINFO

    def set_favorite(self, IsFavorite, KodiItemId, KodiParentId):
        Image, Itemname, KodiSeasonNumber = self.SQLs["video"].get_FavoriteSubcontent(KodiItemId, "season")

        if Itemname:
            utils.FavoriteQueue.put(((Image, IsFavorite, f"videodb://tvshows/titles/{KodiParentId}/{KodiSeasonNumber}/", Itemname, "window", 10025),))

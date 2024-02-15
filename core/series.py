import xbmc
from helper import pluginmenu, utils
from . import common, genre, tag, studio, person, boxsets


class Series:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.GenreObject = genre.Genre(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)
        self.BoxSetObject = boxsets.BoxSets(EmbyServer, self.SQLs)

    def change(self, item):
        if 'Name' not in item or 'Path' not in item:
            xbmc.log(f"EMBY.core.series: Name or Path not found: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.series: Process item: {item['Name']}", 0) # DEBUG
        common.load_ExistingItem(item, self.EmbyServer, self.SQLs["emby"], "Series")
        common.get_path(item, self.EmbyServer.ServerData['ServerId'])
        IsFavorite = common.set_Favorite(item)
        common.set_RunTimeTicks(item)
        common.set_trailer(item, self.EmbyServer)
        common.set_people(item, self.SQLs, self.PersonObject, self.EmbyServer)
        common.set_common(item, self.EmbyServer.ServerData['ServerId'], False)
        item['TagItems'].append({"LibraryId": item["LibraryId"], "Type": "Tag", "Id": f"999999993{item['LibraryId']}", "Name": item['LibraryName'], "Memo": "library"})
        common.set_MetaItems(item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems")
        common.set_MetaItems(item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios")
        common.set_MetaItems(item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems')

        if not item['UpdateItem']:
            xbmc.log(f"EMBY.core.series: KodiItemId {item['Id']} not found", 0) # LOGDEBUG
            KodiPathParentId = self.SQLs["video"].get_add_path(item['KodiPathParent'], "tvshows", None)
            item['KodiPathId'] = self.SQLs["video"].get_add_path(item['KodiPath'], None, KodiPathParentId)
            StackedKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey("Series", item['PresentationUniqueKey'])

            if StackedKodiId:
                item['KodiItemId'] = StackedKodiId
                self.SQLs["emby"].add_reference_series(item['Id'], item['LibraryId'], item['KodiItemId'], IsFavorite, item['PresentationUniqueKey'], item['KodiPathId'])
                xbmc.log(f"EMBY.core.series: ADD STACKED [{item['KodiPathId']} / {item['KodiItemId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO
                utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], IsFavorite, f"videodb://tvshows/titles/{item['KodiItemId']}/", item['Name'], "window", 10025),))
                return False

            item['KodiItemId'] = self.SQLs["video"].create_entry_tvshow()
        else:
            if int(item['Id']) > 999999900: # Skip injected items updates
                return False

            KodiLibraryTagIds = self.SQLs["emby"].get_KodiLibraryTagIds()
            self.SQLs["video"].delete_links_actors(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_director(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_writer(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_countries(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_genres(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_studios(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_tags(item['KodiItemId'], "tvshow", KodiLibraryTagIds)
            self.SQLs["video"].delete_uniqueids(item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_ratings(item['KodiItemId'], "tvshow")
            self.SQLs["video"].common_db.delete_artwork(item['KodiItemId'], "tvshow")

        common.set_Genre_links(item['KodiItemId'], self.SQLs, "tvshow", item["GenreItems"])
        common.set_Studio_links(item['KodiItemId'], self.SQLs, "tvshow", item["Studios"])
        common.set_Tag_links(item['KodiItemId'], self.SQLs, "tvshow", item["TagItems"])
        common.set_Actor_links(item['KodiItemId'], self.SQLs, "tvshow", item["CastItems"])
        common.set_Writer_links(item['KodiItemId'], self.SQLs, "tvshow", item["WritersItems"])
        common.set_Director_links(item['KodiItemId'], self.SQLs, "tvshow", item["DirectorsItems"])
        self.SQLs["video"].add_countries_and_links(item['ProductionLocations'], item['KodiItemId'], "tvshow")
        self.SQLs["video"].common_db.add_artwork(item['KodiArtwork'], item['KodiItemId'], "tvshow")
        self.SQLs["video"].set_Favorite_Tag(IsFavorite, item['KodiItemId'], "tvshow")
        item['Unique'] = self.SQLs["video"].add_uniqueids(item['KodiItemId'], item['ProviderIds'], "tvshow", 'tvdb')
        item['RatingId'] = self.SQLs["video"].add_ratings(item['KodiItemId'], "tvshow", "default", item['CommunityRating'])

        if item['UpdateItem']:
            self.SQLs["video"].update_tvshow(item['Name'], item['Overview'], item['Status'], item['RatingId'], item['KodiPremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart', None), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['KodiRunTimeTicks'], item['KodiItemId'], item['Trailer'])
            self.SQLs["emby"].update_reference_generic(IsFavorite, item['Id'], "Series", item['LibraryId'])

            # Update Boxset
            for BoxSet in self.EmbyServer.API.get_Items(item['ParentId'], ["BoxSet"], True, True, {'GroupItemsIntoCollections': True}):
                BoxSet['LibraryId'] = item['LibraryId']
                self.BoxSetObject.change(BoxSet)

            xbmc.log(f"EMBY.core.series: UPDATE [{item['KodiPathId']} / {item['KodiItemId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO
        else:
            self.SQLs["video"].add_tvshow(item['KodiItemId'], item['Name'], item['Overview'], item['Status'], item['RatingId'], item['KodiPremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart', None), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['KodiRunTimeTicks'], item['Trailer'])
            self.SQLs["emby"].add_reference_series(item['Id'], item['LibraryId'], item['KodiItemId'], IsFavorite, item['PresentationUniqueKey'], item['KodiPathId'])
            self.SQLs["video"].add_link_tvshow(item['KodiItemId'], item['KodiPathId'])
            xbmc.log(f"EMBY.core.series: ADD [{item['KodiPathId']} / {item['KodiItemId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO

        utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], IsFavorite, f"videodb://tvshows/titles/{item['KodiItemId']}/", item['Name'], "window", 10025),))
        return not item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item):
        self.set_favorite(Item['IsFavorite'], Item['KodiItemId'])
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "tvshow")
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Series")
        pluginmenu.reset_querycache("Series")
        xbmc.log(f"EMBY.core.series: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if self.SQLs["emby"].remove_item(Item['Id'], "Series", Item['LibraryId']):
            self.set_favorite(False, Item['KodiItemId'])
            SubcontentKodiIds = self.SQLs["video"].delete_tvshow(Item['KodiItemId'], self.EmbyServer.ServerData['ServerId'], Item['Id'])

            for KodiId, EmbyType in SubcontentKodiIds:
                self.SQLs["emby"].remove_item_by_KodiId(KodiId, EmbyType, Item['LibraryId'])

            xbmc.log(f"EMBY.core.series: DELETE {Item['Id']}", 1) # LOGINFO
        else:
            LibraryName, _ = self.EmbyServer.library.WhitelistUnique[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "tvshow", LibraryName)

    def set_favorite(self, IsFavorite, KodiItemId):
        Image, Itemname, _ = self.SQLs["video"].get_FavoriteSubcontent(KodiItemId, "tvshow")

        if Itemname:
            utils.FavoriteQueue.put(((Image, IsFavorite, f"videodb://tvshows/titles/{KodiItemId}/", Itemname, "window", 10025),))

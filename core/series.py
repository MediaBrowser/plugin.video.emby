import xbmc
from helper import utils
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

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.GenreObject.update_SQLs(self.SQLs)
        self.TagObject.update_SQLs(self.SQLs)
        self.StudioObject.update_SQLs(self.SQLs)
        self.PersonObject.update_SQLs(self.SQLs)
        self.BoxSetObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if 'Name' not in Item or 'Path' not in Item:
            xbmc.log(f"EMBY.core.series: Name or Path not found: {Item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.series: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Series"):
            return False

        common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], {}, False)
        common.set_Favorite(Item)
        common.set_RunTimeTicks(Item)
        common.set_trailer(Item, self.EmbyServer)
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"999999993{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems', "", IncrementalSync, Item["LibraryId"])

        if not Item['UpdateItem']:
            xbmc.log(f"EMBY.core.series: KodiItemId {Item['Id']} not found", 0) # LOGDEBUG
            KodiPathParentId = self.SQLs["video"].get_add_path(Item['KodiPathParent'], "tvshows", None)
            Item['KodiPathId'] = self.SQLs["video"].get_add_path(Item['KodiPath'], None, KodiPathParentId)
            StackedKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey("Series", Item['PresentationUniqueKey'])

            if StackedKodiId:
                Item['KodiItemId'] = StackedKodiId
                self.SQLs["emby"].add_reference_series(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['PresentationUniqueKey'], Item['KodiPathId'])
                xbmc.log(f"EMBY.core.series: ADD STACKED [{Item['KodiPathId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
                return False

            Item['KodiItemId'] = self.SQLs["video"].create_entry_tvshow()
        else:
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            KodiLibraryTagIds = self.SQLs["emby"].get_KodiSpecialTagIds()
            self.SQLs["video"].delete_links_actors(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_director(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_writer(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_countries(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_genres(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_studios(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_links_tags(Item['KodiItemId'], "tvshow", KodiLibraryTagIds, False)
            self.SQLs["video"].delete_uniqueids(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].delete_ratings(Item['KodiItemId'], "tvshow")
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "tvshow")

        common.set_Genre_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["GenreItems"])
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["Studios"])
        common.set_Tag_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["TagItems"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["CastItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "tvshow", Item["DirectorsItems"])
        self.SQLs["video"].add_countries_and_links(Item['ProductionLocations'], Item['KodiItemId'], "tvshow")
        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "tvshow")
        Item['KodiUniqueId'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "tvshow", 'tvdb')
        Item['KodiRatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "tvshow", "default", Item['CommunityRating'])

        if Item['UpdateItem']:
            self.SQLs["video"].update_tvshow(Item['Name'], Item['Overview'], Item['Status'], Item['KodiRatingId'], Item['KodiPremiereDate'], Item['KodiArtwork']['poster'], Item['Genre'], Item['OriginalTitle'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['KodiUniqueId'], Item['OfficialRating'], Item['Studio'], Item['SortName'], Item['KodiRunTimeTicks'], Item['KodiItemId'], Item['Trailer'], Item['KodiPathId'], Item['KodiPath'])
            self.SQLs["emby"].update_reference_generic(Item['Id'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.series: UPDATE [{Item['KodiPathId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "tvshow"}, IncrementalSync)
        else:
            self.SQLs["video"].add_tvshow(Item['KodiItemId'], Item['Name'], Item['Overview'], Item['Status'], Item['KodiRatingId'], Item['KodiPremiereDate'], Item['KodiArtwork']['poster'], Item['Genre'], Item['OriginalTitle'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['KodiUniqueId'], Item['OfficialRating'], Item['Studio'], Item['SortName'], Item['KodiRunTimeTicks'], Item['Trailer'])
            self.SQLs["emby"].add_reference_series(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['PresentationUniqueKey'], Item['KodiPathId'])
            self.SQLs["video"].add_link_tvshow(Item['KodiItemId'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.series: ADD [{Item['KodiPathId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "tvshow"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "tvshow")
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Series")
        xbmc.log(f"EMBY.core.series: USERDATA [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "series"}, True)
        return False

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item, IncrementalSync):
        Delete, _ = self.SQLs["emby"].remove_item(Item['Id'], "Series", Item['LibraryId'])

        if Delete:
            self.set_favorite(False, Item)
            SubcontentKodiIds = self.SQLs["video"].delete_tvshow(Item['KodiItemId'], Item['KodiPathId'])

            for KodiId, EmbyType in SubcontentKodiIds:
                self.SQLs["emby"].remove_item_by_KodiId(KodiId, EmbyType, Item['LibraryId'])
                utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiId, "KodiType": "series"}, IncrementalSync)

            xbmc.log(f"EMBY.core.series: DELETE {Item['Id']}", int(IncrementalSync)) # LOG
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "tvshow", LibrarySyncedName)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item:
            Item['KodiArtwork']['favourite'], Item['Name'], _ = self.SQLs["video"].get_FavoriteSubcontent(Item['KodiItemId'], "tvshow")

        if Item['Name']:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Series", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://tvshows/titles/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

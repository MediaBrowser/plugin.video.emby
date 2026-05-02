import xbmc
from helper import utils
from . import common, tag

KodiTypeMapping = {"Movie": "movie", "Series": "tvshow", "MusicVideo": "musicvideo", "Video": "movie"}


class BoxSets:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.TagObject = tag.Tag(self.EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.TagObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "BoxSet"):
            return False

        BoxSetKodiParentIds = ()
        TagItems = []

        # Query assigned content for collections
        ContentsAssignedToBoxset = []

        for ContentAssignedToBoxset in self.EmbyServer.API.get_Items(Item['Id'], ("Audio", "Video", "Movie", "Episode", "MusicVideo", "Series"), True, {'GroupItemsIntoCollections': True, "Fields": "PresentationUniqueKey"}, "", None, False):
            ContentsAssignedToBoxset.append(ContentAssignedToBoxset)

        # Add new collection tag
        if utils.BoxSetsToTags:
            TagItems = [{"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}{Item['Id']}", "Name": f"{Item['Name']} (Collection)", "Memo": "collection", 'ImageTags': Item.get('ImageTags', {})}]
            self.TagObject.change(TagItems[0], IncrementalSync)

        # Boxsets
        common.set_overview(Item)

        if Item['UpdateItem']:
            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "set")
            self.SQLs["video"].update_boxset(Item['Name'], Item['Overview'], Item['KodiItemId'])
        else:
            if utils.DebugLog: xbmc.log(f"EMBY.core.boxsets (DEBUG): SetId {Item['Id']} not found", 1) # LOGDEBUG
            Item['KodiItemId'] = self.SQLs["video"].add_boxset(Item['Name'], Item['Overview'])

        if Item['KodiParentId']:
            CurrentBoxSetContent = Item['KodiParentId'].split(",")
        else:
            CurrentBoxSetContent = []

        # Assign series to movies
        if utils.MovieToSeries:
            BoxSetSeries = []
            BoxSetMovies = []

            for ContentAssignedToBoxset in ContentsAssignedToBoxset:
                if ContentAssignedToBoxset['Type'] == "Series":
                    BoxSetSeries.append(ContentAssignedToBoxset)
                elif ContentAssignedToBoxset['Type'] in ("Movie", "Video"):
                    BoxSetMovies.append(ContentAssignedToBoxset)

            for BoxSetSerie in BoxSetSeries:
                BoxSetSerieItemKodiId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(BoxSetSerie['Id'], "Series")

                if BoxSetSerieItemKodiId:
                    for BoxSetMovie in BoxSetMovies:
                        BoxSetMovieItemKodiId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(BoxSetMovie['Id'], "Movie")

                        if BoxSetMovieItemKodiId:
                            self.SQLs["video"].add_link_movie_tvshow(BoxSetMovieItemKodiId, BoxSetSerieItemKodiId)

                            if int(IncrementalSync):
                                xbmc.log(f"EMBY.core.boxsets: ADD to series links: Series: [{BoxSetSerieItemKodiId}] {BoxSetSerie['Name']} / Movie: [{BoxSetMovieItemKodiId}] {BoxSetMovie['Name']}", 1) # LOGINFO
                            elif utils.DebugLog:
                                xbmc.log(f"EMBY.core.boxsets (DEBUG): ADD to series links: Series: [{BoxSetSerieItemKodiId}] {BoxSetSerie['Name']} / Movie: [{BoxSetMovieItemKodiId}] {BoxSetMovie['Name']}", 1) # LOGDEBUG

        # Assign boxsets
        for ContentAssignedToBoxset in ContentsAssignedToBoxset:
            if ContentAssignedToBoxset['Type'] not in ("Movie", "Series", "MusicVideo", "Video"): # Episode and season tags not supported by Kodi
                continue

            ContentAssignedToBoxset.update({'KodiItemId': Item['KodiItemId']})
            common.set_PresentationUniqueKey(ContentAssignedToBoxset)
            ContentItemKodiId = self.SQLs["emby"].get_KodiId_by_EmbyPresentationKey(ContentAssignedToBoxset['Type'], ContentAssignedToBoxset['PresentationUniqueKey'])

            if ContentAssignedToBoxset['Type'] in ("Movie", "Video") and ContentItemKodiId:
                if str(ContentItemKodiId) in CurrentBoxSetContent:
                    CurrentBoxSetContent.remove(str(ContentItemKodiId))

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.boxsets: ADD to Kodi set [{Item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.boxsets (DEBUG): ADD to Kodi set [{Item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGDEBUG

                self.SQLs["video"].set_boxset(Item['KodiItemId'], ContentItemKodiId) # assign boxset to movie
                BoxSetKodiParentIds += (str(ContentItemKodiId),)

            # Assign content to collection tag
            if utils.BoxSetsToTags and ContentItemKodiId:
                common.set_Tag_links(ContentItemKodiId, self.SQLs, KodiTypeMapping[ContentAssignedToBoxset['Type']], TagItems)

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.boxsets: ADD to tag [{Item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.boxsets (DEBUG): ADD to tag [{Item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGDEBUG

        # Delete remove content from boxsets
        for KodiContentId in CurrentBoxSetContent:
            self.SQLs["video"].remove_from_boxset(KodiContentId)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.boxsets: DELETE from boxset [{Item['Id']}] {Item['KodiItemId']} {Item['Name']}: {KodiContentId}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.boxsets (DEBUG): DELETE from boxset [{Item['Id']}] {Item['KodiItemId']} {Item['Name']}: {KodiContentId}", 1) # LOGDEBUG

        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

        if IncrementalSync and utils.ArtworkCacheIncremental:
            common.cache_artwork(Item['KodiArtwork'])

        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], "set")
        Item['KodiParentId'] = ",".join(BoxSetKodiParentIds)
        self.SQLs["emby"].add_reference_boxset(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiParentId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.boxsets: UPDATE [{Item['Id']}] {Item['KodiItemId']} {Item['Name']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.boxsets (DEBUG): UPDATE [{Item['Id']}] {Item['KodiItemId']} {Item['Name']}", 1) # LOGDEBUG

        utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "set"}, IncrementalSync)
        return True

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.boxsets: USERDATA {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.boxsets (DEBUG): USERDATA {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "set"}, True)
        return False

    def remove(self, Item, IncrementalSync):
        if utils.BoxSetsToTags:
            TagId = f"{utils.MappingIds['Tag']}{Item['Id']}"
            TagKodiId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(TagId, "Tag")

            if TagKodiId:
                self.TagObject.remove({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": TagId, "KodiItemId": TagKodiId}, IncrementalSync)

        Deleted = self.SQLs["emby"].remove_item(Item['Id'], "BoxSet", Item['LibraryId'])

        if Deleted:
            if not common.verify_KodiIds(Item, IncrementalSync, False):
                return

            for KodiParentId in self.SQLs["emby"].get_KodiParentIds(Item['Id'], "BoxSet"):
                self.SQLs["video"].remove_from_boxset(KodiParentId)

            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "set")
            self.set_favorite(False, Item)
            self.SQLs["video"].delete_boxset(Item['KodiItemId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.boxsets: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.boxsets (DEBUG): DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "set"}, IncrementalSync)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)
        self.SQLs["emby"].update_favourite(IsFavorite, Item['Id'], "BoxSet")

        if IsFavorite and not Item['KodiArtwork']['favourite'] or 'Name' not in Item:
            _, Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["video"].get_favoriteData(None, Item['KodiItemId'], "set")

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Boxset", "Set", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://movies/sets/{Item['KodiItemId']}/", Item['Name'].replace('"', "'"), "window", 10025),))

        if utils.BoxSetsToTags:
            EmbyTagId = f"{utils.MappingIds['Tag']}{Item['Id']}"
            self.SQLs["emby"].update_favourite(IsFavorite, EmbyTagId, "Tag")
            KodiTagId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(EmbyTagId, "Tag")

            if KodiTagId:
                ItemTag = Item.copy()
                ItemTag.update({'KodiItemId': KodiTagId, 'Id': EmbyTagId})

import xbmc
from helper import utils
from . import common, genre, tag, studio, person, trailer


class Movies:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.GenreObject = genre.Genre(self.EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(self.EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(self.EmbyServer, self.SQLs)
        self.PersonObject = person.Person(self.EmbyServer, self.SQLs)
        self.TrailerObject = trailer.Trailer(self.EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.GenreObject.update_SQLs(self.SQLs)
        self.TagObject.update_SQLs(self.SQLs)
        self.StudioObject.update_SQLs(self.SQLs)
        self.PersonObject.update_SQLs(self.SQLs)
        self.TrailerObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "movie"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.movies (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Movie"):
            return False

        # ungroup versions
        isMultiVersion = False

        if Item['UpdateItem']:
            MultiVersionsFound = self.SQLs["emby"].get_movieversions(Item['Id'])

            if len(MultiVersionsFound) > 1:
                isMultiVersion = True
                LastPlayedTicksCompare = 0

                for MultiVersionFound in MultiVersionsFound:
                    Found, timeInSeconds, playCount, lastPlayed = self.SQLs["video"].get_Progress(MultiVersionFound[1])

                    if lastPlayed:
                        LastPlayedTicks = utils.get_unix_ticks(lastPlayed)
                    else:
                        LastPlayedTicks = 0

                    if Found and LastPlayedTicks > LastPlayedTicksCompare:
                        LastPlayedTicksCompare = LastPlayedTicks
                        Item.update({'KodiPlayCount': playCount, 'KodiLastPlayedDate': lastPlayed, 'KodiPlaybackPositionTicks': timeInSeconds, 'IsFavorite': Item['EmbyFavourite']})

                for MultiVersionFound in MultiVersionsFound:
                    self.remove({'KodiFileId': MultiVersionFound[1], 'KodiItemId': MultiVersionFound[2], 'Id': MultiVersionFound[0], 'KodiPathId': MultiVersionFound[3], 'LibraryId': Item['LibraryId']}, False)

        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}00{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems', "", IncrementalSync, Item["LibraryId"])
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])

        if Item['UpdateItem'] and not isMultiVersion:
            common.delete_ContentItemReferences(Item['KodiItemId'], Item['KodiFileId'], Item.get('ExtraType', ""), self.SQLs, "movie", False)
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            common.update_downloaded_info(Item, self.SQLs, "movie")
        else:
            Item['KodiItemId'] = self.SQLs["video"].create_movie_entry()
            Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            Item['KodiPathId'] = self.SQLs['video'].get_add_path(Item['KodiPath'], "movies")

        common.set_RemoteTrailer(Item, self.TrailerObject, IncrementalSync)
        common.set_VideoCommon(Item['KodiItemId'], Item['KodiFileId'], Item, self.SQLs, "movie")
        common.set_Genre_links(Item['KodiItemId'], self.SQLs, "movie", Item["GenreItems"])
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "movie", Item["Studios"])
        common.set_Tag_links(Item['KodiItemId'], self.SQLs, "movie", Item["TagItems"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "movie", Item["CastItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "movie", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "movie", Item["DirectorsItems"])
        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiFileId'], "videoversion")
        Item['KodiUniqueId'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "movie", 'imdb')
        Item['KodiRatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "default", Item['CommunityRating'])
        self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "tomatometerallcritics", Item['KodiCriticRating'])

        if not Item['ProductionLocations']:
            Item['ProductionLocations'].append(None)

        if Item['UpdateItem'] and not isMultiVersion:
            self.SQLs["video"].update_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['KodiSortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPremiereDate'], None, Item['KodiFilename'], Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['MediaSources'][0]['Name'], Item['KodiPathId'], Item['KodiPath'], Item['KodiFullPath'])
            self.SQLs["emby"].update_reference_movie(Item['Id'], Item['PresentationUniqueKey'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.movies: UPDATE [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.movies (DEBUG): UPDATE [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)
        else:
            self.SQLs["video"].add_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['SortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiFullPath'], Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiFilename'], Item['KodiDateCreated'], None, Item['KodiStackedFilename'], Item['MediaSources'][0]['Name'])
            self.SQLs["emby"].add_reference_movie(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiFileId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.movies: ADD [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.movies (DEBUG): ADD [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        common.add_multiversion(Item, "Movie", self.EmbyServer, self.SQLs, self.EmbyServer.ServerData['ServerId'], None, None)

        # Update userdata
        if isMultiVersion:
            self.userdata(Item, IncrementalSync, True)

        # Add Subitems
        self.SQLs["emby"].add_UpdateItem_Parent(Item['Id'], "Movie", Item['LibraryId'], Item['KodiItemId'], "Theme", "") # Theme

        if int(Item['SpecialFeatureCount']):
            self.SQLs["emby"].add_UpdateItem_Parent(Item['Id'], "Movie", Item['LibraryId'], Item['KodiItemId'], "Special", "video") # Specials

        if 'LocalTrailerCount' in Item and Item['LocalTrailerCount']:
            self.SQLs["emby"].add_UpdateItem_Parent(Item['Id'], "Movie", Item['LibraryId'], Item['KodiItemId'], "Trailer", "video")

        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, True):
            return False

        Update = False
        common.set_playstate(Item)
        common.set_Favorite(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "movie")
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Movie")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        for BookmarkData in self.SQLs["video"].get_BookmarkData_by_videoversion(Item['KodiItemId'], "movie"):
            if self.SQLs["video"].update_bookmark_playstate(BookmarkData[0], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], BookmarkData[1]):
                Update = True

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.movies: USERDATA [{BookmarkData[0]} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.movies (DEBUG): USERDATA [{BookmarkData[0]} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, True)
        return Update

    def remove(self, Item, IncrementalSync):
        if not common.verify_KodiIds(Item, IncrementalSync, True):
            return

        if common.delete_ContentItem(Item['KodiItemId'], Item['KodiFileId'], Item, self.SQLs, "movie", "Movie"):
            self.set_favorite(False, Item)
            self.SQLs["video"].delete_movie(Item['KodiItemId'], Item['KodiFileId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.movies: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.movies (DEBUG): DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, IncrementalSync)
            common.update_multiversion(self.SQLs["emby"], "Movie", Item['Id'], Item['LibraryId'], Item.get('PresentationUniqueKey', ''))
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "movie", LibrarySyncedName)

        self.SQLs['emby'].remove_item_by_parentid(Item['Id'], "Video", Item['LibraryId']) # delete referenced specials, themes etc.
        self.SQLs['emby'].remove_item_by_parentid(Item['Id'], "Audio", Item['LibraryId']) # delete referenced themes
        self.SQLs['emby'].remove_item_by_parentid(Item['Id'], "Trailer", Item['LibraryId']) # delete referenced trailers

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item or "KodiFullPath" not in Item:
            Item['KodiFullPath'], Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["video"].get_favoriteData(Item['KodiFileId'], Item['KodiItemId'], "movie")

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Movie", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, Item['KodiFullPath'], Item['Name'].replace('"', "'"), "media", 0),))

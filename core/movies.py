import xbmc
from helper import utils
from . import common, genre, tag, studio, person, boxsets


class Movies:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.GenreObject = genre.Genre(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)
        self.BoxSetObject = boxsets.BoxSets(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "movie"):
            return False

        xbmc.log(f"EMBY.core.movies: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Movie"):
            return False

        # ungroup versions
        if Item['UpdateItem']:
            Movieversions = self.SQLs["emby"].get_movieversions(Item['Id'])

            if len(Movieversions) > 1:
                for Movieversion in Movieversions:
                    DelteItem = {'KodiFileId': Movieversion[1], 'KodiItemId': Movieversion[2], 'Id': Movieversion[0], 'KodiPathId': Movieversion[3], 'LibraryId': Item['LibraryId']}
                    self.remove(DelteItem, False)

                Item['UpdateItem'] = False

        common.set_trailer(Item, self.EmbyServer)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"999999993{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", None, -1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", None, -1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems', None, -1, IncrementalSync)
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])

        if Item['UpdateItem']:
            common.delete_ContentItemReferences(Item, self.SQLs, "movie")
            common.update_downloaded_info(Item, self.SQLs)
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
        else:
            Item['KodiItemId'] = self.SQLs["video"].create_movie_entry()
            Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            Item['KodiPathId'] = self.SQLs['video'].get_add_path(Item['KodiPath'], "movies")

        common.set_VideoCommon(Item, self.SQLs, "movie")
        common.set_Genre_links(Item['KodiItemId'], self.SQLs, "movie", Item["GenreItems"])
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "movie", Item["Studios"])
        common.set_Tag_links(Item['KodiItemId'], self.SQLs, "movie", Item["TagItems"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "movie", Item["CastItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "movie", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "movie", Item["DirectorsItems"])
        self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiFileId'], "videoversion")
        self.SQLs["video"].set_Favorite_Tag(Item['UserData']['IsFavorite'], Item['KodiItemId'], "movie")
        Item['KodiUniqueId'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "movie", 'imdb')
        Item['KodiRatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "default", Item['CommunityRating'])
        self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "tomatometerallcritics", Item['KodiCriticRating'])

        if not Item['ProductionLocations']:
            Item['ProductionLocations'].append(None)

        if Item['UpdateItem']:
            self.SQLs["video"].update_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['KodiSortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPremiereDate'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiFilename'], Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['MediaSources'][0]['Name'], Item['KodiPathId'], Item['KodiPath'])
            self.SQLs["emby"].update_reference_movie_musicvideo(Item['Id'], "Movie", Item['UserData']['IsFavorite'], Item['PresentationUniqueKey'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.movies: UPDATE [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)
        else:
            self.SQLs["video"].add_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['SortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPath'], Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiStackedFilename'], Item['MediaSources'][0]['Name'])
            self.SQLs["emby"].add_reference_movie_musicvideo(Item['Id'], Item['LibraryId'], "Movie", Item['KodiItemId'], Item['UserData']['IsFavorite'], Item['KodiFileId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.movies: ADD [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        self.SQLs["emby"].add_multiversion(Item, "Movie", self.EmbyServer.API, self.SQLs, self.EmbyServer.ServerData['ServerId'])

        if 'SpecialFeatureCount' in Item:
            if int(Item['SpecialFeatureCount']):
                SpecialFeatures = self.EmbyServer.API.get_specialfeatures(Item['Id'])

                for SF_Item in SpecialFeatures:
                    SF_Item.update({"LibraryId": Item['LibraryId'], "KodiItemId": Item['KodiItemId']})
                    common.set_playstate(SF_Item)
                    common.set_streams(SF_Item)
                    common.set_RunTimeTicks(SF_Item)
                    common.set_chapters(SF_Item, self.EmbyServer.ServerData['ServerId'])
                    SF_Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
                    common.set_path_filename(SF_Item, self.EmbyServer.ServerData['ServerId'], None)
                    common.set_multipart(SF_Item, self.EmbyServer)
                    common.set_KodiArtwork(SF_Item, self.EmbyServer.ServerData['ServerId'], False)
                    common.set_DateCreated(SF_Item)
                    SF_Item['KodiPathId'] = self.SQLs['video'].get_add_path(SF_Item['KodiPath'], "movies")
                    self.SQLs["video"].add_bookmarks(SF_Item['KodiFileId'], SF_Item['KodiRunTimeTicks'], SF_Item['MediaSources'][0]['KodiChapters'], SF_Item['KodiPlaybackPositionTicks'])
                    self.SQLs["video"].add_streams(SF_Item['KodiFileId'], SF_Item['MediaSources'][0]['KodiStreams']['Video'], SF_Item['MediaSources'][0]['KodiStreams']['Audio'], SF_Item['MediaSources'][0]['KodiStreams']['Subtitle'], SF_Item['KodiRunTimeTicks'])
                    self.SQLs["video"].common_db.add_artwork(SF_Item['KodiArtwork'], SF_Item['KodiFileId'], "videoversion")
                    self.SQLs["video"].add_movie_version(Item['KodiItemId'], SF_Item['KodiFileId'], SF_Item['KodiPathId'], SF_Item['KodiFilename'], SF_Item['KodiDateCreated'], SF_Item['KodiPlayCount'], SF_Item['KodiLastPlayedDate'], SF_Item['KodiStackedFilename'], SF_Item['Name'], "movie", 1)
                    self.SQLs["emby"].add_streamdata(SF_Item['Id'], SF_Item['MediaSources'])
                    self.SQLs["emby"].add_reference_video(SF_Item['Id'], SF_Item['LibraryId'], SF_Item['KodiItemId'], SF_Item['UserData']['IsFavorite'], SF_Item['KodiFileId'], SF_Item['ParentId'], SF_Item['PresentationUniqueKey'], SF_Item['Path'], SF_Item['KodiPathId'], True)

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Movie", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        Update = False
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "movie")
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Movie")
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'], Item['Id'])

        for KodieFileId in self.SQLs["video"].get_KodiFileId_by_videoversion(Item['KodiItemId'], "movie"):
            if self.SQLs["video"].update_bookmark_playstate(KodieFileId[0], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks']):
                Update = True

        utils.reset_querycache("Movie")
        xbmc.log(f"EMBY.core.movies: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']} / {Item['KodiPlaybackPositionTicks']}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.core.movies: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, True)
        return Update

    def remove(self, Item, IncrementalSync):
        if common.delete_ContentItem(Item, self.SQLs, "movie", "Movie"):
            self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
            self.SQLs["video"].delete_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.movies: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "Movie")
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "movie", LibrarySyncedName)

    def set_favorite(self, IsFavorite, KodiFileId, KodiItemId, EmbyItemId):
        FullPath, ImageUrl, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "movie")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Movie", "Movies", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, FullPath, Itemname, "media", 0),))

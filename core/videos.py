import xbmc
from helper import utils
from . import common, genre, tag, studio, person, boxsets


class Videos:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.GenreObject = genre.Genre(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)
        self.BoxSetObject = boxsets.BoxSets(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "video"):
            return False

        xbmc.log(f"EMBY.core.videos: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Video"):
            return False

        # ungroup versions
        if Item['UpdateItem']:
            Movieversions = self.SQLs["emby"].get_movieversions(Item['Id'])

            if len(Movieversions) > 1:
                for Movieversion in Movieversions:
                    DelteItem = {'KodiFileId': Movieversion[1], 'KodiItemId': Movieversion[2], 'Id': Movieversion[0], 'KodiPathId': Movieversion[3], 'LibraryId': Item['LibraryId']}
                    self.remove(DelteItem, False)

                Item['UpdateItem'] =  False

        common.set_trailer(Item, self.EmbyServer)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
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
            Item['ProductionLocations'].append("")

        if Item['UpdateItem']: # new item
            self.SQLs["video"].update_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['KodiSortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPremiereDate'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiFilename'], Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['MediaSources'][0]['Name'], Item['KodiPathId'], Item['KodiPath'])
            self.SQLs["emby"].update_reference_video(Item['Id'], Item['UserData']['IsFavorite'], Item['ParentId'], Item['PresentationUniqueKey'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.videos: UPDATE {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)
        else:
            self.SQLs["video"].add_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['SortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPath'], Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiStackedFilename'], Item['MediaSources'][0]['Name'])
            self.SQLs["emby"].add_reference_video(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['UserData']['IsFavorite'], Item['KodiFileId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'], False)
            xbmc.log(f"EMBY.core.videos: ADD {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Video", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        self.SQLs["emby"].add_multiversion(Item, "Video", self.EmbyServer.API, self.SQLs, self.EmbyServer.ServerData['ServerId'])
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "movie")
        Update = self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Video")
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
        utils.reset_querycache("Video")
        xbmc.log(f"EMBY.core.videos: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']} / {Item['KodiPlaybackPositionTicks']}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.core.videos: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, True)
        return Update

    def remove(self, Item, IncrementalSync):
        if common.delete_ContentItem(Item, self.SQLs, "movie", "Video", Item['isSpecial']):
            self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
            self.SQLs["video"].delete_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.videos: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "movie"}, IncrementalSync)

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "Video")
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "movie", LibrarySyncedName)

    def set_favorite(self, IsFavorite, KodiFileId, KodiItemId, EmbyItemId):
        FullPath, ImageUrl, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "movie")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Video", "Movies", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, FullPath, Itemname, "media", 0),))

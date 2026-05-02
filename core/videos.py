import json
import xbmc
from helper import utils
from . import common, genre, tag, studio, person


class Videos:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.GenreObject = genre.Genre(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.GenreObject.update_SQLs(self.SQLs)
        self.TagObject.update_SQLs(self.SQLs)
        self.StudioObject.update_SQLs(self.SQLs)
        self.PersonObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "video"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.videos (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Video"):
            return False

        if 'ExtraType' in Item:
            if Item['ExtraType'] == "Clip": # Specials
                if Item['UpdateItem']:
                    self.SQLs["video"].delete_special(Item['KodiParentId'], Item['KodiFileId'], "movie")
                    self.SQLs["emby"].remove_item(Item['Id'], "Video", Item['LibraryId'])

                common.set_playstate(Item)
                common.set_streams(Item)
                common.set_RunTimeTicks(Item)
                common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
                Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
                common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
                common.set_multipart(Item, self.EmbyServer)
                common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)

                if IncrementalSync and utils.ArtworkCacheIncremental:
                    common.cache_artwork(Item['KodiArtwork'])

                common.set_DateCreated(Item)
                Item['KodiPathId'] = self.SQLs['video'].get_add_path(Item['KodiPath'], "movies")
                self.SQLs["video"].add_bookmarks(Item['KodiFileId'], Item['KodiRunTimeTicks'], Item['MediaSources'][0]['KodiChapters'])
                self.SQLs["video"].add_streams(Item['KodiFileId'], Item['MediaSources'][0]['KodiStreams']['Video'], Item['MediaSources'][0]['KodiStreams']['Audio'], Item['MediaSources'][0]['KodiStreams']['Subtitle'], Item['KodiRunTimeTicks'])
                self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiFileId'], "videoversion")
                self.SQLs["video"].add_movie_version(Item['KodiParentId'], Item['KodiFileId'], Item['KodiPathId'], Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiStackedFilename'], Item['Name'], "movie", "special")
                self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])
                self.SQLs["emby"].add_reference_video(Item['Id'], Item['LibraryId'], None, Item['KodiFileId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'], Item['ExtraType'], Item['KodiParentId'])
                if utils.DebugLog: xbmc.log(f"EMBY.core.video (DEBUG): ADD EXTRATYPE {Item['Id']} / {Item['LibraryId']} / {Item['ExtraType']}", 1) # DEBUGLOG
                return False

            if Item['ExtraType'] == "ThemeVideo": # ThemeVideo
                self.SQLs["emby"].add_reference_video_parent(Item['Id'], Item['LibraryId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['ExtraType'], Item['KodiParentId'], Item['EmbyParentType'], json.dumps(Item))
                if utils.DebugLog: xbmc.log(f"EMBY.core.video (DEBUG): ADD EXTRATYPE {Item['Id']} / {Item['LibraryId']} / {Item['ExtraType']}", 1) # DEBUGLOG
                return False

        if Item['LibraryId'] == "999999998": # Trailer in extra trailer folder
            if Item.get('ParentId', ""): # Items from extra trailer folder has no ParentId
                return False

            self.SQLs["emby"].add_reference_video_parent(Item['Id'], Item['LibraryId'], None, Item['PresentationUniqueKey'], Item['Path'], Item.get('ExtraType', ""), None, None, json.dumps(Item))
            if utils.DebugLog: xbmc.log(f"EMBY.core.video (DEBUG): ADD Video trailer in extra folder {Item['Id']} / {Item['LibraryId']} / {Item['ExtraType']}", 1) # DEBUGLOG
            return False

        # ungroup versions
        if Item['UpdateItem']:
            Movieversions = self.SQLs["emby"].get_movieversions(Item['Id'])

            if len(Movieversions) > 1:
                for Movieversion in Movieversions:
                    DelteItem = {'KodiFileId': Movieversion[1], 'KodiItemId': Movieversion[2], 'Id': Movieversion[0], 'KodiPathId': Movieversion[3], 'LibraryId': Item['LibraryId']}
                    self.remove(DelteItem, False)

                Item['UpdateItem'] =  False

        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}00{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", "", IncrementalSync, Item["LibraryId"])
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems', "", IncrementalSync, Item["LibraryId"])
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])

        if Item['UpdateItem']:
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
            Item['ProductionLocations'].append("")

        if Item['UpdateItem']:
            self.SQLs["video"].update_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['KodiSortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], None, Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPremiereDate'], None, Item['KodiFilename'], Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['MediaSources'][0]['Name'], Item['KodiPathId'], Item['KodiPath'], Item['KodiFullPath'])
            self.SQLs["emby"].update_reference_video(Item['Id'], Item['ParentId'], Item['PresentationUniqueKey'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.videos: UPDATE {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.videos (DEBUG): UPDATE {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, IncrementalSync)
        else: # new item
            self.SQLs["video"].add_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['KodiRatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['KodiUniqueId'], Item['SortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], None, Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiFullPath'], Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiFilename'], Item['KodiDateCreated'], None, Item['KodiStackedFilename'], Item['MediaSources'][0]['Name'])
            self.SQLs["emby"].add_reference_video(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiFileId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'], None, None)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.videos: ADD {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.videos (DEBUG): ADD {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        common.add_multiversion(Item, "Video", self.EmbyServer, self.SQLs, self.EmbyServer.ServerData['ServerId'], None, None)
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        Update = False
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "movie")
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Video")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        for KodiFileId in self.SQLs["video"].get_KodiFileId_by_videoversion(Item['KodiItemId'], "movie"):
            if self.SQLs["video"].update_bookmark_playstate(KodiFileId[0], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks']):
                Update = True

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.videos: USERDATA [{KodiFileId} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.videos (DEBUG): USERDATA [{KodiFileId} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, True)
        return Update

    def remove(self, Item, IncrementalSync):
        if common.delete_ContentItem(Item['KodiItemId'], Item['KodiFileId'], Item, self.SQLs, "movie", "Video"):
            self.set_favorite(False, Item)
            self.SQLs["video"].delete_movie(Item['KodiItemId'], Item['KodiFileId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.videos: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.videos (DEBUG): DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "movie"}, IncrementalSync)
            common.update_multiversion(self.SQLs["emby"], "Video", Item['Id'], Item['LibraryId'], Item.get('PresentationUniqueKey', ''))
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "movie", LibrarySyncedName)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item or "KodiFullPath" not in Item:
            Item['KodiFullPath'], Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["video"].get_favoriteData(Item['KodiFileId'], Item['KodiItemId'], "movie")

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Video", "Movies", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, Item['KodiFullPath'], Item['Name'].replace('"', "'"), "media", 0),))

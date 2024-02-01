import xbmc
from helper import pluginmenu, utils
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

    def change(self, Item):
        if not common.verify_content(Item, "video"):
            return False

        xbmc.log(f"EMBY.core.videos: Process Item: {Item['Name']}", 0) # DEBUG
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Video")
        common.SwopMediaSources(Item)  # 3D
        common.set_trailer(Item, self.EmbyServer)
        common.set_RunTimeTicks(Item)
        common.get_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])

        if self.SQLs["video"]: # Sync content to Kodi db
            common.get_path(Item, self.EmbyServer.ServerData['ServerId'])
            Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"999999993{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
            common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems")
            common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios")
            common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems')
            common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer)
            self.SQLs["emby"].add_streamdata(Item['Id'], Item['Streams'])

            if Item['UpdateItem']:
                common.delete_ContentItemReferences(Item, self.SQLs, "movie")
                common.update_downloaded_info(Item, self.SQLs)
            else:
                Item['KodiPathId'] = self.SQLs['video'].get_add_path(Item['KodiPath'], "movies")
                Item['KodiItemId'] = self.SQLs["video"].create_movie_entry()
                Item['KodiFileId'] = self.SQLs["video"].create_entry_file()

            common.set_VideoCommon(Item, self.SQLs, "movie", self.EmbyServer.API)
            common.set_Genre_links(Item['KodiItemId'], self.SQLs, "movie", Item["GenreItems"])
            common.set_Studio_links(Item['KodiItemId'], self.SQLs, "movie", Item["Studios"])
            common.set_Tag_links(Item['KodiItemId'], self.SQLs, "movie", Item["TagItems"])
            common.set_Actor_links(Item['KodiItemId'], self.SQLs, "movie", Item["CastItems"])
            common.set_Writer_links(Item['KodiItemId'], self.SQLs, "movie", Item["WritersItems"])
            common.set_Director_links(Item['KodiItemId'], self.SQLs, "movie", Item["DirectorsItems"])
            self.SQLs["video"].set_Favorite_Tag(Item['UserData']['IsFavorite'], Item['KodiItemId'], "movie")
            Item['Unique'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "movie", 'imdb')
            Item['RatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "default", Item['CommunityRating'])

            if not Item['ProductionLocations']:
                Item['ProductionLocations'].append("")

            if Item['CriticRating']:
                Item['CriticRating'] = float(Item['CriticRating'] / 10.0)
                self.SQLs["video"].add_ratings(Item['KodiItemId'], "movie", "tomatometerallcritics", Item['CriticRating'])

            if Item['UpdateItem']: # new item
                self.SQLs["video"].update_movie(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['RatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['Unique'], Item['KodiSortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPremiereDate'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiFilename'], Item['KodiStackedFilename'])
                self.SQLs["emby"].update_reference_video(Item['Id'], Item['UserData']['IsFavorite'], Item['ParentId'], Item['PresentationUniqueKey'], Item['LibraryId'])

                # Update Boxset
                for BoxSet in self.EmbyServer.API.get_Items(Item['ParentId'], ["BoxSet"], True, True, {'GroupItemsIntoCollections': True}):
                    BoxSet['LibraryId'] = Item['LibraryId']
                    self.BoxSetObject.change(BoxSet)

                xbmc.log(f"EMBY.core.videos: UPDATE {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            else:
                self.SQLs["video"].add_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['ShortOverview'], Item['Tagline'], Item['RatingId'], Item['Writers'], Item['KodiArtwork']['poster'], Item['Unique'], Item['SortName'], Item['KodiRunTimeTicks'], Item['OfficialRating'], Item['Genre'], Item['Directors'], Item['OriginalTitle'], Item['Studio'], Item['Trailer'], Item['KodiArtwork']['fanart'].get('fanart', None), Item['ProductionLocations'][0], Item['KodiPath'], Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], None, Item['KodiStackedFilename'])
                self.SQLs["emby"].add_reference_video(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['UserData']['IsFavorite'], Item['KodiFileId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])

            utils.FavoriteQueue.put(((Item['KodiArtwork']['favourite'], Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        else: # Unsync content to Kodi db (e.g. Emby specials)
            common.SwopMediaSources(Item)  # 3D
            self.SQLs["emby"].add_streamdata(Item['Id'], Item['Streams'])
            self.SQLs["emby"].add_reference_video(Item['Id'], Item['LibraryId'], None, Item['UserData']['IsFavorite'], None, Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], None)
            xbmc.log(f"EMBY.core.videos: ADD {Item['Id']}: {Item['Name']}", 1) # LOGINFO

        self.SQLs["emby"].add_multiversion(Item, "Video", self.EmbyServer.API, self.SQLs)
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "movie")
        self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Video")
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'])
        pluginmenu.reset_querycache("Video")
        xbmc.log(f"EMBY.core.videos: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']} / {Item['KodiPlaybackPositionTicks']}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.core.videos: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        if common.delete_ContentItem(Item, self.SQLs, "movie", "Video"):
            self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'])
            self.SQLs["video"].delete_movie(Item['KodiItemId'], Item['KodiFileId'])
            xbmc.log(f"EMBY.core.videos: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "Video")
        else:
            LibraryName, _ = self.EmbyServer.library.WhitelistUnique[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "movie", LibraryName)

    def set_favorite(self, IsFavorite, KodiFileId, KodiItemId):
        FullPath, Image, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "movie")
        utils.FavoriteQueue.put(((Image, IsFavorite, FullPath, Itemname, "media", 0),))

from helper import loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.movies')


class Movies:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.video_db.init_favorite_tags()

    def movie(self, item):
        LOG.info("Process item: %s" % item['Name'])

        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if not 'MediaSources' in item or not item['MediaSources']:
            LOG.error("No mediasources found for movie: %s" % item['Id'])
            LOG.debug("No mediasources found for movie: %s" % item)
            return False

        ItemIndex = 0
        common.SwopMediaSources(item)  # 3D
        item['OriginalTitle'] = item.get('OriginalTitle', "")
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['CriticRating'] = item.get('CriticRating', None)
        item['ShortOverview'] = item.get('ShortOverview', "")
        common.set_mpaa(item)
        common.set_trailer(item, self.EmbyServer)

        for ItemIndex in range(len(item['Librarys'])):
            if item['KodiItemIds'][ItemIndex]: # existing item
                self.remove_movie(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Id'], item['LibraryIds'][ItemIndex])

            if not common.get_file_path(item, "movies", ItemIndex):
                continue

            item['KodiItemIds'][ItemIndex] = self.video_db.create_movie_entry()
            item['KodiFileIds'][ItemIndex] = self.video_db.create_entry_file()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], "movies")
            common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "movie", "m", ItemIndex)
            item['Unique'] = self.video_db.add_uniqueids(item['KodiItemIds'][ItemIndex], item['ProviderIds'], "movie", 'imdb')
            item['RatingId'] = self.video_db.add_ratings(item['KodiItemIds'][ItemIndex], "movie", "default", item['CommunityRating'])

            if not item['ProductionLocations']:
                item['ProductionLocations'].append("")

            self.video_db.add_movie(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Name'], item['Overview'], item['ShortOverview'], item['Taglines'][0], item['RatingId'], item['Writers'], item['KodiArtwork']['poster'], item['Unique'], item['SortName'], item['RunTimeTicks'], item['OfficialRating'], item['Genre'], item['Directors'], item['OriginalTitle'], item['Studio'], item['Trailer'], item['KodiArtwork']['fanart'].get('fanart', ""), item['ProductionLocations'][0], item['Path'], item['KodiPathId'], item['PremiereDate'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'])
            self.emby_db.add_reference(item['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "Movie", "movie", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
            self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "movie")
            self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemIds'][ItemIndex], "movie")
            self.video_db.add_genres_and_links(item['Genres'], item['KodiItemIds'][ItemIndex], "movie")

            if item['CriticRating']:
                item['CriticRating'] = float(item['CriticRating'] / 10.0)
                self.video_db.add_ratings(item['KodiItemIds'][ItemIndex], "movie", "tomatometerallcritics", item['CriticRating'])

            self.video_db.add_tags_and_links(item['KodiItemIds'][ItemIndex], "movie", item['TagItems'])
            self.emby_db.add_multiversion(item, "Movie", self.EmbyServer.API, self.video_db, ItemIndex)

        # Add Special features
        if 'SpecialFeatureCount' in item:
            if int(item['SpecialFeatureCount']):
                SpecialFeatures = self.EmbyServer.API.get_specialfeatures(item['Id'])

                for SF_item in SpecialFeatures:
                    eSF_item = self.emby_db.get_item_by_id(SF_item['Id'])
                    common.get_streams(SF_item)
                    SF_item['ParentId'] = item['Id']
                    SF_item['Library'] = item['Library']
                    SF_item['ServerId'] = item['ServerId']
                    SF_item['KodiFileIds'] = item['KodiFileIds']
                    SF_item['KodiItemIds'] = item['KodiItemIds']
                    SF_item['LibraryIds'] = item['LibraryIds']
                    SF_item['IntroStartPositionTicks'] = None
                    SF_item['IntroEndPositionTicks'] = None
                    SF_item['CreditsPositionTicks'] = None
                    common.SwopMediaSources(SF_item)  # 3D
                    common.get_file_path(SF_item, "movies", ItemIndex)

                    if not SF_item['FullPath']:  # Invalid Path
                        LOG.error("Invalid path: %s" % SF_item['Id'])
                        LOG.debug("Invalid path: %s" % SF_item)
                        return False

                    SF_item['KodiItemIds'][ItemIndex] = None
                    SF_item['KodiFileIds'][ItemIndex] = None
                    SF_item['KodiPathId'] = None

                    if not eSF_item:
                        common.get_filename(SF_item, "vm", self.EmbyServer.API, ItemIndex)
                        self.emby_db.add_reference(SF_item['Id'], [], [], None, "SpecialFeature", None, [], item['LibraryIds'], item['Id'], SF_item['PresentationUniqueKey'], SF_item['UserData']['IsFavorite'], SF_item['EmbyPath'], None, None, None)
                        LOG.info("ADD SpecialFeature %s: %s" % (SF_item['Id'], SF_item['Name']))

                    self.emby_db.add_streamdata(SF_item['Id'], SF_item['Streams'])

            if item['UpdateItems'][ItemIndex]:
                LOG.info("UPDATE movie [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))
            else:
                LOG.info("ADD movie [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))

        return not item['UpdateItems'][ItemIndex]

    def boxset(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        MoviesAssignedToBoxset = self.EmbyServer.API.get_Items(item['Id'], ["Movie", "Video"], True, True, {})

        for ItemIndex in range(len(item['Librarys'])):
            common.set_overview(item)

            if item['UpdateItems'][ItemIndex]:
                self.video_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "set")
                self.video_db.update_boxset(item['Name'], item['Overview'], item['KodiItemIds'][ItemIndex])
            else:
                LOG.debug("SetId %s not found" % item['Id'])
                item['KodiItemIds'][ItemIndex] = self.video_db.add_boxset(item['Name'], item['Overview'])

            # BoxSets
            CurrentBoxSetMovies = self.emby_db.get_item_by_parent_id(item['KodiItemIds'][ItemIndex], "movie")

            if CurrentBoxSetMovies:
                CurrentBoxSetMovies = dict(CurrentBoxSetMovies)
            else:
                CurrentBoxSetMovies = {}

            for MovieAssignedToBoxset in MoviesAssignedToBoxset:
                MovieID = int(MovieAssignedToBoxset['Id'])

                if MovieID not in CurrentBoxSetMovies:
                    Data = self.emby_db.get_item_by_id(MovieAssignedToBoxset['Id'])

                    if not Data:
                        LOG.info("Failed to process %s to boxset." % MovieAssignedToBoxset['Name'])
                        continue

                    self.video_db.set_boxset(item['KodiItemIds'][ItemIndex], Data[0])
                    KodiItemIds = len(Data[6].split(";")) * [str(item['KodiItemIds'][ItemIndex])] # Data[6] -> EmbyLibraryId
                    KodiItemIds = ";".join(KodiItemIds)
                    self.emby_db.update_parent_id(KodiItemIds, MovieAssignedToBoxset['Id'])
                    LOG.info("ADD to boxset [%s/%s] %s: %s to boxset" % (item['KodiItemIds'][ItemIndex], Data[0], MovieAssignedToBoxset['Name'], MovieAssignedToBoxset['Id']))
                else:
                    del CurrentBoxSetMovies[MovieID]

            for EmbyMovieId in CurrentBoxSetMovies:
                self.video_db.remove_from_boxset(CurrentBoxSetMovies[EmbyMovieId])
                self.emby_db.update_parent_id(None, EmbyMovieId)
                LOG.info("DELETE from boxset [%s] %s %s: %s" % (item['Id'], item['KodiItemIds'][ItemIndex], item['Name'], CurrentBoxSetMovies[EmbyMovieId]))

            common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
            self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "set")
            item['KodiItemIds'][ItemIndex] = item['KodiItemIds'][ItemIndex]
            self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "BoxSet", "set", [], item['LibraryIds'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
            LOG.info("UPDATE boxset [%s] %s %s" % (item['Id'], item['KodiItemIds'][ItemIndex], item['Name']))

        return True

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        Item['Library'] = {}

        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        if Item['PlayedPercentage'] and Item['PlayedPercentage']:
            RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
        else:
            RuntimeSeconds = 0

        common.set_userdata_update_data(Item)

        for ItemIndex in range(len(Item['Librarys'])):
            self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemIds'][ItemIndex], "movie")
            self.video_db.update_bookmark_playstate(Item['KodiFileIds'][ItemIndex], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
            self.emby_db.update_favourite(Item['IsFavorite'], Item['Id'])
            LOG.debug("New resume point %s: %s" % (Item['Id'], Item['PlaybackPositionTicks']))
            LOG.info("USERDATA [%s/%s] %s" % (Item['KodiFileIds'][ItemIndex], Item['KodiItemIds'][ItemIndex], Item['Id']))

    def remove(self, Item):
        if Item['Type'] == 'Movie':
            self.remove_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "Movie")

                if StackedIds: # multi version
                    LOG.info("DELETE multi version movies from embydb %s" % Item['Id'])

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['Movie'], False, False)

                        if StackedItem:
                            StackedItem['Library'] = Item['Library']
                            LOG.info("UPDATE remaining multi version movie %s" % StackedItem['Id'])
                            self.movie(StackedItem)  # update all remaining multiversion items
                        else:
                            self.emby_db.remove_item(StackedId[0], Item['Library']['Id'])
        elif Item['Type'] == 'BoxSet':
            self.remove_boxset(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])
        elif Item['Type'] == 'SpecialFeature':
            self.remove_specialfeature(Item['Id'], Item['Library']['Id'])

    def remove_specialfeature(self, EmbyItemId, EmbyLibraryId):
        self.emby_db.remove_item(EmbyItemId, EmbyLibraryId)
        LOG.info("DELETE specialfeature %s" % EmbyItemId)

    def remove_movie(self, KodiItemId, KodiFileId, EmbyItemId, EmbyLibraryId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "movie", EmbyLibraryId)
        self.video_db.delete_movie(KodiItemId, KodiFileId)
        LOG.info("DELETE movie [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

    def remove_boxset(self, KodiId, KodiFileId, EmbyItemId, EmbyLibrayId):
        for movie in self.emby_db.get_item_by_parent_id(KodiId, "movie"):
            self.video_db.remove_from_boxset(movie[1])
            self.emby_db.update_parent_id(None, movie[0])

        self.video_db.common.delete_artwork(KodiId, "set")
        self.video_db.delete_boxset(KodiId)
        self.emby_db.remove_item(EmbyItemId, EmbyLibrayId)
        LOG.info("DELETE boxset [%s/%s] %s" % (KodiId, KodiFileId, EmbyItemId))

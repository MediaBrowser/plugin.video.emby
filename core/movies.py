from helper import utils, loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.movies')


class Movies:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb

    def movie(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        common.SwopMediaSources(item)  # 3D

        if not common.get_file_path(item, "movies"):
            return False

        if item['ExistingItem']:
            update = True
            item['KodiItemId'] = item['ExistingItem'][0]
            item['KodiFileId'] = item['ExistingItem'][1]
            item['KodiPathId'] = item['ExistingItem'][2]
            self.video_db.delete_links_genres(item['KodiItemId'], "movie")
            self.video_db.delete_ratings(item['KodiItemId'], "movie")
            common.delete_ContentItemReferences(item['Id'], item['KodiItemId'], item['KodiFileId'], self.video_db, self.emby_db, "movie")
        else:
            update = False
            LOG.debug("MovieId %s not found" % item['Id'])
            item['KodiItemId'] = self.video_db.create_movie_entry()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], "movies")
            item['KodiFileId'] = self.video_db.create_entry_file()

        item['OriginalTitle'] = item.get('OriginalTitle', None)
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['CriticRating'] = item.get('CriticRating', None)
        item['ShortOverview'] = item.get('ShortOverview', None)
        common.set_mpaa(item)
        common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "movie", "m")
        self.video_db.add_link_tag(common.MediaTags[item['Library']['Name']], item['KodiItemId'], "movie")
        self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemId'], "movie")
        self.video_db.add_genres_and_links(item['Genres'], item['KodiItemId'], "movie")
        item['Unique'] = self.video_db.add_uniqueids(item['KodiItemId'], item['ProviderIds'], "movie", 'imdb')
        item['RatingId'] = self.video_db.add_ratings(item['KodiItemId'], "movie", "default", item['CommunityRating'])

        if item['CriticRating']:
            item['CriticRating'] = float(item['CriticRating'] / 10.0)
            self.video_db.add_ratings(item['KodiItemId'], "movie", "tomatometerallcritics", item['CriticRating'])

        if not item['ProductionLocations']:
            item['ProductionLocations'].append(None)

        # Trailer
        item['Trailer'] = ""

        if item['LocalTrailerCount']:
            for IntroLocal in self.EmbyServer.API.get_local_trailers(item['Id']):
                Filename = utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
                item['Trailer'] = "http://127.0.0.1:57342/V-%s-%s-%s-%s" % (self.EmbyServer.server_id, IntroLocal['Id'], IntroLocal['MediaSources'][0]['Id'], Filename)
                break

        if 'RemoteTrailers' in item:
            if item['RemoteTrailers']:
                try:
                    item['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % item['RemoteTrailers'][0]['Url'].rsplit('=', 1)[1]
                except:
                    LOG.error("Trailer not valid: %s" % item['Name'])

        if update:
            self.video_db.update_movie(item['Name'], item['Overview'], item['ShortOverview'], item['Taglines'][0], item['RatingId'], item['Writers'], item['KodiArtwork']['poster'], item['Unique'], item['SortName'], item['RunTimeTicks'], item['OfficialRating'], item['Genre'], item['Directors'], item['OriginalTitle'], item['Studio'], item['Trailer'], item['KodiArtwork']['fanart'].get('fanart'), item['ProductionLocations'][0], item['Path'], item['KodiPathId'], item['PremiereDate'], item['KodiItemId'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['KodiFileId'])
            self.emby_db.update_reference(item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Movie", "movie", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
            LOG.info("UPDATE movie [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileId'], item['KodiItemId'], item['Id'], item['Name']))
        else:
            self.video_db.add_movie(item['KodiItemId'], item['KodiFileId'], item['Name'], item['Overview'], item['ShortOverview'], item['Taglines'][0], item['RatingId'], item['Writers'], item['KodiArtwork']['poster'], item['Unique'], item['SortName'], item['RunTimeTicks'], item['OfficialRating'], item['Genre'], item['Directors'], item['OriginalTitle'], item['Studio'], item['Trailer'], item['KodiArtwork']['fanart'].get('fanart'), item['ProductionLocations'][0], item['Path'], item['KodiPathId'], item['PremiereDate'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'])
            self.emby_db.add_reference(item['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Movie", "movie", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD movie [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileId'], item['KodiItemId'], item['Id'], item['Name']))

        self.video_db.add_tags_and_links(item['KodiItemId'], "movie", item['TagItems'])

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
                    common.SwopMediaSources(SF_item)  # 3D
                    common.get_file_path(SF_item, "movies")

                    if not SF_item['FullPath']:  # Invalid Path
                        LOG.error("Invalid path: %s" % SF_item['Id'])
                        LOG.debug("Invalid path: %s" % SF_item)
                        return False

                    SF_item['KodiItemId'] = None
                    SF_item['KodiFileId'] = None
                    SF_item['KodiPathId'] = None

                    if eSF_item:
                        self.emby_db.remove_item_streaminfos(SF_item['Id'])
                        common.get_filename(SF_item, "vm", self.EmbyServer.API)
                        self.emby_db.update_reference(SF_item['KodiItemId'], SF_item['KodiFileId'], SF_item['KodiPathId'], "SpecialFeature", None, None, SF_item['Library']['Id'], SF_item['ParentId'], SF_item['PresentationUniqueKey'], SF_item['UserData']['IsFavorite'], SF_item['Id'])
                        LOG.info("UPDATE SpecialFeature %s: %s" % (SF_item['Id'], SF_item['Name']))
                    else:
                        common.get_filename(SF_item, "vm", self.EmbyServer.API)
                        self.emby_db.add_reference(SF_item['Id'], SF_item['KodiItemId'], SF_item['KodiFileId'], SF_item['KodiPathId'], "SpecialFeature", None, None, SF_item['Library']['Id'], SF_item['ParentId'], SF_item['PresentationUniqueKey'], SF_item['UserData']['IsFavorite'])
                        LOG.info("ADD SpecialFeature %s: %s" % (SF_item['Id'], SF_item['Name']))

                    self.emby_db.add_streamdata(SF_item['Id'], SF_item['Streams'])

        self.emby_db.add_multiversion(item, "Movie", self.EmbyServer.API, self.video_db, update)
        return not update

    def boxset(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        common.set_overview(item)

        if item['ExistingItem']:
            item['KodiSetId'] = item['ExistingItem'][0]
            self.video_db.common.delete_artwork(item['KodiSetId'], "set")
            self.video_db.update_boxset(item['Name'], item['Overview'], item['KodiSetId'])
        else:
            LOG.debug("SetId %s not found" % item['Id'])
            item['KodiSetId'] = self.video_db.add_boxset(item['Name'], item['Overview'])

        # BoxSets
        CurrentBoxSetMovies = self.emby_db.get_item_id_by_parent_id(item['KodiSetId'])

        if CurrentBoxSetMovies:
            CurrentBoxSetMovies = dict(CurrentBoxSetMovies)
        else:
            CurrentBoxSetMovies = {}

        for movie in self.EmbyServer.API.get_Items(item['Id'], ["Movie"], True, True, {}, False, False):
            MovieID = int(movie['Id'])

            if MovieID not in CurrentBoxSetMovies:
                Data = self.emby_db.get_item_by_id(movie['Id'])

                if not Data:
                    LOG.info("Failed to process %s to boxset." % movie['Name'])
                    continue

                self.video_db.set_boxset(item['KodiSetId'], Data[0])
                self.emby_db.update_parent_id(item['KodiSetId'], movie['Id'])
                LOG.info("ADD to boxset [%s/%s] %s: %s to boxset" % (item['KodiSetId'], Data[0], movie['Name'], movie['Id']))
            else:
                del CurrentBoxSetMovies[MovieID]

        for EmbyMovieId in CurrentBoxSetMovies:
            self.video_db.remove_from_boxset(CurrentBoxSetMovies[EmbyMovieId])
            self.emby_db.update_parent_id(None, EmbyMovieId)
            LOG.info("DELETE from boxset [%s] %s %s: %s" % (item['Id'], item['KodiSetId'], item['Name'], CurrentBoxSetMovies[EmbyMovieId]))

        common.set_KodiArtwork(item, self.EmbyServer.server_id)
        self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiSetId'], "set")
        self.emby_db.add_reference(item['Id'], item['KodiSetId'], None, None, "BoxSet", "set", None, item['Library']['Id'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
        LOG.info("UPDATE boxset [%s] %s %s" % (item['Id'], item['KodiSetId'], item['Name']))
        return True

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        if Item['PlayedPercentage']:
            RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
        else:
            RuntimeSeconds = 0

        common.set_userdata_update_data(Item)
        self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemId'], "movie")
        self.video_db.update_bookmark_playstate(Item['KodiFileId'], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
        self.emby_db.update_reference_userdatachanged(Item['IsFavorite'], Item['Id'])
        LOG.debug("New resume point %s: %s" % (Item['Id'], Item['PlaybackPositionTicks']))
        LOG.info("USERDATA [%s/%s] %s" % (Item['KodiFileId'], Item['KodiItemId'], Item['Id']))

    # Remove movieid, fileid, emby reference.
    # Remove artwork, boxset
    def remove(self, Item):
        if Item['Type'] == 'Movie':
            self.remove_movie(Item['KodiItemId'], Item['KodiFileId'], Item['Id'])

            if not Item['DeleteByLibraryId']:
                StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "Movie")

                if StackedIds: # multi version
                    LOG.info("DELETE multi version movies from embydb %s" % Item['Id'])

                    for StackedId in StackedIds:
                        self.emby_db.remove_item(StackedId[0])

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['Movie'], False, False)

                        if StackedItem:
                            StackedItem['Library'] = Item['Library']
                            LOG.info("UPDATE remaining multi version movie %s" % StackedItem['Id'])
                            self.movie(StackedItem)  # update all stacked items
        elif Item['Type'] == 'BoxSet':
            self.remove_boxset(Item['KodiItemId'], Item['KodiFileId'], Item['Id'])
        elif Item['Type'] == 'SpecialFeature':
            self.remove_specialfeature(Item['Id'])

    def remove_specialfeature(self, EmbyItemId):
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE specialfeature %s" % EmbyItemId)

    def remove_movie(self, KodiItemId, KodiFileId, EmbyItemId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "movie")
        self.video_db.delete_movie(KodiItemId, KodiFileId)
        LOG.info("DELETE movie [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

    def remove_boxset(self, KodiId, KodiFileId, EmbyItemId):
        for movie in self.emby_db.get_item_by_parent_id(KodiId, "movie"):
            self.video_db.remove_from_boxset(movie[1])
            self.emby_db.update_parent_id(None, movie[0])

        self.video_db.common.delete_artwork(KodiId, "set")
        self.video_db.delete_boxset(KodiId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE boxset [%s/%s] %s" % (KodiId, KodiFileId, EmbyItemId))

# -*- coding: utf-8 -*-
import helper.loghandler
import helper.utils as Utils
import emby.obj_ops as Objects
from . import common as Common

LOG = helper.loghandler.LOG('EMBY.core.movies.Movies')


class Movies:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb

    def movie(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'Movie')
        obj['Emby_Type'] = 'Movie'
        obj['Item'] = item
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['ServerId'] = self.EmbyServer.server_id
        obj['FullPath'] = Common.SwopMediaSources(obj, item)  # 3D

        if not obj['FullPath']:  # Invalid Path
            LOG.error("Invalid path: %s" % obj['Id'])
            LOG.debug("Invalid path: %s" % obj)
            return False

        if e_item:
            update = True
            obj['KodiMovieId'] = e_item[0]
            obj['KodiFileId'] = e_item[1]
            obj['KodiPathId'] = e_item[2]
        else:
            update = False
            LOG.debug("MovieId %s not found" % obj['Id'])
            obj['KodiMovieId'] = self.video_db.create_movie_entry()

        obj['Path'] = Common.get_path(obj, "movies")
        obj['Genres'] = obj['Genres'] or []
        obj['Studio'] = " / ".join(obj['Studios'] or [])
        obj['People'] = obj['People'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = Common.get_overview(obj['Plot'], item)
        obj['Mpaa'] = Common.get_mpaa(obj['Mpaa'], item)
        obj['Resume'] = Common.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = Common.get_people_artwork(obj['People'], self.EmbyServer.server_id)
        obj['DateAdded'] = Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if not obj['Premiere']:
            obj['Premiere'] = Utils.convert_to_local(obj['Year'])

        obj['DatePlayed'] = None if not obj['DatePlayed'] else Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, self.EmbyServer.server_id)
        obj['Video'] = Common.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = Common.audio_streams(obj['Audio'] or [])
        obj['Streams'] = Common.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])

        # Trailer
        if obj['LocalTrailer']:
            for IntroLocal in self.EmbyServer.API.get_local_trailers(obj['Id']):
                IntroLocalFilename = Utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
                obj['Trailer'] = "http://127.0.0.1:57578/embytrailerlocal-%s-%s-%s-%s-%s" % (self.EmbyServer.server_id, IntroLocal['Id'], IntroLocal['MediaSources'][0]['Id'], "video", IntroLocalFilename)
                break
        elif obj['Trailer']:
            try:
                obj['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % obj['Trailer'].rsplit('=', 1)[1]
            except:
                obj['Trailer'] = None

        if obj['Countries']:
            self.video_db.add_countries(obj['Countries'], obj['KodiMovieId'], "movie")

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite movies')

        obj['Tags'] = tags
        Common.Streamdata_add(obj, self.emby_db, update)

        if update:
            obj['RatingId'] = self.video_db.get_rating_id("movie", obj['KodiMovieId'], "default")
            self.video_db.update_ratings(obj['KodiMovieId'], "movie", "default", obj['Rating'], obj['RatingId'])

            if obj['CriticRating'] is not None:
                obj['CriticRating'] = float(obj['CriticRating'] / 10.0)
                RatingId = self.video_db.get_rating_id("movie", obj['KodiMovieId'], "tomatometerallcritics")
                self.video_db.update_ratings(obj['KodiMovieId'], "movie", "tomatometerallcritics", obj['CriticRating'], RatingId)

            self.video_db.remove_unique_ids(obj['KodiMovieId'], "movie")
            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiMovieId'], "movie", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'imdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiMovieId'], "movie", unique_id, provider)

            if Utils.userRating:
                self.video_db.update_movie(obj['Title'], obj['Plot'], obj['ShortPlot'], obj['Tagline'], obj['RatingId'], obj['Writers'], obj['Year'], obj['Unique'], obj['SortTitle'], obj['Runtime'], obj['Mpaa'], obj['Genre'], obj['Directors'], obj['OriginalTitle'], obj['Studio'], obj['Trailer'], obj['Country'], obj['CriticRating'], obj['Premiere'], obj['KodiMovieId'])
            else:
                self.video_db.update_movie_nouserrating(obj['Title'], obj['Plot'], obj['ShortPlot'], obj['Tagline'], obj['RatingId'], obj['Writers'], obj['Year'], obj['Unique'], obj['SortTitle'], obj['Runtime'], obj['Mpaa'], obj['Genre'], obj['Directors'], obj['OriginalTitle'], obj['Studio'], obj['Trailer'], obj['Country'], obj['Premiere'], obj['KodiMovieId'])

            obj['Filename'] = Common.get_filename(obj, "movies", self.EmbyServer.API)
            self.video_db.update_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])
            self.emby_db.update_reference(obj['PresentationKey'], obj['Favorite'], obj['Id'])
            LOG.info("UPDATE movie [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiFileId'], obj['KodiMovieId'], obj['Id'], obj['Title']))
        else:
            obj['RatingId'] = self.video_db.create_entry_rating()
            self.video_db.add_ratings(obj['RatingId'], obj['KodiMovieId'], "movie", "default", obj['Rating'])

            if obj['CriticRating'] is not None:
                obj['CriticRating'] = float(obj['CriticRating'] / 10.0)
                RatingId = self.video_db.create_entry_rating()
                self.video_db.add_ratings(RatingId, obj['KodiMovieId'], "movie", "tomatometerallcritics", obj['CriticRating'])

            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiMovieId'], "movie", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'imdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiMovieId'], "movie", unique_id, provider)

            obj['KodiPathId'] = self.video_db.get_add_path(obj['Path'], "movies")
            obj['KodiFileId'] = self.video_db.create_entry_file()
            obj['Filename'] = Common.get_filename(obj, "movies", self.EmbyServer.API)
            self.video_db.add_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])

            if Utils.userRating:
                self.video_db.add_movie(obj['KodiMovieId'], obj['KodiFileId'], obj['Title'], obj['Plot'], obj['ShortPlot'], obj['Tagline'], obj['RatingId'], obj['Writers'], obj['Year'], obj['Unique'], obj['SortTitle'], obj['Runtime'], obj['Mpaa'], obj['Genre'], obj['Directors'], obj['OriginalTitle'], obj['Studio'], obj['Trailer'], obj['Country'], obj['CriticRating'], obj['Premiere'])
            else:
                self.video_db.add_movie_nouserrating(obj['KodiMovieId'], obj['KodiFileId'], obj['Title'], obj['Plot'], obj['ShortPlot'], obj['Tagline'], obj['RatingId'], obj['Writers'], obj['Year'], obj['Unique'], obj['SortTitle'], obj['Runtime'], obj['Mpaa'], obj['Genre'], obj['Directors'], obj['OriginalTitle'], obj['Studio'], obj['Trailer'], obj['Country'], obj['Premiere'])

            self.emby_db.add_reference(obj['Id'], obj['KodiMovieId'], obj['KodiFileId'], obj['KodiPathId'], "Movie", "movie", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD movie [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiFileId'], obj['KodiMovieId'], obj['Id'], obj['Title']))

        self.video_db.add_tags(obj['Tags'], obj['KodiMovieId'], "movie")
        self.video_db.add_genres(obj['Genres'], obj['KodiMovieId'], "movie")
        self.video_db.add_studios(obj['Studios'], obj['KodiMovieId'], "movie")
        self.video_db.add_playstate(obj['KodiFileId'], obj['PlayCount'], obj['DatePlayed'], obj['Resume'], obj['Runtime'], "DVDPlayer", 1)
        self.video_db.add_people(obj['People'], obj['KodiMovieId'], "movie")
        self.video_db.add_streams(obj['KodiFileId'], obj['Streams'], obj['Runtime'])
        self.video_db.common_db.add_artwork(obj['Artwork'], obj['KodiMovieId'], "movie")

        if "StackTimes" in obj:
            self.video_db.add_stacktimes(obj['KodiFileId'], obj['StackTimes'])

        # Add Special features
        if 'SpecialFeatureCount' in obj['Item']:
            if int(obj['Item']['SpecialFeatureCount']):
                SpecialFeatures = self.EmbyServer.API.get_specialfeatures(obj['Id'])

                for SpecialFeature_item in SpecialFeatures:
                    eSF_item = self.emby_db.get_item_by_id(SpecialFeature_item['Id'])
                    objF = Objects.mapitem(SpecialFeature_item, 'Movie')
                    objF['EmbyParentId'] = obj['Id']
                    objF['Item'] = SpecialFeature_item
                    objF['LibraryId'] = library['Id']
                    objF['LibraryName'] = library['Name']
                    objF['ServerId'] = self.EmbyServer.server_id
                    objF['FullPath'] = Common.SwopMediaSources(objF, item)  # 3D

                    if not objF['FullPath']:  # Invalid Path
                        LOG.error("Invalid path: %s" % objF['Id'])
                        LOG.debug("Invalid path: %s" % objF)
                        return False

                    objF['Path'] = Common.get_path(objF, "movies")
                    objF['KodiMovieId'] = None
                    objF['KodiFileId'] = None
                    objF['KodiPathId'] = None

                    if eSF_item:
                        Common.Streamdata_add(objF, self.emby_db, True)
                        objF['Filename'] = Common.get_filename(objF, "movies", self.EmbyServer.API)
                        self.emby_db.update_reference(objF['PresentationKey'], objF['Favorite'], objF['Id'])
                        LOG.info("UPDATE SpecialFeature %s: %s" % (objF['Id'], objF['Title']))
                    else:
                        Common.Streamdata_add(objF, self.emby_db, False)
                        objF['Filename'] = Common.get_filename(objF, "movies", self.EmbyServer.API)
                        self.emby_db.add_reference(objF['Id'], objF['KodiMovieId'], objF['KodiFileId'], objF['KodiPathId'], "SpecialFeature", None, None, objF['LibraryId'], objF['EmbyParentId'], objF['PresentationKey'], objF['Favorite'])
                        LOG.info("ADD SpecialFeature %s: %s" % (objF['Id'], objF['Title']))

        Common.add_Multiversion(obj, self.emby_db, "Movie", self.EmbyServer.API)
        return not update

    def boxset(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'Boxset')
        obj['LibraryId'] = library['Id']
        obj['Overview'] = Common.get_overview(obj['Overview'], item)
        obj['Checksum'] = obj['Etag']

        if e_item:
            obj['SetId'] = e_item[0]
            self.video_db.update_boxset(obj['Title'], obj['Overview'], obj['SetId'])
        else:
            LOG.debug("SetId %s not found" % obj['Id'])
            obj['SetId'] = self.video_db.add_boxset(obj['Title'], obj['Overview'])

        # BoxSets
        try:
            current = self.emby_db.get_item_id_by_parent_id(obj['SetId'], "movie")
            movies = dict(current)
        except ValueError:
            movies = {}

        obj['Current'] = movies

        for all_movies in self.EmbyServer.API.get_movies_by_boxset(obj['Id']):
            for movie in all_movies['Items']:
                Data = self.emby_db.get_item_by_id(movie['Id'])

                if not Data:
                    LOG.info("Failed to process %s to boxset." % movie['Name'])
                    continue

                if movie['Id'] not in obj['Current']:
                    self.video_db.set_boxset(obj['SetId'], Data[0])
                    self.emby_db.update_parent_id(obj['SetId'], movie['Id'])
                    LOG.info("ADD to boxset [%s/%s] %s: %s to boxset" % (obj['SetId'], Data[0], movie['Name'], movie['Id']))
                else:
                    obj['Current'].pop(movie['Id'])

        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, self.EmbyServer.server_id)

        for movie in obj['Current']:
            self.video_db.remove_from_boxset(obj['Current'][movie])
            self.emby_db.update_parent_id(None, movie)
            LOG.info("DELETE from boxset [%s] %s: %s" % (obj['SetId'], obj['Title'], obj['Current'][movie]))

        self.video_db.common_db.add_artwork(obj['Artwork'], obj['SetId'], "set")
        self.emby_db.add_reference(obj['Id'], obj['SetId'], None, None, "BoxSet", "set", None, obj['LibraryId'], None, obj['PresentationKey'], obj['Favorite'])
        LOG.info("UPDATE boxset [%s] %s" % (obj['SetId'], obj['Title']))
        return True

    # Special function to remove all existing boxsets
    def boxsets_reset(self, library_id):
        boxsets = self.emby_db.get_items_by_media('set', library_id)

        for boxset in boxsets:
            self.remove(boxset[0])

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, e_item, ItemUserdata):
        KodiMovieId = e_item[0]
        KodiFileId = e_item[1]
        Resume = Common.adjust_resume((ItemUserdata['PlaybackPositionTicks'] or 0) / 10000000.0)
        MovieData = self.video_db.get_movie_data(KodiMovieId)
        Runtime = round(float(MovieData[13]) / 10000000.0, 6)
        PlayCount = Common.get_playcount(ItemUserdata['Played'], ItemUserdata['PlayCount'])
        DatePlayed = Utils.currenttime()

        if ItemUserdata['IsFavorite']:
            self.video_db.get_tag("Favorite movies", KodiMovieId, "movie")
        else:
            self.video_db.remove_tag("Favorite movies", KodiMovieId, "movie")

        LOG.debug("New resume point %s: %s" % (ItemUserdata['ItemId'], Resume))
        self.video_db.add_playstate(KodiFileId, PlayCount, DatePlayed, Resume, Runtime, "DVDPlayer", 1)
        self.emby_db.update_reference_userdatachanged(ItemUserdata['IsFavorite'], ItemUserdata['ItemId'])
        LOG.info("USERDATA [%s/%s] %s: %s" % (KodiFileId, KodiMovieId, ItemUserdata['ItemId'], MovieData[2]))

    # Remove movieid, fileid, emby reference.
    # Remove artwork, boxset
    def remove(self, EmbyItemId):
        e_item = self.emby_db.get_item_by_id(EmbyItemId)

        if e_item:
            KodiId = e_item[0]
            KodiFileId = e_item[1]
            KodiType = e_item[4]
            EmbyType = e_item[5]
            emby_presentation_key = e_item[8]
            emby_folder = e_item[6]
        else:
            return

        if KodiType == 'movie':
            StackedIds = self.emby_db.get_stacked_embyid(emby_presentation_key, emby_folder, "Movie")

            if len(StackedIds) > 1:
                self.emby_db.remove_item(EmbyItemId)
                LOG.info("DELETE stacked movie from embydb %s" % EmbyItemId)

                for StackedId in StackedIds:
                    StackedItem = self.EmbyServer.API.get_item_multiversion(StackedId[0])

                    if StackedItem:
                        library_name = self.emby_db.get_Libraryname_by_Id(emby_folder)
                        LibraryData = {"Id": emby_folder, "Name": library_name}
                        LOG.info("UPDATE remaining stacked movie from embydb %s" % StackedItem['Id'])
                        self.movie(StackedItem, LibraryData)  # update all stacked items
            else:
                self.remove_movie(KodiId, KodiFileId, EmbyItemId)
        elif KodiType == 'set':
            self.remove_boxset(KodiId, KodiFileId, EmbyItemId)
        elif EmbyType == 'SpecialFeature':
            self.remove_specialfeature(EmbyItemId)

    def remove_specialfeature(self, EmbyItemId):
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE specialfeature %s" % EmbyItemId)

    def remove_movie(self, KodiId, KodiFileId, EmbyItemId):
        self.video_db.common_db.delete_artwork(KodiId, "movie")
        self.video_db.delete_movie(KodiId, KodiFileId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE movie [%s/%s] %s" % (KodiId, KodiFileId, EmbyItemId))

    def remove_boxset(self, KodiId, KodiFileId, EmbyItemId):
        for movie in self.emby_db.get_item_by_parent_id(KodiId, "movie"):
            self.video_db.remove_from_boxset(movie[1])
            self.emby_db.update_parent_id(None, movie[0])

        self.video_db.common_db.delete_artwork(KodiId, "set")
        self.video_db.delete_boxset(KodiId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE boxset [%s/%s] %s" % (KodiId, KodiFileId, EmbyItemId))

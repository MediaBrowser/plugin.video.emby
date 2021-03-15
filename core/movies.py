# -*- coding: utf-8 -*-
import logging

import emby.downloader
import helper.wrapper
import helper.api
import database.emby_db
import database.queries
from . import obj_ops
from . import kodi
from . import queries_videos
from . import artwork
from . import common

class Movies():
    def __init__(self, server, embydb, videodb, direct_path, Utils):
        self.LOG = logging.getLogger("EMBY.core.movies.Movies")
        self.Utils = Utils
        self.server = server
        self.emby = embydb
        self.video = videodb
        self.direct_path = direct_path
        self.emby_db = database.emby_db.EmbyDatabase(embydb.cursor)
        self.objects = obj_ops.Objects(self.Utils)
        self.item_ids = []
        self.Downloader = emby.downloader.Downloader(self.Utils)
        self.Common = common.Common(self.emby_db, self.objects, self.Utils, self.direct_path, self.server)
        self.KodiDBIO = kodi.Kodi(videodb.cursor)
        self.MoviesDBIO = MoviesDBIO(videodb.cursor)
        self.ArtworkDBIO = artwork.Artwork(videodb.cursor, self.Utils)

    def __getitem__(self, key):
        if key == 'Movie':
            return self.movie
        elif key == 'BoxSet':
            return self.boxset


    #If item does not exist, entry will be added.
    #If item exists, entry will be updated
    @helper.wrapper.stop
    def movie(self, item, library=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Movie')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True
        StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

        if str(StackedID) != obj['Id']:
            self.LOG.info("Skipping stacked movie %s [%s/%s]", obj['Title'], StackedID, obj['Id'])
            Movies(self.server, self.emby, self.video, self.direct_path, self.Utils).remove(StackedID)

        try:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError:
            update = False
            self.LOG.debug("MovieId %s not found", obj['Id'])
            obj['MovieId'] = self.MoviesDBIO.create_entry()
        else:
            if self.MoviesDBIO.get(*self.Utils.values(obj, queries_videos.get_movie_obj)) is None:
                update = False
                self.LOG.info("MovieId %s missing from kodi. repairing the entry.", obj['MovieId'])

        obj['Item']['MediaSources'][0] = self.objects.MapMissingData(obj['Item']['MediaSources'][0], 'MediaSources')
        obj['MediaSourceID'] = obj['Item']['MediaSources'][0]['Id']
        obj['Runtime'] = obj['Item']['MediaSources'][0]['RunTimeTicks']

        if obj['Item']['MediaSources'][0]['Path']:
            obj['Path'] = obj['Item']['MediaSources'][0]['Path']

            #don't use 3d movies as default
            if "3d" in self.Utils.StringMod(obj['Item']['MediaSources'][0]['Path']):
                for DataSource in obj['Item']['MediaSources']:
                    if not "3d" in self.Utils.StringMod(DataSource['Path']):
                        DataSource = self.objects.MapMissingData(DataSource, 'MediaSources')
                        obj['Path'] = DataSource['Path']
                        obj['MediaSourceID'] = DataSource['Id']
                        obj['Runtime'] = DataSource['RunTimeTicks']
                        break

        obj['Path'] = API.get_file_path(obj['Path'])
        obj['Genres'] = obj['Genres'] or []
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['People'] = obj['People'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Mpaa'] = API.get_mpaa(obj['Mpaa'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = API.get_people_artwork(obj['People'])
        obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['Premiered'] = self.Utils.convert_to_local(obj['Year']) if not obj['Premiered'] else self.Utils.convert_to_local(obj['Premiered']).replace(" ", "T").split('T')[0]
        obj['DatePlayed'] = None if not obj['DatePlayed'] else self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj = self.Common.get_path_filename(obj, "movies")
        self.trailer(obj)

        if obj['Countries']:
            self.MoviesDBIO.add_countries(*self.Utils.values(obj, queries_videos.update_country_obj))

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite movies')

        obj['Tags'] = tags

        if update:
            self.movie_update(obj)
        else:
            self.movie_add(obj)

        self.KodiDBIO.update_path(*self.Utils.values(obj, queries_videos.update_path_movie_obj))
        self.KodiDBIO.update_file(*self.Utils.values(obj, queries_videos.update_file_obj))
        self.KodiDBIO.add_tags(*self.Utils.values(obj, queries_videos.add_tags_movie_obj))
        self.KodiDBIO.add_genres(*self.Utils.values(obj, queries_videos.add_genres_movie_obj))
        self.KodiDBIO.add_studios(*self.Utils.values(obj, queries_videos.add_studios_movie_obj))
        self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.KodiDBIO.add_people(*self.Utils.values(obj, queries_videos.add_people_movie_obj))
        self.KodiDBIO.add_streams(*self.Utils.values(obj, queries_videos.add_streams_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['MovieId'], "movie")
        self.item_ids.append(obj['Id'])

        if "StackTimes" in obj:
            self.KodiDBIO.add_stacktimes(*self.Utils.values(obj, queries_videos.add_stacktimes_obj))

        return not update

    #Add object to kodi
    def movie_add(self, obj):
        obj = self.Common.Streamdata_add(obj, False)
        obj['RatingType'] = "default"
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.Utils.values(obj, queries_videos.add_rating_movie_obj))

        if obj['CriticRating'] is not None:
            self.KodiDBIO.add_ratings(*self.Utils.values(dict(obj, RatingId=self.KodiDBIO.create_entry_rating(), RatingType="tomatometerallcritics", Rating=float(obj['CriticRating']/10.0)), queries_videos.add_rating_movie_obj))

        obj['Unique'] = self.MoviesDBIO.create_entry_unique_id()
        self.MoviesDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_movie_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'imdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.MoviesDBIO.create_entry_unique_id())
                self.MoviesDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_movie_obj))

        obj['PathId'] = self.KodiDBIO.add_path(*self.Utils.values(obj, queries_videos.add_path_obj))
        obj['FileId'] = self.KodiDBIO.add_file(*self.Utils.values(obj, queries_videos.add_file_obj))
        self.MoviesDBIO.add(*self.Utils.values(obj, queries_videos.add_movie_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_movie_obj))
        self.LOG.info("ADD movie [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    #Update object to kodi
    def movie_update(self, obj):
        obj = self.Common.Streamdata_add(obj, True)
        obj['RatingType'] = "default"
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.Utils.values(obj, queries_videos.get_rating_movie_obj))
        self.KodiDBIO.update_ratings(*self.Utils.values(obj, queries_videos.update_rating_movie_obj))

        if obj['CriticRating'] is not None:
            temp_obj = dict(obj, RatingType="tomatometerallcritics", Rating=float(obj['CriticRating']/10.0))
            temp_obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.Utils.values(temp_obj, queries_videos.get_rating_movie_obj))
            self.KodiDBIO.update_ratings(*self.Utils.values(temp_obj, queries_videos.update_rating_movie_obj))

        self.KodiDBIO.remove_unique_ids(*self.Utils.values(obj, queries_videos.delete_unique_ids_movie_obj))
        obj['Unique'] = self.MoviesDBIO.create_entry_unique_id()
        self.MoviesDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_movie_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'imdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.MoviesDBIO.create_entry_unique_id())
                self.MoviesDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_movie_obj))

        self.MoviesDBIO.update(*self.Utils.values(obj, queries_videos.update_movie_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE movie [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    def trailer(self, obj):
        try:
            if obj['LocalTrailer']:
                trailer = self.server['api'].get_local_trailers(obj['Id'])
                API = helper.api.API(trailer, self.Utils, self.server['auth/server-address'])

                if self.direct_path:
                    obj['Trailer'] = API.get_file_path(trailer[0]['Path'])
                    obj['Trailer'] = self.Utils.StringDecode(obj['Trailer'])
                else:
                    obj['Trailer'] = "plugin://plugin.video.emby-next-gen/trailer?id=%s&mode=play" % trailer[0]['Id']
            elif obj['Trailer']:
                obj['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % obj['Trailer'].rsplit('=', 1)[1]
        except Exception as error:
            self.LOG.error("Failed to get trailer: %s", error)
            obj['Trailer'] = None

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated.
    #Process movies inside boxset.
    #Process removals from boxset.
    @helper.wrapper.stop
    def boxset(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Boxset')
        obj['Overview'] = API.get_overview(obj['Overview'])
        obj['Checksum'] = obj['Etag']

        try:
            obj['SetId'] = e_item[0]
            self.MoviesDBIO.update_boxset(*self.Utils.values(obj, queries_videos.update_set_obj))
        except TypeError:
            self.LOG.debug("SetId %s not found", obj['Id'])
            obj['SetId'] = self.MoviesDBIO.add_boxset(*self.Utils.values(obj, queries_videos.add_set_obj))

        self.boxset_current(obj)
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        for movie in obj['Current']:
            temp_obj = dict(obj)
            temp_obj['Movie'] = movie
            temp_obj['MovieId'] = obj['Current'][temp_obj['Movie']]
            self.MoviesDBIO.remove_from_boxset(*self.Utils.values(temp_obj, queries_videos.delete_movie_set_obj))
            self.emby_db.update_parent_id(*self.Utils.values(temp_obj, database.queries.delete_parent_boxset_obj))
            self.LOG.info("DELETE from boxset [%s] %s: %s", temp_obj['SetId'], temp_obj['Title'], temp_obj['MovieId'])

        self.ArtworkDBIO.add(obj['Artwork'], obj['SetId'], "set")
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_boxset_obj))
        self.LOG.info("UPDATE boxset [%s] %s", obj['SetId'], obj['Title'])

    #Add or removes movies based on the current movies found in the boxset
    def boxset_current(self, obj):
        try:
            current = self.emby_db.get_item_id_by_parent_id(*self.Utils.values(obj, database.queries.get_item_id_by_parent_boxset_obj))
            movies = dict(current)
        except ValueError:
            movies = {}

        obj['Current'] = movies

        for all_movies in self.Downloader.get_movies_by_boxset(obj['Id']):
            for movie in all_movies['Items']:
                temp_obj = dict(obj)
                temp_obj['Title'] = movie['Name']
                temp_obj['Id'] = movie['Id']

                try:
                    temp_obj['MovieId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
                except TypeError:
                    self.LOG.info("Failed to process %s to boxset.", temp_obj['Title'])
                    continue

                if temp_obj['Id'] not in obj['Current']:
                    self.MoviesDBIO.set_boxset(*self.Utils.values(temp_obj, queries_videos.update_movie_set_obj))
                    self.emby_db.update_parent_id(*self.Utils.values(temp_obj, database.queries.update_parent_movie_obj))
                    self.LOG.info("ADD to boxset [%s/%s] %s: %s to boxset", temp_obj['SetId'], temp_obj['MovieId'], temp_obj['Title'], temp_obj['Id'])
                else:
                    obj['Current'].pop(temp_obj['Id'])

    #Special function to remove all existing boxsets
    def boxsets_reset(self):
        boxsets = self.emby_db.get_items_by_media('set')
        for boxset in boxsets:
            self.remove(boxset[0])

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    @helper.wrapper.stop
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'MovieUserData')
        obj['Item'] = item

        try:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
        except TypeError:
            return

        obj = self.Common.Streamdata_add(obj, True)
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

        if obj['DatePlayed']:
            obj['DatePlayed'] = self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Favorite']:
            self.KodiDBIO.get_tag(*self.Utils.values(obj, queries_videos.get_tag_movie_obj))
        else:
            self.KodiDBIO.remove_tag(*self.Utils.values(obj, queries_videos.delete_tag_movie_obj))

        self.LOG.debug("New resume point %s: %s", obj['Id'], obj['Resume'])
        self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA movie [%s/%s] %s: %s", obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    #Remove movieid, fileid, emby reference.
    #Remove artwork, boxset
    @helper.wrapper.stop
    def remove(self, item_id=None):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        self.ArtworkDBIO.delete(obj['KodiId'], obj['Media'])

        if obj['Media'] == 'movie':
            self.MoviesDBIO.delete(*self.Utils.values(obj, queries_videos.delete_movie_obj))
        elif obj['Media'] == 'set':
            for movie in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_movie_obj)):
                temp_obj = dict(obj)
                temp_obj['MovieId'] = movie[1]
                temp_obj['Movie'] = movie[0]
                self.MoviesDBIO.remove_from_boxset(*self.Utils.values(temp_obj, queries_videos.delete_movie_set_obj))
                self.emby_db.update_parent_id(*self.Utils.values(temp_obj, database.queries.delete_parent_boxset_obj))

            self.MoviesDBIO.delete_boxset(*self.Utils.values(obj, queries_videos.delete_set_obj))

        self.emby_db.remove_item(item_id)
        self.LOG.info("DELETE %s [%s/%s] %s", obj['Media'], obj['FileId'], obj['KodiId'], obj['Id'])

class MoviesDBIO():
    def __init__(self, cursor):
        self.cursor = cursor

    def create_entry_unique_id(self):
        self.cursor.execute(queries_videos.create_unique_id)
        return self.cursor.fetchone()[0] + 1

    def create_entry(self):
        self.cursor.execute(queries_videos.create_movie)
        return self.cursor.fetchone()[0] + 1

    def create_entry_set(self):
        self.cursor.execute(queries_videos.create_set)
        return self.cursor.fetchone()[0] + 1

    def create_entry_country(self):
        self.cursor.execute(queries_videos.create_country)
        return self.cursor.fetchone()[0] + 1

    def get(self, *args):
        try:
            self.cursor.execute(queries_videos.get_movie, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add(self, *args):
        self.cursor.execute(queries_videos.add_movie, args)

    def update(self, *args):
        self.cursor.execute(queries_videos.update_movie, args)

    def delete(self, kodi_id, file_id):
        self.cursor.execute(queries_videos.delete_movie, (kodi_id,))
        self.cursor.execute(queries_videos.delete_file, (file_id,))

#    def get_unique_id(self, *args):
#        try:
#            self.cursor.execute(queries_videos.get_unique_id, args)
#            return self.cursor.fetchone()[0]
#        except TypeError:
#            return

    # Add the provider id, imdb, tvdb
    def add_unique_id(self, *args):
        self.cursor.execute(queries_videos.add_unique_id, args)

     # Update the provider id, imdb, tvdb
#    def update_unique_id(self, *args):
#        self.cursor.execute(queries_videos.update_unique_id, args)

    def add_countries(self, countries, *args):
        for country in countries:
            self.cursor.execute(queries_videos.update_country, (self.get_country(country),) + args)

    def add_country(self, *args):
        country_id = self.create_entry_country()
        self.cursor.execute(queries_videos.add_country, (country_id,) + args)
        return country_id

    def get_country(self, *args):
        try:
            self.cursor.execute(queries_videos.get_country, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return self.add_country(*args)

    def add_boxset(self, *args):
        set_id = self.create_entry_set()
        self.cursor.execute(queries_videos.add_set, (set_id,) + args)
        return set_id

    def update_boxset(self, *args):
        self.cursor.execute(queries_videos.update_set, args)

    def set_boxset(self, *args):
        self.cursor.execute(queries_videos.update_movie_set, args)

    def remove_from_boxset(self, *args):
        self.cursor.execute(queries_videos.delete_movie_set, args)

    def delete_boxset(self, *args):
        self.cursor.execute(queries_videos.delete_set, args)

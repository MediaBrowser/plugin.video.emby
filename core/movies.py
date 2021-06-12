# -*- coding: utf-8 -*-
import helper.api
import helper.loghandler
import database.emby_db
import database.queries
from . import obj_ops
from . import kodi
from . import queries_videos
from . import artwork
from . import common

class Movies():
    def __init__(self, EmbyServer, embydb, videodb):
        self.LOG = helper.loghandler.LOG('EMBY.core.movies.Movies')
        self.EmbyServer = EmbyServer
        self.emby = embydb
        self.video = videodb
        self.emby_db = database.emby_db.EmbyDatabase(embydb.cursor)
        self.objects = obj_ops.Objects()
        self.Common = common.Common(self.emby_db, self.objects, self.EmbyServer)
        self.KodiDBIO = kodi.Kodi(videodb.cursor, self.EmbyServer.Utils)
        self.MoviesDBIO = MoviesDBIO(videodb.cursor)
        self.ArtworkDBIO = artwork.Artwork(videodb.cursor, self.EmbyServer.Utils)
        self.APIHelper = helper.api.API(self.EmbyServer.Utils)

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated
    def movie(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Movie')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True
        StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

        if str(StackedID) != obj['Id']:
            self.LOG.info("Skipping stacked movie %s [%s/%s]" % (obj['Title'], StackedID, obj['Id']))
            Movies(self.EmbyServer, self.emby, self.video).remove(StackedID)

        if e_item:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]

            if self.MoviesDBIO.get(*self.EmbyServer.Utils.values(obj, queries_videos.get_movie_obj)) is None:
                update = False
                self.LOG.info("MovieId %s missing from kodi. repairing the entry." % obj['MovieId'])
        else:
            update = False
            self.LOG.debug("MovieId %s not found" % obj['Id'])
            obj['MovieId'] = self.MoviesDBIO.create_entry()

        obj['Item']['MediaSources'][0] = self.objects.MapMissingData(obj['Item']['MediaSources'][0], 'MediaSources')
        obj['MediaSourceID'] = obj['Item']['MediaSources'][0]['Id']
        obj['Runtime'] = obj['Item']['MediaSources'][0]['RunTimeTicks']

        if obj['Item']['MediaSources'][0]['Path']:
            obj['Path'] = obj['Item']['MediaSources'][0]['Path']

            #don't use 3d movies as default
            if "3d" in self.EmbyServer.Utils.StringMod(obj['Item']['MediaSources'][0]['Path']):
                for DataSource in obj['Item']['MediaSources']:
                    if not "3d" in self.EmbyServer.Utils.StringMod(DataSource['Path']):
                        DataSource = self.objects.MapMissingData(DataSource, 'MediaSources')
                        obj['Path'] = DataSource['Path']
                        obj['MediaSourceID'] = DataSource['Id']
                        obj['Runtime'] = DataSource['RunTimeTicks']
                        break

        obj['Path'] = self.APIHelper.get_file_path(obj['Path'], item)
        obj['Genres'] = obj['Genres'] or []
        obj['Studios'] = [self.APIHelper.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['People'] = obj['People'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = self.APIHelper.get_overview(obj['Plot'], item)
        obj['Mpaa'] = self.APIHelper.get_mpaa(obj['Mpaa'], item)
        obj['Resume'] = self.APIHelper.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = self.APIHelper.get_people_artwork(obj['People'])
        obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['Premiered'] = self.EmbyServer.Utils.convert_to_local(obj['Year']) if not obj['Premiered'] else self.EmbyServer.Utils.convert_to_local(obj['Premiered']).replace(" ", "T").split('T')[0]
        obj['DatePlayed'] = None if not obj['DatePlayed'] else self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = self.APIHelper.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = self.APIHelper.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = self.APIHelper.audio_streams(obj['Audio'] or [])
        obj['Streams'] = self.APIHelper.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        PathValid, obj = self.Common.get_path_filename(obj, "movies")

        if not PathValid:
            return "Invalid Filepath"

        self.trailer(obj)

        if obj['Countries']:
            self.MoviesDBIO.add_countries(*self.EmbyServer.Utils.values(obj, queries_videos.update_country_obj))

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

        self.KodiDBIO.update_path(*self.EmbyServer.Utils.values(obj, queries_videos.update_path_movie_obj))
        self.KodiDBIO.update_file(*self.EmbyServer.Utils.values(obj, queries_videos.update_file_obj))
        self.KodiDBIO.add_tags(*self.EmbyServer.Utils.values(obj, queries_videos.add_tags_movie_obj))
        self.KodiDBIO.add_genres(*self.EmbyServer.Utils.values(obj, queries_videos.add_genres_movie_obj))
        self.KodiDBIO.add_studios(*self.EmbyServer.Utils.values(obj, queries_videos.add_studios_movie_obj))
        self.KodiDBIO.add_playstate(*self.EmbyServer.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.KodiDBIO.add_people(*self.EmbyServer.Utils.values(obj, queries_videos.add_people_movie_obj))
        self.KodiDBIO.add_streams(*self.EmbyServer.Utils.values(obj, queries_videos.add_streams_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['MovieId'], "movie")

        if "StackTimes" in obj:
            self.KodiDBIO.add_stacktimes(*self.EmbyServer.Utils.values(obj, queries_videos.add_stacktimes_obj))

        return not update

    #Add object to kodi
    def movie_add(self, obj):
        obj = self.Common.Streamdata_add(obj, False)
        obj['RatingType'] = "default"
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.add_rating_movie_obj))

        if obj['CriticRating'] is not None:
            obj['CriticRating'] = float(obj['CriticRating'] / 10.0)
            self.KodiDBIO.add_ratings(*self.EmbyServer.Utils.values(dict(obj, RatingId=self.KodiDBIO.create_entry_rating(), RatingType="tomatometerallcritics", Rating=obj['CriticRating']), queries_videos.add_rating_movie_obj))

        obj['Unique'] = self.MoviesDBIO.create_entry_unique_id()
        self.MoviesDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_movie_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'imdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.MoviesDBIO.create_entry_unique_id())
                self.MoviesDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_movie_obj))

        obj['PathId'] = self.KodiDBIO.add_path(*self.EmbyServer.Utils.values(obj, queries_videos.add_path_obj))
        obj['FileId'] = self.KodiDBIO.add_file(*self.EmbyServer.Utils.values(obj, queries_videos.add_file_obj))

        if self.EmbyServer.Utils.Settings.userRating:
            self.MoviesDBIO.add(*self.EmbyServer.Utils.values(obj, queries_videos.add_movie_obj))
        else:
            self.MoviesDBIO.add_nouserrating(*self.EmbyServer.Utils.values(obj, queries_videos.add_movie_nouserrating_obj))

        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_movie_obj))
        self.LOG.info("ADD movie [%s/%s/%s] %s: %s" % (obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title']))

    #Update object to kodi
    def movie_update(self, obj):
        obj = self.Common.Streamdata_add(obj, True)
        obj['RatingType'] = "default"
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.EmbyServer.Utils.values(obj, queries_videos.get_rating_movie_obj))
        self.KodiDBIO.update_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.update_rating_movie_obj))

        if obj['CriticRating'] is not None:
            obj['CriticRating'] = float(obj['CriticRating'] / 10.0)
            temp_obj = dict(obj, RatingType="tomatometerallcritics", Rating=obj['CriticRating'])
            temp_obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.get_rating_movie_obj))
            self.KodiDBIO.update_ratings(*self.EmbyServer.Utils.values(temp_obj, queries_videos.update_rating_movie_obj))

        self.KodiDBIO.remove_unique_ids(*self.EmbyServer.Utils.values(obj, queries_videos.delete_unique_ids_movie_obj))
        obj['Unique'] = self.MoviesDBIO.create_entry_unique_id()
        self.MoviesDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_movie_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'imdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.MoviesDBIO.create_entry_unique_id())
                self.MoviesDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_movie_obj))

        if self.EmbyServer.Utils.Settings.userRating:
            self.MoviesDBIO.update(*self.EmbyServer.Utils.values(obj, queries_videos.update_movie_obj))
        else:
            self.MoviesDBIO.update_nouserrating(*self.EmbyServer.Utils.values(obj, queries_videos.update_movie_nouserrating_obj))

        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE movie [%s/%s/%s] %s: %s" % (obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title']))

    def trailer(self, obj):
        try:
            if obj['LocalTrailer']:
                trailer = self.EmbyServer.API.get_local_trailers(obj['Id'])

                if self.EmbyServer.Utils.direct_path:
                    obj['Trailer'] = self.APIHelper.get_file_path(trailer[0]['Path'], trailer)
                    obj['Trailer'] = self.EmbyServer.Utils.StringDecode(obj['Trailer'])
                else:
                    obj['Trailer'] = "plugin://plugin.video.emby-next-gen/trailer?id=%s&mode=play" % trailer[0]['Id']
            elif obj['Trailer']:
                obj['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % obj['Trailer'].rsplit('=', 1)[1]
        except Exception as error:
            self.LOG.error("Failed to get trailer: %s" % error)
            obj['Trailer'] = None

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated.
    #Process movies inside boxset.
    #Process removals from boxset.
    def boxset(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        obj = self.objects.map(item, 'Boxset')
        obj['Overview'] = self.APIHelper.get_overview(obj['Overview'], item)
        obj['Checksum'] = obj['Etag']

        if e_item:
            obj['SetId'] = e_item[0]
            self.MoviesDBIO.update_boxset(*self.EmbyServer.Utils.values(obj, queries_videos.update_set_obj))
        else:
            self.LOG.debug("SetId %s not found" % obj['Id'])
            obj['SetId'] = self.MoviesDBIO.add_boxset(*self.EmbyServer.Utils.values(obj, queries_videos.add_set_obj))

        self.boxset_current(obj)
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'Artwork'))

        for movie in obj['Current']:
            temp_obj = dict(obj)
            temp_obj['Movie'] = movie
            temp_obj['MovieId'] = obj['Current'][temp_obj['Movie']]
            self.MoviesDBIO.remove_from_boxset(*self.EmbyServer.Utils.values(temp_obj, queries_videos.delete_movie_set_obj))
            self.emby_db.update_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_parent_boxset_obj))
            self.LOG.info("DELETE from boxset [%s] %s: %s" % (temp_obj['SetId'], temp_obj['Title'], temp_obj['MovieId']))

        self.ArtworkDBIO.add(obj['Artwork'], obj['SetId'], "set")
        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_boxset_obj))
        self.LOG.info("UPDATE boxset [%s] %s" % (obj['SetId'], obj['Title']))
        return True

    #Add or removes movies based on the current movies found in the boxset
    def boxset_current(self, obj):
        try:
            current = self.emby_db.get_item_id_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_id_by_parent_boxset_obj))
            movies = dict(current)
        except ValueError:
            movies = {}

        obj['Current'] = movies

        for all_movies in self.EmbyServer.API.get_movies_by_boxset(obj['Id']):
            for movie in all_movies['Items']:
                temp_obj = dict(obj)
                temp_obj['Title'] = movie['Name']
                temp_obj['Id'] = movie['Id']
                Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

                if Data:
                    temp_obj['MovieId'] = Data[0]
                else:
                    self.LOG.info("Failed to process %s to boxset." % temp_obj['Title'])
                    continue

                if temp_obj['Id'] not in obj['Current']:
                    self.MoviesDBIO.set_boxset(*self.EmbyServer.Utils.values(temp_obj, queries_videos.update_movie_set_obj))
                    self.emby_db.update_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.update_parent_movie_obj))
                    self.LOG.info("ADD to boxset [%s/%s] %s: %s to boxset" % (temp_obj['SetId'], temp_obj['MovieId'], temp_obj['Title'], temp_obj['Id']))
                else:
                    obj['Current'].pop(temp_obj['Id'])

    #Special function to remove all existing boxsets
    def boxsets_reset(self):
        boxsets = self.emby_db.get_items_by_media('set')
        for boxset in boxsets:
            self.remove(boxset[0])

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        obj = self.objects.map(item, 'MovieUserData')
        obj['Item'] = item

        if e_item:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
        else:
            return

        obj = self.Common.Streamdata_add(obj, True)
        obj['Resume'] = self.APIHelper.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = self.APIHelper.get_playcount(obj['Played'], obj['PlayCount'])

        if obj['DatePlayed']:
            obj['DatePlayed'] = self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Favorite']:
            self.KodiDBIO.get_tag(*self.EmbyServer.Utils.values(obj, queries_videos.get_tag_movie_obj))
        else:
            self.KodiDBIO.remove_tag(*self.EmbyServer.Utils.values(obj, queries_videos.delete_tag_movie_obj))

        self.LOG.debug("New resume point %s: %s" % (obj['Id'], obj['Resume']))
        self.KodiDBIO.add_playstate(*self.EmbyServer.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA movie [%s/%s] %s: %s" % (obj['FileId'], obj['MovieId'], obj['Id'], obj['Title']))

    #Remove movieid, fileid, emby reference.
    #Remove artwork, boxset
    def remove(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['Media'] = e_item[4]
        else:
            return

        self.ArtworkDBIO.delete(obj['KodiId'], obj['Media'])

        if obj['Media'] == 'movie':
            self.MoviesDBIO.delete(*self.EmbyServer.Utils.values(obj, queries_videos.delete_movie_obj))
        elif obj['Media'] == 'set':
            for movie in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_movie_obj)):
                temp_obj = dict(obj)
                temp_obj['MovieId'] = movie[1]
                temp_obj['Movie'] = movie[0]
                self.MoviesDBIO.remove_from_boxset(*self.EmbyServer.Utils.values(temp_obj, queries_videos.delete_movie_set_obj))
                self.emby_db.update_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_parent_boxset_obj))

            self.MoviesDBIO.delete_boxset(*self.EmbyServer.Utils.values(obj, queries_videos.delete_set_obj))

        self.emby_db.remove_item(item_id)
        self.LOG.info("DELETE %s [%s/%s] %s" % (obj['Media'], obj['FileId'], obj['KodiId'], obj['Id']))

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
        self.cursor.execute(queries_videos.get_movie, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def add(self, *args):
        self.cursor.execute(queries_videos.add_movie, args)

    def add_nouserrating(self, *args):
        self.cursor.execute(queries_videos.add_movie_nouserrating, args)

    def update(self, *args):
        self.cursor.execute(queries_videos.update_movie, args)

    def update_nouserrating(self, *args):
        self.cursor.execute(queries_videos.update_movie_nouserrating, args)

    def delete(self, kodi_id, file_id):
        self.cursor.execute(queries_videos.delete_movie, (kodi_id,))
        self.cursor.execute(queries_videos.delete_file, (file_id,))

    # Add the provider id, imdb, tvdb
    def add_unique_id(self, *args):
        self.cursor.execute(queries_videos.add_unique_id, args)

    def add_countries(self, countries, *args):
        for country in countries:
            self.cursor.execute(queries_videos.update_country, (self.get_country(country),) + args)

    def add_country(self, *args):
        country_id = self.create_entry_country()
        self.cursor.execute(queries_videos.add_country, (country_id,) + args)
        return country_id

    def get_country(self, *args):
        self.cursor.execute(queries_videos.get_country, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

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

# -*- coding: utf-8 -*-
import sqlite3
import ntpath

import database.queries
import database.emby_db
import helper.api
import helper.loghandler
from . import obj_ops
from . import common
from . import queries_videos
from . import artwork
from . import kodi

class TVShows():
    def __init__(self, EmbyServer, embydb, videodb, update_library=False):
        self.LOG = helper.loghandler.LOG('EMBY.core.tvshows.TVShows')
        self.update_library = update_library
        self.EmbyServer = EmbyServer
        self.emby = embydb
        self.video = videodb
        self.emby_db = database.emby_db.EmbyDatabase(embydb.cursor)
        self.objects = obj_ops.Objects()
        self.item_ids = []
        self.Common = common.Common(self.emby_db, self.objects, self.EmbyServer)
        self.KodiDBIO = kodi.Kodi(videodb.cursor, self.EmbyServer.Utils)
        self.TVShowsDBIO = TVShowsDBIO(videodb.cursor)
        self.ArtworkDBIO = artwork.Artwork(videodb.cursor, self.EmbyServer.Utils)
        self.APIHelper = helper.api.API(self.EmbyServer.Utils)

    def tvshow(self, item, library, pooling=None, redirect=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Series')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True

        if not obj['RecursiveCount']:
            self.LOG.info("Skipping empty show %s: %s" % (obj['Title'], obj['Id']))
            TVShows(self.EmbyServer, self.emby, self.video, False).remove(obj['Id'])
            return False

        if pooling is None:
            StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

            if str(StackedID) != obj['Id']:
                return TVShows(self.EmbyServer, self.emby, self.video, False).tvshow(obj['Item'], obj['Library'], StackedID, False)

        if e_item:
            obj['ShowId'] = e_item[0]
            obj['PathId'] = e_item[2]

            if self.TVShowsDBIO.get(*self.EmbyServer.Utils.values(obj, queries_videos.get_tvshow_obj)) is None:
                update = False
                self.LOG.info("ShowId %s missing from kodi. repairing the entry." % obj['ShowId'])
        else:
            update = False
            self.LOG.debug("ShowId %s not found" % obj['Id'])
            obj['ShowId'] = self.TVShowsDBIO.create_entry()

        obj['Path'] = self.APIHelper.get_file_path(obj['Item']['Path'], item)
        obj['Genres'] = obj['Genres'] or []
        obj['People'] = obj['People'] or []
        obj['Mpaa'] = self.APIHelper.get_mpaa(obj['Mpaa'], item)
        obj['Studios'] = [self.APIHelper.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['People'] = self.APIHelper.get_people_artwork(obj['People'])
        obj['Plot'] = self.APIHelper.get_overview(obj['Plot'], item)
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Status'] != 'Ended':
            obj['Status'] = None

        if not self.get_path_filename(obj):
            return "Invalid Filepath"

        if obj['Premiere']:
            obj['Premiere'] = str(self.EmbyServer.Utils.convert_to_local(obj['Premiere'])).split('.')[0].replace('T', " ")

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite tvshows')

        obj['Tags'] = tags

        if update:
            self.tvshow_update(obj)
        else:
            self.tvshow_add(obj)

        if pooling:
            obj['SeriesId'] = pooling
            self.LOG.info("POOL %s [%s/%s]" % (obj['Title'], obj['Id'], obj['SeriesId']))
            self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_pool_obj))
            return True

        self.TVShowsDBIO.link(*self.EmbyServer.Utils.values(obj, queries_videos.update_tvshow_link_obj))
        self.KodiDBIO.update_path(*self.EmbyServer.Utils.values(obj, queries_videos.update_path_tvshow_obj))
        self.KodiDBIO.add_tags(*self.EmbyServer.Utils.values(obj, queries_videos.add_tags_tvshow_obj))
        self.KodiDBIO.add_people(*self.EmbyServer.Utils.values(obj, queries_videos.add_people_tvshow_obj))
        self.KodiDBIO.add_genres(*self.EmbyServer.Utils.values(obj, queries_videos.add_genres_tvshow_obj))
        self.KodiDBIO.add_studios(*self.EmbyServer.Utils.values(obj, queries_videos.add_studios_tvshow_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['ShowId'], "tvshow")
        self.item_ids.append(obj['Id'])

        if "StackTimes" in obj:
            self.KodiDBIO.add_stacktimes(*self.EmbyServer.Utils.values(obj, queries_videos.add_stacktimes_obj))

        if redirect:
            self.LOG.info("tvshow added as a redirect")
            return True

        season_episodes = {}

        try:
            all_seasons = self.EmbyServer.API.get_seasons(obj['Id'])['Items']
        except Exception as error:
            self.LOG.error("Unable to pull seasons for %s" % obj['Title'])
            self.LOG.error(error)
            return True

        for season in all_seasons:
            if (self.update_library and season['SeriesId'] != obj['Id']) or (not update and not self.update_library):
                season_episodes[season['Id']] = season.get('SeriesId', obj['Id'])

            try:
                self.emby_db.get_item_by_id(season['Id'])[0]
                self.item_ids.append(season['Id'])
            except TypeError:
                self.season(season, library, obj['ShowId'])

        season_id = self.TVShowsDBIO.get_season(*self.EmbyServer.Utils.values(obj, queries_videos.get_season_special_obj))
        self.ArtworkDBIO.add(obj['Artwork'], season_id, "season")

        for season in season_episodes:
            for episodes in self.EmbyServer.API.get_episode_by_season(season_episodes[season], season):
                for episode in episodes['Items']:
                    Ret = self.episode(episode, library)

                    if Ret == "Invalid Filepath":
                        return Ret

        return not update

    #Add object to kodi
    def tvshow_add(self, obj):
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.add_rating_tvshow_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_tvshow_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_tvshow_obj))

        obj['TopPathId'] = self.KodiDBIO.add_path(obj['TopLevel'])
        self.KodiDBIO.update_path(*self.EmbyServer.Utils.values(obj, queries_videos.update_path_toptvshow_obj))
        obj['PathId'] = self.KodiDBIO.add_path(*self.EmbyServer.Utils.values(obj, queries_videos.get_path_obj))
        self.TVShowsDBIO.add(*self.EmbyServer.Utils.values(obj, queries_videos.add_tvshow_obj))
        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_tvshow_obj))
        self.LOG.info("ADD tvshow [%s/%s/%s] %s: %s" % (obj['TopPathId'], obj['PathId'], obj['ShowId'], obj['Id'], obj['Title']))

    #Update object to kodi
    def tvshow_update(self, obj):
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.EmbyServer.Utils.values(obj, queries_videos.get_rating_tvshow_obj))
        self.KodiDBIO.update_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.update_rating_tvshow_obj))
        self.KodiDBIO.remove_unique_ids(*self.EmbyServer.Utils.values(obj, queries_videos.delete_unique_ids_tvshow_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_tvshow_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_tvshow_obj))

        self.TVShowsDBIO.update(*self.EmbyServer.Utils.values(obj, queries_videos.update_tvshow_obj))
        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE tvshow [%s/%s] %s: %s" % (obj['PathId'], obj['ShowId'], obj['Id'], obj['Title']))

    #Get the path and build it into protocol://path
    def get_path_filename(self, obj):
        if not obj['Path']:
            self.LOG.info("Path is missing")
            return False

        if self.EmbyServer.Utils.direct_path:
            if '\\' in obj['Path']:
                obj['Path'] = "%s\\" % obj['Path']
                obj['TopLevel'] = "%s\\" % ntpath.dirname(ntpath.dirname(obj['Path']))
            else:
                obj['Path'] = "%s/" % obj['Path']
                obj['TopLevel'] = "%s/" % ntpath.dirname(ntpath.dirname(obj['Path']))

            obj['Path'] = self.EmbyServer.Utils.StringDecode(obj['Path'])
            obj['TopLevel'] = self.EmbyServer.Utils.StringDecode(obj['TopLevel'])

            if not self.EmbyServer.Utils.validate(obj['Path']):
                return False
        else:
            obj['TopLevel'] = "http://127.0.0.1:57578/tvshows/"
            obj['Path'] = "%s%s/" % (obj['TopLevel'], obj['Id'])

        return True

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated.
    #If the show is empty, try to remove it.
    def season(self, item, library, show_id=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Season')
        obj['LibraryId'] = library['Id']
        obj['ShowId'] = show_id

        if obj['ShowId'] is None:
            if not self.get_show_id(obj):
                return False

        obj['SeasonId'] = self.TVShowsDBIO.get_season(*self.EmbyServer.Utils.values(obj, queries_videos.get_season_obj))
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Location'] != 'Virtual':
            self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_season_obj))
            self.item_ids.append(obj['Id'])

        self.ArtworkDBIO.add(obj['Artwork'], obj['SeasonId'], "season")
        self.LOG.info("UPDATE season [%s/%s] %s: %s" % (obj['ShowId'], obj['SeasonId'], obj['Title'] or obj['Index'], obj['Id']))
        return True

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated.
    #Create additional entry for widgets.
    #This is only required for plugin/episode.
    def episode(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Episode')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True

        if obj['Location'] == 'Virtual':
            self.LOG.info("Skipping virtual episode %s: %s" % (obj['Title'], obj['Id']))
            return False

        if obj['SeriesId'] is None:
            self.LOG.info("Skipping episode %s with missing SeriesId" % obj['Id'])
            return False

        StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

        if str(StackedID) != obj['Id']:
            self.LOG.info("Skipping stacked episode %s [%s]" % (obj['Title'], obj['Id']))
            TVShows(self.EmbyServer, self.emby, self.video, False).remove(StackedID)

        if e_item:
            obj['EpisodeId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]

            if self.TVShowsDBIO.get_episode(*self.EmbyServer.Utils.values(obj, queries_videos.get_episode_obj)) is None:
                update = False
                self.LOG.info("EpisodeId %s missing from kodi. repairing the entry." % obj['EpisodeId'])
        else:
            update = False
            self.LOG.debug("EpisodeId %s not found" % obj['Id'])
            obj['EpisodeId'] = self.TVShowsDBIO.create_entry_episode()

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
        obj['Index'] = obj['Index'] or -1
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = self.APIHelper.get_overview(obj['Plot'], item)
        obj['Resume'] = self.APIHelper.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = self.APIHelper.get_people_artwork(obj['People'] or [])
        obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = self.APIHelper.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = self.APIHelper.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = self.APIHelper.audio_streams(obj['Audio'] or [])
        obj['Streams'] = self.APIHelper.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        PathValid, obj = self.Common.get_path_filename(obj, "tvshows")

        if not PathValid:
            return "Invalid Filepath"

        if obj['Premiere']:
            obj['Premiere'] = self.EmbyServer.Utils.convert_to_local(obj['Premiere']).split('.')[0].replace('T', " ")

        if obj['Season'] is None:
            if obj['AbsoluteNumber']:
                obj['Season'] = 1
                obj['Index'] = obj['AbsoluteNumber']
            else:
                obj['Season'] = 0

        if obj['AirsAfterSeason']:
            obj['AirsBeforeSeason'] = obj['AirsAfterSeason']
            obj['AirsBeforeEpisode'] = 4096 # Kodi default number for afterseason ordering

        if not self.get_show_id(obj):
            self.LOG.info("No series id associated")
            return False

        obj['SeasonId'] = self.TVShowsDBIO.get_season(*self.EmbyServer.Utils.values(obj, queries_videos.get_season_episode_obj))

        if update:
            self.episode_update(obj)
        else:
            self.episode_add(obj)

        self.KodiDBIO.update_path(*self.EmbyServer.Utils.values(obj, queries_videos.update_path_episode_obj))
        self.KodiDBIO.update_file(*self.EmbyServer.Utils.values(obj, queries_videos.update_file_obj))
        self.KodiDBIO.add_people(*self.EmbyServer.Utils.values(obj, queries_videos.add_people_episode_obj))
        self.KodiDBIO.add_streams(*self.EmbyServer.Utils.values(obj, queries_videos.add_streams_obj))
        self.KodiDBIO.add_playstate(*self.EmbyServer.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.ArtworkDBIO.update(obj['Artwork']['Primary'], obj['EpisodeId'], "episode", "thumb")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    def episode_add(self, obj):
        obj = self.Common.Streamdata_add(obj, False)
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.add_rating_episode_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_episode_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_episode_obj))

        obj['PathId'] = self.KodiDBIO.add_path(*self.EmbyServer.Utils.values(obj, queries_videos.add_path_obj))
        obj['FileId'] = self.KodiDBIO.add_file(*self.EmbyServer.Utils.values(obj, queries_videos.add_file_obj))

        try:
            self.TVShowsDBIO.add_episode(*self.EmbyServer.Utils.values(obj, queries_videos.add_episode_obj))
        except sqlite3.IntegrityError:
            self.LOG.error("IntegrityError for %s" % obj)
            obj['EpisodeId'] = self.TVShowsDBIO.create_entry_episode()
            return self.episode_add(obj)

        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_episode_obj))
        self.LOG.info("ADD episode [%s/%s/%s/%s] %s: %s" % (obj['ShowId'], obj['SeasonId'], obj['EpisodeId'], obj['FileId'], obj['Id'], obj['Title']))

    #Update object to kodi
    def episode_update(self, obj):
        obj = self.Common.Streamdata_add(obj, True)
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.EmbyServer.Utils.values(obj, queries_videos.get_rating_episode_obj))
        self.KodiDBIO.update_ratings(*self.EmbyServer.Utils.values(obj, queries_videos.update_rating_episode_obj))
        self.KodiDBIO.remove_unique_ids(*self.EmbyServer.Utils.values(obj, queries_videos.delete_unique_ids_episode_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(obj, queries_videos.add_unique_id_episode_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.EmbyServer.Utils.values(temp_obj, queries_videos.add_unique_id_episode_obj))

        self.TVShowsDBIO.update_episode(*self.EmbyServer.Utils.values(obj, queries_videos.update_episode_obj))
        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.emby_db.update_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.update_parent_episode_obj))
        self.LOG.info("UPDATE episode [%s/%s/%s/%s] %s: %s" % (obj['ShowId'], obj['SeasonId'], obj['EpisodeId'], obj['FileId'], obj['Id'], obj['Title']))

    def get_show_id(self, obj):
        if obj.get('ShowId'):
            return True

        obj['ShowId'] = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_series_obj))
        if obj['ShowId'] is None:
            TVShows(self.EmbyServer, self.emby, self.video, False).tvshow(self.EmbyServer.API.get_item(obj['SeriesId']), None, None, True)
            Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_series_obj))

            if Data:
                obj['ShowId'] = Data[0]
            else:
                self.LOG.error("Unable to add series %s" % obj['SeriesId'])
                return False
        else:
            obj['ShowId'] = obj['ShowId'][0]

        self.item_ids.append(obj['SeriesId'])
        return True

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        obj = self.objects.map(item, 'EpisodeUserData')
        obj['Item'] = item

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['Media'] = e_item[4]
        else:
            return

        if obj['Media'] == "tvshow":
            if obj['Favorite']:
                self.KodiDBIO.get_tag(*self.EmbyServer.Utils.values(obj, queries_videos.get_tag_episode_obj))
            else:
                self.KodiDBIO.remove_tag(*self.EmbyServer.Utils.values(obj, queries_videos.delete_tag_episode_obj))
        elif obj['Media'] == "episode":
            obj = self.Common.Streamdata_add(obj, True)
            obj['Resume'] = self.APIHelper.adjust_resume((obj['Resume'] or 0) / 10000000.0)
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['PlayCount'] = self.APIHelper.get_playcount(obj['Played'], obj['PlayCount'])

            if obj['DatePlayed']:
                obj['DatePlayed'] = self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            if obj['DateAdded']:
                obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

            self.KodiDBIO.add_playstate(*self.EmbyServer.Utils.values(obj, queries_videos.add_bookmark_obj))

        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA %s [%s/%s] %s: %s" % (obj['Media'], obj['FileId'], obj['KodiId'], obj['Id'], obj['Title']))
        return

    #Remove showid, fileid, pathid, emby reference.
    #There's no episodes left, delete show and any possible remaining seasons
    def remove(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        else:
            return

        if obj['Media'] == 'episode':
            temp_obj = dict(obj)
            self.remove_episode(obj['KodiId'], obj['FileId'], obj['Id'])
            season = self.emby_db.get_full_item_by_kodi_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_season_obj))

            if season:
                temp_obj['Id'] = season[0]
                temp_obj['ParentId'] = season[1]
            else:
                return

            if not self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_episode_obj)):
                self.remove_season(obj['ParentId'], obj['Id'])
                self.emby_db.remove_item(temp_obj['Id'])

            temp_obj['Id'] = self.emby_db.get_item_by_kodi_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_tvshow_obj))

            if not self.TVShowsDBIO.get_total_episodes(*self.EmbyServer.Utils.values(temp_obj, queries_videos.get_total_episodes_obj)):
                for season in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_season_obj)):
                    self.remove_season(season[1], obj['Id'])

                self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_item_by_parent_season_obj))
                self.remove_tvshow(temp_obj['ParentId'], obj['Id'])
                self.emby_db.remove_item(temp_obj['Id'])

        elif obj['Media'] == 'tvshow':
            obj['ParentId'] = obj['KodiId']

            for season in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_season_obj)):
                temp_obj = dict(obj)
                temp_obj['ParentId'] = season[1]

                for episode in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_episode_obj)):
                    self.remove_episode(episode[1], episode[2], episode[0])

                self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_item_by_parent_episode_obj))

            self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_season_obj))
            self.remove_tvshow(obj['KodiId'], obj['Id'])
        elif obj['Media'] == 'season':
            obj['ParentId'] = obj['KodiId']

            for episode in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_episode_obj)):
                self.remove_episode(episode[1], episode[2], episode[0])

            self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_episode_obj))
            self.remove_season(obj['KodiId'], obj['Id'])

            if not self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_season_obj)):
                self.remove_tvshow(obj['ParentId'], obj['Id'])
                self.emby_db.remove_item_by_kodi_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_tvshow_obj))

        # Remove any series pooling episodes
        for episode in self.emby_db.get_media_by_parent_id(obj['Id']):
            self.remove_episode(episode[2], episode[3], episode[0])

        self.emby_db.remove_media_by_parent_id(obj['Id'])
        self.emby_db.remove_item(obj['Id'])

    def remove_tvshow(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "tvshow")
        self.TVShowsDBIO.delete_tvshow(kodi_id)
        self.emby_db.remove_item_by_kodi_id(kodi_id, "tvshow")
        self.LOG.info("DELETE tvshow [%s] %s" % (kodi_id, item_id))

    def remove_season(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "season")
        self.TVShowsDBIO.delete_season(kodi_id)
        self.emby_db.remove_item_by_kodi_id(kodi_id, "season")
        self.LOG.info("DELETE season [%s] %s" % (kodi_id, item_id))

    def remove_episode(self, kodi_id, file_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "episode")
        self.TVShowsDBIO.delete_episode(kodi_id, file_id)
        self.emby_db.remove_item(item_id)
        self.LOG.info("DELETE episode [%s/%s] %s" % (file_id, kodi_id, item_id))

    #Get all child elements from tv show emby id
    def get_child(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}
        child = []

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        else:
            return child

        obj['ParentId'] = obj['KodiId']

        for season in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_season_obj)):
            temp_obj = dict(obj)
            temp_obj['ParentId'] = season[1]
            child.append(season[0])

            for episode in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_episode_obj)):
                child.append(episode[0])

        for episode in self.emby_db.get_media_by_parent_id(obj['Id']):
            child.append(episode[0])

        return child

class TVShowsDBIO():
    def __init__(self, cursor):
        self.cursor = cursor

    def create_entry_unique_id(self):
        self.cursor.execute(queries_videos.create_unique_id)
        return self.cursor.fetchone()[0] + 1

    def create_entry(self):
        self.cursor.execute(queries_videos.create_tvshow)
        return self.cursor.fetchone()[0] + 1

    def create_entry_season(self):
        self.cursor.execute(queries_videos.create_season)
        return self.cursor.fetchone()[0] + 1

    def create_entry_episode(self):
        self.cursor.execute(queries_videos.create_episode)
        return self.cursor.fetchone()[0] + 1

    def get(self, *args):
        self.cursor.execute(queries_videos.get_tvshow, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_episode(self, *args):
        self.cursor.execute(queries_videos.get_episode, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_total_episodes(self, *args):
        self.cursor.execute(queries_videos.get_total_episodes, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def add_unique_id(self, *args):
        self.cursor.execute(queries_videos.add_unique_id, args)

    def add(self, *args):
        self.cursor.execute(queries_videos.add_tvshow, args)

    def update(self, *args):
        self.cursor.execute(queries_videos.update_tvshow, args)

    def link(self, *args):
        self.cursor.execute(queries_videos.update_tvshow_link, args)

    def get_season(self, name, *args):
        self.cursor.execute(queries_videos.get_season, args)
        Data = self.cursor.fetchone()

        if Data:
            season_id = Data[0]
        else:
            season_id = self.add_season(*args)

        if name:
            self.cursor.execute(queries_videos.update_season, (name, season_id))

        return season_id

    def add_season(self, *args):
        season_id = self.create_entry_season()
        self.cursor.execute(queries_videos.add_season, (season_id,) + args)
        return season_id

    def add_episode(self, *args):
        self.cursor.execute(queries_videos.add_episode, args)

    def update_episode(self, *args):
        self.cursor.execute(queries_videos.update_episode, args)

    def delete_tvshow(self, *args):
        self.cursor.execute(queries_videos.delete_tvshow, args)

    def delete_season(self, *args):
        self.cursor.execute(queries_videos.delete_season, args)

    def delete_episode(self, kodi_id, file_id):
        self.cursor.execute(queries_videos.delete_episode, (kodi_id,))
        self.cursor.execute(queries_videos.delete_file, (file_id,))

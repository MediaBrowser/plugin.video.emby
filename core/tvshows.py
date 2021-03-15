# -*- coding: utf-8 -*-
import logging
import sqlite3
import ntpath

import emby.downloader
import database.queries
import database.emby_db
import helper.wrapper
import helper.api
from . import obj_ops
from . import common
from . import queries_videos
from . import artwork
from . import kodi

class TVShows():
    def __init__(self, server, embydb, videodb, direct_path, Utils, update_library=False):
        self.LOG = logging.getLogger("EMBY.core.tvshows.TVShows")
        self.Utils = Utils
        self.update_library = update_library
        self.server = server
        self.emby = embydb
        self.video = videodb
        self.direct_path = direct_path
        self.emby_db = database.emby_db.EmbyDatabase(embydb.cursor)
        self.objects = obj_ops.Objects(self.Utils)
        self.item_ids = []
        self.display_multiep = self.Utils.settings('displayMultiEpLabel.bool')
        self.Downloader = emby.downloader.Downloader(self.Utils)
        self.Common = common.Common(self.emby_db, self.objects, self.Utils, self.direct_path, self.server)
        self.KodiDBIO = kodi.Kodi(videodb.cursor)
        self.TVShowsDBIO = TVShowsDBIO(videodb.cursor)
        self.ArtworkDBIO = artwork.Artwork(videodb.cursor, self.Utils)

    def __getitem__(self, key):
        if key == 'Series':
            return self.tvshow
        elif key == 'Season':
            return self.season
        elif key == 'Episode':
            return self.episode

    @helper.wrapper.stop
    def tvshow(self, item, library=None, pooling=None, redirect=False):
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.
            If the show is empty, try to remove it.
            Process seasons.
            Apply series pooling.
        '''
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Series')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True

        if not self.Utils.settings('syncEmptyShows.bool') and not obj['RecursiveCount']:
            self.LOG.info("Skipping empty show %s: %s", obj['Title'], obj['Id'])
            TVShows(self.server, self.emby, self.video, self.direct_path, self.Utils, False).remove(obj['Id'])
            return False

        if pooling is None:
            StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

            if str(StackedID) != obj['Id']:
                return TVShows(self.server, self.emby, self.video, self.direct_path, self.Utils, False).tvshow(obj['Item'], library=obj['Library'], pooling=StackedID)

        try:
            obj['ShowId'] = e_item[0]
            obj['PathId'] = e_item[2]
        except TypeError as error:
            update = False
            self.LOG.debug("ShowId %s not found", obj['Id'])
            obj['ShowId'] = self.TVShowsDBIO.create_entry()
        else:
            if self.TVShowsDBIO.get(*self.Utils.values(obj, queries_videos.get_tvshow_obj)) is None:
                update = False
                self.LOG.info("ShowId %s missing from kodi. repairing the entry.", obj['ShowId'])

        obj['Path'] = API.get_file_path(obj['Item']['Path'])
        obj['Genres'] = obj['Genres'] or []
        obj['People'] = obj['People'] or []
        obj['Mpaa'] = API.get_mpaa(obj['Mpaa'])
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['People'] = API.get_people_artwork(obj['People'])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Status'] != 'Ended':
            obj['Status'] = None

        if not self.get_path_filename(obj):
            return False

        if obj['Premiere']:
            obj['Premiere'] = str(self.Utils.convert_to_local(obj['Premiere'])).split('.')[0].replace('T', " ")

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
            self.LOG.info("POOL %s [%s/%s]", obj['Title'], obj['Id'], obj['SeriesId'])
            self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_pool_obj))
            return True

        self.TVShowsDBIO.link(*self.Utils.values(obj, queries_videos.update_tvshow_link_obj))
        self.KodiDBIO.update_path(*self.Utils.values(obj, queries_videos.update_path_tvshow_obj))
        self.KodiDBIO.add_tags(*self.Utils.values(obj, queries_videos.add_tags_tvshow_obj))
        self.KodiDBIO.add_people(*self.Utils.values(obj, queries_videos.add_people_tvshow_obj))
        self.KodiDBIO.add_genres(*self.Utils.values(obj, queries_videos.add_genres_tvshow_obj))
        self.KodiDBIO.add_studios(*self.Utils.values(obj, queries_videos.add_studios_tvshow_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['ShowId'], "tvshow")
        self.item_ids.append(obj['Id'])

        if "StackTimes" in obj:
            self.KodiDBIO.add_stacktimes(*self.Utils.values(obj, queries_videos.add_stacktimes_obj))

        if redirect:
            self.LOG.info("tvshow added as a redirect")
            return True

        season_episodes = {}

        try:
            all_seasons = self.server['api'].get_seasons(obj['Id'])['Items']
        except Exception as error:
            self.LOG.error("Unable to pull seasons for %s", obj['Title'])
            self.LOG.error(error)
            return True

        for season in all_seasons:
            if (self.update_library and season['SeriesId'] != obj['Id']) or (not update and not self.update_library):
                season_episodes[season['Id']] = season.get('SeriesId', obj['Id'])

            try:
                self.emby_db.get_item_by_id(season['Id'])[0]
                self.item_ids.append(season['Id'])
            except TypeError:
                self.season(season, obj['ShowId'], obj['LibraryId'])

        season_id = self.TVShowsDBIO.get_season(*self.Utils.values(obj, queries_videos.get_season_special_obj))
        self.ArtworkDBIO.add(obj['Artwork'], season_id, "season")

        for season in season_episodes:
            for episodes in self.Downloader.get_episode_by_season(season_episodes[season], season):
                for episode in episodes['Items']:
                    self.episode(episode)

        return not update

    #Add object to kodi
    def tvshow_add(self, obj):
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.Utils.values(obj, queries_videos.add_rating_tvshow_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_tvshow_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_tvshow_obj))

        obj['TopPathId'] = self.KodiDBIO.add_path(obj['TopLevel'])
        self.KodiDBIO.update_path(*self.Utils.values(obj, queries_videos.update_path_toptvshow_obj))
        obj['PathId'] = self.KodiDBIO.add_path(*self.Utils.values(obj, queries_videos.get_path_obj))
        self.TVShowsDBIO.add(*self.Utils.values(obj, queries_videos.add_tvshow_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_tvshow_obj))
        self.LOG.info("ADD tvshow [%s/%s/%s] %s: %s", obj['TopPathId'], obj['PathId'], obj['ShowId'], obj['Id'], obj['Title'])

    #Update object to kodi
    def tvshow_update(self, obj):
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.Utils.values(obj, queries_videos.get_rating_tvshow_obj))
        self.KodiDBIO.update_ratings(*self.Utils.values(obj, queries_videos.update_rating_tvshow_obj))
        self.KodiDBIO.remove_unique_ids(*self.Utils.values(obj, queries_videos.delete_unique_ids_tvshow_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_tvshow_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_tvshow_obj))

        self.TVShowsDBIO.update(*self.Utils.values(obj, queries_videos.update_tvshow_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE tvshow [%s/%s] %s: %s", obj['PathId'], obj['ShowId'], obj['Id'], obj['Title'])

    #Get the path and build it into protocol://path
    def get_path_filename(self, obj):
        if not obj['Path']:
            self.LOG.info("Path is missing")
            return False

        if self.direct_path:
            if '\\' in obj['Path']:
                obj['Path'] = "%s\\" % obj['Path']
                obj['TopLevel'] = "%s\\" % ntpath.dirname(ntpath.dirname(obj['Path']))
            else:
                obj['Path'] = "%s/" % obj['Path']
                obj['TopLevel'] = "%s/" % ntpath.dirname(ntpath.dirname(obj['Path']))

            obj['Path'] = self.Utils.StringDecode(obj['Path'])
            obj['TopLevel'] = self.Utils.StringDecode(obj['TopLevel'])

            if not self.Utils.validate(obj['Path']):
                raise Exception("Failed to validate path. User stopped.")
        else:
            obj['TopLevel'] = "http://127.0.0.1:57578/tvshows/"
            obj['Path'] = "%s%s/" % (obj['TopLevel'], obj['Id'])

        return True

    @helper.wrapper.stop
    def season(self, item, show_id=None, library_id=None):
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.
            If the show is empty, try to remove it.
        '''
        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Season')
        obj['LibraryId'] = library_id
        obj['ShowId'] = show_id

        if obj['ShowId'] is None:
            if not self.get_show_id(obj):
                return False

        obj['SeasonId'] = self.TVShowsDBIO.get_season(*self.Utils.values(obj, queries_videos.get_season_obj))
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Location'] != 'Virtual':
            self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_season_obj))
            self.item_ids.append(obj['Id'])

        self.ArtworkDBIO.add(obj['Artwork'], obj['SeasonId'], "season")
        self.LOG.info("UPDATE season [%s/%s] %s: %s", obj['ShowId'], obj['SeasonId'], obj['Title'] or obj['Index'], obj['Id'])
        return True

    @helper.wrapper.stop
    def episode(self, item, library=None):
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.
            Create additional entry for widgets.
            This is only required for plugin/episode.
        '''
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Episode')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True

        if obj['Location'] == 'Virtual':
            self.LOG.info("Skipping virtual episode %s: %s", obj['Title'], obj['Id'])
            return False

        if obj['SeriesId'] is None:
            self.LOG.info("Skipping episode %s with missing SeriesId", obj['Id'])
            return False

        StackedID = self.emby_db.get_stack(obj['PresentationKey']) or obj['Id']

        if str(StackedID) != obj['Id']:
            self.LOG.info("Skipping stacked episode %s [%s]", obj['Title'], obj['Id'])
            TVShows(self.server, self.emby, self.video, self.direct_path, self.Utils, False).remove(StackedID)

        try:
            obj['EpisodeId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError:
            update = False
            self.LOG.debug("EpisodeId %s not found", obj['Id'])
            obj['EpisodeId'] = self.TVShowsDBIO.create_entry_episode()
        else:
            if self.TVShowsDBIO.get_episode(*self.Utils.values(obj, queries_videos.get_episode_obj)) is None:
                update = False
                self.LOG.info("EpisodeId %s missing from kodi. repairing the entry.", obj['EpisodeId'])

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
        obj['Index'] = obj['Index'] or -1
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = API.get_people_artwork(obj['People'] or [])
        obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj = self.Common.get_path_filename(obj, "tvshows")

        if obj['Premiere']:
            obj['Premiere'] = self.Utils.convert_to_local(obj['Premiere']).split('.')[0].replace('T', " ")

        if obj['Season'] is None:
            if obj['AbsoluteNumber']:
                obj['Season'] = 1
                obj['Index'] = obj['AbsoluteNumber']
            else:
                obj['Season'] = 0

        if obj['AirsAfterSeason']:
            obj['AirsBeforeSeason'] = obj['AirsAfterSeason']
            obj['AirsBeforeEpisode'] = 4096 # Kodi default number for afterseason ordering

        if obj['MultiEpisode'] and self.display_multiep:
            obj['Title'] = "| %02d | %s" % (obj['MultiEpisode'], obj['Title'])

        if not self.get_show_id(obj):
            self.LOG.info("No series id associated")
            return False

        obj['SeasonId'] = self.TVShowsDBIO.get_season(*self.Utils.values(obj, queries_videos.get_season_episode_obj))

        if update:
            self.episode_update(obj)
        else:
            self.episode_add(obj)

        self.KodiDBIO.update_path(*self.Utils.values(obj, queries_videos.update_path_episode_obj))
        self.KodiDBIO.update_file(*self.Utils.values(obj, queries_videos.update_file_obj))
        self.KodiDBIO.add_people(*self.Utils.values(obj, queries_videos.add_people_episode_obj))
        self.KodiDBIO.add_streams(*self.Utils.values(obj, queries_videos.add_streams_obj))
        self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.ArtworkDBIO.update(obj['Artwork']['Primary'], obj['EpisodeId'], "episode", "thumb")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    def episode_add(self, obj):
        obj = self.Common.Streamdata_add(obj, False)
        obj['RatingId'] = self.KodiDBIO.create_entry_rating()
        self.KodiDBIO.add_ratings(*self.Utils.values(obj, queries_videos.add_rating_episode_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_episode_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_episode_obj))

        obj['PathId'] = self.KodiDBIO.add_path(*self.Utils.values(obj, queries_videos.add_path_obj))
        obj['FileId'] = self.KodiDBIO.add_file(*self.Utils.values(obj, queries_videos.add_file_obj))

        try:
            self.TVShowsDBIO.add_episode(*self.Utils.values(obj, queries_videos.add_episode_obj))
        except sqlite3.IntegrityError:
            self.LOG.error("IntegrityError for %s", obj)
            obj['EpisodeId'] = self.TVShowsDBIO.create_entry_episode()
            return self.episode_add(obj)

        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_episode_obj))
        self.LOG.info("ADD episode [%s/%s/%s/%s] %s: %s", obj['ShowId'], obj['SeasonId'], obj['EpisodeId'], obj['FileId'], obj['Id'], obj['Title'])

    #Update object to kodi
    def episode_update(self, obj):
        obj = self.Common.Streamdata_add(obj, True)
        obj['RatingId'] = self.KodiDBIO.get_rating_id(*self.Utils.values(obj, queries_videos.get_rating_episode_obj))
        self.KodiDBIO.update_ratings(*self.Utils.values(obj, queries_videos.update_rating_episode_obj))
        self.KodiDBIO.remove_unique_ids(*self.Utils.values(obj, queries_videos.delete_unique_ids_episode_obj))
        obj['Unique'] = self.TVShowsDBIO.create_entry_unique_id()
        self.TVShowsDBIO.add_unique_id(*self.Utils.values(obj, queries_videos.add_unique_id_episode_obj))

        for provider in obj['UniqueIds'] or {}:
            unique_id = obj['UniqueIds'][provider]
            provider = provider.lower()

            if provider != 'tvdb':
                temp_obj = dict(obj, ProviderName=provider, UniqueId=unique_id, Unique=self.TVShowsDBIO.create_entry_unique_id())
                self.TVShowsDBIO.add_unique_id(*self.Utils.values(temp_obj, queries_videos.add_unique_id_episode_obj))

        self.TVShowsDBIO.update_episode(*self.Utils.values(obj, queries_videos.update_episode_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.emby_db.update_parent_id(*self.Utils.values(obj, database.queries.update_parent_episode_obj))
        self.LOG.info("UPDATE episode [%s/%s/%s/%s] %s: %s", obj['ShowId'], obj['SeasonId'], obj['EpisodeId'], obj['FileId'], obj['Id'], obj['Title'])

    def get_show_id(self, obj):
        if obj.get('ShowId'):
            return True

        obj['ShowId'] = self.emby_db.get_item_by_id(*self.Utils.values(obj, database.queries.get_item_series_obj))
        if obj['ShowId'] is None:

            try:
                TVShows(self.server, self.emby, self.video, self.direct_path, self.Utils, False).tvshow(self.server['api'].get_item(obj['SeriesId']), library=None, redirect=True)
                obj['ShowId'] = self.emby_db.get_item_by_id(*self.Utils.values(obj, database.queries.get_item_series_obj))[0]
            except (TypeError, KeyError):
                self.LOG.error("Unable to add series %s", obj['SeriesId'])
                return False
        else:
            obj['ShowId'] = obj['ShowId'][0]

        self.item_ids.append(obj['SeriesId'])
        return True

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    @helper.wrapper.stop
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
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
                self.KodiDBIO.get_tag(*self.Utils.values(obj, queries_videos.get_tag_episode_obj))
            else:
                self.KodiDBIO.remove_tag(*self.Utils.values(obj, queries_videos.delete_tag_episode_obj))
        elif obj['Media'] == "episode":
            obj = self.Common.Streamdata_add(obj, True)
            obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

            if obj['DatePlayed']:
                obj['DatePlayed'] = self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            if obj['DateAdded']:
                obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

            self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))

        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA %s [%s/%s] %s: %s", obj['Media'], obj['FileId'], obj['KodiId'], obj['Id'], obj['Title'])
        return

    @helper.wrapper.stop
    def remove(self, item_id):
        ''' Remove showid, fileid, pathid, emby reference.
            There's no episodes left, delete show and any possible remaining seasons
        '''
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        if obj['Media'] == 'episode':
            temp_obj = dict(obj)
            self.remove_episode(obj['KodiId'], obj['FileId'], obj['Id'])
            season = self.emby_db.get_full_item_by_kodi_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_season_obj))

            try:
                temp_obj['Id'] = season[0]
                temp_obj['ParentId'] = season[1]
            except TypeError:
                return

            if not self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_episode_obj)):
                self.remove_season(obj['ParentId'], obj['Id'])
                self.emby_db.remove_item(*self.Utils.values(temp_obj, database.queries.delete_item_obj))

            temp_obj['Id'] = self.emby_db.get_item_by_kodi_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_tvshow_obj))

            if not self.TVShowsDBIO.get_total_episodes(*self.Utils.values(temp_obj, queries_videos.get_total_episodes_obj)):
                for season in self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_season_obj)):
                    self.remove_season(season[1], obj['Id'])

                self.emby_db.remove_items_by_parent_id(*self.Utils.values(temp_obj, database.queries.delete_item_by_parent_season_obj))
                self.remove_tvshow(temp_obj['ParentId'], obj['Id'])
                self.emby_db.remove_item(*self.Utils.values(temp_obj, database.queries.delete_item_obj))
        elif obj['Media'] == 'tvshow':
            obj['ParentId'] = obj['KodiId']

            for season in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_season_obj)):
                temp_obj = dict(obj)
                temp_obj['ParentId'] = season[1]

                for episode in self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_episode_obj)):
                    self.remove_episode(episode[1], episode[2], obj['Id'])

                self.emby_db.remove_items_by_parent_id(*self.Utils.values(temp_obj, database.queries.delete_item_by_parent_episode_obj))

            self.emby_db.remove_items_by_parent_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_season_obj))
            self.remove_tvshow(obj['KodiId'], obj['Id'])
        elif obj['Media'] == 'season':
            obj['ParentId'] = obj['KodiId']

            for episode in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_episode_obj)):
                self.remove_episode(episode[1], episode[2], obj['Id'])

            self.emby_db.remove_items_by_parent_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_episode_obj))
            self.remove_season(obj['KodiId'], obj['Id'])

            if not self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_season_obj)):
                self.remove_tvshow(obj['ParentId'], obj['Id'])
                self.emby_db.remove_item_by_kodi_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_tvshow_obj))

        # Remove any series pooling episodes
        for episode in self.emby_db.get_media_by_parent_id(obj['Id']):
            self.remove_episode(episode[2], episode[3], obj['Id'])

        self.emby_db.remove_media_by_parent_id(obj['Id'])
        self.emby_db.remove_item(*self.Utils.values(obj, database.queries.delete_item_obj))

    def remove_tvshow(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "tvshow")
        self.TVShowsDBIO.delete_tvshow(kodi_id)
        self.emby_db.remove_item_by_kodi_id(kodi_id, "tvshow")
        self.LOG.info("DELETE tvshow [%s] %s", kodi_id, item_id)

    def remove_season(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "season")
        self.TVShowsDBIO.delete_season(kodi_id)
        self.emby_db.remove_item_by_kodi_id(kodi_id, "season")
        self.LOG.info("DELETE season [%s] %s", kodi_id, item_id)

    def remove_episode(self, kodi_id, file_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "episode")
        self.TVShowsDBIO.delete_episode(kodi_id, file_id)
        self.emby_db.remove_item(item_id)
        self.LOG.info("DELETE episode [%s/%s] %s", file_id, kodi_id, item_id)

    #Get all child elements from tv show emby id
    def get_child(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}
        child = []

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        except TypeError:
            return child

        obj['ParentId'] = obj['KodiId']

        for season in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_season_obj)):
            temp_obj = dict(obj)
            temp_obj['ParentId'] = season[1]
            child.append(season[0])

            for episode in self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_episode_obj)):
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
        try:
            self.cursor.execute(queries_videos.get_tvshow, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_episode(self, *args):
        try:
            self.cursor.execute(queries_videos.get_episode, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_total_episodes(self, *args):
        try:
            self.cursor.execute(queries_videos.get_total_episodes, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

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

        try:
            season_id = self.cursor.fetchone()[0]
        except TypeError:
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

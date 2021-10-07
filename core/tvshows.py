# -*- coding: utf-8 -*-
import helper.loghandler
import helper.utils as Utils
import emby.obj_ops as Objects
from . import common as Common

LOG = helper.loghandler.LOG('EMBY.core.tvshows.TVShows')


class TVShows:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.KodiSeasonId = None

    def tvshow(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'Series')
        obj['Item'] = item
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']

        if not obj['RecursiveCount']:
            LOG.info("Skipping empty show %s: %s" % (obj['Title'], obj['Id']))
            self.remove(obj['Id'], False)
            return False

        if e_item:
            update = True
            obj['KodiShowId'] = e_item[0]
            obj['KodiPathId'] = e_item[2]
        else:
            update = False
            LOG.debug("KodiShowId %s not found" % obj['Id'])
            StackedKodiId = self.emby_db.get_stacked_kodiid(obj['PresentationKey'], obj['LibraryId'], "Series")

            if StackedKodiId:
                obj['KodiShowId'] = StackedKodiId
            else:
                obj['KodiShowId'] = self.video_db.create_entry_tvshow()

        obj['FullPath'] = Common.get_file_path(obj['Path'], item)
        obj['Path'] = Common.get_path(obj, "tvshows")
        obj['Genres'] = obj['Genres'] or []
        obj['People'] = obj['People'] or []
        obj['Mpaa'] = Common.get_mpaa(obj['Mpaa'], item)
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['People'] = Common.get_people_artwork(obj['People'], self.EmbyServer.server_id)
        obj['Plot'] = Common.get_overview(obj['Plot'], item)
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, self.EmbyServer.server_id)

        if obj['Status'] != 'Ended':
            obj['Status'] = None

        if obj['Premiere']:
            obj['Premiere'] = str(Utils.convert_to_local(obj['Premiere'])).split('.')[0].replace('T', " ")

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite tvshows')

        obj['Tags'] = tags

        if update:
            obj['RatingId'] = self.video_db.get_rating_id("tvshow", obj['KodiShowId'], "default")
            self.video_db.update_ratings(obj['KodiShowId'], "tvshow", "default", obj['Rating'], obj['RatingId'])
            self.video_db.remove_unique_ids(obj['KodiShowId'], "tvshow")
            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiShowId'], "tvshow", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'tvdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiShowId'], "tvshow", unique_id, provider)

            self.video_db.update_tvshow(obj['Title'], obj['Plot'], obj['Status'], obj['RatingId'], obj['Premiere'], obj['Genre'], obj['OriginalTitle'], "disintegrate browse bug", obj['Unique'], obj['Mpaa'], obj['Studio'], obj['SortTitle'], obj['KodiShowId'])
            self.emby_db.update_reference(obj['PresentationKey'], obj['Favorite'], obj['Id'])
            LOG.info("UPDATE tvshow [%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiShowId'], obj['Id'], obj['Title']))
        else:
            obj['RatingId'] = self.video_db.create_entry_rating()
            self.video_db.add_ratings(obj['RatingId'], obj['KodiShowId'], "tvshow", "default", obj['Rating'])
            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiShowId'], "tvshow", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'tvdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiShowId'], "tvshow", unique_id, provider)

            obj['KodiPathParentId'] = self.video_db.get_add_path(obj['PathParent'], "tvshows", None)
            obj['KodiPathId'] = self.video_db.get_add_path(obj['Path'], None, obj['KodiPathParentId'])
            self.video_db.add_tvshow(obj['KodiShowId'], obj['Title'], obj['Plot'], obj['Status'], obj['RatingId'], obj['Premiere'], obj['Genre'], obj['OriginalTitle'], "disintegrate browse bug", obj['Unique'], obj['Mpaa'], obj['Studio'], obj['SortTitle'])
            self.emby_db.add_reference(obj['Id'], obj['KodiShowId'], None, obj['KodiPathId'], "Series", "tvshow", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD tvshow [%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiShowId'], obj['Id'], obj['Title']))

        self.video_db.link(obj['KodiShowId'], obj['KodiPathId'])
        self.video_db.add_tags(obj['Tags'], obj['KodiShowId'], "tvshow")
        self.video_db.add_people(obj['People'], obj['KodiShowId'], "tvshow")
        self.video_db.add_genres(obj['Genres'], obj['KodiShowId'], "tvshow")
        self.video_db.add_studios(obj['Studios'], obj['KodiShowId'], "tvshow")
        self.video_db.common_db.add_artwork(obj['Artwork'], obj['KodiShowId'], "tvshow")

        if "StackTimes" in obj:
            self.video_db.add_stacktimes(obj['KodiFileId'], obj['StackTimes'])

        return not update

    def season(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'Season')
        obj['LibraryId'] = library['Id']
        obj['Index'] = obj['Index'] or 0

        if e_item:
            update = True
            obj['KodiSeasonId'] = e_item[0]
            obj['KodiShowId'] = e_item[3]
        else:
            update = False
            LOG.debug("KodiSeasonId %s not found" % obj['Id'])
            StackedKodiId = self.emby_db.get_stacked_kodiid(obj['PresentationKey'], obj['LibraryId'], "Season")

            if StackedKodiId:
                obj['KodiSeasonId'] = StackedKodiId
            else:
                obj['KodiSeasonId'] = None

        if update:
            self.video_db.update_season(obj['KodiShowId'], obj['Index'], obj['Title'], obj['KodiSeasonId'])
            LOG.info("UPDATE season [%s/%s] %s: %s" % (obj['KodiShowId'], obj['KodiSeasonId'], obj['Title'] or obj['Index'], obj['Id']))
        else:
            if not self.get_show_id(obj):
                LOG.info("No series id associated")
                return False

            if not obj['KodiSeasonId']:
                obj['KodiSeasonId'] = self.video_db.create_entry_season()

            LOG.debug("SeasonId %s not found" % obj['Id'])
            self.video_db.add_season(obj['KodiSeasonId'], obj['KodiShowId'], obj['Index'], obj['Title'])
            LOG.info("ADD season [%s/%s] %s: %s" % (obj['KodiShowId'], obj['KodiSeasonId'], obj['Title'] or obj['Index'], obj['Id']))

        self.KodiSeasonId = obj['KodiSeasonId']
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'ArtworkParent'), True, self.EmbyServer.server_id)
        self.emby_db.add_reference(obj['Id'], obj['KodiSeasonId'], None, None, "Season", "season", obj['KodiShowId'], obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
        self.video_db.common_db.add_artwork(obj['Artwork'], obj['KodiSeasonId'], "season")
        return not update

    def episode(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'Episode')
        obj['Emby_Type'] = 'Episode'
        obj['Item'] = item
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['ServerId'] = self.EmbyServer.server_id

        if obj['SeriesId'] is None:
            LOG.info("Skipping episode %s with missing SeriesId" % obj['Id'])
            return False

        if e_item:
            update = True
            obj['KodiEpisodeId'] = e_item[0]
            obj['KodiFileId'] = e_item[1]
            obj['KodiPathId'] = e_item[2]
        else:
            update = False
            LOG.debug("EpisodeId %s not found" % obj['Id'])

        obj['FullPath'] = Common.SwopMediaSources(obj, item)  # 3D

        if not obj['FullPath']:  # Invalid Path
            LOG.error("Invalid path: %s" % obj['Id'])
            LOG.debug("Invalid path: %s" % obj)
            return False

        obj['Path'] = Common.get_path(obj, "episodes")
        obj['Index'] = obj['Index'] or 0
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = Common.get_overview(obj['Plot'], item)
        obj['Resume'] = Common.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = Common.get_people_artwork(obj['People'] or [], self.EmbyServer.server_id)
        obj['DateAdded'] = Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, self.EmbyServer.server_id)
        obj['Video'] = Common.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = Common.audio_streams(obj['Audio'] or [])
        obj['Streams'] = Common.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])

        if obj['Premiere']:
            obj['Premiere'] = Utils.convert_to_local(obj['Premiere']).split('.')[0].replace('T', " ")

        if obj['Season'] is None:
            if obj['AbsoluteNumber']:
                obj['Season'] = 1
                obj['Index'] = obj['AbsoluteNumber']
            else:
                obj['Season'] = 0

        if obj['AirsAfterSeason']:
            obj['AirsBeforeSeason'] = obj['AirsAfterSeason']
            obj['AirsBeforeEpisode'] = 4096  # Kodi default number for afterseason ordering

        if not self.get_show_id(obj):
            LOG.info("No series id associated")
            return False

        obj['KodiSeasonId'] = self.video_db.get_season(obj['KodiShowId'], obj['Season'])

        # check if episode info has a different season number than the actual referenced season
        if not obj['KodiSeasonId']:
            obj['KodiSeasonId'] = self.video_db.get_season_by_name(obj['KodiShowId'], obj['SeasonName'])

            if obj['KodiSeasonId']:
                LOG.warning("Episode season number not matching season's number: [%s] %s %s %s" % (obj['Id'], obj['SeriesName'], obj['SeasonName'], obj['Title']))

        # Season missing, adding...
        if not obj['KodiSeasonId']:
            if 'SeasonId' in obj['Item']:
                SeasonItem = self.EmbyServer.API.get_item(obj['Item']['SeasonId'])
                self.season(SeasonItem, library)
                obj['KodiSeasonId'] = self.KodiSeasonId
            else:
                LOG.error("No SeasonId: %s" % obj['Id'])
                LOG.debug("No SeasonId: %s" % obj)
                return False

        Common.Streamdata_add(obj, self.emby_db, update)

        if update:
            obj['RatingId'] = self.video_db.get_rating_id("episode", obj['KodiEpisodeId'], "default")
            self.video_db.update_ratings(obj['KodiEpisodeId'], "episode", "default", obj['Rating'], obj['RatingId'])
            self.video_db.remove_unique_ids(obj['KodiEpisodeId'], "episode")
            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiEpisodeId'], "episode", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'tvdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiEpisodeId'], "episode", unique_id, provider)

            obj['Filename'] = Common.get_filename(obj, "tvshows", self.EmbyServer.API)
            self.video_db.update_episode(obj['Title'], obj['Plot'], obj['RatingId'], obj['Writers'], obj['Premiere'], obj['Runtime'], obj['Directors'], obj['Season'], obj['Index'], obj['OriginalTitle'], obj['AirsBeforeSeason'], obj['AirsBeforeEpisode'], obj['KodiSeasonId'], obj['KodiShowId'], obj['KodiEpisodeId'])
            self.video_db.update_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])
            self.emby_db.update_reference(obj['PresentationKey'], obj['Favorite'], obj['Id'])
            self.emby_db.update_parent_id(obj['KodiSeasonId'], obj['Id'])
            LOG.info("UPDATE episode [%s/%s/%s/%s] %s: %s" % (obj['KodiShowId'], obj['KodiSeasonId'], obj['KodiEpisodeId'], obj['KodiFileId'], obj['Id'], obj['Title']))
        else:
            obj['KodiEpisodeId'] = self.video_db.create_entry_episode()
            obj['RatingId'] = self.video_db.create_entry_rating()
            self.video_db.add_ratings(obj['RatingId'], obj['KodiEpisodeId'], "episode", "default", obj['Rating'])
            obj['Unique'] = self.video_db.create_entry_unique_id()
            self.video_db.add_unique_id(obj['Unique'], obj['KodiEpisodeId'], "episode", obj['UniqueId'], obj['ProviderName'])

            for provider in obj['UniqueIds'] or {}:
                unique_id = obj['UniqueIds'][provider]
                provider = provider.lower()

                if provider != 'tvdb':
                    Unique = self.video_db.create_entry_unique_id()
                    self.video_db.add_unique_id(Unique, obj['KodiEpisodeId'], "episode", unique_id, provider)

            obj['KodiPathId'] = self.video_db.get_add_path(obj['Path'], None)
            obj['KodiFileId'] = self.video_db.create_entry_file()
            obj['Filename'] = Common.get_filename(obj, "tvshows", self.EmbyServer.API)
            self.video_db.add_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])
            self.video_db.add_episode(obj['KodiEpisodeId'], obj['KodiFileId'], obj['Title'], obj['Plot'], obj['RatingId'], obj['Writers'], obj['Premiere'], obj['Runtime'], obj['Directors'], obj['Season'], obj['Index'], obj['OriginalTitle'], obj['KodiShowId'], obj['AirsBeforeSeason'], obj['AirsBeforeEpisode'], obj['KodiSeasonId'])
            self.emby_db.add_reference(obj['Id'], obj['KodiEpisodeId'], obj['KodiFileId'], obj['KodiPathId'], "Episode", "episode", obj['KodiSeasonId'], obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD episode [%s/%s/%s/%s] %s: %s" % (obj['KodiShowId'], obj['KodiSeasonId'], obj['KodiEpisodeId'], obj['KodiFileId'], obj['Id'], obj['Title']))

        self.video_db.add_people(obj['People'], obj['KodiEpisodeId'], "episode")
        self.video_db.add_streams(obj['KodiFileId'], obj['Streams'], obj['Runtime'])
        self.video_db.add_playstate(obj['KodiFileId'], obj['PlayCount'], obj['DatePlayed'], obj['Resume'], obj['Runtime'])
        self.video_db.common_db.add_artwork(obj['Artwork'], obj['KodiEpisodeId'], "episode")
        ExistingItem = Common.add_Multiversion(obj, self.emby_db, "Episode", self.EmbyServer.API)

        # Remove existing Item
        if ExistingItem and not update:
            self.video_db.common_db.delete_artwork(ExistingItem[0], "episode")
            self.video_db.delete_episode(ExistingItem[0], ExistingItem[1])

        return not update

    def get_show_id(self, obj):
        if obj.get('KodiShowId'):
            return True

        obj['KodiShowId'] = self.emby_db.get_item_by_id(obj['SeriesId'])

        if obj['KodiShowId'] is None:
            self.tvshow(self.EmbyServer.API.get_item(obj['SeriesId']), None)
            Data = self.emby_db.get_item_by_id(obj['SeriesId'])

            if Data:
                obj['KodiShowId'] = Data[0]
            else:
                LOG.error("Unable to add series %s" % obj['SeriesId'])
                return False
        else:
            obj['KodiShowId'] = obj['KodiShowId'][0]

        return True

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, e_item, ItemUserdata):
        KodiId = e_item[0]
        KodiFileId = e_item[1]
        KodiType = e_item[4]
        Info = KodiType

        if KodiType == "tvshow":
            if ItemUserdata['IsFavorite']:
                self.video_db.get_tag("Favorite tvshows", KodiId, "tvshow")
            else:
                self.video_db.remove_tag("Favorite tvshows", KodiId, "tvshow")
        elif KodiType == "episode":
            Resume = Common.adjust_resume((ItemUserdata['PlaybackPositionTicks'] or 0) / 10000000.0)
            EpisodeData = self.video_db.get_episode_data(KodiId)
            Runtime = round(float(EpisodeData[11]) / 10000000.0, 6)
            PlayCount = Common.get_playcount(ItemUserdata['Played'], ItemUserdata['PlayCount'])
            DatePlayed = Utils.currenttime()
            Info = EpisodeData[2]
            self.video_db.add_playstate(KodiFileId, PlayCount, DatePlayed, Resume, Runtime)

        self.emby_db.update_reference_userdatachanged(ItemUserdata['IsFavorite'], ItemUserdata['ItemId'])
        LOG.info("USERDATA [%s/%s/%s] %s: %s" % (KodiType, KodiFileId, KodiId, ItemUserdata['ItemId'], Info))

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, EmbyItemId, Delete):
        e_item = self.emby_db.get_item_by_id(EmbyItemId)

        if e_item:
            KodiId = e_item[0]
            KodiFileId = e_item[1]
            KodiParentId = e_item[3]
            KodiType = e_item[4]
            emby_presentation_key = e_item[8]
            emby_folder = e_item[6]
        else:
            return

        if KodiType == 'episode':
            if not Delete:
                StackedIds = self.emby_db.get_stacked_embyid(emby_presentation_key, emby_folder, "Episode")

                if len(StackedIds) > 1:
                    self.emby_db.remove_item(EmbyItemId)
                    LOG.info("DELETE stacked episode from embydb %s" % EmbyItemId)

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_item_multiversion(StackedId[0])

                        if StackedItem:
                            library_name = self.emby_db.get_Libraryname_by_Id(emby_folder)
                            LibraryData = {"Id": emby_folder, "Name": library_name}
                            LOG.info("UPDATE remaining stacked episode from embydb %s" % StackedItem['Id'])
                            self.episode(StackedItem, LibraryData)  # update all stacked items
                else:
                    KodiSeasonData = self.emby_db.get_full_item_by_kodi_id(KodiParentId, "season")
                    self.remove_episode(KodiId, KodiFileId, EmbyItemId)

                    # delete empty season
                    if KodiSeasonData:
                        if not self.emby_db.get_item_by_parent_id(KodiParentId, "episode"):
                            KodiTVShowData = self.emby_db.get_full_item_by_kodi_id(KodiSeasonData[1], "tvshow")
                            self.remove_season(KodiParentId, KodiSeasonData[0])

                            # delete empty tvshow
                            if KodiTVShowData:
                                if not self.emby_db.get_item_by_parent_id(KodiSeasonData[1], "season"):
                                    self.remove_tvshow(KodiSeasonData[1], KodiTVShowData[0])
            else:
                self.remove_episode(KodiId, KodiFileId, EmbyItemId)
        elif KodiType == 'tvshow':
            if not Delete:
                if self.emby_db.check_stacked(emby_presentation_key, emby_folder, "Series"):
                    self.emby_db.remove_item(EmbyItemId)
                    LOG.info("DELETE stacked t [%s] %s" % (KodiId, EmbyItemId))
                    StackedItems = self.emby_db.get_items_by_embyparentid(EmbyItemId, emby_folder, "Episode")

                    for StackedItem in StackedItems:
                        self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0])
                        LOG.info("DELETE stacked episode [%s/%s] %s" % (StackedItem[4], StackedItem[5], StackedItem[0]))
                else:
                    # delete seasons
                    for season in self.emby_db.get_item_by_parent_id(KodiId, "season"):
                        # delete episodes
                        for episode in self.emby_db.get_item_by_parent_id(season[1], "episode"):
                            self.remove_episode(episode[1], episode[2], episode[0])

                        self.remove_season(season[1], season[0])

                    self.remove_tvshow(KodiId, EmbyItemId)
            else:
                self.remove_tvshow(KodiId, EmbyItemId)
        elif KodiType == 'season':
            if not Delete:
                if self.emby_db.check_stacked(emby_presentation_key, emby_folder, "Season"):
                    self.emby_db.remove_item(EmbyItemId)
                    LOG.info("DELETE stacked season [%s] %s" % (KodiId, EmbyItemId))
                else:
                    KodiSeasonData = self.emby_db.get_full_item_by_kodi_id(KodiId, "season")

                    # delete episodes
                    for episode in self.emby_db.get_item_by_parent_id(KodiId, "episode"):
                        self.remove_episode(episode[1], episode[2], episode[0])

                    self.remove_season(KodiId, EmbyItemId)

                    # delete empty tvshow
                    if not self.emby_db.get_item_by_parent_id(KodiSeasonData[1], "season"):
                        self.remove_tvshow(KodiSeasonData[1], KodiSeasonData[0])
            else:
                self.remove_season(KodiId, EmbyItemId)

    def remove_tvshow(self, KodiTVShowId, EmbyItemId):
        self.video_db.common_db.delete_artwork(KodiTVShowId, "tvshow")
        self.video_db.delete_tvshow(KodiTVShowId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE tvshow [%s] %s" % (KodiTVShowId, EmbyItemId))

    def remove_season(self, KodiSeasonId, EmbyItemId):
        self.video_db.common_db.delete_artwork(KodiSeasonId, "season")
        self.video_db.delete_season(KodiSeasonId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE season [%s] %s" % (KodiSeasonId, EmbyItemId))

    def remove_episode(self, KodiEpisodeId, KodiFileId, EmbyItemId):
        self.video_db.common_db.delete_artwork(KodiEpisodeId, "episode")
        self.video_db.delete_episode(KodiEpisodeId, KodiFileId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE episode [%s/%s] %s" % (KodiEpisodeId, KodiFileId, EmbyItemId))

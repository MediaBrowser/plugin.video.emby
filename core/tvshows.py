from helper import loghandler, pluginmenu
from . import common

LOG = loghandler.LOG('EMBY.core.tvshows')


class TVShows:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.KodiSeasonId = None
        self.KodiShowId = None

    def tvshow(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if not common.get_file_path(item, "tvshows"):
            return False

        self.KodiShowId = None
        Stacked = False
        get_PresentationUniqueKey(item)

        if item['ExistingItem']:
            update = True
            item['KodiItemId'] = item['ExistingItem'][0]
            item['KodiPathId'] = item['ExistingItem'][2]
            self.video_db.delete_links_actors(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_director(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_writer(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_countries(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_genres(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_studios(item['KodiItemId'], "tvshow")
            self.video_db.delete_links_tags(item['KodiItemId'], "tvshow")
            self.video_db.delete_uniqueids(item['KodiItemId'], "tvshow")
            self.video_db.delete_ratings(item['KodiItemId'], "tvshow")
            self.video_db.common.delete_artwork(item['KodiItemId'], "tvshow")
        else:
            update = False
            LOG.debug("KodiItemId %s not found" % item['Id'])
            StackedKodiId = self.emby_db.get_stacked_kodiid(item['PresentationUniqueKey'], item['Library']['Id'], "Series")

            if StackedKodiId:
                item['KodiItemId'] = StackedKodiId
                Stacked = True
            else:
                item['KodiItemId'] = self.video_db.create_entry_tvshow()

            item['KodiPathParentId'] = self.video_db.get_add_path(item['PathParent'], "tvshows", None)
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None, item['KodiPathParentId'])

        if Stacked:
            self.emby_db.add_reference(item['Id'], item['KodiItemId'], None, item['KodiPathId'], "Series", "tvshow", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD stacked tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemId'], item['Id'], item['Name']))
        else:
            item['Status'] = item.get('Status', None)
            item['CommunityRating'] = item.get('CommunityRating', None)
            item['CriticRating'] = item.get('CriticRating', None)
            item['OriginalTitle'] = item.get('OriginalTitle', None)
            item['ProductionLocations'] = item.get('ProductionLocations', [])
            common.set_RunTimeTicks(item)
            common.set_mpaa(item)
            common.set_videocommon(item, self.EmbyServer.server_id)
            self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemId'], "tvshow")
            self.video_db.add_link_tag(common.MediaTags[item['Library']['Name']], item['KodiItemId'], "tvshow")
            self.video_db.add_genres_and_links(item['Genres'], item['KodiItemId'], "tvshow")
            self.video_db.add_studios_and_links(item['Studios'], item['KodiItemId'], "tvshow")
            self.video_db.add_people_and_links(item['People'], item['KodiItemId'], "tvshow")
            self.video_db.add_countries_and_links(item['ProductionLocations'], item['KodiItemId'], "tvshow")
            self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemId'], "tvshow")
            item['Unique'] = self.video_db.add_uniqueids(item['KodiItemId'], item['ProviderIds'], "tvshow", 'tvdb')
            item['RatingId'] = self.video_db.add_ratings(item['KodiItemId'], "tvshow", "default", item['CommunityRating'])

            if update:
                self.video_db.update_tvshow(item['Name'], item['Overview'], item['Status'], item['RatingId'], item['PremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart'), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['RunTimeTicks'], item['KodiItemId'])
                self.emby_db.update_reference(item['KodiItemId'], None, item['KodiPathId'], "Series", "tvshow", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
                LOG.info("UPDATE tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemId'], item['Id'], item['Name']))
            else:
                self.video_db.add_tvshow(item['KodiItemId'], item['Name'], item['Overview'], item['Status'], item['RatingId'], item['PremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart'), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['RunTimeTicks'])
                self.emby_db.add_reference(item['Id'], item['KodiItemId'], None, item['KodiPathId'], "Series", "tvshow", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
                LOG.info("ADD tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemId'], item['Id'], item['Name']))

        self.video_db.add_tags_and_links(item['KodiItemId'], "tvshow", item['TagItems'])
        self.KodiShowId = item['KodiItemId']
        return not update

    def season(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if 'SeriesId' not in item:
            LOG.error("No Series assigned to Episode: %s %s" % (item['Id'], item['Name']))
            LOG.debug("No Series assigned to Episode: %s" % item)
            return False

        self.KodiSeasonId = None
        Stacked = False
        get_PresentationUniqueKey(item)
        item['IndexNumber'] = item.get('IndexNumber', 0)

        if item['ExistingItem']:
            update = True
            item['KodiSeasonId'] = item['ExistingItem'][0]
            item['KodiShowId'] = item['ExistingItem'][3]
            self.video_db.delete_links_tags(item['KodiSeasonId'], "season")
            self.video_db.common.delete_artwork(item['KodiSeasonId'], "season")
        else:
            update = False
            LOG.debug("KodiSeasonId %s not found" % item['Id'])

            if not self.get_kodi_show_id(item):
                LOG.info("No series id associated")
                return False

            StackedKodiId = self.emby_db.get_stacked_kodiid(item['PresentationUniqueKey'], item['Library']['Id'], "Season")

            if StackedKodiId:
                item['KodiSeasonId'] = StackedKodiId
                Stacked = True
            else:
                item['KodiSeasonId'] = self.video_db.create_entry_season()

        if Stacked:
            self.emby_db.add_reference(item['Id'], item['KodiSeasonId'], None, None, "Season", "season", item['KodiShowId'], item['Library']['Id'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD stacked season [%s/%s] %s: %s" % (item['KodiShowId'], item['KodiSeasonId'], item['Name'] or item['IndexNumber'], item['Id']))
        else:
            common.set_KodiArtwork(item, self.EmbyServer.server_id)
            self.video_db.add_link_tag(common.MediaTags[item['Library']['Name']], item['KodiSeasonId'], "season")
            self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiSeasonId'], "season")

            if update:
                self.video_db.update_season(item['KodiShowId'], item['IndexNumber'], item['Name'], item['KodiSeasonId'])
                self.emby_db.update_reference(item['KodiSeasonId'], None, None, "Season", "season", item['KodiShowId'], item['Library']['Id'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
                LOG.info("UPDATE season [%s/%s] %s: %s" % (item['KodiShowId'], item['KodiSeasonId'], item['Name'] or item['IndexNumber'], item['Id']))
            else:
                self.video_db.add_season(item['KodiSeasonId'], item['KodiShowId'], item['IndexNumber'], item['Name'])
                self.emby_db.add_reference(item['Id'], item['KodiSeasonId'], None, None, "Season", "season", item['KodiShowId'], item['Library']['Id'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
                LOG.info("ADD season [%s/%s] %s: %s" % (item['KodiShowId'], item['KodiSeasonId'], item['Name'] or item['IndexNumber'], item['Id']))

        self.KodiSeasonId = item['KodiSeasonId']
        return not update

    def episode(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if 'SeriesId' not in item:
            LOG.error("No Series assigned to Episode: %s %s" % (item['Id'], item['Name']))
            LOG.debug("No Series assigned to Episode: %s" % item)
            return False

        if 'SeasonId' not in item:
            LOG.error("No season assigned to Episode: %s %s" % (item['Id'], item['Name']))
            LOG.debug("No season assigned to Episode: %s" % item)
            return False

        if not common.get_file_path(item, "episodes"):
            return False

        common.SwopMediaSources(item)  # 3D
        get_PresentationUniqueKey(item)

        if item['ExistingItem']:
            update = True
            item['KodiItemId'] = item['ExistingItem'][0]
            item['KodiFileId'] = item['ExistingItem'][1]
            item['KodiPathId'] = item['ExistingItem'][2]
            self.video_db.delete_ratings(item['KodiItemId'], "episode")
            common.delete_ContentItemReferences(item['Id'], item['KodiItemId'], item['KodiFileId'], self.video_db, self.emby_db, "episode")
        else:
            update = False
            LOG.debug("EpisodeId %s not found" % item['Id'])
            item['KodiItemId'] = self.video_db.create_entry_episode()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None)
            item['KodiFileId'] = self.video_db.create_entry_file()

        if not self.get_kodi_show_id(item):
            LOG.info("No series id associated")
            return False

        if not self.get_kodi_season_id(item):
            LOG.info("No season id associated")
            return False

        item['OriginalTitle'] = item.get('OriginalTitle', None)  # not supported by Emby
        item['SortIndexNumber'] = item.get('SortIndexNumber', None)
        item['SortParentIndexNumber'] = item.get('SortParentIndexNumber', None)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 0)

        # Remove special episode numbers when Season != 0
        if item['ParentIndexNumber']:
            item['SortIndexNumber'] = None
            item['SortParentIndexNumber'] = None

        common.set_mpaa(item)
        common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "episode", "e")
        self.video_db.add_link_tag(common.MediaTags[item['Library']['Name']], item['KodiItemId'], "episode")
        item['Unique'] = self.video_db.add_uniqueids(item['KodiItemId'], item['ProviderIds'], "episode", 'tvdb')
        item['RatingId'] = self.video_db.add_ratings(item['KodiItemId'], "episode", "default", item['CommunityRating'])

        if update:
            self.video_db.update_episode(item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['PremiereDate'], item['KodiArtwork']['thumb'], item['RunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['Unique'], item['KodiShowId'], item['KodiSeasonId'], item['KodiItemId'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['KodiFileId'])
            self.emby_db.update_reference(item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Episode", "episode", item['KodiSeasonId'], item['Library']['Id'], item['SeasonId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
            LOG.info("UPDATE episode [%s/%s/%s/%s] %s: %s" % (item['KodiShowId'], item['KodiSeasonId'], item['KodiItemId'], item['KodiFileId'], item['Id'], item['Name']))
        else:
            self.video_db.add_episode(item['KodiItemId'], item['KodiFileId'], item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['PremiereDate'], item['KodiArtwork']['thumb'], item['RunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['Unique'], item['KodiShowId'], item['KodiSeasonId'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'])
            self.emby_db.add_reference(item['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Episode", "episode", item['KodiSeasonId'], item['Library']['Id'], item['SeasonId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD episode [%s/%s/%s/%s] %s: %s" % (item['KodiShowId'], item['KodiSeasonId'], item['KodiItemId'], item['KodiFileId'], item['Id'], item['Name']))

        self.emby_db.add_multiversion(item, "Episode", self.EmbyServer.API, self.video_db, update)
        return not update

    def get_kodi_show_id(self, item):
        KodiShowItem = self.emby_db.get_item_by_id(item['SeriesId'])

        if not KodiShowItem:
            LOG.info("Load SeriesId")
            item['KodiShowId'] = None
            TVShowItem = self.EmbyServer.API.get_Item(item['SeriesId'], ['Series'], False, False)

            if TVShowItem:
                LOG.info("Add TVShow by SeriesId %s" % item['SeriesId'])
                TVShowItem['Library'] = item['Library']
                self.tvshow(TVShowItem)
                item['KodiShowId'] = self.KodiShowId

            if not item['KodiShowId']:
                LOG.error("Unable to add series %s" % item['SeriesId'])
                return False
        else:
            item['KodiShowId'] = KodiShowItem[0]

        return True

    def get_kodi_season_id(self, item):
        KodiSeasonItem = self.emby_db.get_item_by_id(item['SeasonId'])

        if not KodiSeasonItem:
            item['KodiSeasonId'] = None
            SeasonItem = self.EmbyServer.API.get_Item(item['SeasonId'], ['Season'], False, False)

            if SeasonItem:
                SeasonItem['Library'] = item['Library']
                self.season(SeasonItem)
                item['KodiSeasonId'] = self.KodiSeasonId

            if not item['KodiSeasonId']:
                LOG.error("Unable to add season %s" % item['SeasonId'])
                return False
        else:
            item['KodiSeasonId'] = KodiSeasonItem[0]

        return True

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemId'], Item['KodiType'])

        if Item['KodiType'] == "episode":
            if Item['PlaybackPositionTicks']:
                RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
            else:
                RuntimeSeconds = 0

            common.set_userdata_update_data(Item)
            self.video_db.update_bookmark_playstate(Item['KodiFileId'], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)

        self.emby_db.update_reference_userdatachanged(Item['IsFavorite'], Item['Id'])
        pluginmenu.reset_episodes_cache()
        LOG.info("USERDATA [%s/%s/%s] %s" % (Item['KodiType'], Item['KodiFileId'], Item['KodiItemId'], Item['Id']))

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if Item['Type'] == 'Episode':
            self.remove_episode(Item['KodiItemId'], Item['KodiFileId'], Item['Id'])

            if not Item['DeleteByLibraryId']:
                StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "Episode")

                # multiversion
                if StackedIds:
                    LOG.info("DELETE multi version episodes from embydb %s" % Item['Id'])

                    for StackedId in StackedIds:
                        self.emby_db.remove_item(StackedId[0])

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['Episode'], False, False)

                        if StackedItem:
                            StackedItem['Library'] = Item['Library']
                            LOG.info("UPDATE remaining multi version episode %s" % StackedItem['Id'])
                            self.episode(StackedItem)  # update all stacked items
                else: # single version
                    KodiSeasonData = self.emby_db.get_full_item_by_kodi_id(Item['KodiParentId'], "season")

                    # delete empty season
                    if KodiSeasonData:
                        if not self.emby_db.get_item_by_parent_id(Item['KodiParentId'], "episode"):  # check if nor more episodes assigned to season
                            KodiTVShowData = self.emby_db.get_full_item_by_kodi_id(KodiSeasonData[1], "tvshow")
                            self.remove_season(Item['KodiParentId'], KodiSeasonData[0])

                            # delete empty tvshow
                            if KodiTVShowData:
                                if not self.emby_db.get_item_by_parent_id(KodiSeasonData[1], "season"):
                                    self.remove_tvshow(KodiSeasonData[1], KodiTVShowData[0])
        elif Item['Type'] == 'Series':
            self.remove_tvshow(Item['KodiItemId'], Item['Id'])

            if not Item['DeleteByLibraryId']:
                LOG.info("DELETE stacked tvshow [%s] %s" % (Item['KodiItemId'], Item['Id']))
                StackedSeasonItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Season")

                for StackedSeasonItem in StackedSeasonItems:
                    self.remove_season(StackedSeasonItem[4], StackedSeasonItem[0])
                    LOG.info("DELETE stacked season [%s] %s" % (StackedSeasonItem[4], StackedSeasonItem[0]))
                    StackedItems = self.emby_db.get_items_by_embyparentid(StackedSeasonItem[0], Item['Library']['Id'], "Episode")

                    for StackedItem in StackedItems:
                        self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0])
                        LOG.info("DELETE stacked episode [%s/%s] %s" % (StackedItem[4], StackedItem[5], StackedItem[0]))
        elif Item['Type'] == 'Season':
            self.remove_season(Item['KodiItemId'], Item['Id'])

            if not Item['DeleteByLibraryId']:
                LOG.info("DELETE stacked season [%s] %s" % (Item['KodiItemId'], Item['Id']))
                StackedItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Episode")

                for StackedItem in StackedItems:
                    self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0])
                    LOG.info("DELETE stacked episode [%s/%s] %s" % (StackedItem[4], StackedItem[5], StackedItem[0]))

    def remove_tvshow(self, KodiTVShowId, EmbyItemId):
        self.video_db.common.delete_artwork(KodiTVShowId, "tvshow")
        self.video_db.delete_tvshow(KodiTVShowId)
        self.video_db.delete_links_tags(KodiTVShowId, "tvshow")
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE tvshow [%s] %s" % (KodiTVShowId, EmbyItemId))

    def remove_season(self, KodiSeasonId, EmbyItemId):
        self.video_db.common.delete_artwork(KodiSeasonId, "season")
        self.video_db.delete_season(KodiSeasonId)
        self.video_db.delete_links_tags(KodiSeasonId, "season")
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE season [%s] %s" % (KodiSeasonId, EmbyItemId))

    def remove_episode(self, KodiItemId, KodiFileId, EmbyItemId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "episode")
        self.video_db.delete_episode(KodiItemId, KodiFileId)
        LOG.info("DELETE episode [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

def get_PresentationUniqueKey(item):
    if "PresentationUniqueKey" in item:
        item['PresentationUniqueKey'] = item['PresentationUniqueKey'].replace("-", "_").replace(" ", "")
    else:
        item['PresentationUniqueKey'] = None

from helper import loghandler, pluginmenu
from . import common

LOG = loghandler.LOG('EMBY.core.tvshows')


class TVShows:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.video_db.init_favorite_tags()

    def tvshow(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        LOG.info("Process item: %s" % item['Name'])
        ItemIndex = 0
        get_PresentationUniqueKey(item)
        item['Status'] = item.get('Status', "")
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['CriticRating'] = item.get('CriticRating', None)
        item['OriginalTitle'] = item.get('OriginalTitle', "")
        common.set_RunTimeTicks(item)
        common.set_mpaa(item)
        common.set_trailer(item, self.EmbyServer)

        for ItemIndex in range(len(item['Librarys'])):
            common.set_videocommon(item, self.EmbyServer.ServerData['ServerId'], ItemIndex)
            Stacked = False

            if not common.get_file_path(item, "tvshows", ItemIndex):
                continue

            if not item['UpdateItems'][ItemIndex]:
                LOG.debug("KodiItemId %s not found" % item['Id'])
                StackedKodiId = self.emby_db.get_stacked_kodiid(item['PresentationUniqueKey'], item['Librarys'][ItemIndex]['Id'], "Series")

                if StackedKodiId:
                    item['KodiItemIds'][ItemIndex] = StackedKodiId
                    Stacked = True
                else:
                    item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_tvshow()
            else:
                self.video_db.delete_links_actors(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_director(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_writer(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_countries(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_genres(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_studios(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_links_tags(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_uniqueids(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.delete_ratings(item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "tvshow")

            item['KodiPathParentId'] = self.video_db.get_add_path(item['PathParent'], "tvshows", None)
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None, item['KodiPathParentId'])

            if Stacked:
                item['KodiItemIds'][ItemIndex] = item['KodiItemIds'][ItemIndex]
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], item['KodiPathId'], "Series", "tvshow", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                LOG.info("ADD stacked tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))
            else:
                self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.add_genres_and_links(item['Genres'], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.add_studios_and_links(item['Studios'], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.add_people_and_links(item['People'], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.add_countries_and_links(item['ProductionLocations'], item['KodiItemIds'][ItemIndex], "tvshow")
                self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "tvshow")
                item['Unique'] = self.video_db.add_uniqueids(item['KodiItemIds'][ItemIndex], item['ProviderIds'], "tvshow", 'tvdb')
                item['RatingId'] = self.video_db.add_ratings(item['KodiItemIds'][ItemIndex], "tvshow", "default", item['CommunityRating'])

                if item['UpdateItems'][ItemIndex]:
                    self.video_db.update_tvshow(item['Name'], item['Overview'], item['Status'], item['RatingId'], item['PremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart', ""), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['RunTimeTicks'], item['KodiItemIds'][ItemIndex], item['Trailer'])
                    self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                    LOG.info("UPDATE tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))
                else:
                    self.video_db.add_tvshow(item['KodiItemIds'][ItemIndex], item['Name'], item['Overview'], item['Status'], item['RatingId'], item['PremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart', ""), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['RunTimeTicks'], item['Trailer'])
                    item['KodiItemIds'][ItemIndex] = item['KodiItemIds'][ItemIndex]
                    self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], item['KodiPathId'], "Series", "tvshow", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                    self.video_db.add_link_tvshow(item['KodiItemIds'][ItemIndex], item['KodiPathParentId'])
                    LOG.info("ADD tvshow [%s/%s] %s: %s" % (item['KodiPathId'], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))

            self.video_db.add_tags_and_links(item['KodiItemIds'][ItemIndex], "tvshow", item['TagItems'])

        return not item['UpdateItems'][ItemIndex]

    def season(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if 'SeriesId' not in item:
            LOG.error("No Series assigned to Episode: %s %s" % (item['Id'], item['Name']))
            LOG.debug("No Series assigned to Episode: %s" % item)
            return False

        LOG.info("Process item: %s" % item['Name'])
        ItemIndex = 0
        item['IndexNumber'] = item.get('IndexNumber', 0)
        get_PresentationUniqueKey(item)

        for ItemIndex in range(len(item['Librarys'])):
            Stacked = False

            if not item['UpdateItems'][ItemIndex]:
                LOG.debug("KodiSeasonId %s not found" % item['Id'])
                self.get_kodi_show_id(item, ItemIndex)
                StackedKodiId = self.emby_db.get_stacked_kodiid(item['PresentationUniqueKey'], item['Librarys'][ItemIndex]['Id'], "Season")

                if StackedKodiId:
                    item['KodiItemIds'][ItemIndex] = StackedKodiId
                    Stacked = True
                else:
                    item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_season()
            else:
                self.video_db.delete_links_tags(item['KodiItemIds'][ItemIndex], "season")
                self.video_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "season")

            if Stacked:
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "Season", "season", item['KodiParentIds'], item['LibraryIds'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                LOG.info("ADD stacked season [%s/%s] %s: %s" % (item['KodiParentIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Name'] or item['IndexNumber'], item['Id']))
            else:
                common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
                self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "season")
                self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "season")

                if item['UpdateItems'][ItemIndex]:
                    self.video_db.update_season(item['KodiParentIds'][ItemIndex], item['IndexNumber'], item['Name'], item['KodiItemIds'][ItemIndex])
                    self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                    LOG.info("UPDATE season [%s/%s] %s: %s" % (item['KodiParentIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Name'] or item['IndexNumber'], item['Id']))
                else:
                    self.video_db.add_season(item['KodiItemIds'][ItemIndex], item['KodiParentIds'][ItemIndex], item['IndexNumber'], item['Name'])
                    self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "Season", "season", item['KodiParentIds'], item['LibraryIds'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                    self.video_db.add_path_bookmark(item['KodiParentIds'][ItemIndex], item['IndexNumber'])  # workaround due to Kodi episode bookmark bug
                    LOG.info("ADD season [%s/%s] %s: %s" % (item['KodiParentIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Name'] or item['IndexNumber'], item['Id']))

        return not item['UpdateItems'][ItemIndex]

    def episode(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if not 'MediaSources' in item or not item['MediaSources']:
            LOG.error("No mediasources found for episode: %s" % item['Id'])
            LOG.debug("No mediasources found for episode: %s" % item)
            return False

        if 'SeriesId' not in item:
            LOG.error("No Series assigned to Episode: %s %s" % (item['Id'], item['Name']))
            LOG.debug("No Series assigned to Episode: %s" % item)
            return False

        get_PresentationUniqueKey(item)

        if 'SeasonId' not in item:
            # get seasonID from PresentationUniqueKey
            if item['PresentationUniqueKey']:
                LOG.info("Detect SeasonId by PresentationUniqueKey: %s" % item['PresentationUniqueKey'])
                PresentationUniqueKeySeason = item['PresentationUniqueKey'][:item['PresentationUniqueKey'].rfind("_")]
                item['SeasonId'] = self.emby_db.get_EmbyId_by_EmbyPresentationKey(PresentationUniqueKeySeason)

            if not item['SeasonId']:
                LOG.error("No season assigned to Episode: %s %s" % (item['Id'], item['Name']))
                LOG.debug("No season assigned to Episode: %s" % item)
                return False

        LOG.info("Process item: %s" % item['Name'])
        ItemIndex = 0
        common.set_mpaa(item)
        common.SwopMediaSources(item)  # 3D
        item['OriginalTitle'] = item.get('OriginalTitle', "")
        item['SortIndexNumber'] = item.get('SortIndexNumber', -1)
        item['SortParentIndexNumber'] = item.get('SortParentIndexNumber', -1)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 0)

        # Remove special episode numbers when Season != 0
        if item['ParentIndexNumber']:
            item['SortIndexNumber'] = -1
            item['SortParentIndexNumber'] = -1

        for ItemIndex in range(len(item['Librarys'])):
            if not common.get_file_path(item, "episodes", ItemIndex):
                continue

            if not item['UpdateItems'][ItemIndex]:
                LOG.debug("EpisodeId %s not found" % item['Id'])
                item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_episode()
                item['KodiFileIds'][ItemIndex] = self.video_db.create_entry_file()
                item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None)
            else:
                self.video_db.delete_ratings(item['KodiItemIds'][ItemIndex], "episode")
                common.delete_ContentItemReferences(item['Id'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], self.video_db, self.emby_db, "episode")

            self.get_kodi_show_id(item, ItemIndex)

            # KodiSeasonId
            item['KodiSeasonId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['SeasonId'], item['LibraryIds'][ItemIndex])

            if not item['KodiSeasonId']:
                SeasonItem = self.EmbyServer.API.get_Item(item['SeasonId'], ['Season'], False, False)
                SeasonItem['Library'] = item['Library']
                self.season(SeasonItem)
                item['KodiSeasonId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['SeasonId'], item['LibraryIds'][ItemIndex])

            common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "episode", "e", ItemIndex)
            self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "episode")
            item['Unique'] = self.video_db.add_uniqueids(item['KodiItemIds'][ItemIndex], item['ProviderIds'], "episode", 'tvdb')
            item['RatingId'] = self.video_db.add_ratings(item['KodiItemIds'][ItemIndex], "episode", "default", item['CommunityRating'])

            if item['UpdateItems'][ItemIndex]:
                self.video_db.update_episode(item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['PremiereDate'], item['KodiArtwork']['thumb'], item['RunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['Unique'], item['KodiParentIds'][ItemIndex], item['KodiSeasonId'], item['KodiItemIds'][ItemIndex], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['KodiFileIds'][ItemIndex])
                self.emby_db.update_favourite_markers(item['IntroStartPositionTicks'], item['IntroEndPositionTicks'], item['CreditsPositionTicks'], item['UserData']['IsFavorite'], item['Id'])
                LOG.info("UPDATE episode [%s/%s/%s/%s] %s: %s" % (item['KodiParentIds'][ItemIndex], item['KodiSeasonId'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Id'], item['Name']))
            else:
                self.video_db.add_episode(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['PremiereDate'], item['KodiArtwork']['thumb'], item['RunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['Unique'], item['KodiParentIds'][ItemIndex], item['KodiSeasonId'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'])
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "Episode", "episode", item['KodiParentIds'], item['LibraryIds'], item['SeasonId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], item['IntroStartPositionTicks'], item['IntroEndPositionTicks'], item['CreditsPositionTicks'])
                self.video_db.add_file_bookmark(item['KodiItemIds'][ItemIndex], item['KodiSeasonId'], item['KodiParentIds'][ItemIndex], item['ChapterInfo'], item['RunTimeTicks'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate']) # workaround due to Kodi episode bookmark bug
                LOG.info("ADD episode [%s/%s/%s/%s] %s: %s" % (item['KodiParentIds'][ItemIndex], item['KodiSeasonId'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Id'], item['Name']))

            self.emby_db.add_multiversion(item, "Episode", self.EmbyServer.API, self.video_db, item['UpdateItems'][ItemIndex])

        return not item['UpdateItems'][ItemIndex]

    def get_kodi_show_id(self, Item, ItemIndex):
        Item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(Item['SeriesId'], Item['LibraryIds'][ItemIndex])

        if not Item['KodiParentIds'][ItemIndex]:
            TVShowItem = self.EmbyServer.API.get_Item(Item['SeriesId'], ['Series'], False, False)
            LOG.info("Add TVShow by SeriesId %s" % Item['SeriesId'])
            TVShowItem['Library'] = Item['Library']
            TVShowItem['ServerId'] = TVShowItem['ServerId']
            self.tvshow(TVShowItem)
            Item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(Item['SeriesId'], Item['LibraryIds'][ItemIndex])

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        Item['Library'] = {}

        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        for ItemIndex in range(len(Item['Librarys'])):
            self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemIds'][ItemIndex], Item['KodiType'])

            if Item['KodiType'] == "episode":
                if Item['PlaybackPositionTicks'] and Item['PlayedPercentage']:
                    RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
                else:
                    RuntimeSeconds = 0

                common.set_userdata_update_data(Item)
                self.video_db.update_bookmark_playstate(Item['KodiFileIds'][ItemIndex], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
                pluginmenu.reset_episodes_cache()

            self.emby_db.update_favourite(Item['IsFavorite'], Item['Id'])
            LOG.info("USERDATA [%s/%s/%s] %s" % (Item['KodiType'], Item['KodiFileIds'][ItemIndex], Item['KodiItemIds'][ItemIndex], Item['Id']))

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if Item['Type'] == 'Episode':
            self.remove_episode(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "Episode")

                # multiversion
                if StackedIds:
                    LOG.info("DELETE multi version episodes from embydb %s" % Item['Id'])

                    for StackedId in StackedIds:
                        self.emby_db.remove_item(StackedId[0], Item['Library']['Id'])

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['Episode'], False, False)

                        if StackedItem:
                            StackedItem['Library'] = Item['Library']
                            LOG.info("UPDATE remaining multi version episode %s" % StackedItem['Id'])
                            self.episode(StackedItem)  # update all stacked items
                else: # single version
                    KodiSeasonsData = self.emby_db.get_item_by_KodiId_KodiType(Item['KodiParentId'], "season")

                    # delete empty season
                    for KodiSeasonData in KodiSeasonsData:
                        if not self.emby_db.get_item_by_parent_id(Item['KodiParentId'], "episode"):  # check if nor more episodes assigned to season
                            KodiTVShowsData = self.emby_db.get_item_by_KodiId_KodiType(KodiSeasonData[7], "tvshow")
                            self.remove_season(Item['KodiParentId'], KodiSeasonData[0], Item['Library']['Id'])

                            # delete empty tvshow
                            for KodiTVShowData in KodiTVShowsData:
                                if not self.emby_db.get_item_by_parent_id(KodiSeasonData[7], "season"):
                                    self.remove_tvshow(KodiSeasonData[7], KodiTVShowData[0], Item['Library']['Id'])
        elif Item['Type'] == 'Series':
            self.remove_tvshow(Item['KodiItemId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                LOG.info("DELETE stacked tvshow [%s] %s" % (Item['KodiItemId'], Item['Id']))
                StackedSeasonItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Season")

                for StackedSeasonItem in StackedSeasonItems:
                    self.remove_season(StackedSeasonItem[4], StackedSeasonItem[0], Item['Library']['Id'])
                    LOG.info("DELETE stacked season [%s] %s" % (StackedSeasonItem[4], StackedSeasonItem[0]))
                    StackedItems = self.emby_db.get_items_by_embyparentid(StackedSeasonItem[0], Item['Library']['Id'], "Episode")

                    for StackedItem in StackedItems:
                        self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0], Item['Library']['Id'])
                        LOG.info("DELETE stacked episode [%s/%s] %s" % (StackedItem[4], StackedItem[5], StackedItem[0]))
        elif Item['Type'] == 'Season':
            self.remove_season(Item['KodiItemId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                LOG.info("DELETE stacked season [%s] %s" % (Item['KodiItemId'], Item['Id']))
                StackedItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Episode")

                for StackedItem in StackedItems:
                    self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0], Item['Library']['Id'])
                    LOG.info("DELETE stacked episode [%s/%s] %s" % (StackedItem[4], StackedItem[5], StackedItem[0]))

    def remove_tvshow(self, KodiTVShowId, EmbyItemId, EmbyLibrayId):
        self.video_db.common.delete_artwork(KodiTVShowId, "tvshow")
        self.video_db.delete_tvshow(KodiTVShowId)
        self.video_db.delete_links_tags(KodiTVShowId, "tvshow")
        self.video_db.delete_link_tvshow(KodiTVShowId)
        self.emby_db.remove_item(EmbyItemId, EmbyLibrayId)
        LOG.info("DELETE tvshow [%s] %s" % (KodiTVShowId, EmbyItemId))

    def remove_season(self, KodiSeasonId, EmbyItemId, EmbyLibrayId):
        self.video_db.common.delete_artwork(KodiSeasonId, "season")
        self.video_db.delete_path_bookmark(KodiSeasonId)  # workaround due to Kodi episode bookmark bug
        self.video_db.delete_season(KodiSeasonId)
        self.video_db.delete_links_tags(KodiSeasonId, "season")
        self.emby_db.remove_item(EmbyItemId, EmbyLibrayId)
        LOG.info("DELETE season [%s] %s" % (KodiSeasonId, EmbyItemId))

    def remove_episode(self, KodiItemId, KodiFileId, EmbyItemId, EmbyLibraryId):
        self.video_db.delete_file_bookmark(KodiItemId)  # workaround due to Kodi episode bookmark bug
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "episode", EmbyLibraryId)
        self.video_db.delete_episode(KodiItemId, KodiFileId)
        LOG.info("DELETE episode [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

def get_PresentationUniqueKey(Item):
    if "PresentationUniqueKey" in Item:
        Item['PresentationUniqueKey'] = Item['PresentationUniqueKey'].replace("-", "_").replace(" ", "")
    else:
        Item['PresentationUniqueKey'] = None

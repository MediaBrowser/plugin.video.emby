import xbmc
from helper import pluginmenu
from . import common


class TVShows:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.video_db.init_favorite_tags()

    def tvshow(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "Series"):
            return False

        if not 'Name' in item:
            xbmc.log(f"EMBY.core.music: Process item: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.tvshows: Process item: {item['Name']}", 1) # LOGINFO
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
                xbmc.log(f"EMBY.core.tvshows: KodiItemId {item['Id']} not found", 0) # LOGDEBUG
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

            KodiPathParentId = self.video_db.get_add_path(item['PathParent'], "tvshows", None)
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None, KodiPathParentId)

            if Stacked:
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], item['KodiPathId'], "Series", "tvshow", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                xbmc.log(f"EMBY.core.tvshows: ADD stacked tvshow [{item['KodiPathId']} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO
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
                    xbmc.log(f"EMBY.core.tvshows: UPDATE tvshow [{item['KodiPathId']} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO
                else:
                    self.video_db.add_tvshow(item['KodiItemIds'][ItemIndex], item['Name'], item['Overview'], item['Status'], item['RatingId'], item['PremiereDate'], item['KodiArtwork']['poster'], item['Genre'], item['OriginalTitle'], item['KodiArtwork']['fanart'].get('fanart', ""), item['Unique'], item['OfficialRating'], item['Studio'], item['SortName'], item['RunTimeTicks'], item['Trailer'])
                    self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], item['KodiPathId'], "Series", "tvshow", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                    self.video_db.add_link_tvshow(item['KodiItemIds'][ItemIndex], item['KodiPathId'])
                    xbmc.log(f"EMBY.core.tvshows: ADD tvshow [{item['KodiPathId']} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO

            self.video_db.add_tags_and_links(item['KodiItemIds'][ItemIndex], "tvshow", item['TagItems'])

        return not item['UpdateItems'][ItemIndex]

    def season(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "Season"):
            return False

        if 'SeriesId' not in item:
            xbmc.log(f"EMBY.core.tvshows: No SeriesId assigned to Season: {item['Id']} {item['Name']}", 3) # LOGERROR
            xbmc.log(f"EMBY.core.tvshows: No SeriesId assigned to Season: {item}", 0) # LOGDEBUG
            return False

        if not 'Name' in item:
            xbmc.log(f"EMBY.core.music: Process item: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.tvshows: Process item: {item['Name']}", 1) # LOGINFO
        ItemIndex = 0
        item['IndexNumber'] = item.get('IndexNumber', 0)
        get_PresentationUniqueKey(item)

        for ItemIndex in range(len(item['Librarys'])):
            Stacked = False

            if not item['UpdateItems'][ItemIndex]:
                xbmc.log(f"EMBY.core.tvshows: KodiSeasonId {item['Id']} not found", 0) # LOGDEBUG

                if not self.get_kodi_show_id(item, ItemIndex):
                    xbmc.log(f"EMBY.core.tvshows: Season, tvshow invalid assignment: {item['Id']}", 2) # LOGWARNING
                    xbmc.log(f"EMBY.core.tvshows: Season, tvshow invalid assignment: {item}", 0) # LOGDEBUG
                    continue

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
                xbmc.log(f"EMBY.core.tvshows: ADD stacked season [{item['KodiParentIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO
            else:
                common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
                self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "season")
                self.video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "season")

                if item['UpdateItems'][ItemIndex]:
                    self.video_db.update_season(item['KodiParentIds'][ItemIndex], item['IndexNumber'], item['Name'], item['KodiItemIds'][ItemIndex])
                    self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                    xbmc.log(f"EMBY.core.tvshows: UPDATE season [{item['KodiParentIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO
                else:
                    self.video_db.add_season(item['KodiItemIds'][ItemIndex], item['KodiParentIds'][ItemIndex], item['IndexNumber'], item['Name'])
                    self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "Season", "season", item['KodiParentIds'], item['LibraryIds'], item['SeriesId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                    self.video_db.add_season_bookmark(item['KodiParentIds'][ItemIndex], item['IndexNumber'])  # workaround due to Kodi episode bookmark bug
                    xbmc.log(f"EMBY.core.tvshows: ADD season [{item['KodiParentIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Name'] or item['IndexNumber']}: {item['Id']}", 1) # LOGINFO

        return not item['UpdateItems'][ItemIndex]

    def episode(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "Episode"):
            return False

        if not common.verify_content(item, "episode"):
            return False

        xbmc.log(f"EMBY.core.tvshows: Process item: {item['Name']}", 1) # LOGINFO

        if 'SeriesId' not in item:
            xbmc.log(f"EMBY.core.tvshows: No SeriesId assigned to Episode: {item['Id']} {item['Name']}", 3) # LOGERROR
            xbmc.log(f"EMBY.core.tvshows: No SeriesId assigned to Episode: {item}", 0) # LOGDEBUG
            return False

        get_PresentationUniqueKey(item)

        if 'SeasonId' not in item:
            # get seasonID from PresentationUniqueKey
            if item['PresentationUniqueKey']:
                xbmc.log(f"EMBY.core.tvshows: Detect SeasonId by PresentationUniqueKey: {item['PresentationUniqueKey']}", 1) # LOGINFO
                PresentationUniqueKeySeason = item['PresentationUniqueKey'][:item['PresentationUniqueKey'].rfind("_")]
                item['SeasonId'] = self.emby_db.get_EmbyId_by_EmbyPresentationKey(PresentationUniqueKeySeason)

            # Inject fake season 0 e.g. for recordings
            if not item['SeasonId']:
                xbmc.log(f"EMBY.core.tvshows: No season assigned to Episode: {item['Id']} {item['Name']}", 3) # LOGERROR
                xbmc.log(f"EMBY.core.tvshows: No season assigned to Episode: {item}", 0) # LOGDEBUG

                for ItemIndex in range(len(item['Librarys'])):
                    SeasonItem = {'Id': f"999999997{item['Id']}", 'Name': "Season 0", 'IndexNumber': 0, 'SeriesId': item['SeriesId'], 'Library': item['Librarys'][ItemIndex], 'Type': "Season", 'PresentationUniqueKey': f"{item['PresentationUniqueKey']}-000", 'UserData': {'IsFavorite': 0}}
                    self.season(SeasonItem)

                item['SeasonId'] = SeasonItem['Id']

        ItemIndex = 0
        common.set_mpaa(item)
        common.SwopMediaSources(item)  # 3D
        item['OriginalTitle'] = item.get('OriginalTitle', "")
        item['SortIndexNumber'] = item.get('SortIndexNumber', -1)
        item['SortParentIndexNumber'] = item.get('SortParentIndexNumber', -1)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['CommunityRating'] = item.get('CommunityRating', None)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 0)
        item['Settings'] = len(item['Librarys']) * [{}]

        # Remove special episode numbers when Season != 0
        if item['ParentIndexNumber']:
            item['SortIndexNumber'] = -1
            item['SortParentIndexNumber'] = -1

        for ItemIndex in range(len(item['Librarys'])):
            if item['KodiItemIds'][ItemIndex]: # existing item
                item['Settings'][ItemIndex] = self.video_db.get_settings(item['KodiFileIds'][ItemIndex])
                self.remove_episode(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Id'], item['LibraryIds'][ItemIndex])

            if not common.get_file_path(item, "episodes", ItemIndex):
                continue

            item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_episode()
            item['KodiFileIds'][ItemIndex] = self.video_db.create_entry_file()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], None)

            if not self.get_kodi_show_id(item, ItemIndex):
                xbmc.log(f"EMBY.core.tvshows: Episode, tvshow invalid assignment: {item['Id']}", 2) # LOGWARNING
                xbmc.log(f"EMBY.core.tvshows: Episode, tvshow invalid assignment: {item}", 0) # LOGDEBUG
                continue

            # KodiSeasonId
            item['KodiSeasonId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['SeasonId'], item['LibraryIds'][ItemIndex])

            if not item['KodiSeasonId']:
                SeasonItem = self.EmbyServer.API.get_Item(item['SeasonId'], ['Season'], False, False)

                if not SeasonItem:
                    xbmc.log(f"EMBY.core.tvshows: Episode, season invalid assignment: {item['Id']}", 2) # LOGWARNING
                    xbmc.log(f"EMBY.core.tvshows: Episode, season invalid assignment: {item}", 0) # LOGDEBUG
                    continue

                SeasonItem['Library'] = item['Library']
                self.season(SeasonItem)
                item['KodiSeasonId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['SeasonId'], item['LibraryIds'][ItemIndex])

            common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "episode", ItemIndex)
            self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "episode")
            item['Unique'] = self.video_db.add_uniqueids(item['KodiItemIds'][ItemIndex], item['ProviderIds'], "episode", 'tvdb')
            item['RatingId'] = self.video_db.add_ratings(item['KodiItemIds'][ItemIndex], "episode", "default", item['CommunityRating'])
            self.video_db.add_episode(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['PremiereDate'], item['KodiArtwork']['thumb'], item['RunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], f"{item['Path']}{item['Filename']}", item['KodiPathId'], item['Unique'], item['KodiParentIds'][ItemIndex], item['KodiSeasonId'], item['Filename'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'])
            self.emby_db.add_reference(item['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "Episode", "episode", item['KodiParentIds'], item['LibraryIds'], item['SeasonId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], item['IntroStartPositionTicks'], item['IntroEndPositionTicks'], item['CreditsPositionTicks'])
            self.video_db.add_episode_bookmark(item['KodiItemIds'][ItemIndex], item['KodiSeasonId'], item['KodiParentIds'][ItemIndex], item['ChapterInfo'], item['RunTimeTicks'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate']) # workaround due to Kodi episode bookmark bug
            self.emby_db.add_multiversion(item, "Episode", self.EmbyServer.API, self.video_db, ItemIndex)

            if item['Settings'][ItemIndex]:
                self.video_db.add_settings(item['KodiFileIds'][ItemIndex], item['Settings'][ItemIndex])

            if item['UpdateItems'][ItemIndex]:
                xbmc.log(f"EMBY.core.tvshows: UPDATE episode [{item['KodiParentIds'][ItemIndex]} / {item['KodiSeasonId']} / {item['KodiItemIds'][ItemIndex]} / {item['KodiFileIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO
            else:
                xbmc.log(f"EMBY.core.tvshows: ADD episode [{item['KodiParentIds'][ItemIndex]} / {item['KodiSeasonId']} / {item['KodiItemIds'][ItemIndex]} / {item['KodiFileIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO

        return not item['UpdateItems'][ItemIndex]

    def get_kodi_show_id(self, Item, ItemIndex):
        Item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(Item['SeriesId'], Item['LibraryIds'][ItemIndex])

        if not Item['KodiParentIds'][ItemIndex]:
            TVShowItem = self.EmbyServer.API.get_Item(Item['SeriesId'], ['Series'], False, False)

            if not TVShowItem:
                return False

            xbmc.log(f"EMBY.core.tvshows: Add TVShow by SeriesId {Item['SeriesId']}", 1) # LOGINFO
            TVShowItem['Library'] = Item['Library']
            self.tvshow(TVShowItem)
            Item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(Item['SeriesId'], Item['LibraryIds'][ItemIndex])

        return True

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        for ItemIndex in range(len(Item['Librarys'])):
            self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemIds'][ItemIndex], Item['KodiType'])

            if Item['KodiType'] == "episode":
                if Item['PlaybackPositionTicks'] and Item['PlayedPercentage']:
                    RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
                else:
                    RuntimeSeconds = 0

                common.set_playstate(Item)
                self.video_db.update_bookmark_playstate(Item['KodiFileIds'][ItemIndex], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
                pluginmenu.reset_querycache()

            self.emby_db.update_favourite(Item['IsFavorite'], Item['Id'])
            xbmc.log(f"EMBY.core.tvshows: USERDATA [{Item['KodiType']} / {Item['KodiFileIds'][ItemIndex]} / {Item['KodiItemIds'][ItemIndex]}] {Item['Id']}", 1) # LOGINFO

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if Item['Type'] == 'Episode':
            self.remove_episode(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "Episode")

                # multiversion
                if StackedIds:
                    xbmc.log(f"EMBY.core.tvshows: DELETE multi version episodes from embydb {Item['Id']}", 1) # LOGINFO

                    for StackedId in StackedIds:
                        StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['Episode'], False, False)

                        if StackedItem:
                            StackedItem['Library'] = Item['Library']
                            xbmc.log(f"EMBY.core.tvshows: UPDATE remaining multi version episode {StackedItem['Id']}", 1) # LOGINFO
                            self.episode(StackedItem)  # update all remaining multiversion items
                        else:
                            self.emby_db.remove_item(StackedId[0], Item['Library']['Id'])
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
                xbmc.log(f"EMBY.core.tvshows: DELETE stacked tvshow [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
                StackedSeasonItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Season")

                for StackedSeasonItem in StackedSeasonItems:
                    self.remove_season(StackedSeasonItem[4], StackedSeasonItem[0], Item['Library']['Id'])
                    xbmc.log(f"EMBY.core.tvshows: DELETE stacked season [{StackedSeasonItem[4]}] {StackedSeasonItem[0]}", 1) # LOGINFO
                    StackedItems = self.emby_db.get_items_by_embyparentid(StackedSeasonItem[0], Item['Library']['Id'], "Episode")

                    for StackedItem in StackedItems:
                        self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0], Item['Library']['Id'])
                        xbmc.log(f"EMBY.core.tvshows: DELETE stacked episode [{StackedItem[4]} / {StackedItem[5]}] {StackedItem[0]}", 1) # LOGINFO
        elif Item['Type'] == 'Season':
            self.remove_season(Item['KodiItemId'], Item['Id'], Item['Library']['Id'])

            if not Item['DeleteByLibraryId']:
                xbmc.log(f"EMBY.core.tvshows: DELETE stacked season [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
                StackedItems = self.emby_db.get_items_by_embyparentid(Item['Id'], Item['Library']['Id'], "Episode")

                for StackedItem in StackedItems:
                    self.remove_episode(StackedItem[4], StackedItem[5], StackedItem[0], Item['Library']['Id'])
                    xbmc.log(f"EMBY.core.tvshows: DELETE stacked episode [{StackedItem[4]} / {StackedItem[5]}] {StackedItem[0]}", 1) # LOGINFO

    def remove_tvshow(self, KodiTVShowId, EmbyItemId, EmbyLibrayId):
        self.video_db.common.delete_artwork(KodiTVShowId, "tvshow")
        self.video_db.delete_tvshow(KodiTVShowId)
        self.video_db.delete_links_tags(KodiTVShowId, "tvshow")
        self.video_db.delete_link_tvshow(KodiTVShowId)
        self.emby_db.remove_item(EmbyItemId, EmbyLibrayId)
        xbmc.log(f"EMBY.core.tvshows: DELETE tvshow [{KodiTVShowId}] {EmbyItemId}", 1) # LOGINFO

    def remove_season(self, KodiSeasonId, EmbyItemId, EmbyLibrayId):
        self.video_db.common.delete_artwork(KodiSeasonId, "season")
        self.video_db.delete_season_bookmark(KodiSeasonId)  # workaround due to Kodi episode bookmark bug
        self.video_db.delete_season(KodiSeasonId)
        self.video_db.delete_links_tags(KodiSeasonId, "season")
        self.emby_db.remove_item(EmbyItemId, EmbyLibrayId)
        xbmc.log(f"EMBY.core.tvshows: DELETE season [{KodiSeasonId}] {EmbyItemId}", 1) # LOGINFO

    def remove_episode(self, KodiItemId, KodiFileId, EmbyItemId, EmbyLibraryId):
        self.video_db.delete_episode_bookmark(KodiItemId, KodiItemId)  # workaround due to Kodi episode bookmark bug
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "episode", EmbyLibraryId)
        self.video_db.delete_episode(KodiItemId, KodiFileId)
        xbmc.log(f"EMBY.core.tvshows: DELETE episode [{KodiItemId} / {KodiFileId}] {EmbyItemId}", 1) # LOGINFO

def get_PresentationUniqueKey(Item):
    if "PresentationUniqueKey" in Item:
        Item['PresentationUniqueKey'] = Item['PresentationUniqueKey'].replace("-", "_").replace(" ", "")
    else:
        Item['PresentationUniqueKey'] = None

import xbmc
from helper import pluginmenu, utils
from . import common, series, season, genre, studio, person


class Episode:
    def __init__(self, EmbyServer, SQLs, SeasonObject=None, SeriesObject=None):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

        if SeriesObject:
            self.SeriesObject = SeriesObject
        else:
            self.SeriesObject = series.Series(EmbyServer, self.SQLs)

        if SeasonObject:
            self.SeasonObject = SeasonObject
        else:
            self.SeasonObject = season.Season(EmbyServer, self.SQLs)

        self.GenreObject = genre.Genre(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)

    def change(self, item):
        if not common.verify_content(item, "episode"):
            return False

        xbmc.log(f"EMBY.core.episode: Process item: {item['Name']}", 0) # DEBUG
        common.load_ExistingItem(item, self.EmbyServer, self.SQLs["emby"], "Episode")
        common.set_ItemsDependencies(item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series")
        common.set_ItemsDependencies(item, self.SQLs, self.SeasonObject, self.EmbyServer, "Season")
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_chapters(item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems")
        common.set_MetaItems(item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios")
        common.get_path(item, self.EmbyServer.ServerData['ServerId'])
        self.SQLs["emby"].add_streamdata(item['Id'], item['Streams'])
        common.set_people(item, self.SQLs, self.PersonObject, self.EmbyServer)
        common.set_common(item, self.EmbyServer.ServerData['ServerId'], False)
        common.SwopMediaSources(item)  # 3D
        item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(item['SeriesId'], "Series")
        KodiSeasonId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(item['SeasonId'], "Season")
        SeasonNumber = self.SQLs["video"].get_season_number(KodiSeasonId)

        # Check if ParentIndexNumber (Season number) not in Kodi database
        if item['ParentIndexNumber']:
            if SeasonNumber != item['ParentIndexNumber']:
                xbmc.log(f"EMBY.core.episode: Season number, assigned by episode (ParentIndexNumber) [{item['ParentIndexNumber']}] not matching season number by SeasonId [{SeasonNumber}]", 2) # LOGWARNING
        else:
            xbmc.log("EMBY.core.episode: ParentIndexNumber not found, try to detect season by SeasonId", 2) # LOGWARNING
            item['ParentIndexNumber'] = SeasonNumber

        if item['UpdateItem']:
            common.delete_ContentItemReferences(item, self.SQLs, "episode")

            if common.update_downloaded_info(item, self.SQLs):
                KodiPath = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content")
                KodiPath = utils.PathAddTrailing(f"{KodiPath}episode")
            else:
                KodiPath = item['KodiPath']
        else:
            item['KodiItemId'] = self.SQLs["video"].create_entry_episode()
            item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            item['KodiPathId'] = self.SQLs["video"].get_add_path(item['KodiPath'], None)

        common.set_VideoCommon(item, self.SQLs, "episode", self.EmbyServer.API)
        common.set_Genre_links(item['KodiItemId'], self.SQLs, "episode", item["GenreItems"])
        common.set_Studio_links(item['KodiItemId'], self.SQLs, "episode", item["Studios"])
        common.set_Actor_links(item['KodiItemId'], self.SQLs, "episode", item["CastItems"])
        common.set_Writer_links(item['KodiItemId'], self.SQLs, "episode", item["WritersItems"])
        common.set_Director_links(item['KodiItemId'], self.SQLs, "episode", item["DirectorsItems"])
        item['Unique'] = self.SQLs["video"].add_uniqueids(item['KodiItemId'], item['ProviderIds'], "episode", 'tvdb')
        item['RatingId'] = self.SQLs["video"].add_ratings(item['KodiItemId'], "episode", "default", item['CommunityRating'])

        if item['UpdateItem']:
            self.SQLs["video"].update_episode(item['KodiItemId'], item['KodiFileId'], item['KodiName'], item['Overview'], item['RatingId'], item['Writers'], item['KodiPremiereDate'], item['KodiArtwork']['thumb'], item['KodiRunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], KodiPath, item['KodiFilename'], item['KodiPathId'], item['Unique'], item['KodiParentId'], KodiSeasonId, item['KodiPlayCount'], item['KodiLastPlayedDate'], item['KodiStackedFilename'])
            self.SQLs["emby"].update_reference_episode(item['Id'], item['UserData']['IsFavorite'], item['KodiParentId'], item['PresentationUniqueKey'], item['IntroStartPositionTicks'], item['IntroEndPositionTicks'], item['LibraryId'])
            xbmc.log(f"EMBY.core.episode: UPDATE [{item['KodiParentId']} / {KodiSeasonId} / {item['KodiItemId']} / {item['KodiFileId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO
        else:
            self.SQLs["video"].add_episode(item['KodiItemId'], item['KodiFileId'], item['Name'], item['Overview'], item['RatingId'], item['Writers'], item['KodiPremiereDate'], item['KodiArtwork']['thumb'], item['KodiRunTimeTicks'], item['Directors'], item['ParentIndexNumber'], item['IndexNumber'], item['OriginalTitle'], item['SortParentIndexNumber'], item['SortIndexNumber'], item['KodiPath'], item['KodiFilename'], item['KodiPathId'], item['Unique'], item['KodiParentId'], KodiSeasonId, item['KodiFilename'], item['KodiDateCreated'], item['KodiPlayCount'], item['KodiLastPlayedDate'], item['ChapterInfo'], item['KodiStackedFilename'])
            self.SQLs["emby"].add_reference_episode(item['Id'], item['LibraryId'], item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiFileId'], item['KodiParentId'], item['PresentationUniqueKey'], item['Path'], item['KodiPathId'], item['IntroStartPositionTicks'], item['IntroEndPositionTicks'])
            xbmc.log(f"EMBY.core.episode: ADD [{item['KodiParentId']} / {KodiSeasonId} / {item['KodiItemId']} / {item['KodiFileId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO

        self.SQLs["emby"].add_multiversion(item, "Episode", self.EmbyServer.API, self.SQLs)
        utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], item['UserData']['IsFavorite'], f"{item['KodiPath']}{item['KodiFilename']}", item['Name'], "media", 0),))
        return not item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Episode")
        pluginmenu.reset_querycache("Episode")
        xbmc.log(f"EMBY.core.episode: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item):
        if common.delete_ContentItem(Item, self.SQLs, "episode", "Episode"):
            self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'])
            self.SQLs["video"].delete_episode(Item['KodiItemId'], Item['KodiFileId'])
            xbmc.log(f"EMBY.core.episode: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "Episode")

    def set_favorite(self, isFavorite, KodiFileId, KodiItemId):
        FullPath, Image, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "episode")
        utils.FavoriteQueue.put(((Image, isFavorite, FullPath, Itemname, "media", 0),))

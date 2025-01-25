import xbmc
from helper import utils
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

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "episode"):
            return False

        xbmc.log(f"EMBY.core.episode: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Episode"):
            return False

        common.swap_mediasources(Item)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", None, -1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", None, -1, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        common.set_ItemsDependencies(Item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series", IncrementalSync)
        common.set_ItemsDependencies(Item, self.SQLs, self.SeasonObject, self.EmbyServer, "Season", IncrementalSync)
        Item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeriesId'], "Series")
        KodiSeasonId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeasonId'], "Season")
        SeasonNumber = self.SQLs["video"].get_season_number(KodiSeasonId)
        KodiPath = ""

        # Check if ParentIndexNumber (Season number) not in Kodi database
        if Item['ParentIndexNumber']:
            if SeasonNumber != Item['ParentIndexNumber']:
                xbmc.log(f"EMBY.core.episode: Episode name: {Item['Name']} / SeriesName: {Item.get('SeriesName', 'unknown')} -> Season number, assigned by episode (ParentIndexNumber) [{Item['ParentIndexNumber']}] not matching season number by SeasonId [{SeasonNumber}]", 2) # LOGWARNING
        else:
            xbmc.log(f"EMBY.core.episode: Episode name: {Item['Name']} / SeriesName: {Item.get('SeriesName', 'unknown')} -> ParentIndexNumber not found, try to detect season by SeasonNumber", 2) # LOGWARNING
            Item['ParentIndexNumber'] = SeasonNumber

        if Item['UpdateItem']:
            common.delete_ContentItemReferences(Item, self.SQLs, "episode")
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)

            if common.update_downloaded_info(Item, self.SQLs):
                KodiPath = utils.PathAddTrailing(f"{utils.DownloadPath}EMBY-offline-content")
                KodiPath = utils.PathAddTrailing(f"{KodiPath}episode")
            else:
                KodiPath = Item['KodiPath']
        else:
            Item['KodiItemId'] = self.SQLs["video"].create_entry_episode()
            Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            Item['KodiPathId'] = self.SQLs["video"].get_add_path(Item['KodiPath'], None)

        common.set_VideoCommon(Item, self.SQLs, "episode")
        common.set_Genre_links(Item['KodiItemId'], self.SQLs, "episode", Item["GenreItems"])
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "episode", Item["Studios"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "episode", Item["CastItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "episode", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "episode", Item["DirectorsItems"])
        Item['KodiUniqueId'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "episode", 'tvdb')
        Item['KodiRatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "episode", "default", Item['CommunityRating'])

        if Item['UpdateItem']:
            self.SQLs["video"].update_episode(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['KodiRatingId'], Item['Writers'], Item['KodiPremiereDate'], Item['KodiArtwork']['thumb'], Item['KodiRunTimeTicks'], Item['Directors'], Item['ParentIndexNumber'], Item['IndexNumber'], Item['OriginalTitle'], Item['SortParentIndexNumber'], Item['SortIndexNumber'], KodiPath, Item['KodiFilename'], Item['KodiPathId'], Item['KodiUniqueId'], Item['KodiParentId'], KodiSeasonId, Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiStackedFilename'], Item['KodiDateCreated'])
            self.SQLs["emby"].update_reference_episode(Item['Id'], Item['UserData']['IsFavorite'], Item['KodiParentId'], Item['PresentationUniqueKey'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.episode: UPDATE [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, IncrementalSync)
        else:
            self.SQLs["video"].add_episode(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['KodiRatingId'], Item['Writers'], Item['KodiPremiereDate'], Item['KodiArtwork']['thumb'], Item['KodiRunTimeTicks'], Item['Directors'], Item['ParentIndexNumber'], Item['IndexNumber'], Item['OriginalTitle'], Item['SortParentIndexNumber'], Item['SortIndexNumber'], Item['KodiPath'], Item['KodiFilename'], Item['KodiPathId'], Item['KodiUniqueId'], Item['KodiParentId'], KodiSeasonId, Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiStackedFilename'])
            self.SQLs["emby"].add_reference_episode(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['UserData']['IsFavorite'], Item['KodiFileId'], Item['KodiParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.episode: ADD [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, IncrementalSync)

        self.SQLs["emby"].add_multiversion(Item, "Episode", self.EmbyServer.API, self.SQLs, self.EmbyServer.ServerData['ServerId'])
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Episode", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        Update = self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Episode")
        utils.reset_querycache("Episode")
        xbmc.log(f"EMBY.core.episode: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, True)
        return Update

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item, IncrementalSync):
        if common.delete_ContentItem(Item, self.SQLs, "episode", "Episode"):
            self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
            self.SQLs["video"].delete_episode(Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.episode: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, IncrementalSync)

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "Episode")

    def set_favorite(self, isFavorite, KodiFileId, KodiItemId, EmbyItemId):
        FullPath, ImageUrl, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "episode")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Episode", "TV Shows", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, FullPath, Itemname, "media", 0),))

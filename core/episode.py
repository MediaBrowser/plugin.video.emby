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

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.SeriesObject.update_SQLs(self.SQLs)
        self.SeasonObject.update_SQLs(self.SQLs)
        self.GenreObject.update_SQLs(self.SQLs)
        self.StudioObject.update_SQLs(self.SQLs)
        self.PersonObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "episode"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.episode (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Episode"):
            return False

        common.swap_mediasources(Item)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(Item, self.SQLs, self.GenreObject, self.EmbyServer, "Genre", "GenreItems", "", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", "Studios", "", IncrementalSync, Item['LibraryId'])
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        common.set_ItemsDependencies(Item, self.SQLs, self.SeriesObject, self.EmbyServer, "Series", IncrementalSync, Item['LibraryId'])
        common.set_ItemsDependencies(Item, self.SQLs, self.SeasonObject, self.EmbyServer, "Season", IncrementalSync, Item['LibraryId'])
        Item['KodiParentId'] = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeriesId'], "Series")
        KodiSeasonId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['SeasonId'], "Season")
        SeasonNumber = self.SQLs["video"].get_season_number(KodiSeasonId)

        # Check if ParentIndexNumber (Season number) not in Kodi database
        if Item['ParentIndexNumber'] or Item['ParentIndexNumber'] == 0:
            if SeasonNumber != Item['ParentIndexNumber']:
                xbmc.log(f"EMBY.core.episode: Episode name: {Item['Name']} / SeriesName: {Item.get('SeriesName', 'unknown')} -> Season number, assigned by episode (ParentIndexNumber) [{Item['ParentIndexNumber']}] not matching season number by SeasonId [{SeasonNumber}]", 2) # LOGWARNING
        else:
            xbmc.log(f"EMBY.core.episode: Episode name: {Item['Name']} / SeriesName: {Item.get('SeriesName', 'unknown')} -> ParentIndexNumber not found, try to detect season by SeasonNumber", 2) # LOGWARNING
            Item['ParentIndexNumber'] = SeasonNumber

        if Item['UpdateItem']:
            common.delete_ContentItemReferences(Item['KodiItemId'], Item['KodiFileId'], Item.get('ExtraType', ""), self.SQLs, "episode", False)
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            common.update_downloaded_info(Item, self.SQLs, "episode")
        else:
            Item['KodiItemId'] = self.SQLs["video"].create_entry_episode()
            Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            Item['KodiPathId'] = self.SQLs["video"].get_add_path(Item['KodiPath'], None)

        common.set_VideoCommon(Item['KodiItemId'], Item['KodiFileId'], Item, self.SQLs, "episode")
        common.set_Genre_links(Item['KodiItemId'], self.SQLs, "episode", Item["GenreItems"])
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "episode", Item["Studios"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "episode", Item["CastItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "episode", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "episode", Item["DirectorsItems"])
        Item['KodiUniqueId'] = self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "episode", 'tvdb')
        Item['KodiRatingId'] = self.SQLs["video"].add_ratings(Item['KodiItemId'], "episode", "default", Item['CommunityRating'])

        if Item['UpdateItem']:
            self.SQLs["video"].update_episode(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['Overview'], Item['KodiRatingId'], Item['Writers'], Item['KodiPremiereDate'], Item['KodiArtwork']['thumb'], Item['KodiRunTimeTicks'], Item['Directors'], Item['ParentIndexNumber'], Item['IndexNumber'], Item['OriginalTitle'], Item['SortParentIndexNumber'], Item['SortIndexNumber'], Item['KodiPath'], Item['KodiFilename'], Item['KodiPathId'], Item['KodiUniqueId'], Item['KodiParentId'], KodiSeasonId, Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['KodiFullPath'])
            self.SQLs["emby"].update_reference_episode(Item['Id'], Item['KodiParentId'], Item['PresentationUniqueKey'], Item['LibraryId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.episode: UPDATE [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.episode (DEBUG): UPDATE [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, IncrementalSync)
        else:
            self.SQLs["video"].add_episode(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['Overview'], Item['KodiRatingId'], Item['Writers'], Item['KodiPremiereDate'], Item['KodiArtwork']['thumb'], Item['KodiRunTimeTicks'], Item['Directors'], Item['ParentIndexNumber'], Item['IndexNumber'], Item['OriginalTitle'], Item['SortParentIndexNumber'], Item['SortIndexNumber'], Item['KodiFullPath'], Item['KodiPathId'], Item['KodiUniqueId'], Item['KodiParentId'], KodiSeasonId, Item['KodiFilename'], Item['KodiDateCreated'], Item['KodiStackedFilename'])
            self.SQLs["emby"].add_reference_episode(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiFileId'], Item['KodiParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.episode: ADD [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.episode (DEBUG): ADD [{Item['KodiParentId']} / {KodiSeasonId} / {Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, IncrementalSync)

        common.add_multiversion(Item, "Episode", self.EmbyServer, self.SQLs, self.EmbyServer.ServerData['ServerId'], None, None)
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, True):
            return False

        common.set_Favorite(Item)
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        Update = self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Episode")

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.episode: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.episode (DEBUG): USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "episode"}, True)
        return Update

    # Remove showid, fileid, pathid, emby reference.
    # There's no episodes left, delete show and any possible remaining seasons
    def remove(self, Item, IncrementalSync):
        KodiItemId = Item.get('KodiItemId', "")
        KodiFileId = Item.get('KodiFileId', "")

        if common.delete_ContentItem(KodiItemId, KodiFileId, Item, self.SQLs, "episode", "Episode"):
            self.set_favorite(False, Item)
            self.SQLs["video"].delete_episode(KodiItemId, KodiFileId)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.episode: DELETE [{KodiItemId} / {KodiFileId}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.episode (DEBUG): DELETE [{KodiItemId} / {KodiFileId}] {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemId, "KodiType": "episode"}, IncrementalSync)
            common.update_multiversion(self.SQLs["emby"], "Episode", Item['Id'], Item['LibraryId'], Item.get('PresentationUniqueKey', ''))

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item or "KodiFullPath" not in Item:
            Item['KodiFullPath'], Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["video"].get_favoriteData(Item['KodiFileId'], Item['KodiItemId'], "episode")

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Episode", "TV Shows", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, Item['KodiFullPath'], Item['Name'].replace('"', "'"), "media", 0),))

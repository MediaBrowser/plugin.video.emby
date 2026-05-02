import json
import xbmc
from helper import utils
from . import common, musicartist, musicalbum, musicgenre


class Audio:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs.copy()
        self.SQLs['video'] = None
        self.MusicArtistObject = musicartist.MusicArtist(self.EmbyServer, self.SQLs)
        self.MusicAlbumObject = musicalbum.MusicAlbum(self.EmbyServer, self.SQLs)
        self.MusicGenreObject = musicgenre.MusicGenre(self.EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs.copy()
        self.SQLs['video'] = None
        self.MusicArtistObject.update_SQLs(self.SQLs)
        self.MusicAlbumObject.update_SQLs(self.SQLs)
        self.MusicGenreObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync, PlaylistId=""):
        if 'Path' not in Item:
            xbmc.log(f"EMBY.core.audio: Path not found: {Item}", 3) # LOGERROR
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.audio (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Audio"):
            return False

        if 'ExtraType' in Item:
            if Item['ExtraType'] == "ThemeSong": # ThemeVideo
                self.SQLs["emby"].add_reference_audio_parent(Item['Id'], Item['LibraryId'], Item['Path'], Item['ExtraType'], Item['KodiParentId'], Item['EmbyParentType'], json.dumps(Item), Item['ParentId'])
                if utils.DebugLog: xbmc.log(f"EMBY.core.audio (DEBUG): ADD EXTRATYPE {Item['Id']} / {Item['LibraryId']} / {Item['ExtraType']}", 1) # DEBUGLOG
                return False

        common.set_RunTimeTicks(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        Item["MusicAlbum"] = Item.get('Album', None)
        Item["MusicAlbumId"] = Item.get('AlbumId', None)

        # Track and disc number
        if Item['IndexNumber'] and Item['ParentIndexNumber']:
            Item['IndexNumber'] = Item['ParentIndexNumber'] * 65536 + Item['IndexNumber']

        if not Item['IndexNumber']:
            Item['IndexNumber'] = 0 # Mymusic.db does not execpt NULL, it would result in invalid album disc numbers

        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
        Item['KodiPathId'] = self.SQLs["music"].get_add_path(Item['KodiPath'])

        if Item['MediaSources'][0]['KodiStreams']['Audio']:
            Channels = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("channels", None)
            SampleRate = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("SampleRate", None)
            BitRate = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("BitRate", None)
        else:
            Channels = None
            SampleRate = None
            BitRate = None

        # Load Arrays
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])

        # Update all existing Kodi songs
        for Index, LibraryId in enumerate(LibraryIds):
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            UpdateItem = Item.copy()
            UpdateKodiItemIdCurrent = KodiItemIds[Index]
            UpdateItem['LibraryId'] = LibraryId
            EmbyMusicArtistIds, EmbyMusicGenreIds = self.set_metadata(UpdateItem, IncrementalSync)
            common.remove_old_EmbyMusicArtist(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicArtistIds, self.MusicArtistObject, IncrementalSync)
            common.remove_old_EmbyMusicGenre(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicGenreIds, self.MusicGenreObject, IncrementalSync)
            common.remove_old_EmbyMusicAlbum(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], UpdateItem["MusicAlbumId"], self.MusicAlbumObject, IncrementalSync)
            self.SQLs["music"].common_db.delete_artwork(UpdateKodiItemIdCurrent, "song")
            self.SQLs["music"].delete_link_song_artist(UpdateKodiItemIdCurrent)
            KodiAlbumIds, KodiAlbumLibraryIds = self.SQLs["emby"].get_MusicAlbum_by_EmbyId(UpdateItem['MusicAlbumId'])
            KodiAlbumId = KodiAlbumIds[KodiAlbumLibraryIds.index(UpdateItem['LibraryId'])]
            self.SQLs["music"].update_song(UpdateKodiItemIdCurrent, UpdateItem['KodiPathId'], KodiAlbumId, UpdateItem['ArtistItemsName'], UpdateItem['MusicGenre'], UpdateItem['Name'], UpdateItem['IndexNumber'], UpdateItem['KodiRunTimeTicks'], UpdateItem['KodiPremiereDate'], UpdateItem['KodiProductionYear'], UpdateItem['KodiFilename'], UpdateItem['CommunityRating'], UpdateItem['Overview'], UpdateItem['KodiDateCreated'], BitRate, SampleRate, Channels, UpdateItem['ProviderIds']['MusicBrainzTrack'], UpdateItem['ArtistItemsSortName'], UpdateItem['KodiPath'], PlaylistId)
            self.set_links(UpdateItem, UpdateKodiItemIdCurrent)
            self.SQLs["emby"].update_reference_audio(UpdateItem['Id'], UpdateItem['LibraryId'], UpdateItem['MusicAlbumId'], EmbyMusicArtistIds, EmbyMusicGenreIds)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.audio: UPDATE [{KodiAlbumId} / {UpdateKodiItemIdCurrent}] {UpdateItem['Id']} / {UpdateItem['LibraryId']}: {UpdateItem['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.audio (DEBUG): UPDATE [{KodiAlbumId} / {UpdateKodiItemIdCurrent}] {UpdateItem['Id']} / {UpdateItem['LibraryId']}: {UpdateItem['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": UpdateKodiItemIdCurrent, "KodiType": "audio"}, IncrementalSync)
            del UpdateItem

        # New library (insert new Kodi record)
        if Item['LibraryId'] not in LibraryIds:
            EmbyMusicArtistIds, EmbyMusicGenreIds = self.set_metadata(Item, IncrementalSync)
            KodiAlbumIds, KodiAlbumLibraryIds = self.SQLs["emby"].get_MusicAlbum_by_EmbyId(Item['MusicAlbumId'])
            KodiAlbumId = KodiAlbumIds[KodiAlbumLibraryIds.index(Item['LibraryId'])]
            KodiItemIdCurrent = self.SQLs["music"].add_song(Item['KodiPathId'], KodiAlbumId, Item['ArtistItemsName'], Item['MusicGenre'], Item['Name'], Item['IndexNumber'], Item['KodiRunTimeTicks'], Item['KodiPremiereDate'], Item['KodiProductionYear'], Item['KodiFilename'], Item['CommunityRating'], Item['Overview'], Item['KodiDateCreated'], BitRate, SampleRate, Channels, Item['ProviderIds']['MusicBrainzTrack'], Item['ArtistItemsSortName'], Item['LibraryId'])
            Item['LibraryIds'] = common.add_Ids_SingleContent(LibraryIds, Item['LibraryId'])
            Item['KodiItemId'] = common.add_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
            Item['KodiItemIdNew'] = KodiItemIdCurrent
            self.SQLs["emby"].add_reference_audio(Item['Id'], Item['LibraryId'], KodiItemIds, Item['Path'], Item['KodiPathId'], LibraryIds, Item['MusicAlbumId'], EmbyMusicArtistIds, EmbyMusicGenreIds, Item['ParentId'])
            self.set_links(Item, KodiItemIdCurrent)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.audio: ADD [{Item['KodiPathId']} / {KodiAlbumId} / {KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.audio (DEBUG): ADD [{Item['KodiPathId']} / {KodiAlbumId} / {KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "audio"}, IncrementalSync)

        return not Item['UpdateItem']

    def set_metadata(self, Item, IncrementalSync):
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', "music", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "Composers", "music", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "ArtistItems", "music", IncrementalSync, Item['LibraryId'])
        common.set_ItemsDependencies(Item, self.SQLs, self.MusicAlbumObject, self.EmbyServer, "MusicAlbum", IncrementalSync, Item['LibraryId'])
        EmbyMusicArtistIds = common.get_Artist_Ids(Item, True, False, True)
        EmbyMusicGenreIds = common.get_MusicGenre_Ids(Item)
        common.get_MusicArtistInfos(Item, "Composers", self.SQLs)
        common.get_MusicArtistInfos(Item, "ArtistItems", self.SQLs)
        return EmbyMusicArtistIds, EmbyMusicGenreIds

    def set_links(self, Item, KodiItemIdCurrent):
        common.set_MusicArtist_links(KodiItemIdCurrent, self.SQLs, Item["ArtistItems"], Item['LibraryId'], 1)
        common.set_MusicArtist_links(KodiItemIdCurrent, self.SQLs, Item["Composers"], Item['LibraryId'], 2)
        common.set_MusicGenre_links(KodiItemIdCurrent, self.SQLs, "song", Item["GenreItems"], 0)
        self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdCurrent, "song")

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        common.set_playstate(Item)
        self.SQLs["emby"].update_favourite(Item['Id'], Item['IsFavorite'], "Audio")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        for KodiItemId in Item['KodiItemId'].split(","):
            self.SQLs["music"].update_song_metadata(Item['KodiPlayCount'], Item['KodiLastPlayedDate'], KodiItemId)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.audio: USERDATA [{KodiItemId}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.audio (DEBUG): USERDATA [{KodiItemId}] {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": KodiItemId, "KodiType": "audio"}, True)

        return True

    def remove(self, Item, IncrementalSync):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            self.SQLs["emby"].remove_item(Item['Id'], "Audio", Item['LibraryId'])
            return

        LibraryIdsRemove = ()
        self.set_favorite(False, Item)
        LibraryIdStr = str(Item['LibraryId'])
        Item['LibraryIds'], Item['KodiItemId'], _, _ = self.SQLs["emby"].get_KodiIds_LibraryIds_from_ContentItem(Item['Id'], "Audio") # (Re)Load LibraryIds, KodiItemId as refreences could be modify data after
        if not Item['LibraryIds']:
            xbmc.log(f"EMBY.core.audio (DEBUG): SKIP DELETE, LibraryIds not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
            return

        # Load Arrays
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])

        if LibraryIdStr not in LibraryIds:
            if not LibraryIdStr: # Realtime remove
                LibraryIdsRemove = LibraryIds
            else: # Select all items if a playlist library was removed (playlist libraryids syntax: LibraryId_PlaylistId)
                for EmbyLibraryId in LibraryIds:
                    if EmbyLibraryId.startswith(f"{LibraryIdStr}_"):
                        LibraryIdsRemove += (EmbyLibraryId,)
        else:
            LibraryIdsRemove = (LibraryIdStr,)

        for LibraryIdRemove in LibraryIdsRemove:
            if LibraryIdRemove not in LibraryIds:
                if utils.DebugLog: xbmc.log(f"EMBY.core.audio (DEBUG): SKIP DELETE, LibraryId not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
                continue

            Links = self.SQLs['emby'].get_Links(Item['Id'], LibraryIdRemove)
            Deleted = self.SQLs["emby"].remove_item(Item['Id'], "Audio", LibraryIdRemove)
            common.delete_MusicAlbum_Links(LibraryIdRemove, Links, self.MusicAlbumObject, IncrementalSync, self.SQLs["emby"])
            common.delete_MusicArtist_Links(LibraryIdRemove, Links, self.MusicArtistObject, IncrementalSync, self.SQLs["emby"])
            common.delete_MusicGenre_Links(LibraryIdRemove, Links, self.MusicGenreObject, IncrementalSync, self.SQLs["emby"])
            Index = LibraryIds.index(LibraryIdRemove)
            KodiItemIdCurrent = KodiItemIds[Index]
            self.SQLs["music"].delete_song(KodiItemIdCurrent)

            if not Deleted:
                Item['KodiItemId'] = common.del_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
                Item['LibraryIds'] = common.del_Ids_SingleContent(LibraryIds, LibraryIdRemove)
                self.SQLs['emby'].update_references(Item['Id'], Item['KodiItemId'], "Audio", Item['LibraryIds'])

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.audio: DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {LibraryIdRemove}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.audio (DEBUG): DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {LibraryIdRemove}", 1) # LOGDEBUG
            else:
                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.audio: DELETE [{KodiItemIdCurrent}] {Item['Id']} / {LibraryIdRemove}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.audio (DEBUG): DELETE [{KodiItemIdCurrent}] {Item['Id']} / {LibraryIdRemove}", 1) # LOGDEBUG

            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "audio"}, IncrementalSync)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        for KodiItemId in Item['KodiItemId'].split(","):
            if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item or "KodiFullPath" not in Item:
                Item['KodiFullPath'], Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["music"].get_favoriteData(KodiItemId)

            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Song", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, Item['KodiFullPath'], Item['Name'].replace('"', "'"), "media", 0),))

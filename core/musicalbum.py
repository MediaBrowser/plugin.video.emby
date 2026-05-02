import xbmc
from helper import utils
from . import common, musicartist


class MusicAlbum:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs.copy()
        self.SQLs['video'] = None
        self.MusicArtistObject = musicartist.MusicArtist(self.EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs.copy()
        self.SQLs['video'] = None
        self.MusicArtistObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicAlbum"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.musicalbum (DEBUG): Process item: {Item['Name']}", 1) # LOGDEBUG
        common.set_MetaItems(Item, self.SQLs, None, self.EmbyServer, "Studio", 'Studios', "", IncrementalSync, None)
        common.set_RunTimeTicks(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)

        if int(Item['Id']) > 999999900:
            AlbumType = "single"
        else:
            AlbumType = "album"

        if 'Genres' in Item:
            KodiMusicGenre = " / ".join(Item['Genres'])
        else:
            KodiMusicGenre = ""

        # Detect compilations
        Compilation = 0

        if Item.get('AlbumArtist', "").lower() in ("various artists", "various", "various items", "soundtrack", "xvarious artistsx"):
            Compilation = 1

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicalbum: Compilation detected: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicalbum (DEBUG): Compilation detected: {Item['Name']}", 1) # LOGDEBUG

        # Load Arrays
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])

        # Update all existing Kodi Albums
        for Index, LibraryId in enumerate(LibraryIds):
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            UpdateItem = Item.copy()
            UpdateKodiItemIdCurrent = KodiItemIds[Index]
            UpdateItem['LibraryId'] = LibraryId
            EmbyMusicArtistIds = self.set_metadata(UpdateItem, IncrementalSync)
            common.remove_old_EmbyMusicArtist(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicArtistIds, self.MusicArtistObject, IncrementalSync)
            self.SQLs["music"].common_db.delete_artwork(UpdateKodiItemIdCurrent, "album")
            self.SQLs["music"].delete_link_album_artist(UpdateKodiItemIdCurrent)
            self.SQLs["music"].update_album(UpdateKodiItemIdCurrent, UpdateItem['Name'], AlbumType, UpdateItem['AlbumArtistsName'], UpdateItem['KodiProductionYear'], UpdateItem['KodiPremiereDate'], KodiMusicGenre, UpdateItem['Overview'], UpdateItem['KodiArtwork']['thumb'], UpdateItem['CommunityRating'], UpdateItem['KodiLastScraped'], UpdateItem['KodiDateCreated'], UpdateItem['ProviderIds']['MusicBrainzAlbum'], UpdateItem['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, UpdateItem['Studio'], UpdateItem['KodiRunTimeTicks'], UpdateItem['AlbumArtistsSortName'])
            common.set_MusicArtist_links(UpdateKodiItemIdCurrent, self.SQLs, UpdateItem["AlbumArtists"], UpdateItem['LibraryId'], None)
            self.SQLs["music"].common_db.add_artwork(UpdateItem['KodiArtwork'], UpdateKodiItemIdCurrent, "album")
            self.SQLs["emby"].update_reference_musicalbum(UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicArtistIds)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicalbum: UPDATE [{UpdateKodiItemIdCurrent}] {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicalbum (DEBUG): UPDATE [{UpdateKodiItemIdCurrent}] {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": UpdateKodiItemIdCurrent, "KodiType": "album"}, IncrementalSync)
            del UpdateItem

        # New library (insert new Kodi record)
        if Item['LibraryId'] not in LibraryIds:
            EmbyMusicArtistIds = self.set_metadata(Item, IncrementalSync)
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicalbum (DEBUG): AlbumId {Item['Id']} not found", 1) # LOGDEBUG
            KodiItemIdCurrent = self.SQLs["music"].add_album(Item['Name'], AlbumType, Item['AlbumArtistsName'], Item['KodiProductionYear'], Item['KodiPremiereDate'], KodiMusicGenre, Item['Overview'], Item['KodiArtwork']['thumb'], Item['CommunityRating'], Item['KodiLastScraped'], Item['KodiDateCreated'], Item['ProviderIds']['MusicBrainzAlbum'], Item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, Item['Studio'], Item['KodiRunTimeTicks'], Item['AlbumArtistsSortName'], Item['LibraryId'])
            Item['LibraryIds'] = common.add_Ids_SingleContent(LibraryIds, Item['LibraryId'])
            Item['KodiItemId'] = common.add_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
            self.SQLs["emby"].add_reference_musicalbum(Item['Id'], Item['LibraryId'], KodiItemIds, LibraryIds, EmbyMusicArtistIds)
            common.set_MusicArtist_links(KodiItemIdCurrent, self.SQLs, Item["AlbumArtists"], Item['LibraryId'], None)
            self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdCurrent, "album")

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicalbum: ADD [{KodiItemIdCurrent}] {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicalbum (DEBUG): ADD [{KodiItemIdCurrent}] {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "album"}, IncrementalSync)

        return not Item['UpdateItem']

    def set_metadata(self, Item, IncrementalSync):
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "AlbumArtists", "music", IncrementalSync, Item['LibraryId'])
        EmbyMusicArtistIds = common.get_Artist_Ids(Item, False, True, False)
        common.get_MusicArtistInfos(Item, "AlbumArtists", self.SQLs)
        return EmbyMusicArtistIds

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        self.SQLs["emby"].update_favourite(Item['Id'], Item['IsFavorite'], "MusicAlbum")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "album"}, True)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.musicalbum: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.musicalbum (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        return True

    def remove(self, Item, IncrementalSync):
        Item['LibraryId'] = str(Item['LibraryId'])
        Item['LibraryIds'], Item['KodiItemId'], _, _ = self.SQLs["emby"].get_KodiIds_LibraryIds_from_ContentItem(Item['Id'], "MusicAlbum") # (Re)Load LibraryIds, KodiItemId as references could be modify data after collecting

        if not Item['LibraryIds']:
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicalbum (DEBUG): SKIP DELETE, LibraryIds not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
            return

        Links = self.SQLs['emby'].get_Links(Item['Id'], Item['LibraryId'])
        Deleted = self.SQLs["emby"].remove_item(Item['Id'], "MusicAlbum", Item['LibraryId'])
        common.delete_MusicArtist_Links(Item['LibraryId'], Links, self.MusicArtistObject, IncrementalSync, self.SQLs["emby"])
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])

        if Item['LibraryId'] not in LibraryIds:
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicalbum (DEBUG): SKIP DELETE, LibraryId not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
            return

        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])
        Index = LibraryIds.index(Item['LibraryId'])
        KodiItemIdCurrent = KodiItemIds[Index]
        self.set_favorite(False, Item)
        Item['KodiItemId'] = common.del_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
        Item['LibraryIds'] = common.del_Ids_SingleContent(LibraryIds, Item['LibraryId'])
        self.SQLs["music"].delete_album(KodiItemIdCurrent)

        if not Deleted:
            self.SQLs['emby'].update_references(Item['Id'], Item['KodiItemId'], "MusicAlbum", Item['LibraryIds'])

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicalbum: DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicalbum (DEBUG): DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG
        else:
            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicalbum: DELETE [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicalbum (DEBUG): DELETE [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

        utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "album"}, IncrementalSync)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])

        for KodiItemId in KodiItemIds:
            if IsFavorite and not Item['KodiArtwork']['favourite'] or "Name" not in Item:
                Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["music"].get_FavoriteSubcontent(KodiItemId, "album")

            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Album", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"musicdb://albums/{KodiItemId}/", Item['Name'].replace('"', "'"), "window", 10502),))

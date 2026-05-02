import xbmc
from helper import utils
from . import common

KodiDBs = ("music", "video")

class MusicGenre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.KodiDBMapping = ("music", "video") # Can be updated via library.py (worker_update)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicGenre"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.musicgenre (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        # Load Arrays
        KodiItemIds = common.get_Ids_MultiContentUnique(Item['KodiItemId'])
        LibraryIds = common.get_Ids_MultiContent(Item['LibraryIds'])

        # Load additional data
        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs.get(f"{Item['LibraryId']}MusicGenre", "video,music")
        NewItem = False
        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        # Update all existing Kodi musicgenres
        if Item['Name'] != "--NO INFO--": # update not injected items updates
            for Index in range(2):
                if KodiItemIds[Index] and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]: # Update
                    UpdateItem = Item.copy()
                    UpdateKodiItemIdCurrent = KodiItemIds[Index]
                    self.SQLs[KodiDBs[Index]].update_genre(UpdateItem['Name'], UpdateKodiItemIdCurrent)

                    for LibraryId in LibraryIds[Index]:
                        UpdateItem['LibraryId'] = LibraryId
                        self.SQLs["emby"].update_EmbyLibraryMapping(UpdateItem['Id'], UpdateItem['LibraryId'])
                        self.SQLs["emby"].update_reference_musicgenre(UpdateItem['Id'], UpdateItem['KodiArtwork']['favourite'], UpdateItem['LibraryId'])

                        if int(IncrementalSync):
                            xbmc.log(f"EMBY.core.musicgenre: UPDATE ({KodiDBs[Index]}) {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGINFO
                        elif utils.DebugLog:
                            xbmc.log(f"EMBY.core.musicgenre (DEBUG): UPDATE ({KodiDBs[Index]}) {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGDEBUG

                        utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": UpdateKodiItemIdCurrent, "KodiType": "genre"}, IncrementalSync)

                    del UpdateItem

        # New library (insert new Kodi record)
        for Index in range(2):
            if KodiDBs[Index] in self.KodiDBMapping and LibrarySyncedKodiDBs in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index] and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]:
                Item['LibraryIds'] = common.add_Ids_MultiContent(LibraryIds, Item['LibraryId'], Index)
                KodiItemIdCurrent = str(self.SQLs[KodiDBs[Index]].get_add_genre(Item['Name']))
                Item['KodiItemId'] = common.add_Ids_MultiContentUnique(KodiItemIds, Index, KodiItemIdCurrent)
                NewItem = True

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.musicgenre: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.musicgenre (DEBUG): ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

                utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "genre"}, IncrementalSync)

        if NewItem:
            self.SQLs["emby"].add_reference_musicgenre(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiArtwork']['favourite'], Item['LibraryIds'])

        common.download_SubnodeIcon(Item, self.EmbyServer.ServerData['ServerId']) # Download icon
        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Item['LibraryIds'], Item['KodiItemId'], _, _ = self.SQLs["emby"].get_KodiIds_LibraryIds_from_ContentItem(Item['Id'], "MusicGenre") # (Re)Load LibraryIds, KodiItemId as refreences could be modify data after collecting

        if not Item['LibraryIds']:
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicgenre (DEBUG): SKIP DELETE, LibraryIds not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
            return

        Deleted = self.SQLs["emby"].remove_item(Item['Id'], "MusicGenre", Item['LibraryId'])
        KodiItemIds = common.get_Ids_MultiContentUnique(Item['KodiItemId'])
        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs.get(f"{Item['LibraryId']}MusicGenre", "video,music")
        KodiDBsUpdate = LibrarySyncedKodiDBs.split(",")
        LibraryIds = common.get_Ids_MultiContent(Item['LibraryIds'])

        for KodiDBUpdate in KodiDBsUpdate:
            IndexDatabase = KodiDBs.index(KodiDBUpdate)

            if KodiDBs[IndexDatabase] not in self.SQLs or not self.SQLs[KodiDBs[IndexDatabase]]:
                continue

            if Item['LibraryId'] in LibraryIds[IndexDatabase]:
                Item['LibraryIds'], _ = common.del_Ids_MultiContent(LibraryIds, Item['LibraryId'], IndexDatabase)

                if not LibraryIds[IndexDatabase]:
                    KodiItemIdCurrent = KodiItemIds[IndexDatabase]
                    self.del_Genre(Item, KodiDBs[IndexDatabase], KodiItemIdCurrent, IncrementalSync)
                    Item['KodiItemId'] = common.del_Ids_MultiContentUnique(KodiItemIds, IndexDatabase)

                    if Deleted:
                        if int(IncrementalSync):
                            xbmc.log(f"EMBY.core.musicgenre: DELETE ({KodiDBs[IndexDatabase]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                        elif utils.DebugLog:
                            xbmc.log(f"EMBY.core.musicgenre (DEBUG): DELETE ({KodiDBs[IndexDatabase]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

                    else:
                        if int(IncrementalSync):
                            xbmc.log(f"EMBY.core.musicgenre: DELETE PARTIAL ({KodiDBs[IndexDatabase]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                        elif utils.DebugLog:
                            xbmc.log(f"EMBY.core.musicgenre (DEBUG): DELETE PARTIAL ({KodiDBs[IndexDatabase]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

        if not Deleted:
            self.SQLs['emby'].update_references(Item['Id'], Item['KodiItemId'], "MusicGenre", Item['LibraryIds'])

    def del_Genre(self, Item, KodiDB, KodiItemId, IncrementalSync):
        self.set_favorite(False, Item)
        GenreName = self.SQLs[KodiDB].delete_genre_by_Id(KodiItemId)
        self.EmbyServer.Views.remove_synced_subnode(Item['Id'], Item['LibraryId'], f"MusicGenre{KodiDB}", GenreName) # Delete genre xml node
        utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemId, "KodiType": "genre"}, IncrementalSync)

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicGenre")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.musicgenre: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.musicgenre (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite']:
            Item['KodiArtwork']['favourite'] = self.SQLs["emby"].get_item_by_id(Item['Id'], "MusicGenre")[4]

        KodiItemIds = common.get_Ids_MultiContentUnique(Item['KodiItemId'])

        if KodiItemIds[0] and "music" in self.SQLs and self.SQLs["music"]: # music
            Name, hasSongs = self.SQLs["music"].get_Genre_Name_hasSongs(KodiItemIds[0])

            if hasSongs or not IsFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"musicdb://genres/{KodiItemIds[0]}/", Name.replace('"', "'"), "window", 10502),))

            utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": KodiItemIds[0], "KodiType": "genre"}, True)

        if KodiItemIds[1] and "video" in self.SQLs and self.SQLs["video"]: # video
            Name, hasMusicVideos, _, _ = self.SQLs["video"].get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(KodiItemIds[1])

            if hasMusicVideos or not IsFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"videodb://musicvideos/genres/{KodiItemIds[1]}/", Name.replace('"', "'"), "window", 10025),))

            utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": KodiItemIds[1], "KodiType": "genre"}, True)

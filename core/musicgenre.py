import xbmc
from helper import utils
from . import common

KodiDBs = ("video", "music")

class MusicGenre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicGenre"):
            return False

        xbmc.log(f"EMBY.core.musicgenre: Process item: {Item['Name']}", 0) # DEBUG
        isFavorite = common.set_Favorite(Item)

        if Item['KodiItemIds']:
            KodiItemIds = Item['KodiItemIds'].split(";")
        else:
            KodiItemIds = ["", ""]

        if Item['LibraryIds']:
            LibraryIds = Item['LibraryIds'].split(";")

            if LibraryIds[0]:
                LibraryIds[0] = LibraryIds[0].split(",")
            else:
                LibraryIds[0] = []

            if LibraryIds[1]:
                LibraryIds[1] = LibraryIds[1].split(",")
            else:
                LibraryIds[1] = []
        else:
            LibraryIds = [[], []]

        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs[f"{Item['LibraryId']}MusicGenre"]
        NewItem = False
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        # Update all existing Kodi musicgenres
        if Item['Name'] != "--NO INFO--": # update not injected items updates
            for Index in range(2):
                if KodiItemIds[Index] and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]: # Update
                    self.SQLs[KodiDBs[Index]].update_genre(Item['Name'], KodiItemIds[Index])
                    self.set_favorite(isFavorite, KodiDBs[Index], KodiItemIds[Index], ImageUrl, Item['Id'])
                    xbmc.log(f"EMBY.core.musicgenre: UPDATE ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
                    utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index]}", "KodiType": "genre"}, IncrementalSync)

        # New library (insert new Kodi record)
        for Index in range(2):
            if LibrarySyncedKodiDBs in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index] and self.SQLs[KodiDBs[Index]]:
                LibraryIds[Index].append(str(Item['LibraryId']))
                KodiItemIds[Index] = str(self.SQLs[KodiDBs[Index]].get_add_genre(Item['Name']))
                self.set_favorite(isFavorite, KodiDBs[Index], KodiItemIds[Index], ImageUrl, Item['Id'])
                NewItem = True
                xbmc.log(f"EMBY.core.musicgenre: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG
                utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index]}", "KodiType": "genre"}, IncrementalSync)

        LibraryIds[1] = ",".join(LibraryIds[1])
        LibraryIds[0] = ",".join(LibraryIds[0])
        LibraryIds = ";".join(LibraryIds)
        KodiItemIds = ";".join(KodiItemIds)

        if NewItem:
            self.SQLs["emby"].add_reference_musicgenre(Item['Id'], Item['LibraryId'], KodiItemIds, isFavorite, ImageUrl, LibraryIds)
        else:
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["emby"].update_reference_musicgenre(Item['Id'], isFavorite, ImageUrl, Item['LibraryId'])

        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        KodiItemIds = Item['KodiItemId'].split(";")

        if not Item['LibraryId']:
            for Index in range(2):
                if KodiItemIds[Index]:
                    self.set_favorite(False, KodiDBs[Index], KodiItemIds[Index], "", Item['Id'])
                    self.SQLs[KodiDBs[Index]].delete_musicgenre_by_Id(KodiItemIds[Index])

            self.SQLs['emby'].remove_item(Item['Id'], "MusicGenre", None)
            xbmc.log(f"EMBY.core.musicgenre: DELETE ALL [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        else:
            LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs[f"{Item['LibraryId']}MusicGenre"]
            KodiDBsUpdate = LibrarySyncedKodiDBs.split(",")
            ExistingItem = self.SQLs["emby"].get_item_by_id(Item['Id'], "MusicGenre")
            LibraryIds = ExistingItem[3].split(";")

            if LibraryIds[0]:
                LibraryIds[0] = LibraryIds[0].split(",")
            else:
                LibraryIds[0] = []

            if LibraryIds[1]:
                LibraryIds[1] = LibraryIds[1].split(",")
            else:
                LibraryIds[1] = []

            for KodiDBUpdate in KodiDBsUpdate:
                Index = KodiDBs.index(KodiDBUpdate)
                Item['LibraryId'] = str(Item['LibraryId'])

                if Item['LibraryId'] in LibraryIds[Index]:
                    del LibraryIds[Index][LibraryIds[Index].index(Item['LibraryId'])]

                    if not LibraryIds[Index]:
                        self.set_favorite(False, KodiDBs[Index], KodiItemIds[Index], "", Item['Id'])
                        self.SQLs[KodiDBs[Index]].delete_musicgenre_by_Id(KodiItemIds[Index])
                        utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index]}", "KodiType": "genre"}, IncrementalSync)
                        KodiItemIds[Index] = ""

            LibraryIds[1] = ",".join(LibraryIds[1])
            LibraryIds[0] = ",".join(LibraryIds[0])
            LibraryIds = ";".join(LibraryIds)
            KodiItemIds = ";".join(KodiItemIds)

            if LibraryIds == ";":
                self.SQLs['emby'].remove_item(Item['Id'], "MusicGenre", None)
                xbmc.log(f"EMBY.core.musicgenre: DELETE ({LibrarySyncedKodiDBs}) [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            else:
                self.SQLs['emby'].remove_item_multi_db(Item['Id'], KodiItemIds, "MusicGenre", Item['LibraryId'], LibraryIds)
                xbmc.log(f"EMBY.core.musicgenre: DELETE PARTIAL ({LibrarySyncedKodiDBs}) [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG

    def userdata(self, Item):
        ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "MusicGenre")[4]
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[0]:
            self.set_favorite(Item['IsFavorite'], "video", KodiItemIds[0], ImageUrl, Item['Id'])
            utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[0]}", "KodiType": "genre"}, True)

        if KodiItemIds[1]:
            self.set_favorite(Item['IsFavorite'], "music", KodiItemIds[1], ImageUrl, Item['Id'])
            utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[1]}", "KodiType": "genre"}, True)

        xbmc.log(f"EMBY.core.genre: USERDATA genre [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicGenre")
        utils.reset_querycache("MusicGenre")
        return False

    def set_favorite(self, isFavorite, KodiDB, KodiItemId, ImageUrl, EmbyItemId):
        if KodiDB == "music":
            Name, hasSongs = self.SQLs["music"].get_Genre_Name_hasSongs(KodiItemId)

            if hasSongs or not isFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Songs", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"musicdb://genres/{KodiItemId}/", Name, "window", 10502),))
        else:
            Name, hasMusicVideos, _, _ = self.SQLs["video"].get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(KodiItemId)

            if hasMusicVideos or not isFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Musicvideos", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://musicvideos/genres/{KodiItemId}/", Name, "window", 10025),))

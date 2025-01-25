import xbmc
from helper import utils
from . import common, musicgenre

KodiDBs = ("video", "music")

# General info: Same musicartists from different Emby libraries are duplicated in Kodi's database for unification

class MusicArtist:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicArtist"):
            return False

        xbmc.log(f"EMBY.core.musicartist: Process item: {Item['Name']}", 0) # DEBUG
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', None, -1, IncrementalSync)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        isFavorite = common.set_Favorite(Item)
        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs[f"{Item['LibraryId']}MusicArtist"]
        NewItem = False

        if Item['KodiItemIds']:
            KodiItemIds = Item['KodiItemIds'].split(";")

            if KodiItemIds[0]:
                KodiItemIds[0] = KodiItemIds[0].split(",")
            else:
                KodiItemIds[0] = []

            if KodiItemIds[1]:
                KodiItemIds[1] = KodiItemIds[1].split(",")
            else:
                KodiItemIds[1] = []
        else:
            KodiItemIds = [[], []]

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

        # Update all existing Kodi musicartist
        if Item['Name'] != "--NO INFO--": # update not injected items updates
            for Index, KodiItemIdsByDatabase in enumerate(KodiItemIds):
                if KodiItemIdsByDatabase and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]:
                    for KodiItemIdByDatabase in KodiItemIdsByDatabase:
                        if Index == 0: # video
                            self.SQLs["video"].common_db.delete_artwork(KodiItemIdByDatabase, "actor")
                            self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdByDatabase, "actor")
                            self.SQLs[KodiDBs[Index]].update_person(KodiItemIdByDatabase, Item['Name'], Item['KodiArtwork']['thumb'])
                            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIdByDatabase}", "KodiType": "actor"}, IncrementalSync)
                        else: # music
                            self.SQLs["music"].common_db.delete_artwork(KodiItemIdByDatabase, "artist")
                            self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdByDatabase, "artist")
                            self.SQLs[KodiDBs[Index]].update_artist(KodiItemIdByDatabase, Item['Name'], Item['ProviderIds']['MusicBrainzArtist'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], Item['KodiLastScraped'], Item['SortName'], Item['KodiDateCreated'])
                            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIdByDatabase}", "KodiType": "artist"}, IncrementalSync)

                        self.set_favorite(KodiItemIdByDatabase, isFavorite, KodiDBs[Index], Item['Id'])
                        xbmc.log(f"EMBY.core.musicartist: UPDATE ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG

        # New library (insert new Kodi record)
        for Index in range(2): # Index 0 = video, 1 = music
            if LibrarySyncedKodiDBs in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index] and self.SQLs[KodiDBs[Index]]:
                LibraryIds[Index].append(str(Item['LibraryId']))

                if Index == 0: # video
                    KodiItemIds[Index].append(str(self.SQLs[KodiDBs[Index]].add_person(Item['Name'], Item['KodiArtwork']['thumb'])))
                    self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIds[Index][-1], "actor")
                    utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index][-1]}", "KodiType": "actor"}, IncrementalSync)
                else: # music
                    KodiItemIds[Index].append(str(self.SQLs[KodiDBs[Index]].add_artist(Item['Name'], Item['ProviderIds']['MusicBrainzArtist'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], Item['KodiLastScraped'], Item['SortName'], Item['KodiDateCreated'], Item['LibraryId'])))
                    self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIds[Index][-1], "artist")
                    utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index][-1]}", "KodiType": "artist"}, IncrementalSync)

                self.set_favorite(KodiItemIds[Index][-1], isFavorite, KodiDBs[Index], Item['Id'])
                NewItem = True
                xbmc.log(f"EMBY.core.musicartist: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", int(IncrementalSync)) # LOG

        KodiItemIds[1] = ",".join(KodiItemIds[1])
        KodiItemIds[0] = ",".join(KodiItemIds[0])
        LibraryIds[1] = ",".join(LibraryIds[1])
        LibraryIds[0] = ",".join(LibraryIds[0])
        LibraryIds = ";".join(LibraryIds)
        KodiItemIds = ";".join(KodiItemIds)

        if NewItem:
            self.SQLs["emby"].add_reference_musicartist(Item['Id'], Item['LibraryId'], KodiItemIds, isFavorite, LibraryIds)
        else:
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            self.SQLs["emby"].update_reference_generic(isFavorite, Item['Id'], "MusicArtist", Item['LibraryId'])

        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        KodiItemIds = Item['KodiItemId'].split(";")

        if not Item['LibraryId']:
            for Index in range(2):
                for KodiItemId in KodiItemIds[Index].split(","):
                    self.set_favorite(KodiItemId, False, KodiDBs[Index], Item['Id'])
                    self.SQLs[KodiDBs[Index]].del_musicartist(KodiItemId)

                    if Index:
                        utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "actor"}, IncrementalSync)
                    else:
                        utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "artist"}, IncrementalSync)

            self.SQLs['emby'].remove_item(Item['Id'], "MusicArtist", None)
            xbmc.log(f"EMBY.core.musicartist: DELETE (all) [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        else:
            LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs[f"{Item['LibraryId']}MusicArtist"]
            KodiDBsUpdate = LibrarySyncedKodiDBs.split(",")
            ExistingItem = self.SQLs["emby"].get_item_by_id(Item['Id'], "MusicArtist")
            LibraryIds = ExistingItem[3].split(";")

            if LibraryIds[0]:
                LibraryIds[0] = LibraryIds[0].split(",")
            else:
                LibraryIds[0] = []

            if LibraryIds[1]:
                LibraryIds[1] = LibraryIds[1].split(",")
            else:
                LibraryIds[1] = []

            KodiItemIds = ExistingItem[1].split(";")

            if KodiItemIds[0]:
                KodiItemIds[0] = KodiItemIds[0].split(",")
            else:
                KodiItemIds[0] = []

            if KodiItemIds[1]:
                KodiItemIds[1] = KodiItemIds[1].split(",")
            else:
                KodiItemIds[1] = []

            for KodiDBUpdate in KodiDBsUpdate:
                Index = KodiDBs.index(KodiDBUpdate)
                Item['LibraryId'] = str(Item['LibraryId'])

                if Item['LibraryId'] in LibraryIds[Index]:
                    SubIndex = LibraryIds[Index].index(Item['LibraryId'])
                    self.set_favorite(KodiItemIds[Index][SubIndex], False, KodiDBs[Index], Item['Id'])
                    self.SQLs[KodiDBs[Index]].del_musicartist(KodiItemIds[Index][SubIndex])
                    del LibraryIds[Index][SubIndex]
                    del KodiItemIds[Index][SubIndex]

            LibraryIds[1] = ",".join(LibraryIds[1])
            LibraryIds[0] = ",".join(LibraryIds[0])
            LibraryIds = ";".join(LibraryIds)
            KodiItemIds[1] = ",".join(KodiItemIds[1])
            KodiItemIds[0] = ",".join(KodiItemIds[0])
            KodiItemIds = ";".join(KodiItemIds)

            if LibraryIds == ";":
                self.SQLs['emby'].remove_item(Item['Id'], "MusicArtist", None)
                xbmc.log(f"EMBY.core.musicartist: DELETE ({LibrarySyncedKodiDBs}) [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            else:
                self.SQLs['emby'].remove_item_multi_db(Item['Id'], KodiItemIds, "MusicArtist", Item['LibraryId'], LibraryIds)
                xbmc.log(f"EMBY.core.musicartist: DELETE PARTIAL ({LibrarySyncedKodiDBs}) [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG

    def userdata(self, Item):
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[0]:
            for KodiItemId in KodiItemIds[0].split(","): # musicvideo artists
                self.set_favorite(KodiItemId, Item['IsFavorite'], "video", Item['Id'])
                utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "actor"}, True)

        if KodiItemIds[1]:
            for KodiItemId in KodiItemIds[1].split(","): # music artists
                self.set_favorite(KodiItemId, Item['IsFavorite'], "music", Item['Id'])
                utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "artist"}, True)

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicArtist")
        utils.reset_querycache("MusicArtist")
        return True

    def set_favorite(self, KodiItemId, isFavorite, KodiDB, EmbyItemId):
        if KodiDB == "music":
            Name, ImageUrl, hasMusicArtists = self.SQLs["music"].get_Artist(KodiItemId)

            if hasMusicArtists or not isFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Songs", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"musicdb://artists/{KodiItemId}/", Name, "window", 10502),))
        else:
            Name, ImageUrl, hasMusicVideos, _, _ = self.SQLs["video"].get_People(KodiItemId)

            if hasMusicVideos or not isFavorite:
                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Musicvideos", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), isFavorite, f"videodb://musicvideos/artists/{KodiItemId}/", Name, "window", 10025),))

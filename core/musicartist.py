import xbmc
from helper import utils
from . import common

KodiDBs = ("music", "video")

# General info: Same musicartists from different Emby libraries are duplicated in Kodi's database for unification
class MusicArtist:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.KodiDBMapping = ("music", "video") # Can be updated via library.py (worker_update)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicArtist"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.musicartist (DEBUG): Process item: {Item['Name']}", 1) # DEBUG
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs.get(f"{Item['LibraryId']}MusicArtist", "video,music")
        NewItem = False

        if 'Genres' in Item:
            KodiMusicGenre = " / ".join(Item['Genres'])
        else:
            KodiMusicGenre = ""

        # Load Arrays
        KodiItemIds = common.get_Ids_MultiContent(Item['KodiItemId'])
        LibraryIds = common.get_Ids_MultiContent(Item['LibraryIds'])

        # Update all existing Kodi musicartist
        if Item['Name'] != "--NO INFO--": # update not injected items updates
            for Index, KodiItemIdsByDatabase in enumerate(KodiItemIds):
                if KodiItemIdsByDatabase and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]:
                    for SubIndex, KodiItemIdByDatabase in enumerate(KodiItemIdsByDatabase):
                        UpdateItem = Item.copy()
                        UpdateKodiItemIdCurrent = KodiItemIdByDatabase
                        UpdateItem['LibraryId'] = LibraryIds[Index][SubIndex]

                        if Index == 0: # music
                            self.SQLs["music"].common_db.delete_artwork(UpdateKodiItemIdCurrent, "artist")
                            self.SQLs["music"].common_db.add_artwork(UpdateItem['KodiArtwork'], UpdateKodiItemIdCurrent, "artist")
                            self.SQLs[KodiDBs[Index]].update_artist(UpdateKodiItemIdCurrent, UpdateItem['Name'], UpdateItem['ProviderIds']['MusicBrainzArtist'], KodiMusicGenre, UpdateItem['Overview'], UpdateItem['KodiArtwork']['thumb'], UpdateItem['KodiLastScraped'], UpdateItem['SortName'], UpdateItem['KodiDateCreated'])
                            utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": UpdateKodiItemIdCurrent, "KodiType": "artist"}, IncrementalSync)
                        else: # video
                            self.SQLs["video"].common_db.delete_artwork(UpdateKodiItemIdCurrent, "actor")
                            self.SQLs["video"].common_db.add_artwork(UpdateItem['KodiArtwork'], UpdateKodiItemIdCurrent, "actor")
                            self.SQLs[KodiDBs[Index]].update_person(UpdateKodiItemIdCurrent, UpdateItem['Name'], UpdateItem['KodiArtwork']['thumb'])
                            utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": UpdateKodiItemIdCurrent, "KodiType": "actor"}, IncrementalSync)

                        self.SQLs["emby"].update_reference_musicartist(UpdateItem['Id'], UpdateItem['LibraryId'])

                        if int(IncrementalSync):
                            xbmc.log(f"EMBY.core.musicartist: UPDATE ({KodiDBs[Index]}) {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGINFO
                        elif utils.DebugLog:
                            xbmc.log(f"EMBY.core.musicartist (DEBUG): UPDATE ({KodiDBs[Index]}) {UpdateItem['Name']}: {UpdateItem['Id']} / {UpdateItem['LibraryId']}", 1) # LOGDEBUG

                        del UpdateItem

        # New library (insert new Kodi record)
        for Index in range(2): # Index 0 = music, 1 = video
            if KodiDBs[Index] in self.KodiDBMapping and LibrarySyncedKodiDBs in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index] and KodiDBs[Index] in self.SQLs and self.SQLs[KodiDBs[Index]]:
                Item['LibraryIds'] = common.add_Ids_MultiContent(LibraryIds, Item['LibraryId'], Index)

                if Index == 0: # music
                    KodiItemIdCurrent = self.SQLs[KodiDBs[Index]].add_artist(Item['Name'], Item['ProviderIds']['MusicBrainzArtist'], KodiMusicGenre, Item['Overview'], Item['KodiArtwork']['thumb'], Item['KodiLastScraped'], Item['SortName'], Item['KodiDateCreated'], Item['LibraryId'])
                    Item['KodiItemId'] = common.add_Ids_MultiContent(KodiItemIds, KodiItemIdCurrent, Index)
                    self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdCurrent, "artist")
                    utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "artist"}, IncrementalSync)
                else: # video
                    KodiItemIdCurrent = self.SQLs[KodiDBs[Index]].add_person(Item['Name'], Item['KodiArtwork']['thumb'])
                    Item['KodiItemId'] = common.add_Ids_MultiContent(KodiItemIds, KodiItemIdCurrent, Index)
                    self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdCurrent, "actor")
                    utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "actor"}, IncrementalSync)

                NewItem = True

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.musicartist: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.musicartist (DEBUG): ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

        if NewItem:
            self.SQLs["emby"].add_reference_musicartist(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['LibraryIds'])

        return not Item['UpdateItem']

    def remove(self, Item, IncrementalSync):
        Item['LibraryIds'], Item['KodiItemId'], _, _ = self.SQLs["emby"].get_KodiIds_LibraryIds_from_ContentItem(Item['Id'], "MusicArtist")

        if not Item['LibraryIds']:
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicartist (DEBUG): SKIP DELETE, LibraryIds not found {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG
            return

        LibrarySyncedKodiDBs = self.EmbyServer.library.LibrarySyncedKodiDBs.get(f"{Item['LibraryId']}MusicArtist", "video,music")
        KodiDBsUpdate = LibrarySyncedKodiDBs.split(",")
        KodiItemIds = common.get_Ids_MultiContent(Item['KodiItemId'])
        LibraryIds = common.get_Ids_MultiContent(Item['LibraryIds'])

        for KodiDBUpdate in KodiDBsUpdate:
            Index = KodiDBs.index(KodiDBUpdate)

            if KodiDBs[Index] not in self.SQLs or not self.SQLs[KodiDBs[Index]]:
                continue

            if Item['LibraryId'] in LibraryIds[Index]:
                Item['LibraryIds'], IndexLibrary = common.del_Ids_MultiContent(LibraryIds, Item['LibraryId'], Index)
                KodiItemIdCurrent = KodiItemIds[Index][IndexLibrary]
                isVideo = KodiDBs[Index] == "video"
                isAudio = KodiDBs[Index] == "music"
                self.set_favorite(False, Item, isVideo, isAudio)
                Item['KodiItemId'], _ = common.del_Ids_MultiContent(KodiItemIds, KodiItemIdCurrent, Index)
                self.SQLs[KodiDBs[Index]].del_musicartist(KodiItemIdCurrent)

                if isVideo:
                    utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "actor"}, IncrementalSync)
                else:
                    utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "artist"}, IncrementalSync)

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.musicartist: DELETE ({KodiDBs[Index]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.musicartist (DEBUG): DELETE ({KodiDBs[Index]}) [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG


        # Check if removed LibraryId is still present in one of the Kodi DBs. Happens on Mixed content libraries
        Deleted = False

        if Item['LibraryId'] not in Item['LibraryIds']:
            Deleted = self.SQLs["emby"].remove_item(Item['Id'], "MusicArtist", Item['LibraryId'])

        if not Deleted:
            self.SQLs['emby'].update_references(Item['Id'], Item['KodiItemId'], "MusicArtist", Item['LibraryIds'])

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return False

        common.set_Favorite(Item)
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicArtist")

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.musicartist: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.musicartist (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        return True

    def set_favorite(self, IsFavorite, Item, Video=True, Music=True): # Kodi Favorites
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[1] and Video and "video" in self.SQLs and self.SQLs["video"]: # video
            for KodiItemId in KodiItemIds[1].split(","): # musicvideo artists
                Name, FavoriteImage, hasMusicVideos, _, _ = self.SQLs["video"].get_People(KodiItemId)

                if hasMusicVideos or not IsFavorite:
                    utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], FavoriteImage), IsFavorite, f"videodb://musicvideos/artists/{KodiItemId}/", Name.replace('"', "'"), "window", 10025),))

        if KodiItemIds[0] and Music and "music" in self.SQLs and self.SQLs["music"]: # music
            for KodiItemId in KodiItemIds[0].split(","): # music artists
                Name, FavoriteImage, hasMusicArtists = self.SQLs["music"].get_Artist(KodiItemId)

                if hasMusicArtists or not IsFavorite:
                    utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], FavoriteImage), IsFavorite, f"musicdb://artists/{KodiItemId}/", Name.replace('"', "'"), "window", 10502),))

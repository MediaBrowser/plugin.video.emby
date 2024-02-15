import xbmc
from helper import pluginmenu, utils
from . import common, musicgenre

KodiDBs = ("video", "music")

# General info: Same musicartists from different Emby libraries are duplicated in Kodi's database for unification

class MusicArtist:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)

    def change(self, Item):
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicArtist")
        xbmc.log(f"EMBY.core.musicartist: Process item: {Item['Name']}", 0) # DEBUG
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems')
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        common.set_KodiArtwork(Item, self.EmbyServer.ServerData['ServerId'], False)
        isFavorite = common.set_Favorite(Item)
        _, KodiDB = self.EmbyServer.library.WhitelistUnique[str(Item['LibraryId'])]
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
        if int(Item['Id']) < 999999900: # Skip injected items updates
            for Index, KodiItemIdsByDatabase in enumerate(KodiItemIds):
                if KodiItemIdsByDatabase and KodiDBs[Index] in self.SQLs:
                    for KodiItemIdByDatabase in KodiItemIdsByDatabase:
                        if Index == 0: # video
                            self.SQLs["video"].common_db.delete_artwork(KodiItemIdByDatabase, "actor")
                            self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdByDatabase, "actor")
                            self.SQLs[KodiDBs[Index]].update_person(KodiItemIdByDatabase, Item['Name'], Item['KodiArtwork']['thumb'])
                        else: # music
                            self.SQLs["music"].common_db.delete_artwork(KodiItemIdByDatabase, "artist")
                            self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIdByDatabase, "artist")
                            self.SQLs[KodiDBs[Index]].update_artist(KodiItemIdByDatabase, Item['Name'], Item['ProviderIds']['MusicBrainzArtist'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], Item['KodiLastScraped'], Item['SortName'], Item['KodiDateCreated'])

                        self.set_favorite(KodiItemIdByDatabase, isFavorite, KodiDBs[Index], Item['Name'], Item['KodiArtwork']['poster'])
                        xbmc.log(f"EMBY.core.musicartist: UPDATE ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        # New library (insert new Kodi record)
        for Index in range(2):
            if KodiDB in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index]:
                LibraryIds[Index].append(str(Item['LibraryId']))

                if Index == 0: # video
                    KodiItemIds[Index].append(str(self.SQLs[KodiDBs[Index]].add_person(Item['Name'], Item['KodiArtwork']['thumb'])))
                    self.SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIds[Index][-1], "actor")
                else: # music
                    KodiItemIds[Index].append(str(self.SQLs[KodiDBs[Index]].add_artist(Item['Name'], Item['ProviderIds']['MusicBrainzArtist'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], Item['KodiLastScraped'], Item['SortName'], Item['KodiDateCreated'], Item['LibraryId'])))
                    self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIds[Index][-1], "artist")

                self.set_favorite(KodiItemIds[Index][-1], isFavorite, KodiDBs[Index], Item['Name'], Item['KodiArtwork']['poster'])
                NewItem = True
                xbmc.log(f"EMBY.core.musicartist: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        KodiItemIds[1] = ",".join(KodiItemIds[1])
        KodiItemIds[0] = ",".join(KodiItemIds[0])
        LibraryIds[1] = ",".join(LibraryIds[1])
        LibraryIds[0] = ",".join(LibraryIds[0])
        LibraryIds = ";".join(LibraryIds)
        KodiItemIds = ";".join(KodiItemIds)

        if NewItem:
            self.SQLs["emby"].add_reference_musicartist(Item['Id'], Item['LibraryId'], KodiItemIds, isFavorite, LibraryIds)
        else:
            if int(Item['Id']) > 999999900: # Skip injected items
                return False

            self.SQLs["emby"].update_reference_generic(isFavorite, Item['Id'], "MusicArtist", Item['LibraryId'])

        return not Item['UpdateItem']

    def remove(self, Item):
        KodiItemIds = Item['KodiItemId'].split(";")

        if not Item['LibraryId']:
            for Index in range(2):
                for KodiItemId in KodiItemIds[Index].split(","):
                    self.set_favorite(KodiItemId, False, KodiDBs[Index])
                    self.SQLs[KodiDBs[Index]].del_musicartist(KodiItemId)

            self.SQLs['emby'].remove_item(Item['Id'], "MusicArtist", None)
            xbmc.log(f"EMBY.core.musicartist: DELETE (all) [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        else:
            _, KodiDBsRefresh = self.EmbyServer.library.WhitelistUnique[str(Item['LibraryId'])]
            KodiDBsUpdate = KodiDBsRefresh.split(",")
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
                SubIndex = LibraryIds[Index].index(str(Item['LibraryId']))
                self.set_favorite(KodiItemIds[Index][SubIndex], False, KodiDBs[Index])
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
                xbmc.log(f"EMBY.core.musicartist: DELETE ({KodiDBsRefresh}) [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            else:
                self.SQLs['emby'].remove_item_multi_db(Item['Id'], KodiItemIds, "MusicArtist", Item['LibraryId'], LibraryIds)
                xbmc.log(f"EMBY.core.musicartist: DELETE PARTIAL ({KodiDBsRefresh}) [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[0]:
            for KodiItemId in KodiItemIds[0].split(","): # musicvideo artists
                self.set_favorite(KodiItemId, Item['IsFavorite'], "video")

        if KodiItemIds[1]:
            for KodiItemId in KodiItemIds[1].split(","): # music artists
                self.set_favorite(KodiItemId, Item['IsFavorite'], "music") # musicvideo artists

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicArtist")
        pluginmenu.reset_querycache("MusicArtist")

    def set_favorite(self, KodiItemId, isFavorite, KodiDB, Name="", ImageUrl=""):
        if KodiDB == "music":
            if not Name:
                Name, ImageUrl, _ = self.SQLs["music"].get_Artist(KodiItemId)

            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"musicdb://artists/{KodiItemId}/", f"{Name} (Songs)", "window", 10502),))
        else:
            if not Name:
                Name, ImageUrl, _, _, _ = self.SQLs["video"].get_People(KodiItemId)

            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://musicvideos/artists/{KodiItemId}/", f"{Name} (Musicvideos)", "window", 10025),))

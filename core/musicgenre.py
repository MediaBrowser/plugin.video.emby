import xbmc
from helper import pluginmenu, utils
from . import common

KodiDBs = ("video", "music")

class MusicGenre:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item):
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicGenre")
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

        _, KodiDB = self.EmbyServer.library.WhitelistUnique[str(Item['LibraryId'])]
        NewItem = False
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])

        # Update all existing Kodi musicgenres
        if int(Item['Id']) < 999999900: # Skip injected items updates
            for Index in range(2):
                if KodiItemIds[Index] and KodiDBs[Index] in self.SQLs: # Update
                    self.SQLs[KodiDBs[Index]].update_genre(Item['Name'], KodiItemIds[Index])
                    self.set_favorite(isFavorite, KodiDBs[Index], KodiItemIds[Index], Item['Name'], ImageUrl)
                    xbmc.log(f"EMBY.core.musicgenre: UPDATE ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        # New library (insert new Kodi record)
        for Index in range(2):
            if KodiDB in (KodiDBs[Index], "video,music") and Item['LibraryId'] not in LibraryIds[Index]:
                LibraryIds[Index].append(str(Item['LibraryId']))
                KodiItemIds[Index] = str(self.SQLs[KodiDBs[Index]].get_add_genre(Item['Name']))
                self.set_favorite(isFavorite, KodiDBs[Index], KodiItemIds[Index], Item['Name'], ImageUrl)
                NewItem = True
                xbmc.log(f"EMBY.core.musicgenre: ADD ({KodiDBs[Index]}) {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        LibraryIds[1] = ",".join(LibraryIds[1])
        LibraryIds[0] = ",".join(LibraryIds[0])
        LibraryIds = ";".join(LibraryIds)
        KodiItemIds = ";".join(KodiItemIds)

        if NewItem:
            self.SQLs["emby"].add_reference_musicgenre(Item['Id'], Item['LibraryId'], KodiItemIds, isFavorite, ImageUrl, LibraryIds)
        else:
            if int(Item['Id']) > 999999900: # Skip injected items
                self.SQLs["emby"].update_EmbyLibraryMapping(Item['Id'], Item['LibraryId'])
                return False

            self.SQLs["emby"].update_reference_musicgenre(Item['Id'], isFavorite, ImageUrl, Item['LibraryId'])

        return not Item['UpdateItem']

    def remove(self, Item):
        KodiItemIds = Item['KodiItemId'].split(";")

        if not Item['LibraryId']:
            for Index in range(2):
                if KodiItemIds[Index]:
                    self.set_favorite(False, KodiDBs[Index], KodiItemIds[Index])
                    self.SQLs[KodiDBs[Index]].delete_musicgenre_by_Id(KodiItemIds[Index])

            self.SQLs['emby'].remove_item(Item['Id'], "MusicGenre", None)
            xbmc.log(f"EMBY.core.musicgenre: DELETE ALL [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        else:
            _, KodiDBsRefresh = self.EmbyServer.library.WhitelistUnique[str(Item['LibraryId'])]
            KodiDBsUpdate = KodiDBsRefresh.split(",")
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
                del LibraryIds[Index][LibraryIds[Index].index(str(Item['LibraryId']))]

                if not LibraryIds[Index]:
                    self.set_favorite(False, KodiDBs[Index], KodiItemIds[Index])
                    self.SQLs[KodiDBs[Index]].delete_musicgenre_by_Id(KodiItemIds[Index])
                else:
                    KodiItemIds[Index] = ""

            LibraryIds[1] = ",".join(LibraryIds[1])
            LibraryIds[0] = ",".join(LibraryIds[0])
            LibraryIds = ";".join(LibraryIds)
            KodiItemIds = ";".join(KodiItemIds)

            if LibraryIds == ";":
                self.SQLs['emby'].remove_item(Item['Id'], "MusicGenre", None)
                xbmc.log(f"EMBY.core.musicgenre: DELETE ({KodiDBsRefresh}) [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            else:
                self.SQLs['emby'].remove_item_multi_db(Item['Id'], KodiItemIds, "MusicGenre", Item['LibraryId'], LibraryIds)
                xbmc.log(f"EMBY.core.musicgenre: DELETE PARTIAL ({KodiDBsRefresh}) [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "MusicGenre")[4]
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[0]:
            self.set_favorite(Item['IsFavorite'], "video", KodiItemIds[0], "", ImageUrl)

        if KodiItemIds[1]:
            self.set_favorite(Item['IsFavorite'], "music", KodiItemIds[1], "", ImageUrl)

        xbmc.log(f"EMBY.core.genre: USERDATA genre [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicGenre")
        pluginmenu.reset_querycache("MusicGenre")

    def set_favorite(self, isFavorite, KodiDB, KodiItemId, Name="", ImageUrl=""):
        if KodiDB == "music":
            if not Name:
                Name, _ = self.SQLs["music"].get_Genre_Name(KodiItemId)

            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"musicdb://genres/{KodiItemId}/", f"{Name} (Songs)", "window", 10502),))
        else:
            if not Name:
                Name, _, _, _ = self.SQLs["video"].get_Genre_Name(KodiItemId)

            utils.FavoriteQueue.put(((ImageUrl, isFavorite, f"videodb://musicvideos/genres/{KodiItemId}/", f"{Name} (Musicvideos)", "window", 10025),))

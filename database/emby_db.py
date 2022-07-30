import xbmc

from helper import loghandler, utils
from core import common

LOG = loghandler.LOG('EMBY.database.emby_db')

class EmbyDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def init_EmbyDB(self):
        # Table
        try:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Mapping (EmbyId INTEGER PRIMARY KEY, EmbyLibraryId TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiType TEXT COLLATE NOCASE, KodiId TEXT COLLATE NOCASE, KodiFileId TEXT COLLATE NOCASE, KodiPathId INTEGER, KodiParentId TEXT COLLATE NOCASE, EmbyParentId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFavourite BOOL, EmbyFolder TEXT COLLATE NOCASE, IntroStart INTEGER, IntroEnd INTEGER, CreditStart INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources (EmbyId INTEGER, MediaIndex INTEGER, MediaSourceId TEXT COLLATE NOCASE, Path TEXT COLLATE NOCASE, Name TEXT COLLATE NOCASE, Size INTEGER)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, BitRate INTEGER)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, DisplayTitle TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Subtitles (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, Language TEXT COLLATE NOCASE, DisplayTitle TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS RemoveItems (EmbyId INTEGER, EmbyLibraryId TEXT COLLATE NOCASE, UNIQUE(EmbyId, EmbyLibraryId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UpdateItems (EmbyId INTEGER PRIMARY KEY) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UserdataItems (Data TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Whitelist (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryType TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, UNIQUE(EmbyLibraryId, EmbyLibraryType))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LastIncrementalSync (Date TEXT)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS PendingSync (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyLibraryType TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiCategory TEXT COLLATE NOCASE)")

            # Index
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MediaSources_EmbyId on MediaSources (EmbyId)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MediaSources_Path on MediaSources (Path)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_VideoStreams_EmbyId_MediaIndex on VideoStreams (EmbyId, MediaIndex)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_AudioStreams_EmbyId_MediaIndex on AudioStreams (EmbyId, MediaIndex)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Subtitles_EmbyId_MediaIndex on Subtitles (EmbyId, MediaIndex)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_EmbyParentId on Mapping (EmbyParentId)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_EmbyType_EmbyParentId_EmbyLibraryId on Mapping (EmbyType, EmbyParentId, EmbyLibraryId)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_EmbyPresentationKey_EmbyType_EmbyLibraryId on Mapping (EmbyPresentationKey, EmbyType, EmbyLibraryId)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_KodiType_KodiParentId on Mapping (KodiType, KodiParentId)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_EmbyFolder on Mapping (EmbyFolder)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_EmbyType_EmbyFavourite on Mapping (EmbyType, EmbyFavourite)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Mapping_KodiType_KodiId on Mapping (KodiType, KodiId)")
        except Exception as Error: # Database invalid! Database reset mandatory
            LOG.error("Database invalid, performing reset: %s" % Error)
            utils.set_settings('MinimumSetup', "INVALID DATABASE")
            xbmc.executebuiltin('RestartApp')
            return False

        return True

    # Whitelist
    def get_Whitelist(self):
        self.cursor.execute("SELECT * FROM Whitelist")

        Libs = self.cursor.fetchall()

        if Libs:
            SyncedLibs = {}

            for Lib in Libs:
                SyncedLibs[Lib[0]] = (Lib[1], Lib[2])

            return SyncedLibs, Libs

        return {}, []

    def add_Whitelist(self, EmbyLibraryId, EmbyLibraryType, EmbyLibraryName):
        self.cursor.execute("INSERT OR REPLACE INTO Whitelist (EmbyLibraryId, EmbyLibraryType, EmbyLibraryName) VALUES (?, ?, ?)", (EmbyLibraryId, EmbyLibraryType, EmbyLibraryName))

    def remove_Whitelist(self, EmbyLibraryId):
        self.cursor.execute("DELETE FROM Whitelist WHERE EmbyLibraryId = ?", (EmbyLibraryId,))

    # LastIncrementalSync
    def get_LastIncrementalSync(self):
        self.cursor.execute("SELECT * FROM LastIncrementalSync")
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def update_LastIncrementalSync(self, LastIncrementalSync):
        self.cursor.execute("DELETE FROM LastIncrementalSync")
        self.cursor.execute("INSERT INTO LastIncrementalSync (Date) VALUES (?)", (LastIncrementalSync,))

    # UserdataItems
    def add_Userdata(self, Data):
        self.cursor.execute("INSERT INTO UserdataItems (Data) VALUES (?)", (Data,))

    def get_Userdata(self):
        self.cursor.execute("SELECT * FROM UserdataItems")
        return self.cursor.fetchall()

    def delete_Userdata(self, Data):
        self.cursor.execute("DELETE FROM UserdataItems WHERE Data = ?", (Data,))

    # PendingSync
    def add_PendingSync(self, EmbyLibraryId, EmbyLibraryName, EmbyLibraryType, EmbyType, KodiCategory):
        self.cursor.execute("INSERT INTO PendingSync (EmbyLibraryId, EmbyLibraryName, EmbyLibraryType, EmbyType, KodiCategory) VALUES (?, ?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyLibraryType, EmbyType, KodiCategory))

    def get_PendingSync(self):
        self.cursor.execute("SELECT * FROM PendingSync")
        return self.cursor.fetchall()

    def remove_PendingSync(self, EmbyLibraryId, EmbyLibraryName, EmbyLibraryType, EmbyType, KodiCategory):
        self.cursor.execute("DELETE FROM PendingSync WHERE EmbyLibraryId = ? AND EmbyLibraryName = ? AND EmbyLibraryType = ? AND EmbyType = ? AND KodiCategory = ?", (EmbyLibraryId, EmbyLibraryName, EmbyLibraryType, EmbyType, KodiCategory))

    # UpdateItems
    def add_UpdateItem(self, EmbyId):
        self.cursor.execute("INSERT OR REPLACE INTO UpdateItems (EmbyId) VALUES (?)", (EmbyId,))

    def get_UpdateItem(self):
        self.cursor.execute("SELECT * FROM UpdateItems")
        Items = self.cursor.fetchall()
        Ids = len(Items) * [""]

        for Index, Item in enumerate(Items):
            Ids[Index] = str(Item[0])

        return Ids

    def delete_UpdateItem(self, EmbyId):
        self.cursor.execute("DELETE FROM UpdateItems WHERE EmbyId = ?", (EmbyId,))

    # RemoveItems
    def add_RemoveItem(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("INSERT OR REPLACE INTO RemoveItems (EmbyId, EmbyLibraryId) VALUES (?, ?)", (EmbyId, EmbyLibraryId))

    def get_RemoveItem(self):
        self.cursor.execute("SELECT * FROM RemoveItems")
        return self.cursor.fetchall()

    def delete_RemoveItem(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("DELETE FROM RemoveItems WHERE EmbyId = ? AND EmbyLibraryId = ?", (EmbyId, EmbyLibraryId))

    def delete_RemoveItem_EmbyId(self, EmbyId):
        self.cursor.execute("DELETE FROM RemoveItems WHERE EmbyId = ? ", (EmbyId,))

    # Subtitle
    def get_Subtitles(self, EmbyId, MediaIndex):
        self.cursor.execute("SELECT * FROM Subtitles WHERE EmbyId = ? AND MediaIndex = ?", (EmbyId, MediaIndex))
        return self.cursor.fetchall()

    # MediaSources
    def get_mediasource(self, EmbyId):
        self.cursor.execute("SELECT * FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    def get_mediasource_EmbyID_by_path(self, Path):
        self.cursor.execute("SELECT EmbyId FROM MediaSources WHERE Path LIKE ?", ("%%%s" % Path,))
        return self.cursor.fetchone()

    # VideoStreams
    def get_videostreams(self, EmbyId, MediaIndex):
        self.cursor.execute("SELECT * FROM VideoStreams WHERE EmbyId = ? AND MediaIndex = ?", (EmbyId, MediaIndex))
        return self.cursor.fetchall()

    # AudioStreams
    def get_AudioStreams(self, EmbyId, MediaIndex):
        self.cursor.execute("SELECT * FROM AudioStreams WHERE EmbyId = ? AND MediaIndex = ?", (EmbyId, MediaIndex))
        return self.cursor.fetchall()

    # Mapping
    def get_item_by_id(self, EmbyId):
        self.cursor.execute("SELECT KodiId, KodiFileId, KodiPathId, KodiParentId, KodiType, EmbyType, EmbyLibraryId, EmbyPresentationKey FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchone()

    def add_reference(self, EmbyId, KodiItemIds, KodiFileIds, KodiPathId, EmbyType, KodiType, KodiParentIds, EmbyLibraryIds, EmbyParentId, EmbyPresentationKey, EmbyFavourite, EmbyFolder, IntroStart, IntroEnd, CreditStart):
        KodiId = join_Ids(KodiItemIds)
        KodiParentId = join_Ids(KodiParentIds)
        KodiFileId = join_Ids(KodiFileIds)
        EmbyLibraryId = join_Ids(EmbyLibraryIds)
        self.cursor.execute("INSERT OR REPLACE INTO Mapping (EmbyId, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite, EmbyFolder, IntroStart, IntroEnd, CreditStart) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite, EmbyFolder, IntroStart, IntroEnd, CreditStart))

    def update_favourite(self, EmbyFavourite, EmbyId):
        self.cursor.execute("UPDATE Mapping SET EmbyFavourite = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyId))

    def update_favourite_markers(self, IntroStart, IntroEnd, CreditStart, EmbyFavourite, EmbyId):
        self.cursor.execute("UPDATE Mapping SET IntroStart = ?, IntroEnd = ?, CreditStart = ?, EmbyFavourite = ? WHERE EmbyId = ?", (IntroStart, IntroEnd, CreditStart, EmbyFavourite, EmbyId))

    def get_episode_fav(self):
        self.cursor.execute("SELECT KodiId FROM Mapping WHERE EmbyType = ? AND EmbyFavourite = ?", ("Episode", "1"))
        return self.cursor.fetchall()

    def update_parent_id(self, KodiParentId, EmbyId):
        self.cursor.execute("UPDATE Mapping SET KodiParentId = ? WHERE EmbyId = ?", (KodiParentId, EmbyId))

    def get_item_by_parent_id(self, KodiParentId, KodiType):
        self.cursor.execute("SELECT EmbyId, KodiId FROM Mapping WHERE KodiType = ? AND KodiParentId = ?", (KodiType, KodiParentId))
        Items = self.cursor.fetchall()

        # Try query by MultiKodiIDs
        if not Items: # First item
            self.cursor.execute("SELECT EmbyId, KodiId FROM Mapping WHERE KodiType = ? AND KodiParentId LIKE ?", (KodiType, "%s;%%" % KodiParentId))
            Items = self.cursor.fetchall()

            if not Items: # Last item
                self.cursor.execute("SELECT EmbyId, KodiId FROM Mapping WHERE KodiType = ? AND KodiParentId LIKE ?", (KodiType, "%%;%s" % KodiParentId))
                Items = self.cursor.fetchall()

                if not Items: # Middle item
                    self.cursor.execute("SELECT EmbyId, KodiId FROM Mapping WHERE KodiType = ? AND KodiParentId LIKE ?", (KodiType, "%%;%s;%%" % KodiParentId))
                    Items = self.cursor.fetchall()

        return Items

    def get_media_by_parent_id(self, EmbyParentId):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyParentId = ?", (EmbyParentId,))
        return self.cursor.fetchall()

    def get_items_by_embyparentid(self, EmbyParentId, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyType = ? AND EmbyParentId = ? AND EmbyLibraryId = ?", (EmbyType, EmbyParentId, EmbyLibraryId))
        return self.cursor.fetchall()

    def get_special_features(self, EmbyParentId):
        self.cursor.execute("SELECT EmbyId FROM Mapping WHERE EmbyType = 'SpecialFeature' AND EmbyParentId = ?", (EmbyParentId,))
        return self.cursor.fetchall()

    def get_KodiId_KodiType_by_EmbyId(self, item_id):
        self.cursor.execute("SELECT KodiId, KodiType FROM Mapping WHERE EmbyId = ?", (item_id,))
        return self.cursor.fetchall()

    def get_item_by_KodiId_KodiType(self, KodiId, KodiType):
        self.cursor.execute("SELECT * FROM Mapping WHERE KodiType = ? AND KodiId = ?", (KodiType, KodiId))
        Items = self.cursor.fetchall()

        # Try query by MultiKodiIDs
        if not Items: # First item
            self.cursor.execute("SELECT * FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%s;%%" % KodiId))
            Items = self.cursor.fetchall()

            if not Items: # Last item
                self.cursor.execute("SELECT * FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%%;%s" % KodiId))
                Items = self.cursor.fetchall()

                if not Items: # Middle item
                    self.cursor.execute("SELECT * FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%%;%s;%%" % KodiId))
                    Items = self.cursor.fetchall()

        return Items

    def get_media_by_id(self, EmbyId):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    def get_media_by_folder(self, Folder):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyFolder LIKE ?", ("%s%%" % Folder,))
        return self.cursor.fetchall()

    def get_kodiid(self, EmbyId):
        self.cursor.execute("SELECT KodiId, EmbyPresentationKey, KodiFileId FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchone()

    def remove_item(self, EmbyId, EmbyLibraryId):
        ExistingItem = self.get_media_by_id(EmbyId)

        if ExistingItem:
            KodiId = None
            KodiFileId = None
            KodiParentId = None
            EmbyLibraryIds = ExistingItem[0][1].split(";")

            if EmbyLibraryId not in EmbyLibraryIds:
                return

            EmbyLibraryIdIndex = EmbyLibraryIds.index(EmbyLibraryId)
            del EmbyLibraryIds[EmbyLibraryIdIndex]
            EmbyLibraryId = ";".join(EmbyLibraryIds)

            if ExistingItem[0][4]:
                KodiIds = ExistingItem[0][4].split(";")
                del KodiIds[EmbyLibraryIdIndex]
                KodiId = ";".join(KodiIds)

            if ExistingItem[0][5]:
                KodiFileIds = ExistingItem[0][5].split(";")
                del KodiFileIds[EmbyLibraryIdIndex]
                KodiFileId = ";".join(KodiFileIds)

            if ExistingItem[0][7]:
                KodiParentIds = ExistingItem[0][7].split(";")
                del KodiParentIds[EmbyLibraryIdIndex]
                KodiParentId = ";".join(KodiParentIds)

            if EmbyLibraryId:
                self.cursor.execute("UPDATE Mapping SET KodiId = ?, KodiFileId = ?, KodiParentId = ?, EmbyLibraryId = ? WHERE EmbyId = ?", (KodiId, KodiFileId, KodiParentId, EmbyLibraryId, EmbyId))
                return

        self.cursor.execute("DELETE FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        self.remove_item_streaminfos(EmbyId)

    def remove_item_music_by_kodiid(self, KodiType, KodiId):
        self.cursor.execute("DELETE FROM Mapping WHERE KodiType = ? AND KodiId = ?", (KodiType, KodiId)) # Unique item
        self.cursor.execute("DELETE FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%s;%%" % KodiId)) # First item
        self.cursor.execute("DELETE FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%%;%s" % KodiId)) # Last item
        self.cursor.execute("DELETE FROM Mapping WHERE KodiType = ? AND KodiId LIKE ?", (KodiType, "%%;%s;%%" % KodiId)) # Middle item

    def get_stacked_kodiid(self, EmbyPresentationKey, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT KodiId FROM Mapping WHERE EmbyPresentationKey = ? AND EmbyType = ? AND EmbyLibraryId = ?", (EmbyPresentationKey, EmbyType, EmbyLibraryId))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_stacked_embyid(self, EmbyPresentationKey, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT EmbyId FROM Mapping WHERE EmbyPresentationKey = ? AND EmbyType = ? AND EmbyLibraryId LIKE ?", (EmbyPresentationKey, EmbyType, "%%%s%%" % EmbyLibraryId))
        return self.cursor.fetchall()

    def get_item_by_emby_folder_wild(self, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyId, EmbyType FROM Mapping WHERE EmbyLibraryId LIKE ?", ("%%%s%%" % EmbyLibraryId,))
        return self.cursor.fetchall()

    def get_item_by_emby_folder_wild_and_EmbyType(self, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT EmbyId FROM Mapping WHERE EmbyType = ? AND EmbyLibraryId LIKE ?", (EmbyType, "%%%s%%" % EmbyLibraryId))
        return self.cursor.fetchall()

    def get_KodiId_by_EmbyId_EmbyLibraryId(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyLibraryId, KodiId FROM Mapping WHERE EmbyId = ? AND EmbyLibraryId LIKE ?", (EmbyId, "%%%s%%" % EmbyLibraryId,))
        Data = self.cursor.fetchone()

        if Data:
            EmbyLibraryIds = Data[0].split(";")

            if EmbyLibraryId not in EmbyLibraryIds:
                return None

            EmbyLibraryIdIndex = EmbyLibraryIds.index(EmbyLibraryId)
            KodiIds = Data[1].split(";")
            return KodiIds[EmbyLibraryIdIndex]

        return None

    # stream infos
    def remove_item_streaminfos(self, EmbyId):
        self.cursor.execute("DELETE FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM VideoStreams WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM AudioStreams WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM Subtitles WHERE EmbyId = ?", (EmbyId,))

    def add_streamdata(self, EmbyId, Streams):
        for Stream in Streams:
            self.cursor.execute("INSERT OR REPLACE INTO MediaSources (EmbyId, MediaIndex, MediaSourceId, Path, Name, Size) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], Stream['Id'], Stream['Path'], Stream['Name'], Stream['Size']))

            for VideoStream in Stream['Video']:
                self.cursor.execute("INSERT OR REPLACE INTO VideoStreams (EmbyId, MediaIndex, StreamIndex, Codec, BitRate) VALUES (?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], VideoStream['Index'], VideoStream['codec'], VideoStream['BitRate']))

            for AudioStream in Stream['Audio']:
                self.cursor.execute("INSERT OR REPLACE INTO AudioStreams (EmbyId, MediaIndex, StreamIndex, DisplayTitle) VALUES (?, ?, ?, ?)", (EmbyId, Stream['Index'], AudioStream['Index'], AudioStream['DisplayTitle']))

            for SubtitleStream in Stream['Subtitle']:
                self.cursor.execute("INSERT OR REPLACE INTO Subtitles (EmbyId, MediaIndex, StreamIndex, Codec, Language, DisplayTitle) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], SubtitleStream['Index'], SubtitleStream['codec'], SubtitleStream['language'], SubtitleStream['DisplayTitle']))

    def add_multiversion(self, item, ItemType, API, video_db, update):
        if len(item['MediaSources']) > 1:
            LOG.debug("Multiversion video detected: %s" % item['Id'])

            for DataSource in item['MediaSources']:
                ItemReferenced = API.get_Item(DataSource['Id'], [ItemType], False, False)

                if not ItemReferenced:  # Server restarted
                    LOG.debug("Multiversion video detected, referenced item not found: %s" % DataSource['Id'])
                    continue

                LOG.debug("Multiversion video detected, referenced item: %s" % ItemReferenced['Id'])
                e_MultiItem = self.get_item_by_id(ItemReferenced['Id'])

                if not e_MultiItem:
                    if ItemType == "Episode":
                        self.add_reference(ItemReferenced['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "Episode", "episode", item['KodiParentIds'], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
                    elif ItemType == "Movie":
                        self.add_reference(ItemReferenced['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "Movie", "movie", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
                    elif ItemType == "MusicVideo":
                        self.add_reference(ItemReferenced['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "MusicVideo", "musicvideo", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
                else:
                    KodiId = join_Ids(item['KodiItemIds'])
                    KodiParentId = join_Ids(item['KodiParentIds'])
                    KodiFileId = join_Ids(item['KodiFileIds'])
                    self.cursor.execute("UPDATE Mapping SET EmbyPresentationKey = ?, EmbyFavourite = ?, KodiId = ?, KodiFileId = ?, KodiPathId = ?, KodiParentId = ? WHERE EmbyId = ?", (item['PresentationUniqueKey'], item['UserData']['IsFavorite'], KodiId, KodiFileId, item['KodiPathId'], KodiParentId, ItemReferenced['Id']))
                    self.remove_item_streaminfos(ItemReferenced['Id'])
                    LOG.debug("Multiversion video detected, referenced item exists: %s" % ItemReferenced['Id'])

                    if item['Id'] != ItemReferenced['Id'] and not update:
                        common.delete_ContentItemReferences(None, e_MultiItem[0], e_MultiItem[1], video_db, None, ItemType.lower())

                        if ItemType == "Episode":
                            video_db.delete_episode(e_MultiItem[0], e_MultiItem[1])
                        elif ItemType == "Movie":
                            video_db.delete_movie(e_MultiItem[0], e_MultiItem[1])
                        elif ItemType == "MusicVideo":
                            video_db.delete_musicvideos(e_MultiItem[0], e_MultiItem[1])

                self.add_streamdata(ItemReferenced['Id'], item['Streams'])

def join_Ids(Ids):
    IdsFiltered = []

    for Id in Ids:
        if Id:
            IdsFiltered.append(str(Id))

    if IdsFiltered:
        return ";".join(IdsFiltered)

    return None

from helper import loghandler
from core import common

LOG = loghandler.LOG('EMBY.database.emby_db')

class EmbyDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def init_EmbyDB(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Mapping (EmbyId INTEGER PRIMARY KEY, EmbyLibraryId TEXT, EmbyType TEXT, KodiType TEXT, KodiId INTEGER, KodiFileId INTEGER, KodiPathId INTEGER, KodiParentId INTEGER, EmbyParentId INTEGER, EmbyPresentationKey TEXT, EmbyFavourite BOOL)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources (EmbyId INTEGER, MediaIndex INTEGER, MediaSourceId TEXT, Path TEXT, Name TEXT, Size INTEGER)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT, BitRate INTEGER)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, DisplayTitle TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Subtitles (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT, Language TEXT, DisplayTitle TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS RemoveItems (EmbyId INTEGER PRIMARY KEY, LibraryId TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS UpdateItems (EmbyId INTEGER PRIMARY KEY, EmbyLibraryId TEXT, EmbyLibraryName TEXT, EmbyType TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS UserdataItems (Data TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Whitelist (EmbyLibraryId TEXT, EmbyLibraryType TEXT, EmbyLibraryName TEXT, UNIQUE(EmbyLibraryId, EmbyLibraryType))")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS LastIncrementalSync (EmbyType TEXT UNIQUE, Date TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS PendingSync (EmbyLibraryId TEXT, EmbyLibraryName TEXT, EmbyLibraryType TEXT, EmbyType TEXT, KodiCategory TEXT)")

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
    def get_LastIncrementalSync(self, EmbyType):
        self.cursor.execute("SELECT * FROM LastIncrementalSync WHERE EmbyType = ?", (EmbyType,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[1]

        return None

    def update_LastIncrementalSync(self, LastIncrementalSync, EmbyType):
        self.cursor.execute("INSERT OR REPLACE INTO LastIncrementalSync (EmbyType, Date) VALUES (?, ?)", (EmbyType, LastIncrementalSync))

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
    def add_UpdateItem(self, EmbyId, EmbyLibraryId, EmbyLibraryName, EmbyType):
        self.cursor.execute("INSERT OR REPLACE INTO UpdateItems (EmbyId, EmbyLibraryId, EmbyLibraryName, EmbyType) VALUES (?, ?, ?, ?)", (EmbyId, EmbyLibraryId, EmbyLibraryName, EmbyType))

    def get_UpdateItem(self):
        self.cursor.execute("SELECT * FROM UpdateItems")
        return self.cursor.fetchall()

    def delete_UpdateItem(self, EmbyId):
        self.cursor.execute("DELETE FROM UpdateItems WHERE EmbyId = ?", (EmbyId,))

    # RemoveItems
    def add_RemoveItem(self, EmbyId, LibraryId):
        self.cursor.execute("INSERT OR REPLACE INTO RemoveItems (EmbyId, LibraryId) VALUES (?, ?)", (EmbyId, LibraryId))

    def get_RemoveItem(self):
        self.cursor.execute("SELECT * FROM RemoveItems")
        return self.cursor.fetchall()

    def delete_RemoveItem(self, EmbyId):
        self.cursor.execute("DELETE FROM RemoveItems WHERE EmbyId = ?", (EmbyId,))

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

    def add_reference(self, EmbyId, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite):
        self.cursor.execute("INSERT OR REPLACE INTO Mapping (EmbyId, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite))

    def update_reference(self, KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite, EmbyId):
        self.cursor.execute("UPDATE Mapping SET KodiId = ?, KodiFileId = ?, KodiPathId = ?, EmbyType = ?, KodiType = ?, KodiParentId = ?, EmbyLibraryId = ?, EmbyParentId = ?, EmbyPresentationKey = ?, EmbyFavourite = ? WHERE EmbyId = ?", (KodiId, KodiFileId, KodiPathId, EmbyType, KodiType, KodiParentId, EmbyLibraryId, EmbyParentId, EmbyPresentationKey, EmbyFavourite, EmbyId))

    def update_reference_userdatachanged(self, EmbyFavourite, EmbyId):
        self.cursor.execute("UPDATE Mapping SET EmbyFavourite = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyId))

    def get_episode_fav(self):
        self.cursor.execute("SELECT KodiId FROM Mapping WHERE EmbyType = ? AND EmbyFavourite = ?", ("Episode", "1"))
        return self.cursor.fetchall()

    def update_parent_id(self, KodiParentId, EmbyId):
        self.cursor.execute("UPDATE Mapping SET KodiParentId = ? WHERE EmbyId = ?", (KodiParentId, EmbyId))

    def get_item_id_by_parent_id(self, KodiSetId):
        self.cursor.execute("SELECT EmbyId, KodiId FROM Mapping WHERE KodiParentId = ? AND KodiType = ?", (KodiSetId, "movie"))
        return self.cursor.fetchall()

    def get_item_by_parent_id(self, KodiParentId, KodiType):
        self.cursor.execute("SELECT EmbyId, KodiId, KodiFileId FROM Mapping WHERE KodiParentId = ? AND KodiType = ?", (KodiParentId, KodiType))
        return self.cursor.fetchall()

    def get_media_by_parent_id(self, EmbyParentId):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyParentId = ?", (EmbyParentId,))
        return self.cursor.fetchall()

    def get_items_by_embyparentid(self, EmbyParentId, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyParentId = ? AND EmbyType = ? AND EmbyLibraryId = ?", (EmbyParentId, EmbyType, EmbyLibraryId))
        return self.cursor.fetchall()

    def get_special_features(self, EmbyParentId):
        self.cursor.execute("SELECT EmbyId FROM Mapping WHERE EmbyType = 'SpecialFeature' AND EmbyParentId = ?", (EmbyParentId,))
        return self.cursor.fetchall()

    def get_KodiId_KodiType_by_EmbyId(self, item_id):
        self.cursor.execute("SELECT KodiId, KodiType FROM Mapping WHERE EmbyId = ?", (item_id,))
        return self.cursor.fetchall()

    def get_full_item_by_kodi_id(self, KodiId, KodiType):
        self.cursor.execute("SELECT EmbyId, KodiParentId, EmbyLibraryId, EmbyType, EmbyFavourite FROM Mapping WHERE KodiId = ? AND KodiType = ?", (KodiId, KodiType))
        return self.cursor.fetchone()

    def get_full_item_by_kodi_id_complete(self, KodiId, KodiType):
        self.cursor.execute("SELECT * FROM Mapping WHERE KodiId = ? AND KodiType = ?", (KodiId, KodiType))
        return self.cursor.fetchone()

    def get_media_by_id(self, EmbyId):
        self.cursor.execute("SELECT * FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    def get_kodiid(self, EmbyId):
        self.cursor.execute("SELECT KodiId, EmbyPresentationKey, KodiFileId FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchone()

    def remove_item(self, EmbyId):
        self.cursor.execute("DELETE FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        self.remove_item_streaminfos(EmbyId)

    def remove_item_music(self, EmbyId):
        self.cursor.execute("DELETE FROM Mapping WHERE EmbyId = ?", (EmbyId,))

    def remove_item_music_by_libraryId(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyLibraryId, KodiId, EmbyPresentationKey, KodiParentId FROM Mapping WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if not Data:
            LOG.error("remove_item_music_by_libraryId: %s " % EmbyId)
            return

        LibraryIds = Data[0].split(";")
        Index = LibraryIds.index(EmbyLibraryId)
        del LibraryIds[Index]

        if not LibraryIds:
            self.cursor.execute("DELETE FROM Mapping WHERE EmbyId = ?", (EmbyId,))
            return

        EmbyLibraryId = ";".join(LibraryIds)
        KodiIds = Data[1].split(";")
        del KodiIds[Index]
        KodiId = ";".join(KodiIds)
        EmbyPresentationKeys = Data[2].split(";")
        del EmbyPresentationKeys[Index]
        EmbyPresentationKey = ";".join(EmbyPresentationKeys)
        KodiParentId = Data[3]

        if KodiParentId:
            KodiParentIds = KodiParentId.split(";")
            del KodiParentIds[Index]
            KodiParentId = ";".join(KodiParentIds)

        self.cursor.execute("UPDATE Mapping SET EmbyLibraryId = ?, KodiId = ?, EmbyPresentationKey = ?, KodiParentId = ? WHERE EmbyId = ?", (EmbyLibraryId, KodiId, EmbyPresentationKey, KodiParentId, EmbyId))

    def get_stacked_kodiid(self, EmbyPresentationKey, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT KodiId FROM Mapping WHERE EmbyPresentationKey = ? AND EmbyType = ? AND EmbyLibraryId = ?", (EmbyPresentationKey, EmbyType, EmbyLibraryId))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_stacked_embyid(self, EmbyPresentationKey, EmbyLibraryId, EmbyType):
        self.cursor.execute("SELECT EmbyId FROM Mapping WHERE EmbyPresentationKey = ? AND EmbyType = ? AND EmbyLibraryId = ?", (EmbyPresentationKey, EmbyType, EmbyLibraryId))
        return self.cursor.fetchall()

    def get_item_by_emby_folder_wild(self, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyId, EmbyType FROM Mapping WHERE EmbyLibraryId LIKE ?", ("%%%s%%" % EmbyLibraryId,))
        return self.cursor.fetchall()

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
                        self.add_reference(ItemReferenced['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Episode", "episode", item['KodiSeasonId'], item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
                    elif ItemType == "Movie":
                        self.add_reference(ItemReferenced['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "Movie", "movie", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
                    elif ItemType == "MusicVideo":
                        self.add_reference(ItemReferenced['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "MusicVideo", "musicvideo", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
                else:
                    if ItemType == "Episode":
                        self.cursor.execute("UPDATE Mapping SET EmbyPresentationKey = ?, EmbyFavourite = ?, KodiId = ?, KodiFileId = ?, KodiPathId = ?, KodiParentId = ? WHERE EmbyId = ?", (item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], item['KodiSeasonId'], ItemReferenced['Id']))
                    else:
                        self.cursor.execute("UPDATE Mapping SET EmbyPresentationKey = ?, EmbyFavourite = ?, KodiId = ?, KodiFileId = ?, KodiPathId = ?, KodiParentId = ? WHERE EmbyId = ?", (item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], None, ItemReferenced['Id']))

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

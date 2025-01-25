import xbmc
from helper import utils
from core import common
from . import common_db

EmbyTypes = ("Movie", "Series", "Season", "Episode", "Audio", "MusicAlbum", "MusicArtist", "Genre", "MusicGenre", "Video", "MusicVideo", "BoxSet", "Tag", "Studio", "Playlist", "Person", "Folder") # Folder must be on last position

class EmbyDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common_db = common_db.CommonDatabase(cursor)

    def init_EmbyDB(self):
        Invalid = False

        # Table
        try:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Genre (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Studio (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Tag (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, Memo TEXT COLLATE NOCASE, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Person (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Folder (EmbyId INTEGER PRIMARY KEY, EmbyFolder TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Movie (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Video (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER, EmbyParentId INTEGER, isSpecial BOOL) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS BoxSet (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiParentId TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Series (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, EmbyPresentationKey TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Season (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiParentId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Episode (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, KodiParentId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicArtist (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicGenre (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicVideo (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicAlbum (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Audio (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER, LibraryIds TEXT COLLATE NOCASE, EmbyAlbumId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Playlist (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources (EmbyId INTEGER, MediaSourceId TEXT COLLATE NOCASE, Path TEXT COLLATE NOCASE, Name TEXT COLLATE NOCASE, Size INTEGER, IntroStart INTEGER, IntroEnd INTEGER, CreditsStart INTEGER, PRIMARY KEY(EmbyId, MediaSourceId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams (EmbyId INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, BitRate INTEGER, Width INTEGER, PRIMARY KEY(EmbyId, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams (EmbyId INTEGER, StreamIndex INTEGER, DisplayTitle TEXT COLLATE NOCASE, Codec TEXT COLLATE NOCASE, BitRate INTEGER, PRIMARY KEY(EmbyId, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Subtitles (EmbyId INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, Language TEXT COLLATE NOCASE, DisplayTitle TEXT COLLATE NOCASE, External BOOL, PRIMARY KEY(EmbyId, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS RemoveItems (EmbyId INTEGER, EmbyLibraryId TEXT COLLATE NOCASE, PRIMARY KEY(EmbyId, EmbyLibraryId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UpdateItems (EmbyId INTEGER PRIMARY KEY, EmbyType TEXT COLLATE NOCASE, EmbyLibraryId TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UserdataItems (Data TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LibrarySynced (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiDBs TEXT COLLATE NOCASE, PRIMARY KEY(EmbyLibraryId, EmbyLibraryName, EmbyType))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LibrarySyncedMirrow (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiDBs TEXT COLLATE NOCASE, PRIMARY KEY(EmbyLibraryId, EmbyLibraryName, EmbyType))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LastIncrementalSync (Date TEXT)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LibraryAdd (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiDBs TEXT COLLATE NOCASE, PRIMARY KEY(EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LibraryRemove (EmbyLibraryId TEXT COLLATE NOCASE PRIMARY KEY, EmbyLibraryName TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS EmbyLibraryMapping (EmbyLibraryId TEXT COLLATE NOCASE, EmbyId INTEGER, PRIMARY KEY(EmbyLibraryId, EmbyId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS DownloadItems (EmbyId INTEGER PRIMARY KEY, KodiPathIdBeforeDownload INTEGER, KodiFileId INTEGER, KodiId INTEGER, KodiType TEXT COLLATE NOCASE) WITHOUT ROWID")

            # Verify tabled
            self.cursor.execute("SELECT name FROM pragma_table_info('Genre')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyArtwork',)]:
                xbmc.log(f"EMBY.database.emby_db: Genre invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Studio')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyArtwork',)]:
                xbmc.log(f"EMBY.database.emby_db: Studio invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Tag')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('Memo',), ('EmbyArtwork',)]:
                xbmc.log(f"EMBY.database.emby_db: Tag invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Person')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',)]:
                xbmc.log(f"EMBY.database.emby_db: Person invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Folder')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('EmbyFolder',)]:
                xbmc.log(f"EMBY.database.emby_db: Folder invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Movie')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',)]:
                xbmc.log(f"EMBY.database.emby_db: Movie invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Video')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',), ('EmbyParentId',), ('isSpecial',)]:
                xbmc.log(f"EMBY.database.emby_db: Video invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('BoxSet')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiParentId',)]:
                xbmc.log(f"EMBY.database.emby_db: BoxSet invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Series')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyPresentationKey',), ('KodiPathId',)]:
                xbmc.log(f"EMBY.database.emby_db: Series invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Season')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiParentId',), ('EmbyPresentationKey',)]:
                xbmc.log(f"EMBY.database.emby_db: Season invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Episode')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('KodiParentId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',)]:
                xbmc.log(f"EMBY.database.emby_db: Episode invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MusicArtist')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('LibraryIds',)]:
                xbmc.log(f"EMBY.database.emby_db: MusicArtist invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MusicGenre')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('LibraryIds',), ('EmbyArtwork',)]:
                xbmc.log(f"EMBY.database.emby_db: MusicGenre invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MusicVideo')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',)]:
                xbmc.log(f"EMBY.database.emby_db: MusicVideo invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MusicAlbum')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('LibraryIds',)]:
                xbmc.log(f"EMBY.database.emby_db: MusicAlbum invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Audio')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyFolder',), ('KodiPathId',), ('LibraryIds',), ('EmbyAlbumId',)]:
                xbmc.log(f"EMBY.database.emby_db: Audio invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Playlist')")
            Cols = self.cursor.fetchall()

            if ('EmbyArtwork',) not in Cols:
                xbmc.log("EMBY.database.emby_db: Appand EmbyArtwork to Playlist", 0) # LOGDEBUG
                self.cursor.execute("ALTER TABLE Playlist ADD COLUMN EmbyArtwork 'TEXT COLLATE NOCASE'")
                self.cursor.execute("SELECT name FROM pragma_table_info('Playlist')")
                Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyArtwork',)]:
                xbmc.log(f"EMBY.database.emby_db: Playlist invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MediaSources')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('MediaSourceId',), ('Path',), ('Name',), ('Size',), ('IntroStart',), ('IntroEnd',), ('CreditsStart',)]:
                xbmc.log(f"EMBY.database.emby_db: MediaSources invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('VideoStreams')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('StreamIndex',), ('Codec',), ('BitRate',), ('Width',)]:
                xbmc.log(f"EMBY.database.emby_db: VideoStreams invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('AudioStreams')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('StreamIndex',), ('DisplayTitle',), ('Codec',), ('BitRate',)]:
                xbmc.log(f"EMBY.database.emby_db: AudioStreams invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Subtitles')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('StreamIndex',), ('Codec',), ('Language',), ('DisplayTitle',), ('External',)]:
                xbmc.log(f"EMBY.database.emby_db: Subtitles invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('RemoveItems')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('EmbyLibraryId',)]:
                xbmc.log(f"EMBY.database.emby_db: RemoveItems invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('UpdateItems')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('EmbyType',), ('EmbyLibraryId',)]:
                xbmc.log(f"EMBY.database.emby_db: UpdateItems invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('UserdataItems')")
            Cols = self.cursor.fetchall()

            if Cols != [('Data',)]:
                xbmc.log(f"EMBY.database.emby_db: UserdataItems invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LibrarySynced')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',), ('EmbyType',), ('KodiDBs',)]:
                xbmc.log(f"EMBY.database.emby_db: LibrarySynced invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LibrarySyncedMirrow')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',), ('EmbyType',), ('KodiDBs',)]:
                xbmc.log(f"EMBY.database.emby_db: LibrarySyncedMirrow invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LastIncrementalSync')")
            Cols = self.cursor.fetchall()

            if Cols != [('Date',)]:
                xbmc.log(f"EMBY.database.emby_db: LastIncrementalSync invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LibraryAdd')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',), ('EmbyType',), ('KodiDBs',)]:
                xbmc.log(f"EMBY.database.emby_db: LibraryAdd invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LibraryRemove')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',)]:
                xbmc.log(f"EMBY.database.emby_db: LibraryRemove invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('EmbyLibraryMapping')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyId',)]:
                xbmc.log(f"EMBY.database.emby_db: EmbyLibraryMapping invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('DownloadItems')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiPathIdBeforeDownload',), ('KodiFileId',), ('KodiId',), ('KodiType',)]:
                xbmc.log(f"EMBY.database.emby_db: DownloadItems invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            if not Invalid:
                self.add_Index()
        except Exception as Error: # Database invalid! Database reset mandatory
            xbmc.log(f"EMBY.database.emby_db: Database invalid, performing reset: {Error}", 3) # LOGERROR
            Invalid = True

        if Invalid:
            self.common_db.delete_tables("Emby")
            return False

        return True

    def add_Index(self):
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_EmbyLibraryMapping_EmbyLibraryId on EmbyLibraryMapping (EmbyLibraryId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_EmbyLibraryMapping_EmbyId on EmbyLibraryMapping (EmbyId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MediaSources_EmbyId on MediaSources (EmbyId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MediaSources_Path on MediaSources (Path)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Movie_EmbyFolder on Movie (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_EmbyFolder on Video (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_EmbyParentId on Video (EmbyParentId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Episode_EmbyFolder on Episode (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MusicVideo_EmbyFolder on MusicVideo (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Audio_EmbyFolder on Audio (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_EmbyParentId on Video (EmbyParentId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_KodiFileId on Video (KodiFileId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Tag_Memo on Tag (Memo)")

    def delete_Index(self):
        self.cursor.execute("DROP INDEX IF EXISTS idx_MediaSources_EmbyId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_MediaSources_Path")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Series_EmbyPresentationKey")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Season_EmbyPresentationKey")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Movie_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_EmbyParentId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Episode_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_MusicVideo_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Audio_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_EmbyParentId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_KodiFileId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Tag_Memo")

    # LibrarySynced
    def get_LibrarySynced(self):
        self.cursor.execute("SELECT * FROM LibrarySynced")
        return self.cursor.fetchall()

    def add_LibrarySynced(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs):
        self.cursor.execute("INSERT OR REPLACE INTO LibrarySynced (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs) VALUES (?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs))

    def remove_LibrarySynced(self, EmbyLibraryId):
        self.cursor.execute("DELETE FROM LibrarySynced WHERE EmbyLibraryId = ?", (EmbyLibraryId,))

    def get_LibrarySyncedMirrow(self):
        self.cursor.execute("SELECT * FROM LibrarySyncedMirrow")
        return self.cursor.fetchall()

    def add_LibrarySyncedMirrow(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs):
        self.cursor.execute("INSERT OR REPLACE INTO LibrarySyncedMirrow (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs) VALUES (?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs))

    def remove_LibrarySyncedMirrow(self, EmbyLibraryId):
        self.cursor.execute("DELETE FROM LibrarySyncedMirrow WHERE EmbyLibraryId = ?", (EmbyLibraryId,))

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
    def add_LibraryAdd(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs):
        self.cursor.execute("INSERT OR IGNORE INTO LibraryAdd (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs) VALUES (?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs))

    def remove_LibraryAdd(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs):
        self.cursor.execute("DELETE FROM LibraryAdd WHERE EmbyLibraryId = ? AND EmbyLibraryName = ? AND EmbyType = ? AND KodiDBs = ?", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDBs))

    def get_LibraryAdd(self):
        self.cursor.execute("SELECT * FROM LibraryAdd")
        return self.cursor.fetchall()

    def add_LibraryRemove(self, EmbyLibraryId, EmbyLibraryName):
        self.cursor.execute("INSERT OR IGNORE INTO LibraryRemove (EmbyLibraryId, EmbyLibraryName) VALUES (?, ?)", (EmbyLibraryId, EmbyLibraryName))

    def get_LibraryRemove(self):
        self.cursor.execute("SELECT * FROM LibraryRemove")
        return self.cursor.fetchall()

    def get_LibraryAdd_EmbyLibraryIds(self):
        PendingSyncAdded = set()
        self.cursor.execute("SELECT EmbyLibraryId FROM LibraryAdd")
        EmbyLibraryIds = self.cursor.fetchall()

        if EmbyLibraryIds:
            for EmbyLibraryId in EmbyLibraryIds:
                PendingSyncAdded.add(EmbyLibraryId[0])

        return PendingSyncAdded

    def get_LibraryRemove_EmbyLibraryIds(self):
        PendingSyncRemoved = set()
        self.cursor.execute("SELECT EmbyLibraryId FROM LibraryRemove")
        EmbyLibraryIds = self.cursor.fetchall()

        if EmbyLibraryIds:
            for EmbyLibraryId in EmbyLibraryIds:
                PendingSyncRemoved.add(EmbyLibraryId[0])

        return PendingSyncRemoved

    def remove_LibraryRemove(self, EmbyLibraryId):
        self.cursor.execute("DELETE FROM LibraryRemove WHERE EmbyLibraryId = ?", (EmbyLibraryId,))

    # UpdateItems
    def add_UpdateItem(self, EmbyId, EmbyType, EmbyLibraryId):
        self.cursor.execute("INSERT OR REPLACE INTO UpdateItems (EmbyId, EmbyType, EmbyLibraryId) VALUES (?, ?, ?)", (EmbyId, EmbyType, EmbyLibraryId))

    def get_UpdateItem(self):
        self.cursor.execute("SELECT * FROM UpdateItems")
        Items = self.cursor.fetchall()
        ItemsCount = len(Items)

        if not ItemsCount:
            return {}, 0

        Ids = ItemsCount * [None]
        Data = {}
        Counter = {}
        DataProcessed = {}

        for Item in Items:
            if Item[2] not in Data:
                Data[Item[2]] = {"MusicVideo": Ids.copy(), "Folder": Ids.copy(), "Movie": Ids.copy(), "Video": Ids.copy(), "Series": Ids.copy(), "Season": Ids.copy(), "Episode": Ids.copy(), "MusicArtist": Ids.copy(), "MusicAlbum": Ids.copy(), "Audio": Ids.copy(), "BoxSet": Ids.copy(), "Person": Ids.copy(), "Genre": Ids.copy(), "MusicGenre": Ids.copy(), "Studio": Ids.copy(), "Tag": Ids.copy(), "Playlist": Ids.copy(), "unknown": Ids.copy()}
                Counter[Item[2]] = {"MusicVideo": 0, "Folder": 0, "Movie": 0, "Video": 0, "Series": 0, "Season": 0, "Episode": 0, "MusicArtist": 0, "MusicAlbum": 0, "Audio": 0, "BoxSet": 0, "Person": 0, "MusicGenre": 0, "Genre": 0, "Studio": 0, "Tag": 0, "Playlist": 0, "unknown": 0}

        del Ids

        for Item in Items:
            if Item[1] in Data[Item[2]]:
                Data[Item[2]][Item[1]][Counter[Item[2]][Item[1]]] = str(Item[0])
                Counter[Item[2]][Item[1]] += 1
            else: # e.g. photo updte -> # Item: (3541991, 'Photo', '999999999')
                Data[Item[2]]["unknown"][Counter[Item[2]]["unknown"]] = str(Item[0])
                Counter[Item[2]]["unknown"] += 1

        for Key, Array in list(Data.items()):
            DataProcessed[Key] = {"MusicVideo": Array["MusicVideo"][:Counter[Key]["MusicVideo"]], "Folder": Array["Folder"][:Counter[Key]["Folder"]], "Movie": Array["Movie"][:Counter[Key]["Movie"]], "Video": Array["Video"][:Counter[Key]["Video"]], "Series": Array["Series"][:Counter[Key]["Series"]], "Season": Array["Season"][:Counter[Key]["Season"]], "Episode": Array["Episode"][:Counter[Key]["Episode"]], "MusicArtist": Array["MusicArtist"][:Counter[Key]["MusicArtist"]], "MusicAlbum": Array["MusicAlbum"][:Counter[Key]["MusicAlbum"]], "Audio": Array["Audio"][:Counter[Key]["Audio"]], "Person": Array["Person"][:Counter[Key]["Person"]], "MusicGenre": Array["MusicGenre"][:Counter[Key]["MusicGenre"]], "Genre": Array["Genre"][:Counter[Key]["Genre"]], "Studio": Array["Studio"][:Counter[Key]["Studio"]], "Tag": Array["Tag"][:Counter[Key]["Tag"]], "BoxSet": Array["BoxSet"][:Counter[Key]["BoxSet"]], "Playlist": Array["Playlist"][:Counter[Key]["Playlist"]], "unknown": Array["unknown"][:Counter[Key]["unknown"]]} # Filter None

        del Data
        return DataProcessed, ItemsCount

    def delete_UpdateItem(self, EmbyId):
        self.cursor.execute("DELETE FROM UpdateItems WHERE EmbyId = ?", (EmbyId,))

    # DownloadItems
    def add_DownloadItem(self, EmbyId, KodiPathIdBeforeDownload, KodiFileId, KodiId, KodiType):
        self.cursor.execute("INSERT OR REPLACE INTO DownloadItems (EmbyId, KodiPathIdBeforeDownload, KodiFileId, KodiId, KodiType) VALUES (?, ?, ?, ?, ?)", (EmbyId, KodiPathIdBeforeDownload, KodiFileId, KodiId, KodiType))

    def get_DownloadItem_PathId_FileId(self, EmbyId):
        self.cursor.execute("SELECT KodiPathIdBeforeDownload, KodiFileId, KodiId FROM DownloadItems WHERE EmbyId = ? ", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0], Data[1], Data[2]

        return None, None, None

    def get_DownloadItem(self):
        self.cursor.execute("SELECT * FROM DownloadItems")
        return self.cursor.fetchall()

    def delete_DownloadItem(self, EmbyId):
        self.cursor.execute("DELETE FROM DownloadItems WHERE EmbyId = ? ", (EmbyId,))

    def get_DownloadItem_exists_by_id(self, EmbyId):
        self.cursor.execute("SELECT EXISTS(SELECT 1 FROM DownloadItems WHERE EmbyId = ?)", (EmbyId, ))
        return self.cursor.fetchone()[0]

    # RemoveItems
    def add_RemoveItem(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("INSERT OR REPLACE INTO RemoveItems (EmbyId, EmbyLibraryId) VALUES (?, ?)", (EmbyId, EmbyLibraryId))

    def get_RemoveItem(self):
        self.cursor.execute("SELECT * FROM RemoveItems")
        return self.cursor.fetchall()

    def delete_RemoveItem(self, EmbyId):
        self.cursor.execute("DELETE FROM RemoveItems WHERE EmbyId = ? ", (EmbyId,))

    # Subtitle
    def get_Subtitles(self, EmbyId):
        self.cursor.execute("SELECT * FROM Subtitles WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    # MediaSources
    def get_FileSize(self, EmbyId):
        self.cursor.execute("SELECT Size FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        FileSize = self.cursor.fetchone()

        if FileSize:
            return FileSize[0]

        return 0

    def get_SinglePath(self, EmbyId, EmbyType):
        self.cursor.execute("SELECT Path FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        Paths = self.cursor.fetchall()
        EmbyIds = ()

        if Paths:
            PathData = ()

            for Path in Paths:
                # Emby has poorly designed unique IDs (EmbyId, MediasourceID) definitition, therefore this "by path" query is required
                self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE EmbyFolder = ?", (Path[0],))
                Data = self.cursor.fetchone()

                if Data:
                    EmbyIds += Data
                    PathData += (Path[0],)

            return "\n".join(PathData), EmbyIds

        return "", EmbyIds

    def get_mediasource(self, EmbyId):
        self.cursor.execute("SELECT * FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()


    def get_mediasourceid_by_path(self, Path):
        self.cursor.execute("SELECT MediaSourceId FROM MediaSources WHERE Path = ?", (Path,))
        EmbyId = self.cursor.fetchone()

        if EmbyId:
            return EmbyId[0]

        return None

    def get_mediasource_EmbyID_by_path_like(self, Path):
        self.cursor.execute("SELECT EmbyId FROM MediaSources WHERE Path LIKE ?", (f"%{Path}",))
        EmbyId = self.cursor.fetchone()

        if EmbyId:
            return EmbyId[0]

        return None

    # VideoStreams
    def get_videostreams(self, EmbyId):
        self.cursor.execute("SELECT * FROM VideoStreams WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    # AudioStreams
    def get_AudioStreams(self, EmbyId):
        self.cursor.execute("SELECT * FROM AudioStreams WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    # Mapping
    def get_embypresentationkey_by_id_embytype(self, EmbyId, Tables):
        for Table in Tables:
            self.cursor.execute(f"SELECT EmbyPresentationKey FROM {Table} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0]

        return ""

    def get_albumid_by_id(self, EmbyId):
        self.cursor.execute("SELECT EmbyAlbumId FROM Audio WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            return str(Data[0])

        return ""

    def get_id_by_albumid(self, EmbyAlbumId):
        ReturnData = ()
        self.cursor.execute("SELECT EmbyId FROM Audio WHERE EmbyAlbumId = ?", (EmbyAlbumId,))
        EmbyIds = self.cursor.fetchall()

        for EmbyId in EmbyIds:
            ReturnData += (str(EmbyId[0]),)

        return ReturnData

    def add_reference_audio(self, EmbyId, EmbyLibraryId, KodiIds, EmbyFavourite, EmbyFolder, KodiPathId, EmbyLibraryIds, EmbyAlbumId):
        self.cursor.execute("INSERT OR REPLACE INTO Audio (EmbyId, KodiId, EmbyFavourite, EmbyFolder, KodiPathId, LibraryIds, EmbyAlbumId) VALUES (?, ?, ?, ?, ?, ?, ?)", (EmbyId, ",".join(KodiIds), EmbyFavourite, EmbyFolder, KodiPathId, ",".join(EmbyLibraryIds), EmbyAlbumId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_musicartist(self, EmbyId, EmbyLibraryId, KodiIds, EmbyFavourite, EmbyLibraryIds):
        self.cursor.execute("INSERT OR REPLACE INTO MusicArtist (EmbyId, KodiId, EmbyFavourite, LibraryIds) VALUES (?, ?, ?, ?)", (EmbyId, KodiIds, EmbyFavourite, EmbyLibraryIds))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_musicgenre(self, EmbyId, EmbyLibraryId, KodiIds, EmbyFavourite, EmbyArtwork, LibraryIds):
        self.cursor.execute("INSERT OR REPLACE INTO MusicGenre (EmbyId, KodiId, EmbyFavourite, LibraryIds, EmbyArtwork) VALUES (?, ?, ?, ?, ?)", (EmbyId, KodiIds, EmbyFavourite, LibraryIds, EmbyArtwork))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_musicalbum(self, EmbyId, EmbyLibraryId, KodiIds, EmbyFavourite, EmbyLibraryIds):
        self.cursor.execute("INSERT OR REPLACE INTO MusicAlbum (EmbyId, KodiId, EmbyFavourite, LibraryIds) VALUES (?, ?, ?, ?)", (EmbyId, ",".join(KodiIds), EmbyFavourite, ",".join(EmbyLibraryIds)))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_episode(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId):
        self.cursor.execute("INSERT OR REPLACE INTO Episode (EmbyId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_season(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiParentId, EmbyPresentationKey):
        self.cursor.execute("INSERT OR REPLACE INTO Season (EmbyId, KodiId, KodiParentId, EmbyPresentationKey, EmbyFavourite) VALUES (?, ?, ?, ?, ?)", (EmbyId, KodiId, KodiParentId, EmbyPresentationKey, EmbyFavourite))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_series(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, EmbyPresentationKey, KodiPathId):
        self.cursor.execute("INSERT OR REPLACE INTO Series (EmbyId, KodiId, EmbyFavourite, EmbyPresentationKey, KodiPathId) VALUES (?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, EmbyPresentationKey, KodiPathId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_boxset(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiParentId):
        self.cursor.execute("INSERT OR REPLACE INTO BoxSet (EmbyId, KodiId, EmbyFavourite, KodiParentId) VALUES (?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiParentId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_movie_musicvideo(self, EmbyId, EmbyLibraryId, EmbyType, KodiId, EmbyFavourite, KodiFileId, EmbyPresentationKey, EmbyFolder, KodiPathId):
        self.cursor.execute(f"INSERT OR REPLACE INTO {EmbyType} (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyPresentationKey, EmbyFolder, KodiPathId) VALUES (?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyPresentationKey, EmbyFolder, KodiPathId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_video(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, isSpecial):
        self.cursor.execute("INSERT OR REPLACE INTO Video (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, isSpecial) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, isSpecial))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_folder(self, EmbyId, EmbyLibraryId, EmbyFolder):
        self.cursor.execute("INSERT OR REPLACE INTO Folder (EmbyId, EmbyFolder) VALUES (?, ?)", (EmbyId, EmbyFolder))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_metadata(self, EmbyId, EmbyLibraryId, EmbyType, KodiId, EmbyFavourite):
        self.cursor.execute(f"INSERT OR REPLACE INTO {EmbyType} (EmbyId, KodiId, EmbyFavourite) VALUES (?, ?, ?)", (EmbyId, KodiId, EmbyFavourite))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_tag(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, Memo, EmbyArtwork):
        self.cursor.execute("INSERT OR REPLACE INTO Tag (EmbyId, KodiId, EmbyFavourite, Memo, EmbyArtwork) VALUES (?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, Memo, EmbyArtwork))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_genre(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, EmbyArtwork):
        self.cursor.execute("INSERT OR REPLACE INTO Genre (EmbyId, KodiId, EmbyFavourite, EmbyArtwork) VALUES (?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, EmbyArtwork))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_playlist(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, EmbyArtwork):
        self.cursor.execute("INSERT OR REPLACE INTO Playlist (EmbyId, KodiId, EmbyFavourite, EmbyArtwork) VALUES (?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, EmbyArtwork))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def add_reference_studio(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, EmbyArtwork):
        self.cursor.execute("INSERT OR REPLACE INTO Studio (EmbyId, KodiId, EmbyFavourite, EmbyArtwork) VALUES (?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, EmbyArtwork))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_video(self, EmbyId, EmbyFavourite, EmbyParentId, EmbyPresentationKey, EmbyLibraryId):
        self.cursor.execute("UPDATE Video SET EmbyFavourite = ?, EmbyParentId = ?, EmbyPresentationKey = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyParentId, EmbyPresentationKey, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_studio(self, EmbyId, EmbyFavourite, EmbyArtwork, EmbyLibraryId):
        self.cursor.execute("UPDATE Studio SET EmbyFavourite = ?, EmbyArtwork = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyArtwork, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_genre(self, EmbyId, EmbyFavourite, EmbyArtwork, EmbyLibraryId):
        self.cursor.execute("UPDATE Genre SET EmbyFavourite = ?, EmbyArtwork = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyArtwork, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_tag(self, EmbyId, EmbyFavourite, Memo, EmbyArtwork, EmbyLibraryId):
        self.cursor.execute("UPDATE Tag SET EmbyFavourite = ?, EmbyArtwork = ?, Memo = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyArtwork, Memo, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_movie_musicvideo(self, EmbyId, EmbyType, EmbyFavourite, EmbyPresentationKey, EmbyLibraryId):
        self.cursor.execute(f"UPDATE {EmbyType} SET EmbyFavourite = ?, EmbyPresentationKey = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyPresentationKey, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_episode(self, EmbyId, EmbyFavourite, KodiParentId, EmbyPresentationKey, EmbyLibraryId):
        self.cursor.execute("UPDATE Episode SET EmbyFavourite = ?, KodiParentId = ?, EmbyPresentationKey = ? WHERE EmbyId = ?", (EmbyFavourite, KodiParentId, EmbyPresentationKey, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_musicgenre(self, EmbyId, EmbyFavourite, EmbyArtwork, EmbyLibraryId):
        self.cursor.execute("UPDATE MusicGenre SET EmbyFavourite = ?, EmbyArtwork = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyArtwork, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_audio(self, EmbyFavourite, EmbyId, EmbyLibraryId, EmbyAlbumId):
        self.cursor.execute("UPDATE Audio SET EmbyFavourite = ?, EmbyAlbumId = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyId, EmbyAlbumId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_generic(self, EmbyFavourite, EmbyId, EmbyType, EmbyLibraryId):
        self.cursor.execute(f"UPDATE {EmbyType} SET EmbyFavourite = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_favourite(self, EmbyFavourite, EmbyId, EmbyType):
        self.cursor.execute(f"UPDATE {EmbyType} SET EmbyFavourite = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyId))

    def update_EmbyLibraryMapping(self, EmbyId, EmbyLibraryId):
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def get_kodiid_kodifileid_embytype_kodiparentid_by_id(self, EmbyId): # return KodiItemId, KodiFileId, EmbyType, KodiParentId
        for EmbyType in EmbyTypes:
            if EmbyType in ("Season", "BoxSet"):
                self.cursor.execute(f"SELECT KodiId, KodiParentId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    return Data[0], None, EmbyType, Data[1]

            if EmbyType == "Episode":
                self.cursor.execute("SELECT KodiId, KodiParentId, KodiFileId FROM Episode WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    return Data[0], Data[2], EmbyType, Data[1]

            if EmbyType in ("Movie", "Video", "MusicVideo"):
                self.cursor.execute(f"SELECT KodiId, KodiFileId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    return Data[0], Data[1], EmbyType, None

            if EmbyType == "Folder":
                return None, None, None, None

            self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0], None, EmbyType, None

        xbmc.log(f"EMBY.database.emby_db: EmbyId not found (get_kodiid_kodifileid_embytype_kodiparentid_by_id): {EmbyId}", 3) # LOGERROR
        return None, None, None, None

    def get_remove_generator_items(self, EmbyId, EmbyLibraryId):
        RemoveItems = ()
        ItemFound = False

        for Table in ("Movie", "Episode", "MusicVideo"):
            self.cursor.execute(f"SELECT KodiId, KodiFileId, EmbyPresentationKey, KodiPathId FROM {Table} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], Data[1], Table, Data[2], None, Data[3], False),)
                ItemFound = True
                break

        if not ItemFound:
            self.cursor.execute("SELECT KodiId, KodiFileId, EmbyPresentationKey, KodiPathId, isSpecial FROM Video WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], Data[1], "Video", Data[2], None, Data[3], Data[4]),)
                ItemFound = True

        if not ItemFound:
            self.cursor.execute("SELECT KodiId, EmbyPresentationKey, KodiPathId FROM Series WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], None, "Series", Data[1], None, Data[2], False),)
                ItemFound = True

        if not ItemFound:
            self.cursor.execute("SELECT KodiId, EmbyPresentationKey, KodiParentId FROM Season WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], None, "Season", Data[1], Data[2], None, False),)
                ItemFound = True

        if not ItemFound:
            for Table in ("Genre", "MusicGenre", "Tag", "Person", "MusicArtist", "MusicAlbum", "Studio", "Playlist", "BoxSet"):
                self.cursor.execute(f"SELECT KodiId FROM {Table} WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    RemoveItems += ((EmbyId, Data[0], None, Table, None, None, None, False),)
                    ItemFound = True
                    break

        if not ItemFound:
            self.cursor.execute("SELECT KodiId, KodiPathId FROM Audio WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], None, "Audio", None, None, Data[1], False),)
                ItemFound = True

        if not ItemFound: # Folder
            self.cursor.execute("SELECT EmbyFolder FROM Folder WHERE EmbyId = ?", (EmbyId,))
            EmbyFolder = self.cursor.fetchone()

            if EmbyFolder:
                RemoveItems += ((EmbyId, None, None, "Folder", None, None, None, False),)

                # Delete items by same folder
                if not EmbyLibraryId:
                    for Table in ("Movie", "Episode", "MusicVideo"):
                        self.cursor.execute(f"SELECT EmbyId, KodiId, KodiFileId, EmbyPresentationKey, KodiPathId FROM {Table} WHERE EmbyFolder LIKE ?", (f"{EmbyFolder[0]}%",))
                        Datas = self.cursor.fetchall()

                        for Data in Datas:
                            RemoveItems += ((Data[0], Data[1], Data[2], Table, Data[3], None, Data[4], False),)

                    self.cursor.execute("SELECT EmbyId, KodiId, KodiFileId, EmbyPresentationKey, KodiPathId, isSpecial FROM Video WHERE EmbyFolder LIKE ?", (f"{EmbyFolder[0]}%",))
                    Datas = self.cursor.fetchall()

                    for Data in Datas:
                        RemoveItems += ((Data[0], Data[1], Data[2], "Video", Data[3], None, Data[4], Data[5]),)

                    self.cursor.execute("SELECT EmbyId, KodiId, KodiPathId FROM Audio WHERE EmbyFolder LIKE ?", (f"{EmbyFolder[0]}%",))
                    Datas = self.cursor.fetchall()

                    for Data in Datas:
                        RemoveItems += ((Data[0], Data[1], None, "Audio", None, None, Data[2], False),)

        RemoveItems = set(RemoveItems) # Filter doubles
        return RemoveItems

    def add_remove_library_items(self, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyId, EmbyLibraryId FROM EmbyLibraryMapping WHERE EmbyLibraryId = ?", (EmbyLibraryId,))
        Items = self.cursor.fetchall()
        self.cursor.executemany("INSERT OR REPLACE INTO RemoveItems (EmbyId, EmbyLibraryId) VALUES (?, ?)", Items)
        self.cursor.execute("DELETE FROM UpdateItems WHERE EmbyLibraryId = ?", (EmbyLibraryId,))

    def add_remove_library_items_person(self):
        self.cursor.execute("SELECT EmbyId, '999999999' FROM Person")
        Items = self.cursor.fetchall()
        self.cursor.executemany("INSERT OR REPLACE INTO RemoveItems (EmbyId, EmbyLibraryId) VALUES (?, ?)", Items)

    def get_episode_fav(self):
        self.cursor.execute("SELECT KodiId FROM Episode WHERE EmbyFavourite = ?", ("1",))
        return self.cursor.fetchall()

    def get_season_fav(self):
        self.cursor.execute("SELECT KodiId FROM Season WHERE EmbyFavourite = ?", ("1",))
        return self.cursor.fetchall()

    def update_parent_id(self, KodiParentId, EmbyId, EmbyType):
        self.cursor.execute(f"UPDATE {EmbyType} SET KodiParentId = ? WHERE EmbyId = ?", (KodiParentId, EmbyId))

    def get_KodiParentIds(self, EmbyId, EmbyType):
        self.cursor.execute(f"SELECT KodiParentId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            Data[0].split(";")

        return []

    def get_KodiLibraryTagIds(self):
        self.cursor.execute("SELECT KodiId FROM Tag WHERE Memo = ?", ("library",))
        return self.cursor.fetchall()

    def get_special_features(self, EmbyParentId):
        self.cursor.execute("SELECT EmbyId FROM Video WHERE EmbyParentId = ?", (EmbyParentId,))
        return self.cursor.fetchall()

    def get_EmbyId__KodiId_ImageUrl_by_KodiId_EmbyType(self, KodiId, EmbyType):
        if EmbyType == "MusicArtist":
            self.cursor.execute("SELECT EmbyId, KodiId FROM MusicArtist WHERE KodiId LIKE ? OR KodiId LIKE ? OR KodiId LIKE ? OR KodiId LIKE ? OR KodiId LIKE ?", (f"{KodiId};%", f"%;{KodiId}", f"%;{KodiId},%", f",%{KodiId};%", f",%{KodiId},%"))
        elif EmbyType == "MusicAlbum":
            self.cursor.execute("SELECT EmbyId, KodiId FROM MusicAlbum WHERE KodiId = ? OR KodiId LIKE ? OR KodiId LIKE ? OR KodiId LIKE ?", (KodiId, f"%,{KodiId}", f"{KodiId},%", f"%,{KodiId},%"))
        elif EmbyType == "MusicGenre":
            self.cursor.execute("SELECT EmbyId, KodiId, EmbyArtwork FROM MusicGenre WHERE KodiId LIKE ? OR KodiId LIKE ?", (f"%;{KodiId}", f"{KodiId};%"))
        elif EmbyType in ("Tag", "Genre", "Studio"):
            self.cursor.execute(f"SELECT EmbyId, KodiId, EmbyArtwork FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        else:
            self.cursor.execute(f"SELECT EmbyId, KodiId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))

        Data = self.cursor.fetchone()

        if Data:
            if len(Data) == 3:
                return Data[0], Data[1], Data[2]

            return Data[0], Data[1], None

        return None, None, None

    def remove_item_by_KodiId(self, KodiId, EmbyType, EmbyLibraryId):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            self.remove_item(Data[0], EmbyType, EmbyLibraryId)

    def get_EmbyId_by_KodiId_KodiType(self, KodiId, KodiType):
        if KodiType not in utils.KodiTypeMapping:
            xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_EmbyId_by_KodiId_KodiType): {KodiType}", 3) # LOGERROR
            return None

        self.cursor.execute(f"SELECT EmbyId FROM {utils.KodiTypeMapping[KodiType]} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        if KodiType == "movie": # Emby homevideos are synced as "movie" content into Kodi
            self.cursor.execute("SELECT EmbyId FROM Video WHERE KodiId = ?", (KodiId,))
            Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_LibraryIds_by_EmbyIds(self, EmbyIds):
        LibraryIds = {}

        for EmbyId in EmbyIds:
            self.cursor.execute("SELECT EmbyLibraryId FROM EmbyLibraryMapping WHERE EmbyId = ?", (EmbyId,))
            Datas = self.cursor.fetchall()

            if Datas:
                LibraryIds[EmbyId] = Datas

        return LibraryIds

    def get_EmbyIds_LibraryIds_by_KodiIds_EmbyType(self, KodiId, EmbyType):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        EmbyId = self.cursor.fetchone()
        EmbyLibraryIds = ()

        if EmbyId:
            EmbyId = EmbyId[0]
            self.cursor.execute("SELECT EmbyLibraryId FROM EmbyLibraryMapping WHERE EmbyId = ?", (EmbyId,))
            Datas = self.cursor.fetchall()


            for Data in Datas:
                EmbyLibraryIds += (Data[0],)
        else:
            EmbyId = ""

        return EmbyLibraryIds, EmbyId

    def get_EmbyId_EmbyFavourite_by_KodiId_KodiType(self, KodiId, KodiType):
        if KodiType not in utils.KodiTypeMapping:
            xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_EmbyId_EmbyFavourite_by_KodiId_KodiType): {KodiType}", 3) # LOGERROR
            return None, None

        self.cursor.execute(f"SELECT EmbyId, EmbyFavourite FROM {utils.KodiTypeMapping[KodiType]} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0], Data[1]

        if KodiType == "movie": # Emby homevideos are synced as "movie" content into Kodi
            self.cursor.execute("SELECT EmbyId, EmbyFavourite FROM Video WHERE KodiId = ?", (KodiId,))
            Data = self.cursor.fetchone()

        if Data:
            return Data[0], Data[1]

        return None, None

    def get_nativemode_data(self, KodiId, KodiType):
        if KodiType == "videoversion":
            self.cursor.execute("SELECT EmbyId FROM Video WHERE KodiFileId = ?", (KodiId,))
            Data = self.cursor.fetchone()
            EmbyType = "Video"
        else:
            if KodiType not in utils.KodiTypeMapping:
                xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_nativemode_data): {KodiType}", 3) # LOGERROR
                return None, None, None, None, None

            EmbyType = utils.KodiTypeMapping[KodiType]
            self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
            Data = self.cursor.fetchone()

            if not Data and KodiType == "movie": # Emby homevideos are synced as "movie" content into Kodi
                self.cursor.execute("SELECT EmbyId FROM Video WHERE KodiId = ?", (KodiId,))
                Data = self.cursor.fetchone()
                EmbyType = "Video"

        if Data:
            self.cursor.execute("SELECT IntroStart, IntroEnd, CreditsStart FROM MediaSources WHERE EmbyId = ?", (Data[0],))
            Markers = self.cursor.fetchone()

            if Markers:
                return Data[0], EmbyType, Markers[0], Markers[1], Markers[2]

            return Data[0], EmbyType, None, None, None

        return None, None, None, None, None

    def get_item_by_id(self, EmbyId, EmbyType):
        if not EmbyType:
            Tables = EmbyTypes
        else:
            Tables = [EmbyType]

        for Table in Tables:
            self.cursor.execute(f"SELECT * FROM {Table} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data

        return []

    def get_movieversions(self, EmbyId):
        self.cursor.execute("SELECT KodiId FROM Movie WHERE EmbyId = ?", (EmbyId,))
        KodiId = self.cursor.fetchone()

        if KodiId:
            self.cursor.execute("SELECT EmbyId, KodiFileId, KodiId, KodiPathId FROM Movie WHERE KodiId = ?", (KodiId[0],))
            EmbyIds = self.cursor.fetchall()
            return EmbyIds

        return []

    def get_EpisodePathsBySeries(self, EmbyId):
        self.cursor.execute("SELECT EmbyPresentationKey FROM Series WHERE EmbyId = ?", (EmbyId,))
        EmbyPresentationKey = self.cursor.fetchone()
        EmbyIdsData = ()

        if EmbyPresentationKey:
            self.cursor.execute("SELECT EmbyId FROM Episode WHERE EmbyPresentationKey LIKE ?", (f"{EmbyPresentationKey[0]}%",))
            LocalEmbyIds = self.cursor.fetchall()
            PathData = ()

            for LocalEmbyId in LocalEmbyIds:
                EpisodePath, EpisodeEmbyIds = self.get_SinglePath(LocalEmbyId[0], "Episode")
                PathData += (EpisodePath,)
                EmbyIdsData += EpisodeEmbyIds

            return "\n".join(PathData), EmbyIdsData

        return "", ()

    def get_EpisodePathsBySeason(self, EmbyId):
        self.cursor.execute("SELECT EmbyPresentationKey FROM Season WHERE EmbyId = ?", (EmbyId,))
        EmbyPresentationKey = self.cursor.fetchone()
        EmbyIdsData = ()

        if EmbyPresentationKey:
            self.cursor.execute("SELECT EmbyId FROM Episode WHERE EmbyPresentationKey LIKE ?", (f"{EmbyPresentationKey[0]}%",))
            LocalEmbyIds = self.cursor.fetchall()
            PathData = ()

            for LocalEmbyId in LocalEmbyIds:
                EpisodePath, EpisodeEmbyIds = self.get_SinglePath(LocalEmbyId[0], "Episode")
                PathData += (EpisodePath,)
                EmbyIdsData += EpisodeEmbyIds

            return "\n".join(PathData), EmbyIdsData

        return "", ()

    # favorite infos
    def get_FavoriteInfos(self, Table):
        if Table in ("Person", "MusicArtist", "Series", "Audio", "BoxSet", "MusicAlbum"):
            self.cursor.execute(f"SELECT EmbyFavourite, KodiId, EmbyId FROM {Table}")
        elif Table == "Season":
            self.cursor.execute("SELECT EmbyFavourite, KodiId, KodiParentId, EmbyId FROM Season")
        elif Table in ("Movie", "Episode", "MusicVideo", "Video"):
            self.cursor.execute(f"SELECT EmbyFavourite, KodiFileId, KodiId, EmbyId FROM {Table}")
        else:
            self.cursor.execute(f"SELECT EmbyFavourite, KodiId, EmbyArtwork, EmbyId FROM {Table}")

        return self.cursor.fetchall()

    def get_contenttype_by_id(self, EmbyId):
        for EmbyType in EmbyTypes:
            self.cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {EmbyType} WHERE EmbyId = ?)", (EmbyId, ))

            if self.cursor.fetchone()[0]:
                return EmbyType

        return ""

    def get_item_exists_by_id(self, EmbyId, EmbyType):
        self.cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {EmbyType} WHERE EmbyId = ?)", (EmbyId, ))
        return self.cursor.fetchone()[0]

    def get_item_exists_multi_library(self, EmbyId, EmbyType, LibraryId):
        if LibraryId:
            self.cursor.execute(f"SELECT LibraryIds FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
            LibraryIds = self.cursor.fetchone()

            if LibraryIds:
                Temp = LibraryIds[0].split(",")

                if str(LibraryId) in Temp:
                    return True

        return False

    def get_item_exists_multi_db(self, EmbyId, EmbyType, LibraryId, Index):
        if LibraryId:
            self.cursor.execute(f"SELECT LibraryIds FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
            LibraryIds = self.cursor.fetchone()

            if LibraryIds:
                LibraryIds = LibraryIds[0].split(";")[Index]
                Temp = LibraryIds.split(",")

                if str(LibraryId) in Temp:
                    return True
        else:
            self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
            KodiIds = self.cursor.fetchone()

            if KodiIds:
                KodiIds = KodiIds[0].split(";")

                if KodiIds[Index]:
                    return True

        return False

    def remove_item_by_parentid(self, EmbyParentId, EmbyType, EmbyLibraryId):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE EmbyParentId = ?", (EmbyParentId,))
        EmbyIds = self.cursor.fetchall()

        for EmbyId in EmbyIds:
            self.remove_item(EmbyId[0], EmbyType, EmbyLibraryId)

    def remove_item(self, EmbyId, EmbyType, EmbyLibraryId):
        DeleteItem = True

        if EmbyLibraryId:
            self.cursor.execute("DELETE FROM EmbyLibraryMapping WHERE EmbyId = ? AND EmbyLibraryId = ?", (EmbyId, EmbyLibraryId))
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM EmbyLibraryMapping WHERE EmbyId = ?)", (EmbyId, ))

            if self.cursor.fetchone()[0]:
                DeleteItem = False
        else:
            self.cursor.execute("DELETE FROM EmbyLibraryMapping WHERE EmbyId = ?", (EmbyId,))
            DeleteItem = True

        if DeleteItem:
            self.cursor.execute(f"DELETE FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))

            if EmbyType in ("Movie", "Video", "MusicVideo", "Episode", "Audio"):
                self.remove_item_streaminfos(EmbyId)

        return DeleteItem

    def remove_item_multi_db(self, EmbyId, KodiId, EmbyType, EmbyLibraryId, LibraryIds):
        self.cursor.execute("DELETE FROM EmbyLibraryMapping WHERE EmbyId = ? AND EmbyLibraryId = ?", (EmbyId, EmbyLibraryId))
        self.cursor.execute(f"UPDATE {EmbyType} SET KodiId = ?, LibraryIds = ? WHERE EmbyId = ?", (KodiId, LibraryIds, EmbyId))

    def get_KodiId_by_EmbyPresentationKey(self, EmbyType, EmbyPresentationKey):
        if EmbyPresentationKey:
            self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyPresentationKey = ?", (EmbyPresentationKey,))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                for KodiId in KodiIds:
                    if KodiId[0]:
                        return KodiId[0]

        return None

    def get_EmbyId_by_EmbyPresentationKey(self, EmbyPresentationKey, EmbyType):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE EmbyPresentationKey = ?", (EmbyPresentationKey,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_EmbyIds_by_EmbyPresentationKey(self, EmbyPresentationKey, EmbyType):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE EmbyPresentationKey = ?", (EmbyPresentationKey,))
        return self.cursor.fetchall()

    def get_boxsets(self):
        self.cursor.execute("SELECT EmbyId FROM BoxSet")
        return self.cursor.fetchall()

    def get_item_by_memo(self, Memo):
        self.cursor.execute("SELECT KodiId FROM Tag WHERE Memo = ?", (Memo,))
        Tags = self.cursor.fetchall()
        KodiIds = ()

        for Tag in Tags:
            KodiIds += Tag

        return KodiIds

    def remove_item_by_memo(self, Memo):
        self.cursor.execute("DELETE FROM Tag WHERE Memo = ?", (Memo,))

    def get_KodiId_by_EmbyId(self, EmbyId):
        for Table in ('Genre', 'Episode', 'MusicVideo', 'Series', 'Studio', 'Person', 'MusicArtist', 'Playlist', 'Season', 'MusicGenre', 'Audio', 'MusicAlbum', 'Tag', 'Video', 'Movie', 'BoxSet'):
            self.cursor.execute(f"SELECT KodiId FROM {Table} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0], utils.EmbyTypeMapping[Table]

        return None, None

    def get_KodiId_by_EmbyId_EmbyType(self, EmbyId, EmbyType):
        self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_Records_by_EmbyType(self, EmbyType):
        self.cursor.execute(f"SELECT * FROM {EmbyType}")
        return self.cursor.fetchall()

    def get_KodiId_by_EmbyId_and_LibraryId(self, EmbyId, EmbyType, EmbyLibraryId, EmbyServer):
        self.cursor.execute(f"SELECT KodiId, LibraryIds FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            if EmbyType == "MusicArtist":
                Id = f"{EmbyLibraryId}{EmbyType}"

                if Id in EmbyServer.library.LibrarySyncedKodiDBs:
                    KodiDB = EmbyServer.library.LibrarySyncedKodiDBs[Id]

                    if KodiDB == "video,music": # mixed content
                        return None, None

                    KodiIds = Data[0].split(";")

                    if KodiDB == "video":
                        return KodiIds[0], "video"

                    return KodiIds[1], "music"

                return None, None

            if EmbyType in ("MusicAlbum", "Audio"):
                if f"{EmbyLibraryId}Playlist" in EmbyServer.library.LibrarySyncedKodiDBs: # Request by Playlist library, accept any valid synced EmbyId
                    KodiIds = Data[0].split(",")
                    return KodiIds[0], "music"

                LibraryIds = Data[1].split(",")

                if EmbyLibraryId not in LibraryIds:
                    return None, None

                LibraryIndex = LibraryIds.index(EmbyLibraryId)
                KodiIds = Data[0].split(",")
                return KodiIds[LibraryIndex], "music"

            return Data[0], "music"

        return None, None

    def get_MusicAlbum_by_EmbyId(self, EmbyId):
        self.cursor.execute("SELECT KodiId, LibraryIds FROM MusicAlbum WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0].split(","), Data[1].split(",")

        return [], []

    def get_KodiId_by_EmbyId_multi_db(self, EmbyId, EmbyType, KodiDB):
        self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            Data = Data[0].split(";")

            if KodiDB == "video":
                return Data[0]

            return Data[1]

        return ""

    # stream infos
    def remove_item_streaminfos(self, EmbyId):
        self.cursor.execute("DELETE FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM VideoStreams WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM AudioStreams WHERE EmbyId = ?", (EmbyId,))
        self.cursor.execute("DELETE FROM Subtitles WHERE EmbyId = ?", (EmbyId,))

    def add_streamdata(self, EmbyId, MediaSources):
        self.remove_item_streaminfos(EmbyId)

        for MediaSource in MediaSources:
            self.cursor.execute("INSERT OR REPLACE INTO MediaSources (EmbyId, MediaSourceId, Path, Name, Size, IntroStart, IntroEnd, CreditsStart) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, MediaSource['Id'], MediaSource['Path'], MediaSource['Name'], MediaSource['Size'], MediaSource['IntroStartPositionTicks'], MediaSource['IntroEndPositionTicks'], MediaSource['CreditsPositionTicks']))

            for VideoStream in MediaSource['KodiStreams']['Video']:
                self.cursor.execute("INSERT OR REPLACE INTO VideoStreams (EmbyId, StreamIndex, Codec, BitRate, Width) VALUES (?, ?, ?, ?, ?)", (EmbyId, VideoStream['Index'], VideoStream['codec'], VideoStream['BitRate'], VideoStream['width']))

            for AudioStream in MediaSource['KodiStreams']['Audio']:
                self.cursor.execute("INSERT OR REPLACE INTO AudioStreams (EmbyId, StreamIndex, DisplayTitle, Codec, BitRate) VALUES (?, ?, ?, ?, ?)", (EmbyId, AudioStream['Index'], AudioStream['DisplayTitle'], AudioStream['codec'], AudioStream['BitRate']))

            for SubtitleStream in MediaSource['KodiStreams']['Subtitle']:
                self.cursor.execute("INSERT OR REPLACE INTO Subtitles (EmbyId, StreamIndex, Codec, Language, DisplayTitle, External) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, SubtitleStream['Index'], SubtitleStream['codec'], SubtitleStream['language'], SubtitleStream['DisplayTitle'], SubtitleStream['external']))

    def add_multiversion(self, item, EmbyType, API, SQLs, ServerId):
        if item['MediaSources'][0]['KodiStreams']['Video']:
            MovieDefault = (False, item['MediaSources'][0]['KodiStreams']['Video'][0]['width'], item['KodiFileId'], item['KodiPathId'], item['KodiPath'])
        else:
            MovieDefault = (False, 0, item['KodiFileId'], item['KodiPathId'], item['KodiPath'])

        for MediaSource in item['MediaSources']:
            if MediaSource['Type'] == "Default":
                continue

            xbmc.log(f"EMBY.database.emby_db: Multiversion video detected: {item['Id']}", 0) # LOGDEBUG

            # Get additional data, actually ParentId and probably PresentationUniqueKey could differ to item's core info
            if 'ItemId' not in MediaSource:
                ItemReferenced = API.get_Item(MediaSource['Id'], [EmbyType], False, False, False)

                if not ItemReferenced:  # Server restarted
                    xbmc.log(f"EMBY.database.emby_db: Multiversion video detected, referenced item not found: {MediaSource['Id']}", 0) # LOGDEBUG
                    continue

                EmbyId = ItemReferenced['Id']
            else:
                EmbyId = MediaSource['ItemId']

            # Delete old multiversions
            KodiIds = self.get_item_by_id(EmbyId, EmbyType)

            if KodiIds: # Same content assigned to multiple libraries
                ItemReferenced = item.copy()
                ItemReferenced.update({'Id': EmbyId, 'MediaSources': [MediaSource], "KodiFileId": KodiIds[3], "KodiItemId": KodiIds[1], 'LibraryId': None})

                # Remove old Kodi video-db references
                if str(item['KodiItemId']) != str(ItemReferenced['KodiItemId']) and str(item['KodiFileId']) != str(ItemReferenced['KodiFileId']):
                    common.delete_ContentItem(ItemReferenced, SQLs, utils.EmbyTypeMapping[EmbyType], EmbyType, True)

                    if SQLs['video']: # video otherwise unsynced content e.g. specials
                        if EmbyType == "Episode":
                            if KodiIds[7] != item['KodiPathId']: # KodiIds[7] = KodiPathId
                                SQLs['video'].delete_episode(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], KodiIds[7])
                            else: # Do not delete path if default item path matches sub item path
                                SQLs['video'].delete_episode(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], None)
                        elif EmbyType in ("Movie", "Video"):
                            if KodiIds[6] != item['KodiPathId']: # KodiIds[6] = KodiPathId
                                SQLs['video'].delete_movie(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], KodiIds[6])
                            else: # Do not delete path if default item path matches sub item path
                                SQLs['video'].delete_movie(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], None)
                        elif EmbyType == "MusicVideo":
                            if KodiIds[6] != item['KodiPathId']: # KodiIds[6] = KodiPathId
                                SQLs['video'].delete_musicvideos(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], KodiIds[6])
                            else: # Do not delete path if default item path matches sub item path
                                SQLs['video'].delete_musicvideos(ItemReferenced['KodiItemId'], ItemReferenced['KodiFileId'], None)

            # Add references
            ItemReferenced = item.copy()
            ItemReferenced.update({'Id': EmbyId, 'MediaSources': [MediaSource]})

            if EmbyType == "Episode":
                self.add_reference_episode(ItemReferenced['Id'], ItemReferenced['LibraryId'], None, item['UserData']['IsFavorite'], None, None, ItemReferenced['PresentationUniqueKey'], MediaSource['Path'], None)
            elif EmbyType == "MusicVideo":
                self.add_reference_movie_musicvideo(ItemReferenced['Id'], ItemReferenced['LibraryId'], ItemReferenced['Type'], None, item['UserData']['IsFavorite'], None, ItemReferenced['PresentationUniqueKey'], MediaSource['Path'], None)
            elif EmbyType == "Movie":
                ItemReferenced['KodiFileId'] = SQLs["video"].create_entry_file()
                EmbyIdBackup = ItemReferenced['Id'] # workaround for Emby limitiation not unifying progress by version and not respecting subversion specific ItemId
                ItemReferenced['Id'] = item['Id'] # workaround for Emby limitiation not unifying progress by version and not respecting subversion specific ItemId
                common.set_path_filename(ItemReferenced, ServerId, MediaSource)
                ItemReferenced['Id'] = EmbyIdBackup # workaround for Emby limitiation not unifying progress by version and not respecting subversion specific ItemId
                ItemReferenced['KodiPathId'] = SQLs['video'].get_add_path(ItemReferenced['KodiPath'], "movies")
                SQLs["video"].add_bookmarks(ItemReferenced['KodiFileId'], MediaSource['KodiRunTimeTicks'], MediaSource['KodiChapters'], ItemReferenced['KodiPlaybackPositionTicks'])
                SQLs["video"].add_streams(ItemReferenced['KodiFileId'], MediaSource['KodiStreams']['Video'], MediaSource['KodiStreams']['Audio'], MediaSource['KodiStreams']['Subtitle'], MediaSource['KodiRunTimeTicks'])
                SQLs["video"].common_db.add_artwork(ItemReferenced['KodiArtwork'], ItemReferenced['KodiFileId'], "videoversion")
                SQLs["video"].add_movie_version(item['KodiItemId'], ItemReferenced['KodiFileId'], ItemReferenced['KodiPathId'], ItemReferenced['KodiFilename'], ItemReferenced['KodiDateCreated'], ItemReferenced['KodiPlayCount'], ItemReferenced['KodiLastPlayedDate'], ItemReferenced['KodiStackedFilename'], MediaSource['Name'], "movie", 0)
                self.add_reference_movie_musicvideo(ItemReferenced['Id'], item['LibraryId'], ItemReferenced['Type'], item['KodiItemId'], item['UserData']['IsFavorite'], ItemReferenced['KodiFileId'], ItemReferenced['PresentationUniqueKey'], MediaSource['Path'], ItemReferenced['KodiPathId'])

                # Change default movie version to highest resolution (width)
                if utils.SyncHighestResolutionAsDefault:
                    if MediaSource['KodiStreams']['Video'] and MediaSource['KodiStreams']['Video'][0]['width'] and MediaSource['KodiStreams']['Video'][0]['width'] > MovieDefault[1]:
                        MovieDefault = (True, MediaSource['KodiStreams']['Video'][0]['width'], ItemReferenced['KodiFileId'], ItemReferenced['KodiPathId'], ItemReferenced['KodiPath'])

                # Change default movie version to local content
                if utils.SyncLocalOverPlugins:
                    if not ItemReferenced['KodiPath'].startswith("plugin://") and MovieDefault[4].startswith("plugin://"):
                        MovieDefault = (True, 0, ItemReferenced['KodiFileId'], ItemReferenced['KodiPathId'], ItemReferenced['KodiPath'])
            elif EmbyType == "Video":
                self.add_reference_video(ItemReferenced['Id'], item['LibraryId'], None, item['UserData']['IsFavorite'], None, ItemReferenced['ParentId'], ItemReferenced['PresentationUniqueKey'], MediaSource['Path'], None, False)

        # Update video version
        if MovieDefault[0]:
            xbmc.log(f"EMBY.database.emby_db: Update default video version {item['Id']} / {item['KodiItemId']}", 0) # LOGDEBUG
            SQLs["video"].update_default_movieversion(item['KodiItemId'], MovieDefault[2], MovieDefault[3], MovieDefault[4])

def join_Ids(Ids):
    IdsFiltered = []
    DataFound = False

    for Id in Ids:
        if Id:
            IdsFiltered.append(str(Id))
            DataFound = True
        else:
            IdsFiltered.append("")

    if DataFound:
        return ";".join(IdsFiltered)

    return None

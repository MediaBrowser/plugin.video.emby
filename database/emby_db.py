import xbmc
from helper import utils
from core import common
from . import common_db

EmbyTypes = ("Movie", "Series", "Season", "Episode", "Audio", "MusicAlbum", "MusicArtist", "Genre", "MusicGenre", "Video", "MusicVideo", "BoxSet", "Folder", "Tag", "Studio", "Playlist", "Person")
TablesWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey = ("Movie", "Video", "Episode", "MusicVideo")
TablesWith_KodiId_EmbyFolder = ("Audio",)
TablesWith_KodiId_EmbyPresentationKey = ("Series", "Season")
TablesWith_KodiId = ("Genre", "MusicGenre", "Tag", "Person", "MusicArtist", "MusicAlbum", "Studio", "Playlist", "Audio", "BoxSet")
TablesWith_KodiId_total = ('Genre', 'Episode', 'MusicVideo', 'Series', 'Studio', 'Person', 'MusicArtist', 'Playlist', 'Season', 'MusicGenre', 'Audio', 'MusicAlbum', 'Tag', 'Video', 'Movie', 'BoxSet')

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
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Video (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER, EmbyParentId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS BoxSet (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiParentId TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Series (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, EmbyPresentationKey TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Season (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiParentId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Episode (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, KodiParentId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER, IntroStart INTEGER, IntroEnd INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicArtist (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicGenre (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE, EmbyArtwork TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicVideo (EmbyId INTEGER PRIMARY KEY, KodiId INTEGER, EmbyFavourite BOOL, KodiFileId INTEGER, EmbyPresentationKey TEXT COLLATE NOCASE, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MusicAlbum (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, LibraryIds TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Audio (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL, EmbyFolder TEXT COLLATE NOCASE, KodiPathId INTEGER, LibraryIds TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Playlist (EmbyId INTEGER PRIMARY KEY, KodiId TEXT COLLATE NOCASE, EmbyFavourite BOOL) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources (EmbyId INTEGER, MediaIndex INTEGER, MediaSourceId TEXT COLLATE NOCASE, Path TEXT COLLATE NOCASE, Name TEXT COLLATE NOCASE, Size INTEGER, PRIMARY KEY(EmbyId, MediaIndex, MediaSourceId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, BitRate INTEGER, PRIMARY KEY(EmbyId, MediaIndex, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, DisplayTitle TEXT COLLATE NOCASE, Codec TEXT COLLATE NOCASE, BitRate INTEGER, PRIMARY KEY(EmbyId, MediaIndex, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Subtitles (EmbyId INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT COLLATE NOCASE, Language TEXT COLLATE NOCASE, DisplayTitle TEXT COLLATE NOCASE, External BOOL, PRIMARY KEY(EmbyId, MediaIndex, StreamIndex))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS RemoveItems (EmbyId INTEGER, EmbyLibraryId TEXT COLLATE NOCASE, PRIMARY KEY(EmbyId, EmbyLibraryId))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UpdateItems (EmbyId INTEGER PRIMARY KEY, EmbyType TEXT COLLATE NOCASE, EmbyLibraryId TEXT COLLATE NOCASE) WITHOUT ROWID")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS UserdataItems (Data TEXT COLLATE NOCASE)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS Whitelist (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiDB TEXT COLLATE NOCASE, KodiDBs TEXT COLLATE NOCASE, PRIMARY KEY(EmbyLibraryId, EmbyLibraryName, EmbyType))")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS LastIncrementalSync (Date TEXT)")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS PendingSync (EmbyLibraryId TEXT COLLATE NOCASE, EmbyLibraryName TEXT COLLATE NOCASE, EmbyType TEXT COLLATE NOCASE, KodiDB TEXT COLLATE NOCASE, KodiDBs TEXT COLLATE NOCASE)")
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

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',), ('EmbyParentId',)]:
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

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('KodiFileId',), ('KodiParentId',), ('EmbyPresentationKey',), ('EmbyFolder',), ('KodiPathId',), ('IntroStart',), ('IntroEnd',)]:
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

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',), ('EmbyFolder',), ('KodiPathId',), ('LibraryIds',)]:
                xbmc.log(f"EMBY.database.emby_db: Audio invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Playlist')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('KodiId',), ('EmbyFavourite',)]:
                xbmc.log(f"EMBY.database.emby_db: Playlist invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('MediaSources')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('MediaIndex',), ('MediaSourceId',), ('Path',), ('Name',), ('Size',)]:
                xbmc.log(f"EMBY.database.emby_db: MediaSources invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('VideoStreams')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('MediaIndex',), ('StreamIndex',), ('Codec',), ('BitRate',)]:
                xbmc.log(f"EMBY.database.emby_db: VideoStreams invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('AudioStreams')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('MediaIndex',), ('StreamIndex',), ('DisplayTitle',), ('Codec',), ('BitRate',)]:
                xbmc.log(f"EMBY.database.emby_db: AudioStreams invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('Subtitles')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyId',), ('MediaIndex',), ('StreamIndex',), ('Codec',), ('Language',), ('DisplayTitle',), ('External',)]:
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

            self.cursor.execute("SELECT name FROM pragma_table_info('Whitelist')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',), ('EmbyType',), ('KodiDB',), ('KodiDBs',)]:
                xbmc.log(f"EMBY.database.emby_db: Whitelist invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('LastIncrementalSync')")
            Cols = self.cursor.fetchall()

            if Cols != [('Date',)]:
                xbmc.log(f"EMBY.database.emby_db: LastIncrementalSync invalid: {Cols}", 3) # LOGERROR
                Invalid = True

            self.cursor.execute("SELECT name FROM pragma_table_info('PendingSync')")
            Cols = self.cursor.fetchall()

            if Cols != [('EmbyLibraryId',), ('EmbyLibraryName',), ('EmbyType',), ('KodiDB',), ('KodiDBs',)]:
                xbmc.log(f"EMBY.database.emby_db: PendingSync invalid: {Cols}", 3) # LOGERROR
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
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_VideoStreams_EmbyId_MediaIndex on VideoStreams (EmbyId, MediaIndex)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_AudioStreams_EmbyId_MediaIndex on AudioStreams (EmbyId, MediaIndex)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Subtitles_EmbyId_MediaIndex on Subtitles (EmbyId, MediaIndex)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Series_EmbyPresentationKey on Series (EmbyPresentationKey)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Season_EmbyPresentationKey on Season (EmbyPresentationKey)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Movie_EmbyFolder on Movie (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_EmbyFolder on Video (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Episode_EmbyFolder on Episode (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_MusicVideo_EmbyFolder on MusicVideo (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Audio_EmbyFolder on Audio (EmbyFolder)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Video_EmbyParentId on Video (EmbyParentId)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_Tag_Memo on Tag (Memo)")

    def delete_Index(self):
        self.cursor.execute("DROP INDEX IF EXISTS idx_MediaSources_EmbyId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_MediaSources_Path")
        self.cursor.execute("DROP INDEX IF EXISTS idx_VideoStreams_EmbyId_MediaIndex")
        self.cursor.execute("DROP INDEX IF EXISTS idx_AudioStreams_EmbyId_MediaIndex")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Subtitles_EmbyId_MediaIndex")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Series_EmbyPresentationKey")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Season_EmbyPresentationKey")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Movie_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Episode_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_MusicVideo_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Audio_EmbyFolder")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Video_EmbyParentId")
        self.cursor.execute("DROP INDEX IF EXISTS idx_Tag_Memo")

    # Whitelist
    def get_Whitelist(self):
        self.cursor.execute("SELECT * FROM Whitelist")
        return self.cursor.fetchall()

    def add_Whitelist(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs):
        self.cursor.execute("INSERT OR REPLACE INTO Whitelist (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs) VALUES (?, ?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs))

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
    def add_PendingSync(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs):
        self.cursor.execute("INSERT INTO PendingSync (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs) VALUES (?, ?, ?, ?, ?)", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB, KodiDBs))

    def get_PendingSync(self):
        self.cursor.execute("SELECT * FROM PendingSync")
        return self.cursor.fetchall()

    def remove_PendingSync(self, EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB):
        self.cursor.execute("DELETE FROM PendingSync WHERE EmbyLibraryId = ? AND EmbyLibraryName = ? AND EmbyType = ? AND KodiDB = ?", (EmbyLibraryId, EmbyLibraryName, EmbyType, KodiDB))

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
            Data[Item[2]][Item[1]][Counter[Item[2]][Item[1]]] = str(Item[0])
            Counter[Item[2]][Item[1]] += 1

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
    def get_Subtitles(self, EmbyId, MediaIndex):
        self.cursor.execute("SELECT * FROM Subtitles WHERE EmbyId = ? AND MediaIndex = ?", (EmbyId, MediaIndex))
        return self.cursor.fetchall()

    # MediaSources
    def get_FileSize(self, EmbyId, MediaIndex):
        self.cursor.execute("SELECT Size FROM MediaSources WHERE EmbyId = ? AND MediaIndex = ?", (EmbyId, MediaIndex))
        FileSize = self.cursor.fetchone()

        if FileSize:
            return FileSize[0]

        return 0

    def get_mediasource(self, EmbyId):
        self.cursor.execute("SELECT * FROM MediaSources WHERE EmbyId = ?", (EmbyId,))
        return self.cursor.fetchall()

    def get_mediasource_EmbyID_by_path(self, Path):
        self.cursor.execute("SELECT EmbyId FROM MediaSources WHERE Path LIKE ?", (f"%{Path}",))
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
    def add_reference_audio(self, EmbyId, EmbyLibraryId, KodiIds, EmbyFavourite, EmbyFolder, KodiPathId, EmbyLibraryIds):
        self.cursor.execute("INSERT OR REPLACE INTO Audio (EmbyId, KodiId, EmbyFavourite, EmbyFolder, KodiPathId, LibraryIds) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, ",".join(KodiIds), EmbyFavourite, EmbyFolder, KodiPathId, ",".join(EmbyLibraryIds)))
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

    def add_reference_episode(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, IntroStart, IntroEnd):
        self.cursor.execute("INSERT OR REPLACE INTO Episode (EmbyId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, IntroStart, IntroEnd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiFileId, KodiParentId, EmbyPresentationKey, EmbyFolder, KodiPathId, IntroStart, IntroEnd))
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

    def add_reference_video(self, EmbyId, EmbyLibraryId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId):
        self.cursor.execute("INSERT OR REPLACE INTO Video (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (EmbyId, KodiId, EmbyFavourite, KodiFileId, EmbyParentId, EmbyPresentationKey, EmbyFolder, KodiPathId))
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

    def update_reference_episode(self, EmbyId, EmbyFavourite, KodiParentId, EmbyPresentationKey, IntroStart, IntroEnd, EmbyLibraryId):
        self.cursor.execute("UPDATE Episode SET EmbyFavourite = ?, KodiParentId = ?, EmbyPresentationKey = ?, IntroStart = ?, IntroEnd = ? WHERE EmbyId = ?", (EmbyFavourite, KodiParentId, EmbyPresentationKey, IntroStart, IntroEnd, EmbyId))
        self.cursor.execute("INSERT OR IGNORE INTO EmbyLibraryMapping (EmbyLibraryId, EmbyId) VALUES (?, ?)", (EmbyLibraryId, EmbyId))

    def update_reference_musicgenre(self, EmbyId, EmbyFavourite, EmbyArtwork, EmbyLibraryId):
        self.cursor.execute("UPDATE MusicGenre SET EmbyFavourite = ?, EmbyArtwork = ? WHERE EmbyId = ?", (EmbyFavourite, EmbyArtwork, EmbyId))
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

        for TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey in TablesWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey:
            self.cursor.execute(f"SELECT KodiId, KodiFileId, EmbyPresentationKey FROM {TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                RemoveItems += ((EmbyId, Data[0], Data[1], TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey, Data[2]),)
                ItemFound = True
                break

        if not ItemFound:
            for TableWith_KodiId_EmbyPresentationKey in TablesWith_KodiId_EmbyPresentationKey:
                self.cursor.execute(f"SELECT KodiId, EmbyPresentationKey FROM {TableWith_KodiId_EmbyPresentationKey} WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    RemoveItems += ((EmbyId, Data[0], None, TableWith_KodiId_EmbyPresentationKey, Data[1]),)
                    ItemFound = True
                    break

        if not ItemFound:
            for TableWith_KodiId in TablesWith_KodiId:
                self.cursor.execute(f"SELECT KodiId FROM {TableWith_KodiId} WHERE EmbyId = ?", (EmbyId,))
                Data = self.cursor.fetchone()

                if Data:
                    RemoveItems += ((EmbyId, Data[0], None, TableWith_KodiId, None),)
                    ItemFound = True
                    break

        if not ItemFound: # Folder
            self.cursor.execute("SELECT EmbyFolder FROM Folder WHERE EmbyId = ?", (EmbyId,))
            EmbyFolder = self.cursor.fetchone()

            if EmbyFolder:
                RemoveItems += ((EmbyId, None, None, "Folder", None),)

                # Delete items by same folder
                if not EmbyLibraryId:
                    for TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey in TablesWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey:
                        self.cursor.execute(f"SELECT EmbyId, KodiId, KodiFileId, EmbyPresentationKey FROM {TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey} WHERE EmbyFolder LIKE ?", (f"{EmbyFolder[0]}%",))
                        Datas = self.cursor.fetchall()

                        for Data in Datas:
                            RemoveItems += ((Data[0], Data[1], Data[2], TableWith_KodiId_KodiFileId_EmbyFolder_EmbyPresentationKey, Data[3]),)

                    for TableWith_KodiId_EmbyFolder in TablesWith_KodiId_EmbyFolder:
                        self.cursor.execute(f"SELECT EmbyId, KodiId FROM {TableWith_KodiId_EmbyFolder} WHERE EmbyFolder LIKE ?", (f"{EmbyFolder[0]}%",))
                        Datas = self.cursor.fetchall()

                        for Data in Datas:
                            RemoveItems += ((Data[0], Data[1], None, TableWith_KodiId_EmbyFolder, None),)

        RemoveItems = set(RemoveItems) # Filter doubles
        return RemoveItems

    def remove_library_items(self, EmbyLibraryId):
        self.cursor.execute("SELECT EmbyId, EmbyLibraryId FROM EmbyLibraryMapping WHERE EmbyLibraryId = ?", (EmbyLibraryId,))
        Items = self.cursor.fetchall()
        self.cursor.executemany("INSERT OR REPLACE INTO RemoveItems (EmbyId, EmbyLibraryId) VALUES (?, ?)", Items)

    def remove_library_items_person(self):
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

    def get_item_by_KodiId_EmbyType(self, KodiId, EmbyType):
        self.cursor.execute(f"SELECT * FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def remove_item_by_KodiId(self, KodiId, EmbyType, EmbyLibraryId):
        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            self.remove_item(Data[0], EmbyType, EmbyLibraryId)

    def get_EmbyId_by_KodiId_KodiType(self, KodiId, KodiType):
        if KodiType not in utils.KodiTypeMapping:
            xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_EmbyId_EmbyFavourite_by_KodiId_KodiType): {KodiType}", 3) # LOGERROR
            return None

        self.cursor.execute(f"SELECT EmbyId FROM {utils.KodiTypeMapping[KodiType]} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_EmbyId_EmbyFavourite_by_KodiId_KodiType(self, KodiId, KodiType):
        if KodiType not in utils.KodiTypeMapping:
            xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_EmbyId_EmbyFavourite_by_KodiId_KodiType): {KodiType}", 3) # LOGERROR
            return None, None

        self.cursor.execute(f"SELECT EmbyId, EmbyFavourite FROM {utils.KodiTypeMapping[KodiType]} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0], Data[1]

        return None, None

    def get_EmbyId_EmbyType_IntroStartPosTicks_IntroEndPosTicks_by_KodiId_KodiType(self, KodiId, KodiType):
        if KodiType not in utils.KodiTypeMapping:
            xbmc.log(f"EMBY.database.emby_db: KodiType invalid (get_EmbyId_EmbyType_IntroStartPosTicks_IntroEndPosTicks_by_KodiId_KodiType): {KodiType}", 3) # LOGERROR
            return None, None, None, None

        EmbyType = utils.KodiTypeMapping[KodiType]

        if KodiType == "episode":
            self.cursor.execute("SELECT EmbyId, IntroStart, IntroEnd FROM Episode WHERE KodiId = ?", (KodiId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0], EmbyType, Data[1], Data[2]

            return None, None, None, None

        self.cursor.execute(f"SELECT EmbyId FROM {EmbyType} WHERE KodiId = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0], EmbyType, None, None

        return None, None, None, None

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

    def get_FavoriteInfos(self, Table):
        if Table == "Person":
            self.cursor.execute("SELECT EmbyFavourite, KodiId FROM Person")
        else:
            self.cursor.execute(f"SELECT EmbyFavourite, KodiId, EmbyArtwork FROM {Table}")

        return self.cursor.fetchall()

    def get_item_exists_by_id(self, EmbyId, EmbyType):
        self.cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {EmbyType} WHERE EmbyId = ?)", (EmbyId, ))
        return self.cursor.fetchone()[0]

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
        self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyPresentationKey = ?", (EmbyPresentationKey,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

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

    def get_KodiId_by_EmbyId(self, EmbyId):
        for TableWith_KodiId in TablesWith_KodiId_total:
            self.cursor.execute(f"SELECT KodiId FROM {TableWith_KodiId} WHERE EmbyId = ?", (EmbyId,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0], utils.EmbyTypeMapping[TableWith_KodiId]

        return None, None

    def get_KodiId_by_EmbyId_EmbyType(self, EmbyId, EmbyType):
        self.cursor.execute(f"SELECT KodiId FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_KodiId_by_EmbyId_and_LibraryId(self, EmbyId, EmbyType, EmbyLibraryId, EmbyServer):
        self.cursor.execute(f"SELECT KodiId, LibraryIds FROM {EmbyType} WHERE EmbyId = ?", (EmbyId,))
        Data = self.cursor.fetchone()

        if Data:
            if EmbyType == "MusicArtist":
                _, KodiDB = EmbyServer.library.WhitelistUnique[EmbyLibraryId]

                if KodiDB == "video,music": # mixed content
                    return None, None

                KodiIds = Data[0].split(";")

                if KodiDB == "video":
                    return KodiIds[0], "video"

                return KodiIds[1], "music"

            if EmbyType in ("MusicAlbum", "Audio"):
                LibraryIndex = Data[1].index(EmbyLibraryId)
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

    def add_streamdata(self, EmbyId, Streams):
        for Stream in Streams:
            self.cursor.execute("INSERT OR REPLACE INTO MediaSources (EmbyId, MediaIndex, MediaSourceId, Path, Name, Size) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], Stream['Id'], Stream['Path'], Stream['Name'], Stream['Size']))

            for VideoStream in Stream['Video']:
                self.cursor.execute("INSERT OR REPLACE INTO VideoStreams (EmbyId, MediaIndex, StreamIndex, Codec, BitRate) VALUES (?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], VideoStream['Index'], VideoStream['codec'], VideoStream['BitRate']))

            for AudioStream in Stream['Audio']:
                self.cursor.execute("INSERT OR REPLACE INTO AudioStreams (EmbyId, MediaIndex, StreamIndex, DisplayTitle, Codec, BitRate) VALUES (?, ?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], AudioStream['Index'], AudioStream['DisplayTitle'], AudioStream['codec'], AudioStream['BitRate']))

            for SubtitleStream in Stream['Subtitle']:
                self.cursor.execute("INSERT OR REPLACE INTO Subtitles (EmbyId, MediaIndex, StreamIndex, Codec, Language, DisplayTitle, External) VALUES (?, ?, ?, ?, ?, ?, ?)", (EmbyId, Stream['Index'], SubtitleStream['Index'], SubtitleStream['codec'], SubtitleStream['language'], SubtitleStream['DisplayTitle'], SubtitleStream['external']))

    def add_multiversion(self, item, EmbyType, API, SQLs):
        if len(item['MediaSources']) > 1:
            xbmc.log(f"EMBY.database.emby_db: Multiversion video detected: {item['Id']}", 0) # LOGDEBUG

            for DataSource in item['MediaSources']:
                ItemReferenced = API.get_Item(DataSource['Id'], [EmbyType], False, False) # Get Emby itemId from DataSource['Id'] -> Mediasource id

                if not ItemReferenced:  # Server restarted
                    xbmc.log(f"EMBY.database.emby_db: Multiversion video detected, referenced item not found: {DataSource['Id']}", 0) # LOGDEBUG
                    continue

                if item['Id'] != ItemReferenced['Id']:
                    ExistingItem = self.get_item_by_id(ItemReferenced['Id'], None)

                    if ExistingItem:
                        ExistingItem = {"KodiFileId": ExistingItem[3], "KodiItemId": ExistingItem[1]}

                        # Remove old Kodi video-db references
                        if str(item['KodiItemId']) != str(ExistingItem['KodiItemId']) and str(item['KodiFileId']) != str(ExistingItem['KodiFileId']):
                            common.delete_ContentItemReferences(ExistingItem, SQLs, utils.EmbyTypeMapping[EmbyType])

                            if SQLs['video']: # video else specials
                                if EmbyType == "Episode":
                                    SQLs['video'].delete_episode(ExistingItem['KodiItemId'], ExistingItem['KodiFileId'])
                                elif EmbyType in ("Movie", "Video"):
                                    SQLs['video'].delete_movie(ExistingItem['KodiItemId'], ExistingItem['KodiFileId'])
                                elif EmbyType == "MusicVideo":
                                    SQLs['video'].delete_musicvideos(ExistingItem['KodiItemId'], ExistingItem['KodiFileId'])

                    # Add references
                    if not "ParentId" in item:
                        item['ParentId'] = None

                    if EmbyType == "Episode":
                        self.add_reference_episode(ItemReferenced['Id'], item['LibraryId'], item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiFileId'], item['KodiParentId'], item['PresentationUniqueKey'], item['Path'], item['KodiPathId'], item['IntroStartPositionTicks'], item['IntroEndPositionTicks'])
                    elif EmbyType in ("Movie", "MusicVideo"):
                        self.add_reference_movie_musicvideo(ItemReferenced['Id'], item['LibraryId'], item['Type'], item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiFileId'], item['PresentationUniqueKey'], item['Path'], item['KodiPathId'])
                    elif EmbyType == "Video":
                        self.add_reference_video(ItemReferenced['Id'], item['LibraryId'], item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiFileId'], item['ParentId'], item['PresentationUniqueKey'], item['Path'], item['KodiPathId'])

                    self.add_streamdata(ItemReferenced['Id'], item['Streams'])

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

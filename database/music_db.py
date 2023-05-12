import xbmc
from helper import utils
from . import common_db


class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def add_Index(self):
        # Index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_strType on album (strType)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_dateadded on album (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_dateadded on song (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_comment_strGenres on song (comment, strGenres)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist_strDisambiguation on artist (strDisambiguation)")

    # Make sure rescan and kodi db set
    def disable_rescan(self, Timestamp):
        self.cursor.execute("DELETE FROM versiontagscan")
        self.cursor.execute("INSERT OR REPLACE INTO versiontagscan(idVersion, iNeedsScan, lastscanned, artistlinksupdated, genresupdated) VALUES (?, ?, ?, ?, ?)", (str(utils.DatabaseFiles['music-version']), "0", Timestamp, Timestamp, Timestamp))

    def add_role(self):
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (1, "artist"))
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (2, "composer"))

    def link_album_artist(self, KodiId, KodiAlbumId, ArtistName, Index):
        self.cursor.execute("INSERT INTO album_artist(idArtist, idAlbum, strArtist, iOrder) VALUES (?, ?, ?, ?)", (KodiId, KodiAlbumId, ArtistName, Index))

    def get_ArtistSortname(self, KodiArtistId):
        self.cursor.execute("SELECT strSortName FROM artist WHERE idArtist = ? ", (KodiArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return ""

    def create_entry_artist(self):
        self.cursor.execute("SELECT coalesce(max(idArtist), 0) FROM artist")
        return self.cursor.fetchone()[0] + 1

    def add_artist(self, KodiItemId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name):
        while MusicbrainzId != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name))
                return
            except Exception as error:
                MusicbrainzId = errorhandler_MusicBrainzID(ArtistName, MusicbrainzId, error)

    def update_artist(self, KodiItemId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded):
        while MusicbrainzId != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE artist SET strArtist = ?, strMusicBrainzArtistID = ?, strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ? WHERE idArtist = ?", (ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, KodiItemId))
                return
            except Exception as error:
                MusicbrainzId = errorhandler_MusicBrainzID(ArtistName, MusicbrainzId, error)

    def get_artist_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM artist WHERE idArtist = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "artist")
        return {'mediatype': "artist", "dbid": kodi_id, 'title': ItemData[1], 'artist': ItemData[1],'musicbrainzartistid': ItemData[2], 'genre': ItemData[9], 'comment': ItemData[13], 'path': f"musicdb://artists/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    def create_entry_album(self):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        return self.cursor.fetchone()[0] + 1

    def add_album(self, KodiItemId, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name):
        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, iUserrating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType, strReleaseStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, int(RunTime), ArtistSort, LibraryId_Name, ""))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def update_album(self, KodiItemId, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort):
        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strReleaseGroupMBID = ?, strReleaseType = ?, strArtistDisp = ?, strReleaseDate = ?, strOrigReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ?, strReleaseStatus = ? WHERE idAlbum = ?", (Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, int(RunTime), ArtistSort, "", KodiItemId))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def get_album_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM album WHERE idAlbum = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "album")
        Artwork += self.get_artwork(kodi_id, "single")
        return {'mediatype': "album", "dbid": kodi_id, 'title': ItemData[1], 'musicbrainzalbumid': ItemData[2], 'artist': ItemData[4], 'albumartists': ItemData[4], 'genre': ItemData[6], 'releasedate': ItemData[7], 'year': utils.convert_to_local(ItemData[7], False, True),'comment': ItemData[13], 'playcount': ItemData[27], 'lastplayed': ItemData[30], 'duration': ItemData[31], 'path': f"musicdb://albums/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    def create_entry_song(self):
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        return self.cursor.fetchone()[0] + 1

    def add_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId_Name):
        BitRate, SampleRate, Channels, PlayCount, Comment = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort, strDiscSubtitle, iStartOffset, iEndOffset, mood, strReplayGain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, AlbumId, KodiPathId, Artist, Genre, Title, Index, int(Runtime), Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, "", 0, 0, "", ""))
                return
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

    def update_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId_Name):
        BitRate, SampleRate, Channels, PlayCount, Comment = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE song SET idAlbum = ?, idPath = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFileName = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ?, strDiscSubtitle = ?, iStartOffset = ?, iEndOffset = ?, mood = ?, strReplayGain = ? WHERE idSong = ?", (AlbumId, KodiPathId, Artist, Genre, Title, Index, int(Runtime), Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, "", 0, 0, "", "", KodiItemId))
                return
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

    def link_song_artist(self, idArtist, idSong, idRole, iOrder, strArtist):
        self.cursor.execute("INSERT INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist) VALUES (?, ?, ?, ?, ?)", (idArtist, idSong, idRole, iOrder, strArtist))

    def delete_link_song_artist(self, SongId):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (SongId,))

    def rate_song(self, iTimesPlayed, lastplayed, rating, idSong):
        self.cursor.execute("UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?", (iTimesPlayed, lastplayed, rating, idSong))

    def get_song_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM songview WHERE idSong = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "song")
        Track = ItemData[5] % 65536
        Disc = int(int(ItemData[5]) / 65536)
        return {'mediatype': "song", "dbid": kodi_id, 'artist': ItemData[1], 'genre': ItemData[3], 'title': ItemData[4], 'tracknumber': Track, 'discnumber': Disc, 'duration': ItemData[6], 'releasedate': ItemData[7], 'year': utils.convert_to_local(ItemData[7], False, True), 'musicbrainztrackid': ItemData[11], 'playcount': ItemData[12], 'comment': ItemData[19], 'album': ItemData[21], 'path': ItemData[22], 'albumartists': ItemData[26], 'pathandfilename': f"{ItemData[22]}{ItemData[10]}", 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'artwork': Artwork}

    # Add genres, but delete current genres first
    def update_genres_song(self, kodi_id, genres):
        self.cursor.execute("DELETE FROM song_genre WHERE idSong = ?", (kodi_id,))

        for index, genre in enumerate(genres):
            genre_id = self.get_add_genre(genre)
            self.cursor.execute("INSERT OR REPLACE INTO song_genre(idGenre, idSong, iOrder) VALUES (?, ?, ?)", (genre_id, kodi_id, index))

    def get_add_genre(self, strGenre):
        self.cursor.execute("SELECT idGenre FROM genre WHERE strGenre = ? ", (strGenre,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idGenre), 0) FROM genre")
        genre_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO genre(idGenre, strGenre) VALUES (?, ?)", (genre_id, strGenre))
        return genre_id

    def get_genre(self, LibraryId):
        Genres = []
        self.cursor.execute("SELECT strGenres FROM song WHERE comment LIKE ? COLLATE NOCASE GROUP BY strGenres COLLATE NOCASE", (f"%%{LibraryId}",))
        strGenres = self.cursor.fetchall()

        for strGenre in strGenres:
            SongGenres = strGenre[0].split("/")

            for SongGenre in SongGenres:
                Genres.append(SongGenre.strip())

        Genres = list(dict.fromkeys(Genres)) # filter doubles
        Genres = sorted(Genres, reverse=False, key=str.lower)
        return Genres

    def delete_artist(self, ArtistId):
        self.common.delete_artwork(ArtistId, "artist")
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (ArtistId,))

    def delete_album(self, idAlbum):
        self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (idAlbum,))
        self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
        self.common.delete_artwork(idAlbum, "album")
        self.common.delete_artwork(idAlbum, "single")

    def delete_album_stacked(self, idAlbum):
        DeleteEmbyItems = []
        self.cursor.execute("SELECT idArtist FROM album_artist WHERE idAlbum = ?", (idAlbum,))
        ArtistIds = self.cursor.fetchall()
        self.delete_album(idAlbum)

        # Remove empty albumartists
        for ArtistId in ArtistIds:
            self.cursor.execute("SELECT idAlbum FROM album_artist WHERE idArtist = ?", (ArtistId[0],))
            idAlbum = self.cursor.fetchone()

            if not idAlbum:
                self.delete_artist(ArtistId[0])
                DeleteEmbyItems.append(("artist", ArtistId[0]))

        return DeleteEmbyItems

    def delete_song(self, idSong):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (idSong,))
        self.cursor.execute("DELETE FROM song WHERE idSong = ?", (idSong,))
        self.common.delete_artwork(idSong, "song")

    def delete_song_stacked(self, idSong):
        DeleteEmbyItems = []
        self.cursor.execute("SELECT idArtist FROM song_artist WHERE idSong = ?", (idSong,))
        ArtistIds = self.cursor.fetchall()
        self.cursor.execute("SELECT idAlbum FROM song WHERE idSong = ?", (idSong,))
        AlbumId = self.cursor.fetchone()
        self.delete_song(idSong)

        # Remove empty songartists
        for ArtistId in ArtistIds:
            self.cursor.execute("SELECT idSong FROM song_artist WHERE idArtist = ?", (ArtistId[0],))
            idSong = self.cursor.fetchone()

            if not idSong:
                self.delete_artist(ArtistId[0])
                DeleteEmbyItems.append(("artist", ArtistId[0]))

        # Remove empty albums
        if AlbumId:
            self.cursor.execute("SELECT idSong FROM song WHERE idAlbum = ?", (AlbumId[0],))
            idSong = self.cursor.fetchone()

            if not idSong:
                self.delete_album(AlbumId[0])
                DeleteEmbyItems.append(("album", AlbumId[0]))

        return DeleteEmbyItems
    # Path
    def toggle_path(self, OldPath, NewPath):
        self.cursor.execute("SELECT idPath, strPath FROM path")
        Pathes = self.cursor.fetchall()

        for Path in Pathes:
            if Path[1].startswith(OldPath):
                PathMod = Path[1].replace(OldPath, NewPath)
                self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (PathMod, Path[0]))

    def get_add_path(self, strPath):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (strPath,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        path_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO path(idPath, strPath) VALUES (?, ?)", (path_id, strPath))
        return path_id

    # artwork
    def get_artwork(self, KodiId, ContentType):
        Artwork = {}
        self.cursor.execute("SELECT * FROM art WHERE media_id = ? and media_type = ?", (KodiId, ContentType))
        ArtworksData = self.cursor.fetchall()

        for ArtworkData in ArtworksData:
            Artwork[ArtworkData[3]] = ArtworkData[4]

        return Artwork

def set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name):
    Comment = f"{Comment}\n{LibraryId_Name}"

    if not PlayCount:
        PlayCount = 0

    if not BitRate:
        xbmc.log(f"EMBY.database.music_db: No bitrate info (add_song): {Artist} / {Title}", 2) # LOGWARNING
        BitRate = 0

    if not SampleRate:
        xbmc.log(f"EMBY.database.music_db: No bitrate info (add_song): {Artist} / {Title}", 2) # LOGWARNING
        SampleRate = 0

    if not Channels:
        xbmc.log(f"EMBY.database.music_db: No bitrate info (add_song): {Artist} / {Title}", 2) # LOGWARNING
        Channels = 0

    return BitRate, SampleRate, Channels, PlayCount, Comment

def errorhandler_MusicBrainzID(Title, MusicBrainzID, error):
    error = str(error)
    xbmc.log(f"EMBY.database.music_db: {error}", 3) # LOGERROR

    if "MusicBrainz" in error:  # Duplicate musicbrainz
        xbmc.log(f"EMBY.database.music_db: Duplicate MusicBrainzID detected: {Title} / {MusicBrainzID}", 2) # LOGWARNING
        MusicBrainzID += " "
        return MusicBrainzID

    xbmc.log(f"EMBY.database.music_db: Unknown error: {Title} / {MusicBrainzID}", 3) # LOGERROR
    return "UNKNOWN ERROR"

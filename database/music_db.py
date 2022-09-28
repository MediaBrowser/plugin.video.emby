from helper import utils, loghandler
from . import common_db

LOG = loghandler.LOG('EMBY.database.music_db')


class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def add_Index(self):
        # Index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_mediatype on art (media_type)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_strType on album (strType)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_dateadded on album (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_dateadded on song (dateAdded)")
        self.cursor.execute("DROP INDEX IF EXISTS idx_song_comment")
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
        MetaData = {'mediatype': "artist", "dbid": kodi_id, 'title': ItemData[1], 'musicbrainzartistid': ItemData[2], 'genre': ItemData[9], 'comment': ItemData[13]}
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true'}
        return "musicdb://artists/%s/" % kodi_id, MetaData, Properties

    def create_entry_album(self):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        return self.cursor.fetchone()[0] + 1

    def add_album(self, KodiItemId, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name):
        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, iUserrating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType, strReleaseStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name, ""))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def update_album(self, KodiItemId, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort):
        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strReleaseGroupMBID = ?, strReleaseType = ?, strArtistDisp = ?, strReleaseDate = ?, strOrigReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ?, strReleaseStatus = ? WHERE idAlbum = ?", (Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, "", KodiItemId))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def get_album_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM album WHERE idAlbum = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()
        MetaData = {'mediatype': "album", "dbid": kodi_id, 'title': ItemData[1], 'musicbrainzalbumid': ItemData[2], 'artist': ItemData[4], 'genre': ItemData[6], 'year': ItemData[7], 'comment': ItemData[13], 'playcount': ItemData[27], 'lastplayed': ItemData[30], 'duration': ItemData[31]}
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[31]}
        return "musicdb://albums/%s/" % kodi_id, MetaData, Properties

    def create_entry_song(self):
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        return self.cursor.fetchone()[0] + 1

    def add_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId_Name):
        BitRate, SampleRate, Channels, PlayCount, Comment = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort, strDiscSubtitle, iStartOffset, iEndOffset, mood, strReplayGain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, "", 0, 0, "", ""))
                return
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

    def update_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId_Name):
        BitRate, SampleRate, Channels, PlayCount, Comment = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE song SET idAlbum = ?, idPath = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFileName = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ?, strDiscSubtitle = ?, iStartOffset = ?, iEndOffset = ?, mood = ?, strReplayGain = ? WHERE idSong = ?", (AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, "", 0, 0, "", "", KodiItemId))
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
        TrackNumber = ItemData[7] % 65536
        DiscNumber = int(int(ItemData[7]) / 65536)
        MetaData = {'mediatype': "song", "dbid": kodi_id, 'artist': ItemData[26], 'genre': ItemData[5], 'title': ItemData[6], 'tracknumber': TrackNumber, 'discnumber': DiscNumber, 'duration': ItemData[8], 'year': ItemData[9], 'musicbrainztrackid': ItemData[13], 'playcount': ItemData[14], 'comment': ItemData[21]}
        Properties = {'IsFolder': 'false', 'IsPlayable': 'true'}
        return "%s%s" % (ItemData[22], ItemData[10]), MetaData, Properties

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
        self.cursor.execute("SELECT strGenres FROM song WHERE comment LIKE ? COLLATE NOCASE GROUP BY strGenres COLLATE NOCASE", ("%%%s" % LibraryId,))
        strGenres = self.cursor.fetchall()

        for strGenre in strGenres:
            SongGenres = strGenre[0].split("/")

            for SongGenre in SongGenres:
                Genres.append(SongGenre.strip())

        Genres = list(dict.fromkeys(Genres)) # filter doubles
        Temp = sorted(Genres, reverse=False, key=str.lower)
        return Temp

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

    def get_add_path(self, strPath):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (strPath,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        path_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO path(idPath, strPath) VALUES (?, ?)", (path_id, strPath))
        return path_id

def set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount, Comment, LibraryId_Name):
    Comment = "%s\n%s" % (Comment, LibraryId_Name)

    if not PlayCount:
        PlayCount = 0

    if not BitRate:
        LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
        BitRate = 0

    if not SampleRate:
        LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
        SampleRate = 0

    if not Channels:
        LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
        Channels = 0

    return BitRate, SampleRate, Channels, PlayCount, Comment

def errorhandler_MusicBrainzID(Title, MusicBrainzID, error):
    error = str(error)
    LOG.error(error)

    if "MusicBrainz" in error:  # Duplicate musicbrainz
        LOG.warning("Duplicate MusicBrainzID detected: %s/%s" % (Title, MusicBrainzID))
        MusicBrainzID += " "
        return MusicBrainzID

    LOG.error("Unknown error: %s/%s" % (Title, MusicBrainzID))
    return "UNKNOWN ERROR"

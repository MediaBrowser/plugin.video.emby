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
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_comment on song (comment)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist_strDisambiguation on artist (strDisambiguation)")

    # Make sure rescan and kodi db set
    def disable_rescan(self, Timestamp):
        self.cursor.execute("DELETE FROM versiontagscan")
        self.cursor.execute("INSERT OR REPLACE INTO versiontagscan(idVersion, iNeedsScan, lastscanned, genresupdated) VALUES (?, ?, ?, ?)", (str(utils.DatabaseFiles['music-version']), "0", Timestamp, Timestamp))

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

        return False

    def create_entry_artist(self):
        self.cursor.execute("SELECT coalesce(max(idArtist), 0) FROM artist")
        return self.cursor.fetchone()[0] + 1

    def add_artist(self, KodiItemId, name, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name):
        while True:
            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, name, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name))
                break
            except:  # Duplicate musicbrainz
                LOG.warning("Duplicate artist detected: %s/%s" % (name, MusicbrainzId))
                MusicbrainzId += " "

    def update_artist(self, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, ArtistId):
        self.cursor.execute("UPDATE artist SET strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ? WHERE idArtist = ?", (Genre, Bio, Thumb, LastScraped, SortName, DateAdded, ArtistId))

    def create_entry_album(self):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        return self.cursor.fetchone()[0] + 1

    def add_album(self, KodiItemId, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, UniqueId, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name):
        while True:
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, iUserrating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType, strReleaseStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, Title, UniqueId, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name, ""))
                break

            except:  # Duplicate musicbrainz
                LOG.warning("Duplicate album detected: %s/%s/%s" % (Title, UniqueId, UniqueIdReleaseGroup))
                UniqueId += " "
                UniqueIdReleaseGroup += " "

    def update_album(self, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, AlbumId, Compilation, Studios, RunTime, ArtistSort):
        self.cursor.execute("UPDATE album SET strArtistDisp = ?, strReleaseDate = ?, strOrigReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, bScrapedMBID = 1, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ? WHERE idAlbum = ?", (Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, AlbumId))

    def create_entry_song(self):
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        return self.cursor.fetchone()[0] + 1

    def add_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort, LibraryId_Name):
        if not PlayCount:
            PlayCount = 0

        Comment = "%s\n%s" % (Comment, LibraryId_Name)

        if not BitRate:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            BitRate = 0

        if not SampleRate:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            SampleRate = 0

        if not Channels:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            Channels = 0

        while True:
            IndexFix = 10000

            for _ in range(10): # try fix track# (max 10 duplicate songs)
                try:
                    self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort, strDiscSubtitle, iStartOffset, iEndOffset, mood, strReplayGain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort, "", 0, 0, "", ""))
                    return
                except Exception as error:  # Duplicate track number for same album
                    LOG.warning("Duplicate song detected (add_song), try fix trackNo: %s/%s" % (Artist, Title))
                    LOG.error(error)
                    IndexFix += 1
                    Index = IndexFix

            # track# not the issue, try fix strMusicBrainzTrackID
            LOG.warning("Duplicate song detected (add_song), fix MusicBrainzTrackID: %s/%s" % (Artist, Title))
            MusicBrainzTrack += " "

    def update_song(self, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort, LibraryId_Name):
        Comment = "%s\n%s" % (Comment, LibraryId_Name)

        if not BitRate:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            BitRate = 0

        if not SampleRate:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            SampleRate = 0

        if not Channels:
            LOG.warning("No bitrate info (add_song): %s/%s" % (Artist, Title))
            Channels = 0

        while True:
            IndexFix = 10000

            for _ in range(10): # try fix track# (max 10 duplicate songs)
                try:
                    self.cursor.execute("UPDATE song SET idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ? WHERE idSong = ?", (AlbumId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort, SongId))
                    return
                except Exception as error:  # Duplicate track number for same album
                    LOG.warning("Duplicate song detected (update_song), try fix trackNo: %s/%s" % (Artist, Title))
                    LOG.error(error)
                    IndexFix += 1
                    Index = IndexFix

            # track# not the issue, try fix strMusicBrainzTrackID
            LOG.warning("Duplicate song detected (update_song), fix MusicBrainzTrackID: %s/%s" % (Artist, Title))
            MusicBrainzTrack += " "

    def link_song_artist(self, idArtist, idSong, idRole, iOrder, strArtist):
        self.cursor.execute("INSERT INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist) VALUES (?, ?, ?, ?, ?)", (idArtist, idSong, idRole, iOrder, strArtist))

    def delete_link_song_artist(self, SongId):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (SongId,))

    def rate_song(self, iTimesPlayed, lastplayed, rating, idSong):
        self.cursor.execute("UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?", (iTimesPlayed, lastplayed, rating, idSong))

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
        self.delete_album_stacked(idAlbum)

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

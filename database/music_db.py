from helper import utils, loghandler
from . import common_db

LOG = loghandler.LOG('EMBY.database.music_db')


class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def clean_music(self):
        self.cursor.execute("SELECT idAlbum FROM album")
        albumids = self.cursor.fetchall()

        for albumid in albumids:
            self.cursor.execute("SELECT idSong FROM song WHERE idAlbum = ?", albumid)
            songid = self.cursor.fetchone()

            if not songid:
                self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", albumid)

        self.cursor.execute("SELECT idArtist FROM artist")
        artistids = self.cursor.fetchall()

        for artistid in artistids:
            self.cursor.execute("SELECT idSong FROM song_artist WHERE idArtist = ?", artistid)
            songid = self.cursor.fetchone()

            if not songid:
                self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", artistid)

    # Make sure rescan and kodi db set
    def disable_rescan(self, Timestamp):
        self.cursor.execute("DELETE FROM versiontagscan")
        self.cursor.execute("INSERT OR REPLACE INTO versiontagscan(idVersion, iNeedsScan, lastscanned, genresupdated) VALUES (?, ?, ?, ?)", (str(utils.DatabaseFiles['music-version']), "0", Timestamp, Timestamp))

    def add_role(self):
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (1, "artist"))

    def link_album_artist(self, KodiId, KodiAlbumId, ArtistName, Index):
        self.cursor.execute("INSERT INTO album_artist(idArtist, idAlbum, strArtist, iOrder) VALUES (?, ?, ?, ?)", (KodiId, KodiAlbumId, ArtistName, Index))

    def add_discography(self, ArtistId, AlbumTitle, Year, MusicBrainzReleaseGroup):
        self.cursor.execute("INSERT INTO discography(idArtist, strAlbum, strYear, strReleaseGroupMBID) VALUES (?, ?, ?, ?)", (ArtistId, AlbumTitle, Year, MusicBrainzReleaseGroup))

    def get_ArtistSortname(self, KodiArtistId):
        self.cursor.execute("SELECT strSortName FROM artist WHERE idArtist = ? ", (KodiArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def add_artist(self, name, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name):
        self.cursor.execute("SELECT coalesce(max(idArtist), 1) FROM artist")
        artist_id = self.cursor.fetchone()[0] + 1

        while True:
            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (artist_id, name, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name))
                break
            except:  # Duplicate musicbrainz
                LOG.warning("Duplicate artist detected: %s/%s" % (name, MusicbrainzId))
                MusicbrainzId += " "

        return artist_id

    def update_artist(self, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, ArtistId):
        self.cursor.execute("UPDATE artist SET strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ? WHERE idArtist = ?", (Genre, Bio, Thumb, LastScraped, SortName, DateAdded, ArtistId))

    def add_album(self, Title, Type, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, UniqueId, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        album_id = self.cursor.fetchone()[0] + 1

        while True:
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, iUserrating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (album_id, Title, UniqueId, UniqueIdReleaseGroup, Type, Artist, Year, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, LibraryId_Name))
                break

            except:  # Duplicate musicbrainz
                LOG.warning("Duplicate album detected: %s/%s/%s" % (Title, UniqueId, UniqueIdReleaseGroup))
                UniqueId += " "
                UniqueIdReleaseGroup += " "

        return album_id

    def update_album(self, Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, AlbumId, Compilation, Studios, RunTime, ArtistSort):
        self.cursor.execute("UPDATE album SET strArtistDisp = ?, strReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, bScrapedMBID = 1, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ? WHERE idAlbum = ?", (Artist, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, AlbumId))

    def add_song(self, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort, LibraryId_Name, Path):
        Comment = "%s\n%s" % (Comment, LibraryId_Name)
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        SongId = self.cursor.fetchone()[0] + 1
        KodiPathId = self.get_add_path(Path)

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
                    self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (SongId, AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrack, ArtistSort))
                    return SongId, KodiPathId
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
    def update_genres(self, kodi_id, genres, media):
        if media == 'album':
            self.cursor.execute("DELETE FROM album_genre WHERE idAlbum = ?", (kodi_id,))

            for genre in genres:
                genre_id = self.get_add_genre(genre)
                self.cursor.execute("INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) VALUES (?, ?)", (genre_id, kodi_id))
        elif media == 'song':
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

    def delete_artist(self, kodi_id, LibraryId):
        self.cursor.execute("SELECT strDisambiguation FROM artist WHERE idArtist = ?", (kodi_id,))
        Data = self.cursor.fetchone()

        if not Data:
            return

        LibraryInfos = Data[0].split(";")
        NewLibraryInfo = ""

        for LibraryInfo in LibraryInfos:
            if LibraryInfo and LibraryId not in LibraryInfo:
                NewLibraryInfo = "%s%s;" % (NewLibraryInfo, LibraryInfo)

        if not NewLibraryInfo:
            self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodi_id,))
        else:
            self.cursor.execute("UPDATE artist SET strDisambiguation = ? WHERE idArtist = ?", (NewLibraryInfo, kodi_id))

    def delete_album(self, kodi_id, LibraryId):
        self.cursor.execute("SELECT strType FROM album WHERE idAlbum = ?", (kodi_id,))
        Data = self.cursor.fetchone()

        if not Data:
            return

        LibraryInfos = Data[0].split(";")
        NewLibraryInfo = ""

        for LibraryInfo in LibraryInfos:
            if LibraryInfo and LibraryId not in LibraryInfo:
                NewLibraryInfo = "%s%s;" % (NewLibraryInfo, LibraryInfo)

        if not NewLibraryInfo:
            self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodi_id,))
        else:
            self.cursor.execute("UPDATE album SET strType = ? WHERE idAlbum = ?", (NewLibraryInfo, kodi_id))

    def delete_song(self, kodi_id):
        self.cursor.execute("DELETE FROM song WHERE idSong = ?", (kodi_id,))

    def get_add_path(self, strPath):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (strPath,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        path_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO path(idPath, strPath) VALUES (?, ?)", (path_id, strPath))
        return path_id

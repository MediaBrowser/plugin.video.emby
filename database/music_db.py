# -*- coding: utf-8 -*-
from helper import utils
from . import common_db

class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common_db = common_db.CommonDatabase(self.cursor)

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
    def disable_rescan(self):
        self.cursor.execute("DELETE FROM versiontagscan")
        self.cursor.execute("INSERT OR REPLACE INTO versiontagscan(idVersion, iNeedsScan) VALUES (?, ?)", (str(utils.DatabaseFiles['music-version']), "0"))

    def create_entry_artist(self):
        self.cursor.execute("SELECT coalesce(max(idArtist), 1) FROM artist")
        return self.cursor.fetchone()[0] + 1

    def create_entry_album(self):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        return self.cursor.fetchone()[0] + 1

    def create_entry_song(self):
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        return self.cursor.fetchone()[0] + 1

    def create_entry_genre(self):
        self.cursor.execute("SELECT coalesce(max(idGenre), 0) FROM genre")
        return self.cursor.fetchone()[0] + 1

    def update_path(self, *args):
        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", args)

    def add_role(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", args)

    def update_artist_name(self, ArtistName, ArtistId, LibraryId_Name):
        self.cursor.execute("SELECT strDisambiguation FROM artist WHERE idArtist = ?", (ArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            LibraryInfo = Data[0]
            LibraryInfo = LibraryInfo.replace("%s;" % LibraryId_Name, "")
            LibraryInfo += "%s;" % LibraryId_Name
            self.cursor.execute("UPDATE artist SET strArtist = ?, strDisambiguation = ? WHERE idArtist = ?", (ArtistName, LibraryInfo, ArtistId))

    def update_artist(self, Genre, Bio, Thumb, Backdrops, LastScraped, SortName, DateAdded, ArtistId, LibraryId_Name):
        self.cursor.execute("SELECT strDisambiguation FROM artist WHERE idArtist = ?", (ArtistId,))
        LibraryInfo = self.cursor.fetchone()[0]
        LibraryInfo = LibraryInfo.replace("%s;" % LibraryId_Name, "")
        LibraryInfo += "%s;" % LibraryId_Name

        if utils.DatabaseFiles['music-version'] >= 82:
            self.cursor.execute("UPDATE artist SET strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ?, strDisambiguation = ? WHERE idArtist = ?", (Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryInfo, ArtistId))
        else:
            if Backdrops:
                Backdrop = Backdrops[0]
            else:
                Backdrop = ""

            self.cursor.execute("UPDATE artist SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?, lastScraped = ?, strSortName = ?, strDisambiguation = ? WHERE idArtist = ?", (Genre, Bio, Thumb, Backdrop, LastScraped, SortName, LibraryInfo, ArtistId))

    def link(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist) VALUES (?, ?, ?)", args)

    def get_discography(self, ArtistId, AlbumTitle):
        self.cursor.execute("SELECT * FROM discography WHERE idArtist = ? AND strAlbum = ?", (ArtistId, AlbumTitle))
        Data = self.cursor.fetchone()

        if Data:
            return Data

        return False

    def add_discography(self, *args):
        self.cursor.execute("INSERT INTO discography(idArtist, strAlbum, strYear) VALUES (?, ?, ?)", args)

    def validate_artist(self, ArtistId, LibraryId_Name):
        LibraryId_Name = "%%%s%%" % LibraryId_Name
        self.cursor.execute("SELECT strDisambiguation FROM artist WHERE idArtist = ? AND strDisambiguation LIKE ?", (ArtistId, LibraryId_Name))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def artist_exists(self, ArtistId):
        self.cursor.execute("SELECT strDisambiguation FROM artist WHERE idArtist = ?", (ArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def validate_album(self, AlbumId, LibraryId_Name):
        LibraryId_Name = "%%%s%%" % LibraryId_Name
        self.cursor.execute("SELECT strType FROM album WHERE idAlbum = ? AND strType LIKE ?", (AlbumId, LibraryId_Name))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def album_exists(self, AlbumId):
        self.cursor.execute("SELECT strType FROM album WHERE idAlbum = ?", (AlbumId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def validate_song(self, SongId, LibraryId_Name):
        LibraryId_Name = "%%%s%%" % LibraryId_Name
        self.cursor.execute("SELECT comment FROM song WHERE idSong = ? AND comment LIKE ?", (SongId, LibraryId_Name))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def song_exists(self, SongId):
        self.cursor.execute("SELECT comment FROM song WHERE idSong = ?", (SongId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    # Get artist or create the entry
    def get_add_artist(self, name, musicbrainz, LibraryId_Name):
        self.cursor.execute("SELECT idArtist, strDisambiguation FROM artist WHERE strArtist = ? ", (name,))
        result = self.cursor.fetchone()

        if result:
            artist_id = result[0]
            LibraryInfo = result[1]

            if LibraryInfo.find(LibraryId_Name) == -1:
                LibraryInfo = LibraryInfo.replace("%s;" % LibraryId_Name, "")
                LibraryInfo += "%s;" % LibraryId_Name
                self.cursor.execute("UPDATE artist SET strDisambiguation = ? WHERE idArtist = ?", (LibraryInfo, artist_id))
        else:
            artist_id = self.create_entry_artist()
            LibraryId_Name += ";"

            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strDisambiguation) VALUES (?, ?, ?, ?)", (artist_id, name, musicbrainz, LibraryId_Name))
            except:  # Duplicate musicbrainz
                musicbrainz = None
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strDisambiguation) VALUES (?, ?, ?, ?)", (artist_id, name, musicbrainz, LibraryId_Name))

        return artist_id

    # Add artist
    def add_artist(self, name, musicbrainz, Genre, Bio, Thumb, Backdrops, LastScraped, SortName, DateAdded, LibraryId_Name):
        artist_id = self.create_entry_artist()
        LibraryId_Name += ";"

        if utils.DatabaseFiles['music-version'] >= 82:
            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (artist_id, name, musicbrainz, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name))
            except:  # Duplicate musicbrainz
                musicbrainz = None
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (artist_id, name, musicbrainz, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId_Name))
        else:
            if Backdrops:
                Backdrop = Backdrops[0]
            else:
                Backdrop = ""

            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, strFanart, lastScraped, strSortName, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (artist_id, name, musicbrainz, Genre, Bio, Thumb, Backdrop, LastScraped, SortName, LibraryId_Name))
            except:  # Duplicate musicbrainz
                musicbrainz = None
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, strFanart, lastScraped, strSortName, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (artist_id, name, musicbrainz, Genre, Bio, Thumb, Backdrop, LastScraped, SortName, LibraryId_Name))

        return artist_id

    def get_artistID(self, name, LibraryId_Name):
        LibraryId_Name = "%%%s%%" % LibraryId_Name
        self.cursor.execute("SELECT idArtist FROM artist WHERE strArtist = ? and strDisambiguation LIKE ?", (name, LibraryId_Name))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return False

    def get_add_album(self, Title, Type, Artists, Year, Genre, Thumb, Rating, LastScraped, DateAdded, LibraryId_Name):
        self.cursor.execute("SELECT idAlbum, strType FROM album WHERE strAlbum = ?  AND strArtistDisp = ? ", (Title, Artists))
        result = self.cursor.fetchone()

        if result:
            album_id = result[0]
            LibraryInfo = result[1]

            if LibraryInfo.find(LibraryId_Name) == -1:
                LibraryInfo = LibraryInfo.replace("%s;" % LibraryId_Name, "")
                LibraryInfo += "%s;" % LibraryId_Name
                self.cursor.execute("UPDATE album SET strType = ? WHERE idAlbum = ?", (LibraryInfo, album_id))
        else:
            album_id = self.create_entry_album()
            LibraryId_Name += ";"

            if utils.DatabaseFiles['music-version'] >= 82:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strImage, iUserrating, lastScraped, dateAdded, strType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (album_id, Title, Type, Artists, Year, Year, Genre, Thumb, Rating, LastScraped, DateAdded, LibraryId_Name))
            else:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strReleaseType, strArtistDisp, iYear, strGenres, strImage, iUserrating, lastScraped, strType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (album_id, Title, Type, Artists, Year, Genre, Thumb, LastScraped, DateAdded, LibraryId_Name))

        return album_id

    def update_album(self, Artists, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, AlbumId, LibraryId_Name):
        self.cursor.execute("SELECT strType FROM album WHERE idAlbum = ?", (AlbumId,))
        LibraryInfo = self.cursor.fetchone()[0]
        LibraryInfo = LibraryInfo.replace("%s;" % LibraryId_Name, "")
        LibraryInfo += "%s;" % LibraryId_Name

        if utils.DatabaseFiles['music-version'] >= 82:
            self.cursor.execute("UPDATE album SET strArtistDisp = ?, strReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, bScrapedMBID = 1, dateAdded = ?, strType = ? WHERE idAlbum = ?", (Artists, Year, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, LibraryInfo, AlbumId))
        else:
            self.cursor.execute("UPDATE album SET strArtistDisp = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, strType = ? WHERE idAlbum = ?", (Artists, Year, Genre, Bio, Thumb, Rating, LastScraped, LibraryInfo, AlbumId))

    def get_album_artist(self, album_id, artists):
        self.cursor.execute("SELECT strArtistDisp FROM album WHERE idAlbum = ?", (album_id,))
        curr_artists = self.cursor.fetchone()

        if curr_artists:
            curr_artists = curr_artists[0]
        else:
            return

        if curr_artists != artists:
            self.cursor.execute("UPDATE album SET strArtistDisp = ? WHERE idAlbum = ?", (artists, album_id))

    def add_song(self, AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, LibraryId_Name, Path):
        Comment = "%s;%s;" % (Comment, LibraryId_Name)
        SongId = self.create_entry_song()
        KodiPathId = self.get_add_path(Path)

        if utils.DatabaseFiles['music-version'] >= 82:
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (SongId, AlbumId, KodiPathId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded))
            except:  # Duplicate track number for same album
                Index = None
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (SongId, AlbumId, KodiPathId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded))
        else:
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, iYear, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (SongId, AlbumId, KodiPathId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded))
            except:  # Duplicate track number for same album
                Index = None
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, iYear, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (SongId, AlbumId, KodiPathId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded))

        return SongId, KodiPathId

    def update_song(self, AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId, LibraryId_Name):
        Comment = "%s;%s" % (Comment, LibraryId_Name)

        if utils.DatabaseFiles['music-version'] >= 82:
            try:
                self.cursor.execute("UPDATE song SET idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strReleaseDate = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ? WHERE idSong = ?", (AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId))
            except:  # Duplicate track number for same album
                Index = None
                self.cursor.execute("UPDATE song SET idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strReleaseDate = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ? WHERE idSong = ?", (AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId))
        else:
            try:
                self.cursor.execute("UPDATE song SET idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ? WHERE idSong = ?", (AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId))
            except:  # Duplicate track number for same album
                Index = None
                self.cursor.execute("UPDATE song SET idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ? WHERE idSong = ?", (AlbumId, Artists, Genre, Title, Index, Runtime, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, SongId))

    def link_song_artist(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist) VALUES (?, ?, ?, ?, ?)", args)

    def delete_link_song_artist(self, SongId):
        self.cursor.execute("SELECT idArtist FROM song_artist WHERE idSong = ?", (SongId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (SongId,))
            self.cursor.execute("SELECT idArtist FROM song_artist WHERE idArtist = ?", Data)
            DataArtist = self.cursor.fetchone()

            if not DataArtist:
                self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", Data)

    def link_song_album(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO albuminfosong(idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration) VALUES (?, ?, ?, ?, ?)", args)

    def rate_song(self, *args):
        self.cursor.execute("UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?", args)

    # Add genres, but delete current genres first
    def add_genres(self, kodi_id, genres, media):
        if media == 'album':
            self.cursor.execute("DELETE FROM album_genre WHERE idAlbum = ?", (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute("INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) VALUES (?, ?)", (genre_id, kodi_id))
        elif media == 'song':
            self.cursor.execute("DELETE FROM song_genre WHERE idSong = ?", (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute("INSERT OR REPLACE INTO song_genre(idGenre, idSong) VALUES (?, ?)", (genre_id, kodi_id))

    def get_genre(self, *args):
        self.cursor.execute("SELECT idGenre FROM genre WHERE strGenre = ? ", args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.add_genre(*args)

    def add_genre(self, *args):
        genre_id = self.create_entry_genre()
        self.cursor.execute("INSERT INTO genre(idGenre, strGenre) VALUES (?, ?)", (genre_id,) + args)
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

    def get_add_path(self, *args):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        path_id = self.common_db.create_entry_path()
        self.cursor.execute("INSERT OR REPLACE INTO path(idPath, strPath) VALUES (?, ?)", (path_id,) + args)
        return path_id

import xbmc
from helper import utils
from . import common_db


class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common_db = common_db.CommonDatabase(cursor)

    def add_Index(self):
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (1, "artist"))
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (2, "composer"))
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_strType on album (strType)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_dateadded on album (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_dateadded on song (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_comment_strGenres on song (comment, strGenres)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist_strDisambiguation on artist (strDisambiguation)")

    # Make sure rescan and kodi db set
    def disable_rescan(self, Timestamp):
        self.cursor.execute("DELETE FROM versiontagscan")
        self.cursor.execute("INSERT OR REPLACE INTO versiontagscan(idVersion, iNeedsScan, lastscanned, artistlinksupdated, genresupdated) VALUES (?, ?, ?, ?, ?)", (str(utils.DatabaseFiles['music-version']), "0", Timestamp, Timestamp, Timestamp))

    def get_ArtistSortname(self, KodiArtistId):
        self.cursor.execute("SELECT strSortName FROM artist WHERE idArtist = ? ", (KodiArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return ""

    # studios
    def add_studio(self, StudioName):
        pass

    def update_studio(self, StudioName, StudioId):
        pass

    # artists
    def add_musicartist_link(self, ArtistId, MediaId, Role, Order, Name):
        self.cursor.execute("INSERT INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist) VALUES (?, ?, ?, ?, ?)", (ArtistId, MediaId, Role, Order, Name))

    def del_musicartist(self, ArtistId):
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM song_artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM album_artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM removed_link")

    def get_Artist(self, ArtistId):
        Artists = False
        self.cursor.execute("SELECT strArtist, strImage FROM artist WHERE idArtist = ?", (ArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT * FROM song_artist WHERE idArtist = ?", (ArtistId,))

            if self.cursor.fetchone():
                Artists = True

            return Data[0], Data[1], Artists

        return "", "", False

    def add_artist(self, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, LibraryId):
        self.cursor.execute("SELECT coalesce(max(idArtist), 0) FROM artist")
        ArtistId = self.cursor.fetchone()[0] + 1

        while MusicbrainzId != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, lastScraped, strSortName, dateAdded, strDisambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (ArtistId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, f"EmbyLibraryId-{LibraryId}"))
                return ArtistId
            except Exception as error:
                MusicbrainzId = errorhandler_MusicBrainzID(ArtistName, MusicbrainzId, error)

    def update_artist(self, KodiItemId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded):
        while MusicbrainzId != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE artist SET strArtist = ?, strMusicBrainzArtistID = ?, strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ? WHERE idArtist = ?", (ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, KodiItemId))
                break
            except Exception as error:
                MusicbrainzId = errorhandler_MusicBrainzID(ArtistName, MusicbrainzId, error)

    def get_artist_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM artist WHERE idArtist = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "artist")
        return {'mediatype': "artist", "dbid": kodi_id, 'title': ItemData[1], 'artist': ItemData[1],'musicbrainzartistid': ItemData[2], 'genre': ItemData[9], 'comment': ItemData[13], 'path': f"musicdb://artists/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    # album
    def add_album(self, Title, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        idAlbum = self.cursor.fetchone()[0] + 1

        if not RunTime:
            RunTime = 0

        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, iUserrating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idAlbum, Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, f"EmbyLibraryId-{LibraryId}"))
                return idAlbum
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def update_album(self, KodiItemId, Title, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort):
        if not RunTime:
            RunTime = 0

        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strReleaseGroupMBID = ?, strReleaseType = ?, strArtistDisp = ?, strReleaseDate = ?, strOrigReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, iUserrating = ?, lastScraped = ?, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ? WHERE idAlbum = ?", (Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, KodiItemId))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def get_album_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM albumview WHERE idAlbum = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "album")

        if not Artwork:
            Artwork = self.get_artwork(kodi_id, "single")

        return {'mediatype': "album", "dbid": kodi_id, 'title': ItemData[1], 'musicbrainzalbumid': ItemData[2], 'artist': ItemData[4], 'albumartists': ItemData[4], 'genre': ItemData[6], 'releasedate': ItemData[7], 'year': utils.convert_to_local(ItemData[7], False, True),'comment': ItemData[13], 'playcount': ItemData[27], 'lastplayed': ItemData[30], 'duration': ItemData[31], 'path': f"musicdb://albums/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    def delete_link_album_artist(self, idAlbum):
        self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
        self.cursor.execute("DELETE FROM removed_link")

    def add_albumartist_link(self, ArtistId, idAlbum, Order, Name):
        self.cursor.execute("INSERT INTO album_artist(idArtist, idAlbum, iOrder, strArtist) VALUES (?, ?, ?, ?)", (ArtistId, idAlbum, Order, Name))

    # song
    def add_song(self, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId):
        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        idSong = self.cursor.fetchone()[0] + 1

        if Comment:
            Comment = f"{Comment}\nEmbyLibraryId-{LibraryId}"
        else:
            Comment = f"EmbyLibraryId-{LibraryId}"

        BitRate, SampleRate, Channels, PlayCount = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, iTimesPlayed, lastplayed, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idSong, AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort))
                return idSong
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

    def update_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId):

        if Comment:
            Comment = f"{Comment}\n{LibraryId}"
        else:
            Comment = f"EmbyLibraryId-{LibraryId}"

        BitRate, SampleRate, Channels, PlayCount = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE song SET idAlbum = ?, idPath = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFileName = ?, iTimesPlayed = ?, lastplayed = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ? WHERE idSong = ?", (AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, PlayCount, DatePlayed, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, KodiItemId))
                return
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

    def delete_link_song_artist(self, SongId):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (SongId,))
        self.cursor.execute("DELETE FROM removed_link")

    def rate_song(self, iTimesPlayed, lastplayed, rating, idSong):
        self.cursor.execute("UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?", (iTimesPlayed, lastplayed, rating, idSong))

    def get_song_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM songview WHERE idSong = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "song")

        if ItemData[5]:
            Track = ItemData[5] % 65536
            Disc = int(int(ItemData[5]) / 65536)
        else:
            Track = None
            Disc = None

        return {'mediatype': "song", "dbid": kodi_id, 'artist': ItemData[1], 'genre': ItemData[3], 'title': ItemData[4], 'tracknumber': Track, 'discnumber': Disc, 'duration': ItemData[6], 'releasedate': ItemData[7], 'year': utils.convert_to_local(ItemData[7], False, True), 'musicbrainztrackid': ItemData[11], 'playcount': ItemData[12], 'comment': ItemData[19], 'Album': ItemData[21], 'path': ItemData[22], 'albumartists': ItemData[26], 'pathandfilename': f"{ItemData[22]}{ItemData[10]}", 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'artwork': Artwork}

    # genres
    def add_genre_link(self, GenreId, MediaId, Order):
        self.cursor.execute("INSERT OR REPLACE INTO song_genre(idGenre, idSong, iOrder) VALUES (?, ?, ?)", (GenreId, MediaId, Order))

    def update_genre(self, GenreName, GenreId):
        GenreNameMod = GenreName

        while True:
            try:
                self.cursor.execute("UPDATE genre SET strGenre = ? WHERE idGenre = ?", (GenreNameMod, GenreId))
                break
            except Exception as Error:
                xbmc.log(f"EMBY.database.music_db: Update genre, Duplicate GenreName detected: {GenreNameMod} / {Error}", 2) # LOGWARNING
                GenreNameMod += " "

    def get_add_genre(self, GenreName):
        self.cursor.execute("SELECT idGenre FROM genre WHERE strGenre = ?", (GenreName,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idGenre), 0) FROM genre")
        GenreId = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO genre(idGenre, strGenre) VALUES (?, ?)", (GenreId, GenreName))
        return GenreId

    def get_genre(self, LibraryId):
        Genres = []
        self.cursor.execute("SELECT strGenres FROM song WHERE comment LIKE ? COLLATE NOCASE GROUP BY strGenres COLLATE NOCASE", (f"%EmbyLibraryId-{LibraryId}",))
        strGenres = self.cursor.fetchall()

        for strGenre in strGenres:
            SongGenres = strGenre[0].split("/")

            for SongGenre in SongGenres:
                Genres.append(SongGenre.strip())

        Genres = list(dict.fromkeys(Genres)) # filter doubles
        Genres = sorted(Genres, reverse=False, key=str.lower)
        return Genres

    def get_Genre_Name(self, GenreId):
        Songs = False
        self.cursor.execute("SELECT strGenre FROM genre WHERE idGenre = ?", (GenreId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM song_genre WHERE idGenre = ?)", (GenreId,))

            if self.cursor.fetchone()[0]:
                Songs = True

            return Data[0], Songs

        return "", False

    def delete_musicgenre_by_Id(self, GenreId):
        self.cursor.execute("DELETE FROM song_genre WHERE idGenre = ?", (GenreId,))
        self.cursor.execute("DELETE FROM genre WHERE idGenre = ?", (GenreId,))

    def delete_artist(self, ArtistId):
        self.common_db.delete_artwork(ArtistId, "artist")
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM removed_link")

    def delete_album(self, idAlbums, LibraryId):
        for idAlbum in idAlbums.split(","):
            if not LibraryId:
                self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (idAlbum,))
                self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
                self.common_db.delete_artwork(idAlbum, "album")
                self.common_db.delete_artwork(idAlbum, "single")
                self.cursor.execute("DELETE FROM removed_link")
            else:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM album WHERE idAlbum = ? AND strType = ?)", (idAlbum, f"EmbyLibraryId-{LibraryId}"))

                if self.cursor.fetchone()[0]:
                    self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (idAlbum,))
                    self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
                    self.common_db.delete_artwork(idAlbum, "album")
                    self.common_db.delete_artwork(idAlbum, "single")
                    self.cursor.execute("DELETE FROM removed_link")
                    return

    def delete_song(self, idSongs, LibraryId):
        for idSong in idSongs.split(","):
            if not LibraryId:
                self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (idSong,))
                self.cursor.execute("DELETE FROM song WHERE idSong = ?", (idSong,))
                self.common_db.delete_artwork(idSong, "song")
                self.cursor.execute("DELETE FROM removed_link")
            else:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM song WHERE idSong = ? AND comment LIKE ?)", (idSong, f"%EmbyLibraryId-{LibraryId}"))

                if self.cursor.fetchone()[0]:
                    self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (idSong,))
                    self.cursor.execute("DELETE FROM song WHERE idSong = ?", (idSong,))
                    self.common_db.delete_artwork(idSong, "song")
                    self.cursor.execute("DELETE FROM removed_link")
                    return

    def delete_song_stacked(self, idSong, LibraryId):
        DeleteEmbyItems = []
        self.cursor.execute("SELECT idArtist FROM song_artist WHERE idSong = ?", (idSong,))
        ArtistIds = self.cursor.fetchall()
        self.cursor.execute("SELECT idAlbum FROM song WHERE idSong = ?", (idSong,))
        AlbumId = self.cursor.fetchone()
        self.delete_song(idSong, LibraryId)

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
                self.delete_album(AlbumId[0], LibraryId)
                DeleteEmbyItems.append(("album", AlbumId[0]))

        return DeleteEmbyItems
    # Path
    def delete_path(self, KodiPath):
        self.cursor.execute("DELETE FROM path WHERE strPath = ?", (KodiPath,))

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

    # Favorite for content
    def get_favoriteData(self, KodiId, ContentType):
        self.cursor.execute("SELECT idPath, strTitle, strFilename FROM song WHERE idSong = ?", (KodiId,))
        ItemData = self.cursor.fetchone()
        Thumbnail = ""

        if ItemData:
            self.cursor.execute("SELECT strPath FROM path WHERE idPath = ?", (ItemData[0],))
            DataPath = self.cursor.fetchone()

            if DataPath:
                self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiId, ContentType, "thumb"))
                ArtworkData = self.cursor.fetchone()

                if ArtworkData:
                    Thumbnail = ArtworkData[0]

                return f"{DataPath[0]}{ItemData[2]}", Thumbnail, ItemData[1]

        return "", "", ""

    # Favorite for subcontent
    def get_FavoriteSubcontent(self, KodiId, ContentType):
        Thumbnail = ""

        self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiId, ContentType, "thumb"))
        ArtworkData = self.cursor.fetchone()

        if ArtworkData:
            Thumbnail = ArtworkData[0]

        if ContentType == "artist":
            self.cursor.execute("SELECT strArtist FROM artist WHERE idArtist = ?", (KodiId,))
        elif ContentType == "album":
            self.cursor.execute("SELECT strAlbum FROM album WHERE idAlbum = ?", (KodiId,))
        else:
            return "", ""

        ItemData = self.cursor.fetchone()

        if ItemData:
            return Thumbnail, ItemData[0]

        return "", ""

def set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, PlayCount):
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

    return BitRate, SampleRate, Channels, PlayCount

def errorhandler_MusicBrainzID(Title, MusicBrainzID, error):
    error = str(error)
    xbmc.log(f"EMBY.database.music_db: {error}", 3) # LOGERROR

    if "MusicBrainz" in error:  # Duplicate musicbrainz
        xbmc.log(f"EMBY.database.music_db: Duplicate MusicBrainzID detected: {Title} / {MusicBrainzID}", 2) # LOGWARNING
        MusicBrainzID += " "
        return MusicBrainzID

    xbmc.log(f"EMBY.database.music_db: Unknown error: {Title} / {MusicBrainzID}", 3) # LOGERROR
    return "UNKNOWN ERROR"

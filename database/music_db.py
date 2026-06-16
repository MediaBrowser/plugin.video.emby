from urllib.parse import quote, unquote
import xbmc
from helper import utils
from . import common_db

class MusicDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common_db = common_db.CommonDatabase(cursor)
        self.Index = {}

    def add_Index(self):
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (1, "artist"))
        self.cursor.execute("INSERT OR REPLACE INTO role(idRole, strRole) VALUES (?, ?)", (2, "composer"))

        try: # xbox issue
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_album_strType'")
            IndexTest = self.cursor.fetchone()

            if not IndexTest:
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_strType on album (strType)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_dateadded on album (dateAdded)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_dateadded on song (dateAdded)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_comment_strGenres on song (comment, strGenres)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist_strDisambiguation on artist (strDisambiguation)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_album_strReleaseType on album (strReleaseType)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_idAlbum_lastplayed_iTimesPlayed on song (idAlbum, lastplayed, iTimesPlayed)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_strMusicBrainzTrackID on song (strMusicBrainzTrackID)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_song_strArtistDisp_strTitle on song (strArtistDisp, strTitle)")
                self.cursor.execute("ANALYZE")
                self.cursor.connection.commit()
                self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        except Exception as Error:
            xbmc.log(f"EMBY.database.music_db: Database add index error: {Error}", 3) # LOGERROR

    def delete_Index(self):
        try: # xbox issue
            self.cursor.execute("DROP INDEX IF EXISTS idx_album_strType")
            self.cursor.execute("DROP INDEX IF EXISTS idx_album_dateadded")
            self.cursor.execute("DROP INDEX IF EXISTS idx_song_dateadded")
            self.cursor.execute("DROP INDEX IF EXISTS idx_song_comment_strGenres")
            self.cursor.execute("DROP INDEX IF EXISTS idx_artist_strDisambiguation")
            self.cursor.execute("DROP INDEX IF EXISTS idx_album_strReleaseType")
            self.cursor.execute("DROP INDEX IF EXISTS idx_song_idAlbum_lastplayed_iTimesPlayed")
            self.cursor.execute("DROP INDEX IF EXISTS idx_song_strMusicBrainzTrackID")
            self.cursor.execute("DROP INDEX IF EXISTS idx_song_strArtistDisp_strTitle")
            self.cursor.execute("ANALYZE")
            self.cursor.connection.commit()
            self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        except Exception as Error:
            xbmc.log(f"EMBY.database.music_db: Database delete index error: {Error}", 3) # LOGERROR

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

    # artists
    def add_musicartist_link(self, ArtistId, MediaId, Role, Order, Name):
        self.cursor.execute("INSERT OR REPLACE INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist) VALUES (?, ?, ?, ?, ?)", (ArtistId, MediaId, Role, Order, Name))

    def del_musicartist(self, ArtistId):
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", (ArtistId, "artist"))
        self.cursor.execute("DELETE FROM song_artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM album_artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM removed_link")

    def get_Artist(self, ArtistId):
        Artists = False
        self.cursor.execute("SELECT strArtist, strImage FROM artist WHERE idArtist = ?", (ArtistId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM song_artist WHERE idArtist = ?)", (ArtistId,))

            if self.cursor.fetchone()[0]:
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

        return None

    def update_artist(self, KodiItemId, ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded):
        while MusicbrainzId != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE artist SET strArtist = ?, strMusicBrainzArtistID = ?, strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?, strSortName = ?, dateAdded = ? WHERE idArtist = ?", (ArtistName, MusicbrainzId, Genre, Bio, Thumb, LastScraped, SortName, DateAdded, KodiItemId))
                break
            except Exception as error:
                MusicbrainzId = errorhandler_MusicBrainzID(ArtistName, MusicbrainzId, error)

    def get_artist_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT strArtist, strMusicBrainzArtistID, strGenres, strBiography FROM artist WHERE idArtist = ?", (kodi_id,))
        ArtistData = self.cursor.fetchone()

        if not ArtistData:
            return {}

        Artwork = self.get_artwork(kodi_id, "artist")
        return {'mediatype': "artist", "dbid": kodi_id, 'title': ArtistData[0], 'artist': ArtistData[0],'musicbrainzartistid': ArtistData[1], 'genre': ArtistData[2], 'comment': ArtistData[3], 'path': f"musicdb://artists/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    def get_artistid_by_songid(self, KodiId):
        self.cursor.execute("SELECT idArtist FROM song_artist WHERE idSong = ? AND idRole = ?", (KodiId, 1))
        ArtistId = self.cursor.fetchone()

        if not ArtistId:
            return None

        return ArtistId[0]

    # album
    def add_album(self, Title, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, CommunityRating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort, LibraryId):
        self.cursor.execute("SELECT coalesce(max(idAlbum), 0) FROM album")
        idAlbum = self.cursor.fetchone()[0] + 1

        if not RunTime:
            RunTime = 0

        if CommunityRating:
            Rating = float(CommunityRating)
        else:
            Rating = 0.0

        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseGroupMBID, strReleaseType, strArtistDisp, strReleaseDate, strOrigReleaseDate, strGenres, strReview, strImage, fRating, lastScraped, dateAdded, bCompilation, strLabel, iAlbumDuration, strArtistSort, strType) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idAlbum, Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, f"EmbyLibraryId-{LibraryId}"))
                return idAlbum
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

        return None

    def update_album(self, KodiItemId, Title, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, CommunityRating, LastScraped, DateAdded, MusicBrainzAlbumID, UniqueIdReleaseGroup, Compilation, Studios, RunTime, ArtistSort):
        if not RunTime:
            RunTime = 0

        if CommunityRating:
            Rating = float(CommunityRating)
        else:
            Rating = 0.0

        while MusicBrainzAlbumID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strReleaseGroupMBID = ?, strReleaseType = ?, strArtistDisp = ?, strReleaseDate = ?, strOrigReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?, fRating = ?, lastScraped = ?, dateAdded = ?, bCompilation = ?, strLabel = ?, iAlbumDuration = ?, strArtistSort = ? WHERE idAlbum = ?", (Title, MusicBrainzAlbumID, UniqueIdReleaseGroup, Type, Artist, ProductionYear, PremiereDate, Genre, Bio, Thumb, Rating, LastScraped, DateAdded, Compilation, Studios, RunTime, ArtistSort, KodiItemId))
                return
            except Exception as error:
                MusicBrainzAlbumID = errorhandler_MusicBrainzID(Title, MusicBrainzAlbumID, error)

    def get_album_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT strAlbum, strMusicBrainzAlbumID, strArtists, strGenres, strReleaseDate, strReview, iTimesPlayed, lastplayed, iAlbumDuration, strOrigReleaseDate, fRating FROM albumview WHERE idAlbum = ?", (kodi_id,))
        AlbumData = self.cursor.fetchone()

        if not AlbumData:
            return {}

        Artwork = self.get_artwork(kodi_id, "album")

        if not Artwork:
            Artwork = self.get_artwork(kodi_id, "single")

        return {'mediatype': "album", "dbid": kodi_id, 'title': AlbumData[0], 'musicbrainzalbumid': AlbumData[1], 'artist': AlbumData[2], 'albumartists': AlbumData[2], 'genre': AlbumData[3], 'releasedate': AlbumData[4], 'year': utils.convert_to_local(AlbumData[4], False, True),'comment': AlbumData[5], 'playcount': AlbumData[6], 'lastplayed': AlbumData[7], 'duration': AlbumData[8], 'path': f"musicdb://albums/{kodi_id}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork, 'CommunityRating': AlbumData[10]}

    def delete_link_album_artist(self, idAlbum):
        self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
        self.cursor.execute("DELETE FROM removed_link")

    def add_albumartist_link(self, ArtistId, idAlbum, Order, Name):
        self.cursor.execute("INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, iOrder, strArtist) VALUES (?, ?, ?, ?)", (ArtistId, idAlbum, Order, Name))

    def get_albumid_by_songid(self, KodiId):
        self.cursor.execute("SELECT idAlbum FROM song WHERE idSong = ?", (KodiId,))
        AlbumId = self.cursor.fetchone()

        if not AlbumId:
            return None

        return AlbumId[0]

    # song
    def get_song_doubles(self):
        Data = {}
        self.cursor.execute("SELECT strTitle, strArtistDisp, strReleaseDate, strMusicBrainzTrackID, idAlbum, iTrack FROM song GROUP BY strTitle, strArtistDisp, strReleaseDate, strMusicBrainzTrackID, idAlbum, iTrack HAVING COUNT(strTitle) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idSong FROM song WHERE strTitle = ? AND strArtistDisp = ? AND strReleaseDate IS ? AND strMusicBrainzTrackID IS ? AND idAlbum = ? AND iTrack IS ?" , (Double[0], Double[1], Double[2], Double[3], Double[4], Double[5]))

            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"SONG_BY_TITLE(m)_ARTIST(m)_DATE(o)_MUSICBRAINZID(o)_ALBUMID(m)_TRACK(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}/{Double[5]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"SONG_BY_TITLE(m)_ARTIST(m)_DATE(o)_MUSICBRAINZID(o)_ALBUMID(m)_TRACK(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}/{Double[5]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def add_song_tag(self, KodiId, Tag): # e.g. for playlists
        self.cursor.execute("SELECT comment FROM song WHERE idSong = ?", (KodiId,))
        Comment = self.cursor.fetchone()

        if Comment:
            Comment = f"{Comment[0]}\n{Tag}"
            self.cursor.execute("UPDATE song SET comment = ? WHERE idSong = ?", (Comment, KodiId))

    def add_song(self, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, CommunityRating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, LibraryId):
        if CommunityRating:
            Rating = float(CommunityRating)
        else:
            Rating = 0.0

        self.cursor.execute("SELECT coalesce(max(idSong), 0) FROM song")
        idSong = self.cursor.fetchone()[0] + 1

        if Comment:
            Comment = f"{Comment}\nEmbyLibraryId-{LibraryId}"
        else:
            Comment = f"EmbyLibraryId-{LibraryId}"

        BitRate, SampleRate, Channels, _ = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, None)

        while MusicBrainzTrackID != "UNKNOWN ERROR":
            try:
                self.cursor.execute("INSERT INTO song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack, iDuration, strOrigReleaseDate, strReleaseDate, strFileName, rating, comment, dateAdded, iBitRate, iSampleRate, iChannels, strMusicBrainzTrackID, strArtistSort) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idSong, AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort))
                return idSong
            except Exception as error:
                MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

        return None

    def update_song(self, KodiItemId, KodiPathId, AlbumId, Artist, Genre, Title, Index, Runtime, PremiereDate, Year, Filename, CommunityRating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, KodiPath, PlaylistId):
        if CommunityRating:
            Rating = float(CommunityRating)
        else:
            Rating = 0.0

        # Get/keep current Tags
        self.cursor.execute("SELECT comment FROM song WHERE idSong = ?", (KodiItemId,))
        CommentCurrent = self.cursor.fetchone()

        if not CommentCurrent:
            xbmc.log(f"EMBY.database.music_db: update_song error: {KodiItemId}", 3) # LOGERROR
            return

        CommentsCurrent = CommentCurrent[0].split("\n")
        EmbyLibraryIds = ()
        EmbyPlaylistIds = ()

        for CommentCurrent in CommentsCurrent:
            if CommentCurrent.startswith("EmbyLibraryId-"):
                Tag = CommentCurrent.split("-")
                EmbyLibraryIds += (Tag[1],)
            elif CommentCurrent.startswith("EmbyPlaylistId-"):
                Tag = CommentCurrent.split("-")
                EmbyPlaylistIds += (Tag[1],)

        if not Comment: # Comment could be None
            Comment = ""

        for EmbyLibraryId in EmbyLibraryIds:
            if Comment:
                Comment += f"\nEmbyLibraryId-{EmbyLibraryId}"
            else:
                Comment += f"EmbyLibraryId-{EmbyLibraryId}"

        for EmbyPlaylistId in EmbyPlaylistIds:
            if Comment:
                Comment += f"\nEmbyPlaylistId-{EmbyPlaylistId}"
            else:
                Comment += f"EmbyPlaylistId-{EmbyPlaylistId}"

        # Update song
        BitRate, SampleRate, Channels, _ = set_metadata_song(Artist, Title, BitRate, SampleRate, Channels, None)

        if EmbyPlaylistIds and not PlaylistId or str(PlaylistId) not in EmbyPlaylistIds: # Do not update existing track numbers when metadata from playlist
            while MusicBrainzTrackID != "UNKNOWN ERROR":
                try:
                    self.cursor.execute("UPDATE song SET idAlbum = ?, idPath = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFileName = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ? WHERE idSong = ?", (AlbumId, KodiPathId, Artist, Genre, Title, Runtime, Year, PremiereDate, Filename, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, KodiItemId))
                    return
                except Exception as error:
                    MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)
        else:
            while MusicBrainzTrackID != "UNKNOWN ERROR":
                try:
                    self.cursor.execute("UPDATE song SET idAlbum = ?, idPath = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, strOrigReleaseDate = ?, strReleaseDate = ?, strFileName = ?, rating = ?, comment = ?, dateAdded = ?, iBitRate = ?, iSampleRate = ?, iChannels = ?, strMusicBrainzTrackID = ?, strArtistSort = ? WHERE idSong = ?", (AlbumId, KodiPathId, Artist, Genre, Title, Index, Runtime, Year, PremiereDate, Filename, Rating, Comment, DateAdded, BitRate, SampleRate, Channels, MusicBrainzTrackID, ArtistSort, KodiItemId))
                    return
                except Exception as error:
                    MusicBrainzTrackID = errorhandler_MusicBrainzID(Title, MusicBrainzTrackID, error)

        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (KodiPath, KodiPathId))

    def delete_link_song_artist(self, SongId):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (SongId,))
        self.cursor.execute("DELETE FROM removed_link")

    def update_song_metadata(self, iTimesPlayed, lastplayed, idSong):
        self.cursor.execute("UPDATE song SET iTimesPlayed = ?, lastplayed = ? WHERE idSong = ?", (iTimesPlayed, lastplayed, idSong))

    def get_song_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT strArtists, strGenres, strTitle, iTrack, iDuration, strReleaseDate, strMusicBrainzTrackID, iTimesPlayed, comment, strAlbum, strPath, strAlbumArtists, strFileName, rating FROM songview WHERE idSong = ?", (kodi_id,))
        SongData = self.cursor.fetchone()

        if not SongData:
            return {}

        Artwork = self.get_artwork(kodi_id, "song")

        if SongData[3]:
            Track = SongData[3] % 65536
            Disc = int(int(SongData[3]) / 65536)
        else:
            Track = None
            Disc = None

        return {'mediatype': "song", "dbid": kodi_id, 'artist': SongData[0], 'genre': SongData[1], 'title': SongData[2], 'tracknumber': Track, 'discnumber': Disc, 'duration': SongData[4], 'releasedate': SongData[5], 'year': utils.convert_to_local(SongData[5], False, True), 'musicbrainztrackid': SongData[6], 'playcount': SongData[7], 'comment': SongData[8], 'Album': SongData[9], 'path': SongData[10], 'albumartists': SongData[11], 'pathandfilename': f"{SongData[10]}{SongData[12]}", 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'artwork': Artwork, 'CommunityRating': SongData[13]}

    def update_song_musicvideo(self, data_list):
        self.cursor.executemany("UPDATE song SET strVideoURL = ? WHERE strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ? OR strMusicBrainzTrackID = ?", [(d[1], d[0], f"{d[0]} ", f"{d[0]}  ", f"{d[0]}   ", f"{d[0]}    ", f"{d[0]}     ", f"{d[0]}      ", f"{d[0]}       ", f"{d[0]}        ", f"{d[0]}         ") for d in data_list if d[0]])
        self.cursor.executemany("UPDATE song SET strVideoURL = ? WHERE strArtistDisp = ? AND strTitle = ? AND strVideoURL IS NULL", [(d[1], d[3], d[2]) for d in data_list])

    def del_song_musicvideo(self):
        self.cursor.execute("UPDATE song SET strVideoURL = NULL")

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
                if utils.DebugLog: xbmc.log(f"EMBY.database.music_db (DEBUG): Update genre, Duplicate GenreName detected: {GenreNameMod} / {Error}", 1) # LOGDEBUG
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
        self.cursor.execute("SELECT strGenres FROM song WHERE comment LIKE ? COLLATE NOCASE GROUP BY strGenres COLLATE NOCASE", (f"%EmbyLibraryId-{LibraryId}%",))
        strGenres = self.cursor.fetchall()

        for strGenre in strGenres:
            SongGenres = strGenre[0].split("/")

            for SongGenre in SongGenres:
                Genres.append(SongGenre.strip())

        Genres = list(dict.fromkeys(Genres)) # filter doubles
        Genres = sorted(Genres, reverse=False, key=str.lower)
        return Genres

    def get_Genre_Name_hasSongs(self, GenreId):
        Songs = False
        self.cursor.execute("SELECT strGenre FROM genre WHERE idGenre = ?", (GenreId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM song_genre WHERE idGenre = ?)", (GenreId,))

            if self.cursor.fetchone()[0]:
                Songs = True

            return Data[0], Songs

        return "", False

    def delete_genre_by_Id(self, GenreId):
        GenreName = ""
        self.cursor.execute("SELECT strGenre FROM genre WHERE idGenre = ?", (GenreId,))
        Data = self.cursor.fetchone()

        if Data:
            GenreName = Data[0]

        self.cursor.execute("DELETE FROM song_genre WHERE idGenre = ?", (GenreId,))
        self.cursor.execute("DELETE FROM genre WHERE idGenre = ?", (GenreId,))
        return GenreName

    def delete_artist(self, ArtistId):
        self.common_db.delete_artwork(ArtistId, "artist")
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (ArtistId,))
        self.cursor.execute("DELETE FROM removed_link")

    def delete_album(self, idAlbum):
        self.cursor.execute("DELETE FROM album_artist WHERE idAlbum = ?", (idAlbum,))
        self.cursor.execute("DELETE FROM album_source WHERE idAlbum = ?", (idAlbum,))
        self.common_db.delete_artwork(idAlbum, "album")
        self.common_db.delete_artwork(idAlbum, "single")
        self.cursor.execute("DELETE FROM removed_link")
        self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (idAlbum,))

    def delete_song(self, idSong):
        self.cursor.execute("DELETE FROM song_artist WHERE idSong = ?", (idSong,))
        self.cursor.execute("DELETE FROM song WHERE idSong = ?", (idSong,))
        self.common_db.delete_artwork(idSong, "song")
        self.cursor.execute("DELETE FROM removed_link")

    # Path
    def delete_path(self, KodiPath):
        self.cursor.execute("DELETE FROM path WHERE strPath = ?", (KodiPath,))

    def get_add_path(self, strPath):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (strPath,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        path_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO path(idPath, strPath) VALUES (?, ?)", (path_id, strPath))
        return path_id

    def toggle_path(self, OldPath, NewPath):
        QuotedNew = NewPath != "/emby_addon_mode/"
        QuotedOld = OldPath != "/emby_addon_mode/"
        self.cursor.execute("SELECT idSong, strVideoURL FROM song WHERE strVideoURL IS NOT NULL")
        VideoURLs = self.cursor.fetchall()

        if VideoURLs:
            SQLData = len(VideoURLs) * [()] # pre allocate memory

            for Index, VideoURL in enumerate(VideoURLs):
                Data = VideoURL[1].split("/")
                FileName = Data[-1]

                if QuotedNew:
                    if QuotedOld:
                        FileNameNew = FileName
                    else:
                        FileNameNew = quote(FileName)
                else:
                    if QuotedOld:
                        FileNameNew = unquote(FileName)
                    else:
                        FileNameNew = FileName

                Path = f'{"/".join(Data[:-1])}/{FileNameNew}'
                Path = common_db.toggle_path(Path, NewPath).replace("|redirect-limit=1000&failonerror=false", "")
                SQLData[Index] = (Path, VideoURL[0])

            self.cursor.executemany("UPDATE song SET strVideoURL = ? WHERE idSong = ?", SQLData) # Trailing spaces are used for MusicBrainzTrackID unificaation
            del SQLData

    # artwork
    def get_artwork(self, KodiId, ContentType):
        Artwork = {}
        self.cursor.execute("SELECT type, url FROM art WHERE media_id = ? and media_type = ?", (KodiId, ContentType))
        ArtworksData = self.cursor.fetchall()

        for ArtworkData in ArtworksData:
            Artwork[ArtworkData[0]] = ArtworkData[1]

        return Artwork

    # Favorite for content
    def get_favoriteData(self, KodiId):
        self.cursor.execute("SELECT idPath, strTitle, strFilename, idAlbum FROM song WHERE idSong = ?", (KodiId,))
        ItemData = self.cursor.fetchone()
        Thumbnail = ""

        if ItemData:
            self.cursor.execute("SELECT strPath FROM path WHERE idPath = ?", (ItemData[0],))
            DataPath = self.cursor.fetchone()

            if DataPath:
                self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (ItemData[3], "album", "thumb"))
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
        xbmc.log(f"EMBY.database.music_db: No samplerate info (add_song): {Artist} / {Title}", 2) # LOGWARNING
        SampleRate = 0

    if not Channels:
        xbmc.log(f"EMBY.database.music_db: No channels info (add_song): {Artist} / {Title}", 2) # LOGWARNING
        Channels = 0

    return BitRate, SampleRate, Channels, PlayCount

def errorhandler_MusicBrainzID(Title, MusicBrainzID, error):
    error = str(error)

    if "MusicBrainz" in error:  # Duplicate musicbrainz
        if utils.DebugLog: xbmc.log(f"EMBY.database.music_db (DEBUG): Duplicate MusicBrainzID detected: {Title} / {MusicBrainzID} / {error}", 1) # LOGDEBUG
        MusicBrainzID += " "
        return MusicBrainzID

    xbmc.log(f"EMBY.database.music_db: Unknown error: {Title} / {MusicBrainzID} / {error}", 3) # LOGERROR
    return "UNKNOWN ERROR"

from urllib.parse import quote, unquote
import xbmc
from helper import utils
from . import common_db

if utils.DatabaseFiles["video-version"] >= 135:
    VideoversionTypes = {"regular": 1, "special": 2}
else:
    VideoversionTypes = {"regular": 0, "special": 1}

SeasonPlot = utils.DatabaseFiles["video-version"] >= 145


class VideoDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common_db = common_db.CommonDatabase(cursor)

    def add_Index(self):
        try: # xbox issue
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_strFilename'")
            IndexTest = self.cursor.fetchone()

            if not IndexTest:
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_strFilename on files (strFilename)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_dateAdded on files (dateAdded)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_lastPlayed on files (lastPlayed)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_playCount on files (playCount)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmark_type on bookmark (type)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmark_timeInSeconds on bookmark (timeInSeconds)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_rating on rating (rating)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_episode_c12 on episode (c12)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_episode_idShow_idFile_c12 on episode (idShow, idFile, c12)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_genre_link_genre_id_media_id_media_type ON genre_link(genre_id, media_id, media_type)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_movie_idSet on movie (idSet)")
                self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_videoversion_media_type on videoversion (media_type)")
                self.cursor.execute("ANALYZE")
                self.cursor.connection.commit()
                self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        except Exception as Error:
            xbmc.log(f"EMBY.database.video_db: Database add index error: {Error}", 3) # LOGERROR

    def delete_Index(self):
        try: # xbox issue
            self.cursor.execute("DROP INDEX IF EXISTS idx_files_strFilename")
            self.cursor.execute("DROP INDEX IF EXISTS idx_files_dateAdded")
            self.cursor.execute("DROP INDEX IF EXISTS idx_files_lastPlayed")
            self.cursor.execute("DROP INDEX IF EXISTS idx_files_playCount")
            self.cursor.execute("DROP INDEX IF EXISTS idx_bookmark_type")
            self.cursor.execute("DROP INDEX IF EXISTS idx_bookmark_timeInSeconds")
            self.cursor.execute("DROP INDEX IF EXISTS idx_rating_rating")
            self.cursor.execute("DROP INDEX IF EXISTS idx_episode_c12")
            self.cursor.execute("DROP INDEX IF EXISTS idx_episode_idShow_idFile_c12")
            self.cursor.execute("DROP INDEX IF EXISTS idx_genre_link_genre_id_media_id_media_type")
            self.cursor.execute("DROP INDEX IF EXISTS idx_movie_idSet")
            self.cursor.execute("DROP INDEX IF EXISTS idx_videoversion_media_type")
            self.cursor.execute("ANALYZE")
            self.cursor.connection.commit()
            self.cursor.execute("BEGIN IMMEDIATE TRANSACTION")
        except Exception as Error:
            xbmc.log(f"EMBY.database.video_db: Database delete index error: {Error}", 3) # LOGERROR

    # playcount
    def get_playcount(self, KodiItemId, ContentType):
        if ContentType == "movie":
            self.cursor.execute("SELECT idFile FROM movie WHERE idMovie = ?", (KodiItemId,))
        elif ContentType == "musicvideo":
            self.cursor.execute("SELECT idFile FROM musicvideo WHERE idMVideo = ?", (KodiItemId,))
        elif ContentType == "episode":
            self.cursor.execute("SELECT idFile FROM episode WHERE idEpisode = ?", (KodiItemId,))
        else:
            return 0

        KodiFileId = self.cursor.fetchone()

        if KodiFileId:
            self.cursor.execute("SELECT playCount FROM files WHERE idFile = ?", (KodiFileId[0],))
            KodiPlayCount = self.cursor.fetchone()

            if KodiPlayCount and KodiPlayCount[0]:
                return KodiPlayCount[0]

        return 0

    # Favorite for content
    def get_favoriteData(self, KodiFileId, KodiItemId, ContentType):
        Image = ""

        if ContentType == "set":
            self.cursor.execute("SELECT strSet FROM sets WHERE idSet = ?", (KodiItemId,))
            DataSet = self.cursor.fetchone()

            if DataSet:
                for ImageId in ("poster", "thumb"):
                    self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiItemId, "set", ImageId))
                    ArtworkData = self.cursor.fetchone()

                    if ArtworkData:
                        Image = ArtworkData[0]
                        break

                return "", Image, DataSet[0]

            return "", "", ""

        self.cursor.execute("SELECT idPath, strFilename FROM files WHERE idFile = ?", (KodiFileId,))
        DataFile = self.cursor.fetchone()

        if DataFile:
            self.cursor.execute("SELECT strPath FROM path WHERE idPath = ?", (DataFile[0],))
            DataPath = self.cursor.fetchone()

            if DataPath:
                if ContentType == "movie":
                    self.cursor.execute("SELECT c00 FROM movie WHERE idMovie = ?", (KodiItemId,))
                elif ContentType == "musicvideo":
                    self.cursor.execute("SELECT c00 FROM musicvideo WHERE idMVideo = ?", (KodiItemId,))
                elif ContentType == "episode":
                    self.cursor.execute("SELECT c00 FROM episode WHERE idEpisode = ?", (KodiItemId,))
                else:
                    return "", "", ""

                ItemData = self.cursor.fetchone()

                if ItemData:
                    for ImageId in ("poster", "thumb"):
                        self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiItemId, ContentType, ImageId))
                        ArtworkData = self.cursor.fetchone()

                        if ArtworkData:
                            Image = ArtworkData[0]
                            break

                    if DataPath[0].endswith('|redirect-limit=1000&failonerror=false'):
                        return f"{DataPath[0].replace('|redirect-limit=1000&failonerror=false', '')}{DataFile[1]}|redirect-limit=1000&failonerror=false", Image, ItemData[0]

                    return f"{DataPath[0]}{DataFile[1]}", Image, ItemData[0]

        return "", "", ""

    # Favorite for subcontent
    def get_FavoriteSubcontent(self, KodiItemId, ContentType):
        Image = ""

        if ContentType == "tvshow":
            self.cursor.execute("SELECT c00 FROM tvshow WHERE idShow = ?", (KodiItemId,))
        else:
            self.cursor.execute("SELECT name, season, idShow FROM seasons WHERE idSeason = ?", (KodiItemId,))

        ItemData = self.cursor.fetchone()

        if ItemData:
            Name = ItemData[0]

            if ContentType == "season":
                self.cursor.execute("SELECT c00 FROM tvshow WHERE idShow = ?", (ItemData[2],))
                TVShowData = self.cursor.fetchone()

                if TVShowData:
                    Name = f"{TVShowData[0]} - {Name}"

            for ImageId in ("poster", "thumb"):
                self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiItemId, ContentType, ImageId))
                ArtworkData = self.cursor.fetchone()

                if ArtworkData:
                    Image = ArtworkData[0]
                    break

            if ContentType == "tvshow":
                return Image, Name, -1

            return Image, Name, ItemData[1]

        return "", "", -1

    # movies
    def get_path_runtime_by_movieid(self, KodiId):
        self.cursor.execute("SELECT idMovie, c22, c11 FROM movie WHERE idMovie = ?", (KodiId,))
        Data = self.cursor.fetchone()

        if Data:
            return [Data]

        return []

    def get_movie_doubles(self):
        Data = {}
        self.cursor.execute("SELECT c00, premiered FROM movie GROUP BY c00, premiered HAVING COUNT(c00) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idMovie FROM movie WHERE c00 = ? AND premiered IS ?" , (Double[0], Double[1]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"MOVIE_BY_NAME(m)_DATE(o)/{Double[0]}/{Double[1]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"MOVIE_BY_NAME(m)_DATE(o)/{Double[0]}/{Double[1]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def add_movie(self, KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, KodiFullPath, KodiPathId, PremiereDate, Filename, DateCreated, idSet, KodiStackedFilename, VersionName):
        self.cursor.execute("INSERT INTO movie (idMovie, idFile, c00, c01, c02, c03, c05, c06, c08, c09, c10, c11, c12, c14, c15, c16, c18, c19, c20, c21, c22, c23, premiered, idSet) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, KodiFullPath, KodiPathId, PremiereDate, idSet))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, KodiStackedFilename)
        VideoVersionTypeId = self.get_add_videoversiontype(VersionName, "regular")
        self.cursor.execute("INSERT OR IGNORE INTO videoversion(idFile, idMedia, media_type, itemType, idType) VALUES (?, ?, ?, ?, ?)", (KodiFileId, KodiItemId, "movie", VideoversionTypes["regular"], VideoVersionTypeId))

    def add_movie_version(self, KodiItemId, KodiFileId, KodiPathId, Filename, DateCreated, KodiStackedFilename, VersionName, KodiType, ContentType):
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, KodiStackedFilename)
        VideoVersionTypeId = self.get_add_videoversiontype(VersionName, ContentType)
        self.cursor.execute("INSERT OR IGNORE INTO videoversion(idFile, idMedia, media_type, itemType, idType) VALUES (?, ?, ?, ?, ?)", (KodiFileId, KodiItemId, KodiType, VideoversionTypes[ContentType], VideoVersionTypeId))

    def update_movie(self, KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, PremiereDate, idSet, Filename, KodiStackedFilename, DateCreated, VersionName, KodiPathId, Path, KodiFullPath):
        self.cursor.execute("UPDATE movie SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, c20 = ?, c21 = ?, c22 = ?, premiered = ?, idSet = ? WHERE idMovie = ?", (Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, KodiFullPath, PremiereDate, idSet, KodiItemId))
        self.update_file(KodiFileId, DateCreated, Filename, KodiStackedFilename)
        self.cursor.execute("DELETE FROM movielinktvshow WHERE idMovie = ?", (KodiItemId,))
        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (Path, KodiPathId))

        # update videoversions
        VideoVersionTypeId = self.get_add_videoversiontype(VersionName, "regular")
        self.cursor.execute("UPDATE videoversion SET idType = ? WHERE idFile = ? AND idMedia = ? AND media_type = ? AND itemType = ?", (VideoVersionTypeId, KodiFileId, KodiItemId, "movie", VideoversionTypes["regular"]))

    def update_default_movieversion(self, KodiItemId, KodiFileId, KodiPathId, Path):
        self.cursor.execute("UPDATE movie SET idFile = ?, c23 = ?, c22 = ? WHERE idMovie = ?", (KodiFileId, KodiPathId, Path, KodiItemId))

    def update_trailer(self, KodiItemId, KodiPath, EmbyParentType):
        if EmbyParentType == "Movie":
            self.cursor.execute("UPDATE movie SET c19 = ? WHERE idMovie = ?", (KodiPath, KodiItemId))

        if EmbyParentType == "Series":
            self.cursor.execute("UPDATE tvshow SET c16 = ? WHERE idShow = ?", (KodiPath, KodiItemId))

    def create_movie_entry(self):
        self.cursor.execute("SELECT coalesce(max(idMovie), 0) FROM movie")
        return self.cursor.fetchone()[0] + 1

    def delete_movie(self, KodiItemId, KodiFileId):
        self.cursor.execute("DELETE FROM movie WHERE idMovie = ?", (KodiItemId,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM movielinktvshow WHERE idMovie = ?", (KodiItemId,))
        self.cursor.execute("SELECT idFile FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, "movie"))
        FileIds = self.cursor.fetchall()

        if FileIds:
            self.cursor.executemany("DELETE FROM files WHERE idFile = ?", FileIds)
            self.cursor.execute("DELETE FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, "movie"))

    def delete_special(self, KodiParentId, KodiFileId, KodiParentType):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (KodiFileId,))
        self.common_db.delete_artwork(KodiFileId, "videoversion")
        self.cursor.execute("DELETE FROM videoversion WHERE idMedia = ? AND media_type = ? AND idFile = ?", (KodiParentId, KodiParentType, KodiFileId))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (KodiFileId,))

    def get_movie_metadata_for_listitem(self, KodiItemId, PathAndFilename):
        self.cursor.execute("SELECT c00, c01, c02, c03, c06, c10, c11, c12, c14, c15, c16, c18, c19, c21, premiered, userrating, strPath, playCount, lastPlayed, dateAdded, rating, totalTimeInSeconds, resumeTimeInSeconds, votes, rating_type, uniqueid_value, uniqueid_type, strFileName FROM movie_view WHERE idMovie = ?", (KodiItemId,))
        MovieData = self.cursor.fetchone()

        if not MovieData:
            return {}

        if not PathAndFilename:
            if MovieData[16].endswith('|redirect-limit=1000&failonerror=false'):
                PathAndFilename = f"{MovieData[16].replace('|redirect-limit=1000&failonerror=false', '')}{MovieData[27]}|redirect-limit=1000&failonerror=false"
            else:
                PathAndFilename = f"{MovieData[16]}{MovieData[27]}"

        Artwork = self.get_artwork(KodiItemId, "movie", "")
        People = self.get_people_artwork(KodiItemId, "movie")

        # get ratings
        self.cursor.execute("SELECT rating_type, rating, votes FROM rating WHERE media_id = ? AND media_type = ?", (KodiItemId, "movie"))
        Ratings = self.cursor.fetchall()
        return {'mediatype': "movie", "dbid": KodiItemId, 'title': MovieData[0], 'Overview': MovieData[1], 'ShortOverview': MovieData[2], 'Tagline': MovieData[3], 'Writer': MovieData[4], 'SortName': MovieData[5], 'duration': MovieData[6], 'MPAA': MovieData[7], 'genre': MovieData[8], 'Director': MovieData[9], 'OriginalTitle': MovieData[10], 'StudioName': MovieData[11], 'ProductionLocation': MovieData[13], 'CriticRating': MovieData[15], 'KodiPremiereDate': MovieData[14], 'playcount': MovieData[17], 'lastplayed': MovieData[18], 'KodiDateCreated': MovieData[19], 'CommunityRating': MovieData[20], 'Trailer': MovieData[12], 'path': MovieData[16], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'People': People, 'artwork': Artwork, 'KodiRunTimeTicks': MovieData[21], 'KodiPlaybackPositionTicks': MovieData[22], 'Rating': MovieData[20], 'Votes': MovieData[23], 'RatingType': MovieData[24], 'UniqueIdValue': MovieData[25], 'UniqueIdType': MovieData[26], 'Ratings': Ratings}

    # musicvideo
    def get_musicvideos_doubles(self):
        Data = {}
        self.cursor.execute("SELECT c00, premiered, c10, c09, c12 FROM musicvideo GROUP BY c00, premiered, c10, c09, c12 HAVING COUNT(c00) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idMVideo FROM musicvideo WHERE c00 = ? AND premiered IS ? AND c10 = ? AND c09 IS ? AND c12 IS ?" , (Double[0], Double[1], Double[2], Double[3], Double[4]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"MUSICVIDEO_BY_NAME(m)_DATE(o)_ARTIST(m)_ALBUM(o)_TRACK(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"MUSICVIDEO_BY_NAME(m)_DATE(o)_ARTIST(m)_ALBUM(o)_TRACK(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def add_musicvideos(self, KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, KodiFullPath, KodiPathId, PremiereDate, DateCreated, Filename, KodiStackedFilename, isPlaylist):
        # c15 (not used by Kodi) contains if it's a playlist
        if isPlaylist:
            C15 = "playlist"
        else:
            C15 = None

        self.cursor.execute("INSERT INTO musicvideo (idMVideo, idFile, c00, c01, c04, c05, c06, c08, c09, c10, c11, c12, c13, c14, premiered, c15) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, KodiFullPath, KodiPathId, PremiereDate, C15))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, KodiStackedFilename)

    def update_musicvideos(self, KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, PremiereDate, Filename, KodiStackedFilename, DateCreated, KodiPathId, Path, isPlaylist, KodiFullPath):
        self.cursor.execute("SELECT c15 FROM musicvideo_view WHERE idMVideo = ?", (KodiItemId,))
        Temp = self.cursor.fetchone()
        isPlaylistItem = Temp[0] == "playlist"

        # c15 (not used by Kodi) contains if it's a playlist
        if isPlaylist and not isPlaylistItem or not isPlaylist and isPlaylistItem: # Skip tracknumber updates
            self.cursor.execute("UPDATE musicvideo SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c13 = ?, premiered = ? WHERE idMVideo = ?", (Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, KodiFullPath, PremiereDate, KodiItemId))
        else:
            self.cursor.execute("UPDATE musicvideo SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c13 = ?, premiered = ? WHERE idMVideo = ?", (Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, KodiFullPath, PremiereDate, KodiItemId))

        self.update_file(KodiFileId, DateCreated, Filename, KodiStackedFilename)
        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (Path, KodiPathId))

    def create_entry_musicvideos(self):
        self.cursor.execute("SELECT coalesce(max(idMVideo), 0) FROM musicvideo")
        return self.cursor.fetchone()[0] + 1

    def delete_musicvideos(self, KodiItemId, KodiFileId):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (KodiItemId,))

    def get_musicvideos_metadata_for_listitem(self, KodiItemId, PathAndFilename):
        self.cursor.execute("SELECT c00, c04, c05, c06, c08, c09, c11, c12, premiered, playCount, lastPlayed, strPath, strFileName, totalTimeInSeconds, resumeTimeInSeconds, dateAdded FROM musicvideo_view WHERE idMVideo = ?", (KodiItemId,))
        MusicVideoData = self.cursor.fetchone()

        if not MusicVideoData:
            return {}

        if not PathAndFilename:
            if MusicVideoData[11].endswith('|redirect-limit=1000&failonerror=false'):
                PathAndFilename = f"{MusicVideoData[11].replace('|redirect-limit=1000&failonerror=false', '')}{MusicVideoData[12]}|redirect-limit=1000&failonerror=false"
            else:
                PathAndFilename = f"{MusicVideoData[11]}{MusicVideoData[12]}"

        Artwork = self.get_artwork(KodiItemId, "musicvideo", "")
        People = self.get_people_artwork(KodiItemId, "musicvideo")
        return {'mediatype': "musicvideo", "dbid": KodiItemId, 'title': MusicVideoData[0], 'duration': MusicVideoData[1], 'Director': MusicVideoData[2], 'StudioName': MusicVideoData[3], 'Overview': MusicVideoData[4], 'Album': MusicVideoData[5], 'genre': MusicVideoData[6], 'track': MusicVideoData[7], 'KodiPremiereDate': MusicVideoData[8], 'playcount': MusicVideoData[9], 'lastplayed': MusicVideoData[10], 'path': MusicVideoData[11], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'People': People, 'artwork': Artwork, 'KodiRunTimeTicks': MusicVideoData[13], 'KodiPlaybackPositionTicks': MusicVideoData[14], 'KodiDateCreated': MusicVideoData[15]}

    def get_musicvideos_recentlyadded_albums(self, Tag):
        self.cursor.execute(f'select actor_link.actor_id, musicvideo.c09, musicvideo.c10, musicvideo.idMVideo from musicvideo JOIN files ON files.idFile=musicvideo.idFile JOIN actor_link ON actor_link.media_id=musicvideo.idMVideo AND actor_link.media_type="musicvideo" JOIN tag_link ON tag_link.media_id=musicvideo.idMVideo AND tag_link.media_type="musicvideo" JOIN tag ON tag.tag_id=tag_link.tag_id AND tag.name="{Tag}" GROUP BY musicvideo.c10,musicvideo.c09 ORDER BY files.dateadded DESC LIMIT {utils.maxnodeitems}')
        return self.cursor.fetchall()

    def get_musicvideos_KodiId_MusicBrainzId_Artist_Title(self):
        self.cursor.execute("SELECT media_id, value FROM uniqueid WHERE media_type = ? AND type = ?", ("musicvideo", "musicbrainztrack"))
        MusicVideoDatasIds = self.cursor.fetchall()

        # Mapping
        MusicBrainzTrackId = {}

        for MusicVideoDatasId in MusicVideoDatasIds:
            MusicBrainzTrackId[MusicVideoDatasId[0]] = MusicVideoDatasId[1]

        self.cursor.execute("SELECT c13, c00, c10, idMVideo FROM musicvideo")
        MusicVideos = self.cursor.fetchall()
        MusicVideoDatas = len(MusicVideos) * [()] # pre allocate memory

        for Index, MusicVideo in enumerate(MusicVideos):
            if MusicVideo[3] in MusicBrainzTrackId:
                MusicVideoDatas[Index] = (MusicBrainzTrackId[MusicVideo[3]], MusicVideo[0], MusicVideo[1], MusicVideo[2])
            else:
                MusicVideoDatas[Index] = ("", MusicVideo[0], MusicVideo[1], MusicVideo[2])

        return MusicVideoDatas

    # tvshow
    def get_tvshow_doubles(self):
        Data = {}
        self.cursor.execute("SELECT c00, c05 FROM tvshow GROUP BY c00, c05 HAVING COUNT(c00) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idShow FROM tvshow WHERE c00 = ? AND c05 IS ?", (Double[0], Double[1]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"SERIES_BY_NAME(m)_DATE(o)/{Double[0]}/{Double[1]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"SERIES_BY_NAME(m)_DATE(o)/{Double[0]}/{Double[1]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def update_tvshow(self, TVShowName, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, TVShowSortName, duration, KodiShowId, Trailer, KodiPathId, Path):
        self.cursor.execute("SELECT c00 FROM tvshow WHERE idShow = ?", (KodiShowId,))
        Data = self.cursor.fetchone()

        if Data and Data[0].endswith(" (download)"):
            TVShowNameMod = f"{TVShowName} (download)"
            TVShowSortNameMod = f"{TVShowSortName} (download)"
        else:
            TVShowNameMod = TVShowName
            TVShowSortNameMod = TVShowSortName

        self.cursor.execute("UPDATE tvshow SET c00 = ?, c01 = ?, c02 = ?, c04 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c11 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, duration = ?, c16 = ? WHERE idShow = ?", (TVShowNameMod, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, TVShowSortNameMod, duration, Trailer, KodiShowId))
        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (Path, KodiPathId))

    def add_tvshow(self, KodiShowId, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, Trailer):
        self.cursor.execute("INSERT INTO tvshow(idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, c16) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiShowId, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, Trailer))

    def create_entry_tvshow(self):
        self.cursor.execute("SELECT coalesce(max(idShow), 0) FROM tvshow")
        return self.cursor.fetchone()[0] + 1

    def delete_tvshow(self, KodiShowId, KodiPathId):
        SubcontentKodiIds = ()
        self.common_db.delete_artwork(KodiShowId, "tvshow")
        self.delete_links_tags(KodiShowId, "tvshow", None, True)
        self.cursor.execute("SELECT idSeason FROM seasons WHERE idShow = ?", (KodiShowId,))
        SeasonsData = self.cursor.fetchall()

        for SeasonData in SeasonsData:
            SubcontentKodiIds += ((SeasonData[0], "Season"),)
            SubcontentKodiIds += self.delete_season(SeasonData[0])

        self.cursor.execute("DELETE FROM tvshowlinkpath WHERE idShow = ?", (KodiShowId,))
        self.cursor.execute("DELETE FROM movielinktvshow WHERE idShow = ?", (KodiShowId,))
        self.cursor.execute("DELETE FROM uniqueid WHERE media_id = ? AND media_type = ?", (KodiShowId, "tvshow"))
        self.cursor.execute("DELETE FROM rating WHERE media_id = ? AND media_type = ?", (KodiShowId, "tvshow"))
        self.cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (KodiShowId,))
        self.cursor.execute("DELETE FROM path WHERE idPath = ?", (KodiPathId,))
        return SubcontentKodiIds

    def add_link_tvshow(self, KodiShowId, idPath):
        self.cursor.execute("INSERT OR REPLACE INTO tvshowlinkpath(idShow, idPath) VALUES (?, ?)", (KodiShowId, idPath))

    def delete_link_tvshow(self, KodiShowId):
        self.cursor.execute("DELETE FROM tvshowlinkpath WHERE idShow = ?", (KodiShowId,))

    def get_inprogress_mixedIds(self):
        self.cursor.execute("SELECT idFile FROM bookmark WHERE type = ?", (1,))
        KodiFileIds = self.cursor.fetchall()
        InProgressInfos = ()

        for KodiFileId in KodiFileIds:
            self.cursor.execute("SELECT lastPlayed, idMovie FROM movie_view WHERE idFile = ?", (KodiFileId[0],))
            MovieData = self.cursor.fetchone()

            if MovieData:
                if not MovieData[0]:
                    InProgressInfos += (f"0000;{MovieData[1]};Movie",)
                else:
                    InProgressInfos += (f"{MovieData[0]};{MovieData[1]};Movie",)
            else:
                self.cursor.execute("SELECT lastPlayed, idEpisode FROM episode_view WHERE idFile = ?", (KodiFileId[0],))
                EpisodeData = self.cursor.fetchone()

                if EpisodeData:
                    if not EpisodeData[0]:
                        InProgressInfos += (f"0000;{EpisodeData[1]};Episode",)
                    else:
                        InProgressInfos += (f"{EpisodeData[0]};{EpisodeData[1]};Episode",)
                else:
                    self.cursor.execute("SELECT lastPlayed, idMVideo FROM musicvideo_view WHERE idFile = ?", (KodiFileId[0],))
                    MusicVideoData = self.cursor.fetchone()

                    if MusicVideoData:
                        if not MusicVideoData[0]:
                            InProgressInfos += (f"0000;{MusicVideoData[1]};MusicVideo",)
                        else:
                            InProgressInfos += (f"{MusicVideoData[0]};{MusicVideoData[1]};MusicVideo",)

        InProgressInfos = sorted(InProgressInfos, reverse=True)
        return InProgressInfos

    def get_next_episodesIds(self, TagName):
        if TagName != "unknown":
            self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (TagName,))
            TagId = self.cursor.fetchone()

            if TagId:
                TagId = TagId[0]
            else:
                return ()

            self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE tag_id = ? AND media_type = ?", (TagId, "tvshow"))
        else:
            self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE media_type = ?", ("tvshow",))

        KodiShowIds = self.cursor.fetchall()
        NextEpisodeInfos = ()

        for KodiShowId in KodiShowIds:
            self.cursor.execute("SELECT idEpisode, idFile, c12, playCount, lastPlayed FROM episode_view WHERE idShow = ? ORDER BY CAST(c12 AS INT) ASC, CAST(c13 AS INT) ASC", (KodiShowId[0],))
            Episodes = self.cursor.fetchall()
            LastPlayedDate = "0000"
            PlayedFound = False
            NextEpisodeId = "-1"

            for Episode in Episodes:
                if Episode[4] and Episode[4] > LastPlayedDate: # find highest PlayedDate
                    LastPlayedDate = str(Episode[4])

                if Episode[2] == "0": # Skip special seasons
                    continue

                if Episode[3]: # Playcount
                    PlayedFound = True
                else:
                    if PlayedFound: # get episode Id from the next (not played) episode
                        NextEpisodeId = Episode[0]
                        PlayedFound = False

            if NextEpisodeId != "-1":
                NextEpisodeInfos += (f"{LastPlayedDate};{NextEpisodeId};Episode",)

        NextEpisodeInfos = sorted(NextEpisodeInfos, reverse=True) # reverse sort by date
        return NextEpisodeInfos

    def get_last_played_next_episodesIds(self, TagName):
        if TagName != "unknown":
            self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (TagName,))
            TagId = self.cursor.fetchone()

            if TagId:
                TagId = TagId[0]
            else:
                return ()

            self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE tag_id = ? AND media_type = ?", (TagId, "tvshow"))
        else:
            self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE media_type = ?", ("tvshow",))

        KodiShowIds = self.cursor.fetchall()
        NextEpisodeInfos = ()

        for KodiShowId in KodiShowIds:
            self.cursor.execute("SELECT idEpisode, c12, c13, lastPlayed, resumeTimeInSeconds, c15, c16 FROM episode_view WHERE idShow = ? AND lastPlayed IS NOT NULL and COALESCE(c15,c12) is not '0' AND (playCount > 0 or resumeTimeInSeconds IS NOT NULL) ORDER BY lastPlayed DESC, CAST(COALESCE(c15,c12) AS INT) DESC, CAST(COALESCE(c16,c13) AS INT) DESC, CAST(c12 as INT) ASC, idEpisode ASC LIMIT 1", (KodiShowId[0],))
            Episode = self.cursor.fetchone()

            if Episode:
                LastPlayedDate = str(Episode[3])

                if Episode[4]:
                    NextEpisodeId = Episode[0]
                    NextEpisodeInfos += (f"{LastPlayedDate};{NextEpisodeId};Episode",)
                else:
                    if Episode[5]: # It was a special inserted into the season
                        # Search for more specials at the same point
                        self.cursor.execute("SELECT idEpisode FROM episode_view WHERE idShow = ? AND CAST(c15 AS INT) = ? AND CAST(c16 AS INT) = ? and idEpisode > ? ORDER BY idEpisode ASC LIMIT 1", (KodiShowId[0], Episode[5], Episode[6], Episode[0]))
                        nextEpisode = self.cursor.fetchone()

                        if not nextEpisode:
                            # No more specials, get the regular episode
                            self.cursor.execute("SELECT idEpisode FROM episode_view WHERE idShow = ? AND ((CAST(c12 AS INT) = ? AND CAST(c13 AS INT) >= ?) OR (CAST(c12 AS INT) > ?)) ORDER BY CAST(c12 AS INT) ASC, CAST(c13 AS INT) ASC LIMIT 1", (KodiShowId[0], Episode[5], Episode[6], Episode[5]))
                            nextEpisode = self.cursor.fetchone()
                    else: # It was a regular episode, get the next special or regular episode after it
                        self.cursor.execute("SELECT idEpisode FROM episode_view WHERE idShow = ? AND ((CAST(COALESCE(c15,c12) AS INT) = ? AND CAST(COALESCE(c16,c13) AS INT) > ?) OR (CAST(COALESCE(c15,c12) AS INT) > ?)) ORDER BY CAST(COALESCE(c15,c12) AS INT) ASC, CAST(COALESCE(c16,c13) AS INT) ASC, CAST(c12 as INT) ASC, idEpisode ASC LIMIT 1", (KodiShowId[0], Episode[1], Episode[2], Episode[1]))
                        nextEpisode = self.cursor.fetchone()

                    if nextEpisode:
                        NextEpisodeId = nextEpisode[0]
                        NextEpisodeInfos += (f"{LastPlayedDate};{NextEpisodeId};Episode",)

        NextEpisodeInfos = sorted(NextEpisodeInfos, reverse=True) # reverse sort by date
        return NextEpisodeInfos

    def get_tvshows_metadata_for_listitem(self, KodiShowId):
        self.cursor.execute("SELECT c00, c01, c02, c05, c08, c09, c12, c13, c14, c15, userrating, duration, lastPlayed, rating, totalCount, totalSeasons, watchedCount, dateAdded, rating_type FROM tvshow_view WHERE idShow = ?", (KodiShowId,))
        SeriesData = self.cursor.fetchone()

        if not SeriesData:
            return {}

        if SeriesData[14] and SeriesData[16]:
            UnWatchedEpisodes = int(SeriesData[14]) - int(SeriesData[16])
        else:
            UnWatchedEpisodes = 0

        Artwork = self.get_artwork(KodiShowId, "tvshow", "")
        People = self.get_people_artwork(KodiShowId, "tvshow")

        # get ratings
        self.cursor.execute("SELECT rating_type, rating, votes FROM rating WHERE media_id = ? AND media_type = ?", (KodiShowId, "tvshow"))
        Ratings = self.cursor.fetchall()
        return {'mediatype': "tvshow", "dbid": KodiShowId, 'title': SeriesData[0], 'SeriesName': SeriesData[0], 'Overview': SeriesData[1], 'Status': SeriesData[2], 'KodiPremiereDate': SeriesData[3], 'genre': SeriesData[4], 'OriginalTitle': SeriesData[5], 'UniqueIdLink': SeriesData[6], 'MPAA': SeriesData[7], 'StudioName': SeriesData[8], 'SortName': SeriesData[9], 'CriticRating': SeriesData[10], 'duration': SeriesData[11], 'lastplayed': SeriesData[12], 'CommunityRating': SeriesData[13], 'path': f"videodb://tvshows/titles/{KodiShowId}/", 'properties': {'TotalEpisodes': SeriesData[14], 'TotalSeasons': SeriesData[15], 'WatchedEpisodes': SeriesData[16], 'UnWatchedEpisodes': UnWatchedEpisodes, 'IsFolder': 'true', 'IsPlayable': 'true'}, 'People': People, 'artwork': Artwork, 'KodiDateCreated': SeriesData[17], 'Ratings': Ratings, 'RatingType': SeriesData[18]}

    def add_link_movie_tvshow(self, KodiMovieId, KodiShowId):
        self.cursor.execute("INSERT OR REPLACE INTO movielinktvshow(idMovie, idShow) VALUES (?, ?)", (KodiMovieId, KodiShowId))

    # seasons
    def update_season_tvshowid(self, KodiShowId, KodiShowIdNew):
        self.cursor.execute("UPDATE seasons SET idShow = ? WHERE idShow = ?", (KodiShowIdNew, KodiShowId))

    def get_episodes_by_seasonId(self, TVShowId, SeasonId):
        self.cursor.execute("SELECT idEpisode FROM episode WHERE idShow = ? AND idSeason = ?", (TVShowId, SeasonId,))
        return self.cursor.fetchall()

    def get_season_doubles(self, DoublesSeries):
        Data = {}

        for DoubleSerieDatas in list(DoublesSeries.values()):
            DoublesSeriesIds = ()

            for DoubleSerieData in DoubleSerieDatas[0]:
                DoublesSeriesIds += (DoubleSerieData,)

            Param = ",".join(len(DoublesSeriesIds) * ["?"]  )
            self.cursor.execute(f"SELECT season FROM seasons WHERE idShow IN ({Param}) GROUP BY season HAVING COUNT(season) > 1", DoublesSeriesIds)
            Doubles = self.cursor.fetchall()

            for Double in Doubles:
                ParamValues = DoublesSeriesIds + Double
                self.cursor.execute(f"SELECT idSeason FROM seasons WHERE idShow IN ({Param}) AND season = ?", ParamValues)
                KodiIds = self.cursor.fetchall()

                if KodiIds:
                    Data[f"SEASON_BY_SEASON(m)_SERIESID(m)/{Double[0]}/{str(DoublesSeriesIds)}"] = [{}, {}]

                    for KodiId in KodiIds:
                        Data[f"SEASON_BY_SEASON(m)_SERIESID(m)/{Double[0]}/{str(DoublesSeriesIds)}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def add_season(self, KodiSeasonId, KodiShowId, SeasonNumber, SeasonName, Overview):
        if SeasonPlot:
            self.cursor.execute("INSERT OR REPLACE INTO seasons(idSeason, idShow, season, name, plot) VALUES (?, ?, ?, ?, ?)", (KodiSeasonId, KodiShowId, SeasonNumber, SeasonName, Overview)) # IGNORE required for stacked content
        else:
            self.cursor.execute("INSERT OR REPLACE INTO seasons(idSeason, idShow, season, name) VALUES (?, ?, ?, ?)", (KodiSeasonId, KodiShowId, SeasonNumber, SeasonName)) # IGNORE required for stacked content

    def update_season(self, KodiShowId, SeasonNumber, SeasonName, KodiSeasonId, Overview):
        self.cursor.execute("SELECT name FROM seasons WHERE idSeason = ?", (KodiSeasonId,))
        Data = self.cursor.fetchone()

        if Data and Data[0].endswith(" (download)"):
            SeasonNameMod = f"{SeasonName} (download)"
        else:
            SeasonNameMod = SeasonName

        if SeasonPlot:
            self.cursor.execute("UPDATE seasons SET idShow = ?, season = ?, name = ?, plot = ? WHERE idSeason = ?", (KodiShowId, SeasonNumber, SeasonNameMod, Overview, KodiSeasonId))
        else:
            self.cursor.execute("UPDATE seasons SET idShow = ?, season = ?, name = ? WHERE idSeason = ?", (KodiShowId, SeasonNumber, SeasonNameMod, KodiSeasonId))

    def create_entry_season(self):
        self.cursor.execute("SELECT coalesce(max(idSeason), 0) FROM seasons")
        return self.cursor.fetchone()[0] + 1

    def delete_season(self, KodiSeasonId):
        # Delete Season and subcontent
        SubcontentKodiIds = ()
        SQLData = ()
        SQLData1 = ()
        self.common_db.delete_artwork(KodiSeasonId, "season")
        self.cursor.execute("SELECT idEpisode, idFile FROM episode WHERE idSeason = ?", (KodiSeasonId,))
        EpisodesData = self.cursor.fetchall()

        for EpisodeData in EpisodesData:
            SubcontentKodiIds += ((EpisodeData[0], "Episode"),)
            self.delete_episode(EpisodeData[0], EpisodeData[1])
            SQLData += ((EpisodeData[0],),)
            SQLData1 += ((EpisodeData[1],),)

        if SQLData:
            self.cursor.executemany("DELETE FROM episode WHERE idEpisode = ?", SQLData)

        if SQLData1:
            self.cursor.executemany("DELETE FROM files WHERE idFile = ?", SQLData1)

        del SQLData
        del SQLData1
        self.cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (KodiSeasonId,))
        return SubcontentKodiIds

    def get_season_metadata_for_listitem(self, KodiSeasonId):
        self.cursor.execute("SELECT season, name, userrating, showTitle, plot, premiered, genre, studio, mpaa, aired, idShow, episodes, playCount FROM season_view WHERE idSeason = ?", (KodiSeasonId,))
        SeasonData = self.cursor.fetchone()

        if not SeasonData:
            return {}

        if SeasonData[11] and SeasonData[12]:
            UnWatchedEpisodes = int(SeasonData[11]) - int(SeasonData[12])
        else:
            UnWatchedEpisodes = 0

        Artwork = self.get_artwork(KodiSeasonId, "season", "")
        People = self.get_people_artwork(KodiSeasonId, "season")
        return {'mediatype': "season", "dbid": KodiSeasonId, 'ParentIndexNumber': SeasonData[0], 'title': SeasonData[1], 'CriticRating': SeasonData[2], 'SeriesName': SeasonData[3], 'Overview': SeasonData[4], 'KodiPremiereDate': SeasonData[5], 'genre': SeasonData[6], 'StudioName': SeasonData[7], 'MPAA': SeasonData[8], 'firstaired': SeasonData[9], 'path': f"videodb://tvshows/titles/{SeasonData[10]}/{SeasonData[0]}/", 'properties': {'TVShowDBID': SeasonData[10], 'NumEpisodes': SeasonData[11], 'WatchedEpisodes': SeasonData[12], 'UnWatchedEpisodes': UnWatchedEpisodes, 'IsFolder': 'true', 'IsPlayable': 'true'}, 'People': People, 'artwork': Artwork}

    def get_showid_by_episodeid(self, KodiEpisodeId):
        self.cursor.execute("SELECT idShow FROM episode WHERE idEpisode = ?", (KodiEpisodeId,))
        KodiShowId = self.cursor.fetchone()

        if KodiShowId:
            return KodiShowId[0]

        return None

    def get_seasonid_by_showid_number(self, KodiTVShowId, KodiSeasonNumber):
        self.cursor.execute("SELECT idSeason FROM seasons WHERE idShow = ? AND season = ?", (KodiTVShowId, KodiSeasonNumber))
        KodiSeasonId = self.cursor.fetchone()

        if KodiSeasonId:
            return KodiSeasonId[0]

        return -1

    def get_season_number(self, KodiSeasonId):
        self.cursor.execute("SELECT season FROM seasons WHERE idSeason = ?", (KodiSeasonId,))
        SeasonNumber = self.cursor.fetchone()

        if SeasonNumber:
            return SeasonNumber[0]

        return None

    # episode
    def get_episodeid_path_runtime_by_tvshowid(self, TVShowId):
        self.cursor.execute("SELECT idEpisode, c18, c09 FROM episode WHERE idShow = ?", (TVShowId,))
        return self.cursor.fetchall()

    def update_episode_tvshowid(self, KodiShowId, KodiShowIdNew):
        self.cursor.execute("UPDATE episode SET idShow = ? WHERE idShow = ?", (KodiShowIdNew, KodiShowId))

    def update_episode_seasonid(self, KodiSeasonId, KodiSeasonIdNew):
        self.cursor.execute("UPDATE episode SET idSeason = ? WHERE idSeason = ?", (KodiSeasonIdNew, KodiSeasonId))

    def get_episodes_by_tvshowId(self, TVShowId):
        self.cursor.execute("SELECT idEpisode FROM episode WHERE idShow = ? AND c12 != ?", (TVShowId, 0))
        return self.cursor.fetchall()

    def get_episode_doubles(self):
        Data = {}

        # Detect doubles by multiple identical tvshows but skip if seasonnumber or episodenumber is None -> SQL "IS" respects queries by None, "=" skips None's
        self.cursor.execute("SELECT strTitle, premiered, c12, c13 FROM episode_view GROUP BY strTitle, premiered, c12, c13 HAVING COUNT(strTitle) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idEpisode FROM episode_view WHERE strTitle = ? AND premiered IS ? AND c12 = ? AND c13 = ?", (Double[0], Double[1], Double[2], Double[3]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"EPISODE_BY_TVSHOWNAME(m)_TVSHOWDATE(o)_SEASONNUMBER(m)_NUMBER(m)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"EPISODE_BY_TVSHOWNAME(m)_TVSHOWDATE(o)_SEASONNUMBER(m)_NUMBER(m)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        # Detect doubles by multiple identical tvshows and episode name must match
        self.cursor.execute("SELECT strTitle, premiered, c12, c13, c00 FROM episode_view GROUP BY strTitle, premiered, c12, c13, c00 HAVING COUNT(c00) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idEpisode FROM episode_view WHERE strTitle = ? AND premiered IS ? AND c12 IS ? AND c13 IS ? AND c00 = ?", (Double[0], Double[1], Double[2], Double[3], Double[4]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"EPISODE_BY_TVSHOWNAME(m)_TVSHOWDATE(o)_SEASONNUMBER(o)_NUMBER(o)_NAME(m)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"EPISODE_BY_TVSHOWNAME(m)_TVSHOWDATE(o)_SEASONNUMBER(o)_NUMBER(o)_NAME(m)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}/{Double[4]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        # Detect doubles by single tvshow containing double episodes
        self.cursor.execute("SELECT c00, idShow, c12, c13 FROM episode GROUP BY c00, idShow, c12, c13 HAVING COUNT(c00) > 1")
        Doubles = self.cursor.fetchall()

        for Double in Doubles:
            self.cursor.execute("SELECT idEpisode FROM episode WHERE c00 = ? AND idShow = ? AND c12 IS ? AND c13 IS ?" , (Double[0], Double[1], Double[2], Double[3]))
            KodiIds = self.cursor.fetchall()

            if KodiIds:
                Data[f"EPISODE_BY_NAME(m)_TVSHOWID(m)_SEASONNUMBER(o)_NUMBER(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}"] = [{}, {}]

                for KodiId in KodiIds:
                    Data[f"EPISODE_BY_NAME(m)_TVSHOWID(m)_SEASONNUMBER(o)_NUMBER(o)/{Double[0]}/{Double[1]}/{Double[2]}/{Double[3]}"][0].update({KodiId[0]: {"EmbyServerId": "", "EmbyLibraryIds": "", "EmbyId": ""}})

        return Data

    def add_episode(self, KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, KodiFullPath, KodiPathId, Unique, KodiShowId, KodiSeasonId, Filename, DateCreated, KodiStackedFilename):
        self.cursor.execute("INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c06, c09, c10, c12, c13, c14, c15, c16, c18, c19, c20, idShow, idSeason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, KodiFullPath, KodiPathId, Unique, KodiShowId, KodiSeasonId))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, KodiStackedFilename)

    def update_episode(self, KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, Path, Filename, KodiPathId, Unique, KodiShowId, KodiSeasonId, KodiStackedFilename, DateCreated, KodiFullPath):
        self.cursor.execute("UPDATE episode SET idFile = ?, c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?, c09 = ?, c10 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, c20 = ?, idShow = ?, idSeason = ? WHERE idEpisode = ?", (KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, KodiFullPath, KodiPathId, Unique, KodiShowId, KodiSeasonId, KodiItemId))
        self.update_file(KodiFileId, DateCreated, Filename, KodiStackedFilename)
        self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (Path, KodiPathId))

    def create_entry_episode(self):
        self.cursor.execute("SELECT coalesce(max(idEpisode), 0) FROM episode")
        return self.cursor.fetchone()[0] + 1

    def delete_episode(self, KodiItemId, KodiFileId):
        self.cursor.execute("DELETE FROM uniqueid WHERE media_id = ? AND media_type = ?", (KodiItemId, "episode"))
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", (KodiItemId, "episode"))
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (KodiFileId,))
        self.cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (KodiItemId,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (KodiFileId,))

    def get_episode_metadata_for_listitem(self, KodiItemId, PathAndFilename):
        self.cursor.execute("SELECT c00, c01, c04, c05, c09, c10, c12, c13, c14, c15, c16, c20, userrating, playCount, lastPlayed, genre, studio, strPath, strTitle, strFileName, totalTimeInSeconds, resumeTimeInSeconds, rating, votes, rating_type, uniqueid_value, uniqueid_type, mpaa, dateAdded, idShow, idSeason FROM episode_view WHERE idEpisode = ?", (KodiItemId,))

        EpisodeData = self.cursor.fetchone()

        if not EpisodeData:
            return {}

        if not PathAndFilename:
            if EpisodeData[17].endswith('|redirect-limit=1000&failonerror=false'):
                PathAndFilename = f"{EpisodeData[17].replace('|redirect-limit=1000&failonerror=false', '')}{EpisodeData[19]}|redirect-limit=1000&failonerror=false"
            else:
                PathAndFilename = f"{EpisodeData[17]}{EpisodeData[19]}"

        People = self.get_people_artwork(KodiItemId, "episode")
        People += self.get_people_artwork(EpisodeData[29], "tvshow")
        Artwork = self.get_artwork(KodiItemId, "episode", "")
        Artwork.update(self.get_artwork(EpisodeData[29], "tvshow", "tvshow."))
        Artwork.update(self.get_artwork(EpisodeData[30], "season", "season."))

        # get Ratings
        self.cursor.execute("SELECT rating_type, rating, votes FROM rating WHERE media_id = ? AND media_type = ?", (KodiItemId, "episode"))
        Ratings = self.cursor.fetchall()

        return {'mediatype': "episode", "dbid": KodiItemId, 'title': EpisodeData[0], 'Overview': EpisodeData[1], 'Writer': EpisodeData[2], 'KodiPremiereDate': EpisodeData[3], 'duration': EpisodeData[4], 'Director': EpisodeData[5], 'ParentIndexNumber': EpisodeData[6], 'IndexNumber': EpisodeData[7], 'OriginalTitle': EpisodeData[8], 'SortParentIndexNumber': EpisodeData[9], 'SortIndexNumber': EpisodeData[10], 'UniqueIdLink': EpisodeData[11], 'CriticRating': EpisodeData[12], 'playcount': EpisodeData[13], 'lastplayed': EpisodeData[14], 'SeriesName': EpisodeData[18], 'genre': EpisodeData[15], 'StudioName': EpisodeData[16], 'path': EpisodeData[17], 'pathandfilename': PathAndFilename, 'properties': {'TVShowDBID': EpisodeData[29], 'IsFolder': 'false', 'IsPlayable': 'true'}, 'People': People, 'artwork': Artwork, 'KodiRunTimeTicks': EpisodeData[20], 'KodiPlaybackPositionTicks': EpisodeData[21], 'Rating': EpisodeData[22], 'Votes': EpisodeData[23], 'RatingType': EpisodeData[24], 'UniqueIdValue': EpisodeData[25], 'UniqueIdType': EpisodeData[26], 'Ratings': Ratings, 'MPAA': EpisodeData[27], 'KodiDateCreated': EpisodeData[28]}

    # boxsets
    def add_boxset(self, strSet, strOverview):
        self.cursor.execute("SELECT coalesce(max(idSet), 0) FROM sets")
        set_id =  self.cursor.fetchone()[0] + 1

        if utils.DatabaseFiles["video-version"] >= 144:
            self.cursor.execute("INSERT INTO sets(idSet, strSet, strOverview, strOriginalSet) VALUES (?, ?, ?, ?)", (set_id, strSet, strOverview, strSet))
        else:
            self.cursor.execute("INSERT INTO sets(idSet, strSet, strOverview) VALUES (?, ?, ?)", (set_id, strSet, strOverview))

        return set_id

    def update_boxset(self, strSet, strOverview, idSet):
        if utils.DatabaseFiles["video-version"] >= 144:
            self.cursor.execute("UPDATE sets SET strSet = ?, strOverview = ?, strOriginalSet = ? WHERE idSet = ?", (strSet, strOverview, strSet, idSet))
        else:
            self.cursor.execute("UPDATE sets SET strSet = ?, strOverview = ? WHERE idSet = ?", (strSet, strOverview, idSet))

    def set_boxset(self, idSet, idMovie):
        self.cursor.execute("UPDATE movie SET idSet = ? WHERE idMovie = ?", (idSet, idMovie))

    def remove_from_boxset(self, idMovie):
        self.cursor.execute("UPDATE movie SET idSet = NULL WHERE idMovie = ?", (idMovie,))

    def delete_boxset(self, idSet):
        self.cursor.execute("DELETE FROM sets WHERE idSet = ?", (idSet,))

    # file
    def add_file(self, idPath, Filename, dateAdded, KodiFileId, KodiStackedFilename):
        if KodiStackedFilename:
            Filename = KodiStackedFilename

        self.cursor.execute("INSERT INTO files(idPath, strFilename, dateAdded, idFile) VALUES (?, ?, ?, ?)", (idPath, Filename, dateAdded, KodiFileId))

    def update_file(self, KodiFileId, dateAdded, Filename, KodiStackedFilename):
        if KodiStackedFilename:
            Filename = KodiStackedFilename

        if Filename:
            self.cursor.execute("UPDATE files SET strFilename = ?, dateAdded = ? WHERE idFile = ?", (Filename, dateAdded, KodiFileId))
        else:
            self.cursor.execute("UPDATE files SET dateAdded = ? WHERE idFile = ?", (dateAdded, KodiFileId))

    def create_entry_file(self):
        self.cursor.execute("SELECT coalesce(max(idFile), 0) FROM files")
        return self.cursor.fetchone()[0] + 1

    # video versions
    def get_add_videoversiontype(self, VersionName, ContentType):
        self.cursor.execute("SELECT id FROM videoversiontype WHERE name = ? AND itemType = ?", (VersionName, VideoversionTypes[ContentType]))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(id), 0) FROM videoversiontype")
        VideoVersionTypeId = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT OR REPLACE INTO videoversiontype(id, name, owner, itemType) VALUES (?, ?, ?, ?)", (VideoVersionTypeId, VersionName, 0, VideoversionTypes[ContentType]))
        return VideoVersionTypeId

    def delete_videoversion_by_KodiId_notKodiFileId_KodiType(self, KodiItemId, KodiFileId, KodiType):
        self.cursor.execute("SELECT idFile FROM videoversion WHERE idMedia = ? AND idFile != ? AND media_type = ?", (KodiItemId, KodiFileId, KodiType))
        KodiFileIdsRef = self.cursor.fetchall()
        self.cursor.execute("DELETE FROM videoversion WHERE idMedia = ? AND idFile != ? AND media_type = ?", (KodiItemId, KodiFileId, KodiType))
        SQLData = ()

        for KodiFileIdRef in KodiFileIdsRef:
            SQLData += ((KodiFileIdRef[0],),)

        if SQLData:
            self.cursor.executemany("DELETE FROM files WHERE idFile = ?", SQLData)

        del SQLData

    def get_KodiFileId_by_videoversion(self, KodiItemId, KodiType):
        self.cursor.execute("SELECT idFile FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, KodiType))
        return self.cursor.fetchall()

    def get_BookmarkData_by_videoversion(self, KodiItemId, KodiType):
        self.cursor.execute("SELECT idFile FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, KodiType))
        KodiFileIds = self.cursor.fetchall()
        BookmarkData = len(KodiFileIds) * [()] # pre allocate memory

        for Index, KodiFileId in enumerate(KodiFileIds):
            self.cursor.execute("SELECT iVideoDuration FROM streamdetails WHERE idFile = ? AND iStreamType = ?", (KodiFileId[0], 0))
            RuntimeTicks = self.cursor.fetchone()

            if RuntimeTicks and RuntimeTicks[0]:
                BookmarkData[Index] = (KodiFileId[0], float(RuntimeTicks[0]))
            else:
                BookmarkData[Index] = (KodiFileId[0], 0)

        return BookmarkData

    def delete_videoversion(self, KodiItemId, KodiType):
        self.cursor.execute("SELECT idFile FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, KodiType))
        KodiFileIdsRef = self.cursor.fetchall()
        self.cursor.execute("DELETE FROM videoversion WHERE idMedia = ? AND media_type = ?", (KodiItemId, KodiType))
        SQLData = ()

        for KodiFileIdRef in KodiFileIdsRef:
            SQLData += ((KodiFileIdRef[0],),)

        if SQLData:
            self.cursor.executemany("DELETE FROM files WHERE idFile = ?", SQLData)

        del SQLData

    # people
    def add_person(self, PersonName, ArtUrl):
        self.cursor.execute("SELECT coalesce(max(actor_id), 0) FROM actor")
        PersonId = self.cursor.fetchone()[0] + 1
        PersonNameMod = PersonName

        while True:
            try:
                self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (PersonId, PersonNameMod, ArtUrl))
                break
            except Exception as Error:
                if utils.DebugLog: xbmc.log(f"EMBY.database.video_db (DEBUG): Add person, Duplicate ActorName detected: {PersonNameMod} / {Error}", 1) # LOGDEBUG
                PersonNameMod += " "

            if len(PersonNameMod) >= 255: # max 256 char
                xbmc.log(f"EMBY.database.video_db: Add person, too many charecters ActorName detected: {PersonNameMod}", 2) # LOGWARNING
                return -1

        return PersonId

    def update_person(self, PersonId, PersonName, ArtUrl):
        PersonNameMod = PersonName

        while True:
            try:
                self.cursor.execute("UPDATE OR IGNORE actor SET name = ?, art_urls = ? WHERE actor_id = ?", (PersonNameMod, ArtUrl, PersonId))
                break
            except Exception as Error:
                if utils.DebugLog: xbmc.log(f"EMBY.database.video_db (DEBUG): Update person, Duplicate ActorName detected: {PersonNameMod} / {Error}", 1) # LOGDEBUG
                PersonNameMod += " "

            if len(PersonNameMod) >= 255:
                xbmc.log(f"EMBY.database.video_db: Update person, too many charecters ActorName detected: {PersonNameMod}", 2) # LOGWARNING
                return

    def delete_links_actors(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM actor_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def delete_links_director(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM director_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def delete_links_writer(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM writer_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def get_People(self, ActorId):
        MusicVideos = False
        Movies = False
        TVShows = False
        self.cursor.execute("SELECT name, art_urls FROM actor WHERE actor_id = ?", (ActorId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM actor_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "musicvideo"))

            if self.cursor.fetchone()[0]:
                MusicVideos = True
            else:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM director_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "musicvideo"))

                if self.cursor.fetchone()[0]:
                    MusicVideos = True
                else:
                    self.cursor.execute("SELECT EXISTS(SELECT 1 FROM writer_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "musicvideo"))

                    if self.cursor.fetchone()[0]:
                        MusicVideos = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM actor_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "movie"))

            if self.cursor.fetchone()[0]:
                Movies = True
            else:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM director_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "movie"))

                if self.cursor.fetchone()[0]:
                    Movies = True
                else:
                    self.cursor.execute("SELECT EXISTS(SELECT 1 FROM writer_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "movie"))

                    if self.cursor.fetchone()[0]:
                        Movies = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM actor_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "tvshow"))

            if self.cursor.fetchone()[0]:
                TVShows = True
            else:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM director_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "tvshow"))

                if self.cursor.fetchone()[0]:
                    TVShows = True
                else:
                    self.cursor.execute("SELECT EXISTS(SELECT 1 FROM writer_link WHERE actor_id = ? AND media_type = ?)", (ActorId, "tvshow"))

                    if self.cursor.fetchone()[0]:
                        TVShows = True

            return Data[0], Data[1], MusicVideos, Movies, TVShows

        return "", "", False, False, False

    def get_artist_metadata_for_listitem(self, KodiItemId):
        self.cursor.execute("SELECT name, art_urls FROM actor WHERE actor_id = ?", (KodiItemId,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = {"poster": ItemData[1]}
        return {'mediatype': "actor", "dbid": KodiItemId, 'title': ItemData[0], 'artist': ItemData[0], 'path': f"videodb://musicvideos/artists/{KodiItemId}/", 'properties': {'IsFolder': 'true', 'IsPlayable': 'true'}, 'artwork': Artwork}

    def del_musicartist(self, ArtistId):
        self.delete_people_by_Id(ArtistId)

    def delete_people_by_Id(self, ActorId):
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", (ActorId, "actor"))
        self.cursor.execute("DELETE FROM actor_link WHERE actor_id = ?", (ActorId,))
        self.cursor.execute("DELETE FROM director_link WHERE actor_id = ?", (ActorId,))
        self.cursor.execute("DELETE FROM writer_link WHERE actor_id = ?", (ActorId,))
        self.cursor.execute("DELETE FROM actor WHERE actor_id = ?", (ActorId,))

    def add_director_link(self, ActorId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO director_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (ActorId, MediaId, MediaType))

    def add_writer_link(self, ActorId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO writer_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (ActorId, MediaId, MediaType))

    def add_actor_link(self, ActorId, MediaId, MediaType, Role, Order):
        self.cursor.execute("INSERT OR REPLACE INTO actor_link(actor_id, media_id, media_type, role, cast_order) VALUES (?, ?, ?, ?, ?)", (ActorId, MediaId, MediaType, Role, Order))

    def get_people_artwork(self, KodiItemId, ContentType):
        People = ()
        PeopleCounter = 0
        self.cursor.execute("SELECT actor_id, role FROM actor_link WHERE media_id = ? and media_type = ?", (KodiItemId, ContentType))
        ActorLinks = self.cursor.fetchall()

        for ActorLink in ActorLinks:
            self.cursor.execute("SELECT name, art_urls FROM actor WHERE actor_id = ?", (ActorLink[0],))
            Actor = self.cursor.fetchone()
            People += ((Actor[0], ActorLink[1], PeopleCounter, Actor[1]),)
            PeopleCounter += 1

        self.cursor.execute("SELECT actor_id FROM director_link WHERE media_id = ? and media_type = ?", (KodiItemId, ContentType))
        DirectorLinks = self.cursor.fetchall()

        for DirectorLink in DirectorLinks:
            self.cursor.execute("SELECT name, art_urls FROM actor WHERE actor_id = ?", (DirectorLink[0],))
            Actor = self.cursor.fetchone()
            People += ((Actor[0], "Director", PeopleCounter, Actor[1]),)
            PeopleCounter += 1

        return People

    # streams
    def delete_streams(self, KodiFileId):
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (KodiFileId,))

    def add_streams(self, KodiFileId, videostream, audiostream, subtitlestream, runtime):
        SQLData = ()

        if utils.DatabaseFiles["video-version"] >= 144:
            for track in videostream:
                SQLData += ((KodiFileId, 0, track['codec'], track['aspect'], track['width'], track['height'], runtime, track['stereomode'], track['language'], track['hdrtype'], None, None, None, None, track['hdrdetail']),)

            for track in audiostream:
                SQLData += ((KodiFileId, 1, None, None, None, None, None, None, None, None, track['codec'], track['channels'], track['language'], None, None),)

            for track in subtitlestream:
                if track['external'] == "0":
                    SQLData += ((KodiFileId, 2, None, None, None, None, None, None, None, None, None, None, None, track['language'], None),)
        else:
            for track in videostream:
                SQLData += ((KodiFileId, 0, track['codec'], track['aspect'], track['width'], track['height'], runtime, track['stereomode'], track['language'], track['hdrtype'], None, None, None, None),)

            for track in audiostream:
                SQLData += ((KodiFileId, 1, None, None, None, None, None, None, None, None, track['codec'], track['channels'], track['language'], None),)

            for track in subtitlestream:
                if track['external'] == "0":
                    SQLData += ((KodiFileId, 2, None, None, None, None, None, None, None, None, None, None, None, track['language']),)

        if SQLData:
            if utils.DatabaseFiles["video-version"] >= 144:
                self.cursor.executemany("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth, iVideoHeight, iVideoDuration, strStereoMode, strVideoLanguage, strHdrType, strAudioCodec, iAudioChannels, strAudioLanguage, strSubtitleLanguage, strHdrDetail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SQLData)
            else:
                self.cursor.executemany("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth, iVideoHeight, iVideoDuration, strStereoMode, strVideoLanguage, strHdrType, strAudioCodec, iAudioChannels, strAudioLanguage, strSubtitleLanguage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SQLData)

        del SQLData

    # stacked times
    def delete_stacktimes(self, KodiFileId):
        self.cursor.execute("DELETE FROM stacktimes WHERE idFile = ?", (KodiFileId,))

    def add_stacktimes(self, idFile, times):
        self.cursor.execute("INSERT OR REPLACE INTO stacktimes(idFile, times) VALUES (?, ?)", (idFile, times))

    # tags
    def get_add_tag(self, TagName):
        self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (TagName,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(tag_id), 0) FROM tag")
        TagId = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT OR REPLACE INTO tag(tag_id, name) VALUES (?, ?)", (TagId, TagName))
        return TagId

    def update_tag(self, TagName, TagId):
        while True:
            try:
                self.cursor.execute("UPDATE tag SET name = ? WHERE tag_id = ?", (TagName, TagId))
                break
            except Exception as Error:
                if utils.DebugLog: xbmc.log(f"EMBY.database.video_db (DEBUG): Update tag, Duplicate ActorName detected: {TagName} / {Error}", 1) # LOGDEBUG
                TagName += " "

            if len(TagName) >= 255:
                xbmc.log(f"EMBY.database.video_db: Update tag, too many charecters in field name detected: {TagName}", 2) # LOGWARNING
                return

    def add_tag_link(self, TagId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO tag_link(tag_id, media_id, media_type) VALUES (?, ?, ?)", (TagId, MediaId, MediaType))

    def delete_library_links_tags(self, MediaId, MediaType, LibraryName):
        self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (f"{LibraryName} (Library)",))
        TagId = self.cursor.fetchone()

        if TagId:
            self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ? AND media_id = ? AND media_type = ?", (TagId[0], MediaId, MediaType))

    def delete_links_tags(self, MediaId, MediaType, KodiLibraryTagIds, All):
        if KodiLibraryTagIds:
            KodiLibraryTagIdsArray = ()

            for KodiLibraryTagId in KodiLibraryTagIds:
                KodiLibraryTagIdsArray += (KodiLibraryTagId[0], )

            Param = ",".join(len(KodiLibraryTagIdsArray) * ["?"]  )
            self.cursor.execute(f"DELETE FROM tag_link WHERE media_id = ? AND media_type = ? AND tag_id NOT IN ({Param})", (MediaId, MediaType) + KodiLibraryTagIdsArray)
        elif All:
            self.cursor.execute("DELETE FROM tag_link WHERE media_id = ? AND media_type = ?", (MediaId, MediaType))
        else: # Keep favorites tag
            self.cursor.execute("SELECT tag_id FROM tag_link WHERE media_id = ? AND media_type = ?", (MediaId, MediaType))
            TagIds = self.cursor.fetchall()
            SQLData = ()

            for TagId in TagIds:
                self.cursor.execute("SELECT EXISTS(SELECT 1 FROM tag WHERE tag_id = ? AND name NOT LIKE ?)", (TagId, "% (Favorites)"))

                if self.cursor.fetchone()[0]:
                    SQLData += ((MediaId, MediaType),)

            if SQLData:
                self.cursor.executemany("DELETE FROM tag_link WHERE media_id = ? AND media_type = ?", SQLData)

            del SQLData

    def get_collection_tags(self, LibraryTag, KodiMediaType):
        self.cursor.execute("SELECT tag_id, name FROM tag WHERE name LIKE ?", ("% (Collection)",))
        CollectionItems = self.cursor.fetchall()
        CollectionIds = ()
        CollectionNames = {}

        for CollectionItem in CollectionItems:
            CollectionIds += (CollectionItem[0],)
            CollectionNames[CollectionItem[0]] = CollectionItem[1]

        CollectionValidIds = ()
        CollectionValidNames = ()

        if LibraryTag and LibraryTag != "unknown":
            self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (LibraryTag,))
            LibraryTagId = self.cursor.fetchone()

            if LibraryTagId:
                self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE tag_id = ?", (LibraryTagId[0],))
                ValidMediaIds = self.cursor.fetchall()
            else:
                return (), ()
        else:
            self.cursor.execute("SELECT DISTINCT media_id FROM tag_link WHERE media_type = ?", (KodiMediaType,))
            ValidMediaIds = self.cursor.fetchall()

        for ValidMediaId in  ValidMediaIds:
            self.cursor.execute("SELECT DISTINCT tag_id FROM tag_link WHERE media_id = ? AND media_type = ?", (ValidMediaId[0], KodiMediaType))
            TagIds = self.cursor.fetchall()

            for TagId in TagIds:
                if TagId[0] in CollectionIds and TagId[0] not in CollectionValidIds:
                    CollectionValidIds += TagId
                    CollectionValidNames += (CollectionNames[TagId[0]],)

        return CollectionValidIds, CollectionValidNames

    def get_Tag_Name(self, TagId):
        MusicVideos = False
        Movies = False
        TVShows = False
        self.cursor.execute("SELECT name FROM tag WHERE tag_id = ?", (TagId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM tag_link WHERE tag_id = ? AND media_type = ?)", (TagId, "musicvideo"))

            if self.cursor.fetchone()[0]:
                MusicVideos = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM tag_link WHERE tag_id = ? AND media_type = ?)", (TagId, "movie"))

            if self.cursor.fetchone()[0]:
                Movies = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM tag_link WHERE tag_id = ? AND media_type = ?)", (TagId, "tvshow"))

            if self.cursor.fetchone()[0]:
                TVShows = True

            return Data[0], MusicVideos, Movies, TVShows

        return "", False, False, False

    def delete_tag(self, Name):
        self.cursor.execute("DELETE FROM tag WHERE name = ?", (Name,))

    def delete_tag_by_Id(self, TagId):
        TagName = ""
        self.cursor.execute("SELECT name FROM tag WHERE tag_id = ?", (TagId,))
        Data = self.cursor.fetchone()

        if Data:
            TagName = Data[0]

        self.cursor.execute("DELETE FROM tag WHERE tag_id = ?", (TagId,))
        self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ?", (TagId,))
        return TagName

    def add_link_tag(self, TagId, KodiItemId, KodiType):
        self.cursor.execute("INSERT OR REPLACE INTO tag_link(tag_id, media_id, media_type) VALUES (?, ?, ?)", (TagId, KodiItemId, KodiType)) # IGNORE required for stacked content

    def set_Favorite_Tag(self, IsFavorite, KodiItemId, KodiType):
        if KodiType == "tvshow":
            TagName = "TVShows (Favorites)"
        else:
            TagName = f"{KodiType[:1].upper() + KodiType[1:]}s (Favorites)"

        self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (TagName,))
        Data = self.cursor.fetchone()

        if Data:
            TagId = Data[0]
        else:
            self.cursor.execute("SELECT coalesce(max(tag_id), 0) FROM tag")
            TagId = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO tag(tag_id, name) VALUES (?, ?)", (TagId, TagName))

        if IsFavorite:
            self.add_link_tag(TagId, KodiItemId, KodiType)
        else:
            self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ? AND media_type = ? AND media_id = ?", (TagId, KodiType, KodiItemId))

    # genres
    def get_add_genre(self, GenreName):
        self.cursor.execute("SELECT genre_id FROM genre WHERE name = ?", (GenreName,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(genre_id), 0) FROM genre")
        GenreId = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO genre(genre_id, name) VALUES (?, ?)", (GenreId, GenreName))
        return GenreId

    def update_genre(self, GenreName, GenreId):
        self.cursor.execute("UPDATE OR IGNORE genre SET name = ? WHERE genre_id = ?", (GenreName, GenreId))

    def add_genre_link(self, GenreId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO genre_link(genre_id, media_id, media_type) VALUES (?, ?, ?)", (GenreId, MediaId, MediaType))

    def delete_links_genres(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM genre_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(self, GenreId):
        MusicVideos = False
        Movies = False
        TVShows = False
        self.cursor.execute("SELECT name FROM genre WHERE genre_id = ?", (GenreId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM genre_link WHERE genre_id = ? AND media_type = ?)", (GenreId, "musicvideo"))

            if self.cursor.fetchone()[0]:
                MusicVideos = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM genre_link WHERE genre_id = ? AND media_type = ?)", (GenreId, "movie"))

            if self.cursor.fetchone()[0]:
                Movies = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM genre_link WHERE genre_id = ? AND media_type = ?)", (GenreId, "tvshow"))

            if self.cursor.fetchone()[0]:
                TVShows = True

            return Data[0], MusicVideos, Movies, TVShows

        return "", False, False, False

    def delete_genre_by_Id(self, GenreId):
        GenreName = ""
        self.cursor.execute("SELECT name FROM genre WHERE genre_id = ?", (GenreId,))
        Data = self.cursor.fetchone()

        if Data:
            GenreName = Data[0]

        self.cursor.execute("DELETE FROM genre_link WHERE genre_id = ?", (GenreId,))
        self.cursor.execute("DELETE FROM genre WHERE genre_id = ?", (GenreId,))
        return GenreName

    # studios
    def get_add_studio(self, StudioName):
        self.cursor.execute("SELECT studio_id FROM studio WHERE name = ?", (StudioName,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(studio_id), 0) FROM studio")
        StudioId = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT OR REPLACE INTO studio(studio_id, name) VALUES (?, ?)", (StudioId, StudioName))
        return StudioId

    def update_studio(self, StudioName, StudioId):
        self.cursor.execute("UPDATE OR IGNORE studio SET name = ? WHERE studio_id = ?", (StudioName, StudioId))

    def add_studio_link(self, GenreId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO studio_link(studio_id, media_id, media_type) VALUES (?, ?, ?)", (GenreId, MediaId, MediaType))

    def delete_links_studios(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM studio_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def delete_studio_by_Id(self, StudioId):
        StudioName = ""
        self.cursor.execute("SELECT name FROM studio WHERE studio_id = ?", (StudioId,))
        Data = self.cursor.fetchone()

        if Data:
            StudioName = Data[0]

        self.cursor.execute("DELETE FROM studio_link WHERE studio_id = ?", (StudioId,))
        self.cursor.execute("DELETE FROM studio WHERE studio_id = ?", (StudioId,))
        return StudioName

    def get_Studio_Name(self, StudioId):
        MusicVideos = False
        Movies = False
        TVShows = False
        self.cursor.execute("SELECT name FROM studio WHERE studio_id = ?", (StudioId,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM studio_link WHERE studio_id = ? AND media_type = ?)", (StudioId, "musicvideo"))

            if self.cursor.fetchone()[0]:
                MusicVideos = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM studio_link WHERE studio_id = ? AND media_type = ?)", (StudioId, "movie"))

            if self.cursor.fetchone()[0]:
                Movies = True

            self.cursor.execute("SELECT EXISTS(SELECT 1 FROM studio_link WHERE studio_id = ? AND media_type = ?)", (StudioId, "tvshow"))

            if self.cursor.fetchone()[0]:
                TVShows = True

            return Data[0], MusicVideos, Movies, TVShows

        return "", False, False, False

    # ratings
    def delete_ratings(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM rating WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_ratings(self, KodiItemId, media_type, rating_type, Rating):
        if Rating:
            if rating_type == "default" and utils.imdbrating:
                rating_type = "imdb"

            self.cursor.execute("SELECT coalesce(max(rating_id), 0) FROM rating")
            rating_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO rating(rating_id, media_id, media_type, rating_type, rating) VALUES (?, ?, ?, ?, ?)", (rating_id, KodiItemId, media_type, rating_type, Rating))
            return rating_id

        return None

    # uniqueid
    def delete_uniqueids(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM uniqueid WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_uniqueids(self, KodiItemId, ProviderIds, MediaId, DefaulId):
        SQLData = ()
        SQLData1 = ()

        for Provider, Value in list(ProviderIds.items()):
            if not Value:
                continue

            Provider = Provider.lower()

            if Provider in ("facebook", "instagram", "official website", "x (twitter)", "twitter", "x", "fan site", "wikipedia"):
                continue

            if Provider == DefaulId:
                SQLData1 = (KodiItemId, MediaId, Value, Provider)
            else:
                SQLData += ((KodiItemId, MediaId, Value, Provider),)

        if SQLData1:
            self.cursor.execute("SELECT coalesce(max(uniqueid_id), 0) FROM uniqueid")
            UniqueId = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO uniqueid(uniqueid_id, media_id, media_type, value, type) VALUES (?, ?, ?, ?, ?)", (UniqueId,) + SQLData1)
        else:
            UniqueId = None

        if SQLData:
            self.cursor.executemany("INSERT INTO uniqueid(media_id, media_type, value, type) VALUES (?, ?, ?, ?)", SQLData)

        del SQLData
        del SQLData1
        return UniqueId

    # bookmarks
    def get_bookmark_urls_all(self):
        self.cursor.execute("SELECT thumbNailImage FROM bookmark")
        return self.cursor.fetchall()

    def delete_bookmark(self, KodiFileId, BookmarkType):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ? AND type = ?", (KodiFileId, BookmarkType))

    def add_bookmarks(self, KodiFileId, RunTimeTicks, KodiChapters):
        SQLData = ()

        for StartPositionTicks, Image in list(KodiChapters.items()):
            SQLData += ((KodiFileId, StartPositionTicks, RunTimeTicks, Image, "VideoPlayer", 0),)

        if SQLData:
            self.cursor.executemany("INSERT INTO bookmark(idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, type) VALUES (?, ?, ?, ?, ?, ?)", SQLData)

        del SQLData

    def update_bookmark_playstate(self, KodiFileId, playcount, date_played, Progress, Runtime):
        Update = False

        self.cursor.execute("SELECT timeInSeconds FROM bookmark WHERE idFile = ? AND type = ?", (KodiFileId, "1"))
        Data = self.cursor.fetchone()

        if Data:
            CurrentProgress = Data[0]

            if Progress:
                if CurrentProgress != Progress:
                    self.cursor.execute("UPDATE bookmark SET timeInSeconds = ?, totalTimeInSeconds = ? WHERE idFile = ?", (Progress, Runtime, KodiFileId))
                    Update = True
            else:
                self.cursor.execute("DELETE FROM bookmark WHERE idFile = ? AND type = ?", (KodiFileId, "1"))
                Update = True
        elif Progress:
            Update = True
            self.cursor.execute("INSERT INTO bookmark(idFile, timeInSeconds, totalTimeInSeconds, player, type) VALUES (?, ?, ?, ?, ?)", (KodiFileId, Progress, Runtime, "VideoPlayer", 1))

        # Update playcounter and last played date
        self.cursor.execute("SELECT playCount FROM files WHERE idFile = ?", (KodiFileId,))
        Data = self.cursor.fetchone()

        if Data:
            CurrentPlayCount = Data[0]
            self.cursor.execute("UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?", (playcount, date_played, KodiFileId))

            if (CurrentPlayCount != playcount) and ((CurrentPlayCount and playcount and playcount -1 != CurrentPlayCount) or (not playcount and CurrentPlayCount) or (not CurrentPlayCount and playcount)):
                Update = True
        else:
            xbmc.log(f"EMBY.database.video_db: update_bookmark_playstate, idFile not found {KodiFileId}", 3) # LOGERROR

        return Update

    # countries
    def delete_links_countries(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM country_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_countries_and_links(self, ProductionLocations, media_id, media_type):
        SQLData = ()

        for CountryName in ProductionLocations:
            self.cursor.execute("SELECT country_id FROM country WHERE name = ?", (CountryName,))
            Data = self.cursor.fetchone()

            if Data:
                CountryId = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(country_id), 0) FROM country")
                CountryId = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO country(country_id, name) VALUES (?, ?)", (CountryId, CountryName))

            SQLData += ((CountryId, media_id, media_type),)

        if SQLData:
            self.cursor.executemany("INSERT OR REPLACE INTO country_link(country_id, media_id, media_type) VALUES (?, ?, ?)", SQLData)

        del SQLData

    # artwork
    def get_artwork(self, KodiItemId, ContentType, PrefixKey):
        Artwork = {}
        self.cursor.execute("SELECT type, url FROM art WHERE media_id = ? AND media_type = ?", (KodiItemId, ContentType))
        ArtworksData = self.cursor.fetchall()

        for ArtworkData in ArtworksData:
            Artwork[f"{PrefixKey}{ArtworkData[0]}"] = ArtworkData[1]

        return Artwork

    def get_artworks(self, KodiItemId, ContentType):
        self.cursor.execute("SELECT art_id, type, url FROM art WHERE media_id = ? and media_type = ?", (KodiItemId, ContentType))
        return self.cursor.fetchall()

    def update_artwork(self, ArtId, url):
        self.cursor.execute("UPDATE art SET url = ? WHERE art_id = ?", (url, ArtId))

    # settings
    def get_FileSettings(self, KodiFileId):
        self.cursor.execute("SELECT idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings WHERE idFile = ?", (KodiFileId,))
        return self.cursor.fetchone()

    # Download item
    def get_Fileinfo_by_SubcontentId(self, KodiId, KodiType):
        if KodiType == "season":
            self.cursor.execute("SELECT idEpisode, idFile, c00 FROM episode WHERE idSeason = ?", (KodiId,))
        else:
            self.cursor.execute("SELECT idEpisode, idFile, c00 FROM episode WHERE idShow = ?", (KodiId,))

        FileInfos = ()
        EpisodesInfo = self.cursor.fetchall()

        for EpisodeInfo in EpisodesInfo:
            if EpisodeInfo[2].endswith(" (download)"):
                continue

            self.cursor.execute("SELECT strFilename, idPath FROM files WHERE idFile = ?", (EpisodeInfo[1],))
            FileInfo = self.cursor.fetchone()

            if FileInfo:
                FileInfos += ((EpisodeInfo[0], FileInfo[1], EpisodeInfo[1], FileInfo[0], EpisodeInfo[2]),)

        return FileInfos

    def get_Fileinfo(self, KodiId, KodiType):
        if KodiType == "episode":
            self.cursor.execute("SELECT idFile, c00 FROM episode WHERE idEpisode = ?", (KodiId,))
        elif KodiType == "movie":
            self.cursor.execute("SELECT idFile, c00 FROM movie WHERE idMovie = ?", (KodiId,))
        elif KodiType == "musicvideo":
            self.cursor.execute("SELECT idFile, c00 FROM musicvideo WHERE idMVideo = ?", (KodiId,))

        ContentInfo = self.cursor.fetchone()

        if ContentInfo:
            self.cursor.execute("SELECT strFilename, idPath FROM files WHERE idFile = ?", (ContentInfo[0],))
            FileInfo = self.cursor.fetchone()

            if FileInfo:
                return ((KodiId, FileInfo[1], ContentInfo[0], FileInfo[0], ContentInfo[1]),)

        return ()

    def get_KodiId_FileName_by_SubcontentId(self, KodiId, KodiType):
        if KodiType == "season":
            self.cursor.execute("SELECT idEpisode, c18 FROM episode WHERE idSeason = ?", (KodiId,))
        else:
            self.cursor.execute("SELECT idEpisode, c18 FROM episode WHERE idShow = ?", (KodiId,))

        EpisodesData = self.cursor.fetchall()
        Data = ()

        for EpisodeData in EpisodesData:
            Data += ((EpisodeData[0], "".join("".join(EpisodeData[1].split("/")[-1:]).split("\\")[-1:])),)

        return Data

    def download_Subcontent(self, KodiEpisodeId, Download):
        ArtworksNoUrlParam = ()
        self.cursor.execute("SELECT idShow, idSeason FROM episode WHERE idEpisode = ?", (KodiEpisodeId,))
        EpisodeAdded = self.cursor.fetchone()

        if EpisodeAdded:
            SeasonComplete = True
            self.cursor.execute("SELECT c00 FROM episode WHERE idSeason = ?", (EpisodeAdded[1],)) # get all episodes from season
            SeasonEpisodes = self.cursor.fetchall()

            for SeasonEpisode in SeasonEpisodes:
                if not SeasonEpisode[0].endswith(" (download)"):
                    SeasonComplete = False
                    break

            if SeasonComplete and Download:
                self.update_Name(EpisodeAdded[1], "season", True)
                ArtworksNoUrlParam += self.download_Artwork(EpisodeAdded[1], "season", True)
            elif not SeasonComplete and not Download:
                self.update_Name(EpisodeAdded[1], "season", False)
                ArtworksNoUrlParam += self.download_Artwork(EpisodeAdded[1], "season", False)

            TVShowComplete = True
            self.cursor.execute("SELECT c00 FROM episode WHERE idShow = ?", (EpisodeAdded[0],)) # get all episodes from season
            TVShowEpisodes = self.cursor.fetchall()

            for TVShowEpisode in TVShowEpisodes:
                if not TVShowEpisode[0].endswith(" (download)"):
                    TVShowComplete = False
                    break

            if TVShowComplete and Download:
                self.update_Name(EpisodeAdded[0], "tvshow", True)
                ArtworksNoUrlParam += self.download_Artwork(EpisodeAdded[0], "tvshow", True)
            elif not TVShowComplete and not Download:
                self.update_Name(EpisodeAdded[0], "tvshow", False)
                ArtworksNoUrlParam += self.download_Artwork(EpisodeAdded[0], "tvshow", False)

        return ArtworksNoUrlParam

    def download_Artwork(self, KodiId, KodiType, Download):
        ArtworksNoUrlParam = ()
        SQLData = ()
        ArtworksData = self.get_artworks(KodiId, KodiType)

        for ArtworkData in ArtworksData:
            if ArtworkData[1] in ("poster", "thumb", "landscape"):
                if Download:
                    UrlMod = f"{ArtworkData[2]}-download|redirect-limit=1000&failonerror=false"
                else:
                    UrlMod = ArtworkData[2].replace("-download|redirect-limit=1000&failonerror=false", "")

                SQLData += ((UrlMod, ArtworkData[0]),)
                ArtworksNoUrlParam += ((ArtworkData[2].replace("|redirect-limit=1000&failonerror=false", ""),),)

        if SQLData:
            self.cursor.executemany("UPDATE art SET url = ? WHERE art_id = ?", SQLData)

        del SQLData
        return ArtworksNoUrlParam

    def replace_Path_ContentItem(self, KodiId, KodiType, KodiPath, KodiFilePath):
        if KodiType == "episode":
            self.cursor.execute("UPDATE episode SET c18 = ? WHERE idEpisode = ?", (KodiFilePath, KodiId))
        elif KodiType == "movie":
            self.cursor.execute("UPDATE movie SET c22 = ? WHERE idMovie = ?", (KodiPath, KodiId))
        elif KodiType == "musicvideo":
            self.cursor.execute("UPDATE musicvideo SET c13 = ? WHERE idMVideo = ?", (KodiPath, KodiId))

    def update_Name(self, KodiId, KodiType, isDownloaded):
        if KodiType == "season":
            self.cursor.execute("SELECT name FROM seasons WHERE idSeason = ?", (KodiId,))
        elif KodiType == "tvshow":
            self.cursor.execute("SELECT c00, c15 FROM tvshow WHERE idShow = ?", (KodiId,))
        elif KodiType == "episode":
            self.cursor.execute("SELECT c00 FROM episode WHERE idEpisode = ?", (KodiId,))
        elif KodiType == "movie":
            self.cursor.execute("SELECT c00, c10 FROM movie WHERE idMovie = ?", (KodiId,))
        elif KodiType == "musicvideo":
            self.cursor.execute("SELECT c00 FROM musicvideo WHERE idMVideo = ?", (KodiId,))

        NameChanged = False
        CurrentName = self.cursor.fetchone()

        if CurrentName:
            if isDownloaded:
                NewName = f"{CurrentName[0]} (download)"
            else:
                NewName = CurrentName[0].replace(" (download)", "")

            NameChanged = bool(CurrentName[0] != NewName)

            if NameChanged:
                if KodiType == "season":
                    self.cursor.execute("UPDATE seasons SET name = ? WHERE idSeason = ?", (NewName, KodiId))
                elif KodiType == "tvshow":
                    if isDownloaded:
                        NewSortName = f"{CurrentName[1]} (download)"
                    else:
                        NewSortName = CurrentName[1].replace(" (download)", "")

                    self.cursor.execute("UPDATE tvshow SET c00 = ?, c15 = ? WHERE idShow = ?", (NewName, NewSortName, KodiId))
                elif KodiType == "episode":
                    self.cursor.execute("UPDATE episode SET c00 = ? WHERE idEpisode = ?", (NewName, KodiId))
                elif KodiType == "movie":
                    if isDownloaded:
                        NewSortName = f"{CurrentName[1]} (download)"
                    else:
                        NewSortName = CurrentName[1].replace(" (download)", "")

                    self.cursor.execute("UPDATE movie SET c00 = ?, c10 = ? WHERE idMovie = ?", (NewName, NewSortName, KodiId))
                elif KodiType == "musicvideo":
                    self.cursor.execute("UPDATE musicvideo SET c00 = ? WHERE idMVideo = ?", (NewName, KodiId))

        return NameChanged

    def delete_Subcontent_download_tags(self, KodiEpisodeId):
        self.cursor.execute("SELECT idShow, idSeason FROM episode WHERE idEpisode = ?", (KodiEpisodeId,))
        EpisodesData = self.cursor.fetchone()
        KodiTVShowId = 0
        KodiSeasonId = 0

        if EpisodesData:
            if self.update_Name(EpisodesData[0], "tvshow", False):
                KodiTVShowId = EpisodesData[0]

            if self.update_Name(EpisodesData[1], "season", False):
                KodiSeasonId = EpisodesData[1]

        return KodiTVShowId, KodiSeasonId

    def get_Path(self, KodiPathId):
        self.cursor.execute("SELECT strPath FROM path WHERE idPath = ?", (KodiPathId,))
        Path = self.cursor.fetchone()

        if Path:
            return Path[0]

        return ""

    def replace_PathId(self, KodiFileId, KodiPathId):
        self.cursor.execute("UPDATE files SET idPath = ? WHERE idFile = ?", (KodiPathId, KodiFileId))

    def replace_Path(self, OldPath, NewPath):
        self.cursor.execute("UPDATE path SET strPath = ? WHERE strPath = ?", (NewPath, OldPath))

    def get_Progress_by_KodiType_KodiId(self, KodiType, KodiId):
        if KodiType == "movie":
            self.cursor.execute("SELECT idFile FROM movie WHERE idMovie = ?", (KodiId,))
        elif KodiType == "episode":
            self.cursor.execute("SELECT idFile FROM episode WHERE idEpisode = ?", (KodiId,))
        elif KodiType == "musicvideo":
            self.cursor.execute("SELECT idFile FROM musicvideo WHERE idMVideo = ?", (KodiId,))
        else:
            return 0

        KodiFileId = self.cursor.fetchone()

        if KodiFileId:
            self.cursor.execute("SELECT timeInSeconds FROM bookmark WHERE idFile = ? AND type = ?", (KodiFileId[0], 1))
            Progress = self.cursor.fetchone()

            if Progress:
                return Progress[0]

        return 0

    def get_Progress(self, KodiFileId):
        self.cursor.execute("SELECT playCount, lastPlayed FROM files WHERE idFile = ?", (KodiFileId,))
        FileInfo = self.cursor.fetchone()

        if FileInfo:
            self.cursor.execute("SELECT timeInSeconds FROM bookmark WHERE idFile = ? AND type = ?", (KodiFileId, 1))
            Progress = self.cursor.fetchone()

            if Progress:
                return True, Progress[0], FileInfo[0], FileInfo[1]

            return True, 0, FileInfo[0], FileInfo[1]

        return False, None, None, None

    # Path
    def delete_path(self, Path):
        self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))

    def toggle_path(self, OldPath, NewPath):
        QuotedNew = NewPath != "/emby_addon_mode/"
        QuotedOld = OldPath != "/emby_addon_mode/"
        self.cursor.execute("SELECT idFile, strFilename FROM files")
        FileNames = self.cursor.fetchall()

        if FileNames:
            SQLData = len(FileNames) * [()] # pre allocate memory

            for Index, FileName in enumerate(FileNames):
                if QuotedNew:
                    if QuotedOld:
                        FileNameNew = FileName[1]
                    else:
                        FileNameNew = quote(FileName[1])
                else:
                    if QuotedOld:
                        FileNameNew = unquote(FileName[1])
                    else:
                        FileNameNew = FileName[1]

                SQLData[Index] = (FileNameNew, FileName[0])

            self.cursor.executemany("UPDATE files SET strFilename = ? WHERE idFile = ?", SQLData)
            del SQLData

        self.cursor.execute("SELECT idPath, strPath FROM path")
        Pathes = self.cursor.fetchall()

        if Pathes:
            SQLData = len(Pathes) * [()] # pre allocate memory
            Index = 0

            for Path in Pathes:
                if Path[1].startswith(OldPath):
                    PathMod = common_db.toggle_path(Path[1], NewPath)
                    SQLData[Index] = (PathMod, Path[0])
                    Index += 1

            if Index:
                SQLData = SQLData[:Index]
                self.cursor.executemany("UPDATE path SET strPath = ? WHERE idPath = ?", SQLData)

            del SQLData

        self.cursor.execute("SELECT idMovie, c19, c22 FROM movie")
        Pathes = self.cursor.fetchall()

        if Pathes:
            SQLData = len(Pathes) * [()] # pre allocate memory
            SQLData1 = len(Pathes) * [()] # pre allocate memory
            Index = 0
            Index1 = 0

            for Path in Pathes:
                if Path[1] and Path[1].startswith(OldPath):
                    PathMod = common_db.toggle_path(Path[1], NewPath)
                    SQLData[Index] = (PathMod, Path[0])
                    Index += 1

                if Path[2].startswith(OldPath):
                    PathMod = common_db.toggle_path(Path[2], NewPath)
                    SQLData1[Index1] = (PathMod, Path[0])
                    Index1 += 1

            if Index:
                SQLData = SQLData[:Index]
                self.cursor.executemany("UPDATE movie SET c19 = ? WHERE idMovie = ?", SQLData)

            if Index1:
                SQLData1 = SQLData1[:Index1]
                self.cursor.executemany("UPDATE movie SET c22 = ? WHERE idMovie = ?", SQLData1)

            del SQLData
            del SQLData1

        self.cursor.execute("SELECT idEpisode, c18 FROM episode")
        Pathes = self.cursor.fetchall()

        if Pathes:
            SQLData = len(Pathes) * [()] # pre allocate memory
            Index = 0

            for Path in Pathes:
                if Path[1].startswith(OldPath):
                    PathMod = common_db.toggle_path(Path[1], NewPath)
                    SQLData[Index] = (PathMod, Path[0])
                    Index += 1

            if Index:
                SQLData = SQLData[:Index]
                self.cursor.executemany("UPDATE episode SET c18 = ? WHERE idEpisode = ?", SQLData)

            del SQLData

        self.cursor.execute("SELECT idMVideo, c13 FROM musicvideo")
        Pathes = self.cursor.fetchall()

        if Pathes:
            SQLData = len(Pathes) * [()] # pre allocate memory
            Index = 0

            for Path in Pathes:
                if Path[1].startswith(OldPath):
                    PathMod = common_db.toggle_path(Path[1], NewPath)
                    SQLData[Index] = (PathMod, Path[0])
                    Index += 1

            if Index:
                SQLData = SQLData[:Index]
                self.cursor.executemany("UPDATE musicvideo SET c13 = ? WHERE idMVideo = ?", SQLData)

            del SQLData

    def get_add_path(self, Path, MediaType, LinkId=None):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        KodiPathId = self.cursor.fetchone()[0] + 1

        if MediaType:
            self.cursor.execute("INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate, idParentPath) VALUES (?, ?, ?, ?, ?, ?)", (KodiPathId, Path, MediaType, 'metadata.local', 1, LinkId))
        else:
            self.cursor.execute("INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate, idParentPath) VALUES (?, ?, ?, ?, ?, ?)", (KodiPathId, Path, MediaType, None, 1, LinkId))

        return KodiPathId

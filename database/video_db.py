import xbmc
from helper import utils
from . import common_db

if utils.KodiMajorVersion == "19":
    from . import video_db_kodi19 as video_db_kodiversion
else:
    from . import video_db_kodi20 as video_db_kodiversion

FavoriteTags = {"Favorite movies": None, "Favorite musicvideos": None, "Favorite tvshows": None, "Favorite episodes": None}

class VideoDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def add_Index(self):
        # Index
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_actor_name_art_urls_NOCASE on actor (name COLLATE NOCASE, art_urls COLLATE NOCASE)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_strFilename on files (strFilename)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_dateAdded on files (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_lastPlayed on files (lastPlayed)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_playCount on files (playCount)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmark_type on bookmark (type)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_bookmark_timeInSeconds on bookmark (timeInSeconds)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating_rating on rating (rating)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_episode_c12 on episode (c12)")

    # playcount
    def get_playcount(self, KodiFileId):
        self.cursor.execute("SELECT playCount FROM files WHERE idFile = ?", (KodiFileId,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return -1

    # movies
    def add_movie(self, KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate, Filename, DateCreated, PlayCount, LastPlayedDate, idSet):
        self.cursor.execute("INSERT INTO movie (idMovie, idFile, c00, c01, c02, c03, c05, c06, c08, c09, c10, c11, c12, c14, c15, c16, c18, c19, c20, c21, c22, c23, premiered, c02, c13, idSet) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, " / ".join(Writers), Poster, Unique, SortName, int(RunTimeTicks), OfficialRating, Genre, " / ".join(Directors), OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate, "", 0, idSet))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_movie_entry(self):
        self.cursor.execute("SELECT coalesce(max(idMovie), 0) FROM movie")
        return self.cursor.fetchone()[0] + 1

    def delete_movie(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_movie_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        return video_db_kodiversion.get_movie_metadata_for_listitem(kodi_id, PathAndFilename, self.cursor, self.get_artwork, self.get_people_artwork)

    # musicvideo
    def add_musicvideos(self, KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate, DateCreated, PlayCount, LastPlayedDate, Filename):
        self.cursor.execute("INSERT INTO musicvideo (idMVideo, idFile, c00, c01, c04, c05, c06, c08, c09, c10, c11, c12, c13, c14, premiered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Poster, int(RunTimeTicks), " / ".join(Directors), Studio, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_entry_musicvideos(self):
        self.cursor.execute("SELECT coalesce(max(idMVideo), 0) FROM musicvideo")
        return self.cursor.fetchone()[0] + 1

    def delete_musicvideos(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_musicvideos_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        return video_db_kodiversion.get_musicvideos_metadata_for_listitem(kodi_id, PathAndFilename, self.cursor, self.get_artwork, self.get_people_artwork)

    # tvshow
    def update_tvshow(self, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, idShow, Trailer):
        self.cursor.execute("UPDATE tvshow SET c00 = ?, c01 = ?, c02 = ?, c04 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c11 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, duration = ?, c16 = ? WHERE idShow = ?", (c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, Trailer, idShow))

    def add_tvshow(self, idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, Trailer):
        self.cursor.execute("INSERT INTO tvshow(idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, c10, c16) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, "", Trailer))

    def create_entry_tvshow(self):
        self.cursor.execute("SELECT coalesce(max(idShow), 0) FROM tvshow")
        return self.cursor.fetchone()[0] + 1

    def delete_tvshow(self, idShow):
        self.cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (idShow,))

    def add_link_tvshow(self, idShow, idPath):
        self.cursor.execute("INSERT OR REPLACE INTO tvshowlinkpath(idShow, idPath) VALUES (?, ?)", (idShow, idPath))

    def delete_link_tvshow(self, idShow):
        self.cursor.execute("DELETE FROM tvshowlinkpath WHERE idShow = ?", (idShow,))

    def get_next_episodesIds(self, TagId):
        self.cursor.execute("SELECT media_id FROM tag_link WHERE tag_id = ? AND media_type = ?", (TagId, "tvshow"))
        TvShowIds = self.cursor.fetchall()
        NextEpisodeInfos = ()

        for idShow in TvShowIds:
            self.cursor.execute("SELECT idEpisode, idFile, c12, playCount, lastPlayed FROM episode_view WHERE idShow = ? ORDER BY CAST(c12 AS INT) ASC, CAST(c13 AS INT) ASC", (idShow[0],))
            Episodes = self.cursor.fetchall()
            LastPlayedItem = ("", -1) # timestamp, Id
            NextEpisodeForTVShow = "-1"

            for Episode in Episodes:
                if Episode[2] == "0": # Skip special seasons
                    continue

                if Episode[3] and Episode[4] and Episode[4] > LastPlayedItem[0]:
                    NextEpisodeForTVShow = ""
                    LastPlayedItem = (Episode[4], Episode[0])

                if not NextEpisodeForTVShow and NextEpisodeForTVShow != "-1" and not Episode[3]:
                    NextEpisodeForTVShow = f"{LastPlayedItem[0]};{Episode[0]}"

            if NextEpisodeForTVShow and NextEpisodeForTVShow != "-1":
                NextEpisodeInfos += (NextEpisodeForTVShow,)

        NextEpisodeInfos = sorted(NextEpisodeInfos, reverse=True)
        return NextEpisodeInfos

    def get_tvshows_metadata_for_listitem(self, kodi_id):
        return video_db_kodiversion.get_tvshows_metadata_for_listitem(kodi_id, self.cursor, self.get_artwork, self.get_people_artwork)

    # seasons
    def add_season(self, idSeason, idShow, season, name):
        self.cursor.execute("INSERT OR REPLACE INTO seasons(idSeason, idShow, season, name) VALUES (?, ?, ?, ?)", (idSeason, idShow, season, name)) # IGNORE required for stacked content

    def update_season(self, idShow, season, name, idSeason):
        self.cursor.execute("UPDATE seasons SET idShow = ?, season = ?, name = ? WHERE idSeason = ?", (idShow, season, name, idSeason))

    def create_entry_season(self):
        self.cursor.execute("SELECT coalesce(max(idSeason), 0) FROM seasons")
        return self.cursor.fetchone()[0] + 1

    def delete_season(self, idSeason):
        self.cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (idSeason,))

    def get_season_metadata_for_listitem(self, kodi_id):
        return video_db_kodiversion.get_season_metadata_for_listitem(kodi_id, self.cursor, self.get_artwork, self.get_people_artwork)

    # episode
    def add_episode(self, KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, Filename, DateCreated, PlayCount, LastPlayedDate):
        self.cursor.execute("INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c06, c09, c10, c12, c13, c14, c15, c16, c18, c19, c20, idShow, idSeason, c11, c17) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, RatingId, " / ".join(Writers), PremiereDate, Poster, int(RunTimeTicks), " / ".join(Directors), ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, "", -1))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_entry_episode(self):
        self.cursor.execute("SELECT coalesce(max(idEpisode), 0) FROM episode")
        return self.cursor.fetchone()[0] + 1

    def delete_episode(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_episode_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        return video_db_kodiversion.get_episode_metadata_for_listitem(kodi_id, PathAndFilename, self.cursor, self.get_artwork, self.get_people_artwork)

    # boxsets
    def add_boxset(self, strSet, strOverview):
        self.cursor.execute("SELECT coalesce(max(idSet), 0) FROM sets")
        set_id =  self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO sets(idSet, strSet, strOverview) VALUES (?, ?, ?)", (set_id, strSet, strOverview))
        return set_id

    def update_boxset(self, strSet, strOverview, idSet):
        self.cursor.execute("UPDATE sets SET strSet = ?, strOverview = ? WHERE idSet = ?", (strSet, strOverview, idSet))

    def set_boxset(self, idSet, idMovie):
        self.cursor.execute("UPDATE movie SET idSet = ? WHERE idMovie = ?", (idSet, idMovie))

    def remove_from_boxset(self, idMovie):
        self.cursor.execute("UPDATE movie SET idSet = null WHERE idMovie = ?", (idMovie,))

    def delete_boxset(self, idSet):
        self.cursor.execute("DELETE FROM sets WHERE idSet = ?", (idSet,))

    def get_boxset_metadata_for_listitem(self, kodi_id):
        return video_db_kodiversion.get_boxset_metadata_for_listitem(kodi_id, self.cursor, self.get_artwork)

    # file
    def add_file(self, path_id, filename, dateAdded, file_id, PlayCount, LastPlayedDate):
        if not PlayCount:
            PlayCount = None

        self.cursor.execute("INSERT INTO files(idPath, strFilename, dateAdded, idFile, playCount, lastPlayed) VALUES (?, ?, ?, ?, ?, ?)", (path_id, filename, dateAdded, file_id, PlayCount, LastPlayedDate))

    def create_entry_file(self):
        self.cursor.execute("SELECT coalesce(max(idFile), 0) FROM files")
        return self.cursor.fetchone()[0] + 1

    # people
    def delete_links_actors(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM actor_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def delete_links_director(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM director_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def delete_links_writer(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM writer_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_people_and_links(self, people, KodiId, MediaType):
        cast_order = 0

        for person in people:
            if 'Name' not in person:
                continue

            if 'Role' in person:
                role = person['Role']
            else:
                role = person['Type']

            # Unique persons assignment for each Emby library
            if (MediaType == "movie" and utils.uniquepeoplemovies) or (MediaType == "tvshow" and utils.uniquepeopletvshows) or (MediaType == "episode" and utils.uniquepeopleepisodes) or (MediaType == "musicvideo" and utils.uniquepeoplemusicvideos):
                ImageURL = f"{person['imageurl']}-unique"
                self.cursor.execute("SELECT actor_id, name, art_urls FROM actor WHERE name LIKE ? COLLATE NOCASE AND  art_urls LIKE ? COLLATE NOCASE", (f"{person['Name']}%%", f"%%p-{person['Id']}%%{person['LibraryId']}%%-unique"))
            else: # global persons assignment to Emby libraries
                ImageURL = f"{person['imageurl']}-shared"
                self.cursor.execute("SELECT actor_id, name, art_urls FROM actor WHERE name LIKE ? COLLATE NOCASE AND  art_urls LIKE ? COLLATE NOCASE", (f"{person['Name']}%%", f"%%p-{person['Id']}%%-shared"))

            Data = self.cursor.fetchone()

            if Data:
                if ImageURL != Data[1]: # update artwork
                    self.cursor.execute("UPDATE actor SET art_urls = ? WHERE actor_id = ?", (ImageURL, Data[0]))
                    self.cursor.execute("UPDATE art SET url = ? WHERE media_id = ? AND type = ? AND media_type = ? ", (ImageURL, Data[0], "thumb", person['Type'].lower()))

                NewPersion = False
                person_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(actor_id), 0) FROM actor")
                person_id = self.cursor.fetchone()[0] + 1
                PersonNameMod = person['Name']

                while True:
                    try:
                        self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (person_id, PersonNameMod, ImageURL))
                        break
                    except Exception as Error:
                        xbmc.log(f"EMBY.database.video_db: Duplicate PersonName detected: {PersonNameMod} / {Error}", 2) # LOGWARNING
                        PersonNameMod += " "

                NewPersion = True

            if person['Type'] == 'Director':
                self.cursor.execute("INSERT OR REPLACE INTO director_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))
            elif person['Type'] == 'Writer':
                self.cursor.execute("INSERT OR REPLACE INTO writer_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))
            else:
                self.cursor.execute("INSERT OR REPLACE INTO actor_link(actor_id, media_id, media_type, role, cast_order) VALUES (?, ?, ?, ?, ?)", (person_id, KodiId, MediaType, role, cast_order))
                cast_order += 1

            if NewPersion:
                self.cursor.execute("INSERT OR REPLACE INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (person_id, person['Type'].lower(), "thumb", ImageURL))

    def get_people_artwork(self, KodiId, ContentType):
        People = ()
        PeopleCounter = 0
        self.cursor.execute("SELECT * FROM actor_link WHERE media_id = ? and media_type = ?", (KodiId, ContentType))
        ActorLinks = self.cursor.fetchall()

        for ActorLink in ActorLinks:
            self.cursor.execute("SELECT * FROM actor WHERE actor_id = ?", (ActorLink[0],))
            Actor = self.cursor.fetchone()
            People += ((Actor[1], ActorLink[3], PeopleCounter, Actor[2]),)
            PeopleCounter += 1

        self.cursor.execute("SELECT * FROM director_link WHERE media_id = ? and media_type = ?", (KodiId, ContentType))
        DirectorLinks = self.cursor.fetchall()

        for DirectorLink in DirectorLinks:
            self.cursor.execute("SELECT * FROM actor WHERE actor_id = ?", (DirectorLink[0],))
            Actor = self.cursor.fetchone()
            People += ((Actor[1], "Director", PeopleCounter, Actor[2]),)
            PeopleCounter += 1

        return People

    # streams
    def delete_streams(self, file_id):
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (file_id,))

    def add_streams(self, file_id, videostream, audiostream, subtitlestream, runtime):
        video_db_kodiversion.add_streams(self.cursor, file_id, videostream, audiostream, subtitlestream, runtime)

    # settings
    def get_settings(self, idFile):
        self.cursor.execute("SELECT Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, DeinterlaceMode, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings WHERE idFile = ?", (idFile,))
        Data = self.cursor.fetchone()

        if Data:
            return {"Deinterlace": Data[0], "ViewMode": Data[1], "ZoomAmount": Data[2], "PixelRatio": Data[3], "VerticalShift": Data[4], "AudioStream": Data[5], "SubtitleStream": Data[6], "SubtitleDelay": Data[7], "SubtitlesOn": Data[8], "Brightness": Data[9], "Contrast": Data[10], "Gamma": Data[11], "VolumeAmplification": Data[12], "AudioDelay": Data[13], "ResumeTime": Data[14], "Sharpness": Data[15], "NoiseReduction": Data[16], "NonLinStretch": Data[17], "PostProcess": Data[18], "ScalingMethod": Data[19], "DeinterlaceMode": Data[20], "StereoMode": Data[21], "StereoInvert": Data[22], "VideoStream": Data[23], "TonemapMethod": Data[24], "TonemapParam": Data[25], "Orientation": Data[26], "CenterMixLevel": Data[27]}

        return {}

    def add_settings(self, idFile, Settings):
        self.cursor.execute("INSERT OR REPLACE INTO settings(idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, DeinterlaceMode, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idFile, Settings['Deinterlace'], Settings['ViewMode'], Settings['ZoomAmount'], Settings['PixelRatio'], Settings['VerticalShift'], Settings['AudioStream'], Settings['SubtitleStream'], Settings['SubtitleDelay'], Settings['SubtitlesOn'], Settings['Brightness'], Settings['Contrast'], Settings['Gamma'], Settings['VolumeAmplification'], Settings['AudioDelay'], Settings['ResumeTime'], Settings['Sharpness'], Settings['NoiseReduction'], Settings['NonLinStretch'], Settings['PostProcess'], Settings['ScalingMethod'], Settings['DeinterlaceMode'], Settings['StereoMode'], Settings['StereoInvert'], Settings['VideoStream'], Settings['TonemapMethod'], Settings['TonemapParam'], Settings['Orientation'], Settings['CenterMixLevel']))

    # stacked times
    def delete_stacktimes(self, file_id):
        self.cursor.execute("DELETE FROM stacktimes WHERE idFile = ?", (file_id,))

    def add_stacktimes(self, idFile, times):
        self.cursor.execute("INSERT OR REPLACE INTO stacktimes(idFile, times) VALUES (?, ?)", (idFile, times))

    # tags
    def get_add_tag(self, Name):
        TagId = self.get_tag(Name)

        if not TagId:
            self.cursor.execute("SELECT coalesce(max(tag_id), 0) FROM tag")
            TagId = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO tag(tag_id, name) VALUES (?, ?)", (TagId, Name))

        return TagId

    def delete_tag(self, Name):
        self.cursor.execute("DELETE FROM tag WHERE name = ?", (Name,))

    def get_tag(self, Name):
        self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (Name,))
        Data = self.cursor.fetchone()

        if Data:
            tag_id = Data[0]
        else:
            tag_id = None

        return tag_id

    def add_link_tag(self, TagId, MediaId, MediaType):
        self.cursor.execute("INSERT OR REPLACE INTO tag_link(tag_id, media_id, media_type) VALUES (?, ?, ?)", (TagId, MediaId, MediaType)) # IGNORE required for stacked content

    def delete_links_tags(self, MediaId, MediaType):
        self.cursor.execute("DELETE FROM tag_link WHERE media_id = ? AND media_type = ?", (MediaId, MediaType))

    # tags, links
    def add_tags_and_links(self, MediaId, MediaType, Tags):
        for Tag in Tags:
            TagId = self.get_add_tag(Tag['Name'])
            self.add_link_tag(TagId, MediaId, MediaType)

    # favorites
    def init_favorite_tags(self):
        for FavoriteTag in FavoriteTags:
            self.cursor.execute("SELECT tag_id FROM tag WHERE name = ?", (FavoriteTag,))
            Data = self.cursor.fetchone()

            if Data:
                tag_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(tag_id), 0) FROM tag")
                tag_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO tag(tag_id, name) VALUES (?, ?)", (tag_id, FavoriteTag))

            globals()["FavoriteTags"][FavoriteTag] = tag_id

    def set_Favorite(self, IsFavorite, KodiItemId, MediaType):
        if IsFavorite:
            self.add_link_tag(FavoriteTags[f"Favorite {MediaType}s"], KodiItemId, MediaType)
        else:
            self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ? AND media_type = ? AND media_id = ?", (FavoriteTags[f"Favorite {MediaType}s"], MediaType, KodiItemId))

    # genres
    def delete_links_genres(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM genre_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_genres_and_links(self, Genres, media_id, media_type):
        for Genre in Genres:
            self.cursor.execute("SELECT genre_id FROM genre WHERE name = ?", (Genre,))
            Data = self.cursor.fetchone()

            if Data:
                genre_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(genre_id), 0) FROM genre")
                genre_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO genre(genre_id, name) VALUES (?, ?)", (genre_id, Genre))

            self.cursor.execute("INSERT OR REPLACE INTO genre_link(genre_id, media_id, media_type) VALUES (?, ?, ?)", (genre_id, media_id, media_type))

    # studios
    def delete_links_studios(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM studio_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_studios_and_links(self, Studios, KodiId, MediaType):
        for Studio in Studios:
            self.cursor.execute("SELECT studio_id FROM studio WHERE name = ?", (Studio,))
            Data = self.cursor.fetchone()

            if Data:
                studio_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(studio_id), 0) FROM studio")
                studio_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO studio(studio_id, name) VALUES (?, ?)", (studio_id, Studio))

            self.cursor.execute("INSERT OR REPLACE INTO studio_link(studio_id, media_id, media_type) VALUES (?, ?, ?)", (studio_id, KodiId, MediaType))

    # ratings
    def delete_ratings(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM rating WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_ratings(self, KodiItemId, media_id, media_type, Rating):
        if Rating:
            self.cursor.execute("SELECT coalesce(max(rating_id), 0) FROM rating")
            rating_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO rating(rating_id, media_id, media_type, rating_type, rating, votes) VALUES (?, ?, ?, ?, ?, ?)", (rating_id, KodiItemId, media_id, media_type, Rating, 0))
            return rating_id

        return -1

    # uniqueid
    def delete_uniqueids(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM uniqueid WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_uniqueids(self, KodiItemId, ProviderIds, MediaId, DefaulId):
        UniqueId = -1

        for Provider, unique_id in list(ProviderIds.items()):
            Provider = Provider.lower()
            self.cursor.execute("SELECT coalesce(max(uniqueid_id), 0) FROM uniqueid")
            Unique = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO uniqueid(uniqueid_id, media_id, media_type, value, type) VALUES (?, ?, ?, ?, ?)", (Unique, KodiItemId, MediaId, unique_id, Provider))

            if Provider == DefaulId:
                UniqueId = Unique

        return UniqueId

    # bookmarks
    def get_bookmark_urls_all(self):
        self.cursor.execute("SELECT thumbNailImage FROM bookmark")
        return self.cursor.fetchall()

    def delete_bookmark(self, file_id):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (file_id,))

    def add_bookmark_chapter(self, KodiFileId, RunTimeTicks, Chapters):
        for Chapter in Chapters:
            self.cursor.execute("INSERT INTO bookmark(idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, type, playerState) VALUES (?, ?, ?, ?, ?, ?, ?)", (KodiFileId, Chapter['StartPositionTicks'], RunTimeTicks, Chapter['Image'], "VideoPlayer", 0, ""))

    def add_bookmark_playstate(self, KodiFileId, PlaybackPositionTicks, RunTimeTicks):
        if PlaybackPositionTicks:
            self.cursor.execute("INSERT INTO bookmark(idFile, timeInSeconds, totalTimeInSeconds, player, type, thumbNailImage, playerState) VALUES (?, ?, ?, ?, ?, ?, ?)", (KodiFileId, PlaybackPositionTicks, RunTimeTicks, "VideoPlayer", 1, "", ""))

    def update_bookmark_playstate(self, file_id, playcount, date_played, resume, Runtime):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ? AND type = ?", (file_id, "1"))
        self.cursor.execute("UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?", (playcount, date_played, file_id))

        if resume:
            self.cursor.execute("INSERT INTO bookmark(idFile, timeInSeconds, totalTimeInSeconds, player, type, thumbNailImage, playerState) VALUES (?, ?, ?, ?, ?, ?, ?)", (file_id, resume, Runtime, "VideoPlayer", 1, "", ""))

    # countries
    def delete_links_countries(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM country_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_countries_and_links(self, ProductionLocations, media_id, media_type):
        for CountryName in ProductionLocations:
            self.cursor.execute("SELECT country_id FROM country WHERE name = ?", (CountryName,))
            Data = self.cursor.fetchone()

            if Data:
                country_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(country_id), 0) FROM country")
                country_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO country(country_id, name) VALUES (?, ?)", (country_id, CountryName))

            self.cursor.execute("INSERT OR REPLACE INTO country_link(country_id, media_id, media_type) VALUES (?, ?, ?)", (country_id, media_id, media_type))

    # artwork
    def get_artwork(self, KodiId, ContentType, PrefixKey):
        Artwork = {}
        self.cursor.execute("SELECT * FROM art WHERE media_id = ? and media_type = ?", (KodiId, ContentType))
        ArtworksData = self.cursor.fetchall()

        for ArtworkData in ArtworksData:
            Artwork[f"{PrefixKey}{ArtworkData[3]}"] = ArtworkData[4]

        return Artwork

    # settings
    def get_FileSettings(self, KodiFileId):
        self.cursor.execute("SELECT idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings Where idFile = ?", (KodiFileId,))
        return self.cursor.fetchone()

    # Path
    def toggle_path(self, OldPath, NewPath):
        self.cursor.execute("SELECT idPath, strPath FROM path")
        Pathes = self.cursor.fetchall()

        for Path in Pathes:
            if Path[1].startswith(OldPath):
                PathMod = Path[1].replace(OldPath, NewPath)
                self.cursor.execute("UPDATE path SET strPath = ? WHERE idPath = ?", (PathMod, Path[0]))

        self.cursor.execute("SELECT idMovie, c22 FROM movie")
        Pathes = self.cursor.fetchall()

        for Path in Pathes:
            if Path[1].startswith(OldPath):
                PathMod = Path[1].replace(OldPath, NewPath)
                self.cursor.execute("UPDATE movie SET c22 = ? WHERE idMovie = ?", (PathMod, Path[0]))

        self.cursor.execute("SELECT idEpisode, c18 FROM episode")
        Pathes = self.cursor.fetchall()

        for Path in Pathes:
            if Path[1].startswith(OldPath):
                PathMod = Path[1].replace(OldPath, NewPath)
                self.cursor.execute("UPDATE episode SET c18 = ? WHERE idEpisode = ?", (PathMod, Path[0]))

        self.cursor.execute("SELECT idMVideo, c13 FROM musicvideo")
        Pathes = self.cursor.fetchall()

        for Path in Pathes:
            if Path[1].startswith(OldPath):
                PathMod = Path[1].replace(OldPath, NewPath)
                self.cursor.execute("UPDATE musicvideo SET c13 = ? WHERE idMVideo = ?", (PathMod, Path[0]))

    def get_add_path(self, Path, MediaType, LinkId=None):
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        path_id = self.cursor.fetchone()[0] + 1

        if MediaType:
            self.cursor.execute("INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate, idParentPath) VALUES (?, ?, ?, ?, ?, ?)", (path_id, Path, MediaType, 'metadata.local', 1, LinkId))
        else:
            self.cursor.execute("INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate, idParentPath) VALUES (?, ?, ?, ?, ?, ?)", (path_id, Path, MediaType, None, 1, LinkId))

        return path_id

    # Kodi workarounds for episode bookmark bugs
    # Subqueries are not possible to fix, e.g. browse by tag, genre, year, actor, etc. This would require a permutation (would exponetially grow database records)
    def add_episode_bookmark(self, KodiItemId, KodiSeasonId, KodiShowId, ChapterInfo, RunTimeTicks, DateCreated, PlayCount, LastPlayedDate): # workaround due to Kodi episode bookmark bug
        idPath = self.get_add_path("videodb://recentlyaddedepisodes/", None, None)
        FileId = self.create_entry_file()
        self.add_file(idPath, KodiItemId, DateCreated, FileId, PlayCount, LastPlayedDate)
        self.add_bookmark_chapter(FileId, RunTimeTicks, ChapterInfo)
        self.cursor.execute("SELECT season FROM seasons WHERE idSeason = ?", (KodiSeasonId,))
        Data = self.cursor.fetchone()

        if Data:
            SeasonNumber = Data[0]
            Path = f"videodb://tvshows/titles/{KodiShowId}/{SeasonNumber}/"
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.add_file(idPath, KodiItemId, DateCreated, FileId, PlayCount, LastPlayedDate)
                self.add_bookmark_chapter(FileId, RunTimeTicks, ChapterInfo)

            Path = f"videodb://tvshows/titles/{KodiShowId}/-2/" # -2 if this is the only season for the TV Show
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.add_file(idPath, KodiItemId, DateCreated, FileId, PlayCount, LastPlayedDate)
                self.add_bookmark_chapter(FileId, RunTimeTicks, ChapterInfo)

            Path = f"videodb://inprogresstvshows/{KodiShowId}/{SeasonNumber}/"
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.add_file(idPath, KodiItemId, DateCreated, FileId, PlayCount, LastPlayedDate)
                self.add_bookmark_chapter(FileId, RunTimeTicks, ChapterInfo)

            Path = f"videodb://inprogresstvshows/{KodiShowId}/-2/" # -2 if this is the only season for the TV Show
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.add_file(idPath, KodiItemId, DateCreated, FileId, PlayCount, LastPlayedDate)
                self.add_bookmark_chapter(FileId, RunTimeTicks, ChapterInfo)

    def add_season_bookmark(self, KodiShowId, SeasonNumber): # workaround due to Kodi episode bookmark bug
        Path = f"videodb://tvshows/titles/{KodiShowId}/{SeasonNumber}/"
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath, noUpdate) VALUES (?, ?)", (Path, "1"))

        Path = f"videodb://tvshows/titles/{KodiShowId}/-2/" # -2 if this is the only season for the TV Show
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath, noUpdate) VALUES (?, ?)", (Path, "1"))

        Path = f"videodb://inprogresstvshows/{KodiShowId}/{SeasonNumber}/"
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath, noUpdate) VALUES (?, ?)", (Path, "1"))

        Path = f"videodb://inprogresstvshows/{KodiShowId}/-2/" # -2 if this is the only season for the TV Show
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath, noUpdate) VALUES (?, ?)", (Path, "1"))

    def delete_season_bookmark(self, KodiSeasonId): # workaround due to Kodi episode bookmark bug
        self.cursor.execute("SELECT idShow, season FROM seasons WHERE idSeason = ?", (KodiSeasonId,))
        Data = self.cursor.fetchone()

        if Data:
            Path = f"videodb://tvshows/titles/{Data[0]}/{Data[1]}/"
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = f"videodb://tvshows/titles/{Data[0]}/-2/" # -2 if this is the only season for the TV Show
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = f"videodb://inprogresstvshows/{Data[0]}/{Data[1]}/"
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = f"videodb://inprogresstvshows/{Data[0]}/-2/" # -2 if this is the only season for the TV Show
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))

    def delete_episode_bookmark(self, KodiItemId, KodiFileId): # workaround due to Kodi episode bookmark bug
        self.cursor.execute("DELETE FROM path WHERE strPath = ?", (f"videodb://recentlyaddedepisodes/{KodiItemId}/",))
        self.cursor.execute("DELETE FROM files WHERE strFilename = ?", (KodiFileId,))

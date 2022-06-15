from . import common_db

FavoriteTags = {"Favorite movies": None, "Favorite musicvideos": None, "Favorite tvshows": None, "Favorite episodes": None}


class VideoDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def update_movie(self, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, Fanart, ProductionLocation, Path, KodiPathId, PremiereDate, KodiItemId, Filename, DateCreated, PlayCount, LastPlayedDate, KodiFileId):
        self.cursor.execute("UPDATE movie SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, c20 = ?, c21 = ?, c22 = ?, c23 = ?, premiered = ? WHERE idMovie = ?", (Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, Fanart, ProductionLocation, Path, KodiPathId, PremiereDate, KodiItemId))
        self.update_file(KodiPathId, Filename, DateCreated, PlayCount, LastPlayedDate, KodiFileId)

    def add_movie(self, KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate, Filename, DateCreated, PlayCount, LastPlayedDate):
        self.cursor.execute("INSERT INTO movie (idMovie, idFile, c00, c01, c02, c03, c05, c06, c08, c09, c10, c11, c12, c14, c15, c16, c18, c19, c20, c21, c22, c23, premiered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_movie_entry(self):
        self.cursor.execute("SELECT coalesce(max(idMovie), 0) FROM movie")
        return self.cursor.fetchone()[0] + 1

    def delete_movie(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    # musicvideo
    def update_musicvideos(self, Name, Poster, RunTimeTicks, Directors, Studio, ProductionYear, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate, KodiItemId, DateCreated, PlayCount, LastPlayedDate, KodiFileId, Filename):
        self.cursor.execute("UPDATE musicvideo SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c13 = ?, c14 = ?, premiered = ? WHERE idMVideo = ?", (Name, Poster, RunTimeTicks, Directors, Studio, ProductionYear, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate, KodiItemId))
        self.update_file(KodiPathId, Filename, DateCreated, PlayCount, LastPlayedDate, KodiFileId)

    def add_musicvideos(self, KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, ProductionYear, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate, DateCreated, PlayCount, LastPlayedDate, Filename):
        self.cursor.execute("INSERT INTO musicvideo (idMVideo, idFile, c00, c01, c04, c05, c06, c07, c08, c09, c10, c11, c12, c13, c14, premiered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, ProductionYear, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_entry_musicvideos(self):
        self.cursor.execute("SELECT coalesce(max(idMVideo), 0) FROM musicvideo")
        return self.cursor.fetchone()[0] + 1

    def delete_musicvideos(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    # tvshow
    def update_tvshow(self, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, idShow):
        self.cursor.execute("UPDATE tvshow SET c00 = ?, c01 = ?, c02 = ?, c04 = ?, c05 = ?, c06 = ?, c08 = ?, c09 = ?, c11 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, duration = ? WHERE idShow = ?", (c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration, idShow))

    def add_tvshow(self, idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration):
        self.cursor.execute("INSERT INTO tvshow(idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (idShow, c00, c01, c02, c04, c05, c06, c08, c09, c11, c12, c13, c14, c15, duration))

    def create_entry_tvshow(self):
        self.cursor.execute("SELECT coalesce(max(idShow), 0) FROM tvshow")
        return self.cursor.fetchone()[0] + 1

    def delete_tvshow(self, idShow):
        self.cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (idShow,))

    # seasons
    def create_entry_season(self):
        self.cursor.execute("SELECT coalesce(max(idSeason), 0) FROM seasons")
        return self.cursor.fetchone()[0] + 1

    def delete_season(self, idSeason):
        self.cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (idSeason,))

    # episode
    def add_episode(self, KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, Filename, DateCreated, PlayCount, LastPlayedDate):
        self.cursor.execute("INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c06, c09, c10, c12, c13, c14, c15, c16, c18, c19, c20, idShow, idSeason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def update_episode(self, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, KodiItemId, Filename, DateCreated, PlayCount, LastPlayedDate, KodiFileId):
        self.cursor.execute("UPDATE episode SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?, c09 = ?, c10 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, c20 = ?, idShow = ?, idSeason = ? WHERE idEpisode = ?", (Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, KodiItemId))
        self.update_file(KodiPathId, Filename, DateCreated, PlayCount, LastPlayedDate, KodiFileId)

    def create_entry_episode(self):
        self.cursor.execute("SELECT coalesce(max(idEpisode), 0) FROM episode")
        return self.cursor.fetchone()[0] + 1

    def delete_episode(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

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

    def add_season(self, idSeason, idShow, season, name):
        self.cursor.execute("INSERT OR IGNORE INTO seasons(idSeason, idShow, season, name) VALUES (?, ?, ?, ?)", (idSeason, idShow, season, name)) # IGNORE required for stacked content

    def update_season(self, idShow, season, name, idSeason):
        self.cursor.execute("UPDATE seasons SET idShow = ?, season = ?, name = ? WHERE idSeason = ?", (idShow, season, name, idSeason))

    def create_entry_file(self):
        self.cursor.execute("SELECT coalesce(max(idFile), 0) FROM files")
        return self.cursor.fetchone()[0] + 1

    def add_link_tvshow(self, idShow, idPath):
        self.cursor.execute("INSERT OR IGNORE INTO tvshowlinkpath(idShow, idPath) VALUES (?, ?)", (idShow, idPath))

    def delete_link_tvshow(self, idShow):
        self.cursor.execute("DELETE FROM tvshowlinkpath WHERE idShow = ?", (idShow,))

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

    def add_file(self, path_id, filename, dateAdded, file_id, PlayCount, LastPlayedDate):
        if not PlayCount:
            PlayCount = None

        self.cursor.execute("INSERT INTO files(idPath, strFilename, dateAdded, idFile, playCount, lastPlayed) VALUES (?, ?, ?, ?, ?, ?)", (path_id, filename, dateAdded, file_id, PlayCount, LastPlayedDate))

    def update_file(self, path_id, filename, dateAdded, PlayCount, LastPlayedDate, file_id):
        if not PlayCount:
            PlayCount = None

        self.cursor.execute("UPDATE files SET idPath = ?, strFilename = ?, dateAdded = ?, playCount = ?, lastPlayed = ? WHERE idFile = ?", (path_id, filename, dateAdded, PlayCount, LastPlayedDate, file_id))

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

            role = person.get('Role')

            if role == "MusicVideoArtist":
                person_id, NewPersion = self.add_get_person(person['Name'], person['imageurl'], person['LibraryId'])
            else:
                person_id, NewPersion = self.add_get_person(person['Name'], person['imageurl'], False)

            if person['Type'] == 'Actor':
                self.cursor.execute("INSERT OR IGNORE INTO actor_link(actor_id, media_id, media_type, role, cast_order) VALUES (?, ?, ?, ?, ?)", (person_id, KodiId, MediaType, role, cast_order))
                cast_order += 1
            elif person['Type'] == 'Director':
                self.cursor.execute("INSERT OR IGNORE INTO director_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))
            elif person['Type'] == 'Writer':
                self.cursor.execute("INSERT OR IGNORE INTO writer_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))

            if NewPersion:
                if person['imageurl']:
                    self.cursor.execute("INSERT OR IGNORE INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (person_id, person['Type'].lower(), "thumb", person['imageurl']))

    def add_get_person(self, PersonName, imageurl, LibraryId):
        if LibraryId: # Unify Artist by LibraryId (Allow duplicates for multi Musicvideo Libraries)
            self.cursor.execute("SELECT actor_id, name FROM actor WHERE name LIKE ? AND art_urls LIKE ?", ("%s%%" % PersonName, "%%%s%%" % LibraryId))
            Data = self.cursor.fetchall()

            for Info in Data:
                CompareName = Info[1].rstrip()

                if CompareName == PersonName:
                    return Info[0], False
        else:
            self.cursor.execute("SELECT actor_id FROM actor WHERE name = ? ", (PersonName,))
            Data = self.cursor.fetchone()

            if Data:
                return Data[0], False

        self.cursor.execute("SELECT coalesce(max(actor_id), 0) FROM actor")
        person_id = self.cursor.fetchone()[0] + 1

        if LibraryId:
             # Unify Artist by LibraryId (Allow duplicates for multi Musicvideo Libraries)
            try:
                self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (person_id, PersonName, imageurl))
            except:
                while True:
                    PersonName += " "

                    try:
                        self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (person_id, PersonName, imageurl))
                    except:
                        continue

                    break
        else:
            self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (person_id, PersonName, imageurl))

        return person_id, True

    # streams
    def delete_streams(self, file_id):
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (file_id,))

    def add_streams(self, file_id, videostream, audiostream, subtitlestream, runtime):
        for track in videostream:
            track['KodiFileId'] = file_id
            track['Runtime'] = runtime
            self.cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth, iVideoHeight, iVideoDuration, strStereoMode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (track['KodiFileId'], 0, track['codec'], track['aspect'], track['width'], track['height'], track['Runtime'], track['3d']))

        for track in audiostream:
            track['KodiFileId'] = file_id
            self.cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage) VALUES (?, ?, ?, ?, ?)", (track['KodiFileId'], 1, track['codec'], track['channels'], track['language']))

        for track in subtitlestream:
            self.cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strSubtitleLanguage) VALUES (?, ?, ?)", (file_id, 2, track))

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
        self.cursor.execute("DELETE FROM tag WHERE name = ? ", (Name,))

    def get_tag(self, Name):
        self.cursor.execute("SELECT tag_id FROM tag WHERE name = ? ", (Name,))
        Data = self.cursor.fetchone()

        if Data:
            tag_id = Data[0]
        else:
            tag_id = None

        return tag_id

    def add_link_tag(self, TagId, MediaId, MediaType):
        self.cursor.execute("INSERT OR IGNORE INTO tag_link(tag_id, media_id, media_type) VALUES (?, ?, ?)", (TagId, MediaId, MediaType)) # IGNORE required for stacked content

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
            self.cursor.execute("SELECT tag_id FROM tag WHERE name = ? ", (FavoriteTag,))
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
            self.add_link_tag(FavoriteTags["Favorite %ss" % MediaType], KodiItemId, MediaType)
        else:
            self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ? AND media_id = ? AND media_type = ?", (FavoriteTags["Favorite %ss" % MediaType], KodiItemId, MediaType))

    # genres
    def delete_links_genres(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM genre_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_genres_and_links(self, Genres, media_id, media_type):
        for Genre in Genres:
            self.cursor.execute("SELECT genre_id FROM genre WHERE name = ? ", (Genre,))
            Data = self.cursor.fetchone()

            if Data:
                genre_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(genre_id), 0) FROM genre")
                genre_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO genre(genre_id, name) VALUES (?, ?)", (genre_id, Genre))

            self.cursor.execute("INSERT OR IGNORE INTO genre_link(genre_id, media_id, media_type) VALUES (?, ?, ?)", (genre_id, media_id, media_type))

    # studios
    def delete_links_studios(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM studio_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_studios_and_links(self, Studios, KodiId, MediaType):
        for Studio in Studios:
            self.cursor.execute("SELECT studio_id FROM studio WHERE name = ? ", (Studio,))
            Data = self.cursor.fetchone()

            if Data:
                studio_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(studio_id), 0) FROM studio")
                studio_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO studio(studio_id, name) VALUES (?, ?)", (studio_id, Studio))

            self.cursor.execute("INSERT OR IGNORE INTO studio_link(studio_id, media_id, media_type) VALUES (?, ?, ?)", (studio_id, KodiId, MediaType))

    # ratings
    def delete_ratings(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM rating WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_ratings(self, KodiItemId, media_id, media_type, Rating):
        self.cursor.execute("SELECT coalesce(max(rating_id), 0) FROM rating")
        rating_id = self.cursor.fetchone()[0] + 1
        self.cursor.execute("INSERT INTO rating(rating_id, media_id, media_type, rating_type, rating) VALUES (?, ?, ?, ?, ?)", (rating_id, KodiItemId, media_id, media_type, Rating))
        return rating_id

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
    def delete_bookmark(self, file_id):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (file_id,))

    def add_bookmark_chapter(self, KodiFileId, RunTimeTicks, Chapters):
        for Chapter in Chapters:
            self.cursor.execute("SELECT coalesce(max(idBookmark), 0) FROM bookmark")
            bookmark_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, type) VALUES (?, ?, ?, ?, ?, ?, ?)", (bookmark_id, KodiFileId, Chapter['StartPositionTicks'], RunTimeTicks, Chapter['Image'], "VideoPlayer", 0))

    def add_file_bookmark(self, KodiItemId, KodiSeasonId, KodiShowId, ChapterInfo): # workaround due to Kodi episode bookmark bug
        self.cursor.execute("SELECT season FROM seasons WHERE idSeason = ? ", (KodiSeasonId,))
        Data = self.cursor.fetchone()

        if Data:
            SeasonNumber = Data[0]
            Path = "videodb://tvshows/titles/%s/%s/" % (KodiShowId, SeasonNumber)
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.cursor.execute("INSERT INTO files(idPath, strFilename, idFile) VALUES (?, ?, ?)", (idPath, KodiItemId, FileId))
                self.add_bookmark_chapter(FileId, None, ChapterInfo)

            Path = "videodb://tvshows/titles/%s/-2/" % KodiShowId # -2 if this is the only season for the TV Show
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.cursor.execute("INSERT INTO files(idPath, strFilename, idFile) VALUES (?, ?, ?)", (idPath, KodiItemId, FileId))
                self.add_bookmark_chapter(FileId, None, ChapterInfo)

            Path = "videodb://inprogresstvshows/%s/%s/" % (KodiShowId, SeasonNumber)
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.cursor.execute("INSERT INTO files(idPath, strFilename, idFile) VALUES (?, ?, ?)", (idPath, KodiItemId, FileId))
                self.add_bookmark_chapter(FileId, None, ChapterInfo)

            Path = "videodb://inprogresstvshows/%s/-2/" % KodiShowId # -2 if this is the only season for the TV Show
            self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
            Data = self.cursor.fetchone()

            if Data:
                idPath = Data[0]
                FileId = self.create_entry_file()
                self.cursor.execute("INSERT INTO files(idPath, strFilename, idFile) VALUES (?, ?, ?)", (idPath, KodiItemId, FileId))
                self.add_bookmark_chapter(FileId, None, ChapterInfo)

    def add_path_bookmark(self, KodiShowId, SeasonNumber): # workaround due to Kodi episode bookmark bug
        Path = "videodb://tvshows/titles/%s/%s/" % (KodiShowId, SeasonNumber)
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath) VALUES (?)", (Path,))

        Path = "videodb://tvshows/titles/%s/-2/" % KodiShowId # -2 if this is the only season for the TV Show
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath) VALUES (?)", (Path,))

        Path = "videodb://inprogresstvshows/%s/%s/" % (KodiShowId, SeasonNumber)
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath) VALUES (?)", (Path,))

        Path = "videodb://inprogresstvshows/%s/-2/" % KodiShowId # -2 if this is the only season for the TV Show
        self.cursor.execute("SELECT idPath FROM path WHERE strPath = ? ", (Path,))
        Data = self.cursor.fetchone()

        if not Data:
            self.cursor.execute("INSERT INTO path(strPath) VALUES (?)", (Path,))

    def delete_path_bookmark(self, KodiSeasonId): # workaround due to Kodi episode bookmark bug
        self.cursor.execute("SELECT idShow, season FROM seasons WHERE idSeason = ? ", (KodiSeasonId,))
        Data = self.cursor.fetchone()

        if Data:
            Path = "videodb://tvshows/titles/%s/%s/" % (Data[0], Data[1])
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = "videodb://tvshows/titles/%s/-2/" % Data[0] # -2 if this is the only season for the TV Show
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = "videodb://inprogresstvshows/%s/%s/" % (Data[0], Data[1])
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))
            Path = "videodb://inprogresstvshows/%s/-2/" % Data[0] # -2 if this is the only season for the TV Show
            self.cursor.execute("DELETE FROM path WHERE strPath = ?", (Path,))

    def delete_file_bookmark(self, KodiItemId): # workaround due to Kodi episode bookmark bug
        self.cursor.execute("DELETE FROM files WHERE strFilename = ?", (KodiItemId,))

    def add_bookmark_playstate(self, KodiFileId, PlaybackPositionTicks, RunTimeTicks):
        if PlaybackPositionTicks:
            self.cursor.execute("SELECT coalesce(max(idBookmark), 0) FROM bookmark")
            bookmark_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type) VALUES (?, ?, ?, ?, ?, ?)", (bookmark_id, KodiFileId, PlaybackPositionTicks, RunTimeTicks, "VideoPlayer", 1))

    def update_bookmark_playstate(self, file_id, playcount, date_played, resume, Runtime):
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ? AND type = ?", (file_id, "1"))
        self.cursor.execute("UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?", (playcount, date_played, file_id))

        if resume:
            self.cursor.execute("SELECT coalesce(max(idBookmark), 0) FROM bookmark")
            bookmark_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type) VALUES (?, ?, ?, ?, ?, ?)", (bookmark_id, file_id, resume, Runtime, "VideoPlayer", 1))

    # countries
    def delete_links_countries(self, Media_id, media_type):
        self.cursor.execute("DELETE FROM country_link WHERE media_id = ? AND media_type = ?", (Media_id, media_type))

    def add_countries_and_links(self, ProductionLocations, media_id, media_type):
        for CountryName in ProductionLocations:
            self.cursor.execute("SELECT country_id FROM country WHERE name = ? ", (CountryName,))
            Data = self.cursor.fetchone()

            if Data:
                country_id = Data[0]
            else:
                self.cursor.execute("SELECT coalesce(max(country_id), 0) FROM country")
                country_id = self.cursor.fetchone()[0] + 1
                self.cursor.execute("INSERT INTO country(country_id, name) VALUES (?, ?)", (country_id, CountryName))

            self.cursor.execute("INSERT OR IGNORE INTO country_link(country_id, media_id, media_type) VALUES (?, ?, ?)", (country_id, media_id, media_type))

    # settings
    def get_FileSettings(self, KodiFileId):
        self.cursor.execute("SELECT idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings Where idFile = ?", (KodiFileId,))
        return self.cursor.fetchone()

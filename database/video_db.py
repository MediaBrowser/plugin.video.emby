from helper import loghandler
from . import common_db

FavoriteTags = {"Favorite movies": None, "Favorite musicvideos": None, "Favorite tvshows": None, "Favorite episodes": None}
LOG = loghandler.LOG('EMBY.database.video_db')

class VideoDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def add_Index(self):
        # Index
        self.cursor.execute("DROP INDEX IF EXISTS idx_actor_name_art_urls")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_actor_name_art_urls_NOCASE on actor (name COLLATE NOCASE, art_urls COLLATE NOCASE)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_strFilename on files (strFilename)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_dateAdded on files (dateAdded)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_lastPlayed on files (lastPlayed)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_art_mediatype on art (media_type)")
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
    def add_movie(self, KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, RunTimeTicks, OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate, Filename, DateCreated, PlayCount, LastPlayedDate):
        self.cursor.execute("INSERT INTO movie (idMovie, idFile, c00, c01, c02, c03, c05, c06, c08, c09, c10, c11, c12, c14, c15, c16, c18, c19, c20, c21, c22, c23, premiered, c02, c13) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, ShortOverview, Tagline, RatingId, Writers, Poster, Unique, SortName, int(RunTimeTicks), OfficialRating, Genre, Directors, OriginalTitle, Studio, Trailer, KodiFanart, ProductionLocation, Path, KodiPathId, PremiereDate, "", 0))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_movie_entry(self):
        self.cursor.execute("SELECT coalesce(max(idMovie), 0) FROM movie")
        return self.cursor.fetchone()[0] + 1

    def delete_movie(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_movie_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        self.cursor.execute("SELECT * FROM movie_view WHERE idMovie = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        if not PathAndFilename:
            PathAndFilename = "%s%s" % (ItemData[32], ItemData[31])

        Artwork = self.get_artwork(kodi_id, "movie", "")
        People = self.get_people_artwork(kodi_id, "movie")
        return {'mediatype': "movie", "dbid": kodi_id, 'title': ItemData[2], 'plot': ItemData[3], 'plotoutline': ItemData[4], 'tagline': ItemData[5], 'writer': ItemData[8], 'sorttitle': ItemData[12], 'duration': ItemData[13], 'mpaa': ItemData[14], 'genre': ItemData[16], 'director': ItemData[17], 'originaltitle': ItemData[18], 'studio': ItemData[20], 'country': ItemData[23], 'userrating': ItemData[27], 'premiered': ItemData[28], 'playcount': ItemData[33], 'lastplayed': ItemData[34], 'dateadded': ItemData[35], 'rating': ItemData[39], 'trailer': ItemData[20], 'path': ItemData[30], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[40], 'ResumeTime': ItemData[39]}, 'people': People, 'artwork': Artwork}

    # musicvideo
    def add_musicvideos(self, KodiItemId, KodiFileId, Name, Poster, RunTimeTicks, Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate, DateCreated, PlayCount, LastPlayedDate, Filename):
        self.cursor.execute("INSERT INTO musicvideo (idMVideo, idFile, c00, c01, c04, c05, c06, c08, c09, c10, c11, c12, c13, c14, premiered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Poster, int(RunTimeTicks), Directors, Studio, Overview, Album, Artist, Genre, IndexNumber, FilePath, KodiPathId, PremiereDate))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_entry_musicvideos(self):
        self.cursor.execute("SELECT coalesce(max(idMVideo), 0) FROM musicvideo")
        return self.cursor.fetchone()[0] + 1

    def delete_musicvideos(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_musicvideos_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        self.cursor.execute("SELECT * FROM musicvideo_view WHERE idMVideo = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        if not PathAndFilename:
            PathAndFilename = "%s%s" % (ItemData[29], ItemData[28])

        Artwork = self.get_artwork(kodi_id, "musicvideo", "")
        People = self.get_people_artwork(kodi_id, "musicvideo")
        return {'mediatype': "musicvideo", "dbid": kodi_id, 'title': ItemData[2], 'duration': ItemData[6], 'director': ItemData[7], 'studio': ItemData[8], 'plot': ItemData[10], 'album': ItemData[11], 'artist': ItemData[12].split(" / "), 'genre': ItemData[13], 'track': ItemData[14], 'premiered': ItemData[27], 'playcount': ItemData[30], 'lastplayed': ItemData[31], 'path': ItemData[29], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[33], 'ResumeTime': ItemData[34]}, 'people': People, 'artwork': Artwork}

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
                    NextEpisodeForTVShow = "%s;%s" % (LastPlayedItem[0], Episode[0])

            if NextEpisodeForTVShow and NextEpisodeForTVShow != "-1":
                NextEpisodeInfos += (NextEpisodeForTVShow,)

        NextEpisodeInfos = sorted(NextEpisodeInfos, reverse=True)
        return NextEpisodeInfos

    def get_tvshows_metadata_for_listitem(self, kodi_id):
        self.cursor.execute("SELECT * FROM tvshow_view WHERE idShow = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "tvshow", "")
        People = self.get_people_artwork(kodi_id, "tvshow")
        return {'mediatype': "tvshow", "dbid": kodi_id, 'title': ItemData[1], 'tvshowtitle': ItemData[1], 'plot': ItemData[2], 'tvshowstatus': ItemData[3], 'premiered': ItemData[6], 'genre': ItemData[8], 'originaltitle': ItemData[9], 'imdbnumber': ItemData[13], 'mpaa': ItemData[14], 'studio': ItemData[15], 'sorttitle': ItemData[16], 'userrating': ItemData[25], 'duration': ItemData[26], 'lastplayed': ItemData[30], 'rating': ItemData[34], 'path': "videodb://tvshows/titles/%s/" % kodi_id, 'properties': {'TotalEpisodes': ItemData[31], 'TotalSeasons': ItemData[33], 'WatchedEpisodes': ItemData[32], 'UnWatchedEpisodes': int(ItemData[31]) - int(ItemData[32]), 'IsFolder': 'true', 'IsPlayable': 'true'}, 'people': People, 'artwork': Artwork}

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
        self.cursor.execute("SELECT * FROM season_view WHERE idSeason = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "season", "")
        People = self.get_people_artwork(kodi_id, "season")
        return {'mediatype': "season", "dbid": kodi_id, 'season': ItemData[2], 'title': ItemData[3], 'userrating': ItemData[4], 'tvshowtitle': ItemData[6], 'plot': ItemData[7], 'premiered': ItemData[8], 'genre': ItemData[9], 'studio': ItemData[10], 'mpaa': ItemData[11], 'firstaired': ItemData[14], 'path': "videodb://tvshows/titles/%s/%s/" % (ItemData[1], kodi_id), 'properties': {'NumEpisodes': ItemData[12], 'WatchedEpisodes': ItemData[13], 'UnWatchedEpisodes': int(ItemData[12]) - int(ItemData[13]), 'IsFolder': 'true', 'IsPlayable': 'true'}, 'people': People, 'artwork': Artwork}

    # episode
    def add_episode(self, KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, RunTimeTicks, Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, Filename, DateCreated, PlayCount, LastPlayedDate):
        self.cursor.execute("INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c06, c09, c10, c12, c13, c14, c15, c16, c18, c19, c20, idShow, idSeason, c11, c17) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (KodiItemId, KodiFileId, Name, Overview, RatingId, Writers, PremiereDate, Poster, int(RunTimeTicks), Directors, ParentIndexNumber, IndexNumber, OriginalTitle, SortParentIndexNumber, SortIndexNumber, FilePath, KodiPathId, Unique, KodiShowId, KodiSeasonId, "", -1))
        self.add_file(KodiPathId, Filename, DateCreated, KodiFileId, PlayCount, LastPlayedDate)

    def create_entry_episode(self):
        self.cursor.execute("SELECT coalesce(max(idEpisode), 0) FROM episode")
        return self.cursor.fetchone()[0] + 1

    def delete_episode(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))

    def get_episode_metadata_for_listitem(self, kodi_id, PathAndFilename=None):
        self.cursor.execute("SELECT * FROM episode_view WHERE idEpisode = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        if not PathAndFilename:
            PathAndFilename = "%s%s" % (ItemData[30], ItemData[29])

        People = self.get_people_artwork(kodi_id, "episode")
        People += self.get_people_artwork(ItemData[26], "tvshow")
        Artwork = self.get_artwork(kodi_id, "episode", "")
        Artwork.update(self.get_artwork(ItemData[26], "tvshow", "tvshow."))
        Artwork.update(self.get_artwork(ItemData[28], "season", "season."))
        return {'mediatype': "episode", "dbid": kodi_id, 'title': ItemData[2], 'plot': ItemData[3], 'writer': ItemData[6], 'premiered': ItemData[7], 'duration': ItemData[11], 'director': ItemData[12], 'season': ItemData[14], 'episode': ItemData[15], 'originaltitle': ItemData[16], 'sortseason': ItemData[17], 'sortepisode': ItemData[18], 'imdbnumber': ItemData[22], 'userrating': ItemData[27], 'playCount': ItemData[31], 'lastplayed': ItemData[32], 'tvshowtitle': ItemData[34], 'genre': ItemData[35], 'studio': ItemData[36], 'path': ItemData[30], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[40], 'ResumeTime': ItemData[39]}, 'people': People, 'artwork': Artwork}

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
        self.cursor.execute("SELECT * FROM sets WHERE idSet = ?", (kodi_id,))
        ItemData = self.cursor.fetchone()

        if not ItemData:
            return {}

        Artwork = self.get_artwork(kodi_id, "set", "")
        return{'mediatype': "set", "dbid": kodi_id, 'title': ItemData[1], 'plot': ItemData[2], 'path': "videodb://movies/sets/%s/" % kodi_id, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'artwork': Artwork}

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

            person_id, NewPersion = self.add_get_person(person['Name'], person['imageurl'], person['LibraryId'], person['Type'].lower())

            if person['Type'] == 'Director':
                self.cursor.execute("INSERT OR REPLACE INTO director_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))
            elif person['Type'] == 'Writer':
                self.cursor.execute("INSERT OR REPLACE INTO writer_link(actor_id, media_id, media_type) VALUES (?, ?, ?)", (person_id, KodiId, MediaType))
            else:
                self.cursor.execute("INSERT OR REPLACE INTO actor_link(actor_id, media_id, media_type, role, cast_order) VALUES (?, ?, ?, ?, ?)", (person_id, KodiId, MediaType, role, cast_order))
                cast_order += 1

            if NewPersion:
                if person['imageurl']:
                    self.cursor.execute("INSERT OR REPLACE INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (person_id, person['Type'].lower(), "thumb", person['imageurl']))

    def add_get_person(self, PersonName, imageurl, LibraryId, ArtType):
        self.cursor.execute("SELECT actor_id, name, art_urls FROM actor WHERE name LIKE ? COLLATE NOCASE AND art_urls LIKE ? COLLATE NOCASE", ("%s%%" % PersonName, "%%%s" % LibraryId))
        Data = self.cursor.fetchone()

        if Data:
            if imageurl != Data[1]: # update artwork
                self.cursor.execute("UPDATE actor SET art_urls = ? WHERE actor_id = ?", (imageurl, Data[0]))
                self.cursor.execute("UPDATE art SET url = ? WHERE media_id = ? AND type = ? AND media_type = ? ", (imageurl, Data[0], "thumb", ArtType))

            return Data[0], False

        self.cursor.execute("SELECT coalesce(max(actor_id), 0) FROM actor")
        person_id = self.cursor.fetchone()[0] + 1

        while True:
            try:
                self.cursor.execute("INSERT INTO actor(actor_id, name, art_urls) VALUES (?, ?, ?)", (person_id, PersonName, imageurl))
                break
            except Exception as Error:
                LOG.warning("Duplicate PersonName detected: %s / %s" % (PersonName, Error))
                PersonName += " "

        return person_id, True

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
            self.add_link_tag(FavoriteTags["Favorite %ss" % MediaType], KodiItemId, MediaType)
        else:
            self.cursor.execute("DELETE FROM tag_link WHERE tag_id = ? AND media_type = ? AND media_id = ?", (FavoriteTags["Favorite %ss" % MediaType], MediaType, KodiItemId))

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
            Artwork["%s%s" % (PrefixKey, ArtworkData[3])] = ArtworkData[4]

        return Artwork

    # settings
    def get_FileSettings(self, KodiFileId):
        self.cursor.execute("SELECT idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings Where idFile = ?", (KodiFileId,))
        return self.cursor.fetchone()

    # Path
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

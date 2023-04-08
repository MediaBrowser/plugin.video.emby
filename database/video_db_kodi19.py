def get_movie_metadata_for_listitem(kodi_id, PathAndFilename, Cursor, get_artwork, get_people_artwork):
    Cursor.execute("SELECT * FROM movie_view WHERE idMovie = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    if not PathAndFilename:
        PathAndFilename = f"{ItemData[32]}{ItemData[31]}"

    Artwork = get_artwork(kodi_id, "movie", "")
    People = get_people_artwork(kodi_id, "movie")
    return {'mediatype': "movie", "dbid": kodi_id, 'title': ItemData[2], 'plot': ItemData[3], 'plotoutline': ItemData[4], 'tagline': ItemData[5], 'writer': ItemData[8], 'sorttitle': ItemData[12], 'duration': ItemData[13], 'mpaa': ItemData[14], 'genre': ItemData[16], 'director': ItemData[17], 'originaltitle': ItemData[18], 'studio': ItemData[20], 'country': ItemData[23], 'userrating': ItemData[27], 'premiered': ItemData[28], 'playcount': ItemData[33], 'lastplayed': ItemData[34], 'dateadded': ItemData[35], 'rating': ItemData[39], 'trailer': ItemData[20], 'path': ItemData[30], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[37], 'ResumeTime': ItemData[36]}, 'people': People, 'artwork': Artwork}

def get_musicvideos_metadata_for_listitem(kodi_id, PathAndFilename, Cursor, get_artwork, get_people_artwork):
    Cursor.execute("SELECT * FROM musicvideo_view WHERE idMVideo = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    if not PathAndFilename:
        PathAndFilename = f"{ItemData[29]}{ItemData[28]}"

    Artwork = get_artwork(kodi_id, "musicvideo", "")
    People = get_people_artwork(kodi_id, "musicvideo")
    return {'mediatype': "musicvideo", "dbid": kodi_id, 'title': ItemData[2], 'duration': ItemData[6], 'director': ItemData[7], 'studio': ItemData[8], 'plot': ItemData[10], 'album': ItemData[11], 'artist': ItemData[12].split(" / "), 'genre': ItemData[13], 'track': ItemData[14], 'premiered': ItemData[27], 'playcount': ItemData[30], 'lastplayed': ItemData[31], 'path': ItemData[29], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[34], 'ResumeTime': ItemData[33]}, 'people': People, 'artwork': Artwork}

def get_tvshows_metadata_for_listitem(kodi_id, Cursor, get_artwork, get_people_artwork):
    Cursor.execute("SELECT * FROM tvshow_view WHERE idShow = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    if ItemData[31] and ItemData[32]:
        UnWatchedEpisodes = int(ItemData[31]) - int(ItemData[32])
    else:
        UnWatchedEpisodes = 0

    Artwork = get_artwork(kodi_id, "tvshow", "")
    People = get_people_artwork(kodi_id, "tvshow")
    return {'mediatype': "tvshow", "dbid": kodi_id, 'title': ItemData[1], 'tvshowtitle': ItemData[1], 'plot': ItemData[2], 'tvshowstatus': ItemData[3], 'premiered': ItemData[6], 'genre': ItemData[8], 'originaltitle': ItemData[9], 'imdbnumber': ItemData[13], 'mpaa': ItemData[14], 'studio': ItemData[15], 'sorttitle': ItemData[16], 'userrating': ItemData[25], 'duration': ItemData[26], 'lastplayed': ItemData[30], 'rating': ItemData[34], 'path': f"videodb://tvshows/titles/{kodi_id}/", 'properties': {'TotalEpisodes': ItemData[31], 'TotalSeasons': ItemData[33], 'WatchedEpisodes': ItemData[32], 'UnWatchedEpisodes': UnWatchedEpisodes, 'IsFolder': 'true', 'IsPlayable': 'true'}, 'people': People, 'artwork': Artwork}

def get_season_metadata_for_listitem(kodi_id, Cursor, get_artwork, get_people_artwork):
    Cursor.execute("SELECT * FROM season_view WHERE idSeason = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    if ItemData[12] and ItemData[13]:
        UnWatchedEpisodes = int(ItemData[12]) - int(ItemData[13])
    else:
        UnWatchedEpisodes = 0

    Artwork = get_artwork(kodi_id, "season", "")
    People = get_people_artwork(kodi_id, "season")
    return {'mediatype': "season", "dbid": kodi_id, 'season': ItemData[2], 'title': ItemData[3], 'userrating': ItemData[4], 'tvshowtitle': ItemData[6], 'plot': ItemData[7], 'premiered': ItemData[8], 'genre': ItemData[9], 'studio': ItemData[10], 'mpaa': ItemData[11], 'firstaired': ItemData[14], 'path': f"videodb://tvshows/titles/{ItemData[1]}/{kodi_id}/", 'properties': {'NumEpisodes': ItemData[12], 'WatchedEpisodes': ItemData[13], 'UnWatchedEpisodes': UnWatchedEpisodes, 'IsFolder': 'true', 'IsPlayable': 'true'}, 'people': People, 'artwork': Artwork}

def get_episode_metadata_for_listitem(kodi_id, PathAndFilename, Cursor, get_artwork, get_people_artwork):
    Cursor.execute("SELECT * FROM episode_view WHERE idEpisode = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    if not PathAndFilename:
        PathAndFilename = f"{ItemData[30]}{ItemData[29]}"

    People = get_people_artwork(kodi_id, "episode")
    People += get_people_artwork(ItemData[26], "tvshow")
    Artwork = get_artwork(kodi_id, "episode", "")
    Artwork.update(get_artwork(ItemData[26], "tvshow", "tvshow."))
    Artwork.update(get_artwork(ItemData[28], "season", "season."))
    return {'mediatype': "episode", "dbid": kodi_id, 'title': ItemData[2], 'plot': ItemData[3], 'writer': ItemData[6], 'premiered': ItemData[7], 'duration': ItemData[11], 'director': ItemData[12], 'season': ItemData[14], 'episode': ItemData[15], 'originaltitle': ItemData[16], 'sortseason': ItemData[17], 'sortepisode': ItemData[18], 'imdbnumber': ItemData[22], 'userrating': ItemData[27], 'playCount': ItemData[31], 'lastplayed': ItemData[32], 'tvshowtitle': ItemData[34], 'genre': ItemData[35], 'studio': ItemData[36], 'path': ItemData[30], 'pathandfilename': PathAndFilename, 'properties': {'IsFolder': 'false', 'IsPlayable': 'true', 'TotalTime': ItemData[40], 'ResumeTime': ItemData[39]}, 'people': People, 'artwork': Artwork}

def get_boxset_metadata_for_listitem(kodi_id, Cursor, get_artwork):
    Cursor.execute("SELECT * FROM sets WHERE idSet = ?", (kodi_id,))
    ItemData = Cursor.fetchone()

    if not ItemData:
        return {}

    Artwork = get_artwork(kodi_id, "set", "")
    return{'mediatype': "set", "dbid": kodi_id, 'title': ItemData[1], 'plot': ItemData[2], 'path': f"videodb://movies/sets/{kodi_id}/", 'properties': {'IsFolder': 'false', 'IsPlayable': 'true'}, 'artwork': Artwork}

def add_streams(Cursor, file_id, videostream, audiostream, subtitlestream, runtime):
    for track in videostream:
        Cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth, iVideoHeight, iVideoDuration, strStereoMode, strVideoLanguage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (file_id, 0, track['codec'], track['aspect'], track['width'], track['height'], int(runtime), track['3d'], track['language']))

    for track in audiostream:
        Cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage) VALUES (?, ?, ?, ?, ?)", (file_id, 1, track['codec'], track['channels'], track['language']))

    for track in subtitlestream:
        if not track['external']:
            Cursor.execute("INSERT OR REPLACE INTO streamdetails(idFile, iStreamType, strSubtitleLanguage) VALUES (?, ?, ?)", (file_id, 2, track['language']))

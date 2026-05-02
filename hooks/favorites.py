import xbmc
import xbmcvfs
from helper import utils
from core import movies, videos, musicvideo, boxsets, genre, musicgenre, musicartist, musicalbum, audio, tag, person, studio, playlist, series, season, episode, common
from database import dbio

KodiFavFile = "special://profile/favourites.xml"
FavoriteUpdatedByEmby = False


def monitor_Favorites():
    global FavoriteUpdatedByEmby
    if utils.DebugLog: xbmc.log("EMBY.hooks.favorites (DEBUG): THREAD: --->[ Kodi favorites ]", 1) # LOGDEBUG
    FavoriteUpdatedByEmby = False
    FavoritesCached = get_Favorites()
    FavoriteTimestamp = 0

    while True:
        if utils.sleep(0.5):
            if utils.DebugLog: xbmc.log("EMBY.hooks.favorites (DEBUG): THREAD: ---<[ Kodi favorites ]", 1) # LOGDEBUG
            return

        Stats = xbmcvfs.Stat(KodiFavFile)
        TimestampReadOut = Stats.st_mtime()

        # Skip favorite update
        if FavoriteUpdatedByEmby:
            FavoriteUpdatedByEmby = False
            FavoritesCached = get_Favorites()
            continue

        # Check if favorite.xml file has changed (by timestamp)
        if FavoriteTimestamp < TimestampReadOut:
            Trigger = bool(FavoriteTimestamp)
            FavoriteTimestamp = TimestampReadOut
            FavoritesCurrent = get_Favorites()

            if Trigger:
                FavoritesRemoved = []
                FavoritesAdded = []

                # detect removed favorites
                for FavoriteCached in FavoritesCached["Favorites"]:
                    if FavoriteCached not in FavoritesCurrent["Favorites"]:
                        FavoritesRemoved.append(FavoriteCached)

                # detect added favorites
                for FavoriteCurrent in FavoritesCurrent["Favorites"]:
                    if FavoriteCurrent not in FavoritesCached["Favorites"]:
                        FavoritesAdded.append(FavoriteCurrent)

                xbmc.log("EMBY.hooks.favorites: Kodi favorites changed", 1) # LOGINFO

                for Index, FavoritesChanged in enumerate((FavoritesRemoved, FavoritesAdded)):
                    isAdded = bool(Index)

                    for FavoriteChanged in FavoritesChanged:
                        EmbyType = ""
                        EmbyId = ""
                        ServerId = ""
                        ImageUrlFromDB = ""
                        KodiItemId = -1
                        KodiItemIdFromDB = ""
                        Path, isPath = get_path(FavoriteChanged)

                        if not Path:
                            if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): Path not found: {FavoriteChanged}", 1) # LOGDEBUG
                            continue

                        # get metadata
                        if Path.startswith("videodb://tvshows/titles/"):
                            Temp = Path.split("/")

                            if Temp[5] and Temp[5] != "-1":
                                videodb = dbio.DBOpenRO("video", "Favorites")
                                KodiItemId = videodb.get_seasonid_by_showid_number(Temp[4], Temp[5]) # Temp[4] = KodiTVShowId, Temp[5] = SeasonNumber
                                dbio.DBCloseRO("video", "Favorites")
                                EmbyType = "Season"
                            else:
                                KodiItemId = Temp[4]
                                EmbyType = "Series"
                        elif Path.startswith("videodb://movies/sets/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "BoxSet"
                        elif Path.startswith("videodb://movies/genres/") or Path.startswith("videodb://tvshows/genres/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "Genre"
                        elif Path.startswith("videodb://movies/tags/") or Path.startswith("videodb://tvshows/tags/") or Path.startswith("videodb://musicvideos/tags/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "Tag"
                        elif Path.startswith("videodb://movies/actors/") or Path.startswith("videodb://tvshows/actors/") or Path.startswith("videodb://musicvideos/actors/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "Person"
                        elif Path.startswith("videodb://movies/studios/") or Path.startswith("videodb://tvshows/studios/") or Path.startswith("videodb://musicvideos/studios/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "Studio"
                        elif Path.startswith("special://profile/playlists/video/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[5][:-4]
                            EmbyType = "PlaylistVideo"
                        elif Path.startswith("special://profile/playlists/music/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[5][:-4]
                            EmbyType = "PlaylistAudio"
                        elif Path.startswith("plugin://plugin.service.emby-next-gen/?mode=playlist&mediatype=video"):
                            Temp = Path.split("id=")
                            KodiItemId = Temp[-1]
                            EmbyType = "PlaylistVideo"
                        elif Path.startswith("plugin://plugin.service.emby-next-gen/?mode=playlist&mediatype=audio"):
                            Temp = Path.split("id=")
                            KodiItemId = Temp[-1]
                            EmbyType = "PlaylistAudio"
                        elif Path.startswith("musicdb://genres/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[3]
                            EmbyType = "MusicGenre"
                        elif Path.startswith("videodb://musicvideos/genres/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[4]
                            EmbyType = "MusicGenre"
                        elif Path.startswith("musicdb://artists/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[3]
                            EmbyType = "MusicArtist"
                        elif Path.startswith("musicdb://albums/"):
                            Temp = Path.split("/")
                            KodiItemId = Temp[3]
                            EmbyType = "MusicAlbum"
                        elif Path.startswith("library://music/emby_playlistsaudio_Playlists/"):
                            EmbyType = "PlaylistAudio"
                            Temp = Path.replace("library://music/emby_playlistsaudio_Playlists/", "").replace(".xml", "").replace("/", "").split("_")
                            ServerId = Temp[0]
                            EmbyId = Temp[1]
                        elif Path.startswith("library://video/emby_playlistsvideo_Playlists/"):
                            EmbyType = "PlaylistVideo"
                            Temp = Path.replace("library://video/emby_playlistsvideo_Playlists/", "").replace(".xml", "").replace("/", "").split("_")
                            ServerId = Temp[0]
                            EmbyId = Temp[1]

                        ValidImage = ""

                        # get ServerId by thumbnail's metadata
                        if FavoriteChanged.get("thumbnail", "").startswith("http://127.0.0.1:57342/"): # by picure url metadata
                            ValidImage = FavoriteChanged["thumbnail"]
                            FolderIds = ValidImage.split("/")

                            if len(FolderIds) >= 4:
                                ServerId = FolderIds[4]

                        # get additional metadata
                        if not EmbyId or not EmbyType:
                            if KodiItemId == -1:
                                if ValidImage:
                                    MetaIds = ValidImage.split("-")

                                    if len(MetaIds) >= 2:
                                        EmbyId = MetaIds[1] # get EmbyId by thumbnail's metadata

                                        if isAdded:
                                            embydb = dbio.DBOpenRO(ServerId, "Favorites change artwork (content)")
                                            EmbyType = embydb.get_contenttype_by_id(EmbyId)
                                            dbio.DBCloseRO(ServerId, "Favorites change artwork (content)")
                            else:
                                if ServerId in utils.EmbyServers:
                                    embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata 1")
                                    EmbyId, KodiItemIdFromDB, ImageUrlFromDB = embydb.get_EmbyId_KodiId_ImageUrl_by_KodiId_EmbyType(KodiItemId, EmbyType)
                                    dbio.DBCloseRO(ServerId, "Favorites subcontent metadata 1")
                                else:
                                    for ServerId in utils.EmbyServers:
                                        embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata 2")
                                        EmbyId, KodiItemIdFromDB, ImageUrlFromDB = embydb.get_EmbyId_KodiId_ImageUrl_by_KodiId_EmbyType(KodiItemId, EmbyType)
                                        dbio.DBCloseRO(ServerId, "Favorites subcontent metadata 2")

                                        if EmbyId:
                                            break
                        else:
                            embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata 3")
                            KodiItemIdFromDB, ImageUrlFromDB = embydb.get_KodiId_ImageUrl_by_EmbyId_EmbyType(EmbyId, EmbyType)
                            dbio.DBCloseRO(ServerId, "Favorites subcontent metadata 3")

                        if not EmbyId:
                            if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): EmbyId not found: {FavoriteChanged}", 1) # LOGDEBUG
                            continue

                        if isAdded:
                            delete_favorite(FavoriteChanged, FavoritesCurrent, None) # remove existing favorite record

                            # Update image overlay
                            if isPath:
                                if EmbyType == "MusicVideo":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Musicvideo", "Musicvideos", EmbyId, ServerId, FavoriteChanged["thumbnail"]), "path": FavoriteChanged["path"]})
                                elif EmbyType == "Episode":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Episode", "TV Shows", EmbyId, ServerId, FavoriteChanged["thumbnail"]), "path": FavoriteChanged["path"]})
                                elif EmbyType == "Movie":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Movie", "Movies", EmbyId, ServerId, FavoriteChanged["thumbnail"]), "path": FavoriteChanged["path"]})
                                elif EmbyType == "Video":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Video", "Movies", EmbyId, ServerId, FavoriteChanged["thumbnail"]), "path": FavoriteChanged["path"]})
                                elif EmbyType == "Audio":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Song", "Songs", EmbyId, ServerId, FavoriteChanged["thumbnail"]), "path": FavoriteChanged["path"]})
                                else:
                                    if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): EmbyType not found: {FavoriteChanged}", 1) # LOGDEBUG
                                    continue
                            else: # add additional existing favorite records for linked sub-content
                                if ImageUrlFromDB:
                                    ImageUrlUpdated = ImageUrlFromDB
                                else:
                                    ImageUrlUpdated = FavoriteChanged["thumbnail"]

                                if EmbyType == "MusicGenre":
                                    MusicGenreByMusicVideo = Path.startswith("videodb://musicvideos/genres/")
                                    MusicGenreByAudio = Path.startswith("musicdb://genres/")

                                    # Update artwork for existing item
                                    if MusicGenreByMusicVideo:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Genre", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})
                                    elif MusicGenreByAudio:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Genre", "Songs", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "music"})

                                    # Add additional favorites for linked subcontent
                                    if KodiItemIdFromDB:
                                        KodiItemIdFromDB = KodiItemIdFromDB.split(";")

                                        if MusicGenreByMusicVideo:
                                            musicdb = dbio.DBOpenRO("music", "Favorites change musicgenre (subcontent)")
                                            _, hasSongs = musicdb.get_Genre_Name_hasSongs(KodiItemIdFromDB[1])
                                            dbio.DBCloseRO("music", "Favorites change musicgenre (subcontent)")

                                            if hasSongs:
                                                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Songs", EmbyId, ServerId, ImageUrlUpdated), True, f"musicdb://genres/{KodiItemIdFromDB[1]}/", FavoriteChanged["title"], "window", 10502),))
                                        else:
                                            videodb = dbio.DBOpenRO("video", "Favorites change musicgenre (subcontent)")
                                            _, hasMusicVideos, _, _ = videodb.get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(KodiItemIdFromDB[0])
                                            dbio.DBCloseRO("video", "Favorites change musicgenre (subcontent)")

                                            if hasMusicVideos:
                                                utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/genres/{KodiItemIdFromDB[0]}/", FavoriteChanged["title"], "window", 10025),))
                                elif EmbyType == "Tag":
                                    videodb = dbio.DBOpenRO("video", "Favorites change tag (subcontent)")
                                    _, hasMusicVideos, hasMovies, hasTVShows = videodb.get_Tag_Name(KodiItemId)
                                    dbio.DBCloseRO("video", "Favorites change tag (subcontent)")
                                    TagByMovie = Path.startswith("videodb://movies/tags/")
                                    TagBySeries = Path.startswith("videodb://tvshows/tags/")

                                    if TagByMovie:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Tag", "Movie", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    elif TagBySeries:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Tag", "TV Show", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    else:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Tag", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/tags/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                    # collections assigned to tags -> utils.BoxSetsToTags
                                    if str(EmbyId).startswith(utils.MappingIds['Tag']):
                                        EmbySetId = str(EmbyId).replace(utils.MappingIds['Tag'], "")
                                        embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata tag")
                                        KodiItemId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbySetId, "BoxSet")
                                        dbio.DBCloseRO(ServerId, "Favorites subcontent metadata tag")
                                        delete_favorite(None, FavoritesCurrent, f"videodb://movies/sets/{KodiItemId}/")
                                        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Boxset", "Set", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/sets/{KodiItemId}/", FavoriteChanged["title"].replace(" (Collection)", ""), "window", 10025),))
                                elif EmbyType == "BoxSet":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Boxset", "Set", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})
                                    embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata boxset")
                                    KodiItemId = embydb.get_KodiId_by_EmbyId_EmbyType(f"{utils.MappingIds['Tag']}{EmbyId}", "Tag")
                                    dbio.DBCloseRO(ServerId, "Favorites subcontent metadata boxset")
                                    videodb = dbio.DBOpenRO("video", "Favorites change boxset (subcontent)")
                                    _, hasMusicVideos, hasMovies, hasTVShows = videodb.get_Tag_Name(KodiItemId)
                                    dbio.DBCloseRO("video", "Favorites change boxset (subcontent)")

                                    if hasMovies:
                                        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/tags/{KodiItemId}/", f'{FavoriteChanged["title"]} (Collection)', "window", 10025),))

                                    if hasTVShows:
                                        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/tags/{KodiItemId}/", f'{FavoriteChanged["title"]} (Collection)', "window", 10025),))

                                    if hasMusicVideos:
                                        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Tag", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/tags/{KodiItemId}/", f'{FavoriteChanged["title"]} (Collection)', "window", 10025),))
                                elif EmbyType == "Studio":
                                    StudioByMovie = Path.startswith("videodb://movies/studios/")
                                    StudioByTVShow = Path.startswith("videodb://tvshows/studios/")
                                    videodb = dbio.DBOpenRO("video", "Favorites change studio (subcontent)")
                                    _, hasMusicVideos, hasMovies, hasTVShows = videodb.get_Studio_Name(KodiItemId)
                                    dbio.DBCloseRO("video", "Favorites change studio (subcontent)")

                                    if StudioByMovie:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Studio", "Movies", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    elif StudioByTVShow:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Studio", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    else:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Studio", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Studio", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/studios/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                elif EmbyType == "Person":
                                    PersonByMovie = Path.startswith("videodb://movies/actors/")
                                    PersonByTVShow = Path.startswith("videodb://tvshows/actors/")
                                    videodb = dbio.DBOpenRO("video", "Favorites change person (subcontent)")
                                    _, _, hasMusicVideos, hasMovies, hasTVShows = videodb.get_People(KodiItemId)
                                    dbio.DBCloseRO("video", "Favorites change person (subcontent)")

                                    if PersonByMovie:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Actor", "Movies", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    elif PersonByTVShow:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Actor", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasMusicVideos:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Artist", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://musicvideos/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    else:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Artist", "Musicvideos", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Actor", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/actors/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                elif EmbyType == "Genre":
                                    GenreByMovie = Path.startswith("videodb://movies/genres/")
                                    videodb = dbio.DBOpenRO("video", "Favorites change genre (subcontent)")
                                    _, _, hasMovies, hasTVShows = videodb.get_Genre_Name_hasMusicVideos_hasMovies_hasTVShows(KodiItemId)
                                    dbio.DBCloseRO("video", "Favorites change genre (subcontent)")

                                    if GenreByMovie:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Genre", "Movies", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasTVShows:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "TV Shows", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://tvshows/genres/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                    else:
                                        send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Genre", "TV Show", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})

                                        if hasMovies:
                                            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Genre", "Movies", EmbyId, ServerId, ImageUrlUpdated), True, f"videodb://movies/genres/{KodiItemId}/", FavoriteChanged["title"], "window", 10025),))
                                elif EmbyType == "Series":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Series", "TV Show", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})
                                elif EmbyType == "Season":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Season", "TV Show", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})
                                elif EmbyType == "MusicArtist":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Artist", "Songs", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "music"})
                                elif EmbyType == "MusicAlbum":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Album", "Songs", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "music"})
                                elif EmbyType == "PlaylistVideo":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Playlist", "Video", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "videos"})
                                elif EmbyType == "PlaylistAudio":
                                    send_favorite({"type": FavoriteChanged["type"], "title": FavoriteChanged["title"] , "thumbnail": common.set_Favorites_Artwork_Overlay("Playlist", "Audio", EmbyId, ServerId, ImageUrlUpdated), "windowparameter": FavoriteChanged["windowparameter"], "window": "music"})
                        else: # favorite removed
                            if not isPath:
                                # remove additional existing favorite records for linked sub-content
                                if EmbyType == "MusicGenre":
                                    embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata MusicGenre")
                                    KodiIds = embydb.get_KodiId_by_EmbyId_EmbyType(EmbyId, "MusicGenre")
                                    dbio.DBCloseRO(ServerId, "Favorites subcontent metadata MusicGenre")

                                    if KodiIds:
                                        KodiIds = KodiIds.split(";")

                                        if KodiIds[1]:
                                            delete_favorite(None, FavoritesCurrent, f"musicdb://genres/{KodiIds[1]}/")

                                        if KodiIds[0]:
                                            delete_favorite(None, FavoritesCurrent, f"videodb://musicvideos/genres/{KodiIds[0]}/")
                                elif EmbyType == "Tag":
                                    delete_favorite(None, FavoritesCurrent, f"videodb://movies/tags/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://musicvideos/tags/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://tvshows/tags/{KodiItemId}/")

                                    # collections assigned to tags -> utils.BoxSetsToTags
                                    if str(EmbyId).startswith(utils.MappingIds['Tag']):
                                        EmbySetId = str(EmbyId).replace(utils.MappingIds['Tag'], "")
                                        embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata set")
                                        KodiItemId = embydb.get_KodiId_by_EmbyId_EmbyType(EmbySetId, "BoxSet")
                                        dbio.DBCloseRO(ServerId, "Favorites subcontent metadata set")
                                        delete_favorite(None, FavoritesCurrent, f"videodb://movies/sets/{KodiItemId}/")
                                elif EmbyType == "BoxSet":
                                    # collections assigned to tags -> utils.BoxSetsToTags
                                    embydb = dbio.DBOpenRO(ServerId, "Favorites subcontent metadata set")
                                    KodiItemId = embydb.get_KodiId_by_EmbyId_EmbyType(f"{utils.MappingIds['Tag']}{EmbyId}", "Tag")
                                    dbio.DBCloseRO(ServerId, "Favorites subcontent metadata set")

                                    if KodiItemId:
                                        delete_favorite(None, FavoritesCurrent, f"videodb://movies/tags/{KodiItemId}/")
                                        delete_favorite(None, FavoritesCurrent, f"videodb://musicvideos/tags/{KodiItemId}/")
                                        delete_favorite(None, FavoritesCurrent, f"videodb://tvshows/tags/{KodiItemId}/")
                                elif EmbyType == "Studio":
                                    delete_favorite(None, FavoritesCurrent, f"videodb://movies/studios/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://tvshows/studios/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://musicvideos/studios/{KodiItemId}/")
                                elif EmbyType == "Person":
                                    delete_favorite(None, FavoritesCurrent, f"videodb://movies/actors/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://tvshows/actors/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://musicvideos/actors/{KodiItemId}/")
                                elif EmbyType == "Genre":
                                    delete_favorite(None, FavoritesCurrent, f"videodb://movies/genres/{KodiItemId}/")
                                    delete_favorite(None, FavoritesCurrent, f"videodb://tvshows/genres/{KodiItemId}/")

                        # Update Emby favorites
                        if EmbyId:
                            if str(EmbyId).startswith(utils.MappingIds['Tag']): # skip collections assigned to tags -> utils.BoxSetsToTags
                                EmbyId = str(EmbyId).replace(utils.MappingIds['Tag'], "")

                            utils.ItemSkipUpdate.append(str(EmbyId))
                            if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): ItemSkipUpdate favorite update: {utils.ItemSkipUpdate}", 1) # LOGDEBUG
                            utils.EmbyServers[ServerId].API.favorite(EmbyId, isAdded)

            FavoritesCached = get_Favorites()

def get_Favorites():
    Result = utils.SendJson('{"jsonrpc":"2.0", "method":"Favourites.GetFavourites", "params":{"properties":["windowparameter", "path", "thumbnail", "window"]}, "id": 1}').get("result", {})

    if Result:
        Favorites = Result.get("favourites", [])

        if Favorites: # Favorites can be "None"
            FavoriteData = {"Favorites": Favorites, "Path": len(Favorites) * [""], "Filtered": len(Favorites) * [""], "Title": len(Favorites) * [""], "ImageUrl": len(Favorites) * [""]}

            for Index, Favorite in enumerate(Favorites):
                if 'path' in Favorite:
                    FavoriteData["Path"][Index] = Favorite['path']
                    FavoriteData["Filtered"][Index] = filter_path(Favorite['path'])
                elif 'windowparameter' in Favorite:
                    FavoriteData["Path"][Index] = Favorite['windowparameter']
                    FavoriteData["Filtered"][Index] = filter_path(Favorite['windowparameter'])

                FavoriteData["Title"][Index] = Favorite.get('title', "")
                FavoriteData["ImageUrl"][Index] = Favorite.get('thumbnail', "")

            return FavoriteData

    return {"Favorites": [], "Path": [], "Filtered": [], "Title": [], "ImageUrl": []}

def filter_path(Path):
    PathPos = Path.find("?")

    if PathPos != -1:
        Path = Path[:PathPos]

    return Path

def get_path(Favorite):
    if Favorite:
        if "windowparameter" in Favorite:
            return Favorite["windowparameter"], False

        if "path" in Favorite:
            return Favorite["path"], True

    return "", False

def delete_favorite(Favorite, Favorites, PathCheck):
    _, _, FoundIndex, isValid = get_existing_favorite(Favorite, Favorites, PathCheck)

    if isValid and FoundIndex != -1:
        send_favorite(Favorites["Favorites"][FoundIndex])
        del Favorites["Favorites"][FoundIndex]
        del Favorites["Path"][FoundIndex]
        del Favorites["Filtered"][FoundIndex]
        del Favorites["Title"][FoundIndex]
        del Favorites["ImageUrl"][FoundIndex]

def get_existing_favorite(Favorite, Favorites, PathCheck):
    FoundInPath = False
    FoundInPathFiltered = False
    PathIndex = -1

    if PathCheck:
        Path = PathCheck
    else:
        Path, _ = get_path(Favorite)

    if Path:
        PathFiltered = filter_path(Path)

        if Path in Favorites["Path"]:
            FoundInPath = True
            PathIndex = Favorites["Path"].index(Path)
        elif PathFiltered in Favorites["Filtered"]:
            FoundInPathFiltered = True
            PathIndex = Favorites["Filtered"].index(PathFiltered)

    return FoundInPath, FoundInPathFiltered, PathIndex, bool(Path)

def update_favorite(Favorite, Path, ImageUrl):
    FavoriteUpdated = Favorite.copy()

    if ImageUrl:
        FavoriteUpdated["thumbnail"] = ImageUrl

    if 'path' in Favorite:
        FavoriteUpdated["path"] = Path
    else:
        FavoriteUpdated["windowparameter"] = Path

    return FavoriteUpdated

def send_favorite(Favorite):
    global FavoriteUpdatedByEmby
    FavoriteUpdatedByEmby = True

    if 'path' in Favorite:
        utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Favorite["type"]}", "title":"{Favorite["title"]}", "thumbnail":"{Favorite["thumbnail"]}", "path":"{Favorite["path"]}"}}, "id": 1}}')
    else:
        utils.SendJson(f'{{"jsonrpc":"2.0", "method":"Favourites.AddFavourite", "params":{{"type":"{Favorite["type"]}", "title":"{Favorite["title"]}", "thumbnail":"{Favorite["thumbnail"]}", "windowparameter":"{Favorite["windowparameter"]}", "window":"{Favorite["window"]}"}}, "id": 1}}')

def set_Favorite_Emby_Media(Path, isFavorite):
    if Path.startswith("dav://127.0.0.1:57342/") or Path.startswith("http://127.0.0.1:57342/") or Path.startswith("/emby_addon_mode/"):
        Path = Path.replace("dav://127.0.0.1:57342/", "").replace("http://127.0.0.1:57342/", "").replace("/emby_addon_mode/", "")
        ServerId = Path.split("/")[1]
        EmbyId = Path[Path.rfind("/"):].split("-")[1]
        utils.ItemSkipUpdate.append(str(EmbyId))
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): ItemSkipUpdate: {utils.ItemSkipUpdate}", 1) # LOGDEBUG
        utils.EmbyServers[ServerId].API.favorite(EmbyId, isFavorite)

def emby_change_Favorite(): # Threaded / queued
    if utils.DebugLog: xbmc.log("EMBY.hooks.favorites (DEBUG): THREAD: --->[ Kodi favorites mods ]", 1) # LOGDEBUG

    while True:
        utils.sleep(0.5)
        Favorites = utils.FavoriteQueue.getall()

        if Favorites == ["QUIT"]:
            if utils.DebugLog: xbmc.log("EMBY.hooks.favorites (DEBUG): THREAD: ---<[ Kodi favorites mods ]", 1) # LOGDEBUG
            return

        if not utils.SyncFavorites:
            continue

        FavoritesCurrent = get_Favorites()

        # Filter doubles
        seen = set()
        filtered = [None] * len(Favorites)
        idx = 0

        for fav in reversed(Favorites):
            if fav[2] not in seen:
                seen.add(fav[2])
                filtered[idx] = fav
                idx += 1

        Favorites = filtered[:idx]

        # Updated favorites
        for Favorite in Favorites: # Favorite = (ImageUrl, IsFavorite, FullPath, Title, "media", WindowId)
            FoundInPath, FoundInPathFiltered, FoundIndex, isValid = get_existing_favorite(None, FavoritesCurrent, Favorite[2])

            if not isValid:
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.favorites (DEBUG): Invalid item: {Favorite}", 1) # LOGDEBUG
                continue

            if Favorite[1]:
                if not FoundInPath and not FoundInPathFiltered: # is favorite and doesn't exist
                    if Favorite[4] == "media":
                        FavoriteNew = {"type": Favorite[4], "title": Favorite[3] , "thumbnail": Favorite[0], "path": Favorite[2]}
                    else:
                        FavoriteNew = {"type": Favorite[4], "title": Favorite[3] , "thumbnail": Favorite[0], "windowparameter": Favorite[2], "window": Favorite[5]}

                    send_favorite(FavoriteNew)
                else: # if favorite exists but title or artwork has changed
                    if FavoritesCurrent["Favorites"][FoundIndex]["title"] != Favorite[3] or FavoritesCurrent["Favorites"][FoundIndex]["thumbnail"] != Favorite[0]:
                        send_favorite(FavoritesCurrent["Favorites"][FoundIndex]) # remove existing favorite record

                        if Favorite[4] == "media":
                            FavoriteNew = {"type": FavoritesCurrent["Favorites"][FoundIndex]['type'], "title": Favorite[3] , "thumbnail": Favorite[0], "path": FavoritesCurrent["Favorites"][FoundIndex]['path']}
                        else:
                            FavoriteNew = {"type": FavoritesCurrent["Favorites"][FoundIndex]['type'], "title": Favorite[3] , "thumbnail": Favorite[0], "windowparameter": FavoritesCurrent["Favorites"][FoundIndex]['windowparameter'], "window": FavoritesCurrent["Favorites"][FoundIndex]['window']}

                        send_favorite(FavoriteNew)
            else:
                if FoundInPath or FoundInPathFiltered: # is not favorite and exist
                    send_favorite(FavoritesCurrent["Favorites"][FoundIndex]) # remove existing favorite record

def set_Favorites(Enabled):
    if not Enabled:
        FavoritesCurrent = get_Favorites()

        for Index, ImageUrl in enumerate(FavoritesCurrent["ImageUrl"]):
            if ImageUrl.startswith("http://127.0.0.1:57342/"):
                send_favorite(FavoritesCurrent["Favorites"][Index])
    else:
        for EmbyServer in list(utils.EmbyServers.values()):
            update_Audio(EmbyServer)
            update_MusicAlbum(EmbyServer)
            update_Video(EmbyServer)
            update_MusicVideo(EmbyServer)
            update_Movie(EmbyServer)
            update_Episode(EmbyServer)
            update_Series(EmbyServer)
            update_Season(EmbyServer)
            update_Playlist(EmbyServer)
            update_BoxSet(EmbyServer)
            update_Genre(EmbyServer)
            update_Studio(EmbyServer)
            update_Tag(EmbyServer)
            update_MusicGenre(EmbyServer)
            update_Person(EmbyServer)
            update_MusicArtist(EmbyServer)

def update_Audio(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Audio")
    AudioInfos = embydb.get_FavoriteInfos("Audio") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Audio")
    SQLs = {"music": dbio.DBOpenRO("music", "update_Audio")}
    utils.create_ProgressBar("update_Audio", utils.Translate(33199), utils.Translate(33844))
    AudioObject = audio.Audio(EmbyServer, SQLs)
    RecordsPercent = len(AudioInfos) / 100

    for Index, AudioInfo in enumerate(AudioInfos):
        if AudioInfo[0]:
            AudioObject.set_favorite(AudioInfo[0], {"KodiItemId": AudioInfo[1], "Id": AudioInfo[2]})

        utils.update_ProgressBar("update_Audio", Index / RecordsPercent, utils.Translate(33844), str(AudioInfo[1]))

    del AudioObject
    dbio.DBCloseRO("music", "update_Audio")
    utils.close_ProgressBar("update_Audio")

def update_MusicAlbum(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_MusicAlbum")
    MusicAlbumInfos = embydb.get_FavoriteInfos("MusicAlbum") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_MusicAlbum")
    SQLs = {"music": dbio.DBOpenRO("music", "update_MusicAlbum")}
    utils.create_ProgressBar("update_MusicAlbum", utils.Translate(33199), utils.Translate(33845))
    MusicAlbumObject = musicalbum.MusicAlbum(EmbyServer, SQLs)
    RecordsPercent = len(MusicAlbumInfos) / 100

    for Index, MusicAlbumInfo in enumerate(MusicAlbumInfos):
        if MusicAlbumInfo[0]:
            MusicAlbumObject.set_favorite(MusicAlbumInfo[0], {"KodiItemId": MusicAlbumInfo[1], "Id": MusicAlbumInfo[2]})

        utils.update_ProgressBar("update_MusicAlbum", Index / RecordsPercent, utils.Translate(33845), str(MusicAlbumInfo[1]))

    del MusicAlbumObject
    dbio.DBCloseRO("music", "update_MusicAlbum")
    utils.close_ProgressBar("update_MusicAlbum")

def update_Video(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Video")
    VideoInfos = embydb.get_FavoriteInfos("Video") # EmbyFavourite, KodiFileId, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Video")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Video")}
    utils.create_ProgressBar("update_Video", utils.Translate(33199), utils.Translate(33846))
    VideoObject = videos.Videos(EmbyServer, SQLs)
    RecordsPercent = len(VideoInfos) / 100

    for Index, VideoInfo in enumerate(VideoInfos):
        if VideoInfo[0]:
            VideoObject.set_favorite(VideoInfo[0], {"KodiItemId": VideoInfo[2], "Id": VideoInfo[3], "KodiFileId": VideoInfo[1]})

        utils.update_ProgressBar("update_Video", Index / RecordsPercent, utils.Translate(33846), str(VideoInfo[1]))

    del VideoObject
    dbio.DBCloseRO("video", "update_Video")
    utils.close_ProgressBar("update_Video")

def update_MusicVideo(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_MusicVideo")
    MusicVideoInfos = embydb.get_FavoriteInfos("MusicVideo") # EmbyFavourite, KodiFileId, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_MusicVideo")
    SQLs = {"video": dbio.DBOpenRO("video", "update_MusicVideo")}

    utils.create_ProgressBar("update_MusicVideo", utils.Translate(33199), utils.Translate(33847))
    MusicVideoObject = musicvideo.MusicVideo(EmbyServer, SQLs)
    RecordsPercent = len(MusicVideoInfos) / 100

    for Index, MusicVideoInfo in enumerate(MusicVideoInfos):
        if MusicVideoInfo[0]:
            MusicVideoObject.set_favorite(MusicVideoInfo[0], {"KodiItemId": MusicVideoInfo[2], "Id": MusicVideoInfo[3], "KodiFileId": MusicVideoInfo[1]})

        utils.update_ProgressBar("update_MusicVideo", Index / RecordsPercent, utils.Translate(33847), str(MusicVideoInfo[1]))

    del MusicVideoObject
    dbio.DBCloseRO("video", "update_MusicVideo")
    utils.close_ProgressBar("update_MusicVideo")

def update_BoxSet(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_BoxSet")
    BoxSetInfos = embydb.get_FavoriteInfos("BoxSet") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_BoxSet")
    SQLs = {"video": dbio.DBOpenRO("video", "update_BoxSet")}
    utils.create_ProgressBar("update_BoxSet", utils.Translate(33199), utils.Translate(33848))
    BoxSetObject = boxsets.BoxSets(EmbyServer, SQLs)
    RecordsPercent = len(BoxSetInfos) / 100

    for Index, BoxSetInfo in enumerate(BoxSetInfos):
        if BoxSetInfo[0]:
            BoxSetObject.set_favorite(BoxSetInfo[0], {"KodiItemId": BoxSetInfo[1], "Id": BoxSetInfo[2]})

        utils.update_ProgressBar("update_BoxSet", Index / RecordsPercent, utils.Translate(33848), str(BoxSetInfo[1]))

    del BoxSetObject
    dbio.DBCloseRO("video", "update_BoxSet")
    utils.close_ProgressBar("update_BoxSet")

def update_Series(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Series")
    SeriesInfos = embydb.get_FavoriteInfos("Series") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Series")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Series")}
    utils.create_ProgressBar("update_Series", utils.Translate(33199), utils.Translate(33849))
    SeriesObject = series.Series(EmbyServer, SQLs)
    RecordsPercent = len(SeriesInfos) / 100

    for Index, SeriesInfo in enumerate(SeriesInfos):
        if SeriesInfo[0]:
            SeriesObject.set_favorite(SeriesInfo[0], {"KodiItemId": SeriesInfo[1], "Id": SeriesInfo[2]})

        utils.update_ProgressBar("update_Series", Index / RecordsPercent, utils.Translate(33849), str(SeriesInfo[1]))

    del SeriesObject
    dbio.DBCloseRO("video", "update_Series")
    utils.close_ProgressBar("update_Series")

def update_Season(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Season")
    SeasonInfos = embydb.get_FavoriteInfos("Season") # EmbyFavourite, KodiId, KodiParentId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Season")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Season")}
    utils.create_ProgressBar("update_Season", utils.Translate(33199), utils.Translate(33850))
    SeasonObject = season.Season(EmbyServer, SQLs)
    RecordsPercent = len(SeasonInfos) / 100

    for Index, SeasonInfo in enumerate(SeasonInfos):
        if SeasonInfo[0]:
            SeasonObject.set_favorite(SeasonInfo[0], {"KodiItemId": SeasonInfo[1], "Id": SeasonInfo[3], "KodiParentId": SeasonInfo[2]})

        utils.update_ProgressBar("update_Season", Index / RecordsPercent, utils.Translate(33850), str(SeasonInfo[1]))

    del SeasonObject
    dbio.DBCloseRO("video", "update_Season")
    utils.close_ProgressBar("update_Season")

def update_Playlist(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Playlist")
    PlaylistInfo = embydb.get_FavoriteInfos("Playlist") # EmbyFavourite, KodiId, EmbyArtwork, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Playlist")
    utils.create_ProgressBar("update_Playlist", utils.Translate(33199), utils.Translate(33851))
    PlaylistObject = playlist.Playlist(EmbyServer, {})
    RecordsPercent = len(PlaylistInfo) / 100

    for Index, PlaylistInfo in enumerate(PlaylistInfo):
        if PlaylistInfo[0]:
            PlaylistObject.set_favorite(PlaylistInfo[0], {"KodiItemId": PlaylistInfo[1], "Id": PlaylistInfo[3], "KodiArtwork": {'favourite': PlaylistInfo[2]}})

        utils.update_ProgressBar("update_Playlist", Index / RecordsPercent, utils.Translate(33851), str(PlaylistInfo[1]))

    del PlaylistObject
    utils.close_ProgressBar("update_Playlist")

def update_Episode(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Episode")
    EpisodeInfos = embydb.get_FavoriteInfos("Episode") # EmbyFavourite, KodiFileId, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Episode")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Episode")}
    utils.create_ProgressBar("update_Episode", utils.Translate(33199), utils.Translate(33852))
    EpisodeObject = episode.Episode(EmbyServer, SQLs)
    RecordsPercent = len(EpisodeInfos) / 100

    for Index, EpisodeInfo in enumerate(EpisodeInfos):
        if EpisodeInfo[0]:
            EpisodeObject.set_favorite(EpisodeInfo[0], {"KodiItemId": EpisodeInfo[1], "Id": EpisodeInfo[3], "KodiFileId": EpisodeInfo[2]})

        utils.update_ProgressBar("update_Episode", Index / RecordsPercent, utils.Translate(33852), str(EpisodeInfo[1]))

    del EpisodeObject
    dbio.DBCloseRO("video", "update_Episode")
    utils.close_ProgressBar("update_Episode")

def update_Movie(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Movie")
    MoviesInfos = embydb.get_FavoriteInfos("Movie") # EmbyFavourite, KodiFileId, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Movie")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Movie")}
    utils.create_ProgressBar("update_Movie", utils.Translate(33199), utils.Translate(33853))
    MovieObject = movies.Movies(EmbyServer, SQLs)
    RecordsPercent = len(MoviesInfos) / 100

    for Index, MovieInfo in enumerate(MoviesInfos):
        if MovieInfo[0]:
            MovieObject.set_favorite(MovieInfo[0], {"KodiItemId": MovieInfo[1], "Id": MovieInfo[3], "KodiFileId": MovieInfo[2]})

        utils.update_ProgressBar("update_Movie", Index / RecordsPercent, utils.Translate(33853), str(MovieInfo[1]))

    del MovieObject
    dbio.DBCloseRO("video", "update_Movie")
    utils.close_ProgressBar("update_Movie")

def update_Genre(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Genre")
    GenresInfos = embydb.get_FavoriteInfos("Genre") # EmbyFavourite, KodiId, EmbyArtwork, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Genre")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Genre")}
    utils.create_ProgressBar("update_Genre", utils.Translate(33199), utils.Translate(33854))
    GenreObject = genre.Genre(EmbyServer, SQLs)
    RecordsPercent = len(GenresInfos) / 100

    for Index, GenreInfo in enumerate(GenresInfos):
        if GenreInfo[0]:
            GenreObject.set_favorite(GenreInfo[0], {"KodiItemId": GenreInfo[1], "Id": GenreInfo[3], "KodiArtwork": {'favourite': GenreInfo[2]}})

        utils.update_ProgressBar("update_Genre", Index / RecordsPercent, utils.Translate(33854), str(GenreInfo[1]))

    del GenreObject
    dbio.DBCloseRO("video", "update_Genre")
    utils.close_ProgressBar("update_Genre")

def update_Studio(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Studio")
    StudioInfos = embydb.get_FavoriteInfos("Studio") # EmbyFavourite, KodiId, EmbyArtwork, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Studio")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Studio")}
    utils.create_ProgressBar("update_Studio", utils.Translate(33199), utils.Translate(33855))
    StudioObject = studio.Studio(EmbyServer, SQLs)
    RecordsPercent = len(StudioInfos) / 100

    for Index, StudioInfo in enumerate(StudioInfos):
        if StudioInfo[0]:
            StudioObject.set_favorite(StudioInfo[0], {"KodiItemId": StudioInfo[1], "Id": StudioInfo[3], "KodiArtwork": {'favourite': StudioInfo[2]}})

        utils.update_ProgressBar("update_Studio", Index / RecordsPercent, utils.Translate(33855), str(StudioInfo[1]))

    del StudioObject
    dbio.DBCloseRO("video", "update_Studio")
    utils.close_ProgressBar("update_Studio")

def update_Tag(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Tag")
    TagsInfos = embydb.get_FavoriteInfos("Tag") # EmbyFavourite, KodiId, EmbyArtwork, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Tag")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Tag")}
    utils.create_ProgressBar("update_Tag", utils.Translate(33199), utils.Translate(33856))
    TagObject = tag.Tag(EmbyServer, SQLs)
    RecordsPercent = len(TagsInfos) / 100

    for Index, TagInfo in enumerate(TagsInfos):
        if TagInfo[0]:
            TagObject.set_favorite(TagInfo[0], {"KodiItemId": TagInfo[1], "Id": TagInfo[3], "KodiArtwork": {'favourite': TagInfo[2]}})

        utils.update_ProgressBar("update_Tag", Index / RecordsPercent, utils.Translate(33856), str(TagInfo[1]))

    dbio.DBCloseRO("video", "update_Tag")
    del TagObject
    utils.close_ProgressBar("update_Tag")

def update_MusicGenre(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_MusicGenre")
    MusicGenreInfos = embydb.get_FavoriteInfos("MusicGenre") # EmbyFavourite, KodiId, EmbyArtwork, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_MusicGenre")
    SQLs = {"music": dbio.DBOpenRO("music", "update_MusicGenre"), "video": dbio.DBOpenRO("video", "update_MusicGenre")}
    utils.create_ProgressBar("update_MusicGenre", utils.Translate(33199), utils.Translate(33857))
    MusicGenreObject = musicgenre.MusicGenre(EmbyServer, SQLs)
    RecordsPercent = len(MusicGenreInfos) / 100

    for Index, MusicGenreInfo in enumerate(MusicGenreInfos):
        if MusicGenreInfo[0]:
            MusicGenreObject.set_favorite(MusicGenreInfo[0], {"KodiItemId": MusicGenreInfo[1], "Id": MusicGenreInfo[3], "KodiArtwork": {'favourite': MusicGenreInfo[2]}})

        utils.update_ProgressBar("update_MusicGenre", Index / RecordsPercent, utils.Translate(33857), str(MusicGenreInfo[1]))

    dbio.DBCloseRO("music", "update_MusicGenre")
    dbio.DBCloseRO("video", "update_MusicGenre")
    del MusicGenreObject
    utils.close_ProgressBar("update_MusicGenre")

def update_Person(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_Person")
    PersonInfos = embydb.get_FavoriteInfos("Person") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_Person")
    SQLs = {"video": dbio.DBOpenRO("video", "update_Person")}
    utils.create_ProgressBar("update_Person", utils.Translate(33199), utils.Translate(33858))
    PersonObject = person.Person(EmbyServer, SQLs)
    RecordsPercent = len(PersonInfos) / 100

    for Index, PersonInfo in enumerate(PersonInfos):
        if PersonInfo[0]:
            PersonObject.set_favorite(PersonInfo[0], {"KodiItemId": PersonInfo[1], "Id": PersonInfo[2]})

        utils.update_ProgressBar("update_Person", Index / RecordsPercent, utils.Translate(33858), str(PersonInfo[1]))

    dbio.DBCloseRO("video", "update_Person")
    del PersonObject
    utils.close_ProgressBar("update_Person")

def update_MusicArtist(EmbyServer):
    embydb = dbio.DBOpenRO(EmbyServer.ServerData['ServerId'], "update_MusicArtist")
    MusicArtistInfos = embydb.get_FavoriteInfos("MusicArtist") # EmbyFavourite, KodiId, EmbyId
    dbio.DBCloseRO(EmbyServer.ServerData['ServerId'], "update_MusicArtist")
    SQLs = {"music": dbio.DBOpenRO("music", "update_MusicArtist"), "video": dbio.DBOpenRO("video", "update_MusicArtist")}
    utils.create_ProgressBar("update_MusicArtist", utils.Translate(33199), utils.Translate(33859))
    MusicArtistObject = musicartist.MusicArtist(EmbyServer, SQLs)
    RecordsPercent = len(MusicArtistInfos) / 100

    for Index, MusicArtistInfo in enumerate(MusicArtistInfos):
        if MusicArtistInfo[0]:
            MusicArtistObject.set_favorite(MusicArtistInfo[0], {"KodiItemId": MusicArtistInfo[1], "Id": MusicArtistInfo[2]})

        utils.update_ProgressBar("update_MusicArtist", Index / RecordsPercent, utils.Translate(33859), str(MusicArtistInfo[1]))

    dbio.DBCloseRO("music", "update_MusicArtist")
    dbio.DBCloseRO("video", "update_MusicArtist")
    del MusicArtistObject
    utils.close_ProgressBar("update_MusicArtist")

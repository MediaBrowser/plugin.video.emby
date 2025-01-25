from urllib.parse import quote
import xbmc
from helper import utils
from database import dbio

# filename, label, icon, content, [(rule1, Filter, Operator),...], [direction, order], useLimit, group, Subfolder
SyncNodes = {
    'tvshows': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("sorttitle", "startswith")), ("ascending", "sorttitle"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultTVShows.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('recentlyaddedepisodes', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "episodes", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('inprogress', utils.Translate(30171), 'DefaultInProgressShows.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("inprogress", "true")), ("descending", "lastplayed"), False, False),
        ('inprogressepisodes', utils.Translate(30178), 'DefaultInProgressShows.png', "episodes", (("tag", "is", "LIBRARYTAG"), ("inprogress", "true")), ("descending", "lastplayed"), False, False),
        ('genres', utils.Translate(33248), 'DefaultGenre.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0"), ("rating", "greaterthan", "7")), ("descending", "rating"), True, None),
        ('years', utils.Translate(33218), 'DefaultYear.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('actors', utils.Translate(33219), 'DefaultActor.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "actors"),
        ('tags', utils.Translate(33220), 'DefaultTags.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "tags"),
        ('collections', utils.Translate(33612), 'DefaultTags.png', "tvshows", (("PLUGIN", "collections", "tvshow"),)),
        ('favorites', utils.Translate(33558), 'DefaultTags.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("tag", "endswith", "(Favorites)")), ("ascending", "title"), False, False),
        ('unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0")), ("random",), True, False),
        ('unwatchedepisodes', utils.Translate(33344), 'OverlayUnwatched.png', "episodes", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0")), ("random",), False, False),
        ('studios', utils.Translate(33249), 'DefaultStudios.png', "tvshows", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "studios"),
        ('recentlyplayed', utils.Translate(33347), 'DefaultMusicRecentlyPlayed.png', "tvshows", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, None),
        ('recentlyplayedepisodes', utils.Translate(33351), 'DefaultMusicRecentlyPlayed.png', "episodes", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, None),
        ('nextepisodes', utils.Translate(30179), 'DefaultInProgressShows.png', "tvshows", (("PLUGIN", "nextepisodes", "episode"),)),
        ('nextepisodesplayed', utils.Translate(33667), 'DefaultInProgressShows.png', "tvshows", (("PLUGIN", "nextepisodesplayed", "episode"),)),
    ],
    'movies': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "movies", (("tag", "is", "LIBRARYTAG"), ("sorttitle", "startswith"),), ("ascending", "sorttitle"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultMovies.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "movies", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('recentlyreleased', utils.Translate(33619), 'DefaultRecentlyAddedMovies.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("descending", "year"), True, False),
        ('inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "true")), ("descending", "lastplayed"), False, False),
        ('unwatched', utils.Translate(30189), 'OverlayUnwatched.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0")), ("random",), True, False),
        ('recentlyreleasedunwatched', utils.Translate(33618), 'OverlayUnwatched.png', "movies", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "year"), True, False),
        ('sets', utils.Translate(30185), 'DefaultSets.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "sets"),
        ('genres', utils.Translate(33248), 'DefaultGenre.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0"), ("rating", "greaterthan", "7")), ("descending", "rating"), True, False),
        ('years', utils.Translate(33218), 'DefaultYear.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('actors', utils.Translate(33219), 'DefaultActor.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "actors"),
        ('tags', utils.Translate(33220), 'DefaultTags.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "tags"),
        ('collections', utils.Translate(33612), 'DefaultSets.png', "movies", (("PLUGIN", "collections", "movie"),)),
        ('favorites', utils.Translate(33558), 'DefaultTags.png', "movies", (("tag", "is", "LIBRARYTAG"), ("tag", "endswith", "(Favorites)")), ("ascending", "title"), False, False),
        ('studios', utils.Translate(33249), 'DefaultStudios.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "studios"),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('directors', utils.Translate(33352), 'DefaultDirector.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "directors"),
        ('countries', utils.Translate(33358), 'DefaultCountry.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "countries"),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "is", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "lessthan", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "greaterthan", "1080")), ("ascending", "sorttitle"), False, False)
    ],
    'musicvideos': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("artist", "startswith")), ("ascending", "sorttitle"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultMusicVideos.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("ascending", "artist"), False, False),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('genres', utils.Translate(33248), 'DefaultGenre.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "albums"),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("inprogress", "true")), ("descending", "lastplayed"), False, False),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0")), ("random",), True, False),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("ascending", "artists"), False, "artists"),
        ('tags', utils.Translate(33220), 'DefaultTags.png', "musicvideos", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "tags"),
        ('collections', utils.Translate(33612), 'DefaultSets.png', "musicvideos", (("PLUGIN", "collections", "musicvideo"),)),
        ('favorites', utils.Translate(33558), 'DefaultTags.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("tag", "endswith", "(Favorites)")), ("ascending", "title"), False, False),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "is", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "lessthan", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png', "musicvideos", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "greaterthan", "1080")), ("ascending", "sorttitle"), False, False)
    ],
    'homevideos': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "movies", (("tag", "is", "LIBRARYTAG"), ("sorttitle", "startswith")), ("ascending", "sorttitle"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultMusicVideos.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "movies", (("tag", "is", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('genres', utils.Translate(33248), 'DefaultGenre.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "true")), ("descending", "lastplayed"), False, False),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "is", "0")), ("random",), True, False),
        ('tags', utils.Translate(33220), 'DefaultTags.png', "movies", (("tag", "is", "LIBRARYTAG"),), ("ascending", "title"), False, "tags"),
        ('collections', utils.Translate(33612), 'DefaultSets.png', "movies", (("PLUGIN", "collections", "movie"),)),
        ('favorites', utils.Translate(33558), 'DefaultTags.png', "movies", (("tag", "is", "LIBRARYTAG"), ("tag", "endswith", "(Favorites)")), ("ascending", "title"), False, False),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "movies", (("tag", "is", "LIBRARYTAG"), ("inprogress", "false"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "is", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "lessthan", "1080")), ("ascending", "sorttitle"), False, False),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png', "movies", (("tag", "is", "LIBRARYTAG"), ("videoresolution", "greaterthan", "1080")), ("ascending", "sorttitle"), False, False)
    ],
    'music': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("artist", "startswith")), ("ascending", "artist"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultAddonMusic.png', "artists", (("disambiguation", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('years', utils.Translate(33697), 'DefaultMusicYears.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('singlesyears', utils.Translate(33698), 'DefaultMusicYears.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("descending", "year"), True, "singles"),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png', "artists", (("artists", "disambiguation", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('songsbygenres', utils.Translate(33435), 'DefaultMusicGenres.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("genre", "is")), ("ascending", "title"), True, False, ("genres", "DBMUSICGENRE")),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("role", "is", "artist")), ("ascending", "artists"), False, False),
        ('composers', utils.Translate(33426), 'DefaultMusicArtists.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("role", "is", "composer")), ("ascending", "artists"), False, False),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "title"), False, "albums"),
        ('singles', utils.Translate(33699), 'DefaultMusicAlbums.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("descending", "title"), False, "singles"),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "dateadded"), True, False),
        ('recentlyaddedsingles', utils.Translate(33700), 'DefaultMusicRecentlyAdded.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("descending", "dateadded"), False, "singles"),
        ('recentlyadded', utils.Translate(33390), 'DefaultMusicRecentlyAdded.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "albums", (("type", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('randomsingles', utils.Translate(33701), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "songs", (("type", "is", "LIBRARYTAG"),), ("random",), True, "singles"),
        ('random', utils.Translate(33392), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("random",), True, False)
    ],
    'audiobooks': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("artist", "startswith")), ("ascending", "artist"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultAddonMusic.png', "artists", (("disambiguation", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png', "artists", (("artists", "disambiguation", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("role", "is", "artist")), ("ascending", "artists"), False, False),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "title"), False, "albums"),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "dateadded"), True, False),
        ('recentlyadded', utils.Translate(33389), 'DefaultMusicRecentlyAdded.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "albums", (("type", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('random', utils.Translate(33393), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("random",), True, False)
    ],
    'podcasts': [
        ('letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("artist", "startswith")), ("ascending", "artist"), False, False, ("letter", "LETTER")),
        ('all', "LIBRARYNAME", 'DefaultAddonMusic.png', "artists", (("disambiguation", "is", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, False),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "year"), True, "years"),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png', "artists", (("artists", "disambiguation", "LIBRARYTAG"),), ("ascending", "sorttitle"), False, "genres"),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png', "artists", (("disambiguation", "is", "LIBRARYTAG"), ("role", "is", "artist")), ("ascending", "artists"), False, False),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "title"), False, "albums"),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png', "albums", (("type", "is", "LIBRARYTAG"),), ("descending", "dateadded"), True, False),
        ('recentlyadded', utils.Translate(33395), 'DefaultMusicRecentlyAdded.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "is", "0")), ("descending", "dateadded"), True, False),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png', "songs", (("comment", "endswith", "LIBRARYTAG"), ("playcount", "greaterthan", "0")), ("descending", "lastplayed"), True, False),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "albums", (("type", "is", "LIBRARYTAG"),), ("random",), True, False),
        ('random', utils.Translate(33394), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "songs", (("comment", "endswith", "LIBRARYTAG"),), ("random",), True, False)
    ],
    'rootaudio': [
        ('emby_playlists',  f"EMBY: {utils.Translate(33376)}", 'DefaultMusicPlaylists.png', "audio", (("PLUGIN", "playlist", "audio"),), (), False, True),
        ('emby_inprogressmixed', f"EMBY: {utils.Translate(33628)}", 'DefaultInProgressShows.png', "mixed", (("PLUGIN", "inprogressmixed", "mixed"),))
    ],
    'rootvideo': [
        ('emby_playlists', f"EMBY: {utils.Translate(33376)}", 'DefaultMusicPlaylists.png', "video", (("PLUGIN", "playlist", "video"),), (), False, True),
        ('emby_inprogressmixed', f"EMBY: {utils.Translate(33628)}", 'DefaultInProgressShows.png', "mixed", (("PLUGIN", "inprogressmixed", "mixed"),)),
        ('emby_nextepisodes', f"EMBY: {utils.Translate(33665)}", 'DefaultInProgressShows.png', "tvshows", (("PLUGIN", "nextepisodes", "episode"),)),
        ('emby_nextepisodesplayed', f"EMBY: {utils.Translate(33666)}", 'DefaultInProgressShows.png', "tvshows", (("PLUGIN", "nextepisodesplayed", "episode"),)),
        ('emby_favorite_movies', f"EMBY: {utils.Translate(30180)}", 'DefaultFavourites.png', "movies", (("tag", "is", "Movies (Favorites)"),), ("ascending", "sorttitle"), False, False),
        ('emby_favorite_series', f"EMBY: {utils.Translate(30181)}", 'DefaultFavourites.png', "tvshows", (("tag", "is", "TVShows (Favorites)"),), ("ascending", "sorttitle"), False, False),
        ('emby_favorite_episodes', f"EMBY: {utils.Translate(30182)}", 'DefaultFavourites.png', "episodes", (("PLUGIN", "favepisodes", "episode"),)),
        ('emby_favorite_seasons', f"EMBY: {utils.Translate(33576)}", 'DefaultFavourites.png', "seasons", (("PLUGIN", "favseasons", "season"),)),
        ('emby_favorite_musicvideos', f"EMBY: {utils.Translate(33385)}", 'DefaultFavourites.png', "musicvideos", (("tag", "is", "Musicvideos (Favorites)"),), ("ascending", "sorttitle"), False, False),
        ('emby_collections_movies', f"EMBY: {utils.Translate(33555)}", 'DefaultTags.png', "movies", (("PLUGIN", "collections", "movie"),)),
        ('emby_collections_tvshows', f"EMBY: {utils.Translate(33556)}", 'DefaultTags.png', "tvshows", (("PLUGIN", "collections", "tvshow"),)),
        ('emby_collections_musicvideos', f"EMBY: {utils.Translate(33557)}", 'DefaultTags.png', "musicvideos", (("PLUGIN", "collections", "musicvideo"),)),
        ('emby_downloaded_movies', f"EMBY: {utils.Translate(33629)}", 'DefaultMovies.png', "movies", (("path", "contains", "EMBY-offline-content"),), ("ascending", "sorttitle"), False, False),
        ('emby_downloaded_series', f"EMBY: {utils.Translate(33662)}", 'DefaultAddonVideo.png', "tvshows", (("path", "contains", "EMBY-offline-content"),), ("ascending", "sorttitle"), False, False),
        ('emby_downloaded_episodes', f"EMBY: {utils.Translate(33630)}", 'DefaultAddonVideo.png', "episodes", (("path", "contains", "EMBY-offline-content"),), ("ascending", "sorttitle"), False, False),
        ('emby_downloaded_musicvideos', f"EMBY: {utils.Translate(33631)}", 'DefaultMusicVideos.png', "musicvideos", (("path", "contains", "EMBY-offline-content"),), ("ascending", "sorttitle"), False, False)
    ]
}
DynamicNodes = {
    'tvshows': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Series", False),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png', "Series", False),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode", False),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series", False),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode", False),
        ('Favorite', utils.Translate(33558), 'DefaultFavourites.png', "tvshows", False),
        ('Favorite', utils.Translate(33346), 'DefaultFavourites.png', "Series", False),
        ('Favorite', utils.Translate(30182), 'DefaultFavourites.png', "Episode", False),
        ('Tag', utils.Translate(33353), 'DefaultTags.png', "tvshows", True),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode", False),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Series", True),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "tvshows", True),
        ('Upcoming', utils.Translate(33348), 'DefaultSets.png', "Episode", False),
        ('NextUp', utils.Translate(30179), 'DefaultSets.png', "Episode", False),
        ('Resume', utils.Translate(33355), 'DefaultInProgressShows.png', "Episode", False),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Series", False),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Episode", False)
    ],
    'mixedvideo': [
        ('Letter', utils.Translate(33621), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Movie", False),
        ('Letter', utils.Translate(33622), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Series", False),
        ('Letter', utils.Translate(33617), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Video", False),
        ('Letter', utils.Translate(33620), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "VideoMusicArtist", False),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie", False),
        ('Video', utils.Translate(33367), 'DefaultAddonVideo.png', "Video", False),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie", False),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo", False),
        ('Recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png', "Series", False),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode", False),
        ('Unwatched', utils.Translate(30189), 'OverlayUnwatched.png', "Movie", False),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "MusicVideo", False),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series", False),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode", False),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie", False),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo", False),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode", False),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Series", True),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Movie", True),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "MusicVideo", True),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Series", False),
        ('Random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Movie", False),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Episode", False),
        ('Random', utils.Translate(33365), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "MusicVideo", False)
    ],
    'movies': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Movie", False),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie", False),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie", False),
        ('Unwatched', utils.Translate(30189), 'OverlayUnwatched.png', "Movie", False),
        ('BoxSet', utils.Translate(20434), 'DefaultSets.png', "movies", True),
        ('Recommendations', utils.Translate(33613), 'DefaultInProgressShows.png', "Movie", False),
        ('Tag', utils.Translate(33356), 'DefaultTags.png', "movies", True),
        ('Favorite', utils.Translate(33558), 'DefaultFavourites.png', "movies", False),
        ('Favorite', utils.Translate(33614), 'DefaultFavourites.png', "Movie", False),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Movie", True),
        ('Random', utils.Translate(30229), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Movie", False)
    ],
    'channels': [
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True)
    ],
    'boxsets': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "BoxSet", False),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet", True),
        ('Favorite', utils.Translate(33615), 'DefaultFavourites.png', "BoxSet", False),
    ],
    'livetv': [
        ('TvChannel', utils.Translate(33593), 'DefaultAddonPVRClient.png', 'TvChannel', False)
    ],
    'musicvideos': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "VideoMusicArtist", False),
        ('MusicVideo', utils.Translate(33363), 'DefaultMusicVideos.png', "MusicVideo", False),
        ('VideoMusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "VideoMusicArtist", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo", False),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo", False),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "MusicVideo", False),
        ('Tag', utils.Translate(33364), 'DefaultTags.png', "musicvideos", True),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "musicvideos", True),
        ('Random', utils.Translate(33365), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "MusicVideo", False),
        ('Favorite', utils.Translate(33610), 'DefaultFavourites.png', "MusicVideo", False),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "musicvideos", False),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "MusicVideo", True)
    ],
    'homevideos': [
        ('Letter', utils.Translate(33616), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "PhotoAlbum", False),
        ('Letter', utils.Translate(33617), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "Video", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Video', utils.Translate(33367), 'DefaultAddonVideo.png', "Video", False),
        ('Photo', utils.Translate(33368), 'DefaultPicture.png', "Photo", False),
        ('PhotoAlbum', utils.Translate(33369), 'DefaultAddonPicture.png', "PhotoAlbum", True),
        ('Tag', utils.Translate(33370), 'DefaultTags.png', "PhotoAlbum", True),
        ('Tag', utils.Translate(33371), 'DefaultTags.png', "Photo", True),
        ('Tag', utils.Translate(33372), 'DefaultTags.png', "Video", True),
        ('Favorite', utils.Translate(33608), 'DefaultFavourites.png', "Video", False),
        ('Favorite', utils.Translate(33609), 'DefaultFavourites.png', "Photo", False),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet", True),
        ('Recentlyadded', utils.Translate(33373), 'DefaultRecentlyAddedMovies.png', "Photo", False),
        ('Recentlyadded', utils.Translate(33566), 'DefaultRecentlyAddedMovies.png', "PhotoAlbum", False),
        ('Recentlyadded', utils.Translate(33375), 'DefaultRecentlyAddedMovies.png', "Video", False)
    ],
    'audiobooks': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "MusicArtist", False),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Audio', utils.Translate(33377), 'DefaultFolder.png', "Audio", False),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio", False),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio", False),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio", False),
        ('Random', utils.Translate(33378), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Audio", False),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "Audio", True),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio", False)
    ],
    'podcasts': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "MusicArtist", False),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Audio', utils.Translate(33382), 'DefaultFolder.png', "Audio", False),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio", False),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio", False),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio", False),
        ('Random', utils.Translate(33381), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Audio", False),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "Audio", True),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio", False)
    ],
    'music': [
        ('Letter', utils.Translate(33611), 'special://home/addons/plugin.service.emby-next-gen/resources/letter.png', "MusicArtist", False),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist", False),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder", True),
        ('Random', utils.Translate(33380), 'special://home/addons/plugin.service.emby-next-gen/resources/random.png', "Audio", False),
        ('MusicGenre', utils.Translate(135), 'DefaultMusicGenres.png', "Audio", True),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio", False),
        ('Favorite', utils.Translate(33623), 'DefaultFavourites.png', "Audio", False),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "music", False),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio", False)
    ],
    'rootaudio': [
        ('Playlists', utils.Translate(33376), 'DefaultMusicPlaylists.png', "PlaylistsAudio", True),
        ('Favorite', utils.Translate(33625), 'DefaultFavourites.png', "music", False),
        ('Search', utils.Translate(33626), 'DefaultAddonsSearch.png', "All", False)
    ],
    'rootvideo': [
        ('Playlists', utils.Translate(33376), 'DefaultVideoPlaylists.png', "PlaylistsVideo", True),
        ('Favorite', utils.Translate(33624), 'DefaultFavourites.png', "Person", False),
        ('Favorite', utils.Translate(33608), 'DefaultFavourites.png', "videos", False),
        ('Search', utils.Translate(33626), 'DefaultAddonsSearch.png', "All", False)
    ]
}

class Views:
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.ViewItems = {}
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}
        self.PictureNodes = {}
        self.update_nodes()

    def update_nodes(self):
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}
        self.PictureNodes = {}

        for library_id, Data in list(self.ViewItems.items()):
            view = {'LibraryId': library_id, 'Name': Data[0], 'Tag': Data[0], 'ContentType': Data[1], "Icon": Data[2], 'FilteredName': utils.valid_Filename(Data[0]), "ServerId": self.EmbyServer.ServerData["ServerId"]}

            for Dynamic in (True, False):
                if view['ContentType'] in ("books", "games", "photos", "playlists"):
                    continue

                if Dynamic or f"'{view['LibraryId']}'" in str(self.EmbyServer.library.LibrarySynced):
                    if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                        view['Tag'] = f"EmbyLibraryId-{library_id}"
                        add_xpsplaylist(view)
                        self.add_nodes(view, Dynamic)
                    elif view['ContentType'] == 'mixed':
                        if Dynamic:
                            viewMod = view.copy()
                            viewMod['ContentType'] = 'music'
                            add_xpsplaylist(viewMod)
                            self.add_nodes(viewMod, Dynamic)
                            viewMod['ContentType'] = 'mixedvideo'
                            add_xpsplaylist(viewMod)
                            self.add_nodes(viewMod, Dynamic)
                        else:
                            viewMod = view.copy()

                            for media in ('movies', 'tvshows', 'music'):
                                if media in ('movies', 'tvshows'):
                                    viewMod['Name'] = f"{view['Name']} ({media})"
                                else:
                                    viewMod['Name'] = view['Name']

                                viewMod['ContentType'] = media

                                if media == 'music':
                                    viewMod['Tag'] = f"EmbyLibraryId-{library_id}"

                                add_xpsplaylist(viewMod)
                                self.add_nodes(viewMod, Dynamic)
                    elif not Dynamic and view['ContentType'] == 'homevideos':
                        viewMod = view.copy()
                        viewMod['ContentType'] = "movies"
                        add_xpsplaylist(viewMod)
                        self.add_nodes(viewMod, Dynamic)
                    else:
                        add_xpsplaylist(view)
                        self.add_nodes(view, Dynamic)

        self.add_nodes({'ContentType': "rootaudio"}, False)
        self.add_nodes({'ContentType': "rootvideo"}, False)
        self.add_nodes({'ContentType': "rootaudio"}, True)
        self.add_nodes({'ContentType': "rootvideo"}, True)

    def update_views(self):
        Data = self.EmbyServer.API.get_views()

        if 'Items' in Data:
            Libraries = Data['Items']
        else:
            return

        for library in Libraries:
            iconpath = ""

            if library['Type'] == 'Channel' and library['Name'].lower() == "podcasts":
                library['ContentType'] = "podcasts"
            elif library['Type'] == 'Channel':
                library['ContentType'] = "channels"
            else:
                library['ContentType'] = library.get('CollectionType', "mixed")

            if "Primary" in library["ImageTags"]:
                # Cache artwork
                BinaryData, _, FileExtension = self.EmbyServer.API.get_Image_Binary(library['Id'], "Primary", 0, library["ImageTags"]["Primary"])

                if BinaryData:
                    Filename = utils.valid_Filename(f"{self.EmbyServer.ServerData['ServerName']}_{library['Id']}.{FileExtension}")
                    iconpath = f"{utils.FolderEmbyTemp}{Filename}"
                    utils.delFile(iconpath)
                    utils.writeFileBinary(iconpath, BinaryData)

            self.ViewItems[library['Id']] = [utils.decode_XML(library['Name']), library['ContentType'], iconpath]

    # Remove playlist based on LibraryId
    def delete_playlist_by_id(self, LibraryId):
        if LibraryId in self.ViewItems:
            if self.ViewItems[LibraryId][1] in ('music', 'audiobooks', 'podcasts'):
                path = 'special://profile/playlists/music/'
            else:
                path = 'special://profile/playlists/video/'

            PlaylistPath = f"{path}emby_{self.ViewItems[LibraryId][0].replace(' ', '_')}.xsp"
            utils.delFolder(PlaylistPath)
        else:
            xbmc.log(f"EMBY.emby.views: Delete playlist, library not found: {LibraryId}", 1) # LOGINFO

    def delete_node_by_id(self, LibraryId, RemoveServer=False):
        if LibraryId in self.ViewItems:
            ContentTypes = []

            if self.ViewItems[LibraryId][1] == "mixed":
                ContentTypes.append('movies')
                ContentTypes.append('tvshows')
                ContentTypes.append('music')
                ContentTypes.append('mixed')
            else:
                ContentTypes.append(self.ViewItems[LibraryId][1])

            ContentTypes.append('podcasts')
            ContentTypes.append('channels')
            ContentTypes.append('movies')

            for ContentType in ContentTypes:
                if ContentType in ('music', 'audiobooks', 'podcasts'):
                    path = "special://profile/library/music/"
                else:
                    path = "special://profile/library/video/"

                NodePath = f"{path}emby_{ContentType}_{utils.valid_Filename(self.ViewItems[LibraryId][0])}/"
                utils.delFolder(NodePath)

                if RemoveServer:
                    NodePath = f"{path}emby_dynamic_{ContentType}_{utils.valid_Filename(self.ViewItems[LibraryId][0])}/"
                    utils.delFolder(NodePath)
        else:
            xbmc.log(f"EMBY.emby.views: Delete node, library not found: {LibraryId}", 1) # LOGINFO

    # Create or update the video node file
    def add_nodes(self, view, Dynamic):
        if 'Icon' not in view or not view['Icon']:
            if view['ContentType'] == 'tvshows':
                view['Icon'] = 'DefaultTVShows.png'
            elif view['ContentType'] in ('movies', 'homevideos'):
                view['Icon'] = 'DefaultMovies.png'
            elif view['ContentType'] == 'musicvideos':
                view['Icon'] = 'DefaultMusicVideos.png'
            elif view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                view['Icon'] = 'DefaultMusicVideos.png'
            else:
                view['Icon'] = "special://home/addons/plugin.service.emby-next-gen/resources/icon.png"

        if view['ContentType'] not in ("rootaudio", "rootvideo"):
            if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                if Dynamic:
                    folder = f"special://profile/library/music/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/"
                else:
                    folder = f"special://profile/library/music/emby_{view['ContentType']}_{view['FilteredName']}/"
            else:
                if Dynamic:
                    folder = f"special://profile/library/video/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/"
                else:
                    folder = f"special://profile/library/video/emby_{view['ContentType']}_{view['FilteredName']}/"

            utils.mkDir(folder)
            FilePath = f"{folder}index.xml"

            if not utils.checkFileExists(FilePath):
                Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                Data += '<node order="0">\n'

                if Dynamic:
                    Data += f'    <label>EMBY DYNAMIC: {utils.encode_XML(view["Name"])} ({view["ContentType"]})</label>\n'
                else:
                    Data += f'    <label>EMBY: {utils.encode_XML(view["Name"])} ({view["ContentType"]})</label>\n'

                Data += f'    <icon>{utils.encode_XML(view["Icon"])}</icon>\n'
                Data += '</node>'
                utils.writeFileBinary(FilePath, Data.encode("utf-8"))
        elif view['ContentType'] == "rootvideo":
            folder = "special://profile/library/video/"
            utils.mkDir(folder)
        elif view['ContentType'] == "rootaudio":
            folder = "special://profile/library/music/"
            utils.mkDir(folder)

        # Dynamic nodes
        if Dynamic:
            if view['ContentType'] not in ("rootaudio", "rootvideo"):
                if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                    self.Nodes['NodesDynamic'].append({'title': view['Name'], 'path': f"library://music/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']})
                elif view['ContentType'] == "homevideos":
                    self.Nodes['NodesDynamic'].append({'title': view['Name'], 'path': f"library://video/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']})
                    self.Nodes['NodesDynamic'].append({'title': view['Name'], 'path': f"{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']}) # pictures
                else:
                    self.Nodes['NodesDynamic'].append({'title': view['Name'], 'path': f"library://video/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']})

                NodeIndex = 0

                for node in DynamicNodes[view['ContentType']]:
                    NodeIndex += 1

                    if node[0] == "Letter":
                        FolderPath = f"{folder}letter_{node[3].lower()}/"
                        utils.mkDir(FolderPath)
                        FilePath = f"{FolderPath}index.xml"

                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += '<node order="0">\n'
                            Data += f'    <label>{utils.encode_XML(node[1])}</label>\n'
                            Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                        # Alphabetically
                        for Letter in ("0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"):
                            FilePath = f"{FolderPath}{Letter}.xml"
                            NodeIndex += 1

                            if not utils.checkFileExists(FilePath):
                                Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                                Data += f'<node order="{NodeIndex}" type="folder">\n'
                                Data += f'    <label>{Letter}</label>\n'
                                Data += f'    <path>plugin://plugin.service.emby-next-gen/?mode=browse&amp;id={Letter}&amp;parentid={view["LibraryId"]}&amp;libraryid={view["LibraryId"]}&amp;content={node[3]}&amp;server={view["ServerId"]}&amp;query=Letter</path>\n'
                                Data += '</node>'
                                utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                        continue

                    # Pictures
                    if node[3] in ("Photo", "PhotoAlbum"):
                        if f"{view['ContentType']}_{view['FilteredName']}/" not in self.PictureNodes:
                            self.PictureNodes[f"{view['ContentType']}_{view['FilteredName']}/"] = ()

                        self.PictureNodes[f"{view['ContentType']}_{view['FilteredName']}/"] += ((node[1], FilePath, f'plugin://plugin.service.emby-next-gen/?mode=browse&id={view["LibraryId"]}&parentid={view["LibraryId"]}&libraryid={view["LibraryId"]}&content={node[3]}&server={view["ServerId"]}&query={node[0]}', node[2]),)

                        if node[3] == "Photo":
                            continue
                    elif node[3] == "Folder" and view['ContentType'] == "homevideos":
                        if f"{view['ContentType']}_{view['FilteredName']}/" not in self.PictureNodes:
                            self.PictureNodes[f"{view['ContentType']}_{view['FilteredName']}/"] = ()

                        self.PictureNodes[f"{view['ContentType']}_{view['FilteredName']}/"] += ((node[1], FilePath, f'plugin://plugin.service.emby-next-gen/?mode=browse&id={view["LibraryId"]}&parentid={view["LibraryId"]}&libraryid={view["LibraryId"]}&content={node[3]}&server={view["ServerId"]}&query={node[0]}', node[2]),)

                    FilePath = f"{folder}{node[0].lower()}_{node[3].lower()}.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <label>{utils.encode_XML(node[1])}</label>\n'
                        Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'
                        Data += f'    <path>plugin://plugin.service.emby-next-gen/?mode=browse&amp;id={view["LibraryId"]}&amp;parentid={view["LibraryId"]}&amp;libraryid={view["LibraryId"]}&amp;content={node[3]}&amp;server={view["ServerId"]}&amp;query={node[0]}</path>\n'

                        if node[4]:
                            Data += '    <group/>\n'

                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
            else: # Dynamic root nodes
                for NodeIndex, node in enumerate(DynamicNodes[view['ContentType']], 1):
                    if view['ContentType'] == "rootvideo":
                        NodePath = f"library://video/emby_dynamic_{node[0].lower()}_{node[3].lower()}_{self.EmbyServer.ServerData['ServerId']}.xml"
                        FilePath = f"special://profile/library/video/emby_dynamic_{node[0].lower()}_{node[3].lower()}_{self.EmbyServer.ServerData['ServerId']}.xml"
                    elif view['ContentType'] == "rootaudio":
                        NodePath = f"library://music/emby_dynamic_{node[0].lower()}_{node[3].lower()}_{self.EmbyServer.ServerData['ServerId']}.xml"
                        FilePath = f"special://profile/library/music/emby_dynamic_{node[0].lower()}_{node[3].lower()}_{self.EmbyServer.ServerData['ServerId']}.xml"
                    else:
                        NodePath = f"library://music/emby_dynamic_{node[0].lower()}_{node[3].lower()}.xml"
                        FilePath = f"special://profile/library/music/emby_dynamic_{node[0].lower()}_{node[3].lower()}.xml"

                    if not utils.checkFileExists(FilePath) and self.EmbyServer.ServerData["ServerId"]:
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <label>EMBY DYNAMIC: {utils.encode_XML(node[1])}</label>\n'
                        Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'

                        if node[0] == "Search":
                            Data += f'    <path>plugin://plugin.service.emby-next-gen/?mode=search&amp;server={self.EmbyServer.ServerData["ServerId"]}</path>\n'
                        else:
                            Data += f'    <path>plugin://plugin.service.emby-next-gen/?mode=browse&amp;id=0&amp;parentid=0&amp;libraryid=0&amp;content={node[3]}&amp;server={self.EmbyServer.ServerData["ServerId"]}&amp;query={node[0]}</path>\n'

                        if node[4]:
                            Data += '    <group/>\n'

                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                    self.Nodes['NodesDynamic'].append({'title': node[1], 'path': NodePath, 'icon': node[2]})
        else: # Synced nodes
            if view['ContentType'] not in ("rootaudio", "rootvideo"):
                if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                    self.Nodes['NodesSynced'].append({'title': view['Name'], 'path': f"library://music/emby_{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']})
                else:
                    self.Nodes['NodesSynced'].append({'title': view['Name'], 'path': f"library://video/emby_{view['ContentType']}_{view['FilteredName']}/", 'icon': view['Icon']})

            NodeIndex = 0

            for node in SyncNodes[view['ContentType']]:
                # Node: [filename, label, icon, content, [[rule1, Filter, Operator], [rule1, Filter, Operator], ...], [direction, order], useLimit, group, Subfolder]
                NodeIndex += 1

                if view['ContentType'] in ("rootaudio", "rootvideo"):
                    if not self.EmbyServer.ServerData['ServerId']:
                        continue

                    if view['ContentType'] == "rootvideo":
                        NodeData = {'title': node[1].replace("EMBY: ", ""), 'path': f"library://video/{node[0]}_{self.EmbyServer.ServerData['ServerId']}.xml", 'icon': node[2]}
                    else:
                        NodeData = {'title': node[1].replace("EMBY: ", ""), 'path': f"library://music/{node[0]}_{self.EmbyServer.ServerData['ServerId']}.xml", 'icon': node[2]}

                    NodeAdd = True

                    if node[0] in ('emby_collections_movies', 'emby_collections_tvshows', 'emby_collections_musicvideos'):
                        NodeAdd = utils.BoxSetsToTags

                    if NodeAdd:
                        self.Nodes['NodesSynced'].append(NodeData)
                    else:
                        if NodeData in self.Nodes['NodesSynced']:
                            del self.Nodes['NodesSynced'][self.Nodes['NodesSynced'].index(NodeData)]

                if len(node) == 9:
                    FolderPath = f"{folder}{node[8][0]}/"

                    if node[8][1] == "DBMUSICGENRE":
                        utils.delFolder(FolderPath)
                        utils.mkDir(FolderPath)
                        musicdb = dbio.DBOpenRO("music", "node_songsbygenres")
                        Genres = musicdb.get_genre(view['LibraryId'])
                        dbio.DBCloseRO("music", "node_songsbygenres")

                        for Genre in Genres:
                            SubNode = list(node)
                            SubNode[0] = utils.valid_Filename(Genre)
                            SubNode[1] = utils.encode_XML(Genre)
                            SubNode[4] = list(SubNode[4])
                            SubNode[4][1] += (Genre,)
                            self.set_synced_node(FolderPath, view, SubNode, NodeIndex, 10)
                            NodeIndex += 1
                    elif node[8][1] == "LETTER":
                        utils.mkDir(FolderPath)

                        for Letter in ("0-9", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"):
                            SubNode = list(node)
                            SubNode[0] = Letter
                            SubNode[1] = Letter
                            SubNode[4] = list(SubNode[4])

                            if Letter == "0-9":
                                SubNode[4][1] += (("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "&amp;", "Ä", "Ö", "Ü", "!", "(", ")", "@", "#", "$", "^", "*", "-", "=", "+", "{", "}", "[", "]", "?", ":", ";", ",", ".", "~", "&lt;", "&gt;", "&quot;", "&apos;"),)
                            else:
                                SubNode[4][1] += (Letter,)

                            self.set_synced_node(FolderPath, view, SubNode, NodeIndex, 1)
                            NodeIndex += 1

                    FilePath = f"{FolderPath}index.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += '<node order="0">\n'
                        Data += f'    <label>{utils.encode_XML(node[1])}</label>\n'
                        Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                else:
                    self.set_synced_node(folder, view, node, NodeIndex, 1)

    def set_synced_node(self, Folder, view, node, NodeIndex, LimitFactor):
        Label = node[1]

        if view['ContentType'].startswith("root"):
            FilePath = f"{Folder}{node[0]}_{self.EmbyServer.ServerData['ServerId']}.xml"
        else:
            FilePath = f"{Folder}{node[0]}.xml"

        if Label == "LIBRARYNAME":
            Label = utils.encode_XML(view["Name"])

        if not utils.checkFileExists(FilePath):
            if not self.EmbyServer.ServerData["ServerId"]:
                return

            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'

            if node[4][0][0] == "PLUGIN":
                Data += f'<node order="{NodeIndex}" type="folder">\n'
                Data += f'    <label>{utils.encode_XML(Label)}</label>\n'
                Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'
                Data += f'    <path>plugin://plugin.service.emby-next-gen/?mode={node[4][0][1]}&amp;mediatype={node[4][0][2]}&amp;libraryname={quote(view.get("Name", "unknown"))}&amp;server={self.EmbyServer.ServerData["ServerId"]}</path>\n'

                if len(node) >= 8 and node[7]:
                    Data += '    <group/>\n'
            else:
                Data += f'<node order="{NodeIndex}" type="filter">\n'
                Data += f'    <label>{utils.encode_XML(Label)}</label>\n'
                Data += f'    <icon>{utils.encode_XML(node[2])}</icon>\n'
                Data += f'    <content>{node[3]}</content>\n'

                if len(node[4]) > 1:
                    Data += '    <match>all</match>\n'

                for Rule in node[4]:
                    if len(Rule) == 2:
                        Data += f'    <rule field="{Rule[0]}" operator="{Rule[1]}"/>\n'
                    else:
                        if isinstance(Rule[2], tuple):
                            Data += f'    <rule field="{Rule[0]}" operator="{Rule[1]}">\n'

                            for Value in Rule[2]:
                                Data += f'        <value>{Value}</value>\n'

                            Data += '    </rule>\n'
                        else:
                            Tag = Rule[2]

                            if Tag == "LIBRARYTAG":
                                Tag = utils.encode_XML(view["Tag"])

                            Data += f'    <rule field="{Rule[0]}" operator="{Rule[1]}">{Tag}</rule>\n'

                if node[5]:
                    if len(node[5]) > 1:
                        Data += f'    <order direction="{node[5][0]}">{node[5][1]}</order>\n'
                    else:
                        Data += f'    <order>{node[5][0]}</order>\n'

                if node[6]:
                    Data += f'    <limit>{utils.maxnodeitems * LimitFactor}</limit>\n'

                if node[7]:
                    Data += f'    <group>{node[7]}</group>\n'

            Data += '</node>'
            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

# Create or update the xsp file
def add_xpsplaylist(view):
    if not utils.xspplaylists:
        return

    if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
        path = 'special://profile/playlists/music/'
    else:
        path = 'special://profile/playlists/video/'

    utils.mkDir(path)
    FilePath = f"{path}emby_{view['ContentType']}_{view['FilteredName']}.xsp"

    if not utils.checkFileExists(FilePath):
        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        Data += f'<smartplaylist type="{view["ContentType"]}">\n'
        Data += f'    <name>{view["Name"]}</name>\n'
        Data += '    <match>all</match>\n'
        Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
        Data += '</smartplaylist>'
        utils.writeFileBinary(FilePath, Data.encode("utf-8"))

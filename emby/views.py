from urllib.parse import urlencode, quote
import xbmc
from helper import utils
from database import dbio

SyncNodes = {
    'tvshows': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultTVShows.png'),
        ('recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
        ('recentlyaddedepisodes', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png'),
        ('inprogress', utils.Translate(30171), 'DefaultInProgressShows.png'),
        ('inprogressepisodes', utils.Translate(30178), 'DefaultInProgressShows.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('collections', "Collections", 'DefaultTags.png'),
        ('favortites', "Favorites", 'DefaultTags.png'),
        ('unwatched', utils.Translate(33345), 'OverlayUnwatched.png'),
        ('unwatchedepisodes', utils.Translate(33344), 'OverlayUnwatched.png'),
        ('studios', utils.Translate(33249), 'DefaultStudios.png'),
        ('recentlyplayed', utils.Translate(33347), 'DefaultMusicRecentlyPlayed.png'),
        ('recentlyplayedepisodes', utils.Translate(33351), 'DefaultMusicRecentlyPlayed.png'),
        ('nextepisodes', utils.Translate(30179), 'DefaultInProgressShows.png')
    ],
    'movies': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMovies.png'),
        ('recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
        ('inprogress', utils.Translate(30177), 'DefaultInProgressShows.png'),
        ('unwatched', utils.Translate(30189), 'OverlayUnwatched.png'),
        ('sets', utils.Translate(30185), 'DefaultSets.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', utils.Translate(33218), 'DefaultYear.png'),
        ('actors', utils.Translate(33219), 'DefaultActor.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('collections', "Collections", 'DefaultSets.png'),
        ('favortites', "Favorites", 'DefaultTags.png'),
        ('studios', utils.Translate(33249), 'DefaultStudios.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('directors', utils.Translate(33352), 'DefaultDirector.png'),
        ('countries', utils.Translate(33358), 'DefaultCountry.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'musicvideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('collections', "Collections", 'DefaultSets.png'),
        ('favortites', "Favorites", 'DefaultTags.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'homevideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultGenre.png'),
        ('inprogress', utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', utils.Translate(30258), 'OverlayUnwatched.png'),
        ('tags', utils.Translate(33220), 'DefaultTags.png'),
        ('collections', "Collections", 'DefaultSets.png'),
        ('favortites', "Favorites", 'DefaultTags.png'),
        ('recentlyplayed', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', utils.Translate(33359), 'DefaultIconInfo.png'),
        ('resolutionsd', utils.Translate(33360), 'DefaultIconInfo.png'),
        ('resolution4k', utils.Translate(33361), 'DefaultIconInfo.png')
    ],
    'music': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('songsbygenres', utils.Translate(33435), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('composers', utils.Translate(33426), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyadded', utils.Translate(33390), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('random', utils.Translate(33392), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
    ],
    'audiobooks': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyadded', utils.Translate(33389), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('random', utils.Translate(33393), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ],
    'podcasts': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', utils.Translate(33248), 'DefaultMusicGenres.png'),
        ('artists', utils.Translate(33343), 'DefaultMusicArtists.png'),
        ('albums', utils.Translate(33362), 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', utils.Translate(33388), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyadded', utils.Translate(33395), 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayedmusic', utils.Translate(33350), 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', utils.Translate(33391), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('random', utils.Translate(33394), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ],
    'playlists': [],
    'root': [
        ('inprogressmixed', "In progress (Mixed content)", 'DefaultInProgressShows.png'),
        ('continuewatching', "Continue watching (Mixed content)", 'DefaultInProgressShows.png'),
        ('favortitemovies', utils.Translate(30180), 'DefaultFavourites.png'),
        ('favortiteseries', utils.Translate(30181), 'DefaultFavourites.png'),
        ('favortiteepisodes', utils.Translate(30182), 'DefaultFavourites.png'),
        ('favortiteseasons', utils.Translate(33576), 'DefaultFavourites.png'),
        ('favortitemusicvideos', utils.Translate(33385), 'DefaultFavourites.png'),
        ('collectionmovies', utils.Translate(33555), 'DefaultTags.png'),
        ('collectionseries', utils.Translate(33556), 'DefaultTags.png'),
        ('collectionmmusicvideos', utils.Translate(33557), 'DefaultTags.png'),
        ('downloadedmovies', "Downloaded movies", 'DefaultMovies.png'),
        ('downloadedepisodes', "Downloaded episodes", 'DefaultAddonVideo.png'),
        ('downloadedmusicvideos', "Downloaded musicvideos", 'DefaultMusicVideos.png')
    ]
}
DynamicNodes = {
    'tvshows': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Series"),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png', "Series"),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode"),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series"),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode"),
        ('Favorite', "Favorites", 'DefaultFavourites.png', "tvshows"),
        ('Favorite', utils.Translate(33346), 'DefaultFavourites.png', "Series"),
        ('Favorite', utils.Translate(30182), 'DefaultFavourites.png', "Episode"),
        ('Tag', utils.Translate(33353), 'DefaultTags.png', "tvshows"),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Series"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "tvshows"),
        ('Upcoming', utils.Translate(33348), 'DefaultSets.png', "Episode"),
        ('NextUp', utils.Translate(30179), 'DefaultSets.png', "Episode"),
        ('Resume', utils.Translate(33355), 'DefaultInProgressShows.png', "Episode"),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Series"),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Episode")
    ],
    'mixed': [
        ('Letter', "A-Z movies", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Movie"),
        ('Letter', "A-Z series", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Series"),
        ('Letter', "A-Z videos", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Video"),
        ('Letter', "A-Z musicvideoartists", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "VideoMusicArtist"),
        ('Letter', "A-Z musicartists", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie"),
        ('Video', utils.Translate(33367), 'DefaultAddonVideo.png', "Video"),
        ('Series', utils.Translate(33349), 'DefaultTVShows.png', "Series"),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist"),
        ('Audio', utils.Translate(33377), 'DefaultMusicSongs.png', "Audio"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png', "Episode"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Unwatched', utils.Translate(33345), 'OverlayUnwatched.png', "Series"),
        ('Unwatched', utils.Translate(33344), 'OverlayUnwatched.png', "Episode"),
        ('Inprogress', utils.Translate(30178), 'DefaultInProgressShows.png', "Episode"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "All"),
        ('Random', utils.Translate(33339), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Series"),
        ('Random', utils.Translate(33338), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Episode"),
        ('Random', utils.Translate(33380), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio")
    ],
    'movies': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Movie"),
        ('Movie', utils.Translate(30302), 'DefaultMovies.png', "Movie"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30174), 'DefaultRecentlyAddedMovies.png', "Movie"),
        ('Inprogress', utils.Translate(30177), 'DefaultInProgressShows.png', "Movie"),
        ('Unwatched', utils.Translate(30189), 'OverlayUnwatched.png', "Movie"),
        ('BoxSet', utils.Translate(20434), 'DefaultSets.png', "movies"),
        ('Recommendations', "Recommendations", 'DefaultInProgressShows.png', "Movie"),
        ('Tag', utils.Translate(33356), 'DefaultTags.png', "movies"),
        ('Favorite', "Favorites", 'DefaultFavourites.png', "movies"),
        ('Favorite', "Favorite movies", 'DefaultFavourites.png', "Movie"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Movie"),
        ('Random', utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Movie")
    ],
    'channels': [
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder")
    ],
    'boxsets': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "BoxSet"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet"),
        ('Favorite', "Favorite boxsets", 'DefaultFavourites.png', "BoxSet"),
    ],
    'livetv': [
        ('TvChannel', "LiveTV", 'DefaultAddonPVRClient.png', 'TvChannel')
    ],
    'musicvideos': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "VideoMusicArtist"),
        ('MusicVideo', utils.Translate(33363), 'DefaultMusicVideos.png', "MusicVideo"),
        ('VideoMusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "VideoMusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Recentlyadded', utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png', "MusicVideo"),
        ('Inprogress', utils.Translate(30257), 'DefaultInProgressShows.png', "MusicVideo"),
        ('Unwatched', utils.Translate(30258), 'OverlayUnwatched.png', "MusicVideo"),
        ('Tag', utils.Translate(33364), 'DefaultTags.png', "musicvideos"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "musicvideos"),
        ('Random', utils.Translate(33365), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "MusicVideo"),
        ('Favorite', "Favorite musicvideos", 'DefaultFavourites.png', "MusicVideo"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "musicvideos"),
        ('MusicGenre', utils.Translate(135), 'DefaultGenre.png', "MusicVideo")
    ],
    'homevideos': [
        ('Letter', "A-Z photoalbum", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "PhotoAlbum"),
        ('Letter', "A-Z videos", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Video"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Video', utils.Translate(33367), 'DefaultAddonVideo.png', "Video"),
        ('Photo', utils.Translate(33368), 'DefaultPicture.png', "Photo"),
        ('PhotoAlbum', utils.Translate(33369), 'DefaultAddonPicture.png', "PhotoAlbum"),
        ('Tag', utils.Translate(33370), 'DefaultTags.png', "PhotoAlbum"),
        ('Tag', utils.Translate(33371), 'DefaultTags.png', "Photo"),
        ('Tag', utils.Translate(33372), 'DefaultTags.png', "Video"),
        ('BoxSet', utils.Translate(30185), 'DefaultSets.png', "BoxSet"),
        ('Recentlyadded', utils.Translate(33373), 'DefaultRecentlyAddedMovies.png', "Photo"),
        ('Recentlyadded', utils.Translate(33566), 'DefaultRecentlyAddedMovies.png', "PhotoAlbum"),
        ('Recentlyadded', utils.Translate(33375), 'DefaultRecentlyAddedMovies.png', "Video")
    ],
    'playlists': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "Playlist"),
        ('Playlists', utils.Translate(33376), 'DefaultPlaylist.png', "Playlist")
    ],
    'audiobooks': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Audio', utils.Translate(33377), 'DefaultFolder.png', "Audio"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio"),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio"),
        ('Random', utils.Translate(33378), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio")
    ],
    'podcasts': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Audio', utils.Translate(33382), 'DefaultFolder.png', "Audio"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio"),
        ('Inprogress', utils.Translate(33169), 'DefaultInProgressShows.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "Audio"),
        ('Random', utils.Translate(33381), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('Genre', utils.Translate(135), 'DefaultGenre.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio")
    ],
    'music': [
        ('Letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png', "MusicArtist"),
        ('MusicArtist', utils.Translate(33343), 'DefaultMusicArtists.png', "MusicArtist"),
        ('Folder', utils.Translate(33335), 'DefaultFolder.png', "Folder"),
        ('Random', utils.Translate(33380), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png', "Audio"),
        ('MusicGenre', utils.Translate(135), 'DefaultMusicGenres.png', "Audio"),
        ('Unwatched', utils.Translate(33379), 'OverlayUnwatched.png', "Audio"),
        ('Favorite', "Favorite songs", 'DefaultFavourites.png', "Audio"),
        ('Favorite', utils.Translate(33168), 'DefaultFavourites.png', "music"),
        ('Recentlyadded', utils.Translate(33167), 'DefaultRecentlyAddedMovies.png', "Audio")
    ],
    'root': [
        ('Favorite', "Favorite actors", 'DefaultFavourites.png', "Person"),
        ('Favorite', "Favorite videos", 'DefaultFavourites.png', "videos"),
        ('Favorite', "Favorite audio", 'DefaultFavourites.png', "music"),
        ('Search', "Search", 'DefaultAddonsSearch.png', "All"),
    ]
}
EmbyContentTypeMapping = {"movies": "Movie", "tvshows": "Series", "musicvideos": "MusicVideo", "homevideos": "", "music": "Audio", "audiobooks": "Audio", "podcasts": "Audio", "playlists": "All", "boxsets": "All", "channels": "", "livetv": "", "mixed": ""}


class Views:
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.ViewItems = {}
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}

    def update_nodes(self):
        self.Nodes = {"NodesDynamic": [], "NodesSynced": []}

        for library_id, Data in list(self.ViewItems.items()):
            CleanName = utils.PathToFilenameReplaceSpecialCharecters(Data[0])
            view = {'LibraryId': library_id, 'Name': Data[0], 'Tag': Data[0], 'ContentType': Data[1], "Icon": Data[2], 'FilteredName': CleanName, 'KodiMediaType': "", "ServerId": self.EmbyServer.ServerData["ServerId"]}

            for Dynamic in (True, False):
                if view['ContentType'] in ("books", "games", "photos"):
                    continue

                if Dynamic or f"'{view['LibraryId']}'" in str(self.EmbyServer.library.Whitelist):
                    if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                        view['Tag'] = f"EmbyLibraryId-{library_id}"
                        view['KodiMediaType'] = "song"

                    if not Dynamic and view['ContentType'] == 'mixed':
                        ViewName = view['Name']

                        for media in ('movies', 'tvshows', 'music'):
                            view['ContentType'] = media
                            view['KodiMediaType'] = media[:-1]

                            if media == 'music':
                                view['Tag'] = f"EmbyLibraryId-{library_id}"

                            node_path, playlist_path = get_node_playlist_path(view['ContentType'])
                            view['Name'] = f"{ViewName} / {view['ContentType']}"
                            add_playlist(playlist_path, view)
                            add_nodes(node_path, view, Dynamic)
                            self.window_nodes(view, Dynamic)
                    elif not Dynamic and view['ContentType'] == 'homevideos':
                        view['ContentType'] = "movies"
                        view['KodiMediaType'] = "movie"
                        node_path, playlist_path = get_node_playlist_path(view['ContentType'])
                        add_playlist(playlist_path, view)
                        add_nodes(node_path, view, Dynamic)
                        self.window_nodes(view, Dynamic)
                    else:
                        if not view['KodiMediaType']:
                            view['KodiMediaType'] = view['ContentType'][:-1]

                        node_path, playlist_path = get_node_playlist_path(view['ContentType'])
                        add_playlist(playlist_path, view)
                        add_nodes(node_path, view, Dynamic)
                        self.window_nodes(view, Dynamic)

        for Dynamic in (True, False):
            self.add_nodes_root(Dynamic)

    # Dynamic nodes
    def window_nodes(self, view, Dynamic):
        if not view['Icon']:
            if view['ContentType'] == 'tvshows':
                view['Icon'] = 'DefaultTVShows.png'
            elif view['ContentType'] in ('movies', 'homevideos'):
                view['Icon'] = 'DefaultMovies.png'
            elif view['ContentType'] == 'musicvideos':
                view['Icon'] = 'DefaultMusicVideos.png'
            elif view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                view['Icon'] = 'DefaultMusicVideos.png'
            else:
                view['Icon'] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

        NodeData = {}

        if Dynamic:
            if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                path = f"library://music/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/"
            else:
                path = f"library://video/emby_dynamic_{view['ContentType']}_{view['FilteredName']}/"
        else:
            if view['ContentType'] in ('music', 'audiobooks', 'podcasts'):
                path = f"library://music/emby_{view['ContentType']}_{view['FilteredName']}/"
            else:
                path = f"library://video/emby_{view['ContentType']}_{view['FilteredName']}/"

        NodeData['title'] = view['Name']
        NodeData['path'] = path
        NodeData['icon'] = view['Icon']

        if Dynamic:
            self.Nodes['NodesDynamic'].append(NodeData)
        else:
            self.Nodes['NodesSynced'].append(NodeData)

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
                    Filename = utils.PathToFilenameReplaceSpecialCharecters(f"{self.EmbyServer.ServerData['ServerName']}_{library['Id']}.{FileExtension}")
                    iconpath = f"{utils.FolderEmbyTemp}{Filename}"
                    utils.delFile(iconpath)
                    utils.writeFileBinary(iconpath, BinaryData)

            self.ViewItems[library['Id']] = [library['Name'], library['ContentType'], iconpath]

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

                NodePath = f"{path}emby_{ContentType}_{utils.PathToFilenameReplaceSpecialCharecters(self.ViewItems[LibraryId][0])}/"
                utils.delFolder(NodePath)

                if RemoveServer:
                    NodePath = f"{path}emby_dynamic_{ContentType}_{utils.PathToFilenameReplaceSpecialCharecters(self.ViewItems[LibraryId][0])}/"
                    utils.delFolder(NodePath)
        else:
            xbmc.log(f"EMBY.emby.views: Delete node, library not found: {LibraryId}", 1) # LOGINFO

    # Create or update the video node file
    def add_nodes_root(self, Dynamic):
        if Dynamic:
            for NodeIndex, node in enumerate(DynamicNodes["root"], 1):
                NodePath = f"library://video/emby_dynamic_{node[0].lower()}_{node[3].lower()}.xml"
                FilePath = f"special://profile/library/video/emby_dynamic_{node[0].lower()}_{node[3].lower()}.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="folder">\n'
                    Data += f'    <label>EMBY DYNAMIC: {node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'

                    if node[0] == "Search":
                        Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=search&amp;server={self.EmbyServer.ServerData["ServerId"]}</path>\n'
                    else:
                        Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=browse&amp;id=0&amp;parentid=0&amp;libraryid=0&amp;content={node[3]}&amp;server={self.EmbyServer.ServerData["ServerId"]}&amp;query={node[0]}</path>\n'

                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                self.Nodes['NodesDynamic'].append({'title': node[1], 'path': NodePath, 'icon': node[2]})
        else:
            for NodeIndex, node in enumerate(SyncNodes["root"], 1):
                NodeAdd = True

                if node[0] == "inprogressmixed":
                    FilePath = "special://profile/library/video/emby_inprogress_mixed.xml"
                    NodePath = "library://video/emby_inprogress_mixed.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <path>plugin://plugin.video.emby-next-gen/?mode=inprogressmixed;</path>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "continuewatching":
                    FilePath = "special://profile/library/video/emby_continuewatching_mixed.xml"
                    NodePath = "library://video/emby_continuewatching_mixed.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <path>plugin://plugin.video.emby-next-gen/?mode=continuewatching;</path>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "favortitemovies":
                    FilePath = "special://profile/library/video/emby_Favorite_movies.xml"
                    NodePath = "library://video/emby_Favorite_movies.xml"

                    if not utils.checkFileExists(FilePath):
                        utils.mkDir("special://profile/library/video/")
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>movies</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="tag" operator="is">\n'
                        Data += '        <value>Movies (Favorites)</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "favortiteseries":
                    FilePath = "special://profile/library/video/emby_Favorite_tvshows.xml"
                    NodePath = "library://video/emby_Favorite_tvshows.xml"

                    if not utils.checkFileExists(FilePath):
                        utils.mkDir("special://profile/library/video/")
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>tvshows</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="tag" operator="is">\n'
                        Data += '        <value>TVShows (Favorites)</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "favortiteepisodes":
                    FilePath = "special://profile/library/video/emby_Favorite_episodes.xml"
                    NodePath = "library://video/emby_Favorite_episodes.xml"

                    if not utils.checkFileExists(FilePath):
                        utils.mkDir("special://profile/library/video/")
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += f'    <path>plugin://plugin.video.emby-next-gen/?{urlencode({"mode": "favepisodes"})}</path>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "favortiteseasons":
                    FilePath = "special://profile/library/video/emby_Favorite_seasons.xml"
                    NodePath = "library://video/emby_Favorite_seasons.xml"

                    if not utils.checkFileExists(FilePath):
                        utils.mkDir("special://profile/library/video/")
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="folder">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += f'    <path>plugin://plugin.video.emby-next-gen/?{urlencode({"mode": "favseasons"})}</path>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "favortitemusicvideos":
                    FilePath = "special://profile/library/video/emby_Favorite_musicvideos.xml"
                    NodePath = "library://video/emby_Favorite_musicvideos.xml"

                    if not utils.checkFileExists(FilePath):
                        utils.mkDir("special://profile/library/video/")
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>musicvideos</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="tag" operator="is">\n'
                        Data += '        <value>Musicvideos (Favorites)</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "collectionmovies":
                    FilePath = "special://profile/library/video/emby_Collection_movies.xml"
                    NodePath = "library://video/emby_Collection_movies.xml"

                    if utils.BoxSetsToTags:
                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += f'<node order="{NodeIndex}" type="folder">\n'
                            Data += f'    <icon>{node[2]}</icon>\n'
                            Data += f'    <label>EMBY: {node[1]}</label>\n'
                            Data += '    <path>plugin://plugin.video.emby-next-gen/?mode=collections&amp;mediatype=movie</path>\n'
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                    else:
                        NodeAdd = False

                        if utils.checkFileExists(FilePath):
                            utils.delFile(FilePath)
                elif node[0] == "collectionseries":
                    FilePath = "special://profile/library/video/emby_Collection_tvshows.xml"
                    NodePath = "library://video/emby_Collection_tvshows.xml"

                    if utils.BoxSetsToTags:
                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += f'<node order="{NodeIndex}" type="folder">\n'
                            Data += f'    <icon>{node[2]}</icon>\n'
                            Data += f'    <label>EMBY: {node[1]}</label>\n'
                            Data += '    <path>plugin://plugin.video.emby-next-gen/?mode=collections&amp;mediatype=tvshow</path>\n'
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                    else:
                        NodeAdd = False

                        if utils.checkFileExists(FilePath):
                            utils.delFile(FilePath)
                elif node[0] == "collectionmmusicvideos":
                    FilePath = "special://profile/library/video/emby_Collection_musicvideos.xml"
                    NodePath = "library://video/emby_Collection_musicvideos.xml"

                    if utils.BoxSetsToTags:
                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += f'<node order="{NodeIndex}" type="folder">\n'
                            Data += f'    <icon>{node[2]}</icon>\n'
                            Data += f'    <label>EMBY: {node[1]}</label>\n'
                            Data += '    <path>plugin://plugin.video.emby-next-gen/?mode=collections&amp;mediatype=musicvideo</path>\n'
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                    else:
                        NodeAdd = False

                        if utils.checkFileExists(FilePath):
                            utils.delFile(FilePath)
                elif node[0] == "downloadedmovies":
                    FilePath = "special://profile/library/video/emby_Download_movies.xml"
                    NodePath = "library://video/emby_Download_movies.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>movies</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="path" operator="contains">\n'
                        Data += '        <value>EMBY-offline-content</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "downloadedepisodes":
                    FilePath = "special://profile/library/video/emby_Download_episodes.xml"
                    NodePath = "library://video/emby_Download_episodes.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>episodes</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="path" operator="contains">\n'
                        Data += '        <value>EMBY-offline-content</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))
                elif node[0] == "downloadedmusicvideos":
                    FilePath = "special://profile/library/video/emby_Download_musicvideos.xml"
                    NodePath = "library://video/emby_Download_musicvideos.xml"

                    if not utils.checkFileExists(FilePath):
                        Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                        Data += f'<node order="{NodeIndex}" type="filter">\n'
                        Data += f'    <icon>{node[2]}</icon>\n'
                        Data += f'    <label>EMBY: {node[1]}</label>\n'
                        Data += '    <content>musicvideos</content>\n'
                        Data += '    <match>all</match>\n'
                        Data += '    <rule field="path" operator="contains">\n'
                        Data += '        <value>EMBY-offline-content</value>\n'
                        Data += '    </rule>\n'
                        Data += '</node>'
                        utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                NodeData = {'title': node[1], 'path': NodePath, 'icon': node[2]}

                if NodeAdd:
                    self.Nodes['NodesSynced'].append(NodeData)
                else:
                    if NodeData in self.Nodes['NodesSynced']:
                        del self.Nodes['NodesSynced'][self.Nodes['NodesSynced'].index(NodeData)]

def get_node_playlist_path(ContentType):
    if ContentType in ('music', 'audiobooks', 'podcasts'):
        node_path = "special://profile/library/music/"
        playlist_path = 'special://profile/playlists/music/'
    else:
        node_path = "special://profile/library/video/"
        playlist_path = 'special://profile/playlists/video/'

    return node_path, playlist_path

# Create or update the xsp file
def add_playlist(path, view):
    if not utils.xspplaylists:
        return

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

# Create or update the video node file
def add_nodes(path, view, Dynamic):
    if view['ContentType'] == 'tvshows':
        DefaultIcon = 'DefaultTVShows.png'
        ContentCategory = "TVShows"
    elif view['ContentType'] == 'movies':
        DefaultIcon = 'DefaultMovies.png'
        ContentCategory = "Movies"
    elif view['ContentType'] == 'musicvideos':
        DefaultIcon = 'DefaultMusicVideos.png'
        ContentCategory = "MusicVideos"
    else: # podcasts, audiobooks, music
        DefaultIcon = 'DefaultMusicVideos.png'
        ContentCategory = "Music"

    if Dynamic:
        folder = f"{path}emby_dynamic_{view['ContentType']}_{view['FilteredName']}/"
        utils.mkDir(folder)
        FilePath = f"{folder}index.xml"

        # Dynamic nodes
        if not utils.checkFileExists(FilePath):
            if view['Icon']:
                Icon = view['Icon']
            else:
                Icon = DefaultIcon

            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            Data += '<node order="0">\n'
            Data += f'    <label>EMBY DYNAMIC: {view["Name"]} ({view["ContentType"]})</label>\n'
            Data += f'    <icon>{Icon}</icon>\n'
            Data += '</node>'
            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

        for NodeIndex, node in enumerate(DynamicNodes[view['ContentType']], 1):
            if node[0] == "Letter":
                FolderPath = f"{folder}letter_{node[3].lower()}/"
                utils.mkDir(FolderPath)

                # index.xml
                FilePath = f"{FolderPath}index.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += '<node order="0">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                # 0-9.xml
                FilePath = f"{FolderPath}0-9.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="folder">\n'
                    Data += '    <label>0-9</label>\n'
                    Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=browse&amp;id=0-9&amp;parentid={view["LibraryId"]}&amp;libraryid={view["LibraryId"]}&amp;content={node[3]}&amp;server={view["ServerId"]}&amp;query=Letter</path>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                    # Alphabetically
                    FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

                    for Index, FileName in enumerate(FileNames, 2):
                        FilePath = f"{FolderPath}{FileName}.xml"

                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += f'<node order="{NodeIndex}" type="folder">\n'
                            Data += f'    <label>{FileName}</label>\n'
                            Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=browse&amp;id={FileName}&amp;parentid={view["LibraryId"]}&amp;libraryid={view["LibraryId"]}&amp;content={node[3]}&amp;server={view["ServerId"]}&amp;query=Letter</path>\n'
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            FilePath = f"{folder}{node[0].lower()}_{node[3].lower()}.xml"

            if not utils.checkFileExists(FilePath):
                Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                Data += f'<node order="{NodeIndex}" type="folder">\n'
                Data += f'    <label>{node[1]}</label>\n'
                Data += f'    <icon>{node[2]}</icon>\n'
                Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=browse&amp;id={view["LibraryId"]}&amp;parentid={view["LibraryId"]}&amp;libraryid={view["LibraryId"]}&amp;content={node[3]}&amp;server={view["ServerId"]}&amp;query={node[0]}</path>\n'
                Data += '</node>'
                utils.writeFileBinary(FilePath, Data.encode("utf-8"))
    else: # Synced nodes
        folder = f"{path}emby_{view['ContentType']}_{view['FilteredName']}/"
        utils.mkDir(folder)
        FilePath = f"{folder}index.xml"

        # synced nodes
        if not utils.checkFileExists(FilePath):
            if view['Icon']:
                Icon = view['Icon']
            else:
                Icon = DefaultIcon

            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            Data += f'<node order="0" visible="Library.HasContent({ContentCategory})">\n'
            Data += f'    <label>EMBY: {view["Name"]} ({view["ContentType"]})</label>\n'
            Data += f'    <icon>{Icon}</icon>\n'
            Data += '</node>'
            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

        for NodeIndex, node in enumerate(SyncNodes[view['ContentType']], 1):
            if node[0] == "collections":
                FilePath = f"{folder}collection.xml"

                if not utils.checkFileExists(FilePath):
                    NodeLink = quote(view["Name"])
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="folder">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <path>plugin://plugin.video.emby-next-gen/?mode=collections&amp;mediatype={view["KodiMediaType"]}&amp;librarytag={NodeLink}</path>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            # Library content
            if node[0] == "all":
                FilePath = f"{folder}all.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                        Operator = "is"
                        Filter = "tag"
                        SortOrder = "sorttitle"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                        Operator = "is"
                        Filter = "tag"
                        SortOrder = "sorttitle"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"
                        Operator = "is"
                        Filter = "tag"
                        SortOrder = "artist"
                    else: # Music
                        Content = "artists"
                        Operator = "is"
                        Filter = "disambiguation"
                        SortOrder = "sorttitle"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{view["Name"]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="{Operator}">{view["Tag"]}</rule>\n'
                    Data += f'    <order direction="ascending">{SortOrder}</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            # specific nodes
            if node[0] == "artists":
                FilePath = f"{folder}artists.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "MusicVideos":
                        Content = "musicvideos"
                        Filter = "tag"
                        Operator = "is"
                        Extras = '    <group>artists</group>\n'
                    else: # Music
                        Content = "artists"
                        Filter = "disambiguation"
                        Operator = "is"
                        Extras = '    <rule field="role" operator="is">artist</rule>\n'

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="{Operator}">{view["Tag"]}</rule>\n'
                    Data += Extras
                    Data += '    <order direction="ascending">artists</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "composers":
                FilePath = f"{folder}composers.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>artists</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="disambiguation" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="role" operator="is">composer</rule>\n'
                    Data += '    <order direction="ascending">artists</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "genres":
                FilePath = f"{folder}genres.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"
                        Filter = "tag"
                        Operator = "is"
                    else: # Music
                        Content = "artists"
                        Filter = "disambiguation"
                        Operator = "is"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="{Operator}">{view["Tag"]}</rule>\n'
                    Data += '    <group>genres</group>\n'
                    Data += '    <order direction="ascending">sorttitle</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "randomalbums":
                FilePath = f"{folder}randomalbums.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>albums</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="type" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <order>random</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyaddedalbums":
                FilePath = f"{folder}recentlyaddedalbums.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>albums</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="type" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <order direction="descending">dateadded</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyplayedmusic":
                FilePath = f"{folder}recentlyplayedmusic.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>songs</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="comment" operator="endswith">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="playcount" operator="greaterthan">0</rule>\n'
                    Data += '    <order direction="descending">lastplayed</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "years":
                FilePath = f"{folder}years.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                        Filter = "tag"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                        Filter = "tag"
                    elif ContentCategory == "MusicVideos":
                        Content = "artists"
                        Filter = "tag"
                    else: # Music
                        Content = "albums"
                        Filter = "type"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <order direction="descending">year</order>\n'
                    Data += '    <group>years</group>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "actors":
                FilePath = f"{folder}actors.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    elif ContentCategory == "MusicVideos":
                        Content = "artists"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <group>actors</group>\n'
                    Data += '    <order direction="ascending">title</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "favortites":
                FilePath = f"{folder}favortites.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "episodes"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += '    <rule field="tag" operator="endswith">(Favorites)</rule>\n'
                    Data += '    <order direction="ascending">title</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "inprogress":
                FilePath = f"{folder}inprogress.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="true"/>\n'
                    Data += '    <order direction="descending">lastplayed</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "inprogressepisodes":
                FilePath = f"{folder}inprogressepisodes.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>episodes</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="true"/>\n'
                    Data += '    <order direction="descending">lastplayed</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "nextepisodes":
                FilePath = f"{folder}nextepisodes.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="folder">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <path>plugin://plugin.video.emby-next-gen/?libraryname={quote(view.get("Name", "unknown"))}&mode=nextepisodes</path>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "random":
                FilePath = f"{folder}random.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"
                        Filter = "tag"
                        Operator = "is"
                    else:
                        Content = "songs"
                        Filter = "comment"
                        Operator = "endswith"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="{Operator}">{view["Tag"]}</rule>\n'
                    Data += '    <order>random</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyadded":
                FilePath = f"{folder}recentlyadded.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                        Filter = "tag"
                        Operator = "is"
                    elif ContentCategory == "MusicVideos":
                        Content = "musicvideos"
                        Filter = "tag"
                        Operator = "is"
                    else:
                        Content = "songs"
                        Filter = "comment"
                        Operator = "endswith"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="{Filter}" operator="{Operator}">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="playcount" operator="is">0</rule>\n'
                    Data += '    <order direction="descending">dateadded</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyaddedepisodes":
                FilePath = f"{folder}recentlyaddedepisodes.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>episodes</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="playcount" operator="is">0</rule>\n'
                    Data += '    <order direction="descending">dateadded</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyplayed":
                FilePath = f"{folder}recentlyplayed.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="false"/>\n'
                    Data += '    <rule field="playcount" operator="greaterthan">0</rule>\n'
                    Data += '    <order direction="descending">dateadded</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recentlyplayedepisodes":
                FilePath = f"{folder}recentlyplayedepisodes.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>episodes</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="false"/>\n'
                    Data += '    <rule field="playcount" operator="greaterthan">0</rule>\n'
                    Data += '    <order direction="descending">dateadded</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "recommended":
                FilePath = f"{folder}recommended.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="false"/>\n'
                    Data += '    <rule field="playcount" operator="is">0</rule>\n'
                    Data += '    <rule field="rating" operator="greaterthan">7</rule>\n'
                    Data += '    <order direction="descending">rating</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "studios":
                FilePath = f"{folder}studios.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <group>studios</group>\n'
                    Data += '    <order direction="ascending">title</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "tags":
                FilePath = f"{folder}tags.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <group>tags</group>\n'
                    Data += '    <order direction="ascending">title</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "unwatched":
                FilePath = f"{folder}unwatched.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "TVShows":
                        Content = "tvshows"
                    elif ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="false"/>\n'
                    Data += '    <rule field="playcount" operator="is">0</rule>\n'
                    Data += '    <order>random</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "unwatchedepisodes":
                FilePath = f"{folder}unwatchedepisodes.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>episodes</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="inprogress" operator="false"/>\n'
                    Data += '    <rule field="playcount" operator="is">0</rule>\n'
                    Data += '    <order>random</order>\n'
                    Data += f'    <limit>{utils.maxnodeitems}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "sets":
                FilePath = f"{folder}sets.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '    <content>movies</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <group>sets</group>\n'
                    Data += '    <order direction="ascending">sorttitle</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "resolution4k":
                FilePath = f"{folder}resolution4k.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="videoresolution" operator="greaterthan">1080</rule>\n'
                    Data += '    <order direction="ascending">sorttitle</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "resolutionhd":
                FilePath = f"{folder}resolutionhd.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="videoresolution" operator="is">1080</rule>\n'
                    Data += '    <order direction="ascending">sorttitle</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "resolutionsd":
                FilePath = f"{folder}resolutionsd.xml"

                if not utils.checkFileExists(FilePath):
                    if ContentCategory == "Movies":
                        Content = "movies"
                    else: # "MusicVideos":
                        Content = "musicvideos"

                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{NodeIndex}" type="filter">\n'
                    Data += f'    <label>{node[1]}</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                    Data += '    <rule field="videoresolution" operator="lessthan">1080</rule>\n'
                    Data += '    <order direction="ascending">sorttitle</order>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "songsbygenres":
                FolderPath = f"{folder}genres/"
                utils.delFolder(FolderPath)
                utils.mkDir(FolderPath)

                # index.xml
                FilePath = f"{FolderPath}index.xml"
                Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                Data += '<node order="0" visible="Library.HasContent(Music)">\n'
                Data += f'    <label>{node[1]}</label>\n'
                Data += '</node>'
                utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                # create genre nodes.xml
                musicdb = dbio.DBOpenRO("music", "node_songsbygenres")
                Genres = musicdb.get_genre(view['LibraryId'])
                dbio.DBCloseRO("music", "node_songsbygenres")

                for Index, Genre in enumerate(Genres, 1):
                    Genre = utils.encode_XML(Genre)
                    FilePath = f"{FolderPath}{Index}.xml"
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="{Index}" type="filter">\n'
                    Data += f'    <label>{Genre}</label>\n'
                    Data += '    <content>songs</content>\n'
                    Data += '    <match>all</match>\n'
                    Data += f'    <rule field="comment" operator="endswith">{view["Tag"]}</rule>\n'
                    Data += f'    <rule field="genre" operator="is">{Genre}</rule>\n'
                    Data += '    <order direction="ascending">title</order>\n'
                    Data += f'    <limit>{int(utils.maxnodeitems) * 10}</limit>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                continue

            if node[0] == "letter":
                FolderPath = f"{folder}letter/"
                utils.mkDir(FolderPath)
                Extras = ""

                if ContentCategory == "TVShows":
                    Content = "tvshows"
                elif ContentCategory == "Movies":
                    Content = "movies"
                elif ContentCategory == "MusicVideos":
                    Content = "musicvideos"
                    Extras = '    <group>artists</group>\n'
                else: # Music
                    Content = "artists"

                # index.xml
                FilePath = f"{FolderPath}index.xml"

                if not utils.checkFileExists(FilePath):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += f'<node order="0" visible="Library.HasContent({ContentCategory})">\n'
                    Data += '    <label>A-Z</label>\n'
                    Data += f'    <icon>{node[2]}</icon>\n'
                    Data += '</node>'
                    utils.writeFileBinary(FilePath, Data.encode("utf-8"))

                # 0-9.xml
                FileName = f"{FolderPath}0-9.xml"

                if not utils.checkFileExists(FileName):
                    Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                    Data += '<node order="1" type="filter">\n'
                    Data += '    <label>0-9</label>\n'
                    Data += f'    <content>{Content}</content>\n'
                    Data += '    <match>all</match>\n'

                    if ContentCategory == "Music":
                        Data += '    <order direction="ascending">artist</order>\n'
                        Data += f'    <rule field="disambiguation" operator="is">{view["Tag"]}</rule>\n'
                        Data += '    <rule field="artist" operator="startswith">\n'
                    elif ContentCategory == "MusicVideos":
                        Data += '    <order direction="ascending">artist</order>\n'
                        Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                        Data += '    <rule field="artist" operator="startswith">\n'
                    else:
                        Data += '    <order direction="ascending">sorttitle</order>\n'
                        Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                        Data += '    <rule field="sorttitle" operator="startswith">\n'

                    Data += '        <value>0</value>\n'
                    Data += '        <value>1</value>\n'
                    Data += '        <value>2</value>\n'
                    Data += '        <value>3</value>\n'
                    Data += '        <value>4</value>\n'
                    Data += '        <value>5</value>\n'
                    Data += '        <value>6</value>\n'
                    Data += '        <value>7</value>\n'
                    Data += '        <value>8</value>\n'
                    Data += '        <value>9</value>\n'
                    Data += '        <value>&amp;</value>\n'
                    Data += '        <value>Ä</value>\n'
                    Data += '        <value>Ö</value>\n'
                    Data += '        <value>Ü</value>\n'
                    Data += '        <value>!</value>\n'
                    Data += '        <value>(</value>\n'
                    Data += '        <value>)</value>\n'
                    Data += '        <value>@</value>\n'
                    Data += '        <value>#</value>\n'
                    Data += '        <value>$</value>\n'
                    Data += '        <value>^</value>\n'
                    Data += '        <value>*</value>\n'
                    Data += '        <value>-</value>\n'
                    Data += '        <value>=</value>\n'
                    Data += '        <value>+</value>\n'
                    Data += '        <value>{</value>\n'
                    Data += '        <value>}</value>\n'
                    Data += '        <value>[</value>\n'
                    Data += '        <value>]</value>\n'
                    Data += '        <value>?</value>\n'
                    Data += '        <value>:</value>\n'
                    Data += '        <value>;</value>\n'
                    Data += '        <value>,</value>\n'
                    Data += '        <value>.</value>\n'
                    Data += '        <value>&lt;</value>\n'
                    Data += '        <value>&gt;</value>\n'
                    Data += '        <value>~</value>\n'
                    Data += '        <value>&quot;</value>\n'
                    Data += '        <value>&apos;</value>\n'
                    Data += '    </rule>\n'
                    Data += Extras
                    Data += '</node>'
                    utils.writeFileBinary(FileName, Data.encode("utf-8"))

                    # Alphabetically
                    FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

                    for Index, FileName in enumerate(FileNames, 2):
                        FilePath = f"{FolderPath}{FileName}.xml"

                        if not utils.checkFileExists(FilePath):
                            Data = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
                            Data += f'<node order="{Index}" type="filter">\n'
                            Data += f'    <label>{FileName}</label>\n'
                            Data += f'    <content>{Content}</content>\n'
                            Data += '    <match>all</match>\n'

                            if ContentCategory == "Music":
                                Data += '    <order direction="ascending">artist</order>\n'
                                Data += f'    <rule field="disambiguation" operator="is">{view["Tag"]}</rule>\n'
                                Data += f'    <rule field="artist" operator="startswith">{FileName}</rule>\n'
                            elif ContentCategory == "MusicVideos":
                                Data += '    <order direction="ascending">artist</order>\n'
                                Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                                Data += f'    <rule field="artist" operator="startswith">{FileName}</rule>\n'
                            else:
                                Data += '    <order direction="ascending">sorttitle</order>\n'
                                Data += f'    <rule field="tag" operator="is">{view["Tag"]}</rule>\n'
                                Data += f'    <rule field="sorttitle" operator="startswith">{FileName}</rule>\n'

                            Data += Extras
                            Data += '</node>'
                            utils.writeFileBinary(FilePath, Data.encode("utf-8"))

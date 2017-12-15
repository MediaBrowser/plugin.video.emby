"""
Collection of functions using the Kodi JSON RPC interface.
See http://kodi.wiki/view/JSON-RPC_API
"""
from json import loads, dumps
from utils import millis_to_kodi_time
from xbmc import executeJSONRPC


class JsonRPC(object):
    """
    Used for all Kodi JSON RPC calls.
    """
    id_ = 1
    version = "2.0"

    def __init__(self, method, **kwargs):
        """
        Initialize with the Kodi method, e.g. 'Player.GetActivePlayers'
        """
        self.method = method
        self.params = None
        for arg in kwargs:
            self.arg = arg

    def _query(self):
        query = {
            'jsonrpc': self.version,
            'id': self.id_,
            'method': self.method,
        }
        if self.params is not None:
            query['params'] = self.params
        return dumps(query)

    def execute(self, params=None):
        """
        Pass any params as a dict. Will return Kodi's answer as a dict.
        """
        self.params = params
        return loads(executeJSONRPC(self._query()))


def get_players():
    """
    Returns all the active Kodi players (usually 3) in a dict:
    {
        'video': {'playerid': int, 'type': 'video'}
        'audio': ...
        'picture': ...
    }
    """
    info = JsonRPC("Player.GetActivePlayers").execute()['result']
    ret = {}
    for player in info:
        player['playerid'] = int(player['playerid'])
        ret[player['type']] = player
    return ret


def get_player_ids():
    """
    Returns a list of all the active Kodi player ids (usually 3) as int
    """
    ret = []
    for player in get_players().values():
        ret.append(player['playerid'])
    return ret


def get_playlist_id(typus):
    """
    Returns the corresponding Kodi playlist id as an int
        typus: Kodi playlist types: 'video', 'audio' or 'picture'

    Returns None if nothing was found
    """
    for playlist in get_playlists():
        if playlist.get('type') == typus:
            return playlist.get('playlistid')


def get_playlists():
    """
    Returns a list of all the Kodi playlists, e.g.
        [
            {u'playlistid': 0, u'type': u'audio'},
            {u'playlistid': 1, u'type': u'video'},
            {u'playlistid': 2, u'type': u'picture'}
        ]
    """
    try:
        ret = JsonRPC('Playlist.GetPlaylists').execute()['result']
    except KeyError:
        ret = []
    return ret


def get_volume():
    """
    Returns the Kodi volume as an int between 0 (min) and 100 (max)
    """
    return JsonRPC('Application.GetProperties').execute(
        {"properties": ['volume']})['result']['volume']


def set_volume(volume):
    """
    Set's the volume (for Kodi overall, not only a player).
    Feed with an int
    """
    return JsonRPC('Application.SetVolume').execute({"volume": volume})


def get_muted():
    """
    Returns True if Kodi is muted, False otherwise
    """
    return JsonRPC('Application.GetProperties').execute(
        {"properties": ['muted']})['result']['muted']


def play():
    """
    Toggles all Kodi players to play
    """
    for playerid in get_player_ids():
        JsonRPC("Player.PlayPause").execute({"playerid": playerid,
                                             "play": True})


def pause():
    """
    Pauses playback for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.PlayPause").execute({"playerid": playerid,
                                             "play": False})


def stop():
    """
    Stops playback for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.Stop").execute({"playerid": playerid})


def seek_to(offset):
    """
    Seeks all Kodi players to offset [int]
    """
    for playerid in get_player_ids():
        JsonRPC("Player.Seek").execute(
            {"playerid": playerid,
             "value": millis_to_kodi_time(offset)})


def smallforward():
    """
    Small step forward for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallforward"})


def smallbackward():
    """
    Small step backward for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallbackward"})


def skipnext():
    """
    Skips to the next item to play for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.GoTo").execute({"playerid": playerid,
                                        "to": "next"})


def skipprevious():
    """
    Skips to the previous item to play for all Kodi players
    """
    for playerid in get_player_ids():
        JsonRPC("Player.GoTo").execute({"playerid": playerid,
                                        "to": "previous"})


def input_up():
    """
    Tells Kodi the user pushed up
    """
    return JsonRPC("Input.Up").execute()


def input_down():
    """
    Tells Kodi the user pushed down
    """
    return JsonRPC("Input.Down").execute()


def input_left():
    """
    Tells Kodi the user pushed left
    """
    return JsonRPC("Input.Left").execute()


def input_right():
    """
    Tells Kodi the user pushed left
    """
    return JsonRPC("Input.Right").execute()


def input_select():
    """
    Tells Kodi the user pushed select
    """
    return JsonRPC("Input.Select").execute()


def input_home():
    """
    Tells Kodi the user pushed home
    """
    return JsonRPC("Input.Home").execute()


def input_back():
    """
    Tells Kodi the user pushed back
    """
    return JsonRPC("Input.Back").execute()


def input_sendtext(text):
    """
    Tells Kodi the user sent text [unicode]
    """
    return JsonRPC("Input.SendText").execute({'test': text, 'done': False})


def playlist_get_items(playlistid, properties):
    """
        playlistid:    [int] id of the Kodi playlist
        properties:    [list] of strings for the properties to return
                              e.g. 'title', 'file'

    Returns a list of Kodi playlist items as dicts with the keys specified in
    properties. Or an empty list if unsuccessful. Example:
    [{u'title': u'3 Idiots', u'type': u'movie', u'id': 3, u'file':
    u'smb://nas/PlexMovies/3 Idiots 2009 pt1.mkv', u'label': u'3 Idiots'}]
    """
    reply = JsonRPC('Playlist.GetItems').execute({
        'playlistid': playlistid,
        'properties': properties
    })
    try:
        reply = reply['result']['items']
    except KeyError:
        reply = []
    return reply


def playlist_add(playlistid, item):
    """
    Adds an item to the Kodi playlist with id playlistid. item is either the
    dict
        {'file': filepath as string}
    or
        {kodi_type: kodi_id}

    Returns a dict with the key 'error' if unsuccessful.
    """
    return JsonRPC('Playlist.Add').execute({'playlistid': playlistid,
                                            'item': item})


def playlist_insert(params):
    """
    Insert item(s) into playlist. Does not work for picture playlists (aka
    slideshows). params is the dict
    {
        'playlistid': [int]
        'position': [int]
        'item': <item>
    }
    item is either the dict
            {'file': filepath as string}
        or
            {kodi_type: kodi_id}
    Returns a dict with the key 'error' if something went wrong.
    """
    return JsonRPC('Playlist.Insert').execute(params)


def playlist_remove(playlistid, position):
    """
    Removes the playlist item at position from the playlist
        position:   [int]

    Returns a dict with the key 'error' if something went wrong.
    """
    return JsonRPC('Playlist.Remove').execute({'playlistid': playlistid,
                                               'position': position})


def get_setting(setting):
    """
    Returns the Kodi setting (GetSettingValue), a [str], or None if not
    possible
    """
    try:
        ret = JsonRPC('Settings.GetSettingValue').execute(
            {'setting': setting})['result']['value']
    except (KeyError, TypeError):
        ret = None
    return ret


def set_setting(setting, value):
    """
    Sets the Kodi setting, a [str], to value
    """
    return JsonRPC('Settings.SetSettingValue').execute(
        {'setting': setting, 'value': value})


def get_tv_shows(params):
    """
    Returns a list of tv shows for params (check the Kodi wiki)
    """
    ret = JsonRPC('VideoLibrary.GetTVShows').execute(params)
    try:
        ret['result']['tvshows']
    except (KeyError, TypeError):
        ret = []
    return ret


def get_episodes(params):
    """
    Returns a list of tv show episodes for params (check the Kodi wiki)
    """
    ret = JsonRPC('VideoLibrary.GetEpisodes').execute(params)
    try:
        ret['result']['episodes']
    except (KeyError, TypeError):
        ret = []
    return ret


def get_item(playerid):
    """
    UNRELIABLE on playback startup! (as other JSON and Python Kodi functions)
    Returns the following for the currently playing item:
    {
        u'title': u'Okja',
        u'type': u'movie',
        u'id': 258,
        u'file': u'smb://...movie.mkv',
        u'label': u'Okja'
    }
    """
    return JsonRPC('Player.GetItem').execute({
        'playerid': playerid,
        'properties': ['title', 'file']})['result']['item']


def get_player_props(playerid):
    """
    Returns a dict for the active Kodi player with the following values:
    {
        'type'          [str] the Kodi player type, e.g. 'video'
        'time'          The current item's time in Kodi time
        'totaltime'     The current item's total length in Kodi time
        'speed'         [int] playback speed, 0 is paused, 1 is playing
        'shuffled'      [bool] True if shuffled
        'repeat'        [str] 'off', 'one', 'all'
        'position'      [int] position in playlist (or -1)
        'playlistid'    [int] the Kodi playlist id (or -1)
    }
    """
    return JsonRPC('Player.GetProperties').execute({
        'playerid': playerid,
        'properties': ['type',
                       'time',
                       'totaltime',
                       'speed',
                       'shuffled',
                       'repeat',
                       'position',
                       'playlistid',
                       'currentvideostream',
                       'currentaudiostream',
                       'subtitleenabled',
                       'currentsubtitle']})['result']


def current_audiostream(playerid):
    """
    Returns a dict of the active audiostream for playerid [int]:
    {
        'index':    [int], audiostream index
        'language': [str]
        'name':     [str]
        'codec':    [str]
        'bitrate':  [int]
        'channels': [int]
    }
    or an empty dict if unsuccessful
    """
    ret = JsonRPC('Player.GetProperties').execute(
        {'properties': ['currentaudiostream'], 'playerid': playerid})
    try:
        ret = ret['result']['currentaudiostream']
    except (KeyError, TypeError):
        ret = {}
    return ret


def current_subtitle(playerid):
    """
    Returns a dict of the active subtitle for playerid [int]:
    {
        'index':    [int], subtitle index
        'language': [str]
        'name':     [str]
    }
    or an empty dict if unsuccessful
    """
    ret = JsonRPC('Player.GetProperties').execute(
        {'properties': ['currentsubtitle'], 'playerid': playerid})
    try:
        ret = ret['result']['currentsubtitle']
    except (KeyError, TypeError):
        ret = {}
    return ret


def subtitle_enabled(playerid):
    """
    Returns True if a subtitle is enabled, False otherwise
    """
    ret = JsonRPC('Player.GetProperties').execute(
        {'properties': ['subtitleenabled'], 'playerid': playerid})
    try:
        ret = ret['result']['subtitleenabled']
    except (KeyError, TypeError):
        ret = False
    return ret


def ping():
    """
    Pings the JSON RPC interface
    """
    return JsonRPC('JSONRPC.Ping').execute()

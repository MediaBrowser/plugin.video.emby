"""
Collection of functions using the Kodi JSON RPC interface.
See http://kodi.wiki/view/JSON-RPC_API
"""
from json import loads, dumps
from utils import milliseconds_to_kodi_time
from xbmc import executeJSONRPC


class jsonrpc(object):
    """
    Used for all Kodi JSON RPC calls.
    """
    id_ = 1
    jsonrpc = "2.0"

    def __init__(self, method, **kwargs):
        """
        Initialize with the Kodi method
        """
        self.method = method
        for arg in kwargs:  # id_(int), jsonrpc(str)
            self.arg = arg

    def _query(self):
        query = {
            'jsonrpc': self.jsonrpc,
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
    info = jsonrpc("Player.GetActivePlayers").execute()['result'] or []
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
        ret = jsonrpc('Playlist.GetPlaylists').execute()['result']
    except KeyError:
        ret = []
    return ret


def get_volume():
    """
    Returns the Kodi volume as an int between 0 (min) and 100 (max)
    """
    return jsonrpc('Application.GetProperties').execute(
        {"properties": ['volume']})['result']['volume']


def set_volume(volume):
    """
    Set's the volume (for Kodi overall, not only a player).
    Feed with an int
    """
    return jsonrpc('Application.SetVolume').execute({"volume": volume})


def get_muted():
    """
    Returns True if Kodi is muted, False otherwise
    """
    return jsonrpc('Application.GetProperties').execute(
        {"properties": ['muted']})['result']['muted']


def play():
    """
    Toggles all Kodi players to play
    """
    for playerid in get_player_ids():
        jsonrpc("Player.PlayPause").execute({"playerid": playerid,
                                             "play": True})


def pause():
    """
    Pauses playback for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.PlayPause").execute({"playerid": playerid,
                                             "play": False})


def stop():
    """
    Stops playback for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.Stop").execute({"playerid": playerid})


def seek_to(offset):
    """
    Seeks all Kodi players to offset [int]
    """
    for playerid in get_player_ids():
        jsonrpc("Player.Seek").execute(
            {"playerid": playerid,
             "value": milliseconds_to_kodi_time(offset)})


def smallforward():
    """
    Small step forward for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallforward"})


def smallbackward():
    """
    Small step backward for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallbackward"})


def skipnext():
    """
    Skips to the next item to play for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.GoTo").execute({"playerid": playerid,
                                        "to": "next"})


def skipprevious():
    """
    Skips to the previous item to play for all Kodi players
    """
    for playerid in get_player_ids():
        jsonrpc("Player.GoTo").execute({"playerid": playerid,
                                        "to": "previous"})


def input_up():
    """
    Tells Kodi the user pushed up
    """
    jsonrpc("Input.Up").execute()


def input_down():
    """
    Tells Kodi the user pushed down
    """
    jsonrpc("Input.Down").execute()


def input_left():
    """
    Tells Kodi the user pushed left
    """
    jsonrpc("Input.Left").execute()


def input_right():
    """
    Tells Kodi the user pushed left
    """
    jsonrpc("Input.Right").execute()


def input_select():
    """
    Tells Kodi the user pushed select
    """
    jsonrpc("Input.Select").execute()


def input_home():
    """
    Tells Kodi the user pushed home
    """
    jsonrpc("Input.Home").execute()


def input_back():
    """
    Tells Kodi the user pushed back
    """
    jsonrpc("Input.Back").execute()


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
    reply = jsonrpc('Playlist.GetItems').execute({
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
    return jsonrpc('Playlist.Add').execute({'playlistid': playlistid,
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
    return jsonrpc('Playlist.Insert').execute(params)


def playlist_remove(playlistid, position):
    """
    Removes the playlist item at position from the playlist
        position:   [int]

    Returns a dict with the key 'error' if something went wrong.
    """
    return jsonrpc('Playlist.Remove').execute({'playlistid': playlistid,
                                               'position': position})


def get_setting(setting):
    """
    Returns the Kodi setting (GetSettingValue), a [str], or None if not
    possible
    """
    try:
        ret = jsonrpc('Settings.GetSettingValue').execute(
            {'setting': setting})['result']['value']
    except (KeyError, TypeError):
        ret = None
    return ret


def set_setting(setting, value):
    """
    Sets the Kodi setting, a [str], to value
    """
    return jsonrpc('Settings.SetSettingValue').execute(
        {'setting': setting, 'value': value})


def get_tv_shows(params):
    """
    Returns a list of tv shows for params (check the Kodi wiki)
    """
    ret = jsonrpc('VideoLibrary.GetTVShows').execute(params)
    try:
        ret['result']['tvshows']
    except (KeyError, TypeError):
        ret = []
    return ret


def get_episodes(params):
    """
    Returns a list of tv show episodes for params (check the Kodi wiki)
    """
    ret = jsonrpc('VideoLibrary.GetEpisodes').execute(params)
    try:
        ret['result']['episodes']
    except (KeyError, TypeError):
        ret = []
    return ret


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
    ret = jsonrpc('Player.GetProperties').execute(
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
    ret = jsonrpc('Player.GetProperties').execute(
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
    ret = jsonrpc('Player.GetProperties').execute(
        {'properties': ['subtitleenabled'], 'playerid': playerid})
    try:
        ret = ret['result']['subtitleenabled']
    except (KeyError, TypeError):
        ret = False
    return ret

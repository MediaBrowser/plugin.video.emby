"""
Collection of functions using the Kodi JSON RPC interface.
See http://kodi.wiki/view/JSON-RPC_API
"""
from utils import JSONRPC, milliseconds_to_kodi_time


def get_players():
    """
    Returns all the active Kodi players (usually 3) in a dict:
    {
        'video': {'playerid': int, 'type': 'video'}
        'audio': ...
        'picture': ...
    }
    """
    info = JSONRPC("Player.GetActivePlayers").execute()['result'] or []
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
    return JSONRPC('Playlist.GetPlaylists').execute()


def set_volume(volume):
    """
    Set's the volume (for Kodi overall, not only a player).
    Feed with an int
    """
    return JSONRPC('Application.SetVolume').execute({"volume": volume})


def play():
    """
    Toggles all Kodi players to play
    """
    for playerid in get_player_ids():
        JSONRPC("Player.PlayPause").execute({"playerid": playerid,
                                             "play": True})


def pause():
    """
    Pauses playback for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.PlayPause").execute({"playerid": playerid,
                                             "play": False})


def stop():
    """
    Stops playback for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.Stop").execute({"playerid": playerid})


def seek_to(offset):
    """
    Seeks all Kodi players to offset [int]
    """
    for playerid in get_player_ids():
        JSONRPC("Player.Seek").execute(
            {"playerid": playerid,
             "value": milliseconds_to_kodi_time(offset)})


def smallforward():
    """
    Small step forward for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallforward"})


def smallbackward():
    """
    Small step backward for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.Seek").execute({"playerid": playerid,
                                        "value": "smallbackward"})


def skipnext():
    """
    Skips to the next item to play for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.GoTo").execute({"playerid": playerid,
                                        "to": "next"})


def skipprevious():
    """
    Skips to the previous item to play for all Kodi players
    """
    for playerid in get_player_ids():
        JSONRPC("Player.GoTo").execute({"playerid": playerid,
                                        "to": "previous"})


def input_up():
    """
    Tells Kodi the users pushed up
    """
    JSONRPC("Input.Up").execute()


def input_down():
    """
    Tells Kodi the users pushed down
    """
    JSONRPC("Input.Down").execute()


def input_left():
    """
    Tells Kodi the users pushed left
    """
    JSONRPC("Input.Left").execute()


def input_right():
    """
    Tells Kodi the users pushed left
    """
    JSONRPC("Input.Right").execute()


def input_select():
    """
    Tells Kodi the users pushed select
    """
    JSONRPC("Input.Select").execute()


def input_home():
    """
    Tells Kodi the users pushed home
    """
    JSONRPC("Input.Home").execute()


def input_back():
    """
    Tells Kodi the users pushed back
    """
    JSONRPC("Input.Back").execute()

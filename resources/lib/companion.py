# -*- coding: utf-8 -*-
import logging
from urlparse import urlparse
from re import compile as re_compile

from utils import JSONRPC
import plexdb_functions as plexdb
from variables import ALEXA_TO_COMPANION

###############################################################################

log = logging.getLogger("PLEX."+__name__)

REGEX_PLAYQUEUES = re_compile(r'''/playQueues/(\d+)$''')

###############################################################################


def getPlayers():
    info = JSONRPC("Player.GetActivePlayers").execute()['result'] or []
    log.debug('players: %s' % JSONRPC("Player.GetActivePlayers").execute())
    ret = {}
    for player in info:
        player['playerid'] = int(player['playerid'])
        ret[player['type']] = player
    return ret


def getPlayerIds():
    ret = []
    for player in getPlayers().values():
        ret.append(player['playerid'])
    return ret


def getPlaylistId(typus):
    """
    typus: one of the Kodi types, e.g. audio or video

    Returns None if nothing was found
    """
    for playlist in getPlaylists():
        if playlist.get('type') == typus:
            return playlist.get('playlistid')


def getPlaylists():
    """
    Returns a list, e.g.
        [
            {u'playlistid': 0, u'type': u'audio'},
            {u'playlistid': 1, u'type': u'video'},
            {u'playlistid': 2, u'type': u'picture'}
        ]
    """
    return JSONRPC('Playlist.GetPlaylists').execute()


def millisToTime(t):
    millis = int(t)
    seconds = millis / 1000
    minutes = seconds / 60
    hours = minutes / 60
    seconds = seconds % 60
    minutes = minutes % 60
    millis = millis % 1000
    return {'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'milliseconds': millis}


def skipTo(self, plexId, typus):
    # playlistId = self.getPlaylistId(tryDecode(xbmc_type(typus)))
    # playerId = self.
    with plexdb.Get_Plex_DB() as plex_db:
        plexdb_item = plex_db.getItem_byId(plexId)
        try:
            dbid = plexdb_item[0]
            mediatype = plexdb_item[4]
        except TypeError:
            log.info('Couldnt find item %s in Kodi db' % plexId)
            return
    log.debug('plexid: %s, kodi id: %s, type: %s'
              % (plexId, dbid, mediatype))


def convert_alexa_to_companion(dictionary):
    for key in dictionary:
        if key in ALEXA_TO_COMPANION:
            dictionary[ALEXA_TO_COMPANION[key]] = dictionary[key]
            del dictionary[key]


def process_command(request_path, params, queue=None):
    """
    queue: Queue() of PlexCompanion.py
    """
    if params.get('deviceName') == 'Alexa':
        convert_alexa_to_companion(params)
    log.debug('Received request_path: %s, params: %s' % (request_path, params))
    if "/playMedia" in request_path:
        # We need to tell service.py
        queue.put({
            'action': 'playlist',
            'data': params
        })

    elif request_path == "player/playback/setParameters":
        if 'volume' in params:
            volume = int(params['volume'])
            log.debug("Adjusting the volume to %s" % volume)
            JSONRPC('Application.SetVolume').execute({"volume": volume})

    elif request_path == "player/playback/play":
        for playerid in getPlayerIds():
            JSONRPC("Player.PlayPause").execute({"playerid": playerid,
                                                "play": True})

    elif request_path == "player/playback/pause":
        for playerid in getPlayerIds():
            JSONRPC("Player.PlayPause").execute({"playerid": playerid,
                                                "play": False})

    elif request_path == "player/playback/stop":
        for playerid in getPlayerIds():
            JSONRPC("Player.Stop").execute({"playerid": playerid})

    elif request_path == "player/playback/seekTo":
        for playerid in getPlayerIds():
            JSONRPC("Player.Seek").execute(
                {"playerid": playerid,
                 "value": millisToTime(params.get('offset', 0))})

    elif request_path == "player/playback/stepForward":
        for playerid in getPlayerIds():
            JSONRPC("Player.Seek").execute({"playerid": playerid,
                                           "value": "smallforward"})

    elif request_path == "player/playback/stepBack":
        for playerid in getPlayerIds():
            JSONRPC("Player.Seek").execute({"playerid": playerid,
                                           "value": "smallbackward"})

    elif request_path == "player/playback/skipNext":
        for playerid in getPlayerIds():
            JSONRPC("Player.GoTo").execute({"playerid": playerid,
                                           "to": "next"})

    elif request_path == "player/playback/skipPrevious":
        for playerid in getPlayerIds():
            JSONRPC("Player.GoTo").execute({"playerid": playerid,
                                           "to": "previous"})

    elif request_path == "player/playback/skipTo":
        skipTo(params.get('key').rsplit('/', 1)[1], params.get('type'))

    elif request_path == "player/navigation/moveUp":
        JSONRPC("Input.Up").execute()

    elif request_path == "player/navigation/moveDown":
        JSONRPC("Input.Down").execute()

    elif request_path == "player/navigation/moveLeft":
        JSONRPC("Input.Left").execute()

    elif request_path == "player/navigation/moveRight":
        JSONRPC("Input.Right").execute()

    elif request_path == "player/navigation/select":
        JSONRPC("Input.Select").execute()

    elif request_path == "player/navigation/home":
        JSONRPC("Input.Home").execute()

    elif request_path == "player/navigation/back":
        JSONRPC("Input.Back").execute()

    else:
        log.error('Unknown request path: %s' % request_path)

# -*- coding: utf-8 -*-
import logging
from re import compile as re_compile

from xbmc import Player

from utils import JSONRPC
from variables import ALEXA_TO_COMPANION
from playqueue import Playqueue
from PlexFunctions import GetPlexKeyNumber

###############################################################################

log = logging.getLogger("PLEX."+__name__)

REGEX_PLAYQUEUES = re_compile(r'''/playQueues/(\d+)$''')

###############################################################################


def getPlayers():
    info = JSONRPC("Player.GetActivePlayers").execute()['result'] or []
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


def skipTo(params):
    # Does not seem to be implemented yet
    playQueueItemID = params.get('playQueueItemID', 'not available')
    library, plex_id = GetPlexKeyNumber(params.get('key'))
    log.debug('Skipping to playQueueItemID %s, plex_id %s'
              % (playQueueItemID, plex_id))
    found = True
    playqueues = Playqueue()
    for (player, ID) in getPlayers().iteritems():
        playqueue = playqueues.get_playqueue_from_type(player)
        for i, item in enumerate(playqueue.items):
            if item.ID == playQueueItemID or item.plex_id == plex_id:
                break
        else:
            log.debug('Item not found to skip to')
            found = False
        if found:
            Player().play(playqueue.kodi_pl, None, False, i)


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
        action = 'alexa' if params.get('deviceName') == 'Alexa' else 'playlist'
        queue.put({
            'action': action,
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
        skipTo(params)

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

"""
Processes Plex companion inputs from the plexbmchelper to Kodi commands
"""
from logging import getLogger

from xbmc import Player

from variables import ALEXA_TO_COMPANION
from playqueue import Playqueue
from PlexFunctions import GetPlexKeyNumber
import json_rpc as js
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


def skip_to(params):
    """
    Skip to a specific playlist position.

    Does not seem to be implemented yet by Plex!
    """
    playqueue_item_id = params.get('playQueueItemID')
    _, plex_id = GetPlexKeyNumber(params.get('key'))
    LOG.debug('Skipping to playQueueItemID %s, plex_id %s',
              playqueue_item_id, plex_id)
    found = True
    playqueues = Playqueue()
    for player in js.get_players().values():
        playqueue = playqueues.playqueues[player['playerid']]
        for i, item in enumerate(playqueue.items):
            if item.id == playqueue_item_id:
                found = True
                break
        else:
            for i, item in enumerate(playqueue.items):
                if item.plex_id == plex_id:
                    found = True
                    break
        if found is True:
            Player().play(playqueue.kodi_pl, None, False, i)
        else:
            LOG.error('Item not found to skip to')


def convert_alexa_to_companion(dictionary):
    """
    The params passed by Alexa must first be converted to Companion talk
    """
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
    LOG.debug('Received request_path: %s, params: %s', request_path, params)
    if request_path == 'player/playback/playMedia':
        state.PLAYBACK_INIT_DONE = False
        # We need to tell service.py
        action = 'alexa' if params.get('deviceName') == 'Alexa' else 'playlist'
        queue.put({
            'action': action,
            'data': params
        })
    elif request_path == 'player/playback/refreshPlayQueue':
        state.PLAYBACK_INIT_DONE = False
        queue.put({
            'action': 'refreshPlayQueue',
            'data': params
        })
    elif request_path == "player/playback/setParameters":
        if 'volume' in params:
            js.set_volume(int(params['volume']))
        else:
            LOG.error('Unknown parameters: %s', params)
    elif request_path == "player/playback/play":
        js.play()
    elif request_path == "player/playback/pause":
        js.pause()
    elif request_path == "player/playback/stop":
        js.stop()
    elif request_path == "player/playback/seekTo":
        js.seek_to(int(params.get('offset', 0)))
    elif request_path == "player/playback/stepForward":
        js.smallforward()
    elif request_path == "player/playback/stepBack":
        js.smallbackward()
    elif request_path == "player/playback/skipNext":
        state.PLAYBACK_INIT_DONE = False
        js.skipnext()
    elif request_path == "player/playback/skipPrevious":
        state.PLAYBACK_INIT_DONE = False
        js.skipprevious()
    elif request_path == "player/playback/skipTo":
        state.PLAYBACK_INIT_DONE = False
        skip_to(params)
    elif request_path == "player/navigation/moveUp":
        js.input_up()
    elif request_path == "player/navigation/moveDown":
        js.input_down()
    elif request_path == "player/navigation/moveLeft":
        js.input_left()
    elif request_path == "player/navigation/moveRight":
        js.input_right()
    elif request_path == "player/navigation/select":
        js.input_select()
    elif request_path == "player/navigation/home":
        js.input_home()
    elif request_path == "player/navigation/back":
        js.input_back()
    elif request_path == "player/playback/setStreams":
        queue.put({
            'action': 'setStreams',
            'data': params
        })
    else:
        LOG.error('Unknown request path: %s', request_path)

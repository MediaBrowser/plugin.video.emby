"""
Monitors the Kodi playqueue and adjusts the Plex playqueue accordingly
"""
from logging import getLogger
from threading import RLock, Thread

from xbmc import Player, PlayList, PLAYLIST_MUSIC, PLAYLIST_VIDEO

from utils import window
import playlist_func as PL
from PlexFunctions import ConvertPlexToKodiTime, GetAllPlexChildren
from PlexAPI import API
from playbackutils import PlaybackUtils
import json_rpc as js
import variables as v

###############################################################################
LOG = getLogger("PLEX." + __name__)

# lock used for playqueue manipulations
LOCK = RLock()
PLUGIN = 'plugin://%s' % v.ADDON_ID

# Our PKC playqueues (3 instances of Playqueue_Object())
PLAYQUEUES = []
###############################################################################


def init_playqueues():
    """
    Call this once on startup to initialize the PKC playqueue objects in
    the list PLAYQUEUES
    """
    if PLAYQUEUES:
        LOG.debug('Playqueues have already been initialized')
        return
    # Initialize Kodi playqueues
    with LOCK:
        for i in (0, 1, 2):
            # Just in case the Kodi response is not sorted correctly
            for queue in js.get_playlists():
                if queue['playlistid'] != i:
                    continue
                playqueue = PL.Playqueue_Object()
                playqueue.playlistid = i
                playqueue.type = queue['type']
                # Initialize each Kodi playlist
                if playqueue.type == v.KODI_TYPE_AUDIO:
                    playqueue.kodi_pl = PlayList(PLAYLIST_MUSIC)
                elif playqueue.type == v.KODI_TYPE_VIDEO:
                    playqueue.kodi_pl = PlayList(PLAYLIST_VIDEO)
                else:
                    # Currently, only video or audio playqueues available
                    playqueue.kodi_pl = PlayList(PLAYLIST_VIDEO)
                    # Overwrite 'picture' with 'photo'
                    playqueue.type = v.KODI_TYPE_PHOTO
                PLAYQUEUES.append(playqueue)
    LOG.debug('Initialized the Kodi playqueues: %s', PLAYQUEUES)


def get_playqueue_from_type(typus):
    """
    Returns the playqueue according to the typus ('video', 'audio',
    'picture') passed in
    """
    with LOCK:
        for playqueue in PLAYQUEUES:
            if playqueue.type == typus:
                break
        else:
            raise ValueError('Wrong playlist type passed in: %s' % typus)
        return playqueue


def init_playqueue_from_plex_children(plex_id, transient_token=None):
    """
    Init a new playqueue e.g. from an album. Alexa does this

    Returns the Playlist_Object
    """
    xml = GetAllPlexChildren(plex_id)
    try:
        xml[0].attrib
    except (TypeError, IndexError, AttributeError):
        LOG.error('Could not download the PMS xml for %s', plex_id)
        return
    playqueue = get_playqueue_from_type(
        v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[xml[0].attrib['type']])
    playqueue.clear()
    for i, child in enumerate(xml):
        api = API(child)
        PL.add_item_to_playlist(playqueue, i, plex_id=api.getRatingKey())
    playqueue.plex_transient_token = transient_token
    LOG.debug('Firing up Kodi player')
    Player().play(playqueue.kodi_pl, None, False, 0)
    return playqueue


def update_playqueue_from_PMS(playqueue,
                              playqueue_id=None,
                              repeat=None,
                              offset=None,
                              transient_token=None):
    """
    Completely updates the Kodi playqueue with the new Plex playqueue. Pass
    in playqueue_id if we need to fetch a new playqueue

    repeat = 0, 1, 2
    offset = time offset in Plextime (milliseconds)
    """
    LOG.info('New playqueue %s received from Plex companion with offset '
             '%s, repeat %s', playqueue_id, offset, repeat)
    # Safe transient token from being deleted
    if transient_token is None:
        transient_token = playqueue.plex_transient_token
    with LOCK:
        xml = PL.get_PMS_playlist(playqueue, playqueue_id)
        playqueue.clear()
        try:
            PL.get_playlist_details_from_xml(playqueue, xml)
        except KeyError:
            LOG.error('Could not get playqueue ID %s', playqueue_id)
            return
        playqueue.repeat = 0 if not repeat else int(repeat)
        playqueue.plex_transient_token = transient_token
        PlaybackUtils(xml, playqueue).play_all()
        window('plex_customplaylist', value="true")
        if offset not in (None, "0"):
            window('plex_customplaylist.seektime',
                   str(ConvertPlexToKodiTime(offset)))
        for startpos, item in enumerate(playqueue.items):
            if item.id == playqueue.selectedItemID:
                break
        else:
            startpos = 0
        # Start playback. Player does not return in time
        LOG.debug('Playqueues after Plex Companion update are now: %s',
                  PLAYQUEUES)
        thread = Thread(target=Player().play,
                        args=(playqueue.kodi_pl,
                              None,
                              False,
                              startpos))
        thread.setDaemon(True)
        thread.start()

"""
Used to kick off Kodi playback
"""
from logging import getLogger
from threading import Thread
from urllib import urlencode

from xbmc import Player, sleep

from PlexAPI import API
from PlexFunctions import GetPlexMetadata, init_plex_playqueue
import plexdb_functions as plexdb
import playlist_func as PL
import playqueue as PQ
from playutils import PlayUtils
from PKC_listitem import PKC_ListItem
from pickler import pickle_me, Playback_Successful
import json_rpc as js
from utils import window, settings, dialog, language as lang
from plexbmchelper.subscribers import LOCKER
import variables as v
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


@LOCKER.lockthis
def playback_triage(plex_id=None, plex_type=None, path=None):
    """
    Hit this function for addon path playback, Plex trailers, etc.
    Will setup playback first, then on second call complete playback.

    Will set Playback_Successful() with potentially a PKC_ListItem() attached
    (to be consumed by setResolvedURL in default.py)

    If trailers or additional (movie-)parts are added, default.py is released
    and a completely new player instance is called with a new playlist. This
    circumvents most issues with Kodi & playqueues
    """
    LOG.info('playback_triage called with plex_id %s, plex_type %s, path %s',
             plex_id, plex_type, path)
    if not state.AUTHENTICATED:
        LOG.error('Not yet authenticated for PMS, abort starting playback')
        # Release default.py
        pickle_me(Playback_Successful())
        # "Unauthorized for PMS"
        dialog('notification', lang(29999), lang(30017))
        return
    playqueue = PQ.get_playqueue_from_type(
        v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[plex_type])
    pos = js.get_position(playqueue.playlistid)
    # Can return -1 (as in "no playlist")
    pos = pos if pos != -1 else 0
    LOG.info('playQueue position: %s for %s', pos, playqueue)
    # Have we already initiated playback?
    try:
        playqueue.items[pos]
    except IndexError:
        playback_init(plex_id, plex_type, playqueue)
    else:
        # kick off playback on second pass
        conclude_playback(playqueue, pos)


def playback_init(plex_id, plex_type, playqueue):
    """
    Playback setup if Kodi starts playing an item for the first time.
    """
    LOG.info('Initializing PKC playback')
    contextmenu_play = window('plex_contextplay') == 'true'
    window('plex_contextplay', clear=True)
    xml = GetPlexMetadata(plex_id)
    try:
        xml[0].attrib
    except (IndexError, TypeError, AttributeError):
        LOG.error('Could not get a PMS xml for plex id %s', plex_id)
        # Release default.py
        pickle_me(Playback_Successful())
        # "Play error"
        dialog('notification', lang(29999), lang(30128), icon='{error}')
        return
    api = API(xml[0])
    resume, _ = api.getRuntime()
    trailers = False
    if (plex_type == v.PLEX_TYPE_MOVIE and not resume and
            settings('enableCinema') == "true"):
        if settings('askCinema') == "true":
            # "Play trailers?"
            trailers = dialog('yesno', lang(29999), lang(33016))
            trailers = True if trailers else False
        else:
            trailers = True
    LOG.info('Playing trailers: %s', trailers)
    # Post to the PMS to create a playqueue - in any case due to Plex Companion
    xml = init_plex_playqueue(plex_id,
                              xml.attrib.get('librarySectionUUID'),
                              mediatype=plex_type,
                              trailers=trailers)
    if xml is None:
        LOG.error('Could not get a playqueue xml for plex id %s, UUID %s',
                  plex_id, xml.attrib.get('librarySectionUUID'))
        # Release default.py
        pickle_me(Playback_Successful())
        # "Play error"
        dialog('notification', lang(29999), lang(30128), icon='{error}')
        return
    # Should already be empty, but just in case
    playqueue.clear()
    PL.get_playlist_details_from_xml(playqueue, xml)
    stack = _prep_playlist_stack(xml)
    # Release our default.py before starting our own Kodi player instance
    pickle_me(Playback_Successful())
    # Sleep a bit to let setResolvedUrl do its thing - bit ugly
    sleep(200)
    _process_stack(playqueue, stack)
    # New thread to release this one sooner (e.g. harddisk spinning up)
    thread = Thread(target=Player().play,
                    args=(playqueue.kodi_pl, ))
    thread.setDaemon(True)
    LOG.info('Done initializing PKC playback, starting Kodi player')
    thread.start()


def _prep_playlist_stack(xml):
    stack = []
    for item in xml:
        api = API(item)
        if api.getType() != v.PLEX_TYPE_CLIP:
            with plexdb.Get_Plex_DB() as plex_db:
                plex_dbitem = plex_db.getItem_byId(api.getRatingKey())
            kodi_id = plex_dbitem[0] if plex_dbitem else None
            kodi_type = plex_dbitem[4] if plex_dbitem else None
        else:
            # We will never store clips (trailers) in the Kodi DB
            kodi_id = None
            kodi_type = None
        resume, _ = api.getRuntime()
        for part, _ in enumerate(item[0]):
            api.setPartNumber(part)
            if kodi_id is None:
                # Need to redirect again to PKC to conclude playback
                params = {
                    'mode': 'play',
                    'plex_id': api.getRatingKey(),
                    'plex_type': api.getType()
                }
                path = ('plugin://plugin.video.plexkodiconnect?%s'
                        % urlencode(params))
                listitem = api.CreateListItemFromPlexItem()
                listitem.setPath(path)
            else:
                # Will add directly via the Kodi DB
                path = None
                listitem = None
            stack.append({
                'kodi_id': kodi_id,
                'kodi_type': kodi_type,
                'file': path,
                'xml_video_element': item,
                'listitem': listitem,
                'part': part,
                'playcount': api.getViewCount(),
                'offset': resume
            })
    return stack


def _process_stack(playqueue, stack):
    """
    Takes our stack and adds the items to the PKC and Kodi playqueues.
    """
    # getposition() can return -1
    pos = max(playqueue.kodi_pl.getposition(), 0) + 1
    for item in stack:
        if item['kodi_id'] is None:
            playlist_item = PL.add_listitem_to_Kodi_playlist(
                playqueue,
                pos,
                item['listitem'],
                file=item['file'],
                xml_video_element=item['xml_video_element'])
        else:
            # Directly add element so we have full metadata
            playlist_item = PL.add_item_to_kodi_playlist(
                playqueue,
                pos,
                kodi_id=item['kodi_id'],
                kodi_type=item['kodi_type'],
                xml_video_element=item['xml_video_element'])
        playlist_item.playcount = item['playcount']
        playlist_item.offset = item['offset']
        playlist_item.part = item['part']
        playlist_item.init_done = True
        pos += 1


def conclude_playback(playqueue, pos):
    """
    ONLY if actually being played (e.g. at 5th position of a playqueue).

        Decide on direct play, direct stream, transcoding
        path to
            direct paths: file itself
            PMS URL
            Web URL
        audiostream (e.g. let user choose)
        subtitle stream (e.g. let user choose)
        Init Kodi Playback (depending on situation):
            start playback
            return PKC listitem attached to result
    """
    result = Playback_Successful()
    listitem = PKC_ListItem()
    item = playqueue.items[pos]
    if item.xml is not None:
        # Got a Plex element
        api = API(item.xml)
        api.setPartNumber(item.part)
        api.CreateListItemFromPlexItem(listitem)
        playutils = PlayUtils(api, item)
        playurl = playutils.getPlayUrl()
    else:
        playurl = item.file
    listitem.setPath(playurl)
    if item.playmethod in ("DirectStream", "DirectPlay"):
        listitem.setSubtitles(api.externalSubs())
    else:
        playutils.audio_subtitle_prefs(listitem)
    listitem.setPath(playurl)
    result.listitem = listitem
    pickle_me(result)

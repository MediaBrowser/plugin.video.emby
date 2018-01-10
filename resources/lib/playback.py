"""
Used to kick off Kodi playback
"""
from logging import getLogger
from threading import Thread, Lock
from urllib import urlencode

from xbmc import Player, getCondVisibility, sleep

from PlexAPI import API
from PlexFunctions import GetPlexMetadata, init_plex_playqueue
import plexdb_functions as plexdb
import playlist_func as PL
import playqueue as PQ
from playutils import PlayUtils
from PKC_listitem import PKC_ListItem
from pickler import pickle_me, Playback_Successful
import json_rpc as js
from utils import window, settings, dialog, language as lang, Lock_Function
import variables as v
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)
LOCKER = Lock_Function(Lock())

###############################################################################


@LOCKER.lockthis
def playback_triage(plex_id=None, plex_type=None, path=None):
    """
    Hit this function for addon path playback, Plex trailers, etc.
    Will setup playback first, then on second call complete playback.

    Returns Playback_Successful() with potentially a PKC_ListItem() attached
    (to be consumed by setResolvedURL)
    """
    LOG.info('playback_triage called with plex_id %s, plex_type %s, path %s',
             plex_id, plex_type, path)
    if not state.AUTHENTICATED:
        LOG.error('Not yet authenticated for PMS, abort starting playback')
        # "Unauthorized for PMS"
        dialog('notification', lang(29999), lang(30017))
        # Don't cause second notification to appear
        return Playback_Successful()
    playqueue = PQ.get_playqueue_from_type(
        v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[plex_type])
    pos = js.get_position(playqueue.playlistid)
    pos = pos if pos != -1 else 0
    LOG.info('playQueue position: %s for %s', pos, playqueue)
    # Have we already initiated playback?
    init_done = True
    try:
        item = playqueue.items[pos]
    except IndexError:
        init_done = False
    else:
        init_done = item.init_done
    # Either init the playback now, or - on 2nd pass - kick off playback
    if init_done is False:
        playback_init(plex_id, path, playqueue)
    else:
        conclude_playback(playqueue, pos)


def playback_init(plex_id, path, playqueue):
    """
    Playback setup. Path is the original path PKC default.py has been called
    with
    """
    contextmenu_play = window('plex_contextplay') == 'true'
    window('plex_contextplay', clear=True)
    xml = GetPlexMetadata(plex_id)
    try:
        xml[0].attrib
    except (IndexError, TypeError, AttributeError):
        LOG.error('Could not get a PMS xml for plex id %s', plex_id)
        # "Play error"
        dialog('notification', lang(29999), lang(30128))
        return
    result = Playback_Successful()
    listitem = PKC_ListItem()
    # Set the original path again so Kodi will return a 2nd time to PKC
    listitem.setPath(path)
    api = API(xml[0])
    plex_type = api.getType()
    size_playlist = playqueue.kodi_pl.size()
    # Can return -1
    start_pos = max(playqueue.kodi_pl.getposition(), 0)
    LOG.info("Playlist size %s", size_playlist)
    LOG.info("Playlist starting position %s", start_pos)
    resume, _ = api.getRuntime()
    trailers = False
    if (plex_type == v.PLEX_TYPE_MOVIE and
            not resume and
            size_playlist < 2 and
            settings('enableCinema') == "true"):
        if settings('askCinema') == "true":
            # "Play trailers?"
            trailers = dialog('yesno', lang(29999), lang(33016))
            trailers = True if trailers else False
        else:
            trailers = True
    # Post to the PMS. REUSE THE PLAYQUEUE!
    xml = init_plex_playqueue(plex_id,
                              xml.attrib.get('librarySectionUUID'),
                              mediatype=plex_type,
                              trailers=trailers)
    if xml is None:
        LOG.error('Could not get a playqueue xml for plex id %s, UUID %s',
                  plex_id, xml.attrib.get('librarySectionUUID'))
        # "Play error"
        dialog('notification', lang(29999), lang(30128))
        return
    playqueue.clear()
    PL.get_playlist_details_from_xml(playqueue, xml)
    stack = _prep_playlist_stack(xml)
    force_playback = False
    if (not getCondVisibility('Window.IsVisible(MyVideoNav.xml)') and
            not getCondVisibility('Window.IsVisible(VideoFullScreen.xml)')):
        LOG.info("Detected playback from widget")
        force_playback = True
    if force_playback is False:
        # Return the listelement for setResolvedURL
        result.listitem = listitem
        pickle_me(result)
        # Wait for the setResolvedUrl to have taken its course - ugly
        sleep(50)
        _process_stack(playqueue, stack)
    else:
        # Need to kickoff playback, not using setResolvedURL
        pickle_me(result)
        _process_stack(playqueue, stack)
        # Need a separate thread because Player won't return in time
        listitem.setProperty('StartOffset', str(resume))
        thread = Thread(target=Player().play,
                        args=(playqueue.kodi_pl, ))
        thread.setDaemon(True)
        thread.start()


def _prep_playlist_stack(xml):
    stack = []
    for item in xml:
        api = API(item)
        with plexdb.Get_Plex_DB() as plex_db:
            plex_dbitem = plex_db.getItem_byId(api.getRatingKey())
        try:
            kodi_id = plex_dbitem[0]
            kodi_type = plex_dbitem[4]
        except TypeError:
            kodi_id = None
            kodi_type = None
        for part_no, _ in enumerate(item[0]):
            api.setPartNumber(part_no)
            if kodi_id is not None:
                # We don't need the URL, item is in the Kodi library
                path = None
                listitem = None
            else:
                # Need to redirect again to PKC to conclude playback
                params = {
                    'mode': 'play',
                    'plex_id': api.getRatingKey(),
                    'plex_type': api.getType()
                }
                path = ('plugin://plugin.video.plexkodiconnect?%s'
                        % (urlencode(params)))
                listitem = api.CreateListItemFromPlexItem()
                api.set_listitem_artwork(listitem)
                listitem.setPath(path)
            stack.append({
                'kodi_id': kodi_id,
                'kodi_type': kodi_type,
                'file': path,
                'xml_video_element': item,
                'listitem': listitem,
                'part_no': part_no
            })
    return stack


def _process_stack(playqueue, stack):
    """
    Takes our stack and adds the items to the PKC and Kodi playqueues.
    This needs to be done AFTER setResolvedURL
    """
    for i, item in enumerate(stack):
        if item['kodi_id'] is not None:
            # Use Kodi id & JSON so we get full artwork
            playlist_item = PL.add_item_to_kodi_playlist(
                playqueue,
                i,
                kodi_id=item['kodi_id'],
                kodi_type=item['kodi_type'],
                xml_video_element=item['xml_video_element'])
        else:
            playlist_item = PL.add_listitem_to_Kodi_playlist(
                playqueue,
                i,
                item['listitem'],
                file=item['file'],
                xml_video_element=item['xml_video_element'])
        playlist_item.part = item['part_no']
        playlist_item.init_done = True


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

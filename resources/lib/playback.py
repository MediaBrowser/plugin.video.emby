"""
Used to kick off Kodi playback
"""
from PlexAPI import API
import playqueue as PQ
from playutils import PlayUtils
from PKC_listitem import PKC_ListItem, convert_PKC_to_listitem
from pickler import Playback_Successful
from utils import settings, dialog, language as lang


def playback_setup(plex_id, kodi_id, kodi_type, path):
    """
    Get XML
        For the single element, e.g. including trailers and parts
        For playQueue (init by Companion or Alexa)
    Set up
        PKC/Kodi/Plex Playqueue
        Trailers
        Clips
        Several parts
        companion playqueue
        Alexa music album

    """
    trailers = False
    if (api.getType() == v.PLEX_TYPE_MOVIE and
            not seektime and
            sizePlaylist < 2 and
            settings('enableCinema') == "true"):
        if settings('askCinema') == "true":
            trailers = dialog('yesno', lang(29999), "Play trailers?")
            trailers = True if trailers else False
        else:
            trailers = True
    # Post to the PMS. REUSE THE PLAYQUEUE!
    xml = init_plex_playqueue(plex_id,
                              plex_lib_UUID,
                              mediatype=api.getType(),
                              trailers=trailers)
    pass


def conclude_playback_startup(playqueue_no,
                              pos,
                              plex_id=None,
                              kodi_id=None,
                              kodi_type=None,
                              path=None):
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
    playqueue = PQ.PLAYQUEUES[playqueue_no]
    item = playqueue.items[pos]
    api = API(item.xml)
    api.setPartNumber(item.part)
    api.CreateListItemFromPlexItem(listitem)
    if plex_id is not None:
        playutils = PlayUtils(api, item)
        playurl = playutils.getPlayUrl()
    elif path is not None:
        playurl = path
        item.playmethod = 'DirectStream'
    listitem.setPath(playurl)
    if item.playmethod in ("DirectStream", "DirectPlay"):
        listitem.setSubtitles(api.externalSubs())
    else:
        playutils.audio_subtitle_prefs(listitem)
    listitem.setPath(playurl)
    result.listitem = listitem
    return result

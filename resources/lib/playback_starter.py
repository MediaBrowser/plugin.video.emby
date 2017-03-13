# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import Thread
from urlparse import parse_qsl

from PKC_listitem import PKC_ListItem
from pickler import pickle_me, Playback_Successful
from playbackutils import PlaybackUtils
from utils import window
from PlexFunctions import GetPlexMetadata
from PlexAPI import API
from playqueue import lock
import variables as v

###############################################################################
log = logging.getLogger("PLEX."+__name__)

###############################################################################


class Playback_Starter(Thread):
    """
    Processes new plays
    """
    def __init__(self, callback=None):
        self.mgr = callback
        self.playqueue = self.mgr.playqueue
        Thread.__init__(self)

    def process_play(self, plex_id, kodi_id=None):
        """
        Processes Kodi playback init for ONE item
        """
        log.info("Process_play called with plex_id %s, kodi_id %s"
                 % (plex_id, kodi_id))
        if window('plex_authenticated') != "true":
            log.error('Not yet authenticated for PMS, abort starting playback')
            # Todo: Warn user with dialog
            return
        xml = GetPlexMetadata(plex_id)
        try:
            xml[0].attrib
        except (IndexError, TypeError, AttributeError):
            log.error('Could not get a PMS xml for plex id %s' % plex_id)
            return
        api = API(xml[0])
        if api.getType() == v.PLEX_TYPE_PHOTO:
            # Photo
            result = Playback_Successful()
            listitem = PKC_ListItem()
            listitem = api.CreateListItemFromPlexItem(listitem)
            api.AddStreamInfo(listitem)
            api.set_listitem_artwork(listitem)
            result.listitem = listitem
        else:
            # Video and Music
            playqueue = self.playqueue.get_playqueue_from_type(
                v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[api.getType()])
            with lock:
                result = PlaybackUtils(xml, playqueue).play(
                    plex_id,
                    kodi_id,
                    xml.attrib.get('librarySectionUUID'))
        log.info('Done process_play, playqueues: %s'
                 % self.playqueue.playqueues)
        return result

    def triage(self, item):
        mode, params = item.split('?', 1)
        params = dict(parse_qsl(params))
        log.debug('Received mode: %s, params: %s' % (mode, params))
        try:
            if mode == 'play':
                result = self.process_play(params.get('id'),
                                           params.get('dbid'))
            elif mode == 'companion':
                result = self.process_companion()
        except:
            log.error('Error encountered for mode %s, params %s'
                      % (mode, params))
            import traceback
            log.error(traceback.format_exc())
            # Let default.py know!
            pickle_me(None)
        else:
            pickle_me(result)

    def run(self):
        queue = self.mgr.monitor_kodi_play.playback_queue
        log.info("----===## Starting Playback_Starter ##===----")
        while True:
            item = queue.get()
            if item is None:
                # Need to shutdown - initiated by monitor_kodi_play
                break
            else:
                self.triage(item)
                queue.task_done()
        log.info("----===## Playback_Starter stopped ##===----")

# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import Thread
from urlparse import parse_qsl

from xbmc import Player

from PKC_listitem import PKC_ListItem
from pickler import pickle_me, Playback_Successful
from playbackutils import PlaybackUtils
from utils import window
from PlexFunctions import GetPlexMetadata
from PlexAPI import API
from playqueue import lock
import variables as v
from downloadutils import DownloadUtils
from PKC_listitem import convert_PKC_to_listitem
import plexdb_functions as plexdb
import state

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
        if not state.AUTHENTICATED:
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

    def process_plex_node(self, url, viewOffset, directplay=False,
                          node=True):
        """
        Called for Plex directories or redirect for playback (e.g. trailers,
        clips, watchlater)
        """
        log.info('process_plex_node called with url: %s, viewOffset: %s'
                 % (url, viewOffset))
        # Plex redirect, e.g. watch later. Need to get actual URLs
        if url.startswith('http') or url.startswith('{server}'):
            xml = DownloadUtils().downloadUrl(url)
        else:
            xml = DownloadUtils().downloadUrl('{server}%s' % url)
        try:
            xml[0].attrib
        except:
            log.error('Could not download PMS metadata')
            return
        if viewOffset != '0':
            try:
                viewOffset = int(v.PLEX_TO_KODI_TIMEFACTOR * float(viewOffset))
            except:
                pass
            else:
                window('plex_customplaylist.seektime', value=str(viewOffset))
                log.info('Set resume point to %s' % str(viewOffset))
        api = API(xml[0])
        typus = v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[api.getType()]
        if node is True:
            plex_id = None
            kodi_id = 'plexnode'
        else:
            plex_id = api.getRatingKey()
            kodi_id = None
            with plexdb.Get_Plex_DB() as plex_db:
                plexdb_item = plex_db.getItem_byId(plex_id)
                try:
                    kodi_id = plexdb_item[0]
                except TypeError:
                    log.info('Couldnt find item %s in Kodi db'
                             % api.getRatingKey())
        playqueue = self.playqueue.get_playqueue_from_type(typus)
        with lock:
            result = PlaybackUtils(xml, playqueue).play(
                plex_id,
                kodi_id=kodi_id,
                plex_lib_UUID=xml.attrib.get('librarySectionUUID'))
        if directplay:
            if result.listitem:
                listitem = convert_PKC_to_listitem(result.listitem)
                Player().play(listitem.getfilename(), listitem)
            return Playback_Successful()
        else:
            return result

    def triage(self, item):
        _, params = item.split('?', 1)
        params = dict(parse_qsl(params))
        mode = params.get('mode')
        log.debug('Received mode: %s, params: %s' % (mode, params))
        try:
            if mode == 'play':
                result = self.process_play(params.get('id'),
                                           params.get('dbid'))
            elif mode == 'companion':
                result = self.process_companion()
            elif mode == 'plex_node':
                result = self.process_plex_node(
                    params.get('key'),
                    params.get('view_offset'),
                    directplay=True if params.get('play_directly') else False,
                    node=False if params.get('node') == 'false' else True)
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
        queue = self.mgr.command_pipeline.playback_queue
        log.info("----===## Starting Playback_Starter ##===----")
        while True:
            item = queue.get()
            if item is None:
                # Need to shutdown - initiated by command_pipeline
                break
            else:
                self.triage(item)
                queue.task_done()
        log.info("----===## Playback_Starter stopped ##===----")

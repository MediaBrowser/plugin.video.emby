# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmc

from ..plex_api import API
from ..plex_db import PlexDB
from .. import backgroundthread
from ..backgroundthread.Queue import Empty
from .. import utils, kodidb_functions as kodidb
from .. import itemtypes, artwork, plex_functions as PF, variables as v, state

###############################################################################

LOG = getLogger('PLEX.library_sync.fanart')

###############################################################################


class ThreadedProcessFanart(backgroundthread.KillableThread):
    """
    Threaded download of additional fanart in the background

    Input:
        queue           Queue.Queue() object that you will need to fill with
                        dicts of the following form:
            {
              'plex_id':                the Plex id as a string
              'plex_type':              the Plex media type, e.g. 'movie'
              'refresh': True/False     if True, will overwrite any 3rd party
                                        fanart. If False, will only get missing
            }
    """
    def __init__(self, queue):
        self.queue = queue
        super(ThreadedProcessFanart, self).__init__()

    def isCanceled(self):
        return xbmc.abortRequested or state.STOP_PKC

    def isSuspended(self):
        return (state.SUSPEND_LIBRARY_THREAD or
                state.DB_SCAN or
                state.STOP_SYNC or
                state.SUSPEND_SYNC)

    def run(self):
        LOG.info('---===### Starting FanartSync ###===---')
        try:
            self._run()
        except:
            utils.ERROR(txt='FanartSync crashed', notify=True)
            raise
        LOG.info('---===### Stopping FanartSync ###===---')

    def _run(self):
        """
        Do the work
        """
        # First run through our already synced items in the Plex DB
        for plex_type in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW):
            with PlexDB() as plexdb:
                for plex_id in plexdb.fanart(plex_type):
                    if self.isCanceled():
                        break
                    while self.isSuspended():
                        if self.isCanceled():
                            break
                        xbmc.sleep(1000)
                    process_item(plexdb, {'plex_id': plex_id,
                                          'plex_type': plex_type,
                                          'refresh': False})

        # Then keep checking the queue for new items
        while not self.isCanceled():
            # In the event the server goes offline
            while self.isSuspended():
                # Set in service.py
                if self.isCanceled():
                    return
                xbmc.sleep(1000)
            # grabs Plex item from queue
            try:
                item = self.queue.get(block=False)
            except Empty:
                xbmc.sleep(1000)
                continue
            self.queue.task_done()
            if isinstance(item, artwork.ArtworkSyncMessage):
                if state.IMAGE_SYNC_NOTIFICATIONS:
                    utils.dialog('notification',
                                 heading=utils.lang(29999),
                                 message=item.message,
                                 icon='{plex}',
                                 sound=False)
                continue
            LOG.debug('Get additional fanart for Plex id %s', item['plex_id'])
            with PlexDB() as plexdb:
                process_item(plexdb, item)


def process_item(plexdb, item):
    done = False
    try:
        artworks = None
        db_item = plexdb.item_by_id(item['plex_id'], item['plex_type'])
        if not db_item:
            LOG.error('Could not get Kodi id for plex id %s, abort getfanart',
                      item['plex_id'])
            return
        if item['refresh'] is False:
            with kodidb.GetKodiDB('video') as kodi_db:
                artworks = kodi_db.get_art(db_item['kodi_id'],
                                           db_item['kodi_type'])
            # Check if we even need to get additional art
            for key in v.ALL_KODI_ARTWORK:
                if key not in artworks:
                    break
            else:
                LOG.debug('Already got all fanart for Plex id %s',
                          item['plex_id'])
                done = True
                return
        xml = PF.GetPlexMetadata(item['plex_id'])
        if xml is None:
            LOG.error('Could not get metadata for %s. Skipping that item '
                      'for now', item['plex_id'])
            return
        elif xml == 401:
            LOG.error('HTTP 401 returned by PMS. Too much strain? '
                      'Cancelling sync for now')
            return
        api = API(xml[0])
        if artworks is None:
            artworks = api.artwork()
        # Get additional missing artwork from fanart artwork sites
        artworks = api.fanart_artwork(artworks)
        with itemtypes.ITEMTYPE_FROM_PLEXTYPE[item['plex_type']] as context:
            context.set_fanart(artworks,
                               db_item['kodi_id'],
                               db_item['kodi_type'])
        # Additional fanart for sets/collections
        if api.plex_type() == v.PLEX_TYPE_MOVIE:
            for _, setname in api.collection_list():
                LOG.debug('Getting artwork for movie set %s', setname)
                with kodidb.GetKodiDB('video') as kodi_db:
                    setid = kodi_db.create_collection(setname)
                external_set_artwork = api.set_artwork()
                if (external_set_artwork and
                        utils.settings('PreferKodiCollectionArt') == 'false'):
                    kodi_artwork = api.artwork(kodi_id=setid,
                                               kodi_type=v.KODI_TYPE_SET)
                    for art in kodi_artwork:
                        if art in external_set_artwork:
                            del external_set_artwork[art]
                with itemtypes.Movie() as movie:
                    movie.artwork.modify_artwork(external_set_artwork,
                                                 setid,
                                                 v.KODI_TYPE_SET,
                                                 movie.kodicursor)
        done = True
    finally:
        if done is True:
            LOG.debug('Done getting fanart for Plex id %s', item['plex_id'])
            plexdb.set_fanart_synced(item['plex_id'], item['plex_type'])

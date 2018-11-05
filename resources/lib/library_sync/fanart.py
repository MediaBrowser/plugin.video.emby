# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmc

from . import common
from ..plex_api import API
from ..plex_db import PlexDB
from .. import backgroundthread, utils, kodidb_functions as kodidb
from .. import itemtypes, plex_functions as PF, variables as v, state


LOG = getLogger('PLEX.sync.fanart')

SUPPORTED_TYPES = (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW)
SYNC_FANART = utils.settings('FanartTV') == 'true'
PREFER_KODI_COLLECTION_ART = utils.settings('PreferKodiCollectionArt') == 'false'


class FanartThread(backgroundthread.KillableThread):
    """
    This will potentially take hours!
    """
    def __init__(self, callback, refresh=False):
        self.callback = callback
        self.refresh = refresh
        super(FanartThread, self).__init__()

    def isCanceled(self):
        return state.STOP_PKC

    def isSuspended(self):
        return state.SUSPEND_LIBRARY_THREAD

    def run(self):
        try:
            self._run_internal()
        except:
            utils.ERROR(notify=True)

    def _run_internal(self):
        LOG.info('Starting FanartThread')
        with PlexDB() as plexdb:
            func = plexdb.every_plex_id if self.refresh else plexdb.missing_fanart
            for typus in SUPPORTED_TYPES:
                for plex_id in func(typus):
                    if self.isCanceled():
                        return
                    if self.isSuspended():
                        if self.isCanceled():
                            return
                        xbmc.sleep(1000)
                    process_fanart(plex_id, typus, self.refresh)
        LOG.info('FanartThread finished')
        self.callback()


class FanartTask(backgroundthread.Task, common.libsync_mixin):
    """
    This task will also be executed while library sync is suspended!
    """
    def setup(self, plex_id, plex_type, refresh=False):
        self.plex_id = plex_id
        self.plex_type = plex_type
        self.refresh = refresh

    def run(self):
        process_fanart(self.plex_id, self.plex_type, self.refresh)


def process_fanart(plex_id, plex_type, refresh=False):
    """
    Will look for additional fanart for the plex_type item with plex_id.
    Will check if we already got all artwork and only look if some are indeed
    missing.
    Will set the fanart_synced flag in the Plex DB if successful.
    """
    done = False
    try:
        artworks = None
        with PlexDB() as plexdb:
            db_item = plexdb.item_by_id(plex_id,
                                        plex_type)
        if not db_item:
            LOG.error('Could not get Kodi id for plex id %s', plex_id)
            return
        if not refresh:
            with kodidb.GetKodiDB('video') as kodi_db:
                artworks = kodi_db.get_art(db_item['kodi_id'],
                                           db_item['kodi_type'])
            # Check if we even need to get additional art
            for key in v.ALL_KODI_ARTWORK:
                if key not in artworks:
                    break
            else:
                done = True
                return
        xml = PF.GetPlexMetadata(plex_id)
        try:
            xml[0].attrib
        except (TypeError, IndexError, AttributeError):
            LOG.warn('Could not get metadata for %s. Skipping that item '
                     'for now', plex_id)
            return
        api = API(xml[0])
        if artworks is None:
            artworks = api.artwork()
        # Get additional missing artwork from fanart artwork sites
        artworks = api.fanart_artwork(artworks)
        with itemtypes.ITEMTYPE_FROM_PLEXTYPE[plex_type](None) as context:
            context.set_fanart(artworks,
                               db_item['kodi_id'],
                               db_item['kodi_type'])
        # Additional fanart for sets/collections
        if plex_type == v.PLEX_TYPE_MOVIE:
            for _, setname in api.collection_list():
                LOG.debug('Getting artwork for movie set %s', setname)
                with kodidb.GetKodiDB('video') as kodi_db:
                    setid = kodi_db.create_collection(setname)
                external_set_artwork = api.set_artwork()
                if external_set_artwork and PREFER_KODI_COLLECTION_ART:
                    kodi_artwork = api.artwork(kodi_id=setid,
                                               kodi_type=v.KODI_TYPE_SET)
                    for art in kodi_artwork:
                        if art in external_set_artwork:
                            del external_set_artwork[art]
                with itemtypes.Movie(None) as movie:
                    movie.artwork.modify_artwork(external_set_artwork,
                                                 setid,
                                                 v.KODI_TYPE_SET,
                                                 movie.kodicursor)
        done = True
    finally:
        if done is True:
            with PlexDB() as plexdb:
                plexdb.set_fanart_synced(plex_id,
                                         plex_type)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import time

from . import common, process_metadata, sections
from .get_metadata import GetMetadataTask
from .. import utils, backgroundthread, playlists, variables as v, state
from .. import plex_functions as PF, itemtypes

LOG = getLogger('PLEX.library_sync.full_sync')


def start(repair, callback):
    """
    """
    # backgroundthread.BGThreader.addTask(FullSync().setup(repair, callback))
    FullSync(repair, callback).start()


class FullSync(backgroundthread.KillableThread, common.libsync_mixin):
    def __init__(self, repair, callback):
        """
        repair=True: force sync EVERY item
        """
        self.repair = repair
        self.callback = callback
        self.queue = None
        self.process_thread = None
        self.last_sync = None
        self.plex_db = None
        super(FullSync, self).__init__()

    def process_item(self, xml_item, get_children):
        """
        Processes a single library item
        """
        plex_id = int(xml_item['ratingKey'])
        if self.new_items_only:
            if self.plex_db.check_plexid(plex_id) is None:
                backgroundthread.BGThreader.addTask(
                    GetMetadataTask().setup(self.queue,
                                            plex_id,
                                            get_children))
        else:
            if self.plex_db.check_checksum(
                    int('%s%s' % (xml_item['ratingKey'],
                                  xml_item['updatedAt']))) is None:
                backgroundthread.BGThreader.addTask(
                    GetMetadataTask().setup(self.queue,
                                            plex_id,
                                            get_children))
            else:
                self.plex_db.update_last_sync(plex_id, self.last_sync)

    @utils.log_time
    def process_kind(self, kind):
        """
        kind is a tuple: (<name as unicode>,
                          kodi_type,
                          <itemtype class>,
                          get_children)
        """
        LOG.debug('Start processing %s', kind[0])
        sections = (x for x in sections.SECTIONS if x['kodi_type'] == kind[1])
        for section in sections:
            LOG.debug('Processing library section %s', section)
            if self.isCanceled():
                return False
            if not self.install_sync_done:
                state.PATH_VERIFIED = False
            try:
                iterator = PF.PlexSectionItems(section['id'])
                # Tell the processing thread about this new section
                queue_info = process_metadata.InitNewSection(
                    kind[2],
                    utils.cast(int, iterator.get('totalSize', 0)),
                    utils.cast(unicode, iterator.get('librarySectionTitle')),
                    section['id'])
                self.queue.put(queue_info)
                for xml_item in iterator:
                    if self.isCanceled():
                        return False
                    self.process_item(xml_item, kind[3])
            except RuntimeError:
                LOG.error('Could not entirely process section %s', section)
                continue
        LOG.debug('Finished processing %s', kind[0])
        return True

    def full_library_sync(self, new_items_only=False):
        """
        """
        process = [self.plex_movies, self.plex_tv_show]
        if state.ENABLE_MUSIC:
            process.append(self.plex_music)
        self.queue = backgroundthread.Queue.Queue(maxsize=200)
        t = process_metadata.ProcessMetadata(self.queue, self.last_sync)
        t.start()
        kinds = [
            ('movies', v.KODI_TYPE_MOVIE, itemtypes.Movie, False),
            ('tv shows', v.KODI_TYPE_SHOW, itemtypes.Show, False),
            ('tv seasons', v.KODI_TYPE_SEASON, itemtypes.Season, False),
            ('tv shows', v.KODI_TYPE_SHOW, itemtypes.Show, False),
        ]
        try:
            for kind in kinds:
                if self.isCanceled() or not self.process_kind(kind):
                    return False

            # Let kodi update the views in any case, since we're doing a full sync
            common.update_kodi_library(video=True, music=state.ENABLE_MUSIC)

            if utils.window('plex_scancrashed') == 'true':
                # Show warning if itemtypes.py crashed at some point
                utils.messageDialog(utils.lang(29999), utils.lang(39408))
                utils.window('plex_scancrashed', clear=True)
            elif utils.window('plex_scancrashed') == '401':
                utils.window('plex_scancrashed', clear=True)
                if state.PMS_STATUS not in ('401', 'Auth'):
                    # Plex server had too much and returned ERROR
                    utils.messageDialog(utils.lang(29999), utils.lang(39409))
        finally:
            # Last element will kill the processing thread
            self.queue.put(None)
        return True

    @utils.log_time
    def run(self):
        successful = False
        self.last_sync = time.time()
        try:
            if self.isCanceled():
                return
            LOG.info('Running fullsync for NEW PMS items with repair=%s',
                     self.repair)
            if not sections.sync_from_pms():
                return
            if self.isCanceled():
                return
            # This will also update playstates and userratings!
            if self.full_library_sync(new_items_only=True) is False:
                return
            if self.isCanceled():
                return
            # This will NOT update playstates and userratings!
            LOG.info('Running fullsync for CHANGED PMS items with repair=%s',
                     self.repair)
            if not self.full_library_sync():
                return
            if self.isCanceled():
                return
            if PLAYLIST_SYNC_ENABLED and not playlists.full_sync():
                return
            successful = True
        except:
            utils.ERROR(txt='full_sync.py crashed', notify=True)
        finally:
            self.callback(successful)


def process_updatelist(item_class, show_sync_info=True):
    """
    Downloads all XMLs for item_class (e.g. Movies, TV-Shows). Processes
    them by then calling item_classs.<item_class>()

    Input:
        item_class:             'Movies', 'TVShows' (itemtypes.py classes)
    """
    search_fanart = (item_class in ('Movies', 'TVShows') and
                     utils.settings('FanartTV') == 'true')
    LOG.debug("Starting sync threads")
    # Spawn GetMetadata threads for downloading
    for _ in range(state.SYNC_THREAD_NUMBER):
        thread = get_metadata.ThreadedGetMetadata(DOWNLOAD_QUEUE,
                                                  PROCESS_QUEUE)
        thread.start()
        THREADS.append(thread)
    LOG.debug("%s download threads spawned", state.SYNC_THREAD_NUMBER)
    # Spawn one more thread to process Metadata, once downloaded
    thread = process_metadata.ThreadedProcessMetadata(PROCESS_QUEUE,
                                                      item_class)
    thread.start()
    THREADS.append(thread)
    # Start one thread to show sync progress ONLY for new PMS items
    if show_sync_info:
        sync_info.GET_METADATA_COUNT = 0
        sync_info.PROCESS_METADATA_COUNT = 0
        sync_info.PROCESSING_VIEW_NAME = ''
        thread = sync_info.ThreadedShowSyncInfo(item_number, item_class)
        thread.start()
        THREADS.append(thread)
    # Process items we need to download
    for _ in generator:
        DOWNLOAD_QUEUE.put(self.updatelist.pop(0))
        if search_fanart:
            pass
    # Wait until finished
    DOWNLOAD_QUEUE.join()
    PROCESS_QUEUE.join()
    # Kill threads
    LOG.debug("Waiting to kill threads")
    for thread in THREADS:
        # Threads might already have quit by themselves (e.g. Kodi exit)
        try:
            thread.stop()
        except AttributeError:
            pass
    LOG.debug("Stop sent to all threads")
    # Wait till threads are indeed dead
    for thread in threads:
        try:
            thread.join(1.0)
        except AttributeError:
            pass
    LOG.debug("Sync threads finished")

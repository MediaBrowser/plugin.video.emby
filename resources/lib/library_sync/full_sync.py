#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import Queue
import copy

from cProfile import Profile
from pstats import Stats
from StringIO import StringIO

from .get_metadata import GetMetadataTask, reset_collections
from .process_metadata import InitNewSection, UpdateLastSyncAndPlaystate, \
    ProcessMetadata, DeleteItem
from . import common, sections
from .. import utils, timing, backgroundthread, variables as v, app
from .. import plex_functions as PF, itemtypes
from ..plex_db import PlexDB

if (v.PLATFORM != 'Microsoft UWP' and
        utils.settings('enablePlaylistSync') == 'true'):
    # Xbox cannot use watchdog, a dependency for PKC playlist features
    from .. import playlists
    PLAYLIST_SYNC_ENABLED = True
else:
    PLAYLIST_SYNC_ENABLED = False

LOG = getLogger('PLEX.sync.full_sync')


class FullSync(common.libsync_mixin):
    def __init__(self, repair, callback, show_dialog):
        """
        repair=True: force sync EVERY item
        """
        self._canceled = False
        self.repair = repair
        self.callback = callback
        self.show_dialog = show_dialog
        self.queue = None
        self.process_thread = None
        self.current_sync = None
        self.plexdb = None
        self.plex_type = None
        self.section_type = None
        self.processing_thread = None
        self.install_sync_done = utils.settings('SyncInstallRunDone') == 'true'
        self.threader = backgroundthread.ThreaderManager(
            worker=backgroundthread.NonstoppingBackgroundWorker)
        super(FullSync, self).__init__()

    def process_item(self, xml_item):
        """
        Processes a single library item
        """
        plex_id = int(xml_item.get('ratingKey'))
        if not self.repair and self.plexdb.checksum(plex_id, self.plex_type) == \
                int('%s%s' % (plex_id,
                              xml_item.get('updatedAt',
                                           xml_item.get('addedAt', 1541572987)))):
            # Already got EXACTLY this item in our DB. BUT need to collect all
            # DB updates within the same thread
            self.queue.put(UpdateLastSyncAndPlaystate(plex_id, xml_item))
            return
        task = GetMetadataTask()
        task.setup(self.queue, plex_id, self.plex_type, self.get_children)
        self.threader.addTask(task)

    def process_delete(self):
        """
        Removes all the items that have NOT been updated (last_sync timestamp
        is different)
        """
        for plex_id in self.plexdb.plex_id_by_last_sync(self.plex_type,
                                                        self.current_sync):
            if self.isCanceled():
                return
            self.queue.put(DeleteItem(plex_id))

    @utils.log_time
    def process_section(self, section):
        LOG.debug('Processing library section %s', section)
        if self.isCanceled():
            return False
        if not self.install_sync_done:
            app.SYNC.path_verified = False
        try:
            # Sync new, updated and deleted items
            iterator = section['iterator']
            # Tell the processing thread about this new section
            queue_info = InitNewSection(section['context'],
                                        iterator.total,
                                        iterator.get('librarySectionTitle'),
                                        section['section_id'],
                                        section['plex_type'])
            self.queue.put(queue_info)
            with PlexDB() as self.plexdb:
                for xml_item in iterator:
                    if self.isCanceled():
                        return False
                    self.process_item(xml_item)
        except RuntimeError:
            LOG.error('Could not entirely process section %s', section)
            return False
        LOG.debug('Waiting for download threads to finish')
        while self.threader.threader.working():
            app.APP.monitor.waitForAbort(0.1)
        reset_collections()
        try:
            # Tell the processing thread that we're syncing playstate
            queue_info = InitNewSection(section['context'],
                                        iterator.total,
                                        iterator.get('librarySectionTitle'),
                                        section['section_id'],
                                        section['plex_type'])
            self.queue.put(queue_info)
            LOG.debug('Waiting for processing thread to finish section')
            # Make sure that the processing thread commits all changes
            self.queue.join()
            with PlexDB() as self.plexdb:
                # Delete movies that are not on Plex anymore
                LOG.debug('Look for items to delete')
                self.process_delete()
            # Wait again till the processing thread is done
            self.queue.join()
        except RuntimeError:
            LOG.error('Could not process playstate for section %s', section)
            return False
        LOG.debug('Done processing playstate for section')
        return True

    def threaded_get_iterators(self, kinds, queue):
        """
        PF.SectionItems is costly, so let's do it asynchronous
        """
        try:
            for kind in kinds:
                for section in (x for x in sections.SECTIONS
                                if x['plex_type'] == kind[1]):
                    if self.isCanceled():
                        return
                    element = copy.deepcopy(section)
                    element['section_type'] = element['plex_type']
                    element['plex_type'] = kind[0]
                    element['element_type'] = kind[1]
                    element['context'] = kind[2]
                    element['get_children'] = kind[3]
                    element['iterator'] = PF.SectionItems(section['section_id'],
                                                          plex_type=kind[0])
                    queue.put(element)
        finally:
            queue.put(None)

    def full_library_sync(self):
        """
        """
        kinds = [
            (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_MOVIE, itemtypes.Movie, False),
            (v.PLEX_TYPE_SHOW, v.PLEX_TYPE_SHOW, itemtypes.Show, False),
            (v.PLEX_TYPE_SEASON, v.PLEX_TYPE_SHOW, itemtypes.Season, False),
            (v.PLEX_TYPE_EPISODE, v.PLEX_TYPE_SHOW, itemtypes.Episode, False)
        ]
        if app.SYNC.enable_music:
            kinds.extend([
                (v.PLEX_TYPE_ARTIST, v.PLEX_TYPE_ARTIST, itemtypes.Artist, False),
                (v.PLEX_TYPE_ALBUM, v.PLEX_TYPE_ARTIST, itemtypes.Album, True),
            ])
        # Already start setting up the iterators. We need to enforce
        # syncing e.g. show before season before episode
        iterator_queue = Queue.Queue()
        task = backgroundthread.FunctionAsTask(self.threaded_get_iterators,
                                               None,
                                               kinds,
                                               iterator_queue)
        backgroundthread.BGThreader.addTask(task)
        while True:
            section = iterator_queue.get()
            if section is None:
                break
            # Setup our variables
            self.plex_type = section['plex_type']
            self.section_type = section['section_type']
            self.context = section['context']
            self.get_children = section['get_children']
            # Now do the heavy lifting
            if self.isCanceled() or not self.process_section(section):
                return False
            iterator_queue.task_done()
        return True

    @utils.log_time
    def run(self):
        profile = Profile()
        profile.enable()
        if self.isCanceled():
            return
        successful = False
        self.current_sync = timing.unix_timestamp()
        # Delete playlist and video node files from Kodi
        utils.delete_playlists()
        utils.delete_nodes()
        # Get latest Plex libraries and build playlist and video node files
        if not sections.sync_from_pms():
            return
        try:
            # Fire up our single processing thread
            self.queue = backgroundthread.Queue.Queue(maxsize=1000)
            self.processing_thread = ProcessMetadata(self.queue,
                                                     self.current_sync,
                                                     self.show_dialog)
            self.processing_thread.start()

            # Actual syncing - do only new items first
            LOG.info('Running full_library_sync with repair=%s',
                     self.repair)
            if not self.full_library_sync():
                return
            # Tell the processing thread to exit with one last element None
            self.queue.put(None)
            if self.isCanceled():
                return
            if PLAYLIST_SYNC_ENABLED and not playlists.full_sync():
                return
            successful = True
        except:
            utils.ERROR(txt='full_sync.py crashed', notify=True)
        finally:
            # This will block until the processing thread really exits
            LOG.debug('Waiting for processing thread to exit')
            self.processing_thread.join()
            common.update_kodi_library(video=True, music=True)
            self.threader.shutdown()
            if self.callback:
                self.callback(successful)
            LOG.info('Done full_sync')
            profile.disable()
            string_io = StringIO()
            stats = Stats(profile, stream=string_io).sort_stats('cumulative')
            stats.print_stats()
            LOG.info('cProfile result: ')
            LOG.info(string_io.getvalue())


def start(show_dialog, repair=False, callback=None):
    """
    """
    # FullSync(repair, callback, show_dialog).start()
    FullSync(repair, callback, show_dialog).run()

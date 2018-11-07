#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .get_metadata import GetMetadataTask
from . import common, process_metadata, sections
from .. import utils, backgroundthread, variables as v, state
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
            # Already got EXACTLY this item in our DB
            self.plexdb.update_last_sync(plex_id,
                                         self.plex_type,
                                         self.current_sync)
            return
        task = GetMetadataTask()
        task.setup(self.queue, plex_id, self.get_children)
        self.threader.addTask(task)

    def process_delete(self):
        """
        Removes all the items that have NOT been updated (last_sync timestamp
        is different)
        """
        with self.context(self.current_sync) as c:
            for plex_id in self.plexdb.plex_id_by_last_sync(self.plex_type,
                                                            self.current_sync):
                if self.isCanceled():
                    return
                c.remove(plex_id, plex_type=self.plex_type)

    @utils.log_time
    def process_playstate(self, iterator):
        """
        Updates the playstate (resume point, number of views, userrating, last
        played date, etc.) for all elements in the (xml-)iterator
        """
        with self.context(self.current_sync) as c:
            for xml_item in iterator:
                if self.isCanceled():
                    return False
                c.update_userdata(xml_item, self.plex_type)

    @utils.log_time
    def process_kind(self):
        """
        """
        successful = True
        LOG.debug('Start processing %ss', self.section_type)
        sects = (x for x in sections.SECTIONS
                 if x['plex_type'] == self.section_type)
        for section in sects:
            LOG.debug('Processing library section %s', section)
            if self.isCanceled():
                return False
            if not self.install_sync_done:
                state.PATH_VERIFIED = False
            try:
                # Sync new, updated and deleted items
                iterator = PF.SectionItems(section['section_id'],
                                           plex_type=self.plex_type)
                # Tell the processing thread about this new section
                queue_info = process_metadata.InitNewSection(
                    self.context,
                    utils.cast(int, iterator.get('totalSize', 0)),
                    iterator.get('librarySectionTitle'),
                    section['section_id'])
                self.queue.put(queue_info)
                with PlexDB() as self.plexdb:
                    for xml_item in iterator:
                        if self.isCanceled():
                            return False
                        self.process_item(xml_item)
            except RuntimeError:
                LOG.error('Could not entirely process section %s', section)
                successful = False
                continue
            LOG.debug('Waiting for processing thread to finish section')
            self.queue.join()
            try:
                # Sync playstate of every item
                iterator = PF.SectionItems(section['section_id'],
                                           plex_type=self.plex_type)
                # Tell the processing thread that we're syncing playstate
                queue_info = process_metadata.InitNewSection(
                    self.context,
                    utils.cast(int, iterator.get('totalSize', 0)),
                    iterator.get('librarySectionTitle'),
                    section['section_id'])
                self.queue.put(queue_info)
                # Ensure that the DB connection is closed to commit the
                # changes above - avoids "Item not yet synced" error
                self.queue.join()
                self.process_playstate(iterator)
            except RuntimeError:
                LOG.error('Could not process playstate for section %s', section)
                successful = False
                continue
            LOG.debug('Done processing playstate for section')

        LOG.debug('Finished processing %ss', self.plex_type)
        return successful

    def full_library_sync(self):
        """
        """
        kinds = [
            (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_MOVIE, itemtypes.Movie, False),
            (v.PLEX_TYPE_SHOW, v.PLEX_TYPE_SHOW, itemtypes.Show, False),
            (v.PLEX_TYPE_SEASON, v.PLEX_TYPE_SHOW, itemtypes.Season, False),
            (v.PLEX_TYPE_EPISODE, v.PLEX_TYPE_SHOW, itemtypes.Episode, False)
        ]
        if state.ENABLE_MUSIC:
            kinds.extend([
                (v.PLEX_TYPE_ARTIST, v.PLEX_TYPE_ARTIST, itemtypes.Artist, False),
                (v.PLEX_TYPE_ALBUM, v.PLEX_TYPE_ARTIST, itemtypes.Album, True),
            ])
        with PlexDB() as self.plexdb:
            for kind in kinds:
                # Setup our variables
                self.plex_type = kind[0]
                self.section_type = kind[1]
                self.context = kind[2]
                self.get_children = kind[3]
                # Now do the heavy lifting
                if self.isCanceled() or not self.process_kind():
                    return False
                # Delete movies that are not on Plex anymore
                self.process_delete()
        return True

    @utils.log_time
    def run(self):
        if self.isCanceled():
            return
        successful = False
        self.current_sync = utils.unix_timestamp()
        # Delete playlist and video node files from Kodi
        utils.delete_playlists()
        utils.delete_nodes()
        # Get latest Plex libraries and build playlist and video node files
        if not sections.sync_from_pms():
            return
        try:
            # Fire up our single processing thread
            self.queue = backgroundthread.Queue.Queue(maxsize=400)
            self.processing_thread = process_metadata.ProcessMetadata(
                self.queue, self.current_sync, self.show_dialog)
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


def start(show_dialog, repair=False, callback=None):
    """
    """
    # FullSync(repair, callback, show_dialog).start()
    FullSync(repair, callback, show_dialog).run()

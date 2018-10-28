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


LOG = getLogger('PLEX.library_sync.full_sync')


class FullSync(backgroundthread.KillableThread, common.libsync_mixin):
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
        self.last_sync = None
        self.plexdb = None
        self.plex_type = None
        self.processing_thread = None
        self.install_sync_done = utils.settings('SyncInstallRunDone') == 'true'
        super(FullSync, self).__init__()

    def plex_update_watched(self, viewId, item_class, lastViewedAt=None,
                            updatedAt=None):
        """
        YET to implement

        Updates plex elements' view status ('watched' or 'unwatched') and
        also updates resume times.
        This is done by downloading one XML for ALL elements with viewId
        """
        if self.new_items_only is False:
            # Only do this once for fullsync: the first run where new items are
            # added to Kodi
            return
        xml = PF.GetAllPlexLeaves(viewId,
                                  lastViewedAt=lastViewedAt,
                                  updatedAt=updatedAt)
        # Return if there are no items in PMS reply - it's faster
        try:
            xml[0].attrib
        except (TypeError, AttributeError, IndexError):
            LOG.error('Error updating watch status. Could not get viewId: '
                      '%s of item_class %s with lastViewedAt: %s, updatedAt: '
                      '%s', viewId, item_class, lastViewedAt, updatedAt)
            return

        if item_class in ('Movies', 'TVShows'):
            self.update_kodi_video_library = True
        elif item_class == 'Music':
            self.update_kodi_music_library = True
        with getattr(itemtypes, item_class)() as itemtype:
            itemtype.updateUserdata(xml)

    def process_item(self, xml_item):
        """
        Processes a single library item
        """
        plex_id = int(xml_item.get('ratingKey'))
        if self.new_items_only:
            if self.plexdb.is_recorded(plex_id, self.plex_type):
                return
        else:
            if self.plexdb.check_checksum(
                    int('%s%s' % (plex_id,
                                  xml_item.get('updatedAt')))):
                self.plexdb.update_last_sync(plex_id, self.last_sync)
                return
        task = GetMetadataTask()
        task.setup(self.queue, plex_id, self.get_children)
        backgroundthread.BGThreader.addTask(task)

    def process_delete(self):
        """
        Removes all the items that have NOT been updated (last_sync timestamp)
        is different
        """
        with self.context(self.last_sync) as c:
            for plex_id in self.plexdb.plex_id_by_last_sync(self.plex_type,
                                                            self.last_sync):
                if self.isCanceled():
                    return
                c.remove(plex_id, plex_type=self.plex_type)

    @utils.log_time
    def process_kind(self):
        """
        """
        LOG.debug('Start processing %ss', self.plex_type)
        sects = (x for x in sections.SECTIONS
                 if x['plex_type'] == self.plex_type)
        for section in sects:
            LOG.debug('Processing library section %s', section)
            if self.isCanceled():
                return False
            if not self.install_sync_done:
                state.PATH_VERIFIED = False
            try:
                iterator = PF.SectionItems(section['section_id'],
                                           {'type': self.plex_type})
                # Tell the processing thread about this new section
                queue_info = process_metadata.InitNewSection(
                    self.context,
                    utils.cast(int, iterator.get('totalSize', 0)),
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
                continue
            self.queue.join()

        LOG.debug('Finished processing %ss', self.plex_type)
        return True

    def full_library_sync(self):
        """
        """
        kinds = [
            (v.PLEX_TYPE_MOVIE, itemtypes.Movie, False),
            (v.PLEX_TYPE_SHOW, itemtypes.Show, False),
            (v.PLEX_TYPE_SEASON, itemtypes.Season, False),
            (v.PLEX_TYPE_EPISODE, itemtypes.Episode, False)
        ]
        if state.ENABLE_MUSIC:
            kinds.extend([
                (v.PLEX_TYPE_ARTIST, itemtypes.Artist, False),
                (v.PLEX_TYPE_ALBUM, itemtypes.Album, True),
                (v.PLEX_TYPE_SONG, itemtypes.Song, False)])
        with PlexDB() as self.plexdb:
            for kind in kinds:
                # Setup our variables
                self.plex_type = kind[0]
                self.context = kind[1]
                self.get_children = kind[2]
                # Now do the heavy lifting
                if self.isCanceled() or not self.process_kind():
                    return False
                if self.new_items_only:
                    # Delete movies that are not on Plex anymore - do this only once
                    self.process_delete()
        return True

    @utils.log_time
    def run(self):
        if self.isCanceled():
            return
        successful = False
        self.last_sync = utils.unix_timestamp()
        # Delete playlist and video node files from Kodi
        utils.delete_playlists()
        utils.delete_nodes()
        # Get latest Plex libraries and build playlist and video node files
        if not sections.sync_from_pms():
            return
        try:
            # Fire up our single processing thread
            self.queue = backgroundthread.Queue.Queue(maxsize=200)
            self.processing_thread = process_metadata.ProcessMetadata(
                self.queue, self.last_sync, self.show_dialog)
            self.processing_thread.start()

            # Actual syncing - do only new items first
            LOG.info('Running fullsync for **NEW** items with repair=%s',
                     self.repair)
            self.new_items_only = True
            # This will also update playstates and userratings!
            if not self.full_library_sync():
                return
            if self.isCanceled():
                return
            # This will NOT update playstates and userratings!
            LOG.info('Running fullsync for **CHANGED** items with repair=%s',
                     self.repair)
            self.new_items_only = False
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
            # Last element will kill the processing thread (if not already
            # done so, e.g. quitting Kodi)
            self.queue.put(None)
            # This will block until the processing thread exits
            LOG.debug('Waiting for processing thread to exit')
            self.processing_thread.join()
            if self.callback:
                self.callback(successful)
            LOG.info('Done full_sync')


def start(show_dialog, repair=False, callback=None):
    """
    """
    # backgroundthread.BGThreader.addTask(FullSync().setup(repair, callback))
    FullSync(repair, callback, show_dialog).start()

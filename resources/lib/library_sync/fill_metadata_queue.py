# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from . import common
from ..plex_db import PlexDB
from .. import backgroundthread, app

LOG = getLogger('PLEX.sync.fill_metadata_queue')


class FillMetadataQueue(common.LibrarySyncMixin,
                        backgroundthread.KillableThread, ):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the queue with the downloaded etree XML objects. Will use a COPIED
    plex.db file (plex-copy.db) in order to read much faster without the
    writing thread stalling
    """
    def __init__(self, repair, section_queue, get_metadata_queue):
        self.repair = repair
        self.section_queue = section_queue
        self.get_metadata_queue = get_metadata_queue
        super(FillMetadataQueue, self).__init__()

    def _process_section(self, section):
        # Initialize only once to avoid loosing the last value before we're
        # breaking the for loop
        LOG.debug('Process section %s with %s items',
                  section, section.number_of_items)
        count = 0
        with PlexDB(lock=False, copy=True) as plexdb:
            for xml in section.iterator:
                if self.should_cancel():
                    break
                plex_id = int(xml.get('ratingKey'))
                checksum = int('{}{}'.format(
                    plex_id,
                    xml.get('updatedAt',
                            xml.get('addedAt', '1541572987'))))
                if (not self.repair and
                        plexdb.checksum(plex_id, section.plex_type) == checksum):
                    continue
                self.get_metadata_queue.put((count, plex_id, section))
                count += 1
        # We might have received LESS items from the PMS than anticipated.
        # Ensures that our queues finish
        section.number_of_items = count

    def run(self):
        LOG.debug('Starting %s thread', self.__class__.__name__)
        app.APP.register_thread(self)
        try:
            while not self.should_cancel():
                section = self.section_queue.get()
                self.section_queue.task_done()
                if section is None:
                    break
                self._process_section(section)
        except Exception:
            from .. import utils
            utils.ERROR(notify=True)
        finally:
            # Signal the download metadata threads to stop with a sentinel
            self.get_metadata_queue.put(None)
            app.APP.deregister_thread(self)
            LOG.debug('##===---- %s Stopped ----===##', self.__class__.__name__)

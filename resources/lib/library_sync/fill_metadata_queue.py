# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import Queue
from collections import deque

from . import common
from ..plex_db import PlexDB
from .. import backgroundthread, app

LOG = getLogger('PLEX.sync.fill_metadata_queue')


def batch_sizes():
    """
    Increase batch sizes in order to get download threads for an items xml
    metadata started soon. Corresponds to batch sizes when downloading lists
    of items from the PMS ('limitindex' in the PKC settings)
    """
    for i in (50, 100, 200, 400):
        yield i
    while True:
        yield 1000


class FillMetadataQueue(common.LibrarySyncMixin,
                        backgroundthread.KillableThread, ):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the queue with the downloaded etree XML objects

    Input:
        queue               Queue.Queue() object where this thread will store
                            the downloaded metadata XMLs as etree objects
    """
    def __init__(self, repair, section_queue, get_metadata_queue):
        self.repair = repair
        self.section_queue = section_queue
        self.get_metadata_queue = get_metadata_queue
        self.count = 0
        self.batch_size = batch_sizes()
        super(FillMetadataQueue, self).__init__()

    def _loop(self, section, items):
        while items and not self.should_cancel():
            try:
                with PlexDB(lock=False) as plexdb:
                    while items and not self.should_cancel():
                        last, plex_id, checksum = items.popleft()
                        if (not self.repair and
                                plexdb.checksum(plex_id, section.plex_type) == checksum):
                            continue
                        if last:
                            # We might have received LESS items from the PMS
                            # than anticipated. Ensures that our queues finish
                            section.number_of_items = self.count + 1
                        self.get_metadata_queue.put((self.count, plex_id, section),
                                                    block=False)
                        self.count += 1
            except Queue.Full:
                # Close the DB for speed!
                LOG.debug('Queue full')
                self.sleep(5)
                while not self.should_cancel():
                    try:
                        self.get_metadata_queue.put((self.count, plex_id, section),
                                                    block=False)
                    except Queue.Full:
                        LOG.debug('Queue fuller')
                        self.sleep(2)
                    else:
                        self.count += 1
                        break

    def _process_section(self, section):
        # Initialize only once to avoid loosing the last value before we're
        # breaking the for loop
        iterator = common.tag_last(section.iterator)
        last = True
        self.count = 0
        while not self.should_cancel():
            batch_size = next(self.batch_size)
            LOG.debug('Process batch of size %s with count %s for section %s',
                      batch_size, self.count, section)
            # Iterator will block for download - let's not do that when the
            # DB connection is open
            items = deque()
            for i, (last, xml) in enumerate(iterator):
                plex_id = int(xml.get('ratingKey'))
                checksum = int('{}{}'.format(
                    plex_id,
                    xml.get('updatedAt',
                            xml.get('addedAt', '1541572987'))))
                items.append((last, plex_id, checksum))
                if i == batch_size:
                    break
            self._loop(section, items)
            if last:
                break

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

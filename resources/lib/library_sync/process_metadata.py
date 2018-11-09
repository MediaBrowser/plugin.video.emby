# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmcgui

from . import common
from .. import backgroundthread, utils

LOG = getLogger('PLEX.sync.process_metadata')


class InitNewSection(object):
    """
    Throw this into the queue used for ProcessMetadata to tell it which
    Plex library section we're looking at

    context: itemtypes.Movie, itemtypes.Episode, etc.
    """
    def __init__(self, context, total_number_of_items, section_name,
                 section_id):
        self.context = context
        self.total = total_number_of_items
        self.name = section_name
        self.id = section_id


class ProcessMetadata(backgroundthread.KillableThread, common.libsync_mixin):
    """
    Not yet implemented for more than 1 thread - if ever. Only to be called by
    ONE thread!
    Processes the XML metadata in the queue

    Input:
        queue:      Queue.Queue() object that you'll need to fill up with
                    the downloaded XML eTree objects
        item_class: as used to call functions in itemtypes.py e.g. 'Movies' =>
                    itemtypes.Movies()
    """
    def __init__(self, queue, last_sync, show_dialog):
        self._canceled = False
        self.queue = queue
        self.last_sync = last_sync
        self.show_dialog = show_dialog
        self.total = 0
        self.current = 0
        self.title = None
        self.section_name = None
        self.dialog = None
        super(ProcessMetadata, self).__init__()

    def update_progressbar(self):
        if self.show_dialog:
            try:
                progress = int(float(self.current) / float(self.total) * 100.0)
            except ZeroDivisionError:
                progress = 0
            self.dialog.update(progress,
                               self.section_name,
                               '%s/%s: %s'
                               % (self.current + 1, self.total, self.title))

    def run(self):
        """
        Do the work
        """
        LOG.debug('Processing thread started')
        if self.show_dialog:
            self.dialog = xbmcgui.DialogProgressBG()
            self.dialog.create(utils.lang(39714))
        try:
            # Init with the very first library section. This will block!
            section = self.queue.get()
            self.queue.task_done()
            if section is None:
                return
            while not self.isCanceled():
                if section is None:
                    break
                self.current = 0
                self.total = section.total
                self.section_name = section.name
                with section.context(self.last_sync) as context:
                    while not self.isCanceled():
                        # grabs item from queue. This will block!
                        item = self.queue.get()
                        if isinstance(item, InitNewSection) or item is None:
                            section = item
                            break
                        try:
                            context.add_update(item['xml'][0],
                                               section_name=section.name,
                                               section_id=section.id,
                                               children=item['children'])
                        except:
                            utils.ERROR(txt='process_metadata crashed',
                                        notify=True,
                                        cancel_sync=True)
                        self.title = item['xml'][0].get('title')
                        self.update_progressbar()
                        self.current += 1
                        if self.current % 200 == 0:
                            context.plexconn.commit()
                            context.kodiconn.commit()
                        self.queue.task_done()
                self.queue.task_done()
        finally:
            if self.dialog:
                self.dialog.close()
            while not self.queue.empty():
                # We need to empty the queue to let full_sync finish join()
                self.queue.get()
                self.queue.task_done()
            LOG.debug('Processing thread terminated')

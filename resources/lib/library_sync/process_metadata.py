# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmc
import xbmcgui

from . import common
from .. import utils, backgroundthread

LOG = getLogger('PLEX.library_sync.process_metadata')


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
    def __init__(self, queue, context, total_number_of_items):
        self.queue = queue
        self.context = context
        self.total = total_number_of_items
        self.current = 0
        self.title = None
        super(ProcessMetadata, self).__init__()

    def update_dialog(self):
        """
        """
        try:
            progress = int(float(self.current) / float(self.total) * 100.0)
        except ZeroDivisionError:
            progress = 0
        self.dialog.update(progress,
                           utils.lang(29999),
                           '%s/%s: %s'
                           % (self.current, self.total, self.title))

    def run(self):
        """
        Do the work
        """
        LOG.debug('Processing thread started')
        self.dialog = xbmcgui.DialogProgressBG()
        self.dialog.create(utils.lang(39714))
        with self.context() as context:
            while self.isCanceled() is False:
                # grabs item from queue
                try:
                    xml = self.queue.get(block=False)
                except backgroundthread.Queue.Empty:
                    xbmc.sleep(10)
                    continue
                self.queue.task_done()
                if xml is None:
                    break
                try:
                    if xml.children is not None:
                        context.add_update(xml[0],
                                           viewtag=xml['view_name'],
                                           viewid=xml['view_id'],
                                           children=xml['children'])
                    else:
                        context.add_update(xml[0],
                                           viewtag=xml['view_name'],
                                           viewid=xml['view_id'])
                except:
                    utils.ERROR(txt='process_metadata crashed', notify=True)
                self.current += 1
                if self.current % 20 == 0:
                    self.title = utils.cast(unicode, xml[0].get('title'))
                    self.update_dialog()
        self.dialog.close()
        LOG.debug('Processing thread terminated')

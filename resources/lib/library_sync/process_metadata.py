# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmcgui

from . import common
from .. import backgroundthread, utils, variables as v

LOG = getLogger('PLEX.library_sync.process_metadata')


class InitNewSection(object):
    """
    Throw this into the queue used for ProcessMetadata to tell it which
    Plex library section we're looking at

    context: itemtypes.Movie, itemtypes.Episode, etc.
    """
    def __init__(self, context, total_number_of_items, section_name,
                 section_id, plex_type):
        self.context = context
        self.total = total_number_of_items
        self.name = section_name
        self.id = section_id
        self.plex_type = plex_type


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

    def update(self):
        """
        """
        if self.show_dialog:
            try:
                progress = int(float(self.current) / float(self.total) * 100.0)
            except ZeroDivisionError:
                progress = 0
            self.dialog.update(progress,
                               self.section_name,
                               '%s/%s: %s'
                               % (self.current, self.total, self.title))
        common.update_kodi_library(video=self.is_video,
                                   music=not self.is_video)

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
            while self.isCanceled() is False:
                if section is None:
                    break
                self.current = 0
                self.total = section.total
                self.section_name = section.name
                self.is_video = section.plex_type in v.PLEX_VIDEO_TYPES
                with section.context(self.last_sync) as context:
                    while self.isCanceled() is False:
                        # grabs item from queue. This will block!
                        xml = self.queue.get()
                        if xml is InitNewSection or xml is None:
                            section = xml
                            self.queue.task_done()
                            break
                        try:
                            context.add_update(xml[0],
                                               viewtag=section.name,
                                               viewid=section.id,
                                               children=xml.children)
                        except:
                            utils.ERROR(txt='process_metadata crashed',
                                        notify=True,
                                        cancel_sync=True)
                        if self.current % 20 == 0:
                            self.title = utils.cast(unicode,
                                                    xml[0].get('title'))
                            self.update()
                        self.current += 1
                        self.queue.task_done()
        finally:
            if self.dialog:
                self.dialog.close()
            LOG.debug('Processing thread terminated')

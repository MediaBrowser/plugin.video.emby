# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import xbmcgui

from cProfile import Profile
from pstats import Stats
from StringIO import StringIO

from . import common
from .. import backgroundthread, utils, variables as v

LOG = getLogger('PLEX.sync.process_metadata')


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


class UpdateLastSync(object):
    def __init__(self, plex_id):
        self.plex_id = plex_id


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
        self.current = 1
        self.processed = 0
        self.title = ''
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
                               '%s (%s)' % (self.section_name, self.section_type_text),
                               '%s/%s %s'
                               % (self.current, self.total, self.title))

    def run(self):
        """
        Do the work
        """
        LOG.debug('Processing thread started')
        try:
            if self.show_dialog:
                self.dialog = xbmcgui.DialogProgressBG()
                self.dialog.create(utils.lang(39714))
            # Init with the very first library section. This will block!
            section = self.queue.get()
            self.queue.task_done()
            if section is None:
                return
            while not self.isCanceled():
                if section is None:
                    break
                LOG.debug('Start processing section %s (%ss)',
                          section.name, section.plex_type)
                self.current = 1
                self.processed = 0
                self.total = section.total
                self.section_name = section.name
                self.section_type_text = utils.lang(
                    v.TRANSLATION_FROM_PLEXTYPE[section.plex_type])
                profile = Profile()
                profile.enable()
                with section.context(self.last_sync) as context:
                    while not self.isCanceled():
                        # grabs item from queue. This will block!
                        item = self.queue.get()
                        if isinstance(item, InitNewSection) or item is None:
                            section = item
                            self.queue.task_done()
                            break
                        elif isinstance(item, UpdateLastSync):
                            context.plexdb.update_last_sync(item.plex_id,
                                                            section.plex_type,
                                                            self.last_sync)
                        else:
                            try:
                                context.add_update(item['xml'][0],
                                                   section_name=section.name,
                                                   section_id=section.id,
                                                   children=item['children'])
                            except:
                                utils.ERROR(notify=True, cancel_sync=True)
                            self.title = item['xml'][0].get('title')
                            self.processed += 1
                        self.update_progressbar()
                        self.current += 1
                        if self.processed == 500:
                            self.processed = 0
                            context.commit()
                        self.queue.task_done()
                profile.disable()
                string_io = StringIO()
                stats = Stats(profile, stream=string_io).sort_stats('cumulative')
                stats.print_stats()
                LOG.info('cProfile result: ')
                LOG.info(string_io.getvalue())
        finally:
            if self.dialog:
                self.dialog.close()
            while not self.queue.empty():
                # We need to empty the queue to let full_sync finish join()
                self.queue.get()
                self.queue.task_done()
            LOG.debug('Processing thread terminated')

# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from . import common
from .. import plex_functions as PF, backgroundthread, utils

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


class GetMetadataTask(backgroundthread.Task, common.libsync_mixin):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the queue with the downloaded etree XML objects

    Input:
        queue               Queue.Queue() object where this thread will store
                            the downloaded metadata XMLs as etree objects
    """
    def setup(self, queue, plex_id, get_children=False):
        self.queue = queue
        self.plex_id = plex_id
        self.get_children = get_children

    def run(self):
        """
        Do the work
        """
        if self.isCanceled():
            return
        # Download Metadata
        item = {
            'xml': PF.GetPlexMetadata(self.plex_id),
            'children': None
        }
        if item['xml'] is None:
            # Did not receive a valid XML - skip that item for now
            LOG.error("Could not get metadata for %s. Skipping that item "
                      "for now", self.plex_id)
            return
        elif item['xml'] == 401:
            LOG.error('HTTP 401 returned by PMS. Too much strain? '
                      'Cancelling sync for now')
            utils.window('plex_scancrashed', value='401')
            return
        if not self.isCanceled() and self.get_children:
            children_xml = PF.GetAllPlexChildren(self.plex_id)
            try:
                children_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error('Could not get children for Plex id %s',
                          self.plex_id)
            else:
                item['children'] = children_xml
        self.queue.put(item)

# -*- coding: utf-8 -*-
###############################################################################
from logging import getLogger
from threading import Thread
from urlparse import parse_qsl

from pickler import pickle_me, Playback_Successful
import playback
from context_entry import ContextMenu
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


class Playback_Starter(Thread):
    """
    Processes new plays
    """
    def triage(self, item):
        _, params = item.split('?', 1)
        params = dict(parse_qsl(params))
        mode = params.get('mode')
        LOG.debug('Received mode: %s, params: %s', mode, params)
        if mode == 'play':
            playback.playback_triage(plex_id=params.get('plex_id'),
                                     plex_type=params.get('plex_type'),
                                     path=params.get('path'))
        elif mode == 'plex_node':
            playback.process_indirect(params['key'], params['offset'])
        elif mode == 'context_menu':
            ContextMenu()
            result = Playback_Successful()
            # Let default.py know!
            pickle_me(result)

    def run(self):
        queue = state.COMMAND_PIPELINE_QUEUE
        LOG.info("----===## Starting Playback_Starter ##===----")
        while True:
            item = queue.get()
            if item is None:
                # Need to shutdown - initiated by command_pipeline
                break
            else:
                self.triage(item)
                queue.task_done()
        LOG.info("----===## Playback_Starter stopped ##===----")

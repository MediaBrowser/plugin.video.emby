# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import Thread
from Queue import Queue

from xbmc import sleep

from utils import window, thread_methods
import state

###############################################################################
log = logging.getLogger("PLEX."+__name__)

###############################################################################


@thread_methods
class Monitor_Window(Thread):
    """
    Monitors window('plex_command') for new entries that we need to take care
    of, e.g. for new plays initiated on the Kodi side with addon paths.

    Possible values of window('plex_command'):
        'play_....': to start playback using playback_starter

    Adjusts state.py accordingly
    """
    # Borg - multiple instances, shared state
    def __init__(self, callback=None):
        self.mgr = callback
        self.playback_queue = Queue()
        Thread.__init__(self)

    def run(self):
        thread_stopped = self.thread_stopped
        queue = self.playback_queue
        log.info("----===## Starting Kodi_Play_Client ##===----")
        while not thread_stopped():
            if window('plex_command'):
                value = window('plex_command')
                window('plex_command', clear=True)
                if value.startswith('play_'):
                    queue.put(value)

                elif value == 'SUSPEND_LIBRARY_THREAD-True':
                    state.SUSPEND_LIBRARY_THREAD = True
                elif value == 'SUSPEND_LIBRARY_THREAD-False':
                    state.SUSPEND_LIBRARY_THREAD = False
                elif value == 'STOP_SYNC-True':
                    state.STOP_SYNC = True
                elif value == 'STOP_SYNC-False':
                    state.STOP_SYNC = False
                elif value == 'PMS_STATUS-Auth':
                    state.PMS_STATUS = 'Auth'
                elif value == 'PMS_STATUS-401':
                    state.PMS_STATUS = '401'
                elif value == 'SUSPEND_USER_CLIENT-True':
                    state.SUSPEND_USER_CLIENT = True
                elif value == 'SUSPEND_USER_CLIENT-False':
                    state.SUSPEND_USER_CLIENT = False
                elif value.startswith('PLEX_TOKEN-'):
                    state.PLEX_TOKEN = value.replace('PLEX_TOKEN-', '') or None
                elif value.startswith('PLEX_USERNAME-'):
                    state.PLEX_USERNAME = \
                        value.replace('PLEX_USERNAME-', '') or None
                elif value.startswith('RUN_LIB_SCAN-'):
                    state.RUN_LIB_SCAN = value.replace('RUN_LIB_SCAN-', '')
                else:
                    raise NotImplementedError('%s not implemented' % value)
            else:
                sleep(50)
        # Put one last item into the queue to let playback_starter end
        queue.put(None)
        log.info("----===## Kodi_Play_Client stopped ##===----")

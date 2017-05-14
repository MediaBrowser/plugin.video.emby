# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import Thread
from Queue import Queue

from xbmc import sleep

from utils import window, ThreadMethods

###############################################################################
log = logging.getLogger("PLEX."+__name__)

###############################################################################


@ThreadMethods
class Monitor_Kodi_Play(Thread):
    """
    Monitors for new plays initiated on the Kodi side with addon paths.
    Immediately throws them into a queue to be processed by playback_starter
    """
    # Borg - multiple instances, shared state
    def __init__(self, callback=None):
        self.mgr = callback
        self.playback_queue = Queue()
        Thread.__init__(self)

    def run(self):
        threadStopped = self.threadStopped
        queue = self.playback_queue
        log.info("----===## Starting Kodi_Play_Client ##===----")
        while not threadStopped():
            if window('plex_play_new_item'):
                queue.put(window('plex_play_new_item'))
                window('plex_play_new_item', clear=True)
            else:
                sleep(50)
        # Put one last item into the queue to let playback_starter end
        queue.put(None)
        log.info("----===## Kodi_Play_Client stopped ##===----")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import Queue
from threading import Lock, RLock

from .. import utils


class App(object):
    """
    This class is used to store variables across PKC modules
    """
    def __init__(self, only_reload_settings=False):
        self.load_settings()
        if only_reload_settings:
            return
        # Quit PKC?
        self.stop_pkc = False

        # Need to lock all methods and functions messing with Plex Companion subscribers
        self.lock_subscriber = RLock()
        # Need to lock everything messing with Kodi/PKC playqueues
        self.lock_playqueues = RLock()
        # Necessary to temporarily hold back librarysync/websocket listener when doing
        # a full sync
        self.lock_playlists = Lock()

        # Plex Companion Queue()
        self.companion_queue = Queue.Queue(maxsize=100)
        # Command Pipeline Queue()
        self.command_pipeline_queue = Queue.Queue()
        # Websocket_client queue to communicate with librarysync
        self.websocket_queue = Queue.Queue()
        # xbmc.Monitor() instance from kodimonitor.py
        self.monitor = None

    def load_settings(self):
        # Number of items to fetch and display in widgets
        self.fetch_pms_item_number = int(utils.settings('fetch_pms_item_number'))
        # Hack to force Kodi widget for "in progress" to show up if it was empty
        # before
        self.force_reload_skin = utils.settings('forceReloadSkinOnPlaybackStop') == 'true'
        # Stemming from the PKC settings.xml
        self.kodi_plex_time_offset = float(utils.settings('kodiplextimeoffset'))

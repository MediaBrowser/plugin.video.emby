#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Used to save PKC's application state and share between modules. Be careful
if you invoke another PKC Python instance (!!) when e.g. PKC.movies is called
"""
from __future__ import absolute_import, division, unicode_literals
from copy import deepcopy
from logging import getLogger

import xbmc

from .account import Account
from .application import App
from .connection import Connection
from .libsync import Sync
from .playstate import PlayState

LOG = getLogger('PLEX.app')

ACCOUNT = None
APP = None
CONN = None
SYNC = None
PLAYSTATE = None


def init(entrypoint=False):
    """
    entrypoint=True initiates only the bare minimum - for other PKC python
    instances
    """
    global ACCOUNT, APP, CONN, SYNC, PLAYSTATE
    APP = App(entrypoint)
    CONN = Connection(entrypoint)
    ACCOUNT = Account(entrypoint)
    SYNC = Sync(entrypoint)
    if not entrypoint:
        PLAYSTATE = PlayState()


def _check_thread_suspension():
    global ACCOUNT, APP, SYNC
    threads_to_be_suspended = set()
    if SYNC.background_sync_disabled:
        threads_to_be_suspended.add(APP.pms_websocket)
    if not SYNC.enable_alexa or not ACCOUNT.plex_token:
        threads_to_be_suspended.add(APP.alexa_websocket)
    if ACCOUNT.restricted_user:
        threads_to_be_suspended.add(APP.pms_websocket)
        threads_to_be_suspended.add(APP.alexa_websocket)
    if None in threads_to_be_suspended:
        threads_to_be_suspended.remove(None)
    return threads_to_be_suspended


def resume_threads():
    """
    Resume all thread activity with or without blocking. Won't resume websocket
    threads if they should not be resumed
    Returns True only if PKC shutdown requested
    """
    global APP
    threads = deepcopy(APP.threads)
    threads_to_be_suspended = _check_thread_suspension()
    LOG.debug('Not resuming the following threads: %s', threads_to_be_suspended)
    for thread in threads_to_be_suspended:
        try:
            threads.remove(thread)
        except ValueError:
            pass
    LOG.debug('Thus resuming the following threads: %s', threads)
    for thread in threads:
        thread.resume()
    return xbmc.Monitor().abortRequested()


def check_websocket_threads_suspend():
    threads_to_be_suspended = _check_thread_suspension()
    for thread in threads_to_be_suspended:
        thread.suspend()


def suspend_threads(block=True):
    global APP
    APP.suspend_threads(block=block)


def reload():
    global APP, SYNC
    APP.reload()
    SYNC.reload()

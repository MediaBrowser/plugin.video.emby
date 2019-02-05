#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import xbmc

from .. import app, utils, variables as v

PLAYLIST_SYNC_ENABLED = (v.DEVICE != 'Microsoft UWP' and
                         utils.settings('enablePlaylistSync') == 'true')


class libsync_mixin(object):
    def isCanceled(self):
        return (self._canceled or app.APP.stop_pkc or app.SYNC.stop_sync or
                app.APP.suspend_threads or app.SYNC.suspend_sync)


class fullsync_mixin(object):
    def isCanceled(self):
        return (self._canceled or
                app.APP.stop_pkc or
                app.SYNC.stop_sync or
                app.APP.suspend_threads)


def update_kodi_library(video=True, music=True):
    """
    Updates the Kodi library and thus refreshes the Kodi views and widgets
    """
    if video:
        xbmc.executebuiltin('UpdateLibrary(video)')
    if music:
        xbmc.executebuiltin('UpdateLibrary(music)')


def tag_last(iterable):
    """
    Given some iterable, returns (last, item), where last is only True if you
    are on the final iteration.
    """
    iterator = iter(iterable)
    gotone = False
    try:
        lookback = next(iterator)
        gotone = True
        while True:
            cur = next(iterator)
            yield False, lookback
            lookback = cur
    except StopIteration:
        if gotone:
            yield True, lookback
        raise StopIteration()

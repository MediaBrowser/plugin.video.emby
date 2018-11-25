#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import xbmc

from .. import app


class libsync_mixin(object):
    def isCanceled(self):
        return (self._canceled or app.APP.stop_pkc or app.SYNC.stop_sync or
                app.APP.suspend_threads or app.SYNC.suspend_sync)


def update_kodi_library(video=True, music=True):
    """
    Updates the Kodi library and thus refreshes the Kodi views and widgets
    """
    if xbmc.getCondVisibility('Container.Content(musicvideos)') or \
            xbmc.getCondVisibility('Window.IsMedia'):
        # Prevent cursor from moving
        xbmc.executebuiltin('Container.Refresh')
    else:
        # Update widgets
        if video:
            xbmc.executebuiltin('UpdateLibrary(video)')
        if music:
            xbmc.executebuiltin('UpdateLibrary(music)')

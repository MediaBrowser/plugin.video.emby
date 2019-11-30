#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import xbmc

from .. import utils, app, variables as v

PLAYLIST_SYNC_ENABLED = (v.DEVICE != 'Microsoft UWP' and
                         utils.settings('enablePlaylistSync') == 'true')


def update_kodi_library(video=True, music=True):
    """
    Updates the Kodi library and thus refreshes the Kodi views and widgets
    """
    if video:
        if not xbmc.getCondVisibility('Window.IsMedia'):
            xbmc.executebuiltin('UpdateLibrary(video)')
        else:
            # Prevent cursor from moving - refresh later
            xbmc.executebuiltin('Container.Refresh')
            app.APP.update_widgets = True
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

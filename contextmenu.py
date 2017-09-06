# -*- coding: utf-8 -*-

###############################################################################

import logging
import os
import sys

import xbmc
import xbmcaddon

###############################################################################

_addon = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
try:
    _addon_path = _addon.getAddonInfo('path').decode('utf-8')
except TypeError:
    _addon_path = _addon.getAddonInfo('path').decode()
try:
    _base_resource = xbmc.translatePath(os.path.join(
        _addon_path,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    _base_resource = xbmc.translatePath(os.path.join(
        _addon_path,
        'resources',
        'lib')).decode()
sys.path.append(_base_resource)

###############################################################################

import loghandler
from context_entry import ContextMenu

###############################################################################

loghandler.config()
log = logging.getLogger("PLEX.contextmenu")

###############################################################################

if __name__ == "__main__":

    try:
        # Start the context menu
        ContextMenu()
    except Exception as error:
        log.error(error)
        import traceback
        log.error("Traceback:\n%s" % traceback.format_exc())
        raise

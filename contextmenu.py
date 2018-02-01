# -*- coding: utf-8 -*-

###############################################################################
from os import path as os_path
from sys import path as sys_path

from xbmcaddon import Addon
from xbmc import translatePath, sleep, log, LOGERROR
from xbmcgui import Window

_ADDON = Addon(id='plugin.video.plexkodiconnect')
try:
    _ADDON_PATH = _ADDON.getAddonInfo('path').decode('utf-8')
except TypeError:
    _ADDON_PATH = _ADDON.getAddonInfo('path').decode()
try:
    _base_resource = translatePath(os_path.join(
        _ADDON_PATH,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    _base_resource = translatePath(os_path.join(
        _ADDON_PATH,
        'resources',
        'lib')).decode()
sys_path.append(_base_resource)

from pickler import unpickle_me, pickl_window

###############################################################################

if __name__ == "__main__":
    WINDOW = Window(10000)
    while WINDOW.getProperty('plex_command'):
        sleep(20)
    WINDOW.setProperty('plex_command', 'CONTEXT_menu')
    while not pickl_window('plex_result'):
        sleep(50)
    RESULT = unpickle_me()
    if RESULT is None:
        log('PLEX.%s: Error encountered, aborting' % __name__, level=LOGERROR)

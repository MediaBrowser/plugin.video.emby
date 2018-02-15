# -*- coding: utf-8 -*-
###############################################################################
from sys import listitem
from urllib import urlencode

from xbmc import getCondVisibility, sleep
from xbmcgui import Window

###############################################################################


def _get_kodi_type():
    kodi_type = listitem.getVideoInfoTag().getMediaType().decode('utf-8')
    if not kodi_type:
        if getCondVisibility('Container.Content(albums)'):
            kodi_type = "album"
        elif getCondVisibility('Container.Content(artists)'):
            kodi_type = "artist"
        elif getCondVisibility('Container.Content(songs)'):
            kodi_type = "song"
        elif getCondVisibility('Container.Content(pictures)'):
            kodi_type = "picture"
    return kodi_type


if __name__ == "__main__":
    WINDOW = Window(10000)
    KODI_ID = listitem.getVideoInfoTag().getDbId()
    KODI_TYPE = _get_kodi_type()
    ARGS = {
        'kodi_id': KODI_ID,
        'kodi_type': KODI_TYPE
    }
    while WINDOW.getProperty('plex_command'):
        sleep(20)
    WINDOW.setProperty('plex_command', 'CONTEXT_menu?%s' % urlencode(ARGS))

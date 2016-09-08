# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

_ADDON = xbmcaddon.Addon(id='plugin.video.emby')
_CWD = _ADDON.getAddonInfo('path').decode('utf-8')
_BASE_LIB = xbmc.translatePath(os.path.join(_CWD, 'resources', 'lib')).decode('utf-8')
sys.path.append(_BASE_LIB)

#################################################################################################

import entrypoint
import loghandler
import utils
from utils import window, dialog, language as lang

#################################################################################################

loghandler.config()
log = logging.getLogger("EMBY.default")

#################################################################################################


class Main(object):

    # MAIN ENTRY POINT
    #@utils.profiling()

    def __init__(self):

        # Parse parameters
        base_url = sys.argv[0]
        params = urlparse.parse_qs(sys.argv[2][1:])
        log.warn("Parameter string: %s", sys.argv[2])
        try:
            mode = params['mode'][0]
            itemid = params.get('id')
            if itemid:
                itemid = itemid[0]
        except:
            params = {}
            mode = ""

        if "/extrafanart" in base_url:

            emby_path = sys.argv[2][1:]
            emby_id = params.get('id', [""])[0]
            entrypoint.getExtraFanArt(emby_id,emby_path)

        elif "/Extras" in base_url or "/VideoFiles" in base_url:

            emby_path = sys.argv[2][1:]
            emby_id = params.get('id', [""])[0]
            entrypoint.getVideoFiles(emby_id, emby_path)

        elif not self._modes(mode, params):
            # Other functions
            if mode == 'settings':
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

            elif mode in ('manualsync', 'fastsync', 'repair'):

                if window('emby_online') != "true":
                    # Server is not online, do not run the sync
                    dialog(type_="ok",
                           heading="{emby}",
                           line1=lang(33034))
                    log.warn("Not connected to the emby server.")

                elif window('emby_dbScan') != "true":
                    import librarysync
                    library_sync = librarysync.LibrarySync()

                    if mode == 'manualsync':
                        library_sync.ManualSync().sync()
                    elif mode == 'fastsync':
                        library_sync.startSync()
                    else:
                        library_sync.fullSync(repair=True)
                else:
                    log.warn("Database scan is already running.")

            elif mode == 'texturecache':
                import artwork
                artwork.Artwork().fullTextureCacheSync()
            else:
                entrypoint.doMainListing()

    def _modes(self, mode, params):

        modes = {

            'reset': utils.reset,
            'resetauth': entrypoint.resetAuth,
            'play': entrypoint.doPlayback,
            'passwords': utils.passwordsXML,
            'adduser': entrypoint.addUser,
            'thememedia': entrypoint.getThemeMedia,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
            'deviceid': entrypoint.resetDeviceId,
            'delete': entrypoint.deleteItem,
            'connect': entrypoint.emby_connect
        }
        if mode in modes:
            # Simple functions
            if mode == 'play':
                dbid = params.get('dbid')
                modes[mode](itemid, dbid)

            elif mode in ('nextup', 'inprogressepisodes', 'recentepisodes'):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)

            elif mode in ('channels', 'getsubfolders'):
                modes[mode](itemid)

            elif mode == 'browsecontent':
                modes[mode](itemid, params.get('type', [""])[0], params.get('folderid', [""])[0])

            elif mode == 'channelsfolder':
                folderid = params['folderid'][0]
                modes[mode](itemid, folderid)
            else:
                modes[mode]()

            return True

        return False


if __name__ == "__main__":

    log.info("plugin.video.emby started")
    Main()
    log.info("plugin.video.emby stopped")
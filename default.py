# -*- coding: utf-8 -*-

###############################################################################

import logging
import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


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

import entrypoint
import utils

###############################################################################

import loghandler

loghandler.config()
log = logging.getLogger("PLEX.default")

###############################################################################


class Main():

    # MAIN ENTRY POINT
    #@utils.profiling()
    def __init__(self):
        # Parse parameters
        log.warn("Full sys.argv received: %s" % sys.argv)
        base_url = sys.argv[0]
        params = urlparse.parse_qs(sys.argv[2][1:])
        try:
            mode = params['mode'][0]
            itemid = params.get('id', '')
            if itemid:
                try:
                    itemid = itemid[0]
                except:
                    pass
        except:
            params = {}
            mode = ""

        modes = {

            'reset': utils.reset,
            'resetauth': entrypoint.resetAuth,
            'play': entrypoint.doPlayback,
            'passwords': utils.passwordsXML,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
            'companion': entrypoint.plexCompanion,
            'switchuser': entrypoint.switchPlexUser,
            'deviceid': entrypoint.resetDeviceId,
            'delete': entrypoint.deleteItem,
            'browseplex': entrypoint.BrowsePlexContent,
            'ondeck': entrypoint.getOnDeck,
            'chooseServer': entrypoint.chooseServer,
            'watchlater': entrypoint.watchlater,
            'enterPMS': entrypoint.enterPMS,
            'togglePlexTV': entrypoint.togglePlexTV,
            'playwatchlater': entrypoint.playWatchLater
        }

        if "/extrafanart" in sys.argv[0]:
            plexpath = sys.argv[2][1:]
            plexid = params.get('id', [""])[0]
            entrypoint.getExtraFanArt(plexid, plexpath)
            entrypoint.getVideoFiles(plexid, plexpath)
            return

        if mode == 'fanart':
            log.info('User requested fanarttv refresh')
            utils.window('plex_runLibScan', value='fanart')

        # Called by e.g. 3rd party plugin video extras
        if ("/Extras" in sys.argv[0] or "/VideoFiles" in sys.argv[0] or
                "/Extras" in sys.argv[2]):
            plexId = params.get('id', [None])[0]
            entrypoint.getVideoFiles(plexId, params)

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                # modes[mode](itemid, dbid)
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes"):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)
            
            elif mode in ("channels","getsubfolders"):
                modes[mode](itemid)
                
            elif mode == "browsecontent":
                modes[mode](itemid, params.get('type',[""])[0], params.get('folderid',[""])[0])

            elif mode == 'browseplex':
                modes[mode](
                    itemid,
                    params.get('type', [""])[0],
                    params.get('folderid', [""])[0])

            elif mode in ('ondeck', 'recentepisodes'):
                modes[mode](
                    itemid,
                    params.get('type', [""])[0],
                    params.get('tagname', [""])[0],
                    int(params.get('limit', [""])[0]))

            elif mode == "channelsfolder":
                folderid = params['folderid'][0]
                modes[mode](itemid, folderid)
            elif mode == "companion":
                modes[mode](itemid, params=sys.argv[2])
            elif mode == 'playwatchlater':
                modes[mode](params.get('id')[0], params.get('viewOffset')[0])
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')
            elif mode in ("manualsync", "repair"):
                if utils.window('plex_online') != "true":
                    # Server is not online, do not run the sync
                    xbmcgui.Dialog().ok(
                        "PlexKodiConnect",
                        "Unable to run the sync, the add-on is not connected "
                        "to a Plex server.")
                    log.error("Not connected to a PMS.")
                else:
                    if mode == 'repair':
                        utils.window('plex_runLibScan', value="repair")
                        log.info("Requesting repair lib sync")
                    elif mode == 'manualsync':
                        log.info("Requesting full library scan")
                        utils.window('plex_runLibScan', value="full")
                    
            elif mode == "texturecache":
                utils.window('plex_runLibScan', value='del_textures')
            else:
                entrypoint.doMainListing()
        # Prevent Kodi from hanging in an infinite loop waiting for more
        xbmcplugin.endOfDirectory(int(sys.argv[1]))

if __name__ == "__main__":
    log.info('plugin.video.plexkodiconnect started')
    Main()
    log.info('plugin.video.plexkodiconnect stopped')

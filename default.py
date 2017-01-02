# -*- coding: utf-8 -*-

###############################################################################

import logging
from os import path as os_path
from sys import path as sys_path, argv
from urlparse import parse_qsl

from xbmc import translatePath, sleep, executebuiltin
from xbmcaddon import Addon
from xbmcgui import ListItem, Dialog
from xbmcplugin import setResolvedUrl

_addon = Addon(id='plugin.video.plexkodiconnect')
try:
    _addon_path = _addon.getAddonInfo('path').decode('utf-8')
except TypeError:
    _addon_path = _addon.getAddonInfo('path').decode()
try:
    _base_resource = translatePath(os_path.join(
        _addon_path,
        'resources',
        'lib')).decode('utf-8')
except TypeError:
    _base_resource = translatePath(os_path.join(
        _addon_path,
        'resources',
        'lib')).decode()
sys_path.append(_base_resource)

###############################################################################

import entrypoint
from utils import window, pickl_window, reset, passwordsXML
from pickler import unpickle_me
from PKC_listitem import convert_PKC_to_listitem

###############################################################################

import loghandler

loghandler.config()
log = logging.getLogger("PLEX.default")

###############################################################################

ARGV = argv
HANDLE = int(argv[1])


class Main():

    # MAIN ENTRY POINT
    # @utils.profiling()
    def __init__(self):
        log.debug("Full sys.argv received: %s" % ARGV)
        # Parse parameters
        params = dict(parse_qsl(ARGV[2][1:]))
        try:
            mode = params['mode']
            itemid = params.get('id', '')
        except:
            mode = ""
            itemid = ''

        if mode == 'play':
            # Put the request into the "queue"
            while window('plex_play_new_item'):
                sleep(20)
            window('plex_play_new_item',
                   value='%s%s' % (mode, ARGV[2]))
            # Wait for the result
            while not pickl_window('plex_result'):
                sleep(20)
            result = unpickle_me()
            if result is None:
                log.error('Error encountered, aborting')
                setResolvedUrl(HANDLE, False, ListItem())
            elif result.listitem:
                listitem = convert_PKC_to_listitem(result.listitem)
                setResolvedUrl(HANDLE, True, listitem)
            return

        modes = {
            'reset': reset,
            'resetauth': entrypoint.resetAuth,
            'passwords': passwordsXML,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
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

        if "/extrafanart" in ARGV[0]:
            plexpath = ARGV[2][1:]
            plexid = params.get('id', [""])[0]
            entrypoint.getExtraFanArt(plexid, plexpath)
            entrypoint.getVideoFiles(plexid, plexpath)
            return

        if mode == 'fanart':
            log.info('User requested fanarttv refresh')
            window('plex_runLibScan', value='fanart')

        # Called by e.g. 3rd party plugin video extras
        if ("/Extras" in ARGV[0] or "/VideoFiles" in ARGV[0] or
                "/Extras" in ARGV[2]):
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
                modes[mode](itemid, params=ARGV[2])
            elif mode == 'playwatchlater':
                modes[mode](params.get('id')[0], params.get('viewOffset')[0])
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')
            elif mode in ("manualsync", "repair"):
                if window('plex_online') != "true":
                    # Server is not online, do not run the sync
                    Dialog().ok(
                        "PlexKodiConnect",
                        "Unable to run the sync, the add-on is not connected "
                        "to a Plex server.")
                    log.error("Not connected to a PMS.")
                else:
                    if mode == 'repair':
                        window('plex_runLibScan', value="repair")
                        log.info("Requesting repair lib sync")
                    elif mode == 'manualsync':
                        log.info("Requesting full library scan")
                        window('plex_runLibScan', value="full")
            elif mode == "texturecache":
                window('plex_runLibScan', value='del_textures')
            else:
                entrypoint.doMainListing()

if __name__ == "__main__":
    log.info('plugin.video.plexkodiconnect started')
    Main()
    log.info('plugin.video.plexkodiconnect stopped')

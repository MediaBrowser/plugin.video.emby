# -*- coding: utf-8 -*-

###############################################################################

import logging
from os import path as os_path
from sys import path as sys_path, argv
from urlparse import parse_qsl

from xbmc import translatePath, sleep, executebuiltin
from xbmcaddon import Addon
from xbmcgui import ListItem
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
from utils import window, pickl_window, reset, passwordsXML, language as lang,\
    dialog
from pickler import unpickle_me
from PKC_listitem import convert_PKC_to_listitem

###############################################################################

import loghandler

loghandler.config()
log = logging.getLogger("PLEX.default")

###############################################################################

HANDLE = int(argv[1])


class Main():

    # MAIN ENTRY POINT
    # @utils.profiling()
    def __init__(self):
        log.debug("Full sys.argv received: %s" % argv)
        # Parse parameters
        params = dict(parse_qsl(argv[2][1:]))
        try:
            mode = params['mode']
            itemid = params.get('id', '')
        except:
            mode = ""
            itemid = ''

        if mode == 'play':
            # Put the request into the "queue"
            while window('plex_play_new_item'):
                sleep(50)
            window('plex_play_new_item',
                   value='%s%s' % (mode, argv[2]))
            # Wait for the result
            while not pickl_window('plex_result'):
                sleep(50)
            result = unpickle_me()
            if result is None:
                log.error('Error encountered, aborting')
                dialog('notification',
                       heading='{plex}',
                       message=lang(30128),
                       icon='{error}',
                       time=3000)
                setResolvedUrl(HANDLE, False, ListItem())
            elif result.listitem:
                listitem = convert_PKC_to_listitem(result.listitem)
                setResolvedUrl(HANDLE, True, listitem)
            return

        modes = {
            'reset': reset,
            'resetauth': entrypoint.resetAuth,
            'passwords': passwordsXML,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
            'switchuser': entrypoint.switchPlexUser,
            'deviceid': entrypoint.resetDeviceId,
            'browseplex': entrypoint.BrowsePlexContent,
            'ondeck': entrypoint.getOnDeck,
            'chooseServer': entrypoint.chooseServer,
            'watchlater': entrypoint.watchlater,
            'channels': entrypoint.channels,
            'enterPMS': entrypoint.enterPMS,
            'togglePlexTV': entrypoint.togglePlexTV,
            'Plex_Node': entrypoint.Plex_Node,
            'browse_plex_folder': entrypoint.browse_plex_folder
        }

        if "/extrafanart" in argv[0]:
            plexpath = argv[2][1:]
            plexid = params.get('id')
            entrypoint.getExtraFanArt(plexid, plexpath)
            entrypoint.getVideoFiles(plexid, plexpath)
            return

        if mode == 'fanart':
            log.info('User requested fanarttv refresh')
            window('plex_runLibScan', value='fanart')

        # Called by e.g. 3rd party plugin video extras
        if ("/Extras" in argv[0] or "/VideoFiles" in argv[0] or
                "/Extras" in argv[2]):
            plexId = params.get('id', None)
            entrypoint.getVideoFiles(plexId, params)

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                # modes[mode](itemid, dbid)
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes"):
                limit = int(params['limit'])
                modes[mode](params['tagname'], limit)

            elif mode in ("getsubfolders"):
                modes[mode](itemid)

            elif mode == "browsecontent":
                modes[mode](itemid, params.get('type'), params.get('folderid'))

            elif mode == 'browseplex':
                modes[mode](
                    itemid,
                    params.get('type'),
                    params.get('folderid'))

            elif mode in ('ondeck', 'recentepisodes'):
                modes[mode](
                    itemid,
                    params.get('type'),
                    params.get('tagname'),
                    int(params.get('limit')))

            elif mode == "channelsfolder":
                folderid = params['folderid']
                modes[mode](itemid, folderid)
            elif mode == "companion":
                modes[mode](itemid, params=argv[2])
            elif mode == 'Plex_Node':
                modes[mode](params.get('id'),
                            params.get('viewOffset'))
            elif mode == 'browse_plex_folder':
                modes[mode](params.get('id'))
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')
            elif mode in ("manualsync", "repair"):
                if window('plex_online') != "true":
                    # Server is not online, do not run the sync
                    dialog('ok',
                           heading=lang(29999),
                           message=lang(39205))
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

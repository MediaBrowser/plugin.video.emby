# -*- coding: utf-8 -*-

#################################################################################################

import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

addon_ = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
addon_path = addon_.getAddonInfo('path').decode('utf-8')
base_resource = xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(base_resource)

#################################################################################################

import entrypoint
import utils

#################################################################################################

enableProfiling = False

class Main:


    # MAIN ENTRY POINT
    def __init__(self):
        # Parse parameters
        xbmc.log("Full sys.argv received: %s" % sys.argv)
        base_url = sys.argv[0]
        params = urlparse.parse_qs(sys.argv[2][1:])
        xbmc.log("Parameter string: %s" % sys.argv[2])
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
            'companion': entrypoint.plexCompanion,
            'switchuser': entrypoint.switchPlexUser,
            'deviceid': entrypoint.resetDeviceId,
            'reConnect': entrypoint.reConnect,
            'delete': entrypoint.deleteItem,
            'browseplex': entrypoint.BrowsePlexContent,
            'ondeck': entrypoint.getOnDeck
        }
        
        if "/extrafanart" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getExtraFanArt(embyid,embypath)
            
        if "/Extras" in sys.argv[0] or "/VideoFiles" in sys.argv[0]:
            embypath = sys.argv[2][1:]
            embyid = params.get('id',[""])[0]
            entrypoint.getVideoFiles(embyid,embypath)

        if modes.get(mode):
            # Simple functions
            if mode == "play":
                dbid = params.get('dbid')
                # modes[mode](itemid, dbid)
                modes[mode](itemid, dbid)

            elif mode in ("nextup", "inprogressepisodes", "recentepisodes"):
                limit = int(params['limit'][0])
                modes[mode](itemid, limit)
            
            elif mode in ["channels","getsubfolders"]:
                modes[mode](itemid)
                
            elif mode == "browsecontent":
                modes[mode]( itemid, params.get('type',[""])[0], params.get('folderid',[""])[0] )

            elif mode == 'browseplex':
                modes[mode](
                    itemid,
                    params.get('type', [""])[0],
                    params.get('folderid', [""])[0])

            elif mode == 'ondeck':
                modes[mode](
                    itemid,
                    params.get('type', [""])[0],
                    params.get('tagname', [""])[0],
                    params.get('limit', [""])[0])

            elif mode == "channelsfolder":
                folderid = params['folderid'][0]
                modes[mode](itemid, folderid)
            elif mode == "companion":
                modes[mode](itemid, params=sys.argv[2])
            else:
                modes[mode]()
        else:
            # Other functions
            if mode == "settings":
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')
            elif mode in ("manualsync", "repair"):
                if utils.window('emby_online') != "true":
                    # Server is not online, do not run the sync
                    xbmcgui.Dialog().ok(heading="PlexKodiConnect",
                                        line1=("Unable to run the sync, the add-on is not "
                                               "connected to the Emby server."))
                    utils.logMsg("PLEX", "Not connected to the emby server.", 1)
                    return
                    
                else:
                    utils.logMsg("PLEX", "Requesting full library scan", 1)
                    utils.window('plex_runLibScan', value="full")
                    
            elif mode == "texturecache":
                import artwork
                artwork.Artwork().FullTextureCacheSync()
            else:
                entrypoint.doMainListing()

                      
if ( __name__ == "__main__" ):
    xbmc.log('plugin.video.plexkodiconnect started')

    if enableProfiling:
        import cProfile
        import pstats
        import random
        from time import gmtime, strftime
        addonid      = addon_.getAddonInfo('id').decode( 'utf-8' )
        datapath     = os.path.join( xbmc.translatePath( "special://profile/" ).decode( 'utf-8' ), "addon_data", addonid )
        
        filename = os.path.join( datapath, strftime( "%Y%m%d%H%M%S",gmtime() ) + "-" + str( random.randrange(0,100000) ) + ".log" )
        cProfile.run( 'Main()', filename )
        
        stream = open( filename + ".txt", 'w')
        p = pstats.Stats( filename, stream = stream )
        p.sort_stats( "cumulative" )
        p.print_stats()
    
    else:
        Main()
    
    xbmc.log('plugin.video.plexkodiconnect stopped')
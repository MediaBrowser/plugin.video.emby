# -*- coding: utf-8 -*-

###############################################################################

import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

import utils

addon_ = xbmcaddon.Addon(id='plugin.video.plexkodiconnect')
addon_path = utils.tryDecode(addon_.getAddonInfo('path'))
base_resource = utils.tryDecode(xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')))
sys.path.append(base_resource)

import artwork
import clientinfo
import downloadutils
import librarysync
import read_embyserver as embyserver
import embydb_functions as embydb
import kodidb_functions as kodidb
import musicutils as musicutils

import PlexFunctions as PF
import PlexAPI


def logMsg(msg, lvl=1):
    utils.logMsg("%s %s" % ("PlexKodiConnect", "Contextmenu"), msg, lvl)


#Kodi contextmenu item to configure the emby settings
#for now used to set ratings but can later be used to sync individual items etc.
if __name__ == '__main__':
    itemid = utils.tryDecode(xbmc.getInfoLabel("ListItem.DBID"))
    itemtype = utils.tryDecode(xbmc.getInfoLabel("ListItem.DBTYPE"))
    
    emby = embyserver.Read_EmbyServer()
    
    embyid = ""
    if not itemtype and xbmc.getCondVisibility("Container.Content(albums)"): itemtype = "album"
    if not itemtype and xbmc.getCondVisibility("Container.Content(artists)"): itemtype = "artist"
    if not itemtype and xbmc.getCondVisibility("Container.Content(songs)"): itemtype = "song"
    if not itemtype and xbmc.getCondVisibility("Container.Content(pictures)"): itemtype = "picture"
    
    if (not itemid or itemid == "-1") and xbmc.getInfoLabel("ListItem.Property(embyid)"):
        embyid = xbmc.getInfoLabel("ListItem.Property(embyid)")
    else:
        with embydb.GetEmbyDB() as emby_db:
            item = emby_db.getItem_byKodiId(itemid, itemtype)
        if item:
            embyid = item[0]

    logMsg("Contextmenu opened for embyid: %s  - itemtype: %s" %(embyid,itemtype))

    if embyid:
        item = PF.GetPlexMetadata(embyid)
        if item is None or item == 401:
            logMsg('Could not get item metadata for item %s' % embyid, -1)
            return
        API = PlexAPI.API(item[0])
        userdata = API.getUserData()
        likes = userdata['Likes']
        favourite = userdata['Favorite']
        
        options=[]
        if likes == True:
            #clear like for the item
            options.append(utils.language(30402))
        if likes == False or likes == None:
            #Like the item
            options.append(utils.language(30403))
        if likes == True or likes == None:
            #Dislike the item
            options.append(utils.language(30404)) 
        if favourite == False:
            #Add to emby favourites
            options.append(utils.language(30405)) 
        if favourite == True:
            #Remove from emby favourites
            options.append(utils.language(30406))
        if itemtype == "song":
            #Set custom song rating
            options.append(utils.language(30407))
        
        #delete item
        options.append(utils.language(30409))
        
        #addon settings
        options.append(utils.language(30408))
        
        #display select dialog and process results
        header = utils.language(30401)
        ret = xbmcgui.Dialog().select(header, options)
        if ret != -1:
            if options[ret] == utils.language(30402):
                emby.updateUserRating(embyid, deletelike=True)
            if options[ret] == utils.language(30403):
                emby.updateUserRating(embyid, like=True)
            if options[ret] == utils.language(30404):
                emby.updateUserRating(embyid, like=False)
            if options[ret] == utils.language(30405):
                emby.updateUserRating(embyid, favourite=True)
            if options[ret] == utils.language(30406):
                emby.updateUserRating(embyid, favourite=False)
            if options[ret] == utils.language(30407):
                kodiconn = utils.kodiSQL('music')
                kodicursor = kodiconn.cursor()
                query = ' '.join(("SELECT rating", "FROM song", "WHERE idSong = ?" ))
                kodicursor.execute(query, (itemid,))
                currentvalue = int(round(float(kodicursor.fetchone()[0]),0))
                newvalue = xbmcgui.Dialog().numeric(0, "Set custom song rating (0-5)", str(currentvalue))
                if newvalue:
                    newvalue = int(newvalue)
                    if newvalue > 5: newvalue = "5"
                    if utils.settings('enableUpdateSongRating') == "true":
                        musicutils.updateRatingToFile(newvalue, API.getFilePath())
                    if utils.settings('enableExportSongRating') == "true":
                        like, favourite, deletelike = musicutils.getEmbyRatingFromKodiRating(newvalue)
                        emby.updateUserRating(embyid, like, favourite, deletelike)
                    query = ' '.join(( "UPDATE song","SET rating = ?", "WHERE idSong = ?" ))
                    kodicursor.execute(query, (newvalue,itemid,))
                    kodiconn.commit()

            if options[ret] == utils.language(30408):
                #Open addon settings
                xbmc.executebuiltin("Addon.OpenSettings(plugin.video.plexkodiconnect)")
                
            if options[ret] == utils.language(30409):
                #delete item from the server
                delete = True
                if utils.settings('skipContextMenu') != "true":
                    resp = xbmcgui.Dialog().yesno(
                                            heading="Confirm delete",
                                            line1=("Delete file from Emby Server? This will "
                                                    "also delete the file(s) from disk!"))
                    if not resp:
                        logMsg("User skipped deletion for: %s." % embyid, 1)
                        delete = False
                
                if delete:
                    import downloadutils
                    doUtils = downloadutils.DownloadUtils()
                    url = "{server}/emby/Items/%s?format=json" % embyid
                    logMsg("Deleting request: %s" % embyid, 0)
                    doUtils.downloadUrl(url, action_type="DELETE")

                '''if utils.settings('skipContextMenu') != "true":
                    if xbmcgui.Dialog().yesno(
                                        heading="Confirm delete",
                                        line1=("Delete file on Emby Server? This will "
                                                "also delete the file(s) from disk!")):
                        import downloadutils
                        doUtils = downloadutils.DownloadUtils()
                        doUtils.downloadUrl("{server}/emby/Items/%s?format=json" % embyid, action_type="DELETE")'''
            
            xbmc.sleep(500)
            xbmc.executebuiltin("Container.Update")
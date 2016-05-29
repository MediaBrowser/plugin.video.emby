# -*- coding: utf-8 -*-

###############################################################################

import json
import os
import sys
import urllib

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import xbmcplugin

import artwork
import utils
import clientinfo
import downloadutils
import read_embyserver as embyserver
import embydb_functions as embydb
import playbackutils as pbutils
import playutils
import playlist

import PlexFunctions
import PlexAPI

###############################################################################

# For logging only
addonName = 'PlexKodiConnect'
title = "%s %s" % (addonName, __name__)


def plexCompanion(fullurl, params):
    params = PlexFunctions.LiteralEval(params[26:])

    if (params['machineIdentifier'] !=
            utils.window('plex_machineIdentifier')):
        utils.logMsg(
            title,
            "Command was not for us, machineIdentifier controller: %s, "
            "our machineIdentifier : %s"
            % (params['machineIdentifier'],
               utils.window('plex_machineIdentifier')), -1)
        return

    library, key, query = PlexFunctions.ParseContainerKey(
        params['containerKey'])
    # Construct a container key that works always (get rid of playlist args)
    utils.window('containerKey', '/'+library+'/'+key)

    if 'playQueues' in library:
        utils.logMsg(title, "Playing a playQueue. Query was: %s" % query, 1)
        # Playing a playlist that we need to fetch from PMS
        xml = PlexFunctions.GetPlayQueue(key)
        if xml is None:
            utils.logMsg(
                title, "Error getting PMS playlist for key %s" % key, -1)
            return
        else:
            resume = PlexFunctions.ConvertPlexToKodiTime(
                params.get('offset', 0))
            itemids = []
            for item in xml:
                itemids.append(item.get('ratingKey'))
            return playlist.Playlist().playAll(itemids, resume)

    else:
        utils.logMsg(
            title, "Not knowing what to do for now - no playQueue sent", -1)


def chooseServer():
    """
    Lets user choose from list of PMS
    """
    utils.logMsg(title, "Choosing PMS server requested, starting", 1)

    import initialsetup
    setup = initialsetup.InitialSetup()
    server = setup.PickPMS(showDialog=True)
    if server is None:
        utils.logMsg('We did not connect to a new PMS, aborting', -1)
        utils.window('suspend_Userclient', clear=True)
        utils.window('suspend_LibraryThread', clear=True)
        return

    utils.logMsg(title, "User chose server %s" % server['name'], 1)
    setup.WritePMStoSettings(server)

    if not __LogOut():
        return

    # First remove playlists
    utils.deletePlaylists()
    # Remove video nodes
    utils.deleteNodes()

    # Log in again
    __LogIn()
    utils.logMsg(title, "Choosing new PMS complete", 1)
    # '<PMS> connected'
    xbmcgui.Dialog().notification(
        heading=addonName,
        message='%s %s' % (server['name'],
                           xbmcaddon.Addon().getLocalizedString(39220)),
        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
        time=3000,
        sound=False)


def togglePlexTV():
    if utils.settings('plexToken'):
        utils.logMsg(title, 'Reseting plex.tv credentials in settings', 1)
        utils.settings('plexLogin', value="")
        utils.settings('plexToken', value=""),
        utils.settings('plexid', value="")
        utils.settings('plexHomeSize', value="1")
        utils.settings('plexAvatar', value="")
        utils.settings('plex_status', value="Not logged in to plex.tv")

        utils.window('plex_token', clear=True)
        utils.window('plex_username', clear=True)
    else:
        utils.logMsg(title, 'Login to plex.tv', 1)
        import initialsetup
        initialsetup.InitialSetup().PlexTVSignIn()
    xbmcgui.Dialog().notification(
        heading=addonName,
        message=xbmcaddon.Addon().getLocalizedString(39221),
        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
        time=3000,
        sound=False)


def PassPlaylist(xml, resume=None):
    """
    resume in KodiTime - seconds.
    """
    # Set window properties to make them available later for other threads
    windowArgs = [
        # 'containerKey'
        'playQueueID',
        'playQueueVersion']
    for arg in windowArgs:
        utils.window(arg, value=xml.attrib.get(arg))

    # Get resume point
    resume1 = PlexFunctions.ConvertPlexToKodiTime(utils.IntFromStr(
        xml.attrib.get('playQueueSelectedItemOffset', 0)))
    resume2 = resume
    resume = max(resume1, resume2)

    pbutils.PlaybackUtils(xml).StartPlay(
        resume=resume,
        resumeId=xml.attrib.get('playQueueSelectedItemID', None))


def doPlayback(itemid, dbid):
    """
    Called only for a SINGLE element, not playQueues

    Always to return with a "setResolvedUrl"
    """
    if dbid == 'plexnode':
        # Plex redirect, e.g. watch later. Need to get actual URLs
        xml = downloadutils.DownloadUtils().downloadUrl(itemid,
                                                        authenticate=False)
        if xml in (None, 401):
            utils.logMsg(title, "Could not resolve url %s" % itemid, -1)
            return xbmcplugin.setResolvedUrl(
                int(sys.argv[1]), False, xbmcgui.ListItem())
        return pbutils.PlaybackUtils(xml).play(None, dbid)

    if utils.window('plex_authenticated') != "true":
        utils.logMsg('doPlayback', 'Not yet authenticated for a PMS, abort '
                     'starting playback', -1)
        string = xbmcaddon.Addon().getLocalizedString
        # Not yet connected to a PMS server
        xbmcgui.Dialog().notification(
            addonName,
            string(39210),
            xbmcgui.NOTIFICATION_ERROR,
            7000,
            True)
        return xbmcplugin.setResolvedUrl(
            int(sys.argv[1]), False, xbmcgui.ListItem())

    xml = PlexFunctions.GetPlexMetadata(itemid)
    if xml in (None, 401):
        return xbmcplugin.setResolvedUrl(
            int(sys.argv[1]), False, xbmcgui.ListItem())
    # Everything OK
    return pbutils.PlaybackUtils(xml).play(itemid, dbid)

    # utils.logMsg(title, "doPlayback called with itemid=%s, dbid=%s"
    #              % (itemid, dbid), 1)
    # item = PlexFunctions.GetPlexMetadata(itemid)
    # API = PlexAPI.API(item[0])
    # # If resume != 0, then we don't need to build a playlist for trailers etc.
    # # No idea how we could otherwise get resume timing out of Kodi
    # resume, runtime = API.getRuntime()
    # if resume == 0:
    #     uuid = item.attrib.get('librarySectionUUID', None)
    #     if uuid:
    #         if utils.settings('askCinema') == "true":
    #             trailers = xbmcgui.Dialog().yesno(addonName, "Play trailers?")
    #         else:
    #             trailers = True
    #         if trailers:
    #             playQueue = PlexFunctions.GetPlexPlaylist(
    #                 API.getRatingKey(), uuid, mediatype=API.getType())
    #             if playQueue is not None:
    #                 return PassPlaylist(playQueue)
    #             else:
    #                 utils.logMsg(title, "Error: no valid playQueue", -1)
    #     else:
    #         # E.g trailers being directly played
    #         utils.logMsg(title, "No librarySectionUUID found.", 1)

    # # Play only 1 item, not playQueue
    # pbutils.PlaybackUtils(item).StartPlay(resume=resume,
    #                                       resumeId=None)


##### DO RESET AUTH #####
def resetAuth():
    # User tried login and failed too many times
    string = xbmcaddon.Addon().getLocalizedString
    resp = xbmcgui.Dialog().yesno(
        heading="Warning",
        line1=string(39206))
    if resp == 1:
        utils.logMsg("PLEX", "Reset login attempts.", 1)
        utils.window('emby_serverStatus', value="Auth")
    else:
        xbmc.executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')
def addDirectoryItem(label, path, folder=True):
    li = xbmcgui.ListItem(label, path=path)
    li.setThumbnailImage("special://home/addons/plugin.video.plexkodiconnect/icon.png")
    li.setArt({"fanart":"special://home/addons/plugin.video.plexkodiconnect/fanart.jpg"})
    li.setArt({"landscape":"special://home/addons/plugin.video.plexkodiconnect/fanart.jpg"})
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=folder)

def doMainListing():
    string = xbmcaddon.Addon().getLocalizedString
    xbmcplugin.setContent(int(sys.argv[1]), 'files')    
    # Get emby nodes from the window props
    embyprops = utils.window('Emby.nodes.total')
    if embyprops:
        totalnodes = int(embyprops)
        for i in range(totalnodes):
            path = utils.window('Emby.nodes.%s.index' % i)
            if not path:
                path = utils.window('Emby.nodes.%s.content' % i)
            label = utils.window('Emby.nodes.%s.title' % i)
            node_type = utils.window('Emby.nodes.%s.type' % i)
            #because we do not use seperate entrypoints for each content type, we need to figure out which items to show in each listing.
            #for now we just only show picture nodes in the picture library video nodes in the video library and all nodes in any other window
            if path and xbmc.getCondVisibility("Window.IsActive(Pictures)") and node_type == "photos":
                addDirectoryItem(label, path)
            elif path and xbmc.getCondVisibility("Window.IsActive(VideoLibrary)") and node_type != "photos":
                addDirectoryItem(label, path)
            elif path and not xbmc.getCondVisibility("Window.IsActive(VideoLibrary) | Window.IsActive(Pictures) | Window.IsActive(MusicLibrary)"):
                addDirectoryItem(label, path)

    # Plex Watch later
    addDirectoryItem(string(39211),
                     "plugin://plugin.video.plexkodiconnect/?mode=watchlater")
    # Plex user switch
    addDirectoryItem(string(39200) + utils.window('plex_username'),
                     "plugin://plugin.video.plexkodiconnect/"
                     "?mode=switchuser")

    #experimental live tv nodes
    # addDirectoryItem("Live Tv Channels (experimental)", "plugin://plugin.video.plexkodiconnect/?mode=browsecontent&type=tvchannels&folderid=root")
    # addDirectoryItem("Live Tv Recordings (experimental)", "plugin://plugin.video.plexkodiconnect/?mode=browsecontent&type=recordings&folderid=root")

    # some extra entries for settings and stuff. TODO --> localize the labels
    addDirectoryItem(string(39201), "plugin://plugin.video.plexkodiconnect/?mode=settings")
    # addDirectoryItem("Add user to session", "plugin://plugin.video.plexkodiconnect/?mode=adduser")
    addDirectoryItem(string(39203), "plugin://plugin.video.plexkodiconnect/?mode=refreshplaylist")
    addDirectoryItem(string(39204), "plugin://plugin.video.plexkodiconnect/?mode=manualsync")

    xbmcplugin.endOfDirectory(int(sys.argv[1]))


##### Generate a new deviceId
def resetDeviceId():

    dialog = xbmcgui.Dialog()
    language = utils.language

    deviceId_old = utils.window('plex_client_Id')
    try:
        deviceId = clientinfo.ClientInfo().getDeviceId(reset=True)
    except Exception as e:
        utils.logMsg(addonName,
                     "Failed to generate a new device Id: %s" % e, 1)
        dialog.ok(
            heading=addonName,
            line1=language(33032))
    else:
        utils.logMsg(addonName,
                     "Successfully removed old deviceId: %s New deviceId: %s"
                     % (deviceId_old, deviceId), 1)
        dialog.ok(
            heading=addonName,
            line1=language(33033))
        xbmc.executebuiltin('RestartApp')

##### Delete Item
def deleteItem():

    # Serves as a keymap action
    if xbmc.getInfoLabel('ListItem.Property(embyid)'): # If we already have the embyid
        embyid = xbmc.getInfoLabel('ListItem.Property(embyid)')
    else:
        dbid = xbmc.getInfoLabel('ListItem.DBID')
        itemtype = xbmc.getInfoLabel('ListItem.DBTYPE')

        if not itemtype:

            if xbmc.getCondVisibility('Container.Content(albums)'):
                itemtype = "album"
            elif xbmc.getCondVisibility('Container.Content(artists)'):
                itemtype = "artist"
            elif xbmc.getCondVisibility('Container.Content(songs)'):
                itemtype = "song"
            elif xbmc.getCondVisibility('Container.Content(pictures)'):
                itemtype = "picture"
            else:
                utils.logMsg("EMBY delete", "Unknown type, unable to proceed.", 1)
                return

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)
        item = emby_db.getItem_byKodiId(dbid, itemtype)
        embycursor.close()

        try:
            embyid = item[0]
        except TypeError:
            utils.logMsg("EMBY delete", "Unknown embyId, unable to proceed.", 1)
            return

    if utils.settings('skipContextMenu') != "true":
        resp = xbmcgui.Dialog().yesno(
                                heading="Confirm delete",
                                line1=("Delete file from Emby Server? This will "
                                        "also delete the file(s) from disk!"))
        if not resp:
            utils.logMsg("EMBY delete", "User skipped deletion for: %s." % embyid, 1)
            return
    
    doUtils = downloadutils.DownloadUtils()
    url = "{server}/emby/Items/%s?format=json" % embyid
    utils.logMsg("EMBY delete", "Deleting request: %s" % embyid, 0)
    doUtils.downloadUrl(url, action_type="DELETE")

##### ADD ADDITIONAL USERS #####
def addUser():

    doUtils = downloadutils.DownloadUtils()
    art = artwork.Artwork()
    clientInfo = clientinfo.ClientInfo()
    deviceId = clientInfo.getDeviceId()
    deviceName = clientInfo.getDeviceName()
    userid = utils.window('currUserId')
    dialog = xbmcgui.Dialog()

    # Get session
    url = "{server}/emby/Sessions?DeviceId=%s&format=json" % deviceId
    result = doUtils.downloadUrl(url)
    
    try:
        sessionId = result[0]['Id']
        additionalUsers = result[0]['AdditionalUsers']
        # Add user to session
        userlist = {}
        users = []
        url = "{server}/emby/Users?IsDisabled=false&IsHidden=false&format=json"
        result = doUtils.downloadUrl(url)

        # pull the list of users
        for user in result:
            name = user['Name']
            userId = user['Id']
            if userid != userId:
                userlist[name] = userId
                users.append(name)

        # Display dialog if there's additional users
        if additionalUsers:

            option = dialog.select("Add/Remove user from the session", ["Add user", "Remove user"])
            # Users currently in the session
            additionalUserlist = {}
            additionalUsername = []
            # Users currently in the session
            for user in additionalUsers:
                name = user['UserName']
                userId = user['UserId']
                additionalUserlist[name] = userId
                additionalUsername.append(name)

            if option == 1:
                # User selected Remove user
                resp = dialog.select("Remove user from the session", additionalUsername)
                if resp > -1:
                    selected = additionalUsername[resp]
                    selected_userId = additionalUserlist[selected]
                    url = "{server}/emby/Sessions/%s/Users/%s" % (sessionId, selected_userId)
                    doUtils.downloadUrl(url, postBody={}, action_type="DELETE")
                    dialog.notification(
                            heading="Success!",
                            message="%s removed from viewing session" % selected,
                            icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                            time=1000)

                    # clear picture
                    position = utils.window('EmbyAdditionalUserPosition.%s' % selected_userId)
                    utils.window('EmbyAdditionalUserImage.%s' % position, clear=True)
                    return
                else:
                    return

            elif option == 0:
                # User selected Add user
                for adduser in additionalUsername:
                    try: # Remove from selected already added users. It is possible they are hidden.
                        users.remove(adduser)
                    except: pass

            elif option < 0:
                # User cancelled
                return

        # Subtract any additional users
        utils.logMsg("EMBY", "Displaying list of users: %s" % users)
        resp = dialog.select("Add user to the session", users)
        # post additional user
        if resp > -1:
            selected = users[resp]
            selected_userId = userlist[selected]
            url = "{server}/emby/Sessions/%s/Users/%s" % (sessionId, selected_userId)
            doUtils.downloadUrl(url, postBody={}, action_type="POST")
            dialog.notification(
                    heading="Success!",
                    message="%s added to viewing session" % selected,
                    icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                    time=1000)

    except:
        utils.logMsg("EMBY", "Failed to add user to session.")
        dialog.notification(
                heading="Error",
                message="Unable to add/remove user from the session.",
                icon=xbmcgui.NOTIFICATION_ERROR)

    # Add additional user images
    # always clear the individual items first
    totalNodes = 10
    for i in range(totalNodes):
        if not utils.window('EmbyAdditionalUserImage.%s' % i):
            break
        utils.window('EmbyAdditionalUserImage.%s' % i, clear=True)

    url = "{server}/emby/Sessions?DeviceId=%s" % deviceId
    result = doUtils.downloadUrl(url)
    additionalUsers = result[0]['AdditionalUsers']
    count = 0
    for additionaluser in additionalUsers:
        userid = additionaluser['UserId']
        url = "{server}/emby/Users/%s?format=json" % userid
        result = doUtils.downloadUrl(url)
        utils.window('EmbyAdditionalUserImage.%s' % count,
            value=art.getUserArtwork(result['Id'], 'Primary'))
        utils.window('EmbyAdditionalUserPosition.%s' % userid, value=str(count))
        count +=1


def switchPlexUser():
    """
    Signs out currently logged in user (if applicable). Triggers sign-in of a
    new user
    """
    # Guess these user avatars are a future feature. Skipping for now
    # Delete any userimages. Since there's always only 1 user: position = 0
    # position = 0
    # utils.window('EmbyAdditionalUserImage.%s' % position, clear=True)
    utils.logMsg(title, "Plex home user switch requested", 0)
    if not __LogOut():
        return

    # First remove playlists of old user
    utils.deletePlaylists()
    # Remove video nodes
    utils.deleteNodes()
    __LogIn()


##### THEME MUSIC/VIDEOS #####
def getThemeMedia():

    doUtils = downloadutils.DownloadUtils()
    dialog = xbmcgui.Dialog()
    playback = None

    # Choose playback method
    resp = dialog.select("Playback method for your themes", ["Direct Play", "Direct Stream"])
    if resp == 0:
        playback = "DirectPlay"
    elif resp == 1:
        playback = "DirectStream"
    else:
        return

    library = utils.tryDecode(xbmc.translatePath(
                "special://profile/addon_data/plugin.video.plexkodiconnect/library/"))
    # Create library directory
    if not utils.IfExists(library):
        xbmcvfs.mkdir(library)

    # Set custom path for user
    tvtunes_path = utils.tryDecode(xbmc.translatePath(
        "special://profile/addon_data/script.tvtunes/"))
    if xbmcvfs.exists(tvtunes_path):
        tvtunes = xbmcaddon.Addon(id="script.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', library)
        utils.logMsg("EMBY", "TV Tunes custom path is enabled and set.", 1)
    else:
        # if it does not exist this will not work so warn user
        # often they need to edit the settings first for it to be created.
        dialog.ok(
            heading="Warning",
            line1=(
                "The settings file does not exist in tvtunes. ",
                "Go to the tvtunes addon and change a setting, then come back and re-run."))
        xbmc.executebuiltin('Addon.OpenSettings(script.tvtunes)')
        return
        
    # Get every user view Id
    with embydb.GetEmbyDB() as emby_db:
        viewids = emby_db.getViews()

    # Get Ids with Theme Videos
    itemIds = {}
    for view in viewids:
        url = "{server}/emby/Users/{UserId}/Items?HasThemeVideo=True&ParentId=%s&format=json" % view
        result = doUtils.downloadUrl(url)
        if result['TotalRecordCount'] != 0:
            for item in result['Items']:
                itemId = item['Id']
                folderName = item['Name']
                folderName = utils.normalize_string(
                    utils.tryEncode(folderName))
                itemIds[itemId] = folderName

    # Get paths for theme videos
    for itemId in itemIds:
        nfo_path = xbmc.translatePath(
            "special://profile/addon_data/plugin.video.plexkodiconnect/library/%s/" % itemIds[itemId])
        # Create folders for each content
        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)
        # Where to put the nfos
        nfo_path = "%s%s" % (nfo_path, "tvtunes.nfo")

        url = "{server}/emby/Items/%s/ThemeVideos?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # Create nfo and write themes to it
        nfo_file = xbmcvfs.File(nfo_path, 'w')
        pathstowrite = ""
        # May be more than one theme
        for theme in result['Items']:
            putils = playutils.PlayUtils(theme)
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % utils.tryEncode(playurl))

        # Check if the item has theme songs and add them   
        url = "{server}/emby/Items/%s/ThemeSongs?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # May be more than one theme
        for theme in result['Items']:
            putils = playutils.PlayUtils(theme)  
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % utils.tryEncode(playurl))

        nfo_file.write(
            '<tvtunes>%s</tvtunes>' % pathstowrite
        )
        # Close nfo file
        nfo_file.close()

    # Get Ids with Theme songs
    musicitemIds = {}
    for view in viewids:
        url = "{server}/emby/Users/{UserId}/Items?HasThemeSong=True&ParentId=%s&format=json" % view
        result = doUtils.downloadUrl(url)
        if result['TotalRecordCount'] != 0:
            for item in result['Items']:
                itemId = item['Id']
                folderName = item['Name']
                folderName = utils.normalize_string(
                    utils.tryEncode(folderName))
                musicitemIds[itemId] = folderName

    # Get paths
    for itemId in musicitemIds:
        
        # if the item was already processed with video themes back out
        if itemId in itemIds:
            continue
        
        nfo_path = xbmc.translatePath(
            "special://profile/addon_data/plugin.video.plexkodiconnect/library/%s/" % musicitemIds[itemId])
        # Create folders for each content
        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)
        # Where to put the nfos
        nfo_path = "%s%s" % (nfo_path, "tvtunes.nfo")
        
        url = "{server}/emby/Items/%s/ThemeSongs?format=json" % itemId
        result = doUtils.downloadUrl(url)

        # Create nfo and write themes to it
        nfo_file = xbmcvfs.File(nfo_path, 'w')
        pathstowrite = ""
        # May be more than one theme
        for theme in result['Items']: 
            putils = playutils.PlayUtils(theme)
            if playback == "DirectPlay":
                playurl = putils.directPlay()
            else:
                playurl = putils.directStream()
            pathstowrite += ('<file>%s</file>' % utils.tryEncode(playurl))

        nfo_file.write(
            '<tvtunes>%s</tvtunes>' % pathstowrite
        )
        # Close nfo file
        nfo_file.close()

    dialog.notification(
            heading="Emby for Kodi",
            message="Themes added!",
            icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
            time=1000,
            sound=False)

##### REFRESH EMBY PLAYLISTS #####
def refreshPlaylist():
    utils.logMsg(addonName, 'Requesting playlist/nodes refresh', 0)
    utils.window('plex_runLibScan', value="views")


#### SHOW SUBFOLDERS FOR NODE #####
def GetSubFolders(nodeindex):
    nodetypes = ["",".recent",".recentepisodes",".inprogress",".inprogressepisodes",".unwatched",".nextepisodes",".sets",".genres",".random",".recommended"]
    for node in nodetypes:
        title = utils.window('Emby.nodes.%s%s.title' %(nodeindex,node))
        if title:
            path = utils.window('Emby.nodes.%s%s.content' %(nodeindex,node))
            addDirectoryItem(title, path)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
              
##### BROWSE EMBY NODES DIRECTLY #####    
def BrowseContent(viewname, browse_type="", folderid=""):
    
    emby = embyserver.Read_EmbyServer()
    art = artwork.Artwork()
    doUtils = downloadutils.DownloadUtils()
    
    #folderid used as filter ?
    if folderid in ["recent","recentepisodes","inprogress","inprogressepisodes","unwatched","nextepisodes","sets","genres","random","recommended"]:
        filter_type = folderid
        folderid = ""
    else:
        filter_type = ""
    
    xbmcplugin.setPluginCategory(int(sys.argv[1]), viewname)
    #get views for root level
    if not folderid:
        views = PlexFunctions.GetPlexCollections()
        for view in views:
            if view.get("name") == utils.tryDecode(viewname):
                folderid = view.get("id")
                break
    
    if viewname is not None:
        utils.logMsg("BrowseContent", "viewname: %s - type: %s - folderid: %s "
                     "- filter: %s" % (utils.tryDecode(viewname),
                                      utils.tryDecode(browse_type),
                                      utils.tryDecode(folderid),
                                      utils.tryDecode(filter_type)))
    #set the correct params for the content type
    #only proceed if we have a folderid
    if folderid:
        if browse_type.lower() == "homevideos":
            xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
            itemtype = "Video,Folder,PhotoAlbum"
        elif browse_type.lower() == "photos":
            xbmcplugin.setContent(int(sys.argv[1]), 'files')
            itemtype = "Photo,PhotoAlbum,Folder"
        else:
            itemtype = ""
        
        #get the actual listing
        if browse_type == "recordings":
            listing = emby.getTvRecordings(folderid)
        elif browse_type == "tvchannels":
            listing = emby.getTvChannels()
        elif filter_type == "recent":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="DateCreated", recursive=True, limit=25, sortorder="Descending")
        elif filter_type == "random":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="Random", recursive=True, limit=150, sortorder="Descending")
        elif filter_type == "recommended":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[0], sortby="SortName", recursive=True, limit=25, sortorder="Ascending", filter_type="IsFavorite")
        elif filter_type == "sets":
            listing = emby.getFilteredSection(folderid, itemtype=itemtype.split(",")[1], sortby="SortName", recursive=True, limit=25, sortorder="Ascending", filter_type="IsFavorite")
        else:
            listing = emby.getFilteredSection(folderid, itemtype=itemtype, recursive=False)
        
        #process the listing
        if listing:
            for item in listing.get("Items"):
                li = createListItemFromEmbyItem(item,art,doUtils)
                if item.get("IsFolder") == True:
                    #for folders we add an additional browse request, passing the folderId
                    path = "%s?id=%s&mode=browsecontent&type=%s&folderid=%s" \
                           % (utils.tryDecode(sys.argv[0]),
                              utils.tryDecode(viewname),
                              utils.tryDecode(browse_type),
                              utils.tryDecode(item.get("Id")))
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=True)
                else:
                    #playable item, set plugin path and mediastreams
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=li.getProperty("path"), listitem=li)


    if filter_type == "recent":
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
    else:
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### CREATE LISTITEM FROM EMBY METADATA #####
def createListItemFromEmbyItem(item,art=artwork.Artwork(),doUtils=downloadutils.DownloadUtils()):
    API = PlexAPI.API(item)
    itemid = item['Id']
    
    title = item.get('Name')
    li = xbmcgui.ListItem(title)
    
    premieredate = item.get('PremiereDate',"")
    if not premieredate: premieredate = item.get('DateCreated',"")
    if premieredate:
        premieredatelst = premieredate.split('T')[0].split("-")
        premieredate = "%s.%s.%s" %(premieredatelst[2],premieredatelst[1],premieredatelst[0])

    li.setProperty("embyid",itemid)
    
    allart = art.getAllArtwork(item)
    
    if item["Type"] == "Photo":
        #listitem setup for pictures...
        img_path = allart.get('Primary')
        li.setProperty("path",img_path)
        picture = doUtils.downloadUrl("{server}/Items/%s/Images" %itemid)
        if picture:
            picture = picture[0]
            if picture.get("Width") > picture.get("Height"):
                li.setArt( {"fanart":  img_path}) #add image as fanart for use with skinhelper auto thumb/backgrund creation
            li.setInfo('pictures', infoLabels={ "picturepath": img_path, "date": premieredate, "size": picture.get("Size"), "exif:width": str(picture.get("Width")), "exif:height": str(picture.get("Height")), "title": title})
        li.setThumbnailImage(img_path)
        li.setProperty("plot",API.getOverview())
        li.setIconImage('DefaultPicture.png')
    else:
        #normal video items
        li.setProperty('IsPlayable', 'true')
        path = "%s?id=%s&mode=play" % (sys.argv[0], item.get("Id"))
        li.setProperty("path",path)
        genre = API.getGenres()
        overlay = 0
        userdata = API.getUserData()
        runtime = item.get("RunTimeTicks",0)/ 10000000.0
        seektime = userdata['Resume']
        if seektime:
            li.setProperty("resumetime", str(seektime))
            li.setProperty("totaltime", str(runtime))
        
        played = userdata['Played']
        if played: overlay = 7
        else: overlay = 6       
        playcount = userdata['PlayCount']
        if playcount is None:
            playcount = 0
            
        rating = item.get('CommunityRating')
        if not rating: rating = userdata['UserRating']

        # Populate the extradata list and artwork
        extradata = {
            'id': itemid,
            'rating': rating,
            'year': item.get('ProductionYear'),
            'genre': genre,
            'playcount': str(playcount),
            'title': title,
            'plot': API.getOverview(),
            'Overlay': str(overlay),
            'duration': runtime
        }
        if premieredate:
            extradata["premieredate"] = premieredate
            extradata["date"] = premieredate
        li.setInfo('video', infoLabels=extradata)
        if allart.get('Primary'):
            li.setThumbnailImage(allart.get('Primary'))
        else: li.setThumbnailImage('DefaultTVShows.png')
        li.setIconImage('DefaultTVShows.png')
        if not allart.get('Background'): #add image as fanart for use with skinhelper auto thumb/backgrund creation
            li.setArt( {"fanart": allart.get('Primary') } )
        else:
            pbutils.PlaybackUtils(item).setArtwork(li)

        mediastreams = API.getMediaStreams()
        videostreamFound = False
        if mediastreams:
            for key, value in mediastreams.iteritems():
                if key == "video" and value: videostreamFound = True
                if value: li.addStreamInfo(key, value[0])
        if not videostreamFound:
            #just set empty streamdetails to prevent errors in the logs
            li.addStreamInfo("video", {'duration': runtime})
        
    return li
    
##### BROWSE EMBY CHANNELS #####    
def BrowseChannels(itemid, folderid=None):
    
    _addon_id   =   int(sys.argv[1])
    _addon_url  =   sys.argv[0]
    doUtils = downloadutils.DownloadUtils()
    art = artwork.Artwork()

    xbmcplugin.setContent(int(sys.argv[1]), 'files')
    if folderid:
        url = (
                "{server}/emby/Channels/%s/Items?userid={UserId}&folderid=%s&format=json"
                % (itemid, folderid))
    elif itemid == "0":
        # id 0 is the root channels folder
        url = "{server}/emby/Channels?{UserId}&format=json"
    else:
        url = "{server}/emby/Channels/%s/Items?UserId={UserId}&format=json" % itemid

    result = doUtils.downloadUrl(url)
    if result and result.get("Items"):
        for item in result.get("Items"):
            itemid = item['Id']
            itemtype = item['Type']
            li = createListItemFromEmbyItem(item,art,doUtils)
            if itemtype == "ChannelFolderItem":
                isFolder = True
            else:
                isFolder = False
            channelId = item.get('ChannelId', "")
            channelName = item.get('ChannelName', "")
            if itemtype == "Channel":
                path = "%s?id=%s&mode=channels" % (_addon_url, itemid)
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li, isFolder=True)
            elif isFolder:
                path = "%s?id=%s&mode=channelsfolder&folderid=%s" % (_addon_url, channelId, itemid)
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li, isFolder=True)
            else:
                path = "%s?id=%s&mode=play" % (_addon_url, itemid)
                li.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=path, listitem=li)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### LISTITEM SETUP FOR VIDEONODES #####
def createListItem(item, appendShowTitle=False, appendSxxExx=False):
    title = item['title']
    li = xbmcgui.ListItem(title)
    li.setProperty('IsPlayable', "true")

    metadata = {
        'duration': str(item['runtime']/60),
        'Plot': item['plot'],
        'Playcount': item['playcount']
    }

    if "episode" in item:
        episode = item['episode']
        metadata['Episode'] = episode

    if "season" in item:
        season = item['season']
        metadata['Season'] = season

    if season and episode:
        li.setProperty('episodeno', "s%.2de%.2d" % (season, episode))
        if appendSxxExx is True:
            title = "S%.2dE%.2d - %s" % (season, episode, title)

    if "firstaired" in item:
        metadata['Premiered'] = item['firstaired']

    if "showtitle" in item:
        metadata['TVshowTitle'] = item['showtitle']
        if appendShowTitle is True:
            title = item['showtitle'] + ' - ' + title

    if "rating" in item:
        metadata['Rating'] = str(round(float(item['rating']),1))

    if "director" in item:
        metadata['Director'] = " / ".join(item['director'])

    if "writer" in item:
        metadata['Writer'] = " / ".join(item['writer'])

    if "cast" in item:
        cast = []
        castandrole = []
        for person in item['cast']:
            name = person['name']
            cast.append(name)
            castandrole.append((name, person['role']))
        metadata['Cast'] = cast
        metadata['CastAndRole'] = castandrole

    metadata['Title'] = title
    li.setLabel(title)

    li.setInfo(type="Video", infoLabels=metadata)  
    li.setProperty('resumetime', str(item['resume']['position']))
    li.setProperty('totaltime', str(item['resume']['total']))
    li.setArt(item['art'])
    li.setThumbnailImage(item['art'].get('thumb',''))
    li.setIconImage('DefaultTVShows.png')
    li.setProperty('dbid', str(item['episodeid']))
    li.setProperty('fanart_image', item['art'].get('tvshow.fanart',''))
    for key, value in item['streamdetails'].iteritems():
        for stream in value:
            li.addStreamInfo(key, stream)
    
    return li

##### GET NEXTUP EPISODES FOR TAGNAME #####    
def getNextUpEpisodes(tagname, limit):
    
    count = 0
    # if the addon is called with nextup parameter,
    # we return the nextepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the TV shows - filtered by tag
    query = {

        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {

            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % tagname}
                ]},
            'properties': ['title', 'studio', 'mpaa', 'file', 'art']
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        pass
    else:
        for item in items:
            if utils.settings('ignoreSpecialsNextEpisodes') == "true":
                query = {

                    'jsonrpc': "2.0",
                    'id': 1,
                    'method': "VideoLibrary.GetEpisodes",
                    'params': {

                        'tvshowid': item['tvshowid'],
                        'sort': {'method': "episode"},
                        'filter': {
                            'and': [
                                {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                                {'operator': "greaterthan", 'field': "season", 'value': "0"}
                        ]},
                        'properties': [
                            "title", "playcount", "season", "episode", "showtitle",
                            "plot", "file", "rating", "resume", "tvshowid", "art",
                            "streamdetails", "firstaired", "runtime", "writer",
                            "dateadded", "lastplayed"
                        ],
                        'limits': {"end": 1}
                    }
                }
            else:
                query = {

                    'jsonrpc': "2.0",
                    'id': 1,
                    'method': "VideoLibrary.GetEpisodes",
                    'params': {

                        'tvshowid': item['tvshowid'],
                        'sort': {'method': "episode"},
                        'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                        'properties': [
                            "title", "playcount", "season", "episode", "showtitle",
                            "plot", "file", "rating", "resume", "tvshowid", "art",
                            "streamdetails", "firstaired", "runtime", "writer",
                            "dateadded", "lastplayed"
                        ],
                        'limits': {"end": 1}
                    }
                }

            result = xbmc.executeJSONRPC(json.dumps(query))
            result = json.loads(result)
            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                pass
            else:
                for episode in episodes:
                    li = createListItem(episode)
                    xbmcplugin.addDirectoryItem(
                                handle=int(sys.argv[1]),
                                url=episode['file'],
                                listitem=li)
                    count += 1

            if count == limit:
                break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET INPROGRESS EPISODES FOR TAGNAME #####    
def getInProgressEpisodes(tagname, limit):
    
    count = 0
    # if the addon is called with inprogressepisodes parameter,
    # we return the inprogressepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the in-progress TV shows - filtered by tag
    query = {

        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {

            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % tagname}
                ]},
            'properties': ['title', 'studio', 'mpaa', 'file', 'art']
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        pass
    else:
        for item in items:
            query = {

                'jsonrpc': "2.0",
                'id': 1,
                'method': "VideoLibrary.GetEpisodes",
                'params': {

                    'tvshowid': item['tvshowid'],
                    'sort': {'method': "episode"},
                    'filter': {'operator': "true", 'field': "inprogress", 'value': ""},
                    'properties': [
                        "title", "playcount", "season", "episode", "showtitle", "plot",
                        "file", "rating", "resume", "tvshowid", "art", "cast",
                        "streamdetails", "firstaired", "runtime", "writer",
                        "dateadded", "lastplayed"
                    ]
                }
            }
            result = xbmc.executeJSONRPC(json.dumps(query))
            result = json.loads(result)
            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                pass
            else:
                for episode in episodes:
                    li = createListItem(episode)
                    xbmcplugin.addDirectoryItem(
                                handle=int(sys.argv[1]),
                                url=episode['file'],
                                listitem=li)
                    count += 1

            if count == limit:
                break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET RECENT EPISODES FOR TAGNAME #####    
# def getRecentEpisodes(tagname, limit):
def getRecentEpisodes(viewid, mediatype, tagname, limit):
    count = 0
    # if the addon is called with recentepisodes parameter,
    # we return the recentepisodes list of the given tagname
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    appendShowTitle = utils.settings('RecentTvAppendShow') == 'true'
    appendSxxExx = utils.settings('RecentTvAppendSeason') == 'true'
    # First we get a list of all the TV shows - filtered by tag
    query = {
        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {
            'sort': {'order': "descending", 'method': "dateadded"},
            'filter': {'operator': "is", 'field': "tag", 'value': "%s" % tagname},
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result'][mediatype]
    except (KeyError, TypeError):
        # No items, empty folder
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
        return

    allshowsIds = set()
    for item in items:
        allshowsIds.add(item['tvshowid'])

    query = {
        'jsonrpc': "2.0",
        'id': 1,
        'method': "VideoLibrary.GetEpisodes",
        'params': {
            'sort': {'order': "descending", 'method': "dateadded"},
            'properties': [
                "title", "playcount", "season", "episode", "showtitle", "plot",
                "file", "rating", "resume", "tvshowid", "art", "streamdetails",
                "firstaired", "runtime", "cast", "writer", "dateadded", "lastplayed"
            ],
            "limits": {"end": limit}
        }
    }
    if utils.settings('TVShowWatched') == 'false':
        query['params']['filter'] = {
            'operator': "lessthan",
            'field': "playcount",
            'value': "1"
        }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    try:
        episodes = result['result']['episodes']
    except (KeyError, TypeError):
        pass
    else:
        for episode in episodes:
            if episode['tvshowid'] in allshowsIds:
                li = createListItem(episode,
                                    appendShowTitle=appendShowTitle,
                                    appendSxxExx=appendSxxExx)
                xbmcplugin.addDirectoryItem(
                            handle=int(sys.argv[1]),
                            url=episode['file'],
                            listitem=li)
                count += 1

            if count == limit:
                break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))


def getVideoFiles(plexId, params):
    """
    GET VIDEO EXTRAS FOR LISTITEM

    returns the video files for the item as plugin listing, can be used for
    browsing the actual files or videoextras etc.
    """
    if plexId is None:
        filename = params.get('filename')
        if filename is not None:
            filename = filename[0]
            import re
            regex = re.compile(r'''library/metadata/(\d+)''')
            filename = regex.findall(filename)
            try:
                plexId = filename[0]
            except IndexError:
                pass

    if plexId is None:
        utils.logMsg(title, 'No Plex ID found, abort getting Extras', 0)
        return xbmcplugin.endOfDirectory(int(sys.argv[1]))

    item = PlexFunctions.GetPlexMetadata(plexId)
    try:
        path = item[0][0][0].attrib['file']
    except:
        utils.logMsg(title, 'Could not get file path for item %s'
                     % plexId, -1)
        return xbmcplugin.endOfDirectory(int(sys.argv[1]))
    # Assign network protocol
    if path.startswith('\\\\'):
        path = path.replace('\\\\', 'smb://')
        path = path.replace('\\', '/')
    # Plex returns Windows paths as e.g. 'c:\slfkjelf\slfje\file.mkv'
    elif '\\' in path:
        path = path.replace('\\', '\\\\')
    # Directory only, get rid of filename (!! exists() needs /  or \ at end)
    path = path.replace(os.path.basename(path), '')
    # Only proceed if we can access this folder
    if xbmcvfs.exists(path):
        # Careful, returns encoded strings!
        dirs, files = xbmcvfs.listdir(path)
        for file in files:
            file = path + utils.tryDecode(file)
            li = xbmcgui.ListItem(file, path=file)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=utils.tryEncode(file),
                                        listitem=li)
        for dir in dirs:
            dir = path + utils.tryDecode(dir)
            li = xbmcgui.ListItem(dir, path=dir)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=utils.tryEncode(dir),
                                        listitem=li,
                                        isFolder=True)
    else:
        utils.logMsg(title, 'Kodi cannot access folder %s' % path, 0)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


##### GET EXTRAFANART FOR LISTITEM #####
def getExtraFanArt(embyId,embyPath):
    
    emby = embyserver.Read_EmbyServer()
    art = artwork.Artwork()
    
    # Get extrafanart for listitem 
    # will be called by skinhelper script to get the extrafanart
    try:
        # for tvshows we get the embyid just from the path
        if not embyId:
            if "plugin.video.emby" in embyPath:
                embyId = embyPath.split("/")[-2]
        
        if embyId:
            #only proceed if we actually have a emby id
            utils.logMsg("EMBY", "Requesting extrafanart for Id: %s" % embyId, 0)

            # We need to store the images locally for this to work
            # because of the caching system in xbmc
            fanartDir = utils.tryDecode(xbmc.translatePath(
                "special://thumbnails/emby/%s/" % embyId))
            
            if not xbmcvfs.exists(fanartDir):
                # Download the images to the cache directory
                xbmcvfs.mkdirs(fanartDir)
                item = emby.getItem(embyId)
                if item:
                    backdrops = art.getAllArtwork(item)['Backdrop']
                    tags = item['BackdropImageTags']
                    count = 0
                    for backdrop in backdrops:
                        # Same ordering as in artwork
                        tag = tags[count]
                        if os.path.supports_unicode_filenames:
                            fanartFile = os.path.join(fanartDir, "fanart%s.jpg" % tag)
                        else:
                            fanartFile = os.path.join(
                                utils.tryEncode(fanartDir),
                                "fanart%s.jpg" % utils.tryEncode(tag))
                        li = xbmcgui.ListItem(tag, path=fanartFile)
                        xbmcplugin.addDirectoryItem(
                                            handle=int(sys.argv[1]),
                                            url=fanartFile,
                                            listitem=li)
                        xbmcvfs.copy(backdrop, fanartFile) 
                        count += 1               
            else:
                utils.logMsg("EMBY", "Found cached backdrop.", 2)
                # Use existing cached images
                dirs, files = xbmcvfs.listdir(fanartDir)
                for file in files:
                    fanartFile = os.path.join(fanartDir, utils.tryDecode(file))
                    li = xbmcgui.ListItem(file, path=fanartFile)
                    xbmcplugin.addDirectoryItem(
                                            handle=int(sys.argv[1]),
                                            url=fanartFile,
                                            listitem=li)
    except Exception as e:
        utils.logMsg("EMBY", "Error getting extrafanart: %s" % e, 0)
    
    # Always do endofdirectory to prevent errors in the logs
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def RunLibScan(mode):
    if utils.window('emby_online') != "true":
        # Server is not online, do not run the sync
        string = xbmcaddon.Addon().getLocalizedString
        xbmcgui.Dialog().ok(heading=addonName,
                            line1=string(39205))
    else:
        utils.window('plex_runLibScan', value='full')


def BrowsePlexContent(viewid, mediatype="", nodetype=""):
    """
    Plex:
        viewid:          PMS name of the library
        mediatype:       mediatype, e.g. 'movies', 'tvshows', 'photos'
        nodetype:        e.g. 'ondeck'
    """
    utils.logMsg(title, "BrowsePlexContent called with viewid: %s, mediatype: %s, nodetype: %s" % (viewid, mediatype, nodetype), 1)

    if nodetype == 'ondeck':
        xml = PlexFunctions.GetPlexOnDeck(
            viewid,
            containerSize=int(utils.settings('limitindex')))
        if not xml:
            utils.logMsg(title, "Cannot get view for section %s" % viewid, -1)
            return

    viewname = xml.attrib.get('librarySectionTitle')
    xbmcplugin.setPluginCategory(int(sys.argv[1]), viewname)

    # set the correct params for the content type
    if mediatype.lower() == "homevideos, tvshows":
        xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
        itemtype = "Video,Folder,PhotoAlbum"
    elif mediatype.lower() == "photos":
        xbmcplugin.setContent(int(sys.argv[1]), 'files')
        itemtype = "Photo,PhotoAlbum,Folder"
    else:
        itemtype = ""

    # process the listing
    for item in xml:
        API = PlexAPI.API(item)
        li = API.CreateListItemFromPlexItem()
        if item.tag == 'Directory':
            # for folders we add an additional browse request, passing the
            # folderId
            li.setProperty('IsFolder', 'true')
            li.setProperty('IsPlayable', 'false')
            path = "%s?id=%s&mode=browsecontent&type=%s&folderid=%s" \
                   % (utils.tryDecode(sys.argv[0]),
                      utils.tryDecode(viewname),
                      utils.tryDecode(type),
                      utils.tryDecode(item.get("Id")))
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=True)
        else:
            # playable item, set plugin path and mediastreams
            path = "%s?id=%s&mode=play" % (sys.argv[0], API.getRatingKey())
            li.setProperty("path", path)
            API.AddStreamInfo(li)
            pbutils.PlaybackUtils(item).setArtwork(li)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]),
                url=li.getProperty("path"),
                listitem=li)

    if filter == "recent":
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
    else:
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))


def getOnDeck(viewid, mediatype, tagname, limit):
    """
    Retrieves Plex On Deck items, currently only for TV shows

    Input:
        viewid:             Plex id of the library section, e.g. '1'
        mediatype:          Kodi mediatype, e.g. 'tvshows', 'movies',
                            'homevideos', 'photos'
        tagname:            Name of the Plex library, e.g. "My Movies"
        limit:              Max. number of items to retrieve, e.g. 50
    """
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    appendShowTitle = utils.settings('OnDeckTvAppendShow') == 'true'
    appendSxxExx = utils.settings('OnDeckTvAppendSeason') == 'true'
    directpaths = utils.settings('useDirectPaths') == 'true'
    if utils.settings('OnDeckTVextended') == 'false':
        # Chances are that this view is used on Kodi startup
        # Wait till we've connected to a PMS. At most 30s
        counter = 0
        while utils.window('plex_authenticated') != 'true':
            counter += 1
            if counter >= 300:
                utils.logMsg(title, 'Aborting On Deck view, we were not '
                             'authenticated for the PMS', -1)
                return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)
            xbmc.sleep(100)
        xml = downloadutils.DownloadUtils().downloadUrl(
            '{server}/library/sections/%s/onDeck' % viewid)
        if xml in (None, 401):
            utils.logMsg(title, 'Could not download PMS xml for view %s'
                         % viewid, -1)
            return xbmcplugin.endOfDirectory(int(sys.argv[1]))
        for item in xml:
            API = PlexAPI.API(item)
            listitem = API.CreateListItemFromPlexItem(
                appendShowTitle=appendShowTitle,
                appendSxxExx=appendSxxExx)
            API.AddStreamInfo(listitem)
            pbutils.PlaybackUtils(item).setArtwork(listitem)
            if directpaths:
                url = API.getFilePath()
            else:
                params = {
                    'mode': "play",
                    'id': API.getRatingKey(),
                    'dbid': listitem.getProperty('dbid')
                }
                url = "plugin://plugin.video.plexkodiconnect.tvshows/?%s" \
                      % urllib.urlencode(params)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]),
                url=url,
                listitem=listitem)
        return xbmcplugin.endOfDirectory(
            handle=int(sys.argv[1]),
            cacheToDisc=utils.settings('enableTextureCache') == 'true')

    # if the addon is called with nextup parameter,
    # we return the nextepisodes list of the given tagname
    # First we get a list of all the TV shows - filtered by tag
    query = {
        'jsonrpc': "2.0",
        'id': "libTvShows",
        'method': "VideoLibrary.GetTVShows",
        'params': {
            'sort': {'order': "descending", 'method': "lastplayed"},
            'filter': {
                'and': [
                    {'operator': "true", 'field': "inprogress", 'value': ""},
                    {'operator': "is", 'field': "tag", 'value': "%s" % tagname}
                ]}
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(query))
    result = json.loads(result)
    # If we found any, find the oldest unwatched show for each one.
    try:
        items = result['result'][mediatype]
    except (KeyError, TypeError):
        # Now items retrieved - empty directory
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
        return

    query = {
        'jsonrpc': "2.0",
        'id': 1,
        'method': "VideoLibrary.GetEpisodes",
        'params': {
            'sort': {'method': "episode"},
            'limits': {"end": 1},
            'properties': [
                "title", "playcount", "season", "episode", "showtitle",
                "plot", "file", "rating", "resume", "tvshowid", "art",
                "streamdetails", "firstaired", "runtime", "cast", "writer",
                "dateadded", "lastplayed"
            ],
        }
    }

    if utils.settings('ignoreSpecialsNextEpisodes') == "true":
        query['params']['filter'] = {
            'and': [
                {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                {'operator': "greaterthan", 'field': "season", 'value': "0"}
            ]
        }
    else:
        query['params']['filter'] = {
            'or': [
                {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                {'operator': "true", 'field': "inprogress", 'value': ""}
            ]
        }

    # Are there any episodes still in progress/not yet finished watching?!?
    # Then we should show this episode, NOT the "next up"
    inprogrQuery = {
        'jsonrpc': "2.0",
        'id': 1,
        'method': "VideoLibrary.GetEpisodes",
        'params': {
            'sort': {'method': "episode"},
            'filter': {'operator': "true", 'field': "inprogress", 'value': ""},
        }
    }
    inprogrQuery['params']['properties'] = query['params']['properties']

    count = 0
    for item in items:
        inprogrQuery['params']['tvshowid'] = item['tvshowid']
        result = xbmc.executeJSONRPC(json.dumps(inprogrQuery))
        result = json.loads(result)
        try:
            episodes = result['result']['episodes']
        except (KeyError, TypeError):
            # No, there are no episodes not yet finished. Get "next up"
            query['params']['tvshowid'] = item['tvshowid']
            result = xbmc.executeJSONRPC(json.dumps(query))
            result = json.loads(result)
            try:
                episodes = result['result']['episodes']
            except (KeyError, TypeError):
                # Also no episodes currently coming up
                continue
        for episode in episodes:
            # There will always be only 1 episode ('limit=1')
            li = createListItem(episode,
                                appendShowTitle=appendShowTitle,
                                appendSxxExx=appendSxxExx)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]),
                url=episode['file'],
                listitem=li,
                isFolder=False)

        count += 1
        if count >= limit:
            break

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))


def watchlater():
    """
    Listing for plex.tv Watch Later section (if signed in to plex.tv)
    """
    if utils.window('plex_token') == '':
        utils.logMsg(title, 'No watch later - not signed in to plex.tv', -1)
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)
    if utils.settings('plex_restricteduser') == 'true':
        utils.logMsg(title, 'No watch later - restricted user', -1)
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)

    xml = downloadutils.DownloadUtils().downloadUrl(
        'https://plex.tv/pms/playlists/queue/all',
        authenticate=False,
        headerOptions={'X-Plex-Token': utils.window('plex_token')})
    if xml in (None, 401):
        utils.logMsg(title,
                     'Could not download watch later list from plex.tv', -1)
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)

    utils.logMsg(title, 'Displaying watch later plex.tv items', 1)
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    url = "plugin://plugin.video.plexkodiconnect.movies/"
    params = {
        'mode': "play",
        'dbid': 'plexnode'
    }
    for item in xml:
        API = PlexAPI.API(item)
        listitem = API.CreateListItemFromPlexItem()
        API.AddStreamInfo(listitem)
        pbutils.PlaybackUtils(item).setArtwork(listitem)
        params['id'] = item.attrib.get('key')
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]),
            url="%s?%s" % (url, urllib.urlencode(params)),
            listitem=listitem)

    xbmcplugin.endOfDirectory(
        handle=int(sys.argv[1]),
        cacheToDisc=True if utils.settings('enableTextureCache') == 'true'
        else False)


def enterPMS():
    """
    Opens dialogs for the user the plug in the PMS details
    """
    dialog = xbmcgui.Dialog()
    string = xbmcaddon.Addon().getLocalizedString
    # "Enter your Plex Media Server's IP or URL. Examples are:"
    dialog.ok(addonName,
              string(39215),
              '192.168.1.2',
              'plex.myServer.org')
    ip = dialog.input("Enter PMS IP or URL")
    if ip == '':
        return
    port = dialog.input("Enter PMS port", '32400', xbmcgui.INPUT_NUMERIC)
    if port == '':
        return
    url = '%s:%s' % (ip, port)
    # "Does your Plex Media Server support SSL connections?
    # (https instead of http)"
    https = dialog.yesno(addonName, string(39217))
    if https:
        url = 'https://%s' % url
    else:
        url = 'http://%s' % url
    https = 'true' if https else 'false'

    machineIdentifier = PlexFunctions.GetMachineIdentifier(url)
    if machineIdentifier is None:
        # "Error contacting url
        # Abort (Yes) or save address anyway (No)"
        if dialog.yesno(addonName, '%s %s. %s'
                        % (string(39218), url, string(39219))):
            return
        else:
            utils.settings('plex_machineIdentifier', '')
    else:
        utils.settings('plex_machineIdentifier', machineIdentifier)
    utils.logMsg(title, 'Setting new PMS to: https %s, ip %s, port %s, '
                 'machineIdentifier: %s'
                 % (https, ip, port, machineIdentifier), 1)
    utils.settings('https', value=https)
    utils.settings('ipaddress', value=ip)
    utils.settings('port', value=port)
    # Chances are this is a local PMS, so disable SSL certificate check
    utils.settings('sslverify', value='false')

    # Sign out to trigger new login
    if __LogOut():
        # Only login again if logout was successful
        __LogIn()


def __LogIn():
    """
    Resets (clears) window properties to enable (re-)login:
        suspend_Userclient
        plex_runLibScan: set to 'full' to trigger lib sync

    suspend_LibraryThread is cleared in service.py if user was signed out!
    """
    utils.window('plex_runLibScan', value='full')
    # Restart user client
    utils.window('suspend_Userclient', clear=True)


def __LogOut():
    """
    Finishes lib scans, logs out user. The following window attributes are set:
        suspend_LibraryThread: 'true'
        suspend_Userclient: 'true'

    Returns True if successfully signed out, False otherwise
    """
    string = xbmcaddon.Addon().getLocalizedString
    dialog = xbmcgui.Dialog()
    # Resetting, please wait
    dialog.notification(
        heading=addonName,
        message=string(39207),
        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
        time=3000,
        sound=False)
    # Pause library sync thread
    utils.window('suspend_LibraryThread', value='true')
    # Wait max for 10 seconds for all lib scans to shutdown
    counter = 0
    while utils.window('emby_dbScan') == 'true':
        if counter > 200:
            # Failed to reset PMS and plex.tv connects. Try to restart Kodi.
            dialog.ok(addonName, string(39208))
            # Resuming threads, just in case
            utils.window('suspend_LibraryThread', clear=True)
            utils.logMsg(title, "Could not stop library sync, aborting", -1)
            return False
        counter += 1
        xbmc.sleep(50)
    utils.logMsg(title, "Successfully stopped library sync", 1)

    # Log out currently signed in user:
    utils.window('emby_serverStatus', value="401")
    # Above method needs to have run its course! Hence wait
    counter = 0
    while utils.window('emby_serverStatus') == "401":
        if counter > 100:
            # 'Failed to reset PKC. Try to restart Kodi.'
            dialog.ok(addonName, string(39208))
            utils.logMsg(title, "Could not sign out user, aborting", -1)
            return False
        counter += 1
        xbmc.sleep(50)
    # Suspend the user client during procedure
    utils.window('suspend_Userclient', value='true')
    return True

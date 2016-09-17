# -*- coding: utf-8 -*-

###############################################################################

import json
import logging
import os
import sys
import urllib

import xbmc
import xbmcgui
import xbmcvfs
import xbmcplugin

import artwork
from utils import window, settings, language as lang
from utils import tryDecode, tryEncode, CatchExceptions
import clientinfo
import downloadutils
import embydb_functions as embydb
import playbackutils as pbutils
import playlist

import PlexFunctions
import PlexAPI

###############################################################################

log = logging.getLogger("PLEX."+__name__)

addonName = "PlexKodiConnect"

###############################################################################


def plexCompanion(fullurl, params):
    params = PlexFunctions.LiteralEval(params[26:])

    if params['machineIdentifier'] != window('plex_machineIdentifier'):
        log.error("Command was not for us, machineIdentifier controller: %s, "
                  "our machineIdentifier : %s"
                  % (params['machineIdentifier'],
                     window('plex_machineIdentifier')))
        return

    library, key, query = PlexFunctions.ParseContainerKey(
        params['containerKey'])
    # Construct a container key that works always (get rid of playlist args)
    window('containerKey', '/'+library+'/'+key)

    if 'playQueues' in library:
        log.debug("Playing a playQueue. Query was: %s" % query)
        # Playing a playlist that we need to fetch from PMS
        xml = PlexFunctions.GetPlayQueue(key)
        if xml is None:
            log.error("Error getting PMS playlist for key %s" % key)
            return
        else:
            resume = PlexFunctions.ConvertPlexToKodiTime(
                params.get('offset', 0))
            itemids = []
            for item in xml:
                itemids.append(item.get('ratingKey'))
            return playlist.Playlist().playAll(itemids, resume)

    else:
        log.error("Not knowing what to do for now - no playQueue sent")


def chooseServer():
    """
    Lets user choose from list of PMS
    """
    log.info("Choosing PMS server requested, starting")

    import initialsetup
    setup = initialsetup.InitialSetup()
    server = setup.PickPMS(showDialog=True)
    if server is None:
        log.error('We did not connect to a new PMS, aborting')
        window('suspend_Userclient', clear=True)
        window('suspend_LibraryThread', clear=True)
        return

    log.info("User chose server %s" % server['name'])
    setup.WritePMStoSettings(server)

    if not __LogOut():
        return

    from utils import deletePlaylists, deleteNodes
    # First remove playlists
    deletePlaylists()
    # Remove video nodes
    deleteNodes()

    # Log in again
    __LogIn()
    log.info("Choosing new PMS complete")
    # '<PMS> connected'
    xbmcgui.Dialog().notification(
        heading=addonName,
        message='%s %s' % (server['name'], lang(39220)),
        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
        time=3000,
        sound=False)


def togglePlexTV():
    if settings('plexToken'):
        log.info('Reseting plex.tv credentials in settings')
        settings('plexLogin', value="")
        settings('plexToken', value=""),
        settings('plexid', value="")
        settings('plexHomeSize', value="1")
        settings('plexAvatar', value="")
        settings('plex_status', value="Not logged in to plex.tv")

        window('plex_token', clear=True)
        window('plex_username', clear=True)
    else:
        log.info('Login to plex.tv')
        import initialsetup
        initialsetup.InitialSetup().PlexTVSignIn()
    xbmcgui.Dialog().notification(
        heading=addonName,
        message=lang(39221),
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
        window(arg, value=xml.attrib.get(arg))

    # Get resume point
    from utils import IntFromStr
    resume1 = PlexFunctions.ConvertPlexToKodiTime(IntFromStr(
        xml.attrib.get('playQueueSelectedItemOffset', 0)))
    resume2 = resume
    resume = max(resume1, resume2)

    pbutils.PlaybackUtils(xml).StartPlay(
        resume=resume,
        resumeId=xml.attrib.get('playQueueSelectedItemID', None))


def playWatchLater(itemid, viewOffset):
    """
    Called only for a SINGLE element for Plex.tv watch later

    Always to return with a "setResolvedUrl"
    """
    log.info('playWatchLater called with id: %s, viewOffset: %s'
             % (itemid, viewOffset))
    # Plex redirect, e.g. watch later. Need to get actual URLs
    xml = downloadutils.DownloadUtils().downloadUrl(itemid,
                                                    authenticate=False)
    if xml in (None, 401):
        log.error("Could not resolve url %s" % itemid)
        return xbmcplugin.setResolvedUrl(
            int(sys.argv[1]), False, xbmcgui.ListItem())
    if viewOffset != '0':
        try:
            viewOffset = int(PlexFunctions.PlexToKodiTimefactor() *
                             float(viewOffset))
        except:
            pass
        else:
            window('plex_customplaylist.seektime', value=str(viewOffset))
            log.info('Set resume point to %s' % str(viewOffset))
    return pbutils.PlaybackUtils(xml).play(None, 'plexnode')


def doPlayback(itemid, dbid):
    """
    Called only for a SINGLE element, not playQueues

    Always to return with a "setResolvedUrl"
    """
    if window('plex_authenticated') != "true":
        log.error('Not yet authenticated for a PMS, abort starting playback')
        # Not yet connected to a PMS server
        xbmcgui.Dialog().notification(
            addonName,
            lang(39210),
            xbmcgui.NOTIFICATION_ERROR,
            7000,
            True)
        return xbmcplugin.setResolvedUrl(
            int(sys.argv[1]), False, xbmcgui.ListItem())

    xml = PlexFunctions.GetPlexMetadata(itemid)
    if xml in (None, 401):
        return xbmcplugin.setResolvedUrl(
            int(sys.argv[1]), False, xbmcgui.ListItem())
    if xml[0].attrib.get('type') == 'photo':
        # Photo
        API = PlexAPI.API(xml[0])
        listitem = API.CreateListItemFromPlexItem()
        API.AddStreamInfo(listitem)
        pbutils.PlaybackUtils(xml[0]).setArtwork(listitem)
        return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)
    else:
        # Video
        return pbutils.PlaybackUtils(xml).play(itemid, dbid)


##### DO RESET AUTH #####
def resetAuth():
    # User tried login and failed too many times
    resp = xbmcgui.Dialog().yesno(
        heading="Warning",
        line1=lang(39206))
    if resp == 1:
        log.info("Reset login attempts.")
        window('plex_serverStatus', value="Auth")
    else:
        xbmc.executebuiltin('Addon.OpenSettings(plugin.video.plexkodiconnect)')


def addDirectoryItem(label, path, folder=True):
    li = xbmcgui.ListItem(label, path=path)
    li.setThumbnailImage("special://home/addons/plugin.video.plexkodiconnect/icon.png")
    li.setArt({"fanart":"special://home/addons/plugin.video.plexkodiconnect/fanart.jpg"})
    li.setArt({"landscape":"special://home/addons/plugin.video.plexkodiconnect/fanart.jpg"})
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=li, isFolder=folder)


def doMainListing():
    xbmcplugin.setContent(int(sys.argv[1]), 'files')
    # Get emby nodes from the window props
    plexprops = window('Plex.nodes.total')
    if plexprops:
        totalnodes = int(plexprops)
        for i in range(totalnodes):
            path = window('Plex.nodes.%s.index' % i)
            if not path:
                path = window('Plex.nodes.%s.content' % i)
            label = window('Plex.nodes.%s.title' % i)
            node_type = window('Plex.nodes.%s.type' % i)
            #because we do not use seperate entrypoints for each content type, we need to figure out which items to show in each listing.
            #for now we just only show picture nodes in the picture library video nodes in the video library and all nodes in any other window
            if path and xbmc.getCondVisibility("Window.IsActive(Pictures)") and node_type == "photos":
                addDirectoryItem(label, path)
            elif path and xbmc.getCondVisibility("Window.IsActive(VideoLibrary)") and node_type != "photos":
                addDirectoryItem(label, path)
            elif path and not xbmc.getCondVisibility("Window.IsActive(VideoLibrary) | Window.IsActive(Pictures) | Window.IsActive(MusicLibrary)"):
                addDirectoryItem(label, path)

    # Plex Watch later
    addDirectoryItem(lang(39211),
                     "plugin://plugin.video.plexkodiconnect/?mode=watchlater")
    # Plex user switch
    addDirectoryItem(lang(39200) + window('plex_username'),
                     "plugin://plugin.video.plexkodiconnect/"
                     "?mode=switchuser")

    #experimental live tv nodes
    # addDirectoryItem("Live Tv Channels (experimental)", "plugin://plugin.video.plexkodiconnect/?mode=browsecontent&type=tvchannels&folderid=root")
    # addDirectoryItem("Live Tv Recordings (experimental)", "plugin://plugin.video.plexkodiconnect/?mode=browsecontent&type=recordings&folderid=root")

    # some extra entries for settings and stuff. TODO --> localize the labels
    addDirectoryItem(lang(39201), "plugin://plugin.video.plexkodiconnect/?mode=settings")
    # addDirectoryItem("Add user to session", "plugin://plugin.video.plexkodiconnect/?mode=adduser")
    addDirectoryItem(lang(39203), "plugin://plugin.video.plexkodiconnect/?mode=refreshplaylist")
    addDirectoryItem(lang(39204), "plugin://plugin.video.plexkodiconnect/?mode=manualsync")
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


##### Generate a new deviceId
def resetDeviceId():

    dialog = xbmcgui.Dialog()

    deviceId_old = window('plex_client_Id')
    try:
        deviceId = clientinfo.ClientInfo().getDeviceId(reset=True)
    except Exception as e:
        log.error("Failed to generate a new device Id: %s" % e)
        dialog.ok(heading=addonName, line1=lang(33032))
    else:
        log.info("Successfully removed old deviceId: %s New deviceId: %s"
                 % (deviceId_old, deviceId))
        # "Kodi will now restart to apply the changes"
        dialog.ok(heading=addonName, line1=lang(33033))
        xbmc.executebuiltin('RestartApp')


def deleteItem():
    # Serves as a keymap action
    if xbmc.getInfoLabel('ListItem.Property(plexid)'):
        # If we already have the plexid
        plexid = xbmc.getInfoLabel('ListItem.Property(plexid)')
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
                log.error("Unknown type, unable to proceed.")
                return

        from utils import kodiSQL
        embyconn = kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)
        item = emby_db.getItem_byKodiId(dbid, itemtype)
        embycursor.close()

        try:
            plexid = item[0]
        except TypeError:
            log.error("Unknown plexid, unable to proceed.")
            return

    if settings('skipContextMenu') != "true":
        resp = xbmcgui.Dialog().yesno(
                                heading="Confirm delete",
                                line1=("Delete file from Emby Server? This will "
                                        "also delete the file(s) from disk!"))
        if not resp:
            log.debug("User skipped deletion for: %s." % plexid)
            return
    doUtils = downloadutils.DownloadUtils()
    url = "{server}/emby/Items/%s?format=json" % plexid
    log.info("Deleting request: %s" % plexid)
    doUtils.downloadUrl(url, action_type="DELETE")


def switchPlexUser():
    """
    Signs out currently logged in user (if applicable). Triggers sign-in of a
    new user
    """
    # Guess these user avatars are a future feature. Skipping for now
    # Delete any userimages. Since there's always only 1 user: position = 0
    # position = 0
    # window('EmbyAdditionalUserImage.%s' % position, clear=True)
    log.info("Plex home user switch requested")
    if not __LogOut():
        return

    # First remove playlists of old user
    from utils import deletePlaylists, deleteNodes
    deletePlaylists()
    # Remove video nodes
    deleteNodes()
    __LogIn()


##### REFRESH EMBY PLAYLISTS #####
def refreshPlaylist():
    log.info('Requesting playlist/nodes refresh')
    window('plex_runLibScan', value="views")


#### SHOW SUBFOLDERS FOR NODE #####
def GetSubFolders(nodeindex):
    nodetypes = ["",".recent",".recentepisodes",".inprogress",".inprogressepisodes",".unwatched",".nextepisodes",".sets",".genres",".random",".recommended"]
    for node in nodetypes:
        title = window('Plex.nodes.%s%s.title' %(nodeindex,node))
        if title:
            path = window('Plex.nodes.%s%s.content' %(nodeindex,node))
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
            if view.get("name") == tryDecode(viewname):
                folderid = view.get("id")
                break

    if viewname is not None:
        log.info("viewname: %s - type: %s - folderid: %s - filter: %s"
                 % (tryDecode(viewname),
                    tryDecode(browse_type),
                    tryDecode(folderid),
                    tryDecode(filter_type)))
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
                           % (tryDecode(sys.argv[0]),
                              tryDecode(viewname),
                              tryDecode(browse_type),
                              tryDecode(item.get("Id")))
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

    li.setProperty("plexid",itemid)
    
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
            if settings('ignoreSpecialsNextEpisodes') == "true":
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
    appendShowTitle = settings('RecentTvAppendShow') == 'true'
    appendSxxExx = settings('RecentTvAppendSeason') == 'true'
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
    if settings('TVShowWatched') == 'false':
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
        log.info('No Plex ID found, abort getting Extras')
        return xbmcplugin.endOfDirectory(int(sys.argv[1]))

    item = PlexFunctions.GetPlexMetadata(plexId)
    try:
        path = item[0][0][0].attrib['file']
    except:
        log.error('Could not get file path for item %s' % plexId)
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
            file = path + tryDecode(file)
            li = xbmcgui.ListItem(file, path=file)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=tryEncode(file),
                                        listitem=li)
        for dir in dirs:
            dir = path + tryDecode(dir)
            li = xbmcgui.ListItem(dir, path=dir)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=tryEncode(dir),
                                        listitem=li,
                                        isFolder=True)
    else:
        log.warn('Kodi cannot access folder %s' % path)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


@CatchExceptions(warnuser=False)
def getExtraFanArt(plexid, plexPath):
    """
    Get extrafanart for listitem
    will be called by skinhelper script to get the extrafanart
    for tvshows we get the plexid just from the path
    """
    log.debug('Called with plexid: %s, plexPath: %s' % (plexid, plexPath))
    if not plexid:
        if "plugin.video.plexkodiconnect" in plexPath:
            plexid = plexPath.split("/")[-2]
    if not plexid:
        log.error('Could not get a plexid, aborting')
        return xbmcplugin.endOfDirectory(int(sys.argv[1]))

    # We need to store the images locally for this to work
    # because of the caching system in xbmc
    fanartDir = tryDecode(xbmc.translatePath(
        "special://thumbnails/plex/%s/" % plexid))
    if not xbmcvfs.exists(fanartDir):
        # Download the images to the cache directory
        xbmcvfs.mkdirs(tryEncode(fanartDir))
        xml = PlexFunctions.GetPlexMetadata(plexid)
        if xml is None:
            log.error('Could not download metadata for %s' % plexid)
            return xbmcplugin.endOfDirectory(int(sys.argv[1]))

        API = PlexAPI.API(xml[0])
        backdrops = API.getAllArtwork()['Backdrop']
        for count, backdrop in enumerate(backdrops):
            # Same ordering as in artwork
            if os.path.supports_unicode_filenames:
                fanartFile = os.path.join(fanartDir,
                                          "fanart%.3d.jpg" % count)
            else:
                fanartFile = os.path.join(
                    tryEncode(fanartDir),
                    tryEncode("fanart%.3d.jpg" % count))
            li = xbmcgui.ListItem("%.3d" % count, path=fanartFile)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]),
                url=fanartFile,
                listitem=li)
            xbmcvfs.copy(backdrop, fanartFile)
    else:
        log.info("Found cached backdrop.")
        # Use existing cached images
        dirs, files = xbmcvfs.listdir(fanartDir)
        for file in files:
            fanartFile = os.path.join(fanartDir, tryDecode(file))
            li = xbmcgui.ListItem(file, path=fanartFile)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=fanartFile,
                                        listitem=li)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def RunLibScan(mode):
    if window('plex_online') != "true":
        # Server is not online, do not run the sync
        xbmcgui.Dialog().ok(heading=addonName,
                            line1=lang(39205))
    else:
        window('plex_runLibScan', value='full')


def BrowsePlexContent(viewid, mediatype="", folderid=""):
    """
    Browse Plex Photos:
        viewid:          PMS name of the library
        mediatype:       mediatype, 'photos'
        nodetype:        e.g. 'ondeck' (TBD!!)
    """
    log.debug("BrowsePlexContent called with viewid: %s, mediatype: "
              "%s, folderid: %s" % (viewid, mediatype, folderid))

    if not folderid:
        # Top-level navigation, so get the content of this section
        # Get all sections
        xml = PlexFunctions.GetPlexSectionResults(
            viewid,
            containerSize=int(settings('limitindex')))
        try:
            xml.attrib
        except AttributeError:
            log.error("Error download section %s" % viewid)
            return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)
    else:
        # folderid was passed so we can directly access the folder
        xml = downloadutils.DownloadUtils().downloadUrl(
            "{server}%s" % folderid)
        try:
            xml.attrib
        except AttributeError:
            log.error("Error downloading %s" % folderid)
            return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)

    # Set the folder's name
    xbmcplugin.setPluginCategory(int(sys.argv[1]),
                                 xml.attrib.get('librarySectionTitle'))

    # set the correct params for the content type
    if mediatype == "photos":
        xbmcplugin.setContent(int(sys.argv[1]), 'photos')

    # process the listing
    for item in xml:
        API = PlexAPI.API(item)
        if item.tag == 'Directory':
            li = xbmcgui.ListItem(item.attrib.get('title', 'Missing title'))
            # for folders we add an additional browse request, passing the
            # folderId
            li.setProperty('IsFolder', 'true')
            li.setProperty('IsPlayable', 'false')
            path = "%s?id=%s&mode=browseplex&type=%s&folderid=%s" \
                   % (sys.argv[0], viewid, mediatype, API.getKey())
            pbutils.PlaybackUtils(item).setArtwork(li)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                        url=path,
                                        listitem=li,
                                        isFolder=True)
        else:
            li = API.CreateListItemFromPlexItem()
            pbutils.PlaybackUtils(item).setArtwork(li)
            xbmcplugin.addDirectoryItem(
                handle=int(sys.argv[1]),
                url=li.getProperty("path"),
                listitem=li)

    xbmcplugin.addSortMethod(int(sys.argv[1]),
                             xbmcplugin.SORT_METHOD_VIDEO_TITLE)
    xbmcplugin.addSortMethod(int(sys.argv[1]),
                             xbmcplugin.SORT_METHOD_DATE)
    xbmcplugin.addSortMethod(int(sys.argv[1]),
                             xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(int(sys.argv[1]),
                             xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.endOfDirectory(
        handle=int(sys.argv[1]),
        cacheToDisc=settings('enableTextureCache') == 'true')


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
    appendShowTitle = settings('OnDeckTvAppendShow') == 'true'
    appendSxxExx = settings('OnDeckTvAppendSeason') == 'true'
    directpaths = settings('useDirectPaths') == 'true'
    if settings('OnDeckTVextended') == 'false':
        # Chances are that this view is used on Kodi startup
        # Wait till we've connected to a PMS. At most 30s
        counter = 0
        while window('plex_authenticated') != 'true':
            counter += 1
            if counter >= 300:
                log.error('Aborting On Deck view, we were not authenticated '
                          'for the PMS')
                return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)
            xbmc.sleep(100)
        xml = downloadutils.DownloadUtils().downloadUrl(
            '{server}/library/sections/%s/onDeck' % viewid)
        if xml in (None, 401):
            log.error('Could not download PMS xml for view %s' % viewid)
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
            cacheToDisc=settings('enableTextureCache') == 'true')

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

    if settings('ignoreSpecialsNextEpisodes') == "true":
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
    if window('plex_token') == '':
        log.error('No watch later - not signed in to plex.tv')
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)
    if settings('plex_restricteduser') == 'true':
        log.error('No watch later - restricted user')
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)

    xml = downloadutils.DownloadUtils().downloadUrl(
        'https://plex.tv/pms/playlists/queue/all',
        authenticate=False,
        headerOptions={'X-Plex-Token': window('plex_token')})
    if xml in (None, 401):
        log.error('Could not download watch later list from plex.tv')
        return xbmcplugin.endOfDirectory(int(sys.argv[1]), False)

    log.info('Displaying watch later plex.tv items')
    xbmcplugin.setContent(int(sys.argv[1]), 'movies')
    url = "plugin://plugin.video.plexkodiconnect/"
    params = {
        'mode': "playwatchlater",
    }
    for item in xml:
        API = PlexAPI.API(item)
        listitem = API.CreateListItemFromPlexItem()
        API.AddStreamInfo(listitem)
        pbutils.PlaybackUtils(item).setArtwork(listitem)
        params['id'] = item.attrib.get('key')
        params['viewOffset'] = item.attrib.get('viewOffset', '0')
        xbmcplugin.addDirectoryItem(
            handle=int(sys.argv[1]),
            url="%s?%s" % (url, urllib.urlencode(params)),
            listitem=listitem)

    xbmcplugin.endOfDirectory(
        handle=int(sys.argv[1]),
        cacheToDisc=settings('enableTextureCache') == 'true')


def enterPMS():
    """
    Opens dialogs for the user the plug in the PMS details
    """
    dialog = xbmcgui.Dialog()
    # "Enter your Plex Media Server's IP or URL. Examples are:"
    dialog.ok(addonName,
              lang(39215),
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
    https = dialog.yesno(addonName, lang(39217))
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
                        % (lang(39218), url, lang(39219))):
            return
        else:
            settings('plex_machineIdentifier', '')
    else:
        settings('plex_machineIdentifier', machineIdentifier)
    log.info('Setting new PMS to https %s, ip %s, port %s, machineIdentifier '
             % (https, ip, port, machineIdentifier))
    settings('https', value=https)
    settings('ipaddress', value=ip)
    settings('port', value=port)
    # Chances are this is a local PMS, so disable SSL certificate check
    settings('sslverify', value='false')

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
    window('plex_runLibScan', value='full')
    # Restart user client
    window('suspend_Userclient', clear=True)


def __LogOut():
    """
    Finishes lib scans, logs out user. The following window attributes are set:
        suspend_LibraryThread: 'true'
        suspend_Userclient: 'true'

    Returns True if successfully signed out, False otherwise
    """
    dialog = xbmcgui.Dialog()
    # Resetting, please wait
    dialog.notification(
        heading=addonName,
        message=lang(39207),
        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
        time=3000,
        sound=False)
    # Pause library sync thread
    window('suspend_LibraryThread', value='true')
    # Wait max for 10 seconds for all lib scans to shutdown
    counter = 0
    while window('plex_dbScan') == 'true':
        if counter > 200:
            # Failed to reset PMS and plex.tv connects. Try to restart Kodi.
            dialog.ok(addonName, lang(39208))
            # Resuming threads, just in case
            window('suspend_LibraryThread', clear=True)
            log.error("Could not stop library sync, aborting")
            return False
        counter += 1
        xbmc.sleep(50)
    log.debug("Successfully stopped library sync")

    # Log out currently signed in user:
    window('plex_serverStatus', value="401")
    # Above method needs to have run its course! Hence wait
    counter = 0
    while window('plex_serverStatus') == "401":
        if counter > 100:
            # 'Failed to reset PKC. Try to restart Kodi.'
            dialog.ok(addonName, lang(39208))
            log.error("Could not sign out user, aborting")
            return False
        counter += 1
        xbmc.sleep(50)
    # Suspend the user client during procedure
    window('suspend_Userclient', value='true')
    return True

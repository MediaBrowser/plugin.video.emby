# -*- coding: utf-8 -*-

###############################################################################

from threading import Thread, Lock
from datetime import datetime
import Queue

import xbmc
import xbmcgui
import xbmcvfs

import utils
import clientinfo
import downloadutils
import itemtypes
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver
import userclient
import videonodes

import PlexFunctions

###############################################################################


@utils.ThreadMethodsAdditionalStop('emby_shouldStop')
@utils.ThreadMethods
class ThreadedGetMetadata(Thread):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the out_queue with the downloaded etree XML objects

    Input:
        queue               Queue.Queue() object that you'll need to fill up
                            with Plex itemIds
        out_queue           Queue() object where this thread will store
                            the downloaded metadata XMLs as etree objects
        lock                Lock(), used for counting where we are
    """
    def __init__(self, queue, out_queue, lock):
        self.queue = queue
        self.out_queue = out_queue
        self.lock = lock
        Thread.__init__(self)

    def run(self):
        # cache local variables because it's faster
        queue = self.queue
        out_queue = self.out_queue
        lock = self.lock
        threadStopped = self.threadStopped
        global getMetadataCount
        while threadStopped() is False:
            # grabs Plex item from queue
            try:
                updateItem = queue.get(block=False)
            # Empty queue
            except Queue.Empty:
                xbmc.sleep(100)
                continue
            # Download Metadata
            plexXML = PlexFunctions.GetPlexMetadata(updateItem['itemId'])
            if plexXML is None:
                # Did not receive a valid XML - skip that item for now
                queue.task_done()
                continue

            updateItem['XML'] = plexXML
            # place item into out queue
            out_queue.put(updateItem)
            # Keep track of where we are at
            with lock:
                getMetadataCount += 1
            # signals to queue job is done
            queue.task_done()


@utils.ThreadMethodsAdditionalStop('emby_shouldStop')
@utils.ThreadMethods
class ThreadedProcessMetadata(Thread):
    """
    Not yet implemented - if ever. Only to be called by ONE thread!
    Processes the XML metadata in the queue

    Input:
        queue:      Queue.Queue() object that you'll need to fill up with
                    the downloaded XML eTree objects
        itemType:   as used to call functions in itemtypes.py
                    e.g. 'Movies' => itemtypes.Movies()
        lock:       Lock(), used for counting where we are
    """
    def __init__(self, queue, itemType, lock):
        self.queue = queue
        self.lock = lock
        self.itemType = itemType
        Thread.__init__(self)

    def run(self):
        # Constructs the method name, e.g. itemtypes.Movies
        itemFkt = getattr(itemtypes, self.itemType)
        # cache local variables because it's faster
        queue = self.queue
        lock = self.lock
        threadStopped = self.threadStopped
        global processMetadataCount
        global processingViewName
        with itemFkt() as item:
            while threadStopped() is False:
                # grabs item from queue
                try:
                    updateItem = queue.get(block=False)
                except Queue.Empty:
                    xbmc.sleep(100)
                    continue
                # Do the work; lock to be sure we've only got 1 Thread
                plexitem = updateItem['XML']
                method = updateItem['method']
                viewName = updateItem['viewName']
                viewId = updateItem['viewId']
                title = updateItem['title']
                itemSubFkt = getattr(item, method)
                with lock:
                    # Get the one child entry in the xml and process
                    for child in plexitem:
                        if method == 'add_updateAlbum':
                            item.add_updateAlbum(child,
                                                 viewtag=viewName,
                                                 viewid=viewId)
                        else:
                            itemSubFkt(child,
                                       viewtag=viewName,
                                       viewid=viewId)
                    # Keep track of where we are at
                    processMetadataCount += 1
                    processingViewName = title
                # signals to queue job is done
                queue.task_done()


@utils.ThreadMethodsAdditionalStop('emby_shouldStop')
@utils.ThreadMethods
class ThreadedShowSyncInfo(Thread):
    """
    Threaded class to show the Kodi statusbar of the metadata download.

    Input:
        dialog       xbmcgui.DialogProgressBG() object to show progress
        locks = [downloadLock, processLock]     Locks() to the other threads
        total:       Total number of items to get
    """
    def __init__(self, dialog, locks, total, itemType):
        self.locks = locks
        self.total = total
        self.addonName = clientinfo.ClientInfo().getAddonName()
        self.dialog = dialog
        self.itemType = itemType
        Thread.__init__(self)

    def run(self):
        # cache local variables because it's faster
        total = self.total
        dialog = self.dialog
        threadStopped = self.threadStopped
        downloadLock = self.locks[0]
        processLock = self.locks[1]
        dialog.create("%s: Sync %s: %s items"
                      % (self.addonName, self.itemType, str(total)),
                      "Starting")
        global getMetadataCount
        global processMetadataCount
        global processingViewName
        total = 2 * total
        totalProgress = 0
        while threadStopped() is False:
            with downloadLock:
                getMetadataProgress = getMetadataCount
            with processLock:
                processMetadataProgress = processMetadataCount
                viewName = processingViewName
            totalProgress = getMetadataProgress + processMetadataProgress
            try:
                percentage = int(float(totalProgress) / float(total)*100.0)
            except ZeroDivisionError:
                percentage = 0
            try:
                dialog.update(
                    percentage,
                    message="Downloaded: %s. Processed: %s: %s"
                            % (getMetadataProgress, processMetadataProgress,
                               viewName))
            except:
                # Wierd formating of the string viewName?!?
                pass
            # Sleep for x milliseconds
            xbmc.sleep(500)
        dialog.close()


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('suspend_LibraryThread')
@utils.ThreadMethodsAdditionalStop('emby_shouldStop')
@utils.ThreadMethods
class LibrarySync(Thread):
    # Borg, even though it's planned to only have 1 instance up and running!
    _shared_state = {}
    # How long should we look into the past for fast syncing items (in s)
    syncPast = 30

    def __init__(self):

        self.__dict__ = self._shared_state

        self.clientInfo = clientinfo.ClientInfo()
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.vnodes = videonodes.VideoNodes()
        self.syncThreadNumber = int(utils.settings('syncThreadNumber'))

        self.installSyncDone = True if \
            utils.settings('SyncInstallRunDone') == 'true' else False
        self.showDbSync = True if \
            utils.settings('dbSyncIndicator') == 'true' else False
        self.enableMusic = True if utils.settings('enableMusic') == "true" \
            else False

        Thread.__init__(self)

    def showKodiNote(self, message, forced=False):
        """
        Shows a Kodi popup, if user selected to do so
        """
        if not (self.showDbSync or forced):
            return
        xbmcgui.Dialog().notification(
            heading=self.addonName,
            message=message,
            icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
            sound=False)

    def startSync(self):
        utils.window('emby_dbScan', value="true")
        completed = self.fastSync()
        if not completed:
            # Fast sync failed or server plugin is not found
            self.logMsg("Something went wrong, starting full sync", 0)
            completed = self.fullSync(manualrun=True)
        utils.window('emby_dbScan', clear=True)
        return completed

    def fastSync(self):
        """
        Fast incremential lib sync

        Using /library/recentlyAdded is NOT working as changes to lib items are
        not reflected

        This will NOT remove items from Kodi db that were removed from the PMS
        (happens only during fullsync)

        Currently, ALL items returned by the PMS (because they've just been
        edited by the PMS or have been watched) will be processed. This will
        probably happen several times.
        """
        self.compare = True
        # Get last sync time
        lastSync = self.lastSync - self.syncPast
        if not lastSync:
            # Original Emby format:
            # lastSync = "2016-01-01T00:00:00Z"
            # January 1, 2015 at midnight:
            lastSync = 1420070400
        # Set new timestamp NOW because sync might take a while
        self.saveLastSync()

        # Original idea: Get all PMS items already saved in Kodi
        # Also get checksums of every Plex items already saved in Kodi
        # NEW idea: process every item returned by the PMS
        self.allKodiElementsId = {}

        # Run through views and get latest changed elements using time diff
        self.updateKodiVideoLib = False
        self.updateKodiMusicLib = False
        for view in self.views:
            self.updatelist = []
            if self.threadStopped():
                return True
            # Get items per view
            items = PlexFunctions.GetAllPlexLeaves(
                view['id'], updatedAt=lastSync)
            # Just skip item if something went wrong
            if not items:
                continue
            # Get one itemtype, because they're the same in the PMS section
            plexType = items[0].attrib['type']
            # Populate self.updatelist
            self.GetUpdatelist(items,
                               PlexFunctions.GetItemClassFromType(plexType),
                               PlexFunctions.GetMethodFromPlexType(plexType),
                               view['name'],
                               view['id'])
            # Process self.updatelist
            if self.updatelist:
                if self.updatelist[0]['itemType'] in ['Movies', 'TVShows']:
                    self.updateKodiVideoLib = True
                elif self.updatelist[0]['itemType'] == 'Music':
                    self.updateKodiMusicLib = True
                self.GetAndProcessXMLs(
                    PlexFunctions.GetItemClassFromType(plexType))
                self.updatelist = []

        # Update userdata
        for view in self.views:
            self.PlexUpdateWatched(
                view['id'],
                PlexFunctions.GetItemClassFromType(view['itemtype']),
                lastViewedAt=lastSync)

        # Let Kodi update the library now (artwork and userdata)
        if self.updateKodiVideoLib:
            self.logMsg("Doing Kodi Video Lib update", 2)
            xbmc.executebuiltin('UpdateLibrary(video)')
        if self.updateKodiMusicLib:
            self.logMsg("Doing Kodi Music Lib update", 2)
            xbmc.executebuiltin('UpdateLibrary(music)')

        # Reset and return
        self.allPlexElementsId = {}
        return True

    def saveLastSync(self):
        # Save last sync time
        self.lastSync = utils.getUnixTimestamp()

    def initializeDBs(self):
        """
        Run once during startup to verify that emby db exists.
        """
        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        # Create the tables for the emby database
        # emby, view, version
        embycursor.execute(
            """CREATE TABLE IF NOT EXISTS emby(
            emby_id TEXT UNIQUE, media_folder TEXT, emby_type TEXT, media_type TEXT, kodi_id INTEGER, 
            kodi_fileid INTEGER, kodi_pathid INTEGER, parent_id INTEGER, checksum INTEGER)""")
        embycursor.execute(
            """CREATE TABLE IF NOT EXISTS view(
            view_id TEXT UNIQUE, view_name TEXT, media_type TEXT, kodi_tagid INTEGER)""")
        embycursor.execute("CREATE TABLE IF NOT EXISTS version(idVersion TEXT)")
        embyconn.commit()
        
        # content sync: movies, tvshows, musicvideos, music
        embyconn.close()
        return

    def fullSync(self, manualrun=False, repair=False):
        # Only run once when first setting up. Can be run manually.
        self.compare = manualrun or repair

        # Add sources
        utils.sourcesXML()

        if manualrun:
            message = "Manual sync"
        elif repair:
            message = "Repair sync"
        else:
            message = "Initial sync"
        # Set new timestamp NOW because sync might take a while
        self.saveLastSync()
        starttotal = datetime.now()

        # Ensure that DBs exist if called for very first time
        self.initializeDBs()
        # Set views
        self.maintainViews()

        process = {
            'movies': self.PlexMovies,
            'tvshows': self.PlexTVShows,
        }
        if self.enableMusic:
            process['music'] = self.PlexMusic

        for itemtype in process:
            startTime = datetime.now()
            completed = process[itemtype]()
            if not completed:
                return False
            else:
                elapsedTime = datetime.now() - startTime
                self.logMsg("SyncDatabase (finished %s in: %s)"
                            % (itemtype, str(elapsedTime).split('.')[0]), 1)

        # Let kodi update the views in any case
        xbmc.executebuiltin('UpdateLibrary(video)')
        if self.enableMusic:
            xbmc.executebuiltin('UpdateLibrary(music)')
        elapsedtotal = datetime.now() - starttotal
        utils.window('emby_initialScan', clear=True)
        self.showKodiNote("%s completed in: %s"
                          % (message, str(elapsedtotal).split('.')[0]))

        return True

    def processView(self, folderItem, kodi_db, emby_db, totalnodes):
        vnodes = self.vnodes
        folder = folderItem.attrib
        mediatype = folder['type']
        # Only process supported formats
        supportedMedia = ['movie', 'show']
        if mediatype not in supportedMedia:
            return

        folderid = folder['key']
        foldername = folder['title']
        viewtype = folder['type']

        # Get current media folders from emby database
        view = emby_db.getView_byId(folderid)
        try:
            current_viewname = view[0]
            current_viewtype = view[1]
            current_tagid = view[2]
        except TypeError:
            self.logMsg("Creating viewid: %s in Emby database."
                        % folderid, 1)
            tagid = kodi_db.createTag(foldername)
            # Create playlist for the video library
            if mediatype in ['movies', 'tvshows', 'musicvideos']:
                utils.playlistXSP(mediatype, foldername, viewtype)
            # Create the video node
            if (mediatype in ['movies', 'tvshows', 'musicvideos',
                              'homevideos']):
                vnodes.viewNode(totalnodes,
                                foldername,
                                mediatype,
                                viewtype)
                totalnodes += 1
            # Add view to emby database
            emby_db.addView(folderid, foldername, viewtype, tagid)
        else:
            self.logMsg(' '.join((
                "Found viewid: %s" % folderid,
                "viewname: %s" % current_viewname,
                "viewtype: %s" % current_viewtype,
                "tagid: %s" % current_tagid)), 2)
            # View was modified, update with latest info
            if current_viewname != foldername:
                self.logMsg("viewid: %s new viewname: %s"
                            % (folderid, foldername), 1)
                tagid = kodi_db.createTag(foldername)

                # Update view with new info
                emby_db.updateView(foldername, tagid, folderid)

                if mediatype != "music":
                    if emby_db.getView_byName(current_viewname) is None:
                        # The tag could be a combined view. Ensure there's
                        # no other tags with the same name before deleting
                        # playlist.
                        utils.playlistXSP(mediatype,
                                          current_viewname,
                                          current_viewtype,
                                          True)
                        # Delete video node
                        if mediatype != "musicvideos":
                            vnodes.viewNode(totalnodes,
                                            current_viewname,
                                            mediatype,
                                            current_viewtype,
                                            delete=True)
                    # Added new playlist
                    if mediatype in ['movies', 'tvshows', 'musicvideos']:
                        utils.playlistXSP(mediatype, foldername, viewtype)
                    # Add new video node
                    if mediatype != "musicvideos":
                        vnodes.viewNode(totalnodes,
                                        foldername,
                                        mediatype,
                                        viewtype)
                        totalnodes += 1

                # Update items with new tag
                items = emby_db.getItem_byView(folderid)
                for item in items:
                    # Remove the "s" from viewtype for tags
                    kodi_db.updateTag(current_tagid,
                                      tagid,
                                      item[0],
                                      current_viewtype[:-1])
            else:
                if mediatype != "music":
                    # Validate the playlist exists or recreate it
                    if mediatype in ['movies', 'tvshows', 'musicvideos']:
                        utils.playlistXSP(mediatype, foldername, viewtype)
                    # Create the video node if not already exists
                    if mediatype != "musicvideos":
                        vnodes.viewNode(totalnodes,
                                        foldername,
                                        mediatype,
                                        viewtype)
                        totalnodes += 1

    def maintainViews(self):
        """
        Compare the views to Plex
        """
        vnodes = self.vnodes

        # Get views
        result = downloadutils.DownloadUtils().downloadUrl(
            "{server}/library/sections")
        if not result:
            self.logMsg("Error download PMS views, abort maintainViews", -1)
            return False

        # total nodes for window properties
        vnodes.clearProperties()
        totalnodes = 0

        with embydb.GetEmbyDB() as emby_db:
            with kodidb.GetKodiDB('video') as kodi_db:
                for folderItem in result:
                    self.processView(folderItem, kodi_db, emby_db, totalnodes)
                else:
                    # Add video nodes listings
                    vnodes.singleNode(totalnodes,
                                      "Favorite movies",
                                      "movies",
                                      "favourites")
                    totalnodes += 1
                    vnodes.singleNode(totalnodes,
                                      "Favorite tvshows",
                                      "tvshows",
                                      "favourites")
                    totalnodes += 1
                    vnodes.singleNode(totalnodes,
                                      "channels",
                                      "movies",
                                      "channels")
                    totalnodes += 1
                    # Save total
                    utils.window('Emby.nodes.total', str(totalnodes))

            # update views for all:
            self.views = emby_db.getAllViewInfo()
            # Append music views only to self.views (no custom views otherwise)
            if self.enableMusic:
                for folderItem in result:
                    if folderItem.attrib['type'] == 'artist':
                        entry = {
                            'id': folderItem.attrib['key'],
                            'name': folderItem.attrib['title'],
                            'itemtype': 'artist'
                        }
                        self.views.append(entry)

        self.logMsg("views saved: %s" % self.views, 1)

    def GetUpdatelist(self, xml, itemType, method, viewName, viewId,
                      dontCheck=False):
        """
        THIS METHOD NEEDS TO BE FAST! => e.g. no API calls

        Adds items to self.updatelist as well as self.allPlexElementsId dict

        Input:
            xml:                    PMS answer for section items
            itemType:               'Movies', 'TVShows', ...
            method:                 Method name to be called with this itemtype
                                    see itemtypes.py
            viewName:               Name of the Plex view (e.g. 'My TV shows')
            viewId:                 Id/Key of Plex library (e.g. '1')
            dontCheck:              If True, skips checksum check but assumes
                                    that all items in xml must be processed

        Output: self.updatelist, self.allPlexElementsId
            self.updatelist         APPENDED(!!) list itemids (Plex Keys as
                                    as received from API.getRatingKey())
            One item in this list is of the form:
                'itemId': xxx,
                'itemType': 'Movies','TVShows', ...
                'method': 'add_update', 'add_updateSeason', ...
                'viewName': xxx,
                'viewId': xxx,
                'title': xxx

            self.allPlexElementsId      APPENDED(!!) dict
                = {itemid: checksum}
        """
        if self.compare or not dontCheck:
            # Manual sync
            for item in xml:
                itemId = item.attrib.get('ratingKey')
                # Skipping items 'title=All episodes' without a 'ratingKey'
                if not itemId:
                    continue
                title = item.attrib.get('title', 'Missing Title Name')
                plex_checksum = ("K%s%s"
                                 % (itemId, item.attrib.get('updatedAt', '')))
                self.allPlexElementsId[itemId] = plex_checksum
                kodi_checksum = self.allKodiElementsId.get(itemId)
                if kodi_checksum != plex_checksum:
                    # Only update if movie is not in Kodi or checksum is
                    # different
                    self.updatelist.append({'itemId': itemId,
                                            'itemType': itemType,
                                            'method': method,
                                            'viewName': viewName,
                                            'viewId': viewId,
                                            'title': title})
        else:
            # Initial or repair sync: get all Plex movies
            for item in xml:
                itemId = item.attrib.get('ratingKey')
                # Skipping items 'title=All episodes' without a 'ratingKey'
                if not itemId:
                    continue
                title = item.attrib.get('title', 'Missing Title Name')
                plex_checksum = ("K%s%s"
                                 % (itemId, item.attrib.get('updatedAt', '')))
                self.allPlexElementsId[itemId] = plex_checksum
                self.updatelist.append({'itemId': itemId,
                                        'itemType': itemType,
                                        'method': method,
                                        'viewName': viewName,
                                        'viewId': viewId,
                                        'title': title})

    def GetAndProcessXMLs(self, itemType):
        """
        Downloads all XMLs for itemType (e.g. Movies, TV-Shows). Processes them
        by then calling itemtypes.<itemType>()

        Input:
            itemType:               'Movies', 'TVShows', ...
            self.updatelist
        """
        # Some logging, just in case.
        self.logMsg("self.updatelist: %s" % self.updatelist, 2)
        itemNumber = len(self.updatelist)
        if itemNumber == 0:
            return True

        # Run through self.updatelist, get XML metadata per item
        # Initiate threads
        self.logMsg("Starting sync threads", 1)
        getMetadataQueue = Queue.Queue()
        processMetadataQueue = Queue.Queue(maxsize=100)
        getMetadataLock = Lock()
        processMetadataLock = Lock()
        # To keep track
        global getMetadataCount
        getMetadataCount = 0
        global processMetadataCount
        processMetadataCount = 0
        global processingViewName
        processingViewName = ''
        # Populate queue: GetMetadata
        for updateItem in self.updatelist:
            getMetadataQueue.put(updateItem)
        # Spawn GetMetadata threads for downloading
        threads = []
        for i in range(min(self.syncThreadNumber, itemNumber)):
            thread = ThreadedGetMetadata(getMetadataQueue,
                                         processMetadataQueue,
                                         getMetadataLock)
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
        self.logMsg("%s download threads spawned" % len(threads), 1)
        # Spawn one more thread to process Metadata, once downloaded
        thread = ThreadedProcessMetadata(processMetadataQueue,
                                         itemType,
                                         processMetadataLock)
        thread.setDaemon(True)
        thread.start()
        threads.append(thread)
        self.logMsg("Processing thread spawned", 1)
        # Start one thread to show sync progress
        if self.showDbSync:
            dialog = xbmcgui.DialogProgressBG()
            thread = ThreadedShowSyncInfo(
                dialog,
                [getMetadataLock, processMetadataLock],
                itemNumber,
                itemType)
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
            self.logMsg("Kodi Infobox thread spawned", 1)

        # Wait until finished
        getMetadataQueue.join()
        processMetadataQueue.join()
        # Kill threads
        self.logMsg("Waiting to kill threads", 1)
        for thread in threads:
            thread.stopThread()
        self.logMsg("Stop sent to all threads", 1)
        # Wait till threads are indeed dead
        for thread in threads:
            thread.join(5.0)
            if thread.isAlive():
                self.logMsg("Could not terminate thread", -1)
        try:
            del threads
        except:
            self.logMsg("Could not delete threads", -1)
        self.logMsg("Sync threads finished", 1)
        self.updatelist = []
        return True

    def PlexMovies(self):
        # Initialize
        self.allPlexElementsId = {}

        itemType = 'Movies'

        views = [x for x in self.views if x['itemtype'] == 'movie']
        self.logMsg("Processing Plex %s. Libraries: %s" % (itemType, views), 1)

        self.allKodiElementsId = {}
        if self.compare:
            with embydb.GetEmbyDB() as emby_db:
                # Get movies from Plex server
                # Pull the list of movies and boxsets in Kodi
                try:
                    self.allKodiElementsId = dict(emby_db.getChecksum('Movie'))
                except ValueError:
                    self.allKodiElementsId = {}

        # PROCESS MOVIES #####
        self.updatelist = []
        for view in views:
            if self.threadStopped():
                return False
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            all_plexmovies = PlexFunctions.GetPlexSectionResults(viewId)
            if not all_plexmovies:
                self.logMsg("Couldnt get section items, aborting for view.", 1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(all_plexmovies,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
        self.GetAndProcessXMLs(itemType)
        self.logMsg("Processed view %s with ID %s" % (viewName, viewId), 1)
        # Update viewstate
        for view in views:
            if self.threadStopped():
                return False
            self.PlexUpdateWatched(view['id'], itemType)

        # PROCESS DELETES #####
        if self.compare:
            # Manual sync, process deletes
            with itemtypes.Movies() as Movie:
                for kodimovie in self.allKodiElementsId:
                    if kodimovie not in self.allPlexElementsId:
                        Movie.remove(kodimovie)
        self.logMsg("%s sync is finished." % itemType, 1)
        return True

    def PlexUpdateWatched(self, viewId, itemType,
                          lastViewedAt=None, updatedAt=None):
        """
        Updates plex elements' view status ('watched' or 'unwatched') and
        also updates resume times.
        This is done by downloading one XML for ALL elements with viewId
        """
        xml = PlexFunctions.GetAllPlexLeaves(viewId,
                                             lastViewedAt=lastViewedAt,
                                             updatedAt=updatedAt)
        # Return if there are no items in PMS reply - it's faster
        try:
            xml[0].attrib
        except (TypeError, AttributeError, IndexError):
            return

        if itemType in ['Movies', 'TVShows']:
            self.updateKodiVideoLib = True

        itemMth = getattr(itemtypes, itemType)
        with itemMth() as method:
            method.updateUserdata(xml)

    def musicvideos(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        # Get musicvideos from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        mvideos = itemtypes.MusicVideos(embycursor, kodicursor)

        views = emby_db.getView_byType('musicvideos')
        log("Media folders: %s" % views, 1)

        for view in views:
            
            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (utils.language(33019), viewName))

            # Initial or repair sync
            all_embymvideos = emby.getMusicVideos(viewId, dialog=pdialog)
            total = all_embymvideos['TotalRecordCount']
            embymvideos = all_embymvideos['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymvideo in embymvideos:
                # Process individual musicvideo
                if self.shouldStop():
                    return False
                
                title = embymvideo['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                mvideos.add_update(embymvideo, viewName, viewId)
        else:
            log("MusicVideos finished.", 2)

        return True

    def PlexTVShows(self):
        # Initialize
        self.allPlexElementsId = {}
        itemType = 'TVShows'

        views = [x for x in self.views if x['itemtype'] == 'show']
        self.logMsg("Media folders for %s: %s" % (itemType, views), 1)

        self.allKodiElementsId = {}
        if self.compare:
            with embydb.GetEmbyDB() as emby_db:
                # Pull the list of TV shows already in Kodi
                for kind in ('Series', 'Season', 'Episode'):
                    try:
                        elements = dict(emby_db.getChecksum(kind))
                        self.allKodiElementsId.update(elements)
                    # Yet empty/not yet synched
                    except ValueError:
                        pass

        # PROCESS TV Shows #####
        self.updatelist = []
        for view in views:
            if self.threadStopped():
                return False
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            allPlexTvShows = PlexFunctions.GetPlexSectionResults(viewId)
            if not allPlexTvShows:
                self.logMsg(
                    "Error downloading show view xml for view %s" % viewId, -1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(allPlexTvShows,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
            self.logMsg("Analyzed view %s with ID %s" % (viewName, viewId), 1)

        # COPY for later use
        allPlexTvShowsId = self.allPlexElementsId.copy()

        # PROCESS TV Seasons #####
        # Cycle through tv shows
        for tvShowId in allPlexTvShowsId:
            if self.threadStopped():
                return False
            # Grab all seasons to tvshow from PMS
            seasons = PlexFunctions.GetAllPlexChildren(tvShowId)
            if not seasons:
                self.logMsg(
                    "Error downloading season xml for show %s" % tvShowId, -1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(seasons,
                               itemType,
                               'add_updateSeason',
                               None,
                               tvShowId)  # send showId instead of viewid
            self.logMsg("Analyzed all seasons of TV show with Plex Id %s"
                        % tvShowId, 1)

        # PROCESS TV Episodes #####
        # Cycle through tv shows
        for view in views:
            if self.threadStopped():
                return False
            # Grab all episodes to tvshow from PMS
            episodes = PlexFunctions.GetAllPlexLeaves(view['id'])
            if not episodes:
                self.logMsg(
                    "Error downloading episod xml for view %s"
                    % view.get('name'), -1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(episodes,
                               itemType,
                               'add_updateEpisode',
                               None,
                               None)
            self.logMsg("Analyzed all episodes of TV show with Plex Id %s"
                        % tvShowId, 1)

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed", 1)
        # Refresh season info
        # Cycle through tv shows
        with itemtypes.TVShows() as TVshow:
            for tvShowId in allPlexTvShowsId:
                XMLtvshow = PlexFunctions.GetPlexMetadata(tvShowId)
                TVshow.refreshSeasonEntry(XMLtvshow, tvShowId)
        self.logMsg("Season info refreshed", 1)

        # Update viewstate:
        for view in views:
            self.PlexUpdateWatched(view['id'], itemType)

        if self.compare:
            # Manual sync, process deletes
            with itemtypes.TVShows() as TVShow:
                for kodiTvElement in self.allKodiElementsId:
                    if kodiTvElement not in self.allPlexElementsId:
                        TVShow.remove(kodiTvElement)
        self.logMsg("%s sync is finished." % itemType, 1)
        return True

    def PlexMusic(self):
        itemType = 'Music'

        views = [x for x in self.views if x['itemtype'] == 'artist']
        self.logMsg("Media folders for %s: %s" % (itemType, views), 1)

        methods = {
            'MusicArtist': 'add_updateArtist',
            'MusicAlbum': 'add_updateAlbum',
            'Audio': 'add_updateSong'
        }
        urlArgs = {
            'MusicArtist': {'type': 8},
            'MusicAlbum': {'type': 9},
            'Audio': {'type': 10}
        }

        # Process artist, then album and tracks last
        for kind in ('MusicArtist', 'MusicAlbum', 'Audio'):
            if self.threadStopped():
                return True
            self.logMsg("Start processing music %s" % kind, 1)
            self.ProcessMusic(
                views, kind, urlArgs[kind], methods[kind])
            self.logMsg("Processing of music %s done" % kind, 1)
            self.GetAndProcessXMLs(itemType)
            self.logMsg("GetAndProcessXMLs for music %s completed" % kind, 1)

        # reset stuff
        self.allKodiElementsId = {}
        self.allPlexElementsId = {}
        self.updatelist = []
        self.logMsg("%s sync is finished." % itemType, 1)
        return True

    def ProcessMusic(self, views, kind, urlArgs, method):
        self.allKodiElementsId = {}
        self.allPlexElementsId = {}
        self.updatelist = []

        # Get a list of items already existing in Kodi db
        if self.compare:
            with embydb.GetEmbyDB() as emby_db:
                # Pull the list of items already in Kodi
                try:
                    elements = dict(emby_db.getChecksum(kind))
                    self.allKodiElementsId.update(elements)
                # Yet empty/nothing yet synched
                except ValueError:
                    pass

        for view in views:
            if self.threadStopped():
                return True
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            itemsXML = PlexFunctions.GetPlexSectionResults(
                viewId, args=urlArgs)
            if not itemsXML:
                self.logMsg("Error downloading xml for view %s"
                            % viewId, -1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(itemsXML,
                               'Music',
                               method,
                               viewName,
                               viewId)

    def compareDBVersion(self, current, minimum):
        # It returns True is database is up to date. False otherwise.
        self.logMsg("current: %s minimum: %s" % (current, minimum), 1)
        currMajor, currMinor, currPatch = current.split(".")
        minMajor, minMinor, minPatch = minimum.split(".")

        if currMajor > minMajor:
            return True
        elif currMajor == minMajor and (currMinor > minMinor or
                                       (currMinor == minMinor and currPatch >= minPatch)):
            return True
        else:
            # Database out of date.
            return False

    def run(self):

        try:
            self.run_internal()
        except Exception as e:
            utils.window('emby_dbScan', clear=True)
            xbmcgui.Dialog().ok(
                heading=self.addonName,
                line1=("Library sync thread has exited! "
                       "You should restart Kodi now. "
                       "Please report this on the forum."))
            raise

    def run_internal(self):
        window = utils.window
        settings = utils.settings
        log = self.logMsg

        startupComplete = False
        self.views = []
        count = 0

        self.logMsg("---===### Starting LibrarySync ###===---", 0)
        while not self.threadStopped():

            # In the event the server goes offline, or an item is playing
            while self.threadSuspended():
                # Set in service.py
                if self.threadStopped():
                    # Abort was requested while waiting. We should exit
                    log("###===--- LibrarySync Stopped ---===###", 0)
                    return
                xbmc.sleep(1000)

            if (window('emby_dbCheck') != "true" and
                    self.installSyncDone):
                # Verify the validity of the database
                currentVersion = settings('dbCreatedWithVersion')
                minVersion = window('emby_minDBVersion')
                uptoDate = self.compareDBVersion(currentVersion, minVersion)

                if not uptoDate:
                    log("Db version out of date: %s minimum version required: "
                        "%s" % (currentVersion, minVersion), 0)
                    resp = xbmcgui.Dialog().yesno(
                        heading="Db Version",
                        line1=("Detected the database needs to be recreated "
                               "for this version of " + self.addonName +
                               "Proceed?"))
                    if not resp:
                        log("Db version out of date! USER IGNORED!", 0)
                        xbmcgui.Dialog().ok(
                            heading=self.addonName,
                            line1=(self.addonName + " may not work correctly "
                                   "until the database is reset."))
                    else:
                        utils.reset()

            if not startupComplete:
                # Also runs when installed first
                # Verify the video database can be found
                videoDb = utils.getKodiVideoDBPath()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    log("The current Kodi version is incompatible "
                        "to know which Kodi versions are supported.", 0)
                    xbmcgui.Dialog().ok(
                        heading=self.addonName,
                        line1=("Cancelling the database syncing process. "
                               "Current Kodi version: %s is unsupported. "
                               "Please verify your logs for more info."
                               % xbmc.getInfoLabel('System.BuildVersion')))
                    break

                # Run start up sync
                window('emby_dbScan', value="true")
                log("Db version: %s" % settings('dbCreatedWithVersion'), 0)
                log("SyncDatabase (started)", 1)
                startTime = datetime.now()
                librarySync = self.fullSync(manualrun=True)
                elapsedTime = datetime.now() - startTime
                log("SyncDatabase (finished in: %s) %s"
                    % (str(elapsedTime).split('.')[0], librarySync), 1)
                # Only try the initial sync once per kodi session regardless
                # This will prevent an infinite loop in case something goes wrong.
                startupComplete = True
                settings('SyncInstallRunDone', value="true")
                settings("dbCreatedWithVersion", self.clientInfo.getVersion())
                self.installSyncDone = True
                window('emby_dbScan', clear=True)

            # Currently no db scan, so we can start a new scan
            elif window('emby_dbScan') != "true":
                # Full scan was requested from somewhere else, e.g. userclient
                if window('plex_runLibScan') == "true":
                    log('Full library scan requested, starting', 0)
                    window('emby_dbScan', value="true")
                    window('plex_runLibScan', clear=True)
                    self.fullSync(manualrun=True)
                    window('emby_dbScan', clear=True)
                    count = 0
                else:
                    # Run full lib scan approx every 30min
                    if count >= 1800:
                        count = 0
                        window('emby_dbScan', value="true")
                        log('Running automatic full lib scan', 0)
                        self.fullSync(manualrun=True)
                        window('emby_dbScan', clear=True)
                    # Update views / PMS libraries approx. every 5min
                    elif count % 300 == 0:
                        log('Running maintainViews() scan', 0)
                        window('emby_dbScan', value="true")
                        self.maintainViews()
                        self.startSync()
                    # Run fast sync otherwise (ever 2 seconds or so)
                    else:
                        self.startSync()

            xbmc.sleep(2000)
            count += 1

        log("###===--- LibrarySync Stopped ---===###", 0)

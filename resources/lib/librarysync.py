# -*- coding: utf-8 -*-

##################################################################################################

import threading
from datetime import datetime, timedelta

import xbmc
import xbmcgui
import xbmcvfs

import api
import utils
import clientinfo
import downloadutils
import itemtypes
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver
import userclient
import videonodes

import PlexAPI
import Queue
import time

##################################################################################################


class ThreadedGetMetadata(threading.Thread):
    """
    Threaded download of Plex XML metadata for a certain library item.
    Fills the out_queue with the downloaded etree XML objects

    Input:
        queue               Queue.Queue() object that you'll need to fill up
                            with Plex itemIds
        out_queue           Queue.Queue() object where this thread will store
                            the downloaded metadata XMLs as etree objects
        lock                threading.Lock(), used for counting where we are
        userStop            Handle to a function where True is used to stop
                            this Thread
    """
    def __init__(self, queue, out_queue, lock, userStop):
        self.queue = queue
        self.out_queue = out_queue
        self.lock = lock
        self.userStop = userStop
        self._shouldstop = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        plx = PlexAPI.PlexAPI()
        global getMetadataCount
        while self.stopped() is False:
            # grabs Plex item from queue
            try:
                itemId = self.queue.get(block=False)
            # Empty queue
            except:
                continue
            # Download Metadata
            plexElement = plx.GetPlexMetadata(itemId)
            # place item into out queue
            self.out_queue.put(plexElement)
            # Keep track of where we are at
            with self.lock:
                getMetadataCount += 1
            # signals to queue job is done
            self.queue.task_done()

    def stopThread(self):
        self._shouldstop.set()

    def stopped(self):
        return self._shouldstop.isSet() or self.userStop()


class ThreadedProcessMetadata(threading.Thread):
    """
    Not yet implemented - if ever. Only to be called by ONE thread!
    Processes the XML metadata in the queue

    Input:
        queue:      Queue.Queue() object that you'll need to fill up with
                    the downloaded XML eTree objects
        data = {
            'itemType':         as used to call functions in itemtypes.py
                                e.g. 'Movies' => itemtypes.Movies()
            'viewName'          Plex str for library view (e.g. 'Movies')
            'viewId'            Plex Id to identifiy the library view
        }
        lock:       threading.Lock(), used for counting where we are
        userStop    Handle to a function where True is used to stop this Thread
    """
    def __init__(self, queue, data, lock, userStop):
        self.queue = queue
        self.lock = lock
        self.data = data
        self.userStop = userStop
        self._shouldstop = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        # Constructs the method name, e.g. itemtypes.Movies
        itemFkt = getattr(itemtypes, self.data['itemType'])
        viewName = self.data['viewName']
        viewId = self.data['viewId']
        global processMetadataCount
        with itemFkt() as item:
            while self.stopped() is False:
                # grabs item from queue
                try:
                    plexitem = self.queue.get(block=False)
                # Empty queue
                except:
                    continue
                # Do the work; lock to be sure we've only got 1 Thread
                with self.lock:
                    item.add_update(
                        plexitem,
                        viewtag=viewName,
                        viewid=viewId
                    )
                    # Keep track of where we are at
                    processMetadataCount += 1
                # signals to queue job is done
                self.queue.task_done()

    def stopThread(self):
        self._shouldstop.set()

    def stopped(self):
        return self._shouldstop.isSet() or self.userStop()


class ThreadedShowSyncInfo(threading.Thread):
    """
    Threaded class to show the Kodi statusbar of the metadata download.

    Input:
        dialog       xbmcgui.DialogProgressBG() object to show progress
        locks = [downloadLock, processLock]     Locks() to the other threads
        total:       Total number of items to get
        viewName:    Name of library we're getting
    """
    def __init__(self, dialog, locks, total, viewName):
        self.locks = locks
        self.total = total
        self.viewName = viewName
        self.addonName = clientinfo.ClientInfo().getAddonName()
        self._shouldstop = threading.Event()
        self.dialog = dialog
        threading.Thread.__init__(self)

    def run(self):
        total = self.total
        downloadLock = self.locks[0]
        processLock = self.locks[1]
        self.dialog.create(
            self.addonName + ": Sync " + self.viewName,
            "Starting"
        )
        global getMetadataCount
        global processMetadataCount
        total = 2 * total
        totalProgress = 0
        while self.stopped() is not True:
            with downloadLock:
                getMetadataProgress = getMetadataCount
            with processLock:
                processMetadataProgress = processMetadataCount
            totalProgress = getMetadataProgress + processMetadataProgress
            percentage = int(float(totalProgress) / float(total)*100.0)
            self.dialog.update(
                percentage,
                message="Downloaded: %s, Processed: %s" %
                    (getMetadataProgress, processMetadataProgress)
            )
            time.sleep(0.5)

    def stopThread(self):
        self._shouldstop.set()

    def stopped(self):
        return self._shouldstop.isSet()


class LibrarySync(threading.Thread):

    _shared_state = {}

    stop_thread = False
    suspend_thread = False

    # Track websocketclient updates
    addedItems = []
    updateItems = []
    userdataItems = []
    removeItems = []
    forceLibraryUpdate = False
    refresh_views = False


    def __init__(self):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils()
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.vnodes = videonodes.VideoNodes()
        self.plx = PlexAPI.PlexAPI()
        self.syncThreadNumber = int(utils.settings('syncThreadNumber'))

        threading.Thread.__init__(self)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def progressDialog(self, title, forced=False):

        dialog = None

        if utils.settings('dbSyncIndicator') == "true" or forced:
            dialog = xbmcgui.DialogProgressBG()
            dialog.create("Emby for Kodi", title)
            self.logMsg("Show progress dialog: %s" % title, 2)

        return dialog

    def startSync(self):
        # Run at start up - optional to use the server plugin
        if utils.settings('SyncInstallRunDone') == "true":
            
            # Validate views
            # self.refreshViews()
            completed = False
            # Verify if server plugin is installed.
            if utils.settings('serverSync') == "true":
                # Try to use fast start up
                completed = self.fastSync()

            if not completed:
                # Fast sync failed or server plugin is not found
                completed = self.fullSync(manualrun=True)
        else:
            # Install sync is not completed
            completed = self.fullSync()
        
        return completed

    def fastSync(self):

        lastSync = utils.settings('LastIncrementalSync')
        if not lastSync:
            lastSync = "2010-01-01T00:00:00Z"
        self.logMsg("Last sync run: %s" % lastSync, 1)

        url = "{server}/emby/Emby.Kodi.SyncQueue/{UserId}/GetItems?format=json"
        params = {'LastUpdateDT': lastSync}
        result = self.doUtils.downloadUrl(url, parameters=params)

        try:
            processlist = {
                
                'added': result['ItemsAdded'],
                'update': result['ItemsUpdated'],
                'userdata': result['UserDataChanged'],
                'remove': result['ItemsRemoved']
            }
            
        except (KeyError, TypeError):
            self.logMsg("Failed to retrieve latest updates using fast sync.", 1)
            return False
        
        else:
            self.logMsg("Fast sync changes: %s" % result, 1)
            for action in processlist:
                self.triage_items(action, processlist[action])

            return True

    def saveLastSync(self):
        # Save last sync time
        overlap = 2

        url = "{server}/Emby.Kodi.SyncQueue/GetServerDateTime?format=json"
        result = self.doUtils.downloadUrl(url)
        try: # datetime fails when used more than once, TypeError
            server_time = result['ServerDateTime']
            server_time = datetime.strptime(server_time, "%Y-%m-%dT%H:%M:%SZ")
        
        except Exception as e:
            # If the server plugin is not installed or an error happened.
            self.logMsg("An exception occurred: %s" % e, 1)
            time_now = datetime.utcnow()-timedelta(minutes=overlap)
            lastSync = time_now.strftime('%Y-%m-%dT%H:%M:%SZ')
            self.logMsg("New sync time: client time -%s min: %s" % (overlap, lastSync), 1)

        else:
            lastSync = (server_time - timedelta(minutes=overlap)).strftime('%Y-%m-%dT%H:%M:%SZ')
            self.logMsg("New sync time: server time -%s min: %s" % (overlap, lastSync), 1)

        finally:
            utils.settings('LastIncrementalSync', value=lastSync)

    def shouldStop(self):
        # Checkpoint during the syncing process
        if self.monitor.abortRequested():
            return True
        elif utils.window('emby_shouldStop') == "true":
            return True
        else: # Keep going
            return False

    def dbCommit(self, connection):
        # Central commit, verifies if Kodi database update is running
        kodidb_scan = utils.window('emby_kodiScan') == "true"

        while kodidb_scan:

            self.logMsg("Kodi scan is running. Waiting...", 1)
            kodidb_scan = utils.window('emby_kodiScan') == "true"

            if self.shouldStop():
                self.logMsg("Commit unsuccessful. Sync terminated.", 1)
                break

            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                self.logMsg("Commit unsuccessful.", 1)
                break
        else:
            connection.commit()
            self.logMsg("Commit successful.", 1)

    def initializeDBs(self):
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
        self.compare = manualrun
        music_enabled = utils.settings('enableMusic') == "true"

        utils.window('emby_dbScan', value="true")
        # Add sources
        utils.sourcesXML()

        if manualrun:
            message = "Manual sync"
        elif repair:
            message = "Repair sync"
        else:
            message = "Initial sync"
            utils.window('emby_initialScan', value="true")

        starttotal = datetime.now()

        # Set views
        # self.maintainViews(embycursor, kodicursor)
        # embyconn.commit()
        self.initializeDBs()
        # Sync video library
        process = {

            'movies': self.movies,
            'musicvideos': self.musicvideos,
            'tvshows': self.tvshows,
            'homevideos': self.homevideos
        }

        process = {
            'movies': self.PlexMovies
            # 'tvshows': self.PlexTVShows
        }

        for itemtype in process:
            startTime = datetime.now()
            completed = process[itemtype]()
            if not completed:
                
                utils.window('emby_dbScan', clear=True)

                return False
            else:
                elapsedTime = datetime.now() - startTime
                self.logMsg(
                    "SyncDatabase (finished %s in: %s)"
                    % (itemtype, str(elapsedTime).split('.')[0]), 0)

        # # sync music
        # if music_enabled:
            
        #     musicconn = utils.kodiSQL('music')
        #     musiccursor = musicconn.cursor()
            
        #     startTime = datetime.now()
        #     completed = self.music(embycursor, musiccursor, pDialog, compare=manualrun)
        #     if not completed:

        #         utils.window('emby_dbScan', clear=True)

        #         embycursor.close()
        #         musiccursor.close()
        #         return False
        #     else:
        #         musicconn.commit()
        #         embyconn.commit()
        #         elapsedTime = datetime.now() - startTime
        #         self.logMsg(
        #             "SyncDatabase (finished music in: %s)"
        #             % (str(elapsedTime).split('.')[0]), 1)
        #     musiccursor.close()

        utils.settings('SyncInstallRunDone', value="true")
        utils.settings("dbCreatedWithVersion", self.clientInfo.getVersion())
        self.saveLastSync()
        # tell any widgets to refresh because the content has changed
        utils.window('widgetreload', value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        xbmc.executebuiltin('UpdateLibrary(video)')
        elapsedtotal = datetime.now() - starttotal

        utils.window('emby_dbScan', clear=True)
        xbmcgui.Dialog().notification(
                        heading="Emby for Kodi",
                        message="%s completed in: %s" % 
                                (message, str(elapsedtotal).split('.')[0]),
                        icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                        sound=False)
        return True


    def refreshViews(self):

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()

        # Compare views, assign correct tags to items
        self.maintainViews(embycursor, kodicursor)
        
        self.dbCommit(kodiconn)
        kodicursor.close()

        embyconn.commit()
        embycursor.close()

    def maintainViews(self, embycursor, kodicursor):
        """
        Reverse engineering:

        Input:
            embycursor
            kodicursor
        Output:
            vnodes.viewNode(totalnodes, foldername, mediatype, viewtype)
            kodi_db.createTag(foldername)
            kodi_db.updateTag(current_tagid, tagid, item[0],Current_viewtype[:-1])
        """
        # Compare the views to emby
        emby_db = embydb.Embydb_Functions(embycursor)
        kodi_db = kodidb.Kodidb_Functions(kodicursor)
        doUtils = self.doUtils
        vnodes = self.vnodes
        
        # Get views
        url = "{server}/emby/Users/{UserId}/Views?format=json"
        result = doUtils.downloadUrl(url)
        grouped_views = result['Items']

        try:
            groupedFolders = self.user.userSettings['Configuration']['GroupedFolders']
        except TypeError:
            url = "{server}/emby/Users/{UserId}?format=json"
            result = doUtils.downloadUrl(url)
            groupedFolders = result['Configuration']['GroupedFolders']

        # total nodes for window properties
        vnodes.clearProperties()
        totalnodes = 0

        # Set views for supported media type
        mediatypes = ['movies', 'tvshows', 'musicvideos', 'homevideos', 'music']
        for mediatype in mediatypes:

            # Get media folders from server
            folders = self.emby.getViews(mediatype, root=True)
            for folder in folders:

                folderid = folder['id']
                foldername = folder['name']
                viewtype = folder['type']
                
                if folderid in groupedFolders:
                    # Media folders are grouped into userview
                    for grouped_view in grouped_views:
                        # This is only reserved for the detection of grouped views
                        if (grouped_view['Type'] == "UserView" and 
                            grouped_view.get('CollectionType') == mediatype and
                            grouped_view['Id'] not in grouped_view['Path']):
                            # Take the name of the userview
                            foldername = grouped_view['Name']
                            break

                # Get current media folders from emby database
                view = emby_db.getView_byId(folderid)
                try:
                    current_viewname = view[0]
                    current_viewtype = view[1]
                    current_tagid = view[2]

                except TypeError:
                    self.logMsg("Creating viewid: %s in Emby database." % folderid, 1)
                    tagid = kodi_db.createTag(foldername)
                    # Create playlist for the video library
                    if mediatype != "music":
                        utils.playlistXSP(mediatype, foldername, viewtype)
                        # Create the video node
                        if mediatype != "musicvideos":
                            vnodes.viewNode(totalnodes, foldername, mediatype, viewtype)
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
                        self.logMsg("viewid: %s new viewname: %s" % (folderid, foldername), 1)
                        tagid = kodi_db.createTag(foldername)
                        
                        # Update view with new info
                        emby_db.updateView(foldername, tagid, folderid)

                        if mediatype != "music":
                            if emby_db.getView_byName(current_viewname) is None:
                                # The tag could be a combined view. Ensure there's no other tags
                                # with the same name before deleting playlist.
                                utils.playlistXSP(
                                    mediatype, current_viewname, current_viewtype, True)
                                # Delete video node
                                if mediatype != "musicvideos":
                                    vnodes.viewNode(
                                        indexnumber=totalnodes,
                                        tagname=current_viewname,
                                        mediatype=mediatype,
                                        viewtype=current_viewtype,
                                        delete=True)
                            # Added new playlist
                            utils.playlistXSP(mediatype, foldername, viewtype)
                            # Add new video node
                            if mediatype != "musicvideos":
                                vnodes.viewNode(totalnodes, foldername, mediatype, viewtype)
                                totalnodes += 1
                        
                        # Update items with new tag
                        items = emby_db.getItem_byView(folderid)
                        for item in items:
                            # Remove the "s" from viewtype for tags
                            kodi_db.updateTag(
                                current_tagid, tagid, item[0], current_viewtype[:-1])
                    else:
                        if mediatype != "music":
                            # Validate the playlist exists or recreate it
                            utils.playlistXSP(mediatype, foldername, viewtype)
                            # Create the video node if not already exists
                            if mediatype != "musicvideos":
                                vnodes.viewNode(totalnodes, foldername, mediatype, viewtype)
                                totalnodes += 1
        else:
            # Add video nodes listings
            vnodes.singleNode(totalnodes, "Favorite movies", "movies", "favourites")
            totalnodes += 1
            vnodes.singleNode(totalnodes, "Favorite tvshows", "tvshows", "favourites")
            totalnodes += 1
            vnodes.singleNode(totalnodes, "channels", "movies", "channels")
            totalnodes += 1
            # Save total
            utils.window('Emby.nodes.total', str(totalnodes))

    def GetUpdatelist(self, elementList):
        """
        Adds items to self.updatelist as well as self.allPlexElementsId dict

        Input:
            elementList:           List of elements, e.g. a list of '_children'
                                   movie elements as received via JSON from PMS

        Output: self.updatelist, self.allPlexElementsId
            self.updatelist             APPENDED(!!) list itemids (Plex Keys as
                                        as received from API.getKey())
            self.allPlexElementsId      APPENDED(!!) dic
                = {itemid: checksum}
        """
        if self.compare:
            # Manual sync
            for plexmovie in elementList:
                if self.shouldStop():
                    return False
                API = PlexAPI.API(plexmovie)
                plex_checksum = API.getChecksum()
                itemid = API.getKey()
                self.allPlexElementsId[itemid] = plex_checksum
                kodi_checksum = self.allKodiElementsId.get(itemid)
                if kodi_checksum != plex_checksum:
                    # Only update if movie is not in Kodi or checksum is
                    # different
                    self.updatelist.append(itemid)
        else:
            # Initial or repair sync: get all Plex movies
            for plexmovie in elementList:
                API = PlexAPI.API(plexmovie)
                itemid = API.getKey()
                plex_checksum = API.getChecksum()
                self.allPlexElementsId[itemid] = plex_checksum
                self.updatelist.append(itemid)
        # Update the Kodi popup info
        return self.updatelist, self.allPlexElementsId

    def PlexMovies(self):
        # Initialize
        plx = PlexAPI.PlexAPI()
        compare = self.compare
        self.updatelist = []
        self.allPlexElementsId = {}
        # Initialze DBs
        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()

        # Get movies from Plex server
        emby_db = embydb.Embydb_Functions(embycursor)

        views = plx.GetPlexCollections('movie')
        self.logMsg("Media folders: %s" % views, 1)

        if compare:
            # Pull the list of movies and boxsets in Kodi
            try:
                self.allKodiElementsId = dict(emby_db.getChecksum('Movie'))
            except ValueError:
                self.allKodiElementsId = {}
        else:
            # Getting all metadata, hence set Kodi elements to {}
            self.allKodiElementsId = {}
        embyconn.close()

        ##### PROCESS MOVIES #####
        for view in views:
            self.updatelist = []
            if self.shouldStop():
                return False
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            all_plexmovies = plx.GetPlexSectionResults(viewId)
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(all_plexmovies)
            self.logMsg("Processed view %s with ID %s" % (viewName, viewId), 1)

        self.logMsg("self.updatelist: %s" % self.updatelist, 2)
        self.logMsg("self.allPlexElementsId: %s" % self.allPlexElementsId, 2)
        self.logMsg("self.allKodiElementsId: %s" % self.allKodiElementsId, 2)

        # Run through self.updatelist, get XML metadata per item
        # Initiate threads
        self.logMsg("=====================", 1)
        self.logMsg("Starting sync threads", 1)
        self.logMsg("=====================", 1)
        getMetadataQueue = Queue.Queue()
        processMetadataQueue = Queue.Queue()
        getMetadataLock = threading.Lock()
        processMetadataLock = threading.Lock()
        # To keep track
        global getMetadataCount
        getMetadataCount = 0
        global processMetadataCount
        processMetadataCount = 0
        # Spawn GetMetadata threads
        threads = []
        for i in range(self.syncThreadNumber):
            t = ThreadedGetMetadata(
                getMetadataQueue,
                processMetadataQueue,
                getMetadataLock,
                self.shouldStop
            )
            t.setDaemon(True)
            t.start()
            threads.append(t)
        self.logMsg("%s download threads spawned" % self.syncThreadNumber, 1)
        # Populate queue: GetMetadata
        for itemId in self.updatelist:
            getMetadataQueue.put(itemId)
        self.logMsg("Queue populated", 1)
        # Spawn one more thread to process Metadata, once downloaded
        data = {
            'itemType': 'Movies',
            'viewName': viewName,
            'viewId': viewId
        }
        thread = ThreadedProcessMetadata(
            processMetadataQueue,
            data,
            processMetadataLock,
            self.shouldStop
        )
        thread.setDaemon(True)
        thread.start()
        threads.append(thread)
        self.logMsg("Processing thread spawned", 1)

        # Start one thread to show sync progress
        dialog = xbmcgui.DialogProgressBG()
        total = len(self.updatelist)
        thread = ThreadedShowSyncInfo(
            dialog,
            [getMetadataLock, processMetadataLock],
            total,
            viewName
        )
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
            thread.join()
        dialog.close()
        self.logMsg("=====================", 1)
        self.logMsg("Sync threads finished", 1)
        self.logMsg("=====================", 1)

        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            itemFkt = getattr(itemtypes, 'Movies')
            with itemFkt() as item:
                for kodimovie in self.allKodiElementsId:
                    if kodimovie not in self.allPlexElementsId:
                        item.remove(kodimovie)
                else:
                    self.logMsg("Movies compare finished.", 1)
        return True

    def movies(self, embycursor, kodicursor, pdialog, compare=False):
        # Get movies from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        movies = itemtypes.Movies(embycursor, kodicursor)

        views = emby_db.getView_byType('movies')
        views += emby_db.getView_byType('mixed')
        self.logMsg("Media folders: %s" % views, 1)

        if compare:
            # Pull the list of movies and boxsets in Kodi
            try:
                all_kodimovies = dict(emby_db.getChecksum('Movie'))
            except ValueError:
                all_kodimovies = {}

            try:
                all_kodisets = dict(emby_db.getChecksum('BoxSet'))
            except ValueError:
                all_kodisets = {}

            all_embymoviesIds = set()
            all_embyboxsetsIds = set()
            updatelist = []

        ##### PROCESS MOVIES #####
        for view in views:
            
            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="Gathering movies from view: %s..." % viewName)

            if compare:
                # Manual sync
                if pdialog:
                    pdialog.update(
                            heading="Emby for Kodi",
                            message="Comparing movies from view: %s..." % viewName)

                all_embymovies = emby.getMovies(viewId, basic=True)
                for embymovie in all_embymovies['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embymovie)
                    itemid = embymovie['Id']
                    all_embymoviesIds.add(itemid)

                    
                    if all_kodimovies.get(itemid) != API.getChecksum():
                        # Only update if movie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                self.logMsg("Movies to update for %s: %s" % (viewName, updatelist), 1)
                embymovies = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                # Initial or repair sync
                all_embymovies = emby.getMovies(viewId)
                total = all_embymovies['TotalRecordCount']
                embymovies = all_embymovies['Items']


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymovie in embymovies:
                # Process individual movies
                if self.shouldStop():
                    return False
                
                title = embymovie['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                movies.add_update(embymovie, viewName, viewId)
        else:
            self.logMsg("Movies finished.", 2)


        ##### PROCESS BOXSETS #####
        if pdialog:
            pdialog.update(heading="Emby for Kodi", message="Gathering boxsets from server...")
        
        boxsets = emby.getBoxset()

        if compare:
            # Manual sync
            embyboxsets = []

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="Comparing boxsets...")

            for boxset in boxsets['Items']:

                if self.shouldStop():
                    return False

                # Boxset has no real userdata, so using etag to compare
                checksum = boxset['Etag']
                itemid = boxset['Id']
                all_embyboxsetsIds.add(itemid)

                if all_kodisets.get(itemid) != checksum:
                    # Only update if boxset is not in Kodi or checksum is different
                    updatelist.append(itemid)
                    embyboxsets.append(boxset)

            self.logMsg("Boxsets to update: %s" % updatelist, 1)
            total = len(updatelist)
        else:
            total = boxsets['TotalRecordCount']
            embyboxsets = boxsets['Items']
            

        if pdialog:
            pdialog.update(heading="Processing Boxsets / %s items" % total)

        count = 0
        for boxset in embyboxsets:
            # Process individual boxset
            if self.shouldStop():
                return False

            title = boxset['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            movies.add_updateBoxset(boxset)
        else:
            self.logMsg("Boxsets finished.", 2)


        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for kodimovie in all_kodimovies:
                if kodimovie not in all_embymoviesIds:
                    movies.remove(kodimovie)
            else:
                self.logMsg("Movies compare finished.", 1)

            for boxset in all_kodisets:
                if boxset not in all_embyboxsetsIds:
                    movies.remove(boxset)
            else:
                self.logMsg("Boxsets compare finished.", 1)

        return True

    def musicvideos(self, embycursor, kodicursor, pdialog, compare=False):
        # Get musicvideos from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        mvideos = itemtypes.MusicVideos(embycursor, kodicursor)

        views = emby_db.getView_byType('musicvideos')
        self.logMsg("Media folders: %s" % views, 1)

        if compare:
            # Pull the list of musicvideos in Kodi
            try:
                all_kodimvideos = dict(emby_db.getChecksum('MusicVideo'))
            except ValueError:
                all_kodimvideos = {}

            all_embymvideosIds = set()
            updatelist = []

        for view in views:
            
            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="Gathering musicvideos from view: %s..." % viewName)

            if compare:
                # Manual sync
                if pdialog:
                    pdialog.update(
                            heading="Emby for Kodi",
                            message="Comparing musicvideos from view: %s..." % viewName)

                all_embymvideos = emby.getMusicVideos(viewId, basic=True)
                for embymvideo in all_embymvideos['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embymvideo)
                    itemid = embymvideo['Id']
                    all_embymvideosIds.add(itemid)

                    
                    if all_kodimvideos.get(itemid) != API.getChecksum():
                        # Only update if musicvideo is not in Kodi or checksum is different
                        updatelist.append(itemid)

                self.logMsg("MusicVideos to update for %s: %s" % (viewName, updatelist), 1)
                embymvideos = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                # Initial or repair sync
                all_embymvideos = emby.getMusicVideos(viewId)
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
            self.logMsg("MusicVideos finished.", 2)
        
        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for kodimvideo in all_kodimvideos:
                if kodimvideo not in all_embymvideosIds:
                    mvideos.remove(kodimvideo)
            else:
                self.logMsg("MusicVideos compare finished.", 1)

        return True

    def homevideos(self, embycursor, kodicursor, pdialog, compare=False):
        # Get homevideos from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        hvideos = itemtypes.HomeVideos(embycursor, kodicursor)

        views = emby_db.getView_byType('homevideos')
        self.logMsg("Media folders: %s" % views, 1)

        if compare:
            # Pull the list of homevideos in Kodi
            try:
                all_kodihvideos = dict(emby_db.getChecksum('Video'))
            except ValueError:
                all_kodihvideos = {}

            all_embyhvideosIds = set()
            updatelist = []

        for view in views:
            
            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="Gathering homevideos from view: %s..." % viewName)
            
            all_embyhvideos = emby.getHomeVideos(viewId)

            if compare:
                # Manual sync
                if pdialog:
                    pdialog.update(
                            heading="Emby for Kodi",
                            message="Comparing homevideos from view: %s..." % viewName)

                for embyhvideo in all_embyhvideos['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embyhvideo)
                    itemid = embyhvideo['Id']
                    all_embyhvideosIds.add(itemid)

                    
                    if all_kodihvideos.get(itemid) != API.getChecksum():
                        # Only update if homemovie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                self.logMsg("HomeVideos to update for %s: %s" % (viewName, updatelist), 1)
                embyhvideos = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                total = all_embyhvideos['TotalRecordCount']
                embyhvideos = all_embyhvideos['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embyhvideo in embyhvideos:
                # Process individual homemovies
                if self.shouldStop():
                    return False
                
                title = embyhvideo['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                hvideos.add_update(embyhvideo, viewName, viewId)
        else:
            self.logMsg("HomeVideos finished.", 2)

        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for kodihvideo in all_kodihvideos:
                if kodihvideo not in all_embyhvideosIds:
                    hvideos.remove(kodihvideo)
            else:
                self.logMsg("HomeVideos compare finished.", 1)
        
        return True

    def PlexTVShows(self, embycursor, kodicursor):
        # Initialize
        plx = PlexAPI.PlexAPI()
        compare = self.compare
        pdialog = self.pDialog
        self.updatelist = []
        self.allPlexElementsId = {}
        # Get shows from emby
        emby_db = embydb.Embydb_Functions(embycursor)
        tvshows = itemtypes.TVShows(embycursor, kodicursor)

        views = plx.GetPlexCollections('show')
        self.logMsg("Media folders: %s" % views, 1)

        self.allKodiElementsId = {}
        if compare:
            # Pull the list of TV shows already in Kodi
            try:
                all_koditvshows = dict(emby_db.getChecksum('Series'))
                self.allKodiElementsId.update(all_koditvshows)
            except ValueError:
                pass
            # Same for the episodes (sub-element of shows/series)
            try:
                all_kodiepisodes = dict(emby_db.getChecksum('Episode'))
                self.allKodiElementsId.update(all_kodiepisodes)
            except ValueError:
                pass

        for view in views:
            self.updatelist = []
            if self.shouldStop():
                return False
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            if pdialog:
                pdialog.update(
                    heading=self.addonName,
                    message="Gathering TV Shows from view: %s..." % viewName)
            all_plexTvShows = plx.GetPlexSectionResults(viewId)

            # Populate self.updatelist with TV shows and self.allPlexElementsId
            self.GetUpdatelist(all_plexTvShows, viewName)

            # Run through self.updatelist, get XML metadata per item and safe
            # to Kodi
            self.ProcessUpdateList(tvshows, view)



            if compare:
                # Manual sync
                for plexTvShow in all_plexTvShows:
                    if self.shouldStop():
                        return False
                    API = plx(plexTvShow)
                    plex_checksum = API.getChecksum()
                    itemid = API.getKey()
                    kodi_checksum = all_kodimoviesId.get(itemid)
                    all_plextvshowsIds[itemid] = itemid
                    kodi_checksum = all_koditvshows.get(itemid)
                    #if kodi_checksum != plex_checksum:

                    
                    if all_koditvshows.get(itemid) != API.getChecksum():
                        # Only update if movie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                self.logMsg("TVShows to update for %s: %s" % (viewName, updatelist), 1)
                embytvshows = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                all_embytvshows = emby.getShows(viewId)
                total = all_embytvshows['TotalRecordCount']
                embytvshows = all_embytvshows['Items']


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embytvshow in embytvshows:
                # Process individual show
                if self.shouldStop():
                    return False
                
                itemid = embytvshow['Id']
                title = embytvshow['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                tvshows.add_update(embytvshow, viewName, viewId)

                if not compare:
                    # Process episodes
                    all_episodes = emby.getEpisodesbyShow(itemid)
                    for episode in all_episodes['Items']:

                        # Process individual show
                        if self.shouldStop():
                            return False

                        episodetitle = episode['Name']
                        if pdialog:
                            pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                        tvshows.add_updateEpisode(episode)
            else:
                if compare:
                    # Get all episodes in view
                    if pdialog:
                        pdialog.update(
                                heading="Emby for Kodi",
                                message="Comparing episodes from view: %s..." % viewName)

                    all_embyepisodes = emby.getEpisodes(viewId, basic=True)
                    for embyepisode in all_embyepisodes['Items']:

                        if self.shouldStop():
                            return False

                        API = api.API(embyepisode)
                        itemid = embyepisode['Id']
                        all_embyepisodesIds.add(itemid)

                        if all_kodiepisodes.get(itemid) != API.getChecksum():
                            # Only update if movie is not in Kodi or checksum is different
                            updatelist.append(itemid)

                    self.logMsg("Episodes to update for %s: %s" % (viewName, updatelist), 1)
                    embyepisodes = emby.getFullItems(updatelist)
                    total = len(updatelist)
                    del updatelist[:]

                    count = 0
                    for episode in embyepisodes:

                        # Process individual episode
                        if self.shouldStop():
                            return False                          

                        title = episode['SeriesName']
                        episodetitle = episode['Name']
                        if pdialog:
                            percentage = int((float(count) / float(total))*100)
                            pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                            count += 1
                        tvshows.add_updateEpisode(episode)
        else:
            self.logMsg("TVShows finished.", 2)
        
        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for koditvshow in all_koditvshows:
                if koditvshow not in all_embytvshowsIds:
                    tvshows.remove(koditvshow)
            else:
                self.logMsg("TVShows compare finished.", 1)

            for kodiepisode in all_kodiepisodes:
                if kodiepisode not in all_embyepisodesIds:
                    tvshows.remove(kodiepisode)
            else:
                self.logMsg("Episodes compare finished.", 1)

        return True

    def tvshows(self, embycursor, kodicursor, pdialog, compare=False):
        # Get shows from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        tvshows = itemtypes.TVShows(embycursor, kodicursor)

        views = emby_db.getView_byType('tvshows')
        views += emby_db.getView_byType('mixed')
        self.logMsg("Media folders: %s" % views, 1)

        if compare:
            # Pull the list of movies and boxsets in Kodi
            try:
                all_koditvshows = dict(emby_db.getChecksum('Series'))
            except ValueError:
                all_koditvshows = {}

            try:
                all_kodiepisodes = dict(emby_db.getChecksum('Episode'))
            except ValueError:
                all_kodiepisodes = {}

            all_embytvshowsIds = set()
            all_embyepisodesIds = set()
            updatelist = []


        for view in views:
            
            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="Gathering tvshows from view: %s..." % viewName)

            if compare:
                # Manual sync
                if pdialog:
                    pdialog.update(
                            heading="Emby for Kodi",
                            message="Comparing tvshows from view: %s..." % viewName)

                all_embytvshows = emby.getShows(viewId, basic=True)
                for embytvshow in all_embytvshows['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embytvshow)
                    itemid = embytvshow['Id']
                    all_embytvshowsIds.add(itemid)

                    
                    if all_koditvshows.get(itemid) != API.getChecksum():
                        # Only update if movie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                self.logMsg("TVShows to update for %s: %s" % (viewName, updatelist), 1)
                embytvshows = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                all_embytvshows = emby.getShows(viewId)
                total = all_embytvshows['TotalRecordCount']
                embytvshows = all_embytvshows['Items']


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embytvshow in embytvshows:
                # Process individual show
                if self.shouldStop():
                    return False
                
                itemid = embytvshow['Id']
                title = embytvshow['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                tvshows.add_update(embytvshow, viewName, viewId)

                if not compare:
                    # Process episodes
                    all_episodes = emby.getEpisodesbyShow(itemid)
                    for episode in all_episodes['Items']:

                        # Process individual show
                        if self.shouldStop():
                            return False

                        episodetitle = episode['Name']
                        if pdialog:
                            pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                        tvshows.add_updateEpisode(episode)
            else:
                if compare:
                    # Get all episodes in view
                    if pdialog:
                        pdialog.update(
                                heading="Emby for Kodi",
                                message="Comparing episodes from view: %s..." % viewName)

                    all_embyepisodes = emby.getEpisodes(viewId, basic=True)
                    for embyepisode in all_embyepisodes['Items']:

                        if self.shouldStop():
                            return False

                        API = api.API(embyepisode)
                        itemid = embyepisode['Id']
                        all_embyepisodesIds.add(itemid)

                        if all_kodiepisodes.get(itemid) != API.getChecksum():
                            # Only update if movie is not in Kodi or checksum is different
                            updatelist.append(itemid)

                    self.logMsg("Episodes to update for %s: %s" % (viewName, updatelist), 1)
                    embyepisodes = emby.getFullItems(updatelist)
                    total = len(updatelist)
                    del updatelist[:]

                    count = 0
                    for episode in embyepisodes:

                        # Process individual episode
                        if self.shouldStop():
                            return False                          

                        title = episode['SeriesName']
                        episodetitle = episode['Name']
                        if pdialog:
                            percentage = int((float(count) / float(total))*100)
                            pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                            count += 1
                        tvshows.add_updateEpisode(episode)
        else:
            self.logMsg("TVShows finished.", 2)
        
        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for koditvshow in all_koditvshows:
                if koditvshow not in all_embytvshowsIds:
                    tvshows.remove(koditvshow)
            else:
                self.logMsg("TVShows compare finished.", 1)

            for kodiepisode in all_kodiepisodes:
                if kodiepisode not in all_embyepisodesIds:
                    tvshows.remove(kodiepisode)
            else:
                self.logMsg("Episodes compare finished.", 1)

        return True

    def music(self, embycursor, kodicursor, pdialog, compare=False):
        # Get music from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        music = itemtypes.Music(embycursor, kodicursor)

        if compare:
            # Pull the list of movies and boxsets in Kodi
            try:
                all_kodiartists = dict(emby_db.getChecksum('MusicArtist'))
            except ValueError:
                all_kodiartists = {}

            try:
                all_kodialbums = dict(emby_db.getChecksum('MusicAlbum'))
            except ValueError:
                all_kodialbums = {}

            try:
                all_kodisongs = dict(emby_db.getChecksum('Audio'))
            except ValueError:
                all_kodisongs = {}

            all_embyartistsIds = set()
            all_embyalbumsIds = set()
            all_embysongsIds = set()
            updatelist = []

        process = {

            'artists': [emby.getArtists, music.add_updateArtist],
            'albums': [emby.getAlbums, music.add_updateAlbum],
            'songs': [emby.getSongs, music.add_updateSong]
        }
        types = ['artists', 'albums', 'songs']
        for type in types:

            if pdialog:
                pass
            if compare:
                # Manual Sync
                if pdialog:
                    pass

                if type != "artists":
                    all_embyitems = process[type][0](basic=True)
                else:
                    all_embyitems = process[type][0]()
                for embyitem in all_embyitems['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embyitem)
                    itemid = embyitem['Id']
                    if type == "artists":
                        all_embyartistsIds.add(itemid)
                        if all_kodiartists.get(itemid) != API.getChecksum():
                            # Only update if artist is not in Kodi or checksum is different
                            updatelist.append(itemid)
                    elif type == "albums":
                        all_embyalbumsIds.add(itemid)
                        if all_kodialbums.get(itemid) != API.getChecksum():
                            # Only update if album is not in Kodi or checksum is different
                            updatelist.append(itemid)
                    else:
                        all_embysongsIds.add(itemid)
                        if all_kodisongs.get(itemid) != API.getChecksum():
                            # Only update if songs is not in Kodi or checksum is different
                            updatelist.append(itemid)

                self.logMsg("%s to update: %s" % (type, updatelist), 1)
                embyitems = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]
            else:
                all_embyitems = process[type][0]()
                total = all_embyitems['TotalRecordCount']
                embyitems = all_embyitems['Items']

            if pdialog:
                pass

            count = 0
            for embyitem in embyitems:
                # Process individual item
                if self.shouldStop():
                    return False
                
                title = embyitem['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1

                process[type][1](embyitem)
            else:
                self.logMsg("%s finished." % type, 2)

        ##### PROCESS DELETES #####
        if compare:
            # Manual sync, process deletes
            for kodiartist in all_kodiartists:
                if kodiartist not in all_embyartistsIds and all_kodiartists[kodiartist] is not None:
                    music.remove(kodiartist)
            else:
                self.logMsg("Artist compare finished.", 1)

            for kodialbum in all_kodialbums:
                if kodialbum not in all_embyalbumsIds:
                    music.remove(kodialbum)
            else:
                self.logMsg("Albums compare finished.", 1)

            for kodisong in all_kodisongs:
                if kodisong not in all_embysongsIds:
                    music.remove(kodisong)
            else:
                self.logMsg("Songs compare finished.", 1)

        return True

    # Reserved for websocket_client.py and fast start
    def triage_items(self, process, items):

        processlist = {

            'added': self.addedItems,
            'update': self.updateItems,
            'userdata': self.userdataItems,
            'remove': self.removeItems
        }
        if items:
            if process == "userdata":
                itemids = []
                for item in items:
                    itemids.append(item['ItemId'])
                items = itemids

            self.logMsg("Queue %s: %s" % (process, items), 1)
            processlist[process].extend(items)

    def incrementalSync(self):
        
        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        pDialog = None

        if self.refresh_views:
            # Received userconfig update
            self.refresh_views = False
            self.maintainViews(embycursor, kodicursor)
            self.forceLibraryUpdate = True

        if self.addedItems or self.updateItems or self.userdataItems or self.removeItems:
            # Only present dialog if we are going to process items
            pDialog = self.progressDialog('Incremental sync')


        process = {

            'added': self.addedItems,
            'update': self.updateItems,
            'userdata': self.userdataItems,
            'remove': self.removeItems
        }
        types = ['added', 'update', 'userdata', 'remove']
        for type in types:

            if process[type] and utils.window('emby_kodiScan') != "true":
                
                listItems = list(process[type])
                del process[type][:] # Reset class list

                items_process = itemtypes.Items(embycursor, kodicursor)
                update = False

                # Prepare items according to process type
                if type == "added":
                    items = emby.sortby_mediatype(listItems)

                elif type in ("userdata", "remove"):
                    items = emby_db.sortby_mediaType(listItems, unsorted=False)
                
                else:
                    items = emby_db.sortby_mediaType(listItems)
                    if items.get('Unsorted'):
                        sorted_items = emby.sortby_mediatype(items['Unsorted'])
                        doupdate = items_process.itemsbyId(sorted_items, "added", pDialog)
                        if doupdate:
                            update = True
                        del items['Unsorted']

                doupdate = items_process.itemsbyId(items, type, pDialog)
                if doupdate:
                    update = True
                    
                if update:
                    self.forceLibraryUpdate = True


        if self.forceLibraryUpdate:
            # Force update the Kodi library
            self.forceLibraryUpdate = False
            self.dbCommit(kodiconn)
            embyconn.commit()
            self.saveLastSync()

            # tell any widgets to refresh because the content has changed
            utils.window('widgetreload', value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            self.logMsg("Updating video library.", 1)
            utils.window('emby_kodiScan', value="true")
            xbmc.executebuiltin('UpdateLibrary(video)')

        if pDialog:
            pDialog.close()

        kodicursor.close()
        embycursor.close()


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
            xbmcgui.Dialog().ok(
                        heading="Emby for Kodi",
                        line1=(
                            "Library sync thread has exited! "
                            "You should restart Kodi now. "
                            "Please report this on the forum."))
            raise

    def run_internal(self):

        startupComplete = False
        monitor = self.monitor

        self.logMsg("---===### Starting LibrarySync ###===---", 0)

        while not monitor.abortRequested():

            # In the event the server goes offline
            while self.suspend_thread:
                # Set in service.py
                if monitor.waitForAbort(5):
                    # Abort was requested while waiting. We should exit
                    break

            if (utils.window('emby_dbCheck') != "true" and
                    utils.settings('SyncInstallRunDone') == "true"):
                
                # Verify the validity of the database
                currentVersion = utils.settings('dbCreatedWithVersion')
                minVersion = utils.window('emby_minDBVersion')
                uptoDate = self.compareDBVersion(currentVersion, minVersion)

                if not uptoDate:
                    self.logMsg(
                        "Db version out of date: %s minimum version required: %s"
                        % (currentVersion, minVersion), 0)
                    
                    resp = xbmcgui.Dialog().yesno(
                                            heading="Db Version",
                                            line1=(
                                                "Detected the database needs to be "
                                                "recreated for this version of Emby for Kodi. "
                                                "Proceed?"))
                    if not resp:
                        self.logMsg("Db version out of date! USER IGNORED!", 0)
                        xbmcgui.Dialog().ok(
                                        heading="Emby for Kodi",
                                        line1=(
                                            "Emby for Kodi may not work correctly "
                                            "until the database is reset."))
                    else:
                        utils.reset()

                utils.window('emby_dbCheck', value="true")


            if not startupComplete:
                # Verify the video database can be found
                videoDb = utils.getKodiVideoDBPath()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    self.logMsg(
                            "The current Kodi version is incompatible "
                            "with the Emby for Kodi add-on. Please visit "
                            "https://github.com/MediaBrowser/Emby.Kodi/wiki "
                            "to know which Kodi versions are supported.", 0)

                    xbmcgui.Dialog().ok(
                                    heading="Emby Warning",
                                    line1=(
                                        "Cancelling the database syncing process. "
                                        "Current Kodi versoin: %s is unsupported. "
                                        "Please verify your logs for more info."
                                        % xbmc.getInfoLabel('System.BuildVersion')))
                    break

                # Run start up sync
                self.logMsg("Db version: %s" % utils.settings('dbCreatedWithVersion'), 0)
                self.logMsg("SyncDatabase (started)", 1)
                startTime = datetime.now()
                librarySync = self.startSync()
                elapsedTime = datetime.now() - startTime
                self.logMsg(
                    "SyncDatabase (finished in: %s) %s"
                    % (str(elapsedTime).split('.')[0], librarySync), 1)
                # Only try the initial sync once per kodi session regardless
                # This will prevent an infinite loop in case something goes wrong.
                startupComplete = True

            # Process updates
            if utils.window('emby_dbScan') != "true":
                self.incrementalSync()

            if (utils.window('emby_onWake') == "true" and
                    utils.window('emby_online') == "true"):
                # Kodi is waking up
                # Set in kodimonitor.py
                utils.window('emby_onWake', clear=True)
                if utils.window('emby_syncRunning') != "true":
                    self.logMsg("SyncDatabase onWake (started)", 0)
                    librarySync = self.startSync()
                    self.logMsg("SyncDatabase onWake (finished) %s" % librarySync, 0)

            if self.stop_thread:
                # Set in service.py
                self.logMsg("Service terminated thread.", 2)
                break

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        self.logMsg("###===--- LibrarySync Stopped ---===###", 0)

    def stopThread(self):
        self.stop_thread = True
        self.logMsg("Ending thread...", 2)

    def suspendThread(self):
        self.suspend_thread = True
        self.logMsg("Pausing thread...", 0)

    def resumeThread(self):
        self.suspend_thread = False
        self.logMsg("Resuming thread...", 0)
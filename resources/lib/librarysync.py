# -*- coding: utf-8 -*-

###############################################################################

from threading import Thread, Lock
import Queue

import xbmc
import xbmcgui
import xbmcvfs
import xbmcaddon

import utils
import clientinfo
import downloadutils
import itemtypes
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver
import userclient
import videonodes

import PlexFunctions as PF
import PlexAPI

###############################################################################


@utils.logging
@utils.ThreadMethodsAdditionalStop('suspend_LibraryThread')
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
    def __init__(self, queue, out_queue, lock, processlock):
        self.queue = queue
        self.out_queue = out_queue
        self.lock = lock
        self.processlock = processlock
        Thread.__init__(self)

    def terminateNow(self):
        while not self.queue.empty():
            # Still try because remaining item might have been taken
            try:
                self.queue.get(block=False)
            except Queue.Empty:
                xbmc.sleep(50)
                continue
            else:
                self.queue.task_done()
        if utils.window('plex_terminateNow') == 'true':
            # Extreme measures if Kodi shutdown requested
            while not self.out_queue.empty():
                # Still try because remaining item might have been taken
                try:
                    self.out_queue.get(block=False)
                except Queue.Empty:
                    xbmc.sleep(50)
                    continue
                else:
                    self.out_queue.task_done()

    def run(self):
        # cache local variables because it's faster
        queue = self.queue
        out_queue = self.out_queue
        lock = self.lock
        processlock = self.processlock
        threadStopped = self.threadStopped
        global getMetadataCount
        global processMetadataCount
        while threadStopped() is False:
            # grabs Plex item from queue
            try:
                updateItem = queue.get(block=False)
            # Empty queue
            except Queue.Empty:
                xbmc.sleep(100)
                continue
            # Download Metadata
            plexXML = PF.GetPlexMetadata(updateItem['itemId'])
            if plexXML is None:
                # Did not receive a valid XML - skip that item for now
                self.logMsg("Could not get metadata for %s. "
                            "Skipping that item for now"
                            % updateItem['itemId'], 0)
                # Increase BOTH counters - since metadata won't be processed
                with lock:
                    getMetadataCount += 1
                with processlock:
                    processMetadataCount += 1
                queue.task_done()
                continue
            elif plexXML == 401:
                self.logMsg('HTTP 401 returned by PMS. Too much strain? '
                            'Cancelling sync for now', -1)
                utils.window('plex_scancrashed', value='401')
                # Kill remaining items in queue (for main thread to cont.)
                queue.task_done()
                break

            updateItem['XML'] = plexXML
            # place item into out queue
            out_queue.put(updateItem)
            # Keep track of where we are at
            with lock:
                getMetadataCount += 1
            # signals to queue job is done
            queue.task_done()
        # Empty queue in case PKC was shut down (main thread hangs otherwise)
        self.terminateNow()
        self.logMsg('Download thread terminated', 2)


@utils.logging
@utils.ThreadMethodsAdditionalStop('suspend_LibraryThread')
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

    def terminateNow(self):
        while not self.queue.empty():
            # Still try because remaining item might have been taken
            try:
                self.queue.get(block=False)
            except Queue.Empty:
                xbmc.sleep(100)
                continue
            else:
                self.queue.task_done()

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
                    xbmc.sleep(50)
                    continue
                # Do the work
                plexitem = updateItem['XML']
                method = updateItem['method']
                viewName = updateItem['viewName']
                viewId = updateItem['viewId']
                title = updateItem['title']
                itemSubFkt = getattr(item, method)
                # Get the one child entry in the xml and process
                for child in plexitem:
                    itemSubFkt(child,
                               viewtag=viewName,
                               viewid=viewId)
                # Keep track of where we are at
                with lock:
                    processMetadataCount += 1
                    processingViewName = title
                # signals to queue job is done
                queue.task_done()
        # Empty queue in case PKC was shut down (main thread hangs otherwise)
        # Sleep, just in case the other threads throw another xml
        xbmc.sleep(1000)
        self.terminateNow()
        self.logMsg('Processing thread terminated', 2)


@utils.logging
@utils.ThreadMethodsAdditionalStop('suspend_LibraryThread')
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
                      % (self.addonName,
                         self.itemType,
                         str(total)),
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
            dialog.update(percentage,
                          message="Downloaded: %s. Processed: %s: %s"
                                  % (getMetadataProgress,
                                     processMetadataProgress,
                                     viewName))
            # Sleep for x milliseconds
            xbmc.sleep(500)
        dialog.close()
        self.logMsg('Dialog Infobox thread terminated', 2)


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('suspend_LibraryThread')
@utils.ThreadMethodsAdditionalStop('emby_shouldStop')
@utils.ThreadMethods
class LibrarySync(Thread):
    """
    librarysync.LibrarySync(queue)

    where (communication with websockets)
        queue:      Queue object for background sync
    """
    # Borg, even though it's planned to only have 1 instance up and running!
    _shared_state = {}

    def __init__(self, queue):
        self.__dict__ = self._shared_state

        self.__language__ = xbmcaddon.Addon().getLocalizedString

        # Communication with websockets
        self.queue = queue
        self.itemsToProcess = []
        self.sessionKeys = []
        # How long should we wait at least to process new/changed PMS items?
        self.saftyMargin = int(utils.settings('saftyMargin'))

        self.fullSyncInterval = int(utils.settings('fullSyncInterval')) * 60

        self.clientInfo = clientinfo.ClientInfo()
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.vnodes = videonodes.VideoNodes()
        self.dialog = xbmcgui.Dialog()

        self.syncThreadNumber = int(utils.settings('syncThreadNumber'))
        self.installSyncDone = True if \
            utils.settings('SyncInstallRunDone') == 'true' else False
        self.showDbSync = True if \
            utils.settings('dbSyncIndicator') == 'true' else False
        self.enableMusic = True if utils.settings('enableMusic') == "true" \
            else False
        self.enableBackgroundSync = True if utils.settings(
            'enableBackgroundSync') == "true" else False
        self.limitindex = int(utils.settings('limitindex'))

        if utils.settings('emby_pathverified') == 'true':
            utils.window('emby_pathverified', value='true')

        # Just in case a time sync goes wrong
        self.timeoffset = int(utils.settings('kodiplextimeoffset'))
        utils.window('kodiplextimeoffset', value=str(self.timeoffset))
        Thread.__init__(self)

    def showKodiNote(self, message, forced=False, icon="plex"):
        """
        Shows a Kodi popup, if user selected to do so. Pass message in unicode
        or string

        icon:   "plex": shows Plex icon
                "error": shows Kodi error icon

        forced: always show popup, even if user setting to off
        """
        if not self.showDbSync:
            if not forced:
                return
        if icon == "plex":
            self.dialog.notification(
                self.addonName,
                message,
                "special://home/addons/plugin.video.plexkodiconnect/icon.png",
                5000,
                False)
        elif icon == "error":
            self.dialog.notification(
                self.addonName,
                message,
                xbmcgui.NOTIFICATION_ERROR,
                7000,
                True)

    def syncPMStime(self):
        """
        PMS does not provide a means to get a server timestamp. This is a work-
        around.

        In general, everything saved to Kodi shall be in Kodi time.

        Any info with a PMS timestamp is in Plex time, naturally
        """
        self.logMsg('Synching time with PMS server', 0)
        # Find a PMS item where we can toggle the view state to enforce a
        # change in lastViewedAt

        # Get all Plex libraries
        sections = downloadutils.DownloadUtils().downloadUrl(
            "{server}/library/sections")
        try:
            sections.attrib
        except AttributeError:
            self.logMsg("Error download PMS views, abort syncPMStime", -1)
            return False

        plexId = None
        for mediatype in ('movie', 'show', 'artist'):
            if plexId is not None:
                break
            for view in sections:
                if plexId is not None:
                    break
                if not view.attrib['type'] == mediatype:
                    continue
                items = PF.GetAllPlexLeaves(view.attrib['key'],
                                            containerSize=self.limitindex)
                if items in (None, 401):
                    self.logMsg("Could not download section %s"
                                % view.attrib['key'], -1)
                    continue
                for item in items:
                    if item.attrib.get('viewCount') is not None:
                        # Don't want to mess with items that have playcount>0
                        continue
                    if item.attrib.get('viewOffset') is not None:
                        # Don't mess with items with a resume point
                        continue
                    plexId = item.attrib.get('ratingKey')
                    self.logMsg('Found an item to sync with: %s' % plexId, 1)
                    break

        if plexId is None:
            self.logMsg("Could not find an item to sync time with", -1)
            self.logMsg("Aborting PMS-Kodi time sync", -1)
            return False

        # Get the Plex item's metadata
        xml = PF.GetPlexMetadata(plexId)
        if xml in (None, 401):
            self.logMsg("Could not download metadata, aborting time sync", -1)
            return False

        libraryId = xml[0].attrib['librarySectionID']
        timestamp = xml[0].attrib.get('lastViewedAt')
        if timestamp is None:
            timestamp = xml[0].attrib.get('updatedAt')
            self.logMsg('Using items updatedAt=%s' % timestamp, 1)
            if timestamp is None:
                timestamp = xml[0].attrib.get('addedAt')
                self.logMsg('Using items addedAt=%s' % timestamp, 1)
                if timestamp is None:
                    timestamp = 0
                    self.logMsg('No timestamp; using 0', 1)

        # Set the timer
        koditime = utils.getUnixTimestamp()
        # Toggle watched state
        PF.scrobble(plexId, 'watched')
        # Let the PMS process this first!
        xbmc.sleep(1000)
        # Get PMS items to find the item we just changed
        items = PF.GetAllPlexLeaves(libraryId,
                                    lastViewedAt=timestamp,
                                    containerSize=self.limitindex)
        # Toggle watched state back
        PF.scrobble(plexId, 'unwatched')
        if items in (None, 401):
            self.logMsg("Could not download metadata, aborting time sync", -1)
            return False

        plextime = None
        for item in items:
            if item.attrib['ratingKey'] == plexId:
                plextime = item.attrib.get('lastViewedAt')
                break

        if plextime is None:
            self.logMsg('Could not get lastViewedAt - aborting', -1)
            return False

        # Calculate time offset Kodi-PMS
        self.timeoffset = int(koditime) - int(plextime)
        utils.window('kodiplextimeoffset', value=str(self.timeoffset))
        utils.settings('kodiplextimeoffset', value=str(self.timeoffset))
        self.logMsg("Time offset Koditime - Plextime in seconds: %s"
                    % str(self.timeoffset), 0)
        return True

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

    @utils.LogTime
    def fullSync(self, repair=False):
        """
        repair=True: force sync EVERY item
        """
        # self.compare == False: we're syncing EVERY item
        # True: we're syncing only the delta, e.g. different checksum
        self.compare = not repair

        xbmc.executebuiltin('InhibitIdleShutdown(true)')
        screensaver = utils.getScreensaver()
        utils.setScreensaver(value="")

        # Add sources
        utils.sourcesXML()

        # Ensure that DBs exist if called for very first time
        self.initializeDBs()

        # Set views. Abort if unsuccessful
        if not self.maintainViews():
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            utils.setScreensaver(value=screensaver)
            return False

        process = {
            'movies': self.PlexMovies,
            'tvshows': self.PlexTVShows,
        }
        if self.enableMusic:
            process['music'] = self.PlexMusic

        # Do the processing
        for itemtype in process:
            if self.threadStopped():
                return False
            if not process[itemtype]():
                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                utils.setScreensaver(value=screensaver)
                return False

        # Let kodi update the views in any case, since we're doing a full sync
        xbmc.executebuiltin('UpdateLibrary(video)')
        if self.enableMusic:
            xbmc.executebuiltin('UpdateLibrary(music)')

        utils.window('emby_initialScan', clear=True)
        xbmc.executebuiltin('InhibitIdleShutdown(false)')
        utils.setScreensaver(value=screensaver)
        if utils.window('plex_scancrashed') == 'true':
            # Show warning if itemtypes.py crashed at some point
            self.dialog.ok(self.addonName, self.__language__(39408))
            utils.window('plex_scancrashed', clear=True)
        elif utils.window('plex_scancrashed') == '401':
            utils.window('plex_scancrashed', clear=True)
            if utils.window('emby_serverStatus') not in ('401', 'Auth'):
                # Plex server had too much and returned ERROR
                self.dialog.ok(self.addonName, self.__language__(39409))

        # Path hack, so Kodis Information screen works
        with kodidb.GetKodiDB('video') as kodi_db:
            try:
                kodi_db.pathHack()
            except Exception as e:
                # Empty movies, tv shows?
                self.logMsg('Path hack failed with error message: %s'
                            % str(e), -1)
        return True

    def processView(self, folderItem, kodi_db, emby_db, totalnodes):
        vnodes = self.vnodes
        folder = folderItem.attrib
        mediatype = folder['type']
        # Only process supported formats
        if mediatype not in ('movie', 'show', 'artist'):
            return totalnodes

        # Prevent duplicate for nodes of the same type
        nodes = self.nodes[mediatype]
        # Prevent duplicate for playlists of the same type
        playlists = self.playlists[mediatype]
        sorted_views = self.sorted_views

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
            self.logMsg("Creating viewid: %s in Plex database."
                        % folderid, 1)
            tagid = kodi_db.createTag(foldername)
            # Create playlist for the video library
            if (foldername not in playlists and
                    mediatype in ('movie', 'show', 'musicvideos')):
                utils.playlistXSP(mediatype, foldername, folderid, viewtype)
                playlists.append(foldername)
            # Create the video node
            if (foldername not in nodes and
                    mediatype not in ("musicvideos", "artist")):
                vnodes.viewNode(sorted_views.index(foldername),
                                foldername,
                                mediatype,
                                viewtype,
                                folderid)
                nodes.append(foldername)
                totalnodes += 1
            # Add view to emby database
            emby_db.addView(folderid, foldername, viewtype, tagid)
        else:
            self.logMsg(' '.join((
                "Found viewid: %s" % folderid,
                "viewname: %s" % current_viewname,
                "viewtype: %s" % current_viewtype,
                "tagid: %s" % current_tagid)), 1)

            # Remove views that are still valid to delete rest later
            try:
                self.old_views.remove(folderid)
            except ValueError:
                # View was just created, nothing to remove
                pass

            # View was modified, update with latest info
            if current_viewname != foldername:
                self.logMsg("viewid: %s new viewname: %s"
                            % (folderid, foldername), 1)
                tagid = kodi_db.createTag(foldername)

                # Update view with new info
                emby_db.updateView(foldername, tagid, folderid)

                if mediatype != "artist":
                    if emby_db.getView_byName(current_viewname) is None:
                        # The tag could be a combined view. Ensure there's
                        # no other tags with the same name before deleting
                        # playlist.
                        utils.playlistXSP(mediatype,
                                          current_viewname,
                                          folderid,
                                          current_viewtype,
                                          True)
                        # Delete video node
                        if mediatype != "musicvideos":
                            vnodes.viewNode(
                                indexnumber=sorted_views.index(foldername),
                                tagname=current_viewname,
                                mediatype=mediatype,
                                viewtype=current_viewtype,
                                viewid=folderid,
                                delete=True)
                    # Added new playlist
                    if (foldername not in playlists and
                            mediatype in ('movie', 'show', 'musicvideos')):
                        utils.playlistXSP(mediatype,
                                          foldername,
                                          folderid,
                                          viewtype)
                        playlists.append(foldername)
                    # Add new video node
                    if foldername not in nodes and mediatype != "musicvideos":
                        vnodes.viewNode(sorted_views.index(foldername),
                                        foldername,
                                        mediatype,
                                        viewtype,
                                        folderid)
                        nodes.append(foldername)
                        totalnodes += 1

                # Update items with new tag
                items = emby_db.getItem_byView(folderid)
                for item in items:
                    # Remove the "s" from viewtype for tags
                    kodi_db.updateTag(
                        current_tagid, tagid, item[0], current_viewtype[:-1])
            else:
                # Validate the playlist exists or recreate it
                if mediatype != "artist":
                    if (foldername not in playlists and
                            mediatype in ('movie', 'show', 'musicvideos')):
                        utils.playlistXSP(mediatype,
                                          foldername,
                                          folderid,
                                          viewtype)
                        playlists.append(foldername)
                    # Create the video node if not already exists
                    if foldername not in nodes and mediatype != "musicvideos":
                        vnodes.viewNode(sorted_views.index(foldername),
                                        foldername,
                                        mediatype,
                                        viewtype,
                                        folderid)
                        nodes.append(foldername)
                        totalnodes += 1
        return totalnodes

    def maintainViews(self):
        """
        Compare the views to Plex
        """
        self.views = []
        vnodes = self.vnodes

        # Get views
        sections = downloadutils.DownloadUtils().downloadUrl(
            "{server}/library/sections")
        try:
            sections.attrib
        except AttributeError:
            self.logMsg("Error download PMS views, abort maintainViews", -1)
            return False

        # For whatever freaking reason, .copy() or dict() does NOT work?!?!?!
        self.nodes = {
            'movie': [],
            'show': [],
            'artist': []
        }
        self.playlists = {
            'movie': [],
            'show': [],
            'artist': []
        }
        self.sorted_views = []

        for view in sections:
            itemType = view.attrib['type']
            if itemType in ('movie', 'show'):  # and NOT artist for now
                self.sorted_views.append(view.attrib['title'])
        self.logMsg('Sorted views: %s' % self.sorted_views, 1)

        # total nodes for window properties
        vnodes.clearProperties()
        totalnodes = len(self.sorted_views)

        with embydb.GetEmbyDB() as emby_db:
            # Backup old views to delete them later, if needed (at the end
            # of this method, only unused views will be left in oldviews)
            self.old_views = emby_db.getViews()
            with kodidb.GetKodiDB('video') as kodi_db:
                for folderItem in sections:
                    totalnodes = self.processView(folderItem,
                                                  kodi_db,
                                                  emby_db,
                                                  totalnodes)
                # Add video nodes listings
                # Plex: there seem to be no favorites/favorites tag
                # vnodes.singleNode(totalnodes,
                #                   "Favorite movies",
                #                   "movies",
                #                   "favourites")
                # totalnodes += 1
                # vnodes.singleNode(totalnodes,
                #                   "Favorite tvshows",
                #                   "tvshows",
                #                   "favourites")
                # totalnodes += 1
                # vnodes.singleNode(totalnodes,
                #                   "channels",
                #                   "movies",
                #                   "channels")
                # totalnodes += 1
            with kodidb.GetKodiDB('music') as kodi_db:
                pass

        # Save total
        utils.window('Emby.nodes.total', str(totalnodes))

        # Reopen DB connection to ensure that changes were commited before
        with embydb.GetEmbyDB() as emby_db:
            # update views for all:
            self.views = emby_db.getAllViewInfo()
            self.logMsg("Removing views: %s" % self.old_views, 1)
            for view in self.old_views:
                emby_db.removeView(view)

        self.logMsg("Finished processing views. Views saved: %s"
                    % self.views, 1)
        return True

    def GetUpdatelist(self, xml, itemType, method, viewName, viewId):
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
        if self.compare:
            # Only process the delta - new or changed items
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
                # Only update if movie is not in Kodi or checksum is
                # different
                if kodi_checksum != plex_checksum:
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

    def GetAndProcessXMLs(self, itemType, showProgress=True):
        """
        Downloads all XMLs for itemType (e.g. Movies, TV-Shows). Processes them
        by then calling itemtypes.<itemType>()

        Input:
            itemType:               'Movies', 'TVShows', ...
            self.updatelist
            showProgress            If False, NEVER shows sync progress
        """
        # Some logging, just in case.
        self.logMsg("self.updatelist: %s" % self.updatelist, 2)
        itemNumber = len(self.updatelist)
        if itemNumber == 0:
            return

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
                                         getMetadataLock,
                                         processMetadataLock)
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
        if showProgress:
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
            # Threads might already have quit by themselves (e.g. Kodi exit)
            try:
                thread.stopThread()
            except:
                pass
        self.logMsg("Stop sent to all threads", 1)
        # Wait till threads are indeed dead
        for thread in threads:
            try:
                thread.join(1.0)
            except:
                pass
        self.logMsg("Sync threads finished", 1)
        self.updatelist = []

    @utils.LogTime
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
            all_plexmovies = PF.GetPlexSectionResults(
                viewId, args=None, containerSize=self.limitindex)
            if all_plexmovies is None:
                self.logMsg("Couldnt get section items, aborting for view.", 1)
                continue
            elif all_plexmovies == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(all_plexmovies,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
        self.GetAndProcessXMLs(itemType)
        self.logMsg("Processed view", 1)
        # Update viewstate for EVERY item
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
        xml = PF.GetAllPlexLeaves(viewId,
                                  lastViewedAt=lastViewedAt,
                                  updatedAt=updatedAt,
                                  containerSize=self.limitindex)
        # Return if there are no items in PMS reply - it's faster
        try:
            xml[0].attrib
        except (TypeError, AttributeError, IndexError):
            return

        if itemType in ('Movies', 'TVShows'):
            self.updateKodiVideoLib = True
        elif itemType in ('Music'):
            self.updateKodiMusicLib = True

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

    @utils.LogTime
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
            allPlexTvShows = PF.GetPlexSectionResults(
                viewId, containerSize=self.limitindex)
            if allPlexTvShows is None:
                self.logMsg(
                    "Error downloading show view xml for view %s" % viewId, -1)
                continue
            elif allPlexTvShows == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(allPlexTvShows,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
            self.logMsg("Analyzed view %s with ID %s" % (viewName, viewId), 1)

        # COPY for later use
        allPlexTvShowsId = self.allPlexElementsId.copy()

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for tv shows", 1)

        # PROCESS TV Seasons #####
        # Cycle through tv shows
        for tvShowId in allPlexTvShowsId:
            if self.threadStopped():
                return False
            # Grab all seasons to tvshow from PMS
            seasons = PF.GetAllPlexChildren(
                tvShowId, containerSize=self.limitindex)
            if seasons is None:
                self.logMsg(
                    "Error downloading season xml for show %s" % tvShowId, -1)
                continue
            elif seasons == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(seasons,
                               itemType,
                               'add_updateSeason',
                               None,
                               tvShowId)  # send showId instead of viewid
            self.logMsg("Analyzed all seasons of TV show with Plex Id %s"
                        % tvShowId, 1)

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for seasons", 1)

        # PROCESS TV Episodes #####
        # Cycle through tv shows
        for view in views:
            if self.threadStopped():
                return False
            # Grab all episodes to tvshow from PMS
            episodes = PF.GetAllPlexLeaves(
                view['id'], containerSize=self.limitindex)
            if episodes is None:
                self.logMsg(
                    "Error downloading episod xml for view %s"
                    % view.get('name'), -1)
                continue
            elif episodes == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(episodes,
                               itemType,
                               'add_updateEpisode',
                               None,
                               None)
            self.logMsg("Analyzed all episodes of TV show with Plex Id %s"
                        % view['id'], 1)

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for episodes", 1)
        # Refresh season info
        # Cycle through tv shows
        with itemtypes.TVShows() as TVshow:
            for tvShowId in allPlexTvShowsId:
                XMLtvshow = PF.GetPlexMetadata(tvShowId)
                if XMLtvshow is None or XMLtvshow == 401:
                    self.logMsg('Could not download XMLtvshow', -1)
                    continue
                TVshow.refreshSeasonEntry(XMLtvshow, tvShowId)
        self.logMsg("Season info refreshed", 1)

        # Update viewstate:
        for view in views:
            if self.threadStopped():
                return False
            self.PlexUpdateWatched(view['id'], itemType)

        if self.compare:
            # Manual sync, process deletes
            with itemtypes.TVShows() as TVShow:
                for kodiTvElement in self.allKodiElementsId:
                    if kodiTvElement not in self.allPlexElementsId:
                        TVShow.remove(kodiTvElement)
        self.logMsg("%s sync is finished." % itemType, 1)
        return True

    @utils.LogTime
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

        # Process artist, then album and tracks last to minimize overhead
        for kind in ('MusicArtist', 'MusicAlbum', 'Audio'):
            if self.threadStopped():
                return False
            self.logMsg("Start processing music %s" % kind, 1)
            if self.ProcessMusic(views,
                                 kind,
                                 urlArgs[kind],
                                 methods[kind]) is False:
                return False
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
                return False
            # Get items per view
            viewId = view['id']
            viewName = view['name']
            itemsXML = PF.GetPlexSectionResults(
                viewId, args=urlArgs, containerSize=self.limitindex)
            if itemsXML is None:
                self.logMsg("Error downloading xml for view %s"
                            % viewId, -1)
                continue
            elif itemsXML == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(itemsXML,
                               'Music',
                               method,
                               viewName,
                               viewId)

        if self.compare:
            # Manual sync, process deletes
            with itemtypes.Music() as Music:
                for itemid in self.allKodiElementsId:
                    if itemid not in self.allPlexElementsId:
                        Music.remove(itemid)

    def compareDBVersion(self, current, minimum):
        # It returns True is database is up to date. False otherwise.
        self.logMsg("current: %s minimum: %s" % (current, minimum), 1)
        try:
            currMajor, currMinor, currPatch = current.split(".")
        except ValueError:
            # there WAS no current DB, e.g. deleted.
            return True
        minMajor, minMinor, minPatch = minimum.split(".")
        currMajor = int(currMajor)
        currMinor = int(currMinor)
        currPatch = int(currPatch)
        minMajor = int(minMajor)
        minMinor = int(minMinor)
        minPatch = int(minPatch)

        if currMajor > minMajor:
            return True
        elif currMajor < minMajor:
            return False

        if currMinor > minMinor:
            return True
        elif currMinor < minMinor:
            return False

        if currPatch >= minPatch:
            return True
        else:
            return False

    def processMessage(self, message):
        """
        processes json.loads() messages from websocket. Triage what we need to
        do with "process_" methods
        """
        typus = message.get('type')
        if typus == 'playing':
            self.process_playing(message['_children'])
        elif typus == 'timeline':
            self.process_timeline(message['_children'])

    def multi_delete(self, liste, deleteListe):
        """
        Deletes the list items of liste at the positions in deleteListe
        (which can be in any arbitrary order)
        """
        indexes = sorted(deleteListe, reverse=True)
        for index in indexes:
            del liste[index]
        return liste

    def processItems(self):
        """
        Periodically called to process new/updated PMS items

        PMS needs a while to download info from internet AFTER it
        showed up under 'timeline' websocket messages

        data['type']:
            1:      movie
            2:      tv show??
            3:      season??
            4:      episode
            8:      artist (band)
            9:      album
            10:     track (song)
            12:     trailer, extras?

        data['state']:
            0: 'created',
            2: 'matching',
            3: 'downloading',
            4: 'loading',
            5: 'finished',
            6: 'analyzing',
            9: 'deleted'
        """
        self.videoLibUpdate = False
        self.musicLibUpdate = False
        now = utils.getUnixTimestamp()
        deleteListe = []
        for i, item in enumerate(self.itemsToProcess):
            if now - item['timestamp'] < self.saftyMargin:
                # We haven't waited long enough for the PMS to finish
                # processing the item. Do it later
                continue
            if item['state'] == 5:
                if self.process_newitems(item) is True:
                    deleteListe.append(i)
            elif item['state'] == 9:
                if self.process_deleteditems(item) is True:
                    deleteListe.append(i)

        # Get rid of the items we just processed
        if len(deleteListe) > 0:
            self.itemsToProcess = self.multi_delete(
                self.itemsToProcess, deleteListe)
        # Let Kodi know of the change
        if self.videoLibUpdate is True:
            self.logMsg("Doing Kodi Video Lib update", 1)
            xbmc.executebuiltin('UpdateLibrary(video)')
        if self.musicLibUpdate is True:
            self.logMsg("Doing Kodi Music Lib update", 1)
            xbmc.executebuiltin('UpdateLibrary(music)')

    def process_newitems(self, item):
        ratingKey = item['ratingKey']
        xml = PF.GetPlexMetadata(ratingKey)
        if xml in (None, 401):
            self.logMsg('Could not download metadata for %s, skipping'
                        % ratingKey, -1)
            return False
        self.logMsg("Processing new/updated PMS item: %s" % ratingKey, 1)
        viewtag = xml.attrib.get('librarySectionTitle')
        viewid = xml.attrib.get('librarySectionID')
        mediatype = xml[0].attrib.get('type')
        if mediatype == 'movie':
            self.videoLibUpdate = True
            with itemtypes.Movies() as movie:
                movie.add_update(xml[0],
                                 viewtag=viewtag,
                                 viewid=viewid)
        elif mediatype == 'episode':
            self.videoLibUpdate = True
            with itemtypes.TVShows() as show:
                show.add_updateEpisode(xml[0],
                                       viewtag=viewtag,
                                       viewid=viewid)
        elif mediatype == 'track':
            self.musicLibUpdate = True
            with itemtypes.Music() as music:
                music.add_updateSong(xml[0],
                                     viewtag=viewtag,
                                     viewid=viewid)
        return True

    def process_deleteditems(self, item):
        if item.get('type') == 1:
            self.logMsg("Removing movie %s" % item.get('ratingKey'), 1)
            self.videoLibUpdate = True
            with itemtypes.Movies() as movie:
                movie.remove(item.get('ratingKey'))
        elif item.get('type') in (2, 3, 4):
            self.logMsg("Removing episode/season/tv show %s"
                        % item.get('ratingKey'), 1)
            self.videoLibUpdate = True
            with itemtypes.TVShows() as show:
                show.remove(item.get('ratingKey'))
        elif item.get('type') in (8, 9, 10):
            self.logMsg("Removing song/album/artist %s"
                        % item.get('ratingKey'), 1)
            self.musicLibUpdate = True
            with itemtypes.Music() as music:
                music.remove(item.get('ratingKey'))
        return True

    def process_timeline(self, data):
        """
        PMS is messing with the library items, e.g. new or changed. Put in our
        "processing queue" for later
        """
        for item in data:
            state = item.get('state')
            typus = item.get('type')
            if state == 9 or (state == 5 and typus in (1, 4, 10)):
                self.itemsToProcess.append({
                    'state': state,
                    'type': typus,
                    'ratingKey': item.get('itemID'),
                    'timestamp': utils.getUnixTimestamp()
                })

    def process_playing(self, data):
        """
        Someone (not necessarily the user signed in) is playing something some-
        where
        """
        items = []
        with embydb.GetEmbyDB() as emby_db:
            for item in data:
                # Drop buffering messages immediately
                state = item.get('state')
                if state == 'buffering':
                    continue
                ratingKey = item.get('ratingKey')
                sessionKey = item.get('sessionKey')
                # Do we already have a sessionKey stored?
                if sessionKey not in self.sessionKeys:
                    # No - update our list of all current sessions
                    self.sessionKeys = PF.GetPMSStatus(
                        utils.window('plex_token'))
                    self.logMsg('Updated current sessions. They are: %s'
                                % self.sessionKeys, 2)
                    if sessionKey not in self.sessionKeys:
                        self.logMsg('Session key %s still unknown! Skip item'
                                    % sessionKey, 1)
                        continue

                currSess = self.sessionKeys[sessionKey]
                # Identify the user - same one as signed on with PKC?
                # Skip update if neither session's username nor userid match
                # (Owner sometime's returns id '1', not always)
                if (utils.window('plex_token') == '' and
                        currSess['userId'] == '1'):
                    # PKC not signed in to plex.tv. Plus owner of PMS is
                    # playing (the '1').
                    # Hence must be us (since several users require plex.tv
                    # token for PKC)
                    pass
                elif not (currSess['userId'] == utils.window('currUserId')
                          or
                          currSess['username'] == utils.window('plex_username')):
                    self.logMsg('Our username %s, userid %s did not match the '
                                'session username %s with userid %s'
                                % (utils.window('plex_username'),
                                   utils.window('currUserId'),
                                   currSess['username'],
                                   currSess['userId']), 2)
                    continue

                kodiInfo = emby_db.getItem_byId(ratingKey)
                if kodiInfo is None:
                    # Item not (yet) in Kodi library
                    continue

                # Get an up-to-date XML from the PMS
                # because PMS will NOT directly tell us:
                #   duration of item
                #   viewCount
                if currSess.get('duration') is None:
                    xml = PF.GetPlexMetadata(ratingKey)
                    if xml in (None, 401):
                        self.logMsg('Could not get up-to-date xml for item %s'
                                    % ratingKey, -1)
                        continue
                    API = PlexAPI.API(xml[0])
                    userdata = API.getUserData()
                    currSess['duration'] = userdata['Runtime']
                    currSess['viewCount'] = userdata['PlayCount']
                # Append to list that we need to process
                items.append({
                    'ratingKey': ratingKey,
                    'kodi_id': kodiInfo[0],
                    'file_id': kodiInfo[1],
                    'kodi_type': kodiInfo[4],
                    'viewOffset': PF.ConvertPlexToKodiTime(
                        item.get('viewOffset')),
                    'state': state,
                    'duration': currSess['duration'],
                    'viewCount': currSess['viewCount'],
                    'lastViewedAt': utils.DateToKodi(utils.getUnixTimestamp())
                })
                self.logMsg('Update playstate for user %s with id %s: %s'
                            % (utils.window('plex_username'),
                               utils.window('currUserId'),
                               items[-1]), 2)
        # Now tell Kodi where we are
        for item in items:
            itemFkt = getattr(itemtypes,
                              PF.GetItemClassFromType(item['kodi_type']))
            with itemFkt() as Fkt:
                Fkt.updatePlaystate(item)

    def run(self):
        try:
            self.run_internal()
        except Exception as e:
            utils.window('emby_dbScan', clear=True)
            self.logMsg('LibrarySync thread crashed', -1)
            self.logMsg('Error message: %s' % e, -1)
            import traceback
            self.logMsg("Traceback:\n%s" % traceback.format_exc(), -1)
            # Library sync thread has crashed
            self.dialog.ok(self.addonName,
                           self.__language__(39400))
            raise

    def run_internal(self):
        # Re-assign handles to have faster calls
        window = utils.window
        settings = utils.settings
        log = self.logMsg
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        installSyncDone = self.installSyncDone
        enableBackgroundSync = self.enableBackgroundSync
        fullSync = self.fullSync
        processMessage = self.processMessage
        processItems = self.processItems
        string = self.__language__
        fullSyncInterval = self.fullSyncInterval
        lastSync = 0
        lastTimeSync = 0
        lastProcessing = 0
        oneDay = 60*60*24

        xbmcplayer = xbmc.Player()

        queue = self.queue

        startupComplete = False
        self.views = []
        errorcount = 0

        log("---===### Starting LibrarySync ###===---", 0)

        if self.enableMusic:
            # utils.musiclibXML()
            utils.advancedSettingsXML()

        while not threadStopped():

            # In the event the server goes offline
            while threadSuspended():
                # Set in service.py
                if threadStopped():
                    # Abort was requested while waiting. We should exit
                    log("###===--- LibrarySync Stopped ---===###", 0)
                    return
                xbmc.sleep(1000)

            if (window('emby_dbCheck') != "true" and installSyncDone):
                # Verify the validity of the database
                currentVersion = settings('dbCreatedWithVersion')
                minVersion = window('emby_minDBVersion')

                if not self.compareDBVersion(currentVersion, minVersion):
                    log("Db version out of date: %s minimum version required: "
                        "%s" % (currentVersion, minVersion), 0)
                    # DB out of date. Proceed to recreate?
                    resp = self.dialog.yesno(heading=self.addonName,
                                             line1=string(39401))
                    if not resp:
                        log("Db version out of date! USER IGNORED!", 0)
                        # PKC may not work correctly until reset
                        self.dialog.ok(heading=self.addonName,
                                       line1=(self.addonName + string(39402)))
                    else:
                        utils.reset()
                    break

                window('emby_dbCheck', value="true")

            if not startupComplete:
                # Also runs when first installed
                # Verify the video database can be found
                videoDb = utils.getKodiVideoDBPath()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    log("The current Kodi version is incompatible "
                        "to know which Kodi versions are supported.", -1)
                    log('Current Kodi version: %s' % xbmc.getInfoLabel(
                        'System.BuildVersion').decode('utf-8'))
                    # "Current Kodi version is unsupported, cancel lib sync"
                    self.dialog.ok(heading=self.addonName,
                                   line1=string(39403))
                    break

                # Run start up sync
                window('emby_dbScan', value="true")
                log("Db version: %s" % settings('dbCreatedWithVersion'), 0)
                lastTimeSync = utils.getUnixTimestamp()
                self.syncPMStime()
                log("Initial start-up full sync starting", 0)
                lastSync = utils.getUnixTimestamp()
                librarySync = fullSync()
                # Initialize time offset Kodi - PMS
                window('emby_dbScan', clear=True)
                if librarySync:
                    log("Initial start-up full sync successful", 0)
                    startupComplete = True
                    settings('SyncInstallRunDone', value="true")
                    settings("dbCreatedWithVersion",
                             self.clientInfo.getVersion())
                    installSyncDone = True
                else:
                    log("Initial start-up full sync unsuccessful", -1)
                    errorcount += 1
                    if errorcount > 2:
                        log("Startup full sync failed. Stopping sync", -1)
                        # "Startup syncing process failed repeatedly"
                        # "Please restart"
                        self.dialog.ok(heading=self.addonName,
                                       line1=string(39404))
                        break

            # Currently no db scan, so we can start a new scan
            elif window('emby_dbScan') != "true":
                # Full scan was requested from somewhere else, e.g. userclient
                if window('plex_runLibScan') in ("full", "repair"):
                    log('Full library scan requested, starting', 0)
                    window('emby_dbScan', value="true")
                    if window('plex_runLibScan') == "full":
                        fullSync()
                    elif window('plex_runLibScan') == "repair":
                        fullSync(repair=True)
                    window('plex_runLibScan', clear=True)
                    window('emby_dbScan', clear=True)
                    # Full library sync finished
                    self.showKodiNote(string(39407), forced=True)
                # Reset views was requested from somewhere else
                elif window('plex_runLibScan') == "views":
                    log('Refresh playlist and nodes requested, starting', 0)
                    window('emby_dbScan', value="true")
                    window('plex_runLibScan', clear=True)

                    # First remove playlists
                    utils.deletePlaylists()
                    # Remove video nodes
                    utils.deleteNodes()
                    # Kick off refresh
                    if self.maintainViews() is True:
                        # Ran successfully
                        log("Refresh playlists/nodes completed", 0)
                        # "Plex playlists/nodes refreshed"
                        self.showKodiNote(string(39405), forced=True)
                    else:
                        # Failed
                        log("Refresh playlists/nodes failed", -1)
                        # "Plex playlists/nodes refresh failed"
                        self.showKodiNote(string(39406),
                                          forced=True,
                                          icon="error")
                    window('emby_dbScan', clear=True)
                else:
                    now = utils.getUnixTimestamp()
                    if (now - lastSync > fullSyncInterval and
                            not xbmcplayer.isPlaying()):
                        lastSync = now
                        log('Doing scheduled full library scan', 1)
                        window('emby_dbScan', value="true")
                        if fullSync() is False and not threadStopped():
                            log('Could not finish scheduled full sync', -1)
                            self.showKodiNote(string(39410),
                                              forced=True,
                                              icon='error')
                        window('emby_dbScan', clear=True)
                        # Full library sync finished
                        self.showKodiNote(string(39407), forced=False)
                    elif now - lastTimeSync > oneDay:
                        lastTimeSync = now
                        log('Starting daily time sync', 0)
                        window('emby_dbScan', value="true")
                        self.syncPMStime()
                        window('emby_dbScan', clear=True)
                    elif enableBackgroundSync:
                        # Check back whether we should process something
                        # Only do this once every 10 seconds
                        if now - lastProcessing > 10:
                            lastProcessing = now
                            window('emby_dbScan', value="true")
                            processItems()
                            window('emby_dbScan', clear=True)
                        # See if there is a PMS message we need to handle
                        try:
                            message = queue.get(block=False)
                        except Queue.Empty:
                            xbmc.sleep(100)
                            continue
                        # Got a message from PMS; process it
                        else:
                            window('emby_dbScan', value="true")
                            processMessage(message)
                            queue.task_done()
                            window('emby_dbScan', clear=True)
                            # NO sleep!
                            continue
                    else:
                        # Still sleep if backgroundsync disabled
                        xbmc.sleep(100)

            xbmc.sleep(100)

        # doUtils could still have a session open due to interrupted sync
        try:
            downloadutils.DownloadUtils().stopSession()
        except:
            pass
        log("###===--- LibrarySync Stopped ---===###", 0)

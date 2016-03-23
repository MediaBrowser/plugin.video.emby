# -*- coding: utf-8 -*-

###############################################################################

from threading import Thread, Lock
import Queue
import xml.etree.ElementTree as etree

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

import PlexFunctions

###############################################################################


@utils.logging
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
    def __init__(self, queue, out_queue, lock, processlock):
        self.queue = queue
        self.out_queue = out_queue
        self.lock = lock
        self.processlock = processlock
        Thread.__init__(self)

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
            plexXML = PlexFunctions.GetPlexMetadata(updateItem['itemId'])
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

        self.__language__ = xbmcaddon.Addon().getLocalizedString

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
        self.enableBackgroundSync = True if utils.settings(
            'enableBackgroundSync') == "true" else False
        self.limitindex = int(utils.settings('limitindex'))

        if utils.settings('emby_pathverified') == 'true':
            utils.window('emby_pathverified', value='true')

        # Time offset between Kodi and PMS in seconds (=Koditime - PMStime)
        self.timeoffset = 0
        # Time in seconds to look into the past when looking for PMS changes
        # (safety margin - the larger, the more items we need to process)
        self.syncPast = 30

        Thread.__init__(self)

    def showKodiNote(self, message, forced=False, icon="plex"):
        """
        Shows a Kodi popup, if user selected to do so. Pass message in unicode
        or string

        icon:   "plex": shows Plex icon
                "error": shows Kodi error icon
        """
        if not (self.showDbSync or forced):
            return
        if icon == "plex":
            xbmcgui.Dialog().notification(
                heading=self.addonName,
                message=message,
                icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                time=5000,
                sound=False)
        elif icon == "error":
            xbmcgui.Dialog().notification(
                heading=self.addonName,
                message=message,
                icon=xbmcgui.NOTIFICATION_ERROR,
                time=7000,
                sound=True)

    def syncPMStime(self):
        """
        PMS does not provide a means to get a server timestamp. This is a work-
        around.
        """
        self.logMsg('Synching time with PMS server', 0)
        # Find a PMS item where we can toggle the view state to enforce a
        # change in lastViewedAt
        with kodidb.GetKodiDB('video') as kodi_db:
            unplayedIds = kodi_db.getUnplayedItems()
            resumeIds = kodi_db.getResumes()
        self.logMsg('resumeIds: %s' % resumeIds, 1)

        plexId = False
        for unplayedId in unplayedIds:
            if unplayedId not in resumeIds:
                # Found an item we can work with!
                kodiId = unplayedId
                self.logMsg('Found kodiId: %s' % kodiId, 1)
                # Get Plex ID using the Kodi ID
                with embydb.GetEmbyDB() as emby_db:
                    plexId = emby_db.getItem_byFileId(kodiId, 'movie')
                    if plexId:
                        self.logMsg('Found movie plexId: %s' % plexId, 1)
                        break
                    else:
                        plexId = emby_db.getItem_byFileId(kodiId, 'episode')
                        if plexId:
                            self.logMsg('Found episode plexId: %s' % plexId, 1)
                            break

        # Try getting a music item if we did not find a video item
        if not plexId:
            self.logMsg("Could not find a video item to sync time with", 0)
            with kodidb.GetKodiDB('music') as kodi_db:
                unplayedIds = kodi_db.getUnplayedMusicItems()
                # We don't care about resuming songs in the middle
            for unplayedId in unplayedIds:
                # Found an item we can work with!
                kodiId = unplayedId
                self.logMsg('Found kodiId: %s' % kodiId, 1)
                # Get Plex ID using the Kodi ID
                with embydb.GetEmbyDB() as emby_db:
                    plexId = emby_db.getMusicItem_byFileId(kodiId, 'song')
                if plexId:
                    self.logMsg('Found plexId: %s' % plexId, 1)
                    break
            else:
                self.logMsg("Could not find an item to sync time with", -1)
                self.logMsg("Aborting PMS-Kodi time sync", -1)
                return

        # Get the Plex item's metadata
        xml = PlexFunctions.GetPlexMetadata(plexId)
        if xml is None:
            self.logMsg("Could not download metadata, aborting time sync", -1)
            return
        libraryId = xml[0].attrib['librarySectionID']
        # Get a PMS timestamp to start our question with
        timestamp = xml[0].attrib.get('lastViewedAt')
        if not timestamp:
            timestamp = xml[0].attrib.get('updatedAt')
            self.logMsg('Using items updatedAt=%s' % timestamp, 1)
            if not timestamp:
                timestamp = xml[0].attrib.get('addedAt')
                self.logMsg('Using items addedAt=%s' % timestamp, 1)
        # Set the timer
        koditime = utils.getUnixTimestamp()
        # Toggle watched state
        PlexFunctions.scrobble(plexId, 'watched')
        # Let the PMS process this first!
        xbmc.sleep(2000)
        # Get all PMS items to find the item we changed
        items = PlexFunctions.GetAllPlexLeaves(libraryId,
                                               lastViewedAt=timestamp,
                                               containerSize=self.limitindex)
        # Toggle watched state back
        PlexFunctions.scrobble(plexId, 'unwatched')
        # Get server timestamp for this change
        plextime = None
        for item in items:
            if item.attrib['ratingKey'] == plexId:
                plextime = item.attrib.get('lastViewedAt')
                break
        if not plextime:
            self.logMsg("Could not set the items watched state, abort", -1)
            return

        # Calculate time offset Kodi-PMS
        self.timeoffset = int(koditime) - int(plextime)
        self.logMsg("Time offset Koditime - PMStime in seconds: %s"
                    % str(self.timeoffset), 0)

    def getPMSfromKodiTime(self, koditime):
        """
        Uses self.timeoffset to return the PMS time for a given Kodi timestamp
        (in unix time)

        Feed with integers
        """
        return koditime - self.timeoffset

    def resetProcessedItems(self):
        """
        Resets the list of PMS items that we have already processed
        """
        self.processed = {
            'movie': {},
            'show': {},
            'season': {},
            'episode': {},
            'artist': {},
            'album': {},
            'track': {}
        }

    def getFastUpdateList(self, xml, plexType, viewName, viewId):
        """
        THIS METHOD NEEDS TO BE FAST! => e.g. no API calls

        Adds items to self.updatelist as well as self.allPlexElementsId dict

        Input:
            xml:                    PMS answer for section items
            plexType:               'movie', 'show', 'episode', ...
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
        # Needs to call other methods than if we're only updating userdata
        for item in xml:
            itemId = item.attrib.get('ratingKey')
            # Skipping items 'title=All episodes' without a 'ratingKey'
            if not itemId:
                continue

            lastViewedAt = item.attrib.get('lastViewedAt')
            updatedAt = item.attrib.get('updatedAt')

            # returns the tuple (lastViewedAt, updatedAt) for the
            # specific item
            res = self.processed[plexType].get(itemId)
            if res:
                # Only look at the updatedAt flag!
                # tuple: (lastViewedAt, updatedAt)
                if res[1] == updatedAt:
                    # Nothing to update, we have already processed this
                    # item
                    continue
            title = item.attrib.get('title', 'Missing Title Name')
            # We need to process this:
            self.updatelist.append({
                'itemId': itemId,
                'itemType': PlexFunctions.GetItemClassFromType(
                    plexType),
                'method': PlexFunctions.GetMethodFromPlexType(plexType),
                'viewName': viewName,
                'viewId': viewId,
                'title': title
            })
            # And safe to self.processed:
            self.processed[plexType][itemId] = (lastViewedAt, updatedAt)
        # Quickly log
        if self.updatelist:
            self.logMsg('fastSync updatelist: %s' % self.updatelist, 1)
            self.logMsg('fastSync processed list: %s' % self.processed, 1)

    def fastSync(self):
        """
        Fast incremential lib sync

        Using /library/recentlyAdded is NOT working as changes to lib items are
        not reflected

        This will NOT remove items from Kodi db that were removed from the PMS
        (happens only during fullsync)

        Items that are processed are appended to the dict self.processed:
        {
            '<Plex itemtype>':              e.g. 'movie'
                {
                    '<ratingKey>': (        unique plex id 'ratingKey' as str
                        lastViewedAt,
                        updatedAt
                    )
                }
        }
        """
        # Get last sync time and look a bit in the past (safety margin)
        lastSync = self.lastSync - self.syncPast
        # Set new timestamp NOW because sync might take a while
        self.saveLastSync()

        # Original idea: Get all PMS items already saved in Kodi
        # Also get checksums of every Plex items already saved in Kodi
        self.allKodiElementsId = {}

        # Run through views and get latest changed elements using time diff
        self.updateKodiVideoLib = False
        self.updateKodiMusicLib = False
        for view in self.views:
            self.updatelist = []
            # Get items per view
            items = PlexFunctions.GetAllPlexLeaves(
                view['id'],
                updatedAt=self.getPMSfromKodiTime(lastSync),
                containerSize=self.limitindex)
            # Just skip if something went wrong
            if items is None:
                continue
            # Get one itemtype, because they're the same in the PMS section
            try:
                plexType = items[0].attrib['type']
            except:
                # There was no child - PMS response is empty
                continue
            # Populate self.updatelist
            self.getFastUpdateList(
                items, plexType, view['name'], view['id'])
            # Process self.updatelist
            if self.updatelist:
                if self.updatelist[0]['itemType'] in ['Movies', 'TVShows']:
                    self.updateKodiVideoLib = True
                elif self.updatelist[0]['itemType'] == 'Music':
                    self.updateKodiMusicLib = True
                # Do the work
                self.GetAndProcessXMLs(
                    PlexFunctions.GetItemClassFromType(plexType),
                    showProgress=False)

        self.updatelist = []

        # Update userdata DIRECTLY
        # We don't need to refresh the Kodi library for deltas!!
        # Start with an empty ElementTree and attach items to update
        movieupdate = False
        episodeupdate = False
        songupdate = False
        for view in self.views:
            items = PlexFunctions.GetAllPlexLeaves(
                view['id'],
                lastViewedAt=self.getPMSfromKodiTime(lastSync),
                containerSize=self.limitindex)
            if items is None:
                continue
            for item in items:
                itemId = item.attrib.get('ratingKey')
                # Skipping items 'title=All episodes' without a 'ratingKey'
                if not itemId:
                    continue
                plexType = item.attrib['type']
                lastViewedAt = item.attrib.get('lastViewedAt')
                updatedAt = item.attrib.get('updatedAt')

                # returns the tuple (lastViewedAt, updatedAt) for the
                # specific item
                res = self.processed[plexType].get(itemId)
                if res:
                    # Only look at lastViewedAt
                    if res[0] == lastViewedAt:
                        # Nothing to update, we have already processed this
                        # item
                        continue
                if plexType == 'movie':
                    movieupdate = True
                    try:
                        movieXML.append(item)
                    except:
                        movieXML = etree.Element('root')
                        movieXML.append(item)
                elif plexType == 'episode':
                    episodeupdate = True
                    try:
                        episodeXML.append(item)
                    except:
                        episodeXML = etree.Element('root')
                        episodeXML.append(item)
                elif plexType == 'track':
                    songupdate = True
                    try:
                        musicXML.append(item)
                    except:
                        musicXML = etree.Element('root')
                        musicXML.append(item)
                # And safe to self.processed:
                self.processed[plexType][itemId] = (lastViewedAt, updatedAt)

        if movieupdate:
            with itemtypes.Movies() as movies:
                movies.updateUserdata(movieXML)
        if episodeupdate:
            with itemtypes.TVShows() as tvshows:
                tvshows.updateUserdata(episodeXML)
        if songupdate:
            with itemtypes.Music() as music:
                music.updateUserdata(musicXML)

        # Let Kodi update the library now (artwork and userdata)
        if self.updateKodiVideoLib:
            self.logMsg("Doing Kodi Video Lib update", 1)
            xbmc.executebuiltin('UpdateLibrary(video)')
        if self.updateKodiMusicLib:
            self.logMsg("Doing Kodi Music Lib update", 1)
            xbmc.executebuiltin('UpdateLibrary(music)')

        # Show warning if itemtypes.py crashed at some point
        if utils.window('plex_scancrashed') == 'true':
            xbmcgui.Dialog().ok(self.addonName, self.__language__(39408))
            utils.window('plex_scancrashed', clear=True)
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

    @utils.LogTime
    def fullSync(self, manualrun=False, repair=False):
        # self.compare == False: we're syncing EVERY item
        # True: we're syncing only the delta, e.g. different checksum
        self.compare = manualrun or repair

        xbmc.executebuiltin('InhibitIdleShutdown(true)')
        screensaver = utils.getScreensaver()
        utils.setScreensaver(value="")

        # Add sources
        utils.sourcesXML()

        # Deactivate Kodi popup showing that it's (unsuccessfully) trying to
        # scan music folders
        if self.enableMusic:
            utils.musiclibXML()
            utils.advancedSettingsXML()

        # Set new timestamp NOW because sync might take a while
        self.saveLastSync()

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
        for itemtype in process:
            completed = process[itemtype]()
            if not completed:
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
        # Show warning if itemtypes.py crashed at some point
        if utils.window('plex_scancrashed') == 'true':
            xbmcgui.Dialog().ok(self.addonName, self.__language__(39408))
            utils.window('plex_scancrashed', clear=True)
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
            all_plexmovies = PlexFunctions.GetPlexSectionResults(
                viewId, args=None, containerSize=self.limitindex)
            if all_plexmovies is None:
                self.logMsg("Couldnt get section items, aborting for view.", 1)
                continue
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(all_plexmovies,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
        self.GetAndProcessXMLs(itemType)
        self.logMsg("Processed view", 1)
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
            allPlexTvShows = PlexFunctions.GetPlexSectionResults(
                viewId, containerSize=self.limitindex)
            if allPlexTvShows is None:
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

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for tv shows", 1)

        # PROCESS TV Seasons #####
        # Cycle through tv shows
        for tvShowId in allPlexTvShowsId:
            if self.threadStopped():
                return False
            # Grab all seasons to tvshow from PMS
            seasons = PlexFunctions.GetAllPlexChildren(
                tvShowId, containerSize=self.limitindex)
            if seasons is None:
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

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for seasons", 1)

        # PROCESS TV Episodes #####
        # Cycle through tv shows
        for view in views:
            if self.threadStopped():
                return False
            # Grab all episodes to tvshow from PMS
            episodes = PlexFunctions.GetAllPlexLeaves(
                view['id'], containerSize=self.limitindex)
            if episodes is None:
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
                        % view['id'], 1)

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        self.logMsg("GetAndProcessXMLs completed for episodes", 1)
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
                viewId, args=urlArgs, containerSize=self.limitindex)
            if itemsXML is None:
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
        elif (currMajor == minMajor and (currMinor > minMinor or
              (currMinor == minMinor and currPatch >= minPatch))):
            return True
        else:
            # Database out of date.
            return False

    def run(self):
        try:
            self.run_internal()
        except Exception as e:
            utils.window('emby_dbScan', clear=True)
            self.logMsg('LibrarySync thread crashed', -1)
            self.logMsg('Error message: %s' % e, -1)
            # Library sync thread has crashed
            xbmcgui.Dialog().ok(
                heading=self.addonName,
                line1=self.__language__(39400))
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
        fastSync = self.fastSync
        string = self.__language__

        dialog = xbmcgui.Dialog()

        startupComplete = False
        self.views = []
        count = 0
        errorcount = 0

        # Initialize self.processed
        self.resetProcessedItems()

        log("---===### Starting LibrarySync ###===---", 0)
        while not threadStopped():

            # In the event the server goes offline, or an item is playing
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
                uptoDate = self.compareDBVersion(currentVersion, minVersion)

                if not uptoDate:
                    log("Db version out of date: %s minimum version required: "
                        "%s" % (currentVersion, minVersion), 0)
                    # DB out of date. Proceed to recreate?
                    resp = dialog.yesno(heading=self.addonName,
                                        line1=string(39401))
                    if not resp:
                        log("Db version out of date! USER IGNORED!", 0)
                        # PKC may not work correctly until reset
                        dialog.ok(heading=self.addonName,
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
                    dialog.ok(heading=self.addonName,
                              line1=string(39403))
                    break

                # Run start up sync
                window('emby_dbScan', value="true")
                log("Db version: %s" % settings('dbCreatedWithVersion'), 0)
                log("Initial start-up full sync starting", 0)
                librarySync = fullSync(manualrun=True)
                # Initialize time offset Kodi - PMS
                self.syncPMStime()
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
                        dialog.ok(heading=self.addonName,
                                  line1=string(39404))
                        break

            # Currently no db scan, so we can start a new scan
            elif window('emby_dbScan') != "true":
                # Full scan was requested from somewhere else, e.g. userclient
                if window('plex_runLibScan') == "full":
                    log('Full library scan requested, starting', 0)
                    window('emby_dbScan', value="true")
                    window('plex_runLibScan', clear=True)
                    fullSync(manualrun=True)
                    window('emby_dbScan', clear=True)
                    count = 0
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
                    if self.maintainViews():
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
                elif enableBackgroundSync:
                    # Run full lib scan approx every 30min
                    if count >= 1800:
                        count = 0
                        # Also reset self.processed, just in case
                        self.resetProcessedItems()
                        # Recalculate time offset Kodi - PMS
                        self.syncPMStime()
                        window('emby_dbScan', value="true")
                        log('Running background full lib scan', 0)
                        fullSync(manualrun=True)
                        window('emby_dbScan', clear=True)
                        # Full library sync finished
                        self.showKodiNote(string(39407), forced=False)
                    # Run fast sync otherwise (ever second or so)
                    else:
                        window('emby_dbScan', value="true")
                        if not fastSync():
                            # Fast sync failed or server plugin is not found
                            log("Something went wrong, starting full sync", -1)
                            fullSync(manualrun=True)
                        window('emby_dbScan', clear=True)

            xbmc.sleep(1000)
            count += 1

        log("###===--- LibrarySync Stopped ---===###", 0)

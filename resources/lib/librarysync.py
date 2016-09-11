# -*- coding: utf-8 -*-

###############################################################################

import logging
from threading import Thread, Lock
import Queue
from random import shuffle

import xbmc
import xbmcgui
import xbmcvfs

from utils import window, settings, getUnixTimestamp, kodiSQL, sourcesXML,\
    ThreadMethods, ThreadMethodsAdditionalStop, LogTime, getScreensaver,\
    setScreensaver, playlistXSP, language as lang, DateToKodi, reset,\
    advancedSettingsXML, getKodiVideoDBPath, tryDecode, deletePlaylists,\
    deleteNodes, ThreadMethodsAdditionalSuspend
import clientinfo
import downloadutils
import itemtypes
import embydb_functions as embydb
import kodidb_functions as kodidb
import userclient
import videonodes

import PlexFunctions as PF
import PlexAPI

###############################################################################

log = logging.getLogger("PLEX."+__name__)

addonName = 'PlexKodiConnect'

###############################################################################


@ThreadMethodsAdditionalStop('suspend_LibraryThread')
@ThreadMethods
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
                xbmc.sleep(10)
                continue
            else:
                self.queue.task_done()
        if self.threadStopped():
            # Shutdown from outside requested; purge out_queue as well
            while not self.out_queue.empty():
                # Still try because remaining item might have been taken
                try:
                    self.out_queue.get(block=False)
                except Queue.Empty:
                    xbmc.sleep(10)
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
                xbmc.sleep(10)
                continue
            # Download Metadata
            plexXML = PF.GetPlexMetadata(updateItem['itemId'])
            if plexXML is None:
                # Did not receive a valid XML - skip that item for now
                log.warn("Could not get metadata for %s. Skipping that item "
                         "for now" % updateItem['itemId'])
                # Increase BOTH counters - since metadata won't be processed
                with lock:
                    getMetadataCount += 1
                with processlock:
                    processMetadataCount += 1
                queue.task_done()
                continue
            elif plexXML == 401:
                log.warn('HTTP 401 returned by PMS. Too much strain? '
                         'Cancelling sync for now')
                window('plex_scancrashed', value='401')
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
        log.debug('Download thread terminated')


@ThreadMethodsAdditionalStop('suspend_LibraryThread')
@ThreadMethods
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
                xbmc.sleep(10)
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
                    xbmc.sleep(10)
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
        self.terminateNow()
        log.debug('Processing thread terminated')


@ThreadMethodsAdditionalStop('suspend_LibraryThread')
@ThreadMethods
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
                      % (addonName, self.itemType, str(total)),
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
                          message="%s downloaded. %s processed: %s"
                                  % (getMetadataProgress,
                                     processMetadataProgress,
                                     viewName))
            # Sleep for x milliseconds
            xbmc.sleep(200)
        dialog.close()
        log.debug('Dialog Infobox thread terminated')


@ThreadMethodsAdditionalSuspend('suspend_LibraryThread')
@ThreadMethodsAdditionalStop('plex_shouldStop')
@ThreadMethods
class ProcessFanartThread(Thread):
    """
    Threaded download of additional fanart in the background

    Input:
        queue           Queue.Queue() object that you will need to fill with
                        dicts of the following form:
            {
              'itemId':                 the Plex id as a string
              'class':                  the itemtypes class, e.g. 'Movies'
              'mediaType':              the kodi media type, e.g. 'movie'
              'refresh': True/False     if true, will overwrite any 3rd party
                                        fanart. If False, will only get missing
            }
    """
    def __init__(self, queue):
        self.queue = queue
        Thread.__init__(self)

    def run(self):
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        queue = self.queue
        log.debug('Started Fanart thread')
        while not threadStopped():
            # In the event the server goes offline
            while threadSuspended():
                # Set in service.py
                if threadStopped():
                    # Abort was requested while waiting. We should exit
                    log.debug('Fanart thread terminated while suspended')
                    return
                xbmc.sleep(1000)
            # grabs Plex item from queue
            try:
                item = queue.get(block=False)
            except Queue.Empty:
                xbmc.sleep(50)
                continue
            if item['refresh'] is True:
                # Leave the Plex art untouched
                allartworks = None
            else:
                with embydb.GetEmbyDB() as emby_db:
                    try:
                        kodiId = emby_db.getItem_byId(item['itemId'])[0]
                    except TypeError:
                        log.error('Could not get Kodi id for plex id %s'
                                  % item['itemId'])
                        queue.task_done()
                        continue
                with kodidb.GetKodiDB('video') as kodi_db:
                    allartworks = kodi_db.existingArt(kodiId,
                                                      item['mediaType'])
                # Check if we even need to get additional art
                needsupdate = False
                for key, value in allartworks.iteritems():
                    if not value and not key == 'BoxRear':
                        needsupdate = True
                if needsupdate is False:
                    log.debug('Already got all art for Plex id %s'
                              % item['itemId'])
                    queue.task_done()
                    continue

            log.debug('Getting additional fanart for Plex id %s'
                      % item['itemId'])
            # Download Metadata
            xml = PF.GetPlexMetadata(item['itemId'])
            if xml is None:
                # Did not receive a valid XML - skip that item for now
                log.warn("Could not get metadata for %s. Skipping that item "
                         "for now" % item['itemId'])
                queue.task_done()
                continue
            elif xml == 401:
                log.warn('HTTP 401 returned by PMS. Too much strain? '
                         'Cancelling sync for now')
                # Kill remaining items in queue (for main thread to cont.)
                queue.task_done()
                continue

            # Do the work
            with getattr(itemtypes, item['class'])() as cls:
                cls.getfanart(xml[0], kodiId, item['mediaType'], allartworks)
            # signals to queue job is done
            log.debug('Done getting fanart for Plex id %s' % item['itemId'])
            queue.task_done()
        log.debug('Fanart thread terminated')


@ThreadMethodsAdditionalSuspend('suspend_LibraryThread')
@ThreadMethodsAdditionalStop('plex_shouldStop')
@ThreadMethods
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

        # Communication with websockets
        self.queue = queue
        self.itemsToProcess = []
        self.sessionKeys = []
        if settings('FanartTV') == 'true':
            self.fanartqueue = Queue.Queue()
            self.fanartthread = ProcessFanartThread(self.fanartqueue)
        # How long should we wait at least to process new/changed PMS items?
        self.saftyMargin = int(settings('saftyMargin'))

        self.fullSyncInterval = int(settings('fullSyncInterval')) * 60

        self.clientInfo = clientinfo.ClientInfo()
        self.user = userclient.UserClient()
        self.vnodes = videonodes.VideoNodes()
        self.dialog = xbmcgui.Dialog()

        self.installSyncDone = settings('SyncInstallRunDone') == 'true'
        self.showDbSync = settings('dbSyncIndicator') == 'true'
        self.enableMusic = settings('enableMusic') == "true"
        self.enableBackgroundSync = settings(
            'enableBackgroundSync') == "true"
        self.limitindex = int(settings('limitindex'))

        if settings('plex_pathverified') == 'true':
            window('plex_pathverified', value='true')

        # Just in case a time sync goes wrong
        self.timeoffset = int(settings('kodiplextimeoffset'))
        window('kodiplextimeoffset', value=str(self.timeoffset))
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
                addonName,
                message,
                "special://home/addons/plugin.video.plexkodiconnect/icon.png",
                5000,
                False)
        elif icon == "error":
            self.dialog.notification(
                addonName,
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
        log.info('Synching time with PMS server')
        # Find a PMS item where we can toggle the view state to enforce a
        # change in lastViewedAt

        # Get all Plex libraries
        sections = downloadutils.DownloadUtils().downloadUrl(
            "{server}/library/sections")
        try:
            sections.attrib
        except AttributeError:
            log.error("Error download PMS views, abort syncPMStime")
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
                libraryId = view.attrib['key']
                items = PF.GetAllPlexLeaves(libraryId,
                                            containerSize=self.limitindex)
                if items in (None, 401):
                    log.error("Could not download section %s"
                              % view.attrib['key'])
                    continue
                for item in items:
                    if item.attrib.get('viewCount') is not None:
                        # Don't want to mess with items that have playcount>0
                        continue
                    if item.attrib.get('viewOffset') is not None:
                        # Don't mess with items with a resume point
                        continue
                    plexId = item.attrib.get('ratingKey')
                    log.info('Found an item to sync with: %s' % plexId)
                    break

        if plexId is None:
            log.error("Could not find an item to sync time with")
            log.error("Aborting PMS-Kodi time sync")
            return False

        # Get the Plex item's metadata
        xml = PF.GetPlexMetadata(plexId)
        if xml in (None, 401):
            log.error("Could not download metadata, aborting time sync")
            return False

        timestamp = xml[0].attrib.get('lastViewedAt')
        if timestamp is None:
            timestamp = xml[0].attrib.get('updatedAt')
            log.debug('Using items updatedAt=%s' % timestamp)
            if timestamp is None:
                timestamp = xml[0].attrib.get('addedAt')
                log.debug('Using items addedAt=%s' % timestamp)
                if timestamp is None:
                    timestamp = 0
                    log.debug('No timestamp; using 0')

        # Set the timer
        koditime = getUnixTimestamp()
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
            log.error("Could not download metadata, aborting time sync")
            return False

        plextime = None
        for item in items:
            if item.attrib['ratingKey'] == plexId:
                plextime = item.attrib.get('lastViewedAt')
                break

        if plextime is None:
            log.error('Could not get lastViewedAt - aborting')
            return False

        # Calculate time offset Kodi-PMS
        self.timeoffset = int(koditime) - int(plextime)
        window('kodiplextimeoffset', value=str(self.timeoffset))
        settings('kodiplextimeoffset', value=str(self.timeoffset))
        log.info("Time offset Koditime - Plextime in seconds: %s"
                 % str(self.timeoffset))
        return True

    def initializeDBs(self):
        """
        Run once during startup to verify that emby db exists.
        """
        embyconn = kodiSQL('emby')
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

    @LogTime
    def fullSync(self, repair=False):
        """
        repair=True: force sync EVERY item
        """
        # self.compare == False: we're syncing EVERY item
        # True: we're syncing only the delta, e.g. different checksum
        self.compare = not repair

        xbmc.executebuiltin('InhibitIdleShutdown(true)')
        screensaver = getScreensaver()
        setScreensaver(value="")

        # Add sources
        sourcesXML()

        # Set views. Abort if unsuccessful
        if not self.maintainViews():
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            setScreensaver(value=screensaver)
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
                setScreensaver(value=screensaver)
                return False

        # Let kodi update the views in any case, since we're doing a full sync
        xbmc.executebuiltin('UpdateLibrary(video)')
        if self.enableMusic:
            xbmc.executebuiltin('UpdateLibrary(music)')

        window('plex_initialScan', clear=True)
        xbmc.executebuiltin('InhibitIdleShutdown(false)')
        setScreensaver(value=screensaver)
        if window('plex_scancrashed') == 'true':
            # Show warning if itemtypes.py crashed at some point
            self.dialog.ok(addonName, lang(39408))
            window('plex_scancrashed', clear=True)
        elif window('plex_scancrashed') == '401':
            window('plex_scancrashed', clear=True)
            if window('plex_serverStatus') not in ('401', 'Auth'):
                # Plex server had too much and returned ERROR
                self.dialog.ok(addonName, lang(39409))

        # Path hack, so Kodis Information screen works
        with kodidb.GetKodiDB('video') as kodi_db:
            try:
                kodi_db.pathHack()
                log.info('Path hack successful')
            except Exception as e:
                # Empty movies, tv shows?
                log.error('Path hack failed with error message: %s' % str(e))
        return True

    def processView(self, folderItem, kodi_db, emby_db, totalnodes):
        vnodes = self.vnodes
        folder = folderItem.attrib
        mediatype = folder['type']
        # Only process supported formats
        if mediatype not in ('movie', 'show', 'artist', 'photo'):
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
            log.info("Creating viewid: %s in Plex database." % folderid)
            tagid = kodi_db.createTag(foldername)
            # Create playlist for the video library
            if (foldername not in playlists and
                    mediatype in ('movie', 'show', 'musicvideos')):
                playlistXSP(mediatype, foldername, folderid, viewtype)
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
            log.info(' '.join((
                "Found viewid: %s" % folderid,
                "viewname: %s" % current_viewname,
                "viewtype: %s" % current_viewtype,
                "tagid: %s" % current_tagid)))

            # Remove views that are still valid to delete rest later
            try:
                self.old_views.remove(folderid)
            except ValueError:
                # View was just created, nothing to remove
                pass

            # View was modified, update with latest info
            if current_viewname != foldername:
                log.info("viewid: %s new viewname: %s"
                         % (folderid, foldername))
                tagid = kodi_db.createTag(foldername)

                # Update view with new info
                emby_db.updateView(foldername, tagid, folderid)

                if mediatype != "artist":
                    if emby_db.getView_byName(current_viewname) is None:
                        # The tag could be a combined view. Ensure there's
                        # no other tags with the same name before deleting
                        # playlist.
                        playlistXSP(mediatype,
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
                        playlistXSP(mediatype,
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
                        playlistXSP(mediatype,
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
            log.error("Error download PMS views, abort maintainViews")
            return False

        # For whatever freaking reason, .copy() or dict() does NOT work?!?!?!
        self.nodes = {
            'movie': [],
            'show': [],
            'artist': [],
            'photo': []
        }
        self.playlists = {
            'movie': [],
            'show': [],
            'artist': [],
            'photo': []
        }
        self.sorted_views = []

        for view in sections:
            itemType = view.attrib['type']
            if itemType in ('movie', 'show', 'photo'):  # NOT artist for now
                self.sorted_views.append(view.attrib['title'])
        log.debug('Sorted views: %s' % self.sorted_views)

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
        window('Plex.nodes.total', str(totalnodes))

        # Reopen DB connection to ensure that changes were commited before
        with embydb.GetEmbyDB() as emby_db:
            log.info("Removing views: %s" % self.old_views)
            for view in self.old_views:
                emby_db.removeView(view)
            # update views for all:
            self.views = emby_db.getAllViewInfo()

        log.info("Finished processing views. Views saved: %s" % self.views)
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
        log.debug("self.updatelist: %s" % self.updatelist)
        itemNumber = len(self.updatelist)
        if itemNumber == 0:
            return

        # Run through self.updatelist, get XML metadata per item
        # Initiate threads
        log.info("Starting sync threads")
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
        # Spawn GetMetadata thread for downloading
        threads = []
        thread = ThreadedGetMetadata(getMetadataQueue,
                                     processMetadataQueue,
                                     getMetadataLock,
                                     processMetadataLock)
        thread.setDaemon(True)
        thread.start()
        threads.append(thread)
        log.info("%s download threads spawned" % len(threads))
        # Spawn one more thread to process Metadata, once downloaded
        thread = ThreadedProcessMetadata(processMetadataQueue,
                                         itemType,
                                         processMetadataLock)
        thread.setDaemon(True)
        thread.start()
        threads.append(thread)
        log.info("Processing thread spawned")
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
                log.info("Kodi Infobox thread spawned")

        # Wait until finished
        getMetadataQueue.join()
        processMetadataQueue.join()
        # Kill threads
        log.info("Waiting to kill threads")
        for thread in threads:
            # Threads might already have quit by themselves (e.g. Kodi exit)
            try:
                thread.stopThread()
            except:
                pass
        log.debug("Stop sent to all threads")
        # Wait till threads are indeed dead
        for thread in threads:
            try:
                thread.join(1.0)
            except:
                pass
        log.info("Sync threads finished")
        if settings('FanartTV') == 'true':
            # Save to queue for later processing
            typus = {'Movies': 'movie', 'TVShows': 'tvshow'}[itemType]
            for item in self.updatelist:
                self.fanartqueue.put({
                    'itemId': item['itemId'],
                    'class': itemType,
                    'mediaType': typus,
                    'refresh': False
                })
        self.updatelist = []

    @LogTime
    def PlexMovies(self):
        # Initialize
        self.allPlexElementsId = {}

        itemType = 'Movies'

        views = [x for x in self.views if x['itemtype'] == 'movie']
        log.info("Processing Plex %s. Libraries: %s" % (itemType, views))

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
                log.info("Couldnt get section items, aborting for view.")
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
        log.info("Processed view")
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
        log.info("%s sync is finished." % itemType)
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
            log.error('Error updating watch status. Could not get viewId: '
                      '%s of itemType %s with lastViewedAt: %s, updatedAt: '
                      '%s' % (viewId, itemType, lastViewedAt, updatedAt))
            return

        if itemType in ('Movies', 'TVShows'):
            self.updateKodiVideoLib = True
        elif itemType in ('Music'):
            self.updateKodiMusicLib = True

        itemMth = getattr(itemtypes, itemType)
        with itemMth() as method:
            method.updateUserdata(xml)

    @LogTime
    def PlexTVShows(self):
        # Initialize
        self.allPlexElementsId = {}
        itemType = 'TVShows'

        views = [x for x in self.views if x['itemtype'] == 'show']
        log.info("Media folders for %s: %s" % (itemType, views))

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
                log.error("Error downloading show xml for view %s" % viewId)
                continue
            elif allPlexTvShows == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(allPlexTvShows,
                               itemType,
                               'add_update',
                               viewName,
                               viewId)
            log.debug("Analyzed view %s with ID %s" % (viewName, viewId))

        # COPY for later use
        allPlexTvShowsId = self.allPlexElementsId.copy()

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        log.debug("GetAndProcessXMLs completed for tv shows")

        # PROCESS TV Seasons #####
        # Cycle through tv shows
        for tvShowId in allPlexTvShowsId:
            if self.threadStopped():
                return False
            # Grab all seasons to tvshow from PMS
            seasons = PF.GetAllPlexChildren(
                tvShowId, containerSize=self.limitindex)
            if seasons is None:
                log.error("Error download season xml for show %s" % tvShowId)
                continue
            elif seasons == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(seasons,
                               itemType,
                               'add_updateSeason',
                               None,
                               tvShowId)  # send showId instead of viewid
            log.debug("Analyzed all seasons of TV show with Plex Id %s"
                      % tvShowId)

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        log.debug("GetAndProcessXMLs completed for seasons")

        # PROCESS TV Episodes #####
        # Cycle through tv shows
        for view in views:
            if self.threadStopped():
                return False
            # Grab all episodes to tvshow from PMS
            episodes = PF.GetAllPlexLeaves(
                view['id'], containerSize=self.limitindex)
            if episodes is None:
                log.error("Error downloading episod xml for view %s"
                          % view.get('name'))
                continue
            elif episodes == 401:
                return False
            # Populate self.updatelist and self.allPlexElementsId
            self.GetUpdatelist(episodes,
                               itemType,
                               'add_updateEpisode',
                               None,
                               None)
            log.debug("Analyzed all episodes of TV show with Plex Id %s"
                      % view['id'])

        # Process self.updatelist
        self.GetAndProcessXMLs(itemType)
        log.debug("GetAndProcessXMLs completed for episodes")
        # Refresh season info
        # Cycle through tv shows
        with itemtypes.TVShows() as TVshow:
            for tvShowId in allPlexTvShowsId:
                XMLtvshow = PF.GetPlexMetadata(tvShowId)
                if XMLtvshow is None or XMLtvshow == 401:
                    log.error('Could not download XMLtvshow')
                    continue
                TVshow.refreshSeasonEntry(XMLtvshow, tvShowId)
        log.debug("Season info refreshed")

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
        log.info("%s sync is finished." % itemType)
        return True

    @LogTime
    def PlexMusic(self):
        itemType = 'Music'

        views = [x for x in self.views if x['itemtype'] == 'artist']
        log.info("Media folders for %s: %s" % (itemType, views))

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
            log.debug("Start processing music %s" % kind)
            if self.ProcessMusic(views,
                                 kind,
                                 urlArgs[kind],
                                 methods[kind]) is False:
                return False
            log.debug("Processing of music %s done" % kind)
            self.GetAndProcessXMLs(itemType)
            log.debug("GetAndProcessXMLs for music %s completed" % kind)

        # Update viewstate for EVERY item
        for view in views:
            if self.threadStopped():
                return False
            self.PlexUpdateWatched(view['id'], itemType)

        # reset stuff
        self.allKodiElementsId = {}
        self.allPlexElementsId = {}
        self.updatelist = []
        log.info("%s sync is finished." % itemType)
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
                log.error("Error downloading xml for view %s" % viewId)
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
        log.info("current DB: %s minimum DB: %s" % (current, minimum))
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
        now = getUnixTimestamp()
        deleteListe = []
        for i, item in enumerate(self.itemsToProcess):
            if now - item['timestamp'] < self.saftyMargin:
                # We haven't waited long enough for the PMS to finish
                # processing the item. Do it later
                continue
            if item['state'] == 9:
                successful = self.process_deleteditems(item)
            else:
                successful = self.process_newitems(item)
            if successful is True:
                deleteListe.append(i)
            else:
                # Safety net if we can't process an item
                item['attempt'] += 1
                if item['attempt'] > 3:
                    log.warn('Repeatedly could not process item %s, abort'
                             % item)
                    deleteListe.append(i)

        # Get rid of the items we just processed
        if len(deleteListe) > 0:
            self.itemsToProcess = self.multi_delete(
                self.itemsToProcess, deleteListe)
        # Let Kodi know of the change
        if self.videoLibUpdate is True:
            log.info("Doing Kodi Video Lib update")
            xbmc.executebuiltin('UpdateLibrary(video)')
        if self.musicLibUpdate is True:
            log.info("Doing Kodi Music Lib update")
            xbmc.executebuiltin('UpdateLibrary(music)')

    def process_newitems(self, item):
        ratingKey = item['ratingKey']
        xml = PF.GetPlexMetadata(ratingKey)
        if xml in (None, 401):
            log.error('Could not download data for %s, skipping' % ratingKey)
            return False
        log.debug("Processing new/updated PMS item: %s" % ratingKey)
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
            log.debug("Removing movie %s" % item.get('ratingKey'))
            self.videoLibUpdate = True
            with itemtypes.Movies() as movie:
                movie.remove(item.get('ratingKey'))
        elif item.get('type') in (2, 3, 4):
            log.debug("Removing episode/season/tv show %s"
                      % item.get('ratingKey'))
            self.videoLibUpdate = True
            with itemtypes.TVShows() as show:
                show.remove(item.get('ratingKey'))
        elif item.get('type') in (8, 9, 10):
            log.debug("Removing song/album/artist %s" % item.get('ratingKey'))
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
            typus = item.get('type')
            state = item.get('state')
            if state == 9 or typus in (1, 4, 10):
                itemId = item.get('itemID')
                # Have we already added this element?
                for existingItem in self.itemsToProcess:
                    if existingItem['ratingKey'] == itemId:
                        break
                else:
                    # Haven't added this element to the queue yet
                    self.itemsToProcess.append({
                        'state': state,
                        'type': typus,
                        'ratingKey': itemId,
                        'timestamp': getUnixTimestamp(),
                        'attempt': 0
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
                kodiInfo = emby_db.getItem_byId(ratingKey)
                if kodiInfo is None:
                    # Item not (yet) in Kodi library
                    continue
                sessionKey = item.get('sessionKey')
                # Do we already have a sessionKey stored?
                if sessionKey not in self.sessionKeys:
                    if window('plex_serverowned') == 'false':
                        # Not our PMS, we are not authorized to get the
                        # sessions
                        # On the bright side, it must be us playing :-)
                        self.sessionKeys = {
                            sessionKey: {}
                        }
                    else:
                        # PMS is ours - get all current sessions
                        self.sessionKeys = PF.GetPMSStatus(
                            window('plex_token'))
                        log.debug('Updated current sessions. They are: %s'
                                  % self.sessionKeys)
                        if sessionKey not in self.sessionKeys:
                            log.warn('Session key %s still unknown! Skip '
                                     'item' % sessionKey)
                            continue

                currSess = self.sessionKeys[sessionKey]
                if window('plex_serverowned') != 'false':
                    # Identify the user - same one as signed on with PKC? Skip
                    # update if neither session's username nor userid match
                    # (Owner sometime's returns id '1', not always)
                    if (window('plex_token') == '' and
                            currSess['userId'] == '1'):
                        # PKC not signed in to plex.tv. Plus owner of PMS is
                        # playing (the '1').
                        # Hence must be us (since several users require plex.tv
                        # token for PKC)
                        pass
                    elif not (currSess['userId'] == window('currUserId')
                              or
                              currSess['username'] == window('plex_username')):
                        log.info('Our username %s, userid %s did not match '
                                 'the session username %s with userid %s'
                                 % (window('plex_username'),
                                    window('currUserId'),
                                    currSess['username'],
                                    currSess['userId']))
                        continue

                # Get an up-to-date XML from the PMS
                # because PMS will NOT directly tell us:
                #   duration of item
                #   viewCount
                if currSess.get('duration') is None:
                    xml = PF.GetPlexMetadata(ratingKey)
                    if xml in (None, 401):
                        log.error('Could not get up-to-date xml for item %s'
                                  % ratingKey)
                        continue
                    API = PlexAPI.API(xml[0])
                    userdata = API.getUserData()
                    currSess['duration'] = userdata['Runtime']
                    currSess['viewCount'] = userdata['PlayCount']
                # Sometimes, Plex tells us resume points in milliseconds and
                # not in seconds - thank you very much!
                if item.get('viewOffset') > currSess['duration']:
                    resume = item.get('viewOffset') / 1000
                else:
                    resume = item.get('viewOffset')
                # Append to list that we need to process
                items.append({
                    'ratingKey': ratingKey,
                    'kodi_id': kodiInfo[0],
                    'file_id': kodiInfo[1],
                    'kodi_type': kodiInfo[4],
                    'viewOffset': resume,
                    'state': state,
                    'duration': currSess['duration'],
                    'viewCount': currSess['viewCount'],
                    'lastViewedAt': DateToKodi(getUnixTimestamp())
                })
                log.debug('Update playstate for user %s with id %s: %s'
                          % (window('plex_username'),
                             window('currUserId'),
                             items[-1]))
        # Now tell Kodi where we are
        for item in items:
            itemFkt = getattr(itemtypes,
                              PF.GetItemClassFromType(item['kodi_type']))
            with itemFkt() as Fkt:
                Fkt.updatePlaystate(item)

    def fanartSync(self, refresh=False):
        """
        Checks all Plex movies and TV shows whether they still need fanart

        refresh=True        Force refresh all external fanart
        """
        items = []
        typus = {
            'Movie': 'Movies',
            'Series': 'TVShows'
        }
        with embydb.GetEmbyDB() as emby_db:
            for plextype in typus:
                items.extend(emby_db.itemsByType(plextype))
        # Shuffle the list to not always start out identically
        items = shuffle(items)
        for item in items:
            self.fanartqueue.put({
                'itemId': item['plexId'],
                'mediaType': item['kodi_type'],
                'class': typus[item['plex_type']],
                'refresh': refresh
            })

    def run(self):
        try:
            self.run_internal()
        except Exception as e:
            window('plex_dbScan', clear=True)
            log.error('LibrarySync thread crashed. Error message: %s' % e)
            import traceback
            log.error("Traceback:\n%s" % traceback.format_exc())
            # Library sync thread has crashed
            self.dialog.ok(addonName, lang(39400))
            raise

    def run_internal(self):
        # Re-assign handles to have faster calls
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        installSyncDone = self.installSyncDone
        enableBackgroundSync = self.enableBackgroundSync
        fullSync = self.fullSync
        processMessage = self.processMessage
        processItems = self.processItems
        fullSyncInterval = self.fullSyncInterval
        lastSync = 0
        lastTimeSync = 0
        lastFanartSync = 0
        lastProcessing = 0
        oneDay = 60*60*24

        xbmcplayer = xbmc.Player()

        queue = self.queue

        startupComplete = False
        self.views = []
        errorcount = 0

        log.info("---===### Starting LibrarySync ###===---")

        # Ensure that DBs exist if called for very first time
        self.initializeDBs()

        if self.enableMusic:
            advancedSettingsXML()

        if settings('FanartTV') == 'true':
            self.fanartthread.start()

        while not threadStopped():

            # In the event the server goes offline
            while threadSuspended():
                # Set in service.py
                if threadStopped():
                    # Abort was requested while waiting. We should exit
                    log.info("###===--- LibrarySync Stopped ---===###")
                    return
                xbmc.sleep(1000)

            if (window('plex_dbCheck') != "true" and installSyncDone):
                # Verify the validity of the database
                currentVersion = settings('dbCreatedWithVersion')
                minVersion = window('plex_minDBVersion')

                if not self.compareDBVersion(currentVersion, minVersion):
                    log.warn("Db version out of date: %s minimum version "
                             "required: %s" % (currentVersion, minVersion))
                    # DB out of date. Proceed to recreate?
                    resp = self.dialog.yesno(heading=addonName,
                                             line1=lang(39401))
                    if not resp:
                        log.warn("Db version out of date! USER IGNORED!")
                        # PKC may not work correctly until reset
                        self.dialog.ok(heading=addonName,
                                       line1=(addonName + lang(39402)))
                    else:
                        reset()
                    break

                window('plex_dbCheck', value="true")

            if not startupComplete:
                # Also runs when first installed
                # Verify the video database can be found
                videoDb = getKodiVideoDBPath()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    log.error("The current Kodi version is incompatible "
                              "to know which Kodi versions are supported.")
                    log.error('Current Kodi version: %s' % tryDecode(
                        xbmc.getInfoLabel('System.BuildVersion')))
                    # "Current Kodi version is unsupported, cancel lib sync"
                    self.dialog.ok(heading=addonName, line1=lang(39403))
                    break

                # Run start up sync
                window('plex_dbScan', value="true")
                log.info("Db version: %s" % settings('dbCreatedWithVersion'))
                lastTimeSync = getUnixTimestamp()
                self.syncPMStime()
                log.info("Initial start-up full sync starting")
                lastSync = getUnixTimestamp()
                librarySync = fullSync()
                # Initialize time offset Kodi - PMS
                window('plex_dbScan', clear=True)
                if librarySync:
                    log.info("Initial start-up full sync successful")
                    startupComplete = True
                    settings('SyncInstallRunDone', value="true")
                    settings("dbCreatedWithVersion",
                             self.clientInfo.getVersion())
                    installSyncDone = True
                else:
                    log.error("Initial start-up full sync unsuccessful")
                    errorcount += 1
                    if errorcount > 2:
                        log.error("Startup full sync failed. Stopping sync")
                        # "Startup syncing process failed repeatedly"
                        # "Please restart"
                        self.dialog.ok(heading=addonName,
                                       line1=lang(39404))
                        break

            # Currently no db scan, so we can start a new scan
            elif window('plex_dbScan') != "true":
                # Full scan was requested from somewhere else, e.g. userclient
                if window('plex_runLibScan') in ("full", "repair"):
                    log.info('Full library scan requested, starting')
                    window('plex_dbScan', value="true")
                    if window('plex_runLibScan') == "full":
                        fullSync()
                    elif window('plex_runLibScan') == "repair":
                        fullSync(repair=True)
                    window('plex_runLibScan', clear=True)
                    window('plex_dbScan', clear=True)
                    # Full library sync finished
                    self.showKodiNote(lang(39407), forced=False)
                # Reset views was requested from somewhere else
                elif window('plex_runLibScan') == "views":
                    log.info('Refresh playlist and nodes requested, starting')
                    window('plex_dbScan', value="true")
                    window('plex_runLibScan', clear=True)

                    # First remove playlists
                    deletePlaylists()
                    # Remove video nodes
                    deleteNodes()
                    # Kick off refresh
                    if self.maintainViews() is True:
                        # Ran successfully
                        log.info("Refresh playlists/nodes completed")
                        # "Plex playlists/nodes refreshed"
                        self.showKodiNote(lang(39405), forced=True)
                    else:
                        # Failed
                        log.error("Refresh playlists/nodes failed")
                        # "Plex playlists/nodes refresh failed"
                        self.showKodiNote(lang(39406),
                                          forced=True,
                                          icon="error")
                    window('plex_dbScan', clear=True)
                else:
                    now = getUnixTimestamp()
                    if (now - lastSync > fullSyncInterval and
                            not xbmcplayer.isPlaying()):
                        lastSync = now
                        log.info('Doing scheduled full library scan')
                        window('plex_dbScan', value="true")
                        if fullSync() is False and not threadStopped():
                            log.error('Could not finish scheduled full sync')
                            self.showKodiNote(lang(39410),
                                              forced=True,
                                              icon='error')
                        window('plex_dbScan', clear=True)
                        # Full library sync finished
                        self.showKodiNote(lang(39407), forced=False)
                    elif now - lastTimeSync > oneDay:
                        lastTimeSync = now
                        log.info('Starting daily time sync')
                        window('plex_dbScan', value="true")
                        self.syncPMStime()
                        window('plex_dbScan', clear=True)
                    elif (now - lastFanartSync > oneDay and
                            settings('FanartTV') == 'true'):
                        lastFanartSync = now
                        log.info('Starting daily fanart sync')
                        self.fanartSync()
                        log.info('Finished init of daily fanart sync')
                    elif enableBackgroundSync:
                        # Check back whether we should process something
                        # Only do this once every 10 seconds
                        if now - lastProcessing > 10:
                            lastProcessing = now
                            window('plex_dbScan', value="true")
                            processItems()
                            window('plex_dbScan', clear=True)
                        # See if there is a PMS message we need to handle
                        try:
                            message = queue.get(block=False)
                        except Queue.Empty:
                            xbmc.sleep(100)
                            continue
                        # Got a message from PMS; process it
                        else:
                            window('plex_dbScan', value="true")
                            processMessage(message)
                            queue.task_done()
                            window('plex_dbScan', clear=True)
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
        log.info("###===--- LibrarySync Stopped ---===###")

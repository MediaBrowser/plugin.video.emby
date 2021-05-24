# -*- coding: utf-8 -*-
import threading
import _strptime # Workaround for threads using datetime: _striptime is locked
from datetime import datetime, timedelta

try:
    import queue as Queue
except ImportError:
    import Queue

import xbmc
import xbmcgui

import core.movies
import core.musicvideos
import core.tvshows
import core.music
import emby.views
import helper.xmls
import helper.loghandler
from . import database
from . import sync
from . import emby_db

class Library(threading.Thread):
    def __init__(self, Player, EmbyServer):
        self.LOG = helper.loghandler.LOG('EMBY.library.Library')
        self.Player = Player
        self.EmbyServer = EmbyServer
        self.SyncSkipResume = False
        self.SyncLater = False
        self.stop_thread = False
        self.suspend = False
        self.pending_refresh = False
        self.screensaver = None
        self.progress_updates = None
        self.total_updates = 0
        self.updated_queue = Queue.Queue()
        self.userdata_queue = Queue.Queue()
        self.removed_queue = Queue.Queue()
        self.updated_output = self.NewQueues()
        self.userdata_output = self.NewQueues()
        self.removed_output = self.NewQueues()
        self.notify_output = Queue.Queue()
        self.add_lib_queue = Queue.Queue()
        self.remove_lib_queue = Queue.Queue()
        self.verify_queue = Queue.Queue()
        self.emby_threads = []
        self.download_threads = []
        self.notify_threads = []
        self.writer_threads_updated = []
        self.writer_threads_userdata = []
        self.writer_threads_removed = []
        self.ThreadingLock = threading.Lock()
        self.sync = sync.Sync(self.EmbyServer, self.Player, self.ThreadingLock)
        self.Views = emby.views.Views(self.EmbyServer)
        self.progress_percent = 0
        self.Xmls = helper.xmls.Xmls(self.EmbyServer.Utils)
        threading.Thread.__init__(self)
        self.start()

    def NewQueues(self):
        return {
            'Movie': Queue.Queue(),
            'BoxSet': Queue.Queue(),
            'MusicVideo': Queue.Queue(),
            'Series': Queue.Queue(),
            'Season': Queue.Queue(),
            'Episode': Queue.Queue(),
            'MusicAlbum': Queue.Queue(),
            'MusicArtist': Queue.Queue(),
            'AlbumArtist': Queue.Queue(),
            'Audio': Queue.Queue()
        }

    def get_naming(self, item):
        if item['Type'] == 'Episode':
            if 'SeriesName' in item:
                return "%s: %s" % (item['SeriesName'], item['Name'])
        elif item['Type'] == 'Season':
            if 'SeriesName' in item:
                return "%s: %s" % (item['SeriesName'], item['Name'])
        elif item['Type'] == 'MusicAlbum':
            if 'AlbumArtist' in item:
                return "%s: %s" % (item['AlbumArtist'], item['Name'])
        elif item['Type'] == 'Audio':
            if item.get('Artists'):
                return "%s: %s" % (item['Artists'][0], item['Name'])

        return item['Name']

    def set_progress_dialog(self):
        queue_size = self.worker_queue_size()

        if self.total_updates:
            self.progress_percent = int((float(self.total_updates - queue_size) / float(self.total_updates)) * 100)
        else:
            self.progress_percent = 0

        self.LOG.debug("--[ pdialog (%s/%s) ]" % (queue_size, self.total_updates))

        if self.total_updates < int(self.EmbyServer.Utils.Settings.syncProgress):
            return

        if self.progress_updates is None:
            self.LOG.info("-->[ pdialog ]")
            self.progress_updates = xbmcgui.DialogProgressBG()
            self.progress_updates.create(self.EmbyServer.Utils.Translate('addon_name'), self.EmbyServer.Utils.Translate(33178))

    def update_progress_dialog(self, item):
        if self.progress_updates:
            message = self.get_naming(item)
            self.progress_updates.update(self.progress_percent, message="%s: %s" % (self.EmbyServer.Utils.Translate(33178), message))

    def run(self):
        self.LOG.warning("--->[ library ]")
        self.Views.update_views()
        self.sync.update_library = False

        if self.EmbyServer.Utils.SyncData['Libraries']:
            if not self.sync.mapping(False):
                self.SyncSkipResume = True

            self.sync.FullSync()
        elif not self.EmbyServer.Utils.Settings.SyncInstallRunDone:
            self.Xmls.sources()

            if not self.sync.mapping(False):
                if self.SyncLater:
                    self.EmbyServer.Utils.dialog("ok", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33129))
                    self.EmbyServer.Utils.Settings.set_settings_bool('SyncInstallRunDone', True)
                    self.EmbyServer.Utils.SyncData['Libraries'] = []
                    self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData)

            xbmc.executebuiltin('ReloadSkin()')

        self.Views.update_nodes()
        self.get_fast_sync()

        while not self.stop_thread:
            if xbmc.Monitor().waitForAbort(0.5):
                break

            if self.sync.running:
                continue

            self.service()

            if self.Player.SyncPause:
                continue

        self.Player.SyncPause = False
        self.LOG.warning("---<[ library ]")

    def service(self):
        for thread in self.download_threads:
            if thread.Done():
                self.removed(thread.removed)
                self.download_threads.remove(thread)

        for threads in (self.emby_threads, self.writer_threads_updated, self.writer_threads_userdata, self.writer_threads_removed):
            for thread in threads:
                if thread.Done():
                    threads.remove(thread)

        PlayingVideo = self.Player.isPlayingVideo()

        if not PlayingVideo or self.EmbyServer.Utils.Settings.syncDuringPlay or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
            if not PlayingVideo or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
                if not self.SyncSkipResume:
                    if self.EmbyServer.Utils.SyncData['Libraries']:
                        self.sync.update_library = False

                        if not self.sync.mapping(True):
                            self.SyncSkipResume = True

                        self.sync.FullSync()
                        self.Views.update_nodes()

                        if self.Player.SyncPause:
                            return

                self.worker_remove_lib()
                self.worker_add_lib()

            self.worker_verify()
            self.worker_downloads()
            self.worker_sort()
            self.worker_updates()
            self.worker_userdata()
            self.worker_remove()
            self.worker_notify()

        if self.pending_refresh:
            self.set_progress_dialog()

            if not self.EmbyServer.Utils.Settings.dbSyncScreensaver and self.screensaver is None:
                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                self.screensaver = self.EmbyServer.Utils.Screensaver
                self.EmbyServer.Utils.set_screensaver(value="")

        if self.pending_refresh and not self.download_threads and not self.writer_threads_updated and not self.writer_threads_userdata and not self.writer_threads_removed:
            self.pending_refresh = False
            self.EmbyServer.Utils.save_last_sync()
            self.total_updates = 0

            if self.progress_updates:
                self.LOG.info("--<[ pdialog ]")
                self.progress_updates.close()
                self.progress_updates = None

            if not self.EmbyServer.Utils.Settings.dbSyncScreensaver and self.screensaver is not None:
                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                self.EmbyServer.Utils.set_screensaver(value=self.screensaver)
                self.screensaver = None

            if not xbmc.getCondVisibility('Window.IsMedia'):
                xbmc.executebuiltin('UpdateLibrary(video)')

    #Get how many items are queued up for worker threads
    def worker_queue_size(self):
        total = 0
        total += self._worker_update_size()
        total += self._worker_userdata_size()
        total += self._worker_removed_size()
        return total

    def _worker_update_size(self):
        total = 0

        for queues in self.updated_output:
            total += self.updated_output[queues].qsize()

        return total

    def _worker_userdata_size(self):
        total = 0

        for queues in self.userdata_output:
            total += self.userdata_output[queues].qsize()

        return total

    def _worker_removed_size(self):
        total = 0
        total += self.removed_queue.qsize()

        for queues in self.removed_output:
            total += self.removed_output[queues].qsize()

        return total

    def worker_verify(self):
        if self.verify_queue.qsize():
            ready = []
            not_ready = []

            while not self.verify_queue.empty():
                time_set, item_id = self.verify_queue.get()

                if time_set <= datetime.today():
                    ready.append(item_id)
                elif item_id not in list(self.removed_queue.queue):
                    not_ready.append((time_set, item_id,))

            self.updated(ready)
            list(map(self.verify_queue.put, not_ready)) # re-add items that are not ready yet

    #Get items from emby and place them in the appropriate queues
    def worker_downloads(self):
        for queue in ((self.updated_queue, self.updated_output), (self.userdata_queue, self.userdata_output)):
            if queue[0].qsize() and len(self.download_threads) < int(self.EmbyServer.Utils.Settings.limitThreads):
                new_thread = GetItemWorker(self, queue[0], queue[1])
                self.LOG.info("-->[ q:download/%s ]" % id(new_thread))
                self.download_threads.append(new_thread)

    #Get items based on the local emby database and place item in appropriate queues
    def worker_sort(self):
        if self.removed_queue.qsize() and len(self.emby_threads) < 2:
            new_thread = SortWorker(self)
            self.LOG.info("-->[ q:sort/%s ]" % id(new_thread))
            self.emby_threads.append(new_thread)

    #Update items in the Kodi database
    def worker_updates(self):
        if self._worker_removed_size() or len(self.writer_threads_updated):
            self.LOG.info("[ DELAY UPDATES ]")
            return

        for queues in self.updated_output:
            queue = self.updated_output[queues]

            if queue.qsize(): # and not len(self.writer_threads_updated):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UpdatedWorker(queue, self, "music")
                else:
                    new_thread = UpdatedWorker(queue, self, "video")

                self.LOG.info("-->[ q:updated/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_updated.append(new_thread)
                self.pending_refresh = True

    #Update userdata in the Kodi database
    def worker_userdata(self):
        if self._worker_removed_size() or len(self.writer_threads_userdata):
            self.LOG.info("[ DELAY UPDATES ]")
            return

        for queues in self.userdata_output:
            queue = self.userdata_output[queues]

            if queue.qsize(): # and not len(self.writer_threads_userdata):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UserDataWorker(queue, self, "music")
                else:
                    new_thread = UserDataWorker(queue, self, "video")

                self.LOG.info("-->[ q:userdata/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_userdata.append(new_thread)
                self.pending_refresh = True

    #Remove items from the Kodi database
    def worker_remove(self):
        if len(self.writer_threads_removed):
            self.LOG.info("[ DELAY UPDATES ]")
            return

        for queues in self.removed_output:
            queue = self.removed_output[queues]

            if queue.qsize(): # and not len(self.writer_threads_removed):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = RemovedWorker(queue, self, "music")
                else:
                    new_thread = RemovedWorker(queue, self, "video")

                self.LOG.info("-->[ q:removed/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_removed.append(new_thread)
                self.pending_refresh = True

    #Notify the user of new additions
    def worker_notify(self):
        if self.notify_output.qsize() and not len(self.notify_threads):
            new_thread = NotifyWorker(self)
            self.LOG.info("-->[ q:notify/%s ]" % id(new_thread))
            self.notify_threads.append(new_thread)

    def worker_remove_lib(self):
        if self.remove_lib_queue.qsize():
            while not self.remove_lib_queue.empty():
                library_id = self.remove_lib_queue.get()
                self.sync.remove_library(library_id)
                self.Views.remove_library(library_id)

                if self.Player.SyncPause:
                    return

            xbmc.executebuiltin("Container.Refresh")

    def worker_add_lib(self):
        if self.add_lib_queue.qsize():
            while not self.add_lib_queue.empty():
                library_id, update = self.add_lib_queue.get()
                self.sync.update_library = update

                if library_id not in [x.replace('Mixed:', "") for x in self.EmbyServer.Utils.SyncData['Libraries']]:
                    with database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
                        library = emby_db.EmbyDatabase(embydb.cursor).get_view(library_id)

                    if library:
                        self.EmbyServer.Utils.SyncData['Libraries'].append("Mixed:%s" % library_id if library[2] == 'mixed' else library_id)

                        if library[2] in ('mixed', 'movies'):
                            self.EmbyServer.Utils.SyncData['Libraries'].append('Boxsets:%s' % library_id)
                    else:
                        self.EmbyServer.Utils.SyncData['Libraries'].append(library_id)

                self.sync.FullSync()
                self.Views.update_nodes()

                if self.Player.SyncPause:
                    return

                self.Views.update_nodes()

            xbmc.executebuiltin("Container.Refresh")

    def get_fast_sync(self):
        enable_fast_sync = False

        if self.EmbyServer.Utils.Settings.SyncInstallRunDone:
            if self.EmbyServer.Utils.Settings.kodiCompanion:
                for plugin in self.EmbyServer.API.get_plugins():
                    if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                        enable_fast_sync = True
                        break

                self.fast_sync(enable_fast_sync)
                self.LOG.info("--<[ retrieve changes ]")

    #Movie and userdata not provided by server yet
    def fast_sync(self, plugin):
        last_sync = self.EmbyServer.Utils.Settings.LastIncrementalSync
        self.LOG.info("--[ retrieve changes ] %s" % last_sync)
        LibraryViews = {}

        with database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)
            result = db.get_views()

            for Data in result:
                LibID, _, LibContent, _ = Data
                LibraryViews[LibID] = LibContent

            for library in self.EmbyServer.Utils.SyncData['Whitelist']:
                library = library.replace('Mixed:', "")

                if LibraryViews[library] == "musicvideos":
                    result = self.EmbyServer.API.get_itemsSync(library, "MusicVideo", False, {'MinDateLastSaved': last_sync})
                elif LibraryViews[library] == "movies":
                    result = self.EmbyServer.API.get_itemsSync(library, "BoxSet,Movie", False, {'MinDateLastSaved': last_sync})
                elif LibraryViews[library] == "tvshows":
                    result = self.EmbyServer.API.get_itemsSync(library, "Series,Season,Episode", False, {'MinDateLastSaved': last_sync})
                elif LibraryViews[library] == "music":
                    result = self.EmbyServer.API.get_itemsSync(library, "MusicArtist,MusicAlbum,Audio", False, {'MinDateLastSaved': last_sync})
                elif LibraryViews[library] == "mixed":
                    result = self.EmbyServer.API.get_itemsSync(library.replace('Mixed:', ""), "Series,Season,Episode,BoxSet,Movie,MusicVideo,MusicArtist,MusicAlbum,Audio", False, {'MinDateLastSaved': last_sync})
                else:
                    result = False

                if result:
                    for data in result:
                        for item in data['Items']:
                            if item['Type'] in self.updated_output:
                                item['Library'] = {}
                                item['Library']['Id'] = library
                                item['Library']['Name'] = db.get_view_name(library)
                                self.updated_output[item['Type']].put(item)
                                self.total_updates += 1

                if LibraryViews[library] == "musicvideos":
                    result = self.EmbyServer.API.get_itemsSync(library, "MusicVideo", False, {'MinDateLastSavedForUser': last_sync})
                elif LibraryViews[library] == "tvshows":
                    result = self.EmbyServer.API.get_itemsSync(library, "Episode", False, {'MinDateLastSavedForUser': last_sync})
                elif LibraryViews[library] == "movies":
                    result = self.EmbyServer.API.get_itemsSync(library, "Movie", False, {'MinDateLastSavedForUser': last_sync})
                elif LibraryViews[library] == "music":
                    result = self.EmbyServer.API.get_itemsSync(library, "Audio", False, {'MinDateLastSavedForUser': last_sync})
                elif LibraryViews[library] == "mixed":
                    result = self.EmbyServer.API.get_itemsSync(library.replace('Mixed:', ""), "Episode,Movie,MusicVideo,Audio", False, {'MinDateLastSavedForUser': last_sync})
                else:
                    result = False

                if result:
                    for data in result:
                        for item in data['Items']:
                            if item['Type'] in self.userdata_output:
                                item['Library'] = {}
                                item['Library']['Id'] = library
                                item['Library']['Name'] = db.get_view_name(library)
                                self.userdata_output[item['Type']].put(item)
                                self.total_updates += 1

        if plugin:
            result = self.EmbyServer.API.get_sync_queue(last_sync, None) #Kodi companion plugin
            self.removed(result['ItemsRemoved'])

        return True

    #Select from libraries synced. Either update or repair libraries.
    #Send event back to service.py
    def select_libraries(self, mode):
        whitelist = [x.replace('Mixed:', "") for x in self.EmbyServer.Utils.SyncData['Whitelist']]
        libraries = []

        with database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)

            if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection'):
                for library in self.EmbyServer.Utils.SyncData['Whitelist']:
                    name = db.get_view_name(library.replace('Mixed:', ""))
                    libraries.append({'Id': library, 'Name': name})
            else:
                available = [x for x in self.EmbyServer.Utils.SyncData['SortedViews'] if x not in whitelist]

                for library in available:
                    _, name, media, _ = db.get_view(library)

                    if media in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                        libraries.append({'Id': library, 'Name': name})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, self.EmbyServer.Utils.Translate(33121))
        selection = self.EmbyServer.Utils.dialog("multi", self.EmbyServer.Utils.Translate(33120), choices)

        if selection is None:
            return

        #"All" selected
        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        if mode == 'SyncLibrarySelection':
            for x in selection:
                self.add_library(libraries[x - 1]['Id'], True)
        elif mode == 'AddLibrarySelection':
            for x in selection:
                self.add_library(libraries[x - 1]['Id'], False)
        elif mode == 'RepairLibrarySelection':
            for x in selection:
                self.remove_library(libraries[x - 1]['Id'])
                self.add_library(libraries[x - 1]['Id'], False)
        elif mode == 'RemoveLibrarySelection':
            for x in selection:
                self.remove_library(libraries[x - 1]['Id'])

    def patch_music(self, notification):
        self.sync.patch_music(notification)

    def add_library(self, library_id, update):
        self.add_lib_queue.put((library_id, update))
        self.LOG.info("---[ added library: %s ]" % library_id)

    def remove_library(self, library_id):
        self.remove_lib_queue.put(library_id)
        self.LOG.info("---[ removed library: %s ]" % library_id)

    #Add item_id to userdata queue
    def userdata(self, data):
        items = [x['ItemId'] for x in data]

        for item in self.EmbyServer.Utils.split_list(items):
            self.userdata_queue.put(item)

        self.total_updates += len(items)
        self.LOG.info("---[ userdata:%s ]" % len(items))

    #Add item_id to updated queue
    def updated(self, data):
        for item in self.EmbyServer.Utils.split_list(data):
            self.updated_queue.put(item)

        self.total_updates += len(data)
        self.LOG.info("---[ updated:%s ]" % len(data))

    #Add item_id to removed queue
    def removed(self, data):
        for item in data:
            if item in list(self.removed_queue.queue):
                continue

            self.removed_queue.put(item)

        self.total_updates += len(data)
        self.LOG.info("---[ removed:%s ]" % len(data))

    #Setup a 1 minute delay for items to be verified
    def delay_verify(self, data):
        time_set = datetime.today() + timedelta(seconds=60)

        for item in data:
            self.verify_queue.put((time_set, item,))

        self.LOG.info("---[ verify:%s ]" % len(data))

class UpdatedWorker(threading.Thread):
    def __init__(self, queue, library, DB):
        self.LOG = helper.loghandler.LOG('EMBY.library.UpdatedWorker')
        self.library = library
        self.queue = queue
        self.notify = self.library.EmbyServer.Utils.Settings.newContent
        self.DB = database.Database(self.library.EmbyServer.Utils, DB, True)
        self.library.set_progress_dialog()
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.library.ThreadingLock:
            with self.DB as kodidb:
                with database.Database(self.library.EmbyServer.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()
                        self.library.update_progress_dialog(item)

                        if 'Library' in item:
                            LibID = item['Library']
                        else:
                            LibID = None

                        if item['Type'] == 'Movie':
                            Ret = core.movies.Movies(self.library.EmbyServer, embydb, kodidb).movie(item, LibID)
                        elif item['Type'] == 'BoxSet':
                            Ret = core.movies.Movies(self.library.EmbyServer, embydb, kodidb).boxset(item)
                        elif item['Type'] == 'MusicVideo':
                            Ret = core.musicvideos.MusicVideos(self.library.EmbyServer, embydb, kodidb).musicvideo(item, LibID)
                        elif item['Type'] == 'Series':
                            Ret = core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb).tvshow(item, LibID)
                        elif item['Type'] == 'Season':
                            Ret = core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb).season(item, LibID)
                        elif item['Type'] == 'Episode':
                            Ret = core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb).episode(item, LibID)
                        elif item['Type'] == 'MusicAlbum':
                            Ret = core.music.Music(self.library.EmbyServer, embydb, kodidb).album(item, LibID)
                        elif item['Type'] == 'Audio':
                            Ret = core.music.Music(self.library.EmbyServer, embydb, kodidb).song(item, LibID)
                        elif item['Type'] in ('MusicArtist', 'AlbumArtist'):
                            Ret = core.music.Music(self.library.EmbyServer, embydb, kodidb).artist(item, LibID)
                        else:
                            self.LOG.error("Media Type not found: %s" % item['Type'])
                            break

                        if Ret == "Invalid Filepath":
                            break

                        if Ret and self.notify:
                            self.library.notify_output.put({'Type': item['Type'], 'Name': self.library.get_naming(item)})

                        if self.library.Player.SyncPause:
                            break

        self.LOG.info("--<[ q:updated/%s ]" % id(self))
        self.is_done = True

#Incomming Update Data from Websocket
class UserDataWorker(threading.Thread):
    def __init__(self, queue, library, DB):
        self.LOG = helper.loghandler.LOG('EMBY.library.UserDataWorker')
        self.library = library
        self.queue = queue
        self.DB = database.Database(self.library.EmbyServer.Utils, DB, True)
        self.is_done = False
        self.library.set_progress_dialog()
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.library.ThreadingLock:
            with self.DB as kodidb:
                with database.Database(self.library.EmbyServer.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()
                        self.library.update_progress_dialog(item)

                        if item['Type'] in ('Movie', 'BoxSet'):
                            core.movies.Movies(self.library.EmbyServer, embydb, kodidb).userdata(item)

                        elif item['Type'] == 'MusicVideo':
                            core.musicvideos.MusicVideos(self.library.EmbyServer, embydb, kodidb).userdata(item)

                        elif item['Type'] in ('TVShow', 'Series', 'Season', 'Episode'):
                            core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb).userdata(item)

                        elif item['Type'] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                            core.music.Music(self.library.EmbyServer, embydb, kodidb).userdata(item)

                        if self.library.Player.SyncPause:
                            break

        self.LOG.info("--<[ q:userdata/%s ]" % id(self))
        self.is_done = True

class SortWorker(threading.Thread):
    def __init__(self, library):
        self.LOG = helper.loghandler.LOG('EMBY.library.SortWorker')
        self.library = library
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.library.ThreadingLock:
            with database.Database(self.library.EmbyServer.Utils, 'emby', True) as embydb:
                db = database.emby_db.EmbyDatabase(embydb.cursor)

                while not self.library.removed_queue.empty():
                    item_id = self.library.removed_queue.get()
                    media = db.get_media_by_id(item_id)

                    if media:
                        self.library.removed_output[media].put({'Id': item_id, 'Type': media})
                    else:
                        items = db.get_media_by_parent_id(item_id)

                        if not items:
                            self.LOG.info("Could not find media %s in the emby database." % item_id)
                        else:
                            for item in items:
                                self.library.removed_output[item[1]].put({'Id': item[0], 'Type': item[1]})

                    if self.library.stop_thread:
                        break

            self.LOG.info("--<[ q:sort/%s ]" % id(self))
            self.is_done = True

class RemovedWorker(threading.Thread):
    def __init__(self, queue, library, DB):
        self.LOG = helper.loghandler.LOG('EMBY.library.RemovedWorker')
        self.library = library
        self.queue = queue
        self.DB = database.Database(self.library.EmbyServer.Utils, DB, True)
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.library.ThreadingLock:
            with self.DB as kodidb:
                with database.Database(self.library.EmbyServer.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()

                        if item['Type'] in ('Movie', 'BoxSet'):
                            core.movies.Movies(self.library.EmbyServer, embydb, kodidb).remove(item['Id'])

                        elif item['Type'] == 'MusicVideo':
                            core.musicvideos.MusicVideos(self.library.EmbyServer, embydb, kodidb).remove(item['Id'])

                        elif item['Type'] in ('TVShow', 'Series', 'Season', 'Episode'):
                            core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb).remove(item['Id'])

                        elif item['Type'] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                            core.music.Music(self.library.EmbyServer, embydb, kodidb).remove(item['Id'])

                        if self.library.Player.SyncPause:
                            break

        self.LOG.info("--<[ q:removed/%s ]" % id(self))
        self.is_done = True

class NotifyWorker(threading.Thread):
    def __init__(self, library):
        self.LOG = helper.loghandler.LOG('EMBY.library.NotifyWorker')
        self.library = library
        self.video_time = int(self.library.EmbyServer.Utils.Settings.newvideotime) * 1000
        self.music_time = int(self.library.EmbyServer.Utils.Settings.newmusictime) * 1000
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        while not self.library.notify_output.empty():
            item = self.library.notify_output.get()
            time = self.music_time if item['Type'] == 'Audio' else self.video_time

            if time and (not self.library.Player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')):
                self.library.EmbyServer.Utils.dialog("notification", heading="%s %s" % (self.library.EmbyServer.Utils.Translate(33049), item['Type']), message=item['Name'], icon="{emby}", time=time, sound=False)

            if self.library.stop_thread:
                break

        self.LOG.info("--<[ q:notify/%s ]" % id(self))
        self.is_done = True

class GetItemWorker(threading.Thread):
    def __init__(self, library, queue, output):
        self.library = library
        self.queue = queue
        self.output = output
        self.removed = []
        self.is_done = False
        self.LOG = helper.loghandler.LOG('EMBY.downloader.GetItemWorker')
        self.info = (
            "Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,Video3DFormat,"
            "OfficialRating,CumulativeRunTimeTicks,ItemCounts,PremiereDate,ProductionYear,"
            "Metascore,AirTime,DateCreated,People,Overview,CommunityRating,StartDate,"
            "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
            "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,Status,EndDate,"
            "MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio,DisplayOrder,"
            "PresentationUniqueKey,OriginalTitle,MediaSources,AlternateMediaSources,PartCount"
        )
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        count = 0

        while not self.queue.empty():
            item_ids = self.queue.get()
            clean_list = [str(x) for x in item_ids]
            request = {
                'type': "GET",
                'handler': "Users/%s/Items" % self.library.EmbyServer.Data['auth.user_id'],
                'params': {
                    'Ids': ','.join(clean_list),
                    'Fields': self.info
                }
            }
            result = self.library.EmbyServer.http.request(request)
            self.removed.extend(list(set(clean_list) - set([str(x['Id']) for x in result['Items']])))

            for item in result['Items']:
                if item['Type'] in self.output:
                    self.output[item['Type']].put(item)

            count += len(clean_list)

        self.is_done = True

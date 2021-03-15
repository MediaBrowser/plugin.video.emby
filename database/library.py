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
import emby.downloader
import helper.loghandler
from . import database
from . import sync

class Library(threading.Thread):
    def __init__(self, Monitor, server_id):
        self.LOG = helper.loghandler.LOG('EMBY.library.Library')
        self.Monitor = Monitor
        self.server_id = server_id
        self.SyncSkipResume = False
        self.SyncInProgress = False
        self.SyncLater = False
        self.started = False
        self.stop_thread = False
        self.suspend = False
        self.pending_refresh = False
        self.screensaver = None
        self.progress_updates = None
        self.total_updates = 0
        self.direct_path = self.Monitor.Service.Utils.settings('useDirectPaths') == "1"
        self.LIMIT = min(int(self.Monitor.Service.Utils.settings('limitIndex') or 50), 50)
        self.DTHREADS = int(self.Monitor.Service.Utils.settings('limitThreads') or 3)
        self.MEDIA = {'Movie': core.movies.Movies, 'BoxSet': core.movies.Movies, 'MusicVideo': core.musicvideos.MusicVideos, 'TVShow': core.tvshows.TVShows, 'Series': core.tvshows.TVShows, 'Season': core.tvshows.TVShows, 'Episode': core.tvshows.TVShows, 'Music': core.music.Music, 'MusicAlbum': core.music.Music, 'MusicArtist': core.music.Music, 'AlbumArtist': core.music.Music, 'Audio': core.music.Music, 'MusicDisableScan': core.music.MusicDBIO}
        self.server = self.Monitor.EmbyServer[self.server_id].get_client()
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
        self.database_lock = threading.Lock()
        self.music_database_lock = threading.Lock()
        self.sync = sync.Sync
        self.progress_percent = 0
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

        try:
            self.progress_percent = int((float(self.total_updates - queue_size) / float(self.total_updates))*100)
        except Exception:
            self.progress_percent = 0

        self.LOG.debug("--[ pdialog (%s/%s) ]" % (queue_size, self.total_updates))

        if self.total_updates < int(self.Monitor.Service.Utils.settings('syncProgress') or 50):
            return

        if self.progress_updates is None:
            self.LOG.info("-->[ pdialog ]")
            self.progress_updates = xbmcgui.DialogProgressBG()
            self.progress_updates.create(self.Monitor.Service.Utils.Translate('addon_name'), self.Monitor.Service.Utils.Translate(33178))

    def update_progress_dialog(self, item):
        if self.progress_updates:
            message = self.get_naming(item)
            self.progress_updates.update(self.progress_percent, message="%s: %s" % (self.Monitor.Service.Utils.Translate(33178), message))

    def run(self):
        self.LOG.warning("--->[ library ]")

        while not self.stop_thread:
            if self.Monitor.waitForAbort(5):
                break

            if not self.started and not self.startup():
                self.stop_client()

            if self.sync.running:
                continue

            self.service()

            if self.Monitor.Service.SyncPause:
                continue

        self.Monitor.Service.SyncPause = False
        self.LOG.warning("---<[ library ]")

    def service(self):
        for thread in self.download_threads:
            if thread.Done:
                self.removed(thread.removed)
                self.download_threads.remove(thread)

        for threads in (self.emby_threads, self.writer_threads_updated, self.writer_threads_userdata, self.writer_threads_removed):
            for thread in threads:
                if thread.Done:
                    threads.remove(thread)

        if not self.Monitor.player.isPlayingVideo() or self.Monitor.Service.Utils.settings('syncDuringPlay.bool') or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
            if not self.Monitor.player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
                if not self.SyncSkipResume:
                    if database.get_sync(self.Monitor.Service.Utils)['Libraries']:
                        self.sync_libraries(True)

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
            self.SyncInProgress = True
            self.set_progress_dialog()

            if not self.Monitor.Service.Utils.settings('dbSyncScreensaver.bool') and self.screensaver is None:
                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                self.screensaver = self.Monitor.Service.Utils.Screensaver
                self.Monitor.Service.Utils.set_screensaver(value="")

        if (self.pending_refresh and not self.download_threads and not self.writer_threads_updated and not self.writer_threads_userdata and not self.writer_threads_removed):
            self.pending_refresh = False
            self.save_last_sync()
            self.total_updates = 0
            self.SyncInProgress = False

            if self.progress_updates:
                self.LOG.info("--<[ pdialog ]")
                self.progress_updates.close()
                self.progress_updates = None

            if not self.Monitor.Service.Utils.settings('dbSyncScreensaver.bool') and self.screensaver is not None:
                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                self.Monitor.Service.Utils.set_screensaver(value=self.screensaver)
                self.screensaver = None

            if not xbmc.getCondVisibility('Window.IsMedia'):
                xbmc.executebuiltin('UpdateLibrary(video)')

    def stop_client(self):
        self.stop_thread = True

    #When there's an active thread. Let the main thread know
    def enable_pending_refresh(self):
        self.pending_refresh = True
        self.SyncInProgress = True

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

    #Wait 60 seconds to verify the item by moving it to the updated queue to
    #verify item is still available to user.
    #Used for internal deletion--callback takes too long
    #Used for parental control--server does not send a new event when item has been blocked.
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
            if queue[0].qsize() and len(self.download_threads) < self.DTHREADS:
                new_thread = emby.downloader.GetItemWorker(self.server, queue[0], queue[1], self.Monitor.Service.Utils)
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
        if self._worker_removed_size():
            self.LOG.info("[ DELAY UPDATES ]")
            return

        for queues in self.updated_output:
            queue = self.updated_output[queues]

            if queue.qsize() and not len(self.writer_threads_updated):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UpdatedWorker(queue, self, "music", self.music_database_lock)
                else:
                    new_thread = UpdatedWorker(queue, self, "video", self.database_lock)

                self.LOG.info("-->[ q:updated/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_updated.append(new_thread)
                self.enable_pending_refresh()

    #Update userdata in the Kodi database
    def worker_userdata(self):
        if self._worker_removed_size():
            self.LOG.info("[ DELAY UPDATES ]")
            return

        for queues in self.userdata_output:
            queue = self.userdata_output[queues]

            if queue.qsize() and not len(self.writer_threads_userdata):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UserDataWorker(queue, self, "music", self.music_database_lock)
                else:
                    new_thread = UserDataWorker(queue, self, "video", self.database_lock)

                self.LOG.info("-->[ q:userdata/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_userdata.append(new_thread)
                self.enable_pending_refresh()

    #Remove items from the Kodi database
    def worker_remove(self):
        for queues in self.removed_output:
            queue = self.removed_output[queues]

            if queue.qsize() and not len(self.writer_threads_removed):
                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = RemovedWorker(queue, self, "music", self.music_database_lock)
                else:
                    new_thread = RemovedWorker(queue, self, "video", self.database_lock)

                self.LOG.info("-->[ q:removed/%s/%s ]" % (queues, id(new_thread)))
                self.writer_threads_removed.append(new_thread)
                self.enable_pending_refresh()

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
                self._remove_libraries(library_id)
            xbmc.executebuiltin("Container.Refresh")

    def worker_add_lib(self):
        if self.add_lib_queue.qsize():
            while not self.add_lib_queue.empty():
                library_id, update = self.add_lib_queue.get()
                self._add_libraries(library_id, update)

            xbmc.executebuiltin("Container.Refresh")

    def sync_libraries(self, forced):
        with self.sync(self) as syncObj:
            syncObj.libraries(None, False, forced)

        if self.Monitor.Service.SyncPause:
            return

        self.Monitor.Service.Views.get_nodes()

    def _add_libraries(self, library_id, update):
        with self.sync(self) as syncObj:
            syncObj.libraries(library_id, update, False)

        if self.Monitor.Service.SyncPause:
            return

        self.Monitor.Service.Views.get_nodes()

    def _remove_libraries(self, library_id):
        with self.sync(self) as syncObj:
            syncObj.remove_library(library_id)

        if self.Monitor.Service.SyncPause:
            return

        self.Monitor.Service.Views.remove_library(library_id)
        self.Monitor.Service.Views.get_views()
        self.Monitor.Service.Views.get_nodes()

    #Run at startup.
    #Check databases.
    #Check for the server plugin.
    def startup(self):
        self.started = True
        self.Monitor.Service.Views.get_views()
        self.Monitor.Service.Views.get_nodes()

        if database.get_sync(self.Monitor.Service.Utils)['Libraries']:
            self.sync_libraries(False)
        elif not self.Monitor.Service.Utils.settings('SyncInstallRunDone.bool'):
            with self.sync(self) as syncObj:
                if not syncObj.libraries(None, False, False):
                    if self.SyncLater:
                        self.Monitor.Service.Utils.dialog("ok", heading="{emby}", line1=self.Monitor.Service.Utils.Translate(33129))
                        self.Monitor.Service.Utils.settings('SyncInstallRunDone.bool', True)
                        syncLibs = database.get_sync(self.Monitor.Service.Utils)
                        syncLibs['Libraries'] = []
                        database.save_sync(self.Monitor.Service.Utils, syncLibs)
                        return True
                else:
                    return False

            self.Monitor.Service.Views.get_nodes()
            xbmc.executebuiltin('ReloadSkin()')
            return True

        self.get_fast_sync()
        return True

    def get_fast_sync(self):
        enable_fast_sync = False

        if self.Monitor.Service.Utils.settings('SyncInstallRunDone.bool'):
            if self.Monitor.Service.Utils.settings('kodiCompanion.bool'):
                for plugin in self.server['api'].get_plugins():
                    if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                        enable_fast_sync = True
                        break

                self.fast_sync(enable_fast_sync)
                self.LOG.info("--<[ retrieve changes ]")

    #Movie and userdata not provided by server yet
    def fast_sync(self, plugin):
        last_sync = self.Monitor.Service.Utils.settings('LastIncrementalSync')
        syncOBJ = database.get_sync(self.Monitor.Service.Utils)
        self.LOG.info("--[ retrieve changes ] %s" % last_sync)

        for library in syncOBJ['Whitelist']:
            for data in self.Monitor.Downloader.get_items(library.replace('Mixed:', ""), "Series,Season,Episode,BoxSet,Movie,MusicVideo,MusicArtist,MusicAlbum,Audio", False, {'MinDateLastSaved': last_sync}, self.server_id):
                with database.Database(self.Monitor.Service.Utils, 'emby', True) as embydb:
                    emby_db = database.emby_db.EmbyDatabase(embydb.cursor)

                    for item in data['Items']:
                        if item['Type'] in self.updated_output:
                            item['Library'] = {}
                            item['Library']['Id'] = library
                            item['Library']['Name'] = emby_db.get_view_name(library)
                            self.updated_output[item['Type']].put(item)
                            self.total_updates += 1

            for data in self.Monitor.Downloader.get_items(library.replace('Mixed:', ""), "Episode,Movie,MusicVideo,Audio", False, {'MinDateLastSavedForUser': last_sync}, self.server_id):
                with database.Database(self.Monitor.Service.Utils, 'emby', True) as embydb:
                    emby_db = database.emby_db.EmbyDatabase(embydb.cursor)

                    for item in data['Items']:
                        if item['Type'] in self.userdata_output:
                            item['Library'] = {}
                            item['Library']['Id'] = library
                            item['Library']['Name'] = emby_db.get_view_name(library)
                            self.userdata_output[item['Type']].put(item)
                            self.total_updates += 1

        if plugin:
            try:
                result = self.server['api'].get_sync_queue(last_sync, None) #Kodi companion plugin
                self.removed(result['ItemsRemoved'])
            except Exception as error:
                self.LOG.error(error)

        return True

    def save_last_sync(self):
        time_now = datetime.utcnow() - timedelta(minutes=2)
        last_sync = time_now.strftime('%Y-%m-%dT%H:%M:%Sz')
        self.Monitor.Service.Utils.settings('LastIncrementalSync', value=last_sync)
        self.LOG.info("--[ sync/%s ]" % last_sync)

    #Select from libraries synced. Either update or repair libraries.
    #Send event back to service.py
    def select_libraries(self, mode):
        modes = {
            'SyncLibrarySelection': 'SyncLibrary',
            'RepairLibrarySelection': 'RepairLibrary',
            'AddLibrarySelection': 'SyncLibrary',
            'RemoveLibrarySelection': 'RemoveLibrary'
        }

        syncOBJ = database.get_sync(self.Monitor.Service.Utils)
        whitelist = [x.replace('Mixed:', "") for x in syncOBJ['Whitelist']]
        libraries = []

        with database.Database(self.Monitor.Service.Utils, 'emby', True) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)

            if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection'):
                for library in syncOBJ['Whitelist']:
                    name = db.get_view_name(library.replace('Mixed:', ""))
                    libraries.append({'Id': library, 'Name': name})
            else:
                available = [x for x in syncOBJ['SortedViews'] if x not in whitelist]

                for library in available:
                    name, media = db.get_view(library)

                    if media in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                        libraries.append({'Id': library, 'Name': name})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, self.Monitor.Service.Utils.Translate(33121))
        selection = self.Monitor.Service.Utils.dialog("multi", self.Monitor.Service.Utils.Translate(33120), choices)

        if selection is None:
            return

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:
            library = libraries[x - 1]
            selected_libraries.append(library['Id'])

        self.Monitor.Service.Utils.event(modes[mode], {'Id': ','.join([libraries[x - 1]['Id'] for x in selection]), 'Update': mode == 'SyncLibrarySelection', 'ServerId': self.server_id})

    def patch_music(self, notification):
        with self.sync(self) as syncObj:
            syncObj.patch_music(notification)

    def add_library(self, library_id, update):
        self.add_lib_queue.put((library_id, update))
        self.LOG.info("---[ added library: %s ]" % library_id)

    def remove_library(self, library_id):
        self.remove_lib_queue.put(library_id)
        self.LOG.info("---[ removed library: %s ]" % library_id)

    #Add item_id to userdata queue
    def userdata(self, data):
        items = [x['ItemId'] for x in data]

        for item in self.Monitor.Service.Utils.split_list(items, self.LIMIT):
            self.userdata_queue.put(item)

        self.total_updates += len(items)
        self.LOG.info("---[ userdata:%s ]" % len(items))

    #Add item_id to updated queue
    def updated(self, data):
        for item in self.Monitor.Service.Utils.split_list(data, self.LIMIT):
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
    def __init__(self, queue, library, DB, lock):
        self.LOG = helper.loghandler.LOG('EMBY.library.UpdatedWorker')
        self.library = library
        self.queue = queue
        self.notify = self.library.Monitor.Service.Utils.settings('newContent.bool')
        self.lock = lock
        self.DB = database.Database(self.library.Monitor.Service.Utils, DB, True)
        self.library.set_progress_dialog()
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.lock:
            with self.DB as kodidb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()
                        self.library.update_progress_dialog(item)

                        if 'Library' in item:
                            LibID = item['Library']
                        else:
                            LibID = None

                        Ret = self.library.MEDIA[item['Type']](self.library.server, embydb, kodidb, self.library.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)[item['Type']](item, LibID)

                        if Ret == "Invalid Filepath":
                            break

                        if Ret and self.notify:
                            self.library.notify_output.put(item['Type'], self.library.get_naming(item))

                        if self.library.Monitor.Service.SyncPause:
                            break

        self.LOG.info("--<[ q:updated/%s ]" % id(self))
        self.is_done = True

#Incomming Update Data from Websocket
class UserDataWorker(threading.Thread):
    def __init__(self, queue, library, DB, lock):
        self.LOG = helper.loghandler.LOG('EMBY.library.UserDataWorker')
        self.library = library
        self.queue = queue
        self.lock = lock
        self.DB = database.Database(self.library.Monitor.Service.Utils, DB, True)
        self.is_done = False
        self.library.set_progress_dialog()
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.lock:
            with self.DB as kodidb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()
                        self.library.update_progress_dialog(item)
                        self.library.MEDIA[item['Type']](self.library.server, embydb, kodidb, self.library.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id).userdata(item)

                        if self.library.Monitor.Service.SyncPause:
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
        with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
            db = database.emby_db.EmbyDatabase(embydb.cursor)

            while not self.library.removed_queue.empty():
                item_id = self.library.removed_queue.get()

                try:
                    media = db.get_media_by_id(item_id)
                    self.library.removed_output[media].put({'Id': item_id, 'Type': media})
                except Exception:
                    items = db.get_media_by_parent_id(item_id)

                    if not items:
                        self.LOG.info("Could not find media %s in the emby database." % item_id)
                    else:
                        for item in items:
                            self.library.removed_output[item[1]].put({'Id': item[0], 'Type': item[1]})

                if self.library.Monitor.Service.ShouldStop or self.library.Monitor.sleep:
                    break

        self.LOG.info("--<[ q:sort/%s ]" % id(self))
        self.is_done = True

class RemovedWorker(threading.Thread):
    def __init__(self, queue, library, DB, lock):
        self.LOG = helper.loghandler.LOG('EMBY.library.RemovedWorker')
        self.library = library
        self.queue = queue
        self.lock = lock
        self.DB = database.Database(self.library.Monitor.Service.Utils, DB, True)
        self.is_done = False
        threading.Thread.__init__(self)
        self.start()

    def Done(self):
        return self.is_done

    def run(self):
        with self.lock:
            with self.DB as kodidb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    while not self.queue.empty():
                        item = self.queue.get()
                        self.library.MEDIA[item['Type']](self.library.server, embydb, kodidb, self.library.direct_path, self.library.Monitor.Service.Utils, self.library.server_id).remove(item['Id'])

                        if self.library.Monitor.Service.SyncPause:
                            break

        self.LOG.info("--<[ q:removed/%s ]" % id(self))
        self.is_done = True

class NotifyWorker(threading.Thread):
    def __init__(self, library):
        self.LOG = helper.loghandler.LOG('EMBY.library.NotifyWorker')
        self.library = library
        self.video_time = int(self.library.Monitor.Service.Utils.settings('newvideotime')) * 1000
        self.music_time = int(self.library.Monitor.Service.Utils.settings('newmusictime')) * 1000
        self.is_done = False
        threading.Thread.__init__(self)

    def Done(self):
        return self.is_done

    def run(self):
        while not self.library.notify_output.empty():
            item = self.library.notify_output.get()
            time = self.music_time if item[0] == 'Audio' else self.video_time

            if time and (not self.library.Monitor.player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')):
                self.library.Monitor.Service.Utils.dialog("notification", heading="%s %s" % (self.library.Monitor.Service.Utils.Translate(33049), item[0]), message=item[1], icon="{emby}", time=time, sound=False)

            if self.library.Monitor.Service.ShouldStop or self.library.Monitor.sleep:
                break

        self.LOG.info("--<[ q:notify/%s ]" % id(self))
        self.is_done = True

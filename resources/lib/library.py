# -*- coding: utf-8 -*-

##################################################################################################

import json
import logging
import Queue
import threading
import sys
from datetime import datetime, timedelta

import xbmc
import xbmcgui

import downloader as server
from objects import Movies, TVShows, MusicVideos, Music
from objects.kodi import Movies as kMovies, TVShows as kTVShows, MusicVideos as kMusicVideos, Music as kMusic, Kodi
from database import Database, emby_db, get_sync, save_sync
from sync import Sync
from views import Views
from helper import _, api, stop, settings, window, dialog, event, progress, compare_version, LibraryException
from helper.utils import split_list, set_screensaver, get_screensaver
from emby import Emby

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
LIMIT = min(int(settings('limitIndex') or 50), 50)
DTHREADS = int(settings('limitThreads') or 3)
MEDIA = {
    'Movie': Movies,
    'BoxSet': Movies,
    'MusicVideo': MusicVideos,
    'Series': TVShows,
    'Season': TVShows,
    'Episode': TVShows,
    'MusicAlbum': Music,
    'MusicArtist': Music,
    'AlbumArtist': Music,
    'Audio': Music
}

##################################################################################################



class Library(threading.Thread):

    started = False
    stop_thread = False
    suspend = False
    pending_refresh = False
    screensaver = None
    progress_updates = None
    total_updates = 0


    def __init__(self, monitor):

        self.media = {'Movies': Movies, 'TVShows': TVShows, 'MusicVideos': MusicVideos, 'Music': Music}
        self.kodi_media = {'Movies': kMovies, 'TVShows': kTVShows, 'MusicVideos': kMusicVideos, 'Music': kMusic, 'Kodi': Kodi}
        self.MEDIA = MEDIA

        self.direct_path = settings('useDirectPaths') == "1"
        self.progress_display = int(settings('syncProgress') or 50)
        self.monitor = monitor
        self.player = monitor.monitor.player
        self.server = Emby().get_client()
        self.updated_queue = Queue.Queue()
        self.userdata_queue = Queue.Queue()
        self.removed_queue = Queue.Queue()
        self.updated_output = self.__new_queues__()
        self.userdata_output = self.__new_queues__()
        self.removed_output = self.__new_queues__()
        self.notify_output = Queue.Queue()
        self.add_lib_queue = Queue.Queue()
        self.remove_lib_queue = Queue.Queue()
        self.verify_queue = Queue.Queue()

        self.emby_threads = []
        self.download_threads = []
        self.notify_threads = []
        self.writer_threads = {'updated': [], 'userdata': [], 'removed': []}
        self.database_lock = threading.Lock()
        self.music_database_lock = threading.Lock()
        self.sync = Sync

        threading.Thread.__init__(self)
        self.start()

    def __new_queues__(self):
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

    def run(self):

        LOG.warn("--->[ library ]")
        self.verify_libs = False

        while not self.stop_thread:

            if self.monitor.waitForAbort(1):
                break

            try:
                if not self.started and not self.startup():
                    self.stop_client()

                if self.sync.running:
                    continue

                self.service()
            except LibraryException as error:

                if error.status in ('StopWriteCalled', 'ProgressStopped'):
                    continue

                break
            except Exception as error:
                LOG.exception(error)

                break

            if self.monitor.waitForAbort(2):
                break

        window('emby_sync', clear=True)
        LOG.warn("---<[ library ]")

    @stop()
    def service(self):
        
        ''' If error is encountered, it will rerun this function.
            Start new "daemon threads" to process library updates.
            (actual daemon thread is not supported in Kodi)
        '''
        for thread in self.download_threads:
            if thread.is_done:

                self.removed(thread.removed)
                self.download_threads.remove(thread)

        for threads in (self.emby_threads, self.writer_threads['updated'], self.writer_threads['userdata'],
                        self.writer_threads['removed']):
            for thread in threads:

                if thread.is_done:
                    threads.remove(thread)

        if not self.player.isPlayingVideo() or settings('syncDuringPlay.bool') or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
            if not self.player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):

                if self.verify_libs:
                    self.verify_libs = False

                    if get_sync()['Libraries']:
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
            window('emby_sync.bool', True)

            if self.total_updates > self.progress_display:
                queue_size = self.worker_queue_size()

                if self.progress_updates is None:

                    self.progress_updates = xbmcgui.DialogProgressBG()
                    self.progress_updates.create(_('addon_name'), _(33178))
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates))*100), message="%s: %s" % (_(33178), queue_size))
                elif queue_size:
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates))*100), message="%s: %s" % (_(33178), queue_size))
                else:
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates))*100), message=_(33178))

            if not settings('dbSyncScreensaver.bool') and self.screensaver is None:

                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                self.screensaver = get_screensaver()
                set_screensaver(value="")
        
        if (self.pending_refresh and not self.download_threads and not self.writer_threads['updated'] and
                                     not self.writer_threads['userdata'] and not self.writer_threads['removed']):
            self.pending_refresh = False
            self.save_last_sync()
            self.total_updates = 0
            window('emby_sync', clear=True)

            if self.progress_updates:

                self.progress_updates.close()
                self.progress_updates = None

            if not settings('dbSyncScreensaver.bool') and self.screensaver is not None:

                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                set_screensaver(value=self.screensaver)
                self.screensaver = None

            if not xbmc.getCondVisibility('Window.IsMedia'):
                xbmc.executebuiltin('UpdateLibrary(video)')
            else: # Prevent cursor from moving
                xbmc.executebuiltin('Container.Refresh')
                window('emby.updatewidgets.bool', True)

        elif window('emby.updatewidgets.bool') and not xbmc.getCondVisibility('Window.IsMedia'):

            ''' In case an update happened but we were not on the homescreen and 
                now we are, force widget to update.
            '''
            window('emby.updatewidgets', clear=True)
            xbmc.executebuiltin('UpdateLibrary(video)')

    def stop_client(self):
        self.stop_thread = True

    def enable_pending_refresh(self):

        ''' When there's an active thread. Let the main thread know.
        '''
        self.pending_refresh = True
        window('emby_sync.bool', True)

    def worker_queue_size(self):

        ''' Get how many items are queued up for worker threads.
        '''
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

        for queues in self.removed_output:
            total += self.removed_output[queues].qsize()

        return total

    def worker_verify(self):

        ''' Wait 60 seconds to verify the item by moving it to the updated queue to
            verify item is still available to user.
            Used for internal deletion--callback takes too long
            Used for parental control--server does not send a new event when item has been blocked.
        '''
        if self.verify_queue.qsize():

            ready = []
            not_ready = []

            while True:

                try:
                    time_set, item_id = self.verify_queue.get(timeout=1)
                except Queue.Empty:
                    break

                if time_set <= datetime.today():
                    ready.append(item_id)
                elif item_id not in list(self.removed_queue.queue):
                    not_ready.append((time_set, item_id,))
                
                self.verify_queue.task_done()

            self.updated(ready)
            map(self.verify_queue.put, not_ready) # re-add items that are not ready yet

    def worker_downloads(self):

        ''' Get items from emby and place them in the appropriate queues.
        '''
        for queue in ((self.updated_queue, self.updated_output), (self.userdata_queue, self.userdata_output)):
            if queue[0].qsize() and len(self.download_threads) < DTHREADS:
                
                new_thread = server.GetItemWorker(self.server, queue[0], queue[1])
                LOG.info("-->[ q:download/%s ]", id(new_thread))
                self.download_threads.append(new_thread)

    def worker_sort(self):

        ''' Get items based on the local emby database and place item in appropriate queues.
        '''
        if self.removed_queue.qsize() and len(self.emby_threads) < 2:

            new_thread = SortWorker(self.removed_queue, self.removed_output)
            LOG.info("-->[ q:sort/%s ]", id(new_thread))
            self.emby_threads.append(new_thread)

    def worker_updates(self):

        ''' Update items in the Kodi database.
        '''
        if self._worker_removed_size():
            LOG.info("[ DELAY UPDATES ]")

            return

        for queues in self.updated_output:
            queue = self.updated_output[queues]

            if queue.qsize() and not len(self.writer_threads['updated']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UpdatedWorker(queue, self.notify_output, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UpdatedWorker(queue, self.notify_output, self.database_lock, "video", self.server, self.direct_path)

                LOG.info("-->[ q:updated/%s/%s ]", queues, id(new_thread))
                self.writer_threads['updated'].append(new_thread)
                self.enable_pending_refresh()

    def worker_userdata(self):

        ''' Update userdata in the Kodi database.
        '''
        for queues in self.userdata_output:
            queue = self.userdata_output[queues]

            if queue.qsize() and not len(self.writer_threads['userdata']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UserDataWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UserDataWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                LOG.info("-->[ q:userdata/%s/%s ]", queues, id(new_thread))
                self.writer_threads['userdata'].append(new_thread)
                self.enable_pending_refresh()

    def worker_remove(self):

        ''' Remove items from the Kodi database.
        '''
        for queues in self.removed_output:
            queue = self.removed_output[queues]

            if queue.qsize() and not len(self.writer_threads['removed']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = RemovedWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = RemovedWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                LOG.info("-->[ q:removed/%s/%s ]", queues, id(new_thread))
                self.writer_threads['removed'].append(new_thread)
                self.enable_pending_refresh()

    def worker_notify(self):

        ''' Notify the user of new additions.
        '''
        if self.notify_output.qsize() and not len(self.notify_threads):

            new_thread = NotifyWorker(self.notify_output, self.player)
            LOG.info("-->[ q:notify/%s ]", id(new_thread))
            self.notify_threads.append(new_thread)

    def worker_remove_lib(self):
        if self.remove_lib_queue.qsize():

            while True:
                try:
                    library_id = self.remove_lib_queue.get(timeout=0.5)
                except Queue.Empty:
                    break

                self._remove_libraries(library_id)
                self.remove_lib_queue.task_done()

            xbmc.executebuiltin("Container.Refresh")

    def worker_add_lib(self):
        if self.add_lib_queue.qsize():

            while True:
                try:
                    library_id, update = self.add_lib_queue.get(timeout=0.5)
                except Queue.Empty:
                    break

                self._add_libraries(library_id, update)
                self.add_lib_queue.task_done()

            xbmc.executebuiltin("Container.Refresh")

    def sync_libraries(self, forced=False):

        with self.sync(self, self.server) as sync:
            sync.libraries(forced=forced)

        Views().get_nodes()

    def _add_libraries(self, library_id, update=False):

        try:
            with self.sync(self, server=self.server) as sync:
                sync.libraries(library_id, update)

        except LibraryException as error:

            if error.status == 'StopWriteCalled':
                self.verify_libs = True

            raise

        Views().get_nodes()

    def _remove_libraries(self, library_id):

        try:
            with self.sync(self, self.server) as sync:
                sync.remove_library(library_id)

        except LibraryException as error:

            if error.status == 'StopWriteCalled':
                self.verify_libs = True

            raise

        Views().remove_library(library_id)
        Views().get_views()
        Views().get_nodes()

    def startup(self):

        ''' Run at startup. 
            Check databases. 
            Check for the server plugin.
        '''
        self.started = True
        Views().get_views()
        Views().get_nodes()

        try:
            if get_sync()['Libraries']:
                self.sync_libraries()

            elif not settings('SyncInstallRunDone.bool'):
                
                with self.sync(self, self.server) as sync:
                    sync.libraries()

                Views().get_nodes()
                xbmc.executebuiltin('ReloadSkin()')

                return True

            self.get_fast_sync()

            return True
        except LibraryException as error:
            LOG.error(error.status)

            if error.status in 'SyncLibraryLater':

                dialog("ok", heading="{emby}", line1=_(33129))
                settings('SyncInstallRunDone.bool', True)
                sync = get_sync()
                sync['Libraries'] = []
                save_sync(sync)

                return True

            elif error.status == 'CompanionMissing':

                dialog("ok", heading="{emby}", line1=_(33099))
                settings('kodiCompanion.bool', False)

                return True

            elif error.status == 'StopWriteCalled':
                self.verify_libs = True

            raise

        except Exception as error:
            LOG.exception(error)

        return False

    def get_fast_sync(self):

        new_fast_sync = compare_version(self.server['auth/server-version'],"4.2.0.23")
        enable_fast_sync = False

        if settings('SyncInstallRunDone.bool'):

            if settings('kodiCompanion.bool'):
                for plugin in self.server['api'].get_plugins():

                    if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                        enable_fast_sync = True

                        break

                if new_fast_sync > 0:
                    self.fast_sync(enable_fast_sync)

                elif enable_fast_sync:

                    if not self.fast_sync_plugin():
                        dialog("ok", heading="{emby}", line1=_(33128))

                        raise Exception("Failed to retrieve latest updates")
                else:
                    raise LibraryException('CompanionMissing')

                LOG.info("--<[ retrieve changes ]")

    @progress()
    def fast_sync(self, plugin, dialog):

        ''' Movie and userdata not provided by server yet.
        '''
        last_sync = settings('LastIncrementalSync')
        sync = get_sync()
        LOG.info("--[ retrieve changes ] %s", last_sync)


        for main_index, library in enumerate(sync['Whitelist']):

            # a for loop is needed here, because the 'get_items' method returns a generator
            for data in server.get_items(library.replace('Mixed:', ""),
                                         "Series,Season,Episode,BoxSet,Movie,MusicVideo,MusicArtist,MusicAlbum,Audio",
                                         False,
                                         {'MinDateLastSavedForUser': last_sync}):

                start_index = data['RestorePoint']['params']['StartIndex']

                for index, item in enumerate(data['Items']):

                    if item['Type'] in self.updated_output:
                        self.updated_output[item['Type']].put(item)

                    # the 'get_userdata_date_modified' does actually the same as the 'get_date_modified' method; see 'libraries/emby/core/api.py'
                    # so for this call no separate server request is needed
                    if item['Type'] in self.userdata_output:
                        self.userdata_output[item['Type']].put(item)

                    dialog.update(int(main_index * (50 / len(sync['Whitelist'])) +
                                      (float(start_index + index) / float(data['TotalRecordCount'])) * 
                                      (50 / len(sync['Whitelist']))),
                                  heading="%s: %s" % (_('addon_name'), item['Type']),
                                  message=item['Name'])

        # temp fix for boxsets
        boxsets = {}
        with Database('emby') as embydb:
            boxsets = dict(emby_db.EmbyDatabase(embydb.cursor).get_items_by_media('set') or {})

        for items in server.get_items(None, "BoxSet"):

            start_index = items['RestorePoint']['params']['StartIndex']

            for index, boxset in enumerate(items['Items']):

                if not (boxset['Id'] in boxsets and boxset['Etag'] == boxsets[boxset['Id']]):
                    self.updated_output['BoxSet'].put(boxset)

                dialog.update(int(50 +
                                  (float(start_index + index) / float(items['TotalRecordCount'])) *
                                  50),
                              heading="%s: %s" % (_('addon_name'), boxset['Type']),
                              message=boxset['Name'])

        if plugin:
            try:
                result = self.server['api'].get_sync_queue(last_sync)
                self.removed(result['ItemsRemoved'])

            except Exception as error:
                LOG.exception(error)

        return True

    def fast_sync_plugin(self):

        ''' Movie and userdata not provided by server yet.
        '''
        last_sync = settings('LastIncrementalSync')
        filters = ["tvshows", "boxsets", "musicvideos", "music", "movies"]
        sync = get_sync()
        LOG.info("--[ retrieve changes ] %s", last_sync)

        try:
            updated = []
            userdata = []
            removed = []

            for media in filters:
                result = self.server['api'].get_sync_queue(last_sync, ",".join([x for x in filters if x != media]))
                updated.extend(result['ItemsAdded'])
                updated.extend(result['ItemsUpdated'])
                userdata.extend(result['UserDataChanged'])
                removed.extend(result['ItemsRemoved'])

            total = len(updated) + len(userdata)

            if total > int(settings('askSyncIndicator') or 9999):

                ''' Inverse yes no, in case the dialog is forced closed by Kodi.
                '''
                if dialog("yesno", heading="{emby}", line1=_(33172).replace('{number}', str(total)), nolabel=_(107), yeslabel=_(106)):
                    LOG.warn("Large updates skipped.")

                    return True

            self.updated(updated)
            self.userdata(userdata)
            self.removed(removed)

        except Exception as error:
            LOG.exception(error)

            return False

        return True

    def save_last_sync(self):

        time_now = datetime.utcnow() - timedelta(minutes=2)
        last_sync = time_now.strftime('%Y-%m-%dT%H:%M:%Sz')
        settings('LastIncrementalSync', value=last_sync)
        LOG.info("--[ sync/%s ]", last_sync)

    def select_libraries(self, mode=None):

        ''' Select from libraries synced. Either update or repair libraries.
            Send event back to service.py
        '''
        modes = {
            'SyncLibrarySelection': 'SyncLibrary',
            'RepairLibrarySelection': 'RepairLibrary',
            'AddLibrarySelection': 'SyncLibrary',
            'RemoveLibrarySelection': 'RemoveLibrary'
        }
        sync = get_sync()
        whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
        libraries = []

        with Database('emby') as embydb:
            db = emby_db.EmbyDatabase(embydb.cursor)

            if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection'):
                for library in sync['Whitelist']:

                    name = db.get_view_name(library.replace('Mixed:', ""))
                    libraries.append({'Id': library, 'Name': name})
            else:
                available = [x for x in sync['SortedViews'] if x not in whitelist]

                for library in available:
                    name, media  = db.get_view(library)

                    if media in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                        libraries.append({'Id': library, 'Name': name})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, _(33121))
        selection = dialog("multi", _(33120), choices)

        if selection is None:
            return

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:

            library = libraries[x - 1]
            selected_libraries.append(library['Id'])

        event(modes[mode], {'Id': ','.join([libraries[x - 1]['Id'] for x in selection]), 'Update': mode == 'SyncLibrarySelection'})

    def run_library_task(self, task, notification=False):

        try:
            with self.sync(self, server=self.server) as sync:
                sync[task](notification)
        except Exception as error:
            LOG.exception(error)

            return False

        return True

    def add_library(self, library_id, update=False):

        self.add_lib_queue.put((library_id, update))
        LOG.info("---[ added library: %s ]", library_id)

    def remove_library(self, library_id):

        self.remove_lib_queue.put(library_id)
        LOG.info("---[ removed library: %s ]", library_id)

    def userdata(self, data):

        ''' Add item_id to userdata queue.
        '''
        if not data:
            return

        items = [x['ItemId'] for x in data]

        for item in split_list(items, LIMIT):
            self.userdata_queue.put(item)

        self.total_updates += len(items)
        LOG.info("---[ userdata:%s ]", len(items))

    def updated(self, data):

        ''' Add item_id to updated queue.
        '''
        if not data:
            return

        for item in split_list(data, LIMIT):
            self.updated_queue.put(item)

        self.total_updates += len(data)
        LOG.info("---[ updated:%s ]", len(data))

    def removed(self, data):

        ''' Add item_id to removed queue.
        '''
        if not data:
            return

        for item in data:

            if item in list(self.removed_queue.queue):
                continue

            self.removed_queue.put(item)

        self.total_updates += len(data)
        LOG.info("---[ removed:%s ]", len(data))

    def delay_verify(self, data):

        ''' Setup a 1 minute delay for items to be verified.
        '''
        if not data:
            return

        time_set = datetime.today() + timedelta(seconds=60)
        for item in data:
            self.verify_queue.put((time_set, item,))

        LOG.info("---[ verify:%s ]", len(data))


class UpdatedWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, notify, lock, database, *args):

        self.queue = queue
        self.notify_output = notify
        self.notify = settings('newContent.bool')
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)
        self.start()

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=1)
                        except Queue.Empty:
                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])[item['Type']]

                        try:
                            if obj(item) and self.notify:
                                self.notify_output.put((item['Type'], api.API(item).get_naming()))
                        except LibraryException as error:

                            if error.status in ('StopCalled', 'StopWriteCalled'):
                                self.queue.put(item)

                                break
                        except Exception as error:
                            LOG.exception(error)

                        self.queue.task_done()

                        if window('emby_should_stop.bool'):
                            break

        LOG.info("--<[ q:updated/%s ]", id(self))
        self.is_done = True

class UserDataWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, *args):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)
        self.start()

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=1)
                        except Queue.Empty:
                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])['UserData']

                        try:
                            obj(item)
                        except LibraryException as error:

                            if error.status in ('StopCalled', 'StopWriteCalled'):
                                self.queue.put(item)

                                break
                        except Exception as error:
                            LOG.exception(error)

                        self.queue.task_done()

                        if window('emby_should_stop.bool'):
                            break

        LOG.info("--<[ q:userdata/%s ]", id(self))
        self.is_done = True

class SortWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, output, *args):

        self.queue = queue
        self.output = output
        self.args = args
        threading.Thread.__init__(self)
        self.start()

    def run(self):

        with Database('emby') as embydb:
            database = emby_db.EmbyDatabase(embydb.cursor)

            while True:

                try:
                    item_id = self.queue.get(timeout=1)
                except Queue.Empty:
                    break

                try:
                    media = database.get_media_by_id(item_id)
                    self.output[media].put({'Id': item_id, 'Type': media})
                except Exception:
                    items = database.get_media_by_parent_id(item_id)

                    if not items:
                        LOG.info("Could not find media %s in the emby database.", item_id)
                    else:
                        for item in items:
                            self.output[item[1]].put({'Id': item[0], 'Type': item[1]})

                self.queue.task_done()

                if window('emby_should_stop.bool'):
                    break

        LOG.info("--<[ q:sort/%s ]", id(self))
        self.is_done = True

class RemovedWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, *args):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)
        self.start()

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=1)
                        except Queue.Empty:
                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])['Remove']

                        try:
                            obj(item['Id'])
                        except LibraryException as error:

                            if error.status in ('StopCalled', 'StopWriteCalled'):
                                self.queue.put(item)

                                break
                        except Exception as error:
                            LOG.exception(error)

                        self.queue.task_done()

                        if window('emby_should_stop.bool'):
                            break

        LOG.info("--<[ q:removed/%s ]", id(self))
        self.is_done = True

class NotifyWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, player):

        self.queue = queue
        self.video_time = int(settings('newvideotime')) * 1000
        self.music_time = int(settings('newmusictime')) * 1000
        self.player = player
        threading.Thread.__init__(self)

    def run(self):

        while True:

            try:
                item = self.queue.get(timeout=3)
            except Queue.Empty:
                break

            time = self.music_time if item[0] == 'Audio' else self.video_time

            if time and (not self.player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')):
                dialog("notification", heading="%s %s" % (_(33049), item[0]), message=item[1],
                       icon="{emby}", time=time, sound=False)

            self.queue.task_done()

            if window('emby_should_stop.bool'):
                break

        LOG.info("--<[ q:notify/%s ]", id(self))
        self.is_done = True

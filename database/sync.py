# -*- coding: utf-8 -*-
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

import xbmc
import xbmcgui

import helper.xmls
import helper.loghandler
from . import database
from . import emby_db

class Sync():
    running = False

    def __init__(self, library):
        self.LOG = helper.loghandler.LOG('EMBY.database.sync')
        self.library = library
        self.sync = None
#        self.running = False
        self.SyncInProgress = False
        self.screensaver = None
        self.update_library = False
        self.xmls = helper.xmls.Xmls(self.library.Monitor.Service.Utils)
        self.direct_path = self.library.Monitor.Service.Utils.settings('useDirectPaths') == "1"

        if self.running:
            self.library.Monitor.Service.Utils.dialog("ok", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33197))
            return

    #Do everything we need before the sync
    def __enter__(self):
        self.LOG.info("-->[ fullsync ]")

        if not self.library.Monitor.Service.Utils.settings('dbSyncScreensaver.bool'):
            xbmc.executebuiltin('InhibitIdleShutdown(true)')
            self.screensaver = self.library.Monitor.Service.Utils.WebserverData
            self.library.Monitor.Service.Utils.set_screensaver(value="")

        self.running = True
        self.SyncInProgress = True
        return self

    #Assign the restore point and save the sync status
    def _restore_point(self, restore):
        self.sync['RestorePoint'] = restore
        database.save_sync(self.library.Monitor.Service.Utils, self.sync)

    #Map the syncing process and start the sync. Ensure only one sync is running
    #force to resume any previous sync
    def libraries(self, library_id, update, forced):
        self.update_library = update
        self.sync = database.get_sync(self.library.Monitor.Service.Utils)

        if library_id:
            libraries = library_id.split(',')

            for selected in libraries:
                if selected not in [x.replace('Mixed:', "") for x in self.sync['Libraries']]:
                    library = self.get_libraries(selected)

                    if library:
                        self.sync['Libraries'].append("Mixed:%s" % selected if library[1] == 'mixed' else selected)

                        if library[1] in ('mixed', 'movies'):
                            self.sync['Libraries'].append('Boxsets:%s' % selected)
                    else:
                        self.sync['Libraries'].append(selected)
        else:
            if not self.mapping(forced):
                return

        self.xmls.sources()

        if not self.xmls.advanced_settings() and self.sync['Libraries']:
            self.start()

    def get_libraries(self, library_id):
        with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
            if not library_id:
                return emby_db.EmbyDatabase(embydb.cursor).get_views()

            return emby_db.EmbyDatabase(embydb.cursor).get_view(library_id)

    #Load the mapping of the full sync.
    #This allows us to restore a previous sync
    def mapping(self, forced):
        if self.sync['Libraries']:
            if not forced and not self.library.Monitor.Service.Utils.dialog("yesno", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33102)):
                if not self.library.Monitor.Service.Utils.dialog("yesno", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33173)):
                    self.library.Monitor.Service.Utils.dialog("ok", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33122))
                    self.library.SyncSkipResume = True
                    self.library.Monitor.Service.SyncPause = True
                    return False

                self.sync['Libraries'] = []
                self.sync['RestorePoint'] = {}
        else:
            self.LOG.info("generate full sync")
            libraries = []

            for library in self.get_libraries(False):
                if library[2] in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    libraries.append({'Id': library[0], 'Name': library[1], 'Media': library[2]})

            libraries = self.select_libraries(libraries)

            if not libraries:
                return False

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.sync['Libraries'].append("Boxsets:")

        database.save_sync(self.library.Monitor.Service.Utils, self.sync)
        return True

    #Select all or certain libraries to be whitelisted
    def select_libraries(self, libraries):
        if self.library.Monitor.Service.Utils.dialog("yesno", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33125), nolabel=self.library.Monitor.Service.Utils.Translate(33127), yeslabel=self.library.Monitor.Service.Utils.Translate(33126)):
            self.LOG.info("Selected sync later")
            self.library.SyncLater = True
            return False

        choices = [x['Name'] for x in libraries]
        choices.insert(0, self.library.Monitor.Service.Utils.Translate(33121))
        selection = self.library.Monitor.Service.Utils.dialog("multi", self.library.Monitor.Service.Utils.Translate(33120), choices)

        if selection is None:
            return False

        if not selection:
            self.LOG.info("Nothing was selected")
            self.library.SyncLater = True
            return False

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:
            library = libraries[x - 1]

            if library['Media'] != 'mixed':
                selected_libraries.append(library['Id'])
            else:
                selected_libraries.append("Mixed:%s" % library['Id'])

        self.sync['Libraries'] = selected_libraries
        return [libraries[x - 1] for x in selection]

    #Main sync process
    def start(self):
        self.LOG.info("starting sync with %s" % self.sync['Libraries'])
        database.save_sync(self.library.Monitor.Service.Utils, self.sync)
        start_time = datetime.datetime.now()

        for library in list(self.sync['Libraries']):
            if not self.process_library(library):
                return

            if not library.startswith('Boxsets:') and library not in self.sync['Whitelist']:
                self.sync['Whitelist'].append(library)

            self.sync['Libraries'].pop(self.sync['Libraries'].index(library))
            self._restore_point({})

        elapsed = datetime.datetime.now() - start_time
        self.library.Monitor.Service.Utils.settings('SyncInstallRunDone.bool', True)
        self.library.save_last_sync()
        database.save_sync(self.library.Monitor.Service.Utils, self.sync)
        xbmc.executebuiltin('UpdateLibrary(video)')
        self.library.Monitor.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.library.Monitor.Service.Utils.Translate(33025), str(elapsed).split('.')[0]), icon="{emby}", sound=False)
        self.LOG.info("Full sync completed in: %s" % str(elapsed).split('.')[0])

    #Add a library by it's id. Create a node and a playlist whenever appropriate
    def process_library(self, library_id):
        media = {
            'movies': self.movies,
            'musicvideos': self.musicvideos,
            'tvshows': self.tvshows,
            'music': self.music
        }

        if library_id.startswith('Boxsets:'):
            if library_id.endswith('Refresh'):
                self.refresh_boxsets()
            else:
                self.boxsets(library_id.split('Boxsets:')[1] if len(library_id) > len('Boxsets:') else None)

            return True

        library = self.library.server['api'].get_item(library_id.replace('Mixed:', ""))

        if library_id.startswith('Mixed:'):
            for mixed in ('movies', 'tvshows'):
                media[mixed](library, self.library.Monitor.Downloader)
                self.sync['RestorePoint'] = {}
        else:
            if library['CollectionType']:
                self.library.Monitor.Service.Utils.settings('enableMusic.bool', True)

            media[library['CollectionType']](library, self.library.Monitor.Downloader)

        if self.library.Monitor.Service.SyncPause:
            database.save_sync(self.library.Monitor.Service.Utils, self.sync)
            return False

        return True

    #Process movies from a single library
    def movies(self, library, Downloader):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Movies"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.library.server, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "Movie", self.library.server_id)

                    for items in Downloader.get_items(library['Id'], "Movie", False, self.sync['RestorePoint'].get('params'), self.library.server_id):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, movie in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=movie['Name'])
                            MoviesObject.movie(movie, library=library)

                            if self.library.Monitor.Service.SyncPause:
                                dialog.close()
                                return

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])
                        current = MoviesObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'Movie':
                                MoviesObject.remove(x[0])

        dialog.close()

    #Process tvshows and episodes from a single library
    def tvshows(self, library, Downloader):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "TV Shows"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    TVShowsObject = self.library.MEDIA['TVShow'](self.library.server, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id, True)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "Series", self.library.server_id)

                    for items in Downloader.get_items(library['Id'], "Series", False, self.sync['RestorePoint'].get('params'), self.library.server_id):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, show in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords)*100)
                            dialog.update(percent, heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=show['Name'])

                            if TVShowsObject.tvshow(show, library, None, False):
                                for episodes in Downloader.get_episode_by_show(show['Id'], self.library.server_id):
                                    for episode in episodes['Items']:
                                        dialog.update(percent, message="%s/%s" % (show['Name'], episode['Name'][:10]))
                                        TVShowsObject.episode(episode, library=library)

                                        if self.library.Monitor.Service.SyncPause:
                                            dialog.close()
                                            return

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])

                        for x in list(items):
                            items.extend(TVShowsObject.get_child(x[0]))

                        current = TVShowsObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'Series':
                                TVShowsObject.remove(x[0])

        dialog.close()

    #Process musicvideos from a single library
    def musicvideos(self, library, Downloader):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Musicvideos"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MusicVideosObject = self.library.MEDIA['MusicVideo'](self.library.server, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "MusicVideo", self.library.server_id)

                    for items in Downloader.get_items(library['Id'], "MusicVideo", False, self.sync['RestorePoint'].get('params'), self.library.server_id):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, mvideo in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=mvideo['Name'])
                            MusicVideosObject.musicvideo(mvideo, library=library)

                            if self.library.Monitor.Service.SyncPause:
                                dialog.close()
                                return

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])
                        current = MusicVideosObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'MusicVideo':
                                MusicVideosObject.remove(x[0])

        dialog.close()

    #Process artists, album, songs from a single library
    def music(self, library, Downloader):
        self.patch_music(True)
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Music"))

        with self.library.music_database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'music', True) as musicdb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MusicObject = self.library.MEDIA['Music'](self.library.server, embydb, musicdb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)
                    TotalRecords = Downloader.get_TotalRecordsArtists(library['Id'], self.library.server_id)

                    for items in Downloader.get_artists(library['Id'], False, self.sync['RestorePoint'].get('params'), self.library.server_id):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, artist in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords) * 100)
                            dialog.update(percent, heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=artist['Name'])
                            MusicObject.artist(artist, library=library)

                            for albums in Downloader.get_albums_by_artist(library['Id'], artist['Id'], False, self.library.server_id):
                                for album in albums['Items']:
                                    MusicObject.album(album, library=library)

                                    if self.library.Monitor.Service.SyncPause:
                                        dialog.close()
                                        return

                            for songs in Downloader.get_songs_by_artist(library['Id'], artist['Id'], False, self.library.server_id):
                                for song in songs['Items']:
                                    MusicObject.song(song, library=library)

                                    if self.library.Monitor.Service.SyncPause:
                                        dialog.close()
                                        return

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])

                        for x in list(items):
                            items.extend(MusicObject.get_child(x[0]))

                        current = MusicObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'MusicArtist':
                                MusicObject.remove(x[0])

        dialog.close()

    #Process all boxsets
    def boxsets(self, library_id):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Boxsets"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.library.server, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)
                    TotalRecords = self.library.Monitor.Downloader.get_TotalRecordsRegular(library_id, "BoxSet", self.library.server_id)

                    for items in self.library.Monitor.Downloader.get_items(library_id, "BoxSet", False, self.sync['RestorePoint'].get('params'), self.library.server_id):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, boxset in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), self.library.Monitor.Service.Utils.Translate('boxsets')), message=boxset['Name'])
                            MoviesObject.boxset(boxset)

                            if self.library.Monitor.Service.SyncPause:
                                dialog.close()
                                return

        dialog.close()

    #Delete all exisitng boxsets and re-add
    def refresh_boxsets(self):
        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.library.server, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id)
                    MoviesObject.boxsets_reset()

        self.boxsets(None)

    #Patch the music database to silence the rescan prompt
    def patch_music(self, notification):
        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'music', True) as musicdb:
                self.library.MEDIA['MusicDisableScan'](musicdb.cursor, int(self.library.Monitor.Service.Utils.window('kodidbversion.music'))).disable_rescan()

        self.library.Monitor.Service.Utils.settings('MusicRescan.bool', True)

        if notification:
            self.library.Monitor.Service.Utils.dialog("notification", heading="{emby}", message=self.library.Monitor.Service.Utils.Translate('task_success'), icon="{emby}", time=1000, sound=False)

    #Remove library by their id from the Kodi database
    def remove_library(self, library_id):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'))
        direct_path = self.library.direct_path

        with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
            db = emby_db.EmbyDatabase(embydb.cursor)
            library = db.get_view(library_id.replace('Mixed:', ""))
            items = db.get_item_by_media_folder(library_id.replace('Mixed:', ""))
            media = 'music' if library[1] == 'music' else 'video'

            if items:
                count = 0

                with self.library.music_database_lock if media == 'music' else self.library.database_lock:
                    with database.Database(self.library.Monitor.Service.Utils, media, True) as kodidb:
                        if library[1] == 'mixed':
                            movies = [x for x in items if x[1] == 'Movie']
                            tvshows = [x for x in items if x[1] == 'Series']
                            MediaObject = self.library.MEDIA['Movie'](self.library.server, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id).remove

                            for item in movies:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1

                            MediaObject = self.library.MEDIA['Series'](self.library.server, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id).remove

                            for item in tvshows:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1
                        else:
                            MediaObject = self.library.MEDIA[items[0][1]](self.library.server, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Monitor.Downloader, self.library.server_id).remove

                            for item in items:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1

        dialog.close()
        self.sync = database.get_sync(self.library.Monitor.Service.Utils)

        if library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove(library_id)
        elif 'Mixed:%s' % library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove('Mixed:%s' % library_id)

        database.save_sync(self.library.Monitor.Service.Utils, self.sync)

    #Exiting sync
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        self.SyncInProgress = False

        if self.screensaver is not None:
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            self.library.Monitor.Service.Utils.set_screensaver(value=self.screensaver)
            self.screensaver = None

        self.LOG.info("--<[ fullsync ]")

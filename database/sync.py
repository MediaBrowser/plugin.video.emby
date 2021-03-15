# -*- coding: utf-8 -*-
import datetime
import logging
import xbmc

import helper.translate
import helper.wrapper
import helper.exceptions
import helper.xmls
from . import database
from . import emby_db

class Sync():
    running = False

    def __init__(self, library, server, Downloader, Utils):
        self.LOG = logging.getLogger("EMBY.sync")
        self.sync = None
#        self.running = False
        self.screensaver = None
        self.update_library = False
        self.Downloader = Downloader
        self.Utils = Utils
        self.xmls = helper.xmls.Xmls(self.Utils)
        self.direct_path = self.Utils.settings('useDirectPaths') == "1"

        if self.running:
            self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33197))
            raise Exception("Sync is already running.")

        self.library = library
        self.server = server

    #Do everything we need before the sync
    def __enter__(self):
        self.LOG.info("-->[ fullsync ]")

        if not self.Utils.settings('dbSyncScreensaver.bool'):
            xbmc.executebuiltin('InhibitIdleShutdown(true)')
            self.screensaver = self.Utils.get_screensaver()
            self.Utils.set_screensaver(value="")

        self.running = True
        self.Utils.window('emby_sync.bool', True)
        return self

    #Assign the restore point and save the sync status
    def _restore_point(self, restore):
        self.sync['RestorePoint'] = restore
        database.save_sync(self.sync)

    #Map the syncing process and start the sync. Ensure only one sync is running
    #force to resume any previous sync
    def libraries(self, library_id=None, update=False, forced=False):
        self.update_library = update
        self.sync = database.get_sync()

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
            self.mapping(forced)

        self.xmls.sources()

        if not self.xmls.advanced_settings() and self.sync['Libraries']:
            self.start()

    def get_libraries(self, library_id=None):
        with database.Database('emby') as embydb:
            if library_id is None:
                return emby_db.EmbyDatabase(embydb.cursor).get_views()

            return emby_db.EmbyDatabase(embydb.cursor).get_view(library_id)

    #Load the mapping of the full sync.
    #This allows us to restore a previous sync
    def mapping(self, forced=False):
        if self.sync['Libraries']:
            if not forced and not self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33102)):
                if not self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33173)):
                    self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33122))
                    self.Utils.window('emby_sync_skip_resume.bool', True)
                    raise helper.exceptions.LibraryException("StopWriteCalled")

                self.sync['Libraries'] = []
                self.sync['RestorePoint'] = {}
        else:
            self.LOG.info("generate full sync")
            libraries = []

            for library in self.get_libraries():
                if library[2] in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    libraries.append({'Id': library[0], 'Name': library[1], 'Media': library[2]})

            libraries = self.select_libraries(libraries)

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.sync['Libraries'].append("Boxsets:")

        database.save_sync(self.sync)

    #Select all or certain libraries to be whitelisted
    def select_libraries(self, libraries):
        if self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33125), nolabel=helper.translate._(33127), yeslabel=helper.translate._(33126)):
            self.LOG.info("Selected sync later.")
            raise helper.exceptions.LibraryException('SyncLibraryLater')

        choices = [x['Name'] for x in libraries]
        choices.insert(0, helper.translate._(33121))
        selection = self.Utils.dialog("multi", helper.translate._(33120), choices)

        if selection is None:
            raise helper.exceptions.LibraryException('LibrarySelection')

        if not selection:
            self.LOG.info("Nothing was selected.")
            raise helper.exceptions.LibraryException('SyncLibraryLater')

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
        self.LOG.info("starting sync with %s", self.sync['Libraries'])
        database.save_sync(self.sync)
        start_time = datetime.datetime.now()

        for library in list(self.sync['Libraries']):
            self.process_library(library)

            if not library.startswith('Boxsets:') and library not in self.sync['Whitelist']:
                self.sync['Whitelist'].append(library)

            self.sync['Libraries'].pop(self.sync['Libraries'].index(library))
            self._restore_point({})

        elapsed = datetime.datetime.now() - start_time
        self.Utils.settings('SyncInstallRunDone.bool', True)
        self.library.save_last_sync()
        database.save_sync(self.sync)
        xbmc.executebuiltin('UpdateLibrary(video)')
        self.Utils.dialog("notification", heading="{emby}", message="%s %s" % (helper.translate._(33025), str(elapsed).split('.')[0]), icon="{emby}", sound=False)
        self.LOG.info("Full sync completed in: %s", str(elapsed).split('.')[0])

    #Add a library by it's id. Create a node and a playlist whenever appropriate
    def process_library(self, library_id):
        media = {
            'movies': self.movies,
            'musicvideos': self.musicvideos,
            'tvshows': self.tvshows,
            'music': self.music
        }

        try:
            if library_id.startswith('Boxsets:'):
                if library_id.endswith('Refresh'):
                    self.refresh_boxsets()
                else:
                    self.boxsets(library_id.split('Boxsets:')[1] if len(library_id) > len('Boxsets:') else None)

                return

            library = self.server['api'].get_item(library_id.replace('Mixed:', ""))

            if library_id.startswith('Mixed:'):
                for mixed in ('movies', 'tvshows'):
                    media[mixed](library, self.Downloader)
                    self.sync['RestorePoint'] = {}
            else:
                if library['CollectionType']:
                    self.Utils.settings('enableMusic.bool', True)

                media[library['CollectionType']](library, self.Downloader)
        except helper.exceptions.LibraryException as error:
            if error.status in ('StopCalled', 'StopWriteCalled'):
                database.save_sync(self.sync)
                raise
        except Exception as error:
            if 'Failed to validate path' not in error.args:
                self.Utils.dialog("ok", heading="{emby}", line1=helper.translate._(33119))
                self.LOG.error("full sync exited unexpectedly")
                database.save_sync(self.sync)

            raise

    #Process movies from a single library
    @helper.wrapper.progress()
    def movies(self, library, Downloader, dialog):
        with self.library.database_lock:
            with database.Database() as videodb:
                with database.Database('emby') as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.server, embydb, videodb, self.direct_path, self.Utils)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "Movie")

                    for items in Downloader.get_items(library['Id'], "Movie", False, self.sync['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, movie in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (helper.translate._('addon_name'), library['Name']), message=movie['Name'])
                            MoviesObject.movie(movie, library=library)

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])
                        current = MoviesObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'Movie':
                                MoviesObject.remove(x[0])

    #Process tvshows and episodes from a single library
    @helper.wrapper.progress()
    def tvshows(self, library, Downloader, dialog):
        with self.library.database_lock:
            with database.Database() as videodb:
                with database.Database('emby') as embydb:
                    TVShowsObject = self.library.MEDIA['TVShow'](self.server, embydb, videodb, self.direct_path, self.Utils, True)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "Series")

                    for items in Downloader.get_items(library['Id'], "Series", False, self.sync['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, show in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords)*100)
                            dialog.update(percent, heading="%s: %s" % (helper.translate._('addon_name'), library['Name']), message=show['Name'])

                            if TVShowsObject.tvshow(show, library=library):
                                for episodes in Downloader.get_episode_by_show(show['Id']):
                                    for episode in episodes['Items']:
                                        dialog.update(percent, message="%s/%s" % (show['Name'], episode['Name'][:10]))
                                        TVShowsObject.episode(episode, library=library)

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])

                        for x in list(items):
                            items.extend(TVShowsObject.get_child(x[0]))

                        current = TVShowsObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'Series':
                                TVShowsObject.remove(x[0])

    #Process musicvideos from a single library
    @helper.wrapper.progress()
    def musicvideos(self, library, Downloader, dialog):
        with self.library.database_lock:
            with database.Database() as videodb:
                with database.Database('emby') as embydb:
                    MusicVideosObject = self.library.MEDIA['MusicVideo'](self.server, embydb, videodb, self.direct_path, self.Utils)
                    TotalRecords = Downloader.get_TotalRecordsRegular(library['Id'], "MusicVideo")

                    for items in Downloader.get_items(library['Id'], "MusicVideo", False, self.sync['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, mvideo in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (helper.translate._('addon_name'), library['Name']), message=mvideo['Name'])
                            MusicVideosObject.musicvideo(mvideo, library=library)

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])
                        current = MusicVideosObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'MusicVideo':
                                MusicVideosObject.remove(x[0])

    #Process artists, album, songs from a single library
    @helper.wrapper.progress()
    def music(self, library, Downloader, dialog):
        self.patch_music()

        with self.library.music_database_lock:
            with database.Database('music') as musicdb:
                with database.Database('emby') as embydb:
                    MusicObject = self.library.MEDIA['Music'](self.server, embydb, musicdb, self.direct_path, self.Utils)
                    TotalRecords = Downloader.get_TotalRecordsArtists(library['Id'])

                    for items in Downloader.get_artists(library['Id'], False, self.sync['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, artist in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords) * 100)
                            dialog.update(percent, heading="%s: %s" % (helper.translate._('addon_name'), library['Name']), message=artist['Name'])
                            MusicObject.artist(artist, library=library)

                            for albums in Downloader.get_albums_by_artist(library['Id'], artist['Id']):
                                for album in albums['Items']:
                                    MusicObject.album(album, library=library)

                            for songs in Downloader.get_songs_by_artist(library['Id'], artist['Id']):
                                for song in songs['Items']:
                                    MusicObject.song(song, library=library)

                    #Compare entries from library to what's in the embydb. Remove surplus
                    if self.update_library:
                        items = emby_db.EmbyDatabase(embydb.cursor).get_item_by_media_folder(library['Id'])

                        for x in list(items):
                            items.extend(MusicObject.get_child(x[0]))

                        current = MusicObject.item_ids

                        for x in items:
                            if x[0] not in current and x[1] == 'MusicArtist':
                                MusicObject.remove(x[0])

    #Process all boxsets
    @helper.wrapper.progress(helper.translate._(33018))
    def boxsets(self, library_id=None, dialog=None):
        with self.library.database_lock:
            with database.Database() as videodb:
                with database.Database('emby') as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.server, embydb, videodb, self.direct_path, self.Utils)
                    TotalRecords = self.Downloader.get_TotalRecordsRegular(library_id, "BoxSet")

                    for items in self.Downloader.get_items(library_id, "BoxSet", False, self.sync['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, boxset in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (helper.translate._('addon_name'), helper.translate._('boxsets')), message=boxset['Name'])
                            MoviesObject.boxset(boxset)

    #Delete all exisitng boxsets and re-add
    def refresh_boxsets(self):
        with self.library.database_lock:
            with database.Database() as videodb:
                with database.Database('emby') as embydb:
                    MoviesObject = self.library.MEDIA['Movie'](self.server, embydb, videodb, self.direct_path, self.Utils)
                    MoviesObject.boxsets_reset()

        self.boxsets(None)

    #Patch the music database to silence the rescan prompt
    def patch_music(self, notification=False):
        with self.library.database_lock:
            with database.Database('music') as musicdb:
                self.library.MEDIA['MusicDisableScan'](musicdb.cursor, int(self.Utils.window('kodidbverion.music'))).disable_rescan()

        self.Utils.settings('MusicRescan.bool', True)

        if notification:
            self.Utils.dialog("notification", heading="{emby}", message=helper.translate._('task_success'), icon="{emby}", time=1000, sound=False)

    #Remove library by their id from the Kodi database
    @helper.wrapper.progress(helper.translate._(33144))
    def remove_library(self, library_id, dialog=None):
        direct_path = self.library.direct_path

        with database.Database('emby') as embydb:
            db = emby_db.EmbyDatabase(embydb.cursor)
            library = db.get_view(library_id.replace('Mixed:', ""))
            items = db.get_item_by_media_folder(library_id.replace('Mixed:', ""))
            media = 'music' if library[1] == 'music' else 'video'

            if items:
                count = 0

                with self.library.music_database_lock if media == 'music' else self.library.database_lock:
                    with database.Database(media) as kodidb:
                        if library[1] == 'mixed':
                            movies = [x for x in items if x[1] == 'Movie']
                            tvshows = [x for x in items if x[1] == 'Series']
                            MediaObject = self.library.MEDIA['Movie'](self.server, embydb, kodidb, direct_path, self.Utils).remove

                            for item in movies:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (helper.translate._('addon_name'), library[0]))
                                count += 1

                            MediaObject = self.library.MEDIA['Series'](self.server, embydb, kodidb, direct_path, self.Utils).remove

                            for item in tvshows:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (helper.translate._('addon_name'), library[0]))
                                count += 1
                        else:
                            MediaObject = self.library.MEDIA[items[0][1]](self.server, embydb, kodidb, direct_path, self.Utils).remove

                            for item in items:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (helper.translate._('addon_name'), library[0]))
                                count += 1

        self.sync = database.get_sync()

        if library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove(library_id)
        elif 'Mixed:%s' % library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove('Mixed:%s' % library_id)

        database.save_sync(self.sync)

    #Exiting sync
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        self.Utils.window('emby_sync', clear=True)

        if self.screensaver is not None:
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            self.Utils.set_screensaver(value=self.screensaver)
            self.screensaver = None

        self.LOG.info("--<[ fullsync ]")

# -*- coding: utf-8 -*-
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

import xbmc
import xbmcgui

import core.movies
import core.musicvideos
import core.tvshows
import core.music
import helper.xmls
import helper.loghandler
from . import database
from . import emby_db

class Sync():
    def __init__(self, library):
        self.LOG = helper.loghandler.LOG('EMBY.database.sync')
        self.library = library
        self.SyncData = {}
        self.running = False
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
        self.SyncData['RestorePoint'] = restore
        self.library.Monitor.Service.Utils.save_sync(self.SyncData, False)

    #Map the syncing process and start the sync. Ensure only one sync is running
    #force to resume any previous sync
    def libraries(self, library_id, update, forced):
        self.update_library = update
        self.SyncData = self.library.Monitor.Service.Utils.get_sync()

        if library_id:
            libraries = library_id.split(',')

            for selected in libraries:
                if selected not in [x.replace('Mixed:', "") for x in self.SyncData['Libraries']]:
                    library = self.get_libraries(selected)

                    if library:
                        self.SyncData['Libraries'].append("Mixed:%s" % selected if library[1] == 'mixed' else selected)

                        if library[1] in ('mixed', 'movies'):
                            self.SyncData['Libraries'].append('Boxsets:%s' % selected)
                    else:
                        self.SyncData['Libraries'].append(selected)
        else:
            if not self.mapping(forced):
                return

        self.xmls.sources()

        if not self.xmls.advanced_settings() and self.SyncData['Libraries']:
            self.start()

    def get_libraries(self, library_id):
        with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
            if not library_id:
                return emby_db.EmbyDatabase(embydb.cursor).get_views()

            return emby_db.EmbyDatabase(embydb.cursor).get_view(library_id)

    #Load the mapping of the full sync.
    #This allows us to restore a previous sync
    def mapping(self, forced):
        if self.SyncData['Libraries']:
            if not forced and not self.library.Monitor.Service.Utils.dialog("yesno", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33102)):
                if not self.library.Monitor.Service.Utils.dialog("yesno", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33173)):
                    self.library.Monitor.Service.Utils.dialog("ok", heading="{emby}", line1=self.library.Monitor.Service.Utils.Translate(33122))
                    self.library.SyncSkipResume = True
                    self.library.Monitor.Service.SyncPause = True
                    return False

                self.SyncData['Libraries'] = []
                self.SyncData['RestorePoint'] = {}
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
                self.SyncData['Libraries'].append("Boxsets:")

        self.library.Monitor.Service.Utils.save_sync(self.SyncData, True)
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

        self.SyncData['Libraries'] = selected_libraries
        return [libraries[x - 1] for x in selection]

    #Main sync process
    def start(self):
        self.LOG.info("starting sync with %s" % self.SyncData['Libraries'])
        self.library.Monitor.Service.Utils.save_sync(self.SyncData, True)
        start_time = datetime.datetime.now()

        for library in list(self.SyncData['Libraries']):
            if not self.process_library(library):
                return

            if not library.startswith('Boxsets:') and library not in self.SyncData['Whitelist']:
                self.SyncData['Whitelist'].append(library)

            self.SyncData['Libraries'].pop(self.SyncData['Libraries'].index(library))
            self._restore_point({})

        elapsed = datetime.datetime.now() - start_time
        self.library.Monitor.Service.Utils.settings('SyncInstallRunDone.bool', True)
        self.library.save_last_sync()
        self.library.Monitor.Service.Utils.save_sync(self.SyncData, True)
        xbmc.executebuiltin('UpdateLibrary(video)')
        self.library.Monitor.Service.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.library.Monitor.Service.Utils.Translate(33025), str(elapsed).split('.')[0]), icon="{emby}", sound=False)
        self.LOG.info("Full sync completed in: %s" % str(elapsed).split('.')[0])

    #Add a library by it's id. Create a node and a playlist whenever appropriate
    def process_library(self, library_id):
        if library_id.startswith('Boxsets:'):
            if library_id.endswith('Refresh'):
                self.refresh_boxsets()
            else:
                self.boxsets(library_id.split('Boxsets:')[1] if len(library_id) > len('Boxsets:') else None)

            return True

        library = self.library.EmbyServer.API.get_item(library_id.replace('Mixed:', ""))

        if library_id.startswith('Mixed:'):
            self.movies(library)
            self.SyncData['RestorePoint'] = {}
            self.tvshows(library)
            self.SyncData['RestorePoint'] = {}
        else:
            if library['CollectionType'] == 'movies':
                self.movies(library)
            elif library['CollectionType'] == 'musicvideos':
                self.musicvideos(library)
            elif library['CollectionType'] == 'tvshows':
                self.tvshows(library)
            elif library['CollectionType'] == 'music':
                self.library.Monitor.Service.Utils.settings('enableMusic.bool', True)
                self.music(library)

        if self.library.Monitor.Service.SyncPause:
            self.library.Monitor.Service.Utils.save_sync(self.SyncData, True)
            return False

        return True

    #Process movies from a single library
    def movies(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Movies"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MoviesObject = core.movies.Movies(self.library.EmbyServer, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Downloader)
                    TotalRecords = self.library.Downloader.get_TotalRecordsRegular(library['Id'], "Movie")

                    for items in self.library.Downloader.get_items(library['Id'], "Movie", False, self.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, movie in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=movie['Name'])
                            MoviesObject.movie(movie, library)

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
    def tvshows(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "TV Shows"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    TVShowsObject = core.tvshows.TVShows(self.library.EmbyServer, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Downloader, True)
                    TotalRecords = self.library.Downloader.get_TotalRecordsRegular(library['Id'], "Series")

                    for items in self.library.Downloader.get_items(library['Id'], "Series", False, self.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, show in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords)*100)
                            dialog.update(percent, heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=show['Name'])

                            if TVShowsObject.tvshow(show, library, None, None):
                                for episodes in self.library.Downloader.get_episode_by_show(show['Id']):
                                    for episode in episodes['Items']:
                                        dialog.update(percent, message="%s/%s" % (show['Name'], episode['Name'][:10]))
                                        TVShowsObject.episode(episode, library)

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
    def musicvideos(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Musicvideos"))

        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'video', True) as videodb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MusicVideosObject = core.musicvideos.MusicVideos(self.library.EmbyServer, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils)
                    TotalRecords = self.library.Downloader.get_TotalRecordsRegular(library['Id'], "MusicVideo")

                    for items in self.library.Downloader.get_items(library['Id'], "MusicVideo", False, self.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, mvideo in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=mvideo['Name'])
                            MusicVideosObject.musicvideo(mvideo, library)

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
    def music(self, library):
        self.patch_music(True)
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.library.Monitor.Service.Utils.Translate('addon_name'), "%s %s" % (self.library.Monitor.Service.Utils.Translate('gathering'), "Music"))

        with self.library.music_database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'music', True) as musicdb:
                with database.Database(self.library.Monitor.Service.Utils, 'emby', True) as embydb:
                    MusicObject = core.music.Music(self.library.EmbyServer, embydb, musicdb, self.direct_path, self.library.Monitor.Service.Utils)
                    TotalRecords = self.library.Downloader.get_TotalRecordsArtists(library['Id'])

                    for items in self.library.Downloader.get_artists(library['Id'], False, self.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, artist in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords) * 100)
                            dialog.update(percent, heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library['Name']), message=artist['Name'])
                            MusicObject.artist(artist, library)

                            for albums in self.library.Downloader.get_albums_by_artist(library['Id'], artist['Id'], False):
                                for album in albums['Items']:
                                    MusicObject.album(album, library)

                                    if self.library.Monitor.Service.SyncPause:
                                        dialog.close()
                                        return

                            for songs in self.library.Downloader.get_songs_by_artist(library['Id'], artist['Id'], False):
                                for song in songs['Items']:
                                    MusicObject.song(song, library)

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
                    MoviesObject = core.movies.Movies(self.library.EmbyServer, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Downloader)
                    TotalRecords = self.library.Downloader.get_TotalRecordsRegular(library_id, "BoxSet")

                    for items in self.library.Downloader.get_items(library_id, "BoxSet", False, self.SyncData['RestorePoint'].get('params')):
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
                    MoviesObject = core.movies.Movies(self.library.EmbyServer, embydb, videodb, self.direct_path, self.library.Monitor.Service.Utils, self.library.Downloader)
                    MoviesObject.boxsets_reset()

        self.boxsets(None)

    #Patch the music database to silence the rescan prompt
    def patch_music(self, notification):
        with self.library.database_lock:
            with database.Database(self.library.Monitor.Service.Utils, 'music', True) as musicdb:
                core.music.MusicDBIO(musicdb.cursor, int(self.library.Monitor.Service.Utils.window('kodidbversion.music'))).disable_rescan()

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
                            MediaObject = core.movies.Movies(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Downloader).remove

                            for item in movies:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1

                            MediaObject = core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Downloader).remove

                            for item in tvshows:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1
                        else:
                            if items[0][1] in ('Movie', 'BoxSet'):
                                MediaObject = core.movies.Movies(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Downloader).remove
                            if items[0][1] == 'MusicVideo':
                                MediaObject = core.musicvideos.MusicVideos(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils).remove
                            if items[0][1] in ('TVShow', 'Series', 'Season', 'Episode'):
                                MediaObject = core.tvshows.TVShows(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils, self.library.Downloader).remove
                            if items[0][1] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                                MediaObject = core.music.Music(self.library.EmbyServer, embydb, kodidb, direct_path, self.library.Monitor.Service.Utils).remove

                            for item in items:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.library.Monitor.Service.Utils.Translate('addon_name'), library[0]))
                                count += 1

        dialog.close()
        self.SyncData = self.library.Monitor.Service.Utils.get_sync()

        if library_id in self.SyncData['Whitelist']:
            self.SyncData['Whitelist'].remove(library_id)
        elif 'Mixed:%s' % library_id in self.SyncData['Whitelist']:
            self.SyncData['Whitelist'].remove('Mixed:%s' % library_id)

        self.library.Monitor.Service.Utils.save_sync(self.SyncData, True)

    #Exiting sync
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        self.SyncInProgress = False

        if self.screensaver is not None:
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            self.library.Monitor.Service.Utils.set_screensaver(value=self.screensaver)
            self.screensaver = None

        self.LOG.info("--<[ fullsync ]")

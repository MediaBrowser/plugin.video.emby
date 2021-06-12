# -*- coding: utf-8 -*-
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

import xbmc
import xbmcgui

import core.movies
import core.musicvideos
import core.tvshows
import core.music
import helper.loghandler
from . import database
from . import emby_db

class Sync():
    def __init__(self, EmbyServer, Player, ThreadingLock):
        self.LOG = helper.loghandler.LOG('EMBY.database.sync')
        self.EmbyServer = EmbyServer
        self.Player = Player
        self.ThreadingLock = ThreadingLock
        self.running = False
        self.screensaver = None
        self.update_library = False

        if self.running:
            self.EmbyServer.Utils.dialog("ok", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33197))
            return

    #Assign the restore point and save the sync status
    def _restore_point(self, restore):
        self.EmbyServer.Utils.SyncData['RestorePoint'] = restore
        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, False)

    #Load the mapping of the full sync.
    #This allows us to restore a previous sync
    def mapping(self, forced):
        if self.EmbyServer.Utils.SyncData['Libraries']:
            if not forced and not self.EmbyServer.Utils.dialog("yesno", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33102)):
                if not self.EmbyServer.Utils.dialog("yesno", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33173)):
                    self.EmbyServer.Utils.dialog("ok", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33122))
                    self.Player.SyncPause = True
                    return False

                self.EmbyServer.Utils.SyncData['Libraries'] = []
                self.EmbyServer.Utils.SyncData['RestorePoint'] = {}
        else:
            self.LOG.info("generate full sync")
            libraries = []

            with database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
                libraries_DB = emby_db.EmbyDatabase(embydb.cursor).get_views()

            for library in libraries_DB:

                if library[2] in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    libraries.append({'Id': library[0], 'Name': library[1], 'Media': library[2]})

            if self.EmbyServer.Utils.dialog("yesno", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33125), nolabel=self.EmbyServer.Utils.Translate(33127), yeslabel=self.EmbyServer.Utils.Translate(33126)):
                self.LOG.info("Selected sync later")
                return False

            choices = [x['Name'] for x in libraries]
            choices.insert(0, self.EmbyServer.Utils.Translate(33121))
            selection = self.EmbyServer.Utils.dialog("multi", self.EmbyServer.Utils.Translate(33120), choices)

            if selection is None:
                return False

            if not selection:
                self.LOG.info("Nothing was selected")
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

            self.EmbyServer.Utils.SyncData['Libraries'] = selected_libraries
            libraries = [libraries[x - 1] for x in selection]

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.EmbyServer.Utils.SyncData['Libraries'].append("Boxsets:")

        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, True)
        return True

    #Main sync process
    def FullSync(self):
        self.LOG.info("-->[ starting sync with %s ]" % self.EmbyServer.Utils.SyncData['Libraries'])
        self.EmbyServer.Utils.Settings.set_settings_bool('ReloadSkin', True)

        if not self.EmbyServer.Utils.Settings.dbSyncScreensaver:
            xbmc.executebuiltin('InhibitIdleShutdown(true)')
            self.screensaver = self.EmbyServer.Utils.Screensaver
            self.EmbyServer.Utils.set_screensaver(value="")

        self.running = True
        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, True)
        start_time = datetime.datetime.now()

        for library in list(self.EmbyServer.Utils.SyncData['Libraries']):
            if not self.process_library(library):
                self.running = False
                return

            if not library.startswith('Boxsets:') and library not in self.EmbyServer.Utils.SyncData['Whitelist']:
                self.EmbyServer.Utils.SyncData['Whitelist'].append(library)

            self.EmbyServer.Utils.SyncData['Libraries'].pop(self.EmbyServer.Utils.SyncData['Libraries'].index(library))
            self._restore_point({})

        elapsed = datetime.datetime.now() - start_time
        self.EmbyServer.Utils.Settings.set_settings_bool('SyncInstallRunDone', True)
        self.EmbyServer.Utils.save_last_sync()
        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, True)
        xbmc.executebuiltin('UpdateLibrary(video)')
        self.EmbyServer.Utils.dialog("notification", heading="{emby}", message="%s %s" % (self.EmbyServer.Utils.Translate(33025), str(elapsed).split('.')[0]), icon="{emby}", sound=False)
        self.running = False

        if self.screensaver is not None:
            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            self.EmbyServer.Utils.set_screensaver(value=self.screensaver)

        xbmc.sleep(1000)
        xbmc.executebuiltin('ReloadSkin()')
        self.EmbyServer.Utils.Settings.set_settings_bool('ReloadSkin', False)
        self.LOG.info("--<[ Full sync completed in: %s ]" % str(elapsed).split('.')[0])

    def process_library(self, library_id):
        if library_id.startswith('Boxsets:'):
            if library_id.endswith('Refresh'):
                self.refresh_boxsets()
            else:
                self.boxsets(library_id.split('Boxsets:')[1] if len(library_id) > len('Boxsets:') else None)

            return True

        library = self.EmbyServer.API.get_item(library_id.replace('Mixed:', ""))

        if library_id.startswith('Mixed:'):
            self.movies(library)
            self.EmbyServer.Utils.SyncData['RestorePoint'] = {}
            self.tvshows(library)
            self.EmbyServer.Utils.SyncData['RestorePoint'] = {}
        else:
            if library['CollectionType'] == 'movies':
                self.movies(library)
            elif library['CollectionType'] == 'musicvideos':
                self.musicvideos(library)
            elif library['CollectionType'] == 'tvshows':
                self.tvshows(library)
            elif library['CollectionType'] == 'music':
                self.music(library)

        if self.Player.SyncPause:
            self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, True)
            return False

        return True

    #Process movies from a single library
    def movies(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'), "%s %s" % (self.EmbyServer.Utils.Translate('gathering'), "Movies"))

        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'video', True) as videodb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    MoviesObject = core.movies.Movies(self.EmbyServer, embydb, videodb)
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsRegular(library['Id'], "Movie")

                    for items in self.EmbyServer.API.get_itemsSync(library['Id'], "Movie", False, self.EmbyServer.Utils.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, movie in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library['Name']), message=movie['Name'])
                            MoviesObject.movie(movie, library)

                            if self.Player.SyncPause:
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

    def tvshows(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'), "%s %s" % (self.EmbyServer.Utils.Translate('gathering'), "TV Shows"))

        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'video', True) as videodb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    TVShowsObject = core.tvshows.TVShows(self.EmbyServer, embydb, videodb, True)
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsRegular(library['Id'], "Series")

                    for items in self.EmbyServer.API.get_itemsSync(library['Id'], "Series", False, self.EmbyServer.Utils.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, show in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords)*100)
                            dialog.update(percent, heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library['Name']), message=show['Name'])

                            if TVShowsObject.tvshow(show, library, None, None):
                                for episodes in self.EmbyServer.API.get_episode_by_show(show['Id']):
                                    for episode in episodes['Items']:
                                        dialog.update(percent, message="%s/%s" % (show['Name'], episode['Name'][:10]))
                                        TVShowsObject.episode(episode, library)

                                        if self.Player.SyncPause:
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

    def musicvideos(self, library):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'), "%s %s" % (self.EmbyServer.Utils.Translate('gathering'), "Musicvideos"))

        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'video', True) as videodb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    MusicVideosObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, videodb)
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsRegular(library['Id'], "MusicVideo")

                    for items in self.EmbyServer.API.get_itemsSync(library['Id'], "MusicVideo", False, self.EmbyServer.Utils.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, mvideo in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library['Name']), message=mvideo['Name'])
                            MusicVideosObject.musicvideo(mvideo, library)

                            if self.Player.SyncPause:
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

    def music(self, library):
        self.patch_music(False)
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'), "%s %s" % (self.EmbyServer.Utils.Translate('gathering'), "Music"))

        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'music', True) as musicdb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    MusicObject = core.music.Music(self.EmbyServer, embydb, musicdb)
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsArtists(library['Id'])

                    for items in self.EmbyServer.API.get_artists(library['Id'], False, self.EmbyServer.Utils.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, artist in enumerate(items['Items']):
                            percent = int((float(start_index + index) / TotalRecords) * 100)
                            dialog.update(percent, heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library['Name']), message=artist['Name'])
                            MusicObject.artist(artist, library)

                            for albums in self.EmbyServer.API.get_albums_by_artist(library['Id'], artist['Id'], False):
                                for album in albums['Items']:
                                    MusicObject.album(album, library)

                                    if self.Player.SyncPause:
                                        dialog.close()
                                        return

                            for songs in self.EmbyServer.API.get_songs_by_artist(library['Id'], artist['Id'], False):
                                for song in songs['Items']:
                                    MusicObject.song(song, library)

                                    if self.Player.SyncPause:
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

    def boxsets(self, library_id):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'), "%s %s" % (self.EmbyServer.Utils.Translate('gathering'), "Boxsets"))

        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'video', True) as videodb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    MoviesObject = core.movies.Movies(self.EmbyServer, embydb, videodb)
                    TotalRecords = self.EmbyServer.API.get_TotalRecordsRegular(library_id, "BoxSet")

                    for items in self.EmbyServer.API.get_itemsSync(library_id, "BoxSet", False, self.EmbyServer.Utils.SyncData['RestorePoint'].get('params')):
                        self._restore_point(items['RestorePoint'])
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, boxset in enumerate(items['Items']):
                            dialog.update(int((float(start_index + index) / TotalRecords) * 100), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), self.EmbyServer.Utils.Translate('boxsets')), message=boxset['Name'])
                            MoviesObject.boxset(boxset)

                            if self.Player.SyncPause:
                                dialog.close()
                                return

        dialog.close()

    #Delete all exisitng boxsets and re-add
    def refresh_boxsets(self):
        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'video', True) as videodb:
                with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
                    MoviesObject = core.movies.Movies(self.EmbyServer, embydb, videodb)
                    MoviesObject.boxsets_reset()

        self.boxsets(None)

    def patch_music(self, notification):
        with self.ThreadingLock:
            with database.Database(self.EmbyServer.Utils, 'music', True) as musicdb:
                core.music.MusicDBIO(musicdb.cursor, self.EmbyServer.Utils.DatabaseFiles['music-version']).disable_rescan()

        if notification:
            self.EmbyServer.Utils.dialog("notification", heading="{emby}", message=self.EmbyServer.Utils.Translate('task_success'), icon="{emby}", time=1000, sound=False)

    #Remove library by their id from the Kodi database
    def remove_library(self, library_id):
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(self.EmbyServer.Utils.Translate('addon_name'))

        with database.Database(self.EmbyServer.Utils, 'emby', True) as embydb:
            db = emby_db.EmbyDatabase(embydb.cursor)
            library = db.get_view(library_id.replace('Mixed:', ""))
            items = db.get_item_by_media_folder(library_id.replace('Mixed:', ""))
            media = 'music' if library[2] == 'music' else 'video'

            if items:
                count = 0

                with self.ThreadingLock:
                    with database.Database(self.EmbyServer.Utils, media, True) as kodidb:
                        if library[2] == 'mixed':
                            movies = [x for x in items if x[1] == 'Movie']
                            tvshows = [x for x in items if x[1] == 'Series']
                            MediaObject = core.movies.Movies(self.EmbyServer, embydb, kodidb).remove

                            for item in movies:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library[1]))
                                count += 1

                            MediaObject = core.tvshows.TVShows(self.EmbyServer, embydb, kodidb).remove

                            for item in tvshows:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library[1]))
                                count += 1
                        else:
                            if items[0][1] in ('Movie', 'BoxSet'):
                                MediaObject = core.movies.Movies(self.EmbyServer, embydb, kodidb).remove
                            if items[0][1] == 'MusicVideo':
                                MediaObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb).remove
                            if items[0][1] in ('TVShow', 'Series', 'Season', 'Episode'):
                                MediaObject = core.tvshows.TVShows(self.EmbyServer, embydb, kodidb).remove
                            if items[0][1] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                                MediaObject = core.music.Music(self.EmbyServer, embydb, kodidb).remove

                            for item in items:
                                MediaObject(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (self.EmbyServer.Utils.Translate('addon_name'), library[1]))
                                count += 1

        dialog.close()

        if library_id in self.EmbyServer.Utils.SyncData['Whitelist']:
            self.EmbyServer.Utils.SyncData['Whitelist'].remove(library_id)
        elif 'Mixed:%s' % library_id in self.EmbyServer.Utils.SyncData['Whitelist']:
            self.EmbyServer.Utils.SyncData['Whitelist'].remove('Mixed:%s' % library_id)

        self.EmbyServer.Utils.save_sync(self.EmbyServer.Utils.SyncData, True)

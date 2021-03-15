# -*- coding: utf-8 -*-
import os
import threading
import requests

try:
    from urllib import urlencode
except:
    from urllib.parse import urlencode

import xbmcgui
import xbmcvfs

import database.database
import helper.loghandler
from . import queries_videos
from . import queries_music
from . import queries_texture

class Artwork():
    def __init__(self, cursor, Utils):
        if cursor:
            cursor.execute("PRAGMA database_list;")
            self.is_music = 'MyMusic' in cursor.fetchall()[0][2]

        self.LOG = helper.loghandler.LOG('EMBY.core.artwork.Artwork')
        self.Utils = Utils
        self.cursor = cursor
        self.threads = []
        self.CacheAllEntriesThread = None

    #Update artwork in the video database.
    #Only cache artwork if it changed for the main backdrop, poster.
    #Delete current entry before updating with the new one.
    #Cache fanart and poster in Kodi texture cache.
    def update(self, image_url, kodi_id, media, image):
        if image == 'poster' and media in ('song', 'artist', 'album'):
            return

        try:
            self.cursor.execute(queries_videos.get_art, (kodi_id, media, image,))
            url = self.cursor.fetchone()[0]
        except TypeError:
            self.LOG.debug("ADD to kodi_id %s art: %s" % (kodi_id, image_url))
            self.cursor.execute(queries_videos.add_art, (kodi_id, media, image, image_url))
        else:
            if url != image_url:
                self.delete_cache(url)

                if not image_url:
                    return

                self.LOG.info("UPDATE to kodi_id %s art: %s" % (kodi_id, image_url))
                self.cursor.execute(queries_videos.update_art, (image_url, kodi_id, media, image))

    #Add all artworks
    def add(self, artwork, *args):
        KODI = {
            'Primary': ['thumb', 'poster'],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart"
        }

        for art in KODI:
            if art == 'Backdrop':
                num_backdrops = len(artwork['Backdrop'])
                self.cursor.execute(queries_videos.get_backdrops, args + ("fanart%",))

                if len(self.cursor.fetchall()) > num_backdrops:
                    self.cursor.execute(queries_videos.delete_backdrops, args + ("fanart_",))

                self.update(*(artwork['Backdrop'][0] if num_backdrops else "",) + args + ("fanart",))

                for index, backdrop in enumerate(artwork['Backdrop'][1:]):
                    self.update(*(backdrop,) + args + ("%s%s" % ("fanart", index + 1),))
            elif art == 'Primary':
                for kodi_image in KODI['Primary']:
                    self.update(*(artwork['Primary'],) + args + (kodi_image,))
            else:
                self.update(*(artwork[art],) + args + (KODI[art],))

    #Delete artwork from kodi database and remove cache for backdrop/posters
    def delete(self, *args):
        self.cursor.execute(queries_videos.get_art_url, args)

        for row in self.cursor.fetchall():
            self.delete_cache(row[0])

    #Delete cached artwork
    def delete_cache(self, url):
        with database.database.Database(self.Utils, 'texture', True) as texturedb:
            cursor = texturedb.cursor

            try:
                cursor.execute(queries_texture.get_cache, (url,))
                cached = cursor.fetchone()[0]
            except TypeError:
                self.LOG.debug("Could not find cached url: %s" % url)
            else:
                thumbnails = self.Utils.translatePath("special://thumbnails/%s" % cached)
                xbmcvfs.delete(thumbnails)
                cursor.execute(queries_texture.delete_cache, (url,))

                if self.is_music:
                    self.cursor.execute(queries_music.delete_artwork, (url,))
                else:
                    self.cursor.execute(queries_videos.delete_artwork, (url,))

                self.LOG.info("DELETE cached %s" % cached)

    #This method will sync all Kodi artwork to textures13.dband cache them locally. This takes diskspace!
    def cache_textures(self):
        if not self.Utils.WebserverData['Enabled']:
            return

        self.LOG.info("<[ cache textures ]")

        if self.Utils.dialog("yesno", heading="{emby}", line1=self.Utils.Translate(33044)):
            self.delete_all_cache()

        self._cache_all_video_entries()
        self._cache_all_music_entries()

    #Remove all existing textures from the thumbnails folder
    def delete_all_cache(self):
        self.LOG.info("[ delete all thumbnails ]")
        cache = self.Utils.translatePath('special://thumbnails/')

        if xbmcvfs.exists(cache):
            dirs, _ = xbmcvfs.listdir(cache)

            for directory in dirs:
                _, files = xbmcvfs.listdir(os.path.join(cache, directory))

                for Filename in files:
                    cached = os.path.join(cache, directory, Filename)
                    xbmcvfs.delete(cached)
                    self.LOG.debug("DELETE cached %s" % cached)

        with database.database.Database(self.Utils, 'texture', True) as kodidb:
            kodidb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

            for table in kodidb.cursor.fetchall():
                name = table[0]

                if name != 'version':
                    kodidb.cursor.execute("DELETE FROM " + name)

    #Cache all artwork from video db. Don't include actors
    def _cache_all_video_entries(self):
        with database.database.Database(self.Utils, 'video', True) as kodidb:
            kodidb.cursor.execute(queries_videos.get_artwork)
            urls = kodidb.cursor.fetchall()

        self.CacheAllEntriesThread = CacheAllEntries(urls, "video", self.Utils)
        self.CacheAllEntriesThread.start()

    #Cache all artwork from music db
    def _cache_all_music_entries(self):
        with database.database.Database(self.Utils, 'music', True) as kodidb:
            kodidb.cursor.execute(queries_music.get_artwork)
            urls = kodidb.cursor.fetchall()

        self.CacheAllEntriesThread = CacheAllEntries(urls, "music", self.Utils)
        self.CacheAllEntriesThread.start()

class CacheAllEntries(threading.Thread):
    def __init__(self, urls, Label, Utils):
        self.Utils = Utils
        self.urls = urls
        self.Label = Label
        self.progress_updates = xbmcgui.DialogProgressBG()
        self.progress_updates.create(self.Utils.Translate('addon_name'), self.Utils.Translate(33045))
        threading.Thread.__init__(self)

    #Cache all entries
    def run(self):
        total = len(self.urls)

        for index, url in enumerate(self.urls):
#            if self.Utils.window('emby.should_stop.bool'):
#                break

            Value = int((float(float(index)) / float(total)) * 100)
            self.progress_updates.update(Value, message="%s: %s" % (self.Utils.Translate(33045), self.Label + ": " + str(index)))

            if url[0]:
                url = urlencode({'blahblahblah': url[0]})
                url = url[13:]
                url = urlencode({'blahblahblah': url})
                url = url[13:]

                try:
                    requests.head("http://127.0.0.1:%s/image/image://%s" % (self.Utils.WebserverData['webServerPort'], url), auth=(self.Utils.WebserverData['webServerUser'], self.Utils.WebserverData['webServerPass']))
                except:
                    break

        self.progress_updates.close()

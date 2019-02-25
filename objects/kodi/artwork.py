# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import urllib
import Queue
import threading

import xbmc
import xbmcgui
import xbmcvfs

import queries as QU
import queries_music as QUMU
import queries_texture as QUTEX
import requests
from helper import _, window, settings, dialog
from database import Database

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Artwork(object):

    def __init__(self, cursor):

        self.cursor = cursor
        self.enable_cache = settings('enableTextureCache.bool')
        self.queue = Queue.Queue()
        self.thread_limit = 1 if settings('lowPowered.bool') else 2
        self.threads = []
        self.kodi = {
            'username': settings('webServerUser'),
            'password': settings('webServerPass'),
            'host': "localhost",
            'port': settings('webServerPort')
        }


    def update(self, image_url, kodi_id, media, image):

        ''' Update artwork in the video database.
            Only cache artwork if it changed for the main backdrop, poster.
            Delete current entry before updating with the new one.
            Cache fanart and poster in Kodi texture cache.
        '''
        if not image_url or image == 'poster' and media in ('song', 'artist', 'album'):
            return

        cache = False

        try:
            self.cursor.execute(QU.get_art, (kodi_id, media, image,))
            url = self.cursor.fetchone()[0]
        except TypeError:

            cache = True
            LOG.debug("ADD to kodi_id %s art: %s", kodi_id, image_url)
            self.cursor.execute(QU.add_art, (kodi_id, media, image, image_url))
        else:
            if url != image_url:
                cache = True

                if image in ('fanart', 'poster'):
                    self.delete_cache(url)

                LOG.info("UPDATE to kodi_id %s art: %s", kodi_id, image_url)
                self.cursor.execute(QU.update_art, (image_url, kodi_id, media, image))

        if cache and image in ('fanart', 'poster'):
            self.cache(image_url)

    def add(self, artwork, *args):

        ''' Add all artworks.
        '''
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
                self.cursor.execute(QU.get_backdrops, args + ("fanart%",))

                if len(self.cursor.fetchall()) > len(artwork['Backdrop']):
                    self.cursor.execute(QU.delete_backdrops, args + ("fanart_",))

                for index, backdrop in enumerate(artwork['Backdrop']):

                    if index:
                        self.update(*(backdrop,) + args + ("%s%s" % ("fanart", index),))
                    else:
                        self.update(*(backdrop,) + args + ("fanart",))

            elif art == 'Primary':
                for kodi_image in KODI['Primary']:
                    self.update(*(artwork['Primary'],) + args + (kodi_image,))

            elif artwork.get(art):
                self.update(*(artwork[art],) + args + (KODI[art],))

    def delete(self, *args):

        ''' Delete artwork from kodi database and remove cache for backdrop/posters.
        '''
        self.cursor.execute(QU.get_art_url, args)

        for row in self.cursor.fetchall():
            if row[1] in ('poster', 'fanart'):
                self.delete_cache(row[0])

    def cache(self, url, forced=False):

        ''' Cache a single image to texture cache.
        '''
        if not url or not self.enable_cache and not forced:
            return

        url = self.double_urlencode(url)
        self.queue.put(url)
        self.add_worker()

    def double_urlencode(self, text):

        text = self.single_urlencode(text)
        text = self.single_urlencode(text)

        return text

    def single_urlencode(self, text):
        
        ''' urlencode needs a utf-string.
            return the result as unicode
        '''
        text = urllib.urlencode({'blahblahblah': text.encode('utf-8')})
        text = text[13:]

        return text.decode('utf-8')

    def add_worker(self):

        if self.queue.qsize() and len(self.threads) < self.thread_limit:

            new_thread = GetArtworkWorker(self.kodi, self.queue, self.threads)
            new_thread.start()
            LOG.info("-->[ q:artwork/%s ]", id(new_thread))
            self.threads.append(new_thread)

    def delete_cache(self, url):

        ''' Delete cached artwork.
        '''
        with Database('texture') as texturedb:

            try:
                texturedb.cursor.execute(QUTEX.get_cache, (url,))
                cached = texturedb.cursor.fetchone()[0]
            except TypeError:
                LOG.debug("Could not find cached url: %s", url)
            else:
                thumbnails = xbmc.translatePath("special://thumbnails/%s" % cached).decode('utf-8')
                xbmcvfs.delete(thumbnails)
                texturedb.cursor.execute(QUTEX.delete_cache, (url,))
                LOG.info("DELETE cached %s", cached)

    def cache_textures(self):

        ''' This method will sync all Kodi artwork to textures13.db
            and cache them locally. This takes diskspace!
        '''
        if not dialog("yesno", heading="{emby}", line1=_(33042)):
            LOG.info("<[ cache textures ]")

            return

        pdialog = xbmcgui.DialogProgress()
        pdialog.create(_('addon_name'), _(33045))

        if dialog("yesno", heading="{emby}", line1=_(33044)):
            self.delete_all_cache()

        self._cache_all_video_entries(pdialog)
        self._cache_all_music_entries(pdialog)
        pdialog.update(100, "%s: %s" % (_(33046), len(self.queue.queue)))

        while len(self.threads):

            if pdialog.iscanceled():
                break

            remaining = len(self.queue.queue)
            pdialog.update(100, "%s: %s" % (_(33046), remaining))
            LOG.info("Waiting for all threads to exit: %s (%s)", len(self.threads), remaining)
            xbmc.sleep(500)

        pdialog.close()

    def delete_all_cache(self):

        ''' Remove all existing textures from the thumbnails folder.
        '''
        LOG.info("[ delete all thumbnails ]")
        cache = xbmc.translatePath('special://thumbnails/').decode('utf-8')

        if xbmcvfs.exists(cache):
            dirs, ignored = xbmcvfs.listdir(cache)
            
            for directory in dirs:
                ignored, files = xbmcvfs.listdir(os.path.join(cache, directory).decode('utf-8'))
                
                for file in files:

                    cached = os.path.join(cache, directory, file).decode('utf-8')
                    xbmcvfs.delete(cached)
                    LOG.debug("DELETE cached %s", cached)

        with Database('texture') as kodidb:
            kodidb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

            for table in kodidb.cursor.fetchall():
                name = table[0]

                if name != 'version':
                    kodidb.cursor.execute("DELETE FROM " + name)

    def _cache_all_video_entries(self, pdialog):

        ''' Cache all artwork from video db. Don't include actors.
        '''
        with Database('video') as kodidb:

            kodidb.cursor.execute(QU.get_artwork)
            urls = kodidb.cursor.fetchall()

        self._cache_all_entries(urls, pdialog)

    def _cache_all_music_entries(self, pdialog):

        ''' Cache all artwork from music db.
        '''
        with Database('music') as kodidb:
            
            kodidb.cursor.execute(QUMU.get_artwork)
            urls = kodidb.cursor.fetchall()

        self._cache_all_entries(urls, pdialog)

    def _cache_all_entries(self, urls, pdialog):

        ''' Cache all entries.
        '''
        total = len(urls)
        LOG.info("[ artwork cache pending/%s ]", total)

        for index, url in enumerate(urls):

            if pdialog.iscanceled():
                break

            pdialog.update(int((float(index) / float(total))*100), "%s: %s/%s" % (_(33045), index, total))
            self.cache(url[0], forced=True)


class GetArtworkWorker(threading.Thread):


    def __init__(self, kodi, queue, threads):

        self.kodi = kodi
        self.queue = queue
        self.threads = threads

        threading.Thread.__init__(self)

    def run(self):

        ''' Prepare the request. Request removes the urlencode which is required in this case.
            Use a session allows to use a pool of connections.
        '''
        monitor = xbmc.Monitor()

        with requests.Session() as s:

            while True:

                memory_available = xbmc.getFreeMem()
                LOG.info(memory_available)

                if memory_available < 200:
                    
                    if monitor.waitForAbort(2):
                        LOG.info("[ exited artwork/%s ]", id(self))

                        break

                    continue

                try:
                    url = self.queue.get(timeout=2)
                except Queue.Empty:

                    self.threads.remove(self)
                    LOG.info("--<[ q:artwork/%s ]", id(self))

                    return

                try:
                    req = requests.Request(method='HEAD',
                                           url="http://%s:%s/image/image://%s" % (self.kodi['host'], self.kodi['port'], url),
                                           auth=(self.kodi['username'], self.kodi['password']))
                    prep = req.prepare()
                    prep.url = "http://%s:%s/image/image://%s" % (self.kodi['host'], self.kodi['port'], url)
                    s.send(prep, timeout=(0.01, 0.01))
                    s.content # release the connection
                except Exception:
                    pass

                self.queue.task_done()

                if window('emby_should_stop.bool'):
                    LOG.info("[ exited artwork/%s ]", id(self))

                    break

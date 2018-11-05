#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from Queue import Queue, Empty
from urllib import quote_plus, unquote
from threading import Thread
import requests

import xbmc

from . import backgroundthread, path_ops, utils
from . import state

###############################################################################
LOG = getLogger('PLEX.artwork')

# Disable annoying requests warnings
requests.packages.urllib3.disable_warnings()
ARTWORK_QUEUE = Queue()
IMAGE_CACHING_SUSPENDS = [
    state.SUSPEND_LIBRARY_THREAD,
    state.DB_SCAN
]
if not utils.settings('imageSyncDuringPlayback') == 'true':
    IMAGE_CACHING_SUSPENDS.append(state.SUSPEND_SYNC)

###############################################################################


def double_urlencode(text):
    return quote_plus(quote_plus(text))


def double_urldecode(text):
    return unquote(unquote(text))


class ImageCachingThread(backgroundthread.KillableThread):
    # Potentially issues with limited number of threads
    # Hence let Kodi wait till download is successful
    timeout = (35.1, 35.1)

    def __init__(self):
        self.queue = ARTWORK_QUEUE
        Thread.__init__(self)

    def isCanceled(self):
        return state.STOP_PKC

    def isSuspended(self):
        return any(IMAGE_CACHING_SUSPENDS)

    @staticmethod
    def _art_url_generator():
        from . import kodidb_functions as kodidb
        for kind in ('video', 'music'):
            with kodidb.GetKodiDB(kind) as kodi_db:
                for kodi_type in ('poster', 'fanart'):
                    for url in kodi_db.artwork_generator(kodi_type):
                        yield url

    def missing_art_cache_generator(self):
        from . import kodidb_functions as kodidb
        with kodidb.GetKodiDB('texture') as kodi_db:
            for url in self._art_url_generator():
                if kodi_db.url_not_yet_cached(url):
                    yield url

    def _cache_url(self, url):
        url = double_urlencode(utils.try_encode(url))
        sleeptime = 0
        while True:
            try:
                requests.head(
                    url="http://%s:%s/image/image://%s"
                        % (state.WEBSERVER_HOST,
                           state.WEBSERVER_PORT,
                           url),
                    auth=(state.WEBSERVER_USERNAME,
                          state.WEBSERVER_PASSWORD),
                    timeout=self.timeout)
            except requests.Timeout:
                # We don't need the result, only trigger Kodi to start the
                # download. All is well
                break
            except requests.ConnectionError:
                if self.isCanceled():
                    # Kodi terminated
                    break
                # Server thinks its a DOS attack, ('error 10053')
                # Wait before trying again
                if sleeptime > 5:
                    LOG.error('Repeatedly got ConnectionError for url %s',
                              double_urldecode(url))
                    break
                LOG.debug('Were trying too hard to download art, server '
                          'over-loaded. Sleep %s seconds before trying '
                          'again to download %s',
                          2**sleeptime, double_urldecode(url))
                xbmc.sleep((2**sleeptime) * 1000)
                sleeptime += 1
                continue
            except Exception as err:
                LOG.error('Unknown exception for url %s: %s'.
                          double_urldecode(url), err)
                import traceback
                LOG.error("Traceback:\n%s", traceback.format_exc())
                break
            # We did not even get a timeout
            break

    def run(self):
        LOG.info("---===### Starting ImageCachingThread ###===---")
        # Cache already synced artwork first
        for url in self.missing_art_cache_generator():
            if self.isCanceled():
                return
            while self.isSuspended():
                # Set in service.py
                if self.isCanceled():
                    # Abort was requested while waiting. We should exit
                    LOG.info("---===### Stopped ImageCachingThread ###===---")
                    return
                xbmc.sleep(1000)
            self._cache_url(url)

        # Now wait for more stuff to cache - via the queue
        while not self.isCanceled():
            # In the event the server goes offline
            while self.isSuspended():
                # Set in service.py
                if self.isCanceled():
                    # Abort was requested while waiting. We should exit
                    LOG.info("---===### Stopped ImageCachingThread ###===---")
                    return
                xbmc.sleep(1000)
            try:
                url = self.queue.get(block=False)
            except Empty:
                xbmc.sleep(1000)
                continue
            if isinstance(url, ArtworkSyncMessage):
                if state.IMAGE_SYNC_NOTIFICATIONS:
                    utils.dialog('notification',
                                 heading=utils.lang(29999),
                                 message=url.message,
                                 icon='{plex}',
                                 sound=False)
                self.queue.task_done()
                continue
            self._cache_url(url)
            self.queue.task_done()
            # Sleep for a bit to reduce CPU strain
            xbmc.sleep(100)
        LOG.info("---===### Stopped ImageCachingThread ###===---")


class Artwork():
    enableTextureCache = utils.settings('enableTextureCache') == "true"
    if enableTextureCache:
        queue = ARTWORK_QUEUE

    def fullTextureCacheSync(self):
        """
        This method will sync all Kodi artwork to textures13.db
        and cache them locally. This takes diskspace!
        """
        if not utils.yesno_dialog("Image Texture Cache", utils.lang(39250)):
            return

        LOG.info("Doing Image Cache Sync")

        # ask to rest all existing or not
        if utils.yesno_dialog("Image Texture Cache", utils.lang(39251)):
            LOG.info("Resetting all cache data first")
            # Remove all existing textures first
            path = path_ops.translate_path('special://thumbnails/')
            if path_ops.exists(path):
                path_ops.rmtree(path, ignore_errors=True)
                self.restore_cache_directories()

            # remove all existing data from texture DB
            connection = utils.kodi_sql('texture')
            cursor = connection.cursor()
            query = 'SELECT tbl_name FROM sqlite_master WHERE type=?'
            cursor.execute(query, ('table', ))
            rows = cursor.fetchall()
            for row in rows:
                tableName = row[0]
                if tableName != "version":
                    cursor.execute("DELETE FROM %s" % tableName)
            connection.commit()
            connection.close()

        # Cache all entries in video DB
        connection = utils.kodi_sql('video')
        cursor = connection.cursor()
        # dont include actors
        query = "SELECT url FROM art WHERE media_type != ?"
        cursor.execute(query, ('actor', ))
        result = cursor.fetchall()
        total = len(result)
        LOG.info("Image cache sync about to process %s video images", total)
        connection.close()

        for url in result:
            self.cache_texture(url[0])
        # Cache all entries in music DB
        connection = utils.kodi_sql('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        LOG.info("Image cache sync about to process %s music images", total)
        connection.close()
        for url in result:
            self.cache_texture(url[0])

    def cache_texture(self, url):
        '''
        Cache a single image url to the texture cache. url: unicode
        '''
        if url and self.enableTextureCache:
            self.queue.put(url)

    def modify_artwork(self, artworks, kodi_id, kodi_type, cursor):
        """
        Pass in an artworks dict (see PlexAPI) to set an items artwork.
        """
        for kodi_art, url in artworks.iteritems():
            self.modify_art(url, kodi_id, kodi_type, kodi_art, cursor)

    def modify_art(self, url, kodi_id, kodi_type, kodi_art, cursor):
        """
        Adds or modifies the artwork of kind kodi_art (e.g. 'poster') in the
        Kodi art table for item kodi_id/kodi_type. Will also cache everything
        except actor portraits.
        """
        query = '''
            SELECT url FROM art
            WHERE media_id = ? AND media_type = ? AND type = ?
            LIMIT 1
        '''
        cursor.execute(query, (kodi_id, kodi_type, kodi_art,))
        try:
            # Update the artwork
            old_url = cursor.fetchone()[0]
        except TypeError:
            # Add the artwork
            query = '''
                INSERT INTO art(media_id, media_type, type, url)
                VALUES (?, ?, ?, ?)
            '''
            cursor.execute(query, (kodi_id, kodi_type, kodi_art, url))
        else:
            if url == old_url:
                # Only cache artwork if it changed
                return
            self.delete_cached_artwork(old_url)
            query = '''
                UPDATE art SET url = ?
                WHERE media_id = ? AND media_type = ? AND type = ?
            '''
            cursor.execute(query, (url, kodi_id, kodi_type, kodi_art))
        # Cache fanart and poster in Kodi texture cache
        if kodi_type != 'actor':
            self.cache_texture(url)

    def delete_artwork(self, kodiId, mediaType, cursor):
        query = 'SELECT url FROM art WHERE media_id = ? AND media_type = ?'
        cursor.execute(query, (kodiId, mediaType,))
        for row in cursor.fetchall():
            self.delete_cached_artwork(row[0])

    @staticmethod
    def delete_cached_artwork(url):
        """
        Deleted the cached artwork with path url (if it exists)
        """
        connection = utils.kodi_sql('texture')
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT cachedurl FROM texture WHERE url=? LIMIT 1",
                           (url,))
            cachedurl = cursor.fetchone()[0]
        except TypeError:
            # Could not find cached url
            pass
        else:
            # Delete thumbnail as well as the entry
            path = path_ops.translate_path("special://thumbnails/%s"
                                           % cachedurl)
            if path_ops.exists(path):
                path_ops.rmtree(path, ignore_errors=True)
            cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def restore_cache_directories():
        LOG.info("Restoring cache directories...")
        paths = ("", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
                 "a", "b", "c", "d", "e", "f",
                 "Video", "plex")
        for path in paths:
            new_path = path_ops.translate_path("special://thumbnails/%s" % path)
            path_ops.makedirs(path_ops.encode_path(new_path))


class ArtworkSyncMessage(object):
    """
    Put in artwork queue to display the message as a Kodi notification
    """
    def __init__(self, message):
        self.message = message

#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from urllib import quote_plus, unquote
import requests
import xbmc

from . import backgroundthread, path_ops, utils
from . import state

###############################################################################
LOG = getLogger('PLEX.artwork')

# Disable annoying requests warnings
requests.packages.urllib3.disable_warnings()

# Potentially issues with limited number of threads Hence let Kodi wait till
# download is successful
TIMEOUT = (35.1, 35.1)

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
    def __init__(self):
        self._canceled = False
        super(ImageCachingThread, self).__init__()

    def isCanceled(self):
        return self._canceled or state.STOP_PKC

    def isSuspended(self):
        return any(IMAGE_CACHING_SUSPENDS)

    def cancel(self):
        self._canceled = True

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
            cache_url(url)
        LOG.info("---===### Stopped ImageCachingThread ###===---")


def cache_url(url):
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
                timeout=TIMEOUT)
        except requests.Timeout:
            # We don't need the result, only trigger Kodi to start the
            # download. All is well
            break
        except requests.ConnectionError:
            if state.STOP_PKC:
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


def modify_artwork(artworks, kodi_id, kodi_type, cursor):
    """
    Pass in an artworks dict (see PlexAPI) to set an items artwork.
    """
    for kodi_art, url in artworks.iteritems():
        modify_art(url, kodi_id, kodi_type, kodi_art, cursor)


def modify_art(url, kodi_id, kodi_type, kodi_art, cursor):
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
        delete_cached_artwork(old_url)
        query = '''
            UPDATE art SET url = ?
            WHERE media_id = ? AND media_type = ? AND type = ?
        '''
        cursor.execute(query, (url, kodi_id, kodi_type, kodi_art))


def delete_artwork(kodiId, mediaType, cursor):
    cursor.execute('SELECT url FROM art WHERE media_id = ? AND media_type = ?',
                   (kodiId, mediaType, ))
    for row in cursor.fetchall():
        delete_cached_artwork(row[0])


def delete_cached_artwork(url):
    """
    Deleted the cached artwork with path url (if it exists)
    """
    from . import kodidb_functions as kodidb
    with kodidb.GetKodiDB('texture') as kodi_db:
        try:
            kodi_db.cursor.execute("SELECT cachedurl FROM texture WHERE url=? LIMIT 1",
                                   (url, ))
            cachedurl = kodi_db.cursor.fetchone()[0]
        except TypeError:
            # Could not find cached url
            pass
        else:
            # Delete thumbnail as well as the entry
            path = path_ops.translate_path("special://thumbnails/%s"
                                           % cachedurl)
            if path_ops.exists(path):
                path_ops.rmtree(path, ignore_errors=True)
            kodi_db.cursor.execute("DELETE FROM texture WHERE url = ?", (url,))

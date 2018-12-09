#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
from urllib import quote_plus, unquote
import requests

from .kodi_db import KodiVideoDB, KodiMusicDB, KodiTextureDB
from . import app, backgroundthread, utils

LOG = getLogger('PLEX.artwork')

# Disable annoying requests warnings
requests.packages.urllib3.disable_warnings()

# Potentially issues with limited number of threads Hence let Kodi wait till
# download is successful
TIMEOUT = (35.1, 35.1)

IMAGE_CACHING_SUSPENDS = []


def double_urlencode(text):
    return quote_plus(quote_plus(text))


def double_urldecode(text):
    return unquote(unquote(text))


class ImageCachingThread(backgroundthread.KillableThread):
    def isSuspended(self):
        return any(IMAGE_CACHING_SUSPENDS)

    @staticmethod
    def _art_url_generator():
        for kind in (KodiVideoDB, KodiMusicDB):
            with kind() as kodidb:
                for kodi_type in ('poster', 'fanart'):
                    for url in kodidb.artwork_generator(kodi_type):
                        yield url

    def missing_art_cache_generator(self):
        with KodiTextureDB() as kodidb:
            for url in self._art_url_generator():
                if kodidb.url_not_yet_cached(url):
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
                app.APP.monitor.waitForAbort(1)
            cache_url(url)
        else:
            # Toggles Image caching completed to Yes
            utils.settings('plex_status_image_caching', value=utils.lang(107))
        LOG.info("---===### Stopped ImageCachingThread ###===---")


def cache_url(url):
    url = double_urlencode(utils.try_encode(url))
    sleeptime = 0
    while True:
        try:
            requests.head(
                url="http://%s:%s/image/image://%s"
                    % (app.CONN.webserver_host,
                       app.CONN.webserver_port,
                       url),
                auth=(app.CONN.webserver_username,
                      app.CONN.webserver_password),
                timeout=TIMEOUT)
        except requests.Timeout:
            # We don't need the result, only trigger Kodi to start the
            # download. All is well
            break
        except requests.ConnectionError:
            if app.APP.stop_pkc:
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
            app.APP.monitor.waitForAbort((2**sleeptime))
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

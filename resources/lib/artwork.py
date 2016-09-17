# -*- coding: utf-8 -*-

###############################################################################

import json
import logging
import requests
import os
import urllib
from sqlite3 import OperationalError
from threading import Lock

import xbmc
import xbmcgui
import xbmcvfs

from image_cache_thread import ImageCacheThread
from utils import window, settings, language as lang, kodiSQL, tryEncode, \
    tryDecode, IfExists

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


def setKodiWebServerDetails():
    """
    Get the Kodi webserver details - used to set the texture cache
    """
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None
    web_query = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {
            "setting": "services.webserver"
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(web_query))
    result = json.loads(result)
    try:
        xbmc_webserver_enabled = result['result']['value']
    except (KeyError, TypeError):
        xbmc_webserver_enabled = False
    if not xbmc_webserver_enabled:
        # Enable the webserver, it is disabled
        web_port = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.SetSettingValue",
            "params": {
                "setting": "services.webserverport",
                "value": 8080
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_port))
        xbmc_port = 8080
        web_user = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.SetSettingValue",
            "params": {
                "setting": "services.webserver",
                "value": True
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_user))
        xbmc_username = "kodi"
    # Webserver already enabled
    web_port = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {
            "setting": "services.webserverport"
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(web_port))
    result = json.loads(result)
    try:
        xbmc_port = result['result']['value']
    except (TypeError, KeyError):
        pass
    web_user = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {
            "setting": "services.webserverusername"
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(web_user))
    result = json.loads(result)
    try:
        xbmc_username = result['result']['value']
    except TypeError:
        pass
    web_pass = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {
            "setting": "services.webserverpassword"
        }
    }
    result = xbmc.executeJSONRPC(json.dumps(web_pass))
    result = json.loads(result)
    try:
        xbmc_password = result['result']['value']
    except TypeError:
        pass
    return (xbmc_port, xbmc_username, xbmc_password)


class Artwork():
    lock = Lock()

    enableTextureCache = settings('enableTextureCache') == "true"
    imageCacheLimitThreads = int(settings('imageCacheLimit'))
    imageCacheLimitThreads = imageCacheLimitThreads * 5
    log.info("Using Image Cache Thread Count: %s" % imageCacheLimitThreads)

    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None
    if enableTextureCache:
        xbmc_port, xbmc_username, xbmc_password = setKodiWebServerDetails()

    imageCacheThreads = []

    def double_urlencode(self, text):
        text = self.single_urlencode(text)
        text = self.single_urlencode(text)
        return text

    def single_urlencode(self, text):
        # urlencode needs a utf- string
        text = urllib.urlencode({'blahblahblah': tryEncode(text)})
        text = text[13:]
        # return the result again as unicode
        return tryDecode(text)

    def fullTextureCacheSync(self):
        """
        This method will sync all Kodi artwork to textures13.db
        and cache them locally. This takes diskspace!
        """
        if not xbmcgui.Dialog().yesno(
                "Image Texture Cache", lang(39250)):
            return

        log.info("Doing Image Cache Sync")

        pdialog = xbmcgui.DialogProgress()
        pdialog.create("PlexKodiConnect", "Image Cache Sync")

        # ask to rest all existing or not
        if xbmcgui.Dialog().yesno(
                "Image Texture Cache", lang(39251), ""):
            log.info("Resetting all cache data first")
            # Remove all existing textures first
            path = tryDecode(xbmc.translatePath("special://thumbnails/"))
            if IfExists(path):
                allDirs, allFiles = xbmcvfs.listdir(path)
                for dir in allDirs:
                    allDirs, allFiles = xbmcvfs.listdir(path+dir)
                    for file in allFiles:
                        if os.path.supports_unicode_filenames:
                            xbmcvfs.delete(os.path.join(
                                path + tryDecode(dir),
                                tryDecode(file)))
                        else:
                            xbmcvfs.delete(os.path.join(
                                tryEncode(path) + dir,
                                file))

            # remove all existing data from texture DB
            connection = kodiSQL('texture')
            cursor = connection.cursor()
            cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
            rows = cursor.fetchall()
            for row in rows:
                tableName = row[0]
                if tableName != "version":
                    cursor.execute("DELETE FROM " + tableName)
            connection.commit()
            connection.close()

        # Cache all entries in video DB
        connection = kodiSQL('video')
        cursor = connection.cursor()
        # dont include actors
        cursor.execute("SELECT url FROM art WHERE media_type != 'actor'")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images" % total)
        connection.close()

        count = 0
        for url in result:
            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s (%s)" % (count, total, self.imageCacheThreads)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cacheTexture(url[0])
            count += 1
        # Cache all entries in music DB
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images" % total)
        connection.close()

        count = 0
        for url in result:
            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s" % (count, total)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cacheTexture(url[0])
            count += 1
        pdialog.update(100, "%s %s"
                       % (lang(33046), len(self.imageCacheThreads)))
        log.info("Waiting for all threads to exit")
        while len(self.imageCacheThreads):
            with self.lock:
                for thread in self.imageCacheThreads:
                    if thread.is_finished:
                        self.imageCacheThreads.remove(thread)
            pdialog.update(100, "%s %s"
                           % (lang(33046), len(self.imageCacheThreads)))
            log.info("Waiting for all threads to exit: %s"
                     % len(self.imageCacheThreads))
            xbmc.sleep(500)

        pdialog.close()

    def addWorkerImageCacheThread(self, url):
        while True:
            # removed finished
            with self.lock:
                for thread in self.imageCacheThreads:
                    if thread.isAlive() is False:
                        self.imageCacheThreads.remove(thread)
            # add a new thread or wait and retry if we hit our limit
            with self.lock:
                if len(self.imageCacheThreads) < self.imageCacheLimitThreads:
                    thread = ImageCacheThread(
                        self.xbmc_username,
                        self.xbmc_password,
                        "http://%s:%s/image/image://%s"
                        % (self.xbmc_host,
                           self.xbmc_port,
                           self.double_urlencode(url)))
                    thread.start()
                    self.imageCacheThreads.append(thread)
                    return
            log.error('Waiting for queue spot here')
            xbmc.sleep(50)

    def cacheTexture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enableTextureCache:
            log.debug("Processing: %s" % url)
            if not self.imageCacheLimitThreads:
                # Add image to texture cache by simply calling it at the http
                # endpoint
                url = self.double_urlencode(url)
                try:
                    # Extreme short timeouts so we will have a exception.
                    requests.head(
                        url=("http://%s:%s/image/image://%s"
                             % (self.xbmc_host, self.xbmc_port, url)),
                        auth=(self.xbmc_username, self.xbmc_password),
                        timeout=(0.01, 0.01))
                # We don't need the result
                except:
                    pass
            else:
                self.addWorkerImageCacheThread(url)

    def addArtwork(self, artwork, kodiId, mediaType, cursor):
        # Kodi conversion table
        kodiart = {

            'Primary': ["thumb", "poster"],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart",
            'BoxRear': "poster"
        }

        # Artwork is a dictionary
        for art in artwork:
            if art == "Backdrop":
                # Backdrop entry is a list
                # Process extra fanart for artwork downloader (fanart, fanart1,
                # fanart2...)
                backdrops = artwork[art]
                backdropsNumber = len(backdrops)

                query = ' '.join((

                    "SELECT url",
                    "FROM art",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND type LIKE ?"
                ))
                cursor.execute(query, (kodiId, mediaType, "fanart%",))
                rows = cursor.fetchall()

                if len(rows) > backdropsNumber:
                    # More backdrops in database. Delete extra fanart.
                    query = ' '.join((

                        "DELETE FROM art",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type LIKE ?"
                    ))
                    cursor.execute(query, (kodiId, mediaType, "fanart_",))

                # Process backdrops and extra fanart
                index = ""
                for backdrop in backdrops:
                    self.addOrUpdateArt(
                        imageUrl=backdrop,
                        kodiId=kodiId,
                        mediaType=mediaType,
                        imageType="%s%s" % ("fanart", index),
                        cursor=cursor)

                    if backdropsNumber > 1:
                        try: # Will only fail on the first try, str to int.
                            index += 1
                        except TypeError:
                            index = 1

            elif art == "Primary":
                # Primary art is processed as thumb and poster for Kodi.
                for artType in kodiart[art]:
                    self.addOrUpdateArt(
                        imageUrl=artwork[art],
                        kodiId=kodiId,
                        mediaType=mediaType,
                        imageType=artType,
                        cursor=cursor)

            elif kodiart.get(art):
                # Process the rest artwork type that Kodi can use
                self.addOrUpdateArt(
                    imageUrl=artwork[art],
                    kodiId=kodiId,
                    mediaType=mediaType,
                    imageType=kodiart[art],
                    cursor=cursor)

    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):
        if not imageUrl:
            # Possible that the imageurl is an empty string
            return

        query = ' '.join((
            "SELECT url",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?",
            "AND type = ?"
        ))
        cursor.execute(query, (kodiId, mediaType, imageType,))
        try:
            # Update the artwork
            url = cursor.fetchone()[0]
        except TypeError:
            # Add the artwork
            log.debug("Adding Art Link for kodiId: %s (%s)"
                      % (kodiId, imageUrl))
            query = (
                '''
                INSERT INTO art(media_id, media_type, type, url)
                VALUES (?, ?, ?, ?)
                '''
            )
            cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))
        else:
            if url == imageUrl:
                # Only cache artwork if it changed
                return
            # Only for the main backdrop, poster
            if (window('plex_initialScan') != "true" and
                    imageType in ("fanart", "poster")):
                # Delete current entry before updating with the new one
                self.deleteCachedArtwork(url)
            log.debug("Updating Art url for %s kodiId %s %s -> (%s)"
                      % (imageType, kodiId, url, imageUrl))
            query = ' '.join((
                "UPDATE art",
                "SET url = ?",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND type = ?"
            ))
            cursor.execute(query, (imageUrl, kodiId, mediaType, imageType))

        # Cache fanart and poster in Kodi texture cache
        self.cacheTexture(imageUrl)

    def deleteArtwork(self, kodiId, mediaType, cursor):
        query = ' '.join((
            "SELECT url",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?"
        ))
        cursor.execute(query, (kodiId, mediaType,))
        rows = cursor.fetchall()
        for row in rows:
            self.deleteCachedArtwork(row[0])

    def deleteCachedArtwork(self, url):
        # Only necessary to remove and apply a new backdrop or poster
        connection = kodiSQL('texture')
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT cachedurl FROM texture WHERE url = ?",
                           (url,))
            cachedurl = cursor.fetchone()[0]
        except TypeError:
            log.info("Could not find cached url.")
        except OperationalError:
            log.warn("Database is locked. Skip deletion process.")
        else:
            # Delete thumbnail as well as the entry
            thumbnails = tryDecode(
                xbmc.translatePath("special://thumbnails/%s" % cachedurl))
            log.debug("Deleting cached thumbnail: %s" % thumbnails)
            try:
                xbmcvfs.delete(thumbnails)
            except Exception as e:
                log.error('Could not delete cached artwork %s. Error: %s'
                          % (thumbnails, e))
            try:
                cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
                connection.commit()
            except OperationalError:
                log.error("OperationalError deleting url from cache.")
        finally:
            connection.close()

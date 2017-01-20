# -*- coding: utf-8 -*-

###############################################################################
import json
import logging
import requests
import os
from urllib import quote_plus, unquote
from threading import Thread
import Queue

import xbmc
import xbmcgui
import xbmcvfs

from utils import window, settings, language as lang, kodiSQL, tryEncode, \
    tryDecode, IfExists, ThreadMethods, ThreadMethodsAdditionalStop

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


def double_urlencode(text):
    return quote_plus(quote_plus(text))


def double_urldecode(text):
    return unquote(unquote(text))


@ThreadMethodsAdditionalStop('plex_shouldStop')
@ThreadMethods
class Image_Cache_Thread(Thread):
    xbmc_host = 'localhost'
    xbmc_port, xbmc_username, xbmc_password = setKodiWebServerDetails()
    sleep_between = 50
    # Potentially issues with limited number of threads
    # Hence let Kodi wait till download is successful
    timeout = (35.1, 35.1)

    def __init__(self, queue):
        self.queue = queue
        Thread.__init__(self)

    def threadSuspended(self):
        # Overwrite method to add TWO additional suspends
        return (self._threadSuspended or
                window('suspend_LibraryThread') or
                window('plex_dbScan'))

    def run(self):
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        queue = self.queue
        sleep_between = self.sleep_between
        while not threadStopped():
            # In the event the server goes offline
            while threadSuspended():
                # Set in service.py
                if threadStopped():
                    # Abort was requested while waiting. We should exit
                    log.info("---===### Stopped Image_Cache_Thread ###===---")
                    return
                xbmc.sleep(1000)
            try:
                url = queue.get(block=False)
            except Queue.Empty:
                xbmc.sleep(1000)
                continue
            sleep = 0
            while True:
                try:
                    requests.head(
                        url="http://%s:%s/image/image://%s"
                            % (self.xbmc_host, self.xbmc_port, url),
                        auth=(self.xbmc_username, self.xbmc_password),
                        timeout=self.timeout)
                except requests.Timeout:
                    # We don't need the result, only trigger Kodi to start the
                    # download. All is well
                    break
                except requests.ConnectionError:
                    # Server thinks its a DOS attack, ('error 10053')
                    # Wait before trying again
                    if sleep > 5:
                        log.error('Repeatedly got ConnectionError for url %s'
                                  % double_urldecode(url))
                        break
                    log.debug('Were trying too hard to download art, server '
                              'over-loaded. Sleep %s seconds before trying '
                              'again to download %s'
                              % (2**sleep, double_urldecode(url)))
                    xbmc.sleep((2**sleep)*1000)
                    sleep += 1
                    continue
                except Exception as e:
                    log.error('Unknown exception for url %s: %s'
                              % (double_urldecode(url), e))
                    import traceback
                    log.error("Traceback:\n%s" % traceback.format_exc())
                    break
                # We did not even get a timeout
                break
            queue.task_done()
            log.debug('Cached art: %s' % double_urldecode(url))
            # Sleep for a bit to reduce CPU strain
            xbmc.sleep(sleep_between)
        log.info("---===### Stopped Image_Cache_Thread ###===---")


class Artwork():
    enableTextureCache = settings('enableTextureCache') == "true"
    if enableTextureCache:
        queue = Queue.Queue()
        download_thread = Image_Cache_Thread(queue)
        download_thread.start()

    def fullTextureCacheSync(self):
        """
        This method will sync all Kodi artwork to textures13.db
        and cache them locally. This takes diskspace!
        """
        if not xbmcgui.Dialog().yesno(
                "Image Texture Cache", lang(39250)):
            return

        log.info("Doing Image Cache Sync")

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
        log.info("Image cache sync about to process %s video images" % total)
        connection.close()

        for url in result:
            self.cacheTexture(url[0])
        # Cache all entries in music DB
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s music images" % total)
        connection.close()
        for url in result:
            self.cacheTexture(url[0])

    def cacheTexture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enableTextureCache:
            self.queue.put(double_urlencode(tryEncode(url)))

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
            cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
            connection.commit()
        finally:
            connection.close()

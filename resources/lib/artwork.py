# -*- coding: utf-8 -*-

###############################################################################
import logging
from json import dumps, loads
import requests
from shutil import rmtree
from urllib import quote_plus, unquote
from threading import Thread
from Queue import Queue, Empty

from xbmc import executeJSONRPC, sleep, translatePath
from xbmcvfs import exists

from utils import window, settings, language as lang, kodiSQL, tryEncode, \
    thread_methods, dialog, exists_dir, tryDecode

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################

ARTWORK_QUEUE = Queue()


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
    result = executeJSONRPC(dumps(web_query))
    result = loads(result)
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
        result = executeJSONRPC(dumps(web_port))
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
        result = executeJSONRPC(dumps(web_user))
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
    result = executeJSONRPC(dumps(web_port))
    result = loads(result)
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
    result = executeJSONRPC(dumps(web_user))
    result = loads(result)
    try:
        xbmc_username = result['result']['value']
    except (TypeError, KeyError):
        pass
    web_pass = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "Settings.GetSettingValue",
        "params": {
            "setting": "services.webserverpassword"
        }
    }
    result = executeJSONRPC(dumps(web_pass))
    result = loads(result)
    try:
        xbmc_password = result['result']['value']
    except TypeError:
        pass
    return (xbmc_port, xbmc_username, xbmc_password)


def double_urlencode(text):
    return quote_plus(quote_plus(text))


def double_urldecode(text):
    return unquote(unquote(text))


@thread_methods(add_stops=['STOP_SYNC'],
                add_suspends=['SUSPEND_LIBRARY_THREAD', 'DB_SCAN'])
class Image_Cache_Thread(Thread):
    xbmc_host = 'localhost'
    xbmc_port, xbmc_username, xbmc_password = setKodiWebServerDetails()
    sleep_between = 50
    # Potentially issues with limited number of threads
    # Hence let Kodi wait till download is successful
    timeout = (35.1, 35.1)

    def __init__(self):
        self.queue = ARTWORK_QUEUE
        Thread.__init__(self)

    def run(self):
        thread_stopped = self.thread_stopped
        thread_suspended = self.thread_suspended
        queue = self.queue
        sleep_between = self.sleep_between
        while not thread_stopped():
            # In the event the server goes offline
            while thread_suspended():
                # Set in service.py
                if thread_stopped():
                    # Abort was requested while waiting. We should exit
                    log.info("---===### Stopped Image_Cache_Thread ###===---")
                    return
                sleep(1000)
            try:
                url = queue.get(block=False)
            except Empty:
                sleep(1000)
                continue
            sleeptime = 0
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
                    if thread_stopped():
                        # Kodi terminated
                        break
                    # Server thinks its a DOS attack, ('error 10053')
                    # Wait before trying again
                    if sleeptime > 5:
                        log.error('Repeatedly got ConnectionError for url %s'
                                  % double_urldecode(url))
                        break
                    log.debug('Were trying too hard to download art, server '
                              'over-loaded. Sleep %s seconds before trying '
                              'again to download %s'
                              % (2**sleeptime, double_urldecode(url)))
                    sleep((2**sleeptime)*1000)
                    sleeptime += 1
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
            sleep(sleep_between)
        log.info("---===### Stopped Image_Cache_Thread ###===---")


class Artwork():
    enableTextureCache = settings('enableTextureCache') == "true"
    if enableTextureCache:
        queue = ARTWORK_QUEUE

    def fullTextureCacheSync(self):
        """
        This method will sync all Kodi artwork to textures13.db
        and cache them locally. This takes diskspace!
        """
        if not dialog('yesno', "Image Texture Cache", lang(39250)):
            return

        log.info("Doing Image Cache Sync")

        # ask to rest all existing or not
        if dialog('yesno', "Image Texture Cache", lang(39251)):
            log.info("Resetting all cache data first")
            # Remove all existing textures first
            path = tryDecode(translatePath("special://thumbnails/"))
            if exists_dir(path):
                rmtree(path, ignore_errors=True)

            # remove all existing data from texture DB
            connection = kodiSQL('texture')
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
        connection = kodiSQL('video')
        cursor = connection.cursor()
        # dont include actors
        query = "SELECT url FROM art WHERE media_type != ?"
        cursor.execute(query, ('actor', ))
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
                        try:  # Will only fail on the first try, str to int.
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
        if mediaType != 'actor':
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
            path = translatePath("special://thumbnails/%s" % cachedurl)
            log.debug("Deleting cached thumbnail: %s" % path)
            if exists(path):
                rmtree(tryDecode(path), ignore_errors=True)
            cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
            connection.commit()
        finally:
            connection.close()

# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import urllib
from sqlite3 import OperationalError

import xbmc
import xbmcgui
import xbmcvfs
import requests

import image_cache_thread
from utils import window, settings, dialog, language as lang, kodiSQL, JSONRPC

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Artwork(object):

    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None

    image_cache_threads = []
    image_cache_limit = 0


    def __init__(self):

        self.enable_texture_cache = settings('enableTextureCache') == "true"
        self.image_cache_limit = int(settings('imageCacheLimit')) * 5
        log.info("image cache thread count: %s", self.image_cache_limit)

        if not self.xbmc_port and self.enable_texture_cache:
            self._set_webserver_details()

        self.user_id = window('emby_currUser')
        self.server = window('emby_server%s' % self.user_id)


    def _double_urlencode(self, text):

        text = self._single_urlencode(text)
        text = self._single_urlencode(text)

        return text

    @classmethod
    def _single_urlencode(cls, text):
        # urlencode needs a utf- string
        text = urllib.urlencode({'blahblahblah': text.encode('utf-8')})
        text = text[13:]

        return text.decode('utf-8') #return the result again as unicode

    def _set_webserver_details(self):
        # Get the Kodi webserver details - used to set the texture cache
        get_setting_value = JSONRPC('Settings.GetSettingValue')

        web_query = {

            "setting": "services.webserver"
        }
        result = get_setting_value.execute(web_query)
        try:
            xbmc_webserver_enabled = result['result']['value']
        except (KeyError, TypeError):
            xbmc_webserver_enabled = False

        if not xbmc_webserver_enabled:
            # Enable the webserver, it is disabled
            set_setting_value = JSONRPC('Settings.SetSettingValue')

            web_port = {

                "setting": "services.webserverport",
                "value": 8080
            }
            set_setting_value.execute(web_port)
            self.xbmc_port = 8080

            web_user = {

                "setting": "services.webserver",
                "value": True
            }
            set_setting_value.execute(web_user)
            self.xbmc_username = "kodi"

        # Webserver already enabled
        web_port = {

            "setting": "services.webserverport"
        }
        result = get_setting_value.execute(web_port)
        try:
            self.xbmc_port = result['result']['value']
        except (TypeError, KeyError):
            pass

        web_user = {

            "setting": "services.webserverusername"
        }
        result = get_setting_value.execute(web_user)
        try:
            self.xbmc_username = result['result']['value']
        except TypeError:
            pass

        web_pass = {

            "setting": "services.webserverpassword"
        }
        result = get_setting_value.execute(web_pass)
        try:
            self.xbmc_password = result['result']['value']
        except TypeError:
            pass

    def fullTextureCacheSync(self):
        # This method will sync all Kodi artwork to textures13.db
        # and cache them locally. This takes diskspace!
        if not dialog(type_="yesno",
                      heading="{emby}",
                      line1=lang(33042)):
            return

        log.info("Doing Image Cache Sync")

        pdialog = xbmcgui.DialogProgress()
        pdialog.create(lang(29999), lang(33043))

        # ask to rest all existing or not
        if dialog(type_="yesno", heading="{emby}", line1=lang(33044)):
            log.info("Resetting all cache data first")

            # Remove all existing textures first
            path = xbmc.translatePath('special://thumbnails/').decode('utf-8')
            if xbmcvfs.exists(path):
                allDirs, allFiles = xbmcvfs.listdir(path)
                for dir in allDirs:
                    allDirs, allFiles = xbmcvfs.listdir(path+dir)
                    for file in allFiles:
                        if os.path.supports_unicode_filenames:
                            path = os.path.join(path+dir.decode('utf-8'),file.decode('utf-8'))
                            xbmcvfs.delete(path)
                        else:
                            xbmcvfs.delete(os.path.join(path.encode('utf-8')+dir,file))

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
            cursor.close()

        # Cache all entries in video DB
        connection = kodiSQL('video')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art WHERE media_type != 'actor'") # dont include actors
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images", total)
        cursor.close()

        count = 0
        for url in result:

            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s (%s)" % (count, total, self.image_cache_threads)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cache_texture(url[0])
            count += 1

        # Cache all entries in music DB
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images", total)
        cursor.close()

        count = 0
        for url in result:
            
            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s" % (count, total)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cache_texture(url[0])
            count += 1

        pdialog.update(100, "%s %s" % (lang(33046), len(self.image_cache_threads)))
        log.info("Waiting for all threads to exit")

        while len(self.image_cache_threads):
            for thread in self.image_cache_threads:
                if thread.is_finished:
                    self.image_cache_threads.remove(thread)
            pdialog.update(100, "%s %s" % (lang(33046), len(self.image_cache_threads)))
            log.info("Waiting for all threads to exit: %s", len(self.image_cache_threads))
            xbmc.sleep(500)

        pdialog.close()

    def _add_worker_image_thread(self, url):

        while True:
            # removed finished
            for thread in self.image_cache_threads:
                if thread.is_finished:
                    self.image_cache_threads.remove(thread)

            # add a new thread or wait and retry if we hit our limit
            if len(self.image_cache_threads) < self.image_cache_limit:
                
                new_thread = image_cache_thread.ImageCacheThread()
                new_thread.set_url(self._double_urlencode(url))
                new_thread.set_host(self.xbmc_host, self.xbmc_port)
                new_thread.set_auth(self.xbmc_username, self.xbmc_password)
                
                new_thread.start()
                self.image_cache_threads.append(new_thread)
                return
            else:
                log.info("Waiting for empty queue spot: %s", len(self.image_cache_threads))
                xbmc.sleep(50)

    def cache_texture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enable_texture_cache:
            log.debug("Processing: %s", url)

            if not self.image_cache_limit:

                url = self._double_urlencode(url)
                try: # Add image to texture cache by simply calling it at the http endpoint
                    requests.head(url=("http://%s:%s/image/image://%s"
                                       % (self.xbmc_host, self.xbmc_port, url)),
                                  auth=(self.xbmc_username, self.xbmc_password),
                                  timeout=(0.01, 0.01))
                except Exception: # We don't need the result
                    pass
            else:
                self._add_worker_image_thread(url)

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
                # Process extra fanart for artwork downloader (fanart, fanart1, fanart2...)
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
        # Possible that the imageurl is an empty string
        if imageUrl:
            cacheimage = False

            query = ' '.join((

                "SELECT url",
                "FROM art",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND type = ?"
            ))
            cursor.execute(query, (kodiId, mediaType, imageType,))
            try: # Update the artwork
                url = cursor.fetchone()[0]

            except TypeError: # Add the artwork
                cacheimage = True
                log.debug("Adding Art Link for kodiId: %s (%s)", kodiId, imageUrl)

                query = (
                    '''
                    INSERT INTO art(media_id, media_type, type, url)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))

            else: # Only cache artwork if it changed
                if url != imageUrl:
                    cacheimage = True

                    # Only for the main backdrop, poster
                    if (window('emby_initialScan') != "true" and
                            imageType in ("fanart", "poster")):
                        # Delete current entry before updating with the new one
                        self.delete_cached_artwork(url)

                    log.info("Updating Art url for %s kodiId: %s (%s) -> (%s)",
                             imageType, kodiId, url, imageUrl)

                    query = ' '.join((

                        "UPDATE art",
                        "SET url = ?",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type = ?"
                    ))
                    cursor.execute(query, (imageUrl, kodiId, mediaType, imageType))

            # Cache fanart and poster in Kodi texture cache
            if cacheimage and imageType in ("fanart", "poster"):
                self.cache_texture(imageUrl)

    def delete_artwork(self, kodi_id, media_type, cursor):

        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?"
        ))
        cursor.execute(query, (kodi_id, media_type,))
        rows = cursor.fetchall()
        for row in rows:

            url = row[0]
            image_type = row[1]
            if image_type in ("poster", "fanart"):
                self.delete_cached_artwork(url)

    def delete_cached_artwork(self, url):
        # Only necessary to remove and apply a new backdrop or poster
        conn = kodiSQL('texture')
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
            cached_url = cursor.fetchone()[0]

        except TypeError:
            log.info("Could not find cached url")

        except OperationalError:
            log.info("Database is locked. Skip deletion process.")

        else: # Delete thumbnail as well as the entry
            thumbnails = xbmc.translatePath("special://thumbnails/%s", cached_url).decode('utf-8')
            log.info("Deleting cached thumbnail: %s" % thumbnails)
            xbmcvfs.delete(thumbnails)

            try:
                cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
                conn.commit()
            except OperationalError:
                log.debug("Issue deleting url from cache. Skipping.")

        finally:
            cursor.close()

    def get_people_artwork(self, people):
        # append imageurl if existing
        for person in people:

            image = ""
            person_id = person['Id']

            if "PrimaryImageTag" in person:
                image = (
                    "%s/emby/Items/%s/Images/Primary?"
                    "MaxWidth=400&MaxHeight=400&Index=0&Tag=%s"
                    % (self.server, person_id, person['PrimaryImageTag']))

            person['imageurl'] = image

        return people

    def get_user_artwork(self, item_id, item_type):
        # Load user information set by UserClient
        return "%s/emby/Users/%s/Images/%s?Format=original" % (self.server, item_id, item_type)

    def get_all_artwork(self, item, parent_info=False):

        item_id = item['Id']
        artworks = item['ImageTags']
        backdrops = item.get('BackdropImageTags', [])

        max_height = 10000
        max_width = 10000
        custom_query = ""

        if settings('compressArt') == "true":
            custom_query = "&Quality=90"

        if settings('enableCoverArt') == "false":
            custom_query += "&EnableImageEnhancers=false"

        all_artwork = {

            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }

        # Process backdrops
        for index, tag in enumerate(backdrops):
            artwork = (
                "%s/emby/Items/%s/Images/Backdrop/%s?"
                "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                % (self.server, item_id, index, max_width, max_height, tag, custom_query))
            all_artwork['Backdrop'].append(artwork)

        # Process the rest of the artwork
        for art in artworks:
            # Filter backcover
            if art != "BoxRear":
                tag = artworks[art]
                artwork = (
                    "%s/emby/Items/%s/Images/%s/0?"
                    "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                    % (self.server, item_id, art, max_width, max_height, tag, custom_query))
                all_artwork[art] = artwork

        # Process parent items if the main item is missing artwork
        if parent_info:

            # Process parent backdrops
            if not all_artwork['Backdrop']:

                parent_id = item.get('ParentBackdropItemId')
                if parent_id:
                    # If there is a parentId, go through the parent backdrop list
                    parent_backdrops = item['ParentBackdropImageTags']

                    for index, tag in enumerate(parent_backdrops):
                        artwork = ("%s/emby/Items/%s/Images/Backdrop/%s?"
                                   "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                                   % (self.server, parent_id, index, max_width, max_height,
                                      tag, custom_query))
                        all_artwork['Backdrop'].append(artwork)

            # Process the rest of the artwork
            parent_artwork = ['Logo', 'Art', 'Thumb']
            for parent_art in parent_artwork:

                if not all_artwork[parent_art]:

                    parent_id = item.get('Parent%sItemId' % parent_art)
                    if parent_id:

                        parent_tag = item['Parent%sImageTag' % parent_art]
                        artwork = ("%s/emby/Items/%s/Images/%s/0?"
                                   "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                                   % (self.server, parent_id, parent_art, max_width,
                                      max_height, parent_tag, custom_query))
                        all_artwork[parentart] = artwork

            # Parent album works a bit differently
            if not all_artwork['Primary']:

                parent_id = item.get('AlbumId')
                if parent_id and item.get('AlbumPrimaryImageTag'):

                    parent_tag = item['AlbumPrimaryImageTag']
                    artwork = ("%s/emby/Items/%s/Images/Primary/0?"
                               "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                               % (self.server, parent_id, max_width, max_height,
                                  parent_tag, custom_query))
                    all_artwork['Primary'] = artwork

        return all_artwork

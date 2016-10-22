# -*- coding: utf-8 -*-

###############################################################################

import logging
import json

import xbmc
import xbmcgui

import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
import playbackutils as pbutils
from utils import window, settings, CatchExceptions, tryDecode, tryEncode
from PlexFunctions import scrobble

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class KodiMonitor(xbmc.Monitor):

    def __init__(self):

        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = xbmc.Player()
        xbmc.Monitor.__init__(self)
        log.info("Kodi monitor started.")

    def onScanStarted(self, library):
        log.debug("Kodi library scan %s running." % library)
        if library == "video":
            window('plex_kodiScan', value="true")

    def onScanFinished(self, library):
        log.debug("Kodi library scan %s finished." % library)
        if library == "video":
            window('plex_kodiScan', clear=True)

    def onSettingsChanged(self):
        """
        Monitor the PKC settings for changes made by the user
        """
        currentLog = settings('logLevel')
        if window('plex_logLevel') != currentLog:
            # The log level changed, set new prop
            log.debug("New log level: %s" % currentLog)
            window('plex_logLevel', value=currentLog)
        current_context = "true" if settings('enableContext') == "true" else ""
        if window('plex_context') != current_context:
            log.info("New context setting: %s", current_context)
            window('plex_context', value=current_context)

    @CatchExceptions(warnuser=False)
    def onNotification(self, sender, method, data):

        if data:
            data = json.loads(data, 'utf-8')
            log.debug("Method: %s Data: %s" % (method, data))

        if method == "Player.OnPlay":
            self.PlayBackStart(data)

        elif method == "Player.OnStop":
            # Should refresh our video nodes, e.g. on deck
            # xbmc.executebuiltin('ReloadSkin()')
            pass

        elif method == "VideoLibrary.OnUpdate":
            # Manually marking as watched/unwatched
            playcount = data.get('playcount')
            item = data.get('item')
            try:
                kodiid = item['id']
                item_type = item['type']
            except (KeyError, TypeError):
                log.info("Item is invalid for playstate update.")
            else:
                # Send notification to the server.
                with embydb.GetEmbyDB() as emby_db:
                    emby_dbitem = emby_db.getItem_byKodiId(kodiid, item_type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    log.error("Could not find itemid in emby database for a "
                              "video library update")
                else:
                    # Stop from manually marking as watched unwatched, with actual playback.
                    if window('emby_skipWatched%s' % itemid) == "true":
                        # property is set in player.py
                        window('emby_skipWatched%s' % itemid, clear=True)
                    else:
                        # notify the server
                        if playcount != 0:
                            scrobble(itemid, 'watched')
                        else:
                            scrobble(itemid, 'unwatched')

        elif method == "VideoLibrary.OnRemove":
            # Removed function, because with plugin paths + clean library, it will wipe
            # entire library if user has permissions. Instead, use the emby context menu available
            # in Isengard and higher version
            pass
            '''try:
                kodiid = data['id']
                type = data['type']
            except (KeyError, TypeError):
                log.info("Item is invalid for emby deletion.")
            else:
                # Send the delete action to the server.
                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    log.info("Could not find itemid in emby database.")
                else:
                    if settings('skipContextMenu') != "true":
                        resp = xbmcgui.Dialog().yesno(
                                                heading="Confirm delete",
                                                line1="Delete file on Emby Server?")
                        if not resp:
                            log.info("User skipped deletion.")
                            embycursor.close()
                            return

                    url = "{server}/emby/Items/%s?format=json" % itemid
                    log.info("Deleting request: %s" % itemid)
                    doUtils.downloadUrl(url, action_type="DELETE")
                finally:
                    embycursor.close()'''

        elif method == "System.OnSleep":
            # Connection is going to sleep
            log.info("Marking the server as offline. SystemOnSleep activated.")
            window('plex_online', value="sleep")

        elif method == "System.OnWake":
            # Allow network to wake up
            xbmc.sleep(10000)
            window('plex_onWake', value="true")
            window('plex_online', value="false")

        elif method == "GUI.OnScreensaverDeactivated":
            if settings('dbSyncScreensaver') == "true":
                xbmc.sleep(5000)
                window('plex_runLibScan', value="full")

        elif method == "Playlist.OnClear":
            pass

    def PlayBackStart(self, data):
        """
        Called whenever a playback is started
        """
        # Get currently playing file - can take a while. Will be utf-8!
        try:
            currentFile = self.xbmcplayer.getPlayingFile()
        except:
            currentFile = None
            count = 0
            while currentFile is None:
                xbmc.sleep(100)
                try:
                    currentFile = self.xbmcplayer.getPlayingFile()
                except:
                    pass
                if count == 50:
                    log.info("No current File, cancel OnPlayBackStart...")
                    return
                else:
                    count += 1
        # Just to be on the safe side
        currentFile = tryDecode(currentFile)
        log.debug("Currently playing file is: %s" % currentFile)

        # Get the type of media we're playing
        try:
            typus = data['item']['type']
        except (TypeError, KeyError):
            log.info("Item is invalid for PMS playstate update.")
            return
        log.debug("Playing itemtype is (or appears to be): %s" % typus)

        # Try to get a Kodi ID
        # If PKC was used - native paths, not direct paths
        plexid = window('emby_%s.itemid' % tryEncode(currentFile))
        # Get rid of the '' if the window property was not set
        plexid = None if not plexid else plexid
        kodiid = None
        if plexid is None:
            log.debug('Did not get Plex id from window properties')
            try:
                kodiid = data['item']['id']
            except (TypeError, KeyError):
                log.debug('Did not get a Kodi id from Kodi, darn')
        # For direct paths, if we're not streaming something
        # When using Widgets, Kodi doesn't tell us shit so we need this hack
        if (kodiid is None and plexid is None and typus != 'song'
                and not currentFile.startswith('http')):
            try:
                filename = currentFile.rsplit('/', 1)[1]
                path = currentFile.rsplit('/', 1)[0] + '/'
            except IndexError:
                filename = currentFile.rsplit('\\', 1)[1]
                path = currentFile.rsplit('\\', 1)[0] + '\\'
            log.debug('Trying to figure out playing item from filename: %s '
                      'and path: %s' % (filename, path))
            with kodidb.GetKodiDB('video') as kodi_db:
                try:
                    kodiid, typus = kodi_db.getIdFromFilename(filename, path)
                except TypeError:
                    log.info('Abort playback report, could not id kodi item')
                    return

        if plexid is None:
            # Get Plex' item id
            with embydb.GetEmbyDB() as emby_db:
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, typus)
            try:
                plexid = emby_dbitem[0]
            except TypeError:
                log.info("No Plex id returned for kodiid %s. Aborting playback"
                         " report" % kodiid)
                return
        log.debug("Found Plex id %s for Kodi id %s for type %s"
                  % (plexid, kodiid, typus))

        # Set some stuff if Kodi initiated playback
        if ((settings('useDirectPaths') == "1" and not typus == "song")
                or
                (typus == "song" and settings('enableMusic') == "true")):
            if self.StartDirectPath(plexid,
                                    typus,
                                    tryEncode(currentFile)) is False:
                log.error('Could not initiate monitoring; aborting')
                return

        # Save currentFile for cleanup later and to be able to access refs
        window('plex_lastPlayedFiled', value=currentFile)
        window('plex_currently_playing_itemid', value=plexid)
        window("emby_%s.itemid" % tryEncode(currentFile), value=plexid)
        log.info('Finish playback startup')

    def StartDirectPath(self, plexid, type, currentFile):
        """
        Set some additional stuff if playback was initiated by Kodi, not PKC
        """
        result = self.doUtils('{server}/library/metadata/%s' % plexid)
        try:
            result[0].attrib
        except:
            log.error('Did not receive a valid XML for plexid %s.' % plexid)
            return False
        # Setup stuff, because playback was started by Kodi, not PKC
        pbutils.PlaybackUtils(result[0]).setProperties(
            currentFile, xbmcgui.ListItem())
        if type == "song" and settings('streamMusic') == "true":
            window('emby_%s.playmethod' % currentFile, value="DirectStream")
        else:
            window('emby_%s.playmethod' % currentFile, value="DirectPlay")
        log.debug('Window properties set for direct paths!')

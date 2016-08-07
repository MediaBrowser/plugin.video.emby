# -*- coding: utf-8 -*-

###############################################################################

import json

import xbmc
import xbmcgui

import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
import playbackutils as pbutils
import utils
from PlexFunctions import scrobble

###############################################################################


@utils.logging
class KodiMonitor(xbmc.Monitor):

    def __init__(self):

        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = xbmc.Player()
        xbmc.Monitor.__init__(self)
        self.logMsg("Kodi monitor started.", 1)

    def onScanStarted(self, library):
        self.logMsg("Kodi library scan %s running." % library, 2)
        if library == "video":
            utils.window('plex_kodiScan', value="true")

    def onScanFinished(self, library):
        self.logMsg("Kodi library scan %s finished." % library, 2)
        if library == "video":
            utils.window('plex_kodiScan', clear=True)

    def onSettingsChanged(self):
        # Monitor emby settings
        # Review reset setting at a later time, need to be adjusted to account for initial setup
        # changes.
        '''currentPath = utils.settings('useDirectPaths')
        if utils.window('plex_pluginpath') != currentPath:
            # Plugin path value changed. Offer to reset
            self.logMsg("Changed to playback mode detected", 1)
            utils.window('plex_pluginpath', value=currentPath)
            resp = xbmcgui.Dialog().yesno(
                                heading="Playback mode change detected",
                                line1=(
                                    "Detected the playback mode has changed. The database "
                                    "needs to be recreated for the change to be applied. "
                                    "Proceed?"))
            if resp:
                utils.reset()'''

        currentLog = utils.settings('logLevel')
        if utils.window('plex_logLevel') != currentLog:
            # The log level changed, set new prop
            self.logMsg("New log level: %s" % currentLog, 1)
            utils.window('plex_logLevel', value=currentLog)

    @utils.CatchExceptions(warnuser=False)
    def onNotification(self, sender, method, data):

        if data:
            data = json.loads(data, 'utf-8')
            self.logMsg("Method: %s Data: %s" % (method, data), 1)

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
                self.logMsg("Item is invalid for playstate update.", 1)
            else:
                # Send notification to the server.
                with embydb.GetEmbyDB() as emby_db:
                    emby_dbitem = emby_db.getItem_byKodiId(kodiid, item_type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    self.logMsg("Could not find itemid in emby database.", 1)
                else:
                    # Stop from manually marking as watched unwatched, with actual playback.
                    if utils.window('emby_skipWatched%s' % itemid) == "true":
                        # property is set in player.py
                        utils.window('emby_skipWatched%s' % itemid, clear=True)
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
                self.logMsg("Item is invalid for emby deletion.", 1)
            else:
                # Send the delete action to the server.
                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    self.logMsg("Could not find itemid in emby database.", 1)
                else:
                    if utils.settings('skipContextMenu') != "true":
                        resp = xbmcgui.Dialog().yesno(
                                                heading="Confirm delete",
                                                line1="Delete file on Emby Server?")
                        if not resp:
                            self.logMsg("User skipped deletion.", 1)
                            embycursor.close()
                            return

                    url = "{server}/emby/Items/%s?format=json" % itemid
                    self.logMsg("Deleting request: %s" % itemid)
                    doUtils.downloadUrl(url, action_type="DELETE")
                finally:
                    embycursor.close()'''

        elif method == "System.OnWake":
            # Allow network to wake up
            xbmc.sleep(10000)
            utils.window('plex_onWake', value="true")

        elif method == "GUI.OnScreensaverDeactivated":
            if utils.settings('dbSyncScreensaver') == "true":
                xbmc.sleep(5000)
                utils.window('plex_runLibScan', value="full")

        elif method == "Playlist.OnClear":
            pass

    def PlayBackStart(self, data):
        """
        Called whenever a playback is started
        """
        log = self.logMsg
        window = utils.window
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
                    log("No current File - Cancelling OnPlayBackStart...", -1)
                    return
                else:
                    count += 1
        # Just to be on the safe side
        currentFile = utils.tryDecode(currentFile)
        log("Currently playing file is: %s" % currentFile, 1)

        # Get the type of media we're playing
        try:
            typus = data['item']['type']
        except (TypeError, KeyError):
            log("Item is invalid for PMS playstate update.", 0)
            return
        log("Playing itemtype is (or appears to be): %s" % typus, 1)

        # Try to get a Kodi ID
        # If PKC was used - native paths, not direct paths
        plexid = utils.window('emby_%s.itemid'
                              % utils.tryEncode(currentFile))
        # Get rid of the '' if the window property was not set
        plexid = None if not plexid else plexid
        kodiid = None
        if plexid is None:
            log('Did not get Plex id from window properties', 1)
            try:
                kodiid = data['item']['id']
            except (TypeError, KeyError):
                log('Did not get a Kodi id from Kodi, darn', 1)
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
            log('Trying to figure out playing item from filename: %s and '
                'path: %s' % (filename, path), 1)
            with kodidb.GetKodiDB('video') as kodi_db:
                try:
                    kodiid, typus = kodi_db.getIdFromFilename(filename, path)
                except TypeError:
                    log('Aborting playback report', 1)
                    return

        if plexid is None:
            # Get Plex' item id
            with embydb.GetEmbyDB() as emby_db:
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, typus)
            try:
                plexid = emby_dbitem[0]
            except TypeError:
                log("No Plex id returned for kodiid %s" % kodiid, 1)
                log('Aborting playback report', 1)
                return
        log("Found Plex id %s for Kodi id %s for type %s"
            % (plexid, kodiid, typus), 1)

        # Set some stuff if Kodi initiated playback
        if ((utils.settings('useDirectPaths') == "1" and not typus == "song")
                or
                (typus == "song" and utils.settings('enableMusic') == "true")):
            if self.StartDirectPath(plexid,
                                    typus,
                                    utils.tryEncode(currentFile)) is False:
                log('Could not initiate monitoring; aborting', -1)
                return

        # Save currentFile for cleanup later and to be able to access refs
        window('plex_lastPlayedFiled', value=currentFile)
        window('Plex_currently_playing_itemid', value=plexid)
        window("emby_%s.itemid" % utils.tryEncode(currentFile), value=plexid)
        log('Finish playback startup', 1)

    def StartDirectPath(self, plexid, type, currentFile):
        """
        Set some additional stuff if playback was initiated by Kodi, not PKC
        """
        result = self.doUtils('{server}/library/metadata/%s' % plexid)
        try:
            result[0].attrib
        except:
            self.logMsg('Did not receive a valid XML for plexid %s.'
                        % plexid, -1)
            return False
        # Setup stuff, because playback was started by Kodi, not PKC
        pbutils.PlaybackUtils(result[0]).setProperties(
            currentFile, xbmcgui.ListItem())
        if type == "song" and utils.settings('streamMusic') == "true":
            utils.window('emby_%s.playmethod' % currentFile,
                         value="DirectStream")
        else:
            utils.window('emby_%s.playmethod' % currentFile,
                         value="DirectPlay")
        self.logMsg('Window properties set for direct paths!', 0)

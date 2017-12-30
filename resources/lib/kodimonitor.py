"""
PKC Kodi Monitoring implementation
"""
from logging import getLogger
from json import loads

from xbmc import Monitor, Player, sleep

import plexdb_functions as plexdb
from utils import window, settings, CatchExceptions, plex_command
from PlexFunctions import scrobble
from kodidb_functions import kodiid_from_filename
from plexbmchelper.subscribers import LOCKER
from PlexAPI import API
import json_rpc as js
import playlist_func as PL
import state
import variables as v

###############################################################################

LOG = getLogger("PLEX." + __name__)

# settings: window-variable
WINDOW_SETTINGS = {
    'plex_restricteduser': 'plex_restricteduser',
    'force_transcode_pix': 'plex_force_transcode_pix',
    'fetch_pms_item_number': 'fetch_pms_item_number'
}

# settings: state-variable (state.py)
# Need to use getattr and setattr!
STATE_SETTINGS = {
    'dbSyncIndicator': 'SYNC_DIALOG',
    'remapSMB': 'REMAP_PATH',
    'remapSMBmovieOrg': 'remapSMBmovieOrg',
    'remapSMBmovieNew': 'remapSMBmovieNew',
    'remapSMBtvOrg': 'remapSMBtvOrg',
    'remapSMBtvNew': 'remapSMBtvNew',
    'remapSMBmusicOrg': 'remapSMBmusicOrg',
    'remapSMBmusicNew': 'remapSMBmusicNew',
    'remapSMBphotoOrg': 'remapSMBphotoOrg',
    'remapSMBphotoNew': 'remapSMBphotoNew',
    'enableMusic': 'ENABLE_MUSIC',
    'enableBackgroundSync': 'BACKGROUND_SYNC'
}
###############################################################################


class KodiMonitor(Monitor):
    """
    PKC implementation of the Kodi Monitor class. Invoke only once.
    """
    def __init__(self, callback):
        self.mgr = callback
        self.xbmcplayer = Player()
        self.playqueue = self.mgr.playqueue
        Monitor.__init__(self)
        LOG.info("Kodi monitor started.")

    def onScanStarted(self, library):
        """
        Will be called when Kodi starts scanning the library
        """
        LOG.debug("Kodi library scan %s running." % library)
        if library == "video":
            window('plex_kodiScan', value="true")

    def onScanFinished(self, library):
        """
        Will be called when Kodi finished scanning the library
        """
        LOG.debug("Kodi library scan %s finished." % library)
        if library == "video":
            window('plex_kodiScan', clear=True)

    def onSettingsChanged(self):
        """
        Monitor the PKC settings for changes made by the user
        """
        LOG.debug('PKC settings change detected')
        changed = False
        # Reset the window variables from the settings variables
        for settings_value, window_value in WINDOW_SETTINGS.iteritems():
            if window(window_value) != settings(settings_value):
                changed = True
                LOG.debug('PKC window settings changed: %s is now %s',
                          settings_value, settings(settings_value))
                window(window_value, value=settings(settings_value))
                if settings_value == 'fetch_pms_item_number':
                    LOG.info('Requesting playlist/nodes refresh')
                    plex_command('RUN_LIB_SCAN', 'views')
        # Reset the state variables in state.py
        for settings_value, state_name in STATE_SETTINGS.iteritems():
            new = settings(settings_value)
            if new == 'true':
                new = True
            elif new == 'false':
                new = False
            if getattr(state, state_name) != new:
                changed = True
                LOG.debug('PKC state settings %s changed from %s to %s',
                          settings_value, getattr(state, state_name), new)
                setattr(state, state_name, new)
        # Special cases, overwrite all internal settings
        state.FULL_SYNC_INTERVALL = int(settings('fullSyncInterval')) * 60
        state.BACKGROUNDSYNC_SAFTYMARGIN = int(
            settings('backgroundsync_saftyMargin'))
        state.SYNC_THREAD_NUMBER = int(settings('syncThreadNumber'))
        # Never set through the user
        # state.KODI_PLEX_TIME_OFFSET = float(settings('kodiplextimeoffset'))
        if changed is True:
            # Assume that the user changed the settings so that we can now find
            # the path to all media files
            state.STOP_SYNC = False
            state.PATH_VERIFIED = False

    @CatchExceptions(warnuser=False)
    def onNotification(self, sender, method, data):
        """
        Called when a bunch of different stuff happens on the Kodi side
        """
        if data:
            data = loads(data, 'utf-8')
            LOG.debug("Method: %s Data: %s", method, data)

        if method == "Player.OnPlay":
            self.PlayBackStart(data)
        elif method == "Player.OnStop":
            # Should refresh our video nodes, e.g. on deck
            # xbmc.executebuiltin('ReloadSkin()')
            pass
        elif method == 'Playlist.OnAdd':
            self._playlist_onadd(data)
        elif method == 'Playlist.OnRemove':
            self._playlist_onremove(data)
        elif method == 'Playlist.OnClear':
            self._playlist_onclear(data)
        elif method == "VideoLibrary.OnUpdate":
            # Manually marking as watched/unwatched
            playcount = data.get('playcount')
            item = data.get('item')
            try:
                kodiid = item['id']
                item_type = item['type']
            except (KeyError, TypeError):
                LOG.info("Item is invalid for playstate update.")
            else:
                # Send notification to the server.
                with plexdb.Get_Plex_DB() as plexcur:
                    plex_dbitem = plexcur.getItem_byKodiId(kodiid, item_type)
                try:
                    itemid = plex_dbitem[0]
                except TypeError:
                    LOG.error("Could not find itemid in plex database for a "
                              "video library update")
                else:
                    # Stop from manually marking as watched unwatched, with
                    # actual playback.
                    if window('plex_skipWatched%s' % itemid) == "true":
                        # property is set in player.py
                        window('plex_skipWatched%s' % itemid, clear=True)
                    else:
                        # notify the server
                        if playcount > 0:
                            scrobble(itemid, 'watched')
                        else:
                            scrobble(itemid, 'unwatched')
        elif method == "VideoLibrary.OnRemove":
            pass
        elif method == "System.OnSleep":
            # Connection is going to sleep
            LOG.info("Marking the server as offline. SystemOnSleep activated.")
            window('plex_online', value="sleep")
        elif method == "System.OnWake":
            # Allow network to wake up
            sleep(10000)
            window('plex_onWake', value="true")
            window('plex_online', value="false")
        elif method == "GUI.OnScreensaverDeactivated":
            if settings('dbSyncScreensaver') == "true":
                sleep(5000)
                plex_command('RUN_LIB_SCAN', 'full')
        elif method == "System.OnQuit":
            LOG.info('Kodi OnQuit detected - shutting down')
            state.STOP_PKC = True

    @LOCKER.lockthis
    def _playlist_onadd(self, data):
        """
        Called if an item is added to a Kodi playlist. Example data dict:
        {
            u'item': {
                u'type': u'movie',
                u'id': 2},
            u'playlistid': 1,
            u'position': 0
        }
        Will NOT be called if playback initiated by Kodi widgets
        """
        playqueue = self.playqueue.playqueues[data['playlistid']]
        # Did PKC cause this add? Then lets not do anything
        if playqueue.is_kodi_onadd() is False:
            LOG.debug('PKC added this item to the playqueue - ignoring')
            return
        # Check whether we even need to update our known playqueue
        kodi_playqueue = js.playlist_get_items(data['playlistid'])
        if playqueue.old_kodi_pl == kodi_playqueue:
            # We already know the latest playqueue (e.g. because Plex
            # initiated playback)
            return
        # Playlist has been updated; need to tell Plex about it
        if playqueue.id is None:
            PL.init_Plex_playlist(playqueue, kodi_item=data['item'])
        else:
            PL.add_item_to_PMS_playlist(playqueue,
                                        data['position'],
                                        kodi_item=data['item'])
        # Make sure that we won't re-add this item
        playqueue.old_kodi_pl = kodi_playqueue

    @LOCKER.lockthis
    def _playlist_onremove(self, data):
        """
        Called if an item is removed from a Kodi playlist. Example data dict:
        {
            u'playlistid': 1,
            u'position': 0
        }
        """
        playqueue = self.playqueue.playqueues[data['playlistid']]
        # Did PKC cause this add? Then lets not do anything
        if playqueue.is_kodi_onremove() is False:
            LOG.debug('PKC removed this item already from playqueue - ignoring')
            return
        # Check whether we even need to update our known playqueue
        kodi_playqueue = js.playlist_get_items(data['playlistid'])
        if playqueue.old_kodi_pl == kodi_playqueue:
            # We already know the latest playqueue - nothing to do
            return
        PL.delete_playlist_item_from_PMS(playqueue, data['position'])
        playqueue.old_kodi_pl = kodi_playqueue

    @LOCKER.lockthis
    def _playlist_onclear(self, data):
        """
        Called if a Kodi playlist is cleared. Example data dict:
        {
            u'playlistid': 1,
        }
        """
        playqueue = self.playqueue.playqueues[data['playlistid']]
        if playqueue.is_kodi_onclear() is False:
            LOG.debug('PKC already cleared the playqueue - ignoring')
            return
        playqueue.clear()

    @LOCKER.lockthis
    def PlayBackStart(self, data):
        """
        Called whenever playback is started. Example data:
        {
            u'item': {u'type': u'movie', u'title': u''},
            u'player': {u'playerid': 1, u'speed': 1}
        }
        Unfortunately when using Widgets, Kodi doesn't tell us shit
        """
        # Get the type of media we're playing
        try:
            kodi_type = data['item']['type']
            playerid = data['player']['playerid']
        except (TypeError, KeyError):
            LOG.info('Aborting playback report - item invalid for updates %s',
                     data)
            return
        json_data = js.get_item(playerid)
        path = json_data.get('file')
        kodi_id = json_data.get('id')
        if not path and not kodi_id:
            LOG.info('Aborting playback report - no Kodi id or file for %s',
                     json_data)
            return
        # Plex id will NOT be set with direct paths
        plex_id = state.PLEX_IDS.get(path)
        try:
            plex_type = v.PLEX_TYPE_FROM_KODI_TYPE[kodi_type]
        except KeyError:
            plex_type = None
        # No Kodi id returned by Kodi, even if there is one. Ex: Widgets
        if plex_id and not kodi_id:
            with plexdb.Get_Plex_DB() as plex_db:
                plex_dbitem = plex_db.getItem_byId(plex_id)
            try:
                kodi_id = plex_dbitem[0]
            except TypeError:
                kodi_id = None
        # If using direct paths and starting playback from a widget
        if not path.startswith('http'):
            if not kodi_id:
                kodi_id = kodiid_from_filename(path, kodi_type)
            if not plex_id and kodi_id:
                with plexdb.Get_Plex_DB() as plex_db:
                    plex_dbitem = plex_db.getItem_byKodiId(kodi_id, kodi_type)
                try:
                    plex_id = plex_dbitem[0]
                    plex_type = plex_dbitem[2]
                except TypeError:
                    # No plex id, hence item not in the library. E.g. clips
                    pass
        info = js.get_player_props(playerid)
        state.PLAYER_STATES[playerid].update(info)
        state.PLAYER_STATES[playerid]['file'] = path
        state.PLAYER_STATES[playerid]['kodi_id'] = kodi_id
        state.PLAYER_STATES[playerid]['kodi_type'] = kodi_type
        state.PLAYER_STATES[playerid]['plex_id'] = plex_id
        state.PLAYER_STATES[playerid]['plex_type'] = plex_type
        LOG.debug('Set the player state: %s', state.PLAYER_STATES[playerid])
        # Check whether we need to init our playqueues (e.g. direct play)
        init = False
        playqueue = self.playqueue.playqueues[playerid]
        try:
            playqueue.items[info['position']]
        except IndexError:
            init = True
        if init is False and plex_id is not None:
            if plex_id != playqueue.items[info['position']].plex_id:
                init = True
        elif init is False and path != playqueue.items[info['position']].file:
            init = True
        if init is True:
            LOG.debug('Need to initialize Plex and PKC playqueue')
            if plex_id:
                PL.init_Plex_playlist(playqueue, plex_id=plex_id)
            else:
                PL.init_Plex_playlist(playqueue,
                                      kodi_item={'id': kodi_id,
                                                 'type': kodi_type,
                                                 'file': path})

    def StartDirectPath(self, plex_id, type, currentFile):
        """
        Set some additional stuff if playback was initiated by Kodi, not PKC
        """
        xml = self.doUtils('{server}/library/metadata/%s' % plex_id)
        try:
            xml[0].attrib
        except:
            LOG.error('Did not receive a valid XML for plex_id %s.' % plex_id)
            return False
        # Setup stuff, because playback was started by Kodi, not PKC
        api = API(xml[0])
        listitem = api.CreateListItemFromPlexItem()
        api.set_playback_win_props(currentFile, listitem)
        if type == "song" and settings('streamMusic') == "true":
            window('plex_%s.playmethod' % currentFile, value="DirectStream")
        else:
            window('plex_%s.playmethod' % currentFile, value="DirectPlay")
        LOG.debug('Window properties set for direct paths!')

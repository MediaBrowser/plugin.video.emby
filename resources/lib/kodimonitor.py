"""
PKC Kodi Monitoring implementation
"""
from logging import getLogger
from json import loads
from threading import Thread

from xbmc import Monitor, Player, sleep, getCondVisibility, getInfoLabel, \
    getLocalizedString
from xbmcgui import Window

import plexdb_functions as plexdb
from utils import window, settings, plex_command, thread_methods
from PlexFunctions import scrobble
from kodidb_functions import kodiid_from_filename
from plexbmchelper.subscribers import LOCKER
from playback import playback_triage
from initialsetup import set_replace_paths
import playqueue as PQ
import json_rpc as js
import playlist_func as PL
import state
import variables as v

###############################################################################

LOG = getLogger("PLEX." + __name__)

# settings: window-variable
WINDOW_SETTINGS = {
    'plex_restricteduser': 'plex_restricteduser',
    'force_transcode_pix': 'plex_force_transcode_pix'
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
    'enableBackgroundSync': 'BACKGROUND_SYNC',
    'fetch_pms_item_number': 'FETCH_PMS_ITEM_NUMBER'
}

###############################################################################


class KodiMonitor(Monitor):
    """
    PKC implementation of the Kodi Monitor class. Invoke only once.
    """
    def __init__(self):
        self.xbmcplayer = Player()
        Monitor.__init__(self)
        for playerid in state.PLAYER_STATES:
            state.PLAYER_STATES[playerid] = dict(state.PLAYSTATE)
            state.OLD_PLAYER_STATES[playerid] = dict(state.PLAYSTATE)
        LOG.info("Kodi monitor started.")

    def onScanStarted(self, library):
        """
        Will be called when Kodi starts scanning the library
        """
        LOG.debug("Kodi library scan %s running.", library)
        if library == "video":
            window('plex_kodiScan', value="true")

    def onScanFinished(self, library):
        """
        Will be called when Kodi finished scanning the library
        """
        LOG.debug("Kodi library scan %s finished.", library)
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
                if state_name == 'FETCH_PMS_ITEM_NUMBER':
                    LOG.info('Requesting playlist/nodes refresh')
                    plex_command('RUN_LIB_SCAN', 'views')
        # Special cases, overwrite all internal settings
        set_replace_paths()
        state.FULL_SYNC_INTERVALL = int(settings('fullSyncInterval')) * 60
        state.BACKGROUNDSYNC_SAFTYMARGIN = int(
            settings('backgroundsync_saftyMargin'))
        state.SYNC_THREAD_NUMBER = int(settings('syncThreadNumber'))
        state.SSL_CERT_PATH = settings('sslcert') \
            if settings('sslcert') != 'None' else None
        # Never set through the user
        # state.KODI_PLEX_TIME_OFFSET = float(settings('kodiplextimeoffset'))
        if changed is True:
            # Assume that the user changed the settings so that we can now find
            # the path to all media files
            state.STOP_SYNC = False
            state.PATH_VERIFIED = False

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
            if playcount is None or item is None:
                return
            try:
                kodiid = item['id']
                item_type = item['type']
            except (KeyError, TypeError):
                LOG.info("Item is invalid for playstate update.")
                return
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
        old = state.OLD_PLAYER_STATES[data['playlistid']]
        if (not state.DIRECT_PATHS and data['position'] == 0 and
                not PQ.PLAYQUEUES[data['playlistid']].items and
                data['item']['type'] == old['kodi_type'] and
                data['item']['id'] == old['kodi_id']):
            # Hack we need for RESUMABLE items because Kodi lost the path of the
            # last played item that is now being replayed (see playback.py's
            # Player().play()) Also see playqueue.py _compare_playqueues()
            LOG.info('Detected re-start of playback of last item')
            kwargs = {
                'plex_id': old['plex_id'],
                'plex_type': old['plex_type'],
                'path': old['file'],
                'resolve': False
            }
            thread = Thread(target=playback_triage, kwargs=kwargs)
            thread.start()
            return

    def _playlist_onremove(self, data):
        """
        Called if an item is removed from a Kodi playlist. Example data dict:
        {
            u'playlistid': 1,
            u'position': 0
        }
        """
        pass

    @LOCKER.lockthis
    def _playlist_onclear(self, data):
        """
        Called if a Kodi playlist is cleared. Example data dict:
        {
            u'playlistid': 1,
        }
        """
        playqueue = PQ.PLAYQUEUES[data['playlistid']]
        if not playqueue.is_pkc_clear():
            playqueue.clear(kodi=False)
        else:
            LOG.debug('Detected PKC clear - ignoring')

    def _get_ids(self, json_item):
        """
        """
        kodi_id = json_item.get('id')
        kodi_type = json_item.get('type')
        path = json_item.get('file')
        if not path and not kodi_id:
            LOG.debug('Aborting playback report - no Kodi id or file for %s',
                      json_item)
            raise RuntimeError
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
        return kodi_id, kodi_type, plex_id, plex_type

    @staticmethod
    def _add_remaining_items_to_playlist(playqueue):
        """
        Adds all but the very first item of the Kodi playlist to the Plex
        playqueue
        """
        items = js.playlist_get_items(playqueue.playlistid)
        if not items:
            LOG.error('Could not retrieve Kodi playlist items')
            return
        # Remove first item
        items.pop(0)
        try:
            for i, item in enumerate(items):
                PL.add_item_to_PMS_playlist(playqueue, i + 1, kodi_item=item)
        except PL.PlaylistError:
            LOG.info('Could not build Plex playlist for: %s', items)

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
        if playerid == -1:
            # Kodi might return -1 for "last player"
            try:
                playerid = js.get_player_ids()[0]
            except IndexError:
                LOG.error('Could not retreive active player - aborting')
                return
        # Remember that this player has been active
        state.ACTIVE_PLAYERS.append(playerid)
        playqueue = PQ.PLAYQUEUES[playerid]
        info = js.get_player_props(playerid)
        json_item = js.get_item(playerid)
        path = json_item.get('file')
        pos = info['position'] if info['position'] != -1 else 0
        LOG.debug('Detected position %s for %s', pos, playqueue)
        status = state.PLAYER_STATES[playerid]
        try:
            item = playqueue.items[pos]
        except IndexError:
            try:
                kodi_id, kodi_type, plex_id, plex_type = self._get_ids(json_item)
            except RuntimeError:
                return
            LOG.info('Need to initialize Plex and PKC playqueue')
            try:
                if plex_id:
                    item = PL.init_Plex_playlist(playqueue, plex_id=plex_id)
                else:
                    item = PL.init_Plex_playlist(playqueue,
                                                 kodi_item={'id': kodi_id,
                                                            'type': kodi_type,
                                                            'file': path})
            except PL.PlaylistError:
                LOG.info('Could not initialize our playlist')
                # Avoid errors
                item = PL.Playlist_Item()
            # Set the Plex container key (e.g. using the Plex playqueue)
            container_key = None
            if info['playlistid'] != -1:
                # -1 is Kodi's answer if there is no playlist
                container_key = PQ.PLAYQUEUES[playerid].id
            if container_key is not None:
                container_key = '/playQueues/%s' % container_key
            elif plex_id is not None:
                container_key = '/library/metadata/%s' % plex_id
            LOG.debug('Set the Plex container_key to: %s', container_key)
        else:
            kodi_id = item.kodi_id
            kodi_type = item.kodi_type
            plex_id = item.plex_id
            plex_type = item.plex_type
            if playqueue.id:
                container_key = '/playQueues/%s' % playqueue.id
            else:
                container_key = '/library/metadata/%s' % plex_id
        status.update(info)
        status['container_key'] = container_key
        status['file'] = path
        status['kodi_id'] = kodi_id
        status['kodi_type'] = kodi_type
        status['plex_id'] = plex_id
        status['plex_type'] = plex_type
        status['playmethod'] = item.playmethod
        status['playcount'] = item.playcount
        LOG.debug('Set the player state: %s', status)


@thread_methods
class SpecialMonitor(Thread):
    """
    Detect the resume dialog for widgets.
    Could also be used to detect external players (see Emby implementation)
    """
    def run(self):
        LOG.info("----====# Starting Special Monitor #====----")
        # "Start from beginning", "Play from beginning"
        strings = (getLocalizedString(12021), getLocalizedString(12023))
        while not self.stopped():
            if (getCondVisibility('Window.IsVisible(DialogContextMenu.xml)') and
                    getInfoLabel('Control.GetLabel(1002)') in strings):
                # Remember that the item IS indeed resumable
                state.RESUMABLE = True
                control = int(Window(10106).getFocusId())
                if control == 1002:
                    # Start from beginning
                    state.RESUME_PLAYBACK = False
                elif control == 1001:
                    state.RESUME_PLAYBACK = True
                else:
                    # User chose something else from the context menu
                    state.RESUME_PLAYBACK = False
            sleep(200)
        LOG.info("#====---- Special Monitor Stopped ----====#")

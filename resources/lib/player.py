# -*- coding: utf-8 -*-

###############################################################################
from logging import getLogger

from xbmc import Player

from utils import window, DateToKodi, getUnixTimestamp, kodi_time_to_millis
from downloadutils import DownloadUtils as DU
import plexdb_functions as plexdb
import kodidb_functions as kodidb
from plexbmchelper.subscribers import LOCKER
import variables as v
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


class PKC_Player(Player):
    def __init__(self):
        Player.__init__(self)
        LOG.info("Started playback monitor.")

    def onPlayBackStarted(self):
        """
        Will be called when xbmc starts playing a file.
        """
        pass

    def onPlayBackPaused(self):
        """
        Will be called when playback is paused
        """
        pass

    def onPlayBackResumed(self):
        """
        Will be called when playback is resumed
        """
        pass

    def onPlayBackSeek(self, time, seekOffset):
        """
        Will be called when user seeks to a certain time during playback
        """
        pass

    def onPlayBackStopped(self):
        """
        Will be called when playback is stopped by the user
        """
        LOG.info("ONPLAYBACK_STOPPED")
        self.cleanup_playback()

    def onPlayBackEnded(self):
        """
        Will be called when playback ends due to the media file being finished
        """
        LOG.info("ONPLAYBACK_ENDED")
        self.cleanup_playback()

    @LOCKER.lockthis
    def cleanup_playback(self):
        """
        PKC cleanup after playback ends/is stopped
        """
        # We might have saved a transient token from a user flinging media via
        # Companion (if we could not use the playqueue to store the token)
        state.PLEX_TRANSIENT_TOKEN = None
        for item in ('plex_currently_playing_itemid',
                     'plex_customplaylist',
                     'plex_customplaylist.seektime',
                     'plex_forcetranscode'):
            window(item, clear=True)
        for playerid in state.ACTIVE_PLAYERS:
            status = state.PLAYER_STATES[playerid]
            # Check whether we need to mark an item as completely watched
            if not status['kodi_id'] or not status['plex_id']:
                LOG.info('No PKC info safed for the element just played by Kodi'
                         ' player %s', playerid)
                continue
            # Stop transcoding
            if status['playmethod'] == 'Transcode':
                LOG.info('Tell the PMS to stop transcoding')
                DU().downloadUrl(
                    '{server}/video/:/transcode/universal/stop',
                    parameters={'session': v.PKC_MACHINE_IDENTIFIER})
            if status['plex_type'] == v.PLEX_TYPE_SONG:
                LOG.debug('Song has been played, not cleaning up playstate')
                continue
            resume = kodi_time_to_millis(status['time'])
            runtime = kodi_time_to_millis(status['totaltime'])
            LOG.info('Item playback progress %s out of %s', resume, runtime)
            if not resume or not runtime:
                continue
            complete = float(resume) / float(runtime)
            LOG.info("Percent complete: %s. Mark played at: %s",
                     complete, v.MARK_PLAYED_AT)
            if complete >= v.MARK_PLAYED_AT:
                # Tell Kodi that we've finished watching (Plex knows)
                with plexdb.Get_Plex_DB() as plex_db:
                    plex_dbitem = plex_db.getItem_byId(status['plex_id'])
                file_id = plex_dbitem[1] if plex_dbitem else None
                if file_id is None:
                    LOG.error('No file_id found for %s', status)
                    continue
                with kodidb.GetKodiDB('video') as kodi_db:
                    kodi_db.addPlaystate(
                        file_id,
                        None,
                        None,
                        status['playcount'] + 1,
                        DateToKodi(getUnixTimestamp()))
                LOG.info('Marked plex element %s as completely watched',
                         status['plex_id'])
        # As all playback has halted, reset the players that have been active
        state.ACTIVE_PLAYERS = []
        for playerid in state.PLAYER_STATES:
            state.PLAYER_STATES[playerid] = dict(state.PLAYSTATE)
        LOG.info('Finished PKC playback cleanup')

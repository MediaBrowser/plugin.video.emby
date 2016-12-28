# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import Lock, Thread

import xbmc

from utils import window, ThreadMethods, ThreadMethodsAdditionalSuspend, \
    Lock_Function
import playlist_func as PL
from PlexFunctions import ConvertPlexToKodiTime

###############################################################################
log = logging.getLogger("PLEX."+__name__)

# Lock used to lock methods
lock = Lock()
lockmethod = Lock_Function(lock)
###############################################################################


@ThreadMethodsAdditionalSuspend('plex_serverStatus')
@ThreadMethods
class Playqueue(Thread):
    """
    Monitors Kodi's playqueues for changes on the Kodi side
    """
    # Borg - multiple instances, shared state
    __shared_state = {}
    playqueues = None

    @lockmethod.lockthis
    def __init__(self, callback=None):
        self.__dict__ = self.__shared_state
        Thread.__init__(self)
        if self.playqueues is not None:
            return
        self.mgr = callback
        self.player = xbmc.Player()

        # Initialize Kodi playqueues
        self.playqueues = []
        for queue in PL.get_kodi_playqueues():
            playqueue = PL.Playqueue_Object()
            playqueue.playlistid = queue['playlistid']
            playqueue.type = queue['type']
            # Initialize each Kodi playlist
            if playqueue.type == 'audio':
                playqueue.kodi_pl = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            elif playqueue.type == 'video':
                playqueue.kodi_pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            else:
                # Currently, only video or audio playqueues available
                playqueue.kodi_pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.playqueues.append(playqueue)
        # sort the list by their playlistid, just in case
        self.playqueues = sorted(
            self.playqueues, key=lambda i: i.playlistid)
        log.debug('Initialized the Kodi play queues: %s' % self.playqueues)

    def get_playqueue_from_type(self, typus):
        """
        Returns the playqueue according to the typus ('video', 'audio',
        'picture') passed in
        """
        for playqueue in self.playqueues:
            if playqueue.type == typus:
                break
        else:
            raise ValueError('Wrong type was passed in: %s' % typus)
        return playqueue

    def get_playqueue_from_playerid(self, kodi_player_id):
        for playqueue in self.playqueues:
            if playqueue.playlistid == kodi_player_id:
                break
        else:
            raise ValueError('Wrong kodi_player_id passed was passed in: %s'
                             % kodi_player_id)
        return playqueue

    @lockmethod.lockthis
    def update_playqueue_from_PMS(self,
                                  playqueue,
                                  playqueue_id=None,
                                  repeat=None):
        """
        Completely updates the Kodi playqueue with the new Plex playqueue. Pass
        in playqueue_id if we need to fetch a new playqueue

        repeat = 0, 1, 2
        """
        log.info('New playqueue received, updating!')
        PL.update_playlist_from_PMS(playqueue, playqueue_id, repeat)
        log.debug('Updated playqueue: %s' % playqueue)

        window('plex_customplaylist', value="true")
        if playqueue.selectedItemOffset not in (None, "0"):
            window('plex_customplaylist.seektime',
                   str(ConvertPlexToKodiTime(playqueue.selectedItemOffset)))
        for startpos, item in enumerate(playqueue.items):
            if item.ID == playqueue.selectedItemID:
                break
        else:
            startpos = None
        # Start playback
        if startpos:
            self.player.play(playqueue.kodi_pl, startpos=startpos)
        else:
            self.player.play(playqueue.kodi_pl)
        log.debug('Playqueue at the end: %s' % playqueue)
        playqueue.log_Kodi_playlist()

    @lockmethod.lockthis
    def update_playqueue_with_companion(self, data):
        """
        Feed with Plex companion data
        """

        # Get the correct queue

    @lockmethod.lockthis
    def kodi_onadd(self, data):
        """
        Called if an item is added to a Kodi playqueue. Data is Kodi JSON-RPC
        output, e.g.
            {
                u'item': {u'type': u'movie', u'id': 3},
                u'playlistid': 1,
                u'position': 0
            }
        """
        for playqueue in self.playqueues:
            if playqueue.playlistid == data['playlistid']:
                break
        if playqueue.PKC_playlist_edits:
            old = (data['item'].get('id') if data['item'].get('id')
                   else data['item'].get('file'))
            for i, item in enumerate(playqueue.PKC_playlist_edits):
                if old == item:
                    log.debug('kodimonitor told us of a PKC edit - ignore.')
                    del playqueue.PKC_playlist_edits[i]
                    return
        if playqueue.ID is None:
            # Need to initialize the queue for the first time
            PL.init_Plex_playlist(playqueue, kodi_item=data['item'])
        else:
            PL.add_playlist_item(playqueue, data['item'], data['position'])
            log.debug('Added a new item to the playqueue: %s' % playqueue)

    @lockmethod.lockthis
    def _compare_playqueues(self, playqueue, new):
        """
        Used to poll the Kodi playqueue and update the Plex playqueue if needed
        """
        old = playqueue.old_kodi_pl
        log.debug('Comparing new Kodi playqueue %s with our play queue %s'
                  % (new, playqueue))
        index = list(range(0, len(old)))
        for i, new_item in enumerate(new):
            for j, old_item in enumerate(old):
                if old_item.get('id') is None:
                    identical = old_item['file'] == new_item['file']
                else:
                    identical = (old_item['id'] == new_item['id'] and
                                 old_item['type'] == new_item['type'])
                if j == 0 and identical:
                    del old[j], index[j]
                    break
                elif identical:
                    # item now at pos i has been moved from original pos i+j
                    PL.move_playlist_item(playqueue, i + j, i)
                    # Delete the item we just found
                    del old[i + j], index[i + j]
                    break
            else:
                # Did not find element i in the old list - Kodi monitor should
                # pick this up!
                # PL.add_playlist_item(playqueue, new_item, i-1)
                pass
        for i in index:
            # Still got some old items left that need deleting
            PL.delete_playlist_item(playqueue, i)
        log.debug('New playqueue: %s' % playqueue)

    def run(self):
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        log.info("----===## Starting PlayQueue client ##===----")
        # Initialize the playqueues, if Kodi already got items in them
        for playqueue in self.playqueues:
            for i, item in enumerate(PL.get_kodi_playlist_items(playqueue)):
                if i == 0:
                    PL.init_Plex_playlist(playqueue, kodi_item=item)
                else:
                    PL.add_playlist_item(playqueue, item, i)
        while not threadStopped():
            while threadSuspended():
                if threadStopped():
                    break
                xbmc.sleep(1000)
            for playqueue in self.playqueues:
                if not playqueue.items:
                    # Skip empty playqueues as items can't be modified
                    continue
                kodi_playqueue = PL.get_kodi_playlist_items(playqueue)
                if playqueue.old_kodi_pl != kodi_playqueue:
                    # compare old and new playqueue
                    self._compare_playqueues(playqueue, kodi_playqueue)
                    playqueue.old_kodi_pl = list(kodi_playqueue)
            xbmc.sleep(1000)
        log.info("----===## PlayQueue client stopped ##===----")

# -*- coding: utf-8 -*-
###############################################################################
import logging
from threading import RLock, Thread

from xbmc import sleep, Player, PlayList, PLAYLIST_MUSIC, PLAYLIST_VIDEO

from utils import window, ThreadMethods, ThreadMethodsAdditionalSuspend
import playlist_func as PL
from PlexFunctions import ConvertPlexToKodiTime
from playbackutils import PlaybackUtils

###############################################################################
log = logging.getLogger("PLEX."+__name__)

# Lock used for playqueue manipulations
lock = RLock()
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

    def __init__(self, callback=None):
        self.__dict__ = self.__shared_state
        if self.playqueues is not None:
            return
        self.mgr = callback

        # Initialize Kodi playqueues
        with lock:
            self.playqueues = []
            for queue in PL.get_kodi_playqueues():
                playqueue = PL.Playqueue_Object()
                playqueue.playlistid = queue['playlistid']
                playqueue.type = queue['type']
                # Initialize each Kodi playlist
                if playqueue.type == 'audio':
                    playqueue.kodi_pl = PlayList(PLAYLIST_MUSIC)
                elif playqueue.type == 'video':
                    playqueue.kodi_pl = PlayList(PLAYLIST_VIDEO)
                else:
                    # Currently, only video or audio playqueues available
                    playqueue.kodi_pl = PlayList(PLAYLIST_VIDEO)
                self.playqueues.append(playqueue)
            # sort the list by their playlistid, just in case
            self.playqueues = sorted(
                self.playqueues, key=lambda i: i.playlistid)
        log.debug('Initialized the Kodi play queues: %s' % self.playqueues)
        Thread.__init__(self)

    def get_playqueue_from_type(self, typus):
        """
        Returns the playqueue according to the typus ('video', 'audio',
        'picture') passed in
        """
        with lock:
            for playqueue in self.playqueues:
                if playqueue.type == typus:
                    break
            else:
                raise ValueError('Wrong playlist type passed in: %s' % typus)
            return playqueue

    def update_playqueue_from_PMS(self,
                                  playqueue,
                                  playqueue_id=None,
                                  repeat=None,
                                  offset=None):
        """
        Completely updates the Kodi playqueue with the new Plex playqueue. Pass
        in playqueue_id if we need to fetch a new playqueue

        repeat = 0, 1, 2
        offset = time offset in Plextime (milliseconds)
        """
        log.info('New playqueue %s received from Plex companion with offset '
                 '%s, repeat %s' % (playqueue_id, offset, repeat))
        with lock:
            xml = PL.get_PMS_playlist(playqueue, playqueue_id)
            if xml is None:
                log.error('Could not get playqueue ID %s' % playqueue_id)
                return
            playqueue.clear()
            PL.get_playlist_details_from_xml(playqueue, xml)
            PlaybackUtils(xml, playqueue).play_all()
            playqueue.repeat = 0 if not repeat else int(repeat)
            window('plex_customplaylist', value="true")
            if offset not in (None, "0"):
                window('plex_customplaylist.seektime',
                       str(ConvertPlexToKodiTime(offset)))
            for startpos, item in enumerate(playqueue.items):
                if item.ID == playqueue.selectedItemID:
                    break
            else:
                startpos = 0
            # Start playback. Player does not return in time
            log.debug('Playqueues after Plex Companion update are now: %s'
                      % self.playqueues)
            thread = Thread(target=Player().play,
                            args=(playqueue.kodi_pl,
                                  None,
                                  False,
                                  startpos))
            thread.setDaemon(True)
            thread.start()

    def _compare_playqueues(self, playqueue, new):
        """
        Used to poll the Kodi playqueue and update the Plex playqueue if needed
        """
        old = list(playqueue.items)
        index = list(range(0, len(old)))
        log.debug('Comparing new Kodi playqueue %s with our play queue %s'
                  % (new, old))
        for i, new_item in enumerate(new):
            for j, old_item in enumerate(old):
                if self.threadStopped():
                    # Chances are that we got an empty Kodi playlist due to
                    # Kodi exit
                    return
                if new_item.get('id') is None:
                    identical = old_item.file == new_item['file']
                else:
                    identical = (old_item.kodi_id == new_item['id'] and
                                 old_item.kodi_type == new_item['type'])
                if j == 0 and identical:
                    del old[j], index[j]
                    break
                elif identical:
                    log.debug('Detected playqueue item %s moved to position %s'
                              % (i+j, i))
                    PL.move_playlist_item(playqueue, i + j, i)
                    del old[j], index[j]
                    break
            else:
                log.debug('Detected new Kodi element: %s' % new_item)
                if playqueue.ID is None:
                    PL.init_Plex_playlist(playqueue,
                                          kodi_item=new_item)
                else:
                    PL.add_item_to_PMS_playlist(playqueue,
                                                i,
                                                kodi_item=new_item)
        for i in reversed(index):
            log.debug('Detected deletion of playqueue element at pos %s' % i)
            PL.delete_playlist_item_from_PMS(playqueue, i)
        log.debug('Done comparing playqueues')

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
                    PL.add_item_to_PMS_playlist(playqueue, i, kodi_item=item)
        while not threadStopped():
            while threadSuspended():
                if threadStopped():
                    break
                sleep(1000)
            with lock:
                for playqueue in self.playqueues:
                    kodi_playqueue = PL.get_kodi_playlist_items(playqueue)
                    if playqueue.old_kodi_pl != kodi_playqueue:
                        # compare old and new playqueue
                        self._compare_playqueues(playqueue, kodi_playqueue)
                        playqueue.old_kodi_pl = list(kodi_playqueue)
            sleep(50)
        log.info("----===## PlayQueue client stopped ##===----")

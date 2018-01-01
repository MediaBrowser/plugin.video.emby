"""
Monitors the Kodi playqueue and adjusts the Plex playqueue accordingly
"""
from logging import getLogger
from threading import RLock, Thread

from xbmc import sleep, Player, PlayList, PLAYLIST_MUSIC, PLAYLIST_VIDEO

from utils import window, thread_methods
import playlist_func as PL
from PlexFunctions import ConvertPlexToKodiTime, GetAllPlexChildren
from PlexAPI import API
from playbackutils import PlaybackUtils
import json_rpc as js
import variables as v

###############################################################################
LOG = getLogger("PLEX." + __name__)

# lock used for playqueue manipulations
LOCK = RLock()
PLUGIN = 'plugin://%s' % v.ADDON_ID
###############################################################################


@thread_methods(add_suspends=['PMS_STATUS'])
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
            LOG.debug('Playqueue thread has already been initialized')
            Thread.__init__(self)
            return
        self.mgr = callback

        # Initialize Kodi playqueues
        with LOCK:
            self.playqueues = []
            for queue in js.get_playlists():
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
                    # Overwrite 'picture' with 'photo'
                    playqueue.type = v.KODI_TYPE_PHOTO
                self.playqueues.append(playqueue)
            # sort the list by their playlistid, just in case
            self.playqueues = sorted(
                self.playqueues, key=lambda i: i.playlistid)
        LOG.debug('Initialized the Kodi play queues: %s', self.playqueues)
        Thread.__init__(self)

    def get_playqueue_from_type(self, typus):
        """
        Returns the playqueue according to the typus ('video', 'audio',
        'picture') passed in
        """
        with LOCK:
            for playqueue in self.playqueues:
                if playqueue.type == typus:
                    break
            else:
                raise ValueError('Wrong playlist type passed in: %s' % typus)
            return playqueue

    def init_playqueue_from_plex_children(self, plex_id, transient_token=None):
        """
        Init a new playqueue e.g. from an album. Alexa does this

        Returns the Playlist_Object
        """
        xml = GetAllPlexChildren(plex_id)
        try:
            xml[0].attrib
        except (TypeError, IndexError, AttributeError):
            LOG.error('Could not download the PMS xml for %s', plex_id)
            return
        playqueue = self.get_playqueue_from_type(
            v.KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[xml[0].attrib['type']])
        playqueue.clear()
        for i, child in enumerate(xml):
            api = API(child)
            PL.add_item_to_playlist(playqueue, i, plex_id=api.getRatingKey())
        playqueue.plex_transient_token = transient_token
        LOG.debug('Firing up Kodi player')
        Player().play(playqueue.kodi_pl, None, False, 0)
        return playqueue

    def update_playqueue_from_PMS(self,
                                  playqueue,
                                  playqueue_id=None,
                                  repeat=None,
                                  offset=None,
                                  transient_token=None):
        """
        Completely updates the Kodi playqueue with the new Plex playqueue. Pass
        in playqueue_id if we need to fetch a new playqueue

        repeat = 0, 1, 2
        offset = time offset in Plextime (milliseconds)
        """
        LOG.info('New playqueue %s received from Plex companion with offset '
                 '%s, repeat %s', playqueue_id, offset, repeat)
        # Safe transient token from being deleted
        if transient_token is None:
            transient_token = playqueue.plex_transient_token
        with LOCK:
            xml = PL.get_PMS_playlist(playqueue, playqueue_id)
            playqueue.clear()
            try:
                PL.get_playlist_details_from_xml(playqueue, xml)
            except KeyError:
                LOG.error('Could not get playqueue ID %s', playqueue_id)
                return
            playqueue.repeat = 0 if not repeat else int(repeat)
            playqueue.plex_transient_token = transient_token
            PlaybackUtils(xml, playqueue).play_all()
            window('plex_customplaylist', value="true")
            if offset not in (None, "0"):
                window('plex_customplaylist.seektime',
                       str(ConvertPlexToKodiTime(offset)))
            for startpos, item in enumerate(playqueue.items):
                if item.id == playqueue.selectedItemID:
                    break
            else:
                startpos = 0
            # Start playback. Player does not return in time
            LOG.debug('Playqueues after Plex Companion update are now: %s',
                      self.playqueues)
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
        LOG.debug('Comparing new Kodi playqueue %s with our play queue %s',
                  new, old)
        if self.thread_stopped():
            # Chances are that we got an empty Kodi playlist due to
            # Kodi exit
            return
        for i, new_item in enumerate(new):
            if (new_item['file'].startswith('plugin://') and
                    not new_item['file'].startswith(PLUGIN)):
                # Ignore new media added by other addons
                continue
            for j, old_item in enumerate(old):
                try:
                    if (old_item.file.startswith('plugin://') and
                            not old_item['file'].startswith(PLUGIN)):
                        # Ignore media by other addons
                        continue
                except (TypeError, AttributeError):
                    # were not passed a filename; ignore
                    pass
                if new_item.get('id') is None:
                    identical = old_item.file == new_item['file']
                else:
                    identical = (old_item.kodi_id == new_item['id'] and
                                 old_item.kodi_type == new_item['type'])
                if j == 0 and identical:
                    del old[j], index[j]
                    break
                elif identical:
                    LOG.debug('Detected playqueue item %s moved to position %s',
                              i+j, i)
                    PL.move_playlist_item(playqueue, i + j, i)
                    del old[j], index[j]
                    break
            else:
                LOG.debug('Detected new Kodi element at position %s: %s ',
                          i, new_item)
                if playqueue.id is None:
                    PL.init_Plex_playlist(playqueue,
                                          kodi_item=new_item)
                else:
                    PL.add_item_to_PMS_playlist(playqueue,
                                                i,
                                                kodi_item=new_item)
                for j in range(i, len(index)):
                    index[j] += 1
        for i in reversed(index):
            LOG.debug('Detected deletion of playqueue element at pos %s', i)
            PL.delete_playlist_item_from_PMS(playqueue, i)
        LOG.debug('Done comparing playqueues')

    def run(self):
        thread_stopped = self.thread_stopped
        thread_suspended = self.thread_suspended
        LOG.info("----===## Starting PlayQueue client ##===----")
        # Initialize the playqueues, if Kodi already got items in them
        for playqueue in self.playqueues:
            for i, item in enumerate(js.playlist_get_items(playqueue.id)):
                if i == 0:
                    PL.init_Plex_playlist(playqueue, kodi_item=item)
                else:
                    PL.add_item_to_PMS_playlist(playqueue, i, kodi_item=item)
        while not thread_stopped():
            while thread_suspended():
                if thread_stopped():
                    break
                sleep(1000)
            # with LOCK:
            #     for playqueue in self.playqueues:
            #         kodi_playqueue = js.playlist_get_items(playqueue.id)
            #         if playqueue.old_kodi_pl != kodi_playqueue:
            #             # compare old and new playqueue
            #             self._compare_playqueues(playqueue, kodi_playqueue)
            #             playqueue.old_kodi_pl = list(kodi_playqueue)
            #             # Still sleep a bit so Kodi does not become
            #             # unresponsive
            #             sleep(10)
            #             continue
            sleep(200)
        LOG.info("----===## PlayQueue client stopped ##===----")

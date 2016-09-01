# -*- coding: utf-8 -*-

###############################################################################

import logging
import json
from urllib import urlencode
from threading import Lock
from functools import wraps

import xbmc

import embydb_functions as embydb
from utils import window, tryEncode
import playbackutils
import PlexFunctions
import PlexAPI

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class lockMethod:
    """
    Decorator for class methods to lock hem completely. Same lock is used for
    every single decorator and instance used!

    Here only used for Playlist()
    """
    lock = Lock()

    @classmethod
    def decorate(cls, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with cls.lock:
                result = func(*args, **kwargs)
            return result
        return wrapper


class Playlist():
    """
    Initiate with Playlist(typus='video' or 'music')
    """
    # Borg - multiple instances, shared state
    _shared_state = {}

    typus = None
    queueId = None
    playQueueVersion = None
    guid = None
    playlistId = None
    player = xbmc.Player()
    # "interal" PKC playlist
    items = []

    @lockMethod.decorate
    def __init__(self, typus=None):
        # Borg
        self.__dict__ = self._shared_state

        self.userid = window('currUserId')
        self.server = window('pms_server')
        # Construct the Kodi playlist instance
        if self.typus == typus:
            return
        if typus == 'video':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.typus = 'video'
            log.info('Initiated video playlist')
        elif typus == 'music':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            self.typus = 'music'
            log.info('Initiated music playlist')
        else:
            self.playlist = None
            self.typus = None
            log.info('Empty playlist initiated')
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()

    @lockMethod.decorate
    def getQueueIdFromPosition(self, playlistPosition):
        return self.items[playlistPosition]['playQueueItemID']

    @lockMethod.decorate
    def Typus(self, value=None):
        if value:
            self.typus = value
        else:
            return self.typus

    @lockMethod.decorate
    def PlayQueueVersion(self, value=None):
        if value:
            self.playQueueVersion = value
        else:
            return self.playQueueVersion

    @lockMethod.decorate
    def QueueId(self, value=None):
        if value:
            self.queueId = value
        else:
            return self.queueId

    @lockMethod.decorate
    def Guid(self, value=None):
        if value:
            self.guid = value
        else:
            return self.guid

    @lockMethod.decorate
    def clear(self):
        """
        Empties current Kodi playlist and associated variables
        """
        log.info('Clearing playlist')
        self.playlist.clear()
        self.items = []
        self.queueId = None
        self.playQueueVersion = None
        self.guid = None

    def _initiatePlaylist(self):
        log.info('Initiating playlist')
        playlist = None
        with embydb.GetEmbyDB() as emby_db:
            for item in self.items:
                itemid = item['plexId']
                embydb_item = emby_db.getItem_byId(itemid)
                try:
                    mediatype = embydb_item[4]
                except TypeError:
                    log.info('Couldnt find item %s in Kodi db' % itemid)
                    item = PlexFunctions.GetPlexMetadata(itemid)
                    if item in (None, 401):
                        log.info('Couldnt find item %s on PMS, trying next'
                                 % itemid)
                        continue
                    if PlexAPI.API(item[0]).getType() == 'track':
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                        log.info('Music playlist initiated')
                        self.typus = 'music'
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        log.info('Video playlist initiated')
                        self.typus = 'video'
                else:
                    if mediatype == 'song':
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                        log.info('Music playlist initiated')
                        self.typus = 'music'
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        log.info('Video playlist initiated')
                        self.typus = 'video'
                break
        self.playlist = playlist
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()

    def _processItems(self, startitem, startPlayer=False):
        startpos = None
        with embydb.GetEmbyDB() as emby_db:
            for pos, item in enumerate(self.items):
                kodiId = None
                plexId = item['plexId']
                embydb_item = emby_db.getItem_byId(plexId)
                try:
                    kodiId = embydb_item[0]
                    mediatype = embydb_item[4]
                except TypeError:
                    log.info('Couldnt find item %s in Kodi db' % plexId)
                    xml = PlexFunctions.GetPlexMetadata(plexId)
                    if xml in (None, 401):
                        log.error('Could not download plexId %s' % plexId)
                    else:
                        log.debug('Downloaded xml metadata, adding now')
                        self._addtoPlaylist_xbmc(xml[0])
                else:
                    # Add to playlist
                    log.debug("Adding %s PlexId %s, KodiId %s to playlist."
                              % (mediatype, plexId, kodiId))
                    self._addtoPlaylist(kodiId, mediatype)
                # Add the kodiId
                if kodiId is not None:
                    item['kodiId'] = str(kodiId)
                if (startpos is None and startitem[1] == item[startitem[0]]):
                    startpos = pos

        if startPlayer is True and len(self.playlist) > 0:
            if startpos is not None:
                self.player.play(self.playlist, startpos=startpos)
            else:
                log.info('Never received a starting item for playlist, '
                         'starting with the first entry')
                self.player.play(self.playlist)

    @lockMethod.decorate
    def playAll(self, items, startitem, offset):
        """
        items: list of dicts of the form
        {
            'playQueueItemID':      Plex playQueueItemID, e.g. '29175'
            'plexId':       Plex ratingKey, e.g. '125'
            'kodiId':       Kodi's db id of the same item
        }

        startitem:  tuple (typus, id), where typus is either
                    'playQueueItemID' or 'plexId' and id is the corresponding
                    id as a string
        offset:     First item's time offset to play in Kodi time (an int)
        """
        log.info("---*** PLAY ALL ***---")
        log.debug('Startitem: %s, offset: %s, items: %s'
                  % (startitem, offset, items))
        self.items = items
        if self.playlist is None:
            self._initiatePlaylist()
        if self.playlist is None:
            log.error('Could not create playlist, abort')
            return

        window('plex_customplaylist', value="true")
        if offset != 0:
            # Seek to the starting position
            window('plex_customplaylist.seektime', str(offset))
        self._processItems(startitem, startPlayer=True)
        # Log playlist
        self._verifyPlaylist()
        log.debug('Internal playlist: %s' % self.items)

    @lockMethod.decorate
    def modifyPlaylist(self, itemids):
        log.info("---*** MODIFY PLAYLIST ***---")
        log.debug("Items: %s" % itemids)

        self._initiatePlaylist(itemids)
        self._processItems(itemids, startPlayer=True)

        self._verifyPlaylist()

    @lockMethod.decorate
    def addtoPlaylist(self, dbid=None, mediatype=None, url=None):
        """
        mediatype: Kodi type: 'movie', 'episode', 'musicvideo', 'artist',
                              'album', 'song', 'genre'
        """
        self._addtoPlaylist(dbid=None, mediatype=None, url=None)

    def _addtoPlaylist(self, dbid=None, mediatype=None, url=None):
        pl = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Add",
            'params': {
                'playlistid': self.playlistId
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % tryEncode(mediatype): int(dbid)}
        else:
            pl['params']['item'] = {'file': url}
        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    def _addtoPlaylist_xbmc(self, item):
        API = PlexAPI.API(item)
        params = {
            'mode': "play",
            'dbid': 999999999,
            'id': API.getRatingKey(),
            'filename': API.getKey()
        }
        playurl = "plugin://plugin.video.plexkodiconnect.movies/?%s" \
            % urlencode(params)

        listitem = API.CreateListItemFromPlexItem()
        playbackutils.PlaybackUtils(item).setArtwork(listitem)

        self.playlist.add(playurl, listitem)

    @lockMethod.decorate
    def insertintoPlaylist(self,
                           position,
                           dbid=None,
                           mediatype=None,
                           url=None):
        pl = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Insert",
            'params': {
                'playlistid': self.playlistId,
                'position': position
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % tryEncode(mediatype): int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    @lockMethod.decorate
    def verifyPlaylist(self):
        self._verifyPlaylist()

    def _verifyPlaylist(self):
        pl = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.GetItems",
            'params': {
                'playlistid': self.playlistId,
                'properties': ['title', 'file']
            }
        }
        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    @lockMethod.decorate
    def removefromPlaylist(self, position):
        pl = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Remove",
            'params': {
                'playlistid': self.playlistId,
                'position': position
            }
        }
        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

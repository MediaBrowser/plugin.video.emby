# -*- coding: utf-8 -*-

###############################################################################

import logging
import json
from urllib import urlencode
from threading import Lock
from functools import wraps
from urllib import quote, urlencode

import xbmc

import embydb_functions as embydb
import kodidb_functions as kodidb
from utils import window, tryEncode, JSONRPC
import playbackutils
import PlexFunctions as PF
import PlexAPI
from downloadutils import DownloadUtils

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################

PLEX_PLAYQUEUE_ARGS = (
    'playQueueID',
    'playQueueVersion',
    'playQueueSelectedItemID',
    'playQueueSelectedItemOffset'
)


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

    ATTRIBUTES:
    id: integer
    position: integer, default -1
    type: string, default "unknown"
        "unknown",
        "video",
        "audio",
        "picture",
        "mixed"
    size: integer
    """
    # Borg - multiple instances, shared state
    _shared_state = {}

    player = xbmc.Player()

    playlists = None

    @lockMethod.decorate
    def __init__(self, typus=None):
        # Borg
        self.__dict__ = self._shared_state

        # If already initiated, return
        if self.playlists is not None:
            return

        self.doUtils = DownloadUtils().downloadUrl
        # Get all playlists from Kodi
        self.playlists = JSONRPC('Playlist.GetPlaylists').execute()
        try:
            self.playlists = self.playlists['result']
        except KeyError:
            log.error('Could not get Kodi playlists. JSON Result was: %s'
                      % self.playlists)
            self.playlists = None
            return
        # Example return: [{u'playlistid': 0, u'type': u'audio'},
        #                  {u'playlistid': 1, u'type': u'video'},
        #                  {u'playlistid': 2, u'type': u'picture'}]
        # Initiate the Kodi playlists
        for playlist in self.playlists:
            # Initialize each Kodi playlist
            if playlist['type'] == 'audio':
                playlist['kodi_pl'] = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            elif playlist['type'] == 'video':
                playlist['kodi_pl'] = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            else:
                # Currently, only video or audio playlists available
                playlist['kodi_pl'] = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            # Initialize Plex info on the playQueue
            for arg in PLEX_PLAYQUEUE_ARGS:
                playlist[arg] = None

            # Build a list of all items within each playlist
            playlist['items'] = []
            for item in self._get_kodi_items(playlist['playlistid']):
                playlist['items'].append({
                    'kodi_id': item.get('id'),
                    'type': item['type'],
                    'file': item['file'],
                    'playQueueItemID': None,
                    'plex_id': self._get_plexid(item)
                })
            log.debug('self.playlist: %s' % playlist)

    def _init_pl_item(self):
        return {
            'plex_id': None,
            'kodi_id': None,
            'file': None,
            'type': None,  # 'audio' or 'video'
            'playQueueItemID': None,
            'uri': None,
            # To be able to drag Kodi JSON data along:
            'playlistid': None,
            'position': None,
            'item': None,
        }

    def _get_plexid(self, item):
        """
        Supply with data['item'] as returned from Kodi JSON-RPC interface
        """
        with embydb.GetEmbyDB() as emby_db:
            emby_dbitem = emby_db.getItem_byKodiId(item.get('id'),
                                                   item.get('type'))
        try:
            plex_id = emby_dbitem[0]
        except TypeError:
            plex_id = None
        return plex_id

    def _get_kodi_items(self, playlistid):
        params = {
            'playlistid': playlistid,
            'properties': ["title", "file"]
        }
        answ = JSONRPC('Playlist.GetItems').execute(params)
        # returns e.g. [{u'title': u'3 Idiots', u'type': u'movie', u'id': 3,
        # u'file': u'smb://nas/PlexMovies/3 Idiots 2009 pt1.mkv', u'label':
        # u'3 Idiots'}]
        try:
            answ = answ['result']['items']
        except KeyError:
            answ = []
        return answ

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
                    item = PF.GetPlexMetadata(itemid)
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
                    xml = PF.GetPlexMetadata(plexId)
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
        self._addtoPlaylist(dbid, mediatype, url)

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
            'dbid': 'plextrailer',
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

    def _get_uri(self, plex_id=None, item=None):
        """
        Supply with either plex_id or data['item'] as received from Kodi JSON-
        RPC
        """
        uri = None
        if plex_id is None:
            plex_id = self._get_plexid(item)
            self._cur_item['plex_id'] = plex_id
        if plex_id is not None:
            xml = PF.GetPlexMetadata(plex_id)
            try:
                uri = ('library://%s/item/%s%s' %
                       (xml.attrib.get('librarySectionUUID'),
                        quote('library/metadata/', safe=''), plex_id))
            except:
                pass
        if uri is None:
            try:
                uri = 'library://whatever/item/%s' % quote(item['file'],
                                                           safe='')
            except:
                raise KeyError('Could not get file/url with item: %s' % item)
        self._cur_item['uri'] = uri
        return uri

    def _init_plex_playQueue(self, plex_id=None, data=None):
        """
        Supply either plex_id or the data supplied by Kodi JSON-RPC
        """
        if plex_id is None:
            plex_id = self._get_plexid(data['item'])
        self._cur_item['plex_id'] = plex_id

        if data is not None:
            playlistid = data['playlistid']
            plex_type = self.playlists[playlistid]['type']
        else:
            with embydb.GetEmbyDB() as emby_db:
                plex_type = emby_db.getItem_byId(plex_id)
            try:
                plex_type = PF.KODIAUDIOVIDEO_FROM_MEDIA_TYPE[plex_type[4]]
            except TypeError:
                raise KeyError('Unknown plex_type %s' % plex_type)
            for playlist in self.playlists:
                if playlist['type'] == plex_type:
                    playlistid = playlist['playlistid']
            self._cur_item['playlistid'] = playlistid
            self._cur_item['type'] = plex_type

        params = {
            'next': 0,
            'type': plex_type,
            'uri': self._get_uri(plex_id=plex_id, item=data['item'])
        }
        log.debug('params: %s' % urlencode(params))
        xml = self.doUtils(url="{server}/playQueues",
                           action_type="POST",
                           parameters=params)
        try:
            xml.attrib
        except (TypeError, AttributeError):
            raise KeyError('Could not post to PMS, received: %s' % xml)
        self._Plex_item_updated(xml)

    def _Plex_item_updated(self, xml):
        """
        Called if a new item has just been added/updated @ Plex playQueue

        Call with the PMS' xml reply
        """
        # Update the ITEM
        log.debug('xml.attrib: %s' % xml.attrib)
        args = {
            'playQueueItemID': 'playQueueLastAddedItemID',  # for playlist PUT
            'playQueueItemID': 'playQueueSelectedItemID'  # for playlist INIT
        }
        for old, new in args.items():
            if new in xml.attrib:
                self._cur_item[old] = xml.attrib[new]
        # Update the PLAYLIST
        for arg in PLEX_PLAYQUEUE_ARGS:
            if arg in xml.attrib:
                self.playlists[self._cur_item['playlistid']][arg] = xml.attrib[arg]

    def _init_Kodi_item(self, item):
        """
        Call with Kodi's JSON-RPC data['item']
        """
        self._cur_item['kodi_id'] = item.get('id')
        try:
            self._cur_item['type'] = PF.KODIAUDIOVIDEO_FROM_MEDIA_TYPE[
                item.get('type')]
        except KeyError:
            log.error('Could not get media_type for %s' % item)

    def _add_curr_item(self):
        self.playlists[self._cur_item['playlistid']]['items'].insert(
            self._cur_item['position'],
            self._cur_item)

    @lockMethod.decorate
    def kodi_onadd(self, data):
        """
        Called if Kodi playlist is modified. Data is Kodi JSON-RPC output, e.g.
            {
                u'item': {u'type': u'movie', u'id': 3},
                u'playlistid': 1,
                u'position': 0
            }
        """
        self._cur_item = self._init_pl_item()
        self._cur_item.update(data)
        self._init_Kodi_item(data['item'])

        pl = self.playlists[data['playlistid']]
        if pl['playQueueID'] is None:
            # Playlist needs to be initialized!
            try:
                self._init_plex_playQueue(data=data)
            except KeyError as e:
                log.error('Error encountered while init playQueue: %s' % e)
                return
        else:
            next_item = data['position']
            if next_item != 0:
                next_item = pl['items'][data['position']-1]['playQueueItemID']
            params = {
                'next': next_item,
                'type': pl['type'],
                'uri': self._get_uri(item=data['item'])
            }
            xml = self.doUtils(url="{server}/playQueues/%s"
                               % pl['playQueueID'],
                               action_type="PUT",
                               parameters=params)
            try:
                xml.attrib
            except AttributeError:
                log.error('Could not add item %s to playQueue' % data)
                return
            self._Plex_item_updated(xml)
        # Add the new item to our playlist
        self._add_curr_item()
        log.debug('self.playlists are now: %s' % self.playlists)

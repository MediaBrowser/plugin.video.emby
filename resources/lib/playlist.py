# -*- coding: utf-8 -*-

###############################################################################

import json
from urllib import urlencode

import xbmc

import embydb_functions as embydb
import utils
import playbackutils
import PlexFunctions
import PlexAPI

###############################################################################


@utils.logging
class Playlist():
    """
    Initiate with Playlist(typus='video' or 'music')
    """
    def __init__(self, typus=None):
        self.userid = utils.window('currUserId')
        self.server = utils.window('pms_server')
        # Construct the Kodi playlist instance
        if typus == 'video':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.typus = 'video'
            self.logMsg('Initiated video playlist', 1)
        elif typus == 'music':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            self.typus = 'music'
            self.logMsg('Initiated music playlist', 1)
        else:
            self.playlist = None
            self.typus = None
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()
        # "interal" PKC playlist
        self.items = []

    def clear(self):
        """
        Empties current Kodi playlist and internal self.items list
        """
        self.logMsg('Clearing playlist', 1)
        self.playlist.clear()
        self.items = []

    def _initiatePlaylist(self):
        self.logMsg('Initiating playlist', 1)
        playlist = None
        with embydb.GetEmbyDB() as emby_db:
            for item in self.items:
                itemid = item['plexId']
                embydb_item = emby_db.getItem_byId(itemid)
                try:
                    mediatype = embydb_item[4]
                except TypeError:
                    self.logMsg('Couldnt find item %s in Kodi db'
                                % itemid, 1)
                    item = PlexFunctions.GetPlexMetadata(itemid)
                    if item in (None, 401):
                        self.logMsg('Couldnt find item %s on PMS, trying next'
                                    % itemid, 1)
                        continue
                    if PlexAPI.API(item[0]).getType() == 'track':
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                        self.logMsg('Music playlist initiated', 1)
                        self.typus = 'music'
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        self.logMsg('Video playlist initiated', 1)
                        self.typus = 'video'
                else:
                    if mediatype == 'song':
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                        self.logMsg('Music playlist initiated', 1)
                        self.typus = 'music'
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        self.logMsg('Video playlist initiated', 1)
                        self.typus = 'video'
                break
        self.playlist = playlist
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()

    def _addToPlaylist(self, startitem, startPlayer=False):
        started = False
        with embydb.GetEmbyDB() as emby_db:
            for pos, item in enumerate(self.items):
                kodiId = None
                plexId = item['plexId']
                embydb_item = emby_db.getItem_byId(plexId)
                try:
                    kodiId = embydb_item[0]
                    mediatype = embydb_item[4]
                except TypeError:
                    self.logMsg('Couldnt find item %s in Kodi db' % plexId, 1)
                    xml = PlexFunctions.GetPlexMetadata(plexId)
                    if xml in (None, 401):
                        self.logMsg('Could not download plexId %s'
                                    % plexId, -1)
                    else:
                        self.logMsg('Downloaded xml metadata, adding now', 1)
                        self._addtoPlaylist_xbmc(xml[0])
                else:
                    # Add to playlist
                    self.logMsg("Adding %s PlexId %s, KodiId %s to playlist."
                                % (mediatype, plexId, kodiId), 1)
                    self.addtoPlaylist(kodiId, mediatype)
                # Add the kodiId
                if kodiId is not None:
                    item['kodiId'] = str(kodiId)
                if (started is False and
                        startPlayer is True and
                        startitem[1] == item[startitem[0]]):
                    started = True
                    xbmc.Player().play(self.playlist, startpos=pos)
        if (started is False and
                startPlayer is True and
                len(self.playlist) > 0):
            self.logMsg('Never received a starting item for playlist, '
                        'starting with the first entry', 1)
            xbmc.Player().play(self.playlist)

    def playAll(self, items, startitem, offset):
        """
        items: list of dicts of the form
        {
            'queueId':      Plex playQueueItemID, e.g. '29175'
            'plexId':       Plex ratingKey, e.g. '125'
            'kodiId':       Kodi's db id of the same item
        }

        startitem:  tuple (typus, id), where typus is either 'queueId' or
                    'plexId' and id is the corresponding id as a string
        offset:     First item's time offset to play in Kodi time (an int)
        """
        self.logMsg("---*** PLAY ALL ***---", 1)
        self.logMsg('Startitem: %s, offset: %s, items: %s'
                    % (startitem, offset, items), 1)
        self.items = items
        if self.playlist is None:
            self._initiatePlaylist()
        if self.playlist is None:
            self.logMsg('Could not create playlist, abort', -1)
            return

        utils.window('plex_customplaylist', value="true")
        if offset != 0:
            # Seek to the starting position
            utils.window('plex_customplaylist.seektime', str(offset))
        self._addToPlaylist(startitem, startPlayer=True)
        # Log playlist
        self.verifyPlaylist()
        self.logMsg('Internal playlist: %s' % self.items, 2)

    def modifyPlaylist(self, itemids):
        self.logMsg("---*** ADD TO PLAYLIST ***---", 1)
        self.logMsg("Items: %s" % itemids, 1)

        self._initiatePlaylist(itemids)
        self._addToPlaylist(itemids, startPlayer=True)

        self.verifyPlaylist()

    def addtoPlaylist(self, dbid=None, mediatype=None, url=None):
        """
        mediatype: Kodi type: 'movie', 'episode', 'musicvideo', 'artist',
                              'album', 'song', 'genre'
        """
        pl = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Add",
            'params': {
                'playlistid': self.playlistId
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % utils.tryEncode(mediatype):
                                    int(dbid)}
        else:
            pl['params']['item'] = {'file': url}
        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

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

    def insertintoPlaylist(self, position, dbid=None, mediatype=None, url=None):

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
            pl['params']['item'] = {'%sid' % utils.tryEncode(mediatype):
                                    int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

    def verifyPlaylist(self):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.GetItems",
            'params': {

                'playlistid': self.playlistId,
                'properties': ['title', 'file']
            }
        }
        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

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
        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

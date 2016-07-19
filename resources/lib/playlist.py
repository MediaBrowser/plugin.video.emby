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
        if typus == 'video':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.logMsg('Initiated video playlist', 1)
        elif typus == 'music':
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
            self.logMsg('Initiated music playlist', 1)
        else:
            self.playlist = None
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()

    def _initiatePlaylist(self, itemids):
        self.logMsg('Initiating playlist', 1)
        playlist = None
        with embydb.GetEmbyDB() as emby_db:
            for itemid in itemids:
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
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        self.logMsg('Video playlist initiated', 1)
                else:
                    if mediatype == 'song':
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                        self.logMsg('Music playlist initiated', 1)
                    else:
                        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                        self.logMsg('Video playlist initiated', 1)
                break
        self.playlist = playlist
        if self.playlist is not None:
            self.playlistId = self.playlist.getPlayListId()

    def _addToPlaylist(self, itemids, startPlayer=False):
        started = False
        with embydb.GetEmbyDB() as emby_db:
            for itemid in itemids:
                embydb_item = emby_db.getItem_byId(itemid)
                try:
                    dbid = embydb_item[0]
                    mediatype = embydb_item[4]
                except TypeError:
                    self.logMsg('Couldnt find item %s in Kodi db' % itemid, 1)
                    item = PlexFunctions.GetPlexMetadata(itemid)
                    if item in (None, 401):
                        self.logMsg('Could not download itemid %s'
                                    % itemid, -1)
                    else:
                        self.logMsg('Downloaded item metadata, adding now', 1)
                        self._addtoPlaylist_xbmc(item[0])
                else:
                    # Add to playlist
                    self.logMsg("Adding %s PlexId %s, KodiId %s to playlist."
                                % (mediatype, itemid, dbid), 1)
                    self.addtoPlaylist(dbid, mediatype)
                if started is False and startPlayer is True:
                    started = True
                    xbmc.Player().play(self.playlist)

    def playAll(self, itemids, startat):
        self.logMsg("---*** PLAY ALL ***---", 1)
        self.logMsg("Items: %s and start at: %s" % (itemids, startat), 1)

        if self.playlist is None:
            self._initiatePlaylist(itemids)
        if self.playlist is None:
            self.logMsg('Could not create playlist, abort', -1)
            return

        utils.window('plex_customplaylist', value="true")
        if startat != 0:
            # Seek to the starting position
            utils.window('plex_customplaylist.seektime', str(startat))
        self._addToPlaylist(itemids, startPlayer=True)
        self.verifyPlaylist()

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
        self.logMsg('JSONRPC question: %s' % json.dumps(pl), 2)
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

# -*- coding: utf-8 -*-

###############################################################################

import json
from urllib import urlencode

import xbmc

import embydb_functions as embydb
import read_embyserver as embyserver
import utils
import playbackutils
import PlexFunctions
import PlexAPI

###############################################################################


@utils.logging
class Playlist():

    def __init__(self):
        self.userid = utils.window('currUserId')
        self.server = utils.window('pms_server')

        self.emby = embyserver.Read_EmbyServer()

    def playAll(self, itemids, startat):
        window = utils.window

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)

        player = xbmc.Player()
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()

        self.logMsg("---*** PLAY ALL ***---", 1)
        self.logMsg("Items: %s and start at: %s" % (itemids, startat), 1)

        started = False
        window('emby_customplaylist', value="true")

        if startat != 0:
            # Seek to the starting position
            window('emby_customplaylist.seektime', str(startat))

        with embydb.GetEmbyDB() as emby_db:
            for itemid in itemids:
                embydb_item = emby_db.getItem_byId(itemid)
                try:
                    dbid = embydb_item[0]
                    mediatype = embydb_item[4]
                except TypeError:
                    # Item is not found in our database, add item manually
                    self.logMsg("Item was not found in the database, manually "
                                "adding item.", 1)
                    item = PlexFunctions.GetPlexMetadata(itemid)
                    if item is None or item == 401:
                        self.logMsg('Could not download itemid %s'
                                    % itemid, -1)
                    else:
                        self.addtoPlaylist_xbmc(playlist, item)
                else:
                    # Add to playlist
                    self.addtoPlaylist(dbid, mediatype)

                self.logMsg("Adding %s to playlist." % itemid, 1)

                if not started:
                    started = True
                    player.play(playlist)

        self.verifyPlaylist()

    def modifyPlaylist(self, itemids):

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)

        self.logMsg("---*** ADD TO PLAYLIST ***---", 1)
        self.logMsg("Items: %s" % itemids, 1)

        # player = xbmc.Player()
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        for itemid in itemids:
            embydb_item = emby_db.getItem_byId(itemid)
            try:
                dbid = embydb_item[0]
                mediatype = embydb_item[4]
            except TypeError:
                self.logMsg('item %s not found in Kodi DB, add manually'
                            % itemid, 1)
                item = self.emby.getItem(itemid)
                self.addtoPlaylist_xbmc(playlist, item)
            else:
                # Add to playlist
                self.addtoPlaylist(dbid, mediatype)

            self.logMsg("Adding %s to playlist." % itemid, 1)

        self.verifyPlaylist()
        embycursor.close()
        return playlist

    def addtoPlaylist(self, dbid=None, mediatype=None, url=None):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Add",
            'params': {

                'playlistid': 1
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % mediatype: int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

    def addtoPlaylist_xbmc(self, playlist, item):
        API = PlexAPI.API(item[0])
        params = {
            'mode': "play",
            'dbid': 999999999,
            'id': API.getRatingKey(),
            'filename': API.getKey()
        }
        playurl = "plugin://plugin.video.plexkodiconnect.movies/?%s" \
            % urlencode(params)

        listitem = API.CreateListItemFromPlexItem()
        playbackutils.PlaybackUtils(item[0]).setArtwork(listitem)

        playlist.add(playurl, listitem)

    def insertintoPlaylist(self, position, dbid=None, mediatype=None, url=None):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Insert",
            'params': {

                'playlistid': 1,
                'position': position
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % mediatype: int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

    def verifyPlaylist(self):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.GetItems",
            'params': {

                'playlistid': 1,
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

                'playlistid': 1,
                'position': position
            }
        }
        self.logMsg(xbmc.executeJSONRPC(json.dumps(pl)), 2)

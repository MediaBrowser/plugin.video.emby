import base64
import json
import string

import xbmc

from utils import logging
import embydb_functions as embydb


def xbmc_photo():
    return "photo"


def xbmc_video():
    return "video"


def xbmc_audio():
    return "audio"


def plex_photo():
    return "photo"


def plex_video():
    return "video"


def plex_audio():
    return "music"


def xbmc_type(plex_type):
    if plex_type == plex_photo():
        return xbmc_photo()
    elif plex_type == plex_video():
        return xbmc_video()
    elif plex_type == plex_audio():
        return xbmc_audio()


def plex_type(xbmc_type):
    if xbmc_type == xbmc_photo():
        return plex_photo()
    elif xbmc_type == xbmc_video():
        return plex_video()
    elif xbmc_type == xbmc_audio():
        return plex_audio()


def getXMLHeader():
    return '<?xml version="1.0" encoding="utf-8" ?>\r\n'


def getOKMsg():
    return getXMLHeader() + '<Response code="200" status="OK" />'


def timeToMillis(time):
    return (time['hours']*3600 +
            time['minutes']*60 +
            time['seconds'])*1000 + time['milliseconds']


def millisToTime(t):
    millis = int(t)
    seconds = millis / 1000
    minutes = seconds / 60
    hours = minutes / 60
    seconds = seconds % 60
    minutes = minutes % 60
    millis = millis % 1000
    return {'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
            'milliseconds': millis}


def textFromXml(element):
    return element.firstChild.data


@logging
class jsonClass():

    def __init__(self, requestMgr, settings):
        self.settings = settings
        self.requestMgr = requestMgr

    def jsonrpc(self, action, arguments={}):
        """ put some JSON together for the JSON-RPC APIv6 """
        if action.lower() == "sendkey":
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "Input.SendText",
                "params": {
                    "text": arguments[0],
                    "done": False
                }
            })
        elif action.lower() == "ping":
            request = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "JSONRPC.Ping"
            })
        elif action.lower() == "playmedia":
            xbmc.Player().play("plugin://plugin.video.plexkodiconnect/"
                               "?mode=companion&arguments=%s"
                               % arguments)
            return True
        elif arguments:
            request = json.dumps({
                "id": 1,
                "jsonrpc": "2.0",
                "method": action,
                "params": arguments})
        else:
            request = json.dumps({
                "id": 1,
                "jsonrpc": "2.0",
                "method": action
            })

        result = self.parseJSONRPC(xbmc.executeJSONRPC(request))

        if not result and self.settings['webserver_enabled']:
            # xbmc.executeJSONRPC appears to fail on the login screen, but
            # going through the network stack works, so let's try the request
            # again
            result = self.parseJSONRPC(self.requestMgr.post(
                "127.0.0.1",
                self.settings['port'],
                "/jsonrpc",
                request,
                {'Content-Type': 'application/json',
                 'Authorization': 'Basic %s' % string.strip(
                     base64.encodestring('%s:%s'
                                         % (self.settings['user'],
                                            self.settings['passwd'])))
                 }))
        return result

    def skipTo(self, plexId, typus):
        self.logMsg('players: %s' % self.getPlayers())
        # playlistId = self.getPlaylistId(tryDecode(xbmc_type(typus)))
        # playerId = self.
        with embydb.GetEmbyDB() as emby_db:
            embydb_item = emby_db.getItem_byId(plexId)
            try:
                dbid = embydb_item[0]
                mediatype = embydb_item[4]
            except TypeError:
                self.logMsg('Couldnt find item %s in Kodi db' % plexId, 1)
                return
        self.logMsg('plexid: %s, kodi id: %s, type: %s'
                    % (plexId, dbid, mediatype))

    def getPlexHeaders(self):
        h = {
            "Content-type": "text/xml",
            "Access-Control-Allow-Origin": "*",
            "X-Plex-Version": self.settings['version'],
            "X-Plex-Client-Identifier": self.settings['uuid'],
            "X-Plex-Provides": "player",
            "X-Plex-Product": "PlexKodiConnect",
            "X-Plex-Device-Name": self.settings['client_name'],
            "X-Plex-Platform": "Kodi",
            "X-Plex-Model": self.settings['platform'],
            "X-Plex-Device": "PC",
        }
        if self.settings['myplex_user']:
            h["X-Plex-Username"] = self.settings['myplex_user']
        return h

    def parseJSONRPC(self, jsonraw):
        if not jsonraw:
            self.logMsg("Empty response from XBMC", 1)
            return {}
        else:
            parsed = json.loads(jsonraw)
        if parsed.get('error', False):
            self.logMsg("XBMC returned an error: %s" % parsed.get('error'), -1)
        return parsed.get('result', {})

    def getPlayers(self):
        info = self.jsonrpc("Player.GetActivePlayers") or []
        ret = {}
        for player in info:
            player['playerid'] = int(player['playerid'])
            ret[player['type']] = player
        return ret

    def getPlaylistId(self, typus):
        """
        typus: one of the Kodi types, e.g. audio or video

        Returns None if nothing was found
        """
        for playlist in self.getPlaylists():
            if playlist.get('type') == typus:
                return playlist.get('playlistid')

    def getPlaylists(self):
        """
        Returns a list, e.g.
            [
                {u'playlistid': 0, u'type': u'audio'},
                {u'playlistid': 1, u'type': u'video'},
                {u'playlistid': 2, u'type': u'picture'}
            ]
        """
        return self.jsonrpc('Playlist.GetPlaylists')

    def getPlayerIds(self):
        ret = []
        for player in self.getPlayers().values():
            ret.append(player['playerid'])
        return ret

    def getVideoPlayerId(self, players=False):
        if players is None:
            players = self.getPlayers()
        return players.get(xbmc_video(), {}).get('playerid', None)

    def getAudioPlayerId(self, players=False):
        if players is None:
            players = self.getPlayers()
        return players.get(xbmc_audio(), {}).get('playerid', None)

    def getPhotoPlayerId(self, players=False):
        if players is None:
            players = self.getPlayers()
        return players.get(xbmc_photo(), {}).get('playerid', None)

    def getVolume(self):
        answ = self.jsonrpc('Application.GetProperties',
                            {
                                "properties": ["volume", 'muted']
                            })
        vol = str(answ.get('volume', 100))
        mute = ("0", "1")[answ.get('muted', False)]
        return (vol, mute)

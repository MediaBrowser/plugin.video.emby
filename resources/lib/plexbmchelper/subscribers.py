import re
import threading

from xbmc import Player

import downloadutils
from utils import window, logging
import PlexFunctions as pf
from functions import *


@logging
class SubscriptionManager:
    def __init__(self, jsonClass, RequestMgr):
        self.serverlist = []
        self.subscribers = {}
        self.info = {}
        self.lastkey = ""
        self.containerKey = ""
        self.lastratingkey = ""
        self.volume = 0
        self.mute = '0'
        self.server = ""
        self.protocol = "http"
        self.port = ""
        self.playerprops = {}
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = Player()

        self.js = jsonClass
        self.RequestMgr = RequestMgr

    def getServerByHost(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    def getVolume(self):
        self.volume, self.mute = self.js.getVolume()

    def msg(self, players):
        msg = getXMLHeader()
        msg += '<MediaContainer commandID="INSERTCOMMANDID"'
        if players:
            self.getVolume()
            maintype = plex_audio()
            for p in players.values():
                if p.get('type') == xbmc_video():
                    maintype = plex_video()
                elif p.get('type') == xbmc_photo():
                    maintype = plex_photo()
            self.mainlocation = "fullScreen" + maintype[0:1].upper() + maintype[1:].lower()
        else:
            self.mainlocation = "navigation"
        msg += ' location="%s">' % self.mainlocation
        msg += self.getTimelineXML(self.js.getAudioPlayerId(players), plex_audio())
        msg += self.getTimelineXML(self.js.getPhotoPlayerId(players), plex_photo())
        msg += self.getTimelineXML(self.js.getVideoPlayerId(players), plex_video())
        msg += "\r\n</MediaContainer>"
        return msg
        
    def getTimelineXML(self, playerid, ptype):
        if playerid is not None:
            info = self.getPlayerProperties(playerid)
            # save this info off so the server update can use it too
            self.playerprops[playerid] = info;
            state = info['state']
            time = info['time']
        else:
            state = "stopped"
            time = 0
        ret = "\r\n"+'  <Timeline state="%s" time="%s" type="%s"' % (state, time, ptype)
        if playerid is None:
            ret += ' seekRange="0-0"'
            ret += ' />'
            return ret

        # pbmc_server = str(WINDOW.getProperty('plexbmc.nowplaying.server'))
        # userId = str(WINDOW.getProperty('currUserId'))
        pbmc_server = window('pms_server')
        if pbmc_server:
            (self.protocol, self.server, self.port) = \
                pbmc_server.split(':')
            self.server = self.server.replace('/', '')
        keyid = None
        count = 0
        while not keyid:
            if count > 300:
                break
            keyid = window('Plex_currently_playing_itemid')
            xbmc.sleep(100)
            count += 1
        if keyid:
            self.lastkey = "/library/metadata/%s"%keyid
            self.lastratingkey = keyid
            ret += ' location="%s"' % (self.mainlocation)
            ret += ' key="%s"' % (self.lastkey)
            ret += ' ratingKey="%s"' % (self.lastratingkey)
        serv = self.getServerByHost(self.server)
        if info.get('playQueueID'):
            self.containerKey = "/playQueues/%s" % info.get('playQueueID')
            ret += ' playQueueID="%s"' % info.get('playQueueID')
            ret += ' playQueueVersion="%s"' % info.get('playQueueVersion')
            ret += ' playQueueItemID="%s"' % (info.get('playQueueItemID'))
            ret += ' containerKey="%s"' % self.containerKey
        elif keyid:
            self.containerKey = self.lastkey
            ret += ' containerKey="%s"' % (self.containerKey)

        ret += ' duration="%s"' % info['duration']
        ret += ' seekRange="0-%s"' % info['duration']
        ret += ' controllable="%s"' % self.controllable()
        ret += ' machineIdentifier="%s"' % serv.get('uuid', "")
        ret += ' protocol="%s"' % serv.get('protocol', "http")
        ret += ' address="%s"' % serv.get('server', self.server)
        ret += ' port="%s"' % serv.get('port', self.port)
        ret += ' guid="%s"' % info['guid']
        ret += ' volume="%s"' % info['volume']
        ret += ' shuffle="%s"' % info['shuffle']
        ret += ' mute="%s"' % self.mute
        ret += ' repeat="%s"' % info['repeat']
        # Might need an update in the future
        ret += ' subtitleStreamID="-1"'
        ret += ' audioStreamID="-1"'

        ret += ' />'
        return ret

    def updateCommandID(self, uuid, commandID):
        if commandID and self.subscribers.get(uuid, False):
            self.subscribers[uuid].commandID = int(commandID)            
        
    def notify(self, event = False):
        self.cleanup()
        players = self.js.getPlayers()
        # fetch the message, subscribers or not, since the server
        # will need the info anyway
        msg = self.msg(players)
        if self.subscribers:
            with threading.RLock():
                for sub in self.subscribers.values():
                    sub.send_update(msg, len(players)==0)
        self.notifyServer(players)
        return True
    
    def notifyServer(self, players):
        if not players:
            return True
        params = {'state': 'stopped'}
        for p in players.values():
            info = self.playerprops[p.get('playerid')]
            params = {}
            params['containerKey'] = (self.containerKey or "/library/metadata/900000")
            if info.get('playQueueID'):
                params['containerKey'] = '/playQueues/' + info['playQueueID']
                params['playQueueVersion'] = info['playQueueVersion']
                params['playQueueItemID'] = info['playQueueItemID']
            params['key'] = (self.lastkey or "/library/metadata/900000")
            params['ratingKey'] = (self.lastratingkey or "900000")
            params['state'] = info['state']
            params['time'] = info['time']
            params['duration'] = info['duration']
        serv = self.getServerByHost(self.server)
        url = serv.get('protocol', 'http') + '://' \
            + serv.get('server', 'localhost') + ':' \
            + serv.get('port', '32400') + "/:/timeline"
        self.doUtils(url, type="GET", parameters=params)
        # requests.getwithparams(serv.get('server', 'localhost'), serv.get('port', 32400), "/:/timeline", params, getPlexHeaders(), serv.get('protocol', 'http'))
        self.logMsg("params: %s" % params, 2)
        self.logMsg("players: %s" % players, 2)
        self.logMsg("sent server notification with state = %s"
                    % params['state'], 2)

    def controllable(self):
        return "volume,shuffle,repeat,audioStream,videoStream,subtitleStream,skipPrevious,skipNext,seekTo,stepBack,stepForward,stop,playPause"

    def addSubscriber(self, protocol, host, port, uuid, commandID):
        sub = Subscriber(protocol,
                         host,
                         port,
                         uuid,
                         commandID,
                         self,
                         self.RequestMgr)
        with threading.RLock():
            self.subscribers[sub.uuid] = sub
        return sub

    def removeSubscriber(self, uuid):
        with threading.RLock():
            for sub in self.subscribers.values():
                if sub.uuid == uuid or sub.host == uuid:
                    sub.cleanup()
                    del self.subscribers[sub.uuid]

    def cleanup(self):
        with threading.RLock():
            for sub in self.subscribers.values():
                if sub.age > 30:
                    sub.cleanup()
                    del self.subscribers[sub.uuid]
            
    def getPlayerProperties(self, playerid):
        info = {}
        try:
            # get info from the player
            props = self.js.jsonrpc("Player.GetProperties", {"playerid": playerid, "properties": ["time", "totaltime", "speed", "shuffled", "repeat"]})
            self.logMsg(self.js.jsonrpc("Player.GetItem", {"playerid": playerid, "properties": ["file", "showlink", "episode", "season"]}), 2)
            info['time'] = timeToMillis(props['time'])
            info['duration'] = timeToMillis(props['totaltime'])
            info['state'] = ("paused", "playing")[int(props['speed'])]
            info['shuffle'] = ("0","1")[props.get('shuffled', False)]
            info['repeat'] = pf.getPlexRepeat(props.get('repeat'))
            # New PMS playQueue attributes
            cf = self.xbmcplayer.getPlayingFile()
            info['playQueueID'] = window('playQueueID')
            info['playQueueVersion'] = window('playQueueVersion')
            info['playQueueItemID'] = window('plex_%s.playQueueItemID' % cf)
            info['guid'] = window('plex_%s.guid' % cf)

        except:
            info['time'] = 0
            info['duration'] = 0
            info['state'] = "stopped"
            info['shuffle'] = False
        # get the volume from the application
        info['volume'] = self.volume
        info['mute'] = self.mute

        return info


@logging
class Subscriber:
    def __init__(self, protocol, host, port, uuid, commandID,
                 subMgr, RequestMgr):
        self.protocol = protocol or "http"
        self.host = host
        self.port = port or 32400
        self.uuid = uuid or host
        self.commandID = int(commandID) or 0
        self.navlocationsent = False
        self.age = 0
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.subMgr = subMgr
        self.RequestMgr = RequestMgr

    def __eq__(self, other):
        return self.uuid == other.uuid

    def tostr(self):
        return "uuid=%s,commandID=%i" % (self.uuid, self.commandID)

    def cleanup(self):
        self.RequestMgr.closeConnection(self.protocol, self.host, self.port)

    def send_update(self, msg, is_nav):
        self.age += 1
        if not is_nav:
            self.navlocationsent = False
        elif self.navlocationsent:
            return True
        else:
            self.navlocationsent = True
        msg = re.sub(r"INSERTCOMMANDID", str(self.commandID), msg)
        self.logMsg("sending xml to subscriber %s: %s"
                    % (self.tostr(), msg), 2)
        url = self.protocol + '://' + self.host + ':' + self.port \
            + "/:/timeline"
        t = threading.Thread(target=self.threadedSend, args=(url, msg))
        t.start()

    def threadedSend(self, url, msg):
        """
        Threaded POST request, because they stall due to PMS response missing
        the Content-Length header :-(
        """
        response = self.doUtils(url,
                                postBody=msg,
                                type="POST")
        if response in [False, None, 401]:
            self.subMgr.removeSubscriber(self.uuid)

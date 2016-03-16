import re
import threading
from xml.dom.minidom import parseString
from functions import *
from settings import settings
from httppersist import requests

from xbmc import Player
import xbmcgui
import downloadutils
from utils import window
import PlexFunctions as pf

class SubscriptionManager:
    def __init__(self):
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
        self.download = downloadutils.DownloadUtils()
        self.xbmcplayer = Player()

    def getVolume(self):
        self.volume, self.mute = getVolume()

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
        msg += self.getTimelineXML(getAudioPlayerId(players), plex_audio())
        msg += self.getTimelineXML(getPhotoPlayerId(players), plex_photo())
        msg += self.getTimelineXML(getVideoPlayerId(players), plex_video())
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

        WINDOW = xbmcgui.Window(10000)
        
        # pbmc_server = str(WINDOW.getProperty('plexbmc.nowplaying.server'))
        # userId = str(WINDOW.getProperty('currUserId'))
        # pbmc_server = str(WINDOW.getProperty('pms_server'))
        pbmc_server = None
        keyid = None
        count = 0
        while not keyid:
            if count > 300:
                break
            keyid = WINDOW.getProperty('Plex_currently_playing_itemid')
            xbmc.sleep(100)
            count += 1
        if keyid:
            self.lastkey = "/library/metadata/%s"%keyid
            self.lastratingkey = keyid
            ret += ' location="%s"' % (self.mainlocation)
            ret += ' key="%s"' % (self.lastkey)
            ret += ' ratingKey="%s"' % (self.lastratingkey)
            if pbmc_server:
                (self.server, self.port) = pbmc_server.split(':')
        serv = getServerByHost(self.server)
        if info.get('playQueueID'):
            ret += ' playQueueID="%s"' % info.get('playQueueID')
            ret += ' playQueueVersion="%s"' % info.get('playQueueVersion')
            ret += ' playQueueItemID="%s"' % (info.get('playQueueItemID'))
            ret += ' containerKey="/playQueues/%s"' \
                   % (info.get('playQueueID'))
        elif keyid:
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
        players = getPlayers()
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
        serv = getServerByHost(self.server)
        url = serv.get('protocol', 'http') + '://' \
            + serv.get('server', 'localhost') + ':' \
            + serv.get('port', '32400') + "/:/timeline"
        self.download.downloadUrl(url, type="GET", parameters=params)
        # requests.getwithparams(serv.get('server', 'localhost'), serv.get('port', 32400), "/:/timeline", params, getPlexHeaders(), serv.get('protocol', 'http'))
        printDebug("params: %s" % params)
        printDebug("players: %s" % players)
        printDebug("sent server notification with state = %s" % params['state'])

    def controllable(self):
        return "volume,shuffle,repeat,audioStream,videoStream,subtitleStream,skipPrevious,skipNext,seekTo,stepBack,stepForward,stop,playPause"
        
    def addSubscriber(self, protocol, host, port, uuid, commandID):
        sub = Subscriber(protocol, host, port, uuid, commandID)
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
            props = jsonrpc("Player.GetProperties", {"playerid": playerid, "properties": ["time", "totaltime", "speed", "shuffled", "repeat"]})
            printDebug(jsonrpc("Player.GetItem", {"playerid": playerid, "properties": ["file", "showlink", "episode", "season"]}))
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

class Subscriber:
    def __init__(self, protocol, host, port, uuid, commandID):
        self.protocol = protocol or "http"
        self.host = host
        self.port = port or 32400
        self.uuid = uuid or host
        self.commandID = int(commandID) or 0
        self.navlocationsent = False
        self.age = 0
        self.download = downloadutils.DownloadUtils()
    def __eq__(self, other):
        return self.uuid == other.uuid
    def tostr(self):
        return "uuid=%s,commandID=%i" % (self.uuid, self.commandID)
    def cleanup(self):
        requests.closeConnection(self.protocol, self.host, self.port)
    def send_update(self, msg, is_nav):
        self.age += 1
        if not is_nav:
            self.navlocationsent = False
        elif self.navlocationsent:
            return True
        else:
            self.navlocationsent = True
        msg = re.sub(r"INSERTCOMMANDID", str(self.commandID), msg)
        printDebug("sending xml to subscriber %s: %s" % (self.tostr(), msg))
        url = self.protocol + '://' + self.host + ':' + self.port \
            + "/:/timeline"
        t = threading.Thread(target=self.threadedSend, args=(url, msg))
        t.start()

    def threadedSend(self, url, msg):
        """
        Threaded POST request, because they stall due to PMS response missing
        the Content-Length header :-(
        """
        response = self.download.downloadUrl(
            url,
            postBody=msg,
            type="POSTXML")
        if response in [False, None, 401]:
            subMgr.removeSubscriber(self.uuid)

subMgr = SubscriptionManager()

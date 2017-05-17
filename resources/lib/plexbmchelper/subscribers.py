import logging
import re
import threading

import downloadutils
from utils import window
import PlexFunctions as pf
from functions import *

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class SubscriptionManager:
    def __init__(self, jsonClass, RequestMgr, player, mgr):
        self.serverlist = []
        self.subscribers = {}
        self.info = {}
        self.lastkey = ""
        self.containerKey = ""
        self.ratingkey = ""
        self.lastplayers = {}
        self.lastinfo = {
            'video': {},
            'audio': {},
            'picture': {}
        }
        self.volume = 0
        self.mute = '0'
        self.server = ""
        self.protocol = "http"
        self.port = ""
        self.playerprops = {}
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = player
        self.playqueue = mgr.playqueue

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
        msg += '<MediaContainer size="3" commandID="INSERTCOMMANDID"'
        msg += ' machineIdentifier="%s">' % window('plex_client_Id')
        msg += self.getTimelineXML(self.js.getAudioPlayerId(players), plex_audio())
        msg += self.getTimelineXML(self.js.getPhotoPlayerId(players), plex_photo())
        msg += self.getTimelineXML(self.js.getVideoPlayerId(players), plex_video())
        msg += "\n</MediaContainer>"
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
        ret = "\n"+'  <Timeline state="%s" time="%s" type="%s"' % (state, time, ptype)
        if playerid is None:
            ret += ' />'
            return ret

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
            keyid = window('plex_currently_playing_itemid')
            xbmc.sleep(100)
            count += 1
        if keyid:
            self.lastkey = "/library/metadata/%s" % keyid
            self.ratingkey = keyid
            ret += ' key="%s"' % self.lastkey
            ret += ' ratingKey="%s"' % self.ratingkey
        serv = self.getServerByHost(self.server)
        if info.get('playQueueID'):
            self.containerKey = "/playQueues/%s" % info.get('playQueueID')
            ret += ' playQueueID="%s"' % info.get('playQueueID')
            ret += ' playQueueVersion="%s"' % info.get('playQueueVersion')
            ret += ' playQueueItemID="%s"' % info.get('playQueueItemID')
            ret += ' containerKey="%s"' % self.containerKey
            ret += ' guid="%s"' % info['guid']
        elif keyid:
            self.containerKey = self.lastkey
            ret += ' containerKey="%s"' % self.containerKey

        ret += ' duration="%s"' % info['duration']
        ret += ' controllable="%s"' % self.controllable()
        ret += ' machineIdentifier="%s"' % serv.get('uuid', "")
        ret += ' protocol="%s"' % serv.get('protocol', "http")
        ret += ' address="%s"' % serv.get('server', self.server)
        ret += ' port="%s"' % serv.get('port', self.port)
        ret += ' volume="%s"' % info['volume']
        ret += ' shuffle="%s"' % info['shuffle']
        ret += ' mute="%s"' % self.mute
        ret += ' repeat="%s"' % info['repeat']
        ret += ' itemType="%s"' % info['itemType']
        # Might need an update in the future
        if ptype == 'video':
            ret += ' subtitleStreamID="-1"'
            ret += ' audioStreamID="-1"'

        ret += '/>'
        return ret

    def updateCommandID(self, uuid, commandID):
        if commandID and self.subscribers.get(uuid, False):
            self.subscribers[uuid].commandID = int(commandID)

    def notify(self, event=False):
        self.cleanup()
        # Don't tell anyone if we don't know a Plex ID and are still playing
        # (e.g. no stop called). Used for e.g. PVR/TV without PKC usage
        if (not window('plex_currently_playing_itemid')
                and not self.lastplayers):
            return True
        players = self.js.getPlayers()
        # fetch the message, subscribers or not, since the server
        # will need the info anyway
        msg = self.msg(players)
        if self.subscribers:
            with threading.RLock():
                for sub in self.subscribers.values():
                    sub.send_update(msg, len(players) == 0)
        self.notifyServer(players)
        self.lastplayers = players
        return True

    def notifyServer(self, players):
        for typus, p in players.iteritems():
            info = self.playerprops[p.get('playerid')]
            self._sendNotification(info)
            self.lastinfo[typus] = info
            # Cross the one of the list
            try:
                del self.lastplayers[typus]
            except KeyError:
                pass
        # Process the players we have left (to signal a stop)
        for typus, p in self.lastplayers.iteritems():
            self.lastinfo[typus]['state'] = 'stopped'
            self._sendNotification(self.lastinfo[typus])

    def _sendNotification(self, info):
        params = {
            'containerKey': self.containerKey or "/library/metadata/900000",
            'key': self.lastkey or "/library/metadata/900000",
            'ratingKey': self.ratingkey or "900000",
            'state': info['state'],
            'time': info['time'],
            'duration': info['duration']
        }
        if info.get('playQueueID'):
            params['containerKey'] = '/playQueues/%s' % info['playQueueID']
            params['playQueueVersion'] = info['playQueueVersion']
            params['playQueueItemID'] = info['playQueueItemID']
        serv = self.getServerByHost(self.server)
        url = '%s://%s:%s/:/timeline' % (serv.get('protocol', 'http'),
                                         serv.get('server', 'localhost'),
                                         serv.get('port', '32400'))
        self.doUtils(url, parameters=params)
        log.debug("Sent server notification with parameters: %s to %s"
                  % (params, url))

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
        try:
            # Get the playqueue
            playqueue = self.playqueue.playqueues[playerid]
            # get info from the player
            props = self.js.jsonrpc(
                "Player.GetProperties",
                {"playerid": playerid,
                 "properties": ["type",
                                "time",
                                "totaltime",
                                "speed",
                                "shuffled",
                                "repeat"]})

            info = {
                'time': timeToMillis(props['time']),
                'duration': timeToMillis(props['totaltime']),
                'state': ("paused", "playing")[int(props['speed'])],
                'shuffle': ("0", "1")[props.get('shuffled', False)],
                'repeat': pf.getPlexRepeat(props.get('repeat')),
            }
            # Get the playlist position
            pos = self.js.jsonrpc(
                "Player.GetProperties",
                {"playerid": playerid,
                 "properties": ["position"]})['position']
            try:
                info['playQueueItemID'] = playqueue.items[pos].ID or 'null'
                info['guid'] = playqueue.items[pos].guid or 'null'
                info['playQueueID'] = playqueue.ID or 'null'
                info['playQueueVersion'] = playqueue.version or 'null'
                info['itemType'] = playqueue.items[pos].plex_type or 'null'
            except:
                info['itemType'] = props.get('type') or 'null'
        except:
            import traceback
            log.error("Traceback:\n%s" % traceback.format_exc())
            info = {
                'time': 0,
                'duration': 0,
                'state': 'stopped',
                'shuffle': False,
                'repeat': 0
            }

        # get the volume from the application
        info['volume'] = self.volume
        info['mute'] = self.mute

        return info


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
        log.debug("sending xml to subscriber %s:\n%s" % (self.tostr(), msg))
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
                                action_type="POST")
        if response in [False, None, 401]:
            self.subMgr.removeSubscriber(self.uuid)

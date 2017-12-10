import logging
import re
import threading

from xbmc import sleep

import downloadutils
from clientinfo import getXArgsDeviceInfo
from utils import window, kodi_time_to_millis
import PlexFunctions as pf
import state
import variables as v
import json_rpc as js

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################

# What is Companion controllable?
CONTROLLABLE = {
    v.PLEX_TYPE_PHOTO: 'skipPrevious,skipNext,stop',
    v.PLEX_TYPE_AUDIO: 'playPause,stop,volume,shuffle,repeat,seekTo,' \
        'skipPrevious,skipNext,stepBack,stepForward',
    v.PLEX_TYPE_VIDEO: 'playPause,stop,volume,audioStream,subtitleStream,' \
        'seekTo,skipPrevious,skipNext,stepBack,stepForward'
}

class SubscriptionManager:
    def __init__(self, RequestMgr, player, mgr):
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
        self.server = ""
        self.protocol = "http"
        self.port = ""
        self.playerprops = {}
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = player
        self.playqueue = mgr.playqueue

        self.RequestMgr = RequestMgr

    def getServerByHost(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    def msg(self, players):
        log.debug('players: %s', players)
        msg = v.XML_HEADER
        msg += '<MediaContainer size="3" commandID="INSERTCOMMANDID"'
        msg += ' machineIdentifier="%s">' % v.PKC_MACHINE_IDENTIFIER
        msg += self.getTimelineXML(players.get(v.KODI_TYPE_AUDIO),
                                   v.PLEX_TYPE_AUDIO)
        msg += self.getTimelineXML(players.get(v.KODI_TYPE_PHOTO),
                                   v.PLEX_TYPE_PHOTO)
        msg += self.getTimelineXML(players.get(v.KODI_TYPE_VIDEO),
                                   v.PLEX_TYPE_VIDEO)
        msg += "\n</MediaContainer>"
        log.debug('msg is: %s', msg)
        return msg

    def getTimelineXML(self, player, ptype):
        if player is None:
            status = 'stopped'
        else:
            playerid = player['playerid']
            info = state.PLAYER_STATES[playerid]
            # save this info off so the server update can use it too
            # self.playerprops[playerid] = info
            status = ("paused", "playing")[info['speed']]
        ret = ('\n  <Timeline state="%s" controllable="%s" type="%s" '
               'itemType="%s"' % (status, CONTROLLABLE[ptype], ptype, ptype))
        if player is None:
            ret += ' />'
            return ret

        ret += ' time="%s"' % kodi_time_to_millis(info['time'])
        ret += ' duration="%s"' % kodi_time_to_millis(info['totaltime'])
        ret += ' shuffle="%s"' % ("0", "1")[info['shuffled']]
        ret += ' repeat="%s"' % v.PLEX_REPEAT_FROM_KODI_REPEAT[info['repeat']]
        if ptype != v.KODI_TYPE_PHOTO:
            ret += ' volume="%s"' % info['volume']
            ret += ' mute="%s"' % ("0", "1")[info['muted']]
        pbmc_server = window('pms_server')
        server = self.getServerByHost(self.server)
        if pbmc_server:
            (self.protocol, self.server, self.port) = pbmc_server.split(':')
            self.server = self.server.replace('/', '')
        if info['plex_id']:
            self.lastkey = "/library/metadata/%s" % info['plex_id']
            self.ratingkey = info['plex_id']
            ret += ' key="/library/metadata/%s"' % info['plex_id']
            ret += ' ratingKey="%s"' % info['plex_id']
        # PlayQueue stuff
        playqueue = self.playqueue.playqueues[playerid]
        pos = info['position']
        try:
            ret += ' playQueueItemID="%s"' % playqueue.items[pos].ID or 'null'
            self.containerKey = "/playQueues/%s" % playqueue.ID or 'null'
            ret += ' playQueueID="%s"' % playqueue.ID or 'null'
            ret += ' playQueueVersion="%s"' % playqueue.version or 'null'
            ret += ' containerKey="%s"' % self.containerKey
            ret += ' guid="%s"' % playqueue.items[pos].guid or 'null'
        except IndexError:
            pass
        ret += ' machineIdentifier="%s"' % server.get('uuid', "")
        ret += ' protocol="%s"' % server.get('protocol', 'http')
        ret += ' address="%s"' % server.get('server', self.server)
        ret += ' port="%s"' % server.get('port', self.port)
        # Temp. token set?
        if state.PLEX_TRANSIENT_TOKEN:
            ret += ' token="%s"' % state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            ret += ' token="%s"' % playqueue.plex_transient_token
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
        players = js.get_players()
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
            self._sendNotification(info, int(p['playerid']))
            self.lastinfo[typus] = info
            # Cross the one of the list
            try:
                del self.lastplayers[typus]
            except KeyError:
                pass
        # Process the players we have left (to signal a stop)
        for typus, p in self.lastplayers.iteritems():
            self.lastinfo[typus]['state'] = 'stopped'
            self._sendNotification(self.lastinfo[typus], int(p['playerid']))

    def _sendNotification(self, info, playerid):
        playqueue = self.playqueue.playqueues[playerid]
        xargs = getXArgsDeviceInfo(include_token=False)
        params = {
            'containerKey': self.containerKey or "/library/metadata/900000",
            'key': self.lastkey or "/library/metadata/900000",
            'ratingKey': self.ratingkey or "900000",
            'state': info['state'],
            'time': info['time'],
            'duration': info['duration']
        }
        if state.PLEX_TRANSIENT_TOKEN:
            xargs['X-Plex-Token'] = state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            xargs['X-Plex-Token'] = playqueue.plex_transient_token
        if info.get('playQueueID'):
            params['containerKey'] = '/playQueues/%s' % info['playQueueID']
            params['playQueueVersion'] = info['playQueueVersion']
            params['playQueueItemID'] = info['playQueueItemID']
        serv = self.getServerByHost(self.server)
        url = '%s://%s:%s/:/timeline' % (serv.get('protocol', 'http'),
                                         serv.get('server', 'localhost'),
                                         serv.get('port', '32400'))
        self.doUtils(url, parameters=params, headerOptions=xargs)
        log.debug("Sent server notification with parameters: %s to %s"
                  % (params, url))

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
        # Get the playqueue
        playqueue = self.playqueue.playqueues[playerid]
        # get info from the player
        props = state.PLAYER_STATES[playerid]
        info = {
            'time': kodi_time_to_millis(props['time']),
            'duration': kodi_time_to_millis(props['totaltime']),
            'state': ("paused", "playing")[int(props['speed'])],
            'shuffle': ("0", "1")[props.get('shuffled', False)],
            'repeat': v.PLEX_REPEAT_FROM_KODI_REPEAT[props.get('repeat')]
        }
        pos = props['position']
        try:
            info['playQueueItemID'] = playqueue.items[pos].ID or 'null'
            info['guid'] = playqueue.items[pos].guid or 'null'
            info['playQueueID'] = playqueue.ID or 'null'
            info['playQueueVersion'] = playqueue.version or 'null'
            info['itemType'] = playqueue.items[pos].plex_type or 'null'
        except:
            info['itemType'] = props.get('type') or 'null'

        # get the volume from the application
        info['volume'] = js.get_volume()
        info['mute'] = js.get_muted()

        info['plex_transient_token'] = playqueue.plex_transient_token

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
        log.debug('response is: %s', response)
        if response in [False, None, 401]:
            self.subMgr.removeSubscriber(self.uuid)

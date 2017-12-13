"""
Manages getting playstate from Kodi and sending it to the PMS as well as
subscribed Plex Companion clients.
"""
from logging import getLogger
from re import sub
from threading import Thread, RLock

import downloadutils
from utils import window, kodi_time_to_millis
import state
import variables as v
import json_rpc as js

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################

# What is Companion controllable?
CONTROLLABLE = {
    v.PLEX_TYPE_PHOTO: 'skipPrevious,skipNext,stop',
    v.PLEX_TYPE_AUDIO: 'playPause,stop,volume,shuffle,repeat,seekTo,'
        'skipPrevious,skipNext,stepBack,stepForward',
    v.PLEX_TYPE_VIDEO: 'playPause,stop,volume,shuffle,audioStream,'
        'subtitleStream,seekTo,skipPrevious,skipNext,stepBack,stepForward'
}

class SubscriptionManager:
    """
    Manages Plex companion subscriptions
    """
    def __init__(self, RequestMgr, player, mgr):
        self.serverlist = []
        self.subscribers = {}
        self.info = {}
        self.containerKey = None
        self.ratingkey = None
        self.server = ""
        self.protocol = "http"
        self.port = ""
        # In order to be able to signal a stop at the end
        self.last_params = {}
        self.lastplayers = {}

        self.doUtils = downloadutils.DownloadUtils
        self.xbmcplayer = player
        self.playqueue = mgr.playqueue
        self.RequestMgr = RequestMgr

    @staticmethod
    def _headers():
        """
        Headers are different for Plex Companion!
        """
        return {
            'Content-type': 'text/plain',
            'Connection': 'Keep-Alive',
            'Keep-Alive': 'timeout=20',
            'X-Plex-Client-Identifier': v.PKC_MACHINE_IDENTIFIER,
            'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
            'X-Plex-Protocol': "1.0"
        }

    def getServerByHost(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    def msg(self, players):
        LOG.debug('players: %s', players)
        msg = v.XML_HEADER
        msg += '<MediaContainer size="3" commandID="INSERTCOMMANDID"'
        msg += ' machineIdentifier="%s">\n' % v.PKC_MACHINE_IDENTIFIER
        msg += self.get_timeline_xml(players.get(v.KODI_TYPE_AUDIO),
                                     v.PLEX_TYPE_AUDIO)
        msg += self.get_timeline_xml(players.get(v.KODI_TYPE_PHOTO),
                                     v.PLEX_TYPE_PHOTO)
        msg += self.get_timeline_xml(players.get(v.KODI_TYPE_VIDEO),
                                     v.PLEX_TYPE_VIDEO)
        msg += "</MediaContainer>"
        LOG.debug('msg is: %s', msg)
        return msg

    def _get_container_key(self, playerid):
        key = None
        playlistid = state.PLAYER_STATES[playerid]['playlistid']
        LOG.debug('type: %s, playlistid: %s', type(playlistid), playlistid)
        if playlistid != -1:
            # -1 is Kodi's answer if there is no playlist
            try:
                key = self.playqueue.playqueues[playlistid].id
            except (KeyError, IndexError, TypeError):
                pass
        if key is not None:
            key = '/playQueues/%s' % key
        else:
            if state.PLAYER_STATES[playerid]['plex_id']:
                key = '/library/metadata/%s' % \
                    state.PLAYER_STATES[playerid]['plex_id']
        return key

    def get_timeline_xml(self, player, ptype):
        if player is None:
            return '  <Timeline state="stopped" controllable="%s" type="%s" ' \
                'itemType="%s" />\n' % (CONTROLLABLE[ptype], ptype, ptype)
        playerid = player['playerid']
        info = state.PLAYER_STATES[playerid]
        status = 'paused' if info['speed'] == '0' else 'playing'
        ret = '  <Timeline state="%s"' % status
        ret += ' controllable="%s"' % CONTROLLABLE[ptype]
        ret += ' type="%s" itemType="%s"' % (ptype, ptype)
        ret += ' time="%s"' % kodi_time_to_millis(info['time'])
        ret += ' duration="%s"' % kodi_time_to_millis(info['totaltime'])
        shuffled = '1' if info['shuffled'] else '0'
        ret += ' shuffle="%s"' % shuffled
        ret += ' repeat="%s"' % v.PLEX_REPEAT_FROM_KODI_REPEAT[info['repeat']]
        if ptype != v.KODI_TYPE_PHOTO:
            ret += ' volume="%s"' % info['volume']
            muted = '1' if info['muted'] is True else '0'
            ret += ' mute="%s"' % muted
        pbmc_server = window('pms_server')
        server = self.getServerByHost(self.server)
        if pbmc_server:
            (self.protocol, self.server, self.port) = pbmc_server.split(':')
            self.server = self.server.replace('/', '')
        if info['plex_id']:
            self.ratingkey = info['plex_id']
            ret += ' key="/library/metadata/%s"' % info['plex_id']
            ret += ' ratingKey="%s"' % info['plex_id']
        # PlayQueue stuff
        playqueue = self.playqueue.playqueues[playerid]
        key = self._get_container_key(playerid)
        if key is not None and key.startswith('/playQueues'):
            self.containerKey = key
            ret += ' containerKey="%s"' % self.containerKey
            pos = info['position']
            ret += ' playQueueItemID="%s"' % playqueue.items[pos].id or 'null'
            ret += ' playQueueID="%s"' % playqueue.id or 'null'
            ret += ' playQueueVersion="%s"' % playqueue.version or 'null'
            ret += ' guid="%s"' % playqueue.items[pos].guid or 'null'
        elif key:
            self.containerKey = key
            ret += ' containerKey="%s"' % self.containerKey
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
        ret += '/>\n'
        return ret

    def updateCommandID(self, uuid, commandID):
        if commandID and self.subscribers.get(uuid, False):
            self.subscribers[uuid].commandID = int(commandID)

    def notify(self, event=False):
        self.cleanup()
        # Do we need a check to NOT tell about e.g. PVR/TV and Addon playback?
        players = js.get_players()
        # fetch the message, subscribers or not, since the server
        # will need the info anyway
        msg = self.msg(players)
        if self.subscribers:
            with RLock():
                for subscriber in self.subscribers.values():
                    subscriber.send_update(msg, len(players) == 0)
        self.notifyServer(players)
        self.lastplayers = players
        return True

    def notifyServer(self, players):
        for typus, player in players.iteritems():
            self._send_pms_notification(
                player['playerid'], self._get_pms_params(player['playerid']))
            try:
                del self.lastplayers[typus]
            except KeyError:
                pass
        # Process the players we have left (to signal a stop)
        for typus, player in self.lastplayers.iteritems():
            self.last_params['state'] = 'stopped'
            self._send_pms_notification(player['playerid'], self.last_params)

    def _get_pms_params(self, playerid):
        info = state.PLAYER_STATES[playerid]
        status = 'paused' if info['speed'] == '0' else 'playing'
        params = {'state': status,
            'ratingKey': self.ratingkey,
            'key': '/library/metadata/%s' % self.ratingkey,
            'time': kodi_time_to_millis(info['time']),
            'duration': kodi_time_to_millis(info['totaltime'])
        }
        if self.containerKey:
            params['containerKey'] = self.containerKey
        if self.containerKey is not None and \
                self.containerKey.startswith('/playQueues/'):
            params['playQueueVersion'] = info['playQueueVersion']
            params['playQueueItemID'] = info['playQueueItemID']
        self.last_params = params
        return params

    def _send_pms_notification(self, playerid, params):
        serv = self.getServerByHost(self.server)
        xargs = self._headers()
        playqueue = self.playqueue.playqueues[playerid]
        if state.PLEX_TRANSIENT_TOKEN:
            xargs['X-Plex-Token'] = state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            xargs['X-Plex-Token'] = playqueue.plex_transient_token
        url = '%s://%s:%s/:/timeline' % (serv.get('protocol', 'http'),
                                         serv.get('server', 'localhost'),
                                         serv.get('port', '32400'))
        self.doUtils().downloadUrl(
            url, parameters=params, headerOptions=xargs)
        # Save to be able to signal a stop at the end
        LOG.debug("Sent server notification with parameters: %s to %s",
                  params, url)

    def addSubscriber(self, protocol, host, port, uuid, commandID):
        subscriber = Subscriber(protocol,
                                host,
                                port,
                                uuid,
                                commandID,
                                self,
                                self.RequestMgr)
        with RLock():
            self.subscribers[subscriber.uuid] = subscriber
        return subscriber

    def removeSubscriber(self, uuid):
        with RLock():
            for subscriber in self.subscribers.values():
                if subscriber.uuid == uuid or subscriber.host == uuid:
                    subscriber.cleanup()
                    del self.subscribers[subscriber.uuid]

    def cleanup(self):
        with RLock():
            for subscriber in self.subscribers.values():
                if subscriber.age > 30:
                    subscriber.cleanup()
                    del self.subscribers[subscriber.uuid]


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
        self.doUtils = downloadutils.DownloadUtils
        self.subMgr = subMgr
        self.RequestMgr = RequestMgr

    def __eq__(self, other):
        return self.uuid == other.uuid

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
        msg = sub(r"INSERTCOMMANDID", str(self.commandID), msg)
        LOG.debug("sending xml to subscriber uuid=%s,commandID=%i:\n%s",
                  self.uuid, self.commandID, msg)
        url = self.protocol + '://' + self.host + ':' + self.port \
            + "/:/timeline"
        t = Thread(target=self.threadedSend, args=(url, msg))
        t.start()

    def threadedSend(self, url, msg):
        """
        Threaded POST request, because they stall due to PMS response missing
        the Content-Length header :-(
        """
        response = self.doUtils().downloadUrl(url,
                                              postBody=msg,
                                              action_type="POST")
        if response in [False, None, 401]:
            self.subMgr.removeSubscriber(self.uuid)

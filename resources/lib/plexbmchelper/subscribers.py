"""
Manages getting playstate from Kodi and sending it to the PMS as well as
subscribed Plex Companion clients.
"""
from logging import getLogger
from re import sub
from threading import Thread, Lock

from downloadutils import DownloadUtils as DU
from utils import window, kodi_time_to_millis, Lock_Function
from playlist_func import init_Plex_playlist
import state
import variables as v
import json_rpc as js

###############################################################################

LOG = getLogger("PLEX." + __name__)
# Need to lock all methods and functions messing with subscribers or state
LOCK = Lock()
LOCKER = Lock_Function(LOCK)

###############################################################################

# What is Companion controllable?
CONTROLLABLE = {
    v.PLEX_TYPE_PHOTO: 'skipPrevious,skipNext,stop',
    v.PLEX_TYPE_AUDIO: 'playPause,stop,volume,shuffle,repeat,seekTo,'
                       'skipPrevious,skipNext,stepBack,stepForward',
    v.PLEX_TYPE_VIDEO: 'playPause,stop,volume,shuffle,audioStream,'
                       'subtitleStream,seekTo,skipPrevious,skipNext,'
                       'stepBack,stepForward'
}

STREAM_DETAILS = {
    'video': 'currentvideostream',
    'audio': 'currentaudiostream',
    'subtitle': 'currentsubtitle'
}


class SubscriptionMgr(object):
    """
    Manages Plex companion subscriptions
    """
    def __init__(self, request_mgr, player, mgr):
        self.serverlist = []
        self.subscribers = {}
        self.info = {}
        self.container_key = None
        self.ratingkey = None
        self.server = ""
        self.protocol = "http"
        self.port = ""
        self.isplaying = False
        # In order to be able to signal a stop at the end
        self.last_params = {}
        self.lastplayers = {}

        self.xbmcplayer = player
        self.playqueue = mgr.playqueue
        self.request_mgr = request_mgr

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

    def _server_by_host(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    @LOCKER.lockthis
    def msg(self, players):
        """
        Returns a timeline xml as str
        (xml containing video, audio, photo player state)
        """
        msg = v.XML_HEADER
        msg += '<MediaContainer size="3" commandID="INSERTCOMMANDID"'
        msg += ' machineIdentifier="%s">\n' % v.PKC_MACHINE_IDENTIFIER
        msg += self._timeline_xml(players.get(v.KODI_TYPE_AUDIO),
                                  v.PLEX_TYPE_AUDIO)
        msg += self._timeline_xml(players.get(v.KODI_TYPE_PHOTO),
                                  v.PLEX_TYPE_PHOTO)
        msg += self._timeline_xml(players.get(v.KODI_TYPE_VIDEO),
                                  v.PLEX_TYPE_VIDEO)
        msg += "</MediaContainer>"
        LOG.debug('Our PKC message is: %s', msg)
        return msg

    def signal_stop(self):
        """
        Externally called on PKC shutdown to ensure that PKC signals a stop to
        the PMS. Otherwise, PKC might be stuck at "currently playing"
        """
        LOG.info('Signaling a complete stop to PMS')
        # To avoid RuntimeError, don't use self.lastplayers
        for playerid in (0, 1, 2):
            self.last_params['state'] = 'stopped'
            self._send_pms_notification(playerid, self.last_params)

    def _get_container_key(self, playerid):
        key = None
        playlistid = state.PLAYER_STATES[playerid]['playlistid']
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

    def _plex_stream_index(self, playerid, stream_type):
        """
        Returns the current Plex stream index [str] for the player playerid

        stream_type: 'video', 'audio', 'subtitle'
        """
        playqueue = self.playqueue.playqueues[playerid]
        info = state.PLAYER_STATES[playerid]
        return playqueue.items[info['position']].plex_stream_index(
            info[STREAM_DETAILS[stream_type]]['index'], stream_type)

    @staticmethod
    def _player_info(playerid):
        """
        Grabs all player info again for playerid [int].
        Returns the dict state.PLAYER_STATES[playerid]
        """
        # Update our PKC state of how the player actually looks like
        state.PLAYER_STATES[playerid].update(js.get_player_props(playerid))
        state.PLAYER_STATES[playerid]['volume'] = js.get_volume()
        state.PLAYER_STATES[playerid]['muted'] = js.get_muted()
        return state.PLAYER_STATES[playerid]

    def _timeline_xml(self, player, ptype):
        if player is None:
            return '  <Timeline state="stopped" controllable="%s" type="%s" ' \
                'itemType="%s" />\n' % (CONTROLLABLE[ptype], ptype, ptype)
        playerid = player['playerid']
        info = self._player_info(playerid)
        playqueue = self.playqueue.playqueues[playerid]
        pos = info['position']
        try:
            playqueue.items[pos]
        except IndexError:
            # E.g. for direct path playback for single item
            return '  <Timeline state="stopped" controllable="%s" type="%s" ' \
                'itemType="%s" />\n' % (CONTROLLABLE[ptype], ptype, ptype)
        LOG.debug('INFO: %s', info)
        LOG.debug('playqueue: %s', playqueue)
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
        server = self._server_by_host(self.server)
        if pbmc_server:
            (self.protocol, self.server, self.port) = pbmc_server.split(':')
            self.server = self.server.replace('/', '')
        if info['plex_id']:
            self.ratingkey = info['plex_id']
            ret += ' key="/library/metadata/%s"' % info['plex_id']
            ret += ' ratingKey="%s"' % info['plex_id']
        # PlayQueue stuff
        key = self._get_container_key(playerid)
        if key is not None and key.startswith('/playQueues'):
            self.container_key = key
            ret += ' containerKey="%s"' % self.container_key
            ret += ' playQueueItemID="%s"' % playqueue.items[pos].id or 'null'
            ret += ' playQueueID="%s"' % playqueue.id or 'null'
            ret += ' playQueueVersion="%s"' % playqueue.version or 'null'
            ret += ' guid="%s"' % playqueue.items[pos].guid or 'null'
        elif key:
            self.container_key = key
            ret += ' containerKey="%s"' % self.container_key
        ret += ' machineIdentifier="%s"' % server.get('uuid', "")
        ret += ' protocol="%s"' % server.get('protocol', 'http')
        ret += ' address="%s"' % server.get('server', self.server)
        ret += ' port="%s"' % server.get('port', self.port)
        # Temp. token set?
        if state.PLEX_TRANSIENT_TOKEN:
            ret += ' token="%s"' % state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            ret += ' token="%s"' % playqueue.plex_transient_token
        # Process audio and subtitle streams
        if ptype != v.KODI_TYPE_PHOTO:
            strm_id = self._plex_stream_index(playerid, 'audio')
            if strm_id is not None:
                ret += ' audioStreamID="%s"' % strm_id
            else:
                LOG.error('We could not select a Plex audiostream')
        if ptype == v.KODI_TYPE_VIDEO and info['subtitleenabled']:
            try:
                strm_id = self._plex_stream_index(playerid, 'subtitle')
            except KeyError:
                # subtitleenabled can be True while currentsubtitle can be {}
                strm_id = None
            if strm_id is not None:
                # If None, then the subtitle is only present on Kodi side
                ret += ' subtitleStreamID="%s"' % strm_id
        self.isplaying = True
        return ret + '/>\n'

    @LOCKER.lockthis
    def update_command_id(self, uuid, command_id):
        """
        Updates the Plex Companien client with the machine identifier uuid with
        command_id
        """
        if command_id and self.subscribers.get(uuid):
            self.subscribers[uuid].command_id = int(command_id)

    def notify(self):
        """
        Causes PKC to tell the PMS and Plex Companion players to receive a
        notification what's being played.
        """
        with LOCK:
            self._cleanup()
        # Do we need a check to NOT tell about e.g. PVR/TV and Addon playback?
        players = js.get_players()
        # fetch the message, subscribers or not, since the server will need the
        # info anyway
        self.isplaying = False
        msg = self.msg(players)
        with LOCK:
            if self.isplaying is True:
                # If we don't check here, Plex Companion devices will simply
                # drop out of the Plex Companion playback screen
                for subscriber in self.subscribers.values():
                    subscriber.send_update(msg, not players)
            self._notify_server(players)
            self.lastplayers = players
        return True

    def _notify_server(self, players):
        for typus, player in players.iteritems():
            self._send_pms_notification(
                player['playerid'], self._get_pms_params(player['playerid']))
            try:
                del self.lastplayers[typus]
            except KeyError:
                pass
        # Process the players we have left (to signal a stop)
        for _, player in self.lastplayers.iteritems():
            self.last_params['state'] = 'stopped'
            self._send_pms_notification(player['playerid'], self.last_params)

    def _get_pms_params(self, playerid):
        info = state.PLAYER_STATES[playerid]
        status = 'paused' if info['speed'] == '0' else 'playing'
        params = {
            'state': status,
            'ratingKey': self.ratingkey,
            'key': '/library/metadata/%s' % self.ratingkey,
            'time': kodi_time_to_millis(info['time']),
            'duration': kodi_time_to_millis(info['totaltime'])
        }
        if self.container_key:
            params['containerKey'] = self.container_key
        if self.container_key is not None and \
                self.container_key.startswith('/playQueues/'):
            playqueue = self.playqueue.playqueues[playerid]
            params['playQueueVersion'] = playqueue.version
            params['playQueueItemID'] = playqueue.id
        self.last_params = params
        return params

    def _send_pms_notification(self, playerid, params):
        serv = self._server_by_host(self.server)
        xargs = self._headers()
        playqueue = self.playqueue.playqueues[playerid]
        if state.PLEX_TRANSIENT_TOKEN:
            xargs['X-Plex-Token'] = state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            xargs['X-Plex-Token'] = playqueue.plex_transient_token
        elif state.PLEX_TOKEN:
            xargs['X-Plex-Token'] = state.PLEX_TOKEN
        url = '%s://%s:%s/:/timeline' % (serv.get('protocol', 'http'),
                                         serv.get('server', 'localhost'),
                                         serv.get('port', '32400'))
        DU().downloadUrl(url, parameters=params, headerOptions=xargs)
        LOG.debug("Sent server notification with parameters: %s to %s",
                  params, url)

    @LOCKER.lockthis
    def add_subscriber(self, protocol, host, port, uuid, command_id):
        """
        Adds a new Plex Companion subscriber to PKC.
        """
        subscriber = Subscriber(protocol,
                                host,
                                port,
                                uuid,
                                command_id,
                                self,
                                self.request_mgr)
        self.subscribers[subscriber.uuid] = subscriber
        return subscriber

    @LOCKER.lockthis
    def remove_subscriber(self, uuid):
        """
        Removes a connected Plex Companion subscriber with machine identifier
        uuid from PKC notifications.
        (Calls the cleanup() method of the subscriber)
        """
        for subscriber in self.subscribers.values():
            if subscriber.uuid == uuid or subscriber.host == uuid:
                subscriber.cleanup()
                del self.subscribers[subscriber.uuid]

    def _cleanup(self):
        for subscriber in self.subscribers.values():
            if subscriber.age > 30:
                subscriber.cleanup()
                del self.subscribers[subscriber.uuid]


class Subscriber(object):
    """
    Plex Companion subscribing device
    """
    def __init__(self, protocol, host, port, uuid, command_id, sub_mgr,
                 request_mgr):
        self.protocol = protocol or "http"
        self.host = host
        self.port = port or 32400
        self.uuid = uuid or host
        self.command_id = int(command_id) or 0
        self.navlocationsent = False
        self.age = 0
        self.sub_mgr = sub_mgr
        self.request_mgr = request_mgr

    def __eq__(self, other):
        return self.uuid == other.uuid

    def cleanup(self):
        """
        Closes the connection to the Plex Companion client
        """
        self.request_mgr.closeConnection(self.protocol, self.host, self.port)

    def send_update(self, msg, is_nav):
        """
        Sends msg to the Plex Companion client (via .../:/timeline)
        """
        self.age += 1
        if not is_nav:
            self.navlocationsent = False
        elif self.navlocationsent:
            return True
        else:
            self.navlocationsent = True
        msg = sub(r"INSERTCOMMANDID", str(self.command_id), msg)
        LOG.debug("sending xml to subscriber uuid=%s,commandID=%i:\n%s",
                  self.uuid, self.command_id, msg)
        url = self.protocol + '://' + self.host + ':' + self.port \
            + "/:/timeline"
        thread = Thread(target=self._threaded_send, args=(url, msg))
        thread.start()

    def _threaded_send(self, url, msg):
        """
        Threaded POST request, because they stall due to PMS response missing
        the Content-Length header :-(
        """
        response = DU().downloadUrl(url, postBody=msg, action_type="POST")
        if response in (False, None, 401):
            self.sub_mgr.remove_subscriber(self.uuid)

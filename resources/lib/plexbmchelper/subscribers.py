"""
Manages getting playstate from Kodi and sending it to the PMS as well as
subscribed Plex Companion clients.
"""
from logging import getLogger
from threading import Thread, RLock

from downloadutils import DownloadUtils as DU
from utils import window, kodi_time_to_millis, Lock_Function
import state
import variables as v
import json_rpc as js

###############################################################################

LOG = getLogger("PLEX." + __name__)
# Need to lock all methods and functions messing with subscribers or state
LOCK = RLock()
LOCKER = Lock_Function(LOCK)

###############################################################################

# What is Companion controllable?
CONTROLLABLE = {
    v.PLEX_PLAYLIST_TYPE_VIDEO: 'playPause,stop,volume,shuffle,audioStream,'
        'subtitleStream,seekTo,skipPrevious,skipNext,'
        'stepBack,stepForward',
    v.PLEX_PLAYLIST_TYPE_AUDIO: 'playPause,stop,volume,shuffle,repeat,seekTo,'
        'skipPrevious,skipNext,stepBack,stepForward',
    v.PLEX_PLAYLIST_TYPE_PHOTO: 'skipPrevious,skipNext,stop'
}

STREAM_DETAILS = {
    'video': 'currentvideostream',
    'audio': 'currentaudiostream',
    'subtitle': 'currentsubtitle'
}

XML = ('%s<MediaContainer commandID="{command_id}" location="{location}">\n'
       '  <Timeline {%s}/>\n'
       '  <Timeline {%s}/>\n'
       '  <Timeline {%s}/>\n'
       '</MediaContainer>\n') % (v.XML_HEADER,
                                 v.PLEX_PLAYLIST_TYPE_VIDEO,
                                 v.PLEX_PLAYLIST_TYPE_AUDIO,
                                 v.PLEX_PLAYLIST_TYPE_PHOTO)


def update_player_info(playerid):
    """
    Updates all player info for playerid [int] in state.py.
    """
    state.PLAYER_STATES[playerid].update(js.get_player_props(playerid))
    state.PLAYER_STATES[playerid]['volume'] = js.get_volume()
    state.PLAYER_STATES[playerid]['muted'] = js.get_muted()


class SubscriptionMgr(object):
    """
    Manages Plex companion subscriptions
    """
    def __init__(self, request_mgr, player, mgr):
        self.serverlist = []
        self.subscribers = {}
        self.info = {}
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
        self.isplaying = False
        answ = str(XML)
        timelines = {
            v.PLEX_PLAYLIST_TYPE_VIDEO: None,
            v.PLEX_PLAYLIST_TYPE_AUDIO: None,
            v.PLEX_PLAYLIST_TYPE_PHOTO: None
        }
        for typus in timelines:
            if players.get(v.KODI_PLAYLIST_TYPE_FROM_PLEX_PLAYLIST_TYPE[typus]) is None:
                timeline = {
                    'controllable': CONTROLLABLE[typus],
                    'type': typus,
                    'state': 'stopped'
                }
            else:
                timeline = self._timeline_dict(players[
                    v.KODI_PLAYLIST_TYPE_FROM_PLEX_PLAYLIST_TYPE[typus]], typus)
            timelines[typus] = self._dict_to_xml(timeline)
        location = 'fullScreenVideo' if self.isplaying else 'navigation'
        timelines.update({'command_id': '{command_id}', 'location': location})
        return answ.format(**timelines)

    @staticmethod
    def _dict_to_xml(dictionary):
        """
        Returns the string 'key1="value1" key2="value2" ...' for dictionary
        """
        answ = ''
        for key, value in dictionary.iteritems():
            answ += '%s="%s" ' % (key, value)
        return answ

    def _timeline_dict(self, player, ptype):
        playerid = player['playerid']
        info = state.PLAYER_STATES[playerid]
        playqueue = self.playqueue.playqueues[playerid]
        pos = info['position']
        try:
            playqueue.items[pos]
        except IndexError:
            # E.g. for direct path playback for single item
            return {
                'controllable': CONTROLLABLE[ptype],
                'type': ptype,
                'state': 'stopped'
            }
        pbmc_server = window('pms_server')
        if pbmc_server:
            (self.protocol, self.server, self.port) = pbmc_server.split(':')
            self.server = self.server.replace('/', '')
        status = 'paused' if info['speed'] == '0' else 'playing'
        duration = kodi_time_to_millis(info['totaltime'])
        shuffle = '1' if info['shuffled'] else '0'
        mute = '1' if info['muted'] is True else '0'
        answ = {
            'location': 'fullScreenVideo',
            'controllable': CONTROLLABLE[ptype],
            'protocol': self.protocol,
            'address': self.server,
            'port': self.port,
            'machineIdentifier': window('plex_machineIdentifier'),
            'state': status,
            'type': ptype,
            'itemType': ptype,
            'time': kodi_time_to_millis(info['time']),
            'duration': duration,
            'seekRange': '0-%s' % duration,
            'shuffle': shuffle,
            'repeat': v.PLEX_REPEAT_FROM_KODI_REPEAT[info['repeat']],
            'volume': info['volume'],
            'mute': mute,
            'mediaIndex': pos,  # Still to implement from here
            'partIndex':0,
            'partCount': len(playqueue.items),
            'providerIdentifier': 'com.plexapp.plugins.library',
        }

        if info['plex_id']:
            answ['key'] = '/library/metadata/%s' % info['plex_id']
            answ['ratingKey'] = info['plex_id']
        # PlayQueue stuff
        if info['container_key']:
            answ['containerKey'] = info['container_key']
        if (info['container_key'] is not None and
                info['container_key'].startswith('/playQueues')):
            answ['playQueueID'] = playqueue.id
            answ['playQueueVersion'] = playqueue.version
            answ['playQueueItemID'] = playqueue.items[pos].id
        if playqueue.items[pos].guid:
            answ['guid'] = playqueue.items[pos].guid
        # Temp. token set?
        if state.PLEX_TRANSIENT_TOKEN:
            answ['token'] = state.PLEX_TRANSIENT_TOKEN
        elif playqueue.plex_transient_token:
            answ['token'] = playqueue.plex_transient_token
        # Process audio and subtitle streams
        if ptype != v.PLEX_PLAYLIST_TYPE_PHOTO:
            strm_id = self._plex_stream_index(playerid, 'audio')
            if strm_id:
                answ['audioStreamID'] = strm_id
            else:
                LOG.error('We could not select a Plex audiostream')
        if ptype == v.PLEX_PLAYLIST_TYPE_VIDEO:
            strm_id = self._plex_stream_index(playerid, 'video')
            if strm_id:
                answ['videoStreamID'] = strm_id
            else:
                LOG.error('We could not select a Plex videostream')
            if info['subtitleenabled']:
                try:
                    strm_id = self._plex_stream_index(playerid, 'subtitle')
                except KeyError:
                    # subtitleenabled can be True while currentsubtitle can
                    # still be {}
                    strm_id = None
                if strm_id is not None:
                    # If None, then the subtitle is only present on Kodi side
                    answ['subtitleStreamID'] = strm_id
        self.isplaying = True
        return answ

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

    def _plex_stream_index(self, playerid, stream_type):
        """
        Returns the current Plex stream index [str] for the player playerid

        stream_type: 'video', 'audio', 'subtitle'
        """
        playqueue = self.playqueue.playqueues[playerid]
        info = state.PLAYER_STATES[playerid]
        return playqueue.items[info['position']].plex_stream_index(
            info[STREAM_DETAILS[stream_type]]['index'], stream_type)

    @LOCKER.lockthis
    def update_command_id(self, uuid, command_id):
        """
        Updates the Plex Companien client with the machine identifier uuid with
        command_id
        """
        if command_id and self.subscribers.get(uuid):
            self.subscribers[uuid].command_id = int(command_id)

    @LOCKER.lockthis
    def notify(self):
        """
        Causes PKC to tell the PMS and Plex Companion players to receive a
        notification what's being played.
        """
        self._cleanup()
        # Get all the active/playing Kodi players (video, audio, pictures)
        players = js.get_players()
        # Update the PKC info with what's playing on the Kodi side
        for player in players.values():
            update_player_info(player['playerid'])
        if self.subscribers and state.PLAYBACK_INIT_DONE is True:
            msg = self.msg(players)
            if self.isplaying is True:
                # If we don't check here, Plex Companion devices will simply
                # drop out of the Plex Companion playback screen
                for subscriber in self.subscribers.values():
                    subscriber.send_update(msg, not players)
        self._notify_server(players)
        self.lastplayers = players

    def _notify_server(self, players):
        for typus, player in players.iteritems():
            self._send_pms_notification(
                player['playerid'], self._get_pms_params(player['playerid']))
            try:
                del self.lastplayers[typus]
            except KeyError:
                pass
        # Process the players we have left (to signal a stop)
        for player in self.lastplayers.values():
            self.last_params['state'] = 'stopped'
            self._send_pms_notification(player['playerid'], self.last_params)

    def _get_pms_params(self, playerid):
        info = state.PLAYER_STATES[playerid]
        status = 'paused' if info['speed'] == '0' else 'playing'
        params = {
            'state': status,
            'ratingKey': info['plex_id'],
            'key': '/library/metadata/%s' % info['plex_id'],
            'time': kodi_time_to_millis(info['time']),
            'duration': kodi_time_to_millis(info['totaltime'])
        }
        if info['container_key'] is not None:
            params['containerKey'] = info['container_key']
            if info['container_key'].startswith('/playQueues/'):
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
        msg = msg.format(command_id=self.command_id)
        LOG.debug("sending xml to subscriber uuid=%s,commandID=%i:\n%s",
                  self.uuid, self.command_id, msg)
        url = '%s://%s:%s/:/timeline' % (self.protocol, self.host, self.port)
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

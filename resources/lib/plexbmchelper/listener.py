import re
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse, parse_qs

from xbmc import sleep

from functions import *
from utils import logging


@logging
class MyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    regex = re.compile(r'''/playQueues/(\d+)$''')

    def __init__(self, *args, **kwargs):
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
        self.serverlist = []

    def getServerByHost(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    def do_HEAD(self):
        self.logMsg("Serving HEAD request...", 2)
        self.answer_request(0)

    def do_GET(self):
        self.logMsg("Serving GET request...", 2)
        self.answer_request(1)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.send_header('X-Plex-Client-Identifier',
                         self.server.settings['uuid'])
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Max-Age', '1209600')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods',
                         'POST, GET, OPTIONS, DELETE, PUT, HEAD')
        self.send_header(
            'Access-Control-Allow-Headers',
            'x-plex-version, x-plex-platform-version, x-plex-username, '
            'x-plex-client-identifier, x-plex-target-client-identifier, '
            'x-plex-device-name, x-plex-platform, x-plex-product, accept, '
            'x-plex-device')
        self.end_headers()
        self.wfile.close()

    def sendOK(self):
        self.send_response(200)

    def response(self, body, headers={}, code=200):
        try:
            self.send_response(code)
            for key in headers:
                self.send_header(key, headers[key])
            self.send_header('Content-Length', len(body))
            self.send_header('Connection', "close")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.close()
        except:
            pass

    def answer_request(self, sendData):
        self.serverlist = self.server.client.getServerList()
        subMgr = self.server.subscriptionManager
        js = self.server.jsonClass
        settings = self.server.settings
        queue = self.server.queue

        try:
            request_path = self.path[1:]
            request_path = re.sub(r"\?.*", "", request_path)
            url = urlparse(self.path)
            paramarrays = parse_qs(url.query)
            params = {}
            for key in paramarrays:
                params[key] = paramarrays[key][0]
            self.logMsg("remote request_path: %s" % request_path, 2)
            self.logMsg("params received from remote: %s" % params, 2)
            subMgr.updateCommandID(self.headers.get(
                'X-Plex-Client-Identifier',
                self.client_address[0]),
                params.get('commandID', False))
            if request_path == "version":
                self.response(
                    "PlexKodiConnect Plex Companion: Running\r\nVersion: %s"
                    % settings['version'])
            elif request_path == "verify":
                self.response("XBMC JSON connection test:\r\n" +
                              js.jsonrpc("ping"))
            elif "resources" == request_path:
                resp = ('%s'
                        '<MediaContainer>'
                        '<Player'
                        ' title="%s"'
                        ' protocol="plex"'
                        ' protocolVersion="1"'
                        ' protocolCapabilities="navigation,playback,timeline"'
                        ' machineIdentifier="%s"'
                        ' product="PlexKodiConnect"'
                        ' platform="%s"'
                        ' platformVersion="%s"'
                        ' deviceClass="pc"'
                        '/>'
                        '</MediaContainer>'
                        % (getXMLHeader(),
                           settings['client_name'],
                           settings['uuid'],
                           settings['platform'],
                           settings['plexbmc_version']))
                self.logMsg("crafted resources response: %s" % resp, 2)
                self.response(resp, js.getPlexHeaders())
            elif "/subscribe" in request_path:
                self.response(getOKMsg(), js.getPlexHeaders())
                protocol = params.get('protocol', False)
                host = self.client_address[0]
                port = params.get('port', False)
                uuid = self.headers.get('X-Plex-Client-Identifier', "")
                commandID = params.get('commandID', 0)
                subMgr.addSubscriber(protocol,
                                     host,
                                     port,
                                     uuid,
                                     commandID)
            elif "/poll" in request_path:
                if params.get('wait', False) == '1':
                    sleep(950)
                commandID = params.get('commandID', 0)
                self.response(
                    re.sub(r"INSERTCOMMANDID",
                           str(commandID),
                           subMgr.msg(js.getPlayers())),
                    {
                        'X-Plex-Client-Identifier': settings['uuid'],
                        'Access-Control-Expose-Headers':
                            'X-Plex-Client-Identifier',
                        'Access-Control-Allow-Origin': '*',
                        'Content-Type': 'text/xml'
                    })
            elif "/unsubscribe" in request_path:
                self.response(getOKMsg(), js.getPlexHeaders())
                uuid = self.headers.get('X-Plex-Client-Identifier', False) \
                    or self.client_address[0]
                subMgr.removeSubscriber(uuid)
            elif request_path == "player/playback/setParameters":
                self.response(getOKMsg(), js.getPlexHeaders())
                if 'volume' in params:
                    volume = int(params['volume'])
                    self.logMsg("adjusting the volume to %s%%" % volume, 2)
                    js.jsonrpc("Application.SetVolume",
                               {"volume": volume})
            elif "/playMedia" in request_path:
                self.response(getOKMsg(), js.getPlexHeaders())
                offset = params.get('viewOffset', params.get('offset', "0"))
                protocol = params.get('protocol', "http")
                address = params.get('address', self.client_address[0])
                server = self.getServerByHost(address)
                port = params.get('port', server.get('port', '32400'))
                try:
                    containerKey = urlparse(params.get('containerKey')).path
                except:
                    containerKey = ''
                try:
                    playQueueID = self.regex.findall(containerKey)[0]
                except IndexError:
                    playQueueID = ''
                # We need to tell service.py
                queue.put({
                    'action': 'playlist',
                    'data': params
                })
                subMgr.lastkey = params['key']
                subMgr.containerKey = containerKey
                subMgr.playQueueID = playQueueID
                subMgr.server = server.get('server', 'localhost')
                subMgr.port = port
                subMgr.protocol = protocol
                subMgr.notify()
            elif request_path == "player/playback/play":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.PlayPause",
                               {"playerid": playerid, "play": True})
                subMgr.notify()
            elif request_path == "player/playback/pause":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.PlayPause",
                               {"playerid": playerid, "play": False})
                subMgr.notify()
            elif request_path == "player/playback/stop":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.Stop", {"playerid": playerid})
                subMgr.notify()
            elif request_path == "player/playback/seekTo":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.Seek",
                               {"playerid": playerid,
                                "value": millisToTime(
                                    params.get('offset', 0))})
                subMgr.notify()
            elif request_path == "player/playback/stepForward":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.Seek",
                               {"playerid": playerid,
                                "value": "smallforward"})
                subMgr.notify()
            elif request_path == "player/playback/stepBack":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.Seek",
                               {"playerid": playerid,
                                "value": "smallbackward"})
                subMgr.notify()
            elif request_path == "player/playback/skipNext":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.GoTo",
                               {"playerid": playerid,
                                "to": "next"})
                subMgr.notify()
            elif request_path == "player/playback/skipPrevious":
                self.response(getOKMsg(), js.getPlexHeaders())
                for playerid in js.getPlayerIds():
                    js.jsonrpc("Player.GoTo",
                               {"playerid": playerid,
                                "to": "previous"})
                subMgr.notify()
            elif request_path == "player/playback/skipTo":
                js.skipTo(params.get('key').rsplit('/', 1)[1],
                          params.get('type'))
                subMgr.notify()
            elif request_path == "player/navigation/moveUp":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Up")
            elif request_path == "player/navigation/moveDown":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Down")
            elif request_path == "player/navigation/moveLeft":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Left")
            elif request_path == "player/navigation/moveRight":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Right")
            elif request_path == "player/navigation/select":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Select")
            elif request_path == "player/navigation/home":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Home")
            elif request_path == "player/navigation/back":
                self.response(getOKMsg(), js.getPlexHeaders())
                js.jsonrpc("Input.Back")
            else:
                self.logMsg('Unknown request path: %s' % request_path, -1)
            # elif 'player/mirror/details' in request_path:
            #     # Detailed e.g. Movie information page was opened
            #     # CURRENTLY NOT POSSIBLE DUE TO KODI RESTRICTIONS
            #     plexId = params.get('key', params.get('ratingKey'))
            #     if plexId is None:
            #         self.logMsg('Could not get plex id from params: %s'
            #                     % params, -1)
            #         return
            #     if 'library/metadata' in plexId:
            #         plexId = plexId.rsplit('/', 1)[1]
            #     with embydb.GetEmbyDB() as emby_db:
            #         emby_dbitem = emby_db.getItem_byId(plexId)
            #     try:
            #         kodiid = emby_dbitem[0]
            #         mediatype = emby_dbitem[4]
            #     except TypeError:
            #         self.log("No Plex id returned for plexId %s" % plexId, 0)
            #         return
            #     getDBfromPlexType(mediatype)

        except:
            self.logMsg('Error encountered. Traceback:', -1)
            import traceback
            self.logMsg(traceback.print_exc(), -1)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, client, subscriptionManager, jsonClass, settings,
                 queue, *args, **kwargs):
        """
        client: Class handle to plexgdm.plexgdm. We can thus ask for an up-to-
        date serverlist without instantiating anything

        same for SubscriptionManager and jsonClass
        """
        self.client = client
        self.subscriptionManager = subscriptionManager
        self.jsonClass = jsonClass
        self.settings = settings
        self.queue = queue
        HTTPServer.__init__(self, *args, **kwargs)

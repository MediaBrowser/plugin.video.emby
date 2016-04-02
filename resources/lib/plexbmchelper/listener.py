import re
import traceback
import xbmc
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse, parse_qs
import settings
from functions import *
from utils import logging


@logging
class MyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def __init__(self, *args, **kwargs):
        self.serverlist = []
        self.settings = settings.getSettings()
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def getServerByHost(self, host):
        if len(self.serverlist) == 1:
            return self.serverlist[0]
        for server in self.serverlist:
            if (server.get('serverName') in host or
                    server.get('server') in host):
                return server
        return {}

    def do_HEAD(s):
        s.logMsg("Serving HEAD request...", 2)
        s.answer_request(0)

    def do_GET(s):
        s.logMsg("Serving GET request...", 2)
        s.answer_request(1)

    def do_OPTIONS(s):
        s.send_response(200)
        s.send_header('Content-Length', '0')
        s.send_header('X-Plex-Client-Identifier', s.settings['uuid'])
        s.send_header('Content-Type', 'text/plain')
        s.send_header('Connection', 'close')
        s.send_header('Access-Control-Max-Age', '1209600')
        s.send_header('Access-Control-Allow-Origin', '*')
        s.send_header('Access-Control-Allow-Methods',
                      'POST, GET, OPTIONS, DELETE, PUT, HEAD')
        s.send_header('Access-Control-Allow-Headers',
                      'x-plex-version, x-plex-platform-version, '
                      'x-plex-username, x-plex-client-identifier, '
                      'x-plex-target-client-identifier, x-plex-device-name, '
                      'x-plex-platform, x-plex-product, accept, x-plex-device')
        s.end_headers()
        s.wfile.close()

    def response(s, body, headers={}, code=200):
        try:
            s.send_response(code)
            for key in headers:
                s.send_header(key, headers[key])
            s.send_header('Content-Length', len(body))
            s.send_header('Connection', "close")
            s.end_headers()
            s.wfile.write(body)
            s.wfile.close()
        except:
            pass

    def answer_request(s, sendData):
        s.serverlist = s.server.client.getServerList()
        s.subMgr = s.server.subscriptionManager
        s.js = s.server.jsonClass
        try:
            request_path = s.path[1:]
            request_path = re.sub(r"\?.*", "", request_path)
            url = urlparse(s.path)
            paramarrays = parse_qs(url.query)
            params = {}
            for key in paramarrays:
                params[key] = paramarrays[key][0]
            s.logMsg("request path is: [%s]" % (request_path,), 2)
            s.logMsg("params are: %s" % params, 2)
            s.subMgr.updateCommandID(s.headers.get('X-Plex-Client-Identifier', s.client_address[0]), params.get('commandID', False))
            if request_path=="version":
                s.response("PleXBMC Helper Remote Redirector: Running\r\nVersion: %s" % s.settings['version'])
            elif request_path=="verify":
                result=s.js.jsonrpc("ping")
                s.response("XBMC JSON connection test:\r\n"+result)
            elif "resources" == request_path:
                resp = getXMLHeader()
                resp += "<MediaContainer>"
                resp += "<Player"
                resp += ' title="%s"' % s.settings['client_name']
                resp += ' protocol="plex"'
                resp += ' protocolVersion="1"'
                resp += ' protocolCapabilities="navigation,playback,timeline"'
                resp += ' machineIdentifier="%s"' % s.settings['uuid']
                resp += ' product="PlexKodiConnect"'
                resp += ' platform="%s"' % getPlatform()
                resp += ' platformVersion="%s"' % s.settings['plexbmc_version']
                resp += ' deviceClass="pc"'
                resp += "/>"
                resp += "</MediaContainer>"
                s.logMsg("crafted resources response: %s" % resp, 2)
                s.response(resp, s.js.getPlexHeaders())
            elif "/subscribe" in request_path:
                s.response(getOKMsg(), s.js.getPlexHeaders())
                protocol = params.get('protocol', False)
                host = s.client_address[0]
                port = params.get('port', False)
                uuid = s.headers.get('X-Plex-Client-Identifier', "")
                commandID = params.get('commandID', 0)
                s.subMgr.addSubscriber(protocol, host, port, uuid, commandID)
            elif "/poll" in request_path:
                if params.get('wait', False) == '1':
                    xbmc.sleep(950)
                commandID = params.get('commandID', 0)
                s.response(re.sub(r"INSERTCOMMANDID", str(commandID), s.subMgr.msg(s.js.getPlayers())), {
                  'X-Plex-Client-Identifier': s.settings['uuid'],
                  'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
                  'Access-Control-Allow-Origin': '*',
                  'Content-Type': 'text/xml'
                })
            elif "/unsubscribe" in request_path:
                s.response(getOKMsg(), s.js.getPlexHeaders())
                uuid = s.headers.get('X-Plex-Client-Identifier', False) or s.client_address[0]
                s.subMgr.removeSubscriber(uuid)
            elif request_path == "player/playback/setParameters":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                if 'volume' in params:
                    volume = int(params['volume'])
                    s.logMsg("adjusting the volume to %s%%" % volume, 2)
                    s.js.jsonrpc("Application.SetVolume", {"volume": volume})
            elif "/playMedia" in request_path:
                s.response(getOKMsg(), s.js.getPlexHeaders())
                offset = params.get('viewOffset', params.get('offset', "0"))
                protocol = params.get('protocol', "http")
                address = params.get('address', s.client_address[0])
                server = s.getServerByHost(address)
                port = params.get('port', server.get('port', '32400'))
                try:
                    containerKey = urlparse(params.get('containerKey')).path
                except:
                    containerKey = ''
                regex = re.compile(r'''/playQueues/(\d+)$''')
                try:
                    playQueueID = regex.findall(containerKey)[0]
                except IndexError:
                    playQueueID = ''

                s.js.jsonrpc("playmedia", params)
                s.subMgr.lastkey = params['key']
                s.subMgr.containerKey = containerKey
                s.subMgr.playQueueID = playQueueID
                s.subMgr.server = server.get('server', 'localhost')
                s.subMgr.port = port
                s.subMgr.protocol = protocol
                s.subMgr.notify()
            elif request_path == "player/playback/play":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": True})
            elif request_path == "player/playback/pause":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": False})
            elif request_path == "player/playback/stop":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Stop", {"playerid" : playerid})
            elif request_path == "player/playback/seekTo":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":millisToTime(params.get('offset', 0))})
                s.subMgr.notify()
            elif request_path == "player/playback/stepForward":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallforward"})
                s.subMgr.notify()
            elif request_path == "player/playback/stepBack":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallbackward"})
                s.subMgr.notify()
            elif request_path == "player/playback/skipNext":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigforward"})
                s.subMgr.notify()
            elif request_path == "player/playback/skipPrevious":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                for playerid in s.js.getPlayerIds():
                    s.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigbackward"})
                s.subMgr.notify()
            elif request_path == "player/navigation/moveUp":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Up")
            elif request_path == "player/navigation/moveDown":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Down")
            elif request_path == "player/navigation/moveLeft":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Left")
            elif request_path == "player/navigation/moveRight":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Right")
            elif request_path == "player/navigation/select":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Select")
            elif request_path == "player/navigation/home":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Home")
            elif request_path == "player/navigation/back":
                s.response(getOKMsg(), s.js.getPlexHeaders())
                s.js.jsonrpc("Input.Back")
        except:
            traceback.print_exc()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, client, subscriptionManager, jsonClass,
                 *args, **kwargs):
        """
        client: Class handle to plexgdm.plexgdm. We can thus ask for an up-to-
        date serverlist without instantiating anything

        same for SubscriptionManager and jsonClass
        """
        self.client = client
        self.subscriptionManager = subscriptionManager
        self.jsonClass = jsonClass
        HTTPServer.__init__(self, *args, **kwargs)

import re
import traceback
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse, parse_qs

from xbmc import sleep

from functions import *
from utils import logging


@logging
class MyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

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
        self.send_header('X-Plex-Client-Identifier', self.server.settings['uuid'])
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Connection', 'close')
        self.send_header('Access-Control-Max-Age', '1209600')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods',
                      'POST, GET, OPTIONS, DELETE, PUT, HEAD')
        self.send_header('Access-Control-Allow-Headers',
                      'x-plex-version, x-plex-platform-version, '
                      'x-plex-username, x-plex-client-identifier, '
                      'x-plex-target-client-identifier, x-plex-device-name, '
                      'x-plex-platform, x-plex-product, accept, x-plex-device')
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
        self.subMgr = self.server.subscriptionManager
        self.js = self.server.jsonClass
        self.settings = self.server.settings

        try:
            request_path = self.path[1:]
            request_path = re.sub(r"\?.*", "", request_path)
            url = urlparse(self.path)
            paramarrays = parse_qs(url.query)
            params = {}
            for key in paramarrays:
                params[key] = paramarrays[key][0]
            self.logMsg("params received from remote: %s" % params, 2)
            self.subMgr.updateCommandID(self.headers.get('X-Plex-Client-Identifier', self.client_address[0]), params.get('commandID', False))
            if request_path=="version":
                self.response("PleXBMC Helper Remote Redirector: Running\r\nVersion: %s" % self.settings['version'])
            elif request_path=="verify":
                result=self.js.jsonrpc("ping")
                self.response("XBMC JSON connection test:\r\n"+result)
            elif "resources" == request_path:
                resp = getXMLHeader()
                resp += "<MediaContainer>"
                resp += "<Player"
                resp += ' title="%s"' % self.settings['client_name']
                resp += ' protocol="plex"'
                resp += ' protocolVersion="1"'
                resp += ' protocolCapabilities="navigation,playback,timeline"'
                resp += ' machineIdentifier="%s"' % self.settings['uuid']
                resp += ' product="PlexKodiConnect"'
                resp += ' platform="%s"' % self.settings['platform']
                resp += ' platformVersion="%s"' % self.settings['plexbmc_version']
                resp += ' deviceClass="pc"'
                resp += "/>"
                resp += "</MediaContainer>"
                self.logMsg("crafted resources response: %s" % resp, 2)
                self.response(resp, self.js.getPlexHeaders())
            elif "/subscribe" in request_path:
                self.response(getOKMsg(), self.js.getPlexHeaders())
                protocol = params.get('protocol', False)
                host = self.client_address[0]
                port = params.get('port', False)
                uuid = self.headers.get('X-Plex-Client-Identifier', "")
                commandID = params.get('commandID', 0)
                self.subMgr.addSubscriber(protocol, host, port, uuid, commandID)
            elif "/poll" in request_path:
                if params.get('wait', False) == '1':
                    sleep(950)
                commandID = params.get('commandID', 0)
                self.response(re.sub(r"INSERTCOMMANDID", str(commandID), self.subMgr.msg(self.js.getPlayers())), {
                  'X-Plex-Client-Identifier': self.settings['uuid'],
                  'Access-Control-Expose-Headers': 'X-Plex-Client-Identifier',
                  'Access-Control-Allow-Origin': '*',
                  'Content-Type': 'text/xml'
                })
            elif "/unsubscribe" in request_path:
                self.response(getOKMsg(), self.js.getPlexHeaders())
                uuid = self.headers.get('X-Plex-Client-Identifier', False) or self.client_address[0]
                self.subMgr.removeSubscriber(uuid)
            elif request_path == "player/playback/setParameters":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                if 'volume' in params:
                    volume = int(params['volume'])
                    self.logMsg("adjusting the volume to %s%%" % volume, 2)
                    self.js.jsonrpc("Application.SetVolume", {"volume": volume})
            elif "/playMedia" in request_path:
                self.response(getOKMsg(), self.js.getPlexHeaders())
                offset = params.get('viewOffset', params.get('offset', "0"))
                protocol = params.get('protocol', "http")
                address = params.get('address', self.client_address[0])
                server = self.getServerByHost(address)
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

                self.js.jsonrpc("playmedia", params)
                self.subMgr.lastkey = params['key']
                self.subMgr.containerKey = containerKey
                self.subMgr.playQueueID = playQueueID
                self.subMgr.server = server.get('server', 'localhost')
                self.subMgr.port = port
                self.subMgr.protocol = protocol
                self.subMgr.notify()
            elif request_path == "player/playback/play":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": True})
            elif request_path == "player/playback/pause":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.PlayPause", {"playerid" : playerid, "play": False})
            elif request_path == "player/playback/stop":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Stop", {"playerid" : playerid})
            elif request_path == "player/playback/seekTo":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":millisToTime(params.get('offset', 0))})
                self.subMgr.notify()
            elif request_path == "player/playback/stepForward":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallforward"})
                self.subMgr.notify()
            elif request_path == "player/playback/stepBack":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"smallbackward"})
                self.subMgr.notify()
            elif request_path == "player/playback/skipNext":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigforward"})
                self.subMgr.notify()
            elif request_path == "player/playback/skipPrevious":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                for playerid in self.js.getPlayerIds():
                    self.js.jsonrpc("Player.Seek", {"playerid":playerid, "value":"bigbackward"})
                self.subMgr.notify()
            elif request_path == "player/navigation/moveUp":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Up")
            elif request_path == "player/navigation/moveDown":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Down")
            elif request_path == "player/navigation/moveLeft":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Left")
            elif request_path == "player/navigation/moveRight":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Right")
            elif request_path == "player/navigation/select":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Select")
            elif request_path == "player/navigation/home":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Home")
            elif request_path == "player/navigation/back":
                self.response(getOKMsg(), self.js.getPlexHeaders())
                self.js.jsonrpc("Input.Back")
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
            self.logMsg(traceback.print_exc(), -1)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, client, subscriptionManager, jsonClass, settings,
                 *args, **kwargs):
        """
        client: Class handle to plexgdm.plexgdm. We can thus ask for an up-to-
        date serverlist without instantiating anything

        same for SubscriptionManager and jsonClass
        """
        self.client = client
        self.subscriptionManager = subscriptionManager
        self.jsonClass = jsonClass
        self.settings = settings
        HTTPServer.__init__(self, *args, **kwargs)

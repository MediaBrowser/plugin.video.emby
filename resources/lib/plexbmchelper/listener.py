# -*- coding: utf-8 -*-
import logging
from re import sub
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse, parse_qs

from xbmc import sleep
from companion import process_command
from utils import window
import json_rpc as js
from clientinfo import getXArgsDeviceInfo
import variables as v

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


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
        log.debug("Serving HEAD request...")
        self.answer_request(0)

    def do_GET(self):
        log.debug("Serving GET request...")
        self.answer_request(1)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Content-Length', '0')
        self.send_header('X-Plex-Client-Identifier', v.PKC_MACHINE_IDENTIFIER)
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
            'x-plex-device, x-plex-device-screen-resolution')
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

        try:
            request_path = self.path[1:]
            request_path = sub(r"\?.*", "", request_path)
            url = urlparse(self.path)
            paramarrays = parse_qs(url.query)
            params = {}
            for key in paramarrays:
                params[key] = paramarrays[key][0]
            log.debug("remote request_path: %s" % request_path)
            log.debug("params received from remote: %s" % params)
            subMgr.updateCommandID(self.headers.get(
                'X-Plex-Client-Identifier',
                self.client_address[0]),
                params.get('commandID', False))
            if request_path == "version":
                self.response(
                    "PlexKodiConnect Plex Companion: Running\nVersion: %s"
                    % v.ADDON_VERSION)
            elif request_path == "verify":
                self.response("XBMC JSON connection test:\n" +
                              js.ping())
            elif "resources" == request_path:
                resp = ('%s'
                        '<MediaContainer>'
                        '<Player'
                        ' title="%s"'
                        ' protocol="plex"'
                        ' protocolVersion="1"'
                        ' protocolCapabilities="timeline,playback,navigation,playqueues"'
                        ' machineIdentifier="%s"'
                        ' product="PlexKodiConnect"'
                        ' platform="%s"'
                        ' platformVersion="%s"'
                        ' deviceClass="pc"'
                        '/>'
                        '</MediaContainer>'
                        % (v.XML_HEADER,
                           v.DEVICENAME,
                           v.PKC_MACHINE_IDENTIFIER,
                           v.PLATFORM,
                           v.ADDON_VERSION))
                log.debug("crafted resources response: %s" % resp)
                self.response(resp, getXArgsDeviceInfo(include_token=False))
            elif "/subscribe" in request_path:
                self.response(v.COMPANION_OK_MESSAGE,
                              getXArgsDeviceInfo(include_token=False))
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
                    sub(r"INSERTCOMMANDID",
                        str(commandID),
                        subMgr.msg(js.get_players())),
                    {
                        'X-Plex-Client-Identifier': v.PKC_MACHINE_IDENTIFIER,
                        'X-Plex-Protocol': '1.0',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Max-Age': '1209600',
                        'Access-Control-Expose-Headers':
                            'X-Plex-Client-Identifier',
                        'Content-Type': 'text/xml;charset=utf-8'
                    })
            elif "/unsubscribe" in request_path:
                self.response(v.COMPANION_OK_MESSAGE,
                              getXArgsDeviceInfo(include_token=False))
                uuid = self.headers.get('X-Plex-Client-Identifier', False) \
                    or self.client_address[0]
                subMgr.removeSubscriber(uuid)
            else:
                # Throw it to companion.py
                process_command(request_path, params, self.server.queue)
                self.response('', getXArgsDeviceInfo(include_token=False))
                subMgr.notify()
        except:
            log.error('Error encountered. Traceback:')
            import traceback
            log.error(traceback.print_exc())


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def __init__(self, client, subscriptionManager, queue, *args, **kwargs):
        """
        client: Class handle to plexgdm.plexgdm. We can thus ask for an up-to-
        date serverlist without instantiating anything

        same for SubscriptionManager
        """
        self.client = client
        self.subscriptionManager = subscriptionManager
        self.queue = queue
        HTTPServer.__init__(self, *args, **kwargs)

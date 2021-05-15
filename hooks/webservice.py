# -*- coding: utf-8 -*-
import threading
import socketserver as SocketServer

try:
    from http.server import BaseHTTPRequestHandler #,HTTPServer
    import http.client as httplib
except ImportError:
    import BaseHTTPServer
    BaseHTTPRequestHandler = BaseHTTPServer.BaseHTTPRequestHandler
    import httplib

import xbmcvfs
import xbmc

#Run a webservice to capture playback and incomming events.
class WebService(threading.Thread):
    def __init__(self, WebserviceEventOut, WebserviceEventIn, ServerIP, ServerToken, EnableCoverArt, CompressArt):
        self.SocketServer = SocketServer.TCPServer.allow_reuse_address = True
        self.server = TCPServer(('127.0.0.1', 57578), RequestHandler)
        self.server.timeout = 9999
        self.WebserviceEventOut = WebserviceEventOut
        self.WebserviceEventIn = WebserviceEventIn
        self.ServerIP = ServerIP
        self.ServerToken = ServerToken
        self.EnableCoverArt = EnableCoverArt
        self.CompressArt = CompressArt
        self.LOG = "EMBY.hooks.webservice.WebService"
        threading.Thread.__init__(self)

    def stop(self):
        conn = httplib.HTTPConnection("127.0.0.1:57578", timeout=1)
        conn.request("QUIT", "/")
        conn.getresponse()

        #resend as precaution
        try:
            conn.request("QUIT", "/")
            conn.getresponse()
        except:
            pass

        self.server.server_close()

    def run(self):
        xbmc.log(self.LOG + "--->[ webservice/57578 ]", xbmc.LOGWARNING)
        self.server.serve_forever(self.WebserviceEventOut, self.WebserviceEventIn, self.ServerIP, self.ServerToken, self.EnableCoverArt, self.CompressArt)
        xbmc.log(self.LOG + "---<[ webservice/57578 ]", xbmc.LOGWARNING)

#Http server that reacts to self.stop flag.
class TCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    timeout = 9999

    def serve_forever(self, WebserviceEventOut, WebserviceEventIn, ServerIP, ServerToken, EnableCoverArt, CompressArt):
        self.RequestHandlerClass.Stop = False
        self.RequestHandlerClass.WebserviceEventIn = WebserviceEventIn
        self.RequestHandlerClass.WebserviceEventOut = WebserviceEventOut
        self.RequestHandlerClass.ServerIP = ServerIP
        self.RequestHandlerClass.ServerToken = ServerToken
        self.RequestHandlerClass.EnableCoverArt = EnableCoverArt
        self.RequestHandlerClass.CompressArt = CompressArt
        blankfile = xbmcvfs.File("special://home/addons/plugin.video.emby-next-gen/resources/blank.m4v")
        self.RequestHandlerClass.blankfileSize = blankfile.size()
        self.RequestHandlerClass.blankfileData = blankfile.readBytes()
        blankfile.close()

        try:
            while not self.RequestHandlerClass.Stop:
                self.handle_request()
        except:
            return

#Http request handler. Do not use LOG here, it will hang requests in Kodi > show information dialog.
class RequestHandler(BaseHTTPRequestHandler):
    timeout = 0.5
    Stop = False
    WebserviceEventIn = None
    WebserviceEventOut = None
    ServerIP = ""
    ServerToken = ""
    EnableCoverArt = False
    CompressArt = False
    blankfileSize = 0
    blankfileData = b''

    #Mute the webservice requests
    def log_message(self, format, *args):
        pass

    def do_QUIT(self):
        RequestHandler.Stop = True
        self.send_response(200)
        self.end_headers()

    def do_HEAD(self):
        if 'stream' in self.path:
            self.send_response(200)
            self.send_header('Content-type', 'video/mp4')
            self.end_headers()
        else:
            self.do_GET()

    def do_GET(self):
        if 'extrafanart' in self.path or 'extrathumbs' in self.path or 'Extras/' in self.path or self.path.endswith('.nfo'):
            self.send_response(404)
            self.end_headers()
            return

        if 'Images' in self.path:
            self.send_response(301)

            if self.EnableCoverArt:
                ExtendedParameter = "&EnableImageEnhancers=True"
            else:
                ExtendedParameter = "&EnableImageEnhancers=False"

            if self.CompressArt:
                ExtendedParameter += "&Quality=70"

            if "?" in self.path:
                Query = self.ServerIP + "/emby/Items" + self.path + "&api_key=" + self.ServerToken + ExtendedParameter
            else:
                Query = self.ServerIP + "/emby/Items" + self.path + "?api_key=" + self.ServerToken + ExtendedParameter

            self.send_header('Location', Query)
            self.end_headers()
            return

        if 'stream' in self.path:
            self.WebserviceEventOut.put(self.path) #query multiversion video or HLS audio/subtitle
            Response = self.WebserviceEventIn.get()

            if Response == "RELOAD": #Inject blank mp4, forceing a reload
                self.send_response(200)
                self.send_header('Content-type', 'video/mp4')
                self.send_header('Content-Length', str(self.blankfileSize))
                self.end_headers()
                self.wfile.write(self.blankfileData)
                return

            self.send_response(301)
            self.send_header('Location', Response)
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()
        return

# -*- coding: utf-8 -*-
import threading

try:
#    import socketserver as SocketServer
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import http.client as httplib
except ImportError:
    import BaseHTTPServer
    HTTPServer = BaseHTTPServer.HTTPServer
    BaseHTTPRequestHandler = BaseHTTPServer.BaseHTTPRequestHandler
    import httplib

import xbmcvfs
import xbmc

#Run a webservice to capture playback and incomming events.
class WebService(threading.Thread):
    def __init__(self, WebserviceEventOut, WebserviceEventIn, ServerIP, ServerToken):
#        self.SocketServer = SocketServer.TCPServer.allow_reuse_address = True
        self.server = TCPServer(('127.0.0.1', 57578), RequestHandler)
        self.server.timeout = 9999
        self.WebserviceEventOut = WebserviceEventOut
        self.WebserviceEventIn = WebserviceEventIn
        self.ServerIP = ServerIP
        self.ServerToken = ServerToken
        self.LOG = "EMBY.hooks.webservice.WebService"
        threading.Thread.__init__(self)

    def stop(self):
        conn = httplib.HTTPConnection("127.0.0.1:57578")
        conn.request("QUIT", "/")

#        try:
        conn.getresponse()
#        conn.request("QUIT", "/")
#        conn.getresponse()
#        except:
#            pass
        self.server.server_close()

    def run(self):
        xbmc.log(self.LOG + "--->[ webservice/57578 ]", xbmc.LOGWARNING)
        self.server.serve_forever(self.WebserviceEventOut, self.WebserviceEventIn, self.ServerIP, self.ServerToken)
        xbmc.log(self.LOG + "---<[ webservice/57578 ]", xbmc.LOGWARNING)

#Http server that reacts to self.stop flag.
#class TCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
class TCPServer(HTTPServer):
    timeout = 9999

    def serve_forever(self, WebserviceEventOut, WebserviceEventIn, ServerIP, ServerToken):
        self.RequestHandlerClass.Stop = False
        self.WebserviceEventIn = WebserviceEventIn
        self.WebserviceEventOut = WebserviceEventOut
        self.ServerIP = ServerIP
        self.ServerToken = ServerToken
        blankfile = xbmcvfs.File("special://home/addons/plugin.video.emby-next-gen/resources/blank.m4v")
        self.blankfileSize = blankfile.size()
        self.blankfileData = blankfile.readBytes()
        blankfile.close()

        try:
            while not self.RequestHandlerClass.Stop:
                self.handle_request()

            xbmc.log("WEBSERVER 1 stop A15", xbmc.LOGWARNING)

        except:
            xbmc.log("WEBSERVER 1 stop A16", xbmc.LOGWARNING)
            return

        xbmc.log("WEBSERVER 1 stop A17", xbmc.LOGWARNING)

#Http request handler. Do not use LOG here, it will hang requests in Kodi > show information dialog.
class RequestHandler(BaseHTTPRequestHandler): #SimpleHTTPRequestHandler):
    timeout = 0.5
    Stop = False

    def __init__(self, request, client_address, server):
        self.ServerIP = server.ServerIP
        self.ServerToken = server.ServerToken
        self.WebserviceEventIn = server.WebserviceEventIn
        self.WebserviceEventOut = server.WebserviceEventOut
        self.blankfileSize = server.blankfileSize
        self.blankfileData = server.blankfileData
        BaseHTTPRequestHandler.__init__(self, request, client_address, server)

    #Mute the webservice requests
    def log_message(self, format, *args):
        pass

    def do_QUIT(self):
        xbmc.log("WEBSERVER 1 stop A8", xbmc.LOGWARNING)
        RequestHandler.Stop = True
        xbmc.log("WEBSERVER 1 stop A9", xbmc.LOGWARNING)
        self.send_response(200)
        xbmc.log("WEBSERVER 1 stop A10", xbmc.LOGWARNING)
        self.end_headers()
        xbmc.log("WEBSERVER 1 stop A11", xbmc.LOGWARNING)

    def do_HEAD(self):
        if 'stream' in self.path:
            self.send_response(200)
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
            self.send_header('Location', self.ServerIP + "/emby/Items" + self.path + "&api_key=" + self.ServerToken)
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

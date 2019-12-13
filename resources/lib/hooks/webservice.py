# -*- coding: utf-8 -*-

#################################################################################################

import BaseHTTPServer
import logging
import httplib
import threading
import urlparse
import socket
import Queue
from datetime import datetime
#from uuid import uuid4

import xbmc
import xbmcgui
import xbmcvfs

from emby import Emby
from helper import _, settings, window, dialog, JSONRPC

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
PORT = 57578

#################################################################################################


class WebService(threading.Thread):

    ''' Run a webservice to trigger playback.
    '''
    def __init__(self):
        threading.Thread.__init__(self)

    def is_alive(self):

        ''' Called to see if the webservice is still responding.
        '''
        alive = True
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            s.connect(('127.0.0.1', PORT))
            s.sendall("")
        except Exception as error:
            LOG.error(error)

            if 'Errno 61' in str(error):
                alive = False

        s.close()

        return alive

    def stop(self):

        ''' Called when the thread needs to stop
        '''
        try:
            conn = httplib.HTTPConnection("127.0.0.1:%d" % PORT)
            conn.request("QUIT", "/")
            conn.getresponse()
        except Exception as error:
            pass

    def run(self):

        ''' Called to start the webservice.
        '''
        LOG.warn("--->[ webservice/%s ]", PORT)
        self.stop()

        server = HttpServer(('127.0.0.1', PORT), RequestHandler)

        try:
            server.serve_forever()
        except Exception as error:

            if '10053' not in error: # ignore host diconnected errors
                LOG.exception(error)

        LOG.warn("---<[ webservice ]")


class HttpServer(BaseHTTPServer.HTTPServer):

    ''' Http server that reacts to self.stop flag.
    '''
    def serve_forever(self):

        ''' Handle one request at a time until stopped.
        '''
        self.stop = False
        self.last = None
        self.last_time = datetime.today()
        self.pending = []
        self.threads = []
        self.queue = Queue.Queue()

        while not self.stop:
            self.handle_request()


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    ''' Http request handler. Do not use LOG here,
        it will hang requests in Kodi > show information dialog.
    '''
    timeout = 0.5

    def log_message(self, format, *args):

        ''' Mute the webservice requests.
        '''
        pass

    def handle(self):

        ''' To quiet socket errors with 404.
        '''
        try:
            BaseHTTPServer.BaseHTTPRequestHandler.handle(self)
        except Exception as error:
            pass

    def do_QUIT(self):

        ''' send 200 OK response, and set server.stop to True
        '''
        self.send_response(200)
        self.end_headers()
        self.server.stop = True

    def get_params(self):

        ''' Get the params
        '''
        try:
            path = self.path[1:]

            if '?' in path:
                path = path.split('?', 1)[1]

            params = dict(urlparse.parse_qsl(path))
        except Exception:
            params = {}

        if params.get('transcode'):
            params['transcode'] = params['transcode'].lower() == 'true'

        if params.get('server') and params['server'].lower() == 'none':
            params['server'] = None

        return params

    def do_HEAD(self):

        ''' Called on HEAD requests
        '''
        self.handle_request(True)

        return

    def do_GET(self):

        ''' Called on GET requests
        '''
        self.handle_request()

        return

    def handle_request(self, headers_only=False):

        '''Send headers and reponse
        '''
        try:
            if 'extrafanart' in self.path or 'extrathumbs' in self.path or 'Extras/' in self.path:
                raise Exception("unsupported artwork request")

            if '/Audio' in self.path:
                params = self.get_params()

                self.send_response(301)
                path = Redirect(self.path, params.get('server'))
                path.start()
                path.join() # Block until the thread exits.
                self.send_header('Location', path.path)
                self.end_headers()

            elif headers_only:

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

            elif 'file.strm' not in self.path:
                self.images()
            elif 'file.strm' in self.path:
                self.strm()
            else:
                xbmc.log(str(self.path), xbmc.LOGWARNING)
                raise Exception("UnknownRequest")

        except Exception as error:
            self.send_error(500, "[ webservice ] Exception occurred: %s" % error)

        xbmc.log("<[ webservice/%s/%s ]" % (str(id(self)), int(not headers_only)), xbmc.LOGWARNING)

        return

    def strm(self):

        ''' Return a dummy video and and queue real items.
        '''
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        params = self.get_params()

        if 'kodi/movies' in self.path:
            params['MediaType'] = "movie"
        elif 'kodi/musicvideos' in self.path:
            params['MediaType'] = "musicvideo"
        elif 'kodi/tvshows' in self.path:
            params['MediaType'] = "episode"

        if settings('pluginSimple.bool'):
            path = "plugin://plugin.video.emby?mode=playsingle&id=%s" % params['Id']

            if params.get('server'):
                path += "&server=%s" % params['server']

            if params.get('transcode'):
                path += "&transcode=true"

            if params.get('KodiId'):
                path += "&dbid=%s" % params['KodiId']

            if params.get('Name'):
                path += "&filename=%s" % params['Name']

            self.wfile.write(bytes(path))

            return

        path = "plugin://plugin.video.emby?mode=play&id=%s" % params['Id']
        if params.get('server'):
            path += "&server=%s" % params['server']

        if params.get('transcode'):
            path += "&transcode=true"

        if params.get('KodiId'):
            path += "&dbid=%s" % params['KodiId']

        if params.get('Name'):
            path += "&filename=%s" % params['Name']


        if (datetime.today() - self.server.last_time).seconds > 2: # reset, assume new playlist
            self.server.last = None


        if not self.server.last:
            self.wfile.write(bytes(path))

        elif self.server.last == params['Id']:
            self.wfile.write(bytes(""))

            if params['Id'] not in self.server.pending:

                xbmc.log("[ webservice/%s ] path: %s params: %s" % (str(id(self)), str(self.path), str(params)), xbmc.LOGWARNING)
                self.server.pending.append(params['Id'])
                queue = PlayWidget(self.server, params)

        else: # Play folder
            self.wfile.write(bytes(""))

            if params['Id'] not in self.server.pending:
                xbmc.log("[ webservice/%s ] path: %s params: %s" % (str(id(self)), str(self.path), str(params)), xbmc.LOGWARNING)

                self.server.pending.append(params['Id'])
                self.server.queue.put(params)

                if not len(self.server.threads):

                    queue = PlayFolder(self.server)
                    self.server.threads.append(queue)

        self.server.last = params['Id']
        self.server.last_time = datetime.today()

    def images(self):

        ''' Return a dummy image for unwanted images requests over the webservice.
            Required to prevent freezing of widget playback if the file url has no
            local textures cached yet.
        '''
        image = xbmc.translatePath("special://home/addons/plugin.video.emby/icon.png").decode('utf-8')

        self.send_response(200)
        self.send_header('Content-type', 'image/png')
        modified = xbmcvfs.Stat(image).st_mtime()
        self.send_header('Last-Modified', "%s" % modified)
        image = xbmcvfs.File(image)
        size = image.size()
        self.send_header('Content-Length', str(size))
        self.end_headers()

        self.wfile.write(image.readBytes())
        image.close()


class Redirect(threading.Thread):
    path = None

    def __init__(self, redirect, server_id=None):

        self.redirect = redirect
        self.server = Emby(server_id).get_client()
        threading.Thread.__init__(self)

    def run(self):

        self.path = "%s%s?api_key=%s&static=true" % (self.server['auth/server-address'], self.redirect, self.server['auth/token'])
        """
        self.path = ("%s?UserId=%s&DeviceId=%s&api_key=%s&MaxStreamingBitrate=1280000&Container=aac,mp3,opus,m4a,webma,webm,wav,ogg,mpa,wma,mp2,ogg,oga,ape&MaxSampleRate=48000",
                     "&TranscodingProtocol=hls&TranscodingContainer=aac&AudioCodec=aac&EnableRedirection=true&EnableRemoteMedia=true&PlaySessionId=%s" % (self.server['auth/server-address'], self.server['auth/user-id'], self.server['config/app.device_id'], self.server['auth/token'], str(uuid4()).replace("-", "")))
        """
        LOG.info("path: %s", self.path)


class PlayWidget(threading.Thread):

    def __init__(self, server, params):
        self.server = server
        self.params = params
        threading.Thread.__init__(self)
        self.start()

    def run(self):
        import objects
        ''' Workaround for widgets only playback.
            Widgets start with a music playlist, this causes bugs in skin, etc.
            Create a new video playlist for the item and play it.
        '''
        xbmc.sleep(200) # Let Kodi catch up
        LOG.info("-->[ widget play ]")
        play = None

        xbmc.PlayList(xbmc.PLAYLIST_MUSIC).clear()
        xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
        objects.utils.enable_busy_dialog()

        try:
            server = self.params.get('server')

            if not server and not window('emby_online.bool'):
                dialog("notification", heading="{emby}", message=_(33146), icon=xbmcgui.NOTIFICATION_ERROR)

                raise Exception("NotConnected")

            play = objects.PlayStrm(self.params, server)
            play.play()

        except Exception as error:
            LOG.exception(error)
            objects.utils.disable_busy_dialog()
            xbmc.Player().stop() # mute failed playback pop up
            xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()        
        else:
            objects.utils.disable_busy_dialog()
            window('emby.play.widget.bool', True)
            play.start_playback()

        self.server.pending = []
        LOG.info("--<[ widget play ]")


class PlayFolder(threading.Thread):

    def __init__(self, server):
        self.server = server
        threading.Thread.__init__(self)
        self.start()

    def run(self):
        import objects
        ''' Workaround for playing folders only (context menu on a series/season folder > play)
            Due to plugin paths being returned within the strm, the entries are mislabelled.
            Queue items after the first item was setup and started playing via plugin above.
        '''
        xbmc.sleep(200) # Let Kodi catch up
        LOG.info("-->[ folder play ]")
        play = None
        position = 1 # play folder should always create a new playlist.
        player = xbmc.Player()

        while True:
            if not window('emby.playlist.plugin.bool'): # default.py wait for initial item to start up
                try:
                    try:
                        params = self.server.queue.get(timeout=0.01)
                    except Queue.Empty:
                        break

                    server = params.get('server')

                    if not server and not window('emby_online.bool'):
                        dialog("notification", heading="{emby}", message=_(33146), icon=xbmcgui.NOTIFICATION_ERROR)

                        raise Exception("NotConnected")

                    play = objects.PlayStrm(params, server)
                    position = play.play_folder(position)

                except Exception as error:
                    LOG.exception(error)

                    xbmc.Player().stop() # mute failed playback pop up
                    xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                    self.server.queue.queue.clear()

                    break

                self.server.queue.task_done()

        self.server.threads.remove(self)
        self.server.pending = []
        LOG.info("--<[ folder play ]")

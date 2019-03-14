# -*- coding: utf-8 -*-

#################################################################################################

import BaseHTTPServer
import logging
import httplib
import threading
import urlparse
import socket
import Queue

import xbmc
import xbmcgui
import xbmcvfs

from helper import settings, window, playstrm

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

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        LOG.info("--->[ webservice/%s ]", PORT)
        server = HttpServer(('127.0.0.1', PORT), RequestHandler)

        try:
            server.serve_forever()
        except Exception as error:

            if '10053' not in error: # ignore host diconnected errors
                LOG.exception(error)

        LOG.info("---<[ webservice ]")


class HttpServer(BaseHTTPServer.HTTPServer):

    ''' Http server that reacts to self.stop flag.
    '''
    def serve_forever(self):

        ''' Handle one request at a time until stopped.
        '''
        self.stop = False
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
            if 'extrafanart' in self.path or 'extrathumbs' in self.path:
                raise Exception("unsupported artwork request")

            if headers_only:

                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

            elif 'file.strm' not in self.path:
                self.images()
            elif 'file.strm' in self.path:
                self.strm()
            else:
                xbmc.log(str(self.path), xbmc.LOGWARNING)

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
            params['MediaType'] = 'musicvideo'
        elif 'kodi/tvshows' in self.path:
            params['MediaType'] = "episode"

        res = xbmc.getInfoLabel('System.ScreenResolution')
        xbmc.log("[ webservice ] resolution: %s" % res, xbmc.LOGWARNING)

        if '@' in res:
            refresh_rate = res.split('@', 1)[1].split('Hz')[0].replace('.', "_")

            if refresh_rate not in ["23_976", "24", "25", "59_97", "30", "50", "59_94", "60"]:
                refresh_rate = "25"
        else:
            refresh_rate = "25"

        loading = xbmc.translatePath("special://home/addons/plugin.video.emby/resources/skins/default/media/videos/%s/emby-loading.mp4" % refresh_rate).decode('utf-8')
        self.wfile.write(bytes(loading))

        if params['Id'] not in self.server.pending:

            xbmc.log("[ webservice/%s ] path: %s params: %s" % (str(id(self)), str(self.path), str(params)), xbmc.LOGWARNING)
            self.server.pending.append(params['Id'])
            self.server.queue.put((params, ''.join(["http://127.0.0.1", ":", str(PORT), self.path.encode('utf-8')]), loading.encode('utf-8'), ))

            if len(self.server.threads) < 1:

                queue = QueuePlay(self.server)
                queue.start()
                self.server.threads.append(queue)

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

class QueuePlay(threading.Thread):

    def __init__(self, server):

        self.server = server
        threading.Thread.__init__(self)

    def run(self):

        ''' Queue up strm playback that was called in the webservice.
            Remove the dummy video in player.py (virtual library paths) and here (actual strm link).

            Required delay for widgets, custom skin containers and non library windows.
            Otherwise Kodi will freeze if no artwork textures are cached yet in Textures13.db
            Will be skipped if the player already has media and is playing.

            Important: Never move the check to start play_folder() to prevent race conditions!
        '''
        LOG.info("-->[ queue play ]")
        init_play = False
        play_folder = False
        play = None

        xbmc.sleep(200) # Let Kodi catch up.
        start_position = None
        position = None
        original_play = None

        def is_playback_ready():

            ''' Waits for prompt setup in player.py that lets
                us know the emby-loading video is paused.

                Returns the path of the emby-loading video.
            '''
            count = 0

            while not window('emby_loadingvideo.bool'):

                if count > 200:
                    raise Exception("Failed to start queue play.")

                count += 1
                xbmc.sleep(50)

            window('emby_loadingvideo', clear=True)

            return xbmc.getInfoLabel('Player.Filenameandpath')

        def finish():

            ''' Terminate this thread correctly.
            '''
            xbmc.executebuiltin('Dialog.Close(busydialognocancel)')
            self.server.threads.remove(self)
            self.server.pending = []

        while True:

            try:
                params, path, loading = self.server.queue.get(timeout=0.01)
            except Queue.Empty:

                finish()

                LOG.info("[ playback starting/%s ]", start_position)
                play.start_playback(start_position)
                play.remove_from_playlist_by_path(loading.decode('utf-8'))

                break

            play = playstrm.PlayStrm(params, params.get('ServerId'), loading.decode('utf-8'))
            play.remove_from_playlist_by_path(path)

            if start_position is None:

                start_position = max(play.info['KodiPlaylist'].getposition(), 0)
                position = start_position

            try:
                if self.server.pending.count(params['Id']) != len(self.server.pending):

                    if play_folder:
                        position = play.play_folder(position)
                    else:
                        play_folder = True
                        original_play = is_playback_ready()
                        start_position = position = play.play()
                        xbmc.executebuiltin('ActivateWindow(busydialognocancel)')
                else:
                    original_play = is_playback_ready()
                    play.play()
            except Exception as error:

                LOG.error(error)
                xbmc.Player().stop()
                self.server.queue.queue.clear()
                finish()

                break

            play.remove_from_playlist_by_path(original_play)
            self.server.queue.task_done()

        LOG.info("--<[ queue play ]")

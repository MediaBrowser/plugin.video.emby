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

import objects
from helper import settings, window, JSONRPC

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
            if not window('emby_online.bool'):
                raise Exception("ServerOffline")

            if 'extrafanart' in self.path or 'extrathumbs' in self.path or 'Extras/' in self.path:
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

        if settings('pluginSingle.bool'):
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

        path = "plugin://plugin.video.emby?mode=playstrm&id=%s" % params['Id']
        self.wfile.write(bytes(path))

        if params['Id'] not in self.server.pending:
            xbmc.log("[ webservice/%s ] path: %s params: %s" % (str(id(self)), str(self.path), str(params)), xbmc.LOGWARNING)

            self.server.pending.append(params['Id'])
            self.server.queue.put(params)

            if not len(self.server.threads):

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

        ''' Workflow for new playback:

            Queue up strm playback that was called in the webservice.
            Called playstrm in default.py which will wait for our signal here.
            Downloads emby information.
            Add content to the playlist after the strm file that initiated playback from db.
            Start playback by telling playstrm waiting. It will fail playback of the current strm and
            move to the next entry for us. If play folder, playback starts here.

            Required delay for widgets, custom skin containers and non library windows.
            Otherwise Kodi will freeze if no artwork textures are cached yet in Textures13.db
            Will be skipped if the player already has media and is playing.

            Why do all this instead of using plugin?
            Strms behaves better than plugin in database.
            Allows to load chapter images with direct play.
            Allows to have proper artwork for intros.
            Faster than resolving using plugin, especially on low powered devices.
            Cons:
            Can't use external players with this method.
        '''
        LOG.info("-->[ queue play ]")
        play_folder = False
        play = None
        start_position = None
        position = None
        playlist_audio = False

        xbmc.sleep(200) # Let Kodi catch up

        while True:

            try:
                try:
                    params = self.server.queue.get(timeout=0.01)
                except Queue.Empty:
                    count = 20

                    if xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):
                    	xbmc.Player().stop()

                    while not window('emby.playlist.ready.bool'):
                        xbmc.sleep(50)

                        if not count:
                            LOG.info("[ playback aborted ]")

                            raise Exception("PlaybackAborted")

                        count -= 1
                    else:
                        LOG.info("[ playback starting/%s ]", start_position)

                        if play_folder:

                            LOG.info("[ start play ]")
                            objects.utils.disable_busy_dialog()
                            play.start_playback()
                        elif window('emby.playlist.audio.bool'):

                            window('emby.playlist.play.bool', True)
                            window('emby.play.reset.bool', True)
                            xbmc.sleep(200)
                            play.start_playback()
                        else:
                            window('emby.playlist.play.bool', True)

                            xbmc.sleep(1000)
                            play.remove_from_playlist(start_position)

                    break

                play = objects.PlayStrm(params, params.get('ServerId'))

                if start_position is None:
                    if window('emby.playlist.audio.bool'):

                        LOG.info("[ relaunch playlist ]")
                        xbmc.PlayList(xbmc.PLAYLIST_MUSIC).clear()
                        xbmc.PlayList(xbmc.PLAYLIST_VIDEO).clear()
                        playlist_audio = True
                        window('emby.playlist.ready.bool', True)

                    start_position = max(play.info['KodiPlaylist'].getposition(), 0)
                    position = start_position + int(not playlist_audio)

                if play_folder:
                    position = play.play_folder(position)
                else:
                    if self.server.pending.count(params['Id']) != len(self.server.pending):
                        play_folder = True

                    window('emby.playlist.start', str(start_position))
                    position = play.play(position)

                    if play_folder:
                        objects.utils.enable_busy_dialog()

            except Exception as error:
                LOG.exception(error)

                if not xbmc.Player().isPlaying():

                    play.info['KodiPlaylist'].clear()
                    xbmc.Player().stop()
                    self.server.queue.queue.clear()

                if play_folder:
                    objects.utils.disable_busy_dialog()
                else:
                    window('emby.playlist.aborted.bool', True)

                break

            self.server.queue.task_done()

        self.stop()

    def stop(self):

        window('emby.playlist.play', clear=True)
        window('emby.playlist.ready', clear=True)
        window('emby.playlist.start', clear=True)
        window('emby.playlist.audio', clear=True)
        window('emby.play.cancel.bool', clear=True)

        self.server.threads.remove(self)
        self.server.pending = []
        LOG.info("--<[ queue play ]")

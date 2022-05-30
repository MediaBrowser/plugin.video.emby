from urllib.parse import urlparse
import json
import os
import array
import struct
import uuid
import base64
import socket
import hashlib
import ssl
from _thread import start_new_thread
import xbmc
from helper import utils, playerops, loghandler

XbmcPlayer = xbmc.Player()
LOG = loghandler.LOG('Emby.hooks.websocket')
actions = {
    'Stop': XbmcPlayer.stop,
    'Unpause': XbmcPlayer.pause,
    'Pause': XbmcPlayer.pause,
    'PlayPause': XbmcPlayer.pause,
    'NextTrack': XbmcPlayer.playnext,
    'PreviousTrack': XbmcPlayer.playprevious
}

def maskData(mask_key, data):
    _m = array.array("B", mask_key)
    _d = array.array("B", data)

    for i in range(len(_d)):
        _d[i] ^= _m[i % 4]  # ixor

    return _d.tobytes()

class WSClient:
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.stop = False
        LOG.debug("WSClient initializing...")
        self.sock = None
        self._recv_buffer = []
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        self._cont_data = None
        self.EmbyServerUrl = ""
        self.ReconnectingInProgress = False
        self.TasksRunning = []
        self.SyncInProgress = False
        self.SyncRefresh = False

    def start(self):
        start_new_thread(self.Listen, ())

    def close(self, Terminate=True):
        LOG.info("Close wesocket connection %s" % self.EmbyServer.server_id)

        if Terminate:
            self.stop = True

        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass

            self.sock.close()
            self.sock = None

    def Listen(self):
        LOG.info("--->[ websocket ]")

        if self.EmbyServer.server.startswith('https'):
            self.EmbyServerUrl = self.EmbyServer.server.replace('https', "wss")
        else:
            self.EmbyServerUrl = self.EmbyServer.server.replace('http', "ws")

        if self.connect():
            while not self.stop:
                data = self.recv()

                if self.stop:
                    break

                if data:
                    self.on_message(data)

                if data is None:  # reconnecting
                    self.reconnecting()
        else:
            LOG.info("[ websocket failed ]")
            self.close()

        LOG.info("---<[ websocket ]")

    def reconnecting(self):
        if not self.ReconnectingInProgress:
            self.ReconnectingInProgress = True

            while not self.stop:
                utils.dialog("notification", heading=utils.addon_name, icon="DefaultIconError.png", message="Websocket connection offline", time=1000, sound=False)
                self.close(False)
                LOG.info("--->[ websocket reconnecting ]")

                if utils.waitForAbort(5):
                    break

                if self.connect():
                    LOG.info("---<[ websocket reconnecting ]")
                    break

                LOG.info("[ websocket reconnecting failed ]")

            self.ReconnectingInProgress = False
        else:
            LOG.info("[ websocket reconnecting in progress ]")

    def connect(self):
        url = "%s/embywebsocket?api_key=%s&device_id=%s" % (self.EmbyServerUrl, self.EmbyServer.Token, utils.device_id)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Parse URL
        scheme, url = url.split(":", 1)
        parsed = urlparse(url, scheme="http")
        resource = parsed.path

        if parsed.query:
            resource += "?" + parsed.query

        hostname = parsed.hostname
        port = parsed.port
        is_secure = scheme == "wss"

        if not port:
            if scheme == "http":
                port = 80
            else:
                port = 443

        # Connect
        try:
            self.sock.connect((hostname, port))
        except:
            return False

        self.sock.settimeout(15) # set timeout > ping interval (10 seconds ping)

        if is_secure:
            self.sock = ssl.SSLContext(ssl.PROTOCOL_SSLv23).wrap_socket(self.sock, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=hostname)

        # Handshake
        headers = ["GET %s HTTP/1.1" % resource, "Upgrade: websocket", "Connection: Upgrade"]
        hostport = "%s:%d" % (hostname, port)
        headers.append("Host: %s" % hostport)
        uid = uuid.uuid4()
        EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')
        headers.append("Sec-WebSocket-Key: %s" % EncodingKey)
        headers.append("Sec-WebSocket-Version: 13")
        headers.append("")
        headers.append("")
        header_str = "\r\n".join(headers)
        self.sock.send(header_str.encode('utf-8'))

        # Read Headers
        status = None
        headers = {}

        while True:
            line = []

            while True:
                try:
                    c = self.sock.recv(1).decode()
                except: # timeout
                    return False

                if not c:
                    return False

                line.append(c)

                if c == "\n":
                    break

            line = "".join(line)

            if line == "\r\n":
                break

            line = line.strip()

            if not status:
                status_info = line.split(" ", 2)
                status = int(status_info[1])
            else:
                kv = line.split(":", 1)

                if len(kv) == 2:
                    key, value = kv
                    headers[key.lower()] = value.strip()
                else:
                    LOG.debug("invalid haeader")
                    return False

        if status != 101:
            LOG.debug("Handshake status %d" % status)
            return False

        # Validate Headers
        result = headers.get("sec-websocket-accept", None)

        if not result:
            utils.dialog("notification", heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33235), sound=True)
            return False

        value = "%s258EAFA5-E914-47DA-95CA-C5AB0DC85B11" % EncodingKey
        value = value.encode("utf-8")
        hashed = base64.b64encode(hashlib.sha1(value).digest()).strip().lower().decode('utf-8')

        if hashed == result.lower():
            start_new_thread(self.ping, ())
            self.sendCommands('{"MessageType": "ScheduledTasksInfoStart", "Data": "0,1500"}', 0x1)
            return True

        return False

    def sendCommands(self, payload, opcode):
        if opcode == 0x1:
            payload = payload.encode("utf-8")

        length = len(payload)
        frame_header = struct.pack("B", (1 << 7 | 0 << 6 | 0 << 5 | 0 << 4 | opcode))

        if length < 0x7d:
            frame_header += struct.pack("B", (1 << 7 | length))
        elif length < 1 << 16:  # LENGTH_16
            frame_header += struct.pack("B", (1 << 7 | 0x7e))
            frame_header += struct.pack("!H", length)
        else:
            frame_header += struct.pack("B", (1 << 7 | 0x7f))
            frame_header += struct.pack("!Q", length)

        mask_key = os.urandom(4)
        data = frame_header + mask_key + maskData(mask_key, payload)
        ServerOnline = True

        while data:
            try:
                l = self.sock.send(data)
                data = data[l:]
            except:  # Server offline
                ServerOnline = False
                break

        return ServerOnline

    def ping(self):
        while True:
            # Check Kodi shutdown
            if utils.waitForAbort(10):
                return

            if self.stop or utils.SystemShutdown:
                return

            if not self.sendCommands(b"", 0x9):
                break  # Server offline

        self.reconnecting()

    def recv(self):
        while True:
            # Header
            if self._frame_header is None:
                self._frame_header = self._recv_strict(2)

                if not self._frame_header:  # connection closed
                    return None

            b1 = self._frame_header[0]
            b2 = self._frame_header[1]
            fin = b1 >> 7 & 1
            opcode = b1 & 0xf
            has_mask = b2 >> 7 & 1

            # Frame length
            if self._frame_length is None:
                length_bits = b2 & 0x7f

                if length_bits == 0x7e:
                    length_data = self._recv_strict(2)
                    self._frame_length = struct.unpack("!H", length_data)[0]
                elif length_bits == 0x7f:
                    length_data = self._recv_strict(8)
                    self._frame_length = struct.unpack("!Q", length_data)[0]
                else:
                    self._frame_length = length_bits

            # Mask
            if self._frame_mask is None:
                self._frame_mask = self._recv_strict(4) if has_mask else ""

            # Payload
            if self._frame_length:
                payload = self._recv_strict(self._frame_length)
            else:
                payload = b''

            if has_mask:
                payload = maskData(self._frame_mask, payload)

            # Reset for next frame
            self._frame_header = None
            self._frame_length = None
            self._frame_mask = None

            if opcode in (0x2, 0x1, 0x0):
                if self._cont_data:
                    self._cont_data[1] += payload
                else:
                    self._cont_data = [opcode, payload]

                if fin:
                    data = self._cont_data
                    self._cont_data = None
                    return data
            elif opcode == 0x8:
                self.sendCommands(struct.pack('!H', 1000) + b"", 0x8)
                return False
            elif opcode == 0x9:
                self.sendCommands(payload, 0xa)  # Pong
                return False
            elif opcode == 0xa:
                return False
            else:
                LOG.error("Uncovered opcode: %s" % opcode)
                return False

    def _recv_strict(self, bufsize):
        shortage = bufsize - sum(len(x) for x in self._recv_buffer)

        while shortage > 0:
            try:
                bytesData = self.sock.recv(shortage)
            except Exception as Error:
                LOG.debug("Websocket issue: %s" % Error)
                return None

            self._recv_buffer.append(bytesData)
            shortage -= len(bytesData)

        unified = b"".join(self._recv_buffer)

        if shortage == 0:
            self._recv_buffer = []
            return unified

        self._recv_buffer = [unified[bufsize:]]
        return unified[:bufsize]

    def on_message(self, IncomingData):  # threaded
        IncomingData = IncomingData[1].decode('utf-8')
        LOG.debug("Incoming data: %s" % IncomingData)
        IncomingData = json.loads(IncomingData)

        if IncomingData['MessageType'] == 'GeneralCommand':
            if IncomingData['Data']['Name'] == 'DisplayMessage':
                utils.dialog("notification", heading=IncomingData['Data']['Arguments']['Header'], message=IncomingData['Data']['Arguments']['Text'], icon=utils.icon, time=int(utils.displayMessage) * 1000)
            elif IncomingData['Data']['Name'] in ('Mute', 'Unmute'):
                xbmc.executebuiltin('Mute')
            elif IncomingData['Data']['Name'] == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % IncomingData['Data']['Arguments']['Volume'])
            elif IncomingData['Data']['Name'] == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % IncomingData['Data']['Arguments']['RepeatMode'])
            elif IncomingData['Data']['Name'] == 'SendString':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "VideoLibrary.GetTVShows", "params": {"text": %s, "done": False}}' % IncomingData['Data']['Arguments']['String'])
            elif IncomingData['Data']['Name'] == 'GoHome':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "home"}}')
            elif IncomingData['Data']['Name'] == 'Guide':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "tvguide"}}')
            elif IncomingData['Data']['Name'] == 'MoveUp':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Up"}')
            elif IncomingData['Data']['Name'] == 'MoveDown':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Down"}')
            elif IncomingData['Data']['Name'] == 'MoveRight':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Right"}')
            elif IncomingData['Data']['Name'] == 'MoveLeft':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Left"}')
            elif IncomingData['Data']['Name'] == 'ToggleFullscreen':
                xbmc.executebuiltin('Action(FullScreen)')
            elif IncomingData['Data']['Name'] == 'ToggleOsdMenu':
                xbmc.executebuiltin('Action(OSD)')
            elif IncomingData['Data']['Name'] == 'ToggleContextMenu':
                xbmc.executebuiltin('Action(ContextMenu)')
            elif IncomingData['Data']['Name'] == 'Select':
                xbmc.executebuiltin('Action(Select)')
            elif IncomingData['Data']['Name'] == 'Back':
                xbmc.executebuiltin('Action(back)')
            elif IncomingData['Data']['Name'] == 'NextLetter':
                xbmc.executebuiltin('Action(NextLetter)')
            elif IncomingData['Data']['Name'] == 'PreviousLetter':
                xbmc.executebuiltin('Action(PrevLetter)')
            elif IncomingData['Data']['Name'] == 'GoToSearch':
                xbmc.executebuiltin('VideoLibrary.Search')
            elif IncomingData['Data']['Name'] == 'GoToSettings':
                xbmc.executebuiltin('ActivateWindow(Settings)')
            elif IncomingData['Data']['Name'] == 'PageUp':
                xbmc.executebuiltin('Action(PageUp)')
            elif IncomingData['Data']['Name'] == 'PageDown':
                xbmc.executebuiltin('Action(PageDown)')
            elif IncomingData['Data']['Name'] == 'TakeScreenshot':
                xbmc.executebuiltin('TakeScreenshot')
            elif IncomingData['Data']['Name'] == 'ToggleMute':
                xbmc.executebuiltin('Mute')
            elif IncomingData['Data']['Name'] == 'VolumeUp':
                xbmc.executebuiltin('Action(VolumeUp)')
            elif IncomingData['Data']['Name'] == 'VolumeDown':
                xbmc.executebuiltin('Action(VolumeDown)')
        elif IncomingData['MessageType'] == 'ScheduledTasksInfo':
            for Task in IncomingData['Data']:
                if Task["State"] == "Running":
                    if not Task["Name"] in self.TasksRunning:
                        self.TasksRunning.append(Task["Name"])

                        if not self.SyncInProgress:
                            self.SyncInProgress = True
                            start_new_thread(self.EmbyServerSyncCheck, ())

                    if 'CurrentProgressPercentage' in Task:
                        Progress = int(float(Task['CurrentProgressPercentage']))
                    else:
                        Progress = 0

                    utils.progress_update(Progress, "Emby", "Server is busy: %s" % Task["Name"])
                else:
                    if Task["Name"] in self.TasksRunning:
                        self.TasksRunning = ([s for s in self.TasksRunning if s != Task["Name"]])
        elif IncomingData['MessageType'] == 'RefreshProgress':
            self.SyncRefresh = True

            if not self.SyncInProgress:
                self.SyncInProgress = True
                start_new_thread(self.EmbyServerSyncCheck, ())

            utils.progress_update(int(float(IncomingData['Data']['Progress'])), "Emby", "Server is busy: Sync in progress")
        elif IncomingData['MessageType'] == 'UserDataChanged':
            self.EmbyServer.UserDataChanged(self.EmbyServer.server_id, IncomingData['Data']['UserDataList'], IncomingData['Data']['UserId'])
        elif IncomingData['MessageType'] == 'LibraryChanged':
            LOG.info("[ LibraryChanged ] %s" % IncomingData['Data'])
            self.EmbyServer.library.removed(IncomingData['Data']['ItemsRemoved'])
            UpdateItems = (len(IncomingData['Data']['ItemsUpdated']) + len(IncomingData['Data']['ItemsAdded'])) * [(None, None, None, None)] # preallocate memory

            for Index, ItemMod in enumerate(IncomingData['Data']['ItemsUpdated'] + IncomingData['Data']['ItemsAdded']):
                UpdateItems[Index] = (ItemMod, None, None, None)

            UpdateItems = list(dict.fromkeys(UpdateItems)) # filter doplicates
            self.EmbyServer.library.updated(UpdateItems)

            if self.SyncInProgress:
                LOG.info("Emby server sync in progress, delay updates")
            else:
                self.EmbyServer.library.RunJobs()
        elif IncomingData['MessageType'] == 'ServerRestarting':
            LOG.info("[ ServerRestarting ]")
            self.EmbyServer.Online = False

            if utils.restartMsg:
                utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33006), icon=utils.icon)

            if utils.waitForAbort(5):
                return

            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncomingData['MessageType'] == 'ServerShuttingDown':
            LOG.info("[ ServerShuttingDown ]")
            self.EmbyServer.Online = False
            utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33236))

            if utils.waitForAbort(5):
                return

            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncomingData['MessageType'] == 'RestartRequired':
            utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33237))
        elif IncomingData['MessageType'] == 'Play':
            playerops.Play(IncomingData['Data']['ItemIds'], IncomingData['Data']['PlayCommand'], int(IncomingData['Data'].get('StartIndex', -1)), int(IncomingData['Data'].get('StartPositionTicks', -1)), self.EmbyServer)
        elif IncomingData['MessageType'] == 'Playstate':
            Playstate(IncomingData['Data']['Command'], int(IncomingData['Data'].get('SeekPositionTicks', -1)))

    def EmbyServerSyncCheck(self):
        LOG.info("--> Emby server is busy, sync in progress")
        utils.SyncPause[self.EmbyServer.server_id] = True
        utils.progress_open("Emby Server busy")

        while self.SyncRefresh or self.TasksRunning:
            self.SyncRefresh = False

            if utils.waitForAbort(1): # every second a progress update is expected. If not, sync was canceled
                break

        utils.progress_close()
        self.SyncInProgress = False
        utils.SyncPause[self.EmbyServer.server_id] = False
        self.EmbyServer.library.RunJobs()
        LOG.info("--< Emby server is busy, sync in progress")

# Emby playstate updates (websocket Incoming)
def Playstate(Command, SeekPositionTicks):
    if Command == 'Seek':
        if XbmcPlayer.isPlaying():
            seektime = SeekPositionTicks / 10000000.0
            XbmcPlayer.seekTime(seektime)
            LOG.info("[ seek/%s ]" % seektime)
    elif Command in actions:
        actions[Command]()
        LOG.info("[ command/%s ]" % Command)

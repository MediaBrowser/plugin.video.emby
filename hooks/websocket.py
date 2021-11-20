# -*- coding: utf-8 -*-
import json
import threading
import os
import array
import struct
import uuid
import base64
import socket
import ssl
import xbmc
import helper.loghandler
import helper.utils as Utils
import helper.playerops as PlayerOps

if Utils.Python3:
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

LOG = helper.loghandler.LOG('Emby.hooks.websocket')


def maskData(mask_key, data):
    _m = array.array("B", mask_key)
    _d = array.array("B", data)

    for i in range(len(_d)):
        _d[i] ^= _m[i % 4]  # ixor

    if Utils.Python3:
        return _d.tobytes()

    return _d.tostring()

class WSClient(threading.Thread):
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.stop = False
        LOG.debug("WSClient initializing...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._recv_buffer = []
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        self._cont_data = None
        threading.Thread.__init__(self)

    def run(self):
        LOG.info("--->[ websocket ]")
        server = self.EmbyServer.server.replace('https', "wss") if self.EmbyServer.server.startswith('https') else self.EmbyServer.server.replace('http', "ws")

        if self.connect("%s/embywebsocket?api_key=%s&device_id=%s" % (server, self.EmbyServer.Token, Utils.device_id)):
            threading.Thread(target=self.ping).start()

            while not self.stop:
                data = self.recv()

                if data is None or self.stop:
                    break

                if data:
                    threading.Thread(target=self.on_message, args=(data,)).start()
        else:
            LOG.info("[ websocket failed ]")

        LOG.info("---<[ websocket ]")

    def send(self, message, data):
        self.sendCommands(json.dumps({'MessageType': message, "Data": data}), 0x1)

    def close(self):
        self.stop = True

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass

        self.sock.close()

    def connect(self, url):
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
        self.sock.connect((hostname, port))
        self.sock.settimeout(None)

        if is_secure:
            self.sock = ssl.SSLContext(ssl.PROTOCOL_SSLv23).wrap_socket(self.sock, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=hostname)

        # Handshake
        headers = ["GET %s HTTP/1.1" % resource, "Upgrade: websocket", "Connection: Upgrade"]
        hostport = "%s:%d" % (hostname, port)
        headers.append("Host: %s" % hostport)
        uid = uuid.uuid4()
        key = base64.b64encode(uid.bytes).strip().decode('utf-8')
        headers.append("Sec-WebSocket-Key: %s" % key)
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
                c = self.sock.recv(1).decode()
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

        # Validate Headers
        result = headers.get("sec-websocket-accept", None)

        if not result:
            Utils.dialog("notification", heading=Utils.addon_name, icon="DefaultIconError.png", message=Utils.Translate(33235), sound=True)
            return False

        return True

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

        while data:
            try:
                l = self.sock.send(data)
                data = data[l:]
            except:  # Offline
                break

    def ping(self):
        while True:
            for _ in range(10):
                xbmc.sleep(1000)

                if self.stop or Utils.SystemShutdown:
                    return

            self.sendCommands(b"", 0x9)

    def recv(self):
        while True:
            # Header
            if self._frame_header is None:
                self._frame_header = self._recv_strict(2)

                if not self._frame_header:  # connection closed
                    return None

            if Utils.Python3:
                b1 = self._frame_header[0]
                b2 = self._frame_header[1]
            else:
                b1 = ord(self._frame_header[0])
                b2 = ord(self._frame_header[1])

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
                return None
            elif opcode == 0x9:
                self.sendCommands(payload, 0xa)  # Pong
                return False
            elif opcode == 0xa:
                return False

    def _recv_strict(self, bufsize):
        shortage = bufsize - sum(len(x) for x in self._recv_buffer)

        while shortage > 0:
            try:
                bytesData = self.sock.recv(shortage)
            except:
                return None

            self._recv_buffer.append(bytesData)
            shortage -= len(bytesData)

        unified = b"".join(self._recv_buffer)

        if shortage == 0:
            self._recv_buffer = []
            return unified

        self._recv_buffer = [unified[bufsize:]]
        return unified[:bufsize]

    def on_message(self, IncommingData):  # threaded
        IncommingData = IncommingData[1].decode('utf-8')
        IncommingData = json.loads(IncommingData)

        if IncommingData['MessageType'] == 'GeneralCommand':
            if IncommingData['Data']['Name'] == 'DisplayMessage':
                Utils.dialog("notification", heading=IncommingData['Data']['Arguments']['Header'], message=IncommingData['Data']['Arguments']['Text'], icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=int(Utils.displayMessage) * 1000)
            elif IncommingData['Data']['Name'] in ('Mute', 'Unmute'):
                xbmc.executebuiltin('Mute')
            elif IncommingData['Data']['Name'] == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % IncommingData['Data']['Arguments']['Volume'])
            elif IncommingData['Data']['Name'] == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % IncommingData['Data']['Arguments']['RepeatMode'])
            elif IncommingData['Data']['Name'] == 'SendString':
                params = {'text': IncommingData['Data']['Arguments']['String'], 'done': False}
                xbmc.executeJSONRPC(json.dumps({'jsonrpc': "2.0", 'id': 1, 'method': 'VideoLibrary.GetTVShows', 'params': params}))
            elif IncommingData['Data']['Name'] == 'GoHome':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "home"}}')
            elif IncommingData['Data']['Name'] == 'Guide':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "tvguide"}}')
            elif IncommingData['Data']['Name'] == 'MoveUp':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Up"}')
            elif IncommingData['Data']['Name'] == 'MoveDown':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Down"}')
            elif IncommingData['Data']['Name'] == 'MoveRight':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Right"}')
            elif IncommingData['Data']['Name'] == 'MoveLeft':
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Input.Left"}')
            elif IncommingData['Data']['Name'] == 'ToggleFullscreen':
                xbmc.executebuiltin('Action(FullScreen)')
            elif IncommingData['Data']['Name'] == 'ToggleOsdMenu':
                xbmc.executebuiltin('Action(OSD)')
            elif IncommingData['Data']['Name'] == 'ToggleContextMenu':
                xbmc.executebuiltin('Action(ContextMenu)')
            elif IncommingData['Data']['Name'] == 'Select':
                xbmc.executebuiltin('Action(Select)')
            elif IncommingData['Data']['Name'] == 'Back':
                xbmc.executebuiltin('Action(back)')
            elif IncommingData['Data']['Name'] == 'NextLetter':
                xbmc.executebuiltin('Action(NextLetter)')
            elif IncommingData['Data']['Name'] == 'PreviousLetter':
                xbmc.executebuiltin('Action(PrevLetter)')
            elif IncommingData['Data']['Name'] == 'GoToSearch':
                xbmc.executebuiltin('VideoLibrary.Search')
            elif IncommingData['Data']['Name'] == 'GoToSettings':
                xbmc.executebuiltin('ActivateWindow(Settings)')
            elif IncommingData['Data']['Name'] == 'PageUp':
                xbmc.executebuiltin('Action(PageUp)')
            elif IncommingData['Data']['Name'] == 'PageDown':
                xbmc.executebuiltin('Action(PageDown)')
            elif IncommingData['Data']['Name'] == 'TakeScreenshot':
                xbmc.executebuiltin('TakeScreenshot')
            elif IncommingData['Data']['Name'] == 'ToggleMute':
                xbmc.executebuiltin('Mute')
            elif IncommingData['Data']['Name'] == 'VolumeUp':
                xbmc.executebuiltin('Action(VolumeUp)')
            elif IncommingData['Data']['Name'] == 'VolumeDown':
                xbmc.executebuiltin('Action(VolumeDown)')
        elif IncommingData['MessageType'] == 'UserDataChanged':
            self.EmbyServer.UserDataChanged(self.EmbyServer.server_id, IncommingData['Data']['UserDataList'], IncommingData['Data']['UserId'])
        elif IncommingData['MessageType'] == 'LibraryChanged':
            LOG.info("[ LibraryChanged ] %s" % IncommingData['Data'])
            self.EmbyServer.library.removed(IncommingData['Data']['ItemsRemoved'])
            UpdateItems = IncommingData['Data']['ItemsUpdated']

            for ItemAdded in IncommingData['Data']['ItemsAdded']:
                if ItemAdded not in UpdateItems:
                    UpdateItems.append(ItemAdded)

            LOG.debug("[ LibraryChanged UpdateItems ] %s" % UpdateItems)
            self.EmbyServer.library.updated(UpdateItems)
        elif IncommingData['MessageType'] == 'ServerRestarting':
            if Utils.restartMsg:
                Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33006), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png")

            self.EmbyServer.Online = False
            xbmc.sleep(5000)
            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncommingData['MessageType'] == 'ServerShuttingDown':
            Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33236))
            self.EmbyServer.Online = False
            xbmc.sleep(5000)
            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncommingData['MessageType'] == 'RestartRequired':
            Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33237))
        elif IncommingData['MessageType'] == 'Play':
            PlayerOps.Play(IncommingData['Data']['ItemIds'], IncommingData['Data']['PlayCommand'], int(IncommingData['Data'].get('StartIndex', -1)), int(IncommingData['Data'].get('StartPositionTicks', -1)), self.EmbyServer)
        elif IncommingData['MessageType'] == 'Playstate':
            Playstate(IncommingData['Data']['Command'], int(IncommingData['Data'].get('SeekPositionTicks', -1)))

# Emby playstate updates (websocket incomming)
def Playstate(Command, SeekPositionTicks):
    actions = {
        'Stop': xbmc.Player().stop,
        'Unpause': xbmc.Player().pause,
        'Pause': xbmc.Player().pause,
        'PlayPause': xbmc.Player().pause,
        'NextTrack': xbmc.Player().playnext,
        'PreviousTrack': xbmc.Player().playprevious
    }

    if Command == 'Seek':
        if xbmc.Player().isPlaying():
            seektime = SeekPositionTicks / 10000000.0
            xbmc.Player().seekTime(seektime)
            LOG.info("[ seek/%s ]" % seektime)
    elif Command in actions:
        actions[Command]()
        LOG.info("[ command/%s ]" % Command)

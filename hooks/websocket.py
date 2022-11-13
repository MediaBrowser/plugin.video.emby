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
from database import dbio

LOG = loghandler.LOG('Emby.hooks.websocket')

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
        self.EmbyServerSocketUrl = ""
        self.ConnectionInProgress = False
        self.TasksRunning = []
        self.SyncInProgress = False
        self.SyncRefresh = False

    def start(self):
        start_new_thread(self.Listen, ())

    def close(self, Terminate=True):
        LOG.info("Close wesocket connection %s / %s" % (self.EmbyServer.ServerData['ServerId'], self.EmbyServer.ServerData['ServerName']))

        if Terminate:
            self.stop = True

        if self.sock:
            self.sendCommands(struct.pack('!H', 1000), 0x8)

            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception as error:
                LOG.error(error)

            self.sock.close()
            self.sock = None

    def Listen(self):
        LOG.info("--->[ websocket ]")

        if self.EmbyServer.ServerData['ServerUrl'].startswith('https'):
            self.EmbyServerSocketUrl = self.EmbyServer.ServerData['ServerUrl'].replace('https', "wss")
        else:
            self.EmbyServerSocketUrl = self.EmbyServer.ServerData['ServerUrl'].replace('http', "ws")

        self.connect()

        while not self.stop:
            data = self.recv()

            if self.stop:
                break

            if data:
                self.on_message(data)

            if data is None:  # connect
                self.connect()

        LOG.info("---<[ websocket ]")

    def connect(self):
        if not self.ConnectionInProgress:
            self.ConnectionInProgress = True

            while not self.stop:
                LOG.info("--->[ websocket connect ]")

                if self.establish_connection():
                    LOG.info("---<[ websocket connect ]")
                    break

                utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33430), time=1000, sound=False)
                LOG.info("[ websocket connect failed ]")

                if utils.sleep(5):
                    break

            self.ConnectionInProgress = False
        else:
            LOG.info("[ websocket connect in progress ]")

    def establish_connection(self):
        self.close(False)

        url = "%s/embywebsocket?api_key=%s&device_id=%s" % (self.EmbyServerSocketUrl, self.EmbyServer.ServerData['AccessToken'], utils.device_id)
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
            self.sock.settimeout(25) # set timeout > ping interval (10 seconds ping (2 pings))

            if is_secure:
                self.sock = ssl.SSLContext(ssl.PROTOCOL_SSLv23).wrap_socket(self.sock, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=hostname)

            # Handshake
            uid = uuid.uuid4()
            EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')
            header_str = "GET %s HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nHost: %s:%d\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n" % (resource, hostname, port, EncodingKey)
            self.sock.send(header_str.encode('utf-8'))
        except Exception as error:
            LOG.error(error)
            return False

        # Read Headers
        status = None
        headers = {}

        while True:
            line = []

            while True:
                try:
                    c = self.sock.recv(1).decode()
                except Exception as error:
                    LOG.error(error)
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
            utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33235), sound=True)
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

        if self.sock:
            while data:
                try:
                    l = self.sock.send(data)
                    data = data[l:]
                except Exception as error:
                    LOG.error(error)
                    ServerOnline = False
                    break
        else:
            ServerOnline = False

        return ServerOnline

    def ping(self):
        while True:
            # Check Kodi shutdown
            if utils.sleep(10) or self.stop:
                return

            if not self.sendCommands(b"", 0x9):
                break  # Server offline

        self.connect()

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
            Debug_frame_header = self._frame_header
            Debug_frame_length = self._frame_length
            Debug_frame_mask = self._frame_mask
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
                self.sendCommands(struct.pack('!H', 1000), 0x8)
                return False
            elif opcode == 0x9:
                self.sendCommands(payload, 0xa)  # Pong
                return False
            elif opcode == 0xa:
                return False
            else:
                LOG.error("Uncovered opcode: %s / %s / %s / %s / %s" % (opcode, payload, Debug_frame_header, Debug_frame_length, Debug_frame_mask))
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
        try:
            IncomingData = IncomingData[1].decode('utf-8')
            LOG.debug("Incoming data: %s" % IncomingData)
            IncomingData = json.loads(IncomingData)
        except: # connection interrupted and data corrupted
            LOG.error("Incoming data: %s" % IncomingData)
            return

        if IncomingData['MessageType'] == 'GeneralCommand':
            if IncomingData['Data']['Name'] == 'DisplayMessage':
                utils.Dialog.notification(heading=IncomingData['Data']['Arguments']['Header'], message=IncomingData['Data']['Arguments']['Text'], icon=utils.icon, time=int(utils.displayMessage) * 1000)
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

                    if utils.busyMsg:
                        utils.progress_update(Progress, utils.Translate(33199), "%s: %s" % (utils.Translate(33411), Task["Name"]))
                else:
                    if Task["Name"] in self.TasksRunning:
                        self.TasksRunning = ([s for s in self.TasksRunning if s != Task["Name"]])
        elif IncomingData['MessageType'] == 'RefreshProgress':
            self.SyncRefresh = True

            if not self.SyncInProgress:
                self.SyncInProgress = True
                start_new_thread(self.EmbyServerSyncCheck, ())

            if utils.busyMsg:
                utils.progress_update(int(float(IncomingData['Data']['Progress'])), utils.Translate(33199), utils.Translate(33414))
        elif IncomingData['MessageType'] == 'UserDataChanged':
            if IncomingData['Data']['UserId'] != self.EmbyServer.ServerData['UserId']:
                return

            LOG.info("[ UserDataChanged ] %s" % IncomingData['Data']['UserDataList'])
            UpdateData = []
            embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")

            for ItemData in IncomingData['Data']['UserDataList']:
                ItemData['ItemId'] = int(ItemData['ItemId'])

                if ItemData['ItemId'] not in utils.ItemSkipUpdate:  # Check EmbyID
                    e_item = embydb.get_item_by_id(ItemData['ItemId'])

                    if e_item:
                        if e_item[5] == "Season":
                            LOG.info("[ UserDataChanged skip %s/%s ]" % (e_item[5], ItemData['ItemId']))
                        else:
                            UpdateData.append(ItemData)
                    else:
                        LOG.info("[ UserDataChanged item not found %s ]" % ItemData['ItemId'])
                else:
                    LOG.info("UserDataChanged ItemSkipUpdate: %s" % str(utils.ItemSkipUpdate))
                    LOG.info("[ UserDataChanged skip update/%s ]" % ItemData['ItemId'])
                    utils.ItemSkipUpdate.remove(ItemData['ItemId'])
                    LOG.info("UserDataChanged ItemSkipUpdate: %s" % str(utils.ItemSkipUpdate))

            dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")

            if UpdateData:
                self.EmbyServer.library.userdata(UpdateData)
        elif IncomingData['MessageType'] == 'LibraryChanged':
            LOG.info("[ LibraryChanged ] %s" % IncomingData['Data'])
            self.EmbyServer.library.removed(IncomingData['Data']['ItemsRemoved'])
            UpdateItemIds = (len(IncomingData['Data']['ItemsUpdated']) + len(IncomingData['Data']['ItemsAdded'])) * [None] # preallocate memory

            for Index, ItemMod in enumerate(IncomingData['Data']['ItemsUpdated'] + IncomingData['Data']['ItemsAdded']):
                UpdateItemIds[Index] = ItemMod

            UpdateItemIds = list(dict.fromkeys(UpdateItemIds)) # filter doplicates
            self.EmbyServer.library.updated(UpdateItemIds)

            if self.SyncInProgress:
                LOG.info("Emby server sync in progress, delay updates")
            else:
                self.EmbyServer.library.RunJobs()
        elif IncomingData['MessageType'] == 'ServerRestarting':
            LOG.info("[ ServerRestarting ]")

            if utils.restartMsg:
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33006), icon=utils.icon)

            if utils.sleep(5):
                return

            self.EmbyServer.ServerReconnect()
        elif IncomingData['MessageType'] == 'ServerShuttingDown':
            LOG.info("[ ServerShuttingDown ]")
            utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33236))

            if utils.sleep(5):
                return

            self.EmbyServer.ServerReconnect()
        elif IncomingData['MessageType'] == 'RestartRequired':
            utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33237))
        elif IncomingData['MessageType'] == 'Play':
            playerops.Play(IncomingData['Data']['ItemIds'], IncomingData['Data']['PlayCommand'], int(IncomingData['Data'].get('StartIndex', -1)), int(IncomingData['Data'].get('StartPositionTicks', -1)), self.EmbyServer)
        elif IncomingData['MessageType'] == 'Playstate':
            Playstate(IncomingData['Data']['Command'], int(IncomingData['Data'].get('SeekPositionTicks', -1)))

    def EmbyServerSyncCheck(self):
        LOG.info("--> Emby server is busy, sync in progress")
        utils.SyncPause[self.EmbyServer.ServerData['ServerId']] = True

        if utils.busyMsg:
            utils.progress_open(utils.Translate(33411))

        while self.SyncRefresh or self.TasksRunning:
            self.SyncRefresh = False

            if utils.sleep(5): # every 5 seconds a progress update is expected. If not, sync was canceled
                break

        if utils.busyMsg:
            utils.progress_close()

        self.SyncInProgress = False
        utils.SyncPause[self.EmbyServer.ServerData['ServerId']] = False
        self.EmbyServer.library.RunJobs()
        LOG.info("--< Emby server is busy, sync in progress")

# Emby playstate updates (websocket Incoming)
def Playstate(Command, SeekPositionTicks):
    if utils.XbmcPlayer:
        if Command == 'Seek':
            if utils.XbmcPlayer.isPlaying():
                seektime = SeekPositionTicks / 10000000.0
                utils.XbmcPlayer.seekTime(seektime)
                LOG.info("[ seek/%s ]" % seektime)
        elif Command == "Stop":
            utils.XbmcPlayer.stop()
        elif Command == "Unpause":
            utils.XbmcPlayer.pause()
        elif Command == "Pause":
            utils.XbmcPlayer.pause()
        elif Command == "PlayPause":
            utils.XbmcPlayer.pause()
        elif Command == "NextTrack":
            utils.XbmcPlayer.playnext()
        elif Command == "PreviousTrack":
            utils.XbmcPlayer.playprevious()

    LOG.info("[ command/%s ]" % Command)

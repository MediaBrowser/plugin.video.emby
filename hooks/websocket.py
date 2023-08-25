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
import queue
import xbmc
from helper import utils, playerops, pluginmenu
from database import dbio


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
        self.sock = None
        self._recv_buffer = ()
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        self._cont_data = None
        self.EmbyServerSocketUrl = ""
        self.ConnectionInProgress = False
        self.TasksRunning = ()
        self.SyncInProgress = False
        self.SyncRefresh = False
        self.AsyncMessageQueue = queue.Queue()
        xbmc.log("Emby.hooks.websocket: WSClient initializing...", 0) # LOGDEBUG

    def start(self):
        start_new_thread(self.Listen, ())
        start_new_thread(self.on_message, ())

    def close(self, Terminate=True):
        xbmc.log(f"Emby.hooks.websocket: Close wesocket connection {self.EmbyServer.ServerData['ServerId']} / {self.EmbyServer.ServerData['ServerName']}", 1) # LOGINFO

        if Terminate:
            self.stop = True
            self.AsyncMessageQueue.put("QUIT")

        if self.sock:
            self.sock.settimeout(1)
            self.sendCommands(struct.pack('!H', 1000), 0x8)

            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception as error:
                xbmc.log(f"Emby.hooks.websocket: {error}", 3) # LOGERROR

            self.sock.close()
            self.sock = None
            self._recv_buffer = ()
            self._frame_header = None
            self._frame_length = None
            self._frame_mask = None
            self._cont_data = None
            self.TasksRunning = ()

    def Listen(self):
        xbmc.log("Emby.hooks.websocket: THREAD: --->[ websocket ]", 1) # LOGINFO

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
                self.AsyncMessageQueue.put(data)

            if data is None:  # re-connect
                self.connect()

        xbmc.log("Emby.hooks.websocket: THREAD: ---<[ websocket ]", 1) # LOGINFO

    def connect(self):
        if not self.ConnectionInProgress:
            self.ConnectionInProgress = True

            while not self.stop:
                xbmc.log("Emby.hooks.websocket: --->[ websocket connect ]", 1) # LOGINFO

                if self.establish_connection():
                    xbmc.log("Emby.hooks.websocket: ---<[ websocket connect ]", 1) # LOGINFO
                    break

                utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33430), time=1000, sound=False)
                xbmc.log("Emby.hooks.websocket: [ websocket connect failed ]", 1) # LOGINFO

                if utils.sleep(5):
                    break

            self.ConnectionInProgress = False
        else:
            xbmc.log("Emby.hooks.websocket: [ websocket connect in progress ]", 1) # LOGINFO
            utils.sleep(1)

    def establish_connection(self):
        self.close(False)
        url = f"{self.EmbyServerSocketUrl}/embywebsocket?api_key={self.EmbyServer.ServerData['AccessToken']}&device_id={utils.device_id}"

        # Parse URL
        scheme, url = url.split(":", 1)
        parsed = urlparse(url, scheme="http")
        resource = parsed.path

        if parsed.query:
            resource += f"?{parsed.query}"

        hostname = parsed.hostname
        port = parsed.port
        is_secure = scheme == "wss"

        if not port:
            if scheme == "http":
                port = 80
            else:
                port = 443

        address_family = socket.getaddrinfo(hostname, None)[0][0]
        self.sock = socket.socket(address_family, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Connect
        try:
            self.sock.connect((hostname, port))
            self.sock.settimeout(60) # set timeout > ping interval (10 seconds ping (6 pings -> timeout))

            if is_secure:
                self.sock = ssl.SSLContext(ssl.PROTOCOL_SSLv23).wrap_socket(self.sock, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=hostname)

            # Handshake
            uid = uuid.uuid4()
            EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')
            header_str = f"GET {resource} HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nHost: {hostname}:{port}\r\nSec-WebSocket-Key: {EncodingKey}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            self.sock.send(header_str.encode('utf-8'))
        except Exception as error:
            xbmc.log(f"Emby.hooks.websocket: {error}", 3) # LOGERROR
            return False

        # Read Headers
        status = None
        headers = {}

        while True:
            line = ()

            while True:
                try:
                    c = self.sock.recv(1).decode()
                except Exception as error:
                    xbmc.log(f"Emby.hooks.websocket: {error}", 3) # LOGERROR
                    return False

                if not c:
                    return False

                line += (c,)

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
                    xbmc.log("Emby.hooks.websocket: invalid haeader", 0) # LOGDEBUG
                    return False

        if status != 101:
            xbmc.log(f"Emby.hooks.websocket: Handshake status {status}", 0) # LOGDEBUG
            return False

        # Validate Headers
        result = headers.get("sec-websocket-accept", None)

        if not result:
            utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33235), sound=True)
            return False

        value = f"{EncodingKey}258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
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
                    xbmc.log(f"Emby.hooks.websocket: {error}", 3) # LOGERROR
                    ServerOnline = False
                    break
        else:
            ServerOnline = False

        return ServerOnline

    def ping(self):
        xbmc.log("Emby.hooks.websocket: THREAD: --->[ ping ]", 1) # LOGINFO

        while True:
            # Check Kodi shutdown
            if utils.sleep(10) or self.stop:
                xbmc.log("Emby.hooks.websocket: THREAD: ---<[ ping ] shutdown", 1) # LOGINFO
                return

            if not self.sendCommands(b"", 0x9):
                break  # Server offline

        self.connect()
        xbmc.log("Emby.hooks.websocket: THREAD: ---<[ ping ]", 1) # LOGINFO

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
                xbmc.log(f"Emby.hooks.websocket: Uncovered opcode: {opcode} / {payload} / {Debug_frame_header} / {Debug_frame_length} / {Debug_frame_mask}", 3) # LOGERROR
                return False

    def _recv_strict(self, bufsize):
        shortage = bufsize - sum(len(x) for x in self._recv_buffer)

        while shortage > 0:
            try:
                bytesData = self.sock.recv(shortage)
            except Exception as Error:
                xbmc.log(f"Emby.hooks.websocket: Websocket issue: {Error}", 0) # LOGDEBUG
                return None

            self._recv_buffer += (bytesData,)
            shortage -= len(bytesData)

        unified = b"".join(self._recv_buffer)

        if shortage == 0:
            self._recv_buffer = ()
            return unified

        self._recv_buffer = unified[bufsize:]
        return unified[:bufsize]

    def on_message(self):  # threaded
        while True:
            IncomingData = self.AsyncMessageQueue.get()

            if IncomingData == "QUIT":
                xbmc.log("EMBY.hooks.websocket: Queue closed", 1) # LOGINFO
                break

            try:
                IncomingData = IncomingData[1].decode('utf-8')
                xbmc.log(f"Emby.hooks.websocket: Incoming data: {IncomingData}", 0) # LOGDEBUG
                IncomingData = json.loads(IncomingData)
            except: # connection interrupted and data corrupted
                xbmc.log(f"Emby.hooks.websocket: Incoming data: {IncomingData}", 3) # LOGERROR
                continue

            if IncomingData['MessageType'] == 'GeneralCommand':
                if 'Text' in IncomingData['Data']['Arguments']:
                    Text = IncomingData['Data']['Arguments']['Text']
                else:
                    Text = ""

                if IncomingData['Data']['Name'] == 'DisplayMessage':
                    if IncomingData['Data']['Arguments']['Header'] == "remotecommand":
                        xbmc.log(f"Emby.hooks.websocket: Incoming remote command: {Text}", 1) # LOGINFO
                        Command = Text.split("|")
                        Event = Command[0].lower()

                        if Event == "clients":
                            playerops.update_Remoteclients(self.EmbyServer.ServerData['ServerId'], Command)
                        elif Event == "connect":
                            start_new_thread(self.confirm_remote, (Command[1], Command[2]))
                        elif Event == "support":
                            playerops.add_RemoteClientExtendedSupport(self.EmbyServer.ServerData['ServerId'], Command[1])
                        elif Event == "ack":
                            playerops.add_RemoteClientExtendedSupportAck(self.EmbyServer.ServerData['ServerId'], Command[1], Command[2], Command[3])
                        elif Event == "playsingle":
                            playerops.PlayEmby([Command[1]], "PlaySingle", 0, Command[2], self.EmbyServer, Command[3])
                        elif Event == "playinit":
                            playerops.PlayEmby([Command[1]], "PlayInit", 0, Command[2], self.EmbyServer, Command[3])
                        elif Event == "pause":
                            playerops.Pause(True, Command[1], Command[2])
                        elif Event == "seek":
                            playerops.Seek(Command[1], True, Command[2])

                        continue
                    utils.Dialog.notification(heading=IncomingData['Data']['Arguments']['Header'], message=Text, icon=utils.icon, time=int(utils.displayMessage) * 1000)
                elif IncomingData['Data']['Name'] == 'SetCurrentPlaylistItem':
                    playerops.PlayPlaylistItem(playerops.PlayerId, IncomingData['Data']['Arguments']['PlaylistItemId'])
                elif IncomingData['Data']['Name'] == 'RemoveFromPlaylist':
                    playerops.RemovePlaylistItem(playerops.PlayerId, IncomingData['Data']['Arguments']['PlaylistItemIds'])
                elif IncomingData['Data']['Name'] in ('Mute', 'Unmute'):
                    xbmc.executebuiltin('Mute')
                elif IncomingData['Data']['Name'] == 'SetVolume':
                    xbmc.executebuiltin(f"SetVolume({IncomingData['Data']['Arguments']['Volume']}[,showvolumebar])")
                elif IncomingData['Data']['Name'] == 'SetRepeatMode':
                    xbmc.executebuiltin("xbmc.PlayerControl({IncomingData['Data']['Arguments']['RepeatMode']})")
                elif IncomingData['Data']['Name'] == 'GoHome':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "home"}}')
                elif IncomingData['Data']['Name'] == 'Guide':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "tvguide"}}')
                elif IncomingData['Data']['Name'] == 'MoveUp':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Up"}')
                elif IncomingData['Data']['Name'] == 'MoveDown':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Down"}')
                elif IncomingData['Data']['Name'] == 'MoveRight':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Right"}')
                elif IncomingData['Data']['Name'] == 'MoveLeft':
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "Input.Left"}')
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
                    utils.SendJson('{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {"window": "settings"}}')
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
                            self.TasksRunning += (Task["Name"],)

                            if not self.SyncInProgress:
                                self.SyncInProgress = True
                                start_new_thread(self.EmbyServerSyncCheck, ())

                        if 'CurrentProgressPercentage' in Task:
                            Progress = int(float(Task['CurrentProgressPercentage']))
                        else:
                            Progress = 0

                        if utils.busyMsg:
                            utils.progress_update(Progress, utils.Translate(33199), f"{utils.Translate(33411)}: {Task['Name']}")
                    else:
                        if Task["Name"] in self.TasksRunning:
                            ItemIndex = self.TasksRunning.index(Task["Name"])
                            self.TasksRunning = self.TasksRunning[:ItemIndex] + self.TasksRunning[ItemIndex+ 1 :]
            elif IncomingData['MessageType'] == 'RefreshProgress':
                self.SyncRefresh = True

                if not self.SyncInProgress:
                    self.SyncInProgress = True
                    start_new_thread(self.EmbyServerSyncCheck, ())

                if utils.busyMsg:
                    utils.progress_update(int(float(IncomingData['Data']['Progress'])), utils.Translate(33199), utils.Translate(33414))
            elif IncomingData['MessageType'] == 'UserDataChanged':
                xbmc.log(f"Emby.hooks.websocket: [ UserDataChanged ] {IncomingData['Data']['UserDataList']}", 1) # LOGINFO

                if IncomingData['Data']['UserId'] != self.EmbyServer.ServerData['UserId']:
                    xbmc.log(f"Emby.hooks.websocket: UserDataChanged skip by wrong UserId: {IncomingData['Data']['UserId']}", 1) # LOGINFO
                    continue

                if playerops.RemoteMode:
                    xbmc.log("Emby.hooks.websocket: UserDataChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                UpdateData = ()
                DynamicNodesRefresh = False
                embydb = dbio.DBOpenRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")

                for ItemData in IncomingData['Data']['UserDataList']:
                    ItemData['ItemId'] = int(ItemData['ItemId'])

                    if ItemData['ItemId'] not in playerops.ItemSkipUpdate:  # Check EmbyID
                        e_item = embydb.get_item_by_id(ItemData['ItemId'])

                        if e_item:
                            if e_item[5] == "Season":
                                xbmc.log(f"Emby.hooks.websocket: [ UserDataChanged skip {e_item[5]} / {ItemData['ItemId']} ]", 1) # LOGINFO
                            else:
                                UpdateData += (ItemData,)
                        else:
                            xbmc.log(f"Emby.hooks.websocket: [ UserDataChanged item not found {ItemData['ItemId']} ]", 1) # LOGINFO
                            DynamicNodesRefresh = True
                    else:
                        xbmc.log(f"Emby.hooks.websocket: UserDataChanged skip by ItemSkipUpdate / Id: {ItemData['ItemId']} / ItemSkipUpdate: {playerops.ItemSkipUpdate}", 1) # LOGINFO
                        playerops.ItemSkipUpdate.remove(ItemData['ItemId'])

                dbio.DBCloseRO(self.EmbyServer.ServerData['ServerId'], "UserDataChanged")

                if DynamicNodesRefresh:
                    pluginmenu.reset_querycache()
                    MenuPath =  xbmc.getInfoLabel('Container.FolderPath')

                    if MenuPath.startswith(f"plugin://{utils.PluginId}/") and "mode=browse" in MenuPath.lower():
                        xbmc.log("Emby.hooks.websocket: [ UserDataChanged refresh dynamic nodes ]", 1) # LOGINFO
                        xbmc.executebuiltin('Container.Refresh')
                    else:
                        utils.refresh_widgets()

                if UpdateData:
                    self.EmbyServer.library.userdata(UpdateData)
            elif IncomingData['MessageType'] == 'LibraryChanged':
                xbmc.log(f"Emby.hooks.websocket: [ LibraryChanged ] {IncomingData['Data']}", 1) # LOGINFO

                if playerops.RemoteMode:
                    xbmc.log("Emby.hooks.websocket: LibraryChanged skip by RemoteMode", 1) # LOGINFO
                    continue

                self.EmbyServer.library.removed(IncomingData['Data']['ItemsRemoved'])
                ItemsUpdated = []

                if utils.usepathsubstitution:
                    for ItemId in IncomingData['Data']['ItemsUpdated']: # Filter updates when "use path substitution" is enabled (plugin) and "extract video information from files" is enabled (Kodi)
                        if int(ItemId) in playerops.ItemSkipUpdate:
                            xbmc.log(f"Emby.hooks.websocket: LibraryChanged skip by ItemSkipUpdate / Id: {ItemId} / ItemSkipUpdate: {playerops.ItemSkipUpdate}", 1) # LOGINFO
                            playerops.ItemSkipUpdate.remove(int(ItemId))
                            continue

                        ItemsUpdated.append(ItemId)
                else:
                    ItemsUpdated = IncomingData['Data']['ItemsUpdated']

                UpdateItemIds = (len(ItemsUpdated) + len(IncomingData['Data']['ItemsAdded'])) * [None] # preallocate memory

                for Index, ItemId in enumerate(ItemsUpdated + IncomingData['Data']['ItemsAdded']):
                    UpdateItemIds[Index] = (ItemId, "unknown")

                UpdateItemIds = list(dict.fromkeys(UpdateItemIds)) # filter duplicates
                self.EmbyServer.library.updated(UpdateItemIds)

                if self.SyncInProgress:
                    xbmc.log("Emby.hooks.websocket: Emby server sync in progress, delay updates", 1) # LOGINFO
                else:
                    self.EmbyServer.library.RunJobs()
            elif IncomingData['MessageType'] == 'ServerRestarting':
                xbmc.log("Emby.hooks.websocket: [ ServerRestarting ]", 1) # LOGINFO

                if utils.restartMsg:
                    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33006), icon=utils.icon)

                self.EmbyServer.ServerReconnect()
            elif IncomingData['MessageType'] == 'ServerShuttingDown':
                xbmc.log("Emby.hooks.websocket: [ ServerShuttingDown ]", 1) # LOGINFO
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33236))
                self.EmbyServer.ServerReconnect()
            elif IncomingData['MessageType'] == 'RestartRequired':
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33237))
            elif IncomingData['MessageType'] == 'Play':
                playerops.PlayEmby(IncomingData['Data']['ItemIds'], IncomingData['Data']['PlayCommand'], int(IncomingData['Data'].get('StartIndex', 0)), int(IncomingData['Data'].get('StartPositionTicks', 0)), self.EmbyServer, 0)
            elif IncomingData['MessageType'] == 'Playstate':
                if playerops.PlayerId != -1:
                    if IncomingData['Data']['Command'] == 'Seek':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, False)
                    elif IncomingData['Data']['Command'] == 'SeekRelative':
                        playerops.Seek(int(IncomingData['Data']['SeekPositionTicks']), True, 0, True)
                    elif IncomingData['Data']['Command'] == "Stop":
                        playerops.Stop(True)
                    elif IncomingData['Data']['Command'] == "Unpause":
                        playerops.Unpause(True)
                    elif IncomingData['Data']['Command'] == "Pause":
                        playerops.Pause(True, 0, 0)
                    elif IncomingData['Data']['Command'] == "PlayPause": # Toggle pause
                        playerops.PauseToggle(True)
                    elif IncomingData['Data']['Command'] == "NextTrack":
                        playerops.Next()
                    elif IncomingData['Data']['Command'] == "PreviousTrack":
                        playerops.Previous()

                xbmc.log(f"Emby.hooks.websocket: command: {IncomingData['Data']['Command']} / PlayedId: {playerops.PlayerId}", 1) # LOGINFO

    def EmbyServerSyncCheck(self):
        xbmc.log("Emby.hooks.websocket: THREAD: --->[ Emby server is busy, sync in progress ]", 1) # LOGINFO
        utils.SyncPause[f"server_busy_{self.EmbyServer.ServerData['ServerId']}"] = True

        if utils.busyMsg:
            utils.progress_open(utils.Translate(33411))

        while self.SyncRefresh or self.TasksRunning:
            self.SyncRefresh = False

            if utils.sleep(5): # every 5 seconds a progress update is expected. If not, sync was canceled
                break

        if utils.busyMsg:
            utils.progress_close()

        self.SyncInProgress = False
        utils.SyncPause[f"server_busy_{self.EmbyServer.ServerData['ServerId']}"] = False
        self.EmbyServer.library.RunJobs()
        xbmc.log("Emby.hooks.websocket: THREAD: ---<[ Emby server is busy, sync in progress ]", 1) # LOGINFO

    def confirm_remote(self, SessionId, Timeout): # threaded
        self.EmbyServer.API.send_text_msg(SessionId, "remotecommand", f"support|{self.EmbyServer.EmbySession[0]['Id']}", True)

        if utils.remotecontrol_auto_ack:
            Ack = True
        else:
            Ack = utils.Dialog.yesno(heading=utils.addon_name, message="Accept remote connection", autoclose=int(Timeout) * 1000)

        if Ack: # send confirm msg
            self.EmbyServer.API.send_text_msg(SessionId, "remotecommand", f"ack|{self.EmbyServer.EmbySession[0]['Id']}|{self.EmbyServer.EmbySession[0]['DeviceName']}|{self.EmbyServer.EmbySession[0]['UserName']}", True)

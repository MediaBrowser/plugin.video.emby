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
import helper.jsonrpc
import helper.utils as Utils
import database.db_open
import emby.listitem as ListItem

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


class ABNF:
    def __init__(self, fin, rsv1, rsv2, rsv3, opcode, mask, data):
        self.fin = fin
        self.rsv1 = rsv1
        self.rsv2 = rsv2
        self.rsv3 = rsv3
        self.opcode = opcode
        self.mask = mask
        self.data = data
        self.get_mask_key = os.urandom

    def __str__(self):
        return "fin=" + str(self.fin) + " opcode=" + str(self.opcode) + " data=" + str(self.data)

    def format(self):
        length = len(self.data)
        frame_header = struct.pack("B", (self.fin << 7 | self.rsv1 << 6 | self.rsv2 << 5 | self.rsv3 << 4 | self.opcode))

        if length < 0x7d:
            frame_header += struct.pack("B", (self.mask << 7 | length))
        elif length < 1 << 16:  # LENGTH_16
            frame_header += struct.pack("B", (self.mask << 7 | 0x7e))
            frame_header += struct.pack("!H", length)
        else:
            frame_header += struct.pack("B", (self.mask << 7 | 0x7f))
            frame_header += struct.pack("!Q", length)

        if not self.mask:
            return frame_header + self.data

        mask_key = self.get_mask_key(4)
        return frame_header + mask_key + maskData(mask_key, self.data)

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
        self.connect("%s/embywebsocket?api_key=%s&device_id=%s" % (server, self.EmbyServer.Token, Utils.device_id))
        threading.Thread(target=self.ping).start()

        while not self.stop:
            data = self.recv()

            if data is None or self.stop:
                break

            if data:
                threading.Thread(target=self.on_message, args=(data,)).start()

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
            Utils.dialog("notification", heading="{emby}", icon="DefaultIconError.png", message="Websocket is offline", sound=True)
            return False

    def sendCommands(self, payload, opcode):
        if opcode == 0x1:
            payload = payload.encode("utf-8")

        frame = ABNF(1, 0, 0, 0, opcode, 1, payload)
        data = frame.format()

        while data:
            try:
                l = self.sock.send(data)
                data = data[l:]
            except:  # Offline
                break

    def ping(self):
        while True:
            if xbmc.Monitor().waitForAbort(10):
                return

            if self.stop:
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
            rsv1 = b1 >> 6 & 1
            rsv2 = b1 >> 5 & 1
            rsv3 = b1 >> 4 & 1
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
            frame = ABNF(fin, rsv1, rsv2, rsv3, opcode, has_mask, payload)

            if frame.opcode in (0x2, 0x1, 0x0):
                if self._cont_data:
                    self._cont_data[1] += frame.data
                else:
                    self._cont_data = [frame.opcode, frame.data]

                if frame.fin:
                    data = self._cont_data
                    self._cont_data = None
                    return data
            elif frame.opcode == 0x8:
                self.sendCommands(struct.pack('!H', 1000) + b"", 0x8)
                return None  # (frame.opcode, None)
            elif frame.opcode == 0x9:
                self.sendCommands(frame.data, 0xa)  # Pong
                return False #frame.data
            elif frame.opcode == 0xa:
                return False #frame.data

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
                Utils.dialog("notification", heading=IncommingData['Data']['Arguments']['Header'], message=IncommingData['Data']['Arguments']['Text'], icon="{emby}", time=int(Utils.displayMessage) * 1000)
            elif IncommingData['Data']['Name'] in ('Mute', 'Unmute'):
                xbmc.executebuiltin('Mute')
            elif IncommingData['Data']['Name'] == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % IncommingData['Data']['Arguments']['Volume'])
            elif IncommingData['Data']['Name'] == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % IncommingData['Data']['Arguments']['RepeatMode'])
            elif IncommingData['Data']['Name'] == 'SendString':
                helper.jsonrpc.JSONRPC('Input.SendText').execute({'text': IncommingData['Data']['Arguments']['String'], 'done': False})
            elif IncommingData['Data']['Name'] == 'GoHome':
                helper.jsonrpc.JSONRPC('GUI.ActivateWindow').execute({'window': "home"})
            elif IncommingData['Data']['Name'] == 'Guide':
                helper.jsonrpc.JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})
            elif IncommingData['Data']['Name'] == 'MoveUp':
                helper.jsonrpc.JSONRPC("Input.Up").execute(False)
            elif IncommingData['Data']['Name'] == 'MoveDown':
                helper.jsonrpc.JSONRPC("Input.Down").execute(False)
            elif IncommingData['Data']['Name'] == 'MoveRight':
                helper.jsonrpc.JSONRPC("Input.Right").execute(False)
            elif IncommingData['Data']['Name'] == 'MoveLeft':
                helper.jsonrpc.JSONRPC("Input.Left").execute(False)
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
                Utils.dialog("notification", heading="{emby}", message=Utils.Translate(33006), icon="{emby}")

            self.EmbyServer.Online = False
            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncommingData['MessageType'] == 'ServerShuttingDown':
            Utils.dialog("notification", heading="{emby}", message="Enable server shutdown")
            self.EmbyServer.Online = False
            self.EmbyServer.ServerReconnect(self.EmbyServer.server_id)
        elif IncommingData['MessageType'] == 'RestartRequired':
            Utils.dialog("notification", heading="{emby}", message="Enable server restart required")
        elif IncommingData['MessageType'] == 'Play':
            Play(IncommingData['Data']['ItemIds'], self.EmbyServer.server_id, IncommingData['Data']['PlayCommand'], int(IncommingData['Data'].get('StartIndex', -1)), int(IncommingData['Data'].get('StartPositionTicks', -1)), self.EmbyServer)
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

def AddPlaylistItem(Position, EmbyID, server_id, Offset, EmbyServer):
    with database.db_open.io(Utils.DatabaseFiles, server_id, False) as embydb:
        Data = embydb.get_item_by_wild_id(str(EmbyID))

    if Data:  # Requested video is synced to KodiDB. No additional info required
        if Data[0][1] in ("song", "album", "artist"):
            playlistID = 0
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        else:
            playlistID = 1
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        Pos = GetPlaylistPos(Position, playlist, Offset)
        helper.jsonrpc.JSONRPC('Playlist.Insert').execute({'playlistid': playlistID, 'position': Pos, 'item': {'%sid' % Data[0][1]: int(Data[0][0])}})
    else:
        item = EmbyServer.API.get_item(EmbyID)
        li = ListItem.set_ListItem(item, server_id)
        path = ""

        if item['Type'] == "MusicVideo":
            Type = "musicvideo"
        elif item['Type'] == "Movie":
            Type = "movie"
        elif item['Type'] == "Episode":
            Type = "episode"
        elif item['Type'] == "Audio":
            path = "http://127.0.0.1:57578/embyaudioremote-%s-%s-%s-%s" % (server_id, item['Id'], "audio", Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))
            Type = "audio"
        elif item['Type'] == "Video":
            Type = "video"
        elif item['Type'] == "Trailer":
            Type = "trailer"
        elif item['Type'] == "TvChannel":
            Type = "tvchannel"
            path = "http://127.0.0.1:57578/embylivetv-%s-%s-stream.ts" % (server_id, item['Id'])
        else:
            return None

        if not path:
            if len(item['MediaSources'][0]['MediaStreams']) >= 1:
                path = "http://127.0.0.1:57578/embyvideoremote-%s-%s-%s-%s-%s-%s-%s" % (server_id, item['Id'], Type, item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], item['MediaSources'][0]['MediaStreams'][0]['Codec'], Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))
            else:
                path = "http://127.0.0.1:57578/embyvideoremote-%s-%s-%s-%s-%s-%s-%s" % (server_id, item['Id'], Type, item['MediaSources'][0]['Id'], "0", "", Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))

        li.setProperty('path', path)

        if Type == "audio":
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        else:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        Pos = GetPlaylistPos(Position, playlist, Offset)
        playlist.add(path, li, index=Pos)

    return playlist

# Websocket command from Emby server
def Play(ItemIds, ServerId, PlayCommand, StartIndex, StartPositionTicks, EmbyServer):
    FirstItem = True
    Offset = 0
    playlist = None

    for ID in ItemIds:
        Offset += 1

        if PlayCommand == "PlayNow":
            playlist = AddPlaylistItem("current", ID, ServerId, Offset, EmbyServer)
        elif PlayCommand == "PlayNext":
            playlist = AddPlaylistItem("current", ID, ServerId, Offset, EmbyServer)
        elif PlayCommand == "PlayLast":
            playlist = AddPlaylistItem("last", ID, ServerId, 0, EmbyServer)

        # Play Item
        if PlayCommand == "PlayNow":
            if StartIndex != -1:
                if Offset == int(StartIndex + 1):
                    if FirstItem:
                        Pos = playlist.getposition()

                        if Pos == -1:
                            Pos = 0

                        PlaylistStartIndex = Pos + Offset
                        xbmc.Player().play(item=playlist, startpos=PlaylistStartIndex)
                        Offset = 0
                        FirstItem = False
            else:
                if FirstItem:
                    Pos = playlist.getposition()

                    if Pos == -1:
                        Pos = 0

                    xbmc.Player().play(item=playlist, startpos=Pos + Offset)

                    if StartPositionTicks != -1:
                        xbmc.Player().seekTime(StartPositionTicks / 10000000)

                    Offset = 0
                    FirstItem = False

def GetPlaylistPos(Position, playlist, Offset):
    if Position == "current":
        Pos = playlist.getposition()

        if Pos == -1:
            Pos = 0

        Pos = Pos + Offset
    elif Position == "previous":
        Pos = playlist.getposition()

        if Pos == -1:
            Pos = 0
    elif Position == "last":
        Pos = playlist.size()
    else:
        Pos = Position

    return Pos

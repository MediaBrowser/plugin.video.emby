import base64
import os
import struct
import threading
import uuid
import xbmc

from helper import utils


class WebSocket:
    def __init__(self, Common):
        self.Common = Common
        self.Buffer = b""
        self.SendLock = threading.Lock()
        self.Running = False
        self.ThreadRunning = False

    def start(self):
        if self.ThreadRunning:
            return

        self.Running = True
        self.ThreadRunning = True
        utils.start_thread(self.listen, ())

    def stop(self, SendWebsocketClose=True, DeleteConnection=True):
        self.Running = False
        if utils.websocketenabled:
            self.Common.WebsocketMessageQueue.put("QUIT")

        if "WEBSOCKET" in self.Common.Connection:
            self.close(SendWebsocketClose, DeleteConnection)

        with utils.SafeLock(self.Common.HTTPThreadsRunningCondition):
            self.Common.HTTPThreadsRunningCondition.notify_all()

    def send_locked(self, payload, opcode):
        if opcode not in (0x1, 0x2, 0x8, 0x9, 0xa):
            xbmc.log(f"EMBY.emby.websocket: Invalid Websocket send opcode: {opcode}", 2) # LOGWARNING
            return 698

        if opcode == 0x1:
            if not isinstance(payload, str):
                xbmc.log("EMBY.emby.websocket: Websocket text payload must be str", 2) # LOGWARNING
                return 698

            payload = payload.encode("utf-8")
        elif not isinstance(payload, bytes):
            try:
                payload = bytes(payload)
            except Exception:
                xbmc.log("EMBY.emby.websocket: Invalid Websocket payload type", 2) # LOGWARNING
                return 698

        length = len(payload)

        if opcode >= 0x8 and length > 125:
            xbmc.log("EMBY.emby.websocket: Websocket control frame payload > 125 bytes", 2) # LOGWARNING
            return 698

        frame_header = struct.pack("B", (1 << 7 | 0 << 6 | 0 << 5 | 0 << 4 | opcode))

        if length <= 0x7d:
            frame_header += struct.pack("B", (1 << 7 | length))
        elif length < 1 << 16:
            frame_header += struct.pack("B", (1 << 7 | 0x7e))
            frame_header += struct.pack("!H", length)
        else:
            frame_header += struct.pack("B", (1 << 7 | 0x7f))
            frame_header += struct.pack("!Q", length)

        mask_key = os.urandom(4)
        data = frame_header + mask_key + maskData(mask_key, payload)

        StatusCodeSocket, _ = self.Common.socket_io(data, "WEBSOCKET", 12)
        return StatusCodeSocket

    def send(self, payload, opcode):
        with self.SendLock:
            if "WEBSOCKET" not in self.Common.Connection:
                return False

            StatusCodeSocket = self.send_locked(payload, opcode)

        if StatusCodeSocket:
            xbmc.log(f"EMBY.emby.websocket: Websocket send interupted {StatusCodeSocket}", 1) # LOGINFO
            return False

        return True

    def close(self, SendWebsocketClose=True, DeleteConnection=True):
        if "WEBSOCKET" not in self.Common.Connection:
            return

        with self.SendLock:
            if "WEBSOCKET" not in self.Common.Connection:
                return

            if SendWebsocketClose:
                try:
                    self.Common.Connection["WEBSOCKET"]["Socket"].settimeout(1) # set timeout
                    StatusCodeSocket = self.send_locked(b"", 0x8)

                    if StatusCodeSocket:
                        xbmc.log(f"EMBY.emby.websocket: Socket WEBSOCKET send close error 1: {StatusCodeSocket}", 2) # LOGWARNING
                except Exception as error:
                    xbmc.log(f"EMBY.emby.websocket: Socket WEBSOCKET send close error 1: {error}", 2) # LOGWARNING

            try:
                self.Common.Connection["WEBSOCKET"]["Socket"].close()
            except Exception as error:
                xbmc.log(f"EMBY.emby.websocket: Socket WEBSOCKET close error: {error}", 2) # LOGWARNING

            try:
                if DeleteConnection:
                    del self.Common.Connection["WEBSOCKET"]
            except Exception as error:
                xbmc.log(f"EMBY.emby.websocket: Socket WEBSOCKET reset error: {error}", 2) # LOGWARNING

        if utils.DebugLog: xbmc.log("EMBY.emby.websocket (DEBUG): Socket WEBSOCKET closed", 1) # LOGDEBUG

    def disable_thread(self):
        self.Running = False
        self.ThreadRunning = False

        with utils.SafeLock(self.Common.HTTPThreadsRunningCondition):
            self.Common.HTTPThreadsRunningCondition.notify_all()

    def listen(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket (DEBUG): THREAD: --->[ Websocket {self.Common.HTTP.ServerData['ServerId']} ]", 1) # LOGDEBUG

        while self.Running and self.ThreadRunning and self.Common.HTTP.Running:
            if utils.DebugLog: xbmc.log("EMBY.emby.websocket: Websocket connecting", 1) # LOGINFO

            if self.Common.socket_open(self.Common.HTTP.ServerData['ServerUrl'], "WEBSOCKET", False):
                if utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket: THREAD: ---<[ Websocket {self.Common.HTTP.ServerData['ServerId']} shutdown 1 ]", 1) # LOGDEBUG
                    self.disable_thread()
                    return

                continue

            uid = uuid.uuid4()
            EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')

            with utils.SafeLock(self.Common.HTTP.Connecting):
                if not self.ThreadRunning or not self.Common.HTTP.Running or "WEBSOCKET" not in self.Common.Connection:
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket: THREAD: ---<[ Websocket {self.Common.HTTP.ServerData['ServerId']} shutdown 2 ]", 1) # LOGDEBUG
                    self.disable_thread()
                    return

                self.Common.Connection["WEBSOCKET"]["RequestHeader"].update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": EncodingKey, "Sec-WebSocket-Version": "13"})

            StatusCode, _, Payload = self.Common.HTTP.socket_request("GET", f"embywebsocket?api_key={self.Common.HTTP.ServerData['AccessToken']}&deviceId={self.Common.HTTP.ServerData['DeviceId']}", {}, True, 12, 30, "WEBSOCKET", "", None, 0, self.Common.HTTP.ServerData['ServerUrl'], False)

            if StatusCode == 601: # quit
                if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket: THREAD: ---<[ Websocket {self.Common.HTTP.ServerData['ServerId']} quit ]", 1) # LOGDEBUG
                self.disable_thread()
                return

            if StatusCode != 101:
                self.close(False)

                if utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket: THREAD: ---<[ Websocket {self.Common.HTTP.ServerData['ServerId']} shutdown 2 ]", 1) # LOGDEBUG
                    self.disable_thread()
                    return

                continue

            if not self.send('{"MessageType": "ScheduledTasksInfoStart", "Data": "0,1500"}', 0x1): # subscribe notifications
                self.close()
                continue

            if "WEBSOCKET" not in self.Common.Connection:
                continue

            self.Common.Connection["WEBSOCKET"]["Socket"].settimeout(3)
            self.Buffer = Payload
            ConnectionClosed = False
            ReconnectConnection = False
            WebsocketFragmentBuffer = b''

            while self.Running and self.ThreadRunning and self.Common.HTTP.Running:
                if not self.Common.HTTP.Running:
                    xbmc.log("EMBY.emby.websocket: Websocket receive stopped", 1) # LOGINFO
                    ConnectionClosed = True
                    break

                StatusCodeSocket, PayloadRecv = self.Common.socket_io("", "WEBSOCKET", 6)

                if StatusCodeSocket:
                    xbmc.log(f"EMBY.emby.websocket: Websocket receive interupted {StatusCodeSocket}", 1) # LOGINFO
                    self.close(False)
                    ReconnectConnection = True
                    break

                self.Buffer += PayloadRecv

                while True:
                    if len(self.Buffer) < 2:
                        break

                    FrameHeader = self.Buffer[:2]
                    Curser = 2
                    fin = (FrameHeader[0] >> 7) & 1
                    opcode = FrameHeader[0] & 0x0f
                    FrameLength = FrameHeader[1] & 0x7f

                    if FrameLength == 0x7e:
                        if len(self.Buffer) < Curser + 2:
                            break

                        FrameLength = struct.unpack("!H", self.Buffer[Curser:Curser + 2])[0]
                        Curser += 2
                    elif FrameLength == 0x7f:
                        if len(self.Buffer) < Curser + 8:
                            break

                        FrameLength = struct.unpack("!Q", self.Buffer[Curser:Curser + 8])[0]
                        Curser += 8

                    FrameLengthEndPos = Curser + FrameLength

                    if len(self.Buffer) < FrameLengthEndPos:
                        if utils.DebugLog: xbmc.log("EMBY.emby.websocket (DEBUG): Websocket incomplete frame", 1) # LOGDEBUG
                        break

                    payload = self.Buffer[Curser:FrameLengthEndPos]
                    Curser = FrameLengthEndPos

                    if opcode in (0x1, 0x2):
                        if fin:
                            if payload:
                                self.Common.WebsocketMessageQueue.put(payload)
                        else:
                            WebsocketFragmentBuffer = payload
                    elif opcode == 0x0:
                        WebsocketFragmentBuffer += payload

                        if fin:
                            if WebsocketFragmentBuffer:
                                self.Common.WebsocketMessageQueue.put(WebsocketFragmentBuffer)

                            WebsocketFragmentBuffer = b''
                    elif opcode == 0x8: # Connection close
                        if not self.send(payload, 0x8):
                            ReconnectConnection = True
                            self.Buffer = b""
                            break

                        if utils.DebugLog: xbmc.log("EMBY.emby.websocket (DEBUG): Websocket connection closed", 1) # LOGDEBUG
                        self.Buffer = self.Buffer[Curser:]
                        ConnectionClosed = True
                        break
                    elif opcode == 0x9: # Ping
                        if not self.send(payload, 0xa): # Pong
                            ReconnectConnection = True
                            self.Buffer = b""
                            break
                    elif opcode == 0xa: # Pong
                        if utils.DebugLog: xbmc.log("EMBY.emby.websocket (DEBUG): Websocket Pong received", 1) # LOGDEBUG

                    self.Buffer = self.Buffer[Curser:]

                    if ConnectionClosed or ReconnectConnection:
                        break

                if ReconnectConnection:
                    self.close(False)
                    break

                if ConnectionClosed:
                    self.close(False)
                    break

            if ReconnectConnection:
                continue

            if ConnectionClosed:
                break

        self.disable_thread()
        self.Running = False
        self.ThreadRunning = False
        with utils.SafeLock(self.Common.HTTPThreadsRunningCondition):
            self.Common.HTTPThreadsRunningCondition.notify_all()

        if utils.DebugLog: xbmc.log(f"EMBY.emby.websocket (DEBUG): THREAD: ---<[ Websocket {self.Common.HTTP.ServerData['ServerId']} ]", 1) # LOGDEBUG


def maskData(mask_key, data):
    if not data:
        return b""

    full_mask = mask_key * ((len(data) // len(mask_key)) + 1)
    data_int = int.from_bytes(data, 'big')
    mask_int = int.from_bytes(full_mask[:len(data)], 'big')
    return (data_int ^ mask_int).to_bytes(len(data), 'big')

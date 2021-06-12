# -*- coding: utf-8 -*-
import json
import threading
import os
import array
import struct
import uuid
import hashlib
import base64
import socket
import ssl

import xbmc

import helper.loghandler

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str
    Python3 = True
    from urllib.parse import urlparse
else:
    Python3 = False
    from urlparse import urlparse

def maskData(mask_key, data):
    _m = array.array("B", mask_key)
    _d = array.array("B", data)

    for i in range(len(_d)):
        _d[i] ^= _m[i % 4] #ixor

    if Python3:
        return _d.tobytes()

    return _d.tostring()

class ABNF():
    def __init__(self, fin=0, rsv1=0, rsv2=0, rsv3=0, opcode=0x1, mask=1, data=""):
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
        elif length < 1 << 16: #LENGTH_16
            frame_header += struct.pack("B", (self.mask << 7 | 0x7e))
            frame_header += struct.pack("!H", length)
        else:
            frame_header += struct.pack("B", (self.mask << 7 | 0x7f))
            frame_header += struct.pack("!Q", length)

        if not self.mask:
            return frame_header + self.data

        mask_key = self.get_mask_key(4)
        return frame_header + self._get_masked(mask_key)

    def _get_masked(self, mask_key):
        s = maskData(mask_key, self.data)
        return mask_key + b"".join(s)

class WSClient(threading.Thread):
    def __init__(self, Server, DeviceID, Token, server_id):
        self.Server = Server
        self.DeviceID = DeviceID
        self.Token = Token
        self.server_id = server_id
        self.wsc = None
        self.stop = False
        self.LOG = helper.loghandler.LOG('Emby.core.ws_client')
        self.LOG.debug("WSClient initializing...")
        self.stop = False
        self.connected = False
        self.sock = socket.socket()
        self.get_mask_key = None
        self._recv_buffer = []
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        self._cont_data = None
        threading.Thread.__init__(self)

    def run(self):
        self.LOG.info("--->[ websocket ]")
        server = self.Server.replace('https', "wss") if self.Server.startswith('https') else self.Server.replace('http', "ws")
        self.connect("%s/embywebsocket?api_key=%s&device_id=%s" % (server, self.Token, self.DeviceID))
        thread = threading.Thread(target=self.ping)
        thread.start()
        data = None

        while not self.stop:
            try:
                data = self.recv()
            except:
                break

            if data is None or self.stop:
                break

            self.on_message(data)

        self.LOG.info("---<[ websocket ]")

    def on_message(self, message):
        message = json.loads(message)
        data = message.get('Data', {})

        if not data: #check if data is an empty string
            data = {}

        data['ServerId'] = self.server_id

        if message['MessageType'] == 'RefreshProgress':
            self.LOG.debug("Ignoring %s" % message)
            return

        data = '"[%s]"' % json.dumps(data).replace('"', '\\"')
        xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", message['MessageType'], data))

    def send(self, message, data):
        self.sock.send(json.dumps({'MessageType': message, "Data": data}), 0x1)

    def close(self):
        self.stop = True

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass

        self.connected = False
        self.sock.close()

    def connect(self, url):
        #Parse URL
        scheme, url = url.split(":", 1)
        parsed = urlparse(url, scheme="http")
        resource = parsed.path

        if parsed.query:
            resource += "?" + parsed.query

        hostname = parsed.hostname
        port = parsed.port
        is_secure = scheme == "wss"

        #Connect
        self.sock.connect((hostname, port))
        self.sock.settimeout(None)

        if is_secure:
            self.sock = ssl.SSLContext(ssl.PROTOCOL_SSLv23).wrap_socket(self.sock, do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=hostname)

        #Handshake
        headers = []
        headers.append("GET %s HTTP/1.1" % resource)
        headers.append("Upgrade: websocket")
        headers.append("Connection: Upgrade")
        hostport = "%s:%d" % (hostname, port)
        headers.append("Host: %s" % hostport)
        headers.append("Origin: http://%s" % hostport)
        uid = uuid.uuid4()
        key = base64.b64encode(uid.bytes).strip().decode('utf-8')
        headers.append("Sec-WebSocket-Key: %s" % key)
        headers.append("Sec-WebSocket-Version: 13")
        headers.append("")
        headers.append("")
        header_str = "\r\n".join(headers)
        self.sock.send(header_str.encode('utf-8'))

        #Read Headers
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

        #Validate Headers
        result = headers.get("sec-websocket-accept", None)

        if not result:
            return False

        value = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        value = value.encode("utf-8")
        hashed = base64.b64encode(hashlib.sha1(value).digest()).decode()

        #Set connected state
        self.connected = hashed == result

    def sendCommands(self, payload, opcode):
        if opcode == 0x1 and isinstance(payload, unicode):
            frame = payload.encode("utf-8")
        else:
            frame = ABNF(1, 0, 0, 0, opcode, 1, payload)

        if self.get_mask_key:
            frame.get_mask_key = self.get_mask_key

        data = frame.format()
        length = len(data)

        while data:
            try:
                l = self.sock.send(data)
                data = data[l:]
            except: #Offline
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

            if Python3:
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
            payload = self._recv_strict(self._frame_length)

            if has_mask:
                payload = maskData(self._frame_mask, payload)

            # Reset for next frame
            self._frame_header = None
            self._frame_length = None
            self._frame_mask = None
            frame = ABNF(fin, rsv1, rsv2, rsv3, opcode, has_mask, payload)

            if frame.opcode in (0x1, 0x0):
                if self._cont_data:
                    self._cont_data[1] += frame.data
                else:
                    self._cont_data = [frame.opcode, frame.data]

                if frame.fin:
                    data = self._cont_data
                    self._cont_data = None
                    return data[1]

            elif frame.opcode == 0x8:
                self.sendCommands(struct.pack('!H', 1000) + b"", 0x8)
                return None #(frame.opcode, None)
            elif frame.opcode == 0x9:
                self.sendCommands(frame.data, 0xa) #Pong

    def _recv_strict(self, bufsize):
        shortage = bufsize - sum(len(x) for x in self._recv_buffer)

        while shortage > 0:
            bytesData = self.sock.recv(shortage)
            self._recv_buffer.append(bytesData)
            shortage -= len(bytesData)

        unified = b"".join(self._recv_buffer)

        if shortage == 0:
            self._recv_buffer = []
            return unified

        self._recv_buffer = [unified[bufsize:]]

        return unified[:bufsize]

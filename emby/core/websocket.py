# -*- coding: utf-8 -*-
#websocket - WebSocket client library for Python

#Copyright (C) 2010 Hiroki Ohtani(liris)

#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.

#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.

#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import array
import struct
import uuid
import hashlib
import base64
import threading
import time
import logging
import traceback
import sys
import socket

import xbmc

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str

if sys.version_info[0] < 3:
    Python3 = False
    from urlparse import urlparse
else:
    Python3 = True
    from urllib.parse import urlparse

try:
    import ssl
    from ssl import SSLError
    HAVE_SSL = True
except ImportError:
    # dummy class of SSLError for ssl none-support environment.
    class SSLError(Exception):
        pass

    HAVE_SSL = False

# websocket supported version.
VERSION = 13

# closing frame status codes.
STATUS_NORMAL = 1000
STATUS_GOING_AWAY = 1001
STATUS_PROTOCOL_ERROR = 1002
STATUS_UNSUPPORTED_DATA_TYPE = 1003
STATUS_STATUS_NOT_AVAILABLE = 1005
STATUS_ABNORMAL_CLOSED = 1006
STATUS_INVALID_PAYLOAD = 1007
STATUS_POLICY_VIOLATION = 1008
STATUS_MESSAGE_TOO_BIG = 1009
STATUS_INVALID_EXTENSION = 1010
STATUS_UNEXPECTED_CONDITION = 1011
STATUS_TLS_HANDSHAKE_ERROR = 1015
logger = logging.getLogger()

class WebSocketException(Exception):
    """
    websocket exeception class.
    """

class WebSocketConnectionClosedException(WebSocketException):
    """
    If remote host closed the connection or some network error happened,
    this exception will be raised.
    """

class WebSocketTimeoutException(WebSocketException):
    """
    WebSocketTimeoutException will be raised at socket timeout during read/write data.
    """

def _wrap_sni_socket(sock, sslopt, hostname):
    context = ssl.SSLContext(sslopt.get('ssl_version', ssl.PROTOCOL_SSLv23))

    if sslopt.get('cert_reqs', ssl.CERT_NONE) != ssl.CERT_NONE:
        capath = ssl.get_default_verify_paths().capath
        context.load_verify_locations(cafile=sslopt.get('ca_certs', None), capath=sslopt.get('ca_cert_path', capath))

    return context.wrap_socket(
        sock,
        do_handshake_on_connect=sslopt.get('do_handshake_on_connect', True),
        suppress_ragged_eofs=sslopt.get('suppress_ragged_eofs', True),
        server_hostname=hostname,
    )

def _parse_url(url):
    if ":" not in url:
        raise ValueError("url is invalid")

    scheme, url = url.split(":", 1)
    parsed = urlparse(url, scheme="http")

    if parsed.hostname:
        hostname = parsed.hostname
    else:
        raise ValueError("hostname is invalid")

    port = 0

    if parsed.port:
        port = parsed.port

    is_secure = False

    if scheme == "ws":
        if not port:
            port = 80
    elif scheme == "wss":
        is_secure = True
        if not port:
            port = 443
    else:
        raise ValueError("scheme %s is invalid" % scheme)

    if parsed.path:
        resource = parsed.path
    else:
        resource = "/"

    if parsed.query:
        resource += "?" + parsed.query

    return (hostname, port, resource, is_secure)

def create_connection(url, timeout=None, **options):
    sockopt = options.get("sockopt", [])
    sslopt = options.get("sslopt", {})
    websock = WebSocket(sockopt=sockopt, sslopt=sslopt)
    websock.settimeout(timeout)
    websock.connect(url, **options)
    return websock

_MAX_INTEGER = (1 << 32) -1
_MAX_CHAR_BYTE = (1<<8) -1

def _create_sec_websocket_key():
    uid = uuid.uuid4()
    return base64.b64encode(uid.bytes).strip()

_HEADERS_TO_CHECK = {
    "upgrade": "websocket",
    "connection": "upgrade",
    }

class ABNF():
    # operation code values.
    OPCODE_CONT = 0x0
    OPCODE_TEXT = 0x1
    OPCODE_BINARY = 0x2
    OPCODE_CLOSE = 0x8
    OPCODE_PING = 0x9
    OPCODE_PONG = 0xa

    # available operation code value tuple
    OPCODES = (OPCODE_CONT, OPCODE_TEXT, OPCODE_BINARY, OPCODE_CLOSE, OPCODE_PING, OPCODE_PONG)

    # opcode human readable string
    OPCODE_MAP = {
        OPCODE_CONT: "cont",
        OPCODE_TEXT: "text",
        OPCODE_BINARY: "binary",
        OPCODE_CLOSE: "close",
        OPCODE_PING: "ping",
        OPCODE_PONG: "pong"
        }

    # data length threashold.
    LENGTH_7 = 0x7d
    LENGTH_16 = 1 << 16
    LENGTH_63 = 1 << 63

    def __init__(self, fin=0, rsv1=0, rsv2=0, rsv3=0, opcode=OPCODE_TEXT, mask=1, data=""):
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

    @staticmethod
    def create_frame(data, opcode):
        if opcode == ABNF.OPCODE_TEXT and isinstance(data, unicode):
            data = data.encode("utf-8")
        # mask must be set if send data from client
        return ABNF(1, 0, 0, 0, opcode, 1, data)

    def format(self):
        if any(x not in (0, 1) for x in [self.fin, self.rsv1, self.rsv2, self.rsv3]):
            raise ValueError("not 0 or 1")
        if self.opcode not in ABNF.OPCODES:
            raise ValueError("Invalid OPCODE")
        length = len(self.data)

        if length >= ABNF.LENGTH_63:
            raise ValueError("data is too long")

        frame_header = struct.pack("B", (self.fin << 7 | self.rsv1 << 6 | self.rsv2 << 5 | self.rsv3 << 4 | self.opcode))

        if length < ABNF.LENGTH_7:
            frame_header += struct.pack("B", (self.mask << 7 | length))
        elif length < ABNF.LENGTH_16:
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
        s = ABNF.maskData(mask_key, self.data)
        return mask_key + b"".join(s)

    @staticmethod
    def maskData(mask_key, data):
        _m = array.array("B", mask_key)
        _d = array.array("B", data)

        for i in range(len(_d)):
            _d[i] ^= _m[i % 4]

        return _d.tostring()

class WebSocket():
    def __init__(self, get_mask_key=None, sockopt=None, sslopt=None):
        if sockopt is None:
            sockopt = []

        if sslopt is None:
            sslopt = {}

        self.connected = False
        self.sock = socket.socket()

        for opts in sockopt:
            self.sock.setsockopt(*opts)

        self.sslopt = sslopt
        self.get_mask_key = get_mask_key
        # Buffers over the packets from the layer beneath until desired amount
        # bytes of bytes are received.
        self._recv_buffer = []
        # These buffer over the build-up of a single frame.
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        self._cont_data = None

    def fileno(self):
        return self.sock.fileno()

    def set_mask_key(self, func):
        self.get_mask_key = func

    def gettimeout(self):
        return self.sock.gettimeout()

    def settimeout(self, timeout):
        self.sock.settimeout(timeout)

    timeout = property(gettimeout, settimeout)

    def connect(self, url, **options):
        hostname, port, resource, is_secure = _parse_url(url)
        self.sock.connect((hostname, port))

        if is_secure:
            if HAVE_SSL:
                if self.sslopt is None:
                    sslopt = {}
                else:
                    sslopt = self.sslopt

                if ssl.HAS_SNI:
                    self.sock = _wrap_sni_socket(self.sock, sslopt, hostname)
                else:
                    self.sock = ssl.wrap_socket(self.sock, **sslopt)
            else:
                raise WebSocketException("SSL not available.")

        self._handshake(hostname, port, resource, **options)

    def _handshake(self, host, port, resource, **options):
        headers = []
        headers.append("GET %s HTTP/1.1" % resource)
        headers.append("Upgrade: websocket")
        headers.append("Connection: Upgrade")

        if port == 80:
            hostport = host
        else:
            hostport = "%s:%d" % (host, port)

        headers.append("Host: %s" % hostport)

        if "origin" in options:
            headers.append("Origin: %s" % options["origin"])
        else:
            headers.append("Origin: http://%s" % hostport)

        key = _create_sec_websocket_key().decode('utf-8')
        headers.append("Sec-WebSocket-Key: %s" % key)
        headers.append("Sec-WebSocket-Version: %s" % str(VERSION))

        if "header" in options:
            headers.extend(options["header"])

        headers.append("")
        headers.append("")
        header_str = "\r\n".join(headers)
        self._send(header_str.encode('utf-8'))
        status, resp_headers = self._read_headers()

        if status != 101:
            self.close()
            raise WebSocketException("Handshake Status %d" % status)

        success = self._validate_header(resp_headers, key)

        if not success:
            self.close()
            raise WebSocketException("Invalid WebSocket Header")

        self.connected = True

    def _validate_header(self, headers, key):
        result = headers.get("sec-websocket-accept", None)

        if not result:
            return False

        value = key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        value = value.encode("utf-8")
        hashed = base64.b64encode(hashlib.sha1(value).digest()).decode()
        return hashed == result

    def _read_headers(self):
        status = None
        headers = {}

        while True:
            line = self._recv_line()

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
                    raise WebSocketException("Invalid header")

        return status, headers

    def send(self, payload, opcode=ABNF.OPCODE_TEXT):
        frame = ABNF.create_frame(payload, opcode)

        if self.get_mask_key:
            frame.get_mask_key = self.get_mask_key

        data = frame.format()
        length = len(data)

        while data:
            l = self._send(data)
            data = data[l:]

        return length

    def send_binary(self, payload):
        return self.send(payload, ABNF.OPCODE_BINARY)

    def ping(self, payload=b""):
        self.send(payload, ABNF.OPCODE_PING)

    def pong(self, payload):
        self.send(payload, ABNF.OPCODE_PONG)

    def recv(self):
        opcode, data = self.recv_data()
        return data

    def recv_data(self):
        while True:
            frame = self.recv_frame()

            if not frame:
                # handle error:
                # 'NoneType' object has no attribute 'opcode'
                raise WebSocketException("Not a valid frame %s" % frame)
            elif frame.opcode in (ABNF.OPCODE_TEXT, ABNF.OPCODE_BINARY, ABNF.OPCODE_CONT):
                if frame.opcode == ABNF.OPCODE_CONT and not self._cont_data:
                    raise WebSocketException("Illegal frame")

                if self._cont_data:
                    self._cont_data[1] += frame.data
                else:
                    self._cont_data = [frame.opcode, frame.data]

                if frame.fin:
                    data = self._cont_data
                    self._cont_data = None
                    return data
            elif frame.opcode == ABNF.OPCODE_CLOSE:
                self.send_close()
                return (frame.opcode, None)
            elif frame.opcode == ABNF.OPCODE_PING:
                self.pong(frame.data)

    def recv_frame(self):
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
            payload = ABNF.maskData(self._frame_mask, payload)

        # Reset for next frame
        self._frame_header = None
        self._frame_length = None
        self._frame_mask = None
        return ABNF(fin, rsv1, rsv2, rsv3, opcode, has_mask, payload)

    def send_close(self, status=STATUS_NORMAL, reason=b""):
        if status < 0 or status >= ABNF.LENGTH_16:
            raise ValueError("code is invalid range")

        self.send(struct.pack('!H', status) + reason, ABNF.OPCODE_CLOSE)

    def close(self, status=STATUS_NORMAL, reason=""):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass

        self._closeInternal()

    def _closeInternal(self):
        self.connected = False
        self.sock.close()

    def _send(self, data):
        try:
            return self.sock.send(data)
        except socket.timeout as e:
            raise WebSocketTimeoutException(e.args[0])
        except Exception as e:
            if "timed out" in e.args[0]:
                raise WebSocketTimeoutException(e.args[0])
            else:
                raise e

    def _recv(self, bufsize):
        try:
            bytesData = self.sock.recv(bufsize)
        except socket.timeout as e:
            raise WebSocketTimeoutException(e.args[0])
        except SSLError as e:
            if e.args[0] == "The read operation timed out":
                raise WebSocketTimeoutException(e.args[0])
            else:
                raise

        if not bytesData:
            raise WebSocketConnectionClosedException()

        return bytesData

    def _recv_strict(self, bufsize):
        shortage = bufsize - sum(len(x) for x in self._recv_buffer)

        while shortage > 0:
            bytesData = self._recv(shortage)
            self._recv_buffer.append(bytesData)
            shortage -= len(bytesData)

        unified = b"".join(self._recv_buffer)

        if shortage == 0:
            self._recv_buffer = []
            return unified

        self._recv_buffer = [unified[bufsize:]]
        return unified[:bufsize]

    def _recv_line(self):
        line = []

        while True:
            c = self._recv(1).decode()
            line.append(c)

            if c == "\n":
                break

        return "".join(line)

class WebSocketApp():
    def __init__(self, url, header=[], on_open=None, on_message=None, on_error=None, on_close=None, keep_running=True, get_mask_key=None):

        self.url = url
        self.header = header
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.keep_running = keep_running
        self.get_mask_key = get_mask_key
        self.sock = None

    def send(self, data, opcode=ABNF.OPCODE_TEXT):
        if self.sock.send(data, opcode) == 0:
            raise WebSocketConnectionClosedException()

    def close(self):
        self.keep_running = False
        if self.sock != None:
            self.sock.close()

    def _send_ping(self, interval):
        while True:
            for i in range(interval):
                time.sleep(1)
                if not self.keep_running:
                    return
            self.sock.ping()

    def run_forever(self, sockopt=None, sslopt=None, ping_interval=0):
        if sockopt is None:
            sockopt = []

        if sslopt is None:
            sslopt = {}

        if self.sock:
            raise WebSocketException("socket is already opened")

        thread = None
        self.keep_running = True

        try:
            self.sock = WebSocket(self.get_mask_key, sockopt=sockopt, sslopt=sslopt)
            self.sock.settimeout(None)
            self.sock.connect(self.url, header=self.header)
            self._callback(self.on_open)

            if ping_interval:
                thread = threading.Thread(target=self._send_ping, args=(ping_interval,))
                thread.setDaemon(True)
                thread.start()

            while self.keep_running:
                try:
                    data = self.sock.recv()

                    if data is None or self.keep_running == False:
                        break

                    self._callback(self.on_message, data)
                except Exception as e:
                    if "timed out" not in e.args[0]:
                        raise e

        except Exception as e:
            self._callback(self.on_error, e)
        finally:
            if thread:
                self.keep_running = False

            self.sock.close()
            self._callback(self.on_close)
            self.sock = None

    def _callback(self, callback, *args):
        if callback:
            try:
                callback(self, *args)
            except Exception as e:
                logger.error(e)

                if logger.isEnabledFor(logging.DEBUG):
                    _, _, tb = sys.exc_info()
                    traceback.print_tb(tb)

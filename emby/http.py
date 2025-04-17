from _thread import allocate_lock
import base64
import os
import array
import struct
import hashlib
import json
import zlib
import ssl
import uuid
import _socket
import xbmc
import xbmcgui
from helper import utils, queue, artworkcache
from database import dbio
from core import common
from hooks import websocket


class HTTP:
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.Intros = []
        self.Queues = {"ASYNC": queue.Queue(), "DOWNLOAD": queue.Queue(), "QUEUEDREQUEST": queue.Queue()}
        self.Connection = {}
        self.Connecting = allocate_lock()
        self.RequestBusy = {"MAIN": allocate_lock(), "MAINFALLBACK": allocate_lock(), "REQUESTMAIN": allocate_lock(), "REQUESTMAINFALLBACK": allocate_lock(), "ASYNC": allocate_lock()}
        self.Running = False
        self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        try:
            self.SSLContext.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        except Exception as error:
            xbmc.log(f"EMBY.emby.http: Socket change options Error: {error}", 2) # LOGWARNING

        self.SSLContext.load_default_certs()
        self.Websocket = websocket.WebSocket(EmbyServer)
        self.WebsocketBuffer = b""
        self.AddrInfo = {}
        self.Response = {}
        utils.start_thread(self.queued_request, ())
        self.ThreadsRunning = {"ASYNC": False, "DOWNLOAD": False, "QUEUEDREQUEST": True, "PING": False, "WEBSOCKET": False}

        self.SSLContext.check_hostname = utils.sslverify
        if utils.sslverify:
            self.SSLContext.verify_mode = ssl.CERT_REQUIRED
        else:
            self.SSLContext.verify_mode = ssl.CERT_NONE

    def start(self):
        with self.Connecting:
            if not self.Running:
                self.Running = True
                xbmc.log("EMBY.emby.http: --->[ HTTP ]", 1) # LOGINFO

                if not self.ThreadsRunning["QUEUEDREQUEST"]:
                    self.ThreadsRunning["QUEUEDREQUEST"] = True
                    self.Queues["QUEUEDREQUEST"].clear()
                    utils.start_thread(self.queued_request, ())

                if not self.ThreadsRunning["ASYNC"]:
                    self.ThreadsRunning["ASYNC"] = True
                    self.Queues["ASYNC"].clear()
                    utils.start_thread(self.async_commands, ())

                if not self.ThreadsRunning["DOWNLOAD"]:
                    self.Queues["DOWNLOAD"].clear()
                    self.ThreadsRunning["DOWNLOAD"] = True
                    utils.start_thread(self.download_file, ())

                if not self.ThreadsRunning["PING"]:
                    self.ThreadsRunning["PING"] = True
                    utils.start_thread(self.Ping, ())

                if utils.websocketenabled:
                    if not self.Websocket.Running:
                        self.Websocket.MessageQueue.clear()
                        utils.start_thread(self.Websocket.Message, ())

                    if not self.ThreadsRunning["WEBSOCKET"]:
                        self.ThreadsRunning["WEBSOCKET"] = True
                        utils.start_thread(self.websocket_listen, ())

    def stop(self):
        with self.Connecting:
            if self.Running:
                self.Running = False
                xbmc.log("EMBY.emby.http: ---<[ HTTP ]", 1) # LOGINFO
                self.Queues["ASYNC"].put("QUIT")
                self.Queues["DOWNLOAD"].put("QUIT")
                self.Queues["QUEUEDREQUEST"].put("QUIT")

                if utils.websocketenabled:
                    self.Websocket.MessageQueue.put("QUIT")

                for ConnectionId in list(self.Connection.keys()):
                    self.socket_close(ConnectionId)

                # Verify all threads are stopped
                while self.ThreadsRunning["ASYNC"] or self.ThreadsRunning["DOWNLOAD"] or self.ThreadsRunning["QUEUEDREQUEST"] or self.ThreadsRunning["PING"] or self.ThreadsRunning["WEBSOCKET"] or self.Websocket.Running:
                    xbmc.log(f"EMBY.emby.http: Wait for thread termination: {self.ThreadsRunning} / {self.Websocket.Running}", 1) # LOGINFO
                    xbmc.sleep(100)

    def socket_addrinfo(self, ConnectionId, Hostname, Force):
        if Hostname in self.AddrInfo and not Force:
            return 0

        try:
            AddrInfo = _socket.getaddrinfo(Hostname, None)
            xbmc.log(f"EMBY.emby.http: AddrInfo: {AddrInfo}", 0) # LOGDEBUG
            self.AddrInfo[Hostname] = (AddrInfo[0][4][0], AddrInfo[0][0])
        except Exception as error:
            xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Wrong Hostname: {error}", 2) # LOGWARNING

            if ConnectionId == "MAIN":
                utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33678), time=utils.displayMessage, sound=False)

            if ConnectionId in self.Connection:
                del self.Connection[ConnectionId]

            return 609

        return 0

    def socket_del(self, ConnectionId):
        if ConnectionId in self.Connection:
            del self.Connection[ConnectionId]

    def socket_open(self, ConnectionString, ConnectionId, CloseConnection):
        SSLIssueCounter = 0

        while True:
            NewHeader = False

            if ConnectionId not in self.Connection:
                self.Connection[ConnectionId] = {}

            if "ConnectionString" not in self.Connection[ConnectionId]:
                self.Connection[ConnectionId]["ConnectionString"] = ConnectionString
                NewHeader = True
            else:
                if self.Connection[ConnectionId]["ConnectionString"] != ConnectionString:
                    self.Connection[ConnectionId]["ConnectionString"] = ConnectionString
                    NewHeader = True

            if NewHeader:
                try:
                    Scheme, self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"], self.Connection[ConnectionId]["SubUrl"] = utils.get_url_info(ConnectionString)
                except Exception as error:
                    xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Wrong ConnectionString: {ConnectionString} / {error}", 2) # LOGWARNING

                    if ConnectionId == "MAIN":
                        utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33678), time=utils.displayMessage, sound=False)

                    self.socket_del(ConnectionId)
                    return 611

                self.Connection[ConnectionId]["SSL"] = bool(Scheme == "https")

                if CloseConnection:
                    ConnectionMode = 'close'
                else:
                    ConnectionMode = 'keep-alive'

                self.Connection[ConnectionId]["RequestHeader"] = {"Host": f"{self.Connection[ConnectionId]['Hostname']}:{self.Connection[ConnectionId]['Port']}", 'Content-type': 'application/json; charset=utf-8', 'Accept-Charset': 'utf-8', 'Accept-encoding': 'gzip', 'User-Agent': f"{utils.addon_name}/{utils.addon_version}", 'Connection': ConnectionMode, 'Authorization': f'Emby Client="{utils.addon_name}", Device="{utils.device_name}", DeviceId="{self.EmbyServer.ServerData["DeviceId"]}", Version="{utils.addon_version}"'}

                if ConnectionId == "DOWNLOAD":
                    self.Connection[ConnectionId]["RequestHeader"]['Accept-encoding'] = "identity"

                StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], False)

                if StatusCodeSocket:
                    self.socket_del(ConnectionId)
                    return StatusCodeSocket

            RetryCounter = 0

            while True:
                try:
                    self.Connection[ConnectionId]["Socket"] = _socket.socket(self.AddrInfo[self.Connection[ConnectionId]["Hostname"]][1], _socket.SOCK_STREAM)
                    self.Connection[ConnectionId]["Socket"].setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
                    self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout
                    self.Connection[ConnectionId]["Socket"].connect((self.AddrInfo[self.Connection[ConnectionId]["Hostname"]][0], self.Connection[ConnectionId]['Port']))
                    break
                except TimeoutError:
                    if ConnectionId not in self.Connection:
                        xbmc.log(f"EMBY.emby.http: TimeoutError: No Connection {ConnectionId}", 2) # LOGWARNING
                        return 699

                    RetryCounter += 1

                    if RetryCounter == 1:
                        StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], True)

                        if StatusCodeSocket:
                            self.socket_del(ConnectionId)
                            return StatusCodeSocket

                    if RetryCounter <= 10:
                        continue

                    xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Timeout", 2) # LOGWARNING
                    self.socket_del(ConnectionId)
                    return 606
                except ConnectionRefusedError:
                    if ConnectionId not in self.Connection:
                        xbmc.log(f"EMBY.emby.http: ConnectionRefusedError: No {ConnectionId}", 2) # LOGWARNING
                        return 699

                    RetryCounter += 1

                    if RetryCounter == 1:
                        StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], True)

                        if StatusCodeSocket:
                            self.socket_del(ConnectionId)
                            return StatusCodeSocket

                    if RetryCounter == 1:
                        continue

                    self.socket_del(ConnectionId)
                    xbmc.log(f"EMBY.emby.http: [ ServerUnreachable ] {ConnectionId}", 2) # LOGWARNING
                    xbmc.log(f"EMBY.emby.http: [ ServerUnreachable ] {ConnectionString}", 0) # LOGDEBUG
                    return 607
                except Exception as error:
                    if ConnectionId not in self.Connection:
                        xbmc.log(f"EMBY.emby.http: No Connection {ConnectionId}", 2) # LOGWARNING
                        return 699

                    RetryCounter += 1

                    if RetryCounter == 1:
                        StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], True)

                        if StatusCodeSocket:
                            self.socket_del(ConnectionId)
                            return StatusCodeSocket

                    if str(error).find("timed out") != -1: # workaround when TimeoutError not raised
                        if RetryCounter <= 10:
                            continue

                        xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Timeout", 2) # LOGWARNING
                        self.socket_del(ConnectionId)
                        return 606

                    if RetryCounter == 1:
                        continue

                    if str(error).lower().find("errno 22") != -1 or str(error).lower().find("invalid argument") != -1: # [Errno 22] Invalid argument
                        self.socket_del(ConnectionId)
                        xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Invalid argument", 2) # LOGWARNING

                        if ConnectionId == "MAIN":
                            utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33679), time=utils.displayMessage, sound=False)

                        return 610

                    xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Undefined error: {error} / Type: {type(error)}", 2) # LOGWARNING
                    self.socket_del(ConnectionId)
                    return 699

            if ConnectionId in self.Connection:
                if self.Connection[ConnectionId]["SSL"]:
                    RetryCounter = 0

                    while True:
                        try:
                            self.Connection[ConnectionId]["Socket"] = self.SSLContext.wrap_socket(self.Connection[ConnectionId]["Socket"], do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=self.Connection[ConnectionId]["Hostname"])
                            self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout
                            SSLIssueCounter = 0
                            break
                        except ssl.CertificateError:
                            self.socket_del(ConnectionId)
                            xbmc.log("EMBY.emby.http: socket_open ssl certificate error", 3) # LOGERROR

                            if ConnectionId == "MAIN":
                                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33428), time=utils.displayMessage)

                            return 608
                        except Exception as error:
                            RetryCounter += 1

                            if str(error).find("timed out") != -1: # workaround when TimeoutError not raised
                                if RetryCounter <= 10:
                                    continue

                                xbmc.log(f"EMBY.emby.http: socket_open ssl {ConnectionId}: Timeout", 2) # LOGWARNING
                                self.socket_del(ConnectionId)
                                return 606

                            SSLIssueCounter += 1
                            xbmc.log(f"EMBY.emby.http: socket_open ssl undefined error {SSLIssueCounter}: {error}", 2) # LOGWARNING
                            self.socket_del(ConnectionId)
                            break
            else:
                xbmc.log(f"EMBY.emby.http: socket_open ssl: No ConnectionId {ConnectionId}", 2) # LOGWARNING
                self.socket_del(ConnectionId)
                return 699

            if SSLIssueCounter:
                if SSLIssueCounter < 49:
                    if utils.sleep(0.1):
                        return 699

                    continue

                return 699

            xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} opened", 0) # LOGDEBUG
            return 0

    def socket_close(self, ConnectionId):
        if ConnectionId in self.Connection:
            # Close sessions
            if ConnectionId == "WEBSOCKET": # close websocket
                try:
                    self.Connection[ConnectionId]["Socket"].settimeout(1) # set timeout
                    self.websocket_send(b"", 0x8)  # Close
                except Exception as error:
                    xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} send close error 1: {error}", 2) # LOGWARNING
            elif ConnectionId in ("MAIN", "MAINFALLBACK", "ASYNC"): # send final ping to change tcp session from keep-alive to close
                try:
                    self.Connection[ConnectionId]["Socket"].settimeout(1) # set timeout
                    self.Connection[ConnectionId]["Socket"].send(f'POST {self.Connection[ConnectionId]["SubUrl"]}System/Ping HTTP/1.1\r\nHost: {self.Connection[ConnectionId]["Hostname"]}:{self.Connection[ConnectionId]["Port"]}\r\nContent-type: application/json; charset=utf-8\r\nAccept-Charset: utf-8\r\nAccept-encoding: gzip\r\nUser-Agent: {utils.addon_name}/{utils.addon_version}\r\nConnection: close\r\nAuthorization: Emby Client="{utils.addon_name}", Device="{utils.device_name}", DeviceId="{self.EmbyServer.ServerData["DeviceId"]}", Version="{utils.addon_version}"\r\nContent-Length: 0\r\n\r\n'.encode("utf-8"))
                except Exception as error:
                    xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} send close error 2: {error}", 2) # LOGWARNING

            try:
                self.Connection[ConnectionId]["Socket"].close()
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} close error: {error}", 2) # LOGWARNING

            try:
                del self.Connection[ConnectionId]
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} reset error: {error}", 2) # LOGWARNING

        else:
            xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} already closed", 0) # LOGDEBUG
            return

        xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} closed", 0) # LOGDEBUG

    def socket_io(self, Request, ConnectionId, Timeout):
        IncomingData = b""
        StatusCode = 0
        TimeoutCounter = 0
        BytesSend = 0
        BytesSendTotal = len(Request)
        TimeoutLoops = Timeout / 3 # settimeout = 3 -> calculate seconds

        while True:
            try:
                self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout

                if Request:
                    while BytesSend < BytesSendTotal:
                        BytesSend += self.Connection[ConnectionId]["Socket"].send(Request[BytesSend:])
                else:
                    IncomingData = self.Connection[ConnectionId]["Socket"].recv(1048576)

                    if not IncomingData: # No Data received -> Socket might be closed by Emby server
                        xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Empty data", 0) # LOGDEBUG
                        StatusCode = 600

                break
            except TimeoutError:
                if not TimeoutLoops or (ConnectionId != "MAIN" and self.RequestBusy["MAIN"].locked()): # Websocket or binary -> wait longer for e.g. images. MAIN queries could block IO
                    continue

                TimeoutCounter += 1

                if TimeoutCounter < TimeoutLoops:
                    continue

                xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Timeout", 2) # LOGWARNING
                StatusCode = 603
                break
            except BrokenPipeError:
                xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Pipe error", 2) # LOGWARNING
                StatusCode = 605
                break
            except Exception as error:
                if str(error).find("timed out") != -1: # workaround when TimeoutError not raised
                    if not TimeoutLoops or (ConnectionId != "MAIN" and self.RequestBusy["MAIN"].locked()): # Websocket or binary -> wait longer for e.g. images. MAIN queries could block IO
                        continue

                    TimeoutCounter += 1

                    if TimeoutCounter <= TimeoutLoops:
                        continue

                    xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Timeout (workaround)", 2) # LOGWARNING
                    StatusCode = 603
                    break

                xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Undefined error {error} / Type: {type(error)}", 3) # LOGERROR
                StatusCode = 699
                break

        return StatusCode, IncomingData

    def socket_request(self, Method, Handler, Params, Binary, TimeoutSend, TimeoutRecv, ConnectionId, DownloadPath, DownloadFileSize, DownloadName):
        if ConnectionId not in self.Connection:
            return 601, {}, {}

        PayloadTotal = ()
        PayloadTotalLength = 0
        StatusCode = 612
        IncomingData = b""
        IncomingDataHeader = {}
        isGzip = False
        isDeflate = False

        # Prepare HTTP Header
        HeaderString = ""

        for Key, Values in list(self.Connection[ConnectionId]['RequestHeader'].items()):
            HeaderString += f"{Key}: {Values}\r\n"

        # Prepare HTTP Payload
        if Method == "GET":
            ParamsString = ""

            for Query, Param in list(Params.items()):
                if Param not in ([], None):
                    ParamsString += f"{Query}={Param}&"

            if ParamsString:
                ParamsString = f"?{ParamsString[:-1]}"

            Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler}{ParamsString} HTTP/1.1\r\n{HeaderString}Content-Length: 0\r\n\r\n"
            StatusCodeSocket, _ = self.socket_io(Request.encode("utf-8"), ConnectionId, TimeoutSend)
        else:
            if Params:
                ParamsString = json.dumps(Params)
            else:
                ParamsString = ""

            Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler} HTTP/1.1\r\n{HeaderString}Content-Length: {len(ParamsString)}\r\n\r\n{ParamsString}"
            StatusCodeSocket, _ = self.socket_io(Request.encode("utf-8"), ConnectionId, TimeoutSend)

        if StatusCodeSocket:
            return StatusCodeSocket, {}, ""

        if DownloadPath:
            ProgressBar = xbmcgui.DialogProgressBG()
            ProgressBar.create("Download", DownloadName)
            ProgressBarTotal = DownloadFileSize / 100
            OutFile = open(DownloadPath, 'wb')
        else:
            ProgressBar = None
            ProgressBarTotal = 0
            OutFile = None

        while True:
            StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)
            IncomingData += PayloadRecv

            if StatusCodeSocket or utils.SystemShutdown:
                closeDownload(OutFile, ProgressBar)
                return StatusCodeSocket, {}, ""

            # Check if header is fully loaded
            if b'\r\n\r\n' not in IncomingData:
                xbmc.log("EMBY.emby.http: Incomplete header", 0) # LOGDEBUG
                continue

            IncomingData = IncomingData.split(b'\r\n\r\n', 1) # Split header/payload

            try:
                IncomingMetaData = IncomingData[0].decode("utf-8").split("\r\n")
                StatusCode = int(IncomingMetaData[0].split(" ")[1])
            except Exception as error: # Can happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Info: {error}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Binary: {Binary}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Request: {Request}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: IncomingData: {IncomingData}", 3) # LOGERROR
                return 612, {}, ""

            IncomingDataHeaderArray = IncomingMetaData[1:]
            IncomingDataHeader = {}

            for IncomingDataHeaderArrayData in IncomingDataHeaderArray:
                Temp = IncomingDataHeaderArrayData.split(": ")
                IncomingDataHeader[Temp[0].lower()] = Temp[1]

            # no trailers allowed due to RFC
            if StatusCode in (304, 101, 204) or Method == "HEAD":
                closeDownload(OutFile, ProgressBar)
                return StatusCode, IncomingDataHeader, ""

            # Decompress flags
            isGzip = IncomingDataHeader.get("content-encoding", "") == "gzip"
            isDeflate = IncomingDataHeader.get("content-encoding", "") == "deflate"

            # Recv payload
            try:
                if IncomingDataHeader.get('transfer-encoding', "") == "chunked":
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByChunks(PayloadTotal, PayloadTotalLength, IncomingData[1], ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBar, ProgressBarTotal)
                else:
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByFrames(PayloadTotal, PayloadTotalLength, IncomingData[1], ConnectionId, TimeoutRecv, int(IncomingDataHeader.get("content-length", 0)), DownloadName, OutFile, ProgressBar, ProgressBarTotal)

                if StatusCodeSocket:
                    closeDownload(OutFile, ProgressBar)
                    return 601, {}, ""

                # request additional data
                if StatusCode == 206: # partial content
                    ContentSize = int(IncomingDataHeader['content-range'].split("/")[1])

                    if ContentSize == len(PayloadTotal):
                        StatusCode = 200
                        break

                    xbmc.log(f"EMBY.emby.http: Partial content {ConnectionId}", 1) # LOGINFO

                    if Method == "GET":
                        StatusCodeSocket, _ = self.socket_io(f"{Method} /{Handler}{ParamsString} HTTP/1.1\r\n{HeaderString}Range: bytes={PayloadTotalLength}-\r\nContent-Length: 0\r\n\r\n".encode("utf-8"), ConnectionId, TimeoutSend)
                    else:
                        StatusCodeSocket, _ = self.socket_io(f"{Method} /{Handler} HTTP/1.1\r\n{HeaderString}Content-Length: {len(ParamsString)}\r\n\r\n{ParamsString}".encode("utf-8"), ConnectionId, TimeoutSend)

                    if StatusCodeSocket:
                        closeDownload(OutFile, ProgressBar)
                        return 601, {}, ""

                    continue

                break
            except Exception as error: # Could happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Undefined error {error}: IncomingDataHeader: {IncomingDataHeader}", 3) # LOGERROR
                return 612, {}, ""

        closeDownload(OutFile, ProgressBar)
        PayloadTotal = b''.join(PayloadTotal)

        # Decompress data
        try:
            if isDeflate:
                PayloadTotal = zlib.decompress(PayloadTotal, -zlib.MAX_WBITS)
            elif isGzip:
                PayloadTotal = zlib.decompress(PayloadTotal, zlib.MAX_WBITS|32)
        except Exception as error: # could happen on server overload
            xbmc.log(f"EMBY.emby.http: Decompress issue {ConnectionId}: {IncomingDataHeader} error: {error}", 3) # LOGERROR
            return 612, {}, ""

        if Binary:
            return StatusCode, IncomingDataHeader, PayloadTotal

        isJSON = "json" in IncomingDataHeader.get("content-type", "").lower()

        if isJSON:
            try:
                return StatusCode, IncomingDataHeader, json.loads(PayloadTotal)
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Invalid json content {ConnectionId}: {IncomingDataHeader} error: {error} payload: {PayloadTotal}", 3) # LOGERROR
                return 612, {}, ""
        else:
            try:
                return StatusCode, IncomingDataHeader, PayloadTotal.decode("UTF-8")
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Invalid text content {ConnectionId}: {IncomingDataHeader} error: {error} payload: {PayloadTotal}", 3) # LOGERROR
                return 612, {}, ""

    def download_file(self):
        xbmc.log("EMBY.emby.http: THREAD: --->[ file download ]", 0) # LOGDEBUG

        while True:
            Command = self.Queues["DOWNLOAD"].get() # EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId

            if Command == "QUIT":
                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} ] shutdown 1", 0) # LOGDEBUG
                utils.delFile(Command[3])
                self.socket_close("DOWNLOAD")
                self.ThreadsRunning["DOWNLOAD"] = False
                return

            # check if free space below 2GB
            if utils.getFreeSpace(Command[2]) < (2097152 + Command[4] / 1024):
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=utils.displayMessage, sound=True)
                xbmc.log("EMBY.emby.http: THREAD: ---<[ file download ] terminated by filesize", 2) # LOGWARNING
                self.socket_close("DOWNLOAD")
                self.ThreadsRunning["DOWNLOAD"] = False
                return

            while True:
                if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "DOWNLOAD", True):
                    if utils.sleep(10):
                        xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} shutdown ]", 0) # LOGDEBUG
                        self.ThreadsRunning["DOWNLOAD"] = False
                        return

                    continue

                self.update_header("DOWNLOAD")
                StatusCode, _, _ = self.socket_request("GET", f"Items/{Command[0]}/Download", {}, True, 12, 300, "DOWNLOAD", Command[3], Command[4], Command[5])

                if StatusCode == 601: # quit
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} ] shutdown 2", 0) # LOGDEBUG
                    utils.delFile(Command[3])
                    self.socket_close("DOWNLOAD")
                    self.ThreadsRunning["DOWNLOAD"] = False
                    return

                if StatusCode in (600, 602, 603, 605, 612):
                    xbmc.log(f"EMBY.emby.http: Download retry {StatusCode}", 2) # LOGWARNING
                    utils.delFile(Command[3])
                    self.socket_close("DOWNLOAD")
                    continue

                try:
                    if StatusCode != 200:
                        utils.delFile(Command[3])
                    else:
                        if Command[9]: # KodiId
                            SQLs = {}
                            dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], "download_item", SQLs)
                            SQLs['emby'].add_DownloadItem(Command[0], Command[7], Command[8], Command[9], Command[6])
                            dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], "download_item", SQLs)
                            dbio.DBOpenRW("video", "download_item_replace", SQLs)
                            Artworks = ()
                            ArtworksData = SQLs['video'].get_artworks(Command[9], Command[6])

                            for ArtworkData in ArtworksData:
                                if ArtworkData[3] in ("poster", "thumb", "landscape"):
                                    UrlMod = ArtworkData[4].split("|")
                                    UrlMod = f"{UrlMod[0].replace('-download', '')}-download|redirect-limit=1000"
                                    SQLs['video'].update_artwork(ArtworkData[0], UrlMod)
                                    Artworks += ((UrlMod,),)

                            SQLs['video'].update_Name(Command[9], Command[6], True)
                            SQLs['video'].replace_Path_ContentItem(Command[9], Command[6], Command[2])

                            if Command[6] == "episode":
                                KodiPathId = SQLs['video'].get_add_path(Command[2], None, Command[1])
                                Artworks = SQLs['video'].set_Subcontent_download_tags(Command[9], True)

                                if Artworks:
                                    artworkcache.CacheAllEntries(Artworks, None)
                            elif Command[6] == "movie":
                                KodiPathId = SQLs['video'].get_add_path(Command[2], "movie", None)
                            elif Command[6] == "musicvideo":
                                KodiPathId = SQLs['video'].get_add_path(Command[2], "musicvideos", None)
                            else:
                                KodiPathId = None
                                xbmc.log(f"EMBY.emby.http: Download invalid: KodiPathId: {Command[1]['Path']} / {Command[6]}", 2) # LOGWARNING

                            if KodiPathId:
                                SQLs['video'].replace_PathId(Command[8], KodiPathId)

                            dbio.DBCloseRW("video", "download_item_replace", SQLs)
                            artworkcache.CacheAllEntries(Artworks, None)

                    if self.Queues["DOWNLOAD"].isEmpty():
                        utils.refresh_widgets(True)
                except Exception as error:
                    xbmc.log(f"EMBY.emby.http: Download Emby server did not respond: error: {error}", 2) # LOGWARNING

                break

    def request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, BusyFunction=None, ConnectionId=""):
        if not ConnectionId:
            if CloseConnection:
                ConnectionId = str(uuid.uuid4())
            elif self.RequestBusy["MAIN"].locked():
                if self.RequestBusy["MAINFALLBACK"].locked():
                    ConnectionId = str(uuid.uuid4())
                    CloseConnection = True
                else:
                    ConnectionId = "MAINFALLBACK"
                    self.RequestBusy["MAINFALLBACK"].acquire()
            else:
                ConnectionId = "MAIN"
                self.RequestBusy["MAIN"].acquire()
        else:
            self.RequestBusy[ConnectionId].acquire()

        RequestId = f"REQUEST{ConnectionId}"

       # Simple request
        if CloseConnection or not BusyFunction:
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)
            Data = self.Response[RequestId]
            del self.Response[RequestId]

            if ConnectionId in ("MAIN", "MAINFALLBACK"):
                self.RequestBusy[ConnectionId].release()

            return Data

        # Check conditions while waiting for data -> BusyFunction
        self.Response[RequestId] = False

        if RequestId not in ("REQUESTMAIN", "REQUESTMAINFALLBACK"):
            self.RequestBusy[RequestId] = allocate_lock()

        self.Queues["QUEUEDREQUEST"].put(((Method, Handler, Params, RequestHeader, Binary, ConnectionString, False, ConnectionId, RequestId),))

        while True:
            self.RequestBusy[RequestId].acquire(blocking=True, timeout=0.5)
            Data = self.Response[RequestId]

            # Data received, request finished
            if Data:
                Data = self.Response[RequestId]
                del self.Response[RequestId]

                if ConnectionId in ("MAIN", "MAINFALLBACK"):
                    self.RequestBusy[ConnectionId].release()
                else:
                    del self.RequestBusy[RequestId]

                return Data

            # trigger busy function: Interrupt query if necessary, e.g. Kodi shutdown or simply wait till BusyFunction continues
            if not BusyFunction["Object"](*BusyFunction["Params"]):
                del self.Response[RequestId]

                if RequestId in self.RequestBusy and self.RequestBusy[RequestId].locked():
                    self.RequestBusy[RequestId].release()

                if ConnectionId in ("MAIN", "MAINFALLBACK"):
                    self.RequestBusy[ConnectionId].release()
                else:
                    del self.RequestBusy[RequestId]

                return noData(601, {}, Binary)

    def queued_request(self):
        xbmc.log(f"EMBY.emby.http: THREAD: --->[ Queued request {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG

        while True:
            Incoming = self.Queues["QUEUEDREQUEST"].get() # EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId

            if Incoming == "QUIT":
                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Queued request {self.EmbyServer.ServerData['ServerId']} ] shutdown 1", 0) # LOGDEBUG

                # Send empty data to all pending queued items
                for RequestId in self.Response:
                    self.Response[RequestId] = noData(601, {}, False)

                self.ThreadsRunning["QUEUEDREQUEST"] = False
                return

            Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId = Incoming
            xbmc.log(f"EMBY.emby.http: [ http ] Method: {Method} / Handler: {Handler} / Params: {Params} / Binary: {Binary} / ConnectionString: {ConnectionString} / CloseConnection: {CloseConnection} / RequestHeader: {RequestHeader}", 0) # LOGDEBUG
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)

    def send_request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId):
        if not ConnectionString:
            ConnectionString = self.EmbyServer.ServerData['ServerUrl']

        # Connectionstring changed
        if not CloseConnection and ConnectionId in self.Connection and ConnectionString.find(self.Connection[ConnectionId]['Hostname']) == -1:
            self.socket_close(ConnectionId)

        while True:
            StatusCode = 0

            # Shutdown
            if utils.SystemShutdown:
                self.socket_close(ConnectionId)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Request {self.EmbyServer.ServerData['ServerId']} ] shutdown 2", 0) # LOGDEBUG
                break

            # open socket
            if ConnectionId not in self.Connection:
                StatusCode = self.socket_open(ConnectionString, ConnectionId, CloseConnection)

                if StatusCode:
                    if StatusCode not in (608, 609, 610, 611): # wrong Emby server address or SSL issue
                        self.EmbyServer.ServerReconnect(True)

                    self.Response[RequestId] = noData(StatusCode, {}, Binary)
                    break

            # Update Header information
            if RequestHeader:
                self.Connection[ConnectionId]["RequestHeader"] = {"Host": f"{self.Connection[ConnectionId]['Hostname']}:{self.Connection[ConnectionId]['Port']}", 'Accept': "application/json", 'Accept-Charset': "utf-8", 'X-Application': f"{utils.addon_name}/{utils.addon_version}", 'Content-type': 'application/json'}
                self.Connection[ConnectionId]["RequestHeader"].update(RequestHeader)
            else:
                self.update_header(ConnectionId)

            # Request data with different timeout settings
            if Handler == "System/Ping":
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 6, ConnectionId, "", 0, "")
            elif "Subtitles" in Handler:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 30, ConnectionId, "", 0, "")
            else:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 1200, ConnectionId, "", 0, "")

            # Redirects
            if StatusCode in (301, 302, 307, 308):
                self.socket_close(ConnectionId)
                Location = Header.get("location", "")
                Scheme, Hostname, Port, _ = utils.get_url_info(Location)
                ConnectionString = f"{Scheme}://{Hostname}:{Port}"
                ConnectionStringNoPort = f"{Scheme}://{Hostname}"
                Handler = Location.replace(ConnectionString, "").replace(ConnectionStringNoPort, "")

                if Handler.startswith("/"):
                    Handler = Handler[1:]

                if ConnectionId == "MAIN" and StatusCode in (301, 308):
                    self.EmbyServer.ServerData['ServerUrl'] = ConnectionString

                continue

            if CloseConnection:
                self.socket_close(ConnectionId)

            if StatusCode == 200: # OK
                self.Response[RequestId] = (StatusCode, Header, Payload)
                break

            if StatusCode == 204: # OK, no data
                self.Response[RequestId] = (StatusCode, Header, Payload)
                break

            if StatusCode == 401: # Unauthorized
                xbmc.log(f"EMBY.emby.http: Request unauthorized {StatusCode} / {ConnectionId}", 3) # LOGERROR
                Text = f"{utils.Translate(33147)}\n{str(Payload)}"
                utils.Dialog.notification(heading=utils.addon_name, message=Text, time=utils.displayMessage)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 403: # Access denied
                xbmc.log(f"EMBY.emby.http: Request unauthorized {StatusCode} / {ConnectionId}", 3) # LOGERROR
                Text = f"{utils.Translate(33696)}\n{str(Payload)}"
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33696), time=utils.displayMessage)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode in (600, 605, 612): # no data received, broken pipes, undefined error
                xbmc.log(f"EMBY.emby.http: Request retry {StatusCode} / {ConnectionId}", 2) # LOGWARNING
                self.socket_close(ConnectionId)
                continue

            if StatusCode in (602, 603): # timeouts
                xbmc.log(f"EMBY.emby.http: Request timeout {StatusCode} / {ConnectionId}", 2) # LOGWARNING
                self.socket_close(ConnectionId)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 601: # quit
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 503: # Service Unavailable, usually happens when server is (re)booting
                xbmc.log(f"EMBY.emby.http: Service Unavailable {StatusCode} / {ConnectionId} / {Handler} / {Params}", 3) # LOGERROR
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                self.EmbyServer.ServerReconnect(True)
                break

            if StatusCode == 699: # Connection is closed -> usually it's a Kodi shutdown or forced server disconnect
                xbmc.log(f"EMBY.emby.http: Connection is closed {StatusCode} / {ConnectionId} / {Handler} / {Params}", 3) # LOGERROR
                self.socket_close(ConnectionId)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            xbmc.log(f"EMBY.emby.http: [ Statuscode ] {StatusCode}", 3) # LOGERROR
            xbmc.log(f"EMBY.emby.http: [ Statuscode ] {Payload}", 0) # LOGDEBUG
            self.Response[RequestId] = noData(StatusCode, {}, Binary)
            break

        if RequestId in self.RequestBusy and self.RequestBusy[RequestId].locked():
            self.RequestBusy[RequestId].release()

    def websocket_listen(self):
        xbmc.log(f"EMBY.emby.http: THREAD: --->[ Websocket {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG
        WarningDisplayed = False

        while self.ThreadsRunning["WEBSOCKET"] and self.Running:
            xbmc.log("EMBY.emby.http: Websocket connecting", 1) # LOGINFO

            if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "WEBSOCKET", False):
                if utils.sleep(10):
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} shutdown 1 ]", 0) # LOGDEBUG
                    self.ThreadsRunning["WEBSOCKET"] = False
                    return

                continue

            uid = uuid.uuid4()
            EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')
            self.Connection["WEBSOCKET"]["RequestHeader"].update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": EncodingKey, "Sec-WebSocket-Version": "13"})
            StatusCode, Header, _ = self.socket_request("GET", f"embywebsocket?api_key={self.EmbyServer.ServerData['AccessToken']}&deviceId={self.EmbyServer.ServerData['DeviceId']}", {}, True, 12, 30, "WEBSOCKET", "", 0, "")

            if StatusCode == 601: # quit
                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} quit ]", 0) # LOGDEBUG
                self.ThreadsRunning["WEBSOCKET"] = False
                return

            if StatusCode != 101:
                self.socket_close("WEBSOCKET")

                if utils.sleep(1):
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 2 ]", 0) # LOGDEBUG
                    self.ThreadsRunning["WEBSOCKET"] = False
                    return

            result = Header.get("sec-websocket-accept", "")

            if not result:
                xbmc.log(f"EMBY.emby.http: Websocket {self.EmbyServer.ServerData['ServerId']} sec-websocket-accept not found: Header {Header}", 0) # LOGDEBUG

                if not WarningDisplayed:
                    utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33235), sound=True, time=utils.displayMessage)
                    WarningDisplayed = True

                if utils.sleep(1):
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 3 ]", 0) # LOGDEBUG
                    self.ThreadsRunning["WEBSOCKET"] = False
                    return

                continue

            WarningDisplayed = False
            value = f"{EncodingKey}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("utf-8")
            hashed = base64.b64encode(hashlib.sha1(value).digest()).strip().lower().decode('utf-8')

            if hashed != result.lower():
                xbmc.log(f"EMBY.emby.http: Websocket {self.EmbyServer.ServerData['ServerId']} wrong hash", 0) # LOGDEBUG

                if utils.sleep(1):
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 4 ]", 0) # LOGDEBUG
                    self.ThreadsRunning["WEBSOCKET"] = False
                    return

                continue

            if not self.websocket_send('{"MessageType": "ScheduledTasksInfoStart", "Data": "0,1500"}', 0x1): # subscribe notifications
                continue

            if "WEBSOCKET" not in self.Connection:
                continue

            self.Connection["WEBSOCKET"]["Socket"].settimeout(3)
            self.WebsocketBuffer = b""
            ConnectionClosed = False
            FrameMask = ""
            payload = b''

            while self.ThreadsRunning["WEBSOCKET"] and self.Running:
                if not self.Running:
                    xbmc.log("EMBY.emby.http: Websocket receive stopped", 1) # LOGINFO
                    ConnectionClosed = True
                    break

                StatusCodeSocket, PayloadRecv = self.socket_io("", "WEBSOCKET", 6)

                if StatusCodeSocket:
                    xbmc.log(f"EMBY.emby.http: Websocket receive interupted {StatusCodeSocket}", 1) # LOGINFO
                    break

                self.WebsocketBuffer += PayloadRecv

                while True:
                    if len(self.WebsocketBuffer) < 2:
                        break

                    FrameHeader = self.WebsocketBuffer[:2]
                    Curser = 2
                    fin = FrameHeader[0] >> 7 & 1

                    if not fin:
                        xbmc.log("EMBY.emby.http: Websocket not fin", 0) # LOGDEBUG
                        break

                    opcode = FrameHeader[0] & 0xf
                    has_mask = FrameHeader[1] >> 7 & 1

                    # Frame length
                    try:
                        FrameLength = FrameHeader[1] & 0x7f

                        if FrameLength == 0x7e:
                            length_data = self.WebsocketBuffer[Curser:Curser + 2]
                            Curser += 2
                            FrameLength = struct.unpack("!H", length_data)[0]
                        elif FrameLength == 0x7f:
                            length_data = self.WebsocketBuffer[Curser:Curser + 8]
                            Curser += 8
                            FrameLength = struct.unpack("!Q", length_data)[0]
                    except Exception as error:
                        xbmc.log(f"EMBY.emby.http: Websocket frame lenght error: {error}", 2) # LOGWARNING
                        break

                    # Mask
                    if has_mask:
                        FrameMask = self.WebsocketBuffer[Curser:Curser + 4]
                        Curser += 4

                    # Payload
                    if FrameLength:
                        FrameLengthEndPos = Curser + FrameLength

                        if len(self.WebsocketBuffer) < FrameLengthEndPos: # Incomplete Frame
                            xbmc.log("EMBY.emby.http: Websocket incomplete frame", 0) # LOGDEBUG
                            break

                        payload = self.WebsocketBuffer[Curser:FrameLengthEndPos]
                        Curser = FrameLengthEndPos

                    if has_mask:
                        payload = maskData(FrameMask, payload)

                    if opcode in (0x2, 0x1, 0x0): # 1 textframe, 2 binaryframe, 0 continueframe
                        if fin and payload:
                            self.Websocket.MessageQueue.put(payload)
                    elif opcode == 0x8: # Connection close
                        xbmc.log("EMBY.emby.http: Websocket connection closed", 0) # LOGDEBUG
                        ConnectionClosed = True
                        break
                    elif opcode == 0x9: # Ping
                        if not self.websocket_send(payload, 0xa):  # Pong:
                            break
                    elif opcode == 0xa: # Pong
                        xbmc.log("EMBY.emby.http: Websocket Pong received", 0) # LOGDEBUG
                    else:
                        xbmc.log(f"EMBY.hooks.websocket: Uncovered Opcode: {opcode} / Payload: {payload} / FrameHeader: {FrameHeader} / FrameLength: {FrameLength} / FrameMask: {FrameMask}", 3) # LOGERROR

                    self.WebsocketBuffer = self.WebsocketBuffer[Curser:]
                    continue

            if ConnectionClosed:
                break

        self.ThreadsRunning["WEBSOCKET"] = False
        xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG

    def websocket_send(self, payload, opcode):
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
        StatusCodeSocket, _ = self.socket_io(data, "WEBSOCKET", 12)

        if StatusCodeSocket:
            xbmc.log(f"EMBY.emby.http: Websocket send interupted {StatusCodeSocket}", 1) # LOGINFO
            return False

        return True

    def update_header(self, ConnectionId):
        if 'X-Emby-Token' not in self.Connection[ConnectionId]["RequestHeader"] and self.EmbyServer.ServerData['AccessToken'] and self.EmbyServer.ServerData['UserId']:
            self.Connection[ConnectionId]["RequestHeader"].update({'Authorization': f'{self.Connection[ConnectionId]["RequestHeader"]["Authorization"]}, Emby UserId="{self.EmbyServer.ServerData["UserId"]}"', 'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']})

    # No return values are expected, usually also lower priority
    def async_commands(self):
        xbmc.log("EMBY.emby.http: THREAD: --->[ Async ]", 0) # LOGDEBUG

        # Process commands
        while self.Running:
            Command = self.Queues["ASYNC"].get() # (Method, URL-handler, Parameters, Priority)

            if Command == "QUIT":
                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Async {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG
                self.socket_close("ASYNC")
                self.ThreadsRunning["ASYNC"] = False
                return

            with self.RequestBusy["ASYNC"]:
                while self.Running:
                    if "ASYNC" not in self.Connection:
                        if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "ASYNC", False):
                            if utils.sleep(1):
                                xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Async {self.EmbyServer.ServerData['ServerId']} shutdown ]", 0) # LOGDEBUG
                                self.ThreadsRunning["ASYNC"] = False
                                return

                            continue

                    self.update_header("ASYNC")
                    StatusCode, _, _ = self.socket_request(Command[0], Command[1], Command[2], Command[3], 3, 3, "ASYNC", "", 0, "")

                    if StatusCode == 601: # quit
                        self.socket_close("ASYNC")
                        xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Async {self.EmbyServer.ServerData['ServerId']} ] shutdown 2", 0) # LOGDEBUG
                        self.ThreadsRunning["ASYNC"] = False
                        return

                    if StatusCode in (600, 605, 612):
                        xbmc.log(f"EMBY.emby.http: Async retry {StatusCode}", 2) # LOGWARNING
                        self.socket_close("ASYNC")
                        continue

                    if StatusCode in (602, 603):
                        xbmc.log(f"EMBY.emby.http: Async timeout {StatusCode}", 2) # LOGWARNING -> Emby server is sometimes not responsive, as no response is expected, skip it
                        self.socket_close("ASYNC")

                    break

        self.socket_close("ASYNC")
        self.ThreadsRunning["ASYNC"] = False
        xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Async {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG

    # Ping server -> keep http sessions open (timer)
    def Ping(self):
        xbmc.log(f"EMBY.emby.http: THREAD: --->[ Ping {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG
        self.ThreadsRunning["PING"] = True

        while True:
            for Counter in range(4): # ping every 3 seconds
                if not self.Running or utils.sleep(1):
                    xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Ping {self.EmbyServer.ServerData['ServerId']} ]", 0) # LOGDEBUG
                    self.ThreadsRunning["PING"] = False
                    return

                # Websocket ping
                if Counter == 0 and self.ThreadsRunning["WEBSOCKET"] and "WEBSOCKET" in self.Connection:
                    self.websocket_send(b"", 0x9)

                # Main connection ping
                if Counter == 1 and not self.RequestBusy["MAIN"].locked():
                    self.request("POST", "System/Ping", {}, {}, True, "", False, None, "MAIN")

                # Mainfallback connection ping
                if Counter == 2 and not self.RequestBusy["MAINFALLBACK"].locked():
                    self.request("POST", "System/Ping", {}, {}, True, "", False, None, "MAINFALLBACK")

                # Async connection ping
                if Counter == 3 and not self.RequestBusy["ASYNC"].locked():
                    self.Queues["ASYNC"].put((("POST", "System/Ping", {}, True),))

    # Intros and Trailers
    def verify_intros(self, Intro):
        xbmc.log("EMBY.emby.http: THREAD: --->[ verify intros ]", 0) # LOGDEBUG

        if Intro['Path'].find("http") == -1: # Local Trailer
            common.set_streams(Intro)
            common.set_chapters(Intro, self.EmbyServer.ServerData['ServerId'])
            common.set_path_filename(Intro, self.EmbyServer.ServerData['ServerId'], None, True)
            self.Intros.append(Intro)
            xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] valid local intro", 0) # LOGDEBUG
            return True

        status_code = self.EmbyServer.API.get_stream_statuscode(Intro['Id'], Intro['MediaSources'][0]['Id'])

        if status_code == 200:
            common.set_streams(Intro)
            common.set_chapters(Intro, self.EmbyServer.ServerData['ServerId'])
            common.set_path_filename(Intro, self.EmbyServer.ServerData['ServerId'], None, True)
            self.Intros.append(Intro)
            xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] valid http", 0) # LOGDEBUG
            return True

        xbmc.log(f"EMBY.emby.http: Invalid Trailer: {Intro['Path']} / {status_code}", 3) # LOGERROR
        xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] invalid", 0) # LOGDEBUG
        return False

    def load_Trailers(self, EmbyId):
        ReceivedIntros = []
        self.Intros = []

        if utils.localTrailers:
            LocalTrailers = self.EmbyServer.API.get_local_trailers(EmbyId)

            for LocalTrailer in LocalTrailers:
                ReceivedIntros.append(LocalTrailer)

        if utils.Trailers:
            Intros = self.EmbyServer.API.get_intros(EmbyId)

            if 'Items' in Intros:
                for Intro in Intros['Items']:
                    ReceivedIntros.append(Intro)

        if ReceivedIntros:
            Index = 0

            for Index, Intro in enumerate(ReceivedIntros):
                if self.verify_intros(Intro):
                    break

            for Intro in ReceivedIntros[Index + 1:]:
                utils.start_thread(self.verify_intros, (Intro,))

    def getPayloadByFrames(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, PayloadFrameLenght, DownloadName, OutFile, ProgressBar, ProgressBarTotal):
        PayloadFrameTotalLenght = PayloadFrameLenght + PayloadTotalLength
        PayloadTotalLength, PayloadTotal = processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, ProgressBar, ProgressBarTotal, DownloadName)

        while PayloadTotalLength < PayloadFrameTotalLenght:
            StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)

            if StatusCodeSocket:
                return None, None, StatusCodeSocket

            PayloadTotalLength, PayloadTotal = processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, ProgressBar, ProgressBarTotal, DownloadName)

        return PayloadTotal, PayloadTotalLength, 0

    def getPayloadByChunks(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBar, ProgressBarTotal):
        PayloadChunkBuffer = PayloadRecv
        ChunkPosition = 0

        while True:
            if not PayloadChunkBuffer.endswith(b"0\r\n\r\n"):
                xbmc.log("EMBY.emby.http: Chunks: Load additional data", 0) # LOGDEBUG
                StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)

                if StatusCodeSocket:
                    return None, None, StatusCodeSocket

                PayloadChunkBuffer += PayloadRecv

            ChunkedData = PayloadChunkBuffer.split(b"\r\n", 1)
            ChunkDataLen = int(ChunkedData[0], 16)

            if not ChunkDataLen:
                xbmc.log("EMBY.emby.http: Chunks: Data complete", 0) # LOGDEBUG
                return PayloadTotal, PayloadTotalLength, 0

            if len(ChunkedData[1]) - 2 < ChunkDataLen:
                xbmc.log("EMBY.emby.http: Chunks: Insufficient data", 0) # LOGDEBUG
                continue

            PayloadTotalLength, PayloadTotal = processData(PayloadTotal, PayloadTotalLength, ChunkedData[1][:ChunkDataLen], OutFile, ProgressBar, ProgressBarTotal, DownloadName)
            ChunkPosition = ChunkDataLen + len(ChunkedData[0]) + 4
            PayloadChunkBuffer = PayloadChunkBuffer[ChunkPosition:]

def processData(PayloadTotal, PayloadTotalLength, Data, OutFile, ProgressBar, ProgressBarTotal, DownloadName):
    PayloadTotalLength += len(Data)

    if OutFile:
        OutFile.write(Data)
        ProgressBar.update(int(PayloadTotalLength / ProgressBarTotal), "Download", DownloadName)
    else:
        PayloadTotal += (Data,)

    return PayloadTotalLength, PayloadTotal

def closeDownload(OutFile, ProgressBar):
    if OutFile:
        OutFile.close()
        ProgressBar.close()
        del ProgressBar

# Return empty data
def noData(StatusCode, Header, Binary):
    if Binary:
        return (StatusCode, Header, b"")

    return (StatusCode, Header, {})

def maskData(mask_key, data):
    _m = array.array("B", mask_key)
    _d = array.array("B", data)

    for i in range(len(_d)):
        _d[i] ^= _m[i % 4]  # i xor

    return _d.tobytes()

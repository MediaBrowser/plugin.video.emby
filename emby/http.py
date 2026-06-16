import threading
import base64
import os
import struct
import hashlib
import json
import zlib
import ssl
import uuid
import socket
import xbmc
import xbmcvfs
from helper import utils, queue, artworkcache
from database import dbio
from hooks import websocket

class HTTP:
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.Intros = []
        self.Queues = {"ASYNC": queue.Queue(), "DOWNLOAD": queue.Queue(), "QUEUEDREQUESTMAIN": queue.Queue(), "QUEUEDREQUESTMAINFALLBACK": queue.Queue()}
        self.Connection = {}
        self.Connecting = threading.Lock()
        self.RequestBusy = {"MAIN": threading.Lock(), "MAINFALLBACK": threading.Lock(), "REQUESTMAIN": threading.Lock(), "REQUESTMAINFALLBACK": threading.Lock(), "ASYNC": threading.Lock()}
        self.CounterLock = threading.Lock()
        self.HttpIdleEvent = threading.Event()
        self.HttpIdleEvent.set()
        self.Running = False
        self.ThreadsRunningCondition = threading.Condition(threading.Lock())
#        self.SSLContext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.SSLContext = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.SSLContext.load_default_certs()
        self.Websocket = websocket.WebSocket(EmbyServer, self.ThreadsRunningCondition)
        self.WebsocketBuffer = b""
        self.AddrInfo = {}
        self.Response = {}
        self.ThreadsRunning = {"ASYNC": False, "DOWNLOAD": False, "QUEUEDREQUESTMAIN": False, "QUEUEDREQUESTMAINFALLBACK": False, "PING": False, "WEBSOCKET": False}
        self.RequestsCounter = 0
        self.DownloadId = f"{self.EmbyServer.ServerData['ServerId']}_download"

        if utils.sslverify:
            self.SSLContext.verify_mode = ssl.CERT_REQUIRED
        else:
            self.SSLContext.check_hostname = False
            self.SSLContext.verify_mode = ssl.CERT_NONE

    def start(self):
        if utils.SystemShutdown:
            return

        if utils.DebugLog: xbmc.log(f"EMBY.emby.http: --->[ {self.EmbyServer.ServerData['ServerId']} HTTP ] 1", 1) # LOGINFO
        self.DownloadId = f"{self.EmbyServer.ServerData['ServerId']}_download"

        with utils.SafeLock(self.Connecting):
            if not self.Running and not utils.SystemShutdown:
                self.Running = True
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: --->[ {self.EmbyServer.ServerData['ServerId']} HTTP ] 2", 1) # LOGINFO
                self.DownloadId = f"{self.EmbyServer.ServerData['ServerId']}_download"

                if not self.ThreadsRunning["QUEUEDREQUESTMAIN"]:
                    self.ThreadsRunning["QUEUEDREQUESTMAIN"] = True
                    self.Queues["QUEUEDREQUESTMAIN"].clear()
                    utils.start_thread(self.queued_request, ("MAIN",))

                if not self.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"]:
                    self.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"] = True
                    self.Queues["QUEUEDREQUESTMAINFALLBACK"].clear()
                    utils.start_thread(self.queued_request, ("MAINFALLBACK",))

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

                with utils.SafeLock(self.ThreadsRunningCondition):
                    self.ThreadsRunningCondition.notify_all()

    def stop(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http: ---<[ {self.EmbyServer.ServerData['ServerId']} HTTP ] 1", 1) # LOGINFO

        with utils.SafeLock(self.Connecting):
            if self.Running:
                self.Running = False
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: ---<[ {self.EmbyServer.ServerData['ServerId']} HTTP ] 2", 1) # LOGINFO
                self.Queues["ASYNC"].put((("QUIT", "", {}, False),))
                self.Queues["DOWNLOAD"].put("QUIT")
                self.Queues["QUEUEDREQUESTMAIN"].put("QUIT")
                self.Queues["QUEUEDREQUESTMAINFALLBACK"].put("QUIT")
                self.HttpIdleEvent.set()

                if utils.websocketenabled:
                    self.Websocket.MessageQueue.put("QUIT")

                for ConnectionId in list(self.Connection.keys()):
                    if ConnectionId != "ASYNC": # Skip ASYNC as it might include termination info for server (e.g. remote playback disconnects)
                        self.socket_close(ConnectionId)

                # Verify all threads are stopped
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): CONDITION: --->[ self.ThreadsRunningCondition ]", 1) # LOGDEBUG

                with utils.SafeLock(self.ThreadsRunningCondition):
                    while self.ThreadsRunning["ASYNC"] or self.ThreadsRunning["DOWNLOAD"] or self.ThreadsRunning["QUEUEDREQUESTMAIN"] or self.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"] or self.ThreadsRunning["PING"] or self.ThreadsRunning["WEBSOCKET"] or self.Websocket.Running:
                        self.ThreadsRunningCondition.wait(timeout=0.1)

                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): CONDITION: ---<[ self.ThreadsRunningCondition ]", 1) # LOGDEBUG

                if utils.DebugLog:
                    xbmc.log(f"EMBY.emby.http (DEBUG): self.ThreadsRunning: {self.ThreadsRunning}", 1) # LOGDEBUG
                    xbmc.log(f"EMBY.emby.http (DEBUG): self.Websocket.Running: {self.Websocket.Running}", 1) # LOGDEBUG

    def socket_addrinfo(self, ConnectionId, Hostname, Force):
        if Hostname in self.AddrInfo and not Force:
            return 0

        try:
            AddrInfo = socket.getaddrinfo(Hostname, None)
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): AddrInfo: {AddrInfo}", 1) # LOGDEBUG
            self.AddrInfo[Hostname] = (AddrInfo[0][4][0], AddrInfo[0][0])
        except Exception as error:
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Wrong Hostname: {error}", 2) # LOGWARNING

            if ConnectionId == "MAIN":
                utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33678), time=utils.displayMessage, sound=False)

            if ConnectionId in self.Connection:
                del self.Connection[ConnectionId]

            return 609

        return 0

    def Requests_Counter(self, Increase):
        with utils.SafeLock(self.CounterLock):
            if Increase:
                self.RequestsCounter += 1
                self.HttpIdleEvent.clear()
            else:
                self.RequestsCounter -= 1
                if self.RequestsCounter <= 0:
                    self.RequestsCounter = 0
                    self.HttpIdleEvent.set()

    def socket_del(self, ConnectionId):
        if ConnectionId in self.Connection:
            del self.Connection[ConnectionId]

    def socket_open(self, ConnectionString, ConnectionId, CloseConnection):
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

                self.Connection[ConnectionId]["RequestHeader"] = {"Host": f"{self.Connection[ConnectionId]['Hostname']}:{self.Connection[ConnectionId]['Port']}", 'Content-Type': 'application/json; charset=utf-8', 'Accept-Charset': 'utf-8', 'Accept-Encoding': 'gzip,deflate', 'User-Agent': f"{utils.addon_name}/{utils.addon_version}", 'Connection': ConnectionMode, 'Authorization': f'Emby Client="{utils.addon_name}", Device="{utils.device_name}", DeviceId="{self.EmbyServer.ServerData["DeviceId"]}", Version="{utils.addon_version}"'}

                if ConnectionId == "DOWNLOAD":
                    self.Connection[ConnectionId]["RequestHeader"]['Accept-Encoding'] = "identity"

                StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], False)

                if StatusCodeSocket:
                    self.socket_del(ConnectionId)
                    return StatusCodeSocket

            RetryCounter = 0

            while True:
                try:
                    self.Connection[ConnectionId]["Socket"] = socket.socket(self.AddrInfo[self.Connection[ConnectionId]["Hostname"]][1], socket.SOCK_STREAM)
                    self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                    # CS0 (Best Effort) 0x00 is default
                    # https://bytesolutions.com/dscp-tos-cos-precedence-conversion-chart/
                    # https://en.wikipedia.org/wiki/Type_of_service
                    try:
                        if utils.Tos == "CS4 (Real-time interactive)":
                            self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x80)
                        elif utils.Tos == "CS5, EF (Expedited Forwarding)":
                            self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x184)
                        elif utils.Tos == "CS1, AF11 (Assured Forwarding)":
                            self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x20)
                    except Exception as error:
                        xbmc.log(f"EMBY.emby.http: Socket change IP_TOS Error: {error}", 2) # LOGWARNING

                    self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout

                    if not self.Connection[ConnectionId]["SSL"]:
                        self.Connection[ConnectionId]["Socket"].connect((self.AddrInfo[self.Connection[ConnectionId]["Hostname"]][0], self.Connection[ConnectionId]['Port']))
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

                        continue

                    self.socket_del(ConnectionId)
                    xbmc.log(f"EMBY.emby.http: [ ServerUnreachable ] {ConnectionId}", 2) # LOGWARNING
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): [ ServerUnreachable ] {ConnectionString}", 1) # LOGDEBUG
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

                    if str(error).find("timed out") != -1 or str(error).find("timeout") != -1: # workaround when TimeoutError not raised
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
                        try:
                            self.Connection[ConnectionId]["Socket"] = self.SSLContext.wrap_socket(self.Connection[ConnectionId]["Socket"], do_handshake_on_connect=True, suppress_ragged_eofs=True, server_hostname=self.Connection[ConnectionId]["Hostname"])
                            self.Connection[ConnectionId]["Socket"].connect((self.AddrInfo[self.Connection[ConnectionId]["Hostname"]][0], self.Connection[ConnectionId]['Port']))
                            self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout
                            break
                        except ssl.CertificateError:
                            self.socket_del(ConnectionId)
                            xbmc.log("EMBY.emby.http: socket_open ssl certificate error", 3) # LOGERROR

                            if ConnectionId == "MAIN":
                                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33428), time=utils.displayMessage)

                            return 608
                        except TimeoutError:
                            RetryCounter += 1

                            if RetryCounter <= 10:
                                if utils.sleep(0.1):
                                    return 699

                                continue

                            xbmc.log(f"EMBY.emby.http: socket_open ssl {ConnectionId}: Timeout", 2) # LOGWARNING
                            self.socket_del(ConnectionId)
                            return 606
                        except Exception as error:
                            RetryCounter += 1

                            if RetryCounter <= 10:
                                if utils.sleep(0.1):
                                    return 699

                                continue

                            if str(error).find("timed out") != -1 or str(error).find("timeout") != -1: # workaround when TimeoutError not raised
                                xbmc.log(f"EMBY.emby.http: socket_open ssl {ConnectionId}: Timeout", 2) # LOGWARNING
                                self.socket_del(ConnectionId)
                                return 606

                            xbmc.log(f"EMBY.emby.http: socket_open ssl undefined error {RetryCounter}: {error}", 2) # LOGWARNING
                            self.socket_del(ConnectionId)
                            return 699
                    else:
                        break
                else:
                    xbmc.log(f"EMBY.emby.http: socket_open ssl: No ConnectionId {ConnectionId}", 2) # LOGWARNING
                    self.socket_del(ConnectionId)
                    return 699

            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket {ConnectionId} opened", 1) # LOGDEBUG
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
                    self.Connection[ConnectionId]["Socket"].send(f'POST {self.Connection[ConnectionId]["SubUrl"]}System/Ping HTTP/1.1\r\nHost: {self.Connection[ConnectionId]["Hostname"]}:{self.Connection[ConnectionId]["Port"]}\r\nContent-Type: application/json; charset=utf-8\r\nAccept-Charset: utf-8\r\nAccept-Encoding: gzip,deflate\r\nUser-Agent: {utils.addon_name}/{utils.addon_version}\r\nConnection: close\r\nAuthorization: Emby Client="{utils.addon_name}", Device="{utils.device_name}", DeviceId="{self.EmbyServer.ServerData["DeviceId"]}", Version="{utils.addon_version}"\r\nContent-Length: 0\r\n\r\n'.encode("utf-8"))
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
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket {ConnectionId} already closed", 1) # LOGDEBUG
            return

        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket {ConnectionId} closed", 1) # LOGDEBUG

    def socket_io(self, Request, ConnectionId, Timeout):
        IncomingData = b""
        StatusCode = 0
        TimeoutCounter = 0
        BytesSend = 0
        BytesSendTotal = len(Request)
        TimeoutSocket = 0.1
        TimeoutLoops = Timeout * 10

        while True:
            try:
                self.Connection[ConnectionId]["Socket"].settimeout(TimeoutSocket)

                if Request:
                    while BytesSend < BytesSendTotal:
                        BytesSend += self.Connection[ConnectionId]["Socket"].send(Request[BytesSend:])
                else:
                    IncomingData = self.Connection[ConnectionId]["Socket"].recv(1048576)

                    if not IncomingData or (utils.SystemShutdown and Timeout > 4):
                        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket IO {ConnectionId}: Empty data", 1)
                        StatusCode = 600

                    break

                if BytesSend >= BytesSendTotal:
                    break
            except TimeoutError:
                if not TimeoutLoops or (ConnectionId != "MAIN" and self.RequestBusy["MAIN"].locked()):
                    continue

                TimeoutCounter += 1

                if TimeoutCounter < TimeoutLoops:
                    continue

                if Request:
                    xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Timeout", 2)

                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket IO {ConnectionId}: ({Request}): Timeout", 1)
                StatusCode = 603
                break
            except BrokenPipeError:
                xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Pipe error", 2)
                StatusCode = 605
                break
            except Exception as error:
                if str(error).find("timed out") != -1 or str(error).find("timeout") != -1: # workaround when TimeoutError not raised
                    if not TimeoutLoops or (ConnectionId != "MAIN" and self.RequestBusy["MAIN"].locked()):
                        continue

                    TimeoutCounter += 1

                    if TimeoutCounter <= TimeoutLoops:
                        continue

                    if Request:
                        xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Timeout (workaround)", 2)

                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Socket IO {ConnectionId}: ({Request}): Timeout (workaround)", 1)
                    StatusCode = 603
                    break

                xbmc.log(f"EMBY.emby.http: Socket IO {ConnectionId}: ({Request}): Undefined error {error} / Type: {type(error)}", 3)
                StatusCode = 698
                break

        return StatusCode, IncomingData

    def socket_request(self, Method, Handler, Params, Binary, TimeoutSend, TimeoutRecv, ConnectionId, DownloadName, OutFile, ProgressBarTotal):
        if ConnectionId not in self.Connection:
            return 601, {}, {}

        self.Requests_Counter(True)
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
            GETPayload = ""

            for Query, Param in list(Params.items()):
                if Query == "Ids":
                    IdsLen = len(str(Param))

                    if IdsLen >= utils.MaxURILength:
                        xbmc.log(f"EMBY.emby.http: GET params exceeds maximum len, sending Ids as body: {IdsLen}/{utils.MaxURILength}", 2) # LOGWARNING
                        GETPayload = Param
                    else:
                        ParamsString += f"{Query}={Param}&"
                elif Param not in ([], None):
                    ParamsString += f"{Query}={Param}&"

            if ParamsString:
                ParamsString = f"?{ParamsString[:-1]}"

            if GETPayload:
                GETPayload = f'{{"Ids": "{GETPayload}"}}'
                Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler}{ParamsString} HTTP/1.1\r\n{HeaderString}Content-Length: {len(GETPayload)}\r\n\r\n{GETPayload}"
            else:
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
            self.Requests_Counter(False)
            return StatusCodeSocket, {}, ""

        while True:
            StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)
            IncomingData += PayloadRecv

            if StatusCodeSocket or utils.SystemShutdown:
                self.closeDownload(OutFile)
                self.Requests_Counter(False)
                return StatusCodeSocket, {}, ""

            # Check if header is fully loaded
            if b'\r\n\r\n' not in IncomingData:
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Incomplete header", 1) # LOGDEBUG
                continue

            IncomingData = IncomingData.split(b'\r\n\r\n', 1) # Split header/payload

            try:
                IncomingMetaData = IncomingData[0].decode("ascii").split("\r\n")
                StatusCode = int(IncomingMetaData[0].split(" ")[1])
            except Exception as error: # Can happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Info: {error}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Binary: {Binary}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Request: {Request}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: IncomingData: {IncomingData}", 3) # LOGERROR
                self.Requests_Counter(False)
                return 612, {}, ""

            IncomingDataHeaderArray = IncomingMetaData[1:]
            IncomingDataHeader = {}

            for IncomingDataHeaderArrayData in IncomingDataHeaderArray:
                Temp = IncomingDataHeaderArrayData.split(":", 1)
                IncomingDataHeader[Temp[0].strip().lower()] = Temp[1].strip()

            # no trailers allowed due to RFC
            if StatusCode in (304, 101, 204) or Method == "HEAD":
                self.closeDownload(OutFile)
                self.Requests_Counter(False)
                return StatusCode, IncomingDataHeader, ""

            # Decompress flags
            ContentEncoding = IncomingDataHeader.get("content-encoding", "")
            isGzip = ContentEncoding == "gzip"
            isDeflate = ContentEncoding == "deflate"

            # Recv payload
            try:
                if IncomingDataHeader.get('transfer-encoding', "") == "chunked":
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByChunks(PayloadTotal, PayloadTotalLength, IncomingData[1], ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBarTotal)
                else:
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByFrames(PayloadTotal, PayloadTotalLength, IncomingData[1], ConnectionId, TimeoutRecv, int(IncomingDataHeader.get("content-length", 0)), DownloadName, OutFile, ProgressBarTotal)

                if StatusCodeSocket:
                    self.closeDownload(OutFile)
                    self.Requests_Counter(False)
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
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return 601, {}, ""

                    continue

                break
            except Exception as error: # Could happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Undefined error {error}: IncomingDataHeader: {IncomingDataHeader}", 3) # LOGERROR
                self.Requests_Counter(False)
                return 612, {}, ""

        self.closeDownload(OutFile)
        PayloadTotal = b''.join(PayloadTotal)

        # Decompress data
        try:
            if isDeflate:
                PayloadTotal = zlib.decompress(PayloadTotal, -zlib.MAX_WBITS)
            elif isGzip:
                PayloadTotal = zlib.decompress(PayloadTotal, zlib.MAX_WBITS|32)
        except Exception as error: # could happen on server overload
            xbmc.log(f"EMBY.emby.http: Decompress issue {ConnectionId}: {IncomingDataHeader} error: {error}", 3) # LOGERROR
            self.Requests_Counter(False)
            return 612, {}, ""

        if Binary:
            self.Requests_Counter(False)
            return StatusCode, IncomingDataHeader, PayloadTotal

        isJSON = "json" in IncomingDataHeader.get("content-type", "").lower()
        self.Requests_Counter(False)

        if isJSON:
            try:
                return StatusCode, IncomingDataHeader, json.loads(PayloadTotal)
            except MemoryError:
                xbmc.log(f"EMBY.emby.http: Invalid json content {ConnectionId}: {IncomingDataHeader} error: MemoryError", 3) # LOGERROR
                return 612, {}, ""
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
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Download {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG
        ProgressBar = False

        while True:
            Command = self.Queues["DOWNLOAD"].get() # EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId

            if Command == "QUIT":
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} ] shutdown 1", 1) # LOGDEBUG
                self.socket_close("DOWNLOAD")
                utils.close_ProgressBar(self.DownloadId)
                self.disable_thread("DOWNLOAD")
                return

            EmbyId, PathDownload, FileSize, MediaName, KodiType, KodiPathId, KodiFileId, KodiMediaId, Filename = Command
            EmbyId = str(EmbyId)
            KodiFileId = str(KodiFileId)

            # check if free space below 2GB
            if utils.getFreeSpace(PathDownload) < (2097152 + FileSize / 1024):
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=utils.displayMessage, sound=True)
                xbmc.log("EMBY.emby.http: THREAD: ---<[ file download ] terminated by filesize", 2) # LOGWARNING
                self.socket_close("DOWNLOAD")
                utils.close_ProgressBar(self.DownloadId)
                self.disable_thread("DOWNLOAD")
                return

            while True:
                if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "DOWNLOAD", True):
                    if utils.sleep(10):
                        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} shutdown ]", 1) # LOGDEBUG
                        self.disable_thread("DOWNLOAD")
                        return

                    continue

                self.update_header("DOWNLOAD")

                if not ProgressBar:
                    utils.create_ProgressBar(self.DownloadId, utils.Translate(33814), MediaName)

                ProgressBarTotal = FileSize / 100
                PathDownloadMedia = xbmcvfs.translatePath(os.path.join(PathDownload, KodiType, KodiFileId, ""))
                utils.mkDir(PathDownloadMedia)
                PathDownloadMediaFile = os.path.join(PathDownloadMedia, Filename)
                OutFile = open(PathDownloadMediaFile, 'wb')
                StatusCode, _, _ = self.socket_request("GET", f"Items/{EmbyId}/Download", {}, True, 12, 300, "DOWNLOAD", MediaName, OutFile, ProgressBarTotal)
                ProgressBarTotal = 0
                OutFile = None

                if StatusCode == 601 or utils.SystemShutdown: # quit
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Download {self.EmbyServer.ServerData['ServerId']} ] shutdown 2", 1) # LOGDEBUG
                    utils.delFile(PathDownloadMediaFile)
                    self.socket_close("DOWNLOAD")
                    utils.close_ProgressBar(self.DownloadId)
                    self.disable_thread("DOWNLOAD")
                    return

                if StatusCode in (600, 602, 603, 605, 612):
                    xbmc.log(f"EMBY.emby.http: Download retry {StatusCode}", 2) # LOGWARNING
                    utils.delFile(PathDownloadMediaFile)
                    self.socket_close("DOWNLOAD")
                    continue

                try:
                    if StatusCode != 200 or utils.SystemShutdown:
                        utils.delFile(PathDownloadMediaFile)
                    else:
                        if KodiMediaId: # KodiId
                            SQLs = {}
                            dbio.DBOpenRW("video", "download_item_replace", SQLs)
                            ArtworksNoUrlParam = SQLs['video'].download_Artwork(KodiMediaId, KodiType, True)
                            SQLs['video'].update_Name(KodiMediaId, KodiType, True)
                            SQLs['video'].replace_Path_ContentItem(KodiMediaId, KodiType, PathDownloadMedia, PathDownloadMediaFile)

                            if KodiType == "episode":
                                DownloadPathParent = xbmcvfs.translatePath(os.path.join(PathDownload, KodiType, ""))
                                KodiParentPathId = SQLs['video'].get_add_path(DownloadPathParent, "tvshows", None)
                                KodiPathIdNew = SQLs['video'].get_add_path(PathDownloadMedia, None, KodiParentPathId)
                                ArtworksNoUrlParam += SQLs['video'].download_Subcontent(KodiMediaId, True)
                            elif KodiType == "movie":
                                KodiPathIdNew = SQLs['video'].get_add_path(PathDownloadMedia, "movie", None)
                            elif KodiType == "musicvideo":
                                KodiPathIdNew = SQLs['video'].get_add_path(PathDownloadMedia, "musicvideos", None)
                            else:
                                KodiPathIdNew = None
                                xbmc.log(f"EMBY.emby.http: Download invalid: {KodiMediaId} / {KodiType}", 2) # LOGWARNING

                            if KodiPathIdNew:
                                SQLs['video'].replace_PathId(KodiFileId, KodiPathIdNew)

                            dbio.DBCloseRW("video", "download_item_replace", SQLs)

                            if KodiPathIdNew:
                                dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], "download_item", SQLs)
                                SQLs['emby'].add_DownloadItem(EmbyId, KodiPathId, KodiFileId, KodiMediaId, KodiType, KodiPathIdNew)
                                dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], "download_item", SQLs)

                            if ArtworksNoUrlParam:
                                artworkcache.CacheAllEntries(ArtworksNoUrlParam, "")

                    if self.Queues["DOWNLOAD"].isEmpty():
                        utils.refresh_widgets(True)
                except Exception as error:
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http: Download Emby server did not respond: error: {error}", 2) # LOGWARNING

                break

    def request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, BusyFunction, ConnectionId):
        CloseConnection = False

        # Set Ids
        if not ConnectionId:
            if self.RequestBusy["MAIN"].locked():
                if self.RequestBusy["MAINFALLBACK"].locked():
                    ConnectionId = str(uuid.uuid4())
                    CloseConnection = True
                else:
                    ConnectionId = "MAINFALLBACK"

                    while not self.RequestBusy["MAINFALLBACK"].acquire(timeout=0.1):
                        pass
            else:
                ConnectionId = "MAIN"

                while not self.RequestBusy["MAIN"].acquire(timeout=0.1):
                    pass
        else: # Use explicit connection (ping)
            while not self.RequestBusy[ConnectionId].acquire(timeout=0.1):
                pass

        RequestId = f"REQUEST{ConnectionId}"
        self.Response[RequestId] = False

        # Simple request
        if CloseConnection or not BusyFunction or not self.ThreadsRunning["QUEUEDREQUESTMAIN"] or not self.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"]:
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)
            Data = self.Response[RequestId]
            del self.Response[RequestId]

            if ConnectionId in ("MAIN", "MAINFALLBACK"):
                self.RequestBusy[ConnectionId].release()

            return Data

        if ConnectionId not in ("MAIN", "MAINFALLBACK"):
            self.Queues[f"QUEUEDREQUEST{ConnectionId}"] = queue.Queue()
            utils.start_thread(self.queued_request, (ConnectionId,))
            self.RequestBusy[ConnectionId] = threading.Lock()
            self.RequestBusy[RequestId] = threading.Lock()

        self.Queues[f"QUEUEDREQUEST{ConnectionId}"].put(((Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, RequestId),))

        # Check conditions while waiting for data -> BusyFunction
        while True:
            self.RequestBusy[RequestId].acquire(blocking=True, timeout=0.1)
            Data = self.Response[RequestId]

            # Data received, request finished
            if Data:
                Data = self.Response[RequestId]
                self.RequestBusy[ConnectionId].release()
                del self.Response[RequestId]
                ReturnData = Data
                break

            # trigger busy function: Interrupt query if necessary, e.g. Kodi shutdown or simply wait till BusyFunction continues
            if not BusyFunction["Object"](*BusyFunction["Params"]):
                self.RequestBusy[ConnectionId].release()
                del self.Response[RequestId]
                ReturnData = noData(601, {}, Binary)
                break

        if ConnectionId not in ("MAIN", "MAINFALLBACK"):
            self.Queues[f"QUEUEDREQUEST{ConnectionId}"].put("QUIT")
            del self.RequestBusy[ConnectionId]
            del self.RequestBusy[RequestId]

        return ReturnData

    def queued_request(self, ConnectionId):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Queued request {ConnectionId}: {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG

        while True:
            Incoming = self.Queues[f"QUEUEDREQUEST{ConnectionId}"].get() # EmbyId, ParentPath, Path, FilePath, FileSize, Name, KodiType, KodiPathIdBeforeDownload, KodiFileId, KodiId

            if Incoming == "QUIT":
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Queued request {ConnectionId}: {self.EmbyServer.ServerData['ServerId']} ] shutdown 1", 1) # LOGDEBUG

                if ConnectionId not in ("MAIN", "MAINFALLBACK"):
                    del self.Queues[f"QUEUEDREQUEST{ConnectionId}"]
                else:
                    self.disable_thread(f"QUEUEDREQUEST{ConnectionId}")

                return

            Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, RequestId = Incoming
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): [ http ] Method: {Method} / Handler: {Handler} / Params: {Params} / Binary: {Binary} / ConnectionString: {ConnectionString} / CloseConnection: {CloseConnection} / RequestHeader: {RequestHeader}", 1) # LOGDEBUG
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)

    def send_request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId):
        self.Requests_Counter(True)

        if not ConnectionString:
            ConnectionString = self.EmbyServer.ServerData['ServerUrl']

        # Connectionstring changed
        if not CloseConnection and ConnectionId in self.Connection and ConnectionString.find(self.Connection[ConnectionId]['Hostname']) == -1:
            self.socket_close(ConnectionId)

        while True:
            # Shutdown
            if utils.SystemShutdown:
                self.socket_close(ConnectionId)
                self.Response[RequestId] = noData(0, {}, Binary)
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Request {self.EmbyServer.ServerData['ServerId']} ] shutdown 2", 1) # LOGDEBUG
                break

            # open socket
            if ConnectionId not in self.Connection:
                StatusCodeConnect = self.socket_open(ConnectionString, ConnectionId, CloseConnection)

                if StatusCodeConnect:
                    if StatusCodeConnect not in (608, 609, 610, 611): # wrong Emby server address or SSL issue
                        self.EmbyServer.ServerReconnect(True)

                    self.Response[RequestId] = noData(StatusCodeConnect, {}, Binary)
                    break

            # Update Header information
            if RequestHeader:
                self.Connection[ConnectionId]["RequestHeader"] = {"Host": f"{self.Connection[ConnectionId]['Hostname']}:{self.Connection[ConnectionId]['Port']}", 'Accept': "application/json", 'Accept-Charset': "utf-8", 'X-Application': f"{utils.addon_name}/{utils.addon_version}", 'Content-Type': 'application/json'}
                self.Connection[ConnectionId]["RequestHeader"].update(RequestHeader)
            else:
                self.update_header(ConnectionId)

            # Request data with different timeout settings
            if Handler == "System/Ping":
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 6, ConnectionId, "", None, 0)
            elif "Subtitles" in Handler:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 30, ConnectionId, "", None, 0)
            else:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 1200, ConnectionId, "", None, 0)

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
                Text = f"{utils.Translate(33147)}\n{str(Payload)}"
                xbmc.log(f"EMBY.emby.http: Request unauthorized {StatusCode} / {ConnectionId} / {Text}", 3) # LOGERROR
                utils.Dialog.notification(heading=utils.addon_name, message=Text, time=utils.displayMessage)
                self.EmbyServer.ServerDisconnect(True)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 403: # Access denied
                Text = f"{utils.Translate(33696)}\n{str(Payload)}"
                xbmc.log(f"EMBY.emby.http: Request access denied {StatusCode} / {ConnectionId} / {Text}", 3) # LOGERROR
                utils.Dialog.notification(heading=utils.addon_name, message=Text, time=utils.displayMessage)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode in (600, 605, 612, 698): # no data received, broken pipes, undefined error, Socket IO error
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

            xbmc.log(f"EMBY.emby.http: [ Statuscode ] {StatusCode}", 3) # LOGERROR
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): [ Statuscode ] {Payload}", 1) # LOGDEBUG
            self.Response[RequestId] = noData(StatusCode, {}, Binary)
            break

        if RequestId in self.RequestBusy and self.RequestBusy[RequestId].locked():
            self.RequestBusy[RequestId].release()

        self.Requests_Counter(False)

    def websocket_listen(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Websocket {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG
        WarningDisplayed = False

        while self.ThreadsRunning["WEBSOCKET"] and self.Running:
            if utils.DebugLog: xbmc.log("EMBY.emby.http: Websocket connecting", 1) # LOGINFO

            if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "WEBSOCKET", False):
                if utils.sleep(10):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 1 ]", 1) # LOGDEBUG
                    self.disable_thread("WEBSOCKET")
                    return

                continue

            uid = uuid.uuid4()
            EncodingKey = base64.b64encode(uid.bytes).strip().decode('utf-8')

            if not self.ThreadsRunning["WEBSOCKET"] or not self.Running:
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 2 ]", 1) # LOGDEBUG
                self.disable_thread("WEBSOCKET")
                return

            self.Connection["WEBSOCKET"]["RequestHeader"].update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": EncodingKey, "Sec-WebSocket-Version": "13"})
            StatusCode, Header, Payload = self.socket_request("GET", f"embywebsocket?api_key={self.EmbyServer.ServerData['AccessToken']}&deviceId={self.EmbyServer.ServerData['DeviceId']}", {}, True, 12, 30, "WEBSOCKET", "", None, 0)

            if StatusCode == 601: # quit
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} quit ]", 1) # LOGDEBUG
                self.disable_thread("WEBSOCKET")
                return

            if StatusCode != 101:
                self.socket_close("WEBSOCKET")

                if utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 2 ]", 1) # LOGDEBUG
                    self.disable_thread("WEBSOCKET")
                    return

            result = Header.get("sec-websocket-accept", "")

            if not result:
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Websocket {self.EmbyServer.ServerData['ServerId']} sec-websocket-accept not found: Header: {Header} / Payload: {Payload}", 1) # LOGDEBUG

                if not WarningDisplayed:
                    utils.Dialog.notification(heading=utils.addon_name, icon="DefaultIconError.png", message=utils.Translate(33235), sound=True, time=utils.displayMessage)
                    WarningDisplayed = True

                if utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 3 ]", 1) # LOGDEBUG
                    self.disable_thread("WEBSOCKET")
                    return

                continue

            WarningDisplayed = False
            value = f"{EncodingKey}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("utf-8")
            hashed = base64.b64encode(hashlib.sha1(value).digest()).strip().lower().decode('utf-8')

            if hashed != result.lower():
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Websocket {self.EmbyServer.ServerData['ServerId']} wrong hash", 1) # LOGDEBUG

                if utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} shutdown 4 ]", 1) # LOGDEBUG
                    self.disable_thread("WEBSOCKET")
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
                        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Websocket not fin", 1) # LOGDEBUG
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
                            if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Websocket incomplete frame", 1) # LOGDEBUG
                            break

                        payload = self.WebsocketBuffer[Curser:FrameLengthEndPos]
                        Curser = FrameLengthEndPos

                    if has_mask:
                        payload = maskData(FrameMask, payload)

                    if opcode in (0x2, 0x1, 0x0): # 1 textframe, 2 binaryframe, 0 continueframe
                        if fin and payload:
                            self.Websocket.MessageQueue.put(payload)
                    elif opcode == 0x8: # Connection close
                        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Websocket connection closed", 1) # LOGDEBUG
                        ConnectionClosed = True
                        break
                    elif opcode == 0x9: # Ping
                        if not self.websocket_send(payload, 0xa):  # Pong:
                            break
                    elif opcode == 0xa: # Pong
                        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Websocket Pong received", 1) # LOGDEBUG
                    else:
                        xbmc.log(f"EMBY.hooks.websocket: Uncovered Opcode: {opcode} / Payload: {payload} / FrameHeader: {FrameHeader} / FrameLength: {FrameLength} / FrameMask: {FrameMask}", 3) # LOGERROR

                    self.WebsocketBuffer = self.WebsocketBuffer[Curser:]
                    continue

            if ConnectionClosed:
                break

        self.disable_thread("WEBSOCKET")
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Websocket {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG

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
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Async {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG

        # Process commands
        while True:
            CommandsReceived = self.Queues["ASYNC"].getall() # (Method, URL-handler, Parameters, Priority)

            # Sort by Priority:
            CommandsPriority = ()
            CommandsRegular = ()

            for CommandReceived in CommandsReceived:
                InsertCommand = ((CommandReceived[0], CommandReceived[1], CommandReceived[2]),)

                if CommandReceived[3]: # Priority
                    CommandsPriority += InsertCommand
                else: # Regular command
                    CommandsRegular += InsertCommand

            for CommandPriority in CommandsPriority: # do not interrupt priority commands
                self.async_commands_worker(CommandPriority, True)

            for CommandRegular in CommandsRegular:
                if self.async_commands_worker(CommandRegular, False): # Shutdown
                    self.socket_close("ASYNC")
                    self.disable_thread("ASYNC")
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Async {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG
                    return

    def async_commands_worker(self, Command, Priority):
        if Command[0] == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by QUIT", 1) # LOGDEBUG
            return True

        with utils.SafeLock(self.RequestBusy["ASYNC"]):
            while True:
                # Connect socket
                if "ASYNC" not in self.Connection:
                    if self.socket_open(self.EmbyServer.ServerData['ServerUrl'], "ASYNC", False):
                        if utils.sleep(1):
                            if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by Kodi shutdown", 1) # LOGDEBUG
                            return True

                        continue

                self.update_header("ASYNC")

                if Priority:
                    StatusCode, _, _ = self.socket_request(Command[0], Command[1], Command[2], True, 3, 3, "ASYNC", "", None, 0)
                else:
                    StatusCode, _, _ = self.socket_request(Command[0], Command[1], Command[2], True, 1, 0.1, "ASYNC", "", None, 0)

                if StatusCode == 601: # quit
                    if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by 601", 1) # LOGDEBUG
                    return True

                if StatusCode in (600, 605, 612, 698): # no data received, broken pipes, undefined error, Socket IO error -> Re-try
                    xbmc.log(f"EMBY.emby.http: Async retry {StatusCode}", 2) # LOGWARNING
                    self.socket_close("ASYNC")

                    if not self.Running or utils.SystemShutdown:
                        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by not self.Running", 1) # LOGDEBUG
                        return True

                    continue

                if StatusCode in (602, 603): # timeouts
                    if Priority:
                        xbmc.log(f"EMBY.emby.http: Async timeout {StatusCode}", 2) # LOGWARNING -> Emby server is sometimes not responsive, as no response is expected, skip it

                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Async timeout {StatusCode}", 1) # LOGDEBUG

                return False

    # Ping server -> keep http sessions open (timer)
    def Ping(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Ping {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG

        while True:
            for Counter in range(4): # ping every 3 seconds
                if not self.Running or utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Ping {self.EmbyServer.ServerData['ServerId']} ]", 1) # LOGDEBUG
                    self.disable_thread("PING")
                    return

                # Websocket ping
                if Counter == 0 and self.ThreadsRunning["WEBSOCKET"] and "WEBSOCKET" in self.Connection:
                    self.websocket_send(b"", 0x9)

                # Main connection ping
                if Counter == 1 and not self.RequestBusy["MAIN"].locked():
                    self.request("POST", "System/Ping", {}, {}, True, "", None, "MAIN")

                # Mainfallback connection ping
                if Counter == 2 and not self.RequestBusy["MAINFALLBACK"].locked():
                    self.request("POST", "System/Ping", {}, {}, True, "", None, "MAINFALLBACK")

                # Async connection ping
                if Counter == 3 and not self.RequestBusy["ASYNC"].locked():
                    self.Queues["ASYNC"].put((("POST", "System/Ping", {}, False),))

    def getPayloadByFrames(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, PayloadFrameLenght, DownloadName, OutFile, ProgressBarTotal):
        PayloadFrameTotalLenght = PayloadFrameLenght + PayloadTotalLength
        PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

        while PayloadTotalLength < PayloadFrameTotalLenght:
            StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)

            if StatusCodeSocket:
                return None, None, StatusCodeSocket

            PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

        return PayloadTotal, PayloadTotalLength, 0

    def getPayloadByChunks(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBarTotal):
        PayloadChunkBuffer = PayloadRecv

        while True:
            if not PayloadChunkBuffer.endswith(b"0\r\n\r\n"):
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Load additional data", 1) # LOGDEBUG
                StatusCodeSocket, PayloadRecv = self.socket_io("", ConnectionId, TimeoutRecv)

                if StatusCodeSocket:
                    return None, None, StatusCodeSocket

                PayloadChunkBuffer += PayloadRecv

            ChunkedData = PayloadChunkBuffer.split(b"\r\n", 1)
            ChunkDataLen = int(ChunkedData[0], 16)

            if not ChunkDataLen:
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Data complete", 1) # LOGDEBUG
                return PayloadTotal, PayloadTotalLength, 0

            if len(ChunkedData[1]) - 2 < ChunkDataLen:
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Insufficient data", 1) # LOGDEBUG
                continue

            PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, ChunkedData[1][:ChunkDataLen], OutFile, DownloadName, ProgressBarTotal)
            ChunkPosition = ChunkDataLen + len(ChunkedData[0]) + 4
            PayloadChunkBuffer = PayloadChunkBuffer[ChunkPosition:]

    def closeDownload(self, OutFile):
        if OutFile:
            OutFile.close()

            if self.Queues['DOWNLOAD'].isEmpty():
                utils.close_ProgressBar(self.DownloadId)

    def disable_thread(self, Id):
        self.ThreadsRunning[Id] = False

        with utils.SafeLock(self.ThreadsRunningCondition):
            self.ThreadsRunningCondition.notify_all()

    def processData(self, PayloadTotal, PayloadTotalLength, Data, OutFile, DownloadName, ProgressBarTotal):
        PayloadTotalLength += len(Data)

        if OutFile:
            OutFile.write(Data)
            utils.update_ProgressBar(self.DownloadId, PayloadTotalLength / ProgressBarTotal, utils.Translate(33760), DownloadName)
        else:
            PayloadTotal += (Data,)

        return PayloadTotalLength, PayloadTotal

# Return empty data
def noData(StatusCode, Header, Binary):
    if Binary:
        return (StatusCode, Header, b"")

    return (StatusCode, Header, {})

def maskData(mask_key, data):
    if not data:
        return b""

    full_mask = mask_key * ((len(data) // len(mask_key)) + 1)
    data_int = int.from_bytes(data, 'big')
    mask_int = int.from_bytes(full_mask[:len(data)], 'big')
    return (data_int ^ mask_int).to_bytes(len(data), 'big')

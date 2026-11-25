import socket
import ssl
import threading
import xbmc

from helper import utils
from . import http, websocket


class HTTPCommon:
    def __init__(self, ServerData, HTTPThreadsRunningCondition, WebsocketRunning, WebsocketMessageQueue):
        self.ServerData = ServerData
        self.HTTPThreadsRunningCondition = HTTPThreadsRunningCondition
        self.WebsocketRunning = WebsocketRunning
        self.WebsocketMessageQueue = WebsocketMessageQueue
        self.PingRunning = False
        self.Connection = {}
        self.AddrInfo = {}
        self.AddrInfoLock = threading.Lock()
        self.SSLContext = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        if utils.sslverify:
            self.SSLContext.verify_mode = ssl.CERT_REQUIRED
        else:
            self.SSLContext.check_hostname = False
            self.SSLContext.verify_mode = ssl.CERT_NONE

        self.HTTP = http.HTTP(self)
        self.WebSocket = websocket.WebSocket(self)
        self.Queues = self.HTTP.Queues
        self.RequestBusy = self.HTTP.RequestBusy
        self.Response = self.HTTP.Response
        self.ResponseLock = self.HTTP.ResponseLock
        self.ResponseCanceled = self.HTTP.ResponseCanceled
        self.HttpIdleEvent = self.HTTP.HttpIdleEvent
        self.ThreadsRunning = self.HTTP.ThreadsRunning

    def start(self):
        if utils.SystemShutdown:
            return

        if utils.DebugLog: xbmc.log(f"EMBY.emby.http: --->[ {self.ServerData['ServerId']} HTTP ] 1", 1) # LOGINFO
        self.HTTP.DownloadId = f"{self.ServerData['ServerId']}_download"

        with utils.SafeLock(self.HTTP.Connecting):
            if not self.HTTP.Running and not utils.SystemShutdown:
                self.HTTP.Running = True
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: --->[ {self.ServerData['ServerId']} HTTP ] 2", 1) # LOGINFO
                self.HTTP.DownloadId = f"{self.ServerData['ServerId']}_download"

                self.HTTP.start_http()

                if utils.websocketenabled:
                    self.WebSocket.start()

                if not self.PingRunning:
                    self.PingRunning = True
                    utils.start_thread(self.Ping, ())

                with utils.SafeLock(self.HTTPThreadsRunningCondition):
                    self.HTTPThreadsRunningCondition.notify_all()

    def stop(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http: ---<[ {self.ServerData['ServerId']} HTTP ] 1", 1) # LOGINFO

        with utils.SafeLock(self.HTTP.Connecting):
            if self.HTTP.Running:
                self.HTTP.Running = False
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: ---<[ {self.ServerData['ServerId']} HTTP ] 2", 1) # LOGINFO

                self.HTTP.stop_http()
                self.WebSocket.stop()

                for ConnectionId in list(self.Connection.keys()):
                    if ConnectionId != "ASYNC": # Skip ASYNC as it might include termination info for server (e.g. remote playback disconnects)
                        self.socket_close(ConnectionId, False)

        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): CONDITION: --->[ self.HTTPThreadsRunningCondition ]", 1) # LOGDEBUG

        with utils.SafeLock(self.HTTPThreadsRunningCondition):
            while self.HTTP.ThreadsRunning["ASYNC"] or self.HTTP.ThreadsRunning["DOWNLOAD"] or self.HTTP.ThreadsRunning["QUEUEDREQUESTMAIN"] or self.HTTP.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"] or self.PingRunning or self.WebSocket.ThreadRunning or self.WebsocketRunning[0]:
                self.HTTPThreadsRunningCondition.wait(timeout=0.1)

        for ConnectionId in list(self.Connection.keys()):
            if ConnectionId != "ASYNC":
                self.socket_del(ConnectionId)

        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): CONDITION: ---<[ self.HTTPThreadsRunningCondition ]", 1) # LOGDEBUG

        if utils.DebugLog:
            xbmc.log(f"EMBY.emby.http (DEBUG): self.HTTP.ThreadsRunning: {self.HTTP.ThreadsRunning}", 1) # LOGDEBUG
            xbmc.log(f"EMBY.emby.http (DEBUG): self.WebsocketRunning[0]: {self.WebsocketRunning[0]}", 1) # LOGDEBUG

    def request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, BusyFunction, ConnectionId):
        return self.HTTP.request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, BusyFunction, ConnectionId)

    def Ping(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Ping {self.ServerData['ServerId']} ]", 1) # LOGDEBUG

        while True:
            for Counter in range(4): # ping every 3 seconds
                if not self.HTTP.Running or utils.sleep(1):
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Ping {self.ServerData['ServerId']} ]", 1) # LOGDEBUG
                    self.PingRunning = False
                    with utils.SafeLock(self.HTTPThreadsRunningCondition):
                        self.HTTPThreadsRunningCondition.notify_all()
                    return

                if Counter == 0 and self.WebSocket.ThreadRunning and "WEBSOCKET" in self.Connection:
                    self.WebSocket.send(b"", 0x9)

                if Counter == 1 and not self.HTTP.RequestBusy["MAIN"].locked():
                    self.HTTP.request("POST", "System/Ping", {}, {}, True, "", None, "MAIN")

                if Counter == 2 and not self.HTTP.RequestBusy["MAINFALLBACK"].locked():
                    self.HTTP.request("POST", "System/Ping", {}, {}, True, "", None, "MAINFALLBACK")

                if Counter == 3 and not self.HTTP.RequestBusy["ASYNC"].locked():
                    self.HTTP.Queues["ASYNC"].put((("POST", "System/Ping", {}, False),))

    def socket_addrinfo(self, ConnectionId, Hostname, Force):
        AddrInfoKey = (Hostname, self.Connection[ConnectionId]["Port"])

        with utils.SafeLock(self.AddrInfoLock):
            if AddrInfoKey in self.AddrInfo and not Force:
                return 0

        try:
            AddrInfo = socket.getaddrinfo(Hostname, self.Connection[ConnectionId]["Port"], socket.AF_UNSPEC, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http: AddrInfo: {AddrInfo}", 1) # LOGDEBUG

            AddrInfoList = []

            for AddrInfoData in AddrInfo:
                AddrInfoList.append((AddrInfoData[0], AddrInfoData[4]))

            with utils.SafeLock(self.AddrInfoLock):
                self.AddrInfo[AddrInfoKey] = AddrInfoList
        except Exception as error:
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http: Socket open {ConnectionId}: Wrong Hostname: {error}", 2) # LOGWARNING

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

                if ":" in self.Connection[ConnectionId]["Hostname"]:
                    HostHeader = f'[{self.Connection[ConnectionId]["Hostname"]}]:{self.Connection[ConnectionId]["Port"]}'
                else:
                    HostHeader = f'{self.Connection[ConnectionId]["Hostname"]}:{self.Connection[ConnectionId]["Port"]}'

                self.Connection[ConnectionId]["RequestHeader"] = {"Host": HostHeader, 'Content-Type': 'application/json; charset=utf-8', 'Accept-Charset': 'utf-8', 'Accept-Encoding': 'gzip,deflate', 'User-Agent': f"{utils.addon_name}/{utils.addon_version}", 'Connection': ConnectionMode, 'Authorization': f'Emby Client="{utils.addon_name}", Device="{utils.device_name}", DeviceId="{self.ServerData["DeviceId"]}", Version="{utils.addon_version}"'}

                if ConnectionId == "DOWNLOAD":
                    self.Connection[ConnectionId]["RequestHeader"]['Accept-Encoding'] = "identity"

                StatusCodeSocket = self.socket_addrinfo(ConnectionId, self.Connection[ConnectionId]["Hostname"], False)

                if StatusCodeSocket:
                    self.socket_del(ConnectionId)
                    return StatusCodeSocket

            RetryCounter = 0
            AddrInfoIndex = 0

            while True:
                try:
                    AddressFamily, Address = self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])][AddrInfoIndex]
                    self.Connection[ConnectionId]["Socket"] = socket.socket(AddressFamily, socket.SOCK_STREAM)
                    self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                    # CS0 (Best Effort) 0x00 is default
                    # https://bytesolutions.com/dscp-tos-cos-precedence-conversion-chart/
                    # https://en.wikipedia.org/wiki/Type_of_service
                    try:
                        if utils.Tos == "CS4 (Real-time interactive)":
                            if AddressFamily == socket.AF_INET6:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, 0x80)
                            else:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x80)
                        elif utils.Tos == "CS5 (Signaling)":
                            if AddressFamily == socket.AF_INET6:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, 0xA0)
                            else:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0xA0)
                        elif utils.Tos == "EF (Expedited Forwarding)":
                            if AddressFamily == socket.AF_INET6:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, 0xB8)
                            else:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0xB8)
                        elif utils.Tos == "CS1, AF11 (Assured Forwarding)":
                            if AddressFamily == socket.AF_INET6:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IPV6, socket.IPV6_TCLASS, 0x20)
                            else:
                                self.Connection[ConnectionId]["Socket"].setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x20)
                    except Exception as error:
                        xbmc.log(f"EMBY.emby.http: Socket change IP_TOS Error: {error}", 2) # LOGWARNING

                    self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout

                    if not self.Connection[ConnectionId]["SSL"]:
                        self.Connection[ConnectionId]["Socket"].connect(Address)
                except TimeoutError:
                    if ConnectionId not in self.Connection:
                        xbmc.log(f"EMBY.emby.http: TimeoutError: No Connection {ConnectionId}", 2) # LOGWARNING
                        return 699

                    self.Connection[ConnectionId]["Socket"].close()
                    AddrInfoIndex += 1

                    if AddrInfoIndex < len(self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])]):
                        continue

                    AddrInfoIndex = 0
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

                    self.Connection[ConnectionId]["Socket"].close()
                    AddrInfoIndex += 1

                    if AddrInfoIndex < len(self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])]):
                        continue

                    AddrInfoIndex = 0
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

                    self.Connection[ConnectionId]["Socket"].close()
                    AddrInfoIndex += 1

                    if AddrInfoIndex < len(self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])]):
                        continue

                    AddrInfoIndex = 0
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
                            self.Connection[ConnectionId]["Socket"] = self.SSLContext.wrap_socket(self.Connection[ConnectionId]["Socket"], server_hostname=self.Connection[ConnectionId]["Hostname"])
                            self.Connection[ConnectionId]["Socket"].connect(Address)
                            self.Connection[ConnectionId]["Socket"].settimeout(3) # set timeout
                            break
                        except ssl.CertificateError:
                            self.socket_del(ConnectionId)
                            xbmc.log("EMBY.emby.http: socket_open ssl certificate error", 3) # LOGERROR

                            if ConnectionId == "MAIN":
                                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33428), time=utils.displayMessage)

                            return 608
                        except TimeoutError:
                            self.Connection[ConnectionId]["Socket"].close()
                            AddrInfoIndex += 1

                            if AddrInfoIndex < len(self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])]):
                                continue

                            AddrInfoIndex = 0
                            RetryCounter += 1

                            if RetryCounter <= 10:
                                if utils.sleep(0.1):
                                    return 699

                                continue

                            xbmc.log(f"EMBY.emby.http: socket_open ssl {ConnectionId}: Timeout", 2) # LOGWARNING
                            self.socket_del(ConnectionId)
                            return 606
                        except Exception as error:
                            self.Connection[ConnectionId]["Socket"].close()
                            AddrInfoIndex += 1

                            if AddrInfoIndex < len(self.AddrInfo[(self.Connection[ConnectionId]["Hostname"], self.Connection[ConnectionId]["Port"])]):
                                continue

                            AddrInfoIndex = 0
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

    def socket_close(self, ConnectionId, DeleteConnection=True):
        if ConnectionId in self.Connection:
            try:
                self.Connection[ConnectionId]["Socket"].close()
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Socket {ConnectionId} close error: {error}", 2) # LOGWARNING

            try:
                if DeleteConnection:
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
                if not TimeoutLoops:
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
                    if not TimeoutLoops:
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

import threading
import os
import json
import zlib
import gzip
import uuid
from urllib.parse import urljoin, urlsplit, quote_plus
import xbmc
import xbmcvfs
from helper import utils, queue, artworkcache
from database import dbio

class HTTP:
    def __init__(self, Common):
        self.Common = Common
        self.ServerData = Common.ServerData
        self.Connection = Common.Connection
        self.HTTPThreadsRunningCondition = Common.HTTPThreadsRunningCondition
        self.Intros = []
        self.Queues = {"ASYNC": queue.Queue(), "DOWNLOAD": queue.Queue(), "QUEUEDREQUESTMAIN": queue.Queue(), "QUEUEDREQUESTMAINFALLBACK": queue.Queue()}
        self.Connecting = threading.Lock()
        self.RequestBusy = {"MAIN": threading.Lock(), "MAINFALLBACK": threading.Lock(), "REQUESTMAIN": threading.Lock(), "REQUESTMAINFALLBACK": threading.Lock(), "ASYNC": threading.Lock()}
        self.CounterLock = threading.Lock()
        self.HttpIdleEvent = threading.Event()
        self.HttpIdleEvent.set()
        self.Running = False
        self.Response = {}
        self.ThreadsRunning = {"ASYNC": False, "DOWNLOAD": False, "QUEUEDREQUESTMAIN": False, "QUEUEDREQUESTMAINFALLBACK": False}
        self.RequestsCounter = 0
        self.DownloadId = f"{self.ServerData['ServerId']}_download"
        self.ResponseLock = threading.Lock()
        self.ResponseCanceled = set()

    def start_http(self):
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

    def stop_http(self):
        self.Queues["ASYNC"].put((("QUIT", "", {}, False),))
        self.Queues["DOWNLOAD"].put("QUIT")
        self.Queues["QUEUEDREQUESTMAIN"].put("QUIT")
        self.Queues["QUEUEDREQUESTMAINFALLBACK"].put("QUIT")
        self.HttpIdleEvent.set()

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

    def socket_request(self, Method, Handler, Params, Binary, TimeoutSend, TimeoutRecv, ConnectionId, DownloadName, OutFile, ProgressBarTotal, ConnectionString, CloseConnection):
        if ConnectionId not in self.Connection:
            return 601, {}, {}

        self.Requests_Counter(True)
        PayloadTotal = ()
        PayloadTotalLength = 0
        StatusCode = 612
        IncomingData = b""
        IncomingDataHeader = {}
        CloseDelimited = False

        # Prepare HTTP Header
        HeaderString = ""
        HasRange = False
        HasAcceptEncoding = False

        for Key, Values in list(self.Connection[ConnectionId]['RequestHeader'].items()):
            if Key.lower() == "range":
                HasRange = True
            elif Key.lower() == "accept-encoding":
                HasAcceptEncoding = True

        for Key, Values in list(self.Connection[ConnectionId]['RequestHeader'].items()):
            if HasRange and Key.lower() == "accept-encoding":
                Values = "identity"

            HeaderString += f"{Key}: {Values}\r\n"

        if HasRange and not HasAcceptEncoding:
            HeaderString += "Accept-Encoding: identity\r\n"

        # Prepare HTTP Payload
        if Method in ("GET", "HEAD"):
            ParamsString = ""
            GETPayload = ""

            for Query, Param in list(Params.items()):
                if Query == "Ids":
                    IdsLen = len(str(Param))

                    if Method == "GET" and IdsLen >= utils.MaxURILength:
                        xbmc.log(f"EMBY.emby.http: GET params exceeds maximum len, sending Ids as body: {IdsLen}/{utils.MaxURILength}", 2) # LOGWARNING
                        GETPayload = Param
                    else:
                        ParamsString += f"{quote_plus(str(Query))}={quote_plus(str(Param))}&"
                elif Param not in ([], None):
                    ParamsString += f"{quote_plus(str(Query))}={quote_plus(str(Param))}&"

            if ParamsString:
                ParamsString = f"?{ParamsString[:-1]}"

            if GETPayload:
                GETPayload = f'{{"Ids": "{GETPayload}"}}'
                Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler}{ParamsString} HTTP/1.1\r\n{HeaderString}Content-Length: {len(GETPayload.encode('utf-8'))}\r\n\r\n{GETPayload}"
            else:
                Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler}{ParamsString} HTTP/1.1\r\n{HeaderString}Content-Length: 0\r\n\r\n"

            StatusCodeSocket, _ = self.Common.socket_io(Request.encode("utf-8"), ConnectionId, TimeoutSend)
        else:
            if Params:
                ParamsString = json.dumps(Params)
            else:
                ParamsString = ""

            Request = f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler} HTTP/1.1\r\n{HeaderString}Content-Length: {len(ParamsString.encode('utf-8'))}\r\n\r\n{ParamsString}"
            StatusCodeSocket, _ = self.Common.socket_io(Request.encode("utf-8"), ConnectionId, TimeoutSend)

        if StatusCodeSocket:
            self.Requests_Counter(False)
            return StatusCodeSocket, {}, ""

        PayloadRequestStart = 0
        PayloadRequestEnd = None

        while True:
            if b'\r\n\r\n' not in IncomingData:
                StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)
                IncomingData += PayloadRecv

                if StatusCodeSocket or utils.SystemShutdown:
                    self.closeDownload(OutFile)
                    self.Requests_Counter(False)
                    return StatusCodeSocket, {}, ""

                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Incomplete header", 1) # LOGDEBUG
                continue

            IncomingDataHeaderData, IncomingDataPayload = IncomingData.split(b'\r\n\r\n', 1)

            try:
                IncomingMetaData = IncomingDataHeaderData.decode("latin-1").split("\r\n")
                StatusLine = IncomingMetaData[0].split(" ", 2)
                HttpVersion = StatusLine[0]
                StatusCode = int(StatusLine[1])
            except Exception as error: # Can happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Info: {error}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Binary: {Binary}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Request: {Request}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: IncomingData: {IncomingData}", 3) # LOGERROR
                self.closeDownload(OutFile)
                self.Requests_Counter(False)
                return 612, {}, ""

            IncomingDataHeaderArray = IncomingMetaData[1:]
            IncomingDataHeader = {}

            for IncomingDataHeaderArrayData in IncomingDataHeaderArray:
                Temp = IncomingDataHeaderArrayData.split(":", 1)
                HeaderKey = Temp[0].strip().lower()
                HeaderValue = Temp[1].strip()

                if HeaderKey == "content-length" and HeaderKey in IncomingDataHeader:
                    IncomingDataHeader[HeaderKey] += f",{HeaderValue}"
                elif HeaderKey in ("content-encoding", "transfer-encoding", "connection") and HeaderKey in IncomingDataHeader:
                    IncomingDataHeader[HeaderKey] += f",{HeaderValue}"
                else:
                    IncomingDataHeader[HeaderKey] = HeaderValue

            ConnectionTokens = set()

            for Token in IncomingDataHeader.get("connection", "").lower().split(","):
                Token = Token.strip()

                if Token:
                    ConnectionTokens.add(Token)

            if "close" in ConnectionTokens:
                CloseDelimited = True
            elif HttpVersion == "HTTP/1.0" and "keep-alive" not in ConnectionTokens:
                CloseDelimited = True

            if 100 <= StatusCode < 200:
                if StatusCode == 101:
                    self.closeDownload(OutFile)
                    self.Requests_Counter(False)
                    return StatusCode, IncomingDataHeader, IncomingDataPayload

                IncomingData = IncomingDataPayload
                continue

            if StatusCode in (304, 204) or Method == "HEAD":
                self.closeDownload(OutFile)

                if IncomingDataPayload or CloseDelimited:
                    self.Common.socket_close(ConnectionId)

                self.Requests_Counter(False)

                if Binary:
                    return StatusCode, IncomingDataHeader, b""

                return StatusCode, IncomingDataHeader, ""

            # Decompress flags
            ContentEncodings = []

            for Encoding in IncomingDataHeader.get("content-encoding", "").lower().split(","):
                Encoding = Encoding.strip()

                if Encoding:
                    ContentEncodings.append(Encoding)

            # Recv payload
            TransferEncoding = IncomingDataHeader.get('transfer-encoding', "").lower()
            TransferEncodings = []

            for Encoding in TransferEncoding.split(","):
                Encoding = Encoding.strip()

                if Encoding:
                    TransferEncodings.append(Encoding)

            PayloadOutFile = OutFile

            if OutFile:
                for Encoding in ContentEncodings:
                    if Encoding in ("gzip", "x-gzip", "deflate"):
                        PayloadOutFile = None
                        break

                for Encoding in TransferEncodings:
                    if Encoding in ("gzip", "x-gzip", "deflate"):
                        PayloadOutFile = None
                        break

            try:
                PayloadTotalLengthBeforeRequest = PayloadTotalLength

                if PayloadTotalLength:
                    if StatusCode == 200 and (PayloadRequestStart > 0 or PayloadTotalLength > 0):
                        if OutFile and PayloadOutFile is not None:
                            OutFile.seek(0)
                            OutFile.truncate(0)

                        PayloadTotal = ()
                        PayloadTotalLength = 0
                        PayloadRequestStart = 0
                        PayloadRequestEnd = None
                else:
                    PayloadRequestStart = 0
                    PayloadRequestEnd = None

                    for HeaderKey, HeaderValue in self.Connection[ConnectionId]["RequestHeader"].items():
                        if HeaderKey.lower() != "range":
                            continue

                        RangeValue = HeaderValue.strip()

                        if not RangeValue.lower().startswith("bytes="):
                            continue

                        RangeData = RangeValue[6:].split(",", 1)

                        if len(RangeData) != 1:
                            continue

                        RangePositions = RangeData[0].strip().split("-", 1)

                        if len(RangePositions) != 2:
                            continue

                        RangeStart = RangePositions[0].strip()
                        RangeEnd = RangePositions[1].strip()

                        if not RangeStart:
                            continue

                        for Character in RangeStart:
                            if Character not in "0123456789":
                                RangeStart = ""
                                break

                        if not RangeStart:
                            continue

                        PayloadRequestStart = int(RangeStart)

                        if RangeEnd:
                            for Character in RangeEnd:
                                if Character not in "0123456789":
                                    RangeEnd = ""
                                    break

                            if not RangeEnd:
                                continue

                            PayloadRequestEnd = int(RangeEnd)

                        break

                if TransferEncodings and TransferEncodings[-1] == "chunked":
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByChunks(PayloadTotal, PayloadTotalLength, IncomingDataPayload, ConnectionId, TimeoutRecv, DownloadName, PayloadOutFile, ProgressBarTotal)
                elif "content-length" in IncomingDataHeader and not TransferEncoding:
                    ContentLengthValue = int(IncomingDataHeader["content-length"].split(",", 1)[0].strip())
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadByFrames(PayloadTotal, PayloadTotalLength, IncomingDataPayload, ConnectionId, TimeoutRecv, ContentLengthValue, DownloadName, PayloadOutFile, ProgressBarTotal)
                else:
                    PayloadTotal, PayloadTotalLength, StatusCodeSocket = self.getPayloadUntilClose(PayloadTotal, PayloadTotalLength, IncomingDataPayload, ConnectionId, TimeoutRecv, DownloadName, PayloadOutFile, ProgressBarTotal)
                    CloseDelimited = True

                if StatusCodeSocket:
                    self.closeDownload(OutFile)
                    self.Requests_Counter(False)
                    return StatusCodeSocket, {}, ""

                # request additional data
                if StatusCode == 206: # partial content
                    ContentRange = IncomingDataHeader["content-range"].split("/", 1)
                    ContentRangeStart, ContentRangeEnd = ContentRange[0].split(" ", 1)[1].split("-", 1)
                    ContentRangeStart = int(ContentRangeStart)
                    ContentRangeEnd = int(ContentRangeEnd)

                    ContentSize = ContentRange[1].strip()
                    ContentSizeUnknown = ContentSize == "*"

                    if not ContentSizeUnknown:
                        ContentSize = int(ContentSize)

                    if ContentRangeStart != PayloadRequestStart:
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return 612, {}, ""

                    if ContentRangeEnd < ContentRangeStart:
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return 612, {}, ""

                    if not ContentSizeUnknown and ContentSize <= ContentRangeEnd:
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return 612, {}, ""

                    if ContentRangeEnd - ContentRangeStart + 1 != PayloadTotalLength - PayloadTotalLengthBeforeRequest:
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return 612, {}, ""

                    if PayloadRequestEnd is not None:
                        if ContentRangeEnd > PayloadRequestEnd:
                            self.closeDownload(OutFile)
                            self.Requests_Counter(False)
                            return 612, {}, ""

                        if ContentSizeUnknown:
                            RequestComplete = ContentRangeEnd == PayloadRequestEnd
                        else:
                            RequestComplete = ContentRangeEnd == min(PayloadRequestEnd, ContentSize - 1)
                    elif ContentSizeUnknown:
                        RequestComplete = True
                    else:
                        RequestComplete = ContentRangeEnd == ContentSize - 1

                    if RequestComplete:
                        if PayloadRequestStart == 0 and PayloadRequestEnd is None and not ContentSizeUnknown and ContentSize == PayloadTotalLength:
                            StatusCode = 200

                        if CloseDelimited:
                            self.Common.socket_close(ConnectionId)

                        break

                    xbmc.log(f"EMBY.emby.http: Partial content {ConnectionId}", 1) # LOGINFO

                    PayloadRequestStart = ContentRangeEnd + 1

                    if CloseDelimited:
                        self.Common.socket_close(ConnectionId)
                        StatusCodeConnect = self.Common.socket_open(ConnectionString, ConnectionId, CloseConnection)

                        if StatusCodeConnect:
                            self.closeDownload(OutFile)
                            self.Requests_Counter(False)
                            return StatusCodeConnect, {}, ""

                        CloseDelimited = False

                    if Method == "GET":
                        FollowUpHeaderString = ""

                        for HeaderLine in HeaderString.split("\r\n"):
                            if HeaderLine and HeaderLine.split(":", 1)[0].strip().lower() != "range":
                                FollowUpHeaderString += f"{HeaderLine}\r\n"

                        if PayloadRequestEnd is None:
                            RangeHeader = f"Range: bytes={PayloadRequestStart}-"
                        else:
                            RangeHeader = f"Range: bytes={PayloadRequestStart}-{PayloadRequestEnd}"

                        StatusCodeSocket, _ = self.Common.socket_io(f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler}{ParamsString} HTTP/1.1\r\n{FollowUpHeaderString}{RangeHeader}\r\nContent-Length: 0\r\n\r\n".encode("utf-8"), ConnectionId, TimeoutSend)
                    else:
                        StatusCodeSocket, _ = self.Common.socket_io(f"{Method} {self.Connection[ConnectionId]['SubUrl']}{Handler} HTTP/1.1\r\n{HeaderString}Content-Length: {len(ParamsString.encode('utf-8'))}\r\n\r\n{ParamsString}".encode("utf-8"), ConnectionId, TimeoutSend)

                    if StatusCodeSocket:
                        self.closeDownload(OutFile)
                        self.Requests_Counter(False)
                        return StatusCodeSocket, {}, ""

                    IncomingData = b""
                    continue

                if CloseDelimited:
                    self.Common.socket_close(ConnectionId)

                break
            except Exception as error: # Could happen on Emby server hard reboot
                xbmc.log(f"EMBY.emby.http: Header error {ConnectionId}: Undefined error {error}: IncomingDataHeader: {IncomingDataHeader}", 3) # LOGERROR
                self.closeDownload(OutFile)
                self.Requests_Counter(False)
                return 612, {}, ""

        PayloadTotal = b''.join(PayloadTotal)

        # Decompress transfer encoding
        try:
            for Encoding in reversed(TransferEncodings):
                if Encoding in ("gzip", "x-gzip"):
                    PayloadTotal = gzip.decompress(PayloadTotal)
                elif Encoding == "deflate": # Emby server bug, not RFC conform
                    try:
                        PayloadTotal = zlib.decompress(PayloadTotal, zlib.MAX_WBITS)
                    except:
                        PayloadTotal = zlib.decompress(PayloadTotal, -zlib.MAX_WBITS)
        except Exception as error:
            self.closeDownload(OutFile)
            xbmc.log(f"EMBY.emby.http: Transfer decompress issue {ConnectionId}: {IncomingDataHeader} error: {error}", 3) # LOGERROR
            self.Requests_Counter(False)
            return 612, {}, ""

        # Decompress data
        try:
            for Encoding in reversed(ContentEncodings):
                if Encoding == "deflate": # Emby server bug, not RFC conform
                    try:
                        PayloadTotal = zlib.decompress(PayloadTotal, zlib.MAX_WBITS)
                    except:
                        PayloadTotal = zlib.decompress(PayloadTotal, -zlib.MAX_WBITS)
                elif Encoding in ("gzip", "x-gzip"):
                    PayloadTotal = gzip.decompress(PayloadTotal)
        except Exception as error: # could happen on server overload
            self.closeDownload(OutFile)
            xbmc.log(f"EMBY.emby.http: Decompress issue {ConnectionId}: {IncomingDataHeader} error: {error}", 3) # LOGERROR
            self.Requests_Counter(False)
            return 612, {}, ""

        if Binary:
            if OutFile and PayloadOutFile is None:
                OutFile.write(PayloadTotal)

                if ProgressBarTotal:
                    utils.update_ProgressBar(self.DownloadId, len(PayloadTotal) / ProgressBarTotal, utils.Translate(33760), DownloadName)

            self.closeDownload(OutFile)
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
                Charset = "utf-8"
                ContentType = IncomingDataHeader.get("content-type", "")

                for Parameter in ContentType.split(";")[1:]:
                    if "=" not in Parameter:
                        continue

                    ParameterKey, ParameterValue = Parameter.split("=", 1)

                    if ParameterKey.strip().lower() == "charset":
                        Charset = ParameterValue.strip().strip('"').strip("'")
                        break

                return StatusCode, IncomingDataHeader, PayloadTotal.decode(Charset)
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Invalid text content {ConnectionId}: {IncomingDataHeader} error: {error}", 3) # LOGERROR
                return 612, {}, ""

    def download_file(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Download {self.ServerData['ServerId']} ]", 1) # LOGDEBUG
        ProgressBar = False

        while True:
            Command = self.Queues["DOWNLOAD"].get()

            if Command == "QUIT":
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Download {self.ServerData['ServerId']}\u0020] shutdown 1", 1) # LOGDEBUG
                self.Common.socket_close("DOWNLOAD")
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
                self.Common.socket_close("DOWNLOAD")
                utils.close_ProgressBar(self.DownloadId)
                self.disable_thread("DOWNLOAD")
                return

            while True:
                if not self.Running or utils.SystemShutdown:
                    self.Common.socket_close("DOWNLOAD")
                    utils.close_ProgressBar(self.DownloadId)
                    self.disable_thread("DOWNLOAD")
                    return

                if self.Common.socket_open(self.ServerData['ServerUrl'], "DOWNLOAD", True):
                    if utils.sleep(10):
                        if utils.DebugLog: xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.ServerData['ServerId']} shutdown ]", 1) # LOGDEBUG
                        self.disable_thread("DOWNLOAD")
                        return

                    continue

                if not self.Running or utils.SystemShutdown:
                    self.Common.socket_close("DOWNLOAD")
                    utils.close_ProgressBar(self.DownloadId)
                    self.disable_thread("DOWNLOAD")
                    return

                self.update_header("DOWNLOAD")

                if not ProgressBar:
                    utils.create_ProgressBar(self.DownloadId, utils.Translate(33814), MediaName)

                ProgressBarTotal = FileSize / 100
                PathDownloadMedia = xbmcvfs.translatePath(os.path.join(PathDownload, KodiType, KodiFileId, ""))
                utils.mkDir(PathDownloadMedia)
                PathDownloadMediaFile = os.path.join(PathDownloadMedia, Filename)
                OutFile = open(PathDownloadMediaFile, 'wb')
                StatusCode, _, _ = self.socket_request("GET", f"Items/{EmbyId}/Download", {}, True, 12, 300, "DOWNLOAD", MediaName, OutFile, ProgressBarTotal, self.ServerData['ServerUrl'], True)
                ProgressBarTotal = 0
                OutFile = None

                if StatusCode == 601 or utils.SystemShutdown: # quit
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Download {self.ServerData['ServerId']} ] shutdown 2", 1) # LOGDEBUG
                    utils.delFile(PathDownloadMediaFile)
                    self.Common.socket_close("DOWNLOAD")
                    utils.close_ProgressBar(self.DownloadId)
                    self.disable_thread("DOWNLOAD")
                    return

                if StatusCode in (600, 602, 603, 605, 612):
                    xbmc.log(f"EMBY.emby.http: Download retry {StatusCode}", 2) # LOGWARNING
                    utils.delFile(PathDownloadMediaFile)
                    self.Common.socket_close("DOWNLOAD")
                    continue

                try:
                    if StatusCode != 200 or utils.SystemShutdown:
                        utils.delFile(PathDownloadMediaFile)
                    else:
                        if KodiMediaId: # KodiId
                            SQLs = {}
                            dbio.DBOpenRW("video", "download_item_replace", SQLs)
                            TextureDBUrls = SQLs['video'].download_Artwork(KodiMediaId, KodiType, True)
                            SQLs['video'].update_Name(KodiMediaId, KodiType, True)
                            SQLs['video'].replace_Path_ContentItem(KodiMediaId, KodiType, PathDownloadMedia, PathDownloadMediaFile)

                            if KodiType == "episode":
                                DownloadPathParent = xbmcvfs.translatePath(os.path.join(PathDownload, KodiType, ""))
                                KodiParentPathId = SQLs['video'].get_add_path(DownloadPathParent, "tvshows", None)
                                KodiPathIdNew = SQLs['video'].get_add_path(PathDownloadMedia, None, KodiParentPathId)
                                TextureDBUrls += SQLs['video'].download_Subcontent(KodiMediaId, True)
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
                                dbio.DBOpenRW(self.ServerData['ServerId'], "download_item", SQLs)
                                SQLs['emby'].add_DownloadItem(EmbyId, KodiPathId, KodiFileId, KodiMediaId, KodiType, KodiPathIdNew)
                                dbio.DBCloseRW(self.ServerData['ServerId'], "download_item", SQLs)

                            if TextureDBUrls:
                                artworkcache.CacheAllEntries(TextureDBUrls, "")

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

        RequestId = f"REQUEST{ConnectionId}_{uuid.uuid4()}"
        self.Response[RequestId] = False
        self.RequestBusy[RequestId] = threading.Lock()
        self.RequestBusy[RequestId].acquire()
        Canceled = False

        # Simple request
        if CloseConnection or not BusyFunction or not self.ThreadsRunning["QUEUEDREQUESTMAIN"] or not self.ThreadsRunning["QUEUEDREQUESTMAINFALLBACK"]:
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)
            Data = self.Response[RequestId]
            del self.Response[RequestId]
            del self.RequestBusy[RequestId]

            if ConnectionId in ("MAIN", "MAINFALLBACK"):
                self.RequestBusy[ConnectionId].release()

            return Data

        with utils.SafeLock(self.Connecting):
            if not self.Running:
                del self.Response[RequestId]
                del self.RequestBusy[RequestId]

                if ConnectionId in self.RequestBusy and self.RequestBusy[ConnectionId].locked():
                    self.RequestBusy[ConnectionId].release()

                return noData(601, {}, Binary)

            if ConnectionId not in ("MAIN", "MAINFALLBACK"):
                self.Queues[f"QUEUEDREQUEST{ConnectionId}"] = queue.Queue()
                utils.start_thread(self.queued_request, (ConnectionId,))

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
                with utils.SafeLock(self.ResponseLock):
                    if self.Response[RequestId]:
                        ReturnData = self.Response[RequestId]
                        self.RequestBusy[ConnectionId].release()
                        del self.Response[RequestId]
                        break

                    self.ResponseCanceled.add(RequestId)
                    Canceled = True

                ReturnData = noData(601, {}, Binary)
                break

        if ConnectionId not in ("MAIN", "MAINFALLBACK"):
            self.Queues[f"QUEUEDREQUEST{ConnectionId}"].put("QUIT")

            if not Canceled:
                del self.RequestBusy[ConnectionId]
                del self.RequestBusy[RequestId]
        elif not Canceled:
            del self.RequestBusy[RequestId]

        return ReturnData

    def queued_request(self, ConnectionId):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Queued request {ConnectionId}: {self.ServerData['ServerId']} ]", 1) # LOGDEBUG

        while True:
            Incoming = self.Queues[f"QUEUEDREQUEST{ConnectionId}"].get()

            if Incoming == "QUIT":
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Queued request {ConnectionId}: {self.ServerData['ServerId']} ] shutdown 1", 1) # LOGDEBUG

                if ConnectionId not in ("MAIN", "MAINFALLBACK"):
                    del self.Queues[f"QUEUEDREQUEST{ConnectionId}"]
                else:
                    self.disable_thread(f"QUEUEDREQUEST{ConnectionId}")

                return

            Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, RequestId = Incoming
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http: [ http ] Method: {Method} / Handler: {Handler} / Params: {Params} / Binary: {Binary} / ConnectionString: {ConnectionString} / CloseConnection: {CloseConnection} / RequestHeader: {RequestHeader}", 1) # LOGDEBUG
            self.send_request(Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId)

    def send_request(self, Method, Handler, Params, RequestHeader, Binary, ConnectionString, CloseConnection, ConnectionId, RequestId):
        if not ConnectionString:
            ConnectionString = self.ServerData['ServerUrl']

        RedirectedCrossOrigin = False
        RetryCounter = 0

        if not CloseConnection and ConnectionId in self.Connection:
            Scheme, Hostname, Port, SubUrl = utils.get_url_info(ConnectionString)

            if Hostname != self.Connection[ConnectionId]["Hostname"] or Port != self.Connection[ConnectionId]["Port"] or SubUrl != self.Connection[ConnectionId]["SubUrl"] or bool(Scheme == "https") != self.Connection[ConnectionId]["SSL"]:
                self.Common.socket_close(ConnectionId)

        RedirectedLocations = set()
        RedirectCounter = 0

        while True:
            # Shutdown
            if utils.SystemShutdown:
                self.Common.socket_close(ConnectionId)
                self.Response[RequestId] = noData(0, {}, Binary)
                if utils.DebugLog: xbmc.log(f"EMBY.emby.http: THREAD: ---<[ Request {self.ServerData['ServerId']} ] shutdown 2", 1) # LOGDEBUG
                break

            # open socket
            if ConnectionId not in self.Connection:
                StatusCodeConnect = self.Common.socket_open(ConnectionString, ConnectionId, CloseConnection)

                if StatusCodeConnect:
                    if StatusCodeConnect not in (608, 609, 610, 611): # wrong Emby server address or SSL issue
                        if self.ServerData['ServerId'] in utils.EmbyServers:
                            utils.EmbyServers[self.ServerData['ServerId']].ServerReconnect(True)

                    self.Response[RequestId] = noData(StatusCodeConnect, {}, Binary)
                    break

            # Update Header information
            if RequestHeader:
                if ":" in self.Connection[ConnectionId]["Hostname"]:
                    HostHeader = f'[{self.Connection[ConnectionId]["Hostname"]}]:{self.Connection[ConnectionId]["Port"]}'
                else:
                    HostHeader = f'{self.Connection[ConnectionId]["Hostname"]}:{self.Connection[ConnectionId]["Port"]}'

                self.Connection[ConnectionId]["RequestHeader"].update({"Host": HostHeader, 'Accept': "application/json", 'Accept-Charset': "utf-8", 'X-Application': f"{utils.addon_name}/{utils.addon_version}", 'Content-Type': 'application/json'})
                self.Connection[ConnectionId]["RequestHeader"].update(RequestHeader)
            else:
                self.update_header(ConnectionId)

            if RedirectedCrossOrigin:
                RedirectedRequestHeader = {}

                for Key, Value in self.Connection[ConnectionId]["RequestHeader"].items():
                    if Key.lower() not in ("authorization", "x-emby-token"):
                        RedirectedRequestHeader[Key] = Value

                self.Connection[ConnectionId]["RequestHeader"] = RedirectedRequestHeader

            # Request data with different timeout settings
            if Handler == "System/Ping":
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 6, ConnectionId, "", None, 0, ConnectionString, CloseConnection)
            elif "Subtitles" in Handler:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 30, ConnectionId, "", None, 0, ConnectionString, CloseConnection)
            else:
                StatusCode, Header, Payload = self.socket_request(Method, Handler, Params, Binary, 12, 1200, ConnectionId, "", None, 0, ConnectionString, CloseConnection)

            # Redirects
            if StatusCode in (301, 302, 303, 307, 308):
                LocationHeader = Header.get("location", "")

                if not LocationHeader:
                    self.Response[RequestId] = (StatusCode, Header, Payload)
                    break

                RedirectCounter += 1

                if RedirectCounter > 5:
                    xbmc.log(f"EMBY.emby.http: Maximum redirects exceeded: {ConnectionId}", 2) # LOGWARNING
                    self.Common.socket_close(ConnectionId)
                    self.Response[RequestId] = (StatusCode, Header, Payload)
                    break

                RedirectBase = f'{ConnectionString.rstrip("/")}/{self.Connection[ConnectionId]["SubUrl"].strip("/")}/{Handler.lstrip("/")}'

                if Method in ("GET", "HEAD") and Params:
                    ParamsString = ""

                    for Query, Param in list(Params.items()):
                        if Query == "Ids":
                            IdsLen = len(str(Param))

                            if IdsLen < utils.MaxURILength:
                                ParamsString += f"{quote_plus(str(Query))}={quote_plus(str(Param))}&"
                        elif Param not in ([], None):
                            ParamsString += f"{quote_plus(str(Query))}={quote_plus(str(Param))}&"

                    if ParamsString:
                        RedirectBase += f"?{ParamsString[:-1]}"

                Location = urljoin(RedirectBase, LocationHeader).split("#", 1)[0]

                if Location in RedirectedLocations:
                    xbmc.log(f"EMBY.emby.http: Redirect loop detected: {Location}", 2) # LOGWARNING
                    self.Common.socket_close(ConnectionId)
                    self.Response[RequestId] = (StatusCode, Header, Payload)
                    break

                RedirectedLocations.add(Location)
                CurrentSubUrl = self.Connection[ConnectionId]["SubUrl"]
                self.Common.socket_close(ConnectionId)
                CurrentScheme, CurrentHostname, CurrentPort, _ = utils.get_url_info(ConnectionString)
                Scheme, Hostname, Port, _ = utils.get_url_info(Location)

                if CurrentScheme.lower() != Scheme.lower() or CurrentHostname.lower() != Hostname.lower() or CurrentPort != Port:
                    RedirectedCrossOrigin = True

                Scheme, Hostname, Port, _ = utils.get_url_info(Location)
                ConnectionString = f"{Scheme}://{Hostname}:{Port}"

                LocationParts = urlsplit(Location)
                Handler = LocationParts.path.lstrip("/")

                if LocationParts.query:
                    Handler += f"?{LocationParts.query}"

                if Method in ("GET", "HEAD"):
                    Params = {}
                elif StatusCode == 303 and Method not in ("GET", "HEAD"):
                    Method = "GET"
                    Params = {}

                if ConnectionId == "MAIN" and StatusCode in (301, 308) and not RedirectedCrossOrigin:
                    self.ServerData['ServerUrl'] = f"{Scheme}://{Hostname}:{Port}{CurrentSubUrl}"

                continue

            if CloseConnection:
                self.Common.socket_close(ConnectionId)

            if StatusCode in (200, 206): # OK / partial content
                self.Response[RequestId] = (StatusCode, Header, Payload)
                break

            if StatusCode == 204: # OK, no data
                self.Response[RequestId] = (StatusCode, Header, Payload)
                break

            if StatusCode == 401: # Unauthorized
                Text = f"{utils.Translate(33147)}\n{str(Payload)}"
                xbmc.log(f"EMBY.emby.http: Request unauthorized {StatusCode} / {ConnectionId} / {Text}", 3) # LOGERROR
                utils.Dialog.notification(heading=utils.addon_name, message=Text, time=utils.displayMessage)

                if self.ServerData['ServerId'] in utils.EmbyServers:
                    utils.EmbyServers[self.ServerData['ServerId']].ServerDisconnect(True)

                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 403: # Access denied
                Text = f"{utils.Translate(33696)}\n{str(Payload)}"
                xbmc.log(f"EMBY.emby.http: Request access denied {StatusCode} / {ConnectionId} / {Text}", 3) # LOGERROR
                utils.Dialog.notification(heading=utils.addon_name, message=Text, time=utils.displayMessage)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 605:
                self.Common.socket_close(ConnectionId)

                if self.ServerData['ServerId'] in utils.EmbyServers:
                    utils.EmbyServers[self.ServerData['ServerId']].ServerReconnect(True)

                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode in (600, 698): # no data received, broken pipes, undefined error, Socket IO error
                if Method in ("GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"):
                    RetryCounter += 1
                    xbmc.log(f"EMBY.emby.http: Request retry {StatusCode} / {ConnectionId}: {RetryCounter}/10", 2) # LOGWARNING
                    self.Common.socket_close(ConnectionId)

                    if not self.Running or utils.SystemShutdown:
                        self.Response[RequestId] = noData(601, {}, Binary)
                        break

                    if RetryCounter >= 10:
                        self.Response[RequestId] = noData(StatusCode, {}, Binary)
                        break

                    continue

                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode in (602, 603): # timeouts
                xbmc.log(f"EMBY.emby.http: Request timeout {StatusCode} / {ConnectionId}", 2) # LOGWARNING
                self.Common.socket_close(ConnectionId)
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 601: # quit
                self.Response[RequestId] = noData(StatusCode, {}, Binary)
                break

            if StatusCode == 503: # Service Unavailable, usually happens when server is (re)booting
                xbmc.log(f"EMBY.emby.http: Service Unavailable {StatusCode} / {ConnectionId} / {Handler} / {Params}", 3) # LOGERROR
                self.Response[RequestId] = noData(StatusCode, {}, Binary)

                if self.ServerData['ServerId'] in utils.EmbyServers:
                    utils.EmbyServers[self.ServerData['ServerId']].ServerReconnect(True)

                break

            xbmc.log(f"EMBY.emby.http: [ Statuscode ] {StatusCode}", 3) # LOGERROR
            if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): [ Statuscode ] {Payload}", 1) # LOGDEBUG
            self.Response[RequestId] = noData(StatusCode, {}, Binary)
            break

        with utils.SafeLock(self.ResponseLock):
            if RequestId in self.ResponseCanceled:
                self.ResponseCanceled.remove(RequestId)

                if RequestId in self.Response:
                    del self.Response[RequestId]

                if RequestId in self.RequestBusy and self.RequestBusy[RequestId].locked():
                    self.RequestBusy[RequestId].release()

                if ConnectionId in self.RequestBusy and self.RequestBusy[ConnectionId].locked():
                    self.RequestBusy[ConnectionId].release()

                if ConnectionId not in ("MAIN", "MAINFALLBACK"):
                    if ConnectionId in self.RequestBusy:
                        del self.RequestBusy[ConnectionId]

                if RequestId in self.RequestBusy:
                    del self.RequestBusy[RequestId]
            elif RequestId in self.RequestBusy and self.RequestBusy[RequestId].locked():
                self.RequestBusy[RequestId].release()

    def update_header(self, ConnectionId):
        if 'X-Emby-Token' not in self.Connection[ConnectionId]["RequestHeader"] and self.ServerData['AccessToken'] and self.ServerData['UserId']:
            self.Connection[ConnectionId]["RequestHeader"].update({'Authorization': f'{self.Connection[ConnectionId]["RequestHeader"]["Authorization"]}, Emby UserId="{self.ServerData["UserId"]}"', 'X-Emby-Token': self.ServerData['AccessToken']})

    # No return values are expected, usually also lower priority
    def async_commands(self):
        if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: --->[ Async {self.ServerData['ServerId']} ]", 1) # LOGDEBUG

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
                    self.Common.socket_close("ASYNC")
                    self.disable_thread("ASYNC")
                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): THREAD: ---<[ Async {self.ServerData['ServerId']} ]", 1) # LOGDEBUG
                    return

    def async_commands_worker(self, Command, Priority):
        if Command[0] == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by QUIT", 1) # LOGDEBUG
            return True

        with utils.SafeLock(self.RequestBusy["ASYNC"]):
            while True:
                # Connect socket
                if "ASYNC" not in self.Connection:
                    if self.Common.socket_open(self.ServerData['ServerUrl'], "ASYNC", False):
                        if not self.Running or utils.sleep(1):
                            if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by Kodi shutdown", 1) # LOGDEBUG
                            return True

                        continue

                self.update_header("ASYNC")

                if Priority:
                    StatusCode, _, _ = self.socket_request(Command[0], Command[1], Command[2], True, 3, 3, "ASYNC", "", None, 0, self.ServerData['ServerUrl'], False)
                else:
                    StatusCode, _, _ = self.socket_request(Command[0], Command[1], Command[2], True, 1, 0.1, "ASYNC", "", None, 0, self.ServerData['ServerUrl'], False)

                if StatusCode == 601: # quit
                    if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by 601", 1) # LOGDEBUG
                    return True

                if StatusCode in (600, 605, 612, 698): # no data received, broken pipes, undefined error, Socket IO error -> Re-try
                    xbmc.log(f"EMBY.emby.http: Async retry {StatusCode}", 2) # LOGWARNING
                    self.Common.socket_close("ASYNC")

                    if not self.Running or utils.SystemShutdown:
                        if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): THREAD: Exit by not self.Running", 1) # LOGDEBUG
                        return True

                    continue

                if StatusCode in (602, 603): # timeouts
                    self.Common.socket_close("ASYNC")

                    if Priority:
                        xbmc.log(f"EMBY.emby.http: Async timeout {StatusCode}", 2) # LOGWARNING -> Emby server is sometimes not responsive, skip it

                    if utils.DebugLog: xbmc.log(f"EMBY.emby.http (DEBUG): Async timeout {StatusCode}", 1) # LOGDEBUG

                return False

    def getPayloadByFrames(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, PayloadFrameLenght, DownloadName, OutFile, ProgressBarTotal):
        PayloadFrameTotalLenght = PayloadFrameLenght + PayloadTotalLength

        if len(PayloadRecv) > PayloadFrameLenght:
            return None, None, 612

        PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

        while PayloadTotalLength < PayloadFrameTotalLenght:
            StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

            if StatusCodeSocket:
                return None, None, StatusCodeSocket

            PayloadRemaining = PayloadFrameTotalLenght - PayloadTotalLength

            if len(PayloadRecv) > PayloadRemaining:
                return None, None, 612

            PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

        return PayloadTotal, PayloadTotalLength, 0

    def getPayloadUntilClose(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBarTotal):
        PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

        while True:
            StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

            if StatusCodeSocket == 600 and not PayloadRecv:
                return PayloadTotal, PayloadTotalLength, 0

            if StatusCodeSocket:
                return None, None, StatusCodeSocket

            PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadRecv, OutFile, DownloadName, ProgressBarTotal)

    def getPayloadByChunks(self, PayloadTotal, PayloadTotalLength, PayloadRecv, ConnectionId, TimeoutRecv, DownloadName, OutFile, ProgressBarTotal):
        PayloadChunkBuffer = PayloadRecv

        while True:
            while b"\r\n" not in PayloadChunkBuffer:
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Load additional data", 1) # LOGDEBUG
                StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

                if StatusCodeSocket:
                    return None, None, StatusCodeSocket

                PayloadChunkBuffer += PayloadRecv

            ChunkedData = PayloadChunkBuffer.split(b"\r\n", 1)
            ChunkDataLen = int(ChunkedData[0].split(b";", 1)[0].strip(), 16)
            PayloadChunkBuffer = ChunkedData[1]

            if not ChunkDataLen:
                while b"\r\n" not in PayloadChunkBuffer:
                    StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

                    if StatusCodeSocket:
                        return None, None, StatusCodeSocket

                    PayloadChunkBuffer += PayloadRecv

                if PayloadChunkBuffer.startswith(b"\r\n"):
                    if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Data complete", 1) # LOGDEBUG
                    return PayloadTotal, PayloadTotalLength, 0

                while b"\r\n\r\n" not in PayloadChunkBuffer:
                    StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

                    if StatusCodeSocket:
                        return None, None, StatusCodeSocket

                    PayloadChunkBuffer += PayloadRecv

                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Data complete with trailers", 1) # LOGDEBUG
                return PayloadTotal, PayloadTotalLength, 0

            while len(PayloadChunkBuffer) < ChunkDataLen + 2:
                if utils.DebugLog: xbmc.log("EMBY.emby.http (DEBUG): Chunks: Insufficient data", 1) # LOGDEBUG
                StatusCodeSocket, PayloadRecv = self.Common.socket_io("", ConnectionId, TimeoutRecv)

                if StatusCodeSocket:
                    return None, None, StatusCodeSocket

                PayloadChunkBuffer += PayloadRecv

            PayloadTotalLength, PayloadTotal = self.processData(PayloadTotal, PayloadTotalLength, PayloadChunkBuffer[:ChunkDataLen], OutFile, DownloadName, ProgressBarTotal)
            PayloadChunkBuffer = PayloadChunkBuffer[ChunkDataLen + 2:]

    def closeDownload(self, OutFile):
        if OutFile:
            OutFile.close()

            if self.Queues['DOWNLOAD'].isEmpty():
                utils.close_ProgressBar(self.DownloadId)

    def disable_thread(self, Id):
        self.ThreadsRunning[Id] = False

        with utils.SafeLock(self.HTTPThreadsRunningCondition):
            self.HTTPThreadsRunningCondition.notify_all()

    def processData(self, PayloadTotal, PayloadTotalLength, Data, OutFile, DownloadName, ProgressBarTotal):
        PayloadTotalLength += len(Data)

        if OutFile:
            OutFile.write(Data)

            if ProgressBarTotal:
                utils.update_ProgressBar(self.DownloadId, PayloadTotalLength / ProgressBarTotal, utils.Translate(33760), DownloadName)
        else:
            PayloadTotal += (Data,)

        return PayloadTotalLength, PayloadTotal


# Return empty data
def noData(StatusCode, Header, Binary):
    if Binary:
        return (StatusCode, Header, b"")

    return (StatusCode, Header, {})

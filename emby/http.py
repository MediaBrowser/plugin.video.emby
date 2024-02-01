from _thread import start_new_thread
import socket
import requests
import xbmc
import xbmcgui
from helper import utils, queue, artworkcache
from database import dbio
from core import common

# Patching requests to disable Nagle
try:
    from requests.packages.urllib3 import connectionpool
    _HTTPConnection = connectionpool.HTTPConnection
    _HTTPSConnection = connectionpool.HTTPSConnection

    class HTTPConnection(_HTTPConnection):
        def connect(self):
            _HTTPConnection.connect(self)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    class HTTPSConnection(_HTTPSConnection):
        def connect(self):
            _HTTPSConnection.connect(self)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    connectionpool.HTTPConnection = HTTPConnection
    connectionpool.HTTPSConnection = HTTPSConnection
except Exception as NagleError:
    xbmc.log(f"EMBY.emby.http: disable Nagle failed, error: {NagleError}", 2) # LOGWARNING

class HTTP:
    def __init__(self, EmbyServer):
        self.session = None
        self.EmbyServer = EmbyServer
        self.Intros = []
        self.HeaderCache = {}
        self.AsyncCommandQueue = queue.Queue()
        self.FileDownloadQueue = queue.Queue()
        self.Priority = False

    def download_file(self):
        xbmc.log("EMBY.emby.http: THREAD: --->[ async file download ]", 0) # LOGDEBUG

        while True:
            Command = self.FileDownloadQueue.get()

            if Command == "QUIT":
                xbmc.log("EMBY.emby.http: Download Queue closed", 1) # LOGINFO
                self.FileDownloadQueue.clear()
                break

            self.wait_for_priority_request()
            data = Command[0]
            Download = Command[1]

            if utils.getFreeSpace(Download["Path"]) < (2097152 + Download["FileSize"] / 1024): # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=5000, sound=True)
                xbmc.log("EMBY.emby.http: THREAD: ---<[ async file download ] terminated by filesize", 2) # LOGWARNING
                return

            ProgressBar = xbmcgui.DialogProgressBG()
            ProgressBar.create("Download", Download["Name"])
            ProgressBarTotal = Download["FileSize"] / 100
            ProgressBarCounter = 0
            Terminate = False

            try:
                with self.session.get(**data, stream=True) as r:
                    with open(Download["FilePath"], 'wb') as outfile:
                        for chunk in r.iter_content(chunk_size=4194304): # 4 MB chunks
                            outfile.write(chunk)
                            ProgressBarCounter += 4194304

                            if ProgressBarCounter > Download["FileSize"]:
                                ProgressBarCounter = Download["FileSize"]

                            ProgressBar.update(int(ProgressBarCounter / ProgressBarTotal), "Download", Download["Name"])

                            if utils.SystemShutdown:
                                r.close()
                                Terminate = True
                                break

                if Terminate:
                    utils.delFile(Download["FilePath"])
                else:
                    if "KodiId" in Download:
                        SQLs = dbio.DBOpenRW(self.EmbyServer.ServerData['ServerId'], "download_item", {})
                        SQLs['emby'].add_DownloadItem(Download["Id"], Download["KodiPathIdBeforeDownload"], Download["KodiFileId"], Download["KodiId"], Download["KodiType"])
                        dbio.DBCloseRW(self.EmbyServer.ServerData['ServerId'], "download_item", {})
                        SQLs = dbio.DBOpenRW("video", "download_item_replace", {})
                        Artworks = ()
                        ArtworksData = SQLs['video'].get_artworks(Download["KodiId"], Download["KodiType"])

                        for ArtworkData in ArtworksData:
                            if ArtworkData[3] in ("poster", "thumb", "landscape"):
                                UrlMod = ArtworkData[4].split("|")
                                UrlMod = f"{UrlMod[0].replace('-download', '')}-download|redirect-limit=1000"
                                SQLs['video'].update_artwork(ArtworkData[0], UrlMod)
                                Artworks += ((UrlMod,),)

                        SQLs['video'].update_Name(Download["KodiId"], Download["KodiType"], True)
                        SQLs['video'].replace_Path_ContentItem(Download["KodiId"], Download["KodiType"], Download["Path"])

                        if Download["KodiType"] == "episode":
                            KodiPathId = SQLs['video'].get_add_path(Download["Path"], None, Download["ParentPath"])
                            Artworks = SQLs['video'].set_Subcontent_download_tags(Download["KodiId"], True)

                            if Artworks:
                                artworkcache.CacheAllEntries(Artworks, None)
                        elif Download["KodiType"] == "movie":
                            KodiPathId = SQLs['video'].get_add_path(Download["Path"], "movie", None)
                        elif Download["KodiType"] == "musicvideo":
                            KodiPathId = SQLs['video'].get_add_path(Download["Path"], "musicvideos", None)

                        SQLs['video'].replace_PathId(Download["KodiFileId"], KodiPathId)
                        dbio.DBCloseRW("video", "download_item_replace", {})
                        artworkcache.CacheAllEntries(Artworks, ProgressBar)

                ProgressBar.close()
                del ProgressBar

                if self.FileDownloadQueue.isEmpty():
                    utils.refresh_widgets(True)
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Download Emby server did not respond: error: {error}", 2) # LOGWARNING
                ProgressBar.close()
                del ProgressBar

        xbmc.log("EMBY.emby.http: THREAD: ---<[ async file download ]", 0) # LOGDEBUG

    def async_commands(self):
        xbmc.log("EMBY.emby.http: THREAD: --->[ async queue ]", 0) # LOGDEBUG
        PingTimeoutCounter = 0

        while True:
            Command = self.AsyncCommandQueue.get()

            try:
                if Command == "QUIT":
                    xbmc.log("EMBY.emby.http: Queue closed", 1) # LOGINFO
                    self.AsyncCommandQueue.clear()
                    break

                self.wait_for_priority_request()

                if Command[0] == "POST":
                    Command[1]['timeout'] = (5, 2)
                    r = self.session.post(**Command[1])
                    r.close()
                elif Command[0] == "DELETE":
                    Command[1]['timeout'] = (5, 2)
                    r = self.session.delete(**Command[1])
                    r.close()

                if Command[1]['url'].find("System/Ping") != -1:
                    PingTimeoutCounter = 0
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: Async_commands Emby server did not respond: error: {error}", 2) # LOGWARNING

                if Command[1]['url'].find("System/Ping") != -1: # ping timeout
                    if PingTimeoutCounter == 4:
                        xbmc.log("EMBY.emby.http: Ping re-establish connection", 2) # LOGWARNING
                        self.EmbyServer.ServerReconnect()
                    else:
                        PingTimeoutCounter += 1
                        xbmc.log(f"EMBY.emby.http: Ping timeout: {PingTimeoutCounter}", 2) # LOGWARNING

        xbmc.log("EMBY.emby.http: THREAD: ---<[ async queue ]", 0) # LOGDEBUG

    def wait_for_priority_request(self):
        LOGDone = False

        while self.Priority:
            if not LOGDone:
                LOGDone = True
                xbmc.log("EMBY.emby.http: Delay queries, priority request in progress", 1) # LOGINFO

            if utils.sleep(0.1):
                return

        if LOGDone:
            xbmc.log("EMBY.emby.http: Delay queries, continue", 1) # LOGINFO

    def stop_session(self):
        if not self.session:
            xbmc.log("EMBY.emby.http: Session close: No session found", 0) # LOGDEBUG
            return

        LocalSession = self.session  # Use local var -> self.session must be set to "none" instantly -> self var is also used to detect open sessions
        self.session = None
        self.AsyncCommandQueue.put("QUIT")
        self.FileDownloadQueue.put("QUIT")

        try:
            LocalSession.close()
        except Exception as error:
            xbmc.log(f"EMBY.emby.http: Session close error: {error}", 2) # LOGWARNING

        xbmc.log("EMBY.emby.http: Session close", 1) # LOGINFO

    # decide threaded or wait for response
    def request(self, data, ForceReceiveData, Binary, GetHeaders=False, LastWill=False, Priority=False, Download=None):
        ServerUnreachable = False

        if Priority:
            self.Priority = True

        RequestType = data.pop('type', "GET")

        if 'url' not in data:
            data['url'] = f"{self.EmbyServer.ServerData['ServerUrl']}/emby/{data.pop('handler', '')}"

        if 'headers' not in data:
            Header = {'Content-type': "application/json", 'Accept-Charset': "UTF-8,*", 'Accept-encoding': "gzip", 'User-Agent': f"{utils.addon_name}/{utils.addon_version}"}
        else:
            Header = data['headers']
            del data['headers']

        if 'Authorization' not in Header:
            auth = f"Emby Client={utils.addon_name},Device={utils.device_name},DeviceId={self.EmbyServer.ServerData['DeviceId']},Version={utils.addon_version}"

            if self.EmbyServer.ServerData['AccessToken'] and self.EmbyServer.ServerData['UserId']:
                Header.update({'Authorization': f"{auth},UserId={self.EmbyServer.ServerData['UserId']}", 'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']})
            else:
                Header.update({'Authorization': auth})

        if not ForceReceiveData and (Priority or RequestType in ("POST", "DELETE")):
            data['timeout'] = (1, 0.5)
            RepeatSend = 20 # retry 20 times (10 seconds)
        else:
            data['timeout'] = (15, 300)
            RepeatSend = 2

        xbmc.log(f"EMBY.emby.http: [ http ] {data}", 0) # LOGDEBUG
        data['verify'] = utils.sslverify

        for Index in range(RepeatSend): # timeout 10 seconds
            if not Priority:
                self.wait_for_priority_request()

            if Index > 0:
                xbmc.log(f"EMBY.emby.http: Request no send, retry: {Index}", 2) # LOGWARNING

            # Shutdown
            if utils.SystemShutdown and not LastWill:
                self.stop_session()
                return self.noData(Binary, GetHeaders)

            # start session
            if not self.session:
                self.HeaderCache = {}
                self.session = requests.Session()
                start_new_thread(self.async_commands, ())
                start_new_thread(self.download_file, ())

            # Update session headers
            if Header != self.HeaderCache:
                self.HeaderCache = Header.copy()
                self.session.headers = Header

            # http request
            try:
                if RequestType == "HEAD":
                    r = self.session.head(**data)
                    r.close()
                    self.Priority = False
                    return r.status_code

                if RequestType == "GET":
                    if Download:
                        self.FileDownloadQueue.put(((data, Download),))
                        return None

                    r = self.session.get(**data)
                    r.close()
                    self.Priority = False

                    if r.status_code == 200:
                        if Binary:
                            if GetHeaders:
                                return r.content, r.headers

                            return r.content

                        return r.json()

                    if r.status_code == 401:
                        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33147))

                    xbmc.log(f"EMBY.emby.http: [ Statuscode ] {r.status_code}", 3) # LOGERROR
                    xbmc.log(f"EMBY.emby.http: [ Statuscode ] {data}", 0) # LOGDEBUG
                    return self.noData(Binary, GetHeaders)
                if RequestType == "POST":
                    if Priority or ForceReceiveData:
                        r = self.session.post(**data)
                        r.close()
                        self.Priority = False

                        if GetHeaders:
                            return r.content, r.headers

                        return r.json()

                    self.AsyncCommandQueue.put((("POST", data),))
                elif RequestType == "DELETE":
                    self.AsyncCommandQueue.put((("DELETE", data),))

                return self.noData(Binary, GetHeaders)
            except requests.exceptions.SSLError:
                xbmc.log("EMBY.emby.http: [ SSL error ]", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: [ SSL error ] {data}", 0) # LOGDEBUG
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33428))
                self.stop_session()
                return self.noData(Binary, GetHeaders)
            except requests.exceptions.ConnectionError:
                xbmc.log("EMBY.emby.http: [ ServerUnreachable ]", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: [ ServerUnreachable ] {data}", 0) # LOGDEBUG
                ServerUnreachable = True
                continue
            except requests.exceptions.ReadTimeout:
                xbmc.log("EMBY.emby.http: [ ServerReadTimeout ]", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: [ ServerReadTimeout ] {data}", 0) # LOGDEBUG

                if data['timeout'][0] < 10:
                    continue

                return self.noData(Binary, GetHeaders)
            except Exception as error:
                xbmc.log(f"EMBY.emby.http: [ Unknown ] {error}", 3) # LOGERROR
                xbmc.log(f"EMBY.emby.http: [ Unknown ] {data} / {error}", 0) # LOGDEBUG
                return self.noData(Binary, GetHeaders)

        if ServerUnreachable:
            self.EmbyServer.ServerReconnect()

        return self.noData(Binary, GetHeaders)

    def load_Trailers(self, EmbyId):
        ReceivedIntros = []
        self.Intros = []

        if utils.localTrailers:
            IntrosLocal = self.EmbyServer.API.get_local_trailers(EmbyId)

            for IntroLocal in IntrosLocal:
                ReceivedIntros.append(IntroLocal)

        if utils.Trailers:
            IntrosExternal = self.EmbyServer.API.get_intros(EmbyId)

            if 'Items' in IntrosExternal:
                for IntroExternal in IntrosExternal['Items']:
                    ReceivedIntros.append(IntroExternal)

        if ReceivedIntros:
            Index = 0

            for Index, Intro in enumerate(ReceivedIntros):
                if self.verify_intros(Intro):
                    break

            for Intro in ReceivedIntros[Index + 1:]:
                start_new_thread(self.verify_intros, (Intro,))

    def verify_intros(self, Intro):
        xbmc.log("EMBY.emby.http: THREAD: --->[ verify intros ]", 0) # LOGDEBUG

        if Intro['Path'].find("http") == -1: # Local Trailer
            Intro['Path'], _ = common.get_path_type_from_item(self.EmbyServer.ServerData['ServerId'], Intro, False, True)
            return True

        status_code = self.EmbyServer.API.get_stream_statuscode(Intro['Id'], Intro['MediaSources'][0]['Id'])

        if status_code == 200:
            Intro['Path'], _ = common.get_path_type_from_item(self.EmbyServer.ServerData['ServerId'], Intro, False, True)
            self.Intros.append(Intro)
        else:
            xbmc.log(f"EMBY.emby.http: Invalid Trailer: {Intro['Path']} / {status_code}", 3) # LOGERROR

        xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] invalid", 0) # LOGDEBUG
        return False

    def noData(self, Binary, GetHeaders):
        self.Priority = False

        if Binary:
            if GetHeaders:
                return b"", {}

            return b""

        return {}

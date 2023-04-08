from _thread import start_new_thread
import queue
import requests
import xbmc
from helper import utils


class HTTP:
    def __init__(self, EmbyServer):
        self.session = None
        self.EmbyServer = EmbyServer
        self.Intros = []
        self.HeaderCache = {}
        self.AsyncCommandQueue = queue.Queue()
        self.Priority = False

    def async_commands(self):
        xbmc.log("EMBY.emby.http: THREAD: --->[ async queue ]", 1) # LOGINFO
        CommandRetry = ()
        CommandRetryCounter = 0

        while True:
            if CommandRetry:
                Command = CommandRetry
                CommandRetry = ()
            else:
                Command = self.AsyncCommandQueue.get()

            try:
                self.wait_for_priority_request()

                if Command[0] == "POST":
                    Command[1]['timeout'] = (1, 0.5)
                    r = self.session.post(**Command[1])
                    r.close()
                elif Command[0] == "DELETE":
                    Command[1]['timeout'] = (1, 0.5)
                    r = self.session.delete(**Command[1])
                    r.close()
                elif Command[0] == "QUIT":
                    xbmc.log("EMBY.emby.http: Queue closed", 1) # LOGINFO
                    break

                CommandRetryCounter = 0
            except Exception as error:
                if utils.sleep(5):
                    return

                if CommandRetryCounter < 5:
                    CommandRetryCounter += 1
                    CommandRetry = Command
                    xbmc.log(f"EMBY.emby.http: Async_commands retry: {CommandRetryCounter} / error: {error}", 2) # LOGWARNING
                else:
                    CommandRetryCounter = 0
                    CommandRetry = ()
                    xbmc.log(f"EMBY.emby.http: Async_commands error: {error}", 2) # LOGWARNING

        xbmc.log("EMBY.emby.http: THREAD: ---<[ async queue ]", 1) # LOGINFO

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
            return

        LocalSession = self.session  # Use local var -> self.session must be set to "none" instantly -> self var is also used to detect open sessions
        self.session = None
        self.AsyncCommandQueue.put(("QUIT",))

        try:
            LocalSession.close()
        except Exception as error:
            xbmc.log(f"EMBY.emby.http: Session close error: {error}", 2) # LOGWARNING

        xbmc.log("EMBY.emby.http: Session close", 1) # LOGINFO

    # decide threaded or wait for response
    def request(self, data, ForceReceiveData, Binary, GetHeaders=False, LastWill=False, Priority=False):
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
            auth = f"Emby Client={utils.addon_name},Device={utils.device_name},DeviceId={utils.device_id},Version={utils.addon_version}"

            if self.EmbyServer.ServerData['AccessToken'] and self.EmbyServer.ServerData['UserId']:
                Header.update({'Authorization': f"{auth},UserId={self.EmbyServer.ServerData['UserId']}", 'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']})
            else:
                Header.update({'Authorization': auth})

        if Priority or RequestType in ("POST", "DELETE"):
            data['timeout'] = (1, 0.5)
            RepeatSend = 20 # retry 20 times (10 seconds)
        else:
            data['timeout'] = (15, 300)
            RepeatSend = 1

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

                    self.AsyncCommandQueue.put(("POST", data))
                elif RequestType == "DELETE":
                    self.AsyncCommandQueue.put(("DELETE", data))

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
            self.stop_session()
            self.EmbyServer.ServerUnreachable()

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
        xbmc.log("EMBY.emby.http: THREAD: --->[ verify intros ]", 1) # LOGINFO

        if Intro['Path'].find("http") == -1: # Local Trailer
            Intro['Path'] = f"{self.EmbyServer.ServerData['ServerUrl']}/emby/videos/{Intro['Id']}/stream?static=true&api_key={self.EmbyServer.ServerData['AccessToken']}&DeviceId={utils.device_id}"
            self.Intros.append(Intro)
            xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] local trailer", 1) # LOGINFO
            return True

        try:
            r = requests.head(Intro['Path'], allow_redirects=True, timeout=2)
            r.close()

            if Intro['Path'] == r.url:
                self.Intros.append(Intro)
                xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] remote trailer", 1) # LOGINFO
                return True

            # filter URL redirections, mostly invalid links
            xbmc.log(f"EMBY.emby.http: Invalid Trailer Path (url compare): {Intro['Path']} / {r.url}", 3) # LOGERROR
        except Exception as Error:
            xbmc.log(f"EMBY.emby.http: Invalid Trailer Path: {Intro['Path']} / {Error}", 3) # LOGERROR

        xbmc.log("EMBY.emby.http: THREAD: ---<[ verify intros ] invalid", 1) # LOGINFO
        return False

    def noData(self, Binary, GetHeaders):
        self.Priority = False

        if Binary:
            if GetHeaders:
                return b"", {}

            return b""

        return {}

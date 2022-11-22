from _thread import start_new_thread
import queue
import requests
from helper import utils, loghandler

LOG = loghandler.LOG('EMBY.emby.http')


class HTTP:
    def __init__(self, EmbyServer):
        self.session = None
        self.EmbyServer = EmbyServer
        self.Intros = []
        self.AsyncCommandQueue = queue.Queue()

    def async_commands(self):
        CommandRetry = ()
        CommandRetryCounter = 0

        while True:
            if CommandRetry:
                Command = CommandRetry
                CommandRetry = ()
            else:
                Command = self.AsyncCommandQueue.get()

            try:
                if Command[0] == "POST":
                    Command[1]['timeout'] = (5, 5)
                    r = self.session.post(**Command[1])
                    r.close()
                elif Command[0] == "DELETE":
                    Command[1]['timeout'] = (5, 5)
                    r = self.session.delete(**Command[1])
                    r.close()
                elif Command[0] == "QUIT":
                    LOG.info("Queue closed")
                    break

                CommandRetryCounter = 0
            except Exception as error:
                if CommandRetryCounter < 5:
                    CommandRetryCounter += 1
                    CommandRetry = Command
                    LOG.warning("async_commands retry: %s" % CommandRetryCounter)
                else:
                    CommandRetryCounter = 0
                    CommandRetry = ()
                    LOG.warning("async_commands error: %s" % str(error))

    def stop_session(self):
        if not self.session:
            return

        try:
            self.session.close()
        except Exception as error:
            LOG.warning("session close error: %s" % str(error))

        self.AsyncCommandQueue.put(("QUIT",))
        self.session = None
        LOG.info("session close")

    # decide threaded or wait for response
    def request(self, data, ServerConnecting, Binary, Headers=False):
        RequestType = data.pop('type', "GET")

        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.EmbyServer.ServerData['ServerUrl'], data.pop('handler', ""))

        if 'headers' not in data:
            data['headers'] = {'Content-type': "application/json", 'Accept-Charset': "UTF-8,*", 'Accept-encoding': "gzip", 'User-Agent': "%s/%s" % (utils.addon_name, utils.addon_version)}

        if 'Authorization' not in data['headers']:
            auth = "Emby Client=%s,Device=%s,DeviceId=%s,Version=%s" % (utils.addon_name, utils.device_name, utils.device_id, utils.addon_version)

            if self.EmbyServer.ServerData['AccessToken'] and self.EmbyServer.ServerData['UserId']:
                auth = '%s,UserId=%s' % (auth, self.EmbyServer.ServerData['UserId'])
                data['headers'].update({'Authorization': auth, 'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']})
            else:
                data['headers'].update({'Authorization': auth})

        if ServerConnecting:  # Server connect
            data['timeout'] = (15, 30)
        else:
            data['timeout'] = (15, 300)

        LOG.debug("[ http ] %s" % data)

        # SHutdown
        if utils.sleep(0.01):
            return noData(Binary, Headers)

        # start session
        if not self.session:
            self.session = requests.Session()
            start_new_thread(self.async_commands, ())

        # http request
        try:
            if RequestType == "HEAD":
                r = self.session.head(**data)
                r.close()
                return r.status_code

            if RequestType == "GET":
                r = self.session.get(**data)
                r.close()

                if r.status_code == 200:
                    if Binary:
                        if Headers:
                            return r.content, r.headers

                        return r.content

                    return r.json()

                if r.status_code == 401:
                    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33147))

                LOG.error("[ Statuscode ] %s" % r.status_code)
                LOG.debug("[ Statuscode ] %s" % data)
                return noData(Binary, Headers)
            if RequestType == "POST":
                if ServerConnecting:
                    r = self.session.post(**data)
                    r.close()
                    return r.json()

                self.AsyncCommandQueue.put(("POST", data))
            elif RequestType == "DELETE":
                self.AsyncCommandQueue.put(("DELETE", data))
            return noData(Binary, Headers)
        except requests.exceptions.SSLError:
            LOG.error("[ SSL error ]")
            LOG.debug("[ SSL error ] %s" % data)
            utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33428))
            self.stop_session()
            return noData(Binary, Headers)
        except requests.exceptions.ConnectionError:
            LOG.error("[ ServerUnreachable ]")
            LOG.debug("[ ServerUnreachable ] %s" % data)
            self.stop_session()
            self.EmbyServer.ServerUnreachable()
            self.stop_session()
            return noData(Binary, Headers)
        except requests.exceptions.ReadTimeout:
            LOG.error("[ ServerTimeout ]")
            LOG.debug("[ ServerTimeout ] %s" % data)
            self.stop_session()
            return noData(Binary, Headers)
        except Exception as error:
            LOG.error("[ Unknown ] %s" % str(error))
            LOG.debug("[ Unknown ] %s / %s" % (data, str(error)))
            self.stop_session()
            return noData(Binary, Headers)

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
        if Intro['Path'].find("http") == -1: # Local Trailer
            Intro['Path'] = "%s/emby/videos/%s/stream?static=true&api_key=%s&DeviceId=%s" % (self.EmbyServer.ServerData['ServerUrl'], Intro['Id'], self.EmbyServer.ServerData['AccessToken'], utils.device_id)
            self.Intros.append(Intro)
            return True

        try:
            r = requests.head(Intro['Path'], allow_redirects=True, timeout=2)
            r.close()

            if Intro['Path'] == r.url:
                self.Intros.append(Intro)
                return True

            # filter URL redirections, mostly invalid links
            LOG.error("Invalid Trailer Path (url compare): %s / %s" % (Intro['Path'], r.url))
        except Exception as Error:
            LOG.error("Invalid Trailer Path: %s / %s" % (Intro['Path'], Error))

        return False

def noData(Binary, Headers):
    if Binary:
        if Headers:
            return b"", {}

        return b""

    return {}

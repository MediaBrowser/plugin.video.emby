import requests
from helper import utils, loghandler

LOG = loghandler.LOG('EMBY.emby.http')


class HTTP:
    def __init__(self, EmbyServer):
        self.session = None
        self.EmbyServer = EmbyServer

    def stop_session(self):
        if not self.session:
            return

        LOG.warning("--<[ session/%s ]" % id(self.session))
        self.session.close()
        self.session = None

    def request(self, data, ServerConnecting, Binary):
        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.EmbyServer.server, data.pop('handler', ""))

        data = self.get_header(data)

        if not data:
            return {}

        if ServerConnecting:  # Server connect
            data['timeout'] = 15
        else:
            data['timeout'] = 300

        LOG.debug("--->[ http ] %s" % data)
        Retries = 0

        while True:
            if utils.SystemShutdown:
                self.stop_session()
                return noData(Binary)

            # start session
            if not self.session:
                self.session = requests.Session()

            try:
                r = _requests(self.session, data.pop('type', "GET"), **data)
                LOG.debug("---<[ http ][%s ms]" % int(r.elapsed.total_seconds() * 1000))
                LOG.debug("[ http response %s / %s ]" % (r.status_code, data))

                if r.status_code == 200:
                    if Binary:
                        return r.content

                    return r.json()

                if r.status_code == 401:
                    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33147))

                return noData(Binary)
            except requests.exceptions.SSLError:
                LOG.error("[ SSL error ]")
                utils.Dialog.notification(heading=utils.addon_name, message="SSL Error")
                self.stop_session()
                return noData(Binary)
            except requests.exceptions.ConnectionError:
                LOG.error("[ ServerUnreachable ]")
                self.stop_session()

                if not ServerConnecting:
                    if Retries < 3:
                        Retries += 1
                        LOG.error("[ ServerUnreachable/retries %s ]" % Retries)
                        continue

                    self.EmbyServer.ServerUnreachable()

                self.stop_session()
                return noData(Binary)
            except requests.exceptions.ReadTimeout:
                LOG.error("[ ServerTimeout ] %s" % data)
                self.stop_session()
                return noData(Binary)
            except Exception as error:
                LOG.error(error)
                self.stop_session()
                return noData(Binary)

    def get_header(self, data):
        data['headers'] = data.setdefault('headers', {})

        if not data['headers']:
            data['headers'].update({
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': "%s/%s" % (utils.addon_name, utils.addon_version)
            })

        if 'Authorization' not in data['headers']:
            data = self._authorization(data)

        return data

    def _authorization(self, data):
        auth = "Emby Client=%s, " % utils.addon_name
        auth += "Device=%s, " % utils.device_name
        auth += "DeviceId=%s, " % utils.device_id
        auth += "Version=%s" % utils.addon_version
        data['headers'].update({'Authorization': auth})

        if self.EmbyServer.Token and self.EmbyServer.user_id:
            auth += ', UserId=%s' % self.EmbyServer.user_id
            data['headers'].update({'Authorization': auth, 'X-Emby-Token': self.EmbyServer.Token})

        return data

    def load_Trailers(self, EmbyId):
        Intros = []
        ValidIntros = []

        if utils.localTrailers:
            IntrosLocal = self.EmbyServer.API.get_local_trailers(EmbyId)

            for IntroLocal in IntrosLocal:
                Intros.append(IntroLocal)

        if utils.Trailers:
            IntrosExternal = self.EmbyServer.API.get_intros(EmbyId)

            if 'Items' in IntrosExternal:
                for IntroExternal in IntrosExternal['Items']:
                    Intros.append(IntroExternal)

            for Intro in Intros:
                if Intro['Path'].find("http") == -1:
                    Intro['Path'] = "%s/emby/videos/%s/stream?static=true&api_key=%s&DeviceId=%s" % (self.EmbyServer.server, Intro['Id'], self.EmbyServer.Token, utils.device_id)
                    ValidIntros.append(Intro)
                else:
                    try:
                        r = requests.head(Intro['Path'], allow_redirects=True)

                        if Intro['Path'] == r.url:
                            ValidIntros.append(Intro)
                        else:  # filter URL redirections, mostly invalid links
                            LOG.error("Invalid Trailer Path: %s" % Intro['Path'])
                    except:
                        LOG.error("Invalid Trailer Path: %s" % Intro['Path'])

        return ValidIntros

def _requests(session, action, **kwargs):
    if action == "GET":
        return session.get(**kwargs)

    if action == "POST":
        return session.post(**kwargs)

    if action == "HEAD":
        return session.head(**kwargs)

    if action == "DELETE":
        return session.delete(**kwargs)

    return None

def noData(Binary):
    if Binary:
        return b""

    return {}

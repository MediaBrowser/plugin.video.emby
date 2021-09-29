# -*- coding: utf-8 -*-
import json
import threading
import requests
import helper.utils as Utils
import helper.loghandler

LOG = helper.loghandler.LOG('EMBY.core.HTTP')


class HTTP:
    def __init__(self, EmbyServer, ServerUnreachable, Unauthorized):
        self.session = None
        self.EmbyServer = EmbyServer
        self.ServerUnreachable = ServerUnreachable
        self.Unauthorized = Unauthorized

    def start_session(self):
        self.session = requests.Session()

    def stop_session(self):
        if self.session is None:
            return

        try:
            LOG.warning("--<[ session/%s ]" % id(self.session))
            self.session.close()
            self.session = None
        except Exception as error:
            LOG.warning("The requests session could not be terminated: %s" % error)

    def request(self, data, ServerConnecting, Binary):
        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.EmbyServer.server, data.pop('handler', ""))

        data = self.get_header(data)

        if not data:
            return {}

        if ServerConnecting:  # Server connect
            data['timeout'] = 5
        else:
            data['timeout'] = 60

        data['verify'] = Utils.sslverify
        LOG.debug("--->[ http ] %s" % json.dumps(data, indent=4))
        Retries = 0

        while True:
            try:
                r = _requests(self.session or requests, data.pop('type', "GET"), **data)
                LOG.debug("---<[ http ][%s ms]" % int(r.elapsed.total_seconds() * 1000))

                if r.status_code == 200:
                    if Binary:
                        return r.content

                    return r.json()

                if r.status_code == 401:
                    threading.Thread(target=self.Unauthorized).start()

                LOG.debug("[ http response %s / %s ]" % (r.status_code, data))

                if Binary:
                    return b""

                return {}
            except requests.exceptions.ConnectionError:
                LOG.error("[ ServerUnreachable ]")

                if not ServerConnecting:
                    if Retries < 3:
                        Retries += 1
                        LOG.error("[ ServerUnreachable/retries %s ]" % Retries)
                        continue

                    threading.Thread(target=self.ServerUnreachable).start()

                return {}
            except requests.exceptions.ReadTimeout:
                LOG.error("[ ServerTimeout ]")
                return {}
            except Exception as error:
                LOG.error(error)
                return {}

    def get_header(self, data):
        data['headers'] = data.setdefault('headers', {})

        if not data['headers']:
            data['headers'].update({
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': "Kodi/%s" % Utils.addon_version
            })

        if 'Authorization' not in data['headers']:
            data = self._authorization(data)

        return data

    def _authorization(self, data):
        auth = "Emby "
        auth += "Client=Kodi, "
        auth += "Device=%s, " % Utils.device_name
        auth += "DeviceId=%s, " % Utils.device_id
        auth += "Version=%s" % Utils.addon_version
        data['headers'].update({'Authorization': auth})

        if self.EmbyServer.Token and self.EmbyServer.user_id:
            auth += ', UserId=%s' % self.EmbyServer.user_id
            data['headers'].update({'Authorization': auth, 'X-Emby-Token': self.EmbyServer.Token})

        return data

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

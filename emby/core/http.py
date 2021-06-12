# -*- coding: utf-8 -*-
import json
import time
import requests

import xbmc

import helper.loghandler

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str

class HTTP():
    def __init__(self, EmbyServer):
        self.LOG = helper.loghandler.LOG('EMBY.core.HTTP')
        self.session = None
        self.EmbyServer = EmbyServer

    def start_session(self):
        self.session = requests.Session()

    def stop_session(self):
        if self.session is None:
            return

        try:
            self.LOG.warning("--<[ session/%s ]" % id(self.session))
            self.session.close()
            self.session = None
        except Exception as error:
            self.LOG.warning("The requests session could not be terminated: %s" % error)

    def request(self, data, MSGs=True, Binary=False): #MSGs are disabled on initial sync and reconnection. Only send msgs if connection is unexpectly interrupted
        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.EmbyServer.Data['auth.server'], data.pop('handler', ""))

        data = self.get_header(data)

        if not data:
            return False

        data['timeout'] = self.EmbyServer.Data['http.timeout']
        data['verify'] = self.EmbyServer.Data['auth.ssl']
        self.LOG.debug("--->[ http ] %s" % json.dumps(data, indent=4))
        retry = data.pop('retry', 5)

        def _retry(current):
            if current:
                current -= 1
                time.sleep(1)

            return current

        while True:
            try:
                r = self._requests(self.session or requests, data.pop('type', "GET"), **data)
                r.content # release the connection
                r.raise_for_status()
            except requests.exceptions.ConnectionError:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error("[ ServerUnreachable ]")

                if MSGs:
                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "ServerUnreachable", '"[%s]"' % json.dumps({'ServerId': self.EmbyServer.server_id}).replace('"', '\\"')))

                return False
            except requests.exceptions.ReadTimeout:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error("[ ServerTimeout ]")

                if MSGs:
                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "ServerTimeout", '"[%s]"' % json.dumps({'ServerId': self.EmbyServer.server_id}).replace('"', '\\"')))

                return False
            except requests.exceptions.HTTPError:
#                self.LOG.error(error)

                if r.status_code == 401:
                    if 'X-Application-Error-Code' in r.headers:
                        xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "AccessRestricted", '"[%s]"' % json.dumps({'ServerId': self.EmbyServer.server_id}).replace('"', '\\"')))
                        return False

                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "Unauthorized", '"[%s]"' % json.dumps({'ServerId': self.EmbyServer.server_id}).replace('"', '\\"')))
                    self.EmbyServer.auth.revoke_token()
                    return False

                if r.status_code == 500: # log and ignore.
#                    self.LOG.error("--[ 500 response ] %s" % error)
                    self.LOG.error("[ 500 response ]")
                    return False

                if r.status_code == 400: # log and ignore.
#                    self.LOG.error("--[ 400 response ] %s" % error)
                    self.LOG.error("[ 400 response ]")
                    return False

                if r.status_code == 404: # log and ignore.
#                    self.LOG.error("--[ 404 response ] %s" % error)
                    self.LOG.error("[ 404 response ]")
                    return False

                if r.status_code == 502:
                    retry = _retry(retry)

                    if retry:
                        continue
                elif r.status_code == 503:
                    retry = _retry(retry)

                    if retry:
                        continue

                return False
            except requests.exceptions.MissingSchema:
                self.LOG.error("[ MissingSchema ]")
                return False
            except Exception as error:
                self.LOG.error(error)
                return False
            else:
                elapsed = int(r.elapsed.total_seconds() * 1000)
                self.LOG.debug("---<[ http ][%s ms]" % elapsed)

                if Binary:
                    return r.content
                else:
                    try:
                        self.EmbyServer.Data['server-time'] = r.headers['Date']

                        if r.status_code == 204:
                            # return, because there is no response
                            return

                        response = r.json()

                        try:
                            self.LOG.debug(json.dumps(response, indent=4))
                        except Exception:
                            self.LOG.debug(response)

                        return response
                    except ValueError:
                        return r.content

    def get_header(self, data):
        data['headers'] = data.setdefault('headers', {})

        if not data['headers']:
            data['headers'].update({
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': self.EmbyServer.Data['http.user_agent'] or "%s/%s" % (self.EmbyServer.Data['app.name'], self.EmbyServer.Data['app.version'])
            })

        if 'Authorization' not in data['headers']:
            data = self._authorization(data)

        return data

    def _authorization(self, data):
        if not self.EmbyServer.Data['app.device_name']:
            return False #Device name cannot be null

        auth = "Emby "
        auth += "Client=%s, " % self.EmbyServer.Data['app.name']
        auth += "Device=%s, " % self.EmbyServer.Data['app.device_name']
        auth += "DeviceId=%s, " % self.EmbyServer.Data['app.device_id']
        auth += "Version=%s" % self.EmbyServer.Data['app.version']
        data['headers'].update({'Authorization': auth})

        if self.EmbyServer.Data['auth.token'] and self.EmbyServer.Data['auth.user_id']:
            auth += ', UserId=%s' % self.EmbyServer.Data['auth.user_id']
            data['headers'].update({'Authorization': auth, 'X-Emby-Token': self.EmbyServer.Data['auth.token']})

        return data

    def _requests(self, session, action, **kwargs):
        if action == "GET":
            return session.get(**kwargs)

        if action == "POST":
            return session.post(**kwargs)

        if action == "HEAD":
            return session.head(**kwargs)

        if action == "DELETE":
            return session.delete(**kwargs)

        return None

# -*- coding: utf-8 -*-
import json
import time
import requests

import xbmc

import helper.loghandler

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str

class HTTP():
    def __init__(self, client):
        self.LOG = helper.loghandler.LOG('EMBY.core.HTTP')
        self.session = None
        self.client = client
        self.config = client['config']

    def __shortcuts__(self, key):
        if key == "request":
            return self.request

        return

    def start_session(self):
        self.session = requests.Session()

    def stop_session(self):
        if self.session is None:
            return

        try:
            self.LOG.warning("--<[ session/%s ]" % id(self.session))
            self.session.close()
        except Exception as error:
            self.LOG.warning("The requests session could not be terminated: %s" % error)

    def _replace_user_info(self, string):
        if '{server}' in string:
            if self.config['auth.server']:
                string = string.replace("{server}", self.config['auth.server'])
            else:
                return False

        if '{UserId}'in string:
            if self.config['auth.user_id']:
                string = string.replace("{UserId}", self.config['auth.user_id'])
            else:
                return False

        return string

    def request(self, data, session, MSGs=True):
        data = self._request(data)

        if not data:
            return False

        self.LOG.debug("--->[ http ] %s" % json.dumps(data, indent=4))
        retry = data.pop('retry', 5)

        def _retry(current):
            if current:
                current -= 1
                time.sleep(1)

            return current

        while True:
            try:
                r = self._requests(session or self.session or requests, data.pop('type', "GET"), **data)
                r.content # release the connection
                r.raise_for_status()
            except requests.exceptions.ConnectionError as error:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error(error)

                if MSGs:
                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "ServerUnreachable", '"[%s]"' % json.dumps({'ServerId': self.config['auth.server-id']}).replace('"', '\\"')))

                return False

            except requests.exceptions.ReadTimeout as error:
                retry = _retry(retry)

                if retry:
                    continue

                self.LOG.error(error)

                if MSGs:
                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "ServerTimeout", '"[%s]"' % json.dumps({'ServerId': self.config['auth.server-id']}).replace('"', '\\"')))

                return False

            except requests.exceptions.HTTPError as error:
                self.LOG.error(error)

                if r.status_code == 401:
                    if 'X-Application-Error-Code' in r.headers:
                        xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "AccessRestricted", '"[%s]"' % json.dumps({'ServerId': self.config['auth.server-id']}).replace('"', '\\"')))
                        return False

                    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % ("plugin.video.emby-next-gen", "Unauthorized", '"[%s]"' % json.dumps({'ServerId': self.config['auth.server-id']}).replace('"', '\\"')))
                    self.client['auth/revoke-token']
                    return False

                if r.status_code == 500: # log and ignore.
                    self.LOG.error("--[ 500 response ] %s" % error)
                    return
                elif r.status_code == 400: # log and ignore.
                    self.LOG.error("--[ 400 response ] %s" % error)
                    return
                elif r.status_code == 404: # log and ignore.
                    self.LOG.error("--[ 404 response ] %s" % error)
                    return
                elif r.status_code == 502:
                    retry = _retry(retry)

                    if retry:
                        continue
                elif r.status_code == 503:
                    retry = _retry(retry)

                    if retry:
                        continue

                return False
            except requests.exceptions.MissingSchema as error:
                self.LOG.error(error)
                return False
            except Exception as error:
                self.LOG.error(error)
                return False
            else:
                elapsed = int(r.elapsed.total_seconds() * 1000)
                self.LOG.debug("---<[ http ][%s ms]" % elapsed)

                try:
                    self.config['server-time'] = r.headers['Date']

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
                    return False

    def _request(self, data):
        if 'url' not in data:
            data['url'] = "%s/emby/%s" % (self.config['auth.server'], data.pop('handler', ""))

        Ret = self._get_header(data)

        if not Ret:
            return False

        data['timeout'] = data.get('timeout') or self.config['http.timeout']
        data['url'] = self._replace_user_info(data['url'])

        if not data['url']:
            return False

        if data.get('verify') is None:
            if self.config['auth.ssl'] is None:
                data['verify'] = data['url'].startswith('https')
            else:
                data['verify'] = self.config['auth.ssl']

        self._process_params(data.get('params') or {})
        self._process_params(data.get('json') or {})
        return data

    def _process_params(self, params):
        for key in params:
            value = params[key]

            if isinstance(value, dict):
                self._process_params(value)

            if isinstance(value, (str, unicode)):
                params[key] = self._replace_user_info(value)

    def _get_header(self, data):
        data['headers'] = data.setdefault('headers', {})

        if not data['headers']:
            data['headers'].update({
                'Content-type': "application/json",
                'Accept-Charset': "UTF-8,*",
                'Accept-encoding': "gzip",
                'User-Agent': self.config['http.user_agent'] or "%s/%s" % (self.config['app.name'], self.config['app.version'])
            })

        if 'Authorization' not in data['headers']:
            if not self._authorization(data):
                return False

        return data

    def _authorization(self, data):
        if not self.config['app.device_name']:
            return False #Device name cannot be null

        auth = "MediaBrowser "
        auth += "Client=%s, " % self.config['app.name']
        auth += "Device=%s, " % self.config['app.device_name']
        auth += "DeviceId=%s, " % self.config['app.device_id']
        auth += "Version=%s" % self.config['app.version']
        data['headers'].update({'Authorization': auth})

        if self.config['auth.token'] and self.config['auth.user_id']:
            auth += ', UserId=%s' % self.config['auth.user_id']
            data['headers'].update({'Authorization': auth, 'X-MediaBrowser-Token': self.config['auth.token']})

        return data

    def _requests(self, session, action, **kwargs):
        if action == "GET":
            return session.get(**kwargs)
        elif action == "POST":
            return session.post(**kwargs)
        elif action == "HEAD":
            return session.head(**kwargs)
        elif action == "DELETE":
            return session.delete(**kwargs)

        return None

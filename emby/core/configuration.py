# -*- coding: utf-8 -*-
#This will hold all configs from the client.
#Configuration set here will be used for the HTTP client.
import helper.loghandler

class Config():
    def __init__(self):
        self.LOG = helper.loghandler.LOG('Emby.emby.core.configuration')
        self.LOG.debug("Configuration initializing...")
        self.data = {}
        self.http(None, 3, 30)

    def __shortcuts__(self, key):
        if key == "auth":
            return self.auth

        if key == "app":
            return self.app

        if key == "http":
            return self.http

        if key == "data":
            return self

        return None

    def __setstate__(self, data):
        self.data = data

    def __getstate__(self):
        return self.data

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data.get(key, self.__shortcuts__(key))

    def app(self, name, version, device_name, device_id, capabilities, device_pixel_ratio):
        self.LOG.debug("Begin app constructor")
        self.data['app.name'] = name
        self.data['app.version'] = version
        self.data['app.device_name'] = device_name
        self.data['app.device_id'] = device_id
        self.data['app.capabilities'] = capabilities
        self.data['app.device_pixel_ratio'] = device_pixel_ratio
        self.data['app.default'] = False

    def auth(self, server, user_id, token, ssl):
        self.LOG.debug("Begin auth constructor")
        self.data['auth.server'] = server
        self.data['auth.user_id'] = user_id
        self.data['auth.token'] = token
        self.data['auth.ssl'] = ssl

    def http(self, user_agent, max_retries, timeout):
        self.LOG.debug("Begin http constructor")
        self.data['http.max_retries'] = max_retries
        self.data['http.timeout'] = timeout
        self.data['http.user_agent'] = user_agent

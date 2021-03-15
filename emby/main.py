# -*- coding: utf-8 -*-
import helper.loghandler
from .core import api
from .core import configuration
from .core import http
from .core import ws_client
from .core import connection_manager

class Emby():
    def __init__(self, server_id=None):
        self.LOG = helper.loghandler.LOG('EMBY.emby.main')
        self.logged_in = False
        self.server_id = server_id
        self.config = configuration.Config()
        self.http = http.HTTP(self)
        self.wsock = None
        self.auth = connection_manager.ConnectionManager(self)
        self.emby = api.API(self)
        self.LOG.info("---[ START EMBYCLIENT: ]---")

    def get_client(self):
        return self

    def set_state(self, state):
        if not state:
            self.LOG.warning("state cannot be empty")
            return

        if state.get('config'):
            self.config.__setstate__(state['config'])

        if state.get('credentials'):
            self.logged_in = True
            self.set_credentials(state['credentials'])
            self.auth.server_id = state['credentials']['Servers'][0]['Id']

    def get_state(self):
        state = {'config': self.config.__getstate__(), 'credentials': self.get_credentials()}
        return state

    def set_credentials(self, credentials):
        self.auth.credentials.set_credentials(credentials or {})

    def get_credentials(self):
        return self.auth.credentials.get_credentials()

    def authenticate(self, credentials, options):
        self.set_credentials(credentials or {})
        state = self.auth.connect(options or {})

        if not state:
            return False

        if state['State'] == 3: #SignedIn
            self.logged_in = True
            self.LOG.info("User is authenticated.")

        state['Credentials'] = self.get_credentials()
        return state

    def start(self):
        if not self.logged_in:
            return False #"User is not authenticated."

        self.http.start_session()
        self.wsock = ws_client.WSClient(self)
        self.wsock.start()

    def stop(self):
        self.LOG.info("---[ STOPPED EMBYCLIENT: %s ]---" % self.server_id)
        self.wsock.close()
        self.wsock = None
        self.http.stop_session()

    def __getitem__(self, key):
        if key.startswith('config'):
            return self.config[key.replace('config/', "", 1)] if "/" in key else self.config
        elif key.startswith('http'):
            return self.http.__shortcuts__(key.replace('http/', "", 1))
#        elif key.startswith('websocket'):
#            return self.wsock.__shortcuts__(key.replace('websocket/', "", 1))
        elif key.startswith('auth'):
            return self.auth.__shortcuts__(key.replace('auth/', "", 1))
        elif key.startswith('api'):
            return self.emby
        elif key == 'connected':
            return self.logged_in

        return None

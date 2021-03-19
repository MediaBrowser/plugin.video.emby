# -*- coding: utf-8 -*-
import helper.loghandler
from .core import api
from .core import http
from .core import ws_client
from .core import connection_manager

class Emby():
    def __init__(self, server_id=None):
        self.LOG = helper.loghandler.LOG('EMBY.emby.main')
        self.logged_in = False
        self.server_id = server_id
        self.wsock = None
        self.http = http.HTTP(self)
        self.auth = connection_manager.ConnectionManager(self)
        self.API = api.API(self)
        self.Data = {'http.user_agent': None, 'http.timeout': 30, 'http.max_retries': 3, 'auth.server': None, 'auth.user_id': None, 'auth.token': None, 'auth.ssl': None, 'app.name': None, 'app.version': None, 'app.device_name': None, 'app.device_id': None, 'app.capabilities': None, 'app.session': None}
        self.LOG.info("---[ START EMBYCLIENT: ]---")

    def set_state(self, state):
        if not state:
            self.LOG.warning("state cannot be empty")
            return

        if state.get('config'):
            self.Data = state['config']

        if state.get('credentials'):
            self.logged_in = True
            self.auth.credentials.set_credentials(state['credentials'] or {})
            self.auth.server_id = state['credentials']['Servers'][0]['Id']

    def get_state(self):
        return {'config': self.Data, 'credentials': self.auth.credentials.get_credentials()}

    def authenticate(self, credentials, options):
        self.auth.credentials.set_credentials(credentials or {})
        state = self.auth.connect(options or {})

        if not state:
            return False

        if state['State'] == 3: #SignedIn
            self.logged_in = True
            self.LOG.info("User is authenticated.")

        state['Credentials'] = self.auth.credentials.get_credentials()
        return state

    def start(self):
        if not self.logged_in:
            return False #"User is not authenticated."

        self.http.start_session()
        self.wsock = ws_client.WSClient(self.Data['auth.server'], self.Data['app.device_id'], self.Data['auth.token'], self.server_id)
        self.wsock.start()

    def stop(self):
        self.LOG.info("---[ STOPPED EMBYCLIENT: %s ]---" % self.server_id)
        self.wsock.close()
        self.wsock = None
        self.http.stop_session()

import logging
from .core import api
from .core import configuration
from .core import http
from .core import ws_client
from .core import connection_manager

def callback(message, data):
    ''' Callback function should received message, data
        message: string
        data: json dictionary
    '''
    return

class EmbyClient():
    logged_in = False

    def __init__(self):
        self.LOG = logging.getLogger('Emby.emby.client')
        self.LOG.debug("EmbyClient initializing...")
        self.config = configuration.Config()
        self.http = http.HTTP(self)
        self.wsc = ws_client.WSClient(self)
        self.auth = connection_manager.ConnectionManager(self)
        self.emby = api.API(self.http)
        self.callback_ws = callback
        self.callback = callback

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

    def set_credentials(self, credentials=None):
        self.auth.credentials.set_credentials(credentials or {})

    def get_credentials(self):
        return self.auth.credentials.get_credentials()

    def authenticate(self, credentials=None, options=None):
        self.set_credentials(credentials or {})
        state = self.auth.connect(options or {})

        if state['State'] == connection_manager.CONNECTION_STATE['SignedIn']:
            self.LOG.info("User is authenticated.")
            self['callback']('ServerOnline', {'Id': None if self['config/app.default'] else self['auth/server-id']})
            self.logged_in = True

        state['Credentials'] = self.get_credentials()
        return state

    def start(self, websocket=False, keep_alive=True):
        if not self.logged_in:
            raise ValueError("User is not authenticated.")

        self.http.start_session()

        if keep_alive:
            self.http.keep_alive = True

        if websocket:
            self.start_wsc()

    def start_wsc(self):
        self.wsc.start()

    def stop(self):
        self['callback']('StopServer', {'ServerId': None if self['config/app.default'] else self['auth/server-id']})
        self.wsc.stop_client()
        self.http.stop_session()

    def __getitem__(self, key):
        if key.startswith('config'):
            return self.config[key.replace('config/', "", 1)] if "/" in key else self.config
        elif key.startswith('http'):
            return self.http.__shortcuts__(key.replace('http/', "", 1))
        elif key.startswith('websocket'):
            return self.wsc.__shortcuts__(key.replace('websocket/', "", 1))
        elif key.startswith('callback'):
            return self.callback_ws if 'ws' in key else self.callback
        elif key.startswith('auth'):
            return self.auth.__shortcuts__(key.replace('auth/', "", 1))
        elif key.startswith('api'):
            return self.emby
        elif key == 'connected':
            return self.logged_in

        return

# -*- coding: utf-8 -*-
import helper.loghandler
from .core import api
from .core import http
from .core import ws_client
from .core import connection_manager

class Emby():
    def __init__(self, Utils, server_id=None):
        self.LOG = helper.loghandler.LOG('EMBY.emby.main')
        self.logged_in = False
        self.wsock = None
        self.http = http.HTTP(self)
        self.auth = connection_manager.ConnectionManager(self)
        self.server_id = server_id
        self.Utils = Utils
        self.API = api.API(self)
        self.Data = {'http.user_agent': None, 'http.timeout': 30, 'http.max_retries': 3, 'auth.server': None, 'auth.user_id': None, 'auth.token': None, 'auth.ssl': None, 'app.name': None, 'app.version': None, 'app.device_name': None, 'app.device_id': self.Utils.get_device_id(False), 'app.capabilities': None, 'auth.server-name': None}
        self.LOG.info("---[ INIT EMBYCLIENT: ]---")

    def set_state(self):
        state = self.Utils.Basics.window('emby.server.%s.state.json' % self.server_id)
        self.Data = state['config']
        self.logged_in = True
        self.auth.credentials.set_credentials(state['credentials'] or {})
        self.server_id = state['credentials']['Servers'][0]['Id']
        self.LOG.info("---[ SET EMBYCLIENT: %s ]---" % self.server_id)

    def save_state(self):
        self.Utils.Basics.window('emby.server.%s.state.json' % self.server_id, {'config': self.Data, 'credentials': self.auth.credentials.get_credentials()})
        self.Utils.Basics.window('emby.servers.json', {self.server_id : self.Data['auth.server-name']})

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
            self.LOG.error("User is not logged in.")
            return False #"User is not authenticated."

        self.LOG.info("---[ START EMBYCLIENT: %s ]---" % self.server_id)
        self.http.start_session()
        self.API.post_capabilities({
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"
        })

        if self.Utils.Basics.settings('addUsers'):
            session = self.API.get_device()
            users = self.Utils.Basics.settings('addUsers').split(',')
            hidden = None if self.Utils.Basics.settings('addUsersHidden.bool') else False
            all_users = self.API.get_users(False, hidden)

            for additional in users:
                for user in all_users:
                    if user['Id'] == additional:
                        self.API.session_add_user(session[0]['Id'], user['Id'], True)

            #add additional users
            for i in range(10):
                self.Utils.Basics.window('emby.AdditionalUserImage.%s' % i, clear=True)

            for index, user in enumerate(session[0]['AdditionalUsers']):
#                info = self.API.get_user(user['UserId'])
                image = self.API.get_user_artwork(user['UserId'])
                self.Utils.Basics.window('emby.AdditionalUserImage.%s' % index, image)
                self.Utils.Basics.window('emby.AdditionalUserPosition.%s' % user['UserId'], str(index))

        self.save_state()

        #Websocket
        self.wsock = ws_client.WSClient(self.Data['auth.server'], self.Data['app.device_id'], self.Data['auth.token'], self.server_id)
        self.wsock.start()

    def stop(self):
        self.LOG.info("---[ STOP EMBYCLIENT: %s ]---" % self.server_id)

        if self.wsock:
            self.wsock.close()

        self.wsock = None
        self.http.stop_session()

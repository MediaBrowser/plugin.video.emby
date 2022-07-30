import json
from _thread import start_new_thread
from dialogs import serverconnect, usersconnect, loginconnect, loginmanual, servermanual
from helper import utils, loghandler
from database import library
from hooks import websocket
from . import views, api, http, connection_manager
LOG = loghandler.LOG('EMBY.emby.emby')


class EmbyServer:
    def __init__(self, UserDataChanged, ServerSettings):
        self.UserDataChanged = UserDataChanged
        self.Websocket = None
        self.config = None
        self.logged_in = False
        self.server_id = ""
        self.ServerSettings = ServerSettings
        self.ServerData = {}
        self.Name = None
        self.Token = None
        self.user_id = None
        self.server = None
        self.library = None
        self.Online = False
        self.ServerReconnecting = False
        self.http = http.HTTP(self)
        self.connect_manager = connection_manager.ConnectionManager(self)
        self.API = api.API(self)
        self.Views = views.Views(self)
        self.library = library.Library(self)
        self.Firstrun = not bool(self.ServerSettings)
        LOG.info("---[ INIT EMBYCLIENT: ]---")

    def ServerUnreachable(self):
        if not self.ServerReconnecting:
            utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33146))
            start_new_thread(self.ServerReconnect, ())

    def ServerReconnect(self, Terminate=True):
        if not self.ServerReconnecting:
            self.ServerReconnecting = True
            Tries = 0

            if Terminate:
                self.stop()

            while True:
                if utils.SystemShutdown:
                    break

                SignedIn, _ = self.register()

                if SignedIn:
                    break

                # Delay reconnect: Fast 40 re-tries (first 10 seconds), after delay by 5 seconds
                if Tries > 40:
                    if utils.sleep(5):
                        break
                else:
                    Tries += 1

                    if utils.sleep(0.25):
                        break

            self.ServerReconnecting = False

    def authenticate(self):
        state = self.connect_manager.connect()

        if not state:
            return {}

        if 'State' in state:
            if state['State'] == 3:  # SignedIn
                self.logged_in = True
                LOG.info("User is authenticated.")

        return state

    def start(self):
        if not self.logged_in:
            LOG.error("User is not logged in.")
            return False

        LOG.info("---[ START EMBYCLIENT: %s ]---" % self.server_id)
        session = self.API.get_device()

        if not session:
            LOG.error("---[ SESSION ERROR EMBYCLIENT: %s ] %s ---" % (self.server_id, session))
            return False

        self.API.post_capabilities({
            'Id': session[0]['Id'],
            'PlayableMediaTypes': "Audio,Video,Photo",
            'SupportsMediaControl': True,
            'SupportsSync': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,Mute,Unmute,SetVolume,Pause,Unpause,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"
        })
        self.load_credentials()

        if 'Users' in self.ServerData:
            for UserId in self.ServerData['Users']:
                self.API.session_add_user(session[0]['Id'], UserId, True)

        if utils.connectMsg:
            utils.Dialog.notification(heading=utils.addon_name, message="%s %s" % (utils.Translate(33000), session[0]['UserName']), icon=utils.icon, time=1500, sound=False)

        self.Views.update_views()
        self.library.load_settings()
        self.Views.update_nodes()
        start_new_thread(self.library.KodiStartSync, (self.Firstrun,))  # start initial sync
        self.Websocket = websocket.WSClient(self)
        self.Websocket.start()
        self.Online = True
        utils.SyncPause[self.server_id] = False
        LOG.info("[ Server Online ]")
        return True

    def stop(self):
        LOG.info("---[ STOP EMBYCLIENT: %s ]---" % self.server_id)
        utils.SyncPause[self.server_id] = True
        self.Online = False

        if self.Websocket:
            self.Websocket.close()
            self.Websocket = None

        self.http.stop_session()

    def add_AdditionalUser(self, UserId):
        if 'Users' not in self.ServerData:
            self.ServerData['Users'] = []

        self.ServerData['Users'].append(UserId)
        self.save_credentials()
        session = self.API.get_device()
        self.API.session_add_user(session[0]['Id'], UserId, True)

    def remove_AdditionalUser(self, UserId):
        self.ServerData['Users'].remove(UserId)

        if not self.ServerData['Users']:
            del self.ServerData['Users']

        self.save_credentials()
        session = self.API.get_device()
        self.API.session_add_user(session[0]['Id'], UserId, False)

    # Login into server. If server is None, then it will show the proper prompts to login, etc.
    # If a server id is specified then only a login dialog will be shown for that server.
    def register(self):
        LOG.info("--[ server/%s ]" % "DEFAULT")
        self.load_credentials()
        SignedIn = self.register_client(True)

        if SignedIn:
            if self.start():
                return self.server_id, self

            return False, None

        return SignedIn, None

    def save_credentials(self):
        if not self.ServerSettings:
            self.ServerSettings = "%s%s" % (utils.FolderAddonUserdata, 'servers_%s.json' % self.server_id)

        utils.writeFileString(self.ServerSettings, json.dumps(self.ServerData, sort_keys=True, indent=4, ensure_ascii=False))

    def load_credentials(self):
        if self.ServerSettings:
            FileData = utils.readFileString(self.ServerSettings)
            self.ServerData = json.loads(FileData)
        else:
            self.ServerData = {}

    def register_client(self, server_selection):
        state = self.authenticate()

        if not state:
            return False

        if state:
            if state['State'] == 3:  # SignedIn
                self.server_id = state['Servers'][0]['Id']
                utils.DatabaseFiles[self.server_id] = utils.translatePath("special://profile/Database/emby_%s.db" % self.server_id)
                self.save_credentials()
                return True

            if state['State'] == 0:  # Unavailable
                return False

            if server_selection or state['State'] in (4, 1):  # ConnectSignIn or ServerSelection
                result = self.select_servers(state)

                if not result:  # Cancel
                    return False
            elif state['State'] == 2:  # ServerSignIn
                if 'ExchangeToken' not in state['Servers'][0]:
                    result = self.login()

                    if not result:  # Cancel
                        return False
            elif state['State'] == 0:  # Unavailable
                return False

            return self.register_client(False)

        return False

    # Save user info
    def get_user(self):
        user = self.API.get_user(None)
        self.config = self.API.get_system_info()
        utils.set_settings('username', user['Name'])

    def select_servers(self, state):
        if not state:
            state = self.connect_manager.connect()

            if not state:
                return False

        user = state.get('ConnectUser') or {}
        Dialog = serverconnect.ServerConnect("script-emby-connect-server.xml", *utils.CustomDialogParameters)
        Dialog.PassVar(self.connect_manager, user.get('ImageUrl'), not user)
        Dialog.doModal()

        if Dialog.is_server_selected():
            LOG.debug("Server selected: %s" % self.ServerData)
            return True

        if Dialog.is_connect_login():
            LOG.debug("Login with emby connect")

            if self.login_connect():
                return True
        elif Dialog.is_manual_server():
            LOG.debug("Adding manual server")

            if self.manual_server():
                return True
        else:
            return False  # No server selected

        return self.select_servers({})

    # Return server or raise error
    def manual_server(self):
        Dialog = servermanual.ServerManual("script-emby-connect-server-manual.xml", *utils.CustomDialogParameters)
        Dialog.PassVar(self.connect_manager)
        Dialog.doModal()

        if Dialog.is_connected():
            self.ServerData = Dialog.get_server()
            return True

        return False

    def login(self):
        users = self.API.get_public_users()

        if not users:
            return self.login_manual(None)

        Dialog = usersconnect.UsersConnect("script-emby-connect-users.xml", *utils.CustomDialogParameters)
        Dialog.PassVar(self.server, users)
        Dialog.doModal()

        if Dialog.is_user_selected():
            user = Dialog.get_user()
            username = user['Name']

            if user['HasPassword']:
                LOG.debug("User has password, present manual login")
                Result = self.login_manual(username)

                if Result:
                    return Result
            else:
                return self.connect_manager.login(self.server, username, None, True)
        elif Dialog.is_manual_login():
            Result = self.login_manual(None)

            if Result:
                return Result
        else:
            return False  # No user selected

        return self.login()

    # Return manual login user authenticated
    def login_manual(self, user):
        Dialog = loginmanual.LoginManual("script-emby-connect-login-manual.xml", *utils.CustomDialogParameters)
        Dialog.PassVar(self.connect_manager, user)
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False  # User is not authenticated

    # Return connect user
    def login_connect(self):
        Dialog = loginconnect.LoginConnect("script-emby-connect-login.xml", *utils.CustomDialogParameters)
        Dialog.PassVar(self.connect_manager)
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False  # Connect user is not logged in

# -*- coding: utf-8 -*-
import json
import threading
import xbmcaddon
import xbmc
import dialogs.serverconnect
import dialogs.usersconnect
import dialogs.loginconnect
import dialogs.loginmanual
import dialogs.servermanual
import helper.loghandler
import helper.utils as Utils
import database.library
import database.db_open
import hooks.websocket
from . import views
from . import api
from . import http
from . import connection_manager

XbmcMonitor = xbmc.Monitor()
XmlPath = (xbmcaddon.Addon(Utils.PluginId).getAddonInfo('path'), "default", "1080i")
LOG = helper.loghandler.LOG('EMBY.emby.emby')


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
        self.library = database.library.Library(self)
        self.Firstrun = not bool(self.ServerSettings)
        LOG.info("---[ INIT EMBYCLIENT: ]---")

    def ServerUnreachable(self):
        if not self.ServerReconnecting:
            Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33146))
            threading.Thread(target=self.ServerReconnect).start()

    def ServerReconnect(self, Terminate=True):
        if not self.ServerReconnecting:
            self.ServerReconnecting = True
            Tries = 0

            if Terminate:
                self.stop()

            while True:
                if Utils.SystemShutdown:
                    break

                SignedIn, _ = self.register()

                if SignedIn:
                    break

                # Delay reconnect: Fast 40 re-tries (first 10 seconds), after delay by 5 seconds
                if Tries > 40:
                    if XbmcMonitor.waitForAbort(5):
                        break
                else:
                    Tries += 1

                    if XbmcMonitor.waitForAbort(0.25):
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
        self.http.start_session()
        session = self.API.get_device()

        if not session:
            LOG.error("---[ SESSION ERROR EMBYCLIENT: %s ] %s ---" % (self.server_id, session))
            return False

        self.API.post_capabilities({
            'Id': session[0]['Id'],
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
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

        self.library.load_settings()
        self.load_credentials()

        if 'Users' in self.ServerData:
            for UserId in self.ServerData['Users']:
                self.API.session_add_user(session[0]['Id'], UserId, True)

        if Utils.connectMsg:
            Utils.dialog("notification", heading=Utils.addon_name, message="%s %s" % (Utils.Translate(33000), Utils.StringDecode(session[0]['UserName'])), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=1500, sound=False)

        self.Views.update_views()
        self.Views.update_nodes()
        threading.Thread(target=self.library.InitSync, args=(self.Firstrun,)).start()  # start initial sync
        self.Websocket = hooks.websocket.WSClient(self)
        self.Websocket.start()
        self.Online = True
        Utils.SyncPause = False
        LOG.info("[ Server Online ]")
        return True

    def stop(self):
        LOG.info("---[ STOP EMBYCLIENT: %s ]---" % self.server_id)
        Utils.SyncPause = True
        self.Online = False

        if self.Websocket:
            self.Websocket.close()
            self.Websocket.join()
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
        credentials = json.dumps(self.ServerData, sort_keys=True, indent=4, ensure_ascii=False)

        if not self.ServerSettings:
            self.ServerSettings = "%s%s" % (Utils.FolderAddonUserdata, 'servers_%s.json' % self.server_id)

        Utils.writeFileString(self.ServerSettings, credentials)

    def load_credentials(self):
        if self.ServerSettings:
            FileData = Utils.readFileString(self.ServerSettings)
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
                Utils.DatabaseFiles[self.server_id] = Utils.translatePath("special://profile/Database/emby_%s.db" % self.server_id)
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

                    if not result:
                        return False

            elif state['State'] == 0:  # Unavailable
                return False

            return self.register_client(False)

        return False

    # Save user info
    def get_user(self):
        user = self.API.get_user(None)
        self.config = self.API.get_system_info()
        Utils.set_settings('username', user['Name'])

        if 'PrimaryImageTag' in user:
            Utils.emby_UserImage = self.API.get_user_artwork(user['Id'])

    def select_servers(self, state):
        if not state:
            state = self.connect_manager.connect()

            if not state:
                return False

        user = state.get('ConnectUser') or {}
        Dialog = dialogs.serverconnect.ServerConnect("script-emby-connect-server.xml", *XmlPath)
        Dialog.PassVar(self.connect_manager, user.get('ImageUrl'), not user)
        Dialog.doModal()

        if Dialog.is_server_selected():
            LOG.debug("Server selected: %s" % self.ServerData)
            return True

        if Dialog.is_connect_login():
            LOG.debug("Login with emby connect")
            self.login_connect()
        elif Dialog.is_manual_server():
            LOG.debug("Adding manual server")
            return self.manual_server()
        else:
            return False  # No server selected

        return self.select_servers({})

    # Return server or raise error
    def manual_server(self):
        Dialog = dialogs.servermanual.ServerManual("script-emby-connect-server-manual.xml", *XmlPath)
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

        Dialog = dialogs.usersconnect.UsersConnect("script-emby-connect-users.xml", *XmlPath)
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
        Dialog = dialogs.loginmanual.LoginManual("script-emby-connect-login-manual.xml", *XmlPath)
        Dialog.PassVar(self.connect_manager, user)
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False  # User is not authenticated

    # Return connect user
    def login_connect(self):
        Dialog = dialogs.loginconnect.LoginConnect("script-emby-connect-login.xml", *XmlPath)
        Dialog.PassVar(self.connect_manager)
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False  # Connect user is not logged in

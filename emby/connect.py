# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon

import database.database
import dialogs.serverconnect
import dialogs.usersconnect
import dialogs.loginconnect
import dialogs.loginmanual
import dialogs.servermanual
import helper.loghandler
import helper.api
import emby.main

class Connect(): #ADD SERVER NUMBER FOR SELECTION OR RETURN SERVER ARRAY
    def __init__(self, Monitor):
        self.Monitor = Monitor
        self.XML_PATH = (xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('path'), "default", "1080i")
        self.LOG = helper.loghandler.LOG('EMBY.emby.connect.Connect')
        self.user = None
        self.config = None
        self.connect_manager = None
        self.EmbyServerObj = emby.main.Emby()

    def _save_servers(self, new_servers, default):
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)

        if not new_servers:
            return credentials

        for new_server in new_servers:
            for server in credentials['Servers']:
                if server['Id'] == new_server['Id']:
                    server.update(new_server)

                    if default:
                        credentials['Servers'].remove(server)
                        credentials['Servers'].insert(0, server)

                    break
            else:
                if default:
                    credentials['Servers'].insert(0, new_server)
                else:
                    credentials['Servers'].append(new_server)

        if default:
            default_server = new_servers[0]

            for server in credentials['Servers']:
                if server['Id'] == default_server['Id']:
                    credentials['Servers'].remove(server)

            credentials['Servers'].insert(0, default_server)

        return credentials

    #Login into server. If server is None, then it will show the proper prompts to login, etc.
    #If a server id is specified then only a login dialog will be shown for that server.
    def register(self, options):
        self.LOG.info("--[ server/%s ]" % "DEFAULT")
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)
        new_credentials = self.register_client(credentials, options, not self.Monitor.Service.Utils.settings('SyncInstallRunDone.bool'))

        if new_credentials:
            server_id = new_credentials['Servers'][0]['Id']
            credentials = self._save_servers(new_credentials['Servers'], server_id)
            new_credentials.update(credentials)
            database.database.save_credentials(self.Monitor.Service.Utils, new_credentials)
            return server_id, self.EmbyServerObj                    #, new_credentials['Servers'][0]['Name']

        return False, None

    #Returns boolean value.
    #True: verify connection.
    def get_ssl(self):
        return self.Monitor.Service.Utils.settings('sslverify.bool')

    #Set Emby client
    def set_client(self):
        self.EmbyServerObj.Data['app.name'] = "Kodi"
        self.EmbyServerObj.Data['app.version'] = self.Monitor.Service.Utils.device_info['Version']
        self.EmbyServerObj.Data['app.device_name'] = self.Monitor.Service.Utils.device_info['DeviceName']
        self.EmbyServerObj.Data['app.device_id'] = self.Monitor.Service.Utils.device_info['DeviceId']
        self.EmbyServerObj.Data['app.capabilities'] = None
        self.EmbyServerObj.Data['http.user_agent'] = "Emby-Kodi/%s" % self.Monitor.Service.Utils.device_info['Version']
        self.EmbyServerObj.Data['auth.ssl'] = self.Monitor.Service.Utils.settings('sslverify.bool')

    def register_client(self, credentials, options, server_selection):
        self.set_client()
        self.connect_manager = self.EmbyServerObj.auth
        state = self.EmbyServerObj.authenticate(credentials or {}, options or {})

        if state:
            if state['State'] == 3: #SignedIn
                server_id = state['Servers'][0]['Id']
                self.EmbyServerObj.server_id = server_id
                return state['Credentials']

            if state['State'] == 0: #Unavailable
                return False

            if server_selection or state['State'] in (4, 1): #ConnectSignIn or ServerSelection
                result = self.select_servers(state)

                if not result: #Cancel
                    return False
            elif state['State'] == 2: #ServerSignIn
                if 'ExchangeToken' not in state['Servers'][0]:
                    self.login()
            elif state['State'] == 0: #Unavailable
                return False

            return self.register_client(state['Credentials'], options, False)

        return self.EmbyServerObj.auth.credentials.get_credentials()

    #Save user info
    def get_user(self):
        self.user = self.EmbyServerObj.API.get_user(None)
        self.config = self.EmbyServerObj.API.get_system_info()
        self.Monitor.Service.Utils.settings('username', self.user['Name'])

        if 'PrimaryImageTag' in self.user:
            self.Monitor.Service.Utils.window('emby.UserImage', helper.api.API(self.user, self.Monitor.Service.Utils, self.EmbyServerObj.auth.get_serveraddress()).get_user_artwork(self.user['Id']))

    def select_servers(self, state):
        if not state:
            state = self.connect_manager.connect({'enableAutoLogin': False})

            if not state:
                return False

        user = state.get('ConnectUser') or {}
        Dialog = dialogs.serverconnect.ServerConnect("script-emby-connect-server.xml", *self.XML_PATH)
        Dialog.set_args(**{
            'connect_manager': self.connect_manager,
            'username': user.get('DisplayName', ""),
            'user_image': user.get('ImageUrl'),
            'servers': state.get('Servers', []),
            'emby_connect': not user
        })
        Dialog.doModal()

        if Dialog.is_server_selected():
            self.LOG.debug("Server selected: %s" % Dialog.get_server())
            return True

        if Dialog.is_connect_login():
            self.LOG.debug("Login with emby connect")
            self.login_connect(None)
        elif Dialog.is_manual_server():
            self.LOG.debug("Adding manual server")
            self.manual_server(None)
        else:
            return False #"No server selected"

        return self.select_servers(None)

    #Setup manual servers
    def setup_manual_server(self):
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)
        self.set_client()
        self.EmbyServerObj.auth.credentials.set_credentials(credentials)
        manager = self.EmbyServerObj.auth

        if not self.manual_server(manager):
            return

        new_credentials = self.EmbyServerObj.auth.credentials.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'], False)
        database.database.save_credentials(self.Monitor.Service.Utils, credentials)

    #Return server or raise error
    def manual_server(self, manager):
        Dialog = dialogs.servermanual.ServerManual("script-emby-connect-server-manual.xml", *self.XML_PATH)
        Dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        Dialog.doModal()

        if Dialog.is_connected():
            return Dialog.get_server()

        #raise RuntimeError("Server is not connected")
        return False

    #Setup emby connect by itself
    def setup_login_connect(self):
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)
        self.set_client()
        self.EmbyServerObj.auth.credentials.set_credentials(credentials)
        manager = self.EmbyServerObj.auth

        if not self.login_connect(manager):
            return

        new_credentials = self.EmbyServerObj.auth.credentials.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'], False)
        database.database.save_credentials(self.Monitor.Service.Utils, credentials)

    #Return connect user or raise error
    def login_connect(self, manager):
        Dialog = dialogs.loginconnect.LoginConnect("script-emby-connect-login.xml", *self.XML_PATH)
        Dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False #"Connect user is not logged in"

    def login(self):
        users = self.EmbyServerObj.API.get_public_users()
        server = self.EmbyServerObj.auth.get_serveraddress()

        if not users:
            return self.login_manual(None, None)

        Dialog = dialogs.usersconnect.UsersConnect("script-emby-connect-users.xml", *self.XML_PATH)
        Dialog.set_args(**{'server': server, 'users': users})
        Dialog.doModal()

        if Dialog.is_user_selected():
            user = Dialog.get_user()
            username = user['Name']

            if user['HasPassword']:
                self.LOG.debug("User has password, present manual login")
                Result = self.login_manual(username, None)

                if Result:
                    return Result
            else:
                return self.connect_manager.login(server, username, None, True, {})
        elif Dialog.is_manual_login():
            Result = self.login_manual(None, None)

            if Result:
                return Result
        else:
            return False #"No user selected"

        return self.login()

    #Setup manual login by itself for default server
    def setup_login_manual(self, server_id):
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)
        self.set_client()
        self.EmbyServerObj.auth.credentials.set_credentials(credentials)

        if not self.login_manual(None, self.EmbyServerObj.auth):
            return

        new_credentials = self.EmbyServerObj.auth.credentials.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'], False)
        database.database.save_credentials(self.Monitor.Service.Utils, credentials)

    #Return manual login user authenticated or raise error
    def login_manual(self, user, manager):
        Dialog = dialogs.loginmanual.LoginManual("script-emby-connect-login-manual.xml", *self.XML_PATH)
        Dialog.set_args(**{'connect_manager': manager or self.connect_manager, 'username': user or {}})
        Dialog.doModal()

        if Dialog.is_logged_in():
            return Dialog.get_user()

        return False #"User is not authenticated"

    #Stop client and remove server
    def remove_server(self, server_id):
        self.Monitor.EmbyServer[server_id].close()
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)

        for server in credentials['Servers']:
            if server['Id'] == server_id:
                credentials['Servers'].remove(server)
                break

        database.database.save_credentials(self.Monitor.Service.Utils, credentials)
        self.LOG.info("[ remove server ] %s" % server_id)

    #Allow user to setup ssl verification for additional servers
    def set_ssl(self, server_id):
        value = self.Monitor.Service.Utils.Dialog("yesno", heading="{emby}", line1=self.Monitor.Service.Utils.Translate(33217))
        credentials = database.database.get_credentials(self.Monitor.Service.Utils)

        for server in credentials['Servers']:
            if server['Id'] == server_id:
                server['verify'] = bool(value)
                database.database.save_credentials(self.Monitor.Service.Utils, credentials)
                self.LOG.info("[ ssl/%s/%s ]" % (server_id, server['verify']))
                break

# -*- coding: utf-8 -*-
import logging

import xbmc
import xbmcaddon
import database.database
import dialogs.serverconnect
import dialogs.usersconnect
import dialogs.loginconnect
import dialogs.loginmanual
import dialogs.servermanual
import helper.translate
import helper.api
from . import main
from .core import connection_manager
from .core import exceptions

class Connect():
    pending = []

    def __init__(self, Utils):
        self.Utils = Utils
        self.info = self.Utils.get_info()
        self.XML_PATH = (xbmcaddon.Addon(self.Utils.addon_id()).getAddonInfo('path'), "default", "1080i")
        self.LOG = logging.getLogger("EMBY.connect.Connect")
        self.user = None
        self.config = None
        self.connect_manager = None

    def _save_servers(self, new_servers, default=False):
        credentials = database.database.get_credentials()

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
    def register(self, server_id=None, options={}):
        self.LOG.info("--[ server/%s ]", server_id or 'default')

        if (server_id) in self.pending:
            self.LOG.info("[ server/%s ] is already being registered", server_id or 'default')
            return

        self.pending.append(server_id)
        credentials = database.database.get_credentials()

        if server_id is None and credentials['Servers']:
            credentials['Servers'] = [credentials['Servers'][0]]
        elif credentials['Servers']:
            for server in credentials['Servers']:
                if server['Id'] == server_id:
                    credentials['Servers'] = [server]

        server_select = bool(server_id is None and not self.Utils.settings('SyncInstallRunDone.bool'))

        try:
            new_credentials = self.register_client(credentials, options, server_id, server_select)
            credentials = self._save_servers(new_credentials['Servers'], server_id is None)
            new_credentials.update(credentials)
            database.database.save_credentials(new_credentials)
            main.Emby(server_id).start(not bool(server_id), True)
        except exceptions.HTTPException as error:
            if error.status == 'ServerUnreachable':
                self.pending.remove(server_id)
                raise
        except ValueError as error:
            self.LOG.error(error)

        self.pending.remove(server_id)

    #Returns boolean value.
    #True: verify connection.
    def get_ssl(self):
        return self.Utils.settings('sslverify.bool')

    #Get Emby client
    def get_client(self, server, server_id=None):
        client = main.Emby(server_id)
        client['config/app']("Kodi", self.info['Version'], self.info['DeviceName'], self.info['DeviceId'])
        client['config']['http.user_agent'] = "Emby-Kodi/%s" % self.info['Version']
        client['config']['auth.ssl'] = server.get('verify', self.get_ssl())
        return client

    def register_client(self, credentials=None, options=None, server_id=None, server_selection=False):
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {}, server_id)
        self.connect_manager = client.auth

        if server_id is None:
            client['config']['app.default'] = True

        try:
            state = client.authenticate(credentials or {}, options or {})

            if state['State'] == connection_manager.CONNECTION_STATE['SignedIn']:
                client.callback_ws = self.Utils.event

                if server_id is None: # Only assign for default server
                    client.callback = self.Utils.event
                    self.get_user(client)
                    self.Utils.settings('serverName', client['config/auth.server-name'])
                    self.Utils.settings('server', client['config/auth.server'])

                self.Utils.event('LoadServer', {'ServerId': server_id})
                return state['Credentials']

            if (server_selection or state['State'] in (connection_manager.CONNECTION_STATE['ConnectSignIn'], connection_manager.CONNECTION_STATE['ServerSelection']) or state['State'] == connection_manager.CONNECTION_STATE['Unavailable'] and not self.Utils.settings('SyncInstallRunDone.bool')):
                self.select_servers(state)
            elif state['State'] == connection_manager.CONNECTION_STATE['ServerSignIn']:
                if 'ExchangeToken' not in state['Servers'][0]:
                    self.login()
            elif state['State'] == connection_manager.CONNECTION_STATE['Unavailable']:
                raise exceptions.HTTPException('ServerUnreachable', {})

            return self.register_client(state['Credentials'], options, server_id, False)
        except RuntimeError as error:
            self.LOG.exception(error)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.Utils.addon_id())
            raise Exception('User sign in interrupted')
        except exceptions.HTTPException as error:
            if error.status == 'ServerUnreachable':
                self.Utils.event('ServerUnreachable', {'ServerId': server_id})
                raise

            return client.get_credentials()

    #Save user info
    def get_user(self, client):
        self.user = client['api'].get_user()
        self.config = client['api'].get_system_info()
        self.Utils.settings('username', self.user['Name'])

        if 'PrimaryImageTag' in self.user:
            self.Utils.window('EmbyUserImage', helper.api.API(self.user, self.Utils, client['auth/server-address']).get_user_artwork(self.user['Id']))

    def select_servers(self, state=None):
        state = state or self.connect_manager.connect({'enableAutoLogin': False})
        user = state.get('ConnectUser') or {}
        self.Utils.dialog = dialogs.serverconnect.ServerConnect("script-emby-connect-server.xml", *self.XML_PATH)
        self.Utils.dialog.set_args(**{
            'connect_manager': self.connect_manager,
            'username': user.get('DisplayName', ""),
            'user_image': user.get('ImageUrl'),
            'servers': state.get('Servers', []),
            'emby_connect': not user
        })
        self.Utils.dialog.doModal()

        if self.Utils.dialog.is_server_selected():
            self.LOG.debug("Server selected: %s", self.Utils.dialog.get_server())
            return

        if self.Utils.dialog.is_connect_login():
            self.LOG.debug("Login with emby connect")

            try:
                self.login_connect()
            except RuntimeError:
                pass
        elif self.Utils.dialog.is_manual_server():
            self.LOG.debug("Adding manual server")

            try:
                self.manual_server()
            except RuntimeError:
                pass
        else:
            raise RuntimeError("No server selected")

        return self.select_servers()

    #Setup manual servers
    def setup_manual_server(self):
        credentials = database.database.get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.manual_server(manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        database.database.save_credentials(credentials)

    #Return server or raise error
    def manual_server(self, manager=None):
        self.Utils.dialog = dialogs.servermanual.ServerManual("script-emby-connect-server-manual.xml", *self.XML_PATH)
        self.Utils.dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        self.Utils.dialog.doModal()

        if self.Utils.dialog.is_connected():
            return self.Utils.dialog.get_server()

        raise RuntimeError("Server is not connected")

    #Setup emby connect by itself
    def setup_login_connect(self):
        credentials = database.database.get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.login_connect(manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        database.database.save_credentials(credentials)

    #Return connect user or raise error
    def login_connect(self, manager=None):
        self.Utils.dialog = dialogs.loginconnect.LoginConnect("script-emby-connect-login.xml", *self.XML_PATH)
        self.Utils.dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        self.Utils.dialog.doModal()

        if self.Utils.dialog.is_logged_in():
            return self.Utils.dialog.get_user()

        raise RuntimeError("Connect user is not logged in")

    def login(self):
        users = self.connect_manager['public-users']
        server = self.connect_manager['server-address']

        if not users:
            try:
                return self.login_manual()
            except RuntimeError:
                raise RuntimeError("No user selected")

        self.Utils.dialog = dialogs.usersconnect.UsersConnect("script-emby-connect-users.xml", *self.XML_PATH)
        self.Utils.dialog.set_args(**{'server': server, 'users': users})
        self.Utils.dialog.doModal()

        if self.Utils.dialog.is_user_selected():
            user = self.Utils.dialog.get_user()
            username = user['Name']

            if user['HasPassword']:
                self.LOG.debug("User has password, present manual login")

                try:
                    return self.login_manual(username)
                except RuntimeError:
                    pass
            else:
                return self.connect_manager['login'](server, username)
        elif self.Utils.dialog.is_manual_login():
            try:
                return self.login_manual()
            except RuntimeError:
                pass
        else:
            raise RuntimeError("No user selected")

        return self.login()

    #Setup manual login by itself for default server
    def setup_login_manual(self):
        credentials = database.database.get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.login_manual(manager=manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        database.database.save_credentials(credentials)

    #Return manual login user authenticated or raise error
    def login_manual(self, user=None, manager=None):
        self.Utils.dialog = dialogs.loginmanual.LoginManual("script-emby-connect-login-manual.xml", *self.XML_PATH)
        self.Utils.dialog.set_args(**{'connect_manager': manager or self.connect_manager, 'username': user or {}})
        self.Utils.dialog.doModal()

        if self.Utils.dialog.is_logged_in():
            return self.Utils.dialog.get_user()

        raise RuntimeError("User is not authenticated")

    #Stop client and remove server
    def remove_server(self, server_id):
        main.Emby(server_id).close()
        credentials = database.database.get_credentials()

        for server in credentials['Servers']:
            if server['Id'] == server_id:
                credentials['Servers'].remove(server)
                break

        database.database.save_credentials(credentials)
        self.LOG.info("[ remove server ] %s", server_id)

    #Allow user to setup ssl verification for additional servers
    def set_ssl(self, server_id):
        value = self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33217))
        credentials = database.database.get_credentials()

        for server in credentials['Servers']:
            if server['Id'] == server_id:
                server['verify'] = bool(value)
                database.database.save_credentials(credentials)
                self.LOG.info("[ ssl/%s/%s ]", server_id, server['verify'])
                break

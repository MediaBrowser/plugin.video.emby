# -*- coding: utf-8 -*-

##################################################################################################

import json
import logging
import os

import xbmc
import xbmcaddon
import xbmcvfs

import client
from database import get_credentials, save_credentials
from dialogs import ServerConnect, UsersConnect, LoginConnect, LoginManual, ServerManual
from helper import _, settings, addon_id, event, api, dialog, window
from emby import Emby
from emby.core.connection_manager import get_server_address, CONNECTION_STATE
from emby.core.exceptions import HTTPException

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
XML_PATH = (xbmcaddon.Addon(addon_id()).getAddonInfo('path'), "default", "1080i")

##################################################################################################


class Connect(object):
    pending = []

    def __init__(self):
        self.info = client.get_info()

    def _save_servers(self, new_servers, default=False):
        credentials = get_credentials()

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

    def register(self, server_id=None, options={}):

        ''' Login into server. If server is None, then it will show the proper prompts to login, etc.
            If a server id is specified then only a login dialog will be shown for that server.
        '''
        LOG.info("--[ server/%s ]", server_id or 'default')

        if (server_id) in self.pending:
            LOG.info("[ server/%s ] is already being registered", server_id or 'default')

            return

        self.pending.append(server_id)
        credentials = get_credentials()

        if server_id is None and credentials['Servers']:
            credentials['Servers'] = [credentials['Servers'][0]]
        
        elif credentials['Servers']:
            for server in credentials['Servers']:

                if server['Id'] == server_id:
                    credentials['Servers'] = [server]

        server_select = True if server_id is None and not settings('SyncInstallRunDone.bool') else False

        try:
            new_credentials = self.register_client(credentials, options, server_id, server_select)
            credentials = self._save_servers(new_credentials['Servers'], server_id is None)
            save_credentials(credentials)
            Emby(server_id).start(not bool(server_id), True)
        except HTTPException as error:

            if error.status == 'ServerUnreachable':
                self.pending.remove(server_id)

                raise

        except ValueError as error:
            LOG.error(error)

        self.pending.remove(server_id)

    def get_ssl(self):

        ''' Returns boolean value.
            True: verify connection.
        '''
        return settings('sslverify.bool')

    def get_client(self, server, server_id=None):

        ''' Get Emby client.
        '''
        client = Emby(server_id)
        client['config/app']("Kodi", self.info['Version'], self.info['DeviceName'], self.info['DeviceId'])
        client['config']['http.user_agent'] = "Emby-Kodi/%s" % self.info['Version']
        client['config']['auth.ssl'] = server.get('verify', self.get_ssl())

        return client

    def register_client(self, credentials=None, options=None, server_id=None, server_selection=False):
        
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {}, server_id)
        self.client = client
        self.connect_manager = client.auth

        if server_id is None:
            client['config']['app.default'] = True

        try:
            state = client.authenticate(credentials or {}, options or {})

            if state['State'] == CONNECTION_STATE['SignedIn']:
                client.callback_ws = event

                if server_id is None: # Only assign for default server

                    client.callback = event
                    self.get_user(client)

                    settings('serverName', client['config/auth.server-name'])
                    settings('server', client['config/auth.server'])

                event('LoadServer', {'ServerId': server_id})

                return state['Credentials']

            elif (server_selection or state['State'] in (CONNECTION_STATE['ConnectSignIn'], CONNECTION_STATE['ServerSelection']) or 
                  state['State'] == CONNECTION_STATE['Unavailable'] and not settings('SyncInstallRunDone.bool')):

                self.select_servers(state)

            elif state['State'] == CONNECTION_STATE['ServerSignIn']:
                if 'ExchangeToken' not in state['Servers'][0]:
                    self.login()

            elif state['State'] == CONNECTION_STATE['Unavailable']:
                raise HTTPException('ServerUnreachable', {})

            return self.register_client(state['Credentials'], options, server_id, False)

        except RuntimeError as error:

            LOG.exception(error)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon_id())

            raise Exception('User sign in interrupted')

        except HTTPException as error:

            if error.status == 'ServerUnreachable':
                event('ServerUnreachable', {'ServerId': server_id})

                raise

            return client.get_credentials()


    def get_user(self, client):

        ''' Save user info.
        '''
        self.user = client['api'].get_user()
        self.config = client['api'].get_system_info()

        settings('username', self.user['Name'])
        settings('SeasonSpecials.bool', self.config.get('DisplaySpecialsWithinSeasons', True))

        if 'PrimaryImageTag' in self.user:
            window('EmbyUserImage', api.API(self.user, client['auth/server-address']).get_user_artwork(self.user['Id']))

    def select_servers(self, state=None):

        state = state or self.connect_manager.connect({'enableAutoLogin': False})
        user = state.get('ConnectUser') or {}

        dialog = ServerConnect("script-emby-connect-server.xml", *XML_PATH)
        dialog.set_args(**{
            'connect_manager': self.connect_manager,
            'username': user.get('DisplayName', ""),
            'user_image': user.get('ImageUrl'),
            'servers': state.get('Servers', []),
            'emby_connect': False if user else True
        })
        dialog.doModal()

        if dialog.is_server_selected():
            LOG.debug("Server selected: %s", dialog.get_server())
            return

        elif dialog.is_connect_login():
            LOG.debug("Login with emby connect")
            try:
                self.login_connect()
            except RuntimeError: pass

        elif dialog.is_manual_server():
            LOG.debug("Adding manual server")
            try:
                self.manual_server()
            except RuntimeError: pass
        else:
            raise RuntimeError("No server selected")

        return self.select_servers()

    def setup_manual_server(self):

        ''' Setup manual servers
        '''
        credentials = get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.manual_server(manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        save_credentials(credentials)

    def manual_server(self, manager=None):

        ''' Return server or raise error.
        '''
        dialog = ServerManual("script-emby-connect-server-manual.xml", *XML_PATH)
        dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        dialog.doModal()

        if dialog.is_connected():
            return dialog.get_server()
        else:
            raise RuntimeError("Server is not connected")

    def setup_login_connect(self):

        ''' Setup emby connect by itself.
        '''
        credentials = get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.login_connect(manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        save_credentials(credentials)

    def login_connect(self, manager=None):

        ''' Return connect user or raise error.
        '''
        dialog = LoginConnect("script-emby-connect-login.xml", *XML_PATH)
        dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        dialog.doModal()

        if dialog.is_logged_in():
            return dialog.get_user()
        else:
            raise RuntimeError("Connect user is not logged in")

    def login(self):

        users = self.connect_manager['public-users']
        server = self.connect_manager['server-address']

        if not users:
            try:
                return self.login_manual()
            except RuntimeError:
                raise RuntimeError("No user selected")

        dialog = UsersConnect("script-emby-connect-users.xml", *XML_PATH)
        dialog.set_args(**{'server': server, 'users': users})
        dialog.doModal()

        if dialog.is_user_selected():
            user = dialog.get_user()
            username = user['Name']

            if user['HasPassword']:
                LOG.debug("User has password, present manual login")
                try:
                    return self.login_manual(username)
                except RuntimeError: pass
            else:
                return self.connect_manager['login'](server, username)

        elif dialog.is_manual_login():
            try:
                return self.login_manual()
            except RuntimeError: pass
        else:
            raise RuntimeError("No user selected")

        return self.login()

    def setup_login_manual(self):

        ''' Setup manual login by itself for default server.
        '''
        credentials = get_credentials()
        client = self.get_client(credentials['Servers'][0] if credentials['Servers'] else {})
        client.set_credentials(credentials)
        manager = client.auth

        try:
            self.login_manual(manager=manager)
        except RuntimeError:
            return

        new_credentials = client.get_credentials()
        credentials = self._save_servers(new_credentials['Servers'])
        save_credentials(credentials)

    def login_manual(self, user=None, manager=None):
        
        ''' Return manual login user authenticated or raise error.
        '''
        dialog = LoginManual("script-emby-connect-login-manual.xml", *XML_PATH)
        dialog.set_args(**{'connect_manager': manager or self.connect_manager, 'username': user or {}})
        dialog.doModal()

        if dialog.is_logged_in():
            return dialog.get_user()
        else:
            raise RuntimeError("User is not authenticated")

    def remove_server(self, server_id):

        ''' Stop client and remove server.
        '''
        Emby(server_id).close()
        credentials = get_credentials()

        for server in credentials['Servers']:

            if server['Id'] == server_id:
                credentials['Servers'].remove(server)

                break

        save_credentials(credentials)
        LOG.info("[ remove server ] %s", server_id)

    def set_ssl(self, server_id):

        ''' Allow user to setup ssl verification for additional servers.
        '''
        value = dialog("yesno", heading="{emby}", line1=_(33217))
        credentials = get_credentials()

        for server in credentials['Servers']:

            if server['Id'] == server_id:
                server['verify'] = bool(value)

                break

        save_credentials(credentials)
        LOG.info("[ ssl/%s/%s ]", server_id, server['verify'])


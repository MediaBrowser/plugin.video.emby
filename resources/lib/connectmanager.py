# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcaddon
import xbmcgui

import clientinfo
import connect.connectionmanager as connectionmanager
from dialog.serverconnect import ServerConnect
from dialog.usersconnect import UsersConnect
from dialog.loginconnect import LoginConnect
import dialog.servermanual as servermanual
import dialog.loginmanual as loginmanual
import read_embyserver as embyserver

from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon(id='plugin.video.emby')

ADDON_PATH = addon.getAddonInfo('path')

##################################################################################################


class ConnectManager(object):

    # Borg - multiple instances, shared state
    _shared_state = {}
    state = {}


    def __init__(self):

        self.__dict__ = self._shared_state
        clientInfo = clientinfo.ClientInfo()
        self.emby = embyserver.Read_EmbyServer()
        
        version = clientInfo.getVersion()
        deviceName = clientInfo.getDeviceName()
        deviceId = clientInfo.getDeviceId()

        self._connect = connectionmanager.ConnectionManager("Kodi", version, deviceName, deviceId)
        self._connect.setFilePath(xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8'))
        self.state = self._connect.connect()
        log.info("Started with: %s" % self.state)

    def updateState(self):

        self.state = self._connect.connect({'updateDateLastAccessed': False})
        return self.state

    def getState(self):
        return self.state

    def select_servers(self):
        # Will return selected server or raise error
        dialog = ServerConnect("script-emby-connect-server.xml", ADDON_PATH, "default", "1080i")

        state = self._connect.connect({'enableAutoLogin': False})
        user = state.get('ConnectUser') or {}
        kwargs = {
            'connect_manager': self._connect,
            'username': user.get('DisplayName', ""),
            'user_image': user.get('ImageUrl'),
            'servers': state['Servers'],
            'emby_connect': False if user else True
        }
        dialog.set_args(**kwargs)
        dialog.doModal()

        if dialog.is_server_selected():
            log.debug("Server selected")
            return dialog.get_server()

        elif dialog.is_connect_login():
            log.debug("Login with Emby Connect")
            try: # Login to emby connect
                self.login_connect()
            except RuntimeError:
                pass
            return self.select_servers()

        elif dialog.is_manual_server():
            log.debug("Add manual server")
            try: # Add manual server address
                return self.manual_server()
            except RuntimeError:
                return self.select_servers()
        else:
            raise RuntimeError("No server selected")

    def manual_server(self):
        # Return server
        dialog = servermanual.ServerManual("script-emby-connect-server-manual.xml", ADDON_PATH, "default", "1080i")
        dialog.setConnectManager(self._connect)
        dialog.doModal()

        if dialog.isConnected():
            return dialog.getServer()
        else:
            raise RuntimeError("Server is not connected")

    def login_connect(self):
        # Return connect user
        dialog = LoginConnect("script-emby-connect-login.xml", ADDON_PATH, "default", "1080i")
        dialog.set_connect_manager(self._connect)
        dialog.doModal()

        self.updateState()

        if dialog.is_logged_in():
            return dialog.get_user()
        else:
            raise RuntimeError("Connect user is not logged in")

    def login(self, server=None):
        # Return user
        server = server or self.state['Servers'][0]
        server_address = connectionmanager.getServerAddress(server, server['LastConnectionMode'])

        users = self.emby.getUsers(server_address)

        dialog = UsersConnect("script-emby-connect-users.xml", ADDON_PATH, "default", "1080i")
        dialog.set_server(server_address)
        dialog.set_users(users)
        dialog.doModal()

        if dialog.is_user_selected():
            user = dialog.get_user()
            if user['HasPassword']:
                log.debug("User has password, present manual login")
                try:
                    return self.login_manual(server_address, user)
                except RuntimeError:
                    return self.login(server)
            else:
                user = self.emby.loginUser(server_address, user['Name'])
                self._connect.onAuthenticated(user)
                return user
        elif dialog.is_manual_login():
            try:
                return self.login_manual(server_address)
            except RuntimeError: # User selected cancel
                return self.login(server)
        else:
            raise RuntimeError("No user selected")

    def login_manual(self, server, user=None):
        
        dialog = loginmanual.LoginManual("script-emby-connect-login-manual.xml", ADDON_PATH, "default", "1080i")
        dialog.setServer(server)
        dialog.setUser(user)
        dialog.doModal()

        if dialog.isLoggedIn():
            user = dialog.getUser()
            self._connect.onAuthenticated(user)
            return user
        else:
            raise RuntimeError("User is not authenticated")
# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcaddon
import xbmcgui

import clientinfo
import connect.connectionmanager as connectionmanager
import dialog.loginconnect as loginconnect
import dialog.serverconnect as serverconnect
import dialog.servermanual as servermanual
import dialog.usersconnect as usersconnect
import dialog.loginmanual as loginmanual
import read_embyserver as embyserver

from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon(id='plugin.video.emby')

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
        log.info("cred: %s" %self.state)

    def updateState(self):

        self.state = self._connect.connect({'updateDateLastAccessed': False})
        return self.state

    def getState(self):
        return self.state

    def select_servers(self):
        # Will return selected server or raise error
        user = self.state.get('ConnectUser') or {}
        kwargs = {
            'connect_manager': self._connect,
            'user_name': user.get('DisplayName',""),
            'user_image': user.get('ImageUrl'),
            'servers': self._connect.getAvailableServers(),
            'emby_connect': False if user else True
        }
        dialog = serverconnect.ServerConnect("script-emby-connect-server.xml", addon.getAddonInfo('path'), "default", "1080i", **kwargs)
        dialog.doModal()

        if dialog.isServerSelected():
            log.debug("Server selected")
            return dialog.getServer()

        elif dialog.isEmbyConnectLogin():
            log.debug("Login with Emby Connect")
            try: # Login to emby connect
                self.login_connect()
            except RuntimeError:
                pass
            return self.select_servers()

        elif dialog.isManualServerLogin():
            log.debug("Add manual server")
            try: # Add manual server address
                return self.manual_server()
            except RuntimeError:
                return self.select_servers()
        else:
            raise RuntimeError("No server selected")

    def manual_server(self):
        # Return server
        dialog = servermanual.ServerManual("script-emby-connect-server-manual.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setConnectManager(self._connect)
        dialog.doModal()

        if dialog.isConnected():
            return dialog.getServer()
        else:
            raise RuntimeError("Server is not connected")

    def login_connect(self):
        # Return connect user
        dialog = loginconnect.LoginConnect("script-emby-connect-login.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setConnectManager(self._connect)
        dialog.doModal()

        self.updateState()

        if dialog.isLoggedIn():
            return dialog.getUser()
        else:
            raise RuntimeError("Connect user is not logged in")

    def login(self, server=None):
        # Return user
        server = server or self.state['Servers'][0]
        server = connectionmanager.getServerAddress(server, server['LastConnectionMode'])

        users = self.emby.getUsers(server)

        dialog = usersconnect.UsersConnect("script-emby-connect-users.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setUsers(users)
        dialog.doModal()

        if dialog.isUserSelected():
            user = dialog.getUser()
            if user['HasPassword']:
                log.info("User has password, present manual login")
                try:
                    return self.login_manual(server, user)
                except RuntimeError:
                    return self.login()
            else:
                return self.emby.loginUser(server, user['Name'])
        elif dialog.isManualConnectLogin():
            try:
                return self.login_manual(server)
            except RuntimeError: # User selected cancel
                return self.login()
        else:
            raise RuntimeError("No user selected")

    def login_manual(self, server, user=None):
        
        dialog = loginmanual.LoginManual("script-emby-connect-login-manual.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setServer(server)
        dialog.setUser(user)
        dialog.doModal()

        if dialog.isLoggedIn():
            return dialog.getUser()
        else:
            raise RuntimeError("User is not authenticated")
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
import dialog.usersconnect as usersconnect
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
        
        version = clientInfo.getVersion()
        deviceName = clientInfo.getDeviceName()
        deviceId = clientInfo.getDeviceId()

        self._connect = connectionmanager.ConnectionManager("Kodi", version, deviceName, deviceId)
        self._connect.setFilePath(xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8'))
        self.state = self._connect.connect()
        log.info("cred: %s" %self.state)

    def getState(self):

        self.state = self._connect.connect({'updateDateLastAccessed': False})
        return self.state

    def login_connect(self):

        dialog = loginconnect.LoginConnect("script-emby-connect-login.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setConnectManager(self._connect)

        dialog.doModal()

        if dialog.isLoggedIn():
            self.getState()
            return dialog.getUser()
        else:
            raise Exception("Connect user is not logged in")

    def select_servers(self):

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
            self.getState()
            return dialog.getServer()
        elif dialog.isEmbyConnectLogin():
            try:
                self.login_connect()
            except Exception:
                pass
            return self.select_servers()
        else:
            raise Exception("No server selected")

    def manual_server(self):
        # Present dialog with server + port
        pass

    def login_manual(self):
        # server login with user + pass input
        pass

    def user_selection(self):
        # Present user list
        # Process the list of users
        server = connectionmanager.getServerAddress(self.state['Servers'][0], self.state['Servers'][0]['LastConnectionMode'])
        users = embyserver.Read_EmbyServer().getUsers(server)

        dialog = usersconnect.UsersConnect("script-emby-connect-users.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setUsers(users)
        dialog.doModal()

        if dialog.isUserSelected():
            return dialog.getUser()
        elif dialog.isEmbyConnectLogin():
            # Run manual login
            pass
        else:
            raise Exception("No user selected")
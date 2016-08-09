# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcaddon

import clientinfo
import connect.connectionmanager as connectmanager
import dialog.loginconnect as loginconnect
import dialog.serverconnect as serverconnect

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon(id='plugin.video.emby')

##################################################################################################


class ConnectManager():

    # Borg - multiple instances, shared state
    _shared_state = {}

    state = {}


    def __init__(self):

        self.__dict__ = self._shared_state
        clientInfo = clientinfo.ClientInfo()
        
        version = clientInfo.getVersion()
        deviceName = clientInfo.getDeviceName()
        deviceId = clientInfo.getDeviceId()

        self._connect = connectmanager.ConnectionManager("Kodi", version, deviceName, deviceId)
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

        user = self.state.get('ConnectUser')

        dialog = serverconnect.ServerConnect("script-emby-connect-server.xml", addon.getAddonInfo('path'), "default", "1080i")
        dialog.setConnectManager(self._connect)
        dialog.setName(user.get('DisplayName',""))
        if user.get('ImageUrl'):
            dialog.setImage(user['ImageUrl'])
        dialog.setServers(self._connect.getAvailableServers())

        dialog.doModal()

        if dialog.isServerSelected():
            self.getState()
            return dialog.getServer()
        else:
            raise Exception("No server selected")

    def login_manual(self):
        # server login
        pass

    def server_discovery(self):
        # Lan options
        pass 
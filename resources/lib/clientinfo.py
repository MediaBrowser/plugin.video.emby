# -*- coding: utf-8 -*-

#################################################################################################

import os
from uuid import uuid4

import xbmc
import xbmcaddon

import utils

#################################################################################################


class ClientInfo():


    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.addonName = self.getAddonName()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name')

    def getAddonId(self):

        return "plugin.video.plexkodiconnect"

    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        if utils.settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel('System.FriendlyName')
        else:
            deviceName = utils.settings('deviceName')
            deviceName = deviceName.replace("\"", "_")
            deviceName = deviceName.replace("/", "_")

        return deviceName

    def getPlatform(self):

        if xbmc.getCondVisibility('system.platform.osx'):
            return "OSX"
        elif xbmc.getCondVisibility('system.platform.atv2'):
            return "ATV2"
        elif xbmc.getCondVisibility('system.platform.ios'):
            return "iOS"
        elif xbmc.getCondVisibility('system.platform.windows'):
            return "Windows"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux/RPi"
        elif xbmc.getCondVisibility('system.platform.android'): 
            return "Linux/Android"
        else:
            return "Unknown"

    def getDeviceId(self):
        """
        Returns a unique Plex client id "X-Plex-Client-Identifier" from Kodi
        settings file.
        Also loads Kodi window property 'plex_client_Id'

        If id does not exist, create one and save in Kodi settings file.
        """
        clientId = utils.window('plex_client_Id')
        if clientId:
            return clientId

        clientId = utils.settings('plex_client_Id')
        if clientId:
            utils.window('plex_client_Id', value=clientId)
            self.logMsg("Unique device Id plex_client_Id loaded: %s" % clientId, 1)
            return clientId

        self.logMsg("Generating a new deviceid.", 0)
        clientId = str(uuid4())
        utils.settings('plex_client_Id', value=clientId)
        utils.window('plex_client_Id', value=clientId)
        self.logMsg("Unique device Id plex_client_Id loaded: %s" % clientId, 1)
        return clientId

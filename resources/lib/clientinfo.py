# -*- coding: utf-8 -*-

###############################################################################

from uuid import uuid4

import xbmc
import xbmcaddon

from utils import logging, window, settings

###############################################################################


@logging
class ClientInfo():

    def __init__(self):
        self.addon = xbmcaddon.Addon()

    def getXArgsDeviceInfo(self, options=None):
        """
        Returns a dictionary that can be used as headers for GET and POST
        requests. An authentication option is NOT yet added.

        Inputs:
            options:        dictionary of options that will override the
                            standard header options otherwise set.
        Output:
            header dictionary
        """
        # Get addon infos
        xargs = {
            'Accept': '*/*',
            'Connection': 'keep-alive',
            "Content-Type": "application/x-www-form-urlencoded",
            # "Access-Control-Allow-Origin": "*",
            # 'X-Plex-Language': 'en',
            'X-Plex-Device': self.getAddonName(),
            'X-Plex-Client-Platform': self.getPlatform(),
            'X-Plex-Device-Name': self.getDeviceName(),
            'X-Plex-Platform': self.getPlatform(),
            # 'X-Plex-Platform-Version': 'unknown',
            # 'X-Plex-Model': 'unknown',
            'X-Plex-Product': self.getAddonName(),
            'X-Plex-Version': self.getVersion(),
            'X-Plex-Client-Identifier': self.getDeviceId(),
            'X-Plex-Provides': 'player',
        }

        if window('pms_token'):
            xargs['X-Plex-Token'] = window('pms_token')
        if options is not None:
            xargs.update(options)
        return xargs

    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name')

    def getAddonId(self):
        return "plugin.video.plexkodiconnect"

    def getVersion(self):
        return self.addon.getAddonInfo('version')

    def getDeviceName(self):
        if settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel(
                'System.FriendlyName').decode('utf-8')
        else:
            deviceName = settings('deviceName')
            deviceName = deviceName.replace("\"", "_")
            deviceName = deviceName.replace("/", "_")
        return deviceName

    def getPlatform(self):
        if xbmc.getCondVisibility('system.platform.osx'):
            return "MacOSX"
        elif xbmc.getCondVisibility('system.platform.atv2'):
            return "AppleTV2"
        elif xbmc.getCondVisibility('system.platform.ios'):
            return "iOS"
        elif xbmc.getCondVisibility('system.platform.windows'):
            return "Windows"
        elif xbmc.getCondVisibility('system.platform.raspberrypi'):
            return "RaspberryPi"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux"
        elif xbmc.getCondVisibility('system.platform.android'):
            return "Android"
        else:
            return "Unknown"

    def getDeviceId(self, reset=False):
        """
        Returns a unique Plex client id "X-Plex-Client-Identifier" from Kodi
        settings file.
        Also loads Kodi window property 'plex_client_Id'

        If id does not exist, create one and save in Kodi settings file.
        """
        if reset is True:
            window('plex_client_Id', clear=True)
            settings('plex_client_Id', value="")

        clientId = window('plex_client_Id')
        if clientId:
            return clientId

        clientId = settings('plex_client_Id')
        # Because Kodi appears to cache file settings!!
        if clientId != "" and reset is False:
            window('plex_client_Id', value=clientId)
            self.logMsg("Unique device Id plex_client_Id loaded: %s"
                        % clientId, 1)
            return clientId

        self.logMsg("Generating a new deviceid.", 0)
        clientId = str(uuid4())
        settings('plex_client_Id', value=clientId)
        window('plex_client_Id', value=clientId)
        self.logMsg("Unique device Id plex_client_Id loaded: %s" % clientId, 1)
        return clientId

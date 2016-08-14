# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
from uuid import uuid4

import xbmc
import xbmcaddon
import xbmcvfs

from utils import window, settings

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class ClientInfo():


    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.addonName = self.getAddonName()


    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name').upper()

    def getAddonId(self):

        return "plugin.video.emby"

    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        if settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel('System.FriendlyName').decode('utf-8')
        else:
            deviceName = settings('deviceName')
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
        elif xbmc.getCondVisibility('system.platform.android'): 
            return "Linux/Android"
        elif xbmc.getCondVisibility('system.platform.linux.raspberrypi'):
            return "Linux/RPi"            
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux"
        else:
            return "Unknown"

    def getDeviceId(self, reset=False):

        EMBY_id = xbmc.translatePath("special://temp/emby.id").decode('utf-8')
        
        #######################################
        ## machine_guid -> emby.id migration ##
        #######################################
        addon_path = self.addon.getAddonInfo('path').decode('utf-8')
        if os.path.supports_unicode_filenames:
            path = os.path.join(addon_path, "machine_guid")
        else:
            path = os.path.join(addon_path.encode('utf-8'), "machine_guid")
        
        GUID_file = xbmc.translatePath(path).decode('utf-8')

        if xbmcvfs.exists(GUID_file):
            xbmcvfs.copy(GUID_file, EMBY_id)
            xbmcvfs.delete(GUID_file)
            xbmcvfs.close(GUID_file)
        #######################################
        ##           end migration           ##
        #######################################
        
        clientId = window('emby_deviceId')
        if clientId:
            return clientId
        
        if reset and xbmcvfs.exists(EMBY_id):
            # Reset the file
            xbmcvfs.delete(EMBY_id)

        GUID = xbmcvfs.File(EMBY_id)
        clientId = GUID.read()
        if not clientId:
            log.info("Generating a new deviceid...")
            clientId = str("%012X" % uuid4())
            GUID = xbmcvfs.File(EMBY_id, 'w')
            GUID.write(clientId)

        GUID.close()

        log.info("DeviceId loaded: %s" % clientId)
        window('emby_deviceId', value=clientId)
        
        return clientId

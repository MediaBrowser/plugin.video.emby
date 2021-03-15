# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon

class LOG():
    def __init__(self, Prefix):
        self.Prefix = Prefix
        self.KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

        try:
            self.log_level = int(xbmcaddon.Addon("plugin.video.emby-next-gen").getSetting('logLevel'))
        except ValueError:
            self.log_level = 1



    def debug(self, msg):
        if self.log_level != 2: #Debug
            return

        msg = "DEBUG: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGDEBUG)
        else:
            xbmc.log(msg.encode('utf-8'), xbmc.LOGDEBUG)

    def info(self, msg):
        if self.log_level == 0: #Disabled
            return

        msg = "INFO: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGINFO)
        else:
            xbmc.log(msg.encode('utf-8'), xbmc.LOGNOTICE)

    def warning(self, msg):
        if self.log_level == 0: #Disabled
            return

        msg = "WARNING: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGWARNING)
        else:
            xbmc.log(msg.encode('utf-8'), xbmc.LOGWARNING)

    def error(self, msg):
        if self.log_level == 0: #Disabled
            return

        msg = "ERROR: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGERROR)
        else:
            xbmc.log(msg.encode('utf-8'), xbmc.LOGERROR)

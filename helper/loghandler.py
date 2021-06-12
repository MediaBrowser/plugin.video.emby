# -*- coding: utf-8 -*-
import xbmc

class LOG():
    def __init__(self, Prefix):
        self.Prefix = Prefix
        self.KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

    def debug(self, msg):
        msg = "DEBUG: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGDEBUG)
        else:
            xbmc.log(self.Encode(msg), xbmc.LOGDEBUG)

    def info(self, msg):
        msg = "INFO: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGINFO)
        else:
            xbmc.log(self.Encode(msg), xbmc.LOGNOTICE)

    def warning(self, msg):
        msg = "WARNING: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGWARNING)
        else:
            xbmc.log(self.Encode(msg), xbmc.LOGWARNING)

    def error(self, msg):
        msg = "ERROR: %s: %s" % (self.Prefix, msg)

        if self.KodiVersion >= 19:
            xbmc.log(msg, xbmc.LOGERROR)
        else:
            xbmc.log(self.Encode(msg), xbmc.LOGERROR)

    def Encode(self, Data):
        try:
            Data = unicode(Data, 'utf-8')
        except:
            pass

        return Data.encode('utf-8')

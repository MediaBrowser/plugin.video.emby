# -*- coding: utf-8 -*-
import xbmc

Python3 = bool(int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19)


class LOG:
    def __init__(self, Prefix):
        self.Prefix = Prefix

    def debug(self, msg):
        msg = "DEBUG: %s: %s" % (self.Prefix, msg)

        if Python3:
            xbmc.log(msg, xbmc.LOGDEBUG)
        else:
            xbmc.log(Encode(msg), xbmc.LOGDEBUG)

    def info(self, msg):
        msg = "INFO: %s: %s" % (self.Prefix, msg)

        if Python3:
            xbmc.log(msg, xbmc.LOGINFO)
        else:
            xbmc.log(Encode(msg), xbmc.LOGNOTICE)

    def warning(self, msg):
        msg = "WARNING: %s: %s" % (self.Prefix, msg)

        if Python3:
            xbmc.log(msg, xbmc.LOGWARNING)
        else:
            xbmc.log(Encode(msg), xbmc.LOGWARNING)

    def error(self, msg):
        msg = "ERROR: %s: %s" % (self.Prefix, msg)

        if Python3:
            xbmc.log(msg, xbmc.LOGERROR)
        else:
            xbmc.log(Encode(msg), xbmc.LOGERROR)

def Encode(Data):
    try:
        if not Python3:
            Data = unicode(Data, 'utf-8')
    except:
        pass

    try:
        return Data.encode('utf-8')
    except:
        return "unicode issue, log not possible"

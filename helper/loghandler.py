import xbmc

#from . import utils

class LOG:
    def __init__(self, Prefix):
        self.Prefix = Prefix

    def debug(self, msg):
#        for EmbyServer in utils.EmbyServers.values():
#            msg = msg.replace(EmbyServer.Token, "MASKED_API_KEY")

        msg = "%s: %s" % (self.Prefix, msg)
        xbmc.log(msg, xbmc.LOGDEBUG)

    def info(self, msg):
        msg = "%s: %s" % (self.Prefix, msg)
        xbmc.log(msg, xbmc.LOGINFO)

    def warning(self, msg):
        msg = "%s: %s" % (self.Prefix, msg)
        xbmc.log(msg, xbmc.LOGWARNING)

    def error(self, msg):
        msg = "%s: %s" % (self.Prefix, msg)
        xbmc.log(msg, xbmc.LOGERROR)

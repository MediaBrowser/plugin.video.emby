# -*- coding: utf-8 -*-
###############################################################################
import logging
import xbmc

from utils import tryEncode
###############################################################################
LEVELS = {
    logging.ERROR: xbmc.LOGERROR,
    logging.WARNING: xbmc.LOGWARNING,
    logging.INFO: xbmc.LOGNOTICE,
    logging.DEBUG: xbmc.LOGDEBUG
}
###############################################################################


def config():
    logger = logging.getLogger('PLEX')
    logger.addHandler(LogHandler())
    logger.setLevel(logging.DEBUG)


class LogHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)
        self.setFormatter(logging.Formatter(fmt="%(name)s: %(message)s"))

    def emit(self, record):
        try:
            xbmc.log(self.format(record), level=LEVELS[record.levelno])
        except UnicodeEncodeError:
            xbmc.log(tryEncode(self.format(record)),
                     level=LEVELS[record.levelno])

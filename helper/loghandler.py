# -*- coding: utf-8 -*-
import logging
import xbmc

import database.database
from . import utils

def config():
    logger = logging.getLogger('EMBY')
    logger.addHandler(LogHandler())
    logger.setLevel(logging.DEBUG)

def reset():
    for handler in logging.getLogger('EMBY').handlers:
        logging.getLogger('EMBY').removeHandler(handler)

class LogHandler(logging.StreamHandler):
    def __init__(self):
        self.Utils = utils.Utils()
        self.KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        logging.StreamHandler.__init__(self)
        self.setFormatter(MyFormatter())
        self.sensitive = {'Token': [], 'Server': []}

        for server in database.database.get_credentials()['Servers']:
            if server.get('AccessToken'):
                self.sensitive['Token'].append(server['AccessToken'])

            if server.get('LocalAddress'):
                self.sensitive['Server'].append(server['LocalAddress'].split('://')[1])

            if server.get('RemoteAddress'):
                self.sensitive['Server'].append(server['RemoteAddress'].split('://')[1])

            if server.get('ManualAddress'):
                self.sensitive['Server'].append(server['ManualAddress'].split('://')[1])

        self.mask_info = self.Utils.settings('maskInfo.bool')

        if self.KodiVersion >= 19:
            self.LogFlag = xbmc.LOGINFO
        else:
            self.LogFlag = xbmc.LOGNOTICE

    def emit(self, record):
        if self._get_log_level(record.levelno, self.Utils):
            try:
                string = self.format(record)
            except:
                xbmc.log("Error trying to format string for log", level=xbmc.LOGWARNING)
                return

            if self.mask_info:
                for server in self.sensitive['Server']:
                    if self.KodiVersion >= 19:
                        string = string.replace(server or "{server}", "{emby-server}")
                    else:
                        string = string.replace(server.encode('utf-8') or "{server}", "{emby-server}")

                for token in self.sensitive['Token']:
                    if self.KodiVersion >= 19:
                        string = string.replace(token  or "{token}", "{emby-token}")
                    else:
                        string = string.replace(token.encode('utf-8')  or "{token}", "{emby-token}")

            try:
                xbmc.log(string, level=self.LogFlag)
            except UnicodeEncodeError:
                xbmc.log(string.encode('utf-8'), level=self.LogFlag)

    @classmethod
    def _get_log_level(cls, level, Utils):
        levels = {
            logging.ERROR: 0,
            logging.WARNING: 0,
            logging.INFO: 1,
            logging.DEBUG: 2
        }

        log_level = 1

        try:
            log_level = int(Utils.settings('logLevel'))
        except ValueError:
            log_level = 1

        return log_level >= levels[level]

class MyFormatter(logging.Formatter):
    def __init__(self, fmt="%(name)s -> %(message)s"):
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._fmt

        # Replace the original format with one customized by logging level
        if record.levelno in (logging.DEBUG, logging.ERROR):
            self._fmt = '%(name)s -> %(levelname)s:: %(message)s'

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._fmt = format_orig

        return result

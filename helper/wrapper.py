# -*- coding: utf-8 -*-
import logging

import xbmcgui
import xbmc

from . import translate
from . import exceptions
from . import utils

Utils = utils.Utils()
LOG = logging.getLogger("EMBY.helper.wrapper")

#Will start and close the progress dialog.
def progress(message=None):
    def decorator(func):
        def wrapper(self, item=None, *args, **kwargs):
            dialog = xbmcgui.DialogProgressBG()

            if item and isinstance(item, dict):
                dialog.create(translate._('addon_name'), "%s %s" % (translate._('gathering'), item['Name']))
                LOG.info("Processing %s: %s", item['Name'], item['Id'])
            else:
                dialog.create(translate._('addon_name'), message)
                LOG.info("Processing %s", message)

            if item:
                args = (item,) + args

            try:
                result = func(self, dialog=dialog, *args, **kwargs)
                dialog.close()
            except Exception:
                dialog.close()
                raise

            return result

        return wrapper
    return decorator

#Wrapper to catch exceptions and return using catch
def stop(func):
    def wrapper(*args, **kwargs):
        if xbmc.Monitor().waitForAbort(0.00001) or Utils.window('emby_should_stop.bool') or not Utils.window('emby_online.bool'):
            raise exceptions.LibraryException('StopCalled')

        if Utils.window('emby.sync.pause.bool'):
            LOG.info("Stopping db writing!")
            raise exceptions.LibraryException('StopWriteCalled')

        return func(*args, **kwargs)
    return wrapper

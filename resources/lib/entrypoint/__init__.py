# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys

import xbmc
import xbmcvfs

from helper import loghandler

#################################################################################################

loghandler.reset()
loghandler.config()
LOG = logging.getLogger('EMBY.entrypoint')

#################################################################################################

if 'service' in sys.argv:
	from emby import Emby

	Emby.set_loghandler(loghandler.LogHandler, logging.DEBUG)

	from service import Service

from context import Context
from default import Events

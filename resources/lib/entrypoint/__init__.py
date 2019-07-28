# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys

import xbmc
import xbmcvfs

from emby import Emby
from helper import loghandler, window

#################################################################################################

loghandler.reset()
loghandler.config()
LOG = logging.getLogger('EMBY.entrypoint')
Emby.set_loghandler(loghandler.LogHandler, logging.DEBUG)

#################################################################################################

if 'service' in sys.argv:
	from service import Service
else:
	Emby().set_state(window('emby.server.state.json'))

	for server in window('emby.server.states.json') or []:
		Emby(server).set_state(window('emby.server.%s.state.json' % server))

from context import Context
from default import Events

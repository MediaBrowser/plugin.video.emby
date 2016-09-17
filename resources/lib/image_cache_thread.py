# -*- coding: utf-8 -*-

###############################################################################
import logging
import threading
import requests

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class ImageCacheThread(threading.Thread):
    def __init__(self, xbmc_username, xbmc_password, url):
        self.xbmc_username = xbmc_username
        self.xbmc_password = xbmc_password
        self.url = url
        threading.Thread.__init__(self)

    def run(self):
        try:
            requests.head(
                url=self.url,
                auth=(self.xbmc_username, self.xbmc_password),
                timeout=(0.01, 0.01))
        except requests.Timeout:
            # We don't need the result, only trigger Kodi to start download
            pass
        except Exception as e:
            log.error('Encountered exception: %s' % e)
            import traceback
            log.error("Traceback:\n%s" % traceback.format_exc())

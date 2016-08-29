# -*- coding: utf-8 -*-

#################################################################################################

import logging
import threading
import requests

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()
#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


@utils.logging
class ImageCacheThread(threading.Thread):

    url_to_process = None
    is_finished = False

    xbmc_host = ""
    xbmc_port = ""
    xbmc_username = ""
    xbmc_password = ""


    def __init__(self):

        threading.Thread.__init__(self)


    def set_url(self, url):

        self.url_to_process = url

    def set_host(self, host, port):

        self.xbmc_host = host
        self.xbmc_port = port

    def set_auth(self, username, password):

        self.xbmc_username = username
        self.xbmc_password = password

    def run(self):

        log.debug("Image Caching Thread Processing: %s", self.url_to_process)

        try:
            response = requests.head(
                                url=(
                                    "http://%s:%s/image/image://%s"
                                    % (self.xbmc_host, self.xbmc_port, self.urlToProcess)),
                                auth=(self.xbmc_username, self.xbmc_password),
                                timeout=(5, 5))
        # We don't need the result
        except Exception:
            pass

        log.debug("Image Caching Thread Exited")
        self.is_finished = True

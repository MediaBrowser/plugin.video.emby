# -*- coding: utf-8 -*-
import threading
import traceback
import socket

import xbmc

import utils
from plexbmchelper import listener, plexgdm, subscribers, functions, \
    httppersist, settings


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('plex_serverStatus')
@utils.ThreadMethods
class PlexCompanion(threading.Thread):
    def __init__(self):
        self.logMsg("----===## Starting PlexCompanion ##===----", 1)
        self.settings = settings.getSettings()

        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm()
        self.client.clientDetails(self.settings)
        self.logMsg("Registration string is: %s "
                    % self.client.getClientDetails(), 2)

        threading.Thread.__init__(self)

    def run(self):
        httpd = False
        # Cache for quicker while loops
        log = self.logMsg
        client = self.client
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended

        # Start up instances
        requestMgr = httppersist.RequestMgr()
        jsonClass = functions.jsonClass(requestMgr, self.settings)
        subscriptionManager = subscribers.SubscriptionManager(
            jsonClass, requestMgr)

        if utils.settings('plexCompanion') == 'true':
            self.logMsg('User activated Plex Companion', 0)
            # Start up httpd
            start_count = 0
            while True:
                try:
                    httpd = listener.ThreadedHTTPServer(
                        client,
                        subscriptionManager,
                        jsonClass,
                        self.settings,
                        ('', self.settings['myport']),
                        listener.MyHandler)
                    httpd.timeout = 0.95
                    break
                except:
                    log("Unable to start PlexCompanion. Traceback:", -1)
                    log(traceback.print_exc(), -1)

                xbmc.sleep(3000)

                if start_count == 3:
                    log("Error: Unable to start web helper.", -1)
                    httpd = False
                    break

                start_count += 1
        else:
            self.logMsg('User deactivated Plex Companion', 0)

        client.start_all()

        message_count = 0
        while not threadStopped():
            # If we are not authorized, sleep
            # Otherwise, we trigger a download which leads to a
            # re-authorizations
            while threadSuspended():
                if threadStopped():
                    break
                xbmc.sleep(1000)
            try:
                if httpd:
                    httpd.handle_request()
                    message_count += 1

                    if message_count > 100:
                        if client.check_client_registration():
                            log("Client is still registered", 1)
                        else:
                            log("Client is no longer registered", 1)
                            log("Plex Companion still running on port %s"
                                % self.settings['myport'], 1)
                        message_count = 0

                # Get and set servers
                subscriptionManager.serverlist = client.getServerList()

                subscriptionManager.notify()
                xbmc.sleep(50)
            except:
                log("Error in loop, continuing anyway. Traceback:", 1)
                log(traceback.format_exc(), 1)
                xbmc.sleep(50)

        client.stop_all()
        if httpd:
            try:
                httpd.socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            finally:
                httpd.socket.close()
        log("----===## Plex Companion stopped ##===----", 0)

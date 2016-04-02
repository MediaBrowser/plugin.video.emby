# -*- coding: utf-8 -*-
import threading
import traceback
import socket

import xbmc

import clientinfo
import utils
from plexbmchelper import listener, plexgdm, subscribers, functions, \
    httppersist


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('emby_serverStatus')
@utils.ThreadMethods
class PlexCompanion(threading.Thread):
    def __init__(self):
        ci = clientinfo.ClientInfo()
        self.clientId = ci.getDeviceId()
        self.deviceName = ci.getDeviceName()

        self.port = int(utils.settings('companionPort'))
        self.logMsg("----===## Starting PlexCompanion ##===----", 1)

        # Start GDM for server/client discovery
        self.client = plexgdm.plexgdm(
            debug=utils.settings('companionGDMDebugging'))
        self.client.clientDetails(self.clientId,      # UUID
                                  self.deviceName,    # clientName
                                  self.port,
                                  self.addonName,
                                  '1.0')    # Version
        self.logMsg("Registration string is: %s "
                    % self.client.getClientDetails(), 1)

        threading.Thread.__init__(self)

    def run(self):
        # Cache for quicker while loops
        log = self.logMsg
        client = self.client
        threadStopped = self.threadStopped
        threadSuspended = self.threadSuspended
        start_count = 0

        # Start up instances
        requestMgr = httppersist.RequestMgr()
        jsonClass = functions.jsonClass(requestMgr)
        subscriptionManager = subscribers.SubscriptionManager(
            jsonClass, requestMgr)

        # Start up httpd
        while True:
            try:
                httpd = listener.ThreadedHTTPServer(
                    client,
                    subscriptionManager,
                    jsonClass,
                    ('', self.port),
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

        if not httpd:
            return

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

                httpd.handle_request()
                message_count += 1

                if message_count > 100:
                    if client.check_client_registration():
                        log("Client is still registered", 1)
                    else:
                        log("Client is no longer registered", 1)
                        log("Plex Companion still running on port %s"
                            % self.port, 1)
                    message_count = 0

                # Get and set servers
                subscriptionManager.serverlist = client.getServerList()

                subscriptionManager.notify()
                xbmc.sleep(50)
            except:
                log("Error in loop, continuing anyway", 1)
                log(traceback.format_exc(), 1)
                xbmc.sleep(50)

        client.stop_all()
        try:
            httpd.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        finally:
            httpd.socket.close()
        log("----===## Plex Companion stopped ##===----", 0)

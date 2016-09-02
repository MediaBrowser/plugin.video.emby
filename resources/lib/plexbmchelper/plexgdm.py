"""
PlexGDM.py - Version 0.2

This class implements the Plex GDM (G'Day Mate) protocol to discover
local Plex Media Servers.  Also allow client registration into all local
media servers.


This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
MA 02110-1301, USA.
"""
import logging
import socket
import threading
import time

from xbmc import sleep

import downloadutils
from utils import window, settings

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class plexgdm:

    def __init__(self):
        self.discover_message = 'M-SEARCH * HTTP/1.0'
        self.client_header = '* HTTP/1.0'
        self.client_data = None
        self.client_id = None

        self._multicast_address = '239.0.0.250'
        self.discover_group = (self._multicast_address, 32414)
        self.client_register_group = (self._multicast_address, 32413)
        self.client_update_port = 32412

        self.server_list = []
        self.discovery_interval = 120

        self._discovery_is_running = False
        self._registration_is_running = False

        self.discovery_complete = False
        self.client_registered = False
        self.download = downloadutils.DownloadUtils().downloadUrl

    def clientDetails(self, options):
        self.client_data = (
            "Content-Type: plex/media-player\r\n"
            "Resource-Identifier: %s\r\n"
            "Name: %s\r\n"
            "Port: %s\r\n"
            "Product: %s\r\n"
            "Version: %s\r\n"
            "Protocol: plex\r\n"
            "Protocol-Version: 1\r\n"
            "Protocol-Capabilities: timeline,playback,navigation,"
            "mirror,playqueues\r\n"
            "Device-Class: HTPC"
        ) % (
            options['uuid'],
            options['client_name'],
            options['myport'],
            options['addonName'],
            options['version']
        )
        self.client_id = options['uuid']

    def getClientDetails(self):
        return self.client_data

    def client_update(self):
        update_sock = socket.socket(socket.AF_INET,
                                    socket.SOCK_DGRAM,
                                    socket.IPPROTO_UDP)

        # Set socket reuse, may not work on all OSs.
        try:
            update_sock.setsockopt(socket.SOL_SOCKET,
                                   socket.SO_REUSEADDR,
                                   1)
        except:
            pass

        # Attempt to bind to the socket to recieve and send data.  If we cant
        # do this, then we cannot send registration
        try:
            update_sock.bind(('0.0.0.0', self.client_update_port))
        except:
            log.error("Unable to bind to port [%s] - client will not be "
                      "registered" % self.client_update_port)
            return

        update_sock.setsockopt(socket.IPPROTO_IP,
                               socket.IP_MULTICAST_TTL,
                               255)
        update_sock.setsockopt(socket.IPPROTO_IP,
                               socket.IP_ADD_MEMBERSHIP,
                               socket.inet_aton(
                                   self._multicast_address) +
                               socket.inet_aton('0.0.0.0'))
        update_sock.setblocking(0)
        log.debug("Sending registration data: HELLO %s\r\n%s"
                  % (self.client_header, self.client_data))

        # Send initial client registration
        try:
            update_sock.sendto("HELLO %s\r\n%s"
                               % (self.client_header, self.client_data),
                               self.client_register_group)
        except:
            log.error("Unable to send registration message")

        # Now, listen format client discovery reguests and respond.
        while self._registration_is_running:
            try:
                data, addr = update_sock.recvfrom(1024)
                log.debug("Recieved UDP packet from [%s] containing [%s]"
                          % (addr, data.strip()))
            except socket.error:
                pass
            else:
                if "M-SEARCH * HTTP/1." in data:
                    log.debug("Detected client discovery request from %s. "
                              " Replying" % str(addr))
                    try:
                        update_sock.sendto("HTTP/1.0 200 OK\r\n%s"
                                           % self.client_data,
                                           addr)
                    except:
                        log.error("Unable to send client update message")

                    log.debug("Sending registration data HTTP/1.0 200 OK")
                    self.client_registered = True
            sleep(500)
        log.info("Client Update loop stopped")
        # When we are finished, then send a final goodbye message to
        # deregister cleanly.
        log.debug("Sending registration data: BYE %s\r\n%s"
                  % (self.client_header, self.client_data))
        try:
            update_sock.sendto("BYE %s\r\n%s"
                               % (self.client_header, self.client_data),
                               self.client_register_group)
        except:
            log.error("Unable to send client update message")
        self.client_registered = False

    def check_client_registration(self):

        if self.client_registered and self.discovery_complete:
            if not self.server_list:
                log.info("Server list is empty. Unable to check")
                return False
            try:
                for server in self.server_list:
                    if server['uuid'] == window('plex_machineIdentifier'):
                        media_server = server['server']
                        media_port = server['port']
                        scheme = server['protocol']
                        break
                else:
                    log.info("Did not find our server!")
                    return False

                log.debug("Checking server [%s] on port [%s]"
                          % (media_server, media_port))
                client_result = self.download(
                    '%s://%s:%s/clients' % (scheme, media_server, media_port))
                registered = False
                for client in client_result:
                    if (client.attrib.get('machineIdentifier') ==
                            self.client_id):
                        registered = True
                if registered:
                    log.debug("Client registration successful. "
                              "Client data is: %s" % client_result)
                    return True
                else:
                    log.info("Client registration not found. "
                             "Client data is: %s" % client_result)
            except:
                log.error("Unable to check status")
                pass
        return False

    def getServerList(self):
        return self.server_list

    def discover(self):
        currServer = window('pms_server')
        if not currServer:
            return
        currServerProt, currServerIP, currServerPort = \
            currServer.split(':')
        currServerIP = currServerIP.replace('/', '')
        # Currently active server was not discovered via GDM; ADD
        self.server_list = [{
            'port': currServerPort,
            'protocol': currServerProt,
            'class': None,
            'content-type': 'plex/media-server',
            'discovery': 'auto',
            'master': 1,
            'owned': '1',
            'role': 'master',
            'server': currServerIP,
            'serverName': window('plex_servername'),
            'updated': int(time.time()),
            'uuid': window('plex_machineIdentifier'),
            'version': 'irrelevant'
        }]

    def setInterval(self, interval):
        self.discovery_interval = interval

    def stop_all(self):
        self.stop_discovery()
        self.stop_registration()

    def stop_discovery(self):
        if self._discovery_is_running:
            log.info("Discovery shutting down")
            self._discovery_is_running = False
            self.discover_t.join()
            del self.discover_t
        else:
            log.info("Discovery not running")

    def stop_registration(self):
        if self._registration_is_running:
            log.info("Registration shutting down")
            self._registration_is_running = False
            self.register_t.join()
            del self.register_t
        else:
            log.info("Registration not running")

    def run_discovery_loop(self):
        # Run initial discovery
        self.discover()

        discovery_count = 0
        while self._discovery_is_running:
            discovery_count += 1
            if discovery_count > self.discovery_interval:
                self.discover()
                discovery_count = 0
            sleep(500)

    def start_discovery(self, daemon=False):
        if not self._discovery_is_running:
            log.info("Discovery starting up")
            self._discovery_is_running = True
            self.discover_t = threading.Thread(target=self.run_discovery_loop)
            self.discover_t.setDaemon(daemon)
            self.discover_t.start()
        else:
            log.info("Discovery already running")

    def start_registration(self, daemon=False):
        if not self._registration_is_running:
            log.info("Registration starting up")
            self._registration_is_running = True
            self.register_t = threading.Thread(target=self.client_update)
            self.register_t.setDaemon(daemon)
            self.register_t.start()
        else:
            log.info("Registration already running")

    def start_all(self, daemon=False):
        self.start_discovery(daemon)
        if settings('plexCompanion') == 'true':
            self.start_registration(daemon)

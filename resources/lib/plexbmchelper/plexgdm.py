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

__author__ = 'DHJ (hippojay) <plex@h-jay.com>'

import socket
import struct
import threading
import time

from xbmc import sleep

import downloadutils
from PlexFunctions import PMSHttpsEnabled
from utils import window, logging, settings


@logging
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
        if not self.client_data:
            self.logMsg("Client data has not been initialised.  Please use "
                        "PlexGDM.clientDetails()", -1)

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
            self.logMsg("Unable to bind to port [%s] - client will not be "
                        "registered" % self.client_update_port, -1)
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
        self.logMsg("Sending registration data: HELLO %s\r\n%s"
                    % (self.client_header, self.client_data), 2)

        # Send initial client registration
        try:
            update_sock.sendto("HELLO %s\r\n%s"
                               % (self.client_header, self.client_data),
                               self.client_register_group)
        except:
            self.logMsg("Unable to send registration message", -1)

        # Now, listen for client discovery reguests and respond.
        while self._registration_is_running:
            try:
                data, addr = update_sock.recvfrom(1024)
                self.logMsg("Recieved UDP packet from [%s] containing [%s]"
                            % (addr, data.strip()), 2)
            except socket.error:
                pass
            else:
                if "M-SEARCH * HTTP/1." in data:
                    self.logMsg("Detected client discovery request from %s. "
                                " Replying" % str(addr), 2)
                    try:
                        update_sock.sendto("HTTP/1.0 200 OK\r\n%s"
                                           % self.client_data,
                                           addr)
                    except:
                        self.logMsg("Unable to send client update message", -1)

                    self.logMsg("Sending registration data HTTP/1.0 200 OK", 2)
                    self.client_registered = True
            sleep(500)

        self.logMsg("Client Update loop stopped", 1)

        # When we are finished, then send a final goodbye message to
        # deregister cleanly.
        self.logMsg("Sending registration data: BYE %s\r\n%s"
                    % (self.client_header, self.client_data), 2)
        try:
            update_sock.sendto("BYE %s\r\n%s"
                               % (self.client_header, self.client_data),
                               self.client_register_group)
        except:
            self.logMsg("Unable to send client update message", -1)

        self.client_registered = False

    def check_client_registration(self):

        if self.client_registered and self.discovery_complete:

            if not self.server_list:
                self.logMsg("Server list is empty. Unable to check", 1)
                return False

            try:
                for server in self.server_list:
                    if server['uuid'] == window('plex_machineIdentifier'):
                        media_server = server['server']
                        media_port = server['port']
                        scheme = server['protocol']
                        break
                else:
                    self.logMsg("Did not find our server!", 0)
                    return False

                self.logMsg("Checking server [%s] on port [%s]"
                            % (media_server, media_port), 2)
                client_result = self.download(
                    '%s://%s:%s/clients' % (scheme, media_server, media_port))
                registered = False
                for client in client_result:
                    if (client.attrib.get('machineIdentifier') ==
                            self.client_id):
                        registered = True
                if registered:
                    self.logMsg("Client registration successful", 1)
                    self.logMsg("Client data is: %s" % client_result, 2)
                    return True
                else:
                    self.logMsg("Client registration not found", 1)
                    self.logMsg("Client data is: %s" % client_result, 1)

            except:
                self.logMsg("Unable to check status", 0)
                pass

        return False

    def getServerList(self):
        return self.server_list

    def discover(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set a timeout so the socket does not block indefinitely
        sock.settimeout(0.6)

        # Set the time-to-live for messages to 1 for local network
        ttl = struct.pack('b', 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

        returnData = []
        try:
            # Send data to the multicast group
            self.logMsg("Sending discovery messages: %s"
                        % self.discover_message, 2)
            sock.sendto(self.discover_message, self.discover_group)

            # Look for responses from all recipients
            while True:
                try:
                    data, server = sock.recvfrom(1024)
                    self.logMsg("Received data from %s, %s" % server, 2)
                    returnData.append({'from': server,
                                       'data': data})
                except socket.timeout:
                    break
        except:
            # if we can't send our discovery query, just abort and try again
            # on the next loop
            return
        finally:
            sock.close()

        self.discovery_complete = True

        discovered_servers = []

        if returnData:

            for response in returnData:
                update = {'server': response.get('from')[0]}

                # Check if we had a positive HTTP reponse
                if "200 OK" in response.get('data'):
                    for each in response.get('data').split('\r\n'):
                        update['discovery'] = "auto"
                        update['owned'] = '1'
                        update['master'] = 1
                        update['role'] = 'master'
                        update['class'] = None
                        if "Content-Type:" in each:
                            update['content-type'] = each.split(':')[1].strip()
                        elif "Resource-Identifier:" in each:
                            update['uuid'] = each.split(':')[1].strip()
                        elif "Name:" in each:
                            update['serverName'] = each.split(':')[1].strip()
                        elif "Port:" in each:
                            update['port'] = each.split(':')[1].strip()
                        elif "Updated-At:" in each:
                            update['updated'] = each.split(':')[1].strip()
                        elif "Version:" in each:
                            update['version'] = each.split(':')[1].strip()
                        elif "Server-Class:" in each:
                            update['class'] = each.split(':')[1].strip()

                # Quickly test if we need https
                https = PMSHttpsEnabled(
                    '%s:%s' % (update['server'], update['port']))
                if https is None:
                    # Error contacting server
                    continue
                elif https:
                    update['protocol'] = 'https'
                else:
                    update['protocol'] = 'http'
                discovered_servers.append(update)

        # Append REMOTE PMS that we haven't found yet; if necessary
        currServer = window('pms_server')
        if currServer:
            currServerProt, currServerIP, currServerPort = \
                currServer.split(':')
            currServerIP = currServerIP.replace('/', '')
            for server in discovered_servers:
                if server['server'] == currServerIP:
                    break
            else:
                # Currently active server was not discovered via GDM; ADD
                update = {
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
                }
                discovered_servers.append(update)

        self.server_list = discovered_servers

        if not self.server_list:
            self.logMsg("No servers have been discovered", 0)
        else:
            self.logMsg("Number of servers Discovered: %s"
                        % len(self.server_list), 2)
            for items in self.server_list:
                self.logMsg("Server Discovered: %s" % items, 2)

    def setInterval(self, interval):
        self.discovery_interval = interval

    def stop_all(self):
        self.stop_discovery()
        self.stop_registration()

    def stop_discovery(self):
        if self._discovery_is_running:
            self.logMsg("Discovery shutting down", 0)
            self._discovery_is_running = False
            self.discover_t.join()
            del self.discover_t
        else:
            self.logMsg("Discovery not running", 0)

    def stop_registration(self):
        if self._registration_is_running:
            self.logMsg("Registration shutting down", 0)
            self._registration_is_running = False
            self.register_t.join()
            del self.register_t
        else:
            self.logMsg("Registration not running", 0)

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
            self.logMsg("Discovery starting up", 0)
            self._discovery_is_running = True
            self.discover_t = threading.Thread(target=self.run_discovery_loop)
            self.discover_t.setDaemon(daemon)
            self.discover_t.start()
        else:
            self.logMsg("Discovery already running", 0)

    def start_registration(self, daemon=False):
        if not self._registration_is_running:
            self.logMsg("Registration starting up", 0)
            self._registration_is_running = True
            self.register_t = threading.Thread(target=self.client_update)
            self.register_t.setDaemon(daemon)
            self.register_t.start()
        else:
            self.logMsg("Registration already running", 0)

    def start_all(self, daemon=False):
        self.start_discovery(daemon)
        if settings('plexCompanion') == 'true':
            self.start_registration(daemon)

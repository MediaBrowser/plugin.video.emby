# -*- coding: utf-8 -*-
import json
import socket
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

import helper.loghandler
import emby.core.credentials
import emby.core.http

class ConnectionManager():
    def __init__(self, EmbyServer):
        self.LOG = helper.loghandler.LOG('EMBY.core.connection_manager')
        self.LOG.debug("ConnectionManager initializing...")
        self.LOG.info("Begin connectToServer")
        self.user = {}
        self.EmbyServer = EmbyServer
        self.credentials = emby.core.credentials.Credentials()
        self.http = emby.core.http.HTTP(self.EmbyServer)

    def get_server_address(self, server, mode):
        modes = {0: server.get('LocalAddress'), 1: server.get('RemoteAddress'), 2: server.get('ManualAddress')} #Local...Remote...Manual
        return modes.get(mode) or server.get('ManualAddress', server.get('LocalAddress', server.get('RemoteAddress')))

    def get_serveraddress(self):
        server = self.get_server_info()
        return self.get_server_address(server, server['LastConnectionMode'])

    def clear_data(self):
        self.LOG.info("connection manager clearing data")
        self.user = None
        credentials = self.credentials.get_credentials()
        credentials['ConnectAccessToken'] = None
        credentials['ConnectUserId'] = None
        credentials['Servers'] = list()
        self.credentials.get_credentials(credentials)
        self.EmbyServer.Data['auth.server'] = None
        self.EmbyServer.Data['auth.user_id'] = None
        self.EmbyServer.Data['auth.token'] = None
        self.EmbyServer.Data['auth.ssl'] = None

    def revoke_token(self):
        self.LOG.info("revoking token")
        self.get_server_info()['AccessToken'] = None
        self.credentials.get_credentials(self.credentials.get_credentials())
        self.EmbyServer.Data['auth.token'] = None

    def get_available_servers(self):
        self.LOG.debug("Begin getAvailableServers")

        # Clone the credentials
        credentials = self.credentials.get_credentials()
        connect_servers = self._get_connect_servers(credentials)
        found_servers = self._find_servers(self._server_discovery())

        if not connect_servers and not found_servers and not credentials['Servers']: # back out right away, no point in continuing
            self.LOG.info("Found no servers")
            return list()

        servers = list(credentials['Servers'])
        self._merge_servers(servers, found_servers)
        self._merge_servers(servers, connect_servers)
        servers = self._filter_servers(servers, connect_servers)

#        try:
#        servers.sort(key=lambda x: datetime.datetime.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
#        except TypeError:
#            servers.sort(key=lambda x: datetime.datetime(*(time.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ")[0:6])), reverse=True)

        credentials['Servers'] = servers
        self.credentials.get_credentials(credentials)
        return servers

    def login_to_connect(self, username, password):
        if not username:
            return False #"username cannot be empty"

        if not password:
            return False #"password cannot be empty"

        result = self._request_url({
            'type': "POST",
            'url': self.get_connect_url("user/authenticate"),
            'data': {
                'nameOrEmail': username,
                'rawpw': password
            },
            'dataType': "json"
        }, True, False)

        if not result: #Failed to login
            return False

        credentials = self.credentials.get_credentials()
        credentials['ConnectAccessToken'] = result['AccessToken']
        credentials['ConnectUserId'] = result['User']['Id']
        credentials['ConnectUser'] = result['User']['Name']
        self.credentials.get_credentials(credentials)
        # Signed in
        self._on_connect_user_signin(result['User'])

        return result

    def login(self, server, username, password, clear, options):
        if not username:
            return False #"username cannot be empty"

        if not password:
            return False #"password cannot be empty"

        request = {
            'type': "POST",
            'url': self.get_emby_url(server, "Users/AuthenticateByName"),
            'json': {
                'username': username,
                'pw': password or "",
            }
        }

        if clear:
            request['json']['pw'] = password or ""

        result = self._request_url(request, False, True)

        if not result:
            return False

        self._on_authenticated(result, options)
        return result

    def connect_to_address(self, address, options):
        if not address:
            return False

        address = self._normalize_address(address)
        public_info = self._try_connect(address, None, options)
        self.LOG.info("connectToAddress %s succeeded" % address)
        server = {
            'ManualAddress': address,
            'LastConnectionMode': 2 #Manual
        }
        self._update_server_info(server, public_info)
        server = self.connect_to_server(server, options)

        if not server:
            return False

        return server

    def connect_to_server(self, server, options):
        self.LOG.debug("Begin connectToServer")
        tests = []

        if server.get('LastConnectionMode') != 1 and server.get('AccessToken'): #Remote
            tests.append(server['LastConnectionMode'])

        if 2 not in tests: #Manual
            tests.append(2)

        if 0 not in tests: #Local
            tests.append(0)

        if 1 not in tests: #Remote
            tests.append(1)

        return self._test_next_connection_mode(tests, 0, server, options)

    def connect(self, options):
        self.LOG.info("Begin connect")
        return self._connect_to_servers(self.get_available_servers(), options)

    def get_server_info(self):
        servers = self.credentials.get_credentials()['Servers']

        for server in servers:
            if server['Id'] == self.EmbyServer.server_id:
                return server

    def get_connect_url(self, handler):
        return "https://connect.emby.media/service/%s" % handler

    def get_emby_url(self, base, handler):
        return "%s/emby/%s" % (base, handler)

    def _request_url(self, request, headers, MSGs):
        request['timeout'] = request.get('timeout') or 10

        if headers:
            self._get_headers(request)

        return self.http.request(request, MSGs)

    def _get_headers(self, request):
        headers = request.setdefault('headers', {})

        if request.get('dataType') == "json":
            headers['Accept'] = "application/json"
            request.pop('dataType')

        headers['X-Application'] = "%s/%s" % (self.EmbyServer.Data['app.name'], self.EmbyServer.Data['app.version'])
        headers['Content-type'] = request.get('contentType', 'application/x-www-form-urlencoded; charset=UTF-8')

    def _connect_to_servers(self, servers, options):
        self.LOG.info("Begin connectToServers, with %s servers" % len(servers))
        result = {}

        if len(servers) == 1:
            result = self.connect_to_server(servers[0], options)
            self.LOG.debug("resolving connectToServers with result['State']: %s" % result)
            return result

        first_server = self._get_last_used_server()

        # See if we have any saved credentials and can auto sign in
        if first_server is not None and first_server['DateLastAccessed'] != "2001-01-01T00:00:00Z":
            result = self.connect_to_server(first_server, options)

            if not result:
                return False

            if result['State'] in (3, 0): #SignedIn or Unavailable
                return result

        # Return loaded credentials if exists
        credentials = self.credentials.get_credentials()

        self._ensure_connect_user(credentials)
        return {
            'Servers': servers,
            'State': 4 if (not len(servers) and not self.user) else (result.get('State') or 1), 'ConnectUser': self.user #ConnectSignIn...ServerSelection
        }

    def _try_connect(self, url, timeout, options, MSGs=False):
        url = self.get_emby_url(url, "system/info/public")
        self.LOG.info("tryConnect url: %s" % url)
        return self._request_url({
            'type': "GET",
            'url': url,
            'dataType': "json",
            'timeout': timeout,
            'verify': options.get('ssl'),
            'retry': False
        }, True, MSGs)

    def _test_next_connection_mode(self, tests, index, server, options):
        if index >= len(tests):
            self.LOG.info("Tested all connection modes. Failing server connection.")
            return False

        mode = tests[index]
        address = self.get_server_address(server, mode)
        skip_test = False
        self.LOG.info("testing connection mode %s with server %s" % (str(mode), server.get('Name')))

        if mode == 0: #Local
            if self._string_equals_ignore_case(address, server.get('ManualAddress')):
                self.LOG.info("skipping LocalAddress test because it is the same as ManualAddress")
                skip_test = True

        if skip_test or not address:
            self.LOG.info("skipping test at index: %s" % index)
            return self._test_next_connection_mode(tests, index + 1, server, options)

        result = self._try_connect(address, 10, options, False)

        if not result:
            return self._test_next_connection_mode(tests, index + 1, server, options)

        self.LOG.info("calling onSuccessfulConnection with connection mode %s with server %s" % (mode, server.get('Name')))
        return self._on_successful_connection(server, result, mode, options)

    def _on_successful_connection(self, server, system_info, connection_mode, options):
        credentials = self.credentials.get_credentials()

        if credentials.get('ConnectAccessToken') and options.get('enableAutoLogin') is not False:
            if self._ensure_connect_user(credentials) is not False:
                if server.get('ExchangeToken'):
                    self._add_authentication_info_from_connect(server, connection_mode, credentials, options)

        return self._after_connect_validated(server, credentials, system_info, connection_mode, True, options)

    def _string_equals_ignore_case(self, str1, str2):
        return (str1 or "").lower() == (str2 or "").lower()

    def _get_connect_user(self, user_id, access_token):
        if not user_id:
            return False #"null userId"

        if not access_token:
            return False #"null accessToken"

        return self._request_url({
            'type': "GET",
            'url': self.get_connect_url('user?id=%s' % user_id),
            'dataType': "json",
            'headers': {
                'X-Connect-UserToken': access_token
            }
        }, True, False)

    def _server_discovery(self):
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = b"who is EmbyServer?"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0) # This controls the socket.timeout exception
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        self.LOG.debug("MultiGroup      : %s" % str(MULTI_GROUP))
        self.LOG.debug("Sending UDP Data: %s" % MESSAGE)
        servers = []

        try:
            sock.sendto(MESSAGE, MULTI_GROUP)
        except Exception as error:
            self.LOG.error("ERROR: %s" % error)
            return servers

        while True:
            data = None

            try:
                data, _ = sock.recvfrom(1024) # buffer size
                servers.append(json.loads(data))
            except socket.timeout:
                self.LOG.info("Found Servers: %s" % servers)
                return servers
            except Exception as Error:
                self.LOG.error("Error trying to find servers: %s" % Error)
                return servers

    def _get_connect_servers(self, credentials):
        self.LOG.debug("Begin getConnectServers")
        servers = list()

        if not credentials.get('ConnectAccessToken') or not credentials.get('ConnectUserId'):
            return servers

        url = self.get_connect_url("servers?userId=%s" % credentials['ConnectUserId'])
        request = {
            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {
                'X-Connect-UserToken': credentials['ConnectAccessToken']
            }
        }

        result = self._request_url(request, True, False)

        if not result:
            return []


        for server in result:
            servers.append({
                'ExchangeToken': server['AccessKey'],
                'ConnectServerId': server['Id'],
                'Id': server['SystemId'],
                'Name': server['Name'],
                'RemoteAddress': server['Url'],
                'LocalAddress': server['LocalAddress'],
                'UserLinkType': "Guest" if server['UserType'].lower() == "guest" else "LinkedUser",
            })

        return servers

    def _get_last_used_server(self):
        servers = self.credentials.get_credentials()['Servers']

        if not len(servers):
            return

#        try:
#            servers.sort(key=lambda x: datetime.datetime.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
#        except TypeError:
#            servers.sort(key=lambda x: datetime.datetime(*(time.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ")[0:6])), reverse=True)

        return servers[0]

    def _merge_servers(self, list1, list2):
        for i in range(0, len(list2), 1):
            self.credentials.add_update_server(list1, list2[i])

        return list1

    def _find_servers(self, found_servers):
        servers = []

        for found_server in found_servers:
            server = self._convert_endpoint_address_to_manual_address(found_server)

            if not server and not found_server.get('Address'):
                self.LOG.warning("Server %s has no address." % found_server)
                continue

            info = {
                'Id': found_server['Id'],
                'LocalAddress': server or found_server['Address'],
                'Name': found_server['Name']
            }
            servers.append(info)

        return servers

    def _filter_servers(self, servers, connect_servers):
        filtered = list()

        for server in servers:
            if server.get('ExchangeToken') is None:
                # It's not a connect server, so assume it's still valid
                filtered.append(server)
                continue

            for connect_server in connect_servers:
                if server['Id'] == connect_server['Id']:
                    filtered.append(server)
                    break

        return filtered

    def _convert_endpoint_address_to_manual_address(self, info):
        if info.get('Address') and info.get('EndpointAddress'):
            address = info['EndpointAddress'].split(':')[0]
            # Determine the port, if any
            parts = info['Address'].split(':')

            if len(parts) > 1:
                port_string = parts[len(parts)-1]
                address += ":%s" % int(port_string)
                return self._normalize_address(address)

        return None

    def _normalize_address(self, address):
        # Attempt to correct bad input
        address = address.strip()
        address = address.lower()

        if 'http' not in address:
            address = "http://%s" % address

        return address

    def _ensure_connect_user(self, credentials):
        if self.user and self.user['Id'] == credentials['ConnectUserId']:
            return
        elif credentials.get('ConnectUserId') and credentials.get('ConnectAccessToken'):
            self.user = None
            result = self._get_connect_user(credentials['ConnectUserId'], credentials['ConnectAccessToken'])
            self._on_connect_user_signin(result)

    def _on_connect_user_signin(self, user):
        self.user = user
        self.LOG.info("connectusersignedin %s" % user)

    def _save_user_info_into_credentials(self, server, user):
        info = {
            'Id': user['Id'],
            'IsSignedInOffline': True
        }
        self.credentials.add_update_user(server, info)

    def _add_authentication_info_from_connect(self, server, connection_mode, credentials, options):
        if not server.get('ExchangeToken'):
            return False #"server['ExchangeToken'] cannot be null"

        if not credentials.get('ConnectUserId'):
            return False #"credentials['ConnectUserId'] cannot be null"

        auth = "MediaBrowser "
        auth += "Client=%s, " % self.EmbyServer.Data['app.name']
        auth += "Device=%s, " % self.EmbyServer.Data['app.device_name']
        auth += "DeviceId=%s, " % self.EmbyServer.Data['app.device_id']
        auth += "Version=%s " % self.EmbyServer.Data['app.version']
        auth = self._request_url({
            'url': self.get_emby_url(self.get_server_address(server, connection_mode), "Connect/Exchange"),
            'type': "GET",
            'dataType': "json",
            'verify': options.get('ssl'),
            'params': {
                'ConnectUserId': credentials['ConnectUserId']
            },
            'headers': {
                'X-MediaBrowser-Token': server['ExchangeToken'],
                'X-Emby-Authorization': auth
            }
        }, True, False)

        if not auth:
            server['UserId'] = None
            server['AccessToken'] = None
            return False

        server['UserId'] = auth['LocalUserId']
        server['AccessToken'] = auth['AccessToken']
        return auth

    def _after_connect_validated(self, server, credentials, system_info, connection_mode, verify_authentication, options):
        if options.get('enableAutoLogin') == False:
            self.EmbyServer.Data['auth.user_id'] = server.pop('UserId', None)
            self.EmbyServer.Data['auth.token'] = server.pop('AccessToken', None)
        elif verify_authentication and server.get('AccessToken'):
            if self._validate_authentication(server, connection_mode, options) is not False:
                self.EmbyServer.Data['auth.user_id'] = server['UserId']
                self.EmbyServer.Data['auth.token'] = server['AccessToken']
                return self._after_connect_validated(server, credentials, system_info, connection_mode, False, options)
            elif server.get('AccessToken'):
                return False

        self._update_server_info(server, system_info)
        server['LastConnectionMode'] = connection_mode

        if options.get('updateDateLastAccessed') is not False:
            server['DateLastAccessed'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        self.credentials.add_update_server(credentials['Servers'], server)
        self.credentials.get_credentials(credentials)
        self.EmbyServer.server_id = server['Id']

        # Update configs
        self.EmbyServer.Data['auth.server'] = self.get_server_address(server, connection_mode)
        self.EmbyServer.Data['auth.server-name'] = server['Name']
        self.EmbyServer.Data['auth.server=id'] = server['Id']
        self.EmbyServer.Data['auth.ssl'] = options.get('ssl', self.EmbyServer.Data['auth.ssl'])
        result = {'Servers': [server], 'ConnectUser': self.user}
        result['State'] = 3 if server.get('AccessToken') else 2 #SignedIn...ServerSignIn
        # Connected
        return result

    def _validate_authentication(self, server, connection_mode, options):
        system_info = self._request_url({
            'type': "GET",
            'url': self.get_emby_url(self.get_server_address(server, connection_mode), "System/Info"),
            'verify': options.get('ssl'),
            'dataType': "json",
            'headers': {
                'X-MediaBrowser-Token': server['AccessToken']
            }
        }, True, False)

        if system_info:
            self._update_server_info(server, system_info)
            return True

        return False

    def _update_server_info(self, server, system_info):
        if server is None or system_info is None:
            return

        server['Name'] = system_info['ServerName']
        server['Id'] = system_info['Id']

        if system_info.get('LocalAddress'):
            server['LocalAddress'] = system_info['LocalAddress']
        if system_info.get('WanAddress'):
            server['RemoteAddress'] = system_info['WanAddress']
        if 'MacAddress' in system_info:
            server['WakeOnLanInfos'] = [{'MacAddress': system_info['MacAddress']}]

    def _on_authenticated(self, result, options):
        credentials = self.credentials.get_credentials()
        self.EmbyServer.Data['auth.user_id'] = result['User']['Id']
        self.EmbyServer.Data['auth.token'] = result['AccessToken']

        for server in credentials['Servers']:
            if server['Id'] == result['ServerId']:
                found_server = server
                break
        else:
            return {} # No server found

        if options.get('updateDateLastAccessed') is not False:
            found_server['DateLastAccessed'] = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        found_server['UserId'] = result['User']['Id']
        found_server['AccessToken'] = result['AccessToken']
        self.credentials.add_update_server(credentials['Servers'], found_server)
        self._save_user_info_into_credentials(found_server, result['User'])
        self.credentials.get_credentials(credentials)

# -*- coding: utf-8 -*-
import json
import socket
import helper.utils as Utils
import helper.loghandler

LOG = helper.loghandler.LOG('EMBY.core.connection_manager')


class ConnectionManager:
    def __init__(self, EmbyServer):
        LOG.debug("ConnectionManager initializing...")
        LOG.info("Begin connectToServer")
        self.user = {}
        self.EmbyServer = EmbyServer
        self.Found_Servers = []

    def get_server_address(self, mode):
        if self.EmbyServer.server:
            return self.EmbyServer.server

        modes = {0: self.EmbyServer.ServerData.get('LocalAddress'), 1: self.EmbyServer.ServerData.get('RemoteAddress'), 2: self.EmbyServer.ServerData.get('ManualAddress')}
        return modes.get(mode)

    def get_serveraddress(self):
        return self.get_server_address(self.EmbyServer.ServerData['LastConnectionMode'])

    def clear_data(self):
        LOG.info("connection manager clearing data")
        self.user = None
        self.EmbyServer.ServerData['ConnectAccessToken'] = None
        self.EmbyServer.ServerData['ConnectUserId'] = None
        self.EmbyServer.ServerData['Servers'] = list()
        self.EmbyServer.server = None
        self.EmbyServer.user_id = None
        self.EmbyServer.Token = None

    def get_available_servers(self):
        LOG.debug("Begin getAvailableServers")
        self.Found_Servers = find_servers(server_discovery())
        self._get_connect_servers()

    def login_to_connect(self, username, password):
        if not username:
            return {}  # username cannot be empty

        if not password:
            return {}  # password cannot be empty

        result = self.request_url({
            'type': "POST",
            'url': get_connect_url("user/authenticate"),
            'data': {'nameOrEmail': username, 'rawpw': password},
            'dataType': "json"
        }, True, False)

        if not result:  # Failed to login
            return {}

        self.EmbyServer.ServerData['ConnectAccessToken'] = result['AccessToken']
        self.EmbyServer.ServerData['ConnectUserId'] = result['User']['Id']
        self.EmbyServer.ServerData['ConnectUser'] = result['User']['Name']

        # Signed in
        self._on_connect_user_signin(result['User'])
        return result

    def login(self, server, username, password, clear):
        if not username:
            LOG.error("username cannot be empty")
            return False

        request = {
            'type': "POST",
            'url': get_emby_url(server, "Users/AuthenticateByName"),
            'params': {'username': username, 'pw': password or ""}
        }

        if clear:
            request['params']['pw'] = password or ""

        result = self.request_url(request, False, True)

        if not result:
            return False

        self.EmbyServer.user_id = result['User']['Id']
        self.EmbyServer.Token = result['AccessToken']
        self.EmbyServer.ServerData['UserId'] = result['User']['Id']
        self.EmbyServer.ServerData['AccessToken'] = result['AccessToken']
        return result

    def connect_to_address(self, address):
        if not address:
            return False

        address = normalize_address(address)
        public_info = self._try_connect(address, False)

        if not public_info:
            return False

        LOG.info("connectToAddress %s succeeded" % address)
        self.EmbyServer.ServerData = {'ManualAddress': address, 'LastConnectionMode': 2}  # Manual
        self._update_server_info(public_info)
        self.EmbyServer.ServerData = self.connect_to_server()

        if not self.EmbyServer.ServerData:
            return False

        return self.EmbyServer.ServerData

    def connect_to_server(self):
        LOG.debug("Begin connectToServer")
        tests = []

        if self.EmbyServer.ServerData.get('LastConnectionMode') != 1 and self.EmbyServer.ServerData.get('AccessToken'):  # Remote
            tests.append(self.EmbyServer.ServerData['LastConnectionMode'])

        if 2 not in tests:  # Manual
            tests.append(2)

        if 0 not in tests:  # Local
            tests.append(0)

        if 1 not in tests:  # Remote
            tests.append(1)

        return self._test_next_connection_mode(tests, 0)

    def connect(self):
        LOG.info("Begin connect")

        if self.EmbyServer.ServerData:
            if "Name" in self.EmbyServer.ServerData:
                self.Found_Servers.append(self.EmbyServer.ServerData)
                return self.connect_to_server()


        self.get_available_servers()
        self._ensure_connect_user()
        return {'State': 4 if (not self.Found_Servers and not self.user) else 1, 'ConnectUser': self.user}  # ConnectSignIn...ServerSelection

    def request_url(self, request, headers, ServerConnect):
        if headers:
            get_headers(request)

        return self.EmbyServer.http.request(request, ServerConnect, False)

    def _try_connect(self, url, ServerConnect):
        url = get_emby_url(url, "system/info/public")
        LOG.info("tryConnect url: %s" % url)
        return self.request_url({'type': "GET", 'url': url, 'dataType': "json"}, True, ServerConnect)

    def _test_next_connection_mode(self, tests, index):
        if index >= len(tests):
            LOG.info("Tested all connection modes. Failing server connection.")
            return {}

        mode = tests[index]
        address = self.get_server_address(mode)
        skip_test = False
        LOG.info("testing connection mode %s with server %s" % (str(mode), self.EmbyServer.ServerData.get('Name')))

        if mode == 0:  # Local
            if string_equals_ignore_case(address, self.EmbyServer.ServerData.get('ManualAddress')):
                LOG.info("skipping LocalAddress test because it is the same as ManualAddress")
                skip_test = True

        if skip_test or not address:
            LOG.info("skipping test at index: %s" % index)
            return self._test_next_connection_mode(tests, index + 1)

        result = self._try_connect(address, True)

        if not result:
            return self._test_next_connection_mode(tests, index + 1)

        LOG.info("calling onSuccessfulConnection with connection mode %s with server %s" % (mode, self.EmbyServer.ServerData.get('Name')))
        return self._on_successful_connection(result, mode)

    def _on_successful_connection(self, system_info, connection_mode):
        # Emby Connect
        if self.EmbyServer.ServerData.get('ConnectAccessToken') is not False:
            if self._ensure_connect_user() is not False:
                if self.EmbyServer.ServerData.get('ExchangeToken'):
                    self._add_authentication_info_from_connect(connection_mode)

        return self._after_connect_validated(system_info, connection_mode, True)

    def _get_connect_servers(self):
        LOG.debug("Begin getConnectServers")

        if not self.EmbyServer.ServerData.get('ConnectAccessToken') or not self.EmbyServer.ServerData.get('ConnectUserId'):
            return

        url = get_connect_url("servers?userId=%s" % self.EmbyServer.ServerData['ConnectUserId'])
        request = {
            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {'X-Connect-UserToken': self.EmbyServer.ServerData['ConnectAccessToken']}
        }

        result = self.request_url(request, True, False)

        if not result:
            return

        for server in result:
            self.Found_Servers.append({
                'ExchangeToken': server['AccessKey'],
                'ConnectServerId': server['Id'],
                'Id': server['SystemId'],
                'Name': server['Name'],
                'RemoteAddress': server['Url'],
                'LocalAddress': server['LocalAddress'],
                'UserLinkType': "Guest" if server['UserType'].lower() == "guest" else "LinkedUser"
            })

    def _ensure_connect_user(self):
        if self.user and self.user['Id'] == self.EmbyServer.ServerData['ConnectUserId']:
            return

        if self.EmbyServer.ServerData.get('ConnectUserId') and self.EmbyServer.ServerData.get('ConnectAccessToken'):
            self.user = None
            result = self.get_connect_user(self.EmbyServer.ServerData['ConnectUserId'], self.EmbyServer.ServerData['ConnectAccessToken'])
            self._on_connect_user_signin(result)

    def _on_connect_user_signin(self, user):
        self.user = user
        LOG.info("connectusersignedin %s" % user)

    def _add_authentication_info_from_connect(self, connection_mode):
        if not self.EmbyServer.ServerData.get('ExchangeToken'):
            LOG.error('server ExchangeToken cannot be null')
            return False

        if not self.EmbyServer.ServerData.get('ConnectUserId'):
            LOG.error('server ConnectUserId cannot be null')
            return False

        auth = "Emby "
        auth += "Client=%s, " % Utils.addon_name
        auth += "Device=%s, " % Utils.device_name
        auth += "DeviceId=%s, " % Utils.device_id
        auth += "Version=%s " % Utils.addon_version
        auth = self.request_url({
            'url': get_emby_url(self.get_server_address(connection_mode), "Connect/Exchange"),
            'type': "GET",
            'dataType': "json",
            'params': {'ConnectUserId': self.EmbyServer.ServerData['ConnectUserId']},
            'headers': {'X-Emby-Token': self.EmbyServer.ServerData['ExchangeToken'], 'Authorization': auth}
        }, True, False)

        if not auth:
            self.EmbyServer.ServerData['UserId'] = None
            self.EmbyServer.ServerData['AccessToken'] = None
            return False

        self.EmbyServer.ServerData['UserId'] = auth['LocalUserId']
        self.EmbyServer.ServerData['AccessToken'] = auth['AccessToken']
        return True

    def _after_connect_validated(self, system_info, connection_mode, verify_authentication):
        if verify_authentication and self.EmbyServer.ServerData.get('AccessToken'):
            if self._validate_authentication(connection_mode) is not False:
                self.EmbyServer.user_id = self.EmbyServer.ServerData['UserId']
                self.EmbyServer.Token = self.EmbyServer.ServerData['AccessToken']
                return self._after_connect_validated(system_info, connection_mode, False)

            if self.EmbyServer.ServerData.get('AccessToken'):
                return False

        if not self._update_server_info(system_info):
            return False

        self.EmbyServer.ServerData['LastConnectionMode'] = connection_mode
        self.EmbyServer.server = self.get_server_address(connection_mode)
        self.EmbyServer.Name = self.EmbyServer.ServerData['Name']
        self.EmbyServer.server_id = self.EmbyServer.ServerData['Id']
        result = {'Servers': [self.EmbyServer.ServerData], 'ConnectUser': self.user, 'State': 3 if self.EmbyServer.ServerData.get('AccessToken') else 2}
        return result

    def _validate_authentication(self, connection_mode):
        system_info = self.request_url({
            'type': "GET",
            'url': get_emby_url(self.get_server_address(connection_mode), "System/Info"),
            'dataType': "json",
            'headers': {'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']}
        }, True, False)

        if not system_info:
            return False

        return self._update_server_info(system_info)

    def _update_server_info(self, system_info):
        if self.EmbyServer.ServerData is None or not system_info:
            return False

        self.EmbyServer.ServerData['Name'] = system_info['ServerName']
        self.EmbyServer.ServerData['Id'] = system_info['Id']

        if system_info.get('LocalAddress'):
            self.EmbyServer.ServerData['LocalAddress'] = system_info['LocalAddress']

        if system_info.get('WanAddress'):
            self.EmbyServer.ServerData['RemoteAddress'] = system_info['WanAddress']

        if 'MacAddress' in system_info:
            self.EmbyServer.ServerData['WakeOnLanInfos'] = [{'MacAddress': system_info['MacAddress']}]

        return True

    def get_connect_user(self, user_id, access_token):
        if not user_id:
            return False  # null userId

        if not access_token:
            return False  # null accessToken

        return self.request_url({
            'type': "GET",
            'url': get_connect_url('user?id=%s' % user_id),
            'dataType': "json",
            'headers': {'X-Connect-UserToken': access_token}
        }, True, False)

def get_connect_url(handler):
    return "https://connect.emby.media/service/%s" % handler

def get_emby_url(base, handler):
    return "%s/emby/%s" % (base, handler)

def get_headers(request):
    headers = request.setdefault('headers', {})

    if request.get('dataType') == "json":
        headers['Accept'] = "application/json"
        headers['Accept-Charset'] = "UTF-8,*"
        headers['Accept-encoding'] = "gzip"
        request.pop('dataType')

    headers['X-Application'] = "%s/%s" % (Utils.addon_name, Utils.addon_version)
    headers['Content-type'] = request.get('contentType', 'application/x-www-form-urlencoded; charset=UTF-8')

def server_discovery():
    MULTI_GROUP = ("<broadcast>", 7359)
    MESSAGE = b"who is EmbyServer?"
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)  # This controls the socket.timeout exception
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
    LOG.debug("MultiGroup      : %s" % str(MULTI_GROUP))
    LOG.debug("Sending UDP Data: %s" % MESSAGE)
    servers = []

    try:
        sock.sendto(MESSAGE, MULTI_GROUP)
    except Exception as error:
        LOG.error("ERROR: %s" % error)
        return servers

    while True:
        try:
            data, _ = sock.recvfrom(1024)  # buffer size
            IncommingData = json.loads(data)

            if IncommingData not in servers:
                servers.append(IncommingData)
        except socket.timeout:
            LOG.info("Found Servers: %s" % servers)
            return servers
        except Exception as Error:
            LOG.error("Error trying to find servers: %s" % Error)
            return servers

def string_equals_ignore_case(str1, str2):
    return (str1 or "").lower() == (str2 or "").lower()

def normalize_address(address):
    # Attempt to correct bad input
    address = address.strip()
    address = address.lower()

    if 'http' not in address:
        address = "http://%s" % address

    return address

def convert_endpoint_address_to_manual_address(info):
    if info.get('Address') and info.get('EndpointAddress'):
        address = info['EndpointAddress'].split(':')[0]
        # Determine the port, if any
        parts = info['Address'].split(':')

        if len(parts) > 1:
            port_string = parts[len(parts) - 1]
            address += ":%s" % int(port_string)
            return normalize_address(address)

    return None

def find_servers(found_servers):
    servers = []

    for found_server in found_servers:
        server = convert_endpoint_address_to_manual_address(found_server)

        if not server and not found_server.get('Address'):
            LOG.warning("Server %s has no address." % found_server)
            continue

        info = {'Id': found_server['Id'], 'LocalAddress': server or found_server['Address'], 'Name': found_server['Name']}
        servers.append(info)

    return servers

import json
import socket
from helper import utils, loghandler

LOG = loghandler.LOG('EMBY.core.connection_manager')


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

    def clear_data(self):
        LOG.info("connection manager clearing data")
        self.user = None
        self.EmbyServer.ServerData['ConnectAccessToken'] = None
        self.EmbyServer.ServerData['ConnectUserId'] = None
        self.EmbyServer.ServerData['Servers'] = []
        self.EmbyServer.server = None
        self.EmbyServer.user_id = None
        self.EmbyServer.Token = None

    def login_to_connect(self, username, password):
        if not username:
            return {}  # username cannot be empty

        if not password:
            return {}  # password cannot be empty

        result = self.request_url({'type': "POST", 'url': "https://connect.emby.media/service/user/authenticate", 'data': {'nameOrEmail': username, 'rawpw': password}, 'dataType': "json"})

        if not result:  # Failed to login
            return {}

        self.EmbyServer.ServerData['ConnectAccessToken'] = result['AccessToken']
        self.EmbyServer.ServerData['ConnectUserId'] = result['User']['Id']
        self.EmbyServer.ServerData['ConnectUser'] = result['User']['Name']

        # Signed in
        self._on_connect_user_signin(result['User'])
        return result

    def login(self, server, username, password):
        if not username:
            LOG.error("username cannot be empty")
            return False

        result = self.request_url({'type': "POST", 'url': "%s/emby/Users/AuthenticateByName" % server, 'params': {'username': username, 'pw': password or ""}})

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
        public_info = self._try_connect(address)

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

        LOG.debug("Begin getAvailableServers")
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = b"who is EmbyServer?"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)  # This controls the socket.timeout exception
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        LOG.debug("MultiGroup: %s" % str(MULTI_GROUP))
        LOG.debug("Sending UDP Data: %s" % MESSAGE)
        found_servers = []

        try:
            sock.sendto(MESSAGE, MULTI_GROUP)

            while True:
                try:
                    data, _ = sock.recvfrom(1024)  # buffer size
                    IncommingData = json.loads(data)

                    if IncommingData not in found_servers:
                        found_servers.append(IncommingData)
                except socket.timeout:
                    LOG.info("Found Servers: %s" % found_servers)
                    break
                except Exception as Error:
                    LOG.error("Error trying to find servers: %s" % Error)
                    break
        except Exception as error:
            LOG.error("ERROR: %s" % error)

        self.Found_Servers = []

        for found_server in found_servers:
            server = ""

            if found_server.get('Address') and found_server.get('EndpointAddress'):
                address = found_server['EndpointAddress'].split(':')[0]
                # Determine the port, if any
                parts = found_server['Address'].split(':')

                if len(parts) > 1:
                    port_string = parts[len(parts) - 1]
                    address += ":%s" % int(port_string)
                    server = normalize_address(address)

            if not server and not found_server.get('Address'):
                LOG.warning("Server %s has no address." % found_server)
                continue

            self.Found_Servers.append({'Id': found_server['Id'], 'LocalAddress': server or found_server['Address'], 'Name': found_server['Name']})

        LOG.debug("Begin getConnectServers")

        if self.EmbyServer.ServerData.get('ConnectAccessToken') and self.EmbyServer.ServerData.get('ConnectUserId'):
            request = {'type': "GET", 'url': "https://connect.emby.media/service/servers?userId=%s" % self.EmbyServer.ServerData['ConnectUserId'], 'dataType': "json", 'headers': {'X-Connect-UserToken': self.EmbyServer.ServerData['ConnectAccessToken']}}
            result = self.request_url(request)

            if result:
                for server in result:
                    self.Found_Servers.append({'ExchangeToken': server['AccessKey'], 'ConnectServerId': server['Id'], 'Id': server['SystemId'], 'Name': server['Name'], 'RemoteAddress': server['Url'], 'LocalAddress': server['LocalAddress'], 'UserLinkType': "Guest" if server['UserType'].lower() == "guest" else "LinkedUser"})

        self._ensure_connect_user()
        return {'State': 4 if (not self.Found_Servers and not self.user) else 1, 'ConnectUser': self.user}  # ConnectSignIn...ServerSelection

    def request_url(self, request):
        headers = request.setdefault('headers', {})

        if request.get('dataType') == "json":
            headers['Accept'] = "application/json"
            headers['Accept-Charset'] = "UTF-8,*"
            headers['Accept-encoding'] = "gzip"
            request.pop('dataType')

        headers['X-Application'] = "%s/%s" % (utils.addon_name, utils.addon_version)
        headers['Content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        return self.EmbyServer.http.request(request, True, False)

    def _try_connect(self, url):
        url = "%s/emby/system/info/public" % url
        LOG.info("tryConnect url: %s" % url)
        return self.request_url({'type': "GET", 'url': url, 'dataType': "json"})

    def _test_next_connection_mode(self, tests, index):
        if index >= len(tests):
            LOG.info("Tested all connection modes. Failing server connection.")
            return {}

        connection_mode = tests[index]
        address = self.get_server_address(connection_mode)
        skip_test = False
        LOG.info("testing connection mode %s with server %s" % (str(connection_mode), self.EmbyServer.ServerData.get('Name')))

        if connection_mode == 0:  # Local
            if (address or "").lower() == (self.EmbyServer.ServerData.get('ManualAddress') or "").lower():
                LOG.info("skipping LocalAddress test because it is the same as ManualAddress")
                skip_test = True

        if skip_test or not address:
            LOG.info("skipping test at index: %s" % index)
            return self._test_next_connection_mode(tests, index + 1)

        system_info = self._try_connect(address)

        if not system_info:
            return self._test_next_connection_mode(tests, index + 1)

        LOG.info("calling onSuccessfulConnection with connection mode %s with server %s" % (connection_mode, self.EmbyServer.ServerData.get('Name')))

        # Emby Connect
        if self.EmbyServer.ServerData.get('ConnectAccessToken') is not False:
            if self._ensure_connect_user() is not False:
                if self.EmbyServer.ServerData.get('ExchangeToken'):
                    if self.EmbyServer.ServerData.get('ExchangeToken') and self.EmbyServer.ServerData.get('ConnectUserId'):
                        auth = self.request_url({'url': "%s/emby/%s" % (self.get_server_address(connection_mode), "Connect/Exchange"), 'type': "GET", 'dataType': "json", 'params': {'ConnectUserId': self.EmbyServer.ServerData['ConnectUserId']}, 'headers': {'X-Emby-Token': self.EmbyServer.ServerData['ExchangeToken'], 'Authorization': "Emby Client=%s,Device=%s,DeviceId=%s,Version=%s" % (utils.addon_name, utils.device_name, utils.device_id, utils.addon_version)}})

                        if auth:
                            self.EmbyServer.ServerData['UserId'] = auth['LocalUserId']
                            self.EmbyServer.ServerData['AccessToken'] = auth['AccessToken']
                        else:
                            self.EmbyServer.ServerData['UserId'] = None
                            self.EmbyServer.ServerData['AccessToken'] = None
                    else:
                        LOG.error('server ExchangeToken/ConnectUserId cannot be null')

        return self._after_connect_validated(system_info, connection_mode, True)

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

    def _after_connect_validated(self, system_info, connection_mode, verify_authentication):
        if verify_authentication and self.EmbyServer.ServerData.get('AccessToken'):
            system_info = self.request_url({'type': "GET", 'url': "%s/emby/%s" % (self.get_server_address(connection_mode), "System/Info"), 'dataType': "json", 'headers': {'X-Emby-Token': self.EmbyServer.ServerData['AccessToken']}})

            if system_info:
                if self._update_server_info(system_info):
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

    def _update_server_info(self, system_info):
        if not self.EmbyServer.ServerData or not system_info:
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

        return self.request_url({'type': "GET", 'url': "https://connect.emby.media/service/user?id=%s" % user_id, 'dataType': "json", 'headers': {'X-Connect-UserToken': access_token}})

def normalize_address(address):
    # Attempt to correct bad input
    address = address.strip()
    address = address.lower()

    if 'http' not in address:
        address = "http://%s" % address

    return address

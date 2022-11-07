import socket
import json
from _thread import start_new_thread
from dialogs import serverconnect, usersconnect, loginconnect, loginmanual, servermanual
from helper import utils, loghandler
from database import library
from hooks import websocket
from . import views, api, http
LOG = loghandler.LOG('EMBY.emby.emby')


class EmbyServer:
    def __init__(self, UserDataChanged, ServerSettings):
        self.UserDataChanged = UserDataChanged
        self.EmbySession = []
        self.Websocket = None
        self.Found_Servers = []
        self.ServerSettings = ServerSettings
        self.Firstrun = not bool(self.ServerSettings)
        self.ServerData = {'AccessToken': "", 'UserId': "", 'UserName': "", 'UserImageUrl': "", 'ServerName': "", 'ServerId': "", 'ServerUrl': "", 'EmbyConnectExchangeToken': "", 'EmbyConnectUserId': "", 'EmbyConnectUserName': "", 'EmbyConnectAccessToken': "", 'LastConnectionMode': "", 'ManualAddress': "", 'RemoteAddress': "", 'LocalAddress': "" ,'EmbyConnectRemoteAddress': "", 'EmbyConnectLocalAddress': "", 'AdditionalUsers': {}}
        self.ServerReconnecting = False
        self.http = http.HTTP(self)
        self.API = api.API(self)
        self.Views = views.Views(self)
        self.library = library.Library(self)
        LOG.info("---[ INIT EMBYCLIENT: ]---")

    def ServerUnreachable(self):
        if not self.ServerReconnecting:
            utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33146))
            start_new_thread(self.ServerReconnect, ())

    def ServerReconnect(self):
        if not self.ServerReconnecting:
            self.ServerReconnecting = True
            Tries = 0
            self.stop()

            while True:
                if utils.SystemShutdown:
                    break

                if self.ServerConnect():
                    self.start()
                    break

                # Delay reconnect: Fast 40 re-tries (first 10 seconds), after delay by 5 seconds
                if Tries > 40:
                    if utils.sleep(5):
                        break
                else:
                    Tries += 1

                    if utils.sleep(0.25):
                        break

            self.ServerReconnecting = False

    def start(self):
        LOG.info("---[ START EMBYCLIENT: %s ]---" % self.ServerData['ServerId'])
        self.Views.update_views()
        self.library.load_settings()
        self.Views.update_nodes()
        self.Websocket = websocket.WSClient(self)
        self.Websocket.start()
        utils.SyncPause[self.ServerData['ServerId']] = False
        start_new_thread(self.library.KodiStartSync, (self.Firstrun,))  # start initial sync
        self.Firstrun = False

        if utils.connectMsg:
            utils.Dialog.notification(heading=utils.addon_name, message="%s %s" % (utils.Translate(33000), self.ServerData['UserName']), icon=self.ServerData['UserImageUrl'], time=1500, sound=False)

        LOG.info("[ Server Online ]")

    def stop(self):
        if self.EmbySession:
            LOG.info("---[ STOP EMBYCLIENT: %s ]---" % self.ServerData['ServerId'])
            utils.SyncPause[self.ServerData['ServerId']] = True

            if self.Websocket:
                self.Websocket.close()
                self.Websocket = None

            self.EmbySession = []
            self.http.stop_session()
        else:
            LOG.info("Emby client already closed")

    def add_AdditionalUser(self, UserId, UserName):
        self.ServerData['AdditionalUsers'][UserId] = UserName
        self.save_credentials()
        self.API.session_add_user(self.EmbySession[0]['Id'], UserId, True)

    def remove_AdditionalUser(self, UserId):
        if UserId in self.ServerData['AdditionalUsers']:
            del self.ServerData['AdditionalUsers'][UserId]

        self.save_credentials()
        self.API.session_add_user(self.EmbySession[0]['Id'], UserId, False)

    # Login into server. If server is None, then it will show the proper prompts to login, etc.
    # If a server id is specified then only a login dialog will be shown for that server.
    def ServerInitConnection(self):
        LOG.info("--[ server/%s ]" % "DEFAULT")

        # load credentials froom file
        if self.ServerSettings:
            FileData = utils.readFileString(self.ServerSettings)

            if FileData:
                LoadedServerSettings = json.loads(FileData)

                if 'ServerId' in LoadedServerSettings and LoadedServerSettings['ServerId']: # file content is not valid
                    self.ServerData = LoadedServerSettings

        # Refresh EmbyConnect Emby server addresses (dynamic IP)
        if self.ServerData["LastConnectionMode"] in ("EmbyConnectLocalAddress", "EmbyConnectRemoteAddress"):
            LOG.info("Refresh Emby server urls from EmbyConnect")
            request = {'type': "GET", 'url': "https://connect.emby.media/service/servers?userId=%s" % self.ServerData['EmbyConnectUserId'], 'headers': {'X-Connect-UserToken': self.ServerData['EmbyConnectAccessToken']}}
            result = self.request_url(request)

            if result:
                for server in result:
                    if server['SystemId'] == self.ServerData['ServerId']:
                        self.ServerData['EmbyConnectRemoteAddress'] = server['Url']
                        self.ServerData['EmbyConnectLocalAddress'] = server['LocalAddress']
                        LOG.info("Refresh Emby server urls from EmbyConnect, found")
                        break

        if self.ServerConnect(False):
            SignedIn = True
        else:
            SignedIn = True
            self.ServerDetect()

            # Menu dialogs
            while True:
                if utils.sleep(0.01):
                    SignedIn = False
                    break

                Dialog = serverconnect.ServerConnect("script-emby-connect-server.xml", *utils.CustomDialogParameters)
                Dialog.EmbyServer = self
                Dialog.UserImageUrl = self.ServerData['UserImageUrl']
                Dialog.emby_connect = not self.ServerData['UserId']
                Dialog.doModal()
                del Dialog

                if self.ServerData['LastConnectionMode'] in ("LocalAddress", "RemoteAddress",):
                    if self.UserLogin():
                        if self.ServerConnect():  # SignedIn
                            break

                    self.ServerData['LastConnectionMode'] = ""
                elif self.ServerData['LastConnectionMode'] == "ManualAddress":
                    LOG.debug("Adding manual server")
                    Dialog = servermanual.ServerManual("script-emby-connect-server-manual.xml", *utils.CustomDialogParameters)
                    Dialog.connect_to_address = self.connect_to_address
                    Dialog.doModal()
                    del Dialog

                    if self.ServerData['ManualAddress']:
                        if self.UserLogin():
                            if self.ServerConnect():  # SignedIn
                                break

                    self.ServerData['LastConnectionMode'] = ""
                elif self.ServerData['LastConnectionMode'] in ("EmbyConnectLocalAddress", "EmbyConnectRemoteAddress"):
                    if self.ServerConnect():  # SignedIn
                        break

                    self.ServerData['LastConnectionMode'] = ""
                elif self.ServerData['LastConnectionMode'] == "EmbyConnect":
                    self.ServerData['LastConnectionMode'] = ""
                    Dialog = loginconnect.LoginConnect("script-emby-connect-login.xml", *utils.CustomDialogParameters)
                    Dialog.EmbyServer = self
                    Dialog.doModal()
                    del Dialog
                else:
                    SignedIn = False
                    break

        if SignedIn:
            self.start()
            return self.ServerData['ServerId'], self

        return False, None

    def save_credentials(self):
        if not self.ServerSettings:
            self.ServerSettings = "%sservers_%s.json" % (utils.FolderAddonUserdata, self.ServerData['ServerId'])

        utils.writeFileString(self.ServerSettings, json.dumps(self.ServerData, sort_keys=True, indent=4, ensure_ascii=False))

    def ServerConnect(self, SaveCredentails=True):
        # Connect to server verification
        if self.ServerData["AccessToken"]:
            SystemInfo = self._try_connect(self.ServerData["ServerUrl"])
            self.ServerData['RemoteAddress'] = SystemInfo.get('WanAddress', self.ServerData['RemoteAddress'])
            self.ServerData['LocalAddress'] = SystemInfo.get('LocalAddress', self.ServerData['LocalAddress'])

            if SystemInfo:
                LOG.info("User is authenticated.")
                utils.DatabaseFiles[self.ServerData['ServerId']] = utils.translatePath("special://profile/Database/emby_%s.db" % self.ServerData['ServerId'])
                self.EmbySession = self.API.get_device()

                if not self.EmbySession:
                    LOG.error("---[ SESSION ERROR EMBYCLIENT: %s ] %s ---" % (self.ServerData['ServerId'], self.EmbySession))
                    return False

                if not self.ServerData['UserName']:
                    self.ServerData['UserName'] = self.EmbySession[0]['UserName']

                self.API.post_capabilities({'Id': self.EmbySession[0]['Id'], 'PlayableMediaTypes': "Audio,Video,Photo", 'SupportsMediaControl': True, 'SupportsSync': True, 'SupportedCommands': "MoveUp,MoveDown,MoveLeft,MoveRight,Select,Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,GoHome,PageUp,NextLetter,GoToSearch,GoToSettings,PageDown,PreviousLetter,TakeScreenshot,VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,SetAudioStreamIndex,SetSubtitleStreamIndex,SetRepeatMode,Mute,Unmute,SetVolume,Pause,Unpause,Play,Playstate,PlayNext,PlayMediaSource", 'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"})

                for AdditionalUserId in self.ServerData['AdditionalUsers']:
                    AddUser = True

                    for SessionAdditionalUser in self.EmbySession[0]['AdditionalUsers']:
                        if SessionAdditionalUser['UserId'] == AdditionalUserId:
                            AddUser = False
                            break

                    if AddUser:
                        if utils.connectMsg:
                            utils.Dialog.notification(heading=utils.addon_name, message="%s %s" % (utils.Translate(33067), self.ServerData['AdditionalUsers'][AdditionalUserId]), icon=utils.icon, time=1500, sound=False)
                        self.API.session_add_user(self.EmbySession[0]['Id'], AdditionalUserId, True)

                if not self.ServerData['UserImageUrl']:
                    self.ServerData['UserImageUrl'] = utils.icon

                if SaveCredentails:
                    self.save_credentials()

                return True

        return False

    def UserLogin(self):
        users = self.API.get_public_users()

        if not users:
            return self.login_manual(None)

        Dialog = usersconnect.UsersConnect("script-emby-connect-users.xml", *utils.CustomDialogParameters)
        Dialog.API = self.API
        Dialog.ServerData = self.ServerData
        Dialog.users = users
        Dialog.doModal()
        SelectedUser = Dialog.SelectedUser
        ManualLogin = Dialog.ManualLogin
        del Dialog

        if SelectedUser:
            if SelectedUser['HasPassword']:
                LOG.debug("User has password, present manual login")
                Result = self.login_manual(SelectedUser['Name'])

                if Result:
                    return Result
            else:
                return self.ServerLogin(self.ServerData['ServerUrl'], SelectedUser['Name'], None)
        elif ManualLogin:
            Result = self.login_manual("")

            if Result:
                return Result
        else:
            return False  # No user selected

        return self.UserLogin()

    # Return manual login user authenticated
    def login_manual(self, UserName):
        Dialog = loginmanual.LoginManual("script-emby-connect-login-manual.xml", *utils.CustomDialogParameters)
        Dialog.username = UserName
        Dialog.EmbyServer = self
        Dialog.doModal()
        SelectedUser = Dialog.SelectedUser
        del Dialog
        return SelectedUser

    def login_to_connect(self, username, password):
        if not username:
            return {}  # username cannot be empty

        if not password:
            return {}  # password cannot be empty

        result = self.request_url({'type': "POST", 'url': "https://connect.emby.media/service/user/authenticate", 'data': {'nameOrEmail': username, 'rawpw': password}})

        if not result:  # Failed to login
            return {}

        # Signed in woith EmbyConnect user
        self.ServerData['EmbyConnectUserId'] = result['User']['Id']
        self.ServerData['EmbyConnectUserName'] = result['User']['Name']
        self.ServerData['EmbyConnectAccessToken'] = result['AccessToken']
        LOG.debug("Begin getConnectServers")

        if self.ServerData['EmbyConnectAccessToken'] and self.ServerData['EmbyConnectUserId']:
            request = {'type': "GET", 'url': "https://connect.emby.media/service/servers?userId=%s" % self.ServerData['EmbyConnectUserId'], 'headers': {'X-Connect-UserToken': self.ServerData['EmbyConnectAccessToken']}}
            EmbyConnectServers = self.request_url(request)

            if EmbyConnectServers:
                for EmbyConnectServer in EmbyConnectServers:
                    self.Found_Servers.append({'ExchangeToken': EmbyConnectServer['AccessKey'], 'ConnectServerId': EmbyConnectServer['Id'], 'Id': EmbyConnectServer['SystemId'], 'Name': "Emby Connect: %s" % EmbyConnectServer['Name'], 'RemoteAddress': EmbyConnectServer['Url'], 'LocalAddress': EmbyConnectServer['LocalAddress'], 'UserLinkType': "Guest" if EmbyConnectServer['UserType'].lower() == "guest" else "LinkedUser"})

        return result

    def ServerLogin(self, ServerUrl, username, password):
        LOG.info("Login to server")

        if not username:
            LOG.error("username cannot be empty")
            return False

        # remove old access token and credential data file
        if self.ServerData['ServerId'] in utils.EmbyServers:
            utils.EmbyServers[self.ServerData['ServerId']].API.session_logout()
            del utils.EmbyServers[self.ServerData['ServerId']]
            utils.delFile("%sservers_%s.json" % (utils.FolderAddonUserdata, self.ServerData['ServerId']))

        result = self.http.request({'type': "POST", 'url': "%s/emby/Users/AuthenticateByName" % ServerUrl, 'params': {'username': username, 'pw': password or ""}}, True, False)

        if not result:
            return False

        self.ServerData['UserId'] = result['User']['Id']
        self.ServerData['AccessToken'] = result['AccessToken']
        return result

    def connect_to_address(self, address):
        if not address:
            return False

        address = normalize_address(address)
        public_info = self._try_connect(address)

        if not public_info:
            return False

        self.ServerData.update({'ManualAddress': address, 'LastConnectionMode': "ManualAddress", 'ServerName': public_info['ServerName'], 'ServerId': public_info['Id'], 'ServerUrl': address})
        LOG.info("connectToAddress %s succeeded" % address)
        return True

    def connect_to_server(self):
        LOG.debug("Begin connectToServer")
        Connections = []

        # Try local connections first
        if self.ServerData['LastConnectionMode']:
            Connections.append(self.ServerData['LastConnectionMode'].replace("RemoteAddress", "LocalAddress")) # Local connection priority

        if "EmbyConnectLocalAddress" not in Connections:
            Connections.append("EmbyConnectLocalAddress")

        if "EmbyConnectRemoteAddress" not in Connections:
            Connections.append("EmbyConnectRemoteAddress")

        if "ManualAddress" not in Connections:
            Connections.append("ManualAddress")

        if "LocalAddress" not in Connections:
            Connections.append("LocalAddress")

        if "RemoteAddress" not in Connections:
            Connections.append("RemoteAddress")

        for Connection in Connections:
            ConnectUrl = self.ServerData.get(Connection)

            if not ConnectUrl:
                LOG.info("Skip Emby server connection test: %s" % Connection)
                continue

            public_info = self._try_connect(ConnectUrl)

            if not public_info:
                continue

            LOG.info("calling onSuccessfulConnection with connection mode %s with server %s" % (Connection, self.ServerData['ServerName']))

            # Emby Connect
            if self.ServerData['EmbyConnectExchangeToken'] and self.ServerData['EmbyConnectUserId']:
                auth = self.request_url({'url': "%s/emby/Connect/Exchange" % ConnectUrl, 'type': "GET", 'params': {'ConnectUserId': self.ServerData['EmbyConnectUserId']}, 'headers': {'X-Emby-Token': self.ServerData['EmbyConnectExchangeToken'], 'Authorization': "Emby Client=%s,Device=%s,DeviceId=%s,Version=%s" % (utils.addon_name, utils.device_name, utils.device_id, utils.addon_version)}})

                if auth:
                    self.ServerData['UserId'] = auth['LocalUserId']
                    self.ServerData['AccessToken'] = auth['AccessToken']
                else:
                    self.ServerData['UserId'] = ""
                    self.ServerData['AccessToken'] = ""

            self.ServerData['LastConnectionMode'] = Connection
            self.ServerData['ServerUrl'] = ConnectUrl

            if self.ServerData['AccessToken']:
                return "SignedIn"

            return "ServerSignIn"

        LOG.info("Tested all connection modes. Failing server connection.")
        return "NotConnected"

    def ServerDetect(self):
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

    def request_url(self, request):
        headers = request.setdefault('headers', {})
        headers['Accept'] = "application/json"
        headers['Accept-Charset'] = "UTF-8,*"
        headers['Accept-encoding'] = "gzip"
        headers['X-Application'] = "%s/%s" % (utils.addon_name, utils.addon_version)
        headers['Content-type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        return self.http.request(request, True, False)

    def _try_connect(self, url):
        url = "%s/emby/system/info/public" % url
        LOG.info("tryConnect url: %s" % url)
        return self.request_url({'type': "GET", 'url': url})

def normalize_address(address):
    # Attempt to correct bad input
    address = address.strip()
    address = address.lower()

    if 'http' not in address:
        address = "http://%s" % address

    return address

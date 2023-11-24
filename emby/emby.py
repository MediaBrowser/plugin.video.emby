import json
from _thread import start_new_thread
import _socket
import xbmc
from dialogs import serverconnect, usersconnect, loginconnect, loginmanual, servermanual
from helper import utils, playerops
from database import library
from hooks import websocket
from . import views, api, http


class EmbyServer:
    def __init__(self, ServerSettings):
        self.ShutdownInProgress = False
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
        xbmc.log("EMBY.emby.emby: ---[ INIT EMBYCLIENT: ]---", 1) # LOGINFO

    def ServerReconnect(self):
        if not self.ServerReconnecting:
            start_new_thread(self.worker_ServerReconnect, ())

    def worker_ServerReconnect(self):
        xbmc.log(f"EMBY.emby.emby: THREAD: --->[ Reconnecting ] {self.ServerData['ServerName']} / {self.ServerData['ServerId']}", 1) # LOGINFO

        if not self.ServerReconnecting:
            utils.SyncPause.update({f"server_reconnecting_{self.ServerData['ServerId']}": True, f"server_busy_{self.ServerData['ServerId']}": False})
            self.ServerReconnecting = True
            self.stop()

            while True:
                if utils.sleep(1):
                    break

                xbmc.log(f"EMBY.emby.emby: Reconnect try again: {self.ServerData['ServerName']} / {self.ServerData['ServerId']}", 1) # LOGINFO

                if self.ServerConnect(True):
                    self.start()
                    break

            utils.SyncPause[f"server_reconnecting_{self.ServerData['ServerId']}"] = False
            self.ServerReconnecting = False

        xbmc.log(f"EMBY.emby.emby: THREAD: ---<[ Reconnecting ] {self.ServerData['ServerName']} / {self.ServerData['ServerId']}", 1) # LOGINFO

    def start(self):
        xbmc.log(f"EMBY.emby.emby: ---[ START EMBYCLIENT: {self.ServerData['ServerName']} / {self.ServerData['ServerId']} / {self.ServerData['LastConnectionMode']}]---", 1) # LOGINFO
        utils.SyncPause[f"server_starting_{self.ServerData['ServerId']}"] = True
        utils.EmbyServers[self.ServerData['ServerId']] = self
        playerops.add_RemoteClientSelf(self.ServerData['ServerId'], self.EmbySession[0]['Id'], self.EmbySession[0]['DeviceName'], self.EmbySession[0]['UserName'])
        self.Views.update_views()
        self.library.load_settings()
        self.Views.update_nodes()
        self.toggle_websocket(True)
        start_new_thread(self.library.KodiStartSync, (self.Firstrun,))  # start initial sync
        self.Firstrun = False

        if utils.connectMsg:
            utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33000)} {self.ServerData['UserName']}", icon=self.ServerData['UserImageUrl'], time=1500, sound=False)

        utils.SyncPause[f"server_starting_{self.ServerData['ServerId']}"] = False
        xbmc.log("EMBY.emby.emby: [ Server Online ]", 1) # LOGINFO

    def stop(self):
        if self.EmbySession and not self.ShutdownInProgress:
            self.ShutdownInProgress = True
            xbmc.log(f"EMBY.emby.emby: ---[ STOP EMBYCLIENT: {self.ServerData['ServerId']} ]---", 1) # LOGINFO
            utils.SyncPause.update({f"server_starting_{self.ServerData['ServerId']}": True, f"server_busy_{self.ServerData['ServerId']}": False})
            playerops.delete_RemoteClient(self.ServerData['ServerId'], [self.EmbySession[0]['Id']], True, True)
            self.toggle_websocket(False)
            self.http.stop_session()
            self.EmbySession = []
            self.ShutdownInProgress = False
        else:
            xbmc.log("EMBY.emby.emby: Emby client already closed", 1) # LOGINFO

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
        xbmc.log("EMBY.emby.emby: --[ server/DEFAULT ]", 1) # LOGINFO

        # load credentials froom file
        if self.ServerSettings:
            FileData = utils.readFileString(self.ServerSettings)

            if FileData:
                LoadedServerSettings = json.loads(FileData)

                if 'ServerId' in LoadedServerSettings and LoadedServerSettings['ServerId']: # file content is not valid
                    self.ServerData = LoadedServerSettings

            utils.DatabaseFiles[self.ServerData['ServerId']] = utils.translatePath(f"special://profile/Database/emby_{self.ServerData['ServerId']}.db")

        # Refresh EmbyConnect Emby server addresses (dynamic IP)
        if self.ServerData["LastConnectionMode"] in ("EmbyConnectLocalAddress", "EmbyConnectRemoteAddress"):
            xbmc.log("EMBY.emby.emby: Refresh Emby server urls from EmbyConnect", 1) # LOGINFO
            request = {'type': "GET", 'url': f"https://connect.emby.media/service/servers?userId={self.ServerData['EmbyConnectUserId']}", 'headers': {'X-Connect-UserToken': self.ServerData['EmbyConnectAccessToken']}}
            result = self.request_url(request)

            if result:
                for server in result:
                    if server['SystemId'] == self.ServerData['ServerId']:
                        if self.ServerData['EmbyConnectRemoteAddress'] != server['Url'] or self.ServerData['EmbyConnectLocalAddress'] != server['LocalAddress']: # update server settings
                            self.ServerData.update({'EmbyConnectRemoteAddress': server['Url'], 'EmbyConnectLocalAddress': server['LocalAddress']})
                            self.save_credentials()
                            xbmc.log("EMBY.emby.emby: Update Emby server urls from EmbyConnect", 1) # LOGINFO

                        xbmc.log("EMBY.emby.emby: Refresh Emby server urls from EmbyConnect, found", 1) # LOGINFO
                        break

        if self.Firstrun:
            SignedIn = True
            self.ServerDetect()

            # Menu dialogs
            while True:
                if utils.SystemShutdown:
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
                    xbmc.log("EMBY.emby.emby: Adding manual server", 0) # LOGDEBUG
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
                self.save_credentials()
                self.start()
                return

        # re-establish connection
        start_new_thread(self.establish_existing_connection, ())

    def establish_existing_connection(self):
        xbmc.log("EMBY.emby.emby: THREAD: --->[ establish_existing_connection ]", 1) # LOGINFO

        if self.ServerConnect():
            self.start()

        xbmc.log("EMBY.emby.emby: THREAD: ---<[ establish_existing_connection ]", 1) # LOGINFO

    def save_credentials(self):
        if not self.ServerSettings:
            self.ServerSettings = f"{utils.FolderAddonUserdata}servers_{self.ServerData['ServerId']}.json"

        utils.writeFileString(self.ServerSettings, json.dumps(self.ServerData, sort_keys=True, indent=4, ensure_ascii=False))

    def ServerDisconnect(self):
        xbmc.log("EMBY.emby.emby: Disconnect", 1) # LOGINFO
        utils.EmbyServers[self.ServerData['ServerId']].API.session_logout()
        utils.EmbyServers[self.ServerData['ServerId']].stop()
        utils.delFile(f"{utils.FolderAddonUserdata}servers_{self.ServerData['ServerId']}.json")
        del utils.EmbyServers[self.ServerData['ServerId']]

    def ServerConnect(self, Reconnect=False):
        # Connect to server verification
        if self.ServerData["AccessToken"]:
            if self._try_connect(self.ServerData["ServerUrl"]):
                return True

            if not Reconnect and self.connect_to_server():
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
                xbmc.log("EMBY.emby.emby: User has password, present manual login", 0) # LOGDEBUG
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

        # Signed in with EmbyConnect user
        self.ServerData.update({'EmbyConnectUserId': result['User']['Id'], 'EmbyConnectUserName': result['User']['Name'], 'EmbyConnectAccessToken': result['AccessToken']})
        xbmc.log("EMBY.emby.emby: Begin getConnectServers", 0) # LOGDEBUG

        if self.ServerData['EmbyConnectAccessToken'] and self.ServerData['EmbyConnectUserId']:
            request = {'type': "GET", 'url': f"https://connect.emby.media/service/servers?userId={self.ServerData['EmbyConnectUserId']}", 'headers': {'X-Connect-UserToken': self.ServerData['EmbyConnectAccessToken']}}
            EmbyConnectServers = self.request_url(request)

            if EmbyConnectServers:
                for EmbyConnectServer in EmbyConnectServers:
                    self.Found_Servers.append({'ExchangeToken': EmbyConnectServer['AccessKey'], 'ConnectServerId': EmbyConnectServer['Id'], 'Id': EmbyConnectServer['SystemId'], 'Name': f"Emby Connect: {EmbyConnectServer['Name']}", 'RemoteAddress': EmbyConnectServer['Url'], 'LocalAddress': EmbyConnectServer['LocalAddress'], 'UserLinkType': "Guest" if EmbyConnectServer['UserType'].lower() == "guest" else "LinkedUser"})

        return result

    def ServerLogin(self, ServerUrl, username, password):
        xbmc.log("EMBY.emby.emby: Login to server", 1) # LOGINFO

        if not username:
            xbmc.log("EMBY.emby.emby: Username cannot be empty", 3) # LOGERROR
            return False

        # remove old access token and credential data file
        if self.ServerData['ServerId'] in utils.EmbyServers:
            self.ServerDisconnect()

        result = self.http.request({'type': "POST", 'url': f"{ServerUrl}/emby/Users/AuthenticateByName", 'params': {'username': username, 'pw': password or ""}}, True, False)

        if not result:
            return False

        self.ServerData.update({'UserId': result['User']['Id'], 'AccessToken': result['AccessToken']})
        return result

    def get_PublicInfo(self, address):
        PublicInfoUrl = f"{address}/emby/system/info/public"
        xbmc.log(f"EMBY.emby.emby: tryConnect url: {address}", 1) # LOGINFO
        return self.request_url({'type': "GET", 'url': PublicInfoUrl})

    def connect_to_address(self, address):
        if not address:
            return False

        address = normalize_address(address)
        PublicInfo = self.get_PublicInfo(address)

        if not PublicInfo:
            return False

        self.ServerData.update({'ManualAddress': address, 'LastConnectionMode': "ManualAddress", 'ServerName': PublicInfo['ServerName'], 'ServerId': PublicInfo['Id'], 'ServerUrl': address})
        xbmc.log(f"EMBY.emby.emby: ConnectToAddress {address} succeeded", 1) # LOGINFO
        return True

    def connect_to_server(self):
        xbmc.log("EMBY.emby.emby: Begin connectToServer", 0) # LOGDEBUG
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
            if utils.SystemShutdown:
                return False

            ConnectUrl = self.ServerData.get(Connection)

            if not ConnectUrl:
                xbmc.log(f"EMBY.emby.emby: Skip Emby server connection test: {Connection}", 1) # LOGINFO
                continue

            # Emby Connect
            if self.ServerData['EmbyConnectExchangeToken'] and self.ServerData['EmbyConnectUserId']:
                auth = self.request_url({'url': f"{ConnectUrl}/emby/Connect/Exchange", 'type': "GET", 'params': {'ConnectUserId': self.ServerData['EmbyConnectUserId']}, 'headers': {'X-Emby-Token': self.ServerData['EmbyConnectExchangeToken'], 'Authorization': f"Emby Client={utils.addon_name},Device={utils.device_name},DeviceId={utils.device_id},Version={utils.addon_version}"}})

                if auth:
                    self.ServerData.update({'UserId': auth['LocalUserId'], 'AccessToken': auth['AccessToken']})
                else:
                    self.ServerData.update({'UserId': "", 'AccessToken': ""})

            self.ServerData.update({'LastConnectionMode': Connection, 'ServerUrl': ConnectUrl})

            if not self._try_connect(ConnectUrl):
                continue

            return True

        xbmc.log("EMBY.emby.emby: Tested all connection modes. Failing server connection", 1) # LOGINFO
        return False

    def ServerDetect(self):
        xbmc.log("EMBY.emby.emby: Begin getAvailableServers", 0) # LOGDEBUG
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = b"who is EmbyServer?"
        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        sock.settimeout(1.0)  # This controls the socket.timeout exception
        sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_BROADCAST, 1)
        xbmc.log(f"EMBY.emby.emby: MultiGroup: {MULTI_GROUP}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.emby.emby: Sending UDP Data: {MESSAGE}", 0) # LOGDEBUG
        found_servers = []

        try:
            sock.sendto(MESSAGE, MULTI_GROUP)

            while True:
                try:
                    data, _ = sock.recvfrom(1024)  # buffer size
                    IncommingData = json.loads(data)

                    if IncommingData not in found_servers:
                        found_servers.append(IncommingData)
                except _socket.timeout:
                    xbmc.log(f"EMBY.emby.emby: Found Servers: {found_servers}", 1) # LOGINFO
                    break
                except Exception as Error:
                    xbmc.log(f"EMBY.emby.emby: Error trying to find servers: {Error}", 3) # LOGERROR
                    break
        except Exception as error:
            xbmc.log(f"EMBY.emby.emby: ERROR: {error}", 3) # LOGERROR

        self.Found_Servers = []

        for found_server in found_servers:
            server = ""

            if found_server.get('Address') and found_server.get('EndpointAddress'):
                address = found_server['EndpointAddress'].split(':')[0]
                # Determine the port, if any
                parts = found_server['Address'].split(':')

                if len(parts) > 1:
                    port_string = parts[len(parts) - 1]
                    address += f":{port_string}"
                    server = normalize_address(address)

            if not server and not found_server.get('Address'):
                xbmc.log(f"EMBY.emby.emby: Server {found_server} has no address", 2) # LOGWARNING
                continue

            self.Found_Servers.append({'Id': found_server['Id'], 'LocalAddress': server or found_server['Address'], 'Name': found_server['Name']})

    def request_url(self, request):
        request.setdefault('headers', {})
        request['headers'].update({'Accept': "application/json", 'Accept-Charset': "UTF-8,*", 'Accept-encoding': "gzip", 'X-Application': f"{utils.addon_name}/{utils.addon_version}", 'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        return self.http.request(request, True, False)

    def _try_connect(self, address):
        PublicInfo = self.get_PublicInfo(address)

        if PublicInfo:
            xbmc.log("EMBY.emby.emby: User is authenticated", 1) # LOGINFO
            self.ServerData.update({'RemoteAddress': PublicInfo.get('WanAddress', self.ServerData['RemoteAddress']), 'LocalAddress': PublicInfo.get('LocalAddress', self.ServerData['LocalAddress']), 'ServerName': PublicInfo.get('ServerName'), 'ServerId': PublicInfo.get('Id'), 'ServerUrl': address})
            utils.DatabaseFiles[self.ServerData['ServerId']] = utils.translatePath(f"special://profile/Database/emby_{self.ServerData['ServerId']}.db")

            if not self.ServerData.get('AccessToken', ""):
                return False

            self.EmbySession = self.API.get_device()

            if not self.EmbySession:
                xbmc.log(f"EMBY.emby.emby: ---[ SESSION ERROR EMBYCLIENT: {self.ServerData['ServerId']} ] {self.EmbySession} ---", 3) # LOGERROR
                return False

            if not self.ServerData['UserName']:
                self.ServerData['UserName'] = self.EmbySession[0]['UserName']

            self.API.post_capabilities({'Id': self.EmbySession[0]['Id'], 'SupportsRemoteControl': "true",'PlayableMediaTypes': "Audio,Video,Photo", 'SupportsMediaControl': True, 'SupportsSync': True, 'SupportedCommands': "MoveUp,MoveDown,MoveLeft,MoveRight,Select,Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,GoHome,PageUp,NextLetter,GoToSearch,GoToSettings,PageDown,PreviousLetter,TakeScreenshot,VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,SetAudioStreamIndex,SetSubtitleStreamIndex,SetRepeatMode,Mute,Unmute,SetVolume,Pause,Unpause,Play,Playstate,PlayNext,PlayMediaSource", 'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/plugin.video.emby/master/kodi_icon.png"})

            for AdditionalUserId in self.ServerData['AdditionalUsers']:
                AddUser = True

                for SessionAdditionalUser in self.EmbySession[0]['AdditionalUsers']:
                    if SessionAdditionalUser['UserId'] == AdditionalUserId:
                        AddUser = False
                        break

                if AddUser:
                    if utils.connectMsg:
                        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33067)} {self.ServerData['AdditionalUsers'][AdditionalUserId]}", icon=utils.icon, time=1500, sound=False)
                    self.API.session_add_user(self.EmbySession[0]['Id'], AdditionalUserId, True)

            if not self.ServerData['UserImageUrl']:
                self.ServerData['UserImageUrl'] = utils.icon

            return True

        return False

    def toggle_websocket(self, Enable):
        if Enable:
            if utils.websocketenabled and not self.Websocket:
                self.Websocket = websocket.WSClient(self)
                self.Websocket.start()
        else:
            if self.Websocket:
                self.Websocket.close()
                self.Websocket = None

def normalize_address(address):
    # Attempt to correct bad input
    address = address.strip()
    address = address.lower()

    if 'http' not in address:
        address = f"http://{address}"

    return address

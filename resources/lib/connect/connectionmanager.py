# -*- coding: utf-8 -*-

#################################################################################################

import hashlib
import json
import logging
import requests
import socket
from datetime import datetime

import credentials as cred
import connectservice

#################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

log = logging.getLogger("EMBY."+__name__)

#################################################################################################

ConnectionMode = {
    'Local': 0,
    'Remote': 1,
    'Manual': 2
}

def getServerAddress(server, mode):

    modes = {
        ConnectionMode['Local']: server.get('LocalAddress'),
        ConnectionMode['Remote']: server.get('RemoteAddress'),
        ConnectionMode['Manual']: server.get('ManualAddress')
    }
    return (modes.get(mode) or 
            server.get('ManualAddress',server.get('LocalAddress',server.get('RemoteAddress'))))   


class ConnectionManager(object):

    defaultTimeout = 20000


    def __init__(self, appName, appVersion, deviceName, deviceId,
            capabilities=None, devicePixelRatio=None):
        
        self.credentialProvider = cred.Credentials()
        self.appName = appName
        self.appVersion = appVersion
        self.deviceName = deviceName
        self.deviceId = deviceId
        self.capabilities = capabilities
        self.devicePixelRatio = devicePixelRatio

    def setFilePath(self, path):
        # Set where to save persistant data
        self.credentialProvider.set_path(path)

    def mergeServers(self, list1, list2):

        for i in range(0, len(list2), 1):
            self.credentialProvider.addOrUpdateServer(list1, list2[i])

        return list1

    def updateServerInfo(self, server, systemInfo):

        server['Name'] = systemInfo['ServerName']
        server['Id'] = systemInfo['Id']

        if systemInfo.get('LocalAddress'):
            server['LocalAddress'] = systemInfo['LocalAddress']
        if systemInfo.get('WanAddress'):
            server['RemoteAddress'] = systemInfo['WanAddress']
        if systemInfo.get('MacAddress'):
            server['WakeOnLanInfos'] = [{'MacAddress': systemInfo['MacAddress']}]

    def getHeaders(self, request):
        
        headers = request.setdefault('headers',{})

        if request['dataType'] == "json":
            headers['Accept'] = "application/json"

        headers['X-Application'] = self.addAppInfoToConnectRequest()
        headers['Content-type'] = request.get('contentType',
            'application/x-www-form-urlencoded; charset=UTF-8')

        return headers

    def requestUrl(self, request):

        # Response will contain a set, first value 0 - failed, reason why, value 1 - response

        if not request:
            print "Request cannot be null"
            return (0, "Request cannot be null")

        headers = self.getHeaders(request)
        url = request['url']
        timeout = request.get('timeout', self.defaultTimeout)
        verify = False
        print "ConnectionManager requesting url: %s" % url

        if request['type'] == "GET":
            response = requests.get(url, json=request.get('data'), params=request.get('params'),
                headers=headers, timeout=timeout, verify=verify)
        elif request['type'] == "POST":
            response = requests.post(url, data=request.get('data'),
                headers=headers, timeout=timeout, verify=verify)
            
        print "ConnectionManager response status: %s" % response.status_code

        try:
            if response.status_code == requests.codes.ok:
                try:
                    return (1, response.json())
                except requests.exceptions.ValueError:
                    return (1, response)
            else:
                response.raise_for_status()
        
        except Exception as e:
            print "ConnectionManager request failed: %s" % e
            return (0, e)

    def getEmbyServerUrl(self, baseUrl, handler):
        return "%s/emby/%s" % (baseUrl, handler)

    def getConnectUrl(self, handler):
        return "https://connect.emby.media/service/%s" % handler

    def findServers(self, foundServers):

        servers = []

        for foundServer in foundServers:

            server = self.convertEndpointAddressToManualAddress(foundServer)

            info = {
                'Id': foundServer['Id'],
                'LocalAddress': server or foundServer['Address'],
                'Name': foundServer['Name']
            }

            if info.get('ManualAddress'):
                info['LastConnectionMode'] = ConnectionMode['Manual']
            else:
                info['LastConnectionMode'] = ConnectionMode['Local']

            servers.append(info)
        else:
            return servers

    def convertEndpointAddressToManualAddress(self, info):
        
        if info.get('Address') and info.get('EndpointAddress'):
            address = info['EndpointAddress'].split(':')[0]

            # Determine the port, if any
            parts = info['Address'].split(':')
            if len(parts) > 1:
                portString = parts[len(parts)-1]

                try:
                    int(portString)
                    address += ":%s" % portString
                    return self.normalizeAddress(address)
                except ValueError:
                    pass

        return None

    def serverDiscovery(self):
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0) # This controls the socket.timeout exception

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        log.info("MultiGroup      : %s" % str(MULTI_GROUP))
        log.info("Sending UDP Data: %s" % MESSAGE)
        sock.sendto(MESSAGE, MULTI_GROUP)
        
        servers = []
        while True:
            try:
                data, addr = sock.recvfrom(1024) # buffer size
                servers.append(json.loads(data))
            
            except socket.timeout:
                log.info("Found Servers: %s" % servers)
                return servers
            
            except Exception as e:
                log.error("Error trying to find servers: %s" % e)
                return servers

    def normalizeAddress(self, address):
        # Attempt to correct bad input
        address = address.strip()
        address = address.lower()

        if 'http' not in address:
            address = "http://%s" % address

        return address

    def tryConnect(self, url, timeout=None):

        url = self.getEmbyServerUrl(url, "system/info/public")
        print "tryConnect url: %s" % url

        if timeout is None:
            timeout = defaultTimeout

        return self.requestUrl({
            'type': "GET",
            'url': url,
            'dataType': "json",
            'timeout': timeout
        })

    def addAppInfoToConnectRequest(self):
        return "%s/%s" % (self.appName, self.appVersion)

    def getConnectServers(self, credentials):

        print "Begin getConnectServers"
        servers = []

        if not credentials.get('ConnectAccessToken') or not credentials.get('ConnectUserId'):
            return servers

        # Dummy up - don't involve connect
        url = self.getConnectUrl("servers?userId=%s" % credentials['ConnectUserId'])
        request = {
            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {
                'X-Connect-UserToken': credentials['ConnectAccessToken']
            }
        }
        code, response = self.requestUrl(request)
        if code:
            for server in response:

                if server['UserType'].lower() == "guest":
                    userType = "Guest"
                else:
                    userType = "LinkedUser"

                servers.append({
                    'ExchangeToken': server['AccessKey'],
                    'ConnectServerId': server['Id'],
                    'Id': server['SystemId'],
                    'Name': server['Name'],
                    'RemoteAddress': server['Url'],
                    'LocalAddress': server['LocalAddress'],
                    'UserLinkType': userType
                })

        return servers

    def getAvailableServers(self):
        
        print "Begin getAvailableServers"

        # Clone the array
        credentials = self.credentialProvider.getCredentials()

        connectServers = self.getConnectServers(credentials)
        foundServers = self.findServers(self.serverDiscovery())

        servers = list(credentials['Servers'])
        self.mergeServers(servers, foundServers)
        self.mergeServers(servers, connectServers)

        servers = self.filterServers(servers, connectServers)

        credentials['Servers'] = servers
        self.credentialProvider.getCredentials(credentials)

        return servers

    def filterServers(self, servers, connectServers):
        
        filtered = []

        for server in servers:

            # It's not a connect server, so assume it's still valid
            if not server.get('ExchangeToken'):
                filtered.append(server)
                continue

            for connectServer in connectServers:
                if server['Id'] == connectServer['Id']:
                    filtered.append(server)
                    break
        else:
            return filtered

    def getConnectPasswordHash(self, password):

        password = connectservice.cleanPassword(password)
        
        return hashlib.md5(password).hexdigest()

    def saveUserInfoIntoCredentials(self, server, user):

        info = {
            'Id': user['Id'],
            'IsSignedInOffline': True
        }

        self.credentialProvider.addOrUpdateUser(server, info)

    def connectToServer(self, server, options):

        tests = []

        if server.get('LastConnectionMode'):
            #tests.append.(server['LastConnectionMode'])
            pass
        if ConnectionMode['Manual'] not in tests:
            tests.append(ConnectionMode['Manual'])
        if ConnectionMode['Local'] not in tests:
            tests.append(ConnectionMode['Local'])
        if ConnectionMode['Remote'] not in tests:
            tests.append(ConnectionMode['Remote'])

        wakeOnLanSendTime = datetime.now()

        if type(options) is not dict:
            options = {}

        self.testNextConnectionMode(tests, 0, server, wakeOnLanSendTime, options)

    def stringEqualsIgnoreCase(self, str1, str2):

        if type(str1) is not str: str1 = ""
        if type(str2) is not str: str2 = ""

        return str1.lower() == str2.lower()

    def testNextConnectionMode(self, tests, index, server, wakeOnLanSendTime, options):

        if index >= len(tests):
            print "Tested all connection modes. Failing server connection."
            return False

        mode = tests[index]
        address = getServerAddress(server, mode)
        enableRetry = False
        skipTest = False
        timeout = self.defaultTimeout

        if mode == ConnectionMode['Local']:
            enableRetry = True
            timeout = 8000

            if self.stringEqualsIgnoreCase(address, server['ManualAddress']):
                skipTest = True

        elif mode == ConnectionMode['Manual']:

            if self.stringEqualsIgnoreCase(address, server['LocalAddress']):
                enableRetry = True
                timeout = 8000

        if skipTest or not address:
            self.testNextConnectionMode(tests, index+1, server, wakeOnLanSendTime, options)
            return

        print "testing connection mode %s with server %s" % (mode, server['Name'])

        code, result = self.tryConnect(address, timeout)
        if code:
            print ("calling onSuccessfulConnection with connection mode %s with server %s"
                % (mode, server['Name']))
            self.onSuccessfulConnection(server, result, mode, options)
        else:
            print "test failed for connection mode %s with server %s" % (mode, server['Name'])

            if enableRetry:
                # TODO: Implement delay and retry
                sef.testNextConnectionMode(tests, index+1, server, wakeOnLanSendTime, options)
            else:
                sef.testNextConnectionMode(tests, index+1, server, wakeOnLanSendTime, options)

    def onSuccessfulConnection(self, server, systemInfo, connectionMode, options):
        # TODO
        credentials = self.credentialProvider.getCredentials()

    def afterConnectValidated(self, server, credentials, systemInfo, connectionMode,
            verifyLocalAuthentication, options):
        # TODO
        if options['enableAutoLogin'] == False:
            server['UserId'] = None
            server['AccessToken'] = None
        
        elif (verifyLocalAuthentication and server['AccessToken'] and 
            options['enableAutoLogin'] != False): pass

        self.updateServerInfo(server, systemInfo)
        server['LastConnectionMode'] = connectionMode

    def validateAuthentication(self, server, connectionMode):

        url = getServerAddress(server, connectionMode)
        request = {
            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {
                'X-MediaBrowser-Token': server['AccessToken']
            }
        }
        code, systemInfo = self.requestUrl(request)
        if code:
            
            self.updateServerInfo(server, systemInfo)

            if server.get('UserId'):
                code, user = self.requestUrl({
                    'type': "GET",
                    'url': self.getEmbyServerUrl(url, "users/%s" % server['UserId']),
                    'dataType': "json",
                    'headers': {
                        'X-MediaBrowser-Token': server['AccessToken']
                    }
                })
                # TODO onLocalUserSignIn
                return

        # Reset values
        server['UserId'] = None
        server['AccessToken'] = None
        return False

    def getImageUrl(self, localUser):

        pass

    def loginToConnect(self, username, password):

        if not username:
            return (0, "Username cannot be empty")

        if not password:
            return (0, "Password cannot be empty")

        md5 = self.getConnectPasswordHash(password)
        request = {
            'type': "POST",
            'url': self.getConnectUrl("user/authenticate"),
            'data': {
                'nameOrEmail': username,
                'password': md5
            },
            'dataType': "json"
        }
        code, result = self.requestUrl(request)
        if code:
            credentials = self.credentialProvider.getCredentials()
            credentials['ConnectAccessToken'] = result['AccessToken']
            credentials['ConnectUserId'] = result['User']['Id']
            self.credentialProvider.getCredentials(credentials)
            # Signed in
        
        return (code, result)

    def getConnectUser(self, userId, accessToken):

        if not userId:
            print "No userId"
            return

        if not accessToken:
            print "No accessToken"
            return

        url = self.getConnectUrl('user?id=%s' % userId)

        return self.requestUrl({
            'type': "GET",
            'url': url,
            'dateType': "json",
            'headers': {
                'X-Connect-UserToken': accessToken
            }
        })
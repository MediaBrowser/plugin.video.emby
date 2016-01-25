
"""
Taken from iBaa, https://github.com/iBaa/PlexConnect
Point of time: December 22, 2015


Collection of "connector functions" to Plex Media Server/MyPlex


PlexGDM:
loosely based on hippojay's plexGDM:
https://github.com/hippojay/script.plexbmc.helper... /resources/lib/plexgdm.py


Plex Media Server communication:
source (somewhat): https://github.com/hippojay/plugin.video.plexbmc
later converted from httplib to urllib2


Transcoder support:
PlexAPI_getTranscodePath() based on getTranscodeURL from pyplex/plexAPI
https://github.com/megawubs/pyplex/blob/master/plexAPI/info.py


MyPlex - Basic Authentication:
http://www.voidspace.org.uk/python/articles/urllib2.shtml
http://www.voidspace.org.uk/python/articles/authentication.shtml
http://stackoverflow.com/questions/2407126/python-urllib2-basic-auth-problem
http://stackoverflow.com/questions/111945/is-there-any-way-to-do-http-put-in-python
(and others...)
"""


# Specific to PlexDB:
import clientinfo
import utils
import downloadutils
import xbmcaddon
import xbmcgui
import xbmc

import struct
import time
import urllib2
import httplib
import socket
import StringIO
import gzip
from threading import Thread
import Queue
import traceback
import requests

import re
import json
from urllib import urlencode, quote_plus

try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree

# from Version import __VERSION__
# from Debug import *  # dprint(), prettyXML()


"""
storage for PMS addresses and additional information - now per aTV! (replaces global PMS_list)
syntax: PMS[<ATV_UDID>][PMS_UUID][<data>]
    data: name, ip, ...type (local, myplex)
"""


class PlexAPI():
    # CONSTANTS
    # Timeout for POST/GET commands, I guess in seconds
    timeout = 60
    # VARIABLES

    def __init__(self):
        self.__language__ = xbmcaddon.Addon().getLocalizedString
        self.g_PMS = {}
        client = clientinfo.ClientInfo()
        self.addonName = client.getAddonName()
        self.addonId = client.getAddonId()
        self.clientId = client.getDeviceId()
        self.deviceName = client.getDeviceName()
        self.plexversion = client.getVersion()
        self.platform = client.getPlatform()
        self.userId = utils.window('emby_currUser')
        self.token = utils.window('emby_accessToken%s' % self.userId)
        self.server = utils.window('emby_server%s' % self.userId)

        self.doUtils = downloadutils.DownloadUtils()

    def logMsg(self, msg, lvl=1):
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

    def GetPlexLoginFromSettings(self):
        """
        Returns empty strings if not found.

        myplexlogin is 'true' if user opted to log into plex.tv (the default)
        plexhome is 'true' if plex home is used (the default)
        """
        plexLogin = utils.settings('plexLogin')
        plexToken = utils.settings('plexToken')
        myplexlogin = utils.settings('myplexlogin')
        plexhome = utils.settings('plexhome')
        return (myplexlogin, plexhome, plexLogin, plexToken)

    def GetPlexLoginAndPassword(self):
        """
        Signs in to plex.tv.

        plexLogin, authtoken = GetPlexLoginAndPassword()

        Input: nothing
        Output:
            plexLogin       plex.tv username
            authtoken       token for plex.tv

        Also writes 'plexLogin' and 'token_plex.tv' to Kodi settings file
        If not logged in, empty strings are returned for both.
        """
        retrievedPlexLogin = ''
        plexLogin = 'dummy'
        authtoken = ''
        while retrievedPlexLogin == '' and plexLogin != '':
            dialog = xbmcgui.Dialog()
            plexLogin = dialog.input(
                self.addonName +
                ': Enter plex.tv username. Or nothing to cancel.',
                type=xbmcgui.INPUT_ALPHANUM,
            )
            if plexLogin != "":
                dialog = xbmcgui.Dialog()
                plexPassword = dialog.input(
                    'Enter password for plex.tv user %s' % plexLogin,
                    type=xbmcgui.INPUT_ALPHANUM,
                    option=xbmcgui.ALPHANUM_HIDE_INPUT
                )
                retrievedPlexLogin, authtoken = self.MyPlexSignIn(
                    plexLogin,
                    plexPassword,
                    {'X-Plex-Client-Identifier': self.clientId}
                )
                self.logMsg("plex.tv username and token: %s, %s"
                            % (plexLogin, authtoken), 1)
                if plexLogin == '':
                    dialog = xbmcgui.Dialog()
                    dialog.ok(self.addonName, 'Could not sign in user %s'
                              % plexLogin)
        # Write to Kodi settings file
        utils.settings('plexLogin', value=retrievedPlexLogin)
        utils.settings('plexToken', value=authtoken)
        return (retrievedPlexLogin, authtoken)

    def PlexTvSignInWithPin(self):
        """
        Prompts user to sign in by visiting https://plex.tv/pin

        Writes plexhome, username and token to Kodi settings file. Returns:
        {
            'plexhome':          'true' if Plex Home, 'false' otherwise
            'username':
            'avatar':            URL to user avator
            'token':
        }
        Returns False if authentication did not work.
        """
        code, identifier = self.GetPlexPin()
        dialog = xbmcgui.Dialog()
        if not code:
            dialog.ok(self.addonName,
                      'Problems trying to contact plex.tv',
                      'Try again later')
            return False
        answer = dialog.yesno(self.addonName,
                              'Go to https://plex.tv/pin and enter the code:',
                              '',
                              code)
        if not answer:
            return False
        count = 0
        # Wait for approx 30 seconds (since the PIN is not visible anymore :-))
        while count < 6:
            xml = self.CheckPlexTvSignin(identifier)
            if xml:
                break
            # Wait for 5 seconds
            xbmc.sleep(5000)
            count += 1
        if not xml:
            dialog.ok(self.addonName,
                      'Could not sign in to plex.tv',
                      'Try again later')
            return False
        # Parse xml
        home = xml.get('home', '0')
        if home == '1':
            home = 'true'
        else:
            home = 'false'
        username = xml.get('username', '')
        avatar = xml.get('thumb')
        token = xml.findtext('authentication-token')
        result = {
            'plexhome': home,
            'username': username,
            'avatar': avatar,
            'token': token
        }
        utils.settings('plexLogin', value=username)
        utils.settings('plexToken', value=token)
        utils.settings('plexhome', value=home)
        return result

    def CheckPlexTvSignin(self, identifier):
        """
        Checks with plex.tv whether user entered the correct PIN on plex.tv/pin

        Returns False if not yet done so, or the XML response file as etree
        """
        # Try to get a temporary token
        url = 'https://plex.tv/pins/%s.xml' % identifier
        xml = self.TalkToPlexServer(url, talkType="GET2")
        try:
            temp_token = xml.find('auth_token').text
        except:
            self.logMsg("Error: Could not find token in plex.tv answer.", -1)
            return False
        self.logMsg("temp token from plex.tv is: %s" % temp_token, 2)
        if not temp_token:
            return False
        # Use temp token to get the final plex credentials
        url = 'https://plex.tv/users/account?X-Plex-Token=%s' % temp_token
        xml = self.TalkToPlexServer(url, talkType="GET")
        return xml

    def GetPlexPin(self):
        """
        For plex.tv sign-in: returns 4-digit code and identifier as 2 str
        """
        url = 'https://plex.tv/pins.xml'
        code = None
        identifier = None
        # Download
        xml = self.TalkToPlexServer(url, talkType="POST")
        if not xml:
            return code, identifier
        try:
            code = xml.find('code').text
            identifier = xml.find('id').text
        except:
            self.logMsg("Error, no PIN from plex.tv provided", -1)
        self.logMsg("plex.tv/pin: Code is: %s" % code, 2)
        self.logMsg("plex.tv/pin: Identifier is: %s" % identifier, 2)
        return code, identifier

    def TalkToPlexServer(self, url, talkType="GET", verify=True, token=None):
        """
        Start request with PMS with url.

        Returns the parsed XML answer as an etree object.
        False if the server could not be reached/timeout occured.
        False if HTTP error code of >=400 was returned.
        """
        header = self.getXArgsDeviceInfo()
        if token:
            header['X-Plex-Token'] = token
        timeout = (3, 10)
        try:
            if talkType == "GET":
                answer = requests.get(url,
                                      headers={},
                                      params=header,
                                      verify=verify,
                                      timeout=timeout)
            # Only seems to be used for initial plex.tv sign in
            if talkType == "GET2":
                answer = requests.get(url,
                                      headers=header,
                                      params={},
                                      verify=verify,
                                      timeout=timeout)
            elif talkType == "POST":
                answer = requests.post(url,
                                       data='',
                                       headers=header,
                                       params={},
                                       verify=verify,
                                       timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            self.logMsg("Server is offline or cannot be reached. Url: %s."
                        "Header: %s. Error message: %s"
                        % (url, header, e), -1)
            return False
        except requests.exceptions.ReadTimeout:
            self.logMsg("Server timeout reached for Url %s with header %s"
                        % (url, header), -1)
            return False
        # We received an answer from the server, but not as expected.
        if answer.status_code >= 400:
            self.logMsg("Error, answer from server %s was not as expected. "
                        "HTTP status code: %s" % (url, answer.status_code), -1)
            return False
        xml = answer.text.encode('utf-8')
        self.logMsg("xml received from server %s: %s" % (url, xml), 2)
        try:
            xml = etree.fromstring(xml)
        except:
            self.logMsg("Error parsing XML answer from %s" % url, -1)
            return False
        return xml

    def CheckConnection(self, url, token):
        """
        Checks connection to a Plex server, available at url. Can also be used
        to check for connection with plex.tv.

        Input:
            url         URL to Plex server (e.g. https://192.168.1.1:32400)
            token       appropriate token to access server. If None is passed,
                        the current token is used
        Output:
            False       if server could not be reached or timeout occured
            e.g. 200    if connection was successfull
            int         or other HTML status codes as received from the server
        """
        # Add '/clients' to URL because then an authentication is necessary
        # If a plex.tv URL was passed, this does not work.
        header = self.getXArgsDeviceInfo()
        if token is not None:
            header['X-Plex-Token'] = token
        sslverify = utils.settings('sslverify')
        if sslverify == "true":
            sslverify = True
        else:
            sslverify = False
        self.logMsg("Checking connection to server %s with header %s and "
                    "sslverify=%s" % (url, header, sslverify), 1)
        timeout = (3, 10)
        if 'plex.tv' in url:
            url = 'https://plex.tv/api/home/users'
        else:
            url = url + '/library/onDeck'
        try:
            answer = requests.get(url,
                                  headers={},
                                  params=header,
                                  verify=sslverify,
                                  timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            self.logMsg("Server is offline or cannot be reached. Url: %s."
                        "Header: %s. Error message: %s"
                        % (url, header, e), -1)
            return False
        except requests.exceptions.ReadTimeout:
            self.logMsg("Server timeout reached for Url %s with header %s"
                        % (url, header), -1)
            return False
        result = answer.status_code
        self.logMsg("Result was: %s" % result, 1)
        return result

    def GetgPMSKeylist(self):
        """
        Returns a list of all keys that are saved for every entry in the
        g_PMS variable. 
        """
        keylist = [
            'address',
            'baseURL',
            'enableGzip',
            'ip',
            'local',
            'name',
            'owned',
            'port',
            'scheme'
        ]
        return keylist

    def setgPMSToSettings(self, g_PMS):
        """
        PlexDB: takes an g_PMS list of Plex servers and saves them all to
        the Kodi settings file. It does NOT save the ATV_udid as that id
        seems to change with reboot. Settings are set using the Plex server
        machineIdentifier.

        Input:
            g_PMS

        Output:

        Assumptions:
            There is only one ATV_udid in g_PMS

        Existing entries for servers with the same ID get overwritten.
        New entries get added. Serverinfo already set in file are set to ''.

        NOTE: it is currently not possible to delete entries in Kodi settings
        file!
        """
        addon = xbmcaddon.Addon()
        # Get rid of uppermost level ATV_udid in g_PMS
        ATV_udid = list(g_PMS.keys())[0]
        g_PMS = g_PMS[ATV_udid]

        serverlist = []
        keylist = self.getgPMSKeylist()
        for serverid, servervalues in g_PMS.items():
            serverlist.append(serverid)
            # Set values in Kodi settings file
            for item in keylist:
                # Append the server's ID first, then immediatelly the setting
                addon.setSetting(
                    str(serverid) + str(item),      # the key
                    str(g_PMS[serverid][item])      # the value
                )
        # Write a new or updated 'serverlist' string to settings
        oldserverlist = addon.getSetting('serverlist')
        # If no server has been saved yet, return
        if oldserverlist == '':
            serverlist = ','.join(serverlist)
            addon.setSetting('serverlist', serverlist)
            return
        oldserverlist = oldserverlist.split(',')
        for server in oldserverlist:
            # Delete serverinfo that has NOT been passed in serverlist
            if server not in serverlist:
                # Set old value to '', because deleting is not possible
                for item in keylist:
                    addon.setSetting(str(server) + str(item), '')
        serverlist = ','.join(serverlist)
        addon.setSetting('serverlist', serverlist)
        return

    def declarePMS(self, ATV_udid, uuid, name, scheme, ip, port):
        """
        Plex Media Server handling

        parameters:
            ATV_udid
            uuid - PMS ID
            name, scheme, ip, port, type, owned, token
        """
        # store PMS information in g_PMS database
        if ATV_udid not in self.g_PMS:
            self.g_PMS[ATV_udid] = {}

        address = ip + ':' + port
        baseURL = scheme+'://'+ip+':'+port
        self.g_PMS[ATV_udid][uuid] = { 'name': name,
                                  'scheme':scheme, 'ip': ip , 'port': port,
                                  'address': address,
                                  'baseURL': baseURL,
                                  'local': '1',
                                  'owned': '1',
                                  'accesstoken': '',
                                  'enableGzip': False
                                }

    def updatePMSProperty(self, ATV_udid, uuid, tag, value):
        # set property element of PMS by UUID
        if not ATV_udid in self.g_PMS:
            return ''  # no server known for this aTV
        if not uuid in self.g_PMS[ATV_udid]:
            return ''  # requested PMS not available
        
        self.g_PMS[ATV_udid][uuid][tag] = value

    def getPMSProperty(self, ATV_udid, uuid, tag):
        # get name of PMS by UUID
        if not ATV_udid in self.g_PMS:
            return ''  # no server known for this aTV
        if not uuid in self.g_PMS[ATV_udid]:
            return ''  # requested PMS not available
        
        return self.g_PMS[ATV_udid][uuid].get(tag, '')

    def getPMSFromAddress(self, ATV_udid, address):
        # find PMS by IP, return UUID
        if not ATV_udid in self.g_PMS:
            return ''  # no server known for this aTV
        
        for uuid in self.g_PMS[ATV_udid]:
            if address in self.g_PMS[ATV_udid][uuid].get('address', None):
                return uuid
        return ''  # IP not found

    def getPMSAddress(self, ATV_udid, uuid, data):
        # get address of PMS by UUID
        if not ATV_udid in data:
            return ''  # no server known for this aTV
        if not uuid in data[ATV_udid]:
            return ''  # requested PMS not available
        return data[ATV_udid][uuid]['ip'] + ':' + data[ATV_udid][uuid]['port']

    def getPMSCount(self, ATV_udid):
        # get count of discovered PMS by UUID
        if not ATV_udid in self.g_PMS:
            return 0  # no server known for this aTV
        
        return len(self.g_PMS[ATV_udid])

    def PlexGDM(self):
        """
        PlexGDM

        parameters:
            none
        result:
            PMS_list - dict() of PMSs found
        """
        IP_PlexGDM = '239.0.0.250'  # multicast to PMS
        Port_PlexGDM = 32414
        Msg_PlexGDM = 'M-SEARCH * HTTP/1.0'
        # dprint(__name__, 0, "***")
        # dprint(__name__, 0, "PlexGDM - looking up Plex Media Server")
        # dprint(__name__, 0, "***")
        
        # setup socket for discovery -> multicast message
        GDM = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        GDM.settimeout(1.0)
        
        # Set the time-to-live for messages to 1 for local network
        ttl = struct.pack('b', 1)
        GDM.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        
        returnData = []
        try:
            # Send data to the multicast group
            # dprint(__name__, 1, "Sending discovery message: {0}", Msg_PlexGDM)
            GDM.sendto(Msg_PlexGDM, (IP_PlexGDM, Port_PlexGDM))

            # Look for responses from all recipients
            while True:
                try:
                    data, server = GDM.recvfrom(1024)
                    # dprint(__name__, 1, "Received data from {0}", server)
                    # dprint(__name__, 1, "Data received:\n {0}", data)
                    returnData.append( { 'from' : server,
                                         'data' : data } )
                except socket.timeout:
                    break
        finally:
            GDM.close()

        discovery_complete = True

        PMS_list = {}
        if returnData:
            for response in returnData:
                update = { 'ip' : response.get('from')[0] }
                
                # Check if we had a positive HTTP response                        
                if "200 OK" in response.get('data'):
                    for each in response.get('data').split('\n'): 
                        # decode response data
                        update['discovery'] = "auto"
                        #update['owned']='1'
                        #update['master']= 1
                        #update['role']='master'
                        
                        if "Content-Type:" in each:
                            update['content-type'] = each.split(':')[1].strip()
                        elif "Resource-Identifier:" in each:
                            update['uuid'] = each.split(':')[1].strip()
                        elif "Name:" in each:
                            update['serverName'] = each.split(':')[1].strip().decode('utf-8', 'replace')  # store in utf-8
                        elif "Port:" in each:
                            update['port'] = each.split(':')[1].strip()
                        elif "Updated-At:" in each:
                            update['updated'] = each.split(':')[1].strip()
                        elif "Version:" in each:
                            update['version'] = each.split(':')[1].strip()
                
                PMS_list[update['uuid']] = update
        
        # if PMS_list=={}:
        #     dprint(__name__, 0, "GDM: No servers discovered")
        # else:
        #     dprint(__name__, 0, "GDM: Servers discovered: {0}", len(PMS_list))
        #     for uuid in PMS_list:
        #         dprint(__name__, 1, "{0} {1}:{2}", PMS_list[uuid]['serverName'], PMS_list[uuid]['ip'], PMS_list[uuid]['port'])
        
        return PMS_list

    def discoverPMS(self, ATV_udid, CSettings, IP_self, tokenDict={}):
        """
        discoverPMS

        parameters:
            ATV_udid
            CSettings - for manual PMS configuration. this one looks strange.
            IP_self
        optional:
            tokenDict - dictionary of tokens for MyPlex, PlexHome
        result:
            self.g_PMS dictionary for ATV_udid
        """
        self.g_PMS[ATV_udid] = {}

        # install plex.tv "virtual" PMS - for myPlex, PlexHome
        self.declarePMS(ATV_udid, 'plex.tv', 'plex.tv', 'https', 'plex.tv', '443')
        self.updatePMSProperty(ATV_udid, 'plex.tv', 'local', '-')
        self.updatePMSProperty(ATV_udid, 'plex.tv', 'owned', '-')
        self.updatePMSProperty(ATV_udid, 'plex.tv', 'accesstoken', tokenDict.get('MyPlexToken', ''))

        if 'PlexHomeToken' in tokenDict:
            authtoken = tokenDict.get('PlexHomeToken')
        else:
            authtoken = tokenDict.get('MyPlexToken', '')

        if authtoken == '':
            # not logged into myPlex
            # local PMS
            # PlexGDM
            PMS_list = self.PlexGDM()
            for uuid_id in PMS_list:
                PMS = PMS_list[uuid_id]
                self.declarePMS(ATV_udid, PMS['uuid'], PMS['serverName'], 'http', PMS['ip'], PMS['port'])  # dflt: token='', local, owned
        else:
            # MyPlex servers
            self.getPMSListFromMyPlex(ATV_udid, authtoken)
        # all servers - update enableGzip
        for uuid_id in self.g_PMS.get(ATV_udid, {}):
            # enable Gzip if not on same host, local&remote PMS depending
            # on setting
            enableGzip = (not self.getPMSProperty(ATV_udid, uuid_id, 'ip') == IP_self) \
                and (
                    (self.getPMSProperty(ATV_udid, uuid_id, 'local') == '1'
                        and False)
                    or
                    (self.getPMSProperty(ATV_udid, uuid_id, 'local') == '0'
                        and True) == 'True'
                )
            self.updatePMSProperty(ATV_udid, uuid_id, 'enableGzip', enableGzip)
        # Delete plex.tv again
        del self.g_PMS[ATV_udid]['plex.tv']

    def getPMSListFromMyPlex(self, ATV_udid, authtoken):
        """
        getPMSListFromMyPlex

        get Plex media Server List from plex.tv/pms/resources
        """
        # dprint(__name__, 0, "***")
        # dprint(__name__, 0, "poke plex.tv - request Plex Media Server list")
        # dprint(__name__, 0, "***")
        XML = self.getXMLFromPMS('https://plex.tv', '/api/resources?includeHttps=1', {}, authtoken)
        if XML==False:
            pass  # no data from MyPlex
        else:
            queue = Queue.Queue()
            threads = []
            
            for Dir in XML.getiterator('Device'):
                if Dir.get('product','') == "Plex Media Server" and Dir.get('provides','') == "server":
                    uuid = Dir.get('clientIdentifier')
                    name = Dir.get('name')
                    token = Dir.get('accessToken', authtoken)
                    owned = Dir.get('owned', '0')
                    local = Dir.get('publicAddressMatches')
                    
                    if Dir.find('Connection') == None:
                        continue  # no valid connection - skip
                    
                    uri = ""  # flag to set first connection, possibly overwrite later with more suitable
                    for Con in Dir.getiterator('Connection'):
                        if uri=="" or Con.get('local','') == local:
                            protocol = Con.get('protocol')
                            ip = Con.get('address')
                            port = Con.get('port')
                            uri = Con.get('uri')
                        # todo: handle unforeseen - like we get multiple suitable connections. how to choose one?
                    
                    # check MyPlex data age - skip if >1 days
                    infoAge = time.time() - int(Dir.get('lastSeenAt'))
                    oneDayInSec = 60*60*24
                    if infoAge > 1*oneDayInSec:
                        self.logMsg("Server %s not updated for 1 day - "
                                    "skipping." % name, 0)
                        continue

                    # poke PMS, own thread for each poke
                    PMSInfo = { 'uuid': uuid, 'name': name, 'token': token, 'owned': owned, 'local': local, \
                            'protocol': protocol, 'ip': ip, 'port': port, 'uri': uri }
                    PMS = { 'baseURL': uri, 'path': '/', 'options': None, 'token': token, \
                            'data': PMSInfo }
                    t = Thread(target=self.getXMLFromPMSToQueue, args=(PMS, queue))
                    t.start()
                    threads.append(t)
                
                # wait for requests being answered
                for t in threads:
                    t.join()
                
                # declare new PMSs
                while not queue.empty():
                        (PMSInfo, PMS) = queue.get()
                        
                        if PMS==False:
                            continue
                        
                        uuid = PMSInfo['uuid']
                        name = PMSInfo['name']
                        token = PMSInfo['token']
                        owned = PMSInfo['owned']
                        local = PMSInfo['local']
                        protocol = PMSInfo['protocol']
                        ip = PMSInfo['ip']
                        port = PMSInfo['port']
                        uri = PMSInfo['uri']
                        
                        self.declarePMS(ATV_udid, uuid, name, protocol, ip, port)  # dflt: token='', local, owned - updated later
                        self.updatePMSProperty(ATV_udid, uuid, 'accesstoken', token)
                        self.updatePMSProperty(ATV_udid, uuid, 'owned', owned)
                        self.updatePMSProperty(ATV_udid, uuid, 'local', local)
                        self.updatePMSProperty(ATV_udid, uuid, 'baseURL', uri)  # set in declarePMS, overwrite for https encryption

    def getXMLFromPMS(self, baseURL, path, options={}, authtoken='', enableGzip=False):
        """
        Plex Media Server communication

        parameters:
            host
            path
            options - dict() of PlexConnect-options as received from aTV
                None for no
                std. X-Plex-Args
            authtoken - authentication answer from MyPlex Sign In
        result:
            returned XML or 'False' in case of error
        """
        xargs = {}
        if options is not None:
            xargs = self.getXArgsDeviceInfo(options)
        if not authtoken == '':
            xargs['X-Plex-Token'] = authtoken

        self.logMsg("URL for XML download: %s%s" % (baseURL, path), 1)
        self.logMsg("xargs: %s" % xargs, 1)

        request = urllib2.Request(baseURL+path, None, xargs)
        request.add_header('User-agent', 'PlexDB')
        if enableGzip:
            request.add_header('Accept-encoding', 'gzip')

        try:
            response = urllib2.urlopen(request, timeout=20)
        except (urllib2.URLError, httplib.HTTPException) as e:
            self.logMsg("No Response from Plex Media Server", 0)
            if hasattr(e, 'reason'):
                self.logMsg("We failed to reach a server. Reason: %s" % e.reason, 0)
            elif hasattr(e, 'code'):
                self.logMsg("The server couldn't fulfill the request. Error code: %s" % e.code, 0)
            self.logMsg("Traceback:\n%s" % traceback.format_exc(), 0)
            return False
        except IOError:
            self.logMsg("Error loading response XML from Plex Media Server:\n%s" % traceback.format_exc(), 0)
            return False

        if response.info().get('Content-Encoding') == 'gzip':
            buf = StringIO.StringIO(response.read())
            file = gzip.GzipFile(fileobj=buf)
            XML = etree.parse(file)
        else:
            # parse into etree
            XML = etree.parse(response)
        # Log received XML if debugging enabled.
        self.logMsg("====== received PMS-XML ======", 1)
        self.logMsg(XML.getroot(), 1)
        self.logMsg("====== PMS-XML finished ======", 1)
        return XML

    def getXMLFromPMSToQueue(self, PMS, queue):
        XML = self.getXMLFromPMS(PMS['baseURL'],PMS['path'],PMS['options'],PMS['token'])
        queue.put( (PMS['data'], XML) )

    def getXArgsDeviceInfo(self, options={}, JSON=False):
        """
        Returns a dictionary that can be used as headers for GET and POST
        requests. An authentication option is NOT yet added.

        Inputs:
            JSON=True       will enforce a JSON answer
            options:        dictionary of options that will override the
                            standard header options otherwise set.
        Output:
            header dictionary
        """
        # Get addon infos
        xargs = {
            "Content-type": "application/x-www-form-urlencoded",
            "Access-Control-Allow-Origin": "*",
            'X-Plex-Language': 'en',
            'X-Plex-Device': self.addonName,
            'X-Plex-Client-Platform': self.platform,
            'X-Plex-Device-Name': self.deviceName,
            'X-Plex-Platform': self.addonName,
            'X-Plex-Platform-Version': 'unknown',
            'X-Plex-Model': 'unknown',
            'X-Plex-Product': self.addonName,
            'X-Plex-Version': self.plexversion,
            'X-Plex-Client-Identifier': self.clientId,
            'X-Plex-Provides': 'player',
        }

        if self.token:
            xargs['X-Plex-Token'] = self.token
        if JSON:
            xargs['Accept'] = 'application/json'
        if options:
            xargs.update(options)
        return xargs

    def getXMLFromMultiplePMS(self, ATV_udid, path, type, options={}):
        """
        provide combined XML representation of local servers' XMLs, eg. /library/section

        parameters:
            ATV_udid
            path
            type - owned <> shared (previously: local, myplex)
            options
        result:
            XML
        """
        queue = Queue.Queue()
        threads = []
        
        root = etree.Element("MediaConverter")
        root.set('friendlyName', type+' Servers')
        
        for uuid in g_PMS.get(ATV_udid, {}):
            if (type=='all' and getPMSProperty(ATV_udid, uuid, 'name')!='plex.tv') or \
               (type=='owned' and getPMSProperty(ATV_udid, uuid, 'owned')=='1') or \
               (type=='shared' and getPMSProperty(ATV_udid, uuid, 'owned')=='0') or \
               (type=='local' and getPMSProperty(ATV_udid, uuid, 'local')=='1') or \
               (type=='remote' and getPMSProperty(ATV_udid, uuid, 'local')=='0'):
                Server = etree.SubElement(root, 'Server')  # create "Server" node
                Server.set('name',    getPMSProperty(ATV_udid, uuid, 'name'))
                Server.set('address', getPMSProperty(ATV_udid, uuid, 'ip'))
                Server.set('port',    getPMSProperty(ATV_udid, uuid, 'port'))
                Server.set('baseURL', getPMSProperty(ATV_udid, uuid, 'baseURL'))
                Server.set('local',   getPMSProperty(ATV_udid, uuid, 'local'))
                Server.set('owned',   getPMSProperty(ATV_udid, uuid, 'owned'))
                
                baseURL = getPMSProperty(ATV_udid, uuid, 'baseURL')
                token = getPMSProperty(ATV_udid, uuid, 'accesstoken')
                PMS_mark = 'PMS(' + getPMSProperty(ATV_udid, uuid, 'address') + ')'
                
                Server.set('searchKey', PMS_mark + getURL('', '', '/Search/Entry.xml'))
                
                # request XMLs, one thread for each
                PMS = { 'baseURL':baseURL, 'path':path, 'options':options, 'token':token, \
                        'data': {'uuid': uuid, 'Server': Server} }
                t = Thread(target=getXMLFromPMSToQueue, args=(PMS, queue))
                t.start()
                threads.append(t)
        
        # wait for requests being answered
        for t in threads:
            t.join()
        
        # add new data to root XML, individual Server
        while not queue.empty():
                (data, XML) = queue.get()
                uuid = data['uuid']
                Server = data['Server']
                
                baseURL = getPMSProperty(ATV_udid, uuid, 'baseURL')
                token = getPMSProperty(ATV_udid, uuid, 'accesstoken')
                PMS_mark = 'PMS(' + getPMSProperty(ATV_udid, uuid, 'address') + ')'
                
                if XML==False:
                    Server.set('size',    '0')
                else:
                    Server.set('size',    XML.getroot().get('size', '0'))
                    
                    for Dir in XML.getiterator('Directory'):  # copy "Directory" content, add PMS to links
                        key = Dir.get('key')  # absolute path
                        Dir.set('key',    PMS_mark + getURL('', path, key))
                        Dir.set('refreshKey', getURL(baseURL, path, key) + '/refresh')
                        if 'thumb' in Dir.attrib:
                            Dir.set('thumb',  PMS_mark + getURL('', path, Dir.get('thumb')))
                        if 'art' in Dir.attrib:
                            Dir.set('art',    PMS_mark + getURL('', path, Dir.get('art')))
                        Server.append(Dir)
                    
                    for Playlist in XML.getiterator('Playlist'):  # copy "Playlist" content, add PMS to links
                        key = Playlist.get('key')  # absolute path
                        Playlist.set('key',    PMS_mark + getURL('', path, key))
                        if 'composite' in Playlist.attrib:
                            Playlist.set('composite', PMS_mark + getURL('', path, Playlist.get('composite')))
                        Server.append(Playlist)
                    
                    for Video in XML.getiterator('Video'):  # copy "Video" content, add PMS to links
                        key = Video.get('key')  # absolute path
                        Video.set('key',    PMS_mark + getURL('', path, key))
                        if 'thumb' in Video.attrib:
                            Video.set('thumb', PMS_mark + getURL('', path, Video.get('thumb')))
                        if 'parentKey' in Video.attrib:
                            Video.set('parentKey', PMS_mark + getURL('', path, Video.get('parentKey')))
                        if 'parentThumb' in Video.attrib:
                            Video.set('parentThumb', PMS_mark + getURL('', path, Video.get('parentThumb')))
                        if 'grandparentKey' in Video.attrib:
                            Video.set('grandparentKey', PMS_mark + getURL('', path, Video.get('grandparentKey')))
                        if 'grandparentThumb' in Video.attrib:
                            Video.set('grandparentThumb', PMS_mark + getURL('', path, Video.get('grandparentThumb')))
                        Server.append(Video)
        
        root.set('size', str(len(root.findall('Server'))))
        
        XML = etree.ElementTree(root)
        
        dprint(__name__, 1, "====== Local Server/Sections XML ======")
        dprint(__name__, 1, XML.getroot())
        dprint(__name__, 1, "====== Local Server/Sections XML finished ======")
        
        return XML  # XML representation - created "just in time". Do we need to cache it?

    def getURL(self, baseURL, path, key):
        if key.startswith('http://') or key.startswith('https://'):  # external server
            URL = key
        elif key.startswith('/'):  # internal full path.
            URL = baseURL + key
        elif key == '':  # internal path
            URL = baseURL + path
        else:  # internal path, add-on
            URL = baseURL + path + '/' + key
        
        return URL

    def MyPlexSignIn(self, username, password, options):
        """
        MyPlex Sign In, Sign Out

        parameters:
            username - Plex forum name, MyPlex login, or email address
            password
            options - dict() of PlexConnect-options as received from aTV - necessary: PlexConnectUDID
        result:
            username
            authtoken - token for subsequent communication with MyPlex
        """
        # MyPlex web address
        MyPlexHost = 'plex.tv'
        MyPlexSignInPath = '/users/sign_in.xml'
        MyPlexURL = 'https://' + MyPlexHost + MyPlexSignInPath

        # create POST request
        xargs = self.getXArgsDeviceInfo(options)
        self.logMsg("Header is: %s" % xargs, 1)
        request = urllib2.Request(MyPlexURL, None, xargs)
        request.get_method = lambda: 'POST'
        # turn into 'POST'
        # done automatically with data!=None. But we don't have data.

        # no certificate, will fail with "401 - Authentification required"
        """
        try:
            f = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            print e.headers
            print "has WWW_Authenticate:", e.headers.has_key('WWW-Authenticate')
            print
        """

        # provide credentials
        ### optional... when 'realm' is unknown
        ##passmanager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        ##passmanager.add_password(None, address, username, password)  # None: default "realm"
        passmanager = urllib2.HTTPPasswordMgr()
        passmanager.add_password(MyPlexHost, MyPlexURL, username, password)
        authhandler = urllib2.HTTPBasicAuthHandler(passmanager)
        urlopener = urllib2.build_opener(authhandler)
        
        # sign in, get MyPlex response
        try:
            response = urlopener.open(request).read()
        except urllib2.HTTPError as e:
            if e.code == 401:
                self.logMsg("Authentication failed", 0)
                return ('', '')
            else:
                raise
        # analyse response
        XMLTree = etree.ElementTree(etree.fromstring(response))

        el_username = XMLTree.find('username')
        el_authtoken = XMLTree.find('authentication-token')
        if el_username is None or \
           el_authtoken is None:
            username = ''
            authtoken = ''
        else:
            username = el_username.text
            authtoken = el_authtoken.text
        return (username, authtoken)

    def MyPlexSignOut(self, authtoken):
        # MyPlex web address
        MyPlexHost = 'plex.tv'
        MyPlexSignOutPath = '/users/sign_out.xml'
        MyPlexURL = 'http://' + MyPlexHost + MyPlexSignOutPath
        
        # create POST request
        xargs = { 'X-Plex-Token': authtoken }
        request = urllib2.Request(MyPlexURL, None, xargs)
        request.get_method = lambda: 'POST'  # turn into 'POST' - done automatically with data!=None. But we don't have data.
        
        response = urllib2.urlopen(request).read()
        
        dprint(__name__, 1, "====== MyPlex sign out XML ======")
        dprint(__name__, 1, response)
        dprint(__name__, 1, "====== MyPlex sign out XML finished ======")
        dprint(__name__, 0, 'MyPlex Sign Out done')

    def GetUserArtworkURL(self, username):
        """
        Returns the URL for the user's Avatar. Or False if something went
        wrong.
        """
        plexToken = utils.settings('plexToken')
        users = self.MyPlexListHomeUsers(plexToken)
        url = ''
        # If an error is encountered, set to False
        if not users:
            self.logMsg("Could not get userlist from plex.tv.", 1)
            self.logMsg("No URL for user avatar.", 1)
            return False
        for user in users:
            if username in user['title']:
                url = user['thumb']
        self.logMsg("Avatar url for user %s is: %s" % (username, url), 1)
        return url

    def ChoosePlexHomeUser(self):
        """
        Let's user choose from a list of Plex home users. Will switch to that
        user accordingly.

        Output:
            username
            userid
            authtoken

        Will return empty strings if failed.
        """
        plexLogin = utils.settings('plexLogin')
        plexToken = utils.settings('plexToken')
        machineIdentifier = utils.settings('plex_machineIdentifier')
        self.logMsg("Getting user list.", 1)
        # Get list of Plex home users
        users = self.MyPlexListHomeUsers(plexToken)
        # Download users failed. Set username to Plex login
        if not users:
            utils.settings('username', value=plexLogin)
            self.logMsg("User download failed. Set username = plexlogin", 0)
            return ('', '', '')

        userlist = []
        for user in users:
            username = user['title']
            userlist.append(username)
        usernumber = len(userlist)
        usertoken = ''
        # Plex home not in use: only 1 user returned
        trials = 0
        while trials < 3:
            if usernumber > 1:
                dialog = xbmcgui.Dialog()
                user_select = dialog.select(self.addonName + ": Select User",
                                            userlist)
                if user_select == -1:
                    self.logMsg("No user selected.", 1)
                    xbmc.executebuiltin('Addon.OpenSettings(%s)'
                                        % self.addonId)
                    return ('', '', '')
            # No Plex home in use - only 1 user
            else:
                user_select = 0
            selected_user = userlist[user_select]
            self.logMsg("Selected user: %s" % selected_user, 1)
            utils.settings('username', value=selected_user)
            user = users[user_select]
            # Ask for PIN, if protected:
            if user['protected'] == '1':
                dialog = xbmcgui.Dialog()
                pin = dialog.input(
                    'Enter PIN for user %s' % selected_user,
                    type=xbmcgui.INPUT_NUMERIC,
                    option=xbmcgui.ALPHANUM_HIDE_INPUT
                )
            else:
                pin = None
            # Switch to this Plex Home user, if applicable
            username, usertoken = self.PlexSwitchHomeUser(
                user['id'],
                pin,
                plexToken,
                machineIdentifier
            )
            # Couldn't get user auth
            if not username:
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    self.addonName,
                    'Could not log in user %s' % selected_user,
                    'Please try again.'
                )
            # Successfully retrieved: break out of while loop
            else:
                break
            trials += trials
        if not username:
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return ('', '', '', '')
        return (username, user['id'], usertoken)

    def PlexSwitchHomeUser(self, userId, pin, token, machineId):
        """
        Retrieves Plex home token for a Plex home user.

        Input:
            userId          id of the Plex home user
            pin             PIN of the Plex home user, if protected
            token           token for plex.tv
            machineId       Plex PMS machineIdentifier

        Output:
            (username, token)

        Returns 2 empty strings if unsuccessful
        """
        url = 'https://plex.tv/api/home/users/' + userId + '/switch'
        if pin:
            url += '?pin=' + pin
        self.logMsg('Switching to user %s with url %s and machineId %s'
                    % (userId, url, machineId), 0)
        answer = self.TalkToPlexServer(url, talkType="POST", token=token)
        if not answer:
            self.logMsg('Error: plex.tv switch HomeUser change failed', -1)
            return ('', '')

        username = answer.attrib.get('title', '')
        token = answer.attrib.get('authenticationToken', '')

        # Get final token
        url = 'https://plex.tv/pms/servers.xml'
        answer = self.TalkToPlexServer(url, talkType="GET", token=token)
        if not answer:
            self.logMsg('Error: plex.tv switch HomeUser change failed', -1)
            return ('', '')

        found = 0
        for child in answer:
            if child.attrib['machineIdentifier'] == machineId:
                token = child.attrib['accessToken']
                self.logMsg('Found a plex home user token', 1)
                found += 1
        if found == 0:
            self.logMsg('Error: plex.tv switch HomeUser change failed', -1)
            return ('', '')
        self.logMsg('Plex.tv switch HomeUser change successfull', 0)
        self.logMsg('username: %s, token: xxxx' % username, 0)
        return (username, token)

    def MyPlexListHomeUsers(self, authtoken):
        """
        Returns a list for myPlex home users for the current plex.tv account.

        Input:
            authtoken for plex.tv
        Output:
            List of users, where one entry is of the form:
                "id": userId,
                "admin": '1'/'0',
                "guest": '1'/'0',
                "restricted": '1'/'0',
                "protected": '1'/'0',
                "email": email,
                "title": title,
                "username": username,
                "thumb": thumb_url
            }
        If any value is missing, None is returned instead (or "" from plex.tv)
        If an error is encountered, False is returned
        """
        XML = self.getXMLFromPMS('https://plex.tv', '/api/home/users/', {}, authtoken)
        if not XML:
            # Download failed; quitting with False
            return False
        # analyse response
        root = XML.getroot()
        users = []
        for user in root:
            users.append(user.attrib)
        return users

    def getDirectVideoPath(self, key, AuthToken):
        """
        Direct Video Play support

        parameters:
            path
            AuthToken
            Indirect - media indirect specified, grab child XML to gain real path
            options
        result:
            final path to media file
        """
        if key.startswith('http://') or key.startswith('https://'):  # external address - keep
            path = key
        else:
            if AuthToken=='':
                path = key
            else:
                xargs = dict()
                xargs['X-Plex-Token'] = AuthToken
                if key.find('?')==-1:
                    path = key + '?' + urlencode(xargs)
                else:
                    path = key + '&' + urlencode(xargs)
        
        return path

    def getTranscodeImagePath(self, key, AuthToken, path, width, height):
        """
        Transcode Image support

        parameters:
            key
            AuthToken
            path - source path of current XML: path[srcXML]
            width
            height
        result:
            final path to image file
        """
        if key.startswith('http://') or key.startswith('https://'):  # external address - can we get a transcoding request for external images?
            path = key
        elif key.startswith('/'):  # internal full path.
            path = 'http://127.0.0.1:32400' + key
        else:  # internal path, add-on
            path = 'http://127.0.0.1:32400' + path + '/' + key
        path = path.encode('utf8')
        
        # This is bogus (note the extra path component) but ATV is stupid when it comes to caching images, it doesn't use querystrings.
        # Fortunately PMS is lenient...
        transcodePath = '/photo/:/transcode/' +str(width)+'x'+str(height)+ '/' + quote_plus(path)
        
        args = dict()
        args['width'] = width
        args['height'] = height
        args['url'] = path
        
        if not AuthToken=='':
            args['X-Plex-Token'] = AuthToken
        
        return transcodePath + '?' + urlencode(args)

    def getDirectImagePath(self, path, AuthToken):
        """
        Direct Image support

        parameters:
            path
            AuthToken
        result:
            final path to image file
        """
        if not AuthToken=='':
            xargs = dict()
            xargs['X-Plex-Token'] = AuthToken
            if path.find('?')==-1:
                path = path + '?' + urlencode(xargs)
            else:
                path = path + '&' + urlencode(xargs)
        
        return path

    def getTranscodeAudioPath(self, path, AuthToken, options, maxAudioBitrate):
        """
        Transcode Audio support

        parameters:
            path
            AuthToken
            options - dict() of PlexConnect-options as received from aTV
            maxAudioBitrate - [kbps]
        result:
            final path to pull in PMS transcoder
        """
        UDID = options['PlexConnectUDID']
        
        transcodePath = '/music/:/transcode/universal/start.mp3?'
        
        args = dict()
        args['path'] = path
        args['session'] = UDID
        args['protocol'] = 'http'
        args['maxAudioBitrate'] = maxAudioBitrate
        
        xargs = getXArgsDeviceInfo(options)
        if not AuthToken=='':
            xargs['X-Plex-Token'] = AuthToken
        
        return transcodePath + urlencode(args) + '&' + urlencode(xargs)

    def getDirectAudioPath(self, path, AuthToken):
        """
        Direct Audio support

        parameters:
            path
            AuthToken
        result:
            final path to audio file
        """
        if not AuthToken=='':
            xargs = dict()
            xargs['X-Plex-Token'] = AuthToken
            if path.find('?')==-1:
                path = path + '?' + urlencode(xargs)
            else:
                path = path + '&' + urlencode(xargs)
        
        return path

    def returnServerList(self, ATV_udid, data):
        """
        Returns a nicer list of all servers found in data, where data is in
        g_PMS format, for the client device with unique ID ATV_udid

        Input:
            ATV_udid                Unique client ID
            data                    e.g. self.g_PMS

        Output: List of all servers, with an entry of the form:
        {
        'name': friendlyName,      the Plex server's name
        'address': ip:port
        'ip': ip,                   without http/https
        'port': port
        'scheme': 'http'/'https',   nice for checking for secure connections
        'local': '1'/'0',           Is the server a local server?
        'owned': '1'/'0',           Is the server owned by the user?
        'machineIdentifier': id,    Plex server machine identifier
        'accesstoken': token        Access token to this server
        'baseURL': baseURL          scheme://ip:port
        }
        """
        serverlist = []
        for key, value in data[ATV_udid].items():
            serverlist.append({
                'name': value['name'],
                'address': value['address'],
                'ip': value['ip'],
                'port': value['port'],
                'scheme': value['scheme'],
                'local': value['local'],
                'owned': value['owned'],
                'machineIdentifier': key,
                'accesstoken': value['accesstoken'],
                'baseURL': value['baseURL']
            })
        return serverlist

    def GetPlexCollections(self, mediatype):
        """
        Input:
            mediatype           String or list of strings with possible values
                                'movie', 'show', 'artist', 'photo'
        Output:
            List with an entry of the form:
            {
            'name': xxx         Plex title for the media section
            'type': xxx         Plex type: 'movie', 'show', 'artist', 'photo'
            'id': xxx           Plex unique key for the section (1, 2, 3...)
            'uuid': xxx         Other unique Plex key, e.g.
                                74aec9f2-a312-4723-9436-de2ea43843c1
            }
        Returns an empty list if nothing is found.
        """
        collections = []
        url = "{server}/library/sections"
        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['_children']
        except KeyError:
            pass
        else:
            for item in result:
                contentType = item['type']
                if contentType in mediatype:
                    name = item['title']
                    contentId = item['key']
                    uuid = item['uuid']
                    collections.append({
                        'name': name,
                        'type': contentType,
                        'id': str(contentId),
                        'uuid': uuid
                    })
        return collections

    def GetPlexSectionResults(self, viewId, headerOptions={}):
        """
        Returns a list (raw JSON or XML API dump) of all Plex items in the Plex
        section with key = viewId.
        """
        result = []
        url = "{server}/library/sections/%s/all" % viewId
        jsondata = self.doUtils.downloadUrl(url, headerOptions=headerOptions)
        try:
            result = jsondata['_children']
        except TypeError:
            # Maybe we received an XML, check for that with tag attribute
            try:
                jsondata.tag
                result = jsondata
            # Nope, not an XML, abort
            except AttributeError:
                self.logMsg("Error retrieving all items for Plex section %s"
                            % viewId, -1)
                return result
        except KeyError:
            self.logMsg("Error retrieving all items for Plex section %s"
                        % viewId, -1)
        return result

    def GetAllPlexLeaves(self, viewId, headerOptions={}):
        """
        Returns a list (raw JSON or XML API dump) of all Plex subitems for the
        key.
        (e.g. /library/sections/2/allLeaves pointing to all TV shows)

        Input:
            viewId            Id of Plex library, e.g. '2'
            headerOptions     to override the download headers
        """
        result = []
        url = "{server}/library/sections/%s/allLeaves" % viewId
        jsondata = self.doUtils.downloadUrl(url, headerOptions=headerOptions)
        try:
            result = jsondata['_children']
        except TypeError:
            # Maybe we received an XML, check for that with tag attribute
            try:
                jsondata.tag
                result = jsondata
            # Nope, not an XML, abort
            except AttributeError:
                self.logMsg("Error retrieving all leaves for Plex section %s"
                            % viewId, -1)
                return result
        except KeyError:
            self.logMsg("Error retrieving all leaves for Plex viewId %s"
                        % viewId, -1)
        return result

    def GetAllPlexChildren(self, key):
        """
        Returns a list (raw JSON API dump) of all Plex children for the key.
        (e.g. /library/metadata/194853/children pointing to a season)

        Input:
            key             Key to a Plex item, e.g. 12345
        """
        result = []
        url = "{server}/library/metadata/%s/children" % key
        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['_children']
        except KeyError:
            self.logMsg("Error retrieving all children for Plex item %s" % key, -1)
            pass
        return result

    def GetPlexMetadata(self, key):
        """
        Returns raw API metadata for key as an etree XML.

        Can be called with either Plex key '/library/metadata/xxxx'metadata
        OR with the digits 'xxxx' only.

        Returns an empty string '' if something went wrong
        """
        xml = ''
        key = str(key)
        if '/library/metadata/' in key:
            url = "{server}" + key
        else:
            url = "{server}/library/metadata/" + key
        arguments = {
            'checkFiles': 1,            # No idea
            'includeExtras': 1,         # Trailers and Extras => Extras
            'includeRelated': 1,        # Similar movies => Video -> Related
            'includeRelatedCount': 5,
            'includeOnDeck': 1,
            'includeChapters': 1,
            'includePopularLeaves': 1,
            'includeConcerts': 1
        }
        url = url + '?' + urlencode(arguments)
        headerOptions = {'Accept': 'application/xml'}
        xml = self.doUtils.downloadUrl(url, headerOptions=headerOptions)
        # Did we receive a valid XML?
        try:
            xml.tag
        # Nope we did not receive a valid XML
        except AttributeError:
            self.logMsg("Error retrieving metadata for %s" % url, -1)
            xml = ''
        return xml


class API():
    """
    API(item)

    Processes a Plex media server's XML response

    item: xml.etree.ElementTree element
    """

    def __init__(self, item):
        self.item = item
        # which child in the XML response shall we look at?
        self.child = 0
        # which media part in the XML response shall we look at?
        self.part = 0
        self.clientinfo = clientinfo.ClientInfo()
        self.addonName = self.clientinfo.getAddonName()
        self.clientId = self.clientinfo.getDeviceId()
        self.userId = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userId)
        self.token = utils.window('emby_accessToken%s' % self.userId)

        self.jumpback = int(utils.settings('resumeJumpBack'))

    def logMsg(self, msg, lvl=1):
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

    def setChildNumber(self, number=0):
        """
        Which child in the XML response shall we look at and work with?
        """
        self.child = int(number)

    def getChildNumber(self):
        """
        Returns the child in the XML response that we're currently looking at
        """
        return self.child

    def setPartNumber(self, number=0):
        """
        Sets the part number to work with (used to deal with Movie with several
        parts).
        """
        self.part = int(number)

    def getPartNumber(self):
        """
        Returns the current media part number we're dealing with.
        """
        return self.part

    def convert_date(self, stamp):
        """
        convert_date(stamp) converts a Unix time stamp (seconds passed since
        January 1 1970) to a propper, human-readable time stamp
        """
        # DATEFORMAT = xbmc.getRegion('dateshort')
        # TIMEFORMAT = xbmc.getRegion('meridiem')
        # date_time = time.localtime(stamp)
        # if DATEFORMAT[1] == 'd':
        #     localdate = time.strftime('%d-%m-%Y', date_time)
        # elif DATEFORMAT[1] == 'm':
        #     localdate = time.strftime('%m-%d-%Y', date_time)
        # else:
        #     localdate = time.strftime('%Y-%m-%d', date_time)
        # if TIMEFORMAT != '/':
        #     localtime = time.strftime('%I:%M%p', date_time)
        # else:
        #     localtime = time.strftime('%H:%M', date_time)
        # return localtime + '  ' + localdate
        DATEFORMAT = xbmc.getRegion('dateshort')
        TIMEFORMAT = xbmc.getRegion('meridiem')
        date_time = time.localtime(float(stamp))
        localdate = time.strftime('%Y-%m-%dT%H:%M:%SZ', date_time)
        return localdate

    def getType(self):
        """
        Returns the type of media, e.g. 'movie'
        """
        item = self.item
        item = item[self.child].attrib
        itemtype = item['type']
        return itemtype

    def getChecksum(self):
        """
        Can be used on both XML and JSON
        Returns a string, not int
        """
        item = self.item
        # XML
        try:
            item = item[self.child].attrib
        # JSON
        except KeyError:
            pass
        # Include a letter to prohibit saving as an int!
        checksum = "K%s%s" % (self.getKey(),
                              item.get('updatedAt', ''))
        return checksum

    def getKey(self):
        """
        Can be used on both XML and JSON
        Returns the Plex unique movie id as a str, not int
        """
        item = self.item
        # XML
        try:
            item = item[self.child].attrib
        # JSON
        except KeyError:
            pass
        key = item['ratingKey']
        return str(key)

    def getIndex(self):
        """
        Returns the 'index' of an PMS XML reply. Depicts e.g. season number.
        """
        item = self.item[self.child].attrib
        index = item['index']
        return str(index)

    def getDateCreated(self):
        """
        Returns the date when this library item was created

        Input:
            index       child number as int; normally =0
        """
        item = self.item
        item = item[self.child].attrib
        dateadded = item['addedAt']
        dateadded = self.convert_date(dateadded)
        return dateadded

    def getUserData(self):
        """
        Returns a dict with None if a value is missing
        {
            'Favorite': favorite,                  # False, because n/a in Plex
            'PlayCount': playcount,
            'Played': played,                      # True/False
            'LastPlayedDate': lastPlayedDate,
            'Resume': resume,                      # Resume time in seconds
            'Runtime': runtime,
            'Rating': rating
        }
        """
        item = self.item
        # Default
        favorite = False
        playcount = None
        played = False
        lastPlayedDate = None
        resume = 0
        rating = 0

        item = item[self.child].attrib
        try:
            playcount = int(item['viewCount'])
        except KeyError:
            playcount = None

        if playcount:
            played = True

        try:
            lastPlayedDate = int(item['lastViewedAt'])
            lastPlayedDate = self.convert_date(lastPlayedDate)
        except KeyError:
            lastPlayedDate = None

        resume, runtime = self.getRuntime()
        return {
            'Favorite': favorite,
            'PlayCount': playcount,
            'Played': played,
            'LastPlayedDate': lastPlayedDate,
            'Resume': resume,
            'Runtime': runtime,
            'Rating': rating
        }

    def getPeople(self):
        """
        Returns a dict of lists of people found.
        {
            'Director': list,
            'Writer': list,
            'Cast': list,
            'Producer': list
        }
        """
        item = self.item
        director = []
        writer = []
        cast = []
        producer = []
        for child in item[self.child]:
            if child.tag == 'Director':
                director.append(child.attrib['tag'])
            elif child.tag == 'Writer':
                writer.append(child.attrib['tag'])
            elif child.tag == 'Role':
                cast.append(child.attrib['tag'])
            elif child.tag == 'Producer':
                producer.append(child.attrib['tag'])
        return {
            'Director': director,
            'Writer': writer,
            'Cast': cast,
            'Producer': producer
        }

    def getPeopleList(self):
        """
        Returns a list of people from item, with a list item of the form
        {
            'Name': xxx,
            'Type': xxx,
            'Id': xxx
            'imageurl': url to picture, None otherwise
            ('Role': xxx for cast/actors only, None if not found)
        }
        """
        item = self.item
        people = []
        # Key of library: Plex-identifier. Value represents the Kodi/emby side
        people_of_interest = {
            'Director': 'Director',
            'Writer': 'Writer',
            'Role': 'Actor',
            'Producer': 'Producer'
        }
        for child in item[self.child]:
            if child.tag in people_of_interest.keys():
                name = child.attrib['tag']
                name_id = child.attrib['id']
                Type = child.tag
                Type = people_of_interest[Type]
                try:
                    url = child.attrib['thumb']
                except KeyError:
                    url = None
                try:
                    Role = child.attrib['role']
                except KeyError:
                    Role = None
                people.append({
                    'Name': name,
                    'Type': Type,
                    'Id': name_id,
                    'imageurl': url
                })
                if url:
                    people[-1].update({'imageurl': url})
                if Role:
                    people[-1].update({'Role': Role})
        return people

    def getGenres(self):
        """
        Returns a list of genres found. (Not a string)
        """
        item = self.item
        genre = []
        for child in item[self.child]:
            if child.tag == 'Genre':
                genre.append(child.attrib['tag'])
        return genre

    def getProvider(self, providername=None):
        """
        providername: depricated

        Return IMDB, e.g. "imdb://tt0903624?lang=en". Returns None if not found
        """
        item = self.item
        item = item[self.child].attrib
        try:
            item = item['guid']
        except KeyError:
            return None

        regex = re.compile(r'''com\.plexapp\.agents\.(.+)$''')
        provider = regex.findall(item)
        try:
            provider = provider[0]
        except IndexError:
            provider = None
        return provider

    def getTitle(self):
        """
        Returns an item's name/title or "Missing Title Name" for both XML and
        JSON PMS replies

        Output:
            title, sorttitle

        sorttitle = title, if no sorttitle is found
        """
        item = self.item
        # XML
        try:
            item = item[self.child].attrib
        # JSON
        except KeyError:
            pass
        try:
            title = item['title']
        except:
            title = 'Missing Title Name'
        try:
            sorttitle = item['titleSort']
        except KeyError:
            sorttitle = title
        return title, sorttitle

    def getPlot(self):
        """
        Returns the plot or None.
        """
        item = self.item
        item = item[self.child].attrib
        try:
            plot = item['summary']
        except:
            plot = None
        return plot

    def getTagline(self):
        """
        Returns a shorter tagline or None
        """
        item = self.item
        item = item[self.child].attrib
        try:
            tagline = item['tagline']
        except KeyError:
            tagline = None
        return tagline

    def getAudienceRating(self):
        """
        Returns the audience rating or None
        """
        item = self.item
        item = item[self.child].attrib
        try:
            rating = item['audienceRating']
        except KeyError:
            rating = None
        return rating

    def getYear(self):
        """
        Returns the production(?) year ("year") or None
        """
        item = self.item
        item = item[self.child].attrib
        try:
            year = item['year']
        except KeyError:
            year = None
        return year

    def getRuntime(self):
        """
        Resume point of time and runtime/totaltime in seconds, rounded to 6th
        decimal.
        Time from Plex server is measured in milliseconds.
        Kodi: seconds

        Output:
            resume, runtime         as floats. 0.0 if not found
        """
        time_factor = 1.0 / 1000.0    # millisecond -> seconds
        item = self.item
        item = item[self.child].attrib

        try:
            runtime = float(item['duration'])
        except KeyError:
            runtime = 0.0
        try:
            resume = float(item['viewOffset'])
        except KeyError:
            resume = 0.0

        # Adjust the resume point by x seconds as chosen by the user in the
        # settings
        if resume:
            # To avoid negative bookmark
            if resume > self.jumpback:
                resume = resume - self.jumpback

        runtime = runtime * time_factor
        resume = resume * time_factor
        resume = round(resume, 6)
        runtime = round(runtime, 6)
        return resume, runtime

    def getMpaa(self):
        """
        Get the content rating or None
        """
        # Convert more complex cases
        item = self.item
        item = item[self.child].attrib
        try:
            mpaa = item['contentRating']
        except KeyError:
            mpaa = None
        if mpaa in ("NR", "UR"):
            # Kodi seems to not like NR, but will accept Rated Not Rated
            mpaa = "Rated Not Rated"
        return mpaa

    def getCountry(self):
        """
        Returns a list of all countries found in item.
        """
        item = self.item
        country = []
        for child in item[self.child]:
            if child.tag == 'Country':
                country.append(child.attrib['tag'])
        return country

    def getPremiereDate(self):
        """
        Returns the "originallyAvailableAt" or None
        """
        item = self.item
        item = item[self.child].attrib
        try:
            premiere = item['originallyAvailableAt']
        except:
            premiere = None
        return premiere

    def getStudios(self):
        """
        Returns a list with a single entry for the studio, or an empty list
        """
        item = self.item
        studio = []
        item = item[self.child].attrib
        try:
            studio.append(self.getStudio(item['studio']))
        except KeyError:
            pass
        return studio

    def getStudio(self, studioName):
        """
        Convert studio for Kodi to properly detect them
        """
        studios = {
            'abc (us)': "ABC",
            'fox (us)': "FOX",
            'mtv (us)': "MTV",
            'showcase (ca)': "Showcase",
            'wgn america': "WGN"
        }
        return studios.get(studioName.lower(), studioName)

    def joinList(self, listobject):
        """
        Smart-joins the listobject into a single string using a " / "
        separator.
        If the list is empty, smart_join returns an empty string.
        """
        string = " / ".join(listobject)
        return string

    def getEpisodeDetails(self):
        """
        Call on a single episode.

        Output: for the corresponding the TV show and season:
            [
                TV show key,        Plex: 'grandparentRatingKey'
                TV show title,      Plex: 'grandparentTitle'
                TV show season,     Plex: 'parentIndex'
                Episode number,     Plex: 'index'
            ]
        """
        item = self.item[self.child].attrib
        key = item['grandparentRatingKey']
        title = item['grandparentTitle']
        season = item['parentIndex']
        episode = item['index']
        return key, title, season, episode

    def getFilePath(self):
        """
        returns the path to the Plex object, e.g. "/library/metadata/221803"
        """
        item = self.item
        item = item[self.child].attrib
        try:
            filepath = item['key']
        except KeyError:
            filepath = ""
        # Plex: do we need this?
        else:
            if "\\\\" in filepath:
                # append smb protocol
                filepath = filepath.replace("\\\\", "smb://")
                filepath = filepath.replace("\\", "/")

            if item.get('VideoType'):
                videotype = item['VideoType']
                # Specific format modification
                if 'Dvd'in videotype:
                    filepath = "%s/VIDEO_TS/VIDEO_TS.IFO" % filepath
                elif 'Bluray' in videotype:
                    filepath = "%s/BDMV/index.bdmv" % filepath

            if "\\" in filepath:
                # Local path scenario, with special videotype
                filepath = filepath.replace("/", "\\")

        return filepath

    def addPlexCredentialsToUrl(self, url, arguments={}):
        """
        Takes an URL and optional arguments (also to be URL-encoded); returns
        an extended URL with e.g. the Plex token included.
        """
        token = {'X-Plex-Token': self.token}
        xargs = PlexAPI().getXArgsDeviceInfo(options=token)
        xargs.update(arguments)
        url = "%s?%s" % (url, urlencode(xargs))
        return url

    def getBitrate(self):
        """
        Returns the bitrate as an int. The Part bitrate is returned; if not
        available in the Plex XML, the Media bitrate is returned
        """
        item = self.item
        try:
            bitrate = item[self.child][0][self.part].attrib['bitrate']
        except KeyError:
            bitrate = item[self.child][0].attrib['bitrate']
        bitrate = int(bitrate)
        return bitrate

    def getDataFromPartOrMedia(self, key):
        """
        Retrieves XML data 'key' first from the active part. If unsuccessful,
        tries to retrieve the data from the Media response part.

        If all fails, None is returned.
        """
        media = self.item[self.child][0].attrib
        part = self.item[self.child][0][self.part].attrib
        try:
            try:
                value = part[key]
            except KeyError:
                value = media[key]
        except KeyError:
            value = None
        return value

    def getVideoCodec(self):
        """
        Returns the video codec and resolution for the child and part selected.
        If any data is not found on a part-level, the Media-level data is
        returned.
        If that also fails (e.g. for old trailers, None is returned)

        Output:
            {
                'videocodec': xxx,       e.g. 'h264'
                'resolution': xxx,       e.g. '720' or '1080'
                'height': xxx,           e.g. '816'
                'width': xxx,            e.g. '1920'
                'aspectratio': xxx,      e.g. '1.78'
                'bitrate': xxx,          e.g. 10642 (an int!)
                'container': xxx         e.g. 'mkv'
            }
        """

        videocodec = self.getDataFromPartOrMedia('videoCodec')
        resolution = self.getDataFromPartOrMedia('videoResolution')
        height = self.getDataFromPartOrMedia('height')
        width = self.getDataFromPartOrMedia('width')
        aspectratio = self.getDataFromPartOrMedia('aspectratio')
        bitrate = self.getDataFromPartOrMedia('bitrate')
        container = self.getDataFromPartOrMedia('container')

        videoCodec = {
            'videocodec': videocodec,
            'resolution': resolution,
            'height': height,
            'width': width,
            'aspectratio': aspectratio,
            'bitrate': bitrate,
            'container': container
        }
        return videoCodec

    def getExtras(self):
        """
        Returns a list of trailer and extras from PMS XML. Returns [] if
        no extras are found.
        Extratypes:
            '1':    Trailer
            '5':    Behind the scenes

        Output: list of dicts with one entry of the form:
            'key':                     e.g. /library/metadata/xxxx
            'title':
            'thumb':                    artwork
            'duration':
            'extraType':
            'originallyAvailableAt':
            'year':
        """
        extras = self.item[0].find('Extras')
        elements = []
        if not extras:
            return elements
        for extra in extras:
            # Trailer:
            key = extra.attrib['key']
            title = extra.attrib['title']
            thumb = extra.attrib['thumb']
            duration = extra.attrib['duration']
            year = extra.attrib['year']
            extraType = extra.attrib['extraType']
            originallyAvailableAt = extra.attrib['originallyAvailableAt']
            elements.append({'key': key,
                             'title': title,
                             'thumb': thumb,
                             'duration': duration,
                             'extraType': extraType,
                             'originallyAvailableAt': originallyAvailableAt,
                             'year': year})
        return elements

    def getMediaStreams(self):
        """
        Returns the media streams

        Output: each track contains a dictionaries
        {
            'video': videotrack-list,       'codec', 'height', 'width',
                                            'aspect', 'video3DFormat'
            'audio': audiotrack-list,       'codec', 'channels',
                                            'language'
            'subtitle': list of subtitle languages (or "Unknown")
        }
        """
        item = self.item
        videotracks = []
        audiotracks = []
        subtitlelanguages = []
        aspectratio = None
        try:
            aspectratio = item[self.child][0].attrib['aspectRatio']
        except KeyError:
            pass
        # TODO: what if several Media tags exist?!?
        # Loop over parts
        for child in item[self.child][0]:
            container = child.attrib['container'].lower()
            # Loop over Streams
            for grandchild in child:
                mediaStream = grandchild.attrib
                type = int(mediaStream['streamType'])
                if type == 1:  # Video streams
                    videotrack = {}
                    videotrack['codec'] = mediaStream['codec'].lower()
                    if "msmpeg4" in videotrack['codec']:
                        videotrack['codec'] = "divx"
                    elif "mpeg4" in videotrack['codec']:
                        # if "simple profile" in profile or profile == "":
                        #    videotrack['codec'] = "xvid"
                        pass
                    elif "h264" in videotrack['codec']:
                        if container in ("mp4", "mov", "m4v"):
                            videotrack['codec'] = "avc1"
                    videotrack['height'] = mediaStream.get('height')
                    videotrack['width'] = mediaStream.get('width')
                    # TODO: 3d Movies?!?
                    # videotrack['Video3DFormat'] = item.get('Video3DFormat')
                    try:
                        aspectratio = mediaStream['aspectRatio']
                    except KeyError:
                        if not aspectratio:
                            aspectratio = round(float(videotrack['width'] / videotrack['height']), 6)
                    videotrack['aspect'] = aspectratio
                    # TODO: Video 3d format
                    videotrack['video3DFormat'] = None
                    videotracks.append(videotrack)

                elif type == 2:  # Audio streams
                    audiotrack = {}
                    audiotrack['codec'] = mediaStream['codec'].lower()
                    profile = mediaStream['codecID'].lower()
                    if "dca" in audiotrack['codec'] and "dts-hd ma" in profile:
                        audiotrack['codec'] = "dtshd_ma"
                    audiotrack['channels'] = mediaStream.get('channels')
                    try:
                        audiotrack['language'] = mediaStream.get('language')
                    except KeyError:
                        audiotrack['language'] = 'unknown'
                    audiotracks.append(audiotrack)

                elif type == 3:  # Subtitle streams
                    try:
                        subtitlelanguages.append(mediaStream['language'])
                    except:
                        subtitlelanguages.append("Unknown")
        media = {
            'video': videotracks,
            'audio': audiotracks,
            'subtitle': subtitlelanguages
        }
        return media

    def getAllArtwork(self, parentInfo=False):
        """
        Gets the URLs to the Plex artwork, or empty string if not found.

        Output:
        {
            'Primary':           Plex key: "thumb". Only 1 pix
            'Art':,
            'Banner':,
            'Logo':,
            'Thumb':,
            'Disc':,
            'Backdrop': []       Plex key: "art". Only 1 pix
        }
        """
        server = self.server
        item = self.item

        maxHeight = 10000
        maxWidth = 10000
        customquery = ""

        if utils.settings('compressArt') == "true":
            customquery = "&Quality=90"

        if utils.settings('enableCoverArt') == "false":
            customquery += "&EnableImageEnhancers=false"

        allartworks = {
            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }
        # Process backdrops
        # Get background artwork URL
        item = item[self.child].attrib
        try:
            background = item['art']
            background = "%s%s" % (server, background)
            background = self.addPlexCredentialsToUrl(background)
        except KeyError:
            background = ""
        allartworks['Backdrop'].append(background)
        # Get primary "thumb" pictures:
        try:
            primary = item['thumb']
            primary = "%s%s" % (server, primary)
            primary = self.addPlexCredentialsToUrl(primary)
        except KeyError:
            primary = ""
        allartworks['Primary'] = primary

        # Process parent items if the main item is missing artwork
        if parentInfo:
            
            # Process parent backdrops
            if not allartworks['Backdrop']:
                
                parentId = item.get('ParentBackdropItemId')
                if parentId:
                    # If there is a parentId, go through the parent backdrop list
                    parentbackdrops = item['ParentBackdropImageTags']

                    backdropIndex = 0
                    for parentbackdroptag in parentbackdrops:
                        artwork = (
                            "%s/emby/Items/%s/Images/Backdrop/%s?"
                            "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                            % (server, parentId, backdropIndex,
                                maxWidth, maxHeight, parentbackdroptag, customquery))
                        allartworks['Backdrop'].append(artwork)
                        backdropIndex += 1

            # Process the rest of the artwork
            parentartwork = ['Logo', 'Art', 'Thumb']
            for parentart in parentartwork:

                if not allartworks[parentart]:
                    
                    parentId = item.get('Parent%sItemId' % parentart)
                    if parentId:
                        
                        parentTag = item['Parent%sImageTag' % parentart]
                        artwork = (
                            "%s/emby/Items/%s/Images/%s/0?"
                            "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                            % (server, parentId, parentart,
                                maxWidth, maxHeight, parentTag, customquery))
                        allartworks[parentart] = artwork

            # Parent album works a bit differently
            if not allartworks['Primary']:

                parentId = item.get('AlbumId')
                if parentId and item.get('AlbumPrimaryImageTag'):
                    
                    parentTag = item['AlbumPrimaryImageTag']
                    artwork = (
                        "%s/emby/Items/%s/Images/Primary/0?"
                        "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                        % (server, parentId, maxWidth, maxHeight, parentTag, customquery))
                    allartworks['Primary'] = artwork
        return allartworks

    def getTranscodeVideoPath(self, action, quality={}, subtitle={}, audioboost=None, options={}):
        """
        Transcode Video support; returns the URL to get a media started

        Input:
            action      'DirectPlay', 'DirectStream' or 'Transcode'

            quality:    {
                            'videoResolution': 'resolution',
                            'videoQuality': 'quality',
                            'maxVideoBitrate': 'bitrate'
                        }
                        (one or several of these options)
            subtitle    {'selected', 'dontBurnIn', 'size'}
            audioboost  e.g. 100
            options     dict() of PlexConnect-options as received from aTV
        Output:
            final URL to pull in PMS transcoder

        TODO: mediaIndex
        """
        # Set Client capabilities
        clientArgs = {
            'X-Plex-Client-Capabilities':
                "protocols=shoutcast,"
                    "http-live-streaming,"
                    "http-streaming-video,"
                    "http-streaming-video-720p,"
                    "http-streaming-video-1080p,"
                    "http-mp4-streaming,"
                    "http-mp4-video,"
                    "http-mp4-video-720p,"
                    "http-mp4-video-1080p;"
                "videoDecoders="
                    "h264{profile:high&resolution:1080&level:51},"
                    "h265{profile:high&resolution:1080&level:51},"
                    "mpeg1video,"
                    "mpeg2video,"
                    "mpeg4,"
                    "msmpeg4,"
                    "mjpeg,"
                    "wmv2,"
                    "wmv3,"
                    "vc1,"
                    "cinepak,"
                    "h263;"
                "audioDecoders="
                    "mp3,"
                    "aac,"
                    "ac3{bitrate:800000&channels:8},"
                    "dts{bitrate:800000&channels:8},"
                    "truehd,"
                    "eac3,"
                    "dca,"
                    "mp2,"
                    "pcm,"
                    "wmapro,"
                    "wmav2,"
                    "wmavoice,"
                    "wmalossless;"
        }
        xargs = PlexAPI().getXArgsDeviceInfo(options=options)
        # For Direct Playing
        if action == "DirectPlay":
            path = self.item[self.child][0][self.part].attrib['key']
            transcodePath = self.server + path
            # Be sure to have exactly ONE '?' in the path (might already have
            # been returned, e.g. trailers!)
            if '?' not in path:
                transcodePath = transcodePath + '?'
            url = transcodePath + \
                urlencode(clientArgs) + '&' + \
                urlencode(xargs)
            return url

        # For Direct Streaming or Transcoding
        transcodePath = self.server + \
            '/video/:/transcode/universal/start.m3u8?'
        partCount = 0
        for parts in self.item[self.child][0]:
            partCount = partCount + 1
        # Movie consists of several parts; grap one part
        if partCount > 1:
            path = self.item[self.child][0][self.part].attrib['key']
        # Movie consists of only one part
        else:
            path = self.item[self.child].attrib['key']
        args = {
            'path': path,
            'mediaIndex': 0,       # Probably refering to XML reply sheme
            'partIndex': self.part,
            'protocol': 'hls',   # seen in the wild: 'dash', 'http', 'hls'
            'offset': 0,           # Resume point
            'fastSeek': 1
        }
        # All the settings
        if subtitle:
            argsUpdate = {
                'subtitles': 'burn',
                'subtitleSize': subtitle['size'],        # E.g. 100
                'skipSubtitles': subtitle['dontBurnIn']  # '1': shut off PMS
            }
            self.logMsg(
                "Subtitle: selected %s, dontBurnIn %s, size %s"
                % (subtitle['selected'], subtitle['dontBurnIn'],
                    subtitle['size']),
                1
            )
            args.update(argsUpdate)
        if audioboost:
            argsUpdate = {
                'audioBoost': audioboost
            }
            self.logMsg("audioboost: %s" % audioboost, 1)
            args.update(argsUpdate)

        if action == "DirectStream":
            argsUpdate = {
                'directPlay': '0',
                'directStream': '1',
            }
            args.update(argsUpdate)
        elif action == 'Transcode':
            argsUpdate = {
                'directPlay': '0',
                'directStream': '0'
            }
            self.logMsg("Setting transcode quality to: %s" % quality, 1)
            args.update(quality)
            args.update(argsUpdate)

        url = transcodePath + \
            urlencode(clientArgs) + '&' + \
            urlencode(xargs) + '&' + \
            urlencode(args)
        return url

    def externalSubs(self, playurl):
        externalsubs = []
        mapping = {}

        item = self.item
        itemid = self.getKey()
        try:
            mediastreams = item[self.child][0][0]
        except (TypeError, KeyError, IndexError):
            return

        kodiindex = 0
        for stream in mediastreams:
            # index = stream['Index']
            index = stream.attrib['id']
            # Since Emby returns all possible tracks together, have to pull only external subtitles.
            # IsTextSubtitleStream if true, is available to download from emby.
            if (stream.attrib['streamType'] == "3" and
                    stream.attrib['format']):

                # Direct stream
                # PLEX: TODO!!
                url = ("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                        % (self.server, itemid, itemid, index))
                
                # map external subtitles for mapping
                mapping[kodiindex] = index
                externalsubs.append(url)
                kodiindex += 1
        
        mapping = json.dumps(mapping)
        utils.window('emby_%s.indexMapping' % playurl, value=mapping)

        return externalsubs

    def GetPlexPlaylist(self):
        """
        Returns raw API metadata XML dump for a playlist with e.g. trailers.
        """
        item = self.item
        key = self.getKey()
        try:
            uuid = item.attrib['librarySectionUUID']
        # if not found: probably trying to start a trailer directly
        # Hence no playlist needed
        except KeyError:
            return None
        mediatype = item[self.child].tag.lower()
        trailerNumber = utils.settings('trailerNumber')
        if not trailerNumber:
            trailerNumber = '3'
        url = "{server}/playQueues"
        args = {
            'type': mediatype,
            'uri': 'library://' + uuid +
                        '/item/%2Flibrary%2Fmetadata%2F' + key,
            'includeChapters': '1',
            'extrasPrefixCount': trailerNumber,
            'shuffle': '0',
            'repeat': '0'
        }
        url = url + '?' + urlencode(args)
        xml = downloadutils.DownloadUtils().downloadUrl(
            url,
            type="POST",
            headerOptions={'Accept': 'application/xml'}
        )
        if not xml:
            self.logMsg("Error retrieving metadata for %s" % url, 1)
        return xml

    def GetParts(self):
        """
        Returns the parts of the specified video child in the XML response
        """
        return self.item[self.child][0]

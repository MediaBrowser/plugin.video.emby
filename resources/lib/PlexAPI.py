
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

try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree

from urllib import urlencode, quote_plus

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

    def logMsg(self, msg, lvl=1):
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

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
                self.logMsg("plex.tv username and token: %s, %s" % (plexLogin, authtoken), 1)
                if plexLogin == '':
                    dialog = xbmcgui.Dialog()
                    dialog.ok(self.addonName, 'Could not sign in user %s' % plexLogin)
        # Write to Kodi settings file
        addon = xbmcaddon.Addon()
        addon.setSetting('plexLogin', retrievedPlexLogin)
        addon.setSetting('plexToken', authtoken)
        return (retrievedPlexLogin, authtoken)

    def CheckConnection(self, url, token):
        """
        Checks connection to a Plex server, available at url. Can also be used
        to check for connection with plex.tv!

        Input:
            url         URL to Plex server (e.g. https://192.168.1.1:32400)
            token       appropriate token to access server
        Output:
            200         if the connection was successfull
            ''          empty string if connection failed for whatever reason
            401         integer if token has been revoked
        """
        # Add '/clients' to URL because then an authentication is necessary
        # If a plex.tv URL was passed, this does not work.
        if 'plex.tv' in url:
            url = 'https://plex.tv/api/home/users'
        else:
            url = url + '/clients'
        self.logMsg("CheckConnection called for url %s with a token" % url, 2)

        r = downloadutils.DownloadUtils().downloadUrl(
            url,
            authenticate=False,
            headerOptions={'X-Plex-Token': token}
        )
        self.logMsg("Response was: %s" % r, 2)
        exceptionlist = [
            '',
            401
        ]
        # To get rid of the stuff that was downloaded :-)
        if r not in exceptionlist:
            r = 200
        return r

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
        # Plex: changed CSettings to new function getServerFromSettings()
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
            for uuid in PMS_list:
                PMS = PMS_list[uuid]
                self.declarePMS(ATV_udid, PMS['uuid'], PMS['serverName'], 'http', PMS['ip'], PMS['port'])  # dflt: token='', local, owned
        else:
            # MyPlex servers
            self.getPMSListFromMyPlex(ATV_udid, authtoken)
        # all servers - update enableGzip
        for uuid in self.g_PMS.get(ATV_udid, {}):
            # enable Gzip if not on same host, local&remote PMS depending
            # on setting
            enableGzip = (not self.getPMSProperty(ATV_udid, uuid, 'ip') == IP_self) \
                and (
                    (self.getPMSProperty(ATV_udid, uuid, 'local') == '1'
                        and False)
                    or
                    (self.getPMSProperty(ATV_udid, uuid, 'local') == '0'
                        and True) == 'True'
                )
            self.updatePMSProperty(ATV_udid, uuid, 'enableGzip', enableGzip)

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
                    
                    # check MyPlex data age - skip if >2 days
                    infoAge = time.time() - int(Dir.get('lastSeenAt'))
                    oneDayInSec = 60*60*24
                    if infoAge > 2*oneDayInSec:  # two days in seconds -> expiration in setting?
                        dprint(__name__, 1, "Server {0} not updated for {1} days - skipping.", name, infoAge/oneDayInSec)
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
            options:        dictionary of options that will override the
                            standard header options otherwise set.
            JSON=True       will enforce a JSON answer, never mind any options
        Output:
            header dictionary
        """
        # Get addon infos
        xargs = dict()
        xargs['User-agent'] = 'PlexKodiConnect'
        xargs['X-Plex-Device'] = self.deviceName
        # xargs['X-Plex-Model'] = ''
        xargs['X-Plex-Platform'] = self.platform
        xargs['X-Plex-Client-Platform'] = self.platform
        xargs['X-Plex-Product'] = 'PlexKodiConnect'
        xargs['X-Plex-Version'] = self.plexversion
        xargs['X-Plex-Client-Identifier'] = self.clientId
        if options:
            xargs.update(options)
        if JSON:
            xargs['Accept'] = 'application/json'
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

    def ChoosePlexHomeUser(self):
        """
        Let's user choose from a list of Plex home users. Will switch to that
        user accordingly.

        Output:
            username
            userid
            authtoken
        """
        string = self.__language__
        plexToken = utils.settings('plexToken')
        plexLogin = utils.settings('plexLogin')
        self.logMsg("Getting user list.", 1)
        # Get list of Plex home users
        users = self.MyPlexListHomeUsers(plexToken)
        # Download users failed. Set username to Plex login
        if not users:
            utils.settings('username', value=plexLogin)
            self.logMsg("User download failed. Set username = plexlogin", 1)
            return ('', '', '')

        userlist = []
        for user in users:
            username = user['title']
            userlist.append(username)
        usernumber = len(userlist)
        usertoken = ''
        # Plex home not in use: only 1 user returned
        trials = 1
        while trials < 4:
            if usernumber > 1:
                dialog = xbmcgui.Dialog()
                user_select = dialog.select(string(30200), userlist)
            else:
                user_select = 0
            if user_select > -1:
                selected_user = userlist[user_select]
                self.logMsg("Selected user: %s" % selected_user, 1)
                utils.settings('username', value=selected_user)
            else:
                self.logMsg("No user selected.", 1)
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
                return ('', '', '')
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
            username, usertoken = self.MyPlexSwitchHomeUser(
                user['id'],
                pin,
                plexToken
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
        return (username, user['id'], usertoken)

    def MyPlexSwitchHomeUser(self, id, pin, authtoken, options={}):
        """
        Retrieves Plex home token for a Plex home user.

        Input:
            id              id of the Plex home user
            pin             PIN of the Plex home user, if protected
            authtoken       token for plex.tv
            options={}      optional additional header options

        Output:
            username        Plex home username
            authtoken       token for Plex home user

        Returns empty strings if unsuccessful
        """
        MyPlexHost = 'https://plex.tv'
        MyPlexURL = MyPlexHost + '/api/home/users/' + id + '/switch'

        if pin:
            MyPlexURL += '?pin=' + pin

        xargs = {}
        xargs = self.getXArgsDeviceInfo(options)
        xargs['X-Plex-Token'] = authtoken

        request = urllib2.Request(MyPlexURL, None, xargs)
        request.get_method = lambda: 'POST'

        response = urllib2.urlopen(request).read()

        self.logMsg("====== MyPlexHomeUser XML ======", 1)
        self.logMsg(response, 1)
        self.logMsg("====== MyPlexHomeUser XML finished ======", 1)

        # analyse response
        XMLTree = etree.ElementTree(etree.fromstring(response))

        el_user = XMLTree.getroot()  # root=<user>. double check?
        username = el_user.attrib.get('title', '')
        authtoken = el_user.attrib.get('authenticationToken', '')

        if username and authtoken:
            self.logMsg('MyPlex switch HomeUser change successfull', 0)
        else:
            self.logMsg('MyPlex switch HomeUser change failed', 0)
        return (username, authtoken)

    def MyPlexListHomeUsers(self, authtoken):
        """
        Returns all myPlex home users for the currently signed in account.

        Input:
            authtoken for plex.tv
            options, optional
        Output:
            List of users, where one entry is of the form:
            {
                "id": userId, "admin": '1'/'0', "guest": '1'/'0',
                "restricted": '1'/'0', "protected": '1'/'0',
                "email": email, "title": title, "username": username,
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

    def getTranscodeVideoPath(self, path, AuthToken, options, action, quality, subtitle, audio, partIndex):
        """
        Transcode Video support

        parameters:
            path
            AuthToken
            options - dict() of PlexConnect-options as received from aTV
            action - transcoder action: Auto, Directplay, Transcode
            quality - (resolution, quality, bitrate)
            subtitle - {'selected', 'dontBurnIn', 'size'}
            audio - {'boost'}
        result:
            final path to pull in PMS transcoder
        """
        UDID = options['PlexConnectUDID']
        
        transcodePath = '/video/:/transcode/universal/start.m3u8?'
        
        vRes = quality[0]
        vQ = quality[1]
        mVB = quality[2]
        dprint(__name__, 1, "Setting transcode quality Res:{0} Q:{1} {2}Mbps", vRes, vQ, mVB)
        dprint(__name__, 1, "Subtitle: selected {0}, dontBurnIn {1}, size {2}", subtitle['selected'], subtitle['dontBurnIn'], subtitle['size'])
        dprint(__name__, 1, "Audio: boost {0}", audio['boost'])
        
        args = dict()
        args['session'] = UDID
        args['protocol'] = 'hls'
        args['videoResolution'] = vRes
        args['maxVideoBitrate'] = mVB
        args['videoQuality'] = vQ
        args['directStream'] = '0' if action=='Transcode' else '1'
        # 'directPlay' - handled by the client in MEDIARUL()
        args['subtitleSize'] = subtitle['size']
        args['skipSubtitles'] = subtitle['dontBurnIn']  #'1'  # shut off PMS subtitles. Todo: skip only for aTV native/SRT (or other supported)
        args['audioBoost'] = audio['boost']
        args['fastSeek'] = '1'
        args['path'] = path
        args['partIndex'] = partIndex
        
        xargs = getXArgsDeviceInfo(options)
        xargs['X-Plex-Client-Capabilities'] = "protocols=http-live-streaming,http-mp4-streaming,http-streaming-video,http-streaming-video-720p,http-mp4-video,http-mp4-video-720p;videoDecoders=h264{profile:high&resolution:1080&level:41};audioDecoders=mp3,aac{bitrate:160000}"
        if not AuthToken=='':
            xargs['X-Plex-Token'] = AuthToken
        
        return transcodePath + urlencode(args) + '&' + urlencode(xargs)

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


# Guess this stuff is not yet working
if __name__ == '__main__':
    testPlexGDM = 0
    testLocalPMS = 0
    testSectionXML = 1
    testMyPlexXML = 0
    testMyPlexSignIn = 0
    testMyPlexSignOut = 0
    
    username = 'abc'
    password = 'def'
    token = 'xyz'
    
    
    # test PlexGDM
    if testPlexGDM:
        dprint('', 0, "*** PlexGDM")
        PMS_list = PlexGDM()
        dprint('', 0, PMS_list)
    
    
    # test XML from local PMS
    if testLocalPMS:
        dprint('', 0, "*** XML from local PMS")
        XML = getXMLFromPMS('http://127.0.0.1:32400', '/library/sections')
    
    
    # test local Server/Sections
    if testSectionXML:
        dprint('', 0, "*** local Server/Sections")
        PMS_list = PlexGDM()
        XML = getSectionXML(PMS_list, {}, '')
    
    
    # test XML from MyPlex
    if testMyPlexXML:
        dprint('', 0, "*** XML from MyPlex")
        XML = getXMLFromPMS('https://plex.tv', '/pms/servers', None, token)
        XML = getXMLFromPMS('https://plex.tv', '/pms/system/library/sections', None, token)
    
    
    # test MyPlex Sign In
    if testMyPlexSignIn:
        dprint('', 0, "*** MyPlex Sign In")
        options = {'PlexConnectUDID':'007'}
        
        (user, token) = MyPlexSignIn(username, password, options)
        if user=='' and token=='':
            dprint('', 0, "Authentication failed")
        else:
            dprint('', 0, "logged in: {0}, {1}", user, token)
    
    
    # test MyPlex Sign out
    if testMyPlexSignOut:
        dprint('', 0, "*** MyPlex Sign Out")
        MyPlexSignOut(token)
        dprint('', 0, "logged out")
    
    # test transcoder

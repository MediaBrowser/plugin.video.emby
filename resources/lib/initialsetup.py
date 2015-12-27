# -*- coding: utf-8 -*-

#################################################################################################

import json
import socket

import xbmc
import xbmcgui
import xbmcaddon

import utils
import clientinfo
import downloadutils
import userclient

import PlexAPI

#################################################################################################


class InitialSetup():


    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.__language__ = self.addon.getLocalizedString

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.addonId = self.clientInfo.getAddonId()
        self.doUtils = downloadutils.DownloadUtils()
        self.userClient = userclient.UserClient()
        self.plx = PlexAPI.PlexAPI()
    
    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

    def GetPlexLogin(self):
        """
        Returns (myplexlogin, plexLogin, plexToken) from the Kodi file
        settings. Returns empty strings if not found.

        myplexlogin is 'true' if user opted to log into plex.tv
        """
        plexLogin = utils.settings('plexLogin')
        plexToken = utils.settings('plexToken')
        myplexlogin = utils.settings('myplexlogin')
        return (myplexlogin, plexLogin, plexToken)

    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        string = self.__language__
        addonId = self.addonId

        ##### SERVER INFO #####
        
        self.logMsg("Initial setup called.", 2)
        server = self.userClient.getServer()
        clientId = self.clientInfo.getDeviceId()
        serverid = self.userClient.getServerId()
        myplexlogin, plexLogin, plexToken = self.GetPlexLogin()

        # Optionally sign into plex.tv. Will not be called on very first run
        if plexToken and myplexlogin == 'true':
            chk = self.plx.CheckConnection('plex.tv', plexToken)
            # HTTP Error: unauthorized
            if chk == 401:
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    self.addonName,
                    'Could not login to plex.tv.',
                    'Please try signing in again.'
                )
                plexLogin, plexToken = self.plx.GetPlexLoginAndPassword()
            elif chk == "":
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    self.addonName,
                    'Problems connecting to plex.tv.',
                    'Network or internet issue?'
                )
        # If a Plex server IP has already been set, return.
        if server:
            self.logMsg("Server is already set.", 2)
            self.logMsg(
                "url: %s, Plex machineIdentifier: %s"
                % (server, serverid),
                2
            )
            return

        # If not already retrieved myplex info, optionally let user sign in
        # to plex.tv.
        if not plexToken and myplexlogin == 'true':
            plexLogin, plexToken = self.plx.GetPlexLoginAndPassword()
        # Get g_PMS list of servers (saved to plx.g_PMS)
        serverNum = 1
        while serverNum > 0:
            if plexToken:
                tokenDict = {'MyPlexToken': plexToken}
            else:
                tokenDict = {}
            # Populate g_PMS variable with the found Plex servers
            self.plx.discoverPMS(
                clientId,
                None,
                xbmc.getIPAddress(),
                tokenDict=tokenDict
            )
            self.logMsg("Result of setting g_PMS variable: %s" % self.plx.g_PMS, 2)
            isconnected = False
            serverlist = self.plx.returnServerList(clientId, self.plx.g_PMS)
            # Let user pick server from a list
            # Get a nicer list
            dialoglist = []
            # Exit if no servers found
            serverNum = len(serverlist)
            if serverNum == 0:
                break
            for server in serverlist:
                dialoglist.append(str(server['name']) + ' (IP: ' + str(server['ip']) + ')')
            dialog = xbmcgui.Dialog()
            resp = dialog.select(
                'What Plex server would you like to connect to?',
                dialoglist)
            server = serverlist[resp]
            activeServer = server['machineIdentifier']
            url = server['scheme'] + '://' + server['ip'] + ':' + \
                server['port']
            # Deactive SSL verification if the server is local!
            if server['local'] == '1':
                self.addon.setSetting('sslverify', 'false')
                self.logMsg("Setting SSL verify to false, because server is local", 1)
            else:
                self.addon.setSetting('sslverify', 'true')
                self.logMsg("Setting SSL verify to true, because server is not local", 1)
            chk = self.plx.CheckConnection(url, server['accesstoken'])
            # Unauthorized
            if chk == 401:
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    self.addonName,
                    'Not yet authorized for Plex server %s' % str(server['name']),
                    'Please sign in to plex.tv.'
                )
                plexLogin, plexToken = self.plx.GetPlexLoginAndPassword()
                # Exit while loop if user cancels
                if plexLogin == '':
                    break
            # Problems connecting
            elif chk == '':
                dialog = xbmcgui.Dialog()
                resp = dialog.yesno(
                    self.addonName,
                    'Problems connecting to server.',
                    'Pick another server?'
                )
                # Exit while loop if user chooses No
                if not resp:
                    break
            # Otherwise: connection worked!
            else:
                isconnected = True
                break
        if not isconnected:
            # Enter Kodi settings instead
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return
        # Write to Kodi settings file
        self.addon.setSetting('serverid', activeServer)
        self.addon.setSetting('ipaddress', server['ip'])
        self.addon.setSetting('port', server['port'])
        if server['scheme'] == 'https':
            self.addon.setSetting('https', 'true')
        else:
            self.addon.setSetting('https', 'false')

        ##### USER INFO #####
        self.logMsg("Getting user list.", 1)
        # Get list of Plex home users
        users = self.plx.MyPlexListHomeUsers(plexToken)
        # Download users failed. Set username to Plex login
        if not users:
            utils.settings('username', value=plexLogin)
            self.logMsg("User download failed. Set username = plexlogin", 1)
        else:
            userlist = []
            for user in users:
                username = user['title']
                if user['admin'] == '1':
                    username = username + " (admin)"
                userlist.append(username)
            dialog = xbmcgui.Dialog()
            user_select = dialog.select(string(30200), userlist)
            if user_select > -1:
                selected_user = userlist[user_select]
                self.logMsg("Selected user: %s" % selected_user, 1)
                utils.settings('username', value=selected_user)
            else:
                self.logMsg("No user selected.", 1)
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)

        ##### ADDITIONAL PROMPTS #####
        dialog = xbmcgui.Dialog()

        directPaths = dialog.yesno(
                            heading="%s: Playback Mode" % self.addonName,
                            line1=(
                                "Caution! If you choose Native mode, you "
                                "will probably lose access to certain Plex "
                                "features."),
                            nolabel="Addon (Default)",
                            yeslabel="Native (Direct Paths)")
        if directPaths:
            self.logMsg("User opted to use direct paths.", 1)
            utils.settings('useDirectPaths', value="1")

        musicDisabled = dialog.yesno(
                            heading="%s: Music Library" % self.addonName,
                            line1="Disable Plex music library?")
        if musicDisabled:
            self.logMsg("User opted to disable Plex music library.", 1)
            utils.settings('enableMusic', value="false")
        else:
            # Only prompt if the user didn't select direct paths for videos
            if not directPaths:
                musicAccess = dialog.yesno(
                                    heading="%s: Music Library" % self.addonName,
                                    line1=(
                                        "Direct stream the music library? Select "
                                        "this option only if you plan on listening "
                                        "to music outside of your network."))
                if musicAccess:
                    self.logMsg("User opted to direct stream music.", 1)
                    utils.settings('streamMusic', value="true")
                
    def getServerDetails(self):

        self.logMsg("Getting Server Details from Network", 1)
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        self.logMsg("MultiGroup      : %s" % str(MULTI_GROUP), 2);
        self.logMsg("Sending UDP Data: %s" % MESSAGE, 2);
        sock.sendto(MESSAGE, MULTI_GROUP)
    
        try:
            data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
            self.logMsg("Received Response: %s" % data)
        except:
            self.logMsg("No UDP Response")
            return None
        else:
            # Get the address
            data = json.loads(data)
            return data['Address']
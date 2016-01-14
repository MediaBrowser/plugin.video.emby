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

    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        string = self.__language__
        addonId = self.addonId

        ##### SERVER INFO #####
        
        self.logMsg("Initial setup called.", 0)
        server = self.userClient.getServer()
        clientId = self.clientInfo.getDeviceId()
        serverid = self.userClient.getServerId()
        myplexlogin, plexLogin, plexToken = self.plx.GetPlexLoginFromSettings()

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
                result = self.plx.PlexTvSignInWithPin()
                if result:
                    plexLogin = result['username']
                    plexToken = result['token']
            elif chk == "":
                dialog = xbmcgui.Dialog()
                dialog.ok(
                    self.addonName,
                    'Problems connecting to plex.tv.',
                    'Network or internet issue?'
                )
        # If a Plex server IP has already been set, return.
        if server:
            self.logMsg("Server is already set.", 0)
            self.logMsg(
                "url: %s, Plex machineIdentifier: %s"
                % (server, serverid),
                0)
            return

        # If not already retrieved myplex info, optionally let user sign in
        # to plex.tv.
        if not plexToken and myplexlogin == 'true':
            result = self.plx.PlexTvSignInWithPin()
            if result:
                plexLogin = result['username']
                plexToken = result['token']
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
                if server['local'] == '1':
                    # server is in the same network as client
                    dialoglist.append(str(server['name']) + ' (nearby)')
                else:
                    dialoglist.append(str(server['name']))
            dialog = xbmcgui.Dialog()
            resp = dialog.select(
                'Plex server to connect to?',
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
                dialog.ok(
                    self.addonName,
                    'Not yet authorized for Plex server %s' % str(server['name']),
                    'Please sign in to plex.tv.'
                )
                result = self.plx.PlexTvSignInWithPin()
                if result:
                    plexLogin = result['username']
                    plexToken = result['token']
                else:
                    # Exit while loop if user cancels
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

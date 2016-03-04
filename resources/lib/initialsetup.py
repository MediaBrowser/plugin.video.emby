# -*- coding: utf-8 -*-

###############################################################################

import xbmc
import xbmcgui
import xbmcaddon

import utils
import clientinfo
import downloadutils
import userclient

import PlexAPI

###############################################################################


@utils.logging
class InitialSetup():

    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.__language__ = self.addon.getLocalizedString

        self.clientInfo = clientinfo.ClientInfo()
        self.addonId = self.clientInfo.getAddonId()
        self.doUtils = downloadutils.DownloadUtils()
        self.userClient = userclient.UserClient()
        self.plx = PlexAPI.PlexAPI()

    def setup(self, forcePlexTV=False):
        """
        Initial setup. Run once upon startup.
        Check server, user, direct paths, music, direct stream if not direct
        path.
        """
        string = self.__language__
        # SERVER INFO #####
        self.logMsg("Initial setup called.", 0)
        server = self.userClient.getServer()
        clientId = self.clientInfo.getDeviceId()
        serverid = utils.settings('plex_machineIdentifier')
        # Get Plex credentials from settings file, if they exist
        plexdict = self.plx.GetPlexLoginFromSettings()
        myplexlogin = plexdict['myplexlogin']
        plexLogin = plexdict['plexLogin']
        plexToken = plexdict['plexToken']
        plexid = plexdict['plexid']
        self.logMsg('Plex info retrieved from settings: %s' % plexdict, 1)

        dialog = xbmcgui.Dialog()

        # Optionally sign into plex.tv. Will not be called on very first run
        # as plexToken will be ''
        if (plexToken and myplexlogin == 'true' and forcePlexTV is False):
            chk = self.plx.CheckConnection('plex.tv', plexToken)
            # HTTP Error: unauthorized. Token is no longer valid
            if chk == 401:
                # Delete token in the settings
                utils.settings('plexToken', value='')
                # Could not login, please try again
                dialog.ok(
                    self.addonName,
                    string(39009)
                )
                result = self.plx.PlexTvSignInWithPin()
                if result:
                    plexLogin = result['username']
                    plexToken = result['token']
                    plexid = result['plexid']
            elif chk is False or chk >= 400:
                # Problems connecting to plex.tv. Network or internet issue?
                dialog.ok(
                    self.addonName,
                    string(39010)
                )
        # If a Plex server IP has already been set, return.
        if server and forcePlexTV is False:
            self.logMsg("Server is already set.", 0)
            self.logMsg("url: %s, Plex machineIdentifier: %s"
                        % (server, serverid), 0)
            return

        # If not already retrieved myplex info, optionally let user sign in
        # to plex.tv. This DOES get called on very first install run
        if ((not plexToken and myplexlogin == 'true') or forcePlexTV):
            result = self.plx.PlexTvSignInWithPin()
            if result:
                plexLogin = result['username']
                plexToken = result['token']
                plexid = result['plexid']
        # Get g_PMS list of servers (saved to plx.g_PMS)
        while True:
            tokenDict = {'MyPlexToken': plexToken} if plexToken else {}
            # Populate g_PMS variable with the found Plex servers
            self.plx.discoverPMS(clientId,
                                 None,
                                 xbmc.getIPAddress(),
                                 tokenDict=tokenDict)
            self.logMsg("Result of setting g_PMS variable: %s"
                        % self.plx.g_PMS, 2)
            isconnected = False
            serverlist = self.plx.returnServerList(clientId, self.plx.g_PMS)
            # Let user pick server from a list
            # Get a nicer list
            dialoglist = []
            # Exit if no servers found
            if len(serverlist) == 0:
                dialog.ok(
                    self.addonName,
                    string(39011)
                )
                break
            for server in serverlist:
                if server['local'] == '1':
                    # server is in the same network as client. Add "local"
                    dialoglist.append(str(server['name']) + string(39022))
                else:
                    dialoglist.append(str(server['name']))
            resp = dialog.select(
                string(39012),
                dialoglist)
            server = serverlist[resp]
            activeServer = server['machineIdentifier']
            url = server['scheme'] + '://' + server['ip'] + ':' + \
                server['port']
            # Deactive SSL verification if the server is local!
            if server['local'] == '1':
                utils.settings('sslverify', 'false')
                self.logMsg("Setting SSL verify to false, because server is "
                            "local", 1)
            else:
                utils.settings('sslverify', 'true')
                self.logMsg("Setting SSL verify to true, because server is "
                            "not local", 1)
            chk = self.plx.CheckConnection(url, server['accesstoken'])
            # Unauthorized
            if chk == 401:
                # Not yet authorized for Plex server
                # Please sign in to plex.tv
                dialog.ok(self.addonName,
                          string(39013) + str(server['name']),
                          string(39014))
                result = self.plx.PlexTvSignInWithPin()
                if result:
                    plexLogin = result['username']
                    plexToken = result['token']
                    plexid = result['plexid']
                else:
                    # Exit while loop if user cancels
                    break
            # Problems connecting
            elif chk >= 400 or chk is False:
                # Problems connecting to server. Pick another server?
                resp = dialog.yesno(self.addonName, string(39015))
                # Exit while loop if user chooses No
                if not resp:
                    break
            # Otherwise: connection worked!
            else:
                isconnected = True
                break
        if not isconnected:
            # Enter Kodi settings instead
            if dialog.yesno(
                    heading=self.addonName,
                    line1=string(39016)):
                self.logMsg("User opted to disable Plex music library.", 1)
                utils.settings('enableMusic', value="false")
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return
        # Write to Kodi settings file
        utils.settings('plex_machineIdentifier', activeServer)
        utils.settings('ipaddress', server['ip'])
        utils.settings('port', server['port'])
        if server['scheme'] == 'https':
            utils.settings('https', 'true')
        else:
            utils.settings('https', 'false')
        self.logMsg("Writing to Kodi user settings file", 0)
        self.logMsg("PMS machineIdentifier: %s, ip: %s, port: %s, https: %s "
                    % (activeServer, server['ip'], server['port'],
                        server['scheme']), 0)

        # ADDITIONAL PROMPTS #####
        # directPaths = dialog.yesno(
        #                     heading="%s: Playback Mode" % self.addonName,
        #                     line1=(
        #                         "Caution! If you choose Native mode, you "
        #                         "will probably lose access to certain Plex "
        #                         "features."),
        #                     nolabel="Addon (Default)",
        #                     yeslabel="Native (Direct Paths)")
        # if directPaths:
        #     self.logMsg("User opted to use direct paths.", 1)
        #     utils.settings('useDirectPaths', value="1")

        if forcePlexTV:
            return

        if dialog.yesno(
                heading=self.addonName,
                line1=string(39016)):
            self.logMsg("User opted to disable Plex music library.", 1)
            utils.settings('enableMusic', value="false")

        if dialog.yesno(
                heading=self.addonName,
                line1=string(39017)):
            xbmc.executebuiltin(
                'Addon.OpenSettings(plugin.video.plexkodiconnect)')

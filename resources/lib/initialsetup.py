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
from PlexFunctions import GetMachineIdentifier

###############################################################################


@utils.logging
class InitialSetup():

    def __init__(self):
        self.logMsg('Entering initialsetup class', 1)
        self.clientInfo = clientinfo.ClientInfo()
        self.addonId = self.clientInfo.getAddonId()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.userClient = userclient.UserClient()
        self.plx = PlexAPI.PlexAPI()
        self.dialog = xbmcgui.Dialog()

        self.string = xbmcaddon.Addon().getLocalizedString

        self.server = self.userClient.getServer()
        self.serverid = utils.settings('plex_machineIdentifier')
        # Get Plex credentials from settings file, if they exist
        plexdict = self.plx.GetPlexLoginFromSettings()
        self.myplexlogin = plexdict['myplexlogin'] == 'true'
        self.plexLogin = plexdict['plexLogin']
        self.plexToken = plexdict['plexToken']
        self.plexid = plexdict['plexid']
        if self.plexToken:
            self.logMsg('Found a plex.tv token in the settings', 1)

    def PlexTVSignIn(self):
        """
        Signs (freshly) in to plex.tv (will be saved to file settings)

        Returns True if successful, or False if not
        """
        result = self.plx.PlexTvSignInWithPin()
        if result:
            self.plexLogin = result['username']
            self.plexToken = result['token']
            self.plexid = result['plexid']
            return True
        return False

    def CheckPlexTVSignIn(self):
        """
        Checks existing connection to plex.tv. If not, triggers sign in

        Returns True if signed in, False otherwise
        """
        answer = True
        chk = self.plx.CheckConnection('plex.tv', token=self.plexToken)
        if chk in (401, 403):
            # HTTP Error: unauthorized. Token is no longer valid
            self.logMsg('plex.tv connection returned HTTP %s' % str(chk), 1)
            # Delete token in the settings
            utils.settings('plexToken', value='')
            utils.settings('plexLogin', value='')
            # Could not login, please try again
            self.dialog.ok(self.addonName,
                           self.string(39009))
            answer = self.PlexTVSignIn()
        elif chk is False or chk >= 400:
            # Problems connecting to plex.tv. Network or internet issue?
            self.logMsg('Problems connecting to plex.tv; connection returned '
                        'HTTP %s' % str(chk), 1)
            self.dialog.ok(self.addonName,
                           self.string(39010))
            answer = False
        else:
            self.logMsg('plex.tv connection with token successful', 1)
            utils.settings('plex_status', value='Logged in to plex.tv')
            # Refresh the info from Plex.tv
            xml = self.doUtils('https://plex.tv/users/account',
                               authenticate=False,
                               headerOptions={'X-Plex-Token': self.plexToken})
            try:
                self.plexLogin = xml.attrib['title']
            except (AttributeError, KeyError):
                self.logMsg('Failed to update Plex info from plex.tv', -1)
            else:
                utils.settings('plexLogin', value=self.plexLogin)
                home = 'true' if xml.attrib.get('home') == '1' else 'false'
                utils.settings('plexhome', value=home)
                utils.settings('plexAvatar', value=xml.attrib.get('thumb'))
                utils.settings(
                    'plexHomeSize', value=xml.attrib.get('homeSize', '1'))
                self.logMsg('Updated Plex info from plex.tv', 1)
        return answer

    def CheckPMS(self):
        """
        Check the PMS that was set in file settings.
        Will return False if we need to reconnect, because:
            PMS could not be reached (no matter the authorization)
            machineIdentifier did not match

        Will also set the PMS machineIdentifier in the file settings if it was
        not set before
        """
        answer = True
        chk = self.plx.CheckConnection(self.server,
                                       verifySSL=False)
        if chk is False:
            self.logMsg('Could not reach PMS %s' % self.server, -1)
            answer = False
        if answer is True and not self.serverid:
            self.logMsg('No PMS machineIdentifier found for %s. Trying to '
                        'get the PMS unique ID' % self.server, 1)
            self.serverid = GetMachineIdentifier(self.server)
            if self.serverid is None:
                self.logMsg('Could not retrieve machineIdentifier', -1)
                answer = False
            else:
                utils.settings('plex_machineIdentifier', value=self.serverid)
        elif answer is True:
            tempServerid = GetMachineIdentifier(self.server)
            if tempServerid != self.serverid:
                self.logMsg('The current PMS %s was expected to have a '
                            'unique machineIdentifier of %s. But we got '
                            '%s. Pick a new server to be sure'
                            % (self.server, self.serverid, tempServerid), 1)
                answer = False
        return answer

    def __getServerList(self):
        """
        Returns a list of servers from GDM and possibly plex.tv
        """
        self.plx.discoverPMS(xbmc.getIPAddress(),
                             plexToken=self.plexToken)
        serverlist = self.plx.returnServerList(self.plx.g_PMS)
        self.logMsg('PMS serverlist: %s' % serverlist, 2)
        return serverlist

    def __checkServerCon(self, server):
        """
        Checks for server's connectivity. Returns CheckConnection result
        """
        # Re-direct via plex if remote - will lead to the correct SSL
        # certificate
        if server['local'] == '1':
            url = '%s://%s:%s' \
                  % (server['scheme'], server['ip'], server['port'])
            # Deactive SSL verification if the server is local!
            verifySSL = False
        else:
            url = server['baseURL']
            verifySSL = None
        chk = self.plx.CheckConnection(url,
                                       token=server['accesstoken'],
                                       verifySSL=verifySSL)
        return chk

    def PickPMS(self, showDialog=False):
        """
        Searches for PMS in local Lan and optionally (if self.plexToken set)
        also on plex.tv
            showDialog=True: let the user pick one
            showDialog=False: automatically pick PMS based on machineIdentifier

        Returns the picked PMS' detail as a dict:
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
        'ownername'                 Plex username of PMS owner
        }

        or None if unsuccessful
        """
        server = None
        # If no server is set, let user choose one
        if not self.server or not self.serverid:
            showDialog = True
        if showDialog is True:
            server = self.__UserPickPMS()
        else:
            server = self.__AutoPickPMS()
        return server

    def __AutoPickPMS(self):
        """
        Will try to pick PMS based on machineIdentifier saved in file settings
        but only once

        Returns server or None if unsuccessful
        """
        httpsUpdated = False
        checkedPlexTV = False
        server = None
        while True:
            if httpsUpdated is False:
                serverlist = self.__getServerList()
                for item in serverlist:
                    if item.get('machineIdentifier') == self.serverid:
                        server = item
                if server is None:
                    name = utils.settings('plex_servername')
                    self.logMsg('The PMS you have used before with a unique '
                                'machineIdentifier of %s and name %s is '
                                'offline' % (self.serverid, name), -1)
                    # "PMS xyz offline"
                    self.dialog.notification(self.addonName,
                                             '%s %s'
                                             % (name, self.string(39213)),
                                             xbmcgui.NOTIFICATION_ERROR,
                                             7000,
                                             False)
                    return
            chk = self.__checkServerCon(server)
            if chk == 504 and httpsUpdated is False:
                # Not able to use HTTP, try HTTPs for now
                server['scheme'] = 'https'
                httpsUpdated = True
                continue
            if chk == 401:
                self.logMsg('Not yet authorized for Plex server %s'
                            % server['name'], -1)
                if self.CheckPlexTVSignIn() is True:
                    if checkedPlexTV is False:
                        # Try again
                        checkedPlexTV = True
                        httpsUpdated = False
                        continue
                    else:
                        self.logMsg('Not authorized even though we are signed '
                                    ' in to plex.tv correctly', -1)
                        self.dialog.ok(self.addonName, '%s %s'
                                       % self.string(39214) + server['name'])
                        return
                else:
                    return
            # Problems connecting
            elif chk >= 400 or chk is False:
                self.logMsg('Problems connecting to server %s. chk is %s'
                            % (server['name'], chk), -1)
                return
            self.logMsg('We found a server to automatically connect to: %s'
                        % server['name'], 1)
            return server

    def __UserPickPMS(self):
        """
        Lets user pick his/her PMS from a list

        Returns server or None if unsuccessful
        """
        httpsUpdated = False
        while True:
            if httpsUpdated is False:
                serverlist = self.__getServerList()
                # Exit if no servers found
                if len(serverlist) == 0:
                    self.logMsg('No plex media servers found!', -1)
                    self.dialog.ok(self.addonName, self.string(39011))
                    return
                # Get a nicer list
                dialoglist = []
                for server in serverlist:
                    if server['local'] == '1':
                        # server is in the same network as client.
                        # Add"local"
                        msg = self.string(39022)
                    else:
                        # Add 'remote'
                        msg = self.string(39054)
                    if server.get('ownername'):
                        # Display username if its not our PMS
                        dialoglist.append('%s (%s, %s)'
                                          % (server['name'],
                                             server['ownername'],
                                             msg))
                    else:
                        dialoglist.append('%s (%s)'
                                          % (server['name'], msg))
                # Let user pick server from a list
                resp = self.dialog.select(self.string(39012), dialoglist)

            server = serverlist[resp]
            chk = self.__checkServerCon(server)
            if chk == 504 and httpsUpdated is False:
                # Not able to use HTTP, try HTTPs for now
                serverlist[resp]['scheme'] = 'https'
                httpsUpdated = True
                continue
            httpsUpdated = False
            if chk == 401:
                self.logMsg('Not yet authorized for Plex server %s'
                            % server['name'], -1)
                # Please sign in to plex.tv
                self.dialog.ok(self.addonName,
                               self.string(39013) + server['name'],
                               self.string(39014))
                if self.PlexTVSignIn() is False:
                    # Exit while loop if user cancels
                    return
            # Problems connecting
            elif chk >= 400 or chk is False:
                # Problems connecting to server. Pick another server?
                answ = self.dialog.yesno(self.addonName,
                                         self.string(39015))
                # Exit while loop if user chooses No
                if not answ:
                    return
            # Otherwise: connection worked!
            else:
                return server

    def WritePMStoSettings(self, server):
        """
        Saves server to file settings. server is a dict of the form:
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
        'ownername'                 Plex username of PMS owner
        }
        """
        utils.settings('plex_machineIdentifier', server['machineIdentifier'])
        utils.settings('plex_servername', server['name'])
        utils.settings('plex_serverowned',
                       'true' if server['owned'] == '1'
                       else 'false')
        # Careful to distinguish local from remote PMS
        if server['local'] == '1':
            scheme = server['scheme']
            utils.settings('ipaddress', server['ip'])
            utils.settings('port', server['port'])
            self.logMsg("Setting SSL verify to false, because server is "
                        "local", 1)
            utils.settings('sslverify', 'false')
        else:
            baseURL = server['baseURL'].split(':')
            scheme = baseURL[0]
            utils.settings('ipaddress', baseURL[1].replace('//', ''))
            utils.settings('port', baseURL[2])
            self.logMsg("Setting SSL verify to true, because server is not "
                        "local", 1)
            utils.settings('sslverify', 'true')

        if scheme == 'https':
            utils.settings('https', 'true')
        else:
            utils.settings('https', 'false')
        # And finally do some logging
        self.logMsg("Writing to Kodi user settings file", 0)
        self.logMsg("PMS machineIdentifier: %s, ip: %s, port: %s, https: %s "
                    % (server['machineIdentifier'], server['ip'],
                       server['port'], server['scheme']), 0)

    def setup(self):
        """
        Initial setup. Run once upon startup.

        Check server, user, direct paths, music, direct stream if not direct
        path.
        """
        self.logMsg("Initial setup called.", 0)
        dialog = self.dialog
        string = self.string

        # Optionally sign into plex.tv. Will not be called on very first run
        # as plexToken will be ''
        utils.settings('plex_status', value='Not logged in to plex.tv')
        if self.plexToken and self.myplexlogin:
            self.CheckPlexTVSignIn()

        # If a Plex server IP has already been set
        # return only if the right machine identifier is found
        getNewIP = False
        if self.server:
            self.logMsg("PMS is already set: %s. Checking now..."
                        % self.server, 0)
            getNewIP = not self.CheckPMS()
            if getNewIP is False:
                self.logMsg("Using PMS %s with machineIdentifier %s"
                            % (self.server, self.serverid), 0)
                return

        # If not already retrieved myplex info, optionally let user sign in
        # to plex.tv. This DOES get called on very first install run
        if not self.plexToken and self.myplexlogin:
            self.PlexTVSignIn()

        server = self.PickPMS()
        if server is not None:
            goToSettings = False
            # Write our chosen server to Kodi settings file
            self.WritePMStoSettings(server)
        else:
            goToSettings = True

        # User already answered the installation questions
        if utils.settings('InstallQuestionsAnswered') == 'true':
            if goToSettings:
                xbmc.executebuiltin(
                    'Addon.OpenSettings(plugin.video.plexkodiconnect)')
            return

        # Additional settings where the user needs to choose
        # Direct paths (\\NAS\mymovie.mkv) or addon (http)?
        if dialog.yesno(self.addonName,
                        string(39027),
                        string(39028),
                        nolabel="Addon (Default)",
                        yeslabel="Native (Direct Paths)"):
            self.logMsg("User opted to use direct paths.", 1)
            utils.settings('useDirectPaths', value="1")
            # Are you on a system where you would like to replace paths
            # \\NAS\mymovie.mkv with smb://NAS/mymovie.mkv? (e.g. Windows)
            if dialog.yesno(heading=self.addonName,
                            line1=string(39033)):
                self.logMsg("User chose to replace paths with smb", 1)
            else:
                utils.settings('replaceSMB', value="false")

            # complete replace all original Plex library paths with custom SMB
            if dialog.yesno(heading=self.addonName,
                            line1=string(39043)):
                self.logMsg("User chose custom smb paths", 1)
                utils.settings('remapSMB', value="true")
                # Please enter your custom smb paths in the settings under
                # "Sync Options" and then restart Kodi
                dialog.ok(heading=self.addonName,
                          line1=string(39044))
                goToSettings = True

            # Go to network credentials?
            if dialog.yesno(heading=self.addonName,
                            line1=string(39029),
                            line2=string(39030)):
                self.logMsg("Presenting network credentials dialog.", 1)
                utils.passwordsXML()
        # Disable Plex music?
        if dialog.yesno(heading=self.addonName,
                        line1=string(39016)):
            self.logMsg("User opted to disable Plex music library.", 1)
            utils.settings('enableMusic', value="false")
        else:
            utils.advancedSettingsXML()

        # Download additional art from FanArtTV
        if dialog.yesno(heading=self.addonName,
                        line1=string(39061)):
            self.logMsg("User opted to use FanArtTV", 1)
            utils.settings('FanartTV', value="true")

        # Is your Kodi installed on a low-powered device like a Raspberry Pi?
        # If yes, then we will reduce the strain on Kodi to prevent it from
        # crashing.
        if dialog.yesno(heading=self.addonName,
                        line1=string(39072)):
            self.logMsg('User thinks that PKC runs on a raspi or similar', 1)
            utils.settings('imageCacheLimit', value='1')

        # Make sure that we only ask these questions upon first installation
        utils.settings('InstallQuestionsAnswered', value='true')

        if goToSettings is False:
            # Open Settings page now? You will need to restart!
            goToSettings = dialog.yesno(heading=self.addonName,
                                        line1=string(39017))
        if goToSettings:
            utils.window('plex_serverStatus', value="Stop")
            xbmc.executebuiltin(
                'Addon.OpenSettings(plugin.video.plexkodiconnect)')
        else:
            # "Kodi will now restart to apply the changes"
            dialog.ok(
                heading=self.addonName,
                line1=string(33033))
            xbmc.executebuiltin('RestartApp')
        # We should always restart to ensure e.g. Kodi settings for Music
        # are in use!

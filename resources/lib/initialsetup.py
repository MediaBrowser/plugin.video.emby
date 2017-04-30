# -*- coding: utf-8 -*-

###############################################################################

import logging
import xbmc
import xbmcgui

from utils import settings, window, language as lang, tryEncode
import downloadutils
from userclient import UserClient

from PlexAPI import PlexAPI
from PlexFunctions import GetMachineIdentifier, get_PMS_settings

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class InitialSetup():

    def __init__(self):
        log.debug('Entering initialsetup class')
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.plx = PlexAPI()
        self.dialog = xbmcgui.Dialog()

        self.server = UserClient().getServer()
        self.serverid = settings('plex_machineIdentifier')
        # Get Plex credentials from settings file, if they exist
        plexdict = self.plx.GetPlexLoginFromSettings()
        self.myplexlogin = plexdict['myplexlogin'] == 'true'
        self.plexLogin = plexdict['plexLogin']
        self.plexToken = plexdict['plexToken']
        self.plexid = plexdict['plexid']
        # Token for the PMS, not plex.tv
        self.pms_token = settings('accessToken')
        if self.plexToken:
            log.debug('Found a plex.tv token in the settings')

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
            log.info('plex.tv connection returned HTTP %s' % str(chk))
            # Delete token in the settings
            settings('plexToken', value='')
            settings('plexLogin', value='')
            # Could not login, please try again
            self.dialog.ok(lang(29999), lang(39009))
            answer = self.PlexTVSignIn()
        elif chk is False or chk >= 400:
            # Problems connecting to plex.tv. Network or internet issue?
            log.info('Problems connecting to plex.tv; connection returned '
                     'HTTP %s' % str(chk))
            self.dialog.ok(lang(29999), lang(39010))
            answer = False
        else:
            log.info('plex.tv connection with token successful')
            settings('plex_status', value='Logged in to plex.tv')
            # Refresh the info from Plex.tv
            xml = self.doUtils('https://plex.tv/users/account',
                               authenticate=False,
                               headerOptions={'X-Plex-Token': self.plexToken})
            try:
                self.plexLogin = xml.attrib['title']
            except (AttributeError, KeyError):
                log.error('Failed to update Plex info from plex.tv')
            else:
                settings('plexLogin', value=self.plexLogin)
                home = 'true' if xml.attrib.get('home') == '1' else 'false'
                settings('plexhome', value=home)
                settings('plexAvatar', value=xml.attrib.get('thumb'))
                settings('plexHomeSize', value=xml.attrib.get('homeSize', '1'))
                log.info('Updated Plex info from plex.tv')
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
        chk = self.plx.CheckConnection(self.server, verifySSL=False)
        if chk is False:
            log.warn('Could not reach PMS %s' % self.server)
            answer = False
        if answer is True and not self.serverid:
            log.info('No PMS machineIdentifier found for %s. Trying to '
                     'get the PMS unique ID' % self.server)
            self.serverid = GetMachineIdentifier(self.server)
            if self.serverid is None:
                log.warn('Could not retrieve machineIdentifier')
                answer = False
            else:
                settings('plex_machineIdentifier', value=self.serverid)
        elif answer is True:
            tempServerid = GetMachineIdentifier(self.server)
            if tempServerid != self.serverid:
                log.warn('The current PMS %s was expected to have a '
                         'unique machineIdentifier of %s. But we got '
                         '%s. Pick a new server to be sure'
                         % (self.server, self.serverid, tempServerid))
                answer = False
        return answer

    def _getServerList(self):
        """
        Returns a list of servers from GDM and possibly plex.tv
        """
        self.plx.discoverPMS(xbmc.getIPAddress(),
                             plexToken=self.plexToken)
        serverlist = self.plx.returnServerList(self.plx.g_PMS)
        log.debug('PMS serverlist: %s' % serverlist)
        return serverlist

    def _checkServerCon(self, server):
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
            server = self._UserPickPMS()
        else:
            server = self._AutoPickPMS()
        if server is not None:
            self._write_PMS_settings(server['baseURL'], server['accesstoken'])
        return server

    def _write_PMS_settings(self, url, token):
        """
        Sets certain settings for server by asking for the PMS' settings
        Call with url: scheme://ip:port
        """
        xml = get_PMS_settings(url, token)
        try:
            xml.attrib
        except AttributeError:
            log.error('Could not get PMS settings for %s' % url)
            return
        for entry in xml:
            if entry.attrib.get('id', '') == 'allowMediaDeletion':
                settings('plex_allows_mediaDeletion',
                         value=entry.attrib.get('value', 'true'))
                window('plex_allows_mediaDeletion',
                       value=entry.attrib.get('value', 'true'))

    def _AutoPickPMS(self):
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
                serverlist = self._getServerList()
                for item in serverlist:
                    if item.get('machineIdentifier') == self.serverid:
                        server = item
                if server is None:
                    name = settings('plex_servername')
                    log.warn('The PMS you have used before with a unique '
                             'machineIdentifier of %s and name %s is '
                             'offline' % (self.serverid, name))
                    return
            chk = self._checkServerCon(server)
            if chk == 504 and httpsUpdated is False:
                # Not able to use HTTP, try HTTPs for now
                server['scheme'] = 'https'
                httpsUpdated = True
                continue
            if chk == 401:
                log.warn('Not yet authorized for Plex server %s'
                         % server['name'])
                if self.CheckPlexTVSignIn() is True:
                    if checkedPlexTV is False:
                        # Try again
                        checkedPlexTV = True
                        httpsUpdated = False
                        continue
                    else:
                        log.warn('Not authorized even though we are signed '
                                 ' in to plex.tv correctly')
                        self.dialog.ok(lang(29999), '%s %s'
                                       % (lang(39214),
                                          tryEncode(server['name'])))
                        return
                else:
                    return
            # Problems connecting
            elif chk >= 400 or chk is False:
                log.warn('Problems connecting to server %s. chk is %s'
                         % (server['name'], chk))
                return
            log.info('We found a server to automatically connect to: %s'
                     % server['name'])
            return server

    def _UserPickPMS(self):
        """
        Lets user pick his/her PMS from a list

        Returns server or None if unsuccessful
        """
        httpsUpdated = False
        while True:
            if httpsUpdated is False:
                serverlist = self._getServerList()
                # Exit if no servers found
                if len(serverlist) == 0:
                    log.warn('No plex media servers found!')
                    self.dialog.ok(lang(29999), lang(39011))
                    return
                # Get a nicer list
                dialoglist = []
                for server in serverlist:
                    if server['local'] == '1':
                        # server is in the same network as client.
                        # Add"local"
                        msg = lang(39022)
                    else:
                        # Add 'remote'
                        msg = lang(39054)
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
                resp = self.dialog.select(lang(39012), dialoglist)
                if resp == -1:
                    # User cancelled
                    return

            server = serverlist[resp]
            chk = self._checkServerCon(server)
            if chk == 504 and httpsUpdated is False:
                # Not able to use HTTP, try HTTPs for now
                serverlist[resp]['scheme'] = 'https'
                httpsUpdated = True
                continue
            httpsUpdated = False
            if chk == 401:
                log.warn('Not yet authorized for Plex server %s'
                         % server['name'])
                # Please sign in to plex.tv
                self.dialog.ok(lang(29999),
                               lang(39013) + server['name'],
                               lang(39014))
                if self.PlexTVSignIn() is False:
                    # Exit while loop if user cancels
                    return
            # Problems connecting
            elif chk >= 400 or chk is False:
                # Problems connecting to server. Pick another server?
                answ = self.dialog.yesno(lang(29999),
                                         lang(39015))
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
        settings('plex_machineIdentifier', server['machineIdentifier'])
        settings('plex_servername', server['name'])
        settings('plex_serverowned',
                 'true' if server['owned'] == '1'
                 else 'false')
        # Careful to distinguish local from remote PMS
        if server['local'] == '1':
            scheme = server['scheme']
            settings('ipaddress', server['ip'])
            settings('port', server['port'])
            log.debug("Setting SSL verify to false, because server is "
                      "local")
            settings('sslverify', 'false')
        else:
            baseURL = server['baseURL'].split(':')
            scheme = baseURL[0]
            settings('ipaddress', baseURL[1].replace('//', ''))
            settings('port', baseURL[2])
            log.debug("Setting SSL verify to true, because server is not "
                      "local")
            settings('sslverify', 'true')

        if scheme == 'https':
            settings('https', 'true')
        else:
            settings('https', 'false')
        # And finally do some logging
        log.debug("Writing to Kodi user settings file")
        log.debug("PMS machineIdentifier: %s, ip: %s, port: %s, https: %s "
                  % (server['machineIdentifier'], server['ip'],
                     server['port'], server['scheme']))

    def setup(self):
        """
        Initial setup. Run once upon startup.

        Check server, user, direct paths, music, direct stream if not direct
        path.
        """
        log.info("Initial setup called.")
        dialog = self.dialog

        # Optionally sign into plex.tv. Will not be called on very first run
        # as plexToken will be ''
        settings('plex_status', value='Not logged in to plex.tv')
        if self.plexToken and self.myplexlogin:
            self.CheckPlexTVSignIn()

        # If a Plex server IP has already been set
        # return only if the right machine identifier is found
        if self.server:
            log.info("PMS is already set: %s. Checking now..." % self.server)
            if self.CheckPMS():
                log.info("Using PMS %s with machineIdentifier %s"
                         % (self.server, self.serverid))
                self._write_PMS_settings(self.server, self.pms_token)
                return

        # If not already retrieved myplex info, optionally let user sign in
        # to plex.tv. This DOES get called on very first install run
        if not self.plexToken and self.myplexlogin:
            self.PlexTVSignIn()

        server = self.PickPMS()
        if server is not None:
            # Write our chosen server to Kodi settings file
            self.WritePMStoSettings(server)

        # User already answered the installation questions
        if settings('InstallQuestionsAnswered') == 'true':
            return

        # Additional settings where the user needs to choose
        # Direct paths (\\NAS\mymovie.mkv) or addon (http)?
        goToSettings = False
        if dialog.yesno(lang(29999),
                        lang(39027),
                        lang(39028),
                        nolabel="Addon (Default)",
                        yeslabel="Native (Direct Paths)"):
            log.debug("User opted to use direct paths.")
            settings('useDirectPaths', value="1")
            # Are you on a system where you would like to replace paths
            # \\NAS\mymovie.mkv with smb://NAS/mymovie.mkv? (e.g. Windows)
            if dialog.yesno(heading=lang(29999), line1=lang(39033)):
                log.debug("User chose to replace paths with smb")
            else:
                settings('replaceSMB', value="false")

            # complete replace all original Plex library paths with custom SMB
            if dialog.yesno(heading=lang(29999), line1=lang(39043)):
                log.debug("User chose custom smb paths")
                settings('remapSMB', value="true")
                # Please enter your custom smb paths in the settings under
                # "Sync Options" and then restart Kodi
                dialog.ok(heading=lang(29999), line1=lang(39044))
                goToSettings = True

            # Go to network credentials?
            if dialog.yesno(heading=lang(29999),
                            line1=lang(39029),
                            line2=lang(39030)):
                log.debug("Presenting network credentials dialog.")
                from utils import passwordsXML
                passwordsXML()
        # Disable Plex music?
        if dialog.yesno(heading=lang(29999), line1=lang(39016)):
            log.debug("User opted to disable Plex music library.")
            settings('enableMusic', value="false")
        else:
            from utils import advancedSettingsXML
            advancedSettingsXML()

        # Download additional art from FanArtTV
        if dialog.yesno(heading=lang(29999), line1=lang(39061)):
            log.debug("User opted to use FanArtTV")
            settings('FanartTV', value="true")

        # If you use several Plex libraries of one kind, e.g. "Kids Movies" and
        # "Parents Movies", be sure to check https://goo.gl/JFtQV9
        dialog.ok(heading=lang(29999), line1=lang(39076))
        # Make sure that we only ask these questions upon first installation
        settings('InstallQuestionsAnswered', value='true')

        if goToSettings is False:
            # Open Settings page now? You will need to restart!
            goToSettings = dialog.yesno(heading=lang(29999), line1=lang(39017))
        if goToSettings:
            window('plex_serverStatus', value="Stop")
            xbmc.executebuiltin(
                'Addon.OpenSettings(plugin.video.plexkodiconnect)')
        else:
            # "Kodi will now restart to apply the changes"
            dialog.ok(heading=lang(29999), line1=lang(33033))
            xbmc.executebuiltin('RestartApp')
        # We should always restart to ensure e.g. Kodi settings for Music
        # are in use!

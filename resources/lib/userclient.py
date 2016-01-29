# -*- coding: utf-8 -*-

##################################################################################################

import threading

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import utils
import downloadutils

import PlexAPI

##################################################################################################


@utils.logging
@utils.ThreadMethods
class UserClient(threading.Thread):

    # Borg - multiple instances, shared state
    __shared_state = {}

    auth = True
    retry = 0

    currUser = None
    currUserId = None
    currServer = None
    currToken = None
    HasAccess = True
    AdditionalUser = []

    userSettings = None

    def __init__(self):

        self.__dict__ = self.__shared_state
        self.addon = xbmcaddon.Addon()

        self.doUtils = downloadutils.DownloadUtils()

        threading.Thread.__init__(self)

    def getAdditionalUsers(self):

        additionalUsers = utils.settings('additionalUsers')
        
        if additionalUsers:
            self.AdditionalUser = additionalUsers.split(',')

    def getUsername(self):

        username = utils.settings('username')

        if not username:
            self.logMsg("No username saved.", 2)
            return ""

        return username

    def getLogLevel(self):

        try:
            logLevel = int(utils.settings('logLevel'))
        except ValueError:
            logLevel = 0
        
        return logLevel

    def getUserId(self):

        username = self.getUsername()
        w_userId = utils.window('emby_userId%s' % username)
        s_userId = utils.settings('userId%s' % username)

        # Verify the window property
        if w_userId:
            if not s_userId:
                # Save access token if it's missing from settings
                utils.settings('userId%s' % username, value=w_userId)
            self.logMsg(
                "Returning userId from WINDOW for username: %s UserId: %s"
                % (username, w_userId), 2)
            return w_userId
        # Verify the settings
        elif s_userId:
            self.logMsg(
                "Returning userId from SETTINGS for username: %s userId: %s"
                % (username, s_userId), 2)
            return s_userId
        # No userId found
        else:
            self.logMsg("No userId saved for username: %s." % username, 1)

    def getServer(self, prefix=True):

        alternate = utils.settings('altip') == "true"
        if alternate:
            # Alternate host
            HTTPS = utils.settings('secondhttps') == "true"
            host = utils.settings('secondipaddress')
            port = utils.settings('secondport')
        else:
            # Original host
            HTTPS = utils.settings('https') == "true"
            host = utils.settings('ipaddress')
            port = utils.settings('port')

        server = host + ":" + port
        
        if not host:
            self.logMsg("No server information saved.", 2)
            return False

        # If https is true
        if prefix and HTTPS:
            server = "https://%s" % server
            return server
        # If https is false
        elif prefix and not HTTPS:
            server = "http://%s" % server
            return server
        # If only the host:port is required
        elif not prefix:
            return server

    def getServerId(self):
        serverId = utils.settings('plex_machineIdentifier')
        return serverId

    def getToken(self):

        username = self.getUsername()
        w_token = utils.window('emby_accessToken%s' % username)
        s_token = utils.settings('accessToken')
        
        # Verify the window property
        if w_token:
            if not s_token:
                # Save access token if it's missing from settings
                utils.settings('accessToken', value=w_token)
            self.logMsg("Returning accessToken from WINDOW for username: %s "
                        "accessToken: xxxxx" % username, 2)
            return w_token
        # Verify the settings
        elif s_token:
            self.logMsg("Returning accessToken from SETTINGS for username: %s "
                        "accessToken: xxxxx" % username, 2)
            utils.window('emby_accessToken%s' % username, value=s_token)
            return s_token
        else:
            self.logMsg("No token found.", 1)
            return ""

    def getSSLverify(self):
        # Verify host certificate
        s_sslverify = utils.settings('sslverify')
        if utils.settings('altip') == "true":
            s_sslverify = utils.settings('secondsslverify')

        if s_sslverify == "true":
            return True
        else:
            return False

    def getSSL(self):
        # Client side certificate
        s_cert = utils.settings('sslcert')
        if utils.settings('altip') == "true":
            s_cert = utils.settings('secondsslcert')

        if s_cert == "None":
            return None
        else:
            return s_cert

    def setUserPref(self):

        url = PlexAPI.PlexAPI().GetUserArtworkURL(self.currUser)
        if url:
            utils.window('EmbyUserImage', value=url)
        # Set resume point max
        # url = "{server}/emby/System/Configuration?format=json"
        # result = doUtils.downloadUrl(url)

        # utils.settings('markPlayed', value=str(result['MaxResumePct']))

    def getPublicUsers(self):

        server = self.getServer()

        # Get public Users
        url = "%s/emby/Users/Public?format=json" % server
        result = self.doUtils.downloadUrl(url, authenticate=False)
        
        if result != "":
            return result
        else:
            # Server connection failed
            return False

    def hasAccess(self):
        return True

    def loadCurrUser(self, authenticated=False):

        doUtils = self.doUtils
        username = self.getUsername()
        userId = self.getUserId()
        
        # Only to be used if token exists
        self.currUserId = userId
        self.currServer = self.getServer()
        self.currToken = self.getToken()
        self.machineIdentifier = self.getServerId()
        self.ssl = self.getSSLverify()
        self.sslcert = self.getSSL()

        # Test the validity of current token
        if authenticated == False:
            url = "%s/clients" % (self.currServer)
            utils.window('emby_currUser', value=userId)
            utils.window('emby_accessToken%s' % userId, value=self.currToken)
            result = doUtils.downloadUrl(url)

            if result == 401:
                # Token is no longer valid
                self.resetClient()
                return False

        # Set to windows property
        utils.window('emby_currUser', value=userId)
        utils.window('emby_accessToken%s' % userId, value=self.currToken)
        utils.window('emby_server%s' % userId, value=self.currServer)
        utils.window('emby_server_%s' % userId, value=self.getServer(prefix=False))
        utils.window('plex_machineIdentifier', value=self.machineIdentifier)

        # Set DownloadUtils values
        doUtils.setUsername(username)
        doUtils.setUserId(self.currUserId)
        doUtils.setServer(self.currServer)
        doUtils.setToken(self.currToken)
        doUtils.setSSL(self.ssl, self.sslcert)
        # parental control - let's verify if access is restricted
        # self.hasAccess()

        # Start DownloadUtils session
        doUtils.startSession()
        self.getAdditionalUsers()
        # Set user preferences in settings
        self.currUser = username
        self.setUserPref()
        return True

    def authenticate(self):
        # Get /profile/addon_data
        plx = PlexAPI.PlexAPI()
        addondir = xbmc.translatePath(self.addon.getAddonInfo('profile')).decode('utf-8')
        hasSettings = xbmcvfs.exists("%ssettings.xml" % addondir)

        username = self.getUsername()
        userId = utils.settings('userId%s' % username)
        server = self.getServer()

        # If there's no settings.xml
        if not hasSettings:
            self.logMsg("No settings.xml found.", 0)
            self.auth = False
            return
        # If no user information
        elif not server:
            self.logMsg("Missing server information.", 0)
            self.auth = False
            return
        # If there's a token, load the user
        elif self.getToken():
            result = self.loadCurrUser()

            if result == False:
                pass
            else:
                self.logMsg("Current user: %s" % self.currUser, 1)
                self.logMsg("Current userId: %s" % self.currUserId, 1)
                self.logMsg("Current accessToken: xxxx", 1)

                utils.window('suspend_LibraryThread', value='false')
                return

        ##### AUTHENTICATE USER #####
        # Choose Plex user login
        myplexlogin, plexhome, plexLogin, dont_use_accessToken = \
            plx.GetPlexLoginFromSettings()
        self.logMsg("myplexlogin: %s, plexhome: %s, plexLogin: %s"
                    % (myplexlogin, plexhome, plexLogin), 2)
        if myplexlogin == "true" and plexhome == 'true':
            username, userId, accessToken = plx.ChoosePlexHomeUser()
        else:
            self.logMsg("Trying to connect to PMS without a token", 0)
            accessToken = ''
        # Check connection
        if plx.CheckConnection(server, accessToken) == 200:
            self.currUser = username
            dialog = xbmcgui.Dialog()
            if username:
                dialog.notification(self.addonName,
                                    "Welcome %s" % username,
                                    "special://home/addons/plugin.video."
                                    "plexkodiconnect/icon.png")
            else:
                dialog.notification(self.addonName,
                                    "Welcome",
                                    "special://home/addons/plugin.video."
                                    "plexkodiconnect/icon.png")
            utils.settings('accessToken', value=accessToken)
            utils.settings('userId%s' % username, value=userId)
            self.logMsg("User authenticated with an access token", 1)
            self.loadCurrUser(authenticated=True)
            utils.window('emby_serverStatus', clear=True)
            # Write plex_machineIdentifier to window
            plex_machineIdentifier = utils.settings('plex_machineIdentifier')
            utils.window('plex_machineIdentifier', plex_machineIdentifier)
            self.retry = 0
            # Make sure that lib sync thread is not paused
            utils.window('suspend_LibraryThread', value='false')
        else:
            self.logMsg("Error: user authentication failed.", -1)
            utils.settings('accessToken', value="")
            utils.settings('userId%s' % username, value="")

            # Give 3 attempts at entering password / selecting user
            if self.retry == 3:
                utils.window('emby_serverStatus', value="Stop")
                xbmcgui.Dialog().ok(heading=self.addonName,
                                    line1="Failed to authenticate too many"
                                          "times.",
                                    line2="You can retry by resetting attempts"
                                          " in the addon settings.")
            self.retry += 1
            self.auth = False

    def resetClient(self):

        self.logMsg("Reset UserClient authentication.", 1)
        username = self.getUsername()

        utils.settings('accessToken', value="")
        utils.window('emby_accessToken%s' % username, clear=True)
        self.currToken = None
        self.logMsg("User token has been removed.", 1)

        self.auth = True
        self.currUser = None

    def run(self):

        self.logMsg("----===## Starting UserClient ##===----", 0)

        while not self.threadStopped():
            while self.threadSuspended():
                if self.threadStopped():
                    break
                xbmc.sleep(3000)

            status = utils.window('emby_serverStatus')
            if status:
                # Verify the connection status to server
                if status == "restricted":
                    # Parental control is restricting access
                    self.HasAccess = False

                elif status == "401":
                    # Unauthorized access, revoke token
                    utils.window('emby_serverStatus', value="Auth")
                    self.resetClient()

            if self.auth and (self.currUser is None):
                # Try to authenticate user
                status = utils.window('emby_serverStatus')
                if not status or status == "Auth":
                    # Set auth flag because we no longer need
                    # to authenticate the user
                    self.auth = False
                    self.authenticate()
                

            if not self.auth and (self.currUser is None):
                # If authenticate failed.
                server = self.getServer()
                username = self.getUsername()
                status = utils.window('emby_serverStatus')
                
                # The status Stop is for when user cancelled password dialog.
                if server and username and status != "Stop":
                    # Only if there's information found to login
                    self.logMsg("Server found: %s" % server, 2)
                    self.logMsg("Username found: %s" % username, 2)
                    self.auth = True

        self.doUtils.stopSession()
        self.logMsg("##===---- UserClient Stopped ----===##", 0)

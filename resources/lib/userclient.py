# -*- coding: utf-8 -*-

###############################################################################

import threading

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import utils
import downloadutils

import PlexAPI

###############################################################################


@utils.logging
@utils.ThreadMethodsAdditionalSuspend('suspend_Userclient')
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
            self.logMsg("No username saved, trying to get Plex username", 0)
            username = utils.settings('plexLogin')
            if not username:
                self.logMsg("Also no Plex username found", 0)
                return ""

        return username

    def getLogLevel(self):

        try:
            logLevel = int(utils.settings('logLevel'))
        except ValueError:
            logLevel = 0

        return logLevel

    def getUserId(self, username=None):

        log = self.logMsg
        window = utils.window
        settings = utils.settings

        if username is None:
            username = self.getUsername()
        w_userId = window('emby_currUser')
        s_userId = settings('userId%s' % username)

        # Verify the window property
        if w_userId:
            if not s_userId:
                # Save access token if it's missing from settings
                settings('userId%s' % username, value=w_userId)
            log("Returning userId from WINDOW for username: %s UserId: %s"
                % (username, w_userId), 1)
            return w_userId
        # Verify the settings
        elif s_userId:
            log("Returning userId from SETTINGS for username: %s userId: %s"
                % (username, s_userId), 1)
            return s_userId
        # No userId found
        else:
            log("No userId saved for username: %s. Trying to get Plex ID"
                % username, 0)
            plexId = settings('plexid')
            if not plexId:
                log('Also no Plex ID found in settings', 0)
                return ''
            log('Using Plex ID %s as userid for username: %s'
                % (plexId, username))
            settings('userId%s' % username, value=plexId)
            return plexId

    def getServer(self, prefix=True):

        settings = utils.settings

        # Original host
        HTTPS = settings('https') == "true"
        host = settings('ipaddress')
        port = settings('port')

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

    def getToken(self, username=None, userId=None):

        log = self.logMsg
        window = utils.window
        settings = utils.settings

        if username is None:
            username = self.getUsername()
        if userId is None:
            userId = self.getUserId()
        w_token = window('emby_accessToken%s' % userId)
        s_token = settings('accessToken')

        # Verify the window property
        if w_token:
            if not s_token:
                # Save access token if it's missing from settings
                settings('accessToken', value=w_token)
            log("Returning accessToken from WINDOW for username: %s accessToken: %s"
                % (username, w_token), 2)
            return w_token
        # Verify the settings
        elif s_token:
            log("Returning accessToken from SETTINGS for username: %s accessToken: %s"
                % (username, s_token), 2)
            window('emby_accessToken%s' % username, value=s_token)
            return s_token
        else:
            log("No token found.", 1)
            return ""

    def getSSLverify(self):
        # Verify host certificate
        settings = utils.settings

        s_sslverify = settings('sslverify')
        if settings('altip') == "true":
            s_sslverify = settings('secondsslverify')

        if s_sslverify == "true":
            return True
        else:
            return False

    def getSSL(self):
        # Client side certificate
        settings = utils.settings

        s_cert = settings('sslcert')
        if settings('altip') == "true":
            s_cert = settings('secondsslcert')

        if s_cert == "None":
            return None
        else:
            return s_cert

    def setUserPref(self):
        self.logMsg('Setting user preferences', 0)
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
        # Plex: always return True for now
        return True
        # hasAccess is verified in service.py
        log = self.logMsg
        window = utils.window

        url = "{server}/emby/Users?format=json"
        result = self.doUtils.downloadUrl(url)

        if result == False:
            # Access is restricted, set in downloadutils.py via exception
            log("Access is restricted.", 1)
            self.HasAccess = False

        elif window('emby_online') != "true":
            # Server connection failed
            pass

        elif window('emby_serverStatus') == "restricted":
            log("Access is granted.", 1)
            self.HasAccess = True
            window('emby_serverStatus', clear=True)
            xbmcgui.Dialog().notification(self.addonName, utils.language(33007))

    def loadCurrUser(self, authenticated=False):
        self.logMsg('Loading current user', 0)
        window = utils.window

        doUtils = self.doUtils
        username = self.getUsername()
        userId = self.getUserId()

        self.currUserId = userId
        self.currServer = self.getServer()
        self.currToken = self.getToken()
        self.machineIdentifier = utils.settings('plex_machineIdentifier')
        self.ssl = self.getSSLverify()
        self.sslcert = self.getSSL()

        if authenticated is False:
            self.logMsg('Testing validity of current token', 0)
            window('emby_currUser', value=userId)
            window('plex_username', value=username)
            window('emby_accessToken%s' % userId, value=self.currToken)
            res = PlexAPI.PlexAPI().CheckConnection(
                self.currServer, self.currToken)
            if res is False:
                self.logMsg('Answer from PMS is not as expected. Retrying', -1)
                return False
            elif res == 401:
                self.logMsg('Token is no longer valid', -1)
                self.resetClient()
                return False
            elif res >= 400:
                self.logMsg('Answer from PMS is not as expected. Retrying', -1)
                return False

        # Set to windows property
        window('emby_currUser', value=userId)
        window('plex_username', value=username)
        window('emby_accessToken%s' % userId, value=self.currToken)
        window('emby_server%s' % userId, value=self.currServer)
        window('emby_server_%s' % userId, value=self.getServer(prefix=False))
        window('plex_machineIdentifier', value=self.machineIdentifier)

        window('emby_serverStatus', clear=True)
        window('suspend_LibraryThread', clear=True)

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
        # self.getAdditionalUsers()
        # Set user preferences in settings
        self.currUser = username
        self.setUserPref()
        return True

    def authenticate(self):
        log = self.logMsg
        log('Authenticating user', 1)
        lang = utils.language
        window = utils.window
        settings = utils.settings
        dialog = xbmcgui.Dialog()

        # Get /profile/addon_data
        addondir = xbmc.translatePath(self.addon.getAddonInfo('profile')).decode('utf-8')
        hasSettings = xbmcvfs.exists("%ssettings.xml" % addondir)

        # If there's no settings.xml
        if not hasSettings:
            log("Error, no settings.xml found.", -1)
            self.auth = False
            return
        server = self.getServer()
        # If no user information
        if not server:
            log("Missing server information.", 0)
            self.auth = False
            return

        username = self.getUsername()
        userId = self.getUserId(username)
        # If there's a token, load the user
        if self.getToken(username=username, userId=userId):
            if self.loadCurrUser() is False:
                pass
            else:
                # We successfully loaded a user
                log("Current user: %s" % self.currUser, 1)
                log("Current userId: %s" % self.currUserId, 1)
                log("Current accessToken: xxxx", 1)
                return

        # AUTHENTICATE USER #####
        plx = PlexAPI.PlexAPI()
        # Choose Plex user login
        plexdict = plx.GetPlexLoginFromSettings()
        myplexlogin = plexdict['myplexlogin']
        plexhome = plexdict['plexhome']

        if myplexlogin == "true" and plexhome == 'true':
            username, userId, accessToken = plx.ChoosePlexHomeUser()
        else:
            log("Trying to connect to PMS without a token", 0)
            accessToken = ''
        # Check connection
        if plx.CheckConnection(server, accessToken) == 200:
            self.currUser = username
            dialog = xbmcgui.Dialog()
            settings('accessToken', value=accessToken)
            settings('userId%s' % username, value=userId)
            log("User authenticated with an access token", 1)
            if self.loadCurrUser(authenticated=True) is False:
                # Something went really wrong, return and try again
                self.auth = True
                self.currUser = None
                return
            # Success!
            if username:
                dialog.notification(
                    heading=self.addonName,
                    message="Welcome %s" % username.decode('utf-8'),
                    icon="special://home/addons/plugin.video.plexkodiconnect/icon.png")
            else:
                dialog.notification(
                    heading=self.addonName,
                    message="Welcome",
                    icon="special://home/addons/plugin.video.plexkodiconnect/icon.png")
            self.retry = 0
            # Make sure that lib sync thread is not paused
        else:
            self.logMsg("Error: user authentication failed.", -1)
            settings('accessToken', value="")
            settings('userId%s' % username, value="")

            # Give attempts at entering password / selecting user
            if self.retry >= 5:
                log("Too many retries.", 1)
                window('emby_serverStatus', value="Stop")
                dialog.ok(lang(33001), lang(39023))
                xbmc.executebuiltin(
                    'Addon.OpenSettings(plugin.video.plexkodiconnect)')

            self.retry += 1
            self.auth = False

    def resetClient(self):
        self.logMsg("Reset UserClient authentication.", 1)

        utils.settings('accessToken', value="")
        utils.window('emby_accessToken%s' % self.currUserId, clear=True)
        self.currToken = None
        self.logMsg("User token has been removed. Pausing Lib sync thread", 1)
        utils.window('suspend_LibraryThread', value="true")

        self.auth = True
        self.currUser = None
        self.currUserId = None

    def run(self):
        log = self.logMsg
        window = utils.window
        # Start library sync thread in a suspended mode, until signed in
        utils.window('suspend_LibraryThread', value="true")

        log("----===## Starting UserClient ##===----", 0)
        while not self.threadStopped():
            while self.threadSuspended():
                if self.threadStopped():
                    break
                xbmc.sleep(3000)

            status = window('emby_serverStatus')
            if status:
                # Verify the connection status to server
                if status == "restricted":
                    # Parental control is restricting access
                    self.HasAccess = False

                elif status == "401":
                    # Unauthorized access, revoke token
                    window('emby_serverStatus', value="Auth")
                    self.resetClient()

            if self.auth and (self.currUser is None):
                # Try to authenticate user
                if not status or status == "Auth":
                    # Set auth flag because we no longer need
                    # to authenticate the user
                    self.auth = False
                    self.authenticate()

            if not self.auth and (self.currUser is None):
                # Loop if no server found
                server = self.getServer()

                # The status Stop is for when user cancelled password dialog.
                if server and status != "Stop":
                    # Only if there's information found to login
                    log("Server found: %s" % server, 2)
                    self.auth = True

        self.doUtils.stopSession()
        log("##===---- UserClient Stopped ----===##", 0)

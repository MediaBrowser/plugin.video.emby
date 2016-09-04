# -*- coding: utf-8 -*-

##################################################################################################

import logging
import threading

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import artwork
import clientinfo
import connectmanager
import downloadutils
import read_embyserver as embyserver
from utils import window, settings, language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################

class UserClient(threading.Thread):

    _shared_state = {} # Borg

    _stop_thread = False
    _user = None
    _server = None

    _auth = True
    _has_access = True


    def __init__(self):

        self.__dict__ = self._shared_state

        self.connectmanager = connectmanager.ConnectManager()
        self.doutils = downloadutils.DownloadUtils()
        self.download = self.doutils.downloadUrl
        self.emby = embyserver.Read_EmbyServer()

        threading.Thread.__init__(self)

    def get_username(self):
        return settings('username') or settings('connectUsername') or None

    def get_user(self, data=None):
        return self._user

    def get_server_details(self):
        return self._server

    def get_server(self):

        ###$ Begin transition phase $###
        if settings('server') == "":
            HTTP = "https" if settings('https') == "true" else "http"
            host = settings('ipaddress')
            port = settings('port')

            if host and port:
                settings('server', value="%s://%s:%s" % (HTTP, host, port))
        ###$ End transition phase $###

        return settings('server') or None

    def verify_server(self):

        url = "%s/emby/Users/Public?format=json" % self.get_server()
        result = self.download(url, authenticate=False)
        if result != "":
            return True
        else:
            # Server connection failed
            return False

    def get_ssl(self):
        """
            Returns boolean value or path to certificate
            True: Verify ssl
            False: Don't verify connection
        """
        certificate = settings('sslcert')
        if certificate != "None":
            return certificate

        return True if settings('sslverify') == "true" else False

    def get_access(self):

        if not self._has_access:
            self._set_access()

        return self._has_access

    def _set_access(self):

        try:
            self.download("{server}/emby/Users?format=json")
        except Warning as e:
            if self._has_access and e == "restricted":
                self._has_access = False
                log.info("Access is restricted")
        else:
            if not self._has_access:
                self._has_access = True
                window('emby_serverStatus', clear=True)
                log.info("Access is granted")
                xbmcgui.Dialog().notification(lang(29999), lang(33007))

    def get_userid(self):

        ###$ Begin transition phase $###
        if settings('userId') == "":
            settings('userId', value=settings('userId%s' % settings('username')))
        ###$ End transition phase $###

        return settings('userId') or None

    def get_token(self):

        ###$ Begin transition phase $###
        if settings('token') == "":
            settings('token', value=settings('accessToken'))
        ###$ End transition phase $###

        return settings('token') or None

    def _set_user_server(self):

        self._server = self.download("{server}/emby/System/Configuration?format=json")
        settings('markPlayed', value=str(self._server['MaxResumePct']))

        self._user = self.download("{server}/emby/Users/{UserId}?format=json")
        if "PrimaryImageTag" in self._user:
            window('EmbyUserImage',
                   value=artwork.Artwork().getUserArtwork(self._user['Id'], 'Primary'))

    def _authenticate(self):
        
        if not self.get_server() or not self.get_username():
            log.info('missing server or user information')
            self._auth = False

        elif self.get_token():
            try:
                self._load_user()
            except Warning:
                log.info("token is invalid")
            else:
                log.info("current user: %s", self.get_username())
                log.info("current userid: %s", self.get_userid())
                log.debug("current token: %s", self.get_token())
                return

        ##### AUTHENTICATE USER #####
        server = self.get_server()
        username = self.get_username().decode('utf-8')
        users = self.emby.getUsers(server)
        user_found = None

        for user in users:
            if username == user['Name']:
                user_found = user
                break
        try:
            user = self.connectmanager.login_manual(server, user_found)
        except RuntimeError:
            window('emby_serverStatus', value="Stop")
            self._auth = False
            return
        else:
            log.info("user: %s", user)
            settings('username', value=user['User']['Name'])
            settings('token', value=user['AccessToken'])
            settings('userId', value=user['User']['Id'])
            xbmcgui.Dialog().notification(lang(29999),
                                          "%s %s!" % (lang(33000), username))
            self._load_user(authenticated=True)
            window('emby_serverStatus', clear=True)

    def _load_user(self, authenticated=False):

        doutils = self.doutils

        userid = self.get_userid()
        server = self.get_server()
        token = self.get_token()

        # Set properties
        window('emby_currUser', value=userid)
        window('emby_server%s' % userid, value=server)
        window('emby_accessToken%s' % userid, value=token)

        # Test the validity of the current token
        if not authenticated:
            try:
                self.download("{server}/emby/Users/{UserId}?format=json")
            except Warning as e:
                if "401" in e:
                    # Token is not longer valid
                    raise

        # Set downloadutils.py values
        doutils.setUserId(userid)
        doutils.setServer(server)
        doutils.setToken(token)
        doutils.setSSL(self.get_ssl())

        # verify user access
        self._set_access()

        # Start downloadutils.py session
        doutils.startSession()

        # Set _user and _server
        self._set_user_server()

    def _reset_client(self):

        log.info("reset UserClient authentication")

        settings('accessToken', value="")
        window('emby_accessToken', clear=True)

        log.info("user token revoked.")

        self._user = None
        self.auth = None

    def run(self):

        monitor = xbmc.Monitor()
        log.warn("----===## Starting UserClient ##===----")

        while not self._stop_thread:

            status = window('emby_serverStatus')
            if status:
                # Verify the connection status to server
                if status == "restricted":
                    # Parental control is restricting access
                    self._has_access = False

                elif status == "401":
                    # Unauthorized access, revoke token
                    window('emby_serverStatus', value="auth")
                    self._reset_client()

            if self._auth and self._user is None:
                # Try to authenticate user
                status = window('emby_serverStatus')
                if not status or status == "auth":
                    # Set auth flag because we no longer need
                    # to authenticate the user
                    self._auth = False
                    self._authenticate()

            if not self._auth and self._user is None:
                # If authenticate failed.
                server = self.get_server()
                username = self.get_username()
                status = window('emby_serverStatus')

                # The status Stop is for when user cancelled password dialog.
                if server and username and status != "Stop":
                    # Only if there's information found to login
                    log.info("Server found: %s", server)
                    log.info("Username found: %s", username)
                    self._auth = True

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        log.warn("##===---- UserClient Stopped ----===##")

    def stop_client(self):
        self._stop_thread = True

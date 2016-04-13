# -*- coding: utf-8 -*-

###############################################################################

import requests
import xml.etree.ElementTree as etree

import xbmcgui

from utils import logging, settings, window
import clientinfo

###############################################################################

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

###############################################################################


@logging
class DownloadUtils():
    """
    Manages any up/downloads with PKC. Careful to initiate correctly
    Use startSession() to initiate.
    If not initiated, e.g. SSL check will fallback to False
    """

    # Borg - multiple instances, shared state
    _shared_state = {}

    # Requests session
    timeout = 30
    # How many failed attempts before declaring PMS dead?
    connectionAttempts = 2
    # How many 401 returns before declaring unauthorized?
    unauthorizedAttempts = 2

    def __init__(self):
        self.__dict__ = self._shared_state

    def setUsername(self, username):
        """
        Reserved for userclient only
        """
        self.username = username
        self.logMsg("Set username: %s" % username, 0)

    def setUserId(self, userId):
        """
        Reserved for userclient only
        """
        self.userId = userId
        self.logMsg("Set userId: %s" % userId, 0)

    def setServer(self, server):
        """
        Reserved for userclient only
        """
        self.server = server
        self.logMsg("Set server: %s" % server, 0)

    def setToken(self, token):
        """
        Reserved for userclient only
        """
        self.token = token
        if token == '':
            self.logMsg('Set token: empty token!', 0)
        else:
            self.logMsg("Set token: xxxxxxx", 0)

    def setSSL(self, verifySSL=None, certificate=None):
        """
        Reserved for userclient only

        verifySSL must be 'true' to enable certificate validation

        certificate must be path to certificate or 'None'
        """
        if verifySSL is None:
            verifySSL = settings('sslverify')
        if certificate is None:
            certificate = settings('sslcert')
        self.logMsg("Verify SSL certificates set to: %s" % verifySSL, 0)
        self.logMsg("SSL client side certificate set to: %s" % certificate, 0)
        if verifySSL != 'true':
            self.s.verify = False
        if certificate != 'None':
            self.s.cert = certificate

    def startSession(self):
        """
        User should be authenticated when this method is called (via
        userclient)
        """
        # Start session
        self.s = requests.Session()

        client = clientinfo.ClientInfo()
        self.deviceId = client.getDeviceId()
        # Attach authenticated header to the session
        self.s.headers = client.getXArgsDeviceInfo()
        self.s.encoding = 'utf-8'
        # Set SSL settings
        self.setSSL()

        # Set other stuff
        self.setServer(window('pms_server'))
        self.setToken(window('pms_token'))
        self.setUserId(window('currUserId'))
        self.setUsername(window('plex_username'))

        # Counters to declare PMS dead or unauthorized
        # Use window variables because start of movies will be called with a
        # new plugin instance - it's impossible to share data otherwise
        if window('countUnauthorized') == '':
            window('countUnauthorized', value='0')
            window('countError', value='0')

        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        self.logMsg("Requests session started on: %s" % self.server, 0)

    def stopSession(self):
        try:
            self.s.close()
        except:
            self.logMsg("Requests session already closed", 0)
        try:
            del self.s
        except:
            pass
        self.logMsg('Request session stopped', 0)

    def getHeader(self, options=None):
        header = clientinfo.ClientInfo().getXArgsDeviceInfo()
        if options is not None:
            header.update(options)
        return header

    def __doDownload(self, s, type, **kwargs):
        if type == "GET":
            r = s.get(**kwargs)
        elif type == "POST":
            r = s.post(**kwargs)
        elif type == "DELETE":
            r = s.delete(**kwargs)
        elif type == "OPTIONS":
            r = s.options(**kwargs)
        elif type == "PUT":
            r = s.put(**kwargs)
        return r

    def downloadUrl(self, url, type="GET", postBody=None, parameters=None,
                    authenticate=True, headerOptions=None, verifySSL=True):
        """
        Override SSL check with verifySSL=False

        If authenticate=True, existing request session will be used/started
        Otherwise, 'empty' request will be made

        Returns:
            False              If an error occured
            True               If connection worked but no body was received
            401, ...           integer if PMS answered with HTTP error 401
                               (unauthorized) or other http error codes
            xml                xml etree root object, if applicable
            JSON               json() object, if applicable
        """
        kwargs = {}
        if authenticate is True:
            # Get requests session
            try:
                s = self.s
            except AttributeError:
                self.logMsg("Request session does not exist: start one", 0)
                self.startSession()
                s = self.s
            # Replace for the real values
            url = url.replace("{server}", self.server)
        else:
            # User is not (yet) authenticated. Used to communicate with
            # plex.tv and to check for PMS servers
            s = requests
            headerOptions = self.getHeader(options=headerOptions)
            kwargs['timeout'] = self.timeout
            if settings('sslcert') != 'None':
                kwargs['cert'] = settings('sslcert')

        # Set the variables we were passed (fallback to request session
        # otherwise - faster)
        kwargs['url'] = url
        if verifySSL is False:
            kwargs['verify'] = False
        if headerOptions is not None:
            kwargs['headers'] = headerOptions
        if postBody is not None:
            kwargs['data'] = postBody
        if parameters is not None:
            kwargs['params'] = parameters

        # ACTUAL DOWNLOAD HAPPENING HERE
        try:
            r = self.__doDownload(s, type, **kwargs)

        # THE EXCEPTIONS
        except requests.exceptions.ConnectionError as e:
            # Connection error
            self.logMsg("Server unreachable at: %s" % url, -1)
            self.logMsg(e, 1)

        except requests.exceptions.ConnectTimeout as e:
            self.logMsg("Server timeout at: %s" % url, -1)
            self.logMsg(e, 1)

        except requests.exceptions.HTTPError as e:
            self.logMsg('HTTP Error at %s' % url, -1)
            self.logMsg(e, 1)

        except requests.exceptions.SSLError as e:
            self.logMsg("Invalid SSL certificate for: %s" % url, -1)
            self.logMsg(e, 1)

        except requests.exceptions.TooManyRedirects as e:
            self.logMsg("Too many redirects connecting to: %s" % url, -1)
            self.logMsg(e, 1)

        except requests.exceptions.RequestException as e:
            self.logMsg("Unknown error connecting to: %s" % url, -1)
            self.logMsg(e, 1)

        except SystemExit:
            self.logMsg('SystemExit detected, aborting download', 0)
            self.stopSession()

        except:
            self.logMsg('Unknown error while downloading. Traceback:', -1)
            import traceback
            self.logMsg(traceback.format_exc(), 0)

        # THE RESPONSE #####
        else:
            # We COULD contact the PMS, hence it ain't dead
            if authenticate is True:
                window('countError', value='0')
                if r.status_code != 401:
                    window('countUnauthorized', value='0')

            if r.status_code == 204:
                # No body in the response
                return True

            elif r.status_code == 401:
                if authenticate is False:
                    # Called when checking a connect - no need for rash action
                    return 401
                r.encoding = 'utf-8'
                self.logMsg('HTTP error 401 from PMS', -1)
                self.logMsg(r.text, 1)
                if '401 Unauthorized' in r.text:
                    # Truly unauthorized
                    window('countUnauthorized',
                           value=str(int(window('countUnauthorized')) + 1))
                    if (int(window('countUnauthorized')) >=
                            self.unauthorizedAttempts):
                        self.logMsg('We seem to be truly unauthorized for PMS'
                                    % url, -1)
                        if window('emby_serverStatus') not in ('401', 'Auth'):
                            # Tell userclient token has been revoked.
                            self.logMsg('Setting PMS server status to '
                                        'unauthorized', 0)
                            window('emby_serverStatus', value="401")
                            xbmcgui.Dialog().notification(
                                self.addonName,
                                "Unauthorized for PMS",
                                xbmcgui.NOTIFICATION_ERROR)
                else:
                    # there might be other 401 where e.g. PMS under strain
                    self.logMsg('PMS might only be under strain', 0)
                return 401

            elif r.status_code in (200, 201):
                # 200: OK
                # 201: Created
                try:
                    # xml response
                    r = etree.fromstring(r.content)
                    return r
                except:
                    r.encoding = 'utf-8'
                    if r.text == '':
                        # Answer does not contain a body
                        return True
                    try:
                        # UNICODE - JSON object
                        r = r.json()
                        return r
                    except:
                        if '200 OK' in r.text:
                            # Received fucked up OK from PMS on playstate
                            # update
                            pass
                        else:
                            self.logMsg("Unable to convert the response for: "
                                        "%s" % url, -1)
                            self.logMsg("Received headers were: %s"
                                        % r.headers, -1)
                            self.logMsg('Received text:', -1)
                            self.logMsg(r.text, -1)
                        return True
            else:
                self.logMsg('Unknown answer from PMS %s with status code %s. '
                            'Message:' % (url, r.status_code), -1)
                r.encoding = 'utf-8'
                self.logMsg(r.text, 1)
                return True

        # And now deal with the consequences of the exceptions
        if authenticate is True:
            # Make the addon aware of status
            window('countError',
                   value=str(int(window('countError')) + 1))
            if int(window('countError')) >= self.connectionAttempts:
                self.logMsg('Failed to connect to %s too many times. Declare '
                            'PMS dead' % url, -1)
                window('emby_online', value="false")
        return False

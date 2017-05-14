# -*- coding: utf-8 -*-

###############################################################################

import logging
import requests
import xml.etree.ElementTree as etree

from utils import settings, window, language as lang, dialog
import clientinfo as client

###############################################################################

# Disable annoying requests warnings
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class DownloadUtils():
    """
    Manages any up/downloads with PKC. Careful to initiate correctly
    Use startSession() to initiate.
    If not initiated, e.g. SSL check will fallback to False
    """

    # Borg - multiple instances, shared state
    _shared_state = {}

    # How many failed attempts before declaring PMS dead?
    connectionAttempts = 2
    # How many 401 returns before declaring unauthorized?
    unauthorizedAttempts = 2
    # How long should we wait for an answer from the
    timeout = 30.0

    def __init__(self):
        self.__dict__ = self._shared_state

    def setUsername(self, username):
        """
        Reserved for userclient only
        """
        self.username = username
        log.debug("Set username: %s" % username)

    def setUserId(self, userId):
        """
        Reserved for userclient only
        """
        self.userId = userId
        log.debug("Set userId: %s" % userId)

    def setServer(self, server):
        """
        Reserved for userclient only
        """
        self.server = server
        log.debug("Set server: %s" % server)

    def setToken(self, token):
        """
        Reserved for userclient only
        """
        self.token = token
        if token == '':
            log.debug('Set token: empty token!')
        else:
            log.debug("Set token: xxxxxxx")

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
        log.debug("Verify SSL certificates set to: %s" % verifySSL)
        log.debug("SSL client side certificate set to: %s" % certificate)
        if verifySSL != 'true':
            self.s.verify = False
        if certificate != 'None':
            self.s.cert = certificate

    def startSession(self, reset=False):
        """
        User should be authenticated when this method is called (via
        userclient)
        """
        # Start session
        self.s = requests.Session()

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
        if reset is True:
            window('countUnauthorized', value='0')
            window('countError', value='0')

        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        log.info("Requests session started on: %s" % self.server)

    def stopSession(self):
        try:
            self.s.close()
        except:
            log.info("Requests session already closed")
        try:
            del self.s
        except:
            pass
        log.info('Request session stopped')

    def getHeader(self, options=None):
        header = client.getXArgsDeviceInfo()
        if options is not None:
            header.update(options)
        return header

    def _doDownload(self, s, action_type, **kwargs):
        if action_type == "GET":
            r = s.get(**kwargs)
        elif action_type == "POST":
            r = s.post(**kwargs)
        elif action_type == "DELETE":
            r = s.delete(**kwargs)
        elif action_type == "OPTIONS":
            r = s.options(**kwargs)
        elif action_type == "PUT":
            r = s.put(**kwargs)
        return r

    def downloadUrl(self, url, action_type="GET", postBody=None,
                    parameters=None, authenticate=True, headerOptions=None,
                    verifySSL=True, timeout=None, return_response=False):
        """
        Override SSL check with verifySSL=False

        If authenticate=True, existing request session will be used/started
        Otherwise, 'empty' request will be made

        Returns:
            None              If an error occured
            True               If connection worked but no body was received
            401, ...           integer if PMS answered with HTTP error 401
                               (unauthorized) or other http error codes
            xml                xml etree root object, if applicable
            json               json() object, if applicable
            <response-object>  if return_response=True is set (200, 201 only)
        """
        kwargs = {'timeout': self.timeout}
        if authenticate is True:
            # Get requests session
            try:
                s = self.s
            except AttributeError:
                log.info("Request session does not exist: start one")
                self.startSession()
                s = self.s
            # Replace for the real values
            url = url.replace("{server}", self.server)
        else:
            # User is not (yet) authenticated. Used to communicate with
            # plex.tv and to check for PMS servers
            s = requests
            headerOptions = self.getHeader(options=headerOptions)
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
        if timeout is not None:
            kwargs['timeout'] = timeout

        # ACTUAL DOWNLOAD HAPPENING HERE
        try:
            r = self._doDownload(s, action_type, **kwargs)

        # THE EXCEPTIONS
        except requests.exceptions.ConnectionError as e:
            # Connection error
            log.debug("Server unreachable at: %s" % url)
            log.debug(e)

        except requests.exceptions.Timeout as e:
            log.debug("Server timeout at: %s" % url)
            log.debug(e)

        except requests.exceptions.HTTPError as e:
            log.warn('HTTP Error at %s' % url)
            log.warn(e)

        except requests.exceptions.SSLError as e:
            log.warn("Invalid SSL certificate for: %s" % url)
            log.warn(e)

        except requests.exceptions.TooManyRedirects as e:
            log.warn("Too many redirects connecting to: %s" % url)
            log.warn(e)

        except requests.exceptions.RequestException as e:
            log.warn("Unknown error connecting to: %s" % url)
            log.warn(e)

        except SystemExit:
            log.info('SystemExit detected, aborting download')
            self.stopSession()

        except:
            log.warn('Unknown error while downloading. Traceback:')
            import traceback
            log.warn(traceback.format_exc())

        # THE RESPONSE #####
        else:
            # We COULD contact the PMS, hence it ain't dead
            if authenticate is True:
                window('countError', value='0')
                if r.status_code != 401:
                    window('countUnauthorized', value='0')

            if r.status_code == 204:
                # No body in the response
                # But read (empty) content to release connection back to pool
                # (see requests: keep-alive documentation)
                r.content
                return True

            elif r.status_code == 401:
                if authenticate is False:
                    # Called when checking a connect - no need for rash action
                    return 401
                r.encoding = 'utf-8'
                log.warn('HTTP error 401 from PMS %s' % url)
                log.info(r.text)
                if '401 Unauthorized' in r.text:
                    # Truly unauthorized
                    window('countUnauthorized',
                           value=str(int(window('countUnauthorized')) + 1))
                    if (int(window('countUnauthorized')) >=
                            self.unauthorizedAttempts):
                        log.warn('We seem to be truly unauthorized for PMS'
                                 ' %s ' % url)
                        if window('plex_serverStatus') not in ('401', 'Auth'):
                            # Tell userclient token has been revoked.
                            log.debug('Setting PMS server status to '
                                      'unauthorized')
                            window('plex_serverStatus', value="401")
                            dialog('notification',
                                   lang(29999),
                                   lang(30017),
                                   icon='{error}')
                else:
                    # there might be other 401 where e.g. PMS under strain
                    log.info('PMS might only be under strain')
                return 401

            elif r.status_code in (200, 201):
                # 200: OK
                # 201: Created
                if return_response is True:
                    # return the entire response object
                    return r
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
                            log.error("Unable to convert the response for: "
                                      "%s" % url)
                            log.info("Received headers were: %s" % r.headers)
                            log.info('Received text:')
                            log.info(r.text)
                        return True
            elif r.status_code == 403:
                # E.g. deleting a PMS item
                log.error('PMS sent 403: Forbidden error for url %s' % url)
                return None
            else:
                log.error('Unknown answer from PMS %s with status code %s. '
                          'Message:' % (url, r.status_code))
                r.encoding = 'utf-8'
                log.info(r.text)
                return True

        # And now deal with the consequences of the exceptions
        if authenticate is True:
            # Make the addon aware of status
            try:
                window('countError',
                       value=str(int(window('countError')) + 1))
                if int(window('countError')) >= self.connectionAttempts:
                    log.warn('Failed to connect to %s too many times. '
                             'Declare PMS dead' % url)
                    window('plex_online', value="false")
            except:
                # 'countError' not yet set
                pass
        return None

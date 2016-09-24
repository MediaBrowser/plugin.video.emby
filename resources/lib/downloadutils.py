# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import xbmc
import xbmcgui

import clientinfo
import connect.connectionmanager as connectionmanager
from utils import window, settings, language as lang

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class DownloadUtils(object):

    # Borg - multiple instances, shared state
    _shared_state = {}

    # Requests session
    session = {

        'ServerId': None,
        'Session': None
    }
    other_servers = [] # Multi server setup
    default_timeout = 30


    def __init__(self):

        self.__dict__ = self._shared_state
        self.clientInfo = clientinfo.ClientInfo()


    def set_session(self, user_id, server, server_id, token, ssl):
        # Reserved for userclient only
        info = {
            'UserId': user_id,
            'Server': server,
            'ServerId': server_id,
            'Token': token,
            'SSL': ssl
        }
        self.session.update(info)
        log.info("Set info for server %s: %s", self.session['ServerId'], self.session)

    def add_server(self, server, ssl):

        server_id = server['Id']
        info = {
            'UserId': server['UserId'],
            'Server': connectionmanager.getServerAddress(server, server['LastConnectionMode']),
            'ServerId': server_id,
            'Token': server['AccessToken'],
            'SSL': ssl
        }
        for s in self.other_servers:
            if s['ServerId'] == server_id:
                s.update(info)
                log.info("updating %s to available servers: %s", server_id, s)
                break
        else:
            self.other_servers.append(info)
            log.info("adding %s to available servers: %s", server_id, self.other_servers)

    def remove_server(self, server_id):

        for s in self.other_servers:
            if s['ServerId'] == server_id:
                self.other_servers.remove(s)
                log.info("removing %s from available servers", server_id)

    def post_capabilities(self, device_id):

        # Post settings to session
        url = "{server}/emby/Sessions/Capabilities/Full?format=json"
        data = {

            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (

                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"

                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext"
            )
        }

        log.debug("capabilities URL: %s" % url)
        log.debug("Postdata: %s" % data)

        self.downloadUrl(url, postBody=data, action_type="POST")
        log.debug("Posted capabilities to %s" % self.session['Server'])

        # Attempt at getting sessionId
        url = "{server}/emby/Sessions?DeviceId=%s&format=json" % device_id
        result = self.downloadUrl(url)
        try:
            sessionId = result[0]['Id']

        except (KeyError, TypeError):
            log.info("Failed to retrieve sessionId.")

        else:
            log.debug("Session: %s" % result)
            log.info("SessionId: %s" % sessionId)
            window('emby_sessionId', value=sessionId)

            # Post any permanent additional users
            additionalUsers = settings('additionalUsers')
            if additionalUsers:

                additionalUsers = additionalUsers.split(',')
                log.info("List of permanent users added to the session: %s" % additionalUsers)

                # Get the user list from server to get the userId
                url = "{server}/emby/Users?format=json"
                result = self.downloadUrl(url)

                for additional in additionalUsers:
                    addUser = additional.decode('utf-8').lower()

                    # Compare to server users to list of permanent additional users
                    for user in result:
                        username = user['Name'].lower()

                        if username in addUser:
                            userId = user['Id']
                            url = (
                                    "{server}/emby/Sessions/%s/Users/%s?format=json"
                                    % (sessionId, userId)
                            )
                            self.downloadUrl(url, postBody={}, action_type="POST")


    def startSession(self):

        self.deviceId = self.clientInfo.get_device_id()

        # User is identified from this point
        # Attach authenticated header to the session
        header = self.getHeader()

        # Start session
        s = requests.Session()
        s.headers = header
        s.verify = self.session['SSL']
        # Retry connections to the server
        s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))
        self.session['Session'] = s

        log.info("Requests session started on: %s" % self.session['Server'])

    def stopSession(self):
        try:
            self.s.close()
        except Exception:
            log.warn("Requests session could not be terminated.")

    def getHeader(self, authenticate=True):

        deviceName = self.clientInfo.get_device_name()
        deviceName = deviceName.encode('utf-8')
        deviceId = self.clientInfo.get_device_id()
        version = self.clientInfo.get_version()

        if authenticate:
            auth = (
                'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (self.session['UserId'], deviceName, deviceId, version))

            header = {

                'Content-type': 'application/json',
                'Accept-encoding': 'gzip',
                'Accept-Charset': 'UTF-8,*',
                'Authorization': auth,
                'X-MediaBrowser-Token': self.session['Token']
            }
        else:
            # If user is not authenticated
            auth = (
                'MediaBrowser Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (deviceName, deviceId, version))

            header = {

                'Content-type': 'application/json',
                'Accept-encoding': 'gzip',
                'Accept-Charset': 'UTF-8,*',
                'Authorization': auth
            }

        return header

    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True):

        log.debug("===== ENTER downloadUrl =====")
        
        session = requests
        kwargs = {}
        default_link = ""

        try:
            if self.session['Session'] is not None:
                session = self.session['Session']
            else:
                # request session does not exists
                # Get user information
                user_id = window('emby_currUser')
                info = {
                    'UserId': user_id,
                    'Server': window('emby_server%s' % user_id),
                    'Token': window('emby_accessToken%s' % user_id)
                }

                verifyssl = False

                # IF user enables ssl verification
                if settings('sslverify') == "true":
                    verifyssl = True
                if settings('sslcert') != "None":
                    verifyssl = settings('sslcert')

                info['SSL'] = verifyssl
                self.session.update(info)

                kwargs.update({
                    'verify': self.session['SSL'],
                    'headers': self.getHeader(authenticate)
                })

            # Replace for the real values
            url = url.replace("{server}", self.session['Server'])
            url = url.replace("{UserId}", self.session['UserId'])

            ##### PREPARE REQUEST #####
            kwargs.update({
                'url': url,
                'timeout': self.default_timeout,
                'json': postBody,
                'params': parameters
            })

            ##### THE RESPONSE #####
            log.debug(kwargs)
            r = self._requests(action_type, session, **kwargs)

            if r.status_code == 204:
                # No body in the response
                log.debug("====== 204 Success ======")
                # Read response to release connection
                r.content

            elif r.status_code == requests.codes.ok:
                try:
                    # UNICODE - JSON object
                    r = r.json()
                    log.debug("====== 200 Success ======")
                    log.debug("Response: %s" % r)
                    return r

                except:
                    if r.headers.get('content-type') != "text/html":
                        log.info("Unable to convert the response for: %s" % url)

            else: # Bad status code
                log.error("=== Bad status response: %s ===" % r.status_code)
                r.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            if window('emby_online') != "false":
                log.error("Server unreachable at: %s" % url)
                window('emby_online', value="false")

        except requests.exceptions.ConnectTimeout as e:
            log.error("Server timeout at: %s" % url)

        except requests.exceptions.HTTPError as e:

            if r.status_code == 401:
                # Unauthorized
                status = window('emby_serverStatus')

                if 'X-Application-Error-Code' in r.headers:
                    # Emby server errors
                    if r.headers['X-Application-Error-Code'] == "ParentalControl":
                        # Parental control - access restricted
                        if status != "restricted":
                            xbmcgui.Dialog().notification(
                                                    heading=lang(29999),
                                                    message="Access restricted.",
                                                    icon=xbmcgui.NOTIFICATION_ERROR,
                                                    time=5000)
                        
                        window('emby_serverStatus', value="restricted")
                        raise Warning('restricted')

                    elif r.headers['X-Application-Error-Code'] == "UnauthorizedAccessException":
                        # User tried to do something his emby account doesn't allow
                        pass

                elif status not in ("401", "Auth"):
                    # Tell userclient token has been revoked.
                    window('emby_serverStatus', value="401")
                    log.error("HTTP Error: %s" % e)
                    xbmcgui.Dialog().notification(
                                            heading="Error connecting",
                                            message="Unauthorized.",
                                            icon=xbmcgui.NOTIFICATION_ERROR)
                    raise Warning('401')

            elif r.status_code in (301, 302):
                # Redirects
                pass
            elif r.status_code == 400:
                # Bad requests
                pass

        except requests.exceptions.SSLError as e:
            log.error("Invalid SSL certificate for: %s" % url)

        except requests.exceptions.RequestException as e:
            log.error("Unknown error connecting to: %s" % url)

        return default_link

    def _requests(self, action, session=requests, **kwargs):

        if action == "GET":
            r = session.get(**kwargs)
        elif action == "POST":
            r = session.post(**kwargs)
        elif action == "DELETE":
            r = session.delete(**kwargs)

        return r
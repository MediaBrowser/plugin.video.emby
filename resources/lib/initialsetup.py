# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcgui

import clientinfo
import connectmanager
import connect.connectionmanager as connectionmanager
import downloadutils
import userclient
from utils import settings, language as lang, passwordsXML

#################################################################################################

log = logging.getLogger("EMBY."+__name__)
STATE = connectionmanager.ConnectionState

#################################################################################################


class InitialSetup(object):


    def __init__(self):

        self.addonId = clientinfo.ClientInfo().getAddonId()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.userClient = userclient.UserClient()
        self.connectmanager = connectmanager.ConnectManager()


    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        addonId = self.addonId
        dialog = xbmcgui.Dialog()

        ##### SERVER INFO #####
        
        log.debug("Initial setup called.")

        current_state = self.connectmanager.get_state()
        if current_state['State'] == STATE['SignedIn']:
            server_id = settings('serverId')
            current_server = current_state['Servers'][0]['Id']
            if current_server == server_id:
                self._set_server(current_server)
            else:
                for server in current_state['Servers']:
                    if server['Id'] == server_id:
                        self._set_server(server)
                        return
        try:
            server = self.connectmanager.select_servers()
            log.info("Server: %s" % server)
        
        except RuntimeError as e:
            log.exception(e)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return

        else:
            self._set_server(server)

            user_id = None
            token = None
            if not server.get('AccessToken') and not server.get('UserId'):
                try:
                    user = self.connectmanager.login(server)
                    log.info("User authenticated: %s" % user)
                except RuntimeError:
                    return
                settings('accessToken', value=user['AccessToken'])
                settings('userId', value=user['User']['Id'])
            else:
                settings('accessToken', value=server['AccessToken'])
                settings('userId', value=server['UserId'])

        ##### ADDITIONAL PROMPTS #####

        directPaths = dialog.yesno(
                            heading=lang(30511),
                            line1=lang(33035),
                            nolabel=lang(33036),
                            yeslabel=lang(33037))
        if directPaths:
            log.info("User opted to use direct paths.")
            settings('useDirectPaths', value="1")

            # ask for credentials
            credentials = dialog.yesno(
                                heading=lang(30517),
                                line1= lang(33038))
            if credentials:
                log.info("Presenting network credentials dialog.")
                passwordsXML()
        
        musicDisabled = dialog.yesno(
                            heading=lang(29999),
                            line1=lang(33039))
        if musicDisabled:
            log.info("User opted to disable Emby music library.")
            settings('enableMusic', value="false")
        else:
            # Only prompt if the user didn't select direct paths for videos
            if not directPaths:
                musicAccess = dialog.yesno(
                                    heading=lang(29999),
                                    line1=lang(33040))
                if musicAccess:
                    log.info("User opted to direct stream music.")
                    settings('streamMusic', value="true")

    def _set_server(self, server):

        server_address = connectionmanager.getServerAddress(server, server['LastConnectionMode'])
        prefix, ip, port = server_address.replace("/", "").split(':')
        
        settings('serverId', value=server['Id'])
        settings('ipaddress', value=ip)
        settings('port', value=port)
        if prefix == "https":
            settings('https', value="true")

        log.info("Saved server information: %s", server_address)
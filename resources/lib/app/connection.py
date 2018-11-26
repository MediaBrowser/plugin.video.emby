#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .. import utils, json_rpc as js

LOG = getLogger('PLEX.connection')


class Connection(object):
    def __init__(self, entrypoint=False):
        if entrypoint:
            self.load_entrypoint()
        else:
            self.load_webserver()
            self.load()
            # TODO: Delete
            self.pms_server = None
            # Token passed along, e.g. if playback initiated by Plex Companion. Might be
            # another user playing something! Token identifies user
            self.plex_transient_token = None

    def load_webserver(self):
        """
        PKC needs Kodi webserver to work correctly
        """
        LOG.debug('Loading Kodi webserver details')
        # Kodi webserver details
        if js.get_setting('services.webserver') in (None, False):
            # Enable the webserver, it is disabled
            js.set_setting('services.webserver', True)
        self.webserver_host = 'localhost'
        self.webserver_port = js.get_setting('services.webserverport')
        self.webserver_username = js.get_setting('services.webserverusername')
        self.webserver_password = js.get_setting('services.webserverpassword')

    def load(self):
        LOG.debug('Loading connection settings')
        # Shall we verify SSL certificates? "None" will leave SSL enabled
        self.verify_ssl_cert = None if utils.settings('sslverify') == 'true' \
            else False
        # Do we have an ssl certificate for PKC we need to use?
        self.ssl_cert_path = utils.settings('sslcert') \
            if utils.settings('sslcert') != 'None' else None

        self.machine_identifier = utils.settings('plex_machineIdentifier') or None
        self.server_name = utils.settings('plex_servername') or None
        self.https = utils.settings('https') == 'true'
        self.host = utils.settings('ipaddress') or None
        self.port = int(utils.settings('port')) if utils.settings('port') else None
        if not self.host:
            self.server = None
        elif self.https:
            self.server = 'https://%s:%s' % (self.host, self.port)
        else:
            self.server = 'http://%s:%s' % (self.host, self.port)
        utils.window('pms_server', value=self.server)
        self.online = False
        LOG.debug('Set server %s (%s) to %s',
                  self.server_name, self.machine_identifier, self.server)

    def load_entrypoint(self):
        self.verify_ssl_cert = None if utils.settings('sslverify') == 'true' \
            else False
        self.ssl_cert_path = utils.settings('sslcert') \
            if utils.settings('sslcert') != 'None' else None
        self.https = utils.settings('https') == 'true'
        self.host = utils.settings('ipaddress') or None
        self.port = int(utils.settings('port')) if utils.settings('port') else None
        if not self.host:
            self.server = None
        elif self.https:
            self.server = 'https://%s:%s' % (self.host, self.port)
        else:
            self.server = 'http://%s:%s' % (self.host, self.port)

    def clear(self):
        LOG.debug('Clearing connection settings')
        self.machine_identifier = None
        self.server_name = None
        self.http = None
        self.host = None
        self.port = None
        self.server = None
        utils.window('pms_server', clear=True)

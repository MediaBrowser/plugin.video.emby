#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .. import utils

LOG = getLogger('PLEX.account')


class Account(object):
    def __init__(self):
        # Along with window('plex_authenticated')
        self.authenticated = False
        self._session = None
        utils.window('plex_authenticated', clear=True)
        self.load()

    def set_authenticated(self):
        self.authenticated = True
        utils.window('plex_authenticated', value='true')
        # Start download session
        from .. import downloadutils
        self._session = downloadutils.DownloadUtils()
        self._session.startSession(reset=True)

    def set_unauthenticated(self):
        self.authenticated = False
        utils.window('plex_authenticated', clear=True)

    def load(self):
        LOG.debug('Loading account settings')
        # plex.tv username
        self.plex_username = utils.settings('username') or None
        # Plex ID of that user (e.g. for plex.tv) as a STRING
        self.plex_user_id = utils.settings('userid') or None
        # Token for that user for plex.tv
        self.plex_token = utils.settings('plexToken') or None
        # Plex token for the active PMS for the active user
        # (might be diffent to plex_token)
        self.pms_token = utils.settings('accessToken') or None
        self.avatar = utils.settings('plexAvatar') or None
        self.myplexlogin = utils.settings('myplexlogin') == 'true'

        # Plex home user? Then "False"
        self.restricted_user = True \
            if utils.settings('plex_restricteduser') == 'true' else False
        # Force user to enter Pin if set?
        self.force_login = utils.settings('enforceUserLogin') == 'true'

        # Also load these settings to Kodi window variables - they'll be
        # available for other PKC Python instances
        utils.window('plex_restricteduser',
                     value='true' if self.restricted_user else 'false')
        utils.window('plex_token', value=self.plex_token or '')
        utils.window('pms_token', value=self.pms_token or '')
        utils.window('plexAvatar', value=self.avatar or '')
        LOG.debug('Loaded user %s, %s with plex token %s... and pms token %s...',
                  self.plex_username, self.plex_user_id,
                  self.plex_token[:5] if self.plex_token else None,
                  self.pms_token[:5] if self.pms_token else None)
        LOG.debug('User is restricted Home user: %s', self.restricted_user)

    def clear(self):
        LOG.debug('Clearing account settings')
        self.plex_username = None
        self.plex_user_id = None
        self.plex_token = None
        self.pms_token = None
        self.avatar = None
        self.restricted_user = None
        self.authenticated = False
        self._session = None

        utils.settings('username', value='')
        utils.settings('userid', value='')
        utils.settings('plex_restricteduser', value='')
        utils.settings('plexToken', value='')
        utils.settings('accessToken', value='')
        utils.settings('plexAvatar', value='')

        utils.window('plex_restricteduser', clear=True)
        utils.window('plex_token', clear=True)
        utils.window('pms_token', clear=True)
        utils.window('plexAvatar', clear=True)
        utils.window('plex_authenticated', clear=True)

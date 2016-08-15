# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcgui
import xbmcaddon

import artwork
import connect.connectionmanager as connectionmanager
from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
MANUAL = 200
CANCEL = 201

##################################################################################################


class UsersConnect(xbmcgui.WindowXMLDialog):

    _user = None
    _isManualLogin = False


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def isUserSelected(self):
        return True if self._user else False

    def isManualConnectLogin(self):
        return self._isManualLogin

    def setUsers(self, users):
        self.users = users

    def getUser(self):
        return self._user

    def onInit(self):

        list_ = self.getControl(LIST)
        for user in self.users:
            user_image = "userflyoutdefault2.png" if not user.get('PrimaryImageTag') else artwork.Artwork().getUserArtwork(user['Id'], 'Primary')
            list_.addItem(self._add_listitem(user['Name'], user['Id'], user_image))

        self.setFocus(list_)

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            
            if self.getFocusId() == LIST:
                list_ = self.getControl(LIST)
                user = list_.getSelectedItem()
                selected_id = user.getProperty('id')
                log.info('User Id selected: %s' % selected_id)
                
                for user in self.users:
                    if user['Id'] == selected_id:
                        self._user = user
                        break

                self.close()

    def onClick(self, control):

        if control == MANUAL:
            self._isManualLogin = True
            self.close()

        elif control == CANCEL:
            self.close()

    def _add_listitem(self, label, user_id, user_image):

        item = xbmcgui.ListItem(label)
        item.setProperty('id', user_id)
        item.setArt({'Icon': user_image})

        return item
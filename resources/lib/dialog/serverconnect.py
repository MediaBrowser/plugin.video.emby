# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmcgui
import xbmcaddon

from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
USER_IMAGE = 150
USER_NAME = 151
LIST = 155
CANCEL = 201

##################################################################################################


class ServerConnect(xbmcgui.WindowXMLDialog):

    name = None
    user_image = None
    servers = []
    selected_id = None


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_servers(self, servers):
        self.servers = servers or []

    def set_name(self, name):
        self.name = name

    def set_image(self, image):
        self.user_image = image

    def onInit(self):

        if self.user_image is not None:
            self.getControl(USER_IMAGE).setImage(self.user_image)

        self.getControl(USER_NAME).setLabel("%s %s" % (lang(33000), self.name.decode('utf-8')))

        list_ = self.getControl(LIST)
        for server in self.servers:
            list_.addItem(self._add_listitem(server['Name'], server['Id']))
        #self.setFocus(list_)

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            if self.getFocusId() == LIST:
                list_ = self.getControl(LIST)
                server = list_.getSelectedItem()
                self.selected_id = server.getProperty('id')
                log.info('Server Id selected: %s' % self.selected_id)
                self.close()

    def onClick(self, control):

        if control == CANCEL:
            self.close()

    def _add_listitem(self, label, server_id):
        
        item = xbmcgui.ListItem(label)
        item.setProperty('id', server_id)

        return item
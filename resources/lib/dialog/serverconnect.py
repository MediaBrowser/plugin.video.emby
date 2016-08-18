# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcgui
import xbmcaddon

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
USER_IMAGE = 150
USER_NAME = 151
LIST = 155
CANCEL = 201
MESSAGE_BOX = 202
MESSAGE = 203
BUSY = 204
EMBY_CONNECT = 205
MANUAL_SERVER = 206
ConnectionState = connectionmanager.ConnectionState

##################################################################################################


class ServerConnect(xbmcgui.WindowXMLDialog):

    name = ""
    user_image = None
    servers = []
    selected_server = None
    isEmbyLogin = False
    isManualServer = False


    def __init__(self, *args, **kwargs):

        self._connect_manager = kwargs.pop('connect_manager')
        self.user_image = kwargs.pop('user_image')
        self.servers = kwargs.pop('servers', [])
        self.name = kwargs.pop('user_name', [])
        self.emby_connect = kwargs.pop('emby_connect')

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def isServerSelected(self):
        return True if self.selected_server else False

    def isEmbyConnectLogin(self):
        return self.isEmbyLogin

    def isManualServerLogin(self):
        return self.isManualServer

    def getServer(self):
        return self.selected_server

    def onInit(self):

        if self.user_image is not None:
            self.getControl(USER_IMAGE).setImage(self.user_image)

        # Display emby connect login option
        if not self.emby_connect: # Change
            self.getControl(EMBY_CONNECT).setLabel("[UPPERCASE][B]"+lang(30618)+"[/B][/UPPERCASE]")

        self.getControl(USER_NAME).setLabel("%s %s" % (lang(33000), self.name.decode('utf-8')))
        self.message = self.getControl(MESSAGE)
        self.message_box = self.getControl(MESSAGE_BOX)
        self.busy = self.getControl(BUSY)

        list_ = self.getControl(LIST)
        for server in self.servers:
            server_type = "wifi" if server.get('ExchangeToken') else "network"
            list_.addItem(self._add_listitem(server['Name'], server['Id'], server_type))

        self.setFocus(list_)

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            
            if self.getFocusId() == LIST:
                list_ = self.getControl(LIST)
                server = list_.getSelectedItem()
                selected_id = server.getProperty('id')
                log.info('Server Id selected: %s' % selected_id)
                
                if self._connect_server(selected_id):
                    self.message_box.setVisibleCondition("False")
                    self.close()

    def onClick(self, control):

        if control == EMBY_CONNECT:
            self._connect_manager.clearData()
            self.isEmbyLogin = True
            self.close()

        elif control == MANUAL_SERVER:
            self.isManualServer = True
            self.close()

        elif control == CANCEL:
            self.close()

    def _add_listitem(self, label, server_id, server_type):

        item = xbmcgui.ListItem(label)
        item.setProperty('id', server_id)
        item.setProperty('server_type', server_type)

        return item

    def _connect_server(self, server_id):

        server = self._connect_manager.getServerInfo(server_id)
        self.message.setLabel("%s %s..." % (lang(30610), server['Name']))
        self.message_box.setVisibleCondition("True")
        self.busy.setVisibleCondition("True")
        result = self._connect_manager.connectToServer(server)

        if result.get('State') == ConnectionState['Unavailable']:
            self.busy.setVisibleCondition("False")
            self.message.setLabel(lang(30609))
            return False
        else:
            xbmc.sleep(1000)
            self.selected_server = result['Servers'][0]
            return True
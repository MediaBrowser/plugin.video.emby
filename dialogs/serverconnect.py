# -*- coding: utf-8 -*-
import xbmcgui
import helper.loghandler
import helper.utils as Utils

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
USER_IMAGE = 150
LIST = 155
CANCEL = 201
MESSAGE_BOX = 202
MESSAGE = 203
BUSY = 204
EMBY_CONNECT = 205
MANUAL_SERVER = 206
LOG = helper.loghandler.LOG('EMBY.dialogs.serverconnect')


class ServerConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.user_image = None
        self._selected_server = None
        self._connect_login = False
        self._manual_server = False
        self.message = None
        self.message_box = None
        self.busy = None
        self.list_ = None
        self.connect_manager = None
        self.emby_connect = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def PassVar(self, connect_manager, user_image, emby_connect):
        self.connect_manager = connect_manager
        self.user_image = user_image
        self.emby_connect = emby_connect

    def is_server_selected(self):
        return bool(self._selected_server)

    def is_connect_login(self):
        return self._connect_login

    def is_manual_server(self):
        return self._manual_server

    def onInit(self):
        self.message = self.getControl(MESSAGE)
        self.message_box = self.getControl(MESSAGE_BOX)
        self.busy = self.getControl(BUSY)
        self.list_ = self.getControl(LIST)

        for server in self.connect_manager.Found_Servers:
            if 'Name' not in server:
                continue

            server_type = "wifi" if server.get('ExchangeToken') else "network"
            self.list_.addItem(add_listitem(server['Name'], server['Id'], server_type))

        if self.user_image is not None:
            self.getControl(USER_IMAGE).setImage(self.user_image)

        if not self.emby_connect:  # Change connect user
            self.getControl(EMBY_CONNECT).setLabel("[B]%s[/B]" % Utils.Translate(30618))

        if self.connect_manager.Found_Servers:
            self.setFocus(self.list_)

    def onAction(self, action):
        if action in (ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            if self.getFocusId() == LIST:
                server = self.list_.getSelectedItem()
                LOG.info('Server Id selected: %s' % server.getProperty('id'))
                Server_Selected_Id = server.getProperty('id')

                if self._connect_server(Server_Selected_Id):
                    self.message_box.setVisibleCondition('false')
                    self.close()

    def onClick(self, control):
        if control == EMBY_CONNECT:
            self.connect_manager.clear_data()
            self._connect_login = True
            self.close()
        elif control == MANUAL_SERVER:
            self._manual_server = True
            self.close()
        elif control == CANCEL:
            self.close()

    def _connect_server(self, Server_Selected_Id):
        for server in self.connect_manager.Found_Servers:
            if server['Id'] == Server_Selected_Id:
                if self.connect_manager.EmbyServer.ServerData:
                    server['ConnectAccessToken'] = self.connect_manager.EmbyServer.ServerData['ConnectAccessToken']
                    server['ConnectUserId'] = self.connect_manager.EmbyServer.ServerData['ConnectUserId']
                    server['ConnectUser'] = self.connect_manager.EmbyServer.ServerData['ConnectUser']

                self.connect_manager.EmbyServer.ServerData = server
                self.message.setLabel("%s %s..." % (Utils.Translate(30610), server['Name']))
                self.message_box.setVisibleCondition('true')
                self.busy.setVisibleCondition('true')
                result = self.connect_manager.connect_to_server()

                if not result:  # Unavailable
                    self.busy.setVisibleCondition('false')
                    self.message.setLabel(Utils.Translate(30609))
                    return False

                if result['State'] == 0:  # Unavailable
                    self.busy.setVisibleCondition('false')
                    self.message.setLabel(Utils.Translate(30609))
                    return False

                self._selected_server = result['Servers'][0]
                return True

        return False

def add_listitem(label, server_id, server_type):
    item = xbmcgui.ListItem(label)
    item.setProperty('id', server_id)
    item.setProperty('server_type', server_type)
    return item

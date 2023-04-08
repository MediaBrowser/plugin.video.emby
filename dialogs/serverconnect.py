import xbmc
import xbmcgui
from helper import utils

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


class ServerConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.user_image = ""
        self._connect_login = False
        self._manual_server = False
        self.message = None
        self.message_box = None
        self.busy = None
        self.list_ = None
        self.EmbyServer = None
        self.emby_connect = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.message = self.getControl(MESSAGE)
        self.message_box = self.getControl(MESSAGE_BOX)
        self.busy = self.getControl(BUSY)
        self.list_ = self.getControl(LIST)

        for server in self.EmbyServer.Found_Servers:
            if 'Name' not in server:
                continue

            server_type = "wifi" if server.get('ExchangeToken') else "network"
            listitem = xbmcgui.ListItem(server['Name'])
            listitem.setProperty('id', server['Id'])
            listitem.setProperty('Name', server['Name'])
            listitem.setProperty('server_type', server_type)
            self.list_.addItem(listitem)

        if self.user_image:
            self.getControl(USER_IMAGE).setImage(self.user_image)

        if not self.emby_connect:  # Change connect user
            self.getControl(EMBY_CONNECT).setLabel(f"[B]{utils.Translate(30618)}[/B]")

        if self.EmbyServer.Found_Servers:
            self.setFocus(self.list_)

    def onAction(self, action):
        if action in (ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            if self.getFocusId() == LIST:
                server = self.list_.getSelectedItem()
                xbmc.log(f"EMBY.dialogs.serverconnect: Server Id selected: {server.getProperty('id')}", 1) # LOGINFO
                Server_Selected_Id = server.getProperty('id')
                Server_Selected_Name = server.getProperty('Name')

                for server in self.EmbyServer.Found_Servers:
                    if server['Id'] == Server_Selected_Id and server['Name'] == Server_Selected_Name:
                        self.EmbyServer.ServerData.update({'ServerId': server['Id'], 'ServerName': server['Name']})

                        # EmbyConnect
                        if server.get('ExchangeToken', ""):
                            self.EmbyServer.ServerData.update({'EmbyConnectLocalAddress': server.get('LocalAddress', ""), 'EmbyConnectRemoteAddress': server.get('RemoteAddress', ""), 'EmbyConnectExchangeToken': server.get('ExchangeToken', ""), 'LocalAddress': "", 'RemoteAddress': "", 'ManualAddress': ""})
                        else: #regular
                            self.EmbyServer.ServerData.update({'LocalAddress': server.get('LocalAddress', ""), 'RemoteAddress': server.get('RemoteAddress', ""), 'ManualAddress': server.get('ManualAddress', ""), 'EmbyConnectLocalAddress': "", 'EmbyConnectRemoteAddress': "", 'EmbyConnectExchangeToken': ""})

                        self.message.setLabel(f"{utils.Translate(30610)} {server['Name']}...")
                        self.message_box.setVisibleCondition('true')
                        self.busy.setVisibleCondition('true')
                        result = self.EmbyServer.connect_to_server()

                        if not result:  # Unavailable
                            self.busy.setVisibleCondition('false')
                            self.message.setLabel(utils.Translate(30609))
                            break

                        self.message_box.setVisibleCondition('false')
                        self.close()
                        break

    def onClick(self, controlId):
        if controlId == EMBY_CONNECT:
            self.EmbyServer.ServerData['LastConnectionMode'] = "EmbyConnect"
        elif controlId == MANUAL_SERVER:
            self.EmbyServer.ServerData['LastConnectionMode'] = "ManualAddress"
        elif controlId == CANCEL:
            self.EmbyServer.ServerData['LastConnectionMode'] = ""

        self.close()

import xbmc
import xbmcgui

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
MANUAL = 200
CANCEL = 201


class UsersConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.SelectedUser = {}
        self.list_ = None
        self.users = []
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.list_ = self.getControl(LIST)

        for user in self.users:
            item = xbmcgui.ListItem(user['Name'])
            item.setProperty('id', user['Id'])
            item.setArt({'Icon': user['UserImageUrl']})
            self.list_.addItem(item)

        self.setFocus(self.list_)

    def onAction(self, action):
        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()
            return

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            if self.getFocusId() == LIST:
                user = self.list_.getSelectedItem()
                selected_id = user.getProperty('id')
                xbmc.log(f"EMBY.dialogs.userconnect: User Id selected: {selected_id}", 1) # LOGINFO

                for user in self.users:
                    if user['Id'] == selected_id:
                        self.SelectedUser = user
                        break

                self.close()

    def onClick(self, controlId):
        if controlId == MANUAL:
            self.SelectedUser = "MANUAL"
            self.close()
        elif controlId == CANCEL:
            self.close()

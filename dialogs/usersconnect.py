import xbmcgui
from helper import loghandler, utils

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
MANUAL = 200
CANCEL = 201
LOG = loghandler.LOG('EMBY.dialogs.userconnect')


class UsersConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.SelectedUser = {}
        self.ManualLogin = False
        self.list_ = None
        self.ServerData = {}
        self.API = None
        self.users = []
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        self.list_ = self.getControl(LIST)

        for user in self.users:
            user['UserImageUrl'] = utils.icon

            # Download user picture
            BinaryData, _, FileExtension = self.API.get_Image_Binary(user['Id'], "Primary", 0, 0, True)

            if BinaryData:
                Filename = utils.PathToFilenameReplaceSpecialCharecters("%s_%s_%s.%s" % (self.ServerData['ServerName'], user['Name'], user['Id'], FileExtension))
                iconpath = "%s%s" % (utils.FolderEmbyTemp, Filename)
                utils.delFile(iconpath)
                utils.writeFileBinary(iconpath, BinaryData)
                user['UserImageUrl'] = iconpath

            item = xbmcgui.ListItem(user['Name'])
            item.setProperty('id', user['Id'])
            item.setArt({'Icon': user['UserImageUrl']})
            self.list_.addItem(item)

        self.setFocus(self.list_)

    def onAction(self, action):
        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):
            if self.getFocusId() == LIST:
                user = self.list_.getSelectedItem()
                selected_id = user.getProperty('id')
                LOG.info('User Id selected: %s' % selected_id)

                for user in self.users:
                    if user['Id'] == selected_id:
                        self.SelectedUser = user
                        self.ServerData['UserImageUrl'] = user['UserImageUrl']
                        self.ServerData['UserName'] = user['Name']
                        break

                self.close()

    def onClick(self, controlId):
        if controlId == MANUAL:
            self.ManualLogin = True
            self.close()
        elif controlId == CANCEL:
            self.close()

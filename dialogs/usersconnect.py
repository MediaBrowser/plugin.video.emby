# -*- coding: utf-8 -*-
import xbmcgui
import helper.loghandler

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
MANUAL = 200
CANCEL = 201
LOG = helper.loghandler.LOG('EMBY.dialogs.userconnect')


class UsersConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._user = None
        self._manual_login = False
        self.list_ = None
        self.server = None
        self.users = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def PassVar(self, server, users):
        self.server = server
        self.users = users

    def is_user_selected(self):
        return bool(self._user)

    def get_user(self):
        return self._user

    def is_manual_login(self):
        return self._manual_login

    def onInit(self):
        self.list_ = self.getControl(LIST)

        for user in self.users:
            user_image = ("items/logindefault.png" if 'PrimaryImageTag' not in user else self._get_user_artwork(user['Id'], 'Primary'))
            self.list_.addItem(add_listitem(user['Name'], user['Id'], user_image))

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
                        self._user = user
                        break

                self.close()

    def onClick(self, control):
        if control == MANUAL:
            self._manual_login = True
            self.close()
        elif control == CANCEL:
            self.close()

    # Load user information set by UserClient
    def _get_user_artwork(self, user_id, item_type):
        return "%s/emby/Users/%s/Images/%s?Format=original" % (self.server, user_id, item_type)

def add_listitem(label, user_id, user_image):
    item = xbmcgui.ListItem(label)
    item.setProperty('id', user_id)
    item.setArt({'Icon': user_image})
    return item

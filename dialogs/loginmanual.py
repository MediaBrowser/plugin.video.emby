# -*- coding: utf-8 -*-
import os

import xbmcgui
import xbmcaddon

import helper.utils
import helper.loghandler

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
SIGN_IN = 200
CANCEL = 201
ERROR_TOGGLE = 202
ERROR_MSG = 203
ERROR = {'Invalid': 1, 'Empty': 2}

class LoginManual(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._user = None
        self.error = None
        self.username = None
        self.LOG = helper.loghandler.LOG('EMBY.dialogs.loginmanual.LoginManual')
        self.Utils = helper.utils.Utils()
        self.user_field = None
        self.password_field = None
        self.signin_button = None
        self.error_toggle = None
        self.error_msg = None
        self.cancel_button = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_args(self, **kwargs):
        # connect_manager, user_image, servers, emby_connect
        for key, value in list(kwargs.items()):
            setattr(self, key, value)

    def is_logged_in(self):
        return bool(self._user)

    def get_user(self):
        return self._user

    def onInit(self):
        self.signin_button = self.getControl(SIGN_IN)
        self.cancel_button = self.getControl(CANCEL)
        self.error_toggle = self.getControl(ERROR_TOGGLE)
        self.error_msg = self.getControl(ERROR_MSG)
        self.user_field = self._add_editcontrol(755, 433, 40, 415)
        self.password_field = self._add_editcontrol(755, 543, 40, 415, password=1)

        if self.username:
            self.user_field.setText(self.username)
            self.setFocus(self.password_field)
        else:
            self.setFocus(self.user_field)

        self.user_field.controlUp(self.cancel_button)
        self.user_field.controlDown(self.password_field)
        self.password_field.controlUp(self.user_field)
        self.password_field.controlDown(self.signin_button)
        self.signin_button.controlUp(self.password_field)
        self.cancel_button.controlDown(self.user_field)

    def onClick(self, control):
        if control == SIGN_IN:
            # Sign in to emby connect
            self._disable_error()
            user = self.user_field.getText()
            password = self.password_field.getText()

            if not user:
                # Display error
                self._error(ERROR['Empty'], self.Utils.Translate('empty_user'))
                self.LOG.error("Username cannot be null")
            elif self._login(user, password):
                self.close()
        elif control == CANCEL:
            # Remind me later
            self.close()

    def onAction(self, action):
        if self.error == ERROR['Empty'] and self.user_field.getText():
            self._disable_error()

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def _add_editcontrol(self, x, y, height, width, password=0):
        os.path.join(xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
####        control = xbmcgui.ControlEdit(0, 0, 0, 0, label="User", font="font13", textColor="FF52b54b", disabledColor="FF888888", focusTexture="-", noFocusTexture="-", isPassword=password)
        control = xbmcgui.ControlEdit(0, 0, 0, 0, label="", font="font13", textColor="FF52b54b", disabledColor="FF888888", focusTexture="-", noFocusTexture="-")
#        control.setInputType(xbmcgui.INPUT_TYPE_PASSWORD)
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)
        self.addControl(control)
        return control

    def _login(self, username, password):
        server = self.connect_manager.get_serveraddress()
        result = self.connect_manager.login(server, username, password, True, {})

        if not result:
            self._error(ERROR['Invalid'], self.Utils.Translate('invalid_auth'))
            return False

        self._user = result
        return True

    def _error(self, state, message):
        self.error = state
        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('true')

    def _disable_error(self):
        self.error = None
        self.error_toggle.setVisibleCondition('false')

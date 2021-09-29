# -*- coding: utf-8 -*-
import os
import xbmcgui
import xbmcaddon
import helper.loghandler
import helper.utils as Utils

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
SIGN_IN = 200
CANCEL = 201
ERROR_TOGGLE = 202
ERROR_MSG = 203
ERROR = {'Invalid': 1, 'Empty': 2}
LOG = helper.loghandler.LOG('EMBY.dialogs.loginconnect.LoginConnect')


class LoginConnect(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._user = None
        self.error = None
        self.user_field = None
        self.password_field = None
        self.signin_button = None
        self.remind_button = None
        self.error_toggle = None
        self.error_msg = None
        self.connect_manager = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def PassVar(self, connect_manager):
        self.connect_manager = connect_manager

    def is_logged_in(self):
        return bool(self._user)

    def get_user(self):
        return self._user

    def onInit(self):
        self.user_field = self._add_editcontrol(755, 338, 40, 415, False)
        self.setFocus(self.user_field)
        self.password_field = self._add_editcontrol(755, 448, 40, 415, True)
        self.signin_button = self.getControl(SIGN_IN)
        self.remind_button = self.getControl(CANCEL)
        self.error_toggle = self.getControl(ERROR_TOGGLE)
        self.error_msg = self.getControl(ERROR_MSG)
        self.user_field.controlUp(self.remind_button)
        self.user_field.controlDown(self.password_field)
        self.password_field.controlUp(self.user_field)
        self.password_field.controlDown(self.signin_button)
        self.signin_button.controlUp(self.password_field)
        self.remind_button.controlDown(self.user_field)

    def onClick(self, control):
        if control == SIGN_IN:
            # Sign in to emby connect
            self._disable_error()
            user = self.user_field.getText()
            password = self.password_field.getText()

            if not user or not password:
                # Display error
                self._error(ERROR['Empty'], Utils.Translate('empty_user_pass'))
                LOG.error("Username or password cannot be null")
            elif self._login(user, password):
                self.close()
        elif control == CANCEL:
            # Remind me later
            self.close()

    def onAction(self, action):
        if self.error == ERROR['Empty'] and self.user_field.getText() and self.password_field.getText():
            self._disable_error()

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def _add_editcontrol(self, x, y, height, width, password):
        os.path.join(xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlEdit(0, 0, 0, 0, label="", font="font13", textColor="FF52b54b", disabledColor="FF888888", focusTexture="-", noFocusTexture="-")
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)
        self.addControl(control)

        if password:
            control.setType(xbmcgui.INPUT_TYPE_PASSWORD, "Please enter password")

        return control

    def _login(self, username, password):
        result = self.connect_manager.login_to_connect(username, password)

        if not result:
            self._error(ERROR['Invalid'], Utils.Translate('invalid_auth'))
            return False

        self._user = result
        username = result['User']['Name']
        Utils.dialog("notification", heading="{emby}", message="%s %s" % (Utils.Translate(33000), Utils.StringDecode(username)), icon=result['User'].get('ImageUrl') or "{emby}", time=2000, sound=False)
        return True

    def _error(self, state, message):
        self.error = state
        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('true')

    def _disable_error(self):
        self.error = None
        self.error_toggle.setVisibleCondition('false')

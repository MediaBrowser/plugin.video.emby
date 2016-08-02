# -*- coding: utf-8 -*-

##################################################################################################

import hashlib
import logging
import os

import xbmcgui
import xbmcaddon

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
SIGN_IN = 200
CANCEL = 201

##################################################################################################


class LoginConnect(xbmcgui.WindowXMLDialog):

    user = None
    password = None


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        
        self.user_field = self._add_editcontrol(685,385,40,500)
        self.setFocus(self.user_field)
        self.password_field = self._add_editcontrol(685,470,40,500, password=1)
        self.signin_button = self.getControl(SIGN_IN)
        self.remind_button = self.getControl(CANCEL)

        self.user_field.controlUp(self.remind_button)
        self.user_field.controlDown(self.password_field)
        self.password_field.controlUp(self.user_field)
        self.password_field.controlDown(self.signin_button)
        self.signin_button.controlUp(self.password_field)
        self.remind_button.controlDown(self.user_field)

    def onClick(self, control):

        if control == SIGN_IN:
            # Sign in to emby connect
            self.user = self.user_field.getText()
            self.password = self.password_field.getText()
            #self.password = hashlib.md5(self.password_field.getText()).hexdigest()
            self.close()

        elif control == CANCEL:
            # Remind me later
            self.close()

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def _add_editcontrol(self, x, y, height, width, password=0):
        
        media = os.path.join(addon.getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlEdit(0,0,0,0,
                            label="User",
                            font="font10",
                            textColor="ff464646",
                            focusTexture=os.path.join(media, "button-focus.png"),
                            noFocusTexture=os.path.join(media, "button-focus.png"),
                            isPassword=password)

        control.setPosition(x,y)
        control.setHeight(height)
        control.setWidth(width)

        self.addControl(control)
        return control
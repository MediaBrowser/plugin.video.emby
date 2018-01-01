# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os

import xbmcgui
import xbmcaddon

from utils import window

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

RESUME_BUTTON = 3010
START_BEGINNING_BUTTON = 3011
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92

##################################################################################################


class ResumeDialog(xbmcgui.WindowXMLDialog):

    _resume_point = None
    selected_option = None

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_resume_point(self, time):
        self._resume_point = time

    def is_selected(self):
        return True if self.selected_option else False

    def get_selected(self):
        return self.selected_option

    def onInit(self):
        self.getControl(RESUME_BUTTON).setLabel(self._resume_point)
        self.getControl(START_BEGINNING_BUTTON).setLabel('Start from beginning')

    def doAction(self, actionID):
        
        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def onClick(self, controlID):

        if controlID == RESUME_BUTTON:
            self.selected_option = 1
            self.close()

        if controlID == START_BEGINNING_BUTTON:
            self.selected_option = 0
            self.close()

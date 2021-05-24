# -*- coding: utf-8 -*-
import os

import xbmcgui
import xbmcaddon

import helper.utils
import helper.loghandler

class ContextMenu(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._options = []
        self.selected_option = None
        self.list_ = None
        self.LOG = helper.loghandler.LOG('EMBY.dialogs.context.ContextMenu')
        self.Utils = helper.utils.Utils()
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_options(self, options):
        self._options = options

    def is_selected(self):
        return bool(self.selected_option)

    def get_selected(self):
        return self.selected_option

    def onInit(self):
        if self.Utils.Settings.emby_UserImage:
            self.getControl(150).setImage(self.Utils.Settings.emby_UserImage)

        self.LOG.info("options: %s" % self._options)
        self.list_ = self.getControl(155)

        for option in self._options:
            self.list_.addItem(self._add_listitem(option))

        self.setFocus(self.list_)

    def onAction(self, action):
        if action in (92, 9, 10):
            self.close()

        if action in (7, 100):
            if self.getFocusId() == 155:
                option = self.list_.getSelectedItem()
                self.selected_option = option.getLabel()
                self.LOG.info('option selected: %s' % self.selected_option)
                self.close()

    def _add_editcontrol(self, x, y, height, width):
        media = os.path.join(xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlImage(0, 0, 0, 0, filename=os.path.join(media, "white.png"), aspectRatio=0, colorDiffuse="ff111111")
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)
        self.addControl(control)
        return control

    def _add_listitem(self, label):
        return xbmcgui.ListItem(label)

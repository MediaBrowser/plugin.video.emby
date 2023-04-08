import xbmc
import xbmcgui


class ContextMenu(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._options = []
        self.selected_option = None
        self.list_ = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def PassVar(self, options):
        self.selected_option = None
        self._options = options

    def is_selected(self):
        return bool(self.selected_option)

    def get_selected(self):
        return self.selected_option

    def onInit(self):
        xbmc.log(f"EMBY.dialogs.context: options: {self._options}", 1) # LOGINFO
        self.list_ = self.getControl(155)

        for option in self._options:
            self.list_.addItem(xbmcgui.ListItem(option))

        self.setFocus(self.list_)

    def onAction(self, action):
        if action in (92, 9, 10):
            self.list_.reset()
            self.close()

        if action in (7, 100):
            if self.getFocusId() == 155:
                option = self.list_.getSelectedItem()
                self.selected_option = option.getLabel()
                xbmc.log(f"EMBY.dialogs.context: option selected: {self.selected_option}", 1) # LOGINFO
                self.list_.reset()
                self.close()

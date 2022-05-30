import xbmcgui
from helper import loghandler

LOG = loghandler.LOG('EMBY.dialogs.context')


class ContextMenu(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._options = []
        self.selected_option = None
        self.list_ = None
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def PassVar(self, options):
        self._options = options

    def is_selected(self):
        return bool(self.selected_option)

    def get_selected(self):
        return self.selected_option

    def onInit(self):
        LOG.info("options: %s" % self._options)
        self.list_ = self.getControl(155)

        for option in self._options:
            self.list_.addItem(xbmcgui.ListItem(option))

        self.setFocus(self.list_)

    def onAction(self, action):
        if action in (92, 9, 10):
            self.close()

        if action in (7, 100):
            if self.getFocusId() == 155:
                option = self.list_.getSelectedItem()
                self.selected_option = option.getLabel()
                LOG.info('option selected: %s' % self.selected_option)
                self.close()

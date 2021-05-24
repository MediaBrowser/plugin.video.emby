# -*- coding: utf-8 -*-
import json

import xbmc
import xbmcaddon

import database.database
import helper.utils
import helper.loghandler
import dialogs.context

class Context():
    def __init__(self, Utils, EmbyServers, library):
        self.LOG = helper.loghandler.LOG('EMBY.context.Context')
        self._selected_option = None
        self.Utils = Utils
        self.item = None
        self.EmbyServers = EmbyServers
        self.library = library
        self.XML_PATH = (xbmcaddon.Addon('plugin.video.emby-next-gen').getAddonInfo('path'), "default", "1080i")
        self.server_id = None
        self.OPTIONS = {
            'Refresh': self.Utils.Translate(30410),
            'Delete': self.Utils.Translate(30409),
            'Addon': self.Utils.Translate(30408),
            'AddFav': self.Utils.Translate(30405),
            'RemoveFav': self.Utils.Translate(30406),
            'Transcode': self.Utils.Translate(30412)
        }

    def load_item(self):
        for server_id in self.EmbyServers: ######################## WORKAROUND!!!!!!!!!!!
            self.server_id = server_id
            break

        kodi_id = xbmc.getInfoLabel('ListItem.DBID')
        media = xbmc.getInfoLabel('ListItem.DBTYPE')
        self.item = database.database.get_item(self.Utils, kodi_id, media)

        if not self.item:
            return False

        return True

    def delete_item(self, LoadItem=False):
        if LoadItem:
            if not self.load_item():
                return

        self.EmbyServers[self.server_id].API.delete_item(self.item[0])
        self.library[self.server_id].removed([self.item[0]])
        self.library[self.server_id].delay_verify([self.item[0]])

    def select_menu(self):
        options = []

        if not self.load_item():
            return

        Userdata = json.loads(self.item[4]) if self.item[4] else {}

        if self.item[3] not in 'Season':
            if Userdata.get('IsFavorite'):
                options.append(self.OPTIONS['RemoveFav'])
            else:
                options.append(self.OPTIONS['AddFav'])

        options.append(self.OPTIONS['Refresh'])

        if self.Utils.Settings.enableContextDelete:
            options.append(self.OPTIONS['Delete'])

        options.append(self.OPTIONS['Addon'])
        context_menu = dialogs.context.ContextMenu("script-emby-context.xml", *self.XML_PATH)
        context_menu.set_options(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        if self._selected_option:
            self.action_menu()

    def action_menu(self):
        selected = self.Utils.StringDecode(self._selected_option)

        if selected == self.OPTIONS['Refresh']:
            self.EmbyServers[self.server_id].API.refresh_item(self.item[0])
        elif selected == self.OPTIONS['AddFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], True)
        elif selected == self.OPTIONS['RemoveFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], False)
        elif selected == self.OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
        elif selected == self.OPTIONS['Delete']:
            self.delete_item(False)

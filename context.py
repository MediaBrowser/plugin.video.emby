# -*- coding: utf-8 -*-
import json

import xbmc
import xbmcaddon

import database.database
import dialogs.context
import emby.main
import helper.utils
import helper.loghandler

class Context():
    def __init__(self, delete):
        self.LOG = helper.loghandler.LOG('EMBY.context.Context')
        self._selected_option = None
        self.Utils = helper.utils.Utils()
        self.server_id = None
        self.kodi_id = None
        self.media = None
        self.XML_PATH = (xbmcaddon.Addon('plugin.video.emby-next-gen').getAddonInfo('path'), "default", "1080i")
        self.OPTIONS = {
            'Refresh': self.Utils.Translate(30410),
            'Delete': self.Utils.Translate(30409),
            'Addon': self.Utils.Translate(30408),
            'AddFav': self.Utils.Translate(30405),
            'RemoveFav': self.Utils.Translate(30406),
            'Transcode': self.Utils.Translate(30412)
        }

        if xbmc.getInfoLabel('ListItem.Property(embyid)'):
            item_id = xbmc.getInfoLabel('ListItem.Property(embyid)')
        else:
            self.kodi_id = xbmc.getInfoLabel('ListItem.DBID')
            self.media = xbmc.getInfoLabel('ListItem.DBTYPE')
            item_id = None

        ServerOnline = False

        for _ in range(60):
            if self.Utils.window('emby.online.bool'):
                ServerOnline = True
                break

            xbmc.sleep(500)

        if not ServerOnline:
            return

        #Load server connection data
        self.server = emby.main.Emby(self.Utils, self.server_id).get_client()
        emby.main.Emby(self.Utils).set_state(self.Utils.window('emby.server.state.json'))

        for server in self.Utils.window('emby.server.states.json') or []:
            emby.main.Emby(self.Utils, server).set_state(self.Utils.window('emby.server.%s.state.json' % server))

        if item_id:
            self.item = self.server['api'].get_item(item_id)
        else:
            self.item = self.get_item_id()

        if self.item:
            if delete:
                self.delete_item()

            elif self.select_menu():
                self.action_menu()

    def get_server(self, server_id):
        ServerOnline = False

        for _ in range(60):
            if self.Utils.window('emby.online.bool'):
                ServerOnline = True
                break

            xbmc.sleep(500)

        self.EmbyServer = emby.main.Emby(self.Utils, server_id)
        self.EmbyServer.set_state(self.Utils.window('emby.server.%s.state.json' % server_id))
        return ServerOnline

    #Get synced item from embydb
    def get_item_id(self):
        item = database.database.get_item(self.Utils, self.kodi_id, self.media)

        if not item:
            return {}

        return {
            'Id': item[0],
            'UserData': json.loads(item[4]) if item[4] else {},
            'Type': item[3]
        }

    #Display the select dialog.
    #Favorites, Refresh, Delete (opt), Settings.
    def select_menu(self):
        options = []

        if self.item['Type'] not in 'Season':
            if self.item['UserData'].get('IsFavorite'):
                options.append(self.OPTIONS['RemoveFav'])
            else:
                options.append(self.OPTIONS['AddFav'])

        options.append(self.OPTIONS['Refresh'])

        if self.Utils.settings('enableContextDelete.bool'):
            options.append(self.OPTIONS['Delete'])

        options.append(self.OPTIONS['Addon'])
        context_menu = dialogs.context.ContextMenu("script-emby-context.xml", *self.XML_PATH)
        context_menu.set_options(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        return self._selected_option

    def action_menu(self):
        selected = self.Utils.StringDecode(self._selected_option)

        if selected == self.OPTIONS['Refresh']:
            self.Utils.event('RefreshItem', {'Id': self.item['Id']})

        elif selected == self.OPTIONS['AddFav']:
            self.Utils.event('AddFavItem', {'Id': self.item['Id']})

        elif selected == self.OPTIONS['RemoveFav']:
            self.Utils.event('RemoveFavItem', {'Id': self.item['Id']})

        elif selected == self.OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')

        elif selected == self.OPTIONS['Delete']:
            self.delete_item()

    def delete_item(self):
        delete = True

        if not self.Utils.settings('skipContextMenu.bool'):
            if not self.Utils.dialog("yesno", heading="{emby}", line1=self.Utils.Translate(33015)):
                delete = False

        if delete:
            self.server['api'].delete_item(self.item['Id'])
            self.Utils.event("LibraryChanged", {'ItemsRemoved': [self.item['Id']], 'ItemsVerify': [self.item['Id']], 'ItemsUpdated': [], 'ItemsAdded': []})

if __name__ == "__main__":
    Context()

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
    def __init__(self, delete=False):
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

        if not self.set_server():
            return

        if item_id:
            self.item = self.EmbyServer[self.server_id].API.get_item(item_id)
        else:
            self.item = self.get_item_id()

        if self.item:
            if delete:
                self.delete_item()

            elif self.select_menu():
                self.action_menu()

    def set_server(self):
        if not self.server_id or self.server_id == 'None': #load first server WORKAROUND!!!!!!!!!!!
            server_ids = self.Utils.window('emby.servers.json')

            for server_id in server_ids:
                self.server_id = server_id
                break

        ServerOnline = False
        self.EmbyServer = {}
        self.EmbyServerName = {}
        server_ids = self.Utils.window('emby.servers.json')

        for server_id in server_ids:
            for _ in range(60):
                if self.Utils.window('emby.server.%s.online.bool' % server_id):
                    ServerOnline = True
                    self.EmbyServer[server_id] = emby.main.Emby(self.Utils, server_id)
                    self.EmbyServer[server_id].set_state()
                    self.EmbyServerName[server_id] = self.EmbyServer[server_id].Data['auth.server-name']
                    break

                xbmc.sleep(500)

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
            self.Utils.event('RefreshItem', {'Id': self.item['Id'], 'ServerId' : self.server_id})

        elif selected == self.OPTIONS['AddFav']:
            self.Utils.event('AddFavItem', {'Id': self.item['Id'], 'ServerId' : self.server_id})

        elif selected == self.OPTIONS['RemoveFav']:
            self.Utils.event('RemoveFavItem', {'Id': self.item['Id'], 'ServerId' : self.server_id})

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
            self.EmbyServer[self.server_id].API.delete_item(self.item['Id'])
            self.Utils.event("LibraryChanged", {'ServerId' : self.server_id, 'ItemsRemoved': [self.item['Id']], 'ItemsVerify': [self.item['Id']], 'ItemsUpdated': [], 'ItemsAdded': []})

if __name__ == "__main__":
    Context()

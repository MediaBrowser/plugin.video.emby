import json
import logging
import xbmc
import xbmcaddon

import database.database
import dialogs.context
import emby.main
import helper.translate
import helper.utils
import helper.loghandler

class Context():
    def __init__(self, play=False, transcode=False, delete=False):
        helper.loghandler.reset()
        helper.loghandler.config()
        self.LOG = logging.getLogger("EMBY.context.Context")
        self._selected_option = None
        self.Utils = helper.utils.Utils()
        self.server_id = None
        self.kodi_id = None
        self.media = None
        self.XML_PATH = (xbmcaddon.Addon('plugin.video.emby-next-gen').getAddonInfo('path'), "default", "1080i")
        self.OPTIONS = {
            'Refresh': helper.translate._(30410),
            'Delete': helper.translate._(30409),
            'Addon': helper.translate._(30408),
            'AddFav': helper.translate._(30405),
            'RemoveFav': helper.translate._(30406),
            'Transcode': helper.translate._(30412)
        }

#        try:
#            self.kodi_id = max(sys.listitem.getVideoInfoTag().getDbId(), 0) or max(sys.listitem.getMusicInfoTag().getDbId(), 0) or None
#            self.media = self.get_media_type()
#            self.server_id = sys.listitem.getProperty('embyserver') or None
#            item_id = sys.listitem.getProperty('embyid')
#        except AttributeError:
        if xbmc.getInfoLabel('ListItem.Property(embyid)'):
            item_id = xbmc.getInfoLabel('ListItem.Property(embyid)')
        else:
            self.kodi_id = xbmc.getInfoLabel('ListItem.DBID')
            self.media = xbmc.getInfoLabel('ListItem.DBTYPE')
            item_id = None

        ServerOnline = False

        for i in range(60):
            if self.Utils.window('emby_online.bool'):
                ServerOnline = True
                break

            xbmc.sleep(500)

        if not ServerOnline:
            helper.loghandler.reset()
            return

        #Load server connection data
        self.server = emby.main.Emby(self.server_id).get_client()
        emby.main.Emby().set_state(self.Utils.window('emby.server.state.json'))

        for server in self.Utils.window('emby.server.states.json') or []:
            emby.main.Emby(server).set_state(self.Utils.window('emby.server.%s.state.json' % server))

        if item_id:
            self.item = self.server['api'].get_item(item_id)
        else:
            self.item = self.get_item_id()

        if self.item:
            if delete:
                self.delete_item()

            elif self.select_menu():
                self.action_menu()

    #Get media type based on sys.listitem. If unfilled, base on visible window
#    def get_media_type(self):
#        media = sys.listitem.getVideoInfoTag().getMediaType() or sys.listitem.getMusicInfoTag().getMediaType()

#        if not media:
#            if xbmc.getCondVisibility('Container.Content(albums)'):
#                media = "album"
#            elif xbmc.getCondVisibility('Container.Content(artists)'):
#                media = "artist"
#            elif xbmc.getCondVisibility('Container.Content(songs)'):
#                media = "song"
#            elif xbmc.getCondVisibility('Container.Content(pictures)'):
#                media = "picture"
#            else:
#                self.LOG.info("media is unknown")

#        return media.decode('utf-8')

    #Get synced item from embydb
    def get_item_id(self):
        item = database.database.get_item(self.kodi_id, self.media)

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
            self.server['api'].refresh_item(self.item['Id'])

        elif selected == self.OPTIONS['AddFav']:
            self.server['api'].favorite(self.item['Id'], True)

        elif selected == self.OPTIONS['RemoveFav']:
            self.server['api'].favorite(self.item['Id'], False)

        elif selected == self.OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')

        elif selected == self.OPTIONS['Delete']:
            self.delete_item()

    def delete_item(self):
        delete = True

        if not self.Utils.settings('skipContextMenu.bool'):
            if not self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33015)):
                delete = False

        if delete:
            self.server['api'].delete_item(self.item['Id'])
            self.Utils.event("LibraryChanged", {'ItemsRemoved': [self.item['Id']], 'ItemsVerify': [self.item['Id']], 'ItemsUpdated': [], 'ItemsAdded': []})

if __name__ == "__main__":
    Context()

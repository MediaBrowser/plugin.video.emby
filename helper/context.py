# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon
import database.db_open
import dialogs.context
import emby.listitem as ListItem
from . import loghandler
from . import utils as Utils

XmlPath = (xbmcaddon.Addon(Utils.PluginId).getAddonInfo('path'), "default", "1080i")
SelectOptions = {'Refresh': Utils.Translate(30410), 'Delete': Utils.Translate(30409), 'Addon': Utils.Translate(30408), 'AddFav': Utils.Translate(30405), 'RemoveFav': Utils.Translate(30406), 'SpecialFeatures': "Special Features"}
LOG = loghandler.LOG('EMBY.context.Context')


class Context:
    def __init__(self, EmbyServers):
        self._selected_option = None
        self.item = None
        self.EmbyServers = EmbyServers
        self.server_id = None
        self.SpecialFeaturesSelections = []

    def load_item(self):
        Found = False

        for server_id in self.EmbyServers:
            self.server_id = server_id
            kodi_id = xbmc.getInfoLabel('ListItem.DBID')
            media = xbmc.getInfoLabel('ListItem.DBTYPE')

            with database.db_open.io(Utils.DatabaseFiles, server_id, False) as embydb:
                self.item = embydb.get_full_item_by_kodi_id(kodi_id, media)

            if self.item:
                Found = True
                break

        return Found

    def delete_item(self, LoadItem):
        if LoadItem:
            if not self.load_item():
                return

        if Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33015)):
            self.EmbyServers[self.server_id].API.delete_item(self.item[0])
            self.EmbyServers[self.server_id].library.removed([self.item[0]])

    def SelectSpecialFeatures(self):
        MenuData = []

        for SpecialFeaturesSelection in self.SpecialFeaturesSelections:
            MenuData.append(SpecialFeaturesSelection['Name'])

        resp = Utils.dialog("select", "Special Features", MenuData)

        if resp < 0:
            return

        ItemData = self.SpecialFeaturesSelections[resp]
        item = self.EmbyServers[self.server_id].API.get_item(ItemData['Id'])
        li = ListItem.set_ListItem(item, self.server_id)

        if len(item['MediaSources'][0]['MediaStreams']) >= 1:
            path = "http://127.0.0.1:57578/embyvideoremote-%s-%s-%s-%s-%s-%s-%s" % (self.server_id, item['Id'], "movie", item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], item['MediaSources'][0]['MediaStreams'][0]['Codec'], Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))
        else:
            path = "http://127.0.0.1:57578/embyvideoremote-%s-%s-%s-%s-%s-%s-%s" % (self.server_id, item['Id'], "movie", item['MediaSources'][0]['Id'], "0", "", Utils.PathToFilenameReplaceSpecialCharecters(item['Path']))

        li.setProperty('path', path)
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        Pos = playlist.getposition() + 1
        playlist.add(path, li, index=Pos)
        xbmc.Player().play(playlist, li, False, Pos)

    def select_menu(self):
        options = []
        self.SpecialFeaturesSelections = []

        if not self.load_item():
            return

        # Load SpecialFeatures
        with database.db_open.io(Utils.DatabaseFiles, self.server_id, False) as embydb:
            SpecialFeaturesIds = embydb.get_special_features(self.item[0])

            for SpecialFeaturesId in SpecialFeaturesIds:
                SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])
                self.SpecialFeaturesSelections.append({"Name": SpecialFeaturesMediasources[0][4], "Id": SpecialFeaturesId[0]})

        if self.item[4]:
            options.append(SelectOptions['RemoveFav'])
        else:
            options.append(SelectOptions['AddFav'])

        options.append(SelectOptions['Refresh'])

        if self.SpecialFeaturesSelections:
            options.append(SelectOptions['SpecialFeatures'])

        if Utils.enableContextDelete:
            options.append(SelectOptions['Delete'])

        options.append(SelectOptions['Addon'])
        context_menu = dialogs.context.ContextMenu("script-emby-context.xml", *XmlPath)
        context_menu.PassVar(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        if self._selected_option:
            self.action_menu()

    def action_menu(self):
        selected = Utils.StringDecode(self._selected_option)

        if selected == SelectOptions['Refresh']:
            self.EmbyServers[self.server_id].API.refresh_item(self.item[0])
        elif selected == SelectOptions['AddFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], True)
        elif selected == SelectOptions['RemoveFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], False)
        elif selected == SelectOptions['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % Utils.PluginId)
        elif selected == SelectOptions['Delete']:
            self.delete_item(False)
        elif selected == SelectOptions['SpecialFeatures']:
            self.SelectSpecialFeatures()

# -*- coding: utf-8 -*-
import threading
import xbmc
import xbmcaddon
from database import dbio
from dialogs import context
from emby import listitem
from . import loghandler
from . import utils

XmlPath = (xbmcaddon.Addon(utils.PluginId).getAddonInfo('path'), "default", "1080i")
SelectOptions = {'Refresh': utils.Translate(30410), 'Delete': utils.Translate(30409), 'Addon': utils.Translate(30408), 'AddFav': utils.Translate(30405), 'RemoveFav': utils.Translate(30406), 'SpecialFeatures': "Special Features"}
LOG = loghandler.LOG('EMBY.helper.context')


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
            embydb = dbio.DBOpen(server_id)
            self.item = embydb.get_full_item_by_kodi_id(kodi_id, media)
            dbio.DBClose(server_id, False)

            if self.item:
                Found = True
                break

        return Found

    def delete_item(self, LoadItem=False):  # threaded by caller
        if utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33015)):
            ItemFound = True

            if LoadItem:
                ItemFound = self.load_item()

            if ItemFound:
                self.EmbyServers[self.server_id].API.delete_item(self.item[0])
                self.EmbyServers[self.server_id].library.removed([self.item[0]])

    def SelectSpecialFeatures(self):
        MenuData = []

        for SpecialFeaturesSelection in self.SpecialFeaturesSelections:
            MenuData.append(SpecialFeaturesSelection['Name'])

        resp = utils.dialog(utils.Translate(33230), utils.Translate(33231), MenuData)

        if resp < 0:
            return

        ItemData = self.SpecialFeaturesSelections[resp]
        item = self.EmbyServers[self.server_id].API.get_item(ItemData['Id'])
        li = listitem.set_ListItem(item, self.server_id)

        if len(item['MediaSources'][0]['MediaStreams']) >= 1:
            path = "http://127.0.0.1:57578/embyvideodynamic-%s-%s-%s-%s-%s-%s-%s" % (self.server_id, item['Id'], "movie", item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], item['MediaSources'][0]['MediaStreams'][0]['Codec'], utils.PathToFilenameReplaceSpecialCharecters(item['Path']))
        else:
            path = "http://127.0.0.1:57578/embyvideodynamic-%s-%s-%s-%s-%s-%s-%s" % (self.server_id, item['Id'], "movie", item['MediaSources'][0]['Id'], "0", "", utils.PathToFilenameReplaceSpecialCharecters(item['Path']))

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
        embydb = dbio.DBOpen(self.server_id)
        SpecialFeaturesIds = embydb.get_special_features(self.item[0])

        for SpecialFeaturesId in SpecialFeaturesIds:
            SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])
            self.SpecialFeaturesSelections.append({"Name": SpecialFeaturesMediasources[0][4], "Id": SpecialFeaturesId[0]})

        dbio.DBClose(self.server_id, False)

        if self.item[4]:
            options.append(SelectOptions['RemoveFav'])
        else:
            options.append(SelectOptions['AddFav'])

        options.append(SelectOptions['Refresh'])

        if self.SpecialFeaturesSelections:
            options.append(SelectOptions['SpecialFeatures'])

        if utils.enableContextDelete:
            options.append(SelectOptions['Delete'])

        options.append(SelectOptions['Addon'])
        context_menu = context.ContextMenu("script-emby-context.xml", *XmlPath)
        context_menu.PassVar(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        if self._selected_option:
            self.action_menu()

    def action_menu(self):
        selected = utils.StringDecode(self._selected_option)

        if selected == SelectOptions['Refresh']:
            self.EmbyServers[self.server_id].API.refresh_item(self.item[0])
        elif selected == SelectOptions['AddFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], True)
        elif selected == SelectOptions['RemoveFav']:
            self.EmbyServers[self.server_id].API.favorite(self.item[0], False)
        elif selected == SelectOptions['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
        elif selected == SelectOptions['Delete']:
            threading.Thread(target=self.delete_item).start()
        elif selected == SelectOptions['SpecialFeatures']:
            self.SelectSpecialFeatures()

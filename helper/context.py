import xbmc
import xbmcaddon
from database import dbio
from dialogs import context
from emby import listitem
from . import utils, loghandler

XmlPath = (xbmcaddon.Addon(utils.PluginId).getAddonInfo('path'), "default", "1080i")
SelectOptions = {'Refresh': utils.Translate(30410), 'Delete': utils.Translate(30409), 'Addon': utils.Translate(30408), 'AddFav': utils.Translate(30405), 'RemoveFav': utils.Translate(30406), 'SpecialFeatures': "Special Features"}
XbmcPlayer = xbmc.Player()
LOG = loghandler.LOG('EMBY.helper.context')


def load_item():
    item = None
    server_id = None

    for server_id in utils.EmbyServers:
        kodi_id = xbmc.getInfoLabel('ListItem.DBID')
        media = xbmc.getInfoLabel('ListItem.DBTYPE')
        embydb = dbio.DBOpenRO(server_id, "load_item")
        item = embydb.get_full_item_by_kodi_id(kodi_id, media)
        dbio.DBCloseRO(server_id, "load_item")

        if item:
            break

    return item, server_id

def delete_item(LoadItem, item=None, server_id=""):  # threaded by caller
    if utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33015)):
        if LoadItem:
            item, server_id = load_item()

        if item:
            utils.EmbyServers[server_id].API.delete_item(item[0])
            utils.EmbyServers[server_id].library.removed([item[0]])

def select_menu():
    options = []
    SpecialFeaturesSelections = []
    item, server_id = load_item()

    if not item:
        return

    # Load SpecialFeatures
    embydb = dbio.DBOpenRO(server_id, "select_menu")
    SpecialFeaturesIds = embydb.get_special_features(item[0])

    for SpecialFeaturesId in SpecialFeaturesIds:
        SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])
        SpecialFeaturesSelections.append({"Name": SpecialFeaturesMediasources[0][4], "Id": SpecialFeaturesId[0]})

    dbio.DBCloseRO(server_id, "select_menu")

    if item[4]:
        options.append(SelectOptions['RemoveFav'])
    else:
        options.append(SelectOptions['AddFav'])

    options.append(SelectOptions['Refresh'])

    if SpecialFeaturesSelections:
        options.append(SelectOptions['SpecialFeatures'])

    if utils.enableContextDelete:
        options.append(SelectOptions['Delete'])

    options.append(SelectOptions['Addon'])
    context_menu = context.ContextMenu("script-emby-context.xml", *XmlPath)
    context_menu.PassVar(options)
    context_menu.doModal()

    if context_menu.is_selected():
        selected_option = context_menu.get_selected()

        if selected_option == SelectOptions['Refresh']:
            utils.EmbyServers[server_id].API.refresh_item(item[0])
        elif selected_option == SelectOptions['AddFav']:
            utils.EmbyServers[server_id].API.favorite(item[0], True)
        elif selected_option == SelectOptions['RemoveFav']:
            utils.EmbyServers[server_id].API.favorite(item[0], False)
        elif selected_option == SelectOptions['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
        elif selected_option == SelectOptions['Delete']:
            delete_item(False, item, server_id)
        elif selected_option == SelectOptions['SpecialFeatures']:
            MenuData = []

            for SpecialFeaturesSelection in SpecialFeaturesSelections:
                MenuData.append(SpecialFeaturesSelection['Name'])

            resp = utils.dialog(utils.Translate(33230), utils.Translate(33231), MenuData)

            if resp < 0:
                return

            ItemData = SpecialFeaturesSelections[resp]
            SpecialFeatureItem = utils.EmbyServers[server_id].API.get_Item(ItemData['Id'], ['Movie'], True, False)
            li = listitem.set_ListItem(SpecialFeatureItem, server_id)

            if len(SpecialFeatureItem['MediaSources'][0]['MediaStreams']) >= 1:
                path = "http://127.0.0.1:57342/m-%s-%s-%s-None-None-%s-0-1-%s-%s" % (server_id, SpecialFeatureItem['Id'], SpecialFeatureItem['MediaSources'][0]['Id'], SpecialFeatureItem['MediaSources'][0]['MediaStreams'][0]['BitRate'], SpecialFeatureItem['MediaSources'][0]['MediaStreams'][0]['Codec'], utils.PathToFilenameReplaceSpecialCharecters(SpecialFeatureItem['Path']))
            else:
                path = "http://127.0.0.1:57342/m-%s-%s-%s-None-None-%s-0-1-%s-%s" % (server_id, SpecialFeatureItem['Id'], SpecialFeatureItem['MediaSources'][0]['Id'], 0, "", utils.PathToFilenameReplaceSpecialCharecters(SpecialFeatureItem['Path']))

            li.setProperty('path', path)
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            Pos = playlist.getposition() + 1
            playlist.add(path, li, index=Pos)
            XbmcPlayer.play(playlist, li, False, Pos)

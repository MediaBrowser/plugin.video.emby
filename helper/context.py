import xbmc
from database import dbio
from dialogs import context
from emby import listitem
from . import utils, loghandler, pluginmenu

SelectOptions = {'Refresh': utils.Translate(30410), 'Delete': utils.Translate(30409), 'Addon': utils.Translate(30408), 'AddFav': utils.Translate(30405), 'RemoveFav': utils.Translate(30406), 'SpecialFeatures': utils.Translate(33231)}
LOG = loghandler.LOG('EMBY.helper.context')


def load_item():
    item = None
    server_id = xbmc.getInfoLabel('ListItem.Property(embyserverid)')
    emby_id = xbmc.getInfoLabel('ListItem.Property(embyid)')

    if not server_id:
        for server_id in utils.EmbyServers:
            kodi_id = xbmc.getInfoLabel('ListItem.DBID')
            media = xbmc.getInfoLabel('ListItem.DBTYPE')
            embydb = dbio.DBOpenRO(server_id, "load_item")
            item = embydb.get_item_by_KodiId_KodiType(kodi_id, media)
            dbio.DBCloseRO(server_id, "load_item")

            if item:
                item = item[0]
                break

        return item, server_id

    pluginmenu.reset_querycache() # Clear Cache
    return (emby_id,), server_id

def delete_item(LoadItem, item=None, server_id=""):  # threaded by caller
    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33015)):
        if LoadItem:
            item, server_id = load_item()

        if item:
            utils.EmbyServers[server_id].API.delete_item(item[0])
            utils.EmbyServers[server_id].library.removed([item[0]])
            xbmc.executebuiltin("Container.Refresh()")

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

    if len(item) > 9:
        if item[10]:
            options.append(SelectOptions['RemoveFav'])
        else:
            options.append(SelectOptions['AddFav'])

    options.append(SelectOptions['Refresh'])

    if SpecialFeaturesSelections:
        options.append(SelectOptions['SpecialFeatures'])

    if utils.enableContextDelete:
        options.append(SelectOptions['Delete'])

    options.append(SelectOptions['Addon'])
    context_menu = context.ContextMenu("script-emby-context.xml", *utils.CustomDialogParameters)
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

            resp = utils.Dialog.select(utils.Translate(33231), MenuData)

            if resp < 0:
                return

            ItemData = SpecialFeaturesSelections[resp]
            SpecialFeatureItem = utils.EmbyServers[server_id].API.get_Item(ItemData['Id'], ['Movie'], True, False)
            li = listitem.set_ListItem(SpecialFeatureItem, server_id)

            if len(SpecialFeatureItem['MediaSources'][0]['MediaStreams']) >= 1:
                path = "http://127.0.0.1:57342/m-%s-%s-%s-0-0-%s-0-1-%s-0-0-0-0-%s" % (server_id, SpecialFeatureItem['Id'], SpecialFeatureItem['MediaSources'][0]['Id'], SpecialFeatureItem['MediaSources'][0]['MediaStreams'][0]['BitRate'], SpecialFeatureItem['MediaSources'][0]['MediaStreams'][0]['Codec'], utils.PathToFilenameReplaceSpecialCharecters(SpecialFeatureItem['Path']))
            else:
                path = "http://127.0.0.1:57342/m-%s-%s-%s-0-0-0-0-1--0-0-0-0-%s" % (server_id, SpecialFeatureItem['Id'], SpecialFeatureItem['MediaSources'][0]['Id'], utils.PathToFilenameReplaceSpecialCharecters(SpecialFeatureItem['Path']))

            li.setProperty('path', path)
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            Pos = playlist.getposition() + 1
            playlist.add(path, li, index=Pos)
            utils.XbmcPlayer.play(playlist, li, False, Pos)

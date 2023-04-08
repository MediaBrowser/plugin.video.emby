import xbmc
import xbmcgui
from database import dbio
from dialogs import context
from emby import listitem
from core import common
from . import utils, pluginmenu, playerops

ContextMenu = context.ContextMenu("script-emby-context.xml", *utils.CustomDialogParameters)
SelectOptions = {'Refresh': utils.Translate(30410), 'Delete': utils.Translate(30409), 'Addon': utils.Translate(30408), 'AddFav': utils.Translate(30405), 'RemoveFav': utils.Translate(30406), 'SpecialFeatures': utils.Translate(33231), "Watch together": utils.Translate(33517), "Remove client control": utils.Translate(33518), "Add client control": utils.Translate(33519), "Enable remote mode": utils.Translate(33520), "Disable remote mode": utils.Translate(33521)}

def load_item():
    item = None
    ServerId = xbmc.getInfoLabel('ListItem.Property(embyserverid)')
    emby_id = xbmc.getInfoLabel('ListItem.Property(embyid)')

    if not ServerId:
        for ServerId in utils.EmbyServers:
            kodi_id = xbmc.getInfoLabel('ListItem.DBID')
            media = xbmc.getInfoLabel('ListItem.DBTYPE')
            embydb = dbio.DBOpenRO(ServerId, "load_item")
            item = embydb.get_item_by_KodiId_KodiType(kodi_id, media)
            dbio.DBCloseRO(ServerId, "load_item")

            if item:
                item = item[0]
                break

        return item, ServerId

    pluginmenu.reset_querycache() # Clear Cache
    return (emby_id,), ServerId

def delete_item(LoadItem, item=None, ServerId=""):  # threaded by caller
    if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33015)):
        if LoadItem:
            item, ServerId = load_item()

        if item:
            utils.EmbyServers[ServerId].API.delete_item(item[0])
            utils.EmbyServers[ServerId].library.removed([item[0]])
            xbmc.executebuiltin("Container.Refresh()")

def specials():
    SpecialFeaturesSelections = []
    item, ServerId = load_item()

    if not item:
        return

    # Load SpecialFeatures
    embydb = dbio.DBOpenRO(ServerId, "specials")
    SpecialFeaturesIds = embydb.get_special_features(item[0])

    for SpecialFeaturesId in SpecialFeaturesIds:
        SpecialFeaturesMediasources = embydb.get_mediasource(SpecialFeaturesId[0])
        SpecialFeaturesSelections.append({"Name": SpecialFeaturesMediasources[0][4], "Id": SpecialFeaturesId[0]})

    dbio.DBCloseRO(ServerId, "specials")
    MenuData = []

    for SpecialFeaturesSelection in SpecialFeaturesSelections:
        MenuData.append(SpecialFeaturesSelection['Name'])

    resp = utils.Dialog.select(utils.Translate(33231), MenuData)

    if resp < 0:
        return

    ItemData = SpecialFeaturesSelections[resp]
    SpecialFeatureItem = utils.EmbyServers[ServerId].API.get_Item(ItemData['Id'], ['Movie'], True, False, True, True)

    if SpecialFeatureItem:
        li = listitem.set_ListItem(SpecialFeatureItem, ServerId)
        path, _ = common.get_path_type_from_item(ServerId, SpecialFeatureItem)
        li.setProperty('path', path)
        Pos = playerops.GetPlayerPosition(1) + 1
        utils.Playlists[1].add(path, li, index=Pos)
        playerops.PlayPlaylistItem(1, Pos)

def select_menu(ListItemLabel):
    item, ServerId = load_item()

    if not item:
        return

    while True:
        options = []

        if len(item) > 9:
            if item[10]:
                options.append(SelectOptions['RemoveFav'])
            else:
                options.append(SelectOptions['AddFav'])

        options.append(SelectOptions['Refresh'])

        if utils.enableContextDelete:
            options.append(SelectOptions['Delete'])

        options.append(SelectOptions['Add client control'])

        if len(playerops.RemoteClientData[ServerId]["SessionIds"]) > 1:
            options.append(SelectOptions['Remove client control'])

            if playerops.RemoteMode:
                options.append(SelectOptions['Disable remote mode'])
            else:
                options.append(SelectOptions['Enable remote mode'])

        if item[2] in ('Episode', 'Movie', 'MusicVideo', 'Audio'):
            options.append(SelectOptions['Watch together'])

        options.append(SelectOptions['Addon'])
        ContextMenu.PassVar(options)
        ContextMenu.doModal()

        if ContextMenu.is_selected():
            selected_option = ContextMenu.get_selected()

            if selected_option == SelectOptions['Refresh']:
                utils.EmbyServers[ServerId].API.refresh_item(item[0])
                break

            if selected_option == SelectOptions['Addon']:
                xbmc.executebuiltin(f"Addon.OpenSettings({utils.PluginId})")
                break

            if selected_option == SelectOptions['Delete']:
                delete_item(False, item, ServerId)
                break

            if selected_option == SelectOptions['Watch together']:
                playerops.WatchTogether = False
                playerops.RemoteControl = False
                playerops.RemoteMode = False

                if len(playerops.RemoteClientData[ServerId]["SessionIds"]) <= 1:
                    if not add_remoteclients(ServerId, ListItemLabel):
                        continue

                playerops.PlayEmby([item[0]], "PlayInit", 0, 0, utils.EmbyServers[ServerId], 0)

                for SessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
                    if SessionId in playerops.RemoteClientData[ServerId]["ExtendedSupportAck"] and SessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
                        utils.EmbyServers[ServerId].API.send_text_msg(SessionId, "remotecommand", f"playinit|{item[0]}|0|0", True)
                    elif SessionId not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
                        utils.EmbyServers[ServerId].API.send_play(SessionId, item[0], "PlayNow", 0, True)
                        utils.EmbyServers[ServerId].API.send_pause(SessionId, True)

                 # give time to prepare streams for all client devices
                ProgressBar = xbmcgui.DialogProgress()
                ProgressBar.create(utils.Translate(33493))
                ProgressBar.update(0, utils.Translate(33493))

                # Delay playback
                WaitFactor = int(int(utils.watchtogeter_start_delay) / 10)

                for Index in range(1, WaitFactor * 100):
                    ProgressBar.update(int(Index / WaitFactor), utils.Translate(33493))

                    if Index % 10 == 0: # modulo 20 -> every 2 seconds resend to unspported client the start
                        for SessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
                            if SessionId not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
                                utils.EmbyServers[ServerId].API.send_pause(SessionId, True)
                                utils.EmbyServers[ServerId].API.send_seek(SessionId, 0, True)

                    if check_ProgressBar(ProgressBar):
                        return

                ProgressBar.close()
                playerops.WatchTogether = True
                playerops.RemoteControl = True
                playerops.RemoteMode = True
                playerops.Unpause()
                playerops.send_RemoteClients(ServerId, [], True, False)
                break

            if selected_option == SelectOptions['AddFav']:
                utils.EmbyServers[ServerId].API.favorite(item[0], True)
            elif selected_option == SelectOptions['RemoveFav']:
                utils.EmbyServers[ServerId].API.favorite(item[0], False)
            elif selected_option == SelectOptions['Add client control']:
                add_remoteclients(ServerId, ListItemLabel)
            elif selected_option == SelectOptions['Remove client control']:
                SelectionLabels = []
                SessionIds = []

                for RemoteClientSessionId in playerops.RemoteClientData[ServerId]["SessionIds"]:
                    if RemoteClientSessionId != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
                        SelectionLabels.append(f"{playerops.RemoteClientData[ServerId]['Devicenames'][RemoteClientSessionId]}, {playerops.RemoteClientData[ServerId]['Usernames'][RemoteClientSessionId]}")
                        SessionIds.append(RemoteClientSessionId)

                Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

                if Selections:
                    RemoveSessionIds = []

                    for Selection in Selections:
                        RemoveSessionIds.append(SessionIds[Selection])

                    playerops.delete_RemoteClient(ServerId, RemoveSessionIds)
            elif selected_option == SelectOptions['Enable remote mode']:
                playerops.RemoteControl = True
                playerops.RemoteMode = True
                playerops.send_RemoteClients(ServerId, [], True, False)
            elif selected_option == SelectOptions['Disable remote mode']:
                playerops.disable_RemoteClients(ServerId)
                playerops.unlink_RemoteClients(ServerId)
        else:
            break

def add_remoteclients(ServerId, ListItemLabel):
    ActiveSessions = utils.EmbyServers[ServerId].API.get_active_sessions()
    SelectionLabels = []
    ClientData = []

    for ActiveSession in ActiveSessions:
        if ActiveSession['SupportsRemoteControl'] and ActiveSession['Id'] != utils.EmbyServers[ServerId].EmbySession[0]['Id']:
            if ActiveSession['Id'] not in playerops.RemoteClientData[ServerId]["SessionIds"]:
                SelectionLabels.append(f"{ActiveSession['DeviceName']}, {ActiveSession['UserName']}")
                ClientData.append((ActiveSession['Id'], ActiveSession['DeviceName'], ActiveSession['UserName']))

    Selections = utils.Dialog.multiselect(utils.Translate(33494), SelectionLabels)

    if not Selections:
        return False

    for Selection in Selections:
        utils.EmbyServers[ServerId].API.send_text_msg(ClientData[Selection][0], "remotecommand", f"connect|{utils.EmbyServers[ServerId].EmbySession[0]['Id']}|60", True)

    # wait for clients
    ProgressBar = xbmcgui.DialogProgress()
    ProgressBar.create(utils.Translate(33495))
    WaitFactor = 10 / utils.remotecontrol_wait_clients

    for Index in range(1, int(utils.remotecontrol_wait_clients) * 10):
        ProgressBar.update(int(Index * WaitFactor), utils.Translate(33492))

        if check_ProgressBar(ProgressBar):
            return False

        if len(Selections) + 1 == len(playerops.RemoteClientData[ServerId]["SessionIds"]):
            break

    ProgressBar.close()

    # Force clients to participate
    for Selection in Selections:
        if ClientData[Selection][0] not in playerops.RemoteClientData[ServerId]["ExtendedSupport"]:
            playerops.add_RemoteClient(ServerId, ClientData[Selection][0], ClientData[Selection][1], ClientData[Selection][2])

    if playerops.RemoteMode:
        playerops.send_RemoteClients(ServerId, [], True, False)

    return True

def check_ProgressBar(ProgressBar):
    if utils.sleep(0.1):
        ProgressBar.close()
        return True

    if ProgressBar.iscanceled():
        ProgressBar.close()
        return True

    return False

def Record():
    Temp = xbmc.getInfoLabel('ListItem.EPGEventIcon') # Icon path has Emby's EPG programId assinged (workaround)
    Temp = Temp[Temp.find("@") + 1:].replace("/","")
    Temp = Temp.split("Z")
    Timers = utils.EmbyServers[Temp[0]].API.get_timer(Temp[1])
    TimerId = 0

    if Timers:
        for Timer in Timers:
            if Timer['ProgramId'] == Temp[1]:
                TimerId = Timer['ProgramInfo']['TimerId']
                break

    if TimerId: # Delete recording
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33496)):
            utils.EmbyServers[Temp[0]].API.delete_timer(TimerId)
    else: # Add recoding
        if utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33497)):
            utils.EmbyServers[Temp[0]].API.set_timer(Temp[1])

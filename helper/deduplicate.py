from database import dbio
import xbmc
from . import utils

def deduplicate():
    MediaSelection = utils.Dialog.select("Select content", [utils.Translate(33582), utils.Translate(33704), utils.Translate(33583), utils.Translate(33481)])

    if MediaSelection == -1: # Cancel
        return

    LibrarySelection = ()
    LibrarySelectionMetadata = ()

    for EmbyServerId, EmbyServer in list(utils.EmbyServers.items()):
        EmbyDB = dbio.DBOpenRO(EmbyServerId, "deduplicate")
        Libraries = EmbyDB.get_LibrarySynced()
        dbio.DBCloseRO(EmbyServerId, "deduplicate")

        for Library in Libraries:
            if Library[2] == "Movie" and MediaSelection == 0 or Library[2] == "Series" and MediaSelection == 1 or Library[2] == "MusicVideo" and MediaSelection == 2 or Library[2] == "Audio" and MediaSelection == 3:
                Lib = f"{Library[1]} ({EmbyServer.ServerData['ServerName']})"

                if Lib not in LibrarySelection:
                    LibrarySelection += (Lib,) # Selection
                    LibrarySelectionMetadata += ((EmbyServer.ServerData['ServerId'], Library[0]),) # ServerId, LibraryIds

    selection = utils.Dialog.select(utils.Translate(33705), list(LibrarySelection))

    if selection == -1: # Cancel
        return

    DoublesSeries = {}
    DoublesSeasons = {}

    if MediaSelection == 0:
        VideoDB = dbio.DBOpenRO("video", "deduplicate")
        DoublesContent = VideoDB.get_movie_doubles()
        dbio.DBCloseRO("video", "deduplicate")
        EmbyType = "Movie"
    elif MediaSelection == 1:
        VideoDB = dbio.DBOpenRO("video", "deduplicate")
        DoublesContent = VideoDB.get_episode_doubles()
        DoublesSeries = VideoDB.get_tvshow_doubles()
        DoublesSeasons = VideoDB.get_season_doubles(DoublesSeries)
        dbio.DBCloseRO("video", "deduplicate")
        EmbyType = "Episode"
    elif MediaSelection == 2:
        VideoDB = dbio.DBOpenRO("video", "deduplicate")
        DoublesContent = VideoDB.get_musicvideos_doubles()
        dbio.DBCloseRO("video", "deduplicate")
        EmbyType = "MusicVideo"
    elif MediaSelection == 3:
        MusicDB = dbio.DBOpenRO("music", "deduplicate")
        DoublesContent = MusicDB.get_song_doubles()
        dbio.DBCloseRO("music", "deduplicate")
        EmbyType = "Audio"
    else:
        return

    if DoublesContent:
        deduplicate_by_library(DoublesContent, EmbyType, LibrarySelectionMetadata, selection)
        deduplicate_by_Embyserver(DoublesContent, LibrarySelectionMetadata, selection)
        deduplicate_by_first(DoublesContent)
        ItemsDelete = {}

        for ContentName, DoublesData in list(DoublesContent.items()):
            for DoubleData in list(DoublesData[0].values()):
                for EmbyLibraryId in DoubleData["EmbyLibraryIds"]:
                    if str(DoubleData["EmbyId"]) != str(DoublesData[1]["PriorityEmbyId"]) or DoubleData["EmbyServerId"] != DoublesData[1]["PriorityEmbyServerId"] or str(EmbyLibraryId) != str(DoublesData[1]["PriorityEmbyLibraryId"]):
                        if DoubleData["EmbyServerId"] not in ItemsDelete:
                            ItemsDelete[DoubleData["EmbyServerId"]] = ((EmbyLibraryId, DoubleData["EmbyId"]),)
                        else:
                            ItemsDelete[DoubleData["EmbyServerId"]] += ((EmbyLibraryId, DoubleData["EmbyId"]),)

                        xbmc.log(f"EMBY.helper.pluginmenu: Deduplicate, delete item {ContentName} [{DoubleData['EmbyServerId']} / {DoubleData['EmbyLibraryIds'][0]}]", 1) # LOGINFO

        for ServerId, EmbyDatas in list(ItemsDelete.items()):
            utils.EmbyServers[ServerId].library.removed_deduplicate(EmbyDatas)

    if DoublesSeasons:
        deduplicate_subcontent(DoublesSeasons, "Season", LibrarySelectionMetadata, selection)

    if DoublesSeries:
        deduplicate_subcontent(DoublesSeries, "Series", LibrarySelectionMetadata, selection)

def deduplicate_subcontent(Doubles, EmbyType, LibrarySelectionMetadata, selection):
    deduplicate_by_library(Doubles, EmbyType, LibrarySelectionMetadata, selection)
    deduplicate_by_Embyserver(Doubles, LibrarySelectionMetadata, selection)
    deduplicate_by_first(Doubles)
    ItemsDelete = {}
    ItemsMerge = {}

    for ContentName, DoublesData in list(Doubles.items()):
        for KodiId, DoubleData in list(DoublesData[0].items()):
            for EmbyLibraryId in DoubleData["EmbyLibraryIds"]:
                if str(DoubleData["EmbyId"]) != str(DoublesData[1]["PriorityEmbyId"]) or DoubleData["EmbyServerId"] != DoublesData[1]["PriorityEmbyServerId"] or str(EmbyLibraryId) != str(DoublesData[1]["PriorityEmbyLibraryId"]):
                    if DoubleData["EmbyServerId"] not in ItemsDelete:
                        ItemsDelete[DoubleData["EmbyServerId"]] = ((EmbyLibraryId, DoubleData["EmbyId"]),)
                    else:
                        ItemsDelete[DoubleData["EmbyServerId"]] += ((EmbyLibraryId, DoubleData["EmbyId"]),)

                    if DoublesData[1]["PriorityKodiId"] in ItemsMerge:
                        ItemsMerge[DoublesData[1]["PriorityKodiId"]] += (KodiId,)
                    else:
                        ItemsMerge[DoublesData[1]["PriorityKodiId"]] = (KodiId,)

                    xbmc.log(f"EMBY.helper.pluginmenu: Deduplicate, delete item {ContentName} [{DoubleData['EmbyServerId']} / {DoubleData['EmbyLibraryIds'][0]}]", 1) # LOGINFO

    if ItemsMerge:
        SQLs = {}
        dbio.DBOpenRW("video", f"deduplicate {EmbyType}", SQLs)

        for PriorityKodiId, KodiIds in list(ItemsMerge.items()):
            for KodiId in KodiIds:
                if EmbyType == "Series":
                    SQLs['video'].update_episode_tvshowid(KodiId, PriorityKodiId)
                    SQLs['video'].update_season_tvshowid(KodiId, PriorityKodiId)
                else:
                    SQLs['video'].update_episode_seasonid(KodiId, PriorityKodiId)

        dbio.DBCloseRW("video", f"deduplicate {EmbyType}", SQLs)

    for ServerId, EmbyDatas in list(ItemsDelete.items()):
        utils.EmbyServers[ServerId].library.removed_deduplicate(EmbyDatas)

def deduplicate_by_library(Doubles, EmbyType, LibrarySelectionMetadata, selection):
    for EmbyServerId in utils.EmbyServers:
        EmbyDB = dbio.DBOpenRO(EmbyServerId, f"deduplicate {EmbyType}")

        for ContentName, DoublesData in list(Doubles.items()):
            for KodiId, DoubleData in list(DoublesData[0].items()):
                EmbyLibraryIds, EmbyId = EmbyDB.get_EmbyIds_LibraryIds_by_KodiIds_EmbyType(KodiId, EmbyType)

                if EmbyId:
                    DoubleData.update({"EmbyServerId": EmbyServerId, "EmbyId": EmbyId, "EmbyLibraryIds": EmbyLibraryIds})

                    if EmbyServerId == LibrarySelectionMetadata[selection][0] and str(LibrarySelectionMetadata[selection][1]) in str(EmbyLibraryIds):
                        DoublesData[1] = {"PriorityEmbyId": EmbyId, "PriorityKodiId": KodiId, "PriorityEmbyServerId": EmbyServerId, "PriorityEmbyLibraryId": LibrarySelectionMetadata[selection][1]}
                        xbmc.log(f"EMBY.helper.pluginmenu: Deduplicate, priority content by library {ContentName} [EmbyId: {EmbyId} / KodiId: {KodiId} / LibraryId: {EmbyLibraryIds} / EmbyServerId: {EmbyServerId} / EmbyType: {EmbyType}]", 1) # LOGINFO

        dbio.DBCloseRO(EmbyServerId, f"deduplicate {EmbyType}")

def deduplicate_by_Embyserver(Doubles, LibrarySelectionMetadata, selection):
    # detect priority content by selected Emby server
    for ContentName, DoublesData in list(Doubles.items()):
        if DoublesData[1]:
            continue

        for KodiId, DoubleData in list(DoublesData[0].items()):
            if DoubleData["EmbyServerId"] == LibrarySelectionMetadata[selection][0]:
                DoublesData[1] = {"PriorityEmbyId": DoubleData["EmbyId"], "PriorityKodiId": KodiId, "PriorityEmbyServerId": DoubleData["EmbyServerId"], "PriorityEmbyLibraryId": DoubleData["EmbyLibraryIds"][0]}
                xbmc.log(f"EMBY.helper.pluginmenu: Deduplicate, priority content by Emby server {ContentName} [EmbyId: {DoublesData[1]['PriorityEmbyId']} / Kodi: {DoublesData[1]['PriorityKodiId']} EmbyServerId: {DoublesData[1]['PriorityEmbyServerId']}]", 1) # LOGINFO
                break

def deduplicate_by_first(Doubles):
    # detect priority content by first valid item
    for ContentName, DoublesData in list(Doubles.items()):
        if DoublesData[1]:
            continue

        for KodiId, DoubleData in list(DoublesData[0].items()):
            if DoubleData["EmbyId"]:
                DoublesData[1] = {"PriorityEmbyId": DoubleData["EmbyId"], "PriorityKodiId": KodiId, "PriorityEmbyServerId": DoubleData["EmbyServerId"], "PriorityEmbyLibraryId": DoubleData["EmbyLibraryIds"][0]}
                xbmc.log(f"EMBY.helper.pluginmenu: Deduplicate, priority content by first {ContentName} [EmbyId: {DoublesData[1]['PriorityEmbyId']} / Kodi: {DoublesData[1]['PriorityKodiId']} EmbyServerId: {DoublesData[1]['PriorityEmbyServerId']}]", 1) # LOGINFO
                break

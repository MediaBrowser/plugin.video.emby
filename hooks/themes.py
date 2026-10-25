import os
import threading
import json
import uuid
import xbmc
import xbmcvfs
from helper import utils, player, queue, playerops, copy
from emby import listitem, metadata
from database import dbio
VolumeFade = player.Volume
VolumeFadeInInterrupt = -1
ThemeQueue = queue.Queue()
RestoreBusy = threading.Lock()
ThemeBusy = threading.Lock()
TerminateTheme = False
TerminateRestore = False
ThemeUpdate = threading.Lock()
FocusOld = ()
FocusPending = ()
FocusPendingKodiType = -1
FocusPendingKodiId = -1
PlayerOpsBusy = threading.Lock()

# Player events (queued by monitor notifications)
def ThemePlay():
    global TerminateRestore
    global TerminateTheme
    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: --->[ ThemePlay ]", 1) # LOGDEBUG

    while True:
        ThemeReceived = ThemeQueue.get()

        if ThemeReceived == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ ThemePlay ]", 1) # LOGDEBUG
            return

        if isinstance(ThemeReceived, dict):
            if ThemeReceived.get("Type") != "STOP" or ThemeReceived["Theme"] is not player.Theme:
                continue

            ThemeReceived = "STOP"

        if ThemeReceived == "STOP":
           # Terminate previous processes
            if RestoreBusy.locked():
                TerminateRestore = True

                with utils.SafeLock(RestoreBusy): # Wait for cancel
                    pass

            if ThemeBusy.locked():
                TerminateTheme = True

                with utils.SafeLock(ThemeBusy): # Wait for cancel
                    pass

            PlaybackStop()
        elif ThemeReceived == "FADE":
            with utils.SafeLock(ThemeBusy): # Wait for cancel
                pass

            with RestoreBusy:
                restore_Volume()
                TerminateRestore = False
        else:
            with utils.SafeLock(RestoreBusy): # Wait for cancel
                pass

            with utils.SafeLock(ThemeBusy):
                PlaybackStopped = PlaybackStop()

                if (PlaybackStopped or not player.Theme["KodiId"]) and ThemeReceived[0] and ThemeReceived[1]:
                    PlaybackStart(ThemeReceived[0], ThemeReceived[1])

                TerminateTheme = False

def PlaybackStart(PlayKodiType, PlayKodiId):
    if PlayKodiType not in ("movie", "tvshow", "musicvideo", "song", "album"):
        return

    global VolumeFade
    global VolumeFadeInInterrupt
    global FocusOld
    ThemeLoading = {"PlayerId": -1, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": "", "Runtime": 0}
    EmbyId = ""
    ServerId = ""
    PositionStart = 0
    PositionEnd = 0
    EndTimeTicks = 0
    ThemeFile = ""
    StartTimeTicks = 0
    Runtime = 0
    PlayerId = -1
    ThemeItem = {}
    EmbyType = utils.KodiTypeMapping[PlayKodiType]
    EmbyDB = None

    for ServerId in list(utils.EmbyServers):
        EmbyDB = dbio.DBOpenRO(ServerId, "Theme")

        if utils.theme_enable_audio and utils.theme_enable_video: # Both
            if utils.theme_priority == "audio":
                EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)

                if not EmbyId:
                    EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)

                    if EmbyId:
                        EmbyType = "Video"
                        PlayerId = 1
                else:
                    EmbyType = "Audio"
                    PlayerId = 0
            else:
                EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)

                if not EmbyId:
                    EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)

                    if EmbyId:
                        EmbyType = "Audio"
                        PlayerId = 0
                else:
                    PlayerId = 1
                    EmbyType = "Video"
        elif utils.theme_enable_audio: # Audio only
            EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)

            if EmbyId:
                EmbyType = "Audio"
                PlayerId = 0
        else: # Video only
            EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)

            if EmbyId:
                EmbyType = "Video"
                PlayerId = 1

        dbio.DBCloseRO(ServerId, "Theme")

        if EmbyId:
            break

    del EmbyDB

    if EmbyId: # real theme
        if not check_ThemeReady():
            FocusOld = ()
            return

        Item = json.loads(EmbyMetaData)
        PlaySessionId = str(uuid.uuid4()).replace("-", "")
        Path = os.path.join(utils.DownloadPath, "EMBY-themes", "")
        Container = Item.get('Container', 'ukn')
        ThemeFile = xbmcvfs.translatePath(f"{Path}{ServerId}_{Item['Id']}.{Container}") # Downloaded theme

        if xbmcvfs.exists(ThemeFile): # downloaded theme
            ThemeItem['KodiFullPath'] = ThemeFile

        ThemeLoading.update({"EmbyId": EmbyId, "MediaSourceId": Item['MediaSources'][0]['Id']})
        ThemeItem.update(Item)
        listitem.set_ListItem(ThemeItem, ServerId, "", 0.0, True)

        if PlayerId:
            ThemeItem['KodiType'] = "video"
        else:
            ThemeItem['KodiType'] = "song"
    elif (utils.theme_ThemeBySkipIntro or utils.theme_ThemeByContent) and not utils.useDirectPaths: # fake theme
        # Generate themes by skip intro markers
        KodiContentId = 0
        Runtime = 0

        if PlayKodiType in ("song", "album"):
            KodiDB = dbio.DBOpenRO("music", "Theme")
        else:
            KodiDB = dbio.DBOpenRO("video", "Theme")

        ContentKodiDatas = []

        if PlayKodiType == "tvshow":
            ContentKodiDatas = KodiDB.get_episodeid_path_runtime_by_tvshowid(PlayKodiId)
        elif PlayKodiType == "movie":
            ContentKodiDatas = KodiDB.get_path_runtime_by_movieid(PlayKodiId)
        elif PlayKodiType == "musicvideo":
            ContentKodiDatas = KodiDB.get_path_runtime_by_musicvideoid(PlayKodiId)
        elif PlayKodiType == "song":
            ContentKodiDatas = KodiDB.get_path_runtime_by_songid(PlayKodiId)
        elif PlayKodiType == "album":
            ContentKodiDatas = KodiDB.get_songid_path_runtime_by_albumid(PlayKodiId)
        else:
            ContentKodiDatas = []

        for ContentKodiData in ContentKodiDatas:
            if not ContentKodiData[2] or ContentKodiData[1].find("EMBY-offline-content") != -1: # Runtime not set, or downloaded content
                continue

            ContentPath = ContentKodiData[1].replace("http://127.0.0.1:57342", "").replace("dav://127.0.0.1:57342", "").replace("/emby_addon_mode", "").replace("|redirect-limit=1000&failonerror=false", "")
            KodiContentId = ContentKodiData[0]
            Runtime = round(float(ContentKodiData[2]))
            ThemeItem.update(metadata.load_MetaData(ContentPath, False, False))
            ThemeItem["Id"] = ThemeItem["EmbyId"]
            PositionStart = ThemeItem['MediaSources'][0][0]['IntroStartPositionTicks']
            PositionEnd = ThemeItem['MediaSources'][0][0]['IntroEndPositionTicks']
            ThemeLoading.update({"EmbyId": ThemeItem["Id"], "MediaSourceId": ThemeItem['MediaSources'][0][0]['Id']})

            if utils.theme_ThemeBySkipIntro and PositionStart and PositionEnd and Runtime > 180: # Minimum 180 seconds runtime
                StartTimeTicks = (PositionStart + 5) * 10000000 # 15 seconds start offset
                EndTimeTicks = (PositionEnd - 5) * 10000000 # 15 seconds end offset

                if EndTimeTicks - StartTimeTicks < 150000000: # Minimum 25 seconds intro
                    StartTimeTicks = 0
                    continue

                PlayerId, PlaySessionId = load_KodiItem(ThemeItem, KodiContentId, StartTimeTicks, KodiDB, PlayKodiType)
                break

        if not StartTimeTicks and utils.theme_ThemeByContent and KodiContentId and not utils.useDirectPaths:
            # Generate themes by content
            StartTimeTicks = 5000000 * Runtime # start in the middle of the content runtime
            EndTimeTicks = StartTimeTicks + utils.theme_ThemeByContentDuration * 10000000
            PlayerId, PlaySessionId = load_KodiItem(ThemeItem, KodiContentId, StartTimeTicks, KodiDB, PlayKodiType)

        if PlayKodiType in ("song", "album"):
            dbio.DBCloseRO("music", "Theme")
        else:
            dbio.DBCloseRO("video", "Theme")

        if ThemeItem and 'KodiMetadataDBID' in ThemeItem:
            embydb = dbio.DBOpenRO(ThemeItem["ServerId"], "Theme")
            _, EmbyType, _, _, _ = embydb.get_nativemode_data_by_KodiId_KodiType(int(ThemeItem['KodiMetadataDBID']), ThemeItem['KodiMetadataMediatype'])
            _, _, MediaSources = embydb.get_metadata_by_EmbyId_EmbyType(ThemeItem["EmbyId"], EmbyType)
            ThemeItem['MediaSources'] = MediaSources
            dbio.DBCloseRO(ThemeItem["ServerId"], "Theme")

            if ThemeItem['KodiMetadataPlaycount']:
                ThemeLoading["PlayCount"] = int(ThemeItem['KodiMetadataPlaycount'])
            else:
                ThemeLoading["PlayCount"] = 0

            if ThemeItem['KodiMetadataPlaybackPositionTicks']:
                ThemeLoading["PositionTicks"] = float(ThemeItem['KodiMetadataPlaybackPositionTicks'])
            else:
                ThemeLoading["PositionTicks"] = 0

            if ThemeItem['KodiMetadataLastplayed']:
                ThemeLoading["LastPlayed"] = ThemeItem['KodiMetadataLastplayed']
            else:
                ThemeLoading["LastPlayed"] = ""

    if 'ListItem' in ThemeItem and ThemeItem['ListItem']:
        VolumeOld = player.Volume

        if TerminateTheme:
            return

        ThemeLoading.update({"PlayerId": PlayerId, "KodiParentId": PlayKodiId, "KodiParentType": PlayKodiType, "KodiId": ThemeItem['KodiId'], "KodiType": ThemeItem['KodiType'], "ServerId": ThemeItem['ServerId'], "Runtime": Runtime})

        # Play Theme
        with utils.SafeLock(PlayerOpsBusy):
            if not check_ThemeReady():
                FocusOld = ()
                return

            if utils.theme_fade_in:
                VolumeFade = 0
                xbmc.executebuiltin("SetVolume(0)", False)
            else:
                VolumeFade = VolumeOld

            player.PlayItem = (ThemeLoading["KodiId"], ThemeLoading["KodiType"])

            if ThemeItem['MediaSources']:
                IndexMappingVideoEmby = ThemeItem['MediaSources'][0].get('IndexMappingVideoEmby', [])
                IndexMappingVideoKodi = ThemeItem['MediaSources'][0].get('IndexMappingVideoKodi', [])
                IndexMappingAudioEmby = ThemeItem['MediaSources'][0].get('IndexMappingAudioEmby', [])
                IndexMappingAudioKodi = ThemeItem['MediaSources'][0].get('IndexMappingAudioKodi', [])
                IndexMappingSubtitleEmby = ThemeItem['MediaSources'][0].get('IndexMappingSubtitleEmby', [])
                IndexMappingSubtitleKodi = ThemeItem['MediaSources'][0].get('IndexMappingSubtitleKodi', [])
            else:
                IndexMappingVideoEmby = []
                IndexMappingVideoKodi = []
                IndexMappingAudioEmby = []
                IndexMappingAudioKodi = []
                IndexMappingSubtitleEmby = []
                IndexMappingSubtitleKodi = []

            player.QueuedPlayingItem = {
                "EmbySessionData": {
                    "QueueableMediaTypes": ["Audio", "Video", "Photo"],
                    "CanSeek": True,
                    "IsPaused": False,
                    "ItemId": int(ThemeLoading["EmbyId"]),
                    "MediaSourceId": ThemeLoading["MediaSourceId"],
                    "PlaySessionId": PlaySessionId,
                    "PositionTicks": StartTimeTicks,
                    "RunTimeTicks": Runtime * 10000000,
                    "VolumeLevel": player.Volume,
                    "PlaybackRate": playerops.PlaybackRate[PlayerId],
                    "Shuffle": playerops.Shuffled[PlayerId],
                    "RepeatMode": playerops.RepeatMode[PlayerId],
                    "IsMuted": player.Muted
                },
                "IntroStartPositionTicks": 0,
                "IntroEndPositionTicks": 0,
                "CreditsPositionTicks": 0,
                "EmbyServer": utils.EmbyServers[ThemeItem["ServerId"]],
                "KodiType": ThemeItem['KodiType'],
                "Filename": ThemeItem['KodiFullPath'],
                "IndexMappingVideoEmby": IndexMappingVideoEmby,
                "IndexMappingVideoKodi": IndexMappingVideoKodi,
                "IndexMappingAudioEmby": IndexMappingAudioEmby,
                "IndexMappingAudioKodi": IndexMappingAudioKodi,
                "IndexMappingSubtitleEmby": IndexMappingSubtitleEmby,
                "IndexMappingSubtitleKodi": IndexMappingSubtitleKodi,
                "SubtitleEnabled": False,
                "SubtitleIndexKodi": 0
            }
            player.load_queuePlayingItem()

            with utils.SafeLock(ThemeUpdate):
                player.VideoPlayback = "THEMEINIT"
                player.Theme = copy.Object(ThemeLoading)

            if not playerops.Play(False, ThemeItem['KodiFullPath'], ThemeItem['ListItem'], True, True):
                player.VideoPlayback = "READY"
                xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)

                if player.PlayItem == (ThemeLoading["KodiId"], ThemeLoading["KodiType"]):
                    player.PlayItem = (0, "")

                clear_theme(False)
                FocusOld = ()
                return

            Abort = False

            with utils.SafeLock(player.PlayerLock):
                if player.PlayItem != (ThemeLoading["KodiId"], ThemeLoading["KodiType"]) or player.VideoPlayback != "THEMEINIT":
                    Abort = True
                else:
                    player.VideoPlayback = "THEME"
                    player.Theme["EndTimeTicks"] = EndTimeTicks

            if Abort:
                xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
                clear_theme(True)
                FocusOld = ()
                return

            restore_progress()

        del ThemeItem

        # Fade volume
        if utils.theme_fade_in:
            while VolumeFade != VolumeOld:
                if TerminateTheme:
                    VolumeFadeInInterrupt = VolumeOld
                    break

                VolumeFade += 1
                xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

                if not check_ThemePlaying() or utils.sleep(utils.theme_fade_in):
                    xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
                    VolumeFade = VolumeOld
                    clear_theme(True)
                    break

            if VolumeFade == VolumeOld:
                VolumeFadeInInterrupt = -1

            player.Volume = VolumeOld

def get_FocusKey():
    ControlId = xbmc.getInfoLabel("System.CurrentControlID")

    if ControlId.isdigit():
        Folder = xbmc.getInfoLabel(f"Container({ControlId}).FolderPath")
        CurrentItem = xbmc.getInfoLabel(f"Container({ControlId}).CurrentItem")
    else:
        Folder = ""
        CurrentItem = ""

    return xbmc.getInfoLabel("System.CurrentWindow"), ControlId, CurrentItem, Folder

def reset_Focus():
    global FocusOld
    global FocusPending
    global FocusPendingKodiType
    global FocusPendingKodiId
    FocusOld = ()
    FocusPending = ()
    FocusPendingKodiType = -1
    FocusPendingKodiId = -1

def PlaybackStop():
    global VolumeFade
    global VolumeFadeInInterrupt

    # No theme played or theme already ended
    if not player.Theme["KodiId"] or not player.PlayItem[0]:
        if VolumeFadeInInterrupt != -1:
            VolumeOld = VolumeFadeInInterrupt
            xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
            VolumeFade = VolumeOld
            player.Volume = VolumeOld
            VolumeFadeInInterrupt = -1

        if player.Theme["KodiId"]:
            clear_theme(True)

        return True

    EndTimeTicksBackup = player.Theme["EndTimeTicks"]
    player.Theme["EndTimeTicks"] = 0

    if VolumeFadeInInterrupt == -1:
        VolumeOld = player.Volume

        if utils.theme_fade_out:
            VolumeFade = VolumeOld
    else:
        VolumeOld = VolumeFadeInInterrupt

    if utils.theme_fade_out:
        while VolumeFade:
            VolumeFade -= 1
            xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

            if not check_ThemePlaying() or utils.sleep(utils.theme_fade_out):
                xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
                player.Volume = VolumeOld
                VolumeFade = VolumeOld
                VolumeFadeInInterrupt = -1
                clear_theme(True)
                return False

            if TerminateTheme:
                player.Volume = VolumeOld
                VolumeFadeInInterrupt = VolumeOld
                player.Theme["EndTimeTicks"] = EndTimeTicksBackup
                return False

    playerops.Stop(False, True)
    playerops.wait_Stopped()
    clear_theme(True)

    if utils.theme_fade_out:
        utils.sleep(0.5) # Kodi needs time until playback actually stopped, monitor notifications are not accurate
        xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
    elif VolumeFadeInInterrupt != -1:
        xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)

    VolumeFade = VolumeOld
    player.Volume = VolumeOld
    VolumeFadeInInterrupt = -1
    return True

def restore_Volume():
    global VolumeFadeInInterrupt
    global VolumeFade

    if VolumeFadeInInterrupt == -1:
        if not utils.theme_fade_in:
            return

        VolumeOld = player.Volume
        VolumeFade = VolumeOld
    else:
        VolumeOld = VolumeFadeInInterrupt

        if not utils.theme_fade_in:
            xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
            VolumeFade = VolumeOld
            player.Volume = VolumeOld
            VolumeFadeInInterrupt = -1
            return

    while VolumeFade != VolumeOld:
        if TerminateRestore:
            VolumeFadeInInterrupt = VolumeOld
            break

        if VolumeFade < VolumeOld:
            VolumeFade += 1
        else:
            VolumeFade -= 1

        xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

        if not check_ThemePlaying() or utils.sleep(utils.theme_fade_in):
            xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
            VolumeFade = VolumeOld
            break

    if VolumeFade == VolumeOld:
        VolumeFadeInInterrupt = -1

    player.Volume = VolumeOld

def check_ThemePlaying():
    if not player.PlayItem[0] or player.PlayItem[0] != player.Theme["KodiId"] or player.PlayItem[1] != player.Theme["KodiType"] or player.VideoPlayback not in ("THEME", "THEMEINIT") or player.Trailers:
        return False

    return True

def check_ThemeReady():
    if player.PlayItem[0] and (player.PlayItem[0] != player.Theme["KodiId"] or player.PlayItem[1] != player.Theme["KodiType"]) or player.VideoPlayback not in ("READY", "THEME", "THEMEINIT") or player.Trailers or utils.RemoteMode:
        return False # Playing content

    return True # Idle or theme playing

def ignore_views():
    if xbmc.getCondVisibility('Window.IsActive(12005)') or xbmc.getCondVisibility('Window.IsActive(12006)') or xbmc.getCondVisibility('Window.IsActive(10142)') or xbmc.getCondVisibility("Window.IsActive(10138)") or xbmc.getCondVisibility("Window.IsActive(10160)"): # skip fullscreenvideo, visualisation, fullscreeninfo, busydialogOpen, busydialognocancelOpen
        return True

    return False

def get_KodiIds():
    KodiTypeLocal = xbmc.getInfoLabel('ListItem.DBTYPE')

    if KodiTypeLocal:
        KodiTypeReal = KodiTypeLocal

        if KodiTypeLocal in ("episode", "season"):
            KodiIdLocal = xbmc.getInfoLabel('ListItem.TVShowDBID')

            if not KodiIdLocal:
                KodiIdLocal = xbmc.getInfoLabel('ListItem.Property(TVShowDBID)')

            KodiTypeLocal = "tvshow"
        else:
            KodiIdLocal = xbmc.getInfoLabel('ListItem.DBID')

        if KodiIdLocal and KodiIdLocal.isdigit():
            KodiIdLocal = int(KodiIdLocal)
        else:
            KodiIdLocal = 0

        return KodiTypeLocal, KodiIdLocal, KodiTypeReal

    return "", 0, ""

def download():
    utils.close_dialog(10146) # addoninformation
    DownloadAudioThemes = False
    DownloadVideoThemes = False
    Path = os.path.join(utils.DownloadPath, "EMBY-themes", "")
    utils.mkDir(Path)
    DownloadAudioThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33758), yeslabel=utils.Translate(33760), nolabel=utils.Translate(33761), defaultbutton=11) # defaultbutton=11 = yes
    DownloadVideoThemes = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33759), yeslabel=utils.Translate(33760), nolabel=utils.Translate(33761), defaultbutton=10) # defaultbutton=10 = no

    if not DownloadAudioThemes and not DownloadVideoThemes:
        return

    utils.create_ProgressBar("ThemesDownload", utils.Translate(33199), utils.Translate(33451))

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        Themes = []
        EmbyDB = dbio.DBOpenRO(ServerId, "ThemesDownload")

        if DownloadAudioThemes:
            Themes += EmbyDB.get_ThemeAudio()

        if DownloadVideoThemes:
            Themes += EmbyDB.get_ThemeVideo()

        dbio.DBCloseRO(ServerId, "ThemesDownload")
        TotalItems = len(Themes) / 100

        for Index, Trailer in enumerate(Themes):
            Item = json.loads(Trailer[1])
            utils.update_ProgressBar("ThemesDownload", Index / TotalItems, utils.Translate(33451), str(Trailer))
            FilePath = xbmcvfs.translatePath(f"{Path}{ServerId}_{Trailer[0]}.{Item.get('Container', 'ukn')}")

            if not xbmcvfs.exists(FilePath):
                FileName = f"{ServerId}_{Trailer[0]}.{Item.get('Container', 'ukn')}"
                PathDownload = xbmcvfs.translatePath(Path)

                if 'Size' not in Item or not Item['Size']:
                    if utils.DebugLog: xbmc.log(f"EMBY.monitor.themes: Theme has no filesize: {Item}", 3) # LOGERROR
                    continue

                EmbyServer.API.download_file(Trailer[0], PathDownload, Item['Size'], Item['Id'], "", "", "", "", FileName)
            else:
                if utils.DebugLog: xbmc.log(f"EMBY.monitor.themes: Theme exists: {FilePath}", 1) # LOGDEBUG

    utils.close_ProgressBar("ThemesDownload")
    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33153), icon=utils.icon, time=utils.displayMessage, sound=False)

def PositionTracker():
    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: --->[ position tracker ]", 1) # LOGDEBUG

    while not utils.SystemShutdown:
        if utils.sleep(1):
            break

        if not player.Theme["EndTimeTicks"] or player.VideoPlayback not in ("THEME", "THEMEINIT"):
            continue

        Position = playerops.PlayBackPosition()
        if utils.DebugLog: xbmc.log(f"EMBY.monitor.themes: PositionTracker: Position: {Position} / ThemeEndPosition: {player.Theme['EndTimeTicks']}", 1) # LOGDEBUG

        if Position > player.Theme["EndTimeTicks"]:
            ThemeQueue.put({"Type": "STOP", "Theme": player.Theme})

    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ position tracker ]", 1) # LOGDEBUG

def clear_theme(RestoreProgress):
    with utils.SafeLock(ThemeUpdate):
        if player.Theme["PlayerId"] == -1:
            return

        if RestoreProgress:
            restore_progress()

        player.Theme = {"PlayerId": -1, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": "", "Runtime": 0}

def monitor_Themes():
    if utils.DebugLog: xbmc.log("EMBY.hooks.themes: THREAD: --->[ Monitor themes ]", 1) # LOGDEBUG
    global TerminateRestore
    global TerminateTheme
    global FocusOld
    global FocusPending
    global FocusPendingKodiType
    global FocusPendingKodiId
    utils.start_thread(ThemePlay, ())
    utils.start_thread(PositionTracker, ())

    while True:
        # check if themes enabled
        if utils.DebugLog: xbmc.log("EMBY.hooks.theme (DEBUG): CONDITION: --->[ SettingsChangedCondition ]", 1) # LOGDEBUG

        with utils.SafeLock(utils.SettingsChangedCondition):
            while not utils.theme_enable_audio and not utils.theme_enable_video:
                utils.SettingsChangedCondition.wait(timeout=0.1)

                if utils.SystemShutdown:
                    ThemeQueue.put("QUIT")

                    if utils.DebugLog:
                        xbmc.log("EMBY.monitor.themes (DEBUG): THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                        xbmc.log("EMBY.hooks.theme (DEBUG): CONDITION: ---<[ SettingsChangedCondition ]", 1) # LOGDEBUG

                    return

        if utils.DebugLog: xbmc.log("EMBY.hooks.theme (DEBUG): CONDITION: ---<[ SettingsChangedCondition ]", 1) # LOGDEBUG

        with utils.SafeLock(PlayerOpsBusy):
            # Content playback stopped
            if not player.PlayItem[0] and player.Theme["KodiId"]:
                reset_Focus()
                clear_theme(True)

            ThemeReady = check_ThemeReady()

            if not ThemeReady:
                if player.Theme["KodiId"]:
                    clear_theme(True)

                reset_Focus()

        if not ThemeReady:
            if utils.sleep(3):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes (DEBUG): THREAD: ---<[ Monitor themes ] quit 1", 1)
                return

            continue

        if ignore_views():
            reset_Focus()

            if utils.sleep(1):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes (DEBUG): THREAD: ---<[ Monitor themes ] quit 2", 1) # LOGDEBUG
                return

            continue

        KodiTypeCompare, KodiIdCompare, KodiTypeReal = get_KodiIds()

        # Ignore navigation views
        if not utils.theme_enable_homescreen and xbmc.getCondVisibility('Window.IsActive(10000)'):
            reset_Focus()
            ThemeQueue.put("STOP")

            if utils.sleep(1):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes (DEBUG): THREAD: ---<[ Monitor themes ] quit 3", 1) # LOGDEBUG
                return

            continue

        WindowNav = -1

        if not utils.theme_enable_viewseries and KodiTypeReal == "tvshow":
            WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ] quit 4", 1) # LOGDEBUG
                    return

                reset_Focus()
                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewseason and KodiTypeReal == "season":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ] quit 5", 1) # LOGDEBUG
                    return

                reset_Focus()
                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewepisode and KodiTypeReal == "episode":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ] quit 6", 1) # LOGDEBUG
                    return

                reset_Focus()
                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewmovie and KodiTypeReal == "movie":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ] quit 7", 1) # LOGDEBUG
                    return

                reset_Focus()
                ThemeQueue.put("STOP")
                continue

        # Wait for navigation end
        FocusCompare = get_FocusKey()
        KodiTypeCompare, KodiIdCompare, KodiTypeReal = get_KodiIds()

        if FocusPending != FocusCompare:
            FocusPending = FocusCompare
            FocusPendingKodiType = KodiTypeCompare
            FocusPendingKodiId = KodiIdCompare

        ThemePlayThreadDelay = 0

        while ThemePlayThreadDelay < 10:
            if utils.sleep(utils.theme_delay):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ] quit 8", 1)
                return

            if ignore_views():
                reset_Focus()
                break

            FocusCurrent = get_FocusKey()

            if FocusCurrent != FocusCompare:
                FocusCompare = FocusCurrent
                KodiTypeCompare, KodiIdCompare, KodiTypeReal = get_KodiIds()

                if FocusPending != FocusCompare:
                    FocusPending = FocusCompare
                    FocusPendingKodiType = KodiTypeCompare
                    FocusPendingKodiId = KodiIdCompare

                ThemePlayThreadDelay = 0
            else:
                ThemePlayThreadDelay += 1

        with utils.SafeLock(PlayerOpsBusy):
            if not check_ThemeReady():
                reset_Focus()
                continue

            if not FocusPending or FocusPending == FocusOld:
                FocusPending = ()
                FocusPendingKodiType = -1
                FocusPendingKodiId = -1
                continue

            FocusCompare = FocusPending
            KodiTypeCompare = FocusPendingKodiType
            KodiIdCompare = FocusPendingKodiId
            FocusOld = FocusCompare
            FocusPending = ()
            FocusPendingKodiType = -1
            FocusPendingKodiId = -1

            # Terminate previous processes
            if RestoreBusy.locked():
                TerminateRestore = True

            if ThemeBusy.locked():
                TerminateTheme = True

            # Run commands
            if player.Theme["KodiId"] and KodiIdCompare == player.Theme["KodiParentId"] and KodiTypeCompare == player.Theme["KodiParentType"]:
                ThemeQueue.put("FADE")
            else:
                if not KodiIdCompare:
                    reset_Focus()
                    ThemeQueue.put("STOP")
                elif player.Theme["KodiId"] != KodiIdCompare or player.Theme["KodiType"] != KodiTypeCompare:
                    ThemeQueue.put(((KodiTypeCompare, KodiIdCompare),))

            continue

def restore_progress():
    if "PlayCount" not in player.Theme:
        return

    if player.Theme["Runtime"]:
        EmbyLastPlayed = utils.convert_to_gmt(player.Theme['LastPlayed'])
        EmbyPosition = int(player.Theme['PositionTicks'] * 10000000)
        EmbyServer = utils.EmbyServers.get(player.Theme.get('ServerId'))

        if EmbyServer:
            EmbyServer.API.set_progress_upsync(player.Theme["EmbyId"], EmbyPosition, player.Theme["PlayCount"], EmbyLastPlayed)

def load_KodiItem(ThemeItem, KodiContentId, StartTimeTicks, KodiDB, PlayKodiType):
    PlaySessionId = str(uuid.uuid4()).replace("-", "")
    StartTimeTicks = StartTimeTicks / 10000000

    if PlayKodiType == "tvshow":
        ThemeItem.update(KodiDB.get_episode_metadata_for_listitem(KodiContentId, ""))
        ThemeItem['KodiType'] = "episode"
        PlayerId = 1
    elif PlayKodiType == "movie":
        ThemeItem.update(KodiDB.get_movie_metadata_for_listitem(KodiContentId, ""))
        ThemeItem['KodiType'] = "movie"
        PlayerId = 1
    elif PlayKodiType == "musicvideo":
        ThemeItem.update(KodiDB.get_musicvideos_metadata_for_listitem(KodiContentId, ""))
        ThemeItem['KodiType'] = "musicvideo"
        PlayerId = 1
    elif PlayKodiType in ("song", "album"):
        ThemeItem.update(KodiDB.get_song_metadata_for_listitem(KodiContentId))
        ThemeItem['KodiType'] = "song"
        PlayerId = 0
    else:
        return -1, ""

    listitem.set_ListItem_from_Kodi_database(ThemeItem, "", StartTimeTicks, True)
    return PlayerId, PlaySessionId

import os
import threading
import json
import uuid
import xbmc
import xbmcvfs
from helper import utils, player, queue, playerops
from emby import listitem, metadata
from database import dbio
VolumeFade = player.Volume
VolumeFadeInInterrupt = -1
ThemeQueue = queue.Queue()
RestoreBusy = threading.Lock()
ThemeBusy = threading.Lock()
TerminateTheme = False
TerminateRestore = False
Theme = {"PlayerId": 0, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": ""}
PlayerOpsBusy = False
KodiTypeOld = ""
KodiType = ""
KodiIdOld = 0
KodiId = 0

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
                if PlaybackStop():
                    if ThemeReceived[0] and ThemeReceived[1]:
                        PlaybackStart(ThemeReceived[0], ThemeReceived[1])

                TerminateTheme = False

def PlaybackStart(PlayKodiType, PlayKodiId):
    if PlayKodiType not in ("movie", "tvshow"):
        return

    global Theme
    global VolumeFade
    global VolumeFadeInInterrupt
    global KodiTypeOld
    global KodiType
    global KodiIdOld
    global KodiId
    global PlayerOpsBusy
    ThemeLoading = {"PlayerId": 0, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": ""}
    QueuedPlayingItem = []
    EmbyId = ""
    ListItem = None
    ServerId = ""
    EmbyServer = None
    PositionStart = 0
    PositionEnd = 0
    EndTimeTicks = 0
    ThemeFile = ""
    StartTimeTicks = 0
    KodiItem = {}

    EmbyType = utils.KodiTypeMapping[PlayKodiType]

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
        EmbyDB = dbio.DBOpenRO(ServerId, "Theme")

        if utils.theme_enable_audio and utils.theme_enable_video: # Both
            if utils.theme_priority == "audio":
                EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)
                PlayerId = 0

                if not EmbyId:
                    EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)
                    PlayerId = 1
            else:
                EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)
                PlayerId = 1

                if not EmbyId:
                    EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)
                    PlayerId = 0
        elif utils.theme_enable_audio: # Audio only
            EmbyId, EmbyMetaData = EmbyDB.get_ThemeAudio_by_KodiId_EmbyType(PlayKodiId, EmbyType)
            PlayerId = 0
        else: # Video only
            EmbyId, EmbyMetaData = EmbyDB.get_ThemeVideo_by_KodiId_EmbyType(PlayKodiId, EmbyType)
            PlayerId = 1

        dbio.DBCloseRO(ServerId, "Theme")

        if EmbyId:
            break

    del EmbyDB

    if EmbyId: # real theme
        if player.PlayItem[0] and (player.PlayItem[0] != Theme["KodiId"] or player.PlayItem[1] != Theme["KodiType"]) or player.VideoPlayback not in ("READY", "THEME") or player.Trailers:
            return

        Item = json.loads(EmbyMetaData)
        MediaSourceId = Item['MediaSources'][0]['Id']
        PlaySessionId = str(uuid.uuid4()).replace("-", "")
        Path = os.path.join(utils.DownloadPath, "EMBY-themes", "")
        Container = Item.get('Container', 'ukn')
        ThemeFile = xbmcvfs.translatePath(f"{Path}{ServerId}_{Item['Id']}.{Container}") # Downloaded theme

        if not xbmcvfs.exists(ThemeFile): # remote theme
            ThemeFile = f"{EmbyServer.ServerData['ServerUrl']}/emby/videos/{EmbyId}/stream.{Container}?static=true&MediaSourceId={MediaSourceId}&PlaySessionId={PlaySessionId}&DeviceId={EmbyServer.ServerData['DeviceId']}&api_key={EmbyServer.ServerData['AccessToken']}&stream.{Container}|seekable=0&failonerror=false&verifypeer=false" # seekable=0 must be set -> Kodi uses playerid -1 and not touching playlists

        QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(EmbyId), 'MediaSourceId': MediaSourceId, 'PlaySessionId': PlaySessionId, 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'PlaybackRate': 1, 'Shuffle': False, 'RepeatMode': "RepeatNone", 'IsMuted': False}, None, None, None, EmbyServer, PlayerId, "", ""]
        ListItem = listitem.set_ListItem(Item, ServerId, "", False)
        ListItem.setPath(ThemeFile)
        KodiId = Item['KodiId']
    elif (utils.theme_ThemeBySkipIntro != "off" or utils.theme_ThemeByContent != "off") and not utils.useDirectPaths: # fake theme
        # Generate themes by skip intro markers
        isSkipIntro = False
        KodiContentId = 0
        Runtime = 0
        VideoDB = dbio.DBOpenRO("video", "Theme")
        ContentKodiDatas = []

        if PlayKodiType == "tvshow":
            ContentKodiDatas = VideoDB.get_episodeid_path_runtime_by_tvshowid(PlayKodiId)
        else:
            ContentKodiDatas = VideoDB.get_path_runtime_by_movieid(PlayKodiId)

        for ContentKodiData in ContentKodiDatas:
            if not ContentKodiData[2] or ContentKodiData[1].find("EMBY-offline-content") != -1: # Runtime not set, or downloaded content
                continue

            ContentPath = ContentKodiData[1].replace("http://127.0.0.1:57342", "").replace("dav://127.0.0.1:57342", "").replace("/emby_addon_mode", "").replace("|redirect-limit=1000&failonerror=false", "")
            KodiContentId = ContentKodiData[0]
            Runtime = round(float(ContentKodiData[2]))
            ContentMetadata = metadata.load_MetaData(ContentPath, False, False)
            PositionStart = ContentMetadata['MediaSources'][0][0]['IntroStartPositionTicks']
            PositionEnd = ContentMetadata['MediaSources'][0][0]['IntroEndPositionTicks']

            if PositionStart and PositionEnd and Runtime > 180: # Minimum 180 seconds runtime
                StartTimeTicks = (PositionStart + 15) * 10000000 # 15 seconds start offset
                EndTimeTicks = PositionEnd * 10000000 - StartTimeTicks

                if EndTimeTicks < 150000000: # Minimum 15 seconds intro
                    StartTimeTicks = 0
                    continue

                isSkipIntro = True
                KodiItem, KodiId, ThemeFile, PlayerId, MediaSourceId, PlaySessionId, ThemeLoading["EmbyId"], ThemeLoading["MediaSourceId"] = load_KodiItem(KodiContentId, ContentPath, ContentMetadata, StartTimeTicks, utils.theme_ThemeBySkipIntro, VideoDB, PlayKodiType)
                break

        if not StartTimeTicks and utils.theme_ThemeByContent and KodiContentId and not utils.useDirectPaths:
            # Generate themes by content
            ThemeFile = ""
            StartTimeTicks = 5000000 * Runtime # start in the middle of the content runtime
            EndTimeTicks = StartTimeTicks + utils.theme_ThemeByContentDuration * 10000000
            KodiItem, KodiId, ThemeFile, PlayerId, MediaSourceId, PlaySessionId, ThemeLoading["EmbyId"], ThemeLoading["MediaSourceId"] = load_KodiItem(KodiContentId, ContentPath, ContentMetadata, StartTimeTicks, utils.theme_ThemeByContent, VideoDB, PlayKodiType)

        if KodiItem:
            if isSkipIntro:
                if utils.theme_ThemeBySkipIntro == "video": # Video
                    KodiItem['mediatype'] = "video"
                else:
                    KodiItem['mediatype'] = "song"
            else:
                if utils.theme_ThemeByContent == "video": # Video
                    KodiItem['mediatype'] = "video"
                else:
                    KodiItem['mediatype'] = "song"

            _, ListItem = listitem.set_ListItem_from_Kodi_database(KodiItem, ThemeFile, False)
            QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(ContentMetadata['EmbyId']), 'MediaSourceId': MediaSourceId, 'PlaySessionId': PlaySessionId, 'PositionTicks': StartTimeTicks, 'RunTimeTicks': Runtime * 10000000, 'VolumeLevel': player.Volume, 'PlaybackRate': 1, 'Shuffle': False, 'RepeatMode': "RepeatNone", 'IsMuted': False}, None, None, None, utils.EmbyServers[ContentMetadata['ServerId']], PlayerId, "", ""]
            ThemeLoading["ServerId"] = ContentMetadata['ServerId']

            if KodiItem['playcount']:
                ThemeLoading["PlayCount"] = int(KodiItem['playcount'])
            else:
                ThemeLoading["PlayCount"] = 0

            if KodiItem['KodiPlaybackPositionTicks']:
                ThemeLoading["PositionTicks"] = int(KodiItem['KodiPlaybackPositionTicks']) * 10000000
            else:
                ThemeLoading["PositionTicks"] = 0

            if KodiItem['lastplayed']:
                ThemeLoading["LastPlayed"] = KodiItem['lastplayed']
            else:
                ThemeLoading["LastPlayed"] = ""

        dbio.DBCloseRO("video", "Theme")

    if ListItem:
        VolumeFade = 0
        VolumeOld = player.Volume

        if TerminateTheme:
            return

        ThemeLoading.update({"PlayerId": PlayerId, "KodiParentId": PlayKodiId, "KodiParentType": PlayKodiType, "KodiId": KodiId})

        if PlayerId:
            ThemeLoading["KodiType"] = "video"
        else:
            ThemeLoading["KodiType"] = "song"

        if player.PlayItem[0] and (player.PlayItem[0] != Theme["KodiId"] or player.PlayItem[1] != Theme["KodiType"]) or player.VideoPlayback not in ("READY", "THEME") or player.Trailers:
            return

        if utils.theme_fade_in:
            xbmc.executebuiltin("SetVolume(0)", False)

        player.VideoPlayback = "THEME"
        player.PlayItem = (ThemeLoading["KodiId"], ThemeLoading["KodiType"])
        Theme = ThemeLoading

        if QueuedPlayingItem:
            player.QueuedPlayingItem = QueuedPlayingItem

        PlayerOpsBusy = True

        if not playerops.Play(False, ThemeFile, ListItem, True, True):
            del ListItem
            xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)

            if player.PlayItem == (ThemeLoading["KodiId"], ThemeLoading["KodiType"]):
                player.PlayItem = (0, "")

            clear_theme()
            PlayerOpsBusy = False
            return

        del ListItem

        # Wait for widget refresh
        utils.sleep(0.5)
        KodiType, KodiId, _ = get_KodiIds()
        KodiTypeOld = KodiType
        KodiIdOld = KodiId
        PlayerOpsBusy = False

        # Fade volume
        if utils.theme_fade_in:
            ThemeLoading["EndTimeTicks"] = EndTimeTicks
            Theme = ThemeLoading

            while VolumeFade != VolumeOld:
                if TerminateTheme:
                    VolumeFadeInInterrupt = VolumeOld
                    break

                VolumeFade += 1
                xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

                if not check_ThemePlaying() or utils.sleep(utils.theme_fade_in):
                    xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)

                    if "PlayCount" in Theme:
                        utils.EmbyServers[Theme['ServerId']].API.set_progress_upsync(Theme["EmbyId"], Theme['PositionTicks'], Theme["PlayCount"], Theme["LastPlayed"])

                    clear_theme()
                    break

            VolumeFadeInInterrupt = -1
            player.Volume = VolumeOld
        else:
            ThemeLoading["EndTimeTicks"] = EndTimeTicks
            Theme = ThemeLoading

def PlaybackStop():
    global Theme
    global VolumeFade
    Theme["EndTimeTicks"] = 0

    # No theme played
    if not Theme["KodiId"] or not player.PlayItem[0]:
        return True

    ThemeLocal = Theme

    if utils.theme_fade_out:
        if VolumeFadeInInterrupt == -1:
            VolumeOld = player.Volume
        else:
            VolumeOld = VolumeFadeInInterrupt

        while VolumeFade:
            VolumeFade -= 1
            xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

            if not check_ThemePlaying() or utils.sleep(utils.theme_fade_out):
                xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
                player.Volume = VolumeOld
                return False

            if TerminateTheme:
                player.Volume = VolumeOld
                Theme = ThemeLocal
                return False

    player.PlayItem = (0, "")
    playerops.Stop(False, True)

    if "PlayCount" in ThemeLocal:
        playerops.wait_Stopped()
        utils.EmbyServers[ThemeLocal['ServerId']].API.set_progress_upsync(ThemeLocal["EmbyId"], ThemeLocal['PositionTicks'], ThemeLocal["PlayCount"], ThemeLocal["LastPlayed"])

    clear_theme()

    if utils.theme_fade_out:
        utils.sleep(0.5) # Kodi needs time until playback actually stopped, monitor notification are not accurate
        xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
        player.Volume = VolumeOld

    return True

def restore_Volume():
    global VolumeFadeInInterrupt
    global VolumeFade

    if utils.theme_fade_in:
        VolumeOld = player.Volume

        while VolumeFade != VolumeOld:
            if TerminateRestore:
                VolumeFadeInInterrupt = VolumeOld
                break

            VolumeFade += 1
            xbmc.executebuiltin(f"SetVolume({VolumeFade})", False)

            if not check_ThemePlaying() or utils.sleep(utils.theme_fade_in):
                xbmc.executebuiltin(f"SetVolume({VolumeOld})", False)
                break

        VolumeFadeInInterrupt = -1
        player.Volume = VolumeOld

def check_ThemePlaying():
    if not player.PlayItem[0] or player.PlayItem[0] != Theme["KodiId"] or player.PlayItem[1] != Theme["KodiType"]:
        return False

    return True

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
    Themes = []

    for ServerId, EmbyServer in list(utils.EmbyServers.items()):
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

        if not Theme["EndTimeTicks"]:
            continue

        Position = playerops.PlayBackPosition()
        if utils.DebugLog: xbmc.log(f"EMBY.monitor.themes: PositionTracker: Position: {Position} / ThemeEndPosition: {Theme['EndTimeTicks']}", 1) # LOGDEBUG

        if Position > Theme["EndTimeTicks"]:
            ThemeQueue.put("STOP")

    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ position tracker ]", 1) # LOGDEBUG


def clear_theme():
    global Theme
    Theme = {"PlayerId": 0, "KodiParentId": 0, "KodiParentType": "", "KodiId": 0, "KodiType": "", "EndTimeTicks": 0, "EmbyId": 0, "MediaSourceId": ""}

    # Wait for widget refresh
    global KodiTypeOld
    global KodiType
    global KodiIdOld
    global KodiId
    utils.sleep(0.5)
    KodiType, KodiId, _ = get_KodiIds()
    KodiTypeOld = KodiType
    KodiIdOld = KodiId

def monitor_Themes():
    if utils.DebugLog: xbmc.log("EMBY.hooks.themes: THREAD: --->[ Monitor themes ]", 1) # LOGDEBUG
    global TerminateRestore
    global TerminateTheme
    global KodiTypeOld
    global KodiType
    global KodiIdOld
    global KodiId
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

        if not player.PlayItem[0]:
            if Theme["KodiId"]:
                if "PlayCount" in Theme:
                    utils.EmbyServers[Theme['ServerId']].API.set_progress_upsync(Theme["EmbyId"], Theme['PositionTicks'], Theme["PlayCount"], Theme["LastPlayed"])

                clear_theme()

        if utils.RemoteMode or (player.PlayItem[0] and (player.PlayItem[0] != Theme["KodiId"] or player.PlayItem[1] != Theme["KodiType"]) or player.VideoPlayback not in ("READY", "THEME") or player.Trailers):
            if Theme["KodiId"]:
                if "PlayCount" in Theme:
                    utils.EmbyServers[Theme['ServerId']].API.set_progress_upsync(Theme["EmbyId"], Theme['PositionTicks'], Theme["PlayCount"], Theme["LastPlayed"])

                clear_theme()
                KodiIdOld = ""
                KodiTypeOld = ""

            if utils.sleep(3):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes (DEBUG): THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                return

            continue

        if ignore_views():
            continue

        KodiTypeCompare, KodiIdCompare, KodiTypeReal = get_KodiIds()

        # Ignore navigation views
        if not utils.theme_enable_homescreen and xbmc.getCondVisibility('Window.IsActive(10000)'):
            ThemeQueue.put("STOP")
            continue

        WindowNav = -1

        if not utils.theme_enable_viewseries and KodiTypeReal == "tvshow":
            WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                    return

                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewseason and KodiTypeReal == "season":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                    return

                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewepisode and KodiTypeReal == "episode":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                    return

                ThemeQueue.put("STOP")
                continue

        if not utils.theme_enable_viewmovie and KodiTypeReal == "movie":
            if WindowNav == -1:
                WindowNav = xbmc.getCondVisibility('Window.IsActive(10025)')

            if WindowNav:
                if utils.sleep(utils.theme_delay * 10):
                    ThemeQueue.put("QUIT")
                    if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                    return

                ThemeQueue.put("STOP")
                continue

        # Wait for navigation end
        ThemePlayThreadDelay = 0

        while ThemePlayThreadDelay < 10:
            ThemePlayThreadDelay += 1

            if utils.sleep(utils.theme_delay):
                ThemeQueue.put("QUIT")
                if utils.DebugLog: xbmc.log("EMBY.monitor.themes: THREAD: ---<[ Monitor themes ]", 1) # LOGDEBUG
                return

            if ignore_views():
                continue

            KodiType, KodiId, _ = get_KodiIds()

            if KodiTypeCompare != KodiType or KodiIdCompare != KodiId:
                break
        else: # no break triggered
            if PlayerOpsBusy:
                continue

            # Check if item has changed
            if KodiIdOld != KodiId or KodiTypeOld != KodiType:
                KodiIdOld = KodiId
                KodiTypeOld = KodiType

                # Terminate previous processes
                if RestoreBusy.locked():
                    TerminateRestore = True

                if ThemeBusy.locked():
                    TerminateTheme = True

                # Run commands
                if Theme["KodiId"] and KodiId == Theme["KodiParentId"] and KodiType == Theme["KodiParentType"]:
                    ThemeQueue.put("FADE")
                else:
                    if not KodiId:
                        ThemeQueue.put("STOP")
                    elif Theme["KodiId"] != KodiId and Theme["KodiType"] != KodiType:
                        ThemeQueue.put(((KodiType, KodiId),))

                continue

def load_KodiItem(KodiContentId, ContentPath, ContentMetadata, StartTimeTicks, ThemeBy, VideoDB, PlayKodiType):
    MediaSourceId = ContentMetadata['MediaSources'][0][0]['Id']
    PlaySessionId = str(uuid.uuid4()).replace("-", "")

    if ContentMetadata['ServerId'] in utils.EmbyServers:
        if PlayKodiType == "tvshow":
            KodiItem = VideoDB.get_episode_metadata_for_listitem(KodiContentId, ContentPath)
        else:
            KodiItem = VideoDB.get_movie_metadata_for_listitem(KodiContentId, ContentPath)

        if ThemeBy == "video": # Video
            PlayerId = 1
            ThemeFile = f"{utils.EmbyServers[ContentMetadata['ServerId']].ServerData['ServerUrl']}/emby/videos/{ContentMetadata['EmbyId']}/stream.ts?MediaSourceId={MediaSourceId}&PlaySessionId={PlaySessionId}&DeviceId={utils.EmbyServers[ContentMetadata['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[ContentMetadata['ServerId']].ServerData['AccessToken']}&StartTimeTicks={StartTimeTicks}&MaxAudioChannels=1&VideoCodec=h264&MaxHeight=1080&VideoBitrate=1000000&AudioCodec=aac&MaxFramerate=25&Profile=baseline&stream.ts|seekable=0&failonerror=false&verifypeer=false" # Works
        else: # Audio
            PlayerId = 0
            ThemeFile = f"{utils.EmbyServers[ContentMetadata['ServerId']].ServerData['ServerUrl']}/emby/audio/{ContentMetadata['EmbyId']}/stream.aac?MediaSourceId={MediaSourceId}&PlaySessionId={PlaySessionId}&DeviceId={utils.EmbyServers[ContentMetadata['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[ContentMetadata['ServerId']].ServerData['AccessToken']}&StartTimeTicks={StartTimeTicks}&AudioCodec=aac&Profile=baseline&MaxAudioChannels=1&VideoStreamIndex-1&EnableAutoStreamCopy=false&VideoCodec=copy&stream.acc|seekable=0&failonerror=false&verifypeer=false" # Works

        KodiIdLocal = utils.set_EmbyId_ServerId_by_Fake_KodiId(ContentMetadata['EmbyId'], ContentMetadata['ServerId'])
        KodiItem['dbid'] = KodiIdLocal
        return KodiItem, KodiIdLocal, ThemeFile, PlayerId, MediaSourceId, PlaySessionId, ContentMetadata['EmbyId'], MediaSourceId

    return None, 0, "", 0, "", "", 0, ""

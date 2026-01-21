from _thread import start_new_thread, allocate_lock
import os
import json
import sys
import re
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from dateutil import tz, parser

try:
    from PIL import Image, ImageFont, ImageDraw
    import io
    ImageOverlay = True
except:
    ImageOverlay = False

import xbmcvfs
import xbmc
import xbmcaddon
import xbmcgui

# Add bundled pypinyin to path
try:
    addon_path = xbmcvfs.translatePath("special://home/addons/plugin.service.emby-next-gen/")
    lib_path = os.path.join(addon_path, 'resources', 'lib')
    if lib_path not in sys.path:
        sys.path.insert(0, lib_path)
except:
    pass

# Import pypinyin with graceful fallback
try:
    import pypinyin
    PYPINYIN_AVAILABLE = True
except:
    PYPINYIN_AVAILABLE = False
    xbmc.log("EMBY.helper.utils: pypinyin library not available, pinyin conversion will be disabled", 2) # LOGWARNING

Addon = xbmcaddon.Addon("plugin.service.emby-next-gen")
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
CustomDialogParameters = (Addon.getAddonInfo('path'), "default", "1080i")
WidgetsRefreshLock = allocate_lock()
PlayerBusy = allocate_lock()
EmbyTypeMapping = {"Person": "actor", "Video": "movie", "Movie": "movie", "Series": "tvshow", "Season": "season", "Episode": "episode", "Audio": "song", "MusicAlbum": "album", "MusicArtist": "artist", "Genre": "genre", "MusicGenre": "genre", "Tag": "tag" , "Studio": "studio" , "BoxSet": "set", "Folder": None, "MusicVideo": "musicvideo", "Playlist": "Playlist"}
KodiTypeMapping = {"actor": "Person", "tvshow": "Series", "season": "Season", "episode": "Episode", "song": "Audio", "album": "MusicAlbum", "artist": "MusicArtist", "genre": "Genre", "tag": "Tag", "studio": "Studio" , "set": "BoxSet", "musicvideo": "MusicVideo", "playlist": "Playlist", "movie": "Movie", "videoversion": "Video", "video": "Video"}
icon = ""
ForbiddenCharecters = ("/", "<", ">", ":", '"', "\\", "|", "?", "*", " ", "&", chr(0), chr(1), chr(2), chr(3), chr(4), chr(5), chr(6), chr(7), chr(8), chr(9), chr(10), chr(11), chr(12), chr(13), chr(14), chr(15), chr(16), chr(17), chr(18), chr(19), chr(20), chr(21), chr(22), chr(23), chr(24), chr(25), chr(26), chr(27), chr(28), chr(29), chr(30), chr(31))
FilesizeSuffixes = ('B', 'KB', 'MB', 'GB', 'TB')
EmbyServers = {}
EmbyServerIds = []
QueryCache = {}
QueryCacheMapping = {}
UpcomingLastQueryTicks = 0
RemoteMode = False
ItemSkipUpdate = []
MinimumVersion = "12.3.0"
CurrentServicePluginVersion = ""
EmbyServerVersionResync = "4.9.0.25"
refreshskin = False
device_name = "Kodi"
xspplaylists = False
animateicon = True
TranscodeFormatVideo = ""
TranscodeFormatAudio = ""
videoBitrate = 0
audioBitrate = 0
resumeJumpBack = 0
displayMessage = 1000
newContentTime = 1000
startupDelay = 0
curltimeouts = 2
backupPath = ""
enablehttp2 = False
MinimumSetup = ""
autoclose = 5
maxnodeitems = 25
deviceName = "Kodi"
useDirectPaths = False
menuOptions = False
newContent = False
restartMsg = False
connectMsg = False
TextureCacheCancel = False
enableDeleteByKodiEvent = False
addUsersHidden = False
enableContextDelete = False
enableContextSettingsOptions = False
enableContextRemoteOptions = True
enableContextDownloadOptions = True
enableContextFavouriteOptions = True
enableContextSpecialsOptions = True
enableContextRecordingOptions = True
enableContextRefreshOptions = True
enableContextGotoOptions = True
enableContextSimilarOptions = True
enableContextPlayRandom = True
verifyFreeSpace = True
verifyKodiCompanion = True
SyncLiveTvOnEvents = False
SelectDefaultVideoversion = False
transcode_h264 = False
transcode_hevc = False
transcode_av1 = False
transcode_vp8 = False
transcode_vp9 = False
transcode_wmv3 = False
transcode_mpeg4 = False
transcode_mpeg2video = False
transcode_mjpeg = False
transcode_msmpeg4v3 = False
transcode_aac = False
transcode_mp3 = False
transcode_mp2 = False
transcode_dts = False
transcode_ac3 = False
transcode_eac3 = False
transcode_pcm_mulaw = False
transcode_pcm_s24le = False
transcode_vorbis = False
transcode_wmav2 = False
transcode_ac4 = False
transcode_msmpeg4v2 = False
transcode_vc1 = False
transcode_prores = False
transcode_h264_resolution = 0
transcode_hevc_resolution = 0
transcode_av1_resolution = 0
transcode_vp8_resolution = 0
transcode_vp9_resolution = 0
transcode_wmv3_resolution = 0
transcode_mpeg4_resolution = 0
transcode_mpeg2video_resolution = 0
transcode_mjpeg_resolution = 0
transcode_msmpeg4v2_resolution = 0
transcode_msmpeg4v3_resolution = 0
transcode_vc1_resolution = 0
transcode_prores_resolution = 0
transcode_resolution = 0
transcode_pcm_s16le = False
transcode_aac_latm = False
transcode_dtshd_hra = False
transcode_dtshd_ma = False
transcode_truehd = False
transcode_opus = False
transcode_livetv_video = False
transcode_livetv_audio = False
transcode_select_audiostream = False
skipintroembuarydesign = False
enableCinemaMovies = False
enableCinemaEpisodes = False
enableSkipIntro = False
enableSkipCredits = False
askSkipIntro = False
askSkipCredits = False
askCinema = False
localTrailers = False
Trailers = False
offerDelete = False
deleteTV = False
deleteMovies = False
enableCoverArt = False
compressArt = False
getDateCreated = False
getGenres = False
getStudios = False
getTaglines = False
getOverview = False
getLocalTrailers = False
getProductionLocations = False
getTotalEpisodes = True
getCast = False
deviceNameOpt = False
artworkcacheenable = True
syncdate = ""
synctime = ""
PauseSyncDuringPlayback = False
PauseRefreshLibrary = False
PauseRefreshProgress = False
PauseRefreshChapterImages = False
PauseVacuumDatabase = False
PauseLocalThemeVideosUploadTask = False
PauseLocalThemeSongsUploadTask = False
PauseChapterApiUpdateIntroDB = False
PauseTvMazeUpdateTask = False
PauseServerSync = False
PauseScanInternalMetadataFolderTask = False
PauseRefreshInternetChannels = False
PauseRefreshGuide = False
PauseDownloadSubtitles = False
PauseLocalYTrailersDownloadTask = False
PauseTVLocalThemeSongDownloadTask = False
PauseLocalThemeVideosDownloadTask = False
PauseLocalThemeSongsDownloadTask = False
PauseMarkers = False
PauseSyncPrepare = False
PauseOther = False
PauseEmbScriptxSchedTask = False
webservicemode = "webdav"
busyMsg = True
offlineMsg = True
imdbrating = True
websocketenabled = True
startsyncenabled = True
remotecontrol_force_clients = True
remotecontrol_client_control = True
remotecontrol_sync_clients = True
remotecontrol_wait_clients = 30
remotecontrol_drift = 500
remotecontrol_auto_ack = False
remotecontrol_resync_clients = False
remotecontrol_resync_time = 10
remotecontrol_keep_clients = False
watchtogeter_start_delay = 20
compressArtLevel = 100
ArtworkLimitations = False
ArtworkLimitationPrimary = 50
ArtworkLimitationArt = 50
ArtworkLimitationBanner = 30
ArtworkLimitationDisc = 30
ArtworkLimitationLogo = 30
ArtworkLimitationThumb = 40
ArtworkLimitationBackdrop = 100
ArtworkLimitationChapter = 20
DownloadPath = "special://profile/addon_data/plugin.service.emby-next-gen/"
FolderAddonUserdata = "special://profile/addon_data/plugin.service.emby-next-gen/"
FolderEmbyTemp = "special://profile/addon_data/plugin.service.emby-next-gen/temp/"
FolderUserdataThumbnails = "special://profile/Thumbnails/"
PlaylistPathMusic = "special://profile/playlists/music/"
PlaylistPathVideo = "special://profile/playlists/video/"
SystemShutdown = False
SyncPause = {}  # keys: playing, kodi_sleep, embyserverID, , kodi_rw, priority (thread with higher priorit needs access)
WidgetRefresh = {"video": False, "music": False}
BoxSetsToTags = False
MovieToSeries = True
SyncFavorites = False
Dialog = xbmcgui.Dialog()
WizardCompleted = True
LiveTVEnabled = False
ThemesEnabled = False
AssignEpisodePostersToTVShowPoster = False
sslverify = False
AddonModePath = "dav://127.0.0.1:57342/"
TranslationsCached = {}
Playlists = (xbmc.PlayList(0), xbmc.PlayList(1))
ScreenResolution = (1920, 1080)
HTTPResponseCaches = {}
FavoriteQueue = None
MusicartistPaging = 10000
MusicalbumPaging = 10000
AudioPaging = 20000
MoviePaging = 5000
MusicvideoPaging = 5000
SeriesPaging = 5000
SeasonPaging = 5000
EpisodePaging = 5000
VideoPaging = 5000
GenrePaging = 5000
PhotoalbumPaging = 5000
PhotoPaging = 5000
MusicgenrePaging = 5000
PlaylistPaging = 5000
ChannelsPaging = 5000
LiveTVPaging = 5000
TrailerPaging = 20000
BoxsetPaging = 20000
TagPaging = 20000
StudioPaging = 20000
AllPaging = 5000
FolderPaging = 100000
PersonPaging = 100000
MaxURILength = 1500
SyncHighestResolutionAsDefault = True
SyncLocalOverPlugins = True
AutoSelectHighestResolution = False
NotifyEvents = False
followhttp = False
followhttptimeout = 5
WebserviceWorkers = 10
BusyDialogClose = False
ArtworkCacheIncremental = False
LinkMusicVideos = True
XbmcMonitor = None
Tos = "CS5, EF (Expedited Forwarding)"
IconExtensions = ("jpg", "png", "gif", "webp", "apng", "avif", "svg", "ukn")

def get_pinyin(text):
    """
    Convert Chinese characters in text to pinyin first letters.
    
    :param text: Input text string
    :return: Pinyin first letters string, or original text if pypinyin unavailable
    """
    if not text or not PYPINYIN_AVAILABLE:
        return text if text else ''
    
    try:
        # Get pinyin for all characters
        pinyin_result = pypinyin.pinyin(text, style=pypinyin.NORMAL, heteronym=True)
        result = []
        char_index = 0
        
        for pinyin_list in pinyin_result:
            # Handle heteronym (multiple pronunciations) - use first one
            if len(pinyin_list) > 1 and len(set([p[0].lower() for p in pinyin_list])) > 1:
                # Multiple pronunciations with different first letters - use first
                pinyin_list = [pinyin_list[0]]
            
            # Check if this is the original character (not converted to pinyin)
            if len(pinyin_list) == 1 and pinyin_list[0] == text[char_index:char_index + len(pinyin_list[0])]:
                # Original string returned (likely English/number, not Chinese)
                original_segment = pinyin_list[0]
                char_index += len(original_segment)
                
                # If it's alphanumeric, process based on word boundaries
                if re.match(r'^[0-9a-zA-Z]+$', original_segment):
                    # Check if there are spaces in the original text around this segment
                    # For space-separated words, extract first letter of each
                    # For continuous strings, include as-is
                    # Split by spaces to identify word boundaries
                    words = original_segment.split()
                    if len(words) > 1:
                        # Space-separated words - get first letter of each
                        result.extend([word[0] for word in words if word])
                    else:
                        # Continuous alphanumeric - include as-is
                        result.append(original_segment)
                else:
                    # Extract alphanumeric parts from mixed content
                    alphanumeric_parts = re.findall(r'[0-9a-zA-Z]+', original_segment)
                    for part in alphanumeric_parts:
                        # Check if part has spaces (word boundaries)
                        part_words = part.split()
                        if len(part_words) > 1:
                            result.extend([word[0] for word in part_words if word])
                        else:
                            result.append(part)
            else:
                # Chinese character converted to pinyin - get first letter
                result.append(pinyin_list[0][0])
                char_index += 1
        
        # Join and return lowercase, spaces removed
        return ''.join(result).replace(' ', '').lower()
    
    except Exception as e:
        xbmc.log(f"EMBY.helper.utils: Error in get_pinyin: {e}", 2) # LOGWARNING
        return text if text else ''

def refresh_widgets(isVideo):
    with WidgetsRefreshLock:
        xbmc.log("EMBY.helper.utils: Refresh widgets initialized", 1) # LOGINFO
        IsScanningVideo, IsScanningMusic = get_scans()

        if isVideo and not IsScanningVideo and not WidgetRefresh['video']:
            globals()["WidgetRefresh"]['video'] = True
            xbmc.log("EMBY.helper.utils: Refresh widgets video started", 1) # LOGINFO

            if not SendJson('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","params":{"showdialogs":false,"directory":"EMBY_widget_refresh_trigger"},"id":1}', True):
                globals()["WidgetRefresh"]['video'] = False

        if not isVideo and not IsScanningMusic and not WidgetRefresh['music']:
            globals()["WidgetRefresh"]['music'] = True
            xbmc.log("EMBY.helper.utils: Refresh widgets music started", 1) # LOGINFO

            if not SendJson('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":"EMBY_widget_refresh_trigger"},"id":1}', True):
                globals()["WidgetRefresh"]['music'] = False

def get_scans():
    IsScanningMusic = False
    IsScanningVideo = False
    RPCResult = SendJson('{"jsonrpc":"2.0","method":"XBMC.GetInfoBooleans","params": {"booleans": ["Library.IsScanningMusic", "Library.IsScanningVideo"]},"id":1}', True).get("result", {})

    if RPCResult:
        IsScanningMusic = RPCResult.get("Library.IsScanningMusic", False)
        IsScanningVideo = RPCResult.get("Library.IsScanningVideo", False)
        globals()['SyncPause']['kodi_rw'] = IsScanningVideo or IsScanningMusic

    return IsScanningVideo, IsScanningMusic

def SendJson(JsonString, ForceBreak=False):
    LogSend = False
    JsonString = JsonString.replace("\\", "\\\\") # escape backslashes

    for Index in range(55): # retry -> timeout 10 seconds
        Ret = xbmc.executeJSONRPC(JsonString)

        if not Ret: # Valid but not correct Kodi return value -> Kodi bug
            xbmc.log(f"Emby.helper.utils: Json no response: {JsonString}", 2) # LOGWARNING
            return {}

        Ret = json.loads(Ret)

        if not Ret.get("error", False):
            xbmc.log(f"Emby.helper.utils: Json response: {JsonString} / {Ret}", 0) # LOGDEBUG
            return Ret

        xbmc.log(f"Emby.helper.utils: Json error: {JsonString} / {Ret}", 3) # LOGERROR

        if ForceBreak:
            return {}

        if not LogSend:
            xbmc.log(f"Emby.helper.utils: Json error, retry: {JsonString}", 2) # LOGWARNING
            LogSend = True

        if Index < 50: # 5 seconds rapidly
            if sleep(0.1):
                return {}
        else: # after 5 seconds delay cycle by 1 second for the last 5 seconds
            if sleep(1):
                return {}

    return {}

def image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText, LowPriority, PlaybackCheck):
    xbmc.log(f"EMBY.helper.utils: Add image text overlay: {EmbyID}", 0) # LOGDEBUG

    if ImageTag == "noimage":
        BinaryData = noimagejpg
        ContentType = "image/jpeg"
        FileExtension = "jpg"
    else:
        BinaryData, ContentType, FileExtension = EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag, False, LowPriority, PlaybackCheck)

        if not BinaryData:
            BinaryData = noimagejpg
            ContentType = "image/jpeg"
            FileExtension = "jpg"

    if not ImageOverlay or not OverlayText:
        return BinaryData, ContentType, FileExtension

    try:
        img = Image.open(io.BytesIO(BinaryData))
        draw = ImageDraw.Draw(img, "RGBA")
        font = ImageFont.truetype(FontPath, 1)
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: Pillow issue: {Error}", 3) # LOGERROR
        return BinaryData, ContentType, FileExtension

    ImageWidth, ImageHeight = img.size
    BorderSize = int(ImageHeight * 0.01)  # 1% of image height is box border size
    BoxTop = int(ImageHeight * 0.75)  # Box top position is 75% of image height
    BoxHeight = int(ImageHeight * 0.15)  # 15% of image height is box height
    BoxWidth = int(ImageWidth)
    fontsize = 5

    try:
        _, _, FontWidth, FontHeight = font.getbbox("Title Sequence")
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: Pillow issue (getbox): {Error}", 3) # LOGERROR
        return BinaryData, ContentType, FileExtension

    while FontHeight < BoxHeight - BorderSize * 2 and FontWidth < BoxWidth - BorderSize * 2:
        fontsize += 1
        font = ImageFont.truetype(FontPath, fontsize)
        _, _, FontWidth, FontHeight = font.getbbox("Title Sequence")

    OverlayText = OverlayText.split("\n")
    OverlayTextNewLines = len(OverlayText)

    if OverlayTextNewLines > 1:
        fontsize = round(fontsize / OverlayTextNewLines)
        font = ImageFont.truetype(FontPath, fontsize)

    OverlayText = "\n".join(OverlayText)
    draw.rectangle((-100, BoxTop, BoxWidth + 200, BoxTop + BoxHeight), fill=(0, 0, 0, 127), outline="white",  width=BorderSize)
    draw.text(xy=(ImageWidth / 2, BoxTop + (BoxHeight / 2)) , text=OverlayText, fill="#FFFFFF", font=font, anchor="mm", align="center")
    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format=img.format)
    FileExtension = img.format
    FileExtension = FileExtension.lower()

    if FileExtension in ("jpg", "jpeg"):
        ContentType = "image/jpeg"
        FileExtension = "jpg"
    elif FileExtension == "png":
        ContentType = "image/png"
    elif FileExtension == "gif":
        ContentType = "image/gif"
    elif FileExtension == "webp":
        ContentType = "image/webp"
    elif FileExtension == "apng":
        ContentType = "image/apng"
    elif FileExtension == "avif":
        ContentType = "image/avif"
    elif FileExtension == "svg":
        ContentType = "image/svg"
    else:
        FileExtension = "ukn"
        ContentType = "image/ukn"

    return imgByteArr.getvalue(), ContentType, FileExtension

# Download image
def download_Icon(ItemId, ImageTag, ServerId, NodeName, Force):
    ItemId = str(ItemId).replace('999999993', '') # Collection as Tags

    for IconExtension in IconExtensions:
        FileExists = f"{FolderEmbyTemp}{ItemId}.{IconExtension}"
        Found = xbmcvfs.exists(f"{FolderEmbyTemp}{ItemId}.{IconExtension}")

        if Found:
            break

    if not Found or Force:
        delFile(FileExists)
        BinaryData, _, FileExtension = image_overlay(ImageTag, ServerId, ItemId, "Primary", 0, NodeName, False, False)
        IconFile = f"{FolderEmbyTemp}{ItemId}.{FileExtension}"
        writeFile(IconFile, BinaryData)
    else:
        IconFile = FileExists

    return IconFile

def restart_kodi():
    xbmc.log("EMBY.helper.utils: Restart Kodi", 1) # LOGINFO
    globals()["SystemShutdown"] = True
    xbmc.executebuiltin('RestartApp')

def sleep(Seconds):
    if XbmcMonitor:
        if XbmcMonitor.waitForAbort(Seconds):
            return True
    else:
        for _ in range(int(Seconds * 10)):
            if SystemShutdown:
                return True

            xbmc.sleep(100)

    return False

# Delete objects from kodi cache
def delFolder(path, Pattern=""):
    xbmc.log("EMBY.helper.utils: --[ delete folder ]", 0) # LOGDEBUG
    dirs, files = xbmcvfs.listdir(path)
    SelectedDirs = ()

    if not Pattern:
        SelectedDirs = dirs
    else:
        for Dir in dirs:
            if Pattern in Dir:
                SelectedDirs += (Dir,)

    delete_recursive(path, SelectedDirs)

    for Filename in files:
        if Pattern in Filename:
            delFile(os.path.join(path, Filename))

    if path:
        rmFolder(path)

    xbmc.log(f"EMBY.helper.utils: DELETE {path}", 2) # LOGWARNING

# Delete files and dirs recursively
def delete_recursive(path, dirs):
    for directory in dirs:
        SubFolder = os.path.join(path, directory, '')
        dirs2, files = xbmcvfs.listdir(SubFolder)

        for Filename in files:
            delFile(os.path.join(SubFolder, Filename))

        delete_recursive(SubFolder, dirs2)
        rmFolder(SubFolder)

def rmFolder(Path):
    try:
        xbmcvfs.rmdir(Path)
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: Delete folder issue: {Error} / {Path}", 3) # LOGERROR

def mkDir(Path):
    if xbmcvfs.exists(Path):
        return True

    try:
        xbmcvfs.mkdir(Path)
        return True
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: mkDir: {Error}", 3) # LOGERROR

    return False

def delFile(Path):
    try:
        xbmcvfs.delete(Path)
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: delFile: {Error}", 3) # LOGERROR

def copyFile(SourcePath, DestinationPath):
    if xbmcvfs.exists(DestinationPath):
        xbmc.log(f"EMBY.helper.utils: copy: File exists: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
        return

    try:
        success = xbmcvfs.copy(SourcePath, DestinationPath)

        if not success:
            xbmc.log(f"EMBY.helper.utils: sucess: {success} copy: {SourcePath} to {DestinationPath}", 3) # LOGERROR
        else:
            xbmc.log(f"EMBY.helper.utils: sucess: {success} copy: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: copy issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

def renameFile(SourcePath, DestinationPath):
    if xbmcvfs.exists(DestinationPath):
        xbmc.log(f"EMBY.helper.utils: rename: File exists: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
        return True

    try:
        success = xbmcvfs.rename(SourcePath, DestinationPath)

        if not success:
            xbmc.log(f"EMBY.helper.utils: sucess: {success} rename: {SourcePath} to {DestinationPath}", 3) # LOGERROR
        else:
            xbmc.log(f"EMBY.helper.utils: sucess: {success} rename: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG

        return success
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: rename issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

    return False

def readFileBinary(Path):
    try:
        with xbmcvfs.File(Path) as infile:
            return infile.readBytes()
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: readFileBinary ({Path}): {Error}", 2) # LOGWARNING

    return b""

def readFileString(Path):
    try:
        with xbmcvfs.File(Path) as infile:
            return infile.read()
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: readFileString ({Path}): {Error}", 2) # LOGWARNING

    return ""

def writeFile(Path, Data):
    try:
        with xbmcvfs.File(Path, 'w') as outfile:
            outfile.write(Data)
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: writeFile ({Path}): {Error}", 2) # LOGWARNING

def getFreeSpace(Path):
    if verifyFreeSpace:
        try:
            Path = xbmcvfs.translatePath(Path)
            space = os.statvfs(Path)
            free = space.f_bavail * space.f_frsize / 1024
            return free
        except Exception as Error: # not suported by Windows
            xbmc.log(f"EMBY.helper.utils: getFreeSpace: {Error}", 2) # LOGWARNING
            return 9999999
    else:
        return 9999999

def currenttime():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def currenttime_kodi_format():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def currenttime_kodi_format_and_unixtime():
    Current = datetime.now()
    KodiFormat = Current.strftime('%Y-%m-%d %H:%M:%S')
    UnixTime = int(datetime.timestamp(Current))
    return KodiFormat, UnixTime

def get_unixtime_emby_format(): # Position(ticks) in Emby format 1 sec = 10000
    return datetime.timestamp(datetime.now(timezone.utc)) * 10000

def get_url_info(ConnectionString):
    if not ConnectionString.startswith("http://") and not ConnectionString.startswith("https://"):
        ConnectionString = f"http://{ConnectionString}"

    Temp = ConnectionString.split(":")
    Scheme = Temp[0]

    if len(Temp) < 3:
        if Scheme == "https":
            Port = 443
        else:
            Port = 80
    else:
        Port = int(Temp[2].split("?", 1)[0].split("/", 1)[0])

    Hostname = Temp[1][2:].split("?", 1)[0].split("/", 1)[0]
    SubUrl = ConnectionString.replace(f"{Scheme}://", "").replace(f":{Port}", "").replace(Hostname, "").rsplit("/", 1)[0]
    SubUrl = f"/{SubUrl}/".replace("//", "/")
    xbmc.log(f"Emby.helper.utils: get_url_info: ConnectionString='{ConnectionString}' Scheme='{Scheme}' Hostname='{Hostname}' SubUrl='{SubUrl}' Port='{Port}'", 0) # LOGDEBUG
    return Scheme, Hostname, Port, SubUrl

# Remove all emby playlists
def delete_playlists():
    SearchFolders = [PlaylistPathVideo, PlaylistPathMusic]

    for SearchFolder in SearchFolders:
        _, Filenames = xbmcvfs.listdir(SearchFolder)

        for Filename in Filenames:
            if Filename.endswith('_(video).m3u') or Filename.endswith('_(audio).m3u'):
                delFile(os.path.join(SearchFolder, Filename))

# Remove all nodes
def delete_nodes():
    delFolder("special://profile/library/video/", "emby_")
    delFolder("special://profile/library/music/", "emby_")
    mkDir("special://profile/library/video/")
    mkDir("special://profile/library/music/")

# Convert the gmt datetime to local
def convert_to_gmt(local_time):
    if not local_time:
        return ""

    if isinstance(local_time, str):
        local_time = parser.parse(local_time.encode('utf-8'))
        utc_zone = tz.tzutc()
        local_zone = tz.tzlocal()
        local_time = local_time.replace(tzinfo=local_zone)
        utc_time = local_time.astimezone(utc_zone)
        return utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    return ""

# Convert the gmt datetime to local
def convert_to_local(date, DateOnly=False, YearOnly=False):
    if not date or str(date) == "0":
        return "0"

    try:
        if isinstance(date, int):
            date = str(date)

        if isinstance(date, str):
            date = parser.parse(date.encode('utf-8'))

            if not date.tzname():
                date = date.replace(tzinfo=tz.tzutc())

        timestamp = (date - datetime(1970, 1, 1, tzinfo=tz.tzutc())).total_seconds()

        if timestamp >= 0:
            timestamp = datetime.fromtimestamp(timestamp)
        else:
            timestamp = datetime(1970, 1, 1) + timedelta(seconds=int(timestamp))
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: invalid timestamp: {Error}", 2) # LOGWARNING
        return "0"

    if timestamp.year < 1900:
        xbmc.log(f"EMBY.helper.utils: invalid timestamp < 1900: {timestamp.year}", 2) # LOGWARNING
        return "0"

    if DateOnly:
        return timestamp.strftime('%Y-%m-%d')

    if YearOnly:
        return int(timestamp.strftime('%Y'))

    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def Translate(Id):
    if Id in TranslationsCached:
        return TranslationsCached[Id]

    result = Addon.getLocalizedString(Id)

    if not result:
        result = xbmc.getLocalizedString(Id)

    globals()['TranslationsCached'][Id] = result
    return result

def valid_Filename(Filename):
    if len(Filename) > 150:
        Filename = Filename[:150]
        xbmc.log(f"Emby.helper.utils: Filename too long -> cut: {Filename}", 2) # LOGWARNING

    Filename = decode_XML(Filename)

    for Char in ForbiddenCharecters:
        Filename = Filename.replace(Char, "_")

    return Filename

def get_Filename(Path, NativeMode):
    Separator = get_Path_Seperator(Path)
    Pos = Path.rfind(Separator)
    Filename = Path[Pos + 1:]

    if not NativeMode and webservicemode != "pathsubstitution":
        Filename = quote(Filename)

    return Filename

def SizeToText(FileSize):
    Index = 0

    while FileSize > 1024 and Index < 4:
        Index += 1
        FileSize /= 1024.0

    return f"{round(FileSize)}{FilesizeSuffixes[Index]}"

# Copy folder content from one to another
def copytree(PathSource, PathDestination, FilesExclude, Recursive, Overwrite):
    Folders, Filenames = xbmcvfs.listdir(PathSource)
    mkDir(PathDestination)

    if Recursive and Folders:
        copy_recursive(PathSource, Folders, PathDestination, FilesExclude, Overwrite)

    copy_files(Filenames, FilesExclude, PathSource, PathDestination, Overwrite)
    xbmc.log(f"EMBY.helper.utils: Copied {PathSource}", 1) # LOGINFO

def copy_recursive(PathSource, Folders, PathDestination, FilesExclude, Overwrite):
    for Folder in Folders:
        FolderSource = os.path.join(PathSource, Folder, '')
        FolderDestination = os.path.join(PathDestination, Folder, '')
        mkDir(FolderDestination)
        SubFolders, Filenames = xbmcvfs.listdir(FolderSource)

        if SubFolders:
            copy_recursive(FolderSource, SubFolders, FolderDestination, FilesExclude, Overwrite)

        copy_files(Filenames, FilesExclude, FolderSource, FolderDestination, Overwrite)

def copy_files(Filenames, FilesExclude, FolderSource, FolderDestination, Overwrite):
    for Filename in Filenames:
        # Filter by filename end
        if FilesExclude:
            Found = False

            for FileExclude in FilesExclude:
                if Filename.endswith(FileExclude):
                    Found = True
                    break

            if Found:
                xbmc.log(f"EMBY.helper.utils: Filecopy filtered by fileend: {Filename}", 0) # LOGDEBUG
                continue

        FilePathDestination = os.path.join(FolderDestination, Filename)

        if xbmcvfs.exists(FilePathDestination):
            if Overwrite:
                delFile(FilePathDestination)
                copyFile(os.path.join(FolderSource, Filename), FilePathDestination)
        else:
            copyFile(os.path.join(FolderSource, Filename), FilePathDestination)

# Kodi Settings
def InitSettings():
    load_settings('TranscodeFormatVideo')
    load_settings('TranscodeFormatAudio')
    load_settings('resumeJumpBack')
    load_settings('autoclose')
    load_settings('backupPath')
    load_settings('MinimumSetup')
    load_settings('CurrentServicePluginVersion')
    load_settings('deviceName')
    load_settings('syncdate')
    load_settings('synctime')
    load_settings('watchtogeter_start_delay')
    load_settings('compressArtLevel')
    load_settings('ArtworkLimitationPrimary')
    load_settings('ArtworkLimitationArt')
    load_settings('ArtworkLimitationBanner')
    load_settings('ArtworkLimitationDisc')
    load_settings('ArtworkLimitationLogo')
    load_settings('ArtworkLimitationThumb')
    load_settings('ArtworkLimitationBackdrop')
    load_settings('ArtworkLimitationChapter')
    load_settings('DownloadPath')
    load_settings('Tos')
    load_settings('webservicemode')
    load_settings_int('transcode_resolution')
    load_settings_int('transcode_h264_resolution')
    load_settings_int('transcode_hevc_resolution')
    load_settings_int('transcode_av1_resolution')
    load_settings_int('transcode_vp8_resolution')
    load_settings_int('transcode_vp9_resolution')
    load_settings_int('transcode_wmv3_resolution')
    load_settings_int('transcode_mpeg4_resolution')
    load_settings_int('transcode_mpeg2video_resolution')
    load_settings_int('transcode_mjpeg_resolution')
    load_settings_int('transcode_msmpeg4v2_resolution')
    load_settings_int('transcode_msmpeg4v3_resolution')
    load_settings_int('transcode_vc1_resolution')
    load_settings_int('transcode_prores_resolution')
    load_settings_int('displayMessage')
    load_settings_int('newContentTime')
    load_settings_int('maxnodeitems')
    load_settings_int('videoBitrate')
    load_settings_int('audioBitrate')
    load_settings_int('startupDelay')
    load_settings_int('curltimeouts')
    load_settings_int('remotecontrol_wait_clients')
    load_settings_int('remotecontrol_drift')
    load_settings_int('remotecontrol_resync_time')
    load_settings_int('MusicartistPaging')
    load_settings_int('MusicalbumPaging')
    load_settings_int('AudioPaging')
    load_settings_int('MoviePaging')
    load_settings_int('MusicvideoPaging')
    load_settings_int('SeriesPaging')
    load_settings_int('SeasonPaging')
    load_settings_int('EpisodePaging')
    load_settings_int('VideoPaging')
    load_settings_int('GenrePaging')
    load_settings_int('PhotoalbumPaging')
    load_settings_int('PhotoPaging')
    load_settings_int('MusicgenrePaging')
    load_settings_int('PlaylistPaging')
    load_settings_int('ChannelsPaging')
    load_settings_int('LiveTVPaging')
    load_settings_int('TrailerPaging')
    load_settings_int('BoxsetPaging')
    load_settings_int('TagPaging')
    load_settings_int('StudioPaging')
    load_settings_int('AllPaging')
    load_settings_int('FolderPaging')
    load_settings_int('PersonPaging')
    load_settings_int('MaxURILength')
    load_settings_int('followhttptimeout')
    load_settings_int('WebserviceWorkers')
    load_settings_bool('ArtworkLimitations')
    load_settings_bool('sslverify')
    load_settings_bool('PauseSyncDuringPlayback')
    load_settings_bool('PauseRefreshLibrary')
    load_settings_bool('PauseRefreshProgress')
    load_settings_bool('PauseRefreshChapterImages')
    load_settings_bool('PauseVacuumDatabase')
    load_settings_bool('PauseLocalThemeVideosUploadTask')
    load_settings_bool('PauseLocalThemeSongsUploadTask')
    load_settings_bool('PauseChapterApiUpdateIntroDB')
    load_settings_bool('PauseTvMazeUpdateTask')
    load_settings_bool('PauseServerSync')
    load_settings_bool('PauseScanInternalMetadataFolderTask')
    load_settings_bool('PauseRefreshInternetChannels')
    load_settings_bool('PauseRefreshGuide')
    load_settings_bool('PauseDownloadSubtitles')
    load_settings_bool('PauseLocalYTrailersDownloadTask')
    load_settings_bool('PauseTVLocalThemeSongDownloadTask')
    load_settings_bool('PauseLocalThemeVideosDownloadTask')
    load_settings_bool('PauseLocalThemeSongsDownloadTask')
    load_settings_bool('PauseMarkers')
    load_settings_bool('PauseSyncPrepare')
    load_settings_bool('PauseEmbScriptxSchedTask')
    load_settings_bool('PauseOther')
    load_settings_bool('refreshskin')
    load_settings_bool('animateicon')
    load_settings_bool('enablehttp2')
    load_settings_bool('menuOptions')
    load_settings_bool('xspplaylists')
    load_settings_bool('newContent')
    load_settings_bool('restartMsg')
    load_settings_bool('connectMsg')
    load_settings_bool('addUsersHidden')
    load_settings_bool('enableContextDelete')
    load_settings_bool('enableContextSettingsOptions')
    load_settings_bool('enableContextRemoteOptions')
    load_settings_bool('enableContextDownloadOptions')
    load_settings_bool('enableContextFavouriteOptions')
    load_settings_bool('enableContextSpecialsOptions')
    load_settings_bool('enableContextRecordingOptions')
    load_settings_bool('enableContextRefreshOptions')
    load_settings_bool('enableContextGotoOptions')
    load_settings_bool('enableContextSimilarOptions')
    load_settings_bool('enableContextPlayRandom')
    load_settings_bool('transcode_h264')
    load_settings_bool('transcode_hevc')
    load_settings_bool('transcode_av1')
    load_settings_bool('transcode_vp8')
    load_settings_bool('transcode_vp9')
    load_settings_bool('transcode_wmv3')
    load_settings_bool('transcode_mpeg4')
    load_settings_bool('transcode_mpeg2video')
    load_settings_bool('transcode_mjpeg')
    load_settings_bool('transcode_msmpeg4v3')
    load_settings_bool('transcode_aac')
    load_settings_bool('transcode_mp3')
    load_settings_bool('transcode_mp2')
    load_settings_bool('transcode_dts')
    load_settings_bool('transcode_ac3')
    load_settings_bool('transcode_eac3')
    load_settings_bool('transcode_pcm_mulaw')
    load_settings_bool('transcode_pcm_s24le')
    load_settings_bool('transcode_vorbis')
    load_settings_bool('transcode_wmav2')
    load_settings_bool('transcode_ac4')
    load_settings_bool('transcode_msmpeg4v2')
    load_settings_bool('transcode_vc1')
    load_settings_bool('transcode_prores')
    load_settings_bool('transcode_pcm_s16le')
    load_settings_bool('transcode_aac_latm')
    load_settings_bool('transcode_dtshd_hra')
    load_settings_bool('transcode_dtshd_ma')
    load_settings_bool('transcode_truehd')
    load_settings_bool('transcode_opus')
    load_settings_bool('transcode_livetv_video')
    load_settings_bool('transcode_livetv_audio')
    load_settings_bool('transcode_select_audiostream')
    load_settings_bool('enableCinemaMovies')
    load_settings_bool('enableCinemaEpisodes')
    load_settings_bool('askCinema')
    load_settings_bool('localTrailers')
    load_settings_bool('Trailers')
    load_settings_bool('offerDelete')
    load_settings_bool('deleteTV')
    load_settings_bool('deleteMovies')
    load_settings_bool('enableCoverArt')
    load_settings_bool('compressArt')
    load_settings_bool('getDateCreated')
    load_settings_bool('getGenres')
    load_settings_bool('getStudios')
    load_settings_bool('getTaglines')
    load_settings_bool('getOverview')
    load_settings_bool('getLocalTrailers')
    load_settings_bool('getProductionLocations')
    load_settings_bool('getTotalEpisodes')
    load_settings_bool('getCast')
    load_settings_bool('deviceNameOpt')
    load_settings_bool('useDirectPaths')
    load_settings_bool('enableDeleteByKodiEvent')
    load_settings_bool('enableSkipIntro')
    load_settings_bool('enableSkipCredits')
    load_settings_bool('askSkipIntro')
    load_settings_bool('askSkipCredits')
    load_settings_bool('skipintroembuarydesign')
    load_settings_bool('busyMsg')
    load_settings_bool('offlineMsg')
    load_settings_bool('AssignEpisodePostersToTVShowPoster')
    load_settings_bool('WizardCompleted')
    load_settings_bool('LiveTVEnabled')
    load_settings_bool('ThemesEnabled')
    load_settings_bool('verifyFreeSpace')
    load_settings_bool('verifyKodiCompanion')
    load_settings_bool('remotecontrol_force_clients')
    load_settings_bool('remotecontrol_client_control')
    load_settings_bool('remotecontrol_sync_clients')
    load_settings_bool('remotecontrol_auto_ack')
    load_settings_bool('remotecontrol_resync_clients')
    load_settings_bool('remotecontrol_keep_clients')
    load_settings_bool('websocketenabled')
    load_settings_bool('startsyncenabled')
    load_settings_bool('BoxSetsToTags')
    load_settings_bool('MovieToSeries')
    load_settings_bool('LinkMusicVideos')
    load_settings_bool('SyncFavorites')
    load_settings_bool('SyncLiveTvOnEvents')
    load_settings_bool('imdbrating')
    load_settings_bool('SyncHighestResolutionAsDefault')
    load_settings_bool('SyncLocalOverPlugins')
    load_settings_bool('AutoSelectHighestResolution')
    load_settings_bool('NotifyEvents')
    load_settings_bool('followhttp')
    load_settings_bool('BusyDialogClose')
    load_settings_bool('ArtworkCacheIncremental')
    load_settings_bool('IsoPathConvertEnabled')
    load_settings('IsoPathConvertPrefix')
    load_settings('IsoPathConvertReplaceTo')
    load_settings_bool('IsoPathConvertRemoveTrailing')

    if ArtworkLimitations:
        globals()["ScreenResolution"] = (int(xbmc.getInfoLabel('System.ScreenWidth')), int(xbmc.getInfoLabel('System.ScreenHeight')))
        xbmc.log(f"EMBY.helper.utils: Screen resolution: {ScreenResolution}", 1) # LOGINFO

    if webservicemode == "pathsubstitution":
        globals()["AddonModePath"] = "/emby_addon_mode/"
    elif webservicemode == "webdav":
        globals()["AddonModePath"] = "dav://127.0.0.1:57342/"
    else:
        globals()["AddonModePath"] = "http://127.0.0.1:57342/"

    if not deviceNameOpt:
        globals()["device_name"] = xbmc.getInfoLabel('System.FriendlyName')
    else:
        globals()["device_name"] = deviceName.replace("/", "_")

    if not device_name:
        globals()["device_name"] = "Kodi"
    else:
        globals()["device_name"] = quote(device_name) # url encode

    # Animated icons
    NewIcon = ""

    if animateicon:
        if icon and icon != "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif":
            NewIcon = "animated"

        globals()["icon"] = "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif"
    else:
        if icon and icon != "special://home/addons/plugin.service.emby-next-gen/resources/icon.png":
            NewIcon = "static"

        globals()["icon"] = "special://home/addons/plugin.service.emby-next-gen/resources/icon.png"

    if NewIcon:
        for PluginId in ("video", "image", "audio", "service"):
            xbmc.log("EMBY.helper.utils: Toggle icon", 1) # LOGINFO
            AddonXml = readFileString(f"special://home/addons/plugin.{PluginId}.emby-next-gen/addon.xml")

            if NewIcon == "static":
                AddonXml = AddonXml.replace("resources/icon-animated.gif", "resources/icon.png")
            else:
                AddonXml = AddonXml.replace("resources/icon.png", "resources/icon-animated.gif")

            writeFile(f"special://home/addons/plugin.{PluginId}.emby-next-gen/addon.xml", AddonXml)

    globals()["displayMessage"] *= 1000
    globals()["newContentTime"] *= 1000
    update_mode_settings()
    xbmcgui.Window(10000).setProperty('EmbyDelete', str(enableContextDelete))
    xbmcgui.Window(10000).setProperty('EmbyRemote', str(enableContextRemoteOptions))
    xbmcgui.Window(10000).setProperty('EmbyDownload', str(enableContextDownloadOptions))
    xbmcgui.Window(10000).setProperty('EmbyFavourite', str(enableContextFavouriteOptions))
    xbmcgui.Window(10000).setProperty('EmbySpecials', str(enableContextSpecialsOptions))
    xbmcgui.Window(10000).setProperty('EmbyRecording', str(enableContextRecordingOptions))
    xbmcgui.Window(10000).setProperty('EmbyRefresh', str(enableContextRefreshOptions))
    xbmcgui.Window(10000).setProperty('EmbyGoto', str(enableContextGotoOptions))
    xbmcgui.Window(10000).setProperty('EmbySimilar', str(enableContextSimilarOptions))
    xbmcgui.Window(10000).setProperty('EmbySettings', str(enableContextSettingsOptions))
    xbmcgui.Window(10000).setProperty('EmbyPlayRandom', str(enableContextPlayRandom))


def update_mode_settings():
    # disable file metadata extraction
    if not useDirectPaths and webservicemode in ("pathsubstitution", "webdav"):
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractflags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractthumb","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.usetags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"musicfiles.usetags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"musicfiles.findremotethumbs","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractchapterthumbs","value":true}}', True)

def set_syncdate(TimeStampConvert):
    if TimeStampConvert:
        LocalTime = convert_to_local(TimeStampConvert, False, False)
        TimeStamp = parser.parse(LocalTime.encode('utf-8'))
        set_settings("syncdate", TimeStamp.strftime('%Y-%m-%d'))
        set_settings("synctime", TimeStamp.strftime('%H:%M'))

def load_settings_bool(setting):
    value = Addon.getSetting(setting)

    if value == "true":
        globals()[setting] = True
    else:
        globals()[setting] = False

def load_settings(setting):
    value = Addon.getSetting(setting)
    globals()[setting] = value

def load_settings_int(setting):
    value = Addon.getSetting(setting)
    globals()[setting] = int(value)

def set_settings(setting, value):
    globals()[setting] = value
    Addon.setSetting(setting, value)

def set_settings_bool(setting, value):
    globals()[setting] = value

    if value:
        Addon.setSetting(setting, "true")
    else:
        Addon.setSetting(setting, "false")

def nodesreset():
    delete_nodes()

    for EmbyServer in list(EmbyServers.values()):
        EmbyServer.Views.update_nodes()

    Dialog.notification(heading=addon_name, icon=icon, message=Translate(33672), sound=False, time=displayMessage)

def get_Path_Seperator(Path):
    Pos = Path.rfind("/")

    if Pos == -1:
        return "\\"

    return "/"

def encode_XML(Data):
    Data = Data.replace("&", "&amp;")
    Data = Data.replace("<", "&lt;")
    Data = Data.replace(">", "&gt;")
    Data = Data.replace("\"", "&quot;")
    Data = Data.replace("'", "&apos;")
    return Data

def decode_XML(Data):
    Data = Data.replace("&amp;", "&")
    Data = Data.replace("&lt;", "<")
    Data = Data.replace("&gt;", ">")
    Data = Data.replace("&quot;", "\"")
    Data = Data.replace("&apos;", "'")
    return Data

def check_iptvsimple():
    if not SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"pvr.iptvsimple", "properties": ["version"]}}', True):
        xbmc.log("EMBY.helper.utils: iptv simple not found", 2) # LOGWARNING
        set_settings_bool("LiveTVEnabled", False)
        return False

    return True

def check_tvtunes():
    if not SendJson('{"jsonrpc":"2.0","id":1,"method":"Addons.GetAddonDetails","params":{"addonid":"service.tvtunes", "properties": ["version"]}}', True):
        xbmc.log("EMBY.helper.utils: iptv simple not found", 2) # LOGWARNING
        set_settings_bool("ThemesEnabled", False)
        return False

    return True

def notify_event(Message, Data, SendOption):
    if NotifyEvents and SendOption:
        SendJson(f'{{"jsonrpc":"2.0", "method":"JSONRPC.NotifyAll", "params":{{"sender": "emby-next-gen", "message": "{Message}", "data": {json.dumps(Data)}}}, "id": 1}}', True)

def add_cachemapping(EmbyId, ContentRequest, CacheId, Index):
    EmbyId = str(EmbyId)

    if EmbyId in QueryCacheMapping:
        QueryCacheMapping[EmbyId] += ((ContentRequest, CacheId, Index),)
    else:
        QueryCacheMapping[EmbyId] = ((ContentRequest, CacheId, Index),)

def update_querycache_userdata(UserDatas):
    for UserData in UserDatas: # Id, PlaybackPositionTicks, LastPlayedDate, PlayCount, PlaybackEnded
        EmbyId = UserData[0]

        if UserData[1] is not None:
            KodiPlaybackPositionTicks = round(float(UserData[1] / 10000000.0), 6)
        else:
            KodiPlaybackPositionTicks = -1

        KodiLastPlayedDate = UserData[2]
        KodiPlayCount = UserData[3]
        PlaybackEnded = UserData[4]

        if EmbyId in QueryCacheMapping:
            for UpdateItem in QueryCacheMapping[EmbyId]:
                Listitem = QueryCache[UpdateItem[0]][UpdateItem[1]][1][UpdateItem[2]][1]

                if UpdateItem[0] in ("MusicArtist", "MusicAlbum", "Audio", ): # Music content
                    InfoTags = Listitem.getMusicInfoTag()

                    if KodiPlayCount == -1:
                        if PlaybackEnded:
                            CurrentPlaycount = InfoTags.getPlayCount()

                            if isinstance(CurrentPlaycount, int):
                                KodiPlayCount = CurrentPlaycount + 1
                                InfoTags.setPlayCount(KodiPlayCount) # setPlayCount not unified -> upper case for music
                    else:
                        if KodiPlayCount:
                            InfoTags.setPlayCount(KodiPlayCount)
                        else: # might be None
                            InfoTags.setPlayCount(0)
                else: # Video content
                    InfoTags = Listitem.getVideoInfoTag()

                    if KodiPlaybackPositionTicks != -1:
                        if KodiPlaybackPositionTicks > 60:
                            InfoTags.setResumePoint(float(KodiPlaybackPositionTicks))
                        else:
                            InfoTags.setResumePoint(0.0)

                    if KodiPlayCount == -1:
                        if PlaybackEnded:
                            CurrentPlaycount = InfoTags.getPlayCount()

                            if isinstance(CurrentPlaycount, int):
                                KodiPlayCount = CurrentPlaycount + 1
                                InfoTags.setPlaycount(KodiPlayCount) # setPlayCount not unified -> lower case for video
                    else:
                        if KodiPlayCount:
                            InfoTags.setPlaycount(KodiPlayCount)
                        else: # might be None
                            InfoTags.setPlaycount(0)

                if KodiLastPlayedDate:
                    InfoTags.setLastPlayed(KodiLastPlayedDate)

    # Forced cache resets
    DelCaches = ()

    for ContentId, CachedDataL1 in list(QueryCache.items()): # QueryCache["Episode"][CacheId]
        for CachedId in CachedDataL1:
            if CachedId.startswith("forcedrefresh_"):
                DelCaches += ((ContentId, CachedId),)

    for DelCache in DelCaches:
        del globals()['QueryCache'][DelCache[0]][DelCache[1]]

    refresh_DynamicNode()

def reset_querycache():
    globals()['QueryCache'] = {}
    globals()['QueryCacheMapping'] = {}
    refresh_DynamicNode()

def start_thread(Object, Args):
    Failed = False

    while True:
        try:
            start_new_thread(Object, Args)

            if Failed:
                xbmc.log(f"EMBY.helper.utils: start_thread continue: {Object.__name__}", 2) # LOGWARNING

            break
        except RuntimeError as error:
            Failed = True
            xbmc.log(f"EMBY.helper.utils: start_thread: {Object.__name__}, Error: {error}", 2) # LOGWARNING

            if sleep(1):
                xbmc.log("EMBY.helper.utils: start_thread: shutdown", 2) # LOGWARNING
                break

def release_lock(Lock):
    try:
        Lock.release()
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: Release PlayerBusy lock {Error}", 2) # LOGWARN

def close_busyDialog():
    if BusyDialogClose and xbmc.getCondVisibility("System.HasActiveModalDialog"):
        xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

def ActivateWindow(WindowId, Path, DialogClose=False):
    xbmc.sleep(10) # Kodi needs time to process

    # Wait for modal close
    while xbmc.getCondVisibility("System.HasActiveModalDialog"):
        if DialogClose:
            xbmc.executebuiltin('Dialog.Close(all,true)')

        xbmc.sleep(10) # Kodi needs time to process

    if Path:
        SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "{WindowId}", "parameters": ["{Path}", "return"]}}}}')
    else:
        SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "{WindowId}"}}}}')

def refresh_DynamicNode():
    MenuPath = xbmc.getInfoLabel('Container.FolderPath')

    if MenuPath.startswith("plugin://plugin.service.emby-next-gen/") and "mode=browse" in MenuPath.lower():
        xbmc.log("Emby.hooks.utils: UserDataChanged refresh dynamic nodes", 1) # LOGINFO
        xbmc.executebuiltin('Container.Refresh')
        xbmc.sleep(10) # Kodi needs time to process

def get_EmbyId_ServerId_by_Fake_KodiId(KodiId):
    if KodiId > 1000000000: # Dynamic node item
        ServerIndex = int(str(KodiId)[1])
        EmbyId = int(str(KodiId)[2:])
        ServerId = EmbyServerIds[ServerIndex]
        return EmbyId, ServerId

    return 0, ""

def get_digits(Text):
    Temp = ''.join(i for i in Text if i.isdigit())

    if Temp:
        return int(Temp)

    return 0

# Detect if Kodi's database scans are active
get_scans()

# Make folders
mkDir(FolderAddonUserdata)
mkDir(FolderEmbyTemp)
mkDir(FolderUserdataThumbnails)

# Init settings
InitSettings()

# Find Kodi's database files
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0, 'epg': "", 'epg-version': 0, 'tv': "", 'tv-version': 0, 'addon': "", 'addon-version': 0}
_, DatabaseFilesFound = xbmcvfs.listdir("special://profile/Database/")
FontPath = xbmcvfs.translatePath("special://home/addons/plugin.service.emby-next-gen/resources/font/LiberationSans-Bold.ttf")
noimagejpg = readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/noimage.jpg")
set_settings_bool('artworkcacheenable', True)

for DatabaseFileFound in DatabaseFilesFound:
    if not DatabaseFileFound.endswith('-wal') and not DatabaseFileFound.endswith('-shm') and not DatabaseFileFound.endswith('db-journal'):
        if DatabaseFileFound.startswith('Textures'):
            Version = get_digits(DatabaseFileFound)

            if Version > DatabaseFiles['texture-version']:
                DatabaseFiles['texture'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['texture-version'] = Version
        elif DatabaseFileFound.startswith('MyMusic'):
            Version = get_digits(DatabaseFileFound)

            if Version > DatabaseFiles['music-version']:
                DatabaseFiles['music'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['music-version'] = Version
        elif DatabaseFileFound.startswith('MyVideos'):
            Version = get_digits(DatabaseFileFound)

            if Version > DatabaseFiles['video-version']:
                DatabaseFiles['video'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['video-version'] = Version
        elif DatabaseFileFound.startswith('Epg'):
            Version = get_digits(DatabaseFileFound)

            if Version > DatabaseFiles['epg-version']:
                DatabaseFiles['epg'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['epg-version'] = Version
        elif DatabaseFileFound.startswith('TV'):
            Version = int(''.join(i for i in DatabaseFileFound if i.isdigit()))

            if Version > DatabaseFiles['tv-version']:
                DatabaseFiles['tv'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['tv-version'] = Version
        elif DatabaseFileFound.startswith('Addons'):
            Version = int(''.join(i for i in DatabaseFileFound if i.isdigit()))

            if Version > DatabaseFiles['addon-version']:
                DatabaseFiles['addon'] = xbmcvfs.translatePath(f"special://profile/Database/{DatabaseFileFound}")
                DatabaseFiles['addon-version'] = Version

# Load playback version selection
Result = SendJson('{"jsonrpc":"2.0","method":"Settings.GetSettingValue","params":{"setting": "myvideos.selectdefaultversion"},"id":1}', True).get("result", {})

if Result:
    SelectDefaultVideoversion = Result.get("value", {})

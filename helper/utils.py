import threading
import os
import json
import re
from urllib.parse import quote, unquote, urlsplit, urlparse, parse_qs
from datetime import datetime, timezone

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

Addon = xbmcaddon.Addon("plugin.service.emby-next-gen")
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
CustomDialogParameters = (Addon.getAddonInfo('path'), "default", "1080i")
WidgetsRefreshLock = threading.Lock()
MappingIds = {"Trailer": "999999987", 'Season': "999999989", 'Series': "999999990", 'MusicAlbum': "999999991", 'MusicGenre': "999999992", "Studio": "999999994", "Tag": "999999993", "Genre": "999999995", "MusicArtist": "999999996"}
MappingIdsListKeys = list(MappingIds.keys())
EmbyTypeMapping = {"Person": "actor", "Video": "movie", "Movie": "movie", "Series": "tvshow", "Season": "season", "Episode": "episode", "Audio": "song", "MusicAlbum": "album", "MusicArtist": "artist", "Genre": "genre", "MusicGenre": "genre", "Tag": "tag" , "Studio": "studio" , "BoxSet": "set", "Folder": "folder", "MusicVideo": "musicvideo", "Playlist": "Playlist", "Trailer": "video", "PhotoAlbum": "folder", "Photo": "photo"}
KodiTypeMapping = {"actor": "Person", "tvshow": "Series", "season": "Season", "episode": "Episode", "song": "Audio", "album": "MusicAlbum", "artist": "MusicArtist", "genre": "Genre", "tag": "Tag", "studio": "Studio" , "set": "BoxSet", "musicvideo": "MusicVideo", "playlist": "Playlist", "movie": "Movie", "videoversion": "Video", "video": "Video"}
ContentTypes = {"Movie": "video", "Series": "video", "Season": "video", "Episode": "video", "Genre": "video", "Video": "video", "MusicVideo": "video", "Trailer": "video", "Audio": "audio", "MusicAlbum": "audio", "Photo": "image", "audio": "audio", "podcasts": "audio", "audiobooks": "audio", "playlistsaudio": "audio", "homephotos": "image", "playlistsvideo": "video", "rootvideo": "video", "rootaudio": "audio", "rootimage": "image", "music": "audio", "homevideos": "video", "musicvideos": "video", "movies": "video", "tvshows": "video", "mixedvideo": "video", "channels": "video", "trailers": "video", "videos": "video", "TvChannel": "video", "Person": "video", "Channel": "video", "Audios": "audio", "Videos": "video"}
icon = ""
ForbiddenCharecters = {}

for Char in ("/", "<", ">", ":", '"', "\\", "|", "?", "*", " ", "&", chr(0), chr(1), chr(2), chr(3), chr(4), chr(5), chr(6), chr(7), chr(8), chr(9), chr(10), chr(11), chr(12), chr(13), chr(14), chr(15), chr(16), chr(17), chr(18), chr(19), chr(20), chr(21), chr(22), chr(23), chr(24), chr(25), chr(26), chr(27), chr(28), chr(29), chr(30), chr(31)):
    CharId = ord(Char)
    ForbiddenCharecters[CharId] = "_"

ENC_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"}
ENC_RE = re.compile(r'[&<>"\']')
DEC_MAP = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": "\"", "&apos;": "'"}
DEC_RE = re.compile(r"&amp;|&lt;|&gt;|&quot;|&apos;")
AutoplaySettings = []
FilesizeSuffixes = ('B', 'KB', 'MB', 'GB', 'TB')
EmbyServers = {}
EmbyServersBan = set()
EmbyServerIds = []
UpcomingLastQueryTicks = 0
RemoteMode = False
ItemSkipUpdate = []
MinimumVersion = "12.5.0"
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
verifyKodiCompanion = False
SyncLiveTvOnEvents = False
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
PauseSyncDuringPlaybackStateChange = True
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
theme_enable_audio = True
theme_enable_video = False
theme_fade_in = 1
theme_fade_out = 1
theme_enable_homescreen = True
theme_enable_viewseason = True
theme_enable_viewepisode = True
theme_enable_viewseries = True
theme_enable_viewmovie = True
theme_delay = 0.1
theme_priority = "audio"
theme_ThemeBySkipIntro = False
theme_ThemeByContent = False
theme_ThemeByContentDuration = 20
trailer_remote_options = {}
trailer_playback = 2
trailer_local_folder = True
trailer_local = True
DownloadPath = "special://profile/addon_data/plugin.service.emby-next-gen/"
FolderAddonUserdata = "special://profile/addon_data/plugin.service.emby-next-gen/"
FolderEmbyTemp = "special://profile/addon_data/plugin.service.emby-next-gen/temp/"
FolderUserdataThumbnails = "special://profile/Thumbnails/"
PlaylistPathMusic = "special://profile/playlists/music/"
PlaylistPathVideo = "special://profile/playlists/video/"
SystemShutdown = False
SyncPause = {}  # keys: playing, kodi_sleep, embyserverID, kodi_rw, priority (thread with higher priority needs access)
SyncPauseCondition = threading.Condition(threading.Lock())
SettingsChangedCondition = threading.Condition(threading.Lock())
EmbyServerOnlineCondition = threading.Condition(threading.Lock())
WidgetRefresh = {"video": False, "music": False}
BoxSetsToTags = False
MovieToSeries = True
SyncFavorites = False
Dialog = xbmcgui.Dialog()
WizardCompleted = True
LiveTVEnabled = False
AssignEpisodePostersToTVShowPoster = False
sslverify = False
AddonModePath = "dav://127.0.0.1:57342/"
TranslationsCached = {}
ScreenResolution = (1920, 1080)
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
followhttp = True
followhttptimeout = 5
WebserviceWorkers = 10
BusyDialogClose = True
ArtworkCacheIncremental = False
LinkMusicVideos = True
DebugLog = False
NativeChapterDownload = True
SyncLockCondition = threading.Condition(threading.Lock())
SyncLock = True
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0, 'epg': "", 'epg-version': 0, 'tv': "", 'tv-version': 0, 'addon': "", 'addon-version': 0}
Tos = "CS5, EF (Expedited Forwarding)"
IconExtensions = ("jpg", "png", "gif", "webp", "apng", "avif", "svg", "ukn")
FontPath = xbmcvfs.translatePath("special://home/addons/plugin.service.emby-next-gen/resources/font/LiberationSans-Bold.ttf")
noimagejpg = b''
NextGenOnline = threading.Event()
ProgressBars = [True, {}] # [ProgressbarsEnabled, {Header, Message, Value, ProgressBar}]
ProgressBarsLock = threading.Lock()
JsonId = 1
ArtworkDelete = set()
ArtworkDeleteLock = threading.Lock()

# Kodi hash
CRC_TABLE = []

for ValueHex in range(256):
    CRC = ValueHex << 24

    for _ in range(8):
        if CRC & 0x80000000:
            CRC = (CRC << 1) ^ 0x04C11DB7
        else:
            CRC <<= 1

        CRC &= 0xffffffff

    CRC_TABLE.append(CRC)


def kodi_hash(Path):
    Path = Path.lower()
    crc = 0xffffffff

    for val in Path.encode("utf-8"):
        crc = ((crc << 8) & 0xffffffff) ^ CRC_TABLE[((crc >> 24) ^ val) & 0xff]

    return f"{crc:08x}"

# JsonRPC
def SendJson(Method, Params, ForceBreak):
    global JsonId
    JsonId += 1
    LogSend = False

    # Keep " escapes but escape \
    Params = Params.replace('\\"', "KEEPESPACES") # escape backslashes
    Params = Params.replace("\\", "\\\\") # escape backslashes
    Params = Params.replace('KEEPESPACES', '\\"') # escape backslashes

    if Params:
        JsonString = f'{{"jsonrpc": "2.0", "id": {JsonId}, "method": "{Method}", "params": {Params}}}'
    else:
        JsonString = f'{{"jsonrpc": "2.0", "id": {JsonId}, "method": "{Method}"}}'

    for Index in range(55): # retry -> timeout 10 seconds
        Ret = xbmc.executeJSONRPC(JsonString)

        if not Ret: # Valid but not correct Kodi return value -> Kodi bug
            if DebugLog: xbmc.log(f"Emby.helper.jsonrpc: Json no response: {JsonString}", 2) # LOGWARNING
            return {}

        Ret = json.loads(Ret)

        if not Ret.get("error", False):
            if DebugLog: xbmc.log(f"Emby.helper.jsonrpc (DEBUG): Json response: {JsonString} / {Ret}", 1) # LOGDEBUG
            return Ret

        if DebugLog: xbmc.log(f"Emby.helper.jsonrpc: Json error: {JsonString} / {Ret}", 3) # LOGERROR

        if ForceBreak:
            return {}

        if not LogSend:
            if DebugLog: xbmc.log(f"Emby.helper.jsonrpc: Json error, retry: {JsonString}", 2) # LOGWARNING
            LogSend = True

        if Index < 50: # 5 seconds rapidly
            if sleep(0.1):
                return {}
        else: # after 5 seconds delay cycle by 1 second for the last 5 seconds
            if sleep(1):
                return {}

    return {}

# Progress bars
def create_ProgressBar(TaskId, Header, Message):
    with SafeLock(ProgressBarsLock):
        if TaskId not in ProgressBars[1]:
            ProgressBars[1][TaskId] = [Header, Message, 0, None]

        if ProgressBars[0] and not ProgressBars[1][TaskId][3]: # Progress bars enabled
            ProgressBars[1][TaskId][3] = xbmcgui.DialogProgressBG()
            ProgressBars[1][TaskId][3].create(ProgressBars[1][TaskId][0], ProgressBars[1][TaskId][1])

def update_ProgressBar(TaskId, Value, Header, Message):
    with SafeLock(ProgressBarsLock):
        if TaskId in ProgressBars[1]:
            Value = int(Value)
            ProgressBars[1][TaskId][0] = Header
            ProgressBars[1][TaskId][1] = Message
            ProgressBars[1][TaskId][2] = Value

            if ProgressBars[1][TaskId][3]:
                ProgressBars[1][TaskId][3].update(Value, ProgressBars[1][TaskId][0], ProgressBars[1][TaskId][1])

def close_ProgressBar(TaskId):
    with SafeLock(ProgressBarsLock):
        if TaskId in ProgressBars[1]:
            if ProgressBars[1][TaskId][3]:
                ProgressBars[1][TaskId][3].close()

            del ProgressBars[1][TaskId]

def closeall_ProgressBar():
    with SafeLock(ProgressBarsLock):
        ProgressBars[0] = False

        for ProgressBar in ProgressBars[1].values():
            if ProgressBar[3]:
                ProgressBar[3].close()

            ProgressBar[3] = None

def openall_ProgressBar():
    with SafeLock(ProgressBarsLock):
        ProgressBars[0] = True

        for ProgressBar in ProgressBars[1].values():
            ProgressBar[3] = xbmcgui.DialogProgressBG()
            ProgressBar[3].create(ProgressBar[0], ProgressBar[1])
            ProgressBar[3].update(ProgressBar[2], ProgressBar[0], ProgressBar[1])

# Kodi workaround as it has flaws with blocking code
class SafeLock:
    __slots__ = ['lock']

    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        while not self.lock.acquire(timeout=0.1):
            pass

    def __exit__(self, *args):
        self.lock.release()

def unset_SyncLock():
    global SyncLock

    with SafeLock(SyncLockCondition):
        if not RemoteMode:
            SyncLock = False
            SyncLockCondition.notify_all()

def set_SyncLock():
    global SyncLock

    with SafeLock(SyncLockCondition):
        SyncLock = True
        SyncLockCondition.notify_all()

# Run workers in specific order
def RunSyncJobsAsync():
    global SyncLock
    if DebugLog: xbmc.log("EMBY.helper.utils (DEBUG): THREAD: --->[ sync worker ]", 1) # LOGDEBUG

    while True:
        if DebugLog: xbmc.log("EMBY.helper.utils (DEBUG): CONDITION: --->[ SyncLockCondition ]", 1) # LOGDEBUG

        with SafeLock(SyncLockCondition): # threading.Condition required (not threading.event) as multiple workers can access this module
            while SyncLock:
                SyncLockCondition.wait(timeout=0.1)

                if SystemShutdown:
                    if DebugLog:
                        xbmc.log("EMBY.helper.utils (DEBUG): THREAD: ---<[ sync worker ]", 1) # LOGDEBUG
                        xbmc.log("EMBY.helper.utils (DEBUG): CONDITION: ---<[ SyncLockCondition ]", 1) # LOGDEBUG

                    return

            if DebugLog: xbmc.log("EMBY.helper.utils (DEBUG): CONDITION: ---<[ SyncLockCondition ]", 1) # LOGDEBUG
            SyncLock = True

        for EmbyServer in list(EmbyServers.values()):
            if not EmbyServer.library.Worker_is_paused("RunSyncJobsAsync"):
                xbmc.log("EMBY.helper.utils: Run async jobs", 1) # LOGINFO
                EmbyServer.library.RunJobs(True, False)

def update_SyncPause(Key, Value):
    with SafeLock(SyncPauseCondition):
        SyncPause[Key] = Value
        SyncPauseCondition.notify_all()

def clear_SyncPause():
    global SyncPause

    with SafeLock(SyncPauseCondition):
        SyncPause = {}
        SyncPauseCondition.notify_all()

def refresh_widgets(isVideo):
    with SafeLock(WidgetsRefreshLock):
        if isVideo:
            if WidgetRefresh['video']:
                return

            if DebugLog: xbmc.log("EMBY.helper.utils: Refresh video started", 1)
            WidgetRefresh['video'] = True
            xbmc.executebuiltin('UpdateLibrary(video,/EMBY_widget_refresh_trigger_video/,false)')
        else:
            if WidgetRefresh['music']:
                return

            if DebugLog: xbmc.log("EMBY.helper.utils: Refresh music started", 1)
            WidgetRefresh['music'] = True
            xbmc.executebuiltin('UpdateLibrary(music,/EMBY_widget_refresh_trigger_music/,true)')

# image:// Kodi uses the jobqueue for http calls "async" -> prevents blocking stat requests.
# image://specialtype@ forces Kodi to disable autorefresh cache write the path with image://specialtype@ prefix into the texture.db. Otherwise it would be unquoted to http://127.0.0.1 and written into texture.db
# from xbmc code: image://[type@]<url_encoded_path>?options
# Kodi 21 does not support custom specialtypes
def image_url_encode(url, Filename):
    if DatabaseFiles["texture-version"] <= 13: # Kodi 21
        url = f"{url}|redirect-limit=1000&failonerror=false"
        return f"image://epg@{quote(url, safe='')}/{Filename}"

    url = f"{url}|redirect-limit=1000&failonerror=false"
    return f"image://emby@{quote(url, safe='')}/{Filename}"

def image_url_decode(url, KeepUrlParams=False):
    imagePath, _ = unquote(url).rsplit("/", 1) # imagePath, urlFilename

    if not KeepUrlParams:
        imagePath = imagePath.replace("|redirect-limit=1000&failonerror=false", "")

    if DatabaseFiles["texture-version"] <= 13: # Kodi 21
        return imagePath.replace("image://epg@", "")

    return imagePath.replace("image://emby@", "")

def set_Artwork_Overlay(Text, ImageUrl):
    OverlayText = image_text_encode(Text)

    if ImageUrl:
        Temp = ImageUrl.split("-")
        return f"{'-'.join(Temp[:5])}-{OverlayText}-{'-'.join(Temp[6:])}"

    return ""

# url encode text
def image_text_encode(Text):
    return quote(quote(Text.replace("-", " "), safe=''))

# url decode text
def image_text_decode(Text):
    return unquote(unquote(Text))

def get_MimeType(Path):
    if not Path:
        return "", "unknown"

    p = Path.lower().replace("|redirect-limit=1000&failonerror=false", "").replace("|seekable=0&failonerror=false&verifypeer=false", "").replace("%7Credirect-limit%3D1000%26failonerror%3Dfalse", "")

    if p.endswith(".jpg") or p.endswith(".jpeg") or p.endswith(".jpe") or p.endswith(".jfif"):
        return "image/jpeg", "jpg"

    if p.endswith(".png"):
        return "image/png", "png"

    if p.endswith(".mp4") or p.endswith(".m4v"):
        return "video/mp4", "mp4"

    if p.endswith(".mp3"):
        return "audio/mpeg", "mp3"

    if p.endswith(".flac"):
        return "audio/flac", "flac"

    if p.endswith(".mkv"):
        return "video/x-matroska", "mkv"

    if p.endswith(".avi"):
        return "video/x-msvideo", "avi"

    if p.endswith(".bmp"):
        return "image/bmp", "bmp"

    if p.endswith(".ts") or p.endswith(".m2ts") or p.endswith(".mts"):
        return "video/mp2t", "ts"

    if p.endswith(".mpg") or p.endswith(".mpeg") or p.endswith(".mpe"):
        return "video/mpeg", "mpg"

    if p.endswith(".strm"):
        return "text/plain", "strm"

    if p.endswith(".gif"):
        return "image/gif", "gif"

    if p.endswith(".m3u") or p.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl", "m3u8"

    if p.endswith(".webm"):
        return "video/webm", "webm"

    if p.endswith(".mov"):
        return "video/quicktime", "mov"

    if p.endswith(".wmv"):
        return "video/x-ms-wmv", "wmv"

    if p.endswith(".ogv"):
        return "video/ogg", "ogv"

    if p.endswith(".3gp"):
        return "video/3gpp", "3gp"

    if p.endswith(".flv"):
        return "video/x-flv", "flv"

    if p.endswith(".mxf"):
        return "application/mxf", "mxf"

    if p.endswith(".vob"):
        return "video/dvd", "vob"

    if p.endswith(".asf"):
        return "video/x-ms-asf", "asf"

    if p.endswith(".pls"):
        return "audio/x-scpls", "pls"

    if p.endswith(".webp"):
        return "image/webp", "webp"

    if p.endswith(".avif"):
        return "image/avif", "avif"

    if p.endswith(".heic") or p.endswith(".heif"):
        return "image/heic", "heic"

    if p.endswith(".apng"):
        return "image/apng", "apng"

    if p.endswith(".svg") or p.endswith(".svgz"):
        return "image/svg+xml", "svg"

    if p.endswith(".ico"):
        return "image/vnd.microsoft.icon", "ico"

    if p.endswith(".tiff") or p.endswith(".tif"):
        return "image/tiff", "tiff"

    if p.endswith(".psd"):
        return "image/vnd.adobe.photoshop", "psd"

    if p.endswith(".ai") or p.endswith(".eps"):
        return "application/postscript", "ai"

    if p.endswith(".dng"):
        return "image/x-adobe-dng", "dng"

    if p.endswith(".cr2") or p.endswith(".cr3") or p.endswith(".crw"):
        return "image/x-canon-raw", "crw"

    if p.endswith(".nef") or p.endswith(".nrw"):
        return "image/x-nikon-nef", "nrw"

    if p.endswith(".arw") or p.endswith(".srf") or p.endswith(".sr2"):
        return "image/x-sony-arw", "arw"

    if p.endswith(".orf"):
        return "image/x-olympus-orf", "orf"

    if p.endswith(".raf"):
        return "image/x-fuji-raf", "raf"

    if p.endswith(".rw2"):
        return "image/x-panasonic-raw", "rw2"

    if p.endswith(".raw"):
        return "image/x-dcraw", "raw"

    if p.endswith(".jpx") or p.endswith(".jp2"):
        return "image/jp2", "jp2"

    if p.endswith(".tga"):
        return "image/x-tga", "tga"

    if p.endswith(".pcx"):
        return "image/x-pcx", "pcx"

    if p.endswith(".m4a") or p.endswith(".m4b"):
        return "audio/mp4", "m4a"

    if p.endswith(".wav"):
        return "audio/wav", "wav"

    if p.endswith(".aac"):
        return "audio/aac", "aac"

    if p.endswith(".ogg") or p.endswith(".oga"):
        return "audio/ogg", "ogg"

    if p.endswith(".opus"):
        return "audio/opus", "opus"

    if p.endswith(".wma"):
        return "audio/x-ms-wma", "wma"

    if p.endswith(".aiff") or p.endswith(".aif") or p.endswith(".aifc"):
        return "audio/x-aiff", "aiff"

    if p.endswith(".ac3"):
        return "audio/ac3", "ac3"

    if p.endswith(".dts"):
        return "audio/vnd.dts", "dts"

    if p.endswith(".amr"):
        return "audio/amr", "amr"

    if p.endswith(".mp2"):
        return "audio/mpeg", "mp2"

    if p.endswith(".dsf"):
        return "audio/x-dsf", "dsf"

    if p.endswith(".dff"):
        return "audio/x-dff", "dff"

    if p.endswith(".ape"):
        return "audio/x-ape", "ape"

    if p.endswith(".wv"):
        return "audio/x-wavpack", "wv"

    if p.endswith(".tta"):
        return "audio/x-tta", "tta"

    if p.endswith(".mpc"):
        return "audio/x-musepack", "mpc"

    if p.endswith(".shn"):
        return "audio/x-shn", "shn"

    if p.endswith(".mka"):
        return "audio/x-matroska", "mka"

    if p.endswith(".mid") or p.endswith(".midi"):
        return "audio/midi", "midi"

    if p.endswith(".mod"):
        return "audio/x-mod", "mod"

    if p.endswith(".it"):
        return "audio/x-it", "it"

    if p.endswith(".s3m"):
        return "audio/x-s3m", "s3m"

    if p.endswith(".xm"):
        return "audio/x-xm", "xm"

    return "", "unknown"

def image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText, Format="jpg"):
    if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Add image text overlay: {EmbyID}", 1) # LOGDEBUG

    if ImageTag == "noimage":
        BinaryData = noimagejpg
        ContentType = "image/jpeg"
        FileExtension = "jpg"
    else:
        BinaryData, ContentType, FileExtension = EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag, False, Format)

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
        if DebugLog: xbmc.log(f"EMBY.helper.utils: Pillow issue: {Error}", 3) # LOGERROR
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
        if DebugLog: xbmc.log(f"EMBY.helper.utils: Pillow issue (getbox): {Error}", 3) # LOGERROR
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
def download_Icon(ItemId, ImageTag, ServerId, NodeName, Force, Format="jpg"):
    ItemId = str(ItemId).replace(MappingIds['Tag'], '') # Collection as Tags (Item Id)

    for IconExtension in IconExtensions:
        FileExists = f"{FolderEmbyTemp}{ServerId}-{ItemId}.{IconExtension}"
        Found = xbmcvfs.exists(FileExists)

        if Found:
            break

    if not Found or Force:
        if Found: # Delete exiting file (forced)
            delFile(FileExists)
            Hash = kodi_hash(FileExists)
            PathBase = f"{FolderUserdataThumbnails}{Hash[0]}/{Hash}"

            for ext in ("jpg", "png"):
                PathFile = f"{PathBase}.{ext}"

                if xbmcvfs.exists(PathFile):
                    delFile(PathFile)
                    break

        BinaryData, _, FileExtension = image_overlay(ImageTag, ServerId, ItemId, "Primary", 0, NodeName, Format)
        IconFile = f"{FolderEmbyTemp}{ServerId}-{ItemId}.{FileExtension}"
        writeFile(IconFile, BinaryData)
    else:
        IconFile = FileExists

    return IconFile

def restart_kodi():
    global SystemShutdown
    if DebugLog: xbmc.log("EMBY.helper.utils: Restart Kodi", 1) # LOGINFO
    SystemShutdown = True
    xbmc.executebuiltin('RestartApp')

def sleep(Seconds):
    if Seconds < 0.1:
        if SystemShutdown:
            return True

        xbmc.sleep(int(Seconds * 1000))
    else:
        for _ in range(int(Seconds * 10)):
            if SystemShutdown:
                return True

            xbmc.sleep(100)

    return False

# Delete objects from kodi cache
def delFolder(path, Pattern=""):
    if DebugLog: xbmc.log("EMBY.helper.utils (DEBUG): --[ delete folder ]", 1) # LOGDEBUG
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

    if DebugLog: xbmc.log(f"EMBY.helper.utils: DELETE {path}", 2) # LOGWARNING

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
        if DebugLog: xbmc.log(f"EMBY.helper.utils: Delete folder issue: {Error} / {Path}", 3) # LOGERROR

def mkDir(Path):
    if xbmcvfs.exists(Path):
        return True

    try:
        xbmcvfs.mkdirs(Path)
        return True
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: mkDir: {Error}", 3) # LOGERROR

    return False

def delFile(Path):
    try:
        xbmcvfs.delete(Path)
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: delFile: {Error}", 3) # LOGERROR

def copyFile(SourcePath, DestinationPath):
    if xbmcvfs.exists(DestinationPath):
        if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): copy: File exists: {SourcePath} to {DestinationPath}", 1) # LOGDEBUG
        return

    try:
        success = xbmcvfs.copy(SourcePath, DestinationPath)

        if not success:
            if DebugLog: xbmc.log(f"EMBY.helper.utils: sucess: {success} copy: {SourcePath} to {DestinationPath}", 3) # LOGERROR
        else:
            if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): sucess: {success} copy: {SourcePath} to {DestinationPath}", 1) # LOGDEBUG
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: copy issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

def renameFile(SourcePath, DestinationPath):
    if xbmcvfs.exists(DestinationPath):
        if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): rename: File exists: {SourcePath} to {DestinationPath}", 1) # LOGDEBUG
        return True

    try:
        success = xbmcvfs.rename(SourcePath, DestinationPath)

        if not success:
            if DebugLog: xbmc.log(f"EMBY.helper.utils: sucess: {success} rename: {SourcePath} to {DestinationPath}", 3) # LOGERROR
        else:
            if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): sucess: {success} rename: {SourcePath} to {DestinationPath}", 1) # LOGDEBUG

        return success
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: rename issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

    return False

def readFileBinary(Path):
    try:
        infile = xbmcvfs.File(Path)
        data = infile.readBytes()
        infile.close()
        return data
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: readFileBinary ({Path}): {Error}", 2) # LOGWARNING

    return b""

def readFileString(Path):
    try:
        infile = xbmcvfs.File(Path)
        data = infile.read()
        infile.close()
        return data
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: readFileString ({Path}): {Error}", 2) # LOGWARNING

    return ""

def writeFile(Path, Data):
    try:
        outfile = xbmcvfs.File(Path, 'w')
        outfile.write(Data)
        outfile.close()
    except Exception as Error:
        if DebugLog: xbmc.log(f"EMBY.helper.utils: writeFile ({Path}): {Error}", 2) # LOGWARNING

def getFreeSpace(Path):
    if verifyFreeSpace:
        try:
            Path = xbmcvfs.translatePath(Path)
            space = os.statvfs(Path)
            free = space.f_bavail * space.f_frsize / 1024
            return free
        except Exception as Error: # not suported by Windows
            if DebugLog: xbmc.log(f"EMBY.helper.utils: getFreeSpace: {Error}", 2) # LOGWARNING
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

    Url = urlsplit(ConnectionString)
    Scheme = Url.scheme
    Hostname = Url.hostname

    if Url.port:
        Port = Url.port
    elif Scheme == "https":
        Port = 443
    else:
        Port = 80

    SubUrl = f"/{Url.path.strip('/')}/".replace("//", "/")
    if DebugLog: xbmc.log(f"Emby.helper.utils (DEBUG): get_url_info: ConnectionString='{ConnectionString}' Scheme='{Scheme}' Hostname='{Hostname}' SubUrl='{SubUrl}' Port='{Port}'", 1) # LOGDEBUG
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
    if not isinstance(local_time, str) or not local_time:
        return ""

    if len(local_time) < 10 or local_time[4] != '-' or local_time[7] != '-':
        return ""

    if local_time.endswith('Z'):
        local_time = local_time[:-1] + "+00:00"

    dt = datetime.fromisoformat(local_time)
    utc_time = dt.astimezone(timezone.utc)
    return utc_time.strftime('%Y-%m-%dT%H:%M:%SZ')

def get_unix_ticks(Date):
    try:
        return int(datetime.fromisoformat(Date).timestamp())
    except:
        return 0

# Convert the gmt datetime to local
def convert_to_local(date_input, DateOnly, YearOnly):
    if not date_input or str(date_input) == "0":
        return "0"

    try:
        if isinstance(date_input, (int, float)):
            dt = datetime(date_input, 1, 1, tzinfo=timezone.utc)
        elif isinstance(date_input, str):
            if len(date_input) < 10:
                return "0"

            Zulu = False

            if date_input.endswith("Z"):
                Zulu = True
                date_input = date_input[:-1]

            Pos = date_input.find(".")

            if Pos != -1:
                date_input = date_input[:Pos]

            if Zulu:
                date_input += "+00:00"

            dt = datetime.fromisoformat(date_input)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = date_input

        if not 100 <= dt.year <= 9000:
            xbmc.log(f"Emby.helper.utils: Year out of range: {dt.year}", 2) # LOGWARNING
            return "0"

        local_dt = dt.astimezone(None)

        if YearOnly:
            return local_dt.year

        if DateOnly:
            return local_dt.strftime('%Y-%m-%d')

        return local_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: convert_to_local Error: {date_input} / {Error}", 3) # LOGERROR
        return "0"

def Translate(Id):
    if Id in TranslationsCached:
        return TranslationsCached[Id]

    result = Addon.getLocalizedString(Id)

    if not result:
        result = xbmc.getLocalizedString(Id)

    TranslationsCached[Id] = result
    return result

def valid_Filename(Filename):
    Filename = decode_XML(Filename)

    if len(Filename) > 150:
        Filename = Filename[:150]
        if DebugLog: xbmc.log(f"Emby.helper.utils: Filename too long -> cut: {Filename}", 2) # LOGWARNING

    return Filename.translate(ForbiddenCharecters)

def get_Filename(Path, NativeMode):
    Separator = get_Path_Seperator(Path)
    Pos = Path.rfind(Separator)
    Filename = Path[Pos + 1:]

    if not NativeMode and webservicemode != "pathsubstitution":
        Filename = quote(Filename)

    return Filename

def SizeToText(FileSize):
    Index = 0

    while FileSize >= 1024 and Index < 4:
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
    if DebugLog: xbmc.log(f"EMBY.helper.utils: Copied {PathSource}", 1) # LOGINFO

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
                if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Filecopy filtered by fileend: {Filename}", 1) # LOGDEBUG
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
    global ScreenResolution
    global AddonModePath
    global device_name
    global icon
    global displayMessage
    global newContentTime
    global theme_delay
    global theme_fade_in
    global theme_fade_out

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
    load_settings('theme_priority')
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
    load_settings_int('theme_fade_in')
    load_settings_int('theme_fade_out')
    load_settings_int('theme_delay')
    load_settings_int('theme_ThemeByContentDuration')
    load_settings_int('trailer_playback')
    load_settings_bool('theme_ThemeBySkipIntro')
    load_settings_bool('theme_ThemeByContent')
    load_settings_bool('DebugLog')
    load_settings_bool('trailer_local_folder')
    load_settings_bool('trailer_local')
    load_settings_bool('theme_enable_audio')
    load_settings_bool('theme_enable_video')
    load_settings_bool('theme_enable_homescreen')
    load_settings_bool('theme_enable_viewseason')
    load_settings_bool('theme_enable_viewepisode')
    load_settings_bool('theme_enable_viewseries')
    load_settings_bool('theme_enable_viewmovie')
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
    load_settings_bool('NativeChapterDownload')
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
    load_settings_bool('artworkcacheenable')
    load_settings_bool('PauseSyncDuringPlaybackStateChange')
    load_settings_json('trailer_remote_options')

    if ArtworkLimitations:
        ScreenResolution = (int(xbmc.getInfoLabel('System.ScreenWidth')), int(xbmc.getInfoLabel('System.ScreenHeight')))
        if DebugLog: xbmc.log(f"EMBY.helper.utils: Screen resolution: {ScreenResolution}", 1) # LOGINFO

    if webservicemode == "pathsubstitution":
        AddonModePath = "/emby_addon_mode/"
    elif webservicemode == "webdav":
        AddonModePath = "dav://127.0.0.1:57342/"
    else:
        AddonModePath = "http://127.0.0.1:57342/"

    if not deviceNameOpt:
        device_name = xbmc.getInfoLabel('System.FriendlyName')
    else:
        device_name = deviceName.replace("/", "-")

    if not device_name:
        device_name = "Kodi"
    else:
        device_name = quote(device_name) # url encode

    # Animated icons
    NewIcon = ""

    if animateicon:
        if icon and icon != "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif":
            NewIcon = "animated"

        icon = "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif"
    else:
        if icon and icon != "special://home/addons/plugin.service.emby-next-gen/resources/icon.png":
            NewIcon = "static"

        icon = "special://home/addons/plugin.service.emby-next-gen/resources/icon.png"

    if NewIcon:
        for PluginId in ("video", "image", "audio", "service"):
            if DebugLog: xbmc.log("EMBY.helper.utils (DEBUG): Toggle icon", 1) # LOGINFO
            AddonXml = readFileString(f"special://home/addons/plugin.{PluginId}.emby-next-gen/addon.xml")

            if NewIcon == "static":
                AddonXml = AddonXml.replace("resources/icon-animated.gif", "resources/icon.png")
            else:
                AddonXml = AddonXml.replace("resources/icon.png", "resources/icon-animated.gif")

            writeFile(f"special://home/addons/plugin.{PluginId}.emby-next-gen/addon.xml", AddonXml)

    displayMessage *= 1000
    newContentTime *= 1000
    theme_delay /= 10
    theme_fade_in /= 100
    theme_fade_out /= 100
    update_mode_settings()
    xbmc.executebuiltin(f'SetProperty(EmbyDelete,{enableContextDelete},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyRemote,{enableContextRemoteOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyDownload,{enableContextDownloadOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyFavourite,{enableContextFavouriteOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbySpecials,{enableContextSpecialsOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyRecording,{enableContextRecordingOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyRefresh,{enableContextRefreshOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyGoto,{enableContextGotoOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbySimilar,{enableContextSimilarOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbySettings,{enableContextSettingsOptions},10000)')
    xbmc.executebuiltin(f'SetProperty(EmbyPlayRandom,{enableContextPlayRandom},10000)')

    with SafeLock(SettingsChangedCondition):
        SettingsChangedCondition.notify_all()

def update_mode_settings():
    # disable file metadata extraction
    if not useDirectPaths:
        SendJson("Settings.SetSettingValue", '{"setting":"myvideos.extractflags","value":false}', True)
#        SendJson("Settings.SetSettingValue", '{"setting":"myvideos.extractthumb","value":true}', True)
        SendJson("Settings.SetSettingValue", '{"setting":"myvideos.usetags","value":false}', True)
        SendJson("Settings.SetSettingValue", '{"setting":"musicfiles.usetags","value":false}', True)
        SendJson("Settings.SetSettingValue", '{"setting":"musicfiles.findremotethumbs","value":false}', True)
#        SendJson("Settings.SetSettingValue", '{"setting":"myvideos.extractchapterthumbs","value":true}', True)

def set_syncdate(TimeStampConvert):
    if TimeStampConvert:
        LocalTime = convert_to_local(TimeStampConvert, False, False)

        if isinstance(LocalTime, str) and len(LocalTime) >= 10:
            TimeStamp = datetime.fromisoformat(LocalTime)
            set_settings("syncdate", TimeStamp.strftime('%Y-%m-%d'))
            set_settings("synctime", TimeStamp.strftime('%H:%M'))

def load_settings_bool(setting):
    for _ in range(10):
        value = Addon.getSetting(setting)

        if value == "": # Can happen when Kodi locked the file
            xbmc.log(f"EMBY.helper.utils: Empty setting: {setting}", 1) # LOGINFO

            if sleep(0.1):
                break

            continue

        if value == "true":
            globals()[setting] = True
        else:
            globals()[setting] = False

        break

def load_settings_json(setting):
    for _ in range(10):
        value = Addon.getSetting(setting)

        if value == "": # Can happen when Kodi locked the file
            xbmc.log(f"EMBY.helper.utils: Empty setting: {setting}", 1) # LOGINFO

            if sleep(0.1):
                break

            continue

        globals()[setting] = json.loads(value)
        break

def load_settings(setting):
    for _ in range(10):
        value = Addon.getSetting(setting)

        if value == "": # Can happen when Kodi locked the file
            xbmc.log(f"EMBY.helper.utils: Empty setting: {setting}", 1) # LOGINFO

            if sleep(0.1):
                break

            continue

        globals()[setting] = value
        break

def load_settings_int(setting):
    for _ in range(10):
        value = Addon.getSetting(setting)

        if value == "": # Can happen when Kodi locked the file
            xbmc.log(f"EMBY.helper.utils: Empty setting: {setting}", 1) # LOGINFO

            if sleep(0.1):
                break

            continue

        globals()[setting] = int(value)
        break

def set_settings(setting, value):
    globals()[setting] = value
    Addon.setSetting(setting, value)

def set_settings_json(setting, value):
    globals()[setting] = value
    Addon.setSetting(setting, json.dumps(value))

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
    if not any(char in Data for char in '&<>"\''):
        return Data

    return ENC_RE.sub(lambda m: ENC_MAP[m.group(0)], Data)

def decode_XML(Data):
    if "&" not in Data:
        return Data

    return DEC_RE.sub(lambda m: DEC_MAP[m.group(0)], Data)

def check_iptvsimple():
    if not SendJson("Addons.GetAddonDetails", '{"addonid":"pvr.iptvsimple", "properties": ["version"]}', True):
        if DebugLog: xbmc.log("EMBY.helper.utils: iptv simple not found", 2) # LOGWARNING
        set_settings_bool("LiveTVEnabled", False)
        return False

    return True

def notify_event(Message, Data, SendOption):
    if NotifyEvents and SendOption:
        SendMsg = json.dumps(Data)
        SendMsg = SendMsg.replace('\\', '\\\\').replace('"', '\\"')
        xbmc.executebuiltin(f'NotifyAll(emby-next-gen,{Message},"{SendMsg}")')

def start_thread(Object, Args):
    if SystemShutdown:
        return

    Failed = False

    while True:
        try:
            Thread = threading.Thread(target=Object, args=Args)
            Thread.start()
            if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): start_thread Thread: {Object.__name__} / {Thread.ident}", 1) # LOGINFO

            if Failed:
                if DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): start_thread continue: {Object.__name__}", 2) # LOGWARNING

            break
        except RuntimeError as error:
            Failed = True
            if DebugLog: xbmc.log(f"EMBY.helper.utils: start_thread: {Object.__name__}, Error: {error}", 2) # LOGWARNING

            if sleep(1):
                if DebugLog: xbmc.log("EMBY.helper.utils: start_thread: shutdown", 2) # LOGWARNING
                break

def close_busyDialog(Force=False):
    if not (BusyDialogClose or Force):
        return

    for _ in range(20):
        busydialogOpen = xbmc.getCondVisibility("Window.IsActive(10138)")
        busydialognocancelOpen = xbmc.getCondVisibility("Window.IsActive(10160)")

        if busydialogOpen:
            xbmc.executebuiltin('Dialog.Close(10138,true)') # busydialog

        if busydialognocancelOpen:
            xbmc.executebuiltin('Dialog.Close(10160,true)') # busydialognocancel

        if busydialogOpen or busydialognocancelOpen:
            if sleep(0.1):
                return
        else:
            break

def close_dialog(DialogNameOrId):
    if DialogNameOrId == "all":
        for _ in range(20):
            DialogOpen = xbmc.getCondVisibility("System.HasActiveModalDialog")

            if DialogOpen:
                xbmc.executebuiltin('Dialog.Close(all,true)')

                if sleep(0.01): # Kodi needs time to process
                    return
            else:
                break
    else:
        for _ in range(20):
            DialogOpen = xbmc.getCondVisibility(f"Window.IsActive({DialogNameOrId})")

            if DialogOpen:
                xbmc.executebuiltin(f'Dialog.Close({DialogNameOrId},true)') # busydialog

                if sleep(0.01):
                    return
            else:
                break

def ActivateWindow(WindowId, Path, DialogClose=False, WaitForOpen=0):
    if DialogClose:
        close_dialog("all")

    if Path:
        xbmc.executebuiltin(f'ActivateWindow({WindowId}, "{Path}", return)')
    else:
        xbmc.executebuiltin(f'ActivateWindow({WindowId})')

    if WaitForOpen:
        WindowId = xbmcgui.getCurrentWindowId()

        while WindowId != WaitForOpen:
            WindowId = xbmcgui.getCurrentWindowId()
            sleep(0.01)

    xbmc.log(f"EMBY.helper.utils: [ ActivateWindow ] {WindowId}", 1) # LOGINFO

def refresh_DynamicNode():
    MenuPath = xbmc.getInfoLabel('Container.FolderPath')

    if (MenuPath.startswith("plugin://plugin.service.emby-next-gen/") or MenuPath.startswith("plugin://plugin.audio.emby-next-gen/") or MenuPath.startswith("plugin://plugin.image.emby-next-gen/")) and "mode=browse" in MenuPath.lower():
        if DebugLog: xbmc.log("Emby.hooks.utils: UserDataChanged refresh dynamic nodes", 1) # LOGINFO
        xbmc.executebuiltin('Container.Refresh')
    else:
        refresh_widgets(True)
        refresh_widgets(False)

def set_EmbyId_ServerId_by_Fake_KodiId(EmbyId, ServerId): # Maximum value is 2147483648
    if ServerId in EmbyServerIds:
        ServerIndex = EmbyServerIds.index(ServerId) + 1
    else:
        return 0

    EmbyFakeId = str(EmbyId)
    FakeIndex = 0

    for Index, Value in enumerate(MappingIds.values()):
        if str(EmbyId).startswith(Value):
            EmbyFakeId = EmbyFakeId.replace(Value, "", 1)
            FakeIndex = Index + 1
            break

    KodiId = ServerIndex * 100000000 + FakeIndex * 10000000 + int(EmbyFakeId)
    return KodiId

def get_EmbyId_ServerId_by_Fake_KodiId(KodiId):
    KodiId = int(KodiId)
    ServerIndex = KodiId // 100000000

    if not ServerIndex: # not an EmbyId
        return 0, ""

    Remain = KodiId % 100000000
    FakeNumberKey = Remain // 10000000
    EmbyId = Remain % 10000000

    if FakeNumberKey:
        FakeNumberKey = MappingIdsListKeys[FakeNumberKey - 1]
        EmbyId = int(f"{MappingIds[FakeNumberKey]}{EmbyId}")

    ServerId = EmbyServerIds[ServerIndex - 1]
    return EmbyId, ServerId


def get_digits(Text):
    Temp = ''.join(i for i in Text if i.isdigit())

    if Temp:
        return int(Temp)

    return 0

def get_youtube_path(Url):
    try:
        Parsed = urlparse(Url)

        if Parsed.netloc.lower().endswith("youtu.be"):
            return f"plugin://plugin.video.youtube/play/?video_id={Parsed.path.strip('/')}"

        Query = parse_qs(Parsed.query)

        if 'v' in Query and Query['v']:
            return f"plugin://plugin.video.youtube/play/?video_id={Query['v'][0]}"

        Parts = Parsed.path.strip("/").split("/")

        if len(Parts) >= 2 and Parts[0] in ("embed", "shorts", "v", "live"):
            return f"plugin://plugin.video.youtube/play/?video_id={Parts[1]}"
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: Not valid youtube: {Url} / {Error}", 3) # LOGERROR

    return ""

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

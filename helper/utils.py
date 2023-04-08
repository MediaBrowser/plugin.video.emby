import os
import shutil
import uuid
import json
from urllib.parse import quote
from datetime import datetime, timedelta
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

Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
KodiVersion = xbmc.getInfoLabel("System.BuildVersionCode").split(".")

if int(KodiVersion[1]) > 20:
    KodiMajorVersion = str(int(KodiVersion[0]) + 1)
else:
    KodiMajorVersion = KodiVersion[0]

PluginId = "plugin.video.emby-next-gen"
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
icon = ""
CustomDialogParameters = (Addon.getAddonInfo('path'), "default", "1080i")
EmbyServers = {}
MinimumVersion = "8.1.0"
refreshskin = False
device_name = "Kodi"
xspplaylists = False
animateicon = True
TranscodeFormatVideo = ""
TranscodeFormatAudio = ""
videoBitrate = 0
audioBitrate = 0
resumeJumpBack = 0
displayMessage = 0
newvideotime = 1
newmusictime = 1
startupDelay = 0
backupPath = ""
disablehttp2 = "true"
MinimumSetup = ""
limitIndex = 5
autoclose = 5
maxnodeitems = "25"
deviceName = "Kodi"
useDirectPaths = False
menuOptions = False
newContent = False
restartMsg = False
connectMsg = False
enableDeleteByKodiEvent = False
addUsersHidden = False
enableContextDelete = False
verifyFreeSpace = True
enableContext = False
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
getProductionLocations = False
getCast = False
deviceNameOpt = False
artworkcacheenable = True
device_id = ""
syncdate = ""
synctime = ""
syncduringplayback = False
usekodiworkarounds = False
usepathsubstitution = False
uniquepeoplemovies = False
uniquepeopletvshows = False
uniquepeopleepisodes = False
uniquepeoplemusicvideos = True
synclivetv = False
busyMsg = True
remotecontrol_force_clients = True
remotecontrol_client_control = True
remotecontrol_sync_clients = True
remotecontrol_wait_clients = 30
remotecontrol_drift = 200
remotecontrol_auto_ack = False
remotecontrol_resync_clients = False
remotecontrol_resync_time = 10
remotecontrol_keep_clients = False
watchtogeter_start_delay = 20
FolderAddonUserdata = f"special://profile/addon_data/{PluginId}/"
FolderEmbyTemp = f"special://profile/addon_data/{PluginId}/temp/"
FolderAddonUserdataLibrary = f"special://profile/addon_data/{PluginId}/library/"
FolderUserdataThumbnails = "special://profile/Thumbnails/"
SystemShutdown = False
SyncPause = {}  # keys: playing, kodi_sleep, embyserverID, , kodi_rw, priority (thread with higher priorit needs access)
WidgetRefresh = False
Dialog = xbmcgui.Dialog()
XbmcPlayer = xbmc.Player()  # Init Player
WizardCompleted = True
AssignEpisodePostersToTVShowPoster = False
PluginStarted = False
sslverify = False
ProgressBar = [xbmcgui.DialogProgressBG(), 0, False, False] # obj, Counter, Open, Init in progress
AddonModePath = "http://127.0.0.1:57342/"
TranslationsCached = {}
Playlists = (xbmc.PlayList(0), xbmc.PlayList(1))

def refresh_widgets():
    xbmc.log("EMBY.helper.utils: Refresh widgets initialized", 1) # LOGINFO

    if not WidgetRefresh:
        xbmc.log("EMBY.helper.utils: Refresh widgets started", 1) # LOGINFO
        globals()["WidgetRefresh"] = True
        SendJson('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","params":{"showdialogs":false,"directory":"widget_refresh_trigger"},"id":1}')

def SendJson(JsonString, ForceBreak=False):
    LogSend = False

    for Index in range(70): # retry -> timout 25 seconds
        Ret = xbmc.executeJSONRPC(JsonString)

        if not Ret: # Valid but not correct Kodi return value -> Kodi bug
            return True

        Ret = json.loads(Ret)

        if not Ret.get("error", False):
            return Ret

        if ForceBreak:
            return False

        if not LogSend:
            xbmc.log(f"Emby.helper.utils: Json error, retry: {JsonString}", 2) # LOGWARNING
            LogSend = True

        if Index < 50: # 5 seconds rapidly
            if sleep(0.1):
                return {}
        else: # after 5 seconds delay cycle by 1 second for the last 20 seconds
            if sleep(1):
                return {}

    xbmc.log(f"Emby.helper.utils: Json error, timeout: {Ret} / {JsonString}", 3) # LOGERROR
    return {}

def image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText):
    xbmc.log(f"EMBY.helper.utils: Add image text overlay: {EmbyID}", 1) # LOGINFO

    if ImageTag == "noimage":
        BinaryData = noimagejpg
    else:
        BinaryData, _, _ = EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag)

        if not BinaryData:
            BinaryData = noimagejpg

    if not ImageOverlay:
        return BinaryData

    img = Image.open(io.BytesIO(BinaryData))
    ImageWidth, ImageHeight = img.size
    draw = ImageDraw.Draw(img, "RGBA")
    BoxY = int(ImageHeight * 0.9)
    BorderSize = int(ImageHeight * 0.01)
    fontsize = 1
    font = ImageFont.truetype(FontPath, 1)

    #Use longest possible text to determine font width
    ImageWidthMod = ImageHeight / 3 * 4

    while font.getsize("Title Sequence")[0] < 0.80 * ImageWidthMod and font.getsize("Title Sequence")[1] < 0.80 * BoxY:
        fontsize += 1
        font = ImageFont.truetype(FontPath, fontsize)

    FontSizeY = font.getsize(OverlayText)[1]
    draw.rectangle((-BorderSize, BoxY - FontSizeY, ImageWidth + BorderSize, BoxY), fill=(0, 0, 0, 127), outline="white",  width=BorderSize)
    draw.text(xy=(ImageWidth / 2, BoxY - FontSizeY / 2), text=OverlayText, fill="#FFFFFF", font=font, anchor="mm", align="center")
    imgByteArr = io.BytesIO()
    img.save(imgByteArr, format=img.format)
    return imgByteArr.getvalue()

def restart_kodi():
    xbmc.log("EMBY.helper.utils: Restart Kodi", 1) # LOGINFO
    globals()["SystemShutdown"] = True
    xbmc.executebuiltin('RestartApp')

def sleep(Seconds):
    for _ in range(int(Seconds * 10)):
        if SystemShutdown:
            return True

        xbmc.sleep(100)

    return False

def progress_open(Header):
    while ProgressBar[3]:
        sleep(1)

    globals()["ProgressBar"][1] += 1

    if ProgressBar[1] == 1:
        globals()["ProgressBar"][3] = True
        globals()["ProgressBar"][0].create(Translate(33199), Header)
        globals()["ProgressBar"][3] = False
        globals()["ProgressBar"][2] = True

    xbmc.log(f"EMBY.helper.utils: Progress Bar open: {ProgressBar[1]}", 1) # LOGINFO

def progress_close():
    while ProgressBar[3]:
        sleep(1)

    globals()["ProgressBar"][1] -= 1

    if ProgressBar[1] == 0:
        globals()["ProgressBar"][3] = True
        globals()["ProgressBar"][0].close()
        globals()["ProgressBar"][2] = False
        globals()["ProgressBar"][3] = False

    xbmc.log(f"EMBY.helper.utils: Progress Bar close: {ProgressBar[1]}", 1) # LOGINFO

def progress_update(Progress, Heading, Message):
    if ProgressBar[2]:
        ProgressBar[0].update(Progress, heading=Heading, message=Message)

# Delete objects from kodi cache
def delFolder(path, Pattern=""):
    xbmc.log("EMBY.helper.utils: --[ delete folder ]", 0) # LOGDEBUG
    dirs, files = listDir(path)
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
            delFile(f"{path}{Filename}")

    if path:
        rmFolder(path)

    xbmc.log(f"EMBY.helper.utils: DELETE {path}", 2) # LOGWARNING

# Delete files and dirs recursively
def delete_recursive(path, dirs):
    for directory in dirs:
        dirs2, files = listDir(f"{path}{directory}")

        for Filename in files:
            delFile(f"{path}{directory}/{Filename}")

        delete_recursive(f"{path}{directory}", dirs2)
        rmFolder(f"{path}{directory}")

def rmFolder(Path):
    Path = translatePath(Path)

    if os.path.isdir(Path):
        try:
            os.rmdir(Path)
        except Exception as Error:
            xbmc.log(f"EMBY.helper.utils: Delete folder issue: {Error} / {Path}", 3) # LOGERROR

def mkDir(Path):
    Path = translatePath(Path)

    if not os.path.isdir(Path):
        os.mkdir(Path)

def delFile(Path):
    Path = translatePath(Path)

    if os.path.isfile(Path):
        os.remove(Path)

def copyFile(SourcePath, DestinationPath):
    SourcePath = translatePath(SourcePath)
    DestinationPath = translatePath(DestinationPath)

    if checkFileExists(DestinationPath):
        xbmc.log(f"EMBY.helper.utils: copy: File exists: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
        return

    try:
        shutil.copy(SourcePath, DestinationPath)
        xbmc.log(f"EMBY.helper.utils: copy: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: copy issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

def readFileBinary(Path):
    Path = translatePath(Path)

    if os.path.isfile(Path):
        with open(Path, "rb") as infile:
            data = infile.read()

        return data

    return b""

def readFileString(Path):
    Path = translatePath(Path)

    if os.path.isfile(Path):
        with open(Path, "rb") as infile:
            data = infile.read()

        return data.decode('utf-8')

    return ""

def writeFileString(Path, Data):
    Data = Data.encode('utf-8')
    Path = translatePath(Path)

    with open(Path, "wb") as outfile:
        outfile.write(Data)

def getFreeSpace(Path):
    if verifyFreeSpace:
        try:
            Path = translatePath(Path)
            space = os.statvfs(Path)
            free = space.f_bavail * space.f_frsize / 1024
        #    total = space.f_blocks * space.f_frsize / 1024
            return free
        except Exception as Error: # not suported by Windows
            xbmc.log(f"EMBY.helper.utils: getFreeSpace: {Error}", 2) # LOGWARNING
            return 9999999
    else:
        return 9999999

def writeFileBinary(Path, Data):
    Path = translatePath(Path)

    with open(Path, "wb") as outfile:
        outfile.write(Data)

def checkFileExists(Path):
    Path = translatePath(Path)

    if os.path.isfile(Path):
        return True

    return False

def checkFolderExists(Path):
    Path = translatePath(Path)

    if os.path.isdir(Path):
        return True

    return False

def listDir(Path):
    Files = ()
    Folders = ()
    Path = translatePath(Path)

    if os.path.isdir(Path):
        for FilesFolders in os.listdir(Path):
            FilesFoldersPath = os.path.join(Path, FilesFolders)

            if os.path.isdir(FilesFoldersPath):
                FilesFolders = os.path.join(FilesFolders, b"")  # add trailing / or \
                Folders += (FilesFolders.decode('utf-8'),)
            else:
                Files += (FilesFolders.decode('utf-8'),)

    return Folders, Files

def translatePath(Data):
    Path = xbmcvfs.translatePath(Data)
    Path = Path.encode('utf-8')
    return Path

def currenttime():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

def currenttime_kodi_format():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def currenttime_kodi_format_and_unixtime():
    Current = datetime.now()
    KodiFormat = Current.strftime('%Y-%m-%d %H:%M:%S')
    UnixTime = int(datetime.timestamp(Current))
    return KodiFormat, UnixTime

def unixtimeInMicroseconds():
    Current = datetime.now()
    UnixTime = int(datetime.timestamp(Current))
    return UnixTime + Current.microsecond / 1000000

# Remove all emby playlists
def delete_playlists():
    SearchFolders = ['special://profile/playlists/video/', 'special://profile/playlists/music/']

    for SearchFolder in SearchFolders:
        _, files = listDir(SearchFolder)

        for Filename in files:
            if Filename.startswith('emby'):
                delFile(f"{SearchFolder}{Filename}")

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
def convert_to_local(date, DateOnly=False):
    if not date or str(date) == "0":
        return "0"

    if isinstance(date, int):
        date = str(date)

    if isinstance(date, str):
        date = parser.parse(date.encode('utf-8'))

        if not date.tzname():
            date = date.replace(tzinfo=tz.tzutc())

    timestamp = (date - datetime(1970, 1, 1, tzinfo=tz.tzutc())).total_seconds()

    try:
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

    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

def Translate(Id):
    if Id in TranslationsCached:
        return TranslationsCached[Id]

    result = Addon.getLocalizedString(Id)

    if not result:
        result = xbmc.getLocalizedString(Id)

    globals()['TranslationsCached'][Id] = result
    return result

def PathToFilenameReplaceSpecialCharecters(Path):
    Pos = Path.rfind("/")

    if Pos == -1:  # Windows
        Pos = Path.rfind("\\")

    Path = Path[Pos + 1:]
    Filename = quote(Path)

    while Filename.find("%") != -1:
        Pos = Filename.find("%")
        Filename = Filename.replace(Filename[Pos:Pos + 3], "_")

    return Filename

def SizeToText(size):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0

    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size /= 1024.0

    return f"1.{size}{suffixes[suffixIndex]}"

# Copy folder content from one to another
def copytree(path, dest):
    dirs, files = listDir(path)
    mkDir(dest)

    if dirs:
        copy_recursive(path, dirs, dest)

    for Filename in files:
        CopyFile = f"{path}{Filename}"

        if CopyFile.endswith('.pyo'):
            continue

        copyFile(CopyFile, f"{dest}{Filename}")

    xbmc.log(f"EMBY.helper.utils: Copied {path}", 1) # LOGINFO

def copy_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = f"{path}{directory}"
        dest_dir = f"{dest}{directory}"
        mkDir(dest_dir)
        dirs2, files = listDir(dirs_dir)

        if dirs2:
            copy_recursive(dirs_dir, dirs2, dest_dir)

        for Filename in files:
            CopyFile = f"{dirs_dir}{Filename}"

            if CopyFile.endswith('.pyo'):
                continue

            copyFile(CopyFile, f"{dest_dir}{Filename}")

def get_device_id(reset):
    if device_id:
        return

    mkDir(FolderAddonUserdata)
    emby_guid = f"{FolderAddonUserdata}emby_guid"
    globals()["device_id"] = readFileString(emby_guid)

    if not device_id or reset:
        xbmc.log("EMBY.helper.utils: Generating a new GUID", 1) # LOGINFO
        globals()["device_id"] = str(uuid.uuid4())
        writeFileString(emby_guid, device_id)

    if reset:  # delete login data -> force new login
        _, files = listDir(FolderAddonUserdata)

        for Filename in files:
            if Filename.startswith('servers_'):
                delFile(f"{FolderAddonUserdata}{Filename}")

    xbmc.log(f"EMBY.helper.utils: device_id loaded: {device_id}", 1) # LOGINFO

# Kodi Settings
def InitSettings():
    load_settings('TranscodeFormatVideo')
    load_settings('TranscodeFormatAudio')
    load_settings('videoBitrate')
    load_settings('audioBitrate')
    load_settings('resumeJumpBack')
    load_settings('autoclose')
    load_settings('displayMessage')
    load_settings('newvideotime')
    load_settings('newmusictime')
    load_settings('startupDelay')
    load_settings('backupPath')
    load_settings('MinimumSetup')
    load_settings('limitIndex')
    load_settings('deviceName')
    load_settings('useDirectPaths')
    load_settings('syncdate')
    load_settings('synctime')
    load_settings('maxnodeitems')
    load_settings('remotecontrol_wait_clients')
    load_settings('watchtogeter_start_delay')
    load_settings('remotecontrol_drift')
    load_settings('remotecontrol_resync_time')
    load_settings_bool('sslverify')
    load_settings_bool('syncduringplayback')
    load_settings_bool('usekodiworkarounds')
    load_settings_bool('refreshskin')
    load_settings_bool('animateicon')
    load_settings_bool('disablehttp2')
    load_settings_bool('menuOptions')
    load_settings_bool('xspplaylists')
    load_settings_bool('newContent')
    load_settings_bool('restartMsg')
    load_settings_bool('connectMsg')
    load_settings_bool('addUsersHidden')
    load_settings_bool('enableContextDelete')
    load_settings_bool('enableContext')
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
    load_settings_bool('getProductionLocations')
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
    load_settings_bool('AssignEpisodePostersToTVShowPoster')
    load_settings_bool('WizardCompleted')
    load_settings_bool('verifyFreeSpace')
    load_settings_bool('usepathsubstitution')
    load_settings_bool('uniquepeoplemovies')
    load_settings_bool('uniquepeopletvshows')
    load_settings_bool('uniquepeopleepisodes')
    load_settings_bool('uniquepeoplemusicvideos')
    load_settings_bool('synclivetv')
    load_settings_bool('remotecontrol_force_clients')
    load_settings_bool('remotecontrol_client_control')
    load_settings_bool('remotecontrol_sync_clients')
    load_settings_bool('remotecontrol_auto_ack')
    load_settings_bool('remotecontrol_resync_clients')
    load_settings_bool('remotecontrol_keep_clients')

    if synclivetv:
        if not xbmc.getCondVisibility('System.HasAddon(pvr.iptvsimple)'):
            set_settings_bool('synclivetv', False)

    if usepathsubstitution:
        globals()["AddonModePath"] = "/emby_addon_mode/"
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

    if disablehttp2:
        globals()["disablehttp2"] = "true"
    else:
        globals()["disablehttp2"] = "false"

    ToggleIcon = []

    if animateicon:
        if icon and icon != "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif":
            ToggleIcon = ["resources/icon.png", "resources/icon-animated.gif"]

        globals()["icon"] = "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif"
    else:
        if icon and icon != "special://home/addons/plugin.video.emby-next-gen/resources/icon.png":
            ToggleIcon = ["resources/icon-animated.gif", "resources/icon.png"]

        globals()["icon"] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

    if ToggleIcon:
        xbmc.log("EMBY.helper.utils: Toggle icon", 1) # LOGINFO
        AddonXml = readFileString("special://home/addons/plugin.video.emby-next-gen/addon.xml")
        AddonXml = AddonXml.replace(ToggleIcon[0], ToggleIcon[1])
        writeFileString("special://home/addons/plugin.video.emby-next-gen/addon.xml", AddonXml)

    # Change type to integer
    globals().update({"limitIndex": int(limitIndex), "startupDelay": int(startupDelay), "videoBitrate": int(videoBitrate), "audioBitrate": int(audioBitrate), "remotecontrol_wait_clients": int(remotecontrol_wait_clients), "remotecontrol_drift": int(remotecontrol_drift), "remotecontrol_resync_time": int(remotecontrol_resync_time)})

def set_syncdate(timestamp):
    TimeStamp = parser.parse(timestamp.encode('utf-8'))
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

mkDir(FolderAddonUserdata)
mkDir(FolderEmbyTemp)
mkDir(FolderUserdataThumbnails)
mkDir(FolderAddonUserdataLibrary)
InitSettings()
get_device_id(False)
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0}
_, FolderDatabasefiles = listDir("special://profile/Database/")
FontPath = translatePath("special://home/addons/plugin.video.emby-next-gen/resources/font/LiberationSans-Bold.ttf")
noimagejpg = readFileBinary("special://home/addons/plugin.video.emby-next-gen/resources/noimage.jpg")

for FolderDatabaseFilename in FolderDatabasefiles:
    if not FolderDatabaseFilename.endswith('-wal') and not FolderDatabaseFilename.endswith('-shm') and not FolderDatabaseFilename.endswith('db-journal'):
        if FolderDatabaseFilename.startswith('Textures'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['texture-version']:
                DatabaseFiles['texture'] = translatePath(f"special://profile/Database/{FolderDatabaseFilename}")
                DatabaseFiles['texture-version'] = Version
        elif FolderDatabaseFilename.startswith('MyMusic'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['music-version']:
                DatabaseFiles['music'] = translatePath(f"special://profile/Database/{FolderDatabaseFilename}")
                DatabaseFiles['music-version'] = Version
        elif FolderDatabaseFilename.startswith('MyVideos'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['video-version']:
                DatabaseFiles['video'] = translatePath(f"special://profile/Database/{FolderDatabaseFilename}")
                DatabaseFiles['video-version'] = Version

import os
import shutil
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
EmbyTypeMapping = {"Person": "actor", "Video": "movie", "Movie": "movie", "Series": "tvshow", "Season": "season", "Episode": "episode", "Audio": "song", "MusicAlbum": "album", "MusicArtist": "artist", "Genre": "genre", "MusicGenre": "genre", "Tag": "tag" , "Studio": "studio" , "BoxSet": "set", "Folder": None, "MusicVideo": "musicvideo", "Playlist": "Playlist"}
KodiTypeMapping = {"actor": "Person", "tvshow": "Series", "season": "Season", "episode": "Episode", "song": "Audio", "album": "MusicAlbum", "artist": "MusicArtist", "genre": "Genre", "tag": "Tag", "studio": "Studio" , "set": "BoxSet", "musicvideo": "MusicVideo", "playlist": "Playlist", "movie": "Movie"}
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
icon = ""
CustomDialogParameters = (Addon.getAddonInfo('path'), "default", "1080i")
EmbyServers = {}
ItemSkipUpdate = []
MinimumVersion = "9.4.0"
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
newContentTime = 1
startupDelay = 0
curltimeouts = 2
backupPath = ""
enablehttp2 = False
MinimumSetup = ""
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
enableContextRemoteOptions = True
enableContextDownloadOptions = True
enableContextFavouriteOptions = True
enableContextSpecialsOptions = True
enableContextRecordingOptions = True
enableContextRefreshOptions = True
verifyFreeSpace = True
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
syncdate = ""
synctime = ""
syncduringplayback = False
usekodiworkaroundswidget = False
usepathsubstitution = False
busyMsg = True
websocketenabled = True
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
DownloadPath = "special://profile/addon_data/plugin.video.emby-next-gen/"
FolderAddonUserdata = "special://profile/addon_data/plugin.video.emby-next-gen/"
FolderEmbyTemp = "special://profile/addon_data/plugin.video.emby-next-gen/temp/"
FolderUserdataThumbnails = "special://profile/Thumbnails/"
PlaylistPath = "special://profile/playlists/mixed/"
KodiFavFile = "special://profile/favourites.xml"
SystemShutdown = False
SyncPause = {}  # keys: playing, kodi_sleep, embyserverID, , kodi_rw, priority (thread with higher priorit needs access)
WidgetRefresh = {"video": False, "music": False}
BoxSetsToTags = False
SyncFavorites = False
Dialog = xbmcgui.Dialog()
XbmcPlayer = xbmc.Player()  # Init Player
WizardCompleted = True
AssignEpisodePostersToTVShowPoster = False
sslverify = False
AddonModePath = "http://127.0.0.1:57342/"
TranslationsCached = {}
Playlists = (xbmc.PlayList(0), xbmc.PlayList(1))
ScreenResolution = (1920, 1080)
HTTPQueryDoublesFilter = {}
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

def refresh_widgets(isVideo):
    xbmc.log("EMBY.helper.utils: Refresh widgets initialized", 1) # LOGINFO

    if isVideo and not WidgetRefresh['video']:
        xbmc.log("EMBY.helper.utils: Refresh widgets video started", 1) # LOGINFO
        globals()["WidgetRefresh"]['video'] = True
        SendJson('{"jsonrpc":"2.0","method":"VideoLibrary.Scan","params":{"showdialogs":false,"directory":"widget_refresh_trigger"},"id":1}')

    if not isVideo and not WidgetRefresh['music']:
        xbmc.log("EMBY.helper.utils: Refresh widgets music started", 1) # LOGINFO
        globals()["WidgetRefresh"]['music'] = True
        SendJson('{"jsonrpc":"2.0","method":"AudioLibrary.Scan","params":{"showdialogs":false,"directory":"widget_refresh_trigger"},"id":1}')

def SendJson(JsonString, ForceBreak=False):
    LogSend = False
    Ret = {}

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
        ContentType = "image/jpeg"
    else:
        BinaryData, ContentType, _ = EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag)

        if not BinaryData:
            BinaryData = noimagejpg
            ContentType = "image/jpeg"

    if not ImageOverlay:
        return BinaryData, ContentType

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
    return imgByteArr.getvalue(), "image/jpeg"

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
        try:
            os.remove(Path)
        except Exception as Error:
            xbmc.log(f"EMBY.helper.utils: delFile: {Error}", 3) # LOGERROR

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

def moveFile(SourcePath, DestinationPath):
    try:
        shutil.move(SourcePath, DestinationPath)
        xbmc.log(f"EMBY.helper.utils: move: {SourcePath} to {DestinationPath}", 0) # LOGDEBUG
    except Exception as Error:
        xbmc.log(f"EMBY.helper.utils: move issue: {SourcePath} to {DestinationPath} -> {Error}", 3) # LOGERROR

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

    try:
        with open(Path, "wb") as outfile:
            outfile.write(Data)
    except Exception as Error: # permission denied
        xbmc.log(f"EMBY.helper.utils: writeFileString ({Path}): {Error}", 2) # LOGWARNING

def getFreeSpace(Path):
    if verifyFreeSpace:
        try:
            Path = translatePath(Path)
            space = os.statvfs(Path)
            free = space.f_bavail * space.f_frsize / 1024
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

# add trailing / or \
def PathAddTrailing(Path):
    if isinstance(Path, str):
        return os.path.join(Path, "")

    return os.path.join(Path, b"")

def listDir(Path):
    Files = ()
    Folders = ()
    Path = translatePath(Path)

    if os.path.isdir(Path):
        for FilesFolders in os.listdir(Path):
            FilesFoldersPath = os.path.join(Path, FilesFolders)

            if os.path.isdir(FilesFoldersPath):
                FilesFolders = PathAddTrailing(FilesFolders)
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

def get_unixtime():
    Current = datetime.now()
    return int(datetime.timestamp(Current))

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
def convert_to_local(date, DateOnly=False, YearOnly=False):
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

def PathToFilenameReplaceSpecialCharecters(Path):
    Separator = get_Path_Seperator(Path)
    Pos = Path.rfind(Separator)
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
        Source = f"{path}{Filename}"

        if Source.endswith('.pyo'):
            continue

        copyFile(Source, f"{dest}{Filename}")

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
            Source = f"{dirs_dir}{Filename}"

            if Source.endswith('.pyo'):
                continue

            copyFile(Source, f"{dest_dir}{Filename}")

# Kodi Settings
def InitSettings():
    load_settings('TranscodeFormatVideo')
    load_settings('TranscodeFormatAudio')
    load_settings('resumeJumpBack')
    load_settings('autoclose')
    load_settings('displayMessage')
    load_settings('newContentTime')
    load_settings('backupPath')
    load_settings('MinimumSetup')
    load_settings('deviceName')
    load_settings('syncdate')
    load_settings('synctime')
    load_settings('maxnodeitems')
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
    load_settings_bool('ArtworkLimitations')
    load_settings_bool('sslverify')
    load_settings_bool('syncduringplayback')
    load_settings_bool('usekodiworkaroundswidget')
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
    load_settings_bool('enableContextRemoteOptions')
    load_settings_bool('enableContextDownloadOptions')
    load_settings_bool('enableContextFavouriteOptions')
    load_settings_bool('enableContextSpecialsOptions')
    load_settings_bool('enableContextRecordingOptions')
    load_settings_bool('enableContextRefreshOptions')
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
    load_settings_bool('remotecontrol_force_clients')
    load_settings_bool('remotecontrol_client_control')
    load_settings_bool('remotecontrol_sync_clients')
    load_settings_bool('remotecontrol_auto_ack')
    load_settings_bool('remotecontrol_resync_clients')
    load_settings_bool('remotecontrol_keep_clients')
    load_settings_bool('websocketenabled')
    load_settings_bool('BoxSetsToTags')
    load_settings_bool('SyncFavorites')
    load_settings_bool('SyncLiveTvOnEvents')

    if ArtworkLimitations:
        globals()["ScreenResolution"] = (int(xbmc.getInfoLabel('System.ScreenWidth')), int(xbmc.getInfoLabel('System.ScreenHeight')))
        xbmc.log(f"EMBY.helper.utils: Screen resolution: {ScreenResolution}", 1) # LOGINFO

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

    update_mode_settings()
    xbmcgui.Window(10000).setProperty('EmbyDelete', str(enableContextDelete))
    xbmcgui.Window(10000).setProperty('EmbyRemote', str(enableContextRemoteOptions))
    xbmcgui.Window(10000).setProperty('EmbyDownload', str(enableContextDownloadOptions))
    xbmcgui.Window(10000).setProperty('EmbyFavourite', str(enableContextFavouriteOptions))
    xbmcgui.Window(10000).setProperty('EmbySpecials', str(enableContextSpecialsOptions))
    xbmcgui.Window(10000).setProperty('EmbyRecording', str(enableContextRecordingOptions))
    xbmcgui.Window(10000).setProperty('EmbyRefresh', str(enableContextRefreshOptions))

def update_mode_settings():
    # disable file metadata extraction
    if not useDirectPaths:
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractflags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractthumb","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.usetags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"musicfiles.usetags","value":false}}', True)
        SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"musicfiles.findremotethumbs","value":false}}', True)

        if usepathsubstitution:
            SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractchapterthumbs","value":true}}', True)
        else:
            SendJson('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue", "params": {"setting":"myvideos.extractchapterthumbs","value":false}}', True)

def set_syncdate(TimeStampConvert):
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

def crc8(Bytes):
    crc = 0

    for Byte in Bytes:
        for _ in range(8):
            if (crc >> 7) ^ (Byte & 0x01):
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

            Byte = Byte >> 1

    return crc

def get_hash(Data):
    HashNumber = crc8(Data.encode("utf-8"))
    HashNumber = HashNumber / 2
    return round(HashNumber) # get hash from 0 - 128 (this could include collisions)

def is_number(Value):
    return Value.replace('.','',1).isdigit()

def get_Path_Seperator(Path):
    Pos = Path.rfind("/")

    if Pos == -1:
        Pos = Path.rfind("\\")
        return "\\"

    return "/"

def encode_XML(Data):
    Data = Data.replace("&", "&amp;")
    Data = Data.replace("<", "&lt;")
    Data = Data.replace(">", "&gt;")
    Data = Data.replace("\"", "&quot;")
    Data = Data.replace("'", "&apos;")
    return Data

mkDir(FolderAddonUserdata)
mkDir(FolderEmbyTemp)
mkDir(FolderUserdataThumbnails)
InitSettings()
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0, 'epg': "", 'epg-version': 0, 'tv': "", 'tv-version': 0}
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
        elif FolderDatabaseFilename.startswith('Epg'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['epg-version']:
                DatabaseFiles['epg'] = translatePath(f"special://profile/Database/{FolderDatabaseFilename}")
                DatabaseFiles['epg-version'] = Version
        elif FolderDatabaseFilename.startswith('TV'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['tv-version']:
                DatabaseFiles['tv'] = translatePath(f"special://profile/Database/{FolderDatabaseFilename}")
                DatabaseFiles['tv-version'] = Version

set_settings_bool('artworkcacheenable', True)

import os
import shutil
import uuid
import json
from urllib.parse import quote
from datetime import datetime, timedelta
from dateutil import tz, parser
import xbmcvfs
import xbmc
import xbmcaddon
import xbmcgui
from . import loghandler

LOG = loghandler.LOG('EMBY.helper.utils')
Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
PluginId = "plugin.video.emby-next-gen"
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
icon = "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif"
EmbyServers = {}
MinimumVersion = "7.0.2"
StartupComplete = False
refreshskin = True
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
artworkcachethreads = 5
maxnodeitems = "25"
username = ""
server = ""
deviceName = ""
useDirectPaths = False
menuOptions = False
newContent = False
restartMsg = False
connectMsg = False
enableDeleteByKodiEvent = False
addUsersHidden = False
enableContextDelete = False
enableContext = False
transcodeH265 = False
transcodeDivx = False
transcodeXvid = False
transcodeMpeg2 = False
enableCinemaMovies = False
enableCinemaEpisodes = False
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
syncruntimelimits = False
SkipUpdateSettings = 0
device_id = ""
syncdate = ""
synctime = ""
syncduringplayback = False
databasevacuum = False
FolderAddonUserdata = "special://profile/addon_data/%s/" % PluginId
FolderEmbyTemp = "special://profile/addon_data/%s/temp/" % PluginId
FolderAddonUserdataLibrary = "special://profile/addon_data/%s/library/" % PluginId
SystemShutdown = False
SyncPause = {}  # keys: playing, kodi_busy, embyserverID
DBBusy = False
Dialog = xbmcgui.Dialog()
waitForAbort = xbmc.Monitor().waitForAbort
ProgressBar = [xbmcgui.DialogProgressBG(), 0, False, False] # obj, Counter, Open, Init in progress

DialogTypes = {
    'yesno': Dialog.yesno,
    'ok': Dialog.ok,
    'notification': Dialog.notification,
    'input': Dialog.input,
    'select': Dialog.select,
    'numeric': Dialog.numeric,
    'multi': Dialog.multiselect,
    'textviewer': Dialog.textviewer
}

def progress_open(Header):
    while ProgressBar[3]:
        waitForAbort(1)

    globals()["ProgressBar"][1] += 1

    if ProgressBar[1] == 1:
        globals()["ProgressBar"][3] = True
        globals()["ProgressBar"][0].create("Emby", Header)
        globals()["ProgressBar"][3] = False
        globals()["ProgressBar"][2] = True

    LOG.info("Progress Bar open: %s" % ProgressBar[1])

def progress_close():
    while ProgressBar[3]:
        waitForAbort(1)

    globals()["ProgressBar"][1] -= 1

    if ProgressBar[1] == 0:
        globals()["ProgressBar"][3] = True
        globals()["ProgressBar"][0].close()
        globals()["ProgressBar"][2] = False
        globals()["ProgressBar"][3] = False

    LOG.info("Progress Bar close: %s" % ProgressBar[1])

def progress_update(Progress, Heading, Message):
    if ProgressBar[2]:
        ProgressBar[0].update(Progress, heading=Heading, message=Message)

def sync_is_paused():
    LOG.debug("SyncPause state: %s" % str(SyncPause))

    for Busy in list(SyncPause.values()):
        if Busy:
            return True

    return False

# Delete objects from kodi cache
def delFolder(path):
    LOG.debug("--[ delete folder ]")
    delete_path = path is not None
    path = path or FolderEmbyTemp
    dirs, files = listDir(path)
    delete_recursive(path, dirs)

    for Filename in files:
        delFile("%s%s" % (path, Filename))

    if delete_path:
        rmFolder(path)

    LOG.warning("DELETE %s" % path)

# Delete files and dirs recursively
def delete_recursive(path, dirs):
    for directory in dirs:
        dirs2, files = listDir("%s%s" % (path, directory))

        for Filename in files:
            delFile("%s%s/%s" % (path, directory, Filename))

        delete_recursive("%s%s" % (path, directory), dirs2)
        rmFolder("%s%s" % (path, directory))

def rmFolder(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isdir(Path):
        os.rmdir(Path)

def mkDir(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if not os.path.isdir(Path):
        os.mkdir(Path)

def delFile(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isfile(Path):
        os.remove(Path)

def copyFile(SourcePath, DestinationPath):
    SourcePath = translatePath(SourcePath)
    DestinationPath = translatePath(DestinationPath)

    try:
        shutil.copy(SourcePath, DestinationPath)
        LOG.debug("copy: %s to %s" % (SourcePath, DestinationPath))
    except:
        LOG.error("copy issue: %s to %s" % (SourcePath, DestinationPath))

def renameFolder(SourcePath, DestinationPath):
    SourcePath = translatePath(SourcePath)
    DestinationPath = translatePath(DestinationPath)
    SourcePath = SourcePath.encode('utf-8')
    DestinationPath = DestinationPath.encode('utf-8')
    os.rename(SourcePath, DestinationPath)

def readFileBinary(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isfile(Path):
        with open(Path, "rb") as infile:
            data = infile.read()

        return data

    return b""

def readFileString(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isfile(Path):
        with open(Path, "rb") as infile:
            data = infile.read()

        return data.decode('utf-8')

    return ""

def writeFileString(Path, Data):
    Data = Data.encode('utf-8')
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    with open(Path, "wb") as outfile:
        outfile.write(Data)

def writeFileBinary(Path, Data):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    with open(Path, "wb") as outfile:
        outfile.write(Data)

def checkFileExists(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isfile(Path):
        return True

    return False

def checkFolderExists(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isdir(Path):
        return True

    return False

def listDir(Path):
    Files = ()
    Folders = ()
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

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
    return xbmcvfs.translatePath(Data)

def currenttime():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

def currenttime_kodi_format():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Remove all emby playlists
def delete_playlists():
    SearchFolders = ['special://profile/playlists/video/', 'special://profile/playlists/music/']

    for SearchFolder in SearchFolders:
        _, files = listDir(SearchFolder)

        for Filename in files:
            if Filename.startswith('emby'):
                delFile("%s%s" % (SearchFolder, Filename))

# Remove all nodes
def delete_nodes():
    delFolder("special://profile/library/video/")
    delFolder("special://profile/library/music/")
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
    if not date:
        return ""

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
    except:
        LOG.warning("invalid timestamp")
        return ""

    if timestamp.year < 1900:
        LOG.warning("invalid timestamp < 1900")
        return ""

    if DateOnly:
        return timestamp.strftime('%Y-%m-%d')

    return timestamp.strftime('%Y-%m-%d %H:%M:%S')

# Download external subtitles to temp folder
def download_file_from_Embyserver(request, filename, EmbyServer):
    path = "%s%s" % (FolderEmbyTemp, filename)
    response = EmbyServer.http.request(request, True, True)

    if response:
        writeFileBinary(path, response)
        return path

    return None

def Translate(String):
    result = Addon.getLocalizedString(String)

    if not result:
        result = xbmc.getLocalizedString(String)

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

def CreateListitem(MediaType, Data): # create listitem from Kodi data
    li = xbmcgui.ListItem(label=Data['title'], offscreen=True)
    Data['mediatype'] = MediaType
    Properties = {'IsPlayable': "true"}

    if "resume" in Data:
        Properties['resumetime'] = str(Data['resume']['position'])
        Properties['totaltime'] = str(Data['resume']['total'])
        del Data['resume']

    if "art" in Data:
        li.setArt(Data['art'])
        del Data['art']

    if 'cast' in Data:
        li.setCast(Data['cast'])
        del Data['cast']

    if 'uniqueid' in Data:
        li.setUniqueIDs(Data['uniqueid'])
        del Data['uniqueid']

    if "streamdetails" in Data:
        for key, value in list(Data['streamdetails'].items()):
            for stream in value:
                li.addStreamInfo(key, stream)

        del Data['streamdetails']

    if "showtitle" in Data:
        Data['TVshowTitle'] = Data['showtitle']
        del Data["showtitle"]

    if "firstaired" in Data:
        Data['premiered'] = Data['firstaired']
        del Data["firstaired"]

    if "specialsortepisode" in Data:
        Data['sortseason'] = Data['specialsortepisode']
        del Data["specialsortepisode"]

    if "specialsortseason" in Data:
        Data['sortepisode'] = Data['specialsortseason']
        del Data["specialsortseason"]

    if "file" in Data:
        del Data["file"]

    if "label" in Data:
        li.setLabel(Data['label'])
        del Data["label"]

    if "seasonid" in Data:
        del Data["seasonid"]

    if "episodeid" in Data:
        del Data["episodeid"]

    if "movieid" in Data:
        del Data["movieid"]

    if "musicvideoid" in Data:
        del Data["musicvideoid"]

    li.setInfo('video', Data)
    return li

def load_VideoitemFromKodiDB(MediaType, KodiId):
    Details = {}

    if MediaType == "movie":
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":%s, "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "trailer", "tagline", "plotoutline", "originaltitle",  "writer", "studio", "mpaa", "country", "imdbnumber", "set", "showlink", "top250", "votes", "sorttitle",  "dateadded", "tag", "userrating", "cast", "premiered", "setid", "art", "lastplayed", "uniqueid"]}}' % KodiId)
        Data = json.loads(result)
        Details = Data['result']['moviedetails']
    elif MediaType == "episode":
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":%s, "properties":["title", "playcount", "season", "episode", "showtitle", "plot", "rating", "resume", "streamdetails", "firstaired", "writer", "dateadded", "lastplayed",  "originaltitle", "seasonid", "specialsortepisode", "specialsortseason", "userrating", "votes", "cast", "art", "uniqueid", "file"]}}' % KodiId)
        Data = json.loads(result)
        Details = Data['result']['episodedetails']
    elif MediaType == "musicvideo":
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":%s, "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "studio", "dateadded", "tag", "userrating", "premiered", "album", "artist", "track", "art", "lastplayed"]}}' % KodiId)
        Data = json.loads(result)
        Details = Data['result']['musicvideodetails']

    return Details

def SizeToText(size):
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    suffixIndex = 0

    while size > 1024 and suffixIndex < 4:
        suffixIndex += 1
        size /= 1024.0

    return "%.*f%s" % (2, size, suffixes[suffixIndex])

def dialog(dialog_type, *args, **kwargs):
    if "line1" in kwargs:
        kwargs['message'] = kwargs['line1']
        del kwargs['line1']

    return DialogTypes[dialog_type](*args, **kwargs)

def DeleteThumbnails():
    dirs, _ = listDir('special://thumbnails/')

    for directory in dirs:
        _, thumbs = listDir('special://thumbnails/%s' % directory)
        Progress = xbmcgui.DialogProgressBG()
        Progress.create("Emby", "Delete Artwork Files: %s" % directory)
        Counter = 0
        ThumbsLen = len(thumbs)
        Increment = 0.0

        if ThumbsLen > 0:
            Increment = 100.0 / ThumbsLen

        for thumb in thumbs:
            Counter += 1
            Progress.update(int(Counter * Increment), message="Delete Artwork Files: %s%s" % (directory, thumb))
            LOG.debug("DELETE thumbnail %s" % thumb)
            delFile('special://thumbnails/%s%s' % (directory, thumb))

        Progress.close()

    LOG.warning("[ reset artwork ]")

# Copy folder content from one to another
def copytree(path, dest):
    dirs, files = listDir(path)
    mkDir(dest)

    if dirs:
        copy_recursive(path, dirs, dest)

    for Filename in files:
        CopyFile = "%s%s" % (path, Filename)

        if CopyFile.endswith('.pyo'):
            continue

        copyFile(CopyFile, "%s%s" % (dest, Filename))

    LOG.info("Copied %s" % path)

def copy_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = "%s%s" % (path, directory)
        dest_dir = "%s%s" % (dest, directory)
        mkDir(dest_dir)
        dirs2, files = listDir(dirs_dir)

        if dirs2:
            copy_recursive(dirs_dir, dirs2, dest_dir)

        for Filename in files:
            CopyFile = "%s%s" % (dirs_dir, Filename)

            if CopyFile.endswith('.pyo'):
                continue

            copyFile(CopyFile, "%s%s" % (dest_dir, Filename))

def get_device_id(reset):
    if device_id:
        return

    mkDir(FolderAddonUserdata)
    emby_guid = "%s%s" % (FolderAddonUserdata, "emby_guid")
    globals()["device_id"] = readFileString(emby_guid)

    if not device_id or reset:
        LOG.info("Generating a new GUID.")
        globals()["device_id"] = str(uuid.uuid4())
        writeFileString(emby_guid, device_id)

    if reset:  # delete login data -> force new login
        _, files = listDir(FolderAddonUserdata)

        for Filename in files:
            if Filename.startswith('servers_'):
                delFile("%s%s" % (FolderAddonUserdata, Filename))

    LOG.info("device_id loaded: %s" % device_id)

# Kodi Settings
def InitSettings():
    load_settings('TranscodeFormatVideo')
    load_settings('TranscodeFormatAudio')
    load_settings('videoBitrate')
    load_settings('audioBitrate')
    load_settings('resumeJumpBack')
    load_settings('displayMessage')
    load_settings('newvideotime')
    load_settings('newmusictime')
    load_settings('startupDelay')
    load_settings('backupPath')
    load_settings('MinimumSetup')
    load_settings('limitIndex')
    load_settings('username')
    load_settings('server')
    load_settings('deviceName')
    load_settings('useDirectPaths')
    load_settings('syncdate')
    load_settings('synctime')
    load_settings('artworkcachethreads')
    load_settings('maxnodeitems')
    load_settings_bool('syncduringplayback')
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
    load_settings_bool('transcodeH265')
    load_settings_bool('transcodeDivx')
    load_settings_bool('transcodeXvid')
    load_settings_bool('transcodeMpeg2')
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
    load_settings_bool('syncruntimelimits')
    load_settings_bool('databasevacuum')

    if not deviceNameOpt:
        globals()["device_name"] = xbmc.getInfoLabel('System.FriendlyName')
    else:
        globals()["device_name"] = device_name.encode('utf-8')  # encode special charecters
        globals()["device_name"] = device_name.replace("/", "_")

    if not device_name:
        globals()["device_name"] = "Kodi"

    if disablehttp2:
        globals()["disablehttp2"] = "true"
    else:
        globals()["disablehttp2"] = "false"

    if animateicon:
        globals()["icon"] = "special://home/addons/plugin.video.emby-next-gen/resources/icon-animated.gif"
    else:
        globals()["icon"] = "special://home/addons/plugin.video.emby-next-gen/resources/icon.png"

    globals()["limitIndex"] = int(limitIndex)
    globals()["startupDelay"] = int(startupDelay)
    globals()["videoBitrate"] = int(videoBitrate)
    globals()["audioBitrate"] = int(audioBitrate)
    globals()["artworkcachethreads"] = int(artworkcachethreads)

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
    globals()["SkipUpdateSettings"] += 1
    globals()[setting] = value
    Addon.setSetting(setting, value)

def set_settings_bool(setting, value):
    globals()["SkipUpdateSettings"] += 1
    globals()[setting] = value

    if value:
        Addon.setSetting(setting, "true")
    else:
        Addon.setSetting(setting, "false")

def get_path_type_from_item(server_id, item):
    path = None

    if item['Type'] == 'Photo' and 'Primary' in item['ImageTags']:
        path = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item['Id'], item['ImageTags']['Primary'])
        Type = "p"
    elif item['Type'] == "MusicVideo":
        Type = "M"
    elif item['Type'] == "Movie":
        Type = "m"
    elif item['Type'] == "Episode":
        Type = "e"
    elif item['Type'] == "Audio":
        path = "http://127.0.0.1:57342/a-%s-%s-%s" % (server_id, item['Id'], PathToFilenameReplaceSpecialCharecters(item['Path']))
        Type = "a"
    elif item['Type'] == "Video":
        Type = "v"
    elif item['Type'] == "Trailer":
        Type = "T"
    elif item['Type'] == "TvChannel":
        path = "http://127.0.0.1:57342/t-%s-%s-stream.ts" % (server_id, item['Id'])
        Type = "t"
    else:
        return None, None

    if 'Path' in item:
        if item['Path'].lower().endswith(".iso"):
            Type = "i"
            path = item['Path']

            if path.startswith('\\\\'):
                path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")
        else:
            if not path:
                try:
                    path = "http://127.0.0.1:57342/%s-%s-%s-%s-None-None-%s-0-1-%s-%s" % (Type, server_id, item['Id'], item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], item['MediaSources'][0]['MediaStreams'][0]['Codec'], PathToFilenameReplaceSpecialCharecters(item['Path']))
                except:
                    path = "http://127.0.0.1:57342/%s-%s-%s-%s-None-None-%s-0-1-%s-%s" % (Type, server_id, item['Id'], item['MediaSources'][0]['Id'], 0, "", PathToFilenameReplaceSpecialCharecters(item['Path']))

    return path, Type

mkDir(FolderAddonUserdata)
mkDir(FolderEmbyTemp)
mkDir('special://profile/playlists/video/')
mkDir('special://profile/playlists/music/')
mkDir(FolderAddonUserdataLibrary)
InitSettings()
set_settings_bool('artworkcacheenable', True)
get_device_id(False)
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0, 'epg': "", 'epg-version': 0, 'addons': "", 'addons-version': 0, 'viewmodes': "", 'viewmodes-version': 0, 'tv': "", 'tv-version': 0}
_, FolderDatabasefiles = listDir("special://profile/Database/")

for FolderDatabaseFilename in FolderDatabasefiles:
    if not FolderDatabaseFilename.endswith('-wal') and not FolderDatabaseFilename.endswith('-shm') and not FolderDatabaseFilename.endswith('db-journal'):
        if FolderDatabaseFilename.startswith('Textures'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['texture-version']:
                DatabaseFiles['texture'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['texture-version'] = Version
        elif FolderDatabaseFilename.startswith('MyMusic'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['music-version']:
                DatabaseFiles['music'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['music-version'] = Version
        elif FolderDatabaseFilename.startswith('MyVideos'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['video-version']:
                DatabaseFiles['video'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['video-version'] = Version
        elif FolderDatabaseFilename.startswith('EPG'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['epg-version']:
                DatabaseFiles['epg'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['epg-version'] = Version
        elif FolderDatabaseFilename.startswith('TV'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['tv-version']:
                DatabaseFiles['tv'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['tv-version'] = Version
        elif FolderDatabaseFilename.startswith('Addons'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['addons-version']:
                DatabaseFiles['addons'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['addons-version'] = Version
        elif FolderDatabaseFilename.startswith('ViewModes'):
            Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

            if Version > DatabaseFiles['viewmodes-version']:
                DatabaseFiles['viewmodes'] = translatePath("special://profile/Database/%s" % FolderDatabaseFilename)
                DatabaseFiles['viewmodes-version'] = Version

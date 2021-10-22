# -*- coding: utf-8 -*-
import os
import shutil
import uuid
import json
import threading
from datetime import datetime, timedelta
from dateutil import tz, parser
import xbmcvfs
import xbmc
import xbmcaddon
import xbmcgui
from . import loghandler

if int(xbmc.getInfoLabel('System.BuildVersion')[:2]) >= 19:
    unicode = str
    from urllib.parse import quote
    Python3 = True
else:
    from urllib import quote
    Python3 = False

if xbmc.getCondVisibility('System.HasAddon(plugin.video.emby-next-gen)'):
    Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
    PluginId = "plugin.video.emby-next-gen"
else:
    Addon = xbmcaddon.Addon("plugin.video.emby")
    PluginId = "plugin.video.emby"

LOG = loghandler.LOG('EMBY.helper.utils')
KodiDBLockMusic = threading.Lock()
KodiDBLockVideo = threading.Lock()
Dialog = xbmcgui.Dialog()
VideoBitrateOptions = [664000, 996000, 1320000, 2000000, 3200000, 4700000, 6200000, 7700000, 9200000, 10700000, 12200000, 13700000, 15200000, 16700000, 18200000, 20000000, 25000000, 30000000, 35000000, 40000000, 100000000, 1000000000]
AudioBitrateOptions = [64000, 96000, 128000, 192000, 256000, 320000, 384000, 448000, 512000]
MinimumVersion = "6.0.10"
device_name = "Kodi"
xspplaylists = False
TranscodeFormatVideo = ""
TranscodeFormatAudio = ""
videoBitrate = 0
audioBitrate = 0
VideoBitrate = 0
AudioBitrate = 0
resumeJumpBack = 0
displayMessage = 0
newvideotime = 1
newmusictime = 1
startupDelay = 0
backupPath = ""
MinimumSetup = ""
limitIndex = 10000
username = ""
serverName = ""
server = ""
deviceName = ""
compatibilitymode = False
useDirectPaths = False
menuOptions = False
newContent = False
restartMsg = False
connectMsg = False
addUsersHidden = False
enableContextDelete = False
enableContext = False
transcodeH265 = False
transcodeDivx = False
transcodeXvid = False
transcodeMpeg2 = False
enableCinema = False
askCinema = False
localTrailers = False
Trailers = False
offerDelete = False
deleteTV = False
deleteMovies = False
userRating = False
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
sslverify = False
syncDuringPlay = False
WebserverData = {}
SkipUpdateSettings = 0
device_id = ""
SyncPause = False
addon_version = Addon.getAddonInfo('version')
addon_name = Addon.getAddonInfo('name')
FolderAddonUserdata = "special://profile/addon_data/%s/" % PluginId
FolderEmbyTemp = "special://profile/addon_data/%s/temp/" % PluginId
FolderAddonUserdataLibrary = "special://profile/addon_data/%s/library/" % PluginId

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
    shutil.copy(SourcePath, DestinationPath)
    LOG.debug("copy: %s to %s" % (SourcePath, DestinationPath))

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
        infile = open(Path, "rb")
        data = infile.read()
        infile.close()
        return data

    return b""

def readFileString(Path):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')

    if os.path.isfile(Path):
        infile = open(Path, "rb")
        data = infile.read()
        infile.close()
        return data.decode('utf-8')

    return ""

def writeFileString(Path, Data):
    Data = Data.encode('utf-8')
    Path = translatePath(Path)
    Path = Path.encode('utf-8')
    outfile = open(Path, "wb")
    outfile.write(Data)
    outfile.close()

def writeFileBinary(Path, Data):
    Path = translatePath(Path)
    Path = Path.encode('utf-8')
    outfile = open(Path, "wb")
    outfile.write(Data)
    outfile.close()

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
                FilesFolders = os.path.join(FilesFolders, "".encode('utf-8'))  # add trailing /
                Folders += (FilesFolders.decode('utf-8'),)
            else:
                Files += (FilesFolders.decode('utf-8'),)

    return Folders, Files

def translatePath(Data):
    if Python3:
        return xbmcvfs.translatePath(Data)

    return StringDecode(xbmc.translatePath(Data))

def currenttime():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

def StringDecode(Data):
    if Python3:
        return Data

    try:
        Data = Data.decode('utf-8')
    except:
        Data = Data.encode('utf8').decode('utf-8')

    return Data

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

# Convert the local datetime to local
def convert_to_local(date):
    if not date:
        return ""

    if isinstance(date, int):
        date = str(date)

    if isinstance(date, (str, unicode)):
        date = parser.parse(date.encode('utf-8'))

        if not date.tzname():
            date = date.replace(tzinfo=tz.tzutc())

    timestamp = (date - datetime(1970, 1, 1, tzinfo=tz.tzutc())).total_seconds()

    if timestamp >= 0:
        timestamp = datetime.fromtimestamp(timestamp)
    else:
        timestamp = datetime(1970, 1, 1) + timedelta(seconds=int(timestamp))

    if timestamp.year < 1900:
        return ""

    return timestamp.strftime('%Y-%m-%dT%H:%M:%S')

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

    if not Python3:
        if isinstance(Path, str):
            Path = unicode(Path, 'utf-8')
            Path = Path.encode('utf-8')
            Filename = quote(Path, safe=u':/'.encode('utf-8'))
        else:
            Filename = quote(Path.encode('utf-8'), safe=u':/'.encode('utf-8'))
    else:
        Filename = quote(Path)

    while Filename.find("%") != -1:
        Pos = Filename.find("%")
        Filename = Filename.replace(Filename[Pos:Pos + 3], "_")

    return Filename

def ReplaceSpecialCharecters(Data):
    if not Python3:
        try:
            Data = unicode(Data, 'utf-8')
        except:
            pass

        Data = Data.encode('utf-8')
        Data = quote(Data, safe=u':/'.encode('utf-8'))
    else:
        Data = quote(Data)

    Data = Data.replace("%", "")
    return Data

def StringEncode(Data):
    if Python3:
        return Data

    return Data.encode('utf-8')

def CreateListitem(MediaType, Data):
    li = xbmcgui.ListItem(Data['title'])
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
    if Python3:
        if "line1" in kwargs:
            kwargs['message'] = kwargs['line1']
            del kwargs['line1']

    types = {
        'yesno': Dialog.yesno,
        'ok': Dialog.ok,
        'notification': Dialog.notification,
        'input': Dialog.input,
        'select': Dialog.select,
        'numeric': Dialog.numeric,
        'multi': Dialog.multiselect,
        'textviewer': Dialog.textviewer
    }
    return types[dialog_type](*args, **kwargs)

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
    if globals()["device_id"]:
        return

    mkDir(globals()["FolderAddonUserdata"])
    emby_guid = "%s%s" % (globals()["FolderAddonUserdata"], "emby_guid")
    globals()["device_id"] = readFileString(emby_guid)

    if not globals()["device_id"] or reset:
        LOG.info("Generating a new GUID.")
        globals()["device_id"] = str(uuid.uuid4())
        writeFileString(emby_guid, globals()["device_id"])

    LOG.info("device_id loaded: %s" % globals()["device_id"])

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
    load_settings('serverName')
    load_settings('server')
    load_settings('deviceName')
    load_settings('useDirectPaths')
    load_settings_bool('menuOptions')
    load_settings_bool('compatibilitymode')
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
    load_settings_bool('enableCinema')
    load_settings_bool('askCinema')
    load_settings_bool('localTrailers')
    load_settings_bool('Trailers')
    load_settings_bool('offerDelete')
    load_settings_bool('deleteTV')
    load_settings_bool('deleteMovies')
    load_settings_bool('userRating')
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
    load_settings_bool('sslverify')
    load_settings_bool('syncDuringPlay')
    load_settings_bool('useDirectPaths')
    globals()["VideoBitrate"] = int(VideoBitrateOptions[int(videoBitrate)])
    globals()["AudioBitrate"] = int(AudioBitrateOptions[int(audioBitrate)])

    if not globals()["deviceNameOpt"]:
        globals()["device_name"] = xbmc.getInfoLabel('System.FriendlyName')
    else:
        globals()["device_name"] = globals()["deviceName"].replace("\"", "_")
        globals()["device_name"] = device_name.replace("/", "_")

    if not globals()["device_name"]:
        globals()["device_name"] = "Kodi"

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
    path = ""

    if item['Type'] == 'Photo':
        path = "plugin://%s/?mode=photoviewer&id=%s&server=%s&imageid=%s" % (PluginId, item['Id'], server_id, item['ImageTags']['Primary'])
        return path, "picture"

    if item['Type'] == "MusicVideo":
        Type = "musicvideo"
    elif item['Type'] == "Movie":
        Type = "movie"
    elif item['Type'] == "Episode":
        Type = "episode"
    elif item['Type'] == "Audio":
        path = "http://127.0.0.1:57578/embyaudiodynamic-%s-%s-%s-%s" % (server_id, item['Id'], "audio", PathToFilenameReplaceSpecialCharecters(item['Path']))
        Type = "audio"
    elif item['Type'] == "Video":
        Type = "video"
    elif item['Type'] == "Trailer":
        Type = "trailer"
    elif item['Type'] == "TvChannel":
        Type = "tvchannel"
        path = "http://127.0.0.1:57578/embylivetv-%s-%s-stream.ts" % (server_id, item['Id'])
    else:
        return None, None

    if not path:
        if len(item['MediaSources'][0]['MediaStreams']) >= 1:
            path = "http://127.0.0.1:57578/embyvideodynamic-%s-%s-%s-%s-%s-%s-%s" % (server_id, item['Id'], Type, item['MediaSources'][0]['Id'], item['MediaSources'][0]['MediaStreams'][0]['BitRate'], item['MediaSources'][0]['MediaStreams'][0]['Codec'], PathToFilenameReplaceSpecialCharecters(item['Path']))
        else:
            path = "http://127.0.0.1:57578/embyvideodynamic-%s-%s-%s-%s-%s-%s-%s" % (server_id, item['Id'], Type, item['MediaSources'][0]['Id'], "0", "", PathToFilenameReplaceSpecialCharecters(item['Path']))

    return path, Type

mkDir(FolderAddonUserdata)
mkDir(FolderEmbyTemp)
mkDir('special://profile/playlists/video/')
mkDir('special://profile/playlists/music/')
mkDir(FolderAddonUserdataLibrary)
InitSettings()
get_device_id(False)
DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0}
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

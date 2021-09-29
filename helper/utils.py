# -*- coding: utf-8 -*-
import os
import uuid
import json
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

LOG = loghandler.LOG('EMBY.helper.utils')
Dialog = xbmcgui.Dialog()
VideoBitrateOptions = [664000, 996000, 1320000, 2000000, 3200000, 4700000, 6200000, 7700000, 9200000, 10700000, 12200000, 13700000, 15200000, 16700000, 18200000, 20000000, 25000000, 30000000, 35000000, 40000000, 100000000, 1000000000]
AudioBitrateOptions = [64000, 96000, 128000, 192000, 256000, 320000, 384000, 448000, 512000]
VideoCodecOptions = ["h264", "hevc"]
AudioCodecOptions = ["aac", "ac3"]
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
reloadskin = False
syncDuringPlay = False
VideoCodecID = ""
AudioCodecID = ""
WebserverData = {}
SkipUpdateSettings = 0
device_id = ""
SyncPause = False
STRINGS = {
    'playback_mode': 30511,
    'empty_user': 30613,
    'empty_user_pass': 30608,
    'empty_server': 30617,
    'network_credentials': 30517,
    'invalid_auth': 33009,
    'addon_mode': 33036,
    'native_mode': 33037,
    'cancel': 30606,
    'username': 30024,
    'password': 30602,
    'gathering': 33021,
    'boxsets': 30185,
    'movies': 30302,
    'tvshows': 30305,
    'fav_movies': 30180,
    'fav_tvshows': 30181,
    'fav_episodes': 30182,
    'task_success': 33203,
    'task_fail': 33204
}

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
    SearchFolders = [FolderPlaylistsVideo, FolderPlaylistsMusic]

    for SearchFolder in SearchFolders:
        _, files = xbmcvfs.listdir(SearchFolder)

        for Filename in files:
            if Filename.startswith('emby'):
                xbmcvfs.delete(os.path.join(SearchFolder, Filename))

# Remove all nodes
def delete_nodes():
    SearchFolders = [FolderLibraryVideo, FolderLibraryMusic]

    for SearchFolder in SearchFolders:
        folders, files = xbmcvfs.listdir(SearchFolder)

        for Filename in files:
            if Filename.startswith('emby'):
                xbmcvfs.delete(os.path.join(SearchFolder, Filename))

        for Foldername in folders:
            if Foldername.startswith('emby'):
                SearchSubFolder = os.path.join(SearchFolder, Foldername)
                _, subfolderfiles = xbmcvfs.listdir(SearchSubFolder)

                for SubfolderFilename in subfolderfiles:
                    xbmcvfs.delete(os.path.join(SearchSubFolder, SubfolderFilename))

                SearchLetterFolder = os.path.join(SearchSubFolder, "letter")
                _, letterfolderfiles = xbmcvfs.listdir(SearchLetterFolder)

                for LetterFilename in letterfolderfiles:
                    xbmcvfs.delete(os.path.join(SearchLetterFolder, LetterFilename))

                xbmcvfs.rmdir(SearchLetterFolder, False)
                xbmcvfs.rmdir(SearchSubFolder, False)

# Convert the local datetime to local
def convert_to_local(date):
    try:
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

        return timestamp.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as error:
        LOG.error(error)
        LOG.info("date: %s" % str(date))
        return ""

# Download external subtitles to temp folder
def download_file_from_Embyserver(request, filename, EmbyServer):
    path = os.path.join(FolderEmbyTemp, filename)
    response = EmbyServer.http.request(request, True, True)

    if response:
        outfile = xbmcvfs.File(path, "w")
        outfile.write(response)
        outfile.close()
        return path

    return None

def StringToDict(Data):
    Data = Data.replace("'", '"')
    Data = Data.replace("False", "false")
    Data = Data.replace("True", "true")
    Data = Data.replace('u"', '"')  # Python 2.X workaround
    Data = Data.replace('L, "', ', "')  # Python 2.X workaround
    Data = Data.replace('l, "', ', "')  # Python 2.X workaround
    return json.loads(Data)

def Translate(String):
    if isinstance(String, str):
        String = STRINGS[String]

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

def translatePath(Data):
    if Python3:
        return xbmcvfs.translatePath(Data)

    return xbmc.translatePath(Data)

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
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":' + KodiId + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "trailer", "tagline", "plotoutline", "originaltitle",  "writer", "studio", "mpaa", "country", "imdbnumber", "set", "showlink", "top250", "votes", "sorttitle",  "dateadded", "tag", "userrating", "cast", "premiered", "setid", "art", "lastplayed", "uniqueid"]}}')
        Data = json.loads(result)
        Details = Data['result']['moviedetails']
    elif MediaType == "episode":
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":' + KodiId + ', "properties":["title", "playcount", "season", "episode", "showtitle", "plot", "rating", "resume", "streamdetails", "firstaired", "writer", "dateadded", "lastplayed",  "originaltitle", "seasonid", "specialsortepisode", "specialsortseason", "userrating", "votes", "cast", "art", "uniqueid", "file"]}}')
        Data = json.loads(result)
        Details = Data['result']['episodedetails']
    elif MediaType == "musicvideo":
        result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":' + KodiId + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "studio", "dateadded", "tag", "userrating", "premiered", "album", "artist", "track", "art", "lastplayed"]}}')
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
    if "icon" in kwargs:
        kwargs['icon'] = kwargs['icon'].replace("{emby}", "special://home/addons/plugin.video.emby-next-gen/resources/icon.png")

    if "heading" in kwargs:
        kwargs['heading'] = kwargs['heading'].replace("{emby}", "Emby")

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
    if xbmcvfs.exists(FolderThumbnails):
        dirs, _ = xbmcvfs.listdir(FolderThumbnails)

        for directory in dirs:
            _, thumbs = xbmcvfs.listdir(os.path.join(FolderThumbnails, directory))
            Progress = xbmcgui.DialogProgressBG()
            Progress.create("Emby", "Delete Artwork Files: " + directory)
            Counter = 0
            ThumbsLen = len(thumbs)
            Increment = 0.0

            if ThumbsLen > 0:
                Increment = 100.0 / ThumbsLen

            for thumb in thumbs:
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Artwork Files: " + directory + " / " + thumb)
                LOG.debug("DELETE thumbnail %s" % thumb)
                xbmcvfs.delete(os.path.join(FolderThumbnails, directory, thumb))

            Progress.close()

    LOG.warning("[ reset artwork ]")

# Copy folder content from one to another
def copytree(path, dest):
    dirs, files = xbmcvfs.listdir(path)

    if not xbmcvfs.exists(dest):
        xbmcvfs.mkdirs(dest)

    if dirs:
        copy_recursive(path, dirs, dest)

    for Filename in files:
        copy_file(os.path.join(path, Filename), os.path.join(dest, Filename))

    LOG.info("Copied %s" % path)

def copy_recursive(path, dirs, dest):
    for directory in dirs:
        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)
        dirs2, files = xbmcvfs.listdir(dirs_dir)

        if dirs2:
            copy_recursive(dirs_dir, dirs2, dest_dir)

        for Filename in files:
            copy_file(os.path.join(dirs_dir, Filename), os.path.join(dest_dir, Filename))

# Copy specific file
def copy_file(path, dest):
    if path.endswith('.pyo'):
        return

    xbmcvfs.copy(path, dest)
    LOG.debug("copy: %s to %s" % (path, dest))

def load_DatabaseFiles():
    global DatabaseFiles
    _, FolderDatabasefiles = xbmcvfs.listdir(FolderDatabase)

    for FolderDatabaseFilename in FolderDatabasefiles:
        if not FolderDatabaseFilename.endswith('-wal') and not FolderDatabaseFilename.endswith('-shm') and not FolderDatabaseFilename.endswith('db-journal'):
            if FolderDatabaseFilename.startswith('Textures'):
                Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

                if Version > DatabaseFiles['texture-version']:
                    DatabaseFiles['texture'] = os.path.join(FolderDatabase, FolderDatabaseFilename)
                    DatabaseFiles['texture-version'] = Version
            elif FolderDatabaseFilename.startswith('MyMusic'):
                Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

                if Version > DatabaseFiles['music-version']:
                    DatabaseFiles['music'] = os.path.join(FolderDatabase, FolderDatabaseFilename)
                    DatabaseFiles['music-version'] = Version
            elif FolderDatabaseFilename.startswith('MyVideos'):
                Version = int(''.join(i for i in FolderDatabaseFilename if i.isdigit()))

                if Version > DatabaseFiles['video-version']:
                    DatabaseFiles['video'] = os.path.join(FolderDatabase, FolderDatabaseFilename)
                    DatabaseFiles['video-version'] = Version

def get_device_id(reset):
    global device_id
    global FolderAddonUserdata

    if device_id:
        return

    if not xbmcvfs.exists(FolderAddonUserdata):
        xbmcvfs.mkdir(FolderAddonUserdata)

    emby_guid = os.path.join(FolderAddonUserdata, "emby_guid")
    file_guid = xbmcvfs.File(emby_guid)
    device_id = file_guid.read()

    if not device_id or reset:
        LOG.info("Generating a new GUID.")
        device_id = str(uuid.uuid4())
        file_guid = xbmcvfs.File(emby_guid, 'w')
        file_guid.write(device_id)

    file_guid.close()
    LOG.info("device_id loaded: %s" % device_id)

def get_device_name():
    global deviceNameOpt
    global device_name

    if not deviceNameOpt:
        device_name = xbmc.getInfoLabel('System.FriendlyName')
    else:
        device_name = deviceName.replace("\"", "_")
        device_name = device_name.replace("/", "_")

    if not device_name:
        device_name = "Kodi"

# Kodi Settings
def InitSettings():
    global VideoBitrate
    global AudioBitrate
    global VideoCodecID
    global AudioCodecID
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
    load_settings_bool('reloadskin')
    load_settings_bool('getStudios')
    load_settings_bool('getTaglines')
    load_settings_bool('getOverview')
    load_settings_bool('getProductionLocations')
    load_settings_bool('getCast')
    load_settings_bool('deviceNameOpt')
    load_settings_bool('sslverify')
    load_settings_bool('syncDuringPlay')
    VideoBitrate = int(VideoBitrateOptions[int(videoBitrate)])
    AudioBitrate = int(AudioBitrateOptions[int(audioBitrate)])
    VideoCodecID = VideoCodecOptions[int(TranscodeFormatVideo)]
    AudioCodecID = AudioCodecOptions[int(TranscodeFormatAudio)]

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
    global SkipUpdateSettings
    SkipUpdateSettings += 1
    globals()[setting] = value
    Addon.setSetting(setting, value)

def set_settings_bool(setting, value):
    global SkipUpdateSettings
    SkipUpdateSettings += 1
    globals()[setting] = value

    if value:
        Addon.setSetting(setting, "true")
    else:
        Addon.setSetting(setting, "false")

if xbmc.getCondVisibility('System.HasAddon(plugin.video.emby-next-gen)'):
    Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
    PluginId = "plugin.video.emby-next-gen"
else:
    Addon = xbmcaddon.Addon("plugin.video.emby")
    PluginId = "plugin.video.emby"

FolderThumbnails = translatePath('special://thumbnails/')
FolderDatabase = translatePath("special://profile/Database/")
FolderAddonUserdata = translatePath("special://profile/addon_data/%s/" % PluginId)
FolderPlaylistsVideo = translatePath('special://profile/playlists/video/')
FolderPlaylistsMusic = translatePath('special://profile/playlists/music/')
FolderProfile = translatePath('special://profile/')
FolderXbmcLibraryVideo = translatePath("special://xbmc/system/library/video/")
FolderXbmcLibraryMusic = translatePath("special://xbmc/system/library/music/")
FolderLibraryVideo = translatePath("special://profile/library/video/")
FolderLibraryMusic = translatePath("special://profile/library/music/")
FolderEmbyTemp = translatePath("special://profile/addon_data/%s/temp/" % PluginId)
FolderAddonUserdataLibrary = translatePath("special://profile/addon_data/%s/library/" % PluginId)
FileIcon = translatePath("special://home/addons/plugin.video.emby-next-gen/resources/icon.png")
FileAddonXML = translatePath("special://home/addons/plugin.video.emby-next-gen/addon.xml")
addon_version = Addon.getAddonInfo('version')
InitSettings()
get_device_name()
get_device_id(False)
useDirectPaths = bool(Addon.getSetting('useDirectPaths') == "true")

#Create Folders
if not xbmcvfs.exists(FolderAddonUserdata):
    xbmcvfs.mkdirs(FolderAddonUserdata)

if not xbmcvfs.exists(FolderEmbyTemp):
    xbmcvfs.mkdirs(FolderEmbyTemp)

if not xbmcvfs.exists(FolderPlaylistsVideo):
    xbmcvfs.mkdirs(FolderPlaylistsVideo)

if not xbmcvfs.exists(FolderPlaylistsMusic):
    xbmcvfs.mkdirs(FolderPlaylistsMusic)

if not xbmcvfs.exists(FolderAddonUserdataLibrary):
    xbmcvfs.mkdir(FolderAddonUserdataLibrary)

DatabaseFiles = {'texture': "", 'texture-version': 0, 'music': "", 'music-version': 0, 'video': "", 'video-version': 0}
load_DatabaseFiles()

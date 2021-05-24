# -*- coding: utf-8 -*-
import json
import os
import re
import unicodedata
import uuid
import _strptime # Workaround for threads using datetime: _striptime is locked
from datetime import datetime, timedelta
from dateutil import tz, parser

try:
    from urllib import quote_plus, quote
except:
    from urllib.parse import quote_plus, quote
    unicode = str

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import xmls
from . import settings
from . import loghandler
from . import jsonrpc

class Utils():
    def __init__(self):
        self.LOG = loghandler.LOG('EMBY.helper.utils.Utils')
        self.Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
        self.Settings = settings.Settings(self.Addon)
        self.WindowID = xbmcgui.Window(10000)
        self.KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        self.STRINGS = {
            'addon_name': 29999,
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
        self.Settings.InitSettings()
        self.Dialog = xbmcgui.Dialog()
        self.DeviceName = xbmc.getInfoLabel('System.FriendlyName')
        self.DeviceID = ""
        self.device_id = self.get_device_id(False)
        self.SyncData = self.load_sync()
        self.PathVerified = False
        self.DefaultVideoSettings = None
        self.addon_name = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('name').upper()
        self.addon_version = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('version')
        self.device_name = self.get_device_name()
        self.direct_path = self.Settings.useDirectPaths == "1"
        self.device_info = {'DeviceName': self.device_name, 'Version': self.addon_version, 'DeviceId': self.device_id}
        self.Screensaver = None
        self.SyncTimestampLast = datetime.fromtimestamp(0)
        self.DatabaseFiles = self.load_DatabaseFiles()

    def load_DatabaseFiles(self):
        DatabaseFiles = {
            'emby': self.translatePath("special://database/") + "emby.db",
            'texture': "",
            'texture-version': 0,
            'music': "",
            'music-version': 0,
            'video': "",
            'video-version': 0
        }

        folder = self.translatePath("special://database/")
        _, files = xbmcvfs.listdir(folder)

        for Filename in files:
            if not Filename.endswith('-wal') and not Filename.endswith('-shm') and not Filename.endswith('db-journal'):
                if Filename.startswith('Textures'):
                    Version = int(''.join(i for i in Filename if i.isdigit()))

                    if Version > DatabaseFiles['texture-version']:
                        DatabaseFiles['texture'] = os.path.join(folder, Filename)
                        DatabaseFiles['texture-version'] = Version
                elif Filename.startswith('MyMusic'):
                    Version = int(''.join(i for i in Filename if i.isdigit()))

                    if Version > DatabaseFiles['music-version']:
                        DatabaseFiles['music'] = os.path.join(folder, Filename)
                        DatabaseFiles['music-version'] = Version
                elif Filename.startswith('MyVideos'):
                    Version = int(''.join(i for i in Filename if i.isdigit()))

                    if Version > DatabaseFiles['video-version']:
                        DatabaseFiles['video'] = os.path.join(folder, Filename)
                        DatabaseFiles['video-version'] = Version

        return DatabaseFiles

    def load_defaultvideosettings(self):
        if not self.DefaultVideoSettings: #load from file
            self.DefaultVideoSettings = xmls.Xmls(self).load_defaultvideosettings()

    def load_sync(self):
        SyncData = self.Settings.emby_servers_sync

        if not SyncData: #load from file
            path = self.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

            if not xbmcvfs.exists(path):
                xbmcvfs.mkdirs(path)

            if xbmcvfs.exists(os.path.join(path, "sync.json")):
                with open(os.path.join(path, 'sync.json'), 'rb') as infile:
                    SyncData = json.load(infile)
            else:
                SyncData = {}

            SyncData['Libraries'] = SyncData.get('Libraries', [])
            SyncData['RestorePoint'] = SyncData.get('RestorePoint', {})
            SyncData['Whitelist'] = list(set(SyncData.get('Whitelist', [])))
            SyncData['SortedViews'] = SyncData.get('SortedViews', [])
            self.Settings.emby_servers_sync = SyncData

        return SyncData

    def save_sync(self, Data, ForceSave=False):
        CurrentDate = datetime.utcnow()

        if not ForceSave:
            if (CurrentDate - self.SyncTimestampLast).seconds <= 30: #save every 30 seconds on sync progress
                return

        self.SyncTimestampLast = CurrentDate
        Data['Date'] = CurrentDate.strftime('%Y-%m-%dT%H:%M:%SZ')
        path = self.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)

        with open(os.path.join(path, 'sync.json'), 'wb') as outfile:
            output = json.dumps(Data, sort_keys=True, indent=4, ensure_ascii=False)
            outfile.write(output.encode('utf-8'))

        self.Settings.emby_servers_sync = Data
        self.SyncData = Data

    def save_last_sync(self):
        time_now = datetime.utcnow() - timedelta(minutes=2)
        last_sync = time_now.strftime('%Y-%m-%dT%H:%M:%Sz')
        self.Settings.set_settings('LastIncrementalSync', last_sync)
        self.LOG.info("--[ sync/%s ]" % last_sync)

    def get_device_id(self, reset):
        if self.DeviceID:
            return self.DeviceID

        directory = self.translatePath('special://profile/addon_data/plugin.video.emby-next-gen/')

        if not xbmcvfs.exists(directory):
            xbmcvfs.mkdir(directory)

        emby_guid = os.path.join(directory, "emby_guid")
        file_guid = xbmcvfs.File(emby_guid)
        self.DeviceID = file_guid.read()

        if not self.DeviceID or reset:
            self.LOG.info("Generating a new GUID.")
            self.DeviceID = str(self.create_id())
            file_guid = xbmcvfs.File(emby_guid, 'w')
            file_guid.write(self.DeviceID)

        file_guid.close()
        self.LOG.info("DeviceId loaded: %s" % self.DeviceID)
        return self.DeviceID

    def get_device_name(self):
        ''' Detect the device name. If deviceNameOpt, then
            use the device name in the add-on settings.
            Otherwise fallback to the Kodi device name.
        '''
        if not self.Settings.deviceNameOpt:
            device_name = self.DeviceName
        else:
            device_name = self.Settings.deviceName
            device_name = device_name.replace("\"", "_")
            device_name = device_name.replace("/", "_")

        if not device_name:
            device_name = "Kodi"

        return device_name

    def reset_device_id(self):
        self.DeviceID = ""
        self.get_device_id(True)
        self.dialog("ok", heading="{emby}", line1=self.Translate(33033))
        xbmc.executebuiltin('RestartApp')

    #Download external subtitles to temp folder
    def download_file_from_Embyserver(self, request, filename, EmbyServer):
        temp = self.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/temp/")

        if not xbmcvfs.exists(temp):
            xbmcvfs.mkdir(temp)

        path = os.path.join(temp, filename)
        response = EmbyServer.http.request(request)

        if response:
            with open(path, 'wb') as f:
                f.write(response)

            return path

        return None

    def create_id(self):
        return uuid.uuid4()

    #Find value in dictionary
    def find(self, dictData, item, beta):
        if item in dictData:
            return dictData[item], item

        for key, _ in sorted(iter(list(dictData.items())), key=lambda k_v: (k_v[1], k_v[0])):
            if re.match(key, item, re.I):
                return dictData[key], key

        if beta:
            return self.find(dictData, item.replace('beta-', ""), False)

    def dialog(self, dialog_type, *args, **kwargs):
        if "icon" in kwargs:
            kwargs['icon'] = kwargs['icon'].replace("{emby}", "special://home/addons/plugin.video.emby-next-gen/resources/icon.png")

        if "heading" in kwargs:
            kwargs['heading'] = kwargs['heading'].replace("{emby}", self.Translate('addon_name'))

        if self.KodiVersion >= 19:
            if "line1" in kwargs:
                kwargs['message'] = kwargs['line1']
                del kwargs['line1']

        types = {
            'yesno': self.Dialog.yesno,
            'ok': self.Dialog.ok,
            'notification': self.Dialog.notification,
            'input': self.Dialog.input,
            'select': self.Dialog.select,
            'numeric': self.Dialog.numeric,
            'multi': self.Dialog.multiselect,
            'textviewer': self.Dialog.textviewer
        }
        return types[dialog_type](*args, **kwargs)

    #Toggle the screensaver
    def set_screensaver(self, value):
        params = {
            'setting': "screensaver.mode",
            'value': value
        }
        result = jsonrpc.JSONRPC('Settings.setSettingValue').execute(params)
        self.Screensaver = value
        self.LOG.info("---[ screensaver/%s ] %s" % (value, result))

    #Verify if path is accessible
    def validate(self, path):
        if self.PathVerified:
            return True

        path = self.StringDecode(path)
        string = "%s %s. %s" % (self.Translate(33047), path, self.Translate(33048))

        if not os.path.supports_unicode_filenames:
            path = path.encode('utf-8')

        if not xbmcvfs.exists(path):
            self.LOG.info("Could not find %s" % path)

            if self.dialog("yesno", heading="{emby}", line1=string):
                return False

        self.PathVerified = True
        return True

    #Grab the values in the item for a list of keys {key},{key1}....
    #If the key has no brackets, the key will be passed as is
    def values(self, item, keys):
        return (item[key.replace('{', "").replace('}', "")] if isinstance(key, str) and key.startswith('{') else key for key in keys)

    #Prettify xml docs
    def indent(self, elem, level):
        try:
            i = "\n" + level * "  "

            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for elem in elem:
                    self.indent(elem, level + 1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i
        except Exception:
            return

    def write_xml(self, content, Filepath):
        try:
            with open(Filepath, 'wb') as infile:
                content = content.replace(b"'", b'"')
                content = content.replace(b'?>', b' standalone="yes" ?>', 1)
                infile.write(content)
        except Exception as error:
            self.LOG.error(error)

    #Delete objects from kodi cache
    def delete_folder(self, path):
        self.LOG.debug("--[ delete folder ]")
        delete_path = path is not None
        path = path or self.translatePath('special://temp/emby')
        dirs, files = xbmcvfs.listdir(path)
        self.delete_recursive(path, dirs)

        for Filename in files:
            xbmcvfs.delete(os.path.join(path, Filename))

        if delete_path:
            xbmcvfs.delete(path)

        self.LOG.warning("DELETE %s" % path)

    #Delete files and dirs recursively
    def delete_recursive(self, path, dirs):
        for directory in dirs:
            dirs2, files = xbmcvfs.listdir(os.path.join(path, directory))

            for Filename in files:
                xbmcvfs.delete(os.path.join(path, directory, Filename))

            self.delete_recursive(os.path.join(path, directory), dirs2)
            xbmcvfs.rmdir(os.path.join(path, directory))

    #Unzip file. zipfile module seems to fail on android with badziperror
    def unzip(self, path, dest, folder):
        path = quote_plus(path)
        root = "zip://" + path + '/'

        if folder:
            xbmcvfs.mkdir(os.path.join(dest, folder))
            dest = os.path.join(dest, folder)
            root = self.get_zip_directory(root, folder)

        dirs, files = xbmcvfs.listdir(root)

        if dirs:
            self.unzip_recursive(root, dirs, dest)

        for Filename in files:
            self.unzip_file(os.path.join(root, Filename), os.path.join(dest, Filename))

        self.LOG.warning("Unzipped %s" % path)

    def unzip_recursive(self, path, dirs, dest):
        for directory in dirs:
            dirs_dir = os.path.join(path, directory)
            dest_dir = os.path.join(dest, directory)
            xbmcvfs.mkdir(dest_dir)
            dirs2, files = xbmcvfs.listdir(dirs_dir)

            if dirs2:
                self.unzip_recursive(dirs_dir, dirs2, dest_dir)

            for Filename in files:
                self.unzip_file(os.path.join(dirs_dir, Filename), os.path.join(dest_dir, Filename))

    #Unzip specific file. Path should start with zip://
    def unzip_file(self, path, dest):
        xbmcvfs.copy(path, dest)
        self.LOG.debug("unzip: %s to %s" % (path, dest))

    def get_zip_directory(self, path, folder):
        dirs, _ = xbmcvfs.listdir(path)

        if folder in dirs:
            return os.path.join(path, folder)

        for directory in dirs:
            result = self.get_zip_directory(os.path.join(path, directory), folder)
            if result:
                return result

    #Copy folder content from one to another
    def copytree(self, path, dest):
        dirs, files = xbmcvfs.listdir(path)

        if not xbmcvfs.exists(dest):
            xbmcvfs.mkdirs(dest)

        if dirs:
            self.copy_recursive(path, dirs, dest)

        for Filename in files:
            self.copy_file(os.path.join(path, Filename), os.path.join(dest, Filename))

        self.LOG.info("Copied %s" % path)

    def copy_recursive(self, path, dirs, dest):
        for directory in dirs:
            dirs_dir = os.path.join(path, directory)
            dest_dir = os.path.join(dest, directory)
            xbmcvfs.mkdir(dest_dir)
            dirs2, files = xbmcvfs.listdir(dirs_dir)

            if dirs2:
                self.copy_recursive(dirs_dir, dirs2, dest_dir)

            for Filename in files:
                self.copy_file(os.path.join(dirs_dir, Filename), os.path.join(dest_dir, Filename))

    #Copy specific file
    def copy_file(self, path, dest):
        if path.endswith('.pyo'):
            return

        xbmcvfs.copy(path, dest)
        self.LOG.debug("copy: %s to %s" % (path, dest))

    #Delete pyo files to force Kodi to recreate them
    def delete_pyo(self, path):
        dirs, files = xbmcvfs.listdir(path)

        if dirs:
            for directory in dirs:
                self.delete_pyo(os.path.join(path, directory))

        for Filename in files:
            if Filename.endswith('.pyo'):
                xbmcvfs.delete(os.path.join(path, Filename))

    #For theme media, do not modify unless modified in TV Tunes.
    #Remove dots from the last character as windows can not have directories with dots at the end
    def normalize_string(self, text):
        text = text.replace(":", "")
        text = text.replace("/", "-")
        text = text.replace("\\", "-")
        text = text.replace("<", "")
        text = text.replace(">", "")
        text = text.replace("*", "")
        text = text.replace("?", "")
        text = text.replace('|', "")
        text = text.strip()
        text = text.rstrip('.')

        if self.KodiVersion >= 19:
            text = unicodedata.normalize('NFKD', text)
        else:
            text = unicodedata.normalize('NFKD', text).encode('utf-8')

        return text

    def direct_url(self, item):
        FilenameURL = self.PathToFilenameReplaceSpecialCharecters(item['Path'])

        if item['Type'] == 'Audio':
            Type = 'audio'
        else:
            Type = 'video'

        path = "http://127.0.0.1:57578/%s/%s-%s-stream-%s" % (Type, item['Id'], item['MediaSources'][0]['Id'], FilenameURL)
        return path

    #Split up list in pieces of size. Will generate a list of lists
    def split_list(self, itemlist):
        size = int(self.Settings.limitIndex)
        return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]

    #Convert the local datetime to local
    def convert_to_local(self, date):
        try:
            if not date:
                return ""

            if isinstance(date, int):
                date = str(date)

            if isinstance(date, (str, unicode)):
                date = parser.parse(date.encode('utf-8'))

            date = date.replace(tzinfo=tz.tzutc())
            date = date.astimezone(tz.tzlocal())
            return date.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception as error:
            self.LOG.error(error)
            self.LOG.info("date: %s" % str(date))
            return ""

    def set_queryIO(self, key):
        self.WindowID.setProperty(key, "1")

    def StringDecode(self, Data):
        if self.KodiVersion <= 18:
            try:
                Data = Data.decode('utf-8')
            except:
                Data = Data.encode('utf8').decode('utf-8')

        return Data

    def Translate(self, String):
        if isinstance(String, str):
            String = self.STRINGS[String]

        result = self.Addon.getLocalizedString(String)

        if not result:
            result = xbmc.getLocalizedString(String)

        return result

    def PathToFilenameReplaceSpecialCharecters(self, Path):
        Temp = Path
        Pos = Temp.rfind("/")

        if Pos == -1: #Windows
            Pos = Temp.rfind("\\")

        Temp = Temp[Pos + 1:]

        if self.KodiVersion <= 18:
            if isinstance(Temp, str):
                Temp = unicode(Temp, 'utf-8')
                Temp = Temp.encode('utf-8')
                Filename = quote(Temp, safe=u':/'.encode('utf-8'))
            else:
                Filename = quote(Temp.encode('utf-8'), safe=u':/'.encode('utf-8'))
        else:
            Filename = quote(Temp)

        while Filename.find("%") != -1:
            Pos = Filename.find("%")
            Filename = Filename.replace(Filename[Pos:Pos + 3], "_")

        return Filename

    def ReplaceSpecialCharecters(self, Data):
        if self.KodiVersion <= 18:
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

    def StringMod(self, Data):
        if self.KodiVersion >= 19:
            return Data

        return Data.encode('utf-8')

    def translatePath(self, Data):
        if self.KodiVersion >= 19:
            return xbmcvfs.translatePath(Data)

        return xbmc.translatePath(Data)

    def CreateListitem(self, MediaType, Data):
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

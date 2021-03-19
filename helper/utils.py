# -*- coding: utf-8 -*-
import json
import os
import re
import unicodedata
import uuid
import requests
from dateutil import tz, parser
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

try:
    from urllib import quote, quote_plus
except:
    from urllib.parse import quote, quote_plus
    unicode = str

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import loghandler

class Utils():
    def __init__(self):
        self.LOG = loghandler.LOG('EMBY.helper.utils.Utils')
        self.Dialog = xbmcgui.Dialog()
        self.DeviceName = xbmc.getInfoLabel('System.FriendlyName')
        self.WindowID = xbmcgui.Window(10000)
        self.DeviceID = ""
        self.PathVerified = False
        self.VideoBitrateOptions = [664000, 996000, 1320000, 2000000, 3200000, 4700000, 6200000, 7700000, 9200000, 10700000, 12200000, 13700000, 15200000, 16700000, 18200000, 20000000, 25000000, 30000000, 35000000, 40000000, 100000000, 1000000000]
        self.AudioBitrateOptions = [64000, 96000, 128000, 192000, 256000, 320000, 384000, 448000, 512000]
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
        self.InitSettings()
        self.addon_name = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('name').upper()
        self.addon_version = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('version')
        self.device_name = self.get_device_name()
        self.device_id = self.get_device_id(False)
        self.device_info = {'DeviceName': self.device_name, 'Version': self.addon_version, 'DeviceId': self.device_id}
        self.Screensaver = None



        self.SyncTimestampLast = datetime.datetime.fromtimestamp(0)
        self.SyncData = {}
        self.SyncData = self.get_sync()

    def get_sync(self):
        if not self.SyncData: #load from xbmc
            self.SyncData = self.window('emby.servers.sync.json')

            if not self.SyncData: #load from file
                path = self.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

                if not xbmcvfs.exists(path):
                    xbmcvfs.mkdirs(path)

                if xbmcvfs.exists(os.path.join(path, "sync.json")):
                    with open(os.path.join(path, 'sync.json'), 'rb') as infile:
                        self.SyncData = json.load(infile)
                else:
                    self.SyncData = {}

                self.SyncData['Libraries'] = self.SyncData.get('Libraries', [])
                self.SyncData['RestorePoint'] = self.SyncData.get('RestorePoint', {})
                self.SyncData['Whitelist'] = list(set(self.SyncData.get('Whitelist', [])))
                self.SyncData['SortedViews'] = self.SyncData.get('SortedViews', [])
                self.window('emby.servers.sync.json', self.SyncData)

        return self.SyncData

    def save_sync(self, Data, ForceSave=False):
        CurrentDate = datetime.datetime.utcnow()

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

        self.window('emby.servers.sync.json', Data)
        self.SyncData = Data

    def InitSettings(self):
        self.KodiVersion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        self.Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
        self.VideoBitrate = self.VideoBitrateOptions[int(self.settings('videoBitrate'))]
        self.AudioBitrate = self.AudioBitrateOptions[int(self.settings('audioBitrate'))]
        self.Screensaver = self.get_screensaver()
        self.WebserverData = self.get_web_server_data()
        self.GroupedSet = self.get_grouped_set()

    def Translate(self, String):
        if isinstance(String, str):
            String = self.STRINGS[String]

        result = self.Addon.getLocalizedString(String)

        if not result:
            result = xbmc.getLocalizedString(String)

        return result

    #Get if boxsets should be grouped
    def get_grouped_set(self):
        result = JSONRPC('Settings.GetSettingValue').execute({'setting': "videolibrary.groupmoviesets"})

        try:
            return result['result']['value']
        except:
            return False

    #Get the current screensaver value
    def get_screensaver(self):
        result = JSONRPC('Settings.getSettingValue').execute({'setting': "screensaver.mode"})

        try:
            return result['result']['value']
        except KeyError:
            return ""

    def get_device_id(self, reset):
        ''' Return the device_id if already loaded.
            It will load from emby_guid file. If it's a fresh
            setup, it will generate a new GUID to uniquely
            identify the setup for all users.
            window prop: emby_deviceId
        '''
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
        if not self.settings('deviceNameOpt.bool'):
            device_name = self.DeviceName
        else:
            device_name = self.settings('deviceName')
            device_name = device_name.replace("\"", "_")
            device_name = device_name.replace("/", "_")

        if not device_name:
            device_name = "Kodi"

        return device_name

    #Enable the webserver if not enabled. This is used to cache artwork.
    #Will only test once, if it fails, user will be notified only once
    def get_web_server_data(self):
        Data = {'Enabled' : False}
        get_setting = JSONRPC('Settings.GetSettingValue')

        if not self.get_web_server():
            set_setting = JSONRPC('Settings.SetSetingValue')
            set_setting.execute({'setting': "services.webserver", 'value': True})

            if not self.get_web_server():
#                self.dialog("ok", heading="{emby}", line1=self.Translate(33103))
                return Data

        result = get_setting.execute({'setting': "services.webserverport"})
        Data['webServerPort'] = str(result['result']['value'] or "")
        result = get_setting.execute({'setting': "services.webserverusername"})
        Data['webServerUser'] = str(result['result']['value'] or "")
        result = get_setting.execute({'setting': "services.webserverpassword"})
        Data['webServerPass'] = str(result['result']['value'] or "")
        result = get_setting.execute({'setting': "services.webserverssl"})
        Data['webServerSSL'] = (result['result']['value'] or False)
        Data['Enabled'] = True
        return Data

    def get_web_server(self):
        result = JSONRPC('Settings.GetSettingValue').execute({'setting': "services.webserver"})

        try:
            return result['result']['value']
        except (KeyError, TypeError):
            return False

    def reset_device_id(self):
        self.DeviceID = ""
        self.get_device_id(True)
        self.dialog("ok", heading="{emby}", line1=self.Translate(33033))
        xbmc.executebuiltin('RestartApp')

    #Download external subtitles to temp folder
    def download_external_subs(self, src, filename):
        temp = self.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/temp/")

        if not xbmcvfs.exists(temp):
            xbmcvfs.mkdir(temp)

        path = os.path.join(temp, filename)

        try:
            response = requests.get(src, stream)
            response.raise_for_status()
            response.encoding = 'utf-8'

            with open(path, 'wb') as f:
                f.write(response.content)

            del response
        except:
            path = None

        return path

    def StringMod(self, Data):
        if self.KodiVersion >= 19:
            return Data

        return Data.encode('utf-8')

    def StringDecode(self, Data):
        if self.KodiVersion <= 18:
            try:
                Data = Data.decode('utf-8')
            except:
                Data = Data.encode('utf8').decode('utf-8')

        return Data

    def translatePath(self, Data):
        if self.KodiVersion >= 19:
            return xbmcvfs.translatePath(Data)

        return xbmc.translatePath(Data)

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

    #Get or set window properties
    def window(self, key, value=None, clear=False):
        if clear:
            self.LOG.debug("--[ window clear: %s ]" % key)
            self.WindowID.clearProperty(key.replace('.json', "").replace('.bool', ""))
        elif value is not None:
            if key.endswith('.json'):
                key = key.replace('.json', "")
                value = json.dumps(value)
            elif key.endswith('.bool'):
                key = key.replace('.bool', "")
                value = "true" if value else "false"

            self.WindowID.setProperty(key, value)
        else:
            result = self.WindowID.getProperty(key.replace('.json', "").replace('.bool', ""))

            if result:
                if key.endswith('.json'):
                    result = json.loads(result)
                elif key.endswith('.bool'):
                    result = result in ("true", "1")

            return result

    #Get or add add-on settings.
    #getSetting returns unicode object
    def settings(self, setting, value=None):
        if value is not None:
            if setting.endswith('.bool'):
                setting = setting.replace('.bool', "")
                value = "true" if value else "false"

            self.Addon.setSetting(setting, value)
        else:
            result = self.Addon.getSetting(setting.replace('.bool', ""))

            if result and setting.endswith('.bool'):
                result = result in ("true", "1")

            return result

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

    #Data is a dictionary
    def event(self, method, data, sender="plugin.video.emby-next-gen"):
        #data = data or {"ServerId" : "default"}
        data = '"[%s]"' % json.dumps(data).replace('"', '\\"')
        xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % (sender, method, data))
        self.LOG.debug("---[ event: %s/%s ] %s" % (sender, method, data))

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
        result = JSONRPC('Settings.setSettingValue').execute(params)
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
    def split_list(self, itemlist, size):
        return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]

    #Convert the local datetime to local
    def convert_to_local(self, date):
        try:
            if not date:
                return ""

            if isinstance(date, int):
                date = str(date)

            if isinstance(date, unicode) or isinstance(date, str):
                date = parser.parse(date.encode('utf-8'))

            date = date.replace(tzinfo=tz.tzutc())
            date = date.astimezone(tz.tzlocal())
            return date.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception as error:
            self.LOG.error(error)
            self.LOG.info("date: %s" % str(date))
            return ""

class JSONRPC():
    def __init__(self, method, **kwargs):
        self.method = method
        self.params = False

        for arg in kwargs:
            self.arg = kwargs[arg]

    def _query(self):
        query = {
            'jsonrpc': "2.0",
            'id': 1,
            'method': self.method,
        }

        if self.params:
            query['params'] = self.params

        return json.dumps(query)

    def execute(self, params):
        self.params = params
        return json.loads(xbmc.executeJSONRPC(self._query()))

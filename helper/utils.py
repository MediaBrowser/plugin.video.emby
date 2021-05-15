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
    from urllib import quote_plus
except:
    from urllib.parse import quote_plus
    unicode = str

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import xmls
from . import basics
from . import loghandler

class Utils():
    def __init__(self):
        self.LOG = loghandler.LOG('EMBY.helper.utils.Utils')
        self.Basics = basics.Basics()
        self.Dialog = xbmcgui.Dialog()
        self.DeviceName = xbmc.getInfoLabel('System.FriendlyName')
        self.DeviceID = ""
        self.device_id = self.get_device_id(False)
        self.SyncData = self.load_sync()
        self.PathVerified = False
        self.VideoBitrateOptions = [664000, 996000, 1320000, 2000000, 3200000, 4700000, 6200000, 7700000, 9200000, 10700000, 12200000, 13700000, 15200000, 16700000, 18200000, 20000000, 25000000, 30000000, 35000000, 40000000, 100000000, 1000000000]
        self.AudioBitrateOptions = [64000, 96000, 128000, 192000, 256000, 320000, 384000, 448000, 512000]
        self.VideoCodecOptions = ["h264", "hevc"]
        self.AudioCodecOptions = ["aac", "ac3"]
        self.InitSettings()
        self.addon_name = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('name').upper()
        self.addon_version = xbmcaddon.Addon("plugin.video.emby-next-gen").getAddonInfo('version')
        self.device_name = self.get_device_name()
        self.direct_path = self.Basics.settings('useDirectPaths') == "1"
        self.device_info = {'DeviceName': self.device_name, 'Version': self.addon_version, 'DeviceId': self.device_id}
        self.Screensaver = None
        self.SyncTimestampLast = datetime.fromtimestamp(0)
        self.DatabaseFiles = self.load_DatabaseFiles()

    def load_DatabaseFiles(self):
        DatabaseFiles = self.Basics.window('emby.DatabaseFiles.json')

        if not DatabaseFiles: #load from file
            DatabaseFiles = {
                'emby': self.Basics.translatePath("special://database/") + "emby.db",
                'texture': "",
                'texture-version': 0,
                'music': "",
                'music-version': 0,
                'video': "",
                'video-version': 0
            }

            folder = self.Basics.translatePath("special://database/")
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
        DefaultVideoSettings = self.Basics.window('emby.kodi.get_defaultvideosettings.json')

        if not DefaultVideoSettings: #load from file
            DefaultVideoSettings = xmls.Xmls(self).load_defaultvideosettings()
            self.Basics.window('emby.kodi.get_defaultvideosettings.json', DefaultVideoSettings)

        return DefaultVideoSettings

    def load_sync(self):
        SyncData = self.Basics.window('emby.servers.sync.json')

        if not SyncData: #load from file
            path = self.Basics.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

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
            self.Basics.window('emby.servers.sync.json', SyncData)

        return SyncData

    def save_sync(self, Data, ForceSave=False):
        CurrentDate = datetime.utcnow()

        if not ForceSave:
            if (CurrentDate - self.SyncTimestampLast).seconds <= 30: #save every 30 seconds on sync progress
                return

        self.SyncTimestampLast = CurrentDate
        Data['Date'] = CurrentDate.strftime('%Y-%m-%dT%H:%M:%SZ')
        path = self.Basics.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

        if not xbmcvfs.exists(path):
            xbmcvfs.mkdirs(path)

        with open(os.path.join(path, 'sync.json'), 'wb') as outfile:
            output = json.dumps(Data, sort_keys=True, indent=4, ensure_ascii=False)
            outfile.write(output.encode('utf-8'))

        self.Basics.window('emby.servers.sync.json', Data)
        self.SyncData = Data

    def save_last_sync(self):
        time_now = datetime.utcnow() - timedelta(minutes=2)
        last_sync = time_now.strftime('%Y-%m-%dT%H:%M:%Sz')
        self.Basics.settings('LastIncrementalSync', value=last_sync)
        self.LOG.info("--[ sync/%s ]" % last_sync)

    def InitSettings(self):
        self.VideoBitrate = self.VideoBitrateOptions[int(self.Basics.settings('videoBitrate'))]
        self.AudioBitrate = self.AudioBitrateOptions[int(self.Basics.settings('audioBitrate'))]
        self.TranscodeH265 = self.Basics.settings('transcode_h265.bool')
        self.TranscodeDivx = self.Basics.settings('transcodeDivx.bool')
        self.TranscodeXvid = self.Basics.settings('transcodeXvid.bool')
        self.TranscodeMpeg2 = self.Basics.settings('transcodeMpeg2.bool')
        self.EnableCinema = self.Basics.settings('enableCinema.bool')
        self.AskCinema = self.Basics.settings('askCinema.bool')
        self.OfferDelete = self.Basics.settings('offerDelete.bool')
        self.OfferDeleteTV = self.Basics.settings('deleteTV.bool')
        self.OfferDeleteMovie = self.Basics.settings('deleteMovies.bool')
        self.UserRatingSync = self.Basics.settings('userRating.bool')
        self.EnableCoverArt = self.Basics.settings('enableCoverArt.bool')
        self.CompressArt = self.Basics.settings('compressArt.bool')
        self.VideoCodecID = self.VideoCodecOptions[int(self.Basics.settings('TranscodeFormatVideo'))]
        self.AudioCodecID = self.AudioCodecOptions[int(self.Basics.settings('TranscodeFormatAudio'))]
        self.Screensaver = self.get_screensaver()
        self.WebserverData = self.get_web_server_data()
        self.GroupedSet = self.get_grouped_set()

    #Get if boxsets should be grouped
    def get_grouped_set(self):
        result = basics.JSONRPC('Settings.GetSettingValue').execute({'setting': "videolibrary.groupmoviesets"})

        try:
            return result['result']['value']
        except:
            return False

    #Get the current screensaver value
    def get_screensaver(self):
        result = basics.JSONRPC('Settings.getSettingValue').execute({'setting': "screensaver.mode"})

        try:
            return result['result']['value']
        except KeyError:
            return ""

    def get_device_id(self, reset):
        if self.DeviceID:
            return self.DeviceID

        directory = self.Basics.translatePath('special://profile/addon_data/plugin.video.emby-next-gen/')

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
        if not self.Basics.settings('deviceNameOpt.bool'):
            device_name = self.DeviceName
        else:
            device_name = self.Basics.settings('deviceName')
            device_name = device_name.replace("\"", "_")
            device_name = device_name.replace("/", "_")

        if not device_name:
            device_name = "Kodi"

        return device_name

    #Enable the webserver if not enabled. This is used to cache artwork.
    #Will only test once, if it fails, user will be notified only once
    def get_web_server_data(self):
        Data = {'Enabled' : False}
        get_setting = basics.JSONRPC('Settings.GetSettingValue')

        if not self.get_web_server():
            set_setting = basics.JSONRPC('Settings.SetSetingValue')
            set_setting.execute({'setting': "services.webserver", 'value': True})

            if not self.get_web_server():
#                self.dialog("ok", heading="{emby}", line1=self.Basics.Translate(33103))
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
        result = basics.JSONRPC('Settings.GetSettingValue').execute({'setting': "services.webserver"})

        try:
            return result['result']['value']
        except (KeyError, TypeError):
            return False

    def reset_device_id(self):
        self.DeviceID = ""
        self.get_device_id(True)
        self.dialog("ok", heading="{emby}", line1=self.Basics.Translate(33033))
        xbmc.executebuiltin('RestartApp')

    #Download external subtitles to temp folder
    def download_file_from_Embyserver(self, request, filename, EmbyServer):
        temp = self.Basics.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/temp/")

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
            kwargs['heading'] = kwargs['heading'].replace("{emby}", self.Basics.Translate('addon_name'))

        if self.Basics.KodiVersion >= 19:
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
        result = basics.JSONRPC('Settings.setSettingValue').execute(params)
        self.Screensaver = value
        self.LOG.info("---[ screensaver/%s ] %s" % (value, result))

    #Verify if path is accessible
    def validate(self, path):
        if self.PathVerified:
            return True

        path = self.Basics.StringDecode(path)
        string = "%s %s. %s" % (self.Basics.Translate(33047), path, self.Basics.Translate(33048))

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
        path = path or self.Basics.translatePath('special://temp/emby')
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

        if self.Basics.KodiVersion >= 19:
            text = unicodedata.normalize('NFKD', text)
        else:
            text = unicodedata.normalize('NFKD', text).encode('utf-8')

        return text

    def direct_url(self, item):
        FilenameURL = self.Basics.PathToFilenameReplaceSpecialCharecters(item['Path'])

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

            if isinstance(date, (str, unicode)):
                date = parser.parse(date.encode('utf-8'))

            date = date.replace(tzinfo=tz.tzutc())
            date = date.astimezone(tz.tzlocal())
            return date.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception as error:
            self.LOG.error(error)
            self.LOG.info("date: %s" % str(date))
            return ""

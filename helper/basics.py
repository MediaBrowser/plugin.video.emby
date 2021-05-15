# -*- coding: utf-8 -*-
import json

try:
    from urllib import quote
except:
    from urllib.parse import quote
    unicode = str

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import loghandler

class Basics():
    def __init__(self):
        self.LOG = loghandler.LOG('EMBY.helper.basics.Basics')
        self.WindowID = xbmcgui.Window(10000)
        self.Addon = xbmcaddon.Addon("plugin.video.emby-next-gen")
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
    #Data is a dictionary
    def event(self, method, data):
        data = '"[%s]"' % json.dumps(data).replace('"', '\\"')
        xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen, %s, %s)' % (method, data))
        self.LOG.debug("---[ event: plugin.video.emby-next-gen/%s ] %s" % (method, data))

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

# -*- coding: utf-8 -*-
from . import loghandler
from . import jsonrpc

class Settings():
    def __init__(self, Addon):
        self.LOG = loghandler.LOG('EMBY.helper.settings.Settings')
        self.Addon = Addon
        self.VideoBitrateOptions = [664000, 996000, 1320000, 2000000, 3200000, 4700000, 6200000, 7700000, 9200000, 10700000, 12200000, 13700000, 15200000, 16700000, 18200000, 20000000, 25000000, 30000000, 35000000, 40000000, 100000000, 1000000000]
        self.AudioBitrateOptions = [64000, 96000, 128000, 192000, 256000, 320000, 384000, 448000, 512000]
        self.VideoCodecOptions = ["h264", "hevc"]
        self.AudioCodecOptions = ["aac", "ac3"]

        #Global variable
        self.emby_shouldstop = False
        self.emby_restart = False
        self.emby_servers_sync = None
        self.emby_servers = None
        self.emby_UserImage = None

        #Settings
        self.limitThreads = ""
        self.xspplaylists = False
        self.TranscodeFormatVideo = ""
        self.TranscodeFormatAudio = ""
        self.videoBitrate = ""
        self.audioBitrate = ""
        self.resumeJumpBack = ""
        self.displayMessage = ""
        self.syncProgress = ""
        self.newvideotime = ""
        self.newmusictime = ""
        self.startupDelay = ""
        self.backupPath = ""
        self.LastIncrementalSync = ""
        self.MinimumSetup = ""
        self.useDirectPaths = ""
        self.limitIndex = ""
        self.idMethod = ""
        self.username = ""
        self.connectUsername = ""
        self.serverName = ""
        self.server = ""
        self.deviceName = ""
        self.askSyncIndicator = ""
        self.Users = ""
        self.Migrate = False
        self.SyncInstallRunDone = False
        self.newContent = False
        self.restartMsg = False
        self.connectMsg = False
        self.addUsersHidden = False
        self.enableContextDelete = False
        self.enableContext = False
        self.transcodeH265 = False
        self.transcodeDivx = False
        self.transcodeXvid = False
        self.transcodeMpeg2 = False
        self.enableCinema = False
        self.askCinema = False
        self.offerDelete = False
        self.deleteTV = False
        self.deleteMovies = False
        self.userRating = False
        self.enableCoverArt = False
        self.compressArt = False
        self.getDateCreated = False
        self.getGenres = False
        self.getStudios = False
        self.getTaglines = False
        self.getOverview = False
        self.getProductionLocations = False
        self.getCast = False
        self.groupedSets = False
        self.deviceNameOpt = False
        self.sslverify = False
        self.kodiCompanion = False
        self.syncDuringPlay = False
        self.dbSyncScreensaver = False
        self.enableAddon = False
        self.ReloadSkin = False
        self.VideoBitrate = 0
        self.AudioBitrate = 0
        self.VideoCodecID = ""
        self.AudioCodecID = ""
        self.Screensaver = False
        self.WebserverData = {}
        self.GroupedSet = ""

    def InitSettings(self):
        self.load_settings('limitThreads')
        self.load_settings('TranscodeFormatVideo')
        self.load_settings('TranscodeFormatAudio')
        self.load_settings('videoBitrate')
        self.load_settings('audioBitrate')
        self.load_settings('resumeJumpBack')
        self.load_settings('displayMessage')
        self.load_settings('syncProgress')
        self.load_settings('newvideotime')
        self.load_settings('newmusictime')
        self.load_settings('startupDelay')
        self.load_settings('backupPath')
        self.load_settings('LastIncrementalSync')
        self.load_settings('MinimumSetup')
        self.load_settings('useDirectPaths')
        self.load_settings('limitIndex')
        self.load_settings('idMethod')
        self.load_settings('username')
        self.load_settings('connectUsername')
        self.load_settings('serverName')
        self.load_settings('server')
        self.load_settings('deviceName')
        self.load_settings('askSyncIndicator')
        self.load_settings('Users')
        self.load_settings_bool('xspplaylists')
        self.load_settings_bool('Migrate')
        self.load_settings_bool('SyncInstallRunDone')
        self.load_settings_bool('newContent')
        self.load_settings_bool('restartMsg')
        self.load_settings_bool('connectMsg')
        self.load_settings_bool('addUsersHidden')
        self.load_settings_bool('enableContextDelete')
        self.load_settings_bool('enableContext')
        self.load_settings_bool('transcodeH265')
        self.load_settings_bool('transcodeDivx')
        self.load_settings_bool('transcodeXvid')
        self.load_settings_bool('transcodeMpeg2')
        self.load_settings_bool('enableCinema')
        self.load_settings_bool('askCinema')
        self.load_settings_bool('offerDelete')
        self.load_settings_bool('deleteTV')
        self.load_settings_bool('deleteMovies')
        self.load_settings_bool('userRating')
        self.load_settings_bool('enableCoverArt')
        self.load_settings_bool('compressArt')
        self.load_settings_bool('getDateCreated')
        self.load_settings_bool('getGenres')
        self.load_settings_bool('getStudios')
        self.load_settings_bool('getTaglines')
        self.load_settings_bool('getOverview')
        self.load_settings_bool('getProductionLocations')
        self.load_settings_bool('getCast')
        self.load_settings_bool('groupedSets')
        self.load_settings_bool('deviceNameOpt')
        self.load_settings_bool('sslverify')
        self.load_settings_bool('kodiCompanion')
        self.load_settings_bool('syncDuringPlay')
        self.load_settings_bool('dbSyncScreensaver')
        self.load_settings_bool('enableAddon')
        self.load_settings_bool('ReloadSkin')
        self.VideoBitrate = self.VideoBitrateOptions[int(self.videoBitrate)]
        self.AudioBitrate = self.AudioBitrateOptions[int(self.audioBitrate)]
        self.VideoCodecID = self.VideoCodecOptions[int(self.TranscodeFormatVideo)]
        self.AudioCodecID = self.AudioCodecOptions[int(self.TranscodeFormatAudio)]
        self.Screensaver = self.get_screensaver()
        self.WebserverData = self.get_web_server_data()
        self.GroupedSet = self.get_grouped_set()

    def get_web_server(self):
        result = jsonrpc.JSONRPC('Settings.GetSettingValue').execute({'setting': "services.webserver"})

        try:
            return result['result']['value']
        except (KeyError, TypeError):
            return False

    #Enable the webserver if not enabled. This is used to cache artwork.
    #Will only test once, if it fails, user will be notified only once
    def get_web_server_data(self):
        Data = {'Enabled' : False}
        get_setting = jsonrpc.JSONRPC('Settings.GetSettingValue')

        if not self.get_web_server():
            set_setting = jsonrpc.JSONRPC('Settings.SetSetingValue')
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

    #Get if boxsets should be grouped
    def get_grouped_set(self):
        result = jsonrpc.JSONRPC('Settings.GetSettingValue').execute({'setting': "videolibrary.groupmoviesets"})

        try:
            return result['result']['value']
        except:
            return False

    #Get the current screensaver value
    def get_screensaver(self):
        result = jsonrpc.JSONRPC('Settings.getSettingValue').execute({'setting': "screensaver.mode"})

        try:
            return result['result']['value']
        except KeyError:
            return ""

    def load_settings_bool(self, setting):
        value = self.Addon.getSetting(setting)

        if value == "true":
            setattr(self, setting, True)
        else:
            setattr(self, setting, False)

    def load_settings(self, setting):
        value = self.Addon.getSetting(setting)
        setattr(self, setting, value)

    def set_settings(self, setting, value):
        setattr(self, setting, value)
        self.Addon.setSetting(setting, value)

    def set_settings_bool(self, setting, value):
        setattr(self, setting, value)

        if value:
            self.Addon.setSetting(setting, "true")
        else:
            self.Addon.setSetting(setting, "false")

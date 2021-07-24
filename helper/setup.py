# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs

import helper.xmls
import database.database
from . import loghandler

class Setup():
    def __init__(self, Utils):
        self.Utils = Utils
        self.LOG = loghandler.LOG('EMBY.helper.setup')
        self.LOG.info("---<[ setup ]")

    #Setup playback mode. If native mode selected, check network credentials
    def _is_mode(self):
        value = self.Utils.dialog("yesno", heading=self.Utils.Translate('playback_mode'), line1=self.Utils.Translate(33035), nolabel=self.Utils.Translate('addon_mode'), yeslabel=self.Utils.Translate('native_mode'))

        if value:
            self.Utils.Settings.set_settings('useDirectPaths', "1")
            self.Utils.direct_path = True
            self.Utils.dialog("ok", heading="{emby}", line1=self.Utils.Translate(33145))
        else:
            self.Utils.Settings.set_settings('useDirectPaths', "0")
            self.Utils.direct_path = False

    def EnableUserRating(self):
        value = self.Utils.dialog("yesno", heading="{emby}", line1="Enable userrating sync")

        if value:
            self.Utils.Settings.set_settings_bool('userRating', True)
        else:
            self.Utils.Settings.set_settings_bool('userRating', False)

    def Migrate(self):
        Done = True

        if not self.Utils.Settings.Migrate:
            Source = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby/")

            if xbmcvfs.exists(Source):
                if self.Utils.dialog("yesno", heading="{emby}", line1="Emby for Kodi 4.X version detected. Do you start the migration? (THIS CANNOT BE UNDONE, MAKE SURE YOU HAVE A BACKUP)"):
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "plugin.video.emby", "enabled": false }}')
                    Dest = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/data.json")
                    Source = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby/data.json")

                    if xbmcvfs.exists(Source):
                        self.Utils.copy_file(Source, Dest)

                    Dest = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/emby_guid")
                    Source = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby/emby_guid")

                    if xbmcvfs.exists(Source):
                        self.Utils.copy_file(Source, Dest)

                    Dest = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/settings.xml")
                    Source = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby/settings.xml")

                    if xbmcvfs.exists(Source):
                        self.Utils.copy_file(Source, Dest)

                    Dest = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/sync.json")
                    Source = self.Utils.translatePath("special://profile/addon_data/plugin.video.emby/sync.json")

                    if xbmcvfs.exists(Source):
                        self.Utils.copy_file(Source, Dest)

                    self.Utils.Settings.set_settings_bool('Migrate', True)
                    Done = False
                else:
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "plugin.video.emby-next-gen", "enabled": false}}')
                    self.Utils.Settings.set_settings_bool('Migrate', False)
                    Done = False
            else:
                self.Utils.Settings.set_settings_bool('Migrate', True)

        return Done

    def setup(self):
        minimum = "5.0.0"
        cached = self.Utils.Settings.MinimumSetup

        if cached == minimum:
            return

        self.EnableUserRating()
        self.LOG.info("Userrating: %s" % self.Utils.Settings.userRating)

        if not cached:
            self._is_mode()
            self.LOG.info("Add-on playback: %s" % self.Utils.Settings.useDirectPaths == "0")
        else:
            self.Utils.dialog("notification", heading="{emby}", message="Database reset required, please be patient!", icon="{emby}", time=15000, sound=True)
            database.database.reset(self.Utils, True)

        #Setup completed
        self.Utils.Settings.set_settings('MinimumSetup', minimum)
        self.Xmls = helper.xmls.Xmls(self.Utils)
        self.Xmls.advanced_settings()
        self.Xmls.sources()
        self.Xmls.advanced_settings_add_timeouts()

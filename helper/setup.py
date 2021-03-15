# -*- coding: utf-8 -*-
import xbmc
import xbmcvfs

import database.database
from . import loghandler

class Setup():
    def __init__(self, Service):
        self.Service = Service
        self.LOG = loghandler.LOG('EMBY.helper.setup')
        self.LOG.info("---<[ setup ]")

    #Setup playback mode. If native mode selected, check network credentials
    def _is_mode(self):
        value = self.Service.Utils.dialog("yesno", heading=self.Service.Utils.Translate('playback_mode'), line1=self.Service.Utils.Translate(33035), nolabel=self.Service.Utils.Translate('addon_mode'), yeslabel=self.Service.Utils.Translate('native_mode'))
        self.Service.Utils.settings('useDirectPaths', value="1" if value else "0")

        if value:
            self.Service.Utils.dialog("ok", heading="{emby}", line1=self.Service.Utils.Translate(33145))

    def Migrate(self):
        Done = True

        if not self.Service.Utils.settings('Migrate.bool'):
            Source = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby/")

            if xbmcvfs.exists(Source):
                if self.Service.Utils.dialog("yesno", heading="{emby}", line1="Emby for Kodi 4.X version detected. Do you start the migration? (THIS CANNOT BE UNDONE, MAKE SURE YOU HAVE A BACKUP)"):
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "plugin.video.emby", "enabled": false }}')
                    Dest = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/data.json")
                    Source = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby/data.json")

                    if xbmcvfs.exists(Source):
                        self.Service.Utils.copy_file(Source, Dest)

                    Dest = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/emby_guid")
                    Source = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby/emby_guid")

                    if xbmcvfs.exists(Source):
                        self.Service.Utils.copy_file(Source, Dest)

                    Dest = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/settings.xml")
                    Source = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby/settings.xml")

                    if xbmcvfs.exists(Source):
                        self.Service.Utils.copy_file(Source, Dest)

                    Dest = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/sync.json")
                    Source = self.Service.Utils.translatePath("special://profile/addon_data/plugin.video.emby/sync.json")

                    if xbmcvfs.exists(Source):
                        self.Service.Utils.copy_file(Source, Dest)

                    self.Service.Utils.settings('Migrate.bool', True)
                    Done = False
                else:
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "plugin.video.emby-next-gen", "enabled": false}}')
                    self.Service.Utils.settings('Migrate.bool', False)
                    Done = False
            else:
                self.Service.Utils.settings('Migrate.bool', True)

        return Done

    def setup(self):
        minimum = "5.0.0"
        cached = self.Service.Utils.settings('MinimumSetup')

        if cached == minimum:
            return

        self.Service.ReloadSkin = False

        if not cached:
            self._is_mode()
            self.LOG.info("Add-on playback: %s" % self.Service.Utils.settings('useDirectPaths') == "0")
            self._is_empty_shows()
            self.LOG.info("Sync empty shows: %s" % str(self.Service.Utils.settings('syncEmptyShows.bool')))
            self._is_multiep()
            self.LOG.info("Enable multi episode label: %s" % self.Service.Utils.settings('displayMultiEpLabel.bool'))
            self.Service.ReloadSkin = True
        else:
            self.Service.Utils.dialog("notification", heading="{emby}", message="Database reset required, please be patient!", icon="{emby}", time=15000, sound=True)
            database.database.reset(self.Service.Utils, True)
            self.Service.ReloadSkin = True

        #Setup completed
        self.Service.Utils.settings('MinimumSetup', minimum)

    def _is_empty_shows(self):
        value = self.Service.Utils.dialog("yesno", heading="{emby}", line1=self.Service.Utils.Translate(33100))
        self.Service.Utils.settings('syncEmptyShows.bool', value)

    def _is_music(self):
        value = self.Service.Utils.dialog("yesno", heading="{emby}", line1=self.Service.Utils.Translate(33039))
        self.Service.Utils.settings('enableMusic.bool', value=value)

    def _is_multiep(self):
        value = self.Service.Utils.dialog("yesno", heading="{emby}", line1=self.Service.Utils.Translate(33213))
        self.Service.Utils.settings('displayMultiEpLabel.bool', value=value)

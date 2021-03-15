# -*- coding: utf-8 -*-
#import logging

import xbmc
import xbmcvfs

import database.database
from . import translate
from . import utils

class Setup():
    def __init__(self, Utils):
        self.Utils = Utils
#        self.LOG = logging.getLogger("EMBY.setup")
#        self.LOG.info("---<[ setup ]")

    #Setup playback mode. If native mode selected, check network credentials
    def _is_mode(self):
        value = self.Utils.dialog("yesno", heading=translate._('playback_mode'), line1=translate._(33035), nolabel=translate._('addon_mode'), yeslabel=translate._('native_mode'))
        self.Utils.settings('useDirectPaths', value="1" if value else "0")

        if value:
            self.Utils.dialog("ok", heading="{emby}", line1=translate._(33145))

    def Migrate(self):
        Done = True

        if not self.Utils.settings('Migrate.bool'):
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

                    self.Utils.settings('Migrate.bool', True)
                    Done = False
                else:
                    xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": {"addonid": "plugin.video.emby-next-gen", "enabled": false}}')
                    self.Utils.settings('Migrate.bool', False)
                    Done = False
            else:
                self.Utils.settings('Migrate.bool', True)

        return Done

    def setup(self):
        minimum = "5.0.0"
        cached = self.Utils.settings('MinimumSetup')

        if cached == minimum:
            return

        self.Utils.window('emby_reloadskin.bool', False)

        if not cached:
            self._is_mode()
#            self.LOG.info("Add-on playback: %s", settings('useDirectPaths') == "0")
            self._is_empty_shows()
#            self.LOG.info("Sync empty shows: %s", str(self.Utils.settings('syncEmptyShows.bool')))
            self._is_multiep()
#            self.LOG.info("Enable multi episode label: %s", self.Utils.settings('displayMultiEpLabel.bool'))
            self.Utils.window('emby_reloadskin.bool', True)
        else:
            self.Utils.dialog("notification", heading="{emby}", message="Database reset required, please be patient!", icon="{emby}", time=15000, sound=True)
            database.database.reset(True)
            self.Utils.window('emby_reloadskin.bool', True)

        #Setup completed
        self.Utils.settings('MinimumSetup', minimum)

    def _is_empty_shows(self):
        value = self.Utils.dialog("yesno", heading="{emby}", line1=translate._(33100))
        self.Utils.settings('syncEmptyShows.bool', value)

    def _is_music(self):
        value = self.Utils.dialog("yesno", heading="{emby}", line1=translate._(33039))
        self.Utils.settings('enableMusic.bool', value=value)

    def _is_multiep(self):
        value = self.Utils.dialog("yesno", heading="{emby}", line1=translate._(33213))
        self.Utils.settings('displayMultiEpLabel.bool', value=value)

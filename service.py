# -*- coding: utf-8 -*-
import threading
import os
import xbmc
import xbmcvfs
import hooks.monitor
import database.db_open
import helper.utils as Utils
import helper.xmls as xmls
import helper.loghandler

if Utils.Python3:
    import queue as Queue
else:
    import Queue

Delay = int(Utils.startupDelay)
LOG = helper.loghandler.LOG('EMBY.entrypoint.Service')


class Service:
    def __init__(self):
        self.Monitor = None
        self.PluginCommands = Queue.Queue()

    def Startup(self):
        LOG.warning("--->>>[ Emby ]")
        Ret = setup()

        if Ret == "stop":  # db upgrade declined
            return False

        if not Ret:  # db reset required
            LOG.warning("[ Kodi restart ]")
            xbmc.executebuiltin('RestartApp')
            return False

        self.Monitor = hooks.monitor.Monitor(self.PluginCommands)
        return True

    def ServersConnect(self):
        if Delay:
            if self.Monitor.waitForAbort(Delay):
                return

        _, files = xbmcvfs.listdir(Utils.FolderAddonUserdata)
        ServersSettings = []

        for Filename in files:
            if Filename.startswith('server'):
                ServersSettings.append(os.path.join(Utils.FolderAddonUserdata, Filename))

        if not ServersSettings:  # First run
            threading.Thread(target=self.Monitor.ServerConnect, args=(None,)).start()
        else:
            for ServerSettings in ServersSettings:
                threading.Thread(target=self.Monitor.ServerConnect, args=(ServerSettings,)).start()

    def Commands(self):
        while True:
            try:
                Command = self.PluginCommands.get(timeout=1)

                if Command == "sleep":
                    xbmc.sleep(5000)
                    self.Monitor.System_OnWake()
                elif Command == "stop":
                    self.shutdown()
                    return False
                elif Command == "restart":
                    Utils.dialog("notification", heading="{emby}", message=Utils.Translate(33193), icon="{emby}", time=1000, sound=False)
                    self.shutdown()
                    LOG.warning("[ Restart emby-for-kodi-next-gen ]")
                    return True
            except Queue.Empty:
                if self.Monitor.waitForAbort(0.1):
                    self.shutdown()
                    return False

    def shutdown(self):
        LOG.warning("---<[ EXITING ]")
        Utils.SyncPause = True
        self.Monitor.QuitThreads()
        self.Monitor.EmbyServer_DisconnectAll()
        self.Monitor.libraries = {}

def setup():
    if Utils.MinimumSetup == Utils.MinimumVersion:
        return True

    cached = Utils.MinimumSetup
    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.advanced_settings()
    xmls.advanced_settings_add_timeouts()

    # Clean installation
    if not cached:
        value = Utils.dialog("yesno", heading="{emby}", line1="Enable userrating sync")

        if value:
            Utils.set_settings_bool('userRating', True)
        else:
            Utils.set_settings_bool('userRating', False)

        LOG.info("Userrating: %s" % Utils.userRating)
        value = Utils.dialog("yesno", heading=Utils.Translate('playback_mode'), line1=Utils.Translate(33035), nolabel=Utils.Translate('addon_mode'), yeslabel=Utils.Translate('native_mode'))

        if value:
            Utils.set_settings_bool('useDirectPaths', True)
            Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33145))
        else:
            Utils.set_settings_bool('useDirectPaths', False)

        LOG.info("Add-on playback: %s" % Utils.useDirectPaths == "0")
        Utils.set_settings('MinimumSetup', Utils.MinimumVersion)
        return True


    value = Utils.dialog("yesno", heading="{emby}", line1="FINAL WARNING: Complete database reset is required! If you decline, please stop here and MANUALLY downgrade to previous version.")

    if not value:
        return "stop"

    Utils.set_settings('MinimumSetup', Utils.MinimumVersion)
    Utils.dialog("notification", heading="{emby}", message="Database reset required, wait for Kodi restart", icon="{emby}", time=960000, sound=True)
    DeleteArtwork = Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33086))
    xbmc.sleep(5000)  # Give Kodi time to complete startup before reset

    # delete settings
    _, files = xbmcvfs.listdir(Utils.FolderAddonUserdata)

    for Filename in files:
        xbmcvfs.delete(os.path.join(Utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = xbmcvfs.listdir(Utils.FolderDatabase)

    for Filename in files:
        if Filename.startswith('emby'):
            xbmcvfs.delete(os.path.join(Utils.FolderDatabase, Filename))

    if DeleteArtwork:
        Utils.DeleteThumbnails()
        texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
        texturedb.delete_tables("Texture")
        database.db_open.DBClose("texture", True)

    Utils.delete_playlists()
    Utils.delete_nodes()
    LOG.info("[ complete reset ]")
    xbmc.sleep(5000)  # Give Kodi time to before restart
    return False


if __name__ == "__main__":
    serviceOBJ = Service()

    if serviceOBJ.Startup():
        while True:
            serviceOBJ.ServersConnect()  # threading

            if serviceOBJ.Commands():
                serviceOBJ.Startup()
                continue  # Restart

            break

    xbmc.log("[ emby-for-kodi-next-gen shutdown ]", xbmc.LOGWARNING)

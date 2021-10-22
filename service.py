# -*- coding: utf-8 -*-
import threading
import xbmc
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

        _, files = Utils.listDir(Utils.FolderAddonUserdata)
        ServersSettings = []

        for Filename in files:
            if Filename.startswith('server'):
                ServersSettings.append("%s%s" % (Utils.FolderAddonUserdata, Filename))

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
                    Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33193), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=1000, sound=False)
                    self.shutdown()
                    LOG.warning("[ Restart Emby-next-gen ]")
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
    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.advanced_settings()
    xmls.add_favorites()

    if Utils.MinimumSetup == Utils.MinimumVersion:
        return True

    cached = Utils.MinimumSetup

    # Clean installation
    if not cached:
        value = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33221))

        if value:
            Utils.set_settings_bool('userRating', True)
        else:
            Utils.set_settings_bool('userRating', False)

        LOG.info("Userrating: %s" % Utils.userRating)
        value = Utils.dialog("yesno", heading=Utils.Translate(30511), line1=Utils.Translate(33035), nolabel=Utils.Translate(33036), yeslabel=Utils.Translate(33037))

        if value:
            Utils.set_settings_bool('useDirectPaths', True)
            Utils.dialog("ok", heading=Utils.addon_name, line1=Utils.Translate(33145))
        else:
            Utils.set_settings_bool('useDirectPaths', False)

        LOG.info("Add-on playback: %s" % Utils.useDirectPaths == "0")
        Utils.set_settings('MinimumSetup', Utils.MinimumVersion)
        return True

    value = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33222))

    if not value:
        return "stop"

    Utils.set_settings('MinimumSetup', Utils.MinimumVersion)
    Utils.dialog("notification", heading=Utils.addon_name, message=Utils.Translate(33223), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=960000, sound=True)
    DeleteArtwork = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33086))
    xbmc.sleep(5000)  # Give Kodi time to complete startup before reset

    # delete settings
    _, files = Utils.listDir(Utils.FolderAddonUserdata)

    for Filename in files:
        Utils.delFile("%s%s" % (Utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = Utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            Utils.delFile("special://profile/Database/%s" % Filename)

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

    xbmc.log("[ Shutdown Emby-next-gen ]", xbmc.LOGWARNING)

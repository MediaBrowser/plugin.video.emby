from _thread import start_new_thread
import xbmc
import hooks.monitor
from helper import utils, xmls, loghandler, pluginmenu
from database import dbio

Monitor = hooks.monitor.monitor()  # Init Monitor
LOG = loghandler.LOG('EMBY.service')

def ServersConnect():
    if utils.startupDelay:
        if utils.sleep(utils.startupDelay):
            return

        if utils.SystemShutdown:
            utils.SyncPause = {}
            return

    _, files = utils.listDir(utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in files:
        if Filename.startswith('server'):
            ServersSettings.append("%s%s" % (utils.FolderAddonUserdata, Filename))

    if not ServersSettings:  # First run
        hooks.monitor.ServerConnect(None)
    else:
        for ServerSettings in ServersSettings:
            while not hooks.monitor.ServerConnect(ServerSettings):
                if utils.sleep(2):
                    return

    utils.StartupComplete = True

    # Shutdown
    utils.sleep(0)
    utils.SyncPause = {}
    utils.DBBusy = False
    hooks.monitor.webservice.close()
    hooks.monitor.EmbyServer_DisconnectAll()

    if utils.databasevacuum:
        start_new_thread(dbio.DBVacuum, ()) # thread vaccuum to prevent Kodi killing this task

def setup():
    # Detect corupted setting file
    if not xmls.verify_settings_file():
        if utils.sleep(10):  # Give Kodi time to load skin
            return False

        utils.Dialog.notification(heading=utils.addon_name, message="Corupted setting file detected, restore default. Restart in 5 seconds.")
        utils.delFile("%ssettings.xml" % utils.FolderAddonUserdata)

        if utils.sleep(5):
            return False

        return False

    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.add_favorites()

    if xmls.advanced_settings():
        return False

    if utils.MinimumSetup == utils.MinimumVersion:
        return True

    # Clean installation
    if not utils.MinimumSetup:
        if utils.sleep(10):  # Give Kodi time to load skin
            return False

        value = utils.Dialog.yesno(heading=utils.Translate(30511), message=utils.Translate(33035), nolabel=utils.Translate(33036), yeslabel=utils.Translate(33037))

        if value:
            utils.set_settings_bool('useDirectPaths', True)
            utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33145))
        else:
            utils.set_settings_bool('useDirectPaths', False)

        LOG.info("Add-on playback: %s" % utils.useDirectPaths == "0")
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return True

    if not utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33222)): # final warning
        return "stop"

    utils.set_settings('MinimumSetup', utils.MinimumVersion)
    pluginmenu.factoryreset()
    return False

if __name__ == "__main__":
    LOG.info("[ Start Emby-next-gen ]")
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        hooks.monitor.webservice.close()
        LOG.error("[ DB upgrade declined, Shutdown Emby-next-gen ]")
    elif not Ret:  # db reset required
        LOG.warning("[ DB reset required, Kodi restart ]")
        hooks.monitor.webservice.close()
        xbmc.executebuiltin('RestartApp')
    else:  # Regular start
        ServersConnect()  # Waiting/blocking function till Kodi stops
        LOG.warning("[ Shutdown Emby-next-gen ]")

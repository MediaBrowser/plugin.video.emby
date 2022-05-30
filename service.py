import xbmc
import hooks.monitor
from helper import utils, xmls, loghandler, pluginmenu
from database import dbio

Monitor = hooks.monitor.monitor()  # Init Monitor
LOG = loghandler.LOG('EMBY.service')

def ServersConnect():
    if utils.startupDelay:
        if utils.waitForAbort(utils.startupDelay):
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
                if utils.waitForAbort(2):
                    return

    # Shutdown
    utils.StartupComplete = True
    utils.waitForAbort()
    utils.SyncPause = {}
    utils.DBBusy = False

    if not utils.SystemShutdown:
        hooks.monitor.webservice.close()
        hooks.monitor.EmbyServer_DisconnectAll()

    utils.SystemShutdown = True

    if utils.databasevacuum:
        dbio.DBVacuum()

def setup():
    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.add_favorites()

    if xmls.advanced_settings():
        if utils.waitForAbort(5):  # Give Kodi time to complete startup before reset
            return False

        return False

    if utils.MinimumSetup == utils.MinimumVersion:
        return True

    # Clean installation
    if not utils.MinimumSetup:
        value = utils.dialog("yesno", heading=utils.Translate(30511), line1=utils.Translate(33035), nolabel=utils.Translate(33036), yeslabel=utils.Translate(33037))

        if value:
            utils.set_settings_bool('useDirectPaths', True)
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33145))
        else:
            utils.set_settings_bool('useDirectPaths', False)

        LOG.info("Add-on playback: %s" % utils.useDirectPaths == "0")
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return True

    if not utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33222)):
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

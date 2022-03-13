# -*- coding: utf-8 -*-
import xbmc
import hooks.monitor
from database import dbio
from helper import utils
from helper import xmls
from helper import loghandler

Monitor = hooks.monitor.Monitor()
LOG = loghandler.LOG('EMBY.service')


def ServersConnect():
    if utils.startupDelay:
        if Monitor.waitForAbort(utils.startupDelay):
            return

        if utils.SystemShutdown:
            return

    _, files = utils.listDir(utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in files:
        if Filename.startswith('server'):
            ServersSettings.append("%s%s" % (utils.FolderAddonUserdata, Filename))

    if not ServersSettings:  # First run
        Monitor.ServerConnect(None)
    else:
        for ServerSettings in ServersSettings:
            Monitor.ServerConnect(ServerSettings)

    # Shutdown
    Monitor.waitForAbort()

    if not utils.SystemShutdown:
        utils.SyncPause = True
        Monitor.QuitThreads()
        Monitor.EmbyServer_DisconnectAll()

def setup():
    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.add_favorites()

    if xmls.advanced_settings():
        if Monitor.waitForAbort(5):  # Give Kodi time to complete startup before reset
            return False

        return False

    if utils.MinimumSetup == utils.MinimumVersion:
        return True

    # Clean installation
    if not utils.MinimumSetup:
        value = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33221))

        if value:
            utils.set_settings_bool('userRating', True)
        else:
            utils.set_settings_bool('userRating', False)

        LOG.info("Userrating: %s" % utils.userRating)
        value = utils.dialog("yesno", heading=utils.Translate(30511), line1=utils.Translate(33035), nolabel=utils.Translate(33036), yeslabel=utils.Translate(33037))

        if value:
            utils.set_settings_bool('useDirectPaths', True)
            utils.dialog("ok", heading=utils.addon_name, line1=utils.Translate(33145))
        else:
            utils.set_settings_bool('useDirectPaths', False)

        LOG.info("Add-on playback: %s" % utils.useDirectPaths == "0")
        utils.set_settings('MinimumSetup', utils.MinimumVersion)
        return True

    value = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33222))

    if not value:
        return "stop"

    utils.set_settings('MinimumSetup', utils.MinimumVersion)
    utils.dialog("notification", heading=utils.addon_name, message=utils.Translate(33223), icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=960000, sound=True)
    DeleteArtwork = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33086))

    if Monitor.waitForAbort(5):  # Give Kodi time to complete startup before reset
        return False

    # delete settings
    _, files = utils.listDir(utils.FolderAddonUserdata)

    for Filename in files:
        utils.delFile("%s%s" % (utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            utils.delFile("special://profile/Database/%s" % Filename)

    videodb = dbio.DBOpen("video")
    videodb.common_db.delete_tables("Video")
    dbio.DBClose("video", True)
    musicdb = dbio.DBOpen("music")
    musicdb.common_db.delete_tables("Music")
    dbio.DBClose("music", True)

    if DeleteArtwork:
        utils.DeleteThumbnails()
        texturedb = dbio.DBOpen("texture")
        texturedb.delete_tables("Texture")
        dbio.DBClose("texture", True)

    utils.delete_playlists()
    utils.delete_nodes()
    LOG.info("[ complete reset ]")
    return False

if __name__ == "__main__":
    LOG.warning("[ Start Emby-next-gen ]")
    Ret = setup()

    if Ret == "stop":  # db upgrade declined
        Monitor.QuitThreads()
        LOG.error("[ DB upgrade declined, Shutdown Emby-next-gen ]")
    elif not Ret:  # db reset required
        LOG.warning("[ DB reset required, Kodi restart ]")
        Monitor.QuitThreads()
        xbmc.executebuiltin('RestartApp')
    else:  # Regular start
        ServersConnect()  # Waiting/blocking function till Kodi stops
        LOG.warning("[ Shutdown Emby-next-gen ]")

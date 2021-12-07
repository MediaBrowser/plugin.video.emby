# -*- coding: utf-8 -*-
import xbmc
import hooks.monitor
import database.db_open
import helper.utils as Utils
import helper.xmls as xmls
import helper.loghandler

Monitor = hooks.monitor.Monitor()
LOG = helper.loghandler.LOG('EMBY.service')


def ServersConnect():
    if Utils.startupDelay:
        if Monitor.waitForAbort(Utils.startupDelay):
            return

        if Utils.SystemShutdown:
            return

    _, files = Utils.listDir(Utils.FolderAddonUserdata)
    ServersSettings = []

    for Filename in files:
        if Filename.startswith('server'):
            ServersSettings.append("%s%s" % (Utils.FolderAddonUserdata, Filename))

    if not ServersSettings:  # First run
        Monitor.ServerConnect(None)
    else:
        for ServerSettings in ServersSettings:
            Monitor.ServerConnect(ServerSettings)

        xbmc.executebuiltin('UpdateLibrary(video)')

        if not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

    # Shutdown
    Monitor.waitForAbort()

    if not Utils.SystemShutdown:
        Utils.SyncPause = True
        Monitor.QuitThreads()
        Monitor.EmbyServer_DisconnectAll()

def setup():
    xmls.KodiDefaultNodes()
    xmls.sources()
    xmls.advanced_settings()
    xmls.add_favorites()

    if Utils.MinimumSetup == Utils.MinimumVersion:
        return True

    # Clean installation
    if not Utils.MinimumSetup:
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

    if Monitor.waitForAbort(5):  # Give Kodi time to complete startup before reset
        return False

    # delete settings
    _, files = Utils.listDir(Utils.FolderAddonUserdata)

    for Filename in files:
        Utils.delFile("%s%s" % (Utils.FolderAddonUserdata, Filename))

    # delete database
    _, files = Utils.listDir("special://profile/Database/")

    for Filename in files:
        if Filename.startswith('emby'):
            Utils.delFile("special://profile/Database/%s" % Filename)

    videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
    videodb.common_db.delete_tables("Video")
    database.db_open.DBClose("video", True)
    musicdb = database.db_open.DBOpen(Utils.DatabaseFiles, "music")
    musicdb.common_db.delete_tables("Music")
    database.db_open.DBClose("music", True)

    if DeleteArtwork:
        Utils.DeleteThumbnails()
        texturedb = database.db_open.DBOpen(Utils.DatabaseFiles, "texture")
        texturedb.delete_tables("Texture")
        database.db_open.DBClose("texture", True)

    Utils.delete_playlists()
    Utils.delete_nodes()
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

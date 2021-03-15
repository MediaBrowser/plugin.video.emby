# -*- coding: utf-8 -*-
import xbmc

import hooks.monitor
import database.database
import emby.views
import helper.setup
import helper.utils
import helper.xmls
import helper.loghandler

class Service():
    def __init__(self):
        self.ShouldStop = False
        self.ReloadSkin = True
        self.LOG = helper.loghandler.LOG('EMBY.entrypoint.Service')
        self.Utils = helper.utils.Utils()
        self.Setup = helper.setup.Setup(self)
        self.Delay = int(self.Utils.settings('startupDelay'))
        self.LOG.warning("--->>>[ %s ]" % self.Utils.addon_name)
        self.Monitor = hooks.monitor.Monitor(self)
        self.Views = None
        database.database.test_databases(self.Utils)
        Xmls = helper.xmls.Xmls(self.Utils)
        Xmls.advanced_settings_add_timeouts()
        self.Utils.settings('groupedSets.bool', self.Utils.GroupedSet)
        self.ServerReconnecting = {}
        self.SyncPause = False

        if not self.Setup.Migrate(): #Check Migrate
            xbmc.executebuiltin('RestartApp')
            return

    def ServerConnect(self):
        if self.Delay:
            if self.Monitor.waitForAbort(self.Delay):
                self.shutdown()
                return False

        server_id = self.Monitor.EmbyServer_Connect()
        self.Views = emby.views.Views(self, server_id)
        self.Views.verify_kodi_defaults()
        self.Views.get_nodes()

        if not server_id:
            return False

        self.Setup.setup()
        self.Monitor.LibraryLoad(server_id)
        return True

    def ServerReconnectingInProgress(self, server_id):
        if server_id in self.ServerReconnecting:
            if self.ServerReconnecting[server_id]:
                return True

        return False

    def ServerReconnect(self, server_id, Terminate=True):
        self.ServerReconnecting[server_id] = True
        self.SyncPause = False

        if Terminate:
            self.Monitor.EmbyServer[server_id].stop()
            self.Monitor.LibraryStop(server_id)

        while True:
            if self.Monitor.waitForAbort(10):
                return

            server_id = self.Monitor.EmbyServer_Connect()

            if server_id:
                self.ServerReconnecting[server_id] = False
                break

        self.Monitor.LibraryLoad(server_id)
        self.ServerReconnecting[server_id] = True

    def WatchDog(self):
        while True:
            if self.Monitor.waitForAbort(1):
                self.shutdown()
                return False

            if self.Utils.window('emby.shouldstop.bool'):
                self.ShouldStop = True

            if self.Utils.window('emby.restart.bool'):
                self.Utils.window('emby.restart.bool', False)
                self.Utils.dialog("notification", heading="{emby}", message=self.Utils.Translate(33193), icon="{emby}", time=1000, sound=False)
                self.restart()
                return True

            if self.Monitor.sleep:
                xbmc.sleep(5000)
                self.Monitor.System_OnWake(None)

            if self.ShouldStop:
                self.shutdown()
                return False

    def shutdown(self):
        self.LOG.warning("---<[ EXITING ]")
        self.SyncPause = True
        self.ShouldStop = True
        self.Monitor.QuitThreads()
        self.Monitor.EmbyServer_DisconnectAll()
        self.Monitor.LibraryStopAll()

    def restart(self):
        self.shutdown()
        self.LOG.warning("[ RESTART ]")
        properties = ["emby.restart", "emby.servers", "emby.should_stop", "emby.online", "emby.sync.pause", "emby.nodes.total", "emby.sync", "emby.pathverified", "emby.UserImage", "emby.shouldstop"]

        for server_id in self.Utils.window('emby.servers') or []:
            properties.append("emby.server.%s.state" % server_id)

        for prop in properties:
            self.Utils.window(prop, clear=True)

if __name__ == "__main__":
    serviceOBJ = Service()

    while True:
        serviceOBJ.ServerConnect()

        if serviceOBJ.WatchDog():
            continue #Restart

        break

    serviceOBJ = None

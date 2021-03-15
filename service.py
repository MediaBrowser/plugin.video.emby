# -*- coding: utf-8 -*-
import logging
import _strptime # Workaround for threads using datetime: _striptime is locked
import sys
import threading
import datetime
import xbmc

import hooks.monitor
import database.database
import emby.main
import emby.views
import helper.loghandler
import helper.setup
import helper.translate
import helper.utils

class Service():
    def __init__(self):
        helper.loghandler.reset()
        helper.loghandler.config()
        self.server_thread = []
        self.last_progress = datetime.datetime.today()
        self.last_progress_report = datetime.datetime.today()
        self.running = True
        self.LOG = logging.getLogger("EMBY.entrypoint.Service")
        self.Utils = helper.utils.Utils()
        self.Utils.window('emby_should_stop', clear=True)
        self.Utils.window('emby_sleep.bool', False)
        self.Utils.window('emby_sync_skip_resume.bool', False)
        self.profile = self.Utils.translatePath('special://profile/')
        self.Utils.window('emby_kodiProfile', value=self.profile)
        self.Utils.settings('platformDetected', self.Utils.get_platform())
        self.Utils.settings('distroDetected', self.Utils.get_distro())
        self.Utils.window('emby_reloadskin.bool', True)
        self.Setup = helper.setup.Setup(self.Utils)
        memory = xbmc.getInfoLabel('System.Memory(total)').replace('MB', "")
        self.Delay = int(self.Utils.settings('startupDelay'))
        self.LOG.warning("--->>>[ %s ]", self.Utils.get_addon_name())
        self.LOG.warning("Version: %s", self.Utils.get_version())
        self.LOG.warning("KODI Version: %s", xbmc.getInfoLabel('System.BuildVersion'))
        self.LOG.warning("Platform: %s", self.Utils.settings('platformDetected'))
        self.LOG.warning("OS: %s/%sMB", self.Utils.settings('distroDetected'), memory)
        self.LOG.warning("Python Version: %s", sys.version)
        self.Monitor = None
        Views = emby.views.Views(self.Utils)
        Views.verify_kodi_defaults()
        database.database.test_databases()

        try:
            Views.get_nodes()
        except Exception as error:
            self.LOG.error(error)

        self.Utils.window('emby.connected.bool', True)
        self.Utils.settings('groupedSets.bool', self.Utils.get_grouped_set())
        self.Utils.window('emby_playerreloadindex', '-1')

    def Start(self):
        if not self.Setup.Migrate(): #Check Migrate
            xbmc.executebuiltin('RestartApp')
            return False

        self.Monitor = hooks.monitor.Monitor()
        self.Monitor.ServiceHandle(self)
        self.Server(self.Delay)
        return True

    def WatchDog(self):
        while self.running:
            if self.Utils.window('emby_online.bool'):
                if self.profile != self.Utils.window('emby_kodiProfile'):
                    self.LOG.info("[ profile switch ] %s", self.profile)
                    break

            if self.Utils.window('emby.restart.bool'):
                self.Utils.window('emby.restart.bool', False)
                self.Utils.dialog("notification", heading="{emby}", message=helper.translate._(33193), icon="{emby}", time=1000, sound=False)
                raise Exception('RestartService')

            try:
                if xbmc.Monitor().waitForAbort(1):
                    break

                if self.Utils.window('emby_sleep.bool'):
                    self.Monitor.System_OnWake()
                    continue

                if self.Utils.window('emby_should_stop.bool'):
                    break
            except:
                break

        try:
            self.shutdown()
        except:
            raise Exception("ExitService")

    def Server(self, delay=None, close=False):
        if not self.server_thread:
            thread = StartDefaultServer(self, delay, close)
            self.server_thread.append(thread)

    def shutdown(self):
        self.LOG.warning("---<[ EXITING ]")
        self.Utils.window('emby_should_stop.bool', True)
        properties = [
            "emby_online", "emby.connected", "emby_deviceId",
            "emby_pathverified", "emby_sync", "emby.restart", "emby.sync.pause",
            "emby.server.state", "emby.server.states"
        ]

        for server in self.Utils.window('emby.server.states.json') or []:
            properties.append("emby.server.%s.state" % server)

        for prop in properties:
            self.Utils.window(prop, clear=True)

        self.Monitor.QuitThreads()
        emby.main.Emby.close_all()
        self.Monitor.LibraryStop()
        self.LOG.warning("---<<<[ %s ]", self.Utils.get_addon_name())
        helper.loghandler.reset()
        raise Exception("ExitService")

class StartDefaultServer(threading.Thread):
    def __init__(self, service, retry=None, close=False):
        self.service = service
        self.retry = retry
        self.close = close
        threading.Thread.__init__(self)
        self.start()

    #This is a thread to not block the main service thread
    def run(self):
        try:
            if 'default' in emby.main.Emby.client:
                self.service.Utils.window('emby_online', clear=True)
                emby.main.Emby().close()
                self.service.Monitor.LibraryStop()

                if self.close:
                    raise Exception("terminate default server thread")

            if self.retry and xbmc.Monitor().waitForAbort(self.retry) or not self.service.running:
                raise Exception("abort default server thread")

            self.service.Monitor.Register()
            self.service.Setup.setup()
            self.service.Monitor.LibraryLoad()
            self.service.Monitor.PlayMode = self.service.Utils.settings('useDirectPaths')
        except Exception as error:
            #LOG.error(error) # we don't really case, self.Utils.event will retrigger if need be.
            pass

        self.service.server_thread.remove(self)

if __name__ == "__main__":
    while True:
        serviceOBJ = None

        try:
            serviceOBJ = Service()

            if not serviceOBJ.Start():
                break

            serviceOBJ.WatchDog()
        except Exception as error:
            if serviceOBJ is not None:
                if 'ExitService' in error.args:
                    break
                elif 'RestartService' in error.args:
                    continue
                elif 'Unknown addon id' in error.args[0]:
                    break

# -*- coding: utf-8 -*-

#################################################################################################

import _strptime # Workaround for threads using datetime: _striptime is locked
import logging
import patch
from hooks import webservice

#################################################################################################

WEBSERVICE = webservice.WebService()
WEBSERVICE.start()
LOG = logging.getLogger("EMBY."+__name__)
PATCH = patch.Patch()
PATCH.check_update()

#################################################################################################

import json
import sys
import threading
from datetime import datetime

import xbmc
import xbmcgui

import objects
import connect
import client
import library
import setup
import patch
import requests
from views import Views, verify_kodi_defaults
from helper import _, window, settings, event, dialog, find, compare_version
from emby import Emby
from database import Database, emby_db, reset, test_databases

#################################################################################################


class Service(xbmc.Monitor):

    running = True
    library = None
    monitor = None
    connect = None
    player = None
    data = {'last_progress': datetime.today(), 'last_progress_report': datetime.today()}

    def __init__(self):
        window('emby_should_stop', clear=True)

        self['addon_version'] = client.get_version()
        self['profile'] = xbmc.translatePath('special://profile')
        self['mode'] = settings('useDirectPaths')
        self['log_level'] = settings('logLevel') or "1"
        self['auth_check'] = True
        self['enable_context'] = settings('enableContext.bool')
        self['enable_context_transcode'] = settings('enableContextTranscode.bool')
        self['kodi_companion'] = settings('kodiCompanion.bool')
        window('emby_logLevel', value=str(self['log_level']))
        window('emby_kodiProfile', value=self['profile'])
        settings('platformDetected', client.get_platform())
        settings('distroDetected', client.get_distro())
        memory = xbmc.getInfoLabel('System.Memory(total)').replace('MB', "")
        settings('lowPowered.bool', int(memory or 2961) < 2961) # Use shield (~3GB) as cutoff

        if self['enable_context']:
            window('emby_context.bool', True)
        if self['enable_context_transcode']:
            window('emby_context_transcode.bool', True)

        LOG.warn("--->>>[ %s ]", client.get_addon_name())
        LOG.warn("Version: %s", client.get_version())
        LOG.warn("KODI Version: %s", xbmc.getInfoLabel('System.BuildVersion'))
        LOG.warn("Platform: %s", settings('platformDetected'))
        LOG.warn("OS: %s/%sMB", settings('distroDetected'), memory)
        LOG.warn("Python Version: %s", sys.version)
        LOG.warn("Using dynamic paths: %s", settings('useDirectPaths') == "0")
        LOG.warn("Log Level: %s", self['log_level'])

        self.check_version()
        verify_kodi_defaults()
        test_databases()

        try:
            Views().get_nodes()
        except Exception as error:
            LOG.error(error)

        window('emby.connected.bool', True)
        settings('groupedSets.bool', objects.utils.get_grouped_set())
        xbmc.Monitor.__init__(self)

    def __shortcuts__(self, key):

        if key == 'player':
            return self.player
        elif key == 'library':
            return self.library
        elif key == 'monitor':
            return self.monitor
        elif key == 'connect':
            return self.connect

        return

    def __setitem__(self, key, value):
        self.data[key] = value

    def __getitem__(self, key):
        return self.data.get(key, self.__shortcuts__(key))

    def service(self):

        ''' Keeps the service monitor going.
            Exit on Kodi shutdown or profile switch.

            if profile switch happens more than once, 
            Threads depending on abortRequest will not trigger.
        '''
        self.monitor = objects.monitor.Monitor()
        self.monitor.service = self
        self.connect = connect.Connect()
        self.player = self['monitor'].player

        StartDefaultServer(self)

        while self.running:
            if window('emby_online.bool'):

                if self['profile'] != window('emby_kodiProfile'):
                    LOG.info("[ profile switch ] %s", self['profile'])

                    break

                if self['player'].isPlaying() and self['player'].is_playing_file(self['player'].get_playing_file()):
                    difference = datetime.today() - self['last_progress']

                    if difference.seconds > 4:
                        self['last_progress'] = datetime.today()

                        update = (datetime.today() - self['last_progress_report']).seconds > 40
                        event('ReportProgressRequested', {'Report': update})

                        if update:
                            self['last_progress_report'] = datetime.today()

            if not WEBSERVICE.is_alive():
                
                LOG.info("[ restarting due to socket disconnect ]")
                window('emby.restart.bool', True)

            if window('emby.restart.bool'):
                dialog("notification", heading="{emby}", message=_(33193), icon="{emby}", time=1000, sound=False)

                raise Exception('RestartService')

            if self.waitForAbort(1):
                break

        self.shutdown()

        raise Exception("ExitService")

    def check_version(self):

        ''' Check the database version to ensure we do not need to do a reset.
        '''
        with Database('emby') as embydb:

            version = emby_db.EmbyDatabase(embydb.cursor).get_version()
            LOG.info("---[ db/%s ]", version)

        if version and compare_version(version, "3.1.0") < 0:
            resp = dialog("yesno", heading=_('addon_name'), line1=_(33022))

            if not resp:

                LOG.warn("Database version is out of date! USER IGNORED!")
                dialog("ok", heading=_('addon_name'), line1=_(33023))

                raise Exception("User backed out of a required database reset")
            else:
                reset()

                raise Exception("Completed database reset")
    
    def onNotification(self, sender, method, data):

        ''' All notifications are sent via NotifyAll built-in or Kodi.
            Central hub.
        '''
        if sender.lower() not in ('plugin.video.emby', 'xbmc'):
            return

        if sender == 'plugin.video.emby':
            method = method.split('.')[1]

            if method not in ('ServerUnreachable', 'ServerShuttingDown', 'UserDataChanged', 'ServerConnect',
                              'LibraryChanged', 'ServerOnline', 'SyncLibrary', 'RepairLibrary', 'RemoveLibrary',
                              'EmbyConnect', 'SyncLibrarySelection', 'RepairLibrarySelection', 'AddServer',
                              'Unauthorized', 'UpdateServer', 'UserConfigurationUpdated', 'ServerRestarting',
                              'RemoveServer', 'AddLibrarySelection', 'CheckUpdate', 'RemoveLibrarySelection', 'PatchMusic',
                              'WebSocketRestarting', 'ResetUpdate', 'UserPolicyUpdated', 'SetServerSSL'):
                return

            data = json.loads(data)[0]
        else:
            if method not in ('System.OnQuit', 'System.OnSleep', 'System.OnWake', 'GUI.OnScreensaverDeactivated'):
                return

            data = json.loads(data)

        LOG.info("[ onNotification/%s/%s ]", sender, method)
        LOG.debug("[ %s: %s ] %s", sender, method, json.dumps(data, indent=4))

        if method == 'ServerOnline':
            if data.get('ServerId') is None:

                window('emby_online.bool', True)
                self['auth_check'] = True
                self['warn'] = True

                if settings('connectMsg.bool'):

                    users = Emby()['api'].get_device(window('emby_deviceId'))[0]['AdditionalUsers']
                    users = [user['UserName'] for user in users]
                    users.insert(0, settings('username').decode('utf-8'))
                    dialog("notification", heading="{emby}", message="%s %s" % (_(33000), ", ".join(users)),
                            icon="{emby}", time=1500, sound=False)

        elif method in ('ServerUnreachable', 'ServerShuttingDown'):

            if self['warn'] or data.get('ServerId'):

                self['warn'] = data.get('ServerId') is not None
                dialog("notification", heading="{emby}", message=_(33146) if data.get('ServerId') is None else _(33149), icon=xbmcgui.NOTIFICATION_ERROR)

            if data.get('ServerId') is None:
                StartDefaultServer(self, 20)

        elif method == 'Unauthorized':
            dialog("notification", heading="{emby}", message=_(33147) if data['ServerId'] is None else _(33148), icon=xbmcgui.NOTIFICATION_ERROR)

            if data.get('ServerId') is None and self['auth_check']:

                self['auth_check'] = False
                StartDefaultServer(self, 120)

        elif method == 'ServerRestarting':
            if data.get('ServerId'):
                return
            
            if settings('restartMsg.bool'):
                dialog("notification", heading="{emby}", message=_(33006), icon="{emby}")

            StartDefaultServer(self, 20)

        elif method == 'ServerConnect':
            self['connect'].register(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'EmbyConnect':
            self['connect'].setup_login_connect()

        elif method == 'AddServer':

            self['connect'].setup_manual_server()
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'RemoveServer':

            self['connect'].remove_server(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'UpdateServer':

            dialog("ok", heading="{emby}", line1=_(33151))
            self['connect'].setup_manual_server()

        elif method == 'UserDataChanged':
            if not self['library'] and data.get('ServerId') or not self['library'].started:
                return

            if data.get('UserId') != Emby()['auth/user-id']:
                return

            LOG.info("[ UserDataChanged ] %s", data)
            self['library'].userdata(data['UserDataList'])

        elif method == 'LibraryChanged' and self['library'].started:
            if data.get('ServerId') or not self['library'].started:
                return

            LOG.info("[ LibraryChanged ] %s", data)
            self['library'].updated(data['ItemsUpdated'] + data['ItemsAdded'])
            self['library'].removed(data['ItemsRemoved'])
            self['library'].delay_verify(data.get('ItemsVerify', []))

        elif method == 'WebSocketRestarting':

            if self['library']:
                try:
                    self['library'].get_fast_sync()
                except Exception as error:
                    LOG.error(error)

        elif method == 'System.OnQuit':
            window('emby_should_stop.bool', True)
            self.running = False

        elif method in ('SyncLibrarySelection', 'RepairLibrarySelection', 'AddLibrarySelection', 'RemoveLibrarySelection'):
            self['library'].select_libraries(method)

        elif method == 'SyncLibrary':
            if not data.get('Id'):
                return

            self['library'].add_library(data['Id'], data.get('Update', False))

        elif method == 'RepairLibrary':
            if not data.get('Id'):
                return

            libraries = data['Id'].split(',')

            for lib in libraries:
                self['library'].remove_library(lib)
            
            self['library'].add_library(data['Id'])

        elif method == 'RemoveLibrary':
            libraries = data['Id'].split(',')

            for lib in libraries:
                self['library'].remove_library(lib)

        elif method == 'System.OnSleep':
            
            LOG.info("-->[ sleep ]")
            window('emby_should_stop.bool', True)
            StartDefaultServer(self, close=True)

            Emby.close_all()
            self['monitor'].server = []
            self['monitor'].sleep = True

        elif method == 'System.OnWake':

            if not self['monitor'].sleep:
                LOG.warn("System.OnSleep was never called, skip System.OnWake")

                return

            LOG.info("--<[ sleep ]")
            xbmc.sleep(10000)# Allow network to wake up
            self['monitor'].sleep = False
            window('emby_should_stop', clear=True)
            StartDefaultServer(self, None)

        elif method == 'GUI.OnScreensaverDeactivated':

            LOG.info("--<[ screensaver ]")
            xbmc.sleep(5000)

            if self['library'] is not None:
                self['library'].get_fast_sync()

        elif method in ('UserConfigurationUpdated', 'UserPolicyUpdated'):

            if data.get('ServerId') is None:
                Views().get_views()

        elif method == 'CheckUpdate':

            if not PATCH.check_update(True):
                dialog("notification", heading="{emby}", message=_(21341), icon="{emby}", sound=False)
            else:
                dialog("notification", heading="{emby}", message=_(33181), icon="{emby}", sound=False)
                window('emby.restart.bool', True)

        elif method == 'ResetUpdate':
            PATCH.reset()

        elif method == 'PatchMusic':
            self['library'].run_library_task(method, data.get('Notification', True))

        elif method == 'SetServerSSL':
            self['connect'].set_ssl(data['Id'])

    def onSettingsChanged(self):

        ''' React to setting changes that impact window values.
        '''
        if window('emby_should_stop.bool'):
            return

        if settings('logLevel') != self['log_level']:

            log_level = settings('logLevel')
            window('emby_logLevel', str(log_level))
            self['logLevel'] = log_level
            LOG.warn("New log level: %s", log_level)

        if settings('enableContext.bool') != self['enable_context']:

            window('emby_context', settings('enableContext'))
            self['enable_context'] = settings('enableContext.bool')
            LOG.warn("New context setting: %s", self['enable_context'])

        if settings('enableContextTranscode.bool') != self['enable_context_transcode']:

            window('emby_context_transcode', settings('enableContextTranscode'))
            self['enable_context_transcode'] = settings('enableContextTranscode.bool')
            LOG.warn("New context transcode setting: %s", self['enable_context_transcode'])

        if settings('useDirectPaths') != self['mode'] and self['library'] and self['library'].started:

            self['mode'] = settings('useDirectPaths')
            LOG.warn("New playback mode setting: %s", self['mode'])

            if not self['mode_warn']:

                self['mode_warn'] = True
                if dialog("yesno", heading="{emby}", line1=_(33118)):
                    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.emby/?mode=reset)')

        if settings('kodiCompanion.bool') != self['kodi_companion']:
            self['kodi_companion'] = settings('kodiCompanion.bool')

            if not self['kodi_companion']:
                dialog("ok", heading="{emby}", line1=_(33138))

    def shutdown(self):

        LOG.warn("---<[ EXITING ]")
        window('emby_should_stop.bool', True)

        properties = [
            "emby.play", "emby.autoplay", "emby_online", "emby.connected", "emby.resume",
            "emby.updatewidgets", "emby.external", "emby.external_check", "emby_deviceId",
            "emby_pathverified", "emby_sync", "emby.restart", "emby.sync.pause", "emby.playlist.clear",
            "emby.server.state", "emby.server.states"
        ]
        for server in window('emby.server.states.json') or []:
            properties.append("emby.server.%s.state" % server)

        for prop in properties:
            window(prop, clear=True)

        WEBSERVICE.stop()
        Emby.close_all()

        if self['library'] is not None:
            self['library'].stop_client()

        if self['monitor'] is not None:
            self['monitor'].listener.stop()

        LOG.warn("---<<<[ %s ]", client.get_addon_name())


class StartDefaultServer(threading.Thread):

    def __init__(self, service, retry=None, close=False):

        self.service = service
        self.retry = retry
        self.close = close
        threading.Thread.__init__(self)
        self.start()

    def run(self):

        if 'default' in Emby.client:

            window('emby_online', clear=True)
            Emby().close()

            if self.service['library'] is not None:

                self.service['library'].stop_client()
                self.service['library'] = None

            if self.close:
                return

        if self.retry and self.service['monitor'].waitForAbort(self.retry) or not self.service.running:
            return
        
        try:
            self.service['connect'].register()
            setup.Setup()
            self.service['mode'] = settings('useDirectPaths')

            if self.service['library'] is None:
                self.service['library'] = library.Library(self.service)
        except Exception as error:
            LOG.error(error) # we don't really care

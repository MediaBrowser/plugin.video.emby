# -*- coding: utf-8 -*-
import json
import sys
import time

try:
    from urlparse import parse_qsl
except:
    from urllib.parse import parse_qsl

import xbmc
import xbmcgui

import helper.loghandler

class Events():
    #Parse the parameters. Reroute to our service.py
    #where user is fully identified already
    def __init__(self, Parameter):
        params = dict(parse_qsl(Parameter[2][1:]))
        Handle = int(Parameter[1])
        mode = params.get('mode')
        self.server_id = params.get('server')

        #Simple commands
        if mode == 'deviceid':
            self.event('reset_device_id', {})
            return

        if mode == 'reset':
            self.event('DatabaseReset', {})
            return

        if mode == 'login':
            self.event('ServerConnect', {'ServerId': None})
            return

        if mode == 'backup':
            self.event('Backup', {'ServerId': None})
            return

        if mode == 'restartservice':
            self.event('restartservice', {})
            return

        if mode == 'patchmusic':
            self.event('PatchMusic', {'Notification': True, 'ServerId': None})
            return

        if mode == 'settings':
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
            return

        if mode == 'texturecache':
            self.event('TextureCache', {})
            return

        if mode == 'delete':
            self.event('DeleteItem', {})
            return

        self.LOG = helper.loghandler.LOG('EMBY.Events')
        self.LOG.debug("path: %s params: %s" % (Parameter[2], json.dumps(params, indent=4)))

        #Events
        if mode == 'refreshboxsets':
            self.event('SyncLibrary', {'Id': "Boxsets: Refresh", 'ServerId': self.server_id})
        elif mode == 'nextepisodes':
            self.EmbyQueryData('nextepisodes', {'Handle': Handle, 'libraryname': params.get('libraryname')})
        elif mode == 'photoviewer':
            xbmc.executebuiltin('ShowPicture(http://127.0.0.1:57578/%s/Images/Primary)' %  params['id'])
        elif mode == 'browse':
            self.EmbyQueryData('browse', {'Handle': Handle, 'type': params.get('type'), 'id': params.get('id'), 'folder': params.get('folder'), 'name': params.get('name'), 'extra': params.get('extra')})
        elif mode == 'repairlibs':
            self.event('RepairLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'updatelibs':
            self.event('SyncLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'removelibs':
            self.event('RemoveLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'addlibs':
            self.event('AddLibrarySelection', {'ServerId': self.server_id})
        elif mode == 'addserver':
            self.event('AddServer', {'ServerId': self.server_id})
        elif mode == 'removeserver':
            self.event('RemoveServer', {'ServerId': self.server_id})
        elif mode == 'adduser':
            self.event('AddUser', {'ServerId': self.server_id})
        elif mode == 'thememedia':
            self.event('SyncThemes', {'ServerId': self.server_id})
        elif mode == 'managelibs':
            self.EmbyQueryData('manage_libraries', {'Handle': Handle})
        elif mode == 'setssl':
            self.event('SetServerSSL', {'ServerId': self.server_id})
        else:
            self.EmbyQueryData('listing', {'Handle': Handle})

    def event(self, method, data):
        data = '"[%s]"' % json.dumps(data).replace('"', '\\"')
        xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen, %s, %s)' % (method, data))

    def EmbyQueryData(self, method, Data):
        QueryID = str(round(time.time() * 100000))
        Data['QueryId'] = QueryID
        Data['ServerId'] = self.server_id
        WindowID = xbmcgui.Window(10000)
        Data = '"[%s]"' % json.dumps(Data).replace('"', '\\"')
        xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen, %s, %s)' % (method, Data))
        Ack = False

        for _ in range(10):
            for _ in range(20): #wait for ack (2 seconds timeout)
                data = WindowID.getProperty('emby_event_ack_%s' % QueryID)

                if data:
                    Ack = True
                    break

                try:
                    if xbmc.Monitor().waitForAbort(0.1):
                        WindowID.clearProperty('emby_event_ack_%s' % QueryID)
                        break
                except:
                    break

            if not Ack:
                if xbmc.Monitor().waitForAbort(1): #retry send
                    break

                xbmc.executebuiltin('NotifyAll(plugin.video.emby-next-gen, %s, %s)' % (method, Data))
            else:
                break

        if not Ack:
            WindowID.clearProperty('emby_event_ack_%s' % QueryID)
            return

        #Wait for Data
        while True:
            data = WindowID.getProperty('emby_event_%s' % QueryID)

            if data:
                break

            if xbmc.Monitor().waitForAbort(0.1):
                break

        WindowID.clearProperty('emby_event_%s' % QueryID)

if __name__ == "__main__":
    Events(sys.argv)

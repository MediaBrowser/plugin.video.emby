# -*- coding: utf-8 -*-

###############################################################################

import json
import threading
import Queue
import websocket
import ssl

import xbmc
import xbmcgui

import clientinfo
import downloadutils
import librarysync
import playlist
import userclient
import utils

import logging
logging.basicConfig()

###############################################################################


@utils.logging
@utils.ThreadMethods
class WebSocket_Client(threading.Thread):
    """
    websocket_client.WebSocket_Client(queue)

    where (communication with librarysync)
        queue:      Queue object for background sync
    """
    _shared_state = {}

    client = None
    stopWebsocket = False

    def __init__(self, queue):

        self.__dict__ = self._shared_state

        # Communication with librarysync
        self.queue = queue

        self.doUtils = downloadutils.DownloadUtils()
        self.clientInfo = clientinfo.ClientInfo()
        self.deviceId = self.clientInfo.getDeviceId()

        # 'state' that can be returned by PMS
        self.timeStates = {
            0: 'created',
            2: 'matching',
            3: 'downloading',
            4: 'loading',
            5: 'finished',
            6: 'analyzing',
            9: 'deleted'
        }

        threading.Thread.__init__(self)

    def sendProgressUpdate(self, data):
        log = self.logMsg

        log("sendProgressUpdate", 2)
        try:
            messageData = {

                'MessageType': "ReportPlaybackProgress",
                'Data': data
            }
            messageString = json.dumps(messageData)
            self.client.send(messageString)
            log("Message data: %s" % messageString, 2)

        except Exception as e:
            log("Exception: %s" % e, 1)

    def on_message(self, ws, message):
        """
        Will be called automatically if ws receives a message from PMS
        """
        try:
            message = json.loads(message)
        except Exception as e:
            self.logMsg('Error decoding message from websocket: %s' % e, -1)
            return False

        # Put PMS message on queue and let libsync take care of it
        try:
            self.queue.put(message)
            return True
        except Queue.Full:
            # Queue only takes 100 messages. No worries if we miss one or two
            self.logMsg('Queue is full, dropping PMS message', 0)
            return False

    def processing_playing(self, message):
        """
        Called when somewhere a PMS item is started, being played, stopped.

        Calls Libsync with a list of children dictionaries:
        {
          '_elementType':         e.g. 'PlaySessionStateNotification'
          'guid':                  e.g. ''
          'key':                   e.g. '/library/metadata/282300',
          'ratingKey':             e.g. '282300',
          'sessionKey':            e.g. '590',
          'state':                 e.g. 'playing', 'available', 'buffering',
                                   'stopped'
          'transcodeSession':      e.g. 'yv50n9p4cr',
          'url':                   e.g. ''
          'viewOffset':            e.g. 1878534        (INT!)
        }
        """
        children = message.get('_children')
        if not children:
            return False

    def processing_progress(self, message):
        """
        Called when a PMS items keeps getting played (resume points update)
        """

    def processing_timeline(self, message):
        """
        Called when a PMS is in the process or has updated/added/removed a
        library item
        """
        children = message.get('_children')
        if not children:
            return False
        for item in children:
            state = self.timeStates.get(item.get('state'))
        return True

    def processing_status(self, message):
        """
        Called when a PMS is scanning its libraries (to be verified)
        """


        if messageType == "Play":
            # A remote control play command has been sent from the server.
            itemIds = data['ItemIds']
            command = data['PlayCommand']

            pl = playlist.Playlist()
            dialog = xbmcgui.Dialog()

            if command == "PlayNow":
                dialog.notification(
                        heading="Emby for Kodi",
                        message="%s %s" % (len(itemIds), lang(33004)),
                        icon="special://home/addons/plugin.video.emby/icon.png",
                        sound=False)
                startat = data.get('StartPositionTicks', 0)
                pl.playAll(itemIds, startat)

            elif command == "PlayNext":
                dialog.notification(
                        heading="Emby for Kodi",
                        message="%s %s" % (len(itemIds), lang(33005)),
                        icon="special://home/addons/plugin.video.emby/icon.png",
                        sound=False)
                newplaylist = pl.modifyPlaylist(itemIds)
                player = xbmc.Player()
                if not player.isPlaying():
                    # Only start the playlist if nothing is playing
                    player.play(newplaylist)

        elif messageType == "Playstate":
            # A remote control update playstate command has been sent from the server.
            command = data['Command']
            player = xbmc.Player()

            actions = {

                'Stop': player.stop,
                'Unpause': player.pause,
                'Pause': player.pause,
                'NextTrack': player.playnext,
                'PreviousTrack': player.playprevious,
                'Seek': player.seekTime
            }
            action = actions[command]
            if command == "Seek":
                seekto = data['SeekPositionTicks']
                seektime = seekto / 10000000.0
                action(seektime)
                log("Seek to %s." % seektime, 1)
            else:
                action()
                log("Command: %s completed." % command, 1)

            window('emby_command', value="true")

        elif messageType == "UserDataChanged":
            # A user changed their personal rating for an item, or their playstate was updated
            userdata_list = data['UserDataList']
            self.librarySync.triage_items("userdata", userdata_list)

        elif messageType == "LibraryChanged":
            
            librarySync = self.librarySync
            processlist = {

                'added': data['ItemsAdded'],
                'update': data['ItemsUpdated'],
                'remove': data['ItemsRemoved']
            }
            for action in processlist:
                librarySync.triage_items(action, processlist[action])

        elif messageType == "GeneralCommand":
            
            command = data['Name']
            arguments = data['Arguments']

            if command in ('Mute', 'Unmute', 'SetVolume',
                            'SetSubtitleStreamIndex', 'SetAudioStreamIndex'):

                player = xbmc.Player()
                # These commands need to be reported back
                if command == "Mute":
                    xbmc.executebuiltin('Mute')
                elif command == "Unmute":
                    xbmc.executebuiltin('Mute')
                elif command == "SetVolume":
                    volume = arguments['Volume']
                    xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % volume)
                elif command == "SetAudioStreamIndex":
                    index = int(arguments['Index'])
                    player.setAudioStream(index - 1)
                elif command == "SetSubtitleStreamIndex":
                    embyindex = int(arguments['Index'])
                    currentFile = player.getPlayingFile()

                    mapping = window('emby_%s.indexMapping' % currentFile)
                    if mapping:
                        externalIndex = json.loads(mapping)
                        # If there's external subtitles added via playbackutils
                        for index in externalIndex:
                            if externalIndex[index] == embyindex:
                                player.setSubtitleStream(int(index))
                                break
                        else:
                            # User selected internal subtitles
                            external = len(externalIndex)
                            audioTracks = len(player.getAvailableAudioStreams())
                            player.setSubtitleStream(external + embyindex - audioTracks - 1)
                    else:
                        # Emby merges audio and subtitle index together
                        audioTracks = len(player.getAvailableAudioStreams())
                        player.setSubtitleStream(index - audioTracks - 1)

                # Let service know
                window('emby_command', value="true")

            elif command == "DisplayMessage":
                
                header = arguments['Header']
                text = arguments['Text']
                xbmcgui.Dialog().notification(
                                    heading=header,
                                    message=text,
                                    icon="special://home/addons/plugin.video.emby/icon.png",
                                    time=4000)

            elif command == "SendString":
                
                string = arguments['String']
                text = {

                    'jsonrpc': "2.0",
                    'id': 0,
                    'method': "Input.SendText",
                    'params': {

                        'text': "%s" % string,
                        'done': False
                    }
                }
                result = xbmc.executeJSONRPC(json.dumps(text))

            else:
                builtin = {

                    'ToggleFullscreen': 'Action(FullScreen)',
                    'ToggleOsdMenu': 'Action(OSD)',
                    'ToggleContextMenu': 'Action(ContextMenu)',
                    'MoveUp': 'Action(Up)',
                    'MoveDown': 'Action(Down)',
                    'MoveLeft': 'Action(Left)',
                    'MoveRight': 'Action(Right)',
                    'Select': 'Action(Select)',
                    'Back': 'Action(back)',
                    'GoHome': 'ActivateWindow(Home)',
                    'PageUp': 'Action(PageUp)',
                    'NextLetter': 'Action(NextLetter)',
                    'GoToSearch': 'VideoLibrary.Search',
                    'GoToSettings': 'ActivateWindow(Settings)',
                    'PageDown': 'Action(PageDown)',
                    'PreviousLetter': 'Action(PrevLetter)',
                    'TakeScreenshot': 'TakeScreenshot',
                    'ToggleMute': 'Mute',
                    'VolumeUp': 'Action(VolumeUp)',
                    'VolumeDown': 'Action(VolumeDown)',
                }
                action = builtin.get(command)
                if action:
                    xbmc.executebuiltin(action)

        elif messageType == "ServerRestarting":
            if utils.settings('supressRestartMsg') == "true":
                xbmcgui.Dialog().notification(
                                    heading=self.addonName,
                                    message=lang(33006),
                                    icon="special://home/addons/plugin.video.emby/icon.png")

        elif messageType == "UserConfigurationUpdated":
            # Update user data set in userclient
            userclient.UserClient().userSettings = data
            self.librarySync.refresh_views = True

    def on_close(self, ws):
        self.logMsg("Closed.", 2)

    def on_open(self, ws):
        return
        self.doUtils.postCapabilities(self.deviceId)

    def on_error(self, ws, error):
        if "10061" in str(error):
            # Server is offline
            pass
        else:
            self.logMsg("Error: %s" % error, 2)

    def run(self):

        log = self.logMsg
        window = utils.window

        # websocket.enableTrace(True)

        userId = window('currUserId')
        server = window('pms_server')
        token = window('pms_token')
        deviceId = self.deviceId

        # Get the appropriate prefix for the websocket
        if "https" in server:
            server = server.replace('https', "wss")
        else:
            server = server.replace('http', "ws")

        websocket_url = "%s/:/websockets/notifications" % server
        if token:
            websocket_url += '?X-Plex-Token=%s' % token
        log("websocket url: %s" % websocket_url, 1)

        sslopt = {}
        if utils.settings('sslverify') == "false":
            sslopt["cert_reqs"] = ssl.CERT_NONE

        self.client = websocket.WebSocketApp(
            websocket_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close)

        self.client.on_open = self.on_open
        log("----===## Starting WebSocketClient ##===----", 0)

        while not self.threadStopped():
            self.client.run_forever(ping_interval=10,
                                    sslopt=sslopt)
            xbmc.sleep(100)

        log("##===---- WebSocketClient Stopped ----===##", 0)

    def stopThread(self):
        """
        Overwrite this method from ThreadMethods to close websockets first
        """
        self.logMsg("Stopping websocket client thread.", 1)
        self.client.close()
        self._threadStopped = True

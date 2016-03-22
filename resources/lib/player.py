# -*- coding: utf-8 -*-

###############################################################################

import json
from unicodedata import normalize

import xbmc
import xbmcgui

import utils
import clientinfo
import downloadutils

from urllib import urlencode

###############################################################################


@utils.logging
class Player(xbmc.Player):

    # Borg - multiple instances, shared state
    _shared_state = {}

    played_info = {}
    playStats = {}
    currentFile = None

    def __init__(self):

        self.__dict__ = self._shared_state

        self.clientInfo = clientinfo.ClientInfo()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.xbmcplayer = xbmc.Player()

        self.logMsg("Starting playback monitor.", 2)

        # Should we start notification or is this done by Plex Companion?
        self.doNotify = False if (utils.settings('plexCompanion') == 'true') \
            else True
        if self.doNotify:
            self.logMsg("PMS notifications not done by Plex Companion", 2)
        else:
            self.logMsg("PMS notifications done by Plex Companion", 2)

    def GetPlayStats(self):
        return self.playStats

    def onPlayBackStarted(self):
        """
        Window values need to have been set in Kodimonitor.py
        """
        log = self.logMsg
        window = utils.window
        # Will be called when xbmc starts playing a file
        xbmcplayer = self.xbmcplayer
        self.stopAll()

        # Get current file
        try:
            currentFile = xbmcplayer.getPlayingFile()
            xbmc.sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                xbmc.sleep(100)
                try:
                    currentFile = xbmcplayer.getPlayingFile()
                except:
                    pass
                if count == 20:
                    log("Cancelling playback report...", 1)
                    break
                else:
                    count += 1
        if not currentFile:
            log('Error getting a currently playing file; abort reporting', -1)
            return
        currentFile = currentFile.decode('utf-8')
        # Normalize to string, because we need to use this in WINDOW(key),
        # where key can only be string
        currentFile = normalize('NFKD', currentFile).encode('ascii', 'ignore')
        log('Normalized filename: %s' % currentFile, 1)

        # Save currentFile for cleanup later and for references
        self.currentFile = currentFile
        window('plex_lastPlayedFiled', value=currentFile)
        # We may need to wait for info to be set in kodi monitor
        itemId = window("emby_%s.itemid" % currentFile)
        count = 0
        while not itemId:
            xbmc.sleep(200)
            itemId = window("emby_%s.itemid" % currentFile)
            # try 20 times or about 10 seconds
            if count == 20:
                log("Could not find itemId, cancelling playback report...", -1)
                return
            count += 1

        log("ONPLAYBACK_STARTED: %s itemid: %s" % (currentFile, itemId), 0)

        embyitem = "emby_%s" % currentFile
        runtime = window("%s.runtime" % embyitem)
        refresh_id = window("%s.refreshid" % embyitem)
        playMethod = window("%s.playmethod" % embyitem)
        itemType = window("%s.type" % embyitem)
        window('emby_skipWatched%s' % itemId, value="true")

        log("Playing itemtype is: %s" % itemType, 1)
        # Suspend library sync thread while movie is playing
        if itemType in ('movie', 'episode'):
            log("Suspending library sync while playing", 1)
            window('suspend_LibraryThread', value='true')

        customseek = window('emby_customPlaylist.seektime')
        if (window('emby_customPlaylist') == "true" and customseek):
            # Start at, when using custom playlist (play to Kodi from webclient)
            log("Seeking to: %s" % customseek, 1)
            xbmcplayer.seekTime(int(customseek))
            window('emby_customPlaylist.seektime', clear=True)

        seekTime = xbmcplayer.getTime()

        # Get playback volume
        volume_query = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "Application.GetProperties",
            "params": {
                "properties": ["volume", "muted"]
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(volume_query))
        result = json.loads(result)
        result = result.get('result')
        
        volume = result.get('volume')
        muted = result.get('muted')

        # Postdata structure to send to Emby server
        url = "{server}/:/timeline?"
        postdata = {

            'QueueableMediaTypes': "Video",
            'CanSeek': True,
            'ItemId': itemId,
            'MediaSourceId': itemId,
            'PlayMethod': playMethod,
            'VolumeLevel': volume,
            'PositionTicks': int(seekTime * 10000000),
            'IsMuted': muted
        }

        # Get the current audio track and subtitles
        if playMethod == "Transcode":
            # property set in PlayUtils.py
            postdata['AudioStreamIndex'] = window("%sAudioStreamIndex" % currentFile)
            postdata['SubtitleStreamIndex'] = window("%sSubtitleStreamIndex" % currentFile)
        else:
            # Get the current kodi audio and subtitles and convert to Emby equivalent
            tracks_query = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "Player.GetProperties",
                "params": {

                    "playerid": 1,
                    "properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]
                }
            }
            result = xbmc.executeJSONRPC(json.dumps(tracks_query))
            result = json.loads(result)
            result = result.get('result')

            try: # Audio tracks
                indexAudio = result['currentaudiostream']['index']
            except (KeyError, TypeError):
                indexAudio = 0
            
            try: # Subtitles tracks
                indexSubs = result['currentsubtitle']['index']
            except (KeyError, TypeError):
                indexSubs = 0

            try: # If subtitles are enabled
                subsEnabled = result['subtitleenabled']
            except (KeyError, TypeError):
                subsEnabled = ""

            # Postdata for the audio
            postdata['AudioStreamIndex'] = indexAudio + 1
            
            # Postdata for the subtitles
            if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                
                # Number of audiotracks to help get Emby Index
                audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                mapping = window("%s.indexMapping" % embyitem)

                if mapping: # Set in playbackutils.py
                    
                    log("Mapping for external subtitles index: %s" % mapping, 2)
                    externalIndex = json.loads(mapping)

                    if externalIndex.get(str(indexSubs)):
                        # If the current subtitle is in the mapping
                        postdata['SubtitleStreamIndex'] = externalIndex[str(indexSubs)]
                    else:
                        # Internal subtitle currently selected
                        subindex = indexSubs - len(externalIndex) + audioTracks + 1
                        postdata['SubtitleStreamIndex'] = subindex
                
                else: # Direct paths enabled scenario or no external subtitles set
                    postdata['SubtitleStreamIndex'] = indexSubs + audioTracks + 1
            else:
                postdata['SubtitleStreamIndex'] = ""
        

        # Post playback to server
        # log("Sending POST play started: %s." % postdata, 2)
        # self.doUtils(url, postBody=postdata, type="POST")
        
        # Ensure we do have a runtime
        try:
            runtime = int(runtime)
        except ValueError:
            runtime = xbmcplayer.getTotalTime()
            log("Runtime is missing, Kodi runtime: %s" % runtime, 1)

        playQueueVersion = window('playQueueVersion')
        playQueueID = window('playQueueID')
        playQueueItemID = window('plex_%s.playQueueItemID' % currentFile)
        # Save data map for updates and position calls
        data = {
            'playQueueVersion': playQueueVersion,
            'playQueueID': playQueueID,
            'playQueueItemID': playQueueItemID,
            'runtime': runtime * 1000,
            'item_id': itemId,
            'refresh_id': refresh_id,
            'currentfile': currentFile,
            'AudioStreamIndex': postdata['AudioStreamIndex'],
            'SubtitleStreamIndex': postdata['SubtitleStreamIndex'],
            'playmethod': playMethod,
            'Type': itemType,
            'currentPosition': int(seekTime)
        }
        
        self.played_info[currentFile] = data
        log("ADDING_FILE: %s" % self.played_info, 1)

        # log some playback stats
        '''if(itemType != None):
            if(self.playStats.get(itemType) != None):
                count = self.playStats.get(itemType) + 1
                self.playStats[itemType] = count
            else:
                self.playStats[itemType] = 1
                
        if(playMethod != None):
            if(self.playStats.get(playMethod) != None):
                count = self.playStats.get(playMethod) + 1
                self.playStats[playMethod] = count
            else:
                self.playStats[playMethod] = 1'''

    def reportPlayback(self):
        # Don't use if Plex Companion is enabled
        if not self.doNotify:
            return

        log = self.logMsg

        log("reportPlayback Called", 2)

        # Get current file
        currentFile = self.currentFile
        data = self.played_info.get(currentFile)

        # only report playback if emby has initiated the playback (item_id has value)
        if data:
            # Get playback inforation
            itemId = data['item_id']
            audioindex = data['AudioStreamIndex']
            subtitleindex = data['SubtitleStreamIndex']
            playTime = data['currentPosition']
            playMethod = data['playmethod']
            paused = data.get('paused', False)
            duration = data.get('runtime', '')


            # Get playback volume
            volume_query = {

                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "Application.GetProperties",
                    "params": {

                        "properties": ["volume", "muted"] 
                    }
            }
            result = xbmc.executeJSONRPC(json.dumps(volume_query))
            result = json.loads(result)
            result = result.get('result')

            volume = result.get('volume')
            muted = result.get('muted')

            # Postdata for the websocketclient report
            # postdata = {

            #     'QueueableMediaTypes': "Video",
            #     'CanSeek': True,
            #     'ItemId': itemId,
            #     'MediaSourceId': itemId,
            #     'PlayMethod': playMethod,
            #     'PositionTicks': int(playTime * 10000000),
            #     'IsPaused': paused,
            #     'VolumeLevel': volume,
            #     'IsMuted': muted
            # }
            if paused == 'stopped':
                state = 'stopped'
            elif paused is True:
                state = 'paused'
            else:
                state = 'playing'
            postdata = {
                'ratingKey': itemId,
                'state': state,   # 'stopped', 'paused', 'buffering', 'playing'
                'time': int(playTime) * 1000,
                'duration': int(duration) * 1000
            }

            # For PMS playQueues/playlists only
            if data.get('playQueueID'):
                postdata['containerKey'] = '/playQueues/' + data.get('playQueueID')
                postdata['playQueueVersion'] = data.get('playQueueVersion')
                postdata['playQueueItemID'] = data.get('playQueueItemID')

            if playMethod == "Transcode":
                # Track can't be changed, keep reporting the same index
                postdata['AudioStreamIndex'] = audioindex
                postdata['AudioStreamIndex'] = subtitleindex

            else:
                # Get current audio and subtitles track
                tracks_query = {

                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "Player.GetProperties",
                        "params": {

                            "playerid": 1,
                            "properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]
                        }
                    }
                result = xbmc.executeJSONRPC(json.dumps(tracks_query))
                result = json.loads(result)
                result = result.get('result')

                try: # Audio tracks
                    indexAudio = result['currentaudiostream']['index']
                except (KeyError, TypeError):
                    indexAudio = 0
                
                try: # Subtitles tracks
                    indexSubs = result['currentsubtitle']['index']
                except (KeyError, TypeError):
                    indexSubs = 0

                try: # If subtitles are enabled
                    subsEnabled = result['subtitleenabled']
                except (KeyError, TypeError):
                    subsEnabled = ""

                # Postdata for the audio
                data['AudioStreamIndex'], postdata['AudioStreamIndex'] = [indexAudio + 1] * 2
                
                # Postdata for the subtitles
                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                    
                    # Number of audiotracks to help get Emby Index
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    mapping = utils.window("emby_%s.indexMapping" % currentFile)

                    if mapping: # Set in PlaybackUtils.py
                        
                        log("Mapping for external subtitles index: %s" % mapping, 2)
                        externalIndex = json.loads(mapping)

                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            subindex = [externalIndex[str(indexSubs)]] * 2
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                        else:
                            # Internal subtitle currently selected
                            subindex = [indexSubs - len(externalIndex) + audioTracks + 1] * 2
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                    
                    else: # Direct paths enabled scenario or no external subtitles set
                        subindex = [indexSubs + audioTracks + 1] * 2
                        data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                else:
                    data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [""] * 2

            # Report progress via websocketclient
            # postdata = json.dumps(postdata)
            # self.ws.sendProgressUpdate(postdata)
            self.doUtils(
                "{server}/:/timeline?" + urlencode(postdata), type="GET")

    def onPlayBackPaused(self):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_PAUSED: %s" % currentFile, 2)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = True
        
            self.reportPlayback()

    def onPlayBackResumed(self):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_RESUMED: %s" % currentFile, 2)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = False
        
            self.reportPlayback()

    def onPlayBackSeek(self, time, seekOffset):
        # Make position when seeking a bit more accurate
        currentFile = self.currentFile
        self.logMsg("PLAYBACK_SEEK: %s" % currentFile, 2)

        if self.played_info.get(currentFile):
            position = self.xbmcplayer.getTime()
            self.played_info[currentFile]['currentPosition'] = position

            self.reportPlayback()
    
    def onPlayBackStopped(self):
        # Will be called when user stops xbmc playing a file
        
        log = self.logMsg
        window = utils.window
        log("ONPLAYBACK_STOPPED", 1)

        self.stopAll()

        window('Plex_currently_playing_itemid', clear=True)
        window('emby_customPlaylist', clear=True)
        window('emby_customPlaylist.seektime', clear=True)
        window('emby_playbackProps', clear=True)
        window('suspend_LibraryThread', clear=True)
        window('emby_customPlaylist.seektime', clear=True)
        log("Clear playlist properties.", 1)

    def onPlayBackEnded(self):
        # Will be called when xbmc stops playing a file, because the file ended
        self.logMsg("ONPLAYBACK_ENDED", 1)
        self.onPlayBackStopped()

    def stopAll(self):

        log = self.logMsg
        lang = utils.language
        settings = utils.settings

        doUtils = self.doUtils

        if not self.played_info:
            return 
            
        log("Played_information: %s" % self.played_info, 1)
        # Process each items
        for item in self.played_info:
            
            data = self.played_info.get(item)
            if data:
                
                log("Item path: %s" % item, 2)
                log("Item data: %s" % data, 2)

                runtime = data['runtime']
                currentPosition = data['currentPosition']
                itemid = data['item_id']
                refresh_id = data['refresh_id']
                currentFile = data['currentfile']
                type = data['Type']
                playMethod = data['playmethod']

                # Prevent manually mark as watched in Kodi monitor
                utils.window('emby_skipWatched%s' % itemid, value="true")

                if currentPosition and runtime:
                    try:
                        percentComplete = currentPosition / int(runtime)
                    except ZeroDivisionError:
                        # Runtime is 0.
                        percentComplete = 0
                        
                    markPlayedAt = float(settings('markPlayed')) / 100
                    log("Percent complete: %s Mark played at: %s"
                        % (percentComplete, markPlayedAt), 1)

                    # Send the delete action to the server.
                    offerDelete = False

                    if type == "Episode" and settings('deleteTV') == "true":
                        offerDelete = True
                    elif type == "Movie" and settings('deleteMovies') == "true":
                        offerDelete = True

                    if settings('offerDelete') != "true":
                        # Delete could be disabled, even if the subsetting is enabled.
                        offerDelete = False

                    # Plex: never delete
                    offerDelete = False
                    if percentComplete >= markPlayedAt and offerDelete:
                        resp = xbmcgui.Dialog().yesno(
                            lang(30091),
                            lang(33015),
                            autoclose=120000)
                        if not resp:
                            log("User skipped deletion.", 1)
                            continue

                        url = "{server}/emby/Items/%s?format=json" % itemid
                        log("Deleting request: %s" % itemid, 1)
                        doUtils(url, type="DELETE")
                self.stopPlayback(data)

        # Clean the WINDOW properties
        for filename in self.played_info:
            cleanup = (
                'emby_%s.itemid' % filename,
                'emby_%s.runtime' % filename,
                'emby_%s.refreshid' % filename,
                'emby_%s.playmethod' % filename,
                'emby_%s.type' % filename,
                'plex_%s.playQueueItemID' % filename,
                'plex_%s.playlistPosition' % filename,
                'plex_%s.guid' % filename
            )
            for item in cleanup:
                utils.window(item, clear=True)

                # Stop transcoding
                if playMethod == "Transcode":
                    log("Transcoding for %s terminated." % itemid, 1)
                    deviceId = self.clientInfo.getDeviceId()
                    url = "{server}/emby/Videos/ActiveEncodings?DeviceId=%s" % deviceId
                    doUtils(url, type="DELETE")
    
        self.played_info.clear()

    def stopPlayback(self, data):
        self.logMsg("stopPlayback called", 1)

        itemId = data['item_id']
        playTime = data['currentPosition']
        duration = data.get('runtime', '')

        url = "{server}/:/timeline?"
        args = {
            'ratingKey': itemId,
            'state': 'stopped',   # 'stopped', 'paused', 'buffering', 'playing'
            'time': int(playTime) * 1000,
            'duration': int(duration)
        }
        url = url + urlencode(args)
        self.doUtils(url, type="GET")

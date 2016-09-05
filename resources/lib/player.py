# -*- coding: utf-8 -*-

###############################################################################
import logging
import json

import xbmc
import xbmcgui

from utils import window, settings, language as lang, DateToKodi, \
    getUnixTimestamp
import clientinfo
import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


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

        xbmc.Player.__init__(self)

        log.info("Started playback monitor.")

    def GetPlayStats(self):
        return self.playStats

    def onPlayBackStarted(self):
        """
        Will be called when xbmc starts playing a file.
        Window values need to have been set in Kodimonitor.py
        """
        self.stopAll()

        # Get current file (in utf-8!)
        try:
            currentFile = self.getPlayingFile()
            xbmc.sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                xbmc.sleep(100)
                try:
                    currentFile = self.getPlayingFile()
                except:
                    pass
                if count == 20:
                    break
                else:
                    count += 1
        if not currentFile:
            log.warn('Error getting currently playing file; abort reporting')
            return

        # Save currentFile for cleanup later and for references
        self.currentFile = currentFile
        window('plex_lastPlayedFiled', value=currentFile)
        # We may need to wait for info to be set in kodi monitor
        itemId = window("emby_%s.itemid" % currentFile)
        count = 0
        while not itemId:
            xbmc.sleep(200)
            itemId = window("emby_%s.itemid" % currentFile)
            if count == 5:
                log.warn("Could not find itemId, cancelling playback report!")
                return
            count += 1

        log.info("ONPLAYBACK_STARTED: %s itemid: %s" % (currentFile, itemId))

        embyitem = "emby_%s" % currentFile
        runtime = window("%s.runtime" % embyitem)
        refresh_id = window("%s.refreshid" % embyitem)
        playMethod = window("%s.playmethod" % embyitem)
        itemType = window("%s.type" % embyitem)
        try:
            playcount = int(window("%s.playcount" % embyitem))
        except ValueError:
            playcount = 0
        window('emby_skipWatched%s' % itemId, value="true")

        log.debug("Playing itemtype is: %s" % itemType)

        customseek = window('plex_customplaylist.seektime')
        if customseek:
            # Start at, when using custom playlist (play to Kodi from
            # webclient)
            log.info("Seeking to: %s" % customseek)
            try:
                self.seekTime(int(customseek))
            except:
                log.error('Could not seek!')
            window('plex_customplaylist.seektime', clear=True)

        try:
            seekTime = self.getTime()
        except RuntimeError:
            log.error('Could not get current seektime from xbmc player')
            seekTime = 0

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
                    
                    log.debug("Mapping for external subtitles index: %s"
                              % mapping)
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
            try:
                runtime = self.getTotalTime()
                log.error("Runtime is missing, Kodi runtime: %s" % runtime)
            except:
                log.error('Could not get kodi runtime, setting to zero')
                runtime = 0

        with embydb.GetEmbyDB() as emby_db:
            emby_dbitem = emby_db.getItem_byId(itemId)
        try:
            fileid = emby_dbitem[1]
        except TypeError:
            log.info("Could not find fileid in plex db.")
            fileid = None
        # Save data map for updates and position calls
        data = {
            'runtime': runtime,
            'item_id': itemId,
            'refresh_id': refresh_id,
            'currentfile': currentFile,
            'AudioStreamIndex': postdata['AudioStreamIndex'],
            'SubtitleStreamIndex': postdata['SubtitleStreamIndex'],
            'playmethod': playMethod,
            'Type': itemType,
            'currentPosition': int(seekTime),
            'fileid': fileid,
            'itemType': itemType,
            'playcount': playcount
        }

        self.played_info[currentFile] = data
        log.info("ADDING_FILE: %s" % data)

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

    def onPlayBackPaused(self):

        currentFile = self.currentFile
        log.info("PLAYBACK_PAUSED: %s" % currentFile)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = True

    def onPlayBackResumed(self):

        currentFile = self.currentFile
        log.info("PLAYBACK_RESUMED: %s" % currentFile)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = False

    def onPlayBackSeek(self, time, seekOffset):
        # Make position when seeking a bit more accurate
        currentFile = self.currentFile
        self.info("PLAYBACK_SEEK: %s" % currentFile)

        if self.played_info.get(currentFile):
            try:
                position = self.getTime()
            except RuntimeError:
                # When Kodi is not playing
                return
            self.played_info[currentFile]['currentPosition'] = position

    def onPlayBackStopped(self):
        # Will be called when user stops xbmc playing a file
        log.info("ONPLAYBACK_STOPPED")

        self.stopAll()

        window('Plex_currently_playing_itemid', clear=True)
        window('plex_customplaylist', clear=True)
        window('plex_customplaylist.seektime', clear=True)
        window('plex_customplaylist.seektime', clear=True)
        window('plex_playbackProps', clear=True)
        log.debug("Cleared playlist properties.")

    def onPlayBackEnded(self):
        # Will be called when xbmc stops playing a file, because the file ended
        log.info("ONPLAYBACK_ENDED")
        self.onPlayBackStopped()

    def stopAll(self):
        if not self.played_info:
            return
        log.info("Played_information: %s" % self.played_info)
        # Process each items
        for item in self.played_info:
            data = self.played_info.get(item)
            if data:
                log.debug("Item path: %s" % item)
                log.debug("Item data: %s" % data)

                runtime = data['runtime']
                currentPosition = data['currentPosition']
                itemid = data['item_id']
                refresh_id = data['refresh_id']
                currentFile = data['currentfile']
                media_type = data['Type']
                playMethod = data['playmethod']

                # Prevent manually mark as watched in Kodi monitor
                window('emby_skipWatched%s' % itemid, value="true")

                if currentPosition and runtime:
                    try:
                        percentComplete = float(currentPosition) / float(runtime)
                    except ZeroDivisionError:
                        # Runtime is 0.
                        percentComplete = 0

                    markPlayed = 0.90
                    log.info("Percent complete: %s Mark played at: %s"
                             % (percentComplete, markPlayed))
                    if percentComplete >= markPlayed:
                        # Tell Kodi that we've finished watching (Plex knows)
                        if (data['fileid'] is not None and
                                data['itemType'] in ('movie', 'episode')):
                            with kodidb.GetKodiDB('video') as kodi_db:
                                kodi_db.addPlaystate(
                                    data['fileid'],
                                    None,
                                    None,
                                    data['playcount'] + 1,
                                    DateToKodi(getUnixTimestamp()))
                    # Send the delete action to the server.
                    offerDelete = False

                    if media_type == "Episode" and settings('deleteTV') == "true":
                        offerDelete = True
                    elif media_type == "Movie" and settings('deleteMovies') == "true":
                        offerDelete = True

                    if settings('offerDelete') != "true":
                        # Delete could be disabled, even if the subsetting is enabled.
                        offerDelete = False

                    # Plex: never delete
                    offerDelete = False
                    if percentComplete >= markPlayed and offerDelete:
                        resp = xbmcgui.Dialog().yesno(
                            lang(30091),
                            lang(33015),
                            autoclose=120000)
                        if not resp:
                            log.info("User skipped deletion.")
                            continue

                        url = "{server}/emby/Items/%s?format=json" % itemid
                        log.info("Deleting request: %s" % itemid)
                        self.doUtils(url, action_type="DELETE")

        # Clean the WINDOW properties
        for filename in self.played_info:
            cleanup = (
                'emby_%s.itemid' % filename,
                'emby_%s.runtime' % filename,
                'emby_%s.refreshid' % filename,
                'emby_%s.playmethod' % filename,
                'emby_%s.type' % filename,
                'emby_%s.runtime' % filename,
                'emby_%s.playcount' % filename,
                'plex_%s.playlistPosition' % filename
            )
            for item in cleanup:
                window(item, clear=True)

        # Stop transcoding
        if playMethod == "Transcode":
            log.info("Transcoding for %s terminating" % itemid)
            self.doUtils(
                "{server}/video/:/transcode/universal/stop",
                parameters={'session': self.clientInfo.getDeviceId()})

        self.played_info.clear()

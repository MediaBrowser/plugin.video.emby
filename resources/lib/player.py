# -*- coding: utf-8 -*-

###############################################################################
import logging
import json

import xbmc
import xbmcgui

from utils import window, settings, language as lang, DateToKodi, \
    getUnixTimestamp, tryDecode, tryEncode
import downloadutils
import plexdb_functions as plexdb
import kodidb_functions as kodidb
import variables as v
import state

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
            currentFile = tryDecode(self.getPlayingFile())
            xbmc.sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                xbmc.sleep(100)
                try:
                    currentFile = tryDecode(self.getPlayingFile())
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
        itemId = window("plex_%s.itemid" % tryEncode(currentFile))
        count = 0
        while not itemId:
            xbmc.sleep(200)
            itemId = window("plex_%s.itemid" % tryEncode(currentFile))
            if count == 5:
                log.warn("Could not find itemId, cancelling playback report!")
                return
            count += 1

        log.info("ONPLAYBACK_STARTED: %s itemid: %s" % (currentFile, itemId))

        plexitem = "plex_%s" % tryEncode(currentFile)
        runtime = window("%s.runtime" % plexitem)
        refresh_id = window("%s.refreshid" % plexitem)
        playMethod = window("%s.playmethod" % plexitem)
        itemType = window("%s.type" % plexitem)
        try:
            playcount = int(window("%s.playcount" % plexitem))
        except ValueError:
            playcount = 0
        window('plex_skipWatched%s' % itemId, value="true")

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

        # Postdata structure to send to plex server
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
            postdata['AudioStreamIndex'] = window("%sAudioStreamIndex"
                                                  % tryEncode(currentFile))
            postdata['SubtitleStreamIndex'] = window("%sSubtitleStreamIndex"
                                                     % tryEncode(currentFile))
        else:
            # Get the current kodi audio and subtitles and convert to plex equivalent
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
                
                # Number of audiotracks to help get plex Index
                audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                mapping = window("%s.indexMapping" % plexitem)

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

        with plexdb.Get_Plex_DB() as plex_db:
            plex_dbitem = plex_db.getItem_byId(itemId)
        try:
            fileid = plex_dbitem[1]
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
        log.info("PLAYBACK_SEEK: %s" % currentFile)

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

        for item in ('plex_currently_playing_itemid',
                     'plex_customplaylist',
                     'plex_customplaylist.seektime',
                     'plex_playbackProps',
                     'plex_forcetranscode'):
            window(item, clear=True)
        # We might have saved a transient token from a user flinging media via
        # Companion
        state.PLEX_TRANSIENT_TOKEN = None
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
                window('plex_skipWatched%s' % itemid, value="true")

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
                                data['itemType'] in (v.KODI_TYPE_MOVIE, v.KODI_TYPE_EPISODE)):
                            with kodidb.GetKodiDB('video') as kodi_db:
                                kodi_db.addPlaystate(
                                    data['fileid'],
                                    None,
                                    None,
                                    data['playcount'] + 1,
                                    DateToKodi(getUnixTimestamp()))

        # Clean the WINDOW properties
        for filename in self.played_info:
            plex_item = 'plex_%s' % tryEncode(filename)
            cleanup = (
                '%s.itemid' % plex_item,
                '%s.runtime' % plex_item,
                '%s.refreshid' % plex_item,
                '%s.playmethod' % plex_item,
                '%s.type' % plex_item,
                '%s.runtime' % plex_item,
                '%s.playcount' % plex_item,
                '%s.playlistPosition' % plex_item,
                '%s.subtitle' % plex_item,
            )
            for item in cleanup:
                window(item, clear=True)

        # Stop transcoding
        if playMethod == "Transcode":
            log.info("Transcoding for %s terminating" % itemid)
            self.doUtils(
                "{server}/video/:/transcode/universal/stop",
                parameters={'session': window('plex_client_Id')})

        self.played_info.clear()

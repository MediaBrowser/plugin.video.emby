# -*- coding: utf-8 -*-

###############################################################################
from logging import getLogger
from json import loads

from xbmc import Player, sleep

from utils import window, DateToKodi, getUnixTimestamp, tryDecode, tryEncode
import downloadutils
import plexdb_functions as plexdb
import kodidb_functions as kodidb
import json_rpc as js
import variables as v
import state

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


class PKC_Player(Player):

    played_info = state.PLAYED_INFO
    playStats = state.PLAYER_STATES
    currentFile = None

    def __init__(self):
        self.doUtils = downloadutils.DownloadUtils
        Player.__init__(self)
        LOG.info("Started playback monitor.")

    def onPlayBackStarted(self):
        """
        Will be called when xbmc starts playing a file.
        Window values need to have been set in Kodimonitor.py
        """
        return
        self.stopAll()

        # Get current file (in utf-8!)
        try:
            currentFile = tryDecode(self.getPlayingFile())
            sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                sleep(100)
                try:
                    currentFile = tryDecode(self.getPlayingFile())
                except:
                    pass
                if count == 20:
                    break
                else:
                    count += 1
        if not currentFile:
            LOG.warn('Error getting currently playing file; abort reporting')
            return

        # Save currentFile for cleanup later and for references
        self.currentFile = currentFile
        window('plex_lastPlayedFiled', value=currentFile)
        # We may need to wait for info to be set in kodi monitor
        itemId = window("plex_%s.itemid" % tryEncode(currentFile))
        count = 0
        while not itemId:
            sleep(200)
            itemId = window("plex_%s.itemid" % tryEncode(currentFile))
            if count == 5:
                LOG.warn("Could not find itemId, cancelling playback report!")
                return
            count += 1

        LOG.info("ONPLAYBACK_STARTED: %s itemid: %s" % (currentFile, itemId))

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

        LOG.debug("Playing itemtype is: %s" % itemType)

        customseek = window('plex_customplaylist.seektime')
        if customseek:
            # Start at, when using custom playlist (play to Kodi from
            # webclient)
            LOG.info("Seeking to: %s" % customseek)
            try:
                self.seekTime(int(customseek))
            except:
                LOG.error('Could not seek!')
            window('plex_customplaylist.seektime', clear=True)

        try:
            seekTime = self.getTime()
        except RuntimeError:
            LOG.error('Could not get current seektime from xbmc player')
            seekTime = 0
        volume = js.get_volume()
        muted = js.get_muted()

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
            indexAudio = js.current_audiostream(1).get('index', 0)
            subsEnabled = js.subtitle_enabled(1)
            if subsEnabled:
                indexSubs = js.current_subtitle(1).get('index', 0)
            else:
                indexSubs = 0

            # Postdata for the audio
            postdata['AudioStreamIndex'] = indexAudio + 1
            
            # Postdata for the subtitles
            if subsEnabled and len(Player().getAvailableSubtitleStreams()) > 0:
                
                # Number of audiotracks to help get plex Index
                audioTracks = len(Player().getAvailableAudioStreams())
                mapping = window("%s.indexMapping" % plexitem)

                if mapping: # Set in playbackutils.py
                    
                    LOG.debug("Mapping for external subtitles index: %s"
                              % mapping)
                    externalIndex = loads(mapping)

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
                LOG.error("Runtime is missing, Kodi runtime: %s" % runtime)
            except:
                LOG.error('Could not get kodi runtime, setting to zero')
                runtime = 0

        with plexdb.Get_Plex_DB() as plex_db:
            plex_dbitem = plex_db.getItem_byId(itemId)
        try:
            fileid = plex_dbitem[1]
        except TypeError:
            LOG.info("Could not find fileid in plex db.")
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
        LOG.info("ADDING_FILE: %s" % data)

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
        LOG.info("PLAYBACK_PAUSED: %s" % currentFile)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = True

    def onPlayBackResumed(self):

        currentFile = self.currentFile
        LOG.info("PLAYBACK_RESUMED: %s" % currentFile)

        if self.played_info.get(currentFile):
            self.played_info[currentFile]['paused'] = False

    def onPlayBackSeek(self, time, seekOffset):
        # Make position when seeking a bit more accurate
        currentFile = self.currentFile
        LOG.info("PLAYBACK_SEEK: %s" % currentFile)

        if self.played_info.get(currentFile):
            try:
                position = self.getTime()
            except RuntimeError:
                # When Kodi is not playing
                return
            self.played_info[currentFile]['currentPosition'] = position

    def onPlayBackStopped(self):
        # Will be called when user stops xbmc playing a file
        LOG.info("ONPLAYBACK_STOPPED")

        self.stopAll()

        for item in ('plex_currently_playing_itemid',
                     'plex_customplaylist',
                     'plex_customplaylist.seektime',
                     'plex_forcetranscode'):
            window(item, clear=True)
        # We might have saved a transient token from a user flinging media via
        # Companion (if we could not use the playqueue to store the token)
        state.PLEX_TRANSIENT_TOKEN = None
        LOG.debug("Cleared playlist properties.")

    def onPlayBackEnded(self):
        # Will be called when xbmc stops playing a file, because the file ended
        LOG.info("ONPLAYBACK_ENDED")
        self.onPlayBackStopped()

    def stopAll(self):
        if not self.played_info:
            return
        LOG.info("Played_information: %s" % self.played_info)
        # Process each items
        for item in self.played_info:
            data = self.played_info.get(item)
            if not data:
                continue
            LOG.debug("Item path: %s" % item)
            LOG.debug("Item data: %s" % data)

            runtime = data['runtime']
            currentPosition = data['currentPosition']
            itemid = data['item_id']
            refresh_id = data['refresh_id']
            currentFile = data['currentfile']
            media_type = data['Type']
            playMethod = data['playmethod']

            # Prevent manually mark as watched in Kodi monitor
            window('plex_skipWatched%s' % itemid, value="true")

            if not currentPosition or not runtime:
                continue
            try:
                percentComplete = float(currentPosition) / float(runtime)
            except ZeroDivisionError:
                # Runtime is 0.
                percentComplete = 0
            LOG.info("Percent complete: %s Mark played at: %s"
                     % (percentComplete, v.MARK_PLAYED_AT))
            if percentComplete >= v.MARK_PLAYED_AT:
                # Tell Kodi that we've finished watching (Plex knows)
                if (data['fileid'] is not None and
                        data['itemType'] in (v.KODI_TYPE_MOVIE,
                                             v.KODI_TYPE_EPISODE)):
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
            LOG.info("Transcoding for %s terminating" % itemid)
            self.doUtils().downloadUrl(
                "{server}/video/:/transcode/universal/stop",
                parameters={'session': v.PKC_MACHINE_IDENTIFIER})

        self.played_info.clear()

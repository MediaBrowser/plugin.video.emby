# -*- coding: utf-8 -*-
import uuid
import threading
import json
import xbmc
from database import dbio
from emby import listitem
from helper import loghandler
from helper import utils

if utils.Python3:
    from urllib.parse import unquote_plus
else:
    from urllib import unquote_plus

XbmcMonitor = xbmc.Monitor()
LOG = loghandler.LOG('EMBY.hooks.player')


class PlayerEvents(xbmc.Player):
    def __init__(self):
        self.ItemSkipUpdate = []
        self.Transcoding = False
        self.PlayingItem = {}
        self.QueuedPlayingItem = {}
        self.EmbyServer = None
        self.EmbyServers = None
        self.PlayingVideoAudio = True
        self.MultiselectionDone = False
        self.PlayerSkipItem = "-1"
        self.PositionTrackerThread = None
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}'))
        result = result.get('result', {})
        self.volume = result.get('volume', 0)
        self.muted = result.get('muted', False)
        self.TrailerPath = ""
        self.Intros = []
        self.playlistIndex = -1
        self.AddonModeTrailerItem = None
        self.PlayBackEnded = True

    def StartUp(self, EmbyServers):
        self.EmbyServers = EmbyServers

    def onPlayBackStarted(self):
        if not self.PlayBackEnded:
            self.stop_playback(True, False)

        LOG.info("[ onPlayBackStarted ]")

        if not utils.syncduringplayback:
            utils.SyncPause = True

    def onAVChange(self):
        LOG.info("[ onAVChange ]")

        if self.PlayerSkipItem != "-1" or not self.isPlaying() or self.AddonModeTrailerItem:
            LOG.debug("onAVChange not playing")
            return

        self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)
        PositionTicks = max(int(self.getTime() * 10000000), 0)
        self.PlayingItem['PositionTicks'] = PositionTicks

        if self.EmbyServer and "ItemId" in self.PlayingItem:
            self.EmbyServer.API.session_progress(self.PlayingItem)

    def queuePlayingItem(self, EmbyID, MediaType, MediasourceID, PlaySessionId):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
        LOG.info("[ Queue playing item ]")
        self.QueuedPlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

        if not utils.syncduringplayback:
            utils.SyncPause = True

        self.QueuedPlayingItem['ItemId'] = EmbyID
        self.QueuedPlayingItem['Type'] = MediaType
        self.QueuedPlayingItem['MediaSourceId'] = MediasourceID
        self.QueuedPlayingItem['PlaySessionId'] = PlaySessionId
        self.QueuedPlayingItem['PositionTicks'] = 0
        self.QueuedPlayingItem['RunTimeTicks'] = 0
        self.QueuedPlayingItem['VolumeLevel'] = self.volume
        self.QueuedPlayingItem['IsMuted'] = self.muted

    def onAVStarted(self):
        LOG.info("[ onAVStarted ]")

        if not utils.syncduringplayback:
            utils.SyncPause = True

        # Trailer from webserverice (addon mode)
        if self.AddonModeTrailerItem:
            if self.isPlaying():
                self.updateInfoTag(self.AddonModeTrailerItem)

            return

        # 3D, ISO etc. content from webserverice (addon mode)
        if self.PlayerSkipItem != "-1":
            self.playnext()
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % self.PlayerSkipItem)
            return

        if self.isPlaying():
            kodi_id = None
            media_type = None
            EmbyId = None
            VideoPlayback = False

            try:
                try:
                    PlayerItem = self.getVideoInfoTag()
                    Path = PlayerItem.getPath()
                    VideoPlayback = True
                except:
                    PlayerItem = self.getMusicInfoTag()
                    Path = PlayerItem.getURL()

                self.PlayingVideoAudio = True
            except:
                Path = ""
                PlayerItem = None
                self.PlayingVideoAudio = False

            if utils.useDirectPaths and not Path:
                PlayingFile = self.getPlayingFile()

                if PlayingFile.startswith("bluray://") and not self.MultiselectionDone:
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = PlayingFile.replace("bluray://", "")
                    PlayingFile = PlayingFile.replace("udf://", "")
                    PlayingFile = PlayingFile[:PlayingFile.find("//")]

                    for server_id in self.EmbyServers:
                        self.EmbyServer = self.EmbyServers[server_id]
                        embydb = dbio.DBOpen(server_id)
                        EmbyId = embydb.get_EmbyID_by_path(PlayingFile)

                        if EmbyId:
                            Data = embydb.get_item_by_id(EmbyId[0])
                            kodi_id = Data[0]
                            media_type = Data[4]
                            Path = PlayingFile

                        dbio.DBClose(server_id, False)

            self.MultiselectionDone = False

            # native content
            if Path and not Path.startswith("http://127.0.0.1:57342"):  # native mode
                PlaySessionId = str(uuid.uuid4()).replace("-", "")
                MediasourceID = ""

                if not kodi_id:
                    kodi_id = PlayerItem.getDbId()

                if not media_type:
                    media_type = PlayerItem.getMediaType()

                for server_id in self.EmbyServers:
                    self.EmbyServer = self.EmbyServers[server_id]
                    embydb = dbio.DBOpen(server_id)
                    item = embydb.get_full_item_by_kodi_id_complete(kodi_id, media_type)

                    if not item:
                        dbio.DBClose(server_id, False)
                        continue

                    EmbyId = item[0]

                    # Cinnemamode
                    if (utils.enableCinemaMovies and item[3] == "movie") or (utils.enableCinemaEpisodes and item[3] == "episode"):
                        if self.TrailerPath != "SKIP":
                            PlayingFile = self.getPlayingFile()

                            if self.TrailerPath != PlayingFile:  # Trailer init (load)
                                self.pause()  # Player Pause
                                self.Intros = []
                                PlayTrailer = True

                                if utils.askCinema:
                                    PlayTrailer = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33016))

                                if PlayTrailer:
                                    self.Intros = utils.load_Trailers(self.EmbyServer, EmbyId)

                                if self.Intros:
                                    self.play_Trailer()
                                    dbio.DBClose(server_id, False)
                                    return

                                self.TrailerPath = ""
                                self.pause()  # Player resume
                        else:
                            self.TrailerPath = ""

                    # Multiversion
                    MediaSources = embydb.get_mediasource(EmbyId)
                    dbio.DBClose(server_id, False)
                    MediasourceID = MediaSources[0][2]

                    if len(MediaSources) > 1:
                        self.pause()  # Player Pause
                        Selection = []

                        for Data in MediaSources:
                            Selection.append("%s - %s" % (Data[4], utils.SizeToText(float(Data[5]))))

                        MediaIndex = utils.dialog("select", heading="Select Media Source:", list=Selection)

                        if MediaIndex == -1:
                            self.Cancel()
                            return

                        if MediaIndex == 0:
                            self.pause()  # Player Resume
                        else:
                            self.MultiselectionDone = True
                            Details = utils.load_VideoitemFromKodiDB(media_type, str(kodi_id))
                            li = utils.CreateListitem(media_type, Details)
                            Path = MediaSources[MediaIndex][3]

                            if Path.startswith('\\\\'):
                                Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                            li.setPath(Path)
                            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                            self.playlistIndex = playlist.getposition()
                            playlist.add(Path, li, self.playlistIndex + 1)
                            MediasourceID = MediaSources[MediaIndex][2]
                            self.playnext()
                            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % self.playlistIndex)

                        break

                if EmbyId:
                    self.ItemSkipUpdate.append(EmbyId)
                    LOG.debug("ItemSkipUpdate: %s" % str(self.ItemSkipUpdate))
                    self.queuePlayingItem(EmbyId, media_type, MediasourceID, PlaySessionId)

            self.PlayBackEnded = False
            self.PlayingItem = self.QueuedPlayingItem
            self.QueuedPlayingItem = {}

            if not self.isPlaying(): #check again if playing
                return

            self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)

            if self.EmbyServer and 'ItemId' in self.PlayingItem:
                if VideoPlayback:
                    xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer

                self.EmbyServer.API.session_playing(self.PlayingItem)

                if not self.PositionTrackerThread:
                    self.PositionTrackerThread = threading.Thread(target=self.PositionTracker)
                    self.PositionTrackerThread.start()

    def PositionTracker(self):  # threaded
        while self.EmbyServer and "ItemId" in self.PlayingItem and not utils.SystemShutdown:
            if not XbmcMonitor.waitForAbort(4):
                if self.isPlaying():
                    PositionTicks = max(int(self.getTime() * 10000000), 0)
                    self.PlayingItem['PositionTicks'] = PositionTicks
                    self.EmbyServer.API.session_progress(self.PlayingItem)

        self.PositionTrackerThread = None

    def onPlayBackSeek(self, time, seekOffset):
        LOG.info("[ onPlayBackSeek ]")

        if not self.EmbyServer or self.PlayerSkipItem != "-1" or 'ItemId' not in self.PlayingItem and not self.PlayingVideoAudio:
            return

        SeekPosition = int(time * 10000)

        if 'RunTimeTicks' in self.PlayingItem:
            if SeekPosition > self.PlayingItem['RunTimeTicks']:
                SeekPosition = self.PlayingItem['RunTimeTicks']

            self.PlayingItem['PositionTicks'] = SeekPosition
            self.EmbyServer.API.session_progress(self.PlayingItem)

    def onPlayBackPaused(self):
        LOG.info("[ onPlayBackPaused ]")

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        if self.isPlaying():
            PositionTicks = max(int(self.getTime() * 10000000), 0)
            self.PlayingItem['PositionTicks'] = PositionTicks
            self.PlayingItem['IsPaused'] = True
            self.EmbyServer.API.session_progress(self.PlayingItem)

        LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        LOG.info("[ onPlayBackResumed ]")

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        self.PlayingItem['IsPaused'] = False
        self.EmbyServer.API.session_progress(self.PlayingItem)
        LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        LOG.info("[ onPlayBackStopped ]")

        if self.EmbyServer and self.Transcoding:
            self.EmbyServer.API.close_transcode()

        utils.SyncPause = False
        self.stop_playback(True, True)
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        LOG.info("[ onPlayBackEnded ]")
        utils.SyncPause = False
        self.stop_playback(True, False)
        LOG.info("--<<[ playback ]")

    def SETVolume(self, data):
        data = json.loads(data)
        self.muted = data["muted"]
        self.volume = data["volume"]

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        self.PlayingItem['VolumeLevel'] = self.volume
        self.PlayingItem['IsMuted'] = self.muted
        self.EmbyServer.API.session_progress(self.PlayingItem)

    def onPlayBackError(self):
        LOG.info("[ onPlayBackError ]")
        utils.SyncPause = False
        self.stop_playback(False, False)

    def stop_playback(self, delete, Stopped):
        PlayingItemLocal = self.PlayingItem.copy()
        LOG.debug("[ played info ] %s" % PlayingItemLocal)
        self.PlayBackEnded = True
        self.PlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

        # Trailer is playing, skip
        if self.AddonModeTrailerItem:
            self.AddonModeTrailerItem = None
            return

        # Trailers for native content
        if not Stopped:
            # Play init item after native content trailer playback
            if self.TrailerPath and not self.Intros:
                self.TrailerPath = "SKIP"
                self.Intros = []
                playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                self.play(playlist, None, False, self.playlistIndex)
                return

            # play trailers for native content
            if self.Intros:
                self.play_Trailer()
                return

        self.Intros = []
        self.TrailerPath = ""

        if not self.EmbyServer or 'ItemId' not in PlayingItemLocal:
            return

        self.ItemSkipUpdate.append(PlayingItemLocal['ItemId'])
        self.EmbyServer.API.session_stop(PlayingItemLocal)

        if self.Transcoding:
            self.EmbyServer.API.close_transcode()

        if delete:
            if utils.offerDelete:
                Runtime = int(PlayingItemLocal['RunTimeTicks'])

                if Runtime > 10:
                    if int(PlayingItemLocal['PositionTicks']) > Runtime * 0.90:  # 90% Progress
                        DeleteMsg = False

                        if PlayingItemLocal['Type'] == 'episode' and utils.deleteTV:
                            DeleteMsg = True
                        elif PlayingItemLocal['Type'] == 'movie' and utils.deleteMovies:
                            DeleteMsg = True

                        if DeleteMsg:
                            LOG.info("Offer delete option")

                            if utils.dialog("yesno", heading=utils.Translate(30091), line1=utils.Translate(33015)):
                                self.EmbyServer.API.delete_item(PlayingItemLocal['ItemId'])
                                threading.Thread(target=self.EmbyServer.library.removed, args=([PlayingItemLocal['ItemId']],)).start()

        if self.isPlaying():
            return

        threading.Thread(target=self.start_workers).start()

    def Cancel(self):
        self.stop()
        utils.SyncPause = False
        threading.Thread(target=self.start_workers).start()

    # Continue sync jobs
    def start_workers(self):
        ServerIds = list(self.EmbyServers.keys()) # prevents error -> dictionary changed size during iteration

        for ServerId in ServerIds:
            self.EmbyServers[ServerId].library.RunJobs()

    def play_Trailer(self): # for native content
        Path = self.Intros[0]['Path']

        li = listitem.set_ListItem(self.Intros[0], self.EmbyServer.server_id)
        del self.Intros[0]

        if Path.startswith('\\\\'):
            Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

        self.TrailerPath = Path
        li.setPath(Path)
        self.play(Path, li)

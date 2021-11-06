# -*- coding: utf-8 -*-
import uuid
import threading
import json
import xbmc
import database.db_open
import helper.loghandler
import helper.utils as Utils

if Utils.Python3:
    from urllib.parse import unquote_plus
else:
    from urllib import unquote_plus

LOG = helper.loghandler.LOG('EMBY.hooks.player.Player')


class PlayerEvents(xbmc.Player):
    def __init__(self):
        self.ItemSkipUpdate = []
        self.Transcoding = False
        self.PlayingItem = {}
        self.QueuedPlayingItem = {}
        self.EmbyServer = None
        self.EmbyServers = None
        self.PlayingVideo = True
        self.MultiselectionDone = False
        self.PlayerSkipItem = "-1"
        self.PositionTrackerThread = None
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}'))
        result = result.get('result', {})
        self.volume = result.get('volume', 0)
        self.muted = result.get('muted', False)

    def StartUp(self, EmbyServers):
        self.EmbyServers = EmbyServers

    def onPlayBackStarted(self):
        threading.Thread(target=PlayBackStarted).start()

    def onAVChange(self):
        threading.Thread(target=self.AVChange).start()

    def AVChange(self):  # threaded
        LOG.info("[ onAVChange ]")

        if self.PlayerSkipItem != "-1" or not self.isPlaying():
            LOG.debug("onAVChange not playing")
            return

        self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)
        PositionTicks = int(self.getTime() * 10000000)

        if PositionTicks < 0:
            PositionTicks = 0

        self.PlayingItem['PositionTicks'] = PositionTicks

        if self.EmbyServer and "ItemId" in self.PlayingItem:
            self.EmbyServer.API.session_progress(self.PlayingItem)

    def queuePlayingItem(self, EmbyID, MediaType, MediasourceID, PlaySessionId):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
        LOG.info("[ Queue playing item ]")
        self.QueuedPlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}
        Utils.SyncPause = True
        self.QueuedPlayingItem['ItemId'] = EmbyID
        self.QueuedPlayingItem['Type'] = MediaType
        self.QueuedPlayingItem['MediaSourceId'] = MediasourceID
        self.QueuedPlayingItem['PlaySessionId'] = PlaySessionId
        self.QueuedPlayingItem['PositionTicks'] = 0
        self.QueuedPlayingItem['RunTimeTicks'] = 0
        self.QueuedPlayingItem['VolumeLevel'] = self.volume
        self.QueuedPlayingItem['IsMuted'] = self.muted

    def onAVStarted(self):
        threading.Thread(target=self.AVStarted).start()

    def AVStarted(self):  # threaded
        LOG.info("[ onAVStarted ]")
        Utils.SyncPause = True

        if self.PlayerSkipItem != "-1":
            if self.PlayerSkipItem != "TRAILER":
                self.playnext()
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % self.PlayerSkipItem)

            return

        if self.isPlaying():
            kodi_id = None
            media_type = None
            EmbyId = None

            try:
                try:  # self.isPlayingVideo()
                    PlayerItem = self.getVideoInfoTag()
                    Path = PlayerItem.getPath()
                except:  # self.isPlayingAudio()
                    PlayerItem = self.getMusicInfoTag()
                    Path = PlayerItem.getURL()

                self.PlayingVideo = True
            except:
                Path = ""
                PlayerItem = None
                self.PlayingVideo = False

            if Utils.useDirectPaths and not Path:
                PlayingFile = self.getPlayingFile()

                if PlayingFile.startswith("bluray://") and not self.MultiselectionDone:
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = PlayingFile.replace("bluray://", "")
                    PlayingFile = PlayingFile.replace("udf://", "")
                    PlayingFile = PlayingFile[:PlayingFile.find("//")]

                    for server_id in self.EmbyServers:
                        self.EmbyServer = self.EmbyServers[server_id]
                        embydb = database.db_open.DBOpen(Utils.DatabaseFiles, server_id)
                        EmbyId = embydb.get_EmbyID_by_path(PlayingFile)

                        if EmbyId:
                            Data = embydb.get_item_by_id(EmbyId[0])
                            kodi_id = Data[0]
                            media_type = Data[4]
                            Path = PlayingFile

                        database.db_open.DBClose(server_id, False)

            self.MultiselectionDone = False

            if Path and not Path.startswith("http://127.0.0.1:57578"):  # native mode
                PlaySessionId = str(uuid.uuid4()).replace("-", "")
                MediasourceID = ""

                if not kodi_id:
                    kodi_id = PlayerItem.getDbId()

                if not media_type:
                    media_type = PlayerItem.getMediaType()

                for server_id in self.EmbyServers:
                    self.EmbyServer = self.EmbyServers[server_id]
                    embydb = database.db_open.DBOpen(Utils.DatabaseFiles, server_id)
                    item = embydb.get_full_item_by_kodi_id_complete(kodi_id, media_type)

                    if not item:
                        database.db_open.DBClose(server_id, False)
                        continue

                    EmbyId = item[0]

                    # Multiversion
                    MediaSources = embydb.get_mediasource(EmbyId)
                    database.db_open.DBClose(server_id, False)
                    MediasourceID = ""

                    if len(MediaSources) > 1:
                        self.pause()
                        Selection = []

                        for Data in MediaSources:
                            Selection.append("%s - %s" % (Data[4], Utils.SizeToText(float(Data[5]))))

                        MediaIndex = Utils.dialog("select", heading="Select Media Source:", list=Selection)

                        if MediaIndex <= 0:
                            MediasourceID = MediaSources[0][2]
                            EmbyId = MediaSources[0][0]
                            self.pause()
                        else:
                            self.MultiselectionDone = True
                            Details = Utils.load_VideoitemFromKodiDB(media_type, str(kodi_id))
                            li = Utils.CreateListitem(media_type, Details)
                            Path = MediaSources[MediaIndex][3]

                            if Path.startswith('\\\\'):
                                Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                            li.setPath(Path)
                            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                            playlistIndex = playlist.getposition()
                            playlist.add(Path, li, playlistIndex + 1)
                            MediasourceID = MediaSources[MediaIndex][2]
                            EmbyId = MediaSources[MediaIndex][0]
                            self.playnext()
                            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % playlistIndex)

                        database.db_open.DBClose(server_id, False)
                        break

                if EmbyId:
                    self.ItemSkipUpdate.append(str(EmbyId))
                    self.queuePlayingItem(EmbyId, media_type, MediasourceID, PlaySessionId)

            self.PlayingItem = self.QueuedPlayingItem
            self.QueuedPlayingItem = {}

            if not self.isPlaying(): #check again if playing
                return

            self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)

            if self.EmbyServer and 'ItemId' in self.PlayingItem:
                self.EmbyServer.API.session_playing(self.PlayingItem)

                if not self.PositionTrackerThread:
                    self.PositionTrackerThread = threading.Thread(target=self.PositionTracker)
                    self.PositionTrackerThread.start()

    def PositionTracker(self):  # threaded
        while self.EmbyServer and "ItemId" in self.PlayingItem and not Utils.SystemShutdown:
            xbmc.sleep(4000)

            if self.isPlaying():
                PositionTicks = int(self.getTime() * 10000000)

                if PositionTicks < 0:
                    PositionTicks = 0

                self.PlayingItem['PositionTicks'] = PositionTicks
                self.EmbyServer.API.session_progress(self.PlayingItem)

        self.PositionTrackerThread = None

    def onPlayBackSeek(self, time, seekOffset):
        threading.Thread(target=self.PlayBackSeek, args=(time, seekOffset,)).start()

    def PlayBackSeek(self, time, seekOffset):  # threaded;  Relevant for audio content only, video is covered by "onAVChange"
        LOG.info("[ onPlayBackSeek ]")

        if not self.EmbyServer or self.PlayerSkipItem != "-1" or 'ItemId' not in self.PlayingItem and not self.PlayingVideo:
            return

        SeekPosition = int(time * 10000)

        if 'RunTimeTicks' in self.PlayingItem:
            if SeekPosition > self.PlayingItem['RunTimeTicks']:
                SeekPosition = self.PlayingItem['RunTimeTicks']

            self.PlayingItem['PositionTicks'] = SeekPosition
            self.EmbyServer.API.session_progress(self.PlayingItem)

    def onPlayBackPaused(self):
        threading.Thread(target=self.PlayBackPaused).start()

    def PlayBackPaused(self):  # threaded
        LOG.info("[ onPlayBackPaused ]")

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        if self.isPlaying():
            PositionTicks = int(self.getTime() * 10000000)

            if PositionTicks < 0:
                PositionTicks = 0

            self.PlayingItem['PositionTicks'] = PositionTicks
            self.PlayingItem['IsPaused'] = True
            self.EmbyServer.API.session_progress(self.PlayingItem)

        LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        threading.Thread(target=self.PlayBackResumed).start()

    def PlayBackResumed(self):  # threaded
        LOG.info("[ onPlayBackResumed ]")

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        self.PlayingItem['IsPaused'] = False
        self.EmbyServer.API.session_progress(self.PlayingItem)
        LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        threading.Thread(target=self.PlayBackStopped, args=(self.PlayingItem.copy(),)).start()

    def PlayBackStopped(self, PlayingItem):  # threaded
        LOG.info("[ onPlayBackStopped ]")

        if self.EmbyServer and self.Transcoding:
            self.EmbyServer.API.close_transcode()

        Utils.SyncPause = False
        self.stop_playback(PlayingItem, True)
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        threading.Thread(target=self.PlayBackEnded, args=(self.PlayingItem.copy(),)).start()

    def PlayBackEnded(self, PlayingItem):  # threaded
        LOG.info("[ onPlayBackEnded ]")
        Utils.SyncPause = False
        self.stop_playback(PlayingItem, True)
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
        threading.Thread(target=self.PlayBackError, args=(self.PlayingItem.copy(),)).start()

    def PlayBackError(self, PlayingItem):  # threaded
        LOG.info("[ onPlayBackError ]")
        Utils.SyncPause = False
        self.stop_playback(PlayingItem, False)

    def stop_playback(self, PlayingItem, delete):  # PlayingItem cached due to threading
        LOG.debug("[ played info ] %s" % self.PlayingItem)

        if not self.EmbyServer or 'ItemId' not in PlayingItem:
            return

        self.EmbyServer.API.session_stop(PlayingItem)

        if self.Transcoding:
            self.EmbyServer.API.close_transcode()

        if delete:
            if Utils.offerDelete:
                Runtime = int(PlayingItem['RunTimeTicks'])

                if Runtime > 10:
                    if int(PlayingItem['PositionTicks']) > Runtime * 0.90:  # 90% Progress
                        DeleteMsg = False

                        if PlayingItem['Type'] == 'episode' and Utils.deleteTV:
                            DeleteMsg = True
                        elif PlayingItem['Type'] == 'movie' and Utils.deleteMovies:
                            DeleteMsg = True

                        if DeleteMsg:
                            LOG.info("Offer delete option")

                        if Utils.dialog("yesno", heading=Utils.Translate(30091), line1=Utils.Translate(33015)):
                            self.EmbyServer.API.delete_item(PlayingItem['ItemId'])
                            threading.Thread(target=self.EmbyServer.library.removed, args=([PlayingItem['ItemId']],)).start()

        if self.isPlaying():
            return

        self.PlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

        # Continue sync jobs
        ServerIds = list(self.EmbyServers.keys()) # prevents error -> dictionary changed size during iteration

        for ServerId in ServerIds:
            threading.Thread(target=self.EmbyServers[ServerId].library.RunJobs).start()

def PlayBackStarted():  # threaded
    LOG.info("[ onPlayBackStarted ]")
    Utils.SyncPause = True

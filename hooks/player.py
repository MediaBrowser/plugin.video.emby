# -*- coding: utf-8 -*-
import threading
import json
import xbmc
import database.db_open
import helper.jsonrpc
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
        self.PositionTrackerThread = threading.Thread(target=self.PositionTracker)
        self.PositionTrackerThread.start()

    def StartUp(self, EmbyServers):
        self.EmbyServers = EmbyServers

    def onPlayBackStarted(self):
        LOG.info("[ onPlayBackStarted ]")
        Utils.SyncPause = True

    def onAVChange(self):
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

    def queuePlayingItem(self, EmbyID, MediaType, MediasourceID):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
        LOG.info("[ Queue playing item ]")
        self.QueuedPlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}
        Utils.SyncPause = True
        self.QueuedPlayingItem['ItemId'] = EmbyID
        self.QueuedPlayingItem['Type'] = MediaType
        self.QueuedPlayingItem['MediaSourceId'] = MediasourceID
        self.QueuedPlayingItem['PositionTicks'] = 0
        self.QueuedPlayingItem['RunTimeTicks'] = 0
        self.QueuedPlayingItem['VolumeLevel'], self.QueuedPlayingItem['IsMuted'] = get_volume()

    def onAVStarted(self):
        LOG.info("[ onAVStarted ]")
        Utils.SyncPause = True

        if self.PlayerSkipItem != "-1":
            if self.PlayerSkipItem != "TRAILER":
                self.playnext()
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":' + self.PlayerSkipItem + '}}')

            return

        if self.isPlaying():
            kodi_id = None
            media_type = None
            EmbyId = None

            try:
                try:
                    PlayerItem = self.getVideoInfoTag()
                    Path = PlayerItem.getPath()
                except:
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
                            Selection.append(Data[4] + " - " + Utils.SizeToText(float(Data[5])))

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
                            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":' + str(playlistIndex) + '}}')

                        database.db_open.DBClose(server_id, False)
                        break

                if EmbyId:
                    self.ItemSkipUpdate.append(str(EmbyId))
                    self.queuePlayingItem(EmbyId, media_type, MediasourceID)

            self.PlayingItem = self.QueuedPlayingItem
            self.QueuedPlayingItem = {}

            if not self.isPlaying(): #check again if playing
                return

            self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)

            if self.EmbyServer and 'ItemId' in self.PlayingItem:
                self.EmbyServer.API.session_playing(self.PlayingItem)

    def PositionTracker(self):  # position required for delete option after playback ("stop_playback")
        while True:
            if xbmc.Monitor().waitForAbort(4):
                break

            if self.isPlaying():
                PositionTicks = int(self.getTime() * 10000000)

                if PositionTicks < 0:
                    PositionTicks = 0

                self.PlayingItem['PositionTicks'] = PositionTicks

    def onPlayBackSeek(self, time, seekOffset):  # Only for Audio, Video is covered by "onAVChange"
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
        LOG.info("[ onPlayBackPaused ]")

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        PositionTicks = int(self.getTime() * 10000000)

        if PositionTicks < 0:
            PositionTicks = 0

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

        Utils.SyncPause = False
        self.stop_playback(True)
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        LOG.info("[ onPlayBackEnded ]")
        Utils.SyncPause = False
        self.stop_playback(True)
        LOG.info("--<<[ playback ]")

    def SETVolume(self, data):
        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        data = json.loads(data)
        self.PlayingItem['VolumeLevel'] = data['volume']
        self.PlayingItem['IsMuted'] = data['muted']
        self.EmbyServer.API.session_progress(self.PlayingItem)

    def onPlayBackError(self):
        LOG.info("[ onPlayBackError ]")
        Utils.SyncPause = False
        self.stop_playback()

    def stop_playback(self, delete=False):
        LOG.debug("[ played info ] %s" % self.PlayingItem)

        if not self.EmbyServer or 'ItemId' not in self.PlayingItem:
            return

        self.EmbyServer.API.session_stop(self.PlayingItem)

        if self.Transcoding:
            self.EmbyServer.API.close_transcode()

        if delete:
            if Utils.offerDelete:
                Runtime = int(self.PlayingItem['RunTimeTicks'])

                if Runtime > 10:
                    if int(self.PlayingItem['PositionTicks']) > Runtime * 0.90:  # 90% Progress
                        DeleteMsg = False

                        if self.PlayingItem['Type'] == 'episode' and Utils.deleteTV:
                            DeleteMsg = True
                        elif self.PlayingItem['Type'] == 'movie' and Utils.deleteMovies:
                            DeleteMsg = True

                        if DeleteMsg:
                            LOG.info("Offer delete option")

                        if Utils.dialog("yesno", heading=Utils.Translate(30091), line1=Utils.Translate(33015)):
                            self.EmbyServer.API.delete_item(self.PlayingItem['ItemId'])
                            self.EmbyServer.library.removed([self.PlayingItem['ItemId']])

        if self.isPlaying():
            return

        threading.Thread(target=self.EmbyServer.RunLibraryJobs).start()
        self.PlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

def get_volume():
    result = helper.jsonrpc.JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
    result = result.get('result', {})
    volume = result.get('volume')
    muted = result.get('muted')
    return volume, muted

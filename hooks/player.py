import uuid
from urllib.parse import unquote_plus
import json
from _thread import start_new_thread
import xbmc
from database import dbio
from emby import listitem
from helper import utils, loghandler, pluginmenu
from dialogs import skipintrocredits

Transcoding = False
PlayerSkipItem = "-1"
SkipIntroDialog = skipintrocredits.SkipIntro("SkipIntroDialog.xml", *utils.CustomDialogParameters)
SkipCreditsDialog = skipintrocredits.SkipIntro("SkipCreditsDialog.xml", *utils.CustomDialogParameters)
LOG = loghandler.LOG('EMBY.hooks.player')

class PlayerEvents(xbmc.Player):
    def __init__(self):
        self.ItemSkipUpdate = []
        self.PlayingItem = {}
        self.QueuedPlayingItem = {}
        self.EmbyServer = None
        self.PlayingVideoAudio = True
        self.MultiselectionDone = False
        self.PositionTrackerThread = False
        result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}')).get('result', {})
        self.volume = result.get('volume', 0)
        self.muted = result.get('muted', False)
        self.TrailerPath = ""
        self.Intros = []
        self.playlistIndex = -1
        self.AddonModeTrailerItem = None
        self.MediaType = ""
        self.LibraryId = ""
        self.KodiId = ""
        self.PlayBackEnded = True
        self.IntroStartPositionTicks = 0
        self.IntroEndPositionTicks = 0
        self.CreditsPositionTicks = 0
        self.SkipIntroJumpDone = False
        self.SkipCreditsJumpDone = False
        SkipIntroDialog.set_JumpFunction(self.jump_Intro)
        SkipCreditsDialog.set_JumpFunction(self.jump_Credits)

    def onPlayBackStarted(self):
        if not self.PlayBackEnded:
            self.stop_playback(True, False)

        LOG.info("[ onPlayBackStarted ]")

        if not utils.syncduringplayback:
            utils.SyncPause['playing'] = True

    def onAVChange(self):
        LOG.info("[ onAVChange ]")

        if PlayerSkipItem != "-1" or not self.isPlaying() or self.AddonModeTrailerItem:
            LOG.debug("onAVChange not playing")
            return

        self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)
        PositionTicks = max(int(self.getTime() * 10000000), 0)
        self.PlayingItem['PositionTicks'] = PositionTicks

        if self.EmbyServer and "ItemId" in self.PlayingItem:
            self.EmbyServer.API.session_progress(self.PlayingItem)

    def queuePlayingItem(self, EmbyID, MediasourceID, PlaySessionId, IntroStartPositionTicks, IntroEndPositionTicks, CreditsPositionTicks):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
        LOG.info("[ Queue playing item ]")

        if IntroStartPositionTicks:
            self.IntroStartPositionTicks = IntroStartPositionTicks
        else:
            self.IntroStartPositionTicks = 0

        if IntroEndPositionTicks:
            self.IntroEndPositionTicks = IntroEndPositionTicks
        else:
            self.IntroEndPositionTicks = 0

        if CreditsPositionTicks:
            self.CreditsPositionTicks = CreditsPositionTicks
        else:
            self.CreditsPositionTicks = 0

        self.QueuedPlayingItem = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

        if not utils.syncduringplayback:
            utils.SyncPause['playing'] = True

        self.QueuedPlayingItem['ItemId'] = int(EmbyID)
        self.QueuedPlayingItem['MediaSourceId'] = MediasourceID
        self.QueuedPlayingItem['PlaySessionId'] = PlaySessionId
        self.QueuedPlayingItem['PositionTicks'] = 0
        self.QueuedPlayingItem['RunTimeTicks'] = 0
        self.QueuedPlayingItem['VolumeLevel'] = self.volume
        self.QueuedPlayingItem['IsMuted'] = self.muted

    def onAVStarted(self):
        LOG.info("[ onAVStarted ]")
        close_SkipIntroDialog()
        close_SkipCreditsDialog()
        self.SkipIntroJumpDone = False
        self.SkipCreditsJumpDone = False

        if not utils.syncduringplayback:
            utils.SyncPause['playing'] = True

        # Trailer from webserverice (addon mode)
        if self.AddonModeTrailerItem:
            if self.isPlaying():
                self.updateInfoTag(self.AddonModeTrailerItem)

            return

        # 3D, ISO etc. content from webserverice (addon mode)
        if PlayerSkipItem != "-1":
            self.playnext()
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % PlayerSkipItem)
            return

        # Native mode multiselection
        if self.MultiselectionDone:
            self.MultiselectionDone = False
            xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer
            return

        self.MediaType = ""
        self.LibraryId = ""
        self.KodiId = None

        if self.isPlaying():
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

            self.KodiId = PlayerItem.getDbId()

            # Extract LibraryId from Path
            if Path and Path.startswith("http://127.0.0.1:57342"):
                Temp = Path.split("/")
                self.LibraryId = Temp[4]

            self.MediaType = PlayerItem.getMediaType()

            if utils.useDirectPaths and not Path:
                PlayingFile = self.getPlayingFile()

                if PlayingFile.startswith("bluray://"):
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = PlayingFile.replace("bluray://", "")
                    PlayingFile = PlayingFile.replace("udf://", "")
                    PlayingFile = PlayingFile[:PlayingFile.find("//")]

                    for server_id, EmbyServer in list(utils.EmbyServers.items()):
                        self.EmbyServer = EmbyServer
                        embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                        EmbyId = embydb.get_mediasource_EmbyID_by_path(PlayingFile)

                        if EmbyId:
                            self.MediaType = embydb.get_item_by_id(EmbyId[0])[4]
                            Path = PlayingFile

                        dbio.DBCloseRO(server_id, "onAVStarted")

            # native content
            if Path and not Path.startswith("http://127.0.0.1:57342"):  # native mode but allow dynamic contetn in native mode
                PlaySessionId = str(uuid.uuid4()).replace("-", "")
                MediasourceID = ""

                for server_id, EmbyServer in list(utils.EmbyServers.items()):
                    self.EmbyServer = EmbyServer
                    embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                    item = embydb.get_item_by_KodiId_KodiType(self.KodiId, self.MediaType)

                    if not item:
                        dbio.DBCloseRO(server_id, "onAVStarted")
                        continue

                    EmbyId = item[0][0]

                    # Cinnemamode
                    if (utils.enableCinemaMovies and item[0][3] == "movie") or (utils.enableCinemaEpisodes and item[0][3] == "episode"):
                        if self.TrailerPath != "SKIP":
                            PlayingFile = self.getPlayingFile()

                            if self.TrailerPath != PlayingFile:  # Trailer init (load)
                                self.pause()  # Player Pause
                                self.Intros = []
                                PlayTrailer = True

                                if utils.askCinema:
                                    PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autocloseyesno) * 1000)

                                if PlayTrailer:
                                    self.Intros = self.EmbyServer.http.load_Trailers(EmbyId)

                                if self.Intros:
                                    self.play_Trailer()
                                    dbio.DBCloseRO(server_id, "onAVStarted")
                                    return

                                self.TrailerPath = ""
                                self.pause()  # Player resume
                        else:
                            self.TrailerPath = ""

                    # Multiversion
                    MediaSources = embydb.get_mediasource(EmbyId)
                    dbio.DBCloseRO(server_id, "onAVStarted")

                    if MediaSources: # video
                        MediasourceID = MediaSources[0][2]

                        if len(MediaSources) > 1:
                            self.pause()  # Player Pause
                            Selection = []

                            for Data in MediaSources:
                                Selection.append("%s - %s - %s" % (Data[4], utils.SizeToText(float(Data[5])), Data[3]))

                            MediaIndex = utils.Dialog.select(heading="Select Media Source:", list=Selection)

                            if MediaIndex == -1:
                                self.Cancel()
                                return

                            if MediaIndex == 0:
                                self.pause()  # Player Resume
                            else:
                                self.MultiselectionDone = True
                                Details = utils.load_VideoitemFromKodiDB(self.MediaType, str(self.KodiId))
                                li = utils.CreateListitem(self.MediaType, Details)
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
                    else:
                        MediasourceID = ""

                if EmbyId:
                    self.queuePlayingItem(EmbyId, MediasourceID, PlaySessionId, item[0][12], item[0][13], item[0][14])

            self.PlayBackEnded = False
            self.PlayingItem = self.QueuedPlayingItem
            self.QueuedPlayingItem = {}

            if not self.isPlaying(): #check again if playing
                return

            self.PlayingItem['RunTimeTicks'] = int(self.getTotalTime() * 10000000)

            if self.EmbyServer and 'ItemId' in self.PlayingItem:
                if VideoPlayback:
                    xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer

                self.ItemSkipUpdate += [self.PlayingItem['ItemId'], self.PlayingItem['ItemId'], self.PlayingItem['ItemId']] # triple add -> for Emby (2 times incoming msg) and once for Kodi database incoming msg
                self.EmbyServer.API.session_playing(self.PlayingItem)
                LOG.debug("ItemSkipUpdate: %s" % str(self.ItemSkipUpdate))

                if not self.PositionTrackerThread:
                    self.PositionTrackerThread = True
                    start_new_thread(self.PositionTracker, ())

    def PositionTracker(self):  # threaded
        LoopCounter = 0

        while self.EmbyServer and "ItemId" in self.PlayingItem and not utils.SystemShutdown:
            if not utils.sleep(1):
                if self.isPlaying():
                    Position = int(self.getTime())
                    LOG.debug("PositionTracker: Position: %s / IntroStartPositionTicks: %s / IntroEndPositionTicks: %s / CreditsPositionTicks: %s" % (Position, self.IntroStartPositionTicks, self.IntroEndPositionTicks, self.CreditsPositionTicks))

                    if utils.enableSkipIntro:
                        if self.IntroEndPositionTicks and self.IntroStartPositionTicks < Position < self.IntroEndPositionTicks:
                            if not self.SkipIntroJumpDone:
                                self.SkipIntroJumpDone = True

                                if utils.askSkipIntro:
                                    SkipIntroDialog.show()
                                else:
                                    self.jump_Intro()
                                    LoopCounter = 0
                                    continue
                        else:
                            close_SkipIntroDialog()

                    if utils.enableSkipCredits:
                        if self.CreditsPositionTicks and Position > self.CreditsPositionTicks:
                            if not self.SkipCreditsJumpDone:
                                self.SkipCreditsJumpDone = True

                                if utils.askSkipCredits:
                                    SkipCreditsDialog.show()
                                else:
                                    self.jump_Credits()
                                    LoopCounter = 0
                                    continue
                        else:
                            close_SkipCreditsDialog()

                    if LoopCounter % 4 == 0: # modulo 4
                        self.PlayingItem['PositionTicks'] = Position * 10000000
                        LOG.debug("PositionTracker: Report progress %s" % self.PlayingItem['PositionTicks'])
                        self.EmbyServer.API.session_progress(self.PlayingItem)
                        LoopCounter = 0

                    LoopCounter += 1

        self.PositionTrackerThread = False

    def jump_Intro(self):
        if self.isPlaying():
            LOG.info("PositionTracker: Skip intro jump %s" % self.IntroEndPositionTicks)
            self.seekTime(self.IntroEndPositionTicks)
            self.PlayingItem['PositionTicks'] = self.IntroEndPositionTicks * 10000000
            self.EmbyServer.API.session_progress(self.PlayingItem)

        self.SkipIntroJumpDone = True

    def jump_Credits(self):
        if self.isPlaying():
            LOG.info("PositionTracker: Skip credits jump %s" % self.CreditsPositionTicks)
            self.seekTime(self.PlayingItem['RunTimeTicks'] / 10000000)
            self.PlayingItem['PositionTicks'] = self.PlayingItem['RunTimeTicks']

        self.SkipCreditsJumpDone = True

    def onPlayBackSeek(self, time, seekOffset):
        LOG.info("[ onPlayBackSeek ]")

        if not self.EmbyServer or PlayerSkipItem != "-1" or 'ItemId' not in self.PlayingItem and not self.PlayingVideoAudio:
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

        if self.EmbyServer and Transcoding:
            self.EmbyServer.API.close_transcode()

        utils.SyncPause['playing'] = False
        self.stop_playback(True, True)
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        LOG.info("[ onPlayBackEnded ]")
        utils.SyncPause['playing'] = False
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
        utils.SyncPause['playing'] = False
        self.stop_playback(False, False)

    def stop_playback(self, delete, Stopped):
        if self.MultiselectionDone:
            return

        LOG.info("[ played info ] %s" % self.PlayingItem)

        # remove cached query for next up node
        if self.MediaType == "episode" and self.LibraryId in self.EmbyServer.Views.ViewItems:
            CacheId = "next_episodes_%s" % self.EmbyServer.Views.ViewItems[self.LibraryId][0]

            if CacheId in pluginmenu.QueryCache:
                del pluginmenu.QueryCache[CacheId]

        close_SkipIntroDialog()
        close_SkipCreditsDialog()
        self.PlayBackEnded = True
        PlayingItemLocal = self.PlayingItem.copy()
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

        # Set watched status
        Runtime = int(PlayingItemLocal['RunTimeTicks'])
        PlayPosition = int(PlayingItemLocal['PositionTicks'])

        # Manual progress update
        if utils.syncruntimelimits and self.LibraryId:
            MinResumePct = float(self.EmbyServer.Views.LibraryOptions[self.LibraryId]['MinResumePct']) / 100
            MaxResumePct = float(self.EmbyServer.Views.LibraryOptions[self.LibraryId]['MaxResumePct']) / 100
            RuntimeSeconds = float(Runtime / 10000000)
            PlayPositionSeconds = float(PlayPosition / 10000000)
            PercentProgress = PlayPosition / Runtime
            Playcount = 0

            if self.MediaType == "musicvideo":
                Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":%s, "properties":["playcount"]}}' % self.KodiId))
                Playcount = int(Data['result']['musicvideodetails']['playcount'])
            elif self.MediaType == "episode":
                Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":%s, "properties":["playcount"]}}' % self.KodiId))
                Playcount = int(Data['result']['episodedetails']['playcount'])
            elif self.MediaType == "movie":
                Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":%s, "properties":["playcount"]}}' % self.KodiId))
                Playcount = int(Data['result']['moviedetails']['playcount'])

            if PercentProgress < MinResumePct:
                LOG.info("Watched status %s: PercentProgress %s smaller MinResumePct %s" % (PlayingItemLocal['ItemId'], PercentProgress, MinResumePct))

                if self.MediaType == "musicvideo":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, RuntimeSeconds))
                elif self.MediaType == "episode":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, RuntimeSeconds))
                elif self.MediaType == "movie":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, RuntimeSeconds))
            elif RuntimeSeconds < float(self.EmbyServer.Views.LibraryOptions[self.LibraryId]['MinResumeDurationSeconds']):
                LOG.info("Watched status %s: Runtime %s smaller MinResumeDurationSeconds %s" % (PlayingItemLocal['ItemId'], RuntimeSeconds, self.EmbyServer.Views.LibraryOptions[self.LibraryId]['MinResumeDurationSeconds']))

                if self.MediaType == "musicvideo":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
                elif self.MediaType == "episode":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
                elif self.MediaType == "movie":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
            elif PercentProgress > MaxResumePct:
                LOG.info("Watched status %s: Runtime %s greater MaxResumePct %s" % (PlayingItemLocal['ItemId'], RuntimeSeconds, MaxResumePct))

                if self.MediaType == "musicvideo":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
                elif self.MediaType == "episode":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
                elif self.MediaType == "movie":
                    Playcount += 1
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (self.KodiId, Playcount, RuntimeSeconds))
            else:
                LOG.info("Watched status %s: Progress %s" % (PlayingItemLocal['ItemId'], PlayPositionSeconds))

                if self.MediaType == "musicvideo":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "resume": {"position": %s,"total":%s}}}' % (self.KodiId, PlayPositionSeconds, RuntimeSeconds))
                elif self.MediaType == "episode":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "resume": {"position": %s,"total":%s}}}' % (self.KodiId, PlayPositionSeconds, RuntimeSeconds))
                elif self.MediaType == "movie":
                    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "resume": {"position": %s,"total":%s}}}' % (self.KodiId, PlayPositionSeconds, RuntimeSeconds))

        self.EmbyServer.API.session_stop(PlayingItemLocal)

        if Transcoding:
            self.EmbyServer.API.close_transcode()

        if delete:
            if utils.offerDelete:
                if Runtime > 10:
                    if PlayPosition > Runtime * 0.90:  # 90% Progress
                        DeleteMsg = False

                        if self.MediaType == 'episode' and utils.deleteTV:
                            DeleteMsg = True
                        elif self.MediaType == 'movie' and utils.deleteMovies:
                            DeleteMsg = True

                        if DeleteMsg:
                            LOG.info("Offer delete option")

                            if utils.Dialog.yesno(heading=utils.Translate(30091), message=utils.Translate(33015), autoclose=int(utils.autocloseyesno) * 1000):
                                self.EmbyServer.API.delete_item(PlayingItemLocal['ItemId'])
                                start_new_thread(self.EmbyServer.library.removed, ([PlayingItemLocal['ItemId']],))

        if self.isPlaying():
            return

        start_new_thread(start_workers, ())

    def Cancel(self):
        self.stop()
        utils.SyncPause['playing'] = False
        start_new_thread(start_workers, ())

    def play_Trailer(self): # for native content
        Path = self.Intros[0]['Path']

        li = listitem.set_ListItem(self.Intros[0], self.EmbyServer.server_id)
        del self.Intros[0]

        if Path.startswith('\\\\'):
            Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

        self.TrailerPath = Path
        li.setPath(Path)
        self.play(Path, li)

# Continue sync jobs
def start_workers():
    if not utils.sleep(2):
        for _, EmbyServer in list(utils.EmbyServers.items()):
            EmbyServer.library.RunJobs()

def close_SkipIntroDialog():
    if SkipIntroDialog.dialog_open:
        SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

# Init
Player = PlayerEvents()

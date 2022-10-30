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
PlaylistRemoveItem = "-1"
result = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Application.GetProperties", "params": {"properties": ["volume", "muted"]}}')).get('result', {})
Volume = result.get('volume', 0)
Muted = result.get('muted', False)
ItemSkipUpdate = []
PlayingItem = {}
QueuedPlayingItem = {}
EmbyServerPlayback = None
PlayingVideoAudio = True
MultiselectionDone = False
PositionTrackerThread = False
TrailerPath = ""
playlistIndex = -1
AddonModeTrailerItem = None
MediaType = ""
LibraryId = ""
KodiId = ""
PlayBackEnded = True
IntroStartPositionTicks = 0
IntroEndPositionTicks = 0
CreditsPositionTicks = 0
SkipIntroJumpDone = False
SkipCreditsJumpDone = False
SkipIntroDialog = None
SkipIntroDialogEmbuary = None
SkipCreditsDialog = None
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
LOG = loghandler.LOG('EMBY.hooks.player')

class PlayerEvents(xbmc.Player):
    def __init__(self):
        # Init Dialog here, need from inside class
        globals()["SkipIntroDialog"] = skipintrocredits.SkipIntro("SkipIntroDialog.xml", *utils.CustomDialogParameters)
        globals()["SkipIntroDialogEmbuary"] = skipintrocredits.SkipIntro("SkipIntroDialogEmbuary.xml", *utils.CustomDialogParameters)
        globals()["SkipCreditsDialog"] = skipintrocredits.SkipIntro("SkipCreditsDialog.xml", *utils.CustomDialogParameters)
        SkipIntroDialog.set_JumpFunction(jump_Intro)
        SkipIntroDialogEmbuary.set_JumpFunction(jump_Intro)
        SkipCreditsDialog.set_JumpFunction(jump_Credits)

    def onPlayBackStarted(self):
        if not PlayBackEnded:
            stop_playback(True, False)

        LOG.info("[ onPlayBackStarted ]")

        if not utils.syncduringplayback:
            utils.SyncPause['playing'] = True

    def onAVChange(self):
        LOG.info("[ onAVChange ]")

        if PlaylistRemoveItem != "-1" or not self.isPlaying() or AddonModeTrailerItem:
            LOG.debug("onAVChange not playing")
            return

        globals()["PlayingItem"]['RunTimeTicks'] = int(self.getTotalTime() * 10000000)
        PositionTicks = max(int(self.getTime() * 10000000), 0)
        globals()["PlayingItem"]['PositionTicks'] = PositionTicks

        if EmbyServerPlayback and "ItemId" in PlayingItem:
            EmbyServerPlayback.API.session_progress(PlayingItem)

    def onAVStarted(self):
        LOG.info("[ onAVStarted ]")
        close_SkipIntroDialog()
        close_SkipCreditsDialog()
        globals()["SkipIntroJumpDone"] = False
        globals()["SkipCreditsJumpDone"] = False

        if not utils.syncduringplayback:
            utils.SyncPause['playing'] = True

        # Trailer from webserverice (addon mode)
        if AddonModeTrailerItem:
            if self.isPlaying():
                self.updateInfoTag(AddonModeTrailerItem)

            return

        # 3D, ISO etc. content from webserverice (addon mode)
        if PlaylistRemoveItem != "-1":
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % PlaylistRemoveItem)

        # Native mode multiselection
        if MultiselectionDone:
            globals()["MultiselectionDone"] = False
            xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer
            return

        globals()["MediaType"] = ""
        globals()["LibraryId"] = ""
        globals()["KodiId"] = None

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

                globals()["PlayingVideoAudio"] = True
            except:
                Path = ""
                PlayerItem = None
                globals()["PlayingVideoAudio"] = False

            globals()["KodiId"] = PlayerItem.getDbId()

            # Extract LibraryId from Path
            if Path and Path.startswith("http://127.0.0.1:57342"):
                Temp = Path.split("/")

                if len(Temp) > 5:
                    globals()["LibraryId"] = Temp[4]

            globals()["MediaType"] = PlayerItem.getMediaType()

            if utils.useDirectPaths and not Path:
                PlayingFile = self.getPlayingFile()

                if PlayingFile.startswith("bluray://"):
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = unquote_plus(PlayingFile)
                    PlayingFile = PlayingFile.replace("bluray://", "")
                    PlayingFile = PlayingFile.replace("udf://", "")
                    PlayingFile = PlayingFile[:PlayingFile.find("//")]

                    for server_id, EmbyServer in list(utils.EmbyServers.items()):
                        globals()["EmbyServerPlayback"] = EmbyServer
                        embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                        EmbyId = embydb.get_mediasource_EmbyID_by_path(PlayingFile)

                        if EmbyId:
                            globals()["MediaType"] = embydb.get_item_by_id(EmbyId[0])[4]
                            Path = PlayingFile

                        dbio.DBCloseRO(server_id, "onAVStarted")

            # native content
            if Path and not Path.startswith("http"):  # native mode but allow dynamic contetn in native mode
                PlaySessionId = str(uuid.uuid4()).replace("-", "")
                MediasourceID = ""

                for server_id, EmbyServer in list(utils.EmbyServers.items()):
                    globals()["EmbyServerPlayback"] = EmbyServer
                    embydb = dbio.DBOpenRO(server_id, "onAVStarted")
                    item = embydb.get_item_by_KodiId_KodiType(KodiId, MediaType)

                    if not item:
                        dbio.DBCloseRO(server_id, "onAVStarted")
                        continue

                    EmbyId = item[0][0]

                    # Cinnemamode
                    if (utils.enableCinemaMovies and item[0][3] == "movie") or (utils.enableCinemaEpisodes and item[0][3] == "episode"):
                        if TrailerPath != "SKIP":
                            PlayingFile = self.getPlayingFile()

                            if TrailerPath != PlayingFile:  # Trailer init (load)
                                self.pause()  # Player Pause
                                EmbyServerPlayback.http.Intros = []
                                PlayTrailer = True

                                if utils.askCinema:
                                    PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autocloseyesno) * 1000)

                                if PlayTrailer:
                                    EmbyServerPlayback.http.load_Trailers(EmbyId)

                                if EmbyServerPlayback.http.Intros:
                                    globals()["playlistIndex"] = playlist.getposition()
                                    play_Trailer()
                                    dbio.DBCloseRO(server_id, "onAVStarted")
                                    return

                                globals()["TrailerPath"] = ""
                                self.pause()  # Player resume
                        else:
                            globals()["TrailerPath"] = ""

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
                                Cancel()
                                return

                            if MediaIndex == 0:
                                self.pause()  # Player Resume
                            else:
                                globals()["MultiselectionDone"] = True
                                videodb = dbio.DBOpenRO("video", "onAVStarted")
                                li, _, _ = utils.load_ContentMetadataFromKodiDB(KodiId, MediaType, videodb, None)

                                if not li:
                                    return

                                dbio.DBCloseRO("video", "onAVStarted")
                                Path = MediaSources[MediaIndex][3]

                                if Path.startswith('\\\\'):
                                    Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

                                li.setPath(Path)
                                globals()["playlistIndex"] = playlist.getposition()
                                playlist.add(Path, li, playlistIndex + 1)
                                MediasourceID = MediaSources[MediaIndex][2]
                                self.playnext()
                                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":%s}}' % playlistIndex)

                            break
                    else:
                        MediasourceID = ""

                if EmbyId:
                    queuePlayingItem(EmbyId, MediasourceID, PlaySessionId, item[0][12], item[0][13], item[0][14])

            globals()["PlayBackEnded"] = False
            globals()["PlayingItem"] = QueuedPlayingItem
            globals()["QueuedPlayingItem"] = {}

            if not self.isPlaying(): #check again if playing
                return

            globals()["PlayingItem"]['RunTimeTicks'] = int(self.getTotalTime() * 10000000)

            if EmbyServerPlayback and 'ItemId' in PlayingItem:
                if VideoPlayback:
                    xbmc.executebuiltin('ActivateWindow(12005)')  # focus videoplayer

                globals()["ItemSkipUpdate"] += [PlayingItem['ItemId'], PlayingItem['ItemId'], PlayingItem['ItemId']] # triple add -> for Emby (2 times incoming msg) and once for Kodi database incoming msg
                EmbyServerPlayback.API.session_playing(PlayingItem)
                LOG.debug("ItemSkipUpdate: %s" % str(ItemSkipUpdate))

                if not PositionTrackerThread:
                    globals()["PositionTrackerThread"] = True
                    start_new_thread(PositionTracker, ())

    def onPlayBackSeek(self, time, seekOffset):
        LOG.info("[ onPlayBackSeek ]")

        if not EmbyServerPlayback or PlaylistRemoveItem != "-1" or 'ItemId' not in PlayingItem and not PlayingVideoAudio:
            return

        SeekPosition = int(time * 10000)

        if 'RunTimeTicks' in PlayingItem:
            if SeekPosition > PlayingItem['RunTimeTicks']:
                SeekPosition = PlayingItem['RunTimeTicks']

            globals()["PlayingItem"]['PositionTicks'] = SeekPosition
            EmbyServerPlayback.API.session_progress(PlayingItem)

    def onPlayBackPaused(self):
        LOG.info("[ onPlayBackPaused ]")

        if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
            return

        if self.isPlaying():
            PositionTicks = max(int(self.getTime() * 10000000), 0)
            globals()["PlayingItem"]['PositionTicks'] = PositionTicks
            globals()["PlayingItem"]['IsPaused'] = True
            EmbyServerPlayback.API.session_progress(PlayingItem)

        LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        LOG.info("[ onPlayBackResumed ]")

        if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
            return

        globals()["PlayingItem"]['IsPaused'] = False
        EmbyServerPlayback.API.session_progress(PlayingItem)
        LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        LOG.info("[ onPlayBackStopped ]")
        utils.SyncPause['playing'] = False
        stop_playback(True, True)
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        LOG.info("[ onPlayBackEnded ]")
        utils.SyncPause['playing'] = False
        stop_playback(True, False)
        LOG.info("--<<[ playback ]")

    def onPlayBackError(self):
        LOG.info("[ onPlayBackError ]")
        utils.SyncPause['playing'] = False
        stop_playback(False, False)

def SETVolume(data):
    data = json.loads(data)
    globals()["Muted"] = data["muted"]
    globals()["Volume"] = data["volume"]

    if not EmbyServerPlayback or 'ItemId' not in PlayingItem:
        return

    globals()["PlayingItem"]['VolumeLevel'] = Volume
    globals()["PlayingItem"]['IsMuted'] = Muted
    EmbyServerPlayback.API.session_progress(PlayingItem)

def stop_playback(delete, Stopped):
    if MultiselectionDone:
        return

    LOG.info("[ played info ] %s" % PlayingItem)

    # remove cached query for next up node
    if MediaType == "episode" and LibraryId in EmbyServerPlayback.Views.ViewItems:
        CacheId = "next_episodes_%s" % EmbyServerPlayback.Views.ViewItems[LibraryId][0]

        if CacheId in pluginmenu.QueryCache:
            del pluginmenu.QueryCache[CacheId]

    close_SkipIntroDialog()
    close_SkipCreditsDialog()
    globals()["PlayBackEnded"] = True
    PlayingItemLocal = PlayingItem.copy()
    globals()["PlayingItem"] = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False}

    # Trailer is playing, skip
    if AddonModeTrailerItem:
        globals()["AddonModeTrailerItem"] = None
        return

    # Trailers for native content
    if not Stopped:
        # Play init item after native content trailer playback
        if TrailerPath and not EmbyServerPlayback.http.Intros:
            globals()["TrailerPath"] = "SKIP"
            EmbyServerPlayback.http.Intros = []
            utils.XbmcPlayer.play(playlist, None, False, playlistIndex)
            return

        # play trailers for native content
        if EmbyServerPlayback.http.Intros:
            play_Trailer()
            return

    EmbyServerPlayback.http.Intros = []
    globals()["TrailerPath"] = ""

    if not EmbyServerPlayback or 'ItemId' not in PlayingItemLocal:
        return

    # Set watched status
    Runtime = int(PlayingItemLocal['RunTimeTicks'])
    PlayPosition = int(PlayingItemLocal['PositionTicks'])

    # Manual progress update
    if utils.syncruntimelimits and LibraryId:
        MinResumePct = float(EmbyServerPlayback.Views.LibraryOptions[LibraryId]['MinResumePct']) / 100
        MaxResumePct = float(EmbyServerPlayback.Views.LibraryOptions[LibraryId]['MaxResumePct']) / 100
        RuntimeSeconds = float(Runtime / 10000000)
        PlayPositionSeconds = float(PlayPosition / 10000000)
        PercentProgress = PlayPosition / Runtime
        Playcount = 0

        if MediaType == "musicvideo":
            Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":%s, "properties":["playcount"]}}' % KodiId))
            Playcount = int(Data['result']['musicvideodetails']['playcount'])
        elif MediaType == "episode":
            Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":%s, "properties":["playcount"]}}' % KodiId))
            Playcount = int(Data['result']['episodedetails']['playcount'])
        elif MediaType == "movie":
            Data = json.loads(xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":%s, "properties":["playcount"]}}' % KodiId))
            Playcount = int(Data['result']['moviedetails']['playcount'])

        if PercentProgress < MinResumePct:
            LOG.info("Watched status %s: PercentProgress %s smaller MinResumePct %s" % (PlayingItemLocal['ItemId'], PercentProgress, MinResumePct))

            if MediaType == "musicvideo":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "resume": {"position": 0,"total":%s}}}' % (KodiId, RuntimeSeconds))
            elif MediaType == "episode":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "resume": {"position": 0,"total":%s}}}' % (KodiId, RuntimeSeconds))
            elif MediaType == "movie":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "resume": {"position": 0,"total":%s}}}' % (KodiId, RuntimeSeconds))
        elif RuntimeSeconds < float(EmbyServerPlayback.Views.LibraryOptions[LibraryId]['MinResumeDurationSeconds']):
            LOG.info("Watched status %s: Runtime %s smaller MinResumeDurationSeconds %s" % (PlayingItemLocal['ItemId'], RuntimeSeconds, EmbyServerPlayback.Views.LibraryOptions[LibraryId]['MinResumeDurationSeconds']))

            if MediaType == "musicvideo":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
            elif MediaType == "episode":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
            elif MediaType == "movie":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
        elif PercentProgress > MaxResumePct:
            LOG.info("Watched status %s: Runtime %s greater MaxResumePct %s" % (PlayingItemLocal['ItemId'], RuntimeSeconds, MaxResumePct))

            if MediaType == "musicvideo":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
            elif MediaType == "episode":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
            elif MediaType == "movie":
                Playcount += 1
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "playcount": %s, "resume": {"position": 0,"total":%s}}}' % (KodiId, Playcount, RuntimeSeconds))
        else:
            LOG.info("Watched status %s: Progress %s" % (PlayingItemLocal['ItemId'], PlayPositionSeconds))

            if MediaType == "musicvideo":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMusicVideoDetails", "params":{"musicvideoid":%s, "resume": {"position": %s,"total":%s}}}' % (KodiId, PlayPositionSeconds, RuntimeSeconds))
            elif MediaType == "episode":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetEpisodeDetails", "params":{"episodeid":%s, "resume": {"position": %s,"total":%s}}}' % (KodiId, PlayPositionSeconds, RuntimeSeconds))
            elif MediaType == "movie":
                xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.SetMovieDetails", "params":{"movieid":%s, "resume": {"position": %s,"total":%s}}}' % (KodiId, PlayPositionSeconds, RuntimeSeconds))

    EmbyServerPlayback.API.session_stop(PlayingItemLocal)

    if delete:
        if utils.offerDelete:
            if Runtime > 10:
                if PlayPosition > Runtime * 0.90:  # 90% Progress
                    DeleteMsg = False

                    if MediaType == 'episode' and utils.deleteTV:
                        DeleteMsg = True
                    elif MediaType == 'movie' and utils.deleteMovies:
                        DeleteMsg = True

                    if DeleteMsg:
                        LOG.info("Offer delete option")

                        if utils.Dialog.yesno(heading=utils.Translate(30091), message=utils.Translate(33015), autoclose=int(utils.autocloseyesno) * 1000):
                            EmbyServerPlayback.API.delete_item(PlayingItemLocal['ItemId'])
                            start_new_thread(EmbyServerPlayback.library.removed, ([PlayingItemLocal['ItemId']],))

    if utils.XbmcPlayer.isPlaying():
        return

    start_new_thread(start_workers, ())

def play_Trailer(): # for native content
    Path = EmbyServerPlayback.http.Intros[0]['Path']
    li = listitem.set_ListItem(EmbyServerPlayback.http.Intros[0], EmbyServerPlayback.server_id)
    del EmbyServerPlayback.http.Intros[0]

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    globals()["TrailerPath"] = Path
    li.setPath(Path)
    utils.XbmcPlayer.play(Path, li)

def PositionTracker():  # threaded
    LoopCounter = 0

    while EmbyServerPlayback and "ItemId" in PlayingItem and not utils.SystemShutdown:
        if not utils.sleep(1):
            if utils.XbmcPlayer.isPlaying():
                Position = int(utils.XbmcPlayer.getTime())
                LOG.debug("PositionTracker: Position: %s / IntroStartPositionTicks: %s / IntroEndPositionTicks: %s / CreditsPositionTicks: %s" % (Position, IntroStartPositionTicks, IntroEndPositionTicks, CreditsPositionTicks))

                if utils.enableSkipIntro:
                    if IntroEndPositionTicks and IntroStartPositionTicks < Position < IntroEndPositionTicks:
                        if not SkipIntroJumpDone:
                            globals()["SkipIntroJumpDone"] = True

                            if utils.askSkipIntro:
                                if utils.skipintroembuarydesign:
                                    SkipIntroDialogEmbuary.show()
                                else:
                                    SkipIntroDialog.show()
                            else:
                                jump_Intro()
                                LoopCounter = 0
                                continue
                    else:
                        close_SkipIntroDialog()

                if utils.enableSkipCredits:
                    if CreditsPositionTicks and Position > CreditsPositionTicks:
                        if not SkipCreditsJumpDone:
                            globals()["SkipCreditsJumpDone"] = True

                            if utils.askSkipCredits:
                                SkipCreditsDialog.show()
                            else:
                                jump_Credits()
                                LoopCounter = 0
                                continue
                    else:
                        close_SkipCreditsDialog()

                if LoopCounter % 4 == 0: # modulo 4
                    globals()["PlayingItem"]['PositionTicks'] = Position * 10000000
                    LOG.debug("PositionTracker: Report progress %s" % PlayingItem['PositionTicks'])
                    EmbyServerPlayback.API.session_progress(PlayingItem)
                    LoopCounter = 0

                LoopCounter += 1

    globals()["PositionTrackerThread"] = False

def jump_Intro():
    if utils.XbmcPlayer.isPlaying():
        LOG.info("PositionTracker: Skip intro jump %s" % IntroEndPositionTicks)
        utils.XbmcPlayer.seekTime(IntroEndPositionTicks)
        globals()["PlayingItem"]['PositionTicks'] = IntroEndPositionTicks * 10000000
        EmbyServerPlayback.API.session_progress(PlayingItem)

    globals()["SkipIntroJumpDone"] = True

def jump_Credits():
    if utils.XbmcPlayer.isPlaying():
        LOG.info("PositionTracker: Skip credits jump %s" % CreditsPositionTicks)
        utils.XbmcPlayer.seekTime(PlayingItem['RunTimeTicks'] / 10000000)
        globals()["PlayingItem"]['PositionTicks'] = PlayingItem['RunTimeTicks']

    globals()["SkipCreditsJumpDone"] = True

# Continue sync jobs
def start_workers():
    if not utils.sleep(2):
        for _, EmbyServer in list(utils.EmbyServers.items()):
            EmbyServer.library.RunJobs()

def close_SkipIntroDialog():
    if utils.skipintroembuarydesign:
        if SkipIntroDialogEmbuary.dialog_open:
            SkipIntroDialogEmbuary.close()
    else:
        if SkipIntroDialog.dialog_open:
            SkipIntroDialog.close()

def close_SkipCreditsDialog():
    if SkipCreditsDialog.dialog_open:
        SkipCreditsDialog.close()

def queuePlayingItem(EmbyID, MediasourceID, PlaySessionId, IntroStartPosTicks, IntroEndPosTicks, CreditsPosTicks):  # loaded directly from webservice.py for addon content, or via "onAVStarted" for native content
    LOG.info("[ Queue playing item ]")

    if not utils.syncduringplayback:
        utils.SyncPause['playing'] = True

    if IntroStartPosTicks:
        globals()["IntroStartPositionTicks"] = IntroStartPosTicks
    else:
        globals()["IntroStartPositionTicks"] = 0

    if IntroEndPosTicks:
        globals()["IntroEndPositionTicks"] = IntroEndPosTicks
    else:
        globals()["IntroEndPositionTicks"] = 0

    if CreditsPosTicks:
        globals()["CreditsPositionTicks"] = CreditsPosTicks
    else:
        globals()["CreditsPositionTicks"] = 0

    globals()["QueuedPlayingItem"] = {'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(EmbyID), 'MediaSourceId': MediasourceID, 'PlaySessionId': PlaySessionId, 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': Volume, 'IsMuted': Muted}

def Cancel():
    utils.XbmcPlayer.stop()
    utils.SyncPause['playing'] = False
    start_new_thread(start_workers, ())

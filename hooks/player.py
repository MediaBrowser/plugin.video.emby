# -*- coding: utf-8 -*-
import json
import threading
import uuid

import xbmc
import xbmcgui

import database.database
import database.emby_db
import core.queries_videos
import helper.utils
import helper.loghandler

class ProgressUpdates(threading.Thread):
    def __init__(self, Player):
        self.Player = Player
        self.Exit = False
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True

    def run(self):
        while True:
            if xbmc.Monitor().waitForAbort(5):
                return

            if not self.Exit:
                self.Player.report_playback(True)
            else:
                return

class PlayerEvents(xbmc.Player):
    def __init__(self):
        self.CurrentlyPlaying = {}
        self.LOG = helper.loghandler.LOG('EMBY.hooks.player.Player')
        self.Trailer = False
        self.PlayerReloadIndex = "-1"
        self.PlayerLastItem = ""
        self.PlayerLastItemID = "-1"
        self.ItemSkipUpdate = []
        self.ItemSkipUpdateAfterStop = []
        self.ItemSkipUpdateReset = False
        self.SyncPause = False
        self.ProgressThread = None
        self.PlaySessionId = ""
        self.MediasourceID = ""
        self.Transcoding = False
        self.CurrentItem = {}
        self.SkipUpdate = False
        self.PlaySessionIdLast = ""

    #Threaded by Monitor
    def OnStop(self, EmbyServer):
        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        if self.Transcoding:
            EmbyServer.API.close_transcode()

        self.SyncPause = False

    #Threaded by Monitor
    def OnPlay(self, data, EmbyServer):
        self.LOG.info("[ OnPlay ] %s " % data)

        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        self.SyncPause = True

        if not self.Trailer:
            if not "id" in data['item']:
                self.CurrentItem['Id'] = EmbyServer.Utils.window('emby.DynamicItem_' + EmbyServer.Utils.ReplaceSpecialCharecters(data['item']['title']))

                if not self.CurrentItem['Id']:
                    self.CurrentItem['Tracking'] = False
                    return
            else:
                kodi_id = data['item']['id']
                media_type = data['item']['type']
                item = database.database.get_item(EmbyServer.Utils, kodi_id, media_type)

                if item:
                    self.CurrentItem['Id'] = item[0]
                else:
                    self.CurrentItem['Tracking'] = False
                    return #Kodi internal Source

            if EmbyServer.Utils.direct_path: #native mode
                self.PlaySessionId = str(uuid.uuid4()).replace("-", "")

            self.CurrentItem['Tracking'] = True
            self.CurrentItem['Type'] = data['item']['type']
            self.CurrentItem['Volume'], self.CurrentItem['Muted'] = self.get_volume()
            self.CurrentItem['MediaSourceId'] = self.MediasourceID
            self.CurrentItem['EmbyServer'] = EmbyServer
            self.CurrentItem['RunTime'] = 0
            self.CurrentItem['CurrentPosition'] = 0
            self.CurrentItem['Paused'] = False
            self.CurrentItem['MediaSourceId'] = self.MediasourceID
            self.CurrentItem['Volume'], self.CurrentItem['Muted'] = self.get_volume()

    def onAVStarted(self):
        self.LOG.info("[ onAVStarted ]")
        new_thread = PlayerWorker(self, "ThreadAVStarted")
        new_thread.start()

    def ThreadAVStarted(self):
        self.LOG.info("[ ThreadAVStarted ]")
        self.stop_playback(True)

        while not self.CurrentItem: #wait for OnPlay
            if xbmc.Monitor().waitForAbort(1):
                return

        if not self.CurrentItem['Tracking']:
            self.CurrentItem = {}
            return

        if not self.set_CurrentPosition(): #Stopped directly after started playing 
            self.LOG.info("[ fast stop detected ]")
            return

        self.CurrentItem['PlaySessionId'] = self.PlaySessionId
        self.CurrentlyPlaying = self.CurrentItem
        self.CurrentItem = {}
        self.LOG.info("-->[ play/%s ] %s" % (self.CurrentlyPlaying['Id'], self.CurrentlyPlaying))
        data = {
            'ItemId': self.CurrentlyPlaying['Id'],
            'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
            'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
        }

        #Init session
        self.CurrentlyPlaying['EmbyServer'].API.session_playing(data)
        self.SkipUpdate = False
        self.report_playback(False)

        if not self.ProgressThread:
            self.ProgressThread = ProgressUpdates(self)
            self.ProgressThread.start()

    def SETVolume(self, Volume, Mute):
        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Volume'] = Volume
        self.CurrentlyPlaying['Muted'] = Mute
        self.report_playback(False)

    def set_CurrentPosition(self):
        try:
            CurrentPosition = int(self.getTime() * 10000000)

            if CurrentPosition < 0:
                CurrentPosition = 0

            self.CurrentlyPlaying['CurrentPosition'] = CurrentPosition
            return True
        except:
            return False

    def set_Runtime(self):
        try:
            self.CurrentlyPlaying['RunTime'] = int(self.getTotalTime() * 10000000)
            return bool(self.CurrentlyPlaying['RunTime'])
        except:
            return False

    #Report playback progress to emby server.
    def report_playback(self, UpdatePosition=True):
        if not self.CurrentlyPlaying or self.Trailer or self.SkipUpdate:
            self.SkipUpdate = False
            return

        if not self.CurrentlyPlaying['RunTime']:
            if not self.set_Runtime():
                self.LOG.info("[ skip progress update, no runtime info ]")
                return

        if UpdatePosition:
            if not self.set_CurrentPosition():
                self.LOG.info("[ skip progress update, no position info ]")
                return

        data = {
            'ItemId': self.CurrentlyPlaying['Id'],
            'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
            'PositionTicks': self.CurrentlyPlaying['CurrentPosition'],
            'RunTimeTicks': self.CurrentlyPlaying['RunTime'],
            'CanSeek': True,
            'QueueableMediaTypes': "Video,Audio",
            'VolumeLevel': self.CurrentlyPlaying['Volume'],
            'IsPaused': self.CurrentlyPlaying['Paused'],
            'IsMuted': self.CurrentlyPlaying['Muted'],
            'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
        }
        self.CurrentlyPlaying['EmbyServer'].API.session_progress(data)

    def onAVChange(self):
        self.LOG.info("[ onAVChange ]")

    def onQueueNextItem(self):
        self.LOG.info("[ onQueueNextItem ]")

    def onPlayBackStarted(self):
        self.LOG.info("[ onPlayBackStarted ]")

        if self.ReloadStream():#Media reload (3D Movie)
            return

    def onPlayBackPaused(self):
        self.LOG.info("[ onPlayBackPaused ]")

        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Paused'] = True
        self.report_playback()
        self.LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        self.LOG.info("[ onPlayBackResumed ]")

        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Paused'] = False
        self.report_playback(False)
        self.LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        self.LOG.info("[ onPlayBackStopped ]")

        if self.ReloadStream():#Media reload (3D Movie)
            return

        self.PlayerLastItemID = "-1"
        self.PlayerLastItem = ""
        self.Trailer = False
        self.SyncPause = True
        self.stop_playback(False)
        self.LOG.info("--<[ playback ]")

    def onPlayBackSeek(self, time, seekOffset):
        self.LOG.info("[ onPlayBackSeek ]")
        SeekPosition = int(time * 10000)

        if self.CurrentlyPlaying['RunTime']:
            if SeekPosition > self.CurrentlyPlaying['RunTime']:
                SeekPosition = self.CurrentlyPlaying['RunTime']

        self.CurrentlyPlaying['CurrentPosition'] = SeekPosition
        self.report_playback(False)
        self.SkipUpdate = True #Pause progress updates for one cycle -> new seek position

    def onPlayBackEnded(self):
        self.LOG.info("[ onPlayBackEnded ]")

        if self.Trailer or self.ReloadStream():
            return

        self.PlayerLastItemID = "-1"
        self.PlayerLastItem = ""
        self.SyncPause = True
        self.stop_playback(False)
        self.LOG.info("--<<[ playback ]")

    def get_volume(self):
        result = helper.utils.JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')
        return volume, muted

    def onPlayBackError(self):
        self.LOG.warning("Playback error occured")
        self.stop_playback(False)

    def ReloadStream(self):
        #Media has changed -> reload
        if self.PlayerReloadIndex != "-1":
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.play(item=playlist, startpos=int(self.PlayerReloadIndex))
            self.PlayerReloadIndex = "-1"
            return True

        return False

    def stop_playback(self, Init):
        if self.CurrentlyPlaying:
            self.LOG.debug("[ played info ] %s" % self.CurrentlyPlaying)
            data = {
                'ItemId': self.CurrentlyPlaying['Id'],
                'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
                'PositionTicks': self.CurrentlyPlaying['CurrentPosition'],

                'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
            }
            self.CurrentlyPlaying['EmbyServer'].API.session_stop(data)

            if self.Transcoding:
                self.CurrentlyPlaying['EmbyServer'].API.close_transcode()

            self.CurrentlyPlaying = {}

        if not Init:
            self.ItemSkipUpdate = self.ItemSkipUpdateAfterStop
            self.ItemSkipUpdateReset = True
            self.SyncPause = False

class PlayerWorker(threading.Thread):
    def __init__(self, Player, method):
        self.method = method
        self.Player = Player
        threading.Thread.__init__(self)

    def run(self):
        if self.method == 'ThreadAVStarted':
            self.Player.ThreadAVStarted()
            return

#Call from WebSocket to manipulate playing URL
class WebserviceOnPlay(threading.Thread):
    def __init__(self, Player, EmbyServer, WebserviceEventIn, WebserviceEventOut):
        self.LOG = helper.loghandler.LOG('EMBY.hooks.player.WebserviceOnPlay')
        self.EmbyServer = EmbyServer
        self.WebserviceEventIn = WebserviceEventIn
        self.WebserviceEventOut = WebserviceEventOut
        self.Player = Player
        self.Intros = None
        self.IntrosIndex = 0
        self.Exit = False
        self.Trailers = False
        self.EmbyIDLast = -1
        self.EmbyID = -1
        self.URLQuery = ""
        self.Type = ""
        self.KodiID = -1
        self.KodiFileID = -1
        self.Force = False
        self.Filename = ""
        self.MediaSources = []
        self.TranscodeReasons = ""
        self.TargetVideoBitrate = 0
        self.TargetAudioBitrate = 0
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True
        self.WebserviceEventOut.put("quit")

    def run(self):
        while not self.Exit:
            IncommingData = self.WebserviceEventOut.get()
            self.LOG.debug("[ query IncommingData ] %s" % IncommingData)

            if IncommingData == "quit":
                break

            self.EmbyID, MediasourceID, self.Type, BitrateFromURL, self.Filename = self.GetParametersFromURLQuery(IncommingData)

            if 'audio' in IncommingData:
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/audio/" + self.EmbyID + "/stream?static=true&PlaySessionId=" + self.GETPlaySessionId("") + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename)
                continue

            if 'livetv' in IncommingData:
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream.ts?PlaySessionId=" + self.GETPlaySessionId("") + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename)
                continue

            if 'main.m3u8' in IncommingData: #Dynamic Transcode query
                IncommingData = IncommingData.replace("/movie/", "/")
                IncommingData = IncommingData.replace("/musicvideo/", "/")
                IncommingData = IncommingData.replace("/tvshow/", "/")
                IncommingData = IncommingData.replace("/video/", "/")
                IncommingData = IncommingData.replace("/trailer/", "/")
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyIDLast + IncommingData)
                continue

            if self.Player.Transcoding:
                self.EmbyServer.API.close_transcode()

            self.Player.Transcoding = False
            self.URLQuery = "http://127.0.0.1:57578" + IncommingData

            if self.Type == "movies":
                self.Type = "movie"
            elif self.Type == "tvshows":
                self.Type = "episode"
            elif self.Type == "musicvideos":
                self.Type = "musicvideo"

            self.Player.SyncPause = True

            #Reload Playlistitem after playlist injection
            if self.Player.PlayerReloadIndex != "-1":
                URL = "RELOAD"
                self.WebserviceEventIn.put(URL)
                continue

            #Todo: SKIP TRAILERS IF MULTIPART!
            #Trailers
            if self.EmbyServer.Utils.EnableCinema and self.Player.PlayerLastItemID != self.EmbyID:
                PlayTrailer = True

                if self.EmbyServer.Utils.AskCinema:
                    if not self.Player.Trailer:
                        self.Trailers = False

                    if not self.Trailers and not self.Player.Trailer:
                        self.Trailers = True
                        PlayTrailer = self.EmbyServer.Utils.dialog("yesno", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33016))

                if PlayTrailer:
                    if self.Player.PlayerLastItem != IncommingData or not self.Player.Trailer:
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
                        self.Player.PlayerLastItem = IncommingData
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Intros = self.EmbyServer.API.get_intros(self.EmbyID)
                        #self.IntrosLocal = self.EmbyServer.API.get_local_trailers(self.EmbyID)
                        self.Player.Trailer = True

                    try: #Play next trailer
                        self.WebserviceEventIn.put(self.Intros['Items'][self.IntrosIndex]['Path'])
                        self.IntrosIndex += 1
                        continue
                    except: #No more trailers
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')
                        self.Force = True
                        self.Player.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Player.Trailer = False
                else:
                    xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')

            #Select mediasources, Audiostreams, Subtitles
            if self.Player.PlayerLastItemID != self.EmbyID or self.Force:
                self.Force = False
                self.Player.PlayerLastItemID = str(self.EmbyID)

                with database.database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
                    emby_dbT = database.emby_db.EmbyDatabase(embydb.cursor)
                    EmbyDBItem = emby_dbT.get_kodiid(self.EmbyID)

                    if EmbyDBItem: #Item not synced to Kodi DB
                        if EmbyDBItem[1]:
                            PresentationKey = EmbyDBItem[1].split("-")
                            self.Player.ItemSkipUpdate.append(PresentationKey[0])
                            self.Player.ItemSkipUpdateAfterStop.append(PresentationKey[0])

                        self.KodiID = str(EmbyDBItem[0])
                        self.KodiFileID = str(EmbyDBItem[2])
                    else:
                        self.Player.PlayerReloadIndex = "-1"
                        self.Player.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Player.Trailer = False
                        self.SubTitlesAdd(MediasourceID, emby_dbT)
                        self.Player.Transcoding = self.IsTranscoding(BitrateFromURL, None)

                        if self.Player.Transcoding:
                            URL = self.GETTranscodeURL(MediasourceID, self.Filename, False, False)
                        else:
                            URL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

                        self.WebserviceEventIn.put(URL)
                        continue

                    self.MediaSources = emby_dbT.get_mediasource(self.EmbyID)

                    if len(self.MediaSources) == 1:
                        self.Player.PlayerLastItemID = "-1"
                        self.WebserviceEventIn.put(self.LoadData(MediasourceID, emby_dbT, 0))
                        continue

                    #Multiversion
                    Selection = []

                    for Data in self.MediaSources:
                        Selection.append(Data[8] + " - " + self.SizeToText(float(Data[7])))

                    MediaIndex = self.EmbyServer.Utils.dialog("select", heading="Select Media Source:", list=Selection)

                    if MediaIndex <= 0:
                        MediaIndex = 0
                        self.Player.PlayerLastItemID = "-1"

                    MediasourceID = self.MediaSources[MediaIndex][3]
                    self.WebserviceEventIn.put(self.LoadData(MediasourceID, emby_dbT, MediaIndex))

    #Load SRT subtitles
    def SubTitlesAdd(self, MediasourceID, emby_dbT):
        Subtitles = emby_dbT.get_Subtitles(self.EmbyID, 0)

        if len(Subtitles) >= 1:
            CounterSubTitle = 0

            for Data in Subtitles:
                CounterSubTitle += 1

                if Data[3] == "srt":
                    SubTitleURL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/" + MediasourceID + "/Subtitles/" + str(Data[18]) + "/stream.srt"
                    request = {'type': "GET", 'url': SubTitleURL, 'params': {}}

                    #Get Subtitle Settings
                    with database.database.Database(self.EmbyServer.Utils, 'video', False) as videodb:
                        videodb.cursor.execute(core.queries_videos.get_settings, (self.KodiFileID,))
                        FileSettings = videodb.cursor.fetchone()

                    if FileSettings:
                        EnableSubtitle = bool(FileSettings[9])
                    else:
                        EnableSubtitle = False #Read default value

                    if Data[4]:
                        SubtileLanguage = Data[4]
                    else:
                        SubtileLanguage = "unknown"

                    Filename = self.EmbyServer.Utils.PathToFilenameReplaceSpecialCharecters(str(CounterSubTitle) + "." + SubtileLanguage + ".srt")
                    Path = self.EmbyServer.Utils.download_external_subs(request, Filename, self.EmbyServer)

                    if Path:
                        self.Player.setSubtitles(Path)
                        self.Player.showSubtitles(EnableSubtitle)

    def LoadData(self, MediasourceID, emby_dbT, MediaIndex):
        VideoStreams = emby_dbT.get_videostreams(self.EmbyID, MediaIndex)
        AudioStreams = emby_dbT.get_AudioStreams(self.EmbyID, MediaIndex)

        if not VideoStreams:
            self.LOG.warning("[ VideoStreams not found ] %s" % self.EmbyID)
            return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

        Bitrate = VideoStreams[0][9]
        self.Player.Transcoding = self.IsTranscoding(Bitrate, VideoStreams[0][3]) #add codec from videostreams, Bitrate (from file)

        if self.Player.Transcoding:
            SubtitleIndex = -1
            AudioIndex = -1
            Subtitles = []
            Subtitles = emby_dbT.get_Subtitles(self.EmbyID, MediaIndex)

            if len(AudioStreams) >= 2:
                Selection = []

                for Data in AudioStreams:
                    Selection.append(Data[7])

                AudioIndex = self.EmbyServer.Utils.dialog("select", heading="Select Audio Stream:", list=Selection)

            if len(Subtitles) >= 1:
                Selection = []

                for Data in Subtitles:
                    Selection.append(Data[7])

                SubtitleIndex = self.EmbyServer.Utils.dialog("select", heading="Select Subtitle:", list=Selection)

            if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0: #No change -> resume
                return self.GETTranscodeURL(MediasourceID, self.Filename, False, False)

            if AudioIndex <= 0:
                AudioIndex = 0

            if SubtitleIndex < 0:
                Subtitle = None
            else:
                Subtitle = Subtitles[SubtitleIndex]

            return self.UpdateItem(MediasourceID, self.MediaSources[MediaIndex], VideoStreams[0], AudioStreams[AudioIndex], emby_dbT, Subtitle)

        if MediaIndex == 0:
            self.SubTitlesAdd(MediasourceID, emby_dbT)
            return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

        return self.UpdateItem(MediasourceID, self.MediaSources[MediaIndex], VideoStreams[0], AudioStreams[0], emby_dbT, False)

    def GETTranscodeURL(self, MediasourceID, Filename, Audio, Subtitle):
        TranscodingVideo = ""
        TranscodingAudio = ""

        if Subtitle:
            Subtitle = "&SubtitleStreamIndex=" + Subtitle
        else:
            Subtitle = ""

        if Audio:
            Audio = "&AudioStreamIndex=" + Audio
        else:
            Audio = ""

        if self.TargetVideoBitrate:
            TranscodingVideo = "&VideoBitrate=" + str(self.TargetVideoBitrate)

        if self.TargetAudioBitrate:
            TranscodingAudio = "&AudioBitrate=" + str(self.TargetAudioBitrate)

        if Filename:
            Filename = "&" + Filename

        return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/master.m3u8?api_key=" + self.EmbyServer.Data['auth.token'] + "&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&VideoCodec=" + self.EmbyServer.Utils.VideoCodecID + "&AudioCodec=" + self.EmbyServer.Utils.AudioCodecID + TranscodingVideo + TranscodingAudio + Audio + Subtitle + "&TranscodeReasons=" + self.TranscodeReasons + Filename

    def SizeToText(self, size):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        suffixIndex = 0

        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1
            size = size / 1024.0

        return "%.*f%s" % (2, size, suffixes[suffixIndex])

    def GETPlaySessionId(self, MediasourceID):
        self.Player.PlaySessionId = str(uuid.uuid4()).replace("-", "")
        self.Player.MediasourceID = MediasourceID
        return self.Player.PlaySessionId

    def IsTranscoding(self, Bitrate, Codec):
        if self.EmbyServer.Utils.TranscodeH265:
            if Codec in ("h265", "hevc"):
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.TranscodeDivx:
            if Codec == "msmpeg4v3":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.TranscodeXvid:
            if Codec == "mpeg4":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.TranscodeMpeg2:
            if Codec == "mpeg2video":
                self.IsTranscodingByCodec(Bitrate)
                return True

        self.TargetVideoBitrate = self.EmbyServer.Utils.VideoBitrate
        self.TargetAudioBitrate = self.EmbyServer.Utils.AudioBitrate
        self.TranscodeReasons = "ContainerBitrateExceedsLimit"
        return Bitrate >= self.TargetVideoBitrate

    def IsTranscodingByCodec(self, Bitrate):
        if Bitrate >= self.EmbyServer.Utils.VideoBitrate:
            self.TranscodeReasons = "ContainerBitrateExceedsLimit"
            self.TargetVideoBitrate = self.EmbyServer.Utils.VideoBitrate
            self.TargetAudioBitrate = self.EmbyServer.Utils.AudioBitrate
        else:
            self.TranscodeReasons = "VideoCodecNotSupported"
            self.TargetVideoBitrate = 0
            self.TargetAudioBitrate = 0

    def GetParametersFromURLQuery(self, StreamURL):
        Type = StreamURL[1:]
        Type = Type[:Type.find("/")]
        Temp = StreamURL[StreamURL.rfind("/") + 1:]
        Data = Temp.split("-")

        if len(Data[0]) < 10:
            Filename = StreamURL[StreamURL.find("stream-") + 7:]
            self.EmbyIDLast = Data[0]

            try:
                BitrateFromURL = int(Data[2])
            except:
                BitrateFromURL = 0

            self.Player.SyncPause = True
            self.Player.ItemSkipUpdate.append(Data[0])
            self.Player.ItemSkipUpdateAfterStop.append(Data[0])
            return Data[0], Data[1], Type, BitrateFromURL, Filename

        return None, None, None, None, None

    def UpdateItem(self, MediasourceID, MediaSource, VideoStream, AudioStream, emby_dbT, Subtitle):
        if self.Type == "movie":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":' + self.KodiID + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "director", "trailer", "tagline", "plotoutline", "originaltitle",  "writer", "studio", "mpaa", "country", "imdbnumber", "set", "showlink", "top250", "votes", "sorttitle",  "dateadded", "tag", "userrating", "cast", "premiered", "setid", "art", "lastplayed", "uniqueid"]}}')
            Data = json.loads(result)
            Details = Data['result']['moviedetails']
        elif self.Type == "episode":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":' + self.KodiID + ', "properties":["title", "firstaired", "originaltitle", "productioncode", "rating", "season", "seasonid", "showtitle", "specialsortepisode", "specialsortseason", "tvshowid", "userrating", "votes", "episode", "plot", "writer", "cast", "art", "lastplayed", "uniqueid"]}}')
            Data = json.loads(result)
            Details = Data['result']['episodedetails']
            Details['tvshowtitle'] = Details['showtitle']
        elif self.Type == "musicvideo":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":' + self.KodiID + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "director", "studio", "dateadded", "tag", "userrating", "premiered", "album", "artist", "track", "art", "lastplayed"]}}')
            Data = json.loads(result)
            Details = Data['result']['musicvideodetails']

        Details['mediatype'] = self.Type
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        Filename = self.EmbyServer.Utils.PathToFilenameReplaceSpecialCharecters(MediaSource[4])

        if Subtitle:
            SubtitleStream = str(int(Subtitle[2]) + 2)
        else:
            SubtitleStream = ""

        if self.Player.Transcoding:
            URL = self.GETTranscodeURL(MediasourceID, Filename, str(int(AudioStream[2]) + 1), SubtitleStream)
        else: #stream
            URL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID +"/stream?static=true&api_key=" + self.EmbyServer.Data['auth.token'] + "&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId("") + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&" + Filename

        if "3d" in MediaSource[8].lower():
            item = xbmcgui.ListItem(Details['title'], path=URL)
        else:
            item = xbmcgui.ListItem()
            item.setPath(self.URLQuery)

        item.setArt(Details['art'])
        del Details['art']

        if 'cast' in Details:
            item.setCast(Details['cast'])
            del Details['cast']

        if 'uniqueid' in Details:
            item.setUniqueIDs(Details['uniqueid'])
            del Details['uniqueid']

        item.setInfo('video', Details)
        item.setProperty('IsPlayable', 'true')

        if not VideoStream[10]: #Duration
            Duration = 0
        else:
            Duration = int(VideoStream[10]) / 10000000

        item.addStreamInfo('video', {'codec' : VideoStream[3], 'width' : VideoStream[14], 'height' : VideoStream[15], 'aspect' : VideoStream[20], 'duration' : Duration})
        item.addStreamInfo('audio', {'codec' : AudioStream[3], 'language' : AudioStream[4], 'channels' : AudioStream[12]})

        if Subtitle:
            item.addStreamInfo('subtitle', {'language' : Subtitle[4]})

        if "3d" in MediaSource[8].lower():
            Index = playlist.getposition()
            playlist.add(URL, item, Index)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":' + str(Index + 1) + '}}')
            self.Player.PlayerReloadIndex = str(Index)
            self.Player.PlayerLastItemID = str(self.EmbyID)
            URL = "RELOAD"
        else:
            self.Player.updateInfoTag(item)
            self.SubTitlesAdd(MediasourceID, emby_dbT)
            self.Player.PlayerReloadIndex = "-1"
            self.Player.PlayerLastItemID = "-1"

        return URL

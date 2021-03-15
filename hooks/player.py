# -*- coding: utf-8 -*-
import json
import threading
import logging
import uuid

import xbmc
import xbmcgui
import helper.utils
import helper.translate
import database.database
import database.emby_db

class ProgressUpdates(threading.Thread):
    def __init__(self, Player):
        self.Player = Player
        self.Exit = False
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True

    def run(self):
        while not self.Exit:
            self.Player.report_playback()

            if xbmc.Monitor().waitForAbort(4):
                break
#Basic Player class to track progress of Emby content.
class PlayerEvents(xbmc.Player):
    def __init__(self, monitor):
        self.Monitor = monitor
        self.Utils = self.Monitor.Utils
        self.Monitor.CurrentlyPlaying = {}
        self.LOG = logging.getLogger("EMBY.hooks.player.Player")
        xbmc.Player.__init__(self)

    #Call when playback start to setup play entry in player tracker.
    def set_item(self, PlayItem):
        self.stop_playback(True)
        PlayItem['Volume'], PlayItem['Muted'] = self.get_volume()
        self.Monitor.CurrentlyPlaying = PlayItem
        self.LOG.info("-->[ play/%s ] %s", PlayItem['Id'], PlayItem)
        data = {
            'ItemId': PlayItem['Id'],
            'MediaSourceId': PlayItem['MediaSourceId'],
            'PlaySessionId': PlayItem['PlaySessionId']
        }

        #Init session
        PlayItem['Server']['api'].session_playing(data)
        self.report_playback()

    def SETVolume(self, Volume, Mute):
        if not self.Monitor.CurrentlyPlaying:
            return

        self.Monitor.CurrentlyPlaying['Volume'] = Volume
        self.Monitor.CurrentlyPlaying['Muted'] = Mute
        self.report_playback()

    #Report playback progress to emby server.
    def report_playback(self):
        if self.Monitor.Trailer:
            return

        if not self.Monitor.CurrentlyPlaying:
            return

        try:
            current_time = int(self.getTime())
            TotalTime = int(self.getTotalTime())
        except:
            return #not playing any file

        self.Monitor.CurrentlyPlaying['CurrentPosition'] = current_time * 10000000

        if self.Monitor.CurrentlyPlaying['RunTime'] == -1:
            self.Monitor.CurrentlyPlaying['RunTime'] = TotalTime * 10000000

        data = {
            'ItemId': self.Monitor.CurrentlyPlaying['Id'],
            'MediaSourceId': self.Monitor.CurrentlyPlaying['MediaSourceId'],
            'PositionTicks': self.Monitor.CurrentlyPlaying['CurrentPosition'],
            'RunTimeTicks': self.Monitor.CurrentlyPlaying['RunTime'],
            'CanSeek': True,
            'QueueableMediaTypes': "Video,Audio",
            'VolumeLevel': self.Monitor.CurrentlyPlaying['Volume'],
            'IsPaused': self.Monitor.CurrentlyPlaying['Paused'],
            'IsMuted': self.Monitor.CurrentlyPlaying['Muted'],
            'PlaySessionId': self.Monitor.CurrentlyPlaying['PlaySessionId']
        }
        self.Monitor.CurrentlyPlaying['Server']['api'].session_progress(data)

    def onAVStarted(self):
        self.LOG.info("[ onAVStarted ]")

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

        if not self.Monitor.CurrentlyPlaying:
            return

        self.Monitor.CurrentlyPlaying['Paused'] = True
        self.report_playback()
        self.LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        self.LOG.info("[ onPlayBackResumed ]")

        if not self.Monitor.CurrentlyPlaying:
            return

        self.Monitor.CurrentlyPlaying['Paused'] = False
        self.report_playback()
        self.LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        self.LOG.info("[ onPlayBackStopped ]")

        if self.ReloadStream():#Media reload (3D Movie)
            return

        self.Monitor.PlayerLastItemID = "-1"
        self.Monitor.PlayerLastItem = ""
        self.Monitor.Trailer = False
        self.Utils.window('emby.sync.pause.bool', True)
        self.stop_playback()
        self.LOG.info("--<[ playback ]")

    def onPlayBackSeek(self, time, seekOffset):
        self.LOG.info("[ onPlayBackSeek ]")
        self.report_playback()

    def onPlayBackEnded(self):
        self.LOG.info("[ onPlayBackEnded ]")

        if self.Monitor.Trailer:
            return

        if self.ReloadStream():#Media reload (3D Movie)
            return

        self.Monitor.PlayerLastItemID = "-1"
        self.Monitor.PlayerLastItem = ""
        self.Utils.window('emby.sync.pause.bool', True)
        self.stop_playback()
        self.LOG.info("--<<[ playback ]")

    def get_volume(self):
        result = helper.utils.JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')
        return volume, muted

    def onPlayBackError(self):
        self.LOG.warning("Playback error occured")
        self.stop_playback()

    def get_playing_file(self):
        if self.isPlaying():
            return self.getPlayingFile()

        return None

    def ReloadStream(self):
        #Media has changed -> reload
        if self.Monitor.PlayerReloadIndex != "-1":
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            xbmc.Player().play(item=playlist, startpos=int(self.Monitor.PlayerReloadIndex))
            self.Monitor.PlayerReloadIndex = "-1"
            return True

        return False

    def stop_playback(self, Init=False):
        if self.Monitor.CurrentlyPlaying:
            self.LOG.debug("[ played info ] %s", self.Monitor.CurrentlyPlaying)

            data = {
                'ItemId': self.Monitor.CurrentlyPlaying['Id'],
                'MediaSourceId': self.Monitor.CurrentlyPlaying['MediaSourceId'],
                'PositionTicks': self.Monitor.CurrentlyPlaying['CurrentPosition'],
                'PlaySessionId': self.Monitor.CurrentlyPlaying['PlaySessionId']
            }

            self.Monitor.CurrentlyPlaying['Server']['api'].close_transcode(self.Monitor.CurrentlyPlaying['DeviceId'])
            self.Monitor.CurrentlyPlaying['Server']['api'].session_stop(data)
            self.Monitor.CurrentlyPlaying = {}

        if not Init:
            self.Monitor.SetSkipItemAfterStop()
            self.Utils.window('emby.sync.pause', clear=True)

#Call from WebSocket to manipulate playing URL
class WebserviceOnPlay(threading.Thread):
    def __init__(self, Monitor, server):
        self.Monitor = Monitor
        self.Utils = self.Monitor.Utils
        self.Player = self.Monitor.player
        self.server = server
        self.Intros = None
        self.IntrosIndex = 0
        self.Exit = False
        self.Trailers = False
        self.device_id = self.Monitor.device_id
        self.EmbyIDLast = -1
        self.EmbyID = -1
        self.URLQuery = ""
        self.Type = ""
        self.KodiID = -1
        self.Force = False
        self.Filename = ""
        self.Token = self.server['auth/token']
        self.ServerIP = self.server['auth/server-address']
        self.ServerAPI = self.server['api']
        self.MediaSources = []
        self.WebserviceEventOut = self.Monitor.WebserviceEventOut
        self.WebserviceEventIn = self.Monitor.WebserviceEventIn
        self.TranscodeReasons = ""
        self.VideoBitrate = self.Utils.get_VideoBitrate()
        self.AudioBitrate = self.Utils.get_AudioBitrate()
        self.TargetVideoBitrate = 0
        self.TargetAudioBitrate = 0
        Codec = ["h264", "hevc"]
        ID = self.Utils.settings('TranscodeFormatVideo')
        self.VideoCodec = "&VideoCodec=" + Codec[int(ID)]
        Codec = ["aac", "ac3"]
        ID = self.Utils.settings('TranscodeFormatAudio')
        self.AudioCodec = "&AudioCodec=" + Codec[int(ID)]
        self.TranscodeH265 = self.Utils.settings('transcode_h265.bool')
        self.TranscodeDivx = self.Utils.settings('transcodeDivx.bool')
        self.TranscodeXvid = self.Utils.settings('transcodeXvid.bool')
        self.TranscodeMpeg2 = self.Utils.settings('transcodeMpeg2.bool')
        self.EnableCinema = self.Utils.settings('enableCinema.bool')
        self.AskCinema = self.Utils.settings('askCinema.bool')
        self.LOG = logging.getLogger("EMBY.hooks.player.WebserviceOnPlay")
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True
        self.WebserviceEventOut.put("quit")

    def run(self):
        while not self.Exit:
            IncommingData = self.WebserviceEventOut.get()

            if IncommingData == "quit":
                break

            self.LOG.debug("[ query IncommingData ] %s", IncommingData)
            self.EmbyID, MediasourceID, self.Type, BitrateFromURL, self.Filename = self.GetParametersFromURLQuery(IncommingData)

            if 'audio' in IncommingData:
                self.WebserviceEventIn.put(self.ServerIP + "/emby/audio/" + self.EmbyID + "/stream?static=true&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.device_id + "&api_key=" + self.Token + "&" + self.Filename)
                continue

            if 'livetv' in IncommingData:
                self.WebserviceEventIn.put(self.ServerIP + "/emby/videos/" + self.EmbyID + "/stream.ts?PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.device_id + "&api_key=" + self.Token + "&" + self.Filename)
                continue

            if 'main.m3u8' in IncommingData: #Dynamic Transcode query
                IncommingData = IncommingData.replace("/movie/", "/")
                IncommingData = IncommingData.replace("/musicvideo/", "/")
                IncommingData = IncommingData.replace("/tvshow/", "/")
                IncommingData = IncommingData.replace("/video/", "/")
                IncommingData = IncommingData.replace("/trailer/", "/")
                self.WebserviceEventIn.put(self.ServerIP + "/emby/videos/" + self.EmbyIDLast + IncommingData)
                continue

            self.URLQuery = "http://127.0.0.1:57578" + IncommingData

            if self.Type == "movies":
                self.Type = "movie"
            elif self.Type == "tvshows":
                self.Type = "episode"
            elif self.Type == "musicvideos":
                self.Type = "musicvideo"

            self.Utils.window('emby.sync.pause.bool', True)

            #Reload Playlistitem after playlist injection
            if self.Monitor.PlayerReloadIndex != "-1":
                URL = "RELOAD"
                self.WebserviceEventIn.put(URL)
                continue

            #Todo: SKIP TRAILERS IF MULTIPART!
            #Trailers
            if self.EnableCinema and self.Monitor.PlayerLastItemID != self.EmbyID:
                PlayTrailer = True

                if self.AskCinema:
                    if not self.Monitor.Trailer:
                        self.Trailers = False

                    if not self.Trailers and not self.Monitor.Trailer:
                        self.Trailers = True
                        PlayTrailer = self.Utils.dialog("yesno", heading="{emby}", line1=helper.translate._(33016))

                if PlayTrailer:
                    if self.Monitor.PlayerLastItem != IncommingData or not self.Monitor.Trailer:
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
                        self.Monitor.PlayerLastItem = IncommingData
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Intros = self.ServerAPI.get_intros(self.EmbyID)
                        #self.IntrosLocal = self.ServerAPI.get_local_trailers(self.EmbyID)
                        self.Monitor.Trailer = True

                    try: #Play next trailer
                        self.WebserviceEventIn.put(self.Intros['Items'][self.IntrosIndex]['Path'])
                        self.IntrosIndex += 1
                        continue
                    except: #No more trailers
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')
                        self.Force = True
                        self.Monitor.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Monitor.Trailer = False
                else:
                    xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')

            #Select mediasources, Audiostreams, Subtitles
            if self.Monitor.PlayerLastItemID != self.EmbyID or self.Force:
                self.Force = False
                self.Monitor.PlayerLastItemID = str(self.EmbyID)

                with database.database.Database('emby') as embydb:
                    emby_dbT = database.emby_db.EmbyDatabase(embydb.cursor)
                    EmbyDBItem = emby_dbT.get_kodiid(self.EmbyID)

                    if EmbyDBItem: #Item not synced to Kodi DB
                        PresentationKey = EmbyDBItem[1].split("-")
                        self.Monitor.AddSkipItem(PresentationKey[0])
                        self.KodiID = str(EmbyDBItem[0])
                    else:
                        self.Monitor.PlayerReloadIndex = "-1"
                        self.Monitor.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Monitor.Trailer = False
                        self.SubTitlesAdd(MediasourceID, emby_dbT)
                        Transcoding = self.IsTranscoding(BitrateFromURL, None)

                        if Transcoding:
                            URL = self.GETTranscodeURL(MediasourceID, self.Filename)
                        else:
                            URL = self.ServerIP + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.device_id + "&api_key=" + self.Token + "&" + self.Filename

                        self.WebserviceEventIn.put(URL)
                        continue

                    self.MediaSources = emby_dbT.get_mediasource(self.EmbyID)

                    if len(self.MediaSources) == 1:
                        self.Monitor.PlayerLastItemID = "-1"
                        self.WebserviceEventIn.put(self.LoadData(MediasourceID, emby_dbT, 0))
                        continue

                    #Multiversion
                    Selection = []

                    for Data in self.MediaSources:
                        Selection.append(Data[8] + " - " + self.SizeToText(float(Data[7])))

                    MediaIndex = self.Utils.dialog("select", heading="Select Media Source:", list=Selection)

                    if MediaIndex <= 0:
                        MediaIndex = 0
                        self.Monitor.PlayerLastItemID = "-1"

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
                    SubTitleURL = self.ServerIP + "/emby/videos/" + self.EmbyID + "/" + MediasourceID + "/Subtitles/ " + str(Data[18]) + "/stream.srt?api_key=" + self.Token
                    Filename = self.Utils.PathToFilenameReplaceSpecialCharecters(str(CounterSubTitle) + "." + Data[4] + ".srt")
                    Path = self.Utils.download_external_subs(SubTitleURL, Filename)
                    xbmc.Player().setSubtitles(Path)
                    xbmc.Player().showSubtitles(False)

    def LoadData(self, MediasourceID, emby_dbT, MediaIndex):
        VideoStreams = emby_dbT.get_videostreams(self.EmbyID, MediaIndex)
        AudioStreams = emby_dbT.get_AudioStreams(self.EmbyID, MediaIndex)

        if not VideoStreams:
            self.LOG.warning("[ VideoStreams not found ] %s", self.EmbyID)
            return self.ServerIP + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.device_id + "&api_key=" + self.Token + "&" + self.Filename

        Bitrate = VideoStreams[0][9]
        Transcoding = self.IsTranscoding(Bitrate, VideoStreams[0][3]) #add codec from videostreams, Bitrate (from file)

        if Transcoding:
            SubtitleIndex = -1
            AudioIndex = -1
            Subtitles = []
            Subtitles = emby_dbT.get_Subtitles(self.EmbyID, MediaIndex)

            if len(AudioStreams) >= 2:
                Selection = []

                for Data in AudioStreams:
                    Selection.append(Data[7])

                AudioIndex = self.Utils.dialog("select", heading="Select Audio Stream:", list=Selection)

            if len(Subtitles) >= 1:
                Selection = []

                for Data in Subtitles:
                    Selection.append(Data[7])

                SubtitleIndex = self.Utils.dialog("select", heading="Select Subtitle:", list=Selection)

            if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0: #No change -> resume
                return self.GETTranscodeURL(MediasourceID, self.Filename)

            if AudioIndex <= 0:
                AudioIndex = 0

            if SubtitleIndex < 0:
                Subtitle = None
            else:
                Subtitle = Subtitles[SubtitleIndex]

            return self.UpdateItem(MediasourceID, Transcoding, self.MediaSources[MediaIndex], VideoStreams[0], AudioStreams[AudioIndex], emby_dbT, Subtitle)

        if MediaIndex == 0:
            self.SubTitlesAdd(MediasourceID, emby_dbT)
            return self.ServerIP + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.device_id + "&api_key=" + self.Token + "&" + self.Filename

        return self.UpdateItem(MediasourceID, Transcoding, self.MediaSources[MediaIndex], VideoStreams[0], AudioStreams[0], emby_dbT)

    def GETTranscodeURL(self, MediasourceID, Filename, Audio="", Subtitle=""):
        TranscodingVideo = ""
        TranscodingAudio = ""

        if Subtitle:
            Subtitle = "&SubtitleStreamIndex=" + Subtitle

        if Audio:
            Audio = "&AudioStreamIndex=" + Audio

        if self.TargetVideoBitrate:
            TranscodingVideo = "&VideoBitrate=" + str(self.TargetVideoBitrate)

        if self.TargetAudioBitrate:
            TranscodingAudio = "&AudioBitrate=" + str(self.TargetAudioBitrate)

        if Filename:
            Filename = "&" + Filename

        return self.ServerIP + "/emby/videos/" + self.EmbyID + "/master.m3u8?api_key=" + self.Token + "&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId(MediasourceID) + "&DeviceId=" + self.device_id + self.VideoCodec + self.AudioCodec + TranscodingVideo + TranscodingAudio + Audio + Subtitle + "&TranscodeReasons=" + self.TranscodeReasons + Filename

    def SizeToText(self, size, precision=2):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        suffixIndex = 0

        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1
            size = size / 1024.0

        return "%.*f%s" % (precision, size, suffixes[suffixIndex])

    def GETPlaySessionId(self, MediasourceID=""):
        self.Monitor.PlaySessionId = str(uuid.uuid4()).replace("-", "")
        self.Monitor.MediasourceID = MediasourceID
        return self.Monitor.PlaySessionId

    def IsTranscoding(self, Bitrate, Codec):
        if self.TranscodeH265:
            if Codec in ("h265", "hevc"):
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.TranscodeDivx:
            if Codec == "msmpeg4v3":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.TranscodeXvid:
            if Codec == "mpeg4":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.TranscodeMpeg2:
            if Codec == "mpeg2video":
                self.IsTranscodingByCodec(Bitrate)
                return True

        self.TargetVideoBitrate = self.VideoBitrate
        self.TargetAudioBitrate = self.AudioBitrate
        self.TranscodeReasons = "ContainerBitrateExceedsLimit"
        return Bitrate >= self.TargetVideoBitrate

    def IsTranscodingByCodec(self, Bitrate):
        if Bitrate >= self.VideoBitrate:
            self.TranscodeReasons = "ContainerBitrateExceedsLimit"
            self.TargetVideoBitrate = self.VideoBitrate
            self.TargetAudioBitrate = self.AudioBitrate
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

            self.Utils.window('emby.sync.pause.bool', True)
            self.Monitor.AddSkipItem(Data[0])
            return Data[0], Data[1], Type, BitrateFromURL, Filename

        return None, None, None, None, None

    def UpdateItem(self, MediasourceID, Transcoding, MediaSource, VideoStream, AudioStream, emby_dbT, Subtitle=None):
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
        Index = playlist.getposition()
        Filename = self.Utils.PathToFilenameReplaceSpecialCharecters(MediaSource[4])

        if Subtitle:
            SubtitleStream = str(int(Subtitle[2]) + 2)
        else:
            SubtitleStream = ""

        if Transcoding:
            URL = self.GETTranscodeURL(MediasourceID, Filename, str(int(AudioStream[2]) + 1), SubtitleStream)
        else: #stream
            URL = self.ServerIP + "/emby/videos/" + self.EmbyID +"/stream?static=true&api_key=" + self.Token + "&MediaSourceId=" + MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.device_id + "&" + Filename

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
            playlist.add(URL, item, Index)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":' + str(Index + 1) + '}}')
            self.Monitor.PlayerReloadIndex = str(Index)
            self.Monitor.PlayerLastItemID = str(self.EmbyID)
            URL = "RELOAD"
        else:
            xbmc.Player().updateInfoTag(item)
            self.SubTitlesAdd(MediasourceID, emby_dbT)
            self.Monitor.PlayerReloadIndex = "-1"
            self.Monitor.PlayerLastItemID = "-1"

        return URL

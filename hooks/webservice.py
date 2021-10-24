# -*- coding: utf-8 -*-
import threading
import socket
import xbmc
import database.db_open
import helper.loghandler
import helper.utils as Utils
import helper.xmls as xmls

LOG = helper.loghandler.LOG('EMBY.hooks.webservice.WebService')


# Run a webservice to capture playback and incomming events.
class WebService(threading.Thread):
    def __init__(self):
        self.Stop = False
        self.Player = None
        self.EmbyServers = {}
        self.Intros = []
        self.embydb = None
        self.IntrosIndex = 0
        self.SkipItemVideo = ""
        self.blankfileData = Utils.readFileBinary("special://home/addons/plugin.video.emby-next-gen/resources/blank.m4v")
        self.blankfileSize = len(self.blankfileData)
        self.TrailerInitialItem = ""
        self.socket = None
        self.QueryDataPrevious = {}
        self.DefaultVideoSettings = {}
        threading.Thread.__init__(self)

    def Update_EmbyServers(self, EmbyServers, Player):
        self.EmbyServers = EmbyServers
        self.Player = Player
        self.DefaultVideoSettings = xmls.load_defaultvideosettings()

    def run(self):
        LOG.info("--->[ webservice/57578 ]")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.bind(('127.0.0.1', 57578))
        self.socket.settimeout(None)
        self.Listen()
        LOG.info("---<[ webservice/57578 ]")

    def close(self):
        self.Stop = True

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", 57578))
            s.send('QUIT QUIT'.encode())
            s.shutdown(socket.SHUT_RDWR)
        except:
            pass

    def Listen(self):
        self.socket.listen(50)

        while not self.Stop:
            client, _ = self.socket.accept()
            client.settimeout(None)
            data = client.recv(1024).decode()
            threading.Thread(target=self.Query, args=(client, data)).start()

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

    def Query(self, client, data):


        if not self.EmbyServers:
            SendResponseOK(client)
            client.close()
            return

        IncommingData = data.split(' ')

        if 'extrafanart' in IncommingData[1] or 'extrathumbs' in IncommingData[1] or 'Extras/' in IncommingData[1] or IncommingData[1].endswith('/'):
            SendResponseOK(client)
        elif IncommingData[0] == "GET":
            self.getQuery(client, IncommingData[1])
        elif IncommingData[0] == "HEAD":
            if 'embyimage' in IncommingData[1]:
                self.getQuery(client, IncommingData[1])
            else:
                SendResponseOK(client)

        client.close()

    def SendBlankFile(self, client):
        Response = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: %s\r\nContent-type: video/mp4\r\n\r\n' % self.blankfileSize
        Response = Response.encode()
        client.send(Response + self.blankfileData)

    def LoadISO(self, QueryData, MediaIndex):
        self.Player.MultiselectionDone = True
        self.embydb = database.db_open.DBOpen(Utils.DatabaseFiles, QueryData['ServerId'])
        QueryData['MediaSources'] = self.embydb.get_mediasource(QueryData['EmbyID'])
        database.db_open.DBClose(QueryData['ServerId'], False)
        Details = Utils.load_VideoitemFromKodiDB(QueryData['MediaType'], QueryData['KodiId'])
        li = Utils.CreateListitem(QueryData['MediaType'], Details)
        Path = QueryData['MediaSources'][MediaIndex][3]
        self.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediaType'], QueryData['MediaSources'][MediaIndex][2])

        if Path.startswith('\\\\'):
            Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

        li.setPath(Path)
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        PlaylistPosition = playlist.getposition()
        playlist.add(Path, li, PlaylistPosition + 1)
        self.Player.PlayerSkipItem = str(PlaylistPosition)
        self.SkipItemVideo = QueryData['Payload']
        self.QueryDataPrevious = QueryData.copy()

    def SendResponse(self, client, Data, SkipPlayerUpdate, QueryData, Trailer=False):
        if not SkipPlayerUpdate:  # SkipPlayerUpdate = Audio, VideoTheme, Image
            if Trailer:
                self.Player.PlayerSkipItem = "TRAILER"
            else:
                self.Player.PlayerSkipItem = "-1"

        if Data == "RELOAD":
            self.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediaType'], QueryData['MediasourceID'])
            self.SendBlankFile(client)
            return

        Response = 'HTTP/1.1 302 Found\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % Data
        Response = Response.encode()
        client.send(Response)

        if not SkipPlayerUpdate and not Trailer:
            self.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediaType'], QueryData['MediasourceID'])

    def getQuery(self, client, Payload):
        if 'main.m3u8' in Payload:  # Dynamic Transcode query
            self.SendResponse(client, "%s/emby/videos/%s%s" % (self.EmbyServers[self.QueryDataPrevious['ServerId']].server, self.QueryDataPrevious['EmbyID'], Payload), False, self.QueryDataPrevious)
            return

        if self.SkipItemVideo == Payload:  # 3D, iso (playlist modification)
            self.SendResponse(client, 'RELOAD', False, self.QueryDataPrevious)
            self.SkipItemVideo = ""
            return

        if "emby" not in Payload:  # nfo query for folder, not for item -> return
            SendResponseOK(client)
            return

        QueryData = GetParametersFromURLQuery(Payload)

        if Payload.endswith('.nfo'):  # metadata scraper queries item info. Due to lag of nfo file, the item will be removed by scraper. Workaround: -> trigger item resync from Emby server
            LOG.info("[ nfo query -> refresh item %s ]" % Payload)
            SendResponseOK(client)
            self.EmbyServers[QueryData['ServerId']].library.updated([QueryData['EmbyID']])
            return

        if QueryData['ServerId'] not in self.EmbyServers:
            SendResponseOK(client)
            return

        if QueryData['Type'] == 'embyimage':
            if Utils.enableCoverArt:
                ExtendedParameter = "&EnableImageEnhancers=True"
            else:
                ExtendedParameter = "&EnableImageEnhancers=False"

            if Utils.compressArt:
                ExtendedParameter += "&Quality=70"

            Query = "%s/emby/Items/%s/Images/%s/%s?%s&api_key=%s%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['ImageTag'], self.EmbyServers[QueryData['ServerId']].Token, ExtendedParameter)
            self.SendResponse(client, Query, True, QueryData)
            return

        Utils.SyncPause = True

        if self.Player.Transcoding:
            self.EmbyServers[QueryData['ServerId']].API.close_transcode()

        self.Player.Transcoding = False
        self.Player.EmbyServer = self.EmbyServers[QueryData['ServerId']]

        if QueryData['Type'] == 'embythemeaudio':
            self.SendResponse(client, "%s/emby/audio/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" %(self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename']), True, QueryData)
            return

        if QueryData['Type'] in ('embythemevideo', 'embytrailerlocal'):
            self.SendResponse(client, "%s/emby/videos/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename']), True, QueryData)
            return

        if QueryData['Type'] == 'embyaudio':
            self.SendResponse(client, "%s/emby/audio/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename']), False, QueryData)
            return

        if QueryData['Type'] == 'embylivetv':
            self.Player.Transcoding = True
            self.SendResponse(client, "%s/emby/videos/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token), False, QueryData)
            return

        # Cinnemamode
        if Utils.enableCinema and (Utils.localTrailers or Utils.Trailers):
            if not self.TrailerInitialItem == QueryData['Payload']:  # Trailer init (load)
                PlayTrailer = True

                if Utils.askCinema:
                    PlayTrailer = Utils.dialog("yesno", heading=Utils.addon_name, line1=Utils.Translate(33016))

                if PlayTrailer:
                    URL = self.play_Trailer(True, QueryData)

                    if URL:
                        self.SendResponse(client, URL, False, QueryData, True)
                        return
            else:  # play next trailer
                if self.TrailerInitialItem == QueryData['Payload']:
                    URL = self.play_Trailer(False, QueryData)

                    if URL:
                        self.SendResponse(client, URL, False, QueryData, True)
                        return

        # Select mediasources, Audiostreams, Subtitles
        self.embydb = database.db_open.DBOpen(Utils.DatabaseFiles, QueryData['ServerId'])

        if QueryData['KodiId']:  # Item synced to Kodi DB
            self.Player.ItemSkipUpdate.append(QueryData['EmbyID'])

            if QueryData['MediasourcesCount'] == 1:
                if QueryData['Type'] == 'embyiso':
                    self.LoadISO(QueryData, 0)
                    self.SendResponse(client, 'RELOAD', False, QueryData)
                else:
                    self.SendResponse(client, self.LoadData(0, QueryData), False, QueryData)

                database.db_open.DBClose(QueryData['ServerId'], False)
                return

            # Multiversion
            Selection = []
            QueryData['MediaSources'] = self.embydb.get_mediasource(QueryData['EmbyID'])

            for Data in QueryData['MediaSources']:
                Selection.append("%s - %s" % (Data[4], Utils.SizeToText(float(Data[5]))))

            MediaIndex = Utils.dialog("select", heading="Select Media Source:", list=Selection)

            if MediaIndex <= 0:
                MediaIndex = 0

            # check if multiselection must be forced as native
            if QueryData['MediaSources'][MediaIndex][3].lower().endswith(".iso"):
                self.LoadISO(QueryData, MediaIndex)
                self.SendResponse(client, 'RELOAD', False, QueryData)
                database.db_open.DBClose(QueryData['ServerId'], False)
                return

            QueryData['MediasourceID'] = QueryData['MediaSources'][MediaIndex][2]
            self.SendResponse(client, self.LoadData(MediaIndex, QueryData), False, QueryData)
            database.db_open.DBClose(QueryData['ServerId'], False)
            return

        self.IntrosIndex = 0
        self.SubTitlesAdd(0, QueryData)
        self.Player.Transcoding = IsTranscoding(QueryData['BitrateFromURL'], None, QueryData)

        if self.Player.Transcoding:
            URL = self.GETTranscodeURL(QueryData['Filename'], False, False, QueryData)
        else:
            URL = "%s/emby/videos/%s/stream?static=true&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])

        self.SendResponse(client, URL, False, QueryData)
        database.db_open.DBClose(QueryData['ServerId'], False)

    # Load SRT subtitles
    def SubTitlesAdd(self, MediaIndex, QueryData):
        Subtitles = self.embydb.get_Subtitles(QueryData['EmbyID'], MediaIndex)

        if not Subtitles:
            return

        CounterSubTitle = 0
        DefaultSubtitlePath = ""
        EnableSubtitle = False
        SRTFound = False

        for Data in Subtitles:
            CounterSubTitle += 1

            if Data[3] == "srt":
                SRTFound = True
                SubTitleURL = "%s/emby/videos/%s/%s/Subtitles/%s/stream.srt" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], Data[2])
                request = {'type': "GET", 'url': SubTitleURL, 'params': {}}

                # Get Subtitle Settings
                videodb = database.db_open.DBOpen(Utils.DatabaseFiles, "video")
                videodb.cursor.execute("SELECT idFile, Deinterlace, ViewMode, ZoomAmount, PixelRatio, VerticalShift, AudioStream, SubtitleStream, SubtitleDelay, SubtitlesOn, Brightness, Contrast, Gamma, VolumeAmplification, AudioDelay, ResumeTime, Sharpness, NoiseReduction, NonLinStretch, PostProcess, ScalingMethod, StereoMode, StereoInvert, VideoStream, TonemapMethod, TonemapParam, Orientation, CenterMixLevel FROM settings Where idFile = ?", (QueryData['KodiFileId'],))
                FileSettings = videodb.cursor.fetchone()
                database.db_open.DBClose("video", False)

                if FileSettings:
                    EnableSubtitle = bool(FileSettings[9])
                else:
                    if self.DefaultVideoSettings:
                        EnableSubtitle = self.DefaultVideoSettings['ShowSubtitles']
                    else:
                        EnableSubtitle = False

                if Data[4]:
                    SubtileLanguage = Data[4]
                else:
                    SubtileLanguage = "unknown"

                Filename = Utils.PathToFilenameReplaceSpecialCharecters("%s.%s.srt" % (CounterSubTitle, SubtileLanguage))
                Path = Utils.download_file_from_Embyserver(request, Filename, self.EmbyServers[QueryData['ServerId']])

                if Path:
                    if self.DefaultVideoSettings["SubtitlesLanguage"].lower() in Data[5].lower():
                        DefaultSubtitlePath = Path

                        if self.DefaultVideoSettings["SubtitlesLanguage"].lower() == "forced_only" and "forced" in Data[5].lower():
                            DefaultSubtitlePath = Path
                        else:
                            self.Player.setSubtitles(Path)
                    else:
                        self.Player.setSubtitles(Path)

        if SRTFound:
            if DefaultSubtitlePath:
                self.Player.setSubtitles(DefaultSubtitlePath)

            self.Player.showSubtitles(EnableSubtitle)

    def LoadData(self, MediaIndex, QueryData):
        if MediaIndex == 0:
            self.Player.Transcoding = IsTranscoding(QueryData['BitrateFromURL'], QueryData['CodecVideo'], QueryData)  # add codec from videostreams, Bitrate (from file)

            if not self.Player.Transcoding:
                if QueryData['ExternalSubtitle'] == "1":
                    self.SubTitlesAdd(0, QueryData)

                return "%s/emby/videos/%s/stream?static=true&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])
        else:
            VideoStreams = self.embydb.get_videostreams(QueryData['EmbyID'], MediaIndex)
            QueryData['KodiId'] = str(self.embydb.get_kodiid(QueryData['EmbyID'])[0])
            self.Player.Transcoding = IsTranscoding(VideoStreams[0][4], VideoStreams[0][3], QueryData)

        if self.Player.Transcoding:
            AudioStreams = self.embydb.get_AudioStreams(QueryData['EmbyID'], MediaIndex)
            Subtitles = self.embydb.get_Subtitles(QueryData['EmbyID'], MediaIndex)
            SubtitleIndex = -1
            AudioIndex = -1

            if len(AudioStreams) >= 2:
                Selection = []

                for Data in AudioStreams:
                    Selection.append(Data[3])

                AudioIndex = Utils.dialog("select", heading="Select Audio Stream:", list=Selection)

            if len(Subtitles) >= 1:
                Selection = []

                for Data in Subtitles:
                    Selection.append(Data[5])

                SubtitleIndex = Utils.dialog("select", heading="Select Subtitle:", list=Selection)

            if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0:  # No change, just transcoding
                return self.GETTranscodeURL(QueryData['Filename'], False, False, QueryData)

            if not QueryData['MediaSources']:
                QueryData['MediaSources'] = self.embydb.get_mediasource(QueryData['EmbyID'])

            if AudioIndex < 0:
                AudioIndex = 0

            if SubtitleIndex < 0:
                Subtitle = None
            else:
                Subtitle = Subtitles[SubtitleIndex]

            return self.UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[AudioIndex], Subtitle, QueryData)

        AudioStreams = self.embydb.get_AudioStreams(QueryData['EmbyID'], MediaIndex)
        return self.UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[0], False, QueryData)

    def UpdateItem(self, MediaSource, AudioStream, Subtitle, QueryData):
        Details = Utils.load_VideoitemFromKodiDB(QueryData['MediaType'], QueryData['KodiId'])
        Filename = Utils.PathToFilenameReplaceSpecialCharecters(MediaSource[3])

        if self.Player.Transcoding:
            if Subtitle:
                SubtitleStream = str(Subtitle[2])
            else:
                SubtitleStream = ""

            URL = self.GETTranscodeURL(Filename, str(AudioStream[2]), SubtitleStream, QueryData)
        else:  # stream
            URL = "%s/emby/videos/%s/stream?static=true&api_key=%s&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].Token, QueryData['MediasourceID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, Filename)

        li = Utils.CreateListitem(QueryData['MediaType'], Details)

        if "3d" in MediaSource[4].lower():
            li.setPath(URL)
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            PlaylistPosition = playlist.getposition()
            playlist.add(URL, li, PlaylistPosition + 1)
            self.Player.PlayerSkipItem = str(PlaylistPosition)
            self.SkipItemVideo = QueryData['Payload']
            URL = "RELOAD"
            self.QueryDataPrevious = QueryData.copy()
        else:
            li.setPath("http://127.0.0.1:57578" + QueryData['Payload'])
            self.Player.updateInfoTag(li)
            self.SubTitlesAdd(0, QueryData)

        return URL

    def GETTranscodeURL(self, Filename, Audio, Subtitle, QueryData):
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

        if QueryData['TargetVideoBitrate']:
            TranscodingVideo = "&VideoBitrate=" + str(QueryData['TargetVideoBitrate'])

        if QueryData['TargetAudioBitrate']:
            TranscodingAudio = "&AudioBitrate=" + str(QueryData['TargetAudioBitrate'])

        if Filename:
            Filename = "&stream-" + Filename

        self.QueryDataPrevious = QueryData.copy()
        return "%s/emby/videos/%s/master.m3u8?api_key=%s&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&VideoCodec=%s&AudioCodec=%s%s%s%s%s&TranscodeReasons=%s%s" % (self.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], self.EmbyServers[QueryData['ServerId']].Token, QueryData['MediasourceID'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, Utils.TranscodeFormatVideo, Utils.TranscodeFormatAudio, TranscodingVideo, TranscodingAudio, Audio, Subtitle, QueryData['TranscodeReasons'], Filename)

    def play_Trailer(self, Init, QueryData):
        if Init:
            self.TrailerInitialItem = QueryData['Payload']
            self.Intros = []

            if Utils.localTrailers:
                IntrosLocal = self.EmbyServers[QueryData['ServerId']].API.get_local_trailers(QueryData['EmbyID'])

                for IntroLocal in IntrosLocal:
                    Filename = Utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
                    self.Intros.append("%s/emby/videos/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (self.EmbyServers[QueryData['ServerId']].server, IntroLocal['Id'], self.EmbyServers[QueryData['ServerId']].PlaySessionId, Utils.device_id, self.EmbyServers[QueryData['ServerId']].Token, Filename))

            if Utils.Trailers:
                Intros = self.EmbyServers[QueryData['ServerId']].API.get_intros(QueryData['EmbyID'])

                if 'Items' in Intros:
                    for Intro in Intros['Items']:
                        self.Intros.append(Intro['Path'])

            self.IntrosIndex = 0

        if not self.Intros:
            return None

        if len(self.Intros) > self.IntrosIndex:
            xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
            URL = self.Intros[self.IntrosIndex]
            self.IntrosIndex += 1
            return URL

        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')
        self.TrailerInitialItem = ""
        return None

def IsTranscoding(Bitrate, Codec, QueryData):
    if Utils.transcodeH265:
        if Codec in ("h265", "hevc"):
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif Utils.transcodeDivx:
        if Codec == "msmpeg4v3":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif Utils.transcodeXvid:
        if Codec == "mpeg4":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif Utils.transcodeMpeg2:
        if Codec == "mpeg2video":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True

    QueryData['TargetVideoBitrate'] = Utils.VideoBitrate
    QueryData['TargetAudioBitrate'] = Utils.AudioBitrate
    QueryData['TranscodeReasons'] = "ContainerBitrateExceedsLimit"
    return Bitrate >= QueryData['TargetVideoBitrate']

def IsTranscodingByCodec(Bitrate, QueryData):
    if Bitrate >= Utils.VideoBitrate:
        QueryData['TranscodeReasons'] = "ContainerBitrateExceedsLimit"
        QueryData['TargetVideoBitrate'] = Utils.VideoBitrate
        QueryData['TargetAudioBitrate'] = Utils.AudioBitrate
    else:
        QueryData['TranscodeReasons'] = "VideoCodecNotSupported"
        QueryData['TargetVideoBitrate'] = 0
        QueryData['TargetAudioBitrate'] = 0

def SendResponseOK(client):
    header = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'
    response = header.encode()
    client.send(response)

def GetParametersFromURLQuery(Payload):
    Temp = Payload[Payload.rfind("/") + 1:]
    Data = Temp.split("-")
    QueryData = {'MediaSources': [], 'TargetVideoBitrate': 0, 'TargetAudioBitrate': 0, 'Payload': Payload, 'ServerId': Data[1], 'EmbyID': Data[2]}

    if Data[0] == "embyimage":  # Image
        QueryData['ImageIndex'] = Data[3]
        QueryData['ImageType'] = Data[4]
        QueryData['ImageTag'] = Data[5]
        QueryData['Type'] = "embyimage"
    elif Data[0] in ("embyvideo", "embyiso"):  # Video
        QueryData['MediasourceID'] = Data[3]
#        QueryData['PresentationKey'] = Data[4]
#        QueryData['EmbyParentId'] = Data[5]
        QueryData['KodiId'] = Data[6]
        QueryData['KodiFileId'] = Data[7]
        QueryData['MediaType'] = Data[8]
        QueryData['BitrateFromURL'] = int(Data[9])
        QueryData['ExternalSubtitle'] = Data[10]
        QueryData['MediasourcesCount'] = int(Data[11])
#        QueryData['VideostreamCount'] = int(Data[12])
#        QueryData['AudiostreamCount'] = int(Data[13])
        QueryData['CodecVideo'] = Data[14]
        QueryData['Filename'] = Data[15]
        QueryData['Type'] = Data[0]
    elif Data[0] == "embyaudio":  # Audio
#        QueryData['PresentationKey'] = Data[3]
        QueryData['MediaType'] = Data[4]
        QueryData['Filename'] = Data[5]
        QueryData['MediasourceID'] = ""
        QueryData['Type'] = "embyaudio"
    elif Data[0] == "embylivetv":  # Dynamic item
        QueryData['Filename'] = Data[3]
        QueryData['MediaType'] = "live"
        QueryData['MediasourceID'] = None
        QueryData['Type'] = "embylivetv"
    elif Data[0] == "embyaudiodynamic":  # Dynamic item
        QueryData['MediaType'] = Data[3]
        QueryData['Filename'] = Data[4]
        QueryData['KodiId'] = None
        QueryData['Type'] = "embyaudio"
        QueryData['MediasourceID'] = None
    elif Data[0] == "embyvideodynamic":  # Dynamic item
        QueryData['MediaType'] = Data[3]
        QueryData['MediasourceID'] = Data[4]
        QueryData['BitrateFromURL'] = int(Data[5])
        QueryData['CodecVideo'] = Data[6]
        QueryData['Filename'] = Data[7]
        QueryData['KodiId'] = None
        QueryData['Type'] = "embyvideo"
    else:  # embythemeaudio, embythemevideo
        QueryData['MediasourceID'] = Data[3]
        QueryData['MediaType'] = Data[4]
        QueryData['Filename'] = Data[5]
        QueryData['KodiId'] = None
        QueryData['Type'] = Data[0]

    return QueryData

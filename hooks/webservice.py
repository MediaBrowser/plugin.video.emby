import uuid
from urllib.parse import parse_qsl
import socket
from _thread import start_new_thread
import xbmc
from database import dbio
from emby import listitem
from helper import utils, xmls, loghandler, context, playerops, pluginmenu
from . import player

blankfileData = utils.readFileBinary("special://home/addons/plugin.video.emby-next-gen/resources/blank.wav")
MediaTypeMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "A": "specialaudio", "V": "specialvideo", "i": "movie", "T": "video"} # T=trailer, i=iso
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
sendblankfile = ('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: %s\r\nContent-type: audio/wav\r\n\r\n' % len(blankfileData)).encode() + blankfileData
DefaultVideoSettings = xmls.load_defaultvideosettings()
LOG = loghandler.LOG('EMBY.hooks.webservice')
Intros = []
SkipItemVideo = ""
TrailerInitPayload = ""
PlaySessionId = ""
QueryDataPrevious = {}
Cancel = False
Running = False
embydb = {}
playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)


def start():
    close()
    start_new_thread(Listen, ())

def close():
    if Running:
        try:
            Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            Socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            Socket.connect(("127.0.0.1", 57342))
            Socket.send('QUIT'.encode())
            Socket.shutdown(socket.SHUT_RDWR)
        except:
            pass

        globals()["Running"] = False

def Listen():
    LOG.info("-->[ webservice/57342 ]")
    Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    Socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    Socket.bind(('127.0.0.1', 57342))
    Socket.settimeout(None)
    Socket.listen()
    Init = False
    globals()["Running"] = True

    while True:
        if not Init:
            Init = True

            if utils.refreshskin:
                LOG.info("Reload skin")
                xbmc.executebuiltin('ReloadSkin()')

        client, _ = Socket.accept()
        client.settimeout(None)
        data = client.recv(1024).decode()

        if data == "QUIT":
            LOG.info("webservice: quit")
            break

        start_new_thread(worker_Query, (client, data))

    try:
        Socket.shutdown(socket.SHUT_RDWR)
    except:
        pass

    LOG.info("--<[ webservice/57342 ]")
    globals()["Running"] = False

def worker_Query(client, data):  # thread by caller
    DelayQuery = 0

    # Waiting for Emby server connection
    while not utils.EmbyServers:
        LOG.error("No Emby servers found, delay query")

        if utils.waitForAbort(1) or DelayQuery >= 15:
            LOG.error("Terminate query")
            client.send(sendOK)
            close_connection(client)
            return

        DelayQuery += 1

    IncomingData = data.split(' ')

    # events by event.py
    if IncomingData[0] == "EVENT":
        args = IncomingData[1].split(";")

        if args[1] == "contextmenu":
            client.send(sendOK)
            close_connection(client)
            context.select_menu()
            return

        # no delay
        Handle = args[1]
        params = dict(parse_qsl(args[2][1:]))
        mode = params.get('mode')
        ServerId = params.get('server')

        if mode == 'settings':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
            return

        if mode == 'managelibsselection':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.select_managelibs()
            return

        if mode == 'texturecache':  # Simple commands
            client.send(sendOK)
            close_connection(client)

            if not utils.artworkcacheenable:
                utils.dialog("notification", heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
            else:
                pluginmenu.cache_textures()

            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.databasereset()
            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.databasereset()
            return

        if mode == 'nodesreset':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.nodesreset()
            return

        if mode == 'delete':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            context.delete_item(True)
            return

        if mode == 'adduserselection':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.select_adduser()
            return

        if mode == 'reset_device_id':  # Simple commands
            client.send(sendOK)
            close_connection(client)
            pluginmenu.reset_device_id()
            return

        if mode == 'play':
            client.send(sendOK)
            close_connection(client)
            data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
            playerops.Play((data[1],), "PlayNow", -1, -1, utils.EmbyServers[data[0]])
            return

        # wait for loading
        if mode == 'browse':
            query = params.get("query")

            if query:
                pluginmenu.browse(Handle, params.get('id'), params['query'], params.get('arg'), ServerId)
        elif mode == 'nextepisodes':
            pluginmenu.get_next_episodes(Handle, params['libraryname'])
        elif mode == 'favepisodes':
            pluginmenu.favepisodes(Handle)
        elif mode == 'remotepictures':
            pluginmenu.remotepictures(Handle, params.get('position'))
        else:  # 'listing'
            pluginmenu.listing(Handle)

        client.send(sendOK)
        close_connection(client)
        return

    if 'extrafanart' in IncomingData[1] or 'extrathumbs' in IncomingData[1] or 'Extras/' in IncomingData[1] or IncomingData[1].endswith('/'):
        client.send(sendOK)
    elif IncomingData[0] == "GET":
        http_Query(client, IncomingData[1])
    elif IncomingData[0] == "HEAD":
        if IncomingData[1].startswith("/p-"):
            http_Query(client, IncomingData[1])
        else:
            client.send(sendOK)
    else:
        client.send(sendOK)

    close_connection(client)

def LoadISO(QueryData, MediaIndex, client):
    player.Player.MultiselectionDone = True
    QueryData['MediaSources'] = open_embydb(QueryData['ServerId']).get_mediasource(QueryData['EmbyID'])
    Details = utils.load_VideoitemFromKodiDB(QueryData['Type'], QueryData['KodiId'])
    li = utils.CreateListitem(QueryData['Type'], Details)
    Path = QueryData['MediaSources'][MediaIndex][3]

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    li.setPath(Path)
    PlaylistPosition = playlist.getposition()
    playlist.add(Path, li, PlaylistPosition + 1)
    player.PlayerSkipItem = str(PlaylistPosition)
    globals()["SkipItemVideo"] = QueryData['Payload']
    globals()["QueryDataPrevious"] = QueryData.copy()
    player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediaSources'][MediaIndex][2], PlaySessionId)
    client.send(sendblankfile)
    close_embydb(QueryData['ServerId'])

def http_Query(client, Payload):
    if 'main.m3u8' in Payload:  # Dynamic Transcode query
        player.PlayerSkipItem = "-1"
        player.Player.queuePlayingItem(QueryDataPrevious['EmbyID'], QueryDataPrevious['MediasourceID'], PlaySessionId)
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/videos/%s%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryDataPrevious['ServerId']].server, QueryDataPrevious['EmbyID'], Payload)).encode())
        return

    if SkipItemVideo == Payload:  # 3D, iso (playlist modification)
        player.PlayerSkipItem = "-1"
        player.Player.queuePlayingItem(QueryDataPrevious['EmbyID'], QueryDataPrevious['MediasourceID'], PlaySessionId)
        client.send(sendblankfile)
        globals()["SkipItemVideo"] = ""
        return

    if Cancel:
        globals()["Cancel"] = False
        player.PlayerSkipItem = "-1"
        client.send(sendblankfile)
        player.Player.Cancel()
        return

    QueryData = GetParametersFromURLQuery(Payload)

    if Payload.endswith('.nfo'):  # metadata scraper queries item info. Due to lag of nfo file, the item will be removed by scraper. Workaround: -> trigger item resync from Emby server
        LOG.info("[ nfo query -> refresh item %s ]" % Payload)
        client.send(sendOK)
        utils.EmbyServers[QueryData['ServerId']].library.updated([QueryData['EmbyID']])
        return

    if QueryData['ServerId'] not in utils.EmbyServers:
        client.send(sendOK)
        return

    if QueryData['Type'] == 'picture':
        if utils.enableCoverArt:
            ExtendedParameter = "&EnableImageEnhancers=True"
        else:
            ExtendedParameter = "&EnableImageEnhancers=False"

        if utils.compressArt:
            ExtendedParameter += "&Quality=70"

        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/Items/%s/Images/%s/%s?%s&api_key=%s%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['ImageTag'], utils.EmbyServers[QueryData['ServerId']].Token, ExtendedParameter)).encode())
        return

    if not utils.syncduringplayback:
        utils.SyncPause['playing'] = True

    globals()["PlaySessionId"] = str(uuid.uuid4()).replace("-", "")

    if player.Transcoding:
        utils.EmbyServers[QueryData['ServerId']].API.close_transcode()

    player.Transcoding = False
    player.Player.EmbyServer = utils.EmbyServers[QueryData['ServerId']]

    if QueryData['Type'] == 'specialaudio':
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/audio/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])).encode())
        return

    if QueryData['Type'] == 'specialvideo':
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/videos/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])).encode())
        return

    if QueryData['Type'] == 'audio':
        player.PlayerSkipItem = "-1"
        player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/audio/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])).encode())
        return

    if QueryData['Type'] == 'tvchannel':
        player.Transcoding = True
        player.PlayerSkipItem = "-1"
        player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/videos/%s/stream?static=true&PlaySessionId=%s&DeviceId=%s&api_key=%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token)).encode())
        return

    # Cinnemamode
    if (utils.enableCinemaMovies and QueryData['Type'] == "movie") or (utils.enableCinemaEpisodes and QueryData['Type'] == "episode"):
        if TrailerInitPayload != QueryData['Payload']:  # Trailer init (load)
            globals()["Intros"] = []
            PlayTrailer = True

            if utils.askCinema:
                PlayTrailer = utils.dialog("yesno", heading=utils.addon_name, line1=utils.Translate(33016))

            if PlayTrailer:
                globals()["Intros"] = utils.EmbyServers[QueryData['ServerId']].http.load_Trailers(QueryData['EmbyID'])

        if Intros:
            xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
            URL = Intros[0]['Path']
            LOG.debug("Trailer URL: %s" % URL)
            li = listitem.set_ListItem(Intros[0], utils.EmbyServers[QueryData['ServerId']].server_id)
            li.setPath("http://127.0.0.1:57342" + QueryData['Payload'])
            player.Player.AddonModeTrailerItem = li
            del Intros[0]
            globals()["TrailerInitPayload"] = QueryData['Payload']
            client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % URL).encode())
            return

        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')
        globals()["TrailerInitPayload"] = ""
        player.Player.AddonModeTrailerItem = None

    # Play Kodi synced item
    if QueryData['KodiId']:  # Item synced to Kodi DB
        if QueryData['MediasourcesCount'] == 1:
            if QueryData['Type'] == 'i':
                LoadISO(QueryData, 0, client)
                return

            LoadData(0, QueryData, client)
            return

        # Multiversion
        Selection = []
        QueryData['MediaSources'] = open_embydb(QueryData['ServerId']).get_mediasource(QueryData['EmbyID'])

        for Data in QueryData['MediaSources']:
            Selection.append("%s - %s - %s" % (Data[4], utils.SizeToText(float(Data[5])), Data[3]))

        MediaIndex = utils.dialog("select", heading="Select Media Source:", list=Selection)

        if MediaIndex == -1:
            globals()["Cancel"] = True
            player.PlayerSkipItem = "-1"
            client.send(sendblankfile)
            close_embydb(QueryData['ServerId'])
            return

        # check if multiselection must be forced as native
        if QueryData['MediaSources'][MediaIndex][3].lower().endswith(".iso"):
            LoadISO(QueryData, MediaIndex, client)
            return

        QueryData['MediasourceID'] = QueryData['MediaSources'][MediaIndex][2]
        LoadData(MediaIndex, QueryData, client)
        close_embydb(QueryData['ServerId'])
        return

    SubTitlesAdd(0, QueryData)
    player.Transcoding = IsTranscoding(QueryData['BitrateFromURL'], None, QueryData)

    if player.Transcoding:
        URL = GETTranscodeURL(QueryData['Filename'], False, False, QueryData)
    else:
        URL = "%s/emby/videos/%s/stream?static=true&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s" % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])

    player.PlayerSkipItem = "-1"
    player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
    client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % URL).encode())
    close_embydb(QueryData['ServerId'])

def open_embydb(ServerId):
    if ServerId not in embydb or not embydb[ServerId]:
        globals()["embydb"][ServerId] = dbio.DBOpenRO(ServerId, "http_Query")

    return embydb[ServerId]

def close_embydb(ServerId):
    if ServerId in embydb and embydb[ServerId]:
        dbio.DBCloseRO(ServerId, "http_Query")
        globals()["embydb"][ServerId] = None

# Load SRT subtitles
def SubTitlesAdd(MediaIndex, QueryData):
    Subtitles = open_embydb(QueryData['ServerId']).get_Subtitles(QueryData['EmbyID'], MediaIndex)

    if not Subtitles:
        return

    CounterSubTitle = 0
    DefaultSubtitlePath = ""
    EnableSubtitle = False
    SRTFound = False

    for Data in Subtitles:
        CounterSubTitle += 1

        if Data[3] in ("srt", "ass"):
            SRTFound = True
            SubTitleURL = "%s/emby/videos/%s/%s/Subtitles/%s/stream.%s" % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], Data[2], Data[3])
            request = {'type': "GET", 'url': SubTitleURL, 'params': {}}

            # Get Subtitle Settings
            videodb = dbio.DBOpenRO("video", "SubTitlesAdd")
            FileSettings = videodb.get_FileSettings(QueryData['KodiFileId'])
            dbio.DBCloseRO("video", "SubTitlesAdd")

            if FileSettings:
                EnableSubtitle = bool(FileSettings[9])
            else:
                if DefaultVideoSettings:
                    EnableSubtitle = DefaultVideoSettings['ShowSubtitles']
                else:
                    EnableSubtitle = False

            if Data[4]:
                SubtileLanguage = Data[4]
            else:
                SubtileLanguage = "unknown"

            Filename = utils.PathToFilenameReplaceSpecialCharecters("%s.%s.%s" % (CounterSubTitle, SubtileLanguage, Data[3]))
            Path = utils.download_file_from_Embyserver(request, Filename, utils.EmbyServers[QueryData['ServerId']])

            if Path:
                if DefaultVideoSettings["SubtitlesLanguage"].lower() in Data[5].lower():
                    DefaultSubtitlePath = Path

                    if DefaultVideoSettings["SubtitlesLanguage"].lower() == "forced_only" and "forced" in Data[5].lower():
                        DefaultSubtitlePath = Path
                    else:
                        player.Player.setSubtitles(Path)
                else:
                    player.Player.setSubtitles(Path)

    if SRTFound:
        if DefaultSubtitlePath:
            player.Player.setSubtitles(DefaultSubtitlePath)

        player.Player.showSubtitles(EnableSubtitle)

def LoadData(MediaIndex, QueryData, client):
    if MediaIndex == 0:
        player.Transcoding = IsTranscoding(QueryData['BitrateFromURL'], QueryData['CodecVideo'], QueryData)  # add codec from videostreams, Bitrate (from file)

        if not player.Transcoding:
            if QueryData['ExternalSubtitle'] == "1":
                SubTitlesAdd(0, QueryData)
                close_embydb(QueryData['ServerId'])

            player.PlayerSkipItem = "-1"
            player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
            client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/videos/%s/stream?static=true&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&api_key=%s&%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].Token, QueryData['Filename'])).encode())
            return
    else:
        VideoStreams = open_embydb(QueryData['ServerId']).get_videostreams(QueryData['EmbyID'], MediaIndex)
        QueryData['KodiId'] = str(embydb[QueryData['ServerId']].get_kodiid(QueryData['EmbyID'])[0])
        player.Transcoding = IsTranscoding(VideoStreams[0][4], VideoStreams[0][3], QueryData)

    if player.Transcoding:
        AudioStreams = open_embydb(QueryData['ServerId']).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
        Subtitles = embydb[QueryData['ServerId']].get_Subtitles(QueryData['EmbyID'], MediaIndex)
        SubtitleIndex = -1
        AudioIndex = -1

        if len(AudioStreams) >= 2:
            Selection = []

            for Data in AudioStreams:
                Selection.append(Data[3])

            AudioIndex = utils.dialog("select", heading="Select Audio Stream:", list=Selection)

        if len(Subtitles) >= 1:
            Selection = []

            for Data in Subtitles:
                Selection.append(Data[5])

            SubtitleIndex = utils.dialog("select", heading="Select Subtitle:", list=Selection)

        if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0:  # No change, just transcoding
            URL = GETTranscodeURL(QueryData['Filename'], False, False, QueryData)
            player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
            client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % URL).encode())
            close_embydb(QueryData['ServerId'])
            return

        if not QueryData['MediaSources']:
            QueryData['MediaSources'] = embydb[QueryData['ServerId']].get_mediasource(QueryData['EmbyID'])

        AudioIndex = max(AudioIndex, 0)

        if SubtitleIndex < 0:
            Subtitle = None
        else:
            Subtitle = Subtitles[SubtitleIndex]

        UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[AudioIndex], Subtitle, QueryData, MediaIndex, client)

    AudioStreams = open_embydb(QueryData['ServerId']).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
    UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[0], False, QueryData, MediaIndex, client)

def UpdateItem(MediaSource, AudioStream, Subtitle, QueryData, MediaIndex, client):
    Details = utils.load_VideoitemFromKodiDB(QueryData['Type'], QueryData['KodiId'])
    Filename = utils.PathToFilenameReplaceSpecialCharecters(MediaSource[3])

    if player.Transcoding:
        if Subtitle:
            SubtitleStream = str(Subtitle[2])
        else:
            SubtitleStream = ""

        URL = GETTranscodeURL(Filename, str(AudioStream[2]), SubtitleStream, QueryData)
    else:  # stream
        URL = "%s/emby/videos/%s/stream?static=true&api_key=%s&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&%s" % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], utils.EmbyServers[QueryData['ServerId']].Token, QueryData['MediasourceID'], PlaySessionId, utils.device_id, Filename)

    li = utils.CreateListitem(QueryData['Type'], Details)

    if "3d" in MediaSource[4].lower():
        # inject new playlist item (not update curerent playlist item to initiate 3d selection popup msg
        li.setPath(URL)
        PlaylistPosition = playlist.getposition()
        playlist.add(URL, li, PlaylistPosition + 1)
        player.PlayerSkipItem = str(PlaylistPosition)
        globals()["SkipItemVideo"] = QueryData['Payload']
        globals()["QueryDataPrevious"] = QueryData.copy()
        player.PlayerSkipItem = "-1"
        player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
        client.send(sendblankfile)
        close_embydb(QueryData['ServerId'])
        return

    li.setPath("http://127.0.0.1:57342" + QueryData['Payload'])
    player.Player.updateInfoTag(li)
    SubTitlesAdd(MediaIndex, QueryData)
    player.PlayerSkipItem = "-1"
    player.Player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
    client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % URL).encode())
    close_embydb(QueryData['ServerId'])

def GETTranscodeURL(Filename, Audio, Subtitle, QueryData):
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

    globals()["QueryDataPrevious"] = QueryData.copy()
    return "%s/emby/videos/%s/master.m3u8?api_key=%s&MediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&VideoCodec=%s&AudioCodec=%s%s%s%s%s&TranscodeReasons=%s%s" % (utils.EmbyServers[QueryData['ServerId']].server, QueryData['EmbyID'], utils.EmbyServers[QueryData['ServerId']].Token, QueryData['MediasourceID'], PlaySessionId, utils.device_id, utils.TranscodeFormatVideo, utils.TranscodeFormatAudio, TranscodingVideo, TranscodingAudio, Audio, Subtitle, QueryData['TranscodeReasons'], Filename)

def IsTranscoding(Bitrate, Codec, QueryData):
    if utils.transcodeH265:
        if Codec in ("h265", "hevc"):
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif utils.transcodeDivx:
        if Codec == "msmpeg4v3":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif utils.transcodeXvid:
        if Codec == "mpeg4":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True
    elif utils.transcodeMpeg2:
        if Codec == "mpeg2video":
            IsTranscodingByCodec(Bitrate, QueryData)
            return True

    QueryData['TargetVideoBitrate'] = utils.videoBitrate
    QueryData['TargetAudioBitrate'] = utils.audioBitrate
    QueryData['TranscodeReasons'] = "ContainerBitrateExceedsLimit"
    return Bitrate >= QueryData['TargetVideoBitrate']

def IsTranscodingByCodec(Bitrate, QueryData):
    if Bitrate >= utils.videoBitrate:
        QueryData['TranscodeReasons'] = "ContainerBitrateExceedsLimit"
        QueryData['TargetVideoBitrate'] = utils.videoBitrate
        QueryData['TargetAudioBitrate'] = utils.audioBitrate
    else:
        QueryData['TranscodeReasons'] = "VideoCodecNotSupported"
        QueryData['TargetVideoBitrate'] = 0
        QueryData['TargetAudioBitrate'] = 0

def GetParametersFromURLQuery(Payload):
    Temp = Payload[Payload.rfind("/") + 1:]
    Data = Temp.split("-")
    QueryData = {'MediaSources': [], 'TargetVideoBitrate': 0, 'TargetAudioBitrate': 0, 'Payload': Payload, 'Type': MediaTypeMapping[Data[0]], 'ServerId': Data[1], 'EmbyID': Data[2]}

    if Data[0] == "p":  # Image/picture
        QueryData['ImageIndex'] = Data[3]
        QueryData['ImageType'] = EmbyArtworkIDs[Data[4]]
        QueryData['ImageTag'] = Data[5]
    elif Data[0] in ("e", "m", "M", "i", "T"):  # Video or iso
        QueryData['MediasourceID'] = Data[3]
        QueryData['KodiId'] = Data[4]
        QueryData['KodiFileId'] = Data[5]
        QueryData['BitrateFromURL'] = int(Data[6])
        QueryData['ExternalSubtitle'] = Data[7]
        QueryData['MediasourcesCount'] = int(Data[8])
        QueryData['CodecVideo'] = Data[9]
        QueryData['Filename'] = Data[10]

        # Dynamic content played, cleare cache
        if QueryData['KodiFileId'] == "None":
            pluginmenu.QueryCache = {} # Clear Cache
    elif Data[0] == "a":  # Audio
        QueryData['MediasourceID'] = None
        QueryData['Filename'] = Data[3]
    elif Data[0] == "t":  # tv channel
        QueryData['MediasourceID'] = None
        QueryData['Filename'] = Data[3]
    else:
        QueryData['MediasourceID'] = Data[3]
        QueryData['Filename'] = Data[4]

    return QueryData

def close_connection(client):
    try:  # try force socket to close
        client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')
    except:
        LOG.info("[ webservice/57342 ] so_linger not supported")

    client.close()

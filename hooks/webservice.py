import socket
from _thread import start_new_thread, get_ident
import xbmc
ModulesLoaded = False
DefaultVideoSettings = {}
MediaTypeMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "A": "specialaudio", "V": "specialvideo", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
sendNoContent = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
BlankWAV = b'\x52\x49\x46\x46\x25\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x74\x00\x00\x00\x00'
sendBlankWAV = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 45\r\nContent-type: audio/wav\r\n\r\n'.encode() + BlankWAV # used to "stop" playback by sending a WAV file with silance. File is valid, so Kodi will not raise an error message
SkipItemVideo = ""
TrailerInitItem = ["", None] # payload/listitem of the trailer initiated content item
PlaySessionId = ""
Cancel = False
embydb = {}
QueryDataPrevious = {}
ArtworkCache = [0, {}] # Memory size/data
dbio = None
utils = None
xmls = None
context = None
playerops = None
pluginmenu = None
player = None
uuid = None
parse_qsl = None
unquote = None
PayloadHeadRequest = ""
Socket = None


def start():
    xbmc.log("EMBY.hooks.webservice: Start", xbmc.LOGINFO)
    close()
    start_new_thread(Listen, ())

def close():
    if Socket:
        try:
            Socket.shutdown(socket.SHUT_RDWR)
            Socket.close()
        except Exception as Error:
            xbmc.log("EMBY.hooks.webservice: Socket shutdown (close) %s" % Error, xbmc.LOGERROR)

        globals()["Socket"] = None
        xbmc.log("Shutdown weservice", xbmc.LOGINFO)

def Listen():
    xbmc.log("EMBY.hooks.webservice: -->[ webservice/57342 ]", xbmc.LOGINFO)
    globals()["Socket"] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    Socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    Socket.bind(('127.0.0.1', 57342))
    Socket.settimeout(None)
    Socket.listen()

    while True:
        try:
            client, _ = Socket.accept()
        except:
            break

        start_new_thread(worker_Query, (client,))

    xbmc.log("EMBY.hooks.webservice: --<[ webservice/57342 ]", xbmc.LOGINFO)
    globals()["Socket"] = None

def worker_Query(client):  # thread by caller
    data = client.recv(1024).decode()
    client.settimeout(None)
    DelayQuery = 0

    # Waiting for socket init
    while not ModulesLoaded:
        xbmc.log("Modules not loaded", xbmc.LOGINFO)
        xbmc.sleep(100)

    while not utils.EmbyServers:
        Break = False

        if utils.PluginStarted:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, skip", xbmc.LOGINFO)
            Break = True

        if utils.sleep(1) or DelayQuery >= 60:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, delay query", xbmc.LOGINFO)
            Break = True

        if Break:
            xbmc.log("Terminate query", xbmc.LOGERROR)
            client.send(sendNoContent)
            client.close()
            return

        DelayQuery += 1

    IncomingData = data.split(' ')

    # events by event.py
    if IncomingData[0] == "EVENT":
        args = IncomingData[1].split(";")

        if args[1] == "contextmenu":
            client.send(sendOK)
            client.close()
            context.select_menu()
            return

        # no delay
        Handle = args[1]
        params = dict(parse_qsl(args[2][1:]))
        mode = params.get('mode')
        ServerId = params.get('server')

        if mode == 'settings':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % utils.PluginId)
            return

        if mode == 'managelibsselection':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.select_managelibs()
            return

        if mode == 'texturecache':  # Simple commands
            client.send(sendOK)
            client.close()

            if not utils.artworkcacheenable:
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
            else:
                pluginmenu.cache_textures()

            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.databasereset()
            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.databasereset()
            return

        if mode == 'nodesreset':  # Simple commands
            client.send(sendOK)
            client.close()
            utils.nodesreset()
            return

        if mode == 'delete':  # Simple commands
            client.send(sendOK)
            client.close()
            context.delete_item(True)
            return

        if mode == 'reset_device_id':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.reset_device_id()
            return

        if mode == 'skinreload':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.log("EMBY.hooks.webservice: Reload skin by webservice", xbmc.LOGINFO)
            return

        if mode == 'play':
            client.send(sendOK)
            client.close()
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
        client.close()
        return

    if 'extrafanart' in IncomingData[1] or 'extrathumbs' in IncomingData[1] or 'Extras/' in IncomingData[1] or 'favicon.ico' in IncomingData[1] or IncomingData[1].endswith('/'):
        client.send(sendOK)
    elif IncomingData[0] == "GET":
        http_Query(client, IncomingData[1], IncomingData[0])
    elif IncomingData[0] == "HEAD":
        if IncomingData[1].startswith('/p-'):
            http_Query(client, IncomingData[1], IncomingData[0])
        else:
            globals()["PayloadHeadRequest"] = IncomingData[1]
            client.send(sendOK)
    else:
        client.send(sendOK)

    client.close()

def LoadISO(QueryData, MediaIndex, client, ThreadId): # native content
    player.MultiselectionDone = True
    QueryData['MediaSources'] = open_embydb(QueryData['ServerId'], ThreadId).get_mediasource(QueryData['EmbyID'])
    Path = QueryData['MediaSources'][MediaIndex][3]

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    ListItem = player.load_KodiItem("LoadISO", QueryData['KodiId'], QueryData['Type'], Path)

    if not ListItem:
        client.send(sendOK)
    else:
        QueryData['MediasourceID'] = QueryData['MediaSources'][MediaIndex][2]
        add_playlist_item(client, ListItem, QueryData, Path)

    close_embydb(QueryData['ServerId'], ThreadId)

def send_BlankWAV(client):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    client.send(sendBlankWAV)

def build_Path(QueryData, Data, Filename):
    if Filename:
        Filename = "&%s" % Filename

    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    if QueryData['MediasourceID']:
        Path = '%s/emby/%s%sMediaSourceId=%s&PlaySessionId=%s&DeviceId=%s&api_key=%s%s' % (utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl'], Data, Parameter, QueryData['MediasourceID'], PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken'], Filename)
    else:
        Path = '%s/emby/%s%sPlaySessionId=%s&DeviceId=%s&api_key=%s%s' % (utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl'], Data, Parameter, PlaySessionId, utils.device_id, utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken'], Filename)

    return Path

def send_redirect(client, QueryData, Data, Filename):
    Path = build_Path(QueryData, Data, Filename)
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: %s\r\nContent-length: 0\r\n\r\n' % Path).encode())

def http_Query(client, Payload, RequestType):
    if 'main.m3u8' in Payload:  # Dynamic Transcode query
        player.queuePlayingItem(QueryDataPrevious['EmbyID'], QueryDataPrevious['MediasourceID'], PlaySessionId, QueryDataPrevious['IntroStartPositionTicks'], QueryDataPrevious['IntroEndPositionTicks'], QueryDataPrevious['CreditsPositionTicks'])
        xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
        client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s/emby/videos/%s%s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % (utils.EmbyServers[QueryDataPrevious['ServerId']].ServerData['ServerUrl'], QueryDataPrevious['EmbyID'], Payload)).encode())
        return

    if SkipItemVideo == Payload:  # 3D, iso (playlist modification)
        send_BlankWAV(client)
        globals()["SkipItemVideo"] = ""
        return

    if Cancel:
        globals()["Cancel"] = False
        send_BlankWAV(client)
        player.Cancel()
        return

    if Payload.endswith('.nfo'):  # metadata scraper queries item info. Due to lag of nfo file, the item will be removed by scraper. Workaround: -> trigger item resync from Emby server
        xbmc.log("EMBY.hooks.webservice: [ nfo query -> refresh item %s ]" % Payload, xbmc.LOGINFO)
        client.send(sendOK)
        return

    # Workaround for invalid Kodi GET requests when played via widget
    if not Payload.startswith("/p-"):
        if Payload != PayloadHeadRequest:
            xbmc.log("Invalid GET request filtered: %s " % Payload, xbmc.LOGWARNING)
            client.send(sendNoContent)
            return

    QueryData = GetParametersFromURLQuery(Payload)

    if QueryData['ServerId'] not in utils.EmbyServers:
        client.send(sendOK)
        return

    if QueryData['Type'] == 'picture':
        if Payload not in ArtworkCache[1]:
            xbmc.log("EMBY.hooks.webservice: Load artwork data: %s" % Payload, xbmc.LOGDEBUG)

            # Remove items from artwork cache if mem is over 100MB
            if ArtworkCache[0] > 100000000:
                for PayloadId, ArtworkCacheData in list(ArtworkCache[1].items()):
                    globals()['ArtworkCache'][0] -= int(ArtworkCacheData['Content-Length'])
                    del globals()['ArtworkCache'][1][PayloadId]

                    if ArtworkCache[0] < 100000000:
                        break

            if not QueryData['Overlay']:
                BinaryData, ContentType, _ = utils.EmbyServers[QueryData['ServerId']].API.get_Image_Binary(QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['ImageTag'])
                globals()['ArtworkCache'][1][Payload] = {'Content-Length': len(BinaryData), 'Content-Type': ContentType, "BinaryData": BinaryData}
            else:
                BinaryData = utils.image_overlay(QueryData['ImageTag'], QueryData['ServerId'], QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['Overlay'])
                globals()['ArtworkCache'][1][Payload] = {'Content-Length': len(BinaryData), 'Content-Type': "image/jpeg", "BinaryData": BinaryData}

            globals()['ArtworkCache'][0] = ArtworkCache[0] + globals()['ArtworkCache'][1][Payload]['Content-Length']
        else:
            xbmc.log("EMBY.hooks.webservice: Load artwork data from cache: %s" % Payload, xbmc.LOGDEBUG)

        HTTPHeader = ('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: %s\r\nContent-Type: %s\r\n\r\n' % (ArtworkCache[1][Payload]['Content-Length'], ArtworkCache[1][Payload]['Content-Type'])).encode()

        if RequestType == "HEAD":
            client.send(HTTPHeader)
        else:
            client.send(HTTPHeader + ArtworkCache[1][Payload]['BinaryData'])

        return

    if not utils.syncduringplayback:
        utils.SyncPause['playing'] = True

    globals()["PlaySessionId"] = str(uuid.uuid4()).replace("-", "")
    player.EmbyServerPlayback = utils.EmbyServers[QueryData['ServerId']]

    if QueryData['Type'] == 'specialaudio':
        send_redirect(client, QueryData, "audio/%s/stream?static=true" % QueryData['EmbyID'], QueryData['Filename'])
        return

    if QueryData['Type'] == 'specialvideo':
        send_redirect(client, QueryData, "videos/%s/stream?static=true" % QueryData['EmbyID'], QueryData['Filename'])
        return

    if QueryData['Type'] == 'audio':
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
        send_redirect(client, QueryData, "audio/%s/stream?static=true" % QueryData['EmbyID'], QueryData['Filename'])
        return

    if QueryData['Type'] == 'tvchannel':
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
        send_redirect(client, QueryData, "videos/%s/stream.ts" % QueryData['EmbyID'], "")
        return

    if QueryData['Type'] == 'channel':
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
        send_redirect(client, QueryData, "videos/%s/master.m3u8" % QueryData['EmbyID'], "stream.ts")
        return

    # Cinnemamode
    if (utils.enableCinemaMovies and QueryData['Type'] == "movie") or (utils.enableCinemaEpisodes and QueryData['Type'] == "episode"):
        if TrailerInitItem[0] != QueryData['Payload']:  # Trailer init (load)
            utils.EmbyServers[QueryData['ServerId']].http.Intros = []
            PlayTrailer = True

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                utils.EmbyServers[QueryData['ServerId']].http.load_Trailers(QueryData['EmbyID'])

        if utils.EmbyServers[QueryData['ServerId']].http.Intros:
            globals()["TrailerInitItem"][1] = player.load_KodiItem("http_Query", QueryData['KodiId'], QueryData['Type'], None) # query path
            player.SkipItem = True
            xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
            URL = utils.EmbyServers[QueryData['ServerId']].http.Intros[0]['Path']
            xbmc.log("EMBY.hooks.webservice: Trailer URL: %s" % URL, xbmc.LOGDEBUG)
            ListItem = listitem.set_ListItem(utils.EmbyServers[QueryData['ServerId']].http.Intros[0], QueryData['ServerId'], "http://127.0.0.1:57342" + QueryData['Payload'])
            del utils.EmbyServers[QueryData['ServerId']].http.Intros[0]
            globals()["TrailerInitItem"][0] = QueryData['Payload']
            xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
            client.send(('HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: %s\r\nConnection: close\r\nContent-length: 0\r\n\r\n' % URL).encode())
            utils.XbmcPlayer.updateInfoTag(ListItem)
            return

        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')

        if TrailerInitItem[0]:
            utils.XbmcPlayer.updateInfoTag(TrailerInitItem[1])

    globals()["PayloadHeadRequest"] = ""
    globals()["TrailerInitItem"][0] = ""
    player.SkipItem = False
    ThreadId = get_ident()

    # Play Kodi synced item
    if QueryData['KodiId']:  # Item synced to Kodi DB
        if QueryData['MediasourcesCount'] == 1:
            if QueryData['MediaType'] == 'i':
                LoadISO(QueryData, 0, client, ThreadId)
                return

            LoadData(0, QueryData, client, ThreadId)
            return

        # Multiversion
        Selection = []
        QueryData['MediaSources'] = open_embydb(QueryData['ServerId'], ThreadId).get_mediasource(QueryData['EmbyID'])
        close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input

        for Data in QueryData['MediaSources']:
            Selection.append("%s - %s - %s" % (Data[4], utils.SizeToText(float(Data[5])), Data[3]))

        MediaIndex = utils.Dialog.select(heading="Select Media Source:", list=Selection)

        if MediaIndex == -1:
            globals()["Cancel"] = True
            send_BlankWAV(client)
            return

        # check if multiselection must be forced as native
        if QueryData['MediaSources'][MediaIndex][3].lower().endswith(".iso"):
            LoadISO(QueryData, MediaIndex, client, ThreadId)
            return

        QueryData['MediasourceID'] = QueryData['MediaSources'][MediaIndex][2]
        LoadData(MediaIndex, QueryData, client, ThreadId)
        return

    SubTitlesAdd(0, QueryData, ThreadId)

    if IsTranscoding(QueryData['BitrateFromURL'], None, QueryData):
        URL, EndParameter = GETTranscodeURL(QueryData['Filename'], False, False, QueryData)
    else:
        URL = "videos/%s/stream?static=true" % QueryData['EmbyID']
        EndParameter = QueryData['Filename']

    player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
    send_redirect(client, QueryData, URL, EndParameter)
    close_embydb(QueryData['ServerId'], ThreadId)

def open_embydb(ServerId, ThreadId):
    if ThreadId not in embydb or not embydb[ThreadId]:
        globals()["embydb"][ThreadId] = dbio.DBOpenRO(ServerId, "http_Query")

    return embydb[ThreadId]

def close_embydb(ServerId, ThreadId):
    if ThreadId in embydb and embydb[ThreadId]:
        dbio.DBCloseRO(ServerId, "http_Query")
        globals()["embydb"][ThreadId] = None

# Load SRT subtitles
def SubTitlesAdd(MediaIndex, QueryData, ThreadId):
    Subtitles = open_embydb(QueryData['ServerId'], ThreadId).get_Subtitles(QueryData['EmbyID'], MediaIndex)

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

            BinaryData = utils.EmbyServers[QueryData['ServerId']].API.get_Subtitle_Binary(QueryData['EmbyID'], QueryData['MediasourceID'], Data[2], Data[3])

            if BinaryData:
                Path = "%s%s" % (utils.FolderEmbyTemp, utils.PathToFilenameReplaceSpecialCharecters("%s.%s.%s" % (CounterSubTitle, SubtileLanguage, Data[3])))
                utils.writeFileBinary(Path, BinaryData)

                if DefaultVideoSettings["SubtitlesLanguage"].lower() in Data[5].lower():
                    DefaultSubtitlePath = Path

                    if DefaultVideoSettings["SubtitlesLanguage"].lower() == "forced_only" and "forced" in Data[5].lower():
                        DefaultSubtitlePath = Path
                    else:
                        utils.XbmcPlayer.setSubtitles(Path)
                else:
                    utils.XbmcPlayer.setSubtitles(Path)

    if SRTFound:
        if DefaultSubtitlePath:
            utils.XbmcPlayer.setSubtitles(DefaultSubtitlePath)

        utils.XbmcPlayer.showSubtitles(EnableSubtitle)

def LoadData(MediaIndex, QueryData, client, ThreadId):
    if MediaIndex == 0:
        Transcoding = IsTranscoding(QueryData['BitrateFromURL'], QueryData['CodecVideo'], QueryData)  # add codec from videostreams, Bitrate (from file)

        if not Transcoding:
            if QueryData['ExternalSubtitle'] == "1":
                SubTitlesAdd(0, QueryData, ThreadId)
                close_embydb(QueryData['ServerId'], ThreadId)

            player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
            URL = "videos/%s/stream?static=true" % QueryData['EmbyID']
            EndParameter = QueryData['Filename']

            if QueryData['Remote']:  # remote content -> verify source
                status_code = utils.EmbyServers[QueryData['ServerId']].API.get_stream_statuscode(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId)
                xbmc.log("EMBY.hooks.webservice: Remote content verification: %s" % status_code, xbmc.LOGINFO)

                if status_code != 200:
                    send_redirect(client, QueryData, "videos/%s/master.m3u8?VideoCodec=%s&AudioCodec=%s&TranscodeReasons=DirectPlayError" % (QueryData['EmbyID'], utils.TranscodeFormatVideo, utils.TranscodeFormatAudio), QueryData['Filename'])
                    return

            send_redirect(client, QueryData, URL, EndParameter)
            return
    else:
        VideoStreams = open_embydb(QueryData['ServerId'], ThreadId).get_videostreams(QueryData['EmbyID'], MediaIndex)
        QueryData['KodiId'] = str(embydb[ThreadId].get_kodiid(QueryData['EmbyID'])[0])
        Transcoding = IsTranscoding(VideoStreams[0][4], VideoStreams[0][3], QueryData)

    if Transcoding:
        AudioStreams = open_embydb(QueryData['ServerId'], ThreadId).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
        Subtitles = embydb[ThreadId].get_Subtitles(QueryData['EmbyID'], MediaIndex)
        SubtitleIndex = -1
        AudioIndex = -1

        if len(AudioStreams) > 1:
            Selection = []

            for Data in AudioStreams:
                Selection.append(Data[3])

            close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input
            AudioIndex = utils.Dialog.select(heading="Select Audio Stream:", list=Selection)

        if len(Subtitles) >= 1:
            Selection = []

            for Data in Subtitles:
                Selection.append(Data[5])

            close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input
            SubtitleIndex = utils.Dialog.select(heading="Select Subtitle:", list=Selection)

        if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0:  # No change, just transcoding
            URL, EndParameter = GETTranscodeURL(QueryData['Filename'], False, False, QueryData)
            player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
            send_redirect(client, QueryData, URL, EndParameter)
            close_embydb(QueryData['ServerId'], ThreadId)
            return

        if not QueryData['MediaSources']:
            QueryData['MediaSources'] = open_embydb(QueryData['ServerId'], ThreadId).get_mediasource(QueryData['EmbyID'])
            close_embydb(QueryData['ServerId'], ThreadId)

        AudioIndex = max(AudioIndex, 0)

        if SubtitleIndex < 0:
            Subtitle = None
        else:
            Subtitle = Subtitles[SubtitleIndex]

        UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[AudioIndex], Subtitle, QueryData, MediaIndex, client, Transcoding, ThreadId)
        return

    AudioStreams = open_embydb(QueryData['ServerId'], ThreadId).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
    UpdateItem(QueryData['MediaSources'][MediaIndex], AudioStreams[0], False, QueryData, MediaIndex, client, Transcoding, ThreadId)

def UpdateItem(MediaSource, AudioStream, Subtitle, QueryData, MediaIndex, client, Transcoding, ThreadId):
    Filename = utils.PathToFilenameReplaceSpecialCharecters(MediaSource[3])

    if Transcoding:
        if Subtitle:
            SubtitleStream = str(Subtitle[2])
        else:
            SubtitleStream = ""

        URL, EndParameter = GETTranscodeURL(Filename, str(AudioStream[2]), SubtitleStream, QueryData)
    else:  # stream
        URL = "videos/%s/stream?static=true" % QueryData['EmbyID']
        EndParameter = Filename

    if "3d" in MediaSource[4].lower():
        # inject new playlist item (not update curerent playlist item to initiate 3d selection popup msg
        Path = build_Path(QueryData, URL, EndParameter)
        ListItem = player.load_KodiItem("UpdateItem", QueryData['KodiId'], QueryData['Type'], Path)

        if not ListItem:
            client.send(sendOK)
            close_embydb(QueryData['ServerId'], ThreadId)
            return

        add_playlist_item(client, ListItem, QueryData, Path)
        close_embydb(QueryData['ServerId'], ThreadId)
        return

    SubTitlesAdd(MediaIndex, QueryData, ThreadId)
    player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], PlaySessionId, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
    send_redirect(client, QueryData, URL, EndParameter)
    close_embydb(QueryData['ServerId'], ThreadId)

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
        Filename = "stream-" + Filename

    return "videos/%s/master.m3u8?VideoCodec=%s&AudioCodec=%s%s%s%s%s&TranscodeReasons=%s" % (QueryData['EmbyID'], utils.TranscodeFormatVideo, utils.TranscodeFormatAudio, TranscodingVideo, TranscodingAudio, Audio, Subtitle, QueryData['TranscodeReasons']), Filename

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

    QueryData.update({'TranscodeReasons': "ContainerBitrateExceedsLimit", 'TargetVideoBitrate': utils.videoBitrate, 'TargetAudioBitrate': utils.audioBitrate})
    return Bitrate >= QueryData['TargetVideoBitrate']

def IsTranscodingByCodec(Bitrate, QueryData):
    if Bitrate >= utils.videoBitrate:
        QueryData.update({'TranscodeReasons': "ContainerBitrateExceedsLimit", 'TargetVideoBitrate': utils.videoBitrate, 'TargetAudioBitrate': utils.audioBitrate})
    else:
        QueryData.update({'TranscodeReasons': "VideoCodecNotSupported", 'TargetVideoBitrate': 0, 'TargetAudioBitrate': 0})

def GetParametersFromURLQuery(Payload):
    Temp = Payload[Payload.rfind("/") + 1:]
    Data = Temp.split("-")
    QueryData = {'MediasourceID': None, 'MediaSources': [], 'TargetVideoBitrate': 0, 'TargetAudioBitrate': 0, 'Payload': Payload, 'Type': MediaTypeMapping[Data[0]], 'ServerId': Data[1], 'EmbyID': Data[2], 'IntroStartPositionTicks': 0, 'IntroEndPositionTicks': 0, 'CreditsPositionTicks': 0, 'MediaType': Data[0]}

    if Data[0] == "p":  # Image/picture
        QueryData.update({'ImageIndex': Data[3], 'ImageType': EmbyArtworkIDs[Data[4]], 'ImageTag': Data[5]})

        if QueryData['ImageType'] == "Chapter":
            QueryData['Overlay'] = unquote(Data[6])
        else:
            QueryData['Overlay'] = ""
    elif Data[0] in ("e", "m", "M", "i", "T", "v"):  # Video or iso
        QueryData.update({'MediasourceID': Data[3], 'KodiId': Data[4], 'KodiFileId': Data[5], 'BitrateFromURL': int(Data[6]), 'ExternalSubtitle': Data[7], 'MediasourcesCount': int(Data[8]), 'CodecVideo': Data[9], 'IntroStartPositionTicks': int(Data[10]), 'IntroEndPositionTicks': int(Data[11]), 'CreditsPositionTicks': int(Data[12]), 'Remote': int(Data[13]), 'Filename': Data[14]})
        globals()["QueryDataPrevious"] = QueryData.copy()
        player.PlaylistRemoveItem = -1
    elif Data[0] in ("a", "t"):  # Audio, tv channel
        QueryData.update({'Filename': Data[3]})
    elif Data[0] == "c":  # e.g. channel
        QueryData.update({'MediasourceID': Data[3], 'Filename': Data[4]})
        globals()["QueryDataPrevious"] = QueryData.copy()
    else:
        QueryData.update({'MediasourceID': Data[3], 'Filename': Data[4]})

    return QueryData

def add_playlist_item(client, ListItem, QueryData, Path):
    player.replace_playlist_listitem(ListItem, PlaySessionId, QueryData, Path)
    globals()["SkipItemVideo"] = QueryData['Payload']
    send_BlankWAV(client)

xbmc.log("EMBY.hooks.webservice: -->[ Init ]", xbmc.LOGINFO)
start_new_thread(Listen, ())

# Late imports to start the socket as fast as possible
import uuid
from urllib.parse import parse_qsl, unquote
from database import dbio
from emby import listitem
from helper import utils, xmls, context, playerops, pluginmenu, player
DefaultVideoSettings = xmls.load_defaultvideosettings()
ModulesLoaded = True
xbmc.log("EMBY.hooks.webservice: --<[ Init ]", xbmc.LOGINFO)

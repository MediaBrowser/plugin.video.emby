from _thread import start_new_thread
import uuid
import _socket
import xbmc
ModulesLoaded = False
DefaultVideoSettings = {}
MediaIdMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "A": "specialaudio", "V": "specialvideo", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
EmbyIdMapping = {"m": "Movie", "e": "Episode", "M": "MusicVideo", "a": "Audio", "i": "Movie", "T": "Video", "v": "Video", "A": "Audio"}
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
sendNoContent = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
BlankWAV = b'\x52\x49\x46\x46\x25\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x74\x00\x00\x00\x00' # native blank wave file
sendBlankWAV = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 45\r\nContent-type: audio/wav\r\n\r\n'.encode() + BlankWAV # used to "stop" playback by sending a WAV file with silence. File is valid, so Kodi will not raise an error message
TrailerInitItem = ["", None] # payload/listitem of the trailer initiated content item
Cancel = False
embydb = {}
ArtworkCache = [0, {}] # total cached size / {HTTP parameters, [binary data, item size]}
dbio = None
utils = None
urllibparse = None
listitem = None
context = None
playerops = None
pluginmenu = None
player = None
PayloadHeadRequest = ""
Running = False
Socket = None
KeyBoard = None
DelayedContent = {}

def start():
    globals()['Socket'] = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    Socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    Socket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
    Socket.bind(('127.0.0.1', 57342))
    Socket.settimeout(None)
    xbmc.log("EMBY.hooks.webservice: Start", 1) # LOGINFO
    globals()["Running"] = True
    start_new_thread(Listen, ())

def close():
    if Running:
        globals()["Running"] = False

        try:
            try:
                Socket.shutdown(_socket.SHUT_RDWR)
            except Exception as Error:
                xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 1) # LOGINFO

            Socket.close()
            xbmc.log("EMBY.hooks.webservice: Socket shutdown", 1) # LOGINFO
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket close (error) {Error}", 3) # LOGERROR

        xbmc.log("Shutdown weservice", 1) # LOGINFO
        xbmc.log(f"EMBY.hooks.webservice: DelayedContent queue size: {len(DelayedContent)}", 1) # LOGINFO

def Listen():
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ webservice/57342 ]", 0) # LOGDEBUG
    Socket.listen()

    while True:
        try:
            fd, _ = Socket._accept()
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 3) # LOGERROR
            break

        start_new_thread(worker_Query, (fd,))

    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ webservice/57342 ]", 0) # LOGDEBUG

def worker_Query(fd):  # thread by caller
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ worker_Query ]", 0) # LOGDEBUG
    client = _socket.socket(fileno=fd)
    client.settimeout(None)
    data = client.recv(1024).decode()
    xbmc.log(f"EMBY.hooks.webservice: Incoming Data: {data}", 0) # LOGDEBUG
    DelayQuery = 0

    # Waiting for socket init
    while not ModulesLoaded:
        xbmc.sleep(100)

    while not utils.EmbyServers or not list(utils.EmbyServers.values())[0].ServerData['Online']:
        Break = False

        if utils.sleep(1):
            xbmc.log("EMBY.hooks.webservice: Kodi Shutdown", 1) # LOGINFO
            Break = True

        if DelayQuery >= 30:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, timeout query", 1) # LOGINFO
            Break = True

        if Break:
            client.send(sendNoContent)
            client.close()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] terminate query", 0) # LOGDEBUG
            return

        DelayQuery += 1

    IncomingData = data.split(' ')

    # events by event.py
    if IncomingData[0] == "EVENT":
        args = IncomingData[1].split(";")

        if args[1] == "specials":
            client.send(sendOK)
            client.close()
            context.specials()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event specials", 0) # LOGDEBUG
            return

        if args[1] == "download":
            client.send(sendOK)
            client.close()
            context.download()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event download", 0) # LOGDEBUG
            return

        if args[1] == "deletedownload":
            client.send(sendOK)
            client.close()
            context.deletedownload()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event deletedownload", 0) # LOGDEBUG
            return

        if args[1] == "record":
            client.send(sendOK)
            client.close()
            context.Record()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event record", 0) # LOGDEBUG
            return

        if args[1] == "addremoteclient":
            client.send(sendOK)
            client.close()
            context.add_remoteclients()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event addremoteclient", 0) # LOGDEBUG
            return

        if args[1] == "removeremoteclient":
            client.send(sendOK)
            client.close()
            context.delete_remoteclients()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event removeremoteclient", 0) # LOGDEBUG
            return

        if args[1] == "watchtogether":
            client.send(sendOK)
            client.close()
            context.watchtogether()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event watchtogether", 0) # LOGDEBUG
            return

        if args[1] == "refreshitem":
            client.send(sendOK)
            client.close()
            context.refreshitem()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event refreshitem", 0) # LOGDEBUG
            return

        if args[1] == "deleteitem":
            client.send(sendOK)
            client.close()
            context.deleteitem()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event deleteitem", 0) # LOGDEBUG
            return

        if args[1] == "favorites":
            client.send(sendOK)
            client.close()
            context.favorites()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event favorites", 0) # LOGDEBUG
            return

        # no delay
        Handle = args[1]
        params = dict(urllibparse.parse_qsl(args[2][1:]))
        mode = params.get('mode', "")
        ServerId = params.get('server', "")

        if mode == 'search':  # Simple commands
            client.send(sendOK)
            client.close()
            KeyBoard.setDefault('')
            KeyBoard.setHeading("Search term")
            KeyBoard.doModal()
            SearchTerm = ""

            if KeyBoard.isConfirmed():
                SearchTerm = KeyBoard.getText()

            if SearchTerm:
                pluginmenu.SearchTerm = SearchTerm
                CacheId1 = f"0Search0{ServerId}0"
                CacheId2 = f"0Search0{ServerId}0{utils.maxnodeitems}"

                if "All" in pluginmenu.QueryCache:
                    if CacheId1 in pluginmenu.QueryCache["All"]:
                        pluginmenu.QueryCache["All"][CacheId1][0] = False
                    elif CacheId2 in pluginmenu.QueryCache["All"]:
                        pluginmenu.QueryCache["All"][CacheId2][0] = False

                utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "videos", "parameters": ["plugin://plugin.video.emby-next-gen/?id=0&mode=browse&query=Search&server={ServerId}&parentid=0&content=All&libraryid=0", "return"]}}}}')

            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event search", 0) # LOGDEBUG
            return

        if mode == 'settings':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby-next-gen)')
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event settings", 0) # LOGDEBUG
            return

        if mode == 'managelibsselection':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.select_managelibs()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event managelibsselection", 0) # LOGDEBUG
            return

        if mode == 'texturecache':  # Simple commands
            client.send(sendOK)
            client.close()

            if not utils.artworkcacheenable:
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False)
            else:
                pluginmenu.cache_textures()

            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event texturecache", 0) # LOGDEBUG
            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.databasereset()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event databasereset", 0) # LOGDEBUG
            return

        if mode == 'nodesreset':  # Simple commands
            client.send(sendOK)
            client.close()
            utils.nodesreset()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event nodesreset", 0) # LOGDEBUG
            return

        if mode == 'delete':  # Simple commands
            client.send(sendOK)
            client.close()
            context.delete_item(True)
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event delete", 0) # LOGDEBUG
            return

        if mode == 'skinreload':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('ReloadSkin()')
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event skinreload", 0) # LOGDEBUG
            return

        if mode == 'play':
            client.send(sendOK)
            client.close()
            playerops.PlayEmby((params.get('item'),), "PlayNow", -1, -1, utils.EmbyServers[ServerId], 0)
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event play", 0) # LOGDEBUG
            return

        # wait for loading
        if mode == 'browse':
            query = params.get("query")

            if query:
                pluginmenu.browse(Handle, params.get('id'), query, params.get('parentid'), params.get('content'), ServerId, params.get('libraryid'))
        elif mode == 'nextepisodes':
            pluginmenu.get_next_episodes(Handle, params['libraryname'])
        elif mode == 'favepisodes':
            pluginmenu.favepisodes(Handle)
        elif mode == 'favseasons':
            pluginmenu.favseasons(Handle)
        elif mode == 'collections':
            pluginmenu.collections(Handle, params['mediatype'], params.get('librarytag'))
        elif mode.startswith('inprogressmixed'):
            pluginmenu.get_inprogress_mixed(Handle)
        elif mode.startswith('continuewatching'):
            pluginmenu.get_continue_watching(Handle)
        elif mode == 'remotepictures':
            pluginmenu.remotepictures(Handle, params.get('position'))
        else:  # 'listing'
            pluginmenu.listing(Handle)

        client.send(sendOK)
        client.close()
        xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event browse", 0) # LOGDEBUG
        return

    PayloadLower = IncomingData[1].lower()
    PictureQuery = False

    if IncomingData[1].startswith('/picture/') or IncomingData[1].startswith('/delayed_content/picture'):
        PictureQuery = True

    if 'extrafanart' in PayloadLower or 'extrathumbs' in PayloadLower or 'extras/' in PayloadLower or PayloadLower.endswith('.edl') or PayloadLower.endswith('.txt') or PayloadLower.endswith('.vprj') or PayloadLower.endswith('.xml') or PayloadLower.endswith('/') or PayloadLower.endswith('.nfo') or (not PictureQuery and (PayloadLower.endswith('.bmp') or PayloadLower.endswith('.jpg') or PayloadLower.endswith('.ico') or PayloadLower.endswith('.png') or PayloadLower.endswith('.gif') or PayloadLower.endswith('.tbn') or PayloadLower.endswith('.tiff'))): # Unsupported queries used by Kodi
        client.send(sendNoContent)
    elif IncomingData[1].startswith("/delayed_content"): # workaround for low Kodi network timeout settings, for long running processes. "delayed_content" folder is actually a redirect to keep timeout below threshold
        ThreadId = IncomingData[1].split("/")[2]

        if not send_delayed_content(client, ThreadId):
            for _ in range(utils.curltimeouts * 10 - 2):
                if utils.sleep(0.1):
                    xbmc.log("EMBY.hooks.webservice: Delayed content interrupt, shutdown", 2) # LOGWARNING
                    client.send(sendNoContent)
                    break

                if send_delayed_content(client, ThreadId):
                    break
            else:
                xbmc.log("EMBY.hooks.webservice: Waiting for content", 0) # DEBUGINFO
                client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content/{ThreadId}\r\nContent-length: 0\r\n\r\n".encode())
    elif IncomingData[0] == "GET":
        http_Query(client, IncomingData[1])
    elif IncomingData[0] == "HEAD":
        if PictureQuery:
            http_Query(client, IncomingData[1])
        else:
            globals()["PayloadHeadRequest"] = IncomingData[1]
            client.send(sendOK)
    else:
        client.send(sendOK)

    client.close()
    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ]", 0) # LOGDEBUG

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
        add_playlist_item(client, ListItem, QueryData, Path, ThreadId)

    close_embydb(QueryData['ServerId'], ThreadId)

def send_BlankWAV(client, ThreadId):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if client:
        client.send(sendBlankWAV)
    else:
        globals()['DelayedContent'][ThreadId] = "blank"

def build_Path(QueryData, Data, Filename):
    if Filename:
        Filename = f"&{Filename}"

    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    if QueryData['MediasourceID']:
        Path = f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}MediaSourceId={QueryData['MediasourceID']}&PlaySessionId={QueryData['PlaySessionId']}&DeviceId={utils.EmbyServers[QueryData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken']}{Filename}"
    else:
        Path = f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}PlaySessionId={QueryData['PlaySessionId']}&DeviceId={utils.EmbyServers[QueryData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken']}{Filename}"

    return Path

def send_redirect(client, QueryData, Data, Filename, ThreadId):
    Path = build_Path(QueryData, Data, Filename)
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if "main.m3u8" in Data:
        MainM3U8 = utils.EmbyServers[QueryData['ServerId']].http.request({'type': "GET", 'handler': Path.replace(f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/" , "")}, False, True)
        MainM3U8Mod = MainM3U8.decode().replace("hls1/main/", f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/videos/{QueryData['EmbyID']}/hls1/main/").encode()
        SendData = f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(MainM3U8Mod)}\r\nContent-Type: text/plain\r\n\r\n".encode() + MainM3U8Mod
    else:
        SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-length: 0\r\n\r\n".encode()

    if ("LiveStreamId" in QueryData and QueryData["LiveStreamId"]) or "main.m3u8" in Data:
        utils.HTTPQueryDoublesFilter[QueryData['EmbyID']] = {'Payload': QueryData['Payload'], 'SendData': SendData}

    if client:
        client.send(SendData)
    else:
        globals()['DelayedContent'][ThreadId] = SendData

def http_Query(client, Payload):
    ThreadId = str(uuid.uuid4())

    for HTTPQueryDoubleFilter in list(utils.HTTPQueryDoublesFilter.values()):
        if Payload == HTTPQueryDoubleFilter['Payload']:
            client.send(HTTPQueryDoubleFilter['SendData'])
            xbmc.log(f"EMBY.hooks.webservice: Double query: {Payload}", 1) # LOGINFO
            return

    if Cancel:
        globals()["Cancel"] = False
        send_BlankWAV(client, ThreadId)
        player.Cancel()
        return

    # Workaround for invalid Kodi GET requests when played via widget
    if utils.usekodiworkaroundswidget:
        if not Payload.startswith('/picture/'):
            if Payload != PayloadHeadRequest:
                xbmc.log(f"Invalid GET request filtered: {Payload}", 2) # LOGWARNING
                client.send(sendNoContent)
                return

    # Load parameters from url query
    Folder = Payload.split("/")
    Temp = Payload[Payload.rfind("/") + 1:]
    Data = Temp.split("-")

    try:
        if Data[0] in EmbyIdMapping:
            EmbyType = EmbyIdMapping[Data[0]]
        else:
            EmbyType = None

        QueryData = {'MediasourceID': None, 'MediaSources': [], 'Payload': Payload, 'Type': MediaIdMapping[Data[0]], 'ServerId': Folder[2], 'EmbyID': Data[1], 'IntroStartPositionTicks': 0, 'IntroEndPositionTicks': 0, 'CreditsPositionTicks': 0, 'MediaType': Data[0], "EmbyType": EmbyType}

    except Exception as Error: # data from older versions are no compatible
        xbmc.log(f"EMBY.hooks.webservice: Incoming data (error) {Error}", 3) # LOGERROR
        xbmc.log(f"EMBY.hooks.webservice: Incoming data (error) {Payload}", 0) # LOGDEBUG
        client.send(sendNoContent)
        return

    # Waiting for Emby connection:
    if QueryData['ServerId'] not in utils.EmbyServers:
        xbmc.log(f"EMBY.hooks.webservice: Emby ServerId not found {QueryData['ServerId']}", 2) # LOGWARNING
        client.send(sendNoContent)
        return

    while not utils.EmbyServers[QueryData['ServerId']].EmbySession:
        xbmc.log(f"EMBY.hooks.webservice: Waiting for Emby connection... {QueryData['ServerId']}", 1) # LOGINFO

        if utils.sleep(1):
            xbmc.log(f"EMBY.hooks.webservice: Kodi shutdown while waiting for Emby connection... {QueryData['ServerId']}", 1) # LOGINFO
            client.send(sendNoContent)
            return

    if Data[0] == "p":  # Image/picture
        QueryData.update({'ImageIndex': Data[2], 'ImageType': EmbyArtworkIDs[Data[3]], 'ImageTag': Data[4]})

        if len(Data) >= 6:
            QueryData['Overlay'] = urllibparse.unquote(Data[5])
        else:
            QueryData['Overlay'] = ""
    elif Data[0] in ("e", "m", "M", "i", "T", "v"):  # Videos or iso
        QueryData.update({'MediasourceID': Data[2], 'KodiId': Data[3], 'KodiFileId': Data[4], 'ExternalSubtitle': Data[5], 'MediasourcesCount': int(Data[6]), 'IntroStartPositionTicks': int(Data[7]), 'IntroEndPositionTicks': int(Data[8]), 'CreditsPositionTicks': int(Data[9]), 'Remote': int(Data[10]), 'VideoCodec': Data[11], 'VideoBitrate': int(Data[12]), 'AudioCodec': Data[13], 'AudioBitrate': int(Data[14]), 'Filename': Data[15]})

        if "/dynamic/" in Payload:
            QueryData['MediasourcesCount'] = 1

        player.PlaylistRemoveItem = -1
    elif Data[0] in ("a", "A"):  # Audios
        QueryData.update({'Filename': Data[2]})
    elif Data[0] == "t":  # tv channel
        QueryData.update({'Filename': Data[2]})
    elif Data[0] == "c":  # e.g. channel
        QueryData.update({'MediasourceID': Data[2], 'Filename': Data[3]})
    else:
        QueryData.update({'MediasourceID': Data[2], 'Filename': Data[3]})

    if QueryData['ServerId'] not in utils.EmbyServers:
        client.send(sendOK)
        return

    if QueryData['Type'] == 'picture':
        DelayedContentId = Payload.replace("/", "")

        if Payload not in ArtworkCache[1]:
            globals()['DelayedContent'][DelayedContentId] = ""
            client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content/{DelayedContentId}\r\nContent-length: 0\r\n\r\n".encode())
            client.close()
            client = None
            xbmc.log(f"EMBY.hooks.webservice: Load artwork data: {Payload}", 0) # LOGDEBUG

            # Remove items from artwork cache if mem is over 100MB
            if ArtworkCache[0] > 100000000:
                for PayloadId, ArtworkCacheData in list(ArtworkCache[1].items()):
                    globals()['ArtworkCache'][0] -= ArtworkCacheData[2]
                    del globals()['ArtworkCache'][1][PayloadId]

                    if ArtworkCache[0] < 100000000:
                        break

            if not QueryData['Overlay']:
                BinaryData, ContentType, _ = utils.EmbyServers[QueryData['ServerId']].API.get_Image_Binary(QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['ImageTag'])
            else:
                BinaryData, ContentType = utils.image_overlay(QueryData['ImageTag'], QueryData['ServerId'], QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['Overlay'])

            ContentSize = len(BinaryData)
            globals()["ArtworkCache"][0] += ContentSize
            globals()["ArtworkCache"][1][Payload] = (f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {ContentSize}\r\nContent-Type: {ContentType}\r\n\r\n".encode(), BinaryData, ContentSize)
            del BinaryData
            globals()['DelayedContent'][DelayedContentId] = ArtworkCache[1][Payload][0] + ArtworkCache[1][Payload][1]
        else:
            xbmc.log(f"EMBY.hooks.webservice: Load artwork data from cache: {Payload}", 0) # LOGDEBUG
            client.send(ArtworkCache[1][Payload][0] + ArtworkCache[1][Payload][1])

            if DelayedContentId in DelayedContent:
                del globals()["DelayedContent"][DelayedContentId]

        return

    if QueryData['Type'] == 'specialaudio':
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"audio/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'], ThreadId)
        return

    if QueryData['Type'] == 'specialvideo':
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'], ThreadId)
        return

    if QueryData['Type'] == 'audio':
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"audio/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'], ThreadId)
        return

    if QueryData['Type'] == 'tvchannel':
        MediasourceID, LiveStreamId, PlaySessionId, Container = utils.EmbyServers[QueryData['ServerId']].API.open_livestream(QueryData['EmbyID'])

        if not Container:
            xbmc.log("EMBY.hooks.webservice: LiveTV no container info", 3) # LOGERROR
            client.send(sendNoContent)
            return

        QueryData.update({'MediasourceID': MediasourceID, 'LiveStreamId': LiveStreamId})
        set_QueuedPlayingItem(QueryData, PlaySessionId)

        if utils.transcode_livetv_video or utils.transcode_livetv_audio:
            if utils.transcode_livetv_video:
                TranscodingVideoCodec = utils.TranscodeFormatVideo
            else:
                TranscodingVideoCodec = "copy"

            if utils.transcode_livetv_audio:
                TranscodingAudioCodec = utils.TranscodeFormatAudio
            else:
                TranscodingAudioCodec = "copy"

            send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}&LiveStreamId={LiveStreamId}", "stream.ts", ThreadId)
        else:
            send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream?static=true&LiveStreamId={LiveStreamId}", f"stream.{Container}", ThreadId)

        return

    if QueryData['Type'] == 'channel':
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/main.m3u8", "stream.ts", ThreadId)
        return

    # Cinnemamode
    if ((utils.enableCinemaMovies and QueryData['Type'] == "movie") or (utils.enableCinemaEpisodes and QueryData['Type'] == "episode")) and not playerops.RemoteMode:
        if player.TrailerStatus == "READY":
            utils.EmbyServers[QueryData['ServerId']].http.Intros = []
            globals()["TrailerInitItem"] = [QueryData['Payload'], None]
            PlayTrailer = True

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                utils.EmbyServers[QueryData['ServerId']].http.load_Trailers(QueryData['EmbyID'])

            if utils.EmbyServers[QueryData['ServerId']].http.Intros:
                player.TrailerStatus = "PLAYING"
                globals()["TrailerInitItem"][1] = player.load_KodiItem("http_Query", QueryData['KodiId'], QueryData['Type'], None) # query path
                URL = utils.EmbyServers[QueryData['ServerId']].http.Intros[0]['Path']
                xbmc.log(f"EMBY.hooks.webservice: Trailer URL: {URL}", 0) # LOGDEBUG
                MediasourceID = utils.EmbyServers[QueryData['ServerId']].http.Intros[0]['MediaSources'][0]['Id']
                player.QueuedPlayingItem = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(utils.EmbyServers[QueryData['ServerId']].http.Intros[0]['Id']), 'MediaSourceId': MediasourceID, 'PlaySessionId': str(uuid.uuid4()).replace("-", ""), 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'IsMuted': player.Muted}, None, None, None, utils.EmbyServers[QueryData['ServerId']]]
                ListItem = listitem.set_ListItem(utils.EmbyServers[QueryData['ServerId']].http.Intros[0], QueryData['ServerId'], utils.AddonModePath + QueryData['Payload'][1:])
                del utils.EmbyServers[QueryData['ServerId']].http.Intros[0]
                xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
                player.playlistIndex = playerops.GetPlayerPosition(playerops.PlayerId)
                client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: {URL}\r\nConnection: close\r\nContent-length: 0\r\n\r\n".encode())
                utils.XbmcPlayer.updateInfoTag(ListItem)
                return

        if player.TrailerStatus == "CONTENT":
            utils.XbmcPlayer.updateInfoTag(TrailerInitItem[1])
            player.TrailerStatus = "READY"

    globals()["PayloadHeadRequest"] = ""

    # Play Kodi synced item
    if QueryData['KodiId']:  # Item synced to Kodi DB
        if QueryData['MediasourcesCount'] == 1 or playerops.RemoteMode:
            if QueryData['MediaType'] == 'i':
                LoadISO(QueryData, 0, client, ThreadId)
                return

            LoadData(0, QueryData, client, ThreadId)
            return

        # Multiversion
        globals()['DelayedContent'][ThreadId] = ""
        client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content/{ThreadId}\r\nContent-length: 0\r\n\r\n".encode())
        client.close()
        client = None
        Selection = []
        QueryData['MediaSources'] = open_embydb(QueryData['ServerId'], ThreadId).get_mediasource(QueryData['EmbyID'])
        close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input

        for Data in QueryData['MediaSources']:
            Selection.append(f"{Data[4]} - {utils.SizeToText(float(Data[5]))} - {Data[3]}")

        MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

        if MediaIndex == -1:
            globals()["Cancel"] = True
            send_BlankWAV(client, ThreadId)
            return

        # check if multiselection must be forced as native
        if QueryData['MediaSources'][MediaIndex][3].lower().endswith(".iso"):
            LoadISO(QueryData, MediaIndex, client, ThreadId)
            return

        QueryData['MediasourceID'] = QueryData['MediaSources'][MediaIndex][2]
        LoadData(MediaIndex, QueryData, client, ThreadId)
        return

    SubTitlesAdd(0, QueryData, ThreadId)

    if IsTranscoding(QueryData):
        URL = GETTranscodeURL(False, False, QueryData)
    else:
        URL = f"videos/{QueryData['EmbyID']}/stream?static=true"

    set_QueuedPlayingItem(QueryData, None)
    send_redirect(client, QueryData, URL, QueryData['Filename'], ThreadId)
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
    ExternalSubtitle = False

    for Data in Subtitles:
        if Data[6]:
            CounterSubTitle += 1
            ExternalSubtitle = True

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
                Path = f"{utils.FolderEmbyTemp}{utils.PathToFilenameReplaceSpecialCharecters(f'{CounterSubTitle}.{SubtileLanguage}.{Data[3]}')}"
                utils.writeFileBinary(Path, BinaryData)

                if DefaultVideoSettings["SubtitlesLanguage"].lower() in Data[5].lower():
                    DefaultSubtitlePath = Path

                    if DefaultVideoSettings["SubtitlesLanguage"].lower() == "forced_only" and "forced" in Data[5].lower():
                        DefaultSubtitlePath = Path
                    else:
                        playerops.AddSubtitle(Path)
                else:
                    playerops.AddSubtitle(Path)

    if ExternalSubtitle:
        if DefaultSubtitlePath:
            playerops.AddSubtitle(DefaultSubtitlePath)

        playerops.SetSubtitle(EnableSubtitle)

def LoadData(MediaIndex, QueryData, client, ThreadId):
    if MediaIndex == 0:
        Transcoding = IsTranscoding(QueryData)  # add codec from videostreams, Bitrate (from file)

        if not Transcoding:
            if QueryData['ExternalSubtitle'] == "1":
                SubTitlesAdd(0, QueryData, ThreadId)
                close_embydb(QueryData['ServerId'], ThreadId)

            set_QueuedPlayingItem(QueryData, None)
            URL = f"videos/{QueryData['EmbyID']}/stream?static=true"

            if QueryData['Remote']:  # remote content -> verify source
                status_code = utils.EmbyServers[QueryData['ServerId']].API.get_stream_statuscode(QueryData['EmbyID'], QueryData['MediasourceID'])
                xbmc.log(f"EMBY.hooks.webservice: Remote content verification: {status_code}", 1) # LOGINFO

                if status_code != 200:
                    send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/main.m3u8?VideoCodec={utils.TranscodeFormatVideo}&AudioCodec={utils.TranscodeFormatAudio}&TranscodeReasons=DirectPlayError", QueryData['Filename'], ThreadId)
                    return

            send_redirect(client, QueryData, URL, QueryData['Filename'], ThreadId)
            return
    else:
        VideoStreams = open_embydb(QueryData['ServerId'], ThreadId).get_videostreams(QueryData['EmbyID'], MediaIndex)
        AudioStreams = open_embydb(QueryData['ServerId'], ThreadId).get_AudioStreams(QueryData['EmbyID'], MediaIndex)

        if not VideoStreams or not AudioStreams:
            xbmc.log(f"EMBY.hooks.webservice: Invalid itemid: {QueryData['EmbyID']}", 3) # LOGERROR
            send_BlankWAV(client, ThreadId)
            close_embydb(QueryData['ServerId'], ThreadId)
            return

        if VideoStreams[0][4]:
            VideoBitrate = VideoStreams[0][4]
        else:
            VideoBitrate = 0

        if AudioStreams[0][5]:
            AudioBitrate = AudioStreams[0][5]
        else:
            AudioBitrate = 0

        QueryData.update({'KodiId': str(embydb[ThreadId].get_KodiId_by_EmbyId_EmbyType(QueryData['EmbyID'], QueryData['EmbyType'])), 'VideoBitrate': int(VideoBitrate), 'VideoCodec': VideoStreams[0][3], 'AudioCodec': AudioStreams[0][4], 'AudioBitrate': int(AudioBitrate)})
        Transcoding = IsTranscoding(QueryData)

    if Transcoding:
        AudioStreams = open_embydb(QueryData['ServerId'], ThreadId).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
        Subtitles = embydb[ThreadId].get_Subtitles(QueryData['EmbyID'], MediaIndex)
        SubtitleIndex = -1
        AudioIndex = -1

        if len(AudioStreams) > 1 and utils.transcode_select_audiostream:
            Selection = []

            for Data in AudioStreams:
                Selection.append(Data[3])

            close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input
            AudioIndex = utils.Dialog.select(heading="Select Audio Stream:", list=Selection)

        if len(Subtitles) >= 1:
            Selection = ["none"]

            for Data in Subtitles:
                Selection.append(Data[5])

            close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input
            SubtitleIndex = utils.Dialog.select(heading=utils.Translate(33484), list=Selection) - 1

        if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0:  # No change, just transcoding
            URL = GETTranscodeURL(False, False, QueryData)
            set_QueuedPlayingItem(QueryData, None)
            send_redirect(client, QueryData, URL, QueryData['Filename'], ThreadId)
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

        URL = GETTranscodeURL(str(AudioStream[2]), SubtitleStream, QueryData)
    else:  # stream
        URL = f"videos/{QueryData['EmbyID']}/stream?static=true"

    set_QueuedPlayingItem(QueryData, None)

    if "3d" in MediaSource[4].lower():
        # inject new playlist item (not update curerent playlist item to initiate 3d selection popup msg)
        Path = build_Path(QueryData, URL, Filename)
        ListItem = player.load_KodiItem("UpdateItem", QueryData['KodiId'], QueryData['Type'], Path)

        if not ListItem:
            client.send(sendOK)
            close_embydb(QueryData['ServerId'], ThreadId)
            return

        add_playlist_item(client, ListItem, QueryData, Path, ThreadId)
        close_embydb(QueryData['ServerId'], ThreadId)
        return

    SubTitlesAdd(MediaIndex, QueryData, ThreadId)
    send_redirect(client, QueryData, URL, Filename, ThreadId)
    close_embydb(QueryData['ServerId'], ThreadId)

def GETTranscodeURL(Audio, Subtitle, QueryData):
    TranscodingAudioBitrate = f"&AudioBitrate={QueryData['AudioBitrate']}"
    TranscodingVideoBitrate = f"&VideoBitrate={QueryData['VideoBitrate']}"

    if Subtitle:
        Subtitle = f"&SubtitleStreamIndex={Subtitle}"
    else:
        Subtitle = ""

    if Audio:
        Audio = f"&AudioStreamIndex={Audio}"
    else:
        Audio = ""

    if 'VideoCodecNotSupported' in QueryData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in QueryData['TranscodeReasons']:
        TranscodingVideoCodec = f"&VideoCodec={utils.TranscodeFormatVideo}"
    else:
        TranscodingVideoCodec = "&VideoCodec=copy"

    if 'AudioCodecNotSupported' in QueryData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in QueryData['TranscodeReasons']:
        TranscodingAudioCodec = f"&AudioCodec={utils.TranscodeFormatAudio}"
    else:
        TranscodingAudioCodec = "&AudioCodec=copy"

    return f"videos/{QueryData['EmbyID']}/main.m3u8?TranscodeReasons={QueryData['TranscodeReasons']}{TranscodingVideoCodec}{TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}{Audio}{Subtitle}"

def IsTranscoding(QueryData):
    if utils.transcode_h264 and QueryData['VideoCodec'] == "h264" or utils.transcode_hevc and QueryData['VideoCodec'] == "hevc" or utils.transcode_av1 and QueryData['VideoCodec'] == "av1" or utils.transcode_vp8 and QueryData['VideoCodec'] == "vp8" or utils.transcode_vp9 and QueryData['VideoCodec'] == "vp9" or utils.transcode_wmv3 and QueryData['VideoCodec'] == "wmv3" or utils.transcode_mpeg4 and QueryData['VideoCodec'] == "mpeg4" or utils.transcode_mpeg2video and QueryData['VideoCodec'] == "mpeg2video" or utils.transcode_mjpeg and QueryData['VideoCodec'] == "mjpeg" or utils.transcode_msmpeg4v3 and QueryData['VideoCodec'] == "msmpeg4v3":   #utils.transcodeAac:
        QueryData['TranscodeReasons'] = "VideoCodecNotSupported"

    if utils.transcode_aac and QueryData['AudioCodec'] == "aac" or utils.transcode_mp3 and QueryData['AudioCodec'] == "mp3" or utils.transcode_mp2 and QueryData['AudioCodec'] == "mp2" or utils.transcode_dts and QueryData['AudioCodec'] == "dts" or utils.transcode_ac3 and QueryData['AudioCodec'] == "ac3" or utils.transcode_eac3 and QueryData['AudioCodec'] == "eac3" or utils.transcode_pcm_mulaw and QueryData['AudioCodec'] == "pcm_mulaw" or utils.transcode_pcm_s24le and QueryData['AudioCodec'] == "pcm_s24le" or utils.transcode_vorbis and QueryData['AudioCodec'] == "vorbis" or utils.transcode_wmav2 and QueryData['AudioCodec'] == "wmav2" or utils.transcode_ac4 and QueryData['AudioCodec'] == "ac4":   #utils.transcodeAac:
        if 'TranscodeReasons' in QueryData:
            QueryData['TranscodeReasons'] += ",AudioCodecNotSupported"
        else:
            QueryData['TranscodeReasons'] = "AudioCodecNotSupported"

    if QueryData['VideoBitrate'] >= utils.videoBitrate:
        if 'TranscodeReasons' in QueryData:
            QueryData['TranscodeReasons'] += ",ContainerBitrateExceedsLimit"
            QueryData.update({'VideoBitrate': utils.videoBitrate, 'AudioBitrate': utils.audioBitrate})
        else:
            QueryData.update({'TranscodeReasons': "ContainerBitrateExceedsLimit", 'VideoBitrate': utils.videoBitrate, 'AudioBitrate': utils.audioBitrate})

    return bool('TranscodeReasons' in QueryData)

def add_playlist_item(client, ListItem, QueryData, Path, ThreadId):
    set_QueuedPlayingItem(QueryData, None)
    player.replace_playlist_listitem(ListItem, Path)
    send_BlankWAV(client, ThreadId)

def send_delayed_content(client, DelayedContentId):
    if DelayedContentId in DelayedContent:
        if DelayedContent[DelayedContentId]:
            xbmc.log(f"EMBY.hooks.webservice: Content available: {DelayedContentId}", 0) # DEBUGINFO

            if DelayedContent[DelayedContentId] == "blank":
                send_BlankWAV(client, DelayedContentId)
            else:
                client.send(DelayedContent[DelayedContentId])

                if DelayedContentId in DelayedContent: # check agsin (timing)
                    del globals()["DelayedContent"][DelayedContentId]

            return True
    else:
        xbmc.log("EMBY.hooks.webservice: Delayed content not found", 3) # LOGERROR
        client.send(sendNoContent)
        return True

    return False

def set_QueuedPlayingItem(QueryData, PlaySessionId):
    if not PlaySessionId:
        QueryData['PlaySessionId'] = str(uuid.uuid4()).replace("-", "")
    else:
        QueryData['PlaySessionId'] = PlaySessionId

    if 'LiveStreamId' in QueryData:
        player.QueuedPlayingItem = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(QueryData['EmbyID']), 'MediaSourceId': QueryData['MediasourceID'], 'PlaySessionId': QueryData['PlaySessionId'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'IsMuted': player.Muted, "LiveStreamId": QueryData['LiveStreamId']}, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'], utils.EmbyServers[QueryData['ServerId']]]
    else:
        player.QueuedPlayingItem = [{'CanSeek': True, 'QueueableMediaTypes': "Video,Audio", 'IsPaused': False, 'ItemId': int(QueryData['EmbyID']), 'MediaSourceId': QueryData['MediasourceID'], 'PlaySessionId': QueryData['PlaySessionId'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'IsMuted': player.Muted}, QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'], utils.EmbyServers[QueryData['ServerId']]]

def init_additional_modules():
    # Late imports to start the socket as fast as possible
    xbmc.log("EMBY.hooks.webservice: -->[ Init ]", 1) # LOGINFO
    globals()["urllibparse"] = __import__('urllib.parse', globals(), locals(), ('parse',), 0)
    globals()["dbio"] = __import__('database.dbio', globals(), locals(), ('dbio',), 0)
    globals()["listitem"] = __import__('emby.listitem', globals(), locals(), ('listitem',), 0)
    globals()["utils"] = __import__('helper.utils', globals(), locals(), ('utils',), 0)
    globals()["context"] = __import__('helper.context', globals(), locals(), ('context',), 0)
    globals()["playerops"] = __import__('helper.playerops', globals(), locals(), ('playerops',), 0)
    globals()["pluginmenu"] = __import__('helper.pluginmenu', globals(), locals(), ('pluginmenu',), 0)
    globals()["player"] = __import__('helper.player', globals(), locals(), ('player',), 0)
    xmls = __import__('helper.xmls', globals(), locals(), ('xmls',), 0)
    globals()["DefaultVideoSettings"] = xmls.load_defaultvideosettings()
    globals()["ModulesLoaded"] = True
    globals()["KeyBoard"] = xbmc.Keyboard()
    xbmc.log("EMBY.hooks.webservice: --<[ Init ]", 1) # LOGINFO

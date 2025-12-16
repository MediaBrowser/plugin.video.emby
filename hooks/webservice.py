from _thread import allocate_lock
from urllib.parse import parse_qsl
import uuid
import _socket
import xbmc
from hooks import favorites
from database import dbio
from emby import metadata
from helper import utils, context, playerops, pluginmenu, player, xmls
DefaultVideoSettings = xmls.load_defaultvideosettings()
SubtitlesLanguageDefault = DefaultVideoSettings.get("SubtitlesLanguage", "").lower()
EnableSubtitleDefault = DefaultVideoSettings.get('ShowSubtitles', False)
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\n\r\n'.encode()
sendNotFound = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\n\r\n'.encode()
sendHeadPicture = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: image/unknown\r\n\r\n'.encode()
sendHeadAudio = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: audio/unknown\r\n\r\n'.encode()
sendHeadVideo = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: video/unknown\r\n\r\n'.encode()
sendHeadVideoHLS = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: application/vnd.apple.mpegurl\r\n\r\n'.encode()
sendBlankWAV = ('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 45\r\nContent-Type: audio/wav\r\n\r\n'.encode(), b'\x52\x49\x46\x46\x25\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x74\x00\x00\x00\x00') # used to "stop" playback by sending a WAV file with silence. File is valid, so Kodi will not raise an error message. Data are native blank wave file
Running = False
Socket = None
KeyBoard = xbmc.Keyboard()
DelayedContent = {}
DelayedContentLock = allocate_lock()
EmbyIdCurrentlyPlaying = 0
MaxWorkers = utils.WebserviceWorkers
WorkerQueues = ()
xbmc.log(f"EMBY.hooks.webservice: Number of workers {MaxWorkers}", 1) # LOGINFO

for Counter in range(MaxWorkers):
    WorkerQueues += ([allocate_lock(), False],) # ([Lock, Socket FD],...)

def start():
    globals()["Running"] = True

    try: # intercept multiple start by different threads (just precaution)
        LocalSocket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        LocalSocket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        LocalSocket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        LocalSocket.bind(('127.0.0.1', 57342))
        globals()['Socket'] = LocalSocket
    except Exception as Error:
        xbmc.log(f"EMBY.hooks.webservice: Socket start (error) {Error}", 1) # LOGINFO
        return False

    xbmc.log("EMBY.hooks.webservice: Start", 1) # LOGINFO

    # preload simultan workers
    for WorkerNumber in range(MaxWorkers):
        worker_Queue_release(WorkerNumber) # could be triggered multiple times without stopping before (e.g. sleep)
        WorkerQueues[WorkerNumber][0].acquire()
        utils.start_thread(worker_Queues, (WorkerNumber,))

    utils.start_thread(Listen, ())
    return True

def close():
    if Running:
        globals()["Running"] = False

        try:
            Socket.close()
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 1) # LOGINFO

        for WorkerNumber in range(MaxWorkers):
            WorkerQueues[WorkerNumber][1] = False
            worker_Queue_release(WorkerNumber)

        xbmc.log("EMBY.hooks.webservice: Shutdown webservice", 1) # LOGINFO
        xbmc.log(f"EMBY.hooks.webservice: DelayedContent queue size: {len(DelayedContent)}", 0) # LOGDEBUG

def Listen():
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ webservice/57342 ]", 0) # LOGDEBUG
    Socket.listen()
    Socket.settimeout(1)

    while not utils or not utils.SystemShutdown and Running:
        try:
            fd, _ = Socket._accept()
        except:
            continue

        for WorkerNumber in range(MaxWorkers):
            if not WorkerQueues[WorkerNumber][1]:
                WorkerQueues[WorkerNumber][1] = fd
                worker_Queue_release(WorkerNumber)
                break
        else:
            xbmc.log(f"EMBY.hooks.webservice: New thread file descriptor: {fd}", 1) # LOGINFO
            utils.start_thread(worker_Query, (fd,))

    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ webservice/57342 ]", 0) # LOGDEBUG

def worker_Queue_release(WorkerNumber):
    try:
        WorkerQueues[WorkerNumber][0].release()
    except:
        pass

def worker_Queues(WorkerNumber):  # thread by caller
    xbmc.log(f"EMBY.hooks.webservice: THREAD: --->[ worker_Queues/{WorkerNumber} ]", 0) # LOGDEBUG

    while Running:
        WorkerQueues[WorkerNumber][0].acquire()

        if not Running or not WorkerQueues[WorkerNumber][1]:
            worker_Queue_release(WorkerNumber)
            break

        xbmc.log(f"EMBY.hooks.webservice: Worker queue {WorkerNumber}, file descriptor: {WorkerQueues[WorkerNumber][1]}", 0) # LOGDEBUG
        worker_Query(WorkerQueues[WorkerNumber][1])
        globals()['WorkerQueues'][WorkerNumber][1] = False

    xbmc.log(f"EMBY.hooks.webservice: THREAD: ---<[ worker_Queues/{WorkerNumber} ]", 0) # LOGDEBUG

def worker_Query(fd):  # thread by caller
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ worker_Query ]", 0) # LOGDEBUG
    client = _socket.socket(fileno=fd)
    client.settimeout(None)
    data = client.recv(16384).decode()
    xbmc.log(f"EMBY.hooks.webservice: Incoming Data: {data}", 0) # LOGDEBUG
    IncomingData = data.split(' ')

    if IncomingData[0] in ("PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE", "DELETE", "LOCK", "UNLOCK"): # webdav methodS, currently not supported
        client.send(sendNotFound)
        return

    # Skip item e.g. used for cinemamode
    if IncomingData[1] in player.SkipItem:
        xbmc.log(f"EMBY.hooks.webservice: Skip item: {IncomingData[1]}", 1) # LOGINFO
        client.send(sendNotFound)
        client.close()
        return

    # events by event.py
    if IncomingData[0] == "EVENT":
        args = IncomingData[1].split(";")

        if args[1] == "specials":
            client.send(sendOK)
            client.close()
            context.specials()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event specials", 0) # LOGDEBUG
            return

        if args[1] == "multiversion":
            client.send(sendOK)
            client.close()
            context.multiversion()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event multiversion", 0) # LOGDEBUG
            return

        if args[1] == "playrandom":
            client.send(sendOK)
            client.close()
            context.playrandom()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event playrandom", 0) # LOGDEBUG
            return

        if args[1] == "gotoshow":
            client.send(sendOK)
            client.close()
            context.gotoshow()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event gotoshow", 0) # LOGDEBUG
            return

        if args[1] == "gotoseason":
            client.send(sendOK)
            client.close()
            context.gotoseason()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event gotoseason", 0) # LOGDEBUG
            return

        if args[1] == "gotoalbum":
            client.send(sendOK)
            client.close()
            context.gotoalbum()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event gotoalbum", 0) # LOGDEBUG
            return

        if args[1] == "gotoartist":
            client.send(sendOK)
            client.close()
            context.gotoartist()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event gotoartist", 0) # LOGDEBUG
            return

        if args[1] == "similarshow":
            client.send(sendOK)
            client.close()
            context.similar("Series")
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event similarshow", 0) # LOGDEBUG
            return

        if args[1] == "similarartist":
            client.send(sendOK)
            client.close()
            context.similar("Artist")
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event similarartist", 0) # LOGDEBUG
            return

        if args[1] == "similaralbum":
            client.send(sendOK)
            client.close()
            context.similar("MusicAlbum")
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event similaralbum", 0) # LOGDEBUG
            return

        if args[1] == "similarmusicvideo":
            client.send(sendOK)
            client.close()
            context.similar("MusicVideo")
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event similarmusicvideo", 0) # LOGDEBUG
            return

        if args[1] == "similarmovie":
            client.send(sendOK)
            client.close()
            context.similar("Movie")
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event similarmovie", 0) # LOGDEBUG
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

        if args[1] == "remoteplay":
            client.send(sendOK)
            client.close()
            context.remoteplay()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event remoteplay", 0) # LOGDEBUG
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

        if args[1] == "settings":
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event settings", 0) # LOGDEBUG
            return

        # no delay
        params = args[2]

        if params.endswith("/&reload="):
            params = params[:-9]
        elif params.endswith("/"):
            params = params[:-1]

        Handle = args[1]
        params = dict(parse_qsl(params[1:]))
        mode = params.get('mode', "")
        ServerId = params.get('server', "")

        if mode == 'search':  # Simple commands
            client.send(sendOK)
            client.close()
#            xbmc.executebuiltin('Dialog.Close(all,true),true')
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

                # Delete cache from previous search
                if "All" in utils.QueryCache:
                    if CacheId1 in utils.QueryCache["All"]:
                        utils.QueryCache["All"][CacheId1][0] = False
                    elif CacheId2 in utils.QueryCache["All"]:
                        utils.QueryCache["All"][CacheId2][0] = False

                utils.ActivateWindow("videos", f"plugin://plugin.service.emby-next-gen/?id=0&mode=browse&query=Search&server={ServerId}&parentid=0&content=All&libraryid=0")

            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event search", 0) # LOGDEBUG
            return

        if mode == 'settings':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')
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
                utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False, time=utils.displayMessage)
            else:
                pluginmenu.cache_textures()

            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event texturecache", 0) # LOGDEBUG
            return

        if mode == 'databasereset':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.databasereset(favorites)
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event databasereset", 0) # LOGDEBUG
            return

        if mode == 'nodesreset':  # Simple commands
            client.send(sendOK)
            client.close()
            utils.nodesreset()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event nodesreset", 0) # LOGDEBUG
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

            if query not in ("NodesDynamic", "NodesSynced"):
                if not wait_for_Embyserver(client, ServerId):
                    client.close()
                    return

            if query:
                pluginmenu.browse(Handle, params.get('id'), query, params.get('parentid'), params.get('content'), ServerId, params.get('libraryid'), params.get('contentsupported', ""))
        elif mode == 'playlist':
            pluginmenu.get_playlist(Handle, ServerId, params['mediatype'], params.get('id', ""))
        elif mode == 'nextepisodes':
            pluginmenu.get_next_episodes(Handle, params['libraryname'])
        elif mode == 'nextepisodesplayed':
            pluginmenu.get_next_episodes_played(Handle, params['libraryname'])
        elif mode == 'favepisodes':
            pluginmenu.favepisodes(Handle)
        elif mode == 'favseasons':
            pluginmenu.favseasons(Handle)
        elif mode == 'collections':
            pluginmenu.collections(Handle, params['mediatype'], params.get('libraryname'))
        elif mode == 'inprogressmixed':
            pluginmenu.get_inprogress_mixed(Handle)
        elif mode == 'recentlyaddedmusicvideoalbums':
            pluginmenu.get_recentlyadded_musicvideosalbums(Handle, params.get('libraryname'))
        elif mode == 'remotepictures':
            pluginmenu.remotepictures(Handle, params.get('position'))
        else:  # 'listing'
            pluginmenu.listing(Handle, args[0])

        client.send(sendOK)
        client.close()
        xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event browse", 0) # LOGDEBUG
        return

    # Detect content type
    isPicture = False
    isAudio = False
    isVideo = False
    isDelayedContent = IncomingData[1].startswith("/delayed_content/")
    Payload = IncomingData[1].replace("/delayed_content", "")

    if "/picture/" in IncomingData[1]:
        isPicture = True
    elif "/audio/" in IncomingData[1]:
        isAudio = True
    else:
        isVideo = True

    PayloadLower = Payload.lower()

    if PayloadLower.endswith('/') or 'extrafanart' in PayloadLower or 'extrathumbs' in PayloadLower or 'extras/' in PayloadLower or PayloadLower.endswith('.edl') or PayloadLower.endswith('index.bdmv') or PayloadLower.endswith('index.bdm') or PayloadLower.endswith('.txt') or PayloadLower.endswith('.vprj') or PayloadLower.endswith('.xml') or PayloadLower.endswith('.nfo') or (not isPicture and (PayloadLower.endswith('.bmp') or PayloadLower.endswith('.jpg') or PayloadLower.endswith('.jpeg') or PayloadLower.endswith('.ico') or PayloadLower.endswith('.png') or PayloadLower.endswith('.ifo') or PayloadLower.endswith('.gif') or PayloadLower.endswith('.tbn') or PayloadLower.endswith('.tiff'))): # Filter invalid requests
        client.send(sendNotFound)
    else: # Process request
        if IncomingData[0] == "GET":
            GetRequest(client, Payload, isDelayedContent, isPicture, isAudio, isVideo)
        elif IncomingData[0] == "HEAD":
            if isPicture:
                client.send(sendHeadPicture)
            elif isAudio:
                client.send(sendHeadAudio)
            else:
                if PayloadLower.startswith("/dynamic/"): # set hls mimetype, as content lookup requests are disabled -> listitem.setContentLookup(False)
                    client.send(sendHeadVideoHLS)
                else:
                    client.send(sendHeadVideo)
        else:
            xbmc.log("EMBY.hooks.webservice: Unknown method: {IncomingData[0]}", 1) # LOGINFO
            client.send(sendOK)

    client.close()
    del client
    del IncomingData
    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ]", 0) # LOGDEBUG

def LoadISO(MetaData, client): # native content
    player.MultiselectionDone = True
    Path = MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path']

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path'] = Path
    ListItem = player.load_KodiItem("LoadISO", MetaData['KodiId'], MetaData['Type'], Path)

    if not ListItem:
        client.send(sendOK)
    else:
        set_QueuedPlayingItem(MetaData, None)
        player.replace_playlist_listitem(ListItem, MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path'])
        set_DelayedContent(MetaData['Payload'], "blank")

def send_BlankWAV(client, Payload):
    utils.close_busyDialog()

    try:
        client.send(sendBlankWAV[0] + sendBlankWAV[1])
    except:
        set_DelayedContent(Payload, "blank")

def build_Path(MetaData, Data):
    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    if MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id']:
        Path = f"{utils.EmbyServers[MetaData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}MediaSourceId={MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id']}&PlaySessionId={MetaData['PlaySessionId']}&DeviceId={utils.EmbyServers[MetaData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[MetaData['ServerId']].ServerData['AccessToken']}"
    else:
        Path = f"{utils.EmbyServers[MetaData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}PlaySessionId={MetaData['PlaySessionId']}&DeviceId={utils.EmbyServers[MetaData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[MetaData['ServerId']].ServerData['AccessToken']}"

    return Path

def send_redirect(client, MetaData, Data):
    utils.close_busyDialog()

    if MetaData['isHttp'] and utils.followhttp:
        SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path']}\r\nContent-Length: 0\r\n\r\n".encode()
        utils.HTTPResponseCaches[MetaData['EmbyId']] = SendData
    else:
        Path = build_Path(MetaData, Data)

        if "main.m3u8" in Data:
            M3U8 = utils.EmbyServers[MetaData['ServerId']].API.get_m3u8(Path, MetaData['EmbyId'])
            HlsId = f"{MetaData['Payload']}{Data.replace('/', '')}embyhls.m3u8"
            Path = f"http://127.0.0.1:57342{HlsId}"
            utils.HTTPResponseCaches[MetaData['EmbyId']] = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(M3U8)}\r\nContent-Type: application/vnd.apple.mpegurl\r\n\r\n'.encode() + M3U8
            SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-Length: 0\r\n\r\n".encode()
        else:
            SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-Length: 0\r\n\r\n".encode()
            utils.HTTPResponseCaches[MetaData['EmbyId']] = SendData

    xbmc.log(f"EMBY.hooks.webservice: Send data: {SendData}", 0) # LOGDEBUG

    try:
        client.send(SendData)
    except:
        set_DelayedContent(MetaData['Payload'], SendData)

def GetRequest(client, Payload, isDelayedContent, isPicture, isAudio, isVideo):
    # Delayed contents are used for user inputs (selection box for e.g. multicontent versions, transcoding selection etc.)
    # workaround for low Kodi network timeout settings, for long running processes. "delayed_content" folder is actually a redirect to keep timeout below threshold
    if isDelayedContent:
        if not send_delayed_content(client, Payload):
            for _ in range(utils.curltimeouts * 10 - 2):
                if utils.sleep(0.1):
                    xbmc.log("EMBY.hooks.webservice: Delayed content interrupt, Kodi shutdown", 2) # LOGWARNING
                    client.send(sendNotFound)
                    break

                if send_delayed_content(client, Payload):
                    break
            else:
                xbmc.log("EMBY.hooks.webservice: Continue waiting for content, send another redirect", 0) # DEBUGINFO
                client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content{Payload}\r\nContent-Length: 0\r\n\r\n".encode())

        return

    # Load parameters from url request
    MetaData = metadata.load_MetaData(Payload, isPicture, isAudio)

    if not MetaData: # Invalid request
        client.send(sendNotFound)
        return

    # Use cached responses
    if MetaData['EmbyId'] in utils.HTTPResponseCaches:
        client.send(utils.HTTPResponseCaches[MetaData['EmbyId']])
        xbmc.log(f"EMBY.hooks.webservice: Cached response EmbyId: {MetaData['EmbyId']}", 1) # LOGINFO
        xbmc.log(f"EMBY.hooks.webservice: Cached response Payload: {utils.HTTPResponseCaches[MetaData['EmbyId']]}", 0) # LOGDEBUG
        return

    # Set player id
    if isVideo:
        player.PlaylistRemoveItem = -1
        player.set_PlayerId({"player": {"playerid": 1}})
    elif isAudio:
        player.set_PlayerId({"player": {"playerid": 0}})

    # Waiting for Emby connection:
    if not wait_for_Embyserver(client, MetaData['ServerId']):
        return

    try:
        while not utils.EmbyServers[MetaData['ServerId']].EmbySession:
            xbmc.log(f"EMBY.hooks.webservice: Waiting for Emby connection... {MetaData['ServerId']}", 1) # LOGINFO

            if utils.sleep(1):
                xbmc.log(f"EMBY.hooks.webservice: Kodi shutdown while waiting for Emby connection... {MetaData['ServerId']}", 1) # LOGINFO
                client.send(sendNotFound)
                return
    except: # could be triggered when server was removed -> MetaData['ServerId'] removed from utils.EmbyServers
        return

    if MetaData['Type'] == 'picture':
        xbmc.log(f"EMBY.hooks.webservice: Load artwork data into cache: {Payload}", 0) # LOGDEBUG

        if add_DelayedContent(MetaData, client):
            return

        xbmc.log(f"EMBY.hooks.webservice: Load artwork data from Emby: {Payload}", 0) # LOGDEBUG

        if not MetaData['Overlay']:
            BinaryData, ContentType, _ = utils.EmbyServers[MetaData['ServerId']].API.get_Image_Binary(MetaData['EmbyId'], MetaData['ImageType'], MetaData['ImageIndex'], MetaData['ImageTag'], False, False, False)
        else:
            BinaryData, ContentType, _ = utils.image_overlay(MetaData['ImageTag'], MetaData['ServerId'], MetaData['EmbyId'], MetaData['ImageType'], MetaData['ImageIndex'], MetaData['Overlay'], False, False)

        set_DelayedContent(MetaData['Payload'], f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BinaryData)}\r\nContent-Type: {ContentType}\r\n\r\n".encode() + BinaryData)
        xbmc.log(f"EMBY.hooks.webservice: Loaded Delayed Content for {Payload}", 0) # LOGDEBUG
        return

    if MetaData['Type'] == 'audio':
        set_QueuedPlayingItem(MetaData, None)
        send_redirect(client, MetaData, f"audio/{MetaData['EmbyId']}/stream?static=true")
        return

    globals()['EmbyIdCurrentlyPlaying'] = MetaData['EmbyId']

    if MetaData['Type'] == 'tvchannel':
        MediasourceId, LiveStreamId, PlaySessionId, Container = utils.EmbyServers[MetaData['ServerId']].API.open_livestream(MetaData['EmbyId'])

        if not Container:
            xbmc.log("EMBY.hooks.webservice: LiveTV no container info", 3) # LOGERROR
            client.send(sendNotFound)
            return

        MetaData['MediaSources'][0][0]['Id'] = MediasourceId
        MetaData['LiveStreamId'] = LiveStreamId
        set_QueuedPlayingItem(MetaData, PlaySessionId)

        if utils.transcode_livetv_video or utils.transcode_livetv_audio:
            TranscodingVideoBitrate = ""
            TranscodingAudioBitrate = ""

            if utils.transcode_livetv_video:
                TranscodingVideoCodec = utils.TranscodeFormatVideo
                TranscodingVideoBitrate = f"&VideoBitrate={utils.videoBitrate}"
            else:
                TranscodingVideoCodec = "copy"

            if utils.transcode_livetv_audio:
                TranscodingAudioCodec = utils.TranscodeFormatAudio
                TranscodingAudioBitrate = f"&AudioBitrate={utils.audioBitrate}"
            else:
                TranscodingAudioCodec = "copy"

            if LiveStreamId:
                send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}&LiveStreamId={LiveStreamId}{TranscodingVideoBitrate}{TranscodingAudioBitrate}")
            else:
                send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}")
        else:
            if LiveStreamId:
                send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream?static=true&LiveStreamId={LiveStreamId}")
            else:
                send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream?static=true")

        return

    if MetaData['Type'] == 'channel':
        set_QueuedPlayingItem(MetaData, None)
        send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/main.m3u8")
        return

    # Cinnemamode
    if not utils.RemoteMode and ((utils.enableCinemaMovies and MetaData['Type'] == "movie") or (utils.enableCinemaEpisodes and MetaData['Type'] == "episode")) and not player.TrailerStatus == "PLAYING":
        if not MetaData['isDynamic']:
            videoDB = dbio.DBOpenRO("video", "http_Query")
            Progress = videoDB.get_Progress_by_KodiType_KodiId(MetaData['Type'], MetaData['KodiId'])
            dbio.DBCloseRO("video", "http_Query")
        else:
            Progress = 0

        if not Progress and player.TrailerStatus == "READY":
            player.playlistIndex = playerops.GetPlayerPosition(1)
            player.TrailerStatus = "PLAYING"
            utils.EmbyServers[MetaData['ServerId']].http.Intros = []
            PlayTrailer = True

            if add_DelayedContent(MetaData, client):
                return

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                utils.EmbyServers[MetaData['ServerId']].http.load_Trailers(MetaData['EmbyId'])

                if utils.EmbyServers[MetaData['ServerId']].http.Intros:
                    utils.close_busyDialog()
                    set_DelayedContent(MetaData['Payload'], "blank")
                    player.play_Trailer(utils.EmbyServers[MetaData['ServerId']])

                    # skip incoming content queries, until intros finished playing
                    if player.playlistIndex == 0:
                        player.SkipItem = (Payload, )
                    elif player.playlistIndex != -1:
                        PlaylistItems = playerops.GetPlaylistItems(1)

                        if PlaylistItems:
                            player.SkipItem = (Payload, PlaylistItems[0]['file'].replace("/emby_addon_mode", "").replace("http://127.0.0.1:57342", "").replace("dav://127.0.0.1:57342", ""))
                        else:
                            player.SkipItem = (Payload, )

                    return

            utils.close_busyDialog()
            set_DelayedContent(MetaData['Payload'], f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: http://127.0.0.1:57342{Payload}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode())
            return

        if player.TrailerStatus == "CONTENT":
            player.TrailerStatus = "READY"

    if len(MetaData['MediaSources']) == 1 or utils.RemoteMode or (MetaData['MediaType'] in ("i", "v", "m") and not MetaData['isDynamic']): # no multiversion select for iso or movie/video -> Kodi takes care
        if MetaData['MediaType'] == 'i':
            if add_DelayedContent(MetaData, client):
                return

            LoadISO(MetaData, client)
            return

        LoadData(MetaData, client)
        return

    # Select multiversion content
    if metadata.MediaSourceContextMenu != -1: # Multiversion content played via contextmenu
        MetaData['SelectionIndexMediaSource'] = metadata.MediaSourceContextMenu
        metadata.MediaSourceContextMenu = -1
    elif utils.SelectDefaultVideoversion: # Autoselect mediasource by default version
        MetaData['SelectionIndexMediaSource'] = 0
    elif utils.AutoSelectHighestResolution: # Autoselect mediasource by highest resolution
        HighestResolution = 0
        MetaData['SelectionIndexMediaSource'] = 0

        for MediaSourceIndex, MediaSource in enumerate(MetaData['MediaSources']):
            if HighestResolution < MediaSource[1][0]['Width']:
                HighestResolution = MediaSource[1][0]['Width']
                MetaData['SelectionIndexMediaSource'] = MediaSourceIndex
    else: # Manual select mediasource
        if add_DelayedContent(MetaData, client):
            return

        Selection = []

        for MediaSource in MetaData['MediaSources']:
            Selection.append(f"{MediaSource[0]['Name']} - {utils.SizeToText(float(MediaSource[0]['Size']))} - {MediaSource[0]['Path']}")

        MetaData['SelectionIndexMediaSource'] = utils.Dialog.select(utils.Translate(33453), Selection)

        if MetaData['SelectionIndexMediaSource'] == -1: # Cancel
            set_DelayedContent(MetaData['Payload'], "blank")
            playerops.Stop(False, 1)
            return

    # check if multiselection must be forced as native
    if MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path'].lower().endswith(".iso"):
        LoadISO(MetaData, client)
        return

    LoadData(MetaData, client)
    return

# Load SRT subtitles
def SubTitlesAdd(MetaData):
    if not MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][3]:
        return

    CounterSubTitle = 0
    DefaultSubtitlePath = ""
    EnableSubtitle = False
    ExternalSubtitle = False

    for Subtitle in MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][3]:
        if Subtitle['external']:
            CounterSubTitle += 1
            ExternalSubtitle = True

            # Get Subtitle Settings
            if not MetaData['isDynamic']:
                videoDB = dbio.DBOpenRO("video", "http_Query")
                FileSettings = videoDB.get_FileSettings(MetaData['KodiFileId'])
                dbio.DBCloseRO("video", "http_Query")
            else:
                FileSettings = []

            if FileSettings:
                EnableSubtitle = bool(FileSettings[9])
            else:
                EnableSubtitle = EnableSubtitleDefault

            if Subtitle['language']:
                SubtileLanguage = Subtitle['language']
            else:
                SubtileLanguage = "undefined"

            BinaryData = utils.EmbyServers[MetaData['ServerId']].API.get_Subtitle_Binary(MetaData['EmbyId'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id'], Subtitle['Index'], Subtitle['Codec'])

            if MetaData['EmbyId'] != EmbyIdCurrentlyPlaying: # check if Kodi is still playing the same file
                del BinaryData
                return

            if BinaryData:
                SubtitleCodec = Subtitle['Codec']
                Path = f"{utils.FolderEmbyTemp}{utils.valid_Filename(f'{CounterSubTitle}.{SubtileLanguage}.{SubtitleCodec}')}"
                utils.writeFile(Path, BinaryData)
                del BinaryData

                if SubtitlesLanguageDefault in Subtitle['DisplayTitle'].lower():
                    DefaultSubtitlePath = Path

                    if SubtitlesLanguageDefault == "forced_only" and "forced" in Subtitle['DisplayTitle'].lower():
                        DefaultSubtitlePath = Path
                    else:
                        playerops.AddSubtitle(Path)
                else:
                    playerops.AddSubtitle(Path)

    if ExternalSubtitle:
        if DefaultSubtitlePath:
            playerops.AddSubtitle(DefaultSubtitlePath)

        playerops.SetSubtitle(EnableSubtitle)

def LoadData(MetaData, client):
    # Check transcoding
    if MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][1] and MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][2]:
        VideoCodec = MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][1][MetaData['SelectionIndexVideoStream']]['Codec']
        AudioCodec = MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][2][MetaData['SelectionIndexAudioStream']]['Codec']
        VideoResolutionWidth = MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][1][MetaData['SelectionIndexVideoStream']]['Width']

        if utils.transcode_h264 and VideoCodec == "h264":
            if utils.transcode_h264_resolution:
                if VideoResolutionWidth > utils.transcode_h264_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_hevc and VideoCodec == "hevc":
            if utils.transcode_hevc_resolution:
                if VideoResolutionWidth > utils.transcode_hevc_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_av1 and VideoCodec == "av1":
            if utils.transcode_av1_resolution:
                if VideoResolutionWidth > utils.transcode_av1_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_vp8 and VideoCodec == "vp8":
            if utils.transcode_vp8_resolution:
                if VideoResolutionWidth > utils.transcode_vp8_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_vp9 and VideoCodec == "vp9":
            if utils.transcode_vp9_resolution:
                if VideoResolutionWidth > utils.transcode_vp9_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_wmv3 and VideoCodec == "wmv3":
            if utils.transcode_wmv3_resolution:
                if VideoResolutionWidth > utils.transcode_wmv3_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_mpeg4 and VideoCodec == "mpeg4":
            if utils.transcode_mpeg4_resolution:
                if VideoResolutionWidth > utils.transcode_mpeg4_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_mpeg2video and VideoCodec == "mpeg2video":
            if utils.transcode_mpeg2video_resolution:
                if VideoResolutionWidth > utils.transcode_mpeg2video_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_mjpeg and VideoCodec == "mjpeg":
            if utils.transcode_mjpeg_resolution:
                if VideoResolutionWidth > utils.transcode_mjpeg_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_msmpeg4v3 and VideoCodec == "msmpeg4v3":
            if utils.transcode_msmpeg4v3_resolution:
                if VideoResolutionWidth > utils.transcode_msmpeg4v3_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_msmpeg4v2 and VideoCodec == "msmpeg4v2":
            if utils.transcode_msmpeg4v2_resolution:
                if VideoResolutionWidth > utils.transcode_msmpeg4v2_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_vc1 and VideoCodec == "vc1":
            if utils.transcode_vc1_resolution:
                if VideoResolutionWidth > utils.transcode_vc1_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"
        elif utils.transcode_prores and VideoCodec == "prores":
            if utils.transcode_prores_resolution:
                if VideoResolutionWidth > utils.transcode_prores_resolution:
                    MetaData['TranscodeReasons'] = "VideoResolutionNotSupported"
            else:
                MetaData['TranscodeReasons'] = "VideoCodecNotSupported"

        if utils.transcode_aac and AudioCodec == "aac" or utils.transcode_mp3 and AudioCodec == "mp3" or utils.transcode_mp2 and AudioCodec == "mp2" or utils.transcode_dts and AudioCodec == "dts" or utils.transcode_ac3 and AudioCodec == "ac3" or utils.transcode_eac3 and AudioCodec == "eac3" or utils.transcode_pcm_mulaw and AudioCodec == "pcm_mulaw" or utils.transcode_pcm_s24le and AudioCodec == "pcm_s24le" or utils.transcode_vorbis and AudioCodec == "vorbis" or utils.transcode_wmav2 and AudioCodec == "wmav2" or utils.transcode_ac4 and AudioCodec == "ac4" or utils.transcode_pcm_s16le and AudioCodec == "pcm_s16le" or utils.transcode_aac_latm and AudioCodec == "aac_latm" or utils.transcode_dtshd_hra and AudioCodec == "dtshd_hra" or utils.transcode_dtshd_ma and AudioCodec == "dtshd_ma" or utils.transcode_truehd and AudioCodec == "truehd" or utils.transcode_opus and AudioCodec == "opus":
            if 'TranscodeReasons' in MetaData:
                MetaData['TranscodeReasons'] += ",AudioCodecNotSupported"
            else:
                MetaData['TranscodeReasons'] = "AudioCodecNotSupported"

        if MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][1][MetaData['SelectionIndexVideoStream']]['BitRate'] >= utils.videoBitrate:
            if 'TranscodeReasons' in MetaData:
                MetaData['TranscodeReasons'] += ",ContainerBitrateExceedsLimit"
            else:
                MetaData.update({'TranscodeReasons': "ContainerBitrateExceedsLimit"})

    # Stream content
    if 'TranscodeReasons' not in MetaData:
        if MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['IsRemote']:  # remote content -> verify source
            StatusCode = utils.EmbyServers[MetaData['ServerId']].API.get_stream_statuscode(MetaData['EmbyId'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id'])
            xbmc.log(f"EMBY.hooks.webservice: Remote content verification: {StatusCode}", 1) # LOGINFO

            if StatusCode != 200:
                set_QueuedPlayingItem(MetaData, None)
                send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/main.m3u8?VideoCodec={utils.TranscodeFormatVideo}&AudioCodec={utils.TranscodeFormatAudio}&TranscodeReasons=DirectPlayError")
                return

        utils.start_thread(SubTitlesAdd, (MetaData,))
        set_QueuedPlayingItem(MetaData, None)
        send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream?static=true")
        return

    # Transcoding content
    if len(MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][2]) > 1 and utils.transcode_select_audiostream:
        if add_DelayedContent(MetaData, client):
            return

        Selection = []

        for AudioStreams in MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][2]:
            Selection.append(AudioStreams['DisplayTitle'])

        MetaData['SelectionIndexAudioStream'] = utils.Dialog.select(heading=utils.Translate(33642), list=Selection)

    if len(MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][3]):  # Subtitle) >= 1:
        if add_DelayedContent(MetaData, client):
            return

        Selection = [utils.Translate(33702)]

        for SubTitle in MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][3]:  # Subtitle:
            Selection.append(SubTitle['DisplayTitle'])

        MetaData['SelectionIndexSubtitleStream'] = utils.Dialog.select(heading=utils.Translate(33484), list=Selection) - 1

    MetaData['SelectionIndexAudioStream'] = max(MetaData['SelectionIndexAudioStream'], 0)

    if MetaData['SelectionIndexSubtitleStream'] >= 0:
        utils.start_thread(SubTitlesAdd, (MetaData,))

    TranscodingAudioBitrate = f"&AudioBitrate={utils.audioBitrate}"
    TranscodingVideoBitrate = f"&VideoBitrate={utils.videoBitrate}"

    if MetaData['SelectionIndexSubtitleStream'] != -1:
        Subtitle = f"&SubtitleStreamIndex={MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][3][MetaData['SelectionIndexSubtitleStream']]['Index']}"
    else:
        Subtitle = ""

    Audio = f"&AudioStreamIndex={MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][2][MetaData['SelectionIndexAudioStream']]['Index']}"

    if utils.transcode_resolution:
        TranscodingVideoResolution = f"&Width={utils.transcode_resolution}"
    else:
        TranscodingVideoResolution = ""

    if 'VideoCodecNotSupported' in MetaData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in MetaData['TranscodeReasons'] or 'VideoResolutionNotSupported' in MetaData['TranscodeReasons']:
        TranscodingVideoCodec = f"&VideoCodec={utils.TranscodeFormatVideo}"
    else:
        TranscodingVideoCodec = "&VideoCodec=copy"

    if 'AudioCodecNotSupported' in MetaData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in MetaData['TranscodeReasons']:
        TranscodingAudioCodec = f"&AudioCodec={utils.TranscodeFormatAudio}"
    else:
        TranscodingAudioCodec = "&AudioCodec=copy"

    set_QueuedPlayingItem(MetaData, None)
    send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/main.m3u8?TranscodeReasons={MetaData['TranscodeReasons']}{TranscodingVideoCodec}{TranscodingVideoResolution}{TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}{Audio}{Subtitle}")

def send_delayed_content(client, Payload):
    xbmc.log(f"EMBY.hooks.webservice: send_delay_content: {Payload}", 0) # DEBUGINFO
    DelayedContentLock.acquire()

    if Payload in DelayedContent:
        DC = DelayedContent[Payload][0]
        DelayedContentLock.release()

        if DC:
            xbmc.log(f"EMBY.hooks.webservice: Content available: {Payload}", 0) # DEBUGINFO

            if DC == "blank":
                send_BlankWAV(client, Payload)
            else:
                client.send(DC)

            # Things could have changed by other threads since the check at the top so check again
            with DelayedContentLock:
                if Payload in DelayedContent:
                    globals()['DelayedContent'][Payload][1] -= 1

                    if DelayedContent[Payload][1] < 0:
                        del globals()['DelayedContent'][Payload]

            return True

        return False

    DelayedContentLock.release()
    xbmc.log(f"EMBY.hooks.webservice: Delayed content not found {Payload}", 3) # LOGERROR
    client.send(sendNotFound)
    return True

def set_QueuedPlayingItem(MetaData, PlaySessionId):
    player.PlayerBusy()

    # Disable delete after watched option for multicontent
    if MetaData['SelectionIndexMediaSource'] != 0:
        FilePath = ""
    else:
        FilePath = MetaData['MediaSources'][0][0]['Path']

    if PlaySessionId:
        MetaData['PlaySessionId'] = PlaySessionId
        player.QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(MetaData['EmbyId']), 'MediaSourceId': MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'PlaybackRate': player.PlaybackRate[MetaData["PlayerId"]], 'Shuffle': player.Shuffled[MetaData["PlayerId"]], 'RepeatMode': player.RepeatMode[MetaData["PlayerId"]], 'IsMuted': player.Muted, 'PlaySessionId': MetaData['PlaySessionId'], "LiveStreamId": MetaData['LiveStreamId']}, MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['IntroStartPositionTicks'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['IntroEndPositionTicks'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['CreditsPositionTicks'], utils.EmbyServers[MetaData['ServerId']], MetaData["PlayerId"], MetaData['Type'], FilePath]
    else:
        MetaData['PlaySessionId'] = str(uuid.uuid4()).replace("-", "")
        player.QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(MetaData['EmbyId']), 'MediaSourceId': MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'PlaybackRate': player.PlaybackRate[MetaData["PlayerId"]], 'Shuffle': player.Shuffled[MetaData["PlayerId"]], 'RepeatMode': player.RepeatMode[MetaData["PlayerId"]], 'IsMuted': player.Muted, 'PlaySessionId': MetaData['PlaySessionId']}, MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['IntroStartPositionTicks'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['IntroEndPositionTicks'], MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['CreditsPositionTicks'], utils.EmbyServers[MetaData['ServerId']], MetaData["PlayerId"], MetaData['Type'], FilePath]

def add_DelayedContent(MetaData, client):
    if not MetaData['DelayedContentSet']:
        MetaData['DelayedContentSet'] = True

        with DelayedContentLock:
            if MetaData['Payload'] in DelayedContent:
                globals()['DelayedContent'][MetaData['Payload']][1] += 1
                Added = True
            else:
                globals()['DelayedContent'][MetaData['Payload']] = [None, 0]
                Added = False

        client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content{MetaData['Payload']}\r\nContent-Length: 0\r\n\r\n".encode())
        client.close()
        return Added

    return False

def set_DelayedContent(Payload, Data):
    with DelayedContentLock:
        globals()['DelayedContent'][Payload][0] = Data

def wait_for_Embyserver(client, ServerId):
    DelayQuery = 0

    while ServerId not in utils.EmbyServers or not utils.EmbyServers[ServerId].Online:
        Break = False

        if utils.sleep(1):
            xbmc.log("EMBY.hooks.webservice: Kodi Shutdown", 1) # LOGINFO
            Break = True

        if DelayQuery >= 30:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, timeout query", 1) # LOGINFO
            Break = True

        if Break:
            client.settimeout(1)
            client.send(sendNotFound)
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] terminate query", 0) # LOGDEBUG
            return False

        DelayQuery += 1

    return True

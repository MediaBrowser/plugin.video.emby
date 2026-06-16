import threading
from urllib.parse import parse_qsl
import uuid
import socket
import xbmc
from hooks import favorites
from database import dbio
from emby import metadata, httpcache
from helper import utils, context, playerops, pluginmenu, player, xmls, queue, cache
DefaultVideoSettings = xmls.load_defaultvideosettings()
SubtitlesLanguageDefault = DefaultVideoSettings.get("SubtitlesLanguage", "").lower()
EnableSubtitleDefault = DefaultVideoSettings.get('ShowSubtitles', False)
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\n\r\n'.encode()
sendNotFound = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\n\r\n'.encode()
sendHeadPicture = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: image/unknown\r\n\r\n'.encode()
sendHeadAudio = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: audio/unknown\r\nAccept-Ranges: none\r\n\r\n'.encode()
sendHeadVideo = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: video/unknown\r\nAccept-Ranges: none\r\n\r\n'.encode()
sendHeadVideoHLS = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: 0\r\nContent-Type: application/vnd.apple.mpegurl\r\nAccept-Ranges: none\r\n\r\n'.encode()
Running = False
Socket = None
KeyBoard = xbmc.Keyboard()
DelayedContent = {}
DelayedContentLock = threading.Lock()
EmbyIdCurrentlyPlaying = 0
MaxWorkers = utils.WebserviceWorkers
WorkerQueue = queue.Queue()
AsyncCommandQueue = queue.Queue()
DelayedContentCondition = threading.Condition(threading.Lock())
xbmc.log(f"EMBY.hooks.webservice: Number of workers {MaxWorkers}", 1) # LOGINFO

# Load binary files once
BlackMP4 = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.mp4")
BlackMKV = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.mkv")
BlackAVI = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.avi")
BlackWEBM = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.webm")
BlackMOV = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.mov")
BlackTS = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.ts")
BlackMPEG = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.mpeg")
BlackWMV = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.wmv")
BlackOGV = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.ogv")
Black3GP = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.3gp")
BlackVOB = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.vob")
BlackM4V = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.m4v")
BlackFLV = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.flv")
BlackMXF = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.mxf")
BlackASF = utils.readFileBinary("special://home/addons/plugin.service.emby-next-gen/resources/black.asf")

# Generate HTTP responses
sendBlackMP4 = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackMP4)}\r\nContent-Type: video/mp4\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackMP4
sendBlackMKV = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackMKV)}\r\nContent-Type: video/x-matroska\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackMKV
sendBlackAVI = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackAVI)}\r\nContent-Type: video/x-msvideo\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackAVI
sendBlackWEBM = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackWEBM)}\r\nContent-Type: video/webm\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackWEBM
sendBlackMOV = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackMOV)}\r\nContent-Type: video/quicktime\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackMOV
sendBlackTS = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackTS)}\r\nContent-Type: video/mp2t\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackTS
sendBlackMPEG = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackMPEG)}\r\nContent-Type: video/mpeg\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackMPEG
sendBlackWMV = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackWMV)}\r\nContent-Type: video/x-ms-wmv\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackWMV
sendBlackOGV = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackOGV)}\r\nContent-Type: video/ogg\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackOGV
sendBlack3GP = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(Black3GP)}\r\nContent-Type: video/3gpp\r\nAccept-Ranges: none\r\n\r\n'.encode() + Black3GP
sendBlackVOB = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackVOB)}\r\nContent-Type: video/dvd\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackVOB
sendBlackFLV = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackFLV)}\r\nContent-Type: video/x-flv\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackFLV
sendBlackMXF = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackMXF)}\r\nContent-Type: application/mxf\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackMXF
sendBlackASF = f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BlackASF)}\r\nContent-Type: video/x-ms-asf\r\nAccept-Ranges: none\r\n\r\n'.encode() + BlackASF

def get_MediaHandler(Payload):
    p = Payload.lower()

    if p.endswith(".mp4") or p.endswith(".m4v"):
        return sendBlackMP4

    if p.endswith(".mkv"):
        return sendBlackMKV

    if p.endswith(".avi"):
        return sendBlackAVI

    if p.endswith(".ts") or p.endswith(".m2ts") or p.endswith(".mts"):
        return sendBlackTS

    if p.endswith(".mpg") or p.endswith(".mpeg") or p.endswith(".mpe"):
        return sendBlackMPEG

    if p.endswith(".webm"):
        return sendBlackWEBM

    if p.endswith(".mov"):
        return sendBlackMOV

    if p.endswith(".wmv"):
        return sendBlackWMV

    if p.endswith(".ogv"):
        return sendBlackOGV

    if p.endswith(".3gp"):
        return sendBlack3GP

    if p.endswith(".flv"):
        return sendBlackFLV

    if p.endswith(".mxf"):
        return sendBlackMXF

    if p.endswith(".vob"):
        return sendBlackVOB

    if p.endswith(".asf"):
        return sendBlackASF

    return sendBlackMP4

def start():
    global Running
    global Socket
    Running = True

    try: # intercept multiple start by different threads (just precaution)
        LocalSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        LocalSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        LocalSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        LocalSocket.bind(('127.0.0.1', 57342))
        Socket = LocalSocket
    except Exception as Error:
        xbmc.log(f"EMBY.hooks.webservice: Socket start (error) {Error}", 1) # LOGINFO
        return False

    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice: Start", 1) # LOGINFO

    # preload simultan workers
    for WorkerNumber in range(MaxWorkers):
        utils.start_thread(worker_Query, (WorkerNumber,))

    utils.start_thread(Listen, ())
    utils.start_thread(AsyncCommands, ())
    return True

def close():
    global Running

    if Running:
        Running = False
        AsyncCommandQueue.put("QUIT")

        for _ in range(MaxWorkers):
            WorkerQueue.put("QUIT")

        try:
            Socket.close()
        except Exception as Error:
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 1) # LOGINFO

        xbmc.log("EMBY.hooks.webservice: Shutdown webservice", 1) # LOGINFO
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): DelayedContent queue size: {len(DelayedContent)}", 1) # LOGDEBUG

def Listen():
    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): THREAD: --->[ webservice/57342 ]", 1) # LOGDEBUG
    Socket.listen()
    Socket.settimeout(0.1)

    while not utils.SystemShutdown and Running:
        try:
            ClinetSocket, _ = Socket.accept()
        except:
            continue

        WorkerQueue.put(ClinetSocket)

    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): THREAD: ---<[ webservice/57342 ]", 1) # LOGDEBUG

def worker_Query(WorkerNumber):  # thread by caller
    if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: --->[ worker_Query/{WorkerNumber} ]", 1) # LOGDEBUG

    while Running:
        Data = WorkerQueue.get()

        if Data == "QUIT":
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: ---<[ worker_Query/{WorkerNumber} ] quit", 1) # LOGDEBUG
            return

        client = Data
        client.settimeout(None)
        data = client.recv(16384).decode()
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice: [ worker_Query/{WorkerNumber} ] Incoming Data: {data}", 1) # LOGDEBUG
        IncomingData = data.split(' ')

        if IncomingData[0] in ("PROPFIND", "PROPPATCH", "MKCOL", "COPY", "MOVE", "DELETE", "LOCK", "UNLOCK"): # webdav methodS, currently not supported
            client.send(sendNotFound)
            client.close()
            continue

        # events by event.py
        if IncomingData[0] == "EVENT":
            args = IncomingData[1].split(";")
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): [ worker_Query/{WorkerNumber} ] {IncomingData[1]}", 1) # LOGDEBUG


            if args[1] == "specials":
                client.send(sendOK)
                client.close()
                context.specials()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event specials", 1) # LOGDEBUG
                continue

            if args[1] == "multiversion":
                client.send(sendOK)
                client.close()
                context.multiversion()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event multiversion", 1) # LOGDEBUG
                continue

            if args[1] == "playrandom":
                client.send(sendOK)
                client.close()
                context.playrandom()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event playrandom", 1) # LOGDEBUG
                continue

            if args[1] == "gotoshow":
                client.send(sendOK)
                client.close()
                context.gotoshow()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event gotoshow", 1) # LOGDEBUG
                continue

            if args[1] == "gotoseason":
                client.send(sendOK)
                client.close()
                context.gotoseason()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event gotoseason", 1) # LOGDEBUG
                continue

            if args[1] == "gotoalbum":
                client.send(sendOK)
                client.close()
                context.gotoalbum()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event gotoalbum", 1) # LOGDEBUG
                continue

            if args[1] == "gotoartist":
                client.send(sendOK)
                client.close()
                context.gotoartist()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event gotoartist", 1) # LOGDEBUG
                continue

            if args[1] == "similarshow":
                client.send(sendOK)
                client.close()
                context.similar("Series")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event similarshow", 1) # LOGDEBUG
                continue

            if args[1] == "similarartist":
                client.send(sendOK)
                client.close()
                context.similar("Artist")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event similarartist", 1) # LOGDEBUG
                continue

            if args[1] == "similaralbum":
                client.send(sendOK)
                client.close()
                context.similar("MusicAlbum")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event similaralbum", 1) # LOGDEBUG
                continue

            if args[1] == "similarmusicvideo":
                client.send(sendOK)
                client.close()
                context.similar("MusicVideo")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event similarmusicvideo", 1) # LOGDEBUG
                continue

            if args[1] == "similarmovie":
                client.send(sendOK)
                client.close()
                context.similar("Movie")
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event similarmovie", 1) # LOGDEBUG
                continue

            if args[1] == "download":
                client.send(sendOK)
                client.close()
                context.download()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event download", 1) # LOGDEBUG
                continue

            if args[1] == "deletedownload":
                client.send(sendOK)
                client.close()
                context.deletedownload()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event deletedownload", 1) # LOGDEBUG
                continue

            if args[1] == "record":
                client.send(sendOK)
                client.close()
                context.Record()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event record", 1) # LOGDEBUG
                continue

            if args[1] == "addremoteclient":
                client.send(sendOK)
                client.close()
                context.add_remoteclients()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event addremoteclient", 1) # LOGDEBUG
                continue

            if args[1] == "removeremoteclient":
                client.send(sendOK)
                client.close()
                context.delete_remoteclients()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event removeremoteclient", 1) # LOGDEBUG
                continue

            if args[1] == "watchtogether":
                client.send(sendOK)
                client.close()
                context.watchtogether()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event watchtogether", 1) # LOGDEBUG
                continue

            if args[1] == "remoteplay":
                client.send(sendOK)
                client.close()
                context.remoteplay()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event remoteplay", 1) # LOGDEBUG
                continue

            if args[1] == "refreshitem":
                client.send(sendOK)
                client.close()
                context.refreshitem()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event refreshitem", 1) # LOGDEBUG
                continue

            if args[1] == "deleteitem":
                client.send(sendOK)
                client.close()
                context.deleteitem()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event deleteitem", 1) # LOGDEBUG
                continue

            if args[1] == "favorites":
                client.send(sendOK)
                client.close()
                context.favorites()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event favorites", 1) # LOGDEBUG
                continue

            if args[1] == "settings":
                client.send(sendOK)
                client.close()
                xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event settings", 1) # LOGDEBUG
                continue

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
                    if "All" in cache.QueryCache:
                        if CacheId1 in cache.QueryCache["All"]:
                            cache.QueryCache["All"][CacheId1][0] = False
                        elif CacheId2 in cache.QueryCache["All"]:
                            cache.QueryCache["All"][CacheId2][0] = False

                    utils.ActivateWindow("videos", f"plugin://plugin.service.emby-next-gen/?id=0&mode=browse&query=Search&server={ServerId}&parentid=0&content=All&libraryid=0")

                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event search", 1) # LOGDEBUG
                continue

            if mode == 'settings':  # Simple commands
                client.send(sendOK)
                client.close()
                xbmc.executebuiltin('Addon.OpenSettings(plugin.service.emby-next-gen)')
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event settings", 1) # LOGDEBUG
                continue

            if mode == 'managelibsselection':  # Simple commands
                client.send(sendOK)
                client.close()
                pluginmenu.select_managelibs()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event managelibsselection", 1) # LOGDEBUG
                continue

            if mode == 'texturecache':  # Simple commands
                client.send(sendOK)
                client.close()

                if not utils.artworkcacheenable:
                    utils.Dialog.notification(heading=utils.addon_name, icon=utils.icon, message=utils.Translate(33226), sound=False, time=utils.displayMessage)
                else:
                    pluginmenu.cache_textures()

                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event texturecache", 1) # LOGDEBUG
                continue

            if mode == 'databasereset':  # Simple commands
                client.send(sendOK)
                client.close()
                pluginmenu.databasereset(favorites)
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event databasereset", 1) # LOGDEBUG
                continue

            if mode == 'nodesreset':  # Simple commands
                client.send(sendOK)
                client.close()
                utils.nodesreset()
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event nodesreset", 1) # LOGDEBUG
                continue

            if mode == 'skinreload':  # Simple commands
                client.send(sendOK)
                client.close()
                xbmc.executebuiltin('ReloadSkin()')
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event skinreload", 1) # LOGDEBUG
                continue

            if mode == 'play':
                client.send(sendOK)
                client.close()
                playerops.PlayEmby((params.get('item'),), "PlayNow", -1, -1, utils.EmbyServers[ServerId], 0)
                if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: [ worker_Query/{WorkerNumber} ] event play", 1) # LOGDEBUG
                continue

            # wait for loading
            if mode == 'browse':
                query = params.get("query")

                if query not in ("NodesDynamic", "NodesSynced"):
                    if not wait_for_Embyserver(client, ServerId):
                        client.close()
                        continue

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
            continue

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
                xbmc.log(f"EMBY.hooks.webservice: Unknown method: {IncomingData[0]}", 1) # LOGINFO
                client.send(sendOK)

        client.close()
        del client
        del IncomingData

    if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): THREAD: ---<[ worker_Query/{WorkerNumber} ] not running", 1) # LOGDEBUG

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
        set_DelayedContent(MetaData['ETag'], get_MediaHandler(MetaData['Payload']), 1, MetaData['KodiId'])

def build_Path(MetaData, Data):
    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    Path = f"{utils.EmbyServers[MetaData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}MediaSourceId={MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Id']}&PlaySessionId={MetaData['PlaySessionId']}&DeviceId={utils.EmbyServers[MetaData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[MetaData['ServerId']].ServerData['AccessToken']}"
    return Path

def send_redirect(client, MetaData, Data, AddCache=True):
    utils.close_busyDialog()

    if AddCache:
        httpcache.add(MetaData, Data)

    if MetaData['isHttp'] and utils.followhttp:
        SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {MetaData['MediaSources'][MetaData['SelectionIndexMediaSource']][0]['Path']}\r\nContent-Length: 0\r\nAccept-Ranges: none\r\n\r\n".encode()
    else:
        Path = build_Path(MetaData, Data)

        if "main.m3u8" in Data:
            M3U8 = utils.EmbyServers[MetaData['ServerId']].API.get_m3u8(Path, MetaData['EmbyId'])
            EtagHLS = f'{str(uuid.uuid4()).replace("-", "")}/embyhls.m3u8'
            Path = f"http://127.0.0.1:57342/delayed_content/{EtagHLS}"
            set_DelayedContent(EtagHLS, f'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(M3U8)}\r\nContent-Type: application/vnd.apple.mpegurl\r\nAccept-Ranges: none\r\n\r\n'.encode() + M3U8, 2, 0) # Content (Not redirects) are requested 3 times, therefore indeox must be 2 not 1
            SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-Length: 0\r\nAccept-Ranges: none\r\n\r\n".encode()
        else:
            SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-Length: 0\r\nAccept-Ranges: none\r\n\r\n".encode()

    if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): Send data: {SendData}", 1) # LOGDEBUG

    try:
        client.send(SendData)
    except:
        set_DelayedContent(MetaData['ETag'], SendData, 0, 0)

def GetRequest(client, Payload, isDelayedContent, isPicture, isAudio, isVideo):
    # Delayed contents are used for user inputs (selection box for e.g. multicontent versions, transcoding selection etc.)
    # workaround for low Kodi network timeout settings, for long running processes. "delayed_content" folder is actually a redirect to keep timeout below threshold

    # Read from cache -> double/tripple HTTP GET queries are trigger by e.g. live tv, therefore use cached HTTP responses
    HTTPCache = httpcache.get(Payload)

    if HTTPCache:
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): Use HTTP Cache: {HTTPCache}", 1)
        send_redirect(client, HTTPCache[0], HTTPCache[1], False)
        return

    global EmbyIdCurrentlyPlaying

    # Delayed content used for e.g. multiselection episodes, trailers etc.
    if isDelayedContent:
        Etag = Payload[1:]

        if send_delayed_content(client, Etag):
            return

        with utils.SafeLock(DelayedContentCondition):
            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: --->[ DelayedContentCondition ]", 1)
            Wait = int((utils.curltimeouts - 0.5) * 10)

            while Wait > 0:
                if DelayedContentCondition.wait(timeout=0.1):
                    break

                Wait -= 1

            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: ---<[ DelayedContentCondition ]", 1)

            if utils.SystemShutdown:
                client.send(sendNotFound)
                return

            if send_delayed_content(client, Etag):
                return

            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice: Continue waiting for content, send another redirect", 0)
            client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content/{Etag}\r\nAccept-Ranges: none\r\nContent-Length: 0\r\n\r\n".encode())
            return

    # Load parameters from url request
    MetaData = metadata.load_MetaData(Payload, isPicture, isAudio)
    MetaData['ETag'] = f'{str(uuid.uuid4()).replace("-", "")}{Payload[-5:]}'

    if not MetaData: # Invalid request
        client.send(sendNotFound)
        return

    if MetaData['Type'] in ("movie", "episode", "musicvideo", "tvchannel", "video"):
        playerops.PlayerId = 1
    elif MetaData['Type'] == "audio":
        playerops.PlayerId = 0

    # Set player id
    if isVideo:
        player.PlaylistRemoveItem = -1
        player.set_PlayerId({"player": {"playerid": 1}})
    elif isAudio:
        player.set_PlayerId({"player": {"playerid": 0}})

    # Waiting for Emby connection:
    if not wait_for_Embyserver(client, MetaData['ServerId']):
        return

    if MetaData['Type'] == 'picture':
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): Load artwork: {Payload}", 1) # LOGDEBUG

        if not MetaData['Overlay']:
            if utils.enableCoverArt:
                Enhancers = "&EnableImageEnhancers=True"
            else:
                Enhancers = "&EnableImageEnhancers=False"

            client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {utils.EmbyServers[MetaData['ServerId']].ServerData['ServerUrl']}/emby/Items/{MetaData['EmbyId']}/Images/{MetaData['ImageType']}/{MetaData['ImageIndex']}?&api_key={utils.EmbyServers[MetaData['ServerId']].ServerData['AccessToken']}{Enhancers}\r\nAccept-Ranges: none\r\nContent-Length: 0\r\n\r\n".encode())
            return

        BinaryData, ContentType, _ = utils.image_overlay(MetaData['ImageTag'], MetaData['ServerId'], MetaData['EmbyId'], MetaData['ImageType'], MetaData['ImageIndex'], MetaData['Overlay'])
        client.send(f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BinaryData)}\r\nContent-Type: {ContentType}\r\nAccept-Ranges: none\r\n\r\n".encode() + BinaryData)
        if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): Loaded Delayed Content for {Payload}", 1) # LOGDEBUG
        return

    if MetaData['Type'] == 'audio':
        set_QueuedPlayingItem(MetaData, None)
        send_redirect(client, MetaData, f"audio/{MetaData['EmbyId']}/stream?static=true")
        return

    EmbyIdCurrentlyPlaying = MetaData['EmbyId']

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
    if not utils.RemoteMode and ((utils.enableCinemaMovies and MetaData['Type'] == "movie") or (utils.enableCinemaEpisodes and MetaData['Type'] == "episode")) and player.VideoPlayback not in ("TRAILER", "CONTENT", "TRAILERCANCEL"):

        if not MetaData['isDynamic']:
            videoDB = dbio.DBOpenRO("video", "http_Query")
            Progress = videoDB.get_Progress_by_KodiType_KodiId(MetaData['Type'], MetaData['KodiId'])
            dbio.DBCloseRO("video", "http_Query")
        else:
            Progress = 0

        if not Progress and player.VideoPlayback in ("READY", "THEME"):
            player.PlaylistIndexContent = playerops.GetPlaylistPosition(1)
            PlayTrailer = True

            if add_DelayedContent(MetaData, client):
                return

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                if player.load_Trailer(MetaData['ServerId']):
#                    utils.close_busyDialog()
                    set_DelayedContent(MetaData['ETag'], get_MediaHandler(MetaData['Payload']), 1, MetaData['KodiId'])
                    AsyncCommandQueue.put((("TRAILER", MetaData['ServerId']),))
                    return

#            utils.close_busyDialog()
            player.VideoPlayback = "TRAILERCANCEL"
            set_DelayedContent(MetaData['ETag'], f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: http://127.0.0.1:57342{Payload}\r\nConnection: close\r\nContent-Length: 0\r\nAccept-Ranges: none\r\n\r\n".encode(), 0, 0)
            return

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
            set_DelayedContent(MetaData['ETag'], get_MediaHandler(MetaData['Payload']), 1, MetaData['KodiId'])
            playerops.Stop(False)
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

        set_QueuedPlayingItem(MetaData, None)
        send_redirect(client, MetaData, f"videos/{MetaData['EmbyId']}/stream?static=true")
        AsyncCommandQueue.put((("SUBTITLE", MetaData),))
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

    if MetaData['SelectionIndexSubtitleStream'] >= 0:
        AsyncCommandQueue.put((("SUBTITLE", MetaData),))

def send_delayed_content(client, ETag):
    if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): send_delay_content: {ETag}", 1) # DEBUGINFO

    while not DelayedContentLock.acquire(timeout=0.1):
        pass

    if ETag in DelayedContent:
        DC = DelayedContent[ETag][0]
        DelayedContentLock.release()

        if DC:
            if utils.DebugLog: xbmc.log(f"EMBY.hooks.webservice (DEBUG): Content available: {ETag}", 1) # DEBUGINFO
            client.send(DC)

            with utils.SafeLock(DelayedContentLock):
                if ETag in DelayedContent:
                    DelayedContent[ETag][1] -= 1

                    if DelayedContent[ETag][1] < 0:
                        del DelayedContent[ETag]

            return True

        return False

    DelayedContentLock.release()
    xbmc.log(f"EMBY.hooks.webservice: Delayed content not found {ETag}", 3) # LOGERROR
    client.send(sendNotFound)
    return True

def set_QueuedPlayingItem(MetaData, PlaySessionId):
    player.PlayerBusyDelay = 5

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

        with utils.SafeLock(DelayedContentLock):
            if MetaData['ETag'] in DelayedContent:
                DelayedContent[MetaData['ETag']][1] += 1
                Added = True
            else:
                DelayedContent[MetaData['ETag']] = [None, 0]
                Added = False

        client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content/{MetaData['ETag']}\r\nContent-Length: 0\r\nAccept-Ranges: none\r\n\r\n".encode())
        client.close()
        utils.close_busyDialog(True)
        return Added

    return False

def set_DelayedContent(ETag, Data, Index, KodiId):
    with utils.SafeLock(DelayedContentLock):
        if Index:
            DelayedContent[ETag] = [Data, Index]
        else:
            DelayedContent[ETag][0] = Data

    if KodiId:
        player.ForceStopKodiId = int(KodiId)

    with utils.SafeLock(DelayedContentCondition):
        DelayedContentCondition.notify_all()

def wait_for_Embyserver(client, ServerId):
    with utils.SafeLock(utils.EmbyServerOnlineCondition):
        while ServerId not in utils.EmbyServers or not utils.EmbyServers[ServerId].library.SettingsLoaded:
            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: --->[ EmbyServerOnlineCondition ]", 1)
            Wait = 30

            while Wait > 0:
                if utils.EmbyServerOnlineCondition.wait(timeout=0.1):
                    break

                Wait -= 1

            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: ---<[ EmbyServerOnlineCondition ]", 1)

            if utils.SystemShutdown:
                xbmc.log(f"EMBY.hooks.webservice: Kodi shutdown while waiting for Emby connection... {ServerId}", 1)
                client.send(sendNotFound)
                return False

        return True

def play_initial_trailer(EmbyServer):
    # Wait for player stop
    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: --->[ ForceStopCondition ]", 1) # LOGDEBUG

    with utils.SafeLock(player.ForceStopCondition):
        while player.ForceStopKodiId:
            if utils.SystemShutdown:
                return

            player.ForceStopCondition.wait(timeout=0.1)

    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): CONDITION: ---<[ ForceStopCondition ]", 1) # LOGDEBUG

    # Play invalid item to reset the playerid to -1 for trailers (Kodi workaround), playerid -1 not toucking playlists
    xbmc.executebuiltin('PlayMedia("special://home/addons/plugin.video.emby/icon.png")')

    for _ in range(20):
        if xbmc.getCondVisibility("System.HasActiveModalDialog"):
            break

        if utils.sleep(0.1): # Gibt True bei Shutdown zurück
            return

    utils.close_dialog("all")

    # Play trailer
    player.play_Trailer(EmbyServer)

def AsyncCommands():
    if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): THREAD: --->[ AsyncCommands ]", 1) # LOGDEBUG

    while True:
        IncomingCommand = AsyncCommandQueue.get()

        if IncomingCommand == "QUIT":
            if utils.DebugLog: xbmc.log("EMBY.hooks.webservice (DEBUG): THREAD: ---<[ AsyncCommands ]", 1) # LOGDEBUG
            return

        if IncomingCommand[0] == "TRAILER":
            play_initial_trailer(utils.EmbyServers[IncomingCommand[1]])
        elif IncomingCommand[0] == "SUBTITLE":
            SubTitlesAdd(IncomingCommand[1])

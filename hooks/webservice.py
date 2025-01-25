from _thread import allocate_lock
from urllib.parse import unquote, parse_qsl
import uuid
import _socket
import xbmc
from hooks import favorites
from database import dbio
from helper import utils, context, playerops, pluginmenu, player, xmls
DefaultVideoSettings = xmls.load_defaultvideosettings()
MediaIdMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
EmbyIdMapping = {"m": "Movie", "e": "Episode", "M": "MusicVideo", "a": "Audio", "i": "Movie", "T": "Video", "v": "Video", "A": "Audio"}
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
sendNotFound = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
BlankWAV = b'\x52\x49\x46\x46\x25\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x74\x00\x00\x00\x00' # native blank wave file
sendBlankWAV = ('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 45\r\nContent-type: audio/wav\r\n\r\n'.encode(), BlankWAV) # used to "stop" playback by sending a WAV file with silence. File is valid, so Kodi will not raise an error message
TrailerInitItem = ["", None] # payload/listitem of the trailer initiated content item
Cancel = False
Running = False
Socket = None
KeyBoard = xbmc.Keyboard()
DelayedContent = {}
DelayedContentLock = allocate_lock()
EmbyIdCurrentlyPlaying = 0

def start():
    if not Running:
        globals()["Running"] = True

        try: # intercept multiple start by different threads (just precaution)
            globals()['Socket'] = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            Socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            Socket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
            Socket.bind(('127.0.0.1', 57342))
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket start (error) {Error}", 1) # LOGINFO
            return False

        xbmc.log("EMBY.hooks.webservice: Start", 1) # LOGINFO
        utils.start_thread(Listen, ())
        return True

    return False

def close():
    if Running:
        globals()["Running"] = False

        try:
            Socket.close()
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 1) # LOGINFO

        xbmc.log("EMBY.hooks.webservice: Shutdown weservice", 1) # LOGINFO
        xbmc.log(f"EMBY.hooks.webservice: DelayedContent queue size: {len(DelayedContent)}", 0) # LOGDEBUG

def Listen():
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ webservice/57342 ]", 0) # LOGDEBUG
    Socket.listen()
    Socket.settimeout(1)

    while not utils or not utils.SystemShutdown:
        try:
            fd, _ = Socket._accept()
        except:
            continue

        utils.start_thread(worker_Query, (fd,))

    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ webservice/57342 ]", 0) # LOGDEBUG

def worker_Query(fd):  # thread by caller
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ worker_Query ]", 0) # LOGDEBUG
    client = _socket.socket(fileno=fd)
    client.settimeout(None)
    data = client.recv(16384).decode()
    xbmc.log(f"EMBY.hooks.webservice: Incoming Data: {data}", 0) # LOGDEBUG
    DelayQuery = 0
    IncomingData = data.split(' ')

    if IncomingData[0] != "EVENT" or ("mode" in IncomingData[1] and "query=NodesDynamic" not in IncomingData[1] and "query=NodesSynced" not in IncomingData[1]):
        while not utils.EmbyServers or not list(utils.EmbyServers.values())[0].Online:
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
                client.close()
                xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] terminate query", 0) # LOGDEBUG
                return

            DelayQuery += 1

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

                if "All" in utils.QueryCache:
                    if CacheId1 in utils.QueryCache["All"]:
                        utils.QueryCache["All"][CacheId1][0] = False
                    elif CacheId2 in utils.QueryCache["All"]:
                        utils.QueryCache["All"][CacheId2][0] = False

                utils.SendJson(f'{{"jsonrpc": "2.0", "id": 1, "method": "GUI.ActivateWindow", "params": {{"window": "videos", "parameters": ["plugin://plugin.service.emby-next-gen/?id=0&mode=browse&query=Search&server={ServerId}&parentid=0&content=All&libraryid=0", "return"]}}}}')

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
        elif mode == 'remotepictures':
            pluginmenu.remotepictures(Handle, params.get('position'))
        else:  # 'listing'
            pluginmenu.listing(Handle, args[0])

        client.send(sendOK)
        client.close()
        xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event browse", 0) # LOGDEBUG
        return

    PayloadLower = IncomingData[1].lower()
    isHEAD = IncomingData[0] == "HEAD"
    isPictureQuery = IncomingData[1].startswith('/picture/') or IncomingData[1].startswith('/delayed_content/picture')

    if 'extrafanart' in PayloadLower or 'extrathumbs' in PayloadLower or 'extras/' in PayloadLower or PayloadLower.endswith('.edl') or PayloadLower.endswith('index.bdmv') or PayloadLower.endswith('index.bdm') or PayloadLower.endswith('.txt') or PayloadLower.endswith('.vprj') or PayloadLower.endswith('.xml') or PayloadLower.endswith('/') or PayloadLower.endswith('.nfo') or (not isPictureQuery and (PayloadLower.endswith('.bmp') or PayloadLower.endswith('.jpg') or PayloadLower.endswith('.jpeg') or PayloadLower.endswith('.ico') or PayloadLower.endswith('.png') or PayloadLower.endswith('.ifo') or PayloadLower.endswith('.gif') or PayloadLower.endswith('.tbn') or PayloadLower.endswith('.tiff'))): # Unsupported queries used by Kodi
        client.send(sendNotFound)
    elif IncomingData[0] == "GET" or isHEAD:
        http_Query(client, IncomingData[1], isHEAD, isPictureQuery)
    else:
        client.send(sendOK)

    client.close()
    del client
    del IncomingData
    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ]", 0) # LOGDEBUG

def LoadISO(QueryData, client): # native content
    player.MultiselectionDone = True
    Path = QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Path']

    if Path.startswith('\\\\'):
        Path = Path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Path'] = Path
    ListItem = player.load_KodiItem("LoadISO", QueryData['KodiId'], QueryData['Type'], Path)

    if not ListItem:
        client.send(sendOK)
    else:
        set_QueuedPlayingItem(QueryData, None)
        player.replace_playlist_listitem(ListItem, QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Path'])
        set_DelayedContent(QueryData['Payload'], "blank")

def send_BlankWAV(client, ContentId):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    try:
        client.send(sendBlankWAV[0] + sendBlankWAV[1])
    except:
        set_DelayedContent(ContentId, "blank")

def build_Path(QueryData, Data):
    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    Path = f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}MediaSourceId={QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Id']}&PlaySessionId={QueryData['PlaySessionId']}&DeviceId={utils.EmbyServers[QueryData['ServerId']].ServerData['DeviceId']}&api_key={utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken']}"
    return Path

def send_redirect(client, QueryData, Data):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756

    if QueryData['isHttp'] and utils.followhttp:
        SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Path']}\r\nContent-length: 0\r\n\r\n".encode()
    else:
        Path = build_Path(QueryData, Data)

        if "main.m3u8" in Data:
            _, _, MainM3U8 = utils.EmbyServers[QueryData['ServerId']].http.request("GET", Path.replace(f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/" , ""), {}, {}, True, "", False)
            MainM3U8Mod = MainM3U8.decode('utf-8').replace("hls1/main/", f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/videos/{QueryData['EmbyId']}/hls1/main/").encode()
            SendData = f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(MainM3U8Mod)}\r\nContent-Type: text/plain\r\n\r\n".encode() + MainM3U8Mod
        else:
            SendData = f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-length: 0\r\n\r\n".encode()

    xbmc.log(f"EMBY.hooks.webservice: Send data: {SendData}", 0) # LOGDEBUG

    utils.HTTPQueryDoublesFilter[QueryData['EmbyId']] = {'Payload': QueryData['Payload'], 'SendData': SendData}

    try:
        client.send(SendData)
    except:
        set_DelayedContent(QueryData['Payload'], SendData)

def http_Query(client, Payload, isHEAD, isPictureQuery):
    # Load parameters from url query
    QueryData = {'isDynamic': False, 'isHttp': False}
    PayloadMod = Payload

    if PayloadMod.startswith("/dynamic/"):
        QueryData['isDynamic'] = True
        PayloadMod = PayloadMod.replace("/dynamic", "")

    if PayloadMod.startswith("/http/"):
        QueryData['isHttp'] = True
        PayloadMod = PayloadMod.replace("/http", "")

    PayloadSplit = PayloadMod.split("/")
    MediaSources = []

    if isPictureQuery:  # Image/picture
        Data = PayloadMod[PayloadMod.rfind("/") + 1:].split("-") # MetaData
        ServerId = PayloadSplit[2]
        EmbyId = Data[1]
        DataLen = len(Data)

        if DataLen < 5:
            xbmc.log(f"EMBY.hooks.webservice: Invalid picture {PayloadMod}", 2) # LOGDEBUG
            client.send(sendNotFound)
            return

        QueryData.update({'ImageIndex': Data[2], 'ImageType': EmbyArtworkIDs[Data[3]], 'ImageTag': Data[4]})

        if DataLen >= 6 and Data[5]:
            QueryData['Overlay'] = unquote(Data[5])
        else:
            QueryData['Overlay'] = ""

        PlayerId = 2
    elif PayloadMod.startswith('/audio/'):
        Data = PayloadMod[PayloadMod.rfind("/") + 1:].split("-") # MetaData
        ServerId = PayloadSplit[2]
        EmbyId = Data[1]
        MediaSources = [[{'Id': Data[2], 'IntroStartPositionTicks': 0, 'IntroEndPositionTicks': 0, 'CreditsPositionTicks': 0, 'Path': ""}, [], [], []]]
    else:
        EmbyId = PayloadSplit[-3]
        ServerId = PayloadSplit[-6]
        Data = PayloadSplit[-2]
        Data = Data.split("-")
        Data[4] = bytes.fromhex(Data[4]).decode('utf-8')

        # Extract metatdata, sperators are <>, ><, <<, :
        MetadataSubs = Data[4].split("<>")

        for Index, MetadataSub in enumerate(MetadataSubs):
            MediaDatas = MetadataSub.split("<<")
            MediaSources.append([{}, [], [], []])

            for IndexSub, MediaData in enumerate(MediaDatas):
                if IndexSub == 0:
                    MediaSourceInfos = MediaData.split(":")

                    for MediaSourceInfoIndex, MediaSourceInfo in enumerate(MediaSourceInfos):
                        if MediaSourceInfoIndex == 0:
                            MediaSources[Index][0]['Name'] = MediaSourceInfo.replace("<;>", ":")
                        elif MediaSourceInfoIndex == 1:
                            MediaSources[Index][0]['Size'] = MediaSourceInfo
                        elif MediaSourceInfoIndex == 2:
                            MediaSources[Index][0]['Id'] = MediaSourceInfo
                        elif MediaSourceInfoIndex == 3:
                            MediaSources[Index][0]['Path'] = MediaSourceInfo.replace("<;>", ":")
                        elif MediaSourceInfoIndex == 4:
                            MediaSources[Index][0]['IntroStartPositionTicks'] = int(MediaSourceInfo)
                        elif MediaSourceInfoIndex == 5:
                            MediaSources[Index][0]['IntroEndPositionTicks'] = int(MediaSourceInfo)
                        elif MediaSourceInfoIndex == 6:
                            MediaSources[Index][0]['CreditsPositionTicks'] = int(MediaSourceInfo)
                        elif MediaSourceInfoIndex == 7:
                            MediaSources[Index][0]['IsRemote'] = bool(int(MediaSourceInfo))
                elif IndexSub == 1 and MediaData:
                    VideoStreams = MediaData.split("><")

                    for VideoStreamIndex, VideoStream in enumerate(VideoStreams):
                        MediaSources[Index][1].append({})
                        VideoStreamInfos = VideoStream.split(":")

                        for VideoStreamInfoIndex, VideoStreamInfo in enumerate(VideoStreamInfos):
                            if VideoStreamInfoIndex == 0:
                                MediaSources[Index][1][VideoStreamIndex]['Codec'] = VideoStreamInfo
                            elif VideoStreamInfoIndex == 1:
                                MediaSources[Index][1][VideoStreamIndex]['BitRate'] = int(VideoStreamInfo)
                            elif VideoStreamInfoIndex == 2:
                                MediaSources[Index][1][VideoStreamIndex]['Index'] = VideoStreamInfo
                            elif VideoStreamInfoIndex == 3:
                                MediaSources[Index][1][VideoStreamIndex]['Width'] = int(VideoStreamInfo)
                elif IndexSub == 2 and MediaData:
                    AudioStreams = MediaData.split("><")

                    for AudioStreamIndex, AudioStream in enumerate(AudioStreams):
                        MediaSources[Index][2].append({})
                        AudioStreamInfos = AudioStream.split(":")

                        for AudioStreamInfoIndex, AudioStreamInfo in enumerate(AudioStreamInfos):
                            if AudioStreamInfoIndex == 0:
                                MediaSources[Index][2][AudioStreamIndex]['DisplayTitle'] = AudioStreamInfo
                            elif AudioStreamInfoIndex == 1:
                                MediaSources[Index][2][AudioStreamIndex]['Codec'] = AudioStreamInfo
                            elif AudioStreamInfoIndex == 2:
                                MediaSources[Index][2][AudioStreamIndex]['BitRate'] = int(AudioStreamInfo)
                            elif AudioStreamInfoIndex == 3:
                                MediaSources[Index][2][AudioStreamIndex]['Index'] = AudioStreamInfo
                elif IndexSub == 3 and MediaData:
                    SubtitleStreams = MediaData.split("><")

                    for SubtitleStreamIndex, SubtitleStream in enumerate(SubtitleStreams):
                        MediaSources[Index][3].append({})
                        SubtitleStreamInfos = SubtitleStream.split(":")

                        for SubtitleStreamInfoIndex, SubtitleStreamInfo in enumerate(SubtitleStreamInfos):
                            if SubtitleStreamInfoIndex == 0:
                                MediaSources[Index][3][SubtitleStreamIndex]['language'] = SubtitleStreamInfo
                            elif SubtitleStreamInfoIndex == 1:
                                MediaSources[Index][3][SubtitleStreamIndex]['DisplayTitle'] = SubtitleStreamInfo
                            elif SubtitleStreamInfoIndex == 2:
                                MediaSources[Index][3][SubtitleStreamIndex]['external'] = bool(int(SubtitleStreamInfo))
                            elif SubtitleStreamInfoIndex == 3:
                                MediaSources[Index][3][SubtitleStreamIndex]['Index'] = SubtitleStreamInfo
                            elif SubtitleStreamInfoIndex == 4:
                                MediaSources[Index][3][SubtitleStreamIndex]['Codec'] = SubtitleStreamInfo

        QueryData.update({'KodiId': Data[1], 'KodiFileId': Data[2]})

    if Data[0] in EmbyIdMapping:
        EmbyType = EmbyIdMapping[Data[0]]
    else:
        EmbyType = None

    QueryData.update({'MediaSources': MediaSources, 'Payload': Payload, 'Type': MediaIdMapping[Data[0]], 'ServerId': ServerId, 'EmbyId': EmbyId, 'MediaType': Data[0], "EmbyType": EmbyType, "DelayedContentSet": False, "SelectionIndexMediaSource": 0, "SelectionIndexVideoStream": 0, "SelectionIndexAudioStream": 0, "SelectionIndexSubtitleStream": -1})

    if Data[0] in ("m", "M", "i", "T", "v", "e"):  # Videos or iso
        player.PlaylistRemoveItem = -1
        PlayerId = 1
    elif Data[0] in ("a", "A"):  # Audios
        PlayerId = 0
    elif Data[0] == "t":  # tv channel
        PlayerId = 1
    elif Data[0] == "c":  # e.g. channel
        PlayerId = 1
    else: # "V"
        PlayerId = 1

    if isHEAD:
        send_head_response(client, QueryData["Type"])
        return

    # Filter similar queries
    for HTTPQueryDoubleFilter in list(utils.HTTPQueryDoublesFilter.values()):
        if Payload == HTTPQueryDoubleFilter['Payload']:
            client.send(HTTPQueryDoubleFilter['SendData'])
            xbmc.log(f"EMBY.hooks.webservice: Double query: {Payload}", 1) # LOGINFO
            return

    # Delayed contents are used for user inputs (selection box for e.g. multicontent versions, transcoding selection etc.) are opened.
    # workaround for low Kodi network timeout settings, for long running processes. "delayed_content" folder is actually a redirect to keep timeout below threshold
    if Payload.startswith("/delayed_content"):
        ContentId = Payload.replace("/delayed_content", "")

        if not send_delayed_content(client, ContentId):
            for _ in range(utils.curltimeouts * 10 - 2):
                if utils.sleep(0.1):
                    xbmc.log("EMBY.hooks.webservice: Delayed content interrupt, Kodi shutdown", 2) # LOGWARNING
                    client.send(sendNotFound)
                    break

                if send_delayed_content(client, ContentId):
                    break
            else:
                xbmc.log("EMBY.hooks.webservice: Continue waiting for content, send another redirect", 0) # DEBUGINFO
                client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content{ContentId}\r\nContent-length: 0\r\n\r\n".encode())

        return

    # Waiting for Emby connection:
    if QueryData['ServerId'] not in utils.EmbyServers:
        xbmc.log(f"EMBY.hooks.webservice: Emby ServerId not found {QueryData['ServerId']}", 2) # LOGWARNING
        client.send(sendNotFound)
        return

    try:
        while not utils.EmbyServers[QueryData['ServerId']].EmbySession:
            xbmc.log(f"EMBY.hooks.webservice: Waiting for Emby connection... {QueryData['ServerId']}", 1) # LOGINFO

            if utils.sleep(1):
                xbmc.log(f"EMBY.hooks.webservice: Kodi shutdown while waiting for Emby connection... {QueryData['ServerId']}", 1) # LOGINFO
                client.send(sendNotFound)
                return
    except: # could be triggered when server was removed -> QueryData['ServerId'] removed from utils.EmbyServers
        return

    if QueryData['Type'] == 'picture':
        xbmc.log(f"EMBY.hooks.webservice: Load artwork data into cache: {Payload}", 0) # LOGDEBUG

        if add_DelayedContent(QueryData, client):
            return

        xbmc.log(f"EMBY.hooks.webservice: Load artwork data from Emby: {Payload}", 0) # LOGDEBUG

        if not QueryData['Overlay']:
            BinaryData, ContentType, _ = utils.EmbyServers[QueryData['ServerId']].API.get_Image_Binary(QueryData['EmbyId'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['ImageTag'])
        else:
            BinaryData, ContentType = utils.image_overlay(QueryData['ImageTag'], QueryData['ServerId'], QueryData['EmbyId'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['Overlay'])

        set_DelayedContent(QueryData['Payload'], f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(BinaryData)}\r\nContent-Type: {ContentType}\r\n\r\n".encode() + BinaryData)
        xbmc.log(f"EMBY.hooks.webservice: Loaded Delayed Content for {Payload}", 0) # LOGDEBUG
        return

    if QueryData['Type'] == 'audio':
        playerops.PlayerId = 0
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"audio/{QueryData['EmbyId']}/stream?static=true")
        return

    playerops.PlayerId = 1
    globals()['EmbyIdCurrentlyPlaying'] = QueryData['EmbyId']

    if QueryData['Type'] == 'tvchannel':
        MediasourceId, LiveStreamId, PlaySessionId, Container = utils.EmbyServers[QueryData['ServerId']].API.open_livestream(QueryData['EmbyId'])

        if not Container:
            xbmc.log("EMBY.hooks.webservice: LiveTV no container info", 3) # LOGERROR
            client.send(sendNotFound)
            return

        QueryData['MediaSources'][0][0]['Id'] = MediasourceId
        QueryData['LiveStreamId'] = LiveStreamId
        set_QueuedPlayingItem(QueryData, PlaySessionId)

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
                send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}&LiveStreamId={LiveStreamId}{TranscodingVideoBitrate}{TranscodingAudioBitrate}")
            else:
                send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}")
        else:
            if LiveStreamId:
                send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/stream?static=true&LiveStreamId={LiveStreamId}")
            else:
                send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/stream?static=true")

        return

    if QueryData['Type'] == 'channel':
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/main.m3u8")
        return

    player.PlayerEventsQueue.put((("play", f'{{"player":{{"playerid":{PlayerId}}}}}'),))

    # Cinnemamode
    if ((utils.enableCinemaMovies and QueryData['Type'] == "movie") or (utils.enableCinemaEpisodes and QueryData['Type'] == "episode")) and not utils.RemoteMode and not player.TrailerStatus == "PLAYING":
        if not QueryData['isDynamic']:
            videoDB = dbio.DBOpenRO("video", "http_Query")
            Progress = videoDB.get_Progress_by_KodiType_KodiId(QueryData['Type'], QueryData['KodiId'])
            dbio.DBCloseRO("video", "http_Query")
        else:
            Progress = 0

        if not Progress and player.TrailerStatus == "READY":
            player.playlistIndex = playerops.GetPlayerPosition(1)
            player.TrailerStatus = "PLAYING"
            utils.EmbyServers[QueryData['ServerId']].http.Intros = []
            globals()["TrailerInitItem"] = [QueryData['Payload'], None]
            PlayTrailer = True

            if add_DelayedContent(QueryData, client):
                return

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                utils.EmbyServers[QueryData['ServerId']].http.load_Trailers(QueryData['EmbyId'])

                if utils.EmbyServers[QueryData['ServerId']].http.Intros:
                    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
                    set_DelayedContent(QueryData['Payload'], "blank")
                    player.play_Trailer(utils.EmbyServers[QueryData['ServerId']])
                    globals()["TrailerInitItem"][1] = player.load_KodiItem("http_Query", QueryData['KodiId'], QueryData['Type'], None) # query path

                    # skip incoming content queries, until intros finished playing
                    if player.playlistIndex == 0:
                        player.SkipItem = (Payload, )
                    elif player.playlistIndex != -1:
                        PlaylistItems = playerops.GetPlaylistItems(1)

                        if PlaylistItems:
                            player.SkipItem = (Payload, PlaylistItems[0]['file'].replace("/emby_addon_mode", "").replace("http://127.0.0.1:57342", ""))
                        else:
                            player.SkipItem = (Payload, )

                    return

            xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
            set_DelayedContent(QueryData['Payload'], f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: http://127.0.0.1:57342{Payload}\r\nConnection: close\r\nContent-length: 0\r\n\r\n".encode())
            return

        if player.TrailerStatus == "CONTENT":
            player.TrailerStatus = "READY"

    if len(QueryData['MediaSources']) == 1 or utils.RemoteMode or (QueryData['MediaType'] in ("i", "v", "m") and not QueryData['isDynamic']):
        if QueryData['MediaType'] == 'i':
            if add_DelayedContent(QueryData, client):
                return

            LoadISO(QueryData, client)
            return

        LoadData(QueryData, client)
        return

    # Multiversion
    if add_DelayedContent(QueryData, client):
        return

    # Autoselect mediasource by highest resolution
    if utils.SelectDefaultVideoversion:
        QueryData['SelectionIndexMediaSource'] = 0
    elif utils.AutoSelectHighestResolution:
        HighestResolution = 0
        QueryData['SelectionIndexMediaSource'] = 0

        for MediaSourceIndex, MediaSource in enumerate(QueryData['MediaSources']):
            if HighestResolution < MediaSource[1][0]['Width']:
                HighestResolution = MediaSource[1][0]['Width']
                QueryData['SelectionIndexMediaSource'] = MediaSourceIndex
    else: # Manual select mediasource
        Selection = []

        for MediaSource in QueryData['MediaSources']:
            Selection.append(f"{MediaSource[0]['Name']} - {utils.SizeToText(float(MediaSource[0]['Size']))} - {MediaSource[0]['Path']}")

        QueryData['SelectionIndexMediaSource'] = utils.Dialog.select(utils.Translate(33453), Selection)

        if QueryData['SelectionIndexMediaSource'] == -1:
            set_DelayedContent(QueryData['Payload'], "blank")
            return

    # check if multiselection must be forced as native
    if QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Path'].lower().endswith(".iso"):
        LoadISO(QueryData, client)
        return

    LoadData(QueryData, client)
    return

# Load SRT subtitles
def SubTitlesAdd(QueryData):
    if not QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][3]:
        return

    CounterSubTitle = 0
    DefaultSubtitlePath = ""
    EnableSubtitle = False
    ExternalSubtitle = False

    for Subtitle in QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][3]:
        if Subtitle['external']:
            CounterSubTitle += 1
            ExternalSubtitle = True

            # Get Subtitle Settings
            if not QueryData['isDynamic']:
                videoDB = dbio.DBOpenRO("video", "http_Query")
                FileSettings = videoDB.get_FileSettings(QueryData['KodiFileId'])
                dbio.DBCloseRO("video", "http_Query")
            else:
                FileSettings = []

            if FileSettings:
                EnableSubtitle = bool(FileSettings[9])
            else:
                if DefaultVideoSettings:
                    EnableSubtitle = DefaultVideoSettings['ShowSubtitles']
                else:
                    EnableSubtitle = False

            if Subtitle['language']:
                SubtileLanguage = Subtitle['language']
            else:
                SubtileLanguage = "undefined"

            BinaryData = utils.EmbyServers[QueryData['ServerId']].API.get_Subtitle_Binary(QueryData['EmbyId'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Id'], Subtitle['Index'], Subtitle['Codec'])

            if QueryData['EmbyId'] != EmbyIdCurrentlyPlaying: # check if Kodi is still playing the same file
                del BinaryData
                return

            if BinaryData:
                SubtitleCodec = Subtitle['Codec']
                Path = f"{utils.FolderEmbyTemp}{utils.valid_Filename(f'{CounterSubTitle}.{SubtileLanguage}.{SubtitleCodec}')}"
                utils.writeFileBinary(Path, BinaryData)
                del BinaryData

                if DefaultVideoSettings["SubtitlesLanguage"].lower() in Subtitle['DisplayTitle'].lower():
                    DefaultSubtitlePath = Path

                    if DefaultVideoSettings["SubtitlesLanguage"].lower() == "forced_only" and "forced" in Subtitle['DisplayTitle'].lower():
                        DefaultSubtitlePath = Path
                    else:
                        playerops.AddSubtitle(Path)
                else:
                    playerops.AddSubtitle(Path)

    if ExternalSubtitle:
        if DefaultSubtitlePath:
            playerops.AddSubtitle(DefaultSubtitlePath)

        playerops.SetSubtitle(EnableSubtitle)

def LoadData(QueryData, client):
    Transcoding = False

    # Check transcoding
    if QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][1] and QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][2]:
        VideoCodec = QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][1][QueryData['SelectionIndexVideoStream']]['Codec']
        AudioCodec = QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][2][QueryData['SelectionIndexAudioStream']]['Codec']

        if utils.transcode_h264 and VideoCodec == "h264" or utils.transcode_hevc and VideoCodec == "hevc" or utils.transcode_av1 and VideoCodec == "av1" or utils.transcode_vp8 and VideoCodec == "vp8" or utils.transcode_vp9 and VideoCodec == "vp9" or utils.transcode_wmv3 and VideoCodec == "wmv3" or utils.transcode_mpeg4 and VideoCodec == "mpeg4" or utils.transcode_mpeg2video and VideoCodec == "mpeg2video" or utils.transcode_mjpeg and VideoCodec == "mjpeg" or utils.transcode_msmpeg4v3 and VideoCodec == "msmpeg4v3" or utils.transcode_msmpeg4v2 and VideoCodec == "msmpeg4v2" or utils.transcode_vc1 and VideoCodec == "vc1" or utils.transcode_prores and VideoCodec == "prores":
            QueryData['TranscodeReasons'] = "VideoCodecNotSupported"
            Transcoding = True

        if utils.transcode_aac and AudioCodec == "aac" or utils.transcode_mp3 and AudioCodec == "mp3" or utils.transcode_mp2 and AudioCodec == "mp2" or utils.transcode_dts and AudioCodec == "dts" or utils.transcode_ac3 and AudioCodec == "ac3" or utils.transcode_eac3 and AudioCodec == "eac3" or utils.transcode_pcm_mulaw and AudioCodec == "pcm_mulaw" or utils.transcode_pcm_s24le and AudioCodec == "pcm_s24le" or utils.transcode_vorbis and AudioCodec == "vorbis" or utils.transcode_wmav2 and AudioCodec == "wmav2" or utils.transcode_ac4 and AudioCodec == "ac4" or utils.transcode_pcm_s16le and AudioCodec == "pcm_s16le" or utils.transcode_aac_latm and AudioCodec == "aac_latm" or utils.transcode_dtshd_hra and AudioCodec == "dtshd_hra" or utils.transcode_dtshd_ma and AudioCodec == "dtshd_ma" or utils.transcode_truehd and AudioCodec == "truehd" or utils.transcode_opus and AudioCodec == "opus":
            if 'TranscodeReasons' in QueryData:
                QueryData['TranscodeReasons'] += ",AudioCodecNotSupported"
            else:
                QueryData['TranscodeReasons'] = "AudioCodecNotSupported"

            Transcoding = True

        if QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][1][QueryData['SelectionIndexVideoStream']]['BitRate'] >= utils.videoBitrate:
            if 'TranscodeReasons' in QueryData:
                QueryData['TranscodeReasons'] += ",ContainerBitrateExceedsLimit"
            else:
                QueryData.update({'TranscodeReasons': "ContainerBitrateExceedsLimit"})

            Transcoding = True

    # Stream content
    if not Transcoding:
        if QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['IsRemote']:  # remote content -> verify source
            StatusCode = utils.EmbyServers[QueryData['ServerId']].API.get_stream_statuscode(QueryData['EmbyId'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Id'])
            xbmc.log(f"EMBY.hooks.webservice: Remote content verification: {StatusCode}", 1) # LOGINFO

            if StatusCode != 200:
                set_QueuedPlayingItem(QueryData, None)
                send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/main.m3u8?VideoCodec={utils.TranscodeFormatVideo}&AudioCodec={utils.TranscodeFormatAudio}&TranscodeReasons=DirectPlayError")
                return

        utils.start_thread(SubTitlesAdd, (QueryData,))
        set_QueuedPlayingItem(QueryData, None)
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/stream?static=true")
        return

    # Transcoding content
    if len(QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][2]) > 1 and utils.transcode_select_audiostream:
        Selection = []

        for AudioStreams in QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][2]:
            Selection.append(AudioStreams['DisplayTitle'])

        QueryData['SelectionIndexAudioStream'] = utils.Dialog.select(heading=utils.Translate(33642), list=Selection)

    if len(QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][3]):  # Subtitle) >= 1:
        Selection = [utils.Translate(33702)]

        for SubTitle in QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][3]:  # Subtitle:
            Selection.append(SubTitle['DisplayTitle'])

        QueryData['SelectionIndexSubtitleStream'] = utils.Dialog.select(heading=utils.Translate(33484), list=Selection) - 1

    QueryData['SelectionIndexAudioStream'] = max(QueryData['SelectionIndexAudioStream'], 0)

    if QueryData['SelectionIndexSubtitleStream'] >= 0:
        utils.start_thread(SubTitlesAdd, (QueryData,))

    TranscodingAudioBitrate = f"&AudioBitrate={utils.audioBitrate}"
    TranscodingVideoBitrate = f"&VideoBitrate={utils.videoBitrate}"

    if QueryData['SelectionIndexSubtitleStream'] != -1:
        Subtitle = f"&SubtitleStreamIndex={QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][3][QueryData['SelectionIndexSubtitleStream']]['Index']}"
    else:
        Subtitle = ""

    Audio = f"&AudioStreamIndex={QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][2][QueryData['SelectionIndexAudioStream']]['Index']}"

    if 'VideoCodecNotSupported' in QueryData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in QueryData['TranscodeReasons']:
        TranscodingVideoCodec = f"&VideoCodec={utils.TranscodeFormatVideo}"
    else:
        TranscodingVideoCodec = "&VideoCodec=copy"

    if 'AudioCodecNotSupported' in QueryData['TranscodeReasons'] or 'ContainerBitrateExceedsLimit' in QueryData['TranscodeReasons']:
        TranscodingAudioCodec = f"&AudioCodec={utils.TranscodeFormatAudio}"
    else:
        TranscodingAudioCodec = "&AudioCodec=copy"

    set_QueuedPlayingItem(QueryData, None)
    send_redirect(client, QueryData, f"videos/{QueryData['EmbyId']}/main.m3u8?TranscodeReasons={QueryData['TranscodeReasons']}{TranscodingVideoCodec}{TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}{Audio}{Subtitle}")

def send_delayed_content(client, ContentId):
    xbmc.log(f"EMBY.hooks.webservice: send_delay_content: {ContentId}", 0) # DEBUGINFO
    DelayedContentLock.acquire()

    if ContentId in DelayedContent:
        DC = DelayedContent[ContentId][0]
        DelayedContentLock.release()

        if DC:
            xbmc.log(f"EMBY.hooks.webservice: Content available: {ContentId}", 0) # DEBUGINFO

            if DC == "blank":
                send_BlankWAV(client, ContentId)
            else:
                client.send(DC)

            # Things could have changed by other threads since the check at the top so check again
            with DelayedContentLock:
                if ContentId in DelayedContent:
                    globals()['DelayedContent'][ContentId][1] -= 1

                    if DelayedContent[ContentId][1] < 0:
                        del globals()['DelayedContent'][ContentId]

            return True

        return False

    DelayedContentLock.release()
    xbmc.log(f"EMBY.hooks.webservice: Delayed content not found {ContentId}", 3) # LOGERROR
    client.send(sendNotFound)
    return True

def set_QueuedPlayingItem(QueryData, PlaySessionId):
    utils.PlayerBusy = True

    # Disable delete after watched option for multicontent
    if QueryData['SelectionIndexMediaSource'] != 0:
        FilePath = ""
    else:
        FilePath = QueryData['MediaSources'][0][0]['Path']

    if PlaySessionId:
        QueryData['PlaySessionId'] = PlaySessionId
        player.QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(QueryData['EmbyId']), 'MediaSourceId': QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Id'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'PlaybackRate': player.PlaybackRate[playerops.PlayerId], 'Shuffle': player.Shuffled[playerops.PlayerId], 'RepeatMode': player.RepeatMode[playerops.PlayerId], 'IsMuted': player.Muted, 'PlaySessionId': QueryData['PlaySessionId'], "LiveStreamId": QueryData['LiveStreamId']}, QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['IntroStartPositionTicks'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['IntroEndPositionTicks'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['CreditsPositionTicks'], utils.EmbyServers[QueryData['ServerId']], playerops.PlayerId, QueryData['Type'], FilePath]
    else:
        QueryData['PlaySessionId'] = str(uuid.uuid4()).replace("-", "")
        player.QueuedPlayingItem = [{'QueueableMediaTypes': ["Audio", "Video", "Photo"], 'CanSeek': True, 'IsPaused': False, 'ItemId': int(QueryData['EmbyId']), 'MediaSourceId': QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['Id'], 'PositionTicks': 0, 'RunTimeTicks': 0, 'VolumeLevel': player.Volume, 'PlaybackRate': player.PlaybackRate[playerops.PlayerId], 'Shuffle': player.Shuffled[playerops.PlayerId], 'RepeatMode': player.RepeatMode[playerops.PlayerId], 'IsMuted': player.Muted, 'PlaySessionId': QueryData['PlaySessionId']}, QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['IntroStartPositionTicks'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['IntroEndPositionTicks'], QueryData['MediaSources'][QueryData['SelectionIndexMediaSource']][0]['CreditsPositionTicks'], utils.EmbyServers[QueryData['ServerId']], playerops.PlayerId, QueryData['Type'], FilePath]

def add_DelayedContent(QueryData, client):
    if not QueryData['DelayedContentSet']:
        QueryData['DelayedContentSet'] = True

        with DelayedContentLock:
            if QueryData['Payload'] in DelayedContent:
                globals()['DelayedContent'][QueryData['Payload']][1] += 1
                Added = True
            else:
                globals()['DelayedContent'][QueryData['Payload']] = [None, 0]
                Added = False

        client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: http://127.0.0.1:57342/delayed_content{QueryData['Payload']}\r\nContent-length: 0\r\n\r\n".encode())
        client.close()
        return Added

    return False

def set_DelayedContent(ContentId, Data):
    with DelayedContentLock:
        globals()['DelayedContent'][ContentId][0] = Data

def send_head_response(client, Type):
    if Type == "picture":
        client.send('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\nContent-Type: image/unknown\r\n\r\n'.encode())
    elif Type in ("audio", "specialaudio"):
        client.send('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\nContent-Type: audio/unknown\r\n\r\n'.encode())
    else:
        client.send('HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\nContent-Type: video/unknown\r\n\r\n'.encode())

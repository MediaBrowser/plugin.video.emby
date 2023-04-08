import socket
from _thread import start_new_thread, get_ident
import xbmc
ModulesLoaded = False
DefaultVideoSettings = {}
MediaIdMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "A": "specialaudio", "V": "specialvideo", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
sendOK = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
sendNoContent = 'HTTP/1.1 404 Not Found\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 0\r\n\r\n'.encode()
BlankWAV = b'\x52\x49\x46\x46\x25\x00\x00\x00\x57\x41\x56\x45\x66\x6d\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00\x64\x61\x74\x61\x74\x00\x00\x00\x00'
sendBlankWAV = 'HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-length: 45\r\nContent-type: audio/wav\r\n\r\n'.encode() + BlankWAV # used to "stop" playback by sending a WAV file with silence. File is valid, so Kodi will not raise an error message
SkipItemVideo = ""
TrailerInitItem = ["", None] # payload/listitem of the trailer initiated content item
Cancel = False
embydb = {}
QueryDataPrevious = {}
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
LiveTVEPGCache = ("", 0)
LiveTVM3UCache = ("", 0)
Socket = None

def start():
    globals()['Socket'] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    globals()['Socket'].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    globals()['Socket'].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    globals()['Socket'].bind(('127.0.0.1', 57342))
    globals()['Socket'].settimeout(None)
    xbmc.log("EMBY.hooks.webservice: Start", 1) # LOGINFO
    globals()["Running"] = True
    start_new_thread(Listen, ())

def close():
    if Running:
        globals()["Running"] = False

        try:
            try:
                Socket.shutdown(socket.SHUT_RDWR)
            except Exception as Error:
                xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 3) # LOGERROR

            Socket.close()
            xbmc.log("EMBY.hooks.webservice: Socket shutdown", 3) # LOGERROR
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket close (error) {Error}", 3) # LOGERROR


        xbmc.log("Shutdown weservice", 1) # LOGINFO

def Listen():
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ webservice/57342 ]", 1) # LOGINFO
    Socket.listen()

    while True:
        try:
            client, _ = Socket.accept()
            start_new_thread(worker_Query, (client,))
        except Exception as Error:
            xbmc.log(f"EMBY.hooks.webservice: Socket shutdown (error) {Error}", 3) # LOGERROR
            break

    xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ webservice/57342 ]", 1) # LOGINFO

def worker_Query(client):  # thread by caller
    xbmc.log("EMBY.hooks.webservice: THREAD: --->[ worker_Query ]", 0) # LOGDEBUG
    client.settimeout(None)
    data = client.recv(1024).decode()
    DelayQuery = 0

    # Waiting for socket init
    while not ModulesLoaded:
        xbmc.sleep(100)

    while not utils.EmbyServers:
        Break = False

        if utils.PluginStarted:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, skip query", 1) # LOGINFO
            Break = True

        if utils.sleep(1):
            xbmc.log("EMBY.hooks.webservice: Kodi Shutdown", 1) # LOGINFO
            Break = True

        if DelayQuery >= 60:
            xbmc.log("EMBY.hooks.webservice: No Emby servers found, delay query", 1) # LOGINFO
            Break = True

        if Break:
            xbmc.log("Terminate query", 3) # LOGERROR
            client.send(sendNoContent)
            client.close()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event skinreload", 0) # LOGDEBUG
            return

        DelayQuery += 1

    IncomingData = data.split(' ')

    # events by event.py
    if IncomingData[0] == "EVENT":
        args = IncomingData[1].split(";")

        # contextmenu (via addon.xml)
        if args[1] == "contextmenu":
            client.send(sendOK)
            client.close()
            context.select_menu(urllibparse.unquote(args[len(args) - 1]))
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event contextmenu", 0) # LOGDEBUG
            return

        if args[1] == "specials":
            client.send(sendOK)
            client.close()
            context.specials()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event specials", 0) # LOGDEBUG
            return

        if args[1] == "record":
            client.send(sendOK)
            client.close()
            context.Record()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event record", 0) # LOGDEBUG
            return

        # no delay
        Handle = args[1]
        params = dict(urllibparse.parse_qsl(args[2][1:]))
        mode = params.get('mode')
        ServerId = params.get('server')

        if mode == 'settings':  # Simple commands
            client.send(sendOK)
            client.close()
            xbmc.executebuiltin(f'Addon.OpenSettings({utils.PluginId})')
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

        if mode == 'reset_device_id':  # Simple commands
            client.send(sendOK)
            client.close()
            pluginmenu.reset_device_id()
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event reset_device_id", 0) # LOGDEBUG
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
            data = data.replace('[', "").replace(']', "").replace('"', "").replace('"', "").split(",")
            playerops.PlayEmby((data[1],), "PlayNow", -1, -1, utils.EmbyServers[data[0]])
            xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event play", 0) # LOGDEBUG
            return

        # wait for loading
        if mode == 'browse':
            query = params.get("query")

            if query:
                pluginmenu.browse(Handle, params.get('id'), query, params.get('arg'), ServerId)
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
        xbmc.log("EMBY.hooks.webservice: THREAD: ---<[ worker_Query ] event browse", 0) # LOGDEBUG
        return

    if 'extrafanart' in IncomingData[1] or 'extrathumbs' in IncomingData[1] or 'Extras/' in IncomingData[1] or 'favicon.ico' in IncomingData[1] or IncomingData[1].endswith('.edl') or IncomingData[1].endswith('.txt') or IncomingData[1].endswith('.Vprj') or IncomingData[1].endswith('.xml') or IncomingData[1].endswith('/') or IncomingData[1].endswith('folder.jpg') or IncomingData[1].endswith('.nfo'):
        client.send(sendNoContent)
    elif IncomingData[0] == "GET":
        http_Query(client, IncomingData[1])
    elif IncomingData[0] == "HEAD":
        if IncomingData[1].startswith('/picture/'):
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
        add_playlist_item(client, ListItem, QueryData, Path)

    close_embydb(QueryData['ServerId'], ThreadId)

def send_BlankWAV(client):
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    client.send(sendBlankWAV)

def build_Path(QueryData, Data, Filename):
    if Filename:
        Filename = f"&{Filename}"

    if "?" in Data:
        Parameter = "&"
    else:
        Parameter = "?"

    if QueryData['MediasourceID']:
        Path = f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}MediaSourceId={QueryData['MediasourceID']}&PlaySessionId={player.PlaySessionId}&DeviceId={utils.device_id}&api_key={utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken']}{Filename}"
    else:
        Path = f"{utils.EmbyServers[QueryData['ServerId']].ServerData['ServerUrl']}/emby/{Data}{Parameter}PlaySessionId={player.PlaySessionId}&DeviceId={utils.device_id}&api_key={utils.EmbyServers[QueryData['ServerId']].ServerData['AccessToken']}{Filename}"

    return Path

def send_redirect(client, QueryData, Data, Filename):
    Path = build_Path(QueryData, Data, Filename)
    xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
    client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nLocation: {Path}\r\nContent-length: 0\r\n\r\n".encode())

def http_Query(client, Payload):
    if Payload == '/livetv/m3u':
        _, UnixTime = utils.currenttime_kodi_format_and_unixtime()

        if not LiveTVM3UCache[0] or LiveTVM3UCache[1] < UnixTime - 600: # Use cache for queries < 10 minutes
            playlist = "#EXTM3U\n"

            for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                Channels = EmbyServer.API.get_channels()

                for item in Channels:
                    if item['TagItems']:
                        Tag = item['TagItems'][0]['Name']
                    else:
                        Tag = "--No Info--"

                    ImageUrl = ""

                    if item['ImageTags']:
                        if 'Primary' in item['ImageTags']:
                            ImageUrl = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-0-p-{item['ImageTags']['Primary']}"

                    StreamUrl = f"http://127.0.0.1:57342/dynamic/{ServerId}/t-{item['Id']}-livetv"

                    if item['Name'].lower().find("radio") != -1 or item['MediaType'] != "Video":
                        playlist += f'#EXTINF:-1 tvg-id="{item["Id"]}" tvg-name="{item["Name"]}" tvg-logo="{ImageUrl}" radio="true" group-title="{Tag}",{item["Name"]}\n'
                    else:
                        playlist += f'#EXTINF:-1 tvg-id="{item["Id"]}" tvg-name="{item["Name"]}" tvg-logo="{ImageUrl}" group-title="{Tag}",{item["Name"]}\n'

                    playlist += f"{StreamUrl}\n"


            playlist = playlist.encode()
            globals()["LiveTVM3UCache"] = (playlist, UnixTime)
        else:
            xbmc.log("EMBY.hooks.webservice: Use M3U cache", 1) # LOGINFO
            playlist = LiveTVM3UCache[0]

        client.send(f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(playlist)}\r\nContent-Type: text/plain\r\n\r\n".encode() + playlist)
        return

    if Payload == '/livetv/epg':
        _, UnixTime = utils.currenttime_kodi_format_and_unixtime()

        if not LiveTVEPGCache[0] or LiveTVEPGCache[1] < UnixTime - 600: # Use cache for queries < 10 minutes
            epg = '<?xml version="1.0" encoding="utf-8" ?><tv>'

            for ServerId, EmbyServer in list(utils.EmbyServers.items()):
                for item in EmbyServer.API.get_channelprogram():
                    temp = item['StartDate'].split("T")
                    timestampStart = temp[0].replace("-", "")
                    temp2 = temp[1].split(".")
                    timestampStart += temp2[0].replace(":", "")[:6]
                    temp2 = temp2[1].split("+")

                    if len(temp2) > 1:
                        timestampStart += f"+{temp2[1].replace(':', '')}"

                    temp = item['EndDate'].split("T")
                    timestampEnd = temp[0].replace("-", "")
                    temp2 = temp[1].split(".")
                    timestampEnd += temp2[0].replace(":", "")[:6]
                    temp2 = temp2[1].split("+")

                    if len(temp2) > 1:
                        timestampEnd += f"+{temp2[1].replace(':', '')}"

                    epg += f'<channel id="{item["ChannelId"]}"><display-name lang="en">{item["ChannelId"]}</display-name></channel><programme start="{timestampStart}" stop="{timestampEnd}" channel="{item["ChannelId"]}"><title lang="en">{item["Name"]}</title>'

                    if 'Overview' in item:
                        item["Overview"] = item["Overview"].replace("<", "(").replace(">", ")")
                        epg += f'<desc lang="en">{item["Overview"]}</desc>'

                    epg += f'<icon src="{ServerId}Z{item["Id"]}"/></programme>' # rape icon -> assign serverId and programId

            epg += '</tv>'
            epg = epg.encode()
            globals()["LiveTVEPGCache"] = (epg, UnixTime)
        else:
            xbmc.log("EMBY.hooks.webservice: Use EPG cache", 1) # LOGINFO
            epg = LiveTVEPGCache[0]

        client.send(f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {len(epg)}\r\nContent-Type: text/plain\r\n\r\n".encode() + epg)
        return

    if 'main.m3u8' in Payload:  # Dynamic Transcode query
        player.queuePlayingItem(QueryDataPrevious['EmbyID'], QueryDataPrevious['MediasourceID'], QueryDataPrevious['IntroStartPositionTicks'], QueryDataPrevious['IntroEndPositionTicks'], QueryDataPrevious['CreditsPositionTicks'])
        xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
        client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: {utils.EmbyServers[QueryDataPrevious['ServerId']].ServerData['ServerUrl']}/emby/videos/{QueryDataPrevious['EmbyID']}{Payload}\r\nConnection: close\r\nContent-length: 0\r\n\r\n".encode())
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

    # Workaround for invalid Kodi GET requests when played via widget
    if utils.usekodiworkarounds:
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
        QueryData = {'MediasourceID': None, 'MediaSources': [], 'Payload': Payload, 'Type': MediaIdMapping[Data[0]], 'ServerId': Folder[2], 'EmbyID': Data[1], 'IntroStartPositionTicks': 0, 'IntroEndPositionTicks': 0, 'CreditsPositionTicks': 0, 'MediaType': Data[0]}
    except Exception as Error: # data from older versions are no compatible
        xbmc.log(f"EMBY.hooks.webservice: Incoming data (error) {Error}", 3) # LOGERROR
        xbmc.log(f"EMBY.hooks.webservice: Incoming data (error) {Payload}", 0) # LOGDEBUG
        client.send(sendNoContent)
        return

    if Data[0] == "p":  # Image/picture
        QueryData.update({'ImageIndex': Data[2], 'ImageType': EmbyArtworkIDs[Data[3]], 'ImageTag': Data[4]})

        if QueryData['ImageType'] == "Chapter":
            QueryData['Overlay'] = urllibparse.unquote(Data[5])
        else:
            QueryData['Overlay'] = ""
    elif Data[0] in ("e", "m", "M", "i", "T", "v"):  # Video or iso
        playerops.PlayerId = 1
        QueryData.update({'MediasourceID': Data[2], 'KodiId': Data[3], 'KodiFileId': Data[4], 'ExternalSubtitle': Data[5], 'MediasourcesCount': int(Data[6]), 'IntroStartPositionTicks': int(Data[7]), 'IntroEndPositionTicks': int(Data[8]), 'CreditsPositionTicks': int(Data[9]), 'Remote': int(Data[10]), 'VideoCodec': Data[11], 'VideoBitrate': int(Data[12]), 'AudioCodec': Data[13], 'AudioBitrate': int(Data[14]), 'Filename': Data[15]})
        globals()["QueryDataPrevious"] = QueryData.copy()

        if "/dynamic/" in Payload:
            QueryData['MediasourcesCount'] = 1

        player.PlaylistRemoveItem = -1
    elif Data[0] == "a":  # Audio
        playerops.PlayerId = 0
        QueryData.update({'Filename': Data[2]})
    elif Data[0] == "t":  # tv channel
        playerops.PlayerId = 1
        QueryData.update({'Filename': Data[2]})
    elif Data[0] == "c":  # e.g. channel
        playerops.PlayerId = 1
        QueryData.update({'MediasourceID': Data[2], 'Filename': Data[3]})
        globals()["QueryDataPrevious"] = QueryData.copy()
    else:
        QueryData.update({'MediasourceID': Data[2], 'Filename': Data[3]})

    if QueryData['ServerId'] not in utils.EmbyServers:
        client.send(sendOK)
        return

    # pictures
    if QueryData['Type'] == 'picture':
        if Payload not in ArtworkCache[1]:
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
                BinaryData = utils.image_overlay(QueryData['ImageTag'], QueryData['ServerId'], QueryData['EmbyID'], QueryData['ImageType'], QueryData['ImageIndex'], QueryData['Overlay'])
                ContentType = "image/jpeg"

            ContentSize = len(BinaryData)
            globals()["ArtworkCache"][0] += ContentSize
            globals()["ArtworkCache"][1][Payload] = (f"HTTP/1.1 200 OK\r\nServer: Emby-Next-Gen\r\nConnection: close\r\nContent-Length: {ContentSize}\r\nContent-Type: {ContentType}\r\n\r\n".encode(), BinaryData, ContentSize)
        else:
            xbmc.log(f"EMBY.hooks.webservice: Load artwork data from cache: {Payload}", 0) # LOGDEBUG

        client.send(ArtworkCache[1][Payload][0] + ArtworkCache[1][Payload][1])
        return

    if not utils.syncduringplayback or playerops.WatchTogether:
        utils.SyncPause['playing'] = True

    player.EmbyServerPlayback = utils.EmbyServers[QueryData['ServerId']]

    if QueryData['Type'] == 'specialaudio':
        send_redirect(client, QueryData, f"audio/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'])
        return

    if QueryData['Type'] == 'specialvideo':
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'])
        return

    if QueryData['Type'] == 'audio':
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
        send_redirect(client, QueryData, f"audio/{QueryData['EmbyID']}/stream?static=true", QueryData['Filename'])
        return

    if QueryData['Type'] == 'tvchannel':
        MediasourceID, LiveStreamId, Container = utils.EmbyServers[QueryData['ServerId']].API.open_livestream(QueryData['EmbyID'], player.PlaySessionId)

        if MediasourceID == "FAIL":
            client.send(sendNoContent)
            return

        QueryData['MediasourceID'] = MediasourceID
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'], LiveStreamId)

        if utils.transcode_livetv_video or utils.transcode_livetv_audio:
            if utils.transcode_livetv_video:
                TranscodingVideoCodec = utils.TranscodeFormatVideo
            else:
                TranscodingVideoCodec = "copy"

            if utils.transcode_livetv_audio:
                TranscodingAudioCodec = utils.TranscodeFormatAudio
            else:
                TranscodingAudioCodec = "copy"

            send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream.ts?VideoCodec={TranscodingVideoCodec}&AudioCodec={TranscodingAudioCodec}", "stream.ts")
        else:
            send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/stream?static=true", f"livetv.{Container}")

        return

    if QueryData['Type'] == 'channel':
        player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
        send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/master.m3u8", "stream.ts")
        return

    # Cinnemamode
    if ((utils.enableCinemaMovies and QueryData['Type'] == "movie") or (utils.enableCinemaEpisodes and QueryData['Type'] == "episode")) and not playerops.RemoteMode:
        if TrailerInitItem[0] != QueryData['Payload']:  # Trailer init (load)
            utils.EmbyServers[QueryData['ServerId']].http.Intros = []
            globals()["TrailerInitItem"] = [QueryData['Payload'], None]
            PlayTrailer = True

            if utils.askCinema:
                PlayTrailer = utils.Dialog.yesno(heading=utils.addon_name, message=utils.Translate(33016), autoclose=int(utils.autoclose) * 1000)

            if PlayTrailer:
                utils.EmbyServers[QueryData['ServerId']].http.load_Trailers(QueryData['EmbyID'])

        if utils.EmbyServers[QueryData['ServerId']].http.Intros:
            globals()["TrailerInitItem"][1] = player.load_KodiItem("http_Query", QueryData['KodiId'], QueryData['Type'], None) # query path
            player.SkipItem = True
            playerops.SetRepeatOneTime()
            URL = utils.EmbyServers[QueryData['ServerId']].http.Intros[0]['Path']
            xbmc.log(f"EMBY.hooks.webservice: Trailer URL: {URL}", 0) # LOGDEBUG
            ListItem = listitem.set_ListItem(utils.EmbyServers[QueryData['ServerId']].http.Intros[0], QueryData['ServerId'], utils.AddonModePath + QueryData['Payload'][1:])
            del utils.EmbyServers[QueryData['ServerId']].http.Intros[0]
            xbmc.executebuiltin('Dialog.Close(busydialog,true)') # workaround due to Kodi bug: https://github.com/xbmc/xbmc/issues/16756
            client.send(f"HTTP/1.1 307 Temporary Redirect\r\nServer: Emby-Next-Gen\r\nLocation: {URL}\r\nConnection: close\r\nContent-length: 0\r\n\r\n".encode())
            utils.XbmcPlayer.updateInfoTag(ListItem)
            return

        playerops.SetRepeatOff()

        if TrailerInitItem[1]:
            utils.XbmcPlayer.updateInfoTag(TrailerInitItem[1])

    globals()["PayloadHeadRequest"] = ""
    player.SkipItem = False
    ThreadId = get_ident()

    # Play Kodi synced item
    if QueryData['KodiId']:  # Item synced to Kodi DB
        if QueryData['MediasourcesCount'] == 1 or playerops.RemoteMode:
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
            Selection.append(f"{Data[4]} - {utils.SizeToText(float(Data[5]))} - {Data[3]}")

        MediaIndex = utils.Dialog.select(utils.Translate(33453), Selection)

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

    if IsTranscoding(QueryData):
        URL = GETTranscodeURL(False, False, QueryData)
    else:
        URL = f"videos/{QueryData['EmbyID']}/stream?static=true"

    player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
    send_redirect(client, QueryData, URL, QueryData['Filename'])
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

            player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
            URL = f"videos/{QueryData['EmbyID']}/stream?static=true"

            if QueryData['Remote']:  # remote content -> verify source
                status_code = utils.EmbyServers[QueryData['ServerId']].API.get_stream_statuscode(QueryData['EmbyID'], QueryData['MediasourceID'], player.PlaySessionId)
                xbmc.log(f"EMBY.hooks.webservice: Remote content verification: {status_code}", 1) # LOGINFO

                if status_code != 200:
                    send_redirect(client, QueryData, f"videos/{QueryData['EmbyID']}/master.m3u8?VideoCodec={utils.TranscodeFormatVideo}&AudioCodec={utils.TranscodeFormatAudio}&TranscodeReasons=DirectPlayError", QueryData['Filename'])
                    return

            send_redirect(client, QueryData, URL, QueryData['Filename'])
            return
    else:
        VideoStreams = open_embydb(QueryData['ServerId'], ThreadId).get_videostreams(QueryData['EmbyID'], MediaIndex)
        AudioStreams = open_embydb(QueryData['ServerId'], ThreadId).get_AudioStreams(QueryData['EmbyID'], MediaIndex)
        QueryData.update({'KodiId': str(embydb[ThreadId].get_kodiid(QueryData['EmbyID'])[0]), 'VideoBitrate': int(VideoStreams[0][4]), 'VideoCodec': VideoStreams[0][3], 'AudioCodec': AudioStreams[0][4], 'AudioBitrate': int(AudioStreams[0][5])})
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
            Selection = []

            for Data in Subtitles:
                Selection.append(Data[5])

            close_embydb(QueryData['ServerId'], ThreadId) # close db before waiting for input
            SubtitleIndex = utils.Dialog.select(heading=utils.Translate(33484), list=Selection)

        if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0:  # No change, just transcoding
            URL = GETTranscodeURL(False, False, QueryData)
            player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
            send_redirect(client, QueryData, URL, QueryData['Filename'])
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

    if "3d" in MediaSource[4].lower():
        # inject new playlist item (not update curerent playlist item to initiate 3d selection popup msg
        Path = build_Path(QueryData, URL, Filename)
        ListItem = player.load_KodiItem("UpdateItem", QueryData['KodiId'], QueryData['Type'], Path)

        if not ListItem:
            client.send(sendOK)
            close_embydb(QueryData['ServerId'], ThreadId)
            return

        add_playlist_item(client, ListItem, QueryData, Path)
        close_embydb(QueryData['ServerId'], ThreadId)
        return

    SubTitlesAdd(MediaIndex, QueryData, ThreadId)
    player.queuePlayingItem(QueryData['EmbyID'], QueryData['MediasourceID'], QueryData['IntroStartPositionTicks'], QueryData['IntroEndPositionTicks'], QueryData['CreditsPositionTicks'])
    send_redirect(client, QueryData, URL, Filename)
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

    return f"videos/{QueryData['EmbyID']}/master.m3u8?TranscodeReasons={QueryData['TranscodeReasons']}{TranscodingVideoCodec}{TranscodingAudioCodec}{TranscodingVideoBitrate}{TranscodingAudioBitrate}{Audio}{Subtitle}"

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

def add_playlist_item(client, ListItem, QueryData, Path):
    player.replace_playlist_listitem(ListItem, QueryData, Path)
    globals()["SkipItemVideo"] = QueryData['Payload']
    send_BlankWAV(client)

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
    xbmc.log("EMBY.hooks.webservice: --<[ Init ]", 1) # LOGINFO

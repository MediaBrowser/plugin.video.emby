from urllib.parse import unquote
import xbmc

MediaIdMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "audio", "t": "tvchannel", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
MediaSourceContextMenu = -1

def load_MetaData(Payload, isPicture, isAudio):
    MetaData = {'isDynamic': False, 'isHttp': False}
    PayloadMod = Payload

    if PayloadMod.startswith("/dynamic/"):
        MetaData['isDynamic'] = True
        PayloadMod = PayloadMod.replace("/dynamic", "")

    if PayloadMod.startswith("/http/"):
        MetaData['isHttp'] = True
        PayloadMod = PayloadMod.replace("/http", "")

    PayloadSplit = PayloadMod.split("/")
    MediaSources = []

    if isPicture:  # Image/picture
        MetaData["PlayerId"] = -1
        Data = PayloadMod[PayloadMod.rfind("/") + 1:].split("-") # MetaData
        ServerId = PayloadSplit[2]
        EmbyId = Data[1]
        DataLen = len(Data)

        if DataLen < 5:
            xbmc.log(f"EMBY.hooks.webservice: Invalid picture {PayloadMod}", 2) # LOGERROR
            return {}

        MetaData.update({'ImageIndex': Data[2], 'ImageType': EmbyArtworkIDs[Data[3]], 'ImageTag': Data[4]})

        if DataLen >= 6 and Data[5]:
            MetaData['Overlay'] = unquote(Data[5])
        else:
            MetaData['Overlay'] = ""
    elif isAudio:
        MetaData["PlayerId"] = 0
        Data = PayloadMod[PayloadMod.rfind("/") + 1:].split("-") # MetaData
        ServerId = PayloadSplit[2]
        EmbyId = Data[1]
        MediaSources = [[{'Id': Data[2], 'IntroStartPositionTicks': 0, 'IntroEndPositionTicks': 0, 'CreditsPositionTicks': 0, 'Path': ""}, [], [], []]]
    else:
        MetaData["PlayerId"] = 1
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

        MetaData.update({'KodiId': Data[1], 'KodiFileId': Data[2]})

    MetaData.update({'MediaSources': MediaSources, 'Payload': Payload, 'Type': MediaIdMapping[Data[0]], 'ServerId': ServerId, 'EmbyId': EmbyId, 'MediaType': Data[0], "DelayedContentSet": False, "SelectionIndexMediaSource": 0, "SelectionIndexVideoStream": 0, "SelectionIndexAudioStream": 0, "SelectionIndexSubtitleStream": -1})
    return MetaData

import xbmc
from helper import utils

MediaIdMapping = {"m": "movie", "e": "episode", "M": "musicvideo", "p": "picture", "a": "song", "t": "tvchannel", "i": "movie", "T": "video", "v": "video", "c": "channel"} # T=trailer, i=iso
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
        Data = PayloadMod.split('/', 3)
        PosSlash = Data[3].find("/")

        if PosSlash != -1:
            Data = Data[3][:PosSlash] # MetaData
        else:
            Data = Data[3]

        Data = Data.split("-") # MetaData

        if len(Data) < 7:
            xbmc.log(f"EMBY.hooks.webservice: Invalid picture {PayloadMod}", 2) # LOGERROR
            return {}

        ServerId = PayloadSplit[2]
        EmbyId = Data[1]
        MetaData['Overlay'] = utils.image_text_decode(Data[5])
        _, Format = utils.get_MimeType(Data[6])
        MetaData.update({'ImageIndex': Data[2], 'ImageType': EmbyArtworkIDs[Data[3]], 'ImageTag': Data[4], 'KodiType': "picture", 'Format': Format})
    else:
        if isAudio:
            MetaData["PlayerId"] = 0
            MetaData["EmbyStreamType"] = "audio"
        else:
            MetaData["PlayerId"] = 1
            MetaData["EmbyStreamType"] = "videos"

        EmbyId = PayloadSplit[-3]
        ServerId = PayloadSplit[-6]
        Data = PayloadSplit[-2]
        Data = Data.split("-")
        Data[4] = bytes.fromhex(Data[4]).decode('utf-8')
        MetaData.update({'KodiId': Data[1], 'KodiFileId': Data[2]})

        # Extract metatdata, sperators are <>, ><, <<, :
        MetadataSubs = Data[4].split("<>")

        for Index, MetadataSub in enumerate(MetadataSubs):
            KodiStreamVideoIndex = 0
            KodiStreamAudioIndex = 0
            KodiStreamSubtitleIndex = 0
            MediaDatas = MetadataSub.split("<<")
            MediaSources.append([{}, [], [], []])

            for IndexSub, MediaData in enumerate(MediaDatas):
                if IndexSub == 0:
                    MediaSourceInfos = MediaData.split(":")
                    MediaSources[Index][0]['IndexMappingVideoEmby'] = {}
                    MediaSources[Index][0]['IndexMappingAudioEmby'] = {}
                    MediaSources[Index][0]['IndexMappingSubtitleEmby'] = {}
                    MediaSources[Index][0]['IndexMappingVideoKodi'] = {}
                    MediaSources[Index][0]['IndexMappingAudioKodi'] = {}
                    MediaSources[Index][0]['IndexMappingSubtitleKodi'] = {}

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
                                MediaSources[Index][0]['IndexMappingVideoEmby'][str(VideoStreamInfo)] = KodiStreamVideoIndex
                                MediaSources[Index][0]['IndexMappingVideoKodi'][KodiStreamVideoIndex] = str(VideoStreamInfo)
                                KodiStreamVideoIndex += 1
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
                                MediaSources[Index][0]['IndexMappingAudioEmby'][str(AudioStreamInfo)] = KodiStreamAudioIndex
                                MediaSources[Index][0]['IndexMappingAudioKodi'][KodiStreamAudioIndex] = str(AudioStreamInfo)
                                KodiStreamAudioIndex += 1
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
                                MediaSources[Index][0]['IndexMappingSubtitleEmby'][str(SubtitleStreamInfo)] = KodiStreamSubtitleIndex
                                MediaSources[Index][0]['IndexMappingSubtitleKodi'][KodiStreamSubtitleIndex] = str(SubtitleStreamInfo)
                                KodiStreamSubtitleIndex += 1
                            elif SubtitleStreamInfoIndex == 4:
                                MediaSources[Index][3][SubtitleStreamIndex]['Codec'] = SubtitleStreamInfo
                            elif SubtitleStreamInfoIndex == 5:
                                MediaSources[Index][3][SubtitleStreamIndex]['Forced'] = bool(int(SubtitleStreamInfo))

    MetaData.update({'MediaSources': MediaSources, 'Payload': Payload, 'KodiType': MediaIdMapping[Data[0]], 'ServerId': ServerId, 'EmbyId': EmbyId, 'MediaType': Data[0], "DelayedContentSet": False, "SelectionIndexMediaSource": 0, "SelectionIndexVideoStream": 0, "SelectionIndexAudioStream": 0, "SelectionIndexSubtitleStream": -1})
    return MetaData

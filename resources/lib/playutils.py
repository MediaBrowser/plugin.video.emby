# -*- coding: utf-8 -*-

#################################################################################################

import xbmc
import xbmcgui
import xbmcvfs

import clientinfo
import utils

import PlexAPI

#################################################################################################


@utils.logging
class PlayUtils():
    
    
    def __init__(self, item):

        self.item = item
        self.API = PlexAPI.API(item)

        self.clientInfo = clientinfo.ClientInfo()

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)
        self.machineIdentifier = utils.window('plex_machineIdentifier')

    def getPlayUrl(self):
        """
        Returns a list of playurls, one per part in item
        """
        playurls = []
        for partNumber, part in enumerate(self.item[0]):
            playurl = None
            self.API.setPartNumber(partNumber)

            if self.isDirectPlay():
                self.logMsg("File is direct playing.", 1)
                playurl = self.API.getTranscodeVideoPath('DirectPlay')
                playurl = playurl.encode('utf-8')
                # Set playmethod property
                utils.window('emby_%s.playmethod' % playurl, "DirectPlay")

            elif self.isDirectStream():
                self.logMsg("File is direct streaming.", 1)
                playurl = self.API.getTranscodeVideoPath('DirectStream')
                # Set playmethod property
                utils.window('emby_%s.playmethod' % playurl, "DirectStream")

            elif self.isTranscoding():
                self.logMsg("File is transcoding.", 1)
                quality = {
                    'maxVideoBitrate': self.getBitrate()
                }
                playurl = self.API.getTranscodeVideoPath('Transcode',
                                                         quality=quality)
                # Set playmethod property
                utils.window('emby_%s.playmethod' % playurl, value="Transcode")

            playurls.append(playurl)

        self.logMsg("The playurls are: %s" % playurls, 1)
        return playurls

    def httpPlay(self):
        # Audio, Video, Photo
        item = self.item
        server = self.server

        itemid = item['Id']
        mediatype = item['MediaType']

        if mediatype == "Audio":
            playurl = "%s/emby/Audio/%s/stream" % (server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (server, itemid)

        return playurl

    def isDirectPlay(self):

        # Requirement: Filesystem, Accessible path
        if utils.settings('playFromStream') == "true":
            # User forcing to play via HTTP
            self.logMsg("Can't direct play, user enabled play from HTTP.", 1)
            return False

        if not self.h265enabled():
            return False

        # Found with e.g. trailers
        # if self.API.getDataFromPartOrMedia('optimizedForStreaming') == '1':
        #    return False

        return True

    def directPlay(self):

        item = self.item

        try:
            playurl = item['MediaSources'][0]['Path']
        except (IndexError, KeyError):
            playurl = item['Path']

        if item.get('VideoType'):
            # Specific format modification
            type = item['VideoType']

            if type == "Dvd":
                playurl = "%s/VIDEO_TS/VIDEO_TS.IFO" % playurl
            elif type == "BluRay":
                playurl = "%s/BDMV/index.bdmv" % playurl

        # Assign network protocol
        if playurl.startswith('\\\\'):
            playurl = playurl.replace("\\\\", "smb://")
            playurl = playurl.replace("\\", "/")

        if "apple.com" in playurl:
            USER_AGENT = "QuickTime/7.7.4"
            playurl += "?|User-Agent=%s" % USER_AGENT

        return playurl

    def fileExists(self):

        if 'Path' not in self.item:
            # File has no path defined in server
            return False

        # Convert path to direct play
        path = self.directPlay()
        self.logMsg("Verifying path: %s" % path, 1)

        if xbmcvfs.exists(path):
            self.logMsg("Path exists.", 1)
            return True

        elif ":" not in path:
            self.logMsg("Can't verify path, assumed linux. Still try to direct play.", 1)
            return True

        else:
            self.logMsg("Failed to find file.")
            return False

    def h265enabled(self):
        videoCodec = self.API.getVideoCodec()
        codec = videoCodec['videocodec']
        resolution = videoCodec['resolution']
        # 720p
        if ((utils.settings('transcode720H265') == "true") and
                ("h265" in codec) and
                (resolution in "720 1080")):
            self.logMsg("Option to transcode 720P/h265 enabled.", 0)
            return False
        # 1080p
        if ((utils.settings('transcodeH265') == "true") and
                ("h265" in codec) and
                (resolution == "1080")):
            self.logMsg("Option to transcode 1080P/h265 enabled.", 0)
            return False
        return True

    def isDirectStream(self):
        if not self.h265enabled():
            return False

        # Requirement: BitRate, supported encoding
        # canDirectStream = item['MediaSources'][0]['SupportsDirectStream']
        # Plex: always able?!?
        canDirectStream = True
        # Make sure the server supports it
        if not canDirectStream:
            return False

        # Verify the bitrate
        if not self.isNetworkSufficient():
            self.logMsg("The network speed is insufficient to direct stream file.", 1)
            return False
        return True

    def directStream(self):

        server = self.server

        itemid = self.API.getRatingKey()
        type = self.API.getType()

        # if 'Path' in item and item['Path'].endswith('.strm'):
        #     # Allow strm loading when direct streaming
        #     playurl = self.directPlay()
        if type == "Audio":
            playurl = "%s/emby/Audio/%s/stream.mp3" % (server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (server, itemid)
            playurl = "{server}/player/playback/playMedia?key=%2Flibrary%2Fmetadata%2F%s&offset=0&X-Plex-Client-Identifier={clientId}&machineIdentifier={SERVER ID}&address={SERVER IP}&port={SERVER PORT}&protocol=http&path=http%3A%2F%2F{SERVER IP}%3A{SERVER PORT}%2Flibrary%2Fmetadata%2F{MEDIA ID}" % (itemid)
            playurl = self.API.replaceURLtags()

        return playurl

    def isNetworkSufficient(self):

        settings = self.getBitrate()

        sourceBitrate = int(self.API.getDataFromPartOrMedia('bitrate'))
        self.logMsg("The add-on settings bitrate is: %s, the video bitrate required is: %s" % (settings, sourceBitrate), 1)
        if settings < sourceBitrate:
            return False
        return True

    def isTranscoding(self):
        # I hope Plex transcodes everything
        return True
        item = self.item

        canTranscode = item['MediaSources'][0]['SupportsTranscoding']
        # Make sure the server supports it
        if not canTranscode:
            return False

        return True

    def transcoding(self):

        item = self.item

        if 'Path' in item and item['Path'].endswith('.strm'):
            # Allow strm loading when transcoding
            playurl = self.directPlay()
        else:
            itemid = item['Id']
            deviceId = self.clientInfo.getDeviceId()
            playurl = (
                "%s/emby/Videos/%s/master.m3u8?MediaSourceId=%s"
                % (self.server, itemid, itemid)
            )
            playurl = (
                "%s&VideoCodec=h264&AudioCodec=ac3&MaxAudioChannels=6&deviceId=%s&VideoBitrate=%s"
                % (playurl, deviceId, self.getBitrate()*1000))

        return playurl

    def getBitrate(self):

        # get the addon video quality
        videoQuality = utils.settings('videoBitrate')
        bitrate = {

            '0': 664,
            '1': 996,
            '2': 1320,
            '3': 2000,
            '4': 3200,
            '5': 4700,
            '6': 6200,
            '7': 7700,
            '8': 9200,
            '9': 10700,
            '10': 12200,
            '11': 13700,
            '12': 15200,
            '13': 16700,
            '14': 18200,
            '15': 20000,
            '16': 40000,
            '17': 100000,
            '18': 1000000
        }

        # max bit rate supported by server (max signed 32bit integer)
        return bitrate.get(videoQuality, 2147483)

    def audioSubsPref(self, url, listitem, part=None):
        # For transcoding only
        # Present the list of audio to select from
        audioStreamsList = {}
        audioStreams = []
        audioStreamsChannelsList = {}
        subtitleStreamsList = {}
        subtitleStreams = ['No subtitles']
        downloadableStreams = []
        selectAudioIndex = ""
        selectSubsIndex = ""
        playurlprefs = "%s" % url

        # Set part where we're at
        self.API.setPartNumber(part)
        item = self.item
        try:
            mediasources = item[0]
            mediastreams = mediasources[part]
        except (TypeError, KeyError, IndexError):
            return

        for stream in mediastreams:
            # Since Emby returns all possible tracks together, have to sort them.
            index = stream['index']
            type = stream['streamType']

            # Audio
            if type == "2":
                codec = stream['codec']
                channelLayout = stream.get('audioChannelLayout', "")
               
                try:
                    track = "%s - %s - %s %s" % (index, stream['language'], codec, channelLayout)
                except:
                    track = "%s - %s %s" % (index, codec, channelLayout)
                
                audioStreamsChannelsList[index] = stream['channels']
                audioStreamsList[track] = index
                audioStreams.append(track)

            # Subtitles
            elif type == "3":
                '''if stream['IsExternal']:
                    continue'''
                try:
                    track = "%s - %s" % (index, stream['language'])
                except:
                    track = "%s - %s" % (index, stream['codec'])

                default = stream.get('default', None)
                forced = stream.get('forced', None)
                downloadable = True if stream.get('format', None) else False

                if default:
                    track = "%s - Default" % track
                if forced:
                    track = "%s - Forced" % track
                if downloadable:
                    downloadableStreams.append(index)

                subtitleStreamsList[track] = index
                subtitleStreams.append(track)


        if len(audioStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the audio stream", audioStreams)
            if resp > -1:
                # User selected audio
                selected = audioStreams[resp]
                selectAudioIndex = audioStreamsList[selected]
                playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex
            else: # User backed out of selection
                playurlprefs += "&AudioStreamIndex=%s" % mediasources['DefaultAudioStreamIndex']
        else: # There's only one audiotrack.
            selectAudioIndex = audioStreamsList[audioStreams[0]]
            playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex

        if len(subtitleStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the subtitle stream", subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                pass
            elif resp > -1:
                # User selected subtitles
                selected = subtitleStreams[resp]
                selectSubsIndex = subtitleStreamsList[selected]

                # Load subtitles in the listitem if downloadable
                if selectSubsIndex in downloadableStreams:

                    itemid = item['Id']
                    url = [("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                        % (self.server, itemid, itemid, selectSubsIndex))]
                    self.logMsg("Set up subtitles: %s %s" % (selectSubsIndex, url), 1)
                    listitem.setSubtitles(url)
                else:
                    # Burn subtitles
                    playurlprefs += "&SubtitleStreamIndex=%s" % selectSubsIndex

            else: # User backed out of selection
                playurlprefs += "&SubtitleStreamIndex=%s" % mediasources.get('DefaultSubtitleStreamIndex', "")

        # Get number of channels for selected audio track
        audioChannels = audioStreamsChannelsList.get(selectAudioIndex, 0)
        if audioChannels > 2:
            playurlprefs += "&AudioBitrate=384000"
        else:
            playurlprefs += "&AudioBitrate=192000"

        return playurlprefs
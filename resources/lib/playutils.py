# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import sys
import urllib

import xbmc
import xbmcgui
import xbmcvfs

import clientinfo
import downloadutils
import read_embyserver as embyserver
from utils import window, settings, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlayUtils():
    
    
    def __init__(self, item):

        self.item = item
        self.clientInfo = clientinfo.ClientInfo()
        self.emby = embyserver.Read_EmbyServer()

        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)
        
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
    
    def get_play_url(self):

        ''' New style to retrieve the best playback method based on sending
            the profile to the server. Based on capabilities the correct path is returned,
            including livestreams that need to be opened by the server
        '''
        play_url = None
        info = self.get_playback_info()

        if info:
            log.info("playback info: %s", info)

            play_url = info['Path']

            if info['SupportsDirectPlay']:
                play_method = "DirectPlay"
            elif info['SupportsDirectStream']:
                play_method = "DirectStream"
            elif info.get('LiveStreamId'):
                play_method = "LiveStream"
                if info['RequiresClosing']:
                    window('emby_%s.livestreamid' % play_url, value=info['LiveStreamId'])
            else:
                play_method = "Transcode"

            window('emby_%s.playmethod' % play_url, value=play_method)
            log.info("play method: %s play url: %s", play_method, play_url)

        return play_url

    def getPlayUrl(self):

        # log filename, used by other addons eg subtitles which require the file name
        try:
            window('embyfilename', value=self.directPlay())
        except:
            log.info("Could not get file path for embyfilename window prop")

        playurl = None
        user_token = downloadutils.DownloadUtils().get_token()
        
        if (self.item.get('Type') in ("Recording", "TvChannel") and self.item.get('MediaSources')
                and self.item['MediaSources'][0]['Protocol'] == "Http"):
            # Play LiveTV or recordings
            log.info("File protocol is http (livetv).")
            playurl = "%s/emby/Videos/%s/stream.ts?audioCodec=copy&videoCodec=copy" % (self.server, self.item['Id'])
            playurl += "&api_key=" + str(user_token)
            window('emby_%s.playmethod' % playurl, value="DirectPlay")
            

        elif self.item.get('MediaSources') and self.item['MediaSources'][0]['Protocol'] == "Http":
            # Only play as http, used for channels, or online hosting of content
            log.info("File protocol is http.")
            playurl = self.httpPlay()
            window('emby_%s.playmethod' % playurl, value="DirectStream")

        elif self.isDirectPlay():

            log.info("File is direct playing.")
            playurl = self.directPlay()
            playurl = playurl.encode('utf-8')
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="DirectPlay")

        elif self.isDirectStream():
            
            log.info("File is direct streaming.")
            playurl = self.directStream()
            playurl = playurl.encode('utf-8')
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="DirectStream")

        elif self.isTranscoding():
            
            log.info("File is transcoding.")
            playurl = self.transcoding()
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="Transcode")

        return playurl

    def httpPlay(self):
        # Audio, Video, Photo

        itemid = self.item['Id']
        mediatype = self.item['MediaType']

        if mediatype == "Audio":
            playurl = "%s/emby/Audio/%s/stream?" % (self.server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (self.server, itemid)

        user_token = downloadutils.DownloadUtils().get_token()
        playurl += "&api_key=" + str(user_token)
        return playurl

    def isDirectPlay(self):

        # Requirement: Filesystem, Accessible path
        if settings('playFromStream') == "true":
            # User forcing to play via HTTP
            log.info("Can't direct play, play from HTTP enabled.")
            return False

        videotrack = self.item['MediaSources'][0]['Name']
        transcodeH265 = settings('transcodeH265')
        videoprofiles = [x['Profile'] for x in self.item['MediaSources'][0]['MediaStreams'] if 'Profile' in x]
        transcodeHi10P = settings('transcodeHi10P')        

        if transcodeHi10P == "true" and "H264" in videotrack and "High 10" in videoprofiles:
            return False   

        if transcodeH265 in ("1", "2", "3") and ("HEVC" in videotrack or "H265" in videotrack):
            # Avoid H265/HEVC depending on the resolution
            try:
                resolution = int(videotrack.split("P", 1)[0])
            except ValueError: # 4k resolution
                resolution = 3064
            res = {

                '1': 480,
                '2': 720,
                '3': 1080
            }
            log.info("Resolution is: %sP, transcode for resolution: %sP+"
                % (resolution, res[transcodeH265]))
            if res[transcodeH265] <= resolution:
                return False

        canDirectPlay = self.item['MediaSources'][0]['SupportsDirectPlay']
        # Make sure direct play is supported by the server
        if not canDirectPlay:
            log.info("Can't direct play, server doesn't allow/support it.")
            return False

        # Verify screen resolution
        if self.resolutionConflict():
            log.info("Can't direct play, resolution limit is enabled")
            return False

        location = self.item['LocationType']
        if location == "FileSystem":
            # Verify the path
            if not self.fileExists():
                log.info("Unable to direct play.")
                log.info(self.directPlay())
                xbmcgui.Dialog().ok(
                            heading=lang(29999),
                            line1=lang(33011),
                            line2=(self.directPlay()))                            
                sys.exit()

        return True

    def directPlay(self):

        try:
            playurl = self.item['MediaSources'][0]['Path']
        except (IndexError, KeyError):
            playurl = self.item['Path']

        if self.item.get('VideoType'):
            # Specific format modification
            if self.item['VideoType'] == "Dvd":
                playurl = "%s/VIDEO_TS/VIDEO_TS.IFO" % playurl
            elif self.item['VideoType'] == "BluRay":
                playurl = "%s/BDMV/index.bdmv" % playurl

        # Assign network protocol
        if playurl.startswith('\\\\'):
            playurl = playurl.replace("\\\\", "smb://")
            playurl = playurl.replace("\\", "/")

        if "apple.com" in playurl:
            USER_AGENT = "QuickTime/7.7.4"
            playurl += "?|User-Agent=%s" % USER_AGENT

        # Strm
        if playurl.endswith('.strm'):
            playurl = urllib.urlencode(playurl)

        return playurl

    def fileExists(self):

        if 'Path' not in self.item:
            # File has no path defined in server
            return False

        # Convert path to direct play
        path = self.directPlay()
        log.info("Verifying path: %s" % path)

        if xbmcvfs.exists(path):
            log.info("Path exists.")
            return True

        elif ":" not in path:
            log.info("Can't verify path, assumed linux. Still try to direct play.")
            return True

        else:
            log.info("Failed to find file.")
            return False

    def isDirectStream(self):

        videotrack = self.item['MediaSources'][0]['Name']
        transcodeH265 = settings('transcodeH265')
        videoprofiles = [x['Profile'] for x in self.item['MediaSources'][0]['MediaStreams'] if 'Profile' in x]
        transcodeHi10P = settings('transcodeHi10P')        

        if transcodeHi10P == "true" and "H264" in videotrack and "High 10" in videoprofiles:
            return False   

        if transcodeH265 in ("1", "2", "3") and ("HEVC" in videotrack or "H265" in videotrack):
            # Avoid H265/HEVC depending on the resolution
            try:
                resolution = int(videotrack.split("P", 1)[0])
            except ValueError: # 4k resolution
                resolution = 3064
            res = {

                '1': 480,
                '2': 720,
                '3': 1080
            }
            log.info("Resolution is: %sP, transcode for resolution: %sP+"
                % (resolution, res[transcodeH265]))
            if res[transcodeH265] <= resolution:
                return False

        # Requirement: BitRate, supported encoding
        canDirectStream = self.item['MediaSources'][0]['SupportsDirectStream']
        # Make sure the server supports it
        if not canDirectStream:
            return False

        # Verify the bitrate
        if not self.isNetworkSufficient():
            log.info("The network speed is insufficient to direct stream file.")
            return False

        # Verify screen resolution
        if self.resolutionConflict():
            log.info("Can't direct stream, resolution limit is enabled")
            return False

        return True

    def directStream(self):

        if 'Path' in self.item and self.item['Path'].endswith('.strm'):
            # Allow strm loading when direct streaming
            playurl = self.directPlay()
        elif self.item['Type'] == "Audio":
            playurl = "%s/emby/Audio/%s/stream.mp3?" % (self.server, self.item['Id'])
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (self.server, self.item['Id'])

        user_token = downloadutils.DownloadUtils().get_token()
        playurl += "&api_key=" + str(user_token)
        return playurl

    def isNetworkSufficient(self):

        settings = self.getBitrate()*1000

        try:
            sourceBitrate = int(self.item['MediaSources'][0]['Bitrate'])
        except (KeyError, TypeError):
            log.info("Bitrate value is missing.")
        else:
            log.info("The add-on settings bitrate is: %s, the video bitrate required is: %s"
                % (settings, sourceBitrate))
            if settings < sourceBitrate:
                return False

        return True

    def isTranscoding(self):
        # Make sure the server supports it
        if not self.item['MediaSources'][0]['SupportsTranscoding']:
            return False

        return True

    def transcoding(self):

        if 'Path' in self.item and self.item['Path'].endswith('.strm'):
            # Allow strm loading when transcoding
            playurl = self.directPlay()
        else:
            itemid = self.item['Id']
            deviceId = self.clientInfo.get_device_id()
            playurl = (
                "%s/emby/Videos/%s/master.m3u8?MediaSourceId=%s"
                % (self.server, itemid, itemid)
            )
            playurl = (
                "%s&VideoCodec=h264&AudioCodec=ac3&MaxAudioChannels=6&deviceId=%s&VideoBitrate=%s"
                % (playurl, deviceId, self.getBitrate()*1000))

            # Limit to 8 bit if user selected transcode Hi10P
            transcodeHi10P = settings('transcodeHi10P')
            if transcodeHi10P == "true":
                playurl = "%s&MaxVideoBitDepth=8" % playurl

            # Adjust video resolution
            if self.resolutionConflict():
                screenRes = self.getScreenResolution()
                playurl = "%s&maxWidth=%s&maxHeight=%s" % (playurl, screenRes['width'], screenRes['height'])

            user_token = downloadutils.DownloadUtils().get_token()
            playurl += "&api_key=" + str(user_token)

        return playurl

    def audioSubsPref(self, url, listitem):

        dialog = xbmcgui.Dialog()
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

        try:
            mediasources = self.item['MediaSources'][0]
            mediastreams = mediasources['MediaStreams']
        except (TypeError, KeyError, IndexError):
            return

        for stream in mediastreams:
            # Since Emby returns all possible tracks together, have to sort them.
            index = stream['Index']

            if 'Audio' in stream['Type']:
                codec = stream['Codec']
                channelLayout = stream.get('ChannelLayout', "")
               
                try:
                    track = "%s - %s - %s %s" % (index, stream['Language'], codec, channelLayout)
                except:
                    track = "%s - %s %s" % (index, codec, channelLayout)
                
                audioStreamsChannelsList[index] = stream['Channels']
                audioStreamsList[track] = index
                audioStreams.append(track)

            elif 'Subtitle' in stream['Type']:
                try:
                    track = "%s - %s" % (index, stream['Language'])
                except:
                    track = "%s - %s" % (index, stream['Codec'])

                default = stream['IsDefault']
                forced = stream['IsForced']
                downloadable = stream['SupportsExternalStream']

                if default:
                    track = "%s - Default" % track
                if forced:
                    track = "%s - Forced" % track
                if downloadable:
                    downloadableStreams.append(index)

                subtitleStreamsList[track] = index
                subtitleStreams.append(track)


        if len(audioStreams) > 1:
            resp = dialog.select(lang(33013), audioStreams)
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
            resp = dialog.select(lang(33014), subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                pass
            elif resp > -1:
                # User selected subtitles
                selected = subtitleStreams[resp]
                selectSubsIndex = subtitleStreamsList[selected]
                settings = self.emby.get_server_transcoding_settings()

                # Load subtitles in the listitem if downloadable
                if settings['EnableSubtitleExtraction'] and selectSubsIndex in downloadableStreams:

                    itemid = self.item['Id']
                    url = [("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                        % (self.server, itemid, itemid, selectSubsIndex))]
                    log.info("Set up subtitles: %s %s" % (selectSubsIndex, url))
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
    
    def get_playback_info(self):

        # Get the playback info for the current item

        info = self.emby.get_playback_info(self.item['Id'], self.get_device_profile())       
        return self.get_optimal_source(info['MediaSources'])

    def get_optimal_source(self, media_sources):

        ''' Select the best possible mediasource for playback Because we posted
            our deviceprofile to the server, only streams will be returned that can
            actually be played by this client so no need to check bitrates etc.
        '''
        preferred = ('SupportsDirectPlay', 'SupportsDirectStream', 'SupportsTranscoding')
        optimal_source = {}

        for stream in preferred:
            for source in media_sources:
                if source[stream]:

                    if stream == "lSupportsDirectPlay":
                        if self.is_file_exists(source):
                            optimal_source = source
                    elif optimal_source.get('Bitrate', 0) < source.get('Bitrate', 0):
                        # prefer stream with highest bitrate for http sources
                        optimal_source = source
                    elif source.get('RequiresOpening'):
                        # livestream
                        optimal_source = self.get_live_stream(source['PlaySessionId'], source)

        log.info('get optimal source: %s', optimal_source)
        return optimal_source

    def get_live_stream(self, play_session_id, media_source):

        info = self.emby.get_live_stream(self.item['Id'], self.get_device_profile(), play_session_id, media_source['OpenToken'])
        log.info("get live stream: %s", info)

        return info['MediaSource']

    def is_file_exists(self, source):

        path = source['Path']

        if 'VideoType' in source:
            if source['VideoType'] == "Dvd":
                path = "%s/VIDEO_TS/VIDEO_TS.IFO" % path
            elif source['VideoType'] == "BluRay":
                path = "%s/BDMV/index.bdmv" % path

        # Assign network protocol
        if path.startswith('\\\\'):
            path = path.replace('\\\\', "smb://")
            path = path.replace('\\', "/")

        if xbmcvfs.exists(path) or ":" not in path:
            log.info("Path exists or assumed linux.")
            source['Path'] = path
            return False
        else:
            log.info("Failed to find file.")
            return False

    def get_bitrate(self):

        # get the addon video quality

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
            '16': 25000,
            '17': 30000,
            '18': 35000,
            '16': 40000,
            '17': 100000,
            '18': 1000000
        }
        # max bit rate supported by server (max signed 32bit integer)
        return bitrate.get(settings('videoBitrate'), 2147483)
    
    def get_device_profile(self):
        return {

            "Name": "Kodi",
            "MaxStreamingBitrate": self.get_bitrate() * 1000,
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,

            "Identification": {
                "ModelName": "Kodi",
                "Headers": [
                    {
                        "Name": "User-Agent",
                        "Value": "Kodi",
                        "Match": 2
                    }
                ]
            },

            "TranscodingProfiles": [
                {
                    "Container": "mp3",
                    "AudioCodec": "mp3",
                    "Type": 0
                },
                {
                    "Container": "ts",
                    "AudioCodec": "aac",
                    "VideoCodec": "h264",
                    "Type": 1
                },
                {
                    "Container": "jpeg",
                    "Type": 2
                }
            ],

            "DirectPlayProfiles": [
                {
                    "Container": "",
                    "Type": 0
                },
                {
                    "Container": "",
                    "Type": 1
                },
                {
                    "Container": "",
                    "Type": 2
                }
            ],

            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],

            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": 2
                },
                {
                    "Format": "sub",
                    "Method": 2
                },
                {
                    "Format": "srt",
                    "Method": 1
                },
                {
                    "Format": "ass",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "ssa",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "smi",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "dvdsub",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "pgs",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "pgssub",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "sub",
                    "Method": 1,
                    "DidlMode": ""
                }
            ]
        }





    def resolutionConflict(self):
        if settings('limitResolution') == "true":
            screenRes = self.getScreenResolution()
            videoRes = self.getVideoResolution()
            
            if not videoRes:
                return False

            return videoRes['width'] > screenRes['width'] or videoRes['height'] > screenRes['height']
        else:
            return False

    def getScreenResolution(self):
        wind = xbmcgui.Window()
        return {'width' : wind.getWidth(),
                'height' : wind.getHeight()}

    def getVideoResolution(self):
        try:
            return {'width' : self.item['MediaStreams'][0]['Width'],
                    'height' : self.item['MediaStreams'][0]['Height']}
        except (KeyError, IndexError) as error:
            log.debug(error)
            log.debug(self.item)
            return False


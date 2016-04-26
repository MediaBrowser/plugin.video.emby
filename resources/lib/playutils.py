# -*- coding: utf-8 -*-

###############################################################################

from urllib import urlencode

import xbmcgui
import xbmcvfs

import clientinfo
import utils

import PlexAPI


###############################################################################


@utils.logging
class PlayUtils():

    def __init__(self, item):

        self.item = item
        self.API = PlexAPI.API(item)

        self.clientInfo = clientinfo.ClientInfo()

        self.userid = utils.window('currUserId')
        self.server = utils.window('pms_server')
        self.machineIdentifier = utils.window('plex_machineIdentifier')

    def getPlayUrl(self, partNumber=None):
        """
        Returns the playurl for the part with number partNumber
        (movie might consist of several files)

        playurl is utf-8 encoded!
        """
        log = self.logMsg
        window = utils.window

        self.API.setPartNumber(partNumber)
        playurl = self.isDirectPlay()

        if playurl:
            log("File is direct playing.", 1)
            playurl = playurl.encode('utf-8')
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, "DirectPlay")

        elif self.isDirectStream():
            self.logMsg("File is direct streaming.", 1)
            playurl = self.API.getTranscodeVideoPath('DirectStream').encode('utf-8')
            # Set playmethod property
            utils.window('emby_%s.playmethod' % playurl, "DirectStream")

        elif self.isTranscoding():
            self.logMsg("File is transcoding.", 1)
            quality = {
                'maxVideoBitrate': self.getBitrate(),
                'videoResolution': self.getResolution(),
                'videoQuality': '100'
            }
            playurl = self.API.getTranscodeVideoPath(
                'Transcode',
                quality=quality).encode('utf-8')
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="Transcode")

        log("The playurl is: %s" % playurl, 1)
        return playurl

    def httpPlay(self):
        # Audio, Video, Photo

        itemid = self.item['Id']
        mediatype = self.item['MediaType']

        if mediatype == "Audio":
            playurl = "%s/emby/Audio/%s/stream" % (self.server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (self.server, itemid)

        return playurl

    def isDirectPlay(self):
        """
        Returns the path/playurl if successful, False otherwise
        """
        # True for e.g. plex.tv watch later
        if self.API.shouldStream() is True:
            self.logMsg("Plex item optimized for direct streaming", 1)
            return False

        # set to either 'Direct Stream=1' or 'Transcode=2'
        if utils.settings('playType') != "0":
            # User forcing to play via HTTP
            self.logMsg("User chose to not direct play", 1)
            return False

        if self.h265enabled():
            return False

        path = self.API.validatePlayurl(self.API.getFilePath(),
                                        self.API.getType(),
                                        forceCheck=True)
        if path is None:
            self.logMsg('Kodi cannot access file %s - no direct play'
                        % path, 1)
            return False
        else:
            self.logMsg('Kodi can access file %s - direct playing' % path, 1)
            return path

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
            self.logMsg("Failed to find file.", 1)
            return False

    def h265enabled(self):
        """
        Returns True if we need to transcode
        """
        videoCodec = self.API.getVideoCodec()
        self.logMsg("videoCodec: %s" % videoCodec, 2)
        codec = videoCodec['videocodec']
        resolution = videoCodec['resolution']
        h265 = self.getH265()
        try:
            if not ('h265' in codec or 'hevc' in codec) or (h265 is None):
                return False
        # E.g. trailers without a codec of None
        except TypeError:
            return False

        if resolution >= h265:
            self.logMsg("Option to transcode h265 enabled. Resolution media: "
                        "%s, transcoding limit resolution: %s"
                        % (resolution, h265), 1)
            return True

        return False

    def isDirectStream(self):
        # set to 'Transcode=2'
        if utils.settings('playType') == "2":
            # User forcing to play via HTTP
            self.logMsg("User chose to transcode", 1)
            self.logMsg("Resolution is: %sP, transcode for resolution: %sP+"
        canDirectStream = self.item['MediaSources'][0]['SupportsDirectStream']
            return False
        if self.h265enabled():
            return False
        # Verify the bitrate
        if not self.isNetworkSufficient():
            self.logMsg("The network speed is insufficient to direct stream "
                        "file. Transcoding", 1)
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
        """
        Returns True if the network is sufficient (set in file settings)
        """
        try:
            sourceBitrate = int(self.API.getDataFromPartOrMedia('bitrate'))
        except:
            self.logMsg('Could not detect source bitrate. It is assumed to be'
                        'sufficient', 1)
            return True
        settings = self.getBitrate()
        self.logMsg("The add-on settings bitrate is: %s, the video bitrate"
                    "required is: %s" % (settings, sourceBitrate), 1)
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
        videoQuality = utils.settings('transcoderVideoQualities')
        bitrate = {
            '0': 320,
            '1': 720,
            '2': 1500,
            '3': 2000,
            '4': 3000,
            '5': 4000,
            '6': 8000,
            '7': 10000,
            '8': 12000,
            '9': 20000,
            '10': 40000,
        }
        # max bit rate supported by server (max signed 32bit integer)
        return bitrate.get(videoQuality, 2147483)

    def getH265(self):
        chosen = utils.settings('transcodeH265')
        H265 = {
            '0': None,
            '1': 480,
            '2': 720,
            '3': 1080
        }
        return H265.get(chosen, None)

    def getResolution(self):
        chosen = utils.settings('transcoderVideoQualities')
        res = {
            '0': '420x420',
            '1': '576x320',
            '2': '720x480',
            '3': '1024x768',
            '4': '1280x720',
            '5': '1280x720',
            '6': '1920x1080',
            '7': '1920x1080',
            '8': '1920x1080',
            '9': '1920x1080',
            '10': '1920x1080',
        }
        return res[chosen]

    def audioSubsPref(self, listitem, url, part=None):
        lang = utils.language
        dialog = xbmcgui.Dialog()
        # For transcoding only
        # Present the list of audio to select from
        audioStreamsList = []
        audioStreams = []
        # audioStreamsChannelsList = []
        subtitleStreamsList = []
        subtitleStreams = ['1 No subtitles']
        downloadableStreams = []
        # selectAudioIndex = ""
        selectSubsIndex = ""
        playurlprefs = {}

        # Set part where we're at
        self.API.setPartNumber(part)
        if part is None:
            part = 0
        try:
            mediastreams = self.item[0][part]
        except (TypeError, KeyError, IndexError):
            return url

        audioNum = 0
        # Remember 'no subtitles'
        subNum = 1
        for stream in mediastreams:
            # Since Emby returns all possible tracks together, have to sort them.
            index = stream.attrib.get('id')
            type = stream.attrib.get('streamType')

            # Audio
            if type == "2":
                codec = stream.attrib.get('codec')
                channelLayout = stream.attrib.get('audioChannelLayout', "")
               
                try:
                    track = "%s %s - %s %s" % (audioNum+1, stream.attrib['language'], codec, channelLayout)
                except:
                    track = "%s 'unknown' - %s %s" % (audioNum+1, codec, channelLayout)
                
                #audioStreamsChannelsList[audioNum] = stream.attrib['channels']
                audioStreamsList.append(index)
                audioStreams.append(track.encode('utf-8'))
                audioNum += 1

            # Subtitles
            elif type == "3":
                '''if stream['IsExternal']:
                    continue'''
                try:
                    track = "%s %s" % (subNum+1, stream.attrib['language'])
                except:
                    track = "%s 'unknown' (%s)" % (subNum+1, stream.attrib.get('codec'))

                default = stream.attrib.get('default')
                forced = stream.attrib.get('forced')
                downloadable = stream.attrib.get('key')

                if default:
                    track = "%s - Default" % track
                if forced:
                    track = "%s - Forced" % track
                if downloadable:
                    downloadableStreams.append(index)

                subtitleStreamsList.append(index)
                subtitleStreams.append(track.encode('utf-8'))
                subNum += 1

        if audioNum > 1:
            resp = dialog.select(lang(33013), audioStreams)
            if resp > -1:
                # User selected audio
                playurlprefs['audioStreamID'] = audioStreamsList[resp]
            else: # User backed out of selection - let PMS decide
                pass
        else: # There's only one audiotrack.
            playurlprefs['audioStreamID'] = audioStreamsList[0]

        # Add audio boost
        playurlprefs['audioBoost'] = utils.settings('audioBoost')

        if subNum > 1:
            resp = dialog.select(lang(33014), subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                playurlprefs["skipSubtitles"] = 1
            elif resp > -1:
                # User selected subtitles
                selectSubsIndex = subtitleStreamsList[resp-1]

                # Load subtitles in the listitem if downloadable
                if selectSubsIndex in downloadableStreams:

                    url = "%s/library/streams/%s" \
                          % (self.server, selectSubsIndex)
                    url = self.API.addPlexHeadersToUrl(url)
                    self.logMsg("Downloadable sub: %s: %s" % (selectSubsIndex, url), 1)
                    listitem.setSubtitles([url.encode('utf-8')])
                else:
                    self.logMsg('Need to burn in subtitle %s' % selectSubsIndex, 1)
                    playurlprefs["subtitleStreamID"] = selectSubsIndex
                    playurlprefs["subtitleSize"] = utils.settings('subtitleSize')

            else: # User backed out of selection
                pass

        # Tell the PMS what we want with a PUT request
        # url = self.server + '/library/parts/' + self.item[0][part].attrib['id']
        # PlexFunctions.SelectStreams(url, playurlprefs)
        url += '&' + urlencode(playurlprefs)

        # Get number of channels for selected audio track
        # audioChannels = audioStreamsChannelsList.get(selectAudioIndex, 0)
        # if audioChannels > 2:
        #     playurlprefs += "&AudioBitrate=384000"
        # else:
        #     playurlprefs += "&AudioBitrate=192000"

        return url

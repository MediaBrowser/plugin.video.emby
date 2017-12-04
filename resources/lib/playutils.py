# -*- coding: utf-8 -*-

###############################################################################
import logging
from downloadutils import DownloadUtils

from utils import window, settings, tryEncode, language as lang, dialog
import variables as v
import PlexAPI

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class PlayUtils():

    def __init__(self, item):
        self.item = item
        self.API = PlexAPI.API(item)
        self.doUtils = DownloadUtils().downloadUrl
        self.machineIdentifier = window('plex_machineIdentifier')

    def getPlayUrl(self, partNumber=None):
        """
        Returns the playurl for the part with number partNumber
        (movie might consist of several files)

        playurl is utf-8 encoded!
        """
        self.API.setPartNumber(partNumber)
        self.API.getMediastreamNumber()
        playurl = self.isDirectPlay()

        if playurl is not None:
            log.info("File is direct playing.")
            playurl = tryEncode(playurl)
            # Set playmethod property
            window('plex_%s.playmethod' % playurl, "DirectPlay")

        elif self.isDirectStream():
            log.info("File is direct streaming.")
            playurl = tryEncode(
                self.API.getTranscodeVideoPath('DirectStream'))
            # Set playmethod property
            window('plex_%s.playmethod' % playurl, "DirectStream")

        else:
            log.info("File is transcoding.")
            playurl = tryEncode(self.API.getTranscodeVideoPath(
                'Transcode',
                quality={
                    'maxVideoBitrate': self.get_bitrate(),
                    'videoResolution': self.get_resolution(),
                    'videoQuality': '100',
                    'mediaBufferSize': int(settings('kodi_video_cache'))/1024,
                }))
            # Set playmethod property
            window('plex_%s.playmethod' % playurl, value="Transcode")

        log.info("The playurl is: %s" % playurl)
        return playurl

    def isDirectPlay(self):
        """
        Returns the path/playurl if we can direct play, None otherwise
        """
        # True for e.g. plex.tv watch later
        if self.API.shouldStream() is True:
            log.info("Plex item optimized for direct streaming")
            return
        # Check whether we have a strm file that we need to throw at Kodi 1:1
        path = self.API.getFilePath()
        if path is not None and path.endswith('.strm'):
            log.info('.strm file detected')
            playurl = self.API.validatePlayurl(path,
                                               self.API.getType(),
                                               forceCheck=True)
            if playurl is None:
                return
            else:
                return tryEncode(playurl)
        # set to either 'Direct Stream=1' or 'Transcode=2'
        # and NOT to 'Direct Play=0'
        if settings('playType') != "0":
            # User forcing to play via HTTP
            log.info("User chose to not direct play")
            return
        if self.mustTranscode():
            return
        return self.API.validatePlayurl(path,
                                        self.API.getType(),
                                        forceCheck=True)

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

    def mustTranscode(self):
        """
        Returns True if we need to transcode because
            - codec is in h265
            - 10bit video codec
            - HEVC codec
            - window variable 'plex_forcetranscode' set to 'true'
                (excepting trailers etc.)
            - video bitrate above specified settings bitrate
        if the corresponding file settings are set to 'true'
        """
        if self.API.getType() in (v.PLEX_TYPE_CLIP, v.PLEX_TYPE_SONG):
            log.info('Plex clip or music track, not transcoding')
            return False
        videoCodec = self.API.getVideoCodec()
        log.info("videoCodec: %s" % videoCodec)
        if window('plex_forcetranscode') == 'true':
            log.info('User chose to force-transcode')
            return True
        codec = videoCodec['videocodec']
        if codec is None:
            # e.g. trailers. Avoids TypeError with "'h265' in codec"
            log.info('No codec from PMS, not transcoding.')
            return False
        if ((settings('transcodeHi10P') == 'true' and
                videoCodec['bitDepth'] == '10') and 
                ('h265' in codec or 'hevc' in codec)):
            log.info('Option to transcode 10bit h265 video content enabled.')
            return True
        try:
            bitrate = int(videoCodec['bitrate'])
        except (TypeError, ValueError):
            log.info('No video bitrate from PMS, not transcoding.')
            return False
        if bitrate > self.get_max_bitrate():
            log.info('Video bitrate of %s is higher than the maximal video'
                     'bitrate of %s that the user chose. Transcoding'
                     % (bitrate, self.get_max_bitrate()))
            return True
        try:
            resolution = int(videoCodec['resolution'])
        except (TypeError, ValueError):
            log.info('No video resolution from PMS, not transcoding.')
            return False
        if 'h265' in codec or 'hevc' in codec:
            if resolution >= self.getH265():
                log.info("Option to transcode h265/HEVC enabled. Resolution "
                         "of the media: %s, transcoding limit resolution: %s"
                         % (str(resolution), str(self.getH265())))
                return True
        return False

    def isDirectStream(self):
        # Never transcode Music
        if self.API.getType() == 'track':
            return True
        # set to 'Transcode=2'
        if settings('playType') == "2":
            # User forcing to play via HTTP
            log.info("User chose to transcode")
            return False
        if self.mustTranscode():
            return False
        return True

    def get_max_bitrate(self):
        # get the addon video quality
        videoQuality = settings('maxVideoQualities')
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
            '11': 99999999  # deactivated
        }
        # max bit rate supported by server (max signed 32bit integer)
        return bitrate.get(videoQuality, 2147483)

    def getH265(self):
        """
        Returns the user settings for transcoding h265: boundary resolutions
        of 480, 720 or 1080 as an int

        OR 9999999 (int) if user chose not to transcode
        """
        H265 = {
            '0': 99999999,
            '1': 480,
            '2': 720,
            '3': 1080
        }
        return H265[settings('transcodeH265')]

    def get_bitrate(self):
        """
        Get the desired transcoding bitrate from the settings
        """
        videoQuality = settings('transcoderVideoQualities')
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

    def get_resolution(self):
        """
        Get the desired transcoding resolutions from the settings
        """
        chosen = settings('transcoderVideoQualities')
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
        """
        For transcoding only

        Called at the very beginning of play; used to change audio and subtitle
        stream by a PUT request to the PMS
        """
        # Set media and part where we're at
        if self.API.mediastream is None:
            self.API.getMediastreamNumber()
        if part is None:
            part = 0
        try:
            mediastreams = self.item[self.API.mediastream][part]
        except (TypeError, IndexError):
            log.error('Could not get media %s, part %s'
                      % (self.API.mediastream, part))
            return
        part_id = mediastreams.attrib['id']
        audio_streams_list = []
        audio_streams = []
        subtitle_streams_list = []
        # No subtitles as an option
        subtitle_streams = [lang(39706)]
        downloadable_streams = []
        download_subs = []
        # selectAudioIndex = ""
        select_subs_index = ""
        audio_numb = 0
        # Remember 'no subtitles'
        sub_num = 1
        default_sub = None

        for stream in mediastreams:
            # Since Plex returns all possible tracks together, have to sort
            # them.
            index = stream.attrib.get('id')
            typus = stream.attrib.get('streamType')
            # Audio
            if typus == "2":
                codec = stream.attrib.get('codec')
                channelLayout = stream.attrib.get('audioChannelLayout', "")
                try:
                    track = "%s %s - %s %s" % (audio_numb+1,
                                               stream.attrib['language'],
                                               codec,
                                               channelLayout)
                except:
                    track = "%s %s - %s %s" % (audio_numb+1,
                                               lang(39707),  # unknown
                                               codec,
                                               channelLayout)
                audio_streams_list.append(index)
                audio_streams.append(tryEncode(track))
                audio_numb += 1

            # Subtitles
            elif typus == "3":
                try:
                    track = "%s %s" % (sub_num+1, stream.attrib['language'])
                except KeyError:
                    track = "%s %s (%s)" % (sub_num+1,
                                            lang(39707),  # unknown
                                            stream.attrib.get('codec'))
                default = stream.attrib.get('default')
                forced = stream.attrib.get('forced')
                downloadable = stream.attrib.get('key')

                if default:
                    track = "%s - %s" % (track, lang(39708))  # Default
                if forced:
                    track = "%s - %s" % (track, lang(39709))  # Forced
                if downloadable:
                    # We do know the language - temporarily download
                    if 'language' in stream.attrib:
                        path = self.API.download_external_subtitles(
                            '{server}%s' % stream.attrib['key'],
                            "subtitle.%s.%s" % (stream.attrib['language'],
                                                stream.attrib['codec']))
                    # We don't know the language - no need to download
                    else:
                        path = self.API.addPlexCredentialsToUrl(
                            "%s%s" % (window('pms_server'),
                                      stream.attrib['key']))
                    downloadable_streams.append(index)
                    download_subs.append(tryEncode(path))
                else:
                    track = "%s (%s)" % (track, lang(39710))  # burn-in
                if stream.attrib.get('selected') == '1' and downloadable:
                    # Only show subs without asking user if they can be
                    # turned off
                    default_sub = index

                subtitle_streams_list.append(index)
                subtitle_streams.append(tryEncode(track))
                sub_num += 1

        if audio_numb > 1:
            resp = dialog('select', lang(33013), audio_streams)
            if resp > -1:
                # User selected some audio track
                args = {
                    'audioStreamID': audio_streams_list[resp],
                    'allParts': 1
                }
                self.doUtils('{server}/library/parts/%s' % part_id,
                             action_type='PUT',
                             parameters=args)

        if sub_num == 1:
            # No subtitles
            return

        select_subs_index = None
        if (settings('pickPlexSubtitles') == 'true' and
                default_sub is not None):
            log.info('Using default Plex subtitle: %s' % default_sub)
            select_subs_index = default_sub
        else:
            resp = dialog('select', lang(33014), subtitle_streams)
            if resp > 0:
                select_subs_index = subtitle_streams_list[resp-1]
            else:
                # User selected no subtitles or backed out of dialog
                select_subs_index = ''

        log.debug('Adding external subtitles: %s' % download_subs)
        # Enable Kodi to switch autonomously to downloadable subtitles
        if download_subs:
            listitem.setSubtitles(download_subs)

        if select_subs_index in downloadable_streams:
            for i, stream in enumerate(downloadable_streams):
                if stream == select_subs_index:
                    # Set the correct subtitle
                    window('plex_%s.subtitle' % tryEncode(url), value=str(i))
                    break
            # Don't additionally burn in subtitles
            select_subs_index = ''
        else:
            window('plex_%s.subtitle' % tryEncode(url), value='None')

        args = {
            'subtitleStreamID': select_subs_index,
            'allParts': 1
        }
        self.doUtils('{server}/library/parts/%s' % part_id,
                     action_type='PUT',
                     parameters=args)

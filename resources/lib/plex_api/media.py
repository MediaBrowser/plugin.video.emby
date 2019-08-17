#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from ..utils import cast
from ..downloadutils import DownloadUtils as DU
from .. import utils, variables as v, app, path_ops, clientinfo

LOG = getLogger('PLEX.api')


class Media(object):
    def should_stream(self):
        """
        Returns True if the item's 'optimizedForStreaming' is set, False other-
        wise
        """
        return cast(bool, self.xml[0].get('optimizedForStreaming')) or False

    def _from_part_or_media(self, key):
        """
        Retrieves XML data 'key' first from the active part. If unsuccessful,
        tries to retrieve the data from the Media response part.

        If all fails, None is returned.
        """
        return self.xml[0][self.part].get(key, self.xml[0].get(key))

    def video_codec(self):
        """
        Returns the video codec and resolution for the child and part selected.
        If any data is not found on a part-level, the Media-level data is
        returned.
        If that also fails (e.g. for old trailers, None is returned)

        Output:
            {
                'videocodec': xxx,       e.g. 'h264'
                'resolution': xxx,       e.g. '720' or '1080'
                'height': xxx,           e.g. '816'
                'width': xxx,            e.g. '1920'
                'aspectratio': xxx,      e.g. '1.78'
                'bitrate': xxx,          e.g. '10642'
                'container': xxx         e.g. 'mkv',
                'bitDepth': xxx          e.g. '8', '10'
            }
        """
        answ = {
            'videocodec': self._from_part_or_media('videoCodec'),
            'resolution': self._from_part_or_media('videoResolution'),
            'height': self._from_part_or_media('height'),
            'width': self._from_part_or_media('width'),
            'aspectratio': self._from_part_or_media('aspectratio'),
            'bitrate': self._from_part_or_media('bitrate'),
            'container': self._from_part_or_media('container'),
        }
        try:
            answ['bitDepth'] = self.xml[0][self.part][self.mediastream].get('bitDepth')
        except (TypeError, AttributeError, KeyError, IndexError):
            answ['bitDepth'] = None
        return answ

    def mediastreams(self):
        """
        Returns the media streams for metadata purposes

        Output: each track contains a dictionaries
        {
            'video': videotrack-list,       'codec', 'height', 'width',
                                            'aspect', 'video3DFormat'
            'audio': audiotrack-list,       'codec', 'channels',
                                            'language'
            'subtitle': list of subtitle languages (or "Unknown")
        }
        """
        videotracks = []
        audiotracks = []
        subtitlelanguages = []
        try:
            # Sometimes, aspectratio is on the "toplevel"
            aspect = cast(float, self.xml[0].get('aspectRatio'))
        except IndexError:
            # There is no stream info at all, returning empty
            return {
                'video': videotracks,
                'audio': audiotracks,
                'subtitle': subtitlelanguages
            }
        # Loop over parts
        for child in self.xml[0]:
            container = child.get('container')
            # Loop over Streams
            for stream in child:
                media_type = int(stream.get('streamType', 999))
                track = {}
                if media_type == 1:  # Video streams
                    if 'codec' in stream.attrib:
                        track['codec'] = stream.get('codec').lower()
                        if "msmpeg4" in track['codec']:
                            track['codec'] = "divx"
                        elif "mpeg4" in track['codec']:
                            pass
                        elif "h264" in track['codec']:
                            if container in ("mp4", "mov", "m4v"):
                                track['codec'] = "avc1"
                    track['height'] = cast(int, stream.get('height'))
                    track['width'] = cast(int, stream.get('width'))
                    # track['Video3DFormat'] = item.get('Video3DFormat')
                    track['aspect'] = cast(float,
                                           stream.get('aspectRatio') or aspect)
                    track['duration'] = self.runtime()
                    track['video3DFormat'] = None
                    videotracks.append(track)
                elif media_type == 2:  # Audio streams
                    if 'codec' in stream.attrib:
                        track['codec'] = stream.get('codec').lower()
                        if ("dca" in track['codec'] and
                                "ma" in stream.get('profile', '').lower()):
                            track['codec'] = "dtshd_ma"
                    track['channels'] = cast(int, stream.get('channels'))
                    # 'unknown' if we cannot get language
                    track['language'] = stream.get('languageCode',
                                                   utils.lang(39310).lower())
                    audiotracks.append(track)
                elif media_type == 3:  # Subtitle streams
                    # 'unknown' if we cannot get language
                    subtitlelanguages.append(
                        stream.get('languageCode', utils.lang(39310)).lower())
        return {
            'video': videotracks,
            'audio': audiotracks,
            'subtitle': subtitlelanguages
        }

    def mediastream_number(self):
        """
        Returns the Media stream as an int (mostly 0). Will let the user choose
        if several media streams are present for a PMS item (if settings are
        set accordingly)

        Returns None if the user aborted selection (leaving self.mediastream at
        its default of None)
        """
        # How many streams do we have?
        count = 0
        for entry in self.xml.iterfind('./Media'):
            count += 1
        if (count > 1 and (
                (self.plex_type != v.PLEX_TYPE_CLIP and
                 utils.settings('bestQuality') == 'false')
            or
                (self.plex_type == v.PLEX_TYPE_CLIP and
                 utils.settings('bestTrailer') == 'false'))):
            # Several streams/files available.
            dialoglist = []
            for entry in self.xml.iterfind('./Media'):
                # Get additional info (filename / languages)
                if 'file' in entry[0].attrib:
                    option = entry[0].get('file')
                    option = path_ops.basename(option)
                else:
                    option = self.title() or ''
                # Languages of audio streams
                languages = []
                for stream in entry[0]:
                    if (cast(int, stream.get('streamType')) == 1 and
                            'language' in stream.attrib):
                        language = stream.get('language')
                        languages.append(language)
                languages = ', '.join(languages)
                if languages:
                    if option:
                        option = '%s (%s): ' % (option, languages)
                    else:
                        option = '%s: ' % languages
                else:
                    option = '%s ' % option
                if 'videoResolution' in entry.attrib:
                    res = entry.get('videoResolution')
                    option = '%s%sp ' % (option, res)
                if 'videoCodec' in entry.attrib:
                    codec = entry.get('videoCodec')
                    option = '%s%s' % (option, codec)
                option = option.strip() + ' - '
                if 'audioProfile' in entry.attrib:
                    profile = entry.get('audioProfile')
                    option = '%s%s ' % (option, profile)
                if 'audioCodec' in entry.attrib:
                    codec = entry.get('audioCodec')
                    option = '%s%s ' % (option, codec)
                option = cast(str, option.strip())
                dialoglist.append(option)
            media = utils.dialog('select', 'Select stream', dialoglist)
            LOG.info('User chose media stream number: %s', media)
            if media == -1:
                LOG.info('User cancelled media stream selection')
                return
        else:
            media = 0
        self.mediastream = media
        return media

    def transcode_video_path(self, action, quality=None):
        """

        To be called on a VIDEO level of PMS xml response!

        Transcode Video support; returns the URL to get a media started

        Input:
            action      'DirectStream' or 'Transcode'

            quality:    {
                            'videoResolution': e.g. '1024x768',
                            'videoQuality': e.g. '60',
                            'maxVideoBitrate': e.g. '2000' (in kbits)
                        }
                        (one or several of these options)
        Output:
            final URL to pull in PMS transcoder

        TODO: mediaIndex
        """
        if self.mediastream is None and self.mediastream_number() is None:
            return
        quality = {} if quality is None else quality
        xargs = clientinfo.getXArgsDeviceInfo()
        # For DirectPath, path/key of PART is needed
        # trailers are 'clip' with PMS xmls
        if action == "DirectStream":
            path = self.xml[self.mediastream][self.part].get('key')
            url = app.CONN.server + path
            # e.g. Trailers already feature an '?'!
            return utils.extend_url(url, xargs)

        # For Transcoding
        headers = {
            'X-Plex-Platform': 'Android',
            'X-Plex-Platform-Version': '7.0',
            'X-Plex-Product': 'Plex for Android',
            'X-Plex-Version': '5.8.0.475'
        }
        # Path/key to VIDEO item of xml PMS response is needed, not part
        path = self.xml.get('key')
        transcode_path = app.CONN.server + \
            '/video/:/transcode/universal/start.m3u8'
        args = {
            'audioBoost': utils.settings('audioBoost'),
            'autoAdjustQuality': 0,
            'directPlay': 0,
            'directStream': 1,
            'protocol': 'hls',   # seen in the wild: 'dash', 'http', 'hls'
            'session': v.PKC_MACHINE_IDENTIFIER,  # TODO: create new unique id
            'fastSeek': 1,
            'path': path,
            'mediaIndex': self.mediastream,
            'partIndex': self.part,
            'hasMDE': 1,
            'location': 'lan',
            'subtitleSize': utils.settings('subtitleSize')
        }
        LOG.debug("Setting transcode quality to: %s", quality)
        xargs.update(headers)
        xargs.update(args)
        xargs.update(quality)
        return utils.extend_url(transcode_path, xargs)

    def cache_external_subs(self):
        """
        Downloads external subtitles temporarily to Kodi and returns a list
        of their paths
        """
        externalsubs = []
        try:
            mediastreams = self.xml[0][self.part]
        except (TypeError, KeyError, IndexError):
            return
        kodiindex = 0
        fileindex = 0
        for stream in mediastreams:
            # Since plex returns all possible tracks together, have to pull
            # only external subtitles - only for these a 'key' exists
            if cast(int, stream.get('streamType')) != 3:
                # Not a subtitle
                continue
            # Only set for additional external subtitles NOT lying beside video
            key = stream.get('key')
            # Only set for dedicated subtitle files lying beside video
            # ext = stream.attrib.get('format')
            if key:
                # We do know the language - temporarily download
                if stream.get('languageCode') is not None:
                    language = stream.get('languageCode')
                    codec = stream.get('codec')
                    path = self.download_external_subtitles(
                        "{server}%s" % key,
                        "subtitle%02d.%s.%s" % (fileindex, language, codec))
                    fileindex += 1
                # We don't know the language - no need to download
                else:
                    path = self.attach_plex_token_to_url(
                        "%s%s" % (app.CONN.server, key))
                externalsubs.append(path)
                kodiindex += 1
        LOG.info('Found external subs: %s', externalsubs)
        return externalsubs

    @staticmethod
    def download_external_subtitles(url, filename):
        """
        One cannot pass the subtitle language for ListItems. Workaround; will
        download the subtitle at url to the Kodi PKC directory in a temp dir

        Returns the path to the downloaded subtitle or None
        """
        path = path_ops.path.join(v.EXTERNAL_SUBTITLE_TEMP_PATH, filename)
        response = DU().downloadUrl(url, return_response=True)
        try:
            response.status_code
        except AttributeError:
            LOG.error('Could not temporarily download subtitle %s', url)
            return
        else:
            LOG.debug('Writing temp subtitle to %s', path)
            with open(path_ops.encode_path(path), 'wb') as filer:
                filer.write(response.content)
            return path

    def validate_playurl(self, path, typus, force_check=False, folder=False,
                         omit_check=False):
        """
        Returns a valid path for Kodi, e.g. with '\' substituted to '\\' in
        Unicode. Returns None if this is not possible

            path       : Unicode
            typus      : Plex type from PMS xml
            force_check : Will always try to check validity of path
                         Will also skip confirmation dialog if path not found
            folder     : Set to True if path is a folder
            omit_check  : Will entirely omit validity check if True
        """
        if path is None:
            return
        typus = v.REMAP_TYPE_FROM_PLEXTYPE[typus]
        if app.SYNC.remap_path:
            path = path.replace(getattr(app.SYNC, 'remapSMB%sOrg' % typus),
                                getattr(app.SYNC, 'remapSMB%sNew' % typus),
                                1)
            # There might be backslashes left over:
            path = path.replace('\\', '/')
        elif app.SYNC.replace_smb_path:
            if path.startswith('\\\\'):
                path = 'smb:' + path.replace('\\', '/')
        if app.SYNC.escape_path:
            try:
                protocol, hostname, args = path.split(':', 2)
            except ValueError:
                pass
            else:
                args = utils.quote(args)
                path = '%s:%s:%s' % (protocol, hostname, args)
        if (app.SYNC.path_verified and not force_check) or omit_check:
            return path

        # exist() needs a / or \ at the end to work for directories
        if not folder:
            # files
            check = path_ops.exists(path)
        else:
            # directories
            if "\\" in path:
                if not path.endswith('\\'):
                    # Add the missing backslash
                    check = path_ops.exists(path + "\\")
                else:
                    check = path_ops.exists(path)
            else:
                if not path.endswith('/'):
                    check = path_ops.exists(path + "/")
                else:
                    check = path_ops.exists(path)
        if not check:
            if force_check is False:
                # Validate the path is correct with user intervention
                if self.ask_to_validate(path):
                    app.APP.stop_threads(block=False)
                    path = None
                app.SYNC.path_verified = True
            else:
                path = None
        elif not force_check:
            # Only set the flag if we were not force-checking the path
            app.SYNC.path_verified = True
        return path

    @staticmethod
    def ask_to_validate(url):
        """
        Displays a YESNO dialog box:
            Kodi can't locate file: <url>. Please verify the path.
            You may need to verify your network credentials in the
            add-on settings or use different Plex paths. Stop syncing?

        Returns True if sync should stop, else False
        """
        LOG.warn('Cannot access file: %s', url)
        # Kodi cannot locate the file #s. Please verify your PKC settings. Stop
        # syncing?
        return utils.yesno_dialog(utils.lang(29999), utils.lang(39031) % url)

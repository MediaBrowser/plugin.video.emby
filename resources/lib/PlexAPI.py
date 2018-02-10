# -*- coding: utf-8 -*-
"""
Taken from iBaa, https://github.com/iBaa/PlexConnect
Point of time: December 22, 2015


Collection of "connector functions" to Plex Media Server/MyPlex


PlexGDM:
loosely based on hippojay's plexGDM:
https://github.com/hippojay/script.plexbmc.helper... /resources/lib/plexgdm.py


Plex Media Server communication:
source (somewhat): https://github.com/hippojay/plugin.video.plexbmc
later converted from httplib to urllib2


Transcoder support:
PlexAPI_getTranscodePath() based on getTranscodeURL from pyplex/plexAPI
https://github.com/megawubs/pyplex/blob/master/plexAPI/info.py


MyPlex - Basic Authentication:
http://www.voidspace.org.uk/python/articles/urllib2.shtml
http://www.voidspace.org.uk/python/articles/authentication.shtml
http://stackoverflow.com/questions/2407126/python-urllib2-basic-auth-problem
http://stackoverflow.com/questions/111945/is-there-any-way-to-do-http-put-in-python
(and others...)
"""
from logging import getLogger
from re import compile as re_compile, sub
from urllib import urlencode, unquote
from os.path import basename, join
from os import makedirs

from xbmcgui import ListItem
from xbmcvfs import exists

import clientinfo as client
from downloadutils import DownloadUtils as DU
from utils import window, settings, language as lang, tryDecode, tryEncode, \
    DateToKodi, exists_dir, slugify, dialog
import PlexFunctions as PF
import plexdb_functions as plexdb
import variables as v
import state

###############################################################################
LOG = getLogger("PLEX." + __name__)

REGEX_IMDB = re_compile(r'''/(tt\d+)''')
REGEX_TVDB = re_compile(r'''thetvdb:\/\/(.+?)\?''')
###############################################################################


class API():
    """
    API(item)

    Processes a Plex media server's XML response

    item: xml.etree.ElementTree element
    """
    def __init__(self, item):
        self.item = item
        # which media part in the XML response shall we look at?
        self.part = 0
        self.mediastream = None
        self.server = window('pms_server')

    def setPartNumber(self, number=None):
        """
        Sets the part number to work with (used to deal with Movie with several
        parts).
        """
        self.part = number or 0

    def getPartNumber(self):
        """
        Returns the current media part number we're dealing with.
        """
        return self.part

    def getType(self):
        """
        Returns the type of media, e.g. 'movie' or 'clip' for trailers
        """
        return self.item.attrib.get('type')

    def getChecksum(self):
        """
        Returns a string, not int. 

        WATCH OUT - time in Plex, not Kodi ;-)
        """
        # Include a letter to prohibit saving as an int!
        checksum = "K%s%s" % (self.getRatingKey(),
                              self.item.attrib.get('updatedAt', ''))
        return checksum

    def getRatingKey(self):
        """
        Returns the Plex key such as '246922' as a string
        """
        return self.item.attrib.get('ratingKey')

    def getKey(self):
        """
        Returns the Plex key such as '/library/metadata/246922' or empty string
        """
        return self.item.attrib.get('key', '')

    def plex_media_streams(self):
        """
        Returns the media streams directly from the PMS xml.
        Mind self.mediastream to be set before and self.part!
        """
        return self.item[self.mediastream][self.part]

    def getFilePath(self, forceFirstMediaStream=False):
        """
        Returns the direct path to this item, e.g. '\\NAS\movies\movie.mkv'
        or None

        forceFirstMediaStream=True:
            will always use 1st media stream, e.g. when several different
            files are present for the same PMS item
        """
        if self.mediastream is None and forceFirstMediaStream is False:
            self.getMediastreamNumber()
        try:
            if forceFirstMediaStream is False:
                ans = self.item[self.mediastream][self.part].attrib['file']
            else:
                ans = self.item[0][self.part].attrib['file']
        except:
            ans = None
        if ans is not None:
            try:
                ans = tryDecode(unquote(ans))
            except UnicodeDecodeError:
                # Sometimes, Plex seems to have encoded in latin1
                ans = unquote(ans).decode('latin1')
        return ans

    def get_picture_path(self):
        """
        Returns the item's picture path (transcode, if necessary) as string.
        Will always use addon paths, never direct paths
        """
        extension = self.item[0][0].attrib['key'][self.item[0][0].attrib['key'].rfind('.'):].lower()
        if (window('plex_force_transcode_pix') == 'true' or
                extension not in v.KODI_SUPPORTED_IMAGES):
            # Let Plex transcode
            # max width/height supported by plex image transcoder is 1920x1080
            path = self.server + PF.transcode_image_path(
                self.item[0][0].attrib.get('key'),
                window('pms_token'),
                "%s%s" % (self.server, self.item[0][0].attrib.get('key')),
                1920,
                1080)
        else:
            path = self.addPlexCredentialsToUrl(
                '%s%s' % (window('pms_server'),
                          self.item[0][0].attrib['key']))
        # Attach Plex id to url to let it be picked up by our playqueue agent
        # later
        return tryEncode('%s&plex_id=%s' % (path, self.getRatingKey()))

    def getTVShowPath(self):
        """
        Returns the direct path to the TV show, e.g. '\\NAS\tv\series'
        or None
        """
        res = None
        for child in self.item:
            if child.tag == 'Location':
                res = child.attrib.get('path')
        return res

    def getIndex(self):
        """
        Returns the 'index' of an PMS XML reply. Depicts e.g. season number.
        """
        return self.item.attrib.get('index')

    def getDateCreated(self):
        """
        Returns the date when this library item was created.

        If not found, returns 2000-01-01 10:00:00
        """
        res = self.item.attrib.get('addedAt')
        if res is not None:
            res = DateToKodi(res)
        else:
            res = '2000-01-01 10:00:00'
        return res

    def getViewCount(self):
        """
        Returns the play count for the item as an int or the int 0 if not found
        """
        try:
            return int(self.item.attrib['viewCount'])
        except (KeyError, ValueError):
            return 0

    def getUserData(self):
        """
        Returns a dict with None if a value is missing
        {
            'Favorite': favorite,                  # False, because n/a in Plex
            'PlayCount': playcount,
            'Played': played,                      # True/False
            'LastPlayedDate': lastPlayedDate,
            'Resume': resume,                      # Resume time in seconds
            'Runtime': runtime,
            'Rating': rating
        }
        """
        item = self.item.attrib
        # Default - attributes not found with Plex
        favorite = False
        try:
            playcount = int(item['viewCount'])
        except (KeyError, ValueError):
            playcount = None
        played = True if playcount else False

        try:
            lastPlayedDate = DateToKodi(int(item['lastViewedAt']))
        except (KeyError, ValueError):
            lastPlayedDate = None

        if state.INDICATE_MEDIA_VERSIONS is True:
            userrating = 0
            for entry in self.item.findall('./Media'):
                userrating += 1
            # Don't show a value of '1'
            userrating = 0 if userrating == 1 else userrating
        else:
            try:
                userrating = int(float(item['userRating']))
            except (KeyError, ValueError):
                userrating = 0

        try:
            rating = float(item['audienceRating'])
        except (KeyError, ValueError):
            try:
                rating = float(item['rating'])
            except (KeyError, ValueError):
                rating = 0.0

        resume, runtime = self.getRuntime()
        return {
            'Favorite': favorite,
            'PlayCount': playcount,
            'Played': played,
            'LastPlayedDate': lastPlayedDate,
            'Resume': resume,
            'Runtime': runtime,
            'Rating': rating,
            'UserRating': userrating
        }

    def getCollections(self):
        """
        Returns a list of PMS collection tags or an empty list
        """
        collections = []
        for child in self.item:
            if child.tag == 'Collection':
                if child.attrib['tag']:
                    collections.append(child.attrib['tag'])
        return collections

    def getPeople(self):
        """
        Returns a dict of lists of people found.
        {
            'Director': list,
            'Writer': list,
            'Cast': list,
            'Producer': list
        }
        """
        director = []
        writer = []
        cast = []
        producer = []
        for child in self.item:
            try:
                if child.tag == 'Director':
                    director.append(child.attrib['tag'])
                elif child.tag == 'Writer':
                    writer.append(child.attrib['tag'])
                elif child.tag == 'Role':
                    cast.append(child.attrib['tag'])
                elif child.tag == 'Producer':
                    producer.append(child.attrib['tag'])
            except KeyError:
                LOG.warn('Malformed PMS answer for getPeople: %s: %s',
                         child.tag, child.attrib)
        return {
            'Director': director,
            'Writer': writer,
            'Cast': cast,
            'Producer': producer
        }

    def getPeopleList(self):
        """
        Returns a list of people from item, with a list item of the form
        {
            'Name': xxx,
            'Type': xxx,
            'Id': xxx
            'imageurl': url to picture, None otherwise
            ('Role': xxx for cast/actors only, None if not found)
        }
        """
        people = []
        # Key of library: Plex-identifier. Value represents the Kodi/emby side
        people_of_interest = {
            'Director': 'Director',
            'Writer': 'Writer',
            'Role': 'Actor',
            'Producer': 'Producer'
        }
        for child in self.item:
            if child.tag in people_of_interest.keys():
                name = child.attrib['tag']
                name_id = child.attrib['id']
                Type = child.tag
                Type = people_of_interest[Type]

                url = child.attrib.get('thumb')
                Role = child.attrib.get('role')

                people.append({
                    'Name': name,
                    'Type': Type,
                    'Id': name_id,
                    'imageurl': url
                })
                if url:
                    people[-1].update({'imageurl': url})
                if Role:
                    people[-1].update({'Role': Role})
        return people

    def getGenres(self):
        """
        Returns a list of genres found. (Not a string)
        """
        genre = []
        for child in self.item:
            if child.tag == 'Genre':
                genre.append(child.attrib['tag'])
        return genre

    def getGuid(self):
        return self.item.attrib.get('guid')

    def getProvider(self, providername=None):
        """
        providername:  e.g. 'imdb', 'tvdb'

        Return IMDB, e.g. "tt0903624". Returns None if not found
        """
        item = self.item.attrib
        try:
            item = item['guid']
        except KeyError:
            return None

        if providername == 'imdb':
            regex = REGEX_IMDB
        elif providername == 'tvdb':
            # originally e.g. com.plexapp.agents.thetvdb://276564?lang=en
            regex = REGEX_TVDB
        else:
            return None

        provider = regex.findall(item)
        try:
            provider = provider[0]
        except IndexError:
            provider = None
        return provider

    def getTitle(self):
        """
        Returns an item's name/title or "Missing Title Name".
        Output:
            title, sorttitle

        sorttitle = title, if no sorttitle is found
        """
        title = self.item.attrib.get('title', 'Missing Title Name')
        sorttitle = self.item.attrib.get('titleSort', title)
        return title, sorttitle

    def getPlot(self):
        """
        Returns the plot or None.
        """
        return self.item.attrib.get('summary', None)

    def getTagline(self):
        """
        Returns a shorter tagline or None
        """
        return self.item.attrib.get('tagline', None)

    def getAudienceRating(self):
        """
        Returns the audience rating, 'rating' itself or 0.0
        """
        res = self.item.attrib.get('audienceRating')
        if res is None:
            res = self.item.attrib.get('rating')
        try:
            res = float(res)
        except (ValueError, TypeError):
            res = 0.0
        return res

    def getYear(self):
        """
        Returns the production(?) year ("year") or None
        """
        return self.item.attrib.get('year', None)

    def getResume(self):
        """
        Returns the resume point of time in seconds as int. 0 if not found
        """
        try:
            resume = float(self.item.attrib['viewOffset'])
        except (KeyError, ValueError):
            resume = 0.0
        return int(resume * v.PLEX_TO_KODI_TIMEFACTOR)

    def getRuntime(self):
        """
        Resume point of time and runtime/totaltime in rounded to seconds.
        Time from Plex server is measured in milliseconds.
        Kodi: seconds

        Output:
            resume, runtime         as ints. 0 if not found
        """
        item = self.item.attrib

        try:
            runtime = float(item['duration'])
        except (KeyError, ValueError):
            runtime = 0.0
        try:
            resume = float(item['viewOffset'])
        except (KeyError, ValueError):
            resume = 0.0

        runtime = int(runtime * v.PLEX_TO_KODI_TIMEFACTOR)
        resume = int(resume * v.PLEX_TO_KODI_TIMEFACTOR)
        return resume, runtime

    def getMpaa(self):
        """
        Get the content rating or None
        """
        mpaa = self.item.attrib.get('contentRating', None)
        # Convert more complex cases
        if mpaa in ("NR", "UR"):
            # Kodi seems to not like NR, but will accept Rated Not Rated
            mpaa = "Rated Not Rated"
        return mpaa

    def getCountry(self):
        """
        Returns a list of all countries found in item.
        """
        country = []
        for child in self.item:
            if child.tag == 'Country':
                country.append(child.attrib['tag'])
        return country

    def getPremiereDate(self):
        """
        Returns the "originallyAvailableAt" or None
        """
        return self.item.attrib.get('originallyAvailableAt')

    def getMusicStudio(self):
        return self.item.attrib.get('studio', '')

    def getStudios(self):
        """
        Returns a list with a single entry for the studio, or an empty list
        """
        studio = []
        try:
            studio.append(self.getStudio(self.item.attrib['studio']))
        except KeyError:
            pass
        return studio

    def getStudio(self, studioName):
        """
        Convert studio for Kodi to properly detect them
        """
        studios = {
            'abc (us)': "ABC",
            'fox (us)': "FOX",
            'mtv (us)': "MTV",
            'showcase (ca)': "Showcase",
            'wgn america': "WGN"
        }
        return studios.get(studioName.lower(), studioName)

    def joinList(self, listobject):
        """
        Smart-joins the listobject into a single string using a " / "
        separator.
        If the list is empty, smart_join returns an empty string.
        """
        string = " / ".join(listobject)
        return string

    def getParentRatingKey(self):
        return self.item.attrib.get('parentRatingKey', '')

    def getEpisodeDetails(self):
        """
        Call on a single episode.

        Output: for the corresponding the TV show and season:
            [
                TV show key,        Plex: 'grandparentRatingKey'
                TV show title,      Plex: 'grandparentTitle'
                TV show season,     Plex: 'parentIndex'
                Episode number,     Plex: 'index'
            ]
        """
        item = self.item.attrib
        key = item.get('grandparentRatingKey')
        title = item.get('grandparentTitle')
        season = item.get('parentIndex')
        episode = item.get('index')
        return key, title, season, episode

    def addPlexHeadersToUrl(self, url, arguments={}):
        """
        Takes an URL and optional arguments (also to be URL-encoded); returns
        an extended URL with e.g. the Plex token included.

        arguments overrule everything
        """
        xargs = client.getXArgsDeviceInfo()
        xargs.update(arguments)
        if '?' not in url:
            url = "%s?%s" % (url, urlencode(xargs))
        else:
            url = "%s&%s" % (url, urlencode(xargs))
        return url

    def addPlexCredentialsToUrl(self, url):
        """
        Returns an extended URL with the Plex token included as 'X-Plex-Token='

        url may or may not already contain a '?'
        """
        if window('pms_token') == '':
            return url
        if '?' not in url:
            url = "%s?X-Plex-Token=%s" % (url, window('pms_token'))
        else:
            url = "%s&X-Plex-Token=%s" % (url, window('pms_token'))
        return url

    def getItemId(self):
        """
        Returns current playQueueItemID or if unsuccessful the playListItemID
        If not found, None is returned
        """
        try:
            answ = self.item.attrib['playQueueItemID']
        except KeyError:
            try:
                answ = self.item.attrib['playListItemID']
            except KeyError:
                answ = None
        return answ

    def getDataFromPartOrMedia(self, key):
        """
        Retrieves XML data 'key' first from the active part. If unsuccessful,
        tries to retrieve the data from the Media response part.

        If all fails, None is returned.
        """
        media = self.item[0].attrib
        part = self.item[0][self.part].attrib

        try:
            try:
                value = part[key]
            except KeyError:
                value = media[key]
        except KeyError:
            value = None
        return value

    def getVideoCodec(self):
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
            'videocodec': self.getDataFromPartOrMedia('videoCodec'),
            'resolution': self.getDataFromPartOrMedia('videoResolution'),
            'height': self.getDataFromPartOrMedia('height'),
            'width': self.getDataFromPartOrMedia('width'),
            'aspectratio': self.getDataFromPartOrMedia('aspectratio'),
            'bitrate': self.getDataFromPartOrMedia('bitrate'),
            'container': self.getDataFromPartOrMedia('container'),
        }
        try:
            answ['bitDepth'] = self.item[0][self.part][self.mediastream].attrib.get('bitDepth')
        except:
            answ['bitDepth'] = None
        return answ

    def getExtras(self):
        """
        Currently ONLY returns the very first trailer found!

        Returns a list of trailer and extras from PMS XML. Returns [] if
        no extras are found.
        Extratypes:
            1:    Trailer
            5:    Behind the scenes

        Output: list of dicts with one entry of the form:
            'ratingKey':                e.g. '12345'
            'title':
            'thumb':                    artwork
            'duration':
            'extraType':
            'originallyAvailableAt':
            'year':
        """
        elements = []
        extras = self.item.find('Extras')
        if extras is None:
            return elements
        for extra in extras:
            try:
                extraType = int(extra.attrib['extraType'])
            except (KeyError, TypeError):
                extraType = None
            if extraType != 1:
                continue
            duration = float(extra.attrib.get('duration', 0.0))
            elements.append({
                'ratingKey': extra.attrib.get('ratingKey'),
                'title': extra.attrib.get('title'),
                'thumb': extra.attrib.get('thumb'),
                'duration': int(duration * v.PLEX_TO_KODI_TIMEFACTOR),
                'extraType': extraType,
                'originallyAvailableAt': extra.attrib.get('originallyAvailableAt'),
                'year': extra.attrib.get('year')
            })
            break
        return elements

    def getMediaStreams(self):
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
            aspect = self.item[0].attrib.get('aspectRatio')
        except IndexError:
            # There is no stream info at all, returning empty
            return {
                'video': videotracks,
                'audio': audiotracks,
                'subtitle': subtitlelanguages
            }
        # Loop over parts
        for child in self.item[0]:
            container = child.attrib.get('container')
            # Loop over Streams
            for grandchild in child:
                stream = grandchild.attrib
                media_type = int(stream.get('streamType', 999))
                track = {}
                if media_type == 1:  # Video streams
                    if 'codec' in stream:
                        track['codec'] = stream['codec'].lower()
                        if "msmpeg4" in track['codec']:
                            track['codec'] = "divx"
                        elif "mpeg4" in track['codec']:
                            # if "simple profile" in profile or profile == "":
                            #    track['codec'] = "xvid"
                            pass
                        elif "h264" in track['codec']:
                            if container in ("mp4", "mov", "m4v"):
                                track['codec'] = "avc1"
                    track['height'] = stream.get('height')
                    track['width'] = stream.get('width')
                    # track['Video3DFormat'] = item.get('Video3DFormat')
                    track['aspect'] = stream.get('aspectRatio', aspect)
                    track['duration'] = self.getRuntime()[1]
                    track['video3DFormat'] = None
                    videotracks.append(track)
                elif media_type == 2:  # Audio streams
                    if 'codec' in stream:
                        track['codec'] = stream['codec'].lower()
                        if ("dca" in track['codec'] and
                                "ma" in stream.get('profile', '').lower()):
                            track['codec'] = "dtshd_ma"
                    track['channels'] = stream.get('channels')
                    # 'unknown' if we cannot get language
                    track['language'] = stream.get(
                        'languageCode', lang(39310)).lower()
                    audiotracks.append(track)
                elif media_type == 3:  # Subtitle streams
                    # 'unknown' if we cannot get language
                    subtitlelanguages.append(
                        stream.get('languageCode', lang(39310)).lower())
        return {
            'video': videotracks,
            'audio': audiotracks,
            'subtitle': subtitlelanguages
        }

    def __getOneArtwork(self, entry):
        if entry not in self.item.attrib:
            return ''
        artwork = self.item.attrib[entry]
        if artwork.startswith('http'):
            pass
        else:
            artwork = self.addPlexCredentialsToUrl(
                "%s/photo/:/transcode?width=4000&height=4000&minSize=1&upscale=0&url=%s" % (self.server, artwork))
        return artwork

    def getAllArtwork(self, parentInfo=False):
        """
        Gets the URLs to the Plex artwork, or empty string if not found.
        parentInfo=True will check for parent's artwork if None is found

        Output:
        {
            'Primary'
            'Art'
            'Banner'
            'Logo'
            'Thumb'
            'Disc'
            'Backdrop' : LIST with the first entry xml key "art"
        }
        """
        allartworks = {
            'Primary': "",  # corresponds to Plex poster ('thumb')
            'Art': "",
            'Banner': "",   # corresponds to Plex banner ('banner') for series
            'Logo': "",
            'Thumb': "",    # corresponds to Plex (grand)parent posters (thumb)
            'Disc': "",
            'Backdrop': []  # Corresponds to Plex fanart ('art')
        }
        # Process backdrops
        # Get background artwork URL
        allartworks['Backdrop'].append(self.__getOneArtwork('art'))
        # Get primary "thumb" pictures:
        allartworks['Primary'] = self.__getOneArtwork('thumb')
        # Banner (usually only on tv series level)
        allartworks['Banner'] = self.__getOneArtwork('banner')
        # For e.g. TV shows, get series thumb
        allartworks['Thumb'] = self.__getOneArtwork('grandparentThumb')

        # Process parent items if the main item is missing artwork
        if parentInfo:
            # Process parent backdrops
            if not allartworks['Backdrop']:
                allartworks['Backdrop'].append(
                    self.__getOneArtwork('parentArt'))
            if not allartworks['Primary']:
                allartworks['Primary'] = self.__getOneArtwork('parentThumb')
        return allartworks

    def getFanartArtwork(self, allartworks, parentInfo=False):
        """
        Downloads additional fanart from third party sources (well, link to
        fanart only).

        allartworks = {
            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }
        """
        externalId = self.getExternalItemId()
        if externalId is not None:
            allartworks = self.getFanartTVArt(externalId, allartworks)
        return allartworks

    def getExternalItemId(self, collection=False):
        """
        Returns the item's IMDB id for movies or tvdb id for TV shows

        If not found in item's Plex metadata, check themovidedb.org

        collection=True will try to return the three-tuple:
            collection ID, poster-path, background-path

        None is returned if unsuccessful
        """
        item = self.item.attrib
        media_type = item.get('type')
        mediaId = None
        # Return the saved Plex id's, if applicable
        # Always seek collection's ids since not provided by PMS
        if collection is False:
            if media_type == v.PLEX_TYPE_MOVIE:
                mediaId = self.getProvider('imdb')
            elif media_type == v.PLEX_TYPE_SHOW:
                mediaId = self.getProvider('tvdb')
            if mediaId is not None:
                return mediaId
            LOG.info('Plex did not provide ID for IMDB or TVDB. Start '
                     'lookup process')
        else:
            LOG.info('Start movie set/collection lookup on themoviedb using %s',
                     item.get('title', ''))

        apiKey = settings('themoviedbAPIKey')
        if media_type == v.PLEX_TYPE_SHOW:
            media_type = 'tv'
        title = item.get('title', '')
        # if the title has the year in remove it as tmdb cannot deal with it...
        # replace e.g. 'The Americans (2015)' with 'The Americans'
        title = sub(r'\s*\(\d{4}\)$', '', title, count=1)
        url = 'https://api.themoviedb.org/3/search/%s' % media_type
        parameters = {
            'api_key': apiKey,
            'language': v.KODILANGUAGE,
            'query': tryEncode(title)
        }
        data = DU().downloadUrl(url,
                                authenticate=False,
                                parameters=parameters,
                                timeout=7)
        try:
            data.get('test')
        except:
            LOG.error('Could not download data from FanartTV')
            return
        if data.get('results') is None:
            LOG.info('No match found on themoviedb for type: %s, title: %s',
                     media_type, title)
            return

        year = item.get('year')
        matchFound = None
        # find year match
        if year is not None:
            for entry in data["results"]:
                if year in entry.get("first_air_date", ""):
                    matchFound = entry
                    break
                elif year in entry.get("release_date", ""):
                    matchFound = entry
                    break
        # find exact match based on title, if we haven't found a year match
        if matchFound is None:
            LOG.info('No themoviedb match found using year %s', year)
            replacements = (
                ' ',
                '-',
                '&',
                ',',
                ':',
                ';'
            )
            for entry in data["results"]:
                name = entry.get("name", entry.get("title", ""))
                original_name = entry.get("original_name", "")
                title_alt = title.lower()
                name_alt = name.lower()
                org_name_alt = original_name.lower()
                for replaceString in replacements:
                    title_alt = title_alt.replace(replaceString, '')
                    name_alt = name_alt.replace(replaceString, '')
                    org_name_alt = org_name_alt.replace(replaceString, '')
                if name == title or original_name == title:
                    # match found for exact title name
                    matchFound = entry
                    break
                elif (name.split(" (")[0] == title or title_alt == name_alt
                        or title_alt == org_name_alt):
                    # match found with substituting some stuff
                    matchFound = entry
                    break

        # if a match was not found, we accept the closest match from TMDB
        if matchFound is None and len(data.get("results")) > 0:
            LOG.info('Using very first match from themoviedb')
            matchFound = entry = data.get("results")[0]

        if matchFound is None:
            LOG.info('Still no themoviedb match for type: %s, title: %s, '
                     'year: %s', media_type, title, year)
            LOG.debug('themoviedb answer was %s', data['results'])
            return

        LOG.info('Found themoviedb match for %s: %s',
                 item.get('title'), matchFound)

        tmdbId = str(entry.get("id", ""))
        if tmdbId == '':
            LOG.error('No themoviedb ID found, aborting')
            return

        if media_type == "multi" and entry.get("media_type"):
            media_type = entry.get("media_type")
        name = entry.get("name", entry.get("title"))
        # lookup external tmdbId and perform artwork lookup on fanart.tv
        parameters = {
            'api_key': apiKey
        }
        for language in [v.KODILANGUAGE, "en"]:
            parameters['language'] = language
            if media_type == "movie":
                url = 'https://api.themoviedb.org/3/movie/%s' % tmdbId
                parameters['append_to_response'] = 'videos'
            elif media_type == "tv":
                url = 'https://api.themoviedb.org/3/tv/%s' % tmdbId
                parameters['append_to_response'] = 'external_ids,videos'
            data = DU().downloadUrl(url,
                                    authenticate=False,
                                    parameters=parameters,
                                    timeout=7)
            try:
                data.get('test')
            except:
                LOG.error('Could not download %s with parameters %s',
                          url, parameters)
                continue
            if collection is False:
                if data.get("imdb_id") is not None:
                    mediaId = str(data.get("imdb_id"))
                    break
                if data.get("external_ids") is not None:
                    mediaId = str(data["external_ids"].get("tvdb_id"))
                    break
            else:
                if data.get("belongs_to_collection") is None:
                    continue
                mediaId = str(data.get("belongs_to_collection").get("id"))
                LOG.debug('Retrieved collections tmdb id %s for %s',
                          mediaId, title)
                url = 'https://api.themoviedb.org/3/collection/%s' % mediaId
                data = DU().downloadUrl(url,
                                        authenticate=False,
                                        parameters=parameters,
                                        timeout=7)
                try:
                    data.get('poster_path')
                except AttributeError:
                    LOG.info('Could not find TheMovieDB poster paths for %s in'
                             'the language %s', title, language)
                    continue
                else:
                    poster = 'https://image.tmdb.org/t/p/original%s' % data.get('poster_path')
                    background = 'https://image.tmdb.org/t/p/original%s' % data.get('backdrop_path')
                    mediaId = mediaId, poster, background
                    break
        return mediaId

    def getFanartTVArt(self, mediaId, allartworks, setInfo=False):
        """
        perform artwork lookup on fanart.tv

        mediaId: IMDB id for movies, tvdb id for TV shows
        """
        item = self.item.attrib
        api_key = settings('FanArtTVAPIKey')
        typus = item.get('type')
        if typus == 'show':
            typus = 'tv'

        if typus == "movie":
            url = 'http://webservice.fanart.tv/v3/movies/%s?api_key=%s' \
                % (mediaId, api_key)
        elif typus == 'tv':
            url = 'http://webservice.fanart.tv/v3/tv/%s?api_key=%s' \
                % (mediaId, api_key)
        else:
            # Not supported artwork
            return allartworks
        data = DU().downloadUrl(url,
                                authenticate=False,
                                timeout=15)
        try:
            data.get('test')
        except:
            LOG.error('Could not download data from FanartTV')
            return allartworks

        # we need to use a little mapping between fanart.tv arttypes and kodi
        # artttypes
        fanartTVTypes = [
            ("logo", "Logo"),
            ("musiclogo", "clearlogo"),
            ("disc", "Disc"),
            ("clearart", "Art"),
            ("banner", "Banner"),
            ("clearlogo", "Logo"),
            ("background", "fanart"),
            ("showbackground", "fanart"),
            ("characterart", "characterart")
        ]
        if typus == "artist":
            fanartTVTypes.append(("thumb", "folder"))
        else:
            fanartTVTypes.append(("thumb", "Thumb"))

        if setInfo:
            fanartTVTypes.append(("poster", "Primary"))

        prefixes = (
            "hd" + typus,
            "hd",
            typus,
            "",
        )
        for fanarttype in fanartTVTypes:
            # Skip the ones we already have
            if allartworks.get(fanarttype[1]):
                continue
            for prefix in prefixes:
                fanarttvimage = prefix + fanarttype[0]
                if fanarttvimage not in data:
                    continue
                # select image in preferred language
                for entry in data[fanarttvimage]:
                    if entry.get("lang") == v.KODILANGUAGE:
                        allartworks[fanarttype[1]] = entry.get("url", "").replace(' ', '%20')
                        break
                # just grab the first english OR undefinded one as fallback
                # (so we're actually grabbing the more popular one)
                if not allartworks.get(fanarttype[1]):
                    for entry in data[fanarttvimage]:
                        if entry.get("lang") in ("en", "00"):
                            allartworks[fanarttype[1]] = entry.get("url", "").replace(' ', '%20')
                            break

        # grab extrafanarts in list
        maxfanarts = 10
        fanartcount = 0
        for prefix in prefixes:
            fanarttvimage = prefix + 'background'
            if fanarttvimage not in data:
                continue
            for entry in data[fanarttvimage]:
                if entry.get("url") is None:
                    continue
                if fanartcount > maxfanarts:
                    break
                allartworks['Backdrop'].append(
                    entry['url'].replace(' ', '%20'))
                fanartcount += 1
        return allartworks

    def getSetArtwork(self, parentInfo=False):
        """
        Gets the URLs to the Plex artwork, or empty string if not found.
        parentInfo=True will check for parent's artwork if None is found

        Only call on movies

        Output:
        {
            'Primary'
            'Art'
            'Banner'
            'Logo'
            'Thumb'
            'Disc'
            'Backdrop' : LIST with the first entry xml key "art"
        }
        """
        allartworks = {
            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }

        # Plex does not get much artwork - go ahead and get the rest from
        # fanart tv only for movie or tv show
        externalId = self.getExternalItemId(collection=True)
        if externalId is not None:
            try:
                externalId, poster, background = externalId
            except TypeError:
                poster, background = None, None
            if poster is not None:
                allartworks['Primary'] = poster
            if background is not None:
                allartworks['Backdrop'].append(background)
            allartworks = self.getFanartTVArt(externalId, allartworks, True)
        else:
            LOG.info('Did not find a set/collection ID on TheMovieDB using %s.'
                     ' Artwork will be missing.', self.getTitle()[0])
        return allartworks

    def shouldStream(self):
        """
        Returns True if the item's 'optimizedForStreaming' is set, False other-
        wise
        """
        return self.item[0].attrib.get('optimizedForStreaming') == '1'

    def getMediastreamNumber(self):
        """
        Returns the Media stream as an int (mostly 0). Will let the user choose
        if several media streams are present for a PMS item (if settings are
        set accordingly)
        """
        # How many streams do we have?
        count = 0
        for entry in self.item.findall('./Media'):
            count += 1
        if (count > 1 and (
                (self.getType() != 'clip' and
                 settings('bestQuality') == 'false')
                or
                (self.getType() == 'clip' and
                 settings('bestTrailer') == 'false'))):
            # Several streams/files available.
            dialoglist = []
            for entry in self.item.findall('./Media'):
                # Get additional info (filename / languages)
                filename = None
                if 'file' in entry[0].attrib:
                    filename = basename(entry[0].attrib['file'])
                # Languages of audio streams
                languages = []
                for stream in entry[0]:
                    if (stream.attrib['streamType'] == '1' and
                            'language' in stream.attrib):
                        languages.append(stream.attrib['language'])
                languages = ', '.join(languages)
                if filename:
                    option = tryEncode(filename)
                if languages:
                    if option:
                        option = '%s (%s): ' % (option, tryEncode(languages))
                    else:
                        option = '%s: ' % tryEncode(languages)
                if 'videoResolution' in entry.attrib:
                    option = '%s%sp ' % (option,
                                         entry.attrib.get('videoResolution'))
                if 'videoCodec' in entry.attrib:
                    option = '%s%s' % (option,
                                       entry.attrib.get('videoCodec'))
                option = option.strip() + ' - '
                if 'audioProfile' in entry.attrib:
                    option = '%s%s ' % (option,
                                        entry.attrib.get('audioProfile'))
                if 'audioCodec' in entry.attrib:
                    option = '%s%s ' % (option,
                                        entry.attrib.get('audioCodec'))
                dialoglist.append(option)
            media = dialog('select', 'Select stream', dialoglist)
        else:
            media = 0
        self.mediastream = media
        return media

    def getTranscodeVideoPath(self, action, quality=None):
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
        if self.mediastream is None:
            self.getMediastreamNumber()
        if quality is None:
            quality = {}
        xargs = client.getXArgsDeviceInfo()
        # For DirectPlay, path/key of PART is needed
        # trailers are 'clip' with PMS xmls
        if action == "DirectStream":
            path = self.item[self.mediastream][self.part].attrib['key']
            url = self.server + path
            # e.g. Trailers already feature an '?'!
            if '?' in url:
                url += '&' + urlencode(xargs)
            else:
                url += '?' + urlencode(xargs)
            return url

        # For Transcoding
        headers = {
            'X-Plex-Platform': 'Android',
            'X-Plex-Platform-Version': '7.0',
            'X-Plex-Product': 'Plex for Android',
            'X-Plex-Version': '5.8.0.475'
        }
        # Path/key to VIDEO item of xml PMS response is needed, not part
        path = self.item.attrib['key']
        transcodePath = self.server + \
            '/video/:/transcode/universal/start.m3u8?'
        args = {
            'audioBoost': settings('audioBoost'),
            'autoAdjustQuality': 0,
            'directPlay': 0,
            'directStream': 1,
            'protocol': 'hls',   # seen in the wild: 'dash', 'http', 'hls'
            'session':  window('plex_client_Id'),
            'fastSeek': 1,
            'path': path,
            'mediaIndex': self.mediastream,
            'partIndex': self.part,
            'hasMDE': 1,
            'location': 'lan',
            'subtitleSize': settings('subtitleSize')
            # 'copyts': 1,
            # 'offset': 0,           # Resume point
        }
        # Look like Android to let the PMS use the transcoding profile
        xargs.update(headers)
        LOG.debug("Setting transcode quality to: %s", quality)
        args.update(quality)
        url = transcodePath + urlencode(xargs) + '&' + urlencode(args)
        return url

    def externalSubs(self):
        externalsubs = []
        try:
            mediastreams = self.item[0][self.part]
        except (TypeError, KeyError, IndexError):
            return
        kodiindex = 0
        fileindex = 0
        for stream in mediastreams:
            # Since plex returns all possible tracks together, have to pull
            # only external subtitles - only for these a 'key' exists
            if stream.attrib.get('streamType') != "3":
                # Not a subtitle
                continue
            # Only set for additional external subtitles NOT lying beside video
            key = stream.attrib.get('key')
            # Only set for dedicated subtitle files lying beside video
            # ext = stream.attrib.get('format')
            if key:
                # We do know the language - temporarily download
                if stream.attrib.get('languageCode') is not None:
                    path = self.download_external_subtitles(
                        "{server}%s" % key,
                        "subtitle%02d.%s.%s" % (fileindex,
                                                stream.attrib['languageCode'],
                                                stream.attrib['codec']))
                    fileindex += 1
                # We don't know the language - no need to download
                else:
                    path = self.addPlexCredentialsToUrl(
                        "%s%s" % (self.server, key))
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
        if not exists_dir(v.EXTERNAL_SUBTITLE_TEMP_PATH):
            makedirs(v.EXTERNAL_SUBTITLE_TEMP_PATH)
        path = join(v.EXTERNAL_SUBTITLE_TEMP_PATH, filename)
        r = DU().downloadUrl(url, return_response=True)
        try:
            r.status_code
        except AttributeError:
            LOG.error('Could not temporarily download subtitle %s', url)
            return
        else:
            LOG.debug('Writing temp subtitle to %s', path)
            try:
                with open(path, 'wb') as f:
                    f.write(r.content)
            except UnicodeEncodeError:
                LOG.debug('Need to slugify the filename %s', path)
                path = slugify(path)
                with open(path, 'wb') as f:
                    f.write(r.content)
            return path

    def GetKodiPremierDate(self):
        """
        Takes Plex' originallyAvailableAt of the form "yyyy-mm-dd" and returns
        Kodi's "dd.mm.yyyy"
        """
        date = self.getPremiereDate()
        if date is None:
            return
        try:
            date = sub(r'(\d+)-(\d+)-(\d+)', r'\3.\2.\1', date)
        except:
            date = None
        return date

    def CreateListItemFromPlexItem(self,
                                   listItem=None,
                                   appendShowTitle=False,
                                   appendSxxExx=False):
        if self.getType() == v.PLEX_TYPE_PHOTO:
            listItem = self.__createPhotoListItem(listItem)
            # Only set the bare minimum of artwork
            listItem.setArt({'icon': 'DefaultPicture.png',
                             'fanart': self.__getOneArtwork('thumb')})
        else:
            listItem = self.__createVideoListItem(listItem,
                                                  appendShowTitle,
                                                  appendSxxExx)
            self.add_video_streams(listItem)
            self.set_listitem_artwork(listItem)
        return listItem

    def __createPhotoListItem(self, listItem=None):
        """
        Use for photo items only
        """
        title, _ = self.getTitle()
        if listItem is None:
            listItem = ListItem(title)
        else:
            listItem.setLabel(title)
        metadata = {
            'date': self.GetKodiPremierDate(),
            'size': long(self.item[0][0].attrib.get('size', 0)),
            'exif:width': self.item[0].attrib.get('width', ''),
            'exif:height': self.item[0].attrib.get('height', ''),
        }
        listItem.setInfo(type='image', infoLabels=metadata)
        listItem.setProperty('plot', self.getPlot())
        listItem.setProperty('plexid', self.getRatingKey())
        return listItem

    def __createVideoListItem(self,
                              listItem=None,
                              appendShowTitle=False,
                              appendSxxExx=False):
        """
        Use for video items only
        Call on a child level of PMS xml response (e.g. in a for loop)

        listItem        : existing xbmcgui.ListItem to work with
                          otherwise, a new one is created
        appendShowTitle : True to append TV show title to episode title
        appendSxxExx    : True to append SxxExx to episode title

        Returns XBMC listitem for this PMS library item
        """
        title, sorttitle = self.getTitle()
        typus = self.getType()

        if listItem is None:
            listItem = ListItem(title)
        else:
            listItem.setLabel(title)
        # Necessary; Kodi won't start video otherwise!
        listItem.setProperty('IsPlayable', 'true')
        # Video items, e.g. movies and episodes or clips
        people = self.getPeople()
        userdata = self.getUserData()
        metadata = {
            'genre': self.joinList(self.getGenres()),
            'year': self.getYear(),
            'rating': self.getAudienceRating(),
            'playcount': userdata['PlayCount'],
            'cast': people['Cast'],
            'director': self.joinList(people.get('Director')),
            'plot': self.getPlot(),
            'sorttitle': sorttitle,
            'duration': userdata['Runtime'],
            'studio': self.joinList(self.getStudios()),
            'tagline': self.getTagline(),
            'writer': self.joinList(people.get('Writer')),
            'premiered': self.getPremiereDate(),
            'dateadded': self.getDateCreated(),
            'lastplayed': userdata['LastPlayedDate'],
            'mpaa': self.getMpaa(),
            'aired': self.getPremiereDate()
        }
        # Do NOT set resumetime - otherwise Kodi always resumes at that time
        # even if the user chose to start element from the beginning
        # listItem.setProperty('resumetime', str(userdata['Resume']))
        listItem.setProperty('totaltime', str(userdata['Runtime']))

        if typus == v.PLEX_TYPE_EPISODE:
            key, show, season, episode = self.getEpisodeDetails()
            season = -1 if season is None else int(season)
            episode = -1 if episode is None else int(episode)
            metadata['episode'] = episode
            metadata['season'] = season
            metadata['tvshowtitle'] = show
            if season and episode:
                listItem.setProperty('episodeno',
                                     "s%.2de%.2d" % (season, episode))
                if appendSxxExx is True:
                    title = "S%.2dE%.2d - %s" % (season, episode, title)
            listItem.setArt({'icon': 'DefaultTVShows.png'})
            if appendShowTitle is True:
                title = "%s - %s " % (show, title)
            if appendShowTitle or appendSxxExx:
                listItem.setLabel(title)
        elif typus == v.PLEX_TYPE_MOVIE:
            listItem.setArt({'icon': 'DefaultMovies.png'})
        else:
            # E.g. clips, trailers, ...
            listItem.setArt({'icon': 'DefaultVideo.png'})

        plexId = self.getRatingKey()
        listItem.setProperty('plexid', plexId)
        with plexdb.Get_Plex_DB() as plex_db:
            try:
                listItem.setProperty('dbid',
                                     str(plex_db.getItem_byId(plexId)[0]))
            except TypeError:
                pass
        # Expensive operation
        metadata['title'] = title
        listItem.setInfo('video', infoLabels=metadata)
        try:
            # Add context menu entry for information screen
            listItem.addContextMenuItems([(lang(30032), 'XBMC.Action(Info)',)])
        except TypeError:
            # Kodi fuck-up
            pass
        return listItem

    def add_video_streams(self, listItem):
        """
        Add media stream information to xbmcgui.ListItem
        """
        for key, value in self.getMediaStreams().iteritems():
            if value:
                listItem.addStreamInfo(key, value)

    def validatePlayurl(self, path, typus, forceCheck=False, folder=False,
                        omitCheck=False):
        """
        Returns a valid path for Kodi, e.g. with '\' substituted to '\\' in
        Unicode. Returns None if this is not possible

            path       : Unicode
            typus      : Plex type from PMS xml
            forceCheck : Will always try to check validity of path
                         Will also skip confirmation dialog if path not found
            folder     : Set to True if path is a folder
            omitCheck  : Will entirely omit validity check if True
        """
        if path is None:
            return None
        typus = v.REMAP_TYPE_FROM_PLEXTYPE[typus]
        if state.REMAP_PATH is True:
            path = path.replace(getattr(state, 'remapSMB%sOrg' % typus),
                                getattr(state, 'remapSMB%sNew' % typus),
                                1)
            # There might be backslashes left over:
            path = path.replace('\\', '/')
        elif state.REPLACE_SMB_PATH is True:
            if path.startswith('\\\\'):
                path = 'smb:' + path.replace('\\', '/')
        if ((state.PATH_VERIFIED and forceCheck is False) or
                omitCheck is True):
            return path

        # exist() needs a / or \ at the end to work for directories
        if folder is False:
            # files
            check = exists(tryEncode(path))
        else:
            # directories
            if "\\" in path:
                if not path.endswith('\\'):
                    # Add the missing backslash
                    check = exists_dir(path + "\\")
                else:
                    check = exists_dir(path)
            else:
                if not path.endswith('/'):
                    check = exists_dir(path + "/")
                else:
                    check = exists_dir(path)

        if not check:
            if forceCheck is False:
                # Validate the path is correct with user intervention
                if self.askToValidate(path):
                    state.STOP_SYNC = True
                    path = None
                state.PATH_VERIFIED = True
            else:
                path = None
        elif forceCheck is False:
            # Only set the flag if we were not force-checking the path
            state.PATH_VERIFIED = True
        return path

    def askToValidate(self, url):
        """
        Displays a YESNO dialog box:
            Kodi can't locate file: <url>. Please verify the path.
            You may need to verify your network credentials in the
            add-on settings or use different Plex paths. Stop syncing?

        Returns True if sync should stop, else False
        """
        LOG.warn('Cannot access file: %s', url)
        resp = dialog('yesno',
                      heading=lang(29999),
                      line1=lang(39031) + url,
                      line2=lang(39032))
        return resp

    def set_listitem_artwork(self, listitem):
        """
        Set all artwork to the listitem
        """
        allartwork = self.getAllArtwork(parentInfo=True)
        arttypes = {
            'poster': "Primary",
            'tvshow.poster': "Thumb",
            'clearart': "Art",
            'tvshow.clearart': "Art",
            'clearart': "Primary",
            'tvshow.clearart': "Primary",
            'clearlogo': "Logo",
            'tvshow.clearlogo': "Logo",
            'discart': "Disc",
            'fanart_image': "Backdrop",
            'landscape': "Backdrop",
            "banner": "Banner"
        }
        for arttype in arttypes:
            art = arttypes[arttype]
            if art == "Backdrop":
                try:
                    # Backdrop is a list, grab the first backdrop
                    self._set_listitem_artprop(listitem,
                                               arttype,
                                               allartwork[art][0])
                except:
                    pass
            else:
                self._set_listitem_artprop(listitem, arttype, allartwork[art])

    def _set_listitem_artprop(self, listitem, arttype, path):
        if arttype in (
                'thumb', 'fanart_image', 'small_poster', 'tiny_poster',
                'medium_landscape', 'medium_poster', 'small_fanartimage',
                'medium_fanartimage', 'fanart_noindicators'):
            listitem.setProperty(arttype, path)
        else:
            listitem.setArt({arttype: path})

    def set_playback_win_props(self, playurl, listitem):
        """
        Set all properties necessary for plugin path playback for listitem
        """
        itemtype = self.getType()
        userdata = self.getUserData()

        plexitem = "plex_%s" % playurl
        window('%s.runtime' % plexitem, value=str(userdata['Runtime']))
        window('%s.type' % plexitem, value=itemtype)
        state.PLEX_IDS[tryDecode(playurl)] = self.getRatingKey()
        # window('%s.itemid' % plexitem, value=self.getRatingKey())
        window('%s.playcount' % plexitem, value=str(userdata['PlayCount']))

        if itemtype == v.PLEX_TYPE_EPISODE:
            window('%s.refreshid' % plexitem, value=self.getParentRatingKey())
        else:
            window('%s.refreshid' % plexitem, value=self.getRatingKey())

        # Append external subtitles to stream
        playmethod = window('%s.playmethod' % plexitem)
        # Direct play automatically appends external
        # BUT: Plex may add additional subtitles NOT lying right next to video
        if playmethod in ("DirectStream", "DirectPlay"):
            listitem.setSubtitles(self.externalSubs(playurl))

# -*- coding: utf-8 -*-
from urllib import urlencode
from ast import literal_eval
from urlparse import urlparse, parse_qs
import re
from copy import deepcopy
import requests

from xbmcaddon import Addon

import downloadutils
from utils import logMsg, settings

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


addonName = Addon().getAddonInfo('name')
title = "%s %s" % (addonName, __name__)


def PlexToKodiTimefactor():
    """
    Kodi measures time in seconds, but Plex in milliseconds
    """
    return 1.0 / 1000.0


def ConvertPlexToKodiTime(plexTime):
    """
    Converts Plextime to Koditime. Returns an int (in seconds).
    """
    if plexTime is None:
        return None
    return int(float(plexTime) * PlexToKodiTimefactor())


def GetItemClassFromType(itemType):
    classes = {
        'movie': 'Movies',
        'season': 'TVShows',
        'episode': 'TVShows',
        'show': 'TVShows',
        'artist': 'Music',
        'album': 'Music',
        'track': 'Music'
    }
    return classes[itemType]


def GetItemClassFromNumber(itemType):
    classes = {
        1: 'Movies',
        4: 'TVShows',
    }
    return classes[itemType]


def GetKodiTypeFromPlex(plexItemType):
    """
    As used in playlist.item here: http://kodi.wiki/view/JSON-RPC_API
    """
    classes = {
        'movie': 'movie',
        'episode': 'episode',
        'track': 'song',
        'artist': 'artist',
        'album': 'album',
        'XXXXXX': 'musicvideo',
        'XXXXXXX': 'genre'
    }
    return classes[plexItemType.lower()]


def GetPlexKeyNumber(plexKey):
    """
    Deconstructs e.g. '/library/metadata/xxxx' to the tuple

        ('library/metadata', 'xxxx')

    Returns ('','') if nothing is found
    """
    regex = re.compile(r'''/(.+)/(\d+)$''')
    try:
        result = regex.findall(plexKey)[0]
    except IndexError:
        result = ('', '')
    return result


def ParseContainerKey(containerKey):
    """
    Parses e.g. /playQueues/3045?own=1&repeat=0&window=200 to:
    'playQueues', '3045', {'window': ['200'], 'own': ['1'], 'repeat': ['0']}

    Output hence: library, key, query       (query as a special dict)
    """
    result = urlparse(containerKey)
    library, key = GetPlexKeyNumber(result.path)
    query = parse_qs(result.query)
    return library, key, query


def LiteralEval(string):
    """
    Turns a string e.g. in a dict, safely :-)
    """
    return literal_eval(string)


def GetMethodFromPlexType(plexType):
    methods = {
        'movie': 'add_update',
        'episode': 'add_updateEpisode',
        'show': 'add_update',
        'season': 'add_updateSeason',
        'track': 'add_updateSong',
        'album': 'add_updateAlbum',
        'artist': 'add_updateArtist'
    }
    return methods[plexType]


def XbmcItemtypes():
    return ['photo', 'video', 'audio']


def PlexItemtypes():
    return ['photo', 'video', 'audio']


def PlexLibraryItemtypes():
    return ['movie', 'show']
    # later add: 'artist', 'photo'


def EmbyItemtypes():
    return ['Movie', 'Series', 'Season', 'Episode']


def SelectStreams(url, args):
    """
    Does a PUT request to tell the PMS what audio and subtitle streams we have
    chosen.
    """
    downloadutils.DownloadUtils().downloadUrl(
        url + '?' + urlencode(args), type='PUT')


def GetPlayQueue(playQueueID):
    """
    Fetches the PMS playqueue with the playQueueID as an XML

    Returns None if something went wrong
    """
    url = "{server}/playQueues/%s" % playQueueID
    args = {'Accept': 'application/xml'}
    xml = downloadutils.DownloadUtils().downloadUrl(url, headerOptions=args)
    try:
        xml.attrib['playQueueID']
    except (AttributeError, KeyError):
        return None
    return xml


def GetPlexMetadata(key):
    """
    Returns raw API metadata for key as an etree XML.

    Can be called with either Plex key '/library/metadata/xxxx'metadata
    OR with the digits 'xxxx' only.

    Returns None if something went wrong
    """
    key = str(key)
    if '/library/metadata/' in key:
        url = "{server}" + key
    else:
        url = "{server}/library/metadata/" + key
    arguments = {
        'checkFiles': 1,            # No idea
        'includeExtras': 1,         # Trailers and Extras => Extras
        # 'includeRelated': 1,        # Similar movies => Video -> Related
        # 'includeRelatedCount': 5,
        # 'includeOnDeck': 1,
        'includeChapters': 1,
        'includePopularLeaves': 1,
        'includeConcerts': 1
    }
    url = url + '?' + urlencode(arguments)
    xml = downloadutils.DownloadUtils().downloadUrl(url)
    # Did we receive a valid XML?
    try:
        xml.attrib
    # Nope we did not receive a valid XML
    except AttributeError:
        logMsg(title, "Error retrieving metadata for %s" % url, -1)
        xml = None
    return xml


def GetAllPlexChildren(key, containerSize=None):
    """
    Returns a list (raw xml API dump) of all Plex children for the key.
    (e.g. /library/metadata/194853/children pointing to a season)

    Input:
        key             Key to a Plex item, e.g. 12345
    """
    url = "{server}/library/metadata/%s/children?" % key
    return DownloadChunks(url, containerSize)


def GetPlexSectionResults(viewId, args=None, containerSize=None):
    """
    Returns a list (XML API dump) of all Plex items in the Plex
    section with key = viewId.

    Input:
        args:       optional dict to be urlencoded

    Returns None if something went wrong
    """
    url = "{server}/library/sections/%s/all?" % viewId
    if args:
        url += urlencode(args) + '&'
    return DownloadChunks(url, containerSize)


def DownloadChunks(url, containerSize):
    """
    Downloads PMS url in chunks of containerSize (int).
    If containerSize is None: ONE xml is fetched directly

    url MUST end with '?' (if no other url encoded args are present) or '&'

    Returns a stitched-together xml or None.
    """
    if containerSize is None:
        # Get rid of '?' or '&' at the end of url
        xml = downloadutils.DownloadUtils().downloadUrl(url[:-1])
        try:
            xml.attrib
        except AttributeError:
            # Nope, not an XML, abort
            logMsg(title, "Error getting url %s" % url[:-1], -1)
            return None
        else:
            return xml

    xml = None
    pos = 0
    errorCounter = 0
    while errorCounter < 10:
        args = {
            'X-Plex-Container-Size': containerSize,
            'X-Plex-Container-Start': pos
        }
        xmlpart = downloadutils.DownloadUtils().downloadUrl(
            url + urlencode(args))
        # If something went wrong - skip in the hope that it works next time
        try:
            xmlpart.attrib
        except AttributeError:
            logMsg(title, 'Error while downloading chunks: %s'
                   % (url + urlencode(args)), -1)
            pos += containerSize
            errorCounter += 1
            continue

        # Very first run: starting xml (to retain data in xml's root!)
        if xml is None:
            xml = deepcopy(xmlpart)
            if len(xmlpart) < containerSize:
                break
            else:
                pos += containerSize
                continue
        # Build answer xml - containing the entire library
        for child in xmlpart:
            xml.append(child)
        # Done as soon as we don't receive a full complement of items
        if len(xmlpart) < containerSize:
            break
        pos += containerSize
    if errorCounter == 10:
        logMsg(title, 'Fatal error while downloading chunks for %s' % url, -1)
        return None
    return xml


def GetAllPlexLeaves(viewId, lastViewedAt=None, updatedAt=None,
                     containerSize=None):
    """
    Returns a list (raw XML API dump) of all Plex subitems for the key.
    (e.g. /library/sections/2/allLeaves pointing to all TV shows)

    Input:
        viewId              Id of Plex library, e.g. '2'
        lastViewedAt        Unix timestamp; only retrieves PMS items viewed
                            since that point of time until now.
        updatedAt           Unix timestamp; only retrieves PMS items updated
                            by the PMS since that point of time until now.
        containerSize       Number of items simultaneously fetched from PMS

    If lastViewedAt and updatedAt=None, ALL PMS items are returned.

    Warning: lastViewedAt and updatedAt are combined with AND by the PMS!

    Relevant "master time": PMS server. I guess this COULD lead to problems,
    e.g. when server and client are in different time zones.
    """
    args = []
    url = "{server}/library/sections/%s/allLeaves" % viewId

    if lastViewedAt:
        args.append('lastViewedAt>=%s' % lastViewedAt)
    if updatedAt:
        args.append('updatedAt>=%s' % updatedAt)
    if args:
        url += '?' + '&'.join(args) + '&'
    else:
        url += '?'
    return DownloadChunks(url, containerSize)


def GetPlexOnDeck(viewId, containerSize=None):
    """
    """
    url = "{server}/library/sections/%s/onDeck?" % viewId
    return DownloadChunks(url, containerSize)


def GetPlexCollections(mediatype):
    """
    Input:
        mediatype           String or list of strings with possible values
                            'movie', 'show', 'artist', 'photo'
    Output:
        List with an entry of the form:
        {
        'name': xxx         Plex title for the media section
        'type': xxx         Plex type: 'movie', 'show', 'artist', 'photo'
        'id': xxx           Plex unique key for the section (1, 2, 3...)
        'uuid': xxx         Other unique Plex key, e.g.
                            74aec9f2-a312-4723-9436-de2ea43843c1
        }
    Returns an empty list if nothing is found.
    """
    collections = []
    url = "{server}/library/sections"
    xml = downloadutils.DownloadUtils().downloadUrl(url)
    try:
        xml.attrib
    except AttributeError:
        logMsg(title, 'Could not download PMS sections for %s' % url, -1)
        return {}
    for item in xml:
        contentType = item['type']
        if contentType in mediatype:
            name = item['title']
            contentId = item['key']
            uuid = item['uuid']
            collections.append({
                'name': name,
                'type': contentType,
                'id': str(contentId),
                'uuid': uuid
            })
    return collections


def GetPlexPlaylist(itemid, librarySectionUUID, mediatype='movie'):
    """
    Returns raw API metadata XML dump for a playlist with e.g. trailers.
   """
    trailerNumber = settings('trailerNumber')
    if not trailerNumber:
        trailerNumber = '3'
    url = "{server}/playQueues"
    args = {
        'type': mediatype,
        'uri': 'library://' + librarySectionUUID +
                    '/item/%2Flibrary%2Fmetadata%2F' + itemid,
        'includeChapters': '1',
        'extrasPrefixCount': trailerNumber,
        'shuffle': '0',
        'repeat': '0'
    }
    xml = downloadutils.DownloadUtils().downloadUrl(
        url + '?' + urlencode(args), type="POST")
    try:
        xml[0].tag
    except (IndexError, TypeError, AttributeError):
        logMsg(title, "Error retrieving metadata for %s" % url, -1)
        return None
    return xml


def getPlexRepeat(kodiRepeat):
    plexRepeat = {
        'off': '0',
        'one': '1',
        'all': '2'   # does this work?!?
    }
    return plexRepeat.get(kodiRepeat)


def PMSHttpsEnabled(url):
    """
    Returns True if the PMS wants to talk https, False otherwise. None if error
    occured, e.g. the connection timed out

    With with e.g. url=192.168.0.1:32400 (NO http/https)

    This is done by GET /identity (returns an error if https is enabled and we
    are trying to use http)

    Prefers HTTPS over HTTP
    """
    # True if https, False if http
    answer = True
    try:
        # Don't use downloadutils here, otherwise we may get un-authorized!
        res = requests.get('https://%s/identity' % url,
                           headers={},
                           verify=False,
                           timeout=(3, 10))
        # Don't verify SSL since we can connect for sure then!
    except requests.exceptions.ConnectionError as e:
        # Might have SSL deactivated. Try with http
        try:
            res = requests.get('http://%s/identity' % url,
                               headers={},
                               timeout=(3, 10))
        except requests.exceptions.ConnectionError as e:
            logMsg(title, "Server is offline or cannot be reached. Url: %s"
                   ", Error message: %s" % (url, e), -1)
            return None
        except requests.exceptions.ReadTimeout:
            logMsg(title, "Server timeout reached for Url %s" % url, -1)
            return None
        else:
            answer = False
    except requests.exceptions.ReadTimeout:
        logMsg(title, "Server timeout reached for Url %s" % url, -1)
        return None
    if res.status_code == requests.codes.ok:
        return answer
    else:
        return None


def GetMachineIdentifier(url):
    """
    Returns the unique PMS machine identifier of url

    Returns None if something went wrong
    """
    xml = downloadutils.DownloadUtils().downloadUrl(
        url + '/identity', type="GET")
    try:
        xml.attrib
    except:
        logMsg(title, 'Could not get the PMS machineIdentifier for %s'
               % url, -1)
        return None
    machineIdentifier = xml.attrib.get('machineIdentifier')
    logMsg(title, 'Found machineIdentifier %s for %s'
           % (machineIdentifier, url), 1)
    return machineIdentifier


def scrobble(ratingKey, state):
    """
    Tells the PMS to set an item's watched state to state="watched" or
    state="unwatched"
    """
    args = {
        'key': ratingKey,
        'identifier': 'com.plexapp.plugins.library'
    }
    if state == "watched":
        url = "{server}/:/scrobble?" + urlencode(args)
    elif state == "unwatched":
        url = "{server}/:/unscrobble?" + urlencode(args)
    else:
        return
    downloadutils.DownloadUtils().downloadUrl(url, type="GET")
    logMsg(title, "Toggled watched state for Plex item %s" % ratingKey, 1)

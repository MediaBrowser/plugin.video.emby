# -*- coding: utf-8 -*-
from urllib import urlencode
from ast import literal_eval
from urlparse import urlparse, parse_qs
import re

from xbmcaddon import Addon

import downloadutils
from utils import logMsg, settings


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


def GetAllPlexChildren(key):
    """
    Returns a list (raw xml API dump) of all Plex children for the key.
    (e.g. /library/metadata/194853/children pointing to a season)

    Input:
        key             Key to a Plex item, e.g. 12345
    """
    xml = downloadutils.DownloadUtils().downloadUrl(
        "{server}/library/metadata/%s/children" % key)
    try:
        xml.attrib
    except AttributeError:
        logMsg(
            title, "Error retrieving all children for Plex item %s" % key, -1)
        xml = None
    return xml


def GetPlexSectionResults(viewId, args=None):
    """
    Returns a list (XML API dump) of all Plex items in the Plex
    section with key = viewId.

    Input:
        args:       optional dict to be urlencoded

    Returns None if something went wrong
    """
    result = []
    url = "{server}/library/sections/%s/all" % viewId
    if args:
        url += "?" + urlencode(args)

    result = downloadutils.DownloadUtils().downloadUrl(url)

    try:
        result.tag
    # Nope, not an XML, abort
    except AttributeError:
        logMsg(title,
               "Error retrieving all items for Plex section %s"
               % viewId, -1)
        result = None

    return result


def GetAllPlexLeaves(viewId, lastViewedAt=None, updatedAt=None):
    """
    Returns a list (raw XML API dump) of all Plex subitems for the key.
    (e.g. /library/sections/2/allLeaves pointing to all TV shows)

    Input:
        viewId              Id of Plex library, e.g. '2'
        lastViewedAt        Unix timestamp; only retrieves PMS items viewed
                            since that point of time until now.
        updatedAt           Unix timestamp; only retrieves PMS items updated
                            by the PMS since that point of time until now.

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
        url += '?' + '&'.join(args)

    xml = downloadutils.DownloadUtils().downloadUrl(url)

    try:
        xml.attrib
    # Nope, not an XML, abort
    except AttributeError:
        logMsg(title,
               "Error retrieving all leaves for Plex section %s"
               % viewId, -1)
        xml = None
    return xml


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
    jsondata = downloadutils.DownloadUtils().downloadUrl(url)
    try:
        result = jsondata['_children']
    except KeyError:
        pass
    else:
        for item in result:
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
        logMsg("Error retrieving metadata for %s" % url, -1)
        return None
    return xml


def getPlexRepeat(kodiRepeat):
    plexRepeat = {
        'off': '0',
        'one': '1',
        'all': '2'   # does this work?!?
    }
    return plexRepeat.get(kodiRepeat)

# -*- coding: utf-8 -*-
from urllib import urlencode

from xbmcaddon import Addon

from downloadutils import DownloadUtils
from utils import logMsg


addonName = Addon().getAddonInfo('name')
title = "%s %s" % (addonName, __name__)


def GetItemClassFromType(itemType):
    classes = {
        'movie': 'Movies',
        'episodes': 'TVShows',
        'episode': 'TVShows',
        'show': 'TVShows'
    }
    return classes[itemType]


def GetMethodFromPlexType(plexType):
    methods = {
        'movie': 'add_update',
        'episode': 'add_updateEpisode'
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


def XbmcPhoto():
    return "photo"
def XbmcVideo():
    return "video"
def XbmcAudio():
    return "audio"
def PlexPhoto():
    return "photo"
def PlexVideo():
    return "video"
def PlexAudio():
    return "music"


def GetPlexMetadata(key):
    """
    Returns raw API metadata for key as an etree XML.

    Can be called with either Plex key '/library/metadata/xxxx'metadata
    OR with the digits 'xxxx' only.

    Returns an empty string '' if something went wrong
    """
    xml = ''
    key = str(key)
    if '/library/metadata/' in key:
        url = "{server}" + key
    else:
        url = "{server}/library/metadata/" + key
    arguments = {
        'checkFiles': 1,            # No idea
        'includeExtras': 1,         # Trailers and Extras => Extras
        'includeRelated': 1,        # Similar movies => Video -> Related
        'includeRelatedCount': 5,
        'includeOnDeck': 1,
        'includeChapters': 1,
        'includePopularLeaves': 1,
        'includeConcerts': 1
    }
    url = url + '?' + urlencode(arguments)
    headerOptions = {'Accept': 'application/xml'}
    xml = DownloadUtils().downloadUrl(url, headerOptions=headerOptions)
    # Did we receive a valid XML?
    try:
        xml.tag
    # Nope we did not receive a valid XML
    except AttributeError:
        logMsg(title, "Error retrieving metadata for %s" % url, -1)
        xml = ''
    return xml


def GetAllPlexChildren(key):
    """
    Returns a list (raw JSON API dump) of all Plex children for the key.
    (e.g. /library/metadata/194853/children pointing to a season)

    Input:
        key             Key to a Plex item, e.g. 12345
    """
    result = []
    url = "{server}/library/metadata/%s/children" % key
    jsondata = DownloadUtils().downloadUrl(url)
    try:
        result = jsondata['_children']
    except KeyError:
        logMsg(
            title, "Error retrieving all children for Plex item %s" % key, -1)
        pass
    return result


def GetPlexSectionResults(viewId, headerOptions={}):
    """
    Returns a list (raw JSON or XML API dump) of all Plex items in the Plex
    section with key = viewId.
    """
    result = []
    url = "{server}/library/sections/%s/all" % viewId
    jsondata = DownloadUtils().downloadUrl(url, headerOptions=headerOptions)
    try:
        result = jsondata['_children']
    except TypeError:
        # Maybe we received an XML, check for that with tag attribute
        try:
            jsondata.tag
            result = jsondata
        # Nope, not an XML, abort
        except AttributeError:
            logMsg(title,
                   "Error retrieving all items for Plex section %s"
                   % viewId, -1)
            return result
    except KeyError:
        logMsg(title,
               "Error retrieving all items for Plex section %s"
               % viewId, -1)
    return result


def GetPlexUpdatedItems(viewId, unixTime, headerOptions={}):
    """
    Returns a list (raw JSON or XML API dump) of all Plex items in the Plex
    section with key = viewId AFTER the unixTime
    """
    result = []
    url = "{server}/library/sections/%s/allLeaves?updatedAt>=%s" \
          % (viewId, unixTime)
    jsondata = DownloadUtils().downloadUrl(url, headerOptions=headerOptions)
    try:
        result = jsondata['_children']
    except KeyError:
        logMsg(title,
               "Error retrieving all items for Plex section %s and time %s"
               % (viewId, unixTime), -1)
    return result


def GetAllPlexLeaves(viewId, headerOptions={}):
    """
    Returns a list (raw JSON or XML API dump) of all Plex subitems for the
    key.
    (e.g. /library/sections/2/allLeaves pointing to all TV shows)

    Input:
        viewId            Id of Plex library, e.g. '2'
        headerOptions     to override the download headers
    """
    result = []
    url = "{server}/library/sections/%s/allLeaves" % viewId
    jsondata = DownloadUtils().downloadUrl(url, headerOptions=headerOptions)
    try:
        result = jsondata['_children']
    except TypeError:
        # Maybe we received an XML, check for that with tag attribute
        try:
            jsondata.tag
            result = jsondata
        # Nope, not an XML, abort
        except AttributeError:
            logMsg(title,
                   "Error retrieving all leaves for Plex section %s"
                   % viewId, -1)
            return result
    except KeyError:
        logMsg("Error retrieving all leaves for Plex viewId %s" % viewId, -1)
    return result


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
    jsondata = DownloadUtils().downloadUrl(url)
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

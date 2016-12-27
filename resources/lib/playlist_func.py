import logging
from urllib import quote

import embydb_functions as embydb
from downloadutils import DownloadUtils as DU
from utils import JSONRPC, tryEncode

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class Playlist_Object_Baseclase(object):
    playlistid = None     # Kodi playlist ID, [int]
    type = None           # Kodi type: 'audio', 'video', 'picture'
    kodi_pl = None        # Kodi xbmc.PlayList object
    items = []            # list of PLAYLIST_ITEMS
    old_kodi_pl = []      # to store old Kodi JSON result with all pl items
    ID = None             # Plex id, e.g. playQueueID
    version = None        # Plex version, [int]
    selectedItemID = None
    selectedItemOffset = None
    shuffled = 0          # [int], 0: not shuffled, 1: ??? 2: ???
    repeat = 0            # [int], 0: not repeated, 1: ??? 2: ???

    def __repr__(self):
        answ = "<%s object: " % (self.__class__.__name__)
        for key in self.__dict__:
            answ += '%s: %s, ' % (key, getattr(self, key))
        return answ[:-2] + ">"


class Playlist_Object(Playlist_Object_Baseclase):
    kind = 'playList'


class Playqueue_Object(Playlist_Object_Baseclase):
    kind = 'playQueue'


class Playlist_Item(object):
    ID = None               # Plex playlist/playqueue id, e.g. playQueueItemID
    plex_id = None          # Plex unique item id, "ratingKey"
    plex_UUID = None        # Plex librarySectionUUID
    kodi_id = None          # Kodi unique kodi id (unique only within type!)
    kodi_type = None        # Kodi type: 'movie'
    file = None             # Path to the item's file
    uri = None              # Weird Plex uri path involving plex_UUID


def playlist_item_from_kodi_item(kodi_item):
    """
    Turns the JSON answer from Kodi into a playlist element

    Supply with data['item'] as returned from Kodi JSON-RPC interface.
    kodi_item dict contains keys 'id', 'type', 'file' (if applicable)
    """
    item = Playlist_Item()
    if kodi_item.get('id'):
        item.kodi_id = kodi_item['id']
        with embydb.GetEmbyDB() as emby_db:
            emby_dbitem = emby_db.getItem_byKodiId(kodi_item['id'],
                                                   kodi_item['type'])
        try:
            item.plex_id = emby_dbitem[0]
            item.plex_UUID = emby_dbitem[0]
        except TypeError:
            pass
    item.file = kodi_item.get('file') if kodi_item.get('file') else None
    item.kodi_type = kodi_item.get('type') if kodi_item.get('type') else None
    if item.plex_id is None:
        item.uri = 'library://whatever/item/%s' % quote(item.file, safe='')
    else:
        item.uri = ('library://%s/item/library%%2Fmetadata%%2F%s' %
                    (item.plex_UUID, item.plex_id))
    return item


def playlist_item_from_plex(plex_id):
    """
    Returns a playlist element providing the plex_id ("ratingKey")
    """
    item = Playlist_Item()
    item.plex_id = plex_id
    with embydb.GetEmbyDB() as emby_db:
        emby_dbitem = emby_db.getItem_byId(plex_id)
    try:
        item.kodi_id = emby_dbitem[0]
        item.kodi_type = emby_dbitem[4]
    except:
        raise KeyError('Could not find plex_id %s in database' % plex_id)
    return item


def _log_xml(xml):
    try:
        xml.attrib
    except AttributeError:
        log.error('Did not receive an XML. Answer was: %s' % xml)
    else:
        from xml.etree.ElementTree import dump
        log.error('XML received from the PMS: %s' % dump(xml))


def _get_playListVersion_from_xml(playlist, xml):
    """
    Takes a PMS xml as input to overwrite the playlist version (e.g. Plex
    playQueueVersion). Returns True if successful, False otherwise
    """
    try:
        playlist.version = int(xml.attrib['%sVersion' % playlist.kind])
    except (TypeError, AttributeError, KeyError):
        log.error('Could not get new playlist Version for playlist %s'
                  % playlist)
        _log_xml(xml)
        return False
    return True


def _get_playlist_details_from_xml(playlist, xml):
    """
    Takes a PMS xml as input and overwrites all the playlist's details, e.g.
    playlist.ID with the XML's playQueueID
    """
    try:
        playlist.ID = xml.attrib['%sID' % playlist.kind]
        playlist.version = xml.attrib['%sVersion' % playlist.kind]
        playlist.selectedItemID = xml.attrib['%sSelectedItemID' % playlist.kind]
        playlist.selectedItemOffset = xml.attrib['%sSelectedItemOffset' % playlist.kind]
        playlist.shuffled = xml.attrib['%sShuffled' % playlist.kind]
    except:
        log.error('Could not parse xml answer from PMS for playlist %s'
                  % playlist)
        import traceback
        log.error(traceback.format_exc())
        _log_xml(xml)
        raise KeyError


def init_Plex_playlist(playlist, plex_id=None, kodi_item=None):
    """
    Supply either plex_id or the data supplied by Kodi JSON-RPC
    """
    if plex_id is not None:
        item = playlist_item_from_plex(plex_id)
    else:
        item = playlist_item_from_kodi_item(kodi_item)
    params = {
        'next': 0,
        'type': playlist.type,
        'uri': item.uri
    }
    xml = DU().downloadUrl(url="{server}/%ss" % playlist.kind,
                           action_type="POST",
                           parameters=params)
    _get_playlist_details_from_xml(xml)
    playlist.items.append(item)
    log.debug('Initialized the playlist: %s' % playlist)


def add_playlist_item(playlist, kodi_item, after_pos):
    """
    Adds the new kodi_item to playlist after item at position after_pos
    [int]
    """
    item = playlist_item_from_kodi_item(kodi_item)
    url = "{server}/%ss/%s?uri=%s" % (playlist.kind, playlist.ID, item.uri)
    # Will always put the new item at the end of the playlist
    xml = DU().downloadUrl(url, action_type="PUT")
    try:
        item.ID = xml.attrib['%sLastAddedItemID' % playlist.kind]
    except (TypeError, AttributeError, KeyError):
        log.error('Could not add item %s to playlist %s'
                  % (kodi_item, playlist))
        _log_xml(xml)
        return
    playlist.items.append(item)
    if after_pos == len(playlist.items) - 1:
        # Item was added at the end
        _get_playListVersion_from_xml(playlist, xml)
    else:
        # Move the new item to the correct position
        move_playlist_item(playlist,
                           len(playlist.items) - 1,
                           after_pos)


def move_playlist_item(playlist, before_pos, after_pos):
    """
    Moves playlist item from before_pos [int] to after_pos [int]
    """
    if after_pos == 0:
        url = "{server}/%ss/%s/items/%s/move?after=0" % \
              (playlist.kind,
               playlist.ID,
               playlist.items[before_pos].ID)
    else:
        url = "{server}/%ss/%s/items/%s/move?after=%s" % \
              (playlist.kind,
               playlist.ID,
               playlist.items[before_pos].ID,
               playlist.items[after_pos - 1].ID)
    xml = DU().downloadUrl(url, action_type="PUT")
    # We need to increment the playlistVersion
    _get_playListVersion_from_xml(playlist, xml)
    # Move our item's position in our internal playlist
    playlist.items.insert(after_pos, playlist.items.pop(before_pos))


def delete_playlist_item(playlist, pos):
    """
    Delete the item at position pos [int]
    """
    xml = DU().downloadUrl("{server}/%ss/%s/items/%s?repeat=%s" %
                           (playlist.kind,
                            playlist.ID,
                            playlist.items[pos].ID,
                            playlist.repeat),
                           action_type="DELETE")
    _get_playListVersion_from_xml(playlist, xml)
    del playlist.items[pos]


def get_kodi_playlist_items(playlist):
    """
    Returns a list of the current Kodi playlist items using JSON

    E.g.:
    [{u'title': u'3 Idiots', u'type': u'movie', u'id': 3, u'file':
    u'smb://nas/PlexMovies/3 Idiots 2009 pt1.mkv', u'label': u'3 Idiots'}]
    """
    answ = JSONRPC('Playlist.GetItems').execute({
        'playlistid': playlist.playlistid,
        'properties': ["title", "file"]
    })
    try:
        answ = answ['result']['items']
    except KeyError:
        answ = []
    return answ


def get_kodi_playqueues():
    """
    Example return: [{u'playlistid': 0, u'type': u'audio'},
                     {u'playlistid': 1, u'type': u'video'},
                     {u'playlistid': 2, u'type': u'picture'}]
    """
    queues = JSONRPC('Playlist.GetPlaylists').execute()
    try:
        queues = queues['result']
    except KeyError:
        raise KeyError('Could not get Kodi playqueues. JSON Result was: %s'
                       % queues)
    return queues


# Functions operating on the Kodi playlist objects ##########

def insertintoPlaylist(self,
                       position,
                       dbid=None,
                       mediatype=None,
                       url=None):
    params = {
        'playlistid': self.playlistId,
        'position': position
    }
    if dbid is not None:
        params['item'] = {'%sid' % tryEncode(mediatype): int(dbid)}
    else:
        params['item'] = {'file': url}
    JSONRPC('Playlist.Insert').execute(params)


def addtoPlaylist(self, dbid=None, mediatype=None, url=None):
    params = {
        'playlistid': self.playlistId
    }
    if dbid is not None:
        params['item'] = {'%sid' % tryEncode(mediatype): int(dbid)}
    else:
        params['item'] = {'file': url}
    JSONRPC('Playlist.Add').execute(params)


def removefromPlaylist(self, position):
    params = {
        'playlistid': self.playlistId,
        'position': position
    }
    JSONRPC('Playlist.Remove').execute(params)


def playAll(self, items, startitem, offset):
    """
    items: list of dicts of the form
    {
        'playQueueItemID':      Plex playQueueItemID, e.g. '29175'
        'plexId':       Plex ratingKey, e.g. '125'
        'kodiId':       Kodi's db id of the same item
    }

    startitem:  tuple (typus, id), where typus is either
                'playQueueItemID' or 'plexId' and id is the corresponding
                id as a string
    offset:     First item's time offset to play in Kodi time (an int)
    """
    log.info("---*** PLAY ALL ***---")
    log.debug('Startitem: %s, offset: %s, items: %s'
              % (startitem, offset, items))
    self.items = items
    if self.playlist is None:
        self._initiatePlaylist()
    if self.playlist is None:
        log.error('Could not create playlist, abort')
        return

    window('plex_customplaylist', value="true")
    if offset != 0:
        # Seek to the starting position
        window('plex_customplaylist.seektime', str(offset))
    self._processItems(startitem, startPlayer=True)
    # Log playlist
    self._verifyPlaylist()
    log.debug('Internal playlist: %s' % self.items)


def _processItems(self, startitem, startPlayer=False):
    startpos = None
    with embydb.GetEmbyDB() as emby_db:
        for pos, item in enumerate(self.items):
            kodiId = None
            plexId = item['plexId']
            embydb_item = emby_db.getItem_byId(plexId)
            try:
                kodiId = embydb_item[0]
                mediatype = embydb_item[4]
            except TypeError:
                log.info('Couldnt find item %s in Kodi db' % plexId)
                xml = PF.GetPlexMetadata(plexId)
                if xml in (None, 401):
                    log.error('Could not download plexId %s' % plexId)
                else:
                    log.debug('Downloaded xml metadata, adding now')
                    self._addtoPlaylist_xbmc(xml[0])
            else:
                # Add to playlist
                log.debug("Adding %s PlexId %s, KodiId %s to playlist."
                          % (mediatype, plexId, kodiId))
                self._addtoPlaylist(kodiId, mediatype)
            # Add the kodiId
            if kodiId is not None:
                item['kodiId'] = str(kodiId)
            if (startpos is None and startitem[1] == item[startitem[0]]):
                startpos = pos

    if startPlayer is True and len(self.playlist) > 0:
        if startpos is not None:
            self.player.play(self.playlist, startpos=startpos)
        else:
            log.info('Never received a starting item for playlist, '
                     'starting with the first entry')
            self.player.play(self.playlist)

def _addtoPlaylist_xbmc(self, item):
    API = PlexAPI.API(item)
    params = {
        'mode': "play",
        'dbid': 'plextrailer',
        'id': API.getRatingKey(),
        'filename': API.getKey()
    }
    playurl = "plugin://plugin.video.plexkodiconnect.movies/?%s" \
        % urlencode(params)

    listitem = API.CreateListItemFromPlexItem()
    playbackutils.PlaybackUtils(item).setArtwork(listitem)

    self.playlist.add(playurl, listitem)


def clear(self):
    """
    Empties current Kodi playlist and associated variables
    """
    self.playlist.clear()
    self.items = []
    self.queueId = None
    self.playQueueVersion = None
    self.guid = None
    log.info('Playlist cleared')
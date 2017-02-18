# -*- coding: utf-8 -*-

###############################################################################

import logging
from urllib import urlencode
from threading import Thread

from xbmc import getCondVisibility, Player
import xbmcgui

import playutils as putils
from utils import window, settings, tryEncode, tryDecode, language as lang
import downloadutils

from PlexAPI import API
from PlexFunctions import init_plex_playqueue
from PKC_listitem import PKC_ListItem as ListItem, convert_PKC_to_listitem
from playlist_func import add_item_to_kodi_playlist, \
    get_playlist_details_from_xml, add_listitem_to_Kodi_playlist, \
    add_listitem_to_playlist, remove_from_Kodi_playlist
from pickler import Playback_Successful
from plexdb_functions import Get_Plex_DB
import variables as v

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class PlaybackUtils():

    def __init__(self, xml, playqueue):
        self.xml = xml
        self.playqueue = playqueue

    def play(self, plex_id, kodi_id=None, plex_lib_UUID=None):
        """
        plex_lib_UUID: xml attribute 'librarySectionUUID', needed for posting
        to the PMS
        """
        log.info("Playbackutils called")
        item = self.xml[0]
        api = API(item)
        playqueue = self.playqueue
        xml = None
        result = Playback_Successful()
        listitem = ListItem()
        playutils = putils.PlayUtils(item)
        playurl = playutils.getPlayUrl()
        if not playurl:
            log.error('No playurl found, aborting')
            return

        if kodi_id in (None, 'plextrailer', 'plexnode'):
            # Item is not in Kodi database, is a trailer/clip or plex redirect
            # e.g. plex.tv watch later
            api.CreateListItemFromPlexItem(listitem)
            api.set_listitem_artwork(listitem)
            if kodi_id == 'plexnode':
                # Need to get yet another xml to get final url
                window('plex_%s.playmethod' % playurl, clear=True)
                xml = downloadutils.DownloadUtils().downloadUrl(
                    '{server}%s' % item[0][0].attrib.get('key'))
                try:
                    xml[0].attrib
                except (TypeError, AttributeError):
                    log.error('Could not download %s'
                              % item[0][0].attrib.get('key'))
                    return
                playurl = tryEncode(xml[0].attrib.get('key'))
                window('plex_%s.playmethod' % playurl, value='DirectStream')

            playmethod = window('plex_%s.playmethod' % playurl)
            if playmethod == "Transcode":
                window('plex_%s.playmethod' % playurl, clear=True)
                playurl = tryEncode(playutils.audioSubsPref(
                    listitem, tryDecode(playurl)))
                window('plex_%s.playmethod' % playurl, "Transcode")
            listitem.setPath(playurl)
            api.set_playback_win_props(playurl, listitem)
            result.listitem = listitem
            return result

        kodi_type = v.KODITYPE_FROM_PLEXTYPE[api.getType()]
        kodi_id = int(kodi_id)

        # ORGANIZE CURRENT PLAYLIST ################
        contextmenu_play = window('plex_contextplay') == 'true'
        window('plex_contextplay', clear=True)
        homeScreen = getCondVisibility('Window.IsActive(home)')
        sizePlaylist = len(playqueue.items)
        if contextmenu_play:
            # Need to start with the items we're inserting here
            startPos = sizePlaylist
        else:
            # Can return -1
            startPos = max(playqueue.kodi_pl.getposition(), 0)
        self.currentPosition = startPos

        propertiesPlayback = window('plex_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        log.info("Playing from contextmenu: %s" % contextmenu_play)
        log.info("Playlist start position: %s" % startPos)
        log.info("Playlist plugin position: %s" % self.currentPosition)
        log.info("Playlist size: %s" % sizePlaylist)

        # RESUME POINT ################
        seektime, runtime = api.getRuntime()
        if window('plex_customplaylist.seektime'):
            # Already got seektime, e.g. from playqueue & Plex companion
            seektime = int(window('plex_customplaylist.seektime'))

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:
            window('plex_playbackProps', value="true")
            log.info("Setting up properties in playlist.")
            # Where will the player need to start?
            # Do we need to get trailers?
            trailers = False
            if (api.getType() == v.PLEX_TYPE_MOVIE and
                    not seektime and
                    sizePlaylist < 2 and
                    settings('enableCinema') == "true"):
                if settings('askCinema') == "true":
                    trailers = xbmcgui.Dialog().yesno(
                        lang(29999),
                        "Play trailers?")
                else:
                    trailers = True
            # Post to the PMS. REUSE THE PLAYQUEUE!
            xml = init_plex_playqueue(plex_id,
                                      plex_lib_UUID,
                                      mediatype=api.getType(),
                                      trailers=trailers)
            get_playlist_details_from_xml(playqueue, xml=xml)

            if (not homeScreen and not seektime and sizePlaylist < 2 and
                    window('plex_customplaylist') != "true" and
                    not contextmenu_play):
                # Need to add a dummy file because the first item will fail
                log.debug("Adding dummy file to playlist.")
                dummyPlaylist = True
                add_listitem_to_Kodi_playlist(
                    playqueue,
                    startPos,
                    xbmcgui.ListItem(),
                    playurl,
                    xml[0])
                # Remove the original item from playlist
                remove_from_Kodi_playlist(
                    playqueue,
                    startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have
                # full metadata
                add_item_to_kodi_playlist(
                    playqueue,
                    self.currentPosition+1,
                    kodi_id=kodi_id,
                    kodi_type=kodi_type,
                    file=playurl)
                self.currentPosition += 1

            # -- ADD TRAILERS ################
            if trailers:
                for i, item in enumerate(xml):
                    if i == len(xml) - 1:
                        # Don't add the main movie itself
                        break
                    self.add_trailer(item)
                    introsPlaylist = True

            # -- ADD MAIN ITEM ONLY FOR HOMESCREEN ##############
            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                log.info("Adding main item to playlist.")
                add_item_to_kodi_playlist(
                    playqueue,
                    self.currentPosition,
                    kodi_id,
                    kodi_type)

            elif contextmenu_play:
                if window('useDirectPaths') == 'true':
                    # Cannot add via JSON with full metadata because then we
                    # Would be using the direct path
                    log.debug("Adding contextmenu item for direct paths")
                    if window('plex_%s.playmethod' % playurl) == "Transcode":
                        window('plex_%s.playmethod' % playurl,
                               clear=True)
                        playurl = tryEncode(playutils.audioSubsPref(
                            listitem, tryDecode(playurl)))
                        window('plex_%s.playmethod' % playurl,
                               value="Transcode")
                    api.CreateListItemFromPlexItem(listitem)
                    api.set_playback_win_props(playurl, listitem)
                    api.set_listitem_artwork(listitem)
                    add_listitem_to_Kodi_playlist(
                        playqueue,
                        self.currentPosition+1,
                        convert_PKC_to_listitem(listitem),
                        playurl,
                        kodi_item={'id': kodi_id, 'type': kodi_type})
                else:
                    # Full metadata$
                    add_item_to_kodi_playlist(
                        playqueue,
                        self.currentPosition+1,
                        kodi_id,
                        kodi_type)
                self.currentPosition += 1
                if seektime:
                    window('plex_customplaylist.seektime', value=str(seektime))

            # Ensure that additional parts are played after the main item
            self.currentPosition += 1

            # -- CHECK FOR ADDITIONAL PARTS ################
            if len(item[0]) > 1:
                self.add_part(item, api, kodi_id, kodi_type)

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                log.info("Processed as a playlist. First item is skipped.")
                # Delete the item that's gonna fail!
                del playqueue.items[startPos]
                # Don't attach listitem
                return result

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            log.debug("Resetting properties playback flag.")
            window('plex_playbackProps', clear=True)

        # SETUP MAIN ITEM ##########
        # For transcoding only, ask for audio/subs pref
        if (window('plex_%s.playmethod' % playurl) == "Transcode" and
                not contextmenu_play):
            window('plex_%s.playmethod' % playurl, clear=True)
            playurl = tryEncode(playutils.audioSubsPref(
                listitem, tryDecode(playurl)))
            window('plex_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        api.set_playback_win_props(playurl, listitem)
        api.set_listitem_artwork(listitem)

        # PLAYBACK ################
        if (homeScreen and seektime and window('plex_customplaylist') != "true"
                and not contextmenu_play):
            log.info("Play as a widget item")
            api.CreateListItemFromPlexItem(listitem)
            result.listitem = listitem
            return result

        elif ((introsPlaylist and window('plex_customplaylist') == "true") or
                (homeScreen and not sizePlaylist) or
                contextmenu_play):
            # Playlist was created just now, play it.
            # Contextmenu plays always need this
            log.info("Play playlist from starting position %s" % startPos)
            # Need a separate thread because Player won't return in time
            thread = Thread(target=Player().play,
                            args=(playqueue.kodi_pl, None, False, startPos))
            thread.setDaemon(True)
            thread.start()
            # Don't attach listitem
            return result
        else:
            log.info("Play as a regular item")
            result.listitem = listitem
            return result

    def play_all(self):
        """
        Play all items contained in the xml passed in. Called by Plex Companion
        """
        log.info("Playbackutils play_all called")
        window('plex_playbackProps', value="true")
        self.currentPosition = 0
        for item in self.xml:
            api = API(item)
            if api.getType() == v.PLEX_TYPE_CLIP:
                self.add_trailer(item)
            else:
                with Get_Plex_DB() as plex_db:
                    db_item = plex_db.getItem_byId(api.getRatingKey())
                if db_item is not None:
                    if add_item_to_kodi_playlist(self.playqueue,
                                                 self.currentPosition,
                                                 kodi_id=db_item[0],
                                                 kodi_type=db_item[4]) is True:
                        self.currentPosition += 1
                        if len(item[0]) > 1:
                            self.add_part(item,
                                          api,
                                          db_item[0],
                                          db_item[4])
                else:
                    # Item not in Kodi DB
                    self.add_trailer(item)
            self.playqueue.items[self.currentPosition - 1].ID = item.get(
                '%sItemID' % self.playqueue.kind)

    def add_trailer(self, item):
        # Playurl needs to point back so we can get metadata!
        path = "plugin://plugin.video.plexkodiconnect/movies/"
        params = {
            'mode': "play",
            'dbid': 'plextrailer'
        }
        introAPI = API(item)
        listitem = introAPI.CreateListItemFromPlexItem()
        params['id'] = introAPI.getRatingKey()
        params['filename'] = introAPI.getKey()
        introPlayurl = path + '?' + urlencode(params)
        introAPI.set_listitem_artwork(listitem)
        # Overwrite the Plex url
        listitem.setPath(introPlayurl)
        log.info("Adding Plex trailer: %s" % introPlayurl)
        add_listitem_to_Kodi_playlist(
            self.playqueue,
            self.currentPosition,
            listitem,
            introPlayurl,
            xml_video_element=item)
        self.currentPosition += 1

    def add_part(self, item, api, kodi_id, kodi_type):
        """
        Adds an additional part to the playlist
        """
        # Only add to the playlist after intros have played
        for counter, part in enumerate(item[0]):
            # Never add first part
            if counter == 0:
                continue
            # Set listitem and properties for each additional parts
            api.setPartNumber(counter)
            additionalListItem = xbmcgui.ListItem()
            playutils = putils.PlayUtils(item)
            additionalPlayurl = playutils.getPlayUrl(
                partNumber=counter)
            log.debug("Adding additional part: %s, url: %s"
                      % (counter, additionalPlayurl))
            api.CreateListItemFromPlexItem(additionalListItem)
            api.set_playback_win_props(additionalPlayurl,
                                       additionalListItem)
            api.set_listitem_artwork(additionalListItem)
            add_listitem_to_playlist(
                self.playqueue,
                self.currentPosition,
                additionalListItem,
                kodi_id=kodi_id,
                kodi_type=kodi_type,
                plex_id=api.getRatingKey(),
                file=additionalPlayurl)
            self.currentPosition += 1
        api.setPartNumber(0)

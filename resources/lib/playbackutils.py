# -*- coding: utf-8 -*-

###############################################################################

import logging
from urllib import urlencode
from threading import Thread

from xbmc import getCondVisibility, Player
import xbmcgui

import playutils as putils
from utils import window, settings, tryEncode, tryDecode
import downloadutils

from PlexAPI import API
from PlexFunctions import GetPlexPlaylist, KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE, \
    KODITYPE_FROM_PLEXTYPE
from PKC_listitem import PKC_ListItem as ListItem
from playlist_func import add_item_to_kodi_playlist, \
    get_playlist_details_from_xml, add_listitem_to_Kodi_playlist, \
    add_listitem_to_playlist, remove_from_Kodi_playlist
from playqueue import lock, Playqueue
from pickler import Playback_Successful

###############################################################################

log = logging.getLogger("PLEX."+__name__)

addonName = "PlexKodiConnect"

###############################################################################


class PlaybackUtils():

    def __init__(self, item, callback=None, playlist_type=None):
        self.item = item
        self.api = API(item)
        playlist_type = playlist_type if playlist_type else KODI_PLAYLIST_TYPE_FROM_PLEX_TYPE[self.api.getType()]
        if callback:
            self.mgr = callback
            self.playqueue = self.mgr.playqueue.get_playqueue_from_type(
                playlist_type)
        else:
            self.playqueue = Playqueue().get_playqueue_from_type(playlist_type)

    def play(self, plex_id, kodi_id=None, plex_lib_UUID=None):
        """
        plex_lib_UUID: xml attribute 'librarySectionUUID', needed for posting
        to the PMS
        """
        log.info("Playbackutils called")
        item = self.item
        api = self.api
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
            self.setArtwork(listitem)
            if kodi_id == 'plexnode':
                # Need to get yet another xml to get final url
                window('emby_%s.playmethod' % playurl, clear=True)
                xml = downloadutils.DownloadUtils().downloadUrl(
                    '{server}%s' % item[0][0].attrib.get('key'))
                try:
                    xml[0].attrib
                except (TypeError, AttributeError):
                    log.error('Could not download %s'
                              % item[0][0].attrib.get('key'))
                    return
                playurl = tryEncode(xml[0].attrib.get('key'))
                window('emby_%s.playmethod' % playurl, value='DirectStream')

            playmethod = window('emby_%s.playmethod' % playurl)
            if playmethod == "Transcode":
                window('emby_%s.playmethod' % playurl, clear=True)
                playurl = tryEncode(playutils.audioSubsPref(
                    listitem, tryDecode(playurl)))
                window('emby_%s.playmethod' % playurl, "Transcode")
            listitem.setPath(playurl)
            self.setProperties(playurl, listitem)
            result.listitem = listitem
            return result

        kodi_type = KODITYPE_FROM_PLEXTYPE[api.getType()]
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
            if (api.getType() == 'movie' and not seektime and sizePlaylist < 2
                    and settings('enableCinema') == "true"):
                if settings('askCinema') == "true":
                    trailers = xbmcgui.Dialog().yesno(
                        addonName,
                        "Play trailers?")
                else:
                    trailers = True
            # Post to the PMS. REUSE THE PLAYQUEUE!
            xml = GetPlexPlaylist(
                plex_id,
                plex_lib_UUID,
                mediatype=api.getType(),
                trailers=trailers)
            log.debug('xml: ID: %s' % xml.attrib['playQueueID'])
            get_playlist_details_from_xml(playqueue, xml=xml)
            log.debug('finished ')

            if (not homeScreen and not seektime and
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
                introsPlaylist = self.AddTrailers(xml)

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
                    if window('emby_%s.playmethod' % playurl) == "Transcode":
                        window('emby_%s.playmethod' % playurl,
                               clear=True)
                        playurl = tryEncode(playutils.audioSubsPref(
                            listitem, tryDecode(playurl)))
                        window('emby_%s.playmethod' % playurl,
                               value="Transcode")
                    api.CreateListItemFromPlexItem(listitem)
                    self.setProperties(playurl, listitem)
                    self.setArtwork(listitem)
                    kodiPl.add(playurl, listitem, index=self.currentPosition+1)
                else:
                    # Full metadata
                    self.pl.insertintoPlaylist(
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
                # Only add to the playlist after intros have played
                for counter, part in enumerate(item[0]):
                    # Never add first part
                    if counter == 0:
                        continue
                    # Set listitem and properties for each additional parts
                    api.setPartNumber(counter)
                    additionalListItem = xbmcgui.ListItem()
                    additionalPlayurl = playutils.getPlayUrl(
                        partNumber=counter)
                    log.debug("Adding additional part: %s, url: %s"
                              % (counter, additionalPlayurl))
                    api.CreateListItemFromPlexItem(additionalListItem)
                    self.setProperties(additionalPlayurl, additionalListItem)
                    self.setArtwork(additionalListItem)
                    add_listitem_to_playlist(
                        playqueue,
                        self.currentPosition,
                        additionalListItem,
                        kodi_id=kodi_id,
                        kodi_type=kodi_type,
                        plex_id=plex_id,
                        file=additionalPlayurl)
                    self.currentPosition += 1
                api.setPartNumber(0)

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                log.info("Processed as a playlist. First item is skipped.")
                # Delete the item that's gonna fail!
                with lock:
                    del playqueue.items[startPos]
                # Don't attach listitem
                return result

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            log.debug("Resetting properties playback flag.")
            window('plex_playbackProps', clear=True)

        # SETUP MAIN ITEM ##########
        # For transcoding only, ask for audio/subs pref
        if (window('emby_%s.playmethod' % playurl) == "Transcode" and
                not contextmenu_play):
            window('emby_%s.playmethod' % playurl, clear=True)
            playurl = tryEncode(playutils.audioSubsPref(
                listitem, tryDecode(playurl)))
            window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

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
            log.info("Play playlist")
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

    def AddTrailers(self, xml):
        """
        Adds trailers to a movie, if applicable. Returns True if trailers were
        added
        """
        # Failure when getting trailers, e.g. when no plex pass
        if xml.attrib.get('size') == '1':
            return False
        # Playurl needs to point back so we can get metadata!
        path = "plugin://plugin.video.plexkodiconnect/movies/"
        params = {
            'mode': "play",
            'dbid': 'plextrailer'
        }
        for counter, intro in enumerate(xml):
            # Don't process the last item - it's the original movie
            if counter == len(xml)-1:
                break
            introAPI = API(intro)
            listitem = introAPI.CreateListItemFromPlexItem()
            params['id'] = introAPI.getRatingKey()
            params['filename'] = introAPI.getKey()
            introPlayurl = path + '?' + urlencode(params)
            self.setArtwork(listitem, introAPI)
            # Overwrite the Plex url
            listitem.setPath(introPlayurl)
            log.info("Adding Intro: %s" % introPlayurl)
            add_listitem_to_Kodi_playlist(
                self.playqueue,
                self.currentPosition,
                listitem,
                introPlayurl,
                intro)
            self.currentPosition += 1
        return True

    def setProperties(self, playurl, listitem):
        # Set all properties necessary for plugin path playback
        itemid = self.api.getRatingKey()
        itemtype = self.api.getType()
        userdata = self.api.getUserData()

        embyitem = "emby_%s" % playurl
        window('%s.runtime' % embyitem, value=str(userdata['Runtime']))
        window('%s.type' % embyitem, value=itemtype)
        window('%s.itemid' % embyitem, value=itemid)
        window('%s.playcount' % embyitem, value=str(userdata['PlayCount']))

        if itemtype == "episode":
            window('%s.refreshid' % embyitem,
                   value=self.api.getParentRatingKey())
        else:
            window('%s.refreshid' % embyitem, value=itemid)

        # Append external subtitles to stream
        playmethod = window('%s.playmethod' % embyitem)
        if playmethod in ("DirectStream", "DirectPlay"):
            subtitles = self.api.externalSubs(playurl)
            listitem.setSubtitles(subtitles)

        self.setArtwork(listitem)

    def setArtwork(self, listItem, api=None):
        if api is None:
            api = self.api
        allartwork = api.getAllArtwork(parentInfo=True)
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
                    self.setArtProp(listItem, arttype, allartwork[art][0])
                except:
                    pass
            else:
                self.setArtProp(listItem, arttype, allartwork[art])

    def setArtProp(self, listItem, arttype, path):
        if arttype in (
                'thumb', 'fanart_image', 'small_poster', 'tiny_poster',
                'medium_landscape', 'medium_poster', 'small_fanartimage',
                'medium_fanartimage', 'fanart_noindicators'):
            listItem.setProperty(arttype, path)
        else:
            listItem.setArt({arttype: path})

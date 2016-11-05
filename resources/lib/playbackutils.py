# -*- coding: utf-8 -*-

###############################################################################

import logging
import json
import sys
from urllib import urlencode

import xbmc
import xbmcgui
import xbmcplugin

import playutils as putils
import playlist
from utils import window, settings, tryEncode, tryDecode
import downloadutils

import PlexAPI
import PlexFunctions as PF

###############################################################################

log = logging.getLogger("PLEX."+__name__)

addonName = "PlexKodiConnect"

###############################################################################


class PlaybackUtils():

    def __init__(self, item):

        self.item = item
        self.API = PlexAPI.API(item)

        self.userid = window('currUserId')
        self.server = window('pms_server')

        if self.API.getType() == 'track':
            self.pl = playlist.Playlist(typus='music')
        else:
            self.pl = playlist.Playlist(typus='video')

    def play(self, itemid, dbid=None):

        item = self.item
        # Hack to get only existing entry in PMS response for THIS instance of
        # playbackutils :-)
        self.API = PlexAPI.API(item[0])
        API = self.API
        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(item[0])

        log.info("Play called.")
        playurl = playutils.getPlayUrl()
        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if dbid in (None, '999999999', 'plexnode'):
            # Item is not in Kodi database, is a trailer or plex redirect
            # e.g. plex.tv watch later
            API.CreateListItemFromPlexItem(listitem)
            self.setArtwork(listitem)
            if dbid == 'plexnode':
                # Need to get yet another xml to get final url
                window('emby_%s.playmethod' % playurl, clear=True)
                xml = downloadutils.DownloadUtils().downloadUrl(
                    '{server}%s' % item[0][0][0].attrib.get('key'))
                if xml in (None, 401):
                    log.error('Could not download %s'
                              % item[0][0][0].attrib.get('key'))
                    return xbmcplugin.setResolvedUrl(
                        int(sys.argv[1]), False, listitem)
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
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        ############### ORGANIZE CURRENT PLAYLIST ################
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        kodiPl = self.pl.playlist
        # Can return -1
        startPos = max(kodiPl.getposition(), 0)
        sizePlaylist = kodiPl.size()
        self.currentPosition = startPos

        propertiesPlayback = window('plex_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        log.info("Playlist start position: %s" % startPos)
        log.info("Playlist plugin position: %s" % self.currentPosition)
        log.info("Playlist size: %s" % sizePlaylist)

        ############### RESUME POINT ################
        seektime, runtime = API.getRuntime()

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            window('plex_playbackProps', value="true")
            log.info("Setting up properties in playlist.")

            if (not homeScreen and not seektime and
                    window('plex_customplaylist') != "true"):
                log.debug("Adding dummy file to playlist.")
                dummyPlaylist = True
                kodiPl.add(playurl, listitem, index=startPos)
                # Remove the original item from playlist 
                self.pl.removefromPlaylist(startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have full metadata
                self.pl.insertintoPlaylist(
                    self.currentPosition+1,
                    dbid,
                    PF.GetKodiTypeFromPlex(API.getType()))
                self.currentPosition += 1

            ############### -- CHECK FOR INTROS ################
            if (settings('enableCinema') == "true" and not seektime):
                # if we have any play them when the movie/show is not being resumed
                xml = PF.GetPlexPlaylist(
                    itemid,
                    item.attrib.get('librarySectionUUID'),
                    mediatype=API.getType())
                introsPlaylist = self.AddTrailers(xml)

            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ##############

            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                log.info("Adding main item to playlist.")
                self.pl.addtoPlaylist(
                    dbid,
                    PF.GetKodiTypeFromPlex(API.getType()))

            # Ensure that additional parts are played after the main item
            self.currentPosition += 1

            ############### -- CHECK FOR ADDITIONAL PARTS ################
            if len(item[0][0]) > 1:
                # Only add to the playlist after intros have played
                for counter, part in enumerate(item[0][0]):
                    # Never add first part
                    if counter == 0:
                        continue
                    # Set listitem and properties for each additional parts
                    API.setPartNumber(counter)
                    additionalListItem = xbmcgui.ListItem()
                    additionalPlayurl = playutils.getPlayUrl(
                        partNumber=counter)
                    log.debug("Adding additional part: %s" % counter)

                    self.setProperties(additionalPlayurl, additionalListItem)
                    self.setArtwork(additionalListItem)
                    # NEW to Plex
                    API.CreateListItemFromPlexItem(additionalListItem)

                    kodiPl.add(additionalPlayurl, additionalListItem,
                               index=self.currentPosition)
                    self.pl.verifyPlaylist()
                    self.currentPosition += 1
                API.setPartNumber = 0

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                log.info("Processed as a playlist. First item is skipped.")
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            log.debug("Resetting properties playback flag.")
            window('plex_playbackProps', clear=True)

        #self.pl.verifyPlaylist()
        ########## SETUP MAIN ITEM ##########
        # For transcoding only, ask for audio/subs pref
        if window('emby_%s.playmethod' % playurl) == "Transcode":
            window('emby_%s.playmethod' % playurl, clear=True)
            playurl = tryEncode(playutils.audioSubsPref(
                listitem, tryDecode(playurl)))
            window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

        ############### PLAYBACK ################
        if homeScreen and seektime and window('plex_customplaylist') != "true":
            log.info("Play as a widget item.")
            API.CreateListItemFromPlexItem(listitem)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        elif ((introsPlaylist and window('plex_customplaylist') == "true") or
                (homeScreen and not sizePlaylist)):
            # Playlist was created just now, play it.
            log.info("Play playlist.")
            xbmcplugin.endOfDirectory(int(sys.argv[1]), True, False, False)
            xbmc.Player().play(kodiPl, startpos=startPos)

        else:
            log.info("Play as a regular item.")
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def AddTrailers(self, xml):
        """
        Adds trailers to a movie, if applicable. Returns True if trailers were
        added
        """
        # Failure when downloading trailer playQueue
        if xml in (None, 401):
            return False
        # Failure when getting trailers, e.g. when no plex pass
        if xml.attrib.get('size') == '1':
            return False

        if settings('askCinema') == "true":
            resp = xbmcgui.Dialog().yesno(addonName, "Play trailers?")
            if not resp:
                # User selected to not play trailers
                log.info("Skip trailers.")
                return False

        # Playurl needs to point back so we can get metadata!
        path = "plugin://plugin.video.plexkodiconnect.movies/"
        params = {
            'mode': "play",
            'dbid': 999999999
        }
        for counter, intro in enumerate(xml):
            # Don't process the last item - it's the original movie
            if counter == len(xml)-1:
                break
            # The server randomly returns intros, process them.
            # introListItem = xbmcgui.ListItem()
            # introPlayurl = putils.PlayUtils(intro).getPlayUrl()
            introAPI = PlexAPI.API(intro)
            params['id'] = introAPI.getRatingKey()
            params['filename'] = introAPI.getKey()
            introPlayurl = path + '?' + urlencode(params)
            log.info("Adding Intro: %s" % introPlayurl)

            self.pl.insertintoPlaylist(self.currentPosition, url=introPlayurl)
            self.currentPosition += 1

        return True

    def setProperties(self, playurl, listitem):
        # Set all properties necessary for plugin path playback
        itemid = self.API.getRatingKey()
        itemtype = self.API.getType()
        userdata = self.API.getUserData()

        embyitem = "emby_%s" % playurl
        window('%s.runtime' % embyitem, value=str(userdata['Runtime']))
        window('%s.type' % embyitem, value=itemtype)
        window('%s.itemid' % embyitem, value=itemid)
        window('%s.playcount' % embyitem, value=str(userdata['PlayCount']))

        if itemtype == "episode":
            window('%s.refreshid' % embyitem,
                   value=self.API.getParentRatingKey())
        else:
            window('%s.refreshid' % embyitem, value=itemid)

        # Append external subtitles to stream
        subtitles = self.API.externalSubs(playurl)
        listitem.setSubtitles(subtitles)

        self.setArtwork(listitem)

    def externalSubs(self, playurl):
        externalsubs = []
        mapping = {}

        itemid = self.API.getRatingKey()
        mediastreams = self.API.getMediaStreams()

        kodiindex = 0
        for stream in mediastreams:

            index = stream['Index']
            # Since Emby returns all possible tracks together, have to pull
            # only external subtitles. IsTextSubtitleStream if true, is
            # available to download from emby.
            if (stream['Type'] == "Subtitle" and
                    stream['IsExternal'] and stream['IsTextSubtitleStream']):
                # Direct stream
                url = ("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                       % (self.server, itemid, itemid, index))
                # map external subtitles for mapping
                mapping[kodiindex] = index
                externalsubs.append(url)
                kodiindex += 1
        mapping = json.dumps(mapping)
        window('emby_%s.indexMapping' % playurl, value=mapping)
        return externalsubs

    def setArtwork(self, listItem):
        allartwork = self.API.getAllArtwork(parentInfo=True)
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

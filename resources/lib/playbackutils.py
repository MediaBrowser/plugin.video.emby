# -*- coding: utf-8 -*-

#################################################################################################

import json
import sys
from urllib import urlencode

import xbmc
import xbmcgui
import xbmcplugin

import artwork
import clientinfo
import playutils as putils
import playlist
import read_embyserver as embyserver
import utils

import PlexAPI
import PlexFunctions as PF

#################################################################################################


@utils.logging
class PlaybackUtils():

    def __init__(self, item):

        self.item = item
        self.API = PlexAPI.API(item)

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.pl = playlist.Playlist()

    def play(self, itemid, dbid=None):

        log = self.logMsg
        window = utils.window
        settings = utils.settings

        item = self.item
        # Hack to get only existing entry in PMS response for THIS instance of
        # playbackutils :-)
        self.API = PlexAPI.API(item[0])
        API = self.API
        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(item[0])

        log("Play called.", 1)
        playurl = playutils.getPlayUrl()
        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if dbid is None or dbid == '999999999':
            # Item is not in Kodi database
            playmethod = window('emby_%s.playmethod' % playurl)
            if playmethod == "Transcode":
                window('emby_%s.playmethod' % playurl, clear=True)
                playurl = playutils.audioSubsPref(
                    listitem, playurl)
                window('emby_%s.playmethod' % playurl, "Transcode")
            listitem.setPath(playurl)
            self.setArtwork(listitem)
            self.setListItem(listitem)
            self.setProperties(playurl, listitem)
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        ############### ORGANIZE CURRENT PLAYLIST ################
        
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()
        self.currentPosition = startPos

        propertiesPlayback = window('emby_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        log("Playlist start position: %s" % startPos, 1)
        log("Playlist plugin position: %s" % self.currentPosition, 1)
        log("Playlist size: %s" % sizePlaylist, 1)

        ############### RESUME POINT ################
        
        seektime, runtime = API.getRuntime()

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            window('emby_playbackProps', value="true")
            log("Setting up properties in playlist.", 1)

            if (not homeScreen and not seektime and
                    window('emby_customPlaylist') != "true"):
                log("Adding dummy file to playlist.", 2)
                dummyPlaylist = True
                playlist.add(playurl, listitem, index=startPos)
                # Remove the original item from playlist 
                self.pl.removefromPlaylist(startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have full metadata
                self.pl.insertintoPlaylist(
                    self.currentPosition+1,
                    dbid,
                    PF.GetKodiTypeFromPlex(API.getType()))
                self.currentPosition += 1
            
            ############### -- CHECK FOR INTROS ################

            if (settings('enableCinema') == "true" and not seektime and
                    not window('emby_customPlaylist') == "true"):
                # if we have any play them when the movie/show is not being resumed
                xml = PF.GetPlexPlaylist(
                    itemid,
                    item.attrib.get('librarySectionUUID'),
                    mediatype=API.getType())
                introsPlaylist = self.AddTrailers(xml)

            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ###############

            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                log("Adding main item to playlist.", 1)
                self.pl.addtoPlaylist(
                    dbid,
                    PF.GetKodiTypeFromPlex(API.getType()))

            # Ensure that additional parts are played after the main item
            self.currentPosition += 1

            ############### -- CHECK FOR ADDITIONAL PARTS ################
            
            if len(item[0][0]) > 1:
                # Only add to the playlist after intros have played
                for counter, part in enumerate(item[0][0]):
                    # Playlist items don't fail on their first call - skip them
                    # here, otherwise we'll get two 1st parts
                    if (counter == 0 and
                            window('emby_customPlaylist') == "true"):
                        continue
                    # Set listitem and properties for each additional parts
                    API.setPartNumber(counter)
                    additionalListItem = xbmcgui.ListItem()
                    additionalPlayurl = playutils.getPlayUrl(
                        partNumber=counter)
                    log("Adding additional part: %s" % counter, 1)

                    self.setProperties(additionalPlayurl, additionalListItem)
                    self.setArtwork(additionalListItem)
                    # NEW to Plex
                    self.setListItem(additionalListItem)

                    playlist.add(additionalPlayurl, additionalListItem, index=self.currentPosition)
                    self.pl.verifyPlaylist()
                    self.currentPosition += 1
                API.setPartNumber = 0

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                log("Processed as a playlist. First item is skipped.", 1)
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)
                

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            log("Resetting properties playback flag.", 2)
            window('emby_playbackProps', clear=True)

        #self.pl.verifyPlaylist()
        ########## SETUP MAIN ITEM ##########

        # For transcoding only, ask for audio/subs pref
        if window('emby_%s.playmethod' % playurl) == "Transcode":
            window('emby_%s.playmethod' % playurl, clear=True)
            playurl = playutils.audioSubsPref(playurl, listitem)
            window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

        ############### PLAYBACK ################

        if homeScreen and seektime and window('emby_customPlaylist') != "true":
            log("Play as a widget item.", 1)
            self.setListItem(listitem)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        elif ((introsPlaylist and window('emby_customPlaylist') == "true") or
                (homeScreen and not sizePlaylist)):
            # Playlist was created just now, play it.
            log("Play playlist.", 1)
            xbmc.Player().play(playlist, startpos=startPos)

        else:
            log("Play as a regular item.", 1)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def AddTrailers(self, xml):
        """
        Adds trailers to a movie, if applicable. Returns True if trailers were
        added
        """
        # Failure when downloading trailer playQueue
        if xml is None:
            return False
        # Failure when getting trailers, e.g. when no plex pass
        if xml.attrib.get('size') == '1':
            return False

        if utils.settings('askCinema') == "true":
            resp = xbmcgui.Dialog().yesno(self.addonName, "Play trailers?")
            if not resp:
                # User selected to not play trailers
                self.logMsg("Skip trailers.", 1)
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
            self.logMsg("Adding Intro: %s" % introPlayurl, 1)

            self.pl.insertintoPlaylist(self.currentPosition, url=introPlayurl)
            self.currentPosition += 1

        return True

    def setProperties(self, playurl, listitem):

        window = utils.window
        # Set all properties necessary for plugin path playback
        itemid = self.API.getRatingKey()
        itemtype = self.API.getType()
        resume, runtime = self.API.getRuntime()

        embyitem = "emby_%s" % playurl
        window('%s.runtime' % embyitem, value=str(runtime))
        window('%s.type' % embyitem, value=itemtype)
        window('%s.itemid' % embyitem, value=itemid)

        # We need to keep track of playQueueItemIDs for Plex Companion
        window('plex_%s.playQueueItemID'
               % playurl, self.API.GetPlayQueueItemID())
        window('plex_%s.guid' % playurl, self.API.getGuid())

        if itemtype == "episode":
            window('%s.refreshid' % embyitem,
                   value=self.API.getParentRatingKey())
        else:
            window('%s.refreshid' % embyitem, value=itemid)

        # Append external subtitles to stream
        playmethod = utils.window('%s.playmethod' % embyitem)
        # Only for direct stream
        if playmethod in ("DirectStream"):
            # Direct play automatically appends external
            subtitles = self.externalSubs(playurl)
            listitem.setSubtitles(subtitles)

        self.setArtwork(listitem)

    def externalSubs(self, playurl):

        externalsubs = []
        mapping = {}

        item = self.item
        itemid = item['Id']
        try:
            mediastreams = item['MediaSources'][0]['MediaStreams']
        except (TypeError, KeyError, IndexError):
            return

        kodiindex = 0
        for stream in mediastreams:

            index = stream['Index']
            # Since Emby returns all possible tracks together, have to pull only external subtitles.
            # IsTextSubtitleStream if true, is available to download from emby.
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
        utils.window('emby_%s.indexMapping' % playurl, value=mapping)

        return externalsubs

    def setArtwork(self, listItem):
        allartwork = self.API.getAllArtwork(parentInfo=True)
        self.logMsg('allartwork: %s' % allartwork, 2)

        # arttypes = {

        #     'poster': "Primary",
        #     'tvshow.poster': "Primary",
        #     'clearart': "Art",
        #     'tvshow.clearart': "Art",
        #     'clearlogo': "Logo",
        #     'tvshow.clearlogo': "Logo",
        #     'discart': "Disc",
        #     'fanart_image': "Backdrop",
        #     'landscape': "Thumb"
        # }
        arttypes = {
            'poster': "Primary",
            'tvshow.poster': "Primary",
            'clearart': "Art",
            'tvshow.clearart': "Art",
            'clearart': "Primary",
            'tvshow.clearart': "Primary",
            'clearlogo': "Logo",
            'tvshow.clearlogo': "Logo",
            'discart': "Disc",
            'fanart_image': "Backdrop",
            'landscape': "Backdrop"
        }
        for arttype in arttypes:

            art = arttypes[arttype]
            if art == "Backdrop":
                try: # Backdrop is a list, grab the first backdrop
                    self.setArtProp(listItem, arttype, allartwork[art][0])
                except: pass
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

    def setListItem(self, listItem):

        API = self.API
        mediaType = API.getType()
        people = API.getPeople()

        userdata = API.getUserData()
        title, sorttitle = API.getTitle()

        metadata = {
            'genre': API.joinList(API.getGenres()),
            'year': API.getYear(),
            'rating': API.getAudienceRating(),
            'playcount': userdata['PlayCount'],
            'cast': people['Cast'],
            'director': API.joinList(people.get('Director')),
            'plot': API.getPlot(),
            'title': title,
            'sorttitle': sorttitle,
            'duration': userdata['Runtime'],
            'studio': API.joinList(API.getStudios()),
            'tagline': API.getTagline(),
            'writer': API.joinList(people.get('Writer')),
            'premiered': API.getPremiereDate(),
            'dateadded': API.getDateCreated(),
            'lastplayed': userdata['LastPlayedDate'],
            'mpaa': API.getMpaa(),
            'aired': API.getPremiereDate()
        }

        if "episode" in mediaType:
            # Only for tv shows
            key, show, season, episode = API.getEpisodeDetails()
            metadata['episode'] = episode
            metadata['season'] = season
            metadata['tvshowtitle'] = show

        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)

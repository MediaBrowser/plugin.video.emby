# -*- coding: utf-8 -*-

#################################################################################################

import json
import sys

import xbmc
import xbmcgui
import xbmcplugin

import artwork
import downloadutils
import playutils as putils
import playlist
import read_embyserver as embyserver
import utils
import embydb_functions

import PlexAPI

#################################################################################################


@utils.logging
class PlaybackUtils():

    def __init__(self, xml):

        self.item = xml

        self.doUtils = downloadutils.DownloadUtils()

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)
        self.machineIdentifier = utils.window('plex_machineIdentifier')

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.pl = playlist.Playlist()

    def StartPlay(self, resume=None, resumeId=None):
        """
        Feed with a PMS playQueue or a single PMS item metadata XML
        Every item will get put in playlist
        """
        self.logMsg("StartPlay called with resume=%s, resumeId=%s"
                    % (resume, resumeId), 1)
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        self.startPos = max(self.playlist.getposition(), 0)  # Can return -1
        self.sizePlaylist = self.playlist.size()
        self.currentPosition = self.startPos
        self.logMsg("Playlist size to start: %s" % self.sizePlaylist, 1)
        self.logMsg("Playlist start position: %s" % self.startPos, 1)
        self.logMsg("Playlist position we're starting with: %s"
                    % self.currentPosition, 1)

        # When do we need to kick off Kodi playback from start?
        # if the startPos is equal than playlist size (otherwise we're asked)
        # to only update an url
        startPlayer = True if self.startPos == self.sizePlaylist else False

        # Run through the passed PMS playlist and construct self.playlist
        listitems = []
        for mediaItem in self.item:
            listitems += self.AddMediaItemToPlaylist(mediaItem)

        # Kick off playback
        if startPlayer:
            Player = xbmc.Player()
            Player.play(self.playlist, startpos=self.startPos)
            if resume:
                try:
                    Player.seekTime(resume)
                except:
                    self.logMsg("Error, could not resume", -1)
        else:
            # Delete the last playlist item because we have added it already
            filename = self.playlist[-1].getfilename()
            self.playlist.remove(filename)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitems[0])

    def AddMediaItemToPlaylist(self, item):
        """
        Feed with ONE media item from PMS xml response
        (on level with e.g. key=/library/metadata/220493 present)

        An item may consist of several parts (e.g. movie in 2 pieces/files)

        Returns a list of tuples: (playlistPosition, listitem)
        """
        self.API = PlexAPI.API(item)
        playutils = putils.PlayUtils(item)

        # Get playurls per part and process them
        listitems = []
        for playurl in playutils.getPlayUrl():
            # One new listitem per part
            listitem = xbmcgui.ListItem()

            # For transcoding only, ask for audio/subs pref
            if utils.window('emby_%s.playmethod' % playurl) == "Transcode":
                playurl = playutils.audioSubsPref(playurl, listitem)
                utils.window('emby_%s.playmethod' % playurl, value="Transcode")

            listitem.setPath(playurl)

            # Set artwork
            self.setProperties(playurl, listitem)
            # Set metadata
            self.setListItem(listitem)
            self.playlist.add(
                playurl, listitem, index=self.currentPosition)

            listitems.append(listitem)
            self.currentPosition += 1

            # We need to keep track of playQueueItemIDs for Plex Companion
            playQueueItemID = self.API.GetPlayQueueItemID()
            utils.window(
                'plex_%s.playQueueItemID' % playurl, playQueueItemID)
            utils.window(
                'plex_%s.playlistPosition'
                % playurl, str(self.currentPosition))

        return listitems

    def play(self, itemid, dbid=None):

        self.logMsg("Play called.", 1)

        doUtils = self.doUtils
        item = self.item
        API = self.API
        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(item)

        playurl = playutils.getPlayUrl()
        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if dbid is None:
            # Item is not in Kodi database
            listitem.setPath(playurl)
            self.setProperties(playurl, listitem)
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        ############### ORGANIZE CURRENT PLAYLIST ################
        
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()
        currentPosition = startPos

        propertiesPlayback = utils.window('emby_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        self.logMsg("Playlist start position: %s" % startPos, 1)
        self.logMsg("Playlist plugin position: %s" % currentPosition, 1)
        self.logMsg("Playlist size: %s" % sizePlaylist, 1)

        ############### RESUME POINT ################
        
        userdata = API.getUserData()
        seektime = API.adjustResume(userdata['Resume'])

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            utils.window('emby_playbackProps', value="true")
            self.logMsg("Setting up properties in playlist.", 1)

            if (not homeScreen and not seektime and 
                    utils.window('emby_customPlaylist') != "true"):
                
                self.logMsg("Adding dummy file to playlist.", 2)
                dummyPlaylist = True
                playlist.add(playurl, listitem, index=startPos)
                # Remove the original item from playlist 
                self.pl.removefromPlaylist(startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have full metadata
                self.pl.insertintoPlaylist(currentPosition+1, dbid, item['Type'].lower())
                currentPosition += 1
            
            ############### -- CHECK FOR INTROS ################

            if utils.settings('enableCinema') == "true" and not seektime:
                # if we have any play them when the movie/show is not being resumed
                url = "{server}/emby/Users/{UserId}/Items/%s/Intros?format=json" % itemid    
                intros = doUtils.downloadUrl(url)

                if intros['TotalRecordCount'] != 0:
                    getTrailers = True

                    if utils.settings('askCinema') == "true":
                        resp = xbmcgui.Dialog().yesno("Emby Cinema Mode", "Play trailers?")
                        if not resp:
                            # User selected to not play trailers
                            getTrailers = False
                            self.logMsg("Skip trailers.", 1)
                    
                    if getTrailers:
                        for intro in intros['Items']:
                            # The server randomly returns intros, process them.
                            introListItem = xbmcgui.ListItem()
                            introPlayurl = putils.PlayUtils(intro).getPlayUrl()
                            self.logMsg("Adding Intro: %s" % introPlayurl, 1)

                            # Set listitem and properties for intros
                            pbutils = PlaybackUtils(intro)
                            pbutils.setProperties(introPlayurl, introListItem)

                            self.pl.insertintoPlaylist(currentPosition, url=introPlayurl)
                            introsPlaylist = True
                            currentPosition += 1


            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ###############

            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                self.logMsg("Adding main item to playlist.", 1)
                self.pl.addtoPlaylist(dbid, item['Type'].lower())

            # Ensure that additional parts are played after the main item
            currentPosition += 1

            ############### -- CHECK FOR ADDITIONAL PARTS ################
            
            if item.get('PartCount'):
                # Only add to the playlist after intros have played
                partcount = item['PartCount']
                url = "{server}/emby/Videos/%s/AdditionalParts?format=json" % itemid
                parts = doUtils.downloadUrl(url)
                for part in parts['Items']:

                    additionalListItem = xbmcgui.ListItem()
                    additionalPlayurl = putils.PlayUtils(part).getPlayUrl()
                    self.logMsg("Adding additional part: %s" % partcount, 1)

                    # Set listitem and properties for each additional parts
                    pbutils = PlaybackUtils(part)
                    pbutils.setProperties(additionalPlayurl, additionalListItem)
                    pbutils.setArtwork(additionalListItem)

                    playlist.add(additionalPlayurl, additionalListItem, index=currentPosition)
                    self.pl.verifyPlaylist()
                    currentPosition += 1

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                self.logMsg("Processed as a playlist. First item is skipped.", 1)
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)
                

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            self.logMsg("Resetting properties playback flag.", 2)
            utils.window('emby_playbackProps', clear=True)

        #self.pl.verifyPlaylist()
        ########## SETUP MAIN ITEM ##########

        # For transcoding only, ask for audio/subs pref
        if utils.window('emby_%s.playmethod' % playurl) == "Transcode":
            playurl = playutils.audioSubsPref(playurl, listitem)
            utils.window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

        ############### PLAYBACK ################

        if homeScreen and seektime and utils.window('emby_customPlaylist') != "true":
            self.logMsg("Play as a widget item.", 1)
            self.setListItem(listitem)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        elif ((introsPlaylist and utils.window('emby_customPlaylist') == "true") or
            (homeScreen and not sizePlaylist)):
            # Playlist was created just now, play it.
            self.logMsg("Play playlist.", 1)
            xbmc.Player().play(playlist, startpos=startPos)

        else:
            self.logMsg("Play as a regular item.", 1)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def setProperties(self, playurl, listitem):
        # Set all properties necessary for plugin path playback
        itemid = self.API.getRatingKey()
        itemtype = self.API.getType()
        resume, runtime = self.API.getRuntime()

        embyitem = "emby_%s" % playurl
        utils.window('%s.runtime' % embyitem, value=str(runtime))
        utils.window('%s.type' % embyitem, value=itemtype)
        utils.window('%s.itemid' % embyitem, value=itemid)

        if itemtype == "episode":
            utils.window('%s.refreshid' % embyitem,
                         value=self.API.getParentRatingKey())
        else:
            utils.window('%s.refreshid' % embyitem, value=itemid)

        # Append external subtitles to stream
        playmethod = utils.window('%s.playmethod' % embyitem)
        # Only for direct play and direct stream
        # subtitles = self.externalSubs(playurl)
        subtitles = self.API.externalSubs(playurl)
        if playmethod != "Transcode":
            # Direct play automatically appends external
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
        # allartwork = artwork.getAllArtwork(item, parentInfo=True)
        allartwork = self.API.getAllArtwork(parentInfo=True)
        self.logMsg('allartwork: %s' % allartwork, 2)
        # Set artwork for listitem
        arttypes = {

            'poster': "Primary",
            'tvshow.poster': "Primary",
            'clearart': "Art",
            'tvshow.clearart': "Art",
            'clearlogo': "Logo",
            'tvshow.clearlogo': "Logo",
            'discart': "Disc",
            'fanart_image': "Backdrop",
            'landscape': "Thumb"
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
            'aired': API.getPremiereDate(),
            'votes': None
        }

        if "Episode" in mediaType:
            # Only for tv shows
            key, show, season, episode = API.getEpisodeDetails()
            metadata['episode'] = episode
            metadata['season'] = season
            metadata['tvshowtitle'] = show
        # Additional values:
            # - Video Values:
            # 'tracknumber': None,
            # - overlay : integer (2) - range is 0..8. See GUIListItem.h for
            # values
            # - castandrole : list of tuples ([("Michael C. Hall","Dexter"),
            # ("Jennifer Carpenter","Debra")])
            # # - originaltitle : string (Big Fan)
            # - code : string (tt0110293) - IMDb code
            # - aired : string (2008-12-07)
            # - trailer : string (/home/user/trailer.avi)
            #     - album : string (The Joshua Tree)
            #     - artist : list (['U2'])
        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)
        """
          - Music Values:
              - tracknumber : integer (8)
              - discnumber : integer (2)
              - duration : integer (245) - duration in seconds
              - year : integer (1998)
              - genre : string (Rock)
              - album : string (Pulse)
              - artist : string (Muse)
              - title : string (American Pie)
              - rating : string (3) - single character between 0 and 5
              - lyrics : string (On a dark desert highway...)
              - playcount : integer (2) - number of times this item has been
                            played
              - lastplayed : string (Y-m-d h:m:s = 2009-04-05 23:16:04)

          - Picture Values:
              - title : string (In the last summer-1)
              - picturepath : string (/home/username/pictures/img001.jpg)
              - exif : string (See CPictureInfoTag::TranslateString in
                PictureInfoTag.cpp for valid strings)
        """

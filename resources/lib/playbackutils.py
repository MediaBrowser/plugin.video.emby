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

    def __init__(self, item):

        self.item = item

        self.doUtils = downloadutils.DownloadUtils()

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)
        self.machineIdentifier = utils.window('plex_machineIdentifier')

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.pl = playlist.Playlist()

    def StartPlay(self, resume=0, resumeItem=""):
        self.logMsg("StartPlay called with resume=%s, resumeItem=%s"
                    % (resume, resumeItem), 1)
        # Why should we have different behaviour if user is on home screen?!?
        # self.homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        self.startPos = max(self.playlist.getposition(), 0)  # Can return -1
        sizePlaylist = self.playlist.size()
        self.currentPosition = self.startPos
        self.logMsg("Playlist start position: %s" % self.startPos, 1)
        self.logMsg("Playlist position we're starting with: %s"
                    % self.currentPosition, 1)
        self.logMsg("Playlist size: %s" % sizePlaylist, 1)

        # Might have been called AFTER a playlist has been setup to only
        # update the playitem's url
        self.updateUrlOnly = True if sizePlaylist != 0 else False

        self.plexResumeItemId = resumeItem
        # Where should we ultimately start playback?
        self.resumePos = self.startPos

        # Run through the passed PMS playlist and construct playlist
        startitem = None
        for mediaItem in self.item:
            listitem = self.AddMediaItemToPlaylist(mediaItem)
            if listitem:
                startitem = listitem

        # Return the updated play Url if we've already setup the playlist
        if self.updateUrlOnly:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, startitem)
            return

        # Kick off initial playback
        self.logMsg("Starting playback", 1)
        Player = xbmc.Player()
        Player.play(self.playlist, startpos=self.resumePos)
        if resume != 0:
            try:
                Player.seekTime(resume)
            except:
                self.logMsg("Could not use resume: %s. Start from beginning."
                            % resume, 0)

    def AddMediaItemToPlaylist(self, item):
        """
        Feed with ONE media item from PMS json response
        (on level with e.g. key=/library/metadata/220493 present)

        An item may consist of several parts (e.g. movie in 2 pieces/files)
        """
        API = PlexAPI.API(item)
        playutils = putils.PlayUtils(item)

        # If we're only updating an url, we've been handed metadata for only
        # one part - no need to run over all parts
        if self.updateUrlOnly:
            return playutils.getPlayUrl()[0]

        # e.g. itemid='219155'
        itemid = API.getRatingKey()
        # Get DB id from Kodi by using plex id, if that works
        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby = embydb_functions.Embydb_Functions(embycursor)
        try:
            dbid = emby.getItem_byId(itemid)[0]
        except TypeError:
            # Trailers and the like that are not in the kodi DB
            dbid = None
        embyconn.close()

        # Get playurls per part and process them
        returnListItem = None
        for counter, playurl in enumerate(playutils.getPlayUrl()):
            # One new listitem per part
            listitem = xbmcgui.ListItem()
            # For items that are not (yet) synced to Kodi lib, e.g. trailers
            if not dbid:
                self.logMsg("Add item to playlist without Kodi DB id", 1)
                # Add Plex credentials to url because Kodi will have no headers
                playurl = API.addPlexCredentialsToUrl(playurl)
                listitem.setPath(playurl)
                self.setProperties(playurl, listitem)
                # Set artwork already done in setProperties
                self.playlist.add(
                    playurl, listitem, index=self.currentPosition)
                self.currentPosition += 1
            else:
                self.logMsg("Add item to playlist with existing Kodi DB id", 1)
                self.pl.addtoPlaylist(dbid, API.getType())
                self.currentPosition += 1

            # For transcoding only, ask for audio/subs pref
            if utils.window('emby_%s.playmethod' % playurl) == "Transcode":
                playurl = playutils.audioSubsPref(playurl, listitem)
                utils.window('emby_%s.playmethod' % playurl, value="Transcode")

            playQueueItemID = API.GetPlayQueueItemID()
            # Is this the position where we should start playback?
            if counter == 0:
                if playQueueItemID == self.plexResumeItemId:
                    self.logMsg(
                        "Figure we should start playback at position %s "
                        "with playQueueItemID %s"
                        % (self.currentPosition, playQueueItemID), 2)
                    self.resumePost = self.currentPosition
                    returnListItem = listitem
            # We need to keep track of playQueueItemIDs for Plex Companion
            utils.window(
                'plex_%s.playQueueItemID' % playurl, playQueueItemID)
            utils.window(
                'plex_%s.playlistPosition'
                % playurl, str(self.currentPosition))

        # Log the playlist that we end up with
        self.pl.verifyPlaylist()

        return returnListItem

    def play(self, itemid, dbid=None):
        """
        Original one
        """

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

            if homeScreen and not sizePlaylist:
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

        if homeScreen and seektime:
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
        item = self.item
        # itemid = item['Id']
        itemid = self.API.getRatingKey()
        # itemtype = item['Type']
        itemtype = self.API.getType()
        resume, runtime = self.API.getRuntime()

        embyitem = "emby_%s" % playurl
        utils.window('%s.runtime' % embyitem, value=str(runtime))
        utils.window('%s.type' % embyitem, value=itemtype)
        utils.window('%s.itemid' % embyitem, value=itemid)

        if itemtype == "episode":
            utils.window('%s.refreshid' % embyitem,
                         value=item.get('parentRatingKey'))
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

        item = self.item
        API = self.API
        type = API.getType()
        people = API.getPeople()

        metadata = {
            'title': API.getTitle()[0],
            'year': API.getYear(),
            'plot': API.getPlot(),
            'director': API.joinList(people.get('Director')),
            'writer': API.joinList(people.get('Writer')),
            'mpaa': API.getMpaa(),
            'genre': API.joinList(API.getGenres()),
            'studio': API.joinList(API.getStudios()),
            'aired': API.getPremiereDate(),
            'rating': API.getAudienceRating(),
            'votes': None
        }

        if "Episode" in type:
            # Only for tv shows
            thumbId = item.get('SeriesId')
            season = item.get('ParentIndexNumber', -1)
            episode = item.get('IndexNumber', -1)
            show = item.get('SeriesName', "")

            metadata['TVShowTitle'] = show
            metadata['season'] = season
            metadata['episode'] = episode

        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)
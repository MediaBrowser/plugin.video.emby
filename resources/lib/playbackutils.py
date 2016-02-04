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

    def StartPlay(self, itemid=None, resume=None):
        """
        Feed with a PMS playQueue or a single PMS item metadata XML
        Every item will get put in playlist

        itemid is used to determine the original item supposed to be played
        """
        self.logMsg("StartPlay called with resume=%s, itemid=%s"
                    % (resume, itemid), 1)
        self.itemid = itemid
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
        listtuples = []
        for mediaItem in self.item:
            listtuples += self.AddMediaItemToPlaylist(mediaItem)

        # Kick off playback; no worries about overwriting initial listitem
        if startPlayer:
            self.logMsg("Starting new playback", 1)
            Player = xbmc.Player()
            Player.play(self.playlist, startpos=self.startPos)
            if resume:
                Player.seekTime(resume)
        # Kodi has already started playing; overwrite initial listitem to
        # preserve resume timing on the Kodi side. No trailers anyway
        elif resume > 0:
            self.logMsg("Overwritten Kodi listitem for resume. Pos: %s"
                        % [x for (x, y) in listtuples if
                           x == self.newStartPos][0], 1)
            startitem = [y for (x, y) in listtuples if
                         x == self.newStartPos][0]
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, startitem)
        # No resume point given; start with very first item in our playlist
        else:
            self.logMsg("No resume; start from beginning", 1)
            startitem = [y for (x, y) in listtuples if
                         x == self.startPos][0]
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, startitem)

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
        listtuples = []
        gotStart = False
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

            playQueueItemID = self.API.GetPlayQueueItemID()
            # This is the 1 part we need to start with (otherwise resume is
            # lost on the Kodi side). Skip adding a playlist item; overwrite!
            if (not gotStart and (self.itemid == self.API.getRatingKey() or
                                  self.itemid == playQueueItemID)):
                self.logMsg("Item to start with has playlist position %s"
                            % (self.currentPosition), 1)
                # Safe place we're at for later
                self.newStartPos = self.currentPosition
                # Set flag that we found (first ;-)) start item/part
                gotStart = True
            # Otherwise, add a new playlist item
            else:
                self.playlist.add(
                    playurl, listitem, index=self.currentPosition)

            listtuples.append((self.currentPosition, listitem))
            self.currentPosition += 1

            # We need to keep track of playQueueItemIDs for Plex Companion
            utils.window(
                'plex_%s.playQueueItemID' % playurl, playQueueItemID)
            utils.window(
                'plex_%s.playlistPosition'
                % playurl, str(self.currentPosition))

        return listtuples

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

        # userdata = API.getUserData()
        title, sorttitle = API.getTitle()

        metadata = {
            'genre': API.joinList(API.getGenres()),
            'year': API.getYear(),
            'rating': API.getAudienceRating(),
            # 'playcount': userdata['PlayCount'],
            'cast': people['Cast'],
            'director': API.joinList(people.get('Director')),
            'plot': API.getPlot(),
            'title': title,
            'sorttitle': sorttitle,
            # 'duration': userdata['Runtime'],
            'studio': API.joinList(API.getStudios()),
            'tagline': API.getTagline(),
            'writer': API.joinList(people.get('Writer')),
            'premiered': API.getPremiereDate(),
            'dateadded': API.getDateCreated(),
            # 'lastplayed': userdata['LastPlayedDate'],
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

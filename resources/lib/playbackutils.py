# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import requests
import os
import shutil
import sys

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

import api
import artwork
import downloadutils
import playutils as putils
import playlist
import read_embyserver as embyserver
import shutil
from utils import window, settings, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlaybackUtils():


    def __init__(self, item):

        self.item = item
        log.info(self.item)
        self.API = api.API(item)

        self.server = window('emby_server%s' % window('emby_currUser'))

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()

        self.stack = []
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)


    def play(self, itemid, dbid=None):

        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(self.item)

        log.info("Play called: %s", self.item['Name'])
        playurl = playutils.get_play_url()

        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        seektime = self.API.adjust_resume(self.API.get_userdata()['Resume'])

        ##### CHECK FOR INTROS

        if settings('enableCinema') == "true" and not seektime:
            self._set_intros(itemid)

        ##### ADD MAIN ITEM

        self.set_properties(playurl, listitem)
        self.set_listitem(listitem, dbid)
        self.stack.append([playurl, listitem])

        ##### ADD ADDITIONAL PARTS

        if self.item.get('PartCount'):
            self._set_additional_parts(itemid)

        ##### SETUP PLAYBACK
        ''' To get everything to work together, play the first item in the stack with setResolvedUrl,
            add the rest to the regular playlist.
        '''

        index = max(self.playlist.getposition(), 0) + 1 # Can return -1

        self.stack[0][1].setPath(self.stack[0][0])
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, self.stack[0][1])
        self.stack.pop(0) # remove the first item we just started.

        for stack in self.stack:
            self.playlist.add(url=stack[0], listitem=stack[1], index=index)
            index += 1

    def _set_intros(self, item_id):
        # if we have any play them when the movie/show is not being resumed
        intros = self.emby.get_intros(item_id)

        if intros['Items']:
            enabled = True

            if settings('askCinema') == "true":

                resp = xbmcgui.Dialog().yesno("Emby for Kodi", lang(33016))
                if not resp:
                    # User selected to not play trailers
                    enabled = False
                    log.info("Skip trailers.")

            if enabled:
                for intro in intros['Items']:

                    listitem = xbmcgui.ListItem()
                    url = putils.PlayUtils(intro).get_play_url()
                    log.info("Adding Intro: %s" % url)

                    self.stack.append([url, listitem])

    def _set_additional_parts(self, item_id):

        parts = self.emby.get_additional_parts(item_id)

        for part in parts['Items']:

            listitem = xbmcgui.ListItem()
            url = putils.PlayUtils(part).get_play_url()
            log.info("Adding additional part: %s" % url)

            # Set listitem and properties for each additional parts
            pbutils = PlaybackUtils(part)
            pbutils.set_properties(url, listitem)
            pbutils.setArtwork(listitem)

            self.stack.append([url, listitem])

    def set_listitem(self, listitem, dbid=None):

        people = self.API.get_people()
        mediatype = self.item['Type']

        metadata = {
            'title': self.item.get('Name', "Missing name"),
            'year': self.item.get('ProductionYear'),
            'plot': self.API.get_overview(),
            'director': people.get('Director'),
            'writer': people.get('Writer'),
            'mpaa': self.API.get_mpaa(),
            'genre': " / ".join(self.item['Genres']),
            'studio': " / ".join(self.API.get_studios()),
            'aired': self.API.get_premiere_date(),
            'rating': self.item.get('CommunityRating'),
            'votes': self.item.get('VoteCount')
        }

        if mediatype == "Episode":
            # Only for tv shows
            metadata['mediatype'] = "episode"
            metadata['TVShowTitle'] = self.item.get('SeriesName', "")
            metadata['season'] = self.item.get('ParentIndexNumber', -1)
            metadata['episode'] = self.item.get('IndexNumber', -1)

        elif mediatype == "Movie":
            metadata['mediatype'] = "movie"

        elif mediatype == "MusicVideo":
            metadata['mediatype'] = "musicvideo"

        elif mediatype == "Audio":
            metadata['mediatype'] = "song"

        if dbid:
            metadata['dbid'] = dbid

        listitem.setProperty('IsPlayable', 'true')
        listitem.setProperty('IsFolder', 'false')
        listitem.setLabel(metadata['title'])
        listitem.setInfo('Music' if mediatype == "Audio" else 'Video', infoLabels=metadata)

    def set_properties(self, url, listitem):

        # Set all properties necessary for plugin path playback
        item_id = self.item['Id']
        item_type = self.item['Type']
        play_method = window('emby_%s.playmethod' % url)

        window('emby_%s.json' % url, {

            'url': url,
            'runtime': str(self.item.get('RunTimeTicks')),
            'type': item_type,
            'id': item_id,
            'refreshid': self.item.get('SeriesId') if item_type == "Episode" else item_id,
            'playmethod': play_method
        })

        # Only for direct stream
        if play_method == "DirectStream" and settings('enableExternalSubs') == "true":
            subtitles = self.set_external_subs(url)
            listitem.setSubtitles(subtitles)

        self.set_artwork(listitem)

    def set_external_subs(self, url):

        externalsubs = []
        mapping = {}

        itemid = self.item['Id']
        try:
            mediastreams = self.item['MediaSources'][0]['MediaStreams']
        except (TypeError, KeyError, IndexError):
            return

        temp = xbmc.translatePath(
               "special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

        kodiindex = 0
        for stream in mediastreams:

            index = stream['Index']
            # Since Emby returns all possible tracks together, have to pull only external subtitles.
            # IsTextSubtitleStream if true, is available to download from emby.
            if (stream['Type'] == "Subtitle" and 
                    stream['IsExternal'] and stream['IsTextSubtitleStream']):

                # Direct stream
                url = ("%s/Videos/%s/%s/Subtitles/%s/Stream.%s"
                        % (self.server, itemid, itemid, index, stream['Codec']))

                if "Language" in stream:
                    
                    filename = "Stream.%s.%s" % (stream['Language'], stream['Codec'])
                    try:
                        path = self._download_external_subs(url, temp, filename)
                        externalsubs.append(path)
                    except Exception as e:
                        log.error(e)
                        externalsubs.append(url)
                else:
                    externalsubs.append(url)
                
                # map external subtitles for mapping
                mapping[kodiindex] = index
                kodiindex += 1
        
        mapping = json.dumps(mapping)
        window('emby_%s.indexMapping' % url, value=mapping)

        return externalsubs

    def _download_external_subs(self, src, dst, filename):

        if not xbmcvfs.exists(dst):
            xbmcvfs.mkdir(dst)

        path = os.path.join(dst, filename)

        try:
            response = requests.get(src, stream=True)
            response.raise_for_status()
        except Exception as e:
            raise
        else:
            response.encoding = 'utf-8'
            with open(path, 'wb') as f:
                f.write(response.content)
                del response

            return path

    def set_artwork(self, listitem):

        all_artwork = self.artwork.get_all_artwork(self.item, parent_info=True)
        # Set artwork for listitem
        art = {

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
        for k_art, e_art in art.items():

            if e_art == "Backdrop":
                try: # Backdrop is a list, grab the first backdrop
                    self._set_art(listitem, k_art, all_artwork[e_art][0])
                except Exception: pass
            else:
                self._set_art(listitem, k_art, all_artwork[e_art])

    def _set_art(self, listitem, art, path):
        
        if art in ('thumb', 'fanart_image', 'small_poster', 'tiny_poster',
                   'medium_landscape', 'medium_poster', 'small_fanartimage',
                   'medium_fanartimage', 'fanart_noindicators'):
            
            listitem.setProperty(art, path)
        else:
            listitem.setArt({art: path})

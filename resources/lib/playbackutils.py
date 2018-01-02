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
        self.API = api.API(item)

        self.server = window('emby_server%s' % window('emby_currUser'))

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()

        self.stack = []

        if item['Type'] == "Audio":
            self.playlist = xbmc.Playlist(xbmc.PLAYLIST_MUSIC)
        else:
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def play(self, item_id, dbid=None, force_transcode=False):

        listitem = xbmcgui.ListItem()

        log.info("Play called: %s", self.item['Name'])
        play_url = putils.PlayUtils(self.item, listitem).get_play_url(force_transcode)

        if not play_url:
            if play_url == False: # User backed-out of menu
                self.playlist.clear()
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if force_transcode:
            log.info("Clear the playlist.")
            self.playlist.clear()

        seektime = self.API.adjust_resume(self.API.get_userdata()['Resume'])
        if seektime:
            listitem.setProperty('StartOffset', str(seektime))

        ##### CHECK FOR INTROS

        if settings('enableCinema') == "true" and not seektime:
            self._set_intros(item_id)

        ##### ADD MAIN ITEM

        self.set_properties(play_url, listitem)
        self.set_listitem(listitem, dbid)
        self.stack.append([play_url, listitem])

        ##### ADD ADDITIONAL PARTS

        if self.item.get('PartCount'):
            self._set_additional_parts(item_id)

        ##### SETUP PLAYBACK

        ''' To get everything to work together, play the first item in the stack with setResolvedUrl,
            add the rest to the regular playlist.
        '''

        index = max(self.playlist.getposition(), 0) + 1 # Can return -1
        force_play = False

        # Stack: [(url, listitem), (url, ...), ...]
        self.stack[0][1].setPath(self.stack[0][0])
        try:
            if xbmc.getCondVisibility('Window.IsVisible(10000)'):
                raise IndexError

            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, self.stack[0][1])
            self.stack.pop(0) # remove the first item we just started.
        except IndexError:
            log.info("Playback activated via the context menu.")
            force_play = True

        for stack in self.stack:
            self.playlist.add(url=stack[0], listitem=stack[1], index=index)
            index += 1

        if force_play:
            xbmc.Player().play(self.playlist)

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
                    url = putils.PlayUtils(intro, listitem).get_play_url()
                    log.info("Adding Intro: %s" % url)

                    self.stack.append([url, listitem])

    def _set_additional_parts(self, item_id):

        parts = self.emby.get_additional_parts(item_id)

        for part in parts['Items']:

            listitem = xbmcgui.ListItem()
            url = putils.PlayUtils(part, listitem).get_play_url()
            log.info("Adding additional part: %s" % url)

            # Set listitem and properties for each additional parts
            pb = PlaybackUtils(part)
            pb.set_properties(url, listitem)
            pb.setArtwork(listitem)

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
        window('emby_%s.playmethod' % url, clear=True)
        window('emby_%s.json' % url, {

            'url': url,
            'runtime': str(self.item.get('RunTimeTicks')),
            'type': item_type,
            'id': item_id,
            'refreshid': self.item.get('SeriesId') if item_type == "Episode" else item_id,
            'playmethod': play_method
        })

        self.set_artwork(listitem)

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

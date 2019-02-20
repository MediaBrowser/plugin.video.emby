# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcgui
import xbmcvfs

import api
import playutils
from . import _, settings, dialog, window, JSONRPC
from objects import Actions
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlayStrm(object):

    def __init__(self, params, server_id=None):

        ''' Workflow: Strm that calls our webservice in database. When played,
            the webserivce returns a dummy file to play. Meanwhile,
            PlayStrm adds the real listitems for items to play to the playlist.
        '''
        self.info = {
            'Intros': None,
            'Item': None,
            'Id': params.get('Id'),
            'DbId': params.get('KodiId'),
            'Transcode': params.get('transcode'),
            'AdditionalParts': None,
            'ServerId': server_id,
            'KodiPlaylist': xbmc.PlayList(xbmc.PLAYLIST_VIDEO),
            'Server': Emby(server_id).get_client()
        }
        if self.info['Transcode'] is None:
             self.info['Transcode'] = settings('playFromTranscode.bool') if settings('playFromStream.bool') else None

        self.actions = Actions(server_id, self.info['Server']['auth/server-address'])
        self.set_listitem = self.actions.set_listitem
        self.params = params
        self._detect_play()
        LOG.info("[ play strm ]")

    def remove_from_playlist(self, index, playlist_id=None):

        playlist = playlist_id or 1
        JSONRPC('Playlist.Remove').execute({'playlistid': playlist_id, 'position': index})
    
    def remove_from_playlist_by_path(self, path):
        
        LOG.debug("[ removing ] %s", path)
        self.info['KodiPlaylist'].remove(path)

    def _get_intros(self):
        self.info['Intros'] = self.info['Server']['api'].get_intros(self.info['Id'])

    def _get_additional_parts(self):
        self.info['AdditionalParts'] = self.info['Server']['api'].get_additional_parts(self.info['Id'])

    def _get_item(self):
        self.info['Item'] = self.info['Server']['api'].get_item(self.info['Id'])

    def _detect_play(self):

        ''' Download all information needed to build the playlist for item requested.
        '''
        if self.info['Id']:

            self._get_intros()
            self._get_item()
            self._get_additional_parts()

    def start_playback(self, index=0):
        xbmc.Player().play(self.info['KodiPlaylist'], startpos=index, windowed=False)

    def play(self, delayed=True):

        ''' Create and add listitems to the Kodi playlist.
        '''
        if window('emby_playlistclear.bool'):
            
            LOG.info("[ play clearing playlist ]")
            self.actions.get_playlist(self.info['Item']).clear()
            window('emby_playlistclear.bool', clear=True)

        self.info['StartIndex'] = max(self.info['KodiPlaylist'].getposition(), 0)
        self.info['Index'] = self.info['StartIndex']
        LOG.info("[ play/%s/%s ]", self.info['Id'], self.info['Index'])

        listitem = xbmcgui.ListItem()
        self._set_playlist(listitem)

        if not delayed:
            self.start_playback(self.info['StartIndex'])

        return self.info['StartIndex']

    def play_folder(self, position=None):

        ''' When an entire queue is requested, 
            queue playlist items using strm links to setup playback later.
        '''
        self.info['StartIndex'] = position or max(self.info['KodiPlaylist'].size(), 0)
        self.info['Index'] = self.info['StartIndex'] + 1
        LOG.info("[ play folder/%s/%s ]", self.info['Id'], self.info['Index'])

        listitem = xbmcgui.ListItem()
        self.actions.set_listitem(self.info['Item'], listitem, self.info['DbId'])
        url = "http://127.0.0.1:57578/emby/play/file.strm?mode=playfolder&Id=%s" % self.info['Id']

        if self.info['DbId']:
            url += "&KodiId=%s" % self.info['DbId']

        if self.info['ServerId']:
            url += "&server=%s" % self.info['ServerId']

        if self.info['Transcode']:
            url += "&transcode=true"

        listitem.setPath(url)
        self.info['KodiPlaylist'].add(url=url, listitem=listitem, index=self.info['Index'])

        return self.info['Index']

    def _set_playlist(self, listitem):

        ''' Verify seektime, set intros, set main item and set additional parts.
            Detect the seektime for video type content.
            Verify the default video action set in Kodi for accurate resume behavior.
        '''
        seektime = window('emby.resume')
        window('emby.resume', clear=True)
        seektime = seektime == 'true' if seektime else None

        if seektime is None and self.info['Item']['MediaType'] in ('Video', 'Audio'):
            resume = self.info['Item']['UserData'].get('PlaybackPositionTicks')

            if resume:
                choice = self.actions.resume_dialog(api.API(self.info['Item'], self.info['Server']).adjust_resume((resume or 0) / 10000000.0), self.info['Item'])

                if choice is None:
                    raise Exception("User backed out of resume dialog.")

                seektime = False if not choice else True

        if settings('enableCinema.bool') and not seektime:
            self._set_intros()

        LOG.info("[ main/%s/%s ] %s", self.info['Item']['Id'], self.info['Index'], self.info['Item']['Name'])
        play = playutils.PlayUtilsStrm(self.info['Item'], self.info['Transcode'], self.info['ServerId'], self.info['Server'])
        source = play.select_source(play.get_sources())

        if not source:
            raise Exception("Playback selection cancelled")

        play.set_external_subs(source, listitem)
        self.set_listitem(self.info['Item'], listitem, self.info['DbId'], seektime)
        listitem.setPath(self.info['Item']['PlaybackInfo']['Path'])
        playutils.set_properties(self.info['Item'], self.info['Item']['PlaybackInfo']['Method'], self.info['ServerId'])

        self.info['KodiPlaylist'].add(url=self.info['Item']['PlaybackInfo']['Path'], listitem=listitem, index=self.info['Index'])
        self.info['Index'] += 1

        if self.info['Item'].get('PartCount'):
            self._set_additional_parts()

    def _set_intros(self):

        ''' if we have any play them when the movie/show is not being resumed.
        '''
        if self.info['Intros']['Items']:
            enabled = True

            if settings('askCinema') == "true":

                resp = dialog("yesno", heading="{emby}", line1=_(33016))
                if not resp:

                    enabled = False
                    LOG.info("Skip trailers.")

            if enabled:
                for intro in self.info['Intros']['Items']:

                    listitem = xbmcgui.ListItem()
                    LOG.info("[ intro/%s/%s ] %s", intro['Id'], self.info['Index'], intro['Name'])

                    play = playutils.PlayUtilsStrm(intro, False, self.info['ServerId'], self.info['Server'])
                    source = play.select_source(play.get_sources())
                    self.set_listitem(intro, listitem, intro=True)
                    listitem.setPath(intro['PlaybackInfo']['Path'])
                    playutils.set_properties(intro, intro['PlaybackInfo']['Method'], self.info['ServerId'])

                    self.info['KodiPlaylist'].add(url=intro['PlaybackInfo']['Path'], listitem=listitem, index=self.info['Index'])
                    self.info['Index'] += 1

                    window('emby.skip.%s' % intro['Id'], value="true")

    def _set_additional_parts(self):

        ''' Create listitems and add them to the stack of playlist.
        '''
        for part in self.info['AdditionalParts']['Items']:

            listitem = xbmcgui.ListItem()
            LOG.info("[ part/%s/%s ] %s", part['Id'], self.info['Index'], part['Name'])

            play = playutils.PlayUtilsStrm(part, self.info['Transcode'], self.info['ServerId'], self.info['Server'])
            source = play.select_source(play.get_sources())
            play.set_external_subs(source, listitem)
            self.set_listitem(part, listitem)
            listitem.setPath(part['PlaybackInfo']['Path'])
            playutils.set_properties(part, part['PlaybackInfo']['Method'], self.info['ServerId'])

            self.info['KodiPlaylist'].add(url=part['PlaybackInfo']['Path'], listitem=listitem, index=self.info['Index'])
            self.info['Index'] += 1

# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys

import xbmc
import xbmcgui
import xbmcvfs
import xbmcplugin

import api
import playutils
from . import _, settings, dialog, window, JSONRPC
from downloader import TheVoid
from objects import Actions
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlaySimple(object):

    def __init__(self, params, server_id=None):

        ''' Workflow: Strm that calls our webservice in database. When played,
            the webserivce returns a dummy file to play. Meanwhile,
            PlayStrm adds the real listitems for items to play to the playlist.
        '''
        self.info = {
            'Item': None,
            'Id': params.get('id'),
            'DbId': params.get('dbid'),
            'Transcode': params.get('transcode'),
            'ServerId': server_id,
            'Server': TheVoid('GetServerAddress', {'ServerId': server_id}).get(),
        }
        if self.info['Transcode'] is None:
             self.info['Transcode'] = settings('playFromTranscode.bool') if settings('playFromStream.bool') else None

        self.actions = Actions(server_id, self.info['Server'])
        self.set_listitem = self.actions.set_listitem
        self.params = params
        self._detect_play()
        LOG.info("[ play simple ]")

    def _get_item(self):
        self.info['Item'] = TheVoid('GetItem', {'Id': self.info['Id'], 'ServerId': self.info['Server']}).get()

    def _detect_play(self):

        ''' Download all information needed to build the playlist for item requested.
        '''
        if self.info['Id']:
            self._get_item()

    def play(self):

        ''' Create and add listitems to the Kodi playlist.
        '''
        LOG.info("[ play/%s ]", self.info['Id'])

        listitem = xbmcgui.ListItem()
        self._set_playlist(listitem)

        return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def _set_playlist(self, listitem):

        ''' Verify seektime, set intros, set main item and set additional parts.
            Detect the seektime for video type content.
            Verify the default video action set in Kodi for accurate resume behavior.
        '''
        seektime = self._resume()

        LOG.info("[ main/%s ] %s", self.info['Item']['Id'], self.info['Item']['Name'])
        play = playutils.PlayUtils(self.info['Item'], self.info['Transcode'], self.info['ServerId'], self.info['Server'])
        source = play.select_source(play.get_sources())

        if not source:
            raise Exception("Playback selection cancelled")

        play.set_external_subs(source, listitem)
        self.set_listitem(self.info['Item'], listitem, self.info['DbId'], seektime)
        listitem.setPath(self.info['Item']['PlaybackInfo']['Path'])
        playutils.set_properties(self.info['Item'], self.info['Item']['PlaybackInfo']['Method'], self.info['ServerId'])

    def _resume(self):

        ''' Resume item if available.
            Returns bool or raise an exception if resume was cancelled by user.
        '''
        seektime = window('emby.resume')
        seektime = seektime == 'true' if seektime else None
        auto_play = window('emby.autoplay.bool')
        window('emby.resume', clear=True)

        if auto_play:

            seektime = False
            LOG.info("[ skip resume for auto play ]")

        elif seektime is None and self.info['Item']['MediaType'] in ('Video', 'Audio'):
            resume = self.info['Item']['UserData'].get('PlaybackPositionTicks')

            if resume:

                adjusted = api.API(self.info['Item'], self.info['Server']).adjust_resume((resume or 0) / 10000000.0)
                seektime = self.actions.resume_dialog(adjusted, self.info['Item'])
                LOG.info("Resume: %s", adjusted)

                if seektime is None:
                    raise Exception("User backed out of resume dialog.")

            window('emby.autoplay.bool', True)

        return seektime

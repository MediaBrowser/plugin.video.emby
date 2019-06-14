#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
import urllib

from ..utils import etree
from .. import variables as v, utils

ICON_PATH = 'special://home/addons/plugin.video.plexkodiconnect/icon.png'
RECOMMENDED_SCORE_LOWER_BOUND = 7

# Logic of the following nodes:
# (node_type,
#  label/node name,
#  args for PKC add-on callback,
#  Kodi "content",
#  Bool: does this node's xml even point back to PKC add-on callback?
#  )
NODE_TYPES = {
    v.PLEX_TYPE_MOVIE: (
        ('ondeck',
         utils.lang(39500),  # "On Deck"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/onDeck',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         True),
        ('pkc_ondeck',
         utils.lang(39502),  # "PKC On Deck (faster)"
         {},
         'movies',
         False),
        ('recent',
         utils.lang(30174),  # "Recently Added"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/recentlyAdded',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('all',
         '{self.name}',  # We're using this section's name
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/all',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('recommended',
         utils.lang(30230),  # "Recommended"
         {
              'mode': 'browseplex',
              'key': ('/library/sections/{self.section_id}&%s'
                      % urllib.urlencode({'sort': 'rating:desc'})),
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('genres',
         utils.lang(135),  # "Genres"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/genre',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('sets',
         utils.lang(39501),  # "Collections"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/collection',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('random',
         utils.lang(30227),  # "Random"
         {
              'mode': 'browseplex',
              'key': ('/library/sections/{self.section_id}&%s'
                      % urllib.urlencode({'sort': 'random'})),
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('lastplayed',
         utils.lang(568),  # "Last played"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/recentlyViewed',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         False),
        ('browse',
         utils.lang(39702),  # "Browse by folder"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/folder',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         True),
        ('more',
         utils.lang(22082),  # "More..."
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'movies',
         True),
    ),
    ###########################################################
    v.PLEX_TYPE_SHOW: (
        ('ondeck',
         utils.lang(39500),  # "On Deck"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/onDeck',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'episodes',
         True),
        ('recent',
         utils.lang(30174),  # "Recently Added"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/recentlyAdded',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'episodes',
         False),
        ('all',
         '{self.name}',  # We're using this section's name
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/all',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'tvshows',
         False),
        ('recommended',
         utils.lang(30230),  # "Recommended"
         {
              'mode': 'browseplex',
              'key': ('/library/sections/{self.section_id}&%s'
                      % urllib.urlencode({'sort': 'rating:desc'})),
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'tvshows',
         False),
        ('genres',
         utils.lang(135),  # "Genres"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/genre',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'tvshows',
         False),
        ('sets',
         utils.lang(39501),  # "Collections"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/collection',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'tvshows',
         True),  # There are no sets/collections for shows with Kodi
        ('random',
         utils.lang(30227),  # "Random"
         {
              'mode': 'browseplex',
              'key': ('/library/sections/{self.section_id}&%s'
                      % urllib.urlencode({'sort': 'random'})),
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'tvshows',
         False),
        ('lastplayed',
         utils.lang(568),  # "Last played"
         {
              'mode': 'browseplex',
              'key': ('/library/sections/{self.section_id}/recentlyViewed&%s'
                      % urllib.urlencode({'type': v.PLEX_TYPE_NUMBER_FROM_PLEX_TYPE[v.PLEX_TYPE_EPISODE]})),
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'episodes',
         False),
        ('browse',
         utils.lang(39702),  # "Browse by folder"
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}/folder',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'episodes',
         True),
        ('more',
         utils.lang(22082),  # "More..."
         {
              'mode': 'browseplex',
              'key': '/library/sections/{self.section_id}',
              'plex_type': '{self.section_type}',
              'section_id': '{self.section_id}'
         },
         'episodes',
         True),
    ),
}


def node_pms(section, node_name, args):
    """
    Nodes where the logic resides with the PMS - we're NOT building an
    xml that filters and sorts, but point to PKC add-on path
    """
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'folder'})
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'path').text = section.addon_path(args)
    return xml


def node_pkc_ondeck(section, node_name):
    """
    For movies only - returns in-progress movies sorted by last played
    """
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    etree.SubElement(xml, 'rule', attrib={'field': 'inprogress',
                                          'operator': 'true'})
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'limit').text = utils.settings('widgetLimit')
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'descending'}).text = 'lastplayed'
    return xml


def node_recent(section, node_name):
    xml = etree.Element('node',
                        attrib={'order': unicode(section.order),
                                'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    if ((section.section_type == v.PLEX_TYPE_SHOW and
            utils.settings('TVShowWatched') == 'false') or
        (section.section_type == v.PLEX_TYPE_MOVIE and
            utils.settings('MovieShowWatched') == 'false')):
        # Adds an additional rule if user deactivated the PKC setting
        # "Recently Added: Also show already watched episodes"
        # or
        # "Recently Added: Also show already watched episodes"
        rule = etree.SubElement(xml, 'rule', attrib={'field': 'playcount',
                                                     'operator': 'is'})
        etree.SubElement(rule, 'value').text = '0'
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'limit').text = utils.settings('widgetLimit')
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'descending'}).text = 'dateadded'
    return xml


def node_all(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'ascending'}).text = 'sorttitle'
    return xml


def node_recommended(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    # rule = etree.SubElement(xml, 'rule', attrib={'field': 'rating',
    #                                              'operator': 'greaterthan'})
    # etree.SubElement(rule, 'value').text = unicode(RECOMMENDED_SCORE_LOWER_BOUND)
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'limit').text = utils.settings('widgetLimit')
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'descending'}).text = 'rating'
    return xml


def node_genres(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'ascending'}).text = 'sorttitle'
    etree.SubElement(xml, 'group').text = 'genres'
    return xml


def node_sets(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    # "Collections"
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'ascending'}).text = 'sorttitle'
    etree.SubElement(xml, 'group').text = 'sets'
    return xml


def node_random(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'limit').text = utils.settings('widgetLimit')
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'ascending'}).text = 'random'
    return xml


def node_lastplayed(section, node_name):
    xml = etree.Element('node', attrib={'order': unicode(section.order),
                                        'type': 'filter'})
    etree.SubElement(xml, 'match').text = 'all'
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'tag',
                                                 'operator': 'is'})
    etree.SubElement(rule, 'value').text = section.name
    rule = etree.SubElement(xml, 'rule', attrib={'field': 'playcount',
                                                 'operator': 'greaterthan'})
    etree.SubElement(rule, 'value').text = '0'
    etree.SubElement(xml, 'label').text = node_name
    etree.SubElement(xml, 'icon').text = ICON_PATH
    etree.SubElement(xml, 'content').text = section.content
    etree.SubElement(xml, 'limit').text = utils.settings('widgetLimit')
    etree.SubElement(xml,
                     'order',
                     attrib={'direction':
                             'descending'}).text = 'lastplayed'
    return xml

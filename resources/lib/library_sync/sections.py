#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import copy

from . import common, videonodes
from ..utils import cast
from ..plex_db import PlexDB
from .. import kodi_db
from .. import itemtypes
from .. import plex_functions as PF, music, utils, state, variables as v

LOG = getLogger('PLEX.sync.sections')

VNODES = videonodes.VideoNodes()
PLAYLISTS = {}
NODES = {}
SECTIONS = []


def sync_from_pms():
    """
    Sync the Plex library sections
    """
    sections = PF.get_plex_sections()
    try:
        sections.attrib
    except AttributeError:
        LOG.error("Error download PMS sections, abort")
        return False
    if state.DIRECT_PATHS is True and state.ENABLE_MUSIC is True:
        # Will reboot Kodi is new library detected
        music.excludefromscan_music_folders(xml=sections)

    global PLAYLISTS, NODES, SECTIONS
    SECTIONS = []
    NODES = {
        v.PLEX_TYPE_MOVIE: [],
        v.PLEX_TYPE_SHOW: [],
        v.PLEX_TYPE_ARTIST: [],
        v.PLEX_TYPE_PHOTO: []
    }
    PLAYLISTS = copy.deepcopy(NODES)
    sorted_sections = []

    for section in sections:
        if (section.attrib['type'] in
                (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW, v.PLEX_TYPE_PHOTO,
                 v.PLEX_TYPE_ARTIST)):
            sorted_sections.append(section.attrib['title'])
    LOG.debug('Sorted sections: %s', sorted_sections)
    totalnodes = len(sorted_sections)

    VNODES.clearProperties()

    with PlexDB() as plexdb:
        # Backup old sections to delete them later, if needed (at the end
        # of this method, only unused sections will be left in old_sections)
        old_sections = list(plexdb.section_ids())
        with kodi_db.KodiVideoDB() as kodidb:
            for section in sections:
                _process_section(section,
                                 kodidb,
                                 plexdb,
                                 sorted_sections,
                                 old_sections,
                                 totalnodes)
    if old_sections:
        # Section has been deleted on the PMS
        delete_sections(old_sections)
    # update sections for all:
    with PlexDB() as plexdb:
        SECTIONS = list(plexdb.section_infos())
    utils.window('Plex.nodes.total', str(totalnodes))
    LOG.info("Finished processing library sections: %s", SECTIONS)
    return True


def _process_section(section_xml, kodidb, plexdb, sorted_sections,
                     old_sections, totalnodes):
    folder = section_xml.attrib
    plex_type = folder['type']
    # Only process supported formats
    if plex_type not in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW,
                         v.PLEX_TYPE_ARTIST, v.PLEX_TYPE_PHOTO):
        LOG.error('Unsupported Plex section type: %s', folder)
        return totalnodes
    section_id = cast(int, folder['key'])
    section_name = folder['title']
    global PLAYLISTS, NODES
    # Prevent duplicate for nodes of the same type
    nodes = NODES[plex_type]
    # Prevent duplicate for playlists of the same type
    playlists = PLAYLISTS[plex_type]
    # Get current media folders from plex database
    section = plexdb.section(section_id)
    try:
        current_sectionname = section[1]
        current_sectiontype = section[2]
        current_tagid = section[3]
    except TypeError:
        LOG.info('Creating section id: %s in Plex database.', section_id)
        tagid = kodidb.create_tag(section_name)
        # Create playlist for the video library
        if (section_name not in playlists and
                plex_type in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW)):
            utils.playlist_xsp(plex_type, section_name, section_id)
            playlists.append(section_name)
        # Create the video node
        if section_name not in nodes:
            VNODES.viewNode(sorted_sections.index(section_name),
                            section_name,
                            plex_type,
                            None,
                            section_id)
            nodes.append(section_name)
            totalnodes += 1
        # Add view to plex database
        plexdb.add_section(section_id, section_name, plex_type, tagid)
    else:
        LOG.info('Found library section id %s, name %s, type %s, tagid %s',
                 section_id, current_sectionname, current_sectiontype,
                 current_tagid)
        # Remove views that are still valid to delete rest later
        try:
            old_sections.remove(section_id)
        except ValueError:
            # View was just created, nothing to remove
            pass

        # View was modified, update with latest info
        if current_sectionname != section_name:
            LOG.info('section id: %s new sectionname: %s',
                     section_id, section_name)
            tagid = kodidb.create_tag(section_name)

            # Update view with new info
            plexdb.add_section(section_id,
                               section_name,
                               plex_type,
                               tagid)

            if plexdb.section_id_by_name(current_sectionname) is None:
                # The tag could be a combined view. Ensure there's
                # no other tags with the same name before deleting
                # playlist.
                utils.playlist_xsp(plex_type,
                                   current_sectionname,
                                   section_id,
                                   current_sectiontype,
                                   True)
                # Delete video node
                if plex_type != "musicvideos":
                    VNODES.viewNode(
                        indexnumber=sorted_sections.index(section_name),
                        tagname=current_sectionname,
                        mediatype=plex_type,
                        viewtype=None,
                        viewid=section_id,
                        delete=True)
            # Added new playlist
            if section_name not in playlists and plex_type in v.KODI_VIDEOTYPES:
                utils.playlist_xsp(plex_type,
                                   section_name,
                                   section_id)
                playlists.append(section_name)
            # Add new video node
            if section_name not in nodes and plex_type != "musicvideos":
                VNODES.viewNode(sorted_sections.index(section_name),
                                section_name,
                                plex_type,
                                None,
                                section_id)
                nodes.append(section_name)
                totalnodes += 1
            # Update items with new tag
            for item in plexdb.kodi_id_by_section(section_id):
                # Remove the "s" from viewtype for tags
                kodidb.update_tag(
                    current_tagid, tagid, item[0], current_sectiontype[:-1])
        else:
            # Validate the playlist exists or recreate it
            if (section_name not in playlists and plex_type in
                    (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW)):
                utils.playlist_xsp(plex_type,
                                   section_name,
                                   section_id)
                playlists.append(section_name)
            # Create the video node if not already exists
            if section_name not in nodes and plex_type != "musicvideos":
                VNODES.viewNode(sorted_sections.index(section_name),
                                section_name,
                                plex_type,
                                None,
                                section_id)
                nodes.append(section_name)
                totalnodes += 1
    return totalnodes


def delete_sections(old_sections):
    """
    Deletes all elements for a Plex section that has been deleted. (e.g. all
    TV shows, Seasons and Episodes of a Show section)
    """
    utils.dialog('notification',
                 heading='{plex}',
                 message=utils.lang(30052),
                 icon='{plex}',
                 sound=False)
    video_library_update = False
    music_library_update = False
    with PlexDB() as plexdb:
        old_sections = [plexdb.section(x) for x in old_sections]
        LOG.info("Removing entire Plex library sections: %s", old_sections)
        with kodi_db.KodiVideoDB() as kodidb:
            for section in old_sections:
                if section[2] == v.KODI_TYPE_PHOTO:
                    # not synced
                    plexdb.remove_section(section[0])
                elif section[2] == v.KODI_TYPE_MOVIE:
                    video_library_update = True
                    context = itemtypes.Movie(plexdb=plexdb,
                                              kodidb=kodidb)
                elif section[2] == v.KODI_TYPE_SHOW:
                    video_library_update = True
                    context = itemtypes.Show(plexdb=plexdb,
                                             kodidb=kodidb)
        with kodi_db.KodiMusicDB() as kodidb:
            for section in old_sections:
                if section[2] == v.KODI_TYPE_ARTIST:
                    music_library_update = True
                    context = itemtypes.Artist(plexdb=plexdb,
                                               kodidb=kodidb)
                for plex_id in plexdb.plexid_by_section(section[0]):
                    context.remove(plex_id)
                # Only remove Plex entry if we've removed all items first
                plexdb.remove_section(section[0])
    common.update_kodi_library(video=video_library_update,
                               music=music_library_update)

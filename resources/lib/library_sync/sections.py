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
from .. import plex_functions as PF, music, utils, variables as v, app

LOG = getLogger('PLEX.sync.sections')

BATCH_SIZE = 500
VNODES = videonodes.VideoNodes()
PLAYLISTS = {}
NODES = {}
SECTIONS = []


def isCanceled():
    return app.APP.stop_pkc or app.APP.suspend_threads or app.SYNC.stop_sync


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
    if app.SYNC.direct_paths is True and app.SYNC.enable_music is True:
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
            for kodi_id in plexdb.kodiid_by_sectionid(section_id, plex_type):
                kodidb.update_tag(
                    current_tagid, tagid, kodi_id, current_sectiontype)
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


def _delete_kodi_db_items(section_id, section_type):
    if section_type == v.PLEX_TYPE_MOVIE:
        kodi_context = kodi_db.KodiVideoDB
        types = ((v.PLEX_TYPE_MOVIE, itemtypes.Movie), )
    elif section_type == v.PLEX_TYPE_SHOW:
        kodi_context = kodi_db.KodiVideoDB
        types = ((v.PLEX_TYPE_SHOW, itemtypes.Show),
                 (v.PLEX_TYPE_SEASON, itemtypes.Season),
                 (v.PLEX_TYPE_EPISODE, itemtypes.Episode))
    elif section_type == v.PLEX_TYPE_ARTIST:
        kodi_context = kodi_db.KodiMusicDB
        types = ((v.PLEX_TYPE_ARTIST, itemtypes.Artist),
                 (v.PLEX_TYPE_ALBUM, itemtypes.Album),
                 (v.PLEX_TYPE_SONG, itemtypes.Song))
    for plex_type, context in types:
        while True:
            with PlexDB() as plexdb:
                plex_ids = list(plexdb.plexid_by_sectionid(section_id,
                                                           plex_type,
                                                           BATCH_SIZE))
                with kodi_context(texture_db=True) as kodidb:
                    typus = context(None, plexdb=plexdb, kodidb=kodidb)
                    for plex_id in plex_ids:
                        if isCanceled():
                            return False
                        typus.remove(plex_id)
            if len(plex_ids) < BATCH_SIZE:
                break
    return True


def delete_sections(old_sections):
    """
    Deletes all elements for a Plex section that has been deleted. (e.g. all
    TV shows, Seasons and Episodes of a Show section)
    """
    try:
        with PlexDB() as plexdb:
            old_sections = [plexdb.section(x) for x in old_sections]
        LOG.info("Removing entire Plex library sections: %s", old_sections)
        for section in old_sections:
            # "Deleting <section_name>"
            utils.dialog('notification',
                         heading='{plex}',
                         message='%s %s' % (utils.lang(30052), section[1]),
                         icon='{plex}',
                         sound=False)
            if section[2] == v.PLEX_TYPE_PHOTO:
                # not synced - just remove the link in our Plex sections table
                pass
            else:
                if not _delete_kodi_db_items(section[0], section[2]):
                    return
            # Only remove Plex entry if we've removed all items first
            with PlexDB() as plexdb:
                plexdb.remove_section(section[0])
    finally:
        common.update_kodi_library()

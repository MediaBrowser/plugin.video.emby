#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger
import copy

from . import videonodes
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
# Need a way to interrupt
IS_CANCELED = None


def force_full_sync():
    """
    Resets the sync timestamp for all sections to 0, thus forcing a subsequent
    full sync (not delta)
    """
    LOG.info('Telling PKC to do a full sync instead of a delta sync')
    with PlexDB() as plexdb:
        plexdb.force_full_sync()


def sync_from_pms(parent_self):
    """
    Sync the Plex library sections
    """
    global IS_CANCELED
    IS_CANCELED = parent_self.isCanceled
    try:
        return _sync_from_pms()
    finally:
        IS_CANCELED = None


def _sync_from_pms():
    global PLAYLISTS, NODES, SECTIONS
    sections = PF.get_plex_sections()
    try:
        sections.attrib
    except AttributeError:
        LOG.error("Error download PMS sections, abort")
        return False
    if app.SYNC.direct_paths is True and app.SYNC.enable_music is True:
        # Will reboot Kodi is new library detected
        music.excludefromscan_music_folders(xml=sections)

    VNODES.clearProperties()
    SECTIONS = []
    NODES = {
        v.PLEX_TYPE_MOVIE: [],
        v.PLEX_TYPE_SHOW: [],
        v.PLEX_TYPE_ARTIST: [],
        v.PLEX_TYPE_PHOTO: []
    }
    PLAYLISTS = copy.deepcopy(NODES)
    with PlexDB() as plexdb:
        # Backup old sections to delete them later, if needed (at the end
        # of this method, only unused sections will be left in old_sections)
        old_sections = list(plexdb.all_sections())
        with kodi_db.KodiVideoDB() as kodidb:
            for index, section in enumerate(sections):
                _process_section(section,
                                 kodidb,
                                 plexdb,
                                 index,
                                 old_sections)
    if old_sections:
        # Section has been deleted on the PMS
        delete_sections(old_sections)
    # update sections for all:
    with PlexDB() as plexdb:
        SECTIONS = list(plexdb.all_sections())
    utils.window('Plex.nodes.total', str(len(sections)))
    LOG.info("Finished processing %s library sections: %s", len(sections), SECTIONS)
    return True


def _process_section(section_xml, kodidb, plexdb, index, old_sections):
    global PLAYLISTS, NODES
    folder = section_xml.attrib
    plex_type = folder['type']
    # Only process supported formats
    if plex_type not in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW,
                         v.PLEX_TYPE_ARTIST, v.PLEX_TYPE_PHOTO):
        LOG.error('Unsupported Plex section type: %s', folder)
        return
    section_id = cast(int, folder['key'])
    section_name = folder['title']
    # Prevent duplicate for nodes of the same type
    nodes = NODES[plex_type]
    # Prevent duplicate for playlists of the same type
    playlists = PLAYLISTS[plex_type]
    # Get current media folders from plex database
    section = plexdb.section(section_id)
    if not section:
        LOG.info('Creating section id: %s in Plex database.', section_id)
        tagid = kodidb.create_tag(section_name)
        # Create playlist for the video library
        if (section_name not in playlists and
                plex_type in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW)):
            utils.playlist_xsp(plex_type, section_name, section_id)
            playlists.append(section_name)
        # Create the video node
        if section_name not in nodes:
            VNODES.viewNode(index,
                            section_name,
                            plex_type,
                            None,
                            section_id)
            nodes.append(section_name)
        # Add view to plex database
        plexdb.add_section(section_id,
                           section_name,
                           plex_type,
                           tagid,
                           True,  # Sync this new section for now
                           None)
    else:
        LOG.info('Found library section id %s, name %s, type %s, tagid %s',
                 section_id, section['section_name'], section['plex_type'],
                 section['kodi_tagid'])
        # Remove views that are still valid to delete rest later
        for section in old_sections:
            if section['section_id'] == section_id:
                old_sections.remove(section)
                break
        # View was modified, update with latest info
        if section['section_name'] != section_name:
            LOG.info('section id: %s new sectionname: %s',
                     section_id, section_name)
            tagid = kodidb.create_tag(section_name)

            # Update view with new info
            plexdb.add_section(section_id,
                               section_name,
                               plex_type,
                               tagid,
                               section['sync_to_kodi'],  # Use "old" setting
                               section['last_sync'])

            if plexdb.section_id_by_name(section['section_name']) is None:
                # The tag could be a combined view. Ensure there's
                # no other tags with the same name before deleting
                # playlist.
                utils.playlist_xsp(plex_type,
                                   section['section_name'],
                                   section_id,
                                   section['plex_type'],
                                   True)
                # Delete video node
                if plex_type != "musicvideos":
                    VNODES.viewNode(
                        indexnumber=index,
                        tagname=section['section_name'],
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
                VNODES.viewNode(index,
                                section_name,
                                plex_type,
                                None,
                                section_id)
                nodes.append(section_name)
            # Update items with new tag
            for kodi_id in plexdb.kodiid_by_sectionid(section_id, plex_type):
                kodidb.update_tag(
                    section['kodi_tagid'], tagid, kodi_id, section['plex_type'])
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
                VNODES.viewNode(index,
                                section_name,
                                plex_type,
                                None,
                                section_id)
                nodes.append(section_name)


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
                        if IS_CANCELED():
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
    LOG.info("Removing entire Plex library sections: %s", old_sections)
    for section in old_sections:
        # "Deleting <section_name>"
        utils.dialog('notification',
                     heading='{plex}',
                     message='%s %s' % (utils.lang(30052), section['section_name']),
                     icon='{plex}',
                     sound=False)
        if section['plex_type'] == v.PLEX_TYPE_PHOTO:
            # not synced - just remove the link in our Plex sections table
            pass
        else:
            if not _delete_kodi_db_items(section['section_id'], section['plex_type']):
                return
        # Only remove Plex entry if we've removed all items first
        with PlexDB() as plexdb:
            plexdb.remove_section(section['section_id'])


def choose_libraries():
    """
    Displays a dialog for the user to select the libraries he wants synched

    Returns True if this was successful, False if not
    """
    # xbmcgui.Dialog().multiselect(heading, options[, autoclose, preselect, useDetails])
    # "Select Plex libraries to sync"
    import xbmcgui
    sections = []
    preselect = []
    for i, section in enumerate(SECTIONS):
        sections.append(section['section_name'])
        if section['plex_type'] == v.PLEX_TYPE_ARTIST:
            if section['sync_to_kodi'] and app.SYNC.enable_music:
                preselect.append(i)
        else:
            if section['sync_to_kodi']:
                preselect.append(i)
    selected = xbmcgui.Dialog().multiselect(utils.lang(30524),
                                            sections,
                                            preselect=preselect,
                                            useDetails=False)
    if selected is None:
        # User canceled
        return False
    with PlexDB() as plexdb:
        for i, section in enumerate(SECTIONS):
            sync = True if i in selected else False
            plexdb.update_section_sync(section['section_id'], sync)
        sections = list(plexdb.all_sections())
    LOG.info('Plex libraries to sync: %s', sections)
    return True

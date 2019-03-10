#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .. import plex_functions as PF, utils, timing, variables as v, app

LOG = getLogger('PLEX.sync.time')


def sync_pms_time():
    """
    PMS does not provide a means to get a server timestamp. This is a work-
    around - because the PMS might be in another time zone

    In general, everything saved to Kodi shall be in Kodi time.

    Any info with a PMS timestamp is in Plex time, naturally
    """
    LOG.info('Synching time with PMS server')
    # Find a PMS item where we can toggle the view state to enforce a
    # change in lastViewedAt

    # Get all Plex libraries
    sections = PF.get_plex_sections()
    if not sections:
        LOG.error("Error download PMS views, abort sync_pms_time")
        return False

    plex_id = None
    typus = (
        (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_MOVIE,),
        (v.PLEX_TYPE_SHOW, v.PLEX_TYPE_EPISODE),
        (v.PLEX_TYPE_ARTIST, v.PLEX_TYPE_SONG)
    )
    for section_type, plex_type in typus:
        if plex_id:
            break
        for section in sections:
            if plex_id:
                break
            if not section.attrib['type'] == section_type:
                continue
            library_id = section.attrib['key']
            try:
                iterator = PF.SectionItems(library_id, plex_type=plex_type)
                for item in iterator:
                    if item.get('viewCount'):
                        # Don't want to mess with items that have playcount>0
                        continue
                    if item.get('viewOffset'):
                        # Don't mess with items with a resume point
                        continue
                    plex_id = utils.cast(int, item.get('ratingKey'))
                    LOG.info('Found a %s item to sync with: %s',
                             plex_type, plex_id)
                    break
            except RuntimeError:
                pass
    if plex_id is None:
        LOG.error("Could not find an item to sync time with")
        LOG.error("Aborting PMS-Kodi time sync")
        return False

    # Get the Plex item's metadata
    xml = PF.GetPlexMetadata(plex_id)
    if xml in (None, 401):
        LOG.error("Could not download metadata, aborting time sync")
        return False

    timestamp = xml[0].get('lastViewedAt')
    if timestamp is None:
        timestamp = xml[0].get('updatedAt')
        LOG.debug('Using items updatedAt=%s', timestamp)
        if timestamp is None:
            timestamp = xml[0].get('addedAt')
            LOG.debug('Using items addedAt=%s', timestamp)
            if timestamp is None:
                timestamp = 0
                LOG.debug('No timestamp; using 0')
    timestamp = utils.cast(int, timestamp)
    # Set the timer
    koditime = timing.unix_timestamp()
    # Toggle watched state
    PF.scrobble(plex_id, 'watched')
    # Let the PMS process this first!
    app.APP.monitor.waitForAbort(1)
    # Get updated metadata
    xml = PF.GetPlexMetadata(plex_id)
    # Toggle watched state back
    PF.scrobble(plex_id, 'unwatched')
    try:
        plextime = xml[0].get('lastViewedAt')
    except (IndexError, TypeError, AttributeError):
        LOG.error('Could not get lastViewedAt - aborting')
        return False

    # Calculate time offset Kodi-PMS
    timing.KODI_PLEX_TIME_OFFSET = float(koditime) - float(plextime)
    utils.settings('kodiplextimeoffset',
                   value=str(timing.KODI_PLEX_TIME_OFFSET))
    LOG.info("Time offset Koditime - Plextime in seconds: %s",
             timing.KODI_PLEX_TIME_OFFSET)
    return True

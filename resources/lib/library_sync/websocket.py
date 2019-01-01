#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import update_kodi_library
from .full_sync import PLAYLIST_SYNC_ENABLED
from .fanart import SYNC_FANART, FanartTask
from ..plex_api import API
from ..plex_db import PlexDB
from .. import kodi_db
from .. import backgroundthread, playlists, plex_functions as PF, itemtypes
from .. import artwork, utils, timing, variables as v, app

LOG = getLogger('PLEX.sync.websocket')

CACHING_ENALBED = utils.settings('enableTextureCache') == "true"

WEBSOCKET_MESSAGES = []
# Dict to save info for Plex items currently being played somewhere
PLAYSTATE_SESSIONS = {}


def interrupt_processing():
    return app.APP.stop_pkc or app.APP.suspend_threads or app.SYNC.stop_sync


def multi_delete(input_list, delete_list):
    """
    Deletes the list items of input_list at the positions in delete_list
    (which can be in any arbitrary order)
    """
    for index in sorted(delete_list, reverse=True):
        del input_list[index]
    return input_list


def store_websocket_message(message):
    """
    processes json.loads() messages from websocket. Triage what we need to
    do with "process_" methods
    """
    if message['type'] == 'playing':
        process_playing(message['PlaySessionStateNotification'])
    elif message['type'] == 'timeline':
        store_timeline_message(message['TimelineEntry'])
    elif message['type'] == 'activity':
        store_activity_message(message['ActivityNotification'])


def process_websocket_messages():
    """
    Periodically called to process new/updated PMS items

    PMS needs a while to download info from internet AFTER it
    showed up under 'timeline' websocket messages

    data['type']:
        1:      movie
        2:      tv show??
        3:      season??
        4:      episode
        8:      artist (band)
        9:      album
        10:     track (song)
        12:     trailer, extras?

    data['state']:
        0: 'created',
        2: 'matching',
        3: 'downloading',
        4: 'loading',
        5: 'finished',
        6: 'analyzing',
        9: 'deleted'
    """
    global WEBSOCKET_MESSAGES
    now = timing.unix_timestamp()
    update_kodi_video_library, update_kodi_music_library = False, False
    delete_list = []
    for i, message in enumerate(WEBSOCKET_MESSAGES):
        if interrupt_processing():
            # Chances are that Kodi gets shut down
            break
        if message['state'] == 9:
            successful, video, music = process_delete_message(message)
        elif now - message['timestamp'] < app.SYNC.backgroundsync_saftymargin:
            # We haven't waited long enough for the PMS to finish processing the
            # item. Do it later (excepting deletions)
            continue
        else:
            successful, video, music = process_new_item_message(message)
            if (successful and SYNC_FANART and
                    message['plex_type'] in (v.PLEX_TYPE_MOVIE, v.PLEX_TYPE_SHOW)):
                task = FanartTask()
                task.setup(message['plex_id'],
                           message['plex_type'],
                           refresh=False)
                backgroundthread.BGThreader.addTask(task)
        if successful is True:
            delete_list.append(i)
            update_kodi_video_library = True if video else update_kodi_video_library
            update_kodi_music_library = True if music else update_kodi_music_library
        else:
            # Safety net if we can't process an item
            message['attempt'] += 1
            if message['attempt'] > 3:
                LOG.error('Repeatedly could not process message %s, abort',
                          message)
                delete_list.append(i)

    # Get rid of the items we just processed
    if delete_list:
        WEBSOCKET_MESSAGES = multi_delete(WEBSOCKET_MESSAGES, delete_list)
    # Let Kodi know of the change
    if update_kodi_video_library or update_kodi_music_library:
        update_kodi_library(video=update_kodi_video_library,
                            music=update_kodi_music_library)


def process_new_item_message(message):
    LOG.debug('Message: %s', message)
    xml = PF.GetPlexMetadata(message['plex_id'])
    try:
        plex_type = xml[0].attrib['type']
    except (IndexError, KeyError, TypeError):
        LOG.error('Could not download metadata for %s', message['plex_id'])
        return False, False, False
    LOG.debug("Processing new/updated PMS item: %s", message['plex_id'])
    attempts = 3
    while True:
        try:
            with itemtypes.ITEMTYPE_FROM_PLEXTYPE[plex_type](timing.unix_timestamp()) as typus:
                typus.add_update(xml[0],
                                 section_name=xml.get('librarySectionTitle'),
                                 section_id=xml.get('librarySectionID'))
            cache_artwork(message['plex_id'], plex_type)
        except utils.OperationalError:
            # Since parallel caching of artwork might invalidade the current
            # WAL snapshot of the db, sqlite immediatly throws
            # OperationalError, NOT after waiting for a duraton of timeout
            # See https://github.com/mattn/go-sqlite3/issues/274#issuecomment-211759641
            LOG.debug('sqlite OperationalError encountered, trying again')
            attempts -= 1
            if attempts == 0:
                LOG.error('Repeatedly could not process message %s', message)
                return False, False, False
            continue
        else:
            break
    return True, plex_type in v.PLEX_VIDEOTYPES, plex_type in v.PLEX_AUDIOTYPES


def process_delete_message(message):
    plex_type = message['plex_type']
    with itemtypes.ITEMTYPE_FROM_PLEXTYPE[plex_type](None) as typus:
        typus.remove(message['plex_id'], plex_type=plex_type)
    return True, plex_type in v.PLEX_VIDEOTYPES, plex_type in v.PLEX_AUDIOTYPES


def store_timeline_message(data):
    """
    PMS is messing with the library items, e.g. new or changed. Put in our
    "processing queue" for later
    """
    global WEBSOCKET_MESSAGES
    for message in data:
        if 'tv.plex' in message.get('identifier', ''):
            # Ommit Plex DVR messages - the Plex IDs are not corresponding
            # (DVR ratingKeys are not unique and might correspond to a
            # movie or episode)
            continue
        typus = v.PLEX_TYPE_FROM_WEBSOCKET[int(message['type'])]
        if typus in (v.PLEX_TYPE_CLIP, v.PLEX_TYPE_SET):
            # No need to process extras or trailers
            continue
        status = int(message['state'])
        if typus == 'playlist' and PLAYLIST_SYNC_ENABLED:
            playlists.websocket(plex_id=unicode(message['itemID']),
                                status=status)
        elif status == 9:
            # Immediately and always process deletions (as the PMS will
            # send additional message with other codes)
            WEBSOCKET_MESSAGES.append({
                'state': status,
                'plex_type': typus,
                'plex_id': utils.cast(int, message['itemID']),
                'timestamp': timing.unix_timestamp(),
                'attempt': 0
            })
        elif typus in (v.PLEX_TYPE_MOVIE,
                       v.PLEX_TYPE_EPISODE,
                       v.PLEX_TYPE_SONG) and status == 5:
            plex_id = int(message['itemID'])
            # Have we already added this element for processing?
            for existing_message in WEBSOCKET_MESSAGES:
                if existing_message['plex_id'] == plex_id:
                    break
            else:
                # Haven't added this element to the queue yet
                WEBSOCKET_MESSAGES.append({
                    'state': status,
                    'plex_type': typus,
                    'plex_id': plex_id,
                    'timestamp': timing.unix_timestamp(),
                    'attempt': 0
                })


def store_activity_message(data):
    """
    PMS is re-scanning an item, e.g. after having changed a movie poster.
    WATCH OUT for this if it's triggered by our PKC library scan!
    """
    global WEBSOCKET_MESSAGES
    for message in data:
        if message['event'] != 'ended':
            # Scan still going on, so skip for now
            continue
        elif message['Activity'].get('Context') is None:
            # Not related to any Plex element, but entire library
            continue
        elif message['Activity']['type'] != 'library.refresh.items':
            # Not the type of message relevant for us
            continue
        plex_id = PF.GetPlexKeyNumber(message['Activity']['Context']['key'])[1]
        if not plex_id:
            # Likely a Plex id like /library/metadata/3/children
            continue
        # We're only looking at existing elements - have we synced yet?
        with PlexDB() as plexdb:
            typus = plexdb.item_by_id(plex_id, plex_type=None)
        if not typus:
            LOG.debug('plex_id %s not synced yet - skipping', plex_id)
            continue
        # Have we already added this element?
        for existing_message in WEBSOCKET_MESSAGES:
            if existing_message['plex_id'] == plex_id:
                break
        else:
            # Haven't added this element to the queue yet
            WEBSOCKET_MESSAGES.append({
                'state': None,  # Don't need a state here
                'plex_type': typus['plex_type'],
                'plex_id': plex_id,
                'timestamp': timing.unix_timestamp(),
                'attempt': 0
            })


def process_playing(data):
    """
    Someone (not necessarily the user signed in) is playing something some-
    where
    """
    global PLAYSTATE_SESSIONS
    for message in data:
        status = message['state']
        if status == 'buffering' or status == 'stopped':
            # Drop buffering and stop messages immediately - no value
            continue
        plex_id = utils.cast(int, message['ratingKey'])
        skip = False
        for pid in (0, 1, 2):
            if plex_id == app.PLAYSTATE.player_states[pid]['plex_id']:
                # Kodi is playing this message - no need to set the playstate
                skip = True
        if skip:
            continue
        session_key = message['sessionKey']
        # Do we already have a sessionKey stored?
        if session_key not in PLAYSTATE_SESSIONS:
            with PlexDB() as plexdb:
                typus = plexdb.item_by_id(plex_id, plex_type=None)
            if not typus:
                # Item not (yet) in Kodi library
                continue
            if utils.settings('plex_serverowned') == 'false':
                # Not our PMS, we are not authorized to get the sessions
                # On the bright side, it must be us playing :-)
                PLAYSTATE_SESSIONS[session_key] = {}
            else:
                # PMS is ours - get all current sessions
                PLAYSTATE_SESSIONS.update(PF.GetPMSStatus(app.ACCOUNT.plex_token))
                LOG.debug('Updated current sessions. They are: %s',
                          PLAYSTATE_SESSIONS)
                if session_key not in PLAYSTATE_SESSIONS:
                    LOG.info('Session key %s still unknown! Skip '
                             'playstate update', session_key)
                    continue
            # Attach Kodi info to the session
            PLAYSTATE_SESSIONS[session_key]['kodi_id'] = typus['kodi_id']
            PLAYSTATE_SESSIONS[session_key]['file_id'] = typus['kodi_fileid']
            PLAYSTATE_SESSIONS[session_key]['kodi_type'] = typus['kodi_type']
        session = PLAYSTATE_SESSIONS[session_key]
        if utils.settings('plex_serverowned') != 'false':
            # Identify the user - same one as signed on with PKC? Skip
            # update if neither session's username nor userid match
            # (Owner sometime's returns id '1', not always)
            if not app.ACCOUNT.plex_token and session['userId'] == '1':
                # PKC not signed in to plex.tv. Plus owner of PMS is
                # playing (the '1').
                # Hence must be us (since several users require plex.tv
                # token for PKC)
                pass
            elif not (session['userId'] == app.ACCOUNT.plex_user_id or
                      session['username'] == app.ACCOUNT.plex_username):
                LOG.debug('Our username %s, userid %s did not match '
                          'the session username %s with userid %s',
                          app.ACCOUNT.plex_username,
                          app.ACCOUNT.plex_user_id,
                          session['username'],
                          session['userId'])
                continue
        # Get an up-to-date XML from the PMS because PMS will NOT directly
        # tell us: duration of item viewCount
        if not session.get('duration'):
            xml = PF.GetPlexMetadata(plex_id)
            if xml in (None, 401):
                LOG.error('Could not get up-to-date xml for item %s',
                          plex_id)
                continue
            api = API(xml[0])
            userdata = api.userdata()
            session['duration'] = userdata['Runtime']
            session['viewCount'] = userdata['PlayCount']
        # Sometimes, Plex tells us resume points in milliseconds and
        # not in seconds - thank you very much!
        if message['viewOffset'] > session['duration']:
            resume = message['viewOffset'] / 1000
        else:
            resume = message['viewOffset']
        if resume < v.IGNORE_SECONDS_AT_START:
            continue
        try:
            completed = float(resume) / float(session['duration'])
        except (ZeroDivisionError, TypeError):
            LOG.error('Could not mark playstate for %s and session %s',
                      data, session)
            continue
        if completed >= v.MARK_PLAYED_AT:
            # Only mark completely watched ONCE
            if session.get('marked_played') is None:
                session['marked_played'] = True
                mark_played = True
            else:
                # Don't mark it as completely watched again
                continue
        else:
            mark_played = False
        LOG.debug('Update playstate for user %s for %s with plex id %s to '
                  'viewCount %s, resume %s, mark_played %s',
                  app.ACCOUNT.plex_username, session['kodi_type'], plex_id,
                  session['viewCount'], resume, mark_played)
        func = itemtypes.ITEMTYPE_FROM_KODITYPE[session['kodi_type']]
        with func(None) as fkt:
            fkt.update_playstate(mark_played,
                                 session['viewCount'],
                                 resume,
                                 session['duration'],
                                 session['file_id'],
                                 timing.unix_timestamp(),
                                 v.PLEX_TYPE_FROM_KODI_TYPE[session['kodi_type']])


def cache_artwork(plex_id, plex_type, kodi_id=None, kodi_type=None):
    """
    Triggers caching of artwork (if so enabled in the PKC settings)
    """
    if not CACHING_ENALBED:
        return
    if not kodi_id:
        with PlexDB() as plexdb:
            item = plexdb.item_by_id(plex_id, plex_type)
        if not item:
            LOG.error('Could not retrieve Plex db info for %s', plex_id)
            return
        kodi_id, kodi_type = item['kodi_id'], item['kodi_type']
    with kodi_db.KODIDB_FROM_PLEXTYPE[plex_type]() as kodidb:
        for url in kodidb.art_urls(kodi_id, kodi_type):
            artwork.cache_url(url)

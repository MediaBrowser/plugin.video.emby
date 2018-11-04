#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import ItemBase, process_path
from ..plex_api import API
from .. import plex_functions as PF, state, variables as v

LOG = getLogger('PLEX.tvshows')


class TvShowMixin(object):
    def remove(self, plex_id, plex_type=None):
        """
        Remove the entire TV shows object (show, season or episode) including
        all associated entries from the Kodi DB.
        """
        db_item = self.plexdb.item_by_id(plex_id, plex_type)
        if not db_item:
            LOG.debug('Cannot delete plex_id %s - not found in DB', plex_id)
            return
        LOG.debug('Removing %s %s with kodi_id: %s',
                  db_item['plex_type'], plex_id, db_item['kodi_id'])

        # Remove the plex reference
        self.plexdb.remove(plex_id, db_item['plex_type'])

        # EPISODE #####
        if db_item['plex_type'] == v.PLEX_TYPE_EPISODE:
            # Delete episode, verify season and tvshow
            self.remove_episode(db_item['kodi_id'], db_item['kodi_fileid'])
            # Season verification
            if not self.plexdb.season_has_episodes(db_item['season_id']):
                # No episode left for this season - so delete the season
                self.remove_season(db_item['parent_id'])
                self.plexdb.remove(db_item['season_id'], v.PLEX_TYPE_SEASON)
            # Show verification
            if (not self.plexdb.show_has_seasons(db_item['show_id']) and
                    not self.plexdb.show_has_episodes(db_item['show_id'])):
                # No seasons for show left - so delete entire show
                self.remove_show(db_item['grandparent_id'])
                self.plexdb.remove(db_item['show_id'], v.PLEX_TYPE_SHOW)
        # SEASON #####
        elif db_item['plex_type'] == v.PLEX_TYPE_SEASON:
            # Remove episodes, season, verify tvshow
            for episode in self.plexdb.episode_by_season(db_item['plex_id']):
                self.remove_episode(episode['kodi_id'], episode['kodi_fileid'])
                self.plexdb.remove(episode['plex_id'], v.PLEX_TYPE_EPISODE)
            # Remove season
            self.remove_season(db_item['kodi_id'])
            # Show verification
            if (not self.plexdb.show_has_seasons(db_item['show_id']) and
                    not self.plexdb.show_has_episodes(db_item['show_id'])):
                # There's no other season or episode left, delete the show
                self.remove_show(db_item['parent_id'])
                self.plexdb.remove(db_item['show_id'], v.KODI_TYPE_SHOW)
        # TVSHOW #####
        elif db_item['plex_type'] == v.PLEX_TYPE_SHOW:
            # Remove episodes, seasons and the tvshow itself
            for episode in self.plexdb.episode_by_show(db_item['plex_id']):
                self.remove_episode(episode['kodi_id'],
                                    episode['kodi_fileid'])
                self.plexdb.remove(episode['plex_id'], v.PLEX_TYPE_EPISODE)
            for season in self.plexdb.season_by_show(db_item['plex_id']):
                self.remove_season(season['kodi_id'])
                self.plexdb.remove(season['plex_id'], v.PLEX_TYPE_SEASON)
            self.remove_show(db_item['kodi_id'])

        LOG.debug('Deleted %s %s from all databases',
                  db_item['plex_type'], db_item['plex_id'])

    def remove_show(self, kodi_id):
        """
        Remove a TV show, and only the show, no seasons or episodes
        """
        self.kodi_db.modify_genres(kodi_id, v.KODI_TYPE_SHOW)
        self.kodi_db.modify_studios(kodi_id, v.KODI_TYPE_SHOW)
        self.kodi_db.modify_tags(kodi_id, v.KODI_TYPE_SHOW)
        self.artwork.delete_artwork(kodi_id,
                                    v.KODI_TYPE_SHOW,
                                    self.kodicursor)
        self.kodicursor.execute("DELETE FROM tvshow WHERE idShow = ?",
                                (kodi_id,))
        if v.KODIVERSION >= 17:
            self.kodi_db.remove_uniqueid(kodi_id, v.KODI_TYPE_SHOW)
            self.kodi_db.remove_ratings(kodi_id, v.KODI_TYPE_SHOW)
        LOG.debug("Removed tvshow: %s", kodi_id)

    def remove_season(self, kodi_id):
        """
        Remove a season, and only a season, not the show or episodes
        """
        self.artwork.delete_artwork(kodi_id,
                                    v.KODI_TYPE_SEASON,
                                    self.kodicursor)
        self.kodicursor.execute("DELETE FROM seasons WHERE idSeason = ?",
                                (kodi_id,))
        LOG.debug("Removed season: %s", kodi_id)

    def remove_episode(self, kodi_id, file_id):
        """
        Remove an episode, and episode only from the Kodi DB (not Plex DB)
        """
        self.kodi_db.modify_people(kodi_id, v.KODI_TYPE_EPISODE)
        self.kodi_db.remove_file(file_id, plex_type=v.PLEX_TYPE_EPISODE)
        self.artwork.delete_artwork(kodi_id,
                                    v.KODI_TYPE_EPISODE,
                                    self.kodicursor)
        self.kodicursor.execute("DELETE FROM episode WHERE idEpisode = ?",
                                (kodi_id,))
        if v.KODIVERSION >= 17:
            self.kodi_db.remove_uniqueid(kodi_id, v.KODI_TYPE_EPISODE)
            self.kodi_db.remove_ratings(kodi_id, v.KODI_TYPE_EPISODE)
        LOG.debug("Removed episode: %s", kodi_id)


class Show(ItemBase, TvShowMixin):
    """
    For Plex library-type TV shows
    """
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None):
        """
        Process a single show
        """
        api = API(xml)
        plex_id = api.plex_id()
        LOG.debug('Adding show with plex_id %s', plex_id)
        if not plex_id:
            LOG.error("Cannot parse XML data for TV show: %s", xml.attrib)
            return
        show = self.plexdb.show(plex_id)
        if not show:
            update_item = False
            query = 'SELECT COALESCE(MAX(idShow), 0) FROM tvshow'
            self.kodicursor.execute(query)
            kodi_id = self.kodicursor.fetchone()[0] + 1
        else:
            update_item = True
            kodi_id = show['kodi_id']
            kodi_pathid = show['kodi_pathid']
            # Verification the item is still in Kodi
            self.kodicursor.execute('SELECT * FROM tvshow WHERE idShow = ?',
                                    (kodi_id,))
            try:
                self.kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                LOG.info("idShow: %s missing from Kodi, repairing the entry.",
                         kodi_id)

        genres = api.genre_list()
        genre = api.list_to_string(genres)
        studios = api.music_studio_list()
        studio = api.list_to_string(studios)

        # GET THE FILE AND PATH #####
        if state.DIRECT_PATHS:
            # Direct paths is set the Kodi way
            playurl = api.validate_playurl(api.tv_show_path(),
                                           api.plex_type(),
                                           folder=True)
            if playurl is None:
                return
            path, toplevelpath = process_path(playurl)
            toppathid = self.kodi_db.add_video_path(
                toplevelpath,
                content='tvshows',
                scraper='metadata.local')
        else:
            # Set plugin path
            toplevelpath = "plugin://%s.tvshows/" % v.ADDON_ID
            path = "%s%s/" % (toplevelpath, plex_id)
            # Do NOT set a parent id because addon-path cannot be "stacked"
            toppathid = None

        kodi_pathid = self.kodi_db.add_video_path(path,
                                                  date_added=api.date_created(),
                                                  id_parent_path=toppathid)
        # UPDATE THE TVSHOW #####
        if update_item:
            LOG.info("UPDATE tvshow plex_id: %s - Title: %s",
                     plex_id, api.title())
            # update new ratings Kodi 17
            rating_id = self.kodi_db.get_ratingid(kodi_id, v.KODI_TYPE_SHOW)
            self.kodi_db.update_ratings(kodi_id,
                                        v.KODI_TYPE_SHOW,
                                        "default",
                                        api.audience_rating(),
                                        api.votecount(),
                                        rating_id)
            # update new uniqueid Kodi 17
            if api.provider('tvdb') is not None:
                uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                     v.KODI_TYPE_SHOW)
                self.kodi_db.update_uniqueid(kodi_id,
                                             v.KODI_TYPE_SHOW,
                                             api.provider('tvdb'),
                                             "unknown",
                                             uniqueid)
            else:
                self.kodi_db.remove_uniqueid(kodi_id, v.KODI_TYPE_SHOW)
                uniqueid = -1
            # Update the tvshow entry
            query = '''
                UPDATE tvshow
                SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?,
                    c12 = ?, c13 = ?, c14 = ?, c15 = ?
                WHERE idShow = ?
            '''
            self.kodicursor.execute(
                query, (api.title(), api.plot(), rating_id,
                        api.premiere_date(), genre, api.title(), uniqueid,
                        api.content_rating(), studio, api.sorttitle(),
                        kodi_id))
        # OR ADD THE TVSHOW #####
        else:
            LOG.info("ADD tvshow plex_id: %s - Title: %s",
                     plex_id, api.title())
            # Link the path
            query = "INSERT INTO tvshowlinkpath(idShow, idPath) values (?, ?)"
            self.kodicursor.execute(query, (kodi_id, kodi_pathid))
            rating_id = self.kodi_db.get_ratingid(kodi_id, v.KODI_TYPE_SHOW)
            self.kodi_db.add_ratings(rating_id,
                                     kodi_id,
                                     v.KODI_TYPE_SHOW,
                                     "default",
                                     api.audience_rating(),
                                     api.votecount())
            if api.provider('tvdb') is not None:
                uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                     v.KODI_TYPE_SHOW)
                self.kodi_db.add_uniqueid(uniqueid,
                                          kodi_id,
                                          v.KODI_TYPE_SHOW,
                                          api.provider('tvdb'),
                                          "unknown")
            else:
                uniqueid = -1
            # Create the tvshow entry
            query = '''
                INSERT INTO tvshow(
                    idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14,
                    c15)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            self.kodicursor.execute(
                query, (kodi_id, api.title(), api.plot(), rating_id,
                        api.premiere_date(), genre, api.title(), uniqueid,
                        api.content_rating(), studio, api.sorttitle()))

        self.kodi_db.modify_people(kodi_id,
                                   v.KODI_TYPE_SHOW,
                                   api.people_list())
        self.kodi_db.modify_genres(kodi_id, v.KODI_TYPE_SHOW, genres)
        self.artwork.modify_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_SHOW,
                                    self.kodicursor)
        # Process studios
        self.kodi_db.modify_studios(kodi_id, v.KODI_TYPE_SHOW, studios)
        # Process tags: view, PMS collection tags
        tags = [section_name]
        tags.extend([i for _, i in api.collection_list()])
        self.kodi_db.modify_tags(kodi_id, v.KODI_TYPE_SHOW, tags)
        self.plexdb.add_show(plex_id=plex_id,
                             checksum=api.checksum(),
                             section_id=section_id,
                             kodi_id=kodi_id,
                             kodi_pathid=kodi_pathid,
                             last_sync=self.last_sync)


class Season(ItemBase, TvShowMixin):
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None):
        """
        Process a single season of a certain tv show
        """
        api = API(xml)
        plex_id = api.plex_id()
        LOG.debug('Adding season with plex_id %s', plex_id)
        if not plex_id:
            LOG.error('Error getting plex_id for season, skipping: %s',
                      xml.attrib)
            return
        show_id = api.parent_plex_id()
        show = self.plexdb.show(show_id)
        if not show:
            LOG.warn('Parent TV show %s not found in DB, adding it', show_id)
            show_xml = PF.GetPlexMetadata(show_id)
            try:
                show_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error("Parent tvshow %s xml download failed", show_id)
                return False
            Show(self.last_sync, plexdb=self.plexdb, kodi_db=self.kodi_db).add_update(
                show_xml[0], section_name, section_id)
            show = self.plexdb.show(show_id)
            if not show:
                LOG.error('Still could not find parent tv show %s', show_id)
                return
        parent_id = show['kodi_id']
        kodi_id = self.kodi_db.add_season(parent_id, api.season_number())
        self.artwork.modify_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_SEASON,
                                    self.kodicursor)
        self.plexdb.add_season(plex_id=plex_id,
                               checksum=api.checksum(),
                               section_id=section_id,
                               show_id=show_id,
                               parent_id=parent_id,
                               kodi_id=kodi_id,
                               last_sync=self.last_sync)


class Episode(ItemBase, TvShowMixin):
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None):
        """
        Process single episode
        """
        api = API(xml)
        plex_id = api.plex_id()
        LOG.debug('Adding episode with plex_id %s', plex_id)
        if not plex_id:
            LOG.error('Error getting plex_id for episode, skipping: %s',
                      xml.attrib)
            return
        episode = self.plexdb.episode(plex_id)
        if not episode:
            update_item = False
            query = 'SELECT COALESCE(MAX(idEpisode), 0) FROM episode'
            self.kodicursor.execute(query)
            kodi_id = self.kodicursor.fetchone()[0] + 1
        else:
            update_item = True
            kodi_id = episode['kodi_id']
            old_kodi_fileid = episode['kodi_fileid']
            kodi_pathid = episode['kodi_pathid']
            # Verification the item is still in Kodi
            query = 'SELECT * FROM episode WHERE idEpisode = ? LIMIT 1'
            self.kodicursor.execute(query, (kodi_id, ))
            try:
                self.kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                LOG.info('idEpisode %s missing from Kodi, repairing entry.',
                         kodi_id)

        peoples = api.people()
        director = api.list_to_string(peoples['Director'])
        writer = api.list_to_string(peoples['Writer'])
        userdata = api.userdata()
        show_id, season_id, _, season_no, episode_no = api.episode_data()

        if season_no is None:
            season_no = -1
        if episode_no is None:
            episode_no = -1
        airs_before_season = "-1"
        airs_before_episode = "-1"

        # The grandparent TV show
        show = self.plexdb.show(show_id)
        if not show:
            LOG.warn('Grandparent TV show %s not found in DB, adding it', show_id)
            show_xml = PF.GetPlexMetadata(show_id)
            try:
                show_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error("Grandparent tvshow %s xml download failed", show_id)
                return False
            Show(self.last_sync, plexdb=self.plexdb, kodi_db=self.kodi_db).add_update(
                show_xml[0], section_name, section_id)
            show = self.plexdb.show(show_id)
            if not show:
                LOG.error('Still could not find grandparent tv show %s', show_id)
                return
        grandparent_id = show['kodi_id']

        # The parent Season
        season = self.plexdb.season(season_id)
        if not season:
            LOG.warn('Parent season %s not found in DB, adding it', season_id)
            season_xml = PF.GetPlexMetadata(season_id)
            try:
                season_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error("Parent season %s xml download failed", season_id)
                return False
            Season(self.last_sync, plexdb=self.plexdb, kodi_db=self.kodi_db).add_update(
                season_xml[0], section_name, section_id)
            season = self.plexdb.season(season_id)
            if not season:
                LOG.error('Still could not find parent season %s', season_id)
                return
        parent_id = season['kodi_id']

        # GET THE FILE AND PATH #####
        do_indirect = not state.DIRECT_PATHS
        if state.DIRECT_PATHS:
            playurl = api.file_path(force_first_media=True)
            if playurl is None:
                do_indirect = True
            else:
                playurl = api.validate_playurl(playurl, v.PLEX_TYPE_EPISODE)
                if "\\" in playurl:
                    # Local path
                    filename = playurl.rsplit("\\", 1)[1]
                else:
                    # Network share
                    filename = playurl.rsplit("/", 1)[1]
                path = playurl.replace(filename, "")
                parent_path_id = self.kodi_db.parent_path_id(path)
                kodi_pathid = self.kodi_db.add_video_path(
                    path, id_parent_path=parent_path_id)
        if do_indirect:
            # Set plugin path - do NOT use "intermediate" paths for the show
            # as with direct paths!
            filename = api.file_name(force_first_media=True)
            path = 'plugin://%s.tvshows/%s/' % (v.ADDON_ID, show_id)
            filename = ('%s?plex_id=%s&plex_type=%s&mode=play&filename=%s'
                        % (path, plex_id, v.PLEX_TYPE_EPISODE, filename))
            playurl = filename
            # Root path tvshows/ already saved in Kodi DB
            kodi_pathid = self.kodi_db.add_video_path(path)

        # add/retrieve kodi_pathid and fileid
        # if the path or file already exists, the calls return current value
        kodi_fileid = self.kodi_db.add_file(filename,
                                            kodi_pathid,
                                            api.date_created())

        # UPDATE THE EPISODE #####
        if update_item:
            LOG.info("UPDATE episode plex_id: %s, Title: %s",
                     plex_id, api.title())
            if kodi_fileid != old_kodi_fileid:
                self.kodi_db.remove_file(old_kodi_fileid)
            ratingid = self.kodi_db.get_ratingid(kodi_id,
                                                 v.KODI_TYPE_EPISODE)
            self.kodi_db.update_ratings(kodi_id,
                                        v.KODI_TYPE_EPISODE,
                                        "default",
                                        userdata['Rating'],
                                        api.votecount(),
                                        ratingid)
            # update new uniqueid Kodi 17
            uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                 v.KODI_TYPE_EPISODE)
            self.kodi_db.update_uniqueid(kodi_id,
                                         v.KODI_TYPE_EPISODE,
                                         api.provider('tvdb'),
                                         "tvdb",
                                         uniqueid)
            query = '''
                UPDATE episode
                SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?,
                    c10 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?,
                    c18 = ?, c19 = ?, idFile=?, idSeason = ?,
                    userrating = ?
                WHERE idEpisode = ?
            '''
            self.kodicursor.execute(
                query, (api.title(), api.plot(), ratingid, writer,
                        api.premiere_date(), api.runtime(), director, season_no,
                        episode_no, api.title(), airs_before_season,
                        airs_before_episode, playurl, kodi_pathid, kodi_fileid,
                        parent_id, userdata['UserRating'], kodi_id))

        # OR ADD THE EPISODE #####
        else:
            LOG.info("ADD episode plex_id: %s - Title: %s",
                     plex_id, api.title())
            # Create the episode entry
            rating_id = self.kodi_db.get_ratingid(kodi_id,
                                                  v.KODI_TYPE_EPISODE)
            self.kodi_db.add_ratings(rating_id,
                                     kodi_id,
                                     v.KODI_TYPE_EPISODE,
                                     "default",
                                     userdata['Rating'],
                                     api.votecount())
            # add new uniqueid Kodi 17
            uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                 v.KODI_TYPE_EPISODE)
            self.kodi_db.add_uniqueid(uniqueid,
                                      kodi_id,
                                      v.KODI_TYPE_EPISODE,
                                      api.provider('tvdb'),
                                      "tvdb")
            query = '''
                INSERT INTO episode( idEpisode, idFile, c00, c01, c03, c04,
                    c05, c09, c10, c12, c13, c14, idShow, c15, c16, c18,
                    c19, idSeason, userrating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?)
            '''
            self.kodicursor.execute(
                query, (kodi_id, kodi_fileid, api.title(), api.plot(), rating_id,
                        writer, api.premiere_date(), api.runtime(), director,
                        season_no, episode_no, api.title(), grandparent_id,
                        airs_before_season, airs_before_episode, playurl,
                        kodi_pathid, parent_id, userdata['UserRating']))

        self.kodi_db.modify_people(kodi_id,
                                   v.KODI_TYPE_EPISODE,
                                   api.people_list())
        self.artwork.modify_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_EPISODE,
                                    self.kodicursor)
        streams = api.mediastreams()
        self.kodi_db.modify_streams(kodi_fileid, streams, api.runtime())
        self.kodi_db.set_resume(kodi_fileid,
                                api.resume_point(),
                                api.runtime(),
                                userdata['PlayCount'],
                                userdata['LastPlayedDate'],
                                None)  # Do send None, we check here
        if not state.DIRECT_PATHS:
            # need to set a SECOND file entry for a path without plex show id
            filename = api.file_name(force_first_media=True)
            path = 'plugin://%s.tvshows/' % v.ADDON_ID
            # Filename is exactly the same, WITH plex show id!
            filename = ('%s%s/?plex_id=%s&plex_type=%s&mode=play&filename=%s'
                        % (path, show_id, plex_id, v.PLEX_TYPE_EPISODE,
                           filename))
            kodi_pathid = self.kodi_db.add_video_path(path)
            kodi_fileid = self.kodi_db.add_file(filename,
                                                kodi_pathid,
                                                api.date_created())
            self.kodi_db.set_resume(kodi_fileid,
                                    api.resume_point(),
                                    api.runtime(),
                                    userdata['PlayCount'],
                                    userdata['LastPlayedDate'],
                                    None)  # Do send None - 2nd entry
            self.plexdb.add_episode(plex_id=plex_id,
                                    checksum=api.checksum(),
                                    section_id=section_id,
                                    show_id=show_id,
                                    grandparent_id=grandparent_id,
                                    season_id=season_id,
                                    parent_id=parent_id,
                                    kodi_id=kodi_id,
                                    kodi_fileid=kodi_fileid,
                                    kodi_pathid=kodi_pathid,
                                    last_sync=self.last_sync)

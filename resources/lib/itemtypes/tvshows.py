#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import ItemBase, process_path
from ..plex_api import API
from .. import state, variables as v

LOG = getLogger('PLEX.tvshows')


class TvShowMixin(object):
    def remove(self, plex_id, plex_type=None):
        """
        Remove the entire TV shows object (show, season or episode) including
        all associated entries from the Kodi DB.
        """
        if plex_type is None:
            entry = self.plex_db.episode(plex_id)
            kodi_type = v.KODI_TYPE_EPISODE
            if not entry:
                entry = self.plex_db.season(plex_id)
                kodi_type = v.KODI_TYPE_SEASON
                if not entry:
                    entry = self.plex_db.show(plex_id)
                    kodi_type = v.KODI_TYPE_SHOW
        else:
            pass
        if not entry:
            LOG.debug('Cannot delete plex_id %s - not found in DB', plex_id)
            return
        kodi_id = entry[0]
        file_id = entry[1]
        parent_id = entry[3]
        kodi_type = entry[4]
        LOG.debug("Removing %s with kodi_id: %s file_id: %s parent_id: %s",
                  kodi_type, kodi_id, file_id, parent_id)

        # Remove the plex reference
        self.plex_db.removeItem(plex_id)

        # EPISODE #####
        if kodi_type == v.KODI_TYPE_EPISODE:
            # Delete episode, verify season and tvshow
            self.remove_episode(kodi_id, file_id)
            # Season verification
            season = self.plex_db.getItem_byKodiId(parent_id,
                                                   v.KODI_TYPE_SEASON)
            if season is not None:
                if not self.plex_db.getItem_byParentId(parent_id,
                                                       v.KODI_TYPE_EPISODE):
                    # No episode left for season - so delete the season
                    self.remove_season(parent_id)
                    self.plex_db.removeItem(season[0])
                show = self.plex_db.getItem_byKodiId(season[1],
                                                     v.KODI_TYPE_SHOW)
                if show is not None:
                    if not self.plex_db.getItem_byParentId(season[1],
                                                           v.KODI_TYPE_SEASON):
                        # No seasons for show left - so delete entire show
                        self.remove_show(season[1])
                        self.plex_db.removeItem(show[0])
                else:
                    LOG.error('No show found in Plex DB for season %s', season)
            else:
                LOG.error('No season found in Plex DB!')
        # SEASON #####
        elif kodi_type == v.KODI_TYPE_SEASON:
            # Remove episodes, season, verify tvshow
            for episode in self.plex_db.getItem_byParentId(
                    kodi_id, v.KODI_TYPE_EPISODE):
                self.remove_episode(episode[1], episode[2])
                self.plex_db.removeItem(episode[0])
            # Remove season
            self.remove_season(kodi_id)
            # Show verification
            if not self.plex_db.getItem_byParentId(parent_id,
                                                   v.KODI_TYPE_SEASON):
                # There's no other season left, delete the show
                self.remove_show(parent_id)
                self.plex_db.removeItem_byKodiId(parent_id, v.KODI_TYPE_SHOW)
        # TVSHOW #####
        elif kodi_type == v.KODI_TYPE_SHOW:
            # Remove episodes, seasons and the tvshow itself
            for season in self.plex_db.getItem_byParentId(kodi_id,
                                                          v.KODI_TYPE_SEASON):
                for episode in self.plex_db.getItem_byParentId(
                        season[1], v.KODI_TYPE_EPISODE):
                    self.remove_episode(episode[1], episode[2])
                    self.plex_db.removeItem(episode[0])
                self.remove_season(season[1])
                self.plex_db.removeItem(season[0])
            self.remove_show(kodi_id)

        LOG.debug("Deleted %s %s from Kodi database", kodi_type, plex_id)

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
        update_item = True
        plex_id = api.plex_id()
        LOG.debug('Adding show with plex_id %s', plex_id)
        if not plex_id:
            LOG.error("Cannot parse XML data for TV show: %s", xml.attrib)
            return
        show = self.plex_db.show(plex_id)
        try:
            kodi_id = show[3]
            kodi_pathid = show[4]
        except TypeError:
            update_item = False
            query = 'SELECT COALESCE(MAX(idShow), 0) FROM tvshow'
            self.kodicursor.execute(query)
            kodi_id = self.kodicursor.fetchone()[0] + 1
        else:
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
        self.plex_db.add_show(plex_id=plex_id,
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
        show = self.plex_db.show(show_id)
        try:
            parent_id = show[3]
        except TypeError:
            LOG.error('Could not find parent tv show for season %s. '
                      'Skipping season for now.', plex_id)
            return
        kodi_id = self.kodi_db.add_season(parent_id, api.season_number())
        self.artwork.modify_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_SEASON,
                                    self.kodicursor)
        self.plex_db.add_season(plex_id=plex_id,
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
        update_item = True
        plex_id = api.plex_id()
        LOG.debug('Adding episode with plex_id %s', plex_id)
        if not plex_id:
            LOG.error('Error getting plex_id for episode, skipping: %s',
                      xml.attrib)
            return
        entry = self.plex_db.item_by_id(plex_id)
        try:
            kodi_id = entry[0]
            old_kodi_fileid = entry[1]
            kodi_pathid = entry[2]
        except TypeError:
            update_item = False
            query = 'SELECT COALESCE(MAX(idEpisode), 0) FROM episode'
            self.kodicursor.execute(query)
            kodi_id = self.kodicursor.fetchone()[0] + 1
        else:
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

        show = self.plex_db.show(show_id)
        try:
            grandparent_id = show[3]
        except TypeError:
            LOG.error("Parent tvshow now found, skip item")
            return False
        parent_id = self.kodi_db.add_season(grandparent_id, season_no)

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
            self.plex_db.add_episode(plex_id=plex_id,
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

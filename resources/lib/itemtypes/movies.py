#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import ItemBase
from ..plex_api import API
from .. import state, variables as v, plex_functions as PF

LOG = getLogger('PLEX.movies')


class Movie(ItemBase):
    """
    Used for plex library-type movies
    """
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None):
        """
        Process single movie
        """
        api = API(xml)
        update_item = True
        plex_id = api.plex_id()
        # Cannot parse XML, abort
        if not plex_id:
            LOG.error('Cannot parse XML data for movie: %s', xml.attrib)
            return
        movie = self.plexdb.movie(plex_id)
        try:
            kodi_id = movie['kodi_id']
            old_kodi_fileid = movie['kodi_fileid']
            kodi_pathid = movie['kodi_pathid']
        except TypeError:
            update_item = False
            self.kodicursor.execute('SELECT COALESCE(MAX(idMovie), 0) FROM movie')
            kodi_id = self.kodicursor.fetchone()[0] + 1
        else:
            # Verification the item is still in Kodi
            self.kodicursor.execute('SELECT idMovie FROM movie WHERE idMovie = ? LIMIT 1',
                                    (kodi_id, ))
            try:
                self.kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                LOG.info("kodi_id: %s missing from Kodi, repairing the entry.",
                         kodi_id)

        userdata = api.userdata()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = userdata['Resume']
        runtime = userdata['Runtime']
        rating = userdata['Rating']

        title = api.title()
        people = api.people()
        genres = api.genre_list()
        collections = api.collection_list()
        countries = api.country_list()
        studios = api.music_studio_list()

        # GET THE FILE AND PATH #####
        do_indirect = not state.DIRECT_PATHS
        if state.DIRECT_PATHS:
            # Direct paths is set the Kodi way
            playurl = api.file_path(force_first_media=True)
            if playurl is None:
                # Something went wrong, trying to use non-direct paths
                do_indirect = True
            else:
                playurl = api.validate_playurl(playurl, api.plex_type())
                if playurl is None:
                    return False
                if '\\' in playurl:
                    # Local path
                    filename = playurl.rsplit("\\", 1)[1]
                else:
                    # Network share
                    filename = playurl.rsplit("/", 1)[1]
                path = playurl.replace(filename, "")
                kodi_pathid = self.kodi_db.add_video_path(path,
                                                          content='movies',
                                                          scraper='metadata.local')
        if do_indirect:
            # Set plugin path and media flags using real filename
            filename = api.file_name(force_first_media=True)
            path = 'plugin://%s.movies/' % v.ADDON_ID
            filename = ('%s?plex_id=%s&plex_type=%s&mode=play&filename=%s'
                        % (path, plex_id, v.PLEX_TYPE_MOVIE, filename))
            playurl = filename
            kodi_pathid = self.kodi_db.get_path(path)

        file_id = self.kodi_db.add_file(filename,
                                        kodi_pathid,
                                        api.date_created())

        if update_item:
            LOG.info('UPDATE movie plex_id: %s - %s', plex_id, api.title())
            if file_id != old_kodi_fileid:
                self.kodi_db.remove_file(old_kodi_fileid)
            rating_id = self.kodi_db.get_ratingid(kodi_id,
                                                  v.KODI_TYPE_MOVIE)
            self.kodi_db.update_ratings(kodi_id,
                                        v.KODI_TYPE_MOVIE,
                                        "default",
                                        rating,
                                        api.votecount(),
                                        rating_id)
            # update new uniqueid Kodi 17
            if api.provider('imdb') is not None:
                uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                     v.KODI_TYPE_MOVIE)
                self.kodi_db.update_uniqueid(kodi_id,
                                             v.KODI_TYPE_MOVIE,
                                             api.provider('imdb'),
                                             "imdb",
                                             uniqueid)
            else:
                self.kodi_db.remove_uniqueid(kodi_id, v.KODI_TYPE_MOVIE)
                uniqueid = -1
        else:
            LOG.info("ADD movie plex_id: %s - %s", plex_id, title)
            rating_id = self.kodi_db.get_ratingid(kodi_id,
                                                  v.KODI_TYPE_MOVIE)
            self.kodi_db.add_ratings(rating_id,
                                     kodi_id,
                                     v.KODI_TYPE_MOVIE,
                                     "default",
                                     rating,
                                     api.votecount())
            if api.provider('imdb') is not None:
                uniqueid = self.kodi_db.get_uniqueid(kodi_id,
                                                     v.KODI_TYPE_MOVIE)
                self.kodi_db.add_uniqueid(uniqueid,
                                          kodi_id,
                                          v.KODI_TYPE_MOVIE,
                                          api.provider('imdb'),
                                          "imdb")
            else:
                uniqueid = -1

        # Update Kodi's main entry
        query = '''
            INSERT OR REPLACE INTO movie(idMovie, idFile, c00, c01, c02, c03,
                c04, c05, c06, c07, c09, c10, c11, c12, c14, c15, c16,
                c18, c19, c21, c22, c23, premiered, userrating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?)
        '''
        self.kodicursor.execute(
            query,
            (kodi_id, file_id, title, api.plot(), api.shortplot(),
             api.tagline(), api.votecount(), rating_id,
             api.list_to_string(people['Writer']), api.year(),
             uniqueid, api.sorttitle(), runtime, api.content_rating(),
             api.list_to_string(genres), api.list_to_string(people['Director']),
             title, api.list_to_string(studios), api.trailer(),
             api.list_to_string(countries), playurl, kodi_pathid,
             api.premiere_date(), userdata['UserRating']))

        self.kodi_db.modify_countries(kodi_id, v.KODI_TYPE_MOVIE, countries)
        self.kodi_db.modify_people(kodi_id,
                                   v.KODI_TYPE_MOVIE,
                                   api.people_list())
        self.kodi_db.modify_genres(kodi_id, v.KODI_TYPE_MOVIE, genres)
        self.artwork.modify_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_MOVIE,
                                    self.kodicursor)
        self.kodi_db.modify_streams(file_id, api.mediastreams(), runtime)
        self.kodi_db.modify_studios(kodi_id, v.KODI_TYPE_MOVIE, studios)
        tags = [section_name]
        if collections:
            collections_match = api.collections_match()
            for plex_set_id, set_name in collections:
                tags.append(set_name)
                # Add any sets from Plex collection tags
                kodi_set_id = self.kodi_db.create_collection(set_name)
                self.kodi_db.assign_collection(kodi_set_id, kodi_id)
                for index, plex_id in collections_match:
                    # Get Plex artwork for collections - a pain
                    if index == plex_set_id:
                        set_xml = PF.GetPlexMetadata(plex_id)
                        try:
                            set_xml.attrib
                        except AttributeError:
                            LOG.error('Could not get set metadata %s', plex_id)
                            continue
                        set_api = API(set_xml[0])
                        self.artwork.modify_artwork(set_api.artwork(),
                                                    kodi_set_id,
                                                    v.KODI_TYPE_SET,
                                                    self.kodicursor)
                        break
        self.kodi_db.modify_tags(kodi_id, v.KODI_TYPE_MOVIE, tags)
        # Process playstate
        self.kodi_db.set_resume(file_id,
                                resume,
                                runtime,
                                playcount,
                                dateplayed,
                                v.PLEX_TYPE_MOVIE)
        self.plexdb.add_movie(plex_id=plex_id,
                              checksum=api.checksum(),
                              section_id=section_id,
                              kodi_id=kodi_id,
                              kodi_fileid=file_id,
                              kodi_pathid=kodi_pathid,
                              last_sync=self.last_sync)

        def remove(self, plex_id, plex_type=None):
            """
            Remove a movie with all references and all orphaned associated entries
            from the Kodi DB
            """
            movie = self.plexdb.movie(plex_id)
            try:
                kodi_id = movie[3]
                file_id = movie[4]
                kodi_type = v.KODI_TYPE_MOVIE
                LOG.debug('Removing movie with plex_id %s, kodi_id: %s',
                          plex_id, kodi_id)
            except TypeError:
                LOG.error('Movie with plex_id %s not found - cannot delete',
                          plex_id)
                return
            # Remove the plex reference
            self.plexdb.remove(plex_id, v.PLEX_TYPE_MOVIE)
            # Remove artwork
            self.artwork.delete_artwork(kodi_id, kodi_type, self.self.kodicursor)
            set_id = self.kodi_db.get_set_id(kodi_id)
            self.kodi_db.modify_countries(kodi_id, kodi_type)
            self.kodi_db.modify_people(kodi_id, kodi_type)
            self.kodi_db.modify_genres(kodi_id, kodi_type)
            self.kodi_db.modify_studios(kodi_id, kodi_type)
            self.kodi_db.modify_tags(kodi_id, kodi_type)
            # Delete kodi movie and file
            self.kodi_db.remove_file(file_id)
            self.self.kodicursor.execute('DELETE FROM movie WHERE idMovie = ?',
                                         (kodi_id,))
            if set_id:
                self.kodi_db.delete_possibly_empty_set(set_id)
            self.kodi_db.remove_uniqueid(kodi_id, kodi_type)
            self.kodi_db.remove_ratings(kodi_id, kodi_type)
            LOG.debug('Deleted movie %s from kodi database', plex_id)

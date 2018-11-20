#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import ItemBase
from ..plex_api import API
from .. import app, variables as v, plex_functions as PF

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
        plex_id = api.plex_id()
        # Cannot parse XML, abort
        if not plex_id:
            LOG.error('Cannot parse XML data for movie: %s', xml.attrib)
            return
        movie = self.plexdb.movie(plex_id)
        if movie:
            update_item = True
            kodi_id = movie['kodi_id']
            old_kodi_fileid = movie['kodi_fileid']
            kodi_pathid = movie['kodi_pathid']
        else:
            update_item = False
            kodi_id = self.kodidb.new_movie_id()

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
        do_indirect = not app.SYNC.direct_paths
        if app.SYNC.direct_paths:
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
                kodi_pathid = self.kodidb.add_path(path,
                                                   content='movies',
                                                   scraper='metadata.local')
        if do_indirect:
            # Set plugin path and media flags using real filename
            filename = api.file_name(force_first_media=True)
            path = 'plugin://%s.movies/' % v.ADDON_ID
            filename = ('%s?plex_id=%s&plex_type=%s&mode=play&filename=%s'
                        % (path, plex_id, v.PLEX_TYPE_MOVIE, filename))
            playurl = filename
            kodi_pathid = self.kodidb.get_path(path)

        if update_item:
            LOG.info('UPDATE movie plex_id: %s - %s', plex_id, api.title())
            file_id = self.kodidb.modify_file(filename,
                                              kodi_pathid,
                                              api.date_created())
            if file_id != old_kodi_fileid:
                self.kodidb.remove_file(old_kodi_fileid)
            rating_id = self.kodidb.get_ratingid(kodi_id,
                                                 v.KODI_TYPE_MOVIE)
            self.kodidb.update_ratings(kodi_id,
                                       v.KODI_TYPE_MOVIE,
                                       "default",
                                       rating,
                                       api.votecount(),
                                       rating_id)
            # update new uniqueid Kodi 17
            if api.provider('imdb') is not None:
                uniqueid = self.kodidb.get_uniqueid(kodi_id,
                                                    v.KODI_TYPE_MOVIE)
                self.kodidb.update_uniqueid(kodi_id,
                                            v.KODI_TYPE_MOVIE,
                                            api.provider('imdb'),
                                            "imdb",
                                            uniqueid)
            else:
                self.kodidb.remove_uniqueid(kodi_id, v.KODI_TYPE_MOVIE)
                uniqueid = -1
            self.kodidb.modify_people(kodi_id,
                                      v.KODI_TYPE_MOVIE,
                                      api.people_list())
            self.kodidb.modify_artwork(api.artwork(),
                                       kodi_id,
                                       v.KODI_TYPE_MOVIE)
        else:
            LOG.info("ADD movie plex_id: %s - %s", plex_id, title)
            file_id = self.kodidb.add_file(filename,
                                           kodi_pathid,
                                           api.date_created())
            rating_id = self.kodidb.add_ratingid()
            self.kodidb.add_ratings(rating_id,
                                    kodi_id,
                                    v.KODI_TYPE_MOVIE,
                                    "default",
                                    rating,
                                    api.votecount())
            if api.provider('imdb') is not None:
                uniqueid = self.kodidb.add_uniqueid()
                self.kodidb.add_uniqueid(uniqueid,
                                         kodi_id,
                                         v.KODI_TYPE_MOVIE,
                                         api.provider('imdb'),
                                         "imdb")
            else:
                uniqueid = -1
            self.kodidb.add_people(kodi_id,
                                   v.KODI_TYPE_MOVIE,
                                   api.people_list())
            self.kodidb.add_artwork(api.artwork(),
                                    kodi_id,
                                    v.KODI_TYPE_MOVIE)

        # Update Kodi's main entry
        self.kodidb.add_movie(kodi_id,
                              file_id,
                              title,
                              api.plot(),
                              api.shortplot(),
                              api.tagline(),
                              api.votecount(),
                              rating_id,
                              api.list_to_string(people['Writer']),
                              api.year(),
                              uniqueid,
                              api.sorttitle(),
                              runtime,
                              api.content_rating(),
                              api.list_to_string(genres),
                              api.list_to_string(people['Director']),
                              title,
                              api.list_to_string(studios),
                              api.trailer(),
                              api.list_to_string(countries),
                              playurl,
                              kodi_pathid,
                              api.premiere_date(),
                              userdata['UserRating'])

        self.kodidb.modify_countries(kodi_id, v.KODI_TYPE_MOVIE, countries)
        self.kodidb.modify_genres(kodi_id, v.KODI_TYPE_MOVIE, genres)

        self.kodidb.modify_streams(file_id, api.mediastreams(), runtime)
        self.kodidb.modify_studios(kodi_id, v.KODI_TYPE_MOVIE, studios)
        tags = [section_name]
        if collections:
            for plex_set_id, set_name in collections:
                tags.append(set_name)
                # Add any sets from Plex collection tags
                kodi_set_id = self.kodidb.create_collection(set_name)
                self.kodidb.assign_collection(kodi_set_id, kodi_id)
                if children is None:
                    # e.g. when added via websocket
                    LOG.debug('Costly looking up Plex collection %s: %s',
                              plex_set_id, set_name)
                    for index, coll_plex_id in api.collections_match():
                        # Get Plex artwork for collections - a pain
                        if index == plex_set_id:
                            set_xml = PF.GetPlexMetadata(coll_plex_id)
                            try:
                                set_xml.attrib
                            except AttributeError:
                                LOG.error('Could not get set metadata %s',
                                          coll_plex_id)
                                continue
                            set_api = API(set_xml[0])
                            break
                elif plex_set_id in children:
                    # Provided by get_metadata thread
                    set_api = API(children[plex_set_id][0])
                else:
                    continue
                self.kodidb.modify_artwork(set_api.artwork(),
                                           kodi_set_id,
                                           v.KODI_TYPE_SET)
        self.kodidb.modify_tags(kodi_id, v.KODI_TYPE_MOVIE, tags)
        # Process playstate
        self.kodidb.set_resume(file_id,
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
            self.kodidb.delete_artwork(kodi_id, kodi_type)
            set_id = self.kodidb.get_set_id(kodi_id)
            self.kodidb.modify_countries(kodi_id, kodi_type)
            self.kodidb.modify_people(kodi_id, kodi_type)
            self.kodidb.modify_genres(kodi_id, kodi_type)
            self.kodidb.modify_studios(kodi_id, kodi_type)
            self.kodidb.modify_tags(kodi_id, kodi_type)
            # Delete kodi movie and file
            self.kodidb.remove_file(file_id)
            self.kodidb.remove_movie(kodi_id)
            if set_id:
                self.kodidb.delete_possibly_empty_set(set_id)
            self.kodidb.remove_uniqueid(kodi_id, kodi_type)
            self.kodidb.remove_ratings(kodi_id, kodi_type)
            LOG.debug('Deleted movie %s from kodi database', plex_id)

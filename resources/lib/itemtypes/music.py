#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals
from logging import getLogger

from .common import ItemBase
from ..plex_api import API
from ..plex_db import PlexDB
from .. import artwork, kodidb_functions as kodidb
from .. import plex_functions as PF, utils, state, variables as v

LOG = getLogger('PLEX.music')


class MusicMixin(object):
    def __enter__(self):
        """
        Open DB connections and cursors
        """
        self.plexconn = utils.kodi_sql('plex')
        self.plexcursor = self.plexconn.cursor()
        self.kodiconn = utils.kodi_sql('music')
        self.kodicursor = self.kodiconn.cursor()
        self.plexdb = PlexDB(self.plexcursor)
        self.kodi_db = kodidb.KodiDBMethods(self.kodicursor)
        return self

    def remove(self, plex_id, plex_type=None):
        """
        Remove the entire music object, including all associated entries from
        both Plex and Kodi DBs
        """
        db_item = self.plexdb.item_by_id(plex_id, plex_type)
        if not db_item:
            LOG.debug('Cannot delete plex_id %s - not found in DB', plex_id)
            return
        LOG.debug('Removing %s %s with kodi_id: %s',
                  db_item['plex_type'], plex_id, db_item['kodi_id'])

        # Remove the plex reference
        self.plexdb.remove(plex_id, db_item['plex_type'])

        # SONG #####
        if db_item['plex_type'] == v.PLEX_TYPE_SONG:
            # Delete episode, verify season and tvshow
            self.remove_song(db_item['kodi_id'], db_item['kodi_pathid'])
            # Album verification
            if not self.plexdb.album_has_songs(db_item['album_id']):
                # No episode left for this season - so delete the season
                self.remove_album(db_item['parent_id'])
                self.plexdb.remove(db_item['album_id'], v.PLEX_TYPE_ALBUM)
            # Artist verification
            if (not self.plexdb.artist_has_albums(db_item['artist_id']) and
                    not self.plexdb.artist_has_songs(db_item['artist_id'])):
                self.remove_artist(db_item['grandparent_id'])
                self.plexdb.remove(db_item['artist_id'], v.PLEX_TYPE_ARTIST)
        # ALBUM #####
        elif db_item['plex_type'] == v.PLEX_TYPE_ALBUM:
            # Remove episodes, season, verify tvshow
            for song in self.plexdb.song_by_album(db_item['plex_id']):
                self.remove_song(song['kodi_id'], song['kodi_pathid'])
                self.plexdb.remove(song['plex_id'], v.PLEX_TYPE_SONG)
            # Remove the album
            self.remove_album(db_item['kodi_id'])
            # Show verification
            if (not self.plexdb.artist_has_albums(db_item['album_id']) and
                    not self.plexdb.artist_has_songs(db_item['album_id'])):
                # There's no other season or episode left, delete the show
                self.remove_artist(db_item['parent_id'])
                self.plexdb.remove(db_item['artist_id'], v.KODI_TYPE_ARTIST)
        # ARTIST #####
        elif db_item['plex_type'] == v.PLEX_TYPE_ARTIST:
            # Remove songs, albums and the artist himself
            for song in self.plexdb.song_by_artist(db_item['plex_id']):
                self.remove_song(song['kodi_id'], song['kodi_pathid'])
                self.plexdb.remove(song['plex_id'], v.PLEX_TYPE_SONG)
            for album in self.plexdb.album_by_artist(db_item['plex_id']):
                self.remove_album(album['kodi_id'])
                self.plexdb.remove(album['plex_id'], v.PLEX_TYPE_ALBUM)
            self.remove_artist(db_item['kodi_id'])

        LOG.debug('Deleted %s %s from all databases',
                  db_item['plex_type'], db_item['plex_id'])

    def remove_song(self, kodi_id, path_id=None):
        """
        Remove song, orphaned artists and orphaned paths
        """
        if not path_id:
            query = 'SELECT idPath FROM song WHERE idSong = ? LIMIT 1'
            self.kodicursor.execute(query, (kodi_id, ))
            try:
                path_id = self.kodicursor.fetchone()[0]
            except TypeError:
                pass
        self.kodi_db.delete_song_from_song_artist(kodi_id)
        self.kodicursor.execute('DELETE FROM song WHERE idSong = ?',
                                (kodi_id, ))
        # Check whether we have orphaned path entries
        query = 'SELECT idPath FROM song WHERE idPath = ? LIMIT 1'
        self.kodicursor.execute(query, (path_id, ))
        if not self.kodicursor.fetchone():
            self.kodicursor.execute('DELETE FROM path WHERE idPath = ?',
                                    (path_id, ))
        if v.KODIVERSION < 18:
            self.kodi_db.delete_song_from_song_genre(kodi_id)
            query = 'DELETE FROM albuminfosong WHERE idAlbumInfoSong = ?'
            self.kodicursor.execute(query, (kodi_id, ))
        artwork.delete_artwork(kodi_id, v.KODI_TYPE_SONG, self.kodicursor)

    def remove_album(self, kodi_id):
        '''
        Remove an album
        '''
        self.kodi_db.delete_album_from_discography(kodi_id)
        if v.KODIVERSION < 18:
            self.kodi_db.delete_album_from_album_genre(kodi_id)
            query = 'DELETE FROM albuminfosong WHERE idAlbumInfo = ?'
            self.kodicursor.execute(query, (kodi_id, ))
        self.kodicursor.execute('DELETE FROM album_artist WHERE idAlbum = ?',
                                (kodi_id, ))
        self.kodicursor.execute('DELETE FROM album WHERE idAlbum = ?',
                                (kodi_id, ))
        artwork.delete_artwork(kodi_id, v.KODI_TYPE_ALBUM, self.kodicursor)

    def remove_artist(self, kodi_id):
        '''
        Remove an artist and associated songs and albums
        '''
        self.kodicursor.execute('DELETE FROM album_artist WHERE idArtist = ?',
                                (kodi_id, ))
        self.kodicursor.execute('DELETE FROM artist WHERE idArtist = ?',
                                (kodi_id, ))
        self.kodicursor.execute('DELETE FROM song_artist WHERE idArtist = ?',
                                (kodi_id, ))
        self.kodicursor.execute('DELETE FROM discography WHERE idArtist = ?',
                                (kodi_id, ))
        artwork.delete_artwork(kodi_id, v.KODI_TYPE_ARTIST, self.kodicursor)


class Artist(MusicMixin, ItemBase):
    """
    For Plex library-type artists
    """
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None):
        """
        Process a single artist
        """
        api = API(xml)
        plex_id = api.plex_id()
        if not plex_id:
            LOG.error('Cannot process artist %s', xml.attrib)
            return
        artist = self.plexdb.artist(plex_id)
        if not artist:
            update_item = False
        else:
            update_item = True
            kodi_id = artist['kodi_id']

        # Not yet implemented by Plex
        musicBrainzId = None

        # Associate artwork
        artworks = api.artwork()
        if 'poster' in artworks:
            thumb = "<thumb>%s</thumb>" % artworks['poster']
        else:
            thumb = None
        if 'fanart' in artworks:
            fanart = "<fanart>%s</fanart>" % artworks['fanart']
        else:
            fanart = None

        # UPDATE THE ARTIST #####
        if update_item:
            LOG.info("UPDATE artist plex_id: %s - Name: %s", plex_id, api.title())
        # OR ADD THE ARTIST #####
        else:
            LOG.info("ADD artist plex_id: %s - Name: %s", plex_id, api.title())
            # safety checks: It looks like plex supports the same artist
            # multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the
            # artist entries.
            kodi_id = self.kodi_db.add_artist(api.title(), musicBrainzId)
            # Create the reference in plex table
        query = '''
            UPDATE artist
            SET strGenres = ?,
                strBiography = ?,
                strImage = ?,
                strFanart = ?,
                lastScraped = ?
            WHERE idArtist = ?
        '''
        self.kodicursor.execute(
            query,
            (api.list_to_string(api.genre_list()),
             api.plot(),
             thumb,
             fanart,
             utils.unix_date_to_kodi(self.last_sync),
             kodi_id))
        # Update artwork
        artwork.modify_artwork(artworks,
                               kodi_id,
                               v.KODI_TYPE_ARTIST,
                               self.kodicursor)
        self.plexdb.add_artist(plex_id,
                               api.checksum(),
                               section_id,
                               kodi_id,
                               self.last_sync)


class Album(MusicMixin, ItemBase):
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None, scan_children=True):
        """
        Process a single album
        scan_children: set to False if you don't want to add children, e.g. to
        avoid infinite loops
        """
        api = API(xml)
        plex_id = api.plex_id()
        if not plex_id:
            LOG.error('Error processing album: %s', xml.attrib)
            return
        album = self.plexdb.album(plex_id)
        if album:
            update_item = True
            kodi_id = album['kodi_id']
        else:
            update_item = False

        # Parent artist - should always be present
        parent_id = api.parent_id()
        artist = self.plexdb.artist(parent_id)
        if not artist:
            LOG.info('Artist %s does not yet exist in DB', parent_id)
            artist_xml = PF.GetPlexMetadata(parent_id)
            try:
                artist_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error('Could not get artist %s xml for %s',
                          parent_id, xml.attrib)
                return
            Artist(artist_xml[0], section_name, section_id)
            artist = self.plexdb.artist(parent_id)
            if not artist:
                LOG.error('Adding artist %s failed for %s',
                          parent_id, xml.attrib)
                return
        artist_id = artist['kodi_id']
        # See if we have a compilation - Plex does NOT feature a compilation
        # flag for albums
        compilation = 0
        for song in children:
            if song.get('originalTitle') is not None:
                compilation = 1
                break
        name = api.title()
        userdata = api.userdata()
        # Not yet implemented by Plex
        musicBrainzId = None
        genres = api.genre_list()
        genre = api.list_to_string(genres)
        # Associate artwork
        artworks = api.artwork()
        if 'poster' in artworks:
            thumb = "<thumb>%s</thumb>" % artworks['poster']
        else:
            thumb = None

        # UPDATE THE ALBUM #####
        if update_item:
            LOG.info("UPDATE album plex_id: %s - Name: %s", plex_id, name)
        # OR ADD THE ALBUM #####
        else:
            LOG.info("ADD album plex_id: %s - Name: %s", plex_id, name)
            kodi_id = self.kodi_db.add_album(name, musicBrainzId)
        # Process the album info
        if v.KODIVERSION >= 18:
            # Kodi Leia
            query = '''
                UPDATE album
                SET strArtistDisp = ?,
                    iYear = ?,
                    strGenres = ?,
                    strReview = ?,
                    strImage = ?,
                    iUserrating = ?,
                    lastScraped = ?,
                    strReleaseType = ?,
                    strLabel = ?,
                    bCompilation = ?
                WHERE idAlbum = ?
            '''
            self.kodicursor.execute(
                query,
                (api.artist_name(),
                 api.year(),
                 genre,
                 api.plot(),
                 thumb,
                 userdata['UserRating'],
                 utils.unix_date_to_kodi(self.last_sync),
                 v.KODI_TYPE_ALBUM,
                 api.music_studio(),
                 compilation,
                 kodi_id))
        else:
            # Kodi Krypton
            query = '''
                UPDATE album
                SET strArtists = ?,
                    iYear = ?,
                    strGenres = ?,
                    strReview = ?,
                    strImage = ?,
                    iUserrating = ?,
                    lastScraped = ?,
                    strReleaseType = ?,
                    strLabel = ?,
                    bCompilation = ?
                WHERE idAlbum = ?
            '''
            self.kodicursor.execute(
                query,
                (api.artist_name(),
                 api.year(),
                 genre,
                 api.plot(),
                 thumb,
                 userdata['UserRating'],
                 utils.unix_date_to_kodi(self.last_sync),
                 v.KODI_TYPE_ALBUM,
                 api.music_studio(),
                 compilation,
                 kodi_id))
        # Add artist to album
        query = '''
            INSERT OR REPLACE INTO album_artist(
                idArtist,
                idAlbum,
                strArtist)
            VALUES (?, ?, ?)
        '''
        self.kodicursor.execute(query,
                                (artist_id, kodi_id, api.artist_name()))
        # Update discography
        query = '''
            INSERT OR REPLACE INTO discography(
                idArtist,
                strAlbum,
                strYear)
            VALUES (?, ?, ?)
        '''
        self.kodicursor.execute(query,
                                (artist_id, name, api.year()))
        if v.KODIVERSION < 18:
            self.kodi_db.add_music_genres(kodi_id,
                                          genres,
                                          v.KODI_TYPE_ALBUM)
        # Update artwork
        artwork.modify_artwork(artworks,
                               kodi_id,
                               v.KODI_TYPE_ALBUM,
                               self.kodicursor)
        self.plexdb.add_album(plex_id,
                              api.checksum(),
                              section_id,
                              artist_id,
                              parent_id,
                              kodi_id,
                              self.last_sync)
        # Add all children - all tracks
        if scan_children:
            context = Song(self.last_sync,
                           plexdb=self.plexdb,
                           kodi_db=self.kodi_db)
            for song in children:
                context.add_update(song,
                                   section_name=section_name,
                                   section_id=section_id,
                                   album_xml=xml,
                                   genres=genres,
                                   genre=genre,
                                   compilation=compilation)


class Song(MusicMixin, ItemBase):
    def add_update(self, xml, section_name=None, section_id=None,
                   children=None, album_xml=None, genres=None, genre=None,
                   compilation=None):
        """
        Process single song/track
        """
        api = API(xml)
        plex_id = api.plex_id()
        if not plex_id:
            LOG.error('Error processing song: %s', xml.attrib)
            return
        song = self.plexdb.song(plex_id)
        if song:
            update_item = True
            kodi_id = song['kodi_id']
            kodi_pathid = song['kodi_pathid']
        else:
            update_item = False
            self.kodicursor.execute('SELECT COALESCE(MAX(idSong),0) FROM song')
            kodi_id = self.kodicursor.fetchone()[0] + 1
        artist_id = api.grandparent_id()
        album_id = api.parent_id()

        # The grandparent Artist - should always be present for every song!
        artist = self.plexdb.artist(artist_id)
        if not artist:
            LOG.warn('Grandparent artist %s not found in DB, adding it',
                     artist_id)
            artist_xml = PF.GetPlexMetadata(artist_id)
            try:
                artist_xml[0].attrib
            except (TypeError, IndexError, AttributeError):
                LOG.error('Grandparent tvartist %s xml download failed for %s',
                          artist_id, xml.attrib)
                return
            Artist(self.last_sync, plexdb=self.plexdb, kodi_db=self.kodi_db).add_update(
                artist_xml[0], section_name, section_id)
            artist = self.plexdb.artist(artist_id)
            if not artist:
                LOG.error('Still could not find grandparent artist %s for %s',
                          artist_id, xml.attrib)
                return
        grandparent_id = artist['kodi_id']

        # The parent Album
        if not album_id:
            # No album found, create a single's album
            LOG.info('Creating singles album')
            self.kodicursor.execute(
                'SELECT COALESCE(MAX(idAlbum),0) FROM album')
            parent_id = self.kodicursor.fetchone()[0] + 1
            query = '''
                INSERT INTO album(
                    idAlbum,
                    strGenres,
                    iYear,
                    strReleaseType)
                VALUES (?, ?, ?, ?)
            '''
            self.kodicursor.execute(query,
                                    (parent_id, genre, api.year(), 'single'))
        else:
            album = self.plexdb.album(album_id)
            if not album:
                LOG.warn('Parent album %s not found in DB, adding it', album_id)
                album_xml = PF.GetPlexMetadata(album_id)
                try:
                    album_xml[0].attrib
                except (TypeError, IndexError, AttributeError):
                    LOG.error('Parent album %s xml download failed for %s',
                              album_id, xml.attrib)
                    return
                Album(self.last_sync, plexdb=self.plexdb, kodi_db=self.kodi_db).add_update(
                    album_xml[0], section_name, section_id)
                album = self.plexdb.album(album_id)
                if not album:
                    LOG.error('Still could not find parent album %s for %s',
                              album_id, xml.attrib)
                    return
            parent_id = album['kodi_id']

        title = api.title()
        # Not yet implemented by Plex
        musicBrainzId = None
        comment = None
        userdata = api.userdata()
        playcount = userdata['PlayCount']
        if playcount is None:
            # This is different to Video DB!
            playcount = 0
        # Getting artists name is complicated
        if compilation is not None:
            if compilation == 0:
                artists = api.grandparent_title()
            else:
                artists = xml.get('originalTitle')
        else:
            # compilation not set
            artists = xml.get('originalTitle', api.grandparent_title())
        tracknumber = api.track_number() or 0
        disc = api.disc_number() or 1
        if disc == 1:
            track = tracknumber
        else:
            track = disc * 2 ** 16 + tracknumber
        year = api.year()
        if not year and album_xml:
            # Plex did not pass year info - get it from the parent album
            album_api = API(album_xml)
            year = album_api.year()
        moods = []
        for entry in xml:
            if entry.tag == 'Mood':
                moods.append(entry.attrib['tag'])
        mood = api.list_to_string(moods)

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
                if "\\" in playurl:
                    # Local path
                    filename = playurl.rsplit("\\", 1)[1]
                else:
                    # Network share
                    filename = playurl.rsplit("/", 1)[1]
                path = playurl.replace(filename, "")
        if do_indirect:
            # Plex works a bit differently
            path = "%s%s" % (utils.window('pms_server'),
                             xml[0][0].get('key'))
            path = api.attach_plex_token_to_url(path)
            filename = path.rsplit('/', 1)[1]
            path = path.replace(filename, '')

        # UPDATE THE SONG #####
        if update_item:
            LOG.info("UPDATE song plex_id: %s - %s", plex_id, title)
            # Use dummy strHash '123' for Kodi
            query = "UPDATE path SET strPath = ?, strHash = ? WHERE idPath = ?"
            self.kodicursor.execute(query, (path, '123', kodi_pathid))
            # Update the song entry
            if v.KODIVERSION >= 18:
                # Kodi Leia
                query = '''
                    UPDATE song
                    SET idAlbum = ?,
                        strArtistDisp = ?,
                        strGenres = ?,
                        strTitle = ?,
                        iTrack = ?,
                        iDuration = ?,
                        iYear = ?,
                        strFilename = ?,
                        iTimesPlayed = ?,
                        lastplayed = ?,
                        rating = ?,
                        comment = ?,
                        mood = ?
                    WHERE idSong = ?
                '''
                self.kodicursor.execute(
                    query,
                    (parent_id,
                     artists,
                     genre,
                     title,
                     track,
                     userdata['Runtime'],
                     year,
                     filename,
                     playcount,
                     userdata['LastPlayedDate'],
                     userdata['UserRating'],
                     comment,
                     mood,
                     kodi_id))
            else:
                query = '''
                    UPDATE song
                    SET idAlbum = ?,
                        strArtists = ?,
                        strGenres = ?,
                        strTitle = ?,
                        iTrack = ?,
                        iDuration = ?,
                        iYear = ?,
                        strFilename = ?,
                        iTimesPlayed = ?,
                        lastplayed = ?,
                        rating = ?,
                        comment = ?,
                        mood = ?
                    WHERE idSong = ?
                '''
                self.kodicursor.execute(
                    query,
                    (parent_id,
                     artists,
                     genre,
                     title,
                     track,
                     userdata['Runtime'],
                     year,
                     filename,
                     playcount,
                     userdata['LastPlayedDate'],
                     userdata['UserRating'],
                     comment,
                     mood,
                     kodi_id))

        # OR ADD THE SONG #####
        else:
            LOG.info("ADD song plex_id: %s - %s", plex_id, title)
            # Add path
            kodi_pathid = self.kodi_db.add_music_path(path, hash_string="123")
            # Create the song entry
            if v.KODIVERSION >= 18:
                # Kodi Leia
                query = '''
                    INSERT INTO song(
                        idSong,
                        idAlbum,
                        idPath,
                        strArtistDisp,
                        strGenres,
                        strTitle,
                        iTrack,
                        iDuration,
                        iYear,
                        strFileName,
                        strMusicBrainzTrackID,
                        iTimesPlayed,
                        lastplayed,
                        rating,
                        iStartOffset,
                        iEndOffset,
                        mood)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                self.kodicursor.execute(
                    query,
                    (kodi_id,
                     parent_id,
                     kodi_pathid,
                     artists,
                     genre,
                     title,
                     track,
                     userdata['Runtime'],
                     year,
                     filename,
                     musicBrainzId,
                     playcount,
                     userdata['LastPlayedDate'],
                     userdata['UserRating'],
                     0,
                     0,
                     mood))
            else:
                query = '''
                    INSERT INTO song(
                        idSong,
                        idAlbum,
                        idPath,
                        strArtists,
                        strGenres,
                        strTitle,
                        iTrack,
                        iDuration,
                        iYear,
                        strFileName,
                        strMusicBrainzTrackID,
                        iTimesPlayed,
                        lastplayed,
                        rating,
                        iStartOffset,
                        iEndOffset,
                        mood)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                self.kodicursor.execute(
                    query,
                    (kodi_id,
                     parent_id,
                     kodi_pathid,
                     artists,
                     genre,
                     title,
                     track,
                     userdata['Runtime'],
                     year,
                     filename,
                     musicBrainzId,
                     playcount,
                     userdata['LastPlayedDate'],
                     userdata['UserRating'],
                     0,
                     0,
                     mood))
        if v.KODIVERSION < 18:
            # Link song to album
            query = '''
                INSERT OR REPLACE INTO albuminfosong(
                    idAlbumInfoSong,
                    idAlbumInfo,
                    iTrack,
                    strTitle,
                    iDuration)
                VALUES (?, ?, ?, ?, ?)
            '''
            self.kodicursor.execute(
                query,
                (kodi_id, parent_id, track, title, userdata['Runtime']))
        # Link song to artists
        artist_name = api.grandparent_title()
        # Do the actual linking
        query = '''
            INSERT OR REPLACE INTO song_artist(
                idArtist,
                idSong,
                idRole,
                iOrder,
                strArtist)
            VALUES (?, ?, ?, ?, ?)
        '''
        self.kodicursor.execute(query,
                                (grandparent_id, kodi_id, 1, 0, artist_name))
        # Add genres
        if genres:
            self.kodi_db.add_music_genres(kodi_id, genres, v.KODI_TYPE_SONG)
        artworks = api.artwork()
        artwork.modify_artwork(artworks,
                               kodi_id,
                               v.KODI_TYPE_SONG,
                               self.kodicursor)
        if xml.get('parentKey') is None:
            # Update album artwork
            artwork.modify_artwork(artworks,
                                   parent_id,
                                   v.KODI_TYPE_ALBUM,
                                   self.kodicursor)
        # Create the reference in plex table
        self.plexdb.add_song(plex_id,
                             api.checksum(),
                             section_id,
                             artist_id,
                             grandparent_id,
                             album_id,
                             parent_id,
                             kodi_id,
                             kodi_pathid,
                             self.last_sync)

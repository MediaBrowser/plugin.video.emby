# -*- coding: utf-8 -*-

###############################################################################
from logging import getLogger
from ntpath import dirname
from sqlite3 import IntegrityError

import artwork
from utils import kodi_sql, try_decode
import variables as v

###############################################################################

LOG = getLogger("PLEX." + __name__)

###############################################################################


class GetKodiDB(object):
    """
    Usage: with GetKodiDB(db_type) as kodi_db:
               do stuff with kodi_db

    Parameters:
        db_type:       DB to open: 'video', 'music', 'plex', 'texture'

    On exiting "with" (no matter what), commits get automatically committed
    and the db gets closed
    """
    def __init__(self, db_type):
        self.kodiconn = None
        self.db_type = db_type

    def __enter__(self):
        self.kodiconn = kodi_sql(self.db_type)
        kodi_db = KodiDBMethods(self.kodiconn.cursor())
        return kodi_db

    def __exit__(self, typus, value, traceback):
        self.kodiconn.commit()
        self.kodiconn.close()


class KodiDBMethods(object):
    """
    Best used indirectly with another Class GetKodiDB:
        with GetKodiDB(db_type) as kodi_db:
            kodi_db.method()
    """
    def __init__(self, cursor):
        self.cursor = cursor
        self.artwork = artwork.Artwork()

    def setup_path_table(self):
        """
        Use with Kodi video DB

        Sets strContent to e.g. 'movies' and strScraper to metadata.local

        For some reason, Kodi ignores this if done via itemtypes while e.g.
        adding or updating items. (addPath method does NOT work)
        """
        path_id = self.getPath('plugin://%s.movies/' % v.ADDON_ID)
        if path_id is None:
            self.cursor.execute("SELECT COALESCE(MAX(idPath),-1) FROM path")
            path_id = self.cursor.fetchone()[0] + 1
            query = '''
                INSERT INTO path(idPath,
                                 strPath,
                                 strContent,
                                 strScraper,
                                 noUpdate,
                                 exclude)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query, (path_id,
                                        'plugin://%s.movies/' % v.ADDON_ID,
                                        'movies',
                                        'metadata.local',
                                        1,
                                        0))
        # And TV shows
        path_id = self.getPath('plugin://%s.tvshows/' % v.ADDON_ID)
        if path_id is None:
            self.cursor.execute("SELECT COALESCE(MAX(idPath),-1) FROM path")
            path_id = self.cursor.fetchone()[0] + 1
            query = '''
                INSERT INTO path(idPath,
                                 strPath,
                                 strContent,
                                 strScraper,
                                 noUpdate,
                                 exclude)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query, (path_id,
                                        'plugin://%s.tvshows/' % v.ADDON_ID,
                                        'tvshows',
                                        'metadata.local',
                                        1,
                                        0))

    def getParentPathId(self, path):
        """
        Video DB: Adds all subdirectories to SQL path while setting a "trail"
        of parentPathId
        """
        if "\\" in path:
            # Local path
            parentpath = "%s\\" % dirname(dirname(path))
        else:
            # Network path
            parentpath = "%s/" % dirname(dirname(path))
        pathid = self.getPath(parentpath)
        if pathid is None:
            self.cursor.execute("SELECT COALESCE(MAX(idPath),-1) FROM path")
            pathid = self.cursor.fetchone()[0] + 1
            query = ' '.join((
                "INSERT INTO path(idPath, strPath)",
                "VALUES (?, ?)"
            ))
            self.cursor.execute(query, (pathid, parentpath))
            parentPathid = self.getParentPathId(parentpath)
            query = ' '.join((
                "UPDATE path",
                "SET idParentPath = ?",
                "WHERE idPath = ?"
            ))
            self.cursor.execute(query, (parentPathid, pathid))
        return pathid

    def addPath(self, path, strHash=None):
        # SQL won't return existing paths otherwise
        if path is None:
            path = ""
        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        self.cursor.execute(query, (path,))
        try:
            pathid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("SELECT COALESCE(MAX(idPath),-1) FROM path")
            pathid = self.cursor.fetchone()[0] + 1
            if strHash is None:
                query = (
                    '''
                    INSERT INTO path(
                        idPath, strPath)

                    VALUES (?, ?)
                    '''
                )
                self.cursor.execute(query, (pathid, path))
            else:
                query = (
                    '''
                    INSERT INTO path(
                        idPath, strPath, strHash)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (pathid, path, strHash))

        return pathid

    def getPath(self, path):

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        self.cursor.execute(query, (path,))
        try:
            pathid = self.cursor.fetchone()[0]
        except TypeError:
            pathid = None

        return pathid

    def addFile(self, filename, pathid):

        query = ' '.join((

            "SELECT idFile",
            "FROM files",
            "WHERE strFilename = ?",
            "AND idPath = ?"
        ))
        self.cursor.execute(query, (filename, pathid,))
        try:
            fileid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("SELECT COALESCE(MAX(idFile),-1) FROM files")
            fileid = self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO files(
                    idFile, strFilename)

                VALUES (?, ?)
                '''
            )
            self.cursor.execute(query, (fileid, filename))

        return fileid

    def getFile(self, fileid):

        query = ' '.join((

            "SELECT strFilename",
            "FROM files",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (fileid,))
        try:
            filename = self.cursor.fetchone()[0]
        except TypeError:
            filename = ""

        return filename

    def removeFile(self, path, filename):
        
        pathid = self.getPath(path)

        if pathid is not None:
            query = ' '.join((

                "DELETE FROM files",
                "WHERE idPath = ?",
                "AND strFilename = ?"
            ))
            self.cursor.execute(query, (pathid, filename,))

    def _modify_link_and_table(self, kodi_id, kodi_type, entries, link_table,
                               table, key):
        query = '''
            SELECT %s FROM %s WHERE name = ? COLLATE NOCASE LIMIT 1
        ''' % (key, table)
        query_id = 'SELECT COALESCE(MAX(%s), -1) FROM %s' % (key, table)
        query_new = ('INSERT INTO %s(%s, name) values(?, ?)'
                     % (table, key))
        entry_ids = []
        for entry in entries:
            self.cursor.execute(query, (entry,))
            try:
                entry_id = self.cursor.fetchone()[0]
            except TypeError:
                self.cursor.execute(query_id)
                entry_id = self.cursor.fetchone()[0] + 1
                LOG.debug('Adding %s: %s with id %s', table, entry, entry_id)
                self.cursor.execute(query_new, (entry_id, entry))
            finally:
                entry_ids.append(entry_id)
        # Now process the ids obtained from the names
        # Get the existing, old entries
        query = ('SELECT %s FROM %s WHERE media_id = ? AND media_type = ?'
                 % (key, link_table))
        self.cursor.execute(query, (kodi_id, kodi_type))
        old_entries = self.cursor.fetchall()
        outdated_entries = []
        for entry_id in old_entries:
            try:
                entry_ids.remove(entry_id[0])
            except ValueError:
                outdated_entries.append(entry_id[0])
        # Add all new entries that haven't already been added
        query = 'INSERT INTO %s VALUES (?, ?, ?)' % link_table
        for entry_id in entry_ids:
            self.cursor.execute(query, (entry_id, kodi_id, kodi_type))
        # Delete all outdated references in the link table. Also check whether
        # we need to delete orphaned entries in the master table
        query = '''
            DELETE FROM %s WHERE %s = ? AND media_id = ? AND media_type = ?
        ''' % (link_table, key)
        query_rem = 'SELECT %s FROM %s WHERE %s = ?' % (key, link_table, key)
        query_delete = 'DELETE FROM %s WHERE %s = ?' % (table, key)
        for entry_id in outdated_entries:
            self.cursor.execute(query, (entry_id, kodi_id, kodi_type))
            self.cursor.execute(query_rem, (entry_id,))
            if self.cursor.fetchone() is None:
                # Delete in the original table because entry is now orphaned
                LOG.debug('Removing %s from Kodi DB: %s', table, entry_id)
                self.cursor.execute(query_delete, (entry_id,))

    def modify_countries(self, kodi_id, kodi_type, countries=None):
        """
        Writes a country (string) in the list countries into the Kodi DB. Will
        also delete any orphaned country entries.
        """
        countries = countries if countries else []
        self._modify_link_and_table(kodi_id,
                                    kodi_type,
                                    countries,
                                    'country_link',
                                    'country',
                                    'country_id')

    def modify_genres(self, kodi_id, kodi_type, genres=None):
        """
        Writes a country (string) in the list countries into the Kodi DB. Will
        also delete any orphaned country entries.
        """
        genres = genres if genres else []
        self._modify_link_and_table(kodi_id,
                                    kodi_type,
                                    genres,
                                    'genre_link',
                                    'genre',
                                    'genre_id')

    def modify_studios(self, kodi_id, kodi_type, studios=None):
        """
        Writes a country (string) in the list countries into the Kodi DB. Will
        also delete any orphaned country entries.
        """
        studios = studios if studios else []
        self._modify_link_and_table(kodi_id,
                                    kodi_type,
                                    studios,
                                    'studio_link',
                                    'studio',
                                    'studio_id')

    def modify_tags(self, kodi_id, kodi_type, tags=None):
        """
        Writes a country (string) in the list countries into the Kodi DB. Will
        also delete any orphaned country entries.
        """
        tags = tags if tags else []
        self._modify_link_and_table(kodi_id,
                                    kodi_type,
                                    tags,
                                    'tag_link',
                                    'tag',
                                    'tag_id')

    def modify_people(self, kodi_id, kodi_type, people=None):
        """
        Makes sure that actors, directors and writers are recorded correctly
        for the elmement kodi_id, kodi_type.
        Will also delete a freshly orphaned actor entry.
        """
        people = people if people else {'actor': [],
                                        'director': [],
                                        'writer': []}
        for kind, people_list in people.iteritems():
            self._modify_people_kind(kodi_id, kodi_type, kind, people_list)

    def _modify_people_kind(self, kodi_id, kodi_type, kind, people_list):
        # Get the people already saved in the DB for this specific item
        if kind == 'actor':
            query = '''
                SELECT actor.actor_id, actor.name, art.url, actor_link.role,
                    actor_link.cast_order
                FROM actor_link
                LEFT JOIN actor ON actor.actor_id = actor_link.actor_id
                LEFT JOIN art ON (art.media_id = actor_link.actor_id AND
                                  art.media_type = 'actor')
                WHERE actor_link.media_id = ? AND actor_link.media_type = ?
            '''
        else:
            query = '''
                SELECT actor.actor_id, actor.name
                FROM {0}_link
                LEFT JOIN actor ON actor.actor_id = {0}_link.actor_id
                WHERE {0}_link.media_id = ? AND {0}_link.media_type = ?
            '''.format(kind)
        self.cursor.execute(query, (kodi_id, kodi_type))
        old_people = self.cursor.fetchall()
        # Determine which people we need to save or delete
        outdated_people = []
        for person in old_people:
            try:
                people_list.remove(person[1:])
            except ValueError:
                outdated_people.append(person)
        # Get rid of old entries
        query = '''
            DELETE FROM %s_link
            WHERE actor_id = ? AND media_id = ? AND media_type = ?
        ''' % kind
        query_actor_check = 'SELECT actor_id FROM %s_link WHERE actor_id = ?'
        query_actor_delete = 'DELETE FROM actor WHERE actor_id = ?'
        for person in outdated_people:
            # Delete the outdated entry
            self.cursor.execute(query, (person[0], kodi_id, kodi_type))
            # Do we now have orphaned entries?
            for person_kind in ('actor', 'writer', 'director'):
                self.cursor.execute(query_actor_check % person_kind,
                                    (person[0],))
                if self.cursor.fetchone() is not None:
                    break
            else:
                # person entry in actor table is now orphaned
                # Delete the person from actor table
                LOG.debug('Removing person from Kodi DB: %s', person)
                self.cursor.execute(query_actor_delete, (person[0],))
                if kind == 'actor':
                    # Delete any associated artwork
                    self.artwork.deleteArtwork(person[0], 'actor', self.cursor)
        # Save new people to Kodi DB by iterating over the remaining entries
        if kind == 'actor':
            query = 'INSERT INTO actor_link VALUES (?, ?, ?, ?, ?)'
            for person in people_list:
                LOG.debug('Adding actor to Kodi DB: %s', person)
                # Make sure the person entry in table actor exists
                actor_id = self._get_actor_id(person[0], art_url=person[1])
                # Link the person with the media element
                try:
                    self.cursor.execute(query, (actor_id, kodi_id, kodi_type,
                                                person[2], person[3]))
                except IntegrityError:
                    # With Kodi, an actor may have only one role, unlike Plex
                    pass
        else:
            query = 'INSERT INTO %s_link VALUES (?, ?, ?)' % kind
            for person in people_list:
                LOG.debug('Adding %s to Kodi DB: %s', kind, person[0])
                # Make sure the person entry in table actor exists:
                actor_id = self._get_actor_id(person[0])
                # Link the person with the media element
                try:
                    self.cursor.execute(query, (actor_id, kodi_id, kodi_type))
                except IntegrityError:
                    # Again, Kodi may have only one person assigned to a role
                    pass

    def _get_actor_id(self, name, art_url=None):
        """
        Returns the actor_id [int] for name [unicode] in table actor (without
        ensuring that the name matches).
        If not, will create a new record with actor_id, name, art_url

        Uses Plex ids and thus assumes that Plex person id is unique!
        """
        self.cursor.execute('SELECT actor_id FROM actor WHERE name=? LIMIT 1',
                            (name,))
        try:
            actor_id = self.cursor.fetchone()[0]
        except TypeError:
            # Not yet in actor DB, add person
            self.cursor.execute('SELECT COALESCE(MAX(actor_id),-1) FROM actor')
            actor_id = self.cursor.fetchone()[0] + 1
            self.cursor.execute('INSERT INTO actor(actor_id, name) '
                                'VALUES (?, ?)',
                                (actor_id, name))
            if art_url:
                self.artwork.addOrUpdateArt(art_url,
                                            actor_id,
                                            'actor',
                                            "thumb",
                                            self.cursor)
        return actor_id

    def existingArt(self, kodiId, mediaType, refresh=False):
        """
        For kodiId, returns an artwork dict with already existing art from
        the Kodi db
        """
        # Only get EITHER poster OR thumb (should have same URL)
        kodiToPKC = {
            'banner': 'Banner',
            'clearart': 'Art',
            'clearlogo': 'Logo',
            'discart': 'Disc',
            'landscape': 'Thumb',
            'thumb': 'Primary'
        }
        # BoxRear yet unused
        result = {'BoxRear': ''}
        for art in kodiToPKC:
            query = ' '.join((
                "SELECT url",
                "FROM art",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND type = ?"
            ))
            self.cursor.execute(query, (kodiId, mediaType, art,))
            try:
                url = self.cursor.fetchone()[0]
            except TypeError:
                url = ""
            result[kodiToPKC[art]] = url
        # There may be several fanart URLs saved
        query = ' '.join((
            "SELECT url",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?",
            "AND type LIKE ?"
        ))
        data = self.cursor.execute(query, (kodiId, mediaType, "fanart%",))
        result['Backdrop'] = [d[0] for d in data]
        return result

    def modify_streams(self, fileid, streamdetails=None, runtime=None):
        """
        Leave streamdetails and runtime empty to delete all stream entries for
        fileid
        """
        # First remove any existing entries
        self.cursor.execute('DELETE FROM streamdetails WHERE idFile = ?',
                            (fileid,))
        if not streamdetails:
            return
        for videotrack in streamdetails['video']:
            query = '''
                INSERT INTO streamdetails(
                    idFile, iStreamType, strVideoCodec, fVideoAspect,
                    iVideoWidth, iVideoHeight, iVideoDuration ,strStereoMode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query,
                                (fileid, 0, videotrack['codec'],
                                 videotrack['aspect'], videotrack['width'],
                                 videotrack['height'], runtime,
                                 videotrack['video3DFormat']))
        for audiotrack in streamdetails['audio']:
            query = '''
                INSERT INTO streamdetails(
                    idFile, iStreamType, strAudioCodec, iAudioChannels,
                    strAudioLanguage)
                VALUES (?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query,
                                (fileid, 1, audiotrack['codec'],
                                 audiotrack['channels'],
                                 audiotrack['language']))
        for subtitletrack in streamdetails['subtitle']:
            query = '''
                INSERT INTO streamdetails(idFile, iStreamType,
                    strSubtitleLanguage)
                VALUES (?, ?, ?)
            '''
            self.cursor.execute(query, (fileid, 2, subtitletrack))

    def resume_points(self):
        """
        VIDEOS

        Returns all Kodi idFile that have a resume point set (not unwatched
        ones or items that have already been completely watched)
        """
        query = '''
            SELECT idFile
            FROM bookmark
        '''
        rows = self.cursor.execute(query)
        ids = []
        for row in rows:
            ids.append(row[0])
        return ids

    def video_id_from_filename(self, filename, path):
        """
        Returns the tuple (itemId, type) where
            itemId:     Kodi DB unique Id for either movie or episode
            type:       either 'movie' or 'episode'

        Returns None if not found OR if too many entries were found
        """
        query = ' '.join((
            "SELECT idFile, idPath",
            "FROM files",
            "WHERE strFilename = ?"
        ))
        self.cursor.execute(query, (filename,))
        files = self.cursor.fetchall()
        if len(files) == 0:
            LOG.info('Did not find any file, abort')
            return
        query = ' '.join((
            "SELECT strPath",
            "FROM path",
            "WHERE idPath = ?"
        ))
        # result will contain a list of all idFile with matching filename and
        # matching path
        result = []
        for file in files:
            # Use idPath to get path as a string
            self.cursor.execute(query, (file[1],))
            try:
                strPath = self.cursor.fetchone()[0]
            except TypeError:
                # idPath not found; skip
                continue
            # For whatever reason, double might have become triple
            strPath = strPath.replace('///', '//')
            strPath = strPath.replace('\\\\\\', '\\\\')
            if strPath == path:
                result.append(file[0])
        if len(result) == 0:
            LOG.info('Did not find matching paths, abort')
            return
        # Kodi seems to make ONE temporary entry; we only want the earlier,
        # permanent one
        if len(result) > 2:
            LOG.warn('We found too many items with matching filenames and '
                     ' paths, aborting')
            return
        idFile = result[0]

        # Try movies first
        query = ' '.join((
            "SELECT idMovie",
            "FROM movie",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (idFile,))
        try:
            itemId = self.cursor.fetchone()[0]
            typus = v.KODI_TYPE_MOVIE
        except TypeError:
            # Try tv shows next
            query = ' '.join((
                "SELECT idEpisode",
                "FROM episode",
                "WHERE idFile = ?"
            ))
            self.cursor.execute(query, (idFile,))
            try:
                itemId = self.cursor.fetchone()[0]
                typus = v.KODI_TYPE_EPISODE
            except TypeError:
                LOG.warn('Unexpectantly did not find a match!')
                return
        return itemId, typus

    def music_id_from_filename(self, filename, path):
        """
        Returns the Kodi song_id from the Kodi music database or None if not
        found OR something went wrong.
        """
        query = '''
            SELECT idPath
            FROM path
            WHERE strPath = ?
        '''
        self.cursor.execute(query, (path,))
        path_id = self.cursor.fetchall()
        if len(path_id) != 1:
            LOG.error('Found wrong number of path ids: %s for path %s, abort',
                     path_id, path)
            return
        query = '''
            SELECT idSong
            FROM song
            WHERE strFileName = ? AND idPath = ?
        '''
        self.cursor.execute(query, (filename, path_id[0]))
        song_id = self.cursor.fetchall()
        if len(song_id) != 1:
            LOG.info('Found wrong number of songs %s, abort', song_id)
            return
        return song_id[0]

    def get_resume(self, file_id):
        """
        Returns the first resume point in seconds (int) if found, else None for
        the Kodi file_id provided
        """
        query = '''
            SELECT timeInSeconds
            FROM bookmark
            WHERE idFile = ?
        '''
        self.cursor.execute(query, (file_id,))
        resume = self.cursor.fetchone()
        try:
            resume = resume[0]
        except TypeError:
            resume = None
        return resume

    def delete_all_playstates(self):
        """
        Entirely resets the table bookmark and thus all resume points
        """
        self.cursor.execute("DELETE FROM bookmark")

    def addPlaystate(self, fileid, resume_seconds, total_seconds, playcount,
                     dateplayed):
        # Delete existing resume point
        query = '''
            DELETE FROM bookmark
            WHERE idFile = ?
        '''
        self.cursor.execute(query, (fileid,))
        # Set watched count
        query = '''
            UPDATE files
            SET playCount = ?, lastPlayed = ?
            WHERE idFile = ?
        '''
        self.cursor.execute(query, (playcount, dateplayed, fileid))
        # Set the resume bookmark
        if resume_seconds:
            self.cursor.execute(
                'SELECT COALESCE(MAX(idBookmark),-1) FROM bookmark')
            bookmark_id = self.cursor.fetchone()[0] + 1
            query = '''
            INSERT INTO bookmark(
                idBookmark, idFile, timeInSeconds, totalTimeInSeconds,
                thumbNailImage, player, playerState, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query, (bookmark_id,
                                        fileid,
                                        resume_seconds,
                                        total_seconds,
                                        '',
                                        "VideoPlayer",
                                        '',
                                        1))

    def delete_playstate(self, file_id):
        """
        Removes all playstates/bookmarks for the file with file_id
        """
        self.cursor.execute('DELETE FROM bookmark where idFile = ?', (file_id,))

    def createTag(self, name):
        # This will create and return the tag_id
        query = ' '.join((

            "SELECT tag_id",
            "FROM tag",
            "WHERE name = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (name,))
        try:
            tag_id = self.cursor.fetchone()[0]
        
        except TypeError:
            self.cursor.execute("SELECT COALESCE(MAX(tag_id),-1) FROM tag")
            tag_id = self.cursor.fetchone()[0] + 1

            query = "INSERT INTO tag(tag_id, name) values(?, ?)"
            self.cursor.execute(query, (tag_id, name))
            LOG.debug("Create tag_id: %s name: %s", tag_id, name)
        return tag_id

    def updateTag(self, oldtag, newtag, kodiid, mediatype):
        try:
            query = ' '.join((

                "UPDATE tag_link",
                "SET tag_id = ?",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND tag_id = ?"
            ))
            self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
        except Exception as e:
            # The new tag we are going to apply already exists for this item
            # delete current tag instead
            query = ' '.join((

                "DELETE FROM tag_link",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND tag_id = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype, oldtag,))

    def addSets(self, movieid, collections, kodicursor):
        for setname in collections:
            setid = self.createBoxset(setname)
            self.assignBoxset(setid, movieid)

    def createBoxset(self, boxsetname):

        LOG.debug("Adding boxset: %s", boxsetname)
        query = ' '.join((

            "SELECT idSet",
            "FROM sets",
            "WHERE strSet = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (boxsetname,))
        try:
            setid = self.cursor.fetchone()[0]

        except TypeError:
            self.cursor.execute("SELECT COALESCE(MAX(idSet),-1) FROM sets")
            setid = self.cursor.fetchone()[0] + 1

            query = "INSERT INTO sets(idSet, strSet) values(?, ?)"
            self.cursor.execute(query, (setid, boxsetname))

        return setid

    def assignBoxset(self, setid, movieid):
        
        query = ' '.join((

            "UPDATE movie",
            "SET idSet = ?",
            "WHERE idMovie = ?"
        ))
        self.cursor.execute(query, (setid, movieid,))

    def removefromBoxset(self, movieid):

        query = ' '.join((

            "UPDATE movie",
            "SET idSet = null",
            "WHERE idMovie = ?"
        ))
        self.cursor.execute(query, (movieid,))

    def get_set_id(self, kodi_id):
        """
        Returns the set_id for the movie with kodi_id or None
        """
        query = 'SELECT idSet FROM movie WHERE idMovie = ?'
        self.cursor.execute(query, (kodi_id,))
        try:
            answ = self.cursor.fetchone()[0]
        except TypeError:
            answ = None
        return answ

    def delete_possibly_empty_set(self, set_id):
        """
        Checks whether there are other movies in the set set_id. If not,
        deletes the set
        """
        query = 'SELECT idSet FROM movie WHERE idSet = ?'
        self.cursor.execute(query, (set_id,))
        if self.cursor.fetchone() is None:
            query = 'DELETE FROM sets WHERE idSet = ?'
            self.cursor.execute(query, (set_id,))

    def addSeason(self, showid, seasonnumber):

        query = ' '.join((

            "SELECT idSeason",
            "FROM seasons",
            "WHERE idShow = ?",
            "AND season = ?"
        ))
        self.cursor.execute(query, (showid, seasonnumber,))
        try:
            seasonid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("SELECT COALESCE(MAX(idSeason),-1) FROM seasons")
            seasonid = self.cursor.fetchone()[0] + 1
            query = "INSERT INTO seasons(idSeason, idShow, season) VALUES(?, ?, ?)"
            self.cursor.execute(query, (seasonid, showid, seasonnumber))

        return seasonid

    def addArtist(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idArtist, strArtist",
            "FROM artist",
            "WHERE strMusicBrainzArtistID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            result = self.cursor.fetchone()
            artistid = result[0]
            artistname = result[1]

        except TypeError:

            query = ' '.join((

                "SELECT idArtist",
                "FROM artist",
                "WHERE strArtist = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                artistid = self.cursor.fetchone()[0]
            except TypeError:
                # Krypton has a dummy first entry idArtist: 1  strArtist:
                # [Missing Tag] strMusicBrainzArtistID: Artist Tag Missing
                if v.KODIVERSION >= 17:
                    self.cursor.execute(
                        "SELECT COALESCE(MAX(idArtist),1) FROM artist")
                else:
                    self.cursor.execute(
                        "SELECT COALESCE(MAX(idArtist),-1) FROM artist")
                artistid = self.cursor.fetchone()[0] + 1
                query = (
                    '''
                    INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (artistid, name, musicbrainz))
        else:
            if artistname != name:
                query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
                self.cursor.execute(query, (name, artistid,))

        return artistid

    def addAlbum(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idAlbum",
            "FROM album",
            "WHERE strMusicBrainzAlbumID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            albumid = self.cursor.fetchone()[0]
        except TypeError:
            # Create the album
            self.cursor.execute("SELECT COALESCE(MAX(idAlbum),-1) FROM album")
            albumid = self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType)

                VALUES (?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (albumid, name, musicbrainz, "album"))
        return albumid

    def addMusicGenres(self, kodiid, genres, mediatype):

        if mediatype == "album":

            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM album_genre",
                "WHERE idAlbum = ?"
            ))
            self.cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                try:
                    genreid = self.cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    self.cursor.execute("SELECT COALESCE(MAX(idGenre),-1) FROM genre")
                    genreid = self.cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) values(?, ?)"
                self.cursor.execute(query, (genreid, kodiid))

        elif mediatype == "song":
            
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM song_genre",
                "WHERE idSong = ?"
            ))
            self.cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                try:
                    genreid = self.cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    self.cursor.execute("SELECT COALESCE(MAX(idGenre),-1) FROM genre")
                    genreid = self.cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO song_genre(idGenre, idSong) values(?, ?)"
                self.cursor.execute(query, (genreid, kodiid))

# Krypton only stuff ##############################

    def update_userrating(self, kodi_id, kodi_type, userrating):
        """
        Updates userrating for >=Krypton
        """
        if kodi_type == v.KODI_TYPE_MOVIE:
            ID = 'idMovie'
        elif kodi_type == v.KODI_TYPE_EPISODE:
            ID = 'idEpisode'
        elif kodi_type == v.KODI_TYPE_SONG:
            ID = 'idSong'
        query = '''UPDATE %s SET userrating = ? WHERE ? = ?''' % kodi_type
        self.cursor.execute(query, (userrating, ID, kodi_id))

    def add_uniqueid(self, *args):
        """
        Feed with:
            uniqueid_id: int
            media_id: int
            media_type: string
            value: string
            type: e.g. 'imdb' or 'tvdb'
        """
        query = '''
            INSERT INTO uniqueid(
                uniqueid_id, media_id, media_type, value, type)
            VALUES (?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (args))

    def get_uniqueid(self, kodi_id, kodi_type):
        query = '''
            SELECT uniqueid_id FROM uniqueid
            WHERE media_id = ? AND media_type = ?
        '''
        self.cursor.execute(query, (kodi_id, kodi_type))
        try:
            uniqueid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute(
                'SELECT COALESCE(MAX(uniqueid_id),-1) FROM uniqueid')
            uniqueid = self.cursor.fetchone()[0] + 1
        return uniqueid

    def update_uniqueid(self, *args):
        """
        Pass in media_id, media_type, value, type, uniqueid_id
        """
        query = '''
            UPDATE uniqueid
            SET media_id = ?, media_type = ?, value = ?, type = ?
            WHERE uniqueid_id = ?
        '''
        self.cursor.execute(query, (args))

    def remove_uniqueid(self, kodi_id, kodi_type):
        query = '''
            DELETE FROM uniqueid
            WHERE media_id = ? AND media_type = ?
        '''
        self.cursor.execute(query, (kodi_id, kodi_type))

    def get_ratingid(self, kodi_id, kodi_type):
        query = '''
            SELECT rating_id FROM rating
            WHERE media_id = ? AND media_type = ?
        '''
        self.cursor.execute(query, (kodi_id, kodi_type))
        try:
            ratingid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute('SELECT COALESCE(MAX(rating_id),-1) FROM rating')
            ratingid = self.cursor.fetchone()[0] + 1
        return ratingid

    def update_ratings(self, *args):
        """
        Feed with media_id, media_type, rating_type, rating, votes, rating_id
        """
        query = '''
            UPDATE rating
            SET media_id = ?,
                media_type = ?,
                rating_type = ?,
                rating = ?,
                votes = ?
            WHERE rating_id = ?
        '''
        self.cursor.execute(query, (args))

    def add_ratings(self, *args):
        """
        feed with:
            rating_id, media_id, media_type, rating_type, rating, votes

        rating_type = 'default'
        """
        query = '''
            INSERT INTO rating(
                rating_id, media_id, media_type, rating_type, rating, votes)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        self.cursor.execute(query, (args))

    def remove_ratings(self, kodi_id, kodi_type):
        query = '''
            DELETE FROM rating
            WHERE media_id = ? AND media_type = ?
        '''
        self.cursor.execute(query, (kodi_id, kodi_type))


def kodiid_from_filename(path, kodi_type):
    """
    Returns kodi_id if we have an item in the Kodi video or audio database with
    said path. Feed with the Kodi itemtype, e.v. 'movie', 'song'
    Returns None if not possible
    """
    kodi_id = None
    path = try_decode(path)
    try:
        filename = path.rsplit('/', 1)[1]
        path = path.rsplit('/', 1)[0] + '/'
    except IndexError:
        filename = path.rsplit('\\', 1)[1]
        path = path.rsplit('\\', 1)[0] + '\\'
    if kodi_type == v.KODI_TYPE_SONG:
        with GetKodiDB('music') as kodi_db:
            try:
                kodi_id, _ = kodi_db.music_id_from_filename(filename, path)
            except TypeError:
                LOG.debug('No Kodi audio db element found for path %s', path)
    else:
        with GetKodiDB('video') as kodi_db:
            try:
                kodi_id, _ = kodi_db.video_id_from_filename(filename, path)
            except TypeError:
                LOG.debug('No kodi video db element found for path %s', path)
    return kodi_id

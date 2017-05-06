# -*- coding: utf-8 -*-

###############################################################################

import logging
from ntpath import dirname

import artwork
from utils import kodiSQL
import variables as v

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


class GetKodiDB():
    """
    Usage: with GetKodiDB(db_type) as kodi_db:
               do stuff with kodi_db

    Parameters:
        db_type:       DB to open: 'video', 'music', 'plex', 'texture'

    On exiting "with" (no matter what), commits get automatically committed
    and the db gets closed
    """
    def __init__(self, db_type):
        self.db_type = db_type

    def __enter__(self):
        self.kodiconn = kodiSQL(self.db_type)
        kodi_db = Kodidb_Functions(self.kodiconn.cursor())
        return kodi_db

    def __exit__(self, type, value, traceback):
        self.kodiconn.commit()
        self.kodiconn.close()


class Kodidb_Functions():
    def __init__(self, cursor):
        self.cursor = cursor
        self.artwork = artwork.Artwork()

    def pathHack(self):
        """
        Use with Kodi video DB

        Sets strContent to e.g. 'movies' and strScraper to metadata.local

        For some reason, Kodi ignores this if done via itemtypes while e.g.
        adding or updating items. (addPath method does NOT work)
        """
        query = ' '.join((
            "UPDATE path",
            "SET strContent = ?, strScraper = ?",
            "WHERE strPath LIKE ?"
        ))
        self.cursor.execute(
            query, ('movies',
                    'metadata.local',
                    'plugin://plugin.video.plexkodiconnect/movies%%'))

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
            self.cursor.execute("select coalesce(max(idPath),0) from path")
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
            self.cursor.execute("select coalesce(max(idPath),0) from path")
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
            self.cursor.execute("select coalesce(max(idFile),0) from files")
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

    def addCountries(self, kodiid, countries, mediatype):
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
            for country in countries:
                query = ' '.join((

                    "SELECT country_id",
                    "FROM country",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (country,))

                try:
                    country_id = self.cursor.fetchone()[0]

                except TypeError:
                    # Country entry does not exists
                    self.cursor.execute("select coalesce(max(country_id),0) from country")
                    country_id = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(country_id, name) values(?, ?)"
                    self.cursor.execute(query, (country_id, country))
                    log.debug("Add country to media, processing: %s" % country)

                finally: # Assign country to content
                    query = (
                        '''
                        INSERT OR REPLACE INTO country_link(
                            country_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        '''
                    )
                    self.cursor.execute(query, (country_id, kodiid, mediatype))
        else:
            # Kodi Helix
            for country in countries:
                query = ' '.join((

                    "SELECT idCountry",
                    "FROM country",
                    "WHERE strCountry = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (country,))

                try:
                    idCountry = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Country entry does not exists
                    self.cursor.execute("select coalesce(max(idCountry),0) from country")
                    idCountry = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(idCountry, strCountry) values(?, ?)"
                    self.cursor.execute(query, (idCountry, country))
                    log.debug("Add country to media, processing: %s" % country)
                
                finally:
                    # Only movies have a country field
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO countrylinkmovie(
                                idCountry, idMovie)

                            VALUES (?, ?)
                            '''
                        )
                        self.cursor.execute(query, (idCountry, kodiid))

    def _getactorid(self, name):
        """
        Crucial für sync speed!
        """
        query = ' '.join((
            "SELECT actor_id",
            "FROM actor",
            "WHERE name = ?",
            "LIMIT 1"
        ))
        self.cursor.execute(query, (name,))
        try:
            actorid = self.cursor.fetchone()[0]
        except TypeError:
            # Cast entry does not exists
            self.cursor.execute("select coalesce(max(actor_id),0) from actor")
            actorid = self.cursor.fetchone()[0] + 1
            query = "INSERT INTO actor(actor_id, name) VALUES (?, ?)"
            self.cursor.execute(query, (actorid, name))
        return actorid

    def _addPerson(self, role, person_type, actorid, kodiid, mediatype,
                   castorder):
        if "Actor" == person_type:
            query = '''
                INSERT OR REPLACE INTO actor_link(
                    actor_id, media_id, media_type, role, cast_order)
                VALUES (?, ?, ?, ?, ?)
            '''
            self.cursor.execute(query, (actorid, kodiid, mediatype, role,
                                        castorder))
            castorder += 1
        elif "Director" == person_type:
            query = '''
                INSERT OR REPLACE INTO director_link(
                    actor_id, media_id, media_type)
                VALUES (?, ?, ?)
                '''
            self.cursor.execute(query, (actorid, kodiid, mediatype))
        elif person_type == "Writer":
            query = '''
                INSERT OR REPLACE INTO writer_link(
                    actor_id, media_id, media_type)
                VALUES (?, ?, ?)
            '''
            self.cursor.execute(query, (actorid, kodiid, mediatype))
        elif "Artist" == person_type:
            query = '''
                INSERT OR REPLACE INTO actor_link(
                    actor_id, media_id, media_type)
                VALUES (?, ?, ?)
            '''
            self.cursor.execute(query, (actorid, kodiid, mediatype))
        return castorder

    def addPeople(self, kodiid, people, mediatype):
        castorder = 1
        for person in people:
            # Kodi Isengard, Jarvis, Krypton
            if v.KODIVERSION > 14:
                actorid = self._getactorid(person['Name'])
                # Link person to content
                castorder = self._addPerson(person.get('Role'),
                                            person['Type'],
                                            actorid,
                                            kodiid,
                                            mediatype,
                                            castorder)
            # Kodi Helix
            else:
                query = ' '.join((

                    "SELECT idActor",
                    "FROM actors",
                    "WHERE strActor = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (person['Name'],))
                try:
                    actorid = self.cursor.fetchone()[0]
                except TypeError:
                    # Cast entry does not exists
                    self.cursor.execute("select coalesce(max(idActor),0) from actors")
                    actorid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO actors(idActor, strActor) values(?, ?)"
                    self.cursor.execute(query, (actorid, person['Name']))
                finally:
                    # Link person to content
                    if "Actor" == person['Type']:
                        role = person.get('Role')

                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkmovie(
                                    idActor, idMovie, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif "tvshow" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinktvshow(
                                    idActor, idShow, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkepisode(
                                    idActor, idEpisode, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        else:
                            # Item is invalid
                            return
                        self.cursor.execute(query, (actorid, kodiid, role, castorder))
                        castorder += 1

                    elif "Director" == person['Type']:
                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmovie(
                                    idDirector, idMovie)

                                VALUES (?, ?)
                                '''
                            )
                        elif "tvshow" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinktvshow(
                                    idDirector, idShow)

                                VALUES (?, ?)
                                '''
                            )
                        elif "musicvideo" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmusicvideo(
                                    idDirector, idMVideo)

                                VALUES (?, ?)
                                '''
                            )

                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkepisode(
                                    idDirector, idEpisode)

                                VALUES (?, ?)
                                '''
                            )
                        else: return # Item is invalid

                        self.cursor.execute(query, (actorid, kodiid))

                    elif person['Type'] == "Writer":
                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkmovie(
                                    idWriter, idMovie)

                                VALUES (?, ?)
                                '''
                            )
                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkepisode(
                                    idWriter, idEpisode)

                                VALUES (?, ?)
                                '''
                            )
                        else:
                            # Item is invalid
                            return
                        self.cursor.execute(query, (actorid, kodiid))
                    elif "Artist" == person['Type']:
                        query = (
                            '''
                            INSERT OR REPLACE INTO artistlinkmusicvideo(
                                idArtist, idMVideo)
                            VALUES (?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid))

            # Add person image to art table
            if person['imageurl']:
                self.artwork.addOrUpdateArt(person['imageurl'], actorid,
                                            person['Type'].lower(), "thumb",
                                            self.cursor)

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

    def addGenres(self, kodiid, genres, mediatype):

        
        # Kodi Isengard, Jarvis, Krypton
        if v.KODIVERSION > 14:
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM genre_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype,))

            # Add genres
            for genre in genres:
                
                query = ' '.join((

                    "SELECT genre_id",
                    "FROM genre",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                
                try:
                    genre_id = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    self.cursor.execute("select coalesce(max(genre_id),0) from genre")
                    genre_id = self.cursor.fetchone()[0] + 1
                    
                    query = "INSERT INTO genre(genre_id, name) values(?, ?)"
                    self.cursor.execute(query, (genre_id, genre))
                    log.debug("Add Genres to media, processing: %s" % genre)
                
                finally:
                    # Assign genre to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO genre_link(
                            genre_id, media_id, media_type)

                        VALUES (?, ?, ?)
                        '''
                    )
                    self.cursor.execute(query, (genre_id, kodiid, mediatype))
        else:
            # Kodi Helix
            # Delete current genres for clean slate
            if "movie" in mediatype:
                self.cursor.execute("DELETE FROM genrelinkmovie WHERE idMovie = ?", (kodiid,))
            elif "tvshow" in mediatype:
                self.cursor.execute("DELETE FROM genrelinktvshow WHERE idShow = ?", (kodiid,))
            elif "musicvideo" in mediatype:
                self.cursor.execute("DELETE FROM genrelinkmusicvideo WHERE idMVideo = ?", (kodiid,))

            # Add genres
            for genre in genres:

                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                
                try:
                    idGenre = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
                    idGenre = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (idGenre, genre))
                    log.debug("Add Genres to media, processing: %s" % genre)
                
                finally:
                    # Assign genre to item
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmovie(
                                idGenre, idMovie)

                            VALUES (?, ?)
                            '''
                        )
                    elif "tvshow" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinktvshow(
                                idGenre, idShow)

                            VALUES (?, ?)
                            '''
                        )
                    elif "musicvideo" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmusicvideo(
                                idGenre, idMVideo)

                            VALUES (?, ?)
                            '''
                        )
                    else: return # Item is invalid
                        
                    self.cursor.execute(query, (idGenre, kodiid))

    def addStudios(self, kodiid, studios, mediatype):
        for studio in studios:
            if v.KODIVERSION > 14:
                # Kodi Isengard, Jarvis, Krypton
                query = ' '.join((

                    "SELECT studio_id",
                    "FROM studio",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (studio,))
                try:
                    studioid = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Studio does not exists.
                    self.cursor.execute("select coalesce(max(studio_id),0) from studio")
                    studioid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(studio_id, name) values(?, ?)"
                    self.cursor.execute(query, (studioid, studio))
                    log.debug("Add Studios to media, processing: %s" % studio)

                finally: # Assign studio to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO studio_link(
                            studio_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        ''')
                    self.cursor.execute(query, (studioid, kodiid, mediatype))
            else:
                # Kodi Helix
                query = ' '.join((

                    "SELECT idstudio",
                    "FROM studio",
                    "WHERE strstudio = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (studio,))
                try:
                    studioid = self.cursor.fetchone()[0]

                except TypeError:
                    # Studio does not exists.
                    self.cursor.execute("select coalesce(max(idstudio),0) from studio")
                    studioid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(idstudio, strstudio) values(?, ?)"
                    self.cursor.execute(query, (studioid, studio))
                    log.debug("Add Studios to media, processing: %s" % studio)

                finally: # Assign studio to item
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmovie(idstudio, idMovie) 
                            VALUES (?, ?)
                            ''')
                    elif "musicvideo" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmusicvideo(idstudio, idMVideo) 
                            VALUES (?, ?)
                            ''')
                    elif "tvshow" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinktvshow(idstudio, idShow) 
                            VALUES (?, ?)
                            ''')
                    elif "episode" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkepisode(idstudio, idEpisode) 
                            VALUES (?, ?)
                            ''')
                    self.cursor.execute(query, (studioid, kodiid))

    def addStreams(self, fileid, streamdetails, runtime):
        
        # First remove any existing entries
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (fileid,))
        if streamdetails:
            # Video details
            for videotrack in streamdetails['video']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strVideoCodec, fVideoAspect, 
                        iVideoWidth, iVideoHeight, iVideoDuration ,strStereoMode)
                    
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (fileid, 0, videotrack['codec'],
                    videotrack['aspect'], videotrack['width'], videotrack['height'],
                    runtime ,videotrack['video3DFormat']))
            
            # Audio details
            for audiotrack in streamdetails['audio']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage)
                    
                    VALUES (?, ?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (fileid, 1, audiotrack['codec'],
                    audiotrack['channels'], audiotrack['language']))

            # Subtitles details
            for subtitletrack in streamdetails['subtitle']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strSubtitleLanguage)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (fileid, 2, subtitletrack))

    def getResumes(self):
        """
        VIDEOS

        Returns all Kodi idFile that have a resume point set (not unwatched
        ones or items that have already been completely watched)
        """
        cursor = self.cursor

        query = ' '.join((
            "SELECT idFile",
            "FROM bookmark"
        ))
        try:
            rows = cursor.execute(query)
        except:
            return []
        ids = []
        for row in rows:
            ids.append(row[0])
        return ids

    def getUnplayedMusicItems(self):
        """
        MUSIC

        Returns all Kodi Item idFile that have not yet been completely played
        """
        query = ' '.join((
            "SELECT idSong",
            "FROM song",
            "WHERE iTimesPlayed = ?"
        ))
        try:
            rows = self.cursor.execute(query, (0, ))
        except:
            return []
        ids = []
        for row in rows:
            ids.append(row[0])
        return ids

    def getIdFromFilename(self, filename, path):
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
            log.info('Did not find any file, abort')
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
            log.info('Did not find matching paths, abort')
            return
        # Kodi seems to make ONE temporary entry; we only want the earlier,
        # permanent one
        if len(result) > 2:
            log.warn('We found too many items with matching filenames and '
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
                log.warn('Unexpectantly did not find a match!')
                return
        return itemId, typus

    def getUnplayedItems(self):
        """
        VIDEOS

        Returns all Kodi Item idFile that have not yet been completely played
        """
        query = ' '.join((
            "SELECT idFile",
            "FROM files",
            "WHERE playCount IS NULL OR playCount = ''"
        ))
        try:
            rows = self.cursor.execute(query)
        except:
            return []
        ids = []
        for row in rows:
            ids.append(row[0])
        return ids

    def getVideoRuntime(self, kodiid, mediatype):
        if mediatype == v.KODI_TYPE_MOVIE:
            query = ' '.join((
                "SELECT c11",
                "FROM movie",
                "WHERE idMovie = ?",
            ))
        elif mediatype == v.KODI_TYPE_EPISODE:
            query = ' '.join((
                "SELECT c09",
                "FROM episode",
                "WHERE idEpisode = ?",
            ))
        self.cursor.execute(query, (kodiid,))
        try:
            runtime = self.cursor.fetchone()[0]
        except TypeError:
            return None
        return int(runtime)

    def addPlaystate(self, fileid, resume_seconds, total_seconds, playcount, dateplayed):
        # Delete existing resume point
        query = ' '.join((

            "DELETE FROM bookmark",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (fileid,))
        
        # Set watched count
        query = ' '.join((

            "UPDATE files",
            "SET playCount = ?, lastPlayed = ?",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (playcount, dateplayed, fileid))
        
        # Set the resume bookmark
        if resume_seconds:
            self.cursor.execute("select coalesce(max(idBookmark),0) from bookmark")
            bookmarkId =  self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO bookmark(
                    idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type)
                
                VALUES (?, ?, ?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (bookmarkId, fileid, resume_seconds, total_seconds,
                "DVDPlayer", 1))

    def addTags(self, kodiid, tags, mediatype):
        # First, delete any existing tags associated to the id
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "DELETE FROM tag_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "DELETE FROM taglinks",
                "WHERE idMedia = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype))
    
        # Add tags
        log.debug("Adding Tags: %s" % tags)
        for tag in tags:
            self.addTag(kodiid, tag, mediatype)

    def addTag(self, kodiid, tag, mediatype):
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tag,))
            try:
                tag_id = self.cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag, because it does not exist
                tag_id = self.createTag(tag)
                log.debug("Adding tag: %s" % tag)

            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO tag_link(
                        tag_id, media_id, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (tag_id, kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tag,))
            try:
                tag_id = self.cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag
                tag_id = self.createTag(tag)
                log.debug("Adding tag: %s" % tag)
            
            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO taglinks(
                        idTag, idMedia, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (tag_id, kodiid, mediatype))

    def createTag(self, name):
        # This will create and return the tag_id
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
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
                self.cursor.execute("select coalesce(max(tag_id),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(tag_id, name) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create tag_id: %s name: %s" % (tag_id, name))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                tag_id = self.cursor.fetchone()[0]

            except TypeError:
                self.cursor.execute("select coalesce(max(idTag),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create idTag: %s name: %s" % (tag_id, name))

        return tag_id

    def updateTag(self, oldtag, newtag, kodiid, mediatype):
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
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
        else:
            # Kodi Helix
            try:
                query = ' '.join((

                    "UPDATE taglinks",
                    "SET idTag = ?",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception as e:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, oldtag,))

    def removeTag(self, kodiid, tagname, mediatype):
        if v.KODIVERSION > 14:
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tagname,))
            try:
                tag_id = self.cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, tag_id,))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tagname,))
            try:
                tag_id = self.cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, tag_id,))

    def addSets(self, movieid, collections, kodicursor):
        for setname in collections:
            setid = self.createBoxset(setname)
            self.assignBoxset(setid, movieid)

    def createBoxset(self, boxsetname):

        log.debug("Adding boxset: %s" % boxsetname)
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
            self.cursor.execute("select coalesce(max(idSet),0) from sets")
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
            self.cursor.execute("select coalesce(max(idSeason),0) from seasons")
            seasonid = self.cursor.fetchone()[0] + 1
            query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
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
                self.cursor.execute("select coalesce(max(idArtist),0) from artist")
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
            self.cursor.execute("select coalesce(max(idAlbum),0) from album")
            albumid = self.cursor.fetchone()[0] + 1
            if v.KODIVERSION > 14:
                query = (
                    '''
                    INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (albumid, name, musicbrainz, "album"))
            else: # Helix
                query = (
                    '''
                    INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (albumid, name, musicbrainz))

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
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
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
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
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
        query = ('''UPDATE %s SET userrating = ? WHERE %s = ?'''
                 % (kodi_type, ID))
        self.cursor.execute(query, (userrating, kodi_id))

    def create_entry_uniqueid(self):
        self.cursor.execute(
            "select coalesce(max(uniqueid_id),0) from uniqueid")
        return self.cursor.fetchone()[0] + 1

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
            uniqueid = None
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

    def create_entry_rating(self):
        self.cursor.execute("select coalesce(max(rating_id),0) from rating")
        return self.cursor.fetchone()[0] + 1

    def get_ratingid(self, kodi_id, kodi_type):
        query = '''
            SELECT rating_id FROM rating
            WHERE media_id = ? AND media_type = ?
        '''
        self.cursor.execute(query, (kodi_id, kodi_type))
        try:
            ratingid = self.cursor.fetchone()[0]
        except TypeError:
            ratingid = None
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


def get_kodiid_from_filename(file):
    """
    Returns the tuple (kodiid, type) if we have a video in the database with
    said filename, or (None, None)
    """
    kodiid = None
    typus = None
    try:
        filename = file.rsplit('/', 1)[1]
        path = file.rsplit('/', 1)[0] + '/'
    except IndexError:
        filename = file.rsplit('\\', 1)[1]
        path = file.rsplit('\\', 1)[0] + '\\'
    log.debug('Trying to figure out playing item from filename: %s '
              'and path: %s' % (filename, path))
    with GetKodiDB('video') as kodi_db:
        try:
            kodiid, typus = kodi_db.getIdFromFilename(filename, path)
        except TypeError:
            log.info('No kodi video element found with filename %s' % filename)
    return (kodiid, typus)

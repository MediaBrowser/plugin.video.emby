# -*- coding: utf-8 -*-

###############################################################################

import urllib
from ntpath import dirname
from datetime import datetime

import xbmc
import xbmcgui
import xbmcvfs

import api
import artwork
import downloadutils
import utils
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver

import PlexAPI
from PlexFunctions import GetPlexMetadata

###############################################################################


@utils.logging
class Items(object):
    """
    Items to be called with "with Items() as xxx:" to ensure that __enter__
    method is called (opens db connections)

    Input:
        kodiType:       optional argument; e.g. 'video' or 'music'
    """

    def __init__(self):
        self.doUtils = downloadutils.DownloadUtils()
        self.kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
        self.directpath = utils.settings('useDirectPaths') == "1"
        self.music_enabled = utils.settings('enableMusic') == "true"
        self.contentmsg = utils.settings('newContent') == "true"
        self.newvideo_time = int(utils.settings('newvideotime'))*1000
        self.newmusic_time = int(utils.settings('newmusictime'))*1000

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()

    def __enter__(self):
        """
        Open DB connections and cursors
        """
        self.embyconn = utils.kodiSQL('emby')
        self.embycursor = self.embyconn.cursor()
        self.kodiconn = utils.kodiSQL('video')
        self.kodicursor = self.kodiconn.cursor()
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Make sure DB changes are committed and connection to DB is closed.
        """
        self.embyconn.commit()
        self.kodiconn.commit()
        self.embyconn.close()
        self.kodiconn.close()
        return self

    def itemsbyId(self, items, process, pdialog=None):
        # Process items by itemid. Process can be added, update, userdata, remove
        emby = self.emby
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        music_enabled = self.music_enabled
        
        itemtypes = {

            'Movie': Movies,
            'BoxSet': Movies,
            'Series': TVShows,
            'Season': TVShows,
            'Episode': TVShows,
            'MusicAlbum': Music,
            'MusicArtist': Music,
            'AlbumArtist': Music,
            'Audio': Music
        }

        update_videolibrary = False
        total = 0
        for item in items:
            total += len(items[item])

        if total == 0:
            return False

        self.logMsg("Processing %s: %s" % (process, items), 1)
        if pdialog:
            pdialog.update(heading="Processing %s: %s items" % (process, total))

        count = 0
        for itemtype in items:

            # Safety check
            if not itemtypes.get(itemtype):
                # We don't process this type of item
                continue

            itemlist = items[itemtype]
            if not itemlist:
                # The list to process is empty
                continue

            musicconn = None

            if itemtype in ('MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                if music_enabled:
                    musicconn = utils.kodiSQL('music')
                    musiccursor = musicconn.cursor()
                    items_process = itemtypes[itemtype](embycursor, musiccursor)
                else:
                    # Music is not enabled, do not proceed with itemtype
                    continue
            else:
                update_videolibrary = True
                items_process = itemtypes[itemtype](embycursor, kodicursor)

            if itemtype == "Movie":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "BoxSet":
                actions = {
                    'added': items_process.added_boxset,
                    'update': items_process.add_updateBoxset,
                    'remove': items_process.remove
                }
            elif itemtype == "MusicVideo":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "Series":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "Season":
                actions = {
                    'added': items_process.added_season,
                    'update': items_process.add_updateSeason,
                    'remove': items_process.remove
                }
            elif itemtype == "Episode":
                actions = {
                    'added': items_process.added_episode,
                    'update': items_process.add_updateEpisode,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "MusicAlbum":
                actions = {
                    'added': items_process.added_album,
                    'update': items_process.add_updateAlbum,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype in ("MusicArtist", "AlbumArtist"):
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_updateArtist,
                    'remove': items_process.remove
                }
            elif itemtype == "Audio":
                actions = {
                    'added': items_process.added_song,
                    'update': items_process.add_updateSong,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            else:
                self.logMsg("Unsupported itemtype: %s." % itemtype, 1)
                actions = {}

            if actions.get(process):

                if process == "remove":
                    for item in itemlist:
                        actions[process](item)

                elif process == "added":
                    actions[process](itemlist, pdialog)
            
                else:
                    processItems = emby.getFullItems(itemlist)
                    for item in processItems:

                        title = item['Name']

                        if itemtype == "Episode":
                            title = "%s - %s" % (item['SeriesName'], title)

                        if pdialog:
                            percentage = int((float(count) / float(total))*100)
                            pdialog.update(percentage, message=title)
                            count += 1

                        actions[process](item)


            if musicconn is not None:
                # close connection for special types
                self.logMsg("Updating music database.", 1)
                musicconn.commit()
                musiccursor.close()

        return (True, update_videolibrary)

    def contentPop(self, name, time=5000):
        xbmcgui.Dialog().notification(
                heading="Emby for Kodi",
                message="Added: %s" % name,
                icon="special://home/addons/plugin.video.plexkodiconnect/icon.png",
                time=time,
                sound=False)

    def updateUserdata(self, xml):
        """
        Updates the Kodi watched state of the item from PMS. Also retrieves
        Plex resume points for movies in progress.
        """
        for mediaitem in xml:
            API = PlexAPI.API(mediaitem)
            # Get key and db entry on the Kodi db side
            try:
                fileid = self.emby_db.getItem_byId(API.getRatingKey())[1]
            except:
                continue
            # Grab the user's viewcount, resume points etc. from PMS' answer
            userdata = API.getUserData()
            # Write to Kodi DB
            self.kodi_db.addPlaystate(fileid,
                                      userdata['Resume'],
                                      userdata['Runtime'],
                                      userdata['PlayCount'],
                                      userdata['LastPlayedDate'])


class Movies(Items):

    def added(self, items, pdialog):

        total = len(items)
        count = 0
        for movie in items:
                
            title = movie['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(movie)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)

    def added_boxset(self, items, pdialog):

        total = len(items)
        count = 0
        for boxset in items:

            title = boxset['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateBoxset(boxset)

    def add_update(self, item, viewtag=None, viewid=None):
        # Process single movie
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full
        # item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = API.getRatingKey()
        # Cannot parse XML, abort
        if not itemid:
            self.logMsg("Cannot parse XML data for movie", -1)
            return
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            movieid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]

        except TypeError:
            # movieid
            update_item = False
            kodicursor.execute("select coalesce(max(idMovie),0) from movie")
            movieid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM movie WHERE idMovie = ?"
            kodicursor.execute(query, (movieid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                self.logMsg("movieid: %s missing from Kodi, repairing the entry." % movieid, 1)

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = userdata['Resume']
        runtime = userdata['Runtime']

        # item details
        people = API.getPeople()
        writer = API.joinList(people['Writer'])
        director = API.joinList(people['Director'])
        genres = API.getGenres()
        genre = API.joinList(genres)
        title, sorttitle = API.getTitle()
        plot = API.getPlot()
        shortplot = None
        tagline = API.getTagline()
        votecount = None

        rating = API.getAudienceRating()
        year = API.getYear()
        imdb = API.getProvider('imdb')
        mpaa = API.getMpaa()
        countries = API.getCountry()
        country = API.joinList(countries)
        studios = API.getStudios()
        try:
            studio = studios[0]
        except IndexError:
            studio = None

        # Find one trailer
        trailer = None
        extras = API.getExtras()
        for extra in extras:
            # Only get 1st trailer element
            if extra['extraType'] == '1':
                trailer = ("plugin://plugin.video.plexkodiconnect/trailer/?"
                           "id=%s&mode=play") % extra['key']
                self.logMsg("Trailer for %s: %s" % (itemid, trailer), 2)
                break

        ##### GET THE FILE AND PATH #####
        playurl = API.getKey()
        filename = playurl
        # if "\\" in playurl:
        #     # Local path
        #     filename = playurl.rsplit("\\", 1)[1]
        # else: # Network share
        #     filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.plexkodiconnect.movies/"
            params = {

                #'filename': filename.encode('utf-8'),
                'filename': filename,
                'id': itemid,
                'dbid': movieid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))
        ##### UPDATE THE MOVIE #####
        if update_item:
            self.logMsg("UPDATE movie itemid: %s - Title: %s" % (itemid, title), 1)

            # Update the movie entry
            query = ' '.join((
                
                "UPDATE movie",
                "SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?,",
                    "c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?,",
                    "c16 = ?, c18 = ?, c19 = ?, c21 = ?",
                "WHERE idMovie = ?"
            ))
            kodicursor.execute(query, (title, plot, shortplot, tagline, votecount, rating, writer,
                year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailer,
                country, movieid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE MOVIE #####
        else:
            self.logMsg("ADD movie itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)
            # Add the file
            fileid = kodi_db.addFile(filename, pathid)
            
            # Create the movie entry
            query = (
                '''
                INSERT INTO movie(
                    idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07, 
                    c09, c10, c11, c12, c14, c15, c16, c18, c19, c21)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (movieid, fileid, title, plot, shortplot, tagline, votecount,
                rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title,
                studio, trailer, country))

            # Create the reference in emby table
            emby_db.addReference(itemid, movieid, "Movie", "movie", fileid, pathid, None, checksum, viewid)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, "movies", "metadata.local", 1, pathid))

        # Update the file
        query = ' '.join((

            "UPDATE files",
            "SET idPath = ?, strFilename = ?, dateAdded = ?",
            "WHERE idFile = ?"
        ))
        kodicursor.execute(query, (pathid, filename, dateadded, fileid))
        
        # Process countries
        kodi_db.addCountries(movieid, countries, "movie")
        # Process cast
        people = API.getPeopleList()
        kodi_db.addPeople(movieid, people, "movie")
        # Process genres
        kodi_db.addGenres(movieid, genres, "movie")
        # Process artwork
        allartworks = API.getAllArtwork()
        artwork.addArtwork(allartworks, movieid, "movie", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        kodi_db.addStudios(movieid, studios, "movie")
        # Process tags: view, emby tags
        tags = [viewtag]
        # tags.extend(item['Tags'])
        # if userdata['Favorite']:
        #     tags.append("Favorite movies")
        kodi_db.addTags(movieid, tags, "movie")
        # Process playstates
        kodi_db.addPlaystate(fileid, resume, runtime, playcount, dateplayed)

    def remove(self, itemid):
        # Remove movieid, fileid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            mediatype = emby_dbitem[4]
            self.logMsg("Removing %sid: %s fileid: %s" % (mediatype, kodiid, fileid), 1)
        except TypeError:
            return

        # Remove the emby reference
        emby_db.removeItem(itemid)
        # Remove artwork
        artwork.deleteArtwork(kodiid, mediatype, kodicursor)

        if mediatype == "movie":
            # Delete kodi movie and file
            kodicursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodiid,))
            kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))

        elif mediatype == "set":
            # Delete kodi boxset
            boxset_movies = emby_db.getItem_byParentId(kodiid, "movie")
            for movie in boxset_movies:
                embyid = movie[0]
                movieid = movie[1]
                self.kodi_db.removefromBoxset(movieid)
                # Update emby reference
                emby_db.updateParentId(embyid, None)

            kodicursor.execute("DELETE FROM sets WHERE idSet = ?", (kodiid,))

        self.logMsg("Deleted %s %s from kodi database" % (mediatype, itemid), 1)


class MusicVideos(Items):

    
    def __init__(self, embycursor, kodicursor):
        Items.__init__(self, embycursor, kodicursor)

    def added(self, items, pdialog):

        total = len(items)
        count = 0
        for mvideo in items:

            title = mvideo['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(mvideo)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single music video
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = api.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            self.logMsg("mvideoid: %s fileid: %s pathid: %s" % (mvideoid, fileid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("mvideoid: %s not found." % itemid, 2)
            # mvideoid
            kodicursor.execute("select coalesce(max(idMVideo),0) from musicvideo")
            mvideoid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM musicvideo WHERE idMVideo = ?"
            kodicursor.execute(query, (mvideoid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                self.logMsg("mvideoid: %s missing from Kodi, repairing the entry." % mvideoid, 1)

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        runtime = API.getRuntime()
        plot = API.getOverview()
        title = item['Name']
        year = item.get('ProductionYear')
        genres = item['Genres']
        genre = " / ".join(genres)
        studios = API.getStudios()
        studio = " / ".join(studios)
        artist = " / ".join(item.get('Artists'))
        album = item.get('Album')
        track = item.get('Track')
        people = API.getPeople()
        director = " / ".join(people['Director'])

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getKey()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.plexkodiconnect.musicvideos/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': mvideoid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MUSIC VIDEO #####
        if update_item:
            self.logMsg("UPDATE mvideo itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Update path
            query = "UPDATE path SET strPath = ? WHERE idPath = ?"
            kodicursor.execute(query, (path, pathid))

            # Update the filename
            query = "UPDATE files SET strFilename = ?, dateAdded = ? WHERE idFile = ?"
            kodicursor.execute(query, (filename, dateadded, fileid))

            # Update the music video entry
            query = ' '.join((
                
                "UPDATE musicvideo",
                "SET c00 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?,",
                    "c11 = ?, c12 = ?"
                "WHERE idMVideo = ?"
            ))
            kodicursor.execute(query, (title, runtime, director, studio, year, plot, album,
                artist, genre, track, mvideoid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE MUSIC VIDEO #####
        else:
            self.logMsg("ADD mvideo itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            query = ' '.join((

                "SELECT idPath",
                "FROM path",
                "WHERE strPath = ?"
            ))
            kodicursor.execute(query, (path,))
            try:
                pathid = kodicursor.fetchone()[0]
            except TypeError:
                kodicursor.execute("select coalesce(max(idPath),0) from path")
                pathid = kodicursor.fetchone()[0] + 1
                query = (
                    '''
                    INSERT OR REPLACE INTO path(
                        idPath, strPath, strContent, strScraper, noUpdate)

                    VALUES (?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (pathid, path, "musicvideos", "metadata.local", 1))

            # Add the file
            kodicursor.execute("select coalesce(max(idFile),0) from files")
            fileid = kodicursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO files(
                    idFile, idPath, strFilename, dateAdded)

                VALUES (?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (fileid, pathid, filename, dateadded))
            
            # Create the musicvideo entry
            query = (
                '''
                INSERT INTO musicvideo(
                    idMVideo, idFile, c00, c04, c05, c06, c07, c08, c09, c10, c11, c12)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (mvideoid, fileid, title, runtime, director, studio,
                year, plot, album, artist, genre, track))

            # Create the reference in emby table
            emby_db.addReference(itemid, mvideoid, "MusicVideo", "musicvideo", fileid, pathid,
                checksum=checksum, mediafolderid=viewid)

        
        # Process cast
        people = item['People']
        artists = item['ArtistItems']
        for artist in artists:
            artist['Type'] = "Artist"
        people.extend(artists)
        people = artwork.getPeopleArtwork(people)
        kodi_db.addPeople(mvideoid, people, "musicvideo")
        # Process genres
        kodi_db.addGenres(mvideoid, genres, "musicvideo")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), mvideoid, "musicvideo", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        kodi_db.addStudios(mvideoid, studios, "musicvideo")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite musicvideos")
        kodi_db.addTags(mvideoid, tags, "musicvideo")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        API = api.API(item)
        
        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            self.logMsg(
                "Update playstate for musicvideo: %s fileid: %s"
                % (item['Name'], fileid), 1)
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            kodi_db.addTag(mvideoid, "Favorite musicvideos", "musicvideo")
        else:
            kodi_db.removeTag(mvideoid, "Favorite musicvideos", "musicvideo")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)

        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove mvideoid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            self.logMsg("Removing mvideoid: %s fileid: %s" % (mvideoid, fileid, pathid), 1)
        except TypeError:
            return

        # Remove artwork
        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = 'musicvideo'"
        ))
        kodicursor.execute(query, (mvideoid,))
        rows = kodicursor.fetchall()
        for row in rows:
            
            url = row[0]
            imagetype = row[1]
            if imagetype in ("poster", "fanart"):
                artwork.deleteCachedArtwork(url)

        kodicursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (mvideoid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        if self.directpath:
            kodicursor.execute("DELETE FROM path WHERE idPath = ?", (pathid,))
        self.embycursor.execute("DELETE FROM emby WHERE emby_id = ?", (itemid,))

        self.logMsg("Deleted musicvideo %s from kodi database" % itemid, 1)


class TVShows(Items):
    def added(self, items, pdialog):
        
        total = len(items)
        count = 0
        for tvshow in items:

            title = tvshow['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(tvshow)
            # Add episodes
            all_episodes = self.emby.getEpisodesbyShow(tvshow['Id'])
            self.added_episode(all_episodes['Items'], pdialog)

    def added_season(self, items, pdialog):
        
        total = len(items)
        count = 0
        for season in items:

            title = "%s - %s" % (season.get('SeriesName', "Unknown"), season['Name'])
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateSeason(season)
            # Add episodes
            all_episodes = self.emby.getEpisodesbySeason(season['Id'])
            self.added_episode(all_episodes['Items'], pdialog)

    def added_episode(self, items, pdialog):
        
        total = len(items)
        count = 0
        for episode in items:
            title = "%s - %s" % (episode.get('SeriesName', "Unknown"), episode['Name'])
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateEpisode(episode)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)

    def add_update(self, item, viewtag=None, viewid=None):
        # Process single tvshow
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        update_item = True
        itemid = API.getRatingKey()
        if not itemid:
            self.logMsg("Cannot parse XML data for TV show", -1)
            return
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        force_episodes = False
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            showid = emby_dbitem[0]
            pathid = emby_dbitem[2]
        except TypeError:
            update_item = False
            kodicursor.execute("select coalesce(max(idShow),0) from tvshow")
            showid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM tvshow WHERE idShow = ?"
            kodicursor.execute(query, (showid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                self.logMsg("showid: %s missing from Kodi, repairing the entry." % showid, 1)
                # Force re-add episodes after the show is re-created.
                force_episodes = True

        if viewtag is None or viewid is None:
            # Get view tag from emby
            viewtag, viewid, mediatype = embyserver.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

        # fileId information
        checksum = API.getChecksum()

        # item details
        genres = API.getGenres()
        title, sorttitle = API.getTitle()
        plot = API.getPlot()
        rating = API.getAudienceRating()
        premieredate = API.getPremiereDate()
        tvdb = API.getProvider('Tvdb')
        mpaa = API.getMpaa()
        genre = API.joinList(genres)
        studios = API.getStudios()
        try:
            studio = studios[0]
        except IndexError:
            studio = None

        # GET THE FILE AND PATH #####
        playurl = API.getKey()

        if self.directpath:
            # Direct paths is set the Kodi way
            if "\\" in playurl:
                # Local path
                path = "%s\\" % playurl
                toplevelpath = "%s\\" % dirname(dirname(path))
            else:
                # Network path
                path = "%s/" % playurl
                toplevelpath = "%s/" % dirname(dirname(path))

            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(path):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False

            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path
            toplevelpath = "plugin://plugin.video.plexkodiconnect.tvshows/"
            path = "%s%s/" % (toplevelpath, itemid)

        # UPDATE THE TVSHOW #####
        if update_item:
            self.logMsg("UPDATE tvshow itemid: %s - Title: %s" % (itemid, title), 1)

            # Update the tvshow entry
            query = ' '.join((
                
                "UPDATE tvshow",
                "SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?,",
                    "c12 = ?, c13 = ?, c14 = ?, c15 = ?",
                "WHERE idShow = ?"
            ))
            kodicursor.execute(query, (title, plot, rating, premieredate, genre, title,
                tvdb, mpaa, studio, sorttitle, showid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE TVSHOW #####
        else:
            self.logMsg("ADD tvshow itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add top path
            toppathid = kodi_db.addPath(toplevelpath)
            query = ' '.join((

                "UPDATE path",
                "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
                "WHERE idPath = ?"
            ))
            kodicursor.execute(query, (toplevelpath, "tvshows", "metadata.local", 1, toppathid))
            
            # Add path
            pathid = kodi_db.addPath(path)
            
            # Create the tvshow entry
            query = (
                '''
                INSERT INTO tvshow(
                    idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15) 

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (showid, title, plot, rating, premieredate, genre,
                title, tvdb, mpaa, studio, sorttitle))

            # Link the path
            query = "INSERT INTO tvshowlinkpath(idShow, idPath) values(?, ?)"
            kodicursor.execute(query, (showid, pathid))

            # Create the reference in emby table
            emby_db.addReference(itemid, showid, "Series", "tvshow", pathid=pathid,
                                checksum=checksum, mediafolderid=viewid)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, None, None, 1, pathid))
        
        # Process cast
        people = API.getPeopleList()
        kodi_db.addPeople(showid, people, "tvshow")
        # Process genres
        kodi_db.addGenres(showid, genres, "tvshow")
        # Process artwork
        allartworks = API.getAllArtwork()
        artwork.addArtwork(allartworks, showid, "tvshow", kodicursor)
        # Process studios
        kodi_db.addStudios(showid, studios, "tvshow")
        # Process tags: view, emby tags
        tags = [viewtag]
        kodi_db.addTags(showid, tags, "tvshow")

        if force_episodes:
            # We needed to recreate the show entry. Re-add episodes now.
            self.logMsg("Repairing episodes for showid: %s %s" % (showid, title), 1)
            all_episodes = embyserver.getEpisodesbyShow(itemid)
            self.added_episode(all_episodes['Items'], None)

    def add_updateSeason(self, item, viewid=None, viewtag=None):
        API = PlexAPI.API(item)
        showid = viewid
        itemid = API.getRatingKey()
        if not itemid:
            self.logMsg('Error getting itemid for season, skipping', -1)
            return
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        seasonnum = API.getIndex()
        seasonid = kodi_db.addSeason(showid, seasonnum)
        checksum = API.getChecksum()
        # Check whether Season already exists
        update_item = True
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            embyDbItemId = emby_dbitem[0]
        except TypeError:
            update_item = False

        # Process artwork
        allartworks = API.getAllArtwork()
        artwork.addArtwork(allartworks, seasonid, "season", kodicursor)

        if update_item:
            # Update a reference: checksum in emby table
            emby_db.updateReference(itemid, checksum)
        else:
            # Create the reference in emby table
            emby_db.addReference(itemid, seasonid, "Season", "season", parentid=showid, checksum=checksum)

    def add_updateEpisode(self, item, viewtag=None, viewid=None):
        """
        viewtag and viewid are irrelevant!
        """
        # Process single episode
        kodiversion = self.kodiversion
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full
        # item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = API.getRatingKey()
        if not itemid:
            self.logMsg('Error getting itemid for episode, skipping', -1)
            return
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            episodeid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
        except TypeError:
            update_item = False
            # episodeid
            kodicursor.execute("select coalesce(max(idEpisode),0) from episode")
            episodeid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM episode WHERE idEpisode = ?"
            kodicursor.execute(query, (episodeid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                self.logMsg("episodeid: %s missing from Kodi, repairing the entry." % episodeid, 1)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        peoples = API.getPeople()
        director = API.joinList(peoples['Director'])
        writer = API.joinList(peoples['Writer'])
        cast = API.joinList(peoples['Cast'])
        producer = API.joinList(peoples['Producer'])
        title, sorttitle = API.getTitle()
        plot = API.getPlot()
        rating = API.getAudienceRating()
        resume, runtime = API.getRuntime()
        premieredate = API.getPremiereDate()

        # episode details
        seriesId, seriesName, season, episode = API.getEpisodeDetails()

        if season is None:
            if item.get('AbsoluteEpisodeNumber'):
                # Anime scenario
                season = 1
                episode = item['AbsoluteEpisodeNumber']
            else:
                season = -1

        # Specials ordering within season
        # if item.get('AirsAfterSeasonNumber'):
        #     airsBeforeSeason = item['AirsAfterSeasonNumber']
        #     airsBeforeEpisode = 4096 # Kodi default number for afterseason ordering
        # else:
        #     airsBeforeSeason = item.get('AirsBeforeSeasonNumber', "-1")
        #     airsBeforeEpisode = item.get('AirsBeforeEpisodeNumber', "-1")

        airsBeforeSeason = "-1"
        airsBeforeEpisode = "-1"
        # Append multi episodes to title
        # if item.get('IndexNumberEnd'):
        #     title = "| %02d | %s" % (item['IndexNumberEnd'], title)

        # Get season id
        show = emby_db.getItem_byId(seriesId)
        try:
            showid = show[0]
        except TypeError:
            # self.logMsg("Show is missing from database, trying to add", 2)
            # show = self.emby.getItem(seriesId)
            # self.logMsg("Show now: %s. Trying to add new show" % show, 2)
            # self.add_update(show)
            # show = emby_db.getItem_byId(seriesId)
            # try:
            #     showid = show[0]
            # except TypeError:
            #     self.logMsg("Skipping: %s. Unable to add series: %s." % (itemid, seriesId), -1)
            self.logMsg("Parent tvshow now found, skip item", 2)
            return False
        seasonid = kodi_db.addSeason(showid, season)

        # GET THE FILE AND PATH #####
        playurl = API.getKey()
        filename = playurl

        # if "\\" in playurl:
        #     # Local path
        #     filename = playurl.rsplit("\\", 1)[1]
        # else: # Network share
        #     filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.plexkodiconnect.tvshows/%s/" % seriesId
            params = {

                #'filename': filename.encode('utf-8'),
                'filename': filename,
                'id': itemid,
                'dbid': episodeid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))

        # UPDATE THE EPISODE #####
        if update_item:
            self.logMsg("UPDATE episode itemid: %s" % (itemid), 1)

            # Update the movie entry
            if kodiversion in (16, 17):
                # Kodi Jarvis, Krypton
                query = ' '.join((
                
                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idSeason = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate,
                    runtime, director, season, episode, title, airsBeforeSeason,
                    airsBeforeEpisode, seasonid, episodeid))
            else:
                query = ' '.join((
                    
                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate,
                    runtime, director, season, episode, title, airsBeforeSeason,
                    airsBeforeEpisode, episodeid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
            # Update parentid reference
            emby_db.updateParentId(itemid, seasonid)
        
        ##### OR ADD THE EPISODE #####
        else:
            self.logMsg("ADD episode itemid: %s" % (itemid), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)
            # Add the file
            fileid = kodi_db.addFile(filename, pathid)
            # Create the episode entry
            if kodiversion in (16, 17):
                # Kodi Jarvis, Krypton
                query = (
                    '''
                    INSERT INTO episode(
                        idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                        idShow, c15, c16, idSeason)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (episodeid, fileid, title, plot, rating, writer,
                    premieredate, runtime, director, season, episode, title, showid,
                    airsBeforeSeason, airsBeforeEpisode, seasonid))
            else:
                query = (
                    '''
                    INSERT INTO episode(
                        idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                        idShow, c15, c16)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (episodeid, fileid, title, plot, rating, writer,
                    premieredate, runtime, director, season, episode, title, showid,
                    airsBeforeSeason, airsBeforeEpisode))

            # Create the reference in emby table
            emby_db.addReference(itemid, episodeid, "Episode", "episode", fileid, pathid,
                seasonid, checksum)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, None, None, 1, pathid))
        # Update the file
        query = ' '.join((

            "UPDATE files",
            "SET idPath = ?, strFilename = ?, dateAdded = ?",
            "WHERE idFile = ?"
        ))
        kodicursor.execute(query, (pathid, filename, dateadded, fileid))
        # Process cast
        people = API.getPeopleList()
        kodi_db.addPeople(episodeid, people, "episode")
        # Process artwork
        artworks = API.getAllArtwork()
        artwork.addOrUpdateArt(artworks['Primary'], episodeid, "episode", "thumb", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process playstates
        kodi_db.addPlaystate(fileid, resume, runtime, playcount, dateplayed)
        if not self.directpath and resume:
            # Create additional entry for widgets. This is only required for plugin/episode.
            temppathid = kodi_db.getPath("plugin://plugin.video.plexkodiconnect.tvshows/")
            tempfileid = kodi_db.addFile(filename, temppathid)
            query = ' '.join((

                "UPDATE files",
                "SET idPath = ?, strFilename = ?, dateAdded = ?",
                "WHERE idFile = ?"
            ))
            kodicursor.execute(query, (temppathid, filename, dateadded, tempfileid))
            kodi_db.addPlaystate(tempfileid, resume, runtime, playcount, dateplayed)

    def remove(self, itemid):
        # Remove showid, fileid, pathid, emby reference
        emby_db = self.emby_db
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            parentid = emby_dbitem[3]
            mediatype = emby_dbitem[4]
            self.logMsg("Removing %s kodiid: %s fileid: %s" % (mediatype, kodiid, fileid), 1)
        except TypeError:
            return

        ##### PROCESS ITEM #####

        # Remove the emby reference
        emby_db.removeItem(itemid)


        ##### IF EPISODE #####

        if mediatype == "episode":
            # Delete kodi episode and file, verify season and tvshow
            self.removeEpisode(kodiid, fileid)

            # Season verification
            season = emby_db.getItem_byKodiId(parentid, "season")
            try:
                showid = season[1]
            except TypeError:
                return
            
            season_episodes = emby_db.getItem_byParentId(parentid, "episode")
            if not season_episodes:
                self.removeSeason(parentid)
                emby_db.removeItem(season[0])

            # Show verification
            show = emby_db.getItem_byKodiId(showid, "tvshow")
            query = ' '.join((

                "SELECT totalCount",
                "FROM tvshowcounts",
                "WHERE idShow = ?"
            ))
            kodicursor.execute(query, (showid,))
            result = kodicursor.fetchone()
            if result and result[0] is None:
                # There's no episodes left, delete show and any possible remaining seasons
                seasons = emby_db.getItem_byParentId(showid, "season")
                for season in seasons:
                    self.removeSeason(season[1])
                else:
                    # Delete emby season entries
                    emby_db.removeItems_byParentId(showid, "season")
                self.removeShow(showid)
                emby_db.removeItem(show[0])

        ##### IF TVSHOW #####

        elif mediatype == "tvshow":
            # Remove episodes, seasons, tvshow
            seasons = emby_db.getItem_byParentId(kodiid, "season")
            for season in seasons:
                seasonid = season[1]
                season_episodes = emby_db.getItem_byParentId(seasonid, "episode")
                for episode in season_episodes:
                    self.removeEpisode(episode[1], episode[2])
                else:
                    # Remove emby episodes
                    emby_db.removeItems_byParentId(seasonid, "episode")
            else:
                # Remove emby seasons
                emby_db.removeItems_byParentId(kodiid, "season")

            # Remove tvshow
            self.removeShow(kodiid)

        ##### IF SEASON #####

        elif mediatype == "season":
            # Remove episodes, season, verify tvshow
            season_episodes = emby_db.getItem_byParentId(kodiid, "episode")
            for episode in season_episodes:
                self.removeEpisode(episode[1], episode[2])
            else:
                # Remove emby episodes
                emby_db.removeItems_byParentId(kodiid, "episode")
            
            # Remove season
            self.removeSeason(kodiid)

            # Show verification
            seasons = emby_db.getItem_byParentId(parentid, "season")
            if not seasons:
                # There's no seasons, delete the show
                self.removeShow(parentid)
                emby_db.removeItem_byKodiId(parentid, "tvshow")

        self.logMsg("Deleted %s: %s from kodi database" % (mediatype, itemid), 1)

    def removeShow(self, kodiid):
        
        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "tvshow", kodicursor)
        kodicursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodiid,))
        self.logMsg("Removed tvshow: %s." % kodiid, 2)

    def removeSeason(self, kodiid):
        
        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "season", kodicursor)
        kodicursor.execute("DELETE FROM seasons WHERE idSeason = ?", (kodiid,))
        self.logMsg("Removed season: %s." % kodiid, 2)

    def removeEpisode(self, kodiid, fileid):

        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "episode", kodicursor)
        kodicursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodiid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        self.logMsg("Removed episode: %s." % kodiid, 2)


class Music(Items):

    def __init__(self):
        Items.__init__(self)

        self.directstream = utils.settings('streamMusic') == "true"
        self.enableimportsongrating = utils.settings('enableImportSongRating') == "true"
        self.enableexportsongrating = utils.settings('enableExportSongRating') == "true"
        self.enableupdatesongrating = utils.settings('enableUpdateSongRating') == "true"
        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)

    def __enter__(self):
        """
        OVERWRITE this method, because we need to open another DB.
        Open DB connections and cursors
        """
        self.embyconn = utils.kodiSQL('emby')
        self.embycursor = self.embyconn.cursor()
        # Here it is, not 'video' but 'music'
        self.kodiconn = utils.kodiSQL('music')
        self.kodicursor = self.kodiconn.cursor()
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        return self

    def added(self, items, pdialog):
        
        total = len(items)
        count = 0
        for artist in items:

            title = artist['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateArtist(artist)
            # Add albums
            all_albums = self.emby.getAlbumsbyArtist(artist['Id'])
            self.added_album(all_albums['Items'], pdialog)

    def added_album(self, items, pdialog):
        
        total = len(items)
        count = 0
        for album in items:

            title = album['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateAlbum(album)
            # Add songs
            all_songs = self.emby.getSongsbyAlbum(album['Id'])
            self.added_song(all_songs['Items'], pdialog)

    def added_song(self, items, pdialog):
        
        total = len(items)
        count = 0
        for song in items:

            title = song['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateSong(song)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newmusic_time)

    def add_updateArtist(self, item, viewtag=None, viewid=None,
                         artisttype="MusicArtist"):
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        update_item = True
        itemid = API.getRatingKey()
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            artistid = emby_dbitem[0]
        except TypeError:
            update_item = False

        # The artist details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.getDateCreated()
        checksum = API.getChecksum()

        name, sortname = API.getTitle()
        # musicBrainzId = API.getProvider('MusicBrainzArtist')
        musicBrainzId = None
        genres = API.joinList(API.getGenres())
        bio = API.getPlot()

        # Associate artwork
        artworks = API.getAllArtwork(parentInfo=True)
        thumb = artworks['Primary']
        backdrops = artworks['Backdrop']  # List

        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb
        if backdrops:
            fanart = "<fanart>%s</fanart>" % backdrops[0]
        else:
            fanart = ""

        # UPDATE THE ARTIST #####
        if update_item:
            self.logMsg("UPDATE artist itemid: %s - Name: %s"
                        % (itemid, name), 1)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        # OR ADD THE ARTIST #####
        else:
            self.logMsg("ADD artist itemid: %s - Name: %s" % (itemid, name), 1)
            # safety checks: It looks like Emby supports the same artist
            # multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the
            # artist entries.
            artistid = kodi_db.addArtist(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(
                itemid, artistid, artisttype, "artist", checksum=checksum)

        # Process the artist
        if self.kodiversion in (16, 17):
            query = ' '.join((

                "UPDATE artist",
                "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                    "lastScraped = ?",
                "WHERE idArtist = ?"
            ))
            kodicursor.execute(query, (genres, bio, thumb, fanart,
                                       lastScraped, artistid))
        else:
            query = ' '.join((

                "UPDATE artist",
                "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                    "lastScraped = ?, dateAdded = ?",
                "WHERE idArtist = ?"
            ))
            kodicursor.execute(query, (genres, bio, thumb, fanart, lastScraped,
                                       dateadded, artistid))

        # Update artwork
        artwork.addArtwork(artworks, artistid, "artist", kodicursor)

    def add_updateAlbum(self, item, viewtag=None, viewid=None):
        kodiversion = self.kodiversion
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        update_item = True
        itemid = API.getRatingKey()
        if not itemid:
            self.logMsg('Error processing Album, skipping', -1)
            return
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            albumid = emby_dbitem[0]
        except TypeError:
            # Albumid not found
            update_item = False

        # The album details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        checksum = API.getChecksum()

        name, sorttitle = API.getTitle()
        # musicBrainzId = API.getProvider('MusicBrainzAlbum')
        musicBrainzId = None
        year = API.getYear()
        genres = API.getGenres()
        genre = API.joinList(genres)
        bio = API.getPlot()
        rating = userdata['UserRating']
        # artists = item['AlbumArtists']
        # if not artists:
        #     artists = item['ArtistItems']
        # artistname = []
        # for artist in artists:
        #     artistname.append(artist['Name'])
        artistname = item.attrib.get('parentTitle')
        if not artistname:
            artistname = item.attrib.get('originalTitle')

        # Associate artwork
        artworks = API.getAllArtwork(parentInfo=True)
        thumb = artworks['Primary']
        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb

        # UPDATE THE ALBUM #####
        if update_item:
            self.logMsg("UPDATE album itemid: %s - Name: %s"
                        % (itemid, name), 1)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        # OR ADD THE ALBUM #####
        else:
            self.logMsg("ADD album itemid: %s - Name: %s" % (itemid, name), 1)
            # safety checks: It looks like Emby supports the same artist
            # multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the
            # artist entries.
            albumid = kodi_db.addAlbum(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(
                itemid, albumid, "MusicAlbum", "album", checksum=checksum)

        # Process the album info
        if kodiversion == 17:
            # Kodi Krypton
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iUserrating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb,
                                       rating, lastScraped, "album", albumid))
        elif kodiversion == 16:
            # Kodi Jarvis
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb,
                                       rating, lastScraped, "album", albumid))
        elif kodiversion == 15:
            # Kodi Isengard
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, dateAdded = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb,
                                       rating, lastScraped, dateadded,
                                       "album", albumid))
        else:
            # Kodi Helix
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, dateAdded = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb,
                                       rating, lastScraped, dateadded,
                                       albumid))

        # Associate the parentid for emby reference
        parentId = item.attrib.get('parentRatingKey')
        if parentId is not None:
            emby_dbartist = emby_db.getItem_byId(parentId)
            try:
                artistid = emby_dbartist[0]
            except TypeError:
                self.logMsg('Artist %s does not exist in emby database'
                            % parentId, 1)
                artist = GetPlexMetadata(parentId)
                # Item may not be an artist, verification necessary.
                if artist:
                    if artist[0].attrib.get('type') == "artist":
                        # Update with the parentId, for remove reference
                        emby_db.addReference(
                            parentId, parentId, "MusicArtist", "artist")
                        emby_db.updateParentId(itemid, parentId)
            else:
                # Update emby reference with the artistid
                emby_db.updateParentId(itemid, artistid)

        # Assign main artists to album
        # Plex unfortunately only supports 1 artist :-(
        artistId = parentId
        emby_dbartist = emby_db.getItem_byId(artistId)
        try:
            artistid = emby_dbartist[0]
        except TypeError:
            # Artist does not exist in emby database, create the reference
            self.logMsg('Artist %s does not exist in emby database'
                        % artistId, 1)
            artist = GetPlexMetadata(artistId)
            if artist:
                self.add_updateArtist(artist[0], artisttype="AlbumArtist")
                emby_dbartist = emby_db.getItem_byId(artistId)
                artistid = emby_dbartist[0]
        else:
            # Best take this name over anything else.
            query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
            kodicursor.execute(query, (artistname, artistid,))
            self.logMsg("UPDATE artist: strArtist: %s, idArtist: %s"
                        % (artistname, artistid), 1)

        # Add artist to album
        query = (
            '''
            INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)

            VALUES (?, ?, ?)
            '''
        )
        kodicursor.execute(query, (artistid, albumid, artistname))
        # Update discography
        query = (
            '''
            INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear)

            VALUES (?, ?, ?)
            '''
        )
        kodicursor.execute(query, (artistid, name, year))
        # Update emby reference with parentid
        emby_db.updateParentId(artistId, albumid)
        # Add genres
        kodi_db.addMusicGenres(albumid, genres, "album")
        # Update artwork
        artwork.addArtwork(artworks, albumid, "album", kodicursor)

    def add_updateSong(self, item, viewtag=None, viewid=None):
        # Process single song
        kodiversion = self.kodiversion
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = PlexAPI.API(item)

        update_item = True
        itemid = API.getRatingKey()
        if not itemid:
            self.logMsg('Error processing Song; skipping', -1)
            return
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            songid = emby_dbitem[0]
            pathid = emby_dbitem[2]
            albumid = emby_dbitem[3]
        except TypeError:
            # Songid not found
            update_item = False
            kodicursor.execute("select coalesce(max(idSong),0) from song")
            songid = kodicursor.fetchone()[0] + 1

        # The song details #####
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        title, sorttitle = API.getTitle()
        # musicBrainzId = API.getProvider('MusicBrainzTrackId')
        musicBrainzId = None
        genres = API.getGenres()
        genre = API.joinList(genres)
        artists = item.attrib.get('grandparentTitle')
        tracknumber = int(item.attrib.get('index', 0))
        disc = int(item.attrib.get('parentIndex', 1))
        if disc == 1:
            track = tracknumber
        else:
            track = disc*2**16 + tracknumber
        year = API.getYear()
        resume, duration = API.getRuntime()
        rating = userdata['UserRating']

        comment = None

        # Plex works a bit differently
        # if self.directstream:
        paths = "%s%s" % (self.server, item[0][0].attrib.get('key'))
        paths = paths.rsplit('/', 1)
        path = paths[0] + '/'
        filename = API.addPlexCredentialsToUrl(paths[1])
        # else:
        # path = "plugin://plugin.audio.plexkodiconnect.music/"
        # filename = API.getKey()
        # params = {
        #     'filename': filename,
        #     'id': itemid,
        #     'dbid': songid,
        #     'mode': "play"
        # }
        # filename = "%s?%s" % (path, urllib.urlencode(params))

        # UPDATE THE SONG #####
        if update_item:
            self.logMsg("UPDATE song itemid: %s - Title: %s"
                        % (itemid, title), 1)
            # Update path
            query = "UPDATE path SET strPath = ? WHERE idPath = ?"
            kodicursor.execute(query, (path, pathid))

            # Update the song entry
            query = ' '.join((
                "UPDATE song",
                "SET idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?,",
                    "iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,",
                    "rating = ?, comment = ?",
                "WHERE idSong = ?"
            ))
            kodicursor.execute(query, (albumid, artists, genre, title, track,
                                       duration, year, filename, playcount,
                                       dateplayed, rating, comment, songid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        # OR ADD THE SONG #####
        else:
            self.logMsg("ADD song itemid: %s - Title: %s" % (itemid, title), 1)

            # Add path
            pathid = kodi_db.addPath(path)

            try:
                # Get the album
                emby_dbalbum = emby_db.getItem_byId(
                    item.attrib.get('parentRatingKey'))
                albumid = emby_dbalbum[0]
            except KeyError:
                # No album Id associated to the song.
                self.logMsg("Song itemid: %s has no albumId." % itemid, 1)
                return
            except TypeError:
                # No album found. Let's create it
                self.logMsg("Album database entry missing.", 1)
                emby_albumId = item.attrib.get('parentRatingKey')
                album = GetPlexMetadata(emby_albumId)
                self.add_updateAlbum(album)
                emby_dbalbum = emby_db.getItem_byId(emby_albumId)
                try:
                    albumid = emby_dbalbum[0]
                    self.logMsg("Found albumid: %s" % albumid, 1)
                except TypeError:
                    # No album found, create a single's album
                    self.logMsg("Failed to add album. Creating singles.", 1)
                    kodicursor.execute("select coalesce(max(idAlbum),0) from album")
                    albumid = kodicursor.fetchone()[0] + 1
                    if kodiversion == 16:
                        # Kodi Jarvis
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, strReleaseType)

                            VALUES (?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, "single"))
                    elif kodiversion == 15:
                        # Kodi Isengard
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded, strReleaseType)

                            VALUES (?, ?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, dateadded, "single"))
                    else:
                        # Kodi Helix
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded)

                            VALUES (?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, dateadded))

            # Create the song entry
            query = (
                '''
                INSERT INTO song(
                    idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack,
                    iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                    rating)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(
                query, (songid, albumid, pathid, artists, genre, title, track,
                        duration, year, filename, musicBrainzId, playcount,
                        dateplayed, rating))

            # Create the reference in emby table
            emby_db.addReference(
                itemid, songid, "Audio", "song",
                pathid=pathid,
                parentid=albumid,
                checksum=checksum)

        # Link song to album
        query = (
            '''
            INSERT OR REPLACE INTO albuminfosong(
                idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration)

            VALUES (?, ?, ?, ?, ?)
            '''
        )
        kodicursor.execute(query, (songid, albumid, track, title, duration))
        # Verify if album has artists
        addArtist = False
        query = ' '.join((

            "SELECT strArtists",
            "FROM album",
            "WHERE idAlbum = ?"
        ))
        kodicursor.execute(query, (albumid,))
        result = kodicursor.fetchone()
        if result and result[0] == "":
            addArtist = True

        # if item['AlbumArtists']:
        #     album_artists = item['AlbumArtists']
        # else:
        #     album_artists = item['ArtistItems']

        # Link song to artist
        artist_name = item.attrib.get('grandparentTitle')
        emby_dbartist = emby_db.getItem_byId(
            item.attrib.get('grandparentRatingKey'))
        try:
            artistid = emby_dbartist[0]
        except:
            pass
        else:
            query = (
                '''
                INSERT OR REPLACE INTO song_artist(idArtist, idSong, strArtist)

                VALUES (?, ?, ?)
                '''
            )
            kodicursor.execute(query, (artistid, songid, artist_name))

            if addArtist:
                query = (
                    '''
                    INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)

                    VALUES (?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (artistid, albumid, artist_name))

        if addArtist:
            query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
            kodicursor.execute(query, (artist_name, albumid))

        # Add genres
        kodi_db.addMusicGenres(songid, genres, "song")
        # Update artwork
        allart = API.getAllArtwork(parentInfo=True)
        artwork.addArtwork(allart, songid, "song", kodicursor)

    def remove(self, itemid):
        # Remove kodiid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            self.logMsg("Removing %s kodiid: %s" % (mediatype, kodiid), 1)
        except TypeError:
            return

        ##### PROCESS ITEM #####

        # Remove the emby reference
        emby_db.removeItem(itemid)


        ##### IF SONG #####

        if mediatype == "song":
            # Delete song
            self.removeSong(kodiid)

        ##### IF ALBUM #####

        elif mediatype == "album":
            # Delete songs, album
            album_songs = emby_db.getItem_byParentId(kodiid, "song")
            for song in album_songs:
                self.removeSong(song[1])
            else:
                # Remove emby songs
                emby_db.removeItems_byParentId(kodiid, "song")

            # Remove the album
            self.removeAlbum(kodiid)

        ##### IF ARTIST #####

        elif mediatype == "artist":
            # Delete songs, album, artist
            albums = emby_db.getItem_byParentId(kodiid, "album")
            for album in albums:
                albumid = album[1]
                album_songs = emby_db.getItem_byParentId(albumid, "song")
                for song in album_songs:
                    self.removeSong(song[1])
                else:
                    # Remove emby song
                    emby_db.removeItems_byParentId(albumid, "song")
                    # Remove emby artist
                    emby_db.removeItems_byParentId(albumid, "artist")
                    # Remove kodi album
                    self.removeAlbum(albumid)
            else:
                # Remove emby albums
                emby_db.removeItems_byParentId(kodiid, "album")

            # Remove artist
            self.removeArtist(kodiid)

        self.logMsg("Deleted %s: %s from kodi database" % (mediatype, itemid), 1)

    def removeSong(self, kodiid):

        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "song", kodicursor)
        kodicursor.execute("DELETE FROM song WHERE idSong = ?", (kodiid,))

    def removeAlbum(self, kodiid):

        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "album", kodicursor)
        kodicursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodiid,))

    def removeArtist(self, kodiid):

        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "artist", kodicursor)
        kodicursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodiid,))
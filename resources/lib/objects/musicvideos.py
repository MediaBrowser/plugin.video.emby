# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib
from ntpath import dirname
from datetime import datetime

import api
import common
import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
from utils import window, settings, language as lang, catch_except

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class MusicVideos(common.Items):

    
    def __init__(self, embycursor, kodicursor):
        
        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        
        common.Items.__init__(self)

    def add_all(self, view, pdialog):

        log.info("Processing: %s", view)
        view_name = view['name']

        if self.should_stop():
            return False

        # Get items per view
        if pdialog:
            pdialog.update(
                    heading=lang(29999),
                    message="%s %s..." % (lang(33019), view_name))

        movies = self.emby.getMovies(view['id'], dialog=pdialog)
        total = movies['TotalRecordCount']

        if pdialog:
            pdialog.update(heading="Processing %s / %s items" % (view_name, total))

        self.added(movies['Items'], total, view, pdialog)


            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33019), viewName))

            # Initial or repair sync
            all_embymvideos = self.emby.getMusicVideos(viewId, dialog=pdialog)
            total = all_embymvideos['TotalRecordCount']
            embymvideos = all_embymvideos['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymvideo in embymvideos:
                # Process individual musicvideo
                if should_stop():
                    return False

                title = embymvideo['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                mvideos.add_update(embymvideo, viewName, viewId)

    def compare_all(self, pdialog):
        # Pull the list of movies and boxsets in Kodi

        views = self.emby_db.getView_byType('movies')
        views += self.emby_db.getView_byType('mixed')
        log.info("Media folders: %s" % views)

        try:
            all_kodimovies = dict(self.emby_db.get_checksum('Movie'))
        except ValueError:
            all_kodimovies = {}

        all_embymoviesIds = set()
        updatelist = []

        for view in views:

            if self.should_stop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33026), viewName))

            all_embymovies = self.emby.getMovies(viewId, basic=True, dialog=pdialog)
            for embymovie in all_embymovies['Items']:

                if self.should_stop():
                    return False

                API = api.API(embymovie)
                itemid = embymovie['Id']
                all_embymoviesIds.add(itemid)


                if all_kodimovies.get(itemid) != API.get_checksum():
                    # Only update if movie is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log.info("Movies to update for %s: %s" % (viewName, updatelist))
            embymovies = self.emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            self.added(embymovies, total, view, pdialog)


        for kodimovie in all_kodimovies:
            if kodimovie not in all_embymoviesIds:
                self.remove(kodimovie)
        else:
            log.info("Movies compare finished.")


    def added(self, items, total=None, view=None, pdialog=None):

        total = total or len(items)
        count = 0

        for movie in items:
            title = movie['Name']

            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1

            if self.add_update(movie, view):
                if not pdialog and self.content_msg:
                    self.content_pop(title, self.new_video_time)

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

    @catch_except
    def add_update(self, item, viewtag=None, viewid=None):
        # Process single music video
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        if item.get('LocationType') == "Virtual": # TODO: Filter via api instead
            log.info("Skipping virtual episode: %s", item['Name'])
            return

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("mvideoid: %s fileid: %s pathid: %s" % (mvideoid, fileid, pathid))
        
        except TypeError:
            update_item = False
            log.debug("mvideoid: %s not found." % itemid)
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
                log.info("mvideoid: %s missing from Kodi, repairing the entry." % mvideoid)

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            log.debug("View tag found: %s" % viewtag)

        # fileId information
        checksum = API.get_checksum()
        dateadded = API.get_date_created()
        userdata = API.get_userdata()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        runtime = API.get_runtime()
        plot = API.get_overview()
        title = item['Name']
        year = item.get('ProductionYear')
        genres = item['Genres']
        genre = " / ".join(genres)
        studios = API.get_studios()
        studio = " / ".join(studios)
        artist = " / ".join(item.get('Artists'))
        album = item.get('Album')
        track = item.get('Track')
        people = API.get_people()
        director = " / ".join(people['Director'])

        
        ##### GET THE FILE AND PATH #####
        playurl = API.get_file_path()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if not self.pathValidation(playurl):
                return False
            
            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.emby.musicvideos/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': mvideoid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MUSIC VIDEO #####
        if update_item:
            log.info("UPDATE mvideo itemid: %s - Title: %s" % (itemid, title))
            
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
            log.info("ADD mvideo itemid: %s - Title: %s" % (itemid, title))
            
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
        people = artwork.get_people_artwork(people)
        self.kodi_db.addPeople(mvideoid, people, "musicvideo")
        # Process genres
        self.kodi_db.addGenres(mvideoid, genres, "musicvideo")
        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(item), mvideoid, "musicvideo", kodicursor)
        # Process stream details
        streams = API.get_media_streams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        self.kodi_db.addStudios(mvideoid, studios, "musicvideo")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite musicvideos")
        self.kodi_db.addTags(mvideoid, tags, "musicvideo")
        # Process playstates
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        API = api.API(item)
        
        # Get emby information
        itemid = item['Id']
        checksum = API.get_checksum()
        userdata = API.get_userdata()
        runtime = API.get_runtime()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            log.info(
                "Update playstate for musicvideo: %s fileid: %s"
                % (item['Name'], fileid))
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            self.kodi_db.addTag(mvideoid, "Favorite musicvideos", "musicvideo")
        else:
            self.kodi_db.removeTag(mvideoid, "Favorite musicvideos", "musicvideo")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)

        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
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
            log.info("Removing mvideoid: %s fileid: %s" % (mvideoid, fileid, pathid))
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
        for row in kodicursor.fetchall():
            
            url = row[0]
            imagetype = row[1]
            if imagetype in ("poster", "fanart"):
                artwork.delete_cached_artwork(url)

        kodicursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (mvideoid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        if self.directpath:
            kodicursor.execute("DELETE FROM path WHERE idPath = ?", (pathid,))
        self.embycursor.execute("DELETE FROM emby WHERE emby_id = ?", (itemid,))

        log.info("Deleted musicvideo %s from kodi database" % itemid)

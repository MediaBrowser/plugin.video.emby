# -*- coding: utf-8 -*-
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime

import database.queries
import database.emby_db
import helper.api
import helper.loghandler
from . import obj_ops
from . import queries_music
from . import artwork
from . import common

class Music():
    def __init__(self, EmbyServer, embydb, musicdb):
        self.LOG = helper.loghandler.LOG('EMBY.core.music.Music')
        self.EmbyServer = EmbyServer
        self.emby = embydb
        self.music = musicdb
        self.emby_db = database.emby_db.EmbyDatabase(self.emby.cursor)
        self.objects = obj_ops.Objects()
        self.item_ids = []
        self.Common = common.Common(self.emby_db, self.objects, self.EmbyServer)
        self.MusicDBIO = MusicDBIO(self.music.cursor, self.EmbyServer.Utils.DatabaseFiles['music-version'])
        self.ArtworkDBIO = artwork.Artwork(musicdb.cursor, self.EmbyServer.Utils)
        self.APIHelper = helper.api.API(self.EmbyServer.Utils)
        self.MusicDBIO.disable_rescan()

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated
    def artist(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Artist')
        update = True

        if e_item:
            obj['ArtistId'] = e_item[0]

            if self.MusicDBIO.validate_artist(*self.EmbyServer.Utils.values(obj, queries_music.get_artist_by_id_obj)) is None:
                update = False
                self.LOG.info("ArtistId %s missing from kodi. repairing the entry." % obj['ArtistId'])
        else:
            update = False
            obj['ArtistId'] = None
            self.LOG.debug("ArtistId %s not found" % obj['Id'])

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['ArtistType'] = "MusicArtist"
        obj['Genre'] = " / ".join(obj['Genres'] or [])
        obj['Bio'] = self.APIHelper.get_overview(obj['Bio'], item)
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['Backdrops'] = obj['Artwork']['Backdrop'] or ""
        obj['Disambiguation'] = obj['LibraryName']

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if obj['Backdrops']:
            obj['Backdrops'] = "<fanart>%s</fanart>" % obj['Backdrops'][0]

        if obj['DateAdded']:
            obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if update:
            self.artist_update(obj)
        else:
            self.artist_add(obj)

        if self.EmbyServer.Utils.DatabaseFiles['music-version'] >= 82:
            self.MusicDBIO.update(obj['Genre'], obj['Bio'], obj['Thumb'], obj['LastScraped'], obj['SortName'], obj['DateAdded'], obj['ArtistId'])
        else:
            self.MusicDBIO.update(obj['Genre'], obj['Bio'], obj['Thumb'], obj['Backdrops'], obj['LastScraped'], obj['SortName'], obj['ArtistId'])

        self.ArtworkDBIO.add(obj['Artwork'], obj['ArtistId'], "artist")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    #safety checks: It looks like Emby supports the same artist multiple times.
    #Kodi doesn't allow that. In case that happens we just merge the artist entries
    def artist_add(self, obj):
        obj['ArtistId'] = self.MusicDBIO.get(*self.EmbyServer.Utils.values(obj, queries_music.get_artist_obj))
        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_artist_obj))
        self.LOG.info("ADD artist [%s] %s: %s" % (obj['ArtistId'], obj['Name'], obj['Id']))

    #Update object to kodi
    def artist_update(self, obj):
        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE artist [%s] %s: %s" % (obj['ArtistId'], obj['Name'], obj['Id']))

    #Update object to kodi
    def album(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Album')
        update = True

        if e_item:
            obj['AlbumId'] = e_item[0]

            if self.MusicDBIO.validate_album(*self.EmbyServer.Utils.values(obj, queries_music.get_album_by_id_obj)) is None:
                update = False
        else:
            update = False
            obj['AlbumId'] = None
            self.LOG.debug("AlbumId %s not found" % obj['Id'])

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Rating'] = 0
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['Genres'] = obj['Genres'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Bio'] = self.APIHelper.get_overview(obj['Bio'], item)
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['UniqueId'] = obj['UniqueId'] or None

        if obj['DateAdded']:
            obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if update:
            self.album_update(obj)
        else:
            obj['Type'] = obj['LibraryName']
            self.album_add(obj)

        self.artist_link(obj)
        self.artist_discography(obj)
        self.ArtworkDBIO.add(obj['Artwork'], obj['AlbumId'], "album")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    def album_add(self, obj):
        if self.EmbyServer.Utils.DatabaseFiles['music-version'] >= 82:
            obj['AlbumId'] = self.MusicDBIO.get_album(*self.EmbyServer.Utils.values(obj, queries_music.get_album_obj82))
        else:
            obj['AlbumId'] = self.MusicDBIO.get_album(*self.EmbyServer.Utils.values(obj, queries_music.get_album_obj))

        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_album_obj))
        self.LOG.info("ADD album [%s] %s: %s" % (obj['AlbumId'], obj['Title'], obj['Id']))

    #Update object to kodi
    def album_update(self, obj):
        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))

        if self.EmbyServer.Utils.DatabaseFiles['music-version'] >= 82:
            self.MusicDBIO.update_album(*self.EmbyServer.Utils.values(obj, queries_music.update_album_obj82))
        else:
            self.MusicDBIO.update_album(*self.EmbyServer.Utils.values(obj, queries_music.update_album_obj))

        self.LOG.info("UPDATE album [%s] %s: %s" % (obj['AlbumId'], obj['Title'], obj['Id']))

    #Update the artist's discography
    def artist_discography(self, obj):
        for artist in (obj['ArtistItems'] or []):
            temp_obj = dict(obj)
            temp_obj['Id'] = artist['Id']
            temp_obj['AlbumId'] = obj['Id']
            Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

            if Data:
                temp_obj['ArtistId'] = Data[0]
            else:
                continue

            self.MusicDBIO.add_discography(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_discography_obj))
            self.emby_db.update_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.update_parent_album_obj))

    #Assign main artists to album.
    #Artist does not exist in emby database, create the reference
    def artist_link(self, obj):
        for artist in (obj['AlbumArtists'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

            if Data:
                temp_obj['ArtistId'] = Data[0]
            else:
                self.artist(self.EmbyServer.API.get_item(temp_obj['Id']), library=None)
                Result = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

                if Result:
                    temp_obj['ArtistId'] = Result[0]
                else:
                    continue

            self.MusicDBIO.update_artist_name(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_artist_name_obj))
            self.MusicDBIO.link(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

    #Update object to kodi
    def song(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        obj = self.objects.map(item, 'Song')
        update = True

        if e_item:
            obj['SongId'] = e_item[0]
            obj['PathId'] = e_item[2]
            obj['AlbumId'] = e_item[3]

            if self.MusicDBIO.validate_song(*self.EmbyServer.Utils.values(obj, queries_music.get_song_by_id_obj)) is None:
                update = False
        else:
            update = False
            obj['SongId'] = self.MusicDBIO.create_entry_song()
            self.LOG.debug("SongId %s not found" % obj['Id'])

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Path'] = self.APIHelper.get_file_path(obj['Path'], item)
        PathValid, obj = self.Common.get_path_filename(obj, "audio")

        if not PathValid:
            return "Invalid Filepath"

        obj['Rating'] = 0
        obj['Genres'] = obj['Genres'] or []
        obj['PlayCount'] = self.APIHelper.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Runtime'] = (obj['Runtime'] or 0) / 10000000.0
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['AlbumArtists'] = obj['AlbumArtists'] or []
        obj['Index'] = obj['Index'] or None
        obj['Disc'] = obj['Disc'] or 1
        obj['EmbedCover'] = False
        obj['Comment'] = "%s (Library: %s)" % (self.APIHelper.get_overview(obj['Comment'], item), obj['LibraryName'])
        obj['Artwork'] = self.APIHelper.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['UniqueId'] = obj['UniqueId'] or None
        obj['Album'] = obj['Album'] or "Single"

        if obj['DateAdded']:
            obj['DateAdded'] = self.EmbyServer.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['DatePlayed']:
            obj['DatePlayed'] = self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Disc'] != 1 and obj['Index']:
            obj['Index'] = obj['Disc'] * 2 ** 16 + obj['Index']

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if update:
            self.song_update(obj)
        else:
            self.song_add(obj)

        self.MusicDBIO.add_role(*self.EmbyServer.Utils.values(obj, queries_music.update_role_obj)) # defaultt role
        self.song_artist_link(obj)
        self.song_artist_discography(obj)
        obj['strAlbumArtists'] = " / ".join(obj['AlbumArtists'])
        self.MusicDBIO.get_album_artist(*self.EmbyServer.Utils.values(obj, queries_music.get_album_artist_obj))
        self.MusicDBIO.add_genres(*self.EmbyServer.Utils.values(obj, queries_music.update_genre_song_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['SongId'], "song")
        self.item_ids.append(obj['Id'])

        if obj['SongAlbumId'] is None:
            self.ArtworkDBIO.add(obj['Artwork'], obj['AlbumId'], "album")

        return not update

    #Add object to kodi.
    #Verify if there's an album associated.
    #If no album found, create a single's album
    def song_add(self, obj):
        AlbumFound = False
        obj['PathId'] = self.MusicDBIO.add_path(obj['Path'])

        if obj['SongAlbumId']:
            result = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_song_obj))

            if result:
                obj['AlbumId'] = result[0]
                AlbumFound = True

        if not AlbumFound:
            obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            obj['AlbumId'] = None
            BackupTitle = obj['Title']
            obj['Title'] = "--NO INFO--"
            obj['Type'] = obj['LibraryName']

            if self.EmbyServer.Utils.DatabaseFiles['music-version'] >= 82:
                obj['AlbumId'] = self.MusicDBIO.get_album(*self.EmbyServer.Utils.values(obj, queries_music.get_single_obj82))
            else:
                obj['AlbumId'] = self.MusicDBIO.get_album(*self.EmbyServer.Utils.values(obj, queries_music.get_single_obj))

            obj['Title'] = BackupTitle

        if not self.MusicDBIO.add_song(*self.EmbyServer.Utils.values(obj, queries_music.add_song_obj)):
            obj['Index'] = None #Duplicate track number for same album
            self.MusicDBIO.add_song(*self.EmbyServer.Utils.values(obj, queries_music.add_song_obj))

        self.emby_db.add_reference(*self.EmbyServer.Utils.values(obj, database.queries.add_reference_song_obj))
        self.LOG.info("ADD song [%s/%s/%s] %s: %s" % (obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title']))
        return True # obj

    #Update object to kodi
    def song_update(self, obj):
        self.MusicDBIO.update_path(*self.EmbyServer.Utils.values(obj, queries_music.update_path_obj))

        if not self.MusicDBIO.update_song(*self.EmbyServer.Utils.values(obj, queries_music.update_song_obj)):
            obj['Index'] = None #Duplicate track number for same album
            self.MusicDBIO.update_song(*self.EmbyServer.Utils.values(obj, queries_music.update_song_obj))

        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE song [%s/%s/%s] %s: %s" % (obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title']))

    #Update the artist's discography
    def song_artist_discography(self, obj):
        artists = []

        for artist in (obj['AlbumArtists'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            artists.append(temp_obj['Name'])
            Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

            if Data:
                temp_obj['ArtistId'] = Data[0]
            else:
                self.artist(self.EmbyServer.API.get_item(temp_obj['Id']), library=None)
                Result = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

                if Result:
                    temp_obj['ArtistId'] = Result[0]
                else:
                    continue

            self.MusicDBIO.link(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

            if obj['Album']:
                temp_obj['Title'] = obj['Album']
                temp_obj['Year'] = 0
                self.MusicDBIO.add_discography(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_discography_obj))

        obj['AlbumArtists'] = artists

    #Assign main artists to song.
    #Artist does not exist in emby database, create the reference
    def song_artist_link(self, obj):
        for index, artist in enumerate(obj['ArtistItems'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            temp_obj['Index'] = index
            Data = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

            if Data:
                temp_obj['ArtistId'] = Data[0]
            else:
                self.artist(self.EmbyServer.API.get_item(temp_obj['Id']), library=None)
                Result = self.emby_db.get_item_by_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_obj))

                if Result:
                    temp_obj['ArtistId'] = Result[0]
                else:
                    continue

            self.MusicDBIO.link_song_artist(*self.EmbyServer.Utils.values(temp_obj, queries_music.update_song_artist_obj))
            self.item_ids.append(temp_obj['Id'])

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        obj = self.objects.map(item, 'SongUserData')

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        else:
            return

        obj['Rating'] = 0

        if obj['Media'] == 'song':
            if obj['DatePlayed']:
                obj['DatePlayed'] = self.EmbyServer.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            self.MusicDBIO.rate_song(*self.EmbyServer.Utils.values(obj, queries_music.update_song_rating_obj))

        self.emby_db.update_reference(*self.EmbyServer.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA %s [%s] %s: %s" % (obj['Media'], obj['KodiId'], obj['Id'], obj['Title']))

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    #This should address single song scenario, where server doesn't actually create an album for the song
    def remove(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        else:
            return

        if obj['Media'] == 'song':
            self.remove_song(obj['KodiId'], obj['Id'])
            self.emby_db.remove_wild_item(obj['Id'])

            for item in self.emby_db.get_item_by_wild_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_wild_obj)):
                if item[1] == 'album':
                    temp_obj = dict(obj)
                    temp_obj['ParentId'] = item[0]

                    if not self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                        self.remove_album(temp_obj['ParentId'], obj['Id'])
        elif obj['Media'] == 'album':
            obj['ParentId'] = obj['KodiId']

            for song in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_song_obj)):
                self.remove_song(song[1], obj['Id'])

            self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_song_obj))
            self.remove_album(obj['KodiId'], obj['Id'])
        elif obj['Media'] == 'artist':
            obj['ParentId'] = obj['KodiId']

            for album in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_album_obj)):
                temp_obj = dict(obj)
                temp_obj['ParentId'] = album[1]

                for song in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                    self.remove_song(song[1], obj['Id'])

                self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_item_by_parent_song_obj))
                self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.delete_item_by_parent_artist_obj))
                self.remove_album(temp_obj['ParentId'], obj['Id'])

            self.emby_db.remove_items_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_by_parent_album_obj))
            self.remove_artist(obj['KodiId'], obj['Id'])

        self.emby_db.remove_item(*self.EmbyServer.Utils.values(obj, database.queries.delete_item_obj))

    def remove_artist(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "artist")
        self.MusicDBIO.delete(kodi_id)
        self.LOG.info("DELETE artist [%s] %s" % (kodi_id, item_id))

    def remove_album(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "album")
        self.MusicDBIO.delete_album(kodi_id)
        self.LOG.info("DELETE album [%s] %s" % (kodi_id, item_id))

    def remove_song(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "song")
        self.MusicDBIO.delete_song(kodi_id)
        self.LOG.info("DELETE song [%s] %s" % (kodi_id, item_id))

    #Get all child elements from tv show emby id
    def get_child(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}
        child = []

        if e_item:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        else:
            return child

        obj['ParentId'] = obj['KodiId']

        for album in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(obj, database.queries.get_item_by_parent_album_obj)):
            temp_obj = dict(obj)
            temp_obj['ParentId'] = album[1]
            child.append((album[0],))

            for song in self.emby_db.get_item_by_parent_id(*self.EmbyServer.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                child.append((song[0],))

        return child

class MusicDBIO():
    def __init__(self, cursor, MusicDBVersion):
        self.LOG = helper.loghandler.LOG('EMBY.core.music.Music')
        self.cursor = cursor
        self.DBVersion = MusicDBVersion

    #Make sure rescan and kodi db set
    def disable_rescan(self):
        self.cursor.execute(queries_music.delete_rescan)
        Data = [str(self.DBVersion), "0"]
        self.cursor.execute(queries_music.disable_rescan, Data)

    #Leia has a dummy first entry
    #idArtist: 1  strArtist: [Missing Tag]  strMusicBrainzArtistID: Artist Tag Missing
    def create_entry(self):
        self.cursor.execute(queries_music.create_artist)
        return self.cursor.fetchone()[0] + 1

    def create_entry_album(self):
        self.cursor.execute(queries_music.create_album)
        return self.cursor.fetchone()[0] + 1

    def create_entry_song(self):
        self.cursor.execute(queries_music.create_song)
        return self.cursor.fetchone()[0] + 1

    def create_entry_genre(self):
        self.cursor.execute(queries_music.create_genre)
        return self.cursor.fetchone()[0] + 1

    def update_path(self, *args):
        self.cursor.execute(queries_music.update_path, args)

    def add_role(self, *args):
        self.cursor.execute(queries_music.update_role, args)

    #Get artist or create the entry
    def get(self, artist_id, name, musicbrainz, LibraryName):
        self.cursor.execute(queries_music.get_artist, (musicbrainz,))
        result = self.cursor.fetchone()

        if result:
            artist_id = result[0]
            artist_name = result[1]

            if artist_name != name:
                self.update_artist_name(artist_id, name)
        else:
            artist_id = self.add_artist(artist_id, name, musicbrainz, LibraryName)

        return artist_id

    #Safety check, when musicbrainz does not exist
    def add_artist(self, artist_id, name, musicbrainz, LibraryName):
        self.cursor.execute(queries_music.get_artist_by_name, (name,))
        artist_id = self.cursor.fetchone()

        if artist_id:
            artist_id = artist_id[0]
        else:
            artist_id = artist_id or self.create_entry()
            self.cursor.execute(queries_music.add_artist, (artist_id, name, musicbrainz, LibraryName))

        return artist_id

    def update_artist_name(self, *args):
        self.cursor.execute(queries_music.update_artist_name, args)

    def update(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.update_artist82, args)
        else:
            self.cursor.execute(queries_music.update_artist, args)

    def link(self, *args):
        self.cursor.execute(queries_music.update_link, args)

    def add_discography(self, *args):
        self.cursor.execute(queries_music.update_discography, args)

    def validate_artist(self, *args):
        self.cursor.execute(queries_music.get_artist_by_id, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def validate_album(self, *args):
        self.cursor.execute(queries_music.get_album_by_id, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def validate_song(self, *args):
        self.cursor.execute(queries_music.get_song_by_id, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_album(self, album_id, name, musicbrainz, Type, artists, *args):
        if musicbrainz:
            self.cursor.execute(queries_music.get_album, (musicbrainz,))
        else:
            self.cursor.execute(queries_music.get_album_by_name, (name, artists,))

        album = self.cursor.fetchone()
        album_id = (album or self.cursor.fetchone())

        if album_id:
            album_id = album_id[0]
        else:
            album_id = self.add_album(*(album_id, name, musicbrainz, Type, artists,) + args)

        return album_id

    def add_album(self, album_id, name, musicbrainz, Type, artists, *args):
        album_id = album_id or self.create_entry_album()

        if Type == "album":
            if self.DBVersion >= 82:
                self.cursor.execute(queries_music.add_album82, (album_id, name, musicbrainz, Type, artists,) + args)
            else:
                self.cursor.execute(queries_music.add_album, (album_id, name, musicbrainz, Type, artists,) + args)
        else: #single
            if self.DBVersion >= 82:
                self.cursor.execute(queries_music.add_single82, (album_id, name, musicbrainz, Type, artists,) + args)
            else:
                self.cursor.execute(queries_music.add_single, (album_id, name, musicbrainz, Type, artists,) + args)

        return album_id

    def update_album(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.update_album82, args)
        else:
            self.cursor.execute(queries_music.update_album, args)

    def get_album_artist(self, album_id, artists):
        self.cursor.execute(queries_music.get_album_artist, (album_id,))
        curr_artists = self.cursor.fetchone()

        if curr_artists:
            curr_artists = curr_artists[0]
        else:
            return

        if curr_artists != artists:
            self.update_album_artist(artists, album_id)

    def update_album_artist(self, *args):
        self.cursor.execute(queries_music.update_album_artist, args)

    def add_song(self, *args):
        try: #Covers duplicate track numbers in same album
            if self.DBVersion >= 82:
                self.cursor.execute(queries_music.add_song82, args)
            else:
                self.cursor.execute(queries_music.add_song, args)

            return True
        except:
            return False

    def update_song(self, *args):
        try: #Covers duplicate track numbers in same album
            if self.DBVersion >= 82:
                self.cursor.execute(queries_music.update_song82, args)
            else:
                self.cursor.execute(queries_music.update_song, args)

            return True
        except:
            return False

    def link_song_artist(self, *args):
        self.cursor.execute(queries_music.update_song_artist, args)

    def rate_song(self, *args):
        self.cursor.execute(queries_music.update_song_rating, args)

    #Add genres, but delete current genres first
    def add_genres(self, kodi_id, genres, media):
        if media == 'album':
            self.cursor.execute(queries_music.delete_genres_album, (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute(queries_music.update_genre_album, (genre_id, kodi_id))

        elif media == 'song':
            self.cursor.execute(queries_music.delete_genres_song, (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute(queries_music.update_genre_song, (genre_id, kodi_id))

    def get_genre(self, *args):
        self.cursor.execute(queries_music.get_genre, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return self.add_genre(*args)

    def add_genre(self, *args):
        genre_id = self.create_entry_genre()
        self.cursor.execute(queries_music.add_genre, (genre_id,) + args)
        return genre_id

    def delete(self, *args):
        self.cursor.execute(queries_music.delete_artist, args)

    def delete_album(self, *args):
        self.cursor.execute(queries_music.delete_album, args)

    def delete_song(self, *args):
        self.cursor.execute(queries_music.delete_song, args)

    def get_path(self, *args):
        self.cursor.execute(queries_music.get_path, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return

    def add_path(self, *args):
        path_id = self.get_path(*args)

        if path_id is None:
            path_id = self.create_entry_path()
            self.cursor.execute(queries_music.add_path, (path_id,) + args)

        return path_id

    def create_entry_path(self):
        self.cursor.execute(queries_music.create_path)
        return self.cursor.fetchone()[0] + 1

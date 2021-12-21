# -*- coding: utf-8 -*-
from helper import loghandler
from helper import utils
from emby import obj_ops
from . import common

LOG = loghandler.LOG('EMBY.core.music')


class Music:
    def __init__(self, EmbyServer, embydb, musicdb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.music_db = musicdb
        self.library = None
        self.ArtistID = None
        self.AlbumID = None

    # If item does not exist, entry will be added.
    # If item exists, entry will be updated
    def artist(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        self.library = common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not self.library:
            return False

        obj = obj_ops.mapitem(item, 'Artist')
        obj['LibraryId'] = self.library['Id']
        obj['LibraryId_Name'] = "%s-%s" % (self.library['Id'], self.library['Name'])
        update = True

        if e_item:
            obj['ArtistId'] = e_item[0]
            if not self.music_db.validate_artist(obj['ArtistId'], obj['LibraryId_Name']):
                if not self.music_db.artist_exists(obj['ArtistId']):  # check if Artist not in music.db even if in emby.db
                    update = False
                    LOG.info("ArtistId %s does not exist in mymusic.db. Adding artist %s" % (obj['ArtistId'], obj['LibraryId_Name']))
                else:
                    self.emby_db.add_reference_library_id(obj['Id'], e_item[6], self.library['Id'])
                    LOG.info("ArtistId %s used for multiple libraries. Adding tags %s" % (obj['ArtistId'], obj['LibraryId_Name']))
        else:
            update = False
            obj['ArtistId'] = None
            LOG.debug("ArtistId %s not found" % obj['Id'])

        obj['LastScraped'] = utils.currenttime_kodi_format()
        obj['ArtistType'] = "MusicArtist"
        obj['Genre'] = " / ".join(obj['Genres'] or [])
        obj['Bio'] = common.get_overview(obj['Bio'], item)
        obj['Artwork'] = common.get_all_artwork(obj_ops.mapitem(item, 'ArtworkMusic'), False, self.EmbyServer.server_id)
        obj['Disambiguation'] = obj['LibraryId_Name']

        if obj['DateAdded']:
            obj['DateAdded'] = utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if update:
            self.emby_db.update_reference(obj['PresentationKey'], obj['Id'], obj['Favorite'])
            self.music_db.update_artist(obj['Genre'], obj['Bio'], obj['Artwork']['Thumb'], obj['Artwork']['Backdrop'], obj['LastScraped'], obj['SortName'], obj['DateAdded'], obj['ArtistId'], obj['LibraryId_Name'])
            LOG.info("UPDATE artist [%s] %s: %s" % (obj['ArtistId'], obj['Name'], obj['Id']))
        else:
            obj['ArtistId'] = self.music_db.add_artist(obj['Name'], obj['UniqueId'], obj['Genre'], obj['Bio'], obj['Artwork']['Thumb'], obj['Artwork']['Backdrop'], obj['LastScraped'], obj['SortName'], obj['DateAdded'], obj['LibraryId_Name'])
            self.emby_db.add_reference(obj['Id'], obj['ArtistId'], None, None, obj['ArtistType'], "artist", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD artist [%s] %s: %s" % (obj['ArtistId'], obj['Name'], obj['Id']))

        self.music_db.common_db.add_artwork(obj['Artwork'], obj['ArtistId'], "artist")
        self.ArtistID = obj['ArtistId']
        return not update

    # Update object to kodi
    def album(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        self.library = common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not self.library:
            return False

        obj = obj_ops.mapitem(item, 'Album')
        obj['LibraryId'] = self.library['Id']
        obj['LibraryId_Name'] = "%s-%s" % (self.library['Id'], self.library['Name'])
        update = True

        if e_item:
            obj['AlbumId'] = e_item[0]

            if not self.music_db.validate_album(obj['AlbumId'], obj['LibraryId_Name']):
                if not self.music_db.album_exists(obj['AlbumId']):  # check if album not in music.db even if in emby.db
                    update = False
                    LOG.info("AlbumId %s does not exist in mymusic.db. Adding album %s" % (obj['AlbumId'], obj['LibraryId_Name']))
                else:
                    self.emby_db.add_reference_library_id(obj['Id'], e_item[6], self.library['Id'])
                    LOG.info("AlbumId %s used for multiple libraries. Adding tags %s" % (obj['AlbumId'], obj['LibraryId_Name']))
        else:
            update = False
            obj['AlbumId'] = None
            LOG.debug("AlbumId %s not found" % obj['Id'])

        obj['Rating'] = 0
        obj['LastScraped'] = utils.currenttime_kodi_format()
        obj['Genres'] = obj['Genres'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Bio'] = common.get_overview(obj['Bio'], item)
        obj['Artist'] = " / ".join(obj['Artists'] or [])
        obj['Artwork'] = common.get_all_artwork(obj_ops.mapitem(item, 'ArtworkMusic'), True, self.EmbyServer.server_id)
        obj['UniqueId'] = obj['UniqueId'] or None

        if obj['DateAdded']:
            obj['DateAdded'] = utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if update:
            self.emby_db.update_reference(obj['PresentationKey'], obj['Id'], obj['Favorite'])
            self.music_db.update_album(obj['Artist'], obj['Year'], obj['Genre'], obj['Bio'], obj['Artwork']['Thumb'], obj['Rating'], obj['LastScraped'], obj['DateAdded'], obj['AlbumId'], obj['LibraryId_Name'])
            LOG.info("UPDATE album [%s] %s: %s" % (obj['AlbumId'], obj['Title'], obj['Id']))
        else:
            obj['Type'] = obj['LibraryId_Name']
            obj['AlbumId'] = self.music_db.get_add_album(obj['Title'], "album", obj['Artist'], obj['Year'], obj['Genre'], obj['Artwork']['Thumb'], obj['Rating'], obj['LastScraped'], obj['DateAdded'], obj['LibraryId_Name'])
            self.emby_db.add_reference(obj['Id'], obj['AlbumId'], None, None, "MusicAlbum", "album", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD album [%s] %s: %s" % (obj['AlbumId'], obj['Title'], obj['Id']))

        # Assign main artists to album.
        # Artist does not exist in emby database, create the reference
        for artist in (obj['AlbumArtists'] or []):
            Data = self.emby_db.get_item_by_id(artist['Id'])

            if Data:
                ArtistId = Data[0]
            else:
                self.artist(self.EmbyServer.API.get_item(artist['Id']), self.library)
                ArtistId = self.ArtistID

            self.music_db.update_artist_name(artist['Name'], ArtistId, obj['LibraryId_Name'])
            self.music_db.link(ArtistId, obj['AlbumId'], artist['Name'])

        # Update the artist's discography
        for artist in (obj['ArtistItems'] or []):
            Data = self.emby_db.get_item_by_id(artist['Id'])

            if not Data:
                continue

            self.music_db.add_discography(Data[0], obj['Title'], obj['Year'])
            self.emby_db.update_parent_id(Data[0], obj['Id'])

        self.music_db.common_db.add_artwork(obj['Artwork'], obj['AlbumId'], "album")
        self.AlbumID = obj['AlbumId']
        return not update

    # Update object to kodi
    def song(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        self.library = common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not self.library:
            return False

        obj = obj_ops.mapitem(item, 'Song')
        obj['LibraryId'] = self.library['Id']
        obj['LibraryId_Name'] = "%s-%s" % (self.library['Id'], self.library['Name'])
        obj['ServerId'] = self.EmbyServer.server_id
        update = True

        if e_item:
            obj['SongId'] = e_item[0]
            obj['KodiPathId'] = e_item[2]
            obj['AlbumId'] = e_item[3]

            if not self.music_db.validate_song(obj['SongId'], obj['LibraryId_Name']):
                if not self.music_db.song_exists(obj['SongId']):  # check if song not in music.db even if in emby.db
                    update = False
                    LOG.info("SongId %s does not exist in mymusic.db. Adding song %s" % (obj['SongId'], obj['LibraryId_Name']))
                else:
                    self.emby_db.add_reference_library_id(obj['Id'], e_item[6], self.library['Id'])
                    LOG.info("SongId %s used for multiple libraries. Adding tags %s" % (obj['SongId'], obj['LibraryId_Name']))
        else:
            update = False
            LOG.debug("SongId %s not found" % obj['Id'])

        if not obj['Path']:
            LOG.warning("Path %s not found" % obj['Title'])
            return False

        obj['FullPath'] = common.get_file_path(obj['Path'], item)
        obj['Path'] = common.get_path(obj, "audio")
        obj['Filename'] = common.get_filename(obj, "audio", self.EmbyServer.API)
        obj['Rating'] = 0
        obj['Genres'] = obj['Genres'] or []
        obj['PlayCount'] = common.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Runtime'] = (obj['Runtime'] or 0) / 10000000.0
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Artist'] = " / ".join(obj['Artists'] or [])
        obj['AlbumArtists'] = obj['AlbumArtists'] or []
        obj['Index'] = obj['Index'] or None
        obj['Disc'] = obj['Disc'] or 1
        obj['EmbedCover'] = False
        obj['Comment'] = common.get_overview(obj['Comment'], item)
        obj['Artwork'] = common.get_all_artwork(obj_ops.mapitem(item, 'ArtworkMusic'), True, self.EmbyServer.server_id)

        if not obj['Artist']:
            obj['Artist'] = "--NO INFO--"
            obj['Artists'] = ["--NO INFO--"]
            obj['Disambiguation'] = obj['LibraryId_Name']
            obj['ArtistId'] = self.music_db.get_add_artist(obj['Artist'], None, obj['Disambiguation'])

        obj['UniqueId'] = obj['UniqueId'] or None
        obj['Album'] = obj['Album'] or "Single"
        obj['LastScraped'] = utils.currenttime_kodi_format()

        if obj['DateAdded']:
            obj['DateAdded'] = utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['DatePlayed']:
            obj['DatePlayed'] = utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Disc'] != 1 and obj['Index']:
            obj['Index'] = obj['Disc'] * 2 ** 16 + obj['Index']

        AlbumTitleSingle = ""

        if obj['SongAlbumId']:
            Data = self.emby_db.get_item_by_id(obj['SongAlbumId'])

            if Data:
                obj['AlbumId'] = Data[0]
            else:
                self.album(self.EmbyServer.API.get_item(obj['SongAlbumId']), self.library)
                obj['AlbumId'] = self.AlbumID
        else:  # Single
            AlbumTitleSingle = "--NO INFO--"
            obj['AlbumArtists'] = obj['Artists']
            obj['AlbumId'] = self.music_db.get_add_album(AlbumTitleSingle, "single", obj['Artist'], None, obj['Genre'], obj['Artwork']['Thumb'], obj['Rating'], obj['LastScraped'], obj['DateAdded'], obj['LibraryId_Name'])

        if update:
            self.music_db.delete_link_song_artist(obj['SongId'])
            self.music_db.update_song(obj['AlbumId'], obj['Artist'], obj['Genre'], obj['Title'], obj['Index'], obj['Runtime'], obj['Year'], obj['Filename'], obj['PlayCount'], obj['DatePlayed'], obj['Rating'], obj['Comment'], obj['DateAdded'], obj['SongId'], obj['LibraryId_Name'])
            self.emby_db.update_reference(obj['PresentationKey'], obj['Id'], obj['Favorite'])
            LOG.info("UPDATE song [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title']))
        else:
            obj['SongId'], obj['KodiPathId'] = self.music_db.add_song(obj['AlbumId'], obj['Artist'], obj['Genre'], obj['Title'], obj['Index'], obj['Runtime'], obj['Year'], obj['Filename'], obj['PlayCount'], obj['DatePlayed'], obj['Rating'], obj['Comment'], obj['DateAdded'], obj['LibraryId_Name'], obj['Path'])

            if not obj['SongId']:
                return True

            self.emby_db.add_reference(obj['Id'], obj['SongId'], None, obj['KodiPathId'], "Audio", "song", obj['AlbumId'], obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD song [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title']))

        self.music_db.add_role(1, "artist")  # default role

        if obj['Artist'] == "--NO INFO--":
            self.music_db.link_song_artist(obj['ArtistId'], obj['SongId'], 1, 1, "--NO INFO--")
        else:
            # Assign main artists to song.
            # Artist does not exist in emby database, create the reference
            if 'ArtistItems' in obj:
                for index, artist in enumerate(obj['ArtistItems']):
                    Data = self.emby_db.get_item_by_id(artist['Id'])

                    if Data:
                        ArtistId = Data[0]
                    else:
                        LOG.warning("Possible Artist/Albumartist inconsistency (Link the artist's song): %s %s %s" % (obj['Artist'], obj['AlbumArtists'], obj['Title']))
                        self.artist(self.EmbyServer.API.get_item(artist['Id']), self.library)
                        ArtistId = self.ArtistID

                    self.music_db.link_song_artist(ArtistId, obj['SongId'], 1, index, artist['Name'])

        if AlbumTitleSingle:
            if "ArtistId" not in obj:
                for AlbumArtist in obj['AlbumArtists']:
                    obj['ArtistId'] = self.music_db.get_artistID(AlbumArtist, obj['LibraryId_Name'])

                    if not self.music_db.get_discography(obj['ArtistId'], AlbumTitleSingle):
                        self.music_db.add_discography(obj['ArtistId'], AlbumTitleSingle, None)
            else:
                if not self.music_db.get_discography(obj['ArtistId'], AlbumTitleSingle):
                    self.music_db.add_discography(obj['ArtistId'], AlbumTitleSingle, None)

            obj['AlbumArtist'] = " / ".join(obj['AlbumArtists'])
            self.music_db.link(obj['ArtistId'], obj['AlbumId'], obj['AlbumArtist'])
        else:
            # Update the artist's discography
            artists = []

            for artist in (obj['AlbumArtists'] or []):
                artists.append(artist['Name'])
                Data = self.emby_db.get_item_by_id(artist['Id'])

                if Data:
                    ArtistId = Data[0]
                else:
                    LOG.warning("Possible Artist/Albumartist inconsistency (Update the artist's discography): %s %s %s" % (obj['Artist'], obj['AlbumArtist'], obj['Title']))
                    self.artist(self.EmbyServer.API.get_item(artist['Id']), self.library)
                    ArtistId = self.ArtistID

                self.music_db.link(ArtistId, obj['AlbumId'], artist['Name'])

            obj['AlbumArtists'] = artists
            obj['AlbumArtist'] = " / ".join(obj['AlbumArtists'])
            self.music_db.get_album_artist(obj['AlbumId'], obj['AlbumArtist'])

        self.music_db.add_genres(obj['SongId'], obj['Genres'], "song")
        self.music_db.common_db.add_artwork(obj['Artwork'], obj['SongId'], "song")

        if obj['SongAlbumId'] is None:
            self.music_db.common_db.add_artwork(obj['Artwork'], obj['AlbumId'], "album")

        return not update

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    # Poster with progress bar
    def userdata(self, e_item, ItemUserdata):
        KodiPathId = e_item[0]
        Media = e_item[4]
        Rating = 0
        PlayCount = common.get_playcount(ItemUserdata['Played'], ItemUserdata['PlayCount'])

        if Media == 'song':
            DatePlayed = utils.currenttime_kodi_format()
            self.music_db.rate_song(PlayCount, DatePlayed, Rating, KodiPathId)

        self.emby_db.update_reference_userdatachanged(ItemUserdata['ItemId'], ItemUserdata['IsFavorite'])
        LOG.info("USERDATA %s [%s] %s" % (Media, KodiPathId, ItemUserdata['ItemId']))

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    # Poster with progress bar
    # This should address single song scenario, where server doesn't actually create an album for the song
    def remove(self, EmbyItemId, LibraryId):
        e_item = self.emby_db.get_item_by_id(EmbyItemId)

        if e_item:
            KodiId = e_item[0]
            KodiType = e_item[4]
        else:
            return

        if KodiType == 'song':
            self.remove_song(KodiId, EmbyItemId)
            self.emby_db.remove_item_music(EmbyItemId)
            return

        if KodiType == 'album':
            self.remove_album(KodiId, EmbyItemId, LibraryId)
        elif KodiType == 'artist':
            self.remove_artist(KodiId, EmbyItemId, LibraryId)

        if not LibraryId:
            self.emby_db.remove_item_music(EmbyItemId)
        else:
            self.emby_db.remove_item_music_by_libraryId(EmbyItemId, LibraryId)

    def remove_artist(self, kodi_id, item_id, LibraryId):
        self.music_db.common_db.delete_artwork(kodi_id, "artist")
        self.music_db.delete_artist(kodi_id, LibraryId)
        LOG.info("DELETE artist [%s] %s" % (kodi_id, item_id))

    def remove_album(self, kodi_id, item_id, LibraryId):
        self.music_db.common_db.delete_artwork(kodi_id, "album")
        self.music_db.delete_album(kodi_id, LibraryId)
        LOG.info("DELETE album [%s] %s" % (kodi_id, item_id))

    def remove_song(self, kodi_id, item_id):
        self.music_db.common_db.delete_artwork(kodi_id, "song")
        self.music_db.delete_song(kodi_id)
        LOG.info("DELETE song [%s] %s" % (kodi_id, item_id))

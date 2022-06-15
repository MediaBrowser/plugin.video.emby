from helper import utils, loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.music')


class Music:
    def __init__(self, EmbyServer, embydb, musicdb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.music_db = musicdb
        self.NEWKodiArtistId = None
        self.NEWKodiAlbumId = None

    # If item does not exist, entry will be added.
    # If item exists, entry will be updated
    def artist(self, item):
        self.NEWKodiArtistId = None

        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        update = True

        if item['ExistingItem']:
            ExistingEmbyDBKodiIds = str(item['ExistingItem'][0])
            ExistingEmbyDBLibraryIds = str(item['ExistingItem'][6])
            ExistingEmbyDBPresentationUniqueKeys = str(item['ExistingItem'][7])
        else:
            update = False
            LOG.debug("ArtistId %s not found" % item['Id'])

        item['LastScraped'] = utils.currenttime_kodi_format()
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzArtist'] = item['ProviderIds'].get('MusicBrainzArtist', None)
        common.set_genres(item)
        common.set_overview(item)
        common.set_KodiArtwork(item, self.EmbyServer.server_id)
        KodiArtistIds = []

        if update:
            KodiArtistIds = ExistingEmbyDBKodiIds.split(";")

            for KodiArtistId in KodiArtistIds:
                self.music_db.common.delete_artwork(KodiArtistId, "artist")
                self.music_db.update_artist(item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], item['LastScraped'], item['SortName'], item['DateCreated'], KodiArtistId)
                LOG.info("UPDATE existing artist [%s] %s: %s" % (KodiArtistId, item['Name'], item['Id']))

            if item['Library']['Id'] not in ExistingEmbyDBLibraryIds:
                self.NEWKodiArtistId = self.music_db.add_artist(item['Name'], item['ProviderIds']['MusicBrainzArtist'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], item['LastScraped'], item['SortName'], item['DateCreated'], item['Library']['LibraryId_Name'])
                KodiArtistIds.append(self.NEWKodiArtistId)
                ExistingEmbyDBKodiIds = "%s;%s" % (ExistingEmbyDBKodiIds, self.NEWKodiArtistId)
                ExistingEmbyDBLibraryIds = "%s;%s" % (ExistingEmbyDBLibraryIds, item['Library']['Id'])
                ExistingEmbyDBPresentationUniqueKeys = "%s;%s" % (ExistingEmbyDBPresentationUniqueKeys, item['PresentationUniqueKey'])
                LOG.info("UPDATE new artist [%s] %s: %s" % (self.NEWKodiArtistId, item['Name'], item['Id']))

            self.emby_db.update_reference(ExistingEmbyDBKodiIds, None, None, "MusicArtist", "artist", None, ExistingEmbyDBLibraryIds, None, ExistingEmbyDBPresentationUniqueKeys, item['UserData']['IsFavorite'], item['Id'])
        else:
            self.NEWKodiArtistId = self.music_db.add_artist(item['Name'], item['ProviderIds']['MusicBrainzArtist'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], item['LastScraped'], item['SortName'], item['DateCreated'], item['Library']['LibraryId_Name'])
            self.emby_db.add_reference(item['Id'], self.NEWKodiArtistId, None, None, "MusicArtist", "artist", None, item['Library']['Id'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            KodiArtistIds.append(self.NEWKodiArtistId)
            LOG.info("ADD artist [%s] %s: %s" % (self.NEWKodiArtistId, item['Name'], item['Id']))

        for KodiArtistId in KodiArtistIds:
            self.music_db.common.add_artwork(item['KodiArtwork'], KodiArtistId, "artist")

        return not update

    # Update object to kodi
    def album(self, item):
        self.NEWKodiAlbumId = None

        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        update = True

        if item['ExistingItem']:
            ExistingEmbyDBKodiIds = str(item['ExistingItem'][0])
            ExistingEmbyKodiParentIds = str(item['ExistingItem'][3])
            ExistingEmbyDBLibraryIds = str(item['ExistingItem'][6])
            ExistingEmbyDBPresentationUniqueKeys = str(item['ExistingItem'][7])
        else:
            update = False
            LOG.debug("AlbumId %s not found" % item['Id'])

        item['LastScraped'] = utils.currenttime_kodi_format()
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProductionYear'] = item.get('ProductionYear')
        common.set_studios(item)
        common.set_genres(item)
        common.set_overview(item)
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', None)
        item['ProviderIds']['MusicBrainzReleaseGroup'] = item['ProviderIds'].get('MusicBrainzReleaseGroup', None)
        common.set_KodiArtwork(item, self.EmbyServer.server_id)
        common.set_RunTimeTicks(item)
        self.get_ArtistInfos(item, "ArtistItems")
        self.get_ArtistInfos(item, "AlbumArtists")

        if not 'AlbumArtistSortName' in item:
            if 'AlbumArtist' in item:
                item['AlbumArtistSortName'] = item['AlbumArtist']
                LOG.warning("Invalid Artist seperation: %s" % item['AlbumArtist'])
            else:
                LOG.warning("No AlbumArtist in album: %s" % item)
                return False

        item["ArtistTotalItems"] = item["ArtistItems"].copy()

        for AlbumArtist in item["AlbumArtists"]:
            if AlbumArtist not in item["ArtistTotalItems"]:
                item["ArtistTotalItems"].append(AlbumArtist)

        Compilation = 0

        if str(item['Id']).startswith("9999999"):
            AlbumType = "single"
        else:
            AlbumType = "album"

        # Detect compilations
        if item['AlbumArtist'].lower() in ("various artists", "various", "various items", "sountrack"):
            Compilation = 1
            LOG.info("Compilation detected: %s" % item['Name'])

        KodiAlbumIds = []

        if update:
            # Update all existing Kodi Albums
            KodiAlbumIds = ExistingEmbyDBKodiIds.split(";")

            for KodiAlbumId in KodiAlbumIds:
                self.music_db.common.delete_artwork(KodiAlbumId, "single")
                self.music_db.common.delete_artwork(KodiAlbumId, "album")


# Update discograph and link_album_artist here






                self.music_db.update_album(item['AlbumArtist'], item['ProductionYear'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], 0, item['LastScraped'], item['DateCreated'], KodiAlbumId, Compilation, item['Studio'], item['RunTimeTicks'], item['AlbumArtistSortName'])
                LOG.info("UPDATE existing album [%s] %s: %s" % (KodiAlbumId, item['Name'], item['Id']))

            # Add new Kodi Album
            if item['Library']['Id'] not in ExistingEmbyDBLibraryIds:
                self.NEWKodiAlbumId = self.music_db.add_album(item['Name'], AlbumType, item['AlbumArtist'], item['ProductionYear'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], 0, item['LastScraped'], item['DateCreated'], item['ProviderIds']['MusicBrainzAlbum'], item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, item['Studio'], item['RunTimeTicks'], item['AlbumArtistSortName'], item['Library']['LibraryId_Name'])
                KodiAlbumIds.append(self.NEWKodiAlbumId)
                ExistingEmbyDBKodiIds = "%s;%s" % (ExistingEmbyDBKodiIds, self.NEWKodiAlbumId)
                ExistingEmbyKodiParentIds = "%s;%s" % (ExistingEmbyKodiParentIds, item['ArtistItemsKodiId'])
                ExistingEmbyDBLibraryIds = "%s;%s" % (ExistingEmbyDBLibraryIds, item['Library']['Id'])
                ExistingEmbyDBPresentationUniqueKeys = "%s;%s" % (ExistingEmbyDBPresentationUniqueKeys, item['PresentationUniqueKey'])
                LOG.info("UPDATE new album [%s] %s: %s" % (self.NEWKodiAlbumId, item['Name'], item['Id']))

            self.emby_db.update_reference(ExistingEmbyDBKodiIds, None, None, "MusicAlbum", AlbumType, ExistingEmbyKodiParentIds, ExistingEmbyDBLibraryIds, None, ExistingEmbyDBPresentationUniqueKeys, item['UserData']['IsFavorite'], item['Id'])
        else:
            self.NEWKodiAlbumId = self.music_db.add_album(item['Name'], AlbumType, item['AlbumArtist'], item['ProductionYear'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], 0, item['LastScraped'], item['DateCreated'], item['ProviderIds']['MusicBrainzAlbum'], item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, item['Studio'], item['RunTimeTicks'], item['AlbumArtistSortName'], item['Library']['LibraryId_Name'])
            self.emby_db.add_reference(item['Id'], self.NEWKodiAlbumId, None, None, "MusicAlbum", AlbumType, item['ArtistItemsKodiId'], item['Library']['Id'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'])

            KodiAlbumIds.append(self.NEWKodiAlbumId)
            LOG.info("ADD album [%s] %s: %s" % (self.NEWKodiAlbumId, item['Name'], item['Id']))

        if self.NEWKodiAlbumId:
            for index, ArtistTotalItem in enumerate(item['ArtistTotalItems']):
                self.music_db.link_album_artist(ArtistTotalItem['KodiId'], self.NEWKodiAlbumId, ArtistTotalItem['Name'], index)
                self.music_db.add_discography(ArtistTotalItem['KodiId'], item['Name'], item['ProductionYear'], item['ProviderIds']['MusicBrainzReleaseGroup'])

        for KodiAlbumId in KodiAlbumIds:
            self.music_db.common.add_artwork(item['KodiArtwork'], KodiAlbumId, AlbumType)

        return not update

    def song(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        if not item['Path']:
            LOG.warning("Path %s not found" % item['Name'])
            return False

        update = True
        KodiSongId = ""
        KodiPathId = ""

        if item['ExistingItem']:
            KodiSongId = item['ExistingItem'][0]
            KodiPathId = item['ExistingItem'][2]
        else:
            update = False
            LOG.debug("SongId %s not found" % item['Id'])

        if not common.get_file_path(item, "audio"):
            return False

        self.get_ArtistInfos(item, "ArtistItems")
        self.get_ArtistInfos(item, "AlbumArtists")
        item['AlbumId'] = item.get('AlbumId', None)

        # Inject fake Artist
        if not item['ArtistItemsSortName']:
            NoInfoArtistItem = item.copy()
            NoInfoArtistItem['Id'] = "9999998"
            NoInfoArtistItem['Name'] = "--NO INFO--"
            NoInfoArtistItem['SortName'] = "--NO INFO--"
            self.artist(NoInfoArtistItem)
            item['ArtistItemsSortName'] = "--NO INFO--"
            item['ArtistItemsArtistName'] = "--NO INFO--"
            item['ArtistItems'] = [{'Name': "--NO INFO--", 'Id': NoInfoArtistItem['Id'], 'KodiId': self.NEWKodiArtistId, 'SortName': "--NO INFO--"}]

        item["ArtistTotalItems"] = item["ArtistItems"].copy()

        for AlbumArtist in item["AlbumArtists"]:
            if AlbumArtist not in item["ArtistTotalItems"]:
                item["ArtistTotalItems"].append(AlbumArtist)

        Single = False

        if item['AlbumId']:
            e_item = self.emby_db.get_item_by_id(item['AlbumId'])
            Found = False

            if e_item:
                self.NEWKodiAlbumId = get_KodiArtistEmbyDB(e_item, item['Library']['Id'])

                if self.NEWKodiAlbumId:
                    Found = True

            if not Found:
                AlbumItem = self.EmbyServer.API.get_Item(item['AlbumId'], ['MusicAlbum'], False, False)

                if AlbumItem:
                    AlbumItem['Library'] = item['Library']
                    self.album(AlbumItem)
                else: # This should never happen
                    LOG.error("Album not found, but AlbumId was assigned: %s" % item['AlbumId'])
                    Single = True


        else:  # Single
            Single = True

        if Single:
            # Inject fake Single Album
            SingleAlbumItem = item.copy()
            SingleAlbumItem['Id'] = "9999999%s" % item["ArtistItems"][0]['Id']
            SingleAlbumItem['Name'] = "--NO INFO--"
            SingleAlbumItem['SortName'] = "--NO INFO--"
            SingleAlbumItem['AlbumArtist'] = item["ArtistItems"][0]['Name']
            item['AlbumId'] = SingleAlbumItem['Id']
            self.album(SingleAlbumItem)

            if not self.NEWKodiAlbumId :
                e_item = self.emby_db.get_item_by_id(item['AlbumId'])
                self.NEWKodiAlbumId = get_KodiArtistEmbyDB(e_item, item['Library']['Id'])

        common.get_filename(item, "a", self.EmbyServer.API)
        common.set_RunTimeTicks(item)
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['ProductionYear'] = item.get('ProductionYear', None)
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzTrack'] = item['ProviderIds'].get('MusicBrainzTrack', None)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 0)
        item['UserData']['LastPlayedDate'] = item['UserData'].get('LastPlayedDate', None)

        if 'PremiereDate' in  item:
            item['PremiereDate'] = utils.convert_to_local(item['PremiereDate'])[:10]
        else:
            item['PremiereDate'] = item['ProductionYear']

        common.set_genres(item)
        common.set_overview(item)
        common.set_KodiArtwork(item, self.EmbyServer.server_id)
        common.get_streams(item)
        common.set_playstate(item)

        # Track and disc number
        if item['IndexNumber']:
            item['IndexNumber'] = item['ParentIndexNumber'] * 65536 + item['IndexNumber']

        if update:
            self.music_db.common.delete_artwork(KodiSongId, "song")
            self.music_db.delete_link_song_artist(KodiSongId)
            self.music_db.update_song(self.NEWKodiAlbumId, item['ArtistItemsName'], item['Genre'], item['Name'], item['IndexNumber'], item['RunTimeTicks'], item['PremiereDate'], item['ProductionYear'], item['Filename'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], 0, item['Overview'], item['DateCreated'], KodiSongId, item['Streams'][0]['Audio'][0]["BitRate"], item['Streams'][0]['Audio'][0]["SampleRate"], item['Streams'][0]['Audio'][0]["channels"], item['ProviderIds']['MusicBrainzTrack'], item['ArtistItemsSortName'], item['Library']['LibraryId_Name'])
            self.emby_db.update_reference(KodiSongId, None, KodiPathId, "Audio", "song", self.NEWKodiAlbumId, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
            LOG.info("UPDATE song [%s/%s/%s] %s: %s" % (KodiPathId, self.NEWKodiAlbumId, KodiSongId, item['Id'], item['Name']))
        else:
            KodiSongId, KodiPathId = self.music_db.add_song(self.NEWKodiAlbumId, item['ArtistItemsName'], item['Genre'], item['Name'], item['IndexNumber'], item['RunTimeTicks'], item['PremiereDate'], item['ProductionYear'], item['Filename'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], 0, item['Overview'], item['DateCreated'], item['Streams'][0]['Audio'][0]["BitRate"], item['Streams'][0]['Audio'][0]["SampleRate"], item['Streams'][0]['Audio'][0]["channels"], item['ProviderIds']['MusicBrainzTrack'], item['ArtistItemsSortName'], item['Library']['LibraryId_Name'], item['Path'])
            self.emby_db.add_reference(item['Id'], KodiSongId, None, KodiPathId, "Audio", "song", self.NEWKodiAlbumId, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD song [%s/%s/%s] %s: %s" % (KodiPathId, self.NEWKodiAlbumId, KodiSongId, item['Id'], item['Name']))

        for index, ArtistTotalItem in enumerate(item['ArtistTotalItems']):
            self.music_db.link_song_artist(ArtistTotalItem['KodiId'], KodiSongId, 1, index, ArtistTotalItem['Name'])

        self.music_db.update_genres(KodiSongId, item['Genres'], "song")
        self.music_db.common.add_artwork(item['KodiArtwork'], KodiSongId, "song")
        return not update

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    # Poster with progress bar
    def userdata(self, Item):
        if Item['Type'] == 'Audio':
            common.set_userdata_update_data(Item)
            self.music_db.rate_song(Item['PlayCount'], Item['LastPlayedDate'], 0, Item['KodiItemId'])

        self.emby_db.update_reference_userdatachanged(Item['Id'], Item['IsFavorite'])
        LOG.info("USERDATA %s [%s] %s" % (Item['Type'], Item['KodiItemId'], Item['Id']))

    def remove(self, Item):
        if Item['Type'] == 'Audio':
            self.music_db.delete_song(Item['KodiItemId'])
            self.emby_db.remove_item_music(Item['Id'])
            LOG.info("DELETE song [%s] %s" % (Item['KodiItemId'], Item['Id']))
            return

        if 'Multi' in Item['Library']:
            LibraryIds = Item['Library']['Multi'].split(";")
            KodiItemIds = str(Item['KodiItemId']).split(";")
        else:
            LibraryIds = [Item['Library']['Id']]
            KodiItemIds = [Item['KodiItemId']]

        for Index, LibraryId in enumerate(LibraryIds):
            if not Item['DeleteByLibraryId'] or LibraryId in Item['DeleteByLibraryId']:
                if Item['Type'] == 'MusicAlbum':
                    self.music_db.common.delete_artwork(KodiItemIds[Index], "album")
                    self.music_db.common.delete_artwork(KodiItemIds[Index], "single")
                    self.music_db.delete_album(KodiItemIds[Index], LibraryId)
                    LOG.info("DELETE album [%s] %s" % (KodiItemIds[Index], Item['Id']))
                elif Item['Type'] == 'MusicArtist':
                    self.music_db.common.delete_artwork(KodiItemIds[Index], "artist")
                    self.music_db.delete_artist(KodiItemIds[Index], LibraryId)
                    LOG.info("DELETE artist [%s] %s" % (KodiItemIds[Index], Item['Id']))

                self.emby_db.remove_item_music_by_libraryId(Item['Id'], LibraryId)

    def get_ArtistInfos(self, item, Id):
        Artists = []
        SortNames = []
        KodiIds = []

        for ArtistItem in item[Id]:
            Artists.append(ArtistItem['Name'])

            if ArtistItem['Id']:
                Found = False
                e_item = self.emby_db.get_item_by_id(int(ArtistItem['Id']))

                if e_item:
                    ArtistItem['KodiId'] = get_KodiArtistEmbyDB(e_item, item['Library']['Id'])

                    if ArtistItem['KodiId']:
                        ArtistItem['KodiId'] = ArtistItem['KodiId']
                        Found = True

                if not Found:
                    LOG.warning("Artist query: %s" % ArtistItem['Id'])
                    ArtistEmbyItem = self.EmbyServer.API.get_Item(ArtistItem['Id'], ['MusicArtist'], False, False)

                    if not ArtistEmbyItem:
                        LOG.error("Artist not found: %s" % ArtistItem['Id'])
                        continue

                    LOG.warning("Artist added: %s" % ArtistEmbyItem['Id'])
                    ArtistEmbyItem['Library'] = item['Library']
                    self.artist(ArtistEmbyItem)

                    if not self.NEWKodiArtistId:
                        LOG.info("Artist added issue: %s" % ArtistItem['Id'])
                        continue

                    ArtistItem['KodiId'] = self.NEWKodiArtistId

                KodiIdList = str(ArtistItem['KodiId']).split(",")
                ArtistItem['SortName'] = self.music_db.get_ArtistSortname(KodiIdList[0])
                KodiIds.append(str(ArtistItem['KodiId']))
                Sortname = ArtistItem['SortName'].replace("The ", "")
                Sortname = Sortname.replace("Der ", "")
                Sortname = Sortname.replace("Die ", "")
                Sortname = Sortname.replace("Das ", "")
                SortNames.append(Sortname)

                if 'AlbumArtist' in item:
                    if item['AlbumArtist'] == ArtistItem['Name']:
                        item['AlbumArtistSortName'] = ArtistItem['SortName']

        item["%sSortName" % Id] = " / ".join(SortNames)
        item['%sName' % Id] = " / ".join(Artists)
        item['%sKodiId' % Id] = ",".join(KodiIds)

def get_KodiArtistEmbyDB(e_item, LibraryId):
    ExistingEmbyDBLibraryIds = str(e_item[6])

    if LibraryId in ExistingEmbyDBLibraryIds:
        ExistingEmbyDBKodiIds = str(e_item[0])
        ExistingEmbyDBLibraryIdsList = ExistingEmbyDBLibraryIds.split(";")
        ExistingEmbyDBKodiIdsList = ExistingEmbyDBKodiIds.split(";")
        Index = ExistingEmbyDBLibraryIdsList.index(LibraryId)
        return ExistingEmbyDBKodiIdsList[Index]

    return None

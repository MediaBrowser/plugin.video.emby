import xbmc
from helper import utils
from . import common


class Music:
    def __init__(self, EmbyServer, embydb, musicdb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.music_db = musicdb

    def artist(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "MusicArtist"):
            xbmc.log(f"EMBY.core.music artist, general error: Process item: {item}", 3) # LOGERROR
            return False

        if not 'Name' in item:
            xbmc.log(f"EMBY.core.music artist, no name: Process item: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.music: Process item: {item['Name']}", 1) # LOGINFO
        ItemIndex = 0
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzArtist'] = item['ProviderIds'].get('MusicBrainzArtist', None)
        common.set_genres(item)
        common.set_overview(item)
        common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)

        for ItemIndex in range(len(item['Librarys'])):
            if item['UpdateItems'][ItemIndex]:
                self.music_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "artist")
                self.music_db.update_artist(item['KodiItemIds'][ItemIndex], item['Name'], item['ProviderIds']['MusicBrainzArtist'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], item['LastScraped'], item['SortName'], item['DateCreated'])
                self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                xbmc.log(f"EMBY.core.music: UPDATE existing artist [{item['KodiItemIds'][ItemIndex]}] {item['Name']}: {item['Id']}", 1) # LOGINFO
            else:
                item['KodiItemIds'][ItemIndex] = self.music_db.create_entry_artist()
                self.music_db.add_artist(item['KodiItemIds'][ItemIndex], item['Name'], item['ProviderIds']['MusicBrainzArtist'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], item['LastScraped'], item['SortName'], item['DateCreated'], item['Librarys'][ItemIndex]['LibraryId_Name'])
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "MusicArtist", "artist", [], item['LibraryIds'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)
                xbmc.log(f"EMBY.core.music: ADD artist [{item['KodiItemIds'][ItemIndex]}] {item['Name']}: {item['Id']}", 1) # LOGINFO

            self.music_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "artist")

        return not item['UpdateItems'][ItemIndex]

    def album(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "MusicAlbum"):
            xbmc.log(f"EMBY.core.music album, general error: Process item: {item}", 3) # LOGERROR
            return False

        if not 'Name' in item:
            xbmc.log(f"EMBY.core.music album, no name: Process item: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.music: Process item: {item['Name']}", 1) # LOGINFO
        ItemIndex = 0
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProductionYear'] = item.get('ProductionYear', "")
        common.set_studios(item)
        common.set_genres(item)
        common.set_overview(item)
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzAlbum'] = item['ProviderIds'].get('MusicBrainzAlbum', None)
        item['ProviderIds']['MusicBrainzReleaseGroup'] = item['ProviderIds'].get('MusicBrainzReleaseGroup', None)
        common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
        common.set_RunTimeTicks(item)

        if not item['ProductionYear']:
            if 'PremiereDate' in  item:
                item['ProductionYear'] = utils.convert_to_local(item['PremiereDate'])[:10]

        if str(item['Id']).startswith("999999999"):
            AlbumType = "single"
        else:
            AlbumType = "album"

        for ItemIndex in range(len(item['Librarys'])):
            if not item['UpdateItems'][ItemIndex]:
                item['KodiItemIds'][ItemIndex] = self.music_db.create_entry_album()
                xbmc.log(f"EMBY.core.music: AlbumId {item['Id']} not found", 0) # LOGDEBUG

            self.get_ArtistInfos(item, "ArtistItems", ItemIndex)
            self.get_ArtistInfos(item, "AlbumArtists", ItemIndex)

            # Detect compilations
            Compilation = 0

            if item['AlbumArtistsName'].lower() in ("various artists", "various", "various items", "sountrack"):
                Compilation = 1
                xbmc.log(f"EMBY.core.music: Compilation detected: {item['Name']}", 1) # LOGINFO

            if item['UpdateItems'][ItemIndex]:
                # Update all existing Kodi Albums
                self.music_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "single")
                self.music_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "album")
                self.music_db.update_album(item['KodiItemIds'][ItemIndex], item['Name'], AlbumType, item['AlbumArtistsName'], item['ProductionYear'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], 0, item['LastScraped'], item['DateCreated'], item['ProviderIds']['MusicBrainzAlbum'], item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, item['Studio'], item['RunTimeTicks'], item['AlbumArtistsSortName'])
                self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                xbmc.log(f"EMBY.core.music: UPDATE existing album [{item['KodiItemIds'][ItemIndex]}] {item['Name']}: {item['Id']}", 1) # LOGINFO
            else:
                self.music_db.add_album(item['KodiItemIds'][ItemIndex], item['Name'], AlbumType, item['AlbumArtistsName'], item['ProductionYear'], item['Genre'], item['Overview'], item['KodiArtwork']['thumb'], 0, item['LastScraped'], item['DateCreated'], item['ProviderIds']['MusicBrainzAlbum'], item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, item['Studio'], item['RunTimeTicks'], item['AlbumArtistsSortName'], item['Librarys'][ItemIndex]['LibraryId_Name'])
                item['KodiParentIds'][ItemIndex] = item['ArtistItemsKodiId']
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], None, "MusicAlbum", AlbumType, item['KodiParentIds'], item['LibraryIds'], None, item['PresentationUniqueKey'], item['UserData']['IsFavorite'], None, None, None, None)

                for index, AlbumArtist in enumerate(item["AlbumArtists"]):
                    self.music_db.link_album_artist(AlbumArtist['KodiId'], item['KodiItemIds'][ItemIndex], AlbumArtist['Name'], index)

                xbmc.log(f"EMBY.core.music: ADD album [{item['KodiItemIds'][ItemIndex]}] {item['Name']}: {item['Id']}", 1) # LOGINFO

            self.music_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], AlbumType)

        return not item['UpdateItems'][ItemIndex]

    def song(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "Audio"):
            xbmc.log(f"EMBY.core.music song, general error: Process item: {item}", 3) # LOGERROR
            return False

        if not 'Name' in item:
            xbmc.log(f"EMBY.core.music song, no name: Process item: {item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.music: Process item: {item['Name']}", 1) # LOGINFO
        ItemIndex = 0
        item['AlbumId'] = item.get('AlbumId', None)
        common.set_RunTimeTicks(item)
        item['LastScraped'] = utils.currenttime_kodi_format()
        item['ProductionYear'] = item.get('ProductionYear', "")
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
        item['ProviderIds'] = item.get('ProviderIds', [])
        item['ProviderIds']['MusicBrainzTrack'] = item['ProviderIds'].get('MusicBrainzTrack', None)
        item['IndexNumber'] = item.get('IndexNumber', 0)
        item['ParentIndexNumber'] = item.get('ParentIndexNumber', 0)
        item['UserData']['LastPlayedDate'] = item['UserData'].get('LastPlayedDate', None)
        common.set_genres(item)
        common.set_overview(item)
        common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
        common.get_streams(item)
        common.set_playstate(item)

        # Track and disc number
        if item['IndexNumber']:
            item['IndexNumber'] = item['ParentIndexNumber'] * 65536 + item['IndexNumber']

        if 'PremiereDate' in  item:
            item['PremiereDate'] = utils.convert_to_local(item['PremiereDate'])[:10]

            if not item['ProductionYear']:
                item['ProductionYear'] = item['PremiereDate']
        else:
            item['PremiereDate'] = item['ProductionYear']

        for ItemIndex in range(len(item['Librarys'])):
            if not common.get_file_path(item, "audio", ItemIndex):
                continue

            if not item['UpdateItems'][ItemIndex]:
                item['KodiItemIds'][ItemIndex] = self.music_db.create_entry_song()
                xbmc.log(f"EMBY.core.music: SongId {item['Id']} not found", 0) # LOGDEBUG

            item['KodiPathId'] = self.music_db.get_add_path(item['Path'])
            self.get_ArtistInfos(item, "Composers", ItemIndex)
            self.get_ArtistInfos(item, "ArtistItems", ItemIndex)

            # Inject fake Artist
            if not item['ArtistItemsSortName']:
                NoInfoArtistItem = item.copy()
                NoInfoArtistItem['Id'] = "999999998"
                NoInfoArtistItem['Name'] = "--NO INFO--"
                NoInfoArtistItem['SortName'] = "--NO INFO--"
                self.artist(NoInfoArtistItem)
                item['ArtistItemsSortName'] = "--NO INFO--"
                item['ArtistItemsArtistName'] = "--NO INFO--"
                item['ArtistItems'] = [{'Name': "--NO INFO--", 'Id': "999999998"}]
                self.get_ArtistInfos(item, "Composers", ItemIndex)
                self.get_ArtistInfos(item, "ArtistItems", ItemIndex)

            if item['AlbumId']:
                item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['AlbumId'], item['LibraryIds'][ItemIndex])

                if not item['KodiParentIds'][ItemIndex]:
                    xbmc.log(f"EMBY.core.music: Load album: {item['AlbumId']}", 2) # LOGWARNING
                    AlbumItem = self.EmbyServer.API.get_Item(item['AlbumId'], ['MusicAlbum'], False, False)

                    if not AlbumItem:
                        xbmc.log(f"EMBY.core.music: Album not found: {item['AlbumId']}", 3) # LOGERROR
                        return False

                    AlbumItem['Library'] = {'Id': item['Librarys'][ItemIndex]['Id'], 'Name': item['Librarys'][ItemIndex]['Name'], 'LibraryId_Name': item['Librarys'][ItemIndex]['LibraryId_Name']}
                    self.album(AlbumItem)
                    item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['AlbumId'], item['LibraryIds'][ItemIndex])
            else:  # Single
                # Inject fake Single Album
                SingleAlbumItem = item.copy()

                if item['AlbumArtists']:
                    SingleAlbumItem['Id'] = f"999999999{item['AlbumArtists'][0]['Id']}"
                else:
                    SingleAlbumItem['Id'] = f"999999999{item['ArtistItems'][0]['Id']}"
                    SingleAlbumItem['AlbumArtist'] = item["ArtistItems"][0]['Name']
                    SingleAlbumItem['AlbumArtists'] = [{'Name': item["ArtistItems"][0]['Name'], 'Id': item["ArtistItems"][0]['Id']}]

                SingleAlbumItem['Name'] = "--NO INFO--"
                SingleAlbumItem['SortName'] = "--NO INFO--"
                item['AlbumId'] = SingleAlbumItem['Id']
                self.album(SingleAlbumItem)
                item['KodiParentIds'][ItemIndex] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(item['AlbumId'], item['LibraryIds'][ItemIndex])

            common.get_filename(item, self.EmbyServer.API, ItemIndex, "audio")

            if 'Streams' in item and item['Streams'] and 'Audio' in item['Streams'][0] and item['Streams'][0]['Audio']:
                Channels = item['Streams'][0]['Audio'][0]["channels"]
                SampleRate = item['Streams'][0]['Audio'][0]["SampleRate"]
                BitRate = item['Streams'][0]['Audio'][0]["BitRate"]
            else:
                Channels = None
                SampleRate = None
                BitRate = None

            if item['UpdateItems'][ItemIndex]:
                self.music_db.common.delete_artwork(item['KodiItemIds'][ItemIndex], "song")
                self.music_db.delete_link_song_artist(item['KodiItemIds'][ItemIndex])
                self.music_db.update_song(item['KodiItemIds'][ItemIndex], item['KodiPathId'], item['KodiParentIds'][ItemIndex], item['ArtistItemsName'], item['Genre'], item['Name'], item['IndexNumber'], item['RunTimeTicks'], item['PremiereDate'], item['ProductionYear'], item['Filename'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], 0, item['Overview'], item['DateCreated'], BitRate, SampleRate, Channels, item['ProviderIds']['MusicBrainzTrack'], item['ArtistItemsSortName'], item['Librarys'][ItemIndex]['LibraryId_Name'])
                self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                xbmc.log(f"EMBY.core.music: UPDATE song [{item['KodiParentIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO
            else:
                self.music_db.add_song(item['KodiItemIds'][ItemIndex], item['KodiPathId'], item['KodiParentIds'][ItemIndex], item['ArtistItemsName'], item['Genre'], item['Name'], item['IndexNumber'], item['RunTimeTicks'], item['PremiereDate'], item['ProductionYear'], item['Filename'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], 0, item['Overview'], item['DateCreated'], BitRate, SampleRate, Channels, item['ProviderIds']['MusicBrainzTrack'], item['ArtistItemsSortName'], item['Librarys'][ItemIndex]['LibraryId_Name'])
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], [], item['KodiPathId'], "Audio", "song", item['KodiParentIds'], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
                xbmc.log(f"EMBY.core.music: ADD song [{item['KodiPathId']} / {item['KodiParentIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO

            for index, ArtistItem in enumerate(item['ArtistItems']):
                self.music_db.link_song_artist(ArtistItem['KodiId'], item['KodiItemIds'][ItemIndex], 1, index, ArtistItem['Name'])

            for index, Composer in enumerate(item['Composers']):
                self.music_db.link_song_artist(Composer['KodiId'], item['KodiItemIds'][ItemIndex], 2, index, Composer['Name'])

            self.music_db.update_genres_song(item['KodiItemIds'][ItemIndex], item['Genres'])
            self.music_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], "song")

        return not item['UpdateItems'][ItemIndex]

    def userdata(self, Item):
        Item['Library'] = {}

        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        for ItemIndex in range(len(Item['Librarys'])):
            if Item['Type'] == 'Audio':
                common.set_userdata_update_data(Item)
                self.music_db.rate_song(Item['PlayCount'], Item['LastPlayedDate'], 0, Item['KodiItemIds'][ItemIndex])

            self.emby_db.update_favourite(Item['Id'], Item['IsFavorite'])
            xbmc.log(f"EMBY.core.music: USERDATA {Item['Type']} [{Item['KodiItemIds'][ItemIndex]}] {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        if Item['DeleteByLibraryId']:
            if Item['Type'] == 'Audio':
                self.music_db.delete_song(Item['KodiItemId'])
                xbmc.log(f"EMBY.core.music: DELETE song [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif Item['Type'] == 'MusicAlbum':
                self.music_db.delete_album(Item['KodiItemId'])
                xbmc.log(f"EMBY.core.music: DELETE album [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif Item['Type'] == 'MusicArtist':
                self.music_db.delete_artist(Item['KodiItemId'])
                xbmc.log(f"EMBY.core.music: DELETE artist [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        else:
            if Item['Type'] == 'Audio':
                DeleteEmbyItems = self.music_db.delete_song_stacked(Item['KodiItemId'])

                for DeleteEmbyItem in DeleteEmbyItems:
                    xbmc.log(f"EMBY.core.music: Clean music: {DeleteEmbyItem[0]} / {DeleteEmbyItem[1]}", 2) # LOGWARNING
                    self.emby_db.remove_item_music_by_kodiid(DeleteEmbyItem[0], DeleteEmbyItem[1])

                xbmc.log(f"EMBY.core.music: DELETE song [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif Item['Type'] == 'MusicAlbum':
                DeleteEmbyItems = self.music_db.delete_album_stacked(Item['KodiItemId'])

                for DeleteEmbyItem in DeleteEmbyItems:
                    xbmc.log(f"EMBY.core.music: Clean music: {DeleteEmbyItem[0]} / {DeleteEmbyItem[1]}", 2) # LOGWARNING
                    self.emby_db.remove_item_music_by_kodiid(DeleteEmbyItem[0], DeleteEmbyItem[1])

                xbmc.log(f"EMBY.core.music: DELETE album [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
            elif Item['Type'] == 'MusicArtist':
                self.music_db.delete_artist(Item['KodiItemId'])
                xbmc.log(f"EMBY.core.music: DELETE artist [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

        self.emby_db.remove_item(Item['Id'], Item['Library']['Id'])

    def get_ArtistInfos(self, Item, Id, ItemIndex):
        Artists = []
        SortNames = []
        KodiIds = []

        for ArtistItem in Item[Id]:
            Artists.append(ArtistItem['Name'])

            if ArtistItem['Id']:
                ArtistItem['KodiId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(ArtistItem['Id'], Item['LibraryIds'][ItemIndex])

                if not ArtistItem['KodiId']:
                    xbmc.log(f"EMBY.core.music: Load artist: {ArtistItem['Id']}", 2) # LOGWARNING
                    ArtistEmbyItem = self.EmbyServer.API.get_Item(ArtistItem['Id'], ['MusicArtist'], False, False)

                    if not ArtistEmbyItem:
                        xbmc.log(f"EMBY.core.music: Artist not found: {ArtistItem['Id']}", 3) # LOGERROR
                        continue

                    xbmc.log(f"EMBY.core.music: Artist added: {ArtistEmbyItem['Id']}", 2) # LOGWARNING
                    ArtistEmbyItem['Library'] = {'Id': Item['Librarys'][ItemIndex]['Id'], 'Name': Item['Librarys'][ItemIndex]['Name'], 'LibraryId_Name': Item['Librarys'][ItemIndex]['LibraryId_Name']}
                    self.artist(ArtistEmbyItem)
                    ArtistItem['KodiId'] = self.emby_db.get_KodiId_by_EmbyId_EmbyLibraryId(ArtistItem['Id'], Item['LibraryIds'][ItemIndex])

                SortNames.append(self.music_db.get_ArtistSortname(ArtistItem['KodiId']))
                KodiIds.append(str(ArtistItem['KodiId']))

        Item[f"{Id}SortName"] = " / ".join(SortNames)
        Item[f"{Id}Name"] = " / ".join(Artists)
        Item[f"{Id}KodiId"] = ",".join(KodiIds)

import xbmc
from helper import utils
from . import common, musicartist, musicalbum, musicgenre


class Audio:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.MusicArtistObject = musicartist.MusicArtist(EmbyServer, self.SQLs)
        self.MusicAlbumObject = musicalbum.MusicAlbum(EmbyServer, self.SQLs)
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if 'Path' not in Item:
            xbmc.log(f"EMBY.core.audio: Path not found: {Item}", 3) # LOGERROR
            return False

        xbmc.log(f"EMBY.core.audio: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Audio"):
            return False

        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        Item["MusicAlbum"] = Item.get('Album', None)
        Item["MusicAlbumId"] = Item.get('AlbumId', None)

        # Track and disc number
        if Item['IndexNumber'] and Item['ParentIndexNumber']:
            Item['IndexNumber'] = Item['ParentIndexNumber'] * 65536 + Item['IndexNumber']

        if not Item['IndexNumber']:
            Item['IndexNumber'] = 0 # Mymusic.db does not execpt NULL, it would result in invalid album disc numbers

        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', None, 1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "Composers", Item['LibraryId'], 1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "ArtistItems", Item['LibraryId'], 1, IncrementalSync)
        common.set_ItemsDependencies(Item, self.SQLs, self.MusicAlbumObject, self.EmbyServer, "MusicAlbum", IncrementalSync)
        common.get_MusicArtistInfos(Item, "Composers", self.SQLs)
        common.get_MusicArtistInfos(Item, "ArtistItems", self.SQLs)
        common.set_streams(Item)
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
        Item['KodiPathId'] = self.SQLs["music"].get_add_path(Item['KodiPath'])
        KodiAlbumIds, KodiAlbumLibraryIds = self.SQLs["emby"].get_MusicAlbum_by_EmbyId(Item['MusicAlbumId'])

        if Item['MediaSources'][0]['KodiStreams']['Audio']:
            Channels = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("channels", None)
            SampleRate = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("SampleRate", None)
            BitRate = Item['MediaSources'][0]['KodiStreams']['Audio'][0].get("BitRate", None)
        else:
            Channels = None
            SampleRate = None
            BitRate = None

        if Item['KodiItemIds']:
            KodiItemIds = Item['KodiItemIds'].split(",")
        else:
            KodiItemIds = []

        if Item['LibraryIds']:
            LibraryIds = Item['LibraryIds'].split(",")
        else:
            LibraryIds = []

        # Update all existing Kodi songs
        for Index, LibraryId in enumerate(LibraryIds):
            if Item['Name'] == "--NO INFO--": # Skip injected items updates
                return False

            self.SQLs["music"].common_db.delete_artwork(KodiItemIds[Index], "song")
            self.SQLs["music"].delete_link_song_artist(KodiItemIds[Index])
            KodiAlbumId = KodiAlbumIds[KodiAlbumLibraryIds.index(LibraryId)]
            self.SQLs["music"].update_song(KodiItemIds[Index], Item['KodiPathId'], KodiAlbumId, Item['ArtistItemsName'], Item['MusicGenre'], Item['Name'], Item['IndexNumber'], Item['KodiRunTimeTicks'], Item['KodiPremiereDate'], Item['KodiProductionYear'], Item['KodiFilename'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], 0, Item['Overview'], Item['KodiDateCreated'], BitRate, SampleRate, Channels, Item['ProviderIds']['MusicBrainzTrack'], Item['ArtistItemsSortName'], Item['LibraryId'], Item['KodiPath'])
            self.set_links(Item, KodiItemIds[Index])

            # Album reference has changed
            if str(Item['MusicAlbumId']) != str(Item['MusicAlbumIdExisting']):
                KodiAlbumIdOld = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(Item['MusicAlbumIdExisting'], "MusicAlbum")
                self.SQLs["music"].delete_abandonedalbum([str(KodiAlbumIdOld)])

            xbmc.log(f"EMBY.core.audio: UPDATE [{KodiAlbumId} / {KodiItemIds[Index]}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemIds[Index]}", "KodiType": "audio"}, IncrementalSync)

        # New library (insert new Kodi record)
        if Item['LibraryId'] not in LibraryIds:
            KodiAlbumId = KodiAlbumIds[KodiAlbumLibraryIds.index(Item['LibraryId'])]
            KodiItemId = self.SQLs["music"].add_song(Item['KodiPathId'], KodiAlbumId, Item['ArtistItemsName'], Item['MusicGenre'], Item['Name'], Item['IndexNumber'], Item['KodiRunTimeTicks'], Item['KodiPremiereDate'], Item['KodiProductionYear'], Item['KodiFilename'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], 0, Item['Overview'], Item['KodiDateCreated'], BitRate, SampleRate, Channels, Item['ProviderIds']['MusicBrainzTrack'], Item['ArtistItemsSortName'], Item['LibraryId'])
            LibraryIds.append(str(Item['LibraryId']))
            KodiItemIds.append(str(KodiItemId))
            self.SQLs["emby"].add_reference_audio(Item['Id'], Item['LibraryId'], KodiItemIds, Item['UserData']['IsFavorite'], Item['Path'], Item['KodiPathId'], LibraryIds, Item['MusicAlbumId'])
            self.set_links(Item, KodiItemId)
            xbmc.log(f"EMBY.core.audio: ADD [{Item['KodiPathId']} / {KodiAlbumId} / {KodiItemId}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "audio"}, IncrementalSync)
        else:
            self.SQLs["emby"].update_reference_audio(Item['UserData']['IsFavorite'], Item['Id'], Item['LibraryId'], Item['MusicAlbumId'])

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Song", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        return not Item['UpdateItem']

    def set_links(self, Item, KodiItemId):
        common.set_MusicArtist_links(KodiItemId, self.SQLs, Item["ArtistItems"], Item['LibraryId'], 1)
        common.set_MusicArtist_links(KodiItemId, self.SQLs, Item["Composers"], Item['LibraryId'], 2)
        common.set_MusicGenre_links(KodiItemId, self.SQLs, "song", Item["GenreItems"], 1)
        self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemId, "song")

    def userdata(self, Item):
        common.set_playstate(Item)

        for KodiItemId in Item['KodiItemId'].split(","):
            self.SQLs["music"].rate_song(Item['KodiPlayCount'], Item['KodiLastPlayedDate'], 0, KodiItemId)
            FullPath, ImageUrl, Itemname = self.SQLs["music"].get_favoriteData(KodiItemId, "song")
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Song", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], ImageUrl), Item['IsFavorite'], FullPath, Itemname, "media", 0),))
            self.SQLs["emby"].update_favourite(Item['Id'], Item['IsFavorite'], "Audio")
            xbmc.log(f"EMBY.core.audio: USERDATA {Item['Type']} [{KodiItemId}] {Item['Id']}", 1) # LOGINFO
            utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{KodiItemId}", "KodiType": "audio"}, True)

        return True

    def remove(self, Item, IncrementalSync):
        FullPath, ImageUrl, Itemname = self.SQLs["music"].get_favoriteData(Item['KodiItemId'], "song")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Song", "Songs", Item['Id'], self.EmbyServer.ServerData['ServerId'], ImageUrl), False, FullPath, Itemname, "media", 0),))
        self.SQLs["emby"].remove_item(Item['Id'], "Audio", Item['LibraryId'])
        self.SQLs["music"].delete_song(Item['KodiItemId'], Item['LibraryId'])
        xbmc.log(f"EMBY.core.audio: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "audio"}, IncrementalSync)

    def set_favorite(self, IsFavorite, KodiItemId, EmbyItemId):
        FullPath, ImageUrl, Itemname = self.SQLs["music"].get_favoriteData(KodiItemId, "song")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Song", "Songs", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, FullPath, Itemname, "media", 0),))

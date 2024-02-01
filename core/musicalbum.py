import xbmc
from helper import pluginmenu, utils
from . import common, musicartist, musicgenre, studio


class MusicAlbum:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.MusicArtistObject = musicartist.MusicArtist(EmbyServer, self.SQLs)
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)

    def change(self, Item):
        common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicAlbum")
        xbmc.log(f"EMBY.core.musicalbum: Process item: {Item['Name']}", 0) # DEBUG
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", 'Studios')
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', None, 1)
        common.set_RunTimeTicks(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)

        if int(Item['Id']) > 999999900:
            AlbumType = "single"
        else:
            AlbumType = "album"

        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", "AlbumArtists", Item['LibraryId'], 1)
        isFavorite = common.set_Favorite(Item)
        common.get_MusicArtistInfos(Item, "AlbumArtists", self.SQLs)

        # Detect compilations
        Compilation = 0

        if Item['AlbumArtist'].lower() in ("various artists", "various", "various items", "sountrack", "xvarious artistsx"):
            Compilation = 1
            xbmc.log(f"EMBY.core.musicalbum: Compilation detected: {Item['Name']}", 1) # LOGINFO

        if Item['KodiItemIds']:
            KodiItemIds = Item['KodiItemIds'].split(",")
        else:
            KodiItemIds = []

        if Item['LibraryIds']:
            LibraryIds = Item['LibraryIds'].split(",")
        else:
            LibraryIds= []

        # Update all existing Kodi Albums
        for Index, LibraryId in enumerate(LibraryIds):
            if int(Item['Id']) > 999999900: # Skip injected items updates
                return False

            self.SQLs["music"].common_db.delete_artwork(KodiItemIds[Index], "album")
            self.SQLs["music"].delete_link_album_artist(KodiItemIds[Index])
            self.SQLs["music"].update_album(KodiItemIds[Index], Item['Name'], AlbumType, Item['AlbumArtistsName'], Item['KodiProductionYear'], Item['KodiPremiereDate'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], 0, Item['KodiLastScraped'], Item['KodiDateCreated'], Item['ProviderIds']['MusicBrainzAlbum'], Item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, Item['Studio'], Item['KodiRunTimeTicks'], Item['AlbumArtistsSortName'])
            common.set_MusicArtist_links(KodiItemIds[Index], self.SQLs, Item["AlbumArtists"], LibraryId, None)
            self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemIds[Index], "album")
            utils.FavoriteQueue.put(((Item['KodiArtwork']['favourite'], isFavorite, f"musicdb://albums/{KodiItemIds[Index]}/", Item['Name'], "window", 10502),))
            xbmc.log(f"EMBY.core.musicalbum: UPDATE [{KodiItemIds[Index]}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO

        # New library (insert new Kodi record)
        if Item['LibraryId'] not in LibraryIds:
            xbmc.log(f"EMBY.core.musicalbum: AlbumId {Item['Id']} not found", 0) # LOGDEBUG
            KodiItemId = self.SQLs["music"].add_album(Item['Name'], AlbumType, Item['AlbumArtistsName'], Item['KodiProductionYear'], Item['KodiPremiereDate'], Item['MusicGenre'], Item['Overview'], Item['KodiArtwork']['thumb'], 0, Item['KodiLastScraped'], Item['KodiDateCreated'], Item['ProviderIds']['MusicBrainzAlbum'], Item['ProviderIds']['MusicBrainzReleaseGroup'], Compilation, Item['Studio'], Item['KodiRunTimeTicks'], Item['AlbumArtistsSortName'], Item['LibraryId'])
            LibraryIds.append(str(Item['LibraryId']))
            KodiItemIds.append(str(KodiItemId))
            self.SQLs["emby"].add_reference_musicalbum(Item['Id'], Item['LibraryId'], KodiItemIds, isFavorite, LibraryIds)
            xbmc.log(f"EMBY.core.musicalbum: ADD [{KodiItemId}] {Item['Name']}: {Item['Id']}", 1) # LOGINFO
            common.set_MusicArtist_links(KodiItemId, self.SQLs, Item["AlbumArtists"], Item['LibraryId'], None)
            self.SQLs["music"].common_db.add_artwork(Item['KodiArtwork'], KodiItemId, "album")
            utils.FavoriteQueue.put(((Item['KodiArtwork']['favourite'], isFavorite, f"musicdb://albums/{KodiItemId}/", Item['Name'], "window", 10502),))
        else:
            self.SQLs["emby"].update_reference_generic(isFavorite, Item['Id'], "MusicAlbum", Item['LibraryId'])

        return not Item['UpdateItem']

    def userdata(self, Item):
        Image, Itemname = self.SQLs["music"].get_FavoriteSubcontent(Item['KodiItemId'], "album")
        utils.FavoriteQueue.put(((Image, Item['IsFavorite'], f"musicdb://albums/{Item['KodiItemId']}/", Itemname, "window", 10502),))
        self.SQLs["emby"].update_favourite(Item['Id'], Item['IsFavorite'], "MusicAlbum")
        pluginmenu.reset_querycache("MusicAlbum")
        xbmc.log(f"EMBY.core.musicalbum: USERDATA {Item['Type']} [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        Image, Itemname = self.SQLs["music"].get_FavoriteSubcontent(Item['KodiItemId'], "album")
        self.SQLs["emby"].remove_item(Item['Id'], "MusicAlbum", Item['LibraryId'])
        utils.FavoriteQueue.put(((Image, False, f"musicdb://albums/{Item['KodiItemId']}/", Itemname, "window", 10502),))
        self.SQLs["music"].delete_album(Item['KodiItemId'], Item['LibraryId'])
        xbmc.log(f"EMBY.core.musicalbum: DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

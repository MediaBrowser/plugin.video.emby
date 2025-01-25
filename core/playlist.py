import xbmc
from helper import utils
from . import common

class Playlist:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Playlist"):
            return False

        IsFavorite = common.set_Favorite(Item)
        ImageUrl = common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])
        xbmc.log(f"EMBY.core.playlist: Process item: {Item['Name']}", 0) # DEBUG
        PlaylistItems = self.EmbyServer.API.get_Items(Item['Id'], ["Episode", "Movie", "Trailer", "MusicVideo", "Audio", "Video"], False, True, {}, "", False, None)
        ItemFilename = utils.valid_Filename(Item['Name'])
        M3UPlaylistAudio = ""
        M3UPlaylistVideo = ""
        KodiItemIdVideo = ""
        KodiItemIdAudio = ""

        for PlaylistItem in PlaylistItems:
            common.set_RunTimeTicks(PlaylistItem)
            common.set_streams(PlaylistItem)
            common.set_common(PlaylistItem, self.EmbyServer.ServerData['ServerId'], True)

            if PlaylistItem.get('Type', "") == "Audio":
                common.set_path_filename(PlaylistItem, self.EmbyServer.ServerData['ServerId'], None, True)
                M3UPlaylistAudio += f"#EXTINF:-1,{PlaylistItem['Name']}\n"
                M3UPlaylistAudio += f"{PlaylistItem['KodiFullPath']}\n"
            else:
                common.set_chapters(PlaylistItem, self.EmbyServer.ServerData['ServerId'])
                common.set_path_filename(PlaylistItem, self.EmbyServer.ServerData['ServerId'], None, True)
                M3UPlaylistVideo += f"#EXTINF:-1,{PlaylistItem['Name']}\n"
                M3UPlaylistVideo += f"{PlaylistItem['KodiFullPath']}\n"

        utils.delFile(f"{utils.PlaylistPathMusic}emby_{ItemFilename}_audio.m3u")
        utils.delFile(f"{utils.PlaylistPathVideo}emby_{ItemFilename}_video.m3u")

        if M3UPlaylistAudio:
            M3UPlaylistAudio = f"#EXTCPlayListM3U::M3U\n{M3UPlaylistAudio}"
            KodiItemIdAudio = f"emby_{ItemFilename}_audio"
            PlaylistPath = f"{utils.PlaylistPathMusic}{KodiItemIdAudio}.m3u"
            utils.writeFileBinary(PlaylistPath, M3UPlaylistAudio.encode("utf-8"))
            self.set_favorite(IsFavorite, KodiItemIdAudio, ImageUrl, Item['Id'], True)

        if M3UPlaylistVideo:
            M3UPlaylistVideo = f"#EXTCPlayListM3U::M3U\n{M3UPlaylistVideo}"
            KodiItemIdVideo = f"emby_{ItemFilename}_video"
            PlaylistPath = f"{utils.PlaylistPathVideo}{KodiItemIdVideo}.m3u"
            utils.writeFileBinary(PlaylistPath, M3UPlaylistVideo.encode("utf-8"))
            self.set_favorite(IsFavorite, KodiItemIdVideo, ImageUrl, Item['Id'], False)

        Item['KodiItemId'] = f"{KodiItemIdVideo};{KodiItemIdAudio}"
        self.SQLs["emby"].add_reference_playlist(Item['Id'], Item['LibraryId'], Item['KodiItemId'], IsFavorite, ImageUrl)
        xbmc.log(f"EMBY.core.playlist: ADD/REPLACE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG
        utils.reset_querycache("Playlist")
        return False

    def remove(self, Item, IncrementalSync):
        if self.SQLs["emby"].remove_item(Item['Id'], "PlayList", Item['LibraryId']):
            KodiItemIds = Item['KodiItemId'].split(";")

            if KodiItemIds[0]:
                self.set_favorite(False, KodiItemIds[0], "", Item['Id'], False)
                utils.delFile(f"{utils.PlaylistPathVideo}{KodiItemIds[0]}.m3u")

            if KodiItemIds[1]:
                self.set_favorite(False, KodiItemIds[1], "", Item['Id'], True)
                utils.delFile(f"{utils.PlaylistPathMusic}{KodiItemIds[1]}.m3u")

            xbmc.log(f"EMBY.core.playlist: DELETE [{Item['KodiItemId']}] {Item['Id']}", int(IncrementalSync)) # LOG

    def userdata(self, Item):
        ImageUrl = ""
        KodiItemIds = Item['KodiItemId'].split(";")

        if Item['IsFavorite']:
            ImageUrl = self.SQLs["emby"].get_item_by_id(Item['Id'], "Playlist")[3]

        if KodiItemIds[0]:
            self.set_favorite(Item['IsFavorite'], KodiItemIds[0], ImageUrl, Item['Id'], False)

        if KodiItemIds[1]:
            self.set_favorite(Item['IsFavorite'], KodiItemIds[1], ImageUrl, Item['Id'], True)

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Playlist")
        utils.reset_querycache("Playlist")
        xbmc.log(f"EMBY.core.playlist: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        return False

    def set_favorite(self, IsFavorite, KodiItemId, ImageUrl, EmbyItemId, isAudio):
        if isAudio:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Playlist", "Audio", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, f"{utils.PlaylistPathMusic}{KodiItemId}.m3u", KodiItemId, "window", 10502),))
        else:
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Playlist", "Video", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, f"{utils.PlaylistPathVideo}{KodiItemId}.m3u", KodiItemId, "window", 10025),))

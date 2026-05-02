import xbmc
from helper import utils
from . import common, audio, musicvideo, tag

PlaylistAudioFolder = "special://profile/library/music/emby_playlistsaudio_Playlists/"
PlaylistVideoFolder = "special://profile/library/video/emby_playlistsvideo_Playlists/"

class Playlist:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.AudioObject = audio.Audio(self.EmbyServer, self.SQLs)
        self.MusicVideoObject = musicvideo.MusicVideo(self.EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs
        self.TagObject.update_SQLs(self.SQLs)
        self.AudioObject.update_SQLs(self.SQLs)
        self.MusicVideoObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "Playlist"):
            return False

        common.set_Favorites_Artwork(Item, self.EmbyServer.ServerData['ServerId'])
        if utils.DebugLog: xbmc.log(f"EMBY.core.playlist (DEBUG): Process item: {Item['Name']}", 1) # DEBUG
        IconFile = utils.download_Icon(Item['Id'], Item['ImageTags'].get("Primary", "noimage"), self.EmbyServer.ServerData["ServerId"], Item['Name'], True) # Download image
        ItemFilename = utils.valid_Filename(Item['Name'])
        utils.delFile(f"{utils.PlaylistPathMusic}emby_{ItemFilename}_audio.m3u")
        utils.delFile(f"{utils.PlaylistPathVideo}emby_{ItemFilename}_video.m3u")
        utils.delFile(f"{PlaylistAudioFolder}{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml")
        utils.delFile(f"{PlaylistVideoFolder}{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml")
        TrackNumber = {"Audio": 0, "MusicVideo": 0}
        M3UPlaylist = {"Audio": "", "Video": ""}
        KodiPlaylistId = {"Audio": "", "Video": ""}
        EmbyRemoveIds = set()
        EmbyLinkedId = {"Audio": (), "Video": (), "Movie": (), "Episode": (), "MusicVideo": ()}
        PlaylistItems = self.EmbyServer.API.get_Items(Item['Id'], ("Audio", "Video", "Movie", "Episode", "MusicVideo"), False, {}, "", None, True)

        # Get previously links EmbyItemIds
        if Item['UpdateItem']:
            for Index in range(5):
                EmbyExistingIds = Item['EmbyLinkedId'].split(";")

                if EmbyExistingIds[Index]:
                    EmbyRemoveIds = EmbyRemoveIds.union(EmbyExistingIds[Index].split(","))

        for PlaylistItem in PlaylistItems:
            common.set_RunTimeTicks(PlaylistItem)
            common.set_streams(PlaylistItem)
            PlaylistItemType = PlaylistItem.get('Type', "")

            if not PlaylistItemType:
                continue

            EmbyLinkedId[PlaylistItemType] += (str(PlaylistItem['Id']),)

            if str(PlaylistItem['Id']) in EmbyRemoveIds:
                EmbyRemoveIds.remove(str(PlaylistItem['Id']))

            PlaylistItem['ParentIndexNumber'] = 0
            PlaylistItem['LibraryId'] = Item['LibraryId']
            common.set_common(PlaylistItem, self.EmbyServer.ServerData['ServerId'], True, IncrementalSync)

            if PlaylistItemType == "Audio":
                common.set_path_filename(PlaylistItem, self.EmbyServer.ServerData['ServerId'], None)
                TrackNumber["Audio"] += 1
                PlaylistItem['IndexNumber'] = TrackNumber["Audio"]
                self.AudioObject.change(PlaylistItem, IncrementalSync, Item['Id'])

                if "KodiItemIdNew" in PlaylistItem:
                    self.SQLs["music"].add_song_tag(PlaylistItem['KodiItemIdNew'], f"EmbyPlaylistId-{Item['Id']}")

                Node = (f"{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}", utils.encode_XML(Item['Name']), IconFile, "songs", (("comment", "contains", "LIBRARYTAG"),), ("ascending", "track"), False, False)
                View = {'ContentType': "playlistsaudio", "Tag": f"EmbyPlaylistId-{Item['Id']}", "Name": Item['Name']}
                self.EmbyServer.Views.set_synced_node(PlaylistAudioFolder, View, Node, Item['Id'], 0)
                M3UPlaylist["Audio"] += f"#EXTINF:-1,{PlaylistItem['Name']}\n"
                M3UPlaylist["Audio"] += f"{PlaylistItem['KodiFullPath']}\n"
            elif PlaylistItemType == "MusicVideo":
                TrackNumber["MusicVideo"] += 1
                PlaylistItem['IndexNumber'] = TrackNumber["MusicVideo"]
                PlaylistTag = {"LibraryId": PlaylistItem["LibraryId"], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}{Item['Id']}", "Name": Item['Name'], "Memo": "playlist", 'ImageTags': Item.get('ImageTags', [])}
                self.TagObject.change(PlaylistTag, False)
                self.MusicVideoObject.change(PlaylistItem, IncrementalSync, PlaylistTag)
                common.set_RunTimeTicks(PlaylistItem)
                common.set_streams(PlaylistItem)
                common.set_path_filename(PlaylistItem, self.EmbyServer.ServerData['ServerId'], None)
                Node = (f"{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}", utils.encode_XML(Item['Name']), IconFile, "musicvideos", (("tag", "is", Item['Name']),), ("ascending", "track"), False, False)
                View = {'ContentType': "playlistsvideo", "Tag": f"EmbyPlaylistId-{Item['Id']}", "Name": Item['Name']}
                self.EmbyServer.Views.set_synced_node(PlaylistVideoFolder, View, Node, Item['Id'], 0)
                M3UPlaylist["Video"] += f"#EXTINF:-1,{PlaylistItem['Name']}\n"
                M3UPlaylist["Video"] += f"{PlaylistItem['KodiFullPath']}\n"

        if M3UPlaylist["Audio"]:
            M3UData = f'#EXTCPlayListM3U::M3U\n{M3UPlaylist["Audio"]}'
            KodiPlaylistId["Audio"] = f"emby_{ItemFilename}_audio"
            utils.writeFile(f'{utils.PlaylistPathMusic}{KodiPlaylistId["Audio"]}.m3u', M3UData.encode("utf-8"))

        if M3UPlaylist["Video"]:
            M3UData = f'#EXTCPlayListM3U::M3U\n{M3UPlaylist["Video"]}'
            KodiPlaylistId["Video"] = f"emby_{ItemFilename}_video"
            utils.writeFile(f'{utils.PlaylistPathVideo}{KodiPlaylistId["Video"]}.m3u', M3UData.encode("utf-8"))

        EmbyLinkedId["Audio"] = ",".join(EmbyLinkedId["Audio"])
        EmbyLinkedId["Video"] = ",".join(EmbyLinkedId["Video"])
        EmbyLinkedId["Movie"] = ",".join(EmbyLinkedId["Movie"])
        EmbyLinkedId["Episode"] = ",".join(EmbyLinkedId["Episode"])
        EmbyLinkedId["MusicVideo"] = ",".join(EmbyLinkedId["MusicVideo"])
        Item['KodiItemId'] = f'{KodiPlaylistId["Audio"]};{KodiPlaylistId["Video"]}'
        Item['EmbyLinkedId'] = f'{EmbyLinkedId["Audio"]};{EmbyLinkedId["Video"]};{EmbyLinkedId["Movie"]};{EmbyLinkedId["Episode"]};{EmbyLinkedId["MusicVideo"]}'
        self.SQLs["emby"].add_reference_playlist(Item['Id'], Item['LibraryId'], Item['KodiItemId'], Item['KodiArtwork']['favourite'], Item['EmbyLinkedId'], Item['Name'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.playlist: ADD/REPLACE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.playlist (DEBUG): ADD/REPLACE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        if EmbyRemoveIds:
            for EmbyRemoveId in EmbyRemoveIds:
                self.SQLs["emby"].add_RemoveItem(EmbyRemoveId, Item['LibraryId'])

        return False

    def remove(self, Item, IncrementalSync):
        if not common.verify_KodiIds(Item, IncrementalSync, False):
            return

        self.set_favorite(False, Item)
        KodiItemIds = Item['KodiItemId'].split(";")

        if KodiItemIds[0]: # Audio
            utils.delFile(f"{PlaylistAudioFolder}{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml")
            utils.delFile(f"{utils.PlaylistPathMusic}{KodiItemIds[0]}.m3u")

        if KodiItemIds[1]: # Video
            utils.delFile(f"{PlaylistVideoFolder}{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml")
            utils.delFile(f"{utils.PlaylistPathVideo}{KodiItemIds[1]}.m3u")
            TagId = f"{utils.MappingIds['Tag']}{Item['Id']}"
            TagKodiId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(TagId, "Tag")
            self.TagObject.remove({'Id': TagId, 'KodiItemId': TagKodiId, "LibraryId": Item['LibraryId']}, IncrementalSync)

        self.SQLs["emby"].remove_item(Item['Id'], "Playlist", Item['LibraryId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.playlist: DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.playlist (DEBUG): DELETE [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        common.set_Favorite(Item)

        if UpdateKodiFavorite:
            self.set_favorite(Item['IsFavorite'], Item)

        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "Playlist")

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.playlist: USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.playlist (DEBUG): USERDATA [{Item['KodiItemId']}] {Item['Id']}", 1) # LOGDEBUG

        return False

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)
        KodiItemIds = Item['KodiItemId'].split(";")
        EmbyLinkedIds = Item['EmbyLinkedId'].split(";")

        if IsFavorite and not Item['KodiArtwork']['favourite']:
            Item['KodiArtwork']['favourite'] = self.SQLs["emby"].get_item_by_id(Item['Id'], "Playlist")[3]

        if EmbyLinkedIds[0]: # Audio
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Playlist", "Audio", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"library://music/emby_playlistsaudio_Playlists/{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml/", Item['Name'].replace('"', "'"), "window", 10502),))

        if EmbyLinkedIds[4]: # Musicvideo
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Playlist", "Video", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"library://video/emby_playlistsvideo_Playlists/{self.EmbyServer.ServerData['ServerId']}_{Item['Id']}.xml/", Item['Name'].replace('"', "'"), "window", 10025),))

        if EmbyLinkedIds[1] or EmbyLinkedIds[2] or EmbyLinkedIds[3]: # Mixed videos
            PlaylistName = KodiItemIds[1].replace("emby_", "").replace("_video", "", 1).replace("_", " ")
            utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Playlist", "Video", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, f"plugin://plugin.service.emby-next-gen/?mode=playlist&mediatype=video&server={self.EmbyServer.ServerData['ServerId']}&id={KodiItemIds[1]}", PlaylistName, "window", 10025),))

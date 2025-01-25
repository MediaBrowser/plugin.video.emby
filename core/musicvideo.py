import xbmc
from helper import utils
from . import common, musicgenre, tag, studio, person, musicartist, boxsets


class MusicVideo:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)
        self.MusicArtistObject = musicartist.MusicArtist(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)
        self.BoxSetObject = boxsets.BoxSets(EmbyServer, self.SQLs)

    def change(self, Item, IncrementalSync):
        if not common.verify_content(Item, "musicvideo"):
            return False

        xbmc.log(f"EMBY.core.musicvideo: Process item: {Item['Name']}", 0) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicVideo"):
            return False

        common.swap_mediasources(Item)
        common.set_MusicVideoTracks(Item)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False)
        Item['TagItems'].append({"LibraryId": Item["LibraryId"], "Type": "Tag", "Id": f"999999993{Item['LibraryId']}", "Name": Item['LibraryName'], "Memo": "library"})
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", 'ArtistItems', Item['LibraryId'], 0, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', None, 0, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag",'TagItems', None, -1, IncrementalSync)
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio",'Studios', None, -1, IncrementalSync)
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])
        Item['Album'] = Item.get('Album', "--NO INFO--")

        if Item['UpdateItem']:
            common.delete_ContentItemReferences(Item, self.SQLs, "musicvideo")
            common.update_downloaded_info(Item, self.SQLs)
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
        else:
            #Item['KodiPathId'] = self.SQLs["video"].get_add_path(Item['KodiPath'], "musicvideos")
            Item['KodiItemId'] = self.SQLs["video"].create_entry_musicvideos()
            Item['KodiFileId'] = self.SQLs["video"].create_entry_file()
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            Item['KodiPathId'] = self.SQLs["video"].get_add_path(Item['KodiPath'], "musicvideos")

        common.set_VideoCommon(Item, self.SQLs, "musicvideo")
        common.set_MusicGenre_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["GenreItems"], 0)
        common.set_Studio_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["Studios"])
        common.set_Tag_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["TagItems"])
        common.set_Writer_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["WritersItems"])
        common.set_Director_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["DirectorsItems"])
        common.set_Actor_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["CastItems"])
        common.set_Actor_MusicArtist_links(Item['KodiItemId'], self.SQLs, "musicvideo", Item["ArtistItems"], Item['LibraryId'])
        self.SQLs["video"].add_uniqueids(Item['KodiItemId'], Item['ProviderIds'], "musicvideo", 'imvdb')
        self.SQLs["video"].add_ratings(Item['KodiItemId'], "musicvideo", "default", Item['CommunityRating'])
        self.SQLs["video"].set_Favorite_Tag(Item['UserData']['IsFavorite'], Item['KodiItemId'], "musicvideo")

        if Item['UpdateItem']:
            self.SQLs["video"].update_musicvideos(Item['KodiItemId'], Item['KodiFileId'], Item['KodiName'], Item['KodiArtwork']['poster'], Item['KodiRunTimeTicks'], Item['Directors'], Item['Studio'], Item['Overview'], Item['Album'], Item['MusicArtist'], Item['MusicGenre'], Item['IndexNumber'], Item['KodiPremiereDate'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiFilename'], Item['KodiStackedFilename'], Item['KodiDateCreated'], Item['KodiPathId'], Item['KodiPath'])
            self.SQLs["emby"].update_reference_movie_musicvideo(Item['Id'], "MusicVideo", Item['UserData']['IsFavorite'], Item['PresentationUniqueKey'], Item['LibraryId'])
            xbmc.log(f"EMBY.core.musicvideo: UPDATE [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_update", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "musicvideo"}, IncrementalSync)
        else:
            self.SQLs["video"].add_musicvideos(Item['KodiItemId'], Item['KodiFileId'], Item['Name'], Item['KodiArtwork']['poster'], Item['KodiRunTimeTicks'], Item['Directors'], Item['Studio'], Item['Overview'], Item['Album'], Item['MusicArtist'], Item['MusicGenre'], Item['IndexNumber'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['KodiPathId'], Item['KodiPremiereDate'], Item['KodiDateCreated'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiFilename'], Item['KodiStackedFilename'])
            self.SQLs["emby"].add_reference_movie_musicvideo(Item['Id'], Item['LibraryId'], "Musicvideo", Item['KodiItemId'], Item['UserData']['IsFavorite'], Item['KodiFileId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.musicvideo: ADD [{Item['KodiPathId']} / {Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}: {Item['Name']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_add", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "musicvideo"}, IncrementalSync)

        common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
        self.SQLs["emby"].add_multiversion(Item, "MusicVideo", self.EmbyServer.API, self.SQLs, self.EmbyServer.ServerData['ServerId'])
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Musicvideo", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), Item['UserData']['IsFavorite'], f"{Item['KodiPath']}{Item['KodiFilename']}", Item['Name'], "media", 0),))
        return not Item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
        Update = self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicVideo")
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'], Item['Id'])
        utils.reset_querycache("MusicVideo")
        xbmc.log(f"EMBY.core.musicvideo: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']} / {Item['KodiPlaybackPositionTicks']}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.core.musicvideo: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO
        utils.notify_event("content_changed", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "musicvideo"}, True)
        return Update

    def remove(self, Item, IncrementalSync):
        self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'], Item['Id'])

        if common.delete_ContentItem(Item, self.SQLs, "musicvideo", "MusicVideo"):
            self.SQLs["video"].delete_musicvideos(Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'])
            xbmc.log(f"EMBY.core.musicvideo: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", int(IncrementalSync)) # LOG
            utils.notify_event("content_remove", {"EmbyId": f"{Item['Id']}", "KodiId": f"{Item['KodiItemId']}", "KodiType": "musicvideo"}, IncrementalSync)

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "MusicVideo")
        else:
            LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "musicvideo", LibrarySyncedName)

    def set_favorite(self, IsFavorite, KodiFileId, KodiItemId, EmbyItemId):
        FullPath, ImageUrl, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "musicvideo")
        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Musicvideo", "Musicvideos", EmbyItemId, self.EmbyServer.ServerData['ServerId'], ImageUrl), IsFavorite, FullPath, Itemname, "media", 0),))

import xbmc
from helper import pluginmenu, utils
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

    def change(self, item):
        if not common.verify_content(item, "musicvideo"):
            return False

        xbmc.log(f"EMBY.core.musicvideo: Process item: {item['Name']}", 0) # DEBUG
        common.load_ExistingItem(item, self.EmbyServer, self.SQLs["emby"], "MusicVideo")
        common.SwopMediaSources(item)  # 3D
        common.set_MusicVideoTracks(item)
        common.set_RunTimeTicks(item)
        common.get_streams(item)
        common.set_common(item, self.EmbyServer.ServerData['ServerId'], False)
        item['TagItems'].append({"LibraryId": item["LibraryId"], "Type": "Tag", "Id": f"999999993{item['LibraryId']}", "Name": item['LibraryName'], "Memo": "library"})
        common.set_chapters(item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", 'ArtistItems', item['LibraryId'], 0)
        common.set_MetaItems(item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', None, 0)
        common.set_MetaItems(item, self.SQLs, self.TagObject, self.EmbyServer, "Tag",'TagItems')
        common.set_MetaItems(item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio",'Studios')
        common.set_people(item, self.SQLs, self.PersonObject, self.EmbyServer)
        common.get_path(item, self.EmbyServer.ServerData['ServerId'])
        self.SQLs["emby"].add_streamdata(item['Id'], item['Streams'])
        item['Album'] = item.get('Album', None)

        if item['UpdateItem']:
            common.delete_ContentItemReferences(item, self.SQLs, "musicvideo")
            common.update_downloaded_info(item, self.SQLs)
        else:
            item['KodiPathId'] = self.SQLs["video"].get_add_path(item['KodiPath'], "musicvideos")
            item['KodiItemId'] = self.SQLs["video"].create_entry_musicvideos()
            item['KodiFileId'] = self.SQLs["video"].create_entry_file()

        self.SQLs["video"].set_Favorite_Tag(item['UserData']['IsFavorite'], item['KodiItemId'], "musicvideo")
        common.set_VideoCommon(item, self.SQLs, "musicvideo", self.EmbyServer.API)
        common.set_MusicGenre_links(item['KodiItemId'], self.SQLs, "musicvideo", item["GenreItems"], 0)
        common.set_Studio_links(item['KodiItemId'], self.SQLs, "musicvideo", item["Studios"])
        common.set_Tag_links(item['KodiItemId'], self.SQLs, "musicvideo", item["TagItems"])
        common.set_Writer_links(item['KodiItemId'], self.SQLs, "musicvideo", item["WritersItems"])
        common.set_Director_links(item['KodiItemId'], self.SQLs, "musicvideo", item["DirectorsItems"])
        common.set_Actor_MusicArtist_links(item['KodiItemId'], self.SQLs, "musicvideo", item["ArtistItems"], item['LibraryId'])

        if item['UpdateItem']:
            self.SQLs["video"].update_musicvideos(item['KodiItemId'], item['KodiFileId'], item['KodiName'], item['KodiArtwork']['poster'], item['KodiRunTimeTicks'], item['Directors'], item['Studio'], item['Overview'], item['Album'], item['MusicArtist'], item['MusicGenre'], item['IndexNumber'], item['KodiPremiereDate'], item['KodiPlayCount'], item['KodiLastPlayedDate'], item['KodiFilename'], item['KodiStackedFilename'])
            self.SQLs["emby"].update_reference_movie_musicvideo(item['Id'], "MusicVideo", item['UserData']['IsFavorite'], item['PresentationUniqueKey'], item['LibraryId'])

            # Update Boxset
            for BoxSet in self.EmbyServer.API.get_Items(item['ParentId'], ["BoxSet"], True, True, {'GroupItemsIntoCollections': True}):
                BoxSet['LibraryId'] = item['LibraryId']
                self.BoxSetObject.change(BoxSet)

            xbmc.log(f"EMBY.core.musicvideo: UPDATE [{item['KodiPathId']} / {item['KodiFileId']} / {item['KodiItemId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO
        else:
            self.SQLs["video"].add_musicvideos(item['KodiItemId'], item['KodiFileId'], item['Name'], item['KodiArtwork']['poster'], item['KodiRunTimeTicks'], item['Directors'], item['Studio'], item['Overview'], item['Album'], item['MusicArtist'], item['MusicGenre'], item['IndexNumber'], f"{item['KodiPath']}{item['KodiFilename']}", item['KodiPathId'], item['KodiPremiereDate'], item['KodiDateCreated'], item['KodiPlayCount'], item['KodiLastPlayedDate'], item['KodiFilename'], item['KodiStackedFilename'])
            self.SQLs["emby"].add_reference_movie_musicvideo(item['Id'], item['LibraryId'], "Musicvideo", item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiFileId'], item['PresentationUniqueKey'], item['Path'], item['KodiPathId'])
            xbmc.log(f"EMBY.core.musicvideo: ADD [{item['KodiPathId']} / {item['KodiFileId']} / {item['KodiItemId']}] {item['Id']}: {item['Name']}", 1) # LOGINFO

        self.SQLs["emby"].add_multiversion(item, "MusicVideo", self.EmbyServer.API, self.SQLs)
        utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], item['UserData']['IsFavorite'], f"{item['KodiPath']}{item['KodiFilename']}", item['Name'], "media", 0),))
        return not item['UpdateItem']

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        common.set_playstate(Item)
        common.set_RunTimeTicks(Item)
        self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
        self.SQLs["video"].update_bookmark_playstate(Item['KodiFileId'], Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
        self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicVideo")
        self.set_favorite(Item['IsFavorite'], Item['KodiFileId'], Item['KodiItemId'])
        pluginmenu.reset_querycache("MusicVideo")
        xbmc.log(f"EMBY.core.musicvideo: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']} / {Item['KodiPlaybackPositionTicks']}", 0) # LOGDEBUG
        xbmc.log(f"EMBY.core.musicvideo: USERDATA [{Item['KodiFileId']} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        self.set_favorite(False, Item['KodiFileId'], Item['KodiItemId'])

        if common.delete_ContentItem(Item, self.SQLs, "musicvideo", "MusicVideo"):
            self.SQLs["video"].delete_musicvideos(Item['KodiItemId'], Item['KodiFileId'])
            xbmc.log(f"EMBY.core.musicvideo: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO

            if not Item['LibraryId']:
                common.update_multiversion(self.SQLs["emby"], Item, "MusicVideo")
        else:
            LibraryName, _ = self.EmbyServer.library.WhitelistUnique[Item['LibraryId']]
            self.SQLs["video"].delete_library_links_tags(Item['KodiItemId'], "musicvideo", LibraryName)

    def set_favorite(self, IsFavorite, KodiFileId, KodiItemId):
        FullPath, Image, Itemname = self.SQLs["video"].get_favoriteData(KodiFileId, KodiItemId, "musicvideo")
        utils.FavoriteQueue.put(((Image, IsFavorite, FullPath, Itemname, "media", 0),))

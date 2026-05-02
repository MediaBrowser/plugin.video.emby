import xbmc
from helper import utils
from . import common, musicgenre, tag, studio, person, musicartist, boxsets


class MusicVideo:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs.copy()
        self.SQLs['music'] = None
        self.MusicGenreObject = musicgenre.MusicGenre(EmbyServer, self.SQLs)
        self.MusicArtistObject = musicartist.MusicArtist(EmbyServer, self.SQLs)
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)
        self.StudioObject = studio.Studio(EmbyServer, self.SQLs)
        self.PersonObject = person.Person(EmbyServer, self.SQLs)
        self.BoxSetObject = boxsets.BoxSets(EmbyServer, self.SQLs)

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs.copy()
        self.SQLs['music'] = None
        self.MusicGenreObject.update_SQLs(self.SQLs)
        self.MusicArtistObject.update_SQLs(self.SQLs)
        self.TagObject.update_SQLs(self.SQLs)
        self.StudioObject.update_SQLs(self.SQLs)
        self.PersonObject.update_SQLs(self.SQLs)
        self.BoxSetObject.update_SQLs(self.SQLs)

    def change(self, Item, IncrementalSync, PlaylistTag=False):
        if not common.verify_content(Item, "musicvideo"):
            return False

        if utils.DebugLog: xbmc.log(f"EMBY.core.musicvideo (DEBUG): Process item: {Item['Name']}", 1) # DEBUG

        if not common.load_ExistingItem(Item, self.EmbyServer, self.SQLs["emby"], "MusicVideo"):
            return False

        common.swap_mediasources(Item)
        common.set_MusicVideoTracks(Item)
        common.set_RunTimeTicks(Item)
        common.set_streams(Item)
        common.set_common(Item, self.EmbyServer.ServerData['ServerId'], False, IncrementalSync)
        Item['Album'] = Item.get('Album', "--NO INFO--")

        # Load Arrays
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])
        KodiPathIds = common.get_Ids_SingleContent(Item['KodiPathId'])
        KodiFileIds = common.get_Ids_SingleContent(Item['KodiFileId'])

        for Index, LibraryId in enumerate(LibraryIds):
            UpdateItem = Item.copy()
            UpdateItem['LibraryId'] = LibraryId
            KodiItemIdCurrent = KodiItemIds[Index]
            KodiPathIdCurrent = KodiPathIds[Index]
            KodiFileIdCurrent = KodiFileIds[Index]
            EmbyMusicArtistIds, EmbyMusicGenreIds = self.set_metadata(UpdateItem, IncrementalSync)
            common.remove_old_EmbyMusicArtist(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicArtistIds, self.MusicArtistObject, IncrementalSync)
            common.remove_old_EmbyMusicGenre(self.SQLs["emby"], UpdateItem['Id'], UpdateItem['LibraryId'], EmbyMusicGenreIds, self.MusicGenreObject, IncrementalSync)
            common.delete_ContentItemReferences(KodiItemIdCurrent, KodiFileIdCurrent, UpdateItem.get('ExtraType', ""), self.SQLs, "musicvideo", False)
            common.set_path_filename(UpdateItem, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(UpdateItem, self.EmbyServer)
            common.update_downloaded_info(UpdateItem, self.SQLs, "musicvideo")
            self.assign_metadata(UpdateItem, KodiItemIdCurrent, KodiFileIdCurrent)
            self.SQLs["video"].update_musicvideos(KodiItemIdCurrent, KodiFileIdCurrent, UpdateItem['KodiName'], UpdateItem['KodiArtwork']['poster'], UpdateItem['KodiRunTimeTicks'], UpdateItem['Directors'], UpdateItem['Studio'], UpdateItem['Overview'], UpdateItem['Album'], UpdateItem['MusicArtist'], UpdateItem['MusicGenre'], UpdateItem['IndexNumber'], UpdateItem['KodiPremiereDate'], UpdateItem['KodiFilename'], UpdateItem['KodiStackedFilename'], UpdateItem['KodiDateCreated'], KodiPathIdCurrent, UpdateItem['KodiPath'], bool(PlaylistTag), UpdateItem['KodiFullPath'])
            self.SQLs["emby"].update_reference_musicvideo(UpdateItem['Id'], UpdateItem['PresentationUniqueKey'], UpdateItem['LibraryId'], EmbyMusicArtistIds, EmbyMusicGenreIds)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicvideo: UPDATE [{KodiPathIdCurrent} / {KodiFileIdCurrent} / {KodiItemIdCurrent}] {UpdateItem['Id']}: {UpdateItem['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicvideo (DEBUG): UPDATE [{KodiPathIdCurrent} / {KodiFileIdCurrent} / {KodiItemIdCurrent}] {UpdateItem['Id']}: {UpdateItem['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_update", {"EmbyId": UpdateItem['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "musicvideo"}, IncrementalSync)
            common.update_boxsets(IncrementalSync, UpdateItem['ParentId'], UpdateItem['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
            common.add_multiversion(UpdateItem, "MusicVideo", self.EmbyServer, self.SQLs, self.EmbyServer.ServerData['ServerId'], EmbyMusicArtistIds, EmbyMusicGenreIds)
            del UpdateItem

        # New library (insert new Kodi record)
        if Item['LibraryId'] not in LibraryIds:
            if PlaylistTag:
                Item['TagItems'].append(PlaylistTag)

            EmbyMusicArtistIds, EmbyMusicGenreIds = self.set_metadata(Item, IncrementalSync)
            KodiItemIdCurrent = self.SQLs["video"].create_entry_musicvideos()
            Item['KodiItemId'] = common.add_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
            KodiFileIdCurrent = self.SQLs["video"].create_entry_file()
            Item['KodiFileId'] = common.add_Ids_SingleContent(KodiFileIds, KodiFileIdCurrent)
            common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None)
            common.set_multipart(Item, self.EmbyServer)
            KodiPathIdCurrent = self.SQLs["video"].get_add_path(Item['KodiPath'], "musicvideos")
            Item['KodiPathId'] = common.add_Ids_SingleContent(KodiPathIds, KodiPathIdCurrent)
            Item['LibraryIds'] = common.add_Ids_SingleContent(LibraryIds, Item['LibraryId'])
            self.assign_metadata(Item, KodiItemIdCurrent, KodiFileIdCurrent)
            self.SQLs["video"].add_musicvideos(KodiItemIdCurrent, KodiFileIdCurrent, Item['Name'], Item['KodiArtwork']['poster'], Item['KodiRunTimeTicks'], Item['Directors'], Item['Studio'], Item['Overview'], Item['Album'], Item['MusicArtist'], Item['MusicGenre'], Item['IndexNumber'], Item['KodiFullPath'], KodiPathIdCurrent, Item['KodiPremiereDate'], Item['KodiDateCreated'], Item['KodiFilename'], Item['KodiStackedFilename'], bool(PlaylistTag))
            self.SQLs["emby"].add_reference_musicvideo(Item['Id'], Item['LibraryId'], KodiItemIds, KodiFileIds, Item['PresentationUniqueKey'], Item['Path'], KodiPathIds, Item['LibraryIds'], EmbyMusicArtistIds, EmbyMusicGenreIds)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicvideo: ADD [{KodiPathIdCurrent} / {KodiFileIdCurrent} / {KodiItemIdCurrent}] {Item['Id']}: {Item['Name']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicvideo (DEBUG): ADD [{KodiPathIdCurrent} / {KodiFileIdCurrent} / {KodiItemIdCurrent}] {Item['Id']}: {Item['Name']}", 1) # LOGDEBUG

            utils.notify_event("content_add", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "musicvideo"}, IncrementalSync)
            common.update_boxsets(IncrementalSync, Item['ParentId'], Item['LibraryId'], self.SQLs, self.EmbyServer) # Update Boxset
            common.add_multiversion(Item, "MusicVideo", self.EmbyServer, self.SQLs, self.EmbyServer.ServerData['ServerId'], EmbyMusicArtistIds, EmbyMusicGenreIds)

        return not Item['UpdateItem']

    def set_metadata(self, Item, IncrementalSync):
        LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
        Item['TagItems'].append({"LibraryId": Item['LibraryId'], "Type": "Tag", "Id": f"{utils.MappingIds['Tag']}00{Item['LibraryId']}", "Name": LibrarySyncedName, "Memo": "library"})
        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
        common.set_MetaItems(Item, self.SQLs, self.MusicArtistObject, self.EmbyServer, "MusicArtist", 'ArtistItems', "video", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.MusicGenreObject, self.EmbyServer, "MusicGenre", 'GenreItems', "video", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.TagObject, self.EmbyServer, "Tag", 'TagItems', "", IncrementalSync, Item['LibraryId'])
        common.set_MetaItems(Item, self.SQLs, self.StudioObject, self.EmbyServer, "Studio", 'Studios', "", IncrementalSync, Item['LibraryId'])
        EmbyMusicArtistIds = common.get_Artist_Ids(Item, True, True, True)
        EmbyMusicGenreIds = common.get_MusicGenre_Ids(Item)
        common.set_people(Item, self.SQLs, self.PersonObject, self.EmbyServer, IncrementalSync)
        self.SQLs["emby"].add_streamdata(Item['Id'], Item['MediaSources'])
        return EmbyMusicArtistIds, EmbyMusicGenreIds

    def assign_metadata(self, Item, KodiItemIdCurrent, KodiFileIdCurrent):
        common.set_VideoCommon(KodiItemIdCurrent, KodiFileIdCurrent, Item, self.SQLs, "musicvideo")
        common.set_MusicGenre_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["GenreItems"], 1)
        common.set_Studio_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["Studios"])
        common.set_Tag_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["TagItems"])
        common.set_Writer_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["WritersItems"])
        common.set_Director_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["DirectorsItems"])
        common.set_Actor_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["CastItems"])
        common.set_Actor_MusicArtist_links(KodiItemIdCurrent, self.SQLs, "musicvideo", Item["ArtistItems"], Item['LibraryId'])
        self.SQLs["video"].add_uniqueids(KodiItemIdCurrent, Item['ProviderIds'], "musicvideo", 'imvdb')
        self.SQLs["video"].add_ratings(KodiItemIdCurrent, "musicvideo", "default", Item['CommunityRating'])

    def userdata(self, Item, IncrementalSync, UpdateKodiFavorite):
        if not common.verify_KodiIds(Item, IncrementalSync, True):
            return False

        common.set_Favorite(Item)
        Update = False
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])
        KodiFileIds = common.get_Ids_SingleContent(Item['KodiFileId'])

        for Index, KodiItemIdCurrent in enumerate(KodiItemIds):
            KodiFileIdCurrent = KodiFileIds[Index]
            common.set_playstate(Item)
            common.set_RunTimeTicks(Item)
            self.SQLs["video"].set_Favorite_Tag(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
            Update = self.SQLs["video"].update_bookmark_playstate(KodiFileIdCurrent, Item['KodiPlayCount'], Item['KodiLastPlayedDate'], Item['KodiPlaybackPositionTicks'], Item['KodiRunTimeTicks'])
            self.SQLs["emby"].update_favourite(Item['IsFavorite'], Item['Id'], "MusicVideo")

            if UpdateKodiFavorite:
                self.set_favorite(Item['IsFavorite'], Item)

            if int(IncrementalSync):
                xbmc.log(f"EMBY.core.musicvideo: USERDATA [{KodiFileIdCurrent} / {KodiItemIdCurrent}] {Item['Id']}", 1) # LOGINFO
            elif utils.DebugLog:
                xbmc.log(f"EMBY.core.musicvideo (DEBUG): USERDATA [{KodiFileIdCurrent} / {KodiItemIdCurrent}] {Item['Id']}", 1) # LOGDEBUG

            utils.notify_event("content_changed", {"EmbyId": Item['Id'], "KodiId": Item['KodiItemId'], "KodiType": "musicvideo"}, True)

        return Update

    def remove(self, Item, IncrementalSync):
        LibraryIdsRemove = ()
        self.set_favorite(False, Item)
        LibraryIdStr = str(Item['LibraryId'])
        Item['LibraryIds'], Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'] = self.SQLs["emby"].get_KodiIds_LibraryIds_from_ContentItem(Item['Id'], "MusicVideo") # (Re)Load LibraryIds, KodiItemId as references could be modify data after collecting

        if not Item['LibraryIds']:
            if utils.DebugLog: xbmc.log(f"EMBY.core.musicvideo (DEBUG): SKIP DELETE, LibraryIds not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
            return

        # Load Arrays
        LibraryIds = common.get_Ids_SingleContent(Item['LibraryIds'])
        KodiItemIds = common.get_Ids_SingleContent(Item['KodiItemId'])
        KodiPathIds = common.get_Ids_SingleContent(Item['KodiPathId'])
        KodiFileIds = common.get_Ids_SingleContent(Item['KodiFileId'])

        if LibraryIdStr not in LibraryIds:
            if not LibraryIdStr: # Realtime remove
                LibraryIdsRemove = LibraryIds
            else: # Select all items if a playlist library was removed (playlist libraryids syntax: LibraryId_PlaylistId)
                for EmbyLibraryId in LibraryIds:
                    if EmbyLibraryId.startswith(f"{LibraryIdStr}_"):
                        LibraryIdsRemove += (EmbyLibraryId,)
        else:
            LibraryIdsRemove = (LibraryIdStr,)

        for Item['LibraryId'] in LibraryIdsRemove:
            Item['LibraryId'] = str(Item['LibraryId'])

            if Item['LibraryId'] not in LibraryIds:
                if utils.DebugLog: xbmc.log(f"EMBY.core.musicvideo (DEBUG): SKIP DELETE, LibraryId not found {Item['Id']} / {Item['LibraryId']}", 1) # DEBUGLOG
                continue

            Links = self.SQLs['emby'].get_Links(Item['Id'], Item['LibraryId'])
            Deleted = self.SQLs["emby"].remove_item(Item['Id'], "MusicVideo", Item['LibraryId'])
            common.delete_MusicArtist_Links(Item['LibraryId'], Links, self.MusicArtistObject, IncrementalSync, self.SQLs["emby"])
            common.delete_MusicGenre_Links(Item['LibraryId'], Links, self.MusicGenreObject, IncrementalSync, self.SQLs["emby"])
            Index = LibraryIds.index(Item['LibraryId'])

            if KodiItemIds:
                KodiItemIdCurrent = KodiItemIds[Index]
                KodiFileIdCurrent = KodiFileIds[Index]
                KodiPathIdCurrent = KodiPathIds[Index]
                Item['KodiItemId'] = common.del_Ids_SingleContent(KodiItemIds, KodiItemIdCurrent)
                Item['KodiFileId'] = common.del_Ids_SingleContent(KodiFileIds, KodiFileIdCurrent)
                Item['KodiPathId'] = common.del_Ids_SingleContent(KodiPathIds, KodiPathIdCurrent)
                common.delete_ContentItemReferences(KodiItemIdCurrent, KodiFileIdCurrent, Item.get('ExtraType', ""), self.SQLs, "musicvideo", False)
            else:
                KodiItemIdCurrent = None
                KodiFileIdCurrent = None

            self.SQLs["video"].delete_musicvideos(KodiItemIdCurrent, KodiFileIdCurrent)
            common.update_multiversion(self.SQLs["emby"], "MusicVideo", Item['Id'], Item['LibraryId'], Item.get('PresentationUniqueKey', ''))

            if not Deleted:
                Item['LibraryIds'] = common.del_Ids_SingleContent(LibraryIds, Item['LibraryId'])
                self.SQLs["emby"].update_deleted_musicvideo(Item['Id'], Item['KodiItemId'], Item['KodiFileId'], Item['KodiPathId'], Item['LibraryIds'])
                LibrarySyncedName = self.EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]
                self.SQLs["video"].delete_library_links_tags(KodiItemIdCurrent, "musicvideo", LibrarySyncedName)

                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.musicvideo: DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.musicvideo (DEBUG): DELETE PARTIAL [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG
            else:
                if int(IncrementalSync):
                    xbmc.log(f"EMBY.core.musicvideo: DELETE [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGINFO
                elif utils.DebugLog:
                    xbmc.log(f"EMBY.core.musicvideo (DEBUG): DELETE [{KodiItemIdCurrent}] {Item['Id']} / {Item['LibraryId']}", 1) # LOGDEBUG

            utils.notify_event("content_remove", {"EmbyId": Item['Id'], "KodiId": KodiItemIdCurrent, "KodiType": "musicvideo"}, IncrementalSync)

    def set_favorite(self, IsFavorite, Item):
        common.validate_FavoriteImage(Item)

        if IsFavorite and not Item['KodiArtwork']['favourite'] or "KodiFullPath" not in Item:
            Item['KodiFullPath'], Item['KodiArtwork']['favourite'], Item['Name'] = self.SQLs["video"].get_favoriteData(Item['KodiFileId'], Item['KodiItemId'], "musicvideo")

        utils.FavoriteQueue.put(((common.set_Favorites_Artwork_Overlay("Musicvideo", "Musicvideos", Item['Id'], self.EmbyServer.ServerData['ServerId'], Item['KodiArtwork']['favourite']), IsFavorite, Item['KodiFullPath'], Item['Name'].replace('"', "'"), "media", 0),))

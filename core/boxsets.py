import xbmc
from helper import pluginmenu, utils
from . import common, tag

KodiTypeMapping = {"Movie": "movie", "Series": "tvshow", "MusicVideo": "musicvideo", "Video": "movie"}


class BoxSets:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs
        self.TagObject = tag.Tag(EmbyServer, self.SQLs)

    def change(self, item):
        common.load_ExistingItem(item, self.EmbyServer, self.SQLs["emby"], "BoxSet")
        BoxSetKodiParentIds = ()
        TagItems = []

        # Query assigned content for collections
        ContentsAssignedToBoxset = []

        for ContentAssignedToBoxset in self.EmbyServer.API.get_Items(item['Id'], ["All"], True, True, {'GroupItemsIntoCollections': False}):
            ContentsAssignedToBoxset.append(ContentAssignedToBoxset)

        # Add new collection tag
        if utils.BoxSetsToTags:
            TagItems = [{"LibraryId": item["LibraryId"], "Type": "Tag", "Id": f"999999993{item['Id']}", "Name": f"{item['Name']} (Collection)", "Memo": "collection"}]
            self.TagObject.change(TagItems[0])

        # Boxsets
        common.set_overview(item)

        if item['UpdateItem']:
            self.SQLs["video"].common_db.delete_artwork(item['KodiItemId'], "set")
            self.SQLs["video"].update_boxset(item['Name'], item['Overview'], item['KodiItemId'])
        else:
            xbmc.log(f"EMBY.core.boxsets: SetId {item['Id']} not found", 0) # LOGDEBUG
            item['KodiItemId'] = self.SQLs["video"].add_boxset(item['Name'], item['Overview'])

        if item['KodiParentId']:
            CurrentBoxSetContent = item['KodiParentId'].split(",")
        else:
            CurrentBoxSetContent = []

        for ContentAssignedToBoxset in ContentsAssignedToBoxset:
            if ContentAssignedToBoxset['Type'] not in ("Movie", "Series", "MusicVideo", "Video"): # Episode and season tags not supported by Kodi
                continue

            ContentAssignedToBoxset.update({'KodiItemId': item['KodiItemId']})
            ContentItemKodiId = self.SQLs["emby"].get_KodiId_by_EmbyId_EmbyType(ContentAssignedToBoxset['Id'], ContentAssignedToBoxset['Type'])

            if ContentAssignedToBoxset['Type'] in ("Movie", "Video") and ContentItemKodiId:
                if str(ContentItemKodiId) in CurrentBoxSetContent:
                    CurrentBoxSetContent.remove(str(ContentItemKodiId))

                xbmc.log(f"EMBY.core.boxsets: ADD to Kodi set [{item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGINFO
                self.SQLs["video"].set_boxset(item['KodiItemId'], ContentItemKodiId) # assign boxset to movie
                BoxSetKodiParentIds += (str(ContentItemKodiId),)

            # Assign content to collection tag
            if utils.BoxSetsToTags and ContentItemKodiId:
                common.set_Tag_links(ContentItemKodiId, self.SQLs, KodiTypeMapping[ContentAssignedToBoxset['Type']], TagItems)
                xbmc.log(f"EMBY.core.boxsets: ADD to tag [{item['KodiItemId']}] {ContentAssignedToBoxset['Name']}: {ContentAssignedToBoxset['Id']}", 1) # LOGINFO

        # Delete remove content from boxsets
        for KodiContentId in CurrentBoxSetContent:
            self.SQLs["video"].remove_from_boxset(KodiContentId)
            xbmc.log(f"EMBY.core.boxsets: DELETE from boxset [{item['Id']}] {item['KodiItemId']} {item['Name']}: {KodiContentId}", 1) # LOGINFO

        common.set_KodiArtwork(item, self.EmbyServer.ServerData['ServerId'], False)
        self.SQLs["video"].common_db.add_artwork(item['KodiArtwork'], item['KodiItemId'], "set")
        item['KodiParentId'] = ",".join(BoxSetKodiParentIds)
        utils.FavoriteQueue.put(((item['KodiArtwork']['favourite'], item['UserData']['IsFavorite'], f"videodb://movies/sets/{item['KodiItemId']}/", item['Name'], "window", 10025),))
        xbmc.log(f"EMBY.core.boxsets: UPDATE [{item['Id']}] {item['KodiItemId']} {item['Name']}", 1) # LOGINFO
        self.SQLs["emby"].add_reference_boxset(item['Id'], item['LibraryId'], item['KodiItemId'], item['UserData']['IsFavorite'], item['KodiParentId'])
        return True

    # This updates: Favorite, LastPlayedDate, PlaybackPositionTicks
    def userdata(self, Item):
        pluginmenu.reset_querycache("BoxSet")
        xbmc.log(f"EMBY.core.boxsets: USERDATA {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        KodiParentIds = self.SQLs["emby"].get_KodiParentIds(Item['Id'], "BoxSet")

        if self.SQLs["emby"].remove_item(Item['Id'], "BoxSet", Item['LibraryId']):
            self.SQLs["emby"].add_RemoveItem(f"999999993{Item['Id']}", Item['LibraryId'])

            for KodiParentId in KodiParentIds:
                self.SQLs["video"].remove_from_boxset(KodiParentId)

            self.SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], "set")
            self.SQLs["video"].delete_boxset(Item['KodiItemId'])

        xbmc.log(f"EMBY.core.boxsets: DELETE [{Item['KodiItemId']} / {Item['KodiFileId']}] {Item['Id']}", 1) # LOGINFO

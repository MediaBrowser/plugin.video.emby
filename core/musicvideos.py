import xbmc
from . import common


class MusicVideos:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.video_db.init_favorite_tags()

    def musicvideo(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db, "MusicVideo"):
            return False

        if not common.verify_content(item, "musicvideo"):
            return False

        xbmc.log(f"EMBY.core.musicvideos: Process item: {item['Name']}", 1) # LOGINFO
        ItemIndex = 0
        common.SwopMediaSources(item)  # 3D
        item['ArtistItems'] = item.get('ArtistItems', [])
        item['Album'] = item.get('Album', "--NO INFO--")
        item['Artist'] = " / ".join(item['Artists'])
        item['Settings'] = len(item['Librarys']) * [{}]
        common.set_MusicVideoTracks(item)

        for ItemIndex in range(len(item['Librarys'])):
            if item['KodiItemIds'][ItemIndex]: # existing item
                item['Settings'][ItemIndex] = self.video_db.get_settings(item['KodiFileIds'][ItemIndex])
                self.remove_musicvideo(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Id'], item['LibraryIds'][ItemIndex])

            if not common.get_file_path(item, "musicvideos", ItemIndex):
                continue

            for Artist in item['ArtistItems']:
                Artist['Type'] = "Actor"
                Artist['Role'] = "MusicVideoArtist"
                Artist['PrimaryImageTag'] = "0"

            for People in item['People']:
                if People['Type'] == "Actor":
                    People['Role'] = "MusicVideoArtist"
                    People['PrimaryImageTag'] = "0"

            if not item['Artist']:
                xbmc.log(f"EMBY.core.musicvideos: No artist found: {item['Name']} {item['FullPath']} {item['Id']}", 2) # LOGWARNING
                item['Artist'] = "--NO INFO--"
                item['ArtistItems'].append({'Name': '--NO INFO--', 'Type': "Actor", 'Role': "MusicVideoArtist", 'LibraryId': item['Librarys'][ItemIndex]['Id'], 'Id': "999999996"})

            item['People'] = item['People'] + item['ArtistItems']
            item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_musicvideos()
            item['KodiFileIds'][ItemIndex] = self.video_db.create_entry_file()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], "musicvideo")
            common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "musicvideo", ItemIndex)
            self.video_db.add_musicvideos(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Name'], item['KodiArtwork']['poster'], item['RunTimeTicks'], item['Directors'], item['Studio'], item['Overview'], item['Album'], item['Artist'], item['Genre'], item['IndexNumber'], f"{item['Path']}{item['Filename']}", item['KodiPathId'], item['PremiereDate'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['Filename'])
            self.emby_db.add_reference(item['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "MusicVideo", "musicvideo", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
            self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.add_genres_and_links(item['Genres'], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.add_tags_and_links(item['KodiItemIds'][ItemIndex], "musicvideo", item['TagItems'])
            self.emby_db.add_multiversion(item, "MusicVideo", self.EmbyServer.API, self.video_db, ItemIndex)

            if item['Settings'][ItemIndex]:
                self.video_db.add_settings(item['KodiFileIds'][ItemIndex], item['Settings'][ItemIndex])

        if item['UpdateItems'][ItemIndex]:
            xbmc.log(f"EMBY.core.musicvideos: UPDATE musicvideo [{item['KodiPathId']} / {item['KodiFileIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO
        else:
            xbmc.log(f"EMBY.core.musicvideos: ADD musicvideo [{item['KodiPathId']} / {item['KodiFileIds'][ItemIndex]} / {item['KodiItemIds'][ItemIndex]}] {item['Id']}: {item['Name']}", 1) # LOGINFO

        return not item['UpdateItems'][ItemIndex]

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        if Item['PlaybackPositionTicks'] and Item['PlayedPercentage']:
            RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
        else:
            RuntimeSeconds = 0

        common.set_playstate(Item)

        for ItemIndex in range(len(Item['Librarys'])):
            self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
            self.video_db.update_bookmark_playstate(Item['KodiFileIds'][ItemIndex], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
            self.emby_db.update_favourite(Item['IsFavorite'], Item['Id'])
            xbmc.log(f"EMBY.core.musicvideos: New resume point {Item['Id']}: {Item['PlaybackPositionTicks']}", 0) # LOGDEBUG
            xbmc.log(f"EMBY.core.musicvideos: USERDATA musicvideo [{Item['KodiFileIds'][ItemIndex]} / {Item['KodiItemId']}] {Item['Id']}", 1) # LOGINFO

    def remove(self, Item):
        self.remove_musicvideo(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])

        if not Item['DeleteByLibraryId']:
            StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "MusicVideo")

            if StackedIds: # multi version
                xbmc.log(f"EMBY.core.musicvideos: DELETE multi version musicvideos from embydb {Item['Id']}", 1) # LOGINFO

                for StackedId in StackedIds:
                    StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['MusicVideo'], False, False)

                    if StackedItem:
                        StackedItem['Library'] = Item['Library']
                        xbmc.log(f"EMBY.core.musicvideos: UPDATE remaining multi version musicvideo {StackedItem['Id']}", 1) # LOGINFO
                        self.musicvideo(StackedItem)  # update all remaining multiversion items
                    else:
                        self.emby_db.remove_item(StackedId[0], Item['Library']['Id'])

    def remove_musicvideo(self, KodiItemId, KodiFileId, EmbyItemId, EmbyLibraryId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "musicvideo", EmbyLibraryId)
        self.video_db.delete_musicvideos(KodiItemId, KodiFileId)
        xbmc.log(f"EMBY.core.musicvideos: DELETE musicvideo [{KodiItemId} / {KodiFileId}] {EmbyItemId}", 1) # LOGINFO

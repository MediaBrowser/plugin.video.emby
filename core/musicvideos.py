from helper import loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.musicvideos')


class MusicVideos:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb
        self.video_db.init_favorite_tags()

    def musicvideo(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        LOG.info("Process item: %s" % item['Name'])
        ItemIndex = 0
        common.SwopMediaSources(item)  # 3D
        item['ArtistItems'] = item.get('ArtistItems', [])
        item['Album'] = item.get('Album', "--NO INFO--")
        item['Artist'] = " / ".join(item['Artists'])
        common.set_MusicVideoTracks(item)

        for ItemIndex in range(len(item['Librarys'])):
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
                LOG.warning("No artist found: %s %s %s " % (item['Name'], item['FullPath'], item['Id']))
                item['Artist'] = "--NO INFO--"
                item['ArtistItems'].append({'Name': '--NO INFO--', 'Type': "Actor", 'Role': "MusicVideoArtist", 'LibraryId': item['Librarys'][ItemIndex]['Id']})

            item['People'] = item['People'] + item['ArtistItems']

            if not item['UpdateItems'][ItemIndex]:
                LOG.debug("MusicVideoId for %s not found" % item['Id'])
                item['KodiItemIds'][ItemIndex] = self.video_db.create_entry_musicvideos()
                item['KodiFileIds'][ItemIndex] = self.video_db.create_entry_file()
                item['KodiPathId'] = self.video_db.get_add_path(item['Path'], "musicvideo")
            else:
                self.video_db.delete_links_genres(item['KodiItemIds'][ItemIndex], "musicvideo")
                common.delete_ContentItemReferences(item['Id'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], self.video_db, self.emby_db, "musicvideo")

            common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "musicvideo", "M", ItemIndex)

            if item['UpdateItems'][ItemIndex]:
                self.video_db.update_musicvideos(item['Name'], item['KodiArtwork']['poster'], item['RunTimeTicks'], item['Directors'], item['Studio'], item['Overview'], item['Album'], item['Artist'], item['Genre'], item['IndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['PremiereDate'], item['KodiItemIds'][ItemIndex], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['KodiFileIds'][ItemIndex], item['Filename'])
                self.emby_db.update_favourite(item['UserData']['IsFavorite'], item['Id'])
                LOG.info("UPDATE musicvideo [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))
            else:
                self.video_db.add_musicvideos(item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], item['Name'], item['KodiArtwork']['poster'], item['RunTimeTicks'], item['Directors'], item['Studio'], item['Overview'], item['Album'], item['Artist'], item['Genre'], item['IndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['PremiereDate'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['Filename'])
                item['KodiItemIds'][ItemIndex] = item['KodiItemIds'][ItemIndex]
                item['KodiFileIds'][ItemIndex] = item['KodiFileIds'][ItemIndex]
                self.emby_db.add_reference(item['Id'], item['KodiItemIds'], item['KodiFileIds'], item['KodiPathId'], "MusicVideo", "musicvideo", [], item['LibraryIds'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['EmbyPath'], None, None, None)
                LOG.info("ADD musicvideo [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileIds'][ItemIndex], item['KodiItemIds'][ItemIndex], item['Id'], item['Name']))

            self.video_db.add_link_tag(common.MediaTags[item['Librarys'][ItemIndex]['Name']], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.add_genres_and_links(item['Genres'], item['KodiItemIds'][ItemIndex], "musicvideo")
            self.video_db.add_tags_and_links(item['KodiItemIds'][ItemIndex], "musicvideo", item['TagItems'])
            self.emby_db.add_multiversion(item, "MusicVideo", self.EmbyServer.API, self.video_db, item['UpdateItems'][ItemIndex])

        return not item['UpdateItems'][ItemIndex]

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        Item['Library'] = {}

        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return

        if Item['PlaybackPositionTicks'] and Item['PlayedPercentage']:
            RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
        else:
            RuntimeSeconds = 0

        common.set_userdata_update_data(Item)

        for ItemIndex in range(len(Item['Librarys'])):
            self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
            self.video_db.update_bookmark_playstate(Item['KodiFileIds'][ItemIndex], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
            self.emby_db.update_favourite(Item['IsFavorite'], Item['Id'])
            LOG.debug("New resume point %s: %s" % (Item['Id'], Item['PlaybackPositionTicks']))
            LOG.info("USERDATA musicvideo [%s/%s] %s" % (Item['KodiFileIds'][ItemIndex], Item['KodiItemId'], Item['Id']))

    def remove(self, Item):
        self.remove_musicvideo(Item['KodiItemId'], Item['KodiFileId'], Item['Id'], Item['Library']['Id'])

        if not Item['DeleteByLibraryId']:
            StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "MusicVideo")

            if StackedIds: # multi version
                LOG.info("DELETE multi version musicvideos from embydb %s" % Item['Id'])

                for StackedId in StackedIds:
                    self.emby_db.remove_item(StackedId[0], Item['Library']['Id'])

                for StackedId in StackedIds:
                    StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['MusicVideo'], False, False)

                    if StackedItem:
                        StackedItem['Library'] = Item['Library']
                        LOG.info("UPDATE remaining multi version musicvideo %s" % StackedItem['Id'])
                        self.musicvideo(StackedItem)  # update all stacked items

    def remove_musicvideo(self, KodiItemId, KodiFileId, EmbyItemId, EmbyLibraryId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "musicvideo", EmbyLibraryId)
        self.video_db.delete_musicvideos(KodiItemId, KodiFileId)
        LOG.info("DELETE musicvideo [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

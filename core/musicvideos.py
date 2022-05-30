from helper import loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.musicvideos')


class MusicVideos:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb

    def musicvideo(self, item):
        if not common.library_check(item, self.EmbyServer, self.emby_db):
            return False

        common.SwopMediaSources(item)  # 3D

        if not common.get_file_path(item, "musicvideos"):
            return False

        if item['ExistingItem']:
            update = True
            item['KodiItemId'] = item['ExistingItem'][0]
            item['KodiFileId'] = item['ExistingItem'][1]
            item['KodiPathId'] = item['ExistingItem'][2]
            self.video_db.delete_links_genres(item['KodiItemId'], "musicvideo")
            common.delete_ContentItemReferences(item['Id'], item['KodiItemId'], item['KodiFileId'], self.video_db, self.emby_db, "musicvideo")
        else:
            update = False
            LOG.debug("MusicVideoId for %s not found" % item['Id'])
            item['KodiItemId'] = self.video_db.create_entry_musicvideos()
            item['KodiPathId'] = self.video_db.get_add_path(item['Path'], "musicvideo")
            item['KodiFileId'] = self.video_db.create_entry_file()

        item['ArtistItems'] = item.get('ArtistItems', [])
        item['Album'] = item.get('Album', "--NO INFO--")
        item['Artist'] = " / ".join(item['Artists'])

        for Artist in item['ArtistItems']:
            Artist['Type'] = "Actor"
            Artist['Role'] = "MusicVideoArtist"
            Artist['PrimaryImageTag'] = "0"
            Artist['LibraryId'] = item['Library']['Id']

        for People in item['People']:
            if People['Type'] == "Actor":
                People['Role'] = "MusicVideoArtist"
                People['PrimaryImageTag'] = "0"
                People['LibraryId'] = item['Library']['Id']

        if not item['Artist']:
            LOG.warning("No artist found: %s %s %s " % (item['Name'], item['FullPath'], item['Id']))
            item['Artist'] = "--NO INFO--"
            item['ArtistItems'].append({'Name': '--NO INFO--', 'Type': "Actor", 'Role': "MusicVideoArtist", 'LibraryId': item['Library']['Id']})

        item['People'] = item['People'] + item['ArtistItems']
        common.set_MusicVideoTracks(item)
        common.set_ContentItem(item, self.video_db, self.emby_db, self.EmbyServer, "musicvideo", "M")
        self.video_db.add_link_tag(common.MediaTags[item['Library']['Name']], item['KodiItemId'], "musicvideo")
        self.video_db.set_Favorite(item['UserData']['IsFavorite'], item['KodiItemId'], "musicvideo")
        self.video_db.add_genres_and_links(item['Genres'], item['KodiItemId'], "musicvideo")

        if update:
            self.video_db.update_musicvideos(item['Name'], item['KodiArtwork']['poster'], item['RunTimeTicks'], item['Directors'], item['Studio'], item['ProductionYear'], item['Overview'], item['Album'], item['Artist'], item['Genre'], item['IndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['PremiereDate'], item['KodiItemId'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['KodiFileId'], item['Filename'])
            self.emby_db.update_reference(item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "MusicVideo", "musicvideo", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'], item['Id'])
            LOG.info("UPDATE musicvideo [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileId'], item['KodiItemId'], item['Id'], item['Name']))
        else:
            self.video_db.add_musicvideos(item['KodiItemId'], item['KodiFileId'], item['Name'], item['KodiArtwork']['poster'], item['RunTimeTicks'], item['Directors'], item['Studio'], item['ProductionYear'], item['Overview'], item['Album'], item['Artist'], item['Genre'], item['IndexNumber'], "%s%s" % (item['Path'], item['Filename']), item['KodiPathId'], item['PremiereDate'], item['DateCreated'], item['UserData']['PlayCount'], item['UserData']['LastPlayedDate'], item['Filename'])
            self.emby_db.add_reference(item['Id'], item['KodiItemId'], item['KodiFileId'], item['KodiPathId'], "MusicVideo", "musicvideo", None, item['Library']['Id'], item['ParentId'], item['PresentationUniqueKey'], item['UserData']['IsFavorite'])
            LOG.info("ADD musicvideo [%s/%s/%s] %s: %s" % (item['KodiPathId'], item['KodiFileId'], item['KodiItemId'], item['Id'], item['Name']))

        self.video_db.add_tags_and_links(item['KodiItemId'], "musicvideo", item['TagItems'])
        self.emby_db.add_multiversion(item, "MusicVideo", self.EmbyServer.API, self.video_db, update)
        return not update

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, Item):
        if Item['PlaybackPositionTicks']:
            RuntimeSeconds = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] / 100000)
        else:
            RuntimeSeconds = 0

        common.set_userdata_update_data(Item)
        self.video_db.set_Favorite(Item['IsFavorite'], Item['KodiItemId'], "musicvideo")
        self.video_db.update_bookmark_playstate(Item['KodiFileId'], Item['PlayCount'], Item['LastPlayedDate'], Item['PlaybackPositionTicks'], RuntimeSeconds)
        self.emby_db.update_reference_userdatachanged(Item['IsFavorite'], Item['Id'])
        LOG.debug("New resume point %s: %s" % (Item['Id'], Item['PlaybackPositionTicks']))
        LOG.info("USERDATA musicvideo [%s/%s] %s" % (Item['KodiFileId'], Item['KodiItemId'], Item['Id']))

    def remove(self, Item):
        self.remove_musicvideo(Item['KodiItemId'], Item['KodiFileId'], Item['Id'])

        if not Item['DeleteByLibraryId']:
            StackedIds = self.emby_db.get_stacked_embyid(Item['PresentationUniqueKey'], Item['Library']['Id'], "MusicVideo")

            if StackedIds: # multi version
                LOG.info("DELETE multi version musicvideos from embydb %s" % Item['Id'])

                for StackedId in StackedIds:
                    self.emby_db.remove_item(StackedId[0])

                for StackedId in StackedIds:
                    StackedItem = self.EmbyServer.API.get_Item(StackedId[0], ['MusicVideo'], False, False)

                    if StackedItem:
                        StackedItem['Library'] = Item['Library']
                        LOG.info("UPDATE remaining multi version musicvideo %s" % StackedItem['Id'])
                        self.musicvideo(StackedItem)  # update all stacked items

    def remove_musicvideo(self, KodiItemId, KodiFileId, EmbyItemId):
        common.delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, self.video_db, self.emby_db, "musicvideo")
        self.video_db.delete_musicvideos(KodiItemId, KodiFileId)
        LOG.info("DELETE musicvideo [%s/%s] %s" % (KodiItemId, KodiFileId, EmbyItemId))

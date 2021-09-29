# -*- coding: utf-8 -*-
import helper.loghandler
import helper.utils as Utils
import emby.obj_ops as Objects
from . import common as Common

LOG = helper.loghandler.LOG('EMBY.core.musicvideos.MusicVideos')


class MusicVideos:
    def __init__(self, EmbyServer, embydb, videodb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb
        self.video_db = videodb

    def musicvideo(self, item, library):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = Common.library_check(e_item, item['Id'], library, self.EmbyServer.API, self.EmbyServer.library.Whitelist)

        if not library:
            return False

        obj = Objects.mapitem(item, 'MusicVideo')
        obj['Emby_Type'] = 'MusicVideo'
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['ServerId'] = self.EmbyServer.server_id
        obj['FullPath'] = Common.SwopMediaSources(obj, item)  # 3D

        if not obj['FullPath']:  # Invalid Path
            LOG.error("Invalid path: %s" % obj['Id'])
            LOG.debug("Invalid path: %s" % obj)
            return False

        if e_item:
            update = True
            obj['KodiMvideoId'] = e_item[0]
            obj['KodiFileId'] = e_item[1]
            obj['KodiPathId'] = e_item[2]
        else:
            update = False
            LOG.debug("MvideoId for %s not found" % obj['Id'])
            obj['KodiMvideoId'] = self.video_db.create_entry_musicvideos()

        obj['Path'] = Common.get_path(obj, "musicvideos")
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Genres'] = obj['Genres'] or []
        obj['ArtistItems'] = obj['ArtistItems'] or []
        obj['Plot'] = Common.get_overview(obj['Plot'], item)
        obj['DateAdded'] = Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = Common.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Resume'] = Common.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)

        if not obj['Premiere']:
            obj['Premiere'] = Utils.convert_to_local(obj['Year'])

        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Studio'] = " / ".join(obj['Studios'] or [])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Video'] = Common.video_streams(obj['Video'] or [], obj['Container'], item)
        obj['Audio'] = Common.audio_streams(obj['Audio'] or [])
        obj['Streams'] = Common.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['Artwork'] = Common.get_all_artwork(Objects.mapitem(item, 'Artwork'), False, self.EmbyServer.server_id)

        if obj['Premiere']:
            obj['Premiere'] = str(obj['Premiere']).split('.')[0].replace('T', " ")

        for artist in obj['ArtistItems']:
            artist['Type'] = "Artist"

        obj['People'] = obj['People'] or [] + obj['ArtistItems']
        obj['People'] = Common.get_people_artwork(obj['People'], self.EmbyServer.server_id)

        # Try to detect track number
        if obj['Index'] is None: # and obj['SortTitle'] is not None:
            Temp = obj['MediaSourcesName'][:4]  # e.g. 01 - Artist - Title
            Temp = Temp.split("-")

            if len(Temp) > 1:
                Track = Temp[0].strip()

                if Track.isnumeric():
                    obj['Index'] = str(int(Track))  # remove leading zero e.g. 01

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite musicvideos')

        obj['Tags'] = tags
        Common.Streamdata_add(obj, self.emby_db, update)

        if update:
            self.video_db.update_musicvideos(obj['Title'], obj['Runtime'], obj['Directors'], obj['Studio'], obj['Year'], obj['Plot'], obj['Album'], obj['Artists'], obj['Genre'], obj['Index'], obj['Premiere'], obj['KodiMvideoId'])
            obj['Filename'] = Common.get_filename(obj, "musicvideos", self.EmbyServer.API)
            self.video_db.update_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])
            self.emby_db.update_reference(obj['PresentationKey'], obj['Favorite'], obj['Id'])
            LOG.info("UPDATE mvideo [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiFileId'], obj['KodiMvideoId'], obj['Id'], obj['Title']))
        else:
            obj['KodiPathId'] = self.video_db.get_add_path(obj['Path'], "musicvideos")
            obj['KodiFileId'] = self.video_db.create_entry_file()
            obj['Filename'] = Common.get_filename(obj, "musicvideos", self.EmbyServer.API)
            self.video_db.add_file(obj['KodiPathId'], obj['Filename'], obj['DateAdded'], obj['KodiFileId'])
            self.video_db.add_musicvideos(obj['KodiMvideoId'], obj['KodiFileId'], obj['Title'], obj['Runtime'], obj['Directors'], obj['Studio'], obj['Year'], obj['Plot'], obj['Album'], obj['Artists'], obj['Genre'], obj['Index'], obj['Premiere'])
            self.emby_db.add_reference(obj['Id'], obj['KodiMvideoId'], obj['KodiFileId'], obj['KodiPathId'], "MusicVideo", "musicvideo", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
            LOG.info("ADD mvideo [%s/%s/%s] %s: %s" % (obj['KodiPathId'], obj['KodiFileId'], obj['KodiMvideoId'], obj['Id'], obj['Title']))

        self.video_db.add_tags(obj['Tags'], obj['KodiMvideoId'], "musicvideo")
        self.video_db.add_genres(obj['Genres'], obj['KodiMvideoId'], "musicvideo")
        self.video_db.add_studios(obj['Studios'], obj['KodiMvideoId'], "musicvideo")
        self.video_db.add_playstate(obj['KodiFileId'], obj['PlayCount'], obj['DatePlayed'], obj['Resume'], obj['Runtime'], "DVDPlayer", 1)
        self.video_db.add_people(obj['People'], obj['KodiMvideoId'], "musicvideo")
        self.video_db.add_streams(obj['KodiFileId'], obj['Streams'], obj['Runtime'])
        self.video_db.common_db.add_artwork(obj['Artwork'], obj['KodiMvideoId'], "musicvideo")

        if "StackTimes" in obj:
            self.video_db.add_stacktimes(obj['KodiFileId'], obj['StackTimes'])

        Common.add_Multiversion(obj, self.emby_db, "MusicVideo", self.EmbyServer.API)
        return not update

    # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    def userdata(self, e_item, ItemUserdata):
        KodiMvideoId = e_item[0]
        KodiFileId = e_item[1]
        Resume = Common.adjust_resume((ItemUserdata['PlaybackPositionTicks'] or 0) / 10000000.0)
        MusicvideoData = self.video_db.get_musicvideos_data(KodiMvideoId)
        Runtime = round(float(MusicvideoData[6]) / 10000000.0, 6)
        PlayCount = Common.get_playcount(ItemUserdata['Played'], ItemUserdata['PlayCount'])
        DatePlayed = Utils.currenttime()

        if ItemUserdata['IsFavorite']:
            self.video_db.get_tag("Favorite musicvideos", KodiMvideoId, "musicvideo")
        else:
            self.video_db.remove_tag("Favorite musicvideos", KodiMvideoId, "musicvideo")

        LOG.debug("New resume point %s: %s" % (ItemUserdata['ItemId'], Resume))
        self.video_db.add_playstate(KodiFileId, PlayCount, DatePlayed, Resume, Runtime, "DVDPlayer", 1)
        self.emby_db.update_reference_userdatachanged(ItemUserdata['IsFavorite'], ItemUserdata['ItemId'])
        LOG.info("USERDATA musicvideo [%s/%s] %s: %s" % (KodiFileId, KodiMvideoId, ItemUserdata['ItemId'], MusicvideoData[2]))

    # Remove mvideoid, fileid, pathid, emby reference
    def remove(self, EmbyItemId):
        e_item = self.emby_db.get_item_by_id(EmbyItemId)

        if e_item:
            KodiId = e_item[0]
            KodiFileId = e_item[1]
            emby_presentation_key = e_item[8]
            emby_folder = e_item[6]

        else:
            return

        StackedIds = self.emby_db.get_stacked_embyid(emby_presentation_key, emby_folder, "MusicVideo")

        if len(StackedIds) > 1:
            self.emby_db.remove_item(EmbyItemId)
            LOG.info("DELETE stacked musicvideo from embydb %s" % EmbyItemId)

            for StackedId in StackedIds:
                StackedItem = self.EmbyServer.API.get_item_multiversion(StackedId[0])

                if StackedItem:
                    library_name = self.emby_db.get_Libraryname_by_Id(emby_folder)
                    LibraryData = {"Id": emby_folder, "Name": library_name}
                    LOG.info("UPDATE remaining stacked musicvideo from embydb %s" % StackedItem['Id'])
                    self.musicvideo(StackedItem, LibraryData)  # update all stacked items
        else:
            self.remove_musicvideo(KodiId, KodiFileId, EmbyItemId)

    def remove_musicvideo(self, KodiId, KodiFileId, EmbyItemId):
        self.video_db.common_db.delete_artwork(KodiId, "musicvideo")
        self.video_db.delete_musicvideos(KodiId, KodiFileId)
        self.emby_db.remove_item(EmbyItemId)
        LOG.info("DELETE musicvideo [%s/%s] %s" % (KodiId, KodiFileId, EmbyItemId))

# -*- coding: utf-8 -*-
import _strptime # Workaround for threads using datetime: _striptime is locked
import datetime
import re

import database.queries
import database.emby_db
import helper.api
import helper.loghandler
from . import obj_ops
from . import kodi
from . import queries_videos
from . import artwork
from . import common

class MusicVideos():
    def __init__(self, EmbyServer, embydb, videodb, direct_path, Utils):
        self.LOG = helper.loghandler.LOG('EMBY.core.musicvideos.MusicVideos')
        self.Utils = Utils
        self.EmbyServer = EmbyServer
        self.emby = embydb
        self.video = videodb
        self.emby_db = database.emby_db.EmbyDatabase(embydb.cursor)
        self.objects = obj_ops.Objects(self.Utils)
        self.item_ids = []
        self.Common = common.Common(self.emby_db, self.objects, self.Utils, direct_path, self.EmbyServer)
        self.MusicVideosDBIO = MusicVideosDBIO(videodb.cursor)
        self.KodiDBIO = kodi.Kodi(videodb.cursor, Utils)
        self.ArtworkDBIO = artwork.Artwork(videodb.cursor, self.Utils)

    def musicvideo(self, item, library):
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            If we don't get the track number from Emby, see if we can infer it
            from the sortname attribute.
        '''
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.EmbyServer.auth.get_serveraddress())
        obj = self.objects.map(item, 'MusicVideo')
        obj['Item'] = item
        obj['Library'] = library
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        update = True

        if e_item:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]

            if self.MusicVideosDBIO.get(*self.Utils.values(obj, queries_videos.get_musicvideo_obj)) is None:
                update = False
                self.LOG.info("MvideoId %s missing from kodi. repairing the entry" % obj['MvideoId'])
        else:
            update = False
            self.LOG.debug("MvideoId for %s not found" % obj['Id'])
            obj['MvideoId'] = self.MusicVideosDBIO.create_entry()

        obj['Item']['MediaSources'][0] = self.objects.MapMissingData(obj['Item']['MediaSources'][0], 'MediaSources')
        obj['MediaSourceID'] = obj['Item']['MediaSources'][0]['Id']
        obj['Runtime'] = obj['Item']['MediaSources'][0]['RunTimeTicks']

        if obj['Item']['MediaSources'][0]['Path']:
            obj['Path'] = obj['Item']['MediaSources'][0]['Path']

            #don't use 3d movies as default
            if "3d" in self.Utils.StringMod(obj['Item']['MediaSources'][0]['Path']):
                for DataSource in obj['Item']['MediaSources']:
                    if not "3d" in self.Utils.StringMod(DataSource['Path']):
                        DataSource = self.objects.MapMissingData(DataSource, 'MediaSources')
                        obj['Path'] = DataSource['Path']
                        obj['MediaSourceID'] = DataSource['Id']
                        obj['Runtime'] = DataSource['RunTimeTicks']
                        break

        obj['Path'] = API.get_file_path(obj['Path'])
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Genres'] = obj['Genres'] or []
        obj['ArtistItems'] = obj['ArtistItems'] or []
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['Premiere'] = self.Utils.convert_to_local(obj['Premiere']) if obj['Premiere'] else datetime.date(int(str(obj['Year'])[:4]) if obj['Year'] else 2021, 1, 1)
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))
        PathValid, obj = self.Common.get_path_filename(obj, "musicvideos")

        if not PathValid:
            return "Invalid Filepath"

        if obj['Premiere']:
            obj['Premiere'] = str(obj['Premiere']).split('.')[0].replace('T', " ")

        for artist in obj['ArtistItems']:
            artist['Type'] = "Artist"

        obj['People'] = obj['People'] or [] + obj['ArtistItems']
        obj['People'] = API.get_people_artwork(obj['People'])

        if obj['Index'] is None and obj['SortTitle'] is not None:
            search = re.search(r'^\d+\s?', obj['SortTitle'])

            if search:
                obj['Index'] = search.group()

        tags = []
        tags.extend(obj['TagItems'] or obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite musicvideos')

        obj['Tags'] = tags

        if update:
            self.musicvideo_update(obj)
        else:
            self.musicvideo_add(obj)

        self.KodiDBIO.update_path(*self.Utils.values(obj, queries_videos.update_path_mvideo_obj))
        self.KodiDBIO.update_file(*self.Utils.values(obj, queries_videos.update_file_obj))
        self.KodiDBIO.add_tags(*self.Utils.values(obj, queries_videos.add_tags_mvideo_obj))
        self.KodiDBIO.add_genres(*self.Utils.values(obj, queries_videos.add_genres_mvideo_obj))
        self.KodiDBIO.add_studios(*self.Utils.values(obj, queries_videos.add_studios_mvideo_obj))
        self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.KodiDBIO.add_people(*self.Utils.values(obj, queries_videos.add_people_mvideo_obj))
        self.KodiDBIO.add_streams(*self.Utils.values(obj, queries_videos.add_streams_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['MvideoId'], "musicvideo")
        self.item_ids.append(obj['Id'])

        if "StackTimes" in obj:
            self.KodiDBIO.add_stacktimes(*self.Utils.values(obj, queries_videos.add_stacktimes_obj))

        return not update

    #Add object to kodi
    def musicvideo_add(self, obj):
        obj = self.Common.Streamdata_add(obj, False)
        obj['PathId'] = self.KodiDBIO.add_path(*self.Utils.values(obj, queries_videos.add_path_obj))
        obj['FileId'] = self.KodiDBIO.add_file(*self.Utils.values(obj, queries_videos.add_file_obj))
        self.MusicVideosDBIO.add(*self.Utils.values(obj, queries_videos.add_musicvideo_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_mvideo_obj))
        self.LOG.info("ADD mvideo [%s/%s/%s] %s: %s" % (obj['PathId'], obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title']))

    #Update object to kodi
    def musicvideo_update(self, obj):
        obj = self.Common.Streamdata_add(obj, True)
        self.MusicVideosDBIO.update(*self.Utils.values(obj, queries_videos.update_musicvideo_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE mvideo [%s/%s/%s] %s: %s" % (obj['PathId'], obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title']))

    def userdata(self, item):
        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar
        '''
        e_item = self.emby_db.get_item_by_id(item['Id'])
        API = helper.api.API(item, self.Utils, self.EmbyServer.auth.get_serveraddress())
        obj = self.objects.map(item, 'MusicVideoUserData')
        obj['Item'] = item

        if e_item:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
        else:
            return

        obj = self.Common.Streamdata_add(obj, True)
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0, self.Utils)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

        if obj['DatePlayed']:
            obj['DatePlayed'] = self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Favorite']:
            self.KodiDBIO.get_tag(*self.Utils.values(obj, queries_videos.get_tag_mvideo_obj))
        else:
            self.KodiDBIO.remove_tag(*self.Utils.values(obj, queries_videos.delete_tag_mvideo_obj))

        self.KodiDBIO.add_playstate(*self.Utils.values(obj, queries_videos.add_bookmark_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA mvideo [%s/%s] %s: %s" % (obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title']))

    #Remove mvideoid, fileid, pathid, emby reference
    def remove(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        if e_item:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        else:
            return

        self.ArtworkDBIO.delete(obj['MvideoId'], "musicvideo")
        self.MusicVideosDBIO.delete(*self.Utils.values(obj, queries_videos.delete_musicvideo_obj))
        self.emby_db.remove_item(*self.Utils.values(obj, database.queries.delete_item_obj))
        self.LOG.info("DELETE musicvideo %s [%s/%s] %s" % (obj['MvideoId'], obj['PathId'], obj['FileId'], obj['Id']))

class MusicVideosDBIO():
    def __init__(self, cursor):
        self.cursor = cursor

    def create_entry(self):
        self.cursor.execute(queries_videos.create_musicvideo)
        return self.cursor.fetchone()[0] + 1

    def get(self, *args):
        self.cursor.execute(queries_videos.get_musicvideo, args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def add(self, *args):
        self.cursor.execute(queries_videos.add_musicvideo, args)

    def update(self, *args):
        self.cursor.execute(queries_videos.update_musicvideo, args)

    def delete(self, kodi_id, file_id):
        self.cursor.execute(queries_videos.delete_musicvideo, (kodi_id,))
        self.cursor.execute(queries_videos.delete_file, (file_id,))

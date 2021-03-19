# -*- coding: utf-8 -*-
import helper.loghandler
import database.queries

class Common():
    def __init__(self, emby_db, objects, Utils, direct_path, EmbyServer):
        self.LOG = helper.loghandler.LOG('EMBY.core.common.Common')
        self.Utils = Utils
        self.emby_db = emby_db
        self.objects = objects
        self.direct_path = direct_path
        self.EmbyServer = EmbyServer

    #Add streamdata
    def Streamdata_add(self, obj, Update):
        if Update:
            self.emby_db.remove_item_streaminfos(obj['Id'])

        if "3d" in self.Utils.StringMod(obj['Item']['MediaSources'][0]['Path']):
            if len(obj['Item']['MediaSources']) >= 2:
                Temp = obj['Item']['MediaSources'][1]
                obj['Item']['MediaSources'][1] = obj['Item']['MediaSources'][0]
                obj['Item']['MediaSources'][0] = Temp

        CountMediaSources = 0

        for DataSource in obj['Item']['MediaSources']:
            DataSource = self.objects.MapMissingData(DataSource, 'MediaSources')
            DataSource['emby_id'] = obj['Item']['Id']
            DataSource['MediaIndex'] = CountMediaSources
            DataSource['Formats'] = ""
            DataSource['RequiredHttpHeaders'] = ""
            CountMediaStreamAudio = 0
            CountMediaStreamVideo = 0
            CountMediaSubtitle = 0
            CountStreamSources = 0
            DataSource = self.objects.MapMissingData(DataSource, 'MediaSources')
            self.emby_db.add_mediasource(*self.Utils.values(DataSource, database.queries.add_mediasource_obj))

            for DataStream in DataSource['MediaStreams']:
                DataStream['emby_id'] = obj['Item']['Id']
                DataStream['MediaIndex'] = CountMediaSources
                DataStream['StreamIndex'] = CountStreamSources

                if DataStream['Type'] == "Video":
                    DataStream = self.objects.MapMissingData(DataStream, 'VideoStreams')
                    DataStream['VideoIndex'] = CountMediaStreamVideo
                    self.emby_db.add_videostreams(*self.Utils.values(DataStream, database.queries.add_videostreams_obj))
                    CountMediaStreamVideo += 1
                elif DataStream['Type'] == "Audio":
                    DataStream = self.objects.MapMissingData(DataStream, 'AudioStreams')
                    DataStream['AudioIndex'] = CountMediaStreamAudio
                    self.emby_db.add_audiostreams(*self.Utils.values(DataStream, database.queries.add_audiostreams_obj))
                    CountMediaStreamAudio += 1
                elif DataStream['Type'] == "Subtitle":
                    DataStream = self.objects.MapMissingData(DataStream, 'Subtitles')
                    DataStream['SubtitleIndex'] = CountMediaSubtitle
                    self.emby_db.add_subtitles(*self.Utils.values(DataStream, database.queries.add_subtitles_obj))
                    CountMediaSubtitle += 1

                CountStreamSources += 1

            CountMediaSources += 1

        return obj

    def get_path_filename(self, obj, MediaID):
        #Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
        KodiPluginPath = False

        if obj['Path'].startswith("plugin://"):
            KodiPluginPath = True

        if self.direct_path or KodiPluginPath:
            if KodiPluginPath:
                obj['Filename'] = obj['Path']
            else:
                obj['Filename'] = obj['Path'].rsplit('\\', 1)[1] if '\\' in obj['Path'] else obj['Path'].rsplit('/', 1)[1]

            obj['Path'] = self.Utils.StringDecode(obj['Path'])
            obj['Filename'] = self.Utils.StringDecode(obj['Filename'])

            if not self.Utils.validate(obj['Path']):
                return False, obj

            obj['Path'] = obj['Path'].replace(obj['Filename'], "")

            if MediaID == "audio":
                return True, obj

            #Detect Multipart videos
            if 'PartCount' in obj['Item']:
                if (obj['Item']['PartCount']) >= 2:
                    AdditionalParts = self.EmbyServer.API.get_additional_parts(obj['Id'])
                    obj['Filename'] = obj['Path'] + obj['Filename']
                    obj['StackTimes'] = str(obj['Runtime'])

                    for AdditionalItem in AdditionalParts['Items']:
                        AdditionalItem = self.objects.MapMissingData(AdditionalItem, 'MediaSources')
                        Path = self.Utils.StringDecode(AdditionalItem['Path'])
                        obj['Filename'] = obj['Filename'] + " , " + Path
                        RunTimePart = round(float((AdditionalItem['RunTimeTicks'] or 0) / 10000000.0), 6)
                        obj['Runtime'] = obj['Runtime'] + RunTimePart
                        obj['StackTimes'] = str(obj['StackTimes']) + "," + str(obj['Runtime'])

                    obj['Filename'] = "stack://" + obj['Filename']
        else:
            Filename = self.Utils.PathToFilenameReplaceSpecialCharecters(obj['Path'])

            if MediaID == "tvshows":
                obj['Path'] = "http://127.0.0.1:57578/tvshows/%s/" % obj['SeriesId']

                try:
                    obj['Filename'] = "%s-%s-%s-stream-%s" % (obj['Id'], obj['Item']['MediaSources'][0]['Id'], obj['Item']['MediaSources'][0]['MediaStreams'][0]['BitRate'], Filename)
                except:
                    obj['Filename'] = "%s-%s-stream-%s" % (obj['Id'], obj['Item']['MediaSources'][0]['Id'], Filename)
                    self.LOG.warning("No video bitrate available %s" % self.Utils.StringMod(obj['Item']['Path']))
            elif MediaID == "movies":
                obj['Path'] = "http://127.0.0.1:57578/movies/%s/" % obj['LibraryId']

                try:
                    obj['Filename'] = "%s-%s-%s-stream-%s" % (obj['Id'], obj['MediaSourceID'], obj['Item']['MediaSources'][0]['MediaStreams'][0]['BitRate'], Filename)
                except:
                    obj['Filename'] = "%s-%s-stream-%s" % (obj['Id'], obj['MediaSourceID'], Filename)
                    self.LOG.warning("No video bitrate available %s" % self.Utils.StringMod(obj['Item']['Path']))
            elif MediaID == "musicvideos":
                obj['Path'] = "http://127.0.0.1:57578/musicvideos/%s/" % obj['LibraryId']

                try:
                    obj['Filename'] = "%s-%s-%s-stream-%s" % (obj['Id'], obj['PresentationKey'], obj['Streams']['video'][0]['BitRate'], Filename)
                except:
                    obj['Filename'] = "%s-%s-stream-%s" % (obj['Id'], obj['PresentationKey'], Filename)
                    self.LOG.warning("No video bitrate available %s" % self.Utils.StringMod(obj['Item']['Path']))
            elif MediaID == "audio":
                obj['Path'] = "http://127.0.0.1:57578/audio/%s/" % obj['Id']
                obj['Filename'] = "%s-stream-%s" % (obj['Id'], Filename)
                return True, obj

            #Detect Multipart videos
            if 'PartCount' in obj['Item']:
                if (obj['Item']['PartCount']) >= 2:
                    AdditionalParts = self.EmbyServer.API.get_additional_parts(obj['Id'])
                    obj['Filename'] = obj['Path'] + obj['Filename']
                    obj['StackTimes'] = str(obj['Runtime'])

                    for AdditionalItem in AdditionalParts['Items']:
                        AdditionalItem = self.objects.MapMissingData(AdditionalItem, 'MediaSources')
                        Filename = self.Utils.PathToFilenameReplaceSpecialCharecters(AdditionalItem['Path'])

                        try:
                            obj['Filename'] = obj['Filename'] + " , " + obj['Path'] + "%s--%s-stream-%s" % (AdditionalItem['Id'], AdditionalItem['MediaSources'][0]['MediaStreams'][0]['BitRate'], Filename)
                        except:
                            obj['Filename'] = obj['Filename'] + " , " + obj['Path'] + "%s--stream-%s" % (AdditionalItem['Id'], Filename)

                        RunTimePart = round(float((AdditionalItem['RunTimeTicks'] or 0) / 10000000.0), 6)
                        obj['Runtime'] = obj['Runtime'] + RunTimePart
                        obj['StackTimes'] = str(obj['StackTimes']) + "," + str(obj['Runtime'])

                    obj['Filename'] = "stack://" + obj['Filename']

        return True, obj

    def library_check(self, e_item, item, library):
        if library is None:
            if e_item:
                view_id = e_item[6]
                view_name = self.emby_db.get_view_name(view_id)
            else:
                ancestors = self.EmbyServer.API.get_ancestors(item['Id'])

                if not ancestors:
                    if item['Type'] == 'MusicArtist':
                        try:
                            views = self.emby_db.get_views_by_media('music')[0]
                            view_id = views[0]
                            view_name = views[1]
                        except:
                            view_id = None
                            view_name = None

                    else: # Grab the first music library
                        view_id = None
                        view_name = None
                else:
                    for ancestor in ancestors:
                        if ancestor['Type'] == 'CollectionFolder':
                            view = self.emby_db.get_view_name(ancestor['Id'])

                            if not view:
                                view_id = None
                                view_name = None
                            else:
                                view_id = ancestor['Id']
                                view_name = ancestor['Name']

                            break

            sync = self.Utils.get_sync()

            if not library:
                library = {}

            if view_id not in [x.replace('Mixed:', "") for x in sync['Whitelist'] + sync['Libraries']]:
                self.LOG.info("Library %s is not synced. Skip update." % view_id)
                return False

            library['Id'] = view_id
            library['Name'] = view_name

        return library

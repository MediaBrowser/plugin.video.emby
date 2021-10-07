# -*- coding: utf-8 -*-
import helper.loghandler
import helper.utils as Utils


if Utils.Python3:
    from urllib.parse import quote, urlparse
else:
    from urllib import quote
    from urlparse import urlparse

LOG = helper.loghandler.LOG('EMBY.core.common')


def add_Multiversion(obj, emby_db, emby_type, API):
    MediaStreamsTotal = len(obj['Item']['MediaSources'])
    ExistingItem = None

    if MediaStreamsTotal > 1:
        CurrentId = obj['Id']
        LOG.debug("Multiversion video detected: %s" % CurrentId)

        for DataSource in obj['Item']['MediaSources']:
            ItemReferenced = API.get_item(DataSource['Id'])

            if not ItemReferenced:  # Server restarted
                return

            LOG.debug("Multiversion video detected, referenced item: %s" % ItemReferenced['Id'])
            e_MultiItem = emby_db.get_item_by_id(ItemReferenced['Id'])
            obj['Id'] = ItemReferenced['Id']

            if not e_MultiItem:
                if emby_type == "Episode":
                    emby_db.add_reference(obj['Id'], obj['KodiEpisodeId'], obj['KodiFileId'], obj['KodiPathId'], "Episode", "episode", obj['KodiSeasonId'], obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
                elif emby_type == "Movie":
                    emby_db.add_reference(obj['Id'], obj['KodiMovieId'], obj['KodiFileId'], obj['KodiPathId'], "Movie", "movie", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])
                elif emby_type == "MusicVideo":
                    emby_db.add_reference(obj['Id'], obj['KodiMvideoId'], obj['KodiFileId'], obj['KodiPathId'], "MusicVideo", "musicvideo", None, obj['LibraryId'], obj['EmbyParentId'], obj['PresentationKey'], obj['Favorite'])

                Streamdata_add(obj, emby_db, False)
            else:
                if emby_type == "Episode":
                    emby_db.update_reference_multiversion(obj['Id'], obj['PresentationKey'], obj['Favorite'], obj['KodiEpisodeId'], obj['KodiFileId'], obj['KodiPathId'], obj['KodiSeasonId'])
                elif emby_type == "Movie":
                    emby_db.update_reference_multiversion(obj['Id'], obj['PresentationKey'], obj['Favorite'], obj['KodiMovieId'], obj['KodiFileId'], obj['KodiPathId'], None)
                elif emby_type == "MusicVideo":
                    emby_db.update_reference_multiversion(obj['Id'], obj['PresentationKey'], obj['Favorite'], obj['KodiMvideoId'], obj['KodiFileId'], obj['KodiPathId'], None)

                Streamdata_add(obj, emby_db, True)
                LOG.debug("Multiversion video detected, referenced item exists: %s" % ItemReferenced['Id'])

                # check if referenced Kodi item changed on multivideos and return old item to read Kodiid and Kodi fileid -> used to remove old item
                if CurrentId != obj['Id']:
                    ExistingItem = e_MultiItem

    return ExistingItem

def library_check(e_item, ItemId, library, API, Whitelist):
    if not library:
        library_id = ""
        library = {}

        if e_item:
            library_id = e_item[6]
            library_name = Check_LibraryIsSynced(library_id, Whitelist)

            if not library_name:
                return False
        else:  # Realtime Updates
            library_name = ""
            ancestors = API.get_ancestors(ItemId)

            if not ancestors:
                return False

            for ancestor in ancestors:
                if ancestor['Type'] == 'CollectionFolder':
                    library_name = Check_LibraryIsSynced(ancestor['Id'], Whitelist)

                    if not library_name:
                        return False

                    library_id = ancestor['Id']
                    break

        if library_id:
            library = {'Id': library_id, 'Name': library_name}

    return library

def Check_LibraryIsSynced(library_id, Whitelist):
    Library_Name = ""

    for SyncedLib in Whitelist:
        if library_id == SyncedLib[0]:
            Library_Name = SyncedLib[2]
            break

    if not Library_Name:
        LOG.info("Library %s is not synced. Skip update." % library_id)
        return False

    return Library_Name

def get_filename(obj, MediaID, API):
    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    Temp = obj['FullPath'].lower()

    if Temp.startswith("plugin://"):
        return obj['FullPath']

    if Temp.endswith(".bdmv"):
        ForceNativeMode = True

    # Native
    if Utils.useDirectPaths or ForceNativeMode:
        Filename = obj['FullPath'].rsplit('\\', 1)[1] if '\\' in obj['FullPath'] else obj['FullPath'].rsplit('/', 1)[1]
        Filename = Utils.StringDecode(Filename)

        if MediaID == "audio":
            return Filename

        # Detect Multipart videos
        if 'PartCount' in obj['Item']:
            if (obj['Item']['PartCount']) >= 2:
                AdditionalParts = API.get_additional_parts(obj['Id'])
                Filename = Utils.StringDecode(obj['FullPath'])
                obj['StackTimes'] = str(obj['Runtime'])

                for AdditionalItem in AdditionalParts['Items']:
                    Path = Utils.StringDecode(AdditionalItem['Path'])
                    Filename = Filename + " , " + Path

                    if 'RunTimeTicks' not in AdditionalItem:
                        AdditionalItem['RunTimeTicks'] = 0

                    RunTimePart = round(float((AdditionalItem['RunTimeTicks']) / 10000000.0), 6)
                    obj['Runtime'] += RunTimePart
                    obj['StackTimes'] = str(obj['StackTimes']) + "," + str(obj['Runtime'])

                Filename = "stack://" + Filename

        return Filename

    # Addon
    Filename = Utils.PathToFilenameReplaceSpecialCharecters(obj['FullPath'])
    Filename = Filename.replace("-", "_").replace(" ", "")

    if 'PresentationKey' in obj:
        PresentationKey = obj['PresentationKey'].replace("-", "_").replace(" ", "")
    else:
        PresentationKey = ""

    if 'CodecVideo' in obj:
        CodecVideo = obj['CodecVideo']
    else:
        CodecVideo = ""

    if MediaID == "tvshows":
        if Temp.endswith(".iso"):
            Filename = "embyiso-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiEpisodeId'], obj['KodiFileId'], "episode", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, "iso-container.mp4")
        else:
            try:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiEpisodeId'], obj['KodiFileId'], "episode", obj['Item']['MediaSources'][0]['MediaStreams'][0]['BitRate'], obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
            except:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiEpisodeId'], obj['KodiFileId'], "episode", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
                LOG.warning("No video bitrate available %s" % Utils.StringEncode(obj['Item']['Path']))
    elif MediaID == "movies":
        if Temp.endswith(".iso"):
            Filename = "embyiso-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMovieId'], obj['KodiFileId'], "movie", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, "iso-container.mp4")
        else:
            try:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMovieId'], obj['KodiFileId'], "movie", obj['Item']['MediaSources'][0]['MediaStreams'][0]['BitRate'], obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
            except:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMovieId'], obj['KodiFileId'], "movie", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
                LOG.warning("No video bitrate available %s" % Utils.StringEncode(obj['Item']['Path']))
    elif MediaID == "musicvideos":
        if Temp.endswith(".iso"):
            Filename = "embyiso-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMvideoId'], obj['KodiFileId'], "musicvideo", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
        else:
            try:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMvideoId'], obj['KodiFileId'], "musicvideo", obj['Streams']['video'][0]['BitRate'], obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
            except:
                Filename = "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], obj['MediaSourceID'], PresentationKey, obj['EmbyParentId'], obj['KodiMvideoId'], obj['KodiFileId'], "musicvideo", 0, obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], CodecVideo, Filename)
                LOG.warning("No video bitrate available %s" % Utils.StringEncode(obj['Item']['Path']))
    elif MediaID == "audio":
        Filename = "embyaudio-%s-%s-%s-%s-%s" % (obj['ServerId'], obj['Id'], PresentationKey, "song", Filename)
        return Filename

    # Detect Multipart videos
    if 'PartCount' in obj['Item']:
        if (obj['Item']['PartCount']) >= 2:
            AdditionalParts = API.get_additional_parts(obj['Id'])
            obj['StackTimes'] = str(obj['Runtime'])
            StackedFilename = obj['Path'] + Filename

            for AdditionalItem in AdditionalParts['Items']:
                AdditionalFilename = Utils.PathToFilenameReplaceSpecialCharecters(AdditionalItem['Path'])
                AdditionalFilename = AdditionalFilename.replace("-", "_").replace(" ", "")

                try:
                    StackedFilename = StackedFilename + " , " + obj['Path'] + "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], AdditionalItem['Id'], AdditionalItem['MediaSources'][0]['Id'], PresentationKey, obj['EmbyParentId'], obj['KodiPathId'], obj['KodiFileId'], "movie", AdditionalItem['MediaSources'][0]['MediaStreams'][0]['BitRate'], obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], obj['CodecVideo'], AdditionalFilename)
                except:
                    StackedFilename = StackedFilename + " , " + obj['Path'] + "embyvideo-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (obj['ServerId'], AdditionalItem['Id'], AdditionalItem['MediaSources'][0]['Id'], PresentationKey, obj['EmbyParentId'], obj['KodiPathId'], obj['KodiFileId'], "movie", "", obj['ExternalSubtitle'], obj['MediasourcesCount'], obj['VideostreamCount'], obj['AudiostreamCount'], "", AdditionalFilename)

                if 'RunTimeTicks' in AdditionalItem:
                    RunTimePart = round(float((AdditionalItem['RunTimeTicks'] or 0) / 10000000.0), 6)
                else:
                    RunTimePart = 0

                obj['Runtime'] += RunTimePart
                obj['StackTimes'] = str(obj['StackTimes']) + "," + str(obj['Runtime'])

            Filename = "stack://" + StackedFilename

    return Filename

def adjust_resume(resume_seconds):
    resume = 0

    if resume_seconds:
        resume = round(float(resume_seconds), 6)
        jumpback = int(Utils.resumeJumpBack)

        if resume > jumpback:
            # To avoid negative bookmark
            resume -= jumpback

    return resume

def get_path(obj, MediaID):
    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    Temp = obj['FullPath'].lower()

    if 'Container' not in obj:
        Container = ""
    else:
        Container = obj['Container']

    if Temp.startswith("plugin://"):
        ForceNativeMode = True
    elif Container in ('dvd', 'bluray') and not Temp.endswith(".iso"):
        ForceNativeMode = True
    elif Temp.startswith("http"):
        UrlData = urlparse(obj['FullPath'])
        UrlPath = quote(UrlData[2])
        obj['FullPath'] = "%s://%s%s" % (UrlData[0], UrlData[1], UrlPath)

    if Utils.useDirectPaths or ForceNativeMode:
        Temp2 = obj['FullPath'].rsplit('\\', 1)[1] if '\\' in obj['FullPath'] else obj['FullPath'].rsplit('/', 1)[1]
        Temp2 = Utils.StringDecode(Temp2)
        Path = Utils.StringDecode(obj['FullPath']).replace(Temp2, "")
        PathChar = Path[-1]

        if MediaID == "tvshows":
            obj['PathParent'] = Path
            Path = "%s%s" % (Utils.StringDecode(obj['FullPath']), PathChar)
    else:
        if MediaID == "tvshows":
            obj['PathParent'] = "http://127.0.0.1:57578/tvshows/%s/" % obj['LibraryId']
            Path = "http://127.0.0.1:57578/tvshows/%s/%s/" % (obj['LibraryId'], obj['Id'])
        elif MediaID == "episodes":
            Path = "http://127.0.0.1:57578/tvshows/%s/%s/" % (obj['LibraryId'], obj['SeriesId'])
        elif MediaID == "movies":
            Path = "http://127.0.0.1:57578/movies/%s/" % obj['LibraryId']
        elif MediaID == "musicvideos":
            Path = "http://127.0.0.1:57578/musicvideos/%s/" % obj['LibraryId']
        elif MediaID == "audio":
            Path = "http://127.0.0.1:57578/audio/%s/" % obj['LibraryId']
        else:
            Path = ""

    return Path

# Add streamdata
def Streamdata_add(obj, emby_db, Update):
    if Update:
        emby_db.remove_item_streaminfos(obj['Id'])

    PathTemp = Utils.StringEncode(obj['Item']['MediaSources'][0]['Path'])
    Counter = 0

    if "3d" in PathTemp or ".iso" in PathTemp:
        for DataSource in obj['Item']['MediaSources']:
            PathTemp = Utils.StringEncode(DataSource['Path'])

            if "3d" not in PathTemp and ".iso" not in PathTemp:
                Temp = DataSource
                obj['Item']['MediaSources'][Counter] = obj['Item']['MediaSources'][0]
                obj['Item']['MediaSources'][0] = Temp
                break

            Counter += 1

    CountMediaSources = 0
    CodecVideoAdded = False
    ExternalSubtitle = "0"
    CountMediaStreamAudio = 0
    CountMediaStreamVideo = 0

    for DataSource in obj['Item']['MediaSources']:
        DataSource['emby_id'] = obj['Id']
        DataSource['MediaIndex'] = CountMediaSources
        DataSource['Formats'] = ""
        DataSource['RequiredHttpHeaders'] = ""
        CountMediaStreamAudio = 0
        CountMediaStreamVideo = 0
        CountMediaSubtitle = 0
        CountStreamSources = 0
        emby_db.add_mediasource(DataSource['emby_id'], DataSource['MediaIndex'], DataSource['Id'], DataSource['Path'], DataSource['Name'], DataSource['Size'])

        for DataStream in DataSource['MediaStreams']:
            DataStream['emby_id'] = obj['Id']
            DataStream['MediaIndex'] = CountMediaSources
            DataStream['StreamIndex'] = CountStreamSources

            if DataStream['Type'] == "Video":
                if 'BitRate' not in DataStream:
                    DataStream['BitRate'] = 0

                if 'Codec' not in DataStream:
                    DataStream['Codec'] = ""

                emby_db.add_videostreams(DataStream['emby_id'], DataStream['MediaIndex'], DataStream['StreamIndex'], DataStream['Codec'], DataStream['BitRate'])

                if not CodecVideoAdded:
                    CodecVideoAdded = True
                    obj['CodecVideo'] = DataStream['Codec']

                CountMediaStreamVideo += 1
            elif DataStream['Type'] == "Audio":
                emby_db.add_audiostreams(DataStream['emby_id'], DataStream['MediaIndex'], DataStream['StreamIndex'], DataStream['DisplayTitle'])
                CountMediaStreamAudio += 1
            elif DataStream['Type'] == "Subtitle":
                if 'Language' not in DataStream:
                    DataStream['Language'] = "no info"

                emby_db.add_subtitles(DataStream['emby_id'], DataStream['MediaIndex'], DataStream['StreamIndex'], DataStream['Codec'], DataStream['Language'], DataStream['DisplayTitle'])

                if DataStream['Codec'] == "srt":
                    ExternalSubtitle = "1"

                CountMediaSubtitle += 1

            CountStreamSources += 1

        CountMediaSources += 1

    obj['ExternalSubtitle'] = ExternalSubtitle
    obj['VideostreamCount'] = CountMediaStreamVideo
    obj['AudiostreamCount'] = CountMediaStreamAudio
    obj['MediasourcesCount'] = CountMediaSources

def SwopMediaSources(obj, item):
    try:
        if 'Path' in obj['Item']['MediaSources'][0]:
            obj['MediaSourceID'] = obj['Item']['MediaSources'][0]['Id']

            if 'RunTimeTicks' in obj['Item']['MediaSources'][0]:
                obj['Runtime'] = obj['Item']['MediaSources'][0]['RunTimeTicks']
            else:
                obj['Runtime'] = 0

            if obj['Item']['MediaSources'][0]['Path']:
                obj['Path'] = obj['Item']['MediaSources'][0]['Path']

                # don't use 3d or iso movies as default
                PathTemp = Utils.StringEncode(obj['Item']['MediaSources'][0]['Path'])

                if "3d" in PathTemp or ".iso" in PathTemp:
                    for DataSource in obj['Item']['MediaSources']:
                        PathTemp = Utils.StringEncode(DataSource['Path'])

                        if "3d" not in PathTemp and ".iso" not in PathTemp:
                            obj['Path'] = DataSource['Path']
                            obj['MediaSourceID'] = DataSource['Id']
                            obj['Runtime'] = DataSource['RunTimeTicks']
                            break

            return get_file_path(obj['Path'], item)
    except:
        LOG.debug("No valid content: %s" % item)

    return ""

def get_file_path(path, item):
    if path is None:
        path = item.get('Path')

    path = Utils.StringEncode(path)

    # Addonmode replace filextensions
    if path.endswith('.strm'):
        path = path.replace('.strm', "")

        if 'Container' in item:
            if not path.endswith(Utils.StringEncode(item['Container'])):
                path = path + "." + Utils.StringEncode(item['Container'])

    if not path:
        return ""

    if path.startswith('\\\\'):
        path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    if 'Container' in item:
        if item['Container'] == 'dvd':
            path = "%s/VIDEO_TS/VIDEO_TS.IFO" % path
        elif item['Container'] == 'bluray':
            path = "%s/BDMV/index.bdmv" % path

    path = path.replace('\\\\', "\\")

    if '\\' in path:
        path = path.replace('/', "\\")

    if '://' in path:
        protocol = path.split('://')[0]
        path = path.replace(protocol, protocol.lower())

    return path

def get_playcount(played, playcount):
    return (playcount or 1) if played else None

def get_actors(people, ServerId):
    cast = []
    get_people_artwork(people, ServerId)

    for person in people:
        if person['Type'] == "Actor":
            cast.append({
                'name': person['Name'],
                'role': person.get('Role', "Unknown"),
                'order': len(cast) + 1,
                'thumbnail': person['imageurl']
            })

    return cast

def media_streams(video, audio, subtitles):
    return {'video': video or [], 'audio': audio or [], 'subtitle': subtitles or []}

def video_streams(tracks, container, item):
    if container:
        container = container.split(',')[0]

    for track in tracks:
        track.update({
            'codec': track.get('Codec', "").lower(),
            'profile': track.get('Profile', "").lower(),
            'height': track.get('Height'),
            'width': track.get('Width'),
            '3d': item.get('Video3DFormat'),
            'aspect': 1.85
        })

        if "msmpeg4" in track['codec']:
            track['codec'] = "divx"

        elif "mpeg4" in track['codec']:
            if "simple profile" in track['profile'] or not track['profile']:
                track['codec'] = "xvid"
        elif "h264" in track['codec']:
            if container in ('mp4', 'mov', 'm4v'):
                track['codec'] = "avc1"

        try:
            width, height = item.get('AspectRatio', track.get('AspectRatio', "0")).split(':')
            track['aspect'] = round(float(width) / float(height), 6)
        except (ValueError, ZeroDivisionError):

            if track['width'] and track['height']:
                track['aspect'] = round(float(track['width'] / track['height']), 6)

        track['duration'] = get_runtime(item)

    return tracks

def audio_streams(tracks):
    for track in tracks:
        track.update({
            'codec': track.get('Codec', "").lower(),
            'profile': track.get('Profile', "").lower(),
            'channels': track.get('Channels'),
            'language': track.get('Language')
        })

        if "dts-hd ma" in track['profile']:
            track['codec'] = "dtshd_ma"
        elif "dts-hd hra" in track['profile']:
            track['codec'] = "dtshd_hra"

    return tracks

def get_runtime(item):
    try:
        runtime = item['RunTimeTicks'] / 10000000.0
    except KeyError:
        runtime = item.get('CumulativeRunTimeTicks', 0) / 10000000.0

    return runtime


def get_overview(overview, item):
    overview = overview or item.get('Overview')

    if not overview:
        return ""

    overview = overview.replace("\"", "\'")
    overview = overview.replace("\n", "[CR]")
    overview = overview.replace("\r", " ")
    overview = overview.replace("<br>", "[CR]")
    return overview

def get_DateAdded(DateInfo):
    if DateInfo:
        DateAdded = DateInfo.split('.')[0].replace('T', " ")
        FileDate = "%s.%s.%s" % tuple(reversed(DateAdded.split('T')[0].split('-')))
        return DateAdded, FileDate

    return None, None

def get_mpaa(rating, item):
    mpaa = rating or item.get('OfficialRating', "")

    if mpaa in ("NR", "UR"):
        # Kodi seems to not like NR, but will accept Not Rated
        mpaa = "Not Rated"

    if "FSK-" in mpaa:
        mpaa = mpaa.replace("-", " ")

    if "GB-" in mpaa:
        mpaa = mpaa.replace("GB-", "UK:")

    return mpaa

# Get people (actor, director, etc) artwork.
def get_people_artwork(people, ServerId):
    for person in people:
        if 'PrimaryImageTag' in person:
            person['imageurl'] = "http://127.0.0.1:57578/embyimage-%s-%s-0-Primary-%s" % (ServerId, person['Id'], person['PrimaryImageTag'])
        else:
            person['imageurl'] = None

    return people

# Get all artwork possible. If parent_info is True, it will fill missing artwork with parent artwork.
def get_all_artwork(obj, parent_info, ServerId):
    all_artwork = {'Backdrop': get_backdrops(obj['Id'], obj['BackdropTags'] or [], ServerId), 'Thumb': ""}

    for artwork in (obj['Tags'] or []):
        all_artwork[artwork] = "http://127.0.0.1:57578/embyimage-%s-%s-0-%s-%s" % (ServerId, obj['Id'], artwork, obj['Tags'][artwork])

    if parent_info:
        if not all_artwork['Backdrop'] and obj['ParentBackdropId']:
            all_artwork['Backdrop'] = get_backdrops(obj['ParentBackdropId'], obj['ParentBackdropTags'], ServerId)

        for art in ('Logo', 'Art', 'Thumb'):
            if art not in all_artwork and obj['Parent%sId' % art]:
                all_artwork[art] = "http://127.0.0.1:57578/embyimage-%s-%s-0-%s-%s" % (ServerId, obj['Parent%sId' % art], art, obj['Parent%sTag' % art])

        # TV Show
        if obj.get('SeriesTag'):
            all_artwork['Series.Primary'] = "http://127.0.0.1:57578/embyimage-%s-%s-0-Primary-%s" % (ServerId, obj['SeriesId'], obj['SeriesTag'])

            if 'Primary' not in all_artwork:
                all_artwork['Primary'] = all_artwork['Series.Primary']

        # Album
        elif obj.get('AlbumTag'):
            all_artwork['Album.Primary'] = "http://127.0.0.1:57578/embyimage-%s-%s-0-Primary-%s" % (ServerId, obj['AlbumId'], obj['AlbumTag'])

            if 'Primary' not in all_artwork:
                all_artwork['Primary'] = all_artwork['Album.Primary']

    return all_artwork

# Get backdrops based of "BackdropImageTags" in the emby object.
def get_backdrops(item_id, tags, ServerId):
    backdrops = []

    for index, tag in enumerate(tags):
        artwork = "http://127.0.0.1:57578/embyimage-%s-%s-%s-Backdrop-%s" % (ServerId, item_id, index, tag)
        backdrops.append(artwork)

    return backdrops

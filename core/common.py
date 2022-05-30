from urllib.parse import quote, urlparse
from helper import utils, loghandler

EmbyArtworkKeys = ["Primary", "Art", "Banner", "Disc", "Logo", "Thumb"]
EmbyArtworkIDs = {"Primary": "p", "Art": "a", "Banner": "b", "Disc": "d", "Logo": "l", "Thumb": "t", "Backdrop": "B", "Chapter": "c"}
ImageTagsMapping = {
    "Series": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb', 'landscape')},
    "Season": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Episode": {'Primary': ('thumb', 'poster'), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Movie": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb', 'landscape')},
    "BoxSet": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb', 'landscape')},
    "Video": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "MusicArtist": {'Primary': ('thumb', 'poster'), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "MusicAlbum": {'Primary': ('thumb', 'poster'), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Audio": {'Primary': ('thumb', 'poster'), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "MusicVideo": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Photo": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "PhotoAlbum": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Folder": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "TvChannel": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb',)},
    "Trailer": {'Primary': ('poster',), "Art": ('clearart',), "Banner": ('banner',), "Disc": ('discart',), "Logo": ('clearlogo',), "Thumb": ('thumb', 'landscape')}
}
MediaTags = {}
LOG = loghandler.LOG('EMBY.core.common')

def library_check(item, EmbyServer, emby_db):
    if not item:
        return False

    item['ServerId'] = EmbyServer.server_id
    item['ExistingItem'] = emby_db.get_item_by_id(item['Id'])

    if not item['Library']:
        if item['ExistingItem']:
            library_id = item['ExistingItem'][6]
            library_name = Check_LibraryIsSynced(library_id, EmbyServer.library.Whitelist)

            if not library_name:
                return False
        else:  # Realtime Updates
            library_id = ""
            library_name = ""
            ancestors = EmbyServer.API.get_ancestors(item['Id'])

            if not ancestors:
                return False

            for ancestor in ancestors:
                if ancestor['Type'] == 'CollectionFolder':
                    library_name = Check_LibraryIsSynced(ancestor['Id'], EmbyServer.library.Whitelist)

                    if not library_name:
                        return False

                    library_id = ancestor['Id']
                    break

        if library_id:
            item['Library']['Id'] = library_id
            item['Library']['Name'] = library_name
            item['Library']['LibraryId_Name'] = "%s-%s" % (library_id, library_name)
            return True

        return False

    item['Library']['LibraryId_Name'] = "%s-%s" % (item['Library']['Id'], item['Library']['Name'])
    return True

def Check_LibraryIsSynced(library_id, Whitelist):
    Library_Name = ""

    for LibraryId, Value in list(Whitelist.items()):
        if library_id == LibraryId:
            Library_Name = Value[1]
            break

    if not Library_Name:
        LOG.info("Library %s is not synced. Skip update." % library_id)
        return False

    return Library_Name

def get_Bitrate_Codec(item):
    Bitrate = 0
    Codec = ""

    if item['Streams'][0]['Video']:
        if 'BitRate' in item['Streams'][0]['Video'][0]:
            Bitrate = item['Streams'][0]['Video'][0]['BitRate']
        else:
            LOG.warning("No Video Bitrate found: %s %s " % (item['Id'], item['Name']))

        if 'codec' in item['Streams'][0]['Video'][0]:
            Codec = item['Streams'][0]['Video'][0]['codec']
        else:
            LOG.warning("No Video Codec found: %s %s " % (item['Id'], item['Name']))
    else:
        LOG.warning("No Video Streams found: %s %s " % (item['Id'], item['Name']))

    return Bitrate, Codec

def get_filename(item, MediaID, API):
    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    Temp = item['FullPath'].lower()

    if Temp.startswith("plugin://"):
        return

    if Temp.endswith(".bdmv"):
        ForceNativeMode = True

    # Native
    if utils.useDirectPaths or ForceNativeMode:
        item['Filename'] = item['FullPath'].rsplit('\\', 1)[1] if '\\' in item['FullPath'] else item['FullPath'].rsplit('/', 1)[1]

        if MediaID == "a":
            return

        # Detect Multipart videos
        if 'PartCount' in item:
            if (item['PartCount']) >= 2:
                AdditionalParts = API.get_additional_parts(item['Id'])
                item['Filename'] = item['FullPath']
                item['StackTimes'] = str(item['RunTimeTicks'])

                for AdditionalItem in AdditionalParts['Items']:
                    Path = AdditionalItem['Path']
                    item['Filename'] = "%s , %s" % (item['Filename'], Path)

                    if 'RunTimeTicks' not in AdditionalItem:
                        AdditionalItem['RunTimeTicks'] = 0

                    RunTimePart = round(float((AdditionalItem['RunTimeTicks']) / 10000000.0), 6)
                    item['RunTimeTicks'] += RunTimePart
                    item['StackTimes'] = "%s,%s" % (item['StackTimes'], item['RunTimeTicks'])

                item['Filename'] = "stack://" + item['Filename']

        return

    # Addon
    item['Filename'] = utils.PathToFilenameReplaceSpecialCharecters(item['FullPath'])
    item['Filename'] = item['Filename'].replace("-", "_").replace(" ", "")

    if MediaID == "a":
        item['Filename'] = "a-%s-%s-%s" % (item['ServerId'], item['Id'], item['Filename'])
        return

    Bitrate, Codec = get_Bitrate_Codec(item)

    if Temp.endswith(".iso"):
        item['Filename'] = "i-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (item['ServerId'], item['Id'], item['MediaSources'][0]['Id'], item['KodiItemId'], item['KodiFileId'], Bitrate, item['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, "iso-container.mp4")
    else:
        item['Filename'] = "%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (MediaID, item['ServerId'], item['Id'], item['MediaSources'][0]['Id'], item['KodiItemId'], item['KodiFileId'], Bitrate, item['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, item['Filename'])

        # Detect Multipart videos
        if 'PartCount' in item:
            if (item['PartCount']) >= 2:
                AdditionalParts = API.get_additional_parts(item['Id'])
                item['StackTimes'] = str(item['RunTimeTicks'])
                StackedFilename = item['Path'] + item['Filename']

                for AdditionalItem in AdditionalParts['Items']:
                    AdditionalFilename = utils.PathToFilenameReplaceSpecialCharecters(AdditionalItem['Path'])
                    AdditionalFilename = AdditionalFilename.replace("-", "_").replace(" ", "")
                    get_streams(AdditionalItem)
                    Bitrate, Codec = get_Bitrate_Codec(item)
                    StackedFilename = "%s , %s%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (StackedFilename, item['Path'], MediaID, item['ServerId'], AdditionalItem['Id'], AdditionalItem['MediaSources'][0]['Id'], item['KodiPathId'], item['KodiFileId'], Bitrate, AdditionalItem['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, AdditionalFilename)

                    if 'RunTimeTicks' in AdditionalItem:
                        RunTimePart = round(float((AdditionalItem['RunTimeTicks'] or 0) / 10000000.0), 6)
                    else:
                        RunTimePart = 0

                    item['RunTimeTicks'] += RunTimePart
                    item['StackTimes'] = "%s,%s" % (item['StackTimes'], item['RunTimeTicks'])

                item['Filename'] = "stack://" + StackedFilename

def adjust_resume(resume_seconds):
    resume = 0

    if resume_seconds:
        resume = round(float(resume_seconds), 6)
        jumpback = int(utils.resumeJumpBack)

        if resume > jumpback:
            # To avoid negative bookmark
            resume -= jumpback

    return resume

def get_file_path(item, MediaID):
    if not 'Path' in item:
        return False

    item['FullPath'] = ""
    path = item['Path']

    # Addonmode replace filextensions
    if path.endswith('.strm'):
        path = path.replace('.strm', "")

        if 'Container' in item:
            if not path.endswith(item['Container']):
                path = "%s.%s" % (path, item['Container'])

    if not path:
        return False

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

    item['FullPath'] = path

    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    Temp = item['FullPath'].lower()
    item['Path'] = ""

    if 'Container' not in item:
        Container = ""
    else:
        Container = item['Container']

    if Temp.startswith("plugin://"):
        ForceNativeMode = True
    elif Container in ('dvd', 'bluray') and not Temp.endswith(".iso"):
        ForceNativeMode = True
    elif Temp.startswith("http"):
        UrlData = urlparse(item['FullPath'])
        UrlPath = quote(UrlData[2])
        item['FullPath'] = "%s://%s%s" % (UrlData[0], UrlData[1], UrlPath)

    if utils.useDirectPaths or ForceNativeMode:
        Temp2 = item['FullPath'].rsplit('\\', 1)[1] if '\\' in item['FullPath'] else item['FullPath'].rsplit('/', 1)[1]
        item['Path'] = item['FullPath'].replace(Temp2, "")
        PathChar = item['Path'][-1]

        if MediaID == "tvshows":
            item['PathParent'] = item['Path']
            item['Path'] = "%s%s" % (item['FullPath'], PathChar)
    else:
        if MediaID == "tvshows":
            item['PathParent'] = "http://127.0.0.1:57342/tvshows/%s/" % item['Library']['Id']
            item['Path'] = "http://127.0.0.1:57342/tvshows/%s/%s/" % (item['Library']['Id'], item['Id'])
        elif MediaID == "episodes":
            item['Path'] = "http://127.0.0.1:57342/tvshows/%s/%s/" % (item['Library']['Id'], item['SeriesId'])
        elif MediaID == "movies":
            item['Path'] = "http://127.0.0.1:57342/movies/%s/" % item['Library']['Id']
        elif MediaID == "musicvideos":
            item['Path'] = "http://127.0.0.1:57342/musicvideos/%s/" % item['Library']['Id']
        elif MediaID == "audio":
            item['Path'] = "http://127.0.0.1:57342/audio/%s/" % item['Library']['Id']

    if not item['FullPath']:  # Invalid Path
        LOG.error("Invalid path: %s" % item['Id'])
        LOG.debug("Invalid path: %s" % item)
        return False

    return True

# Get people (actor, director, etc) artwork.
def set_people(item, ServerId):
    item['Writers'] = []
    item['Directors'] = []
    item['Cast'] = []

    if "People" in item:
        for People in item['People']:
            if People['Type'] == "Writer":
                item['Writers'].append(People['Name'])
            elif People['Type'] == "Director":
                item['Directors'].append(People['Name'])
            elif People['Type'] == "Actor":
                item['Cast'].append(People['Name'])

            if item['Type'] == "MusicVideo":
                if 'PrimaryImageTag' in People:
                    People['imageurl'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s-%s" % (ServerId, People['Id'], People['PrimaryImageTag'], item['Library']['Id'])
                else:
                    People['imageurl'] = item['Library']['Id']
            else:
                if 'PrimaryImageTag' in People:
                    People['imageurl'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (ServerId, People['Id'], People['PrimaryImageTag'])
                else:
                    People['imageurl'] = None
    else:
        item['People'] = []

    item['Writers'] = " / ".join(item['Writers'])
    item['Directors'] = " / ".join(item['Directors'])

def SwopMediaSources(item):
    if len(item['MediaSources']) > 1:
        if item['MediaSources'][0].get('Video3DFormat'):
            LOG.info("3D detected, swap MediaSources %s" % item['Name'])
            Item0 = item['MediaSources'][0]
            Item1 = item['MediaSources'][1]
            item['MediaSources'][0] = Item1
            item['MediaSources'][1] = Item0

            if 'Path' in item['MediaSources'][0]:
                item['Path'] = item['MediaSources'][0]['Path']

def get_streams(item):
    item['Streams'] = []

    for IndexMediaSources, MediaSource in enumerate(item['MediaSources']):
        # TVChannel
        MediaSource['Path'] = MediaSource.get('Path', "")
        MediaSource['Size'] = MediaSource.get('Size', "")

        # Videos
        item['Streams'].append({'SubtitleLanguage': [], 'Subtitle': [], 'Audio': [], 'Video': [], 'Id': MediaSource['Id'], 'Index': IndexMediaSources, 'Path': MediaSource['Path'], 'Name': MediaSource['Name'], 'Size': MediaSource['Size']})
        HasExternalSubtitle = "0"

        for Index, Stream in enumerate(MediaSource['MediaStreams']):
            Codec = Stream.get('Codec')

            if Codec:
                Codec = Codec.lower()

            if Stream['Type'] == "Audio" or Stream['Type'] == "Default":
                item['Streams'][IndexMediaSources]['Audio'].append({'SampleRate': Stream.get('SampleRate'), 'BitRate': Stream.get('BitRate'), 'codec': Codec, 'channels': Stream.get('Channels'), 'language': Stream.get('Language'), 'Index': Index, 'DisplayTitle': Stream.get('DisplayTitle', "unknown")})
            elif Stream['Type'] == "Video":
                StreamData = {'codec': Codec, 'height': Stream.get('Height'), 'width': Stream.get('Width'), '3d': Stream.get('Video3DFormat'), 'BitRate': Stream.get('BitRate'), 'Index': Index, 'aspect': None}

                if "AspectRatio" in Stream:
                    width, height = Stream['AspectRatio'].split(':')
                    StreamData['aspect'] = round(float(width) / float(height), 6)

                item['Streams'][IndexMediaSources]['Video'].append(StreamData)
            elif Stream['Type'] == "Subtitle":
                Language = Stream.get('Language', "unknown")

                if Stream['Codec'] in ("srt", "ass"):
                    HasExternalSubtitle = "1"

                item['Streams'][IndexMediaSources]['Subtitle'].append({'Index': Index, 'language': Language, 'DisplayTitle': Stream.get('DisplayTitle', "unknown"), 'codec': Codec})
                item['Streams'][IndexMediaSources]['SubtitleLanguage'].append(Language)

        item['Streams'][IndexMediaSources]['HasExternalSubtitle'] = HasExternalSubtitle

    if not item['Streams'][0]['Audio']:
        LOG.debug("No Audio Streams found: %s %s" % (item['Name'], item.get('Path')))
        item['Streams'][0]['Audio'].append({'SampleRate': 0, 'BitRate': 0, 'codec': None, 'channels': 0, 'language': None, 'Index': None, 'DisplayTitle': None})

def set_RunTimeTicks(item):
    if 'RunTimeTicks' in item:
        item['RunTimeTicks'] = round(float((item['RunTimeTicks'] or 0) / 10000000.0), 6)
    else:
        item['RunTimeTicks'] = 0
        LOG.debug("No Runtime found: %s %s" % (item['Name'], item['Id']))

def set_overview(item):
    if 'Overview' in item:
        if item['Overview']:
            item['Overview'] = item['Overview'].replace("\"", "\'")
            item['Overview'] = item['Overview'].replace("\n", "[CR]")
            item['Overview'] = item['Overview'].replace("\r", " ")
            item['Overview'] = item['Overview'].replace("<br>", "[CR]")
    else:
        item['Overview'] = ""

    if 'CurrentProgram' in item: #TvChannel
        if 'Overview' in item['CurrentProgram']:
            if item['CurrentProgram']['Overview']:
                item['CurrentProgram']['Overview'] = item['CurrentProgram']['Overview'].replace("\"", "\'")
                item['CurrentProgram']['Overview'] = item['CurrentProgram']['Overview'].replace("\n", "[CR]")
                item['CurrentProgram']['Overview'] = item['CurrentProgram']['Overview'].replace("\r", " ")
                item['CurrentProgram']['Overview'] = item['CurrentProgram']['Overview'].replace("<br>", "[CR]")
        else:
            item['CurrentProgram']['Overview'] = ""

def set_mpaa(item):
    if 'OfficialRating' in item:
        if item['OfficialRating']:
            if item['OfficialRating'] in ("NR", "UR"):
                # Kodi seems to not like NR, but will accept Not Rated
                item['OfficialRating'] = "Not Rated"

            if "FSK-" in item['OfficialRating']:
                item['OfficialRating'] = item['OfficialRating'].replace("-", " ")

            if "GB-" in item['OfficialRating']:
                item['OfficialRating'] = item['OfficialRating'].replace("GB-", "UK:")
    else:
        item['OfficialRating'] = None

def set_userdata_update_data(item):
    if item['PlayCount'] == 0 or not item['Played']:
        item['PlayCount'] = None
    else:
        item['LastPlayedDate'] = item.get('LastPlayedDate', None)

    if 'LastPlayedDate' in item:
        item['LastPlayedDate'] = utils.convert_to_local(item['LastPlayedDate'])
    else:
        item['LastPlayedDate'] = None

    item['PlaybackPositionTicks'] = adjust_resume((item['PlaybackPositionTicks'] or 0) / 10000000.0)

def set_playstate(item):
    if item['UserData']['PlayCount'] == 0 or not item['UserData']['Played']:
        item['UserData']['PlayCount'] = None
    else:
        item['UserData']['LastPlayedDate'] = item['UserData'].get('LastPlayedDate', None)

    if 'LastPlayedDate' in item['UserData']:
        item['UserData']['LastPlayedDate'] = utils.convert_to_local(item['UserData']['LastPlayedDate'])
    else:
        item['UserData']['LastPlayedDate'] = None

def set_genres(item):
    if 'Genres' in item:
        if not item['Genres']:
            item['Genres'] = ["--NO INFO--"]
    else:
        item['Genres'] = ["--NO INFO--"]

    item['Genre'] = " / ".join(item['Genres'])

def set_videocommon(item, server_id):
    item['ProductionLocations'] = item.get('ProductionLocations', None)
    item['PresentationUniqueKey'] = item.get('PresentationUniqueKey', None)
    item['UserData']['PlaybackPositionTicks'] = adjust_resume((item['UserData']['PlaybackPositionTicks'] or 0) / 10000000.0)

    if 'DateCreated' in item:
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
    else:
        item['DateCreated'] = None

    if not 'Taglines' in item:
        item['Taglines'] = [None]
    else:
        if not item['Taglines']:
            item['Taglines'] = [None]

    set_genres(item)
    set_playstate(item)
    set_people(item, server_id)
    set_studios(item)
    set_overview(item)
    set_PremiereDate(item)
    set_KodiArtwork(item, server_id)

def set_PremiereDate(item):
    if 'PremiereDate' in item:
        item['PremiereDate'] = utils.convert_to_local(item['PremiereDate'], True)
    else:
        if 'ProductionYear' in item:
            item['PremiereDate'] = item['ProductionYear']
        else:
            item['PremiereDate'] = None
            item['ProductionYear'] = None

def set_studios(item):
    StudioNames = []

    if 'Studios' in item:
        if item['Studios']:
            for Studio in item['Studios']:
                if 'Name' not in Studio: # already cached
                    return
                StudioNames.append(Studio['Name'])

            item['Studios'] = StudioNames
        else:
            item['Studios'] = ["--NO INFO--"]
    else:
        item['Studios'] = ["--NO INFO--"]

    item['Studio'] = " / ".join(item['Studios'])

def set_chapters(item, server_id):
    item['ChapterInfo'] = []

    if 'Chapters' in item:
        if len(item['Chapters']) > 3:
            if "01" not in item['Chapters']:  # some magic to detect autogenerated chapters
                if int(item['Chapters'][1]["StartPositionTicks"]) % 3000000000 == 0 or int(item['Chapters'][3]["StartPositionTicks"]) % 3000000000 == 0:  # some more magic: modulo -> detect autogenerated chapters (2nd and 3rd chapter)
                    for index, Chapter in enumerate(item['Chapters']):
                        if "ImageTag" in Chapter:
                            ChapterImage = "http://127.0.0.1:57342/p-%s-%s-%s-c-%s" % (server_id, item['Id'], index, Chapter['ImageTag'])
                        else:
                            ChapterImage = None

                        item['ChapterInfo'].append({"StartPositionTicks": round(float((Chapter["StartPositionTicks"] or 0) / 10000000.0), 6), "Image": ChapterImage})

# Set Kodi artwork
def set_KodiArtwork(item, server_id):
    item['ParentLogoItemId'] = item.get('ParentLogoItemId', None)
    item['ParentLogoImageTag'] = item.get('ParentLogoImageTag', None)
    item['ParentThumbItemId'] = item.get('ParentThumbItemId', None)
    item['ParentThumbImageTag'] = item.get('ParentThumbImageTag', None)
    item['ParentBackdropItemId'] = item.get('ParentBackdropItemId', None)
    item['ParentBackdropImageTags'] = item.get('ParentBackdropImageTags', [])
    item['ImageTags'] = item.get('ImageTags', [])
    item['BackdropImageTags'] = item.get('BackdropImageTags', [])
    item['AlbumPrimaryImageTag'] = item.get('AlbumPrimaryImageTag', None)
    item['SeriesPrimaryImageTag'] = item.get('SeriesPrimaryImageTag', None)
    item['KodiArtwork'] = {'clearart': None, 'clearlogo': None, 'discart': None, 'landscape': None, 'thumb': None, 'banner': None, 'poster': None, 'fanart': {}}

    if 'Library' not in item:
        item['Library'] = {'Id': 0}

    # ImageTags
    for EmbyArtworkKey in EmbyArtworkKeys:
        EmbyArtworkId = None
        EmbyArtworkTag = ""

        if EmbyArtworkKey in item["ImageTags"]:
            if item["ImageTags"][EmbyArtworkKey]:
                EmbyArtworkTag = item["ImageTags"][EmbyArtworkKey]
                EmbyArtworkId = item['Id']

        if not EmbyArtworkId:
            if EmbyArtworkKey == "Primary":
                if item['SeriesPrimaryImageTag']:
                    EmbyArtworkTag = item['SeriesPrimaryImageTag']
                    EmbyArtworkId = item['SeriesId']
                elif item['AlbumPrimaryImageTag']:
                    EmbyArtworkTag = item['AlbumPrimaryImageTag']
                    EmbyArtworkId = item['AlbumId']

        if not EmbyArtworkId:
            EmbyParentArtworkKey = 'Parent%sItemTag' % EmbyArtworkKey

            if EmbyParentArtworkKey in item:
                if item[EmbyParentArtworkKey]:
                    EmbyArtworkTag = item[EmbyParentArtworkKey]
                    EmbyArtworkId = item['Parent%sItemId' % EmbyArtworkKey]

        if EmbyArtworkId:
            for KodiArtworkId in ImageTagsMapping[item["Type"]][EmbyArtworkKey]:
                item['KodiArtwork'][KodiArtworkId] = "http://127.0.0.1:57342/p-%s-%s-0-%s-%s" % (server_id, EmbyArtworkId, EmbyArtworkIDs[EmbyArtworkKey], EmbyArtworkTag)

    # BackdropImageTags
    if item['BackdropImageTags']:
        item['KodiArtwork']["fanart"]["fanart"] = "http://127.0.0.1:57342/p-%s-%s-0-B-%s" % (server_id, item['Id'], item['BackdropImageTags'][0])

        for index, EmbyArtworkTag in enumerate(item['BackdropImageTags'][1:], 1):
            item['KodiArtwork']["fanart"]["fanart%s" % index] = "http://127.0.0.1:57342/p-%s-%s-%s-B-%s" % (server_id, item['Id'], index, EmbyArtworkTag)
    elif item['ParentBackdropImageTags']:
        item['KodiArtwork']["fanart"]["fanart"] = "http://127.0.0.1:57342/p-%s-%s-0-B-%s" % (server_id, item['ParentBackdropItemId'], item['ParentBackdropImageTags'][0])

        for index, EmbyArtworkTag in enumerate(item['ParentBackdropImageTags'][1:], 1):
            item['KodiArtwork']["fanart"]["fanart%s" % index] = "http://127.0.0.1:57342/p-%s-%s-%s-B-%s" % (server_id, item['ParentBackdropItemId'], index, EmbyArtworkTag)

    # Fallbacks
    if not item['KodiArtwork']['thumb']:
        if item['KodiArtwork']['poster']:
            item['KodiArtwork']['thumb'] = item['KodiArtwork']['poster']

        if not item['KodiArtwork']['thumb'] and item['Type'] != "season":
            if 'fanart' in item['KodiArtwork']["fanart"]:
                item['KodiArtwork']['thumb'] = item['KodiArtwork']["fanart"]["fanart"]

def set_MusicVideoTracks(item):
    # Try to detect track number
    item['IndexNumber'] = None
    Temp = item['MediaSources'][0]['Name'][:4]  # e.g. 01 - Artist - Title
    Temp = Temp.split("-")

    if len(Temp) > 1:
        Track = Temp[0].strip()

        if Track.isnumeric():
            item['IndexNumber'] = str(int(Track))  # remove leading zero e.g. 01

def delete_ContentItemReferences(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType):
    video_db.delete_links_actors(KodiItemId, MediaType)
    video_db.delete_links_director(KodiItemId, MediaType)
    video_db.delete_links_writer(KodiItemId, MediaType)
    video_db.delete_links_countries(KodiItemId, MediaType)
    video_db.delete_links_studios(KodiItemId, MediaType)
    video_db.delete_links_tags(KodiItemId, MediaType)
    video_db.delete_uniqueids(KodiItemId, MediaType)
    video_db.delete_bookmark(KodiFileId)
    video_db.delete_streams(KodiFileId)
    video_db.delete_stacktimes(KodiFileId)
    video_db.common.delete_artwork(KodiItemId, MediaType)

    if EmbyItemId:
        emby_db.remove_item_streaminfos(EmbyItemId)

def set_ContentItem(item, video_db, emby_db, EmbyServer, MediaType, FileId):
    item['ProductionLocations'] = item.get('ProductionLocations', [])
    set_RunTimeTicks(item)
    get_streams(item)
    get_filename(item, FileId, EmbyServer.API)
    set_chapters(item, EmbyServer.server_id)
    set_videocommon(item, EmbyServer.server_id)
    emby_db.add_streamdata(item['Id'], item['Streams'])
    video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemId'], MediaType)
    video_db.add_bookmark_chapter(item['KodiFileId'], item['RunTimeTicks'], item['ChapterInfo'])
    video_db.add_bookmark_playstate(item['KodiFileId'], item['UserData']['PlaybackPositionTicks'], item['RunTimeTicks'])
    video_db.add_studios_and_links(item['Studios'], item['KodiItemId'], MediaType)
    video_db.add_people_and_links(item['People'], item['KodiItemId'], MediaType)
    video_db.add_countries_and_links(item['ProductionLocations'], item['KodiItemId'], MediaType)
    video_db.add_streams(item['KodiFileId'], item['Streams'][0]['Video'], item['Streams'][0]['Audio'], item['Streams'][0]['SubtitleLanguage'], item['RunTimeTicks'])

    if "StackTimes" in item:
        video_db.add_stacktimes(item['KodiFileId'], item['StackTimes'])

def delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType):
    delete_ContentItemReferences(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType)
    emby_db.remove_item(EmbyItemId)

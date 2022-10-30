from urllib.parse import quote, urlparse
from helper import utils, loghandler

EmbyArtworkIdShort = {"Primary": "p", "Art": "a", "Banner": "b", "Disc": "d", "Logo": "l", "Thumb": "t", "Backdrop": "B", "Chapter": "c", "SeriesPrimary": "p", "AlbumPrimary": "p", "ParentBackdrop": "B", "ParentThumb": "t", "ParentLogo": "l", "ParentBanner": "b", "AlbumArtists": "p", "ArtistItems": "p"}
MarkerTypeMapping = {"IntroStart": "Intro Start", "IntroEnd": "Intro End", "CreditsStart": "Credits"}
ImageTagsMappings = {
    "Series": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Backdrop", 'landscape')),
    "Season": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ('SeriesPrimary', 'poster'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo", 'clearlogo'), ("ParentBackdrop", 'fanart')),
    "Episode": (('Primary', 'thumb'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ("ParentLogo", 'clearlogo'), ("ParentBanner", 'banner'), ("ParentThumb", 'landscape'), ("ParentThumb", 'thumb'), ("ParentBackdrop", 'landscape'), ("ParentBackdrop", 'fanart'), ('Primary', 'landscape')),
    "Movie": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "BoxSet": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "Video": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "MusicArtist": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "MusicAlbum": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo" ,'clearlogo'), ("AlbumArtists", 'poster'), ("AlbumArtists", 'thumb'), ("AlbumArtists", 'fanart'), ("ArtistItems", 'poster'), ("ArtistItems", 'thumb'), ("ArtistItems", 'fanart')),
    "Audio": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('AlbumPrimary', 'poster'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo", 'clearlogo'), ("ParentBackdrop", 'fanart'), ("AlbumArtists", 'poster'), ("AlbumArtists", 'thumb'), ("AlbumArtists", 'fanart'), ("ArtistItems", 'poster'), ("ArtistItems", 'thumb'), ("ArtistItems", 'fanart')),
    "MusicVideo": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "Photo": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "PhotoAlbum": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "Folder": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "TvChannel": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "Trailer": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'))
}
MediaTags = {}
LOG = loghandler.LOG('EMBY.core.common')

def library_check(item, EmbyServer, emby_db):
    if not item:
        return False

    item['KodiItemIds'] = []
    item['KodiParentIds'] = []
    item['KodiFileIds'] = []
    item['UpdateItems'] = []
    item['Librarys'] = []
    item['ServerId'] = EmbyServer.server_id
    ExistingItem = emby_db.get_item_by_id(item['Id'])

    if ExistingItem:
        LibraryIds = ExistingItem[6].split(";")

        # Update existing items
        for LibraryId in LibraryIds:
            if LibraryId not in EmbyServer.Views.ViewItems:
                LOG.info("[ library_check remove library %s ]" % LibraryId)
                return False

            LibraryName = EmbyServer.Views.ViewItems[LibraryId][0]
            item['UpdateItems'].append(True)
            item['Librarys'].append({'Id': LibraryId, 'Name': LibraryName, 'LibraryId_Name': "%s-%s" % (LibraryId, LibraryName)})

        if ExistingItem[0]:
            item['KodiItemIds'] = str(ExistingItem[0]).split(";")
        else:
            item['KodiItemIds'] = len(LibraryIds) * [None]

        if ExistingItem[3]:
            item['KodiParentIds'] = str(ExistingItem[3]).split(";")
        else:
            item['KodiParentIds'] = len(LibraryIds) * [None]

        if ExistingItem[1]:
            item['KodiFileIds'] = str(ExistingItem[1]).split(";")
        else:
            item['KodiFileIds'] = len(LibraryIds) * [None]

        item['KodiPathId'] = ExistingItem[2]

        # New item (by different library id)
        if item['Library']: # Init sync
            if not item['Library']['Id'] in LibraryIds:
                item['KodiItemIds'].append(None)
                item['KodiParentIds'].append(None)
                item['KodiFileIds'].append(None)
                item['UpdateItems'].append(False)
                item['Librarys'].append({'Id': item['Library']['Id'], 'Name': item['Library']['Name'], 'LibraryId_Name': "%s-%s" % (item['Library']['Id'], item['Library']['Name'])})
    else:
        # New item
        if item['Library']: # Init sync
            item['KodiItemIds'].append(None)
            item['KodiParentIds'].append(None)
            item['KodiFileIds'].append(None)
            item['UpdateItems'].append(False)
            item['Librarys'].append({'Id': item['Library']['Id'], 'Name': item['Library']['Name'], 'LibraryId_Name': "%s-%s" % (item['Library']['Id'], item['Library']['Name'])})
        else: # realtime or startup sync
            for LibraryIdWhitelist, _ in list(EmbyServer.library.Whitelist.items()):
                if EmbyServer.API.get_Item_Basic(item['Id'], LibraryIdWhitelist, item['Type']):
                    LibraryName = Check_LibraryIsSynced(LibraryIdWhitelist, EmbyServer.library.Whitelist)
                    item['KodiItemIds'].append(None)
                    item['KodiParentIds'].append(None)
                    item['KodiFileIds'].append(None)
                    item['UpdateItems'].append(False)
                    item['Librarys'].append({'Id': LibraryIdWhitelist, 'Name': LibraryName, 'LibraryId_Name': "%s-%s" % (LibraryIdWhitelist, LibraryName)})

    if not item['Librarys']:
        return False

    item['LibraryIds'] = []

    for Library in item['Librarys']:
        item['LibraryIds'].append(Library['Id'])

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

def get_filename(item, MediaID, API, ItemIndex):
    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    Temp = item['FullPath'].lower()

    if Temp.startswith("plugin://"):
        item['Filename'] = Temp
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
    IsRemote = item['MediaSources'][0].get('IsRemote', False)

    if IsRemote:
        IsRemote = "1"
    else:
        IsRemote = "0"

    if Temp.endswith(".iso"):
        item['Filename'] = "i-%s-%s-%s-%s-%s-%s-%s-%s-%s-0-0-0-0-%s" % (item['ServerId'], item['Id'], item['MediaSources'][0]['Id'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], Bitrate, item['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, "iso-container.mp4")
    else:
        item['Filename'] = "%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-%s" % (MediaID, item['ServerId'], item['Id'], item['MediaSources'][0]['Id'], item['KodiItemIds'][ItemIndex], item['KodiFileIds'][ItemIndex], Bitrate, item['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, item['IntroStartPositionTicks'], item['IntroEndPositionTicks'], item['CreditsPositionTicks'], IsRemote, item['Filename'])

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
                    StackedFilename = "%s , %s%s-%s-%s-%s-%s-%s-%s-%s-%s-%s-0-0-0-0-%s" % (StackedFilename, item['Path'], MediaID, item['ServerId'], AdditionalItem['Id'], AdditionalItem['MediaSources'][0]['Id'], item['KodiPathId'], item['KodiFileIds'][ItemIndex], Bitrate, AdditionalItem['Streams'][0]['HasExternalSubtitle'], len(item['MediaSources']), Codec, AdditionalFilename)

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

def get_file_path(item, MediaID, ItemIndex):
    if not 'Path' in item:
        return False

    if 'MediaSources' in item:
        item['Path'] = item['MediaSources'][0]['Path']

    item['EmbyPath'] = item['Path']
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
            item['PathParent'] = "http://127.0.0.1:57342/tvshows/%s/" % item['LibraryIds'][ItemIndex]
            item['Path'] = "http://127.0.0.1:57342/tvshows/%s/%s/" % (item['LibraryIds'][ItemIndex], item['Id'])
        elif MediaID == "episodes":
            item['Path'] = "http://127.0.0.1:57342/tvshows/%s/%s/" % (item['LibraryIds'][ItemIndex], item['SeriesId'])
        elif MediaID == "movies":
            item['Path'] = "http://127.0.0.1:57342/movies/%s/" % item['LibraryIds'][ItemIndex]
        elif MediaID == "musicvideos":
            item['Path'] = "http://127.0.0.1:57342/musicvideos/%s/" % item['LibraryIds'][ItemIndex]
        elif MediaID == "audio":
            item['Path'] = "http://127.0.0.1:57342/audio/%s/" % item['LibraryIds'][ItemIndex]

    if not item['FullPath']:  # Invalid Path
        LOG.error("Invalid path: %s" % item['Id'])
        LOG.debug("Invalid path: %s" % item)
        return False

    return True

# Get people (actor, director, etc) artwork.
def set_people(item, ServerId, ItemIndex):
    item['Writers'] = []
    item['Directors'] = []
    item['Cast'] = []
    PeopleInvalidRecords = []

    if "People" in item:
        for Index, People in enumerate(item['People']):
            if 'Name' in People:
                if People['Type'] == "Writer":
                    item['Writers'].append(People['Name'])
                elif People['Type'] == "Director":
                    item['Directors'].append(People['Name'])
                elif People['Type'] == "Actor":
                    item['Cast'].append(People['Name'])

                if item['Type'] == "MusicVideo":
                    if 'PrimaryImageTag' in People:
                        People['imageurl'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s-%s" % (ServerId, People['Id'], People['PrimaryImageTag'], item['LibraryIds'][ItemIndex])
                    else:
                        People['imageurl'] = item['LibraryIds'][ItemIndex]
                else:
                    if 'PrimaryImageTag' in People:
                        People['imageurl'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (ServerId, People['Id'], People['PrimaryImageTag'])
                    else:
                        People['imageurl'] = ""
            else:
                PeopleInvalidRecords.append(Index)

        for PeopleInvalidRecord in PeopleInvalidRecords:
            del item['People'][PeopleInvalidRecord]
            LOG.warning("Invalid people detected: %s / %s" % (item['Id'], item['Name']))
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
    if 'MediaSources' not in item:
        return

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
                    AspectRatio = Stream['AspectRatio'].split(':')

                    if len(AspectRatio) != 2:
                        LOG.warning("AspectRatio detected by alternative method: %s / %s" % (item['Id'], item['Name']))
                        AspectRatio = Stream['AspectRatio'].split('/')

                    if len(AspectRatio) == 2 and AspectRatio[0].isnumeric() and AspectRatio[1].isnumeric() and float(AspectRatio[1]) > 0:
                        StreamData['aspect'] = round(float(AspectRatio[0]) / float(AspectRatio[1]), 6)
                    else:
                        LOG.warning("AspectRatio not detected: %s / %s" % (item['Id'], item['Name']))

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
        item['OfficialRating'] = ""

def set_trailer(item, EmbyServer):
    item['Trailer'] = ""

    if item['LocalTrailerCount']:
        for IntroLocal in EmbyServer.API.get_local_trailers(item['Id']):
            Filename = utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
            item['Trailer'] = "http://127.0.0.1:57342/V-%s-%s-%s-%s" % (EmbyServer.server_id, IntroLocal['Id'], IntroLocal['MediaSources'][0]['Id'], Filename)
            break

    if 'RemoteTrailers' in item:
        if item['RemoteTrailers']:
            try:
                item['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % item['RemoteTrailers'][0]['Url'].rsplit('=', 1)[1]
            except:
                LOG.error("Trailer not valid: %s" % item['Name'])

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

def set_videocommon(item, server_id, ItemIndex, DynamicNode=False):
    item['ProductionLocations'] = item.get('ProductionLocations', [])
    item['PresentationUniqueKey'] = item.get('PresentationUniqueKey', None)
    item['ProductionYear'] = item.get('ProductionYear', 0)
    item['UserData']['PlaybackPositionTicks'] = adjust_resume((item['UserData']['PlaybackPositionTicks'] or 0) / 10000000.0)

    if 'DateCreated' in item:
        item['DateCreated'] = utils.convert_to_local(item['DateCreated'])
    else:
        item['DateCreated'] = None

    if not 'Taglines' in item:
        item['Taglines'] = [""]
    else:
        if not item['Taglines']:
            item['Taglines'] = [""]

    set_genres(item)
    set_playstate(item)
    set_people(item, server_id, ItemIndex)
    set_studios(item)
    set_overview(item)
    set_PremiereDate(item)
    set_KodiArtwork(item, server_id, DynamicNode)

def set_PremiereDate(item):
    if 'PremiereDate' in item:
        item['PremiereDate'] = utils.convert_to_local(item['PremiereDate'], True)
    else:
        if 'ProductionYear' in item:
            item['PremiereDate'] = item['ProductionYear']
        else:
            item['PremiereDate'] = "0"
            item['ProductionYear'] = "0"

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
    item['IntroStartPositionTicks'] = 0
    item['IntroEndPositionTicks'] = 0
    item['CreditsPositionTicks'] = 0
    ChapterDuplicateCheck = []

    if 'Chapters' in item:
        for index, Chapter in enumerate(item['Chapters']):
            ChapterImage = None

            if "MarkerType" in Chapter and (Chapter['MarkerType'] == "IntroStart" or Chapter['MarkerType'] == "IntroEnd" or Chapter['MarkerType'] == "CreditsStart"):
                if Chapter['MarkerType'] == "IntroStart":
                    item['IntroStartPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)
                elif Chapter['MarkerType'] == "IntroEnd":
                    item['IntroEndPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)
                elif Chapter['MarkerType'] == "CreditsStart":
                    item['CreditsPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)

                if "ImageTag" in Chapter:
                    ChapterImage = "http://127.0.0.1:57342/p-%s-%s-%s-c-%s-%s" % (server_id, item['Id'], index, Chapter['ImageTag'], quote(MarkerTypeMapping[Chapter['MarkerType']]))
                else: # inject blank image, otherwise not possible to use text overlay (webservice.py)
                    ChapterImage = "http://127.0.0.1:57342/p-%s-%s-%s-c-%s-%s" % (server_id, item['Id'], index, "noimage", quote(MarkerTypeMapping[Chapter['MarkerType']]))
            else:
                if "Name" in Chapter:
                    if Chapter['Name'] == "Title Sequence" or Chapter['Name'] == "End Credits" or Chapter['Name'] == "Intro Start" or Chapter['Name'] == "Intro End":
                        if Chapter['Name'] == "Intro Start" and not item['IntroStartPositionTicks']:
                            item['IntroStartPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)
                        elif Chapter['Name'] == "Intro End" and not item['IntroEndPositionTicks']:
                            item['IntroEndPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)
                        elif Chapter['Name'] == "End Credits" and not item['CreditsPositionTicks']:
                            item['CreditsPositionTicks'] = int(int(Chapter["StartPositionTicks"]) / 10000000)
                    elif " 0" in Chapter['Name'] or int(Chapter["StartPositionTicks"]) % 3000000000 != 0: # embedded chapter
                        continue

                    if "ImageTag" in Chapter:
                        if "Name" in Chapter and "Chapter " not in Chapter['Name']:
                            ChapterImage = "http://127.0.0.1:57342/p-%s-%s-%s-c-%s-%s" % (server_id, item['Id'], index, Chapter['ImageTag'], quote(Chapter['Name']))
                        else:
                            ChapterImage = "http://127.0.0.1:57342/p-%s-%s-%s-c-%s" % (server_id, item['Id'], index, Chapter['ImageTag'])

            if Chapter["StartPositionTicks"] in ChapterDuplicateCheck:
                continue

            item['ChapterInfo'].append({"StartPositionTicks": round(float((Chapter["StartPositionTicks"] or 0) / 10000000.0), 6), "Image": ChapterImage})
            ChapterDuplicateCheck.append(Chapter["StartPositionTicks"])

# Set Kodi artwork
def set_KodiArtwork(item, server_id, DynamicNode):
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
    item['KodiArtwork'] = {'clearart': "", 'clearlogo': "", 'discart': "", 'landscape': "", 'thumb': "", 'banner': "", 'poster': "", 'fanart': {}}

    if item['Type'] in ImageTagsMappings:
        for ImageTagsMapping in ImageTagsMappings[item['Type']]:
            EmbyArtworkId = None
            EmbyArtworkTag = ""

            if ImageTagsMapping[0] in item["ImageTags"]:
                if item["ImageTags"][ImageTagsMapping[0]] and item["ImageTags"][ImageTagsMapping[0]] != "None":
                    EmbyArtworkTag = item["ImageTags"][ImageTagsMapping[0]]
                    EmbyArtworkId = item['Id']
            elif "%sImageTag" % ImageTagsMapping[0] in item:
                ImageTagKey = "%sImageTag" % ImageTagsMapping[0]

                if item[ImageTagKey] and item[ImageTagKey] != "None":
                    EmbyArtworkTag = item[ImageTagKey]

                    if "%sItemId" % ImageTagsMapping[0] in item:
                        EmbyArtworkId = item["%sItemId" % ImageTagsMapping[0]]
                    else:
                        if ImageTagsMapping[0] == "SeriesPrimary":
                            if "SeriesId" in item:
                                EmbyArtworkId = item["SeriesId"]
                        elif ImageTagsMapping[0] == "AlbumPrimary":
                            if "AlbumId" in item:
                                EmbyArtworkId = item["AlbumId"]
            elif ImageTagsMapping[0] == "ParentBanner":
                if "SeriesId" in item:
                    EmbyArtworkId = item["SeriesId"]
                    EmbyArtworkTag = ""
            elif ImageTagsMapping[0] == "AlbumArtists" and "AlbumArtists" in item and item["AlbumArtists"] and item["AlbumArtists"] != "None":
                EmbyArtworkId = item["AlbumArtists"][0]['Id']
                EmbyArtworkTag = 0
            elif ImageTagsMapping[0] == "ArtistItems" and "ArtistItems" in item and item["ArtistItems"] and item["ArtistItems"] != "None":
                EmbyArtworkId = item["ArtistItems"][0]['Id']
                EmbyArtworkTag = 0
            elif "%sImageTags" % ImageTagsMapping[0] in item:
                BackDropsKey = "%sImageTags" % ImageTagsMapping[0]
                EmbyBackDropsId = None

                if BackDropsKey == "ParentBackdropImageTags":
                    EmbyBackDropsId = item["ParentBackdropItemId"]
                else:
                    EmbyBackDropsId = item["Id"]

                if EmbyBackDropsId:
                    if item[BackDropsKey] and item[BackDropsKey] != "None":
                        if ImageTagsMapping[1] == "fanart":
                            if not "fanart" in item['KodiArtwork']["fanart"]:
                                item['KodiArtwork']["fanart"]["fanart"] = "http://127.0.0.1:57342/p-%s-%s-0-B-%s" % (server_id, EmbyBackDropsId, item[BackDropsKey][0])

                            for index, EmbyArtworkTag in enumerate(item[BackDropsKey][1:], 1):
                                if not "fanart%s" % index in item['KodiArtwork']["fanart"]:
                                    item['KodiArtwork']["fanart"]["fanart%s" % index] = "http://127.0.0.1:57342/p-%s-%s-%s-B-%s" % (server_id, EmbyBackDropsId, index, EmbyArtworkTag)
                        else:
                            if not item['KodiArtwork'][ImageTagsMapping[1]]:
                                item['KodiArtwork'][ImageTagsMapping[1]] = "http://127.0.0.1:57342/p-%s-%s-0-%s-%s" % (server_id, EmbyBackDropsId, EmbyArtworkIdShort[ImageTagsMapping[0]], item[BackDropsKey][0])

            if EmbyArtworkId:
                if ImageTagsMapping[1] == "fanart":
                    if not "fanart" in item['KodiArtwork']["fanart"]:
                        item['KodiArtwork']["fanart"]["fanart"] = "http://127.0.0.1:57342/p-%s-%s-0-%s-%s" % (server_id, EmbyArtworkId, EmbyArtworkIdShort[ImageTagsMapping[0]], EmbyArtworkTag)
                else:
                    if not item['KodiArtwork'][ImageTagsMapping[1]]:
                        item['KodiArtwork'][ImageTagsMapping[1]] = "http://127.0.0.1:57342/p-%s-%s-0-%s-%s" % (server_id, EmbyArtworkId, EmbyArtworkIdShort[ImageTagsMapping[0]], EmbyArtworkTag)


    if utils.AssignEpisodePostersToTVShowPoster:
        if item['Type'] == "Episode" and 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
            item['KodiArtwork']['poster'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item["SeriesId"], item["SeriesPrimaryImageTag"])

    if DynamicNode:
        if item['Type'] == "Episode":
            if 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
                item['KodiArtwork']['tvshow.poster'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item["SeriesId"], item["SeriesPrimaryImageTag"])

            if 'ParentThumbItemId' in item and "ParentThumbImageTag" in item and item["ParentThumbImageTag"] and item["ParentThumbImageTag"] != "None":
                item['KodiArtwork']['tvshow.thumb'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item["ParentThumbItemId"], item["ParentThumbImageTag"])

            if 'ParentLogoItemId' in item and "ParentLogoImageTag" in item and item["ParentLogoImageTag"] and item["ParentLogoImageTag"] != "None":
                item['KodiArtwork']['tvshow.clearlogo'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item["ParentLogoItemId"], item["ParentLogoImageTag"])

            if 'ParentBackdropItemId' in item and "ParentBackdropImageTags" in item and item["ParentBackdropImageTags"]:
                item['KodiArtwork']['tvshow.fanart'] = "http://127.0.0.1:57342/p-%s-%s-0-p-%s" % (server_id, item["ParentBackdropItemId"], item["ParentBackdropImageTags"][0])

def set_MusicVideoTracks(item):
    # Try to detect track number
    item['IndexNumber'] = -1
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

def set_ContentItem(item, video_db, emby_db, EmbyServer, MediaType, FileId, ItemIndex):
    set_RunTimeTicks(item)
    get_streams(item)
    set_chapters(item, EmbyServer.server_id)
    get_filename(item, FileId, EmbyServer.API, ItemIndex)
    set_videocommon(item, EmbyServer.server_id, ItemIndex)
    emby_db.add_streamdata(item['Id'], item['Streams'])
    video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_bookmark_chapter(item['KodiFileIds'][ItemIndex], item['RunTimeTicks'], item['ChapterInfo'])
    video_db.add_bookmark_playstate(item['KodiFileIds'][ItemIndex], item['UserData']['PlaybackPositionTicks'], item['RunTimeTicks'])
    video_db.add_studios_and_links(item['Studios'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_people_and_links(item['People'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_countries_and_links(item['ProductionLocations'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_streams(item['KodiFileIds'][ItemIndex], item['Streams'][0]['Video'], item['Streams'][0]['Audio'], item['Streams'][0]['SubtitleLanguage'], item['RunTimeTicks'])

    if "StackTimes" in item:
        video_db.add_stacktimes(item['KodiFileIds'][ItemIndex], item['StackTimes'])

def delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType, EmbyLibraryId):
    delete_ContentItemReferences(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType)
    emby_db.remove_item(EmbyItemId, EmbyLibraryId)

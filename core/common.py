from urllib.parse import quote, urlparse
import xbmc
from helper import utils

MediaTypeMapping = {"movie": "m", "episode": "e", "musicvideo": "M", "picture": "p", "audio": "a", "tvchannel": "t", "specialaudio": "A", "specialvideo": "V", "video": "v", "channel": "c"}
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

def library_check(item, EmbyServer, emby_db, EmbyType=""):
    if not item or "Id" not in item:
        xbmc.log(f"EMBY.core.common: library_check: {item}", 3)
        return False

    item['KodiItemIds'] = []
    item['KodiParentIds'] = []
    item['KodiFileIds'] = []
    item['UpdateItems'] = []
    item['Librarys'] = []
    item['ServerId'] = EmbyServer.ServerData['ServerId']
    ExistingItem = emby_db.get_item_by_id(item['Id'])

    if EmbyType and ExistingItem and ExistingItem[5] != EmbyType:
        xbmc.log(f"EMBY.core.common: No matching content type: {EmbyType} / {ExistingItem[5]}", 2) # LOGWARNING
        ExistingItem = ()

    if ExistingItem:
        LibraryIds = ExistingItem[6].split(";")

        # Update existing items
        for LibraryId in LibraryIds:
            if LibraryId not in EmbyServer.Views.ViewItems:
                xbmc.log(f"EMBY.core.common: [ library_check remove library {LibraryId} ]", 1) # LOGINFO
                return False

            LibraryName = EmbyServer.Views.ViewItems[LibraryId][0]
            item['UpdateItems'].append(True)
            item['Librarys'].append({'Id': LibraryId, 'Name': LibraryName, 'LibraryId_Name': f"{LibraryId}-{LibraryName}"})

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
        if 'Library' in item:
            if not item['Library']['Id'] in LibraryIds:
                item['KodiItemIds'].append(None)
                item['KodiParentIds'].append(None)
                item['KodiFileIds'].append(None)
                item['UpdateItems'].append(False)
                item['Librarys'].append({'Id': item['Library']['Id'], 'Name': item['Library']['Name'], 'LibraryId_Name': f"{item['Library']['Id']}-{item['Library']['Name']}"})

        item['LibraryIds'] = []

        for Library in item['Librarys']:
            item['LibraryIds'].append(Library['Id'])
    else:
        # New item
        if 'Library' not in item:
            return False

        item['KodiItemIds'].append(None)
        item['KodiParentIds'].append(None)
        item['KodiFileIds'].append(None)
        item['UpdateItems'].append(False)
        item['Librarys'].append({'Id': item['Library']['Id'], 'Name': item['Library']['Name'], 'LibraryId_Name': f"{item['Library']['Id']}-{item['Library']['Name']}"})
        item['LibraryIds'] = [item['Library']['Id']]

    return True

def get_Bitrate_Codec(item, StreamType):
    Bitrate = 0
    Codec = ""

    if item['Streams'][0][StreamType]:
        if 'BitRate' in item['Streams'][0][StreamType][0]:
            Bitrate = item['Streams'][0][StreamType][0]['BitRate']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Bitrate found: {item['Id']} {item['Name']}", 2) # LOGWARNING

        if 'codec' in item['Streams'][0][StreamType][0]:
            Codec = item['Streams'][0][StreamType][0]['codec']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Codec found: {item['Id']} {item['Name']}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.core.common: No Streams Bitrate found: {item['Id']} {item['Name']}", 2) # LOGWARNING

    return Bitrate, Codec

def get_filename(item, API, ItemIndex, MediaType):
    # Native Kodi plugins starts with plugin:// -> If native Kodi plugin, drop the link directly in Kodi DB. Emby server cannot play Kodi-Plugins
    ForceNativeMode = False
    MediaID = MediaTypeMapping[MediaType]
    Temp = item['FullPath'].lower()

    if Temp.startswith("plugin://"):
        item['Filename'] = item['FullPath']
        return

    Container = item.get('Container', "")

    if Temp.endswith(".bdmv") or Temp.endswith(".iso") or Container in ('dvd', 'bluray'):
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
                    item['Filename'] = f"{item['Filename']} , {Path}"

                    if 'RunTimeTicks' not in AdditionalItem:
                        AdditionalItem['RunTimeTicks'] = 0

                    RunTimePart = round(float(AdditionalItem.get('RunTimeTicks', 0) / 10000000.0), 6)
                    item['RunTimeTicks'] += RunTimePart
                    item['StackTimes'] = f"{item['StackTimes']},{item['RunTimeTicks']}"

                item['Filename'] = f"stack://{item['Filename']}"

        return

    # Addon
    HasSpecials = ""

    if 'SpecialFeatureCount' in item:
        if int(item['SpecialFeatureCount']):
            HasSpecials = "s"

    item['Filename'] = utils.PathToFilenameReplaceSpecialCharecters(item['FullPath'])
    item['Filename'] = item['Filename'].replace("-", "_").replace(" ", "")

    if MediaID == "a":
        item['Filename'] = f"a-{item['Id']}-{item['Filename']}"
        return

    VideoBitrate, VideoCodec = get_Bitrate_Codec(item, "Video")
    AudioBitrate, AudioCodec = get_Bitrate_Codec(item, "Audio")
    IsRemote = item['MediaSources'][0].get('IsRemote', False)

    if IsRemote:
        IsRemote = "1"
    else:
        IsRemote = "0"

    item['Filename'] = f"{MediaID}-{item['Id']}-{item['MediaSources'][0]['Id']}-{item['KodiItemIds'][ItemIndex]}-{item['KodiFileIds'][ItemIndex]}-{item['Streams'][0]['HasExternalSubtitle']}-{len(item['MediaSources'])}-{item['IntroStartPositionTicks']}-{item['IntroEndPositionTicks']}-{item['CreditsPositionTicks']}-{IsRemote}-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{HasSpecials}-{item['Filename']}"

    # Detect Multipart videos
    if 'PartCount' in item:
        if (item['PartCount']) >= 2:
            AdditionalParts = API.get_additional_parts(item['Id'])
            item['StackTimes'] = str(item['RunTimeTicks'])
            StackedFilename = f"{item['Path']}{item['Filename']}"

            for AdditionalItem in AdditionalParts['Items']:
                AdditionalFilename = utils.PathToFilenameReplaceSpecialCharecters(AdditionalItem['Path'])
                AdditionalFilename = AdditionalFilename.replace("-", "_").replace(" ", "")
                get_streams(AdditionalItem)
                VideoBitrate, VideoCodec = get_Bitrate_Codec(item, "Video")
                AudioBitrate, AudioCodec = get_Bitrate_Codec(item, "Audio")
                StackedFilename = f"{StackedFilename} , {item['Path']}{MediaID}-{AdditionalItem['Id']}-{AdditionalItem['MediaSources'][0]['Id']}-{item['KodiPathId']}-{item['KodiFileIds'][ItemIndex]}-{AdditionalItem['Streams'][0]['HasExternalSubtitle']}-{len(item['MediaSources'])}-0-0-0-0-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{AdditionalFilename}"

                if 'RunTimeTicks' in AdditionalItem:
                    RunTimePart = round(float(AdditionalItem.get('RunTimeTicks', 0) / 10000000.0), 6)
                else:
                    RunTimePart = 0

                item['RunTimeTicks'] += RunTimePart
                item['StackTimes'] = f"{item['StackTimes']},{item['RunTimeTicks']}"

            item['Filename'] = f"stack://{StackedFilename}"

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
                path = f"{path}.{item['Container']}"

    if not path:
        return False

    if path.startswith('\\\\'):
        path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

    if 'Container' in item:
        if item['Container'] == 'dvd':
            path = f"{path}/VIDEO_TS/VIDEO_TS.IFO"
        elif item['Container'] == 'bluray':
            path = f"{path}/BDMV/index.bdmv"

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
    Container = item.get('Container', "")

    if Temp.startswith("plugin://") or Temp.endswith(".bdmv") or Temp.endswith(".iso") or Container in ('dvd', 'bluray'):
        ForceNativeMode = True
    elif Temp.startswith("http"):
        UrlData = urlparse(item['FullPath'])
        UrlPath = quote(UrlData[2])
        item['FullPath'] = f"{UrlData[0]}://{UrlData[1]}{UrlPath}"

    if utils.useDirectPaths or ForceNativeMode:
        Temp2 = item['FullPath'].rsplit('\\', 1)[1] if '\\' in item['FullPath'] else item['FullPath'].rsplit('/', 1)[1]
        item['Path'] = item['FullPath'].replace(Temp2, "")
        PathChar = item['Path'][-1]

        if MediaID == "tvshows":
            item['PathParent'] = item['Path']
            item['Path'] = f"{item['FullPath']}{PathChar}"
    else:
        if MediaID == "tvshows":
            item['PathParent'] = f"{utils.AddonModePath}tvshows/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/"
            item['Path'] = f"{utils.AddonModePath}tvshows/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/{item['Id']}/"
        elif MediaID == "episodes":
            item['Path'] = f"{utils.AddonModePath}tvshows/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/{item['SeriesId']}/{item['Id']}/"
        elif MediaID == "movies":
            item['Path'] = f"{utils.AddonModePath}movies/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/"
        elif MediaID == "musicvideos":
            item['Path'] = f"{utils.AddonModePath}musicvideos/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/"
        elif MediaID == "audio":
            item['Path'] = f"{utils.AddonModePath}audio/{item['ServerId']}/{item['LibraryIds'][ItemIndex]}/"

    if not item['FullPath']:  # Invalid Path
        xbmc.log(f"EMBY.core.common: Invalid path: {item['Id']}", 3) # LOGERROR
        xbmc.log(f"EMBY.core.common: Invalid path: {item}", 0) # LOGDEBUG
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
            People['LibraryId'] = item['LibraryIds'][ItemIndex]

            if 'Name' in People:
                if People['Type'] == "Writer":
                    item['Writers'].append(People['Name'])
                elif People['Type'] == "Director":
                    item['Directors'].append(People['Name'])
                elif People['Type'] == "Actor":
                    item['Cast'].append(People['Name'])

                if 'PrimaryImageTag' in People:
                    People['imageurl'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{People['Id']}-0-p-{People['PrimaryImageTag']}-{item['LibraryIds'][ItemIndex]}"
                else:
                    People['imageurl'] = f"p-{People['Id']}-0-p-0-{item['LibraryIds'][ItemIndex]}"
            else:
                PeopleInvalidRecords.append(Index)

        for PeopleInvalidRecord in PeopleInvalidRecords[::-1]: # reversed order
            del item['People'][PeopleInvalidRecord]
            xbmc.log(f"EMBY.core.common: Invalid people detected: {item['Id']} / {item['Name']}", 2) # LOGWARNING
    else:
        item['People'] = []

def SwopMediaSources(item):
    if len(item['MediaSources']) > 1:
        if item['MediaSources'][0].get('Video3DFormat'):
            xbmc.log(f"EMBY.core.common: 3D detected, swap MediaSources {item['Name']}", 1) # LOGINFO
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
        item['Streams'].append({'Subtitle': [], 'Audio': [], 'Video': [], 'Id': MediaSource['Id'], 'Index': IndexMediaSources, 'Path': MediaSource['Path'], 'Name': MediaSource['Name'], 'Size': MediaSource['Size']})
        HasExternalSubtitle = "0"

        for Index, Stream in enumerate(MediaSource['MediaStreams']):
            Codec = Stream.get('Codec')

            if not Codec:
                Codec = Stream.get('CodecTag', "")

            if Codec:
                Codec = Codec.lower().replace("-", "")

            if Codec == "dts":
                Profile = Stream.get('Profile', "").lower()

                if Profile == "dts-hd ma":
                    Codec = "dtshd_ma"
                elif Profile == "dts-hd hra":
                    Codec = "dtshd_hra"

            if Stream['Type'] == "Audio" or Stream['Type'] == "Default":
                item['Streams'][IndexMediaSources]['Audio'].append({'SampleRate': Stream.get('SampleRate', 0), 'BitRate': Stream.get('BitRate', 0), 'codec': Codec, 'channels': Stream.get('Channels', 0), 'language': Stream.get('Language', ""), 'Index': Index, 'DisplayTitle': Stream.get('DisplayTitle', "unknown")})
            elif Stream['Type'] == "Video":
                StreamData = {'language': Stream.get('Language', ""),'hdrtype': '', 'codec': Codec, 'height': Stream.get('Height', 0), 'width': Stream.get('Width', 0), '3d': Stream.get('Video3DFormat', ""), 'BitRate': Stream.get('BitRate', 0), 'Index': Index, 'aspect': 0.0}

                CodecTag = Stream.get('CodecTag', "")

                if CodecTag == "dvhe":
                    StreamData['hdrtype'] = "dolbyvision"
                elif CodecTag == "hvc1":
                    StreamData['hdrtype'] = "hdr10"

                if "AspectRatio" in Stream:
                    AspectRatio = Stream['AspectRatio'].split(':')

                    if len(AspectRatio) != 2:
                        xbmc.log(f"EMBY.core.common: AspectRatio detected by alternative method: {item['Id']} / {item['Name']}", 2) # LOGWARNING
                        AspectRatio = Stream['AspectRatio'].split('/')

                    if len(AspectRatio) == 2 and AspectRatio[0].isnumeric() and AspectRatio[1].isnumeric() and float(AspectRatio[1]) > 0:
                        StreamData['aspect'] = round(float(AspectRatio[0]) / float(AspectRatio[1]), 6)
                    else:
                        xbmc.log(f"EMBY.core.common: AspectRatio not detected: {item['Id']} / {item['Name']}", 2) # LOGWARNING

                item['Streams'][IndexMediaSources]['Video'].append(StreamData)
            elif Stream['Type'] == "Subtitle":
                IsExternal = Stream.get('IsExternal', False)

                if IsExternal:
                    HasExternalSubtitle = "1"

                item['Streams'][IndexMediaSources]['Subtitle'].append({'Index': Index, 'language': Stream.get('Language', ""), 'DisplayTitle': Stream.get('DisplayTitle', "unknown"), 'codec': Codec, 'external': IsExternal})

        item['Streams'][IndexMediaSources]['HasExternalSubtitle'] = HasExternalSubtitle

def set_RunTimeTicks(item):
    if 'RunTimeTicks' in item:
        item['RunTimeTicks'] = round(float(item.get('RunTimeTicks', 0) / 10000000.0), 6)
    else:
        item['RunTimeTicks'] = 0
        xbmc.log(f"EMBY.core.common: No Runtime found: {item['Name']} {item['Id']}", 0) # LOGDEBUG

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

    if 'LocalTrailerCount' in item and item['LocalTrailerCount']:
        for IntroLocal in EmbyServer.API.get_local_trailers(item['Id']):
            Filename = utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
            item['Trailer'] = f"{utils.AddonModePath}dynamic/{item['ServerId']}/V-{IntroLocal['Id']}-{IntroLocal['MediaSources'][0]['Id']}-{Filename}"
            return

    if 'RemoteTrailers' in item and item['RemoteTrailers']:
        try:
            item['Trailer'] = f"plugin://plugin.video.youtube/play/?video_id={item['RemoteTrailers'][0]['Url'].rsplit('=', 1)[1]}"
        except:
            xbmc.log(f"EMBY.core.common: Trailer not valid: {item['Name']}", 3) # LOGERROR

def set_playstate(UserData):
    if not UserData['Played']:
        UserData['PlayCount'] = 0
    else:
        if not UserData.get('PlayCount', 0): # Workaround for Emby server bug -> UserData {'PlaybackPositionTicks': 0, 'PlayCount': 0, 'IsFavorite': False, 'Played': True}
            UserData['PlayCount'] = 1

        UserData['LastPlayedDate'] = UserData.get('LastPlayedDate', "")

    if 'LastPlayedDate' in UserData:
        UserData['LastPlayedDate'] = utils.convert_to_local(UserData['LastPlayedDate'])
    else:
        UserData['LastPlayedDate'] = ""

    UserData['PlaybackPositionTicks'] = adjust_resume(UserData.get('PlaybackPositionTicks', 0) / 10000000.0)

def set_genres(item):
    if 'Genres' in item:
        if not item['Genres']:
            item['Genres'] = ["--NO INFO--"]
    else:
        item['Genres'] = ["--NO INFO--"]

    item['Genre'] = " / ".join(item['Genres'])

def set_videocommon(item, ServerId, ItemIndex, DynamicNode=False):
    item['ProductionLocations'] = item.get('ProductionLocations', [])
    item['PresentationUniqueKey'] = item.get('PresentationUniqueKey', "")
    item['ProductionYear'] = item.get('ProductionYear', 0)

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
    set_playstate(item['UserData'])
    set_people(item, ServerId, ItemIndex)
    set_studios(item)
    set_overview(item)
    set_PremiereDate(item)
    set_KodiArtwork(item, ServerId, DynamicNode)

def set_PremiereDate(item):
    if 'PremiereDate' in item:
        item['PremiereDate'] = utils.convert_to_local(item['PremiereDate'], True)
    else:
        if 'ProductionYear' in item and item['ProductionYear']:
            item['PremiereDate'] = str(item['ProductionYear'])
        else:
            item['PremiereDate'] = ""
            item['ProductionYear'] = 0

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

def set_chapters(item, ServerId):
    Chapters = {}
    item['ChapterInfo'] = []
    item['IntroStartPositionTicks'] = 0
    item['IntroEndPositionTicks'] = 0
    item['CreditsPositionTicks'] = 0

    if 'Chapters' in item:
        MarkerLabel = ""

        for index, Chapter in enumerate(item['Chapters']):
            Chapter["StartPositionTicks"] = round(float(Chapter.get("StartPositionTicks", 0) / 10000000))

            if "MarkerType" in Chapter and (Chapter['MarkerType'] == "IntroStart" or Chapter['MarkerType'] == "IntroEnd" or Chapter['MarkerType'] == "CreditsStart"):
                if Chapter['MarkerType'] == "IntroStart":
                    item['IntroStartPositionTicks'] = Chapter["StartPositionTicks"]
                elif Chapter['MarkerType'] == "IntroEnd":
                    item['IntroEndPositionTicks'] = Chapter["StartPositionTicks"]
                elif Chapter['MarkerType'] == "CreditsStart":
                    item['CreditsPositionTicks'] = Chapter["StartPositionTicks"]

                MarkerLabel = quote(MarkerTypeMapping[Chapter['MarkerType']])

                if "ImageTag" in Chapter:
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-{Chapter['ImageTag']}-{MarkerLabel}"
                else: # inject blank image, otherwise not possible to use text overlay (webservice.py)
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-noimage-{MarkerLabel}"
            else:
                if "Name" in Chapter:
                    Chapter['Name'] = Chapter['Name'].replace("-", " ")

                    if Chapter['Name'] == "Title Sequence" or Chapter['Name'] == "End Credits" or Chapter['Name'] == "Intro Start" or Chapter['Name'] == "Intro End":
                        if Chapter['Name'] == "Intro Start" and not item['IntroStartPositionTicks']:
                            item['IntroStartPositionTicks'] = Chapter["StartPositionTicks"]
                        elif Chapter['Name'] == "Intro End" and not item['IntroEndPositionTicks']:
                            item['IntroEndPositionTicks'] = Chapter["StartPositionTicks"]
                        elif Chapter['Name'] == "End Credits" and not item['CreditsPositionTicks']:
                            item['CreditsPositionTicks'] = Chapter["StartPositionTicks"]

                        MarkerLabel = quote(Chapter['Name'])
                    elif " 0" in Chapter['Name'] or Chapter["StartPositionTicks"] % 300 != 0: # embedded chapter
                        continue
                else:
                    Chapter["Name"] = "unknown"

                if "ImageTag" in Chapter:
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-{Chapter['ImageTag']}-{quote(Chapter['Name'])}"
                else:
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-noimage-{quote(Chapter['Name'])}"

            if not Chapter["StartPositionTicks"] in Chapters:
                Chapters[Chapter["StartPositionTicks"]] = ChapterImage
            else:
                # replace existing chapter label with marker label
                if MarkerLabel:
                    Data = Chapters[Chapter["StartPositionTicks"]].split("-")
                    Data[5] = MarkerLabel
                    Chapters[Chapter["StartPositionTicks"]] = "-".join(Data)

    for StartPositionTicks, ChapterImage in list(Chapters.items()):
        item['ChapterInfo'].append({"StartPositionTicks": StartPositionTicks, "Image": ChapterImage})

# Set Kodi artwork
def set_KodiArtwork(item, ServerId, DynamicNode):
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
            elif f"{ImageTagsMapping[0]}ImageTag" in item:
                ImageTagKey = f"{ImageTagsMapping[0]}ImageTag"

                if item[ImageTagKey] and item[ImageTagKey] != "None":
                    EmbyArtworkTag = item[ImageTagKey]

                    if f"{ImageTagsMapping[0]}ItemId" in item:
                        EmbyArtworkId = item[f"{ImageTagsMapping[0]}ItemId"]
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
                EmbyArtworkTag = ""
            elif ImageTagsMapping[0] == "ArtistItems" and "ArtistItems" in item and item["ArtistItems"] and item["ArtistItems"] != "None":
                EmbyArtworkId = item["ArtistItems"][0]['Id']
                EmbyArtworkTag = ""
            elif f"{ImageTagsMapping[0]}ImageTags" in item:
                BackDropsKey = f"{ImageTagsMapping[0]}ImageTags"

                if BackDropsKey == "ParentBackdropImageTags":
                    EmbyBackDropsId = item["ParentBackdropItemId"]
                else:
                    EmbyBackDropsId = item["Id"]

                if EmbyBackDropsId:
                    if item[BackDropsKey] and item[BackDropsKey] != "None":
                        if ImageTagsMapping[1] == "fanart":
                            if not "fanart" in item['KodiArtwork']["fanart"]:
                                item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-B-{item[BackDropsKey][0]}"

                            for index, EmbyArtworkTag in enumerate(item[BackDropsKey][1:], 1):
                                if not f"fanart{index}" in item['KodiArtwork']["fanart"]:
                                    item['KodiArtwork']["fanart"][f"fanart{index}"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-{index}-B-{EmbyArtworkTag}"
                        else:
                            if not item['KodiArtwork'][ImageTagsMapping[1]]:
                                item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{item[BackDropsKey][0]}"

            if EmbyArtworkId:
                if ImageTagsMapping[1] == "fanart":
                    if not "fanart" in item['KodiArtwork']["fanart"]:
                        item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}"
                else:
                    if not item['KodiArtwork'][ImageTagsMapping[1]]:
                        item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}"

    if utils.AssignEpisodePostersToTVShowPoster:
        if item['Type'] == "Episode" and 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
            item['KodiArtwork']['poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['SeriesId']}-0-p-{item['SeriesPrimaryImageTag']}"

    if DynamicNode:
        if item['Type'] == "Episode":
            if 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
                item['KodiArtwork']['tvshow.poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['SeriesId']}-0-p-{item['SeriesPrimaryImageTag']}"

            if 'ParentThumbItemId' in item and "ParentThumbImageTag" in item and item["ParentThumbImageTag"] and item["ParentThumbImageTag"] != "None":
                item['KodiArtwork']['tvshow.thumb'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentThumbItemId']}-0-p-{item['ParentThumbImageTag']}"

            if 'ParentLogoItemId' in item and "ParentLogoImageTag" in item and item["ParentLogoImageTag"] and item["ParentLogoImageTag"] != "None":
                item['KodiArtwork']['tvshow.clearlogo'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentLogoItemId']}-0-p-{item['ParentLogoImageTag']}"

            if 'ParentBackdropItemId' in item and "ParentBackdropImageTags" in item and item["ParentBackdropImageTags"]:
                item['KodiArtwork']['tvshow.fanart'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentBackdropItemId']}-0-p-{item['ParentBackdropImageTags'][0]}"

def set_MusicVideoTracks(item):
    # Try to detect track number
    item['IndexNumber'] = -1
    Temp = item['MediaSources'][0]['Name'][:4]  # e.g. 01 - Artist - Title
    Temp = Temp.split("-")

    if len(Temp) > 1:
        Track = Temp[0].strip()

        if Track.isnumeric():
            item['IndexNumber'] = int(Track)  # remove leading zero e.g. 01

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

def set_ContentItem(item, video_db, emby_db, EmbyServer, MediaType, ItemIndex):
    set_RunTimeTicks(item)
    get_streams(item)
    set_chapters(item, EmbyServer.ServerData['ServerId'])
    get_filename(item, EmbyServer.API, ItemIndex, MediaType)
    set_videocommon(item, EmbyServer.ServerData['ServerId'], ItemIndex)
    emby_db.add_streamdata(item['Id'], item['Streams'])
    video_db.common.add_artwork(item['KodiArtwork'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_bookmark_chapter(item['KodiFileIds'][ItemIndex], item['RunTimeTicks'], item['ChapterInfo'])
    video_db.add_bookmark_playstate(item['KodiFileIds'][ItemIndex], item['UserData']['PlaybackPositionTicks'], item['RunTimeTicks'])
    video_db.add_studios_and_links(item['Studios'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_people_and_links(item['People'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_countries_and_links(item['ProductionLocations'], item['KodiItemIds'][ItemIndex], MediaType)
    video_db.add_streams(item['KodiFileIds'][ItemIndex], item['Streams'][0]['Video'], item['Streams'][0]['Audio'], item['Streams'][0]['Subtitle'], item['RunTimeTicks'])

    if "StackTimes" in item:
        video_db.add_stacktimes(item['KodiFileIds'][ItemIndex], item['StackTimes'])

def delete_ContentItem(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType, EmbyLibraryId):
    delete_ContentItemReferences(EmbyItemId, KodiItemId, KodiFileId, video_db, emby_db, MediaType)
    emby_db.remove_item(EmbyItemId, EmbyLibraryId)

def get_path_type_from_item(ServerId, item):
    HasSpecials = ""

    if 'SpecialFeatureCount' in item:
        if int(item['SpecialFeatureCount']):
            HasSpecials = "s"

    if item.get('NoLink'):
        return "", None

    if (item['Type'] == 'Photo' and 'Primary' in item['ImageTags']) or (item['Type'] == 'PhotoAlbum' and 'Primary' in item['ImageTags']):
        if 'Path' in item:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-0-p-{item['ImageTags']['Primary']}-{utils.PathToFilenameReplaceSpecialCharecters(item['Path'])}", "p"

        return f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-0-p-{item['ImageTags']['Primary']}", "p"

    if item['Type'] == "TvChannel":
        return f"http://127.0.0.1:57342/dynamic/{ServerId}/t-{item['Id']}-livetv", "t"

    if item['Type'] == "Audio":
        return f"http://127.0.0.1:57342/dynamic/{ServerId}/a-{item['Id']}-{utils.PathToFilenameReplaceSpecialCharecters(item['Path'])}", "a"

    if item['Type'] == "MusicVideo":
        Type = "M"
    elif item['Type'] == "Movie":
        Type = "m"
    elif item['Type'] == "Episode":
        Type = "e"
    elif item['Type'] == "Video":
        Type = "v"
    elif item['Type'] == "Trailer":
        Type = "T"
    else:
        return None, None

    if 'Path' in item:
        path = item['Path']

        # Strm
        if path.lower().endswith('.strm'):
            if 'MediaSources' in item and len(item['MediaSources']) > 0:
                path = item['MediaSources'][0].get('Path', "")
        elif path.lower().endswith(".iso"): # Iso
            if path.startswith('\\\\'):
                path = path.replace('\\\\', "smb://", 1).replace('\\\\', "\\").replace('\\', "/")

            return path, "i"

        # Plugin (youtube)
        if path.lower().startswith("plugin://"):
            return path, "v"

        # Regular
        IsRemote = item['MediaSources'][0].get('IsRemote', "0")

        if IsRemote and IsRemote != "0":
            IsRemote = "1"
        else:
            IsRemote = "0"

        get_streams(item)
        set_chapters(item, ServerId)
        VideoBitrate, VideoCodec = get_Bitrate_Codec(item, "Video")
        AudioBitrate, AudioCodec = get_Bitrate_Codec(item, "Audio")
        path = f"{utils.AddonModePath}dynamic/{ServerId}/{Type}-{item['Id']}-{item['MediaSources'][0]['Id']}-0-0-{item['Streams'][0]['HasExternalSubtitle']}-{len(item['MediaSources'])}-{item['IntroStartPositionTicks']}-{item['IntroEndPositionTicks']}-{item['CreditsPositionTicks']}-{IsRemote}-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{HasSpecials}-{utils.PathToFilenameReplaceSpecialCharecters(path)}"
        return path, Type

    # Channel
    return f"http://127.0.0.1:57342/dynamic/{ServerId}/c-{item['Id']}-{item['MediaSources'][0]['Id']}-stream.ts", "c"

def verify_content(Item, MediaType):
    if not 'Name' in Item:
        xbmc.log(f"EMBY.core.common: No name assinged: {Item}", 3) # LOGERROR
        return False

    if not 'MediaSources' in Item or not Item['MediaSources']:
        xbmc.log(f"EMBY.core.common: No mediasources found for {MediaType}: {Item['Id']}", 3) # LOGERROR
        xbmc.log(f"EMBY.core.common: No mediasources found for {MediaType}: {Item}", 0) # LOGDEBUG
        return False

    if len(Item['MediaSources']) > 0:
        if not 'MediaStreams' in Item['MediaSources'][0] or not Item['MediaSources'][0]['MediaStreams']:
            xbmc.log(f"EMBY.core.common: No mediastreams found for {MediaType}: {Item['Id']} / {Item.get('Path', '')}", 2) # LOGWARNING
            xbmc.log(f"EMBY.core.common: No mediastreams found for {MediaType}: {Item}", 0) # LOGDEBUG
    else:
        xbmc.log(f"EMBY.core.common: Empty mediasources found for {MediaType}: {Item['Id']}", 3) # LOGERROR
        xbmc.log(f"EMBY.core.common: Empty mediasources found for {MediaType}: {Item}", 0) # LOGDEBUG
        return False

    return True

def load_tvchannel(item, ServerId):
    item['CurrentProgram'] = item.get('CurrentProgram', {})
    item['CurrentProgram']['UserData'] = item['CurrentProgram'].get('UserData', {})

    if 'Name' in item['CurrentProgram']:
        item['Name'] = f"{item['Name']} / {item['CurrentProgram']['Name']}"

    if 'RunTimeTicks' in item['CurrentProgram']:
        item['CurrentProgram']['RunTimeTicks'] = round(float(item['CurrentProgram']['RunTimeTicks'] / 10000000.0), 6)
    else:
        item['CurrentProgram']['RunTimeTicks'] = 0

    if 'PlaybackPositionTicks' in item['CurrentProgram']['UserData']:
        item['CurrentProgram']['UserData']['PlaybackPositionTicks'] = round(float(item['CurrentProgram']['UserData']['PlaybackPositionTicks'] / 10000000.0), 6)
    else:
        item['CurrentProgram']['UserData']['PlaybackPositionTicks'] = 0

    item['CurrentProgram']['Genres'] = item['CurrentProgram'].get('Genres', [])
    item['CurrentProgram']['UserData']['PlayCount'] = item['CurrentProgram']['UserData'].get('PlayCount', 0)
    item['CurrentProgram']['UserData']['LastPlayedDate'] = item['CurrentProgram']['UserData'].get('LastPlayedDate', "")
    get_streams(item)
    set_overview(item)
    set_videocommon(item, ServerId, 0, True)

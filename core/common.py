from urllib.parse import quote, urlparse
import xbmc
from helper import utils

EmbyTypeMappingShort = {"Movie": "m", "Episode": "e", "MusicVideo": "M", "Audio": "a", "Video": "v"}
EmbyArtworkIdShort = {"Primary": "p", "Art": "a", "Banner": "b", "Disc": "d", "Logo": "l", "Thumb": "t", "Backdrop": "B", "Chapter": "c", "SeriesPrimary": "p", "AlbumPrimary": "p", "ParentBackdrop": "B", "ParentThumb": "t", "ParentLogo": "l", "ParentBanner": "b", "AlbumArtists": "p", "ArtistItems": "p"}
MarkerTypeMapping = {"IntroStart": "Intro Start", "IntroEnd": "Intro End", "CreditsStart": "Credits"}
MappingIds = {'Season': "999999989", 'Series': "999999990", 'MusicAlbum': "999999991", 'MusicGenre': "999999992", "Studio": "999999994", "Tag": "999999993", "Genre": "999999995", "MusicArtist": "999999996"}
ImageTagsMappings = {
    "Series": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Backdrop", 'landscape'), ("Primary", 'landscape')),
    "Season": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ('SeriesPrimary', 'poster'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo", 'clearlogo'), ("ParentBackdrop", 'fanart')),
    "Episode": (('Primary', 'thumb'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ("ParentLogo", 'clearlogo'), ("ParentBanner", 'banner'), ("ParentThumb", 'landscape'), ("ParentThumb", 'thumb'), ("ParentBackdrop", 'landscape'), ("ParentBackdrop", 'fanart'), ('Primary', 'landscape')),
    "Movie": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape')),
    "BoxSet": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape')),
    "Video": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "MusicArtist": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "MusicAlbum": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo" ,'clearlogo'), ("AlbumArtists", 'poster'), ("AlbumArtists", 'thumb'), ("AlbumArtists", 'fanart'), ("ArtistItems", 'poster'), ("ArtistItems", 'thumb'), ("ArtistItems", 'fanart'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "Audio": (('Primary', 'thumb'), ('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('AlbumPrimary', 'poster'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo", 'clearlogo'), ("ParentBackdrop", 'fanart'), ("AlbumArtists", 'poster'), ("AlbumArtists", 'thumb'), ("AlbumArtists", 'fanart'), ("ArtistItems", 'poster'), ("ArtistItems", 'thumb'), ("ArtistItems", 'fanart'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "MusicVideo": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "Photo": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "PhotoAlbum": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "Folder": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "TvChannel": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb')),
    "Trailer": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape')),
    "Person": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape'))
}

def load_ExistingItem(Item, EmbyServer, emby_db, EmbyType):
    ExistingItem = emby_db.get_item_by_id(Item['Id'], EmbyType)
    ForceNew = False

    if ExistingItem and EmbyType in ("Movie", "Video", "MusicVideo", "Episode"):
        if not ExistingItem[1]: # no KodiItemId assined but Item exists (this means it's a multi version content item (grouped))
            if len(Item['MediaSources']) == 1: # multi version content item (grouped) was released
                emby_db.remove_item(Item['Id'], EmbyType, Item['LibraryId'])
                xbmc.log(f"EMBY.core.common: load_ExistingItem, release grouped content: {Item['Name']}", 1) # LOGINFO
                ForceNew = True
            else:
                xbmc.log(f"EMBY.core.common: load_ExistingItem, skip grouped content: {Item['Name']}", 1) # LOGINFO
                return False

    if EmbyType in ("Genre", "Person", "Tag", "Studio", "Playlist"):
        if ExistingItem:
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False})

        return True

    if EmbyType == "BoxSet":
        if ExistingItem:
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiParentId": ExistingItem[3]})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "KodiParentId": None})

        return True

    if EmbyType == "Episode":
        if not ForceNew and ExistingItem:
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiFileId": ExistingItem[3], "KodiParentId": ExistingItem[4], "EmbyPresentationKey": ExistingItem[5], "EmbyFolder": ExistingItem[6], "KodiPathId": ExistingItem[7], "IntroStart": ExistingItem[8], "IntroEnd": ExistingItem[9]})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "KodiParentId": None, "EmbyPresentationKey": None, "EmbyFolder": None, "KodiFileId": None, "KodiPathId": None, "IntroStart": None, "IntroEnd": None})

        return True

    if EmbyType == "Season":
        if ExistingItem:
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiParentId": ExistingItem[3], "EmbyPresentationKey": ExistingItem[4]})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "KodiParentId": None, "EmbyPresentationKey": None})

        return True

    LibraryName, _ = EmbyServer.library.WhitelistUnique[Item['LibraryId']]

    if EmbyType in ("Movie", "Video", "MusicVideo"):
        if not ForceNew and ExistingItem:
            Item.update({"LibraryName": LibraryName, 'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiFileId": ExistingItem[3], "EmbyPresentationKey": ExistingItem[4], "EmbyFolder": ExistingItem[5], "KodiPathId": ExistingItem[6]})
        else:
            Item.update({"LibraryName": LibraryName, 'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyPresentationKey": None, "EmbyFolder": None, "KodiFileId": None, "KodiPathId": None})

        return True

    if EmbyType == "Series":
        if ExistingItem:
            Item.update({"LibraryName": LibraryName, 'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "EmbyPresentationKey": ExistingItem[3], "KodiPathId": ExistingItem[4]})
        else:
            Item.update({"LibraryName": LibraryName, 'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyPresentationKey": None, "KodiPathId": None})

        return True

    if EmbyType in ("MusicArtist", "MusicGenre"):
        if ExistingItem:
            Item.update({'KodiItemIds': ExistingItem[1], 'UpdateItem': True, "LibraryIds": ExistingItem[3]})
        else:
            Item.update({'KodiItemIds': "", 'UpdateItem': False, "LibraryIds": ""})

        return True

    if EmbyType == "MusicAlbum":
        if ExistingItem:
            Item.update({'KodiItemIds': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "LibraryIds": ExistingItem[3]})
        else:
            Item.update({'KodiItemIds': "", 'UpdateItem': False, "EmbyFavourite": None, "LibraryIds": ""})

        return True

    if EmbyType == "Audio":
        if ExistingItem:
            Item.update({'KodiItemIds': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "EmbyFolder": ExistingItem[3], "KodiPathId": ExistingItem[4], "LibraryIds": ExistingItem[5]})
        else:
            Item.update({'KodiItemIds': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyFolder": None, "KodiPathId": None, "LibraryIds": ""})

        return True

    xbmc.log(f"EMBY.core.common: EmbyType invalid: {EmbyType}", 3) # LOGERROR
    return False

def get_Bitrate_Codec(Item, StreamType):
    Bitrate = 0
    Codec = ""

    if Item['Streams'][0][StreamType]:
        if 'BitRate' in Item['Streams'][0][StreamType][0]:
            Bitrate = Item['Streams'][0][StreamType][0]['BitRate']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Bitrate found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING

        if 'codec' in Item['Streams'][0][StreamType][0]:
            Codec = Item['Streams'][0][StreamType][0]['codec']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Codec found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.core.common: No Streams Bitrate found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING

    if not Bitrate:
        Bitrate = 0

    if not Codec:
        Codec = ""

    return Bitrate, Codec

def get_path(Item, ServerId):
    if 'MediaSources' in Item:
        Item['KodiPath'] = Item['MediaSources'][0]['Path']
    else:
        Item['KodiPath'] = Item['Path']

    # Addonmode replace filextensions
    if Item['KodiPath'].endswith('.strm') and 'Container' in Item:
        Item['KodiPath'] = Item['KodiPath'].replace('.strm', "")

        if not Item['KodiPath'].endswith(Item['Container']):
            Item['KodiPath'] += f".{Item['Container']}"

    if Item['KodiPath'].startswith('\\\\'):
        Item['KodiPath'] = Item['KodiPath'].replace('\\\\', "SMBINJECT", 1).replace('\\', "/") # only replace \\ on beginning with smb://
        Item['KodiPath'] = Item['KodiPath'].replace('//', "/")  # fix trailing "/" (Emby server path substitution -> user assigned "wrong" trailing "/")
        Item['KodiPath'] = Item['KodiPath'].replace('SMBINJECT', "smb://") # only replace \\ on beginning with smb://
    elif '://' in Item['KodiPath']:
        protocol = Item['KodiPath'].split('://')[0]
        Item['KodiPath'] = Item['KodiPath'].replace(protocol, protocol.lower())
    else:
        Item['KodiPath'] = Item['KodiPath'].replace("\\\\", "\\")

    ForceNativeMode = False
    KodiPathLower = Item['KodiPath'].lower()
    Container = Item.get('Container', "")

    if Container == 'dvd' or KodiPathLower.endswith(".ifo"):
        Item['KodiPath'] += "/VIDEO_TS/VIDEO_TS.IFO"
        ForceNativeMode = True
    elif Container == 'bluray' or KodiPathLower.endswith(".bdmv"):
        Item['KodiPath'] += "/BDMV/index.bdmv"
        ForceNativeMode = True
    elif Container == 'iso' or KodiPathLower.endswith(".iso"):
        ForceNativeMode = True
    elif KodiPathLower.startswith("http://") or KodiPathLower.startswith("dav://"):
        UrlData = urlparse(Item['KodiPath'])
        UrlPath = quote(UrlData[2])
        Item['KodiPath'] = f"{UrlData[0]}://{UrlData[1]}{UrlPath}"
        ForceNativeMode = True
    elif KodiPathLower.startswith("plugin://"):
        return

    if utils.useDirectPaths or ForceNativeMode:
        Item['NativeMode'] = True
        PathSeperator = utils.get_Path_Seperator(Item['KodiPath'])
        Temp = Item['KodiPath'].rsplit(PathSeperator, 1)[1]

        if Item['Type'] == "Series":
            Item['KodiPathParent'] = f"{Item['KodiPath'].replace(Temp, '')}"
            Item['KodiPath'] += PathSeperator
        else:
            Item['KodiPath'] = f"{Item['KodiPath'].replace(Temp, '')}"
    else:
        Item['NativeMode'] = False

        if Item['Type'] == "Series":
            Item['KodiPathParent'] = f"{utils.AddonModePath}tvshows/{ServerId}/{Item['LibraryId']}/"
            Item['KodiPath'] = f"{utils.AddonModePath}tvshows/{ServerId}/{Item['LibraryId']}/{Item['Id']}/"
        elif Item['Type'] == "Episode":
            Item['KodiPath'] = f"{utils.AddonModePath}tvshows/{ServerId}/{Item['LibraryId']}/{Item['SeriesId']}/{Item['Id']}/"
        elif Item['Type'] in ("Movie", "Video"):
            Item['KodiPath'] = f"{utils.AddonModePath}movies/{ServerId}/{Item['LibraryId']}/"
        elif Item['Type'] == "MusicVideo":
            Item['KodiPath'] = f"{utils.AddonModePath}musicvideos/{ServerId}/{Item['LibraryId']}/"
        elif Item['Type'] == "Audio":
            Item['KodiPath'] = f"{utils.AddonModePath}audio/{ServerId}/{Item['LibraryId']}/"

def get_filename(Item, API):
    Item['KodiStackedFilename'] = None

    if Item['KodiPath'].lower().startswith("plugin://"):
        Item['KodiFilename'] = Item['KodiPath']
        return

    # Native mode: (KodiFilename was set in "get_file_path" function for native files)
    if Item['NativeMode']:
        if 'MediaSources' in Item:
            Path = Item['MediaSources'][0]['Path']
        else:
            Path = Item['Path']

        PathSeperator = utils.get_Path_Seperator(Path)
        Item['KodiFilename'] = Path.rsplit(PathSeperator, 1)[1]

        if Item['Type'] == "Audio":
            return

        set_multipart(Item, API, None)
        return

    # Addon
    HasSpecials = ""
    MediaID = EmbyTypeMappingShort[Item['Type']]

    if 'SpecialFeatureCount' in Item:
        if int(Item['SpecialFeatureCount']):
            HasSpecials = "s"

    FilteredFilename = utils.PathToFilenameReplaceSpecialCharecters(Item['Path']).replace("-", "_").replace(" ", "_")

    if Item['Type'] == "Audio":
        Item['KodiFilename'] = f"a-{Item['Id']}-{FilteredFilename}"
        return

    VideoBitrate, VideoCodec = get_Bitrate_Codec(Item, "Video")
    AudioBitrate, AudioCodec = get_Bitrate_Codec(Item, "Audio")
    IsRemote = Item['MediaSources'][0].get('IsRemote', False)

    if IsRemote:
        IsRemote = "1"
    else:
        IsRemote = "0"

    Item['KodiFilename'] = f"{MediaID}-{Item['Id']}-{Item['MediaSources'][0]['Id']}-{Item['KodiItemId']}-{Item['KodiFileId']}-{Item['Streams'][0]['HasExternalSubtitle']}-{len(Item['MediaSources'])}-{Item['IntroStartPositionTicks']}-{Item['IntroEndPositionTicks']}-{Item['CreditsPositionTicks']}-{IsRemote}-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{HasSpecials}-{FilteredFilename}"
    set_multipart(Item, API, MediaID)

# Detect Multipart videos
def set_multipart(Item, API, MediaID):
    if 'PartCount' in Item and API:
        if Item['PartCount'] >= 2:
            AdditionalParts = API.get_additional_parts(Item['Id'])

            if Item['KodiRunTimeTicks']:
                Value = float(Item['KodiRunTimeTicks'])
                StackedKodiRunTimeTicks = (str(Value),)
                StackedKodiRunTimeTicksSum = Value
            else:
                StackedKodiRunTimeTicks = ("0",)
                StackedKodiRunTimeTicksSum = 0

            StackedFilenames = (f"{Item['KodiPath']}{Item['KodiFilename']}",)

            for AdditionalItem in AdditionalParts['Items']:
                if Item['NativeMode']:
                    if 'MediaSources' in AdditionalItem:
                        Path = AdditionalItem['MediaSources'][0]['Path']
                    else:
                        Path = AdditionalItem['Path']

                    PathSeperatorAdditionalPart = utils.get_Path_Seperator(Path)
                    StackedFilenames += (f"{Item['KodiPath']}{Path.rsplit(PathSeperatorAdditionalPart, 1)[1]}",)
                else:
                    AdditionalFilteredFilename = utils.PathToFilenameReplaceSpecialCharecters(AdditionalItem['Path']).replace("-", "_").replace(" ", "_")
                    get_streams(AdditionalItem)
                    VideoBitrate, VideoCodec = get_Bitrate_Codec(Item, "Video")
                    AudioBitrate, AudioCodec = get_Bitrate_Codec(Item, "Audio")
                    StackedFilenames += (f"{Item['KodiPath']}{MediaID}-{AdditionalItem['Id']}-{AdditionalItem['MediaSources'][0]['Id']}-{Item['KodiPathId']}-{Item['KodiFileId']}-{AdditionalItem['Streams'][0]['HasExternalSubtitle']}-{len(Item['MediaSources'])}-0-0-0-0-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{AdditionalFilteredFilename}",)

                if 'RunTimeTicks' in AdditionalItem and AdditionalItem['RunTimeTicks']:
                    Value = round(float(AdditionalItem['RunTimeTicks'] / 10000000.0), 6)
                    StackedKodiRunTimeTicks += (str(Value),)
                    StackedKodiRunTimeTicksSum += Value
                else:
                    StackedKodiRunTimeTicks += ("0",)

            if StackedKodiRunTimeTicksSum:
                Item['KodiRunTimeTicks'] = StackedKodiRunTimeTicksSum
            else:
                Item['KodiRunTimeTicks'] = None

            Item['KodiStackedFilename'] = f"stack://{' , '.join(StackedFilenames)}"
            Item['KodiStackTimes'] = ','.join(StackedKodiRunTimeTicks)

def SwopMediaSources(Item):
    if 'MediaSources' not in Item:
        return

    if len(Item['MediaSources']) > 1:
        if Item['MediaSources'][0].get('Video3DFormat'):
            xbmc.log(f"EMBY.core.common: 3D detected, swap MediaSources {Item['Name']}", 1) # LOGINFO
            Item0 = Item['MediaSources'][0]
            Item1 = Item['MediaSources'][1]
            Item['MediaSources'][0] = Item1
            Item['MediaSources'][1] = Item0

            if 'Path' in Item['MediaSources'][0]:
                Item['Path'] = Item['MediaSources'][0]['Path']

def get_streams(Item):
    Item['Streams'] = []

    if 'MediaSources' not in Item:
        return

    for IndexMediaSources, MediaSource in enumerate(Item['MediaSources']):
        # TVChannel
        MediaSource['Path'] = MediaSource.get('Path', "")
        MediaSource['Size'] = MediaSource.get('Size', "")

        # Videos
        Item['Streams'].append({'Subtitle': [], 'Audio': [], 'Video': [], 'Id': MediaSource['Id'], 'Index': IndexMediaSources, 'Path': MediaSource['Path'], 'Name': MediaSource['Name'], 'Size': MediaSource['Size']})
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
                Item['Streams'][IndexMediaSources]['Audio'].append({'SampleRate': Stream.get('SampleRate', None), 'BitRate': Stream.get('BitRate', None), 'codec': Codec, 'channels': Stream.get('Channels', None), 'language': Stream.get('Language', None), 'Index': Index, 'DisplayTitle': Stream.get('DisplayTitle', "unknown")})
            elif Stream['Type'] == "Video":
                StreamData = {'language': Stream.get('Language', None),'hdrtype': None, 'codec': Codec, 'height': Stream.get('Height', None), 'width': Stream.get('Width', None), '3d': Stream.get('Video3DFormat', None), 'BitRate': Stream.get('BitRate', None), 'Index': Index, 'aspect': None}

                CodecTag = Stream.get('CodecTag', "")

                if CodecTag == "dvhe":
                    StreamData['hdrtype'] = "dolbyvision"
                elif CodecTag == "hvc1":
                    StreamData['hdrtype'] = "hdr10"

                if "AspectRatio" in Stream:
                    AspectRatio = Stream['AspectRatio'].split(':')

                    if len(AspectRatio) != 2:
                        xbmc.log(f"EMBY.core.common: AspectRatio detected by alternative method: {Item['Id']} / {Item['Name']}", 2) # LOGWARNING
                        AspectRatio = Stream['AspectRatio'].split('/')

                    if len(AspectRatio) == 2 and utils.is_number(AspectRatio[0]) and utils.is_number(AspectRatio[1]) and float(AspectRatio[1]) > 0:
                        StreamData['aspect'] = round(float(AspectRatio[0]) / float(AspectRatio[1]), 6)
                    else:
                        xbmc.log(f"EMBY.core.common: AspectRatio not detected: {Item['Id']} / {Item['Name']}", 2) # LOGWARNING

                        if Stream['Height'] and Stream['Width']:
                            StreamData['aspect'] = round(float(Stream['Width']) / float(Stream['Height']), 6)
                            xbmc.log(f"EMBY.core.common: AspectRatio calculated based on width/height ratio: {Stream['Height']} / {Stream['Height']} / {StreamData['aspect']}", 1) # LOGINFO

                Item['Streams'][IndexMediaSources]['Video'].append(StreamData)
            elif Stream['Type'] == "Subtitle":
                IsExternal = Stream.get('IsExternal', False)

                if IsExternal:
                    HasExternalSubtitle = "1"

                Item['Streams'][IndexMediaSources]['Subtitle'].append({'Index': Index, 'language': Stream.get('Language', "und"), 'DisplayTitle': Stream.get('DisplayTitle', "unknown"), 'codec': Codec, 'external': IsExternal})

        Item['Streams'][IndexMediaSources]['HasExternalSubtitle'] = HasExternalSubtitle

def set_RunTimeTicks(Item):
    if 'RunTimeTicks' in Item:
        RunTimeTicks = Item['RunTimeTicks']
    elif 'CurrentProgram' in Item and 'RunTimeTicks' in Item['CurrentProgram']:
        RunTimeTicks = Item['CurrentProgram']['RunTimeTicks']
    elif 'PlaybackPositionTicks' in Item and Item['PlaybackPositionTicks'] and 'PlayedPercentage' in Item and Item['PlayedPercentage']: # calculate runtime based on progress
        RunTimeTicks = int(Item['PlaybackPositionTicks'] / Item['PlayedPercentage'] * 100)
    else:
        RunTimeTicks = None

    if RunTimeTicks:
        Item['KodiRunTimeTicks'] = round(float(RunTimeTicks / 10000000.0), 6)
    else:
        Item['KodiRunTimeTicks'] = None
        xbmc.log(f"EMBY.core.common: No Runtime found: {Item.get('Id', '-1')}", 0) # LOGDEBUG

def set_overview(Item):
    if 'Overview' in Item:
        if Item['Overview']:
            Item['Overview'] = Item['Overview'].replace("\"", "\'")
            Item['Overview'] = Item['Overview'].replace("\n", "[CR]")
            Item['Overview'] = Item['Overview'].replace("\r", " ")
            Item['Overview'] = Item['Overview'].replace("<br>", "[CR]")
    else:
        Item['Overview'] = None

    if 'CurrentProgram' in Item: #TvChannel
        if 'Overview' in Item['CurrentProgram']:
            if Item['CurrentProgram']['Overview']:
                Item['CurrentProgram']['Overview'] = Item['CurrentProgram']['Overview'].replace("\"", "\'")
                Item['CurrentProgram']['Overview'] = Item['CurrentProgram']['Overview'].replace("\n", "[CR]")
                Item['CurrentProgram']['Overview'] = Item['CurrentProgram']['Overview'].replace("\r", " ")
                Item['CurrentProgram']['Overview'] = Item['CurrentProgram']['Overview'].replace("<br>", "[CR]")
        else:
            Item['CurrentProgram']['Overview'] = None

def set_mpaa(Item):
    if 'OfficialRating' in Item:
        if Item['OfficialRating']:
            if Item['OfficialRating'] in ("NR", "UR"):
                # Kodi seems to not like NR, but will accept Not Rated
                Item['OfficialRating'] = "Not Rated"

            if "FSK-" in Item['OfficialRating']:
                Item['OfficialRating'] = Item['OfficialRating'].replace("-", " ")

            if "GB-" in Item['OfficialRating']:
                Item['OfficialRating'] = Item['OfficialRating'].replace("GB-", "UK:")
    else:
        Item['OfficialRating'] = None

def set_trailer(Item, EmbyServer):
    Item['Trailer'] = None

    if 'LocalTrailerCount' in Item and Item['LocalTrailerCount']:
        for IntroLocal in EmbyServer.API.get_local_trailers(Item['Id']):
            Filename = utils.PathToFilenameReplaceSpecialCharecters(IntroLocal['Path'])
            Item['Trailer'] = f"{utils.AddonModePath}dynamic/{EmbyServer.ServerData['ServerId']}/V-{IntroLocal['Id']}-{IntroLocal['MediaSources'][0]['Id']}-{Filename}"
            return

    if 'RemoteTrailers' in Item and Item['RemoteTrailers']:
        try:
            Item['Trailer'] = f"plugin://plugin.video.youtube/play/?video_id={Item['RemoteTrailers'][0]['Url'].rsplit('=', 1)[1]}"
        except Exception as Error:
            xbmc.log(f"EMBY.core.common: Trailer not valid: {Item['Name']} / {Error}", 3) # LOGERROR

def set_playstate(Item):
    if 'UserData' in Item:
        UserData = Item['UserData']
    elif 'CurrentProgram' in Item and 'UserData' in Item['CurrentProgram']:
        UserData = Item['CurrentProgram']['UserData']
    else:
        UserData = Item

    PlayCount = UserData.get('PlayCount', None)

    if 'Played' in UserData:
        if not UserData['Played']:
            Item['KodiPlayCount'] = None
        else:
            if PlayCount:
                Item['KodiPlayCount'] = PlayCount
            else:
                Item['KodiPlayCount'] = 1
    else:
        Item['KodiPlayCount'] = PlayCount

        if not Item['KodiPlayCount']: # could be "0" then substitute with "None"
            Item['KodiPlayCount'] = None

    if 'LastPlayedDate' in UserData and UserData['LastPlayedDate']:
        Item['KodiLastPlayedDate'] = utils.convert_to_local(UserData['LastPlayedDate'])
    else:
        Item['KodiLastPlayedDate'] = None

    if 'PlaybackPositionTicks' in UserData and UserData['PlaybackPositionTicks']:
        Item['KodiPlaybackPositionTicks'] = (float(UserData['PlaybackPositionTicks']) - float(utils.resumeJumpBack)) / 10000000.0

        if UserData['PlaybackPositionTicks'] <= 0:
            Item['KodiPlaybackPositionTicks'] = None
    else:
        Item['KodiPlaybackPositionTicks'] = None

def set_common(Item, ServerId, DynamicNode):
    Item['ProductionLocations'] = Item.get('ProductionLocations', [])

    if 'DateCreated' in Item:
        Item['KodiDateCreated'] = utils.convert_to_local(Item['DateCreated'])
    else:
        Item['KodiDateCreated'] = None

    if 'Taglines' not in Item or not Item['Taglines']:
        Item['Tagline'] = None
    else:
        Item['Tagline'] = "\n".join(Item['Taglines'])

    if 'TagItems' not in Item:
        Item['TagItems'] = []

    Item['OriginalTitle'] = Item.get('OriginalTitle', None)
    Item['SortIndexNumber'] = Item.get('SortIndexNumber', None)
    Item['SortParentIndexNumber'] = Item.get('SortParentIndexNumber', None)
    Item['IndexNumber'] = Item.get('IndexNumber', None)
    Item['CommunityRating'] = Item.get('CommunityRating', None)
    Item['ParentIndexNumber'] = Item.get('ParentIndexNumber', None)
    Item['CriticRating'] = Item.get('CriticRating', None)
    Item['ShortOverview'] = Item.get('ShortOverview', None)
    Item['Status'] = Item.get('Status', None)
    Item['KodiLastScraped'] = utils.currenttime_kodi_format()
    Item['ProviderIds'] = Item.get('ProviderIds', {})
    Item['ProviderIds']['MusicBrainzTrack'] = Item['ProviderIds'].get('MusicBrainzTrack', None)
    Item['ProviderIds']['MusicBrainzAlbum'] = Item['ProviderIds'].get('MusicBrainzAlbum', None)
    Item['ProviderIds']['MusicBrainzReleaseGroup'] = Item['ProviderIds'].get('MusicBrainzReleaseGroup', None)
    Item['ProviderIds']['MusicBrainzArtist'] = Item['ProviderIds'].get('MusicBrainzArtist', None)
    Item['ProviderIds']['MusicBrainzAlbumArtist'] = Item['ProviderIds'].get('MusicBrainzAlbumArtist', None)
    Item['IndexNumber'] = Item.get('IndexNumber', None)
    get_PresentationUniqueKey(Item)
    set_mpaa(Item)
    set_playstate(Item)
    set_overview(Item)
    set_Dates(Item)
    set_KodiArtwork(Item, ServerId, DynamicNode)

    if DynamicNode:
        Item['GenreNames'] = []

        if 'GenreItems' in Item and Item['GenreItems']:
            for GenreItem in Item['GenreItems']:
                if 'Name' in GenreItem:
                    Item['GenreNames'].append(GenreItem['Name'])

        Item['StudioNames'] = []

        if 'Studios' in Item and Item['Studios']:
            for Studio in Item['Studios']:
                if 'Name' in Studio:
                    Item['StudioNames'].append(Studio['Name'])

        Item['Writers'] = []
        Item['Directors'] = []
        Item['Cast'] = []
        PeopleInvalidRecords = []

        if "People" in Item:
            for Index, People in enumerate(Item['People']):
                if 'Name' in People:
                    if People['Type'] == "Writer":
                        Item['Writers'].append(People['Name'])
                    elif People['Type'] == "Director":
                        Item['Directors'].append(People['Name'])
                    elif People['Type'] == "Actor":
                        Item['Cast'].append(People['Name'])

                    if 'PrimaryImageTag' in People:
                        People['imageurl'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{People['Id']}-0-p-{People['PrimaryImageTag']}|redirect-limit=1000"
                    else:
                        People['imageurl'] = ""
                else:
                    PeopleInvalidRecords.append(Index)

            for PeopleInvalidRecord in PeopleInvalidRecords[::-1]: # reversed order
                del Item['People'][PeopleInvalidRecord]
        else:
            Item['People'] = []

        if "ArtistItems" in Item:
            for ArtistItem in Item['ArtistItems']:
                if 'PrimaryImageTag' in ArtistItem:
                    ArtistItem['imageurl'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{ArtistItem['Id']}-0-p-{ArtistItem['PrimaryImageTag']}|redirect-limit=1000"
                else:
                    ArtistItem['imageurl'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{ArtistItem['Id']}-0-p-0|redirect-limit=1000"

def set_Dates(Item):
    if 'ProductionYear' in Item:
        Item['KodiProductionYear'] = utils.convert_to_local(Item['ProductionYear'], True)
    else:
        Item['KodiProductionYear'] = None

    if 'PremiereDate' in Item:
        Item['KodiPremiereDate'] = utils.convert_to_local(Item['PremiereDate'], True)
    else:
        Item['KodiPremiereDate'] = None

    if not Item['KodiPremiereDate'] and Item['KodiProductionYear']:
        Item['KodiProductionYear'] = Item['KodiPremiereDate']

    if not Item['KodiProductionYear'] and Item['KodiPremiereDate']:
        Item['KodiPremiereDate'] = Item['KodiProductionYear']

    if Item['KodiProductionYear']:
        Item['KodiProductionYear'] = Item['KodiProductionYear'][:4]

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
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-{Chapter['ImageTag']}-{MarkerLabel}|redirect-limit=1000"
                else: # inject blank image, otherwise not possible to use text overlay (webservice.py)
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-noimage-{MarkerLabel}|redirect-limit=1000"
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
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-{Chapter['ImageTag']}-{quote(Chapter['Name'])}|redirect-limit=1000"
                else:
                    ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-{index}-c-noimage-{quote(Chapter['Name'])}|redirect-limit=1000"

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
    item['KodiArtwork'] = {'clearart': None, 'clearlogo': None, 'discart': None, 'landscape': None, 'thumb': None, 'banner': None, 'poster': None, 'fanart': {}, 'favourite': None}

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
                    elif f"{ImageTagsMapping[0]}ImageItemId" in item:
                        EmbyArtworkId = item[f"{ImageTagsMapping[0]}ImageItemId"]
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
                    EmbyBackDropsId = item.get("Id", None)

                if EmbyBackDropsId:
                    if item[BackDropsKey] and item[BackDropsKey] != "None":
                        if ImageTagsMapping[1] == "fanart":
                            if not "fanart" in item['KodiArtwork']["fanart"]:
                                item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-B-{item[BackDropsKey][0]}|redirect-limit=1000"

                            for index, EmbyArtworkTag in enumerate(item[BackDropsKey][1:], 1):
                                if not f"fanart{index}" in item['KodiArtwork']["fanart"]:
                                    item['KodiArtwork']["fanart"][f"fanart{index}"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-{index}-B-{EmbyArtworkTag}|redirect-limit=1000"
                        else:
                            if not item['KodiArtwork'][ImageTagsMapping[1]]:
                                item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{item[BackDropsKey][0]}|redirect-limit=1000"

            if EmbyArtworkId:
                if ImageTagsMapping[1] == "fanart":
                    if not "fanart" in item['KodiArtwork']["fanart"]:
                        item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}|redirect-limit=1000"
                else:
                    if not item['KodiArtwork'][ImageTagsMapping[1]]:
                        item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}|redirect-limit=1000"

    if utils.AssignEpisodePostersToTVShowPoster:
        if item['Type'] == "Episode" and 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
            item['KodiArtwork']['poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['SeriesId']}-0-p-{item['SeriesPrimaryImageTag']}|redirect-limit=1000"

    if DynamicNode:
        if item['Type'] == "Episode":
            if 'SeriesId' in item and "SeriesPrimaryImageTag" in item and item["SeriesPrimaryImageTag"] and item["SeriesPrimaryImageTag"] != "None":
                item['KodiArtwork']['tvshow.poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['SeriesId']}-0-p-{item['SeriesPrimaryImageTag']}|redirect-limit=1000"

            if 'ParentThumbItemId' in item and "ParentThumbImageTag" in item and item["ParentThumbImageTag"] and item["ParentThumbImageTag"] != "None":
                item['KodiArtwork']['tvshow.thumb'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentThumbItemId']}-0-p-{item['ParentThumbImageTag']}|redirect-limit=1000"

            if 'ParentLogoItemId' in item and "ParentLogoImageTag" in item and item["ParentLogoImageTag"] and item["ParentLogoImageTag"] != "None":
                item['KodiArtwork']['tvshow.clearlogo'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentLogoItemId']}-0-p-{item['ParentLogoImageTag']}|redirect-limit=1000"

            if 'ParentBackdropItemId' in item and "ParentBackdropImageTags" in item and item["ParentBackdropImageTags"]:
                item['KodiArtwork']['tvshow.fanart'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['ParentBackdropItemId']}-0-p-{item['ParentBackdropImageTags'][0]}|redirect-limit=1000"

    if item['KodiArtwork']['poster']:
        item['KodiArtwork']['favourite'] = item['KodiArtwork']['poster']
    else:
        item['KodiArtwork']['favourite'] = item['KodiArtwork']['thumb']

def set_MusicVideoTracks(item):
    # Try to detect track number
    item['IndexNumber'] = None
    Temp = item['MediaSources'][0]['Name'][:4]  # e.g. 01 - Artist - Title
    Temp = Temp.split("-")

    if len(Temp) > 1:
        Track = Temp[0].strip()

        if Track.isdigit():
            item['IndexNumber'] = int(Track)  # remove leading zero e.g. 01

def delete_ContentItemReferences(Item, SQLs, KodiType):
    KodiLibraryTagIds = SQLs["emby"].get_KodiLibraryTagIds()
    SQLs["video"].delete_links_actors(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_director(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_writer(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_countries(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_studios(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_tags(Item['KodiItemId'], KodiType, KodiLibraryTagIds)
    SQLs["video"].delete_uniqueids(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_bookmark(Item['KodiFileId'])
    SQLs["video"].delete_streams(Item['KodiFileId'])
    SQLs["video"].delete_stacktimes(Item['KodiFileId'])
    SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], KodiType)

def set_VideoCommon(Item, SQLs, KodiType, API):
    get_filename(Item, API)
    SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], KodiType)
    SQLs["video"].add_bookmarks(Item['KodiFileId'], Item['KodiRunTimeTicks'], Item['ChapterInfo'], Item['KodiPlaybackPositionTicks'])
    SQLs["video"].add_countries_and_links(Item['ProductionLocations'], Item['KodiItemId'], KodiType)
    SQLs["video"].add_streams(Item['KodiFileId'], Item['Streams'][0]['Video'], Item['Streams'][0]['Audio'], Item['Streams'][0]['Subtitle'], Item['KodiRunTimeTicks'])

    if "KodiStackTimes" in Item:
        SQLs["video"].add_stacktimes(Item['KodiFileId'], Item['KodiStackTimes'])

def delete_ContentItem(Item, SQLs, KodiType, EmbyType):
    if SQLs['emby'].remove_item(Item['Id'], EmbyType, Item['LibraryId']):
        delete_ContentItemReferences(Item, SQLs, KodiType)
        return True

    return False

def get_path_type_from_item(ServerId, item, isSpecial=False, isTrailer=False):
    HasSpecials = ""

    if 'SpecialFeatureCount' in item:
        if int(item['SpecialFeatureCount']):
            HasSpecials = "s"

    if item.get('NoLink'):
        return "", None

    if (item['Type'] == 'Photo' and 'Primary' in item['ImageTags']) or (item['Type'] == 'PhotoAlbum' and 'Primary' in item['ImageTags']):
        if 'Path' in item:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-0-p-{item['ImageTags']['Primary']}--{utils.PathToFilenameReplaceSpecialCharecters(item['Path'])}|redirect-limit=1000", "p"

        return f"http://127.0.0.1:57342/picture/{ServerId}/p-{item['Id']}-0-p-{item['ImageTags']['Primary']}|redirect-limit=1000", "p"

    if item['Type'] == "TvChannel":
        return f"http://127.0.0.1:57342/dynamic/{ServerId}/t-{item['Id']}-livetv", "t"

    if item['Type'] == "Audio":
        if isSpecial:
            return f"http://127.0.0.1:57342/dynamic/{ServerId}/A-{item['Id']}-{utils.PathToFilenameReplaceSpecialCharecters(item['Path'])}", "A"

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
                path = path.replace('\\\\', "smb://", 1).replace('\\', "/")

            return path, "i"

        # Plugin (youtube)
        if path.lower().startswith("plugin://"):
            return path, "v"

        get_streams(item)
        set_chapters(item, ServerId)
        VideoBitrate, VideoCodec = get_Bitrate_Codec(item, "Video")
        AudioBitrate, AudioCodec = get_Bitrate_Codec(item, "Audio")

        if isTrailer: # used to skip remote content verification
            path = f"http://127.0.0.1:57342/dynamic/{ServerId}/{Type}-{item['Id']}-{item['MediaSources'][0]['Id']}-0-0-{item['Streams'][0]['HasExternalSubtitle']}-{len(item['MediaSources'])}-{item['IntroStartPositionTicks']}-{item['IntroEndPositionTicks']}-{item['CreditsPositionTicks']}-0-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{HasSpecials}-{utils.PathToFilenameReplaceSpecialCharecters(path)}"
        else:
            IsRemote = item['MediaSources'][0].get('IsRemote', "0")

            if IsRemote and IsRemote != "0":
                IsRemote = "1"
            else:
                IsRemote = "0"

            path = f"{utils.AddonModePath}dynamic/{ServerId}/{Type}-{item['Id']}-{item['MediaSources'][0]['Id']}-0-0-{item['Streams'][0]['HasExternalSubtitle']}-{len(item['MediaSources'])}-{item['IntroStartPositionTicks']}-{item['IntroEndPositionTicks']}-{item['CreditsPositionTicks']}-{IsRemote}-{VideoCodec}-{VideoBitrate}-{AudioCodec}-{AudioBitrate}-{HasSpecials}-{utils.PathToFilenameReplaceSpecialCharecters(path)}"

        return path, Type

    # Channel
    return f"http://127.0.0.1:57342/dynamic/{ServerId}/c-{item['Id']}-{item['MediaSources'][0]['Id']}-stream.ts", "c"

def verify_content(Item, MediaType):
    if 'Path' not in Item:
        xbmc.log(f"EMBY.core.common: Path not found in Item {Item['Id']}", 3) # LOGERROR
        return False

    if 'MediaSources' not in Item or not Item['MediaSources']:
        xbmc.log(f"EMBY.core.common: No mediasources found for {MediaType}: {Item['Id']}", 3) # LOGERROR
        xbmc.log(f"EMBY.core.common: No mediasources found for {MediaType}: {Item}", 0) # LOGDEBUG
        return False

    if len(Item['MediaSources']) > 0:
        if 'MediaStreams' not in Item['MediaSources'][0] or not Item['MediaSources'][0]['MediaStreams']:
            xbmc.log(f"EMBY.core.common: No mediastreams found for {MediaType}: {Item['Id']} / {Item.get('Path', '')}", 2) # LOGWARNING
            xbmc.log(f"EMBY.core.common: No mediastreams found for {MediaType}: {Item}", 0) # LOGDEBUG
    else:
        xbmc.log(f"EMBY.core.common: Empty mediasources found for {MediaType}: {Item['Id']}", 3) # LOGERROR
        xbmc.log(f"EMBY.core.common: Empty mediasources found for {MediaType}: {Item}", 0) # LOGDEBUG
        return False

    return True

def load_tvchannel(Item, ServerId):
    Item['CurrentProgram'] = Item.get('CurrentProgram', {})

    if 'Name' in Item['CurrentProgram']:
        Item['Name'] = f"{Item['Name']} / {Item['CurrentProgram']['Name']}"

    Item['CurrentProgram']['Genres'] = Item['CurrentProgram'].get('Genres', [])
    set_RunTimeTicks(Item)
    set_playstate(Item)
    get_streams(Item)
    set_common(Item, ServerId, True)

def set_Favorite(Item):
    IsFavorite = False

    if "UserData" in Item and "IsFavorite" in Item['UserData'] and Item['UserData']['IsFavorite']:
        IsFavorite = Item['UserData']['IsFavorite']

    return IsFavorite

def get_PresentationUniqueKey(Item):
    if 'PresentationUniqueKey' in Item and Item['PresentationUniqueKey']:
        Item['PresentationUniqueKey'] = Item['PresentationUniqueKey'].replace("-", "_").replace(" ", "")
    else:
        Item['PresentationUniqueKey'] = None

def set_ItemsDependencies(Item, SQLs, WorkerObject, EmbyServer, EmbyType):
    AddSubItem = False
    SubItemId = f'{EmbyType}Id'

    if SubItemId not in Item or not Item[SubItemId]:
        AddSubItem = True
    else:
        if not SQLs["emby"].get_item_exists_by_id(Item[SubItemId], EmbyType):
            EmbyItem = EmbyServer.API.get_Item(Item[SubItemId], [EmbyType], False, False, False)

            if EmbyItem:
                EmbyItem['LibraryId'] = Item['LibraryId']
                WorkerObject.change(EmbyItem)
            else:
                AddSubItem = True

    if AddSubItem:
        Item[SubItemId] = None

        if Item['PresentationUniqueKey']:
            Pos = Item['PresentationUniqueKey'].rfind("_")

            if Pos != -1:
                SearchPresentationUniqueKey = Item['PresentationUniqueKey'][:Pos]
                Item[SubItemId] = SQLs["emby"].get_EmbyId_by_EmbyPresentationKey(SearchPresentationUniqueKey)
                xbmc.log(f"EMBY.core.common: Detect by PresentationUniqueKey: {Item['PresentationUniqueKey']} / {Item[SubItemId]}", 1) # LOGINFO

        if not Item[SubItemId]:
            Item[SubItemId] = MappingIds[EmbyType]

            if EmbyType == "MusicAlbum":
                Item[SubItemId] = f"{Item[SubItemId]}{Item['Id']}"

                if 'AlbumArtists' in Item and Item['AlbumArtists']:
                    WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": Item['Name'], "SortName": Item['Name'], "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None, "AlbumArtists": Item['AlbumArtists'], "ArtistItems": [], "AlbumArtist": Item['AlbumArtist']})
                else:
                    WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": Item['Name'], "SortName": Item['Name'], "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None, "AlbumArtists": Item['ArtistItems'], "ArtistItems": [], "AlbumArtist": Item['MusicArtist']})
            elif EmbyType == "Season":
                Item["SeasonId"] = f"{Item[SubItemId]}{Item['Id']}"
                WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item["SeasonId"], "SeriesId": Item["SeriesId"], "Name": "--NO INFO--", "SortName": "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None})
            else:
                WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": "--NO INFO--", "SortName": "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}, 'Path': Item.get('Path', "/--NO INFO--/--NO INFO--/"), 'ParentId': None})

def set_MusicGenre_links(KodiItemId, SQLs, KodiType, MetaDataItems, Index):
    for Order, MetaDataItem in enumerate(MetaDataItems):
        MetaDataItemKodiIds = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "MusicGenre")[1]
        MetaDataItemKodiIds = MetaDataItemKodiIds.split(";")

        if Index == 0:
            SQLs["video"].add_genre_link(MetaDataItemKodiIds[0], KodiItemId, KodiType)
        else:
            SQLs["music"].add_genre_link(MetaDataItemKodiIds[1], KodiItemId, Order)

def set_Genre_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for MetaDataItem in MetaDataItems:
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Genre")[1]
        SQLs["video"].add_genre_link(MetaDataItemKodiId, KodiItemId, KodiType)

def set_Writer_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for MetaDataItem in MetaDataItems:
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Person")[1]
        SQLs["video"].add_writer_link(MetaDataItemKodiId, KodiItemId, KodiType)

def set_Director_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for MetaDataItem in MetaDataItems:
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Person")[1]
        SQLs["video"].add_director_link(MetaDataItemKodiId, KodiItemId, KodiType)

def set_Studio_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for MetaDataItem in MetaDataItems:
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Studio")[1]
        SQLs["video"].add_studio_link(MetaDataItemKodiId, KodiItemId, KodiType)

def set_Tag_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for MetaDataItem in MetaDataItems:
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Tag")[1]
        SQLs["video"].add_tag_link(MetaDataItemKodiId, KodiItemId, KodiType)

def set_Actor_links(KodiItemId, SQLs, KodiType, MetaDataItems):
    for Order, MetaDataItem in enumerate(MetaDataItems):
        MetaDataItemKodiId = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "Person")[1]
        SQLs["video"].add_actor_link(MetaDataItemKodiId, KodiItemId, KodiType, MetaDataItem["Role"], Order)

def set_Actor_MusicArtist_links(KodiItemId, SQLs, KodiType, MetaDataItems, LibraryId):
    for Order, MetaDataItem in enumerate(MetaDataItems):
        ArtistData = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "MusicArtist")
        MetaDataItemKodiId = ArtistData[1].split(";")[0]
        MetaDataItemKodiId = MetaDataItemKodiId.split(",")
        MetaDataItemLibraryId = ArtistData[3].split(";")[0]
        MetaDataItemLibraryId = MetaDataItemLibraryId.split(",")
        Index = MetaDataItemLibraryId.index(LibraryId)
        SQLs["video"].add_actor_link(MetaDataItemKodiId[Index], KodiItemId, KodiType, None, Order)

def set_MusicArtist_links(KodiItemId, SQLs, MetaDataItems, LibraryId, ArtistRole):
    for Order, MetaDataItem in enumerate(MetaDataItems):
        ArtistData = SQLs["emby"].get_item_by_id(MetaDataItem['Id'], "MusicArtist")
        MetaDataItemKodiId = ArtistData[1].split(";")[1]
        MetaDataItemKodiId = MetaDataItemKodiId.split(",")
        MetaDataItemLibraryId = ArtistData[3].split(";")[1]
        MetaDataItemLibraryId = MetaDataItemLibraryId.split(",")
        Index = MetaDataItemLibraryId.index(LibraryId)

        if ArtistRole:
            SQLs["music"].add_musicartist_link(MetaDataItemKodiId[Index], KodiItemId, ArtistRole, Order, MetaDataItem['Name'])
        else:
            SQLs["music"].add_albumartist_link(MetaDataItemKodiId[Index], KodiItemId, Order, MetaDataItem['Name'])

def set_MetaItems(Item, SQLs, WorkerObject, EmbyServer, EmbyType, MetaDataId, LibraryId=None, Index=-1):
    AddSubItem = False
    Names = ()

    if MetaDataId not in Item or not Item[MetaDataId]:
        AddSubItem = True
    else:
        for MetaItem in Item[MetaDataId]:
            if Index != -1:
                Exists = SQLs["emby"].get_item_exists_multi_db(MetaItem['Id'], EmbyType, LibraryId, Index)
            else:
                Exists = SQLs["emby"].get_item_exists_by_id(MetaItem['Id'], EmbyType)

            if Exists:
                Names += (MetaItem['Name'],)
                continue

            EmbyItem = EmbyServer.API.get_Item(MetaItem["Id"], [EmbyType], False, False, False)

            if EmbyItem:
                Names += (MetaItem['Name'],)
                EmbyItem['LibraryId'] = Item['LibraryId']
                WorkerObject.change(EmbyItem)
                continue

            AddSubItem = True

    if AddSubItem:
        Names += ("--NO INFO--",)
        AddSubItemId = MappingIds[EmbyType]
        WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": AddSubItemId, "Name": "--NO INFO--", 'SortName': "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}})
        Item[MetaDataId] = [{"Name": "--NO INFO--", "Id": AddSubItemId, "Memo": f"no info {EmbyType}"}]

    if EmbyType == "MusicGenre":
        Item["MusicGenreItems"] = Item["GenreItems"]

    Item[EmbyType] = " / ".join(Names)

def set_people(Item, SQLs, PersonObject, EmbyServer):
    Item['WritersItems'] = ()
    Item['DirectorsItems'] = ()
    Item['CastItems'] = ()
    Writers = ()
    Directors = ()

    if "People" in Item:
        for People in Item['People']:
            if 'Name' in People:
                if not SQLs["emby"].get_item_exists_by_id(People['Id'], "Person"):
                    EmbyItem = EmbyServer.API.get_Item(People['Id'], ["Person"], False, False, False)

                    if EmbyItem:
                        EmbyItem['LibraryId'] = Item['LibraryId']
                        PersonObject.change(EmbyItem)
                    else:
                        continue

                if People['Type'] == "Writer":
                    Item['WritersItems'] += ({"Name": People['Name'], "Id": People['Id'], "KodiType": "actor"},)
                    Writers += (People['Name'],)
                elif People['Type'] == "Director":
                    Item['DirectorsItems'] += ({"Name": People['Name'], "Id": People['Id'], "KodiType": "actor"},)
                    Directors += (People['Name'],)
                elif People['Type'] == "Actor":

                    if 'Role' in People:
                        role = People['Role']
                    else:
                        role = People['Type']

                    Item['CastItems'] += ({"Name": People['Name'], "Id": People['Id'], "KodiType": "actor", "Role": role},)

    if Writers:
        Item['Writers'] = " / ".join(Writers)
    else:
        Item['Writers'] = None

    if Directors:
        Item['Directors'] = " / ".join(Directors)
    else:
        Item['Directors'] = None

def get_MusicArtistInfos(Item, ArtistType, SQLs):
    Artists = []
    SortNames = []
    KodiIds = []

    for ArtistItem in Item[ArtistType]:
        Artists.append(ArtistItem['Name'])
        ArtistItem['KodiId'] = SQLs["emby"].get_KodiId_by_EmbyId_multi_db(ArtistItem['Id'], "MusicArtist", "music")
        KodiIds.append(ArtistItem['KodiId'])
        SortNames.append(SQLs["music"].get_ArtistSortname(ArtistItem['KodiId']))

    Item[f"{ArtistType}SortName"] = " / ".join(SortNames)
    Item[f"{ArtistType}Name"] = " / ".join(Artists)
    Item[f"{ArtistType}KodiId"] = ",".join(KodiIds)

def update_multiversion(EmbyDB, Item, EmbyType):
    if not Item['LibraryId']:
        StackedIds = EmbyDB.get_EmbyIds_by_EmbyPresentationKey(Item['PresentationUniqueKey'], EmbyType)

        if StackedIds: # multi version force update
            xbmc.log(f"EMBY.core.common: DELETE multi version {EmbyType} from embydb {Item['Id']}", 1) # LOGINFO

            for StackedId in StackedIds:
                EmbyDB.add_RemoveItem(StackedId[0], None)
                EmbyDB.add_UpdateItem(StackedId[0], EmbyType, "unknown")

def set_Favorites_Artwork(Item, ServerId):
    if 'ImageTags' in Item and Item['ImageTags']:
        if "Primary" in Item['ImageTags']:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id']}-0-p-{Item['ImageTags']['Primary']}|redirect-limit=1000"

        if "Thumb" in Item['ImageTags']:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id']}-0-p-{Item['ImageTags']['Thumb']}|redirect-limit=1000"

    return None

def update_downloaded_info(Item, SQLs):
    if SQLs["emby"].get_DownloadItem_exists_by_id(Item['Id']):
        Item['KodiName'] = f"{Item['Name']} (download)"

        if "SortName" in Item and Item["SortName"]:
            Item['KodiSortName'] = f"{Item['SortName']} (download)"

        for KodiArtworkId, KodiArtworkUrl in list(Item['KodiArtwork'].items()):
            if KodiArtworkId in ("poster", "thumb", "landscape") and KodiArtworkUrl:
                KodiArtworkUrlMod = KodiArtworkUrl.split("|")
                KodiArtworkUrlMod = f"{KodiArtworkUrlMod[0].replace('-download', '')}-download|redirect-limit=1000"
                Item['KodiArtwork'][KodiArtworkId] = KodiArtworkUrlMod

        return True

    Item['KodiName'] = Item['Name']

    if "SortName" in Item and Item["SortName"]:
        Item['KodiSortName'] = Item["SortName"]

    return False

import base64
from urllib.parse import quote
import xbmc
from helper import utils
EmbyTypeMappingShort = {"Movie": "m", "Episode": "e", "MusicVideo": "M", "Audio": "a", "Video": "v", "TvChannel": "t", "Trailer": "T"}
EmbyArtworkIdShort = {"Primary": "p", "Art": "a", "Banner": "b", "Disc": "d", "Logo": "l", "Thumb": "t", "Backdrop": "B", "Chapter": "c", "SeriesPrimary": "p", "AlbumPrimary": "p", "ParentBackdrop": "B", "ParentThumb": "t", "ParentLogo": "l", "ParentBanner": "b", "AlbumArtists": "p", "ArtistItems": "p"}
MarkerTypeMapping = {"IntroStart": "Intro Start", "IntroEnd": "Intro End", "CreditsStart": "Credits"}
MappingIds = {'Season': "999999989", 'Series': "999999990", 'MusicAlbum': "999999991", 'MusicGenre': "999999992", "Studio": "999999994", "Tag": "999999993", "Genre": "999999995", "MusicArtist": "999999996"}
ImageTagsMappings = {
    "Series": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Backdrop", 'landscape'), ("Primary", 'landscape')),
    "Season": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ('SeriesPrimary', 'poster'), ("ParentThumb", 'thumb'), ("Primary", 'thumb'), ("ParentLogo", 'clearlogo'), ("ParentBackdrop", 'fanart')),
    "Episode": (('Primary', 'thumb'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ("ParentLogo", 'clearlogo'), ("ParentBanner", 'banner'), ("ParentThumb", 'landscape'), ("ParentThumb", 'thumb'), ("ParentBackdrop", 'landscape'), ("ParentBackdrop", 'fanart'), ('Primary', 'landscape'), ('SeriesPrimary', 'thumb')),
    "Movie": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'thumb'), ("Backdrop", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape')),
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
    "Person": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Thumb", 'thumb'), ("Thumb", 'landscape'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Primary", 'landscape')),
    "Genre": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "MusicGenre": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "Tag": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape')),
    "Studio": (('Primary', 'poster'), ("Art", 'clearart'), ("Banner", 'banner'), ("Disc", 'discart'), ("Logo", 'clearlogo'), ("Thumb", 'thumb'), ("Backdrop", 'fanart'), ('Primary', 'thumb'), ("Thumb", 'landscape'), ("Primary", 'landscape'))
}


def load_ExistingItem(Item, EmbyServer, emby_db, EmbyType):
    if Item['LibraryId'] not in EmbyServer.library.LibrarySyncedNames:
        xbmc.log(f"EMBY.core.common: Library not synced: {Item['LibraryId']}", 3) # LOGERROR
        return False

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
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiFileId": ExistingItem[3], "KodiParentId": ExistingItem[4], "EmbyPresentationKey": ExistingItem[5], "EmbyFolder": ExistingItem[6], "KodiPathId": ExistingItem[7]})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "KodiParentId": None, "EmbyPresentationKey": None, "EmbyFolder": None, "KodiFileId": None, "KodiPathId": None})

        return True

    if EmbyType == "Season":
        if ExistingItem:
            Item.update({'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiParentId": ExistingItem[3], "EmbyPresentationKey": ExistingItem[4]})
        else:
            Item.update({'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "KodiParentId": None, "EmbyPresentationKey": None})

        return True

    LibrarySyncedName = EmbyServer.library.LibrarySyncedNames[Item['LibraryId']]

    if EmbyType in ("Movie", "MusicVideo"):
        if not ForceNew and ExistingItem:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiFileId": ExistingItem[3], "EmbyPresentationKey": ExistingItem[4], "EmbyFolder": ExistingItem[5], "KodiPathId": ExistingItem[6]})
        else:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyPresentationKey": None, "EmbyFolder": None, "KodiFileId": None, "KodiPathId": None})

        return True

    if EmbyType == "Video":
        if not ForceNew and ExistingItem:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "KodiFileId": ExistingItem[3], "EmbyPresentationKey": ExistingItem[4], "EmbyFolder": ExistingItem[5], "KodiPathId": ExistingItem[6], "isSpecial": ExistingItem[7]})
        else:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyPresentationKey": None, "EmbyFolder": None, "KodiFileId": None, "KodiPathId": None, "isSpecial": False})

        return True

    if EmbyType == "Series":
        if ExistingItem:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "EmbyPresentationKey": ExistingItem[3], "KodiPathId": ExistingItem[4]})
        else:
            Item.update({"LibraryName": LibrarySyncedName, 'KodiItemId': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyPresentationKey": None, "KodiPathId": None,})

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
            Item.update({'KodiItemIds': ExistingItem[1], 'UpdateItem': True, "EmbyFavourite": ExistingItem[2], "EmbyFolder": ExistingItem[3], "KodiPathId": ExistingItem[4], "LibraryIds": ExistingItem[5], "MusicAlbumIdExisting": ExistingItem[6]})
        else:
            Item.update({'KodiItemIds': "", 'UpdateItem': False, "EmbyFavourite": None, "EmbyFolder": None, "KodiPathId": None, "LibraryIds": "", "MusicAlbumIdExisting": None})

        return True

    xbmc.log(f"EMBY.core.common: EmbyType invalid: {EmbyType}", 3) # LOGERROR
    return False

def get_Bitrate_Codec(Item, StreamType, MediaSource):
    Bitrate = 0
    Codec = ""

    if MediaSource['KodiStreams'][StreamType]:
        if 'BitRate' in MediaSource['KodiStreams'][StreamType][0]:
            Bitrate = MediaSource['KodiStreams'][StreamType][0]['BitRate']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Bitrate found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING

        if 'codec' in MediaSource['KodiStreams'][StreamType][0]:
            Codec = MediaSource['KodiStreams'][StreamType][0]['codec']
        else:
            xbmc.log(f"EMBY.core.common: No {StreamType} Codec found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING
    else:
        xbmc.log(f"EMBY.core.common: No Streams Bitrate found: {Item['Id']} {Item['Name']}", 2) # LOGWARNING

    if not Bitrate:
        Bitrate = 0

    if not Codec:
        Codec = ""

    return Bitrate, Codec

def set_path_filename(Item, ServerId, MediaSource, isDynamic=False):
    Item['KodiFullPath'] = ""
    isHttp = False

    if Item.get('NoLink'):
        return

    if isDynamic:
        Dynamic = "dynamic/"
        Item['LibraryId'] = "0"
    else:
        Dynamic = ""

    if Item['Type'] in ('Photo', 'PhotoAlbum'):
        if 'Primary' in Item['ImageTags']:
            if 'Path' in Item:
                Item['KodiFullPath'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id']}-0-p-{Item['ImageTags']['Primary']}--{quote(utils.get_Filename(Item['Path'], ''))}|redirect-limit=1000"
                return

            Item['KodiFullPath'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id']}-0-p-{Item['ImageTags']['Primary']}|redirect-limit=1000"
            return

        Item['KodiFullPath'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id']}-0-p-0|redirect-limit=1000"
        return

    NativeMode = utils.useDirectPaths
    Item['KodiStackedFilename'] = None
    MediaSourcesLocal = Item.get('MediaSources', [])

    if MediaSource and "Path" in MediaSource: # Multiversion content supported by Kodi (Movies)
        MediaSourcesLocal = (MediaSource,)
        Path = MediaSource['Path']
    elif 'MediaSources' in Item and "Path" in Item['MediaSources'][0]:
        Path = Item['MediaSources'][0]['Path']
    elif 'Path' in Item:
        Path = Item['Path']
    else:
        Path = ""
        xbmc.log(f"EMBY.core.common: No path found: {Item['Type']} / {Item['Name']}", 1) # LOGINFO

    Item['KodiPath'] = Path

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

    KodiPathLower = Item['KodiPath'].lower()
    Container = Item.get('Container', "")

    if Container == 'dvd':
        Item['KodiPath'] += "/VIDEO_TS/"
        Item['KodiFilename'] = "VIDEO_TS.IFO"
        Item['KodiFullPath'] = f"{Item['KodiPath']}{Item['KodiFilename']}"
        return

    if Container == 'bluray':
        Item['KodiPath'] += "/BDMV/"
        Item['KodiFilename'] = "index.bdmv"
        Item['KodiFullPath'] = f"{Item['KodiPath']}{Item['KodiFilename']}"
        return

    if KodiPathLower.startswith("plugin://"):
        Item['KodiFilename'] = Item['KodiPath']
        Item['KodiFullPath'] = Item['KodiPath']
        return

    if Item['KodiPath']:
        Item['KodiFilename'] = utils.get_Filename(Item['KodiPath'], NativeMode)
    else: # channels
        Item['KodiFilename'] = "unknown"
        NativeMode = False

    if Container == 'iso' or KodiPathLower.endswith(".iso"):
        NativeMode = True
    elif KodiPathLower.startswith("dav://"):
        NativeMode = True
    elif KodiPathLower.startswith("http://") or KodiPathLower.startswith("https://"):
        NativeMode = False
        Dynamic += "http/"
        isHttp = True

        if 'Container' in Item:
            Item['KodiFilename'] = f"unknown.{Item['Container']}"
        else:
            Item['KodiFilename'] = "unknown"

    if NativeMode:
        PathSeperator = utils.get_Path_Seperator(Item['KodiPath'])
        Temp = Item['KodiPath'].rsplit(PathSeperator, 1)[1]

        if Item['Type'] == "Series":
            Item['KodiPathParent'] = f"{Item['KodiPath'].replace(Temp, '')}"
            Item['KodiPath'] += PathSeperator
        else:
            Item['KodiPath'] = f"{Item['KodiPath'].replace(Temp, '')}"
    else:
        if Item['Type'] == "Audio": # Do NOT use different pathes for Audio content, a Kodi audio scan would take very long -> Kodi audio scan does not respect the directory paramerter -> jsonrpc AudioLibrary.Scan
            if MediaSourcesLocal and "Id" in MediaSourcesLocal[0]:
                Item['KodiFilename'] = f"a-{Item['Id']}-{MediaSourcesLocal[0]['Id']}-{base64.b16encode(Item['KodiPath'].encode('utf-8')).decode('utf-8')}-{quote(Item['KodiFilename'].replace('-', '_'))}"
            else:
                Item['KodiFilename'] = f"a-{Item['Id']}--{base64.b16encode(Item['KodiPath'].encode('utf-8')).decode('utf-8')}-{quote(Item['KodiFilename'].replace('-', '_'))}"

            Item['KodiPath'] = f"http://127.0.0.1:57342/{Dynamic}audio/{ServerId}/{Item['LibraryId']}/0/"
        elif Item['Type'] in EmbyTypeMappingShort:
            HasSpecials = ""
            MediaID = EmbyTypeMappingShort[Item['Type']]

            if 'SpecialFeatureCount' in Item:
                if int(Item['SpecialFeatureCount']):
                    HasSpecials = "s"

            MetaFolder = f"{MediaID}-{Item.get('KodiItemId', 0)}-{Item.get('KodiFileId', 0)}-{HasSpecials}"
            MetadataSub = []

            # Encode metatdata, sperators are <>, ><, <<, :
            for MediaSourceItem in MediaSourcesLocal:
                IsRemote = MediaSourceItem.get('IsRemote', "false")

                if IsRemote == "true":
                    IsRemote = "1"
                else:
                    IsRemote = "0"

                MediasourceString = f"{MediaSourceItem.get('Name', 'unknown').replace(':', '<;>')}:{MediaSourceItem['Size'] or 0}:{MediaSourceItem['Id']}:{MediaSourceItem['Path'].replace(':', '<;>')}:{MediaSourceItem['IntroStartPositionTicks']}:{MediaSourceItem['IntroEndPositionTicks']}:{MediaSourceItem['CreditsPositionTicks']}:{IsRemote}"
                SubData = [[], [], []]

                for KodiVideoStream in MediaSourceItem['KodiStreams']['Video']:
                    SubData[0].append(f"{KodiVideoStream['codec'].replace(':', '<;>')}:{KodiVideoStream['BitRate'] or 0}:{KodiVideoStream['Index']}:{KodiVideoStream['width'] or 0}")

                for KodiAudioStream in MediaSourceItem['KodiStreams']['Audio']:
                    SubData[1].append(f"{KodiAudioStream['DisplayTitle'].replace(':', '<;>')}:{KodiAudioStream['codec'].replace(':', '<;>')}:{KodiAudioStream['BitRate'] or 0}:{KodiAudioStream['Index']}")

                for KodiSubtitleStream in MediaSourceItem['KodiStreams']['Subtitle']:
                    SubData[2].append(f"{KodiSubtitleStream['language'].replace(':', '<;>')}:{KodiSubtitleStream['DisplayTitle'].replace(':', '<;>')}:{KodiSubtitleStream['external']}:{KodiSubtitleStream['Index']}:{KodiSubtitleStream['codec'].replace(':', '<;>')}")

                SubData[0] = "><".join(SubData[0])
                SubData[1] = "><".join(SubData[1])
                SubData[2] = "><".join(SubData[2])
                MetadataSub.append(f"{MediasourceString}<<{'<<'.join(SubData)}")

            MetadataSub = "<>".join(MetadataSub)
            MetadataSub = base64.b16encode(MetadataSub.encode('utf-8')).decode('utf-8')
            MetaFolder += f"-{MetadataSub}"

        if Item['Type'] == "Series":
            Item['KodiPathParent'] = f"{utils.AddonModePath}{Dynamic}tvshows/{ServerId}/{Item['LibraryId']}/"
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}tvshows/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/"
        elif Item['Type'] == "Episode":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}tvshows/{ServerId}/{Item['LibraryId']}/{Item['SeriesId']}/{Item['Id']}/{MetaFolder}/"
        elif Item['Type'] == "Movie":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}movies/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/{MetaFolder}/"
        elif Item['Type'] == "Video":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}video/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/{MetaFolder}/"
        elif Item['Type'] == "MusicVideo":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}musicvideos/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/{MetaFolder}/"
        elif Item['Type'] == "TvChannel":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}livetv/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/{MetaFolder}/"
        elif Item['Type'] == "Trailer":
            Item['KodiPath'] = f"{utils.AddonModePath}{Dynamic}trailer/{ServerId}/{Item['LibraryId']}/0/{Item['Id']}/{MetaFolder}/"

    if isHttp and utils.followhttp:
        Item['KodiPath'] = Item['KodiPath'].replace("/emby_addon_mode/", "http://127.0.0.1:57342/")
        Item['KodiFilename'] += f"|connection-timeout={utils.followhttptimeout}"

    Item['KodiFullPath'] = f"{Item['KodiPath']}{Item['KodiFilename']}"

# Detect Multipart videos
def set_multipart(Item, EmbyServer):
    if 'PartCount' in Item and EmbyServer.API:
        if Item['PartCount'] >= 2:
            AdditionalParts = EmbyServer.API.get_additional_parts(Item['Id'])

            if Item['KodiRunTimeTicks']:
                Value = float(Item['KodiRunTimeTicks'])
                StackedKodiRunTimeTicks = (str(Value),)
                StackedKodiRunTimeTicksSum = Value
            else:
                StackedKodiRunTimeTicks = ("0",)
                StackedKodiRunTimeTicksSum = 0

            Item.update({'KodiPath': Item['KodiPath'].replace(',', ' '), 'KodiFilename': Item['KodiFilename'].replace(',', ' ')})
            StackedFilenames = (f"{Item['KodiPath']}{Item['KodiFilename']}",)

            for AdditionalItem in AdditionalParts['Items']:
                set_streams(AdditionalItem)
                set_chapters(AdditionalItem, EmbyServer.ServerData['ServerId'])
                AdditionalItem.update({'KodiItemId': Item['KodiItemId'], 'KodiFileId': Item['KodiFileId'], 'KodiPath': Item['KodiPath'], 'LibraryId': Item['LibraryId']})
                set_path_filename(AdditionalItem, EmbyServer.ServerData['ServerId'], {}, False)
                set_streams(AdditionalItem)
                AdditionalItem.update({'KodiPath': AdditionalItem['KodiPath'].replace(',', ' '), 'KodiFilename': AdditionalItem['KodiFilename'].replace(',', ' ')})
                StackedFilenames += (f"{AdditionalItem['KodiPath']}{AdditionalItem['KodiFilename']}",)

                if 'RunTimeTicks' in AdditionalItem and AdditionalItem['RunTimeTicks']:
                    Value = round(float(AdditionalItem['RunTimeTicks'] / 10000000.0), 6)
                else:
                    Value = 0

                StackedKodiRunTimeTicksSum += Value
                StackedKodiRunTimeTicks += (str(StackedKodiRunTimeTicksSum),)

            if StackedKodiRunTimeTicksSum:
                Item['KodiRunTimeTicks'] = StackedKodiRunTimeTicksSum
            else:
                Item['KodiRunTimeTicks'] = None

            Item['KodiStackedFilename'] = f"stack://{' , '.join(StackedFilenames)}"
            Item['KodiStackTimes'] = ','.join(StackedKodiRunTimeTicks)
            Item['KodiPath'] = utils.AddonModePath

def set_streams(Item):
    if 'MediaSources' not in Item or not Item['MediaSources']:
        xbmc.log(f"EMBY.core.common: set_streams -> Mediasources not found: {Item['Name']}", 0) # LOGDEBUG
        return

    # Sort mediasources -> core infos must reference first mediasource
    if Item['MediaSources'][0]['Type'] != "Default":
        xbmc.log(f"EMBY.core.common: Sort -> First Mediasource is not default: {Item['Name']}", 0) # LOGDEBUG
        MediaSourcesLen = len(Item['MediaSources'])
        MediaSourcesSort = MediaSourcesLen * [None]
        Index = 1

        for MediaSource in Item['MediaSources']:
            if MediaSource['Type'] == "Default":
                MediaSourcesSort[0] = MediaSource
            else:
                if Index == MediaSourcesLen:
                    MediaSourcesSort[0] = MediaSource
                else:
                    MediaSourcesSort[Index] = MediaSource

                Index += 1

        Item['MediaSources'] = MediaSourcesSort

    # Streams
    for MediaSource in Item['MediaSources']:
        MediaSource['Path'] = MediaSource.get('Path', "")
        MediaSource['Size'] = MediaSource.get('Size', "")
        RunTimeTicks = MediaSource.get('RunTimeTicks', Item.get('RunTimeTicks', None))

        if RunTimeTicks:
            MediaSource['KodiRunTimeTicks'] = round(float(RunTimeTicks / 10000000.0), 6)
        else:
            MediaSource['KodiRunTimeTicks'] = None
            xbmc.log(f"EMBY.core.common: No Runtime found: {MediaSource.get('Id', '-1')}", 0) # LOGDEBUG

        MediaSource['KodiStreams'] = {'Subtitle': [], 'Audio': [], 'Video': []}

        for Stream in MediaSource['MediaStreams']:
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
                MediaSource['KodiStreams']['Audio'].append({'SampleRate': Stream.get('SampleRate', None), 'BitRate': Stream.get('BitRate', None), 'codec': Codec, 'channels': Stream.get('Channels', None), 'language': Stream.get('Language', None), 'Index': Stream.get('Index', "0"), 'DisplayTitle': Stream.get('DisplayTitle', "unknown").replace(chr(1), "").replace(chr(0), "")})
            elif Stream['Type'] == "Video":
                StreamData = {'language': Stream.get('Language', None),'hdrtype': None, 'codec': Codec, 'height': Stream.get('Height', None), 'width': Stream.get('Width', None), '3d': Stream.get('Video3DFormat', None), 'BitRate': Stream.get('BitRate', None), 'Index': Stream.get('Index', "0"), 'aspect': None}
                VideoRange = Stream.get('VideoRange', "").lower()

                if VideoRange == "hdr 10":
                    StreamData['hdrtype'] = "hdr10"
                elif VideoRange in ("hlg", "dolbyvision"):
                    StreamData['hdrtype'] = VideoRange

                if "AspectRatio" in Stream:
                    AspectRatio = Stream['AspectRatio'].split(':')

                    if len(AspectRatio) != 2:
                        xbmc.log(f"EMBY.core.common: AspectRatio detected by alternative method: {Item['Id']} / {Item['Name']}", 2) # LOGWARNING
                        AspectRatio = Stream['AspectRatio'].split('/')

                    if len(AspectRatio) == 2 and utils.is_number(AspectRatio[0]) and utils.is_number(AspectRatio[1]) and float(AspectRatio[1]) > 0:
                        StreamData['aspect'] = round(float(AspectRatio[0]) / float(AspectRatio[1]), 6)

                if not StreamData['aspect']:
                    xbmc.log(f"EMBY.core.common: AspectRatio not detected: {Item['Id']} / {Item['Name']}", 2) # LOGWARNING

                    if 'Height' in Stream and Stream['Height'] and 'Width' in Stream and Stream['Width']:
                        StreamData['aspect'] = round(float(Stream['Width']) / float(Stream['Height']), 6)
                        xbmc.log(f"EMBY.core.common: AspectRatio calculated based on width/height ratio: {Stream['Height']} / {Stream['Height']} / {StreamData['aspect']}", 1) # LOGINFO

                MediaSource['KodiStreams']['Video'].append(StreamData)
            elif Stream['Type'] == "Subtitle":
                IsExternal = Stream.get('IsExternal', False)

                if IsExternal:
                    IsExternal = "1"
                else:
                    IsExternal = "0"

                MediaSource['KodiStreams']['Subtitle'].append({'Index': Stream.get('Index', "0"), 'language': Stream.get('Language', "undefined"), 'DisplayTitle': Stream.get('DisplayTitle', "undefined").replace(chr(1), "").replace(chr(0), ""), 'codec': Codec, 'external': IsExternal})

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
            set_streams(IntroLocal)
            set_chapters(IntroLocal, EmbyServer.ServerData['ServerId'])
            set_path_filename(IntroLocal, EmbyServer.ServerData['ServerId'], {}, True)
            Item['Trailer'] = IntroLocal['KodiFullPath']
            return

    if 'RemoteTrailers' in Item and Item['RemoteTrailers']:
        if 'Url' in Item['RemoteTrailers'][0]:
            if Item['RemoteTrailers'][0]['Url'].lower().find("youtube") != -1:
                try:
                    Item['Trailer'] = f"plugin://plugin.video.youtube/play/?video_id={Item['RemoteTrailers'][0]['Url'].rsplit('=', 1)[1]}"
                except Exception as Error:
                    xbmc.log(f"EMBY.core.common: Trailer not valid: {Item['Name']} / {Error}", 3) # LOGERROR
            else:
                Item['Trailer'] = Item['RemoteTrailers'][0]['Url']

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

def set_DateCreated(Item):
    if 'DateCreated' in Item:
        Item['KodiDateCreated'] = utils.convert_to_local(Item['DateCreated'])
    else:
        Item['KodiDateCreated'] = None

def set_common(Item, ServerId, DynamicNode):
    Item['ProductionLocations'] = Item.get('ProductionLocations', [])
    set_DateCreated(Item)

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

    if "CriticRating" in Item:
        Item['KodiCriticRating'] = float(Item['CriticRating'] / 10.0)
    else:
        Item['KodiCriticRating'] = None

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
    set_PresentationUniqueKey(Item)
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
                    ArtistItem['imageurl'] = ""

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
        Item['KodiPremiereDate'] = Item['KodiProductionYear']

    if not Item['KodiProductionYear'] and Item['KodiPremiereDate']:
        Item['KodiProductionYear'] = Item['KodiPremiereDate']

    if Item['KodiProductionYear']:
        Item['KodiProductionYear'] = Item['KodiProductionYear'][:4]

def set_chapters(Item, ServerId):
    if 'MediaSources' not in Item:
        return

    MediaSourcesChapters = False

    for MediaSource in Item['MediaSources']:
        if 'Chapters' in MediaSource:
            MediaSourcesChapters = True
            break

    xbmc.log(f"EMBY.core.common: Use items chapterimages {MediaSourcesChapters}", 0) # LOGDEBUG -> Emby 4.8 compatibility

    for MediaSourceIndex, MediaSource in enumerate(Item['MediaSources']):
        MediaSource['KodiChapters'] = {}
        MediaSource['IntroStartPositionTicks'] = 0
        MediaSource['IntroEndPositionTicks'] = 0
        MediaSource['CreditsPositionTicks'] = 0

        if MediaSourcesChapters:
            if 'Chapters' in MediaSource: # Chapters by mediasource
                for Index, Chapter in enumerate(MediaSource['Chapters']):
                    load_chapter(MediaSource, Chapter, Index, ServerId, Item['Id'])
        else:
            if 'Chapters' in Item and MediaSourceIndex == 0: # load chapters by item
                for Index, Chapter in enumerate(Item['Chapters']):
                    load_chapter(MediaSource, Chapter, Index, ServerId, Item['Id'])
            else: # copy global KodiChapters to all MediaSources
                MediaSource['KodiChapters'] = Item['MediaSources'][0]['KodiChapters']
                MediaSource['IntroStartPositionTicks'] = Item['MediaSources'][0]['IntroStartPositionTicks']
                MediaSource['IntroEndPositionTicks'] = Item['MediaSources'][0]['IntroEndPositionTicks']
                MediaSource['CreditsPositionTicks'] = Item['MediaSources'][0]['CreditsPositionTicks']

def load_chapter(MediaSource, Chapter, Index, ServerId, ItemId):
    MarkerLabel = ""
    Chapter["StartPositionTicks"] = round(float(Chapter.get("StartPositionTicks", 0) / 10000000))
    Id = MediaSource.get('ItemId', ItemId)

    if "MarkerType" in Chapter and (Chapter['MarkerType'] == "IntroStart" or Chapter['MarkerType'] == "IntroEnd" or Chapter['MarkerType'] == "CreditsStart"):
        if Chapter['MarkerType'] == "IntroStart":
            MediaSource['IntroStartPositionTicks'] = Chapter["StartPositionTicks"]
        elif Chapter['MarkerType'] == "IntroEnd":
            MediaSource['IntroEndPositionTicks'] = Chapter["StartPositionTicks"]
        elif Chapter['MarkerType'] == "CreditsStart":
            MediaSource['CreditsPositionTicks'] = Chapter["StartPositionTicks"]

        MarkerLabel = quote(MarkerTypeMapping[Chapter['MarkerType']])

        if "ImageTag" in Chapter:
            ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Id}-{Index}-c-{Chapter['ImageTag']}-{MarkerLabel}|redirect-limit=1000"
        else: # inject blank image, otherwise not possible to use text overlay (webservice.py)
            ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Id}-{Index}-c-noimage-{MarkerLabel}|redirect-limit=1000"
    else:
        if "Name" in Chapter:
            Chapter['Name'] = Chapter['Name'].replace("-", " ")

            if Chapter['Name'] == "Title Sequence" or Chapter['Name'] == "End Credits" or Chapter['Name'] == "Intro Start" or Chapter['Name'] == "Intro End":
                if Chapter['Name'] == "Intro Start" and not MediaSource['IntroStartPositionTicks']:
                    MediaSource['IntroStartPositionTicks'] = Chapter["StartPositionTicks"]
                elif Chapter['Name'] == "Intro End" and not MediaSource['IntroEndPositionTicks']:
                    MediaSource['IntroEndPositionTicks'] = Chapter["StartPositionTicks"]
                elif Chapter['Name'] == "End Credits" and not MediaSource['CreditsPositionTicks']:
                    MediaSource['CreditsPositionTicks'] = Chapter["StartPositionTicks"]

                MarkerLabel = quote(Chapter['Name'])
            elif " 0" in Chapter['Name'] or Chapter["StartPositionTicks"] % 300 != 0: # embedded chapter
                return
        else:
            Chapter["Name"] = "unknown"

        if "ImageTag" in Chapter:
            ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Id}-{Index}-c-{Chapter['ImageTag']}-{quote(Chapter['Name'])}|redirect-limit=1000"
        else:
            ChapterImage = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Id}-{Index}-c-noimage-{quote(Chapter['Name'])}|redirect-limit=1000"

    if Chapter["StartPositionTicks"] not in MediaSource['KodiChapters']:
        MediaSource['KodiChapters'][Chapter["StartPositionTicks"]] = ChapterImage
    else:
        # replace existing chapter label with marker label
        if MarkerLabel:
            Data = MediaSource['KodiChapters'][Chapter["StartPositionTicks"]].split("-")
            Data[5] = MarkerLabel
            MediaSource['KodiChapters'][Chapter["StartPositionTicks"]] = "-".join(Data)

# Set Kodi artwork
def set_KodiArtwork(Item, ServerId, DynamicNode):
    Item['ParentLogoItemId'] = Item.get('ParentLogoItemId', None)
    Item['ParentLogoImageTag'] = Item.get('ParentLogoImageTag', None)
    Item['ParentThumbItemId'] = Item.get('ParentThumbItemId', None)
    Item['ParentThumbImageTag'] = Item.get('ParentThumbImageTag', None)
    Item['ParentBackdropItemId'] = Item.get('ParentBackdropItemId', None)
    Item['ParentBackdropImageTags'] = Item.get('ParentBackdropImageTags', [])
    Item['ImageTags'] = Item.get('ImageTags', [])
    Item['BackdropImageTags'] = Item.get('BackdropImageTags', [])
    Item['AlbumPrimaryImageTag'] = Item.get('AlbumPrimaryImageTag', None)
    Item['SeriesPrimaryImageTag'] = Item.get('SeriesPrimaryImageTag', None)
    Item['KodiArtwork'] = {'clearart': None, 'clearlogo': None, 'discart': None, 'landscape': None, 'thumb': None, 'banner': None, 'poster': None, 'fanart': {}, 'favourite': None}

    if not DynamicNode and Item['Type'] == "Audio": # no artwork for synced song content (Kodi handels that based on Albumart etc.)
        if Item["AlbumPrimaryImageTag"] and "AlbumId" in Item:
            Item['KodiArtwork']['favourite'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['AlbumId']}-0-p-{Item['AlbumPrimaryImageTag']}|redirect-limit=1000"

        return

    if Item['Type'] in ImageTagsMappings:
        for ImageTagsMapping in ImageTagsMappings[Item['Type']]:
            EmbyArtworkId = None
            EmbyArtworkTag = ""

            if ImageTagsMapping[0] in Item["ImageTags"]:
                if Item["ImageTags"][ImageTagsMapping[0]] and Item["ImageTags"][ImageTagsMapping[0]] != "None":
                    EmbyArtworkTag = Item["ImageTags"][ImageTagsMapping[0]]
                    EmbyArtworkId = Item['Id']
            elif f"{ImageTagsMapping[0]}ImageTag" in Item:
                ImageTagKey = f"{ImageTagsMapping[0]}ImageTag"

                if Item[ImageTagKey] and Item[ImageTagKey] != "None":
                    EmbyArtworkTag = Item[ImageTagKey]

                    if f"{ImageTagsMapping[0]}ItemId" in Item:
                        EmbyArtworkId = Item[f"{ImageTagsMapping[0]}ItemId"]
                    elif f"{ImageTagsMapping[0]}ImageItemId" in Item:
                        EmbyArtworkId = Item[f"{ImageTagsMapping[0]}ImageItemId"]
                    else:
                        if ImageTagsMapping[0] == "SeriesPrimary":
                            if "SeriesId" in Item:
                                EmbyArtworkId = Item["SeriesId"]
                        elif ImageTagsMapping[0] == "AlbumPrimary":
                            if "AlbumId" in Item:
                                EmbyArtworkId = Item["AlbumId"]

            if DynamicNode:
                if ImageTagsMapping[0] == "ParentBanner":
                    if "SeriesId" in Item:
                        EmbyArtworkId = Item["SeriesId"]
                        EmbyArtworkTag = ""
                elif ImageTagsMapping[0] == "AlbumArtists" and "AlbumArtists" in Item and Item["AlbumArtists"] and Item["AlbumArtists"] != "None":
                    EmbyArtworkId = Item["AlbumArtists"][0]['Id']
                    EmbyArtworkTag = ""
                elif ImageTagsMapping[0] == "ArtistItems" and "ArtistItems" in Item and Item["ArtistItems"] and Item["ArtistItems"] != "None":
                    EmbyArtworkId = Item["ArtistItems"][0]['Id']
                    EmbyArtworkTag = ""

            if f"{ImageTagsMapping[0]}ImageTags" in Item:
                BackDropsKey = f"{ImageTagsMapping[0]}ImageTags"

                if BackDropsKey == "ParentBackdropImageTags":
                    EmbyBackDropsId = Item["ParentBackdropItemId"]
                else:
                    EmbyBackDropsId = Item.get("Id", None)

                if EmbyBackDropsId:
                    if Item[BackDropsKey] and Item[BackDropsKey] != "None":
                        if ImageTagsMapping[1] == "fanart":
                            if "fanart" not in Item['KodiArtwork']["fanart"]:
                                Item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-B-{Item[BackDropsKey][0]}|redirect-limit=1000"

                            for index, EmbyArtworkTag in enumerate(Item[BackDropsKey][1:], 1):
                                if f"fanart{index}" not in Item['KodiArtwork']["fanart"]:
                                    Item['KodiArtwork']["fanart"][f"fanart{index}"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-{index}-B-{EmbyArtworkTag}|redirect-limit=1000"
                        else:
                            if not Item['KodiArtwork'][ImageTagsMapping[1]]:
                                Item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyBackDropsId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{Item[BackDropsKey][0]}|redirect-limit=1000"

            if EmbyArtworkId:
                if ImageTagsMapping[1] == "fanart":
                    if "fanart" not in Item['KodiArtwork']["fanart"]:
                        Item['KodiArtwork']["fanart"]["fanart"] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}|redirect-limit=1000"
                else:
                    if not Item['KodiArtwork'][ImageTagsMapping[1]]:
                        Item['KodiArtwork'][ImageTagsMapping[1]] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{EmbyArtworkId}-0-{EmbyArtworkIdShort[ImageTagsMapping[0]]}-{EmbyArtworkTag}|redirect-limit=1000"

    if utils.AssignEpisodePostersToTVShowPoster:
        if Item['Type'] == "Episode" and 'SeriesId' in Item and "SeriesPrimaryImageTag" in Item and Item["SeriesPrimaryImageTag"] and Item["SeriesPrimaryImageTag"] != "None":
            Item['KodiArtwork']['poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['SeriesId']}-0-p-{Item['SeriesPrimaryImageTag']}|redirect-limit=1000"

    if DynamicNode:
        if Item['Type'] == "Episode":
            if 'SeriesId' in Item and "SeriesPrimaryImageTag" in Item and Item["SeriesPrimaryImageTag"] and Item["SeriesPrimaryImageTag"] != "None":
                Item['KodiArtwork']['tvshow.poster'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['SeriesId']}-0-p-{Item['SeriesPrimaryImageTag']}|redirect-limit=1000"

            if 'ParentThumbItemId' in Item and "ParentThumbImageTag" in Item and Item["ParentThumbImageTag"] and Item["ParentThumbImageTag"] != "None":
                Item['KodiArtwork']['tvshow.thumb'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['ParentThumbItemId']}-0-p-{Item['ParentThumbImageTag']}|redirect-limit=1000"

            if 'ParentLogoItemId' in Item and "ParentLogoImageTag" in Item and Item["ParentLogoImageTag"] and Item["ParentLogoImageTag"] != "None":
                Item['KodiArtwork']['tvshow.clearlogo'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['ParentLogoItemId']}-0-p-{Item['ParentLogoImageTag']}|redirect-limit=1000"

            if 'ParentBackdropItemId' in Item and "ParentBackdropImageTags" in Item and Item["ParentBackdropImageTags"]:
                Item['KodiArtwork']['tvshow.fanart'] = f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['ParentBackdropItemId']}-0-p-{Item['ParentBackdropImageTags'][0]}|redirect-limit=1000"

    if Item['KodiArtwork']['poster']:
        Item['KodiArtwork']['favourite'] = Item['KodiArtwork']['poster']
    else:
        Item['KodiArtwork']['favourite'] = Item['KodiArtwork']['thumb']

    if Item['Type'] in ("Genre", "Sudio", "Tag", "MusicGenre"):
        for KodiArtworkKey, KodiArtwork in list(Item['KodiArtwork'].items()):
            if KodiArtwork and KodiArtworkKey != "fanart":
                KodiArtwork = KodiArtwork.replace("|redirect-limit=1000", "")
                Item['KodiArtwork'][KodiArtworkKey] = f"{KodiArtwork}-{quote(Item['Name'])}|redirect-limit=1000"

def set_MusicVideoTracks(Item):
    # Try to detect track number
    Item['IndexNumber'] = None
    Temp = Item['MediaSources'][0]['Name'][:4]  # e.g. 01 - Artist - Title
    Temp = Temp.split("-")

    if len(Temp) > 1:
        Track = Temp[0].strip()

        if Track.isdigit():
            Item['IndexNumber'] = int(Track)  # remove leading zero e.g. 01

def delete_ContentItemReferences(Item, SQLs, KodiType, isSpecial=False):
    KodiLibraryTagIds = SQLs["emby"].get_KodiLibraryTagIds()
    SQLs["video"].delete_links_actors(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_director(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_writer(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_countries(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_studios(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_links_tags(Item['KodiItemId'], KodiType, KodiLibraryTagIds)
    SQLs["video"].delete_links_genres(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_uniqueids(Item['KodiItemId'], KodiType)
    SQLs["video"].delete_bookmark(Item['KodiFileId'])
    SQLs["video"].delete_streams(Item['KodiFileId'])
    SQLs["video"].delete_stacktimes(Item['KodiFileId'])
    SQLs["video"].delete_ratings(Item['KodiItemId'], KodiType)
    SQLs["video"].common_db.delete_artwork(Item['KodiItemId'], KodiType)

    if KodiType == "movie":
        SQLs["video"].common_db.delete_artwork(Item['KodiFileId'], "videoversion") # delete videoversions artwork

        if isSpecial:
            SQLs["video"].delete_videoversion(Item['KodiItemId'], KodiType)
        else:
            SQLs["video"].delete_videoversion_by_KodiId_notKodiFileId_KodiType(Item['KodiItemId'], Item['KodiFileId'], KodiType) # delete videoversions

        SQLs['emby'].remove_item_by_parentid(Item['Id'], "Video", Item['LibraryId']) # delete reference specials

def set_VideoCommon(Item, SQLs, KodiType):
    SQLs["video"].common_db.add_artwork(Item['KodiArtwork'], Item['KodiItemId'], KodiType)
    SQLs["video"].add_bookmarks(Item['KodiFileId'], Item['KodiRunTimeTicks'], Item['MediaSources'][0]['KodiChapters'], Item['KodiPlaybackPositionTicks'])
    SQLs["video"].add_countries_and_links(Item['ProductionLocations'], Item['KodiItemId'], KodiType)
    SQLs["video"].add_streams(Item['KodiFileId'], Item['MediaSources'][0]['KodiStreams']['Video'], Item['MediaSources'][0]['KodiStreams']['Audio'], Item['MediaSources'][0]['KodiStreams']['Subtitle'], Item['KodiRunTimeTicks'])

    if "KodiStackTimes" in Item:
        SQLs["video"].add_stacktimes(Item['KodiFileId'], Item['KodiStackTimes'])

def delete_ContentItem(Item, SQLs, KodiType, EmbyType, isSpecial=False):
    if SQLs['emby'].remove_item(Item['Id'], EmbyType, Item['LibraryId']):
        delete_ContentItemReferences(Item, SQLs, KodiType, isSpecial)
        return True

    return False

def verify_content(Item, MediaType):
    if 'Name' not in Item:
        xbmc.log(f"EMBY.core.common: Name not found in Item {Item}", 3) # LOGERROR
        return False

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
    set_streams(Item)
    set_common(Item, ServerId, True)

def set_Favorite(Item):
    IsFavorite = False

    if "UserData" in Item and "IsFavorite" in Item['UserData'] and Item['UserData']['IsFavorite']:
        IsFavorite = Item['UserData']['IsFavorite']

    return IsFavorite

def set_PresentationUniqueKey(Item):
    if 'PresentationUniqueKey' in Item and Item['PresentationUniqueKey']:
        Item['PresentationUniqueKey'] = Item['PresentationUniqueKey'].replace("-", "_").replace(" ", "")
    else:
        Item['PresentationUniqueKey'] = None

def set_ItemsDependencies(Item, SQLs, WorkerObject, EmbyServer, EmbyType, IncrementalSync):
    AddSubItem = False
    SubItemId = f'{EmbyType}Id'

    if SubItemId not in Item or not Item[SubItemId]:
        AddSubItem = True
    else:
        if EmbyType == "MusicAlbum":
            Exists = SQLs["emby"].get_item_exists_multi_library(Item[SubItemId], EmbyType, Item['LibraryId'])
        else:
            Exists = SQLs["emby"].get_item_exists_by_id(Item[SubItemId], EmbyType)

        if not Exists:
            EmbyItem = EmbyServer.API.get_Item(Item[SubItemId], [EmbyType], False, False, False)

            if EmbyItem:
                EmbyItem['LibraryId'] = Item['LibraryId']
                WorkerObject.change(EmbyItem, IncrementalSync)
            else:
                AddSubItem = True

    if AddSubItem:
        Item[SubItemId] = None

        if Item['PresentationUniqueKey'] and EmbyType != "MusicAlbum":
            PresentationData = Item['PresentationUniqueKey'].split("_")

            if Item['Type'] == "Episode" and len(PresentationData) >= 2: # multiepisode:
                SearchPresentationUniqueKey = "_".join(PresentationData[:-1])
                Item[SubItemId] = SQLs["emby"].get_EmbyId_by_EmbyPresentationKey(SearchPresentationUniqueKey, EmbyType)
                xbmc.log(f"EMBY.core.common: Detect by PresentationUniqueKey: {Item[SubItemId]} / {Item['PresentationUniqueKey']} / {SearchPresentationUniqueKey}", 1) # LOGINFO

        if not Item[SubItemId]:
            Item[SubItemId] = MappingIds[EmbyType]

            if EmbyType == "MusicAlbum":
                Item[SubItemId] = f"{Item[SubItemId]}{Item['Id']}"

                if 'AlbumArtists' in Item and Item['AlbumArtists']:
                    WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": Item['Name'], "SortName": Item['Name'], "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None, "AlbumArtists": Item['AlbumArtists'], "ArtistItems": [], "AlbumArtist": Item['AlbumArtist']}, IncrementalSync)
                else:
                    WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": Item['Name'], "SortName": Item['Name'], "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None, "AlbumArtists": Item['ArtistItems'], "ArtistItems": [], "AlbumArtist": Item['MusicArtist']}, IncrementalSync)
            elif EmbyType == "Season":
                Item["SeasonId"] = f"{Item[SubItemId]}{Item['Id']}"
                WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item["SeasonId"], "SeriesId": Item["SeriesId"], "Name": "--NO INFO--", "SortName": "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}, 'ParentId': None}, IncrementalSync)
            else:
                WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": Item[SubItemId], "Name": "--NO INFO--", "SortName": "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}, 'Path': Item.get('Path', "/--NO INFO--/--NO INFO--/"), 'ParentId': None}, IncrementalSync)

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
        SQLs["video"].add_actor_link(MetaDataItemKodiId[Index], KodiItemId, KodiType, "Artist", Order)

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

def set_MetaItems(Item, SQLs, WorkerObject, EmbyServer, EmbyType, MetaDataId, LibraryId, Index, IncrementalSync):
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

                if WorkerObject:
                    WorkerObject.change(EmbyItem, IncrementalSync)

                continue

            AddSubItem = True

    if AddSubItem:
        Names += ("--NO INFO--",)
        AddSubItemId = MappingIds[EmbyType]

        if WorkerObject:
            WorkerObject.change({"LibraryId": Item["LibraryId"], "Type": EmbyType, "Id": AddSubItemId, "Name": "--NO INFO--", 'SortName': "--NO INFO--", "DateCreated": utils.currenttime(), "ProviderIds": {}}, IncrementalSync)

        Item[MetaDataId] = [{"Name": "--NO INFO--", "Id": AddSubItemId, "Memo": f"no info {EmbyType}"}]

    if EmbyType == "MusicGenre":
        Item["MusicGenreItems"] = Item["GenreItems"]

    Item[EmbyType] = " / ".join(Names)

def set_people(Item, SQLs, PersonObject, EmbyServer, IncrementalSync):
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
                        PersonObject.change(EmbyItem, IncrementalSync)
                    else:
                        continue

                if People['Type'] == "Writer":
                    Item['WritersItems'] += ({"Name": People['Name'], "Id": People['Id'], "KodiType": "actor"},)
                    Writers += (People['Name'],)
                elif People['Type'] == "Director":
                    Item['DirectorsItems'] += ({"Name": People['Name'], "Id": People['Id'], "KodiType": "actor"},)
                    Directors += (People['Name'],)
                elif People['Type'] in ("Actor", "GuestStar"):
                    if 'Role' in People:
                        role = People['Role']
                    else:
                        if People['Type'] == "GuestStar":
                            role = "Guest Star"
                        else:
                            role = "Actor"

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

def update_boxsets(IncrementalSync, ParentId, LibraryId, SQLs, EmbyServer):
    if IncrementalSync:
        for BoxSet in EmbyServer.API.get_Items(ParentId, ["BoxSet"], True, True, {'GroupItemsIntoCollections': True}, "", True, None):
            SQLs["emby"].add_UpdateItem(BoxSet['Id'], "BoxSet", LibraryId)

def set_Favorites_Artwork(Item, ServerId):
    if 'ImageTags' in Item and Item['ImageTags']:
        if "Primary" in Item['ImageTags']:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id'].replace('999999993', '')}-0-p-{Item['ImageTags']['Primary']}|redirect-limit=1000" # 999999993 replacement: Collections assigned to tags -> utils.BoxSetsToTags

        if "Thumb" in Item['ImageTags']:
            return f"http://127.0.0.1:57342/picture/{ServerId}/p-{Item['Id'].replace('999999993', '')}-0-p-{Item['ImageTags']['Thumb']}|redirect-limit=1000"

    return None

def set_Favorites_Artwork_Overlay(Label, Content, EmbyItemId, EmbyServerId, ImageUrl):
    OverlayText = quote(f"{Label}\n({Content})")

    if ImageUrl:
        return ImageUrl.replace("|redirect-limit=1000", f"-{OverlayText}|redirect-limit=1000")

    return f"http://127.0.0.1:57342/picture/{EmbyServerId}/p-{EmbyItemId}-0-p-noimage-{OverlayText}|redirect-limit=1000"

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

def swap_mediasources(Item):
    if utils.SyncLocalOverPlugins:
        if len(Item.get('MediaSources', [])) > 1:
            for DefaultIndex, Mediasource in enumerate(Item['MediaSources']):
                if Mediasource['Type'] == "Default":
                    if Mediasource['Path'].startswith("plugin://"):
                        if 'ItemId' not in Mediasource:
                            return

                        for Mediasource in Item['MediaSources']:
                            if not Mediasource['Path'].startswith("plugin://"):
                                Item['MediaSources'][DefaultIndex]['Type'] = Mediasource['Type']
                                Mediasource['Type'] = "Default"
                                Item['Id'] = Mediasource['ItemId']
                                xbmc.log(f"EMBY.core.common: Swap mediasources by plugin path: {Item['Id']}", 1) # LOGINFO
                                break

                        break

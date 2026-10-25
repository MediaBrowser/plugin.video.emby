import threading
from . import utils

CacheLock = threading.Lock()
# ItemCacheId can be the EmbyId or a generated Uid
ItemCacheId_by_Path = {} # [Path] = ItemCacheId -> used by player.py
Path_by_ItemCacheId = {} # [ItemCacheId] = Path -> reverse lookup, used by player.py
Item_by_ItemCacheId = {} # [ItemCacheId] = Item
Query = {} # [CacheId] = [ItemCacheIds, QueryParams]

def add_Item(Item, ServerId):
    with utils.SafeLock(CacheLock):
        ItemCacheId = ""

        if 'Id' in Item:
            ItemCacheId = f"{Item['Id']};{ServerId}"
        elif 'CacheId' in Item:
            ItemCacheId = Item['CacheId'] # Item['CacheId'] set in pluginmenu.py
        else:
            return

        if Item['KodiFullPath'] and not Item['KodiFullPath'].startswith("plugin") and Item['KodiFullPath'] not in ItemCacheId_by_Path:
            ItemCacheId_by_Path[Item['KodiFullPath']] = ItemCacheId
            Path_by_ItemCacheId[ItemCacheId] = Item['KodiFullPath']

        if ItemCacheId not in Item_by_ItemCacheId:
            Item_by_ItemCacheId[ItemCacheId] = Item

def get_ItemByPath(Path):
    with utils.SafeLock(CacheLock):
        if Path in ItemCacheId_by_Path:
            ItemCacheId = ItemCacheId_by_Path[Path]

            if ItemCacheId in Item_by_ItemCacheId:
                return Item_by_ItemCacheId[ItemCacheId]

        return {}

def get_ItemByEmbyId(EmbyId, ServerId):
    ItemCacheId = f"{EmbyId};{ServerId}"

    with utils.SafeLock(CacheLock):
        if ItemCacheId in Item_by_ItemCacheId:
            return Item_by_ItemCacheId[ItemCacheId]

        return {}

def reset():
    with utils.SafeLock(CacheLock):
        Query.clear()
        ItemCacheId_by_Path.clear()
        Path_by_ItemCacheId.clear()
        Item_by_ItemCacheId.clear()

    utils.refresh_DynamicNode()

def remove(EmbyId, ServerId):
    ItemCacheId = f"{EmbyId};{ServerId}"

    with utils.SafeLock(CacheLock):
        if ItemCacheId in Item_by_ItemCacheId:
            del Item_by_ItemCacheId[ItemCacheId]

        if ItemCacheId in Path_by_ItemCacheId:
            Path = Path_by_ItemCacheId[ItemCacheId]
            del Path_by_ItemCacheId[ItemCacheId]

            if Path in ItemCacheId_by_Path:
                del ItemCacheId_by_Path[Path]

def set_Playcount(InfoTag, GenericPlayCount, KodiPlayEnded, isAudio):
    GenericPlayed = None

    if GenericPlayCount is None: # Try to detect by Playback ended
        if KodiPlayEnded is not None and KodiPlayEnded:
            current = InfoTag.getPlayCount()

            if isinstance(current, int):
                GenericPlayCount = current + 1

                if isAudio:
                    InfoTag.setPlayCount(GenericPlayCount)
                else:
                    InfoTag.setPlaycount(GenericPlayCount)

                GenericPlayed = True
        else:
            GenericPlayCount = None
    else:
        GenericPlayCount = int(GenericPlayCount)
        GenericPlayed = bool(GenericPlayCount)

        if isAudio:
            InfoTag.setPlayCount(GenericPlayCount)
        else:
            InfoTag.setPlaycount(GenericPlayCount)

    return GenericPlayed, GenericPlayCount

def set_LastPlayedDate(InfoTag, KodiLastPlayedDate):
    if KodiLastPlayedDate is not None:
        InfoTag.setLastPlayed(KodiLastPlayedDate)

def update_Item(Item, PlayedPercentage, PlaybackPositionTicks, PlayCount, IsFavorite, LastPlayedDate, Played, KodiPlaybackPositionTicks, KodiLastPlayedDate, KodiPlayCount, GenericPlayCount, GenericPlayed):
    if "UserData" not in Item:
        Item["UserData"] = {}

    if Played is None and GenericPlayed is not None:
        Played = GenericPlayed

    if KodiPlayCount is not None and PlayCount is None:
        PlayCount = KodiPlayCount

    if PlayCount is not None and KodiPlayCount is None:
        KodiPlayCount = PlayCount

    if KodiPlayCount is None and GenericPlayCount is not None:
        KodiPlayCount = GenericPlayCount

    if PlayCount is None and GenericPlayCount is not None:
        PlayCount = GenericPlayCount

    if PlayedPercentage is not None:
        Item["UserData"]["PlayedPercentage"] = PlayedPercentage

    if PlaybackPositionTicks is not None:
        Item["UserData"]["PlaybackPositionTicks"] = PlaybackPositionTicks

    if PlayCount is not None:
        Item["UserData"]["PlayCount"] = PlayCount

    if LastPlayedDate is not None:
        Item["UserData"]["LastPlayedDate"] = LastPlayedDate

    if KodiPlaybackPositionTicks is not None:
        Item["KodiPlaybackPositionTicks"] = KodiPlaybackPositionTicks

    if KodiLastPlayedDate is not None:
        Item["KodiLastPlayedDate"] = KodiLastPlayedDate

    if KodiPlayCount is not None:
        Item["KodiPlayCount"] = KodiPlayCount

    if IsFavorite is not None:
        Item["IsFavorite"] = IsFavorite
        Item["UserData"]["IsFavorite"] = IsFavorite

    if Played is not None:
        Item["UserData"]["Played"] = bool(Played)

def update_Listitem(Item, GenericPlayCount, KodiLastPlayedDate, KodiPlaybackPositionTicks, KodiPlayEnded):
    Update = False
    GenericPlayed = None

    if Item['Type'] in ("MusicArtist", "MusicAlbum", "Audio"): # Music
        InfoTag = Item['ListItem'].getMusicInfoTag()
        GenericPlayed, GenericPlayCount = set_Playcount(InfoTag, GenericPlayCount, KodiPlayEnded, True)
        set_LastPlayedDate(InfoTag, KodiLastPlayedDate)
        Update = True
    elif Item['Type'] not in ("Photo", "PhotoAlbum"): # Videos
        InfoTag = Item['ListItem'].getVideoInfoTag()

        if KodiPlaybackPositionTicks is not None:
            if KodiPlaybackPositionTicks > 60:
                InfoTag.setResumePoint(float(KodiPlaybackPositionTicks))
            else:
                InfoTag.setResumePoint(0.0)

        GenericPlayed, GenericPlayCount = set_Playcount(InfoTag, GenericPlayCount, KodiPlayEnded, False)
        set_LastPlayedDate(InfoTag, KodiLastPlayedDate)
        Update = True

    return Update, GenericPlayed, GenericPlayCount

def update_userdata_Kodi(EmbyId, ServerId, KodiPlaybackPositionTicks, LastPlayedDate, KodiPlayEnded, KodiRunTimeTicks, KodiPlayCount):
    ItemCacheId = f"{EmbyId};{ServerId}"
    PlaybackPositionTicks = None
    PlayedPercentage = None
    KodiLastPlayedDate = None

    if KodiPlaybackPositionTicks is not None:
        PlaybackPositionTicks = KodiPlaybackPositionTicks * 10000000.0

    if LastPlayedDate is not None:
        KodiLastPlayedDate = utils.convert_to_local(LastPlayedDate, False, False)

    if KodiPlayEnded:
        PlayedPercentage = 0.0
    else:
        if KodiPlaybackPositionTicks is not None and KodiRunTimeTicks is not None and KodiRunTimeTicks:
            PlayedPercentage = (KodiPlaybackPositionTicks / KodiRunTimeTicks) * 100

    with utils.SafeLock(CacheLock):
        if ItemCacheId in Item_by_ItemCacheId:
            Item = Item_by_ItemCacheId[ItemCacheId]
            Update, GenericPlayed, GenericPlayCount = update_Listitem(Item, KodiPlayCount, KodiLastPlayedDate, KodiPlaybackPositionTicks, KodiPlayEnded)

            if Update:
                update_Item(Item, PlayedPercentage, PlaybackPositionTicks, None, None, LastPlayedDate, None, KodiPlaybackPositionTicks, KodiLastPlayedDate, KodiPlayCount, GenericPlayCount, GenericPlayed)

def update_userdata_Emby(EmbyId, ServerId, PlaybackPositionTicks, PlayCount, IsFavorite, Played, LastPlayedDate, PlayedPercentage):
    ItemCacheId = f"{EmbyId};{ServerId}"

    with utils.SafeLock(CacheLock):
        KodiLastPlayedDate = None
        KodiPlaybackPositionTicks = None

        if not PlayCount or (Played is not None and not Played):
            PlayCount = 0

        if LastPlayedDate is not None:
            KodiLastPlayedDate = utils.convert_to_local(LastPlayedDate, False, False)

        if PlaybackPositionTicks is not None:
            PlaybackPositionTicks = float(PlaybackPositionTicks)
            KodiPlaybackPositionTicks = round(float(PlaybackPositionTicks / 10000000.0), 6)

        if ItemCacheId in Item_by_ItemCacheId:
            Item = Item_by_ItemCacheId[ItemCacheId]
            Update, GenericPlayed, GenericPlayCount = update_Listitem(Item, PlayCount, KodiLastPlayedDate, KodiPlaybackPositionTicks, None)

            if Update:
                update_Item(Item, PlayedPercentage, PlaybackPositionTicks, PlayCount, IsFavorite, LastPlayedDate, Played, KodiPlaybackPositionTicks, KodiLastPlayedDate, None, GenericPlayCount, GenericPlayed)
                return  True

    return False

def remove_Query(CacheId):
    with utils.SafeLock(CacheLock):
        if CacheId in Query:
            del Query[CacheId]

def add_Query(CacheId, QueryParams, ItemsListings):
    with utils.SafeLock(CacheLock):
        ItemCacheIds = len(ItemsListings[1]) * [""]

        for Index, ItemCacheId in enumerate(ItemsListings[1]):
            ItemCacheIds[Index] = ItemCacheId

        Query[CacheId] = [ItemCacheIds, QueryParams]

def get_Query(CacheId):
    with utils.SafeLock(CacheLock):
        ItemsListings = [[], []]

        if CacheId not in Query:
            return {}

        for ItemCacheId in Query[CacheId][0]:
            if ItemCacheId not in Item_by_ItemCacheId:
                return {}

            Item = Item_by_ItemCacheId[ItemCacheId]
            IsFolder = Item.get('IsFolder', False)
            ItemsListings[0].append((Item['KodiFullPath'], Item["ListItem"], IsFolder))
            ItemsListings[1].append(ItemCacheId)

        Cache = Query[CacheId][1] # QueryParams
        Cache['listings'] = ItemsListings
        return Cache

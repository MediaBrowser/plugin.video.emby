import struct
from urllib.parse import unquote, quote
import xbmcvfs
import xbmc
from database import dbio
from . import utils

EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}
HEX = "0123456789abcdefABCDEF"

# Cache native Chapter
def CacheNativeChapter(Chapters, WorkerName, KodiFullPath):
    if utils.useDirectPaths or not utils.NativeChapterDownload or not Chapters:
        return

    total = len(Chapters)
    ArtworkCacheItems = 1000 * [{}]
    ArtworkCacheIndex = 0

    for IndexUrl, Chapter in enumerate(Chapters):
        if utils.TextureCacheCancel:
            return

        if IndexUrl % 1000 == 0:
            add_textures(ArtworkCacheItems)
            ArtworkCacheItems = 1000 * [{}]
            ArtworkCacheIndex = 0

            if utils.getFreeSpace(utils.FolderUserdataThumbnails) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=utils.displayMessage, sound=True)
                xbmc.log("EMBY.helper.artworkcache: Artwork chapter cache: running out of space", 2) # LOGWARNING
                return
        else:
            ArtworkCacheIndex += 1

        if not Chapter:
            continue

        ChapterKodiIndex = Chapter['Index'] + 1

        if utils.DatabaseFiles["texture-version"] <= 13: # Kodi 21
            CachePath = f"chapter:///{KodiFullPath}/{ChapterKodiIndex}"
        else:
            CachePath = lower_hex(f"image://video@{quote(KodiFullPath, safe='')}/?chapter={ChapterKodiIndex}")

        Hash = utils.kodi_hash(CachePath)

        if utils.SystemShutdown:
            return

        TempPath = f"{utils.FolderUserdataThumbnails}{Hash[0]}/{Hash}"

        if not xbmcvfs.exists(f"{TempPath}.jpg") and not xbmcvfs.exists(f"{TempPath}.png"):
            ImageBinary, _, _ = utils.image_overlay(Chapter['ImageTag'], Chapter['ServerId'], Chapter['Id'], "Chapter", Chapter['Index'], "")
            Width, Height, ImageFormat = get_image_metadata(ImageBinary, Hash)
            cachedUrl = f"{Hash[0]}/{Hash}.{ImageFormat}"
            utils.mkDir(f"{utils.FolderUserdataThumbnails}{Hash[0]}")
            Path = f"{utils.FolderUserdataThumbnails}{cachedUrl}"

            if Width == 0:
                if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork chapter cache: image not detected: {Chapter}", 2) # LOGWARNING
            else:
                utils.writeFile(Path, ImageBinary)
                Size = len(ImageBinary)
                ArtworkCacheItems[ArtworkCacheIndex] = {'Url': CachePath, 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': "", 'Path': Path, 'cachedUrl': cachedUrl}

            del ImageBinary

        utils.update_ProgressBar(WorkerName, (IndexUrl + 1) / total * 100, utils.Translate(33199), f"{utils.Translate(33045)}: {Chapter['Id']} / {Chapter['Index']}")

    add_textures(ArtworkCacheItems)

# Cache all entries
def CacheAllEntries(urls, WorkerName):
    total = len(urls)
    ArtworkCacheItems = 1000 * [{}]
    ArtworkCacheIndex = 0

    for IndexUrl, url in enumerate(urls):
        if utils.TextureCacheCancel:
            return

        if IndexUrl % 1000 == 0:
            add_textures(ArtworkCacheItems)
            ArtworkCacheItems = 1000 * [{}]
            ArtworkCacheIndex = 0

            if utils.getFreeSpace(utils.FolderUserdataThumbnails) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=utils.displayMessage, sound=True)
                xbmc.log("EMBY.helper.artworkcache: Artwork cache: running out of space", 2) # LOGWARNING
                return
        else:
            ArtworkCacheIndex += 1

        if not url[0]:
            continue

        if url[0].startswith("image://"):
            if utils.DatabaseFiles["texture-version"] <= 13: # Kodi 21
                CachePath = url[0]
                HttpPath = utils.image_url_decode(url[0], True)
            else:
                CachePath = lower_hex(f"{url[0].rsplit('/', 1)[0]}/") # Add trailing / and Kodi uses lower case escapes
                HttpPath = utils.image_url_decode(url[0], True)

            hasImagePrefix = True
        else:
            CachePath = url[0]
            HttpPath = url[0]
            hasImagePrefix = False

        Folder = HttpPath.split("/")
        Data = HttpPath.replace("|redirect-limit=1000&failonerror=false", "")
        Data = Data[Data.rfind("/") + 1:].split("-")

        if len(Data) < 7 or len(Folder) < 5:
            xbmc.log(f"EMBY.helper.artworkcache: Artwork cache: Invalid item found {url[0]}", 2) # LOGWARNING
            continue

        ServerId = Folder[4]
        EmbyID = Data[1]
        ImageIndex = Data[2]
        ImageTag = Data[4]

        if Data[3] not in EmbyArtworkIDs:
            if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache: Invalid (EmbyArtworkIDs) item found {url[0]}", 2) # LOGWARNING
            continue

        ImageType = EmbyArtworkIDs[Data[3]]
        Hash = utils.kodi_hash(CachePath)

        if utils.SystemShutdown:
            return

        TempPath = f"{utils.FolderUserdataThumbnails}{Hash[0]}/{Hash}"

        if not xbmcvfs.exists(f"{TempPath}.jpg") and not xbmcvfs.exists(f"{TempPath}.png"):
            if Data[5]:
                OverlayText = unquote(Data[5])
            else:
                OverlayText = ""

            ImageBinary, _, _ = utils.image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText)
            Width, Height, ImageFormat = get_image_metadata(ImageBinary, Hash)
            cachedUrl = f"{Hash[0]}/{Hash}.{ImageFormat}"
            utils.mkDir(f"{utils.FolderUserdataThumbnails}{Hash[0]}")
            Path = f"{utils.FolderUserdataThumbnails}{cachedUrl}"

            if Width == 0:
                if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache: image not detected: {url[0]}", 2) # LOGWARNING
            else:
                utils.writeFile(Path, ImageBinary)
                Size = len(ImageBinary)

                if hasImagePrefix:
                    ArtworkCacheItems[ArtworkCacheIndex] = {'Url': CachePath, 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': "", 'Path': Path, 'cachedUrl': cachedUrl}
                else:
                    ArtworkCacheItems[ArtworkCacheIndex] = {'Url': CachePath, 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': f"d0s{Size}", 'Path': Path, 'cachedUrl': cachedUrl}

            del ImageBinary

        utils.update_ProgressBar(WorkerName, (IndexUrl + 1) / total * 100, utils.Translate(33199), f"{utils.Translate(33045)}: {EmbyID} / {IndexUrl}")

    add_textures(ArtworkCacheItems)

def add_textures(ArtworkCacheItems):
    SQLs = {}
    dbio.DBOpenRW("texture", "artwork_cache", SQLs)

    for ArtworkCacheItem in ArtworkCacheItems:
        if ArtworkCacheItem:
            SQLs['texture'].add_texture(ArtworkCacheItem["Url"], ArtworkCacheItem["cachedUrl"], ArtworkCacheItem["ImageHash"], "1", ArtworkCacheItem["Width"], ArtworkCacheItem["Height"], "")

    dbio.DBCloseRW("texture", "artwork_cache", SQLs)

def get_image_metadata(ImageBinaryData, Hash):
    height = 0
    width = 0
    imageformat = ""
    ImageBinaryDataSize = len(ImageBinaryData)

    if ImageBinaryDataSize < 10:
        if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache: invalid image size: {Hash} / {ImageBinaryDataSize}", 2) # LOGWARNING
        return width, height, imageformat

    # JPG
    if ImageBinaryData[0] == 0xFF and ImageBinaryData[1] == 0xD8 and ImageBinaryData[2] == 0xFF:
        i = 4

        try:
            BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]

            if BlockLength:
                while i < ImageBinaryDataSize:
                    i += BlockLength

                    if i >= ImageBinaryDataSize or ImageBinaryData[i] != 0xFF:
                        if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache: invalid jpg: {Hash}", 2) # LOGWARNING
                        break

                    if ImageBinaryData[i + 1] >> 4 == 12: # 0xCX
                        height = ImageBinaryData[i + 5] * 256 + ImageBinaryData[i + 6]
                        width = ImageBinaryData[i + 7] * 256 + ImageBinaryData[i + 8]
                        break

                    i += 2
                    BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]

                imageformat = "jpg"
        except Exception as Error:
            xbmc.log(f"EMBY.helper.artworkcache: Artwork cache: invalid jpg: {Hash} / {Error}", 2) # LOGWARNING
    elif ImageBinaryData[0] == 0x89 and ImageBinaryData[1] == 0x50 and ImageBinaryData[2] == 0x4E and ImageBinaryData[3] == 0x47: # PNG
        if len(ImageBinaryData) >= 24:
            imageformat = "png"
            width, height = struct.unpack('>ii', ImageBinaryData[16:24])
    else: # Not supported format
        if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache: invalid image format: {Hash}", 2) # LOGWARNING

    if utils.DebugLog: xbmc.log(f"EMBY.helper.artworkcache (DEBUG): Artwork cache image data: {width} / {height} / {Hash}", 1) # LOGDEBUG
    return width, height, imageformat

def delete_artworkcache_watchdog():
    while True:
        if utils.sleep(1):
            return

        delete_artworkcache()

def delete_artworkcache():
    with utils.SafeLock(utils.ArtworkDeleteLock):
        if utils.ArtworkDelete:
            SQLs = {}
            dbio.DBOpenRW("texture", "artwork_cache", SQLs)
            Urls = list(utils.ArtworkDelete)

            for Index in range(0, len(Urls), 500):
                Chunk = Urls[Index:Index + 500]
                CachedUrls = SQLs['texture'].delete_textures(Chunk)

                for CachedUrl in CachedUrls:
                    Path = f"{utils.FolderUserdataThumbnails}{CachedUrl[0]}"
                    utils.delFile(Path)
                    utils.delFile(f"{Path.rsplit('.', 1)[0]}.dds")

            dbio.DBCloseRW("texture", "artwork_cache", SQLs)
            utils.ArtworkDelete.clear()

def is_hex_pair(t):
    return len(t) == 2 and t[0] in HEX and t[1] in HEX

def lower_hex(s):
    out = []
    i = 0

    while i < len(s):
        if s[i] == "%":
            j = i + 1

            while s[j:j + 2] == "25" and is_hex_pair(s[j + 2:j + 4]):
                j += 2

            if is_hex_pair(s[j:j+2]):
                out.append(s[i:j+2].lower())
                i = j + 2
                continue

        out.append(s[i])
        i += 1

    return "".join(out)

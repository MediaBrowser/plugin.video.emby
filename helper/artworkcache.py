import struct
from urllib.parse import unquote
import xbmc
from database import dbio
from . import utils

EmbyArtworkIDs = {"p": "Primary", "a": "Art", "b": "Banner", "d": "Disc", "l": "Logo", "t": "Thumb", "B": "Backdrop", "c": "Chapter"}

# Cache all entries
def CacheAllEntries(urls, ProgressBar):
    total = len(urls)
    ArtworkCacheItems = 1000 * [{}]
    ArtworkCacheIndex = 0

    for IndexUrl, url in enumerate(urls):
        if IndexUrl % 1000 == 0:
            add_textures(ArtworkCacheItems)
            ArtworkCacheItems = 1000 * [{}]
            ArtworkCacheIndex = 0

            if utils.getFreeSpace(utils.FolderUserdataThumbnails) < 2097152: # check if free space below 2GB
                utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33429), icon=utils.icon, time=5000, sound=True)
                xbmc.log("EMBY.helper.pluginmenu: Artwork cache: running out of space", 2) # LOGWARNING
                return
        else:
            ArtworkCacheIndex += 1

        if not url[0]:
            continue

        Folder = url[0].split("/")
        Data = url[0][url[0].rfind("/") + 1:].replace("|redirect-limit=1000", "").split("-")

        if len(Data) < 4 or len(Folder) < 5:
            xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: Invalid item found {url}", 2) # LOGWARNING
            continue

        ServerId = Folder[4]
        EmbyID = Data[1]
        ImageIndex = Data[2]
        ImageTag = Data[4]

        if Data[3] not in EmbyArtworkIDs:
            xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: Invalid (EmbyArtworkIDs) item found {url}", 2) # LOGWARNING
            continue

        ImageType = EmbyArtworkIDs[Data[3]]

        # Calculate hash -> crc32mpeg2
        crc = 0xffffffff

        for val in url[0].encode("utf-8"):
            crc ^= val << 24

            for _ in range(8):
                crc = crc << 1 if (crc & 0x80000000) == 0 else (crc << 1) ^ 0x104c11db7

        Hash = hex(crc).replace("0x", "")

        if utils.SystemShutdown:
            return

        TempPath = f"{utils.FolderUserdataThumbnails}{Hash[0]}/{Hash}"

        if not utils.checkFileExists(f"{TempPath}.jpg") and not utils.checkFileExists(f"{TempPath}.png"):
            if len(Data) > 5:
                OverlayText = unquote("-".join(Data[5:]))
                ImageBinary, _ = utils.image_overlay(ImageTag, ServerId, EmbyID, ImageType, ImageIndex, OverlayText)
            else:
                ImageBinary, _, _ = utils.EmbyServers[ServerId].API.get_Image_Binary(EmbyID, ImageType, ImageIndex, ImageTag)

            Width, Height, ImageFormat = get_image_metadata(ImageBinary, Hash)
            cachedUrl = f"{Hash[0]}/{Hash}.{ImageFormat}"
            utils.mkDir(f"{utils.FolderUserdataThumbnails}{Hash[0]}")
            Path = f"{utils.FolderUserdataThumbnails}{cachedUrl}"

            if Width == 0:
                xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: image not detected: {url[0]}", 2) # LOGWARNING
            else:
                utils.writeFileBinary(Path, ImageBinary)
                Size = len(ImageBinary)
                ArtworkCacheItems[ArtworkCacheIndex] = {'Url': url[0], 'Width': Width, 'Height': Height, 'Size': Size, 'Extension': ImageFormat, 'ImageHash': f"d0s{Size}", 'Path': Path, 'cachedUrl': cachedUrl}

        Value = int((IndexUrl + 1) / total * 100)

        if ProgressBar:
            ProgressBar.update(Value, "Emby", f"{utils.Translate(33045)}: {EmbyID} / {IndexUrl}")

    add_textures(ArtworkCacheItems)

def add_textures(ArtworkCacheItems):
    SQLs = dbio.DBOpenRW("texture", "artwork_cache", {})

    for ArtworkCacheItem in ArtworkCacheItems:
        if ArtworkCacheItem:
            SQLs['texture'].add_texture(ArtworkCacheItem["Url"], ArtworkCacheItem["cachedUrl"], ArtworkCacheItem["ImageHash"], "1", ArtworkCacheItem["Width"], ArtworkCacheItem["Height"], "")

    dbio.DBCloseRW("texture", "artwork_cache", {})

def get_image_metadata(ImageBinaryData, Hash):
    height = 0
    width = 0
    imageformat = ""
    ImageBinaryDataSize = len(ImageBinaryData)

    if ImageBinaryDataSize < 10:
        xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid image size: {Hash} / {ImageBinaryDataSize}", 2) # LOGWARNING
        return width, height, imageformat

    # JPG
    if ImageBinaryData[0] == 0xFF and ImageBinaryData[1] == 0xD8 and ImageBinaryData[2] == 0xFF:
        imageformat = "jpg"
        i = 4
        BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]

        while i < ImageBinaryDataSize:
            i += BlockLength

            if i >= ImageBinaryDataSize or ImageBinaryData[i] != 0xFF:
                xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid jpg: {Hash}", 2) # LOGWARNING
                break

            if ImageBinaryData[i + 1] >> 4 == 12: # 0xCX
                height = ImageBinaryData[i + 5] * 256 + ImageBinaryData[i + 6]
                width = ImageBinaryData[i + 7] * 256 + ImageBinaryData[i + 8]
                break

            i += 2
            BlockLength = ImageBinaryData[i] * 256 + ImageBinaryData[i + 1]
    elif ImageBinaryData[0] == 0x89 and ImageBinaryData[1] == 0x50 and ImageBinaryData[2] == 0x4E and ImageBinaryData[3] == 0x47: # PNG
        imageformat = "png"
        width, height = struct.unpack('>ii', ImageBinaryData[16:24])
    else: # Not supported format
        xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache: invalid image format: {Hash}", 2) # LOGWARNING

    xbmc.log(f"EMBY.helper.pluginmenu: Artwork cache image data: {width} / {height} / {Hash}", 0) # LOGDEBUG
    return width, height, imageformat

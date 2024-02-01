import xbmc
from . import utils


# Create master lock compatible sources.
# Also add the kodi.emby.tv source.
def get_Section(FileData, Id):
    PosStart = FileData.find(f"<{Id}>")

    if PosStart != -1:
        PosEnd = FileData.find(f"</{Id}>")

        if PosEnd == -1:
            xbmc.log(f"EMBY.helper.xmls: special://profile/sources.xml file corrupted, {Id} section", 3) # LOGERROR
        else:
            return FileData[PosStart + len(f"<{Id}>"):PosEnd]

    return ""

def replace_Section(Id, SectionReplace, SectionMain):
    PosStart = SectionMain.find(f"<{Id}>")
    PosEnd = SectionMain.find(f"</{Id}>")
    return SectionMain[:PosStart + len(f"<{Id}>")] + "\n" + SectionReplace + "\n    " + SectionMain[PosEnd:]

def add_replace_Section(Id, IdSub, SectionReplace, SectionMain):
    PosStart = SectionMain.find(f"<{Id}>")

    if PosStart == -1:
        PosSubEnd = SectionMain.find(f"</{IdSub}>")
        return SectionMain[:PosSubEnd] + "\n        " + SectionReplace + "\n    " + SectionMain[PosSubEnd:]

    PosEnd = SectionMain.find(f"</{Id}>")
    return SectionMain[:PosStart] + SectionReplace + SectionMain[PosEnd + len(f"</{Id}>"):]

def get_value(Id, Data):
    Pos = Data.find(Id)

    if Pos != -1:
        Value = Data[Pos:]
        Value = Value[Value.find(">") + 1:]
        return Value[:Value.find("<")]

    return ""

def sources():
    Filepath = 'special://profile/sources.xml'
    FileData = utils.readFileString(Filepath)
    Changed = False
    SectionMain = get_Section(FileData, "sources")
    SectionData = get_Section(SectionMain, "files")

    if not SectionData:
        SectionMain += '\n    <files>'
        SectionMain += '\n        <source>'
        SectionMain += '\n            <name>kodi.emby.tv</name>'
        SectionMain += '\n            <path pathversion="1">http://kodi.emby.tv</path>'
        SectionMain += '\n            <allowsharing>false</allowsharing>'
        SectionMain += '\n        </source>'
        SectionMain += '\n    </files>'
        Changed = True
    else:
        if '<name>kodi.emby.tv</name>' not in SectionData:
            SectionData += '\n        <source>'
            SectionData += '\n            <name>kodi.emby.tv</name>'
            SectionData += '\n            <path pathversion="1">http://kodi.emby.tv</path>'
            SectionData += '\n            <allowsharing>false</allowsharing>'
            SectionData += '\n        </source>'
            SectionMain = replace_Section("files", SectionData, SectionMain)
            Changed = True

    SectionData = get_Section(SectionMain, "video")

    if not SectionData:
        SectionMain += '\n    <video>'
        SectionMain += '\n        <source>'
        SectionMain += '\n            <name>emby-for-kodi-next-gen-addon-video-path-substitution</name>'
        SectionMain += '\n            <path pathversion="1">/emby_addon_mode/</path>'
        SectionMain += '\n            <allowsharing>false</allowsharing>'
        SectionMain += '\n        </source>'
        SectionMain += '\n        <source>'
        SectionMain += '\n            <name>emby-for-kodi-next-gen-addon-video</name>'
        SectionMain += '\n            <path pathversion="1">http://127.0.0.1:57342/</path>'
        SectionMain += '\n            <allowsharing>false</allowsharing>'
        SectionMain += '\n        </source>'
        SectionMain += '\n    </video>'
        Changed = True
    else:
        SectionChanged = False

        if '<name>emby-for-kodi-next-gen-addon-video-path-substitution</name>' not in SectionData:
            SectionData += '\n        <source>'
            SectionData += '\n            <name>emby-for-kodi-next-gen-addon-video-path-substitution</name>'
            SectionData += '\n            <path pathversion="1">/emby_addon_mode/</path>'
            SectionData += '\n            <allowsharing>false</allowsharing>'
            SectionData += '\n        </source>'
            SectionChanged = True

        if '<name>emby-for-kodi-next-gen-addon-video</name>' not in SectionData:
            SectionData += '\n        <source>'
            SectionData += '\n            <name>emby-for-kodi-next-gen-addon-video</name>'
            SectionData += '\n            <path pathversion="1">http://127.0.0.1:57342/</path>'
            SectionData += '\n            <allowsharing>false</allowsharing>'
            SectionData += '\n        </source>'
            SectionChanged = True

        if SectionChanged:
            SectionMain = replace_Section("video", SectionData, SectionMain)
            Changed = True

    SectionData = get_Section(SectionMain, "music")

    if not SectionData:
        SectionMain += '\n    <music>'
        SectionMain += '\n        <source>'
        SectionMain += '\n            <name>emby-for-kodi-next-gen-addon-music-path-substitution</name>'
        SectionMain += '\n            <path pathversion="1">/emby_addon_mode/</path>'
        SectionMain += '\n            <allowsharing>false</allowsharing>'
        SectionMain += '\n        </source>'
        SectionMain += '\n        <source>'
        SectionMain += '\n            <name>emby-for-kodi-next-gen-addon-music</name>'
        SectionMain += '\n            <path pathversion="1">http://127.0.0.1:57342/</path>'
        SectionMain += '\n            <allowsharing>false</allowsharing>'
        SectionMain += '\n        </source>'
        SectionMain += '\n    </music>'
        Changed = True
    else:
        SectionChanged = False

        if '<name>emby-for-kodi-next-gen-addon-music-path-substitution</name>' not in SectionData:
            SectionData += '\n        <source>'
            SectionData += '\n            <name>emby-for-kodi-next-gen-addon-music-path-substitution</name>'
            SectionData += '\n            <path pathversion="1">/emby_addon_mode/</path>'
            SectionData += '\n            <allowsharing>false</allowsharing>'
            SectionData += '\n        </source>'
            SectionChanged = True

        if '<name>emby-for-kodi-next-gen-addon-music</name>' not in SectionData:
            SectionData += '\n        <source>'
            SectionData += '\n            <name>emby-for-kodi-next-gen-addon-music</name>'
            SectionData += '\n            <path pathversion="1">http://127.0.0.1:57342/</path>'
            SectionData += '\n            <allowsharing>false</allowsharing>'
            SectionData += '\n        </source>'
            SectionChanged = True

        if SectionChanged:
            SectionMain = replace_Section("music", SectionData, SectionMain)
            Changed = True

    if Changed:
        SectionMain = f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<sources>\n{SectionMain}\n</sources>'
        utils.writeFileBinary(Filepath, SectionMain.encode("utf-8"))

# Settings table for audio and subtitle tracks.
def load_defaultvideosettings():
    FileData = utils.readFileString('special://profile/guisettings.xml')

    if FileData:
        SubtitlesLanguage = get_value("subtitles.languages", FileData)
        LocalSubtitlesLanguage = get_value("locale.subtitlelanguage", FileData)
        ShowSubtitles = bool(get_Section(FileData, "showsubtitles") == 'true')

        if LocalSubtitlesLanguage != "original":
            SubtitlesLanguage = LocalSubtitlesLanguage

        return {'SubtitlesLanguage': SubtitlesLanguage, 'ShowSubtitles': ShowSubtitles}

    return {}

def advanced_settings():
    Changed = False
    Filepath = 'special://profile/advancedsettings.xml'
    FileData = utils.readFileString(Filepath)

    if utils.enablehttp2:
        disablehttp2 = "false"
    else:
        disablehttp2 = "true"

    SectionMain = get_Section(FileData, "advancedsettings")
    SectionData = get_Section(SectionMain, "network")

    if not SectionData:
        SectionMain += '\n    <network>'
        SectionMain += f'\n        <disablehttp2>{disablehttp2}</disablehttp2>'
        SectionMain += f'\n        <curlclienttimeout>{utils.curltimeouts}</curlclienttimeout>'
        SectionMain += '\n    </network>'
        Changed = True
    else:
        SectionData = get_Section(SectionMain, "disablehttp2")

        if disablehttp2 != SectionData:
            SectionMain = add_replace_Section("disablehttp2", "network", f"<disablehttp2>{disablehttp2}</disablehttp2>", SectionMain)
            Changed = True

        SectionData = get_Section(SectionMain, "curlclienttimeout")

        if f'{utils.curltimeouts}' != SectionData:
            SectionMain = add_replace_Section("curlclienttimeout", "network", f"<curlclienttimeout>{utils.curltimeouts}</curlclienttimeout>", SectionMain)
            Changed = True

    SectionData = get_Section(SectionMain, "pathsubstitution")

    if not SectionData:
        SectionMain += '\n    <pathsubstitution>'
        SectionMain += '\n        <substitute>'
        SectionMain += '\n            <from>/emby_addon_mode/</from>'
        SectionMain += '\n            <to>http://127.0.0.1:57342/|redirect-limit=1000</to>'
        SectionMain += '\n        </substitute>'
        SectionMain += '\n    </pathsubstitution>'
        Changed = True
    else:
        if '<from>/emby_addon_mode/</from>' not in SectionData or '<to>http://127.0.0.1:57342/|redirect-limit=1000</to>' not in SectionData:
            SectionData += '\n        <substitute>'
            SectionData += '\n            <from>/emby_addon_mode/</from>'
            SectionData += '\n            <to>http://127.0.0.1:57342/|redirect-limit=1000</to>'
            SectionData += '\n        </substitute>'
            SectionMain = replace_Section("pathsubstitution", SectionData, SectionMain)
            Changed = True

    if Changed:
        SectionMain = f'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<advancedsettings>\n{SectionMain}\n</advancedsettings>'
        utils.writeFileBinary(Filepath, SectionMain.encode("utf-8"))

    return Changed

import xml.etree.ElementTree
import xbmc
from . import utils


# Create master lock compatible sources.
# Also add the kodi.emby.media source.
def sources():
    Filepath = 'special://profile/sources.xml'
    xmlData = utils.readFileString(Filepath)

    # skip if kodi.emby.media already added
    if 'kodi.emby.media' in xmlData and 'emby-for-kodi-next-gen-addon-video-path-substitution' in xmlData and 'emby-for-kodi-next-gen-addon-video' in xmlData and 'emby-for-kodi-next-gen-addon-music-path-substitution' in xmlData and 'emby-for-kodi-next-gen-addon-music' in xmlData and 'emby-for-kodi-next-gen-addon-pictures-path-substitution' in xmlData and 'emby-for-kodi-next-gen-addon-pictures' in xmlData:
        xbmc.log("EMBY.helper.xmls: Source http://kodi.emby.media exists, no change", 1) # LOGINFO
        return

    if xmlData:
        xmlData = xml.etree.ElementTree.fromstring(xmlData)
    else:
        xmlData = xml.etree.ElementTree.Element('sources')

    # Files sources
    files = xmlData.find('files')

    if not files:
        files = xml.etree.ElementTree.SubElement(xmlData, 'files')

    source = xml.etree.ElementTree.SubElement(files, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"

    # Video sources
    video = xmlData.find('video')

    if not video:
        video = xml.etree.ElementTree.SubElement(xmlData, 'video')

    source = xml.etree.ElementTree.SubElement(video, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-video-path-substitution"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "/emby_addon_mode/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
    source = xml.etree.ElementTree.SubElement(video, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-video"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://127.0.0.1:57342/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"


    # Music sources
    music = xmlData.find('music')

    if not music:
        music = xml.etree.ElementTree.SubElement(xmlData, 'music')

    source = xml.etree.ElementTree.SubElement(music, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-music-path-substitution"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "/emby_addon_mode/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
    source = xml.etree.ElementTree.SubElement(music, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-music"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://127.0.0.1:57342/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"

    # Pictures sources
    pictures = xmlData.find('pictures')

    if not pictures:
        pictures = xml.etree.ElementTree.SubElement(xmlData, 'pictures')

    source = xml.etree.ElementTree.SubElement(pictures, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-pictures-path-substitution"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "/emby_addon_mode/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
    source = xml.etree.ElementTree.SubElement(pictures, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "emby-for-kodi-next-gen-addon-pictures"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://127.0.0.1:57342/"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"

    # Write xml
    WriteXmlFile(Filepath, xmlData)

# Settings table for audio and subtitle tracks.
def load_defaultvideosettings():
    SubtitlesLanguage = ""
    LocalSubtitlesLanguage = ""
    FilePath = 'special://profile/guisettings.xml'
    xmlData = utils.readFileString(FilePath)

    if xmlData:
        xmlData = xml.etree.ElementTree.fromstring(xmlData)

        for child in xmlData:
            if 'id' in child.attrib:
                if child.attrib['id'] == "subtitles.languages":
                    SubtitlesLanguage = child.text
                elif child.attrib['id'] == "locale.subtitlelanguage":
                    if child.text.lower() != "original":
                        LocalSubtitlesLanguage = child.text

        if LocalSubtitlesLanguage:
            SubtitlesLanguage = LocalSubtitlesLanguage

        default = xmlData.find('defaultvideosettings')
        return {'SubtitlesLanguage': SubtitlesLanguage, 'ShowSubtitles': default.find('showsubtitles').text == 'true'}

    return {}

def advanced_settings():
    WriteData = False
    Filepath = 'special://profile/advancedsettings.xml'
    FileData = utils.readFileString(Filepath)

    if utils.enablehttp2:
        disablehttp2 = "false"
    else:
        disablehttp2 = "true"

    if FileData:
        if "<from>/emby_addon_mode/</from>" in FileData and f"<curllowspeedtime>{utils.curltimeouts}</curllowspeedtime>" in FileData and f"<curlclienttimeout>{utils.curltimeouts}</curlclienttimeout>" in FileData and f"<disablehttp2>{disablehttp2}</disablehttp2>" in FileData:
            xbmc.log("EMBY.helper.xmls: advancedsettings.xml valid, no change", 1) # LOGINFO
            return False

        xmlData = xml.etree.ElementTree.fromstring(FileData)
        pathsubstitution = xmlData.find('pathsubstitution')

        if pathsubstitution is not None:
            substitute = pathsubstitution.find('substitute')

            if substitute is not None:
                fromPath = substitute.find('from')

                if fromPath.text != "/emby_addon_mode/":
                    xbmc.log("EMBY.helper.xmls: advancedsettings.xml set path substitution from", 2) # LOGWARNING
                    substitute.remove(fromPath)
                    xml.etree.ElementTree.SubElement(substitute, 'from').text = "/emby_addon_mode/"
                    WriteData = True

                toPath = substitute.find('to')

                if toPath.text != "http://127.0.0.1:57342/":
                    xbmc.log("EMBY.helper.xmls: advancedsettings.xml set path substitution to", 2) # LOGWARNING
                    substitute.remove(toPath)
                    xml.etree.ElementTree.SubElement(substitute, 'to').text = "http://127.0.0.1:57342/"
                    WriteData = True
            else:
                substitute = xml.etree.ElementTree.SubElement(pathsubstitution, 'substitute')
                xml.etree.ElementTree.SubElement(substitute, 'from').text = "/emby_addon_mode/"
                xml.etree.ElementTree.SubElement(substitute, 'to').text = "http://127.0.0.1:57342/"
                WriteData = True
        else:
            xbmc.log("EMBY.helper.xmls: advancedsettings.xml set pathsubstitution", 2) # LOGWARNING
            pathsubstitution = xml.etree.ElementTree.SubElement(xmlData, 'pathsubstitution')
            substitute = xml.etree.ElementTree.SubElement(pathsubstitution, 'substitute')
            xml.etree.ElementTree.SubElement(substitute, 'from').text = "/emby_addon_mode/"
            xml.etree.ElementTree.SubElement(substitute, 'to').text = "http://127.0.0.1:57342/"
            WriteData = True

        videolibrary = xmlData.find('videolibrary')

        if videolibrary is not None:
            cleanonupdate = videolibrary.find('cleanonupdate')

            if cleanonupdate is not None and cleanonupdate.text == "true":
                xbmc.log("EMBY.helper.xmls: cleanonupdate disabled", 2) # LOGWARNING
                videolibrary.remove(cleanonupdate)
                WriteData = True
                utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33097))

        Network = xmlData.find('network')

        if Network is not None:
            curlclienttimeout = Network.find('curlclienttimeout')

            if curlclienttimeout is not None:
                if curlclienttimeout.text != utils.curltimeouts:
                    xbmc.log("EMBY.helper.xmls: advancedsettings.xml set curlclienttimeout", 2) # LOGWARNING
                    Network.remove(curlclienttimeout)
                    xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = utils.curltimeouts
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = utils.curltimeouts
                WriteData = True

            curllowspeedtime = Network.find('curllowspeedtime')

            if curllowspeedtime is not None:
                if curllowspeedtime.text != utils.curltimeouts:
                    xbmc.log("EMBY.helper.xmls: advancedsettings.xml set curllowspeedtime", 2) # LOGWARNING
                    Network.remove(curllowspeedtime)
                    xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = utils.curltimeouts
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = utils.curltimeouts
                WriteData = True

            # set HTTP2 support
            curldisablehttp2 = Network.find('disablehttp2')

            if curldisablehttp2 is not None:
                if curldisablehttp2.text != disablehttp2:
                    xbmc.log("EMBY.helper.xmls: advancedsettings.xml set disablehttp2", 2) # LOGWARNING
                    Network.remove(curldisablehttp2)
                    xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = disablehttp2
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = disablehttp2
                WriteData = True
        else:
            xbmc.log("EMBY.helper.xmls: advancedsettings.xml set network", 2) # LOGWARNING
            Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
            xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = utils.curltimeouts
            xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = utils.curltimeouts
            xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = disablehttp2
            WriteData = True
    else:
        xbmc.log("EMBY.helper.xmls: advancedsettings.xml set data", 2) # LOGWARNING
        xmlData = xml.etree.ElementTree.Element('advancedsettings')
        Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
        xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = utils.curltimeouts
        xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = utils.curltimeouts
        xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = disablehttp2
        pathsubstitution = xml.etree.ElementTree.SubElement(xmlData, 'pathsubstitution')
        substitute = xml.etree.ElementTree.SubElement(pathsubstitution, 'substitute')
        xml.etree.ElementTree.SubElement(substitute, 'from').text = "/emby_addon_mode/"
        xml.etree.ElementTree.SubElement(substitute, 'to').text = "http://127.0.0.1:57342/"
        WriteData = True

    if WriteData:
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33268), icon=utils.icon, time=10000, sound=True)
        WriteXmlFile(Filepath, xmlData)
        return True

    return False

def WriteXmlFile(FilePath, Data):
    DataQueue = [(0, Data)]

    # Prettify xml
    while DataQueue:
        level, element = DataQueue.pop(0)
        children = []

        for child in list(element):
            children.append((level + 1, child))

        if children:
            element.text = f"\n{'    ' * (level + 1)}"

        if DataQueue:
            element.tail = f"\n{'    ' * DataQueue[0][0]}"
        else:
            element.tail = f"\n{'    ' * (level - 1)}"

        DataQueue[0:0] = children

    # write xml
    Data = xml.etree.ElementTree.tostring(Data)
    Data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + Data
    utils.writeFileBinary(FilePath, Data)

def verify_settings_file():
    xmlData = utils.readFileString(f"{utils.FolderAddonUserdata}settings.xml")

    if xmlData:
        try:
            xml.etree.ElementTree.fromstring(xmlData)
        except Exception as Error:
            xbmc.log(f"EMBY.helper.xmls: Setting file corupted, restore: {Error}", 3) # LOGERROR
            return False

    return True

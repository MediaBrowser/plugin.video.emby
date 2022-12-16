import xml.etree.ElementTree
from . import utils, loghandler

LOG = loghandler.LOG('EMBY.helper.xmls')


# Create master lock compatible sources.
# Also add the kodi.emby.media source.
def sources():
    Filepath = 'special://profile/sources.xml'
    xmlData = utils.readFileString(Filepath)

    # skip if kodi.emby.media already added
    if 'http://kodi.emby.media' in xmlData:
        LOG.info("Source http://kodi.emby.media exists, no change")
        return

    if xmlData:
        xmlData = xml.etree.ElementTree.fromstring(xmlData)
    else:
        xmlData = xml.etree.ElementTree.Element('sources')

    files = xmlData.find('files')

    if not files:
        files = xml.etree.ElementTree.SubElement(xmlData, 'files')

    source = xml.etree.ElementTree.SubElement(files, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
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

def restart_required(Filepath, xmlData):
    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33268), icon=utils.icon, time=10000, sound=True)
    WriteXmlFile(Filepath, xmlData)

def advanced_settings():
    WriteData = False
    Filepath = 'special://profile/advancedsettings.xml'
    FileData = utils.readFileString(Filepath)

    if FileData:
        http2check = "<disablehttp2>%s</disablehttp2>" % utils.disablehttp2

        if "<curllowspeedtime>120</curllowspeedtime>" in FileData and "<curlclienttimeout>120</curlclienttimeout>" in FileData and http2check in FileData:
            LOG.info("advancedsettings.xml valid, no change")
            return False

        xmlData = xml.etree.ElementTree.fromstring(FileData)
        videolibrary = xmlData.find('videolibrary')

        if videolibrary is not None:
            cleanonupdate = videolibrary.find('cleanonupdate')

            if cleanonupdate is not None and cleanonupdate.text == "true":
                LOG.warning("cleanonupdate disabled")
                videolibrary.remove(cleanonupdate)
                WriteData = True
                utils.Dialog.ok(heading=utils.addon_name, message=utils.Translate(33097))

        Network = xmlData.find('network')

        if Network is not None:
            curlclienttimeout = Network.find('curlclienttimeout')

            if curlclienttimeout is not None:
                if curlclienttimeout.text != "120":
                    LOG.warning("advancedsettings.xml set curlclienttimeout")
                    Network.remove(curlclienttimeout)
                    xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "120"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "120"
                WriteData = True

            curllowspeedtime = Network.find('curllowspeedtime')

            if curllowspeedtime is not None:
                if curllowspeedtime.text != "120":
                    LOG.warning("advancedsettings.xml set curllowspeedtime")
                    Network.remove(curllowspeedtime)
                    xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "120"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "120"
                WriteData = True

            # set HTTP2 support
            curldisablehttp2 = Network.find('disablehttp2')

            if curldisablehttp2 is not None:
                if curldisablehttp2.text != utils.disablehttp2:
                    LOG.warning("advancedsettings.xml set disablehttp2")
                    Network.remove(curldisablehttp2)
                    xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = utils.disablehttp2
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = utils.disablehttp2
                WriteData = True
        else:
            LOG.warning("advancedsettings.xml set network")
            Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
            xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "120"
            xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "120"
            xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = utils.disablehttp2
            WriteData = True
    else:
        LOG.warning("advancedsettings.xml set data")
        xmlData = xml.etree.ElementTree.Element('advancedsettings')
        Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
        xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "120"
        xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "120"
        xml.etree.ElementTree.SubElement(Network, 'disablehttp2').text = utils.disablehttp2
        WriteData = True

    if WriteData:
        restart_required(Filepath, xmlData)

    return WriteData

def WriteXmlFile(FilePath, Data):
    DataQueue = [(0, Data)]

    # Prettify xml
    while DataQueue:
        level, element = DataQueue.pop(0)
        children = []

        for child in list(element):
            children.append((level + 1, child))

        if children:
            element.text = '\n' + '    ' * (level + 1)

        if DataQueue:
            element.tail = '\n' + '    ' * DataQueue[0][0]
        else:
            element.tail = '\n' + '    ' * (level - 1)

        DataQueue[0:0] = children

    # write xml
    Data = xml.etree.ElementTree.tostring(Data)
    Data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n' + Data
    utils.writeFileBinary(FilePath, Data)

def verify_settings_file():
    xmlData = utils.readFileString("%ssettings.xml" % utils.FolderAddonUserdata)

    if xmlData:
        try:
            xml.etree.ElementTree.fromstring(xmlData)
        except Exception as Error:
            LOG.error("Setting file corupted, restore: %s" % Error)
            return False

    return True

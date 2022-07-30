import xml.etree.ElementTree
from urllib.parse import urlencode
from . import utils, loghandler

LOG = loghandler.LOG('EMBY.helper.xmls')


# Create master lock compatible sources.
# Also add the kodi.emby.media source.
def sources():
    Filepath = 'special://profile/sources.xml'
    xmlData = utils.readFileString(Filepath)

    if xmlData:
        xmlData = xml.etree.ElementTree.fromstring(xmlData)
    else:
        xmlData = xml.etree.ElementTree.Element('sources')

    files = xmlData.find('files')

    if not files:
        files = xml.etree.ElementTree.SubElement(xmlData, 'files')

    for source in xmlData.findall('.//path'):
        if source.text == 'http://kodi.emby.media':
            return

    source = xml.etree.ElementTree.SubElement(files, 'source')
    xml.etree.ElementTree.SubElement(source, 'name').text = "kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
    WriteXmlFile(Filepath, xmlData)

# Create tvtunes.nfo
def tvtunes_nfo(path, urls):
    if utils.checkFileExists(path):
        xmlData = utils.readFileString(path)
        xmlData = xml.etree.ElementTree.fromstring(xmlData)
    else:
        xmlData = xml.etree.ElementTree.Element('tvtunes')

    for elem in xmlData.iter('tvtunes'):
        for Filename in list(elem):
            elem.remove(Filename)

    for url in urls:
        xml.etree.ElementTree.SubElement(xmlData, 'file').text = url

    WriteXmlFile(path, xmlData)

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
        return {
            'SubtitlesLanguage': SubtitlesLanguage,
            'Deinterlace': default.find('interlacemethod').text,
            'ViewMode': default.find('viewmode').text,
            'ZoomAmount': default.find('zoomamount').text,
            'PixelRatio': default.find('pixelratio').text,
            'VerticalShift': default.find('verticalshift').text,
            'SubtitleDelay': default.find('subtitledelay').text,
            'ShowSubtitles': default.find('showsubtitles').text == 'true',
            'Brightness': default.find('brightness').text,
            'Contrast': default.find('contrast').text,
            'Gamma': default.find('gamma').text,
            'VolumeAmplification': default.find('volumeamplification').text,
            'AudioDelay': default.find('audiodelay').text,
            'Sharpness': default.find('sharpness').text,
            'NoiseReduction': default.find('noisereduction').text,
            'NonLinStretch': int(default.find('nonlinstretch').text == 'true'),
            'PostProcess': int(default.find('postprocess').text == 'true'),
            'ScalingMethod': default.find('scalingmethod').text,
            'StereoMode': default.find('stereomode').text,
            'CenterMixLevel': default.find('centermixlevel').text
        }

    return {}

def restart_required(Filepath, xmlData):
    utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33268), icon=utils.icon, time=10000, sound=True)

    if utils.sleep(10):  # Give Kodi time to complete startup before reset
        return

    WriteXmlFile(Filepath, xmlData)

def advanced_settings_runtimelimits(xmlData):
    WriteData = False
    Filepath = ""

    if not xmlData: # Toggle via settings menu, otherwise it's triggered by Kodi start
        Filepath = 'special://profile/advancedsettings.xml'
        FileData = utils.readFileString(Filepath)
        xmlData = xml.etree.ElementTree.fromstring(FileData)

    if utils.syncruntimelimits:
        video = xmlData.find('video')

        if video is not None:
            playcountminimumpercent = video.find('playcountminimumpercent')

            if playcountminimumpercent is not None:
                if playcountminimumpercent.text != "101":
                    video.remove(playcountminimumpercent)
                    xml.etree.ElementTree.SubElement(video, 'playcountminimumpercent').text = "101"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(video, 'playcountminimumpercent').text = "101"
                WriteData = True

            ignorepercentatend = video.find('ignorepercentatend')

            if ignorepercentatend is not None:
                if ignorepercentatend.text != "101":
                    video.remove(ignorepercentatend)
                    xml.etree.ElementTree.SubElement(video, 'ignorepercentatend').text = "101"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(video, 'ignorepercentatend').text = "101"
                WriteData = True
        else:
            video = xml.etree.ElementTree.SubElement(xmlData, 'video')
            xml.etree.ElementTree.SubElement(video, 'playcountminimumpercent').text = "101"
            xml.etree.ElementTree.SubElement(video, 'ignorepercentatend').text = "101"
            WriteData = True
    else:
        video = xmlData.find('video')

        if video is not None:
            playcountminimumpercent = video.find('playcountminimumpercent')

            if playcountminimumpercent is not None:
                video.remove(playcountminimumpercent)
                WriteData = True

            ignorepercentatend = video.find('ignorepercentatend')

            if ignorepercentatend is not None:
                video.remove(ignorepercentatend)
                WriteData = True

    if Filepath and WriteData:
        restart_required(Filepath, xmlData)

    return WriteData

def advanced_settings():
    WriteData = False
    Filepath = 'special://profile/advancedsettings.xml'
    FileData = utils.readFileString(Filepath)

    if FileData:
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

    if advanced_settings_runtimelimits(xmlData):
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

def KodiDefaultNodes():
    utils.mkDir("special://profile/library/video/")
    utils.mkDir("special://profile/library/music/")
    utils.copytree("special://xbmc/system/library/video/", "special://profile/library/video/")
    utils.copytree("special://xbmc/system/library/music/", "special://profile/library/music/")

    for index, node in enumerate(['movies', 'tvshows', 'musicvideos']):
        filename = "%s%s/%s" % ("special://profile/library/video/", node, "index.xml")
        xmlData = utils.readFileString(filename)

        if xmlData:
            xmlData = xml.etree.ElementTree.fromstring(xmlData)
            xmlData.set('order', str(17 + index))
            WriteXmlFile(filename, xmlData)

    for index, node in enumerate(['music']):
        filename = "%s%s/%s" % ("special://profile/library/music/", node, "index.xml")
        xmlData = utils.readFileString(filename)

        if xmlData:
            xmlData = xml.etree.ElementTree.fromstring(xmlData)
            xmlData.set('order', str(17 + index))
            WriteXmlFile(filename, xmlData)

def add_favorites():
    utils.mkDir("special://profile/library/video/")
    index = 0

    for single in [{'Name': utils.Translate(30180), 'Tag': "Favorite movies", 'MediaType': "movies"}, {'Name': utils.Translate(30181), 'Tag': "Favorite tvshows", 'MediaType': "tvshows"}, {'Name': utils.Translate(30182), 'Tag': "Favorite episodes", 'MediaType': "episodes"}, {'Name': "Favorite musicvideos", 'Tag': "Favorite musicvideos", 'MediaType': "musicvideos"}]:
        index += 1
        filepath = "special://profile/library/video/emby_%s.xml" % single['Tag'].replace(" ", "_")
        xmlData = utils.readFileString(filepath)

        if xmlData:
            xmlData = xml.etree.ElementTree.fromstring(xmlData)
        else:
            if single['MediaType'] == 'episodes':
                xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "folder"})
            else:
                xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "filter"})

            xml.etree.ElementTree.SubElement(xmlData, 'icon').text = 'DefaultFavourites.png'
            xml.etree.ElementTree.SubElement(xmlData, 'label')
            xml.etree.ElementTree.SubElement(xmlData, 'match')
            xml.etree.ElementTree.SubElement(xmlData, 'content')

        label = xmlData.find('label')
        label.text = "EMBY: %s" % single['Name']
        content = xmlData.find('content')
        content.text = single['MediaType']
        match = xmlData.find('match')
        match.text = "all"

        if single['MediaType'] != 'episodes':
            for rule in xmlData.findall('.//value'):
                if rule.text == single['Tag']:
                    break
            else:
                rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
                xml.etree.ElementTree.SubElement(rule, 'value').text = single['Tag']

            for rule in xmlData.findall('.//order'):
                if rule.text == "sorttitle":
                    break
            else:
                xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
        else:
            params = {'mode': "favepisodes"}
            path = "plugin://%s/?%s" % (utils.PluginId, urlencode(params))

            for rule in xmlData.findall('.//path'):
                rule.text = path
                break
            else:
                xml.etree.ElementTree.SubElement(xmlData, 'path').text = path

            for rule in xmlData.findall('.//content'):
                rule.text = "episodes"
                break
            else:
                xml.etree.ElementTree.SubElement(xmlData, 'content').text = "episodes"

        WriteXmlFile(filepath, xmlData)

def verify_settings_file():
    xmlData = utils.readFileString("%ssettings.xml" % utils.FolderAddonUserdata)

    if xmlData:
        try:
            xml.etree.ElementTree.fromstring(xmlData)
        except Exception as Error:
            LOG.error("Setting file corupted, restore: %s" % Error)
            return False

    return True

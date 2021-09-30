# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree
import xbmcvfs
from . import loghandler
from . import utils as Utils

LOG = loghandler.LOG('EMBY.helper.xmls')


# Create master lock compatible sources.
# Also add the kodi.emby.media source.
def sources():
    Filepath = os.path.join(Utils.FolderProfile, 'sources.xml')

    if xbmcvfs.exists(Filepath):
        xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
    else:
        xmlData = xml.etree.ElementTree.Element('sources')
        video = xml.etree.ElementTree.SubElement(xmlData, 'video')
        files = xml.etree.ElementTree.SubElement(xmlData, 'files')
        xml.etree.ElementTree.SubElement(video, 'default', attrib={'pathversion': "1"})
        xml.etree.ElementTree.SubElement(files, 'default', attrib={'pathversion': "1"})

    video = xmlData.find('video')
    count_http = 1
    count_smb = 1

    for source in xmlData.findall('.//path'):
        if source.text == 'smb://':
            count_smb -= 1
        elif source.text == 'http://':
            count_http -= 1

        if not count_http and not count_smb:
            break
    else:
        for protocol in ('smb://', 'http://'):
            if (protocol == 'smb://' and count_smb > 0) or (protocol == 'http://' and count_http > 0):
                source = xml.etree.ElementTree.SubElement(video, 'source')
                xml.etree.ElementTree.SubElement(source, 'name').text = "Emby"
                xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = protocol
                xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"

    try:
        files = xmlData.find('files')

        if files is None:
            files = xml.etree.ElementTree.SubElement(xmlData, 'files')

        for source in xmlData.findall('.//path'):
            if source.text == 'http://kodi.emby.media':
                break
        else:
            source = xml.etree.ElementTree.SubElement(files, 'source')
            xml.etree.ElementTree.SubElement(source, 'name').text = "kodi.emby.media"
            xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
            xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
    except Exception as error:
        LOG.error(error)

    WriteXmlFile(Filepath, xmlData)

# Create tvtunes.nfo
def tvtunes_nfo(path, urls):
    if xbmcvfs.exists(path):
        xmlData = xml.etree.ElementTree.parse(path).getroot()
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

    try:  # Skip fileread issues
        FilePath = os.path.join(Utils.FolderProfile, 'guisettings.xml')
        xmlData = xml.etree.ElementTree.parse(FilePath).getroot()

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
    except:
        return {}

# Track the existence of <cleanonupdate>true</cleanonupdate>
# It is incompatible with plugin paths.
def advanced_settings():
    Filepath = os.path.join(Utils.FolderProfile, 'advancedsettings.xml')

    if xbmcvfs.exists(Filepath):
        xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
        video = xmlData.find('videolibrary')

        if video is not None:
            cleanonupdate = video.find('cleanonupdate')

            if cleanonupdate is not None and cleanonupdate.text == "true":
                LOG.warning("cleanonupdate disabled")
                video.remove(cleanonupdate)
                WriteXmlFile(Filepath, xmlData)
                Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33097))

def advanced_settings_add_timeouts():
    WriteData = False
    Filepath = os.path.join(Utils.FolderProfile, 'advancedsettings.xml')

    if xbmcvfs.exists(Filepath):
        xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
        Network = xmlData.find('network')

        if Network is not None:
            curlclienttimeout = Network.find('curlclienttimeout')

            if curlclienttimeout is not None:
                if curlclienttimeout.text != "9999999":
                    LOG.warning("advancedsettings.xml set curlclienttimeout")
                    Network.remove(curlclienttimeout)
                    xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
                WriteData = True

            curllowspeedtime = Network.find('curllowspeedtime')

            if curllowspeedtime is not None:
                if curllowspeedtime.text != "9999999":
                    LOG.warning("advancedsettings.xml set curllowspeedtime")
                    Network.remove(curllowspeedtime)
                    xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
                    WriteData = True
            else:
                xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
                WriteData = True
        else:
            LOG.warning("advancedsettings.xml set network")
            Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
            xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
            xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
            WriteData = True
    else:
        LOG.warning("advancedsettings.xml set data")
        xmlData = xml.etree.ElementTree.Element('advancedsettings')
        Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
        xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
        xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
        WriteData = True

    if WriteData:
        WriteXmlFile(Filepath, xmlData)

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
    Data = b"<?xml version='1.0' encoding='UTF-8'?>\n" + Data
    outputfile = xbmcvfs.File(FilePath, 'w')
    outputfile.write(Data)
    outputfile.close()

def KodiDefaultNodes():
    if not xbmcvfs.exists(Utils.FolderLibraryVideo):
        xbmcvfs.mkdirs(Utils.FolderLibraryVideo)

    if not xbmcvfs.exists(Utils.FolderLibraryMusic):
        xbmcvfs.mkdirs(Utils.FolderLibraryMusic)

    Utils.copytree(Utils.FolderXbmcLibraryVideo, Utils.FolderLibraryVideo)
    Utils.copytree(Utils.FolderXbmcLibraryMusic, Utils.FolderLibraryMusic)

    for index, node in enumerate(['movies', 'tvshows', 'musicvideos']):
        filename = os.path.join(Utils.FolderLibraryVideo, node, "index.xml")

        if xbmcvfs.exists(filename):
            try:
                xmlData = xml.etree.ElementTree.parse(filename).getroot()
            except Exception as error:
                LOG.error(error)
                continue

            xmlData.set('order', str(17 + index))
            WriteXmlFile(filename, xmlData)

    for index, node in enumerate(['music']):
        filename = os.path.join(Utils.FolderLibraryMusic, node, "index.xml")

        if xbmcvfs.exists(filename):
            try:
                xmlData = xml.etree.ElementTree.parse(filename).getroot()
            except Exception as error:
                LOG.error(error)
                continue

            xmlData.set('order', str(17 + index))
            WriteXmlFile(filename, xmlData)

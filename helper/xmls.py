# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree
import xbmcvfs
import xbmc

from . import loghandler

class Xmls():
    def __init__(self, Utils):
        self.LOG = loghandler.LOG('EMBY.helper.xmls.Xmls')
        self.Utils = Utils

    #Create master lock compatible sources.
    #Also add the kodi.emby.media source.
    def sources(self):
        path = self.Utils.Basics.translatePath('special://profile/')
        Filepath = os.path.join(path, 'sources.xml')

        try:
            xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
        except:
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
            self.LOG.error(error)

        self.Utils.indent(xmlData, 0)
        self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), Filepath)

    #Create tvtunes.nfo
    def tvtunes_nfo(self, path, urls):
        if xbmcvfs.exists(path):
            xmlData = xml.etree.ElementTree.parse(path).getroot()
        else:
            xmlData = xml.etree.ElementTree.Element('tvtunes')

        for elem in xmlData.iter('tvtunes'):
            for Filename in list(elem):
                elem.remove(Filename)

        for url in urls:
            xml.etree.ElementTree.SubElement(xmlData, 'file').text = url

        self.Utils.indent(xmlData, 0)
        self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), path)

    #Settings table for audio and subtitle tracks.
    def load_defaultvideosettings(self):
        try: #Skip fileread issues
            path = xbmc.translatePath('special://profile/')
            FilePath = os.path.join(path, 'guisettings.xml')
            xmlData = xml.etree.ElementTree.parse(FilePath).getroot()
            default = xmlData.find('defaultvideosettings')
            return {
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

    #Track the existence of <cleanonupdate>true</cleanonupdate>
    #It is incompatible with plugin paths.
    def advanced_settings(self):
        video = None
        path = self.Utils.Basics.translatePath('special://profile/')
        Filepath = os.path.join(path, 'advancedsettings.xml')

        if xbmcvfs.exists(Filepath):
            xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
            video = xmlData.find('videolibrary')

        if video is not None:
            cleanonupdate = video.find('cleanonupdate')

            if cleanonupdate is not None and cleanonupdate.text == "true":
                self.LOG.warning("cleanonupdate disabled")
                video.remove(cleanonupdate)
                self.Utils.indent(xmlData, 0)
                self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), Filepath)
                self.Utils.dialog("ok", heading="{emby}", line1=self.Utils.Basics.Translate(33097))
                xbmc.executebuiltin('RestartApp')

    def advanced_settings_add_timeouts(self):
        WriteData = False
        path = self.Utils.Basics.translatePath('special://profile/')
        Filepath = os.path.join(path, 'advancedsettings.xml')

        if xbmcvfs.exists(Filepath):
            xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
            Network = xmlData.find('network')

            if Network is not None:
                curlclienttimeout = Network.find('curlclienttimeout')

                if curlclienttimeout is not None:
                    if curlclienttimeout.text != "9999999":
                        self.LOG.warning("advancedsettings.xml set curlclienttimeout")
                        Network.remove(curlclienttimeout)
                        xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
                        WriteData = True
                else:
                    xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
                    WriteData = True

                curllowspeedtime = Network.find('curllowspeedtime')

                if curllowspeedtime is not None:
                    if curllowspeedtime.text != "9999999":
                        self.LOG.warning("advancedsettings.xml set curllowspeedtime")
                        Network.remove(curllowspeedtime)
                        xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
                        WriteData = True
                else:
                    xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
                    WriteData = True
            else:
                self.LOG.warning("advancedsettings.xml set network")
                Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
                xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
                xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
                WriteData = True

        else:
            self.LOG.warning("advancedsettings.xml set data")
            xmlData = xml.etree.ElementTree.Element('advancedsettings')
            Network = xml.etree.ElementTree.SubElement(xmlData, 'network')
            xml.etree.ElementTree.SubElement(Network, 'curllowspeedtime').text = "9999999"
            xml.etree.ElementTree.SubElement(Network, 'curlclienttimeout').text = "9999999"
            WriteData = True

        if WriteData:
            self.Utils.indent(xmlData, 0)
            self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), Filepath)
            self.Utils.dialog("ok", heading="{emby}", line1="Network timeouts modified in advancedsettings.xml, Kodi will reboot now")
            xbmc.executebuiltin('RestartApp')

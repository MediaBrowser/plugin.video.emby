# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
import xml.etree.ElementTree as etree

import xbmc

from . import _, indent, write_xml, dialog, settings

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################

def sources():

    ''' Create master lock compatible sources.
        Also add the kodi.emby.media source.
    '''
    path = xbmc.translatePath('special://profile/').decode('utf-8')
    file = os.path.join(path, 'sources.xml').decode('utf-8')

    try:
        xml = etree.parse(file).getroot()
    except Exception:

        xml = etree.Element('sources')
        video = etree.SubElement(xml, 'video')
        files = etree.SubElement(xml, 'files')
        etree.SubElement(video, 'default', attrib={'pathversion': "1"})
        etree.SubElement(files, 'default', attrib={'pathversion': "1"})

    video = xml.find('video')
    count_http = 1
    count_smb = 1
    count_nfs = 1

    for source in xml.findall('.//path'):
        if source.text == 'smb://':
            count_smb -= 1
        elif source.text == 'http://':
            count_http -= 1
        elif source.text == 'nfs://':
            count_nfs -= 1

        if not count_http and not count_smb and not count_nfs:
            break
    else:
        for protocol in ('smb://', 'http://', 'nfs://'):
            if (protocol == 'smb://' and count_smb > 0) or (protocol == 'http://' and count_http > 0) or (protocol == 'nfs://' and count_nfs > 0):

                source = etree.SubElement(video, 'source')
                etree.SubElement(source, 'name').text = "Emby"
                etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = protocol
                etree.SubElement(source, 'allowsharing').text = "true"

    try:
        files = xml.find('files')

        if files is None:
            files = etree.SubElement(xml, 'files')

        for source in xml.findall('.//path'):
            if source.text == 'http://kodi.emby.media':
                break
        else:
            source = etree.SubElement(files, 'source')
            etree.SubElement(source, 'name').text = "kodi.emby.media"
            etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
            etree.SubElement(source, 'allowsharing').text = "true"
    except Exception as error:
        LOG.exception(error)

    indent(xml)
    write_xml(etree.tostring(xml, 'UTF-8'), file)

def tvtunes_nfo(path, urls):

    ''' Create tvtunes.nfo
    '''
    try:
        xml = etree.parse(path).getroot()
    except Exception:
        xml = etree.Element('tvtunes')

    for elem in xml.getiterator('tvtunes'):
        for file in list(elem):
            elem.remove(file)

    for url in urls:
        etree.SubElement(xml, 'file').text = url

    indent(xml)
    write_xml(etree.tostring(xml, 'UTF-8'), path)

def advanced_settings():

    ''' Track the existence of <cleanonupdate>true</cleanonupdate>
        It is incompatible with plugin paths.
    '''
    if settings('useDirectPaths') != "0":
        return

    path = xbmc.translatePath('special://profile/').decode('utf-8')
    file = os.path.join(path, 'advancedsettings.xml').decode('utf-8')

    try:
        xml = etree.parse(file).getroot()
    except Exception:
        return

    video = xml.find('videolibrary')

    if video is not None:
        cleanonupdate = video.find('cleanonupdate')

        if cleanonupdate is not None and cleanonupdate.text == "true":

            LOG.warn("cleanonupdate disabled")
            video.remove(cleanonupdate)

            indent(xml)
            write_xml(etree.tostring(xml, 'UTF-8'), path)

            dialog("ok", heading="{emby}", line1=_(33097))
            xbmc.executebuiltin('RestartApp')

            return True

def default_settings_default():

    ''' Settings table for audio and subtitle tracks.
    '''
    path = xbmc.translatePath('special://profile/').decode('utf-8')
    file = os.path.join(path, 'guisettings.xml').decode('utf-8')

    try:
        xml = etree.parse(file).getroot()
    except Exception:
        return

    default = xml.find('defaultvideosettings')

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

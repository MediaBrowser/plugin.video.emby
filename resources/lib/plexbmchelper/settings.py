import uuid
import xbmc
import xbmcaddon
from xml.dom.minidom import parse
import utils

settings = {}
try:
    path = xbmc.translatePath(
        'special://userdata/guisettings.xml').decode('utf-8')
    guidoc = parse(path)
except:
    print "PlexKodiConnect - Unable to read XBMC's guisettings.xml"

def getGUI(name):
    global guidoc
    if guidoc is None:
        return False
    try:
        return guidoc.getElementsByTagName(name)[0].firstChild.nodeValue
    except:
        return ""

addon = xbmcaddon.Addon()
plexbmc = xbmcaddon.Addon('plugin.video.plexkodiconnect')

settings['debug'] = utils.settings('companionDebugging')
settings['gdm_debug'] = utils.settings('companionGDMDebugging')

# Transform 'true' into True because of the way Kodi's file settings work
kodiSettingsList = ['debug', 'gdm_debug']
for entry in kodiSettingsList:
    if settings[entry] == 'true':
        settings[entry] = True
    else:
        settings[entry] = False

settings['client_name'] = plexbmc.getSetting('deviceName')

# XBMC web server settings
xbmc.sleep(5000)
settings['webserver_enabled'] = (getGUI('webserver') == "true")
settings['port'] = int(getGUI('webserverport'))
settings['user'] = getGUI('webserverusername')
settings['passwd'] = getGUI('webserverpassword')

settings['uuid'] = plexbmc.getSetting('plex_client_Id')

settings['version'] = plexbmc.getAddonInfo('version')
settings['plexbmc_version'] = plexbmc.getAddonInfo('version')
settings['myplex_user'] = plexbmc.getSetting('username')
settings['serverList'] = []
settings['myport'] = addon.getSetting('companionPort')

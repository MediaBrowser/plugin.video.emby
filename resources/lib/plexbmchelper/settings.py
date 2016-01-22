import uuid
import xbmc
import xbmcaddon
from xml.dom.minidom import parse

settings = {}
try:
    guidoc = parse(xbmc.translatePath('special://userdata/guisettings.xml'))
except:
    print "Unable to read XBMC's guisettings.xml"

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

if plexbmc.getSetting('logLevel') == '2' or \
        plexbmc.getSetting('logLevel') == '1':
    settings['debug'] = 'true'
    settings['gdm_debug'] = 'true'
else:
    settings['debug'] = 'false'
    settings['gdm_debug'] = 'false'

settings['client_name'] = plexbmc.getSetting('deviceName')

# XBMC web server settings
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

import uuid
import xbmc
import xbmcaddon
from xml.dom.minidom import parse
import utils

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

settings['debug'] = utils.settings('companionDebugging')
settings['gdm_debug'] = utils.settings('companionGDMDebugging')

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

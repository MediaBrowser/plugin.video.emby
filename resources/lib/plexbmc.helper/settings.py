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
plexbmc = xbmcaddon.Addon('plugin.video.plexbmc')

settings['debug'] = addon.getSetting('debug') == "true"
settings['gdm_debug'] = addon.getSetting('gdm_debug') == "true"
if addon.getSetting('use_xbmc_name') == "true":
    settings['client_name'] = getGUI('devicename')
else:
    settings['client_name'] = addon.getSetting('c_name')
# XBMC web server settings
settings['webserver_enabled'] = (getGUI('webserver') == "true")
settings['port'] = int(getGUI('webserverport'))
settings['user'] = getGUI('webserverusername')
settings['passwd'] = getGUI('webserverpassword')

settings['uuid'] = str(addon.getSetting('uuid')) or str(uuid.uuid4())
addon.setSetting('uuid', settings['uuid'])
settings['version'] = addon.getAddonInfo('version')
settings['plexbmc_version'] = plexbmc.getAddonInfo('version')
settings['myplex_user'] = plexbmc.getSetting('myplex_user')
settings['serverList'] = []
settings['myport'] = 3005

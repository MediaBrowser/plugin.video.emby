import xbmc
import xbmcaddon
import utils

settings = {}

guisettingsXML = utils.guisettingsXML()


def getGUI(name):
    try:
        ans = list(guisettingsXML.iter(name))[0].text
        if ans is None:
            ans = ''
        return ans
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

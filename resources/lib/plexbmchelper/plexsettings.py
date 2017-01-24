import logging
from utils import guisettingsXML, settings
import variables as v

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


def getGUI(name):
    xml = guisettingsXML()
    try:
        ans = list(xml.iter(name))[0].text
        if ans is None:
            ans = ''
    except:
        ans = ''
    return ans


def getSettings():
    options = {}

    options['gdm_debug'] = settings('companionGDMDebugging')
    options['gdm_debug'] = True if options['gdm_debug'] == 'true' else False

    options['client_name'] = settings('deviceName')

    # XBMC web server options
    options['webserver_enabled'] = (getGUI('webserver') == "true")
    log.info('Webserver is set to %s' % options['webserver_enabled'])
    webserverport = getGUI('webserverport')
    try:
        webserverport = int(webserverport)
        log.info('Using webserver port %s' % str(webserverport))
    except:
        log.info('No setting for webserver port found in guisettings.xml.'
                 'Using default fallback port 8080')
        webserverport = 8080
    options['port'] = webserverport

    options['user'] = getGUI('webserverusername')
    options['passwd'] = getGUI('webserverpassword')
    log.info('Webserver username: %s, password: %s'
             % (options['user'], options['passwd']))

    options['addonName'] = v.ADDON_NAME
    options['uuid'] = settings('plex_client_Id')
    options['platform'] = v.PLATFORM
    options['version'] = v.ADDON_VERSION
    options['plexbmc_version'] = options['version']
    options['myplex_user'] = settings('username')
    try:
        options['myport'] = int(settings('companionPort'))
        log.info('Using Plex Companion Port %s' % str(options['myport']))
    except:
        log.error('Error getting Plex Companion Port from file settings. '
                  'Using fallback port 39005')
        options['myport'] = 39005
    return options

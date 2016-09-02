from utils import guisettingsXML, settings, logMsg
import clientinfo


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
    client = clientinfo.ClientInfo()
    options = {}
    title = 'PlexCompanion Settings'

    options['gdm_debug'] = settings('companionGDMDebugging')
    options['gdm_debug'] = True if options['gdm_debug'] == 'true' else False

    options['client_name'] = settings('deviceName')

    # XBMC web server options
    options['webserver_enabled'] = (getGUI('webserver') == "true")
    logMsg(title, 'Webserver is set to %s' % options['webserver_enabled'], 0)
    webserverport = getGUI('webserverport')
    try:
        webserverport = int(webserverport)
        logMsg(title, 'Using webserver port %s' % str(webserverport), 0)
    except:
        logMsg(title, 'No setting for webserver port found in guisettings.xml.'
               'Using default fallback port 8080', 0)
        webserverport = 8080
    options['port'] = webserverport

    options['user'] = getGUI('webserverusername')
    options['passwd'] = getGUI('webserverpassword')
    logMsg(title, 'Webserver username: %s, password: %s'
           % (options['user'], options['passwd']), 1)

    options['addonName'] = client.getAddonName()
    options['uuid'] = settings('plex_client_Id')
    options['platform'] = client.getPlatform()
    options['version'] = client.getVersion()
    options['plexbmc_version'] = options['version']
    options['myplex_user'] = settings('username')
    try:
        options['myport'] = int(settings('companionPort'))
        logMsg(title, 'Using Plex Companion Port %s'
               % str(options['myport']), 0)
    except:
        logMsg(title, 'Error getting Plex Companion Port from file settings. '
               'Using fallback port 39005', -1)
        options['myport'] = 39005
    return options

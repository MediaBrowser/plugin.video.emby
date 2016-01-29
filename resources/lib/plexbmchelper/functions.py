import base64
import inspect
import json
import string
import traceback
import xbmc
from settings import settings
from httppersist import requests

def xbmc_photo():
    return "photo"
def xbmc_video():
    return "video"
def xbmc_audio():
    return "audio"

def plex_photo():
    return "photo"
def plex_video():
    return "video"
def plex_audio():
    return "music"

def xbmc_type(plex_type):
    if plex_type == plex_photo():
        return xbmc_photo()
    elif plex_type == plex_video():
        return xbmc_video()
    elif plex_type == plex_audio():
        return xbmc_audio()
        
def plex_type(xbmc_type):
    if xbmc_type == xbmc_photo():
        return plex_photo()
    elif xbmc_type == xbmc_video():
        return plex_video()
    elif xbmc_type == xbmc_audio():
        return plex_audio()

def getPlatform():
    if xbmc.getCondVisibility('system.platform.osx'):
        return "MacOSX"
    elif xbmc.getCondVisibility('system.platform.atv2'):
        return "AppleTV2"
    elif xbmc.getCondVisibility('system.platform.ios'):
        return "iOS"
    elif xbmc.getCondVisibility('system.platform.windows'):
        return "Windows"
    elif xbmc.getCondVisibility('system.platform.raspberrypi'):
        return "RaspberryPi"
    elif xbmc.getCondVisibility('system.platform.linux'):
        return "Linux"
    elif xbmc.getCondVisibility('system.platform.android'): 
        return "Android"
    return "Unknown"
    
def printDebug( msg, functionname=True ):
    if settings['debug']:
        if functionname is False:
            print str(msg)
        else:
            print "PleXBMC Helper -> " + inspect.stack()[1][3] + ": " + str(msg)
            
""" communicate with XBMC """
def jsonrpc(action, arguments = {}):
    """ put some JSON together for the JSON-RPC APIv6 """
    if action.lower() == "sendkey":
        request=json.dumps({ "jsonrpc" : "2.0" , "method" : "Input.SendText", "params" : { "text" : self.arguments[0], "done" : False }} )
    elif action.lower() == "ping":
        request=json.dumps({ "jsonrpc" : "2.0",
                             "id" : 1 ,
                             "method"  : "JSONRPC.Ping" })
    elif action.lower() == "playmedia":
        xbmc.Player().play("plugin://plugin.video.plexkodiconnect/"
                           "?mode=companion&arguments=%s"
                           % arguments)
        return True
    elif arguments:
        request=json.dumps({ "id" : 1,
                             "jsonrpc" : "2.0",
                             "method"  : action,
                             "params"  : arguments})
    else:
        request=json.dumps({ "id" : 1,
                             "jsonrpc" : "2.0",
                             "method"  : action})
    
    printDebug("Sending request to XBMC without network stack: %s" % request)
    result = parseJSONRPC(xbmc.executeJSONRPC(request))

    if not result and settings['webserver_enabled']:
        # xbmc.executeJSONRPC appears to fail on the login screen, but going
        # through the network stack works, so let's try the request again
        result = parseJSONRPC(requests.post(
            "127.0.0.1",
            settings['port'],
            "/jsonrpc",
            request,
            { 'Content-Type' : 'application/json',
              'Authorization' : 'Basic ' + string.strip(base64.encodestring(settings['user'] + ':' + settings['passwd'])) }))

    return result



def parseJSONRPC(jsonraw):
    if not jsonraw:
        printDebug("Empty response from XBMC")
        return {}
    else:
        printDebug("Response from XBMC: %s" % jsonraw)
        parsed=json.loads(jsonraw)
    if parsed.get('error', False):
        print "XBMC returned an error: %s" % parsed.get('error')
    return parsed.get('result', {})

def getXMLHeader():
    return '<?xml version="1.0" encoding="utf-8"?>'+"\r\n"

def getOKMsg():
    return getXMLHeader() + '<Response code="200" status="OK" />'

def getPlexHeaders():
    h = {
      "Content-type": "application/x-www-form-urlencoded",
      "Access-Control-Allow-Origin": "*",
      "X-Plex-Version": settings['version'],
      "X-Plex-Client-Identifier": settings['uuid'],
      "X-Plex-Provides": "player",
      "X-Plex-Product": "PlexKodiConnect",
      "X-Plex-Device-Name": settings['client_name'],
      "X-Plex-Platform": "XBMC",
      "X-Plex-Model": getPlatform(),
      "X-Plex-Device": "PC",
    }
    if settings['myplex_user']:
        h["X-Plex-Username"] = settings['myplex_user']
    return h

def getServerByHost(host):
    list = settings['serverList']
    if len(list) == 1:
        return list[0]
    for server in list:
        if server.get('serverName') in host or server.get('server') in host:
            return server
    return {}
    
def getPlayers():
    info = jsonrpc("Player.GetActivePlayers") or []
    ret = {}
    for player in info:
        player['playerid'] = int(player['playerid'])
        ret[player['type']] = player
    return ret
    
def getPlayerIds():
    ret = []
    for player in getPlayers().values():
        ret.append(player['playerid'])
    return ret
    
def getVideoPlayerId(players = False):
    if players is None:
        players = getPlayers()
    return players.get(xbmc_video(), {}).get('playerid', None)

def getAudioPlayerId(players = False):
    if players is None:
        players = getPlayers()
    return players.get(xbmc_audio(), {}).get('playerid', None)

def getPhotoPlayerId(players = False):
    if players is None:
        players = getPlayers()
    return players.get(xbmc_photo(), {}).get('playerid', None)
    
def getVolume():
    return str(jsonrpc('Application.GetProperties', { "properties": [ "volume" ] }).get('volume', 100))

def timeToMillis(time):
    return (time['hours']*3600 + time['minutes']*60 + time['seconds'])*1000 + time['milliseconds']

def millisToTime(t):
    millis = int(t)
    seconds = millis / 1000
    minutes = seconds / 60
    hours = minutes / 60
    seconds = seconds % 60
    minutes = minutes % 60
    millis = millis % 1000
    return {'hours':hours,'minutes':minutes,'seconds':seconds,'milliseconds':millis}

def textFromXml(element):
    return element.firstChild.data
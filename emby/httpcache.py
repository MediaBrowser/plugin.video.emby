import threading
from helper import utils
import xbmc

CacheLock = threading.Lock()
CacheByPlaySessionId = {}
CacheByHTTPRequest = {}
Counter = 4

def get(HTTPRequest):
    global Counter

    with utils.SafeLock(CacheLock):
        if HTTPRequest in CacheByHTTPRequest:
            Counter = 4 # Reset Timer on http requests
            return CacheByHTTPRequest[HTTPRequest]

    return ""

def add(MetaData, Response):
    global Counter

    with utils.SafeLock(CacheLock):
        Counter = 4 # Reset Timer on http requests
        CacheByPlaySessionId[MetaData['PlaySessionId']] = MetaData['Payload']
        CacheByHTTPRequest[MetaData['Payload']] = (MetaData, Response)

def delete(PlaySessionId):
    with utils.SafeLock(CacheLock):
        if PlaySessionId in CacheByPlaySessionId:
            del CacheByHTTPRequest[CacheByPlaySessionId[PlaySessionId]]
            del CacheByPlaySessionId[PlaySessionId]

# Reset cache after 1 second
def clear():
    global Counter

    if utils.DebugLog:
        xbmc.log("EMBY.emby.httpcache (DEBUG): THREAD: --->[ clear ]", 1) # LOGDEBUG

    while True:
        if utils.sleep(0.2):
            if utils.DebugLog:
                xbmc.log("EMBY.emby.httpcache (DEBUG): THREAD: ---<[ clear ]", 1) # LOGDEBUG

            return

        with utils.SafeLock(CacheLock):
            if Counter:
                Counter -= 1
                continue

            Counter = 4
            CacheByPlaySessionId.clear()
            CacheByHTTPRequest.clear()

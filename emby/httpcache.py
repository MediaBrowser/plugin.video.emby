import threading
from helper import utils

CacheLock = threading.Lock()
CacheByPlaySessionId = {}
CacheByHTTPRequest = {}
Counter = 5

def get(HTTPRequest):
    global Counter

    with utils.SafeLock(CacheLock):
        if HTTPRequest in CacheByHTTPRequest:
            Counter = 5 # Reset Timer on http requests
            return CacheByHTTPRequest[HTTPRequest]

    return ""

def add(MetaData, Response):
    global Counter

    with utils.SafeLock(CacheLock):
        Counter = 5 # Reset Timer on http requests
        CacheByPlaySessionId[MetaData['PlaySessionId']] = MetaData['Payload']
        CacheByHTTPRequest[MetaData['Payload']] = (MetaData, Response)

def delete(PlaySessionId):
    with utils.SafeLock(CacheLock):
        if PlaySessionId in CacheByPlaySessionId:
            del CacheByHTTPRequest[CacheByPlaySessionId[PlaySessionId]]
            del CacheByPlaySessionId[PlaySessionId]

# Reset cache after 1 second
def clear():
    global CacheByPlaySessionId
    global CacheByHTTPRequest
    global Counter

    while True:
        while Counter:
            if utils.sleep(0.2):
                return

            Counter -= 1

        with utils.SafeLock(CacheLock):
            Counter = 5
            CacheByPlaySessionId = {}
            CacheByHTTPRequest = {}

# -*- coding: utf-8 -*-

###############################################################################
import logging

from utils import window, settings
import variables as v

###############################################################################

log = logging.getLogger("PLEX."+__name__)

###############################################################################


def getXArgsDeviceInfo(options=None):
    """
    Returns a dictionary that can be used as headers for GET and POST
    requests. An authentication option is NOT yet added.

    Inputs:
        options:        dictionary of options that will override the
                        standard header options otherwise set.
    Output:
        header dictionary
    """
    xargs = {
        'Accept': '*/*',
        'Connection': 'keep-alive',
        "Content-Type": "application/x-www-form-urlencoded",
        # "Access-Control-Allow-Origin": "*",
        # 'X-Plex-Language': 'en',
        'X-Plex-Device': v.ADDON_NAME,
        'X-Plex-Client-Platform': v.PLATFORM,
        'X-Plex-Device-Name': v.DEVICENAME,
        'X-Plex-Platform': v.PLATFORM,
        # 'X-Plex-Platform-Version': 'unknown',
        # 'X-Plex-Model': 'unknown',
        'X-Plex-Product': v.ADDON_NAME,
        'X-Plex-Version': v.ADDON_VERSION,
        'X-Plex-Client-Identifier': getDeviceId(),
        'X-Plex-Provides': 'client,controller,player,pubsub-player',
    }
    if window('pms_token'):
        xargs['X-Plex-Token'] = window('pms_token')
    if options is not None:
        xargs.update(options)
    return xargs


def getDeviceId(reset=False):
    """
    Returns a unique Plex client id "X-Plex-Client-Identifier" from Kodi
    settings file.
    Also loads Kodi window property 'plex_client_Id'

    If id does not exist, create one and save in Kodi settings file.
    """
    if reset is True:
        window('plex_client_Id', clear=True)
        settings('plex_client_Id', value="")

    clientId = window('plex_client_Id')
    if clientId:
        return clientId

    clientId = settings('plex_client_Id')
    # Because Kodi appears to cache file settings!!
    if clientId != "" and reset is False:
        window('plex_client_Id', value=clientId)
        log.info("Unique device Id plex_client_Id loaded: %s" % clientId)
        return clientId

    log.info("Generating a new deviceid.")
    from uuid import uuid4
    clientId = str(uuid4())
    settings('plex_client_Id', value=clientId)
    window('plex_client_Id', value=clientId)
    log.info("Unique device Id plex_client_Id loaded: %s" % clientId)
    return clientId

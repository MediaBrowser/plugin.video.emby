# -*- coding: utf-8 -*-
# THREAD SAFE

# Quit PKC
STOP_PKC = False


# Usually triggered by another Python instance - will have to be set (by
# polling window) through e.g. librarysync thread
SUSPEND_LIBRARY_THREAD = False
# Set if user decided to cancel sync
STOP_SYNC = False
# Set if a Plex-Kodi DB sync is being done - along with
# window('plex_dbScan') set to 'true'
DB_SCAN = False
# Plex Media Server Status - along with window('plex_serverStatus')
PMS_STATUS = False
# When the userclient needs to wait
SUSPEND_USER_CLIENT = False
# Plex home user? Then "False". Along with window('plex_restricteduser')
RESTRICTED_USER = False
# Direct Paths (True) or Addon Paths (False)? Along with
# window('useDirectPaths')
DIRECT_PATHS = False
# Along with window('plex_authenticated')
AUTHENTICATED = False
PLEX_TOKEN = None

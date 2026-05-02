import json
import xbmc
from helper import utils
from . import common

class Photo:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, _):
        EmbyItem = Item.copy()
        common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], None, False)
        self.SQLs["emby"].add_reference_photo(Item['Id'], Item['LibraryId'], Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item['KodiFullPath'], json.dumps(EmbyItem))
        del EmbyItem
        if utils.DebugLog: xbmc.log(f"EMBY.core.photo (DEBUG): ADD OR REPLACE {Item['Id']}: {Item['Path']}", 1) # DEBUGLOG
        return False

    def remove(self, Item, IncrementalSync):
        self.SQLs["emby"].remove_item(Item['Id'], "photo", Item['LibraryId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.photo: DELETE {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.photo (DEBUG): DELETE {Item['Id']}", 1) # LOGDEBUG

    def userdata(self, Item, IncrementalSync, _UpdateKodiFavorite):
        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.photo: USERDATA {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.photo (DEBUG): USERDATA {Item['Id']}", 1) # LOGDEBUG

        return False

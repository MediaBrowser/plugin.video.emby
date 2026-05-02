import json
import xbmc
from helper import utils

class Folder:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        EmbyItem = Item.copy()

        if 'Path' in Item and Item['Path']:
            if Item['Path'].find("/") >= 0: # Linux
                Path = f"{Item['Path']}/"
            else: # Windows
                Path = f"{Item['Path']}\\"
        else:
            Path = None

        self.SQLs["emby"].add_reference_folder(Item['Id'], Item['LibraryId'], Path, json.dumps(EmbyItem))
        del EmbyItem

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.folder: ADD OR REPLACE {Item['Id']}: {Path}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.folder (DEBUG): ADD OR REPLACE {Item['Id']}: {Path}", 1) # LOGDEBUG

        return True

    def remove(self, Item, IncrementalSync):
        self.SQLs["emby"].remove_item(Item['Id'], "Folder", Item['LibraryId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.folder: DELETE {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.folder (DEBUG): DELETE {Item['Id']}", 1) # LOGDEBUG

    def userdata(self, Item, IncrementalSync, _UpdateKodiFavorite):
        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.folder: USERDATA {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.folder (DEBUG): USERDATA {Item['Id']}", 1) # LOGDEBUG

        return False

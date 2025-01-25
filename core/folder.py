import xbmc
from helper import utils

class Folder:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def change(self, Item, IncrementalSync):
        if 'Path' in Item and Item['Path']:
            if Item['Path'].find("/") >= 0: # Linux
                Path = f"{Item['Path']}/"
            else: # Windows
                Path = f"{Item['Path']}\\"

            self.SQLs["emby"].add_reference_folder(Item['Id'], Item['LibraryId'], Path)
            xbmc.log(f"EMBY.core.folder: ADD OR REPLACE {Item['Id']}: {Path}", int(IncrementalSync)) # LOG

        return True

    def remove(self, Item, IncrementalSync):
        self.SQLs["emby"].remove_item(Item['Id'], "Folder", Item['LibraryId'])
        xbmc.log(f"EMBY.core.folder: DELETE {Item['Id']}", int(IncrementalSync)) # LOG

    def userdata(self, Item):
        xbmc.log(f"EMBY.core.folder: USERDATA {Item}", 1) # LOGINFO
        self.change(Item, True)
        utils.reset_querycache("Folder")
        return False

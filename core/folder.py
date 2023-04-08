import xbmc
from . import common

class Folder:
    def __init__(self, EmbyServer, embydb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb

    def folder(self, Item):
        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return False

        if 'Path' in Item and Item['Path']:
            if Item['Path'].find("/") >= 0: # Linux
                Path = f"{Item['Path']}/"
            else: # Windows
                Path = f"{Item['Path']}\\"

            self.emby_db.add_reference(Item['Id'], [], [], None, "Folder", None, [], Item['LibraryIds'], None, None, None, Path, None, None, None)
            xbmc.log(f"EMBY.core.folder: ADD OR REPLACE folder {Item['Id']}: {Path}", 1) # LOGINFO

        return True

    def remove(self, Item):
        self.emby_db.remove_item(Item['Id'], Item['Library']['Id'])
        xbmc.log(f"EMBY.core.folder: DELETE Folder {Item['Id']}", 1) # LOGINFO

    def userdata(self, Item):
        xbmc.log(f"EMBY.core.folder: USERDATA FOLDER {Item}", 1) # LOGINFO
        Item['Library'] = {}
        self.folder(Item)

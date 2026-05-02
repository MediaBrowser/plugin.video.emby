import json
import xbmc
from helper import utils
from . import common

class Trailer:
    def __init__(self, EmbyServer, SQLs):
        self.EmbyServer = EmbyServer
        self.SQLs = SQLs

    def update_SQLs(self, SQLs): # When paused, databases are closed and re-opened -> Update database
        self.SQLs = SQLs

    def change(self, Item, _):
        EmbyItem = Item.copy()

        if 'Path' in Item and Item['Path']:
            KodiParentId = Item.get('KodiParentId', None)
            EmbyParentType = Item.get('EmbyParentType', None)
            LibraryId = Item.get('LibraryId', None)

            if Item['Path'].startswith("http"):
                KodiPath = common.set_RemoteTrailerURL(Item['Path'])
            else:
                KodiPath = Item['Path']

                # Update local trailers
                if KodiParentId:
                    if EmbyParentType in ("Movie", "Series"):
                        common.set_streams(Item)
                        common.set_chapters(Item, self.EmbyServer.ServerData['ServerId'])
                        common.set_path_filename(Item, self.EmbyServer.ServerData['ServerId'], {}, True)
                        KodiPath = Item['KodiFullPath']
                        self.SQLs["video"].update_trailer(KodiParentId, KodiPath, EmbyParentType)

            self.SQLs["emby"].add_reference_trailer(Item['Id'], LibraryId, Item['ParentId'], Item['PresentationUniqueKey'], Item['Path'], Item.get('ExtraType', None), KodiParentId, EmbyParentType, KodiPath, json.dumps(EmbyItem))
            del EmbyItem
            if utils.DebugLog: xbmc.log(f"EMBY.core.trailer (DEBUG): ADD OR REPLACE {Item['Id']}: {Item['Path']}", 1) # DEBUGLOG
        else:
            xbmc.log(f"EMBY.core.trailer: Path missing {Item['Id']}: {Item}", 2) # ERRORLOG

        return False

    def remove(self, Item, IncrementalSync):
        self.SQLs["emby"].remove_item(Item['Id'], "trailer", Item['LibraryId'])

        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.trailer: DELETE {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.trailer (DEBUG): DELETE {Item['Id']}", 1) # LOGDEBUG

    def userdata(self, Item, IncrementalSync, _UpdateKodiFavorite):
        if int(IncrementalSync):
            xbmc.log(f"EMBY.core.trailer: USERDATA {Item['Id']}", 1) # LOGINFO
        elif utils.DebugLog:
            xbmc.log(f"EMBY.core.trailer (DEBUG): USERDATA {Item['Id']}", 1) # LOGDEBUG

        return False

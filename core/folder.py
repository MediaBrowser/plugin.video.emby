from helper import loghandler
from . import common

LOG = loghandler.LOG('EMBY.core.folder')


class Folder:
    def __init__(self, EmbyServer, embydb):
        self.EmbyServer = EmbyServer
        self.emby_db = embydb

    def folder(self, Item):
        if not common.library_check(Item, self.EmbyServer, self.emby_db):
            return False

        if 'Path' in Item and Item['Path']:
            if Item['Path'].find("/") >= 0: # Linux
                Path = "%s/" % Item['Path']
            else: # Windows
                Path = "%s\\" % Item['Path']

            self.emby_db.add_reference(Item['Id'], [], [], None, "Folder", None, [], Item['LibraryIds'], None, None, None, Path, None, None, None)
            LOG.info("ADD OR REPLACE folder %s: %s" % (Item['Id'], Path))

        return True

    def remove(self, Item):
        self.emby_db.remove_item(Item['Id'], Item['Library']['Id'])
        LOG.info("DELETE Folder %s" % Item['Id'])

    def userdata(self, Item):
        LOG.info("USERDATA FOLDER %s" % Item)
        Item['Library'] = {}
        self.folder(Item)

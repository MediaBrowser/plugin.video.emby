from . import common_db

class TextureDatabase:
    def __init__(self, cursor):
        self.common = common_db.CommonDatabase(cursor)

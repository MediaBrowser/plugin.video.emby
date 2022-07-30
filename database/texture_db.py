from . import common_db


class TextureDatabase:
    def __init__(self, cursor):
        self.cursor = cursor
        self.common = common_db.CommonDatabase(cursor)

    def add_Index(self):
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_texture_cachedurl on texture (cachedurl)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_texture_imagehash on texture (imagehash)")

    def add_texture(self, url, cachedUrl, imagehash, size, width, height, KodiTime):
        self.cursor.execute("SELECT id FROM texture WHERE url = ?", (url,))
        Data = self.cursor.fetchone()

        if Data:
            idtexture = Data[0]
        else:
            self.cursor.execute("SELECT coalesce(max(id), 0) FROM texture")
            idtexture = self.cursor.fetchone()[0] + 1
            self.cursor.execute("INSERT INTO texture (url, cachedUrl, imagehash, lasthashcheck) VALUES (?, ?, ?, ?)", (url, cachedUrl, imagehash, KodiTime))

        self.cursor.execute("SELECT idtexture FROM sizes WHERE idtexture = ?", (idtexture,))
        Data = self.cursor.fetchone()

        if Data:
            self.cursor.execute("UPDATE sizes SET size = ?, width = ?, height = ?, usecount = ?, lastusetime = ? WHERE idtexture = ?", (size, width, height, "1", KodiTime, idtexture))
        else:
            self.cursor.execute("INSERT INTO sizes (idtexture, size, width, height, usecount, lastusetime) VALUES (?, ?, ?, ?, ?, ?)", (idtexture, size, width, height, "1", KodiTime))

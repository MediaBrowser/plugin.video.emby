import xbmcgui
from helper import utils


class CommonDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    # reset
    def delete_tables(self, DatabaseName):
        ProgressBar = xbmcgui.DialogProgressBG()
        ProgressBar.create(utils.Translate(33199), f"{utils.Translate(33415)}-{DatabaseName} {utils.Translate(33416)}")

        # Temporay remove triggers
        self.cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
        Triggers = self.cursor.fetchall()

        for Trigger in Triggers:
            self.cursor.execute(f"DROP TRIGGER {Trigger[0]}")

        # Temporay remove Indices
        self.cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
        Indexs = self.cursor.fetchall()

        for Index in Indexs:
            if not Index[0].startswith("sqlite_autoindex"):
                self.cursor.execute(f"DROP INDEX {Index[0]}")

        # Delete tables
        self.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        Tables = self.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(Tables) - 1)

        for Table in Tables:
            if Table[0] not in ('version', 'versiontagscan', 'videoversiontype'):
                Counter += 1
                ProgressBar.update(int(Counter * Increment), utils.Translate(33199), f"{utils.Translate(33415)}-{DatabaseName} {utils.Translate(33416)}: {Table[0]}")
                self.cursor.execute(f"DELETE FROM {Table[0]}")

        # readding triggers
        for Trigger in Triggers:
            self.cursor.execute(Trigger[1])

        # readding index
        for Index in Indexs:
            if not Index[0].startswith("sqlite_autoindex"):
                self.cursor.execute(Index[1])

        ProgressBar.close()
        del ProgressBar

    # artwork
    def delete_artwork(self, KodiId, KodiMediaType):
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", (KodiId, KodiMediaType))

    def delete_artwork_force(self, KodiId):
        self.cursor.execute("DELETE FROM art WHERE media_id = ?", (KodiId,))

    def get_artwork_urls(self, media_type):
        self.cursor.execute("SELECT url FROM art WHERE media_type = ?", (media_type,))
        return self.cursor.fetchall()

    def get_artwork_urls_all(self):
        self.cursor.execute("SELECT url FROM art")
        return self.cursor.fetchall()

    def add_artwork(self, KodiArtworks, KodiId, KodiMediaType):
        for ArtworkId, ImagePath in list(KodiArtworks.items()):
            if ArtworkId != "fanart":
                if ImagePath:
                    self.cursor.execute("INSERT INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (KodiId, KodiMediaType, ArtworkId, ImagePath))
            else:
                for ArtworkFanArtId, ImageFanArtPath in list(KodiArtworks['fanart'].items()):
                    self.cursor.execute("INSERT INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (KodiId, KodiMediaType, ArtworkFanArtId, ImageFanArtPath))

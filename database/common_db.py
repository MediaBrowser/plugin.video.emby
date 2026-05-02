from helper import utils
import xbmcvfs

class CommonDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def analyze(self):
        self.cursor.execute("ANALYZE")

    # reset
    def delete_tables(self, DatabaseName):
        utils.create_ProgressBar("delete_tables", utils.Translate(33199), f"{utils.Translate(33415)}-{DatabaseName} {utils.Translate(33416)}")

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
                utils.update_ProgressBar("delete_tables", Counter * Increment, utils.Translate(33199), f"{utils.Translate(33415)}-{DatabaseName} {utils.Translate(33416)}: {Table[0]}")
                self.cursor.execute(f"DELETE FROM {Table[0]}")

        # readding triggers
        for Trigger in Triggers:
            self.cursor.execute(Trigger[1])

        # readding index
        for Index in Indexs:
            if not Index[0].startswith("sqlite_autoindex"):
                self.cursor.execute(Index[1])

        utils.close_ProgressBar("delete_tables")

    # artwork
    def delete_artwork(self, KodiId, KodiMediaType):
        self.cursor.execute("SELECT DISTINCT url FROM art WHERE media_id = ? AND media_type = ?", (KodiId, KodiMediaType))
        URLs = self.cursor.fetchall()
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", (KodiId, KodiMediaType))
        delete_artworkcache(URLs)

    def delete_artwork_force(self, KodiId):
        self.cursor.execute("SELECT DISTINCT url FROM art WHERE media_id = ?", (KodiId,))
        URLs = self.cursor.fetchall()
        self.cursor.execute("DELETE FROM art WHERE media_id = ?", (KodiId,))
        delete_artworkcache(URLs)

    def get_artwork_urls(self, media_type):
        self.cursor.execute("SELECT url FROM art WHERE media_type = ?", (media_type,))
        return self.cursor.fetchall()

    def get_artwork_urls_all(self):
        self.cursor.execute("SELECT url FROM art")
        return self.cursor.fetchall()

    def add_artwork(self, KodiArtworks, KodiId, KodiMediaType):
        SQLData = ()

        for ArtworkId, ImagePath in list(KodiArtworks.items()):
            if ArtworkId != "fanart":
                if ImagePath:
                    SQLData += ((KodiId, KodiMediaType, ArtworkId, ImagePath),)
            else:
                for ArtworkFanArtId, ImageFanArtPath in list(KodiArtworks['fanart'].items()):
                    SQLData += ((KodiId, KodiMediaType, ArtworkFanArtId, ImageFanArtPath),)

        if SQLData:
            self.cursor.executemany("INSERT INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", SQLData)

        del SQLData
def toggle_path(CurrentPath, NewPath):
    if NewPath == "http://127.0.0.1:57342/":
        if CurrentPath.startswith("/emby_addon_mode/"):
            return f'{CurrentPath.replace("/emby_addon_mode/", "http://127.0.0.1:57342/")}|redirect-limit=1000&failonerror=false'

        return CurrentPath.replace("dav://127.0.0.1:57342/", "http://127.0.0.1:57342/")

    if NewPath == "/emby_addon_mode/":
        if CurrentPath.startswith("http://127.0.0.1:57342/"):
            return CurrentPath.replace("http://127.0.0.1:57342/", "/emby_addon_mode/").replace("|redirect-limit=1000&failonerror=false", "")

        return CurrentPath.replace("dav://127.0.0.1:57342/", "/emby_addon_mode/").replace("|redirect-limit=1000&failonerror=false", "")
    # if NewPath == "dav://127.0.0.1:57342/":
    if CurrentPath.startswith("/emby_addon_mode/"):
        return f'{CurrentPath.replace("/emby_addon_mode/", "dav://127.0.0.1:57342/")}|redirect-limit=1000&failonerror=false'

    return CurrentPath.replace("http://127.0.0.1:57342/", "dav://127.0.0.1:57342/")

def delete_artworkcache(Paths):
    for row in Paths:
        Path = row[0]

        if not Path:
            continue

        Hash = utils.kodi_hash(Path)
        PathBase = f"{utils.FolderUserdataThumbnails}{Hash[0]}/{Hash}"

        for ext in ("jpg", "png"):
            PathFile = f"{PathBase}.{ext}"

            if xbmcvfs.exists(PathFile):
                utils.delFile(PathFile)
                break

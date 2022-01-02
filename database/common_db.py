# -*- coding: utf-8 -*-
import xbmcgui


class CommonDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def delete_tables(self, DatabaseName):
        Progress = xbmcgui.DialogProgressBG()
        Progress.create("Emby", "Delete %s Database" % DatabaseName)
        self.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        tables = self.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(tables) - 1)

        for table in tables:
            name = table[0]

            if name not in ('version', 'versiontagscan'):
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Kodi-Music Database: %s" % name)
                self.cursor.execute("DELETE FROM " + name)

        Progress.close()

    def get_urls(self):
        self.cursor.execute("SELECT url FROM art")
        return self.cursor.fetchall()

    def update_artwork(self, image_url, kodi_id, media, image):
        self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodi_id, media, image))
        result = self.cursor.fetchone()

        if result:
            url = result[0]

            if url != image_url:
                if image_url:
                    self.cursor.execute("UPDATE art SET url = ? WHERE media_id = ? AND media_type = ? AND type = ?", (image_url, kodi_id, media, image))
        else:
            self.cursor.execute("INSERT OR REPLACE INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (kodi_id, media, image, image_url))

    # Add all artworks
    def add_artwork(self, ArtworkEmby, KodiId, KodiMediaType):
        ExtraThumb = False

        if KodiMediaType == "episode":
            ArtMapping = {
                'Primary': 'thumb',
                'Banner': "banner",
                'Logo': "clearlogo",
                'Art': "clearart",
                'Disc': "discart",
                'Backdrop': "fanart"
            }
        elif KodiMediaType in ("tvshow", "movie"):
            ArtMapping = {
                'Thumb': "landscape",
                'Primary': 'poster',
                'Banner': "banner",
                'Logo': "clearlogo",
                'Art': "clearart",
                'Disc': "discart",
                'Backdrop': "fanart"
            }
            ExtraThumb = True
        elif KodiMediaType in ('song', 'artist', 'album'):
            ArtMapping = {
                'Primary': 'thumb',
                'Banner': "banner",
                'Logo': "clearlogo",
                'Art': "clearart",
                'Disc': "discart",
                'Backdrop': "fanart"
            }
        else:
            ArtMapping = {
                'Thumb': "thumb",
                'Primary': "poster",
                'Banner': "banner",
                'Logo': "clearlogo",
                'Art': "clearart",
                'Disc': "discart",
                'Backdrop': "fanart"
            }

        # Primary as fallback for empty thumb
        if 'Thumb' in ArtworkEmby and 'Primary' in ArtworkEmby:
            if not ArtworkEmby['Thumb'] and ArtworkEmby['Primary']:
                ArtworkEmby['Thumb'] = ArtworkEmby['Primary']

        for ArtKey, ArtValue in ArtMapping.items():
            if ArtKey == 'Backdrop':
                if 'Backdrop' in ArtworkEmby:
                    if ArtworkEmby['Backdrop']:
                        num_backdrops = len(ArtworkEmby['Backdrop'])

                        if num_backdrops:
                            self.update_artwork(ArtworkEmby['Backdrop'][0], KodiId, KodiMediaType, "fanart")

                            for index, backdrop in enumerate(ArtworkEmby['Backdrop'][1:]):
                                self.update_artwork(backdrop, KodiId, KodiMediaType, "%s%s" % ("fanart", index + 1))

                            continue

                self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiId, KodiMediaType, "fanart"))
            else:
                if ArtKey in ArtworkEmby:
                    if ArtworkEmby[ArtKey]:
                        self.update_artwork(ArtworkEmby[ArtKey], KodiId, KodiMediaType, ArtValue)
                        continue

                self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (KodiId, KodiMediaType, ArtValue))

        if ExtraThumb:
            if 'Thumb' in ArtworkEmby:
                if ArtworkEmby['Thumb']:
                    self.update_artwork('Thumb', KodiId, KodiMediaType, "thumb")

    # Delete artwork from kodi database and remove cache for backdrop/posters
    def delete_artwork(self, *args):
        self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ?", args)

    def create_entry_path(self):
        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        return self.cursor.fetchone()[0] + 1

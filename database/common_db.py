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
                Progress.update(int(Counter * Increment), message="Delete Kodi-Music Database: " + name)
                self.cursor.execute("DELETE FROM " + name)

        Progress.close()

    def get_urls(self):
        self.cursor.execute("SELECT url FROM art")
        return self.cursor.fetchall()

    def update_artwork(self, image_url, kodi_id, media, image):
        if image == 'poster' and media in ('song', 'artist', 'album'):
            return

        self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodi_id, media, image,))
        result = self.cursor.fetchone()

        if result:
            url = result[0]

            if url != image_url:
                if image_url:
                    self.cursor.execute("UPDATE art SET url = ? WHERE media_id = ? AND media_type = ? AND type = ?", (image_url, kodi_id, media, image))
        else:
            self.cursor.execute("INSERT OR REPLACE INTO art(media_id, media_type, type, url) VALUES (?, ?, ?, ?)", (kodi_id, media, image, image_url))

    # Add all artworks
    def add_artwork(self, artwork, *args):
        KODI = {
            'Primary': ['thumb', 'poster'],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart"
        }

        for art in KODI:
            if art == 'Backdrop':
                num_backdrops = len(artwork['Backdrop'])
                self.cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type LIKE ?", args + ("fanart%",))

                if len(self.cursor.fetchall()) > num_backdrops:
                    self.cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ? AND type LIKE ?", args + ("fanart_",))

                if 'Backdrop' in artwork:
                    if artwork['Backdrop']:
                        self.update_artwork(*(artwork['Backdrop'][0] if num_backdrops else "",) + args + ("fanart",))

                for index, backdrop in enumerate(artwork['Backdrop'][1:]):
                    self.update_artwork(*(backdrop,) + args + ("%s%s" % ("fanart", index + 1),))
            elif art == 'Primary':
                for kodi_image in KODI['Primary']:
                    if 'Primary' in artwork:
                        if artwork['Primary']:
                            self.update_artwork(*(artwork['Primary'],) + args + (kodi_image,))
            else:
                if art in artwork:
                    if artwork[art]:
                        self.update_artwork(*(artwork[art],) + args + (KODI[art],))    # Delete artwork from kodi database and remove cache for backdrop/posters

    # Delete artwork from kodi database and remove cache for backdrop/posters
    def delete_artwork(self, *args):
        self.cursor.execute("SELECT url, type FROM art WHERE media_id = ? AND media_type = ?", args)

        for row in self.cursor.fetchall():
            self.cursor.execute("DELETE FROM art WHERE url = ?", (row[0],))

    def create_entry_path(self):
        self.cursor.execute("SELECT coalesce(max(idPath), 0) FROM path")
        return self.cursor.fetchone()[0] + 1
